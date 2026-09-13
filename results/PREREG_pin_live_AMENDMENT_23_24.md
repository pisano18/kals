# PRE-REGISTRATION — AMENDMENTS 23 and 24

**Written 2026-09-13, BEFORE either what-if has produced a single fill.**
That ordering is the whole point: CLAUDE.md's 2026-09-10 amendment forbids
deploying a threshold from a replay without a holdout split *and* a live bar
written before the number is seen. The replay numbers below are already known
and are stated here so they cannot be quietly restated later; the **live bars**
are the new thing, and nothing in this file may be edited after the first fill.

Both amendments are **OFF in the live bot right now.** Live runs
`--size 20 --loss-abort -60.00 --max-positions 3 --max-losses 3
--improve-scope market`, which is exactly what it ran before this work.

---

## Where these came from

The operator, 2026-09-13, asked two things and attached a condition:

> "NO you can buy the same coin again if all the metrics line up and it's
> something you'd usually buy and it's under the contract threshold, because
> if it's really going to flip then the confidence should be dropping. Can you
> check and see if this is really the case and what's better, then implement
> that, do what's best"

> "And I'm not certain if it should take the first or scan for the best
> because prices move quick but also what if there's better options so I'm not
> sure. Is that calculatable? Do what's best, implement that"

> "For both of those make sure your work is 100% right and accurate as they
> could be very very bad to get wrong."

**One measurement was thrown away before any of this.** The obvious source,
`results/pinlevels_rows.jsonl`, is CENSORED for the first question: a row is
only written once the model is already certain, so its minimum confidence
across 16,683 rows is 0.995002 and "confidence never fell below the gate"
comes back as 0 of 16,683. That is a fact about the file, not the world, and
it would have confirmed the operator's premise beautifully. It is not used.

---

## AMENDMENT 23 — the re-buy band

**Change.** `MAX_PER_MARKET` may exceed 1, and a same-market second buy is
allowed only when it is cheaper by at least `IMPROVE_BY` (0.5c, AMENDMENT 3's
existing floor) and **no more than `IMPROVE_MAX` (1.0c)**. Implemented as
`pinrun.rebuy_ok()`, called from the trade loop. Default `MAX_PER_MARKET` is
still 1, so live behaviour is unchanged.

**Replay evidence, already seen** (`research/pinpick.py`, 13,984 gate-passing
candidate rows → 1,260 markets on 738 closes):

| how much cheaper the second buy was | markets | lost | loss rate | 2nd leg |
|---|---|---|---|---|
| 0.5–1c  | 142 | 1  | **0.70%**  | **+3.08c** |
| 1–2c    | 141 | 8  | 5.67%      | −0.09c |
| 2–5c    |  87 | 10 | 11.49%     | −4.92c |
| 5–10c   |  23 | 6  | **26.09%** | **−11.45c** |

Break-even is 3.58%. Holdout on close time, last 40% never fitted:
1.79 / 6.06 / 21.21 / 44.44%. Markets where **no** cheaper second ever
appeared: 862, of which **0 lost**; where one did: 398, of which 25 lost
(+6.28pp, 95% CI [+3.46, +9.82] bootstrapped over CLOSES).

**The supporting measurement, and its limit** (`research/pinwarn.py`, 18,653
closes rebuilt from the index with nothing filtered): confidence falls below
the gate on **31 of 31** closes the model gets wrong, and on only 0.4% of the
ones it gets right. But it falls LATE — 11 of 18 by tau 25, 12 of 19 by tau 20.
On our own money it was later still: SOL 2026-09-12 23:00 was bought three
times at tau 30/29/28 while confidence ROSE 0.9994 → 0.9997 → 0.9998, and the
flip only appeared around tau 12. **So the operator's premise is true and too
slow to act on. The price is the fast signal; the confidence is not.**

**Caveat carried forward, not buried.** Those loss rates are the tape's, whose
population is "an offer was sitting there" and not ours (rule 5). What is
relied on is the ORDERING and the fact that the groups differ — statements
about what the market did, which the tape is valid for.

### THE LIVE BAR for A23

Scored on the paper run
`--size 20 … --improve-scope market --max-per-market 2 --improve-max 0.010`
against the live bot over the same closes.

A23 goes live only if **all four** hold:

1. **≥ 30 closes** in which the what-if actually took a second leg. Fewer than
   that and the answer is "no power", which is not the same as "no effect".
2. The **second legs alone** return **≥ 0.0c per contract**. They are extra
   money on an outcome already owned, so a negative number is a straight loss
   however the close ends.
3. The what-if's **total P/L exceeds the live bot's** over the shared closes.
4. The what-if's **worst single close** is no worse than the live bot's. The
   contract budget says it cannot be; if it is, the budget is not doing what
   AMENDMENT 17 claims and that gets fixed before anything ships.

If (1) fails, the run continues. If (2), (3) or (4) fails, A23 is **struck**,
not retuned — retuning `IMPROVE_MAX` against the run that judged it is exactly
the loop this file exists to prevent.

---

## AMENDMENT 24 — best-first scan order

**Change.** `PICK = "best"` orders each scan pass by the net edge measured on
the **previous** pass (50ms earlier at 20Hz), so when two markets pass the gate
in the same second the better one is reached first. Nothing is computed twice
and no order is deferred. Default is still `"first"`.

**Replay evidence, already seen** (`research/pinpick.py`): 2+ different markets
pass in the same scan second on **6.3%** of passes; when they do, the first one
seen is the best-edge one only **56.3%** of the time, giving up a mean 2.10c of
edge (median 0.28c, p90 7.43c) and paying 2.21c more. Replayed at one contract
per close: **+2.07c → +2.76c per contract on identical loss counts (10 and
10)**. Holdout, last 40% of closes never fitted: **+1.63c → +2.43c, loss counts
6 and 6.** "Highest confidence" reaches only +2.19c — the gain is price, not a
different risk appetite.

**What would make it an artefact:** if best-edge were simply picking adversely
selected offers, the loss count would rise with the P/L. It does not, in either
half. That is the check, and it passed; it is not proof, because both arms are
tape arms.

### THE LIVE BAR for A24

Scored on the paper run `--size 20 … --improve-scope market --pick best`
against the live bot over the same closes.

A24 goes live only if **all three** hold:

1. **≥ 30 closes** on which the two arms bought **different markets**. If the
   arms almost never diverge, the change is real but worthless and is not worth
   a live edit.
2. On those closes the A24 arm's **mean price paid is strictly lower**.
3. On those closes the A24 arm's **loss count is no worse than live + 1**.

If (1) fails the run continues. If (2) or (3) fails, A24 is **struck**.

---

## What is being risked while these run

Nothing. Both what-ifs are `MODE PAPER` — no `--live`, so `pintake.take()` is
never reached. The only cost is ~56 MB of RAM each and the log files. The
collector and `crypto_feeds` were verified alive after both were started
(33 MB and 21 MB), free disk 36.3 GB, free RAM 4.7 GB.
