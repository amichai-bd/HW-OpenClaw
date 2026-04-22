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
2. `~/.openclaw/secrets/agentmail.env`.

Expected local secret file format:

```sh
AGENTMAIL_API_KEY='...'
AGENTMAIL_INBOX='codex-amichaibd@agentmail.to'
```

## Send

Send plain text:

```sh
python .codex/skills/send-email/scripts/send-agentmail.py \
  --to amichaibd@gmail.com \
  --subject "Subject" \
  --text "Body"
```

Send from a file:

```sh
python .codex/skills/send-email/scripts/send-agentmail.py \
  --to amichaibd@gmail.com \
  --subject "Subject" \
  --text-file path/to/body.txt
```

Attachments (base64 per AgentMail API; repeat `--attach`):

```sh
python .codex/skills/send-email/scripts/send-agentmail.py \
  --to amichaibd@gmail.com \
  --subject "Subject with files" \
  --text "See attachments." \
  --attach path/to/report.txt \
  --attach path/to/diagram.svg
```

The script discovers the AgentMail inbox id from the configured inbox email, sends through `POST /v0/inboxes/{inbox_id}/messages/send`, and prints the message id and thread id. It never prints the API key. Large payloads use a longer HTTP timeout when attachments are present.

Attachment MIME types: unknown extensions default to `application/octet-stream`. For `.rpt`, `.log`, `.yaml`, `.def`, and similar text artifacts the script forces `text/plain; charset=utf-8` so Gmail and other clients show a readable preview instead of a blank panel.

Attachment size limit: each file is checked before reading and must be no larger
than 10 MiB. For larger generated artifacts, send a summary plus the `workdir/`
path instead of attaching the file.

## Rules

- Ask for recipient, subject, and body when they are not obvious.
- Use `amichaibd@gmail.com` only when the user asks to email Amichai or says "send me".
- Do not send secrets, API keys, private credentials, or unreviewed sensitive content by email.
- Do not commit `~/.openclaw/secrets/agentmail.env` or copy its contents into the repo.
