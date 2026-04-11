# Counter Physical Design

The counter IP uses the `openroad_foundation` physical-design profile from `cfg/pd.yaml`.

The current PD area uses builder-generated DEF and report review artifacts so
repository QA and `./build -pd` exercise the same floorplan, IO, timing,
placement, CTS, route, timing-report, and utilization-report contract as FIFO.
