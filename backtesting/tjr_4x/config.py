"""Approved-parameter configuration for the TJR 4X backtest.

All values are baked in as defaults from knowledge/decisions/0001. Two
values follow the *task brief* rather than the decision doc, and are
flagged inline: fees and slippage. The decision doc quoted
0.04% fee + 0.02% slippage as "tunable v0 defaults"; the coding brief
pins them to 0.05% + 0.05%. The brief is treated as authoritative here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # --- Instrument / data ---
    symbol: str = "BTC/USDT:USDT"      # ccxt binanceusdm USD???-M perp
    base_timeframe: str = "5m"          # base data interval; everything derived
    setup_timeframe: str = "15m"        # sweep + BOS detection (resampled)
    bias_timeframe: str = "1D"          # daily bias (resampled)
    confluence_timeframe: str = "4h"    # HTF confluence gate on the daily bias

    # --- Bias engine ablation ---
    # When False, ``find_trades`` returns ALL directional candidates (both
    # long & short) with NO bias filter applied. Used by bias_sweep to run
    # candidate detection once and then filter per bias mode.
    apply_bias_filter: bool = True

    # Which bias encoding find_trades uses (iteration-3 default: C, the
    # draw-on-liquidity mode promoted from the iteration-2 ablation). Maps to
    # ``compute_bias_modes`` keys "current"/"A"/"B"/"C"; when
    # ``use_4h_confluence`` is True the "+4h" gated variant is used.
    bias_mode: str = "C"
    use_4h_confluence: bool = False

    # --- Exit model ---
    # "fixed_rr"          -> tp = entry +/- rr_target * risk (iteration-2 ref).
    # "opposite_liquidity"-> tp = nearest OPPOSING liquidity level beyond entry,
    #                        causal (formed at/before the confirming BOS bar);
    #                        setups with planned rr < min_rr (or no level) skip.
    exit_model: str = "fixed_rr"
    min_rr: float = 1.0                 # min planned reward:risk (opp-liq esp.)

    # --- Min-stop filter ---
    # Skip setups whose structural stop distance is < this fraction of entry
    # (cuts the fee-per-R cost tax on tiny stops). 0 = off.
    min_stop_pct: float = 0.0

    # --- Structure detection ---
    swing_length: int = 3               # pivot: 3 bars each side
    liquidity_range_percent: float = 0.01

    # --- Sweep / confirmation ---
    sweep_close_back_bars: int = 1      # body must close back beyond level within N bars
    close_break: bool = True            # smc BOS uses body-close breaks (wick alone != BOS)

    # --- Risk model ---
    sl_buffer_pct: float = 0.001        # 0.1% beyond sweep extreme
    rr_target: float = 2.0              # fixed 2R single TP
    risk_per_trade: float = 0.01        # 1% (sizing only)
    max_open_positions: int = 1

    # --- Bias fallback ---
    bias_lookback_days: int = 20        # HH/HL slope when no confirmed daily BOS

    # --- Costs (per side, applied to entry AND exit) ---
    # NOTE: follows coding brief (0.05% + 0.05%), not decision-0001's 0.04%/0.02%.
    taker_fee_pct: float = 0.0005       # 0.05% / side
    slippage_pct: float = 0.0005        # 0.05% / side

    @property
    def cost_per_side_pct(self) -> float:
        """Total adverse cost fraction applied on entry and on exit."""
        return self.taker_fee_pct + self.slippage_pct
