# AGENTS.md — HW-OpenClaw repository

This file is the concise operating contract for agents working in this repository.
Detailed structure, methods, and philosophy live in the repo-root `wiki/`.

## Start Here

- Read [wiki/Home.md](/home/amichai/openclaw/workspaces/hw-design/HW-OpenClaw/wiki/Home.md) first.
- Treat the wiki as the version-controlled specification surface of the repository.
- Use the relevant mirrored wiki path and the methodology pages under `wiki/flows-methods-phylosophy/` as the deeper source of truth.
- Keep this `AGENTS.md` concise. Repository-wide philosophy, long-form rules, and detailed methodology belong in the wiki.

## Local Agent Email

- This repository may be used by an agent that has the AgentMail inbox `codex-amichaibd@agentmail.to`.
- Outbound email is optional operational support for the agent and is not part of the repository specification surface.
- Do not assume inbound email reading is configured or required for work in this repository.
- If the user asks to send email, prefer AgentMail API usage from the local machine rather than embedding secrets in the repository.
- The local AgentMail API key path is `/home/amichai/.openclaw/secrets/agentmail.env`.
- Local machine paths in this file are host-specific operational hints, not portable repository configuration.
- Load that file locally when needed and keep it out of commits, logs, generated artifacts, and repository documentation.
- If email sending fails, report the failure clearly instead of guessing alternate mail paths or providers.

## Workflow

- All meaningful changes start from an issue.
- Each issue must begin from the specification with wording such as `according to wiki wiki/...`.
- Each issue should carry the correct labels for the change type, for example `bug`, `enhancement`, or `documentation`.
- Each issue should be implemented on a short-lived branch whose name starts with the issue number.
- Open a pull request before merging to `main`.
- Each pull request must reference the relevant wiki path.
- Pull requests are expected to satisfy the repository gate checks before merge.
- Once an agent opens a pull request, the task is not complete until the pull request is green, merged, and the local workspace is synced back to `main`.
- Agents are expected to poll their open pull requests, watch CI and review feedback, fix problems on the same branch, and stay with the pull request until merge completes.
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
- [rtl-coding-style.md](/home/amichai/openclaw/workspaces/hw-design/HW-OpenClaw/wiki/flows-methods-phylosophy/rtl-coding-style.md)
- [dv-methodology.md](/home/amichai/openclaw/workspaces/hw-design/HW-OpenClaw/wiki/flows-methods-phylosophy/dv-methodology.md)
- [github-flow.md](/home/amichai/openclaw/workspaces/hw-design/HW-OpenClaw/wiki/flows-methods-phylosophy/github-flow.md)
- [spec-driven-development.md](/home/amichai/openclaw/workspaces/hw-design/HW-OpenClaw/wiki/flows-methods-phylosophy/spec-driven-development.md)

## Tool And Config Rules

- YAML files are the source of truth for repository tools.
- Do not hardcode fallback paths, inferred defaults, search patterns, or directory discovery logic inside scripts.
- If a tool needs build flow definitions, read them from the tool YAML file.
- The builder should treat `tools/build/build.yaml` as a declarative target/step graph, with dependency order and parallelism expressed through explicit `depends_on` fields.
- If a tool needs IP-specific paths, tops, tests, regressions, binaries, or output layout, read them from the relevant config YAML file.
- Repository environment data lives in `cfg/env.yaml`, and shell tools should source `cfg/env.sh` as the entry point to that data.
- The shell export contract itself should be defined in `cfg/env.yaml`; `cfg/env.sh` should only materialize YAML-defined exports and PATH updates.
- Shared formal profile data lives in `cfg/fv.yaml`.
- Shared synthesis profile data lives in `cfg/synth.yaml`.
- Source filelists should be authored relative to `$MODEL_ROOT`.
- Tools should translate source filelists into generated explicit filelists under `workdir/` when downstream tools require absolute paths.
- Structured run outputs should be described in YAML and emitted under `workdir/<tag>/<ip>/...`.
- Scripts should fail clearly when required YAML keys or files are missing instead of guessing.

## Repository Shape

- `bin/` contains thin user-facing launchers.
- `tools/` contains implementations.
- `src/rtl/`, `src/dv/`, `src/fv/`, and `src/syn/` are separate disciplines.
- Shared reusable collateral belongs under the relevant discipline’s `common/` directory.
- Cross-IP composition is allowed when architecturally intentional and declared explicitly through config and filelists, not through ad hoc neighbor-tree dependency.
- The primary product of this repository is the hardware development environment itself.
- IPs in the repository are mainly vehicles to exercise, validate, and demonstrate that environment rather than the main product identity.

For detailed structure, consult:
- [repo-structure.md](/home/amichai/openclaw/workspaces/hw-design/HW-OpenClaw/wiki/flows-methods-phylosophy/repo-structure.md)
- [builder-methodology.md](/home/amichai/openclaw/workspaces/hw-design/HW-OpenClaw/wiki/flows-methods-phylosophy/builder-methodology.md)

## Standard Entry Points

- The standard shell entrypoint is `. cfg/env.sh`.
- The standard interactive builder entrypoint is the repo-root `./build`, which should source `cfg/env.sh` and delegate to `bin/build`.
- `./build` is the required user-facing entry point for simulation, formal, synthesis, and related flows.
- Do not treat bare tool invocations such as raw simulator, formal, or synthesis commands as the normal interface for repository work.
- The builder supports combining multiple discipline flags in one command.
- Shared prerequisites such as generated filelists and compile should run once per invocation when needed.
- `-debug` remains standalone.
- `-test` and `-regress` remain mutually exclusive in a single invocation.
- GitHub Actions gates should invoke the same repository builder and config used locally rather than re-encoding tool logic in workflow YAML.
