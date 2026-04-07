#!/usr/bin/env python3
"""Minimal YAML-driven builder."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_CONFIG = REPO_ROOT / "tools" / "build" / "build.yaml"
IP_CONFIG = REPO_ROOT / "cfg" / "ip.yaml"
ENV_CONFIG = REPO_ROOT / "cfg" / "env.yaml"
SYNTH_CONFIG = REPO_ROOT / "cfg" / "synth.yaml"
FV_CONFIG = REPO_ROOT / "cfg" / "fv.yaml"


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


def lookup(mapping: dict, dotted_key: str):
    value = mapping
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise BuildError(f"missing '{dotted_key}' in environment context")
        value = value[part]
    return value


def resolve_template_text(text: str, mapping: dict) -> str:
    def replace(match):
        key = match.group(1)
        value = lookup(mapping, key)
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return re.sub(r"\{([^{}]+)\}", replace, text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run project build steps")
    parser.add_argument("-ip", help="IP name to build")
    parser.add_argument("-tag", help="run tag for the output directory")
    parser.add_argument("-lint", action="store_true", help="run lint step")
    parser.add_argument("-fv", action="store_true", help="run formal verification step")
    parser.add_argument("-synth", action="store_true", help="run synthesis step")
    parser.add_argument("-compile", action="store_true", help="run compile step")
    parser.add_argument("-test", help="run a named test")
    parser.add_argument("-regress", help="run a named regression")
    parser.add_argument("-debug", action="store_true", help="list saved waveforms and open one in gtkwave")
    args = parser.parse_args()

    requested_modes = sum(
        [
            1 if args.lint else 0,
            1 if args.fv else 0,
            1 if args.synth else 0,
            1 if args.compile else 0,
            1 if args.test else 0,
            1 if args.regress else 0,
            1 if args.debug else 0,
        ]
    )
    if requested_modes == 0:
        raise BuildError("select at least one of -lint, -fv, -synth, -compile, -test, -regress, or -debug")
    if args.debug and requested_modes != 1:
        raise BuildError("'-debug' must be used by itself")
    if args.test and args.regress:
        raise BuildError("select only one of '-test' or '-regress'")
    if not args.debug and not args.ip:
        raise BuildError("'-ip' is required for -lint, -fv, -synth, -compile, -test, or -regress")
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
            "generated_fv_filelist",
            "lint_out_dir",
            "lint_log",
            "fv_out_dir",
            "fv_log",
            "fv_run_dir",
            "generated_fv_config",
            "fv_summary_yaml",
            "synth_out_dir",
            "synth_log",
            "generated_synth_script",
            "synth_json",
            "synth_netlist",
            "synth_stat_json",
            "synth_area_report",
            "synth_check_report",
            "synth_summary_yaml",
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
    ip_data["test_name"] = ""
    ip_data["regress_name"] = ""
    return ip_data


def get_synth_profile(profile_name: str) -> dict:
    synth_root = load_yaml(SYNTH_CONFIG)
    require_keys(synth_root, ["scripts", "profiles"], str(SYNTH_CONFIG))
    scripts = synth_root["scripts"]
    profiles = synth_root["profiles"]
    if not isinstance(scripts, dict):
        raise BuildError(f"'scripts' must be a mapping in {SYNTH_CONFIG}")
    if not isinstance(profiles, dict):
        raise BuildError(f"'profiles' must be a mapping in {SYNTH_CONFIG}")
    if profile_name not in profiles:
        raise BuildError(f"unknown synth profile '{profile_name}'")

    profile = dict(profiles[profile_name])
    if "enabled" in profile and not profile["enabled"]:
        raise BuildError(f"synth profile '{profile_name}' is defined but not enabled")
    require_keys(
        profile,
        ["description", "script", "liberty", "abc_mode", "delay_target_ps", "check_is_gating", "technology"],
        f"profiles.{profile_name}",
    )
    script_name = profile["script"]
    if script_name not in scripts:
        raise BuildError(f"unknown synth script '{script_name}' for profile '{profile_name}'")
    script_cfg = scripts[script_name]
    if not isinstance(script_cfg, dict):
        raise BuildError(f"'scripts.{script_name}' must be a mapping in {SYNTH_CONFIG}")
    require_keys(script_cfg, ["path"], f"scripts.{script_name}")

    technology = profile["technology"]
    if not isinstance(technology, dict):
        raise BuildError(f"'technology' must be a mapping in profiles.{profile_name}")
    require_keys(technology, ["kind", "source", "note"], f"profiles.{profile_name}.technology")

    return {
        "synth_profile": profile_name,
        "synth_profile_description": profile["description"],
        "synth_script": resolve_path(script_cfg["path"]),
        "synth_liberty": resolve_path(profile["liberty"]),
        "synth_abc_mode": profile["abc_mode"],
        "synth_delay_target_ps": profile["delay_target_ps"],
        "synth_check_is_gating": bool(profile["check_is_gating"]),
        "synth_technology": technology,
    }


def get_fv_profile(profile_name: str) -> dict:
    fv_root = load_yaml(FV_CONFIG)
    require_keys(fv_root, ["scripts", "profiles"], str(FV_CONFIG))
    scripts = fv_root["scripts"]
    profiles = fv_root["profiles"]
    if not isinstance(scripts, dict):
        raise BuildError(f"'scripts' must be a mapping in {FV_CONFIG}")
    if not isinstance(profiles, dict):
        raise BuildError(f"'profiles' must be a mapping in {FV_CONFIG}")
    if profile_name not in profiles:
        raise BuildError(f"unknown fv profile '{profile_name}'")

    profile = dict(profiles[profile_name])
    require_keys(
        profile,
        ["description", "script", "mode", "depth", "expect", "engine", "solver", "multiclock"],
        f"profiles.{profile_name}",
    )
    script_name = profile["script"]
    if script_name not in scripts:
        raise BuildError(f"unknown fv script '{script_name}' for profile '{profile_name}'")
    script_cfg = scripts[script_name]
    if not isinstance(script_cfg, dict):
        raise BuildError(f"'scripts.{script_name}' must be a mapping in {FV_CONFIG}")
    require_keys(script_cfg, ["path"], f"scripts.{script_name}")

    return {
        "fv_profile": profile_name,
        "fv_profile_description": profile["description"],
        "fv_script_template": resolve_path(script_cfg["path"]),
        "fv_mode": profile["mode"],
        "fv_depth": profile["depth"],
        "fv_expect": profile["expect"],
        "fv_engine": profile["engine"],
        "fv_solver": profile["solver"],
        "fv_multiclock": bool(profile["multiclock"]),
    }


def get_env_data(required_tool_names: set[str]) -> dict:
    env_root = load_yaml(ENV_CONFIG)
    require_keys(env_root, ["environment"], str(ENV_CONFIG))
    env = env_root["environment"]
    if not isinstance(env, dict):
        raise BuildError(f"'environment' must be a mapping in {ENV_CONFIG}")

    require_keys(env, ["home_dir", "model_root", "tools", "simulation"], "environment")
    tools = env["tools"]
    if not isinstance(tools, dict):
        raise BuildError(f"'tools' must be a mapping in {ENV_CONFIG}")
    tool_key_requirements = {
        "python3": ["exe", "version", "version_cmd"],
        "verilator": ["exe", "version", "version_cmd", "trace_flag"],
        "gtkwave": ["exe", "version", "version_cmd"],
        "yosys": ["exe", "version", "version_cmd"],
        "sby": ["exe", "version", "version_cmd"],
        "boolector": ["exe", "version", "version_cmd"],
        "z3": ["exe", "version", "version_cmd"],
    }
    for tool_name in required_tool_names:
        if tool_name not in tool_key_requirements:
            raise BuildError(f"unsupported tool requirement '{tool_name}'")
        if tool_name not in tools:
            raise BuildError(f"missing '{tool_name}' in environment.tools")
        tool_cfg = tools[tool_name]
        if not isinstance(tool_cfg, dict):
            raise BuildError(f"'environment.tools.{tool_name}' must be a mapping in {ENV_CONFIG}")
        require_keys(
            tool_cfg,
            tool_key_requirements[tool_name],
            f"environment.tools.{tool_name}",
        )

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

    env_context = dict(env)
    env_context["repo_root"] = str(REPO_ROOT)
    env_context["host_home"] = os.environ.get("HOME", str(Path.home()))
    env_context["home_dir"] = resolve_template_text(str(env["home_dir"]), env_context)
    env_context["model_root"] = resolve_template_text(str(env["model_root"]), env_context)
    env_context["bin_dir"] = resolve_template_text(str(env["bin_dir"]), env_context)

    env_data = {
        "model_root": env_context["model_root"],
        "waveform_enabled": bool(waveform["enabled"]),
        "waveform_format": waveform["format"],
    }
    if "python3" in tools:
        env_data["python3_exe"] = resolve_template_text(str(tools["python3"]["exe"]), env_context)
        env_data["python3_version"] = resolve_template_text(str(tools["python3"]["version"]), env_context)
    if "verilator" in tools:
        env_data["verilator_exe"] = resolve_template_text(str(tools["verilator"]["exe"]), env_context)
        env_data["verilator_version"] = resolve_template_text(str(tools["verilator"]["version"]), env_context)
        env_data["verilator_trace_flag"] = (
            resolve_template_text(str(tools["verilator"]["trace_flag"]), env_context) if waveform["enabled"] else ""
        )
    if "gtkwave" in tools:
        env_data["gtkwave_exe"] = resolve_template_text(str(tools["gtkwave"]["exe"]), env_context)
        env_data["gtkwave_version"] = resolve_template_text(str(tools["gtkwave"]["version"]), env_context)
    if "yosys" in tools:
        env_data["yosys_exe"] = resolve_template_text(str(tools["yosys"]["exe"]), env_context)
        env_data["yosys_version"] = resolve_template_text(str(tools["yosys"]["version"]), env_context)
    if "sby" in tools:
        env_data["sby_exe"] = resolve_template_text(str(tools["sby"]["exe"]), env_context)
        env_data["sby_version"] = resolve_template_text(str(tools["sby"]["version"]), env_context)
    if "boolector" in tools:
        env_data["boolector_exe"] = resolve_template_text(str(tools["boolector"]["exe"]), env_context)
        env_data["boolector_version"] = resolve_template_text(str(tools["boolector"]["version"]), env_context)
    if "z3" in tools:
        env_data["z3_exe"] = resolve_template_text(str(tools["z3"]["exe"]), env_context)
        env_data["z3_version"] = resolve_template_text(str(tools["z3"]["version"]), env_context)
    return env_data


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
    ip_data["generated_fv_filelist"] = resolve_path(
        apply_template(layout["generated_fv_filelist"], ip_data)
    )
    ip_data["lint_out_dir"] = resolve_path(apply_template(layout["lint_out_dir"], ip_data))
    ip_data["fv_out_dir"] = resolve_path(apply_template(layout["fv_out_dir"], ip_data))
    ip_data["fv_run_dir"] = resolve_path(apply_template(layout["fv_run_dir"], ip_data))
    ip_data["generated_fv_config"] = resolve_path(apply_template(layout["generated_fv_config"], ip_data))
    ip_data["fv_summary_yaml"] = resolve_path(apply_template(layout["fv_summary_yaml"], ip_data))
    ip_data["synth_out_dir"] = resolve_path(apply_template(layout["synth_out_dir"], ip_data))
    ip_data["generated_synth_script"] = resolve_path(
        apply_template(layout["generated_synth_script"], ip_data)
    )
    ip_data["synth_json"] = resolve_path(apply_template(layout["synth_json"], ip_data))
    ip_data["synth_netlist"] = resolve_path(apply_template(layout["synth_netlist"], ip_data))
    ip_data["synth_stat_json"] = resolve_path(apply_template(layout["synth_stat_json"], ip_data))
    ip_data["synth_area_report"] = resolve_path(apply_template(layout["synth_area_report"], ip_data))
    ip_data["synth_check_report"] = resolve_path(apply_template(layout["synth_check_report"], ip_data))
    ip_data["synth_summary_yaml"] = resolve_path(apply_template(layout["synth_summary_yaml"], ip_data))
    ip_data["compile_dir"] = resolve_path(apply_template(layout["compile_dir"], ip_data))
    ip_data["binary_path"] = resolve_path(apply_template(layout["binary_path"], ip_data))
    ip_data["run_dir"] = ip_data["compile_dir"]
    ip_data["log_file"] = resolve_path(apply_template(layout["compile_log"], ip_data))
    ip_data["lint_log"] = resolve_path(apply_template(layout["lint_log"], ip_data))
    ip_data["fv_log"] = resolve_path(apply_template(layout["fv_log"], ip_data))
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


def resolve_requested_workflows(args: argparse.Namespace) -> list[str]:
    workflows: list[str] = []
    if args.debug:
        return ["debug"]
    if args.lint:
        workflows.append("lint")
    if args.fv:
        workflows.append("fv")
    if args.synth:
        workflows.append("synth")
    if args.compile:
        workflows.append("compile")
    if args.test:
        workflows.append("test")
    if args.regress:
        workflows.append("regress")
    return workflows


def collect_required_tool_names(
    requested_workflows: list[str],
    context: dict,
    fv_profile: dict | None,
) -> set[str]:
    required_tool_names: set[str] = set()
    if any(workflow in requested_workflows for workflow in ["lint", "compile", "test", "regress"]):
        required_tool_names.add("verilator")
    if "synth" in requested_workflows:
        required_tool_names.add("yosys")
    if "fv" in requested_workflows:
        if fv_profile is None:
            raise BuildError("internal error: missing fv profile")
        required_tool_names.update({"sby", "yosys", fv_profile["fv_solver"]})
    return required_tool_names


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
    if "fv_filelist" in context:
        write_generated_filelist(
            context["fv_filelist"],
            context["generated_fv_filelist"],
            context,
        )


def build_yosys_read_verilog_args(filelist_path: str) -> str:
    return build_yosys_read_verilog_args_multi([filelist_path])


def build_yosys_read_verilog_args_multi(filelist_paths: list[str]) -> str:
    include_args: list[str] = []
    source_args: list[str] = []
    for filelist_path in filelist_paths:
        for raw_line in Path(filelist_path).read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("+incdir+"):
                include_path = line[len("+incdir+") :].strip()
                include_args.extend(["-I", include_path])
                continue
            source_args.append(line)
    return " ".join(include_args + source_args)


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


def list_filelist_sources(filelist_path: str) -> list[str]:
    sources: list[str] = []
    for raw_line in Path(filelist_path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("+incdir+"):
            continue
        sources.append(line)
    return sources


def prepare_fv_config(context: dict) -> None:
    source_path = Path(context["fv_script_template"])
    if not source_path.is_file():
        raise BuildError(f"missing fv script template: {source_path}")
    destination_path = Path(context["generated_fv_config"])
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    fv_context = dict(context)
    fv_context["yosys_read_verilog_args"] = build_yosys_read_verilog_args_multi(
        [context["generated_rtl_filelist"], context["generated_fv_filelist"]]
    )
    fv_context["fv_multiclock_option"] = "multiclock on" if context["fv_multiclock"] else ""
    rendered = source_path.read_text(encoding="utf-8").format(**fv_context)
    destination_path.write_text(rendered + "\n", encoding="utf-8")


def parse_area_report(report_path: Path) -> dict:
    data: dict[str, int | dict[str, int] | None] = {"estimated_transistors": None}
    cell_counts: dict[str, int] = {}
    in_cells = False
    for raw_line in report_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("Number of wires:"):
            data["num_wires"] = int(stripped.split(":")[1].strip())
        elif stripped.startswith("Number of wire bits:"):
            data["num_wire_bits"] = int(stripped.split(":")[1].strip())
        elif stripped.startswith("Number of public wires:"):
            data["num_pub_wires"] = int(stripped.split(":")[1].strip())
        elif stripped.startswith("Number of public wire bits:"):
            data["num_pub_wire_bits"] = int(stripped.split(":")[1].strip())
        elif stripped.startswith("Number of memories:"):
            data["num_memories"] = int(stripped.split(":")[1].strip())
        elif stripped.startswith("Number of memory bits:"):
            data["num_memory_bits"] = int(stripped.split(":")[1].strip())
        elif stripped.startswith("Number of processes:"):
            data["num_processes"] = int(stripped.split(":")[1].strip())
        elif stripped.startswith("Number of cells:"):
            data["num_cells"] = int(stripped.split(":")[1].strip())
            in_cells = True
        elif stripped.startswith("Estimated number of transistors:"):
            value = stripped.split(":")[1].strip().rstrip("+")
            data["estimated_transistors"] = int(value)
            in_cells = False
        elif in_cells and stripped:
            parts = stripped.split()
            if len(parts) == 2 and parts[1].isdigit():
                cell_counts[parts[0]] = int(parts[1])
    data["num_cells_by_type"] = cell_counts
    return data


def parse_check_report(report_path: Path) -> dict:
    warnings: list[str] = []
    problem_count = 0
    for raw_line in report_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("Warning:"):
            warnings.append(line)
        if "Found and reported" in line and "problems" in line:
            parts = line.split()
            for token in parts:
                if token.isdigit():
                    problem_count = int(token)
                    break
    return {
        "warning_count": len(warnings),
        "problem_count": problem_count,
        "warnings_sample": warnings[:20],
    }


def relativize_path(path_text: str) -> str:
    return str(Path(path_text).resolve().relative_to(REPO_ROOT))


def prepare_synth_summary(context: dict) -> None:
    stat_path = Path(context["synth_stat_json"])
    area_path = Path(context["synth_area_report"])
    check_path = Path(context["synth_check_report"])
    if not stat_path.is_file():
        raise BuildError(f"missing synth stat report: {stat_path}")
    if not area_path.is_file():
        raise BuildError(f"missing synth area report: {area_path}")
    if not check_path.is_file():
        raise BuildError(f"missing synth check report: {check_path}")

    stat_data = json.loads(stat_path.read_text(encoding="utf-8"))
    area_data = parse_area_report(area_path)
    check_data = parse_check_report(check_path)

    design_stats = stat_data.get("design", {})
    summary = {
        "synth": {
            "ip": context["ip"],
            "tag": context["tag"],
            "module": context["rtl_module"],
            "profile": context["synth_profile"],
            "profile_description": context["synth_profile_description"],
            "status": {
                "completed": True,
                "check_is_gating": context["synth_check_is_gating"],
                "check_warning_count": check_data["warning_count"],
                "check_problem_count": check_data["problem_count"],
            },
            "tool": {
                "yosys_exe": context["yosys_exe"],
                "yosys_version": context["yosys_version"],
            },
            "technology": {
                "kind": context["synth_technology"]["kind"],
                "source": context["synth_technology"]["source"],
                "note": context["synth_technology"]["note"],
                "liberty": relativize_path(context["synth_liberty"]),
                "abc_mode": context["synth_abc_mode"],
                "delay_target_ps": context["synth_delay_target_ps"],
            },
            "artifacts": {
                "generated_script": relativize_path(context["generated_synth_script"]),
                "synth_log": relativize_path(context["synth_log"]),
                "json_netlist": relativize_path(context["synth_json"]),
                "verilog_netlist": relativize_path(context["synth_netlist"]),
                "stat_report": relativize_path(context["synth_stat_json"]),
                "area_report": relativize_path(context["synth_area_report"]),
                "check_report": relativize_path(context["synth_check_report"]),
            },
            "design": {
                "num_wires": design_stats.get("num_wires"),
                "num_wire_bits": design_stats.get("num_wire_bits"),
                "num_pub_wires": design_stats.get("num_pub_wires"),
                "num_pub_wire_bits": design_stats.get("num_pub_wire_bits"),
                "num_memories": design_stats.get("num_memories"),
                "num_memory_bits": design_stats.get("num_memory_bits"),
                "num_processes": design_stats.get("num_processes"),
                "num_cells": design_stats.get("num_cells"),
                "num_cells_by_type": design_stats.get("num_cells_by_type", {}),
                "estimated_transistors": area_data.get("estimated_transistors"),
            },
            "check": {
                "warnings_sample": check_data["warnings_sample"],
            },
        }
    }

    summary_path = Path(context["synth_summary_yaml"])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(yaml.safe_dump(summary, sort_keys=False), encoding="utf-8")


def prepare_fv_summary(context: dict) -> None:
    status_path = Path(context["fv_run_dir"]) / "status"
    if not status_path.is_file():
        raise BuildError(f"missing fv status file: {status_path}")
    status_text = status_path.read_text(encoding="utf-8").strip()
    status_parts = status_text.split()
    result = status_parts[0] if status_parts else "UNKNOWN"
    engine_index = int(status_parts[1]) if len(status_parts) > 1 and status_parts[1].isdigit() else None
    task_index = int(status_parts[2]) if len(status_parts) > 2 and status_parts[2].isdigit() else None
    trace_vcds = [
        relativize_path(str(path))
        for path in sorted(Path(context["fv_run_dir"]).glob("**/trace*.vcd"))
    ]
    summary = {
        "fv": {
            "ip": context["ip"],
            "tag": context["tag"],
            "top": context["fv_top"],
            "profile": context["fv_profile"],
            "profile_description": context["fv_profile_description"],
            "status": {
                "text": status_text,
                "result": result,
                "expected": context["fv_expect"].upper(),
                "engine_index": engine_index,
                "task_index": task_index,
            },
            "tool": {
                "sby_exe": context["sby_exe"],
                "sby_version": context["sby_version"],
                "yosys_exe": context["yosys_exe"],
                "yosys_version": context["yosys_version"],
                "solver_exe": context["fv_solver_exe"],
                "solver_version": context["fv_solver_version"],
            },
            "proof": {
                "mode": context["fv_mode"],
                "depth": context["fv_depth"],
                "engine": context["fv_engine"],
                "solver": context["fv_solver"],
                "multiclock": context["fv_multiclock"],
            },
            "artifacts": {
                "config": relativize_path(context["generated_fv_config"]),
                "generated_filelist": relativize_path(context["generated_fv_filelist"]),
                "log": relativize_path(context["fv_log"]),
                "run_dir": relativize_path(context["fv_run_dir"]),
                "status": relativize_path(str(status_path)),
                "trace_vcds": trace_vcds,
            },
            "sources": [
                relativize_path(source)
                for source in list_filelist_sources(context["generated_fv_filelist"])
            ],
        }
    }
    summary_path = Path(context["fv_summary_yaml"])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(yaml.safe_dump(summary, sort_keys=False), encoding="utf-8")


def resolve_fv_solver(context: dict) -> tuple[str, str]:
    solver = context["fv_solver"]
    if solver == "boolector":
        return context["boolector_exe"], context["boolector_version"]
    if solver == "z3":
        return context["z3_exe"], context["z3_version"]
    raise BuildError(f"unsupported fv solver '{solver}'")


def run_command(command: str | dict, context: dict) -> None:
    if isinstance(command, dict) and command.get("action") == "prepare_filelists":
        print("wait prepare_filelists", flush=True)
        prepare_filelists(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_synth_script":
        print("wait prepare_synth_script", flush=True)
        prepare_synth_script(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_fv_config":
        print("wait prepare_fv_config", flush=True)
        prepare_fv_config(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_fv_summary":
        print("wait prepare_fv_summary", flush=True)
        prepare_fv_summary(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_synth_summary":
        print("wait prepare_synth_summary", flush=True)
        prepare_synth_summary(context)
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


def validate_lint_context(context: dict) -> None:
    if not Path(context["lint_waiver"]).is_file():
        raise BuildError(f"missing lint waiver file: {context['lint_waiver']}")


def validate_fv_context(context: dict, fv_profile: dict | None) -> None:
    if fv_profile is None:
        raise BuildError("internal error: missing fv profile")
    context.update(fv_profile)
    if not isinstance(context["fv_filelist"], str) or not context["fv_filelist"]:
        raise BuildError(f"'fv_filelist' must be a non-empty string in ip.{context['ip']}")
    if not Path(context["fv_script_template"]).is_file():
        raise BuildError(f"missing fv script template: {context['fv_script_template']}")
    if not (REPO_ROOT / context["fv_filelist"]).is_file():
        raise BuildError(f"missing fv filelist: {REPO_ROOT / context['fv_filelist']}")
    if not Path(context["sby_exe"]).is_file():
        raise BuildError(f"missing sby executable: {context['sby_exe']}")
    solver_exe, solver_version = resolve_fv_solver(context)
    context["fv_solver_exe"] = solver_exe
    context["fv_solver_version"] = solver_version
    if not Path(solver_exe).is_file():
        raise BuildError(f"missing fv solver executable: {solver_exe}")


def validate_synth_context(context: dict) -> None:
    if "synth_profile" not in context:
        raise BuildError(f"missing 'synth_profile' in ip.{context['ip']}")
    context.update(get_synth_profile(context["synth_profile"]))
    if not Path(context["synth_script"]).is_file():
        raise BuildError(f"missing synth script: {context['synth_script']}")
    if not Path(context["synth_liberty"]).is_file():
        raise BuildError(f"missing synth liberty: {context['synth_liberty']}")


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

        requested_workflows = resolve_requested_workflows(args)
        if args.debug:
            env_data = get_env_data({"gtkwave"})
            run_debug_mode(env_data)
            return 0
        for workflow_name in requested_workflows:
            if workflow_name not in workflows:
                raise BuildError(f"workflow '{workflow_name}' is not defined")

        context = get_ip_data(args.ip)
        fv_profile: dict | None = None
        if "fv" in requested_workflows:
            require_keys(context, ["fv_profile", "fv_top", "fv_filelist"], f"ip.{context['ip']}")
            fv_profile = get_fv_profile(context["fv_profile"])
        required_tool_names = collect_required_tool_names(requested_workflows, context, fv_profile)

        env_data = get_env_data(required_tool_names)
        context.update(env_data)
        context = apply_run_paths(context, resolve_tag(args.tag, context))
        regression_tests: list[str] = []

        if args.test:
            get_test_data(dict(context), args.test, "test")
        if args.regress:
            regression_tests = get_regression_tests(context, args.regress)
            context["regress_name"] = args.regress
        if "lint" in requested_workflows:
            validate_lint_context(context)
        if "fv" in requested_workflows:
            validate_fv_context(context, fv_profile)
        if "synth" in requested_workflows:
            validate_synth_context(context)

        Path(context["compile_dir"]).mkdir(parents=True, exist_ok=True)

        completed: set[str] = set()
        print(
            f"start workflow {','.join(requested_workflows)} ip={context['ip']} tag={context['tag']}",
            flush=True,
        )
        for workflow_name in requested_workflows:
            if workflow_name == "lint":
                lint_context = dict(context)
                lint_context["run_dir"] = lint_context["lint_out_dir"]
                lint_context["log_file"] = lint_context["lint_log"]
                for step_name in workflows[workflow_name]:
                    run_step(step_name, steps_cfg, lint_context, completed)
                continue
            if workflow_name == "fv":
                fv_context = dict(context)
                fv_context["run_dir"] = fv_context["fv_out_dir"]
                fv_context["log_file"] = fv_context["fv_log"]
                for step_name in workflows[workflow_name]:
                    run_step(step_name, steps_cfg, fv_context, completed)
                continue
            if workflow_name == "synth":
                synth_context = dict(context)
                synth_context["run_dir"] = synth_context["synth_out_dir"]
                synth_context["log_file"] = synth_context["synth_log"]
                for step_name in workflows[workflow_name]:
                    run_step(step_name, steps_cfg, synth_context, completed)
                continue
            if workflow_name == "compile":
                compile_context = dict(context)
                compile_context["run_dir"] = compile_context["compile_dir"]
                compile_context["log_file"] = resolve_path(
                    apply_template(compile_context["output_layout"]["compile_log"], compile_context)
                )
                for step_name in workflows[workflow_name]:
                    run_step(step_name, steps_cfg, compile_context, completed)
                continue
            if workflow_name == "test":
                test_context = get_test_data(dict(context), args.test, "test")
                for step_name in workflows[workflow_name]:
                    run_step(step_name, steps_cfg, test_context, completed)
                continue
            if workflow_name == "regress":
                regress_context = dict(context)
                regress_context["regress_name"] = args.regress
                run_step("compile", steps_cfg, regress_context, completed)
                run_regression(steps_cfg["regress"], regress_context, regression_tests)
                completed.add("regress")
                continue
            raise BuildError(f"unsupported workflow '{workflow_name}'")
        print(
            f"done workflow {','.join(requested_workflows)} ip={context['ip']} tag={context['tag']}",
            flush=True,
        )
        return 0
    except BuildError as error:
        print(f"done error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
