from __future__ import annotations

import argparse

from .api import run_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MBW API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--state-root", default=".mbw_api")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, state_root=args.state_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
