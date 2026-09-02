# The bias catalogue — every pattern this project has actually shipped

Not a textbook list. Every entry below is a bug that was written, believed,
published as a result, and only later caught. The count in brackets is how many
distinct files have carried it.

Use this as the checklist for any new estimator, and re-run it against files
that are *new*: the 2026-08-28 audit excluded `calib.py` as "written this
week" and it carried pattern 4, found separately the same day. **Newness is a
risk factor, not a defence.**

---

### 1. Look-ahead / hindsight  [4]
Information used at decision time that would not have been available then.
- `endgame.py` drew `strike = settle + noise` — the strike depended on the
  future settlement value, making every market a 50/50 regardless of the tape.
- `cross.py` priced markets with FULL-SAMPLE index variance.
- Taking the LARGEST model-vs-market disagreement in a window: finds where the
  MODEL is most wrong, not the market.

### 2. Occupation-time / endogenous sampling  [2]
Sampling at moments the market chose. Quote intensity rises with volatility, so
"implied vol at a typical quote" divided by a calendar-time realised vol picks
up the coupling. Fix: an exogenous fixed-interval grid.

### 3. One-sided trim of a symmetric error  [1]
`implied.py` returned None for `sd <= 0`, deleting only the negative half of a
symmetric estimation error and manufacturing a "frown" out of a flat surface.

### 4. Wrong clustering unit  [5]
`n` reported as trades when every fill in a window settles on ONE outcome; iid
SEs on clustered data; clustering by market when the shared shock is the close
TIME across all series. Cluster by market, always; report n as markets.

### 5. Future-dependent weights  [1]
`pathstats.py` weighted clusters 1/K where K counted FUTURE gridpoints —
−1.46c of fake reversion out of an exact martingale.

### 6. Stale-vs-fresh asymmetry  [2]
`edge.py` scored a gridpoint model against a trade print up to 60s stale; a
proper scoring rule pays the fresher forecast by construction.
`implied.collect`'s 30s carry-forward inverts a stale quote through a
`var_factor` that has since collapsed — 7.58x at tau=10.

### 7. Pooling across the dimension the theory says matters  [3]
`proxy.py` pooled scale; `implied.py` pooled tau bands. Measured cost: a book
quoting each window's own true sigma, scanned with one pooled sigma per series,
claims +2.5c and realises −4.2c against a TRUE EDGE OF ZERO.

### 8. Selection on the measured quantity  [1]
Filtering on |z| computed with the row's OWN implied sigma is selection on the
thing being measured; because `sqrt(var_factor(tau))` shrinks into the close it
selects differently at each tau, manufacturing a term structure out of a flat
one. Filter on a reference value instead.

### 9. The wrong null  [2]
Testing against zero when the honest null is negative (any sub-second quote lag
makes the honest-maker null negative). A "significant" result against the wrong
null is not a result.

### 10. A fixture that does not test what is reported  [3]
Checking one number and printing a different one — the test passes and means
nothing. Also: a fixture that clamps quotes to [1c, 99c] and then asserts the
book is "correctly priced" when the clamp itself is a 0.9c mispricing.

### 11. Trimmed statistic reported as the full-sample one  [1]
`chain.py` printed a winsorised kurtosis of 4.7 where the true value was 14.9 —
the exact statistic whose whole purpose is to see the tail.

### 12. Silent empty loader read as a null result  [4]
Schema drift (`price` → `price_dollars`), a wrong `--out`, a stale cached
`schema.json`. 1,399,175 quotes read, zero understood, "no edge found" printed.
Every loader must refuse LOUDLY with the absolute path it tried.

### 13. Multiple looks  [1]
Choosing the tau cap, price band or window after seeing which one worked. State
every cut up front and report them all.

### 14. Detection asserted without power  [2]
Asserting `t > 3` where the sample could never produce it: certifying a 0.5c
edge at a 46c per-trade sd needs ~76,000 markets against 3,600 recorded. Print
the MDE next to every null.

### 15. Environment divergence  [3]  ← added 2026-08-28
**Behaviour that differs between the machine the code is written on and the
machine that runs the data, where the writing machine reports clean.** This is
the newest and it cost a whole evening in one night:

- `research/compression.py` shadowed the stdlib package Python 3.14 added.
  Invisible on 3.11 (where `gzip` imports `_compression`), fatal on 3.14.
- `shadow.py`'s first import probe deleted `sys` from `sys.modules` and
  re-imported it, losing `sys.stderr`. Survived on 3.11 by luck; killed the run
  on Windows 3.14.
- The same file compared paths with `startswith` on a case-sensitive basis,
  which silently answers "not ours" on Windows.

Mitigations now in place: `research/shadow.py` (probes in a CHILD interpreter,
carries a forward-compatibility list of names that are stdlib in newer Pythons
than the one running), a `PREFLIGHT` in `go.py` that runs even under `--only`,
and the operator script refusing to run when HEAD does not match origin.
**The general rule: a self-test that only ever runs on the development machine
cannot certify anything about the run machine. Where the two differ, test on
the run machine's version.**

---

### 16. The fixture disagrees with the collector  [4]  ← added 2026-08-29

Pattern 15 was written about Python versions. The 2026-08-29 audit found the
same shape four more times, and none of them involved Python at all. In every
case a fixture and the real world differed in **one detail the fixture's author
chose**, and the self-test passed on a world that does not exist:

- `endgame.py` wrote `"settle": settle > strike` — a **bool** — where the
  collector writes the settled index LEVEL with the outcome in `result`. The
  estimator read the truthiness of a price. Every market on the tape booked a
  YES win and a full P&L table was published from it. Every other fixture in
  the repo (`replay.py`, `edge.py`) matched the collector; this one did not.
- `implied._build` emitted a quote **every 3 seconds**, so no fixture in this
  project had ever produced a quote more than 2 seconds stale. `term.py`'s
  staleness rule was built and validated entirely inside that blind spot; at
  20-second spacing it returned β = −0.487 (t = −7.7) on a book whose true β
  was exactly zero.
- `surface.availability()` medianed spreads over **messages** where the channel
  is publish-on-change and the analysis needs a per-second grid — the same
  occupation-time bias `implied.collect()` had been fixed for days earlier.
- `surface`'s settled simulation had an MDE of ~1.8¢ against costs of ~1¢, so
  deleting the entire taker fee left it **passing**.

**A fixture is a claim about reality.** An untested claim about reality is
exactly the thing this project exists to distrust, and a self-test built on one
inherits its error silently and then certifies it.

Practical rules that follow:
1. **A fixture must use the producer's schema, verbatim.** If the collector
   writes a float, the fixture writes a float. Never a "cleaner" equivalent.
2. **Sweep the parameter the fixture holds fixed.** Quote spacing, message
   rate, gap size, field type. The constant nobody thought about is where the
   estimator has never been looked at.
3. **A self-test must be shown to FAIL.** Plant the bug it claims to catch and
   watch it fail; a check whose MDE exceeds the effect it guards is decoration.

---

### 17. A cluster standard error off a handful of clusters  [1]  ← 2026-09-01

`oos.py` allowed a cell to report as long as it had **three** close-time
clusters. On its first real-data run the min-edge 2.00c cell printed

    trades / closes   16 / 12
    realised P&L      +9.60c   t = +12.28
    MDE               2.35c

A t of twelve is the number that ends an argument, and it came from twelve
observations. The tell was there in the same block: the MDE of **2.35c was
LOWER than the 11.58c of the cell above it**, which is impossible for a strictly
smaller sample and can only mean the standard error had stopped being an
estimate of anything.

The floor is thirty clusters now, and a cell below it prints the raw mean with
an explicit statement that no significance is claimed — because suppressing the
number entirely invites someone to compute it by hand without the warning.

**A filter that tightens until only a few observations survive will always end
in a spectacular t.** Any sweep over a threshold needs a floor on what survives
it, stated before the sweep runs.

### 18. The fixture plants the effect in the wrong place  [1]  ← 2026-09-02

`flow.py` asks whether order flow at second *t* predicts the mid move from *t*
to *t+k*. Its self-test builds a world where the answer is a loud yes: size
lands on the side the price is about to move toward.

The first version of that fixture emitted the flow at `sec*1000+200` and the
price move at `sec*1000+700` — **the same second**. So the planted effect was
*contemporaneous*, not predictive. The forward regression correctly read zero.
Had that code been pointed at real data, a genuine null and a broken fixture
would have printed identically, and the honest conclusion "order flow does not
predict the next move" would have been unfalsifiable.

What caught it was the **backward check**: the same *x* against the move that
has already finished. It read `t = +340` while forward read `t = -0.91`. An
estimator that can find an enormous effect one second in the past and nothing
one second in the future is not measuring the future — it is measuring the
present and calling it the past.

A second, subtler version of the same failure followed. Once the timing was
fixed, the *backward* check read zero, because the fixture's book was one level
deep on each side: a price step deleted the only level, the side went
momentarily empty, the order-flow chain reset, and the reactive flow that every
real move generates contributed exactly nothing. Real books are laddered and
never do this. **A fixture simple enough to reason about is often simple enough
to be degenerate in exactly the dimension being measured.**

**Any test for a forward-looking effect needs a backward-looking companion that
must be large.** A null result is only interpretable from an estimator that has
been shown, on the same data path, to be capable of finding something.

---

## The two meta-rules

1. **Every exciting result this project has produced so far was a measurement
   bug.** Treat anything eye-catching as a bug until it survives its own null.
2. **Test against a planted answer before touching real data.** Build a world
   where the truth is known, and fail if the estimator misses it OR finds
   something in a world where nothing was planted.
