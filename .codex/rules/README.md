# codex rules

Repository-local, execution-facing rules for agents. The wiki (`wiki/`) remains the long-form specification; these files are the short operational layer.

## Intended use

- Read the relevant rule file before editing that area.
- Keep rules aligned with the wiki when behavior changes.
- Prefer updating the wiki when the spec changes, then tighten rules here if needed.

## Read order

1. `README.md` (this file)
2. `github-flow.md`
3. Task-specific:
   - `rtl-coding-style.md` — RTL
   - `dv-methodology.md` — verification / DV
   - `fpga-quartus-methodology.md` — Intel Quartus / FPGA implementation
   - `builder-methodology.md` — `./build` YAML graph and artifacts
4. Lint methodology lives in the wiki only: `wiki/flows-methods-phylosophy/lint-methodology.md` (Questa `vlog -lint`; not Verilator).
5. Standard entrypoints: `./build` and `cfg/env.sh`
6. Skills: `wiki/flows-methods-phylosophy/codex-agent-skills.md`, `.codex/skills/update-wiki/SKILL.md`, `.codex/skills/send-email/SKILL.md`

## Rule hierarchy

1. System and developer instructions  
2. Repo `AGENTS.md`  
3. Repo `wiki/`  
4. Repo `.codex/rules/`

If they disagree, fix the drift.

## Stack note

This repo targets **Windows + Git Bash**, **Questa** simulation, and **Quartus** FPGA flows only. Formal verification (FV) and ASIC-style PD rules were removed from the active rule set.
