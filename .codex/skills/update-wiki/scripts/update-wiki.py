#!/usr/bin/env python3
"""Publish repo-root wiki/ to the GitHub Wiki repository on demand.

The versioned repo-root ``wiki/`` directory is treated as the source tree for the
GitHub Wiki. Publishing intentionally performs minimal translation:

1. Clone ``https://github.com/<owner>/<repo>.wiki.git`` into a temporary local
   directory.
2. Remove the clone content except ``.git``.
3. Copy local ``wiki/`` content into the clone as-is.
4. Commit and push when content changed.
5. Remove the temporary local clone before exiting.

Dry-run mode copies to a caller-provided output directory instead of cloning or
pushing.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=here.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()

    for parent in here.parents:
        if (parent / ".git").exists():
            return parent

    sys.exit("could not locate repository root")


def parse_owner_repo(full: str) -> tuple[str, str]:
    parts = full.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        sys.exit(f"invalid repository name: {full!r}")
    return parts[0], parts[1]


def detect_repository() -> str:
    env_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if env_repo:
        return env_repo

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    url = remote.stdout.strip()
    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?$", url)
    if match:
        return f"{match.group(1)}/{match.group(2)}"

    sys.exit("could not detect repository; set GITHUB_REPOSITORY=owner/repo")


def run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, check=True)


def clone_wiki_repo(remote_repo: str, dest: Path) -> None:
    run(["git", "clone", f"https://github.com/{remote_repo}.wiki.git", str(dest)])


def clean_destination(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for child in dest.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def copy_wiki_tree(source: Path, dest: Path) -> None:
    if not source.is_dir():
        sys.exit(f"wiki source missing: {source}")
    clean_destination(dest)
    for child in source.iterdir():
        target = dest / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def configure_commit_identity(workdir: Path) -> None:
    name = subprocess.run(
        ["git", "config", "--get", "user.name"],
        capture_output=True,
        text=True,
        check=False,
    )
    email = subprocess.run(
        ["git", "config", "--get", "user.email"],
        capture_output=True,
        text=True,
        check=False,
    )
    run(["git", "config", "user.name", name.stdout.strip() or "hw-openclaw-wiki-skill"], cwd=workdir)
    run(
        ["git", "config", "user.email", email.stdout.strip() or "hw-openclaw-wiki-skill@users.noreply.github.com"],
        cwd=workdir,
    )


def commit_and_push(workdir: Path) -> None:
    configure_commit_identity(workdir)
    run(["git", "add", "-A"], cwd=workdir)
    status = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=workdir, check=False)
    if status.returncode == 0:
        print("no wiki changes to publish")
        return
    run(["git", "commit", "-m", "sync wiki from versioned wiki tree"], cwd=workdir)
    run(["git", "push", "origin", "HEAD"], cwd=workdir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None, help="wiki source directory (default: <repo>/wiki)")
    parser.add_argument("--output", type=Path, default=None, help="with --dry-run: write mirror here")
    parser.add_argument("--dry-run", action="store_true", help="copy files only; do not clone or push")
    args = parser.parse_args()

    root = repo_root()
    source = args.source or (root / "wiki")

    if args.dry_run:
        if args.output is None:
            sys.exit("--output is required with --dry-run")
        out = args.output
        copy_wiki_tree(source, out)
        print(f"dry-run: wiki tree copied to {out}")
        return

    full = detect_repository()
    parse_owner_repo(full)

    with tempfile.TemporaryDirectory(prefix="HW-OpenClaw-wiki-") as tmp:
        clone = Path(tmp) / "HW-OpenClaw-wiki"
        clone_wiki_repo(full, clone)
        copy_wiki_tree(source, clone)
        commit_and_push(clone)


if __name__ == "__main__":
    main()
