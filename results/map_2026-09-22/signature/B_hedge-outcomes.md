# B_hedge-outcomes -- the hedge population at ENTRY, and the price of buying protection early

**Finished 2026-09-23 ~02:1xZ (09-22 ~22:1x ET).** Read-only throughout; no
process started, stopped or signalled. Nothing written outside this file and my
scratchpad. Collectors alive after every job: `kalshi_collector.py` pid 105304
at 56 MB, `crypto_feeds.py` pid 105352 at 54 MB. Free RAM 2.45 GB, free disk
**24.4 GB** (above the 6 GB hard collection stop). My own jobs peaked under
60 MB -- no tape scan was needed.

**Scope.** TRAIN only: closes up to 2026-09-20 23:59:59 ET. **697 markets, 509
closes, 17 losses, ledger +$482.88.** Of those, **14 markets were hedged -- 7
real saves and 7 false alarms, in 13 distinct closes** -- and 2 more alarmed
without a hedge. Money and outcomes are Kalshi's ledger via A_table's fills
table; decisions and alarm beliefs are the 124+ live logs; the per-second
insurance prices are the tape (via `flow_cache/hedgetune_table.json`, built by
`hedgetune.py` from the 1/sec index and the ticker tape). **No replay, no
pinsim, no pindata.** Two numbers come from 09-22 (holdout) and are labelled
where they appear.

**Cuts taken: 242.** Multiple-looks bar = 0.05 / 242 = **0.000207**.

---

# THE ANSWER IN ONE PARAGRAPH

**There is no cheap insurance, and the reason is arithmetic, not bad luck.**
Buying protection at entry at the market's price is *exactly* the same trade as
buying fewer contracts, plus the cost of crossing the spread -- proved to the
cent below. And there is no middle moment to buy it either: when one of these
markets turns, the price of the other side does not walk up through 20c and 30c,
it **gaps** from under 11c to over 44c between two consecutive seconds, in 5 of
the 7 markets we actually saved. So the only real dial on the half of our losses
that arrive silently is **how many contracts we are holding**, not insurance.

---

# FINDING 1 -- a protective leg bought at entry is buying fewer contracts, and paying to do it

**Claim.** At any single instant the ask on our side and the ask on the other
side **never** sum to less than 100c: in **696 of 696** quoted TRAIN fills the
pair summed to 100.1c at the very cheapest, **median 101.4c**, p95 107.5c. So a
protective leg at entry can never be a free hedge. It is algebraically identical
to entering smaller:

> holding `n` of our side and `m` of the other side
> = holding `(n - m)` of our side, plus a certain loss of `m x (our ask + their ask - 100c)`.

**Proved to the cent on the real fills.** Summed over every quoted TRAIN fill, a
1:1 protective leg bought at entry returns **-$1236.39**, and

    -$1236.39 = -(gross entry P&L +$575.39) - crossing spread $545.34 - the leg's own fees $115.66
    residual: $0.0007

**The price, both halves, from Kalshi's ledger.**

| what we protect | markets | losses | ledger $ | saved on the losers | paid on the winners | NET | vs simply not entering |
|---|---|---|---|---|---|---|---|
| **every TRAIN market** | 697 | 17 | +482.88 | **+578.73** | **-1815.12** | **-1236.39** | $753.51 worse |
| insurance <= 3c ("nearly free") | 206 | 1 | +68.65 | +107.65 | -266.23 | -158.58 | $89.92 worse |
| **insurance 5-8c (the 6-7c band)** | 172 | 5 | +138.39 | +161.22 | **-504.75** | **-343.54** | $205.15 worse |
| insurance >= 25c at entry | 10 | 6 | -126.58 | +144.49 | -28.60 | +115.89 | $10.68 worse |
| the 29 markets A_table Finding 1 flags | 29 | 9 | -214.96 | +282.49 | -136.11 | +146.38 | $68.59 worse |
| **the 16 that later alarmed (perfect hindsight)** | 16 | 8 | -352.21 | +275.68 | -35.75 | **+239.93** | **$112.28 worse** |

Partial protection is linear: at 0.50 it is -$618.20, at 0.25 it is -$309.10.

**Read the last row twice.** Even if we knew in advance exactly which 16 markets
would go on to scare us, protecting them at entry returns +$239.93 while simply
not entering them returns +$352.21. **Protection loses to abstention by $112.28
even with perfect foresight**, because it is the same trade with a spread and a
second fee bolted on.

**The band the operator named is the worst one.** Insurance at 5-8c looks almost
free, and that is the trap: across 172 markets it costs **$504.75 of winner
money to recover $161.22 from 5 losers**. Cheap insurance is cheap because the
market thinks we are going to win, and it is right 97 times in 100.

**No cheaper route exists.** A resting bid cannot beat the ask (a bid at or above
the ask crosses immediately; a bid below it only fills when the market moves
*in our favour*). The ask is the floor.

**What would make this an artefact, and the check.** A unit or side error would
break the 100c floor; it does not -- 0 of 696 pairs sum below 100c, and A_table
validated the tape's opposite-side ask against the bot's own `hedge_quote` to
0.00c median. Using the *executed* price instead of the ask does produce 12% of
rows summing under 100c, but that is the market moving while our order was in
flight (A_table Finding 2), knowable only afterwards -- not an arbitrage.

---

# FINDING 2 -- insurance does not ramp, it gaps: a price-triggered hedge has nothing to fill at

**Claim.** The natural fix for the expensive hedge -- "buy the other side the
moment it reaches 25c, instead of waiting for our belief to fall" -- fails
because **the 25c rung usually does not print.** From the per-second tape for
the 14 hedged TRAIN markets:

| market | lost | insurance at entry | the jump, two consecutive seconds |
|---|---|---|---|
| BTC 09-14 05:30 | yes | 36.0c | tau 13 **1c** -> tau 11 **52c** |
| DOGE 09-18 00:15 | yes | 94.8c | tau 29 **2c** -> tau 27 **74c** |
| BNB 09-19 12:30 | yes | 10.0c | tau 13 **3c** -> tau 11 **65c** |
| HYPE 09-14 16:00 | yes | 5.2c | tau 21 **5c** -> tau 19 **44c** |
| ZEC 09-12 20:00 | yes | 11.0c | tau 25 **11c** -> tau 23 **61c** |
| BNB 09-16 12:30 | yes | 7.2c | walked: 9 -> 16 -> 27 -> 38 -> 48 -> 66c |
| BTC 09-17 21:15 | yes | 59.0c | already dear at entry |

**5 of the 7 saves gapped straight past the whole 15-40c band.** A 25c trigger
would have executed at 44-74c -- which is where the deployed 0.25 belief trigger
already executes. Only BNB 09-16 (a 1-contract position) actually walked up.

**And tonight's DOGE is the same shape, harder.** From the bot's own per-second
`hedge_quote` records: the insurance ask ran **6.6c ... 6.6c, then 93c with 1
contract offered**. There was no 25c, no 50c, no 75c. (That close is holdout,
outside this report's TRAIN mandate; quoted as illustration only.)

**The one piece of good news, and it is holdout.** Across the **29 held markets
that have per-second insurance quotes** (they start 2026-09-22 12:14Z, so this
is the holdout window, n far below the 30-close floor): on the **26 that won,
the insurance ask never once exceeded 12.0c.** The only market that crossed 25c
was the DOGE loss. So a 25c trigger would fire very rarely on a winner -- it
simply fires too late to help on a loser.

**Could not measure:** the false-fire rate of a 25c trigger over the TRAIN
window. `hedge_quote` did not exist before 2026-09-22 11:52Z and
`hedgetune_table.json` only covers the 16 markets that alarmed. The 29-market
bound above is the only measurement that exists.

---

# FINDING 3 -- the entry insurance price is a real warning, but it is 100% redundant with the 2-second collapse flag

**Claim.** Refusing a fill whose opposite-side ask is expensive at that second
is a strong rule in isolation -- and it catches **not one losing market that
A_table's Finding 1 (our ask fell >3c in 2 s) does not already catch.**

Per-FILL gate, TRAIN, from A_table's per-leg arithmetic (`entry_pnl - fee` on
the legs it blocks):

| refuse if insurance >= | fills | closes | losing markets touched | avoided on losers | forgone on winners | NET | Poisson p |
|---|---|---|---|---|---|---|---|
| 12c | 66 | 64 | 8 of 17 | -223.54 | +190.70 | +32.85 | 2.7e-04 |
| **15c** | **44** | **43** | **8 of 17** | **-223.54** | **+126.16** | **+97.39** | **1.7e-05** |
| **20c** | **18** | **17** | **8 of 17** | **-223.54** | **+32.51** | **+191.03** | **2.3e-08** |
| 25c | 11 | 10 | 7 of 17 | -211.05 | +7.21 | +203.83 | 1.6e-08 |
| 30c | 9 | 8 | 6 of 17 | -152.07 | +7.17 | +144.90 | 1.3e-07 |

Both 15c and 20c clear the 0.000207 multiple-looks bar. 15c also clears the
**30-close floor (43 closes)**; 20c does not (17 closes). Excluding the 09-19
bug day, >=15c still returns +$49.93 and >=20c +$132.06.

**Then the kill.** Overlaid on Finding 1:

| threshold | markets | also collapse-flagged | losing markets it ADDS | the extra legs it blocks |
|---|---|---|---|---|
| >= 15c | 44 | 15 | **0** | 29 winning legs, **-$97.72** |
| >= 20c | 18 | 11 | **0** | 7 winning legs, -$25.34 |
| >= 25c | 11 | 10 | **0** | 1 winning leg, -$0.05 |

Applied per fill, Finding 1 alone returns **+$247.06**; adding the insurance
gate on top makes it **worse** at every threshold. **So this is not a second
gate. It is the same gate, measured off a different wire.** Ship one, not both.

---

# FINDING 4 -- half the loss money arrives with nothing visible at entry, and the market cannot see it either

| the 17 TRAIN losses | count | ledger $ |
|---|---|---|
| pre-flagged (our ask fell >3c in 2 s) | 9 | **-260.77** |
| **silent at entry** | **8** | **-269.37** |

The silent half costs slightly **more** than the flagged half. And the market was
just as blind: **0 of the 8 silent losses had insurance above 12c at entry** --
every one sat at 2.0c to 11.0c, the modal price of a market we are about to win.

| silent loss | ledger $ | insurance at entry | 2 s move | alarms |
|---|---|---|---|---|
| BTC 09-19 16:00 | -107.95 | 2.0c | +0.7c | **0** |
| BTC 09-19 02:00 | -66.34 | 5.7c | +1.2c | **0** |
| HYPE 09-14 16:00 | -29.90 | 5.2c | +1.0c | 1 (saved) |
| SOL 09-11 23:00 | -19.61 | 5.1c | +1.7c | 0 |
| SOL 09-12 04:00 | -18.88 | 11.0c | +7.8c | 0 |
| BNB 09-10 01:30 | -17.60 | 7.9c | 0.0c | 0 |
| ZEC 09-12 20:00 | -8.63 | 11.0c | +1.2c | 1 (saved) |
| BNB 09-16 12:30 | -0.47 | 7.2c | +2.3c | 1 (saved) |

**The two biggest losses we have ever taken are in this table with no alarm at
all** -- both on 09-19, the day already recorded as "3 of 4 losses were new
gates/brakes blocking a hedge or crashing the loop". **Excluding 09-19, the
silent losses total -$95.08 and the hedge caught 3 of the 6.** That reframes the
silent half: it is mostly a hedge-plumbing failure that has since been fixed
(v-safety1), not an information problem.

---

# Refuted, or not supported -- reported as nulls

- **NOTHING at entry tells a real save from a false alarm.** 19 features, best
  threshold chosen freely (so the p is flattered), on 7 saves vs 7 false alarms:
  best Fisher **p = 0.123** (`cushion_sd`), then 0.131 (`insurance at entry
  >= 36c`, 3 of 7 saves vs 0 of 6 false alarms), 0.133, 0.141. The bar is
  0.000207. **MDE: with 7 and 7, only a PERFECT separator (7 of 7 vs 0 of 7,
  Fisher p = 0.0006) could have cleared the bar.** The test could have found a
  perfect rule. There is not one.
- **Nothing at entry isolates the 8 silent losses either.** 197 threshold cuts
  over 31 features on the 668 markets Finding 1 leaves alone (8 losses, 1.20%
  base, +$697.85): best **p = 0.063** (`sd_remaining >= 4.44`: 34 markets, 2
  losses, -$110.61) -- which is just "the two big BTC positions on 09-19".
  Nothing else is under 0.19. **MDE: a rule would have to pack 5 of the 8 silent
  losses into 30 markets, or 7 of 8 into 100.** The best found 3 of 8 in 138.
- **The 2-second collapse flag leans toward the hedge being RIGHT, but not
  significantly**: 4 of 7 saves were collapse-flagged at entry vs 1 of 7 false
  alarms (Fisher **p = 0.131**). Coherent -- an entry-time collapse is real
  information, a quiet entry means the alarm is model noise -- and that is
  exactly what A_table's Finding 5 says from the alarm second. **Suggestive
  only; do not gate on it.**
- **Position size does not predict a false alarm** (median 84 contracts vs 60
  for saves, p = 0.231). The false alarms cost more dollars because they came
  later, when sizing was bigger.
- **The hedge program itself, TRAIN, for the record:** 7 saves +$115.81, 7 false
  alarms -$152.79, **net -$36.98**. Consistent with the lifetime -$47.
- **Cross-check on the deployed trigger, not a new finding.** Read straight off
  the `hedge_alarm` records, **all 7 TRAIN false alarms alarmed at a belief of
  0.27-0.89 -- every one above 0.25** -- while 4 of the 7 saves alarmed at
  0.15-0.24. That agrees with `v-hedge25`'s per-second rebuild, which is the
  better instrument and is already live. **Settled; not re-litigated here.**

---

# Could not measure, and why

- **The false-fire rate of any price-triggered hedge over TRAIN.**
  `hedge_quote` (per-second insurance ask and depth per held market) starts
  2026-09-22 11:52:44Z, and `hedgetune_table.json` covers only the 16 markets
  that alarmed. The 26-winner bound in Finding 2 is holdout and one day.
- **Whether the 4 cheap false alarms would have re-fired later.** A market whose
  belief was 0.53 at its 0.8-threshold alarm may have dipped under 0.25 later in
  the same close; the log only records the alarm at the threshold then in force.
  `hedgetune.py` is the instrument that answers this and already has.
- **DOGE 09-16 09:00** is unusable for the price work: its `hedgetune` path shows
  the insurance ask pinned at 93c with 3 contracts for the entire close while we
  held the other side at 97.93c. That cannot both be true; its entry hour is one
  of the two unreadable tape hours as well. Treated as a bad row, not evidence.
- **Per-fill ledger money** does not exist (a hedged market is one ledger row),
  so the gate tables use A_table's per-leg arithmetic, which reconciles to the
  ledger within 5c on 777 of 779 markets.

---

# Solutions worth testing -- and what each one BLOCKS

1. **Do not build "buy protection at entry", in any size.** It is arithmetically
   entering smaller plus the spread, and loses to abstention by $112.28 even
   with perfect hindsight. **Blocks nothing -- it is a decision not to build.**
   If the intent behind it was "carry less risk into these markets", the honest
   implementation is a size change or A_table Finding 1's entry gate, and it
   should be measured as a sizing change.
2. **Do not ship the entry insurance-price gate on top of Finding 1's gate.** It
   adds 0 losing markets and costs $97.72 of winners at >=15c. **It blocks 29
   winning legs for nothing.** If Finding 1's gate is ever reverted, >=15c is
   the fallback that clears both the 30-close floor and the looks bar on its own
   (+$97.39, 43 closes, p = 1.7e-05).
3. **Measure the price-trigger question with the record already being written.**
   `hedge_quote` gives ask + depth + belief per second per held market at zero
   cost. At ~30 held markets a day, 10 days gives ~300 markets and answers
   directly: how often does the insurance ask reach 25c on a market that goes on
   to win, and is there depth there. **Blocks nothing -- it is a read.** Bar to
   pre-register before looking: fewer than 1 in 20 winners touching 25c, and
   median depth at 25c at least the position size.
4. **Nothing at entry should be allowed to touch the hedge.** This report found
   no entry feature that predicts a false alarm, so any proposal to *suppress* a
   hedge based on how the entry looked has no evidence behind it and would be
   the 2026-09-19 failure again (a gate blocking a hedge). **State this
   explicitly in any hedge change.**
