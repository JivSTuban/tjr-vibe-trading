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
    taker_fee_pct: float = 0.0005       # 0.05% / side (market/stop fills)
    maker_fee_pct: float = 0.0002       # 0.02% / side (resting limit fills)
    slippage_pct: float = 0.0005        # 0.05% / side (adverse, taker legs only)

    # --- Cost model (iteration 4) ---------------------------------------- #
    # "taker_only"   -> every leg pays taker fee + slippage (the conservative
    #                   iteration 1-3 model), charged per-leg at the ACTUAL
    #                   fill prices (entry and exit_price).
    # "maker_taker"  -> models how the setup actually executes:
    #     * ENTRY is a LIMIT order resting at the FVG/OB edge — price must
    #       trade INTO it to fill, so the entry leg is a MAKER fill (no
    #       slippage; you set the price).
    #     * TP is a LIMIT order resting beyond price ⇒ MAKER fill.
    #     * SL is a STOP that converts to a MARKET order on trigger ⇒ TAKER
    #       fill + adverse slippage.
    #   So a winner pays two maker legs; a loser pays maker entry + a
    #   taker+slippage exit (strictly more costly per unit of risk).
    #   Funding is EXCLUDED: holds are intraday (entry->TP/SL inside the
    #   5m walk), so no 8h funding window is crossed in the modelled path.
    cost_model: str = "maker_taker"     # "taker_only" | "maker_taker"

    @property
    def cost_per_side_pct(self) -> float:
        """Total adverse cost fraction for a *taker* side (fee + slippage).

        Retained for the ``taker_only`` model and backward compatibility.
        """
        return self.taker_fee_pct + self.slippage_pct
