# Counter Physical Design

The counter IP uses the `openroad_foundation` physical-design profile from `cfg/pd.yaml`.

Plain `./build -ip counter -pd` uses builder-generated foundation collateral.
After `./setup --pd`, add `-pd-exec` to run the pinned ORFS Nangate45 backend
through routed DEF, extracted SPEF, timing, GDS, and KLayout DRC. See
`wiki/pd/counter/pd-counter.md` for constraints and limitations.
