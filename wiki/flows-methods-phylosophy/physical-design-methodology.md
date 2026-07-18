# physical-design methodology

Physical design is a separate repository discipline named `pd`.

## Purpose

The PD flow owns the transition from synthesized netlist to physical collateral:

- floorplan
- IO boundary placement
- timing constraints
- placement
- clock-tree synthesis
- routing
- extraction
- timing, DRC, LVS, and image reports
- final DEF, GDS, and SPEF artifacts

## Configuration

`cfg/pd.yaml` owns shared physical-design profiles. A profile declares the backend,
bootstrap status, required tools, required inputs, and planned outputs.

`cfg/ip.yaml` owns IP-local PD intent through `pd_profile` and `pd_constraints`.
That intent includes floorplan shape, IO policy, and timing intent.

The builder must not infer a backend by scanning directories or by guessing which
tools are installed. If a tool is required, the profile must declare it.

## Builder Contract

The standard entry point is:

```sh
./build -ip fifo -pd
```

Optional **local** real RTL-to-GDS run after `./setup --pd`:

```sh
./build -ip counter -pd -pd-exec
```

`-pd-exec` requires `-pd`. The builder first emits the same foundation package,
then runs the pinned ORFS image and replaces authoritative floorplan, IO,
placement, CTS, route, final DEF/GDS/SPEF, timing, utilization, and DRC outputs
with backend-produced artifacts. The IP must declare fixed ORFS floorplan and
backend controls under `pd_constraints.orfs`. **CI must not** add `-pd` or
`-pd-exec` to the default merge gate.

The `pd` target depends on synthesis because physical design consumes the mapped
netlist and synthesis summary. At the foundation package stage, the step emits
deterministic review collateral from the synthesis JSON and IP-local PD intent:
floorplan DEF, IO placement TCL, timing SDC, placed DEF, CTS report, route-stage
DEF, final DEF, foundation GDSII, SPEF limitation file, timing/utilization/DRC/LVS
review reports, SVG/PNG layout images, PD log, and `pd_summary.yaml`.

Generated PD collateral belongs under:

```text
workdir/<tag>/<ip>/pd/
```

The planned artifact groups are:

- `floorplan/`
- `timing/`
- `place/`
- `reports/` for CTS, timing, utilization, and informational signoff reports
- `route/`
- `signoff/`
- `images/`

## Software stack placement

Physical design sits in **Tier 2** of the repository tool stack: it is the
**place-and-route layer** that turns synthesis outputs into layout-oriented
artifacts (DEF, GDS/SPEF, images, and signoff-style reports). That layer is **not**
part of the same bootstrap bundle as Verilator, Yosys, and SBY; separating them
avoids conflating **logical netlists** with **physical implementation**.

The split, CI scope, and rationale are documented in
[software-stack](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/software-stack).

## Backend Strategy

The selected executable backend is a digest-pinned OpenROAD Flow Scripts image
using its Nangate45 reference platform.

This choice keeps the project on an open-source physical-design path:

1. Verilator validates RTL behavior separately
2. ORFS/Yosys maps RTL to Nangate45 cells
3. OpenROAD performs floorplan, PDN, placement, CTS, and routing
4. OpenRCX emits SPEF and OpenSTA reports timing
5. KLayout merges final GDS and runs the public Nangate45 DRC deck

The repository should not pretend a real PDK-backed signoff flow exists before
technology collateral and backend installation are handled explicitly.

The internal scaffold remains a review artifact generator when `-pd-exec` is
absent. Nangate45 backend output is materially stronger but still is not
foundry-qualified signoff: it is a reference platform, and its LVS deck is not
present in the pinned public image. The summary distinguishes these states.
