"""Offline HTML dashboard for the swing-bounce backtest. No network."""
from __future__ import annotations

import os


def _cells_table(cells: dict) -> str:
    rows = []
    gated = sorted(((k, v) for k, v in cells.items() if k.startswith("gated")),
                   key=lambda kv: kv[1]["expectancy_R"], reverse=True)
    for k, v in gated:
        _, thr, t, s, h = k.split("|")
        rows.append(f"<tr><td>{thr[3:]}</td><td>{t[1:]}</td><td>{s[1:]}</td><td>{h[1:]}</td>"
                    f"<td>{v['n']}</td><td>{v['hit_rate']:.0%}</td>"
                    f"<td class='{'pos' if v['expectancy_R'] > 0 else 'neg'}'>{v['expectancy_R']:+.3f}</td></tr>")
    return "".join(rows)


def render_dashboard(results: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    h = results["headline_cell"]["gated"]
    surv = results["survivorship"]
    con = results["concentration"]
    ne = results["n_events"]
    html = f"""<!doctype html><meta charset=utf-8><title>Swing Bounce Backtest</title>
<style>body{{font:14px system-ui;margin:2rem;max-width:900px}}
.verdict{{background:#3a1414;color:#ffd;padding:1rem;border-radius:8px;border-left:5px solid #c33}}
table{{border-collapse:collapse;margin:1rem 0;width:100%}}td,th{{border:1px solid #ccc;padding:4px 8px;text-align:right}}
th{{background:#f0f0f0}}.pos{{color:#0a0}}.neg{{color:#c00}}.card{{display:inline-block;border:1px solid #ddd;border-radius:8px;padding:.6rem 1rem;margin:.3rem}}</style>
<h1>Swing Bounce Backtest — beaten-down + financially-alive</h1>
<div class=verdict><b>VERDICT: edge NOT proven — do not automate.</b> The intuitive +20%/-10%/20d cell
loses ({h['expectancy_R']:+.3f}R gated); the quality gate hurts on average; positives are
survivor-biased, concentration-dominated, negative-R:R. Keep swing mode discretionary only.</div>
<div>
<span class=card>events: {ne['gated']} gated / {ne['ungated']} ungated</span>
<span class=card>coverage: {results['coverage_pct']}%</span>
<span class=card>headline gated: n={h['n']} · hit {h['hit_rate']:.0%} · <b class="{'pos' if h['expectancy_R']>0 else 'neg'}">{h['expectancy_R']:+.3f}R</b></span>
<span class=card>survivorship: {surv['n_truncated']} truncated · stressed {surv['stressed']['expectancy_R']:+.3f}R</span>
<span class=card>concentration: {con['top_ticker']} {con['top_ticker_share']:.0%} of P&L</span>
</div>
<h2>Sweep surface — gated cells (sorted by expectancy_R)</h2>
<table><tr><th>drop×high</th><th>target</th><th>stop</th><th>horizon</th><th>n</th><th>hit</th><th>exp&nbsp;R</th></tr>
{_cells_table(results['cells'])}</table>
<p style="color:#666">Green = positive expectancy after 15bps/side costs. Positives cluster at long-horizon/wide-stop
(low reward:risk) — read FINDINGS.md before trusting any cell. SPY forward baseline: {results['spy_benchmark']}.</p>
"""
    p = os.path.join(out_dir, "dashboard.html")
    with open(p, "w") as f:
        f.write(html)
    return p
