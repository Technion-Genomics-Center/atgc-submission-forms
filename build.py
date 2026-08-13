# -*- coding: utf-8 -*-
"""Build the submission-form site: one page per application, plus a landing page.

    python build.py            # build, then verify
    python build.py --report   # build and print everything that was changed

Output layout — each directory is a PUBLIC, PERMANENT URL (doc 03, ARCHITECTURE):

    dist/index.html                     landing page, lists every application
    dist/<slug>/index.html              one form per application
    dist/assets/                        shared css, js, logos

Assets are SHARED rather than inlined per page. Eighteen self-contained copies
of the same css, js and a 210 KB logo would be 4 MB of duplication, and the
researcher reaches these by URL rather than by saving a file. It still works
offline once served: nothing here fetches anything at runtime.

NEVER hand-edit anything under dist/ — it is regenerated wholesale.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from data.applications import SITE, SITE_BIOINFORMATICS, published
from tools.schema import all_specs

DIST = ROOT / "dist"

# Anything that looks like money must never reach a built page (D12).
# Matched precisely: a bare case-insensitive "NIS" also hits "orgaNISm", and a
# check that cries wolf gets switched off, which is worse than not having it.
PRICE_PATTERNS = (
    r"₪",
    r"\bNIS\b",               # case-sensitive: bare "nis" hits "orgaNISm"
    r"price_technion", r"price_non_technion",
    r"\bprices?\b",
    r"\b\d[\d,]*\.\d{2}\b",   # 1234.00 - a formatted amount
)

# Only the currency code is case-sensitive; everything else is not.
CASE_SENSITIVE = (r"\bNIS\b",)


def asset_version():
    """Short hash of the shared assets, used to bust caches.

    Without it a researcher who used the form last week gets last week's
    JavaScript from cache after we publish a fix, and the bug looks unfixed.
    """
    import hashlib
    h = hashlib.sha256()
    for name in sorted(("tokens.css", "form.css", "form.js", "xlsx.js", "xlsx_read.js", "quote.js", "logo_data.js")):
        h.update((ROOT / "assets" / name).read_bytes())
    return h.hexdigest()[:8]


VER = None


def render(spec):
    tpl = (ROOT / "template.html").read_text(encoding="utf-8")
    payload = dict(spec)
    payload["bioinformatics_url"] = SITE_BIOINFORMATICS
    payload.pop("report", None)          # build-time only, never shipped
    return (tpl
            .replace("{{APP_NAME}}", spec["name"])
            .replace("{{SLUG}}", spec["slug"])
            .replace("{{GROUP}}", spec.get("group", "transcriptomics"))
            .replace("{{GUIDELINES}}", spec.get("site") or SITE)
            .replace("{{SITE}}", SITE)
            .replace("{{VER}}", VER)
            .replace("{{SPEC_JSON}}", json.dumps(payload, ensure_ascii=False)))


def landing(specs):
    """The menu, grouped and coloured exactly as the website groups them.

    Only reached by someone who arrived without an application in mind — every
    website page links straight to its own form. Mirroring the site's sections
    means they are looking for the same heading in the same colour.
    """
    from data.applications import APP_GROUPS

    titles = {"transcriptomics": "Transcriptomics", "genomics": "Genomics",
              "epigenomics": "Epigenomics", "additional": "Additional services"}
    by_slug = {s["slug"]: s for s in specs}

    sections = []
    for group, slugs in APP_GROUPS.items():
        items = [by_slug[sl] for sl in slugs if sl in by_slug]
        if not items:
            continue
        links = "\n".join(
            f'      <li><a href="{i["slug"]}/">{i["name"]}</a></li>'
            for i in sorted(items, key=lambda i: i["name"]))
        sections.append(
            f'  <section class="group group-{group}">\n'
            f'    <h2>{titles.get(group, group)}</h2>\n'
            f'    <ul class="app-list">\n{links}\n    </ul>\n'
            f'  </section>')

    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sample submission forms — Azrieli Technion Genomics Center</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700&family=Roboto:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="assets/tokens.css?v={VER}">
<link rel="stylesheet" href="assets/form.css?v={VER}">
<header class="masthead">
  <img class="logo" src="assets/atgc_logo.jpg"
       alt="Azrieli Technion Genomics Center">
  <div class="masthead-text">
    <h1>Sample Submission Forms</h1>
  </div>
</header>
<div class="atgc-rule"></div>
<p class="flow-note">
  Choose your application. If you reached this page from an application page on
  our website, that page links straight to the right form.
</p>
{chr(10).join(sections)}
<footer>
  <img src="assets/technion_logo.png" alt="Technion" class="tech-logo">
  <p>Azrieli Technion Genomics Center &middot;
  <a href="{SITE}" target="_blank" rel="noopener">atgc.net.technion.ac.il</a></p>
</footer>
<script>
// An older-style ?app=<slug> link redirects to its canonical directory, so
// anything already published keeps working.
var slug = new URLSearchParams(location.search).get('app');
if (slug && /^[a-z0-9-]+$/.test(slug)) location.replace(slug + '/');
</script>
"""


def check_no_prices(paths):
    """A price on any page is as public as a price on all of them."""
    import re
    bad = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        for pat in PRICE_PATTERNS:
            m = re.search(pat, text, 0 if pat in CASE_SENSITIVE else re.I)
            if m:
                bad.append((p.relative_to(DIST), pat, m.group(0)))
    return bad


def check_js_syntax(path):
    """Catch a quoted string broken across a newline.

    Worth having because the build otherwise reports "all checks passed" for a
    page whose JavaScript does not parse: every check here reads the HTML, and a
    dead script leaves the markup perfectly valid.

    A ' or " literal may not span lines in JS (only backticks may). The scanner
    has to know about comments and REGEX LITERALS too — /"/g contains a quote
    that opens nothing, and flagging it would be a false alarm. False alarms are
    how a check ends up switched off, so it is worth the extra state.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    problems = []
    state = None          # None | "'" | '"' | '`' | '//' | '/*' | 'regex'
    line = 1
    prev = ""             # last non-space character before the cursor
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if ch == "\n":
            if state in ("'", '"'):
                problems.append((path.name, line, state, lines[line - 1].strip()[:60]))
                state = None
            elif state in ("//", "regex"):
                state = None      # neither may span a line
            line += 1
            i += 1
            continue

        if state in ("'", '"', "`", "regex"):
            if ch == "\\":
                i += 2
                continue
            if (state == "regex" and ch == "/") or ch == state:
                state = None
            i += 1
            continue

        if state == "//":
            i += 1
            continue

        if state == "/*":
            if ch == "*" and nxt == "/":
                state = None
                i += 2
                continue
            i += 1
            continue

        if ch == "/" and nxt == "/":
            state = "//"; i += 2; continue
        if ch == "/" and nxt == "*":
            state = "/*"; i += 2; continue
        # A '/' is a regex only where a value may start; after an identifier or
        # a closing bracket it is division.
        if ch == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%~^<>"):
            state = "regex"; i += 1; continue
        if ch in "'\"`":
            state = ch

        if not ch.isspace():
            prev = ch
        i += 1
    return problems


def check_no_typos(paths):
    from tools.schema import TYPOS
    bad = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        for wrong in TYPOS:
            if wrong in text:
                bad.append((p.relative_to(DIST), wrong))
    return bad


def main():
    global VER
    VER = asset_version()
    specs, missing = all_specs()
    if missing:
        print(f"NO SOURCE WORKBOOK for: {missing}")
        return 1

    # Clear the CONTENTS rather than the directory itself. A dev server run
    # from inside dist/ holds a handle on the directory, and rmtree(DIST) then
    # fails with WinError 32 — which has nothing to do with the build being
    # wrong, and is a miserable thing to debug twice.
    DIST.mkdir(exist_ok=True)
    for child in DIST.iterdir():
        try:
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        except PermissionError as exc:
            print(f"  cannot remove {child.name}: {exc.strerror}. "
                  f"Stop anything serving dist/ and rebuild.")
            return 1

    shutil.copytree(ROOT / "assets", DIST / "assets")

    written = []
    for spec in specs:
        out = DIST / spec["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(spec), encoding="utf-8")
        written.append(out)

    index = DIST / "index.html"
    index.write_text(landing(specs), encoding="utf-8")
    written.append(index)

    print(f"built {len(written)} pages into {DIST}")

    # ── verification, doc 03 VERIFY AND SHOW ME ─────────────────────────────
    failures = 0

    prices = check_no_prices(written)
    print(f"\nprice check   : {len(prices)} hits across {len(written)} pages")
    for path, pat, hit in prices[:10]:
        print(f"  FAIL {path} matched {pat} -> {hit!r}")
    failures += len(prices)

    typos = check_no_typos(written)
    print(f"typo check    : {len(typos)} hits")
    for path, wrong in typos[:10]:
        print(f"  FAIL {path} contains {wrong!r}")
    failures += len(typos)

    js_problems = []
    for js in ("form.js", "xlsx.js", "xlsx_read.js", "quote.js"):
        js_problems += check_js_syntax(ROOT / "assets" / js)
    print(f"js syntax     : {len(js_problems)} unterminated string(s)")
    for fname, n, q, text in js_problems[:10]:
        print(f"  FAIL {fname}:{n} unbalanced {q} -> {text}")
    failures += len(js_problems)

    # A recipient with no TLD looks fine in a spreadsheet and bounces in a mail
    # client, taking the submission with it. Check the shape of every address.
    import re as _re
    ADDR = _re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
    bad_addr = []
    for spec in specs:
        for route in spec.get("routing", []):
            for kind in ("to", "cc"):
                for addr in route.get(kind, []):
                    if not ADDR.match(addr):
                        bad_addr.append((spec["slug"], route["lab"], kind, addr))
    # Structure is not enough: "fdoron@techion.ac.il" is a perfectly well-formed
    # address at a domain that does not exist. Every ATGC recipient is at
    # technion.ac.il, so anything else is worth a second look rather than a
    # silent bounce.
    odd_domain = []
    for spec in specs:
        for route in spec.get("routing", []):
            for kind in ("to", "cc"):
                for addr in route.get(kind, []):
                    if not ADDR.match(addr):
                        continue
                    domain = addr.rsplit("@", 1)[-1].lower()
                    if domain != "technion.ac.il" and not domain.endswith(".technion.ac.il"):
                        odd_domain.append((spec["slug"], route["lab"], addr))

    print(f"recipients    : {len(bad_addr)} malformed address(es) in data/routing.csv")
    for slug, lab, kind, addr in bad_addr[:12]:
        print(f"  FAIL {slug} / {lab} / {kind}: {addr!r} is not a valid address")
    failures += len(bad_addr)

    if odd_domain:
        seen = sorted({a for _, _, a in odd_domain})
        print(f"                {len(odd_domain)} recipient(s) not at technion.ac.il "
              f"— check these are right: {', '.join(seen)}")

    unrouted = [s["slug"] for s in specs if not s.get("routing")]
    print(f"routing       : {len(specs) - len(unrouted)}/{len(specs)} applications "
          f"have at least one lab")
    for slug in unrouted:
        print(f"  FAIL {slug} has no lab with recipients in data/routing.csv")
    failures += len(unrouted)

    single = [(s["slug"], s["routing"][0]["lab"]) for s in specs
              if len(s.get("routing", [])) == 1]
    if single:
        print(f"                {len(single)} run at one lab only: "
              + ", ".join(f"{a} -> {l}" for a, l in single))

    # dist/ is the PUBLIC site. Nothing that is not a page or a shared asset
    # belongs in it — no data file, no script, no notes. The admin tool lives
    # outside this folder entirely (../FormAdmin), but a stray copy or an
    # export left behind would be served to the world without anyone noticing.
    ALLOWED = {".html", ".css", ".js", ".jpg", ".png", ".svg", ".ico"}
    strays = [p.relative_to(DIST) for p in DIST.rglob("*")
              if p.is_file() and p.suffix.lower() not in ALLOWED]
    print(f"publish scope : {len(strays)} file(s) in dist/ that should not be public")
    for f in strays[:10]:
        print(f"  FAIL {f} is not a page or an asset — move it out of dist/")
    failures += len(strays)

    pending = {}
    for spec in specs:
        for term in spec["report"].get("needs_catalog", []):
            pending.setdefault(term, []).append(spec["slug"])
    if pending:
        print(f"catalog gaps  : {len(pending)} offered service(s) with no catalog entry")
        for term, slugs in sorted(pending.items()):
            print(f"                {term} — on {', '.join(slugs)}; cannot be quoted yet")

    retired_hits = []
    for p in written:
        text = p.read_text(encoding="utf-8").lower()
        for term in ("miseq", "p3 50 cycles"):
            if term in text:
                retired_hits.append((p.relative_to(DIST), term))
    print(f"retired check : {len(retired_hits)} hits")
    for path, term in retired_hits[:10]:
        print(f"  FAIL {path} contains {term!r}")
    failures += len(retired_hits)

    if "--report" in sys.argv:
        print("\n── what the build changed ──")
        for s in specs:
            r = s["report"]
            if not any(r.values()):
                continue
            print(f"\n{s['slug']}")
            for kind in ("typos", "renamed_columns", "added"):
                for item in r[kind]:
                    print(f"   {kind:<16} {item}")
            print(f"   {'retired':<16} {len(r['retired'])} terms removed")

    print()
    if failures:
        print(f"{failures} FAILURE(S)")
        return 1
    print("all build checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
