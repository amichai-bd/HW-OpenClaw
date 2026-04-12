# ai native cli first

The repository is AI-native and CLI-first.

- structure should be predictable enough that an AI agent can infer intent from paths and config
- environment entrypoints should be explicit
- YAML files are the source of truth for tools and flow structure
- shell commands should stay simple and reviewable
- repository work should not depend on hidden GUI state
- debug artifacts should be emitted as structured files that both humans and agents can inspect
- repo-local agent procedures live under `.codex/skills/` and are documented in [codex-agent-skills](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/codex-agent-skills)
