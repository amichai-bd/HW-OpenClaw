# software stack

This page defines **what tools the repository assumes** and **why the stack is split** the way it is. It is about **intent and boundaries**, not install recipes.

## Why define the stack explicitly

Hardware work here spans disciplines that use **different toolchains**:

- **RTL through synthesis** produces a **logical** view: simulatable SystemVerilog, formal models, and a **mapped netlist** (cells and connectivity).
- **Physical design** produces a **geometric** view: floorplan, placement, clock tree, routes, and layout exchange formats (DEF, later GDS) plus parasitics (SPEF) and signoff-style reports.

Those layers depend on each other, but they are **not the same program**. Yosys answers “what gates and wires exist?” OpenROAD-class tools answer “where do they sit on the die, and can they meet timing?” The repository therefore treats **physical place-and-route** as a **declared backend** with its own expectations, instead of pretending synthesis outputs are already “the chip.”

Defining the stack in config (`cfg/env.yaml`, `cfg/pd.yaml`) keeps `./setup` and `./build` honest: bootstrap installs what CI and most contributors need daily; PD installs stay explicit until the project wires a supported backend path.

## Tier 1 — Repository bootstrap (`./setup`)

**Role:** Everything needed for **spec-driven RTL work**, **DV**, **FV**, **lint**, and **Yosys synthesis** on typical Ubuntu-style hosts and GitHub-hosted CI.

**Source of truth:** `cfg/env.yaml` → `environment.bootstrap` and `environment.tools`.

**Result:** A predictable environment for `./build` targets such as `-compile`, `-test`, `-regress`, `-fv`, `-synth`, and `-qa`. The main CI gate is built from this tier so pull requests stay fast and reproducible.

## Tier 2 — Physical-design backend (place-and-route)

**Role:** **Floorplan, placement, CTS, routing**, and the path toward **DEF / GDS / SPEF** and signoff-class reports. This is the **P&R engine** and its ecosystem, not another RTL tool.

**Declared foundation:** **OpenROAD Flow Scripts** (OpenROAD-class backend), as named in `cfg/pd.yaml` and summarized in [physical-design-methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/physical-design-methodology).

**Source of truth:** `cfg/pd.yaml` (profiles, backend kind, planned inputs/outputs) and `cfg/env.yaml` → `manual_tools.openroad` (executable expectation for the wired flow).

**Result today:**

- `./build -ip <ip> -pd` is the **PD entry point**; it depends on synthesis outputs.
- `./build -ip <ip> -pd -pd-exec` is an **optional local** check that an `openroad` binary exists after the scaffold; it is **not** part of the default CI gate.
- The builder can emit **deterministic review collateral** and a **PD summary** aligned with the declared backend contract.
- Until the external backend is installed and integrated, the flow **fails clearly** when the profile requires a real `openroad` (or equivalent) executable—rather than silently skipping physical implementation.

**CI today:** The default PR gate exercises **Tier 1** only. Adding Tier 2 to CI is a separate decision (machine size, caching, container), not implied by the current workflow.

## How the pieces connect

```text
RTL / DV / FV
  →  ./setup (Tier 1)
  →  ./build … -compile -fv -synth …
  →  mapped netlist + PD constraints
  →  ./build … -pd
  →  PD backend (Tier 2: OpenROAD-class P&R)
  →  DEF / GDS / SPEF / reports (as wired)
```

## Related pages

- [physical-design methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/physical-design-methodology)
- [builder methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/builder-methodology)
- [synthesis methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/synthesis-methodology)
