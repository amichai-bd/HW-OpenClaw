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
    REPO_ROOT="$_codex_repo_root" ENV_YAML="$_codex_env_yaml" python3 - <<'PY'
import os
import shlex
from pathlib import Path

import yaml

repo_root = os.environ["REPO_ROOT"]
env_yaml = Path(os.environ["ENV_YAML"])
data = yaml.safe_load(env_yaml.read_text(encoding="utf-8"))
env = data["environment"]
tools = env["tools"]
wave = env["simulation"]["waveform"]

exports = {
    "MODEL_ROOT": env["model_root"].format(repo_root=repo_root),
    "PYTHON3_EXE": tools["python3"]["exe"],
    "PYTHON3_VERSION": tools["python3"]["version"],
    "VERILATOR_EXE": tools["verilator"]["exe"],
    "VERILATOR_VERSION": tools["verilator"]["version"],
    "VERILATOR_TRACE_FLAG": tools["verilator"]["trace_flag"],
    "GTKWAVE_EXE": tools["gtkwave"]["exe"],
    "GTKWAVE_VERSION": tools["gtkwave"]["version"],
    "WAVEFORM_ENABLED": "1" if wave["enabled"] else "0",
    "WAVEFORM_FORMAT": wave["format"],
}

for key, value in exports.items():
    print(f"export {key}={shlex.quote(value)}")
PY
)"
