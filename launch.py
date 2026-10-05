"""Install an isolated local runtime from this checkout and start the personal planner."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path


def main() -> int:
    """Keep application dependencies in its own directory and expose an explicit no-browser test mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        print("Please install Python 3.12 from python.org, then start DayWeave again.")
        return 2
    root = Path(__file__).resolve().parent
    environment = root / ".venv"
    binary = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not binary.exists():
        print("Preparing DayWeave's local environment…", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    executable = environment / ("Scripts/dayweave.exe" if os.name == "nt" else "bin/dayweave")
    if not executable.exists():
        print("Installing the planner. The first start needs internet for Python packages…", flush=True)
        subprocess.run([str(binary), "-m", "pip", "install", "--disable-pip-version-check", str(root)], check=True)
    print(f"DayWeave: http://127.0.0.1:{args.port} · keep this window open · Ctrl+C to stop", flush=True)
    command = [str(executable), "serve", "--port", str(args.port)]
    if not args.no_browser:
        command.append("--open")
    try:
        return subprocess.call(command, cwd=root)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
