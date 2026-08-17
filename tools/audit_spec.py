# -*- coding: utf-8 -*-
"""Check the built forms against docs/05_Analysis_Intake_Spec.md.

Written after §11.2 (the sample table swapping when extraction is wanted) was
found to be fully specified and never built. The spec is prose, so nothing was
enforcing it; this walks the decisions that CAN be checked mechanically and
reports what is missing.

    python tools/audit_spec.py

Not a substitute for reading the spec. It checks that each decision left a
trace in the code or the built pages — not that the trace is correct.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

JS = (ROOT / "assets" / "form.js").read_text(encoding="utf-8")
# Source is wrapped, so a phrase from the spec can straddle a line break.
# Comparing against a whitespace-flattened copy stops that reading as a gap.
FLAT = re.sub(r"\s+", " ", JS)
DIST = ROOT / "dist"


def spec_of(slug):
    page = DIST / slug / "index.html"
    if not page.exists():
        return None
    # Greedy to the LAST '};' on the line: the spec is one long line ending in
    # '};</script>', and a lazy match stops at the first nested object.
    m = re.search(r"window\.APP = (\{.*\});", page.read_text(encoding="utf-8"))
    return json.loads(m.group(1)) if m else None


# (section, what the spec says, how to tell it was built)
CHECKS = [
    ("§1", "consultation wording used verbatim",
     lambda: "can be submitted only after scheduling a consultation" in FLAT),
    ("§1", "consultation names Liat first",
     lambda: JS.index("Liat Linde") < JS.index("Nitsan Fourier")),
    ("§1", "bioinformatics section is last",
     lambda: (lambda s: s and "<section id=\"bioinformatics\">" in
              (DIST / "rnaseq" / "index.html").read_text(encoding="utf-8"))(1)),
    ("§1", "NCBI note on reference and annotation fields",
     lambda: "most up-to-date genome and annotation" in JS),

    ("§2.1", "RNA-seq branches on the rRNA-removal-bacteria prep",
     lambda: "rRNA removal bacteria" in JS and "Metatranscriptomics" in JS),
    ("§2.3", "metatranscriptomics reuses the shotgun set",
     lambda: "SETS.shotgun" in JS or "shotgun" in JS),

    ("§3.1", "scRNA-seq asks primary (CellRanger) and full analysis",
     lambda: (spec_of("scrna-seq-10x") or {}).get("primary_analysis") is not None),
    ("§3.2", "SpaceRanger only for Visium HD kits",
     lambda: "only_for_kits" in json.dumps(spec_of("spatial-transcriptomics") or {})),

    ("§4.1", "metagenomics library type is multi-select",
     lambda: "multi" in JS.lower() and "LibraryType" in JS),
    ("§4.1", "header library type fills the per-sample Library Type column",
     lambda: "Library Type" in JS),

    ("§6", "DNA-seq offers four analysis branches",
     lambda: all(b in JS for b in ("De-novo assembly", "Variant analysis",
                                   "Metagenomic"))),
    ("§10", "user-prepared picks which analysis, then shows that set",
     lambda: "which" in JS and "user_prepared" in JS),

    ("§11.1", "extraction is a Yes/No plus a service choice",
     lambda: "needext" in JS),
    ("§11.2", "the sample table swaps when extraction is wanted",
     lambda: "extraction_columns" in JS and "reshapeSamples" in JS),
    ("§11.2", "fresh/frozen note shown when extraction is wanted",
     lambda: "fresh" in JS.lower() and "frozen" in JS.lower()),
    ("§11.2", "warns if concentration is filled while extraction is wanted",
     lambda: "cannot be known" in JS or "before extraction" in JS),

    ("§13", "export has an Analysis sheet",
     lambda: "'Analysis'" in JS),
    ("§13", "export has a Warnings sheet when there are warnings",
     lambda: "'Warnings'" in JS),

    ("§15.2", "budget number highlights for Technion, never blocks",
     lambda: "budget-note" in JS and "is-warn" in JS),
    ("§15.3", "faculty is free text, no vocabulary embedded",
     lambda: "faculty" in JS and "faculty_en" not in JS),
    ("§15.4", "BaseSpace instructions linked",
     lambda: "Downloading-your-sequencing-data" in JS),

    ("§16.2", "Olink keeps its own table, no concentration",
     lambda: "ng/ul" not in (spec_of("olink-reveal") or {}).get("columns", [])),
    ("§16.4", "no MiSeq anywhere in the built site",
     lambda: not any("miseq" in p.read_text(encoding="utf-8").lower()
                     for p in DIST.rglob("index.html"))),

    ("§17", "CosMx add-on question asked after a CosMx kit",
     lambda: "cosmx_addon" in JS),
    ("§17", "spatial exports the catalog billing name",
     lambda: "Flow cell (catalog name)" in FLAT or
             "catalog" in json.dumps((spec_of("spatial-transcriptomics") or {})
                                     .get("vocabularies", {}))),

    ("§18.1", "ten blocking rules enforced",
     lambda: JS.count("problems.push") >= 10),
    ("§18.1", "rule 10 — cells or nuclei blocks export",
     lambda: 'name="material"]:checked' in JS and
             "problems.push(APP.sample_material.label)" in JS),
    ("§18.1", "quote never blocks (D8)",
     lambda: "A quote is not required" in JS),

    ("§19", "quote read from the stamped payload, not the printed page",
     lambda: "ATGC-QUOTE-V1" in
             (ROOT / "assets" / "quote.js").read_text(encoding="utf-8")),
]


def main():
    built, missing = [], []
    for section, what, test in CHECKS:
        try:
            ok = bool(test())
        except Exception:
            ok = False
        (built if ok else missing).append((section, what))

    print(f"{len(built)}/{len(CHECKS)} decisions left a trace in the build\n")
    if missing:
        print("NOT FOUND — specified in doc 05, no sign of it in the code:")
        for section, what in missing:
            print(f"  {section:<8} {what}")
        print()
    print("found:")
    for section, what in built:
        print(f"  {section:<8} {what}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
