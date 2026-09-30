#!/usr/bin/env node
// I5-DD leg 2b: two-pass GROUNDED veto over 8-K / 6-K text. VETO side only: it can add a
// veto or a caveat, never clear a name the older gates flagged, and it never sizes anything.
//
//   pass 1  (claude -p)   label from a fixed taxonomy + a verbatim quote per event
//   check   (code)        the quote must exist in the excerpt, else the claim is ungrounded
//   pass 2  (claude -p)   a SMALLER model (Haiku) re-reads quote + surrounding excerpt and
//                         labels it independently, never shown pass 1's label or reasoning.
//                         `--p2 codex` opts into a different model family (see below)
//   decide  (code)        verdict from verified, agreed findings only
//
// Design sources: arXiv 2607.08346 (2026-07-09: label + quote + independent regrade took
// precision 12% -> 96% at the top score); same-family judges can share blind spots (arXiv 2604.22891, 2604.07650, unverified here), so codex is OPT-IN, not
// the default: it spends ChatGPT quota, a dead quota turns verified vetoes provisional, and on the
// 2026-09-30 replay (GME, RWT, ADC, INR) Haiku re-graded correctly. Every finding carries the engine
// that graded it and a same-family grade is tagged SAME-FAMILY. Compare the two on the replay set
// once before deciding Codex is worth keeping.
// Fail-closed rules, from KB traps #9-#17:
//   * a quote not found in the filing is discarded AND named, and the filing is `unknown`;
//   * a filing we could not fetch / a truncated list / a missing exhibit is `unknown`;
//   * CLEAR is only returned when nothing was unknown; "no findings" from a source that was
//     not fully read is not a clean bill (KB: "unverified is not absent");
//   * if pass 2 is unavailable a verified VETO-class finding stays a provisional VETO
//     (the quote is shown, so a human can overrule it in seconds; the reverse costs money).
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { tmpdir, homedir } from "node:os";
import { createHash } from "node:crypto";
import { join } from "node:path";
import { collectFilingEvents, STRONG_DILUTION } from "./filing_events.mjs";

// label -> how it counts. VETO labels are the ones the DD gate already treats as killers
// (SKILL.md P4: going concern, active ATM, shelf takedown); CAVEAT labels are surfaced but
// do not block alone; CLEAR labels are explicit negatives that stop false vetoes
// (ADC's 424B5 was partnership notes, UBER's was EUR4.5B of senior notes; 2026-09-17).
export const TAXONOMY = {
  EQUITY_ISSUANCE: "VETO",            // shares sold for cash: public, registered direct, PIPE, ATM sale
  EQUITY_FOR_DEBT_EXCHANGE: "VETO",   // notes exchanged for shares (the GME hole)
  CONVERTIBLE_ISSUANCE: "VETO",       // convertible notes / convertible preferred issued (the RWT hole)
  EQUITY_LINE_OR_ATM_AGREEMENT: "VETO", // capacity to issue established, even if undrawn
  GOING_CONCERN: "VETO",
  NON_RELIANCE: "VETO",               // Item 4.02, prior financials can no longer be relied on
  DEBT_DEFAULT_OR_ACCELERATION: "VETO",
  LISTING_DEFICIENCY: "VETO",         // Item 3.01 delisting / minimum-bid / equity notice
  WARRANT_ISSUANCE: "CAVEAT",
  REVERSE_SPLIT: "CAVEAT",
  MATERIAL_WEAKNESS: "CAVEAT",
  AUDITOR_CHANGE: "CAVEAT",
  EXEC_DEPARTURE: "CAVEAT",           // Item 5.02, matters most right after an insider buy
  CYBER_INCIDENT: "CAVEAT",
  REGULATORY_ACTION: "CAVEAT",        // subpoena, Wells notice, cease-and-desist
  NON_DILUTIVE_DEBT: "CLEAR",         // senior notes / credit facility with no equity feature
  BUYBACK: "CLEAR",
};
const LABELS = Object.keys(TAXONOMY);
const ACTIONS = ["issuer_did_it", "holder_resale", "hypothetical", "other"];
// A line in a financial statement ("Proceeds from issuance of Series A Preferred Stock 350,000"
// in a six-month cash-flow table) proves the event happened at SOME point in the period, not
// that it is new. INR 2026-09-30: a $350M preferred issuance that funded an earlier
// acquisition was read as a fresh veto. Such findings are caveats with the quote shown.
const TIMINGS = ["dated_event", "period_financial_statement", "undated"];
// A VETO-class dilution label only counts when the ISSUER did it (a holder's resale
// registration sends the company nothing) and it is not hypothetical risk-factor language.
const NEEDS_ISSUER = new Set(["EQUITY_ISSUANCE", "EQUITY_FOR_DEBT_EXCHANGE", "CONVERTIBLE_ISSUANCE", "EQUITY_LINE_OR_ATM_AGREEMENT", "WARRANT_ISSUANCE"]);

const nullableStr = { type: ["string", "null"] };
export const P1_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["findings"],
  properties: {
    findings: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["window_id", "label", "issuer_action", "timing", "quote", "amount_text", "shares_text"],
        properties: {
          window_id: { type: "string" },
          label: { type: "string", enum: LABELS },
          issuer_action: { type: "string", enum: ACTIONS },
          timing: { type: "string", enum: TIMINGS },
          quote: { type: "string" },
          amount_text: nullableStr,
          shares_text: nullableStr,
        },
      },
    },
  },
};
export const P2_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["own_label", "issuer_did_it", "contradicted_nearby", "score", "reason"],
  properties: {
    own_label: { type: "string", enum: [...LABELS, "NONE"] },
    issuer_did_it: { type: "boolean" },
    contradicted_nearby: { type: "boolean" },
    score: { type: "integer", enum: [1, 2, 3, 4, 5] },
    reason: { type: "string" },
  },
};

const LABEL_HELP = `EQUITY_ISSUANCE: the issuer sold or agreed to sell new shares for cash (public offering, registered direct, PIPE, an ATM sale actually made).
EQUITY_FOR_DEBT_EXCHANGE: the issuer exchanged notes or other debt for new shares.
CONVERTIBLE_ISSUANCE: the issuer issued convertible notes or convertible preferred stock.
EQUITY_LINE_OR_ATM_AGREEMENT: a sales / equity-line agreement that lets the issuer sell shares over time (capacity, even if nothing sold yet).
WARRANT_ISSUANCE: new warrants issued by the issuer.
GOING_CONCERN: substantial doubt about the issuer's ability to continue as a going concern.
NON_RELIANCE: prior financial statements should no longer be relied on / restatement (Item 4.02).
DEBT_DEFAULT_OR_ACCELERATION: event of default, acceleration, forbearance.
LISTING_DEFICIENCY: exchange notice about delisting, minimum bid or equity requirement.
REVERSE_SPLIT: a reverse stock split.
MATERIAL_WEAKNESS: a material weakness in internal control.
AUDITOR_CHANGE: the issuer dismissed or engaged an auditor.
EXEC_DEPARTURE: a named officer or director resigned or was terminated.
CYBER_INCIDENT: a cybersecurity incident.
REGULATORY_ACTION: subpoena, Wells notice, cease-and-desist or similar.
NON_DILUTIVE_DEBT: senior notes, a credit facility or other debt with NO conversion or equity feature.
BUYBACK: a share repurchase.`;

const P1_SYSTEM = `You read excerpts from SEC filings (8-K, 8-K/A, 6-K and their exhibits) of ONE issuer and report events that could harm or help existing shareholders.
Use ONLY the text given. For each event output: window_id, label, issuer_action, quote, amount_text, shares_text.
- quote: copied CHARACTER FOR CHARACTER from the excerpt, one contiguous span, at most 350 characters. Never paraphrase, never join separate sentences.
- amount_text and shares_text: copied verbatim from the excerpt (e.g. "$185 million", "55,500,000 shares") or null. Never compute a number.
- timing: dated_event (the text gives a date or says today / announced / entered into), period_financial_statement (a line in a financial statement or table that totals a period, such as a cash-flow line), undated.
- issuer_action: issuer_did_it, holder_resale (a holder registers or sells shares and the company receives nothing), hypothetical (risk-factor or "may / could" language, not something that happened), other.
- Risk-factor boilerplate and forward-looking "may issue" language is NOT an event.
- Debt with no conversion or equity feature is NON_DILUTIVE_DEBT, not dilution.
- If an excerpt holds no event, output nothing for it. An empty findings array is a valid answer.
Labels:
${LABEL_HELP}`;

const P2_SYSTEM = `You audit a claim about an SEC filing. You are given an issuer, the filing header, an excerpt, and ONE quoted span from that excerpt. Decide independently what the quoted span says happened.
- own_label: the best label from the list, or NONE if the span is not an event.
- issuer_did_it: true only if the issuer itself did the thing (not a holder, not a third party, not hypothetical).
- contradicted_nearby: true if the excerpt around the span negates, conditions, terminates or qualifies it (for example "no shares were sold", "the agreement was terminated", "subject to approval that has not happened").
- score 1-5: 5 = unambiguous completed event by this issuer, 4 = clear, 3 = plausible but conditional or partial, 2 = weak, 1 = not supported by the text.
- reason: one sentence, at most 200 characters.
Use only the text given.
Labels:
${LABEL_HELP}`;

// ---------- grounding ----------
export function norm(s) {
  return String(s)
    .toLowerCase()
    .replace(/[‘’‚′']/g, "'")
    .replace(/[“”„″"]/g, '"')
    .replace(/[‐-―-]/g, "-")
    .replace(/\s+/g, " ")
    .trim();
}
// "exact" (normalized substring) or "fuzzy" (>=90% of the quote's 5-word shingles appear in
// the source; tolerates a dropped ellipsis or a repaired typo but not an invented sentence).
export function verifyQuote(quote, source) {
  const q = norm(quote), s = norm(source);
  if (!q) return "none";
  if (s.includes(q)) return "exact";
  // Punctuation is not a way to fabricate a fact, so the fuzzy path ignores it.
  const loose = (x) => x.replace(/[^a-z0-9$%.]+/g, " ").replace(/\s+/g, " ").trim();
  const ls = " " + loose(s) + " ";
  const w = loose(q).split(" ");
  if (w.length < 8) return "none";
  const sh = [];
  for (let i = 0; i + 5 <= w.length; i++) sh.push(w.slice(i, i + 5).join(" "));
  const found = sh.filter((x) => ls.includes(" " + x + " ")).length;
  return found / sh.length >= 0.9 ? "fuzzy" : "none";
}

// ---------- decision (pure) ----------
// finding: { label, issuer_action, grounded: 'exact'|'fuzzy'|'none', p2: {own_label,issuer_did_it,contradicted_nearby,score}|null|'unavailable' }
export function classify(f) {
  const cls = TAXONOMY[f.label];
  if (f.grounded === "none") return { status: "UNGROUNDED", cls };
  if (cls === "CLEAR") return { status: "EXPLAINED", cls };
  if (NEEDS_ISSUER.has(f.label) && f.issuer_action !== "issuer_did_it") return { status: "NOT_ISSUER_EVENT", cls };
  // A period-total line is evidence the event happened sometime in the period, not that it is new.
  if (f.timing === "period_financial_statement" && cls === "VETO") return { status: "PROBABLE", cls, note: "period total, not a dated event: verify the date" };
  if (f.p2 === "unavailable") return { status: cls === "VETO" ? "PROVISIONAL" : "PROBABLE", cls };
  const p = f.p2;
  if (!p) return { status: "PROBABLE", cls };
  const sameClass = p.own_label !== "NONE" && TAXONOMY[p.own_label] === cls;
  if (p.score <= 2 || p.own_label === "NONE") return { status: "REJECTED", cls };
  if (NEEDS_ISSUER.has(f.label) && !p.issuer_did_it) return { status: "REJECTED", cls };
  if (p.score >= 4 && sameClass && !p.contradicted_nearby) return { status: "CONFIRMED", cls };
  return { status: "PROBABLE", cls };
}

export function decide(findings, unknowns = []) {
  const rows = findings.map((f) => ({ ...f, ...classify(f) }));
  const has = (st, cls) => rows.some((r) => r.status === st && (!cls || r.cls === cls));
  let verdict = "CLEAR";
  if (has("CONFIRMED", "VETO") || has("PROVISIONAL", "VETO")) verdict = "VETO";
  else if (has("CONFIRMED", "CAVEAT") || has("PROBABLE") || has("UNGROUNDED") || unknowns.length) verdict = "CAVEAT";
  return { verdict, rows, unknowns };
}

// ---------- LLM runners (spawn CLIs; session/subscription auth, no API key in the repo) ----------
function parseOrThrow(s, what) {
  try { return JSON.parse(s); } catch { throw new Error(`${what}: not JSON: ${String(s).slice(0, 120)}`); }
}
export function runClaude({ system, prompt, schema, model = process.env.VETO_P1_MODEL || "claude-sonnet-5-5" }) {
  const r = spawnSync(
    "claude",
    ["-p", "--json-schema", JSON.stringify(schema), "--output-format", "json", "--tools", "", "--disable-slash-commands",
      "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence", "--model", model, "--system-prompt", system],
    { input: prompt, encoding: "utf8", maxBuffer: 64 << 20, timeout: 240000 },
  );
  if (r.status !== 0) throw new Error(`claude exit ${r.status}: ${(r.stderr || r.stdout || "").slice(0, 200)}`);
  const d = parseOrThrow(r.stdout, "claude");
  // A failed run can still exit 0 (seen with codex); trust the payload, not the exit code.
  if (d.is_error || !d.structured_output) throw new Error(`claude returned no structured_output: ${String(d.result || "").slice(0, 160)}`);
  return { out: d.structured_output, cost: d.total_cost_usd || 0 };
}
export function runCodex({ system, prompt, schema, model = process.env.VETO_P2_CODEX_MODEL }) {
  const dir = mkdtempSync(join(tmpdir(), "veto-p2-"));
  const sf = join(dir, "schema.json"), of = join(dir, "out.json");
  writeFileSync(sf, JSON.stringify(schema));
  // Explicit read-only: this machine's codex config defaults to danger-full-access.
  const args = ["exec", "--output-schema", sf, "-o", of, "-s", "read-only", "--skip-git-repo-check", "--ephemeral", ...(model ? ["-m", model] : []), "-"];
  const r = spawnSync("codex", args, { input: `${system}\n\n${prompt}`, encoding: "utf8", maxBuffer: 64 << 20, timeout: 300000 });
  // codex can exit 0 on a failed run and report "Logged in" with a revoked token: the output
  // artifact is the only evidence (KB: trap-codex-false-green-auth).
  if (!existsSync(of) || !readFileSync(of, "utf8").trim()) throw new Error(`codex produced no output (exit ${r.status}): ${(r.stderr || "").slice(-200)}`);
  return { out: parseOrThrow(readFileSync(of, "utf8"), "codex"), cost: 0 };
}

// ---------- orchestration ----------
// Cache keys carry a hash of the prompts so editing the taxonomy never serves stale verdicts.
const PROMPT_V = createHash("sha1").update(P1_SYSTEM + P2_SYSTEM).digest("hex").slice(0, 8);
const cacheDir = join(homedir(), ".cache", "stock-scan-veto");
function cached(key, fn) {
  mkdirSync(cacheDir, { recursive: true });
  const f = join(cacheDir, key.replace(/[^\w.-]/g, "_") + ".json");
  if (existsSync(f)) return JSON.parse(readFileSync(f, "utf8"));
  const v = fn();
  writeFileSync(f, JSON.stringify(v));
  return v;
}

const MAX_CHARS_PER_FILING = 36000;
// The terms sit in the main document, press release and agreement exhibits; an indenture (EX-4)
// is mostly boilerplate and would otherwise fill the budget.
const docPriority = (t) => (/^EX-4/i.test(t) ? 0 : /^EX-(1|10)/i.test(t) ? 15 : /^EX-99/i.test(t) ? 20 : 30);

function buildWindows(filing) {
  const all = [];
  for (const d of filing.docs) for (const w of d.windows) all.push({ doc: d.type, score: w.score + docPriority(d.type), text: w.text });
  all.sort((a, b) => b.score - a.score);
  const kept = [];
  let used = 0;
  const cut = [];
  for (const w of all) {
    if (used + w.text.length > MAX_CHARS_PER_FILING) { cut.push(w); continue; }
    used += w.text.length;
    kept.push(w);
  }
  // Doc-level window caps (filing_events) are reported by the collector; report this cap here.
  // Only a cut that could hide an event counts (see `coverageGaps`).
  return { windows: kept.map((w, i) => ({ id: `W${i + 1}`, ...w })), cutStrong: cut.filter((w) => STRONG_DILUTION.test(w.text)) };
}

// Pass 2 defaults to Claude Haiku. `p2Engine: "codex"` is an EXPLICIT opt-in for a different model
// family; it is never a silent fallback either way, and every finding carries the
// engine that graded it so a same-family grade cannot pass for an independent one.
// An 8-K must disclose the material terms of an agreement in its own body (or the EX-99 press
// release); exhibits corroborate. So unread EXHIBIT excerpts only make the filing `unknown`
// when the body gave us nothing to read. Unread BODY excerpts with dilution language always do.
// Everything unread is still named in `notes` (KB trap #14: name what you discard).
const isBody = (t) => /^(8-K|6-K|EX-99)/i.test(t);
export function coverageGaps(f, cutStrong) {
  const unknowns = [], notes = [];
  const bodyRead = f.docs.some((d) => isBody(d.type) && d.total > 0);
  const tag = `${f.form} ${f.date}`;
  for (const d of f.docs) {
    if (!d.droppedStrong) continue;
    const msg = `${tag} ${d.type}: ${d.droppedStrong} excerpt(s) with dilution language not read (read ${d.kept} of ${d.total})`;
    (isBody(d.type) || !bodyRead ? unknowns : notes).push(msg);
  }
  for (const [doc, n] of Object.entries(cutStrong.reduce((m, w) => ((m[w.doc] = (m[w.doc] || 0) + 1), m), {}))) {
    const msg = `${tag} ${doc}: ${n} excerpt(s) with dilution language over the ${MAX_CHARS_PER_FILING}-char budget`;
    (isBody(doc) || !bodyRead ? unknowns : notes).push(msg);
  }
  return { unknowns, notes };
}

export async function vetoTicker(ticker, { days = 90, p1 = runClaude, p2, p2Engine = "claude", runP2 = true, collect = collectFilingEvents, cache = cached } = {}) {
  p2 = p2 || (p2Engine === "claude" ? (a) => runClaude({ ...a, model: process.env.VETO_P2_MODEL || "claude-haiku-4-5" }) : runCodex);
  if (p2Engine !== "claude" && p2Engine !== "codex") throw new Error(`unknown --p2 engine "${p2Engine}" (claude|codex)`);
  const ev = await collect(ticker, { days });
  if (ev.error) return { ticker, verdict: "CAVEAT", unknowns: [ev.error], rows: [], filings: 0 };
  const unknowns = [], notes = [];
  if (ev.coverage.truncatedList) unknowns.push(`filing list truncated: recent page stops at ${ev.coverage.oldestInRecent}, window starts ${ev.cutoff}`);
  for (const d of ev.drops) unknowns.push(`unread ${d.form} ${d.date} ${d.acc}: ${d.reason}`);
  const findings = [];
  let cost = 0;
  for (const f of ev.filings) {
    if (f.exhibitMissing) unknowns.push(`${f.form} ${f.date} items ${f.items} announce terms but no exhibit was attached/read`);
    const { windows, cutStrong } = buildWindows(f);
    const gaps = coverageGaps(f, cutStrong);
    unknowns.push(...gaps.unknowns);
    notes.push(...gaps.notes);
    if (!windows.length) continue;
    const head = `Issuer: ${ev.name} (${ticker}). Filing: ${f.form} filed ${f.date}, Items: ${f.items || "n/a"}.\n\n`;
    const prompt = head + windows.map((w) => `### ${w.id} [${w.doc}]\n${w.text}`).join("\n\n");
    let out;
    try {
      const r = cache(`p1-${PROMPT_V}-${f.acc}-${process.env.VETO_P1_MODEL || "default"}`, () => p1({ system: P1_SYSTEM, prompt, schema: P1_SCHEMA }));
      out = r.out; cost += r.cost || 0;
    } catch (e) {
      unknowns.push(`pass 1 failed for ${f.form} ${f.date} ${f.acc}: ${e.message}`);
      continue;
    }
    for (const x of out.findings || []) {
      const w = windows.find((v) => v.id === x.window_id);
      const grounded = w ? verifyQuote(x.quote, w.text) : "none";
      // Numbers are taken from the text, never trusted from the model.
      const amount = x.amount_text && w && norm(w.text).includes(norm(x.amount_text)) ? x.amount_text : null;
      const shares = x.shares_text && w && norm(w.text).includes(norm(x.shares_text)) ? x.shares_text : null;
      const finding = { filing: `${f.form} ${f.date} ${f.acc}`, items: f.items, doc: w?.doc, label: x.label, issuer_action: x.issuer_action, timing: x.timing, quote: x.quote, grounded, amount, shares, p2: null };
      const pre = classify(finding);
      if (runP2 && ["UNGROUNDED", "EXPLAINED", "NOT_ISSUER_EVENT"].indexOf(pre.status) < 0 && pre.cls !== "CLEAR") {
        try {
          const p2prompt = `Issuer: ${ev.name}. Filing: ${f.form} filed ${f.date}, Items: ${f.items || "n/a"}.\n\nEXCERPT:\n${w.text}\n\nQUOTED SPAN:\n"${x.quote}"`;
          const r = cache(`p2-${PROMPT_V}-${p2Engine}-${process.env.VETO_P2_MODEL || ""}-${f.acc}-${norm(x.quote).slice(0, 60)}`, () => p2({ system: P2_SYSTEM, prompt: p2prompt, schema: P2_SCHEMA }));
          finding.p2 = r.out;
          finding.p2_engine = p2Engine;
          cost += r.cost || 0;
        } catch (e) {
          finding.p2 = "unavailable";
          finding.p2_error = e.message.slice(0, 160);
        }
      }
      findings.push(finding);
    }
  }
  return { ticker, name: ev.name, since: ev.cutoff, filings: ev.filings.length, cost, notes, ...decide(findings, unknowns) };
}

function render(r) {
  const out = [`${r.ticker} [${r.name || "?"}] ${r.verdict}  (${r.filings} filings read since ${r.since || "?"}${r.cost ? `, $${r.cost.toFixed(3)}` : ""})`];
  for (const x of r.rows) {
    const p = x.p2 && x.p2 !== "unavailable" ? ` p2=${x.p2.own_label}/${x.p2.score}${x.p2.contradicted_nearby ? "/contradicted" : ""}${x.p2_engine === "claude" ? " (SAME-FAMILY)" : ""}` : x.p2 === "unavailable" ? ` p2=UNAVAILABLE(${x.p2_error || "?"})` : "";
    out.push(`  ${x.status.padEnd(16)} ${x.label}${x.timing && x.timing !== "dated_event" ? ` <${x.timing}>` : ""} [${x.filing}] quote:${x.grounded}${p}${x.amount ? ` amount=${x.amount}` : ""}${x.shares ? ` shares=${x.shares}` : ""}`);
    out.push(`      "${x.quote.slice(0, 240)}"`);
  }
  for (const u of r.unknowns) out.push(`  UNKNOWN: ${u}`);
  for (const n of r.notes || []) out.push(`  note: ${n}`);
  return out.join("\n");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const json = args.includes("--json"), runP2 = !args.includes("--no-p2");
  const pe = args.indexOf("--p2");
  const p2Engine = pe >= 0 ? args[pe + 1] : "claude";
  const di = args.indexOf("--days");
  const days = di >= 0 ? +args[di + 1] : 90;
  const tickers = args.filter((a, i) => !a.startsWith("--") && args[i - 1] !== "--days" && args[i - 1] !== "--p2");
  let bad = 0;
  const all = [];
  for (const t of tickers) {
    try {
      const r = await vetoTicker(t, { days, runP2, p2Engine });
      all.push(r);
      if (!json) console.log(render(r));
    } catch (e) {
      bad++;
      all.push({ ticker: t, verdict: "CAVEAT", error: e.message, unknowns: [`veto run failed: ${e.message}`], rows: [] });
      if (!json) console.log(`${t}: FAILED ${e.message}`);
    }
  }
  if (json) console.log(JSON.stringify(all, null, 1));
  process.exit(bad ? 1 : 0);
}
