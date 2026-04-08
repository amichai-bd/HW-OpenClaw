# lint methodology

Lint is part of the RTL discipline contract.

- lint collateral should live next to the RTL under `src/rtl/<ip>/lint/`
- lint waivers should be explicit and reviewable
- lint should be builder-invoked through YAML-defined flow, not ad hoc shell use
- lint output should be structured under `workdir/<tag>/<ip>/lint/`

## Waiver philosophy

Waivers should be treated as specification-backed exceptions, not casual suppression.

If a warning is waived:

- the waiver should live near the RTL it affects
- the reason should be understandable from context
- the spec should not silently drift into depending on waived behavior without being written down
