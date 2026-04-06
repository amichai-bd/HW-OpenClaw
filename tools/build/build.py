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
ENV_CONFIG = REPO_ROOT / "cfg" / "env.yaml"


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
    parser.add_argument("-ip", help="IP name to build")
    parser.add_argument("-tag", help="run tag for the output directory")
    parser.add_argument("-lint", action="store_true", help="run lint step")
    parser.add_argument("-synth", action="store_true", help="run synthesis step")
    parser.add_argument("-compile", action="store_true", help="run compile step")
    parser.add_argument("-test", help="run a named test")
    parser.add_argument("-regress", help="run a named regression")
    parser.add_argument("-debug", action="store_true", help="list saved waveforms and open one in gtkwave")
    args = parser.parse_args()

    requested_modes = sum(
        [1 if args.lint else 0, 1 if args.synth else 0, 1 if args.compile else 0, 1 if args.test else 0, 1 if args.regress else 0, 1 if args.debug else 0]
    )
    if requested_modes != 1:
        raise BuildError("select exactly one of -lint, -synth, -compile, -test, -regress, or -debug")
    if not args.debug and not args.ip:
        raise BuildError("'-ip' is required for -lint, -synth, -compile, -test, or -regress")
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
            "lint_out_dir",
            "lint_log",
            "synth_out_dir",
            "synth_log",
            "generated_synth_script",
            "synth_json",
            "synth_netlist",
            "synth_stat_json",
            "synth_area_report",
            "synth_check_report",
            "compile_dir",
            "compile_log",
            "binary_path",
            "test_out_dir",
            "test_log",
            "test_tracker",
            "test_wave",
            "regression_test_out_dir",
            "regression_test_log",
            "regression_test_tracker",
            "regression_test_wave",
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
            "rtl_module",
            "synth_script",
            "synth_liberty",
            "synth_delay_target_ps",
            "dv_filelist",
            "all_filelist",
            "rtl_top",
            "lint_dir",
            "lint_waiver",
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
    ip_data["lint_source_dir"] = resolve_path(ip_data["lint_dir"])
    ip_data["lint_waiver"] = resolve_path(ip_data["lint_waiver"])
    ip_data["synth_script"] = resolve_path(ip_data["synth_script"])
    ip_data["synth_liberty"] = resolve_path(ip_data["synth_liberty"])
    ip_data["test_name"] = ""
    ip_data["regress_name"] = ""
    return ip_data


def get_env_data() -> dict:
    env_root = load_yaml(ENV_CONFIG)
    require_keys(env_root, ["environment"], str(ENV_CONFIG))
    env = env_root["environment"]
    if not isinstance(env, dict):
        raise BuildError(f"'environment' must be a mapping in {ENV_CONFIG}")

    require_keys(env, ["model_root", "tools", "simulation"], "environment")
    tools = env["tools"]
    if not isinstance(tools, dict):
        raise BuildError(f"'tools' must be a mapping in {ENV_CONFIG}")
    require_keys(tools, ["python3", "verilator", "gtkwave", "yosys"], "environment.tools")
    require_keys(tools["verilator"], ["exe", "version", "version_cmd", "trace_flag"], "environment.tools.verilator")
    require_keys(tools["python3"], ["exe", "version", "version_cmd"], "environment.tools.python3")
    require_keys(tools["gtkwave"], ["exe", "version", "version_cmd"], "environment.tools.gtkwave")
    require_keys(tools["yosys"], ["exe", "version", "version_cmd"], "environment.tools.yosys")

    simulation = env["simulation"]
    if not isinstance(simulation, dict):
        raise BuildError(f"'simulation' must be a mapping in {ENV_CONFIG}")
    require_keys(simulation, ["waveform"], "environment.simulation")
    waveform = simulation["waveform"]
    if not isinstance(waveform, dict):
        raise BuildError(f"'waveform' must be a mapping in {ENV_CONFIG}")
    require_keys(
        waveform,
        ["enabled", "format"],
        "environment.simulation.waveform",
    )

    return {
        "model_root": env["model_root"].format(repo_root=str(REPO_ROOT)),
        "python3_exe": tools["python3"]["exe"],
        "python3_version": tools["python3"]["version"],
        "verilator_exe": tools["verilator"]["exe"],
        "verilator_version": tools["verilator"]["version"],
        "verilator_trace_flag": tools["verilator"]["trace_flag"] if waveform["enabled"] else "",
        "gtkwave_exe": tools["gtkwave"]["exe"],
        "gtkwave_version": tools["gtkwave"]["version"],
        "yosys_exe": tools["yosys"]["exe"],
        "yosys_version": tools["yosys"]["version"],
        "waveform_enabled": bool(waveform["enabled"]),
        "waveform_format": waveform["format"],
    }


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
    ip_data["lint_out_dir"] = resolve_path(apply_template(layout["lint_out_dir"], ip_data))
    ip_data["synth_out_dir"] = resolve_path(apply_template(layout["synth_out_dir"], ip_data))
    ip_data["generated_synth_script"] = resolve_path(
        apply_template(layout["generated_synth_script"], ip_data)
    )
    ip_data["synth_json"] = resolve_path(apply_template(layout["synth_json"], ip_data))
    ip_data["synth_netlist"] = resolve_path(apply_template(layout["synth_netlist"], ip_data))
    ip_data["synth_stat_json"] = resolve_path(apply_template(layout["synth_stat_json"], ip_data))
    ip_data["synth_area_report"] = resolve_path(apply_template(layout["synth_area_report"], ip_data))
    ip_data["synth_check_report"] = resolve_path(apply_template(layout["synth_check_report"], ip_data))
    ip_data["compile_dir"] = resolve_path(apply_template(layout["compile_dir"], ip_data))
    ip_data["binary_path"] = resolve_path(apply_template(layout["binary_path"], ip_data))
    ip_data["run_dir"] = ip_data["compile_dir"]
    ip_data["log_file"] = resolve_path(apply_template(layout["compile_log"], ip_data))
    ip_data["lint_log"] = resolve_path(apply_template(layout["lint_log"], ip_data))
    ip_data["synth_log"] = resolve_path(apply_template(layout["synth_log"], ip_data))
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
        wave_path = resolve_path(apply_template(layout["test_wave"], ip_data))
    else:
        run_dir = resolve_path(apply_template(layout["regression_test_out_dir"], ip_data))
        log_file = resolve_path(apply_template(layout["regression_test_log"], ip_data))
        tracker_path = resolve_path(
            apply_template(layout["regression_test_tracker"], ip_data)
        )
        wave_path = resolve_path(apply_template(layout["regression_test_wave"], ip_data))
    ip_data["run_dir"] = run_dir
    ip_data["log_file"] = log_file
    ip_data["tracker_path"] = tracker_path
    ip_data["wave_path"] = wave_path
    ip_data["wave_enable"] = 1 if ip_data["waveform_enabled"] else 0
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
    if args.debug:
        return "debug"
    if args.lint:
        return "lint"
    if args.synth:
        return "synth"
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


def build_yosys_read_verilog_args(filelist_path: str) -> str:
    args: list[str] = []
    for raw_line in Path(filelist_path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("+incdir+"):
            include_path = line[len("+incdir+") :].strip()
            args.extend(["-I", include_path])
            continue
        args.append(line)
    return " ".join(args)


def prepare_synth_script(context: dict) -> None:
    source_path = Path(context["synth_script"])
    if not source_path.is_file():
        raise BuildError(f"missing synth script: {source_path}")
    destination_path = Path(context["generated_synth_script"])
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    synth_context = dict(context)
    synth_context["yosys_read_verilog_args"] = build_yosys_read_verilog_args(
        context["generated_rtl_filelist"]
    )
    rendered = source_path.read_text(encoding="utf-8").format(**synth_context)
    destination_path.write_text(rendered + "\n", encoding="utf-8")


def run_command(command: str | dict, context: dict) -> None:
    if isinstance(command, dict) and command.get("action") == "prepare_filelists":
        print("wait prepare_filelists", flush=True)
        prepare_filelists(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_synth_script":
        print("wait prepare_synth_script", flush=True)
        prepare_synth_script(context)
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


def parse_debug_entry(wave_path: Path) -> dict | None:
    parts = wave_path.relative_to(REPO_ROOT).parts
    if len(parts) < 5 or parts[0] != "workdir":
        return None

    tag = parts[1]
    ip_name = parts[2]

    if len(parts) == 6 and parts[3] == "tests":
        test_name = parts[4]
        run_kind = "test"
        regression_name = ""
    elif len(parts) == 7 and parts[3] == "regressions":
        regression_name = parts[4]
        test_name = parts[5]
        run_kind = "regress"
    else:
        return None

    stat_result = wave_path.stat()
    return {
        "wave_path": wave_path,
        "tag": tag,
        "ip": ip_name,
        "test_name": test_name,
        "run_kind": run_kind,
        "regress_name": regression_name,
        "timestamp": datetime.fromtimestamp(stat_result.st_mtime),
    }


def discover_debug_entries() -> list[dict]:
    workdir = REPO_ROOT / "workdir"
    if not workdir.is_dir():
        return []

    entries: list[dict] = []
    for wave_path in workdir.glob("*/*/tests/*/*.vcd"):
        parsed = parse_debug_entry(wave_path)
        if parsed is not None:
            entries.append(parsed)
    for wave_path in workdir.glob("*/*/regressions/*/*/*.vcd"):
        parsed = parse_debug_entry(wave_path)
        if parsed is not None:
            entries.append(parsed)

    entries.sort(key=lambda entry: entry["timestamp"], reverse=True)
    return entries


def print_debug_entries(entries: list[dict]) -> None:
    for index, entry in enumerate(entries, start=1):
        timestamp = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        reg_text = ""
        if entry["run_kind"] == "regress":
            reg_text = f" | reg={entry['regress_name']}"
        print(
            f"[{index}] {timestamp} | tag={entry['tag']} | ip={entry['ip']} | test={entry['test_name']}{reg_text}",
            flush=True,
        )


def open_debug_entry(entries: list[dict], gtkwave_exe: str) -> None:
    print_debug_entries(entries)
    while True:
        selection = input("select entry number to open with gtkwave (blank to cancel): ").strip()
        if selection == "":
            print("done debug canceled", flush=True)
            return
        if not selection.isdigit():
            print("wait enter a valid number", flush=True)
            continue
        index = int(selection)
        if index < 1 or index > len(entries):
            print("wait enter a valid number", flush=True)
            continue

        selected = entries[index - 1]
        wave_path = str(selected["wave_path"])
        try:
            subprocess.Popen(
                [gtkwave_exe, wave_path],
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise BuildError(f"failed to launch gtkwave: {error}") from error
        print(f"done debug open={wave_path}", flush=True)
        return


def run_debug_mode(env_data: dict) -> None:
    entries = discover_debug_entries()
    if not entries:
        raise BuildError("no saved waveform files found under workdir")

    print("start debug", flush=True)
    open_debug_entry(entries, env_data["gtkwave_exe"])


def main() -> int:
    try:
        args = parse_args()
        env_data = get_env_data()
        if args.debug:
            run_debug_mode(env_data)
            return 0

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
        context.update(env_data)
        context = apply_run_paths(context, resolve_tag(args.tag, context))
        regression_tests: list[str] = []

        if args.test:
            context = get_test_data(context, args.test, "test")
        elif args.regress:
            regression_tests = get_regression_tests(context, args.regress)
            context["regress_name"] = args.regress
        elif args.lint:
            if not Path(context["lint_waiver"]).is_file():
                raise BuildError(f"missing lint waiver file: {context['lint_waiver']}")
            context["run_dir"] = context["lint_out_dir"]
            context["log_file"] = context["lint_log"]
        elif args.synth:
            if not Path(context["synth_script"]).is_file():
                raise BuildError(f"missing synth script: {context['synth_script']}")
            if not Path(context["synth_liberty"]).is_file():
                raise BuildError(f"missing synth liberty: {context['synth_liberty']}")
            context["run_dir"] = context["synth_out_dir"]
            context["log_file"] = context["synth_log"]

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
