# lost-races -- adversarial verification

**Status: COMPLETE** (2026-09-22 ~18:3xZ). Read-only: nothing started, stopped or
edited outside this file and `scratchpad/missed/verify-lost-races/`. No network
calls at all (the report's ~80 timing GETs were not repeated -- our own logs
carry the same number, see C2). Every figure below was re-derived with my own
scripts from the live logs, `results/kalshi_ledger.json`, `C:\kals\fulltape\markets.json`
and the `ticker` tape. **n = closes.** Collectors alive at finish (pids 105304,
105352); free RAM 1.76 GB, disk 26.5 GB.

**Headline counts reproduce.** My independent pass over all 126 live logs:
995 orders reached the exchange (report 993), 209 zero-fill (208), 87 partial
(86), 8,194 contracts unfilled (8,184). Differences are order-dedup keying only.

---

## C1. "Count an attempt only when an order is SENT" (report L2) -- **WEAKENED**

**Mechanism: confirmed, independently, in the code.** `attempts_tk[(close_s, tk)] += 1`
is at `pinrun.py:11359`; `early_cheap` (11421), `early_dear` (11445),
`early_wide` (11452), `staged_none` (11459) and `price_band` (11468) each
`continue` after it without sending. The lockout test is at 10916. I count 34
lockouts since 09-17 (42 all-time) -- the report's number.

**What it would really admit.** Taking SIZE from each refusal's own `size_now`
and subtracting what that market already held: **32 of 34 lockouts still had room
(median 77 contracts); 2 had none** (KXXRP 09-19 02:30Z, KXZEC 09-19 07:30Z were
already fully loaded, so `staged_none` would have refused them at tau<=30 anyway).
The report's count survives.

**Size, re-derived from the `ticker` tape (HYPOTHESIS -- tape, not our fills).**
Our side was offered at <=98c somewhere in tau 30..3 after the lock in 24 of 34
markets; inside 90-98c in 22 of 34 (report: 15).

| fill rule (capped at each market's real room) | contracts | $ over ~5 days |
|---|---|---|
| cheapest 90-98c second (the report's rule) | 632 | **+45.46** |
| FIRST offer <=98c at any price | 696 | **+119.28** |
| report's own figure | 514 | +23.38 |

The report's number is inside my range; the **range itself is the finding's
uncertainty**, because neither rule applies the edge/confidence gates the order
would still have faced, and neither models a fill probability.

**The valuation is selected on the model being right.** Using the side the model
wanted at the LAST refusal before the lock, **29 of 29 resolvable lockouts won --
zero losers.** The report's 4 losers come from using the side wanted at the FIRST
refusal; in all four the model flipped sides before the lock. Neither is the side
the bot would have held at tau<=30, so on the small cases the sign is an
assumption.

**Risk evidence from OUR OWN FILLS of the same kind -- this is what fails.**
The class the fix admits is "a fill at tau<=30 in a market whose early leg was
refused by one of the five burner gates in the same close". Ours, since 09-17:

| own fills, tau<=30, since 09-17 | orders | closes | losing closes | contracts | naked $ | per contract |
|---|---|---|---|---|---|---|
| prior burner refusal in the same market | 12 | 11 | 1 (9.1%, CI 0.2-41%) | 727 | -64.02 | **-8.80c** |
| no burner refusal | 119 | 91 | 1 (1.1%, CI 0-6%) | 7,829 | +224.63 | **+2.87c** |

One-sided Fisher p = 0.21 -- 11 closes cannot tell 9% from 1%. Net of the hedge,
from Kalshi's own settlement rows, those 11 markets are **-$42.46**, because one
is KXBNB15M 09-19 12:30 ET at **-$61.75 net** (-$82.36 naked; the hedge recovered
~$20). **One loss of this class is roughly three times the fix's entire upper
bound.** This is not proof the class is bad; it is the absence of any evidence
that it is safe, which is what "no added risk" claims.

**It does change what fills us, in a direction the report does not state.** 17 of
the 34 lockouts were burned by `early_cheap` or `early_wide` -- the gates written
because "a cheap ask out there is the market disagreeing with us at the moment we
can least afford to be wrong" (A49) and "too good to be true" (A50). The bug has
been silently extending those two gates into the <=30 s window whenever the
disagreement lasted more than ~150 ms. Removing the counter re-admits exactly
that population 15 seconds later. The code's own position is that a wide edge
inside 30 s is fine; that is a belief, and the 12 fills above are all the evidence
there is.

**A narrower version that keeps most of the money and none of that transfer
(my proposal).** Stop burning the counter only for `staged_none` and
`price_band` -- refusals that say something about US (nothing left to take; a
configured skip band), not about the market's price -- and leave `early_cheap`,
`early_dear`, `early_wide` burning it. That covers **15 of the 34 lockouts,
+$13.81 on 187 contracts (cheapest-90-98c rule, ~$2.8/day)**, versus +$45.46 for
the full fix, and it re-admits none of the A49/A50 population.

**Verdict: WEAKENED.** Mechanism, block and rough size confirmed; the "no added
risk" half is unsupported by our own fills.

---

## C2. "Take the universe refresh out of the trading loop" (report L3) -- **SURVIVES (size trimmed)**

**Mechanism: confirmed.** `pinrun.py:10704`, `if now - uni_at > 20:`, inline in
`trade_loop`: one `get("/markets", series_ticker=...)` per series, **11 series**
(`SERIES_TO_INDEX`, line 109), sequential, on a fresh connection each, with no
condition on time to close. The hedge pass is in the same loop (the code says so
at 10695: "hedge pass is ABOVE; it keeps running"), so the stall covers hedges.

**Duration, corroborated from OUR OWN LOGS instead of new network calls.** Our
authenticated POSTs to the same host, fresh connection each, run **median 94 ms
(p10 83, p90 119, n = 980 orders)**. Eleven of those back to back is **~1.03 s**,
which brackets the report's measured 0.84-1.0 s. The refresh period is
20 s + refresh, about 21 s, so in a close's last 30 s the loop is blind ~1.3 s
(**4.3%**).

**Size, at our own measured edge rather than an assumed 3-6c.** Our fills at
tau<=30: 805 contracts/day post-fix at +3.92c naked, 1,426/day since 09-17 at
+1.88c. 4.3% of that is **$1.15-1.36/day** -- somewhat below the report's
$1.5-2.5/day, same order. Hedge timeliness in that 4.3% stays unpriced.

**The report's own live check is arithmetically incapable of finding the stall.**
It reports "no gaps > 1 s in per-second `hedge_quote` records" as a non-
confirmation. A blackout shorter than 1.000 s can never skip a whole second of
`hedge_quote` (it cannot cover `[k, k+1)`), so that check could not have detected
a 0.84-1.0 s stall either way. It is not evidence against the finding.

**I tried to find a second, bigger harm in the same code and it is NOT supported.**
`_get` uses `timeout=20` (`pintake.py:1536`) and `seen_markets = fresh` replaces
the universe wholesale, so one failed or hung GET drops a whole coin from the
tradeable set for >=21 s and could in principle freeze the loop for 20 s. Measured:
394 `universe_http_-1` skips in all live logs, **379 of them inside the known
09-22 00:50-05:30Z Kalshi outage** (HANDOFF's top section; nothing was tradeable
then). Outside that outage: **15 skips in 14 days, none closer than 467 s to a
close.** So in normal operation this costs nothing measurable. Reported as
checked and not found.

**What it blocks: nothing, and I checked the edge case.** The refresh filters to
markets closing within 900 s, so at tau < 60 of one close the next close's
markets (960 s out) are excluded anyway -- deferring the refresh while any
watched market has tau < 60 cannot delay the next close's discovery, provided the
skip ends at the close (it does: no watched market then has tau < 60). A
background thread is the riskier form: it shares `urllib`/`kauth` with the loop,
and `if fresh:` plus wholesale replacement means a partial build must never be
published (build local, swap atomically).

**Verdict: SURVIVES.** Mechanism confirmed from code and our own latency data;
dollars trimmed to ~$1.2-1.4/day of entries plus unpriced hedge timeliness; the
logging half (`uni_ms`, loop-pass gap) is freeze-legal and is what turns this from
arithmetic into measurement.

---

## C3. "Do NOT buy speed to win races" (report L1) -- **SURVIVES as a decision, WEAKENED as a measurement**

The -$96-at-43 ms figure is tape-priced, decided by 1-3 losing closes, and the
report says its own earlier estimator gave -$45. Its optimistic case (+$17 over
14 days = +$1.2/day) is inside the noise of a day's P&L. Neither number is a
reason to build anything -- so the recommendation stands on its own -- but
"speed would LOSE money" is not established.

**Our own fills do support it, by a route the report only hypothesised (F2).**
A faster bot buys YOUNGER resting levels by construction. Bucketing our own
fills by `level_age_ms` (exact ages only, n = 341 fills):

| level we consumed | orders | closes | losing closes | contracts | naked $ | per contract |
|---|---|---|---|---|---|---|
| < 0.25 s old | 230 | 196 | 10 (5.1%) | 13,425 | -3.41 | **-0.03c** |
| 0.25-1 s | 60 | 56 | 1 (1.8%) | 3,860 | +90.04 | +2.33c |
| 1-10 s | 31 | 31 | 1 (3.2%) | 1,866 | +5.35 | +0.29c |
| > 10 s | 20 | 20 | 0 | 1,296 | +36.04 | +2.78c |

196 closes in the young bucket, comfortably over the 30-close floor (the
loss-rate difference alone is only p = 0.14; the per-contract gap is the solid
part). **Controlled by time to close, the penalty is entirely in the early leg:**
tau 31-45, young -4.34c/contract and 6 of 74 closes lost vs older +3.05c and 0 of
42; tau 11-30, +1.75c vs +0.33c; tau <=10, +5.55c vs +5.74c (27 and 12 closes --
too few to read). So: buying younger is bad out at 31-45 s, and shows no penalty
inside 10 s. If speed is ever bought, that is where the evidence says to spend
it, and the 31-45 s leg is where it would hurt.

**Verdict: SURVIVES.** Don't buy speed for races; our own fills, not the tape,
now carry that conclusion.

---

## Checked and NOT supported

- **"A failed market-list GET blanks a coin inside the money window."** 15 such
  skips in 14 days outside the known outage, none within 467 s of a close.
- **"A market already holding its full early leg gains nothing from the counter
  fix."** True for only 2 of 34 lockouts; 32 had real room.
- **"The `hedge_quote` gap check disproves the 0.9 s stall."** It cannot: a
  sub-1 s stall can never skip a whole second of records.

## Could not measure

- Whether a locked-out market would have passed `confidence`/`edge_floor` at
  tau<=30 -- needs the model's fair per second, so every C1 dollar is an upper
  bound for that reason too.
- Fill probability on any missed offer: we never sent, so nothing in our own
  fills speaks to it.
- The hedge cost of the 4.3% blind window: no loop-pass timing is logged.

## How each candidate should be tested

- **C1 (full fix):** paper arm with the two increments moved to just before the
  send, synced to live settings, and a pinned scorer that tracks the ADMITTED
  class separately (fills whose market had a burner refusal that close). Bar,
  written before reading: the admitted class must not lose more closes than the
  ordinary tau<=30 class over >=30 admitted closes. Freeze-legal now: log the
  count of orders actually SENT on every `market_attempts` refusal.
- **C1 (narrow version):** same arm, flag limited to `staged_none`/`price_band`.
- **C2:** log `uni_ms` and the loop's maximum pass gap per close (freeze-legal,
  blocks nothing); bar = no pass gap > 200 ms inside tau <= 45.
- **C3:** nothing to test; it is a decision not to build.
