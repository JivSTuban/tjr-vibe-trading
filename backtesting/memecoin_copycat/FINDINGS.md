# Meme-coin copycat / crowding test (2026-10-07)

**Question:** if a scraper finds a trending topic and we launch a coin on it first, does being
early/first change the odds of the coin developing a real market?

**Verdict: NOT SUPPORTED by the data we have.** Being first barely moves the odds, and the one
table that makes it look good is look-ahead. The question that decides the scraper idea (can a
topic be detected BEFORE other launchers do?) cannot be tested from this data.

## Data
Mac Mini `~/memecoin-radar-data/radar.sqlite3` (read-only, 4.2 GB live): **504,909 pump.fun launches,
2026-09-17 to 2026-10-06**, every one observed for the first 3600 s. `trend_context` and
`social_mentions` are empty there (0 rows), so there is no external topic signal.

Extract (run over ssh, `sqlite3 -readonly`):

```sql
select t.mint,t.name,t.ticker,t.created_at,t.deployer,t.initial_buy,t.creator_supply_pct,
       s.n_snap,s.peak_liq,s.peak_mc,s.last_age
from tokens t left join (select mint,count(*) n_snap,max(liquidity_usd) peak_liq,
       max(market_cap_usd) peak_mc,max(age_seconds) last_age
       from market_snapshots group by mint) s on s.mint=t.mint
```

**Outcome ("win") = peak liquidity >= $15,000 within the first hour** (the radar's tradeability
floor). That is "a market exists", not profit. Pair-flip guard applied (liquidity above market cap
or above $10M is dropped): 6,827 raw wins become 6,796.

## Results (ticker key; name key within 0.1 to 0.5pp of every cell)
Base rate: **1.35% of launches reach $15k liquidity in the first hour**; median peak liquidity $3,619.

| Others who launched the same ticker before you (1h chain) | n | win % |
|---|---|---|
| none (first) | 219,283 | 1.90 |
| 2-3rd | 57,010 | 1.93 |
| 4-10th | 36,059 | 1.53 |
| 11-30th | 13,208 | 1.35 |
| 31st+ | 4,981 | 1.00 |

- **First vs 2nd/3rd is a tie** (1.90 vs 1.93). Crowding costs you only past about the 4th launcher.
- **Hindsight cut (look-ahead, do not quote as an edge):** among clusters that later reached 8+
  deployers, the first launcher won 4.63% vs 1.74% for a cold first launcher. The cluster only
  became hot because the first coin ran and drew copies.
- **Even among hot topics, 85% produced no winner at all** (483 of 3,284 clusters had one). Two
  thirds of those winners were not the first launcher (first-winner rank: 1st 31.5%, 2-3rd 18.8%,
  4-10th 32.7%, 11th+ 17.0%).
- Largest clusters (`19stocks`, `memecoin`, `grokmemes`, `bobs`, 120 to 190 deployers each in one
  hour) had **0 winners**: topic heat does not create a market.

## Limits (read before reusing)
- Ticker/name matching is lexical. It misses semantic copies (TRUMP vs MAGA2) and over-merges
  generic words (`sol`, `cat`, `memecoin`).
- Outcome window is 1 hour; late bloomers are not counted.
- 19 days of one regime. Not a verdict on every market.
- Wins measure a market existing, not creator income. Volume per winner is NOT measured here.

## What would settle the scraper question
Persist an external trend signal (X / Google Trends / Reddit) with timestamps into `trend_context`,
then test whether launching within N minutes of a topic's first appearance beats the 1.35% base.
Until that exists, a trend scraper is unvalidated.
