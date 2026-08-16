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


def is_live(rel, want):
    """Is the live site serving exactly these bytes for this file?

    Byte comparison of a file we KNOW changed, rather than a version string.
    The earlier version fingerprinted form.js, which is wrong whenever the
    change is in the page rather than the script.
    """
    try:
        with urllib.request.urlopen(LIVE + rel.replace("\\", "/"), timeout=20) as f:
            got = f.read()
    except Exception:                                       # noqa: BLE001
        return False
    return got.replace(b"\r\n", b"\n") == want.replace(b"\r\n", b"\n")


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

    # Deliberately NO early exit on a fingerprint.
    #
    # This used to compare form.js?v= against the live page and stop if they
    # matched. That is wrong whenever the change is in a page rather than in a
    # script: editing data/applications.py rewrote six dropdown options and
    # left form.js untouched, so the publisher announced "nothing to publish"
    # about a build that genuinely differed. A publisher that can be fooled
    # into skipping is worse than none, because it is believed.
    #
    # git decides what changed, over the real file set. The live check then
    # follows git rather than guessing.
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
        status = run("git", "status", "--porcelain", cwd=WORKTREE)
        if not status:
            print("gh-pages already identical — nothing to push")
            return
        changed = [ln[3:].strip().strip('"') for ln in status.splitlines()
                   if not ln.lstrip().startswith("D")]
        print(f"{len(changed)} file(s) changed: " + ", ".join(changed[:6])
              + (" …" if len(changed) > 6 else ""))
        run("git", "-c", "core.autocrlf=false", "commit", "-q",
            "-m", args.message, cwd=WORKTREE)
        run("git", "push", "-q", "origin", f"HEAD:{BRANCH}", cwd=WORKTREE)
        print(f"pushed to {BRANCH}")
    finally:
        run("git", "worktree", "remove", "--force", str(WORKTREE), check=False)

    # Watch a file git says actually changed, and compare it byte for byte.
    probe = next((c for c in changed if c.endswith((".html", ".js", ".css"))), None)
    if not probe or not (DIST / probe).exists():
        print("pushed; no text file to verify against")
        return
    want = (DIST / probe).read_bytes()
    print(f"waiting for the deploy (watching {probe})", end="", flush=True)
    for _ in range(40):                     # up to ~10 minutes
        time.sleep(15)
        print(".", end="", flush=True)
        if is_live(probe, want):
            print(f"\nLIVE — {LIVE} now serves the build just made")
            return
    sys.exit("\nthe deploy has not appeared yet. Check the Actions tab; the "
             "push itself succeeded.")


if __name__ == "__main__":
    main()
