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

The `pd` target depends on synthesis because physical design consumes the mapped
netlist and synthesis summary. At the skeleton stage, the step writes
`pd_summary.yaml` and then fails clearly if the declared backend executable is
missing.

Generated PD collateral belongs under:

```text
workdir/<tag>/<ip>/pd/
```

The planned artifact groups are:

- `floorplan/`
- `timing/`
- `place/`
- `route/`
- `signoff/`
- `reports/`
- `images/`

## Backend Strategy

The current selected foundation backend is OpenROAD Flow Scripts.

This choice keeps the project on an open-source physical-design path while
allowing incremental integration:

1. declare structure and tool expectations
2. add floorplan and IO boundary generation
3. add placement, CTS, routing, and DEF outputs
4. add GDS, SPEF, signoff reports, and review images

The repository should not pretend a real PDK-backed signoff flow exists before
technology collateral and backend installation are handled explicitly.
