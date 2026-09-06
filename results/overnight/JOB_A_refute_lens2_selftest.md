# REFUTER, lens 2 of 3 — the self-test

Target: `C:\kals-repo\research\queuesim.py` (JOB A's stage; the task named
`research/queue.py`, which does not exist — `queue` shadows the stdlib and the
repo's own `shadow.py` guard forbids it, so JOB A's rename is correct).
Report under review: `C:\kals-repo\results\overnight\JOB_A_queue.md`.

**Verdict: REFUTED.** The self-test is green, and it is 26 real checks — but it
constrains only the pure FIFO consumption arithmetic in a world with constant
depth and no queue-camping. **14 of 20 deliberately wrong estimators I planted
pass all 26 checks**, including three that reverse or multiply the headline
money, one that quadruples the fill count through the headline cancel policy,
and one that deletes the null control outright.

I did **not** find a bug in the shipped estimator. I found that the self-test
would not tell you if there were one — which is the thing this repo says the
self-test is for ("the self-test is the deliverable; the estimator is the easy
part", CLAUDE.md).

---

## 1. Line coverage: what the self-test never executes

Traced with `sys.settrace` over `Q.selftest(verbose=True)`.

Inside `simulate_side`, these executable lines are **never reached**:

    275   if change < 0.0:                       <- the ENTIRE cancel-policy block
    276       if policy == "front":
    277           st[1] = max(0.0, st[1] + change)
    278       elif policy == "prorata":
    279           st[1] = (st[1] * (d_cur / after)) if after > 0 else 0.0
    236   st[1] = d_prev                         <- clamp: carried position > current depth
    281   st[1] = d_cur                          <- clamp: position > level at the boundary
    242   continue                               <- the per-trade price match
    186   ti += 1                                <- trade-index advance past an unmatched second

And `run()` — every dollar in the report — **is never called by the self-test
at all.**

## 2. The "× 3 cancel policies" in check (a) is nine identical runs

`_alt_states` flips the touch price every second, so `p_cur != p_prev` on every
iteration and the boundary block is `continue`d past before the policy branch.
The three policies are byte-identical in every world the self-test builds.

On a tape where cancels actually happen (constant touch, depth 5,000 -> 3,000
every other second, 100 contracts trading), the policies are not close:

    policy=behind    10,800 fills    $108.00      -64.0% vs prorata
    policy=prorata   29,999 fills    $299.99       (headline)
    policy=front     59,400 fills    $594.00      +98.0% vs prorata

A 5.5x spread across the assumption the report calls "the one genuinely
unknowable piece", from code no check exercises. The report's real-data bracket
(behind $11,586 / prorata $11,290 / front $11,191, "a 3.5% spread, so the
unknowable piece decides nothing") is a real-data finding produced by untested
code. Note also that fills must be monotone `behind <= prorata <= front` and
the self-test does not assert that free invariant.

## 3. Mutation battery — 14 of 20 wrong estimators pass

Each mutant is one realistic edit to `queuesim.py`; the mutated module runs the
**unmodified** 26-check self-test. Harness:
`C:\Users\Joe\AppData\Local\Temp\kals-work\refute2\mutate.py`.

    CAUGHT  6 / MISSED 14 / ERROR 0

Caught (the test does have some teeth): join the middle of the queue
(`ahead = d_prev/2`), `ahead` not decaying within a second, contiguity dropped,
`recycle=False` made a no-op, the bootstrap lower bound forced up, and
`clustered()` re-weighted by trade count.

**Missed — self-test still green.** Consequence measured on a small realistic
tape (`demo.py`, `demo2.py`, same directory):

| planted wrong estimator | effect | self-test |
|---|---|---|
| headline `prorata` jumps to the FRONT of the queue on any cancel | **+498% fills** | PASSES |
| a print **1c away** from our price fills us | **+98% fills** | PASSES |
| ask-side P&L sign flipped (`pnl = Y - p` on both sides) | **+300% money** | PASSES |
| every fill's P&L doubled | **+100% money** | PASSES |
| settlement outcome inverted (`Y -> 100-Y`) | **+$65,835 -> -$53,865** | PASSES |
| queue sized from `d_cur` (same second) not `d_prev` | +19.4% fills | PASSES |
| sign-scramble control deleted (sign always +1) | control == estimate | PASSES |
| `run()`'s `offset` placebo argument ignored | placebo cannot move | PASSES |
| 10c–90c ZONE (tapered tick) filter removed | re-admits the deci-cent zone | PASSES |
| cancel block deleted entirely | -64% fills | PASSES |
| cancel adjustment sign flipped | (equivalent on my tape) | PASSES |
| both queue clamps dropped; order topped back to S each second | (equivalent on my tape) | PASSES |

The outcome-inversion number is from a bid-only tape (all fills buy YES at 45c);
on a symmetric two-sided tape it is masked because bid and ask P&L sum to a
constant. That is the bug class CLAUDE.md already records: *"`settle` is the
index level, and confusing the two once booked a YES win for every market."*
The current self-test cannot see it.

## 4. Check (b) does not test "always last in queue"

Check (b) builds a level of 1,000 with 900-contract trades and asserts zero
fills. But its price alternates every second, so the estimator **re-joins the
back of the queue 9,995 times over 1,999 seconds** (every second × every size,
instrumented count). The position is never carried. The zero is enforced by the
world, not by the queue logic.

Hold the touch price constant — same depth 1,000, same 900-contract trades,
same "we are always last" claim:

    self-test (b) world, price alternates:  fills [0, 0, 0, 0, 0]
    identical numbers, constant price:      fills [999, 9990, 49950, 99900, 499500]
    modelled queue position after warm-up:  0     (book still displays 1,000
                                                   resting at the END of every second)

Because `ahead` is only ever clamped **down** (`elif st[1] > d_prev`) and never
re-based upward, once a taker clears the queue we sit permanently in front of a
level that keeps redisplaying 1,000 contracts. That is defensible if 100% of the
refill is new orders joining behind us — but it is an assumption, it is the
regime the headline's fills actually come from, and check (b) has zero coverage
of it. The `recycle=False` bound is the report's answer to camping, and it is
the one camping-related thing the self-test does check.

## 5. The null/shuffle control is at the wrong level, and is untested

`run()` draws an independent sign **per fill**:

    sh[close] += rng.choice((1.0, -1.0)) * pnl * q / 100.0

Every fill in one market shares one settlement `Y`, so the real estimator's
per-close P&L is comonotone. Scrambling per fill destroys exactly the dependence
the control exists to preserve. On 400 closes × 3,000 fills, one outcome each:

    real estimator                     per-close sd  $1,500.00
    run()'s control (sign PER FILL)    per-close sd  $   27.06   <- 55x too tight
    correct control (sign PER CLOSE)   per-close sd  $1,501.80

Check (d) scrambles per fill too, so the self-test cannot detect the level
error; and mutant 17 shows the control could be removed entirely with the
self-test still green. The real tape is only partly comonotone (9 markets per
close, prices vary), so the real factor is smaller than 55x — the report's own
shuffle interval at S=50 is [-$1,943, +$1,496] against a real interval of
[+$8,027, +$14,529] — but the control is not the random-sign companion
CLAUDE.md asks for.

## 6. Two smaller things

* Requirement (c) is verified only through the outer `traded_here` aggregate
  gate. The inner per-trade price match (`if tp != p_prev: continue`) is never
  executed, because check (c)'s world contains **no** trade at the touch at all.
  Widening that match to ±1c passes the self-test and nearly doubles fills.
* `main()` does hold the gate correctly (`KALS_SELFTESTED` or run the self-test
  before touching real data). `queuesim_full.log` contains no "self-test passed"
  line, so the production run was made with `KALS_SELFTESTED=1`. The self-test
  does pass — I ran it — so this is bookkeeping, not a breach.

## What survives

* The self-test is not empty. Check (a) is a genuine closed-form plant and it
  rejects queue-position errors as small as one contract; six of my twenty
  mutants died on it.
* No error in the shipped estimator was demonstrated. This lens says the gate
  is weak, not that the number is wrong.

## What would fix it

Four checks, all cheap: (i) a world with a **constant** touch price and depth
that falls by more than the traded volume, asserting each policy's closed form
and `behind <= prorata <= front`; (ii) a carried-position world asserting the
"always last" property where the position is actually carried; (iii) a
`run()`-level plant — a hand-built book/trades/settlement triple whose dollars
are known in closed form, which would catch every money mutant above and the
`offset` placebo; (iv) scramble the sign **per close**, and assert the per-fill
version is rejected.

---

## Protocol

* **Both collectors alive before and after.** `kalshi_collector.py` pid 2708908
  at 25.6 MB, `crypto_feeds.py` pid 531268 at 14.1 -> 14.2 MB.
* Nothing was written to `kalshi_data/` or `feed_data/`; neither was opened.
  `replay.load_quotes` was **not** called. `flow.py` was not rebuilt. The real
  measurement was **not** re-run — this lens needed only the self-test, which is
  pure synthetic, so the heaviest process I ran was a few MB.
* Free RAM 3.67 GB before, 3.66 GB after (another agent's 462 MB job was
  running throughout; I left it alone). No `python.exe` was killed.
* **Free disk 52.07 GB.** Well above the 4 GB stop threshold.
* Files written: this report, plus
  `C:\Users\Joe\AppData\Local\Temp\kals-work\refute2\{cover,mutate,demo,demo2}.py`
  and their generated mutant modules. No file under `C:\kals-repo\research`
  was modified.
