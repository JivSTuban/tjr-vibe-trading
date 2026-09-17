"""Event-level expectancy for swing bounce trades."""
from __future__ import annotations


def expectancy(trades: list[dict]) -> dict:
    n = len(trades)
    if n == 0:
        return {"n": 0, "hit_rate": 0.0, "stop_rate": 0.0, "time_rate": 0.0,
                "avg_ret": 0.0, "expectancy_R": 0.0, "avg_win": 0.0, "avg_loss": 0.0}
    rets = [t["net_ret"] for t in trades]
    Rs = [t["R"] for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]

    def c(o):
        return sum(1 for t in trades if t["outcome"] == o)

    return {"n": n, "hit_rate": c("target") / n, "stop_rate": c("stop") / n, "time_rate": c("time") / n,
            "avg_ret": sum(rets) / n, "expectancy_R": sum(Rs) / n,
            "avg_win": (sum(wins) / len(wins)) if wins else 0.0,
            "avg_loss": (sum(losses) / len(losses)) if losses else 0.0}
