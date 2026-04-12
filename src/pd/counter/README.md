# Counter Physical Design

The counter IP uses the `openroad_foundation` physical-design profile from `cfg/pd.yaml`.

The current PD area uses builder-generated DEF, foundation GDSII/SPEF,
informational report, and layout image artifacts so repository QA and
`./build -pd` exercise the same floorplan, IO, timing, placement, CTS, route,
signoff-package, timing-report, utilization-report, DRC/LVS-report, and image
contract as FIFO.
