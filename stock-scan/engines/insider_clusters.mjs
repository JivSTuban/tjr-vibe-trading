#!/usr/bin/env node
// Form-4 CLUSTER engine for /stock-scan insider mode.
//
// WHY the raw /screener and not /latest-cluster-buys: the aggregated openinsider feeds
// fail SILENTLY (HTTP 200 + an empty table), which reads as "a quiet market" instead of
// "the source is down". Building clusters from raw Form-4 rows also structurally kills
// the double-count bug the aggregated nBuyers column has (it over-reports distinct buyers).
// Standing rule: zero rows = SOURCE FAILURE, never a quiet market. See memory
// openinsider-screener-rebuild + trap-openinsider-filing-vs-trade-date.
const UA = { "User-Agent": "stock-scan research jivtuban14@gmail.com" };

const scr = (xp, fd, cnt = 5000) =>
  `http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=${fd}&fdr=&td=0&tdr=&fdlyl=&fdlyh=`
  + `&daysago=&${xp}=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=`
  + `&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=${cnt}&page=1`;

// Parse raw Form-4 rows. Anchors on the "P - Purchase"/"S - Sale" cell so tooltip junk
// in neighbouring cells cannot shift the field offsets.
export function parseRows(html) {
  const out = [];
  for (const r of html.match(/<tr[^>]*>[\s\S]*?<\/tr>/g) || []) {
    const ticker = (r.match(/href=['"]\/([A-Z][A-Z.]{0,5})['"]/) || [])[1];
    if (!ticker) continue;
    const cells = (r.match(/<td[^>]*>[\s\S]*?<\/td>/g) || []).map(c =>
      c.replace(/<[^>]+>/g, " ").replace(/&#?\w+;/g, " ").replace(/\|/g, "").replace(/\s+/g, " ").trim());
    const tt = cells.findIndex(c => /^[A-Z] - (Purchase|Sale)/.test(c));
    if (tt < 4) continue;
    const num = s => +(String(s || "").replace(/[$,+%\s]/g, "")) || 0;
    out.push({
      ticker,
      filingDate: (cells[1] || "").slice(0, 10),
      tradeDate: (cells[2] || "").slice(0, 10),   // trade date != filing date (the lag that lies)
      insider: (cells[tt - 2] || "").slice(0, 40),
      title: (cells[tt - 1] || "").slice(0, 34),
      kind: cells[tt].startsWith("P") ? "P" : "S",
      price: num(cells[tt + 1]),
      qty: Math.abs(num(cells[tt + 2])),
      value: Math.abs(num(cells[tt + 5])),
    });
  }
  return out;
}

async function feed(xp, fd) {
  const html = await (await fetch(scr(xp, fd), { headers: UA })).text();
  const rows = parseRows(html).filter(r => r.kind === (xp === "xp" ? "P" : "S"));
  if (!rows.length) throw new Error(`FEED FAILURE: ${xp} fd=${fd} returned 0 rows (HTTP ok but empty = source down, not a quiet market)`);
  return rows;
}

const [buys, sells] = await Promise.all([feed("xp", 30), feed("xs", 30)]);
console.log(`feed health: ${buys.length} buy rows / ${sells.length} sell rows`);

// Cluster = >=2 DISTINCT insider names buying open-market in the window.
const byT = {};
for (const b of buys) (byT[b.ticker] ||= []).push(b);
const sellByT = {};
for (const s of sells) sellByT[s.ticker] = (sellByT[s.ticker] || 0) + s.value;

const clusters = Object.entries(byT).map(([ticker, rs]) => {
  const names = new Set(rs.map(r => r.insider.toUpperCase()));
  const buyV = rs.reduce((a, r) => a + r.value, 0);
  const wAvg = rs.reduce((a, r) => a + r.price * r.qty, 0) / Math.max(1, rs.reduce((a, r) => a + r.qty, 0));
  const csuite = rs.some(r => /\b(CEO|CFO|COO|PRES|CHAIR|CHIEF)\b/i.test(r.title));
  const sellV = sellByT[ticker] || 0;
  return {
    ticker, nBuyers: names.size, buyM: +(buyV / 1e6).toFixed(2), sellM: +(sellV / 1e6).toFixed(2),
    netM: +((buyV - sellV) / 1e6).toFixed(2), avgBuy: +wAvg.toFixed(2), csuite,
    freshFiling: rs.map(r => r.filingDate).sort().pop(),
    freshTrade: rs.map(r => r.tradeDate).sort().pop(),
    titles: [...new Set(rs.map(r => r.title))].slice(0, 4).join("/"),
  };
}).filter(c => c.nBuyers >= 2);

// BLOCK-TRADE HANDOFF / exit-liquidity filter: buying that is dwarfed by same-window selling
// is not a signal. Reported, not silently dropped, so the kill is visible.
const handoffs = clusters.filter(c => c.sellM > c.buyM);
const clean = clusters.filter(c => c.sellM <= c.buyM).sort((a, b) => b.nBuyers - a.nBuyers || b.buyM - a.buyM);

console.log(`clusters(>=2 distinct buyers): ${clusters.length} | net-selling KILLED: ${handoffs.length} | clean: ${clean.length}`);
console.log("KILLED (buy vs sell $M): " + handoffs.sort((a,b)=>(b.sellM-b.buyM)-(a.sellM-a.buyM)).slice(0, 10).map(c => `${c.ticker} ${c.buyM}/-${c.sellM}`).join(", "));
console.log(JSON.stringify(clean));
