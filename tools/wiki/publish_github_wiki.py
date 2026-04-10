#!/usr/bin/env python3
"""Publish the versioned wiki/ tree to the GitHub Wiki git repository.

Markdown under ``wiki/`` uses normal nested paths (``rtl/index.md``, …) so it is
easy to browse in the main repository. **GitHub Wiki does not work that way:**
page identity is the file basename, so many ``index.md`` files collide, and
links that look like ``folder/page`` or end in ``.md`` often open **raw**
markdown instead of the wiki renderer.

This tool therefore **flattens** the tree when publishing:

1. Clones ``https://github.com/<owner>/<repo>.wiki.git`` (or writes ``--output``).
2. Emits **one wiki page per source file** at the clone root, using a **unique
   slug**: relative path with ``/`` replaced by ``-`` (e.g.
   ``rtl/fifo/index.md`` → ``rtl-fifo-index.md``).
3. Rewrites internal links to ``https://github.com/<owner>/<repo>/wiki/<slug>``
   (no ``.md``, no nested path in the URL) so clicks stay in the Wiki UI.
4. Writes ``_Footer.md`` and commits/pushes when needed.

Configuration (CI):

- ``GITHUB_REPOSITORY`` — ``owner/repo``
- ``WIKI_SYNC_TOKEN`` — token with push access to the wiki remote

Local: ``--dry-run`` / ``--output`` (output directory must be new or empty).
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
from urllib.parse import quote

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


def source_rel_to_slug(rel_posix: str) -> str:
    """Map ``wiki/`` relative path to GitHub Wiki page slug (filename stem)."""
    if rel_posix == "Home.md":
        return "Home"
    if rel_posix == "_Sidebar.md":
        return "_Sidebar"
    if not rel_posix.endswith(".md"):
        sys.exit(f"wiki publish: expected .md file, got {rel_posix!r}")
    stem = rel_posix[: -len(".md")]
    return stem.replace("/", "-")


def page_path_to_slug(page_path: str) -> str:
    """Map resolved page path (no .md, posix slashes) to the same slug rule."""
    if not page_path or page_path == "Home":
        return "Home"
    return page_path.replace("/", "-")


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

    if path_part.endswith("/"):
        path_part = path_part.rstrip("/") + "/index.md"

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
    slug = page_path_to_slug(page_path)
    safe = quote(slug, safe="-")
    return f"{base}/{safe}{anchor}"


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

Pages here use **one flat wiki page per source file**, with a unique name derived
from the path (slashes become hyphens) so GitHub Wiki does not merge conflicting
``index.md`` files. Links use ``/wiki/<slug>`` URLs so navigation stays in the
rendered wiki view.
"""


def _prepare_dest(dest: Path, *, clean_dest: bool) -> None:
    if clean_dest:
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


def flatten_publish(source: Path, dest: Path, owner: str, repo: str, *, clean_dest: bool) -> None:
    if not source.is_dir():
        sys.exit(f"wiki source missing: {source}")

    md_sources = sorted(source.rglob("*.md"))
    slug_to_rel: dict[str, str] = {}
    for path in md_sources:
        rel = path.relative_to(source).as_posix()
        slug = source_rel_to_slug(rel)
        if slug in slug_to_rel:
            sys.exit(
                "wiki publish: slug collision for "
                f"{slug!r}: {slug_to_rel[slug]} and {rel}"
            )
        slug_to_rel[slug] = rel

    _prepare_dest(dest, clean_dest=clean_dest)

    for path in md_sources:
        rel = path.relative_to(source).as_posix()
        slug = source_rel_to_slug(rel)
        text = path.read_text(encoding="utf-8")
        out = rewrite_markdown_links(text, rel, owner, repo)
        (dest / f"{slug}.md").write_text(out, encoding="utf-8", newline="\n")

    (dest / "_Footer.md").write_text(render_footer(owner, repo), encoding="utf-8", newline="\n")


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
        flatten_publish(source, out, owner, repo, clean_dest=False)
        print(f"dry-run: transformed wiki written to {out}")
        return

    token = os.environ.get("WIKI_SYNC_TOKEN", "").strip()
    if not token:
        sys.exit("WIKI_SYNC_TOKEN is not set")

    with tempfile.TemporaryDirectory(prefix="hw-openclaw-wiki-") as tmp:
        clone = Path(tmp) / "wiki.git"
        plain_url = f"https://github.com/{full}.wiki.git"
        _git(token, ["clone", plain_url, str(clone)])
        flatten_publish(source, clone, owner, repo, clean_dest=True)
        git_commit_push(clone, token, full)


if __name__ == "__main__":
    main()
