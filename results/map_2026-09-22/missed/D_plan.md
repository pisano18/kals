# D -- the plan: what to chase, in what order, and the bar that judges each

**Nothing here is live and nothing here is proposed for live.** The FREEZE
(`results/FREEZE_2026-09-22.md`) allows paper arms, logging, bug fixes and
safety fixes. Every item below is one of those. Any PASS produces a
*proposal* for the operator after the freeze, with a live bar written before
the live number is read (CLAUDE.md amendment 2026-09-10 §4).

Inputs: the three investigator reports (`A_supply-gap.md`, `B_lost-races.md`,
`C_gate-winners.md`) and their verifiers. Only candidates a verifier marked
**survives** are ranked. My own measurements in this file come from the live
logs (`results/pinrun-live-*.jsonl`) and from `research/pinrun.py` source.

Resources at write time: 1.90 GB free RAM, 26.5 GB free disk, both recorders
alive (pids 105304, 105352). 26 paper arms are running at 82 MB mean RSS
(2.12 GB total).

---

## 0. The price rule that sizes everything below -- use this, not A2's

A's "chase only <=95c and it is risk-neutral even at the bad end" rests on a
loss rate its verifier could not reproduce. **Do not quote 2.29% anywhere,
including into B5.** From Kalshi's own settlement rows:

| population (our own fills) | closes | losing | rate | margin |
|---|---|---|---|---|
| <=30 s, paid 90-98c | 395 | 13 | 3.29% [1.76, 5.56] | +2.11c/ctr |
| <=30 s, paid 90-95c | 107 | 5 | 4.67% [1.53, 10.57] | **+5.45c/ctr** (5,209 ctr, 13 of 14 days positive) |
| <=30 s, paid 96-98c | 240 | 7 | 2.92% [1.18, 5.92] | +0.80c/ctr |

Break-even is 4.67% at 95c and 3.73% at 96c. **The 90-95c loss rate sits ON
its break-even**; the interval does not clear it. What survives is the
realised margin, which already contains the losses and the hedges. So the
rule is: *chase cheap because 90-95c has earned +5.45c a contract over 107
closes*, and price the 96-98c part at its own +0.80c rather than assuming it
away. Every dollar figure below uses these margins.

---

## 1. Ranking

"$/day captured" = at our own realised margins, over the window the
investigator measured, with no added risk unless the row says otherwise.
**R1 and R3 draw on the SAME pool of contracts -- do not add them.** The
combined pool is about $3-5/day.

| # | candidate | $/day | risk added | needs | freeze |
|---|---|---|---|---|---|
| R1 | count a per-market attempt only when an ORDER IS SENT | **$2-3** (range $0.7-4.9) | a population; verdicts disagree | new flag + paper arm | arm only |
| R2 | take the 11-GET universe refresh out of the loop's critical time | **$1.2-1.4** + unpriced hedge lateness | **none** -- buys nothing new | logging first, and the logging IS the test | logging is freeze-legal now |
| R3 | `staged_none` tests the ladder reach, not the touch | overlaps R1; marginal share unquantified | contested (survives / weakened) | new flag + paper arm + a repricing scorer | arm only |
| R4 | log the silent base-budget skip | **$0 direct**; makes ~$3/day visible and feeds B5 | none -- a record, not a decision | one logging line | freeze-legal now |
| R5 | do NOT build speed to win races | $0; avoids giving back $164 | none | nothing | n/a |

**Order of work is not the ranking.** Do R4 and R2's logging first (both are
freeze-legal, both are prerequisites for sizing anything), then R1's arm,
then R3's arm.

---

## 2. R4 -- log the silent base-budget skip (do this first; it is $0 and it
unblocks the rest)

### The defect, confirmed three ways

`research/pinrun.py` 11316-11323, after every gate has passed:

```python
state["signals"] += 1
if CLOSE_BUDGET:
    _pvb = fired.get(close_s)
    _left = close_budget() - (_pvb.get("contracts", 0.0) if _pvb else 0.0)
    if _left <= 0:
        continue                      # <-- no record of any kind
```

`close_budget()` is the BASE budget (`MAX_PER_CLOSE * SIZE` = 2 bets). The
gate that already refused on budget, at 10852, uses `close_budget_for(prev,
tk, tau=tau)` -- base **plus one bet** for a new coin or inside 15 s -- and
logs. `worst_close_cost()` and the bank brake both price three bets. So the
third bet is granted, priced, sized for, and then dropped with no refusal
record and no `close_summary` count.

1. Source walk: this is the only `continue` between the signals counter and
   the order send that does not write a `_gate()` record.
2. The bot's own counter: run `20260920T023207Z` ended with
   `state.signals = 102` against **5** `signal` records and 5 `order`
   records. Every other run carrying an `end` record has them equal exactly
   (1/1, 7/7, 33/33, 4/4, 23/23, 0/0).
3. **The contamination check the verifier did not run, and it holds.** The
   five gates that sit AFTER the counter (`early_cheap`, `early_dear`,
   `early_wide`, `staged_none`, `price_band`) dedupe their refusal records
   per (close, market, gate), so they could in principle have eaten the 97
   looks silently. They did not: that run's `close_summary.gates` totals are
   undeduped look counts, and they show **0** looks at any of those five
   gates. All 97 exited at line 11322.

### The change (logging only -- FREEZE §1 "may change: logging")

One call immediately before the `continue`:

```
_gate("close_budget_base", close_s, tk, want=want, price=round(price, 4),
      take_n=take_n, base=close_budget(), spent=<the same _pvb contracts>,
      tau=tau)
```

`_gate` already appends `budget_left` (computed from `close_budget_for`) and
`size_now`, already dedupes per (close, market, gate) -- so it adds **one
record per market per close, not 20 a second** -- and already increments the
undeduped `close_summary.gates` counter.

### Bar (a verification bar, not a decision)

- **Window:** opens when the line is deployed.
- **PASS:** on the first run after the change that writes an `end` record,
  `end.state.signals` equals `signal` records plus the undeduped
  `close_summary.gates` counts of `close_budget_base`, `early_cheap`,
  `early_dear`, `early_wide`, `staged_none` and `price_band` over that run.
- **FAIL:** the identity still does not close -- then there is a second
  silent exit and it must be found before any budget number is trusted.
- Today that identity fails by 97 on one run, so the test has been shown
  capable of failing.

### What it feeds

B5 cannot currently see this refusal at all. Note the signature the new
record gives B5 for free: `budget_left` on a `close_budget_base` record is
computed from `close_budget_for`, so it will be **> 0** while the base is
spent. That is what distinguishes "the close's budget really ran out" from
"the third bet was dropped". C's F5 finding that no refusal since v-safety1
has `budget_left <= 0` is fully consistent with this skip happening and being
invisible -- it is not evidence that the budget never bound.

### Blocks

Nothing. It is a record, not a decision; it cannot touch a hedge. Cost is one
set lookup per gate-passing look inside the 20 Hz loop, and `t_ms_decide`
(live since v-safety1) will show it if it ever matters.

---

## 3. R2 -- the universe refresh off the loop's critical time ($1.2-1.4/day,
the only candidate that adds no risk at all)

### Mechanism (source-confirmed)

`research/pinrun.py` 10704: `if now - uni_at > 20:` then a synchronous loop
of one `GET /markets` per series (11 series), each on a fresh TCP+TLS
connection, **with no condition on time to close**. Our own authenticated
POSTs to the same host on a fresh connection run a median 94 ms (n = 980
orders), so 11 back to back is ~1.03 s -- bracketing B's measured 837-998 ms.
That is ~4.3% of every close's last 30 s in which nothing is bought **and no
hedge fires**, because the hedge pass is in the same thread.

### Logging first, and the logging IS the test (FREEZE-legal)

- `rec("universe", ms=<refresh duration>, n=<markets kept>)` on each refresh.
- per close, the **maximum loop-pass gap** and the tau at which it happened,
  in `close_summary` (or a `loop` record whenever a pass exceeds 200 ms).

B's non-confirmation from `hedge_quote` gaps is arithmetically incapable of
seeing this: a blackout under 1.000 s can never cover a whole second. So
there is currently no instrument.

### Pre-registered bar, written now

- **Window:** opens when the logging deploys. **Sample:** the first 100
  watched closes.
- **PASS (the stall is real and worth fixing):** median `universe.ms`
  >= 500 ms **AND** >= 20 of the 100 closes have a loop-pass gap > 500 ms at
  tau <= 45.
- **FAIL (drop the idea):** fewer than 5 of 100 closes show any pass gap
  > 200 ms at tau <= 45.
- Between the two: report the distribution and re-register at 300 closes.
- **Statistic is descriptive** -- a duration, not a test -- so it carries no
  multiple-looks cost.

### Only on PASS, the change itself (after the freeze, operator's call)

Defer the refresh while any watched market has tau < 60 s. Its bar: the same
two numbers, plus contracts filled per close at tau <= 30 on shared closes
against live.

- **Blocks: nothing.** Checked: the refresh already discards any market
  closing more than 900 s out, so while tau < 60 for one close the next
  close's markets (960 s away) are excluded anyway -- deferring cannot delay
  discovery, provided the skip ends at the close, which it does.
- **Hedge:** this is the one candidate that can only make the hedge *faster*.
  Hard condition on any implementation: **no new condition may be added to
  the hedge pass**, and the background-thread form (the riskier one) must
  build the universe locally and swap it atomically -- `if fresh:` replaces
  `seen_markets` wholesale, so a partially built universe would drop a coin
  for 21 s.

---

## 4. R1 -- count a per-market attempt only when an ORDER IS SENT
($2-3/day; the biggest single item)

### Mechanism (source-confirmed)

Lines 11358-11359 increment both counters at the SIGNAL point:

```python
attempts[close_s]           = attempts.get(close_s, 0) + 1
attempts_tk[(close_s, tk)]  = attempts_tk.get((close_s, tk), 0) + 1
```

Five gates that refuse **without sending** sit after them: `early_cheap`
(11421), `early_dear` (11447), `early_wide` (11452), `staged_none` (11459),
`price_band` (11470). At ~20 looks a second, three refused passes (~150 ms)
reach `MAX_ATTEMPTS_PER_MARKET = 3` and the read at 10916 then locks the
market out **for the rest of the close, including the last 30 s**. The
constant's own comment says it counts "orders SENT".

### My own event-rate measurement (the investigators' rates are stale)

Lockouts (`market_attempts` refusals, distinct close+market) and the burner
gates, per UTC day, from all live logs:

| day | closes | lockouts | markets hitting a burner gate | of which `staged_none` |
|---|---|---|---|---|
| 09-17 | 88 | 1 | 1 | 1 |
| 09-18 | 95 | 9 | 22 | 6 |
| 09-19 | 95 | 9 | 14 | 9 |
| 09-20 | 93 | **13** | 12 | 11 |
| 09-21 | 96 | **1** | 2 | 1 |
| 09-22 (to 14:35Z) | 71 | **1** | 2 | 1 |

42 lockouts lifetime, **32 of 42 preceded by a burner refusal in the same
market and close** (reproduces the investigators' mechanism exactly). Every
record has `tried = 3`.

**This is the number that changes the plan: the rate has fallen from 13/day
to 1/day.** A's "about five times a day, so a week is the minimum useful
arm" was computed over a window dominated by 09-20. At the last two days'
rate, 30 events is a month. So the sample below is **event-counted, never
day-counted**, and the arm reports COLLECTING until it has its events.

### Code change needed -- the flag does NOT exist

Checked `research/pinrun.py`'s argparse (lines 12045-12414): there is no
attempts flag of any kind. **Needed, described not written:**

- `--attempts-on-send` (`action="store_true"`, default off, so live's
  behaviour on any restart is byte-identical).
- It moves **only** `attempts_tk[(close_s, tk)] += 1` (line 11359) to
  immediately before the order send / paper book site. **`attempts[close_s]`
  (line 11358) does NOT move** -- the verifier's amendment and it is right:
  that per-close counter is checked against `MAX_ATTEMPTS_PER_CLOSE = 24`,
  and it is deliberately incremented outside the entry path -- by the hedge
  at 10418 under the key `_hcs` ("a hedge order still spends the ENTRY
  budget") and by the plant at 10999. Moving it would loosen the runaway rail
  for nothing, because every lockout in this window is per-market.
- **Self-test is the deliverable:** (a) three burner-gate refusals in one
  market must leave `attempts_tk` at 0; (b) three real sends must still reach
  3 and refuse the fourth; (c) the existing literal checks at 3734 and 3737
  must still find their strings inside `trade_loop`; (d) the send/attempt
  pairing check at 3745-3754 -- "for each `pintake.take(`, the nearest
  preceding `attempts[...]` increment must be an increment" -- must still
  pass, which it will only if the moved line lands **before** the send, not
  after it.
- `MAX_ATTEMPTS_PER_MARKET <= 3` (self-test 3723) is untouched.

### The arm, as a `sync_arms.ps1` entry

Add to the `$arms` list in section 2 of `sync_arms.ps1`:

```powershell
  @{ n="arm-attempt-send";  drop=@();  add=@("--attempts-on-send") },
```

`drop` is empty: it overrides no live flag. Everything else is inherited from
the live command line, which is what `sync_arms.ps1` exists for.

**The code_sha problem, stated up front.** `_source_fingerprint()` is a
sha256 of the whole of `pinrun.py`, so adding the flag changes `code_sha`.
FREEZE B6's shared-close rule requires arm and live to carry the **same**
`code_sha`, so this arm is outside B6 until live next restarts on the same
file. I am not proposing that restart. Instead the bar below defines its own
shared-close rule and asserts the code difference is exactly this flag.

### Pre-registered bar (written now, before any arm data exists)

- **Window:** opens the moment the arm starts, after a `sync_arms.ps1`
  re-sync. Every arm number before 2026-09-20 is void and a re-sync restarts
  the window.
- **Shared close:** both bots logged a `close_summary` for it; the close is
  >= 60 s after the arm's start; the arm's `start` record shows
  `attempts_on_send` true; and the only difference between the arm's source
  and live's is this flag plus R4's logging line.
- **Admitted event:** the arm sent an order at tau <= 45 in a (close, market)
  for which the LIVE bot logged a `market_attempts` refusal in the same
  close and market.
- **Sample:** the first **30 admitted events**. COLLECTING before that. At
  the last two days' rate that is weeks; at the six-day mean it is ~6 days.

**Three conditions, all required for PASS:**

1. **The flag fired, in the same markets.** >= 30 admitted events, each
   traceable to a live `market_attempts` refusal. Report markets-both /
   arm-only / live-only (`h2h`, never `diff`); arm-only markets must be the
   admitted ones. Zero admitted events = the arm measured nothing -- the A51
   failure, and it is reported as such, not as a result.
2. **Safety, and it can stop the arm at ANY n:** admitted closes that lost
   <= **3**. A 4th losing admitted close before 30 events ends the arm as
   FAILED on safety and no proposal follows. Under our own baseline (3.29%,
   13 of 395 closes) that stop fires by accident **1.8%** of the time. Its
   power is the weak half: against the lost-races verifier's admitted-class
   rate of 9.1% it fires only **29%** of the time at n = 30, so a clean
   safety result is *not* proof of safety, and that is stated in the report.
3. **Dollars, repriced -- the arm's own paper P&L must NOT be used.** The
   paper entry path books `_book_slot(price, take_n)` at the **touch price**
   and fills **100%** (line 11757-11762; only the hedge uses `hedge_vwap`),
   while our live fill rate is 70% and a sweep pays the rung average. So
   score each admitted fill from the market's settled outcome:
   `contracts x 0.70 x (win: (1 - ladder-average price) - fee | loss:
   -ladder-average price)`, with the arm's own `hedge` records applied. PASS
   needs that sum > $0, resampled P(sum > 0) >= **0.90** over admitted
   closes, and **no single close > 50%** of the gain.

- **FAIL** at 30 events otherwise. FAIL means "not shown", never "no effect".
- **This dollar half is a HYPOTHESIS** (the arm's fills are paper and the
  outcomes are the market's, not ours). The risk evidence that is *not* a
  hypothesis is our own fills, and the three investigators disagree about
  which population is the right analogue -- which is exactly why condition 2
  scores the admitted class separately:

  | own-fill population | closes | losing | margin | source |
  |---|---|---|---|---|
  | swept a thin touch (`swept` flag) | 127 | 4 (3.1%) | +2.30c | A verifier |
  | signal touch < 5 contracts | 40 | 1 (2.5%) | +3.33c | A verifier |
  | pre-early-leg, model sure, tape offered < 90c | 20 | 0 | +6.81c | C verifier |
  | **burner refusal that close, then filled at tau<=30** | **11** | **1 (9.1%)** | **-8.80c naked, -$42.46 net** | B verifier |
  | ordinary tau <= 30, no burner refusal | 91-395 | 1-13 (1.1-3.3%) | +1.88 to +2.87c | B / A verifiers |

  The negative row is 11 closes and is driven by one market,
  `KXBNB15M-26SEP191230-30` at -$61.75 net. One event on 11 closes settles
  nothing either way, and Fisher gives p = 0.21.

- **MDE, stated before the estimate:** at 30 events and ~19 filled contracts
  an event, the dollar half separates "+2.3c/contract" from "-3.5c/contract"
  with about **60%** power at one-sided 5% (sd ~$17.5 over the sample, driven
  by whether one more close loses). 100 events would be needed for a clean
  answer on either half.

### What it blocks, and the hedge

- It **removes** a refusal; it blocks nothing new. A released market must
  still pass every gate, and `MAX_ATTEMPTS_PER_MARKET = 3` still caps real
  orders.
- **It cannot block a hedge.** `attempts_tk` is read in exactly one place --
  line 10916, inside the entry loop. The hedge path was cut free of the entry
  attempts counter by A71 (2026-09-19); it uses `MAX_HEDGE_ATTEMPTS_PER_CLOSE`
  and only *increments* `attempts[close_s]`, which this change does not move.
- One honest side effect, from the B verifier: 17 of the 34 recent lockouts
  were burned by `early_cheap` or `early_wide`, so the bug has been silently
  *extending* A49 ("a cheap ask is the market disagreeing with us") and A50
  ("too good to be true") into the <=30 s window. Fixing it re-admits that
  population 15 s later. That is a real behaviour change and it is why the
  arm exists.

### Freeze

Paper arm only. The flag defaults off, so live is unchanged whether or not it
restarts. Nothing in `restart_bot.ps1` changes, so `versioncheck.py` stays
green and no `config_keys` move, so no freeze bar restarts.

---

## 5. R3 -- `staged_none` should test the ladder reach, not the touch

### Mechanism (source-confirmed)

At ~11113, `take_n = min(float(SIZE), float(size))` -- the **touch**. At
~11122 `depth_floor` computes `_reach`, how many we could actually sweep,
and its own comment says "take_n is deliberately NOT reassigned here". Then
at 11459, `if take_n < MIN_LEVEL:` refuses with `staged_none` -- against the
touch, on a ladder `depth_floor` has already approved. With
`MIN_FILL_FRAC = 0` and `MIN_LEVEL = 1`, the two gates test the same
threshold (1.0) against different things. 26 of 28 lifetime `staged_none`
records have `held = 0` and a sub-contract touch (0.5 x9, 0.02 x6, 0.1 x4).

It is the burner behind **11 of the 12** lockouts on 09-20 and 28 of 42
lifetime, so on its own it stops the refusal happening at all, where R1 only
stops it locking the market out for the rest of the close.

### Money: overlapping, not additive

Same pool as R1 (A verifier: 342 contracts / 137 a day / +$2.88-4.90 a day
over 236 watched closes; C verifier's separate cut is smaller). Its marginal
value **on top of** R1 is the looks it stops refusing that would not have
locked anything, and nobody has sized that. Report it as "inside R1's pool",
never as a second $3/day.

### Code change needed -- the flag does NOT exist

- `--staged-reach` (`action="store_true"`, default off). It makes the
  `staged_none` test read the reach `depth_floor` already computed
  (`_reach`), staged through the same leg cap, instead of the touch-sized
  `take_n`. `MIN_LEVEL` still applies, to the reach; `depth_floor` still
  refuses a genuinely shallow book.
- Self-test: a dust touch over a fat ladder must **not** refuse under the
  flag and must still refuse without it; a dust touch over a dust ladder must
  refuse either way.

### The arm, as a `sync_arms.ps1` entry

```powershell
  @{ n="arm-staged-reach";  drop=@();  add=@("--staged-reach") },
```

Keep it a **separate arm** from `arm-attempt-send`: both verifiers asked for
the two halves to be separable, and a combined arm cannot attribute either.

### Pre-registered bar

Same shape as R1, with two differences that matter:

- **Admitted event:** the arm sent an order where live logged `staged_none`
  in the same close and market. **Sample: the first 30 admitted events**
  (`staged_none` ran 1-11/day; 1/day for the last two days, so expect weeks).
- **The money statistic MUST come from a repricing scorer, not the arm.**
  This is the load-bearing point: the paper path books the **touch** price
  for every contract and always fills, and this change exists precisely to
  buy contracts that are *not* at the touch. Scored on paper dollars the arm
  reads positive by construction. Price each admitted fill from the arm's own
  `signal.ladder` and `sweep_depth` records at the **rung average**, with the
  0.70 fill haircut, fees, and the arm's own `hedge` records -- the same
  instrument class B1 uses via `earlyhindsight.freeze_rows()`.
- **PASS:** >= 30 admitted events, each traceable to a live `staged_none`
  refusal; admitted losing closes <= 3 (any-n safety stop at 4, false-stop
  rate 1.8% under our 3.29% baseline); repriced sum > $0 with resampled
  P >= 0.90 and no single close > 50%; **and** the early-leg share reported
  separately, because our own 31-45 s fills earn +0.53c a contract against
  +2.19c inside 30 s -- a gain that is all early-leg is worth a fifth as much
  and should be capped to the full leg instead.
- **FAIL** otherwise at 30 events.

### The split verdict, said once and plainly

A's verifier calls this the strongest evidence in the whole map (swept fills:
127 closes, 4 losing, +2.30c against not-swept 122 closes, 4 losing, +1.81c).
C's verifier calls it weakened on a narrower population (11 closes, 1 losing,
about -$35.5 net), and that one loss is `KXBNB15M-26SEP191230-30`, 84.5
contracts at 97.3c, -$61.75. The two are measuring different things and 11
closes cannot separate them -- hence the arm.

**Useful cross-link:** that BNB market is also in FREEZE bar B3's population
(a fill landing >= 2c below the ask we saw). If B3 passes, R3's worst
observed case is the exact failure B3 would insure. Sequence R3 behind B3's
verdict and its downside shrinks; that is a scheduling note, not a bar.

### Blocks, and the hedge

Nothing is blocked -- it stops refusing a book we can already sweep. It lives
in the entry loop and cannot touch a hedge. The risk it adds is real and
should be written down: it buys through a ladder when the visible touch is
dust, which is the book shape that produced the price-through fills (97.8c
ask seen, 53c executed).

---

## 6. R5 -- do NOT build speed (no work, no arm, no code)

Recorded so it is not re-opened. B's own optimistic case for a 43 ms
speed-up is +$17 over 14 days against a tape-priced -$96 central estimate
whose sign flips on one to three losing closes. Our own fills say the same
thing by a route the report only hypothesised: fills on levels < 0.25 s old
(230 orders, 196 closes) lose 10 closes (5.1%) at **-0.03c** a contract,
against +2.33c (0.25-1 s), +0.29c (1-10 s) and +2.78c (> 10 s). Being slow
also saved $163.98 on 28 collapse fills (27 closes, 7 lost).

If speed is ever revisited, the pre-registered screen is written now: it must
first be shown, on OUR OWN fills in the window being sped up, that levels
< 0.25 s old carry no per-contract penalty. The last 10 s is currently the
only window where they do not. And any keep-alive connection must reconcile a
send error by `client_order_id` -- never a blind resend.

---

## 7. Not ranked, and why

- **Make the third bet takeable** (`close_budget` -> `close_budget_for` at
  11319, with a 95c cap): verdict **weakened**. It cannot even be sized until
  R4's logging exists, bets inside one close are not independent (175 of 183
  multi-market closes finished all the same sign), and the own-fill support
  is 19 markets, 0 losing -- below the 30-close floor, so "no loss seen yet",
  not "safe". Revisit after R4 has produced 30 days of `close_budget_base`
  records.
- **C1 narrow** (burn the counter for `staged_none`/`price_band` only, keep
  `early_cheap`/`early_wide` burning it): weakened, and it is a strictly
  smaller version of R1 + R3. If R1's arm fails on safety, this is the
  fallback to arm next, not now.
- **Uptime / KalsBoot / a non-re-halting drawdown brake:** weakened -- 288 of
  the 344 missing minutes were an exchange-side outage the collector saw too,
  leaving ~$1.8/day. Worth doing, but it is infrastructure, not a missed
  deal, and a non-re-halting brake is a **safety rail being loosened**, which
  2026-09-19 (-$106.73, 3 of 4 losses caused by gates and brakes blocking a
  hedge) says to treat carefully. The measure to track daily is watched
  closes per ET day against 96 (09-20: 93, 09-21: 95), plus closes with
  `looks = 0` scored separately.
- **Everything the gate investigation refuted** -- loosening `edge_floor`,
  `price_ceiling`, `confidence`, `dump_guard`, `early_cheap`, `against_thin`
  or any capacity gate. Our own fills below the confidence line lose 2 of 35
  closes at -5.43c a contract. Do not re-open without new own-fill evidence.

---

## 8. Multiple looks

R1's and R3's bars are new discovery tests and they sit **outside** the
freeze family (B1 0.036 + 0.008, B2 0.009, B3 0.019 = 0.072 of a 0.10
budget), because a PASS here produces a proposal, not a change -- the same
status as B5. Registered separately: each arm's PASS requires a dollar
condition at resampled P >= 0.90, a single-close guard, and a safety count,
so its false-PASS rate under a true null is about 0.07; two arms sum to about
0.14 against a registered budget of 0.15 for this family. Each bar is
computed **once**, on its first 30 admitted events in time order; before that
it reports COLLECTING and its running numbers decide nothing.

## 9. Resources

Two new arms cost about 165 MB (82 MB mean RSS x 2) against 1.90 GB free.
That fits, but if free RAM goes under 1.0 GB, retire an arm that has already
answered (B6 names the arms whose flag has never changed a trade) rather than
adding. The collector outranks every arm.
