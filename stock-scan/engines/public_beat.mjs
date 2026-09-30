#!/usr/bin/env node
// I4 gate, measured definition: "an earnings beat that was ALREADY PUBLIC within the 90 days
// before the insider event". This is the exact catalyst definition behind the re-test
// (backtesting/insider_cluster/RETEST_N39.md, matured-trades correction 2026-10-01):
//   insider + public beat   +5.23% median net (n=23)
//   insider, no beat        -2.61% (n=54)   <- refuse
// Why a separate module: universe_catalyst.mjs only looks back 25 days for an already-reported
// beat, but insiders bought a median 24 days after the beat and 12 of the 24 qualifying
// backtest events sat MORE than 25 days back (max 78). A 25-day window would have labelled half
// of the proven cases "no catalyst".
//
// It deliberately does NOT require the market to have rewarded the print. The re-test never
// conditioned on the reaction, and the "drift only when the beat was rewarded" belief is what the
// research found dead. `surprise` is a free GAAP-vs-consensus feed (see trap-earnings-beat-is-fake):
// a BEAT here is necessary, not sufficient, and the DD still reads the release.
//
// Fail-closed: a failed feed, or a feed with no quarters, is UNKNOWN, never NO_BEAT. A gate that
// reports "no catalyst" because it could not look is a signal that cannot fire (KB trap #14).
import { nasdaqSurprise } from "./earnings_cal.mjs";

const DAY = 86400e3;

// Nasdaq returns MM/DD/YYYY; accept ISO too. null on anything else (never guess a date).
export function parseDate(s) {
  if (!s) return null;
  let m = String(s).match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m) return new Date(Date.UTC(+m[3], +m[1] - 1, +m[2]));
  m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])) : null;
}

// eventDate: the insider cluster's filing date (when the market could first see it). Default today.
export async function publicBeat(ticker, eventDate = new Date(), { days = 90, surprise = nasdaqSurprise } = {}) {
  const ev = parseDate(eventDate instanceof Date ? eventDate.toISOString().slice(0, 10) : eventDate);
  if (!ev) return { ticker, status: "UNKNOWN", reason: `unparseable event date ${eventDate}` };
  const rows = await surprise(ticker);
  if (rows == null) return { ticker, status: "UNKNOWN", reason: "surprise feed failed" };
  if (!rows.length) return { ticker, status: "UNKNOWN", reason: "feed returned no quarters (new listing or feed gap), not evidence of no beat" };
  const dated = rows.map((r) => ({ ...r, d: parseDate(r.reported) })).filter((r) => r.d);
  if (!dated.length) return { ticker, status: "UNKNOWN", reason: "no quarter carried a parseable report date" };
  const inWindow = dated
    .filter((r) => r.surpPct != null && r.surpPct > 0)
    .filter((r) => ev - r.d >= 0 && ev - r.d <= days * DAY)        // public on or before the event, never after
    .sort((a, b) => b.d - a.d);
  if (inWindow.length) {
    const b = inWindow[0];
    return { ticker, status: "BEAT", reported: b.d.toISOString().slice(0, 10), daysBefore: Math.round((ev - b.d) / DAY), qtr: b.qtr, surpPct: b.surpPct };
  }
  const latest = dated.sort((a, b) => b.d - a.d)[0];
  return {
    ticker, status: "NO_BEAT",
    reason: `no positive surprise reported in the ${days}d before ${ev.toISOString().slice(0, 10)}`,
    latestReported: latest.d.toISOString().slice(0, 10), latestSurpPct: latest.surpPct,
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  // usage: node public_beat.mjs TICKER[:YYYY-MM-DD] ...   (event date defaults to today)
  let unknown = 0;
  for (const a of process.argv.slice(2)) {
    const [t, d] = a.split(":");
    const r = await publicBeat(t, d || new Date());
    if (r.status === "UNKNOWN") unknown++;
    console.log(JSON.stringify(r));
    await new Promise((z) => setTimeout(z, 200));
  }
  process.exit(unknown ? 2 : 0);
}
