# fifo physical design

The FIFO physical-design flow is the first proof-of-concept target for the PD
skeleton.

Intent:

- consume the synthesized FIFO netlist and synth summary
- use `cfg/ip.yaml` for floorplan, IO boundary, and timing intent
- use `cfg/pd.yaml` for backend strategy
- generate artifacts under `workdir/<tag>/fifo/pd/`
- emit floorplan, IO, timing, placed DEF, CTS, route-stage DEF, timing, and utilization review artifacts

The current FIFO PD configuration is deliberately modest: low utilization,
square aspect ratio, grouped IO policy, and the same clock period used by synth.
