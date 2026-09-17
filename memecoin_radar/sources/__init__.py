"""External data clients.

Each module owns its own rate limiting, because the three providers have very
different budgets (DexScreener 300 req/min unauthenticated, Helius free tier
10 RPS, PumpPortal one connection total) and a shared limiter would have to be
pessimistic enough for the tightest of them.
"""
