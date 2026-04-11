# AGENTS.md — HW-OpenClaw repository

This file is the concise operating contract for agents working in this repository.
Detailed structure, methods, and philosophy live in the repo-root `wiki/`.

## Start Here

- Read [wiki/Home.md](./wiki/Home.md) first.
- Treat the wiki as the version-controlled specification surface of the repository.
- Use the relevant mirrored wiki path and the methodology pages under `wiki/flows-methods-phylosophy/` as the deeper source of truth.
- For implementation work, also consult the relevant files under `.codex/rules/`. In this repository, `.codex/rules/` is the condensed execution-facing rules layer derived from the wiki.
- Keep this `AGENTS.md` concise. Repository-wide philosophy, long-form rules, and detailed methodology belong in the wiki.

## Quick Orientation

```text
bin/     thin user-facing entrypoints
cfg/     yaml source of truth for environment and flows
.codex/  agent rules and repo-local skills
src/     implementation by discipline: rtl, dv, fv, syn, pd
tools/   tool implementations
wiki/    version-controlled specification surface
workdir/ generated run outputs
```

## Workflow

- All meaningful changes start from an issue.
- Each issue must begin from the specification with wording such as `according to wiki wiki/...`.
- Each issue should carry the correct labels for the change type, for example `bug`, `enhancement`, or `documentation`.
- Each issue should be implemented on a short-lived branch whose name starts with the issue number.
- Open a pull request before merging to `main`.
- Each pull request must reference the relevant wiki path.
- Pull requests are expected to satisfy the repository gate checks before merge.
- Pull requests are also expected to satisfy the PR-Agent review gate before merge.
- Pull requests are also expected to satisfy the CodeRabbit review gate before merge.
- Once an agent opens a pull request, the task is not complete until the pull request is green, merged, and the local workspace is synced back to `main`.
- Agents are expected to poll their open pull requests, watch CI, PR-Agent, CodeRabbit, and review feedback, fix problems on the same branch, and stay with the pull request until merge completes.
- If PR-Agent raises findings or comments, address them before merge. Do not leave PR-Agent findings unresolved and assume the pull request is ready anyway.
- If CodeRabbit raises findings or review threads, address them before merge. Do not leave CodeRabbit findings unresolved and assume the pull request is ready anyway.
- PR-Agent should answer in the repository-defined structured format from `.pr_agent.toml`. Agents should use that structure to decide what is blocking, what is informational, and what needs a code or doc fix.
- PR-Agent and CodeRabbit have different gate surfaces. PR-Agent is the repository-managed GitHub Actions review gate configured by `.pr_agent.toml`. CodeRabbit is the GitHub App review gate configured by `.coderabbit.yaml` and can also block merge through unresolved review conversations.
- If `main` advanced while a pull request stayed open, merge current `main` into the branch (or rebase) and push so gates and reviews run against an up-to-date base.
- If the PR-Agent workflow concludes **cancelled** rather than **failure**, re-run that workflow run or push to the branch; treat that as automation or concurrency, not a completed PR-Agent verdict.
- The normal finish state is native GitHub auto-merge after the required PR/build checks and conversation-resolution requirements are clean.
- After merge, delete the branch locally and on origin.
- If a change resolves an issue, use closing language such as `Closes #<issue>` in the commit message and/or pull request body.

## Spec-Driven Rule

- The repository is spec-driven.
- The top-level `wiki/` tree mirrors `src/` and is the source of truth for intended structure and behavior.
- `wiki/flows-methods-phylosophy/` holds repository-wide flow, methods, coding rules, and philosophy.
- Changes in `src/` must be checked against the relevant wiki path and should update the wiki when intended structure, behavior, or method changes.
- Changes in `wiki/` must be checked against the corresponding implementation paths so spec and implementation remain aligned.
- If code reveals ambiguity, missing detail, or the wrong abstraction in the wiki, fix the wiki as part of the same change.

## Coding Rules

- Keep only short repository-level examples here. The detailed coding rules live in the wiki pages listed below.
- Module and file names must match and be lowercase.
- Parameter names must be uppercase.
- Signal names should be lowercase with underscores.
- Use `always_comb` for combinational logic and `always_ff` for sequential logic.
- Do not use plain `always`.
- Do not combine `logic` declarations with inline initialization or assignment.
- Keep non-blocking assignments inside approved macros only. Do not write explicit `<=` assignments in handwritten RTL, DV, or FV code.

For detailed style and methodology, consult:
- [rtl-coding-style.md](./wiki/flows-methods-phylosophy/rtl-coding-style.md)
- [dv-methodology.md](./wiki/flows-methods-phylosophy/dv-methodology.md)
- [software-stack.md](./wiki/flows-methods-phylosophy/software-stack.md)
- [physical-design-methodology.md](./wiki/flows-methods-phylosophy/physical-design-methodology.md)
- [github-flow.md](./wiki/flows-methods-phylosophy/github-flow.md)
- [spec-driven-development.md](./wiki/flows-methods-phylosophy/spec-driven-development.md)

## Tool And Config Rules

- The repository **software stack** is intentionally **two-tier**: `./setup` provisions **RTL, DV, FV, lint, and Yosys synthesis** for normal dev and CI; **physical place-and-route** is a **separate backend tier** (OpenROAD-class, declared in `cfg/pd.yaml`) so P&R is not conflated with logical synthesis. Rationale and boundaries: [software-stack.md](./wiki/flows-methods-phylosophy/software-stack.md).
- **`openroad`** (or the wired equivalent) is listed under `cfg/env.yaml` → `manual_tools` until the PD backend is integrated into bootstrap or CI; `./build -ip <ip> -pd` remains the PD entry point and should fail clearly if the profile requires a missing backend executable.
- YAML files are the source of truth for repository tools.
- Do not hardcode fallback paths, inferred defaults, search patterns, or directory discovery logic inside scripts.
- If a tool needs build flow definitions, read them from the tool YAML file.
- The builder should treat `tools/build/build.yaml` as a declarative target/step graph, with dependency order and parallelism expressed through explicit `depends_on` fields.
- If a tool needs IP-specific paths, tops, tests, regressions, binaries, or output layout, read them from the relevant config YAML file.
- Repository environment data lives in `cfg/env.yaml`, and shell tools should source `cfg/env.sh` as the entry point to that data.
- The shell export contract itself should be defined in `cfg/env.yaml`; `cfg/env.sh` should only materialize YAML-defined exports and PATH updates.
- Shared formal profile data lives in `cfg/fv.yaml`.
- Shared synthesis profile data lives in `cfg/synth.yaml`.
- Shared physical-design profile data lives in `cfg/pd.yaml`.
- Source filelists should be authored relative to `$MODEL_ROOT`.
- Tools should translate source filelists into generated explicit filelists under `workdir/` when downstream tools require absolute paths.
- Structured run outputs should be described in YAML and emitted under `workdir/<tag>/<ip>/...`.
- Scripts should fail clearly when required YAML keys or files are missing instead of guessing.
- The GitHub Wiki mirror is updated on demand through the repo-local `.codex/skills/update-wiki/` skill, not through an automatic CI workflow.

## Agent Email

- Project-related outbound email should use the repo-local `.codex/skills/send-email/` skill.
- The default agent-owned sender inbox is `codex-amichaibd@agentmail.to`.
- The default project-owner recipient is `amichaibd@gmail.com` when the user says "send me an email".
- AgentMail credentials must not be committed to the repo.
- On this system, AgentMail credentials are expected at `~/.openclaw/secrets/agentmail.env`.
- That file should define `AGENTMAIL_API_KEY` and `AGENTMAIL_INBOX`; agents may also use those environment variables directly.
- To send, use `.codex/skills/send-email/scripts/send-agentmail.py`; the script reads the secret file automatically and must not print the API key.

## Repository Shape

- `bin/` contains thin user-facing launchers.
- `tools/` contains implementations.
- `src/rtl/`, `src/dv/`, `src/fv/`, `src/syn/`, and `src/pd/` are separate disciplines.
- Shared reusable collateral belongs under the relevant discipline’s `common/` directory.
- Cross-IP composition is allowed when architecturally intentional and declared explicitly through config and filelists, not through ad hoc neighbor-tree dependency.

For detailed structure, consult:
- [repo-structure.md](./wiki/flows-methods-phylosophy/repo-structure.md)
- [builder-methodology.md](./wiki/flows-methods-phylosophy/builder-methodology.md)

Useful first reads by topic:
- structure and navigation: [repo-structure.md](./wiki/flows-methods-phylosophy/repo-structure.md)
- toolchain tiers and PD backend: [software-stack.md](./wiki/flows-methods-phylosophy/software-stack.md)
- build flow and artifacts: [builder-methodology.md](./wiki/flows-methods-phylosophy/builder-methodology.md)
- RTL rules: [rtl-coding-style.md](./wiki/flows-methods-phylosophy/rtl-coding-style.md)
- DV rules: [dv-methodology.md](./wiki/flows-methods-phylosophy/dv-methodology.md)
- PD rules: [physical-design-methodology.md](./wiki/flows-methods-phylosophy/physical-design-methodology.md)
- process and PR flow: [github-flow.md](./wiki/flows-methods-phylosophy/github-flow.md)

Useful `.codex/rules/` files by topic:
- [README.md](./.codex/rules/README.md)
- [github-flow.md](./.codex/rules/github-flow.md)
- [rtl-coding-style.md](./.codex/rules/rtl-coding-style.md)
- [dv-methodology.md](./.codex/rules/dv-methodology.md)
- [fv-methodology.md](./.codex/rules/fv-methodology.md)
- [synthesis-methodology.md](./.codex/rules/synthesis-methodology.md)
- [physical-design-methodology.md](./.codex/rules/physical-design-methodology.md)
- [builder-methodology.md](./.codex/rules/builder-methodology.md)

## Standard Entry Points

- The standard shell entrypoint is `. cfg/env.sh`.
- The standard interactive builder entrypoint is the repo-root `./build`, which should source `cfg/env.sh` and delegate to `bin/build`.
- `./build` is the required user-facing entry point for simulation, formal, synthesis, physical design, and related flows.
- Physical design: `-pd` runs the scaffold; `-pd-exec` (requires `-pd`) is an optional **local** OpenROAD binary gate. Do **not** add `-pd` or `-pd-exec` to the default GitHub Actions merge gate unless the project explicitly opts into Tier-2 PD in CI.
- `./setup` is the required repository bootstrap entry point for fresh clones and CI provisioning.
- Do not treat bare tool invocations such as raw simulator, formal, or synthesis commands as the normal interface for repository work.
- The builder supports combining multiple discipline flags in one command.
- `-qa` is the standard repository QA check for an IP and should be used before or alongside other discipline flows when structural or style drift is a concern.
- Shared prerequisites such as generated filelists and compile should run once per invocation when needed.
- `-debug` remains standalone.
- `-test` and `-regress` remain mutually exclusive in a single invocation.
- GitHub Actions gates should invoke the same repository setup and builder entrypoints used locally rather than re-encoding tool logic in workflow YAML.
- GitHub Actions PR gates should include the PR-Agent review action with repository-specific instructions from the repo-root `.pr_agent.toml`.
- CodeRabbit should be configured from the repo-root `.coderabbit.yaml` and used as an additional PR review gate on the public repository.
- Wiki publishing should use `.codex/skills/update-wiki/scripts/update-wiki.py` or the compatibility wrapper `./bin/wiki-publish`.
