"""Validate the real implementation against every schema embedded in SPEC.md.

SPEC.md is the contract: each ```json block is a JSON Schema with an $id.
These tests run the actual pipeline, experiment matrix, and HTTP API, and
check that every input example and every produced artifact conforms.
"""
from __future__ import annotations

import json
import re
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest
from jsonschema import validate

from mbw_cyber.api import create_server
from mbw_cyber.pipeline import run_experiment_matrix, run_pipeline

ROOT = Path(__file__).resolve().parents[1]

BASE_PAYLOAD = {
    "environment": {"type": "warehouse", "size": [20, 12, 6]},
    "objects": [
        {
            "id": "forklift_1",
            "class": "forklift",
            "source": "generate",
            "prompt": "yellow forklift",
            "position": [2, 0, 4],
            "physics": {"body": "dynamic", "mass": 1200},
        },
        {"id": "pallet_stack_1", "class": "pallet_stack", "source": "asset_library"},
    ],
    "agents": [{"id": "worker_1", "goal": "move pallet", "policy": "llm_planner"}],
    "events": [{"t": 2, "type": "spawn", "target": "forklift_2"}],
}

EXPERIMENT_PAYLOAD = {
    "seed": 18442,
    "variations": {"num_workers": [2, 5], "forklift_speed": [1.0, 2.4]},
    "metrics": ["collisions", "task_completion", "travel_time"],
}

ARTIFACT_SCHEMAS = {
    "scene_spec.json": "mbw-cyber/scene_spec",
    "sim_spec.json": "mbw-cyber/sim_spec",
    "assets_manifest.json": "mbw-cyber/assets_manifest",
    "compiled_sim.json": "mbw-cyber/compiled_sim",
    "scene_manifest.json": "mbw-cyber/scene_manifest",
    "trajectory.json": "mbw-cyber/trajectory",
    "metrics.json": "mbw-cyber/metrics",
    "replay.json": "mbw-cyber/replay",
    "run_summary.json": "mbw-cyber/run_summary",
}


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict]:
    text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    blocks = re.findall(r"^```json\n(.*?)^```", text, flags=re.DOTALL | re.MULTILINE)
    return {json.loads(b)["$id"]: json.loads(b) for b in blocks}


@pytest.fixture(scope="module")
def run_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("conformance_runs")
    run_pipeline(
        BASE_PAYLOAD,
        root,
        backend="web_rapier",
        duration_s=2,
        hz=3,
        requested_metrics=["collisions", "task_completion", "travel_time"],
    )
    return root


def test_example_scene_spec_conforms(schemas: dict[str, dict]) -> None:
    payload = json.loads((ROOT / "examples/warehouse_spec.json").read_text(encoding="utf-8"))
    validate(payload, schemas["mbw-cyber/prompt_payload"])


def test_example_experiment_spec_conforms(schemas: dict[str, dict]) -> None:
    payload = json.loads((ROOT / "examples/experiment_spec.json").read_text(encoding="utf-8"))
    validate(payload, schemas["mbw-cyber/experiment_spec"])


@pytest.mark.parametrize("artifact_name", sorted(ARTIFACT_SCHEMAS))
def test_run_artifact_conforms(schemas: dict[str, dict], run_root: Path, artifact_name: str) -> None:
    run_dir = next(p for p in run_root.iterdir() if p.is_dir())
    payload = json.loads((run_dir / artifact_name).read_text(encoding="utf-8"))
    validate(payload, schemas[ARTIFACT_SCHEMAS[artifact_name]])


def test_experiment_matrix_conforms(schemas: dict[str, dict], tmp_path: Path) -> None:
    run_experiment_matrix(BASE_PAYLOAD, EXPERIMENT_PAYLOAD, tmp_path, duration_s=2, hz=2)
    matrix = json.loads((tmp_path / "experiment_matrix.json").read_text(encoding="utf-8"))
    validate(matrix, schemas["mbw-cyber/experiment_matrix"])
    assert len(matrix) == 4


def test_api_responses_conform(schemas: dict[str, dict], tmp_path: Path) -> None:
    server = create_server(host="127.0.0.1", port=0, state_root=str(tmp_path / "api_state"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        conn = HTTPConnection(host, port)

        def call(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
            body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
            conn.request(method, path, body=body, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))

        status, generated = call("POST", "/scene/generate", BASE_PAYLOAD)
        assert status == 200
        validate(generated["scene"], schemas["mbw-cyber/scene_spec"])
        validate(generated["sim"], schemas["mbw-cyber/sim_spec"])

        status, compiled = call("POST", "/scene/compile", {"scene": generated["scene"], "sim": generated["sim"]})
        assert status == 200
        validate(compiled["compiled_sim"], schemas["mbw-cyber/compiled_sim"])

        run_payload = dict(BASE_PAYLOAD)
        run_payload.update({"duration": 2, "hz": 2, "metrics": ["collisions", "task_completion"]})
        status, run_resp = call("POST", "/sim/run", run_payload)
        assert status == 200
        run_id = run_resp["run_id"]

        status, replay = call("POST", "/sim/replay", {"run_id": run_id})
        assert status == 200
        validate(replay["replay"], schemas["mbw-cyber/replay"])
        validate(replay["trajectory"], schemas["mbw-cyber/trajectory"])

        status, run_info = call("GET", f"/runs/{run_id}")
        assert status == 200
        validate(run_info["summary"], schemas["mbw-cyber/run_summary"])
        validate(run_info["metrics"], schemas["mbw-cyber/metrics"])

        conn.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_validate_endpoint_matches_schema_requirements(schemas: dict[str, dict], tmp_path: Path) -> None:
    """POST /scene/validate must accept exactly what the prompt_payload schema accepts.

    Per the schema, objects[].id is the only required field; class is optional
    (default "unknown").
    """
    server = create_server(host="127.0.0.1", port=0, state_root=str(tmp_path / "api_state"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        conn = HTTPConnection(host, port)

        def call(payload: dict) -> tuple[int, dict]:
            body = json.dumps(payload).encode("utf-8")
            conn.request("POST", "/scene/validate", body=body, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))

        # Schema-valid: id present, class omitted.
        no_class = {"objects": [{"id": "thing_1"}]}
        validate(no_class, schemas["mbw-cyber/prompt_payload"])
        status, result = call(no_class)
        assert status == 200 and result["valid"] is True

        # Schema-invalid: id missing.
        no_id = {"objects": [{"class": "forklift"}]}
        with pytest.raises(Exception):
            validate(no_id, schemas["mbw-cyber/prompt_payload"])
        status, result = call(no_id)
        assert status == 400 and result["valid"] is False

        conn.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)
