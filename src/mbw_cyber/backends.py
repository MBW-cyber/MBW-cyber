from __future__ import annotations

from abc import ABC, abstractmethod
from random import Random
from typing import Any

from .models import BackendConfig


class SimulationBackend(ABC):
    @abstractmethod
    def run(self, compiled_sim: dict[str, Any], config: BackendConfig) -> dict[str, Any]:
        raise NotImplementedError


class WebRapierBackend(SimulationBackend):
    """Lightweight runtime profile aligned with a browser + Rapier loop."""

    def run(self, compiled_sim: dict[str, Any], config: BackendConfig) -> dict[str, Any]:
        rng = Random(compiled_sim["seed"])
        frames = config.duration_s * config.hz
        return {
            "backend": "web_rapier",
            "frames": _build_agent_frames(compiled_sim, frames, config.hz, rng, jitter=0.02),
        }


class GenesisIsaacBackend(SimulationBackend):
    """Heavier runtime profile with slightly lower noise and longer horizon."""

    def run(self, compiled_sim: dict[str, Any], config: BackendConfig) -> dict[str, Any]:
        rng = Random(compiled_sim["seed"] ^ 0xABCDEF)
        frames = config.duration_s * config.hz
        return {
            "backend": "genesis_isaac",
            "frames": _build_agent_frames(compiled_sim, frames, config.hz, rng, jitter=0.01),
        }


def _build_agent_frames(
    compiled_sim: dict[str, Any],
    frames: int,
    hz: int,
    rng: Random,
    jitter: float,
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for f in range(frames):
        timeline.append(
            {
                "frame": f,
                "time": f / hz,
                "agent_states": [
                    {
                        "id": agent.get("id", "agent"),
                        "goal": agent.get("goal", "unspecified"),
                        "progress": round(min(1.0, (f + 1) / frames + rng.random() * jitter), 4),
                    }
                    for agent in compiled_sim.get("agents", [])
                ],
            }
        )
    return timeline


def resolve_backend(name: str) -> SimulationBackend:
    normalized = name.strip().lower().replace("-", "_")
    if normalized in {"web", "web_rapier", "rapier"}:
        return WebRapierBackend()
    if normalized in {"genesis", "isaac", "genesis_isaac"}:
        return GenesisIsaacBackend()
    raise ValueError(f"Unsupported backend '{name}'. Use web_rapier or genesis_isaac.")
