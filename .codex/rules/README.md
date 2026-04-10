# codex rules

This directory is the repository-local execution-facing rules layer for agents.

It is intentionally separate from the repo-root wiki:

- `wiki/` is the specification source of truth
- `.codex/rules/` is the condensed implementation-facing guidance derived from that spec
- `AGENTS.md` is the concise operating contract that tells agents to use both

## Intended use

- read the relevant rule files here before making implementation changes in that discipline
- keep these rules aligned with the wiki instead of inventing a second source of truth
- prefer updating the wiki first when the intended behavior or structure changes
- update these rule files when the agent-facing execution guidance changes materially

## Recommended read order

1. `README.md`
2. `github-flow.md`
3. the discipline rule file relevant to the task:
   - `rtl-coding-style.md`
   - `dv-methodology.md`
   - `fv-methodology.md`
   - `synthesis-methodology.md`
   - `builder-methodology.md`
4. when onboarding or hardening repository infrastructure:
   - `builder-methodology.md`
   - the standard repo entrypoints `./setup` and `./build`

## Rule hierarchy

1. system and developer instructions
2. repo `AGENTS.md`
3. repo `wiki/`
4. repo `.codex/rules/`

If these ever disagree, fix the drift instead of guessing.
