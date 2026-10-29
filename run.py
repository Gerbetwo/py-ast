#!/usr/bin/env python3
"""Cross-platform launcher for py-ast.

Detects the presence of the `uv` package manager (`shutil.which('uv')`).
If available, synchronizes dependencies via `uv sync --all-extras --dev` and runs
the application using `uv run python -m py_ast.main`.
Otherwise, checks for a virtual environment (or creates a local `.venv` if missing),
installs dependencies via `pip install -e .`, and runs the application.
Command-line arguments (such as `--web-only`, `--host`, and `--port`) are forwarded.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"


def get_venv_python() -> Path:
    """Get the path to the Python executable inside the .venv directory."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def main(argv: list[str] | None = None) -> int:
    """Synchronize environment dependencies and launch py-ast."""
    if argv is None:
        argv = sys.argv[1:]

    has_uv = bool(shutil.which("uv"))

    if has_uv:
        print(">> Detected 'uv' package manager.")
        print(">> Synchronizing dependencies: uv sync --all-extras --dev")
        sync_cmd = ["uv", "sync", "--all-extras", "--dev"]
        run_cmd = ["uv", "run", "python", "-m", "py_ast.main", *argv]
    else:
        print(">> 'uv' package manager not found.")

        # Check if an external virtual environment is active or if .venv exists locally
        is_venv_active = (
            hasattr(sys, "real_prefix")
            or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
            or "VIRTUAL_ENV" in os.environ
        )

        venv_python = get_venv_python()

        # If no environment is active and .venv doesn't exist yet, create it automatically
        if not is_venv_active and not venv_python.exists():
            print(f">> No virtual environment detected. Automatically creating one at: {VENV_DIR}")
            creation_res = subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                check=False,
                cwd=PROJECT_ROOT,
            )
            if creation_res.returncode != 0:
                print(
                    f">> Error: Failed to create virtual environment (exit code {creation_res.returncode}).",
                    file=sys.stderr,
                )
                return creation_res.returncode
            print(">> Virtual environment created successfully.")

        # Choose the correct python executable
        if is_venv_active:
            python_bin = sys.executable
        else:
            python_bin = str(venv_python)

        print(f">> Using Python interpreter: {python_bin}")
        print(">> Installing dependencies: pip install -e .")
        sync_cmd = [python_bin, "-m", "pip", "install", "-e", "."]
        run_cmd = [python_bin, "-m", "py_ast.main", *argv]

    try:
        sync_res = subprocess.run(sync_cmd, check=False, cwd=PROJECT_ROOT)
        if sync_res.returncode != 0:
            print(
                f">> Error: Dependency synchronization failed (exit code {sync_res.returncode}).",
                file=sys.stderr,
            )
            return sync_res.returncode

        run_res = subprocess.run(run_cmd, check=False, cwd=PROJECT_ROOT)
        return run_res.returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())