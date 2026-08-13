/* Reading an ATGC quote PDF, in the browser.
 *
 * WHAT THIS DOES NOT DO: parse the printed page. That was measured, not
 * assumed — see docs/05 §19. Quotes are printed from an RTL sheet, so plain
 * text extraction returns the number reversed and run together
 * ("-15331022026" for quote 1022026-1533). Across 30 real quotes a careful
 * regex recovered 14 correctly and got one WRONG, reading 2912026-115 as
 * 912026-1152. A silently wrong quote number is worse than an empty box, so
 * that route is deliberately not taken. The positional parser that does work
 * (atgc/quotepdf.py) needs x/y coordinates for every glyph, which means
 * reimplementing positional PDF extraction here — disproportionate for a
 * shrinking set of legacy files.
 *
 * WHAT THIS DOES: read a payload that QuoteDesk stamps into the PDFs it
 * generates, as a plain comment line in the file. A PDF comment is ignored by
 * every reader, survives copying and emailing, and needs no PDF parsing at all
 * to find — just a byte scan. Exact data, no heuristics.
 *
 * Quotes issued before QuoteDesk stamps them have no payload; for those the
 * researcher types the number, which is what they do today.
 */
'use strict';

(function (global) {

  const MARKER = '%%ATGC-QUOTE-V1 ';

  /** Find the stamped payload in a PDF's raw bytes. Returns null if absent. */
  function findPayload(bytes) {
    const text = new TextDecoder('latin1').decode(bytes);
    const at = text.lastIndexOf(MARKER);
    if (at < 0) return null;
    const end = text.indexOf('\n', at);
    const line = text.slice(at + MARKER.length, end < 0 ? undefined : end).trim();
    try {
      // The payload is written as base64 so it can never contain a byte that
      // upsets a PDF reader, and never wraps onto a second line.
      return JSON.parse(new TextDecoder().decode(
        Uint8Array.from(atob(line), c => c.charCodeAt(0))));
    } catch (e) {
      return null;
    }
  }

  /** Is this actually a PDF? Checked on the bytes, not the file extension. */
  function isPdf(bytes) {
    return bytes.length > 4 && bytes[0] === 0x25 && bytes[1] === 0x50 &&
           bytes[2] === 0x44 && bytes[3] === 0x46;          // %PDF
  }

  function isEncrypted(bytes) {
    return new TextDecoder('latin1').decode(bytes).includes('/Encrypt');
  }

  /** Does the file contain any extractable text at all, or is it a scan? */
  function looksScanned(bytes) {
    const text = new TextDecoder('latin1').decode(bytes);
    return !/\/Font/.test(text);
  }

  /**
   * read(File) -> {status, payload?, reason?}
   * status: 'payload' | 'no-payload' | 'not-pdf' | 'encrypted' | 'scanned'
   */
  async function read(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (!isPdf(bytes)) return { status: 'not-pdf' };
    if (isEncrypted(bytes)) return { status: 'encrypted' };

    const payload = findPayload(bytes);
    if (payload) return { status: 'payload', payload };

    return { status: looksScanned(bytes) ? 'scanned' : 'no-payload' };
  }

  global.QuotePDF = { read, MARKER };

})(window);
