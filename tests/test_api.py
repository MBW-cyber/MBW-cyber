from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

from mbw_cyber.api import create_server


def _request_json(conn: HTTPConnection, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    conn.request(method, path, body=body, headers=headers)
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    return response.status, data


def test_api_endpoints_roundtrip(tmp_path: Path) -> None:
    server = create_server(host="127.0.0.1", port=0, state_root=str(tmp_path / "api_state"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    conn = HTTPConnection(host, port)

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
        "events": [{"t": 5, "type": "spawn", "target": "forklift_2"}],
        "metrics": ["collisions", "task_completion", "travel_time"],
    }

    status, health = _request_json(conn, "GET", "/health")
    assert status == 200
    assert health["ok"] is True

    status, scene = _request_json(conn, "POST", "/scene/generate", payload)
    assert status == 200
    assert "scene" in scene
    assert "sim" in scene

    status, validation = _request_json(conn, "POST", "/scene/validate", payload)
    assert status == 200
    assert validation["valid"] is True

    status, compiled = _request_json(conn, "POST", "/scene/compile", {"scene": scene["scene"], "sim": scene["sim"]})
    assert status == 200
    assert compiled["compiled_sim"]["seed"] == scene["sim"]["seed"]

    status, assets = _request_json(conn, "POST", "/assets/generate", payload)
    assert status == 200
    assert assets["assets"]

    first_asset_file = Path(assets["assets"][0]["path"])
    asset_id = first_asset_file.stem.replace(".asset", "")

    status, assembled = _request_json(conn, "POST", "/scene/assemble", payload)
    assert status == 200
    assert "scene" in assembled

    status, run_resp = _request_json(conn, "POST", "/sim/run", payload)
    assert status == 200
    run_id = run_resp["run_id"]

    status, replay = _request_json(conn, "POST", "/sim/replay", {"run_id": run_id})
    assert status == 200
    assert "trajectory" in replay

    status, runs = _request_json(conn, "GET", "/runs")
    assert status == 200
    assert any(r["run_id"] == run_id for r in runs["runs"])

    status, run_info = _request_json(conn, "GET", f"/runs/{run_id}")
    assert status == 200
    assert run_info["metrics"]["requested_metrics"]["collisions"] >= 0

    status, asset = _request_json(conn, "GET", f"/assets/{asset_id}")
    assert status == 200
    assert asset["asset"]["class"] == "forklift"

    conn.close()
    server.shutdown()
    thread.join(timeout=2)


def test_experiment_run_endpoint(tmp_path: Path) -> None:
    server = create_server(host="127.0.0.1", port=0, state_root=str(tmp_path / "api_state"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    conn = HTTPConnection(host, port)

    payload = {
        "base": {
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
        },
        "experiment": {
            "seed": 18442,
            "variations": {"num_workers": [2, 5], "forklift_speed": [1.0, 2.4]},
            "metrics": ["collisions", "task_completion"],
        },
        "duration": 2,
        "hz": 2,
    }

    status, resp = _request_json(conn, "POST", "/experiment/run", payload)
    assert status == 200
    assert len(resp["matrix"]) == 4
    assert all("collisions" in row["metrics"] for row in resp["matrix"])
    assert len({row["seed"] for row in resp["matrix"]}) == 4

    conn.close()
    server.shutdown()
    thread.join(timeout=2)
