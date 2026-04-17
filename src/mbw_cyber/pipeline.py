from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backends import resolve_backend
from .models import AssetRecord, BackendConfig, RunArtifacts, SceneSpec, SimSpec


class LLMPlanner:
    """Parses prompt payload into explicit scene/simulation contracts."""

    def parse(self, prompt_payload: dict[str, Any]) -> tuple[SceneSpec, SimSpec]:
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
        run_id = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        return RunArtifacts(run_id=run_id, root=run_dir)

    def dump_json(self, artifacts: RunArtifacts, name: str, payload: Any) -> Path:
        target = artifacts.root / name
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        artifacts.add(name, target)
        return target


def run_pipeline(prompt_payload: dict[str, Any], out_root: Path, backend: str = "web_rapier", duration_s: int = 12, hz: int = 10) -> RunArtifacts:
    planner = LLMPlanner()
    scene_spec, sim_spec = planner.parse(prompt_payload)

    store = RunStore(out_root)
    artifacts = store.create()

    assets = AssetGenerator(cache_dir=artifacts.root / "asset_cache").materialize(scene_spec)
    compiled_sim = SimulationCompiler().compile(sim_spec, scene_spec)
    scene_manifest = SceneAssembler().assemble(scene_spec, assets, artifacts.root)

    backend_config = BackendConfig(name=backend, duration_s=duration_s, hz=hz)
    runtime = resolve_backend(backend).run(compiled_sim, backend_config)

    completed_tasks = sum(
        1
        for frame in runtime["frames"]
        for state in frame["agent_states"]
        if state["progress"] >= 1.0
    )

    metrics = {
        "backend": runtime["backend"],
        "seed": sim_spec.seed,
        "frames": len(runtime["frames"]),
        "agents": len(compiled_sim.get("agents", [])),
        "completed_progress_events": completed_tasks,
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
