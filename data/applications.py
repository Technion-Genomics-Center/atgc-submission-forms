# -*- coding: utf-8 -*-
"""The application registry — the CONDITIONAL RULES half.

Split in two on 2026-08-17, because it was doing two jobs at once:

    data/applications.csv   the FLAT FACTS — slug, name, status, group, site
                            link, source workbook. Git-tracked, editable in
                            Excel, and safe for CatalogAdmin to write.
    data/applications.py    THIS FILE — only the rules that are conditional:
                            which analysis panel expands and when, which kits a
                            form offers, which questions an application does not
                            ask. Hand-edited, and still the only place doc 05's
                            decisions are written down.

The mixture was why FormAdmin had to print a block of Python and ask a human to
paste it, which made every new service end with a step only one person could
do. Adding an application is now a CSV row plus, if it needs any, a RULES
entry. The two are joined by `key` — the slug for a published application, and
a stable name-derived key for the withdrawn and merged ones, which have no slug.

Structure comes from the workbooks (see tools/survey_workbooks.py); the
DECISIONS come from docs/05_Analysis_Intake_Spec.md and are not derivable from
any file. doc 05 §12 is the prose that explains them.

`slug` is a PUBLIC CONTRACT. The website links to /SubmissionForm/<slug>/ and
those links end up in emails and bookmarks. Never rename one; add to
`SLUG_ALIASES` instead so the old URL keeps working. This survived the split
unchanged and must survive the next one.
"""

from __future__ import annotations

import csv
import io
import os

# ── how each application is treated ─────────────────────────────────────────
BUILD = "build"            # a published form
MERGED = "merged"          # folded into another form; no page of its own
WITHDRAWN = "withdrawn"    # service no longer offered

# ── analysis intake sets, doc 05 ────────────────────────────────────────────
# None means: ask the bioinformatics Yes/No and show the consultation
# paragraph, but expand no panel (doc 05 §12.2).
RNASEQ = "rnaseq"                    # §2.2, branches on rRNA-removal prep §2.1
SCRNA = "scrna"                      # §3.1 — two questions, only the 2nd expands
SPATIAL = "spatial"                  # §3.2 — panel; Visium HD kits also get
                                     #        the primary/full split, CosMx not
AMPLICON16S = "amplicon_16s"         # §4.3
SHOTGUN = "shotgun"                  # §4.4 (also DNA-seq's metagenomic branch)
AMPLICON = "amplicon"                # §5
DNASEQ = "dnaseq"                    # §6 — four branches
EXOME = "exome"                      # §6.1 — variant-analysis branch only
CHIP = "chip"                        # §7
RRBS = "rrbs"                        # §8
OLINK = "olink"                      # §9
USER_PREPARED = "user_prepared"      # §10 — dropdown reusing the sets above

# Where the source workbooks live on the lab share. READ-ONLY, both of them.
#
# These were spelled out as `Y:\LAB\...` until the split. That is the exact
# defect D23 exists to stop: the same storage is Y: on some machines and Z: on
# others, so a literal drive letter is wrong for half the team. Resolved
# through atgc.config, which works the share out from where the code is
# running. The CSV stores the token WEBSITE or FORMS, never a path.
def _share(*parts):
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)
    from atgc import config
    return config.under_storage(*parts)


WEBSITE = _share("LAB", "TGC_website", "ATGC_website_2025", "Applications")
FORMS = _share("LAB", "Forms", "Submission_forms")

ROOTS = {"WEBSITE": WEBSITE, "FORMS": FORMS}

# The public site, read off https://atgc.net.technion.ac.il/applications/ on
# 2026-08-11. `site` on each entry is the page the form links to for sample
# requirements and guidelines. Some pages serve two forms (ChIP-seq and Cut&Run
# share one; RRBS and Infinium share the methylation page), which is why this is
# a mapping rather than a slug transformation.
SITE = "https://atgc.net.technion.ac.il/applications/"

# Linked from the consultation paragraph wherever analysis is offered.
SITE_BIOINFORMATICS = SITE + "bioinformatics/"

# ── which ATGC lab receives the samples (Nitsan, 2026-08-11) ────────────────
# ATGC runs in two buildings and the completed form goes to different people
# depending on which one. The researcher chooses; the mailto is built from it.
# This is the ONLY thing that decides where a submission is sent, so it is a
# required field — a form with no lab has nowhere to go.

# Section colours, from the website's applications.html. A form takes the
# accent of the group the researcher just came from, so the page reads as a
# continuation of the site rather than a separate tool.
#
# APP_GROUPS and GROUP_OF are now derived from applications.csv's `group` and
# `group_order` columns — see _load_groups() at the foot of this file. They
# used to be a second literal list, and keeping it in step with APPLICATIONS
# was one of the steps a new application could silently miss.

# Where samples are physically delivered. Shown on the form for whichever
# lab the researcher is submitting to.
LABS = [
    {
        "id": "emerson",
        "label": "Emerson",
        "to": ["nitsanf@technion.ac.il", "angelao@technion.ac.il"],
        "address": ["Technion Genomics Center",
                    "Room 2-2, 2nd floor, Emerson building",
                    "Technion campus"],
        "phone": "073-3781387",
    },
    {
        "id": "medicine",
        "label": "Medicine (Rappaport)",
        "to": ["fdoron@technion.ac.il", "gliza@technion.ac.il",
               "nitsanf@technion.ac.il"],
        "address": ["Technion Genomics Center",
                    "M1 floor, Medicine Faculty",
                    "Efron Street, Haifa (near Rambam hospital)"],
        "phone": "073-3785221",
    },
]

# doc 05 §11.3 — offer every extraction service in the catalog, filtered by
# nucleic acid. Names only; prices never reach the page.
# doc 05 §11.2 — when extraction is wanted, the researcher is sending material,
# not measured nucleic acid. Concentration and purity cannot be known yet, so
# the table asks what is actually in the tube.
EXTRACTION_COLUMNS = ["Sample name", "# cells / tissue weight [mg]", "Organism",
                      "Experimental group", "Remarks"]

# A form offering both asks which nucleic acid first: twelve services in one
# dropdown is a list to scroll, four is a choice to make.
EXTRACTION_TYPES = ["DNA", "RNA"]

EXTRACTION_SERVICES = {
    "rna": [
        "RNA extraction",
        "RNA extraction [fibrouse tissue]",
        "RNA extraction [PAX blood]",
        "RNA extraction [PAX tubes]",
        "RNA extraction [plant]",
        "RNA extraction FFPE",
        "RNA extraction low input",
        "miRNA extraction- serum/plasma",
    ],
    "dna": [
        "DNA extraction",
        "DNA extraction from plant",
        "DNA extraction from stool",
        "DNA extraction from tissue",
    ],
}



# Which library preps each application actually offers (Nitsan, 2026-08-12).
# The workbooks shared one Setting sheet across several applications, so the
# metagenomics form inherited RRBS, ChIP-seq and Exome preps that belong to
# other services entirely. Listing them per form replaces that grab-bag —
# where a form appears here, this list wins outright.
# Services the forms offer that the CATALOG does not carry yet. They can be
# picked on a form but cannot be quoted until Module 0 adds them, so the build
# names them rather than letting them hide among the unmatched terms.
#
# Nitsan, 2026-08-12: 16S-seq and 18S-seq are sub-services of metagenomics, and
# 18S is quoted as its own service with its own kit — but no 18S entry exists.
NEEDS_CATALOG_ENTRY = {
    # Nitsan, 2026-08-12. Nanopore runs two kits today and more are coming; the
    # catalog carries only a bundled "Nanopore sequencing (2 samples, library
    # prep + sequencing)" line, so neither kit can be quoted on its own.
    "Nanopore DNA ligation library prep": "Nanopore kit, no service in the price list",
    "Nanopore DNA rapid library prep": "Nanopore kit, no service in the price list",
}

def _load_form_kits():
    """Which library preps each application offers.

    Lives in data/form_kits.csv rather than here so it can be edited in Excel,
    or by tools/manage.py, without anyone touching Python. The workbooks shared
    one Setting sheet across several applications, so the metagenomics form
    inherited RRBS, ChIP-seq and Exome preps belonging to other services
    entirely; this file replaces that grab-bag. Where a form appears here, this
    list wins outright.
    """
    import csv
    import os
    path = os.path.join(os.path.dirname(__file__), "form_kits.csv")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            slug = (r.get("application_slug") or "").strip()
            prep = (r.get("library_prep") or "").strip()
            if slug and prep:
                out.setdefault(slug, []).append(prep)
    return out


FORM_PREPS = _load_form_kits()


RULES = {
    # ── sequencing forms with an analysis panel ─────────────────────────────
    "rnaseq": dict(analysis=RNASEQ,
         # doc 05 §11 — RNAseq-extraction folded in behind a Yes/No.
         extraction="rna",
         # Nitsan, 2026-08-12. The workbook offered one vague "[rRNA removal]"
         # option. Three different kits do rRNA removal and they are priced and
         # run differently, so the form names each — a researcher reading their
         # quote can then pick the one they were quoted.
         ),

    "scrna-seq-10x": dict(analysis=SCRNA,
         # Nitsan, 2026-08-17. "Illumina/Fluent scRNA-seq library prep" is GONE
         # from this form. Fluent is the old name for Illumina scRNA-seq, which
         # now has a form of its own listing the four real kits (§12.1), so
         # keeping it here offered one service twice, under two names, on the
         # wrong form. It was added on 2026-08-12, before that form existed.
         #
         # Deleting the `extra_preps` line is the whole fix: it was the only
         # source of the term. The sc10X workbook never listed it.
         # Nitsan, 2026-08-17. Cells or nuclei changes the handling, so it is
         # asked once for the whole submission, immediately above the table it
         # describes rather than among the sequencing choices.
         sample_material=True,
         # Nitsan, 2026-08-16. 10X libraries are read at a fixed length on a
         # 100-cycle kit, and single/paired follows the chemistry. Both were
         # being asked as if the researcher chose them.
         flowcell_cycles=100,
         run_settings_from_kit=True,
         # doc 05 §3.1 — CellRanger is a priced pipeline, not a bespoke
         # analysis, so it is asked separately and is never gated by the
         # consultation. Unlike Spatial's SpaceRanger it applies to every kit.
         primary_analysis=dict(
             label="Do you require primary analysis (CellRanger)?",
             catalog="Primary analysis- CellRanger")),

    # PH-24 / PH-25. `SC PIPseq_Illumina` in the old project tree is really
    # Illumina scRNA-seq; it becomes its own application rather than a variant
    # of the 10X form, and gets its own project folder. Received by Medicine
    # (Rappaport) — data/routing.csv leaves Emerson blank.
    #
    # No workbook of its own — the service is new. The 10X form is the right
    # layout: same question (how many cells, how viable), same sample table.
    # The KITS are not shared, and come from data/form_kits.csv, which wins
    # outright over anything the borrowed Setting sheet lists.
    "illumina-scrna-seq": dict(analysis=SCRNA,
         # Same reasoning as 10X (doc 05 §20a): the read configuration is fixed
         # by the kit and set by the lab, so the researcher is not asked.
         flowcell_cycles=100,
         run_settings_from_kit=True,
         # Nitsan, 2026-08-17. Borrowed from the 10X layout, whose header covers
         # both cases: "Fresh: cells/ul ; Fixed: total #cells". This service
         # takes fixed cells only, so half that header is a question the
         # researcher cannot answer and the other half is the only one asked.
         rename_columns={"Fresh: cells/ul ; Fixed: total #cells": "cells/ul"},
         sample_material=True,
         # doc 05 §3.1 — the scRNA set, the same one 10X uses. CellRanger is
         # 10X's own software and is NOT offered here; Illumina libraries are
         # processed with Illumina's pipeline, so there is no primary_analysis
         # entry. Ask before adding one.
         ),

    "spatial-transcriptomics": dict(analysis=SPATIAL,
         # Nitsan, 2026-08-16. Same reasoning as 10X scRNA-seq: a Visium HD
         # library is read at a fixed length on a 100-cycle kit, and the run
         # parameters follow the chemistry. These apply to the Visium kits
         # only — CosMx is imaged on the instrument and never reaches a flow
         # cell at all, so it never sees these questions whatever they say.
         flowcell_cycles=100,
         run_settings_from_kit=True,
         # Nitsan, 2026-08-11. REPLACES the workbook's eight Visium/CosMx
         # variants outright — the FFPE 11mm, PFA-fixed and fresh/frozen options
         # are no longer offered. `catalog` is the canonical service each kit
         # bills as; None means the catalog has no entry yet (doc 05 §17).
         library_kits=[
             dict(label="Visium HD", technology="sequencing",
                  catalog="10X Visium HD 6.5mm  [2 slides]"),
             dict(label="Visium HD 3'", technology="sequencing",
                  catalog="10X Visium HD 3' [2 slides]",
                  # Billing name confirmed by Nitsan; the catalog entry itself
                  # does not exist yet and has NO price. Needs adding via
                  # Module 0 before this kit can be quoted.
                  needs_catalog_entry=True, needs_price=True),
             # Nitsan, 2026-08-16. The six real panels, replacing four options
             # that named a plex count and a species but not the panel — a
             # researcher choosing "CosMx x1000 mouse" had not said whether
             # they wanted Universal or Neuroscience, which are different kits
             # at different prices.
             #
             # `label` is the catalog name minus its size suffix, the same rule
             # every other kit here follows, so the name on the form is the
             # name on the quote. Kit part numbers live in
             # ProjectHub/data/libprep_kits.csv; the catalog is the authority
             # for what a submission bills as.
             dict(label="CosMx Human Universal 1K", technology="imaging",
                  catalog="CosMx Human Universal 1K [2 slides]"),
             dict(label="CosMx Human Discovery 6K", technology="imaging",
                  catalog="CosMx Human Discovery 6K [2 slides]"),
             dict(label="CosMx Human Whole Transcriptome", technology="imaging",
                  catalog="CosMx Human Whole Transcriptome [2 slides]"),
             dict(label="CosMx Mouse Universal 1K", technology="imaging",
                  catalog="CosMx Mouse Universal 1K [2 slides]"),
             # Catalog entry exists, both prices are still blank.
             dict(label="CosMx Mouse Neuroscience 1K", technology="imaging",
                  catalog="CosMx Mouse Neuroscience 1K [2 slides]",
                  needs_price=True),
             dict(label="CosMx Mouse Whole Transcriptome WTX", technology="imaging",
                  catalog="CosMx Mouse Whole Transcriptome WTX [2 slides]",
                  needs_price=True),
         ],
         # SpaceRanger is 10X Visium software, so the primary/full split
         # applies to the Visium HD kits only. CosMx primary analysis runs on
         # the instrument and is not ordered here (doc 05 §3.2).
         primary_analysis=dict(
             label="Do you require primary analysis (SpaceRanger)?",
             catalog="Primary analysis- SpaceRanger",
             only_for_kits=["Visium HD", "Visium HD 3'"]),
         # Nitsan, 2026-08-13. CosMx is a DIFFERENT TECHNOLOGY, not a different
         # setting: it is imaged on the instrument and never sequences, whatever
         # the kit. Visium is sequenced. Each kit above says which it is, so a
         # new kit cannot be added without answering the question — a list of
         # "kits that sequence" would let a new Visium kit silently lose its
         # sequencing questions.
         # Every CosMx kit can carry custom add-on genes, billed per gene.
         cosmx_addon=dict(
             trigger_prefix="CosMx",
             question="Do you require a custom add-on?",
             quantity="How many add-on genes?",
             catalog="CosMx custom add-on [per gene]"),
         # The exported record carries the CANONICAL billing name next to the
         # kit label the researcher picked, so quote, submission and lab report
         # all name the same thing (D6).
         export_catalog_name=True),

    "metagenomics-16s-18s": dict(analysis=AMPLICON16S,
         # doc 05 §4.1 — header multi-select drives the per-sample column.
         # Nitsan asked what a mixed project should do. Proposal: the header
         # states what the submission contains, and "Mixed" hands the decision
         # to the per-sample Library Type column, which already exists and
         # already auto-fills. No new UI, and one sample per row stays true.
         library_types=["16S", "18S", "Mixed — set per sample"],
         regions=["V4", "V3-V4"],
         sample_library_types=["16S V4", "16S V3-V4", "18S"],
         extraction="dna"),

    # doc 05 §4.2 — no workbook exists; built from the DNA-seq layout and
    # generated into SubmissionForm/ for Nitsan to place.
    # Guidelines come from DNA-seq, not metagenomics: the form is built from the
    # DNA-seq layout and the sample requirements are the DNA-seq ones. The
    # SERVICE is described on the metagenomics page, hence the two links.
    "shotgun-metagenomics": dict(analysis=SHOTGUN,
         # Quoted and reported under the DNA-seq prep — a new form, not a new
         # catalog service.
         catalog_prep="NEBNext DNA library prep",
         extraction="dna"),

    "amplicon-seq": dict(analysis=AMPLICON),

    "dna-seq": dict(analysis=DNASEQ, extraction="dna"),

    "exome-seq": dict(analysis=EXOME),

    "chip-seq-cut-and-run": dict(analysis=CHIP,
         # Nitsan, 2026-08-12. One form, but which protocol was run has to be
         # recorded: the kit is the same and the protocols are not, and
         # downstream processing depends on knowing which. BLOCKING, because a
         # submission that does not say is ambiguous the moment it arrives.
         protocol_choice=dict(
             label="Which protocol?", options=["ChIP-seq", "Cut&Run"])),

    "rrbs": dict(analysis=RRBS, extraction="dna"),

    "olink-reveal": dict(analysis=OLINK,
         # Nitsan, 2026-08-17 (doc 05 §9). Olink is the one application where
         # analysis is not all-or-nothing: every Reveal order already includes
         # the initial analysis, so the only open question is whether the
         # researcher also wants the differential work on top.
         #
         # Saying "Do you require bioinformatic analysis?" here was actively
         # misleading - answering No reads as "no analysis", when initial
         # analysis is part of the service and cannot be declined.
         analysis_intro=("Every Olink Reveal order includes initial data "
                         "analysis, which delivers the NPX count matrix."),
         analysis_label="Do you require full differential analysis?",
         # The comparisons are needed either way: they describe the experiment,
         # not the extra service. So this field sits OUTSIDE the Yes/No gate and
         # is asked of every Olink submission - see ALWAYS in assets/form.js.
         analysis_always_fields=True,
         # doc 05 §16.2 — keeps its own plate-based table, no concentration.
         keep_own_table=True,
         # Nitsan, 2026-08-13: the free-text "other" column is not used, and
         # Olink plates are not QC'd here.
         drop_columns=["Sample Type- other"],
         no_qc=True),

    # The researcher brings a finished library, so there is no prep to choose.
    "user-prepared": dict(analysis=USER_PREPARED,
         no_library_prep=True, no_experimental_group=True,
         # No prep to choose, but the library still gets measured before it
         # goes on a flow cell (Nitsan, 2026-08-12).
         qc_services=["Qubit measurement", "TapeStation"]),

    # ── forms with the question but no panel, doc 05 §12.2 ──────────────────
    "nanopore": dict(analysis=None,
         # Nanopore has its own flow cells and its own run settings — the
         # NextSeq questions do not apply. The library prep still does.
         no_flowcell=True),

    "mirna-seq": dict(analysis=None, extraction="rna"),

    # ── no bioinformatics question at all, doc 05 §12.5 ─────────────────────
    "cell-line-authentication": dict(analysis=None, no_analysis_question=True,
         # doc 05 §16.3 — normalised naming, but still no experimental group.
         no_experimental_group=True,
         # A lab service, not a sequencing run: the workbook asks only about DNA
         # extraction, and nothing is sequenced, so no prep, flow cell, run mode
         # or flow-cell count belongs on it.
         no_sequencing=True,
         extraction="dna"),

    "dna-rna-quality-quantity": dict(analysis=None, no_analysis_question=True,
         no_experimental_group=True,
         # This IS the service — measuring. Each instrument is ordered
         # separately and takes a different kit, so each is its own question.
         # Kits are the workbook's own lists (Setting!Qubit, Setting!Tapestation).
         no_sequencing=True,
         qc_panel=dict(
             guide_url=SITE + "dna-rna-quality-and-quantity/",
             note=("Please supply samples at the concentration the kit requires "
                   "\u2014 we do not dilute samples."),
             qubit=dict(
                 label="Do you require Qubit?",
                 kit_label="Qubit kit",
                 # Broad range RNA withdrawn 2026-08-13 — no longer used.
                 # The workbook's Setting sheet still lists it; this list wins.
                 kits=["High sensitivity DNA", "High sensitivity RNA"]),
             tapestation=dict(
                 label="Do you require TapeStation?",
                 type_label="DNA or RNA?",
                 kit_label="TapeStation kit",
                 kits={
                     "DNA": ["D1000 DNA", "High Sensitivity D1000 DNA",
                             "Genomic DNA", "HS Genomic DNA"],
                     "RNA": ["RNA [Eukaryotes]",
                             "High Sensitivity RNA [Eukaryotes]",
                             "RNA [Prokaryotes]",
                             "High Sensitivity RNA [Prokaryotes]"],
                 }),
         )),

    # doc 05 §12.3 — extraction produces no data to analyse; the bioinformatics
    # question is vestigial and is dropped.
    "extraction": dict(analysis=None, no_analysis_question=True,
         # Nothing is sequenced here. The whole service is: extract, and measure
         # what came out. Library prep and flow cell belong to the application
         # that follows, on its own form.
         # Asking "do you require extraction?" on the extraction form is asking
         # someone why they are here. It is always yes.
         no_sequencing=True, extraction="both", extraction_always=True,
         qc_services=["Qubit measurement", "TapeStation"]),

    # ── not published ───────────────────────────────────────────────────────
    # The withdrawn and merged applications carry no rules of their own — the
    # reason each was withdrawn is a flat fact and lives in the CSV's `note`.
}

# Superseded by the 16S/18S + Amplicon-seq split (doc 05 §4). Never built, never
# deleted — it lives on read-only storage.
SUPERSEDED = ["Amplicon_16S-seq-electronic_2025.xlsx"]

# Old URLs that must keep working if a slug is ever retired.
SLUG_ALIASES: dict[str, str] = {}


# ── the join ────────────────────────────────────────────────────────────────
APPLICATIONS_CSV = os.path.join(os.path.dirname(__file__), "applications.csv")


# ── flat rule fields the CSV may also carry ─────────────────────────────────
# `analysis`, `extraction` and the behaviour flags are selections from fixed
# vocabularies, not conditional logic — so a new application can set them in the
# CSV and needs NO Python edit to be built. That is the point of the split: a new
# service should not end with a step only one person can do.
#
# **RULES still wins where it says anything.** The rule is: a fact goes in the
# CSV when there is nothing to explain, and in RULES when there IS — and then the
# comment beside it is the explanation. Every existing application keeps its
# fields here, with the reasoning doc 05 recorded; their CSV cells are blank.
FLAGS = {
    "no_analysis_question", "no_sequencing", "no_experimental_group",
    "no_library_prep", "no_flowcell", "no_qc", "extraction_always",
    "keep_own_table", "export_catalog_name", "run_settings_from_kit",
    "sample_material",
}

# Analysis-panel names, so a typo in the CSV is caught rather than silently
# meaning "no panel".
PANELS = {RNASEQ, SCRNA, SPATIAL, AMPLICON16S, SHOTGUN, AMPLICON, DNASEQ,
          EXOME, CHIP, RRBS, OLINK, USER_PREPARED}

EXTRACTION_KINDS = {"rna", "dna", "both"}


class RegistryError(Exception):
    """A row in applications.csv says something the registry cannot honour."""


def _flat_rules_from_csv(r):
    """The rule fields a CSV row is allowed to set, validated."""
    out = {}
    analysis = (r.get("analysis") or "").strip()
    if analysis:
        if analysis not in PANELS:
            raise RegistryError(
                "applications.csv: analysis=%r on %r is not a known panel. "
                "One of: %s" % (analysis, r.get("key"),
                                ", ".join(sorted(PANELS))))
        out["analysis"] = analysis

    extraction = (r.get("extraction") or "").strip().lower()
    if extraction:
        if extraction not in EXTRACTION_KINDS:
            raise RegistryError(
                "applications.csv: extraction=%r on %r must be one of %s"
                % (extraction, r.get("key"), ", ".join(sorted(EXTRACTION_KINDS))))
        out["extraction"] = extraction

    prep = (r.get("catalog_prep") or "").strip()
    if prep:
        out["catalog_prep"] = prep

    cycles = (r.get("flowcell_cycles") or "").strip()
    if cycles:
        try:
            out["flowcell_cycles"] = int(cycles)
        except ValueError:
            raise RegistryError(
                "applications.csv: flowcell_cycles=%r on %r is not a whole "
                "number" % (cycles, r.get("key")))

    # Semicolon-separated, and an unknown one is an ERROR rather than a no-op.
    # A misspelled flag that quietly does nothing is the worst outcome here:
    # the form builds, looks right, and asks a question it should not.
    for flag in [f.strip() for f in (r.get("flags") or "").split(";")]:
        if not flag:
            continue
        if flag not in FLAGS:
            raise RegistryError(
                "applications.csv: flag %r on %r is not a known flag. One of: "
                "%s" % (flag, r.get("key"), ", ".join(sorted(FLAGS))))
        out[flag] = True
    return out


def _load_applications():
    """Flat facts from the CSV, conditional rules from RULES above.

    The result is exactly the list this module used to hold literally, in the
    same order, so nothing downstream had to change. `key` is what joins the
    two halves: the slug for a published application, and a stable
    name-derived key for the withdrawn and merged ones, which have no slug.

    A blank cell means "not set", so it becomes None rather than "" — several
    callers test `a.get("workbook")` for truth and an empty string would read
    as a workbook that exists.
    """
    out = []
    if not os.path.exists(APPLICATIONS_CSV):
        raise RuntimeError(
            "The application registry's flat half is missing: %s. It is "
            "git-tracked; restore it rather than recreating it by hand."
            % APPLICATIONS_CSV)
    with io.open(APPLICATIONS_CSV, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            key = (r.get("key") or "").strip()
            if not key:
                continue
            slug = (r.get("slug") or "").strip() or None
            entry = {
                "slug": slug,
                "name": (r.get("name") or "").strip(),
                "status": (r.get("status") or "").strip(),
                "root": ROOTS.get((r.get("root") or "").strip()),
                "workbook": (r.get("workbook") or "").strip() or None,
            }
            # `site` and `service_page` are stored as the tail after SITE, so
            # the public host is written down once (here) rather than 20 times.
            for field in ("site", "service_page"):
                tail = (r.get(field) or "").strip()
                if tail:
                    entry[field] = tail if "://" in tail else SITE + tail
            for field in ("layout_from", "new_workbook", "merged_into", "note"):
                val = (r.get(field) or "").strip()
                if val:
                    entry[field] = val
            # CSV first, then RULES — so a documented decision always beats a
            # bare cell, and the existing 18 applications are untouched.
            entry.update(_flat_rules_from_csv(r))
            entry.update(RULES.get(key, {}))
            out.append(entry)
    return out


def _load_groups():
    """Website section per slug, in the order each section lists them.

    Was `APP_GROUPS`, a literal. Now derived from the CSV's `group` and
    `group_order`, because a new application's section is a flat fact and
    having to edit a second list was one of the steps that got forgotten.
    """
    rows = []
    with io.open(APPLICATIONS_CSV, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            slug = (r.get("slug") or "").strip()
            group = (r.get("group") or "").strip()
            if not slug or not group:
                continue
            try:
                order = int((r.get("group_order") or "").strip() or 0)
            except ValueError:
                order = 0
            rows.append((group, order, slug))
    out = {}
    for group, order, slug in sorted(rows, key=lambda x: (x[0], x[1])):
        out.setdefault(group, []).append(slug)
    # Keep the section order the site uses, not alphabetical.
    return {g: out[g] for g in ("transcriptomics", "genomics", "epigenomics",
                                "additional") if g in out}


APPLICATIONS = _load_applications()
APP_GROUPS = _load_groups()
GROUP_OF = {slug: g for g, slugs in APP_GROUPS.items() for slug in slugs}


def published():
    return [a for a in APPLICATIONS if a["status"] == BUILD]


def by_slug(slug):
    for a in published():
        if a["slug"] == slug:
            return a
    return None
