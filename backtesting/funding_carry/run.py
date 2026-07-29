"""Run the delta-neutral funding-carry backtest over the 8 large-cap majors.

    python3 -m backtesting.funding_carry.run

Fetches settled funding-rate history (cached) for each symbol, runs always-on and
funding-timed carry, and writes runs/funding_carry.{json,html} + a per-symbol table.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import Dict

from dataclasses import replace as _replace

from .data import fetch_funding, load_funding
from .strategy import FundingCfg, carry_symbol, portfolio, gate_sweep
from .viz import render_html

# maker execution test: same funding stream, cheaper legs (resting limits, no slippage)
_FEE_SCENARIOS = [
    ("taker (spot 0.10% + perp 0.05%/side)", 0.0010, 0.0005),
    ("maker (spot 0.02% + perp 0.02%/side)", 0.0002, 0.0002),
]


def cost_scenarios(frames, base_cfg: FundingCfg):
    """Re-run carry under taker vs maker legs; report portfolio net APR for each."""
    out = []
    for name, sf, pf in _FEE_SCENARIOS:
        c = _replace(base_cfg, spot_fee_pct=sf, perp_fee_pct=pf)
        ps = {s: carry_symbol(df, c) for s, df in frames.items() if len(df)}
        p = portfolio(ps)
        out.append({"scenario": name, "round_trip": round(c.round_trip, 4),
                    "net_always": p["net_APR_always"], "net_gated": p["net_APR_gated"]})
    return out

_RUNS = os.path.join(os.path.dirname(__file__), "runs")
_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "LINK"]
_VENUE = "gate"          # Binance USDⓈ-M geo-blocked here; Gate allows 180-day lookback
_LOOKBACK_DAYS = 179     # Gate's public funding history cap


def load_all(refetch: bool = True):
    out = {}
    now = dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    until = now.strftime("%Y-%m-%d")
    import ccxt
    ex = getattr(ccxt, _VENUE)({"enableRateLimit": True}) if refetch else None
    for sym in _SYMBOLS:
        ccxt_sym = f"{sym}/USDT:USDT"
        try:
            if refetch:
                out[sym] = fetch_funding(ccxt_sym, since, until, exchange=ex)
            else:
                out[sym] = load_funding(f"{sym}_USDT_USDT_funding_*.csv")
            print(f"  {sym}: {len(out[sym])} funding intervals")
        except Exception as e:
            print(f"  skip {sym}: {str(e)[:80]}")
    return out, since


def main():
    cfg = FundingCfg()
    frames, since = load_all(refetch=True)
    per_symbol = {s: carry_symbol(df, cfg) for s, df in frames.items() if len(df)}
    port = portfolio(per_symbol)
    valid = {s: df for s, df in frames.items() if len(df)}
    sweep = gate_sweep(valid, cfg, [0.1, 0.2, 0.3, 0.5, 1.0])
    costs = cost_scenarios(valid, cfg)
    _SINCE = since

    # strip heavy curve arrays from the console/json-summary copy
    light = {s: {k: v for k, v in r.items() if not k.startswith("_")}
             for s, r in per_symbol.items()}
    report = {
        "config": {"spot_fee_pct": cfg.spot_fee_pct, "perp_fee_pct": cfg.perp_fee_pct,
                   "round_trip_pct": cfg.round_trip, "cond_threshold": cfg.cond_threshold,
                   "since": _SINCE},
        "portfolio": port, "per_symbol": light, "curves": per_symbol,
        "gate_sweep": sweep, "cost_scenarios": costs,
        "gate_cfg": {"window": cfg.gate_window, "enter_bps": cfg.gate_enter_bps,
                     "exit_bps": cfg.gate_exit_bps},
    }

    os.makedirs(_RUNS, exist_ok=True)
    with open(os.path.join(_RUNS, "funding_carry.json"), "w") as f:
        json.dump({k: v for k, v in report.items() if k != "curves"}, f, indent=2)
    html_path = os.path.join(_RUNS, "funding_carry.html")
    render_html(report, html_path)

    print(f"\nDelta-neutral funding carry — {len(per_symbol)} majors since {_SINCE}")
    print(f"Costs: spot {cfg.spot_fee_pct:.2%}/side + perp {cfg.perp_fee_pct:.2%}/side "
          f"= {cfg.round_trip:.2%} round-trip\n")
    print(f"{'sym':5} {'n':>4} {'pos%':>6} {'grossAPR':>9} {'netAPR(on)':>11} "
          f"{'netAPR(gated)':>13} {'held%':>6} {'togg':>5}")
    for s, r in light.items():
        print(f"{s:5} {r['n']:>4} {r['pct_positive']:>6.1%} {r['gross_APR']:>9.2%} "
              f"{r['net_APR_always']:>11.2%} {r['net_APR_gated']:>13.2%} "
              f"{r['gated_held_frac']:>6.0%} {r['gated_toggles']:>5}")
    if port:
        print(f"\nPORTFOLIO (equal-weight): gross {port['gross_APR']:.2%}  "
              f"always-on {port['net_APR_always']:.2%}  gated {port['net_APR_gated']:.2%} "
              f"(held {port['gated_held_frac']:.0%})  | funding+ {port['pct_positive']:.1%} of intervals")
    print(f"\nMAKER vs TAKER (portfolio net APR):")
    print(f"  {'scenario':40} {'round-trip':>10} {'always-on':>10} {'gated':>9}")
    for c in costs:
        print(f"  {c['scenario']:40} {c['round_trip']:>10.2%} "
              f"{c['net_always']:>10.2%} {c['net_gated']:>9.2%}")
    print(f"\nGATE ENTER-THRESHOLD SWEEP (portfolio net APR):")
    print(f"  {'enter bps/8h':>12} {'net APR':>9} {'held%':>6} {'avg toggles':>12}")
    for row in sweep:
        print(f"  {row['enter_bps']:>12.2f} {row['net_APR']:>9.2%} "
              f"{row['held_frac']:>6.0%} {row['avg_toggles']:>12.1f}")
    print(f"\nWrote {html_path}")


if __name__ == "__main__":
    main()
