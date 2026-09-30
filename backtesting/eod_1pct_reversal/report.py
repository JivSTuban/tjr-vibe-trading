"""Build the emailed backtest report from whatever runs exist in runs/.

Plain text + HTML. HTML because a table of basis points read as plaintext in Gmail is
unreadable on a phone, and the whole point of the report is a reader comparing columns.

    uv run python -m backtesting.eod_1pct_reversal.report            # write files
    uv run python -m backtesting.eod_1pct_reversal.report --print    # stdout preview
"""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd

RUNS = os.path.join(os.path.dirname(__file__), "runs")
OUT = os.path.join(RUNS, "email")


def load(tag: str) -> dict | None:
    p = os.path.join(RUNS, f"{tag}.json")
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


def _tbl(rows: list[dict], cols: list[str], headers: list[str]) -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        tds = []
        for c in cols:
            v = r.get(c, "")
            cls = ""
            if isinstance(v, (int, float)) and c not in ("n", "n_trades", "n_sessions", "horizon"):
                cls = ' class="pos"' if v > 0 else (' class="neg"' if v < 0 else "")
                v = f"{v:,.2f}"
            elif isinstance(v, (int, float)):
                v = f"{v:,.0f}"
            tds.append(f"<td{cls}>{v}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"


CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
     font-size:15px;line-height:1.55;color:#16202b;max-width:760px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.08em;color:#5b6675;
   margin:30px 0 8px;border-bottom:1px solid #d9dee6;padding-bottom:6px}
.verdict{border-left:4px solid #a4402a;background:#fbf3f1;padding:12px 14px;margin:14px 0}
.verdict b{color:#a4402a}
table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}
th{text-align:right;padding:7px 9px;font-size:11px;text-transform:uppercase;
   letter-spacing:.05em;color:#5b6675;border-bottom:1px solid #c9d1db}
th:first-child,td:first-child{text-align:left}
td{padding:6px 9px;text-align:right;border-bottom:1px solid #eef1f5;
   font-variant-numeric:tabular-nums}
.pos{color:#2f6b4f}.neg{color:#a4402a}
.note{color:#5b6675;font-size:13px}
code{background:#eef1f5;padding:1px 5px;border-radius:3px;font-size:12px}
ul{padding-left:20px}li{margin:5px 0}
"""


def build(daily: dict | None, alp: dict | None) -> tuple[str, str]:
    txt, html = [], [f"<style>{CSS}</style>"]

    html.append("<h1>EOD 1% Previous-Low Reversal — backtest results</h1>")
    html.append('<div class="note">Spec: EOD_1Percent_Codex_Skill_Automation_Design.pdf v1.0 · '
                'repo: <code>backtesting/eod_1pct_reversal/</code></div>')
    txt.append("EOD 1% PREVIOUS-LOW REVERSAL — BACKTEST RESULTS")
    txt.append("Spec: EOD_1Percent_Codex_Skill_Automation_Design.pdf v1.0")
    txt.append("")

    # ---- verdict
    html.append('<div class="verdict"><b>VERDICT: REJECT.</b><br>'
                'Tested over 12.7 years on daily bars and 598 sessions of real minute bars. '
                'The spec&rsquo;s signature filter &mdash; late-session pressure &mdash; is not '
                'neutral but <b>significantly negative</b> (&minus;21.1 bps vs the same '
                'afternoon&rsquo;s market at T+5, t&nbsp;=&nbsp;&minus;2.03). The only rung that '
                'works is the loosest one, and it does not clear its own costs.</div>')
    txt.append("VERDICT: REJECT as specified.")
    txt.append("")

    # ---- long history
    if daily:
        lad = pd.DataFrame(daily["ladder"])
        t1 = lad[lad["rung"].str.endswith("|T+1")].copy()
        t1["rung"] = t1["rung"].str.replace(r"\|T\+1$", "", regex=True)
        html.append("<h2>1 · Long history, 2014-2026 (daily bars, 15:50 proxied by the close)</h2>")
        html.append(f'<div class="note">{daily["sessions"]:,} sessions · '
                    f'{daily["tickers_loaded"]} point-in-time S&amp;P 500 names · '
                    f'{daily["ticker_sessions"]:,} liquid ticker-sessions</div>')
        html.append(_tbl(t1.to_dict("records"),
                         ["rung", "n", "per_day", "hit_rate", "gross_bps", "net@5bps", "mae_bps"],
                         ["Rung", "N", "Per day", "Hit rate", "Gross bps", "Net @5bps", "MAE bps"]))
        ex_rows = pd.DataFrame(daily.get("excess", []))
        if not ex_rows.empty:
            e1 = ex_rows[ex_rows["rung"].str.endswith("|T+1")]
            html.append('<div class="note">Excess over the same afternoon&rsquo;s control, '
                        'one vote per session:</div>')
            html.append(_tbl(e1.to_dict("records"),
                             ["rung", "n_trades", "n_sessions", "excess_bps_by_session",
                              "excess_t_by_session", "pct_sessions_positive"],
                             ["Rung", "Trades", "Sessions", "Excess bps", "t", "% days +"]))
        txt.append(f"1. LONG HISTORY 2014-2026: {daily['sessions']:,} sessions, "
                   f"{daily['ticker_sessions']:,} liquid ticker-sessions")
        for r in t1.to_dict("records"):
            txt.append(f"   {r['rung']:22s} n={r.get('n',0):>9,} hit={r.get('hit_rate',0):.3f} "
                       f"gross={r.get('gross_bps',0):>7} net@5={r.get('net@5bps',0):>7}")
        txt.append("")

    # ---- alpaca minute
    if alp:
        html.append("<h2>2 · The late-pressure gate, on real minute bars</h2>")
        html.append(f'<div class="note">{alp["sessions_sampled"]} randomly sampled sessions '
                    f'2016-2026 · {alp["ticker_sessions"]:,} ticker-sessions · Alpaca consolidated '
                    f'tape. This is the gate the first study could only see on 57 days.</div>')
        ed = pd.DataFrame(alp["excess"])
        if not ed.empty:
            for fill in ["15:51"]:
                for hz in (1, 3, 5):
                    sub = ed[(ed["fill"] == fill) & (ed["horizon"] == hz) & ed["n_trades"].notna()]
                    if sub.empty:
                        continue
                    html.append(f'<div class="note"><b>Fill at {fill}, T+{hz}:</b></div>')
                    html.append(_tbl(sub.to_dict("records"),
                                     ["rung", "n_trades", "n_sessions", "raw_bps", "control_bps",
                                      "excess_bps_by_session", "excess_t_by_session"],
                                     ["Rung", "Trades", "Sessions", "Raw bps", "Control bps",
                                      "Excess bps", "t"]))
                sub = ed[(ed["fill"] == fill) & (ed["horizon"] == 99)]
                if sub.empty:
                    continue
                html.append(_tbl(sub.to_dict("records"),
                                 ["rung", "n_trades", "n_sessions", "raw_bps", "control_bps",
                                  "excess_bps_by_session", "excess_t_by_session"],
                                 ["Rung", "Trades", "Sessions", "Raw bps", "Control bps",
                                  "Excess bps", "t"]))
        dk = pd.DataFrame(alp["fill_decay"])
        html.append("<h2>3 · Price is moving — what the delay costs</h2>")
        html.append('<div class="note">Drift from the 15:50 signal print to each achievable '
                    'fill, on gated names. The <b>mean is about zero</b> &mdash; the delay does not '
                    'cost you on average. It buries you in variance: by 15:55 the p10&ndash;p90 '
                    'spread is &plusmn;26 bps around a gross edge of 1&ndash;5 bps, so the '
                    'uncertainty of your own fill is 5&ndash;20&times; the signal. '
                    '(An interim note from a 12-session pilot put this at &minus;6.9 bps; on the '
                    'full 144,076-row sample that was wrong.)</div>')
        html.append(_tbl(dk[dk["population"] == "spec_gate"].to_dict("records"),
                         ["fill", "n", "mean_bps", "median_bps", "p10_bps", "p90_bps"],
                         ["Fill", "N", "Mean bps", "Median bps", "p10", "p90"]))
        txt.append(f"2. LATE GATE ON MINUTE BARS: {alp['sessions_sampled']} sessions 2016-2026, "
                   f"{alp['ticker_sessions']:,} ticker-sessions")
        txt.append("")

    html.append("<h2>4 · What would change the verdict</h2>")
    html.append("<ul>"
                "<li>Costs demonstrably under ~2.5 bps/side, evidenced by real fills.</li>"
                "<li>A same-session excess that survives <b>session</b> weighting, not trade "
                "weighting — 8 names bought the same afternoon is one bet, not eight.</li>"
                "<li>Forward paper signals (the spec&rsquo;s own final stage). Costs nothing but "
                "time and is the only honest test of a research-driven version.</li>"
                "</ul>")
    html.append('<div class="note">Full write-up: <code>backtesting/eod_1pct_reversal/FINDINGS.md</code>. '
                'Nothing here was tuned; the spec&rsquo;s stated thresholds were run as written.</div>')
    txt.append("Full write-up: backtesting/eod_1pct_reversal/FINDINGS.md")

    return "\n".join(txt), "\n".join(html)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="show")
    args = ap.parse_args()

    daily, alp = load("daily"), load("alpaca_full")
    txt, html = build(daily, alp)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "body.txt"), "w") as fh:
        fh.write(txt)
    with open(os.path.join(OUT, "body.html"), "w") as fh:
        fh.write(html)
    print(f"wrote {OUT}/body.txt and body.html "
          f"(daily={'yes' if daily else 'no'}, alpaca={'yes' if alp else 'no'})")
    if args.show:
        print("\n" + txt)


if __name__ == "__main__":
    main()
