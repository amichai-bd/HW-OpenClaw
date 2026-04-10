#!/usr/bin/env python3
"""Publish the versioned wiki/ tree to the GitHub Wiki git repository.

The GitHub Wiki web UI expects page links in wiki URL form. Markdown in the
main repository intentionally uses relative ``*.md`` paths so the same files
render sensibly when browsed under ``wiki/`` on GitHub. This tool:

1. Clones ``https://github.com/<owner>/<repo>.wiki.git`` (or uses ``--output``).
2. Copies the source ``wiki/`` tree into the clone (excluding ``.git``).
3. Rewrites internal markdown links to absolute ``https://github.com/.../wiki/...``
   targets so sidebar, footer, and cross-page navigation work in the Wiki UI.
4. Writes a generated ``_Footer.md`` that points readers at the source tree.
5. Commits and pushes when there are changes (CI), unless ``--dry-run``.

Configuration is passed via environment variables for CI:

- ``GITHUB_REPOSITORY`` — ``owner/repo`` (set automatically in GitHub Actions).
- ``WIKI_SYNC_TOKEN`` — token with push access to the wiki remote (use  ``secrets.GITHUB_TOKEN`` in Actions for the same repository).

Optional flags for local debugging:

- ``--dry-run`` — do not clone or push; write the transformed tree to ``--output``.
- ``--source DIR`` — default: ``<repo-root>/wiki``.
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

MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

_ASSET_EXT = frozenset(
    {
        "png",
        "jpg",
        "jpeg",
        "gif",
        "svg",
        "webp",
        "css",
        "js",
        "json",
        "pdf",
        "zip",
        "tar",
        "gz",
        "ico",
        "bmp",
        "ttf",
        "woff",
        "woff2",
        "eot",
        "otf",
    }
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def should_rewrite_target(href: str) -> bool:
    href = href.strip()
    if not href or href.startswith("#"):
        return False
    if href.startswith(("http://", "https://", "mailto:")):
        return False
    if href.startswith("/"):
        return False
    path_only = href.split("#", 1)[0].split("?", 1)[0].strip()
    if not path_only:
        return False
    if path_only.startswith("/"):
        return False
    if path_only.endswith("/"):
        return True
    base = os.path.basename(path_only)
    if "." in base:
        ext = base.rsplit(".", 1)[-1].lower()
        if ext == "md":
            return True
        if ext in _ASSET_EXT:
            return False
        return False
    return True


def resolve_wiki_page_path(current_md_relative: str, href: str) -> tuple[str, str]:
    """Return (wiki page path without .md suffix, anchor including # if any)."""
    path_part, sep, anchor = href.partition("#")
    anchor_suffix = f"#{anchor}" if sep else ""
    path_part = path_part.strip()
    if not path_part:
        return "", anchor_suffix

    cur_dir = os.path.dirname(current_md_relative)
    if cur_dir == "":
        cur_dir = "."
    norm = os.path.normpath(os.path.join(cur_dir, path_part))
    norm = norm.replace("\\", "/")
    if norm.startswith("../") or norm == "..":
        raise ValueError(f"link escapes wiki root: {href!r} from {current_md_relative!r}")
    if norm == ".":
        return "Home", anchor_suffix
    if norm.endswith(".md"):
        norm = norm[: -len(".md")]
    return norm, anchor_suffix


def wiki_page_url(owner: str, repo: str, page_path: str, anchor: str) -> str:
    base = f"https://github.com/{owner}/{repo}/wiki"
    if not page_path or page_path == "Home":
        return f"{base}/Home{anchor}"
    return f"{base}/{page_path}{anchor}"


def rewrite_markdown_links(content: str, current_md_relative: str, owner: str, repo: str) -> str:
    def repl(match: re.Match[str]) -> str:
        text, href = match.group(1), match.group(2)
        if not should_rewrite_target(href):
            return match.group(0)
        try:
            page_path, anchor = resolve_wiki_page_path(current_md_relative, href)
        except ValueError:
            return match.group(0)
        if not page_path and not anchor:
            return match.group(0)
        if not page_path and anchor:
            return f"[{text}]({anchor})"
        url = wiki_page_url(owner, repo, page_path, anchor)
        return f"[{text}]({url})"

    return MD_LINK_RE.sub(repl, content)


def render_footer(owner: str, repo: str) -> str:
    full = f"{owner}/{repo}"
    return f"""### Source of truth

Versioned markdown lives in
[`{full}` / `wiki/`](https://github.com/{full}/tree/main/wiki)
on branch `main`. This GitHub Wiki is **generated** from that tree on each
eligible push; edit there (pull requests) instead of the Wiki web editor, or
changes may be overwritten on the next sync.

Internal links use GitHub Wiki URLs so the sidebar and in-page navigation work
in the Wiki UI.
"""


def transform_tree(dest: Path, owner: str, repo: str) -> None:
    md_files = sorted(dest.rglob("*.md"))
    for path in md_files:
        rel = path.relative_to(dest).as_posix()
        text = path.read_text(encoding="utf-8")
        out = rewrite_markdown_links(text, rel, owner, repo)
        path.write_text(out, encoding="utf-8", newline="\n")
    (dest / "_Footer.md").write_text(render_footer(owner, repo), encoding="utf-8", newline="\n")


def _copy_wiki_entries(source: Path, dest: Path) -> None:
    for entry in source.iterdir():
        if entry.name.startswith("."):
            continue
        target = dest / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)


def copy_source_tree(source: Path, dest: Path, *, destructive: bool) -> None:
    if not source.is_dir():
        sys.exit(f"wiki source missing: {source}")
    if destructive:
        for child in dest.iterdir():
            if child.name == ".git":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        if dest.exists() and any(dest.iterdir()):
            sys.exit(f"refusing dry-run: destination {dest} is not empty (pick a new path or remove files)")
        dest.mkdir(parents=True, exist_ok=True)
    _copy_wiki_entries(source, dest)


def _git(token: str, args: list[str], *, cwd: Path | None = None) -> None:
    """Run git with Authorization header (avoid embedding the token in remote URLs)."""
    header = f"AUTHORIZATION: token {token}"
    subprocess.run(["git", "-c", f"http.extraHeader={header}", *args], cwd=cwd, check=True)


def git_commit_push(workdir: Path, token: str, remote_repo: str) -> None:
    def run_local(cmd: list[str]) -> None:
        subprocess.run(cmd, cwd=workdir, check=True)

    run_local(["git", "config", "user.name", "github-actions[bot]"])
    run_local(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    run_local(["git", "add", "-A"])
    st = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=workdir)
    if st.returncode == 0:
        print("no wiki changes to publish")
        return
    run_local(["git", "commit", "-m", "sync wiki from main repository (automated)"])
    plain_url = f"https://github.com/{remote_repo}.wiki.git"
    _git(token, ["push", plain_url, "HEAD"], cwd=workdir)


def parse_owner_repo(full: str) -> tuple[str, str]:
    parts = full.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        sys.exit(f"invalid GITHUB_REPOSITORY: {full!r}")
    return parts[0], parts[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--source",
        type=Path,
        default=None,
        help="wiki source directory (default: <repo>/wiki)",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="with --dry-run: write transformed wiki here instead of cloning",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="transform files only; do not clone or push",
    )
    args = ap.parse_args()

    root = repo_root()
    source = args.source or (root / "wiki")
    full = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not full:
        if args.dry_run:
            full = "OWNER/REPO"
        else:
            sys.exit("GITHUB_REPOSITORY is not set")
    owner, repo = parse_owner_repo(full)

    if args.dry_run:
        out = args.output
        if out is None:
            out = Path(tempfile.mkdtemp(prefix="wiki-publish-"))
        copy_source_tree(source, out, destructive=False)
        transform_tree(out, owner, repo)
        print(f"dry-run: transformed wiki written to {out}")
        return

    token = os.environ.get("WIKI_SYNC_TOKEN", "").strip()
    if not token:
        sys.exit("WIKI_SYNC_TOKEN is not set")

    with tempfile.TemporaryDirectory(prefix="hw-openclaw-wiki-") as tmp:
        clone = Path(tmp) / "wiki.git"
        plain_url = f"https://github.com/{full}.wiki.git"
        _git(token, ["clone", plain_url, str(clone)])
        copy_source_tree(source, clone, destructive=True)
        transform_tree(clone, owner, repo)
        git_commit_push(clone, token, full)


if __name__ == "__main__":
    main()
