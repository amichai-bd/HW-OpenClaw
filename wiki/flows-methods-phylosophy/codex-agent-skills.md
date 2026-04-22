# codex agent skills

The repository ships **repo-local agent procedures** under `.codex/skills/`. Each skill has a `SKILL.md` contract (name, description, workflow, rules) and optional scripts.

These are **not** CI steps. They run only when a human or agent explicitly invokes them.

## Inventory

| Skill | Purpose | Entry point |
| ----- | ------- | ----------- |
| **update-wiki** | Publish the version-controlled `wiki/` tree to the GitHub Wiki mirror (`*.wiki.git`). | `python .codex/skills/update-wiki/scripts/update-wiki.py` |
| **send-email** | Send project email from the repo-owned AgentMail inbox (reports, summaries, notifications). | `python .codex/skills/send-email/scripts/send-agentmail.py` |

Compatibility wrapper for wiki publish: `./bin/wiki-publish` (delegates to the update-wiki script).

## Where to read the full contract

On `main` in the code repository (not in the GitHub Wiki git):

- [update-wiki/SKILL.md](https://github.com/amichai-bd/HW-OpenClaw/blob/main/.codex/skills/update-wiki/SKILL.md) — dry-run, publish, auth, rules (do not treat the GitHub Wiki UI as source of truth).
- [send-email/SKILL.md](https://github.com/amichai-bd/HW-OpenClaw/blob/main/.codex/skills/send-email/SKILL.md) — AgentMail credentials (`~/.openclaw/secrets/agentmail.env` or env vars), defaults, CLI examples, safety rules.

## update-wiki (summary)

- **Source of truth:** repo-root `wiki/` on `main` (reviewed via PR).
- **Mirror:** GitHub Wiki for browsing; content is **replaced** from `wiki/` on publish.
- **Typical flow:** `--dry-run --output …` to preview, then run without `--dry-run` to push when ready.
- **Auth:** normal `git push` credentials for `github.com:<owner>/<repo>.wiki.git`.

## send-email (summary)

- **Transport:** AgentMail API; default sender `codex-amichaibd@agentmail.to`.
- **Secrets:** never commit; use `AGENTMAIL_API_KEY` / `AGENTMAIL_INBOX` or `~/.openclaw/secrets/agentmail.env`.
- **Defaults:** project-owner recipient `amichaibd@gmail.com` when the user asks to email them or says “send me”.
- **Safety:** no secrets or unreviewed sensitive content in outbound mail.

## Related

- [Home](/amichai-bd/HW-OpenClaw/wiki/Home) — GitHub Wiki tab versus versioned `wiki/` tree
- [repo-structure](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/repo-structure) — repository layout including `.codex/`
- [ai-native-cli-first](/amichai-bd/HW-OpenClaw/wiki/flows-methods-phylosophy/ai-native-cli-first)
