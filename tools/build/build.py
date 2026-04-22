#!/usr/bin/env python3
"""YAML-driven FPGA builder: Questa (vlog/vsim) + Intel Quartus. Windows + Git Bash only."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import shutil
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
INTERACTIVE_SELECT = "__interactive_select__"


def env_config_path() -> Path:
    override = os.environ.get("HW_OPENCLAW_ENV_FILE", "").strip()
    if override:
        candidate = Path(override)
        if not candidate.is_file():
            candidate = (REPO_ROOT / override).resolve()
        if candidate.is_file():
            return candidate.resolve()
    local = REPO_ROOT / "cfg" / "env.local.yaml"
    if local.is_file():
        return local.resolve()
    return (REPO_ROOT / "cfg" / "env.yaml").resolve()


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


def format_text(template: str, context: dict) -> str:
    return template.format(**context)


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
            "qa_out_dir",
            "qa_report",
            "lint_out_dir",
            "lint_log",
            "compile_dir",
            "compile_log",
            "test_out_dir",
            "test_log",
            "test_tracker",
            "test_wave",
            "regression_test_out_dir",
            "regression_test_log",
            "regression_test_tracker",
            "regression_test_wave",
            "quartus_out_dir",
            "quartus_log",
        ],
        "output_layout",
    )
    ip_cfg = ip_root["ip"]
    if not isinstance(ip_cfg, dict) or ip_name not in ip_cfg:
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
            "dv_top",
            "tb_top_module",
            "regression_dir",
            "test_dir",
        ],
        f"ip.{ip_name}",
    )
    ip_data["ip"] = ip_name
    ip_data["model_root_var"] = ip_root["model_root_var"]
    ip_data["output_layout"] = dict(output_layout)
    ip_data["top_module"] = ip_data["tb_top_module"]
    fpga_cfg = ip_data.get("fpga")
    if fpga_cfg is not None and not isinstance(fpga_cfg, dict):
        raise BuildError(f"ip.{ip_name}.fpga must be a mapping when present")
    f = dict(fpga_cfg or {})
    ip_data["fpga_family"] = str(f.get("family", "MAX 10"))
    ip_data["fpga_device"] = str(f.get("device", "10M50DAF484C7G"))
    ip_data["fpga_revision"] = str(f.get("revision", f"{ip_name}_fpga"))
    ip_data["fpga_top_entity"] = str(f.get("top_entity", ip_data["rtl_module"]))
    return ip_data


def apply_run_paths(ip_data: dict, tag: str) -> dict:
    layout = ip_data["output_layout"]
    ip_data["tag"] = tag
    ip_data["repo_root"] = str(REPO_ROOT)
    # Layout templates include test/regress paths; those keys are not set yet for
    # qa/lint/compile/fpga. Use placeholders so .format() succeeds; simulate
    # recomputes run_dir/log_file/wave via get_test_data().
    fmt = dict(ip_data)
    fmt.setdefault("test_name", "_")
    fmt.setdefault("regress_name", "_")
    for key in layout:
        ip_data[key] = resolve_path(format_text(layout[key], fmt))
    ip_data["run_dir"] = ip_data["compile_dir"]
    ip_data["log_file"] = ip_data["compile_log"]
    ip_data["tracker_path"] = ""
    return ip_data


def get_env_data(required_tool_names: set[str]) -> dict:
    env_path = env_config_path()
    env_root = load_yaml(env_path)
    require_keys(env_root, ["environment"], str(env_path))
    env = env_root["environment"]
    require_keys(env, ["home_dir", "model_root", "tools", "simulation"], "environment")
    tools = env["tools"]
    if not isinstance(tools, dict):
        raise BuildError(f"'tools' must be a mapping in {env_path}")
    tool_keys = {
        "python3": ["exe", "version", "version_cmd"],
        "vlib": ["exe", "version", "version_cmd"],
        "vlog": ["exe", "version", "version_cmd", "extra_flags"],
        "vsim": ["exe", "version", "version_cmd"],
        "quartus_map": ["exe", "version", "version_cmd"],
        "quartus_sh": ["exe", "version", "version_cmd"],
        "gtkwave": ["exe", "version", "version_cmd"],
    }
    for name in required_tool_names:
        if name not in tool_keys:
            raise BuildError(f"unsupported tool requirement '{name}'")
        if name not in tools:
            raise BuildError(f"missing '{name}' in environment.tools")
        cfg = tools[name]
        require_keys(cfg, tool_keys[name], f"environment.tools.{name}")

    simulation = env["simulation"]
    require_keys(simulation, ["waveform"], "environment.simulation")
    waveform = simulation["waveform"]
    require_keys(waveform, ["enabled", "format"], "environment.simulation.waveform")

    env_context = dict(env)
    env_context["repo_root"] = str(REPO_ROOT)
    env_context["host_home"] = os.environ.get("HOME", str(Path.home()))
    env_context["home_dir"] = resolve_template_text(str(env["home_dir"]), env_context)
    env_context["model_root"] = resolve_template_text(str(env["model_root"]), env_context)
    if isinstance(env.get("bin_dir"), str) and env["bin_dir"].strip():
        env_context["bin_dir"] = resolve_template_text(str(env["bin_dir"]), env_context)
    else:
        env_context["bin_dir"] = str(REPO_ROOT / "bin")

    out: dict = {
        "model_root": env_context["model_root"],
        "waveform_enabled": bool(waveform["enabled"]),
        "waveform_format": waveform["format"],
    }
    if "python3" in required_tool_names:
        out["python3_exe"] = resolve_template_text(str(tools["python3"]["exe"]), env_context)
    if "vlib" in required_tool_names:
        out["vlib_exe"] = resolve_template_text(str(tools["vlib"]["exe"]), env_context)
    if "vlog" in required_tool_names:
        out["vlog_exe"] = resolve_template_text(str(tools["vlog"]["exe"]), env_context)
        vxf = tools["vlog"].get("extra_flags", "+acc")
        if isinstance(vxf, list):
            out["vlog_extra_flags"] = [str(x) for x in vxf if str(x).strip()]
        else:
            out["vlog_extra_flags"] = [t for t in str(vxf).split() if t]
    if "vsim" in required_tool_names:
        out["vsim_exe"] = resolve_template_text(str(tools["vsim"]["exe"]), env_context)
    if "quartus_map" in required_tool_names:
        out["quartus_map_exe"] = resolve_template_text(str(tools["quartus_map"]["exe"]), env_context)
    if "quartus_sh" in required_tool_names:
        out["quartus_sh_exe"] = resolve_template_text(str(tools["quartus_sh"]["exe"]), env_context)
    if "gtkwave" in required_tool_names:
        out["gtkwave_exe"] = resolve_template_text(str(tools["gtkwave"]["exe"]), env_context)
    return out


def sh_path(path_text: str) -> str:
    return str(Path(path_text)).replace("\\", "/")


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
    prefix = color + (COLOR_BOLD if bold else "")
    return f"{prefix}{text}{COLOR_RESET}"


def status_prefix(kind: str) -> str:
    base = f"[{kind} {timestamp_text()}]"
    mapping = {"wait": COLOR_WAIT, "start": COLOR_START, "done-pass": COLOR_PASS, "done-fail": COLOR_FAIL}
    return colorize(base, mapping.get(kind, ""), bold=True) if kind in mapping else base


def print_status_line(kind: str, subject: str, *, duration: str | None = None) -> None:
    text = f"{status_prefix(kind)} {subject}"
    if duration:
        text += f" {duration}"
    with PRINT_LOCK:
        print(text, flush=True)


def display_path(path_text: str) -> str:
    try:
        return str(Path(path_text).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(Path(path_text).resolve())


def print_review_files(paths: list[str]) -> None:
    with PRINT_LOCK:
        for index, path_text in enumerate(paths[:3], start=1):
            print(f"  file{index}={display_path(path_text)}", flush=True)


def print_review_hint(paths: list[str]) -> None:
    if paths:
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
        inner = template[1:-1]
        value = lookup(context, inner)
        return format_text(value, context) if isinstance(value, str) else str(value)
    return format_text(template, context)


def render_condition(template: str, context: dict) -> bool:
    rendered = render_value(template, context).strip().lower()
    if rendered in {"1", "true", "yes", "on"}:
        return True
    if rendered in {"0", "false", "no", "off", ""}:
        return False
    raise BuildError(f"condition did not resolve to a boolean value: {template} -> {rendered}")


def render_paths(templates: list, context: dict) -> list[str]:
    paths: list[str] = []
    for template in templates:
        path_template = template
        if isinstance(template, dict):
            require_keys(template, ["path"], "review_files entry")
            when_text = template.get("when", "true")
            if not isinstance(when_text, str):
                raise BuildError("'when' must be a string in review_files entry")
            if not render_condition(when_text, context):
                continue
            path_template = template["path"]
        if not isinstance(path_template, str):
            raise BuildError("review_files entries must be strings or mappings")
        rendered = render_value(path_template, context)
        if rendered:
            paths.append(rendered)
    return paths


def get_step_review_files(step_name: str, steps_cfg: dict, context: dict) -> list[str]:
    step_cfg = steps_cfg.get(step_name, {})
    rf = step_cfg.get("review_files", [])
    if not isinstance(rf, list):
        raise BuildError(f"'review_files' must be a list for step '{step_name}'")
    return render_paths(rf, context)


def get_step_display_name(step_name: str, steps_cfg: dict, context: dict) -> str:
    step_cfg = steps_cfg.get(step_name, {})
    dn = step_cfg.get("display_name")
    if isinstance(dn, str) and dn:
        return render_value(dn, context)
    return f"{step_name} {context['ip']}"


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
    deps = step_cfg.get("depends_on", step_cfg.get("deps", []))
    if not isinstance(deps, list):
        raise BuildError(f"'depends_on' must be a list for step '{step_name}'")
    return list(deps)


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
    for dep in get_step_dependencies(step_name, steps_cfg):
        closure.update(collect_step_closure(dep, steps_cfg, memo, active))
    active.remove(step_name)
    memo[step_name] = closure
    return closure


def collect_target_step_closure(
    target_name: str, targets_cfg: dict, steps_cfg: dict, memo: dict[str, set[str]]
) -> set[str]:
    closure: set[str] = set()
    for step_name in targets_cfg[target_name].get("root_steps", []):
        closure.update(collect_step_closure(step_name, steps_cfg, memo))
    return closure


def collect_target_dependencies(
    requested_targets: list[str], targets_cfg: dict, steps_cfg: dict
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    step_to_target: dict[str, str] = {}
    for tname, tcfg in targets_cfg.items():
        for sname in tcfg.get("root_steps", []):
            if sname in step_to_target and step_to_target[sname] != tname:
                raise BuildError(f"step '{sname}' is assigned to multiple targets")
            step_to_target[sname] = tname
    memo: dict[str, set[str]] = {}
    target_closures = {t: collect_target_step_closure(t, targets_cfg, steps_cfg, memo) for t in requested_targets}
    requested_set = set(requested_targets)
    target_dependencies: dict[str, set[str]] = {}
    for tname in requested_targets:
        deps: set[str] = set()
        for sname in targets_cfg[tname].get("root_steps", []):
            for dstep in collect_step_closure(sname, steps_cfg, memo):
                dt = step_to_target.get(dstep)
                if dt and dt != tname and dt in requested_set:
                    deps.add(dt)
        target_dependencies[tname] = deps
    # When FPGA and simulation are both requested, run Quartus only after vsim/review.
    rs = set(requested_targets)
    if "fpga" in rs:
        if "test" in rs:
            target_dependencies["fpga"].add("test")
        if "regress" in rs:
            target_dependencies["fpga"].add("regress")
    return target_dependencies, target_closures


def resolve_filelist_entry(entry: str, context: dict) -> str:
    replaced = entry.replace(context["model_root_var"], context["repo_root"])
    return str(Path(replaced).resolve())


def expand_filelist(source_path: Path, context: dict) -> list[str]:
    lines_out: list[str] = []
    for raw_line in source_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-F"):
            nested_path = Path(resolve_filelist_entry(line[2:].strip(), context))
            lines_out.extend(expand_filelist(nested_path, context))
            continue
        if line.startswith("+incdir+"):
            inc = line[len("+incdir+") :].strip()
            lines_out.append("+incdir+" + resolve_filelist_entry(inc, context))
            continue
        lines_out.append(resolve_filelist_entry(line, context))
    return lines_out


def write_generated_filelist(source_file: str, destination_file: str, context: dict) -> None:
    source_path = REPO_ROOT / source_file
    if not source_path.is_file():
        raise BuildError(f"missing source filelist: {source_path}")
    dest = Path(destination_file)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(expand_filelist(source_path, context)) + "\n", encoding="utf-8")


def prepare_filelists(context: dict) -> None:
    Path(context["filelist_dir"]).mkdir(parents=True, exist_ok=True)
    write_generated_filelist(context["rtl_filelist"], context["generated_rtl_filelist"], context)
    write_generated_filelist(context["dv_filelist"], context["generated_dv_filelist"], context)
    write_generated_filelist(context["all_filelist"], context["generated_all_filelist"], context)


def fpga_include_and_sources_from_rtl_filelist(context: dict) -> tuple[list[str], list[str]]:
    fl = Path(context["generated_rtl_filelist"])
    if not fl.is_file():
        raise BuildError(f"missing generated RTL filelist: {fl}")
    incs: list[str] = []
    srcs: list[str] = []
    for raw in (ln.strip() for ln in fl.read_text(encoding="utf-8").splitlines()):
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("+incdir+"):
            incs.append(Path(raw[len("+incdir+") :].strip()).resolve().as_posix())
            continue
        p = Path(raw).resolve()
        if p.is_file() and p.suffix.lower() in {".sv", ".svh", ".v", ".vh"}:
            srcs.append(p.as_posix())
    if not srcs:
        raise BuildError("no RTL source files found for FPGA (expected .sv/.v in generated RTL filelist)")
    return incs, srcs


def tcl_braced_path(path_posix: str) -> str:
    escaped = path_posix.replace("{", "\\{").replace("}", "\\}")
    return "{" + escaped + "}"


def write_quartus_tcl_action(context: dict) -> None:
    """Emit synth_hw.tcl (Quartus Tcl): project, assignments from RTL filelist, execute_flow -compile."""
    qdir = Path(context["quartus_out_dir"])
    qdir.mkdir(parents=True, exist_ok=True)
    incs, srcs = fpga_include_and_sources_from_rtl_filelist(context)
    rev = context["fpga_revision"]
    top = context["fpga_top_entity"]
    fam = context["fpga_family"].replace('"', "").strip()
    dev = context["fpga_device"].replace('"', "").strip()
    lines: list[str] = [
        "# Auto-generated by HW-OpenClaw tools/build/build.py",
        f"# IP={context['ip']} revision={rev} top={top}",
        "load_package flow",
        "package require ::quartus::project",
        "set script_dir [file normalize [file dirname [info script]]]",
        "cd $script_dir",
        f"set PROJECT_NAME {{{rev}}}",
        "set search_paths [list]",
        "set hdl_files [list]",
    ]
    for p in incs:
        lines.append(f"lappend search_paths {tcl_braced_path(p)}")
    for p in srcs:
        lines.append(f"lappend hdl_files {tcl_braced_path(p)}")
    lines.extend(
        [
            "if {[llength $search_paths] == 0} {",
            "  lappend search_paths $script_dir",
            "}",
            "if {[catch {project_new $PROJECT_NAME -revision $PROJECT_NAME -overwrite} err]} {",
            "  post_message -type error \"project_new failed: $err\"",
            "  exit 2",
            "}",
            f"set_global_assignment -name FAMILY {{{fam}}}",
            f"set_global_assignment -name DEVICE {dev}",
            f"set_global_assignment -name TOP_LEVEL_ENTITY {top}",
            "set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files",
            "foreach p $search_paths {",
            "  set_global_assignment -name SEARCH_PATH $p",
            "}",
            "foreach f $hdl_files {",
            "  set_global_assignment -name SYSTEMVERILOG_FILE $f",
            "}",
            "if {[catch {execute_flow -compile} err]} {",
            "  post_message -type error \"execute_flow -compile failed: $err\"",
            "  project_close",
            "  exit 1",
            "}",
            "project_close",
        ]
    )
    (qdir / "synth_hw.tcl").write_text("\n".join(lines) + "\n", encoding="utf-8")


QUARTUS_LOG_TRIAGE_PATTERN = re.compile(
    r"(?i)(\*\*\s*error|\berror\s*\(|^error:|\bfatal\b|\bsevere\b|unsuccessful|segmentation fault)"
)


def print_quartus_failure_triage(context: dict, *, max_log_lines: int = 28) -> None:
    """Print one-line report pointers and grep-friendly excerpts from quartus.log (stderr)."""
    rev = str(context.get("fpga_revision", "project"))
    qroot = Path(context["quartus_out_dir"]).resolve()
    outf = qroot / "output_files"
    log_p = Path(context["quartus_log"]).resolve()

    report_paths: list[str] = []
    if outf.is_dir():
        for suffix in ("fit", "sta", "map", "flow"):
            p = (outf / f"{rev}.{suffix}.rpt").resolve()
            if p.is_file():
                report_paths.append(str(p))
        if not report_paths:
            for p in sorted(outf.glob("*.fit.rpt"))[:2]:
                report_paths.append(str(p.resolve()))
            for p in sorted(outf.glob("*.sta.rpt"))[:2]:
                if str(p.resolve()) not in report_paths:
                    report_paths.append(str(p.resolve()))

    shown = " ".join(display_path(p) for p in report_paths) if report_paths else f"(no rpt yet under {display_path(str(outf))})"
    log_disp = display_path(str(log_p))
    with PRINT_LOCK:
        print(f"[quartus-triage] primary_reports={shown}", file=sys.stderr, flush=True)
        print(
            f'[quartus-triage] log_grep: rg -n "\\*\\* Error|Error:|ERROR:|FATAL|unsuccessful" {log_disp}',
            file=sys.stderr,
            flush=True,
        )

    hits: list[str] = []
    if log_p.is_file():
        for line in log_p.read_text(encoding="utf-8", errors="replace").splitlines():
            if QUARTUS_LOG_TRIAGE_PATTERN.search(line):
                hits.append(line.rstrip()[:400])
                if len(hits) >= max_log_lines:
                    break
    with PRINT_LOCK:
        print(f"[quartus-triage] first_{max_log_lines}_matching_lines_from_quartus.log:", file=sys.stderr, flush=True)
        if hits:
            for h in hits:
                print(f"  {h}", file=sys.stderr, flush=True)
        else:
            print(
                f"  (no lines matched triage pattern; read full log: {log_disp})",
                file=sys.stderr,
                flush=True,
            )


def run_quartus_sh_compile_action(context: dict) -> None:
    qdir = Path(context["quartus_out_dir"])
    tcl = qdir / "synth_hw.tcl"
    if not tcl.is_file():
        raise BuildError(f"missing {tcl}; run write_quartus_tcl first")
    argv = [context["quartus_sh_exe"], "-t", tcl.name]
    try:
        run_subprocess_logged(argv, cwd=qdir, log_path=Path(context["quartus_log"]))
    except BuildError:
        print_quartus_failure_triage(context)
        raise


def test_phase_vlog_action(context: dict) -> None:
    """Per-test vlog into existing compile work library (after compile target). Logs to test run_dir."""
    run_dir = Path(context["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    vlog_log = run_dir / "vlog.log"
    comp = Path(context["compile_dir"])
    print_summary_line(f"phase=vlog ip={context['ip']} test={context.get('test_name', '')}")
    argv = [
        context["vlog_exe"],
        "-sv",
        "-work",
        "work",
        *context["vlog_extra_flags"],
        "-f",
        context["generated_all_filelist"],
    ]
    result = subprocess.run(argv, cwd=str(comp), text=True, capture_output=True)
    text = (result.stdout or "") + (result.stderr or "")
    vlog_log.write_text(text, encoding="utf-8")
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="", file=sys.stderr)
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        raise BuildError(f"vlog (test phase) failed with exit code {result.returncode}")


def review_test_outputs_action(context: dict) -> None:
    """Print paths and short tails of vlog/sim logs (after vsim, before any Quartus work)."""
    run_dir = Path(context["run_dir"])
    vlog_log = run_dir / "vlog.log"
    sim_log = Path(context["log_file"])
    wave = Path(context.get("wave_path", ""))
    tracker = Path(context.get("tracker_path", ""))

    def tail_text(path: Path, n: int) -> str:
        if not path.is_file():
            return f"(missing {path.name})"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        body = "\n".join(lines[-n:]) if lines else "(empty)"
        return body

    # Do not wrap in PRINT_LOCK: print_summary_line acquires the same non-reentrant Lock.
    print_summary_line(
        f"review ip={context['ip']} test={context.get('test_name', '')} "
        f"vlog_log={display_path(str(vlog_log))} sim_log={display_path(str(sim_log))}"
    )
    if wave.name:
        print_summary_line(f"waveform={display_path(str(wave))}")
    if tracker.name:
        print_summary_line(f"tracker={display_path(str(tracker))}")
    with PRINT_LOCK:
        print("--- vlog.log (tail) ---", flush=True)
        print(tail_text(vlog_log, 25), flush=True)
        print("--- simulate.log (tail) ---", flush=True)
        print(tail_text(sim_log, 40), flush=True)


def _append_process_output(result: subprocess.CompletedProcess[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        if result.stdout:
            handle.write(result.stdout)
        if result.stderr:
            handle.write(result.stderr)


def run_subprocess_logged(argv: list[str], *, cwd: Path, log_path: Path) -> None:
    """Run subprocess with stdout+stderr streamed to log (avoids pipe buffer stalls on verbose tools)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            argv,
            cwd=str(cwd),
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    if result.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
        if tail.strip():
            print(tail, end="", file=sys.stderr)
        raise BuildError(f"command failed with exit code {result.returncode}")


def compile_sim_action(context: dict) -> None:
    comp = Path(context["compile_dir"])
    comp.mkdir(parents=True, exist_ok=True)
    log_path = Path(context["log_file"])
    work = comp / "work"
    if work.exists():
        shutil.rmtree(work)
    log_path.write_text("", encoding="utf-8")
    r1 = subprocess.run(
        [context["vlib_exe"], "work"],
        cwd=str(comp),
        text=True,
        capture_output=True,
    )
    _append_process_output(r1, log_path)
    if r1.returncode != 0:
        raise BuildError(f"vlib failed with exit code {r1.returncode}")
    argv = [
        context["vlog_exe"],
        "-sv",
        "-work",
        "work",
        *context["vlog_extra_flags"],
        "-f",
        context["generated_all_filelist"],
    ]
    r2 = subprocess.run(argv, cwd=str(comp), text=True, capture_output=True)
    _append_process_output(r2, log_path)
    if r2.returncode != 0:
        if r2.stdout:
            print(r2.stdout, end="", file=sys.stderr)
        if r2.stderr:
            print(r2.stderr, end="", file=sys.stderr)
        raise BuildError(f"vlog failed with exit code {r2.returncode}")


def lint_sim_action(context: dict) -> None:
    lint_dir = Path(context["lint_out_dir"])
    lint_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(context["lint_log"])
    work = lint_dir / "work"
    if work.exists():
        shutil.rmtree(work)
    log_path.write_text("", encoding="utf-8")
    r1 = subprocess.run(
        [context["vlib_exe"], "work"],
        cwd=str(lint_dir),
        text=True,
        capture_output=True,
    )
    _append_process_output(r1, log_path)
    if r1.returncode != 0:
        raise BuildError(f"vlib (lint) failed with exit code {r1.returncode}")
    argv = [
        context["vlog_exe"],
        "-lint",
        "-sv",
        "-work",
        "work",
        "-f",
        context["generated_rtl_filelist"],
    ]
    r2 = subprocess.run(argv, cwd=str(lint_dir), text=True, capture_output=True)
    _append_process_output(r2, log_path)
    if r2.returncode != 0:
        if r2.stdout:
            print(r2.stdout, end="", file=sys.stderr)
        if r2.stderr:
            print(r2.stderr, end="", file=sys.stderr)
        raise BuildError(f"vlog -lint failed with exit code {r2.returncode}")


def simulate_sim_action(context: dict) -> None:
    Path(context["run_dir"]).mkdir(parents=True, exist_ok=True)
    log_path = Path(context["log_file"])
    argv = [
        context["vsim_exe"],
        "-c",
        "-work",
        "work",
        context["tb_top_module"],
        "-do",
        "run -all; quit",
        f"+test={context['test_name']}",
        f"+tracker_path={sh_path(context['tracker_path'])}",
        f"+wave_enable={context['wave_enable']}",
        f"+wave_path={sh_path(context['wave_path'])}",
    ]
    run_subprocess_logged(argv, cwd=Path(context["compile_dir"]), log_path=log_path)


def run_regression(
    _step_cfg: dict, base_context: dict, tests: list[str], steps_cfg: dict
) -> None:
    if not tests:
        print_summary_line("tests=0 passed=0 failed=0")
        return
    simulate_step_cfg = steps_cfg["simulate"]
    failed: list[str] = []
    passed = 0
    errors: list[str] = []
    for test_name in tests:
        test_context = get_test_data(dict(base_context), test_name, "regress")
        subj = get_step_display_name("simulate", steps_cfg, test_context)
        test_context["status_subject"] = subj
        t0 = monotonic()
        print_status_line("start", subj)
        try:
            for command in simulate_step_cfg.get("commands", []):
                run_command(command, test_context, steps_cfg)
        except BuildError as err:
            errors.append(str(err))
            failed.append(test_name)
            print_status_line("done-fail", subj, duration=duration_text(t0))
            print_review_files(get_step_review_files("simulate", steps_cfg, test_context))
            print_review_hint(get_step_review_files("simulate", steps_cfg, test_context))
            continue
        passed += 1
        print_status_line("done-pass", subj, duration=duration_text(t0))
        print_review_files(get_step_review_files("simulate", steps_cfg, test_context))
    if errors:
        print_summary_line(f"tests={len(tests)} passed={passed} failed={len(failed)} failed_names={','.join(failed)}")
        for msg in errors:
            print(msg, file=sys.stderr)
        raise BuildError("regression failed")
    print_summary_line(f"tests={len(tests)} passed={passed} failed=0")


def run_command(command: str | dict, context: dict, steps_cfg: dict) -> None:
    if isinstance(command, dict) and command.get("action") == "ensure_dir":
        path_t = command.get("path")
        if not isinstance(path_t, str):
            raise BuildError("ensure_dir requires string 'path'")
        Path(render_value(path_t, context)).mkdir(parents=True, exist_ok=True)
        return
    if isinstance(command, dict) and command.get("action") == "run_qa":
        run_qa_checks(context)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_filelists":
        prepare_filelists(context)
        return
    if isinstance(command, dict) and command.get("action") == "compile_sim":
        compile_sim_action(context)
        return
    if isinstance(command, dict) and command.get("action") == "lint_sim":
        lint_sim_action(context)
        return
    if isinstance(command, dict) and command.get("action") == "test_phase_vlog":
        test_phase_vlog_action(context)
        return
    if isinstance(command, dict) and command.get("action") == "review_test_outputs":
        review_test_outputs_action(context)
        return
    if isinstance(command, dict) and command.get("action") == "simulate_sim":
        simulate_sim_action(context)
        return
    if isinstance(command, dict) and command.get("action") == "write_quartus_tcl":
        write_quartus_tcl_action(context)
        return
    if isinstance(command, dict) and command.get("action") == "run_quartus_sh_compile":
        run_quartus_sh_compile_action(context)
        return
    if isinstance(command, dict) and command.get("action") == "run_regression":
        run_regression(steps_cfg["regress"], context, context.get("selected_tests", []), steps_cfg)
        return

    command_text, log_name = normalize_command(command)
    formatted = format_text(command_text, context)
    result = subprocess.run(formatted, shell=True, cwd=REPO_ROOT, text=True, capture_output=True)
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


def run_step(step_name: str, steps_cfg: dict, context: dict, completed: set[str]) -> None:
    if step_name in completed:
        return
    if step_name not in steps_cfg:
        raise BuildError(f"unknown build step '{step_name}'")
    step_cfg = steps_cfg[step_name]
    subject = get_step_display_name(step_name, steps_cfg, context)
    for dep in get_step_dependencies(step_name, steps_cfg):
        run_step(dep, steps_cfg, context, completed)
    t0 = monotonic()
    print_status_line("start", subject)
    try:
        for cmd in step_cfg.get("commands", []):
            run_command(cmd, context, steps_cfg)
    except BuildError:
        print_status_line("done-fail", subject, duration=duration_text(t0))
        print_review_files(get_step_review_files(step_name, steps_cfg, context))
        print_review_hint(get_step_review_files(step_name, steps_cfg, context))
        raise
    print_status_line("done-pass", subject, duration=duration_text(t0))
    print_review_files(get_step_review_files(step_name, steps_cfg, context))
    completed.add(step_name)


def collect_required_tool_names(requested_targets: list[str], targets_cfg: dict, context: dict) -> set[str]:
    required: set[str] = set()
    for target_name in requested_targets:
        if target_name == "debug":
            required.add("gtkwave")
            continue
        tcfg = targets_cfg[target_name]
        for req in tcfg.get("tool_requirements", []):
            if isinstance(req, str):
                required.add(format_text(req, context))
                continue
            if not isinstance(req, dict):
                raise BuildError(f"invalid tool_requirements entry for target '{target_name}'")
            require_keys(req, ["name"], f"targets.{target_name}.tool_requirements")
            when = req.get("when", "true")
            if not isinstance(when, str):
                raise BuildError("'when' must be a string")
            if not render_condition(when, context):
                continue
            required.add(format_text(req["name"], context))
    return required


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FPGA build: Questa + Quartus (Windows + Git Bash)")
    p.add_argument("-ip", help="IP name")
    p.add_argument("-tag", help="run tag for workdir")
    p.add_argument("-qa", action="store_true", help="structural QA for one IP")
    p.add_argument("-lint", action="store_true", help="Questa vlog -lint on RTL filelist")
    p.add_argument("-compile", action="store_true", help="Questa vlib + vlog compile")
    p.add_argument("-test", nargs="?", const=INTERACTIVE_SELECT, help="run one DV test (vsim)")
    p.add_argument("-regress", nargs="?", const=INTERACTIVE_SELECT, help="run regression (vsim)")
    p.add_argument("-fpga", action="store_true", help="Quartus smoke (quartus_map --version)")
    p.add_argument("-debug", action="store_true", help="open last VCD in GTKWave")
    args = p.parse_args()
    modes = sum(
        [
            bool(args.qa),
            bool(args.lint),
            bool(args.compile),
            bool(args.test),
            bool(args.regress),
            bool(args.fpga),
            bool(args.debug),
        ]
    )
    if args.debug and modes != 1:
        raise BuildError("'-debug' must be used by itself")
    if args.test and args.regress:
        raise BuildError("select only one of '-test' or '-regress'")
    return args


def resolve_requested_targets(args: argparse.Namespace) -> list[str]:
    targets: list[str] = []
    if args.debug:
        return ["debug"]
    if args.qa:
        targets.append("qa")
    if args.lint:
        targets.append("lint")
    if args.compile:
        targets.append("compile")
    if args.test:
        targets.append("test")
    if args.regress:
        targets.append("regress")
    if args.fpga:
        targets.append("fpga")
    return targets


def build_resolved_command(args: argparse.Namespace) -> str:
    parts = ["./build"]
    if args.ip:
        parts.extend(["-ip", args.ip])
    if args.tag:
        parts.extend(["-tag", args.tag])
    if args.qa:
        parts.append("-qa")
    if args.lint:
        parts.append("-lint")
    if args.compile:
        parts.append("-compile")
    if args.fpga:
        parts.append("-fpga")
    if args.debug:
        parts.append("-debug")
    if args.test and isinstance(args.test, str):
        parts.extend(["-test", args.test])
    if args.regress and isinstance(args.regress, str):
        parts.extend(["-regress", args.regress])
    return " ".join(parts)


def get_available_ips() -> list[str]:
    ip_root = load_yaml(IP_CONFIG)
    return sorted(ip_root["ip"].keys())


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


def prompt_for_named_entry(kind: str, names: list[str]) -> str | None:
    if not names:
        raise BuildError(f"no {kind}s are defined")
    with PRINT_LOCK:
        print(f"available {kind}s:", flush=True)
        for i, name in enumerate(names, start=1):
            print(f"  [{i}] {name}", flush=True)
    while True:
        sel = input(f"select {kind} number (0/q to cancel): ").strip()
        if sel in {"0", "q", "Q", ""}:
            return None
        if not sel.isdigit():
            continue
        idx = int(sel)
        if 1 <= idx <= len(names):
            return names[idx - 1]


def prompt_for_modes() -> list[str] | None:
    items = [
        ("qa", "-qa"),
        ("lint", "-lint"),
        ("compile", "-compile"),
        ("test", "-test"),
        ("regress", "-regress"),
        ("fpga", "-fpga"),
        ("debug", "-debug"),
    ]
    with PRINT_LOCK:
        print("available modes:", flush=True)
        for i, (name, flag) in enumerate(items, start=1):
            print(f"  [{i}] {name} ({flag})", flush=True)
    while True:
        sel = input("select mode numbers (comma-separated, 0/q to cancel): ").strip()
        if sel in {"0", "q", "Q", ""}:
            return None
        parts = [p.strip() for p in sel.split(",") if p.strip()]
        if not parts or not all(p.isdigit() for p in parts):
            continue
        idxs = [int(p) for p in parts]
        if any(i < 1 or i > len(items) for i in idxs):
            continue
        chosen = [items[i - 1][0] for i in idxs]
        if "debug" in chosen and len(set(chosen)) != 1:
            print("debug must be selected by itself", flush=True)
            continue
        if "test" in chosen and "regress" in chosen:
            print("select only one of test or regress", flush=True)
            continue
        return chosen


def apply_selected_modes(args: argparse.Namespace, modes: list[str]) -> None:
    args.qa = "qa" in modes
    args.lint = "lint" in modes
    args.compile = "compile" in modes
    args.fpga = "fpga" in modes
    args.debug = "debug" in modes
    if "test" in modes and not args.test:
        args.test = INTERACTIVE_SELECT
    if "regress" in modes and not args.regress:
        args.regress = INTERACTIVE_SELECT


def get_requested_mode_names(args: argparse.Namespace) -> list[str]:
    return resolve_requested_targets(args)


def get_test_data(ip_data: dict, test_name: str, mode: str) -> dict:
    test_file = REPO_ROOT / ip_data["test_dir"] / f"{test_name}.yaml"
    if not test_file.is_file():
        raise BuildError(f"unknown test '{test_name}' for ip '{ip_data['ip']}'")
    test_data = load_yaml(test_file)
    require_keys(test_data, ["test"], str(test_file))
    if test_data["test"]["name"] != test_name:
        raise BuildError(f"test file name mismatch for '{test_name}'")
    ip_data["test_name"] = test_name
    layout = ip_data["output_layout"]
    if mode == "test":
        ip_data["run_dir"] = resolve_path(format_text(layout["test_out_dir"], ip_data))
        ip_data["log_file"] = resolve_path(format_text(layout["test_log"], ip_data))
        ip_data["tracker_path"] = resolve_path(format_text(layout["test_tracker"], ip_data))
        ip_data["wave_path"] = resolve_path(format_text(layout["test_wave"], ip_data))
    else:
        ip_data["run_dir"] = resolve_path(format_text(layout["regression_test_out_dir"], ip_data))
        ip_data["log_file"] = resolve_path(format_text(layout["regression_test_log"], ip_data))
        ip_data["tracker_path"] = resolve_path(format_text(layout["regression_test_tracker"], ip_data))
        ip_data["wave_path"] = resolve_path(format_text(layout["regression_test_wave"], ip_data))
    ip_data["wave_enable"] = 1 if ip_data.get("waveform_enabled") else 0
    return ip_data


def get_regression_tests(ip_data: dict, regression_name: str) -> list[str]:
    reg_file = REPO_ROOT / ip_data["regression_dir"] / f"{regression_name}.yaml"
    if not reg_file.is_file():
        raise BuildError(f"unknown regression '{regression_name}'")
    reg_data = load_yaml(reg_file)
    require_keys(reg_data, ["regression"], str(reg_file))
    reg = reg_data["regression"]
    if reg["name"] != regression_name:
        raise BuildError("regression name mismatch")
    tests = reg["tests"]
    if not isinstance(tests, list):
        raise BuildError("'tests' must be a list")
    ip_data["regress_name"] = regression_name
    for t in tests:
        get_test_data(dict(ip_data), t, "regress")
    return list(tests)


def resolve_selector_argument_name(param: str) -> str:
    m = {"test_name": "test", "regress_name": "regress"}
    if param not in m:
        raise BuildError(f"unsupported selector param '{param}'")
    return m[param]


def resolve_target_context(
    base: dict, target_name: str, target_cfg: dict, args: argparse.Namespace
) -> dict:
    ctx = dict(base)
    sel = target_cfg.get("selector")
    if sel:
        require_keys(sel, ["kind", "param"], f"targets.{target_name}.selector")
        argn = resolve_selector_argument_name(sel["param"])
        val = getattr(args, argn)
        if not isinstance(val, str) or not val:
            raise BuildError(f"missing selector value for target '{target_name}'")
        if sel["kind"] == "test":
            ctx = get_test_data(ctx, val, "test")
        elif sel["kind"] == "regression":
            ctx["regress_name"] = val
            ctx["selected_tests"] = get_regression_tests(dict(ctx), val)
        else:
            raise BuildError(f"unsupported selector kind '{sel['kind']}'")
    tctx = target_cfg.get("context", {})
    if tctx:
        for k, v in tctx.items():
            ctx[k] = render_value(str(v), ctx)
    return ctx


def validate_filelist_tree(filelist_path: Path, visited: set[Path]) -> None:
    resolved = filelist_path.resolve()
    if resolved in visited:
        return
    visited.add(resolved)
    if not resolved.is_file():
        raise BuildError(f"missing filelist: {resolved}")
    for num, raw in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("+incdir+"):
            p = Path(line[len("+incdir+") :].strip().replace("$MODEL_ROOT", str(REPO_ROOT)))
            if not p.is_dir():
                raise BuildError(f"missing include dir {resolved}:{num}: {p}")
            continue
        if line.startswith("-F "):
            validate_filelist_tree(Path(line[3:].strip().replace("$MODEL_ROOT", str(REPO_ROOT))), visited)
            continue
        src = Path(line.replace("$MODEL_ROOT", str(REPO_ROOT)))
        if not src.is_file():
            raise BuildError(f"missing source {resolved}:{num}: {src}")


def collect_filelist_sources(filelist_path: Path, visited: set[Path], sources: set[Path]) -> None:
    resolved = filelist_path.resolve()
    if resolved in visited:
        return
    visited.add(resolved)
    for raw in resolved.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("+incdir+"):
            continue
        if line.startswith("-F "):
            collect_filelist_sources(Path(line[3:].strip().replace("$MODEL_ROOT", str(REPO_ROOT))), visited, sources)
            continue
        sources.add(Path(line.replace("$MODEL_ROOT", str(REPO_ROOT))).resolve())


def validate_exists(path_text: str, kind: str) -> None:
    path = (REPO_ROOT / path_text).resolve()
    if kind == "file" and not path.is_file():
        raise BuildError(f"missing file: {path}")
    if kind == "dir" and not path.is_dir():
        raise BuildError(f"missing directory: {path}")


def iter_sv_sources(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in {".sv", ".svh"})


ALWAYS_PATTERN = re.compile(r"(?<![\w$])always(?!_(?:comb|ff|latch)\b)")
INLINE_LOGIC_INIT_PATTERN = re.compile(r"^\s*logic\b[^;]*=")
NONBLOCKING_ASSIGN_PATTERN = re.compile(
    r"^\s*[A-Za-z_][\w$]*(?:\s*\[[^]]+\])?(?:\s*\.[A-Za-z_][\w$]*(?:\s*\[[^]]+\])?)*\s*<=\s*.+;"
)


def strip_line_comments(line: str, in_block: bool) -> tuple[str, bool]:
    cleaned: list[str] = []
    i = 0
    while i < len(line):
        if in_block:
            j = line.find("*/", i)
            if j == -1:
                return "".join(cleaned), True
            i = j + 2
            in_block = False
            continue
        if line.startswith("/*", i):
            in_block = True
            i += 2
            continue
        if line.startswith("//", i):
            break
        cleaned.append(line[i])
        i += 1
    return "".join(cleaned), in_block


def validate_style_file(path: Path) -> list[str]:
    violations: list[str] = []
    allow_nb = path.name == "macros.svh"
    in_block = False
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line, in_block = strip_line_comments(raw, in_block)
        if not line.strip():
            continue
        if ALWAYS_PATTERN.search(line):
            violations.append(f"{path.relative_to(REPO_ROOT)}:{n}: plain 'always' is not allowed")
        if INLINE_LOGIC_INIT_PATTERN.search(line):
            violations.append(f"{path.relative_to(REPO_ROOT)}:{n}: inline logic init not allowed")
        if not allow_nb and NONBLOCKING_ASSIGN_PATTERN.search(line):
            violations.append(f"{path.relative_to(REPO_ROOT)}:{n}: explicit <= not allowed")
    if path.name != path.name.lower():
        violations.append(f"{path.relative_to(REPO_ROOT)}: file name must be lowercase")
    return violations


def collect_validation_style_files(context: dict) -> list[Path]:
    files: set[Path] = set()
    rtl_src: set[Path] = set()
    collect_filelist_sources((REPO_ROOT / context["rtl_filelist"]).resolve(), set(), rtl_src)
    files.update(rtl_src)
    dv_root = REPO_ROOT / f"src/dv/{context['ip']}/code"
    if dv_root.is_dir():
        files.update(iter_sv_sources(dv_root.resolve()))
    inc = REPO_ROOT / "src/rtl/common/include"
    if inc.is_dir():
        files.update(iter_sv_sources(inc.resolve()))
    return sorted(files)


def write_validation_report(context: dict, checked: list[Path], violations: list[str]) -> None:
    report = Path(context["qa_report"])
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"ip: {context['ip']}",
        f"checked_files: {len(checked)}",
        f"violations: {len(violations)}",
        "",
        "checked:",
    ]
    lines.extend(f"- {p.relative_to(REPO_ROOT)}" for p in checked)
    lines.append("")
    lines.append("violations:")
    if violations:
        lines.extend(f"- {v}" for v in violations)
    else:
        lines.append("- none")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_qa_checks(context: dict) -> None:
    require_keys(
        context,
        [
            "rtl_filelist",
            "rtl_module",
            "dv_filelist",
            "all_filelist",
            "rtl_top",
            "lint_dir",
            "dv_top",
            "tb_top_module",
            "regression_dir",
            "test_dir",
            "qa_report",
        ],
        f"ip.{context['ip']}",
    )
    required_dirs = [
        f"src/rtl/{context['ip']}/code",
        f"src/rtl/{context['ip']}/lint",
        f"src/dv/{context['ip']}/code/if",
        f"src/dv/{context['ip']}/code/pkg",
        f"src/dv/{context['ip']}/code/env",
        f"src/dv/{context['ip']}/code/tb",
        f"src/dv/{context['ip']}/code/tests",
        f"src/dv/{context['ip']}/filelist",
        f"src/dv/{context['ip']}/regressions",
    ]
    required_files = [
        context["rtl_filelist"],
        context["dv_filelist"],
        context["all_filelist"],
        context["rtl_top"],
        f"wiki/rtl/{context['ip']}/rtl-{context['ip']}.md",
        f"wiki/dv/{context['ip']}/dv-{context['ip']}.md",
        "wiki/rtl/rtl.md",
        "wiki/dv/dv.md",
        "wiki/Home.md",
        "wiki/flows-methods-phylosophy/repo-structure.md",
        "wiki/flows-methods-phylosophy/builder-methodology.md",
        "wiki/flows-methods-phylosophy/software-stack.md",
        "wiki/flows-methods-phylosophy/fpga-quartus-methodology.md",
    ]
    for d in required_dirs:
        validate_exists(d, "dir")
    for f in required_files:
        validate_exists(f, "file")
    validate_filelist_tree((REPO_ROOT / context["rtl_filelist"]).resolve(), set())
    validate_filelist_tree((REPO_ROOT / context["dv_filelist"]).resolve(), set())
    validate_filelist_tree((REPO_ROOT / context["all_filelist"]).resolve(), set())
    checked = collect_validation_style_files(context)
    violations: list[str] = []
    for path in checked:
        violations.extend(validate_style_file(path))
    write_validation_report(context, checked, violations)
    if violations:
        raise BuildError(f"qa failed with {len(violations)} violation(s)")


def discover_debug_entries() -> list[dict]:
    workdir = REPO_ROOT / "workdir"
    if not workdir.is_dir():
        return []
    entries: list[dict] = []
    for wave_path in workdir.glob("*/*/tests/*/*.vcd"):
        parts = wave_path.relative_to(REPO_ROOT).parts
        if len(parts) >= 6 and parts[0] == "workdir":
            entries.append({"wave_path": wave_path, "timestamp": datetime.fromtimestamp(wave_path.stat().st_mtime)})
    for wave_path in workdir.glob("*/*/regressions/*/*/*.vcd"):
        parts = wave_path.relative_to(REPO_ROOT).parts
        if len(parts) >= 7:
            entries.append({"wave_path": wave_path, "timestamp": datetime.fromtimestamp(wave_path.stat().st_mtime)})
    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return entries


def run_debug_mode(env_data: dict) -> None:
    entries = discover_debug_entries()
    if not entries:
        raise BuildError("no saved waveform files found under workdir")
    print_status_line("wait", "debug")
    print_status_line("start", "debug")
    for i, e in enumerate(entries[:20], start=1):
        print(f"  [{i}] {e['wave_path'].relative_to(REPO_ROOT)}", flush=True)
    sel = input("select entry number to open with gtkwave (blank to cancel): ").strip()
    if not sel or not sel.isdigit():
        print_status_line("done-pass", "debug", duration="+0ms")
        return
    idx = int(sel)
    if idx < 1 or idx > len(entries):
        return
    path = str(entries[idx - 1]["wave_path"])
    subprocess.Popen(
        [env_data["gtkwave_exe"], path],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print_status_line("done-pass", "debug", duration="+0ms")
    print_review_files([path])


def announce_step_tree(
    step_name: str, steps_cfg: dict, context: dict, announced: set[str]
) -> None:
    if step_name in announced:
        return
    for dep in get_step_dependencies(step_name, steps_cfg):
        announce_step_tree(dep, steps_cfg, context, announced)
    print_status_line("wait", get_step_display_name(step_name, steps_cfg, context))
    announced.add(step_name)


def announce_regression_tests(base: dict, tests: list[str], steps_cfg: dict) -> None:
    for t in tests:
        ctx = get_test_data(dict(base), t, "regress")
        print_status_line("wait", get_step_display_name("simulate", steps_cfg, ctx))


def main() -> int:
    resolved_command_text = ""
    try:
        args = parse_args()
        if not args.ip and not args.debug:
            sel = prompt_for_named_entry("ip", get_available_ips())
            if sel is None:
                print(f"[done-pass {timestamp_text()}] ip selection canceled", flush=True)
                return 0
            args.ip = sel
        if not get_requested_mode_names(args):
            modes = prompt_for_modes()
            if modes is None:
                print(f"[done-pass {timestamp_text()}] mode selection canceled", flush=True)
                return 0
            apply_selected_modes(args, modes)

        build_cfg = load_yaml(BUILD_CONFIG)
        require_keys(build_cfg, ["targets", "steps"], str(BUILD_CONFIG))
        targets_cfg = build_cfg["targets"]
        steps_cfg = build_cfg["steps"]
        requested = resolve_requested_targets(args)
        if args.debug:
            run_debug_mode(get_env_data({"gtkwave"}))
            return 0
        for t in requested:
            if t not in targets_cfg:
                raise BuildError(f"unknown target '{t}'")

        context = get_ip_data(args.ip)
        for tname in requested:
            tcfg = targets_cfg[tname]
            sel = tcfg.get("selector")
            if not sel:
                continue
            argn = resolve_selector_argument_name(sel["param"])
            val = getattr(args, argn)
            if val != INTERACTIVE_SELECT:
                continue
            names = (
                get_available_tests(context)
                if sel["kind"] == "test"
                else get_available_regressions(context)
            )
            picked = prompt_for_named_entry(sel["kind"], names)
            if picked is None:
                print(f"[done-pass {timestamp_text()}] {sel['kind']} selection canceled", flush=True)
                return 0
            setattr(args, argn, picked)

        required = collect_required_tool_names(requested, targets_cfg, context)
        env_data = get_env_data(required)
        context.update(env_data)
        tag = resolve_tag(args.tag, context)
        args.tag = tag
        if args.regress and isinstance(args.regress, str):
            context["regress_name"] = args.regress
        context = apply_run_paths(context, tag)

        workflow = f"workflow {','.join(requested)} ip={context['ip']} tag={context['tag']}"
        t0 = monotonic()
        resolved_command_text = build_resolved_command(args)
        print_command_banner(resolved_command_text, "resolved_command")
        print_status_line("wait", workflow)
        print_status_line("start", workflow)

        tdeps, tclosures = collect_target_dependencies(requested, targets_cfg, steps_cfg)
        tctxs = {
            t: resolve_target_context(context, t, targets_cfg[t], args) for t in requested
        }
        announced: set[str] = set()
        announce_step_tree("prepare", steps_cfg, context, announced)
        for t in requested:
            for s in targets_cfg[t].get("root_steps", []):
                announce_step_tree(s, steps_cfg, tctxs[t], announced)
            if t == "regress":
                announce_regression_tests(tctxs[t], tctxs[t].get("selected_tests", []), steps_cfg)

        run_step("prepare", steps_cfg, context, set())
        futures: dict[str, concurrent.futures.Future[None]] = {}

        def execute_target(tname: str) -> None:
            for dep in sorted(tdeps[tname]):
                futures[dep].result()
            done = {"prepare"}
            for dep in tdeps[tname]:
                done.update(tclosures[dep])
            for s in targets_cfg[tname].get("root_steps", []):
                run_step(s, steps_cfg, tctxs[tname], done)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(requested)) as ex:
            for t in requested:
                futures[t] = ex.submit(execute_target, t)
            for t in requested:
                futures[t].result()

        print_status_line("done-pass", workflow, duration=duration_text(t0))
        print_review_files([context["ip_root"]])
        print_summary_line(f"targets={','.join(requested)} tag={context['tag']} ip={context['ip']}")
        print_command_banner(resolved_command_text, "completed_command")
        return 0
    except BuildError as err:
        with PRINT_LOCK:
            print(f"{status_prefix('done-fail')} workflow {err}", file=sys.stderr, flush=True)
            if resolved_command_text:
                print_command_banner(resolved_command_text, "failed_command")
        return 1


if __name__ == "__main__":
    sys.exit(main())
