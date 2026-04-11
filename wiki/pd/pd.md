# physical design

`wiki/pd/` mirrors `src/pd/` and describes physical-design intent.

Physical design starts after synthesis and owns the path from mapped netlist to
floorplan, placement, routing, extraction, signoff reports, and review images.

The current repository stage is a skeleton:

- `cfg/pd.yaml` declares the selected backend strategy
- `cfg/ip.yaml` declares IP floorplan, IO boundary, and timing intent
- `src/pd/common/` is the shared physical-design collateral home
- `src/pd/<ip>/` is the IP-local physical-design collateral home
- `./build -pd -ip <ip>` exists and fails clearly until the backend is installed

The selected foundation backend is OpenROAD Flow Scripts. The repository does not
vendor or install it yet; later issues will add the backend integration in stages.
