# insider_cluster — does an insider cluster buy add tradeable alpha?

Event-driven backtest of SEC Form-4 **open-market cluster buys** (≥2 distinct insiders) as a small-cap
signal, with a **counterfactual** that isolates whether the insider filing adds anything on top of a
catalyst. Built to answer the open question left by the deep-research on the `/stock-scan insider` mode.

**Result:** WEAK / cost-fragile. Real but short-lived (~20-day) survivorship-inflated drift that decays
to ~zero by 60d; the earnings catalyst carries the durable edge. See [FINDINGS.md](FINDINGS.md).

## Data (free, point-in-time)
- **Insider panel:** openinsider historical screener, paged one month at a time
  (`fd=-1` + `fdr` date range, `xp=1` purchases). Clustering is done locally (`grp=1` is broken from
  this env). Each row's *filing date* = public disclosure → t+1 entry is genuinely tradeable.
- **Prices:** Yahoo daily OHLC (reuses `swing_bounce/prices_ohlc.py`). ⚠️ no delisted names →
  survivorship bias → all numbers are UPPER bounds.
- **Catalyst:** Finnhub earnings surprise (PEAD proxy). Key in macOS Keychain (`stock-scan-finnhub`).

## Layout
| File | Role |
|---|---|
| `panel.py` | openinsider historical P-buy panel + cluster-event builder |
| `catalyst.py` | Finnhub earnings-beat overlay (`had_beat_near`, `beat_events`) |
| `run.py` | driver: arms (insider / catalyst-only / intersection / control) + survivorship stress |
| `runs/<ts>/results.json` | per-run output (gitignored) |

Reuses `swing_bounce`'s generic `prices_ohlc`, `trade_sim`, `metrics`.

## Run
```
python3 -m backtesting.insider_cluster.run     # ~15 min (rate-limited fetch), then runs + prints summary
```
Window/universe knobs at the top of `run.py` (`START`, `END`, `MAX_TICKERS`, `HORIZONS`).

## Arms
- `control` — unconditional H-day base rate (same universe) — the bar to beat
- `insider_all` / `insider_csuite` / `insider_big` — cluster events, sliced by quality
- `insider_plus_catalyst` / `insider_no_catalyst` — cluster split by nearby earnings beat
- `catalyst_only` — earnings beats WITHOUT a cluster (isolates catalyst-alone)
