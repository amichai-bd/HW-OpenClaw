#!/usr/bin/env python3
"""Minimal YAML-driven builder."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from time import monotonic

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_CONFIG = REPO_ROOT / "tools" / "build" / "build.yaml"
IP_CONFIG = REPO_ROOT / "cfg" / "ip.yaml"
ENV_CONFIG = REPO_ROOT / "cfg" / "env.yaml"
SYNTH_CONFIG = REPO_ROOT / "cfg" / "synth.yaml"
FV_CONFIG = REPO_ROOT / "cfg" / "fv.yaml"
INTERACTIVE_SELECT = "__interactive_select__"


class BuildError(RuntimeError):
    """Raised when build setup or execution fails."""


PRINT_LOCK = threading.Lock()
COLOR_ENABLED = sys.stdout.isatty() and os.environ.get("TERM", "").lower() != "dumb"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_WAIT = "\033[33m"
COLOR_START = "\033[36m"
COLOR_PASS = "\033[32m"
COLOR_FAIL = "\033[31m"
COLOR_COMMAND = "\033[35m"


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
    parser.add_argument("-test", nargs="?", const=INTERACTIVE_SELECT, help="run a named test")
    parser.add_argument("-regress", nargs="?", const=INTERACTIVE_SELECT, help="run a named regression")
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
    if args.debug and requested_modes != 1:
        raise BuildError("'-debug' must be used by itself")
    if args.test and args.regress:
        raise BuildError("select only one of '-test' or '-regress'")
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


def get_available_ips() -> list[str]:
    ip_root = load_yaml(IP_CONFIG)
    require_keys(ip_root, ["ip"], str(IP_CONFIG))
    ip_cfg = ip_root["ip"]
    if not isinstance(ip_cfg, dict):
        raise BuildError(f"'ip' must be a mapping in {IP_CONFIG}")
    return sorted(ip_cfg.keys())


def load_named_yaml_entries(directory: Path, top_key: str) -> list[str]:
    if not directory.is_dir():
        raise BuildError(f"missing directory: {directory}")
    names: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        data = load_yaml(path)
        if top_key not in data or not isinstance(data[top_key], dict):
            continue
        name = data[top_key].get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def get_available_tests(ip_data: dict) -> list[str]:
    return load_named_yaml_entries(REPO_ROOT / ip_data["test_dir"], "test")


def get_available_regressions(ip_data: dict) -> list[str]:
    return load_named_yaml_entries(REPO_ROOT / ip_data["regression_dir"], "regression")


def format_available_names(label: str, names: list[str]) -> str:
    if not names:
        return f"available {label}: none"
    return f"available {label}: {', '.join(names)}"


def prompt_for_named_entry(kind: str, names: list[str]) -> str | None:
    if not names:
        raise BuildError(f"no {kind}s are defined")
    with PRINT_LOCK:
        print(f"available {kind}s:", flush=True)
        for index, name in enumerate(names, start=1):
            print(f"  [{index}] {name}", flush=True)
    while True:
        selection = input(f"select {kind} number (0/q to cancel): ").strip()
        if selection in {"0", "q", "Q", ""}:
            return None
        if not selection.isdigit():
            with PRINT_LOCK:
                print("enter a valid number", flush=True)
            continue
        index = int(selection)
        if 1 <= index <= len(names):
            return names[index - 1]
        with PRINT_LOCK:
            print("enter a valid number", flush=True)


def prompt_for_modes() -> list[str] | None:
    mode_items = [
        ("lint", "-lint"),
        ("fv", "-fv"),
        ("synth", "-synth"),
        ("compile", "-compile"),
        ("test", "-test"),
        ("regress", "-regress"),
        ("debug", "-debug"),
    ]
    with PRINT_LOCK:
        print("available modes:", flush=True)
        for index, (name, flag) in enumerate(mode_items, start=1):
            print(f"  [{index}] {name} ({flag})", flush=True)
    while True:
        selection = input("select mode numbers (comma-separated, 0/q to cancel): ").strip()
        if selection in {"0", "q", "Q", ""}:
            return None
        parts = [part.strip() for part in selection.split(",") if part.strip()]
        if not parts or not all(part.isdigit() for part in parts):
            with PRINT_LOCK:
                print("enter valid mode numbers", flush=True)
            continue
        indexes = [int(part) for part in parts]
        if any(index < 1 or index > len(mode_items) for index in indexes):
            with PRINT_LOCK:
                print("enter valid mode numbers", flush=True)
            continue
        selected = [mode_items[index - 1][0] for index in indexes]
        selected_set = set(selected)
        if "debug" in selected_set and len(selected_set) != 1:
            with PRINT_LOCK:
                print("debug must be selected by itself", flush=True)
            continue
        if "test" in selected_set and "regress" in selected_set:
            with PRINT_LOCK:
                print("select only one of test or regress", flush=True)
            continue
        return selected


def apply_selected_modes(args: argparse.Namespace, selected_modes: list[str]) -> None:
    args.lint = "lint" in selected_modes
    args.fv = "fv" in selected_modes
    args.synth = "synth" in selected_modes
    args.compile = "compile" in selected_modes
    args.debug = "debug" in selected_modes
    if "test" in selected_modes and not args.test:
        args.test = INTERACTIVE_SELECT
    if "regress" in selected_modes and not args.regress:
        args.regress = INTERACTIVE_SELECT


def get_requested_target_names(args: argparse.Namespace) -> list[str]:
    return resolve_requested_targets(args)


def get_requested_mode_names(args: argparse.Namespace) -> list[str]:
    return get_requested_target_names(args)


def build_resolved_command(args: argparse.Namespace) -> str:
    parts = ["build"]
    if args.ip:
        parts.extend(["-ip", args.ip])
    if args.tag:
        parts.extend(["-tag", args.tag])
    if args.lint:
        parts.append("-lint")
    if args.fv:
        parts.append("-fv")
    if args.synth:
        parts.append("-synth")
    if args.compile:
        parts.append("-compile")
    if args.test:
        parts.extend(["-test", args.test])
    if args.regress:
        parts.extend(["-regress", args.regress])
    if args.debug:
        parts.append("-debug")
    return " ".join(parts)


def get_test_data(ip_data: dict, test_name: str, mode: str) -> dict:
    test_file = REPO_ROOT / ip_data["test_dir"] / f"{test_name}.yaml"
    if not test_file.is_file():
        raise BuildError(
            f"unknown test '{test_name}' for ip '{ip_data['ip']}' | {format_available_names('tests', get_available_tests(ip_data))}"
        )

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
            f"unknown regression '{regression_name}' for ip '{ip_data['ip']}' | {format_available_names('regressions', get_available_regressions(ip_data))}"
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


def resolve_requested_targets(args: argparse.Namespace) -> list[str]:
    targets: list[str] = []
    if args.debug:
        return ["debug"]
    if args.lint:
        targets.append("lint")
    if args.fv:
        targets.append("fv")
    if args.synth:
        targets.append("synth")
    if args.compile:
        targets.append("compile")
    if args.test:
        targets.append("test")
    if args.regress:
        targets.append("regress")
    return targets


def collect_required_tool_names(
    requested_targets: list[str],
    targets_cfg: dict,
    context: dict,
) -> set[str]:
    required_tool_names: set[str] = set()
    for target_name in requested_targets:
        if target_name == "debug":
            required_tool_names.add("gtkwave")
            continue
        target_cfg = targets_cfg[target_name]
        tool_requirements = target_cfg.get("tool_requirements", [])
        if not isinstance(tool_requirements, list):
            raise BuildError(f"'tool_requirements' must be a list for target '{target_name}'")
        for tool_name in tool_requirements:
            if not isinstance(tool_name, str):
                raise BuildError(f"tool requirement entries must be strings for target '{target_name}'")
            required_tool_names.add(format_text(tool_name, context))
    return required_tool_names


def format_text(template: str, context: dict) -> str:
    return template.format(**context)


def normalize_command(command: str | dict) -> tuple[str, str | None]:
    if isinstance(command, str):
        return command, None
    if isinstance(command, dict) and "cmd" in command:
        return command["cmd"], command.get("log")
    raise BuildError("command entries must be strings or mappings with 'cmd'")


def get_step_dependencies(step_name: str, steps_cfg: dict) -> list[str]:
    if step_name not in steps_cfg:
        raise BuildError(f"unknown build step '{step_name}'")
    step_cfg = steps_cfg[step_name]
    depends_on = step_cfg.get("depends_on")
    if depends_on is None:
        depends_on = step_cfg.get("deps", [])
    if not isinstance(depends_on, list):
        raise BuildError(f"'depends_on' must be a list for step '{step_name}'")
    return list(depends_on)


def collect_step_closure(
    step_name: str,
    steps_cfg: dict,
    memo: dict[str, set[str]],
    active: set[str] | None = None,
) -> set[str]:
    if step_name in memo:
        return memo[step_name]
    if active is None:
        active = set()
    if step_name in active:
        raise BuildError(f"cyclic step dependency detected at '{step_name}'")
    active.add(step_name)
    closure = {step_name}
    for dependency in get_step_dependencies(step_name, steps_cfg):
        closure.update(collect_step_closure(dependency, steps_cfg, memo, active))
    active.remove(step_name)
    memo[step_name] = closure
    return closure


def collect_target_step_closure(target_name: str, targets_cfg: dict, steps_cfg: dict, memo: dict[str, set[str]]) -> set[str]:
    closure: set[str] = set()
    target_cfg = targets_cfg[target_name]
    root_steps = target_cfg.get("root_steps", [])
    if not isinstance(root_steps, list):
        raise BuildError(f"'root_steps' must be a list for target '{target_name}'")
    for step_name in root_steps:
        closure.update(collect_step_closure(step_name, steps_cfg, memo))
    return closure


def collect_target_dependencies(requested_targets: list[str], targets_cfg: dict, steps_cfg: dict) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    step_to_target: dict[str, str] = {}
    for target_name, target_cfg in targets_cfg.items():
        root_steps = target_cfg.get("root_steps", [])
        if not isinstance(root_steps, list):
            raise BuildError(f"'root_steps' must be a list for target '{target_name}'")
        for step_name in root_steps:
            if step_name in step_to_target and step_to_target[step_name] != target_name:
                raise BuildError(f"step '{step_name}' is assigned to multiple targets")
            step_to_target[step_name] = target_name

    memo: dict[str, set[str]] = {}
    target_closures = {
        target_name: collect_target_step_closure(target_name, targets_cfg, steps_cfg, memo)
        for target_name in requested_targets
    }

    requested_set = set(requested_targets)
    target_dependencies: dict[str, set[str]] = {}
    for target_name in requested_targets:
        dependencies: set[str] = set()
        for step_name in targets_cfg[target_name].get("root_steps", []):
            for dependency_step in collect_step_closure(step_name, steps_cfg, memo):
                dependency_target = step_to_target.get(dependency_step)
                if dependency_target and dependency_target != target_name and dependency_target in requested_set:
                    dependencies.add(dependency_target)
        target_dependencies[target_name] = dependencies
    return target_dependencies, target_closures


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


def display_path(path_text: str) -> str:
    try:
        return relativize_path(path_text)
    except ValueError:
        return str(Path(path_text).resolve())


def timestamp_text() -> str:
    return datetime.now().strftime("%H:%M:%S")


def duration_text(start_time: float) -> str:
    elapsed = monotonic() - start_time
    if elapsed < 1.0:
        return f"+{int(round(elapsed * 1000.0))}ms"
    return f"+{elapsed:.1f}s"


def colorize(text: str, color: str, *, bold: bool = False) -> str:
    if not COLOR_ENABLED:
        return text
    prefix = color
    if bold:
        prefix += COLOR_BOLD
    return f"{prefix}{text}{COLOR_RESET}"


def status_prefix(kind: str) -> str:
    base = f"[{kind} {timestamp_text()}]"
    if kind == "wait":
        return colorize(base, COLOR_WAIT, bold=True)
    if kind == "start":
        return colorize(base, COLOR_START, bold=True)
    if kind == "done-pass":
        return colorize(base, COLOR_PASS, bold=True)
    if kind == "done-fail":
        return colorize(base, COLOR_FAIL, bold=True)
    return base


def print_status_line(kind: str, subject: str, *, duration: str | None = None) -> None:
    text = f"{status_prefix(kind)} {subject}"
    if duration:
        text += f" {duration}"
    with PRINT_LOCK:
        print(text, flush=True)


def print_review_files(paths: list[str]) -> None:
    with PRINT_LOCK:
        for index, path_text in enumerate(paths[:3], start=1):
            print(f"  file{index}={display_path(path_text)}", flush=True)


def print_review_hint(paths: list[str]) -> None:
    if not paths:
        return
    with PRINT_LOCK:
        print(f"  review_first={display_path(paths[0])}", flush=True)


def print_summary_line(text: str) -> None:
    with PRINT_LOCK:
        print(f"  summary={text}", flush=True)


def print_command_banner(command_text: str, phase: str) -> None:
    label = f"[command {timestamp_text()}] {phase}"
    if COLOR_ENABLED:
        label = colorize(label, COLOR_COMMAND, bold=True)
        command_text = colorize(command_text, COLOR_COMMAND)
    with PRINT_LOCK:
        print(label, flush=True)
        print(f"  {command_text}", flush=True)


def render_value(template: str, context: dict) -> str:
    if template.startswith("{") and template.endswith("}") and "." in template[1:-1]:
        inner_key = template[1:-1]
        value = lookup(context, inner_key)
        if isinstance(value, str):
            return format_text(value, context)
        return str(value)
    return format_text(template, context)


def render_paths(templates: list[str], context: dict) -> list[str]:
    paths: list[str] = []
    for template in templates:
        if not isinstance(template, str):
            continue
        rendered = render_value(template, context)
        if rendered:
            paths.append(rendered)
    return paths


def get_step_review_files(step_name: str, steps_cfg: dict, context: dict) -> list[str]:
    step_cfg = steps_cfg.get(step_name, {})
    review_files = step_cfg.get("review_files", [])
    if not isinstance(review_files, list):
        raise BuildError(f"'review_files' must be a list for step '{step_name}'")
    return render_paths(review_files, context)


def get_target_review_files(target_name: str, targets_cfg: dict, context: dict) -> list[str]:
    target_cfg = targets_cfg.get(target_name, {})
    review_files = target_cfg.get("review_files", [])
    if not isinstance(review_files, list):
        raise BuildError(f"'review_files' must be a list for target '{target_name}'")
    return render_paths(review_files, context)


def get_step_display_name(step_name: str, steps_cfg: dict, context: dict) -> str:
    step_cfg = steps_cfg.get(step_name, {})
    display_name = step_cfg.get("display_name")
    if isinstance(display_name, str) and display_name:
        return render_value(display_name, context)
    return f"{step_name} {context['ip']}"


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


def run_command(command: str | dict, context: dict, steps_cfg: dict) -> None:
    if isinstance(command, dict) and command.get("action") == "prepare_filelists":
        prepare_filelists(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_synth_script":
        prepare_synth_script(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_fv_config":
        prepare_fv_config(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_fv_summary":
        prepare_fv_summary(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_synth_summary":
        prepare_synth_summary(context)
        return
    if isinstance(command, dict) and command.get("action") == "run_regression":
        run_regression(steps_cfg["regress"], context, context.get("selected_tests", []), steps_cfg)
        return

    command_text, log_name = normalize_command(command)
    formatted = format_text(command_text, context)
    result = subprocess.run(
        formatted,
        shell=True,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if log_name:
        log_path = Path(render_value(log_name, context))
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
    subject = get_step_display_name(step_name, steps_cfg, context)
    for dependency in get_step_dependencies(step_name, steps_cfg):
        run_step(dependency, steps_cfg, context, completed)

    start_time = monotonic()
    print_status_line("start", subject)
    try:
        for command in step_cfg.get("commands", []):
            run_command(command, context, steps_cfg)
    except BuildError:
        review_files = get_step_review_files(step_name, steps_cfg, context)
        print_status_line("done-fail", subject, duration=duration_text(start_time))
        print_review_files(review_files)
        print_review_hint(review_files)
        raise
    review_files = get_step_review_files(step_name, steps_cfg, context)
    print_status_line("done-pass", subject, duration=duration_text(start_time))
    print_review_files(review_files)
    completed.add(step_name)


def run_regression(step_cfg: dict, base_context: dict, tests: list[str], steps_cfg: dict) -> None:
    if not tests:
        print_summary_line("tests=0 passed=0 failed=0")
        return

    processes: list[tuple[str, dict, subprocess.Popen[str]]] = []
    simulate_step_cfg = steps_cfg["simulate"]
    failed_tests: list[str] = []
    passed_count = 0

    for test_name in tests:
        test_context = dict(base_context)
        test_context = get_test_data(test_context, test_name, "regress")
        test_subject = get_step_display_name("simulate", steps_cfg, test_context)
        test_context["status_subject"] = test_subject
        test_context["start_time"] = monotonic()
        print_status_line("start", test_subject)
        command_parts = []
        for command in simulate_step_cfg.get("commands", []):
            command_text, _ = normalize_command(command)
            command_parts.append(format_text(command_text, test_context))
        formatted = " && ".join(command_parts)
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
            failed_tests.append(test_name)
            review_files = get_step_review_files("simulate", steps_cfg, test_context)
            print_status_line("done-fail", test_context["status_subject"], duration=duration_text(test_context["start_time"]))
            print_review_files(review_files)
            print_review_hint(review_files)
        else:
            passed_count += 1
            print_status_line("done-pass", test_context["status_subject"], duration=duration_text(test_context["start_time"]))
            print_review_files(get_step_review_files("simulate", steps_cfg, test_context))

    if error_messages:
        print_summary_line(
            f"tests={len(tests)} passed={passed_count} failed={len(failed_tests)} failed_names={','.join(failed_tests)}"
        )
        for message in error_messages:
            print(message, end="" if message.endswith("\n") else "\n", file=sys.stderr)
        raise BuildError("regression failed")
    print_summary_line(f"tests={len(tests)} passed={passed_count} failed=0")


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
    start_time = monotonic()
    while True:
        selection = input("select entry number to open with gtkwave (blank to cancel): ").strip()
        if selection == "":
            print_status_line("done-pass", "debug", duration=duration_text(start_time))
            return
        if not selection.isdigit():
            continue
        index = int(selection)
        if index < 1 or index > len(entries):
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
        print_status_line("done-pass", "debug", duration=duration_text(start_time))
        print_review_files([wave_path])
        return


def run_debug_mode(env_data: dict) -> None:
    entries = discover_debug_entries()
    if not entries:
        raise BuildError("no saved waveform files found under workdir")

    print_status_line("wait", "debug")
    print_status_line("start", "debug")
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


def announce_step_tree(
    step_name: str,
    steps_cfg: dict,
    context: dict,
    announced: set[str],
) -> None:
    if step_name in announced:
        return
    for dependency in get_step_dependencies(step_name, steps_cfg):
        announce_step_tree(dependency, steps_cfg, context, announced)
    print_status_line("wait", get_step_display_name(step_name, steps_cfg, context))
    announced.add(step_name)


def announce_regression_tests(base_context: dict, tests: list[str], steps_cfg: dict) -> None:
    for test_name in tests:
        test_context = get_test_data(dict(base_context), test_name, "regress")
        print_status_line("wait", get_step_display_name("simulate", steps_cfg, test_context))


def resolve_selector_argument_name(param_name: str) -> str:
    selector_to_arg = {
        "test_name": "test",
        "regress_name": "regress",
    }
    if param_name not in selector_to_arg:
        raise BuildError(f"unsupported selector param '{param_name}'")
    return selector_to_arg[param_name]


def resolve_target_context(
    base_context: dict,
    target_name: str,
    target_cfg: dict,
    args: argparse.Namespace,
) -> dict:
    context = dict(base_context)
    selector_cfg = target_cfg.get("selector")
    if selector_cfg is not None:
        if not isinstance(selector_cfg, dict):
            raise BuildError(f"'selector' must be a mapping for target '{target_name}'")
        require_keys(selector_cfg, ["kind", "param"], f"targets.{target_name}.selector")
        selector_kind = selector_cfg["kind"]
        selector_param = selector_cfg["param"]
        arg_name = resolve_selector_argument_name(selector_param)
        selected_name = getattr(args, arg_name)
        if not isinstance(selected_name, str) or not selected_name:
            raise BuildError(f"missing selector value for target '{target_name}'")
        if selector_kind == "test":
            context = get_test_data(context, selected_name, "test")
        elif selector_kind == "regression":
            context["regress_name"] = selected_name
            context["selected_tests"] = get_regression_tests(dict(context), selected_name)
        else:
            raise BuildError(f"unsupported selector kind '{selector_kind}' for target '{target_name}'")

    target_context_cfg = target_cfg.get("context", {})
    if target_context_cfg:
        if not isinstance(target_context_cfg, dict):
            raise BuildError(f"'context' must be a mapping for target '{target_name}'")
        for key, value in target_context_cfg.items():
            if not isinstance(value, str):
                raise BuildError(f"context values must be strings for target '{target_name}'")
            context[key] = render_value(value, context)
    return context


def main() -> int:
    resolved_command_text = ""
    try:
        args = parse_args()
        if not args.ip and not args.debug:
            selected_ip = prompt_for_named_entry("ip", get_available_ips())
            if selected_ip is None:
                with PRINT_LOCK:
                    print(f"[done-pass {timestamp_text()}] ip selection canceled", flush=True)
                return 0
            args.ip = selected_ip

        if not get_requested_mode_names(args):
            selected_modes = prompt_for_modes()
            if selected_modes is None:
                with PRINT_LOCK:
                    print(f"[done-pass {timestamp_text()}] mode selection canceled", flush=True)
                return 0
            apply_selected_modes(args, selected_modes)

        build_cfg = load_yaml(BUILD_CONFIG)
        require_keys(build_cfg, ["targets", "steps"], str(BUILD_CONFIG))
        targets_cfg = build_cfg["targets"]
        steps_cfg = build_cfg["steps"]
        if not isinstance(targets_cfg, dict):
            raise BuildError(f"'targets' must be a mapping in {BUILD_CONFIG}")
        if not isinstance(steps_cfg, dict):
            raise BuildError(f"'steps' must be a mapping in {BUILD_CONFIG}")

        requested_targets = resolve_requested_targets(args)
        if args.debug:
            env_data = get_env_data({"gtkwave"})
            run_debug_mode(env_data)
            return 0
        for target_name in requested_targets:
            if target_name not in targets_cfg:
                raise BuildError(f"target '{target_name}' is not defined")

        context = get_ip_data(args.ip)
        for target_name in requested_targets:
            target_cfg = targets_cfg[target_name]
            selector_cfg = target_cfg.get("selector")
            if selector_cfg is None:
                continue
            if not isinstance(selector_cfg, dict):
                raise BuildError(f"'selector' must be a mapping for target '{target_name}'")
            require_keys(selector_cfg, ["kind", "param"], f"targets.{target_name}.selector")
            arg_name = resolve_selector_argument_name(selector_cfg["param"])
            arg_value = getattr(args, arg_name)
            if arg_value != INTERACTIVE_SELECT:
                continue
            selected_name = prompt_for_named_entry(selector_cfg["kind"], (
                get_available_tests(context) if selector_cfg["kind"] == "test" else get_available_regressions(context)
            ))
            if selected_name is None:
                with PRINT_LOCK:
                    print(f"[done-pass {timestamp_text()}] {selector_cfg['kind']} selection canceled", flush=True)
                return 0
            setattr(args, arg_name, selected_name)
        fv_profile: dict | None = None
        if "fv" in requested_targets:
            require_keys(context, ["fv_profile", "fv_top", "fv_filelist"], f"ip.{context['ip']}")
            fv_profile = get_fv_profile(context["fv_profile"])
            context.update(fv_profile)
        required_tool_names = collect_required_tool_names(requested_targets, targets_cfg, context)

        env_data = get_env_data(required_tool_names)
        context.update(env_data)
        resolved_tag = resolve_tag(args.tag, context)
        args.tag = resolved_tag
        context = apply_run_paths(context, resolved_tag)
        if args.regress and isinstance(args.regress, str):
            context["regress_name"] = args.regress
        if "lint" in requested_targets:
            validate_lint_context(context)
        if "fv" in requested_targets:
            validate_fv_context(context, fv_profile)
        if "synth" in requested_targets:
            validate_synth_context(context)

        Path(context["compile_dir"]).mkdir(parents=True, exist_ok=True)

        workflow_subject = f"workflow {','.join(requested_targets)} ip={context['ip']} tag={context['tag']}"
        workflow_start = monotonic()
        resolved_command_text = build_resolved_command(args)
        print_command_banner(resolved_command_text, "resolved")
        print_status_line("wait", workflow_subject)
        print_status_line("start", workflow_subject)

        target_dependencies, target_closures = collect_target_dependencies(
            requested_targets,
            targets_cfg,
            steps_cfg,
        )
        target_contexts = {
            target_name: resolve_target_context(context, target_name, targets_cfg[target_name], args)
            for target_name in requested_targets
        }
        announced_steps: set[str] = set()
        for target_name in requested_targets:
            target_cfg = targets_cfg[target_name]
            target_context = target_contexts[target_name]
            root_steps = target_cfg.get("root_steps", [])
            if not isinstance(root_steps, list):
                raise BuildError(f"'root_steps' must be a list for target '{target_name}'")
            for step_name in root_steps:
                announce_step_tree(step_name, steps_cfg, target_context, announced_steps)
            if target_name == "regress":
                announce_regression_tests(target_context, target_context.get("selected_tests", []), steps_cfg)

        run_step("prepare", steps_cfg, context, set())
        target_futures: dict[str, concurrent.futures.Future[None]] = {}

        def execute_target(target_name: str) -> None:
            for dependency_target in sorted(target_dependencies[target_name]):
                target_futures[dependency_target].result()

            target_completed = {"prepare"}
            for dependency_target in target_dependencies[target_name]:
                target_completed.update(target_closures[dependency_target])

            target_cfg = targets_cfg[target_name]
            target_context = target_contexts[target_name]
            for step_name in target_cfg.get("root_steps", []):
                run_step(step_name, steps_cfg, target_context, target_completed)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(requested_targets)) as executor:
            for target_name in requested_targets:
                target_futures[target_name] = executor.submit(execute_target, target_name)
            for target_name in requested_targets:
                target_futures[target_name].result()
        print_status_line("done-pass", workflow_subject, duration=duration_text(workflow_start))
        print_review_files([context["ip_root"]])
        print_summary_line(f"targets={','.join(requested_targets)} tag={context['tag']} ip={context['ip']}")
        print_command_banner(resolved_command_text, "completed")
        return 0
    except BuildError as error:
        with PRINT_LOCK:
            prefix = status_prefix("done-fail")
            print(f"{prefix} workflow {error}", file=sys.stderr, flush=True)
            if resolved_command_text:
                banner = f"[command {timestamp_text()}] failed"
                if COLOR_ENABLED:
                    banner = colorize(banner, COLOR_COMMAND, bold=True)
                    command_text = colorize(resolved_command_text, COLOR_COMMAND)
                else:
                    command_text = resolved_command_text
                print(banner, file=sys.stderr, flush=True)
                print(f"  {command_text}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
