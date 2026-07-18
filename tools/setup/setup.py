#!/usr/bin/env python3
"""Repository bootstrap and tool verification."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
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


def resolve_templates(value, context: dict):
    if isinstance(value, dict):
        return {key: resolve_templates(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_templates(item, context) for item in value]
    if isinstance(value, str):
        return format_template(value, context)
    return value


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
        "manual_tools": bootstrap.get("manual_tools", {}),
    }


def get_orfs_data(environment: dict) -> dict:
    bootstrap = require_mapping(environment, "bootstrap", "environment")
    user_installs = require_mapping(bootstrap, "user_installs", "environment.bootstrap")
    orfs_cfg = require_mapping(user_installs, "orfs", "environment.bootstrap.user_installs")
    crane_cfg = require_mapping(orfs_cfg, "crane", "environment.bootstrap.user_installs.orfs")
    context = {
        "repo_root": str(REPO_ROOT),
        "host_home": os.environ.get("HOME", str(Path.home())),
    }
    resolved = resolve_templates(orfs_cfg, context)
    resolved["crane"] = resolve_templates(crane_cfg, context)
    for key in ["image", "image_digest", "platform", "install_root", "runner"]:
        if not isinstance(resolved.get(key), str) or not resolved[key].strip():
            raise SetupError(f"missing string '{key}' in environment.bootstrap.user_installs.orfs")
    for key in ["version", "exe", "archive_url", "archive_sha256"]:
        if not isinstance(resolved["crane"].get(key), str) or not resolved["crane"][key].strip():
            raise SetupError(f"missing string '{key}' in environment.bootstrap.user_installs.orfs.crane")
    return resolved


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_crane(orfs: dict) -> Path:
    crane = orfs["crane"]
    target = Path(crane["exe"]).expanduser()
    expected_version = crane["version"].removeprefix("v")
    if target.is_file():
        version = capture_cmd([str(target), "version"])
        if version == expected_version:
            return target

    with tempfile.TemporaryDirectory(prefix="hw-openclaw-crane-") as tmp_dir:
        archive_path = Path(tmp_dir) / "crane.tar.gz"
        urllib.request.urlretrieve(crane["archive_url"], archive_path)
        actual_sha256 = sha256_file(archive_path)
        if actual_sha256 != crane["archive_sha256"]:
            raise SetupError(
                f"crane archive checksum mismatch: expected {crane['archive_sha256']}, got {actual_sha256}"
            )
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.getmember("crane")
            source = archive.extractfile(member)
            if source is None:
                raise SetupError("crane archive does not contain an extractable 'crane' binary")
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = Path(tmp_dir) / "crane"
            staged.write_bytes(source.read())
            staged.chmod(0o755)
            os.replace(staged, target)
    version = capture_cmd([str(target), "version"])
    if version != expected_version:
        raise SetupError(f"unexpected crane version after install: expected {expected_version}, got {version}")
    return target


def install_orfs(environment: dict) -> None:
    orfs = get_orfs_data(environment)
    runner = Path(orfs["runner"])
    if not runner.is_file():
        raise SetupError(
            f"missing bubblewrap runner {runner}; install the YAML-declared 'bubblewrap' apt package first"
        )
    install_root = Path(orfs["install_root"]).expanduser()
    rootfs = install_root / "rootfs"
    marker = install_root / "image-digest.txt"
    openroad = rootfs / "OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"
    if openroad.is_file():
        marker.write_text(orfs["image_digest"] + "\n", encoding="utf-8")
        return

    crane = install_crane(orfs)
    partial_rootfs = install_root / "rootfs.partial"
    if partial_rootfs.exists():
        shutil.rmtree(partial_rootfs)
    partial_rootfs.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [str(crane), "export", "--platform", orfs["platform"], orfs["image"], "-"],
        stdout=subprocess.PIPE,
    )
    if process.stdout is None:
        raise SetupError("failed to capture crane export stream")
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|*") as archive:
            archive.extractall(partial_rootfs, filter="fully_trusted")
    finally:
        process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        raise SetupError(f"crane export failed with exit code {return_code}")
    if rootfs.exists():
        shutil.rmtree(rootfs)
    partial_rootfs.rename(rootfs)
    marker.write_text(orfs["image_digest"] + "\n", encoding="utf-8")


def orfs_command(orfs: dict, script: str) -> list[str]:
    rootfs = Path(orfs["install_root"]).expanduser() / "rootfs"
    return [
        orfs["runner"],
        "--ro-bind",
        str(rootfs),
        "/",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--tmpfs",
        "/tmp",
        "--chdir",
        "/OpenROAD-flow-scripts",
        "--setenv",
        "HOME",
        "/tmp",
        "--setenv",
        "USER",
        os.environ.get("USER", "user"),
        "/usr/bin/bash",
        "-lc",
        script,
    ]


def verify_orfs(environment: dict) -> None:
    orfs = get_orfs_data(environment)
    install_root = Path(orfs["install_root"]).expanduser()
    rootfs = install_root / "rootfs"
    marker = install_root / "image-digest.txt"
    actual_digest = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    if actual_digest != orfs["image_digest"]:
        raise SetupError(
            "ORFS image digest marker is missing or stale; run ./setup --pd to install the pinned image"
        )
    required = [
        rootfs / "OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad",
        rootfs / "OpenROAD-flow-scripts/tools/install/yosys/bin/yosys",
        rootfs / "usr/bin/klayout",
    ]
    for path in required:
        if not path.is_file():
            raise SetupError(f"missing ORFS tool: {path}; run ./setup --pd")
    output = capture_cmd(
        orfs_command(
            orfs,
            "source ./env.sh && openroad -version && yosys -V && klayout -v",
        )
    )
    print("physical-design tool verification:", flush=True)
    print(f"- image: {orfs['image']}", flush=True)
    for line in output.splitlines():
        print(f"- {line}", flush=True)


def verify_tools(environment: dict, strict: bool = True) -> None:
    tools = get_tools(environment)
    print("tool verification:", flush=True)
    for tool_name in ["python3", "verilator", "gtkwave", "dot", "yosys", "sby", "boolector", "z3"]:
        tool_cfg = tools.get(tool_name)
        if not isinstance(tool_cfg, dict):
            raise SetupError(f"missing tool config for '{tool_name}'")
        exe_value = tool_cfg.get("exe")
        if not isinstance(exe_value, str) or not exe_value.strip():
            raise SetupError(f"missing string 'exe' in environment.tools.{tool_name}")
        exe = exe_value
        if not Path(exe).expanduser().is_file():
            raise SetupError(f"missing executable for {tool_name}: {exe}")
        if strict:
            version_cmd_text = tool_cfg.get("version_cmd")
            if not isinstance(version_cmd_text, str) or not version_cmd_text.strip():
                raise SetupError(f"missing string 'version_cmd' in environment.tools.{tool_name}")
            version_cmd = version_cmd_text.split()
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
    manual_tools = bootstrap["manual_tools"]
    if manual_tools:
        print("- manual/containerized tools:", flush=True)
        for tool_name, tool_cfg in manual_tools.items():
            reason = tool_cfg.get("reason", "") if isinstance(tool_cfg, dict) else ""
            print(f"  - {tool_name}: {reason}", flush=True)


def print_pd_plan(environment: dict) -> None:
    orfs = get_orfs_data(environment)
    print("physical-design setup plan:", flush=True)
    print(f"- pinned image: {orfs['image']}", flush=True)
    print(f"- platform: {orfs['platform']}", flush=True)
    print(f"- user-local root: {orfs['install_root']}", flush=True)
    print(f"- sandbox runner: {orfs['runner']}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repository setup/bootstrap")
    parser.add_argument("--check", action="store_true", help="verify installed tools only")
    parser.add_argument("--print-plan", action="store_true", help="print the setup plan and exit")
    parser.add_argument("--ci", action="store_true", help="non-interactive CI mode")
    parser.add_argument(
        "--pd",
        action="store_true",
        help="install or check the optional pinned ORFS physical-design tier only",
    )
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        environment = load_env_config()

        if args.print_plan:
            if args.pd:
                print_pd_plan(environment)
            else:
                print_plan(environment)
            return 0

        if args.check:
            if args.pd:
                verify_orfs(environment)
            else:
                verify_tools(environment)
            return 0

        if args.pd:
            install_orfs(environment)
            verify_orfs(environment)
            print("", flush=True)
            print("next step:", flush=True)
            print("- run `./build -ip counter -pd -pd-exec`", flush=True)
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
