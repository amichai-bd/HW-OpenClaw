#!/usr/bin/env python3
"""Minimal YAML-driven builder."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_CONFIG = REPO_ROOT / "tools" / "build" / "build.yaml"
IP_CONFIG = REPO_ROOT / "cfg" / "ip.yaml"


class BuildError(RuntimeError):
    """Raised when build setup or execution fails."""


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise BuildError(f"missing yaml file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        raise BuildError(f"empty yaml file: {path}")
    if not isinstance(data, dict):
        raise BuildError(f"expected mapping in {path}")
    return data


def require_keys(data: dict, required_keys: list[str], context: str) -> None:
    for key in required_keys:
        if key not in data:
            raise BuildError(f"missing '{key}' in {context}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run project build steps")
    parser.add_argument("-ip", required=True, help="IP name to build")
    parser.add_argument("-tag", help="run tag for the output directory")
    parser.add_argument("-compile", action="store_true", help="run compile step")
    parser.add_argument("-test", help="run a named test")
    parser.add_argument("-regress", help="run a named regression")
    args = parser.parse_args()

    requested_modes = sum(
        [1 if args.compile else 0, 1 if args.test else 0, 1 if args.regress else 0]
    )
    if requested_modes != 1:
        raise BuildError("select exactly one of -compile, -test, or -regress")
    return args


def resolve_path(path_text: str) -> str:
    return str((REPO_ROOT / path_text).resolve())


def resolve_tag(requested_tag: str | None, ip_data: dict) -> str:
    workdir = REPO_ROOT / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)

    if requested_tag:
        return requested_tag

    prefix = datetime.now().strftime("%Y_%m_%d_%H%M")
    iteration = 0
    while (workdir / f"{prefix}_{iteration}").exists():
        iteration += 1
    return f"{prefix}_{iteration}"


def get_ip_data(ip_name: str) -> dict:
    ip_root = load_yaml(IP_CONFIG)
    require_keys(ip_root, ["model_root_var", "output_layout", "ip"], str(IP_CONFIG))
    if not isinstance(ip_root["model_root_var"], str):
        raise BuildError(f"'model_root_var' must be a string in {IP_CONFIG}")
    output_layout = ip_root["output_layout"]
    if not isinstance(output_layout, dict):
        raise BuildError(f"'output_layout' must be a mapping in {IP_CONFIG}")
    require_keys(
        output_layout,
        [
            "tag_root",
            "ip_root",
            "filelist_dir",
            "generated_rtl_filelist",
            "generated_dv_filelist",
            "generated_all_filelist",
            "compile_dir",
            "compile_log",
            "binary_path",
            "test_out_dir",
            "test_log",
            "test_tracker",
            "regression_test_out_dir",
            "regression_test_log",
            "regression_test_tracker",
        ],
        "output_layout",
    )
    ip_cfg = ip_root["ip"]
    if not isinstance(ip_cfg, dict):
        raise BuildError(f"'ip' must be a mapping in {IP_CONFIG}")
    if ip_name not in ip_cfg:
        raise BuildError(f"unknown ip '{ip_name}'")

    ip_data = dict(ip_cfg[ip_name])
    require_keys(
        ip_data,
        [
            "rtl_filelist",
            "dv_filelist",
            "all_filelist",
            "rtl_top",
            "dv_top",
            "tb_top_module",
            "sim_binary",
            "regression_dir",
            "test_dir",
        ],
        f"ip.{ip_name}",
    )
    ip_data["ip"] = ip_name
    ip_data["model_root_var"] = ip_root["model_root_var"]
    ip_data["output_layout"] = dict(output_layout)
    ip_data["repo_root"] = str(REPO_ROOT)
    ip_data["top_module"] = ip_data["tb_top_module"]
    ip_data["binary_name"] = ip_data["sim_binary"]
    ip_data["test_name"] = ""
    ip_data["regress_name"] = ""
    return ip_data


def apply_template(value: str, context: dict) -> str:
    return value.format(**context)


def apply_run_paths(ip_data: dict, tag: str) -> dict:
    layout = ip_data["output_layout"]
    ip_data["tag"] = tag
    ip_data["tag_root"] = resolve_path(apply_template(layout["tag_root"], ip_data))
    ip_data["ip_root"] = resolve_path(apply_template(layout["ip_root"], ip_data))
    ip_data["filelist_dir"] = resolve_path(apply_template(layout["filelist_dir"], ip_data))
    ip_data["generated_rtl_filelist"] = resolve_path(
        apply_template(layout["generated_rtl_filelist"], ip_data)
    )
    ip_data["generated_dv_filelist"] = resolve_path(
        apply_template(layout["generated_dv_filelist"], ip_data)
    )
    ip_data["generated_all_filelist"] = resolve_path(
        apply_template(layout["generated_all_filelist"], ip_data)
    )
    ip_data["compile_dir"] = resolve_path(apply_template(layout["compile_dir"], ip_data))
    ip_data["binary_path"] = resolve_path(apply_template(layout["binary_path"], ip_data))
    ip_data["run_dir"] = ip_data["compile_dir"]
    ip_data["log_file"] = resolve_path(apply_template(layout["compile_log"], ip_data))
    ip_data["tracker_path"] = ""
    return ip_data


def get_test_data(ip_data: dict, test_name: str, mode: str) -> dict:
    test_file = REPO_ROOT / ip_data["test_dir"] / f"{test_name}.yaml"
    if not test_file.is_file():
        raise BuildError(f"unknown test '{test_name}' for ip '{ip_data['ip']}'")

    test_data = load_yaml(test_file)
    require_keys(test_data, ["test"], str(test_file))
    if not isinstance(test_data["test"], dict):
        raise BuildError(f"'test' must be a mapping in {test_file}")
    require_keys(test_data["test"], ["name", "description"], str(test_file))
    if test_data["test"]["name"] != test_name:
        raise BuildError(f"test file {test_file} does not match test name '{test_name}'")

    ip_data["test_name"] = test_name
    layout = ip_data["output_layout"]
    if mode == "test":
        run_dir = resolve_path(apply_template(layout["test_out_dir"], ip_data))
        log_file = resolve_path(apply_template(layout["test_log"], ip_data))
        tracker_path = resolve_path(apply_template(layout["test_tracker"], ip_data))
    else:
        run_dir = resolve_path(apply_template(layout["regression_test_out_dir"], ip_data))
        log_file = resolve_path(apply_template(layout["regression_test_log"], ip_data))
        tracker_path = resolve_path(
            apply_template(layout["regression_test_tracker"], ip_data)
        )
    ip_data["run_dir"] = run_dir
    ip_data["log_file"] = log_file
    ip_data["tracker_path"] = tracker_path
    return ip_data


def get_regression_tests(ip_data: dict, regression_name: str) -> list[str]:
    regression_file = REPO_ROOT / ip_data["regression_dir"] / f"{regression_name}.yaml"
    if not regression_file.is_file():
        raise BuildError(
            f"unknown regression '{regression_name}' for ip '{ip_data['ip']}'"
        )

    regression_data = load_yaml(regression_file)
    require_keys(regression_data, ["regression"], str(regression_file))
    regression = regression_data["regression"]
    if not isinstance(regression, dict):
        raise BuildError(f"'regression' must be a mapping in {regression_file}")
    require_keys(regression, ["name", "tests"], str(regression_file))
    if regression["name"] != regression_name:
        raise BuildError(
            f"regression file {regression_file} does not match regression '{regression_name}'"
        )

    tests = regression["tests"]
    if not isinstance(tests, list):
        raise BuildError(f"'tests' must be a list in {regression_file}")
    ip_data["regress_name"] = regression_name
    for test_name in tests:
        get_test_data(dict(ip_data), test_name, "regress")

    return list(tests)


def resolve_workflow_name(args: argparse.Namespace) -> str:
    if args.compile:
        return "compile"
    if args.test:
        return "test"
    return "regress"


def format_text(template: str, context: dict) -> str:
    return template.format(**context)


def normalize_command(command: str | dict) -> tuple[str, str | None]:
    if isinstance(command, str):
        return command, None
    if isinstance(command, dict) and "cmd" in command:
        return command["cmd"], command.get("log")
    raise BuildError("command entries must be strings or mappings with 'cmd'")


def resolve_filelist_entry(entry: str, context: dict) -> str:
    replaced = entry.replace(context["model_root_var"], context["repo_root"])
    return str(Path(replaced).resolve())


def expand_filelist(source_path: Path, context: dict) -> list[str]:
    expanded_lines: list[str] = []
    for raw_line in source_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-F"):
            nested = line[2:].strip()
            nested_path = Path(resolve_filelist_entry(nested, context))
            expanded_lines.extend(expand_filelist(nested_path, context))
            continue
        if line.startswith("+incdir+"):
            include_path = line[len("+incdir+") :].strip()
            expanded_lines.append("+incdir+" + resolve_filelist_entry(include_path, context))
            continue
        expanded_lines.append(resolve_filelist_entry(line, context))
    return expanded_lines


def write_generated_filelist(source_file: str, destination_file: str, context: dict) -> None:
    source_path = REPO_ROOT / source_file
    if not source_path.is_file():
        raise BuildError(f"missing source filelist: {source_path}")
    destination_path = Path(destination_file)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    expanded_lines = expand_filelist(source_path, context)
    destination_path.write_text("\n".join(expanded_lines) + "\n", encoding="utf-8")


def prepare_filelists(context: dict) -> None:
    Path(context["filelist_dir"]).mkdir(parents=True, exist_ok=True)
    write_generated_filelist(context["rtl_filelist"], context["generated_rtl_filelist"], context)
    write_generated_filelist(context["dv_filelist"], context["generated_dv_filelist"], context)
    write_generated_filelist(context["all_filelist"], context["generated_all_filelist"], context)


def run_command(command: str | dict, context: dict) -> None:
    if isinstance(command, dict) and command.get("action") == "prepare_filelists":
        print("wait prepare_filelists", flush=True)
        prepare_filelists(context)
        return

    command_text, log_name = normalize_command(command)
    formatted = format_text(command_text, context)
    print(f"wait {formatted}", flush=True)
    result = subprocess.run(
        formatted,
        shell=True,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if log_name:
        log_path = Path(format_text(log_name, context))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as handle:
            if result.stdout:
                handle.write(result.stdout)
            if result.stderr:
                handle.write(result.stderr)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="", file=sys.stderr)
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        raise BuildError(f"command failed with exit code {result.returncode}")


def run_step(
    step_name: str,
    steps_cfg: dict,
    context: dict,
    completed: set[str],
) -> None:
    if step_name in completed:
        return
    if step_name not in steps_cfg:
        raise BuildError(f"unknown build step '{step_name}'")

    step_cfg = steps_cfg[step_name]
    for dependency in step_cfg.get("deps", []):
        run_step(dependency, steps_cfg, context, completed)

    print(f"start {step_name}", flush=True)
    for command in step_cfg.get("commands", []):
        run_command(command, context)
    print(f"done {step_name}", flush=True)
    completed.add(step_name)


def run_regression(step_cfg: dict, base_context: dict, tests: list[str]) -> None:
    print(f"start regress ({base_context['regress_name']})", flush=True)
    if not tests:
        print(f"done regress ({base_context['regress_name']})", flush=True)
        return

    processes: list[tuple[str, dict, subprocess.Popen[str]]] = []

    for test_name in tests:
        test_context = dict(base_context)
        test_context = get_test_data(test_context, test_name, "regress")
        print(f"start test {test_name}", flush=True)
        command_parts = []
        for command in step_cfg.get("commands", []):
            command_text, _ = normalize_command(command)
            command_parts.append(format_text(command_text, test_context))
        formatted = " && ".join(command_parts)
        print(f"wait {formatted}", flush=True)
        process = subprocess.Popen(
            formatted,
            shell=True,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        processes.append((test_name, test_context, process))

    error_messages = []
    for test_name, test_context, process in processes:
        stdout, stderr = process.communicate()
        log_path = Path(test_context["log_file"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as handle:
            if stdout:
                handle.write(stdout)
            if stderr:
                handle.write(stderr)
        if process.returncode != 0:
            if stdout:
                error_messages.append(stdout)
            if stderr:
                error_messages.append(stderr)
            error_messages.append(f"test '{test_name}' failed with exit code {process.returncode}")
        else:
            print(f"done test {test_name}", flush=True)

    if error_messages:
        for message in error_messages:
            print(message, end="" if message.endswith("\n") else "\n", file=sys.stderr)
        raise BuildError("regression failed")

    print(f"done regress ({base_context['regress_name']})", flush=True)


def main() -> int:
    try:
        args = parse_args()
        build_cfg = load_yaml(BUILD_CONFIG)
        require_keys(build_cfg, ["workflows", "steps"], str(BUILD_CONFIG))
        workflows = build_cfg["workflows"]
        steps_cfg = build_cfg["steps"]
        if not isinstance(workflows, dict):
            raise BuildError(f"'workflows' must be a mapping in {BUILD_CONFIG}")
        if not isinstance(steps_cfg, dict):
            raise BuildError(f"'steps' must be a mapping in {BUILD_CONFIG}")

        workflow_name = resolve_workflow_name(args)
        if workflow_name not in workflows:
            raise BuildError(f"workflow '{workflow_name}' is not defined")

        context = get_ip_data(args.ip)
        context = apply_run_paths(context, resolve_tag(args.tag, context))
        regression_tests: list[str] = []

        if args.test:
            context = get_test_data(context, args.test, "test")
        elif args.regress:
            regression_tests = get_regression_tests(context, args.regress)
            context["regress_name"] = args.regress

        Path(context["compile_dir"]).mkdir(parents=True, exist_ok=True)

        completed: set[str] = set()
        print(
            f"start workflow {workflow_name} ip={context['ip']} tag={context['tag']}",
            flush=True,
        )
        for step_name in workflows[workflow_name]:
            if step_name == "regress":
                run_step("compile", steps_cfg, context, completed)
                run_regression(steps_cfg["regress"], context, regression_tests)
                completed.add("regress")
                continue

            run_step(step_name, steps_cfg, context, completed)
        print(
            f"done workflow {workflow_name} ip={context['ip']} tag={context['tag']}",
            flush=True,
        )
        return 0
    except BuildError as error:
        print(f"done error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
