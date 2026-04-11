# physical design

`wiki/pd/` mirrors `src/pd/` and describes physical-design intent.

Physical design starts after synthesis and owns the path from mapped netlist to
floorplan, placement, routing, extraction, signoff reports, and review images.

That work requires a **P&R backend** (place-and-route engine), which the
repository defines as a **second toolchain tier** after RTL/DV/FV/synth
bootstrap. See [software-stack](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/software-stack)
for why the stack is split and what each tier covers.

The current repository stage is a DEF-stage scaffold:

- `cfg/pd.yaml` declares the selected backend strategy
- `cfg/ip.yaml` declares IP floorplan, IO boundary, and timing intent
- `src/pd/common/` is the shared physical-design collateral home
- `src/pd/<ip>/` is the IP-local physical-design collateral home
- `./build -ip <ip> -pd` consumes synthesis output and emits review DEF artifacts
- `./build -ip <ip> -pd -pd-exec` (optional, local) additionally checks that an `openroad` binary exists; not used in default CI

The selected foundation backend is OpenROAD Flow Scripts. The repository does not
vendor or install it yet. Until external backend integration lands, the builder
emits deterministic DEF-style review artifacts:

- `floorplan/<ip>_floorplan.def`
- `floorplan/<ip>_io_placement.tcl`
- `timing/<ip>.sdc`
- `place/<ip>_placed.def`
- `reports/<ip>_cts.rpt`
- `reports/<ip>_timing.rpt`
- `reports/<ip>_utilization.rpt`
- `route/<ip>_routed.def`
- `pd.log`
- `<ip>_pd_summary.yaml`

GDS, SPEF, signoff reports, and layout images remain later signoff-stage work.
