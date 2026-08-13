/* A minimal .xlsx writer, in the browser, with no dependencies.
 *
 * Why not a library: this page must work offline and fetch nothing at runtime.
 * A CDN script that fails to load would take the export with it — and export is
 * the whole point of the form. Fonts failing is cosmetic; this would not be.
 *
 * An .xlsx is a ZIP of XML parts. We write the ZIP with STORE (no compression):
 * a submission is a few hundred rows of text, so the saving is irrelevant and
 * store-only avoids shipping a deflate implementation. Excel, LibreOffice and
 * Google Sheets all open it.
 *
 * Strings are written inline (t="inlineStr") rather than through a shared-string
 * table — fewer parts, and no index to keep consistent.
 */
'use strict';

(function (global) {

  /* ── CRC32, needed by the ZIP local header ───────────────────────────── */
  const CRC_TABLE = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();

  function crc32(bytes) {
    let c = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  const enc = new TextEncoder();

  /* ── ZIP (store only) ─────────────────────────────────────────────────── */
  function zip(files) {
    const parts = [], central = [];
    let offset = 0;

    for (const f of files) {
      const name = enc.encode(f.name);
      // An image part arrives as bytes; every XML part arrives as a string.
      const data = f.data instanceof Uint8Array ? f.data : enc.encode(f.data);
      const sum = crc32(data);

      const local = new DataView(new ArrayBuffer(30));
      local.setUint32(0, 0x04034b50, true);
      local.setUint16(4, 20, true);          // version needed
      local.setUint16(6, 0, true);           // flags
      local.setUint16(8, 0, true);           // method 0 = store
      local.setUint16(10, 0, true);          // time
      local.setUint16(12, 0x21, true);       // date (1980-01-01, deterministic)
      local.setUint32(14, sum, true);
      local.setUint32(18, data.length, true);
      local.setUint32(22, data.length, true);
      local.setUint16(26, name.length, true);
      local.setUint16(28, 0, true);
      parts.push(new Uint8Array(local.buffer), name, data);

      const cd = new DataView(new ArrayBuffer(46));
      cd.setUint32(0, 0x02014b50, true);
      cd.setUint16(4, 20, true);
      cd.setUint16(6, 20, true);
      cd.setUint16(8, 0, true);
      cd.setUint16(10, 0, true);
      cd.setUint16(12, 0, true);
      cd.setUint16(14, 0x21, true);
      cd.setUint32(16, sum, true);
      cd.setUint32(20, data.length, true);
      cd.setUint32(24, data.length, true);
      cd.setUint16(28, name.length, true);
      cd.setUint32(42, offset, true);
      central.push(new Uint8Array(cd.buffer), name);

      offset += 30 + name.length + data.length;
    }

    const centralSize = central.reduce((n, a) => n + a.length, 0);
    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true);
    end.setUint16(8, files.length, true);
    end.setUint16(10, files.length, true);
    end.setUint32(12, centralSize, true);
    end.setUint32(16, offset, true);

    const blobParts = [...parts, ...central, new Uint8Array(end.buffer)];
    return new Blob(blobParts, {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    });
  }

  /* ── XML ──────────────────────────────────────────────────────────────── */
  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    // Excel rejects most control characters outright.
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '');

  function colName(n) {
    let s = '';
    while (n >= 0) { s = String.fromCharCode(65 + (n % 26)) + s; n = Math.floor(n / 26) - 1; }
    return s;
  }

  /* Style indices, matching the order of <cellXfs> below. A cell is either a
   * bare value or {v, s} where s is one of these names. */
  const S = { plain: 0, title: 1, section: 2, label: 3, head: 4, sub: 5 };

  function sheetXml(rows, cols, withDrawing) {
    const widths = cols && cols.length
      ? '<cols>' + cols.map((w, i) =>
          `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join('') + '</cols>'
      : '';
    const body = rows.map((row, r) => {
      const cells = row.map((cell, c) => {
        const v = (cell && typeof cell === 'object') ? cell.v : cell;
        const style = (cell && typeof cell === 'object') ? (S[cell.s] || 0) : 0;
        const ref = colName(c) + (r + 1);
        // An empty cell still needs emitting when it carries a style, or a
        // section band would colour column A and stop dead at column B.
        if (v === '' || v == null) {
          return style ? `<c r="${ref}" s="${style}"/>` : '';
        }
        // A bare number stays a number so Excel can sum it; everything else,
        // including anything with a leading zero, stays text.
        const numeric = typeof v === 'number' ||
          (typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v) && !/^0\d/.test(v));
        return numeric
          ? `<c r="${ref}" s="${style}"><v>${esc(v)}</v></c>`
          : `<c r="${ref}" t="inlineStr" s="${style}"><is><t xml:space="preserve">${esc(v)}</t></is></c>`;
      }).join('');
      const tall = row.some(x => x && typeof x === 'object' && x.s === 'title');
      return `<row r="${r + 1}"${tall ? ' ht="26" customHeight="1"' : ''}>${cells}</row>`;
    }).join('');
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
${widths}<sheetData>${body}</sheetData>${withDrawing ? '<drawing r:id="rId1"/>' : ''}</worksheet>`;
  }

  /**
   * build([{name, rows, cols}], {accent}) -> Blob
   * rows is an array of arrays. A cell is a string, a number, or {v, s} where
   * s names a style: title | section | label | head | sub.
   * cols is an optional array of column widths.
   */
  /* base64 -> bytes, for the embedded logo. */
  function unb64(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  const PX = 9525;         // EMU per pixel at 96 dpi

  function build(sheets, opts) {
    opts = opts || {};
    const logo = opts.logo;          // {w, h, b64}
    const files = [];

    files.push({
      name: '[Content_Types].xml',
      data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
${logo ? '<Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>' : ''}
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
${sheets.map((s, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('\n')}
</Types>`
    });

    files.push({
      name: '_rels/.rels',
      data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`
    });

    files.push({
      name: 'xl/workbook.xml',
      data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>${sheets.map((s, i) =>
        `<sheet name="${esc(s.name).slice(0, 31)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('')}</sheets>
</workbook>`
    });

    files.push({
      name: 'xl/_rels/workbook.xml.rels',
      data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
${sheets.map((s, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('\n')}
<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`
    });

    /* The same palette the page uses (assets/tokens.css), so an exported file
     * looks like the form it came from rather than a raw dump. `accent` is the
     * application's section colour, passed in by form.js. */
    const accent = (opts.accent || '1DA5FF').replace('#', '').toUpperCase();
    const NAVY = '112954';

    files.push({
      name: 'xl/styles.xml',
      data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="6">
  <font><sz val="11"/><name val="Calibri"/><color rgb="FF262626"/></font>
  <font><sz val="18"/><b/><name val="Calibri"/><color rgb="FF${NAVY}"/></font>
  <font><sz val="11"/><b/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
  <font><sz val="11"/><b/><name val="Calibri"/><color rgb="FF${NAVY}"/></font>
  <font><sz val="11"/><b/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
  <font><sz val="10"/><i/><name val="Calibri"/><color rgb="FF5F7488"/></font>
</fonts>
<fills count="4">
  <fill><patternFill patternType="none"/></fill>
  <fill><patternFill patternType="gray125"/></fill>
  <fill><patternFill patternType="solid"><fgColor rgb="FF${accent}"/><bgColor indexed="64"/></patternFill></fill>
  <fill><patternFill patternType="solid"><fgColor rgb="FF${NAVY}"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
  <border/>
  <border><bottom style="thin"><color rgb="FFE3EBF2"/></bottom></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="6">
  <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
  <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
  <xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
  <xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
  <xf numFmtId="0" fontId="4" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
  <xf numFmtId="0" fontId="5" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
</cellXfs>
</styleSheet>`
    });

    /* The logo sits on the first sheet only, anchored top-left and floating
     * over the cells, so it never shifts a value out of place. */
    if (logo) {
      /* Keep the picture inside column A. Excel's column width is in
       * characters, so px = width * 7 + 5; leave a margin so the logo never
       * spills into the value column. */
      const colA = (sheets[0] && sheets[0].cols && sheets[0].cols[0]) || 34;
      const maxW = Math.max(60, colA * 7 + 5 - 24);
      const scale = Math.min(1, maxW / logo.w);
      const lw = Math.round(logo.w * scale), lh = Math.round(logo.h * scale);

      files.push({ name: 'xl/media/image1.png', data: unb64(logo.b64) });
      files.push({
        name: 'xl/drawings/drawing1.xml',
        data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<xdr:oneCellAnchor>
<xdr:from><xdr:col>0</xdr:col><xdr:colOff>36000</xdr:colOff><xdr:row>0</xdr:row><xdr:rowOff>36000</xdr:rowOff></xdr:from>
<xdr:ext cx="${lw * PX}" cy="${lh * PX}"/>
<xdr:pic>
<xdr:nvPicPr><xdr:cNvPr id="1" name="ATGC"/><xdr:cNvPicPr/></xdr:nvPicPr>
<xdr:blipFill><a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>
<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${lw * PX}" cy="${lh * PX}"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>
</xdr:pic>
<xdr:clientData/>
</xdr:oneCellAnchor>
</xdr:wsDr>`
      });
      files.push({
        name: 'xl/drawings/_rels/drawing1.xml.rels',
        data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>`
      });
      files.push({
        name: 'xl/worksheets/_rels/sheet1.xml.rels',
        data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>
</Relationships>`
      });
    }

    sheets.forEach((s, i) => {
      files.push({ name: `xl/worksheets/sheet${i + 1}.xml`,
                   data: sheetXml(s.rows, s.cols, i === 0 && logo) });
    });

    return zip(files);
  }

  global.XLSX = { build };

})(window);
