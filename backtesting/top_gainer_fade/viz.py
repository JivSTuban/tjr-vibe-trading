"""Render a self-contained (offline, no CDN) HTML dashboard comparing FADE vs RIDE.

Report shape: {universe, decision_hour, min_gain, sides:{short:{...}, long:{...}}}.
Each side block has headline, gross, scenarios, walk_forward,
per_instrument, curve. Two equity curves drawn on <canvas> with vanilla JS.
"""

from __future__ import annotations

import json

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Top-Gainer: Fade vs Ride — Universe A backtest</title>
<style>
  :root{--bg:#0b0e14;--panel:#141922;--ink:#e6edf3;--mut:#8b98a9;--line:#232b38;
        --pos:#3fb950;--neg:#f85149;--acc:#58a6ff;--warn:#d29922}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  .wrap{max-width:1160px;margin:0 auto;padding:32px 20px 64px}
  h1{font-size:22px;margin:0 0 4px} h2{font-size:15px;margin:26px 0 12px;color:var(--mut);
     text-transform:uppercase;letter-spacing:.06em;font-weight:600}
  h3{font-size:14px;margin:0 0 10px} .sub{color:var(--mut);margin:0 0 18px;font-size:13px}
  .verdict{padding:14px 16px;border-radius:10px;border:1px solid var(--line);
           background:var(--panel);margin:0 0 8px;font-size:15px}
  .verdict b{color:var(--warn)}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
  @media(max-width:820px){.grid2{grid-template-columns:1fr}}
  .col{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
  .col.short{border-top:3px solid var(--neg)} .col.long{border-top:3px solid var(--pos)}
  .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}
  .card{background:#0f141c;border:1px solid var(--line);border-radius:9px;padding:10px}
  .card .k{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
  .card .v{font-size:20px;font-weight:700;margin-top:3px}
  .pos{color:var(--pos)} .neg{color:var(--neg)} .acc{color:var(--acc)}
  canvas{width:100%;height:200px;background:#0f141c;border:1px solid var(--line);
         border-radius:9px;margin-bottom:12px}
  table{width:100%;border-collapse:collapse;font-size:12.5px;margin-bottom:6px}
  th,td{padding:6px 8px;text-align:right;border-bottom:1px solid var(--line)}
  th:first-child,td:first-child{text-align:left}
  th{color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase}
  tr:last-child td{border-bottom:none}
  .mono{font-family:ui-monospace,Menlo,monospace}
  .foot{color:var(--mut);font-size:12px;margin-top:24px;line-height:1.7}
</style></head><body><div class="wrap">
  <h1>Top-Gainer of the Day <span class="acc">·</span> Fade vs Ride</h1>
  <p class="sub" id="sub"></p>
  <div class="verdict" id="verdict"></div>
  <div class="grid2" id="cols"></div>
  <div class="foot" id="foot"></div>
</div>
<script>
const R = __DATA__;
const f=(x,d=4)=>(x>=0?"+":"")+Number(x).toFixed(d);
const pct=x=>(x*100).toFixed(1)+"%";
const cls=x=>x>0?"pos":(x<0?"neg":"");

document.getElementById("sub").innerHTML =
  `Each day, take the single biggest gainer among ${R.universe.length} large-cap perps `+
  `(${R.universe.join(", ")}) that is up ≥${pct(R.min_gain)} at `+
  `${String(R.decision_hour).padStart(2,"0")}:00 UTC · exit same-day close. `+
  `Cards + curve show the maker-entry execution; the ladder in each column steps taker→maker.`;

const s=R.sides.short.headline, l=R.sides.long.headline;
const sg=R.sides.short.gross, lg=R.sides.long.gross;
const winner = l.avg_R>s.avg_R ? "RIDE (long)" : "FADE (short)";
const both = (s.avg_R<0 && l.avg_R<0);
document.getElementById("verdict").innerHTML = both
  ? `Verdict: <b>both sides lose net</b> after costs (fade ${f(s.avg_R)}R, ride ${f(l.avg_R)}R). `+
    `Continuation is visible in GROSS (long gross ${f(lg.avg_R)}R vs short gross ${f(sg.avg_R)}R) `+
    `but same-day fees eat it. The daily top-gainer is not a clean same-day tradable on either side.`
  : `Verdict: <b>${winner}</b> is the better side — net avg ride ${f(l.avg_R)}R vs fade ${f(s.avg_R)}R. `+
    `Gross confirms direction: long ${f(lg.avg_R)}R vs short ${f(sg.avg_R)}R.`;

function col(key,label){
  const B=R.sides[key], h=B.headline, g=B.gross;
  const cards=[["Trades",h.trades,""],["Win rate",pct(h.win_rate),cls(h.win_rate-0.5)],
    ["Gross avg R",f(g.avg_R),cls(g.avg_R)],["Net avg R",f(h.avg_R),cls(h.avg_R)],
    ["Profit factor",h.profit_factor,cls(h.profit_factor-1)],["Net total R",f(h.net_return_R,1),cls(h.net_return_R)]];
  const scen=B.scenarios.map(([n,m])=>`<tr><td>${n}</td><td class="${cls(m.avg_R)}">${f(m.avg_R)}</td>`+
    `<td class="${cls(m.net_return_R)}">${f(m.net_return_R,1)}</td></tr>`).join("");
  const wf=B.walk_forward.filter(w=>w.n).map(w=>`<tr><td class="mono">${w.start}→${w.end}</td>`+
    `<td>${w.n}</td><td>${pct(w.win_rate)}</td><td class="${cls(w.net_avg_R)}">${f(w.net_avg_R)}</td></tr>`).join("");
  const inst=B.per_instrument.map(r=>`<tr><td><b>${r.symbol}</b></td><td>${r.faded_days}</td>`+
    `<td>${pct(r.win_rate)}</td><td class="${cls(r.net_avg_R)}">${f(r.net_avg_R)}</td>`+
    `<td class="${cls(r.net_total_R)}">${f(r.net_total_R,1)}</td></tr>`).join("");
  return `<div class="col ${key}"><h3>${label}</h3>
    <div class="cards">${cards.map(c=>`<div class="card"><div class="k">${c[0]}</div>
      <div class="v ${c[2]}">${c[1]}</div></div>`).join("")}</div>
    <canvas id="eq_${key}" width="560" height="200"></canvas>
    <table><thead><tr><th>Scenario</th><th>Avg R</th><th>Total R</th></tr></thead><tbody>${scen}</tbody></table>
    <table><thead><tr><th>Walk-forward fold</th><th>n</th><th>Win%</th><th>Net R</th></tr></thead><tbody>${wf}</tbody></table>
    <table><thead><tr><th>Coin</th><th>Days</th><th>Win%</th><th>Net avg R</th><th>Net total R</th></tr></thead><tbody>${inst}</tbody></table>
  </div>`;
}
document.getElementById("cols").innerHTML = col("short","FADE — short the gainer") + col("long","RIDE — long the gainer");

function drawEq(key){
  const cv=document.getElementById("eq_"+key), ctx=cv.getContext("2d");
  const W=cv.width,H=cv.height,pad=34, pts=R.sides[key].curve.map((c,i)=>({x:i,y:c.cum_R}));
  if(!pts.length){ctx.fillStyle="#8b98a9";ctx.fillText("no trades",pad,H/2);return;}
  const ys=pts.map(p=>p.y).concat([0]);
  const ymin=Math.min(...ys),ymax=Math.max(...ys),xr=Math.max(1,pts.length-1);
  const sx=i=>pad+(i/xr)*(W-2*pad), sy=v=>H-pad-((v-ymin)/((ymax-ymin)||1))*(H-2*pad);
  ctx.strokeStyle="#2b3342";ctx.beginPath();ctx.moveTo(pad,sy(0));ctx.lineTo(W-pad,sy(0));ctx.stroke();
  ctx.fillStyle="#8b98a9";ctx.font="10px monospace";
  ctx.fillText(ymax.toFixed(0)+"R",3,sy(ymax)+8);ctx.fillText(ymin.toFixed(0)+"R",3,sy(ymin)-2);ctx.fillText("0",3,sy(0)+3);
  const last=pts[pts.length-1].y, col=last>=0?"#3fb950":"#f85149";
  ctx.beginPath();ctx.moveTo(sx(0),sy(pts[0].y));pts.forEach(p=>ctx.lineTo(sx(p.x),sy(p.y)));
  ctx.lineTo(sx(pts.length-1),sy(0));ctx.lineTo(sx(0),sy(0));ctx.closePath();
  ctx.fillStyle=last>=0?"rgba(63,185,80,.12)":"rgba(248,81,73,.12)";ctx.fill();
  ctx.beginPath();ctx.moveTo(sx(0),sy(pts[0].y));pts.forEach(p=>ctx.lineTo(sx(p.x),sy(p.y)));
  ctx.strokeStyle=col;ctx.lineWidth=2;ctx.stroke();
}
drawEq("short");drawEq("long");

const c=R.sides.short.config;
document.getElementById("foot").innerHTML =
  `<b>Method:</b> look-ahead-safe (rank uses only bars ≤ decision time; resolution starts the next bar). `+
  `SHORT stop = intraday high×(1+${pct(c.sl_buffer_pct)}) (resistance); LONG stop = intraday low×(1−${pct(c.sl_buffer_pct)}) (support); `+
  `min-stop ${pct(c.min_stop_pct)}. Exec ladder: taker = ${(c.taker_fee_pct*100).toFixed(3)}% fee + ${(c.slippage_pct*100).toFixed(3)}% slip/side; `+
  `MAKER entry = ${(c.maker_fee_pct*100).toFixed(3)}% fee, no slip (resting limit, optimistic: assumes fill). Exit always taker (close/stop = market). `+
  `Funding = SCENARIO (cache is OHLCV-only): market rate per 8h boundary (00/08/16 UTC); +rate ⇒ short earns, long pays. `+
  `<br><b>Guardrail:</b> research spike only — nothing approved, no live execution.`;
</script></body></html>
"""


def render_html(report: dict, path: str) -> None:
    html = _TEMPLATE.replace("__DATA__", json.dumps(report))
    with open(path, "w") as f:
        f.write(html)
