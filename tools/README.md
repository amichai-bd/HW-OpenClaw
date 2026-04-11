# tools

Implementations invoked by repo entrypoints (`./build`, `./setup`).

## Build orchestration

- **`tools/build/build.yaml`** — declarative targets and steps (dependency graph, artifacts).
- **`tools/build/build.py`** — executor for that graph.

The builder is discipline-agnostic policy-wise: RTL, DV, FV, synthesis, and physical design are all **targets** driven from YAML plus `cfg/*.yaml`, not separate ad hoc scripts.

## Software stack context

Tool expectations and bootstrap scope live in **`cfg/env.yaml`** (what `./setup` installs vs what stays manual). Physical-design backends are **`cfg/pd.yaml`** plus `manual_tools` in `cfg/env.yaml`.

For **why** the stack splits **RTL-through-synth** from **P&R / OpenROAD-class** tools, see the wiki page [software-stack](../wiki/flows-methods-phylosophy/software-stack.md).
