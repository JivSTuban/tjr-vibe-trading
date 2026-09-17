"""Self-contained (offline) HTML dashboard for the value+quality+drawdown backtest.

render_dashboard(results, out_dir) -> str
  - writes equity_curves.png (matplotlib, Agg backend — no display needed)
  - writes dashboard.html (offline, embeds the PNG as a data-URI)
  - returns the html path
"""

from __future__ import annotations

import base64
import io
import json
import os
from typing import Optional

# ---------------------------------------------------------------------------
# Matplotlib — Agg backend, no display required
# ---------------------------------------------------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


# ---------------------------------------------------------------------------
# Equity-curve PNG
# ---------------------------------------------------------------------------

def _equity_curve_png(monthly_returns: dict) -> bytes:
    """Build the three-series equity-curve chart; return PNG bytes."""
    fig, ax = plt.subplots(figsize=(10, 4), facecolor="#0b0e14")
    ax.set_facecolor("#141922")

    colors = {
        "strategy":  "#58a6ff",   # blue — strategy
        "cheap_only": "#d29922",  # gold — cheap only
        "spy":        "#3fb950",  # green — SPY
        "ew_universe": "#8b98a9", # grey — equal-weight universe
    }
    labels = {
        "strategy": "Strategy (value+quality+drop)",
        "cheap_only": "Cheap-only (value gate)",
        "spy": "SPY",
        "ew_universe": "Equal-weight universe",
    }

    for key in ("spy", "cheap_only", "ew_universe", "strategy"):
        rets = monthly_returns.get(key, {})
        if not rets:
            continue
        dates = sorted(rets.keys())
        cum = 1.0
        xs, ys = [], []
        for d in dates:
            cum *= (1.0 + rets[d])
            xs.append(d)
            ys.append((cum - 1.0) * 100.0)
        ax.plot(range(len(xs)), ys,
                color=colors[key], linewidth=1.8, label=labels[key])

    ax.axhline(0, color="#2b3342", linewidth=0.8)
    ax.set_title("Cumulative return — Strategy vs benchmarks", color="#e6edf3",
                 fontsize=12, pad=10)
    ax.set_ylabel("Return (%)", color="#8b98a9", fontsize=10)
    ax.tick_params(colors="#8b98a9", labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor("#232b38")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.set_xticks([])
    ax.legend(facecolor="#141922", edgecolor="#232b38", labelcolor="#e6edf3",
              fontsize=9, loc="upper left")

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# HTML template (f-string; data injected as inline JSON + base64 PNG)
# ---------------------------------------------------------------------------

_CSS = """
:root{--bg:#0b0e14;--panel:#141922;--ink:#e6edf3;--mut:#8b98a9;--line:#232b38;
      --pos:#3fb950;--neg:#f85149;--acc:#58a6ff;--warn:#d29922}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:13px;margin:28px 0 10px;color:var(--mut);text-transform:uppercase;
   letter-spacing:.06em;font-weight:600}
.sub{color:var(--mut);margin:0 0 18px;font-size:13px}
.verdict{padding:14px 16px;border-radius:10px;border:1px solid var(--line);
         background:var(--panel);margin:0 0 8px;font-size:14px;line-height:1.7}
.verdict b{color:var(--warn)}
.verdict .caveat{color:var(--neg);font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin-bottom:4px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:13px}
.card .k{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.card .v{font-size:22px;font-weight:700;margin-top:4px}
.pos{color:var(--pos)} .neg{color:var(--neg)} .acc{color:var(--acc)} .warn{color:var(--warn)}
img.chart{width:100%;border:1px solid var(--line);border-radius:10px;display:block}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);
      border-radius:10px;overflow:hidden;font-size:13px;margin-bottom:4px}
th,td{padding:9px 13px;text-align:right;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase}
tr:last-child td{border-bottom:none}
.flag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600}
.flag.red{background:#f8514933;color:var(--neg)}
.flag.ok{background:#3fb95033;color:var(--pos)}
.foot{color:var(--mut);font-size:12px;margin-top:28px;line-height:1.8}
"""


def _pct(v: Optional[float], decimals: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v * 100:+.{decimals}f}%"


def _f(v: Optional[float], decimals: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:.{decimals}f}"


def _cls(v: Optional[float]) -> str:
    if v is None:
        return ""
    return "pos" if v > 0 else ("neg" if v < 0 else "")


def _build_html(results: dict, png_b64: str) -> str:
    strat = results.get("strategy", {})
    spy   = results.get("spy", {})
    cheap = results.get("cheap_only", {})
    ew    = results.get("ew_universe", {})
    cov   = results.get("coverage_pct", 0.0)
    conc  = results.get("concentration", {})
    surv  = results.get("survivorship", {})
    sub   = results.get("subperiods", {})
    sweep = results.get("sweep", {})
    meta  = results.get("meta", {})

    # ---- verdict text -------------------------------------------------------
    top_name = conc.get("top_name", "—")
    top_share = conc.get("top_name_share", 0.0)
    conc_flag = conc.get("single_name_over_50pct", False)
    conc_html = (
        f'<span class="flag red">CONCENTRATION &gt;50%: {top_name} '
        f'({top_share * 100:.0f}%)</span>'
        if conc_flag
        else f'<span class="flag ok">OK ({top_name} {top_share * 100:.0f}%)</span>'
    )

    missing_ct = surv.get("missing_prices_count", 0)
    univ_size  = surv.get("universe_size", "?")

    verdict = f"""
<b>Validation milestone — NOT a verdict.</b> The pipeline, PIT discipline, and 15 bps
transaction costs are proven end-to-end on a 20-name, 2015–2020 run.
EDGAR free fundamentals delivered <b>100% tag coverage</b> on large caps — the
free-data thesis holds on the fundamentals side.<br><br>
<span class="caveat">Strategy {_pct(strat.get('cagr'))} CAGR / {_f(strat.get('sharpe'))} Sharpe
is NOT informative:</span> the compound gate fires only ~3/71 months on 20 names,
leaving ~96% of months in cash. The entire P&L is effectively AAPL alone.
Concentration flag: {conc_html}<br><br>
<b>Cheap-only</b> (value gate, no quality/drop filter): {_pct(cheap.get('cagr'))} CAGR /
{_f(cheap.get('sharpe'))} Sharpe — beats SPY on return ({_pct(spy.get('cagr'))} / {_f(spy.get('sharpe'))});
trails on Sharpe. Equal-weight universe: {_pct(ew.get('cagr'))} CAGR / {_f(ew.get('sharpe'))} Sharpe.<br><br>
<b>Survivorship hole (UN-backstopped):</b> Yahoo drops delisted names, Stooq fallback is dead (JS-challenge).
Missing price files: <b>{missing_ct} / {univ_size}</b>.
On this large-cap validation universe the gap is zero — but a full S&P 500 run will include
small/mid-caps where survivorship bias is severe. Results are optimistically biased until a
delisted-price source (e.g. Polygon $29/mo) is added.<br><br>
<b>No edge verdict yet.</b> Scale to the full S&amp;P 500 universe + close the survivorship hole
+ extend to 2009-now (incl. the value winter) — THEN read the verdict.
"""

    # ---- summary cards ------------------------------------------------------
    cards = [
        ("Strategy CAGR",  _pct(strat.get("cagr")),  _cls(strat.get("cagr"))),
        ("Strategy Sharpe", _f(strat.get("sharpe")), _cls(strat.get("sharpe"))),
        ("Cheap-only CAGR", _pct(cheap.get("cagr")), _cls(cheap.get("cagr"))),
        ("SPY CAGR",        _pct(spy.get("cagr")),   _cls(spy.get("cagr"))),
        ("Coverage %",      f"{cov * 100:.1f}%",     "acc"),
        ("Survivorship gap", f"{missing_ct}/{univ_size}", "warn" if missing_ct > 0 else "pos"),
    ]
    cards_html = "\n".join(
        f'<div class="card"><div class="k">{k}</div>'
        f'<div class="v {c}">{v}</div></div>'
        for k, v, c in cards
    )

    # ---- sub-period table ---------------------------------------------------
    sub_rows = ""
    for label, sp in sub.items():
        sub_rows += (
            f"<tr><td>{label}</td>"
            f'<td class="{_cls(sp.get("cagr"))}">{_pct(sp.get("cagr"))}</td>'
            f'<td class="{_cls(sp.get("sharpe"))}">{_f(sp.get("sharpe"))}</td>'
            f'<td class="{_cls(sp.get("max_drawdown"))}">{_pct(sp.get("max_drawdown"))}</td>'
            f"<td>{sp.get('n_periods', 0)}</td></tr>"
        )

    # ---- sweep table --------------------------------------------------------
    sweep_rows = ""
    for thr, sp in sorted(sweep.items(), key=lambda x: float(x[0]), reverse=True):
        sweep_rows += (
            f"<tr><td>{float(thr):.2f}</td>"
            f'<td class="{_cls(sp.get("cagr"))}">{_pct(sp.get("cagr"))}</td>'
            f'<td class="{_cls(sp.get("sharpe"))}">{_f(sp.get("sharpe"))}</td>'
            f'<td class="{_cls(sp.get("max_drawdown"))}">{_pct(sp.get("max_drawdown"))}</td>'
            f"</tr>"
        )

    # ---- survivorship table -------------------------------------------------
    s_base    = surv.get("base", {})
    s_stress  = surv.get("stressed", {})
    surv_rows = (
        f'<tr><td>Base (missing → dropped)</td>'
        f'<td class="{_cls(s_base.get("cagr"))}">{_pct(s_base.get("cagr"))}</td>'
        f'<td class="{_cls(s_base.get("sharpe"))}">{_f(s_base.get("sharpe"))}</td>'
        f'<td class="{_cls(s_base.get("max_drawdown"))}">{_pct(s_base.get("max_drawdown"))}</td></tr>'
        f'<tr><td>Stress (missing → −50%)</td>'
        f'<td class="{_cls(s_stress.get("cagr"))}">{_pct(s_stress.get("cagr"))}</td>'
        f'<td class="{_cls(s_stress.get("sharpe"))}">{_f(s_stress.get("sharpe"))}</td>'
        f'<td class="{_cls(s_stress.get("max_drawdown"))}">{_pct(s_stress.get("max_drawdown"))}</td></tr>'
    )

    # ---- metadata footer ----------------------------------------------------
    start  = meta.get("start", "?")
    end    = meta.get("end", "?")
    n_reb  = meta.get("n_rebalances", "?")
    cost   = meta.get("txn_cost_bps_per_side", 15)
    sector = meta.get("sector_source", "?")

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Value + Quality + Drop — Backtest Dashboard</title>
<style>{_CSS}</style>
</head><body><div class="wrap">
  <h1>Value + Quality + Drop &nbsp;<span class="acc">·</span>&nbsp; Backtest Dashboard</h1>
  <p class="sub">{start} → {end} &nbsp;|&nbsp; {n_reb} rebalances &nbsp;|&nbsp;
    {cost} bps/side txn cost &nbsp;|&nbsp; sector: {sector}</p>

  <div class="verdict">{verdict}</div>

  <h2>Summary</h2>
  <div class="cards">{cards_html}</div>

  <h2>Equity curves — cumulative return</h2>
  <img class="chart" src="data:image/png;base64,{png_b64}" alt="Equity curves">

  <h2>Strategy — sub-period breakdown</h2>
  <table>
    <thead><tr><th>Period</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th><th>Months</th></tr></thead>
    <tbody>{sub_rows}</tbody>
  </table>

  <h2>Drop-threshold sweep (strategy leg)</h2>
  <table>
    <thead><tr><th>Drop threshold</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th></tr></thead>
    <tbody>{sweep_rows}</tbody>
  </table>

  <h2>Survivorship stress — base vs pessimistic (−50% for missing names)</h2>
  <table>
    <thead><tr><th>Scenario</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th></tr></thead>
    <tbody>{surv_rows}</tbody>
  </table>

  <div class="foot">
    <b>EDGAR tag coverage:</b> {cov * 100:.1f}% of universe names had usable PIT fundamentals.
    &nbsp;|&nbsp; <b>Survivorship:</b> missing price files = {missing_ct}/{univ_size} (Yahoo-only; Stooq fallback dead).
    &nbsp;|&nbsp; <b>Concentration:</b> top name = {top_name} ({top_share * 100:.0f}% of cumulative P&L).
    Concentration flag ({'>'}50%) = {conc_flag}.<br>
    <b>Disclaimer:</b> Research spike only — no live execution, no approved rules, nothing
    validated for production. Positive cheap-only / SPY numbers do NOT constitute a
    reliable signal until the universe, time window, and survivorship hole are all
    addressed. Negative-result is equally valid.
  </div>
</div></body></html>"""
    return html


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_dashboard(results: dict, out_dir: str) -> str:
    """Write equity_curves.png + dashboard.html into out_dir. Returns html path."""
    os.makedirs(out_dir, exist_ok=True)

    monthly = results.get("monthly_returns", {})
    png_bytes = _equity_curve_png(monthly)

    png_path = os.path.join(out_dir, "equity_curves.png")
    with open(png_path, "wb") as fh:
        fh.write(png_bytes)

    png_b64 = base64.b64encode(png_bytes).decode("ascii")
    html = _build_html(results, png_b64)

    html_path = os.path.join(out_dir, "dashboard.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    return html_path
