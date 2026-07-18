# Kimi K3 chip-design stack research

## What Moonshot disclosed

Moonshot's July 2026 Kimi K3 launch blog says that K3 spent one autonomous
48-hour run building, optimizing, and verifying a nano-model inference chip
with **open-source EDA tools** and the **Nangate 45 nm library**. It reports a
4 mm² design, 100 MHz timing closure, 1.46 million standard cells, 0.277 MB
SRAM, and simulated decode throughput above 8,700 tokens/s.

Primary source:
<https://www.kimi.com/blog/kimi-k3#chip-design>

The launch post does not name the tools, RTL language, simulator, agent harness,
verification plan, prompts, source repository, or intermediate artifacts. It
says more technical details will accompany a later technical report. Therefore
the exact stack remains unconfirmed as of 2026-07-19.

## Best-supported stack hypothesis

The strongest match is **OpenROAD Flow Scripts (ORFS)**:

- ORFS officially describes itself as an autonomous RTL-to-GDSII flow.
- Its documented integrated tools are **Yosys** for synthesis,
  **OpenROAD** for floorplan through detailed routing, and **KLayout** for GDS,
  DRC, and LVS where public decks exist.
- OpenROAD contains **OpenSTA** timing analysis and **OpenRCX** parasitic
  extraction in the same physical-design application.
- ORFS directly ships the **Nangate45/FreePDK45** reference platform named in
  Moonshot's disclosure.
- The OpenROAD project's explicit goal is a no-human-in-loop, approximately
  24-hour autonomous digital implementation flow, which fits the type of
  long-horizon agent demonstration Kimi described.

Primary sources:

- <https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts>
- <https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/master/docs/user/UserGuide.md>
- <https://github.com/The-OpenROAD-Project/OpenROAD>

## Confidence ranking

1. **High confidence:** ORFS or a thin custom wrapper around the same
   Yosys/OpenROAD/OpenSTA/OpenRCX/KLayout stack.
2. **Medium-high confidence:** Yosys handled RTL synthesis and OpenROAD handled
   floorplan, PDN, placement, CTS, global routing, and detailed routing.
3. **Medium confidence:** KLayout generated/merged final GDS and ran physical
   DRC. ORFS does this by default for Nangate45, but Moonshot did not say so.
4. **Medium confidence:** Verilator was used for fast RTL simulation/lint before
   physical implementation. It is a natural open-source choice, but the K3 post
   provides no direct evidence.
5. **Low confidence:** OpenLane, Magic, Netgen, or Icarus Verilog were involved.
   These are common in other open-source flows, but ORFS is the more direct
   match for Nangate45 and already covers the reported task.

Probable orchestration layers are shell, Make, Tcl, Python, and an agent terminal
harness such as Kimi Code. That orchestration is also unconfirmed.

## Local reproducible approximation

This repository pins the Linux/amd64 ORFS image by immutable digest:

```text
openroad/orfs@sha256:86dfae2d567b8570d71fa49f24ea420a2e79d9645673ba41fd70c5a63510e4aa
```

Verified bundled versions on 2026-07-19:

- OpenROAD `26Q3-528-g20d2d5c16e`
- Yosys `0.67+post`
- KLayout `0.30.7`
- host-side Verilator `5.020`

Install and verify:

```sh
./setup --pd
./setup --pd --check
```

Run the small counter through behavioral simulation and the physical flow:

```sh
./build -ip counter -tag kimi_stack_local -test sanity
./build -ip counter -tag kimi_stack_local -pd -pd-exec
```

The locally verified run completed Nangate45 floorplan/PDN, placement, CTS,
detailed routing, OpenRCX SPEF extraction, timing analysis, KLayout GDS merge,
and KLayout DRC. It produced zero final DRC violations and zero setup/hold TNS at
the declared 10 ns clock. Results are under
`workdir/kimi_stack_local/counter/pd/`.

## Important limits

- Nangate45/FreePDK45 is a research/reference platform, not a manufacturable
  foundry PDK.
- The pinned image declares a Nangate45 KLayout LVS deck path but does not ship
  that file, so the repository records LVS as not run instead of claiming a
  false pass.
- ORFS LEC is disabled in this profile because its helper exits with an illegal
  instruction on the current WSL host CPU. Behavioral Verilator simulation is
  run separately; this is not equivalent to post-layout LEC.
- This reproduces the most likely tool family, not Moonshot's unpublished RTL,
  agent prompts, run trajectory, SRAM methodology, or exact verification plan.
