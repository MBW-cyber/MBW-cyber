from __future__ import annotations

import hashlib
import itertools
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass
class ExperimentSpec:
    seed: int
    variations: dict[str, list[float | int]]
    metrics: list[str]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ExperimentSpec":
        return cls(
            seed=int(payload.get("seed", 0)),
            variations=dict(payload.get("variations", {})),
            metrics=list(payload.get("metrics", [])),
        )


def variation_cases(spec: ExperimentSpec) -> list[dict[str, float | int]]:
    keys = sorted(spec.variations.keys())
    options: list[list[float | int]] = []
    for key in keys:
        raw = spec.variations[key]
        if len(raw) == 2:
            options.append([raw[0], raw[1]])
        elif raw:
            options.append(raw)
        else:
            options.append([0])

    cases: list[dict[str, float | int]] = []
    for values in itertools.product(*options):
        cases.append({k: v for k, v in zip(keys, values)})
    return cases


def apply_case(base_payload: dict[str, Any], case: dict[str, float | int], case_seed: int) -> dict[str, Any]:
    payload = deepcopy(base_payload)

    num_workers = int(case.get("num_workers", len(payload.get("agents", [])) or 1))
    template = (payload.get("agents") or [{"id": "worker_1", "goal": "move pallets to loading zone", "policy": "llm_planner"}])[0]
    payload["agents"] = [
        {
            **template,
            "id": f"worker_{i+1}",
        }
        for i in range(num_workers)
    ]

    spawn_interval = int(case.get("spawn_interval_sec", 20))
    payload["events"] = [
        {"t": spawn_interval, "type": "spawn", "target": "forklift_2"},
        {"t": spawn_interval * 2, "type": "spawn", "target": "forklift_3"},
    ]

    forklift_speed = float(case.get("forklift_speed", 1.5))
    for obj in payload.get("objects", []):
        if obj.get("class") == "forklift":
            obj.setdefault("physics", {})["speed_limit"] = forklift_speed

    payload["seed"] = case_seed
    payload["variation_case"] = case
    return payload


def seeded_case(spec_seed: int, case: dict[str, float | int]) -> int:
    raw = json.dumps(case, sort_keys=True)
    digest = hashlib.sha256(f"{spec_seed}:{raw}".encode()).hexdigest()[:8]
    return int(digest, 16)
