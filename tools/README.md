# tools

Implementations invoked by repo entrypoints (`./build`, `./setup`).

## Build orchestration

- **`tools/build/build.yaml`** — declarative targets and steps (dependency graph, artifacts).
- **`tools/build/build.py`** — executor for that graph.
- **`tools/misc/`** — optional debugging utilities that are not normal user-facing entrypoints.

The builder is discipline-agnostic policy-wise: RTL, DV, FV, synthesis, and physical design are all **targets** driven from YAML plus `cfg/*.yaml`, not separate ad hoc scripts.

## Software stack context

Tool expectations and bootstrap scope live in **`cfg/env.yaml`**: plain
`./setup` owns Tier 1, while `./setup --pd` installs the optional digest-pinned
ORFS root filesystem. Physical-design backend behavior lives in **`cfg/pd.yaml`**
and IP-local `pd_constraints.orfs`.

For **why** the stack splits **RTL-through-synth** from **P&R / OpenROAD-class** tools, see the wiki page [software-stack](../wiki/flows-methods-phylosophy/software-stack.md).
