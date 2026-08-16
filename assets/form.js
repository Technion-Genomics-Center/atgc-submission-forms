/* ATGC submission form — behaviour.
 *
 * Everything here runs in the browser and nothing leaves it: no fetch, no
 * upload, no analytics. window.APP is the per-application spec that build.py
 * injected; this file is identical on all 18 pages.
 *
 * Rules implemented here are specified in docs/05_Analysis_Intake_Spec.md.
 * The two that are easy to get backwards:
 *   - a quote NEVER blocks anything (D8)
 *   - the Technion budget number NEVER blocks; it highlights (§18.3)
 */
'use strict';

const APP = window.APP;
const $ = (s, r = document) => r.querySelector(s);

/* ── header fields, doc 05 §15 ─────────────────────────────────────────── */
const HEADER_FIELDS = [
  { id: 'date',      label: 'Date',              type: 'date' },
  { id: 'lab',       label: 'Submitting to which ATGC lab?', type: 'select',
    options: [...new Set((window.APP.routing || []).map(r => r.lab))],
    help: 'This decides who receives your form.' },
  { id: 'name',      label: 'Name',              type: 'text' },
  { id: 'group',     label: 'Group / PI',        type: 'text' },
  { id: 'institute', label: 'Institute',         type: 'text' },
  { id: 'faculty',   label: 'Faculty (Technion only)', type: 'text',
    hint: 'Free text, English' },
  { id: 'email',     label: 'Email',             type: 'email' },
  { id: 'phone',     label: 'Phone',             type: 'tel' },
  { id: 'quote',     label: 'Quote number',      type: 'text',
    hint: 'Optional — not required' },
  { id: 'basespace', label: 'BaseSpace account', type: 'text',
    help: 'Sequencing data is delivered through BaseSpace.',
    link: { href: 'https://atgc.net.technion.ac.il/files/2025/02/' +
                  'Downloading-your-sequencing-data-from-BaseSapce-2025-4.pdf',
            text: 'How to open a BaseSpace account (PDF)' } },
  { id: 'budget',    label: 'Technion budget number', type: 'text',
    help: 'Only Technion accounts pay by budget number. Leave blank otherwise.' },
];

/* Sample naming — the rules Samplesheet_generator already enforces. */
const ILLEGAL = /[^A-Za-z0-9_.]/;
const NAMING_TEXT =
  'Sample names must be unique, and may use letters, numbers, underscore ' +
  'and full stop only — no spaces, no hyphens, and none of / \\ : * ? " < > |';

/* Plates are 96 or 384, and multi-plate submissions do happen. Typing beyond
 * a plate is miserable, so past this many rows we point at the upload route —
 * but we never refuse the rows. */
const BIG_SUBMISSION = 96;
const MAX_ROWS = 1536;              // four 384 plates

const state = { rows: [], warnings: [], id: null };

/* ── build the page from the spec ──────────────────────────────────────── */
function field(f) {
  const wrap = document.createElement('div');
  wrap.className = 'field';
  wrap.dataset.field = f.id;
  const link = f.link
    ? `<p class="hint"><a href="${f.link.href}" target="_blank" ` +
      `rel="noopener">${f.link.text} &nearr;</a></p>`
    : '';
  const control = f.type === 'select'
    ? `<select id="f-${f.id}"><option value=""></option>` +
      f.options.map(o => `<option>${o}</option>`).join('') + '</select>'
    : `<input type="${f.type}" id="f-${f.id}">`;
  /* Help is a visible line, not a "?" tooltip. See renderChoices() for why. */
  wrap.innerHTML =
    `<label>${f.label}${control}</label>` +
    (f.help ? `<p class="hint hint-help">${f.help}</p>` : '') +
    (f.hint ? `<p class="hint">${f.hint}</p>` : '') + link;
  return wrap;
}

function renderHeader() {
  const box = $('#header-fields');
  HEADER_FIELDS.forEach(f => box.appendChild(field(f)));
  $('#f-date').valueAsDate = new Date();

  /* Several applications run at one lab only (data/routing.csv). Where there is
   * no choice to make, make it for them: select it, lock it, and say so — a
   * dropdown holding a single option is a click that teaches nothing. */
  const labs = [...new Set((APP.routing || []).map(r => r.lab))];
  const labEl = $('#f-lab');
  if (labs.length === 1) {
    labEl.value = labs[0];
    labEl.disabled = true;
    const note = document.createElement('p');
    note.className = 'hint';
    note.textContent = `${APP.name} runs at ${labs[0]} only.`;
    $('[data-field="lab"]').appendChild(note);
  }

  // doc 05 §18.3 — detect Technion, highlight an empty budget number. Never block.
  const check = () => {
    const email = $('#f-email').value.trim().toLowerCase();
    const inst = $('#f-institute').value.trim().toLowerCase();
    const isTechnion =
      /@([\w-]+\.)*technion\.ac\.il$/.test(email) ||
      inst.includes('technion') || inst.includes('טכניון');
    const wrap = $('[data-field="budget"]');
    const empty = !$('#f-budget').value.trim();
    wrap.classList.toggle('is-warn', isTechnion && empty);
    let note = wrap.querySelector('.budget-note');
    if (isTechnion && empty) {
      if (!note) {
        note = document.createElement('p');
        note.className = 'hint budget-note';
        note.textContent = 'Technion accounts are paid by budget number — please add yours.';
        wrap.appendChild(note);
      }
    } else if (note) { note.remove(); }
  };
  // Both events: 'input' covers typing, 'change' covers paste, autofill and a
  // browser filling the field on restore. Binding only 'input' silently skips
  // the highlight for anyone who pastes their institute in.
  ['f-email', 'f-institute', 'f-budget'].forEach(id => {
    $('#' + id).addEventListener('input', check);
    $('#' + id).addEventListener('change', check);
  });
}

function renderChoices() {
  const box = $('#choice-fields');

  /* "Sequencing" is wrong on a form that sequences nothing — extraction,
   * cell-line authentication and quality-and-quantity all ask for services
   * instead. */
  if (APP.no_sequencing) $('#choices-heading').textContent = 'Services required';
  const v = APP.vocabularies || {};
  const add = (id, label, opts, help, dflt) => {
    // An empty list is legitimate when the options are filled in later.
    if (!opts) return null;
    const wrap = document.createElement('div');
    wrap.className = 'field';
    wrap.dataset.field = id;
    /* Help is a visible line under the field, NOT a "?" tooltip.
     *
     * The "?" was inside the <label>, and the <label> also wraps the <select>.
     * So clicking it did not show help — it activated the label and opened the
     * dropdown. The only way to reach the text was to hover and wait for the
     * OS tooltip, which never happens on a phone and rarely on a desktop. An
     * affordance that promises help and opens a dropdown instead is worse than
     * no affordance, so the text is simply shown. */
    wrap.innerHTML =
      `<label>${label}<select id="c-${id}">` +
      '<option value=""></option>' +
      opts.map(o => {
        const val = typeof o === 'string' ? o : o.label;
        return `<option${val === dflt ? ' selected' : ''}>${val}</option>`;
      }).join('') +
      '</select></label>' +
      (help ? `<p class="hint hint-help">${help}</p>` : '');
    box.appendChild(wrap);
    return wrap;
  };

  /* Where two protocols share a form, which one was run must be recorded —
   * the kit is the same but the downstream handling is not. Radio buttons
   * rather than a dropdown: two mutually exclusive options both visible is
   * one glance instead of one click, and it cannot be left looking answered. */
  if (APP.protocol_choice) {
    const wrap = document.createElement('div');
    wrap.className = 'field';
    wrap.dataset.field = 'protocol';
    wrap.innerHTML = `<span class="grouplabel">${APP.protocol_choice.label}</span>` +
      '<div class="radios">' + APP.protocol_choice.options.map(o =>
        `<label class="radio"><input type="radio" name="protocol" value="${o}">${o}</label>`
      ).join('') + '</div>';
    box.appendChild(wrap);
  }

  const quoteHelp = 'If you are unsure, this is stated on your quote — the ' +
    'names here match the names there.';
  add('libprep', 'Library preparation', v.LibraryPrep, quoteHelp);
  const ltWrap = add('librarytype', 'Library type', v.LibraryType);
  const rgWrap = add('region', '16S region', v.Region);

  /* doc 05 §4.1 — the header choice fills the per-sample Library Type column,
   * folding the region in for 16S. A hand-edited row is never overwritten:
   * the header says what the submission contains, the column says what each
   * sample is, and only the researcher knows when they differ. */
  if (ltWrap && APP.columns.includes('Library Type')) {
    const fill = () => {
      const type = $('#c-librarytype').value;
      if (!type) return;
      if (type.startsWith('Mixed')) {
        const note = $('#table-report');
        note.hidden = false; note.className = 'msg warn';
        note.textContent = 'Mixed submission — please set the library type on ' +
          'each sample row.';
        return;
      }
      const region = rgWrap && $('#c-region').value;
      const value = (type === '16S' && region) ? `16S ${region}` : type;
      let touched = 0;
      document.querySelectorAll('#samples tbody [data-col="Library Type"]')
        .forEach(el => { if (!el.dataset.edited) el.value = value; else touched++; });
      if (touched) {
        const note = $('#table-report');
        note.hidden = false; note.className = 'msg warn';
        note.textContent = `${touched} row(s) have a library type you set by ` +
          'hand and were left alone.';
      }
    };
    ['c-librarytype', 'c-region'].forEach(id => {
      const el = $('#' + id); if (el) el.addEventListener('change', fill);
    });
    document.addEventListener('input', e => {
      if (e.target.dataset && e.target.dataset.col === 'Library Type')
        e.target.dataset.edited = '1';
    });
  }
  add('flowcell', 'Flow cell', v.FlowCell, quoteHelp);
  add('runmode', 'Run mode', v.RunMode);
  add('runs', 'Number of flow cells', v['Run#'], null, '1');

  /* Extraction is two questions, not one: most submissions arrive already
   * extracted, so the kit list only appears once it is wanted. */
  if (v.ExtractionService || v.ExtractionByType) {
    /* On the extraction form itself the answer is always yes, so the question
     * is not asked — only which nucleic acid and which service. */
    if (!APP.extraction_always)
      add('needext', 'Do you require extraction?', ['Yes', 'No'], null, 'No');

    /* Where both DNA and RNA are offered, ask which first: twelve services in
     * one dropdown is a list to scroll, four is a choice to make. */
    const byType = v.ExtractionByType;
    const typeWrap = byType
      ? add('exttype', 'DNA or RNA?', Object.keys(byType)) : null;
    const kit = add('extraction', 'Extraction service',
                    byType ? [] : v.ExtractionService);
    if (byType) {
      $('#c-exttype').addEventListener('change', () => {
        const list = byType[$('#c-exttype').value] || [];
        $('#c-extraction').innerHTML = '<option value=""></option>' +
          list.map(o => `<option>${o}</option>`).join('');
      });
    }
    const sync = () => {
      const on = APP.extraction_always || $('#c-needext').value === 'Yes';
      if (typeWrap) typeWrap.hidden = !on;
      kit.hidden = !on || (!!byType && !$('#c-exttype').value);
      if (!on) { $('#c-extraction').value = ''; if (typeWrap) $('#c-exttype').value = ''; }
      if (APP.extraction_always) { /* nothing to hide */ }

      /* doc 05 §11.2 — the note the RNAseq-extraction workbook carried. */
      let note = $('#extraction-note');
      if (on && !note) {
        note = document.createElement('p');
        note.id = 'extraction-note';
        note.className = 'msg warn';
        note.textContent = 'For extraction from tissue, please state whether ' +
          'the material is fresh or frozen in the Remarks column. Concentration ' +
          'and purity cannot be known before extraction, so those columns are ' +
          'not asked for.';
        $('#choice-fields').parentElement.appendChild(note);
      } else if (!on && note) { note.remove(); }

      reshapeSamples();
    };
    if (byType) $('#c-exttype').addEventListener('change', sync);
    $('#c-needext').addEventListener('change', sync);
    sync();
  }

  /* Cell-line authentication and the like are lab services, not sequencing
   * runs: no prep, no flow cell, and no QC-before-sequencing question. */
  if (!APP.no_sequencing && !APP.no_qc)
    add('qc', 'QC required', ['Yes', 'No'], null, 'Yes');

  /* Some forms name the QC service, because the library arrives finished and
   * measuring it is the only lab step. Shown only when QC is wanted. */
  if (APP.qc_services) {
    /* One, the other, or both — a library can be quantified and sized. A single
     * choice would force a wrong answer. */
    const wrap = document.createElement('div');
    wrap.className = 'field';
    wrap.dataset.field = 'qcservice';
    wrap.innerHTML = '<span class="grouplabel">QC service (choose any)</span>' +
      '<div class="radios">' + APP.qc_services.map(o =>
        `<label class="radio"><input type="checkbox" name="qcservice" value="${o}">${o}</label>`
      ).join('') + '</div>';
    box.appendChild(wrap);
    const syncQc = () => {
      wrap.hidden = $('#c-qc').value !== 'Yes';
      if (wrap.hidden) wrap.querySelectorAll('input').forEach(i => { i.checked = false; });
    };
    $('#c-qc').addEventListener('change', syncQc);
    syncQc();
  }

  /* CosMx and Visium are different technologies sharing one form. CosMx is
   * imaged on the instrument and never sequences; Visium is sequenced. Each
   * kit declares which it is (data/applications.py), so the run questions
   * appear only for a kit that actually reaches a flow cell. */
  if (APP.sequenced_kits && $('#c-libprep')) {
    const runFields = ['flowcell', 'runmode', 'runs'];
    const syncRun = () => {
      const sequenced = APP.sequenced_kits.includes($('#c-libprep').value);
      runFields.forEach(id => {
        const w = $(`[data-field="${id}"]`);
        if (!w) return;
        w.hidden = !sequenced;
        if (!sequenced) $('#c-' + id).value = '';
      });
    };
    $('#c-libprep').addEventListener('change', syncRun);
    syncRun();
  }

  /* Read length follows the flow cell: the shortest read of each part is run
   * single-read, everything longer is paired-end. The researcher can override
   * — this only sets the starting point. */
  const fc = $('#c-flowcell'), rm = $('#c-runmode');
  if (fc && rm) {
    fc.addEventListener('change', () => {
      const chosen = (v.FlowCell || []).find(o => o.label === fc.value);
      if (chosen && chosen.runmode) rm.value = chosen.runmode;
    });
  }
}

/* An empty section is worse than no section — a heading with nothing under it
 * reads as something that failed to load. */
function dropEmptySections() {
  document.querySelectorAll('form > section').forEach(sec => {
    const grid = sec.querySelector('.grid');
    if (grid && !grid.children.length && sec.children.length <= 2) sec.remove();
  });
}

/* Which set of columns applies right now. Asking for extraction means sending
 * material, so concentration and purity cannot be known yet; asking for none
 * means the nucleic acid is already measured. */
function activeColumns() {
  const wantsExtraction = APP.extraction_always ||
    ($('#c-needext') && $('#c-needext').value === 'Yes');
  return (wantsExtraction && APP.extraction_columns) || APP.columns;
}

/* DNA/RNA quality and quantity is not a step before sequencing — measuring IS
 * the service. Each instrument is ordered separately and takes a different kit,
 * so each gets its own question, and the kit list only appears once the
 * instrument is wanted. */
function renderQcPanel() {
  const cfg = APP.qc_panel;
  if (!cfg) return;
  const box = $('#choice-fields');

  const block = document.createElement('div');
  block.className = 'qc-panel';
  block.innerHTML = `
    <p class="hint">Not sure which kit you need?
      <a href="${cfg.guide_url}" target="_blank" rel="noopener">See the kit
      options on our website &nearr;</a></p>
    <p class="msg warn">${cfg.note}</p>

    <div class="field" data-field="qubit">
      <label>${cfg.qubit.label}
        <select id="c-qubit"><option value=""></option><option>Yes</option><option selected>No</option></select>
      </label>
    </div>
    <div class="field wide" data-field="qubitkit" hidden>
      <label>${cfg.qubit.kit_label}
        <select id="c-qubitkit"><option value=""></option>${
          cfg.qubit.kits.map(k => `<option>${k}</option>`).join('')}</select>
      </label>
    </div>

    <div class="field" data-field="tapestation">
      <label>${cfg.tapestation.label}
        <select id="c-tapestation"><option value=""></option><option>Yes</option><option selected>No</option></select>
      </label>
    </div>
    <div class="field" data-field="tstype" hidden>
      <label>${cfg.tapestation.type_label}
        <select id="c-tstype"><option value=""></option>${
          Object.keys(cfg.tapestation.kits).map(k => `<option>${k}</option>`).join('')}</select>
      </label>
    </div>
    <div class="field wide" data-field="tskit" hidden>
      <label>${cfg.tapestation.kit_label}
        <select id="c-tskit"><option value=""></option></select>
      </label>
    </div>`;
  box.parentElement.insertBefore(block, box.nextSibling);

  const show = (sel, on) => { $(`[data-field="${sel}"]`).hidden = !on;
                              if (!on) $('#c-' + sel).value = ''; };

  $('#c-qubit').addEventListener('change', e =>
    show('qubitkit', e.target.value === 'Yes'));

  const syncTs = () => {
    const on = $('#c-tapestation').value === 'Yes';
    show('tstype', on);
    const type = $('#c-tstype').value;
    show('tskit', on && !!type);
    if (on && type) {
      const kits = cfg.tapestation.kits[type] || [];
      $('#c-tskit').innerHTML = '<option value=""></option>' +
        kits.map(k => `<option>${k}</option>`).join('');
    }
  };
  $('#c-tapestation').addEventListener('change', syncTs);
  $('#c-tstype').addEventListener('change', syncTs);
  syncTs();
}

function renderSamples() {
  $('#naming-rules').textContent = NAMING_TEXT;
  const t = $('#samples');
  const cols = activeColumns();
  t.innerHTML =
    '<thead><tr><th></th>' +
    cols.map(c => `<th>${c}</th>`).join('') +
    '</tr></thead><tbody></tbody>';
  setRows(1);
}

/* Swap the columns without losing what has been typed: anything whose column
 * survives the swap keeps its value. Silently discarding a filled table would
 * be the worst possible response to changing one dropdown. */
function reshapeSamples() {
  const body = $('#samples tbody');
  if (!body) return;
  const before = activeColumns.previous || APP.columns;
  const after = activeColumns();
  if (before.join('|') === after.join('|')) return;

  const kept = [...body.rows].map(tr => {
    const row = {};
    before.forEach((c, i) => {
      const el = tr.querySelectorAll('input,select')[i];
      if (el && el.value.trim()) row[c] = el.value.trim();
    });
    return row;
  });
  const lost = before.filter(c => !after.includes(c))
    .filter(c => kept.some(r => r[c]));

  activeColumns.previous = after;
  const n = body.rows.length;
  renderSamples();
  setRows(n);
  [...$('#samples tbody').rows].forEach((tr, i) => {
    after.forEach(c => {
      const el = tr.querySelector(`[data-col="${c}"]`);
      if (el && kept[i] && kept[i][c] !== undefined) el.value = kept[i][c];
    });
  });

  if (lost.length) {
    const note = $('#table-report');
    note.hidden = false; note.className = 'msg warn';
    note.textContent = 'The sample table changed for an extraction submission. ' +
      'These columns no longer apply and their values were dropped: ' +
      lost.join(', ') + '.';
  }
  validate(); saveDraft();
}

function setRows(n) {
  const body = $('#samples tbody');
  const filled = [...body.rows].filter(rowHasData).length;
  if (n < body.rows.length && filled > n) {
    if (!confirm(`${filled} rows contain data. Reducing to ${n} will remove ` +
                 `some of them. Continue?`)) {
      $('#row-count').value = body.rows.length;
      return;
    }
  }
  while (body.rows.length > n) body.deleteRow(-1);
  while (body.rows.length < n) {
    const tr = body.insertRow();
    tr.innerHTML = `<td class="rownum">${body.rows.length}</td>` +
      activeColumns().map(c => `<td>${cell(c)}</td>`).join('');
  }
  $('#row-count').value = body.rows.length;
}

/* Most columns are free text; the ones with a fixed vocabulary get a select,
 * so nobody types "qbit" and staff have to guess. */
function cell(col) {
  /* A mixed 16S/18S submission sets the type per row, so the column is a
   * dropdown rather than free text. */
  if (col === 'Library Type' && APP.sample_library_types) {
    return `<select data-col="${col}"><option value=""></option>` +
      APP.sample_library_types.map(o => `<option>${o}</option>`).join('') + '</select>';
  }
  if (col === APP.quant_column) {
    return `<select data-col="${col}"><option value=""></option>` +
      APP.quant_options.map(o => `<option>${o}</option>`).join('') + '</select>';
  }
  return `<input data-col="${col}">`;
}

const rowHasData = tr =>
  [...tr.querySelectorAll('input,select')].some(i => i.value.trim());

/* ── bioinformatics, always the final section ──────────────────────────── */
function renderBioinformatics() {
  const box = $('#bioinformatics');
  if (APP.no_analysis_question) { box.remove(); return; }

  box.innerHTML = `
    <h2>Bioinformatic analysis</h2>
    <div class="consult quiet" id="consult">
      <p><strong>Bioinformatic analysis can be submitted only after scheduling a
      consultation meeting with Liat Linde
      (<a href="mailto:linde@technion.ac.il">linde@technion.ac.il</a>) or
      Nitsan Fourier
      (<a href="mailto:nitsanf@technion.ac.il">nitsanf@technion.ac.il</a>)</strong></p>
      <p>Samples can be submitted without analysis and without a meeting.
      <a href="${APP.bioinformatics_url}" target="_blank" rel="noopener">What analysis involves &nearr;</a></p>
    </div>
    ${APP.primary_analysis ? `
    <div class="field" data-field="primary" id="primary-wrap">
      <label>${APP.primary_analysis.label}
        <select id="c-primary"><option value=""></option><option>Yes</option><option>No</option></select>
      </label>
    </div>` : ''}
    <div class="field" data-field="analysis">
      <label>Do you require bioinformatic analysis?
        <select id="c-analysis"><option value=""></option><option>Yes</option><option selected>No</option></select>
      </label>
    </div>
    <div id="analysis-panel"></div>`;

  const openPanel = () => {
    const yes = $('#c-analysis').value === 'Yes';
    $('#consult').classList.toggle('quiet', !yes);
    $('#analysis-panel').innerHTML = yes ? panelFor(APP.analysis) : '';
    if (yes) {
      const rule = BRANCHES[APP.analysis];
      if (rule && $('#a-' + rule.on)) {
        $('#a-' + rule.on).addEventListener('change', () => renderBranch(APP.analysis));
      }
      renderBranch(APP.analysis);
    }
    validate();
  };
  $('#c-analysis').addEventListener('change', openPanel);

  /* doc 05 §3.2 — SpaceRanger is 10X Visium software, so it is only asked for a
   * Visium kit. Switching to CosMx must clear the answer rather than exporting
   * an order for something that does not apply. */
  const onlyFor = APP.primary_analysis && APP.primary_analysis.only_for_kits;
  if (onlyFor && $('#c-libprep')) {
    const syncPrimary = () => {
      const show = onlyFor.includes($('#c-libprep').value);
      $('#primary-wrap').hidden = !show;
      if (!show) $('#c-primary').value = '';
    };
    $('#c-libprep').addEventListener('change', syncPrimary);
    syncPrimary();
  }

  /* doc 05 §17 — every CosMx kit can carry custom add-on genes, billed per
   * gene. Not shown for Visium. */
  if (APP.cosmx_addon && $('#c-libprep')) {
    const cfg = APP.cosmx_addon;
    const wrap = document.createElement('div');
    wrap.className = 'field';
    wrap.dataset.field = 'addon';
    wrap.innerHTML = `<label>${cfg.question}
        <select id="c-addon"><option value=""></option><option>Yes</option><option>No</option></select>
      </label>
      <div class="field" data-field="addonqty" hidden>
        <label>${cfg.quantity}<input type="number" id="c-addonqty" min="1"></label>
      </div>`;
    $('#choice-fields').appendChild(wrap);
    const syncAddon = () => {
      const isCosmx = ($('#c-libprep').value || '').startsWith(cfg.trigger_prefix);
      wrap.hidden = !isCosmx;
      if (!isCosmx) { $('#c-addon').value = ''; $('#c-addonqty').value = ''; }
      $('[data-field="addonqty"]').hidden = !isCosmx || $('#c-addon').value !== 'Yes';
    };
    $('#c-libprep').addEventListener('change', syncAddon);
    $('#c-addon').addEventListener('change', syncAddon);
    syncAddon();
  }

  /* The RNA-seq questions depend on the library prep, so rebuild if it moves. */
  if ($('#c-libprep')) $('#c-libprep').addEventListener('change', () => {
    if ($('#c-analysis').value === 'Yes') openPanel();
  });
}

/* Field sets from doc 05. Only the selected application's set is rendered.
 *
 * A field is [id, label, required] and renders as free text, or
 * [id, label, required, 'choice', [options]] where the spec names a fixed set
 * of answers. BRANCHES adds the fields that only apply once a particular
 * answer is given — DNA-seq asks four quite different things depending on the
 * type of analysis, and asking all of them at once would be nonsense.
 */
const SETS = {
  rnaseq: [['aim', 'Biological question and analysis aim', 1],
           ['comparisons', 'Comparisons required — detail each one', 1],
           ['ref', 'Genome reference (URL)', 0],
           ['gtf', 'Annotation (GTF) file (URL)', 0],
           ['genes', 'Genes for validation (KO, KI) or expected to change', 0],
           ['tissue', 'Tissue source', 0],
           ['pathways', 'Biological pathways of interest', 0]],
  spatial: [['question', 'Biological question', 1],
            ['aim', 'Analysis aim', 1],
            ['describe', 'Describe the analysis required', 1]],
  amplicon_16s: [['aim', 'Biological question and analysis aim', 1],
                 ['compare', 'Compare between experimental groups?', 1,
                  'choice', ['Yes', 'No']],
                 ['comparisons', 'If yes — detail the comparisons', 0],
                 ['env', 'Sample / environment type (gut, soil, water…)', 0],
                 ['lowbiomass', 'Low-biomass samples?', 0, 'choice', ['Yes', 'No']]],
  amplicon: [['aim', 'Biological question and analysis aim', 1],
             ['describe', 'Describe the requested analysis', 1]],
  rrbs: [['describe', 'Analysis requirements — describe what you need', 1]],
  olink: [['comparisons', 'Comparisons required — detail each one', 1]],
  chip: [['aim', 'Biological question and analysis aim', 1],
         ['ref', 'Genome reference (URL)', 0],
         ['gtf', 'Annotation (GTF) file (URL)', 0],
         ['diff', 'Is differential analysis required?', 1, 'choice', ['Yes', 'No']],
         ['comparisons', 'If yes — detail the comparisons', 0],
         ['genes', 'Genes for validation', 0],
         ['pathways', 'Biological pathways of interest', 0]],
  exome: [['aim', 'Biological question and analysis aim', 1],
          ['ref', 'Genome reference (URL)', 0],
          ['gtf', 'Annotation (GTF) file (URL)', 0],
          ['freq', 'Expected variant frequency', 1, 'choice', ['>50%', '<50%']],
          ['refsample', 'Reference sample for comparison', 1]],
  dnaseq: [['aim', 'Biological question and analysis aim', 1],
           ['type', 'Type of analysis', 1, 'choice',
            ['De-novo assembly', 'Assembly', 'Variant analysis', 'Metagenomic']]],
  user_prepared: [['which', 'Which analysis do you require?', 1, 'choice',
                   ['RNA-seq — differential expression', 'Metatranscriptomics',
                    'scRNA-seq — full analysis', '16S / 18S',
                    'Shotgun metagenomics', 'Amplicon-seq',
                    'DNA-seq — variant analysis', 'DNA-seq — de-novo assembly',
                    'ChIP-seq / Cut&Run', 'RRBS', 'Other']]],
};
SETS.scrna = SETS.rnaseq;
SETS.shotgun = SETS.amplicon_16s.concat([
  ['functional', 'Functional / pathway profiling required?', 0, 'choice', ['Yes', 'No']],
  ['mags', 'Assembly and binning (MAGs) required?', 0, 'choice', ['Yes', 'No']]]);

/* doc 05 §2.1 — bacterial rRNA-removal work may be metatranscriptomics, which
 * is a metagenomics question rather than a differential-expression one. */
const RNASEQ_BRANCH_PREP = 'NEBNext Directional RNA Library Prep [rRNA removal bacteria]';

const BRANCHES = {
  dnaseq: {
    on: 'type',
    options: {
      'De-novo assembly': [
        ['similar', 'Similar or closely related reference genomes, if any (link)', 0]],
      'Assembly': [
        ['ref', 'Genome reference (URL)', 0],
        ['gtf', 'Annotation (GTF) file (URL)', 0]],
      'Variant analysis': [
        ['ref', 'Genome reference (URL)', 0],
        ['gtf', 'Annotation (GTF) file (URL)', 0],
        ['freq', 'Expected variant frequency', 1, 'choice', ['>50%', '<50%']],
        ['refsample', 'Reference sample for comparison', 1]],
      'Metagenomic': [
        ['compare', 'Compare between experimental groups?', 1, 'choice', ['Yes', 'No']],
        ['comparisons', 'If yes — detail the comparisons', 0],
        ['env', 'Sample / environment type', 0],
        ['functional', 'Functional / pathway profiling required?', 0, 'choice', ['Yes', 'No']],
        ['mags', 'Assembly and binning (MAGs) required?', 0, 'choice', ['Yes', 'No']]],
    },
  },
  rnaseq: {
    on: 'analysistype',
    options: { 'Metatranscriptomics': null },   // null = replace with the shotgun set
  },
};

function fieldRow(spec) {
  const [id, label, req, kind, options] = spec;
  const control = kind === 'choice'
    ? `<select id="a-${id}" data-required="${req}"><option value=""></option>` +
      options.map(o => `<option>${o}</option>`).join('') + '</select>'
    : `<textarea id="a-${id}" data-required="${req}"></textarea>`;
  const NCBI = 'We use the most up-to-date genome and annotation version from ' +
    'NCBI. If another version is required, please provide a link.';
  const note = (id === 'ref' || id === 'gtf') ? `<p class="hint">${NCBI}</p>` : '';
  return `<div class="field wide" data-field="a-${id}"><label>${label}` +
         (req ? '<span class="req">*</span>' : '') + control + '</label>' + note + '</div>';
}

function panelFor(kind) {
  let set = SETS[kind] || SETS.rnaseq;

  /* doc 05 §2.1 — the bacterial rRNA-removal prep can be either differential
   * expression or metatranscriptomics, and they ask different things. */
  const prep = $('#c-libprep') && $('#c-libprep').value;
  const needsBranch = kind === 'rnaseq' && prep === RNASEQ_BRANCH_PREP;
  if (needsBranch) {
    set = [['analysistype', 'Analysis type', 1, 'choice',
            ['Differential expression', 'Metatranscriptomics']]].concat(set);
  }

  return '<div class="stack" id="analysis-fields">' +
    set.map(fieldRow).join('') + '</div>' +
    '<div class="stack" id="analysis-branch"></div>' +
    '<p class="hint">Fields marked * must be filled in before you can export. ' +
    'Hebrew is accepted in this section.</p>';
}

/* Show the fields that only apply to the answer just given. */
function renderBranch(kind) {
  const box = $('#analysis-branch');
  if (!box) return;
  const rule = BRANCHES[kind];
  if (!rule) { box.innerHTML = ''; return; }
  const chosen = $('#a-' + rule.on) && $('#a-' + rule.on).value;
  if (!chosen || !(chosen in rule.options)) { box.innerHTML = ''; validate(); return; }

  const extra = rule.options[chosen];
  // A null branch means "ask the shotgun questions instead", not "ask nothing".
  box.innerHTML = (extra || SETS.shotgun.slice(1)).map(fieldRow).join('');
  validate();
}

/* ── validation — nine blocking rules, doc 05 §18.1 ────────────────────── */
function validate() {
  const problems = [];
  const mark = (sel, bad) => {
    const el = document.querySelector(sel);
    if (el) el.classList.toggle('is-error', bad);
  };

  const need = (id, label) => {
    const el = $('#c-' + id);
    if (!el) return;
    const bad = !el.value;
    mark(`[data-field="${id}"]`, bad);
    if (bad) problems.push(label);
  };
  const labEl = $('#f-lab');
  const labBad = !labEl.value;
  $('[data-field="lab"]').classList.toggle('is-error', labBad);
  if (labBad) problems.push('Which ATGC lab you are submitting to');

  if (APP.protocol_choice) {
    const picked = document.querySelector('input[name="protocol"]:checked');
    document.querySelector('[data-field="protocol"]').classList.toggle('is-error', !picked);
    if (!picked) problems.push(APP.protocol_choice.label);
  }
  need('libprep', 'Library preparation');
  need('flowcell', 'Flow cell');
  need('qc', 'QC required');
  need('analysis', 'Bioinformatic analysis — yes or no');

  const seen = new Set();
  [...$('#samples tbody').rows].forEach((tr, i) => {
    const get = c => { const el = tr.querySelector(`[data-col="${c}"]`); return el ? el.value.trim() : ''; };
    const name = get('Sample name');
    if (name) {
      if (ILLEGAL.test(name)) problems.push(`Row ${i + 1}: illegal character in sample name`);
      if (seen.has(name)) problems.push(`Row ${i + 1}: duplicate sample name "${name}"`);
      seen.add(name);
    }
    const conc = get('ng/ul');
    if (conc && !get(APP.quant_column))
      problems.push(`Row ${i + 1}: "${APP.quant_column}" required`);
    if (activeColumns().includes('Experimental group') && rowHasData(tr) && !get('Experimental group'))
      problems.push(`Row ${i + 1}: experimental group required`);
    const org = 'Organism';
    if (activeColumns().includes(org) && rowHasData(tr) && !get(org))
      problems.push(`Row ${i + 1}: ${org.toLowerCase()} required`);
  });

  document.querySelectorAll('#analysis-panel [data-required="1"]').forEach(el => {
    if (el.closest('[hidden]')) return;
    const bad = !el.value.trim();
    el.closest('.field').classList.toggle('is-error', bad);
    if (bad) problems.push(el.previousSibling ? el.closest('label').textContent.replace('*', '').trim() : 'analysis field');
  });

  const confirmEl = $('#confirm');
  if (confirmEl && !confirmEl.checked) problems.push('Tick the confirmation before sending');
  if (confirmEl) $('#confirm-wrap').classList.toggle('is-error', !confirmEl.checked);

  const box = $('#problems');
  box.hidden = !problems.length;
  if (problems.length) {
    box.innerHTML = `<h3>${problems.length} thing${problems.length > 1 ? 's' : ''} to fix before export</h3><ul>` +
      problems.slice(0, 12).map(p => `<li>${p}</li>`).join('') +
      (problems.length > 12 ? `<li>…and ${problems.length - 12} more</li>` : '') + '</ul>';
  }
  $('#export-xlsx').disabled = !!problems.length;
  return problems;
}

/* ── draft autosave, doc 03 ────────────────────────────────────────────── */
const KEY = 'atgc-submission-' + APP.slug;

function snapshot() {
  const d = { at: Date.now(), fields: {}, rows: [] };
  document.querySelectorAll('input[id], select[id], textarea[id]').forEach(el => {
    if (el.type !== 'file') d.fields[el.id] = el.value;
  });
  [...$('#samples tbody').rows].forEach(tr =>
    d.rows.push([...tr.querySelectorAll('input,select')].map(i => i.value)));
  return d;
}

function saveDraft() { try { localStorage.setItem(KEY, JSON.stringify(snapshot())); } catch (e) {} }

function offerRestore() {
  let d; try { d = JSON.parse(localStorage.getItem(KEY)); } catch (e) { return; }
  if (!d || !d.rows) return;
  const when = new Date(d.at).toLocaleString();
  const box = $('#restore');
  box.hidden = false;
  box.innerHTML = `You have an unfinished ${APP.name} submission from ${when}. ` +
    '<button type="button" id="do-restore">Resume</button>' +
    '<button type="button" id="do-discard">Discard</button>';
  $('#do-restore').onclick = () => { applyDraft(d); box.hidden = true; };
  $('#do-discard').onclick = () => { localStorage.removeItem(KEY); box.hidden = true; };
}

function applyDraft(d) {
  setRows(d.rows.length || 1);
  Object.entries(d.fields).forEach(([id, v]) => { const el = document.getElementById(id); if (el) el.value = v; });
  if ($('#c-analysis') && $('#c-analysis').value === 'Yes')
    $('#c-analysis').dispatchEvent(new Event('change'));
  [...$('#samples tbody').rows].forEach((tr, r) =>
    [...tr.querySelectorAll('input,select')].forEach((inp, c) => {
      inp.value = (d.rows[r] || [])[c] || ''; }));
  validate();
}

/* ── submission id ─────────────────────────────────────────────────────── */
/* Short, unambiguous over the phone: no vowels (so no accidental words), no
 * 0/O or 1/I. Lives in the filename, the subject AND inside the file — a
 * researcher can edit a subject line, but the attachment travels intact. */
function submissionId() {
  const A = '23456789BCDFGHJKMNPQRSTVWXYZ';
  let s = '';
  const r = crypto.getRandomValues(new Uint8Array(6));
  for (const b of r) s += A[b % A.length];
  return 'ATGC-' + s.slice(0, 3) + '-' + s.slice(3);
}

/* ── where to send the samples ─────────────────────────────────────────── */
function renderShipping() {
  const box = $('#shipping');
  if (!box) return;
  const labs = [...new Set((APP.routing || []).map(r => r.lab))];
  const chosen = $('#f-lab').value;

  /* Show only the address they need. With no lab picked yet, show all of them
   * rather than nothing — a researcher reading ahead should not have to answer
   * a question above to find out where to post a box. */
  const show = chosen ? [chosen] : labs;
  box.innerHTML = '<h2>Shipping address</h2>' + show.map(lab => {
    const a = (APP.addresses || {})[lab] || {};
    const lines = a.lines || [];
    /* A courier or a confused researcher needs a number to ring, and it must
     * be the number for the building the box is going to. */
    const phone = a.phone
      ? `<p class="address-phone">Lab contact number: ` +
        `<a href="tel:${a.phone.replace(/[^0-9+]/g, '')}">${a.phone}</a></p>`
      : '';
    return `<div class="address">` +
      (show.length > 1 ? `<p class="address-lab">${lab}</p>` : '') +
      lines.map(l => `<p>${l}</p>`).join('') + phone + '</div>';
  }).join('');
}

/* ── who to email the downloaded file to ───────────────────────────────── */
/* There is no mailto button any more. A mailto cannot attach the file, so it
 * produced a half-written email the researcher still had to attach to — and on
 * a machine with no desktop mail client it did nothing at all. Download, then
 * tell them plainly where to send it. Addresses come from data/routing.csv, so
 * FormAdmin can change them without touching this file. */
function renderSendTo() {
  const box = $('#send-to');
  if (!box) return;
  const routes = APP.routing || [];
  const chosen = routes.find(r => r.lab === $('#f-lab').value);

  /* Before a lab is picked, show every lab's address rather than nothing — the
   * same reasoning as the shipping block above it. */
  const show = chosen ? [chosen] : routes;
  const one = show.length === 1;

  const line = r => {
    const all = [...(r.to || []), ...(r.cc || [])];
    return `<p class="send-row">` +
      (one ? '' : `<span class="send-lab">${r.lab}</span>`) +
      all.map(a => `<a href="mailto:${a}">${a}</a>`).join(' <span class="sep">and</span> ') +
      `</p>`;
  };

  box.innerHTML = '<h2>Where to send the completed form</h2>' +
    '<p class="send-lead">Download the file below, then attach it to an email to:</p>' +
    show.map(line).join('') +
    '<p class="send-note">Please attach the <strong>.xlsx</strong> file itself — ' +
    'do not paste the table into the message body.</p>';
}


/* ── the exported workbook ─────────────────────────────────────────────────
 * Three sheets, because they answer three different questions and mixing them
 * costs more than it saves (doc 05 §12):
 *   Submission  what was ordered
 *   Samples     the table, exactly as shown
 *   Analysis    the bioinformatics answers, only when analysis = Yes
 * A Warnings sheet is added only when there is something to warn about, so its
 * presence is itself the signal to staff.
 */
function collect() {
  const val = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };

  /* A <label> wraps its control, so textContent would drag in every <option>
   * of the select. Take only the label's own text nodes. */
  const labelText = el => {
    if (!el) return '';
    return [...el.childNodes].filter(n => n.nodeType === 3)
      .map(n => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
  };

  const T = v => ({ v, s: 'title' });
  const H = v => ({ v, s: 'section' });
  const L = v => ({ v, s: 'label' });
  const K = v => ({ v, s: 'head' });
  const N = v => ({ v, s: 'sub' });

  /* ── sheet 1: what was ordered ─────────────────────────────────────────── */
  /* Rows 1-6 are left clear for the logo, which floats above them; the title
   * then sits beside it, the way the page header reads. */
  const submission = [
    ['', T(APP.name + ' Submission Form')],
    ['', N('Azrieli Technion Genomics Center')],
    [], [], [], [],
    [H('Submission'), H('')],
    [L('Submission id'), state.id],
    [L('Exported'), new Date().toISOString().slice(0, 16).replace('T', ' ')],
    [],
    [H('Your details'), H('')],
  ];
  HEADER_FIELDS.forEach(f => submission.push([L(f.label), val('f-' + f.id)]));

  submission.push([], [H('Sequencing'), H('')]);
  document.querySelectorAll('#choice-fields .field').forEach(w => {
    if (w.hidden) return;                       // an unasked question has no answer
    const checks = [...w.querySelectorAll('input[type="checkbox"]:checked')];
    if (checks.length) {
      submission.push([L(w.querySelector('.grouplabel').textContent),
                       checks.map(c => c.value).join('; ')]);
      return;
    }
    const radio = w.querySelector('input[type="radio"]:checked');
    if (radio) {
      submission.push([L(w.querySelector('.grouplabel').textContent), radio.value]);
      return;
    }
    const sel = w.querySelector('select');
    if (!sel) return;
    submission.push([L(labelText(w.querySelector('label'))), sel.value]);
  });

  /* The flow cell also goes out under its CATALOG name, so the submission, the
   * quote and the lab report all name one service (D6). */
  const fc = document.getElementById('c-flowcell');
  if (fc && fc.value) {
    const match = (APP.vocabularies.FlowCell || []).find(o => o.label === fc.value);
    if (match) submission.push([L('Flow cell (catalog name)'), match.catalog]);
  }

  submission.push([], [H('Confirmation'), H('')]);
  submission.push([L('Information confirmed correct'),
                   document.getElementById('confirm').checked ? 'YES' : 'no']);
  submission.push([L('Keep excess samples for collection'),
                   document.getElementById('keep-samples').checked ? 'YES' : 'no']);

  const lab = $('#f-lab').value;
  const addr = (APP.addresses || {})[lab];
  if (addr) {
    submission.push([], [H('Deliver samples to'), H('')]);
    (addr.lines || []).forEach(l => submission.push(['', l]));
    if (addr.phone) submission.push([L('Lab contact number'), addr.phone]);
  }

  /* ── sheet 2: the samples ──────────────────────────────────────────────── */
  const samples = [['#', ...activeColumns()].map(K)];
  [...document.querySelectorAll('#samples tbody tr')].forEach((tr, i) => {
    if (!rowHasData(tr)) return;                // never export empty rows
    samples.push([i + 1, ...[...tr.querySelectorAll('input,select')].map(el => el.value.trim())]);
  });

  const sheets = [
    { name: 'Submission', rows: submission, cols: [34, 62] },
    { name: 'Samples', rows: samples,
      cols: [5, ...activeColumns().map(c => c === 'Remarks' ? 34 : 16)] },
  ];

  /* ── sheet 3: analysis, only when there is any ─────────────────────────── */
  const panel = document.querySelectorAll('#analysis-panel textarea');
  if (panel.length) {
    const analysis = [
      ['', T('Bioinformatics analysis')],
      ['', N('A consultation meeting with Liat Linde or Nitsan Fourier is ' +
             'required before analysis begins.')],
      [],
      [H('Requested'), H('')],
    ];
    panel.forEach(t => analysis.push(
      [L(labelText(t.closest('label')).replace('*', '').trim()), t.value.trim()]));
    sheets.push({ name: 'Analysis', rows: analysis, cols: [40, 76] });
  }

  if (state.warnings.length) {
    sheets.push({ name: 'Warnings', cols: [100],
                  rows: [[T('Warnings')],
                         [N('Flagged, but did not stop the submission.')], [],
                         ...state.warnings.map(w => [w])] });
  }
  return sheets;
}

/* The application leads, so a folder of these sorts by service; the date and
 * the id follow, and the id is what staff quote back when chasing one. */
function fileName() {
  const date = $('#f-date').value || new Date().toISOString().slice(0, 10);
  return `${APP.slug}_submission_form_${date}_${state.id}.xlsx`;
}

const ACCENT = getComputedStyle(document.documentElement)
  .getPropertyValue('--accent').trim() || '#1da5ff';

function download() {
  const blob = XLSX.build(collect(), { accent: ACCENT, logo: window.ATGC_LOGO });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = fileName();
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);

  /* The draft has done its job once the file exists. */
  try { localStorage.removeItem(KEY); } catch (e) {}
  /* Name the recipients again here. This message is the last thing a
   * researcher reads, and "attach it to the email" leaves them scrolling back
   * up to find out which email. */
  const r = (APP.routing || []).find(x => x.lab === $('#f-lab').value);
  const who = r ? [...(r.to || []), ...(r.cc || [])].join(' and ') : '';
  const note = $('#table-report');
  note.hidden = false; note.className = 'msg ok';
  note.textContent = `Saved ${fileName()}` +
    (who ? ` — now email it as an attachment to ${who}.`
         : ' — now email it to us as an attachment.');
}

$('#export-xlsx').addEventListener('click', download);


/* ── the sample table, offline ─────────────────────────────────────────────
 * The primary route for anything past a plate: take a blank table away, fill
 * it in Excel where filling tables is pleasant, bring it back.
 */

/* Old workbook spellings, so a table built from a form someone already had on
 * disk still imports (doc 05 §16.1). */
const COLUMN_ALIASES = {
  'quant. method': 'Quantified by',
  'quant. method ': 'Quantified by',
  'quant.method': 'Quantified by',
  'ng/ul method': 'Quantified by',
  'quantification method': 'Quantified by',
  'experimental group*': 'Experimental group',
  'experiment group': 'Experimental group',
  '# cells / tissue weight': '# cells / tissue weight [mg]',
  'remarks*': 'Remarks',
  'sample id': null,          // dropped — the row number is the sample number
  '#': null,
  'species': 'Organism',      // renamed 2026-08-13; old tables still import
};

const norm = s => String(s == null ? '' : s).trim().replace(/\s+/g, ' ');

function canonicalColumn(name) {
  const key = norm(name).toLowerCase();
  if (key in COLUMN_ALIASES) return COLUMN_ALIASES[key];
  const hit = activeColumns().find(c => c.toLowerCase() === key);
  return hit || norm(name);
}

function downloadTemplate() {
  const cols = activeColumns();
  const rows = [cols.map(c => ({ v: c, s: 'head' }))];
  // A few blank rows so the file opens looking like a table, not a lone header.
  for (let i = 0; i < 24; i++) rows.push(cols.map(() => ''));
  const blob = XLSX.build(
    [{ name: 'Samples', rows,
       cols: cols.map(c => c === 'Remarks' ? 34 : 16) }],
    { accent: ACCENT });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${APP.slug}_sample_table_template.xlsx`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function uploadTable(file) {
  const note = $('#table-report');
  const say = (cls, html) => { note.hidden = false; note.className = 'msg ' + cls;
                               note.innerHTML = html; };
  let rows;
  try {
    rows = await XLSXRead.read(file);
  } catch (err) {
    say('err', err.message === 'NO_INFLATE'
      ? 'This browser cannot read .xlsx files. Save the table as CSV and upload that instead.'
      : `Could not read that file: ${err.message}. It should be the table you ` +
        'downloaded, as .xlsx or .csv.');
    return;
  }

  rows = rows.filter(r => r.some(v => norm(v) !== ''));
  if (!rows.length) { say('err', 'That file has no rows in it.'); return; }

  /* Match by HEADER NAME, never by position, so a reordered or extra column
   * still lands in the right place. */
  const header = rows[0].map(canonicalColumn);
  const matched = [], ignored = [];
  header.forEach((h, i) => {
    if (h === null) return;                       // deliberately dropped
    if (activeColumns().includes(h)) matched.push({ from: i, col: h });
    else if (norm(rows[0][i])) ignored.push(norm(rows[0][i]));
  });

  if (!matched.length) {
    say('err', 'None of the column headings in that file match this form. ' +
        'Expected: ' + activeColumns().join(', ') + '.<br>Found: ' +
        rows[0].map(norm).filter(Boolean).join(', ') + '.');
    return;
  }

  const body = rows.slice(1);
  const filled = [...document.querySelectorAll('#samples tbody tr')].filter(rowHasData).length;
  if (filled && !confirm(
        `${filled} row(s) already have data. Replace them with ${body.length} ` +
        'row(s) from the file?')) return;

  setRows(Math.max(1, Math.min(MAX_ROWS, body.length)));
  const trs = [...document.querySelectorAll('#samples tbody tr')];
  let unknownQuant = 0;
  body.slice(0, trs.length).forEach((r, i) => {
    matched.forEach(m => {
      const cell = trs[i].querySelector(`[data-col="${m.col}"]`);
      if (!cell) return;
      const v = norm(r[m.from]);
      if (cell.tagName === 'SELECT') {
        // A dropdown cannot hold a value it does not offer; report rather than
        // silently blanking it.
        const ok = [...cell.options].some(o => o.value.toLowerCase() === v.toLowerCase());
        if (v && !ok) { unknownQuant++; return; }
        cell.value = [...cell.options].find(o => o.value.toLowerCase() === v.toLowerCase())?.value || '';
      } else {
        cell.value = v;
      }
    });
  });

  const bits = [`Read <strong>${body.length}</strong> row(s); matched ` +
                `<strong>${matched.length}</strong> column(s).`];
  if (body.length > trs.length)
    bits.push(`Only the first ${trs.length} fitted — the limit is ${MAX_ROWS}.`);
  if (ignored.length)
    bits.push(`Ignored column(s) this form does not use: ${ignored.join(', ')}.`);
  if (unknownQuant)
    bits.push(`${unknownQuant} cell(s) had a value not offered by its dropdown ` +
              'and were left blank.');
  const missing = activeColumns().filter(c => !matched.some(m => m.col === c));
  if (missing.length) bits.push(`No column in the file for: ${missing.join(', ')}.`);

  say(ignored.length || unknownQuant || missing.length ? 'warn' : 'ok', bits.join('<br>'));
  validate(); saveDraft();
}

$('#dl-template').addEventListener('click', downloadTemplate);
$('#up-template').addEventListener('change', e => {
  if (e.target.files && e.target.files[0]) uploadTable(e.target.files[0]);
  e.target.value = '';        // so the same file can be re-uploaded after a fix
});


/* ── the quote ─────────────────────────────────────────────────────────────
 * A convenience, never a step (D8). Nothing here can block export, and the
 * contact fields are never touched: the person filling the form is usually a
 * student, not the PI named on the quote.
 */

async function importQuote(file) {
  const box = $('#quote-msg');
  const say = (cls, html) => { box.hidden = false; box.className = 'msg ' + cls;
                               box.innerHTML = html; };
  const KEEP = ' A quote is not required — you can continue without one.';

  let res;
  try {
    res = await QuotePDF.read(file);
  } catch (e) {
    say('warn', 'Could not read that file.' + KEEP);
    return;
  }

  if (res.status === 'not-pdf') {
    say('warn', 'Please upload the quote as a PDF. Other file types cannot be read.' + KEEP);
    return;
  }
  if (res.status === 'encrypted') {
    say('warn', 'This PDF is password-protected and cannot be read. ' +
                'Please upload an unprotected copy.' + KEEP);
    return;
  }
  if (res.status === 'scanned') {
    say('warn', 'This looks like a scan or photo of a quote. Please upload the ' +
                'original PDF as it was issued by ATGC.' + KEEP);
    return;
  }
  if (res.status === 'no-payload') {
    say('warn', 'This quote was issued before we started including its details ' +
                'in the file, so nothing could be filled in automatically. ' +
                'Please type the quote number above.' + KEEP);
    return;
  }

  /* ── a stamped quote: fill the services, never the contact details ─────── */
  const q = res.payload;
  const filled = [], unmatched = [];

  if (q.quote_number) { $('#f-quote').value = q.quote_number; filled.push('quote number'); }

  /* The payload lists the services as they were QUOTED. Match each against the
   * dropdowns on this form — by catalog name where we have one, since that is
   * the name the quote uses (D6) — and fill what fits. */
  const matchService = (desc) => {
    const want = desc.trim().toLowerCase();
    for (const [id, key] of [['libprep', 'LibraryPrep'], ['flowcell', 'FlowCell'],
                             ['extraction', 'ExtractionService']]) {
      const el = $('#c-' + id);
      const vocab = (APP.vocabularies || {})[key] || [];
      if (!el) continue;
      const hit = vocab.find(o => {
        const label = typeof o === 'string' ? o : o.label;
        const cat = (typeof o === 'object' && o.catalog) || label;
        return label.toLowerCase() === want || cat.toLowerCase() === want;
      });
      if (hit) return { el, id, value: typeof hit === 'string' ? hit : hit.label };
    }
    return null;
  };

  (q.services || []).forEach(svc => {
    const m = matchService(svc.description || '');
    if (!m) { unmatched.push(svc.description); return; }
    m.el.value = m.value;
    m.el.dispatchEvent(new Event('change', { bubbles: true }));  // run mode follows
    filled.push(m.value);
    /* Extraction is behind a Yes/No, so answering the second question without
     * the first would leave a hidden field holding a value. */
    if (m.id === 'extraction' && $('#c-needext')) {
      $('#c-needext').value = 'Yes';
      $('#c-needext').dispatchEvent(new Event('change', { bubbles: true }));
    }
  });

  /* Warnings only — every one of these is for staff to resolve, and none is a
   * reason to stop someone submitting samples (D8). */
  const warn = [];
  if (q.expires && new Date(q.expires) < new Date())
    warn.push(`This quote expired on ${q.expires}.`);
  if (unmatched.length && !filled.some(f => f !== 'quote number'))
    warn.push('Nothing on this quote matches the ' + APP.name +
              ' form — check you are on the right form.');
  const n = [...document.querySelectorAll('#samples tbody tr')].filter(rowHasData).length;
  const qty = (q.services || []).reduce((m, s) => Math.max(m, s.quantity || 0), 0);
  if (qty && n > qty)
    warn.push(`You have ${n} samples but the quote covers ${qty}.`);

  state.warnings = warn.slice();
  const bits = [];
  if (filled.length) bits.push(`Filled in: ${filled.join(', ')}.`);
  if (unmatched.length)
    bits.push(`Also on the quote, but not a field on this form: ${unmatched.join('; ')}.`);
  bits.push('Contact details are never filled from a quote — please enter your own.');
  warn.forEach(w => bits.push('&#9888; ' + w));

  say(warn.length ? 'warn' : 'ok', bits.join('<br>'));
  validate(); saveDraft();
}

$('#quote-pdf').addEventListener('change', e => {
  if (e.target.files && e.target.files[0]) importQuote(e.target.files[0]);
  e.target.value = '';
});

/* The sample count can drift past the quoted quantity after the import, so
 * re-check it whenever the table changes. */
function recheckQuoteQuantity() {
  state.warnings = state.warnings.filter(w => !/but the quote covers/.test(w));
}


/* ── help ──────────────────────────────────────────────────────────────────
 * Written for someone sending samples for the first time. It answers the
 * questions people actually ask — what happens to my samples, why can I not
 * press the button, do I need a quote — rather than describing the fields,
 * which are already labelled.
 */
function helpHtml() {
  return `
  <button type="button" class="help-close" id="help-close" aria-label="Close">&times;</button>
  <h2>Completing the ${APP.name} submission form</h2>

  <p class="help-lead">This form is not submitted online. Once completed, it is
  exported as an Excel file which you attach to an email to ATGC. Your entries
  remain in your browser until then, so the form may be closed and resumed.</p>

  <h3>Procedure</h3>
  <ol>
    <li>Complete your contact details and the sequencing requirements.</li>
    <li>Enter your samples (see <em>Large sample sets</em> below).</li>
    <li>Confirm the declaration at the foot of the form.</li>
    <li>Select <strong>Download (.xlsx)</strong>.</li>
    <li>Attach the downloaded file to an email addressed to the recipients
        shown under <em>Where to send the completed form</em>.</li>
  </ol>
  <p class="help-note">Please send the .xlsx file as an attachment. The table
  cannot be read if it is pasted into the body of the message.</p>

  <h3>Using your quote</h3>
  <p>A quote is <strong>not required</strong>; samples may be submitted without
  one.</p>
  <p>If a quote has been issued, please keep it to hand while completing this
  form. Most of the information requested here &mdash; library preparation, flow
  cell, sample numbers &mdash; was agreed when the quote was prepared, and the
  service names used on this form are identical to those on the quote.</p>
  <p>Uploading the quote completes those fields automatically. Contact details
  are never taken from a quote, and an unrecognised or expired quote does not
  prevent submission.</p>

  <h3>Large sample sets</h3>
  <p>Samples need not be entered individually. Either:</p>
  <ul>
    <li>select <strong>Download a blank table</strong>, complete it in Excel and
        return it using <strong>Upload a filled table</strong>; or</li>
    <li>paste the cells directly from your own spreadsheet into the first cell
        of the table.</li>
  </ul>
  <p>Uploaded columns are matched by their headings rather than their position,
  so column order is immaterial and additional columns are ignored. A summary of
  what was read is displayed after upload.</p>

  <h3>If the download button is unavailable</h3>
  <p>Required information is outstanding. The panel immediately above the
  buttons lists each item by name. The button becomes available once these are
  complete.</p>

  <h3>Bioinformatic analysis</h3>
  <p>The final section is optional. Selecting <em>No</em> completes the form;
  sample submission does not require a consultation. Selecting <em>Yes</em>
  requests details of the intended analysis, and a consultation meeting is
  arranged before any analysis begins.</p>

  <h3>Sample delivery</h3>
  <p>The delivery address and laboratory telephone number are shown under
  <em>Shipping address</em> at the foot of this form, for whichever laboratory
  is selected above.</p>

  <h3>Assistance</h3>
  <p>Please contact us if anything is unclear. The addresses are listed under
  <em>Where to send the completed form</em>, and depend on the laboratory
  selected above.</p>`;
}

function toggleHelp(show) {
  const box = $('#help');
  if (show) {
    box.innerHTML = helpHtml();
    box.hidden = false;
    $('#help-close').addEventListener('click', () => toggleHelp(false));
    box.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } else {
    box.hidden = true;
    $('#help-open').focus();
  }
}

$('#help-open').addEventListener('click', () => toggleHelp($('#help').hidden));
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !$('#help').hidden) toggleHelp(false);
});

/* ── wire up ───────────────────────────────────────────────────────────── */
renderHeader();
renderChoices();
renderQcPanel();
renderSamples();
renderBioinformatics();
dropEmptySections();
offerRestore();

$('#row-count').addEventListener('change', e => {
  const n = Math.max(1, Math.min(MAX_ROWS, parseInt(e.target.value, 10) || 1));
  setRows(n); validate();
});
document.addEventListener('input', () => { saveDraft(); });
document.addEventListener('change', () => {
  validate(); renderSendTo(); renderShipping(); saveDraft();
});
state.id = submissionId();
validate();
renderSendTo();
renderShipping();
