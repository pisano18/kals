# D_frozen_index — why no `hedge_blind` was written for KXDOGE15M-26SEP222245-45

Close `2026-09-23T02:45:00Z` (10:45 PM ET 09-22). Run
`results/pinrun-live-20260923T003317Z.jsonl`. All line numbers are
`research/pinrun.py` **as it was running**: the file's SHA-256 prefix is
`b359cfa7f841`, which is the `code_sha` in that run's own `start` record, and
it is identical in the worktree at HEAD `0a15fbf` — 14,090 lines, unmodified.

---

## Headline — there are two answers and the brief's premise is the wrong one

**1. No `hedge_blind` was written because there was no stale index to report.
K3 was not broken here; it had nothing to say.** The largest index age
anywhere in this run is **1.1 s** (44 `signal`/`order` records carry
`index_age_s`; median 0.52 s, 12 of 44 above 1.0 s, **none above 1.5 s**),
against a 2 s bar.

**2. The index was NOT frozen for those nine seconds. The *log* was.** The
byte-identical `0.0514329175139725` at tau 9→1 is `last_belief` no longer
being **written**, not the index no longer **printing** — pinrun.py **10967**
skips a fully-covered position *above* the line that writes it (11066), and
`hedge_quote` (11461) only reads it. This confirms `B_verify.md` §3 and
refutes `A_autopsy.md` §3 ("the model went blind for the last 9 seconds").

**3. The real defect is a blind spot, and it is exactly the one that made this
report necessary: if that index HAD frozen after the hedge filled, today's
code would write nothing, and the log would look *identical* to a perfectly
healthy feed.** Reproduced offline: worlds W2 and W3 below produce the same
records, field for field, one with a frozen index and one with a healthy one.

**Two corrections to the task brief, both factual:**

| brief said | the log says |
|---|---|
| `index_stale` refusals "age_s 2.044 on three tickers at 02:15" | **01:14:48–49Z** (9:14 PM ET), **nine** tickers, ages 2.022–2.046 s, on the 21:15Z close |
| "the BOOK was flowing and the INDEX was not" | the index's own witness stopped being written at tau 9; nothing in the log says the index stopped |

At 01:14:48–49Z **we held nothing** (no `hedge_quote` in that second or the
four around it), so even those nine stale looks could not have produced a
`hedge_blind`.

---

## 1. The mechanism, line by line

### 1a. `index_age()` is PER INDEX. One frozen feed does not hide behind eleven healthy ones.

- **1132–1139** `index_age(idx, iid)` → `idx.spot(iid)[2]`, and any exception
  returns `None`, which 11023 treats as not fresh.
- **2374–2381** `IndexWS.spot(iid)`:
  ```python
  d = self.ticks.get(iid)          # this index's own dict
  s = max(d)
  return s, d[s], time.time() - s  # age from THIS index's newest print
  ```
  The age is measured from the newest print **of that index_id**, using the
  print's own exchange second. So a single frozen feed is detectable, and it
  is detectable even if Kalshi re-sends the same second for ever (the second
  does not advance, so the age keeps rising). **This is not the cause.**
- **2311 / 2353** `last_rx[iid]` is a second, per-index witness (local receive
  ms). It is written and **never read** anywhere in the file.
- What IS socket-wide is **recovery**, not detection: **2650**
  `raw = await asyncio.wait_for(ws.recv(), timeout=30)`. A frame from any of
  the twelve indices resets that clock, so one frozen index behind eleven live
  ones never forces a reconnect. K3's own comment (11008–11010) says this.

### 1b. The hedge pass does NOT reach the K3 check once the position is covered

```
10947   for _hid, (_hcs, _hwant, _hcost, _hn_orig, _htk) in list(open_pos.items()):
10966       _hn = hedge_remain.get(_hid, _hn_orig)
10967       if _hid in hedged or _hid.startswith("hedge-"):
10968           continue                       <-- EXITS HERE
...
11021       _hage = index_age(idx, _hiid)      <-- K3, never reached
11023       if _hage is None or _hage > MAX_INDEX_AGE_S:
11028           _hmkt = market_belief(_hbk3, _hwant)
11029           _hquiet("index_stale", ...)    <-- the hedge_blind record
...
11066       last_belief[_htk] = float(_hmodel) <-- what hedge_quote reads
```

The 2-lot went into `hedged` at **11343** on its tau-10 fill; the 11-lot on
its tau-9 fill. From tau 8 down both positions exit at 10968 — before the
index is looked at and before `last_belief` is written. `hedge_quote`
(**11447–11466**, `rec(...)` at **11461**) then reports
`belief=last_belief.get(_qtk)`, a value nobody is updating, for nine seconds.

**Is skipping right?** For the **action**, yes, and it is load-bearing —
see X2 in §2. For the **record**, no: it is the only per-second index witness
a held market has, and it is switched off exactly when a position is at risk
but no longer being watched.

### 1c. Why a frozen index gives a *byte-identical* belief, and why that is ambiguous

**2567–2628** `partial()` ends the locked window at the newest print actually
held (**2610** `hi = have[-1]`) and returns `(sum, N_AVG - want)`. `now_s`
only caps `hi` upward. So the belief is a function of **the prints held**, not
of the clock: with the feed frozen at second F the same `(locked, r)` comes
back every second and `fair()` returns the same float to the bit.

That signature is real — but it is only readable while `last_belief` is being
written. Once it is not, "same number" means nothing at all.

### 1d. Nothing else was watching DOGE either

The entry path's own index gate (**11851**, `_gate("index_stale", ...)`) sits
**below** `max_per_market` (**11777**). After the second fill at tau 11 DOGE
was refused at 11777 and never reached 11851 again. And `_gate` records once
per (close, ticker, gate) — the `close_summary` for close `1790131500` lists
gates `no_offer, edge_floor, price_ceiling, confidence, depth_floor,
max_per_market` and **no `index_stale` at all**, so the eleven other coins'
indices were fresh through the whole close. None of them can witness
`DOGEUSD_RTI`.

**So whether the bot's own `DOGEUSD_RTI` socket delivered seconds
…491 to …499 is NOT RECORDED ANYWHERE.** The last thing known is that the
print for …490 was in hand by 02:44:51.014Z. One weak bound: at 02:59:15Z the
next DOGE market was refused by `edge_floor` and `depth_floor`, both of which
sit below the index gate, so any freeze had recovered inside 14 minutes.

---

## 2. Reproduction — offline, pinrun's own functions, no socket and no key

`scratchpad/doge2245/D_frozen/harness.py` (+ `harness_out.txt`). It extends
the K3 harness (`verify/K3-frozen-index-code.md`) with the three paths that
harness did not have: the `hedged` skip (10967), the K3 block (11021–11036)
and `hedge_quote` (11447–11466). It imports pinrun's `IndexWS`, `fair`,
`widen_factor`, `index_age`, `market_belief`, `hedge_should_fire`,
`hedge_want`, `var_factor`; `kauth` is stubbed before the import. Live flags
from this run's `start` record (`hedge_belief 0.25`, `hedge_panic 0.40`,
`hedge_prop false`, `hedge_jump null`, `jump_widen false`,
`sigma_stress 1.0`, `max_index_age_s 2`, `max_book_age_ms 2000`).
**Peak working set 35 MB. 20 of 20 checks pass.**

In every world the BOOK is fresh every second — the book was flowing, which is
the case under investigation — and only the held market's index freezes; the
other index keeps arriving, so the 30 s socket timeout never fires.

| world | index | hedge | `hedge_blind` | first alarm | distinct beliefs, tau ≤ 9 |
|---|---|---|---|---|---|
| C1 control | fresh | never fills | 0 | tau 22 `belief` | — |
| C2 **null** | freezes at tau 28 | never fills, **calm book** | 1 `index_stale` | **none** | — |
| W1 | freezes at tau 28 | never fills | **1 `index_stale`** at tau 28 | tau 28 `market_index_stale` | 1 |
| **W2 (the DOGE shape)** | fresh to tau 10, **freezes at tau 9** | fills in full at tau 10 | **0** | tau 22 `belief` | **1** |
| **W3** | **fresh all through** | fills in full at tau 10 | **0** | tau 22 `belief` | **1** |
| F2 = W2 + fix | freezes at tau 9 | as W2 | 0 | as W2 | 1, **plus `index_age_s` 2.05→10.05 s** |
| F3 = W3 + fix | fresh | as W3 | 0 | as W3 | 1, **`index_age_s` 1.05 s flat** |
| X1 | freezes at tau 9 | as W2 | 1 at tau 9 | as W2 | 1 |
| X2 | freezes at tau 9 | as W2 | 1 at tau 9 | as W2 | 1 |

The load-bearing checks:

- **C1** a fresh feed through a collapse DOES alarm — the harness can see one.
- **C2 (the null that catches the sign)** a frozen index on a **calm** book is
  recorded but buys **nothing**: no alarm, no hedge. K3 does not invent.
- **W1** K3 works as shipped: an **unhedged** hold on a frozen index writes
  `hedge_blind index_stale`.
- **W2** the same freeze on an **already-hedged** hold writes **no record at
  all**, and `hedge_quote`'s belief is byte-identical for every remaining
  second.
- **W3** a **perfectly healthy** index produces the byte-identical belief too.
- **W2 vs W3** every field of today's log from tau 9 down is **identical**.
  *The symptom the brief reasoned from cannot distinguish a frozen index from
  a healthy one.* This is the defect.

### X2 — the landmine in the obvious fix

Moving the skip **below** the whole pass so the check is reached **re-buys the
hedge it already owns**: 22 sends instead of 13, filling 13 contracts nine
extra times. Cause: `hedge_remain.pop(_hid, None)` at **11344** means
`_hn = hedge_remain.get(_hid, _hn_orig)` at 10966 falls back to the **full
original size**, and with `HEDGE_PROP` off `hedge_want` (**1522–1540**)
returns all of it. **The skip at 10967 must stay where it is.** X1 (skip moved
to just below the K3 record) is safe and does write the record, but it runs
new work inside the hedge pass, which the freeze and this project's own
history argue against.

### W4 — the real DOGE index, replayed through pinrun's own `fair()`

Real `DOGEUSD_RTI` prints from the collector's tape (read-only; 60/60 in the
window; settle `0.10171337` vs strike `0.1017036`), fed one second at a time.
Because `partial()` keys on the newest print held, the table is keyed on that:

| newest print held | its value | pinrun's belief in NO (`repr`) | live `hedge_quote` showing it |
|---|---|---|---|
| …486 (tau 14) | 0.101698 | `0.992364742172938` | — |
| …487 (tau 13) | 0.101709 | `0.9869440639160239` | — |
| **…488 (tau 12)** | 0.101707 | **`0.9955949944046358`** | **tau 12 AND tau 11** |
| **…489 (tau 11)** | 0.101707 | **`0.9986709079754776`** | **tau 10** |
| **…490 (tau 10)** | **0.101805** | **`0.0514329175139725`** | **tau 9,8,7,6,5,4,3,2,1** |
| …491 (tau 9) | 0.101852 | `1.1184922847684575e-05` | — |
| …492 (tau 8) | 0.101823 | `0.00020980722214614111` | — |
| …493 … …499 | 0.10182 → 0.101816 | `1.3e-05`, `2.7e-12`, `0.0`, … | — |

Four things fall out, all reproduced to the bit:

1. The live tau-12 and tau-11 records are **one print read by two passes**
   (`index_age_s` 0.52 → 0.80 → 1.04 s, all under the 2 s bar). Identical
   beliefs, healthy feed.
2. A print **did** arrive between tau 11 and tau 10 (belief moved to
   `0.9986709079754776`).
3. The live tau-9 value is the print for second …490 — i.e. the pass at
   02:44:51.014Z ran **14 ms into its second**, before that second's print.
   Completely ordinary.
4. **Had `last_belief` kept being written, tau 8 would have read
   `1.12e-05`, tau 7 `2.10e-04`, then `1.3e-05`, `2.7e-12`, `0.0`…** The bot's
   own model, on the real prints, gives a *different* answer every one of those
   seconds. The repeated number is the log stopping, not the model.

---

## 3. The two counterfactuals the task asked for

### 3a. Already hedged: would the market-price fallback have changed anything? **No, and it could only have hurt.**

- The position was fully covered, so it exits at 10968 before the fallback
  exists. Even with the skip moved below the K3 record (X1) the record is
  written and **nothing** is sent.
- Had the fallback been allowed to reach the action path (X2) it would have
  bought 13 more YES contracts every second for nine seconds.
- And the fallback had nothing to add anyway: the belief used is
  `min(model, our-side ask)` (**11056–11058**), and the model was already
  `0.05143`, far below the 0.25 line. A minimum with any number ≤ 1 fires at
  the same instant. The alarm had already fired, at tau 10.

### 3b. Had we NOT been hedged, with the index frozen at tau 9: **the hedge still fires every second on belief alone, and the most it could have recovered is ~24c.**

The belief collapsed **before** any freeze could begin, so K3 was never the
binding constraint:

- `hedge_should_fire(0.05143)` is true against `HEDGE_BELIEF 0.25`, and
  `hedge_panic(0.05143)` is true against 0.40 — the alarm is already ringing at
  tau 10 and one try per second is allowed until `HEDGE_MAX_TRIES 30`.
- Insurance prices, from this run's own `hedge_quote` records: tau 9 98.7c
  (74.41 offered), tau 8 99.0c (450.71), tau 7 99.0c, tau 6–3 99.8c, tau 2
  99.2c, tau 1 99.7c. Net recovery per contract 1.21c, 0.93c, 0.93c, 0.18c,
  0.74c, 0.27c. On 13 contracts the best reachable from tau 9 onward is
  13 × 1.21c = **15.73c**; the bot actually got **24.13c** (2 @ 94.75c swept +
  11 @ 98.6c).
- So an unhedged-and-frozen version of this close costs at most about **24
  cents** of a $2.47 loss on 13 contracts, and nothing at all in decision
  terms.

**The case K3 exists for is the opposite order of events**: freeze **first**,
while the model is still confident, collapse **second**. Then the model sits at
0.9956 to the close and the book is the only witness. That is not what
happened here, and the fix below does not change it.

---

## 4. How big the blind window is, on our own fills

`scratchpad/doge2245/D_frozen/logscan.py` (+ `logscan_out.txt`), 128 live run
files, our own fills only:

| | |
|---|---|
| held markets (≥ 1 entry fill) | **787** |
| markets fully covered before their close | **17** |
| seconds each then spent unwatchable | min 4, **median 20**, p90 34, max 34 |
| total unwatchable held-seconds, lifetime | **358 s** |
| entry `index_stale` looks ever recorded | 111 |
| of those, falling inside a hold of the same ticker | **0** |
| `hedge_blind` records ever written | **0** |

So the window is real but narrow: 17 markets, about six minutes of held time
in total, and we have still never once seen a stale index while holding — the
same null K3's own verify reported (0 of 545 held closes).

A second, smaller hole in the same skip: `hedged.add(_hid)` is also set with
contracts **still uncovered** by `hedge_gave_up` (**11142**),
`hedge_refused hedge_attempt_cap` (**11175**) and `hedge_unknown`
(**11378**, pilot only). Those positions are exposed and never looked at
again, including by K3. Lifetime counts across all 128 runs:
`hedge_gave_up` **2**, `hedge_refused` **0**, `hedge_unknown` **0** — and
`hedge_panic` bypasses both caps, so the worst beliefs are already exempt.
Named, not fixed.

---

## 5. The smallest correct fix

**Logging only. It adds no branch, no gate and no order. It cannot block,
delay or complicate a hedge: it lives in the `hedge_quote` block, which is
already below the hedge pass, already once per held market per second, and
already inside its own `try/except` (**11447** / **11465**).**

Three edits, all in `research/pinrun.py`:

1. Beside `last_belief = {}` (**10323**), add
   `last_belief_t = {}   # the second last_belief was last WRITTEN`.
2. Beside each `last_belief[_htk] = float(_hmodel)` (**11066** and **11103**),
   add `last_belief_t[_htk] = now_s`.
3. In the `hedge_quote` loop (**11452–11463**), carry the position id and add
   two fields:

```python
            _hq_held.setdefault(_qtk, (_qcs, _qwant, _qid))   # 11451: + _qid
...
        for _qtk, (_qcs, _qwant, _qid) in _hq_held.items():   # 11452
            ...
                _qm = hedge_meta.get(_qid)
                _qiid = _qm[2] if _qm else None
                _qage = None if _qiid is None else index_age(idx, _qiid)
                rec("hedge_quote", ticker=_qtk, side=_qopp,
                    ask=_qb.get(f"{_qopp}_ask"),
                    size=_qb.get(f"{_qopp}_ask_size"),
                    tau=_qcs - now_s, belief=last_belief.get(_qtk),
                    iid=_qiid,
                    index_age_s=(None if _qage is None else round(_qage, 2)),
                    belief_age_s=(None if last_belief_t.get(_qtk) is None
                                  else now_s - last_belief_t[_qtk]))
```

**What it buys.** Every second a position is held — hedged or not, watched or
not — the log now says how old that market's own index print is and how old
the belief printed next to it is. The nine seconds this whole report is about
would have been one glance. It also covers the `_hquiet` dedupe's own blind
spot: `_hq71` (**10312**) records `index_stale` **once per position per run**,
so even in the unhedged case there is no duration and no recovery in the log.

**Why not the alternatives.**

| candidate | verdict |
|---|---|
| move the `hedged` skip below the whole pass | **X2: re-buys the full hedge every second.** Never. |
| move it to just below the K3 record (X1) | correct, and it writes the record — but it runs `book.best`, `market_belief` and a record inside the hedge pass for a position with nothing left to do. Strictly more risk than the same information logged below it. |
| a per-index watchdog on `last_rx` that resubscribes after N s | the only real fix for **recovery** (2650 is socket-wide) — but it touches the socket, it is not a bug or logging fix, and it has **0 observed events in 787 held markets** to validate against. Named; not proposed under the freeze. |
| lower `MAX_INDEX_AGE_S` | already refuted in `B_verify.md` §8: the missing print was identical in value, so a fresher feed makes the decision *more* confident. |

**Self-test, four required worlds — all four are implemented and passing in the
harness, and the third is the one that fails when the fix is reverted:**

- **A** frozen index, held **and hedged** → `hedge_quote` reports
  `index_age_s` above the 2 s bar (F2: 2.05 → 10.05 s).
- **B (null)** healthy index, same hold → `index_age_s` never above the bar
  (F3: 1.05 s flat), so a fresh feed is never reported as stale.
- **C (the revert catcher)** A and B must **not** produce the same records:
  `sig(F2) != sig(F3)` passes with the fix, and `sig(W2) == sig(W3)` — today's
  code, field for field — is exactly what it must not be allowed to be again.
- **D (no behaviour change)** every pre-existing field, every `hedge_alarm`,
  every `hedge` send and every refusal is **identical** with and without the
  fix, in both the frozen and the healthy world (F2 ≡ W2, F3 ≡ W3 on the old
  fields; hedge sends identical in second and size).

Conventions this must respect when it ships: the self-test asserts the
`_DEFAULT_*` constants, not running globals (pinrun self-tests at STARTUP with
the live flags applied); any source-text search must not match its own copy
(anchor after an offset, or use `rindex`); the suite must pass plain **and**
under the live argv (`--live --size 20 … --early-frac 0.333 … --loss-cap 200`).

---

## 6. Could not measure

- **Whether the bot's own `DOGEUSD_RTI` socket delivered seconds …491–…499.**
  It is recorded nowhere, for the three independent reasons in §1d. The last
  fact available is that the print for …490 was in hand by 02:44:51.014Z, and
  that DOGE cleared the index gate again by 02:59:15Z. The collector's tape had
  all 60 prints, but that is a different socket.
- **Whether a frozen index has ever cost us money.** 0 stale looks inside 787
  held markets; the 358 unwatchable seconds carry no record either way. This
  is a tail-risk and a diagnosis defect, not a measured bleed.
- **Whether the fix's `index_age_s` would fire on real live data.** It has
  never had the chance; the only validation available is the self-test plus a
  paper arm with a forced feed freeze.

## Housekeeping

Read-only against `C:\kals-repo` and `C:\kals`; nothing written outside this
file and the scratchpad; no process started, stopped or signalled; no order,
no network. Worktree `wf_a51a5354-b5e-1`, `research/pinrun.py` untouched
(`git status` clean on it, hash identical to the live file).
`kalshi_collector.py` and `crypto_feeds.py` both **alive** —
`kalshi_data/cfbenchmarks_value/20260923T04.jsonl.gz` and
`feed_data/coinbase/20260923T04.jsonl.gz` were both being written at
**04:44:39Z** against a wall clock of 04:44:39Z. Free RAM **3.07 GB**, free
disk **24.06 GB** (guard 6 GB). Harness peak working set **35 MB**; largest
object held was 1,979 floats.

Cuts / looks: 3 data cuts (held-and-hedged seconds; `index_stale` looks
overlapping a hold; give-up/cap/unknown counts). No significance claim is
made; the one rate quoted (0 of 787) is a null.
