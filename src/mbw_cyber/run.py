from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Text-to-3D + generative simulation pipeline")
    parser.add_argument("--input", required=True, help="Path to input JSON prompt payload")
    parser.add_argument("--out", default="runs", help="Output root directory")
    parser.add_argument("--backend", default="web_rapier", choices=["web_rapier", "genesis_isaac"])
    parser.add_argument("--duration", type=int, default=12, help="Simulation duration in seconds")
    parser.add_argument("--hz", type=int, default=10, help="Simulation tick rate")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    artifacts = run_pipeline(
        payload,
        Path(args.out),
        backend=args.backend,
        duration_s=args.duration,
        hz=args.hz,
    )

    print(f"Run complete: {artifacts.run_id}")
    print(f"Output: {artifacts.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
