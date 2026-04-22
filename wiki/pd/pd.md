# physical design

`wiki/pd/` mirrors `src/pd/` and describes physical-design intent.

Physical design starts after synthesis and owns the path from mapped netlist to
floorplan, placement, routing, extraction, signoff reports, and review images.

That work requires a **P&R backend** (place-and-route engine), which the
repository defines as a **second toolchain tier** after RTL/DV/FV/synth
bootstrap.

> **Historical / legacy:** The active `./build` stack is **Windows + Questa + Quartus**; **`-pd`** and OpenROAD are **not** supported targets today. The text below describes the **original foundation PD package** for reference. See [software-stack](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/software-stack).

The current repository stage is a foundation PD package:

- `cfg/pd.yaml` declares the selected backend strategy
- `cfg/ip.yaml` declares IP floorplan, IO boundary, and timing intent
- `src/pd/common/` is the shared physical-design collateral home
- `src/pd/<ip>/` is the IP-local physical-design collateral home
- `./build -ip <ip> -pd` consumes synthesis output and emits review physical-design artifacts
- `./build -ip <ip> -pd -pd-exec` (optional, local) additionally checks that an `openroad` binary exists at the preferred path in `cfg/env.yaml`; not used in default CI

The selected foundation backend is OpenROAD Flow Scripts. The repository does not
vendor or install it yet. Until external backend integration lands, the builder
emits deterministic foundation review artifacts:

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

The final DEF, GDSII, SPEF, DRC, LVS, and image files are foundation artifacts.
They are useful for structure, automation, and PR review, but they are not
PDK-backed signoff results until the external OpenROAD/technology integration is
wired.
