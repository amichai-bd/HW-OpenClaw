#!/usr/bin/env bash

_codex_env_source="${BASH_SOURCE[0]:-$0}"
_codex_env_dir=$(CDPATH= cd -- "$(dirname -- "$_codex_env_source")" && pwd)
_codex_repo_root=$(CDPATH= cd -- "$_codex_env_dir/.." && pwd)
_codex_env_yaml="$_codex_env_dir/env.yaml"

if [ ! -f "$_codex_env_yaml" ]; then
    echo "missing env yaml: $_codex_env_yaml" >&2
    return 1 2>/dev/null || exit 1
fi

eval "$(
    REPO_ROOT="$_codex_repo_root" ENV_YAML="$_codex_env_yaml" python - <<'PY'
import os
import re
import shlex
from pathlib import Path

import yaml

repo_root = os.environ["REPO_ROOT"]
env_yaml = Path(os.environ["ENV_YAML"])
data = yaml.safe_load(env_yaml.read_text(encoding="utf-8"))
env = data["environment"]
shell_cfg = env["shell"]
host_home = os.environ.get("HOME", "")

def lookup(mapping, dotted_key):
    value = mapping
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(dotted_key)
        value = value[part]
    return value


def resolve_template(text, mapping):
    def replace(match):
        key = match.group(1)
        value = lookup(mapping, key)
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return re.sub(r"\{([^{}]+)\}", replace, text)


context = dict(env)
context["repo_root"] = repo_root
context["host_home"] = host_home
context["home_dir"] = resolve_template(str(env["home_dir"]), context)
context["model_root"] = resolve_template(str(env["model_root"]), context)
context["bin_dir"] = resolve_template(str(env["bin_dir"]), context)

tools_cfg = env.get("tools", {})
resolved_tools = {}
for tool_name, tool_cfg in tools_cfg.items():
    if not isinstance(tool_cfg, dict):
        raise TypeError(f"environment.tools.{tool_name} must be a mapping")
    resolved_tool = {}
    for key, value in tool_cfg.items():
        if isinstance(value, str):
            resolved_tool[key] = resolve_template(value, context)
        else:
            resolved_tool[key] = value
    resolved_tools[tool_name] = resolved_tool
context["tools"] = resolved_tools

exports_cfg = shell_cfg["exports"]
path_prepend_cfg = shell_cfg.get("path_prepend", [])
exports = {key: resolve_template(str(value), context) for key, value in exports_cfg.items()}

for key, value in exports.items():
    print(f"export {key}={shlex.quote(value)}")

for raw_path in path_prepend_cfg:
    path_value = resolve_template(str(raw_path), context)
    print('case ":${PATH:-}:" in')
    print(f'  *:{shlex.quote(path_value)}:*) ;;')
    print(f'  *) export PATH={shlex.quote(path_value)}:"$PATH" ;;')
    print("esac")
PY
)"
