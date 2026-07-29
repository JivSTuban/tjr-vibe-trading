"""Top-gainer intraday fade — the ONE untested variant from the deep-research verdict.

Research (deep-research 2026-07-29) killed the naive "fade the day's top gainer"
thesis in general, but left exactly one variant empirically UNTESTED on our data:
the same-day fade of the SINGLE biggest LARGE-CAP perp gainer, funding costed.
Our 8-perp cache (BTC/ETH/SOL/BNB/XRP/ADA/DOGE/LINK) IS Universe A (majors), where
the literature predicts CONTINUATION, not reversal — so the prior is this loses.
This package tests that empirically. Nothing here approves a live rule.
"""
