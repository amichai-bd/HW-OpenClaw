# physical-design methodology

Use these rules when editing `src/pd/`, `cfg/pd.yaml`, PD build steps, or PD wiki
pages.

- Treat `pd` as the physical-design discipline.
- Keep physical-design collateral under `src/pd/`, not under `src/syn/`.
- Put reusable scripts and methods under `src/pd/common/`.
- Put IP-local physical-design collateral under `src/pd/<ip>/`.
- Drive backend selection from `cfg/pd.yaml`.
- Drive IP floorplan, IO, and timing intent from `cfg/ip.yaml`.
- Do not infer technology, backend, or tool paths by scanning directories.
- Do not silently skip required PD tools. If a profile or opt-in flag requires
  an external backend, fail with the profile name, missing tool, and summary
  artifact path.
- Keep generated PD outputs under `workdir/<tag>/<ip>/pd/`.
- Treat synthesis output as the PD input boundary unless a later spec explicitly
  introduces a different handoff.
- Keep floorplan, place, route, signoff, and image artifacts separated in the
  output layout.
- Be explicit when a generated DEF is an internal review scaffold rather than a
  routed DEF from an external P&R backend.
- Update `wiki/pd/` and `wiki/flows-methods-phylosophy/physical-design-methodology.md`
  when PD structure or behavior changes.
- When changing what belongs in bootstrap vs manual PD tooling, also align
  `wiki/flows-methods-phylosophy/software-stack.md` and `cfg/env.yaml` manual_tools.
