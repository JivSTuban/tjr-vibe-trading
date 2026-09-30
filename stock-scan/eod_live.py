"""LIVE 15:50 ET scan for the EOD 1% previous-low reversal (the `/stock-scan eod` mode).

This is the LIVE entry point. It deliberately imports the gate and feature contract
from `backtesting.eod_1pct_reversal` rather than restating it, so the thing that runs
against real money is the same code that was measured over 3,190 sessions. If the
backtest's definition of a gate changes, this changes with it.

WHY THIS EXISTS AT ALL, given FINDINGS.md says REJECT: the backtest could only reach
the `late` gate on 57 days of 5m data, where 90% of the result landed on three
sessions and the sign INVERTED against the long sample. The research-gated variant is
therefore *unproven*, not disproven, and the only way left to test it is FORWARD. So
this runner is a paper-log generator first and a trade list second, and it prints the
cost floor next to every candidate because the banked break-even is 2.85 bps/side
against a close->open drift of ~4-6 bps.

    uv run python -m stock-scan.eod_live --signal 15:50
    python3 stock-scan/eod_live.py --signal 15:50 --limit 120
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backtesting.eod_1pct_reversal import features as F  # noqa: E402
from backtesting.eod_1pct_reversal import strategy as S  # noqa: E402

DATA = "https://data.alpaca.markets/v2/stocks/bars"
ET = "America/New_York"

# The banked cost floor. FINDINGS.md: the four-filter stack is worth +0.52 bps over
# buying anything, and break-even is 2.85 bps PER SIDE. Printed on every run so the
# number is never absent from the decision.
BREAKEVEN_BPS_PER_SIDE = 2.85
CLOSE_TO_OPEN_DRIFT_BPS = 4.13


def keychain(account: str) -> str | None:
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-s", "claude-alpaca", "-a", account, "-w"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None


def headers() -> dict:
    k = os.environ.get("ALPACA_API_KEY") or keychain("ALPACA_API_KEY")
    s = os.environ.get("ALPACA_SECRET_KEY") or keychain("ALPACA_SECRET_KEY")
    if not k or not s:
        raise SystemExit("no Alpaca credentials (keychain claude-alpaca / env)")
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}


def fetch(symbols: list[str], timeframe: str, start: str, end: str, feed: str,
          hdrs: dict, limit: int = 10000) -> dict:
    """Page through Alpaca's multi-symbol bars endpoint. Returns {symbol: [bars]}."""
    out: dict[str, list] = {}
    for i in range(0, len(symbols), 200):
        chunk = symbols[i:i + 200]
        token = None
        while True:
            p = {"symbols": ",".join(chunk), "timeframe": timeframe, "start": start,
                 "end": end, "limit": limit, "adjustment": "all", "feed": feed}
            if token:
                p["page_token"] = token
            r = requests.get(DATA, params=p, headers=hdrs, timeout=30)
            if r.status_code != 200:
                raise SystemExit(f"alpaca {r.status_code}: {r.text[:300]}")
            j = r.json()
            for sym, bars in (j.get("bars") or {}).items():
                out.setdefault(sym, []).extend(bars)
            token = j.get("next_page_token")
            if not token:
                break
    return out


def to_daily(bars: list) -> pd.DataFrame:
    """Alpaca daily bars -> the frame features.py expects (adjustment=all => adjclose=close)."""
    df = pd.DataFrame(bars)
    if df.empty:
        return df
    df["session"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(ET).dt.normalize().dt.tz_localize(None)
    df = df.set_index("session").sort_index()
    out = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    out["adjclose"] = out["close"]          # bars requested pre-adjusted
    return out[["open", "high", "low", "close", "adjclose", "volume"]]


def to_5m(bars: list) -> pd.DataFrame:
    """1-minute bars -> 5-minute bars indexed by tz-aware ET bar START.

    features.intraday_features reads the OPEN of the 15:50 bar as the signal price, so
    the bar must be labelled by when it OPENS (label='left'). Getting this backwards
    smuggles five minutes of look-ahead into the signal.
    """
    df = pd.DataFrame(bars)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(ET)
    df = df.set_index("ts").sort_index()
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample("5min", label="left", closed="left").agg(agg).dropna(subset=["open"])


def sp500() -> list[str]:
    """Point-in-time-ish universe. Falls back loudly rather than silently shrinking."""
    try:
        from backtesting.eod_pressure_reversal import universe as U
        mem = U.fetch_membership()
        syms = U.members_on(mem, datetime.now().date())
        if syms:
            # Alpaca wants the DOT form (BF.B), not Yahoo's dash form (BF-B).
            return sorted({s.replace("-", ".") for s in syms})
    except Exception as e:                                   # noqa: BLE001
        print(f"[warn] universe module unavailable ({e}); using Alpaca active-assets fallback")
    r = requests.get("https://paper-api.alpaca.markets/v2/assets",
                     params={"status": "active", "asset_class": "us_equity"},
                     headers=headers(), timeout=60)
    r.raise_for_status()
    syms = [a["symbol"] for a in r.json()
            if a.get("tradable") and a.get("exchange") in ("NYSE", "NASDAQ", "ARCA")
            and "." not in a["symbol"] and len(a["symbol"]) <= 4]
    return sorted(set(syms))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", default="15:50", help="signal time ET (spec: 15:50)")
    ap.add_argument("--feed", default="iex", help="iex (free) or sip (paid)")
    ap.add_argument("--limit", type=int, default=150, help="max candidates to price intraday")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    hdrs = headers()
    now_et = pd.Timestamp.now(tz=ET)
    today = now_et.normalize()
    print(f"[live] now {now_et:%Y-%m-%d %H:%M:%S %Z} · signal {a.signal} · feed {a.feed}")

    syms = sp500()
    print(f"[universe] {len(syms)} symbols")

    # --- daily leg: 60 calendar days is enough for the 20d range/ADV windows ---
    d_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    d_end = today.strftime("%Y-%m-%d")
    daily_raw = fetch(syms, "1Day", d_start, d_end, a.feed, hdrs)
    # Silent-cap detection. FULL coverage is the EXPECTED result for a blue-chip
    # universe (every S&P 500 member has daily bars), so "response == request" is not
    # the tell and warning on it just trains you to ignore the warning. The real tell
    # is a SHORT response that lands on a suspiciously round number — that is a page
    # limit, not a market fact.
    ROUND_CAPS = {100, 200, 250, 500, 1000, 1500, 5000, 10000}
    got, want = len(daily_raw), len(syms)
    print(f"[daily] {got}/{want} symbols returned ({100*got//max(1,want)}% coverage)")
    if got < want and got in ROUND_CAPS:
        print(f"[WARN] daily response is SHORT and landed on exactly {got} — "
              f"a round number is the silent-cap tell, not a quiet market. Verify paging.")
    elif got < want * 0.9:
        print(f"[warn] {want - got} symbols returned no daily bars "
              f"(delistings/halts are normal; a large gap is not)")

    dailies = {s: to_daily(b) for s, b in daily_raw.items()}
    dailies = {s: d for s, d in dailies.items() if len(d) >= F.RANGE_WINDOW + 2}

    # --- cheap daily pre-filter: WIDER than the real gate on both sides, so the
    # intraday leg is never starved of a name the 15:50 gate would have selected.
    # (This is the trap-8 lesson: a pre-filter ranked on a different axis than the
    # gate silently deletes the gate's candidates.)
    # The daily index is tz-NAIVE session dates; `today` is tz-aware. Comparing them
    # directly makes the membership test always False and the scan reports a confident
    # zero — the house failure mode. Keep the naive form explicit.
    today_naive = today.tz_localize(None)
    pre = []
    for s, d in dailies.items():
        if today_naive not in d.index or len(d) < 2:
            continue
        adj = F.adjusted(d)
        prev_low, prev_close = adj["low"].iloc[-2], adj["close"].iloc[-2]
        px = adj["close"].iloc[-1]
        dist = (px / prev_low - 1.0) * 100.0
        dret = (px / prev_close - 1.0) * 100.0
        adv20 = (d["close"] * d["volume"]).shift(1).rolling(F.RANGE_WINDOW).mean().iloc[-1]
        if d["close"].iloc[-1] < F.MIN_PRICE or adv20 < F.MIN_ADV20:
            continue
        if -2.0 <= dist <= 2.5 and dret <= 0.0:
            pre.append((s, dist, dret, adv20))
    pre.sort(key=lambda r: abs(r[1]))
    print(f"[prefilter] {len(pre)} names in the wide prev-low band and red on the day")
    if len(pre) > a.limit:
        print(f"[cap] pricing only the {a.limit} nearest the prev low — "
              f"{len(pre) - a.limit} DROPPED (stated, not silent)")
    cands = [r[0] for r in pre[:a.limit]]
    if not cands:
        print("\nNO CANDIDATES. That is an honest empty, not a failure — say so and stop.")
        return 0

    # --- intraday leg: the literal 15:50 features, including the `late` gate ---
    i_start = today.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    i_end = now_et.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    intra_raw = fetch(cands, "1Min", i_start, i_end, a.feed, hdrs)
    print(f"[intraday] {len(intra_raw)}/{len(cands)} symbols returned minute bars")

    rows = []
    for s in cands:
        bars = intra_raw.get(s)
        if not bars:
            continue
        b5 = to_5m(bars)
        if b5.empty or a.signal not in set(b5.index.strftime("%H:%M")):
            continue
        feats = F.intraday_features(b5, dailies[s])
        if feats.empty:
            continue
        f = feats.iloc[[-1]]
        if not bool(F.tradable(f).iloc[0]):
            continue
        conds = S.conditions(f)
        row = {"symbol": s, **{k: float(f[k].iloc[0]) for k in
               ("entry_ref", "prev_low_distance_pct", "day_return_pct",
                "late_return_pct", "close_location_value", "range_capacity_pct")},
               **{g: bool(conds[g].iloc[0]) for g in conds.columns}}
        row["rung"] = sum(1 for _, gates in S.LADDER[1:]
                          if all(row.get(g) for g in gates))
        row["passes_spec"] = all(row.get(g) for g in dict(S.LADDER)[S.SPEC_CONFIG])
        rows.append(row)

    res = pd.DataFrame(rows)
    if res.empty:
        print("\nNO NAME REACHED THE 15:50 GATE. Honest empty.")
        return 0

    res = res.sort_values(["passes_spec", "rung", "late_return_pct"],
                          ascending=[False, False, True])
    passing = res[res["passes_spec"]]

    print(f"\n=== {len(passing)} name(s) pass the spec config ({S.SPEC_CONFIG}) ===")
    cols = ["symbol", "entry_ref", "prev_low_distance_pct", "day_return_pct",
            "late_return_pct", "close_location_value", "range_capacity_pct", "rung"]
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print((passing if len(passing) else res.head(12))[cols].to_string(index=False))

    print(f"\nCOST FLOOR — break-even {BREAKEVEN_BPS_PER_SIDE} bps/side "
          f"({2 * BREAKEVEN_BPS_PER_SIDE:.2f} round trip) vs a close->open drift of "
          f"{CLOSE_TO_OPEN_DRIFT_BPS} bps on ANY liquid name. The gates were worth "
          f"+0.52 bps over that control. Treat every line below as a PAPER LOG entry.")

    # --- Forward-sample integrity. E6's whole purpose is a clean >=30-trade close->open
    # sample, and a row logged from a run that could NOT have traded would contaminate it.
    # This is stamped from the CLOCK, in code, rather than annotated by judgement after
    # the fact: a flag that depends on someone remembering to add it gets forgotten (it
    # was, on 2026-09-23, when a re-run silently dropped it).
    hh, mm = (int(x) for x in a.signal.split(":"))
    sig_dt = now_et.replace(hour=hh, minute=mm, second=0, microsecond=0)
    mins_late = (now_et - sig_dt).total_seconds() / 60.0
    tradable_live = 0 <= mins_late <= 9          # inside the 15:50-15:59 entry window
    if not tradable_live:
        print(f"\n[EXCLUDED FROM FORWARD SAMPLE] run stands {mins_late:+.0f} min from the "
              f"{a.signal} signal — outside the 0..9 min entry window, so no entry was "
              f"achievable. Rows are marked tradable_live=false and must NOT count toward "
              f"the >=30-trade decision rule.")
    for r in rows:
        r["tradable_live"] = bool(tradable_live)
        r["minutes_after_signal"] = round(mins_late, 1)
    res = res.assign(tradable_live=tradable_live, minutes_after_signal=round(mins_late, 1))

    out = a.out or os.path.join(os.path.dirname(__file__), "eod-setups",
                                f"{today:%Y-%m-%d}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump({"asof": now_et.isoformat(), "signal": a.signal, "feed": a.feed,
                   "tradable_live": bool(tradable_live),
                   "minutes_after_signal": round(mins_late, 1),
                   "universe": len(syms), "prefilter": len(pre), "priced": len(res),
                   "rows": res.to_dict("records")}, fh, indent=2, default=str)
    print(f"[journal] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
