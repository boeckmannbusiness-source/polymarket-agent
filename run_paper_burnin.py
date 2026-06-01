#!/usr/bin/env python3
"""
Root-level entry point for Paper Burn-In Short Test.

Usage:
    python run_paper_burnin.py [--duration 15] [--extended] [--port 8000]

Prepares environment and delegates to backend/scripts/paper_burnin_short.py.
"""
import os
import sys
import subprocess
from pathlib import Path


def main():
    backend_dir = Path(__file__).resolve().parent / "backend"
    script = backend_dir / "scripts" / "paper_burnin_short.py"

    if not script.exists():
        print(f"ERROR: {script} not found", file=sys.stderr)
        sys.exit(1)

    # Pass all arguments through
    cmd = [sys.executable, str(script)] + sys.argv[1:]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_dir) + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.Popen(cmd, cwd=backend_dir, env=env)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
