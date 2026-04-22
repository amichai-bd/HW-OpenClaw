#!/usr/bin/env python3
"""Windows + Git Bash bootstrap: PyYAML check and optional EDA tool verification."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_CONFIG = REPO_ROOT / "cfg" / "env.yaml"


class SetupError(RuntimeError):
    """Raised when repository setup fails."""


def ensure_yaml_module() -> None:
    try:
        import yaml  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SetupError(
            "PyYAML is required. Install with: pip install pyyaml"
        ) from exc


def load_env() -> dict:
    ensure_yaml_module()
    import yaml

    if not ENV_CONFIG.is_file():
        raise SetupError(f"missing {ENV_CONFIG}")
    data = yaml.safe_load(ENV_CONFIG.read_text(encoding="utf-8"))
    env = data.get("environment")
    if not isinstance(env, dict):
        raise SetupError("missing environment mapping in cfg/env.yaml")
    return env


def capture_cmd(argv: list[str]) -> str:
    result = subprocess.run(argv, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or "command failed"
        raise SetupError(f"{' '.join(argv)}: {detail}")
    return (result.stdout or result.stderr).strip()


def verify_tools(strict: bool) -> None:
    import yaml

    data = yaml.safe_load(ENV_CONFIG.read_text(encoding="utf-8"))
    tools = data["environment"]["tools"]
    print("tool verification (cfg/env.yaml):", flush=True)
    for name, cfg in tools.items():
        if not isinstance(cfg, dict):
            continue
        exe = cfg.get("exe")
        if not isinstance(exe, str) or not exe.strip():
            continue
        # PATH-based tools may not be Path().is_file() — use shutil.which for bare names
        resolved = Path(exe).expanduser()
        on_path = shutil.which(exe) if not resolved.is_file() else str(resolved)
        if not on_path and not resolved.is_file():
            raise SetupError(f"{name}: executable not found: {exe}")
        if strict and cfg.get("version_cmd"):
            cmd = str(cfg["version_cmd"]).split()
            try:
                ver = capture_cmd(cmd)
            except SetupError as err:
                raise SetupError(f"{name}: {err}") from err
            print(f"- {name}: {ver}", flush=True)
        else:
            print(f"- {name}: {exe}", flush=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HW-OpenClaw setup (Windows)")
    p.add_argument("--check", action="store_true", help="verify tools from cfg/env.yaml")
    p.add_argument("--ci", action="store_true", help="skip strict version probes")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
        load_env()
        if args.check:
            verify_tools(strict=not args.ci)
            return 0
        print("HW-OpenClaw setup:", flush=True)
        print("- Install Intel Quartus + Questa/ModelSim for Windows; add to PATH.", flush=True)
        print("- pip install pyyaml", flush=True)
        print("- . cfg/env.sh && ./build -h", flush=True)
        return 0
    except SetupError as err:
        print(f"setup failed: {err}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
