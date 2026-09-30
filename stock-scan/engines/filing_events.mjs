#!/usr/bin/env node
// I5-DD leg 2a: collect 8-K / 8-K/A / 6-K filings WITH their exhibits, reduced to candidate
// WINDOWS for the two-pass veto (veto_extract.mjs). Deterministic, no LLM.
//
// Why this exists: dd_filings.mjs regexes only the PRIMARY document of the 12 newest filings.
// The real terms of a dilution event sit in exhibits (ATM sales agreement EX-1.1, purchase
// agreement EX-10.x, notes and warrants EX-4.x, press release EX-99.1), amendments (8-K/A)
// carry their own Items, and a busy issuer can push the event past a 12-filing cap.
// GME (55.5M shares by note exchange) and RWT ($185M convertible) both slipped a form-name
// filter for exactly these reasons (2026-09-22).
//
// Rules this module keeps (KB trap #14 / #9-11): it NAMES everything it discards, never
// prints a bare count; a filing it cannot fetch is a `drop` with a reason, never silence;
// a truncated filing list is reported as truncated. The caller must treat any drop as
// "unknown", not "clear".
const UA = { "User-Agent": "stock-scan research jivtuban14@gmail.com" };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// EDGAR allows 10 req/s; stay well under it.
const GAP_MS = 150;

export async function secGet(url, { json = false, retries = 2 } = {}) {
  let last;
  for (let a = 0; a <= retries; a++) {
    try {
      await sleep(GAP_MS);
      const r = await fetch(url, { headers: UA });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return json ? await r.json() : await r.text();
    } catch (e) {
      last = e;
      await sleep(400 * (a + 1));
    }
  }
  throw new Error(`${url}: ${last?.message}`);
}

// Document types worth reading. EX-5 (legal opinion) and EX-101 (XBRL) carry no terms; the
// 8-K main document is always kept.
const KEEP_TYPE = /^(8-K|8-K\/A|6-K|EX-(1|2|4|10|99)(\.|$))/i;

// Trigger vocabulary. It only decides WHICH passages the model reads, so it is deliberately
// broad: a missed passage is a missed veto, a spurious one just costs tokens.
const TRIGGERS = {
  dilution:
    /convertible|conversion price|at[- ]the[- ]market|sales agreement|equity distribution|purchase agreement|registered direct|private placement|public offering|underwritten|pre-funded|warrants?\b|exchange agreement|exchange[ds]? .{0,60}(notes|debentures)|equity line|standby equity|\bPIPE\b|issu(e|ed|ance|ing) .{0,40}shares|reverse (stock )?split/gi,
  distress:
    /going concern|substantial doubt|non-reliance|no longer be relied|restate|material weakness|delist|minimum bid|stockholders.? equity requirement|event of default|acceleration|forbearance|cease.and.desist|subpoena|wells notice/gi,
  governance:
    /resign|termination of employment|cyber|unauthorized access|ransomware|dismiss.{0,30}(auditor|accountant)|engage.{0,40}accounting firm/gi,
};
// Language that can only mean new equity or a path to it. A dropped excerpt matching this is a
// real coverage hole; one that only matches distress words (credit-agreement "event of
// default") is boilerplate. Used to decide whether a cap may raise `unknown`.
export const STRONG_DILUTION =
  /convertible|conversion price|at[- ]the[- ]market|equity distribution|registered direct|private placement|pre-funded|\bwarrants?\b|equity line|standby equity|\bPIPE\b|issu(e|ed|ance|ing) .{0,40}shares|exchange[ds]? .{0,60}(notes|debentures)|reverse (stock )?split|shares of (common|class [a-z] common) stock/i;
const AMOUNT = /\$\s?\d[\d,.]*\s?(million|billion|m\b|bn\b)?|\b\d{1,3}(,\d{3}){2,}\s+shares/i;

export function htmlToText(s) {
  return String(s)
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;|&#160;|&#xa0;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&#8217;|&#x2019;|&rsquo;/gi, "'")
    .replace(/&#8220;|&#8221;|&ldquo;|&rdquo;/gi, '"')
    .replace(/&#8211;|&#8212;|&ndash;|&mdash;/gi, "-")
    .replace(/&#?\w+;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Split a full-submission .txt into its <DOCUMENT>s: [{ type, text }].
export function splitSubmission(txt) {
  const docs = [];
  const re = /<DOCUMENT>([\s\S]*?)<\/DOCUMENT>/gi;
  let m;
  while ((m = re.exec(txt))) {
    const body = m[1];
    const type = (body.match(/<TYPE>([^\n\r<]+)/i) || [])[1]?.trim() || "";
    const text = (body.match(/<TEXT>([\s\S]*?)(<\/TEXT>|$)/i) || [, body])[1];
    docs.push({ type, text });
  }
  return docs;
}

// Filings in the window from a submissions JSON. Reports when the `recent` page does not
// reach back to the cutoff (older rows live in filings.files and would be silently missed).
// `now` is also an UPPER bound: a replay "as of" a past date must not read filings made after it,
// or the veto would see the future (the look-ahead that made the first n=39 result too good).
export function listFilings(sub, { now = Date.now(), days = 90 } = {}) {
  const R = sub.filings.recent;
  const cutoff = new Date(now - days * 86400e3).toISOString().slice(0, 10);
  const upper = new Date(now).toISOString().slice(0, 10);
  const rows = [];
  for (let i = 0; i < R.form.length; i++) {
    if (!/^(8-K|8-K\/A|6-K)$/.test(R.form[i])) continue;
    if (R.filingDate[i] < cutoff || R.filingDate[i] > upper) continue;
    rows.push({
      acc: R.accessionNumber[i],
      form: R.form[i],
      date: R.filingDate[i],
      items: R.items?.[i] || "",
    });
  }
  const oldest = R.filingDate[R.filingDate.length - 1];
  const truncatedList = (sub.filings.files?.length || 0) > 0 && oldest > cutoff;
  return { rows, cutoff, truncatedList, oldestInRecent: oldest };
}

// Pick the passages worth sending to a model. Returns windows plus what was cut, so a cap is
// visible to the caller instead of silently shrinking the pool.
export function windowsFrom(text, { width = 700, max = 10 } = {}) {
  const hits = [];
  for (const [cls, re] of Object.entries(TRIGGERS)) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(text))) hits.push({ at: m.index, cls });
  }
  hits.sort((a, b) => a.at - b.at);
  const merged = [];
  for (const h of hits) {
    const s = Math.max(0, h.at - width);
    const e = Math.min(text.length, h.at + width);
    const last = merged[merged.length - 1];
    if (last && s <= last.end) {
      last.end = Math.max(last.end, e);
      last.cls.add(h.cls);
      last.n++;
    } else merged.push({ start: s, end: e, cls: new Set([h.cls]), n: 1 });
  }
  const scored = merged.map((w) => {
    const body = text.slice(w.start, w.end);
    return { start: w.start, text: body, score: w.cls.size * 10 + Math.min(w.n, 10) + (AMOUNT.test(body) ? 5 : 0) };
  });
  scored.sort((a, b) => b.score - a.score || a.start - b.start);
  const keptRaw = scored.slice(0, max);
  const dropped = scored.slice(max);
  const kept = keptRaw.sort((a, b) => a.start - b.start);
  return { windows: kept, total: scored.length, kept: kept.length, droppedStrong: dropped.filter((w) => STRONG_DILUTION.test(w.text)).length };
}

let _tickers = null;
async function cikFor(t, get) {
  if (!_tickers) _tickers = await get("https://www.sec.gov/files/company_tickers.json", { json: true });
  const T = t.toUpperCase();
  for (const k in _tickers) if (_tickers[k].ticker.toUpperCase() === T) return String(_tickers[k].cik_str).padStart(10, "0");
  return null;
}

// `get` is injectable so tests run offline against recorded filings.
export async function collectFilingEvents(ticker, { days = 90, now = Date.now(), maxFilings = 40, get = secGet } = {}) {
  const cik = await cikFor(ticker, get);
  if (!cik) return { ticker, error: "no CIK (renamed, delisted or foreign symbol: resolve by name)", filings: [], drops: [] };
  const sub = await get(`https://data.sec.gov/submissions/CIK${cik}.json`, { json: true });
  const L = listFilings(sub, { now, days });
  const drops = [];
  // Newest first; when over the cap, NAME the filings left unread.
  let rows = L.rows.sort((a, b) => (a.date < b.date ? 1 : -1));
  if (rows.length > maxFilings) {
    for (const r of rows.slice(maxFilings)) drops.push({ ...r, reason: `over maxFilings=${maxFilings}` });
    rows = rows.slice(0, maxFilings);
  }
  const filings = [];
  for (const r of rows) {
    const acc = r.acc.replace(/-/g, "");
    const url = `https://www.sec.gov/Archives/edgar/data/${+cik}/${acc}/${r.acc}.txt`;
    let raw;
    try {
      raw = await get(url);
    } catch (e) {
      drops.push({ ...r, reason: `fetch failed: ${e.message}` });
      continue;
    }
    const docs = splitSubmission(raw)
      .filter((d) => KEEP_TYPE.test(d.type))
      .map((d) => {
        const text = htmlToText(d.text);
        return { type: d.type, chars: text.length, text, ...windowsFrom(text) };
      });
    const hasExhibit = docs.some((d) => /^EX-/i.test(d.type));
    // Items that announce an agreement/issuance with no exhibit attached: the terms are
    // somewhere we did not read, so the verdict for this filing is `unknown`.
    const termsItem = /(^|,)(1\.01|2\.03|3\.02)(,|$)/.test(r.items);
    filings.push({ ...r, docs, exhibitMissing: termsItem && !hasExhibit });
  }
  return {
    ticker,
    cik,
    name: sub.name,
    cutoff: L.cutoff,
    filings,
    drops,
    coverage: { listed: L.rows.length, read: filings.length, truncatedList: L.truncatedList, oldestInRecent: L.oldestInRecent },
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  for (const t of process.argv.slice(2).filter((a) => !a.startsWith("--"))) {
    const r = await collectFilingEvents(t);
    if (r.error) { console.log(`${t}: ${r.error}`); continue; }
    console.log(`${t} [${r.name}] since ${r.cutoff}: read ${r.coverage.read}/${r.coverage.listed} filings${r.coverage.truncatedList ? " (LIST TRUNCATED: recent page stops at " + r.coverage.oldestInRecent + ")" : ""}`);
    for (const f of r.filings)
      console.log(`  ${f.date} ${f.form} items=${f.items || "-"}${f.exhibitMissing ? " EXHIBIT-MISSING" : ""} docs=${f.docs.map((d) => `${d.type}(${d.kept}/${d.total}w${d.droppedStrong ? " DROPPED-STRONG=" + d.droppedStrong : ""})`).join(",")}`);
    for (const d of r.drops) console.log(`  DROP ${d.date} ${d.form} ${d.acc} ${d.reason}`);
  }
}
