"""Offline HTML dashboard (no CDN, no network at view time)."""
from __future__ import annotations

import json
from typing import Any

import pandas as pd

_CSS = """
:root{--bg:#ffffff;--fg:#16181d;--muted:#666d78;--line:#e4e7ec;--pos:#17724a;--neg:#b3261e;--accent:#1b4ea8;--panel:#f7f8fa}
@media(prefers-color-scheme:dark){:root{--bg:#131519;--fg:#e8eaed;--muted:#99a0aa;--line:#2b2f36;--pos:#4ec98a;--neg:#f2837b;--accent:#7aa5f0;--panel:#1a1d22}}
*{box-sizing:border-box}
body{margin:0;padding:32px;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1140px;margin:0 auto}
h1{font-size:25px;margin:0 0 4px} h2{font-size:17px;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.sub{color:var(--muted);margin:0 0 22px;font-size:13px}
.verdict{padding:14px 16px;border-radius:8px;border:1px solid var(--line);background:var(--panel);margin:18px 0}
.verdict b{font-size:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:10px;margin:14px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.card .k{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.card .v{font-size:21px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums}
.pos{color:var(--pos)} .neg{color:var(--neg)}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
.note{color:var(--muted);font-size:12.5px;margin:8px 0 0}
svg{max-width:100%;height:auto;display:block}
"""


def _fmt(v: Any, kind: str = "") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if kind == "bps":
        return f"{v*1e4:,.2f}"
    if kind == "pct":
        return f"{v*100:,.2f}%"
    if kind == "num":
        return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.3f}"
    return str(v)


def _cards(items: list[tuple[str, str, bool | None]]) -> str:
    out = []
    for k, v, good in items:
        cls = "" if good is None else (" pos" if good else " neg")
        out.append(f'<div class="card"><div class="k">{k}</div><div class="v{cls}">{v}</div></div>')
    return f'<div class="grid">{"".join(out)}</div>'


def _table(rows: list[dict], cols: list[tuple[str, str, str]]) -> str:
    if not rows:
        return '<p class="note">no rows</p>'
    head = "".join(f"<th>{label}</th>" for _, label, _ in cols)
    body = []
    for r in rows:
        tds = []
        for key, _, kind in cols:
            v = r.get(key)
            cls = ""
            if kind in ("bps", "pct") and isinstance(v, (int, float)) and not pd.isna(v):
                cls = ' class="pos"' if v > 0 else (' class="neg"' if v < 0 else "")
            tds.append(f"<td{cls}>{_fmt(v, kind)}</td>")
        body.append(f"<tr>{''.join(tds)}</tr>")
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _equity_svg(daily: pd.DataFrame, w: int = 1080, h: int = 240) -> str:
    if daily.empty:
        return ""
    eq = daily["equity"].to_numpy()
    lo, hi = float(eq.min()), float(eq.max())
    rng = (hi - lo) or 1.0
    pad = 28
    pts = [
        f"{pad + i/(len(eq)-1 or 1)*(w-2*pad):.1f},{h-pad - (v-lo)/rng*(h-2*pad):.1f}"
        for i, v in enumerate(eq)
    ]
    base_y = h - pad - (1.0 - lo) / rng * (h - 2 * pad)
    color = "var(--pos)" if eq[-1] >= 1.0 else "var(--neg)"
    return f"""<svg viewBox="0 0 {w} {h}" role="img" aria-label="Equity curve">
<line x1="{pad}" y1="{base_y:.1f}" x2="{w-pad}" y2="{base_y:.1f}" stroke="var(--line)" stroke-dasharray="4 4"/>
<polyline fill="none" stroke="{color}" stroke-width="1.8" points="{' '.join(pts)}"/>
<text x="{pad}" y="16" fill="var(--muted)" font-size="11">{daily['date'].iloc[0]}</text>
<text x="{w-pad}" y="16" fill="var(--muted)" font-size="11" text-anchor="end">{daily['date'].iloc[-1]}</text>
<text x="{pad}" y="{h-6}" fill="var(--muted)" font-size="11">x{lo:.3f}</text>
<text x="{w-pad}" y="{h-6}" fill="var(--muted)" font-size="11" text-anchor="end">x{eq[-1]:.3f} final</text>
</svg>"""


def write_dashboard(results: dict, daily: pd.DataFrame, path: str) -> str:
    h = results.get("headline", {})
    cov = results.get("coverage", {})
    bench = results.get("benchmark", {})
    g = results.get("headline_gross", {})
    mean = h.get("mean_ret", 0.0)
    pf = h.get("profit_factor", 0.0)

    verdict = ("EDGE NOT PROVEN" if mean <= 0 else
               "POSITIVE BEFORE FURTHER SCRUTINY" if pf and pf > 1.05 else "MARGINAL")

    cards = _cards([
        ("Trades", f"{h.get('n_trades',0):,}", None),
        ("Mean / trade", f"{_fmt(mean,'bps')} bps", mean > 0),
        ("Median / trade", f"{_fmt(h.get('median_ret'),'bps')} bps", (h.get("median_ret") or 0) > 0),
        ("Win rate", _fmt(h.get("win_rate"), "pct"), (h.get("win_rate") or 0) > 0.5),
        ("Profit factor", _fmt(pf, "num"), (pf or 0) > 1),
        ("Sharpe", _fmt(h.get("pf_sharpe"), "num"), (h.get("pf_sharpe") or 0) > 0),
        ("Max drawdown", _fmt(h.get("pf_max_drawdown"), "pct"), False),
        ("Worst trade", _fmt(h.get("worst"), "pct"), False),
        ("t-stat", _fmt(h.get("t_stat"), "num"), abs(h.get("t_stat") or 0) > 2),
        ("Exposure", _fmt(h.get("pf_exposure"), "pct"), None),
    ])

    html = f"""<!doctype html><meta charset="utf-8"><title>EOD Pressure Reversal V1 — backtest</title>
<style>{_CSS}</style><div class="wrap">
<h1>EOD Pressure Reversal V1</h1>
<p class="sub">{results.get('window','')} · point-in-time S&amp;P 500 · entry = signal-day close, exit = next open ·
costs 5 bps/side unless stated · generated {results.get('generated_utc','')[:19]}Z</p>

<div class="verdict"><b>{verdict}</b><br>
Gross <b>{_fmt(g.get('mean_ret'),'bps')} bps</b>/trade (t={_fmt(g.get('t_stat'),'num')}) →
breaks even at <b>{results.get('breakeven_bps_per_side',0):.2f} bps per side</b>; at 5 bps/side it is
{_fmt(mean,'bps')} bps.<br>
Control, all gross: strategy {bench.get('strategy_mean_bps',0):.2f} · any RED S&amp;P name
{bench.get('any_red_stock_overnight_mean_bps',0):.2f} · any S&amp;P name
{bench.get('any_stock_overnight_mean_bps',0):.2f} · SPY overnight
{bench.get('spy_overnight_mean_bps',0):.2f} bps.</div>

{cards}

<h2>Equity curve — equal-weighted, top 5/day</h2>
{_equity_svg(daily)}

<h2>§9 Staged build order — where does the edge come from? (GROSS)</h2>
{_table(results.get('stages',[]), [('label','Stage','' ),('n_trades','Trades','num'),
 ('win_rate','Win','pct'),('mean_ret','Mean','bps'),('median_ret','Median','bps'),
 ('profit_factor','PF','num'),('pf_sharpe','Sharpe','num'),('worst','Worst','pct')])}
<p class="note">Basis points per trade, <b>gross</b> — costs get their own section below, and a flat
10 bps round trip swamps an effect this size and hides the filter-by-filter structure. Stages 0-6
trade every qualifier; stage 7 applies the top-5 cap. Compare stage 7 against stage 0: that gap is
everything the six filters are worth.</p>

<h2>§8 Transaction-cost stress</h2>
{_table(results.get('cost_stress',[]), [('cost_bps_per_side','bps/side','num'),
 ('n_trades','Trades','num'),('mean_ret','Mean','bps'),('profit_factor','PF','num'),
 ('pf_sharpe','Sharpe','num'),('pf_total_return','Total','pct'),('pf_max_drawdown','MaxDD','pct')])}

<h2>§11 Out-of-sample splits</h2>
{_table(results.get('oos',[]), [('period','Period',''),('n_trades','Trades','num'),
 ('win_rate','Win','pct'),('mean_ret','Mean','bps'),('median_ret','Median','bps'),
 ('profit_factor','PF','num'),('t_stat','t','num')])}

<h2>Year by year — is the edge concentrated?</h2>
{_table(results.get('by_year',[]), [('year','Year','num'),('n_trades','Trades','num'),
 ('win_rate','Win','pct'),('mean_ret','Mean','bps'),('median_ret','Median','bps'),
 ('profit_factor','PF','num'),('sum_ret','Sum','pct'),('worst','Worst','pct')])}
<p class="note">One dominant year is a regime, not an edge.</p>

<h2>§13 Regime — VIX</h2>
{_table(results.get('regime_vix',[]), [('vix_bucket','Regime',''),('n_trades','Trades','num'),
 ('win_rate','Win','pct'),('mean_ret','Mean','bps'),('profit_factor','PF','num'),('worst','Worst','pct')])}

<h2>§13 Regime — SPY on the signal day</h2>
{_table(results.get('regime_spy',[]), [('spy_bucket','Regime',''),('n_trades','Trades','num'),
 ('win_rate','Win','pct'),('mean_ret','Mean','bps'),('profit_factor','PF','num'),('worst','Worst','pct')])}

<h2>§10 Parameter robustness — plateau or spike?</h2>
{"".join(f"<h3 style='font-size:14px;margin:16px 0 6px'>{p}</h3>" + _table(rows, [('value','Value','num'),('n_trades','Trades','num'),('win_rate','Win','pct'),('mean_ret','Mean','bps'),('profit_factor','PF','num')]) for p, rows in results.get('robustness',{}).items())}
<p class="note">A real edge is a plateau across neighbouring values. A single winning cell surrounded by
losers is curve fit.</p>

<h2>§14 Left tail</h2>
{_table([results.get('left_tail',{})], [('n','Trades','num'),('worst_trade','Worst','pct'),
 ('worst_1pct_sum','Worst 1% sum','pct'),('best_1pct_sum','Best 1% sum','pct'),
 ('mean_ex_worst_1pct','Mean ex worst 1%','bps'),('mean_ex_best_1pct','Mean ex best 1%','bps')])}
<p class="note">If "mean ex best 1%" is negative while the headline is positive, the edge is a handful of
lottery tickets and §17 rejects it.</p>

<h2>§14 Worst 25 trades — cause worklist</h2>
{_table(results.get('worst_trades',[]), [('date','Date',''),('ticker','Ticker',''),
 ('day_ret','Signal day','pct'),('rel_vol','RelVol','num'),('price','Entry','num'),
 ('next_open','Exit','num'),('net_ret','Net','pct')])}

<h2>Data coverage — the survivorship disclosure</h2>
{_table([cov], [('pit_tickers','PIT tickers','num'),('priced','Priced','num'),
 ('missing','No price source','num'),('sessions','Sessions','num'),
 ('earnings_events','Earnings events','num'),('earnings_blocked_pairs','Blocked pairs','num')])}
<p class="note">Missing tickers are names that were S&amp;P 500 members during the window but have no free
price history (mostly acquisitions and ticker changes; some failures). Their absence biases results
optimistically and is why this run is a screen, not a green light.</p>
</div>"""
    with open(path, "w") as fh:
        fh.write(html)
    return path
