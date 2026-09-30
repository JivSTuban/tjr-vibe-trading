// Offline tests for the two-pass 8-K veto. Real filing excerpts live in fixtures/ (public SEC
// text from 2026-09-30 runs). Run: node --test stock-scan/engines/veto_extract.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { verifyQuote, classify, decide, coverageGaps, vetoTicker, TAXONOMY, P1_SCHEMA } from "./veto_extract.mjs";
import { splitSubmission, htmlToText, listFilings, windowsFrom, collectFilingEvents } from "./filing_events.mjs";

const fx = (n) => readFileSync(new URL(`./fixtures/${n}`, import.meta.url), "utf8");
const GME = fx("gme_exchange.txt");
const QUOTE = "In total, the Existing Noteholders will receive in the aggregate approximately 55.5 million shares of Common Stock";
const noCache = (_k, fn) => fn();

test("verifyQuote: exact, curly-quote normalised, fuzzy, fabricated", () => {
  assert.equal(verifyQuote(QUOTE, GME), "exact");
  assert.equal(verifyQuote(QUOTE.replace("Company", "Company"), GME.replace(/"/g, "“")), "exact");
  assert.equal(verifyQuote("In total the Existing Noteholders will receive in the aggregate approximately 55.5 million shares of Common Stock", GME), "fuzzy");
  assert.equal(verifyQuote("The Company sold 12,000,000 shares in an underwritten public offering priced at $4.00 per share", GME), "none");
  assert.equal(verifyQuote("", GME), "none");
  assert.equal(verifyQuote("55.5 shares", GME), "none", "a short non-substring must not pass fuzzy");
});

test("every taxonomy label has a class and is in the schema enum", () => {
  const en = P1_SCHEMA.properties.findings.items.properties.label.enum;
  assert.deepEqual([...en].sort(), Object.keys(TAXONOMY).sort());
});

const base = { label: "EQUITY_FOR_DEBT_EXCHANGE", issuer_action: "issuer_did_it", grounded: "exact" };
const p2 = (o) => ({ own_label: "EQUITY_FOR_DEBT_EXCHANGE", issuer_did_it: true, contradicted_nearby: false, score: 5, reason: "", ...o });

test("decide: confirmed VETO-class finding vetoes", () => {
  assert.equal(decide([{ ...base, p2: p2() }]).verdict, "VETO");
});
test("decide: fabricated quote never vetoes, and is named, and forces CAVEAT", () => {
  const d = decide([{ ...base, grounded: "none", p2: null }]);
  assert.equal(d.verdict, "CAVEAT");
  assert.equal(d.rows[0].status, "UNGROUNDED");
});
test("decide: holder resale and hypothetical language are not issuer events", () => {
  for (const issuer_action of ["holder_resale", "hypothetical", "other"]) {
    const d = decide([{ ...base, label: "EQUITY_ISSUANCE", issuer_action, p2: p2({ own_label: "EQUITY_ISSUANCE" }) }]);
    assert.equal(d.verdict, "CLEAR", issuer_action);
  }
});
test("decide: non-dilutive debt is explained, not vetoed (ADC / UBER notes)", () => {
  const d = decide([{ ...base, label: "NON_DILUTIVE_DEBT", p2: null }]);
  assert.equal(d.verdict, "CLEAR");
  assert.equal(d.rows[0].status, "EXPLAINED");
});
test("decide: pass 2 unavailable keeps a verified VETO-class finding as a provisional VETO (fail closed)", () => {
  const d = decide([{ ...base, p2: "unavailable" }]);
  assert.equal(d.verdict, "VETO");
  assert.equal(d.rows[0].status, "PROVISIONAL");
});
test("decide: low pass-2 score rejects, contradiction or wrong label downgrades", () => {
  assert.equal(decide([{ ...base, p2: p2({ score: 2 }) }]).verdict, "CLEAR");
  assert.equal(decide([{ ...base, p2: p2({ own_label: "NONE", score: 5 }) }]).verdict, "CLEAR");
  assert.equal(decide([{ ...base, p2: p2({ contradicted_nearby: true }) }]).verdict, "CAVEAT");
  assert.equal(decide([{ ...base, p2: p2({ score: 3 }) }]).verdict, "CAVEAT");
  assert.equal(decide([{ ...base, p2: p2({ own_label: "BUYBACK" }) }]).verdict, "CAVEAT");
  assert.equal(decide([{ ...base, p2: p2({ issuer_did_it: false }) }]).verdict, "CLEAR");
});
test("decide: a financial-statement period total is a caveat, not a veto (INR preferred line)", () => {
  const d = decide([{ ...base, label: "EQUITY_ISSUANCE", timing: "period_financial_statement", p2: p2({ own_label: "EQUITY_ISSUANCE" }) }]);
  assert.equal(d.verdict, "CAVEAT");
  assert.match(d.rows[0].note, /verify the date/);
  assert.equal(decide([{ ...base, label: "EQUITY_ISSUANCE", timing: "dated_event", p2: p2({ own_label: "EQUITY_ISSUANCE" }) }]).verdict, "VETO");
});
test("decide: nothing found is CLEAR only if nothing was unknown", () => {
  assert.equal(decide([], []).verdict, "CLEAR");
  assert.equal(decide([], ["unread 8-K 2026-08-03: fetch failed"]).verdict, "CAVEAT");
});
test("classify: CAVEAT-class label alone does not veto", () => {
  const d = decide([{ label: "EXEC_DEPARTURE", issuer_action: "issuer_did_it", grounded: "exact", p2: p2({ own_label: "EXEC_DEPARTURE" }) }]);
  assert.equal(d.verdict, "CAVEAT");
});

test("htmlToText / splitSubmission keep exhibits and types", () => {
  assert.equal(htmlToText("<p>Hello&nbsp;<b>world</b> &amp; co&#8217;s</p>"), "Hello world & co's");
  const txt = `<DOCUMENT><TYPE>8-K<TEXT><html>main</html></TEXT></DOCUMENT><DOCUMENT><TYPE>EX-99.1<TEXT>press</TEXT></DOCUMENT>`;
  assert.deepEqual(splitSubmission(txt).map((d) => d.type), ["8-K", "EX-99.1"]);
});

const sub = (dates, more = false) => ({
  name: "X",
  filings: {
    recent: {
      form: dates.map(() => "8-K"), filingDate: dates, accessionNumber: dates.map((_, i) => `0000000000-26-00000${i}`),
      items: dates.map(() => "1.01,3.02"), primaryDocument: dates.map(() => "a.htm"),
    },
    files: more ? [{ name: "older.json" }] : [],
  },
});
test("listFilings: honours an injected clock and flags a truncated list", () => {
  const now = Date.parse("2026-09-30");
  const a = listFilings(sub(["2026-09-20", "2026-01-01"]), { now, days: 90 });
  assert.equal(a.rows.length, 1);
  assert.equal(a.truncatedList, false);
  const b = listFilings(sub(["2026-09-20", "2026-08-01"], true), { now, days: 90 });
  assert.equal(b.truncatedList, true, "recent page ends inside the window and older pages exist");
});

test("listFilings: an as-of replay never reads filings made after the as-of date", () => {
  const s = sub(["2026-09-25", "2026-09-05", "2026-08-20"]);
  const r = listFilings(s, { now: Date.parse("2026-09-10"), days: 90 });
  assert.deepEqual(r.rows.map((x) => x.date), ["2026-09-05", "2026-08-20"], "the 09-25 filing is in the future of the replay date");
  const same = listFilings(s, { now: Date.parse("2026-09-25"), days: 90 });
  assert.equal(same.rows.length, 3, "a filing on the as-of day itself is public and counts");
});

test("windowsFrom: finds the exchange, reports caps by name not count", () => {
  const w = windowsFrom(GME);
  assert.ok(w.windows.some((x) => x.text.includes("55.5 million shares")));
  const many = Array.from({ length: 30 }, (_, i) => `${"filler ".repeat(400)} convertible notes issued ${i}`).join(" ");
  const m = windowsFrom(many, { max: 5 });
  assert.equal(m.kept, 5);
  assert.ok(m.total > 5 && m.droppedStrong > 0);
  assert.equal(windowsFrom(fx("risk_boilerplate.txt")).windows.length, 1, "boilerplate still reaches the model; the model, not a regex, rules it out");
});

test("coverageGaps: exhibit cuts are notes when the body was read, unknown otherwise", () => {
  const f = (docs) => ({ form: "8-K", date: "2026-08-07", docs });
  const body = { type: "8-K", total: 2, kept: 2, droppedStrong: 0 };
  const ex = { type: "EX-10.1", total: 40, kept: 10, droppedStrong: 10 };
  assert.equal(coverageGaps(f([body, ex]), []).unknowns.length, 0);
  assert.equal(coverageGaps(f([body, ex]), []).notes.length, 1, "named, not silent");
  assert.equal(coverageGaps(f([{ ...body, droppedStrong: 1 }, ex]), []).unknowns.length, 1, "a cut BODY excerpt is unknown");
  assert.equal(coverageGaps(f([{ type: "8-K", total: 0, kept: 0, droppedStrong: 0 }, ex]), []).unknowns.length, 1, "terms only in the exhibit");
  assert.equal(coverageGaps(f([body]), [{ doc: "EX-99.1", text: "convertible" }]).unknowns.length, 1, "cut press-release excerpt");
});

// ---- collector, offline ----
const fullTxt = (types) => types.map(([t, b]) => `<DOCUMENT><TYPE>${t}<TEXT>${b}</TEXT></DOCUMENT>`).join("");
const fakeGet = (routes) => async (url, o = {}) => {
  for (const [k, v] of Object.entries(routes)) if (url.includes(k)) { if (v instanceof Error) throw v; return o.json ? v : v; }
  throw new Error(`unrouted ${url}`);
};
const tickers = { 0: { ticker: "FAKE", cik_str: 123 } };
const NOW = Date.parse("2026-09-30");

test("collectFilingEvents: a fetch failure is a NAMED drop, over-cap filings are named, missing exhibit flagged", async () => {
  const s = sub(["2026-09-25", "2026-09-20", "2026-09-10"]);
  const get = fakeGet({
    "company_tickers": tickers,
    "submissions/CIK": s,
    "000000000026000000/": fullTxt([["8-K", "<p>agreement</p>"]]),
    "000000000026000001/": new Error("HTTP 503"),
    "000000000026000002/": fullTxt([["8-K", "x"], ["EX-10.1", "y"]]),
  });
  const r = await collectFilingEvents("FAKE", { now: NOW, maxFilings: 2, get });
  assert.equal(r.filings.length, 1, "0 read OK + 1 fetch-failed of the 2 newest");
  assert.ok(r.filings[0].exhibitMissing, "Item 1.01/3.02 with no exhibit");
  const reasons = r.drops.map((d) => d.reason);
  assert.ok(reasons.some((x) => x.startsWith("fetch failed")));
  assert.ok(reasons.some((x) => x.startsWith("over maxFilings")));
  assert.ok(r.drops.every((d) => d.acc && d.date), "each drop names its filing");
});

// ---- end to end with fakes ----
const evWith = (docText, extra = {}) => async () => ({
  name: "Fake Co", cutoff: "2026-07-02", drops: [], coverage: { truncatedList: false },
  filings: [{ acc: "0000000000-26-000001", form: "8-K", date: "2026-08-03", items: "1.01,3.02", exhibitMissing: false,
    docs: [{ type: "8-K", total: 1, kept: 1, droppedStrong: 0, windows: [{ score: 30, text: docText }] }] }],
  ...extra,
});
const finding = (quote, o = {}) => ({ window_id: "W1", label: "EQUITY_FOR_DEBT_EXCHANGE", issuer_action: "issuer_did_it", quote, amount_text: null, shares_text: "approximately 55.5 million shares", ...o });

test("vetoTicker: GME-shaped exchange is a VETO with a grounded quote and a text-verified share count", async () => {
  const r = await vetoTicker("FAKE", { collect: evWith(GME), cache: noCache,
    p1: () => ({ out: { findings: [finding(QUOTE)] } }), p2: () => ({ out: p2() }) });
  assert.equal(r.verdict, "VETO");
  assert.equal(r.rows[0].shares, "approximately 55.5 million shares");
});
test("vetoTicker: pass-2 engine defaults to claude (Haiku), codex is an explicit opt-in, unknown is refused", async () => {
  const opts = { collect: evWith(GME), cache: noCache, p1: () => ({ out: { findings: [finding(QUOTE)] } }), p2: () => ({ out: p2() }) };
  assert.equal((await vetoTicker("FAKE", opts)).rows[0].p2_engine, "claude");
  assert.equal((await vetoTicker("FAKE", { ...opts, p2Engine: "codex" })).rows[0].p2_engine, "codex");
  await assert.rejects(() => vetoTicker("FAKE", { ...opts, p2Engine: "gpt" }), /unknown --p2 engine/);
});
test("vetoTicker: the pass-2 cache key carries the engine, so a Haiku verdict is never served as a Codex one", async () => {
  const keys = [];
  const cache = (k, fn) => (keys.push(k), fn());
  const base = { collect: evWith(GME), cache, p1: () => ({ out: { findings: [finding(QUOTE)] } }), p2: () => ({ out: p2() }) };
  await vetoTicker("FAKE", base);
  await vetoTicker("FAKE", { ...base, p2Engine: "codex" });
  const p2k = keys.filter((k) => k.startsWith("p2-"));
  assert.equal(p2k.length, 2);
  assert.notEqual(p2k[0], p2k[1]);
});
test("vetoTicker: a number the model invented is dropped, not reported", async () => {
  const r = await vetoTicker("FAKE", { collect: evWith(GME), cache: noCache,
    p1: () => ({ out: { findings: [finding(QUOTE, { shares_text: "99 million shares" })] } }), p2: () => ({ out: p2() }) });
  assert.equal(r.rows[0].shares, null);
});
test("vetoTicker: fabricated quote is ungrounded -> CAVEAT, never VETO", async () => {
  const r = await vetoTicker("FAKE", { collect: evWith(GME), cache: noCache,
    p1: () => ({ out: { findings: [finding("The Company sold 12,000,000 shares in an underwritten public offering priced at $4.00 per share")] } }),
    p2: () => assert.fail("pass 2 must not run on an ungrounded claim") });
  assert.equal(r.verdict, "CAVEAT");
  assert.equal(r.rows[0].status, "UNGROUNDED");
});
test("vetoTicker: pass 2 down -> provisional VETO; pass 1 down -> unknown CAVEAT, not CLEAR", async () => {
  const a = await vetoTicker("FAKE", { collect: evWith(GME), cache: noCache,
    p1: () => ({ out: { findings: [finding(QUOTE)] } }), p2: () => { throw new Error("usage limit"); } });
  assert.equal(a.verdict, "VETO");
  assert.match(a.rows[0].p2_error, /usage limit/);
  const b = await vetoTicker("FAKE", { collect: evWith(GME), cache: noCache, p1: () => { throw new Error("auth"); } });
  assert.equal(b.verdict, "CAVEAT");
  assert.match(b.unknowns.join(" "), /pass 1 failed/);
});
test("vetoTicker: unresolvable ticker is a CAVEAT with the reason, not CLEAR", async () => {
  const r = await vetoTicker("ZZZZ", { collect: async () => ({ error: "no CIK" }), cache: noCache });
  assert.equal(r.verdict, "CAVEAT");
});
test("vetoTicker: ADC-shaped senior notes are explained, not vetoed", async () => {
  const r = await vetoTicker("FAKE", { collect: evWith(fx("adc_notes.txt")), cache: noCache,
    p1: () => ({ out: { findings: [{ window_id: "W1", label: "NON_DILUTIVE_DEBT", issuer_action: "issuer_did_it",
      quote: "underwritten public offering of $400,000,000 aggregate principal amount of the Issuer's 5.650% Notes due 2036", amount_text: "$400,000,000", shares_text: null }] } }),
    p2: () => assert.fail("CLEAR-class findings are not sent to pass 2") });
  assert.equal(r.verdict, "CLEAR");
});
