# Insider + news-catalyst setups, and where AI adds edge (research review, 2026-09-30)

**Question.** For a long-only, stocks-only, PH-based retail swing trader (3 days to 12 weeks,
free data, manual execution on GoTrade), which insider-transaction and news-catalyst setups
have an edge that survives realistic costs, and where does an LLM (reading filings/news) or an
AI agent (orchestrating the pipeline) add measurable value?

**Method.** `/deep-research` run `wf_bfa6b697-64c`: 6 search angles, 29 sources fetched, 144
claims extracted, top 25 put through 3-vote adversarial verification (14 confirmed, 11 killed).
Then a manual pass, described in "Harness defect" below, recovered the AI evidence the
verification budget had dropped.

---

## Bottom line

1. **No long-only, net-of-cost edge is established for any free-data insider or earnings setup.**
   Every headline number in this literature is GROSS. Not one of the six core papers contains a
   transaction-cost, spread, or impact analysis. The alpha that survives sits in small, illiquid
   names, where the only measured spread for insider-purchase stocks is **133 bps median (173
   bps flagged)**, 23x to 30x the 5.7 bps floor this project used to assume.
2. **Only one candidate clears a cost floor by a wide margin, and it is out of reach**: a
   text-derived earnings surprise whose long leg earns **131 bps over 63 days, gross**. It needs
   paid call transcripts, is a logistic text regression (not an LLM), and its sample ends 2019.
3. **Analyst-surprise PEAD is dead outside microcaps**, and the mechanism behind this project's
   banked "drift only when the beat was rewarded" belief is exactly what died.
4. **The banked insider-cluster + earnings-catalyst result was re-tested and shrank by more than
   half.** +11.15% (n=39) became **+4.79% median net, n=24** once corrected (real announcement
   date, t+2 open, ex-microcap, 150 bps). It passes the pre-committed rule but is fragile, and a
   bare insider buy without a catalyst is **-3.04%** net. See
   `backtesting/insider_cluster/RETEST_N39.md`.
   **Corrected 2026-10-01:** on matured trades (full 60-day windows, refreshed prices) insider + beat
   is +5.23% (n=23) against beat-alone +3.25% (n=221); the +1.99pp difference fails the 3pp rule,
   so the insider layer is NOT established. The beat requirement and the bare-insider refuse
   (-2.61%, n=54) stand.
5. **AI is a defense and discipline tool here, not an alpha source.** The strongest AI evidence
   supports LLMs *classifying filings* (the veto side) and agents *enforcing process*. Every
   test of an LLM or agent *finding* alpha, net of costs, came back negative.

---

## Ranked shortlist (rank = strength of evidence after costs)

| # | Setup | Gross edge | Net (my arithmetic) | Verdict |
|---|---|---|---|---|
| 1 | Text-derived earnings surprise, long top quintile, hold 63d | **131 bps** / 63d (n=85,160, 2010-2019) | ~125 bps at 5.7 bps; **~71 bps at 60 bps** | Best measured, **not implementable free** |
| 2 | Opportunistic-insider **filter** on an existing catalyst setup | 30-40 bps/mo post-decay; long leg 0.52-0.72%/mo, t 1.73-2.27 | Borderline | Filter only, never an entry |
| 3 | Announcement-reaction (EAR) sort, large caps, t+2 open | 89-140 bps/qtr **long-short**, 1987-2004 | Long-only leg **unmeasured** | Cheapest to forward-test; honest prior is failure |
| 4 | Microcap insider buy far below 52w high | 5.2% CAR[1,30] flagged | **Break-even cost 5.2%**; interval includes 0 at a 3% charge | **NEGATIVE, do not build** |
| 5 | Analyst-surprise PEAD / unconditional SUE, liquid names | 4 bps/mo VW, top liquidity quintile | Negative | **DEAD, do not build** |

Net figures are **not published**. They are this review's arithmetic against the old 5.7 bps
floor and a 60 bps small-cap alternative. If the real GoTrade round trip on a $300M-cap name is
150 bps, ranks 2 and 3 go to zero. **Measure the real cost on 20 fills before building anything.**

### Rank 1: text-derived earnings surprise (PEAD.txt)
- **Rule.** Rank each quarter's calls on a text-only surprise model; buy the top quintile at the
  first close after the call; hold 63 trading days; no stop.
- **Evidence.** Meursault, Liang, Routledge, Scanlon, *JFQA* 58(6), 2023. Long leg CAR(1,63)
  **1.31% vs 0.16%** for classic SUE; 1.15 of the 1.33pp spread improvement comes from the long
  top quintile. Out-of-sample by construction (8-quarter sliding window, 40 iterations).
- **Why it is not usable yet.** Capital IQ transcripts via WRDS (paid, no free full-history
  corpus); equal-weighted with no size screen, so microcaps carry full weight; ends 2019Q4; a
  quintile of 85,160 observations is hundreds of positions per quarter, so a manual trader taking
  a handful gets the mean without the diversification.
- **AI role.** The text model *is* the signal, the only place reading text is the edge. But the
  measured model is a regularized logistic regression on bag-of-words features, so "an LLM does
  this better" is **speculative**.
- **Kill rule.** Build a free proxy from 8-K Item 2.02 EX-99.1 earnings-release exhibits (EDGAR
  full text, back to 2004). Delete if the top-quintile mean 63-day benchmark-adjusted return is
  **below 60 bps after 60 graded positions**.
- **Most likely killer.** The signal lives in the call's Q-and-A, which no free source carries.

### Rank 2: routine vs opportunistic, as a filter
- **Rule.** Never a standalone entry. Require the buying insider to be classifiable AND
  opportunistic; otherwise drop the trade.
- **Exact classifier** (Cohen, Malloy, Pomorski, *JF* 2012). Needs at least one trade in each of
  the three prior years to classify at all. **Routine** = traded in the same calendar month for 3+
  consecutive years; everyone else is **opportunistic**. Labels set at the start of each year and
  applied only forward, so no look-ahead. Open-market P and S only.
- **Cost of the gate.** Cuts the sample to about one-third, and on the buy side **only 36% of
  purchases are opportunistic** (64% routine). Tilts toward bigger firms.
- **Free implementation.** Every field is in free EDGAR Form 4 XML from 2003. The blocker: it
  needs **per-insider history keyed by reporting-owner CIK**, across every issuer they file at.
  openinsider is per-issuer and cannot supply it. A common variant is "same month in 3 of the
  past 5 years"; state which one you built.
- **Kill rule.** Drop the filter if the opportunistic subset does not beat the unfiltered subset
  by **at least 50 bps over 40 paired observations**.
- **Most likely killer.** At 36% of purchases, 40 paired observations takes years manually.

### Rank 3: announcement-reaction (EAR) sort in large caps
- **Rule.** Rank on the [t-1, t+1] abnormal return around the release, breakpoints from the
  prior quarter, buy the top quintile at the **t+2 open**, hold to the next announcement.
- **Evidence.** Brandt, Kishore, Santa-Clara, Venkatachalam (UCLA, June 2007 version; 1987-2004).
  Survived a top-1,000 restriction (89-140 bps per quarter long-short, "considerably reduced, yet
  far from eliminated"). The SUE leg collapsed in large caps. Do not quote the 18.06% figure; it
  is labelled perfect foresight.
- **Kill rule.** Free to compute (Yahoo prices + earnings calendar). Delete if the top quintile
  beats a same-day equal-weighted control by **less than 40 bps over 40 positions**.
- **Most likely killer.** Martineau's martingale result (below) says this mechanism is already
  exhausted in exactly this universe.

### Rank 4 (NEGATIVE): microcap insider buy below the 52-week high
arXiv 2602.06198 **v2** (cite v2 only; v1's headline was formally withdrawn in Appendix E).
13,534 code-P lines, $30M-$500M, 2018-2024.
- **3.27 of the 6.90-point gradient lands in the first session after filing** (t=9.77), largely
  an overnight gap a manual PH trader cannot take. The remaining days 2-30 drift has **t=1.70**.
- At a **$5 price floor** the drift is 2.09% (t=1.23); in the liquid subset 1.70% (t=0.70).
- Out-of-sample 2024: flagged 5.2% gross vs **break-even round trip 5.2%**. Net of 3% the interval
  is [-0.5%, 5.0%]. **Trimming the 56 trades above +50% cuts the mean to 1.6%**, below a 3% charge.
- 34.7% of lines were lost at the Yahoo-coverage step (survivorship), and 27% of flagged lines are
  sub-$2 (bid-ask bounce bias).

### Rank 5 (DEAD): analyst-surprise PEAD
Martineau, *Critical Finance Review* 11(3-4), 2022 (312,462 announcements, 1984-2019). BHAR[2,60]
on surprise decile, all-but-microcap: **-0.001 (2006-10), 0.000 (2011-15), -0.002 significant
(2016-19)**, a mild reversal. Replicated through **Dec 2024** by Subrahmanyam (2026): 0.19%/mo,
**t=1.43 excluding microcaps**. Microcaps still show drift. Chordia et al. (*FAJ* 2009): 4 bps/mo
VW in the most liquid quintile vs 2.43% in the least; costs ate 70-100% at institutional scale.
That cost figure is market impact, which a $200-$500 order mostly escapes, so it does not prove
the illiquid drift is unavailable to a small account. The result is monotonic across liquidity
quintiles, and quintiles 2-4 are unmeasured.

---

## Banked beliefs this research puts under pressure

| Banked belief | What the evidence says | Action |
|---|---|---|
| Cluster + earnings catalyst = +11% median, n=39 | Both parts die ex-microcap independently | **Re-tested 2026-09-30, corrected 2026-10-01 on matured trades: insider + beat +5.23% (n=23) vs beat-alone +3.25% (n=221), insider adds +1.99pp, NOT established; bare insider -2.61%** |
| PEAD works when the beat was rewarded | Non-microcap announcement prices are now ~a martingale: unbiasedness slope fell from ~1.6 to ~1.0 (trend 1.38 - 0.012t, p<0.001). The reaction no longer predicts the drift | The post-earnings reaction filter is still a good *veto*; it is no longer evidence of *edge* |
| Opportunistic alpha decayed to 0.3-0.4%/mo (2008-2024) | This exact claim was **refuted 0-3** in verification | Treat as unverified; do not quote as fact |
| Insider edge is stronger in small caps | Same Aalto replication supports opposite size stories by table (EW event-time 1.6x larger, but VW calendar alphas 0.61-0.71 above EW 0.47-0.66) | Size tilt is not established |

---

## Where AI actually helps

Tiers: **[V]** 3-vote verified in the run; **[A]** confirmed by me against the primary abstract;
**[Q]** extracted with a verbatim quote, not independently verified.

### LLM reading text: strong for classification (veto side), unproven for alpha

- **[A] Item codes miss the events that move prices; a grounded LLM recovers them.** *Grounded
  Event Extraction from SEC 8-K Filings* (arXiv 2607.08346): 292,984 filings, 2022-2026. Many of
  the most market-moving disclosures sit in a catch-all item. **[Q]** 9 of the 15 most reactive
  event types file mostly under **Item 8.01 "Other Events"** (clinical trial results, merger
  agreements, regulatory decisions); of 309 cybersecurity incidents only **16%** used the dedicated
  Item 1.05. This is the same failure as this project's form-name dilution gate that missed
  ~55.5M GME shares and RWT's $205M convertible.
- **[A] The build rule that makes LLM extraction reliable.** Two stages: (1) constrain output to a
  fixed taxonomy and **anchor every tag to a verbatim quote**, validated by fuzzy n-gram match;
  (2) **re-grade each quote in a separate, dedicated second pass.** Precision rises from **12% to
  96%** with the second-pass score, and unsupported tags fall from 8% to near zero. The score is
  **only calibrated when assigned in a separate pass**; inline self-rating saturates and cannot
  reach those precision levels.
- **[Q] LLM-on-news alpha is short-lived and gross.** A leak-free news model (ChronoBERT/ChronoGPT)
  posts Sharpe 4.8-4.9 **long-short, daily-rebalanced, gross**, and predictability collapses
  within **two trading days**: wrong horizon for a manual t+1 swing entry. A GPT-sentiment
  strategy earned 6-16 bps/day gross out-of-sample, **t=1.20, not significant**. Knowing the
  company's name made the model *worse* (overconfident directional calls lost 242-289 bps).
- **[A] The famous "GPT-4 beats analysts at financial statement analysis" paper is WITHDRAWN**
  (arXiv 2407.17866; a co-author found data and analysis inconsistencies). Do not cite it.
- **[V] The one strong text result (Rank 1) is not an LLM.** Offensive LLM alpha is unproven here.

### AI agent orchestration: no new alpha, and three concrete design rules

- **[A] Agent-discovered strategies do not survive honest evaluation.** *What survives honest
  evaluation?* (arXiv 2608.27734): 453-stock point-in-time universe, realistic costs, two frontier
  models, up to 100 candidates, 5 runs. **Every LLM-discovered strategy was rejected; passive
  benchmarks were certified.** **A deliberately leaky feature with Sharpe 35 passed Deflated Sharpe
  and PBO tests completely**: statistics do not catch look-ahead, only a structural guardrail on
  which features exist does. **Rule: do not let an agent search for strategies. Pre-register the
  hypothesis, then test only that.**
- **[A] Red-team loops fail by agreeing.** *Multi-Agent Debate for Explainable Trading* (arXiv
  2609.29701), 210 runs: reasoning quality had **no relationship with returns (r=0.07, p=0.29)**.
  The central failure is **sycophantic convergence**: in critique-and-revise cycles agents abandon
  their positions and converge. The only intervention that helped **forced disagreement to persist
  (Sharpe +0.14, p=0.028)**. **Rule: DD red-team agents must stay independent. Never show one agent
  another's verdict, and never let the thesis writer revise a DD verdict.** The current `/stock-scan`
  I5-DD design (parallel, isolated subagents) already follows this; keep it that way.
- **[A] Agents do not follow their own analysis.** *CLQT* (arXiv 2606.29771): a year-long
  contamination-controlled backtest plus a 4-week live paper track. A **stating-versus-doing gap**
  (+0.30 backtest, +0.23 live): allocations systematically diverge from the agent's stated analysis.
  **Net of realistic costs, agents beat defensive baselines but not the index.** **[Q]** Fully
  autonomous orchestration did worse than a constrained pipeline, and knocking out the
  news-sentiment module did not hurt returns. **Rule: the LLM writes the analysis; deterministic
  code turns it into a size and an order.** This is the same lesson as the $300 PLTR loss, where
  the output's *shape* (an orders block) overrode its *label* (`size NONE`).
- **[Q] Published multi-agent trading returns are gross.** A survey of 12 systems found none meets
  basic evaluation standards (best 2 of 5); FinMem's +23.26% on MSFT became **-22.04%** under an
  equally defensible window with costs.

**Where the agent layer earns its keep:** measurement and exposure control. This project's losses
clustered by *theme*, not name (5 of 7 stops on two macro days). A theme label per position plus
a hard cap on how many share one is a cheap, testable control. Three of the five traps below are
measurement failures, and with every candidate edge this thin, getting the measurement right is
worth more than finding another signal.

---

## Traps confirmed inside the sources (with numbers)

1. **Survivorship.** 34.7% of Form-4 lines lost at the price-coverage step.
2. **Right tail.** The 20 largest outcomes supplied 36.6% of summed CAR; trimming 56 trades cut the
   mean from 5.2% to 1.6%. **Always report the trimmed mean beside the mean.**
3. **Restatement.** COMPUSTAT earnings are backfilled; a price-derived signal is structurally
   safer on free data than an earnings-derived one.
4. **Announcement-time ambiguity.** No time-of-day flag, so BMO/AMC is unknown for some events.
   Matches the banked rule: unknown timing blocks both sides.
5. **Signal completes at the close.** EAR needs the t+1 close, so real entry is the t+2 open.
6. **Look-ahead survives statistics.** A Sharpe-35 leaky feature passed DSR and PBO (above).
7. **Version drift.** EAR is 6.3%/11.5% in one version and 7.55%/12.5% in another; the microcap
   paper's v1 headline was withdrawn but still circulates.
8. **Capacity.** A $50k order exceeds 5% of daily dollar volume for 53% of microcap insider events.
   A small account escapes impact but inherits the full spread, so the floor must be measured.

---

## Not covered

No surviving claim addresses contract awards, index inclusion, spin-offs, management changes,
short-squeeze setups, or supply-chain read-through. The 8-K paper classifies events but its
return study is unsigned (it measures that events move prices, not which direction). Infer no
verdict on these.

---

## Harness defect (read before trusting a future deep-research run)

The run verified only the **top 25 of 144** extracted claims. Every claim from the LLM and agent
angles fell below that cut, and the synthesis then reported "nothing measures an LLM" and "nothing
addresses agent orchestration" **as findings**. Both were false: 9 relevant papers had been fetched
and their claims extracted with verbatim quotes. A global top-N ranked on one axis starved whole
angles, and the absence was reported as evidence. This is trap #14 in
`trap-a-signal-that-cannot-fire` (a selector that silently drops its input). The AI section above
was recovered from the journal (`wf_bfa6b697-64c/journal.jsonl`) and spot-checked against the
primary abstracts.

---

## Next tests, pre-committed

1. **Measure the real GoTrade round trip** on 20 real fills (spread + fee, $200-$500, a ~$300M
   name). Every net figure above depends on this one number. Requires live trades, so it is Jiv's.
2. ~~Re-test the banked n=39 cluster + catalyst result.~~ **Done 2026-09-30, downgraded 2026-10-01** (insider adds +1.99pp over a public beat on
   matured trades, fails the 3pp rule; first read was +4.79%, n=24); see `backtesting/insider_cluster/RETEST_N39.md`.
3. **Rebuild the dilution/event veto as grounded two-pass extraction** over 8-K text: taxonomy +
   verbatim quote in pass 1, independent re-grade in pass 2, keep only high scores.

## Sources

Verified in-run: Cohen, Malloy, Pomorski, *JF* 2012 (NBER w16454) · Martineau, *CFR* 2022 ·
Meursault et al., *JFQA* 2023 (PEAD.txt) · Brandt et al., UCLA 2007 (EAR) · Chordia et al., *FAJ*
2009 · arXiv 2602.06198 v2 (microcap insider; single-author preprint) · Aalto Master's thesis, Dec
2025 (2008-2024 replication; not peer-reviewed) · Subrahmanyam, *J. Investment and Management* 2026.
Abstract-checked by hand: arXiv 2607.08346, 2608.27734, 2609.29701, 2606.29771, 2407.17866
(withdrawn). Extracted, not verified: arXiv 2502.21206, 2309.17322, 2603.27539.
