from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

from mbw_cyber.api import create_server


def _request_json(conn: HTTPConnection, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload or {}).encode("utf-8")
    conn.request(method, path, body=body, headers={"Content-Type": "application/json"})
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

    status, scene = _request_json(conn, "POST", "/scene/generate", payload)
    assert status == 200
    assert "scene_spec" in scene

    status, assets = _request_json(conn, "POST", "/assets/generate", payload)
    assert status == 200
    assert assets["assets"]

    first_asset_file = Path(assets["assets"][0]["path"])  # .../<id>.asset.json
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

    status, run_info = _request_json(conn, "GET", f"/runs/{run_id}")
    assert status == 200
    assert run_info["metrics"]["requested_metrics"]["collisions"] >= 0

    status, asset = _request_json(conn, "GET", f"/assets/{asset_id}")
    assert status == 200
    assert asset["asset"]["class"] == "forklift"

    conn.close()
    server.shutdown()
    thread.join(timeout=2)
