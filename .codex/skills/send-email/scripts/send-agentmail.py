#!/usr/bin/env python3
"""Send email through the repo-owned AgentMail inbox."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import urllib.error
import urllib.request
from pathlib import Path

AGENTMAIL_API = "https://api.agentmail.to"
DEFAULT_SECRET_FILE = Path.home() / ".openclaw/secrets/agentmail.env"
DEFAULT_INBOX = "codex-amichaibd@agentmail.to"


def read_secret_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        sys.exit(f"failed to read AgentMail secret file {path}: {exc}")

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        try:
            parts = shlex.split(raw_value, comments=False, posix=True)
        except ValueError as exc:
            sys.exit(f"failed to parse {path}: {exc}")
        values[key.strip()] = parts[0] if parts else ""
    return values


def load_config(secret_file: Path) -> tuple[str, str]:
    file_values = read_secret_file(secret_file)
    api_key = os.environ.get("AGENTMAIL_API_KEY") or file_values.get("AGENTMAIL_API_KEY")
    inbox = os.environ.get("AGENTMAIL_INBOX") or file_values.get("AGENTMAIL_INBOX") or DEFAULT_INBOX

    if not api_key:
        sys.exit(
            "missing AGENTMAIL_API_KEY; export it or add it to "
            f"{secret_file} without committing it"
        )
    return api_key, inbox


def agentmail_request(
    method: str,
    path: str,
    api_key: str,
    payload: dict | None = None,
) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        AGENTMAIL_API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            if not body:
                return {}
            try:
                return json.loads(body)
            except json.JSONDecodeError as exc:
                sys.exit(f"AgentMail returned invalid JSON from {request.full_url}: {exc}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        sys.exit(f"AgentMail HTTP {exc.code}: {body[:1000]}")
    except urllib.error.URLError as exc:
        sys.exit(f"AgentMail request failed for {request.full_url}: {exc}")
    except TimeoutError:
        sys.exit(f"AgentMail request timed out for {request.full_url}")


def find_inbox_id(api_key: str, inbox: str) -> str:
    response = agentmail_request("GET", "/v0/inboxes?limit=100", api_key)
    for item in response.get("inboxes", []):
        if item.get("email") == inbox or item.get("inbox_id") == inbox:
            inbox_id = item.get("inbox_id")
            if inbox_id:
                return inbox_id
            sys.exit(f"AgentMail response missing inbox_id for matched inbox: {inbox}")

    available = ", ".join(
        sorted(item.get("email", item.get("inbox_id", "")) for item in response.get("inboxes", []))
    )
    sys.exit(f"AgentMail inbox not found: {inbox}; available: {available or 'none'}")


def read_body(args: argparse.Namespace) -> str:
    if args.text and args.text_file:
        sys.exit("use either --text or --text-file, not both")
    if args.text_file:
        try:
            return args.text_file.read_text(encoding="utf-8")
        except OSError as exc:
            sys.exit(f"failed to read message body file {args.text_file}: {exc}")
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        body = sys.stdin.read()
        if body:
            return body
    sys.exit("missing message body; use --text, --text-file, or stdin")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", required=True, help="recipient email address")
    parser.add_argument("--subject", required=True, help="message subject")
    parser.add_argument("--text", default="", help="plain text message body")
    parser.add_argument("--text-file", type=Path, default=None, help="file containing plain text body")
    parser.add_argument("--inbox", default="", help="AgentMail inbox email or inbox id")
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET_FILE)
    args = parser.parse_args()

    api_key, configured_inbox = load_config(args.secret_file)
    inbox = args.inbox or configured_inbox
    inbox_id = find_inbox_id(api_key, inbox)
    body = read_body(args)

    result = agentmail_request(
        "POST",
        f"/v0/inboxes/{inbox_id}/messages/send",
        api_key,
        {
            "to": args.to,
            "subject": args.subject,
            "text": body,
        },
    )

    print(
        json.dumps(
            {
                "sent": True,
                "from": inbox,
                "to": args.to,
                "subject": args.subject,
                "message_id": result.get("message_id"),
                "thread_id": result.get("thread_id"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
