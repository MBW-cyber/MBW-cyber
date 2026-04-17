from __future__ import annotations

import json
from pathlib import Path

from mbw_cyber.pipeline import run_experiment_matrix, run_pipeline


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

    artifacts = run_pipeline(
        payload,
        tmp_path,
        backend="genesis_isaac",
        duration_s=3,
        hz=4,
        requested_metrics=["collisions", "task_completion", "travel_time"],
    )

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
    assert set(metrics["requested_metrics"].keys()) == {"collisions", "task_completion", "travel_time"}


def test_experiment_matrix_runs_all_variations(tmp_path: Path) -> None:
    base_payload = {
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
    }
    experiment_payload = {
        "seed": 18442,
        "variations": {
            "num_workers": [2, 5],
            "spawn_interval_sec": [10, 45],
            "forklift_speed": [1.0, 2.4],
        },
        "metrics": ["collisions", "task_completion", "travel_time"],
    }

    matrix = run_experiment_matrix(base_payload, experiment_payload, tmp_path, duration_s=2, hz=2)
    assert len(matrix) == 8
    assert (tmp_path / "experiment_matrix.json").exists()
    assert all("collisions" in row["metrics"] for row in matrix)
