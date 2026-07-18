# counter physical design

The counter is the repository's small, reproducible ORFS proof design.

Plain `./build -ip counter -pd` emits the foundation artifact package.
After `./setup --pd`, `./build -ip counter -pd -pd-exec` runs the pinned
Nangate45 backend through Yosys synthesis, floorplan and PDN, placement, CTS,
detailed routing, OpenRCX extraction, timing analysis, KLayout GDS generation,
and KLayout DRC. Its fixed 100 um square die is declared explicitly under
`cfg/ip.yaml` → `counter.pd_constraints.orfs`; the size accommodates the
Nangate45 reference PDN strap geometry even though the counter itself is tiny.

The authoritative backend outputs replace the foundation DEF, GDS, SPEF,
timing, utilization, CTS, and DRC files under `workdir/<tag>/counter/pd/`.
LVS is recorded as not run because the pinned ORFS image does not contain the
LVS deck referenced by its public Nangate45 platform.
