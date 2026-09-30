#!/usr/bin/env node
// I2 universe gate + I4 catalyst cross-reference for /stock-scan insider mode.
// Reads the cluster JSON on stdin (last line of insider_clusters.mjs output).
//
// NO CAP DISCRIMINATION (Jiv's standing all-cap rule) — the only hard universe drops are
// anti-manipulation/liquidity. The catalyst cross-reference is the LOAD-BEARING gate:
// backtest says cluster-alone underperforms, cluster+catalyst = +11% median (n=39).
import { execSync } from "child_process";
const YUA = { "User-Agent": "Mozilla/5.0 stock-scan research" };
const UA = { "User-Agent": "stock-scan research jivtuban14@gmail.com" };
const FIN = execSync("security find-generic-password -s stock-scan-finnhub -a api -w").toString().trim();

const clusters = JSON.parse(process.argv[2]);
const TODAY = new Date(process.env.ASOF || "2026-09-22");
const iso = d => d.toISOString().slice(0, 10);
const plus = n => iso(new Date(TODAY.getTime() + n * 86400e3));

// --- earnings calendar: the dated-catalyst source ---
const { calendar } = await import("./earnings_cal.mjs");
const cal = await calendar(-25, 75);
const earn = cal.earn;
console.log(`earnings calendar: ${cal.total} rows / ${cal.symbols} symbols, chunks-truncated=${cal.truncated}`);

// --- universe metrics (12-18mo price history too: "% off 52w high" is NOT a drawdown) ---
async function meta(t) {
  try {
    const p2 = Math.floor(TODAY.getTime() / 1000), p1 = p2 - 550 * 86400;
    const j = await (await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${t}?period1=${p1}&period2=${p2}&interval=1d&events=split`, { headers: YUA })).json();
    const r = j.chart?.result?.[0]; if (!r) return null;
    const m = r.meta, q = r.indicators.quote[0];
    const cl = [], vol = [];
    for (let i = 0; i < r.timestamp.length; i++) if (q.close[i] != null) { cl.push(q.close[i]); vol.push(q.volume[i] || 0); }
    if (cl.length < 30) return null;
    const px = m.regularMarketPrice;
    const avgVol = vol.slice(-30).reduce((a, b) => a + b, 0) / Math.min(30, vol.length);
    const sma20 = cl.slice(-20).reduce((a, b) => a + b, 0) / 20;
    const sma50 = cl.slice(-50).reduce((a, b) => a + b, 0) / Math.min(50, cl.length);
    const lo18 = Math.min(...cl);                        // 18-month low — the parabola-unwind detector
    const px18 = cl[0];
    const splits = Object.keys(r.events?.splits || {}).length;
    return {
      px: +px.toFixed(2), fromHi: +(100 * (px / m.fiftyTwoWeekHigh - 1)).toFixed(0),
      dVolM: +(px * avgVol / 1e6).toFixed(1), vsSMA20: +(100 * (px / sma20 - 1)).toFixed(1),
      vsSMA50: +(100 * (px / sma50 - 1)).toFixed(1),
      ret18m: +(100 * (px / px18 - 1)).toFixed(0), offLo18: +(100 * (px / lo18 - 1)).toFixed(0),
      splits, lastTick: new Date(m.regularMarketTime * 1000).toISOString().slice(0, 10),
    };
  } catch { return null; }
}

const rows = [];
for (let i = 0; i < clusters.length; i += 12) {
  const chunk = clusters.slice(i, i + 12);
  (await Promise.all(chunk.map(c => meta(c.ticker)))).forEach((m, j) => { if (m) rows.push({ ...chunk[j], ...m }); });
}
console.log(`universe data: ${rows.length}/${clusters.length} resolved`);

// Hard drops: illiquid / OTC-thin / blown-off. NOT size.
const tradeable = rows.filter(r => r.dVolM >= 2 && r.vsSMA20 <= 25);
const dropped = rows.filter(r => !(r.dVolM >= 2 && r.vsSMA20 <= 25));
console.log(`tradeable(>=$2M/day, not blown-off): ${tradeable.length} | dropped: ${dropped.length} (illiquid: ${rows.filter(r=>r.dVolM<2).length}, blown-off: ${rows.filter(r=>r.vsSMA20>25).length})`);

const withCat = tradeable.map(r => {
  const e = earn[r.ticker];
  const days = e ? Math.round((new Date(e.date) - TODAY) / 86400e3) : null;
  return { ...r, earnDate: e?.date || null, earnDays: days, earnReported: e?.act != null,
           aboveBase: r.px && clusters.find(c=>c.ticker===r.ticker)?.avgBuy ? +(100*(r.px/clusters.find(c=>c.ticker===r.ticker).avgBuy-1)).toFixed(1) : null };
});
const dated14 = withCat.filter(r => r.earnDays != null && r.earnDays >= 0 && r.earnDays <= 14);
const dated32 = withCat.filter(r => r.earnDays != null && r.earnDays > 14 && r.earnDays <= 45);

// PEAD bucket. It used to gate on `earnReported` (= calendar's epsActual != null), which is
// ALWAYS false on the Nasdaq fallback because that calendar carries no actual EPS. The bucket
// returned a confident 0 while 11 cluster names had already reported and were absent from every
// printed bucket (2026-09-23). Gate on the DATE, then fetch actual-vs-consensus per ticker.
// See trap-a-signal-that-cannot-fire instance 13.
const reportedNames = withCat.filter(r => r.earnDays != null && r.earnDays < 0);
const { nasdaqSurprise } = await import("./earnings_cal.mjs");
const YUA2 = { "User-Agent": "Mozilla/5.0 stock-scan research" };
async function reaction(t, earnDate) {                  // did the market REWARD the print?
  try {
    const p2 = Math.floor(TODAY.getTime() / 1000), p1 = p2 - 40 * 86400;
    const j = await (await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${t}?period1=${p1}&period2=${p2}&interval=1d`, { headers: YUA2 })).json();
    const r = j.chart?.result?.[0]; if (!r) return null;
    const ts = r.timestamp, cl = r.indicators.quote[0].close;
    const ed = Math.floor(new Date(earnDate + "T00:00:00Z").getTime() / 1000);
    let pre = null; for (let i = 0; i < ts.length; i++) if (ts[i] < ed && cl[i] != null) pre = cl[i];
    const now = cl.filter(x => x != null).pop();
    return pre == null ? null : +(100 * (now / pre - 1)).toFixed(1);
  } catch { return null; }
}
const recent = [];
for (const r of reportedNames) {
  const [sp, rx] = await Promise.all([nasdaqSurprise(r.ticker), reaction(r.ticker, r.earnDate)]);
  const q = (sp || [])[0];
  recent.push({ ...r, surpPct: q?.surpPct ?? null, repDate: q?.reported ?? null, reactionPct: rx,
    // A beat the market SOLD has inverted/dead drift — the GILT/INOD shape. Kept but labelled,
    // because a silent drop is how a gate stops being falsifiable.
    pead: q?.surpPct > 0 && rx > 0 ? "BEAT+REWARDED" : q?.surpPct > 0 ? "beat-but-SOLD" : "no beat" });
  await new Promise(z => setTimeout(z, 200));
}
console.log(`\nREPORTED-IN-WINDOW: ${reportedNames.length} cluster names already printed | live PEAD (beat AND rewarded): ${recent.filter(r => r.pead === "BEAT+REWARDED").length}`);
console.log("reported detail: " + JSON.stringify(recent.map(r => ({ t: r.ticker, d: r.earnDate, surp: r.surpPct, react: r.reactionPct, v: r.pead, n: r.nBuyers, buyM: r.buyM, vol: r.dVolM }))));
console.log(`\nCATALYST CROSS-REF: earnings<=14d: ${dated14.length} | 15-45d: ${dated32.length} | already reported: ${recent.length}`);
console.log("<=14d: " + JSON.stringify(dated14));
console.log("15-45d: " + JSON.stringify(dated32.map(r=>({t:r.ticker,d:r.earnDate,n:r.nBuyers,buyM:r.buyM,px:r.px,ab:r.aboveBase,fromHi:r.fromHi,r18:r.ret18m,vol:r.dVolM,cs:r.csuite}))));
console.log("PEAD (beat AND rewarded only): " + JSON.stringify(recent.filter(r=>r.pead==="BEAT+REWARDED").map(r=>({t:r.ticker,d:r.earnDate,surp:r.surpPct,react:r.reactionPct,n:r.nBuyers,buyM:r.buyM,px:r.px,ab:r.aboveBase,fromHi:r.fromHi,r18:r.ret18m,vol:r.dVolM,cs:r.csuite}))));
console.log("\nNO-CATALYST tradeable (top 20 by buyers/$): " + JSON.stringify(withCat.filter(r=>r.earnDays==null||r.earnDays>45).sort((a,b)=>b.nBuyers-a.nBuyers||b.buyM-a.buyM).slice(0,20).map(r=>({t:r.ticker,n:r.nBuyers,buyM:r.buyM,px:r.px,ab:r.aboveBase,fromHi:r.fromHi,r18:r.ret18m,vol:r.dVolM,cs:r.csuite,e:r.earnDate}))));
