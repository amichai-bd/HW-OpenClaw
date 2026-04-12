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

Optional **local** opt-in after you install an OpenROAD-class backend:

```sh
./build -ip fifo -pd -pd-exec
```

`-pd-exec` requires `-pd`. It keeps the same foundation PD package, then checks
that an `openroad` binary resolves at the preferred path in `cfg/env.yaml`. It
does **not** run a full ORFS place-and-route from the builder until that
integration is implemented; the gate exists so local workflows can fail fast when
the backend is missing. **CI must not** add `-pd` or `-pd-exec` to the default
merge gate.

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

The current selected foundation backend is OpenROAD Flow Scripts.

This choice keeps the project on an open-source physical-design path while
allowing incremental integration:

1. declare structure and tool expectations
2. add floorplan and IO boundary generation
3. add placement, CTS, routing, and DEF outputs
4. add foundation GDS, SPEF, signoff reports, and review images
5. replace foundation artifacts with real backend-produced PDK-backed artifacts

The repository should not pretend a real PDK-backed signoff flow exists before
technology collateral and backend installation are handled explicitly.

The current internal scaffold is a review artifact generator, not a substitute
for external OpenROAD execution or signoff. Its GDSII, SPEF, DRC, LVS, and timing
outputs are intentionally marked foundation/informational. External backend tools
must be declared in `cfg/pd.yaml` when they become required by a later stage.
