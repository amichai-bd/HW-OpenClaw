# FIFO Physical Design

The FIFO IP uses the `openroad_foundation` physical-design profile from `cfg/pd.yaml`.

Current scope:

- declare the physical-design structure
- declare floorplan, IO boundary, and timing intent in `cfg/ip.yaml`
- depend on synthesis outputs as PD inputs
- emit floorplan, IO, timing, placed DEF, CTS, route-stage DEF, final DEF, foundation GDSII/SPEF, timing/utilization/DRC/LVS reports, and layout image review artifacts
