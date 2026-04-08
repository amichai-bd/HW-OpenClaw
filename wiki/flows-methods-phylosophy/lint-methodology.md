# lint methodology

Lint is part of the RTL discipline contract.

- lint collateral should live next to the RTL under `src/rtl/<ip>/lint/`
- lint waivers should be explicit and reviewable
- lint should be builder-invoked through YAML-defined flow, not ad hoc shell use
- lint output should be structured under `workdir/<tag>/<ip>/lint/`
