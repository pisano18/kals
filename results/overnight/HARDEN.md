# HARDEN.md -- killing the mutation survivors in pin and informed

Job 4, 2026-09-06. Six named mutations survived the self-test gates. All six
are dead. Two more mutations that had never actually applied were repaired,
and one of the repaired pair exposed a seventh hole, which is also dead.

**This job earns $0.** It does not change a single published number -- every
line added lives inside `selftest()` and no estimator was touched (338 lines
added, 0 deleted, verified by diff). What it buys is that pin's headline
(`$30-101/day` on `$50-268` peak concurrent capital, 10 of 11 days positive)
is now certified by a gate that catches the specific ways that number could
have been a lie. The most important of the six -- survivor 3 -- would have
turned the entire out-of-sample claim into an in-sample claim without one
assertion firing.

---

## 1. HEADLINE: BOTH NUMBERS, BEFORE AND AFTER

Two panels. The first is the original `mutate.py` panel exactly as it stood,
so the before/after is a like-for-like comparison. The second is an extended
panel I built afterwards to attack the guards I had just written -- because a
guard tuned to the literal string of the mutation it was written against is
worth nothing, and the only way to find out is to fire the mirror image at it.

### Panel A -- the original `mutate.py`, 16 mutations, 14 of them applied

| stage | before | after |
|---|---|---|
| `pin` | **6 killed, 3 SURVIVED of 9 applied = 67%** | **9 killed, 0 survived = 100%** |
| `informed` | **2 killed, 3 SURVIVED of 5 applied = 40%** | **5 killed, 0 survived = 100%** |

0 crashes on either side. A crash is the interpreter catching the bug, not
the gate, and `mutate.py` scores it separately; none of these were crashes.

### Panel B -- 10 new mutations (2 repairs + 8 attacks on the new guards)

| stage | before (pre-hardening tree) | after |
|---|---|---|
| `pin` | **0 killed, 5 SURVIVED of 5** | **5 killed, 0 survived = 100%** |
| `informed` | **0 killed, 5 SURVIVED of 5** | **5 killed, 0 survived = 100%** |

### Both panels together -- 24 mutations, all 24 applied

| stage | before | after |
|---|---|---|
| `pin` | **6 of 14 = 43%** | **14 of 14 = 100%** |
| `informed` | **2 of 10 = 20%** | **10 of 10 = 100%** |

The 67% / 40% that this job started from was measured against a panel that had
never attacked a call site, never attacked one leg of a two-leg fee, and never
attacked the mirror image of anything. Against the fuller panel the gate was
**43% and 20%**. That is the honest "before", and it is worse than the number
in HANDOFF.md. Report half a comparison as half a comparison: 67%/40% was half
a comparison.

Cost of the hardening, measured: `pin --selftest` 5.77s -> **7.1s**;
`informed --selftest` 2.45s -> **2.40s** (unchanged inside noise). Both are
byte-for-byte deterministic across 3 consecutive runs (sha256 of stdout
identical), so nothing added is a coin flip that will fail a real run at 3am.

---

## 2. WHAT WAS ADDED, AND WHY EACH SURVIVOR SURVIVED

### pin -- survivor 1: "fee removed on the YES leg only"

*Why it lived.* Guard 1 (added earlier today) computes fee drag as
`mean(gross) - mean(net)` over ALL trades. With the fee still charged on the
NO legs the aggregate stayed comfortably positive -- `+0.867c` on the fixture
-- and the guard passed while every YES trade in the report was being handed
its fee back. An aggregate cannot see a per-leg lie.

*The kill -- `MUTATION GUARD 5`.* The fee is a per-leg quantity, so it is
checked per leg. For every single trade, the realised P&L must differ from
that trade's own gross by exactly the fee its own entry price implies:

```
    59 YES legs drag +0.8414c   65 NO legs drag +0.8896c
    worst per-trade residual 7.11e-15c (no)
```

`7.11e-15c` is float noise; the tolerance is `1e-9`. Two further assertions
stop the guard being vacuous: the fixture must contain at least 5 legs of
EACH side (it has 59 and 65), and the mean drag on each side separately must
be strictly positive. Without the leg-count assertion, a fixture that happened
to take only NO trades would pass this guard while proving nothing about YES.

### pin -- survivor 2: "edge overstated by 0.5c in `evaluate()`"

*Why it lived.* Nothing ever recomputed the edge a trade was taken on. The
`+0.5c` both admits trades that do not clear the floor and inflates the
`claimed` column of every table. The fair-band test does not see it: that band
redraws outcomes from the model's own `fair`, so its mean is the TRUE edge and
moves only ~`0.24c` (0.5c on the 59 YES legs of 124) -- against a Monte-Carlo
noise of `±0.11c` at 500 reps. Too close to threshold safely.

*The kill -- `MUTATION GUARD 6`.* It does not need Monte Carlo at all. The
model's expected P&L on a YES fill is `100*(fair - entry) - fee(entry)`, which
is precisely what `evaluate()` stores as `edge`. So "the realised edge
distribution matches what the entry rule claims" has a **closed form, per
trade**:

```
    worst |stored edge - recomputed| 0.00e+00c over 124 trades;
    0 at or below the 0.5c floor;
    claimed +21.612c vs the model's own resettled mean +21.595c (gap -0.016c)
```

Exactly zero, over all 124 trades. Plus the floor-clearance count (0 trades at
or below the 0.5c floor they were required to clear), which catches the variant
where the decision is inflated but the stored number is not. The resettled
cross-check is kept at `reps=2000` where its noise falls to ~`0.03c`, tolerance
`0.15c`, observed gap `-0.016c` -- it is a live check on `redraw_null` itself,
not the kill.

### pin -- survivor 3: "walk_forward replaced by in-sample evaluate AT THE CALL SITE"

**This is the one that mattered.** Guard 4 tests `walk_forward`. The mutation
does not touch `walk_forward`. It rewrites line 470 of `pin.py` -- inside
`run_oos`, under a heading that says OUT OF SAMPLE -- to call `evaluate()`
in-sample instead. Guard 4 still passes, because the function it guards is
still honest and still there; it is simply no longer being used. Every number
under "OUT OF SAMPLE" would have been in-sample and nothing would have said so.

*The kill -- `MUTATION GUARD 7`.* The property to assert is not "walk_forward
is honest" but "**the out-of-sample tables are made of walk_forward's
output**". So the guard asserts the data flow, not the function:
`walk_forward` and `_walk_markets` are replaced by delegates that run the real
thing and TAG every trade they return; `block` and `portfolio` -- the two
consumers that turn trades into printed tables -- are replaced by collectors.
`run_oos` and `run_portfolio` are then actually executed on the fixture (with
stdout captured), and every row that reaches a table must carry the tag.

```
    run_oos + run_portfolio built 12 tables from 690 trades;
    walk_forward called 10x (expected 10), _walk_markets 2x;
    690/690 of the scored trades came from them
```

The expected call count is derived from the module's own constants
(`2 * len(FLOORS) + 2`) so it tracks the config instead of a hard-coded 10.

Three anti-vacuity assertions: at least the expected number of `walk_forward`
calls, at least 2 `_walk_markets` calls, and at least 100 trades must actually
reach the tables (690 do). Without the last one, a mutation that made the
tables empty would pass "all 0 of 0 trades were tagged".

**Stated limit of this guard.** It proves the tables are fed by whatever the
module currently binds to the name `walk_forward`. That the function so named
has no look-ahead is guard 4's job (truncation test: removing only FUTURE
closes must leave every refitted `k` bit-identical -- 9 closes checked, 0
moved). Neither guard is sufficient alone. Together they cover the printed
table: guard 4 owns the estimator, guard 7 owns the call site.

**Artefact risk in the guard itself, checked.** Guard 7 rebinds module globals.
If the restore ever leaked, every real run after a self-test would be driven by
spies. Verified directly (`job4/probe5.py`): after `selftest()` returns True,
all eight of `walk_forward, block, _walk_markets, portfolio, evaluate,
evaluate_markets, run_oos, run_portfolio` are the identical objects they were
before (`globals rebound after selftest: none`), and a fresh `run_oos` call
afterwards still produces 8 populated cells.

### informed -- survivor 4: "every cell mean inflated 50%"

*Why it lived.* Every number this stage prints is a `Cell.stat()` mean, and
nothing ever handed `Cell` a mean it already knew. Worse: **no significance
test can ever catch this.** A constant factor scales `mu` and `se` together and
cancels exactly in the t-stat. The zero-information world still reads t≈0; the
planted-tail world still reads t=+55.8. Only planting the answer and demanding
it back detects it.

*The kill -- `MUTATION GUARD 1`.* 40 closes, each fed two values straddling a
known per-close mean (so the internal `sum/n` aggregation is exercised, not
bypassed), and the recovered mean, `G`, `n`, `t` and `MDE` are all compared to
hand arithmetic:

```
    planted mean +2.010666c over 40 closes (80 adds) -> stat() mean +2.010666c
    G=40  n=80  t=+48.1764 (hand +48.1764)  MDE 0.0844 (hand 0.0844)
```

Tolerance `1e-9` on all three. The mutation moves the mean to `+3.016c` and
the MDE to `0.127`, while leaving `t` untouched -- which is exactly the point.

### informed -- survivor 5: "the 30-cluster floor removed"

*Why it lived.* The floor exists because a cluster SE off a handful of closes
once produced `t = +12.28` off 12 closes. Nothing asserted it. Every fixture
cell has 398-400 closes, so `G < 30` was never reached in the self-test at all.

*The kill -- `MUTATION GUARD 2`.* Two synthetic cells, one on each side of the
documented boundary:

```
    G=29 -> t=None  MDE=None  mean +1.1400c        G=30 -> t=+71.24  MDE=0.0329
```

At 29 clusters `t` and `MDE` must both be `None` and the MEAN must still be
returned (the floor suppresses the CLAIM, not the number). At exactly 30 the
`t` must appear. Checking both sides matters: a floor raised to 300 would also
"pass" a one-sided test that only demanded silence -- and it is a real failure
mode, since it would silently withhold every genuine result. It is mutation
B8 below, and it dies on the `G=30` half.

### informed -- survivor 6: "every group counted as monotone (`up = True`)"

*Why it lived, and this is the interesting one.* Test 5 already fires a
sweepless tape at `sweep_verdict`. But that fixture's trades are ALSO
sequence-scattered, so with every group called monotone the verdict still died
on the contiguity term. **The existing case masked the predicate it was meant
to test.** The masking is what let the mutation through, not the absence of a
case.

*The kill -- `MUTATION GUARD 3`.* A fixture that removes the mask. 1,200
groups that are simultaneous, single-sided, sequence-contiguous and
multi-price -- everything a sweep is -- differing from a sweep in exactly one
respect: the price walks up, back DOWN, and up again.

```
    zig-zag: 1,200 multi-price groups, 100% single-sided, 100% seq-contiguous,
             0 monotone, verdict not established
    rising : 1,200 multi-price groups, 1200 monotone, 1200 direction-consistent,
             verdict PER LEVEL
```

`mono` must be exactly 0 -- the predicate asserted directly -- and the verdict
must also refuse, with an explicit assertion that the fixture really is 100%
single-sided and 100% contiguous so that nothing but monotonicity can be doing
the refusing. The rising control beside it must be read as PER LEVEL, so the
guard has to discriminate rather than merely refuse everything.

### informed -- survivor 7 (BONUS): "the sign-scrambled control pinned at 0"

Found by repairing a mutation that had never applied (see section 3).

*Why it lived.* `shufS` is the null that certifies this whole stage does not
manufacture information. Every test that touches it asks only whether it is
near zero -- so a control hard-wired to `0.0` passes all of them. A null with
no variance is not a null; it is a printed zero.

*The kill -- `MUTATION GUARD 4`.* The control must be a LIVE measurement:
near zero in MEAN, but carrying the same order of per-close SPREAD as the
measure it is the null for (it is the same magnitudes under a random sign, so
it must).

```
    ALL/all: shuffle mean +0.21c sd 6.26c t=+0.68   measured mkS mean +4.97c sd 5.79c
    size/3 : shuffle mean +0.19c sd 15.27c t=+0.25  measured mkS mean +26.09c sd 9.32c
```

Threshold `sd_shuffle > 0.5 * sd_measure`; observed ratios 1.08 and 1.64, so
2-3x of headroom. Plus `|t| < 4` on both cells, plus an assertion that the
control covers the same number of closes as the measure it controls.

### informed -- a guard that crashed instead of failing, and was fixed

Attack B8 ("cluster floor RAISED to 300") first came back **CRASH**, not
KILLED: my own guard formatted `stat()['t']` with `:+.4f` and the raised floor
made it `None`, so it raised `TypeError` before the assertion could fire.
Under this project's rules that is the interpreter catching the bug, not the
gate -- it does not count. Fixed with a `_n()` formatter that renders `None`
as `"None"`, and None-safe comparisons in the assertions. B8 now reads KILLED.
Final tally across both panels: **0 crashes in 24 mutations.**

---

## 3. THE TWO MUTATIONS THAT NEVER APPLIED

`mutate.py` reported "pattern NOT FOUND" twice. A mutation whose pattern is
absent is not evidence about the gate; it is a typo in my mutation, and
leaving it in the denominator would have flattered both stages. Both repaired:

**`pin` -- "edge floor effectively disabled".** The pattern
`if edge <= edge_floor:` was aimed at `pin.py`. The line lives in
`endgame.py:311`. Repaired by pointing at the right file. Result: **SURVIVED**
the old gate, **KILLED** by guard 6 (trades below the floor are counted).

**`informed` -- "the sign-scrambled control renamed away".** The pattern
`            "shufS": ` is a dict-key form that does not exist in the file.
Renaming the key that DOES exist (`MEASURES`, or the `vals.update(shufS=...)`
kwarg) raises `KeyError` inside `Cell.add` -- a crash, which `mutate.py`
rightly refuses to score as a kill. The faithful non-crashing form of "the null
is silently absent" is `shufS = 0.0`. Result: **SURVIVED** both the old gate
AND the first pass of the new one, which is how survivor 7 was found. Now
KILLED by guard 4.

---

## 4. THE EXTENDED PANEL -- ATTACKING MY OWN GUARDS

A 100% kill rate on the panel the guards were written against proves almost
nothing: it is the definition of overfitting. So eight further mutations, each
aimed at one new guard's specific blind spot, mostly the mirror image of the
mutation the guard was written for. All eight survived the pre-hardening tree
(0 of 10 killed, including the two repairs) and all ten die now.

| # | stage | mutation | target guard | before | after |
|---|---|---|---|---|---|
| A1 | pin | edge floor disabled (repaired file) | G6 | SURVIVED | KILLED |
| A2 | informed | sign-scrambled control pinned at 0 (repaired) | I4 | SURVIVED | KILLED |
| B3 | pin | fee removed on the **NO** leg only | G5 | SURVIVED | KILLED |
| B4 | pin | edge overstated 0.5c on the **SELL** side | G6 | SURVIVED | KILLED |
| B5 | pin | `run_oos` **calls** walk_forward then throws its answer away | G7 | SURVIVED | KILLED |
| B6 | pin | `run_portfolio`'s every-market table made in-sample | G7 | SURVIVED | KILLED |
| B7 | informed | cell mean **shifted** +0.5c (a bias, not a scale) | I1 | SURVIVED | KILLED |
| B8 | informed | cluster floor **raised** to 300 (not removed) | I2 | SURVIVED | KILLED |
| B9 | informed | the **other** half of the monotone predicate (`down = True`) | I3 | SURVIVED | KILLED |
| B10 | informed | trade counter double-counts, per-close means halve | I1 | SURVIVED | KILLED |

B5 is the sharpest of these. It calls `walk_forward` -- so a guard that merely
counted the call would pass -- and then overwrites the result with an in-sample
`evaluate`. It dies on the tag check, which is why guard 7 asserts the data
flow and not just the call.

B3, B4 and B9 are pure mirrors: if guards 5, 6 and I3 had been written to the
literal text of the mutations they were built against, the mirrors would have
walked through. They did not.

---

## 5. ARTEFACT CHECK -- WHAT WOULD MAKE "100%" FICTION

Six ways this number could be a lie, and what was done about each.

**(a) The guards are vacuous -- loops over empty collections.** Every new
guard carries an explicit "is this guard checking anything" assertion, and each
prints its own n: 59 YES / 65 NO legs, 124 trades, 690 trades across 12 tables,
1,200 zig-zag groups at 100% single-sided and 100% contiguous, `G=40 n=80`,
`G=29` and `G=30`, 398-400 closes on the shuffle control. **Checked.**

**(b) The guards are overfit to the literal mutation strings.** This is the
real risk and the reason panel B exists. Eight mirror-image attacks, all dead.
**Checked.**

**(c) A guard leaves the module in a broken state, so the real run is
corrupted.** Guard 7 rebinds four globals. `job4/probe5.py` proves all eight
inspected module attributes are identical objects after `selftest()` returns,
and that `run_oos` still produces 8 populated cells afterwards. **Checked.**

**(d) An existing assertion was weakened to make something pass.**
`diff` of my own work: `pin.py` **+156 / -0**, `informed.py` **+182 / -0**.
Zero deletions in either file. Nothing was relaxed. **Checked.**

**(e) A "kill" is really a crash.** `mutate.py` and `mutate2.py` both classify
crashes separately. One crash appeared (B8) and was converted into a real gate
failure. Final: **0 crashes in 24 mutations.** **Checked.**

**(f) The guards pass on the fixture but will fail or hang on a real run.**
All seven guards sit inside `selftest()` and use only fixtures the self-test
already builds; none reads the tape. Both self-tests are byte-identical across
3 consecutive runs (stdout sha256), and the added cost is 1.3s on `pin` and
0.0s on `informed`. **Checked.**

**WHAT IS STILL NOT PROVEN.** The panel is 24 mutations I chose. 100% means
the gate covers these 24 named failure modes and their mirrors -- it is not a
proof of completeness, and the next person to write a mutation this panel
does not contain may well find it survives. That is how the last two rounds
went: 33% -> 67% -> (with a fuller panel) 43% -> 100%. The honest claim is
"these specific lies now fail loudly", not "the gate is sound".

---

## 6. WHAT I COULD NOT DO

**The out-of-sample call site cannot be asserted without test doubles.** I
looked for a pure-data assertion -- something that reads the printed table and
proves it out-of-sample. There is not one: any independent re-derivation of the
table would have to run the same code, and comparing the table to itself proves
nothing. Static inspection of `run_oos`'s source with `ast` was the other
candidate; it is strictly weaker than the spy (it proves a name appears, not
that its result is used -- attack B5 would survive it). So guard 7 uses
delegates, and its limit is stated in the code rather than hidden.

**No fixture was missing.** Every guard is built from fixtures the repo already
had (`_world`, `_bridge_world`) or from synthetic data constructed inline. No
guard needed tape the repo does not hold, so nothing had to be skipped for want
of a fixture.

**I did not touch the real-data path and ran no real-data job.** Nothing here
reads `kalshi_data`, `feed_data` or `fulltape`. No API calls, no orders.

**I did not commit.** The working tree carries the changes; both self-tests
pass, so the overnight runner will pick them up cleanly if it starts.

---

## 7. RELIABILITY -- DOES THIS NEED THE MARKET TO BE WRONG?

No. Nothing here is a trade. This is gate work: it does not need the market to
be wrong, or right, or anything at all. It changes no estimator and moves no
published number -- all 338 added lines are inside the two `selftest()`
functions (line ranges verified: `pin.selftest` 558-1018 holds guards 5/6/7 at
854/898/945; `informed.selftest` 702-1066 holds guards 1/2/3/4 at
893/933/967/1023).

The money consequence is indirect and worth being precise about. pin's
published edge is `$30-101/day` on `$50-268` peak concurrent capital, 10 of 11
days positive, bootstrap interval excluding zero. Before today, three specific
ways for that to be false would not have failed the gate:

* the fee could have been dropped on half the trades (survivor 1),
* the entry rule could have been claiming 0.5c it did not have, and taking
  trades that did not qualify (survivor 2),
* **the out-of-sample table could have been in-sample** (survivor 3).

The third is not a rounding error. The whole reason pin is believed is that
`k` is fitted only on closes strictly earlier than the one being traded; the
in-sample version of the same table claimed `+2.51c` where the walk-forward
delivered `+1.70c`. A silent swap at the call site would have restored the
flattering number under an honest heading. It now fails loudly.

---

## 8. FILES

Changed (working tree, not committed):

* `C:\kals-repo\research\pin.py` -- +156 lines, 0 deleted. Guards 5, 6, 7 at
  lines 854, 898, 945, all inside `selftest()`.
* `C:\kals-repo\research\informed.py` -- +182 lines, 0 deleted. Guards 1, 2,
  3, 4 at lines 893, 933, 967, 1023, plus the `_n()` None-safe formatter, all
  inside `selftest()`.

Written:

* `C:\kals-repo\results\overnight\HARDEN.md` -- this report.
* `C:\Users\Joe\AppData\Local\Temp\kals-work\job4\mutate2.py` -- the extended
  10-mutation panel. Takes a source tree as argv[1] and never mutates in
  place, so it can be pointed at the pre-hardening tree for a before/after.
* `C:\Users\Joe\AppData\Local\Temp\kals-work\job4\pre\` -- the pre-hardening
  tree (research/ with the two originals restored), kept so panel B's "before"
  column can be re-measured by anyone.
* `C:\Users\Joe\AppData\Local\Temp\kals-work\job4\{pin,informed}.py.bak` --
  the exact pre-job originals.
* `C:\Users\Joe\AppData\Local\Temp\kals-work\job4\probe5.py` -- the guard-7
  global-restoration artefact check.
* Panel logs: `mut_before.txt` (in `kals-work\`), `job4\mut_after2.txt`,
  `job4\ext_before.txt`, `job4\ext_after2.txt`.

Unchanged: `C:\Users\Joe\AppData\Local\Temp\kals-work\mutate.py` -- left
exactly as it was so its before/after is comparable. Its two mis-targeted
mutations are repaired in `mutate2.py` instead of being edited in place.

---

## 9. NEXT STEP

Run the same panel against the stages that have never been mutation-tested at
all. `pin` and `informed` are now at 100% on 24 mutations; `queuesim` is at
6 of 20 from Lens 2 and was never re-hardened, and `endgame`, `maker`,
`calib` and `chain` have never been tested. `endgame` is the one to do next:
`pin` imports `scan`, `evaluate`, `summarise`, `redraw_null`, `mde`,
`fee_cents` and `outcome_of` from it, so every guard above is standing on
`endgame`'s arithmetic, and `endgame` has no mutation panel of its own.

---

## RESOURCE PROTOCOL

Both collectors verified ALIVE after every heavy job and at the end of this
one: `kalshi_collector.py` PID 3381772 and `crypto_feeds.py` PID 3385232,
both started 10:57:01. Free disk 51.7 GB (hard stop is 6 GB). Free RAM ~4.5 GB
at the start; every job here is a self-test on a synthetic fixture, peak
working set well under 200 MB, and `replay.load_quotes` was never called. No
python process was killed.
