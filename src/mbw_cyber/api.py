from __future__ import annotations

import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import SceneSpec, SimSpec
from .pipeline import (
    AssetGenerator,
    LLMPlanner,
    RunStore,
    SceneAssembler,
    SimulationCompiler,
    run_experiment_matrix,
    run_pipeline,
)


class ApiStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.root / "runs"
        self.assets_dir = self.root / "assets"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id


class MBWApiHandler(BaseHTTPRequestHandler):
    planner = LLMPlanner()
    store = ApiStore(Path(".mbw_api"))

    def _read_json(self) -> dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_len) if content_len else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/scene/generate":
            self.handle_scene_generate()
            return
        if parsed.path == "/scene/compile":
            self.handle_scene_compile()
            return
        if parsed.path == "/scene/validate":
            self.handle_scene_validate()
            return
        if parsed.path == "/assets/generate":
            self.handle_assets_generate()
            return
        if parsed.path == "/scene/assemble":
            self.handle_scene_assemble()
            return
        if parsed.path == "/sim/run":
            self.handle_sim_run()
            return
        if parsed.path == "/sim/replay":
            self.handle_sim_replay()
            return
        if parsed.path == "/experiment/run":
            self.handle_experiment_run()
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._write_json(HTTPStatus.OK, {"ok": True})
            return
        if parsed.path == "/runs":
            self.handle_list_runs()
            return
        if parsed.path.startswith("/runs/"):
            self.handle_get_run(parsed.path.split("/", 2)[2])
            return
        if parsed.path.startswith("/assets/"):
            self.handle_get_asset(parsed.path.split("/", 2)[2])
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})

    def handle_scene_generate(self) -> None:
        payload = self._read_json()
        scene_spec, sim_spec = self.planner.parse(payload)
        self._write_json(
            HTTPStatus.OK,
            {
                "scene": asdict(scene_spec),
                "sim": asdict(sim_spec),
            },
        )

    def handle_scene_compile(self) -> None:
        payload = self._read_json()
        scene_payload = payload.get("scene") if isinstance(payload.get("scene"), dict) else payload
        sim_payload = payload.get("sim") if isinstance(payload.get("sim"), dict) else payload

        scene_spec = SceneSpec.from_payload(scene_payload)
        sim_spec = SimSpec.from_payload(sim_payload, seed=int(sim_payload.get("seed", 42)))
        compiled_sim = SimulationCompiler().compile(sim_spec, scene_spec)
        self._write_json(
            HTTPStatus.OK,
            {
                "scene_id": f"scene_{sim_spec.seed}",
                "scene": asdict(scene_spec),
                "sim": asdict(sim_spec),
                "objects": compiled_sim["physics"]["objects"],
                "compiled_sim": compiled_sim,
            },
        )

    def handle_scene_validate(self) -> None:
        payload = self._read_json()
        errors: list[str] = []

        objects = payload.get("objects")
        if objects is not None and not isinstance(objects, list):
            errors.append("objects must be a list")
        if isinstance(objects, list):
            for index, obj in enumerate(objects):
                if not isinstance(obj, dict):
                    errors.append(f"objects[{index}] must be an object")
                    continue
                if "id" not in obj:
                    errors.append(f"objects[{index}] is missing id")

        valid = len(errors) == 0
        self._write_json(HTTPStatus.OK if valid else HTTPStatus.BAD_REQUEST, {"valid": valid, "errors": errors})

    def handle_assets_generate(self) -> None:
        payload = self._read_json()
        scene_spec = SceneSpec.from_payload(payload)
        generator = AssetGenerator(cache_dir=self.store.assets_dir)
        assets = generator.materialize(scene_spec)
        self._write_json(HTTPStatus.OK, {"assets": [asdict(a) for a in assets]})

    def handle_scene_assemble(self) -> None:
        payload = self._read_json()
        scene_spec = SceneSpec.from_payload(payload)
        assets = AssetGenerator(cache_dir=self.store.assets_dir).materialize(scene_spec)
        assembled = SceneAssembler().assemble(scene_spec, assets, self.store.root)
        self._write_json(HTTPStatus.OK, {"scene": assembled})

    def handle_sim_run(self) -> None:
        payload = self._read_json()
        backend = payload.get("backend", "web_rapier")
        duration_s = int(payload.get("duration", 12))
        hz = int(payload.get("hz", 10))
        requested_metrics = payload.get("metrics") if isinstance(payload.get("metrics"), list) else None

        artifacts = run_pipeline(
            payload,
            self.store.runs_dir,
            backend=backend,
            duration_s=duration_s,
            hz=hz,
            requested_metrics=requested_metrics,
        )
        self._write_json(HTTPStatus.OK, {"run_id": artifacts.run_id, "run_dir": str(artifacts.root)})

    def handle_sim_replay(self) -> None:
        payload = self._read_json()
        run_id = payload.get("run_id", "")
        run_dir = self.store.run_dir(run_id)
        replay_file = run_dir / "replay.json"
        trajectory_file = run_dir / "trajectory.json"
        if not replay_file.exists() or not trajectory_file.exists():
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Run not found"})
            return
        replay = json.loads(replay_file.read_text(encoding="utf-8"))
        trajectory = json.loads(trajectory_file.read_text(encoding="utf-8"))
        self._write_json(HTTPStatus.OK, {"replay": replay, "trajectory": trajectory})

    def handle_experiment_run(self) -> None:
        payload = self._read_json()
        base = payload.get("base") if isinstance(payload.get("base"), dict) else {}
        experiment = payload.get("experiment") if isinstance(payload.get("experiment"), dict) else {}
        backend = payload.get("backend", "web_rapier")
        duration_s = int(payload.get("duration", 8))
        hz = int(payload.get("hz", 6))

        matrix = run_experiment_matrix(
            base,
            experiment,
            self.store.runs_dir,
            backend=backend,
            duration_s=duration_s,
            hz=hz,
        )
        self._write_json(HTTPStatus.OK, {"matrix": matrix})

    def handle_list_runs(self) -> None:
        runs: list[dict[str, Any]] = []
        for run_dir in sorted(self.store.runs_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            summary_file = run_dir / "run_summary.json"
            metrics_file = run_dir / "metrics.json"
            if not summary_file.exists() or not metrics_file.exists():
                continue
            runs.append(
                {
                    "run_id": run_dir.name,
                    "summary": json.loads(summary_file.read_text(encoding="utf-8")),
                    "metrics": json.loads(metrics_file.read_text(encoding="utf-8")),
                }
            )
        self._write_json(HTTPStatus.OK, {"runs": runs})

    def handle_get_run(self, run_id: str) -> None:
        run_dir = self.store.run_dir(run_id)
        if not run_dir.exists():
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Run not found"})
            return

        summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
        self._write_json(HTTPStatus.OK, {"summary": summary, "metrics": metrics})

    def handle_get_asset(self, asset_id: str) -> None:
        asset_path = self.store.assets_dir / f"{asset_id}.asset.json"
        if not asset_path.exists():
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Asset not found"})
            return
        asset = json.loads(asset_path.read_text(encoding="utf-8"))
        self._write_json(HTTPStatus.OK, {"asset": asset})


def create_server(host: str = "127.0.0.1", port: int = 8000, state_root: str = ".mbw_api") -> ThreadingHTTPServer:
    MBWApiHandler.store = ApiStore(Path(state_root))
    return ThreadingHTTPServer((host, port), MBWApiHandler)


def run_server(host: str = "127.0.0.1", port: int = 8000, state_root: str = ".mbw_api") -> None:
    server = create_server(host=host, port=port, state_root=state_root)
    print(f"MBW API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
