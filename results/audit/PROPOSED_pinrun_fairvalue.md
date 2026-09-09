# PROPOSED patch — fair value / settlement model (pinrun.py)

Written 2026-09-08 by an audit that did **not** edit the live path. `pinrun.py`
on disk fingerprints `d6826548c653`, which is exactly the `code_sha` in the
running process's own start record, so everything below describes the code that
is trading. **Nothing here has been applied.** Applying any of it requires a
process restart, which is the operator's call.

Ordered by how much money the defect can cost.

---

## P1 — index staleness is measured on the EXCHANGE's clock, one-sided

`pinrun.py:228-235`, `IndexWS.spot()`:

    s = max(d)
    return s, d[s], time.time() - s          # <-- content timestamp

`s` comes from `data["time"]//1000` in `on_frame` — the CF Benchmarks second.
So `age = (our clock) − (their clock)`, and `pinrun.py:1043` tests only
`iage > MAX_INDEX_AGE_S`. **Measured:** injecting one tick stamped 8 s in the
future into a feed frozen for 10 s makes `spot()` report `age = −7.87 s`, and
the gate **passes**. A local clock running slow does the same thing
permanently and silently. (Local clock checked against Kalshi's own `Date`
header three times today: local is AHEAD by +0.31 to +0.82 s — the safe
direction, today, unmonitored.)

`self.last_rx` (line 185, written line 224) already holds the LOCAL receive
ms of each tick and **is read by nothing**. Proposed:

    def spot(self, iid):
        """(second, value, age_seconds) of the newest tick, or (None,None,None).

        age is the MAX of two independent clocks:
          content age = now - the tick's own CF Benchmarks second
          receive age = now - the LOCAL ms at which that tick arrived
        Content age alone is (our clock - their clock): a local clock running
        slow, or one future-dated tick, reports stale data as fresh, and the
        gate is one-sided so it never fires on a negative age. Receive age uses
        only our own clock -- the same quantity livebook already gates the book
        on (MAX_BOOK_AGE_MS). Measured 2026-09-08: a feed frozen for 10 s plus
        one +8 s tick reported -7.87 s and passed a 2 s gate.
        """
        with self.lock:
            d = self.ticks.get(iid)
            if not d:
                return None, None, None
            s = max(d)
            v = d[s]
            rx = self.last_rx.get(iid)
        now = time.time()
        content_age = now - s
        recv_age = (now - rx / 1000.0) if rx is not None else content_age
        if content_age < -1.0:
            self.stats["future_dated"] += 1     # visible, not silent
        return s, v, max(content_age, recv_age)

Self-test to add (it FAILS on today's code, which is the point):

    idxF = IndexWS(["F"])
    nowS = int(time.time())
    for s in range(nowS - 400, nowS - 9):
        idxF.ticks["F"][s] = 1.0
    idxF.last_rx["F"] = (nowS - 10) * 1000.0
    idxF.ticks["F"][nowS + 8] = 1.0                 # one future-dated tick
    _, _, ageF = idxF.spot("F")
    ck(ageF > MAX_INDEX_AGE_S,
       f"a future-dated tick cannot make a 10 s stale feed look fresh "
       f"(age {ageF:.2f}s)")

---

## P2 — `sigma()` samples the last 300 PRESENT seconds, not the last 300 seconds

`pinrun.py:237-248`:

    secs = sorted(d)[-SIGMA_WIN:]        # last 300 seconds we HOLD

`self.ticks` retains 1,200 seconds, so after an index outage this window is
dominated by pre-outage tape. **Measured** on a synthetic feed (600 s at
sigma 0.01/s, a 240 s outage, then tape at 0.05/s), with the settlement window
fully covered so `partial()` accepts:

| fresh tape since the outage | sigma sample pre-outage | sigma returned | vs true 0.05 |
|---|---|---|---|
| 61 s | 239/300 (80%) | 0.0238 | **2.10x too small** |
| 120 s | 180/300 | 0.0316 | 1.58x too small |
| 240 s | 60/300 | 0.0458 | 1.09x too small |
| 300 s | 0/300 | 0.0497 | 1.01x |

`partial()` recovers ~60 s after an outage; `sigma()` takes ~300 s. In between,
the model trades on a pre-outage volatility, and understated sigma is the
direction that makes it overconfident. `sigma()` also returns **exactly 0.0**
for a feed whose value is frozen but whose timestamps advance.

Proposed — window in WALL seconds, a coverage floor expressed in terms of
`SIGMA_WIN` (never a literal), and no zero:

    SIGMA_MIN_FRAC = 0.5                 # of SIGMA_WIN, not a literal count

    def sigma(self, iid, now_s=None):
        """sd of 1-second index diffs over the last SIGMA_WIN WALL seconds.

        Not the last SIGMA_WIN seconds we happen to hold: after a feed gap
        that window is mostly pre-gap tape and understates current vol by up
        to 2.1x (measured 2026-09-08), which is the direction that makes the
        model overconfident. A frozen-but-printing feed gives sd exactly 0,
        which fair() then turns into a hard 0/1 -- refuse instead.
        """
        now_s = int(time.time()) if now_s is None else int(now_s)
        with self.lock:
            d = dict(self.ticks.get(iid) or {})
        lo = now_s - SIGMA_WIN
        secs = sorted(s for s in d if lo <= s <= now_s)
        diffs = [d[secs[i]] - d[secs[i - 1]]
                 for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
        if len(diffs) < SIGMA_MIN_FRAC * SIGMA_WIN:
            return None
        mu = sum(diffs) / len(diffs)
        sg = math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))
        return sg if sg > 0.0 else None

**The guard needs its own null, per CLAUDE.md.** On a healthy 1/sec feed the
window holds ~300 seconds and ~299 usable diffs, so `SIGMA_MIN_FRAC = 0.5`
discards nothing. Add `sigma_n=len(diffs)` to the `signal` record for a run so
the operator can see the healthy distribution before this ever binds.

Caller change at `pinrun.py:1045`: `sg = idx.sigma(iid, now_s)`.

---

## P3 — `fair()` asserts certainty when it has no volatility estimate

`pinrun.py:385-386`:

    if sd <= 0:
        return 1.0 if mu >= K else 0.0

**Measured:** a feed printing a constant 500.0 gives `sigma() == 0.0`, and
`fair()` then returns exactly `1.0` for a strike `1e-9` below spot and exactly
`0.0` for a strike `1e-9` above it — a `+4.66c` model edge and `+3.76c` EV
against a 0.95 offer, on a market whose true probability is a coin flip.
Every downstream gate passes.

P2 removes the only way to reach this today, but the branch should not assert
certainty regardless:

    if sd <= 0:
        return None        # no risk estimate is not zero risk

Leave the `r <= 0` branch (line 382) alone — with all 60 prints in hand the
outcome genuinely is determined, and the CORRECTION-1/2 self-test fixtures
depend on it. It is unreachable at `TAU_MIN = 3` anyway (verified: `r = tau-1`
for `1 <= tau <= 61`, `r = 0` only at `tau <= 1`).

---

## P4 — every health rejection is invisible in the log

`pinrun.py:1038-1047`. `suspect` book, stale book, missing/stale index, missing
sigma and `fair() is None` all `continue` **before** `near` is touched, so they
appear in no counter and no record. A run that is completely blind — a dead
index thread, for instance — writes **no `close_summary` at all**, because
`near` stays empty and `report_closes` iterates it.

That is the same failure the v8 entry in `results/VERSIONS.md` was written
about: "the refusal was invisible in the log that was written specifically to
explain refusals."

Also `pinrun.py:1080` vs `1087-1088`: the dust test runs twice and the second
one sits behind the first one's `continue`, so `nb["dust"]` can never
increment. Confirmed live — `dust` is `0` in all 28 `close_summary` records
that carry it, and dusty levels are not counted in `looks` or `decided`
either. "0 dust" is currently not evidence of anything.

Proposed: add the reasons to `_fresh_near()` and count them before each
`continue`; count dust once, before skipping:

    def _fresh_near():
        return {"best": None, "n": 0, "decided": 0, "tradeable": 0,
                "no_offer": 0, "undecided": 0, "dust": 0,
                "book_suspect": 0, "book_stale": 0,
                "index_stale": 0, "no_sigma": 0, "no_fair": 0}

and emit those five in both `close_summary` branches.

---

## P5 — a truncated strike can reach the model when `round_digits >= 5`

`pinrun.py:1000-1010` uses `custom_strike.floor_strike` when present and the
top-level `floor_strike` otherwise. **Measured live 2026-09-08 across all 9
series with open markets:** `custom_strike.floor_strike` is present for
**DOGE only**; every other series returns `None` there and a top-level strike
that carries exactly `round_digits` decimals. DOGE's top-level is `0.09069`
against an exact `0.0906904` — truncated by `4.0e-7`, which is **8x** the
`5e-8` rounding correction and about **0.07 sd** at DOGE's measured
`sigma = 7e-6/s` and `tau = 20`.

So the code is right today, by exactly one field that the exchange supplies for
exactly one series, with no assertion that it is there. Proposed guard:

    if d is not None and int(d) >= 5 and cs_.get("floor_strike") is None:
        rec("skip", why="truncated_strike", ticker=m["ticker"],
            round_digits=d, floor_strike=sk)
        continue

Null on a healthy feed: **zero markets discarded** — DOGE is the only series
with `round_digits >= 5` and it carries the exact field.

---

## P6 — `now_s` is captured BEFORE the universe pass, so `tau` is overstated

`pinrun.py:1015-1016` takes `now = time.time()` and then the universe block
(from `pinrun.py:1018`) makes 11 sequential blocking GETs before the market
loop uses `now_s`. **Measured: those 11 GETs take 0.84 s** (76 ms each) from
this box right now; `kauth.get` has `timeout=20`, so the structural worst case
is 220 s.

Direction: `tau` is reported too large, `partial()` treats one or more already
locked prints as unknown, so `sd` comes out too **large** — conservative on
variance. But it substitutes spot for prints already on the tape, which is the
"SPOT SUBSTITUTION" error named in the module docstring as the real cause of
the only loss in the replay, and it can admit a market whose true `tau` is
below `TAU_MIN`. One-line fix — re-read the clock inside the market loop:

    for tk, (iid, close_s, strike, digits, exi) in list(seen_markets.items()):
        now_s = int(time.time())          # not the pre-universe-pass clock
        tau = close_s - now_s

---

## Not proposed, but the number the operator should see

`SIGMA_STRESS = 1.0` — no cushion. `sigma` is estimated backward over 300 s and
used forward over 3–30 s. For each of the 17 real live signals I computed `k`,
the factor by which true sigma must exceed the estimate for the model's own
implied flip rate to reach the exact breakeven flip rate `f* = 1 − p − fee(p)`:

    k: min 1.06x   median 1.34x   max 2.70x
    12 of 17 trades die at k = 1.5x;  15 of 17 at k = 2.0x

`k > 1` is guaranteed by the `EDGE_FLOOR` gate (it requires
`f_model <= f* − 0.003`), so the design is sound — but the margin is one third
of a volatility estimate, and a 1.34x forward/backward vol ratio over a
five-minute horizon in crypto is ordinary.

**I did not measure the real distribution of that ratio.** Doing it needs the
index tape loaded, and free RAM was 2.2 GB with three analysis jobs already
running; the collector outranks the measurement. That measurement — the
empirical distribution of `sigma[next 30 s] / sigma[trailing 300 s]` per index —
is the highest-value thing left to run in this dimension, and it is what should
set `SIGMA_STRESS`, not a guess.

---

## What was checked and found CORRECT

- `sd = sigma * sqrt(var_factor(r, [1.0]))` with `mu = (locked + r*spot)/60`.
  `var_factor` already divides by `N_AVG**2`, so both halves are in
  settle-average units and no `60/r` rescaling is needed or present. Verified
  against a 200,000-path Monte Carlo at `r = 1,2,5,10,19,29,59,60`: analytic
  vs simulated sd ratio 0.9974–1.0024.
- `IndexWS.partial()` boundaries: `r = tau − 1` for `1 <= tau <= 61`, `r = 0`
  at `tau <= 1`, `r = 60` at `tau >= 61`, locked count `61 − tau`. Identical to
  `settlewin.partial()` at every tau tested (0,1,2,3,4,5,10,20,29,30,31,59,60,
  61,62) on a complete tape. `settlewin.py --selftest` passes.
- `eff_strike(K, d) == K − 0.5*10^-d` and it agrees exactly with
  `endgame.settle_threshold` on BTC/ETH/SOL/DOGE and on `d = None`.
- `round_digits` is READ from `custom_strike.round_digits` on every market,
  never assumed. Live: `"2"` for BTC/ETH/BNB, `"4"` for SOL/XRP/ZEC/HYPE/NEAR,
  `"7"` for DOGE. The live log shows DOGE traded with `digits 7`.
- `strike_type` is `greater_or_equal` and `cap_strike` is `None` on all 9
  series with open markets, so `fair = P(settle >= K_eff)` has the right sense
  and the NO side is `1 − fair`. (The code never reads `strike_type`; it is
  right by fact, not by construction.)
- `exchange_index` is 2 on all 9, matching what the order path sends.
- "Fewer than a handful of prints" cannot reach the model: `partial()` refuses
  a settlement window missing more than 5% of its prints, which forces at least
  ~57 consecutive seconds into `sigma()`'s sample. The `len(diffs) < 20` floor
  is not the binding constraint — staleness is.
- A frozen index feed with no future-dated ticks IS caught: age grows past the
  2 s gate. `pinrun.py --selftest` passes all 52 assertions.
