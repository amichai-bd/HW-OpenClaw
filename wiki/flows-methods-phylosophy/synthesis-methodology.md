# synthesis methodology

> **Historical / legacy:** The **active** hardware synthesis path is **Intel Quartus** via `./build -fpga` ([fpga-quartus-methodology](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/fpga-quartus-methodology)). This page describes the **older Yosys / `cfg/synth.yaml` foundation** model for reference; it is **not** in the default builder.

Synthesis is a separate engineering discipline.

- synthesis collateral lives under `src/syn/`
- shared synthesis libraries and scripts live under `src/syn/common/`
- the synthesis flow should stay explicit, generic, and config-driven
- synthesized outputs and reports should live under `workdir/<tag>/<ip>/synth/`
- synthesis should emit a machine-readable summary artifact in addition to raw reports
- synthesis should emit human-reviewable structural visuals when the selected profile enables them
- the current flow is a foundation flow, not a signoff flow

## Review intent

The synthesis discipline should make it easy to answer:

- what script/profile was used
- what technology assumptions were used
- what clock/reset/IO timing intent was declared
- what outputs were produced
- what warnings or limitations are known

Foundation-level synthesis is still valuable, but it should be honest about what it is and is not.
The foundation `check` report is captured before final generic liberty remapping
so it reflects the stable internal driver model instead of post-map warnings that
are known to be technology-model artifacts in the current generic flow.

## Constraints

IP-level synthesis constraints live in `cfg/ip.yaml`.

The foundation flow captures clock, reset, and IO timing intent in YAML even when the active generic Yosys profile cannot yet consume full SDC semantics. This keeps the interface stable for future technology-backed synthesis and physical-design flows.

The summary artifact should report both:

- the profile-level constraint model from `cfg/synth.yaml`
- the IP-level constraint values from `cfg/ip.yaml`

## Visual Artifacts

When enabled by the synth profile, the flow should emit structural schematic artifacts under `workdir/<tag>/<ip>/synth/`.

Expected visual artifacts are:

- `{ip}_schematic.dot`
- `{ip}_schematic.svg`
- `{ip}_schematic.png`

These visuals are generated from synthesized structural connectivity. They are useful for checking IO shape, bus widths, cell/register connectivity, and gross datapath/control structure.

They are not physical floorplans, placement views, routed layouts, or timing heatmaps. Physical-design artifacts belong in a separate physical-design discipline.
