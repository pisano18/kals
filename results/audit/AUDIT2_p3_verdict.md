# AUDIT of finding "fair() returns a hard 1.0/0.0 when sigma is zero" (P3)

Read-only. **Nothing was edited on the live path.** `research/pinrun.py` on disk
hashes `d6826548c653`, which is the `code_sha` in the running process's own
`start` record (`results/pinrun-live-20260908T163644Z.jsonl`), so this describes
the code that is trading: size 5, tau 3-30, pin 0.98, edge floor 0.3c,
EV floor 0.3c, price ceiling 0.988, max-positions 3, loss-abort -21.00.

## 1. The code is exactly as described

`research/pinrun.py:371-387`

    def fair(idx, iid, close_s, now_s, strike, sigma, round_digits=None):
        ...
        if r <= 0:
            return 1.0 if mu >= K else 0.0
        sd = sigma * math.sqrt(var_factor(int(r), [1.0]))
        if sd <= 0:
            return 1.0 if mu >= K else 0.0
        return ND.cdf((mu - K) / sd)

`research/pinrun.py:1045-1049` is the only caller on the live path:

    sg = idx.sigma(iid)
    if sg is None:
        continue
    f = fair(idx, iid, close_s, now_s, strike, sg * SIGMA_STRESS, ...)

`sg == 0.0` is not `None`, so there is **no guard between `sigma()` and
`fair()`**. `SIGMA_STRESS` is 1.0 and has no CLI flag.

## 2. sd <= 0 can only come from sigma == 0 (measured)

`var_factor(r,[1.0]) > 0` for every `r` in 1..60 (only `r = 0` gives 0.0), and
`partial()` returns `r = tau-1`, so `r >= 2` at `TAU_MIN = 3`. The `r <= 0`
branch is unreachable live; the `sd <= 0` branch is reachable only via
`sigma() == 0.0`.

## 3. The chain reproduces (results/audit/AUDIT2_p3_repro.py)

* a feed printing a constant value gives `sigma() -> 0.0` (not `None`)
* `fair()` then returns exactly `1.0` for a strike `1e-9` below spot and
  exactly `0.0` for a strike `1e-9` above it -- the side is chosen on the sign
  of a difference the model has no ability to resolve
* every downstream gate passes at any price up to the EV ceiling:

  | price | net_edge | EV | fires? | TRUE EV if p\*=0.5 |
  |---|---|---|---|---|
  | 0.50 | +48.25c | +47.34c | YES | **-1.76c** |
  | 0.60 | +38.32c | +37.41c | YES | **-11.69c** |
  | 0.90 | +9.37c | +8.47c | YES | **-40.63c** |
  | 0.95 | +4.67c | +3.76c | YES | **-45.34c** |
  | 0.988 | +1.12c | +0.21c | no (EV floor) | |

  At `--size 5` and `MAX_PER_CLOSE = 2` that is up to $10 of stake on one
  close bought on a coin flip.

* **no existing self-test exercises `sigma == 0`.** `selftest()` calls
  `fair()` only with hand-supplied sigmas of 1.0 and 0.02 and never calls
  `IndexWS.sigma()`.

## 4. Reachability -- the part the original finding did not measure

`sigma()` needs `len(ticks) >= 30` and `>= 20` consecutive-second diffs, and
returns 0.0 iff **every** diff in its sample is identical. Its sample is the
last 300 seconds it HOLDS, so the requirement is a bit-identical flat run as
long as the whole tick history, capped at 300 s.

Measured over the whole tape (`AUDIT2_sigma_zero_scan.py`,
`AUDIT2_flatrun_history.py`), 332 hourly files, 349.2 h, 11 indices,
~12.5M index-seconds:

| | |
|---|---|
| 300-second windows evaluated (17.3 h slice, 11 indices) | 681,989 |
| windows with `sigma == 0` | **0** |
| windows with `sigma < 1e-9` | 0 |
| minimum consecutive-second diffs per 300-window (whole tape) | 295-297 |
| windows with fewer than 50 diffs | **0** |

So the feed is dense (the sparse-tick route to a 20-diff sample never occurs)
and the longest bit-identical flat run ever recorded, per index, is:

    SOL 163 s   NEAR 81 s   DOGE 22 s   XRP 17 s   BCH/ETH 16 s   ADA 15 s
    BNB 13 s    HYPE 10 s   BRTI 5 s    ZEC 3 s

In steady state ~295 identical diffs are required and the record is 163, so
**`sigma() == 0` is unreachable in steady state on 349 h of real tape.**

The one route that survives is the **first 30-300 s after a process restart**,
when the tick history is shorter than 300 s and the flat run only has to cover
all of it. The minimum is a 30 s flat run beginning at process start
(`AUDIT2_p3_repro.py` section 2: 30 frozen seconds -> `sigma 0.0`;
22 -> `None`). `partial()`'s 95% coverage test then restricts which tau are
live: at 30 s of history only tau 29-30, at 45 s tau 13-30, at 60 s+ all of
tau 3-30. SOL (163 s) and NEAR (81 s) both have runs long enough.

## 5. What it would cost if it fired

`pintake.check_take` has no model input, so nothing there refuses a wrong fair
value. The money is bounded by the ledger rails, not by the model:
`pintake.LOSS_ABORT` is **-2.00** and `pinrun` never overrides it, so after
$2.00 of *realised* loss every subsequent take is refused at the order stage
regardless of `--loss-abort -21.00`. Realistic worst case from this defect is
one or two bad closes, roughly $3-$10.

## 6. PROPOSED change (NOT APPLIED -- requires a restart, operator's call)

`research/pinrun.py:385`

    -    if sd <= 0:
    -        return 1.0 if mu >= K else 0.0
    +    if sd <= 0:
    +        # No volatility estimate is not zero volatility. sigma() returns
    +        # exactly 0.0 for a feed whose value is bit-identical across its
    +        # whole sample, and this branch then asserts certainty and picks
    +        # the side on the sign of a difference the model cannot resolve.
    +        # Declining is not the same as being certain.
    +        return None

Leave the `r <= 0` branch at line 382 alone: with all 60 prints in hand the
outcome genuinely is determined, it is unreachable at `TAU_MIN = 3`
(`r = tau-1`), and the CORRECTION-1/2 self-test fixtures depend on it.

Self-test to add -- it FAILS on today's code, which is the point, and it is
written against the CONSTANTS, not against literals:

    # a frozen-but-printing feed has NO volatility estimate; fair() must
    # decline rather than assert certainty and pick a side on a 1e-9 sign.
    zf = IndexWS(["ZF"])
    Cz = 1_000_000
    for s in range(Cz - (SIGMA_WIN + 100), Cz - TAU_MIN):
        zf.ticks["ZF"][s] = 500.0
    ck(zf.sigma("ZF") == 0.0,
       "a bit-flat feed gives sigma exactly 0.0, not None (the input)")
    for eps in (1e-9, 1e-6, 0.01):
        ck(fair(zf, "ZF", Cz, Cz - TAU_MIN, 500.0 - eps, zf.sigma("ZF"),
                round_digits=2) is None,
           f"fair() declines with no volatility estimate (strike-{eps:g})")
        ck(fair(zf, "ZF", Cz, Cz - TAU_MIN, 500.0 + eps, zf.sigma("ZF"),
                round_digits=2) is None,
           f"fair() declines with no volatility estimate (strike+{eps:g})")

## 7. What this fix does NOT fix

`sd <= 0` is an exact-equality corner. A sigma that is merely *tiny* skips this
branch entirely and `ND.cdf` still returns 1.0 to full float precision. The
smallest sigma in a real live signal today was **7e-06** (DOGE,
`results/pinrun-live-20260908T114547Z.jsonl`), giving `sd(tau=30) = 1.1e-05`.
Any `|mu-K|` above ~9e-05 is already a hard 1.0 out of `ND.cdf`. So this patch
removes an assertion of certainty but does not make the model humble; that is
P2's `sigma()` window fix and a sigma floor, and they should go together.

---

# ADDENDUM — the reachable route was backtested against real settlements

`results/audit/AUDIT2_p3_backtest2.py`. SOL and NEAR are the **only** indices
whose bit-identical flat runs ever reach the 30 s `sigma()` needs (census over
349.2 h: SOL 163 s, NEAR 81 s, then DOGE 22, XRP 17, BCH/ETH 16, ADA 15,
BNB 13, HYPE 10, BRTI 5, ZEC 3). SOL is quantised to **$0.01** at ~$103
(310 distinct values in 24 h) — that, not a feed fault, is why it sits still:

    10:45:11Z 103.47 | 10:45:12Z 103.46 ... 59 s ... 103.46 | 10:46:11Z 103.45

For every settled market in `fulltape/markets.json` (round_digits **4** — SOL
and NEAR strikes carry 4 dp) I stepped tau = 3..30 on an exogenous grid and
kept the moments where a freshly-started process could have `sigma() == 0.0`
(a >= 30 s flat run ending at `now`, and some history length 30..300 s that
still satisfies `partial()`'s 95% coverage of `[close-60, now]`):

| | KXSOL15M | KXNEAR15M |
|---|---|---|
| settled markets with index cover in tau[3,30] | 1,015 | 1,016 |
| moments where `sigma()` could be 0.0 | **194** | **4** |
| hard `sd<=0` verdict WRONG vs settlement | **0** | **0** |
| a properly estimated sigma fires the SAME side | 194 | 4 |
| a properly estimated sigma fires the OPPOSITE side | 0 | 0 |
| **fires ONLY because sigma was 0 (the defect's own trades)** | **0** | **0** |

**The defect's own trade set is empty on 12.5 days of the only tape that can
produce it.** Where the branch is reachable, the index is quantised rather than
faulty, the real sigma is already small enough that `ND.cdf` returns 1.0/0.0 to
full float precision, and the verdict was right 198 times out of 198.

## Verdict

* **The code defect is real and I reproduced it end to end.** `sigma()` returns
  `0.0`, `fair()` asserts certainty, the side is chosen on the sign of an
  unresolvable difference, and no gate between them or after them objects.
* **The severity claim "loses-money" is NOT supported.** There is no measured
  path to a loss. In steady state the branch is unreachable (needs ~295
  identical consecutive-second diffs; the record in 349 h is 163). The only
  live route is the 30-300 s warm-up after a restart, it needs SOL or NEAR to
  be bit-flat across the process's entire tick history AND a close at
  tau 3-30 inside that run, and on the tape where that lines up the branch was
  never wrong and never generated a trade a correct model would not have made.
* Money is separately bounded: `pintake.LOSS_ABORT` is **-2.00** and `pinrun`
  never overrides it, so realised losses past $2.00 refuse every further take
  regardless of `--loss-abort -21.00`. (That literal is itself a size-1-era
  constant that does not scale with `--size` — a separate finding, not this
  one.)
* **Recommendation: fix it, but do not restart for it.** `return None` is one
  line, strictly safer, cannot change any decision the measurement found, and
  costs nothing. Fold it into the next scheduled restart together with P2.
  Restarting a winning process today to fix a branch with zero measured
  decision impact is the more expensive of the two mistakes.
