# -*- coding: utf-8 -*-
"""Turn the surveyed workbooks into the per-application spec build.py renders.

This is where the decisions in docs/05_Analysis_Intake_Spec.md meet the raw
structure in the workbooks: retired options stripped, column names
canonicalised, typos fixed, the experimental-group column added. Everything it
changes is reported, because a silent rewrite of the lab's own wording is
exactly what this project exists to stop.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))          # for atgc.retired

from data.applications import (EXTRACTION_SERVICES, FORM_PREPS, GROUP_OF,
                               LABS, NEEDS_CATALOG_ENTRY, published)
from survey_workbooks import survey, workbooks

from atgc.retired import retired_reason

# ── doc 05 §16.1 — canonical column names, and the spellings they replace ────
# "Quant. Method" says method; the answer is always an instrument, so the
# header now says so. One rename, applied everywhere, rather than three
# spellings of a vaguer word.
QUANT_COLUMN = "Quantified by"
QUANT_OPTIONS = ["Qubit", "Tapestation", "Nanodrop"]

CANONICAL_COLUMNS = {
    "quant. method": QUANT_COLUMN,
    "quant. method ": QUANT_COLUMN,
    "quant.method": QUANT_COLUMN,
    "ng/ul method": QUANT_COLUMN,
    "experimental group*": "Experimental group",
    "experiment group": "Experimental group",
    "# cells / tissue weight": "# cells / tissue weight [mg]",
    "remarks*": "Remarks",
}

# ── the module prompt's typo list, counted across the 20 workbooks ───────────
TYPOS = {
    "Basesapce": "BaseSpace",
    "basesapce": "BaseSpace",
    "insturment": "instrument",
    "Insturment": "Instrument",
    "numer": "number",
    "samle": "sample",
    "SpcaeRanger": "SpaceRanger",
    "coloumn": "column",
}

# NOT fixed here: "RNA extraction [fibrouse tissue]" is a CATALOG SERVICE NAME,
# not a form label. Renaming it in the page would break the link to the catalog,
# the quote and the lab report — the exact drift this project exists to remove.
# It is a real typo, but it belongs to the reference data: fix it in Module 0
# and it flows through everywhere at once.
DATA_TYPOS_TO_REPORT = {
    "RNA extraction [fibrouse tissue]": "fibrouse -> fibrous (services.csv)",
}

# doc 05 §16.2/§16.3 — the two forms with no experimental-group column.
NO_EXPERIMENTAL_GROUP = {"cell-line-authentication", "dna-rna-quality-quantity"}

# Vocabularies that never reach the page: the instrument is gone (D5).
DROP_SETTING_COLUMNS = {"Miseq"}


def fix_typos(text):
    """Return (corrected, [(before, after), ...])."""
    if not text:
        return text, []
    out, changes = text, []
    for wrong, right in TYPOS.items():
        if wrong in out:
            out = out.replace(wrong, right)
            changes.append((wrong, right))
    return out, changes


def canonical_column(name):
    return CANONICAL_COLUMNS.get(name.strip().lower(), name.strip())


def catalog_flowcell_options():
    """Every flow cell we sell, from the catalog — not from the workbooks.

    The `Setting` sheets are years out of date: they list no P4 at all and miss
    P2 300M 600, while carrying MiSeq and P3 50 cycles that no longer exist. The
    catalog is the only current list, and "(seq only)" is what marks a
    sequencing-run line there.

    `label` is what the researcher picks; `catalog` is what gets exported, so a
    submission names the same service the quote does (D6).
    """
    import csv
    out = []
    path = ROOT.parent / "data" / "reference" / "services.csv"
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            desc = row["description"]
            if "seq only" not in desc.lower() or row.get("active") != "1":
                continue
            out.append({
                "label": desc.replace(" (seq only)", ""),
                "catalog": desc,
                # doc: SE for the shortest read of each part, PE otherwise.
                "runmode": "Single read" if _flowcell_key(desc) in SE_DEFAULT
                           else "Paired end",
            })
    out.sort(key=lambda o: o["label"])
    return out


# Flow cells that default to single-read; everything else defaults to paired-end.
SE_DEFAULT = {("P1", "100"), ("P2", "100"), ("P3", "100"), ("P4", "50")}


def _catalog_flowcells():
    """The flow cells the facility actually offers, as {(part, cycles)}.

    The CATALOG is the authority here, not a regex. retired.py's non-XLEAP rule
    cannot judge these terms: the forms spell a flow cell "NextSeq 2000 P2 100
    cycles" while the catalog spells it "NextSeq 2000 P2 XLEAP 100 cycles (seq
    only)", so the rule wrongly retires the whole RunType vocabulary — and it
    wrongly KEEPS "P3 50 cycles", because that short form contains no "NextSeq"
    token to match on. Comparing against the active catalog entries gets both
    right: P4 50 cycles is offered, P3 50 cycles is not.
    """
    import csv
    offered = set()
    path = ROOT.parent / "data" / "reference" / "services.csv"
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row["category"] != "Nextseq" or row.get("active") != "1":
                continue
            key = _flowcell_key(row["description"])
            if key:
                offered.add(key)
    return offered


_FC = re.compile(r"\bP([1-4])\b.*?(\d+)\s*cycles", re.I | re.S)


def _flowcell_key(text):
    """('P2', '100') for any spelling of a NextSeq flow cell, else None."""
    m = _FC.search(text or "")
    return (f"P{m.group(1)}".upper(), m.group(2)) if m else None


OFFERED_FLOWCELLS = None


def clean_vocabulary(values):
    """Drop retired terms. Returns (kept, [(term, reason), ...])."""
    global OFFERED_FLOWCELLS
    if OFFERED_FLOWCELLS is None:
        OFFERED_FLOWCELLS = _catalog_flowcells()

    kept, dropped = [], []
    for v in values:
        # MiSeq and other withdrawn product lines: retired.py is right.
        reason = retired_reason(v)
        if reason and "miseq" in v.lower().replace(" ", ""):
            dropped.append((v, reason))
            continue

        key = _flowcell_key(v)
        if key:
            if key in OFFERED_FLOWCELLS:
                kept.append(v)
            else:
                dropped.append((v, f"{key[0]} {key[1]} cycles is not an active "
                                   f"catalog flow cell"))
            continue

        if reason:
            dropped.append((v, reason))
        else:
            kept.append(v)
    return kept, dropped


def routing_for(slug):
    """Who this application's completed form is emailed to, per lab.

    Read from data/routing.csv so Nitsan can edit recipients in Excel without
    touching code — the same pattern the rest of the platform uses for
    reference data.

    A BLANK `to` means the application is NOT offered at that lab, so the row is
    dropped and the lab never appears in the dropdown. scRNA-seq, Spatial, CLA,
    Olink and RRBS run at Medicine only, and offering Emerson would send those
    samples to a building that cannot process them.

    Falls back to LABS only if the application has no rows at all, so a newly
    added form still has somewhere to go rather than silently having no
    recipient.
    """
    import csv
    path = ROOT / "data" / "routing.csv"
    rows = []
    if path.exists():
        with open(path, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                if r["application_slug"] != slug:
                    continue
                split = lambda v: [x.strip() for x in (v or "").replace(",", ";").split(";") if x.strip()]
                to = split(r["to"])
                if not to:            # blank = not offered at this lab
                    continue
                rows.append({"lab": r["lab"], "to": to, "cc": split(r["cc"])})
    if not rows:
        rows = [{"lab": l["label"], "to": l["to"], "cc": []} for l in LABS]
    return rows


def _prep_aliases():
    """Nitsan's confirmed form-term -> catalog-name mappings.

    The workbooks name a prep loosely ("Exome", "16S"); a quote names the
    service exactly ("Twist Exome library prep"). Matching is what lets a
    researcher pick the right prep straight off their quote, so the mapping is
    a data file rather than code — rows marked CHECK are proposals awaiting
    confirmation and are IGNORED until the confidence says otherwise.
    """
    import csv
    path = ROOT / "data" / "prep_aliases.csv"
    out = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            canon = (r.get("catalog_name") or "").strip()
            conf = (r.get("confidence") or "").strip().lower()
            if canon and conf not in ("check", "keep", ""):
                out[_squash(r["form_term"])] = canon
    return out


PREP_ALIASES = None


# Nitsan, 2026-08-12: the catalog splits single-cell and spatial services by
# PROJECT SIZE for pricing — [2 samples], [3 samples], [2 slides] — but the base
# service is one thing. The researcher picks the service; staff pick the size
# when quoting, from the sample count.
#
# Size is not the only thing in those brackets, though. "[1BC, 2 samples]" and
# "[4BC, 4 samples]" differ by barcode count as well, and THAT is a real choice
# the researcher makes. So drop only the size component and keep the rest:
#     [1BC, 2 samples]     -> [1BC]
#     [4 samples project]  -> (gone)
#     [2 slides]           -> (gone)
_SIZE_PART = re.compile(r"^\s*\d+\s*(sample|slide|plate)s?\b.*$", re.I)


def base_service(description):
    """A priced variant reduced to the service behind it."""
    def trim(match):
        parts = [p.strip() for p in match.group(1).split(",")]
        kept = [p for p in parts if p and not _SIZE_PART.match(p)]
        return (" [" + ", ".join(kept) + "]") if kept else ""
    return re.sub(r"\s*\[([^\]]*)\]\s*$", trim, description or "").strip()


def _catalog_preps():
    """Active prep services, keyed for matching.

    Indexed BOTH by full name and by base service, so a form term matches
    whether it names the variant or the family. Where several variants share a
    base, the base name is what the form shows — offering a researcher a choice
    between "[2 samples]" and "[3 samples]" asks them to price their own
    project.
    """
    import csv
    out, families = {}, {}
    path = ROOT.parent / "data" / "reference" / "services.csv"
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row.get("active") != "1":
                continue
            if row["category"] not in ("LibraryPrep", "scRNAseq", "Spatial"):
                continue
            desc = row["description"]
            out.setdefault(_squash(desc), desc)
            base = base_service(desc)
            families.setdefault(_squash(base), base)
    # Base names win, so a matched term shows the family rather than one size.
    out.update(families)
    return out


def _squash(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


CATALOG_PREPS = None


def canonical_prep(term):
    """The catalog's name for a library prep, or None if it is not a safe match.

    EXACT (squashed) matching only. The workbooks are full of near-misses —
    "NEBNext directional RNA library prep" could be the Ultra II prep or the
    rRNA-removal one, and the catalog carries both. Guessing would quietly put
    the wrong service on a submission, so anything short of an exact match is
    reported for a human to decide (doc 05 §21).
    """
    global CATALOG_PREPS, PREP_ALIASES
    if CATALOG_PREPS is None:
        CATALOG_PREPS = _catalog_preps()
    if PREP_ALIASES is None:
        PREP_ALIASES = _prep_aliases()
    key = _squash(term)
    hit = CATALOG_PREPS.get(key) or PREP_ALIASES.get(key)
    if hit:
        return hit
    # The form may name a variant the catalog prices differently — try the
    # service behind the form's own wording as well.
    base = _squash(base_service(term))
    return CATALOG_PREPS.get(base) or PREP_ALIASES.get(base)


def build_spec(app, surveyed):
    """One application's full field spec, plus a record of what was changed."""
    report = {"typos": [], "renamed_columns": [], "retired": [], "added": [],
              "unresolved_preps": []}

    # ── sample columns ──────────────────────────────────────────────────────
    columns = []
    for raw in surveyed["sample_columns"]:
        fixed, typo_changes = fix_typos(raw)
        report["typos"] += typo_changes
        canon = canonical_column(fixed)
        if canon != raw:
            report["renamed_columns"].append((raw, canon))
        columns.append(canon)

    # "Sample ID" only ever held 1, 2, 3... in the workbooks, and the table
    # already numbers its rows. Keeping both invites two different numbers for
    # the same sample.
    if "Sample ID" in columns:
        columns.remove("Sample ID")
        report["added"].append("Sample ID dropped — the row number is the sample number")

    # doc 05 §16 — experimental group everywhere but the two exemptions.
    if app["slug"] not in NO_EXPERIMENTAL_GROUP:
        if "Experimental group" not in columns:
            # After the identifiers, before free-text remarks.
            pos = len(columns)
            for i, c in enumerate(columns):
                if c.lower().startswith("remarks"):
                    pos = i
                    break
            columns.insert(pos, "Experimental group")
            report["added"].append("Experimental group (sample column)")

    # Remarks last on every table: somewhere to say the thing the form did not
    # think to ask. Always optional.
    if "Remarks" not in columns:
        columns.append("Remarks")
        report["added"].append("Remarks (sample column)")

    # ── vocabularies ────────────────────────────────────────────────────────
    vocab = {}
    for name, values in surveyed["setting"].items():
        if name in DROP_SETTING_COLUMNS:
            report["retired"] += [(v, "MiSeq decommissioned — column dropped")
                                  for v in values]
            continue
        kept, dropped = clean_vocabulary(values)
        report["retired"] += dropped
        if kept:
            vocab[name] = kept

    # ── choice fields ───────────────────────────────────────────────────────
    choices = []
    for c in surveyed["choice_fields"]:
        label, typo_changes = fix_typos(c["label"])
        report["typos"] += typo_changes
        if label:
            choices.append({"label": label, "source": c["source"]})

    # ── decisions that come from the registry, not the workbook ─────────────
    if app.get("no_sequencing"):
        for key in ("LibraryPrep", "FlowCell", "RunMode", "Run#", "Nextseq",
                    "RunType", "Instrument"):
            vocab.pop(key, None)
        report["added"].append("sequencing choices removed — not a sequencing service")
    elif app.get("no_library_prep"):
        vocab.pop("LibraryPrep", None)
        report["added"].append("library prep removed — the researcher supplies the library")

    if app["slug"] in FORM_PREPS and not app.get("no_sequencing"):
        before = vocab.get("LibraryPrep", [])
        vocab["LibraryPrep"] = list(FORM_PREPS[app["slug"]])
        dropped = [t for t in before if t not in vocab["LibraryPrep"]]
        if dropped:
            report["added"].append(
                f"library preps pruned: dropped {', '.join(dropped)}")

    swap = app.get("replace_preps") or {}
    if swap and vocab.get("LibraryPrep"):
        out = []
        for term in vocab["LibraryPrep"]:
            if term in swap:
                out.extend(swap[term])
                report["added"].append(
                    f"{term!r} split into {len(swap[term])} named kits")
            else:
                out.append(term)
        vocab["LibraryPrep"] = out

    for extra in app.get("extra_preps", []):
        if extra not in vocab.get("LibraryPrep", []):
            vocab.setdefault("LibraryPrep", []).append(extra)
            report["added"].append(f"library prep: {extra}")

    if app.get("library_kits"):
        vocab["LibraryPrep"] = [k["label"] for k in app["library_kits"]]
        report["added"].append("Spatial kit list replaces the workbook's (doc 05 §17)")
    if app.get("extraction"):
        vocab["ExtractionService"] = EXTRACTION_SERVICES[app["extraction"]]
        report["added"].append(
            f"{app['extraction'].upper()} extraction services (doc 05 §11)")
    if app.get("library_types"):
        vocab["LibraryType"] = app["library_types"]
        vocab["Region"] = app["regions"]

    # Show the name the QUOTE uses, so a quote import matches and staff read one
    # name everywhere (D6). Unresolved terms keep the workbook wording and are
    # listed in the build report rather than being guessed at.
    if vocab.get("LibraryPrep") and not app.get("library_kits"):
        resolved, kept = [], []
        for term in vocab["LibraryPrep"]:
            canon = canonical_prep(term)
            if canon and canon != term:
                report["renamed_columns"].append((term, canon))
                resolved.append(canon)
            elif canon:
                resolved.append(canon)
            elif term in NEEDS_CATALOG_ENTRY:
                report.setdefault("needs_catalog", []).append(term)
                resolved.append(term)
            else:
                kept.append(term)
                resolved.append(term)
        vocab["LibraryPrep"] = resolved
        if kept:
            report["unresolved_preps"] = kept

    # The flow-cell list comes from the catalog wherever the form had one at
    # all. The workbook's own list stays in the spec only as evidence of what
    # was replaced; nothing renders it.
    if vocab.get("Nextseq") or vocab.get("RunType"):
        vocab["FlowCell"] = catalog_flowcell_options()
        report["added"].append(
            f"{len(vocab['FlowCell'])} flow cells from the catalog "
            f"(the workbook listed {len(vocab.get('Nextseq') or vocab.get('RunType', []))})")
        vocab.pop("Nextseq", None)
        vocab.pop("RunType", None)

    return {
        "slug": app["slug"],
        "name": app["name"],
        "site": app.get("site"),
        "service_page": app.get("service_page"),
        "analysis": app.get("analysis"),
        "no_analysis_question": app.get("no_analysis_question", False),
        "no_sequencing": app.get("no_sequencing", False),
        "extraction": app.get("extraction"),
        "keep_own_table": app.get("keep_own_table", False),
        "primary_analysis": app.get("primary_analysis"),
        "protocol_choice": app.get("protocol_choice"),
        "qc_services": app.get("qc_services"),
        "cosmx_addon": app.get("cosmx_addon"),
        "routing": routing_for(app["slug"]),
        "addresses": {l["label"]: {"lines": l.get("address", []),
                                   "phone": l.get("phone", "")}
                      for l in LABS},
        "quant_column": QUANT_COLUMN,
        "quant_options": QUANT_OPTIONS,
        "group": GROUP_OF.get(app["slug"], "transcriptomics"),
        "columns": columns,
        "choices": choices,
        "vocabularies": vocab,
        "report": report,
    }


def all_specs():
    """Every published application, keyed by slug."""
    by_name = {}
    for path in workbooks():
        by_name[Path(path).name] = survey(path)

    specs, missing = [], []
    for app in published():
        wb = app.get("workbook") or app.get("layout_from")
        surveyed = by_name.get(Path(wb).name) if wb else None
        if surveyed is None:
            missing.append(app["slug"])
            continue
        specs.append(build_spec(app, surveyed))
    return specs, missing


if __name__ == "__main__":
    specs, missing = all_specs()
    if missing:
        print(f"NO SOURCE WORKBOOK: {missing}")
    print(f"{len(specs)} application specs\n")
    tot = {"typos": 0, "renamed_columns": 0, "retired": 0, "added": 0}
    for s in specs:
        r = s["report"]
        for k in tot:
            tot[k] += len(r[k])
        print(f"{s['slug']:<26} cols={len(s['columns']):<2} "
              f"vocab={len(s['vocabularies']):<2} "
              f"typos={len(r['typos']):<2} renamed={len(r['renamed_columns']):<2} "
              f"retired={len(r['retired']):<3} added={len(r['added'])}")
    print(f"\ntotals: {tot}")
