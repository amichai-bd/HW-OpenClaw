# physical design

`wiki/pd/` mirrors `src/pd/` and describes physical-design intent.

Physical design starts after synthesis and owns the path from mapped netlist to
floorplan, placement, routing, extraction, signoff reports, and review images.

That work requires a **P&R backend** (place-and-route engine), which the
repository defines as a **second toolchain tier** after RTL/DV/FV/synth
bootstrap. See [software-stack](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/software-stack)
for why the stack is split and what each tier covers.

The current repository stage is a foundation PD package:

- `cfg/pd.yaml` declares the selected backend strategy
- `cfg/ip.yaml` declares IP floorplan, IO boundary, and timing intent
- `src/pd/common/` is the shared physical-design collateral home
- `src/pd/<ip>/` is the IP-local physical-design collateral home
- `./build -ip <ip> -pd` consumes synthesis output and emits review physical-design artifacts
- `./setup --pd` provisions the optional pinned ORFS toolchain in user-local storage
- `./build -ip counter -pd -pd-exec` (optional, local) runs real Nangate45 RTL-to-GDS; not used in default CI

The selected backend is a digest-pinned OpenROAD Flow Scripts image. Without
`-pd-exec`, the builder emits deterministic foundation review artifacts:

- `floorplan/<ip>_floorplan.def`
- `floorplan/<ip>_io_placement.tcl`
- `timing/<ip>.sdc`
- `place/<ip>_placed.def`
- `reports/<ip>_cts.rpt`
- `reports/<ip>_timing.rpt`
- `reports/<ip>_utilization.rpt`
- `route/<ip>_routed.def`
- `signoff/<ip>.def`
- `signoff/<ip>.gds`
- `signoff/<ip>.spef`
- `reports/<ip>_drc.rpt`
- `reports/<ip>_lvs.rpt`
- `images/<ip>_layout.svg`
- `images/<ip>_layout.png`
- `pd.log`
- `<ip>_pd_summary.yaml`

With `-pd-exec`, the counter's DEF, GDSII, SPEF, CTS, timing, utilization, and
DRC files come from the ORFS Nangate45 run. The SVG/PNG remain lightweight
builder review images. Nangate45 is a reference platform rather than a
manufacturable foundry PDK, and LVS is not run because its referenced public
deck is absent from the pinned image.
