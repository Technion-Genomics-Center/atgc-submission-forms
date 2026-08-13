# -*- coding: utf-8 -*-
"""The application registry — one entry per form the site will publish.

Structure comes from the workbooks (see tools/survey_workbooks.py); the
DECISIONS here come from docs/05_Analysis_Intake_Spec.md and are not derivable
from any file. Keep this the only place they are written down: build.py reads
it, and doc 05 §12 is the prose that explains it.

`slug` is a PUBLIC CONTRACT. The website links to /SubmissionForm/<slug>/ and
those links end up in emails and bookmarks. Never rename one; add to
`slug_aliases` instead so the old URL keeps working.
"""

from __future__ import annotations

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

WEBSITE = r"Y:\LAB\TGC_website\ATGC_website_2025\Applications"
FORMS = r"Y:\LAB\Forms\Submission_forms"

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
APP_GROUPS = {
    "transcriptomics": ['rnaseq', 'mirna-seq', 'scrna-seq-10x', 'spatial-transcriptomics'],
    "genomics": ['amplicon-seq', 'dna-seq', 'exome-seq', 'nanopore', 'metagenomics-16s-18s', 'shotgun-metagenomics'],
    "epigenomics": ['chip-seq-cut-and-run', 'rrbs', 'infinium-methylation'],
    "additional": ['cell-line-authentication', 'extraction', 'dna-rna-quality-quantity', 'olink-reveal', 'user-prepared'],
}

GROUP_OF = {slug: g for g, slugs in APP_GROUPS.items() for slug in slugs}

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


APPLICATIONS = [
    # ── sequencing forms with an analysis panel ─────────────────────────────
    dict(slug="rnaseq", site=SITE + "rna-seq/", name="RNA-seq", status=BUILD, analysis=RNASEQ,
         workbook="RNA-seq additional files/RNAseq-electronic 2025.xlsx",
         root=WEBSITE,
         # doc 05 §11 — RNAseq-extraction folded in behind a Yes/No.
         extraction="rna",
         # Nitsan, 2026-08-12. The workbook offered one vague "[rRNA removal]"
         # option. Three different kits do rRNA removal and they are priced and
         # run differently, so the form names each — a researcher reading their
         # quote can then pick the one they were quoted.
         ),

    dict(slug="scrna-seq-10x", site=SITE + "single-cell-transcriptomics/", name="10X scRNA-seq", status=BUILD, analysis=SCRNA,
         workbook="sc10X-electronic_2025.xlsx", root=FORMS,
         # Nitsan, 2026-08-12. The workbook predates it. Catalog carries five
         # size variants (2/4/6/8 samples, and a T10 24-sample); the researcher
         # picks the prep, staff pick the size when quoting.
         extra_preps=["Illumina/Fluent scRNA-seq library prep"],
         # doc 05 §3.1 — CellRanger is a priced pipeline, not a bespoke
         # analysis, so it is asked separately and is never gated by the
         # consultation. Unlike Spatial's SpaceRanger it applies to every kit.
         primary_analysis=dict(
             label="Do you require primary analysis (CellRanger)?",
             catalog="Primary analysis- CellRanger")),

    dict(slug="spatial-transcriptomics", site=SITE + "spatial-transcriptomics/", name="Spatial transcriptomics",
         status=BUILD, analysis=SPATIAL,
         workbook="Spatial-electronic_2025.xlsx", root=FORMS,
         # Nitsan, 2026-08-11. REPLACES the workbook's eight Visium/CosMx
         # variants outright — the FFPE 11mm, PFA-fixed and fresh/frozen options
         # are no longer offered. `catalog` is the canonical service each kit
         # bills as; None means the catalog has no entry yet (doc 05 §17).
         library_kits=[
             dict(label="Visium HD",
                  catalog="10X Visium HD 6.5mm  [2 slides]"),
             dict(label="Visium HD 3'",
                  catalog="10X Visium HD 3' [2 slides]",
                  # Billing name confirmed by Nitsan; the catalog entry itself
                  # does not exist yet and has NO price. Needs adding via
                  # Module 0 before this kit can be quoted.
                  needs_catalog_entry=True, needs_price=True),
             # Priced identically; the species split exists so the lab pulls
             # the right kit. One catalog entry, two form options.
             dict(label="CosMx x1000 mouse",
                  catalog="CosMx 1000plex [2 slides]", lab_kit="mouse"),
             dict(label="CosMx x1000 human",
                  catalog="CosMx 1000plex [2 slides]", lab_kit="human"),
             dict(label="CosMx x6000",
                  catalog="CosMx 6000plex [2 slides]"),
             dict(label="CosMx WT human",
                  catalog="CosMx WTS [2 slides]", lab_kit="human"),
         ],
         # SpaceRanger is 10X Visium software, so the primary/full split
         # applies to the Visium HD kits only. CosMx primary analysis runs on
         # the instrument and is not ordered here (doc 05 §3.2).
         primary_analysis=dict(
             label="Do you require primary analysis (SpaceRanger)?",
             catalog="Primary analysis- SpaceRanger",
             only_for_kits=["Visium HD", "Visium HD 3'"]),
         # Nitsan, 2026-08-13. CosMx is imaged on the instrument; nothing goes
         # on a flow cell. Visium HD does get sequenced, so the sequencing
         # questions follow the kit rather than the application.
         flowcell_only_for_kits=["Visium HD", "Visium HD 3'"],
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

    dict(slug="metagenomics-16s-18s", site=SITE + "metagenomics/", name="Metagenomics — 16S / 18S",
         status=BUILD, analysis=AMPLICON16S,
         workbook="Metagenomics/Metagenomics-electronicV2_2025.xlsx",
         root=WEBSITE,
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
    dict(slug="shotgun-metagenomics", site=SITE + "dna-seq/",
         service_page=SITE + "metagenomics/", name="Shotgun metagenomics",
         status=BUILD, analysis=SHOTGUN,
         workbook=None,
         layout_from="DNA-seqeucning additional files/DNAseq-electronicV2_2025.xlsx",
         root=WEBSITE,
         new_workbook="Shotgun-metagenomics-electronic_2026.xlsx",
         # Quoted and reported under the DNA-seq prep — a new form, not a new
         # catalog service.
         catalog_prep="NEBNext DNA library prep",
         extraction="dna"),

    dict(slug="amplicon-seq", site=SITE + "amplicon-seq/", name="Amplicon-seq", status=BUILD, analysis=AMPLICON,
         workbook="Amplicon-seq/Amplicon-seq-electronic_2025.xlsx", root=WEBSITE),

    dict(slug="dna-seq", site=SITE + "dna-seq/", name="DNA-seq", status=BUILD, analysis=DNASEQ,
         extraction="dna",
         workbook="DNA-seqeucning additional files/DNAseq-electronicV2_2025.xlsx",
         root=WEBSITE),

    dict(slug="exome-seq", site=SITE + "exome-seq/", name="Exome-seq", status=BUILD, analysis=EXOME,
         workbook="Exsome-seq/Exome-seq-electronicV2_2025.xlsx", root=WEBSITE),

    dict(slug="chip-seq-cut-and-run", site=SITE + "chip-seq/", name="ChIP-seq / Cut&Run",
         status=BUILD, analysis=CHIP,
         # Nitsan, 2026-08-12. One form, but which protocol was run has to be
         # recorded: the kit is the same and the protocols are not, and
         # downstream processing depends on knowing which. BLOCKING, because a
         # submission that does not say is ambiguous the moment it arrives.
         protocol_choice=dict(
             label="Which protocol?", options=["ChIP-seq", "Cut&Run"]),
         workbook="ChIP-seq and cut&run additional files/ChIP-seq_Cut&Run-electronic_2025.xlsx",
         root=WEBSITE),

    dict(slug="rrbs", site=SITE + "dna-methylation/", name="RRBS", status=BUILD, analysis=RRBS,
         extraction="dna",
         workbook="Methylation additional files/RRBS-electronic_2025.xlsx",
         root=WEBSITE),

    dict(slug="olink-reveal", site=SITE + "olink_reveal/", name="Olink Reveal", status=BUILD, analysis=OLINK,
         workbook="Olink Reveal/Olink_reveal-electronicV2_2025.xlsx", root=WEBSITE,
         # doc 05 §16.2 — keeps its own plate-based table, no concentration.
         keep_own_table=True,
         # Nitsan, 2026-08-13: the free-text "other" column is not used, and
         # Olink plates are not QC'd here.
         drop_columns=["Sample Type- other"],
         no_qc=True),

    # The researcher brings a finished library, so there is no prep to choose.
    dict(slug="user-prepared", no_library_prep=True, no_experimental_group=True,
         # No prep to choose, but the library still gets measured before it
         # goes on a flow cell (Nitsan, 2026-08-12).
         qc_services=["Qubit measurement", "TapeStation"],
         site=SITE + "user-prepared-library-sequencing/", name="User-prepared library sequencing",
         status=BUILD, analysis=USER_PREPARED,
         workbook="User-prepared library sequencing additional files/User-prepared-electronicV2_2025.xlsx",
         root=WEBSITE),

    # ── forms with the question but no panel, doc 05 §12.2 ──────────────────
    dict(slug="nanopore", site=SITE + "long-read-sequencing/", name="Oxford Nanopore", status=BUILD, analysis=None,
         # Nanopore has its own flow cells and its own run settings — the
         # NextSeq questions do not apply. The library prep still does.
         no_flowcell=True,
         workbook="Long read sequencing additional files/Oxford Nanopore-electronic_2025.xlsx",
         root=WEBSITE),

    dict(slug="mirna-seq", site=SITE + "mirna-seq/", name="miRNA-seq", status=BUILD, analysis=None,
         extraction="rna",
         workbook="miRNA-seq additional files/miRNAseq-electronic 2025.xlsx",
         root=WEBSITE),

    # ── no bioinformatics question at all, doc 05 §12.5 ─────────────────────
    dict(slug="cell-line-authentication", site=SITE + "cell-line-authentication/", name="Cell-line authentication",
         status=BUILD, analysis=None, no_analysis_question=True,
         # doc 05 §16.3 — normalised naming, but still no experimental group.
         no_experimental_group=True,
         # A lab service, not a sequencing run: the workbook asks only about DNA
         # extraction, and nothing is sequenced, so no prep, flow cell, run mode
         # or flow-cell count belongs on it.
         no_sequencing=True,
         extraction="dna",
         workbook="Cell-line authentication additional files/CLA-electronic_2025.xlsx",
         root=WEBSITE),

    dict(slug="dna-rna-quality-quantity", site=SITE + "dna-rna-quality-and-quantity/", name="DNA/RNA quality and quantity",
         status=BUILD, analysis=None, no_analysis_question=True,
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
         ),
         workbook="DNA-RNA quality and quantity additional files/DNA-RNA_Quality_&_Quantity-electronic_2025.xlsx",
         root=WEBSITE),

    # Nitsan, 2026-08-12: no longer offered.
    dict(slug=None, name="Infinium methylation", status=WITHDRAWN,
         workbook="Methylation additional files/Infinium-methylation-electronic_2025.xlsx",
         root=WEBSITE,
         note="Service withdrawn. RRBS remains the methylation application."),

    # doc 05 §12.3 — extraction produces no data to analyse; the bioinformatics
    # question is vestigial and is dropped.
    dict(slug="extraction", site=SITE + "dna-rna-extraction/", name="DNA / RNA extraction",
         status=BUILD, analysis=None, no_analysis_question=True,
         # Nothing is sequenced here. The whole service is: extract, and measure
         # what came out. Library prep and flow cell belong to the application
         # that follows, on its own form.
         # Asking "do you require extraction?" on the extraction form is asking
         # someone why they are here. It is always yes.
         no_sequencing=True, extraction="both", extraction_always=True,
         qc_services=["Qubit measurement", "TapeStation"],
         workbook="DNA-RNA extraction additional files/Extraction sample submission-electronic_2025.xlsx",
         root=WEBSITE),

    # ── not published ───────────────────────────────────────────────────────
    dict(slug=None, name="CEL-seq2", status=WITHDRAWN,
         workbook="CEL-Seq2 additional files/CELseq-electronic 2025.xlsx",
         root=WEBSITE,
         note="Service withdrawn. Also remove CEL-Seq2 from the LibraryPrep "
              "vocabulary of the RNA-seq forms."),

    dict(slug=None, name="RNA-seq with extraction", status=MERGED,
         merged_into="rnaseq",
         workbook="RNA-seq additional files/RNAseq-extraction-electronic 2025.xlsx",
         root=WEBSITE),

    dict(slug=None, name="Metagenomics with extraction", status=MERGED,
         merged_into="metagenomics-16s-18s",
         workbook="Metagenomics/Metagenomics-extraction-electronicV2_2025.xlsx",
         root=WEBSITE),
]

# Superseded by the 16S/18S + Amplicon-seq split (doc 05 §4). Never built, never
# deleted — it lives on read-only storage.
SUPERSEDED = ["Amplicon_16S-seq-electronic_2025.xlsx"]

# Old URLs that must keep working if a slug is ever retired.
SLUG_ALIASES: dict[str, str] = {}


def published():
    return [a for a in APPLICATIONS if a["status"] == BUILD]


def by_slug(slug):
    for a in published():
        if a["slug"] == slug:
            return a
    return None
