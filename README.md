# ATGC submission forms

One public web form per application. A researcher fills it in, downloads an
`.xlsx`, and emails it to the lab (D12). Nothing is submitted to a server, there
are no accounts, and no researcher data leaves the browser.

    python build.py          # rebuild every page into dist/, then verify
    python build.py --report # ...and list everything the build changed

`dist/` is generated wholesale — **never hand-edit anything in it.**

---

## The one thing to know first

**The form must name services exactly as the quote does.** A researcher reads
their quote and picks the matching option; if the names differ, they guess. That
is why library preps, flow cells and extraction services all come from
`data/reference/services.csv` rather than from the old workbooks, and why the
build reports anything it could not match.

---

## Who touches what

    SubmissionForm/    the researcher-facing app — this is what gets published
    ../FormAdmin/      the LAB's tool for changing kits and forms

The admin tool lives **outside this folder on purpose**. Researchers reach the
form by URL, so anything inside the published app is potentially reachable;
`FormAdmin` reaches in to edit data files, never the other way round. The build
enforces it — `dist/` may contain only pages and assets, and fails on anything
else.

    ..\FormAdmin\Manage Forms.bat      double-click, guided prompts

---

## Everyday changes

Either use `..\FormAdmin\Manage Forms.bat`, which asks the questions and
re-runs the checks, or edit the data files directly as below.

### Change who receives a form

Edit **`data/routing.csv`** in Excel and rebuild.

| Column | Meaning |
|---|---|
| `to` | recipients, separated by `;` |
| `cc` | optional |
| **blank `to`** | **this application is NOT offered at that lab** — the lab disappears from the dropdown |

An application with one lab left shows it locked, with a note, instead of a
pointless dropdown. The build fails if any application ends up with no lab at
all, and checks every address is well formed and at `technion.ac.il`.

### Add or change a library prep / kit

1. Make sure the service exists in `data/reference/services.csv`. If it does
   not, it cannot be quoted — add it there first (see below).
2. Edit **`data/form_kits.csv`** — one row per application/kit. Excel is fine,
   or use `add-kit` / `drop-kit` in the admin tool, which checks the kit against
   the catalog first.
3. Rebuild. The build prints what it pruned and flags any option with no catalog
   entry:

       catalog gaps  : 1 offered service(s) with no catalog entry
                       18S library prep — on metagenomics-16s-18s; cannot be quoted yet

**Use the catalog's exact wording.** Where the old workbooks used looser names,
`data/prep_aliases.csv` maps them; rows marked `CHECK` are proposals and are
ignored until someone sets `confidence` to `ok`.

Size variants are handled automatically: the catalog prices
`[2 samples]`, `[4 samples]` and so on separately, but the form offers the base
service and staff pick the size when quoting. Anything that is *not* a size —
`[1BC]` vs `[4BC]`, `[PCR1-library]` — stays a separate option, because those
are real choices.

### Add a new service to the catalog

`data/reference/services.csv`, with a timestamped backup into
`data/reference/_backups/` first. Copy the nearest existing row and change the
`service_id`, `description` and prices.

Leave `sap_cat_no` **blank** unless you have the real number — a wrong SAP
number reaches a real invoice. Note in `remarks` what is still missing.

### Change the analysis questions

`docs/05_Analysis_Intake_Spec.md` is the authority for what each application
asks; the sets live in `SETS` in `assets/form.js`. Change both together.

---

## Adding a whole new form

Everything is driven by one entry in `data/applications.py`:

```python
dict(slug="my-new-service",              # PERMANENT — see below
     name="My New Service",
     status=BUILD,
     site=SITE + "my-new-service/",      # the page on the website
     analysis=None,                      # or a set from docs/05
     workbook="Some folder/Some-form.xlsx",
     root=WEBSITE),
```

Then:

1. Add its rows to `data/routing.csv` (one per lab).
2. Add it to `APP_GROUPS` so it takes the right section colour.
3. Add `FORM_PREPS["my-new-service"]` if it offers library preps.
4. `python tools/check_registry.py` — it verifies the workbook path resolves,
   the slug is unique and URL-safe, and every application has a lab.
5. `python build.py`.

**No workbook yet?** Use `layout_from=` to borrow another application's
structure, as `shotgun-metagenomics` borrows DNA-seq's.

### Slugs are permanent

`slug` becomes a public URL — `.../atgc-submission-forms/rnaseq/` — which ends
up in emails, bookmarks and on the website. **Never rename one.** If it truly
must change, keep the old directory as a redirect. Regenerate
`docs/WEBSITE_LINKS.csv` and hand it to whoever edits the site.

### Switching a form off

Set `status=WITHDRAWN` and `slug=None`, and add a `note` saying why. The form
stops being built; the workbook is left alone. If the *service* is gone rather
than just the form, add it to `atgc/retired.py` so QuoteDesk and the lab report
drop it too — that is how CEL-seq2 and Infinium methylation were handled.

---

## What the build checks, and why

| Check | Why it exists |
|---|---|
| no prices in any page | the pages are public; `services.csv` carries prices (D12) |
| no typos | `Basesapce`, `insturment` and friends were in 20 workbooks |
| JS syntax | a broken script leaves the HTML perfectly valid, so everything else still "passes" |
| recipients well formed | `linde@technion` looks fine in Excel and bounces in a mail client |
| every application routed | a form with no recipient has nowhere to go |
| no retired terms | MiSeq, `P3 50 cycles`, CEL-seq2 |
| catalog gaps | an option nobody can be quoted for |
| publish scope | only pages and assets in `dist/` — no data files, no scripts |

A failing check stops the build. If one ever cries wolf, fix the check — a
check people learn to ignore is worse than no check.

---

## Publishing — `main` is NOT the branch the site serves

The live site is served from **`gh-pages`**. `main` holds the source. Pushing a
fix to `main` changes nothing that a researcher can see, and the push succeeds,
which is what makes the mistake so easy to make and so easy to announce.

One command, always:

    python tools/publish.py "Rebuild: what changed"

It builds, refuses to go on unless every check above passes, re-checks that
nothing but pages and assets is about to become public, replaces `gh-pages`
wholesale — so a page deleted from `dist/` actually disappears from the site —
pushes, and then polls the live URL until it serves the build just made. It
does not print `LIVE` until the live page proves it.

Do not push `dist/` by hand, and do not trust a green push to `main`.

---

## Layout

    build.py                 renders dist/ and runs every check
    template.html            the page shell; per-application content is injected
    data/applications.py     the registry — every decision that is not in a file
    data/routing.csv         who receives each form, per lab
    data/prep_aliases.csv    old workbook wording -> catalog service names
    tools/survey_workbooks.py  reads the source workbooks
    tools/schema.py          workbook + decisions -> the spec each page renders
    tools/check_registry.py  registry sanity, run it after editing the registry
    tools/publish.py         build + push to gh-pages + verify it went live
    assets/                  shared css, js, logo — one copy for all pages
      form.js                the form itself
      xlsx.js / xlsx_read.js writing and reading .xlsx, no dependencies
      quote.js               reading a QuoteDesk-stamped quote

Source workbooks under `Y:\LAB\` are **read-only** and are never modified.
