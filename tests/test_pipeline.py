from __future__ import annotations

import json
from pathlib import Path

from mbw_cyber.pipeline import run_pipeline


def test_pipeline_generates_expected_artifacts(tmp_path: Path) -> None:
    payload = {
        "environment": {"type": "warehouse"},
        "objects": [
            {
                "id": "forklift_1",
                "class": "forklift",
                "source": "generate",
                "prompt": "yellow forklift",
                "physics": {"body": "dynamic", "mass": 1200},
            }
        ],
        "agents": [{"id": "worker_1", "goal": "move pallet"}],
        "events": [{"t": 1, "type": "spawn", "target": "forklift_2"}],
    }

    artifacts = run_pipeline(payload, tmp_path, backend="genesis_isaac", duration_s=3, hz=4)

    expected = {
        "scene_spec.json",
        "sim_spec.json",
        "assets_manifest.json",
        "compiled_sim.json",
        "scene_manifest.json",
        "trajectory.json",
        "metrics.json",
        "replay.json",
        "run_summary.json",
    }

    produced = {p.name for p in artifacts.root.iterdir() if p.is_file()}
    assert expected.issubset(produced)

    compiled = json.loads((artifacts.root / "compiled_sim.json").read_text())
    assert compiled["physics"]["objects"][0]["body"] == "dynamic"
    assert compiled["event_graph"][0]["type"] == "spawn"

    metrics = json.loads((artifacts.root / "metrics.json").read_text())
    assert metrics["backend"] == "genesis_isaac"
    assert metrics["frames"] == 12
