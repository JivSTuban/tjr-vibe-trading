#!/usr/bin/env node
// Earnings calendar — the dated-catalyst source. Finnhub primary, Nasdaq FALLBACK.
//
// WHY chunked (Finnhub): a single wide-window request returns EXACTLY 1500 rows and silently
// drops the rest, so a wider window can LOSE dates a narrower one showed (AMRC 2026-11-02
// disappeared when the window grew 09-14..11-06 -> 09-14..12-06). A capped flat list reads as
// "no catalysts exist" when it means "the response was truncated". Assert each chunk < cap.
//
// WHY a fallback at all (2026-09-23): finnhub.io became unreachable from this machine — DNS
// resolves, HTTPS hangs to timeout in BOTH node and python. A dead calendar makes the
// load-bearing I4 catalyst gate report zero dated catalysts, which is indistinguishable from
// a real catalyst desert. That is `trap-a-signal-that-cannot-fire` exactly. So: if Finnhub
// yields nothing, fall through to Nasdaq's public calendar (api.nasdaq.com, keyless, one
// request per CALENDAR DAY) and say which source was used. Never return an empty map silently.
import { execSync } from "child_process";
const UA = { "User-Agent": "stock-scan research jivtuban14@gmail.com" };
const NUA = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127 Safari/537.36", "Accept": "application/json" };
const CAP = 1500;
const TODAY = new Date(process.env.ASOF || "2026-09-22");
const iso = d => d.toISOString().slice(0, 10);
const day = n => new Date(TODAY.getTime() + n * 86400e3);

const withTimeout = async (u, h, ms = 12000) => {
  const ac = new AbortController(); const tm = setTimeout(() => ac.abort(), ms);
  try { return await fetch(u, { headers: h, signal: ac.signal }); } finally { clearTimeout(tm); }
};

async function finnhubCalendar(fromDays, toDays, step) {
  const FIN = execSync("security find-generic-password -s stock-scan-finnhub -a api -w").toString().trim();
  const out = {}; let truncated = 0, total = 0;
  for (let d = fromDays; d < toDays; d += step) {
    const a = iso(day(d)), b = iso(day(Math.min(d + step - 1, toDays)));
    const j = await (await withTimeout(`https://finnhub.io/api/v1/calendar/earnings?from=${a}&to=${b}&token=${FIN}`, UA)).json();
    const rows = j.earningsCalendar || [];
    total += rows.length;
    if (rows.length >= CAP) { truncated++; console.error(`WARN chunk ${a}..${b} hit cap (${rows.length}) — shrink step`); }
    for (const e of rows) {
      const p = out[e.symbol];
      if (!p || e.date < p.date) out[e.symbol] = { date: e.date, hour: e.hour, est: e.epsEstimate, act: e.epsActual };
    }
    await new Promise(r => setTimeout(r, 120));
  }
  return { earn: out, total, truncated, symbols: Object.keys(out).length, source: "finnhub" };
}

// Nasdaq serves ONE calendar day per request and carries no `epsActual`, so a reported
// quarter's beat has to come from the per-ticker surprise endpoint (nasdaqSurprise below).
//
// Two DIFFERENT kinds of empty, and conflating them is the whole trap:
//  - inside the GATED window (<= +45d, the buckets A-LIST actually keys on) a run of >5 empty
//    weekdays is a SOURCE FAILURE and throws. Silence there would read as a catalyst desert.
//  - past +45d the feed simply runs out of scheduled dates (verified 2026-09-23: +55d still
//    returns 43-516 rows/day, +58d returns errorMessage "No record found"). That is a HORIZON
//    END, not a failure — stop and report where it ended instead of faking coverage.
const GATED_DAYS = 45;
async function nasdaqCalendar(fromDays, toDays) {
  const out = {}; let total = 0, emptyWeekdays = 0, reqs = 0, horizonEnd = null;
  for (let d = fromDays; d < toDays; d++) {
    const dt = day(d); const wd = dt.getUTCDay();
    if (wd === 0 || wd === 6) continue;
    const a = iso(dt);
    let rows = [];
    try {
      const j = await (await withTimeout(`https://api.nasdaq.com/api/calendar/earnings?date=${a}`, NUA)).json();
      rows = j?.data?.rows || [];
    } catch { rows = []; }
    reqs++;
    if (!rows.length) {
      emptyWeekdays++;
      if (emptyWeekdays > 5) {
        if (d <= GATED_DAYS) throw new Error(`FEED FAILURE: nasdaq calendar returned 0 rows on >5 consecutive weekdays INSIDE the gated window (ended ${a})`);
        horizonEnd = a; break;                       // far tail: the schedule just runs out
      }
    } else emptyWeekdays = 0;
    total += rows.length;
    for (const r of rows) {
      const sym = (r.symbol || "").trim().toUpperCase(); if (!sym) continue;
      const est = parseFloat(String(r.epsForecast || "").replace(/[$,()]/g, "")) || null;
      const p = out[sym];
      if (!p || a < p.date) out[sym] = { date: a, hour: r.time || null, est, act: null, mcap: r.marketCap || null };
    }
    await new Promise(r => setTimeout(r, 120));
  }
  if (!total) throw new Error("FEED FAILURE: nasdaq calendar returned 0 rows across the entire window");
  return { earn: out, total, truncated: 0, symbols: Object.keys(out).length,
           source: `nasdaq (${reqs} day-requests${horizonEnd ? `, horizon ended ${horizonEnd}` : ""})` };
}

// Per-ticker reported-quarter surprise. Nasdaq's calendar has no epsActual, so this is how a
// PEAD candidate gets its actual-vs-consensus. Same GAAP-vs-non-GAAP caveat as every free
// surprise feed — see trap-earnings-beat-is-fake; the DD still has to read the release.
export async function nasdaqSurprise(ticker) {
  try {
    const j = await (await withTimeout(`https://api.nasdaq.com/api/company/${ticker}/earnings-surprise`, NUA)).json();
    const rows = j?.data?.earningsSurpriseTable?.rows || [];
    return rows.map(r => ({
      qtr: r.fiscalQtrEnd, reported: r.dateReported,
      eps: r.eps == null ? null : +r.eps,
      est: r.consensusForecast == null ? null : +r.consensusForecast,
      surpPct: r.percentageSurprise == null ? null : +r.percentageSurprise,
    }));
  } catch { return null; }
}

export async function calendar(fromDays, toDays, step = 7) {
  try {
    const c = await finnhubCalendar(fromDays, toDays, step);
    if (c.symbols > 0) return c;
    console.error("WARN finnhub calendar returned 0 symbols — falling back to Nasdaq");
  } catch (e) {
    console.error(`WARN finnhub calendar unreachable (${String(e).slice(0, 60)}) — falling back to Nasdaq`);
  }
  return await nasdaqCalendar(fromDays, toDays);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const c = await calendar(-8, 75);
  console.log(`calendar [${c.source}]: ${c.total} rows, ${c.symbols} symbols, chunks-truncated=${c.truncated}`);
  const days = s => Math.round((new Date(c.earn[s].date) - TODAY) / 86400e3);
  const buckets = { "<=7d": 0, "8-14d": 0, "15-30d": 0, "31-45d": 0, ">45d": 0 };
  for (const s in c.earn) { const d = days(s);
    if (d < 0) continue;
    buckets[d <= 7 ? "<=7d" : d <= 14 ? "8-14d" : d <= 30 ? "15-30d" : d <= 45 ? "31-45d" : ">45d"]++; }
  console.log("market-wide forward earnings distribution: " + JSON.stringify(buckets));
  const { writeFileSync } = await import("fs");
  writeFileSync("/tmp/earn_cal.json", JSON.stringify(c.earn));
  console.log("wrote /tmp/earn_cal.json");
}
