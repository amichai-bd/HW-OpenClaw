# software stack

This page defines **what tools the repository assumes** and **why the stack is split** the way it is. It is about **intent and boundaries**, not install recipes.

## Why define the stack explicitly

Hardware work here spans disciplines that use **different toolchains**:

- **RTL through synthesis** produces a **logical** view: simulatable SystemVerilog, formal models, and a **mapped netlist** (cells and connectivity).
- **Physical design** produces a **geometric** view: floorplan, placement, clock tree, routes, layout exchange formats (DEF/GDS), parasitics (SPEF), layout images, and signoff-style reports.

Those layers depend on each other, but they are **not the same program**. Yosys answers “what gates and wires exist?” OpenROAD-class tools answer “where do they sit on the die, and can they meet timing?” The repository therefore treats **physical place-and-route** as a **declared backend** with its own expectations, instead of pretending synthesis outputs are already “the chip.”

Defining the stack in config (`cfg/env.yaml`, `cfg/pd.yaml`) keeps `./setup` and `./build` honest: bootstrap installs what CI and most contributors need daily; PD installs stay explicit until the project wires a supported backend path.

## Tier 1 — Repository bootstrap (`./setup`)

**Role:** Everything needed for **spec-driven RTL work**, **DV**, **FV**, **lint**, and **Yosys synthesis** on typical Ubuntu-style hosts and GitHub-hosted CI.

**Source of truth:** `cfg/env.yaml` → `environment.bootstrap` and `environment.tools`.

**Result:** A predictable environment for `./build` targets such as `-compile`, `-test`, `-regress`, `-fv`, `-synth`, and `-qa`. The main CI gate is built from this tier so pull requests stay fast and reproducible.

## Tier 2 — Physical-design backend (place-and-route)

**Role:** **Floorplan, placement, CTS, routing, extraction, timing, GDS, and DRC**. This is the **P&R engine** and its ecosystem, not another RTL tool.

**Declared foundation:** **OpenROAD Flow Scripts** (OpenROAD-class backend), as named in `cfg/pd.yaml` and summarized in [physical-design-methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/physical-design-methodology).

**Source of truth:** `cfg/pd.yaml` (profile/backend contract), `cfg/env.yaml` → `bootstrap.user_installs.orfs` (pinned image and installer), and IP-local `pd_constraints.orfs`.

**Provisioning:**

```sh
./setup --pd
./setup --pd --check
```

The installer downloads a checksum-pinned `crane` client, exports the digest-pinned
`openroad/orfs` Linux/amd64 image into `~/.local/share/hw-openclaw/orfs/`, and
runs it with Bubblewrap. This needs no Docker daemon and changes no system
permissions. The image bundles the matched ORFS versions of Yosys, OpenROAD
(including OpenSTA/OpenRCX), and KLayout.

**Result today:**

- `./build -ip <ip> -pd` is the **PD entry point**; it depends on synthesis outputs.
- `./build -ip <ip> -pd -pd-exec` is the **optional local real-backend path** for an IP with explicit ORFS floorplan constraints.
- The counter profile runs Nangate45 synthesis, floorplan/PDN, placement, CTS, routing, OpenRCX extraction, STA, GDS generation, and KLayout DRC.
- Plain `-pd` remains the fast deterministic foundation path.
- Nangate45/FreePDK45 is a reference platform, not a foundry-qualified manufacturing PDK. The pinned public image also omits its referenced Nangate45 LVS deck, so LVS is reported honestly as not run.

**CI today:** The default PR gate exercises **Tier 1** only. Adding Tier 2 to CI is a separate decision (machine size, caching, container), not implied by the current workflow.

## How the pieces connect

```text
RTL / DV / FV
  →  ./setup (Tier 1)
  →  ./build … -compile -fv -synth …
  →  mapped netlist + PD constraints
  →  ./setup --pd
  →  ./build … -pd -pd-exec
  →  PD backend (Tier 2: pinned ORFS/Nangate45)
  →  DEF / GDS / SPEF / reports (as wired)
```

## Why this is the Kimi K3 working hypothesis

Moonshot only disclosed “open-source EDA tools” and Nangate45. ORFS is the
strongest reproducible match because its official stack combines Yosys,
OpenROAD/OpenSTA/OpenRCX, and KLayout and directly ships a Nangate45 platform.
See [Kimi K3 stack research](./kimi-k3-stack-research.md) for evidence,
confidence levels, and unknowns.

## Related pages

- [physical-design methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/physical-design-methodology)
- [builder methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/builder-methodology)
- [synthesis methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/synthesis-methodology)
