# Adversarial verification of `A_supply-gap.md`

**Verifier, 2026-09-22 ~18:3xZ. Read-only throughout** -- nothing started, stopped or edited
outside this file and my scratchpad
(`...\scratchpad\missed\verify-supply-gap\`: `ext.py`, `fills.py`, `a2.py`, `a2b.py`,
`a3risk.py`, `adverse.py`, `a5.py`, `a5b.py`, `peek.py`, `gapsize.py`, `gapsize2.py`).
At finish: `kalshi_collector` (105304) and `crypto_feeds` (105352) both alive, free RAM
2.03 GB, free disk 28.5 GB. My own python peaked under 120 MB; no order-book rebuild, no
`load_quotes`.

**My instruments, deliberately different from A's.** A rebuilt the full order book; I did
not. I used (1) `research/pinrun.py` source for every mechanism claim, (2) all 126
`pinrun-live-*.jsonl` (1,224 orders, 788 fills, 14,550 refusals, 1,275 close summaries,
14 `end` records), (3) Kalshi's own `results/kalshi_ledger.json` for every dollar
(`payout - costs - fees`, 761 markets we entered, +$507.56 lifetime), and (4) the `ticker`
channel for targeted market-windows only. Where A and I agree using instruments we did not
share, the finding is stronger. Where we disagree, I say which number I trust and why.
**n = closes. Every risk number is from OUR OWN fills. The tape appears only as "what was
offered / what the market did".**

---

## Verdicts at a glance

| A's candidate | verdict | why |
|---|---|---|
| 1. Log the silent budget skip | **survives** | mechanism confirmed twice over; costs nothing, decides nothing |
| 2. Count an attempt only when an ORDER is sent | **survives (with one amendment)** | lockout counts reproduce exactly; move only the PER-TICKER counter |
| 3. Make the third bet takeable (95c cap) | **weakened** | real but ~$3/day, and the safety argument fails on my re-derivation |
| 4. `staged_none` should read the ladder, not the touch | **survives -- strongest risk evidence here** | our own swept/thin-touch fills are not adversely selected, n=127 closes |
| 5. Uptime "beats every gate change" | **weakened** | ~5/6 of those lost closes were an EXCHANGE outage, provable from the collector's own gaps |
| A2's "95c or cheaper is risk-neutral even at the bad end" | **weakened** | the loss rate is 3.29% [1.76, 5.56], not 2.29% [1.05, 4.30]; at 90-95c it is 4.67% against a 4.67% break-even |

---

## 1. What reproduced exactly

- **A5's lockouts, to the market.** `market_attempts` lockouts: **42 lifetime in 36
  closes; 13 post-fix in 12 closes; every record `tried`=3**. A's figures exactly. **12 of
  the 13** carry a refusal from a gate that sits AFTER the attempts counter
  (`early_cheap` or `staged_none`) -- i.e. a gate that burnt the attempt. The one
  exception is `KXBTC15M-26SEP200215-15`.
- **A4's silent skip, from the bot's own counter.** Run `20260920T023207Z` ended with
  `state.signals` = 102 against `sent` = 5 and 5 `signal` records. **In every run before
  it that carries an `end` record, `signals` == `sent` exactly** (1/1, 7/7, 33/33, 4/4,
  23/23). So 97 looks passed every gate and left no trace. I also walked every `continue`
  between the counter (line 11316) and the order send: there are six, and five write a
  `_gate()` record. **The budget skip at 11322 is the only silent exit in the whole
  region.**
- **A4's "priced for three, can only take two".** `close_budget()` (line 8982) =
  `MAX_PER_CLOSE * SIZE` = 2 bets. `close_budget_for()` (line 1625) returns
  `base + EXTRA_COIN*SIZE` for a new coin and `base + LATE_EXTRA*SIZE` inside
  `late_extra_tau`. `worst_close_cost()` (line 8990) =
  `(MAX_PER_CLOSE + max(EXTRA_COIN, LATE_EXTRA)) * size * PRICE_CEILING` -- **three bets**.
  Live flags: `extra_coin` 1.0, `late_extra` 1.0, `late_extra_tau` 15. Confirmed.
- **A5's mechanism, in the source.** `take_n = min(float(SIZE), float(size))` where `size`
  is the TOUCH (line 11113). `depth_floor` computes the ladder reach and the comment says
  outright *"take_n is deliberately NOT reassigned here"*. `MIN_FILL_FRAC` is 0.0 and
  `MIN_LEVEL` is 1.0, so **`depth_floor` and `staged_none` test the same threshold (1.0)
  against different things** -- the ladder and the touch. A thin touch with a fat ladder
  passes the first and is refused by the second. Of 28 lifetime `staged_none` records, 26
  have `held` = 0 (the touch case, not the "we already hold it" case) and the touch sizes
  are sub-contract dust: 0.5 (x9), 0.02 (x6), 0.1 (x4), 0.92, 0.57, 0.38.
- **The size deflator I went looking for is not there.** I suspected A's contract counts
  were measured at a bet size much bigger than today's. They are not: `autosize` ran
  70-80 contracts through the whole window and is **80 now** (bank $940.89, 17:02:51Z).
  A's counts scale to today.

## 2. What did NOT reproduce

### 2a. The loss rate underneath A2's price rule is worse than A2 says

Our own fills, entry orders joined to Kalshi's settlement rows, a close counts as losing
when the markets we entered in it net negative:

| our <=30 s fills at 90-98c | closes | losing | rate (Clopper-Pearson 95%) | contracts | c/contract |
|---|---|---|---|---|---|
| **A's figure** | 393 | 9 | 2.29% [1.05, 4.30] | 21,938 | +2.01c |
| **mine** | **395** | **13** | **3.29% [1.76, 5.56]** | **22,370** | **+2.11c** |
| mine, 90-95c | 107 | 5 | **4.67% [1.53, 10.57]** | 5,209 | +5.45c |
| mine, 95-98c | 267 | 8 | 3.00% [1.30, 5.82] | 13,399 | +0.97c |
| mine, 96-98c | 240 | 7 | 2.92% [1.18, 5.92] | 11,762 | +0.80c |

Closes and contracts agree to within 0.5% and 2%, so we are looking at the same
population; **we disagree on which closes lost**, 13 against 9. I cannot reconstruct A's
rule. Mine is: Kalshi's own settlement rows, `payout - both sides' cost - fees`, summed
over the markets we entered in that close. The four A appears to be missing include the
two largest (`KXNEAR15M-26SEP082045-45` -$52.60 and `KXBNB15M-26SEP191230-30` -$61.75),
which is the signature of reading the bot's `settled` records instead of the ledger -- a
market that settles after a restart never gets one.

**What this does to the rule.** Break-even is 4.67% at 95c. A compares it to the *blended*
upper bound (4.30%) and concludes 95c survives the bad end. But the band a 95c cap actually
buys is 90-95c, and **that band's own rate is 4.67% [1.53, 10.57] -- the point estimate
sits exactly on break-even and the upper bound is more than double it.** The honest
statement is the opposite of A's: *at the bad end of what we have measured, even a 95c
chase is not clearly positive.*

**What survives is the realised margin, which is the better measure anyway** (it already
contains the losses and the hedges): 90-95c at <=30 s earns **+5.45c a contract over 5,209
contracts in 107 closes**, median day +6.59c, **13 of 14 days positive**, and +5.20c with
the best day removed. So: chase cheap, yes -- but because the money has actually arrived,
not because a loss-rate interval clears break-even. It does not.

### 2b. "Uptime beats every gate change here" -- most of that time was the exchange, not us

A counts 364 contracts (+$28.35) offered while the bot was down or blind, over two windows.
They are not the same kind of thing.

- **09-22 01:00-05:15Z: 18 closes with `looks` = 0**, every one refusing on `book_stale` /
  `index_stale`. **The collector -- a separate process on a separate WebSocket -- went dark
  in the same window**: `kalshi_data/ticker/20260922T01..04.jsonl.gz` **do not exist**, and
  `cfbenchmarks_value` is 6 KB for hour 01 and missing for 02, 03, 04 (1.3-1.6 MB on a
  normal hour). Two independent consumers blind at once is the exchange or the link.
  **No bot change recovers this.**
- **09-20 03:45-04:41Z (the drawdown re-halts): the tape is COMPLETE** -- ticker 1.96/2.12/2.19 MB
  and index 1.61/1.59/1.59 MB for hours 03/04/05. That one is genuinely ours, and it shows
  up as **3 missed closes on 09-20** (watched closes per ET day: 09-20 93/96, 09-21 95/96).

Apportioning A's $28.35 by duration -- 56 min ours, 288 min not -- leaves about **$4.60
recoverable**, not $28.35. Candidate 5 is still worth doing (it costs nothing and blocks
nothing) but it does not beat candidate 4.

### 2c. Two arithmetic inconsistencies inside A's own tables

- A5 prose: the unlockable offers are *"272 contracts at <=30 s, 521 at 31-45 s, +$8.16"*
  -> 793 contracts. A3's table, same item and the same $8.16: 204 + 365 = **569**. One of
  the two contract counts is wrong.
- A3's 31-45 s block: the reasons sum to 365 + 156 + 77 + 76 = **674** against a stated gap
  of **600**. (The <=30 s block is internally consistent: 323+262+204+81+55 = 925.)

### 2d. My own independent sizing of the blocked windows

Different instrument, no order-book rebuild: for every post-fix window that logged a
`market_attempts` or `close_budget` refusal (13 + 31), I read the `ticker` channel for tau
3-30, took the ask on the side the bot's own refusal record says it wanted (no hindsight --
windows with no `want` are dropped), kept 90-98c with >= 1 contract, and capped each window
at one bet (77).

**34 windows: 395 contracts standing at <=95c, 1,128 at 90-98c**, which at our own fills'
margins is **+$21.52 (cheap part) / +$23.80 (whole band)** over 2.5 days.

Split by why the window was blocked, same method, over the same 236 watched closes (2.5 days):

| blocked by | windows | ctr 90-98c | $/day, whole band | ctr <=95c | $/day, cheap part only |
|---|---|---|---|---|---|
| `market_attempts` lockout | 13 | 342 (137/day) | **+$2.88** | 225 (90/day) | **+$4.90** |
| logged `close_budget` | 21 | 786 (314/day) | **+$6.63** | 170 (68/day) | **+$3.71** |

(The cheap column is priced at the 90-95c margin and the band column at the blended one, so
they are two different rules, not two halves of one number.) The silent skip (A4) cannot
appear in this table at all -- it leaves no record, which is the whole of candidate 1.

This is the touch only, so it is a floor against A's ladder rebuild; it does not condition
on the model being >= 99.5% sure, so it is an over-count in the other direction. The two
errors point opposite ways and the answer lands on A's: **the whole pile is $20-25 over
2.5 days, roughly $8-10 a day, not the $50-60/day arithmetic bound.** A's central and least
welcome finding -- *there is very little left to grab* -- is corroborated on an instrument
A did not use. It is also concentrated: of 13 attempts-lockout windows, **two** carry
almost all of it (`KXBTC15M-26SEP200215-15`, `KXBTC15M-26SEP200515-15`, thousands of
contracts standing at the touch); the other eleven are 0-49 contracts.

## 3. The risk attack, per candidate, on our own fills only

**The question I was sent to ask: is there evidence from OUR OWN fills that these captured
trades would not lose more than their margin, or is it the tape illusion again?**

- **Candidate 4 has the best answer in the report, and it is real.** The population it adds
  is "thin touch, fat ladder, we sweep". We already have fills of exactly that kind, flagged
  `swept` by the bot itself: **127 closes, 4 losing (3.1%), +2.30c a contract** against
  not-swept **122 closes, 4 losing (3.3%), +1.81c**. Fills where the signal's touch was
  under 5 contracts: **40 closes, 1 losing (2.5%), +3.33c**. Both are above the 30-close
  floor and both point the same way: **sweeping a thin touch is not adversely selected for
  us.** This is the only candidate whose added population is directly evidenced.
- **Adverse selection, tested the way that has caught us before.** Our fills on levels that
  had rested >= 1 s: **113 closes, 2 losing (1.8%), +2.61c**. On levels under 0.25 s old:
  117 closes, 4 losing (3.4%), +2.13c. The direction supports A's argument that offers which
  stood a whole second are the better sub-population -- though the intervals overlap, so
  treat it as consistent, not proven.
- **Candidate 3's added population is NOT evidenced.** Bet #3+ in a close: **19 markets, 0
  losing, +3.59c a contract** -- below the 30-close floor, so "no loss seen yet", not
  "safe". And the correlation is exactly what the settlement model predicts: in **175 of
  183** multi-market closes every market we held finished the same sign. A third bet is
  mostly a bigger version of the same bet, not a second one. The per-close loss rate does
  not rise with bets (1 market 4.0%, 2 markets 4.8%, 3 markets 0 of 15) but n is far too
  small to call that safety. A's own wording -- *"inside the risk we are already sized for",
  not "no risk"* -- is the correct one and should stay that way in any summary.
- **Would any of this change what fills us?** Only candidate 3 plausibly: a third bet
  arrives later in the close, into a book two of our own sweeps have already moved. Nothing
  in our own fills measures that, so it is a hypothesis and the paper arm has to be scored
  on fill PRICES, not only on decisions.
- **None of the five can block a hedge.** Checked in source: the hedge path stopped reading
  the entry attempts counter at A71 (lines 10298-10320 explain why -- it is the shape of all
  three losses on 2026-09-19), and every candidate is in the entry loop.

## 4. One amendment to candidate 2

A says "move the two counter increments below the 45 s-leg gates". **Move only
`attempts_tk` (line 11359). Leave `attempts[close_s]` (line 11358) where it is.** The
per-close counter is checked against `MAX_ATTEMPTS_PER_CLOSE` = 24 and **hedge orders
increment it too** (line 10418, deliberately: *"a hedge order still spends the ENTRY
budget"*). Moving it as well would quietly loosen the per-close runaway rail on a busy
close, and it buys nothing -- every lockout in this window is per-market, not per-close.

## 5. For FREEZE bar B5 -- two corrections to A's input

- A's input to B5 stands on the supply side: the gap is absent supply, and B5's refusal-based
  bounds cannot contain the silent skip (A4). I confirmed the silent skip independently from
  the bot's own `end` counter, so that input is sound.
- **But B5 must not take A2's 2.29% as the loss rate.** On Kalshi's own settlement rows it is
  **3.29% [1.76, 5.56]** of closes, and **4.67% [1.53, 10.57]** in the 90-95c band that any
  "chase cheap" rule would buy. Any B5 arithmetic that nets a captured contract against a
  2.29% loss rate is using a number I could not reproduce.
