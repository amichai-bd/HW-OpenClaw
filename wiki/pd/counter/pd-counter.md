# counter physical design

The counter physical-design area exists so repository structure and QA remain
consistent across IPs.

The counter uses the same `openroad_foundation` profile as FIFO. It emits the
same floorplan, IO, timing, placed DEF, CTS, route-stage DEF, final DEF,
foundation GDSII/SPEF, timing/utilization/DRC/LVS, layout image, log, and summary
artifact set so both current IPs exercise the physical-design builder contract
before external PDK-backed signoff integration.
