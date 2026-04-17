from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class SceneSpec:
    environment: dict[str, Any]
    objects: list[dict[str, Any]]


@dataclass
class SimSpec:
    agents: list[dict[str, Any]]
    events: list[dict[str, Any]]
    seed: int


@dataclass
class AssetRecord:
    id: str
    klass: str
    source: str
    path: str
    collider: str = "convex_hull"
    lod: str = "auto"


@dataclass
class RunArtifacts:
    run_id: str
    root: Path
    files: dict[str, Path] = field(default_factory=dict)

    def add(self, name: str, path: Path) -> None:
        self.files[name] = path

    def to_json(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "root": str(self.root),
            "files": {k: str(v) for k, v in self.files.items()},
        }


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)
