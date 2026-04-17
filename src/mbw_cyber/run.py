from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Text-to-3D + generative simulation MVP pipeline")
    parser.add_argument("--input", required=True, help="Path to input prompt payload JSON")
    parser.add_argument("--out", default="runs", help="Output root directory")
    args = parser.parse_args()

    payload_path = Path(args.input)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    artifacts = run_pipeline(payload, Path(args.out))
    print(f"Run complete: {artifacts.run_id}")
    print(f"Output: {artifacts.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
