"""Self-contained (offline) HTML dashboard for the funding-carry backtest."""

from __future__ import annotations

import json

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Delta-Neutral Funding Carry — 8 majors</title>
<style>
  :root{--bg:#0b0e14;--panel:#141922;--ink:#e6edf3;--mut:#8b98a9;--line:#232b38;
        --pos:#3fb950;--neg:#f85149;--acc:#58a6ff;--warn:#d29922}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  .wrap{max-width:1080px;margin:0 auto;padding:32px 20px 64px}
  h1{font-size:22px;margin:0 0 4px} h2{font-size:15px;margin:26px 0 12px;color:var(--mut);
     text-transform:uppercase;letter-spacing:.06em;font-weight:600}
  .sub{color:var(--mut);margin:0 0 18px;font-size:13px}
  .verdict{padding:14px 16px;border-radius:10px;border:1px solid var(--line);
           background:var(--panel);margin:0 0 8px;font-size:15px} .verdict b{color:var(--warn)}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
  .card .k{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.05em}
  .card .v{font-size:24px;font-weight:700;margin-top:4px}
  .pos{color:var(--pos)} .neg{color:var(--neg)} .acc{color:var(--acc)}
  canvas{width:100%;height:300px;background:var(--panel);border:1px solid var(--line);border-radius:10px}
  table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);
        border-radius:10px;overflow:hidden;font-size:13px}
  th,td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--line)}
  th:first-child,td:first-child{text-align:left}
  th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase}
  tr:last-child td{border-bottom:none}
  .foot{color:var(--mut);font-size:12px;margin-top:24px;line-height:1.7}
  .lg{display:flex;gap:16px;font-size:12px;color:var(--mut);margin:6px 2px 0}
  .lg span::before{content:"■ ";}
</style></head><body><div class="wrap">
  <h1>Delta-Neutral Funding Carry <span class="acc">·</span> 8 large-cap majors</h1>
  <p class="sub" id="sub"></p>
  <div class="verdict" id="verdict"></div>

  <h2>Portfolio (equal-weight)</h2>
  <div class="cards" id="cards"></div>

  <h2>Cumulative carry — % of notional (BTC)</h2>
  <canvas id="eq" width="1040" height="300"></canvas>
  <div class="lg"><span style="color:#8b98a9">gross (funding only)</span>
    <span style="color:#3fb950">net always-on</span>
    <span style="color:#d29922">net regime-gated</span>
    <span style="color:#58a6ff">net funding-timed</span></div>

  <h2>Maker vs taker execution — how much of the deadness is the fee tax?</h2>
  <table id="costs"><thead><tr><th>Execution</th><th>Round-trip cost</th>
    <th>Net APR · always-on</th><th>Net APR · gated</th></tr></thead><tbody></tbody></table>

  <h2>Regime-gate enter-threshold sweep — does switching on selectively beat always-on?</h2>
  <table id="sweep"><thead><tr><th>Enter threshold (bps/8h)</th><th>Portfolio net APR</th>
    <th>Held % of time</th><th>Avg toggles</th></tr></thead><tbody></tbody></table>

  <h2>Per-symbol</h2>
  <table id="tbl"><thead><tr><th>Symbol</th><th>Intervals</th><th>Funding +%</th>
    <th>Mean bps/8h</th><th>Gross APR</th><th>Net APR (always-on)</th>
    <th>Net APR (timed)</th><th>Timed toggles</th><th>Max neg streak</th></tr></thead><tbody></tbody></table>

  <div class="foot" id="foot"></div>
</div>
<script>
const R = __DATA__;
const f=(x)=>(x>=0?"+":"")+(x*100).toFixed(2)+"%";
const cls=x=>x>0?"pos":(x<0?"neg":"");
const P=R.portfolio, C=R.config;

document.getElementById("sub").innerHTML =
  `Long spot + short perp, harvest funding. Since ${C.since}. `+
  `Costs: spot ${(C.spot_fee_pct*100).toFixed(2)}%/side + perp ${(C.perp_fee_pct*100).toFixed(2)}%/side `+
  `= ${(C.round_trip_pct*100).toFixed(2)}% round-trip. Funding-timed holds only when the last settled rate ≥ ${C.cond_threshold}.`;

const on=P.net_APR_always, gt=P.net_APR_gated;
const best = Math.max(on, gt);
const edge = best>0.03 ? "a REAL positive carry" : (best>0 ? "a THIN positive carry" : "NEGATIVE net carry");
document.getElementById("verdict").innerHTML =
  `Verdict: best net APR is <b>${f(best)}</b> (${gt>on?"regime-gated":"always-on"}) — ${edge}. `+
  `Gross funding ${f(P.gross_APR)} APR; positive ${(P.pct_positive*100).toFixed(0)}% of intervals (mean ${P.mean_funding_bps.toFixed(3)} bps/8h). `+
  `The regime gate ${gt>on?"BEAT":"did NOT beat"} always-on (${f(gt)} vs ${f(on)}), holding only ${(P.gated_held_frac*100).toFixed(0)}% of the time — `+
  `${gt>on?"selective switch-on adds value.":"in this compressed regime there wasn't enough fuel to justify turning it on."}`;

const cards=[["Gross APR",f(P.gross_APR),cls(P.gross_APR)],
  ["Net · always-on",f(P.net_APR_always),cls(P.net_APR_always)],
  ["Net · regime-gated",f(P.net_APR_gated),cls(P.net_APR_gated)],
  ["Gate held %",(P.gated_held_frac*100).toFixed(0)+"%",""],
  ["Funding positive",(P.pct_positive*100).toFixed(0)+"%",cls(P.pct_positive-0.5)],
  ["Mean funding",P.mean_funding_bps.toFixed(3)+" bps/8h",cls(P.mean_funding_bps)]];
document.getElementById("cards").innerHTML = cards.map(c=>
  `<div class="card"><div class="k">${c[0]}</div><div class="v ${c[2]}">${c[1]}</div></div>`).join("");

const tb=document.querySelector("#tbl tbody");
Object.entries(R.per_symbol).forEach(([s,r])=> tb.insertAdjacentHTML("beforeend",
  `<tr><td><b>${s}</b></td><td>${r.n}</td><td>${(r.pct_positive*100).toFixed(0)}%</td>`+
  `<td>${r.mean_funding_bps.toFixed(3)}</td><td class="${cls(r.gross_APR)}">${f(r.gross_APR)}</td>`+
  `<td class="${cls(r.net_APR_always)}">${f(r.net_APR_always)}</td>`+
  `<td class="${cls(r.net_APR_timed)}">${f(r.net_APR_timed)}</td>`+
  `<td>${r.timed_toggles}</td><td>${r.max_neg_streak}</td></tr>`));

// maker vs taker table
const cb=document.querySelector("#costs tbody");
(R.cost_scenarios||[]).forEach(c=> cb.insertAdjacentHTML("beforeend",
  `<tr><td>${c.scenario}</td><td>${(c.round_trip*100).toFixed(2)}%</td>`+
  `<td class="${cls(c.net_always)}">${f(c.net_always)}</td>`+
  `<td class="${cls(c.net_gated)}">${f(c.net_gated)}</td></tr>`));

// gate sweep table
const sw=document.querySelector("#sweep tbody");
(R.gate_sweep||[]).forEach(r=> sw.insertAdjacentHTML("beforeend",
  `<tr><td>${r.enter_bps.toFixed(2)}</td><td class="${cls(r.net_APR)}">${f(r.net_APR)}</td>`+
  `<td>${(r.held_frac*100).toFixed(0)}%</td><td>${r.avg_toggles}</td></tr>`));

// cumulative carry curve for BTC (or first symbol)
const key = R.curves.BTC ? "BTC" : Object.keys(R.curves)[0];
const cur = R.curves[key];
const cv=document.getElementById("eq"), ctx=cv.getContext("2d"), W=cv.width,H=cv.height,pad=42;
const series=[["_gross_cum","#8b98a9"],["_always_cum_net","#3fb950"],
  ["_gated_cum_net","#d29922"],["_timed_cum_net","#58a6ff"]];
const all=series.flatMap(([k])=>cur[k]);
if(all.length){
  const ymin=Math.min(...all,0),ymax=Math.max(...all,0),xr=Math.max(1,cur._gross_cum.length-1);
  const sx=i=>pad+(i/xr)*(W-2*pad), sy=v=>H-pad-((v-ymin)/((ymax-ymin)||1))*(H-2*pad);
  ctx.strokeStyle="#2b3342";ctx.beginPath();ctx.moveTo(pad,sy(0));ctx.lineTo(W-pad,sy(0));ctx.stroke();
  ctx.fillStyle="#8b98a9";ctx.font="11px monospace";
  ctx.fillText((ymax*100).toFixed(1)+"%",4,sy(ymax)+8);ctx.fillText((ymin*100).toFixed(1)+"%",4,sy(ymin)-2);
  ctx.fillText(key,W-pad-30,18);
  series.forEach(([k,col])=>{const d=cur[k];ctx.beginPath();ctx.moveTo(sx(0),sy(d[0]));
    d.forEach((v,i)=>ctx.lineTo(sx(i),sy(v)));ctx.strokeStyle=col;ctx.lineWidth=2;ctx.stroke();});
} else { ctx.fillStyle="#8b98a9";ctx.fillText("no data",pad,H/2); }

document.getElementById("foot").innerHTML =
  `<b>Model:</b> first-order — the two price legs (long spot / short perp) cancel, so per-interval return ≈ the funding rate; `+
  `short perp receives positive funding, pays negative. Basis (spot–perp spread) convergence is OMITTED (small on majors, funding pins it) — a real caveat, mild optimism. `+
  `Settled rates via ccxt fetch_funding_rate_history (not the estimated endpoint). Always-on books the round-trip cost up front (conservative). `+
  `<br><b>Guardrail:</b> research spike — nothing approved, no live execution. Ignores collateral-separation / leg-failure / borrow, the real-world killers the strategy-edges report flagged.`;
</script></body></html>
"""


def render_html(report: dict, path: str) -> None:
    with open(path, "w") as fh:
        fh.write(_TEMPLATE.replace("__DATA__", json.dumps(report)))
