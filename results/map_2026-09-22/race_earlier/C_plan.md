# race_earlier / C_plan -- the paper arm, and the bar written before it runs

Status: PLAN ONLY. Nothing live changed, no size changed, no code written, no
process touched. Read-only session. Collectors alive (`kalshi_collector.py` pid
105304, `crypto_feeds.py` pid 105352); free disk 26.5 GB.

Inputs: `A_find.md` (the idea), `B_verify.md` (VERDICT: WEAKENED -- the idea
survives, three of its numbers do not), `08_coin-race.md`, VERSIONS entries
v-race90 / v-race30 / v-race-rolling, `research/pinracearm.py`,
`research/pinracefair.py`. New measurement of my own in section 7.

**The rule is WEAKENED, not refuted, so this file defines the arm.** It uses
B_verify's corrected version, not A_find's.

---

## 1. The rule being tested

**`arm-race-z3-above30`: open the coin-race penny rule out to 60 seconds, but
above 30 seconds only enter races where the leader is at least 3 standard
deviations clear of EVERY other coin -- and it must stay that way through all
five confirmation seconds.**

In plain words: further out, only bet on a race that is not close. "3 standard
deviations clear" is the same model the bot already prices with, asked a
different question: how big is the leader's lead compared with how much the gap
can still move in the seconds that are left.

Everything else is exactly today's live penny test: 1 contract a leg, 90c floor,
98c ceiling, edge >= 0, confirm-5-seconds-or-clock-20, the per-race consistency
rule, the $20 open-stake cap.

**It blocks nothing inside 30 seconds** -- it is a strict superset of what runs
live today. **It blocks nothing hedge-related: the coin race has no hedge.**

Tape evidence for it (market-did, not our loss rate; lag 0, live arming,
24.7 days, B_verify section 6): 853 races (34.5/day) against today's 586
(23.7/day); 6 losses, the same six, **all inside 30 s; 0 of the 366 new early
races lost**; 1.02% -> 0.70%. Our own fills, n = 2 losers: both our real losing
races above 30 s were at 1.09 and 1.58 sd; our 4 real races above 30 s at 3 sd
or better all won.

Threshold as a range, not a point: **2.5 / 3 / 3.5 are indistinguishable** on
this data (incremental P = 0.027 for 3 over 2.5, P = 1.0 for 3.5 over 3). 3 is
the middle. The arm logs the number continuously so the threshold can be
re-chosen from ITS data rather than re-fitted on the tape.

## 2. Existing flags CANNOT express this arm. Two things are missing

I read `pinracearm.py`'s argparse (lines 1079-1131). Every existing flag:
`--selftest --minutes --size --min-edge --log --tau-max --min-gap-bp
--min-price --model --one-per-race-band --live --max-contracts --max-stake
--live-tau-max --live-min-price --live-confirm --live-clock-tau
--live-rolling-stake --live-max-legs`.

Missing 1: **there is no z floor of any kind.** `live_fair()` (line 480) builds
the covariance and the projected returns and then throws both away, returning
only `{coin: P(win)}` and the ruler name. A_find is right that it must NOT be
read off `win_probs` -- that is 1,000 random draws and cannot resolve 0.1%.

Missing 2: **the paper path is not the live rule.** Without `--live`, a leg
never reaches `arm_leg` / `live_refusals` / `confirm_refusal` (line 1552's
`if LIVE["on"]`), so a paper arm has no confirmation, no per-race leg
consistency and no `--live-*` rails. B_verify measured that this changes the
answer: the same floor scored at the fire second alone loses 1 of 554 early
races; served through the confirmation it loses 0 of 366. A paper arm built
from existing flags would be testing a looser rule and its bar would mean
something else.

So the arm needs **three new flags and one new number**, specified below. I did
not write any of it.

### 2a. `--min-z FLOAT` (default 0.0 = off)

Race-level floor on `zmin`. Applies to the paper path and the live path alike,
so a paper arm and a real-money version are the same rule.

### 2b. `--min-z-tau INT` (default 30)

The floor applies only when `tau > this`. At 30 seconds or less nothing changes.
This is B_verify's V7 and it is load-bearing: inside 30 s the settlement
variance has collapsed, so a fifth of a basis point reads as "3.6 sd". Three of
the six inside-30 losers survive a z >= 3 floor on leads of 0.19, 1.48 and
4.64 bp, while the floor throws away 10 of our own 15 inside-30 races. **z is
the wrong ruler at small tau.**

### 2c. `--paper-live` (store_true; mutually exclusive with `--live`)

Runs the **entire live decision path** -- `arm_leg`, `live_refusals`,
`confirm_refusal`, `inconsistent`, `--live-tau-max`, `--live-min-price`,
`--live-max-legs`, the stake caps -- and **never calls `pintake.take`**. At the
point where `live_order` is written, it writes `live_paper` instead, with the
same fields plus `would_fill = min(want_n, have)` at the seen ask, and appends
to `live_pos` so `live_settled` scores it exactly as today.

Three details that are not optional:

- **`stop_on_loss` must be FALSE in this mode**, and the `start` record must say
  so. The live test halts on its first loss on purpose; an arm that halts can
  never reach 125 races.
- **Skip the REST last look** (`pintake._get` at line 1583) and record
  `fresh_ask: null`. Measured today: across 54 real sends and all 3,548
  `live_refused` records in `results/pinracepenny-live.jsonl`, the fresh read
  has refused **0** sends -- so skipping it does not change the population, and
  it saves an authenticated request per would-send.
- It must not write to `pintake.LEDGER` or to any live state file.

### 2d. The new number: `zmin`, computed analytically

In `live_fair()`, where `c = F.pick_cov(ser, now, which)` and
`rnow = [log(rets[k]) for k in F.COINS]` already exist:

```
k    = F.var_factor(tau)            # already computed for win_probs
L    = argmax(rnow)                 # the leader
z_j  = (rnow[L] - rnow[j]) / sqrt(k * (c[L][L] + c[j][j] - 2*c[L][j]))
zmin = min(z_j over j != L)
```

That is the same covariance, the same variance collapse and the same projected
returns `win_probs` uses one line later -- no new model. Return
`(probs, ruler, zmin, {coin: z_j})` and cache it in the existing
`fair_cache[(evt, tau)]`, so it costs nothing per second.

**Null discipline:** if the denominator is zero, negative or non-finite, `zmin`
is `None`, and `None` **fails** the floor. Never treat it as passing. This is
the same rule the file already applies to `worth` (line 569: "None worth is
None edge -- never a number, so it can never clear a floor").

`zmin` is race-level and side-independent: the same number blocks the leader's
YES and a trailing coin's NO. That is deliberate -- the paper loss
`26SEP211830` was a NO leg whose own confidence was 98.6% inside a three-way
tie whose race `zmin` was 0.09. A leg-level gate does not stop it; a race-level
one does.

### 2e. Where the gate goes, and the disarm that makes it part of qualifying

In the leg loop, in the same `bad` chain as `thin_edge` (lines 1468-1481),
after the edge test:

```
elif a.min_z > 0 and tau > a.min_z_tau and (zmin is None or zmin < a.min_z):
    bad = "zmin_under_floor"
```

and, before the `continue` that follows, **when the z gate is the reason**:

```
LIVE["armed"].get(evt, {}).pop((coin, side), None)     # restart the clock
```

That single line is the difference between 1 loss in 554 and 0 in 366.
`arm_leg` records the tau a leg FIRST qualified at and never clears it, so
without the pop a leg that drops under 3 sd for a second and comes back still
fires on its original clock. **Confine the disarm to the z gate** -- making
every gate disarm would change how the live bot's other rails behave, which is
not what was measured.

### 2f. Self-test (the deliverable, per CLAUDE.md)

Plant the answer and fail if it is missed, and fail if it fires on nothing:

1. `zmin` arithmetic on a hand-built 2-coin covariance: known lead, known sd,
   known z.
2. At tau 45: a 3.5-sd race passes, a 2.5-sd race is refused
   `zmin_under_floor`. At tau 25 both pass (`--min-z-tau 30`).
3. The disarm: a leg qualifying at tau 50, 49, 48, 47, failing z at 46, passing
   at 45 must **not** fire at 45, and must fire at 41.
4. `zmin = None` never fires at any tau above the band.
5. `--paper-live` never reaches `pintake.take`: assert on the source **anchored
   with `rindex` after the `def main(` offset**, the way lines 1009-1018 already
   do -- a self-test that searches this file finds its own copy of the literal
   otherwise (this has bitten four times).
6. `--paper-live` together with `--live` exits non-zero.
7. `--min-z 0` reproduces today's decisions byte-identically on a replayed
   race (the off switch is the revert).

## 3. The arm, as it would be launched

Same box, same launcher pattern as `start_arms.ps1`. **Same size as the live
test: 1 contract.**

```
python -u research\pinracearm.py --paper-live ^
  --minutes 10080 --size 1 --max-contracts 1 ^
  --max-stake 20 --live-rolling-stake ^
  --live-tau-max 60 --live-min-price 0.90 --live-max-legs 5 ^
  --live-confirm 5 --live-clock-tau 20 ^
  --min-z 3.0 --min-z-tau 30 ^
  --model fair --tau-max 60 --min-price 0.80 --min-edge 0.00 ^
  --log results\pinracearm-z3.jsonl
```

That is the live penny argv from HANDOFF.md line 34 with exactly four changes:
`--live` -> `--paper-live`, `--live-tau-max 30` -> `60`, `--minutes 1440` ->
`10080`, plus `--size 1` and the two z flags. Nothing else moves. **The live
penny test keeps running unchanged at `--live-tau-max 30`**; the arm is the
control-and-treatment in one process, because it enters inside 30 s on exactly
today's rule and above 30 s only under the floor.

## 4. The pre-registered bar -- written now, before any of the arm's output exists

**Window** starts at the arm's first `start` record carrying `min_z: 3.0`. A
restart continues the same window only while the argv is byte-identical (the
`start` record carries it); any argv change starts a new window and voids the
count.

**Unit is a RACE** (one quarter-hour event), never a leg, never a trade.
- A race is **EARLY** if the arm's first entry in it came at tau 31-60.
- A race is **INSIDE** if its first entry came at tau 2-30.
- A race entered in both counts once, as EARLY (that is the thing being tested).
- A race is **LOST** if any leg the arm entered in it lost (`live_settled`
  legs with `win` false).

**Statistic:** losing races among EARLY entries, with the same arm's INSIDE
entries as the matched control (same process, same seconds, same regime).

### Validity gates -- checked BEFORE the result is read

1. `min_z: 3.0` and `min_z_tau: 30` appear in the arm's `start` record, and
   `zmin` is present on its entries.
2. **The flag actually fired:** at least 30 races were refused
   `zmin_under_floor` above tau 30. (Memory rule: an arm must have exercised its
   flag. A51 read +201% on a flag it had never once used.)
3. **The arm mirrors live below 30 s:** on races both processes covered, their
   INSIDE entries agree on at least 80% -- head to head, not by totals. A
   mismatch means config drift, not a result.
4. Races in periods where the arm logged `cannot_evaluate` (no index, no
   covariance) are excluded from both bands.

### PASS (both conditions)

- **P1 -- absolute:** 125 EARLY races with 0 losses, **or** 250 with at most 1,
  **or** 375 with at most 2. Exact 95% upper bounds: **2.37%**, **1.88%**,
  **1.67%** -- all under the **2.42%** break-even at the 97.4c average price.
- **P2 -- relative:** the EARLY loss rate is not worse than the same arm's
  INSIDE rate at one-sided Fisher p < 0.05. This exists to catch "3 of 200 early
  against 0 of 300 inside", which P1 alone would let through at 375.

### KILL (either)

- **K1:** 2 EARLY losses within the first 50 EARLY races.
- **K2:** 3 EARLY losses at any point before P1 is met.

### Looks

Score **weekly**, and at the moment either bar is crossed. No other looks. The
interim numbers decide nothing before their n, the way `FREEZE_bars.json`
already treats every other bar here.

### Operating characteristics (computed, not asserted)

| if the truth is | P(PASS at 125 with 0) | P(false KILL, 2 in first 50) |
|---|---|---|
| 0.29% (the index's rate at this floor) | **70%** | 0.9% |
| 0.50% (the holdout regime) | 53% | 2.6% |
| 1.00% | 28% | 8.9% |
| 3.00% (above break-even) | 2% | **44%** |
| 5.00% | 0.2% | **72%** |

So the bar is honest in both directions: it rarely kills a good rule and it
catches a 3-5% truth about half the time inside 50 races.

### Timeline

11-15 qualifying EARLY races a day. **125 EARLY races is 9-11 days; 250 is
17-23 days.** Cross-check from our own logs rather than the tape (section 7):
the live process's own paper side recorded a 90-98c entry at tau 31-60 in **41
of the 134 races it covered** on 09-21..09-22 -- about 29 early races a day
before any floor, against the tape's 30.4/day unfloored. The floor keeps about
half.

## 5. What a PASS would allow, and what it would block

**Allow (the operator's call, not automatic):** a real-money version of the
existing penny test -- `v-race-z3` -- which is today's live argv with
`--live-tau-max 60 --min-z 3.0 --min-z-tau 30`. **Still 1 contract.** It adds
about 11-15 races a day at a median 98c ask.

**A PASS would NOT allow raising the size.** Size stays at 1 contract until the
existing inside-30 bar resolves (160 loss-free races, or 337 with 2 or fewer --
report 08 F8), and that is a separate decision the operator makes.

**Blocks, in the live version:** only entries at tau 31-60 in races whose leader
is under 3 sd clear -- every leg, YES or NO. **Nothing inside 30 seconds.
Nothing hedge-related: the coin race has no hedge.** No pin-bot behaviour of any
kind is touched.

**A KILL** closes the far band again: `--live-tau-max` stays 30, and `zmin`
stays as a logged number for the next question.

## 6. What it is worth, and the three ways this bar can still mislead

**Worth:** the arm itself makes **$0** -- it is paper. The real-money version it
could unlock is **+$0.34/day at 1 contract** on the tape (B_verify section 6:
+$1.03/day against today's +$0.69/day). That is a measurement, not a business.
The product is the number in three weeks.

1. **Regime.** The index says this floor ran at 0.11% in the recent half and
   **0.52%** in the holdout half, and the **unfloored** far band ran at 2.50% in
   the holdout -- above break-even. A forward test starting today starts in the
   friendliest fortnight in the sample. A PASS is a PASS in one regime.
2. **Fills, and this is the part no paper arm can see.** Our own races above
   30 s lost **2 of 15 (13%)** where the tape says 1.20% -- a 10x gap, the same
   direction and the same order as the pin bot's 31x. Both real race losses
   filled at prices a once-a-second tape never shows (93c seen, 85c paid; an 86c
   offer that lived 0.1 s). **The floor picks which races we are in; it does
   nothing about the fill.** The arm books the seen ask and therefore cannot
   produce a fill-risk number at all. That is why the real-money follow-on
   carries one extra kill that the paper arm cannot: **kill on any early loss
   whose fill came 2c or more under the decision price** -- the pickoff
   signature from report 08 F2/F3.
3. **Multiple looks.** A_find's scripts printed on the order of 1,000 cells
   against 12-14 losers. A strict Bonferroni bar is p < 5e-5 and the best
   statistic anyone produced is p = 0.0016. **No cell here survives strictly.**
   The forward bar above is the only honest arbiter, and it is one bar with one
   statistic, fixed before the arm exists.

## 7. Do this now, whatever else happens -- and it costs nothing

**Log `zmin` and the four pairwise z's on every race record that already
exists** (`fill`, `no_trade`, `live_refused`, `live_order`) in the live penny
process and in the paper arms. It is one field, it changes no decision, and
without it the next version of this measurement is another rebuild of the tape
instead of a read of our own decisions.

It is not free of process, though: it touches the running live penny test, so
it needs a restart and a `results/VERSIONS.md` entry. **That is the operator's
call, not this job's.** The arm in section 3 carries the logging anyway, so
nothing is blocked if the answer is no.

New, measured in this session (read-only, `results/pinracepenny-live.jsonl`):

- **The REST last look has never refused anything.** 54 real sends, 3,548
  `live_refused` records, **0** mentioning the fresh read. v-race90's second
  half has bought us nothing so far, which matches report 08 F3 -- and it is why
  `--paper-live` can skip it without changing the population.
- **Live fires the instant tau hits the bar**, exactly as B_verify's V2 says:
  of 54 real orders, **11 are at tau 30 exactly** (the `--live-tau-max 30` bar)
  and 10 at tau 55 (the old 60 bar, 5 confirmation seconds later). Any arm whose
  entry logic forbids firing in the top seconds of its band is not this bot.
- **Our own coverage:** 134 races covered 09-21 08:59Z..09-22 17:44Z; 41 had a
  90-98c paper entry at 31-60 s, 10 inside 30 s, 5 in both.
