# -*- coding: utf-8 -*-
"""Publish dist/ to the gh-pages branch — the branch the live site serves.

WHY THIS EXISTS
---------------
Pushing to main does NOT update the site. main holds the source; the workflow
in .github/workflows/pages.yml triggers on gh-pages only. Committing a fix to
main, seeing the push succeed and announcing it as live is a mistake that has
been made — and the researcher looking at the page is the one who finds out.

So publishing is one command that cannot be half-done:

    python tools/publish.py "Rebuild: what changed"

It runs the build first (which runs every check, including the one that no
price reached a page), refuses to publish if anything fails, copies dist/ into
a worktree of gh-pages, pushes, and then waits for the live page to actually
change before it says the word "live".
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BRANCH = "gh-pages"
LIVE = "https://technion-genomics-center.github.io/atgc-submission-forms/"
WORKTREE = ROOT / ".ghpages"

# Only these reach the public branch. Same list the workflow enforces, checked
# here first so a bad file never leaves this machine.
ALLOWED = {".html", ".css", ".js", ".jpg", ".png", ".svg", ".ico"}


def run(*args, cwd=ROOT, check=True):
    # The repo lives on a UNC share, so a fresh worktree trips git's
    # dubious-ownership guard. Scope the exception to this process rather than
    # writing it into the user's global config.
    if args and args[0] == "git":
        args = ("git", "-c", "safe.directory=*") + args[1:]
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"$ {' '.join(args)}\n{r.stdout}{r.stderr}")
    return r.stdout.strip()


def build():
    r = subprocess.run([sys.executable, "build.py"], cwd=ROOT,
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode or "all build checks passed" not in r.stdout:
        sys.exit("build failed — nothing published")


def live_fingerprint():
    """Whatever version string the live page is currently serving."""
    try:
        with urllib.request.urlopen(LIVE + "rnaseq/", timeout=20) as f:
            html = f.read().decode("utf-8", "replace")
    except Exception as e:                                  # noqa: BLE001
        return f"unreachable: {e}"
    import re
    m = re.search(r"form\.js\?v=([a-f0-9]+)", html)
    return m.group(1) if m else "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("message", help='e.g. "Rebuild: mailto button removed"')
    args = ap.parse_args()

    build()

    bad = [p for p in DIST.rglob("*")
           if p.is_file() and p.suffix.lower() not in ALLOWED
           and p.name != ".nojekyll"]
    if bad:
        sys.exit("refusing to publish, these are not pages or assets:\n  " +
                 "\n  ".join(str(p.relative_to(DIST)) for p in bad))

    before = live_fingerprint()
    want = None
    import re
    m = re.search(r"form\.js\?v=([a-f0-9]+)",
                  (DIST / "rnaseq" / "index.html").read_text(encoding="utf-8"))
    want = m.group(1) if m else None
    print(f"live now : {before}\nbuilt    : {want}")
    if before == want:
        print("nothing to publish — the live site already serves this build")
        return

    if WORKTREE.exists():
        run("git", "worktree", "remove", "--force", str(WORKTREE), check=False)
        shutil.rmtree(WORKTREE, ignore_errors=True)
    run("git", "fetch", "origin", BRANCH)
    run("git", "worktree", "add", str(WORKTREE), f"origin/{BRANCH}",
        "--detach")

    try:
        # Replace, don't merge: a page deleted from dist/ must disappear from
        # the site, not linger because nothing overwrote it.
        for p in WORKTREE.iterdir():
            if p.name == ".git":
                continue
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        shutil.copytree(DIST, WORKTREE, dirs_exist_ok=True)
        (WORKTREE / ".nojekyll").touch()

        run("git", "add", "-A", cwd=WORKTREE)
        if not run("git", "status", "--porcelain", cwd=WORKTREE):
            print("gh-pages already identical — nothing to push")
            return
        run("git", "-c", "core.autocrlf=false", "commit", "-q",
            "-m", args.message, cwd=WORKTREE)
        run("git", "push", "-q", "origin", f"HEAD:{BRANCH}", cwd=WORKTREE)
        print(f"pushed to {BRANCH}")
    finally:
        run("git", "worktree", "remove", "--force", str(WORKTREE), check=False)

    print("waiting for the deploy", end="", flush=True)
    for _ in range(40):                     # up to ~10 minutes
        time.sleep(15)
        print(".", end="", flush=True)
        if live_fingerprint() == want:
            print(f"\nLIVE — {LIVE} now serves {want}")
            return
    sys.exit("\nthe deploy has not appeared yet. Check the Actions tab; the "
             "push itself succeeded.")


if __name__ == "__main__":
    main()
