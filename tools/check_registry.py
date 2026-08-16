# -*- coding: utf-8 -*-
"""Check the application registry against reality and against doc 05 §12.

Three ways this can silently rot, so all three are checked:
  * a workbook path that does not resolve (a folder was renamed)
  * a surveyed workbook that no entry accounts for (a form would vanish)
  * counts that no longer match doc 05 §12's buckets
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.applications import (APPLICATIONS, BUILD, MERGED, WITHDRAWN,
                               SUPERSEDED, published)
from survey_workbooks import workbooks

# doc 05 §12 buckets, and what they add up to:
#   §12.1  panel-bearing            13  (11 existing workbooks, shotgun, Illumina scRNA-seq)
#   §12.2  question, but no panel    2  (miRNA-seq, Nanopore)
#   §12.3  question dropped          1  (Extraction)
#   §12.4  withdrawn or merged       4  (CEL-seq2, Infinium, RNAseq-extr, Metagenomics-extr)
#   §12.5  no question at all        2  (CLA, DNA/RNA Q&Q) — Infinium withdrawn
# Published pages = 13 + 2 + 1 + 2 = 18, from 20 existing workbooks (20 - 3
# not built = 17) plus two forms with no workbook of their own: shotgun, which
# borrows the DNA-seq layout, and Illumina scRNA-seq, which borrows 10X's.
#
# Qubit is NOT here. PH-12/PH-24 say it becomes an application eventually;
# Nitsan pulled it from this round on 2026-08-16, so it has no slug, no page and
# no routing row. Adding it later means +1 built page and no change to the panel
# count, since quantification has no analysis.
#
# These are not a tally of the registry — that would make the check agree with
# itself. They are doc 05 §12's numbers, and a mismatch means the registry and
# the spec have drifted. Move them only alongside the doc.
EXPECTED_PANEL = 13         # + Illumina scRNA-seq (PH-25), 2026-08-16
EXPECTED_BUILT_PAGES = 18   # + Illumina scRNA-seq (PH-25), 2026-08-16
EXPECTED_EXISTING_WORKBOOKS = 20   # what the survey walks

failures = []


def fail(msg):
    failures.append(msg)
    print(f"  FAIL  {msg}")


print("1. workbook paths resolve")
for a in APPLICATIONS:
    wb = a.get("workbook")
    if wb is None:
        print(f"  ok    {a['name']}: no workbook (built from "
              f"{a.get('layout_from', '?')})")
        continue
    p = Path(a["root"]) / wb
    if p.exists():
        print(f"  ok    {a['name']}")
    else:
        fail(f"{a['name']}: missing {p}")

print("\n2. every surveyed workbook is accounted for")
registered = {Path(a["workbook"]).name for a in APPLICATIONS if a.get("workbook")}
registered |= set(SUPERSEDED)
for path in workbooks():
    name = Path(path).name
    if name in registered:
        continue
    fail(f"surveyed but not in the registry: {name}")
else:
    if not failures:
        print(f"  ok    all {len(list(workbooks()))} surveyed workbooks registered")

print("\n3. slugs are unique and URL-safe")
slugs = [a["slug"] for a in published()]
if len(slugs) != len(set(slugs)):
    fail(f"duplicate slugs: {[s for s in slugs if slugs.count(s) > 1]}")
for s in slugs:
    if s != s.lower() or " " in s or not s.replace("-", "").isalnum():
        fail(f"slug not URL-safe: {s!r}")
if not any("slug" in f for f in failures):
    print(f"  ok    {len(slugs)} slugs, all unique and URL-safe")

print("\n4. counts reconcile with doc 05 §12")
built = len(published())
merged = sum(a["status"] == MERGED for a in APPLICATIONS)
withdrawn = sum(a["status"] == WITHDRAWN for a in APPLICATIONS)
existing = sum(1 for a in APPLICATIONS if a.get("workbook"))
print(f"  built pages           {built}")
print(f"  merged away           {merged}")
print(f"  withdrawn             {withdrawn}")
print(f"  existing workbooks    {existing}  (+{len(SUPERSEDED)} superseded)")
if built != EXPECTED_BUILT_PAGES:
    fail(f"expected {EXPECTED_BUILT_PAGES} built pages, registry has {built}")
if existing != EXPECTED_EXISTING_WORKBOOKS:
    fail(f"expected {EXPECTED_EXISTING_WORKBOOKS} existing workbooks, "
         f"registry references {existing}")

print("\n5. analysis coverage")
with_panel = [a for a in published() if a.get("analysis")]
no_panel = [a for a in published() if not a.get("analysis")]
print(f"  panel      {len(with_panel)}: {', '.join(a['slug'] for a in with_panel)}")
print(f"  no panel   {len(no_panel)}: {', '.join(a['slug'] for a in no_panel)}")
if len(with_panel) != EXPECTED_PANEL:
    fail(f"expected {EXPECTED_PANEL} panel-bearing forms (doc 05 §12.1), "
         f"registry has {len(with_panel)}")

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    sys.exit(1)
print("all checks passed")
