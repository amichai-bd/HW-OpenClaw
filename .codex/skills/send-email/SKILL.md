---
name: send-email
description: Send project-related email from the repo-owned AgentMail inbox. Use when the user asks Codex or another agent to email a report, note, result, summary, artifact, or test message.
---

# Send Email

Use AgentMail for agent-owned outbound email. Do not use a human personal email account.

Default sender inbox:

```text
codex-amichaibd@agentmail.to
```

Default recipient for project owner messages:

```text
amichaibd@gmail.com
```

## Credentials

Never commit AgentMail secrets.

The script reads credentials in this order:

1. `AGENTMAIL_API_KEY` and optional `AGENTMAIL_INBOX` from the environment.
1. `~/.openclaw/secrets/agentmail.env`.

Expected local secret file format:

```sh
AGENTMAIL_API_KEY='...'
AGENTMAIL_INBOX='codex-amichaibd@agentmail.to'
```

## Send

Send plain text:

```sh
python3 .codex/skills/send-email/scripts/send-agentmail.py \
  --to amichaibd@gmail.com \
  --subject "Subject" \
  --text "Body"
```

Send from a file:

```sh
python3 .codex/skills/send-email/scripts/send-agentmail.py \
  --to amichaibd@gmail.com \
  --subject "Subject" \
  --text-file path/to/body.txt
```

The script discovers the AgentMail inbox id from the configured inbox email, sends through `POST /v0/inboxes/{inbox_id}/messages/send`, and prints the message id and thread id. It never prints the API key.

## Rules

- Ask for recipient, subject, and body when they are not obvious.
- Use `amichaibd@gmail.com` only when the user asks to email Amichai or says "send me".
- Do not send secrets, API keys, private credentials, or unreviewed sensitive content by email.
- Do not commit `~/.openclaw/secrets/agentmail.env` or copy its contents into the repo.
