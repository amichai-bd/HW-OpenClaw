#!/usr/bin/env python3
"""Repository bootstrap and tool verification."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_CONFIG = REPO_ROOT / "cfg" / "env.yaml"


class SetupError(RuntimeError):
    """Raised when repository setup fails."""


def ensure_yaml_module() -> None:
    try:
        import yaml  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    if shutil.which("apt-get") is None:
        raise SetupError("missing python yaml support and apt-get is not available to install python3-yaml")

    run_cmd(["sudo", "apt-get", "update"])
    run_cmd(["sudo", "apt-get", "install", "-y", "python3-yaml"])

    os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]])


def load_env_config() -> dict:
    ensure_yaml_module()
    import yaml

    if not ENV_CONFIG.is_file():
        raise SetupError(f"missing env config: {ENV_CONFIG}")
    data = yaml.safe_load(ENV_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SetupError(f"expected mapping in {ENV_CONFIG}")
    environment = data.get("environment")
    if not isinstance(environment, dict):
        raise SetupError(f"missing 'environment' mapping in {ENV_CONFIG}")
    return environment


def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd, text=True, env=env)
    if result.returncode != 0:
        raise SetupError(f"command failed with exit code {result.returncode}: {' '.join(cmd)}")


def capture_cmd(cmd: list[str]) -> str:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or "command failed"
        raise SetupError(f"{' '.join(cmd)}: {detail}")
    return (result.stdout or result.stderr).strip()


def require_mapping(mapping: dict, key: str, context: str) -> dict:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise SetupError(f"missing mapping '{key}' in {context}")
    return value


def require_list(mapping: dict, key: str, context: str) -> list:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise SetupError(f"missing list '{key}' in {context}")
    return value


def format_template(text: str, context: dict) -> str:
    return text.format(**context)


def get_bootstrap_data(environment: dict) -> dict:
    bootstrap = require_mapping(environment, "bootstrap", "environment")
    apt_packages = require_list(bootstrap, "apt_packages", "environment.bootstrap")
    user_installs = require_mapping(bootstrap, "user_installs", "environment.bootstrap")
    sby_cfg = require_mapping(user_installs, "sby", "environment.bootstrap.user_installs")

    context = {
        "repo_root": str(REPO_ROOT),
        "host_home": os.environ.get("HOME", str(Path.home())),
    }
    install_prefix = format_template(str(sby_cfg["install_prefix"]), context)

    return {
        "platform": bootstrap.get("platform", ""),
        "apt_packages": [str(item) for item in apt_packages],
        "sby_repo": str(sby_cfg["repo"]),
        "sby_ref": str(sby_cfg.get("ref", "master")),
        "sby_install_prefix": install_prefix,
    }


def get_tools(environment: dict) -> dict:
    tools = require_mapping(environment, "tools", "environment")
    resolved = {}
    context = {
        "repo_root": str(REPO_ROOT),
        "host_home": os.environ.get("HOME", str(Path.home())),
        "home_dir": os.environ.get("HOME", str(Path.home())),
    }
    for tool_name, tool_cfg in tools.items():
        if not isinstance(tool_cfg, dict):
            raise SetupError(f"environment.tools.{tool_name} must be a mapping")
        resolved_tool = {}
        for key, value in tool_cfg.items():
            if isinstance(value, str):
                resolved_tool[key] = format_template(value, context)
            else:
                resolved_tool[key] = value
        resolved[tool_name] = resolved_tool
    return resolved


def check_platform(bootstrap: dict) -> None:
    platform_name = bootstrap["platform"]
    if platform_name != "debian-ubuntu":
        raise SetupError(f"unsupported bootstrap platform '{platform_name}'")
    if shutil.which("apt-get") is None:
        raise SetupError("this setup flow expects apt-get on Debian/Ubuntu")


def install_apt_packages(bootstrap: dict) -> None:
    apt_env = dict(os.environ)
    apt_env["DEBIAN_FRONTEND"] = "noninteractive"
    run_cmd(["sudo", "apt-get", "update"], env=apt_env)
    run_cmd(["sudo", "apt-get", "install", "-y", *bootstrap["apt_packages"]], env=apt_env)


def install_sby(bootstrap: dict) -> None:
    install_prefix = Path(bootstrap["sby_install_prefix"]).expanduser()
    target_exe = install_prefix / "bin" / "sby"
    if target_exe.is_file():
        return

    with tempfile.TemporaryDirectory(prefix="hw-openclaw-sby-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        clone_dir = tmp_path / "sby"
        run_cmd(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                bootstrap["sby_ref"],
                bootstrap["sby_repo"],
                str(clone_dir),
            ]
        )
        install_prefix.mkdir(parents=True, exist_ok=True)
        run_cmd(["make", "install", f"PREFIX={install_prefix}"], cwd=clone_dir)


def verify_tools(environment: dict, strict: bool = True) -> None:
    tools = get_tools(environment)
    print("tool verification:", flush=True)
    for tool_name in ["python3", "verilator", "gtkwave", "yosys", "sby", "boolector", "z3"]:
        tool_cfg = tools.get(tool_name)
        if not isinstance(tool_cfg, dict):
            raise SetupError(f"missing tool config for '{tool_name}'")
        exe = str(tool_cfg["exe"])
        if not Path(exe).expanduser().is_file():
            raise SetupError(f"missing executable for {tool_name}: {exe}")
        if strict:
            version_cmd = str(tool_cfg["version_cmd"]).split()
            version_text = capture_cmd(version_cmd)
            print(f"- {tool_name}: {version_text}", flush=True)
        else:
            print(f"- {tool_name}: {exe}", flush=True)


def print_plan(environment: dict) -> None:
    bootstrap = get_bootstrap_data(environment)
    print("repository setup plan:", flush=True)
    print(f"- platform: {bootstrap['platform']}", flush=True)
    print("- apt packages:", flush=True)
    for package in bootstrap["apt_packages"]:
        print(f"  - {package}", flush=True)
    print(f"- user install: sby from {bootstrap['sby_repo']} -> {bootstrap['sby_install_prefix']}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repository setup/bootstrap")
    parser.add_argument("--check", action="store_true", help="verify installed tools only")
    parser.add_argument("--print-plan", action="store_true", help="print the setup plan and exit")
    parser.add_argument("--ci", action="store_true", help="non-interactive CI mode")
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        environment = load_env_config()

        if args.print_plan:
            print_plan(environment)
            return 0

        if args.check:
            verify_tools(environment)
            return 0

        bootstrap = get_bootstrap_data(environment)
        check_platform(bootstrap)
        install_apt_packages(bootstrap)
        install_sby(bootstrap)
        verify_tools(environment, strict=not args.ci)
        if not args.ci:
            print("", flush=True)
            print("next step:", flush=True)
            print("- source the repository environment with `. cfg/env.sh`", flush=True)
            print("- run the builder through `./build`", flush=True)
        return 0
    except SetupError as error:
        print(f"setup failed: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
