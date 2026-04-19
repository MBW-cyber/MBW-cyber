from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

from .backends import resolve_backend
from .experiment import ExperimentSpec, apply_case, seeded_case, variation_cases
from .models import AssetRecord, BackendConfig, RunArtifacts, SceneSpec, SimSpec


class LLMPlanner:
    """Parses prompt payload into explicit scene/simulation contracts."""

    def parse(self, prompt_payload: dict[str, Any]) -> tuple[SceneSpec, SimSpec]:
        explicit_seed = prompt_payload.get("seed")
        if explicit_seed is not None:
            seed = int(explicit_seed)
        else:
            payload_str = json.dumps(prompt_payload, sort_keys=True)
            seed = int(hashlib.sha256(payload_str.encode()).hexdigest()[:8], 16)
        scene = SceneSpec.from_payload(prompt_payload)
        sim = SimSpec.from_payload(prompt_payload, seed=seed)
        return scene, sim


class AssetGenerator:
    """Asset retrieval/generation with deterministic cache and basic repair metadata."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def materialize(self, scene_spec: SceneSpec) -> list[AssetRecord]:
        assets: list[AssetRecord] = []
        for obj in scene_spec.objects:
            obj_id = obj["id"]
            klass = obj.get("class", "unknown")
            source = obj.get("source", "asset_library")
            prompt = obj.get("prompt", klass)

            key = hashlib.md5(f"{source}:{klass}:{prompt}".encode()).hexdigest()
            asset_path = self.cache_dir / f"{key}.asset.json"

            if not asset_path.exists():
                payload = {
                    "id": obj_id,
                    "class": klass,
                    "source": source,
                    "prompt": prompt,
                    "retrieval": "generated" if source == "generate" else "asset_library",
                    "repair": {"watertight": True, "normals_fixed": True},
                    "exports": {"usd": f"{key}.usd", "glb": f"{key}.glb"},
                }
                asset_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            assets.append(
                AssetRecord(
                    id=obj_id,
                    klass=klass,
                    source=source,
                    path=str(asset_path),
                    repaired=True,
                )
            )
        return assets


class SimulationCompiler:
    """Compiles simulation specs into runtime-ready contracts."""

    def compile(self, sim_spec: SimSpec, scene_spec: SceneSpec) -> dict[str, Any]:
        object_physics = []
        for obj in scene_spec.objects:
            physics = obj.get("physics", {})
            object_physics.append(
                {
                    "id": obj["id"],
                    "body": physics.get("body", "static"),
                    "mass": physics.get("mass", 0),
                    "position": obj.get("position", [0, 0, 0]),
                    "speed_limit": physics.get("speed_limit"),
                }
            )

        return {
            "seed": sim_spec.seed,
            "physics": {"gravity": [0, -9.81, 0], "objects": object_physics},
            "agents": sim_spec.agents,
            "agent_goals": {a.get("id", f"agent_{i}"): a.get("goal", "") for i, a in enumerate(sim_spec.agents)},
            "event_graph": sorted(sim_spec.events, key=lambda e: e.get("t", 0)),
        }


class SceneAssembler:
    """Generates scene manifest, master USD placeholder, and GLB export placeholder."""

    def assemble(self, scene_spec: SceneSpec, assets: list[AssetRecord], output_dir: Path) -> dict[str, Any]:
        objects_by_id = {obj["id"]: obj for obj in scene_spec.objects}
        nodes: list[dict[str, Any]] = []

        for asset in assets:
            obj = objects_by_id.get(asset.id, {})
            nodes.append(
                {
                    "id": asset.id,
                    "class": asset.klass,
                    "asset_path": asset.path,
                    "transform": {
                        "position": obj.get("position", [0, 0, 0]),
                        "rotation": obj.get("rotation", [0, 0, 0]),
                    },
                    "collider": asset.collider,
                    "lod": asset.lod,
                }
            )

        usd_master = output_dir / "scene_master.usda"
        glb_export = output_dir / "scene_preview.glb.json"

        usd_master.write_text(
            "#usda 1.0\n# Generated placeholder master scene\n",
            encoding="utf-8",
        )
        glb_export.write_text(json.dumps({"nodes": len(nodes), "format": "glb"}, indent=2), encoding="utf-8")

        return {
            "environment": scene_spec.environment,
            "nodes": nodes,
            "exports": {"usd_master": str(usd_master), "glb_preview": str(glb_export)},
            "viewer": {"web": "rapier", "native": "genesis_isaac"},
        }


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self) -> RunArtifacts:
        base = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S")
        for idx in range(1000):
            suffix = "Z" if idx == 0 else f"Z_{idx:03d}"
            run_id = f"{base}{suffix}"
            run_dir = self.root / run_id
            if not run_dir.exists():
                run_dir.mkdir(parents=True, exist_ok=False)
                return RunArtifacts(run_id=run_id, root=run_dir)
        raise RuntimeError("Could not create a unique run directory")

    def dump_json(self, artifacts: RunArtifacts, name: str, payload: Any) -> Path:
        target = artifacts.root / name
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        artifacts.add(name, target)
        return target


def _compute_requested_metrics(compiled_sim: dict[str, Any], runtime: dict[str, Any], requested: list[str] | None) -> dict[str, float]:
    if not requested:
        requested = ["task_completion"]

    rng = Random(compiled_sim["seed"])
    workers = max(1, len(compiled_sim.get("agents", [])))
    forklift_speed = 1.0
    for obj in compiled_sim.get("physics", {}).get("objects", []):
        if obj.get("speed_limit"):
            forklift_speed = float(obj["speed_limit"])
            break

    frames = runtime.get("frames", [])
    final_states = frames[-1].get("agent_states", []) if frames else []
    avg_progress = sum(s.get("progress", 0.0) for s in final_states) / max(1, len(final_states))

    results: dict[str, float] = {}
    for metric in requested:
        if metric == "task_completion":
            results[metric] = round(avg_progress, 4)
        elif metric == "travel_time":
            results[metric] = round(max(1.0, 100.0 / (forklift_speed * avg_progress + 0.05)), 3)
        elif metric == "collisions":
            collision_score = (workers * forklift_speed * 0.3) + rng.random()
            results[metric] = round(collision_score, 3)
    return results


def run_pipeline(
    prompt_payload: dict[str, Any],
    out_root: Path,
    backend: str = "web_rapier",
    duration_s: int = 12,
    hz: int = 10,
    requested_metrics: list[str] | None = None,
) -> RunArtifacts:
    planner = LLMPlanner()
    scene_spec, sim_spec = planner.parse(prompt_payload)

    store = RunStore(out_root)
    artifacts = store.create()

    assets = AssetGenerator(cache_dir=artifacts.root / "asset_cache").materialize(scene_spec)
    compiled_sim = SimulationCompiler().compile(sim_spec, scene_spec)
    scene_manifest = SceneAssembler().assemble(scene_spec, assets, artifacts.root)

    backend_config = BackendConfig(name=backend, duration_s=duration_s, hz=hz)
    runtime = resolve_backend(backend).run(compiled_sim, backend_config)

    metric_values = _compute_requested_metrics(compiled_sim, runtime, requested_metrics)
    metrics = {
        "backend": runtime["backend"],
        "seed": sim_spec.seed,
        "frames": len(runtime["frames"]),
        "agents": len(compiled_sim.get("agents", [])),
        "requested_metrics": metric_values,
    }

    replay = {
        "run_id": artifacts.run_id,
        "seed": sim_spec.seed,
        "backend": runtime["backend"],
        "trajectory_file": "trajectory.json",
    }

    store.dump_json(artifacts, "scene_spec.json", asdict(scene_spec))
    store.dump_json(artifacts, "sim_spec.json", asdict(sim_spec))
    store.dump_json(artifacts, "assets_manifest.json", [asdict(a) for a in assets])
    store.dump_json(artifacts, "compiled_sim.json", compiled_sim)
    store.dump_json(artifacts, "scene_manifest.json", scene_manifest)
    store.dump_json(artifacts, "trajectory.json", runtime)
    store.dump_json(artifacts, "metrics.json", metrics)
    store.dump_json(artifacts, "replay.json", replay)
    store.dump_json(artifacts, "run_summary.json", artifacts.to_json())

    return artifacts


def run_experiment_matrix(
    base_payload: dict[str, Any],
    experiment_payload: dict[str, Any],
    out_root: Path,
    backend: str = "web_rapier",
    duration_s: int = 12,
    hz: int = 10,
) -> list[dict[str, Any]]:
    spec = ExperimentSpec.from_payload(experiment_payload)
    cases = variation_cases(spec)
    matrix_results: list[dict[str, Any]] = []

    for idx, case in enumerate(cases):
        case_seed = seeded_case(spec.seed, case)
        payload = apply_case(base_payload, case, case_seed)
        artifacts = run_pipeline(
            payload,
            out_root,
            backend=backend,
            duration_s=duration_s,
            hz=hz,
            requested_metrics=spec.metrics,
        )

        metrics = json.loads((artifacts.root / "metrics.json").read_text(encoding="utf-8"))
        matrix_results.append(
            {
                "case_id": idx,
                "case": case,
                "seed": case_seed,
                "run_id": artifacts.run_id,
                "metrics": metrics.get("requested_metrics", {}),
                "run_dir": str(artifacts.root),
            }
        )

    summary_path = out_root / "experiment_matrix.json"
    summary_path.write_text(json.dumps(matrix_results, indent=2), encoding="utf-8")
    return matrix_results
