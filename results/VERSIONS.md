# Live strategy versions — what is running, and how to go back

**Every change to what trades real money is listed here with its git SHA, the
evidence, and the exact command to revert.** Newest first.

---

## HOW TO USE THIS FILE — read before adding a version

**Every change to what trades real money gets an entry here, at the moment it
is deployed, not afterwards.** The log lapsed between 2026-09-11 and
2026-09-13 while eight live changes went out; the back-fill below was written
from git on 2026-09-13 and is thinner than it should be, which is exactly the
cost of letting it lapse.

An entry needs five things and nothing else:

1. **A version tag** `v-<short name>`, and the same tag in the deploy command.
2. **The UTC time it went live** and the **git SHA** it was deployed from.
3. **What changed, in one sentence**, in terms of what the bot now does
   differently.
4. **The evidence**, or the honest absence of it, with the pre-registration
   filename if there is one.
5. **THE EXACT REVERT COMMAND.** Not a description of how to revert. The
   command, copy-pasteable.

`research/versioncheck.py` fails if `restart_bot.ps1` carries a flag that no
entry mentions, so a live change without an entry is caught rather than
remembered. Run it in any session that touches the live bot.

---

## v-a24 — 2026-09-13 22:2xZ — AMENDMENT 24: buy the BEST market of the second, not the first one reached (`6d85371`)

**What the bot now does differently.** When two or more markets clear every
gate in the same scan second, it buys the one with the most edge instead of
whichever the loop happened to reach first. Also deployed in the same restart:
AMENDMENT 25, which makes every gate record why it refused a trade (logging
only — it decides nothing).

**Evidence.** `research/pinpick.py` over 13,984 gate-passing candidate rows on
738 closes. Two or more different markets pass in the same second on **6.3%**
of passes; when they do the first one reached is the best-edge one only
**56.3%** of the time, giving up a mean 2.10c of edge and paying 2.21c more.
Replayed one contract per close: **+2.07c → +2.76c per contract with IDENTICAL
loss counts (10 and 10)**. Holdout on close time, last 40% never fitted:
**+1.63c → +2.43c, six losses either way.** Ranking by confidence instead of
edge reaches only +2.19c, so the gain is price and not a riskier appetite.

**Why it adds no risk and loses no race.** The ordering comes from the edge
measured on the *previous* pass, 50ms earlier at 20Hz. Nothing is computed
twice and no order is deferred. The old order was dict insertion order — the
one gate in this bot that was never an EV comparison. Every gate still has to
pass; only the sequence changed.

**What is NOT deployed:** `--max-per-market` (AMENDMENT 23). It pays, but it
concentrates a close on one coin, and the operator's condition was "if it's
good and does not raise risk". Still in a paper what-if against the bar in
`results/PREREG_pin_live_AMENDMENT_23_24.md`.

**REVERT:**

```powershell
cd C:\kals-repo
git revert --no-edit 6d85371
# then remove "--pick", "best" from the Start-Process line in restart_bot.ps1
.\restart_bot.ps1
```

To revert ONLY the scan order without losing the gate instrumentation, drop
`"--pick", "best"` from `restart_bot.ps1` and run `.\restart_bot.ps1`; the
default is `"first"`, which is the old behaviour exactly.

---

## NOT LIVE — AMENDMENT 23, in a paper what-if since 2026-09-13 21:5xZ

**Listed here because the FLAG now exists in `pinrun.py` and a future session
must not mistake "the flag is there" for "it is running".** `MAX_PER_MARKET`
is still 1 on the live bot.

- **AMENDMENT 23 — the re-buy band.** `rebuy_ok()`: a SAME-market second buy
  must be cheaper by at least `IMPROVE_BY` (0.5c) and at most `IMPROVE_MAX`
  (1.0c, `--improve-max`). Only reachable when `--max-per-market` > 1, which is
  still refused on `--live`.
  Paper run: `--max-per-market 2 --improve-max 0.010`.

**Why it is here and not live, when AMENDMENT 24 went live the same evening.**
The operator's condition was *"if it's good and does not raise risk, implement
it."* A23 is good and it DOES raise one risk: the contract budget caps the
dollars on a close either way, but allowing a second fill on the same coin
makes the close more likely to spend that whole budget on ONE outcome instead
of splitting it across two. Same worst case, reached more often. A24 had no
such cost — identical loss counts in both halves of the sample — so it went.

*(AMENDMENT 24 was in a paper what-if alongside this one from 21:5xZ and was
deployed at 22:2xZ; see the v-a24 entry above.)*

Evidence, bars and the strike conditions:
`results/PREREG_pin_live_AMENDMENT_23_24.md`, written before either run took a
fill. Measurements: `research/pinpick.py` (first-vs-best, and the re-buy band
with a 60/40 holdout on close time) and `research/pinwarn.py` (18,653 closes
rebuilt from the index, uncensored, on whether confidence warns before a flip).

**Revert (removes both flags from anything that could use them):**

```powershell
cd C:\kals-repo
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object {$_.CommandLine -like '*pinrun*' -and
                ($_.CommandLine -like '*--pick*' -or
                 $_.CommandLine -like '*--max-per-market*')} |
  ForEach-Object { Stop-Process -Id $_.ProcessId }
```

That stops the two paper runs and touches nothing else — the live bot carries
neither flag, and the filter requires one of them.

---

## v-a22 — 2026-09-13 19:3xZ — AMENDMENT 22: a second COIN at the same close is allowed on its own merits

**What changed.** `--improve-scope market`. The improve-by rule no longer
blocks a different coin.

**The operator, watching the live bot take ETH and skip HYPE while the what-if
took HYPE:** *"I would've hoped my bot would grab eth, then when hype looks
like a good buy it'd see that and scoop it up too."*

**What happened at 19:15Z.** The bot filled ETH at 98.0c. HYPE was then offered
at 97.7c with **2.14c of edge — a better trade than the one it took** — and was
refused, because 97.7c is not at least 0.5c below 98.0c.

**Why that is a bug and not a design choice.** AMENDMENT 3 wrote the improve-by
rule for SCALING INTO THE SAME MARKET: *"re-buying at the same level would
double the risk without lowering the average paid."* AMENDMENT 13 then set
`MAX_PER_MARKET = 1`, which forbids re-buying the same market at all. **Since
2026-09-12 the rule has been unable to do the job it was written for.** The
only thing it can still do is block a different coin — which it was never meant
to touch — and AMENDMENT 17, the same day, says a close is capped on CONTRACTS
with *"coins unlimited"*. The rule was silently contradicting it.

**Why this does not add risk, and why it is not the ruler.** The close's
contract budget is unchanged: `MAX_PER_CLOSE * SIZE` either way. Two coins at
47 contracts is the same 94 contracts as one coin at 94 — **identical worst
case**, only which markets get bought changes. And because coins at one close
correlate at rho ~0.8 rather than 1.0, splitting the same budget across two
markets can only reduce the chance that all of it loses together.

That is why this went live directly while the ruler went to a what-if: the
ruler was a statistical bet on a population that is not ours, with a measured
cost in volume. This is a code-reading, its exposure is provably unchanged, and
every trade it adds passes every existing gate.

**Revert:** remove `"--improve-scope","market"` from `restart_bot.ps1`.

---

## v-revert1 — 2026-09-13 18:49Z — AMENDMENTS 20, 20b and 21 REVERTED (operator call)

**What changed.** `--sigma-ruler` and `--pin` removed. Back to the 300-second
ruler and the 0.995 gate. **The sweep (v-a18) stays** — it is separately
evidenced, needs no flag, and is 3 for 3.

**Why.** The operator: *"I have barely seen any trades since I woke up and
cannot see how that's smarter... I'm having a very hard time trusting this new
idea."*

He was right and the measurement backs him, not me:

| | signals per hour |
|---|---|
| today, before the ruler change | **4.21** |
| today, after it | **1.55** |

**A 63% cut in signals.** I had measured that cost in advance — 46.6% of
signals, from re-scoring 619 real ones — and deployed anyway, then tried to
buy the volume back by loosening the gate, which is a second change to fix the
first.

**The asymmetry I should have weighted properly the first time.** The ruler's
COST is measured on our own real signals and is certain. Its BENEFIT is
measured on the index population, and CLAUDE.md rule 5 exists precisely because
that population is not ours — it differs by 31x on the one number we care
about. Certain cost, unproven benefit, no forward evidence after 7 hours. That
is a bad trade whoever proposes it.

**What is NOT concluded.** The ruler may still be right — `RESULTS_ruler.md`,
`RESULTS_calib.md` and `RESULTS_flood.md` all stand, and the model's tails
really are 8x too thin. What is concluded is that it may not be deployed on
index-population evidence alone. It needs a test that costs nothing while it
runs.

**Next step for it, if it is revisited:** score the ruler in SHADOW against
live signals — recompute what it would have said at each real decision and
compare, without touching what trades. That is `pinshadow`'s method applied to
the ruler, and it should have been built before the deploy, not after.

**Revert of the revert:** add back `"--sigma-ruler","maxdown","--pin","0.990"`
in `restart_bot.ps1`.

---

## v-a21 — 2026-09-13 17:0xZ — AMENDMENT 21: the confidence gate 0.995 → 0.990

**What changed.** `--pin 0.990`. The gate the model must clear before a trade
is considered.

**Why it is a partial REVERT, not a new bet.** v-a20b moved this gate without
touching it: a wider ruler lowers every stated confidence, so the same PIN
became a stricter gate overnight. Measured — the new ruler reads a median
**1.167x wider** (2,666 tape samples), and re-scoring **619 real live signals**
through `z -> z/1.167` shows it cost **46.6% of them**. Lowering PIN to 0.990
gives back most of that volume at the same expected money.

**Evidence.** `results/PREREG_ruler.md`, amended before this deploy. Both 0.995
and 0.990 are worth the same expected $/hour; 0.990 keeps 83% of trades against
53%, so it leans a third as hard on the one number rule 5 says cannot be
assumed to transfer — that a loss reduction measured on the index population
applies to fills someone chose to sell US.

**Also recorded:** the index population said tightening 0.995 → 0.998 costs
0.7% of decisions; on real signals it costs 51%. A 70x error. That population
may compare rulers and may NOT count trades.

**`--pin` may only LOWER the gate** — outside [0.95, 0.995] it refuses to
start. Raising it needs a code change and a version entry, not a flag.

**Revert:**

```powershell
# edit restart_bot.ps1: delete the "--pin","0.990" arguments
powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo
estart_bot.ps1
```

---

## v-a20b — 2026-09-13 11:57Z — AMENDMENT 20b: the ruler reads DOWN moves only (`9591ec8`)

**What changed.** The volatility estimate is now `max(downside 300s, downside
1800s)` instead of `max(two-sided 300s, two-sided 3600s)`. The model's claim is
one-sided — the settle lands on its side of the strike — and we lose only when
the index comes in the other way, so a ruler built from both directions spends
half its information on moves that cannot hurt us.

**Evidence.** 45 rulers scored over 108,000 decisions rebuilt from the index
alone (`results/RESULTS_ruler.md`). Beat the ruler deployed 47 minutes earlier
on every axis in both halves: gated loss −48.5% vs −42.3%, sd(z) 0.950 vs
0.919 (1.000 is honest), kurtosis 53.5 vs 69.1, decisions kept −0.9% vs −1.0%.
Bar and kill criterion in `results/PREREG_ruler.md`, including BAR ITEM 4
(hedge frequency) added 12:32Z before anything was scored.

**Known cost, measured 2026-09-13 on the 12:30 PM ET BNB close:** this ruler
read **40% wider** than the old one at that second (0.0271 → 0.0379). A wider
ruler pushes every belief toward 0.5 and the hedge fires below 0.80, so it
makes the hedge fire more readily. That is arithmetic, not a counterfactual —
whether that particular hedge would have fired under the old ruler could NOT be
reconstructed from the tape and is not claimed.

**Revert:**

```powershell
# edit restart_bot.ps1: delete the "--sigma-ruler","maxdown" arguments
powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo
estart_bot.ps1
```

---

## v-a20 — 2026-09-13 11:10Z — AMENDMENT 20: the volatility ruler lengthens (`a988c71`)

**What changed.** `--sigma-ruler max3600`: volatility measured over the larger
of 300s and 3600s instead of 300s alone. **Superseded by v-a20b 47 minutes
later; it took two fills.**

**Evidence.** `results/RESULTS_calib.md` and `results/RESULTS_flood.md`: the
calmer the last five minutes, the MORE often the model blew up (4.28% in the
calmest fifth vs 1.05% in the choppiest, 4.05x, holding out of sample) because
a quiet 300 seconds understates the next minute. Lengthening the ruler
collapsed that gradient from 4.09x to 1.15x and cut kurtosis 132 → 47.

**The deploy failed on my own guard and the bot was down ~4 minutes.** The
self-test asserted `SIGMA_RULER == "live"`, but `main()` applies the flag
BEFORE running the suite. Fixed by asserting the DECLARED default
(`_DEFAULT_SIGMA_RULER`) instead. The same latent bug was in AMENDMENT 19's
guard and was fixed at the same time.

---

## v-a18 — 2026-09-13 09:24Z — AMENDMENT 18: bid up to the gate, not to the ask (`986cc71`)

**What changed.** The IOC limit is now the highest price that still passes the
SAME gate, instead of exactly the ask we saw. When we win the race we still pay
the resting price; when we lose it we take the next level instead of buying
nothing.

**Evidence.** 28.2% of orders filled nothing and it was not latency — filled
and zero-filled orders have the same median latency, 96 ms. A crossing IOC
fills at the RESTING price: 283 of 283 live fills at or below the signalled
price, 76 strictly better, ZERO worse (RUNBOOK CONFIRMED FACTS). 43% of lost
races had a next level still inside the gate at a median +0.20c.
`results/PREREG_sweep.md` holds the bar.

**First three swept fills, all winners:** SOL 6:15 AM ET (85.0→87.0c, +$5.01),
XRP 7:00 AM (95.1→97.5c, +$0.98), BNB 12:30 PM (92.0→92.3c, +$2.30 on the bet
before the hedge). n=3 proves the mechanism, not the economics.

**Revert:** add `"--no-sweep"` to the argument list in `restart_bot.ps1`.

---

## v-brake3 — 2026-09-13 02:26Z — BANK_BRAKE 1.5 → 3.0 (`f04087d`)

Size is `bank / (BANK_BRAKE x 2 x 0.98)`. The worst single close falls from 64%
of bank to 32%. Operator's decision; the reason recorded in the commit is not
the one either of us first gave.

**Revert:** `BANK_BRAKE = 1.5` in `research/pinrun.py`, restart.

---

## v-a17 — 2026-09-13 01:49Z — AMENDMENT 17: a close is capped on CONTRACTS (`3f393ea`)

`MAX_PER_CLOSE x SIZE` contracts per close, coins unlimited, instead of a cap
on the number of fills. Same worst-case exposure under both rules.

**Revert:** set `CLOSE_BUDGET = False`; the old fill-count cap is kept behind
it for exactly this.

---

## v-a16 — 2026-09-12 23:13Z — AMENDMENT 16: SIZE follows the bank (`c0f8e33`)

Size is re-read from `/portfolio/balance` every 300 s while flat, so it grows
and shrinks with the account instead of being a fixed argument. `--size` became
a starting value only.

**Revert:** `--no-auto-size`.

---

## v-hedgefix — 2026-09-12 20:07Z — a partial hedge fill was shrinking the original position (`2ffb40d`)

**A correctness fix, not a strategy change.** A partial hedge fill silently
reduced the ORIGINAL position's settled size, which understated losses fed to
the loss-abort brake. Every loss number computed before this commit is
suspect.

---

## v-a15 — 2026-09-12 18:06Z — AMENDMENT 15: the belief-collapse hedge, threshold 0.80

When the model's belief in a held position falls below 0.80, buy the opposite
side. Recovers about one third of a loss; costs ~$1.29/day at size 20 and saves
money in bad stretches. `results/PREREG_hedge.md` holds the bar.
**On 2026-09-12 the railed holdout showed the base strategy NEGATIVE on 72
unseen hours with the hedge carrying it** (`aa257ce`), which is the single most
important caveat attached to any live version.

**Revert:** `HEDGE_ENABLED = False` in `research/pinrun.py`.

---

## BACK-FILL NOTE

v-a13 (one fill per market) and v-a14 are NOT reconstructed here — they were
deployed while the log was lapsed and the commits do not state deploy times.
`git log --grep "AMENDMENT 13"` is the starting point if either needs reverting.
This gap is the cost of letting the log lapse and is left visible rather than
guessed at.

---

## v-a12a — 2026-09-11 13:25Z — AMENDMENT 12a: scraps accumulate, exposure re-bounded (`9aa2014`)

**Found by auditing my own change rather than admiring it.** A12 said a scrap
fill spends no scale-in slot. With nothing else changed that DOUBLED the worst
case: `MAX_ATTEMPTS_PER_CLOSE` is 8, so eight scraps of 9.99 contracts would
each keep a position and none would spend a slot — **79.9 contracts, $78.32,
against an intended $39.20**, with only the run-wide $130 stake cap as a
backstop. That is a regression I introduced this morning.

**Fix:** scraps ACCUMULATE. Once they add up to a real fill (half our size)
they spend a slot exactly as one fill would. Measured in the self-test by the
only number that matters — contracts filled before the slots run out:

| scrap size | contracts before slots exhaust | intended |
|---|---|---|
| 9.99 | 39.96 | 40 |
| 5.0 | 20.00 | 40 |
| 2.0 | 20.00 | 40 |
| 0.5 | 20.00 | 40 |

and within the 8-attempt cap, 0.02 crumbs still spend **no** slot — the thing
A12 exists for.

**Two of my own test assertions were wrong before this passed**, both recorded
in place rather than quietly edited: I asserted 8 scraps of 9.99 spend 7 slots
(the code gives 4, and the code is right), and that 0.02 crumbs "never" exhaust
the slots (they do, after a thousand; the attempt cap is the real bound).
Asserting a bound that does not exist is worse than not asserting.

Restarted 13:25Z, pid 611172.

---

## v-a12 — 2026-09-11 12:40Z — AMENDMENT 12: a scrap fill is not a slot (`d3e2ef0`)

**What changed:** a fill smaller than half our size (under 10 contracts at size
20) still books its POSITION — it exists, settles and releases like any other —
but no longer spends one of the `MAX_PER_CLOSE` buys for that close and no
longer raises the improve bar. It is written as a `scrap` record. The side is
still recorded, so the both-sides guard holds. Nothing else changed.

**Why:** 2026-09-11 07:00 ET, the bot asked for 20 twice and got **2.0** (BNB)
and **0.02** (BTC) — the offer was gone by the time the order landed — and each
scrap consumed a buy for its close and raised the bar, blocking a real fill
behind it. `MIN_FILL_FRAC` gated what we ask for; nothing gated what we got.
This was already logged as open in SKIM.md ("dust fills burn a scale-in slot").

**Risk:** none to money — a scrap can only lose its own few cents. The change
can only ADD a real fill where a scrap used to block one. Self-tested
structurally (slot booked only when `filled >= _real`, scrap recorded) and on
the arithmetic (at size 20 the line is 10; 2.0 and 0.02 are scraps).

Restarted 12:40Z in the quiet window; pid 602652.

---

## v-a10c — 2026-09-11 12:45Z — the crazy-deal guard was WRONG IN BOTH DIRECTIONS; fixed (`65b0fc2`)

**A second loss (KXSOL15M 12:30Z, −$12.16) went straight through the guard**:
99.508% sure, filled at 59.1¢ — a **29.5¢ discount** — because the rule demanded
≥99.9% confidence. Scoring the guard on all 139 live fills then showed the
other half of the error.

| discount to fair at the FILLED price | fills | lost | loss rate | P&L |
|---|---|---|---|---|
| under 2¢ | 42 | 1 | 2.4% | −$2.11 |
| 2–5¢ | 64 | 2 | 3.1% | −$0.11 |
| **5–15¢** | **24** | **0** | **0.0%** | **+$32.20** |
| **15¢+** | **9** | **4** | **44.4%** | **−$12.41** |

**As deployed the guard cost −$10.49**: it refused 8 winners (+$29.22) to avoid
2 losers (−$18.73). A measurably negative rule does not stay — the operator's
own test.

**Two changes, and their evidence is NOT equal.**
* **Drop the confidence condition — NOT fitted.** The SOL loss proves the
  discount matters independent of confidence, and every trade already passes
  PIN, so "confident" carried no information.
* **5¢ → 15¢ — FITTED, and labelled so.** The 5–15¢ evidence is strong and
  one-directional (0 losses in 24 fills, +$32.20; refusing it was the guard's
  worst error). The 15¢ line itself was chosen after seeing 9 fills. It is kept
  only because no guard is also negative on that band (−$12.41) and because the
  operator decided to refuse deals this extreme. **It claims no significance.
  The pre-registered review at 40 records decides it on data it never saw.**

Restarted 12:45Z, pid 601412. Revert: `DUMP_ENABLED = False`.

---

## v-a10b — 2026-09-11 00:12Z — AMENDMENT 10 ON, BY OPERATOR DECISION; would-be outcomes recorded (`0c5f513`)

**Operator:** *"don't do the 'crazy trades', but track them with the 'would be'
outcome. Later they'll be reviewed when populated with more data. Leave the
program to continue."*

**What changed:** `DUMP_ENABLED = True`. A fill where the model is ≥ 0.999 and the
offer is more than 5¢ below fair is refused. **Every such moment writes one
`dumped` record per (close, market)** — ticker, side, price, fair, tau, discount,
depth — whether or not it is refused, so the would-be P&L resolves against the
settlement later. Everything else is v-pin995.

**The basis, stated exactly:** the EV of this class is **undeterminable** on the
six live fills (+$4.75, mean +$0.79, SE ±$4.1, t = 0.19). On an undeterminable tie
the owner chose fewer losses. **This is a recorded owner decision, not a claim
that refusing is profitable.** The 40-fill evaluation stands: refuse stays only
if the 95% CI on mean would-be P&L is not entirely above zero; if it is, the
class comes back. Cumulative P&L is never the trigger.

**To resolve would-be outcomes:** join `dumped` records to settlements on ticker
— the same join `pinrace.py` does for orders.

**Revert (buy them again):** `DUMP_ENABLED = False`, stop/start per RESTART.md.

Restarted 00:12Z; pid 439076.

---

## v-a10a — 2026-09-10 23:51Z — AMENDMENT 10 SWITCHED TO LOG-ONLY: the math does not support it (`82f2656`)

**What changed:** `DUMP_ENABLED = False`. The guard still COUNTS every fill it
would have refused (`dumped` in the close summary) and refuses none. Trading rule
is back to exactly v-pin995. Live for 13 minutes (23:38–23:51Z); no fill was
refused in that window.

**Why it came off — the operator's rule, applied:** *if it is profitable do it,
if not don't; if the math is not certain, don't use it.* The six live fills of
this class: +15.36, +3.78, +2.82, +1.52, −16.61, −2.12 = **+$4.75, mean
+$0.79/fill, standard error ±$4.1, t = 0.19. The sign is not determinable.**
Refusing is not certifiably profitable; neither is buying. The frozen baseline
(buy) therefore stands. v-a10 was deployed on a loss-frequency preference
dressed as a decision, and that was wrong.

**The metric, settled:** `CLAUDE.md`'s own kill criterion defines "consistent"
as positive expectancy. Variance matters only through ruin, and this class
cannot cause ruin at size 20 (≤ $19.60 per fill, brakes intact). So the
criterion is EV alone; EV is unknown; the class is ~3 fills/day, so the decision
is worth ~$2/day either way and does not merit a rule until it can be measured.

**PRE-REGISTERED EVALUATION, fixed now:** at **40 fills** of this class (model
≥ 0.999 and offer > 5¢ below fair), refuse only if the 95% CI on their mean P&L
lies entirely below zero; keep only if entirely above; otherwise re-evaluate at
80. **Cumulative P&L is not a trigger** — a bar moved by outcomes is not a bar.

**Revert to v-a10 (refusing):** `DUMP_ENABLED = True`, stop/start per RESTART.md.

Restarted 23:51Z in the quiet window after the 23:45 settlement; pid 445008.

---

## v-a10 — 2026-09-10 23:38Z — AMENDMENT 10: never buy a certainty at a discount (`fdd581e`)

**What changed in `pinrun.py`:** after the edge floor, a fill is refused when the
model's confidence is ≥ 0.999 (3.09 sd) AND the offer sits more than 5¢ below the
model's fair value. Counted in the close summary as `dumped`. Nothing else: size
20, gate 0.995, ceiling 98.0¢, tau 3–30, brakes unchanged.

**Why (live fills only, both gates — `fair()` is identical in both):** 14 fills at
≥4 sd. The 8 priced 94¢+ went 8–0. The 6 priced below — 8¢ to 90¢ discounts on a
"certainty" — went 4–2, and both losses were the same reconstructed event: the
book sold us the certain side cheap and the index jumped 10–18 sigma within a
second. The model puts that at ~1e−9. A trade whose EV rests on that tail is a
trade whose EV cannot be estimated, so it is removed.

**Not a fitted threshold:** any discount cut from 6.2¢ to 8.1¢ gives the same
live result; 5¢ is the conservative side and ~17× the edge floor.

**Cost on the live record:** forgoes SOL +$15.36, DOGE +$3.78, ETH +$2.82, SOL
+$1.52; avoids XRP −$16.61, DOGE −$2.12. **EV ≈ neutral (−$4.75 over 111 fills);
loss frequency down by the whole class.** The operator's stated preference, and
the definition of consistent.

**The one thing the operator asked that this answers:** *"why can't we just not
buy the crazy 'deals' that basically always end up being someone knowing what's
happening?"* We now don't.

**Revert:** set `DUMP_DISCOUNT = 9.0` (never trips) or `git checkout fdd581e --
research/pinrun.py`, then stop/start per `RESTART.md`.

Restarted 23:38Z in the quiet window after the 23:30 settlement; pid 442440.

---

## v-pin995 — 2026-09-10 08:4xZ — AMENDMENT 9: the confidence gate 0.98 → 0.995 (`184c826`)

**THE BAR MOVED. Loud, dated, and with the evidence beside it.**

**What changed in `pinrun.py`:** `PIN = 0.995` (was 0.98). The bot now needs the
model at 99.5% — a margin of **2.58 sd** instead of 2.05 — before it will buy.
Nothing else: size 20, 2 buys per close, ceiling 98.0¢, tau 3–30, brakes −$60 /
3 losing closes / 2 order errors / 8 attempts.

**Evidence (`research/pinfirst.py`, 10,796 markets walked tau 30→3, flip rate
measured AT THE SECOND THE BOT FIRES, fit/holdout over closes):**

| margin at fill | markets | flips | rate | holdout |
|---|---|---|---|---|
| 2.05–2.3 sd | 502 | 9 | 1.79% | 2.51% → 1.38% (bands pooled) |
| 2.3–2.6 sd | 195 | 6 | 3.08% | |
| 2.6–4 sd | 594 | 3 | 0.51% | 0.74% → 0% |
| 4+ sd | 7,868 | 0 | [0, 0.05%] | 0 → 0 of 2,500 |

Flips at the crossing 18 → 10 at 0.995; holdout 3 → 1; 9,151 of 9,159 markets
still reach 0.995 inside the window. On the 84 live fills: skips 3 of the 5
losses (NEAR ×2, BNB — all fired at 2.09–2.25 sd), keeps every deep win,
keeps 43 fills.

**What is NOT known:** the fill count. Deeper markets are priced higher, so
the same number of opportunities may fill less often. The next 24 h measures
that. The operator's standing want is MORE bets; tonight's want was FEWER
losses, and this trades one for the other on evidence.

**Revert:**
```powershell
# research/pinrun.py line "PIN = 0.995"  ->  "PIN = 0.98", then stop/start per RESTART.md
git checkout 184c826 -- research/pinrun.py
```

Restarted during the maintenance halt; pid 246096.

---

## v-cond — 2026-09-10 07:47Z — conditions logged on every decision (`2994b55`)

**What changed in `pinrun.py`:** every `signal` record now carries `cond_x`,
`cond_n`, `cond_own` (see `IndexWS.conditions`). Tick retention 1200s → 4000s
so the 3600s baseline is real. A per-feed, per-second cache keyed on a version
counter (a revised print busts it, an identical duplicate does not).
**Nothing about what is bought, at what price, or in what size changed.**
Price ceiling, gates, brakes, size: identical to the previous version.

**Evidence:** `research/pintail.py` — the model's loss-tail is 2.22% with no
other coin moving and 6.60% with three or more (9,159 markets). Every fixed
gate on it failed a holdout split, so it is **logged, not gated**.

**Cost on the order path:** `conditions()` runs only when a signal fires;
~0.5 ms cached, 6 ms cold once per second. Measured.

**Revert:**
```powershell
git checkout 33ead84 -- research/pinrun.py
# then stop/start per RESTART.md
```

**Restart done during the exchange's maintenance halt** (`trading_active:
false`, all shards) — trader down 07:43–07:47Z, zero opportunity cost.
pid 245640, size 20, brake at 3 losing closes.

---

## OUTAGE — 2026-09-08 14:40–15:44 UTC, ~1 hour, NO TRADING

**Cause:** three separate hardcoded rails silently refused every scale-up, and
I verified the process *started* rather than that it *survived*.

1. `pinrun` refused `--loss-abort` outside `[-5.00, 0.00)`. The −$10 (v5) and
   −$15 (v6) values were rejected and the process **exited immediately**.
2. `pinrun` refused `--max-positions > 3`. I passed 4.
3. `pintake.MAX_TAKE_COUNT` was **1 contract**, and `MAX_RUN_STAKE` was $5 —
   less than a single size-8 buy (~$7.60). So even with (1) and (2) fixed,
   **size 3 and size 8 would both have been refused at the order stage.**

**The operator noticed before I did** ("No bets have been bought since we upped
it"). The lesson is recorded, not just the fix: **check that a process is still
alive after it starts, and that its orders are accepted, before believing a
deployment.**

**Fixes:** the loss abort now **scales with size** (allowed range is roughly 2–4
ordinary losses at whatever size is trading) instead of a flat cap that was
right at size 1 and fatal at size 8. Order rails raised deliberately with the
reasoning in the source: `MAX_TAKE_COUNT` 1 → 10 (~8% of the median 125
resting at the touch), `HARD_MAX` 5 → 25, `MAX_RUN_STAKE` $5 → $60.

**`pintake`'s own self-test also had to be fixed** — it asserted "count 2 must
be refused", which was correct when the rail was 1 and became a *false alarm*
the moment it was raised. The rail tests are now written **relative to the
constants**, so they stay meaningful at any setting.

---

## v14 — CURRENT (2026-09-08 22:47 UTC) — funded, size 20, cap 3

| setting | value |
|---|---|
| **bank** | **$154.33**, all on the Crypto shard |
| size | **20 contracts** |
| buys per close | **3**, each ≥0.5¢ cheaper than the last |
| partial fills | down to 50% of size |
| price ceiling | 98.8¢ |
| worst case, one close | $60 |
| dollar brake | −$90 |
| **loss-count brake** | **3 losing trades** |
| **attempts per close** | **8**, separate from the 3-fill cap |
| max open positions | 4 |
| pid / code sha | 4074664 / `e4cdb6320807` |

The operator funded the account. The $150 landed on exchange_index 0, where it
could not have bought anything, and $113.0360 was moved to the Crypto shard.

---

## THE RUNAWAY — 2026-09-08 22:44:30Z, 160 refused orders in one second

**No money lost. Balance unchanged, zero fills, zero open positions.** Caught by
the monitor and stopped within seconds.

**Two of my own changes collided, and neither was wrong alone.**

1. **`pintake.MAX_TAKE_COUNT` was still 10**, so every order at size 20 was
   silently refused. **The FOURTH size-1 literal to break scaling in one day**,
   after the loss-abort range, the run-stake cap and the stake release.
   `take()` *returns* its violations rather than raising, so nothing noticed:
   the order records carry `status_code: null`, `parsed: false`, `error: null`.
2. **AMENDMENT 6 had just stopped a no-fill from consuming a scale-in slot.**
   That is correct — an unfilled order creates no exposure — and it earned
   +27.96¢ within five minutes of deployment. But it left **nothing bounding
   how many times we may try**, so a permanently refused order retried at 20 Hz
   forever.

**Fills and attempts needed separate budgets and only had one.**

### Three fixes

| | |
|---|---|
| `set_limits()` now raises `MAX_TAKE_COUNT` too | and `HARD_MAX` with it, announced, never silently. Still refuses to lower either. |
| a returned refusal is now an **error** | `order_errors` increments, so two in a row halt the run |
| `MAX_ATTEMPTS_PER_CLOSE = 8` | counted **before** the send, so a call that never returns still consumes one |

**Verified against the production endpoint without sending:** `check_take` at
size 20 returned `['count 20.0 exceeds MAX_TAKE_COUNT 10.0']` before the fix and
`[]` after.

### The lesson, and it is the second time today

I verified the process **started** and that its start record described the right
configuration. **I did not verify that an order at the new size would be
ACCEPTED.** That is one function call, no network, no money, and it is now part
of every deployment. *"The process is alive"* and *"the process can trade"* are
different claims.

---

## v13 — 2026-09-08 22:15 UTC — cap 2 → 3

**Withdrawn, then reinstated at the operator's instruction** (*"if you know the
idea works then do it"*). It is **not a new mechanism**: the scale-in rule has
been live since v3 and has produced second buys on real closes. Cap 3 only lets
the same proven rule repeat once more, and **the trade it adds is the cheapest
of the close** — every extra buy must clear `IMPROVE_BY`, so a third buy is at
least 1.0¢ below the first. Cheaper wins more *and* loses less, so cap 3 cannot
degrade the average price paid. Structurally, not merely empirically.

Measured with losses injected per close at the 2.31% exact upper bound:

| | typical result | ruined |
|---|---|---|
| size 20, cap 2 | $271 | 3.4% |
| **size 20, cap 3** | **$304** | **1.1%** |

**12% more money and a third of the ruin.** What it costs is exposure, not
per-contract risk.

**The self-test found the deployment bug for free.** With `--max-positions 3`,
the third buy plus a straggler still settling from the previous close would have
been silently refused. The flag is now 4.

---

## v11 — 2026-09-08 21:39 UTC — MORE BETS, same maximum exposure

| setting | value |
|---|---|
| size | 10 contracts |
| **partial fills** | **take `min(size, offered)` down to 50% of size** |
| **scale-in slot** | **consumed by a FILL, never by an attempt** |
| price ceiling | 98.8¢ |
| loss abort | −$30.00 |
| pid / code sha | 4052684 / `792ee01f2153` |

**Neither change raises the maximum exposure of a close.** That was the
constraint, because the balance cannot fund more.

### Change 1 — a no-fill no longer burns a scale-in slot: +33.3%

`fired[close_s]` was written when the SIGNAL fired, *before* the order was
sent, so an order filling **zero** contracts still burned one of the two
allowed buys and still raised the improve bar. **5 of our first 19 live orders
filled nothing**, and depth was not the cause — the misses had 562, 107, 93, 10
and 5 contracts on offer. Lost races, not thin books, so they recur.

| at the observed 26% miss rate | closes won | buys | expected |
|---|---|---|---|
| no-fill BURNS a slot (before) | 67 | 87 | $40.29 |
| **no-fill keeps the slot** | **80** | **119** | **$53.72** |

**Max exposure unchanged** — the cap always meant two *fills*; the bug made it
two *attempts*.

### Change 2 — take a partial down to half size: +1.3% at size 10, +5.4% at 25

| threshold | buys | expected |
|---|---|---|
| full size only (before) | 124 | $59.75 |
| **≥50% of size** | **125** | **$60.53** |
| ≥5% of size | 129 | $58.37 |

**Taking any scrap is worse than taking none:** a tiny early fill burns a slot
and raises the improve bar, trading a big cheap buy later for a small dear one
now. Half is the measured optimum at both sizes. Exposure can only fall.

### MEASURED AND REJECTED: `MAX_PER_CLOSE` 2 → 3

**+26.7%, larger than either change above, and NOT deployed because it cannot
be funded.** Worst close $30 against a $38.83 balance, and the rail would need
a brake at −$45 or looser. **This is the best available change the moment the
account is funded.**

### Three self-tests were inspecting themselves

`src.index("def trade_loop(")` matched this test file's OWN string literal,
because `selftest()` is defined above `trade_loop`. Every structural check
built on it was reading the test instead of the code and could have passed
vacuously. All three now anchor on a newline.

**Revert:** `MIN_FILL_FRAC = 1.0`, and move `_book_slot()` back above the order.
**Pre-registration:** `results/PREREG_pin_live_AMENDMENT_6.md`.

---

## v10 — 2026-09-08 21:14 UTC — size 10, and two silent killers removed

| setting | value |
|---|---|
| size | **10 contracts** |
| price ceiling | 98.8¢ |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| loss abort | **−$30.00**, and the order path now agrees |
| pid / code sha | 4056648 / `497c2f96b280` |

### First size-10 trade: +103.14¢, more than the whole day before it

```
21:30Z close   KXBTC15M  tau=7s  buy NO @0.8900  fair 0.00256  edge +10.058c
1,000 contracts on offer, we took 10
filled 10.0 @ 0.89, fee $0.0680  ->  settled NO, payout $10.00
stake $8.9000 + fee $0.0680      profit +$1.0314   = 11.59% on stake
```

**89¢ is the cheapest price we have ever paid**, and the cheapest price wins
more *and* loses less. Break-even at 89¢ is an 11% error rate; ours is 0.90%.

### Two size-1 literals were silently disarming the trader — found by audit

1. **The stake release gave back ONE contract instead of the whole fill.**
   pintake commits `filled × price`; reconcile released bare `price`. At size 5
   that stranded $3.90 per settled trade, turning the $60 run-stake cap back
   into a **cap on lifetime turnover** — every order refused after ~15 fills,
   6 at size 10. `take()` *returns* the refusal rather than raising, so nothing
   halted and nothing logged. Two give-up branches released **nothing at all**.
2. **`pintake.LOSS_ABORT` was a hard −$2.00.** One ordinary loss at size 5 is
   −$4.88, so **the first loss we ever took would have shut off all trading**,
   silently, while the −$21 brake sat untouched.

**Fixes:** a single `_release()` used on all three exit paths, releasing
`cost × contracts`; P&L booked on contracts actually filled; and
`pintake.set_limits()`, which raises the order-path rails to agree with the
run's own brake and **refuses to tighten**.

**The self-tests now sweep sizes 1, 5, 8, 10, 25**, include a positive
assertion that a one-contract release at size 5 leaks $3.90 so they cannot pass
vacuously, and scan the source to require every exit path to release.

### Depth tracking added

`close_summary` now carries min/p25/median/p75/max/total contracts offered
across every moment we could have bought, plus how many survive at each
candidate size. Early readings: **median 530 contracts** on one close, **101**
on another, with 414 moments surviving size 10.

**Revert:** `--size 5 --loss-abort -21.00`.
**Revert trigger:** any fill above 98.8¢, or a flip rate above 2.31%.

---

## v9 — CURRENT (2026-09-08 16:36 UTC) — back to a 98.8¢ ceiling

| setting | value |
|---|---|
| **price ceiling** | **98.8¢** |
| size | 5 contracts |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| loss abort | −$21.00 |
| pid / code sha | 3997812 / `d6826548c653` |

---

## v8 — 96¢ CEILING. IT *WAS* LIVE, IT SUPPRESSED TRADING, AND I TWICE GOT THE STORY WRONG

**This entry has been wrong twice. Both wrong versions are described here rather
than deleted, because the failure mode is the lesson.**

### Wrong version 1 (16:35 UTC): "v8 is live and it is safer AND more profitable"

Two of the three claims did not hold. Total realised profit goes DOWN when you
tighten (742.0¢ → 724.9¢); it only rises in EXPECTATION at an assumed 0.90%
flip rate (625.9¢ → 649.3¢). And "the dear trades were never paying for the
risk" was never measured — there are **zero flips in the entire eligible
sample at every ceiling**, and the 96–98.8¢ band realised **+2.087¢ per
contract** over 784 moments. I stated a model output as a measurement.

### Wrong version 2 (16:20 UTC): "the 96¢ ceiling was never live"

**Also wrong, and worse, because I acted on it.** I read the live process's own
start record, saw `"price_ceiling": 0.988`, and concluded the change had never
been applied.

**That field was DERIVED, not the constant.** The line was:

```python
price_ceiling=round(1.0 - MEASURED_FLIP - EV_FLOOR, 4)   #  = 0.988, ALWAYS
```

It reports the ceiling the EV arithmetic *implies*. It never read
`PRICE_CEILING` at all. **A process running a 96¢ ceiling truthfully logged
98.8¢.** My "verify what the process logged, not what the source says" rule was
right in principle and I applied it to a field that could not answer the
question.

### What actually gave it away — the operator noticed the symptom first

The operator said "haven't seen a trade in a while." The 16:30Z close then
showed this:

```
close 16:30Z  4,264 looks  954 tradeable  fired: FALSE
best: KXBTC15M NO @ 96.6c  edge +2.891c  tau 28s  665.71 contracts on offer
```

Every gate in the code on disk passes that moment: edge 2.891¢ ≥ 0.3¢,
EV 2.270¢ ≥ 0.3¢, price 96.6¢ ≤ 98.8¢. **The only rule that rejects 96.6¢ is a
96¢ ceiling.** Behaviour, not logs, proved it was live.

### Cost

Live signal history: **12 of our 16 real signals were above 96¢** (mean price
paid 97.61¢). The 96¢ ceiling was refusing roughly three quarters of our
trades, against a backtest that predicted it would refuse 30%.

### Two fixes, both in `pinrun.py`

1. **The start record now logs `PRICE_CEILING` itself**, with the derived value
   kept alongside as `ev_implied_ceiling`, plus a `code_sha` fingerprint of the
   running file. A log line can no longer describe code that is not running.
2. **`close_summary` now emits `over_ceiling` and `neg_ev`.** Both counters
   existed and neither was reported, so the refusal was invisible in the log
   that was written specifically to explain refusals.

### The standing rule this replaces

*"Check what the process logged at start"* is not enough. **A configuration
check must read a field that is derived from the constant it claims to
describe — and the way to prove a rule is live is to find a moment it changed
the behaviour.**

---

## v7 — 2026-09-08 16:12 UTC

| setting | value |
|---|---|
| size | **5 contracts** per buy |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| EV gate | ≥0.3¢ at 0.90% flip rate → ceiling 98.8¢ |
| worst case per close | **$10.00** |
| loss abort | **−$21.00** → survives 2.1 bad closes |

### First size-8 trade: WON +49.34¢

```
KXHYPE15M  tau=9s  buy NO @0.9350  fair 0.0103  edge +5.04c  size on offer 34
filled 8.0 @ 0.934, fee $0.0346  ->  settled, payout $8.00
stake $7.4720 + fee $0.0346 = $7.5066   profit +$0.4934   = 6.6% on stake
crypto shard $38.2157 -> $38.7091, reconciles exactly
```

**The rebuilt order rails work end to end at size 8.**

### The safety system caught two configuration errors in ten minutes

**1. Self-halt after the fill (correct).**
```
HALT: realised $+0.00 with $7.47 still open; one more contract
      could take this run past $-15.00
```
Size 8 with 2 buys can commit ~$16 against a −$15 brake. **The configuration
was self-contradictory** and the forward-looking loss bound refused to enter a
state where the brake could be breached. Exactly the right behaviour.

**2. The deployment rail then refused −$21 at size 5 — right call, wrong
arithmetic.** It sized the abort against **one contract** when a close can buy
**MAX_PER_CLOSE** of them. Fixed to use `size × MAX_PER_CLOSE` as the unit of
loss, because **the unit of loss is a CLOSE, not a contract**.

### The pattern, now explicit

This is the **third** time today a limit set for a size-1 proof silently
blocked scaling: the loss-abort range, `pintake`'s 1-contract order cap and $5
run stake, and now the abort's unit of measure. Every one of them was *correct
for size 1* and wrong afterwards.

**Rule going forward: any constant tied to size must be expressed in terms of
size, never as a literal.**

---

## v6 @ size 1 — CURRENT (2026-09-08 15:47 UTC)

| setting | value |
|---|---|
| window | tau 3–**30** s |
| model gate | p_flip ≤ 0.02 |
| EV gate | ≥0.3¢ expected at 0.90% flip rate → ceiling **98.8¢** |
| size | **1 contract** |
| buys per close | up to **2**, second only if ≥0.5¢ cheaper |
| max exposure/close | ~$1.90 |
| loss abort | −$3.00 |

**Deployed at size 1 deliberately.** The operator's instruction: only go one
step beyond a *proven* version, and only if each change passed its historic
test and its failure would be identifiable.

**Each change passed:**
- EV gate — 5 of 7 live trades were negative-EV; break-even price = 1−f is exact
- scale-in — 70 closes, 4.18¢ → 7.43¢/close, average price paid FELL
- tau 30 — 0 flips in 2,872 moments across 118 closes at tau 21–30

**Each failure is distinguishable:**
| symptom | cause | fix |
|---|---|---|
| flips on trades at tau > 20 | v4 | `--tau-max 20` |
| second buy at a WORSE price than the first | v3 | `MAX_PER_CLOSE = 1` |
| any fill above ~98.7¢ | EV gate not binding | check `MEASURED_FLIP` |
| flip rate > 2.31% | the whole ceiling is wrong | re-derive every threshold |

**Size stays at 1 until this version has traded and won on its own.** Scaling
is a separate, later decision — it does not accelerate learning, only exposure.

---

## v4 — 2026-09-08 15:20 UTC — SHA `45966b9`

Window **20 → 30 seconds**. Model calibration measured by horizon: 0 flips in
5,219 moments below tau 30; 3.7× overconfident at 31–45; **10.9× at 46–60**.
The overconfidence is entirely a long-horizon effect, which also explains why
the `tau<=60` backtest cell was dead. Roughly doubles qualifying moments.

**Revert:** set `TAU_MAX = 20`.
**Revert trigger:** any flip on a trade at tau > 20 → review; a second → revert.

---

## v3 — 2026-09-08 15:00 UTC — SHA `d04647d`

**Scale in as the price improves**: up to 2 buys per close, the second only at
≥0.5¢ better. Measured 4.18¢ → 8.87¢ per opportunity, average price paid FELL
95.53¢ → 94.28¢. Waiting instead is strictly worse (skipping one tick missed 7
of 70 closes).

**Revert:** `MAX_PER_CLOSE = 1`.
**Revert trigger:** average fill price across a close exceeding the first
fill's price over 50+ closes.

---

## v2 — 2026-09-08 11:35 UTC — SHA `c3aca51`

**EV gate.** Replaced "model edge ≥ floor" with `EV = (1−f)(1−p) − f·p − fee ≥
0.3¢` at the **measured** 0.90% flip rate, implying a price ceiling near 98.5¢.
Found because 5 of the first 7 live trades were negative-EV: breakeven price is
exactly `1 − f = 99.1¢`, and the model's own fair value implied 0.06% error
where reality is 0.90%.

Effect: profit per trade 1.41¢ → 3.42¢.

**Revert:** remove the `expected_value` check.

---

## v1 — 2026-09-08 08:20 UTC — SHA `2489d73`

**Edge floor 0.5¢ → 0.3¢.** Out of sample the looser floor gave 389 closes /
+2.76¢ / t=+5.6 / 1 flip in 359, against 354 / +2.51¢ / t=+4.1 / 3 flips in 333.

**Revert:** `EDGE_FLOOR = 0.005`.
**Revert trigger:** live flip rate ≥ 1.0%.

---

## v0 — 2026-09-08 07:09 UTC — first live version

tau 3–20, fair ≥0.98/≤0.02, edge ≥0.5¢, one buy per close, size 1,
loss abort −$3.00. First real trade 08:00Z (BTC YES @0.992, won +0.74¢).

---

## Running record

| | |
|---|---|
| won / **lost** | **29 / 3** |
| live flip rate | **9.4%** (3 of 32) — see the caveat below |
| bank | **$110.33** |
| day | started $38.83, funded +$113.04, now $110.33 = **−$41.54** |
| best single close | +$2.52 (three fills) |
| best single trade | +185.51¢ (SOL at 90.1¢) |
| **worst single close** | **−$52.60** (three fills, ONE market, all lost together) |

### THE FIRST LOSS — 2026-09-09 00:45Z, KXNEAR15M

Three same-side buys on **one market** at tau 22 / 21 / 17, 96.2¢ / 95.6¢ /
73.0¢, all lost together. The loss-count brake halted the run. Settlement was
reproduced independently from the raw index and agrees with the exchange, so
**the arithmetic is not broken**. The index sat flat for eight seconds, then
moved 0.0021 in a single second at tau 16 and never came back.

**A six-agent forensic investigation refuted nearly every proposed fix,
including my own.** Flatness, sigma regime and recent-jump separate losers from
winners at p = 0.14–0.99; once the model's own `z` is held fixed, nothing adds
anything. Every entry gate tested costs **22–44 winning trades per loss
avoided**. See AMENDMENT 8 and IDEAS_LOG.

**The live flip rate of 9.4% is 3 losses in one correlated close, not 3
independent events.** Clustered by close it is 1 losing close in 20, and the
sample is far too small either way. It does NOT yet exceed the 2.31% bound that
would kill the strategy, because that bound is per-trade on independent draws
and these were not independent. **This is exactly why the brake now counts
closes.**

## What to check first if it starts losing

1. **Flip rate by tau.** If flips appear above tau 20, v4 is the cause — revert
   to `TAU_MAX = 20`.
2. **Average fill price per close.** If the second buy is coming at *worse*
   prices, v3's mechanism has reversed — set `MAX_PER_CLOSE = 1`.
3. **Prices paid.** If trades are appearing above 98.5¢, the EV gate is not
   binding — check `MEASURED_FLIP` and `EV_FLOOR`.
4. **The measured flip rate itself.** Everything above is built on 0.90% from
   3 flips in 333. If the live rate exceeds 2.31% (the EXACT one-sided 95%
   Clopper-Pearson bound; the 1.80% figure quoted until 2026-09-08 was a normal
   approximation and is optimistic by 28% at only 3 events), the
   price ceiling is wrong and every threshold must be re-derived.
