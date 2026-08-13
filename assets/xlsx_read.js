/* Reading a .xlsx (and .csv/.tsv) in the browser, with no dependencies.
 *
 * Writing a ZIP is easy; reading one needs inflate, because Excel compresses
 * its parts. Rather than ship a deflate implementation we use the platform's
 * own DecompressionStream('deflate-raw'). Where that is missing the reader says
 * so and points at CSV, instead of failing with something unhelpful.
 *
 * Only what we need is parsed: the first worksheet, plus the shared-string
 * table it refers to.
 */
'use strict';

(function (global) {

  const dec = new TextDecoder();

  /* ── ZIP ───────────────────────────────────────────────────────────────── */
  async function unzip(buf) {
    const view = new DataView(buf);
    const bytes = new Uint8Array(buf);

    // Find the end-of-central-directory record, scanning back from the tail.
    let eocd = -1;
    for (let i = bytes.length - 22; i >= 0 && i > bytes.length - 66000; i--) {
      if (view.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('not a zip');

    const count = view.getUint16(eocd + 10, true);
    let p = view.getUint32(eocd + 16, true);
    const out = {};

    for (let n = 0; n < count; n++) {
      if (view.getUint32(p, true) !== 0x02014b50) break;
      const method = view.getUint16(p + 10, true);
      const size = view.getUint32(p + 20, true);
      const nameLen = view.getUint16(p + 28, true);
      const extraLen = view.getUint16(p + 30, true);
      const commentLen = view.getUint16(p + 32, true);
      const local = view.getUint32(p + 42, true);
      const name = dec.decode(bytes.subarray(p + 46, p + 46 + nameLen));

      // The local header repeats the name and extra fields, and its extra
      // length often differs from the central one — read it, do not assume.
      const lNameLen = view.getUint16(local + 26, true);
      const lExtraLen = view.getUint16(local + 28, true);
      const start = local + 30 + lNameLen + lExtraLen;
      const raw = bytes.subarray(start, start + size);

      out[name] = method === 0 ? raw : await inflate(raw);
      p += 46 + nameLen + extraLen + commentLen;
    }
    return out;
  }

  async function inflate(raw) {
    if (typeof DecompressionStream !== 'function') {
      throw new Error('NO_INFLATE');
    }
    const stream = new Blob([raw]).stream()
      .pipeThrough(new DecompressionStream('deflate-raw'));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }

  /* ── worksheet ─────────────────────────────────────────────────────────── */
  function colIndex(ref) {
    let n = 0;
    for (const ch of ref) {
      if (ch < 'A' || ch > 'Z') break;
      n = n * 26 + (ch.charCodeAt(0) - 64);
    }
    return n - 1;
  }

  function parseSheet(xml, shared) {
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    const rows = [];
    for (const row of doc.getElementsByTagName('row')) {
      const cells = [];
      for (const c of row.getElementsByTagName('c')) {
        const ref = c.getAttribute('r') || '';
        const i = ref ? colIndex(ref) : cells.length;
        const type = c.getAttribute('t');
        let v = '';
        if (type === 'inlineStr') {
          const t = c.getElementsByTagName('t')[0];
          v = t ? t.textContent : '';
        } else {
          const node = c.getElementsByTagName('v')[0];
          const text = node ? node.textContent : '';
          v = type === 's' ? (shared[+text] || '') : tidyNumber(text);
        }
        cells[i] = v;
      }
      for (let i = 0; i < cells.length; i++) if (cells[i] == null) cells[i] = '';
      rows.push(cells);
    }
    return rows;
  }

  /* Spreadsheets store numbers as binary floats, so a cell showing 8.8 can be
   * written as 8.800000000000001. Excel hides that; we would paste it straight
   * into a form field. Trim the noise, but only when the shortened form is
   * genuinely the same number. */
  function tidyNumber(text) {
    if (!/^-?\d*\.\d{12,}$/.test(text)) return text;
    const short = String(Number(Number(text).toPrecision(12)));
    return Number(short) === Number(text) ? short : text;
  }

  function parseShared(xml) {
    if (!xml) return [];
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    return [...doc.getElementsByTagName('si')].map(si =>
      [...si.getElementsByTagName('t')].map(t => t.textContent).join(''));
  }

  /* ── delimited text ────────────────────────────────────────────────────── */
  function parseDelimited(text) {
    // Excel writes a BOM; a stray one becomes part of the first header name and
    // then that column silently fails to match.
    if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
    const delim = (text.split('\n')[0].split('\t').length >
                   text.split('\n')[0].split(',').length) ? '\t' : ',';
    const rows = [];
    let row = [], field = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (ch === '"') quoted = false;
        else field += ch;
        continue;
      }
      if (ch === '"') { quoted = true; continue; }
      if (ch === delim) { row.push(field); field = ''; continue; }
      if (ch === '\r') continue;
      if (ch === '\n') { row.push(field); rows.push(row); row = []; field = ''; continue; }
      field += ch;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    return rows;
  }

  /**
   * read(File) -> Promise<string[][]>
   * Rows of strings, first row being whatever headers the file has.
   */
  async function read(file) {
    const name = (file.name || '').toLowerCase();
    if (name.endsWith('.csv') || name.endsWith('.tsv') || name.endsWith('.txt')) {
      return parseDelimited(await file.text());
    }
    const parts = await unzip(await file.arrayBuffer());
    const sheetName = Object.keys(parts)
      .filter(n => /^xl\/worksheets\/sheet\d+\.xml$/.test(n))
      .sort()[0];
    if (!sheetName) throw new Error('no worksheet in that file');
    const shared = parseShared(parts['xl/sharedStrings.xml']
      ? dec.decode(parts['xl/sharedStrings.xml']) : '');
    return parseSheet(dec.decode(parts[sheetName]), shared);
  }

  global.XLSXRead = { read };

})(window);
