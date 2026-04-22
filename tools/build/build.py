#!/usr/bin/env python3
"""Generic YAML-driven build engine: loads tools/flows from tools/build/build.yaml."""

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


def resolve_env_file_path(build_cfg: dict) -> Path:
    """Prefer env.local / HW_OPENCLAW_ENV_FILE; else build.yaml env_input.path."""
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
    rel = (build_cfg.get("env_input") or {}).get("path", "cfg/env.yaml")
    return (REPO_ROOT / rel).resolve()


def deep_get(mapping: dict, dotted_path: str):
    cur: object = mapping
    for part in dotted_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise BuildError(f"missing path {dotted_path!r} in environment data")
        cur = cur[part]
    return cur


def env_context_from_root(env: dict) -> dict:
    """Resolve home_dir/model_root/bin_dir templates (same inputs as legacy get_env_data)."""
    env_context = dict(env)
    env_context["repo_root"] = str(REPO_ROOT)
    env_context["host_home"] = os.environ.get("HOME", str(Path.home()))
    env_context["home_dir"] = resolve_template_text(str(env["home_dir"]), env_context)
    env_context["model_root"] = resolve_template_text(str(env["model_root"]), env_context)
    if isinstance(env.get("bin_dir"), str) and env["bin_dir"].strip():
        env_context["bin_dir"] = resolve_template_text(str(env["bin_dir"]), env_context)
    else:
        env_context["bin_dir"] = str(REPO_ROOT / "bin")
    return env_context


def apply_environment_from_build_cfg(required_tool_names: set[str], build_cfg: dict) -> dict:
    """Populate context keys from cfg/env.yaml using build.yaml `tools` + `derived_context`."""
    env_path = resolve_env_file_path(build_cfg)
    env_root = load_yaml(env_path)
    root_key = (build_cfg.get("env_input") or {}).get("root_key", "environment")
    if root_key not in env_root:
        raise BuildError(f"missing '{root_key}' in {env_path}")
    env = env_root[root_key]
    for rk in (build_cfg.get("env_input") or {}).get("require_root_keys", []):
        require_keys(env, [rk], f"{env_path}::{root_key}")
    tools_root = env["tools"]
    if not isinstance(tools_root, dict):
        raise BuildError(f"'tools' must be a mapping in {env_path}")
    env_ctx = env_context_from_root(env)
    out: dict = {
        "model_root": env_ctx["model_root"],
    }
    for entry in build_cfg.get("derived_context", []):
        require_keys(entry, ["path", "as"], "derived_context entry")
        raw = deep_get(env, str(entry["path"]))
        dest = str(entry["as"])
        xf = entry.get("transform")
        if xf == "bool":
            if isinstance(raw, bool):
                out[dest] = raw
            else:
                out[dest] = str(raw).strip().lower() in {"1", "true", "yes", "on"}
        elif xf in (None, ""):
            out[dest] = raw
        else:
            raise BuildError(f"unknown derived_context transform {xf!r}")
    tool_defs = build_cfg.get("tools")
    if not isinstance(tool_defs, dict):
        raise BuildError("build.yaml must define 'tools' as a mapping")
    for name in required_tool_names:
        if name not in tool_defs:
            raise BuildError(f"tool {name!r} required but missing from build.yaml tools")
        if name not in tools_root:
            raise BuildError(f"missing tool {name!r} in {env_path}")
        tdef = tool_defs[name]
        if not isinstance(tdef, dict):
            raise BuildError(f"tools.{name} must be a mapping")
        cfg = tools_root[name]
        for field in tdef.get("require_fields", []):
            require_keys(cfg, [str(field)], f"environment.tools.{name}")
        exports = tdef.get("exports") or {}
        if not isinstance(exports, dict):
            raise BuildError(f"tools.{name}.exports must be a mapping")
        for ctx_key, spec in exports.items():
            if not isinstance(spec, dict):
                raise BuildError(f"tools.{name}.exports.{ctx_key} must be a mapping")
            require_keys(spec, ["from_field"], f"tools.{name}.exports.{ctx_key}")
            field = str(spec["from_field"])
            raw = cfg[field]
            if spec.get("resolve_templates"):
                out[str(ctx_key)] = resolve_template_text(str(raw), env_ctx)
            elif spec.get("as_argv_word_list"):
                if isinstance(raw, list):
                    out[str(ctx_key)] = [str(x) for x in raw if str(x).strip()]
                else:
                    out[str(ctx_key)] = [t for t in str(raw).split() if t]
            else:
                out[str(ctx_key)] = raw
    return out


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


def flatten_build_parameters(parameters: object, prefix: str = "b") -> dict:
    """Nested build.yaml `parameters` -> flat keys `b_group_leaf` for {b_group_leaf} templates."""
    out: dict = {}

    def walk(node: object, parts: list[str]) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                walk(val, parts + [str(key)])
            return
        key = "_".join([prefix] + parts)
        out[key] = node

    if isinstance(parameters, dict):
        walk(parameters, [])
    elif parameters not in (None, {}):
        raise BuildError("build.yaml 'parameters' must be a mapping when present")
    return out


def merge_build_parameters_into_context(context: dict, build_cfg: dict) -> None:
    context.update(flatten_build_parameters(build_cfg.get("parameters")))


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


def get_ip_data(ip_name: str, build_cfg: dict) -> dict:
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
    dfp = (build_cfg.get("ip_defaults") or {}).get("fpga") or {}
    rev_default = format_text(str(dfp.get("revision_template", "{ip}_fpga")), ip_data)
    top_from = str(dfp.get("top_entity_from", "rtl_module"))
    top_default = ip_data[top_from] if top_from in ip_data else ip_data["rtl_module"]
    ip_data["fpga_family"] = str(f.get("family", dfp.get("family", "MAX 10")))
    ip_data["fpga_device"] = str(f.get("device", dfp.get("device", "10M50DAF484C7G")))
    ip_data["fpga_revision"] = str(f.get("revision", rev_default))
    ip_data["fpga_top_entity"] = str(f.get("top_entity", top_default))
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
    requested_targets: list[str], targets_cfg: dict, steps_cfg: dict, build_cfg: dict
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
    for rule in (build_cfg.get("target_ordering") or {}).get("edges") or []:
        when = set(rule.get("when_all_requested") or [])
        if not when.issubset(requested_set):
            continue
        edge = rule.get("add_edge") or {}
        before = edge.get("before")
        after = edge.get("after")
        if isinstance(before, str) and isinstance(after, str) and before in target_dependencies:
            target_dependencies[before].add(after)
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


def tcl_braced_path(path_posix: str) -> str:
    escaped = path_posix.replace("{", "\\{").replace("}", "\\}")
    return "{" + escaped + "}"


def action_remove_tree(context: dict, cmd: dict) -> None:
    require_keys(cmd, ["path"], "remove_tree")
    p = Path(render_value(str(cmd["path"]), context))
    if p.exists():
        shutil.rmtree(p)


def action_truncate_file(context: dict, cmd: dict) -> None:
    require_keys(cmd, ["path"], "truncate_file")
    p = Path(render_value(str(cmd["path"]), context))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")


def action_filelist_consumer(context: dict, cmd: dict, build_cfg: dict) -> None:
    require_keys(cmd, ["consumer"], "filelist_consumer")
    name = str(cmd["consumer"])
    consumers = build_cfg.get("filelist_consumers") or {}
    if name not in consumers:
        raise BuildError(f"unknown filelist_consumers entry {name!r}")
    spec = consumers[name]
    require_keys(spec, ["read_filelist_key", "incdir_prefix", "source_suffixes"], f"filelist_consumers.{name}")
    fl = Path(context[str(spec["read_filelist_key"])])
    if not fl.is_file():
        raise BuildError(f"missing filelist: {fl}")
    incpfx = str(spec["incdir_prefix"])
    suffixes = {s.lower() for s in spec["source_suffixes"]}
    incs: list[str] = []
    srcs: list[str] = []
    for raw in (ln.strip() for ln in fl.read_text(encoding="utf-8").splitlines()):
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith(incpfx):
            incs.append(Path(raw[len(incpfx) :].strip()).resolve().as_posix())
            continue
        p = Path(raw).resolve()
        if p.is_file() and p.suffix.lower() in suffixes:
            srcs.append(p.as_posix())
    if not srcs:
        raise BuildError(f"filelist_consumer {name!r}: no matching source files in {fl}")
    search_lines = [f"lappend search_paths {tcl_braced_path(p)}" for p in incs]
    hdl_lines = [f"lappend hdl_files {tcl_braced_path(p)}" for p in srcs]
    context["quartus_search_paths_tcl_block"] = "\n".join(search_lines) + ("\n" if search_lines else "")
    context["quartus_hdl_files_tcl_block"] = "\n".join(hdl_lines) + ("\n" if hdl_lines else "")


def walk_template_key(build_cfg: dict, dotted: str) -> object:
    node: object = build_cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise BuildError(f"missing template key {dotted!r} in build.yaml")
        node = node[part]
    return node


ANGLE_CTX = re.compile(r"<<([a-zA-Z_][a-zA-Z0-9_]*)>>")


def apply_angle_bracket_template(text: str, context: dict) -> str:
    """Substitute <<context_key>> from context (Tcl/other templates stay brace-safe)."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise BuildError(f"missing context key {key!r} for template substitution")
        return str(context[key])

    return ANGLE_CTX.sub(repl, text)


def action_write_text_template(context: dict, cmd: dict, build_cfg: dict) -> None:
    require_keys(cmd, ["template_key", "dest"], "write_text_template")
    node = walk_template_key(build_cfg, str(cmd["template_key"]))
    if not isinstance(node, str):
        raise BuildError("write_text_template template must be a string")
    text = apply_angle_bracket_template(str(node), context)
    flow = str(context.get("b_quartus_execute_flow_arg", "-compile")).strip()
    text = text.replace("__BUILD_FLOW_ARG__", flow)
    dest = Path(render_value(str(cmd["dest"]), context))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def print_log_triage(profile_name: str, context: dict, build_cfg: dict) -> None:
    profiles = build_cfg.get("log_triage_profiles") or {}
    if profile_name not in profiles:
        return
    prof = profiles[profile_name]
    require_keys(prof, ["log_context_key"], f"log_triage_profiles.{profile_name}")
    rev = str(context.get(str(prof.get("revision_context_key", "fpga_revision")), "project"))
    if "out_dir_context_key" in prof:
        qroot = Path(render_value(str(prof["out_dir_context_key"]), context)).resolve()
    else:
        qroot = Path(context.get("quartus_out_dir", ".")).resolve()
    outf = qroot / "output_files"
    log_p = Path(render_value(str(prof["log_context_key"]), context)).resolve()
    suffixes = prof.get("report_suffixes") or ["fit", "sta", "map", "flow"]
    report_paths: list[str] = []
    if outf.is_dir():
        for suffix in suffixes:
            p = (outf / f"{rev}.{suffix}.rpt").resolve()
            if p.is_file():
                report_paths.append(str(p))
        if not report_paths:
            for p in sorted(outf.glob("*.fit.rpt"))[:2]:
                report_paths.append(str(p.resolve()))
            for p in sorted(outf.glob("*.sta.rpt"))[:2]:
                if str(p.resolve()) not in report_paths:
                    report_paths.append(str(p.resolve()))
    tag = str(prof.get("tag", profile_name))
    shown = " ".join(display_path(p) for p in report_paths) if report_paths else f"(no rpt yet under {display_path(str(outf))})"
    log_disp = display_path(str(log_p))
    hint = str(prof.get("log_grep_hint", "Error|FATAL"))
    with PRINT_LOCK:
        print(f"[{tag}-triage] primary_reports={shown}", file=sys.stderr, flush=True)
        print(f"[{tag}-triage] log_grep: rg -n \"{hint}\" {log_disp}", file=sys.stderr, flush=True)
    pat = re.compile(str(prof.get("line_pattern", "(?i)error")))
    max_lines = int(prof.get("max_matching_lines", 28))
    hits: list[str] = []
    if log_p.is_file():
        for line in log_p.read_text(encoding="utf-8", errors="replace").splitlines():
            if pat.search(line):
                hits.append(line.rstrip()[:400])
                if len(hits) >= max_lines:
                    break
    with PRINT_LOCK:
        print(f"[{tag}-triage] first_{max_lines}_matching_log_lines:", file=sys.stderr, flush=True)
        if hits:
            for h in hits:
                print(f"  {h}", file=sys.stderr, flush=True)
        else:
            print(f"  (no lines matched; read full log: {log_disp})", file=sys.stderr, flush=True)


def action_log_tail_review(context: dict, _cmd: dict, build_cfg: dict) -> None:
    cfg = build_cfg.get("log_tail_review") or {}
    for line in cfg.get("summaries") or []:
        if isinstance(line, str) and line.strip():
            try:
                s = format_text(line, context)
            except KeyError:
                continue
            if s.strip():
                print_summary_line(s)
    for sec in cfg.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        label = str(sec.get("label", "log"))
        path_t = str(sec.get("path", ""))
        n = int(sec.get("tail_lines", 20))
        p = Path(render_value(path_t, context))

        def tail_text(path: Path, lines_n: int) -> str:
            if not path.is_file():
                return f"(missing {path.name})"
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            body = "\n".join(lines[-lines_n:]) if lines else "(empty)"
            return body

        with PRINT_LOCK:
            print(f"--- {label} (tail) ---", flush=True)
            print(tail_text(p, n), flush=True)


def action_foreach_run_step(context: dict, cmd: dict, steps_cfg: dict, build_cfg: dict) -> None:
    require_keys(cmd, ["child_step", "items_context_key", "iterate_param", "path_mode"], "foreach_run_step")
    step = str(cmd["child_step"])
    items = context.get(str(cmd["items_context_key"])) or []
    if not items:
        print_summary_line(str(cmd.get("empty_summary", "tests=0 passed=0 failed=0")))
        return
    step_cfg = steps_cfg[step]
    failed: list[str] = []
    passed = 0
    errors: list[str] = []
    for item in items:
        test_context = dict(context)
        test_context[str(cmd["iterate_param"])] = item
        apply_test_run_paths(test_context, str(cmd["path_mode"]), build_cfg)
        subj = get_step_display_name(step, steps_cfg, test_context)
        t0 = monotonic()
        print_status_line("start", subj)
        try:
            for command in step_cfg.get("commands", []):
                run_command(command, test_context, steps_cfg, build_cfg)
        except BuildError as err:
            errors.append(str(err))
            failed.append(str(item))
            print_status_line("done-fail", subj, duration=duration_text(t0))
            print_review_files(get_step_review_files(step, steps_cfg, test_context))
            print_review_hint(get_step_review_files(step, steps_cfg, test_context))
            continue
        passed += 1
        print_status_line("done-pass", subj, duration=duration_text(t0))
        print_review_files(get_step_review_files(step, steps_cfg, test_context))
    if errors:
        print_summary_line(
            f"tests={len(items)} passed={passed} failed={len(failed)} failed_names={','.join(failed)}"
        )
        for msg in errors:
            print(msg, file=sys.stderr)
        raise BuildError("regression failed")
    print_summary_line(f"tests={len(items)} passed={passed} failed=0")


def apply_test_run_paths(ctx: dict, mode: str, build_cfg: dict) -> None:
    tr = (build_cfg.get("test_run_paths") or {}).get(mode)
    if not isinstance(tr, dict):
        raise BuildError(f"unknown test_run_paths mode {mode!r}")
    layout_map = tr.get("layout")
    if not isinstance(layout_map, dict):
        raise BuildError(f"test_run_paths.{mode}.layout must be a mapping")
    layout = ctx["output_layout"]
    for dest_key, layout_key in layout_map.items():
        ctx[str(dest_key)] = resolve_path(format_text(layout[str(layout_key)], ctx))
    ctx["wave_enable"] = 1 if ctx.get("waveform_enabled") else 0
    for exp in build_cfg.get("posix_path_exports") or []:
        if not isinstance(exp, dict):
            continue
        require_keys(exp, ["from", "as"], "posix_path_exports entry")
        ctx[str(exp["as"])] = sh_path(str(ctx[str(exp["from"])]))


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


def merged_run_from_invoke(cmd: dict, build_cfg: dict) -> dict:
    name = cmd.get("invoke")
    if not isinstance(name, str) or not name.strip():
        raise BuildError("'invoke' requires a non-empty template name")
    templates = build_cfg.get("command_templates")
    if not isinstance(templates, dict) or name not in templates:
        raise BuildError(f"unknown command_templates entry '{name}'")
    tpl = templates[name]
    if not isinstance(tpl, dict):
        raise BuildError(f"command_templates.{name} must be a mapping")
    merged = dict(tpl)
    for key, val in cmd.items():
        if key in {"invoke", "print_summary"}:
            continue
        merged[key] = val
    return merged


def merged_run_from_run_key(cmd: dict) -> dict:
    block = cmd.get("run")
    if not isinstance(block, dict):
        raise BuildError("'run' must be a mapping")
    merged = dict(block)
    for key, val in cmd.items():
        if key == "run":
            continue
        merged[key] = val
    return merged


def execute_merged_run(merged: dict, context: dict, build_cfg: dict) -> None:
    argv_tpl = merged.get("argv")
    if not isinstance(argv_tpl, list) or not argv_tpl:
        raise BuildError("run/invoke requires non-empty argv (list of template strings)")
    argv = [render_value(str(item), context) for item in argv_tpl]
    ext_key = merged.get("append_argv_from_context")
    if ext_key:
        if not isinstance(ext_key, str):
            raise BuildError("append_argv_from_context must be a string naming a context key")
        extra = context.get(ext_key)
        if extra is None:
            pass
        elif isinstance(extra, list):
            argv.extend(str(x) for x in extra if str(x).strip())
        else:
            raise BuildError(f"context[{ext_key!r}] must be a list for append_argv_from_context")

    cwd_raw = merged.get("cwd")
    cwd = Path(render_value(str(cwd_raw), context)) if cwd_raw else REPO_ROOT
    log_mode = str(merged.get("log_mode", "overwrite")).lower()
    log_raw = merged.get("log")
    if log_raw:
        log_path = Path(render_value(str(log_raw), context))
        if log_mode == "append":
            result = subprocess.run(argv, cwd=str(cwd), text=True, capture_output=True)
            _append_process_output(result, log_path)
            if result.returncode != 0:
                if result.stdout:
                    print(result.stdout, end="", file=sys.stderr)
                if result.stderr:
                    print(result.stderr, end="", file=sys.stderr)
                raise BuildError(f"command failed with exit code {result.returncode}")
        elif log_mode == "overwrite":
            try:
                run_subprocess_logged(argv, cwd=cwd, log_path=log_path)
            except BuildError:
                triage = merged.get("failure_triage_profile")
                if isinstance(triage, str) and triage.strip():
                    print_log_triage(triage.strip(), context, build_cfg)
                raise
        else:
            raise BuildError(f"invalid log_mode {log_mode!r} (use append or overwrite)")
    else:
        result = subprocess.run(argv, cwd=str(cwd), text=True, capture_output=True)
        if result.stdout:
            print(result.stdout, end="", file=sys.stderr)
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            raise BuildError(f"command failed with exit code {result.returncode}")


def run_command(command: str | dict, context: dict, steps_cfg: dict, build_cfg: dict) -> None:
    if isinstance(command, dict) and command.get("action") == "ensure_dir":
        path_t = command.get("path")
        if not isinstance(path_t, str):
            raise BuildError("ensure_dir requires string 'path'")
        Path(render_value(path_t, context)).mkdir(parents=True, exist_ok=True)
        return
    if isinstance(command, dict) and command.get("action") == "run_qa":
        run_qa_from_profile(context, build_cfg)
        return
    if isinstance(command, dict) and command.get("action") == "prepare_filelists":
        prepare_filelists(context)
        return
    if isinstance(command, dict) and command.get("action") == "remove_tree":
        action_remove_tree(context, command)
        return
    if isinstance(command, dict) and command.get("action") == "truncate_file":
        action_truncate_file(context, command)
        return
    if isinstance(command, dict) and command.get("action") == "filelist_consumer":
        action_filelist_consumer(context, command, build_cfg)
        return
    if isinstance(command, dict) and command.get("action") == "write_text_template":
        action_write_text_template(context, command, build_cfg)
        return
    if isinstance(command, dict) and command.get("action") == "log_tail_review":
        action_log_tail_review(context, command, build_cfg)
        return
    if isinstance(command, dict) and command.get("action") == "foreach_run_step":
        action_foreach_run_step(context, command, steps_cfg, build_cfg)
        return
    if isinstance(command, dict) and "invoke" in command:
        ps = command.get("print_summary")
        if isinstance(ps, str) and ps.strip():
            print_summary_line(format_text(ps, context))
        execute_merged_run(merged_run_from_invoke(command, build_cfg), context, build_cfg)
        return
    if isinstance(command, dict) and "run" in command:
        ps = command.get("print_summary")
        if isinstance(ps, str) and ps.strip():
            print_summary_line(format_text(ps, context))
        execute_merged_run(merged_run_from_run_key(command), context, build_cfg)
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


def run_step(step_name: str, steps_cfg: dict, context: dict, completed: set[str], build_cfg: dict) -> None:
    if step_name in completed:
        return
    if step_name not in steps_cfg:
        raise BuildError(f"unknown build step '{step_name}'")
    step_cfg = steps_cfg[step_name]
    subject = get_step_display_name(step_name, steps_cfg, context)
    for dep in get_step_dependencies(step_name, steps_cfg):
        run_step(dep, steps_cfg, context, completed, build_cfg)
    t0 = monotonic()
    print_status_line("start", subject)
    try:
        for cmd in step_cfg.get("commands", []):
            run_command(cmd, context, steps_cfg, build_cfg)
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
    p.add_argument(
        "-fpga",
        action="store_true",
        help="FPGA compile (see build.yaml targets.fpga / quartus_compile step)",
    )
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


def get_available_tests(ip_data: dict, build_cfg: dict) -> list[str]:
    top = (build_cfg.get("discovery") or {}).get("test_yaml_top_key", "test")
    return load_named_yaml_entries(REPO_ROOT / ip_data["test_dir"], str(top))


def get_available_regressions(ip_data: dict, build_cfg: dict) -> list[str]:
    top = (build_cfg.get("discovery") or {}).get("regression_yaml_top_key", "regression")
    return load_named_yaml_entries(REPO_ROOT / ip_data["regression_dir"], str(top))


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


def get_test_data(ip_data: dict, test_name: str, mode: str, build_cfg: dict) -> dict:
    disc = build_cfg.get("discovery") or {}
    top = str(disc.get("test_yaml_top_key", "test"))
    test_file = REPO_ROOT / ip_data["test_dir"] / f"{test_name}.yaml"
    if not test_file.is_file():
        raise BuildError(f"unknown test '{test_name}' for ip '{ip_data['ip']}'")
    test_data = load_yaml(test_file)
    require_keys(test_data, [top], str(test_file))
    if test_data[top]["name"] != test_name:
        raise BuildError(f"test file name mismatch for '{test_name}'")
    ip_data["test_name"] = test_name
    apply_test_run_paths(ip_data, "test" if mode == "test" else "regress", build_cfg)
    return ip_data


def get_regression_tests(ip_data: dict, regression_name: str, build_cfg: dict) -> list[str]:
    disc = build_cfg.get("discovery") or {}
    rtop = str(disc.get("regression_yaml_top_key", "regression"))
    reg_file = REPO_ROOT / ip_data["regression_dir"] / f"{regression_name}.yaml"
    if not reg_file.is_file():
        raise BuildError(f"unknown regression '{regression_name}'")
    reg_data = load_yaml(reg_file)
    require_keys(reg_data, [rtop], str(reg_file))
    reg = reg_data[rtop]
    if reg["name"] != regression_name:
        raise BuildError("regression name mismatch")
    tests = reg["tests"]
    if not isinstance(tests, list):
        raise BuildError("'tests' must be a list")
    ip_data["regress_name"] = regression_name
    ttop = str(disc.get("test_yaml_top_key", "test"))
    for t in tests:
        tf = REPO_ROOT / ip_data["test_dir"] / f"{t}.yaml"
        if not tf.is_file():
            raise BuildError(f"regression lists unknown test {t!r}")
        td = load_yaml(tf)
        require_keys(td, [ttop], str(tf))
        if td[ttop]["name"] != t:
            raise BuildError(f"test file name mismatch for {t!r}")
    return list(tests)


def resolve_selector_argument_name(param: str, build_cfg: dict) -> str:
    m = (build_cfg.get("selectors") or {}).get("param_to_arg") or {}
    if param not in m:
        raise BuildError(f"unsupported selector param '{param}' (add to selectors.param_to_arg)")
    return str(m[param])


def resolve_target_context(
    base: dict, target_name: str, target_cfg: dict, args: argparse.Namespace, build_cfg: dict
) -> dict:
    ctx = dict(base)
    sel = target_cfg.get("selector")
    if sel:
        require_keys(sel, ["kind", "param"], f"targets.{target_name}.selector")
        argn = resolve_selector_argument_name(sel["param"], build_cfg)
        val = getattr(args, argn)
        if not isinstance(val, str) or not val:
            raise BuildError(f"missing selector value for target '{target_name}'")
        if sel["kind"] == "test":
            ctx = get_test_data(ctx, val, "test", build_cfg)
        elif sel["kind"] == "regression":
            ctx["regress_name"] = val
            ctx["selected_tests"] = get_regression_tests(dict(ctx), val, build_cfg)
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


def validate_style_file(path: Path, patterns: dict[str, re.Pattern], allow_nb: bool) -> list[str]:
    violations: list[str] = []
    labels = {
        "always_plain": "plain 'always' is not allowed",
        "inline_logic_init": "inline logic init not allowed",
        "nonblocking_assign": "explicit <= not allowed",
    }
    in_block = False
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line, in_block = strip_line_comments(raw, in_block)
        if not line.strip():
            continue
        for key, pat in patterns.items():
            if key == "nonblocking_assign" and allow_nb:
                continue
            if pat.search(line):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{n}: {labels.get(key, key)}"
                )
    if path.name != path.name.lower():
        violations.append(f"{path.relative_to(REPO_ROOT)}: file name must be lowercase")
    return violations


def collect_sv_style_files_from_qa_spec(context: dict, collect: list) -> list[Path]:
    files: set[Path] = set()
    for entry in collect:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if kind == "from_filelist":
            ck = str(entry["context_key"])
            rtl_src: set[Path] = set()
            collect_filelist_sources((REPO_ROOT / context[ck]).resolve(), set(), rtl_src)
            files.update(rtl_src)
        elif kind == "glob_sv":
            root = REPO_ROOT / format_text(str(entry["root"]), context)
            if root.is_dir():
                files.update(iter_sv_sources(root.resolve()))
            elif not entry.get("optional"):
                raise BuildError(f"qa collect glob_sv: missing directory {root}")
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


def run_qa_from_profile(context: dict, build_cfg: dict) -> None:
    profile = build_cfg.get("qa_profile")
    if not isinstance(profile, dict):
        raise BuildError("build.yaml must define qa_profile")
    for k in profile.get("require_context_keys", []):
        if str(k) not in context:
            raise BuildError(f"qa_profile missing context key {k!r}")
    checked_files: list[Path] = []
    violations: list[str] = []
    for check in profile.get("checks", []):
        if not isinstance(check, dict):
            continue
        kind = check.get("kind")
        if kind == "dirs_exist":
            for d in check.get("paths", []):
                validate_exists(format_text(str(d), context), "dir")
        elif kind == "files_exist":
            for f in check.get("paths", []):
                validate_exists(format_text(str(f), context), "file")
        elif kind == "filelist_trees_valid":
            for ck in check.get("context_paths", []):
                validate_filelist_tree((REPO_ROOT / context[str(ck)]).resolve(), set())
        elif kind == "sv_style_scan":
            patterns_raw = check.get("patterns") or {}
            patterns = {k: re.compile(str(v)) for k, v in patterns_raw.items()}
            allow_in = set(check.get("allow_nonblocking_assign_in") or [])
            checked_files = collect_sv_style_files_from_qa_spec(context, check.get("collect") or [])
            for path in checked_files:
                allow_nb = path.name in allow_in
                violations.extend(validate_style_file(path, patterns, allow_nb))
        else:
            raise BuildError(f"unknown qa_profile check kind {kind!r}")
    write_validation_report(context, checked_files, violations)
    if violations:
        raise BuildError(f"qa failed with {len(violations)} violation(s)")


def discover_debug_entries(build_cfg: dict) -> list[dict]:
    prof = build_cfg.get("debug_profile") or {}
    globs = prof.get("artifact_globs") or []
    entries: list[dict] = []
    for pattern in globs:
        for wave_path in REPO_ROOT.glob(str(pattern)):
            if wave_path.is_file():
                entries.append(
                    {"wave_path": wave_path, "timestamp": datetime.fromtimestamp(wave_path.stat().st_mtime)}
                )
    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return entries


def run_debug_mode(build_cfg: dict, env_data: dict) -> None:
    prof = build_cfg.get("debug_profile") or {}
    tool = str(prof.get("tool", "gtkwave"))
    tool_defs = build_cfg.get("tools") or {}
    if tool not in tool_defs:
        raise BuildError(f"debug_profile.tool {tool!r} missing from build.yaml tools")
    exports = tool_defs[tool].get("exports") or {}
    exe_key = next(iter(exports.keys()), None)
    if not exe_key or exe_key not in env_data:
        raise BuildError(f"debug mode: could not resolve exe context key for tool {tool!r}")
    exe = env_data[exe_key]
    entries = discover_debug_entries(build_cfg)
    if not entries:
        raise BuildError("no saved waveform artifacts matched debug_profile.artifact_globs")
    nmax = int(prof.get("list_max", 20))
    print_status_line("wait", "debug")
    print_status_line("start", "debug")
    for i, e in enumerate(entries[:nmax], start=1):
        print(f"  [{i}] {e['wave_path'].relative_to(REPO_ROOT)}", flush=True)
    sel = input("select entry number to open (blank to cancel): ").strip()
    if not sel or not sel.isdigit():
        print_status_line("done-pass", "debug", duration="+0ms")
        return
    idx = int(sel)
    if idx < 1 or idx > len(entries):
        return
    path = str(entries[idx - 1]["wave_path"])
    subprocess.Popen(
        [str(exe), path],
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


def announce_regression_tests(
    base: dict, tests: list[str], steps_cfg: dict, build_cfg: dict
) -> None:
    for t in tests:
        ctx = get_test_data(dict(base), t, "regress", build_cfg)
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
            req = collect_required_tool_names(requested, targets_cfg, {})
            env_data = apply_environment_from_build_cfg(req, build_cfg)
            run_debug_mode(build_cfg, env_data)
            return 0
        for t in requested:
            if t not in targets_cfg:
                raise BuildError(f"unknown target '{t}'")

        context = get_ip_data(args.ip, build_cfg)
        for tname in requested:
            tcfg = targets_cfg[tname]
            sel = tcfg.get("selector")
            if not sel:
                continue
            argn = resolve_selector_argument_name(sel["param"], build_cfg)
            val = getattr(args, argn)
            if val != INTERACTIVE_SELECT:
                continue
            names = (
                get_available_tests(context, build_cfg)
                if sel["kind"] == "test"
                else get_available_regressions(context, build_cfg)
            )
            picked = prompt_for_named_entry(sel["kind"], names)
            if picked is None:
                print(f"[done-pass {timestamp_text()}] {sel['kind']} selection canceled", flush=True)
                return 0
            setattr(args, argn, picked)

        required = collect_required_tool_names(requested, targets_cfg, context)
        env_data = apply_environment_from_build_cfg(required, build_cfg)
        context.update(env_data)
        merge_build_parameters_into_context(context, build_cfg)
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

        tdeps, tclosures = collect_target_dependencies(requested, targets_cfg, steps_cfg, build_cfg)
        tctxs = {
            t: resolve_target_context(context, t, targets_cfg[t], args, build_cfg) for t in requested
        }
        announced: set[str] = set()
        announce_step_tree("prepare", steps_cfg, context, announced)
        for t in requested:
            for s in targets_cfg[t].get("root_steps", []):
                announce_step_tree(s, steps_cfg, tctxs[t], announced)
            if t == "regress":
                announce_regression_tests(
                    tctxs[t], tctxs[t].get("selected_tests", []), steps_cfg, build_cfg
                )

        run_step("prepare", steps_cfg, context, set(), build_cfg)
        futures: dict[str, concurrent.futures.Future[None]] = {}

        def execute_target(tname: str) -> None:
            for dep in sorted(tdeps[tname]):
                futures[dep].result()
            done = {"prepare"}
            for dep in tdeps[tname]:
                done.update(tclosures[dep])
            for s in targets_cfg[tname].get("root_steps", []):
                run_step(s, steps_cfg, tctxs[tname], done, build_cfg)

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
