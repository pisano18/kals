# THE INFERRED-CONSTRAINT AUDIT

**Run 2026-09-06 ~11:30-12:10 UTC. Intended to be re-run periodically.**
Scope: `CLAUDE.md`, `HANDOFF.md`, `IDEAS.md` (incl. the graveyard), `PLAN.md`,
`RUNBOOK.md`, `BIASES.md`, plus the code that actually enforces them
(`pin.py`, `endgame.evaluate`, `go.py`, `kalshi_collector.py`).

A constraint counts as **inferred** if it is acted on as a rule but no operator
instruction requires it. Ranked by **how much money it may have cost**, not by
how interesting it is.

Two of the items were settled by measurement tonight rather than by argument,
and both are reported with their arithmetic. Everything else is flagged as
untested and priced.

---

## SCOREBOARD

**Ranked by money at stake. #1 and #2 are the largest *potential* costs and are
unmeasured. #3 is the largest *measured* cost — the number is in hand.
#4 is the one that decides whether any of it becomes real.**


| # | Constraint | Verdict | Money it may have cost | Cost to test |
|---|---|---|---|---|
| 1 | Only the 15-minute crypto series exist | **WRONG** | the depth ceiling that is pin's only binding limit | $0, index tape already on disk |
| 2 | One strike per window ⇒ ladder arb undefined here | **WRONG (scope error)**; no lock at 14s resolution, but the bound is **binding to 0.1c** by the close | it hid item 1; and a sub-cent-tolerance lock we cannot see | 57 samples done tonight, $0; the real test is 1 line in `CRYPTO_15M` |
| 3 | One trade per close | **WRONG when it sets size, and it also SELECTS** | 1.84x at tau<=20; **sign inversion** at tau<=60 (-$1.52/day vs +$61.68/day) | already done, free |
| 4 | read-only ⇒ never probe (operator's #1) | **WRONG as applied** | pin's #1 risk left unmeasured | < $100 at 1 contract |
| 5 | 12 correlated series = leverage, not diversification | **PARTLY — wrong for money** | 1.55x at an unchanged tail | free, already measured |
| 6 | A cell must clear its MDE to count | **WRONG** | endgame's +0.86c/contract shelved | free, already measured |
| 7 | The graveyard is current | **WRONG (stale)** | market-making reads as dead while it is alive | free, an edit |
| 8 | "consistently" = statistically significant (operator's #2) | **WRONG** | every-market variant graded down for a falling t | free |
| 9 | $50/day, 50 contracts, 96 closes/day | retired but **still load-bearing** | one FAIL verdict, several inflated tables | free |
| 10 | The tape is the only data source | **PARTLY WRONG** | 3 free read-only sources unused | $0 |
| 11 | flow.py costs 100 min ⇒ the book is off-limits | **rule right, behaviour wrong** | queue position idle for days | seconds (cache is warm) |
| 12 | 500 forward closes before anything is believed | **WRONG under the new framing** | ~14 days of not trading | free to drop |
| 13 | "Never place an order, **ever**" (repo wording) | **stricter than the operator** | it stops anyone ever ASKING | an edit |
| 14 | Hold to settlement | **CORRECT — measured tonight** | none: early exit is worse by 3–6c | done tonight |
| 15 | Kills that were capacity/absolute-dollar kills | **several do not survive the re-scope** | "best +7c at depth 0-1" filed as a kill | varies |

---

## THE MONEY, RESTATED IN THE OPERATOR'S UNITS

Nothing in this repo has ever been reported as return on capital. Measured
tonight from the cached `rows_tau60.pkl` + `depth_map.pkl` (script
`money.py` in the session work dir), pin at `tau<=20s`, floor 0.5c, size
`min(100, 0.25 x touch depth)`, **every market**, over the full 12.2-day
cached tape:

```
  +3.21 c per contract traded            ~1,650 contracts traded/day
  $53.07 per day
  PEAK CONCURRENT CAPITAL     $231       (median close $29, mean close $44)
  RETURN ON PEAK CAPITAL      22.9 % / day
  RETURN PER TURN             3.48 %     (mean hold 17.5 seconds)
  worst close  -$25.84        best close  +$43.36      max drawdown  -$25.84
```

**This is in-sample over the whole cached tape (warmup included). It is not the
published out-of-sample number and must not be quoted as one.**
`PREREG_pin.md` §3, on the OOS window at `tau<=60` every-market, gives
$101/day with a $51 max drawdown. Both agree on the shape.

**The single most important fact this reframing exposes:**

> pin's peak concurrent capital is **$231** against an account of **$1,000**.
> Max drawdown is **$26**, i.e. **2.6% of the account**. The strategy cannot
> use three quarters of the money available to it, and the binding constraint
> is **resting depth in the 15-minute books** — a constraint that most of the
> items below either create or preserve.

That inverts the priority order. **Finding more places to put the same trade
is worth more than improving the trade**, because the capital is idle and the
tail is bounded by the capital deployed.

---

# 1. "Kalshi's 15-minute crypto markets" is the universe

**As written.** `CLAUDE.md` line 7: *"Read-only quantitative research into
whether a tradeable edge exists in Kalshi's 15-minute crypto binary markets:
12 up/down series (`KXBTC15M` and siblings) plus 2 Coin Race
relative-performance series."* Every stage, loader and results file obeys it.
`kalshi_collector.py` line 177 subscribes 13 CF Benchmarks indices; `CRYPTO_15M`
lists 14 series.

**Where it came from.** Nowhere. It is the list the collector was pointed at on
2026-08-25 and it has never been revisited. `HANDOFF.md` describes how the
universe is set: *"the collector default now includes
KXCRYPTOLEAD15M/COMP15M; deploy = one file copy."* The universe is whatever
somebody typed into a list nine months' worth of reasoning ago.

**What it ruled out — from Kalshi's own catalogue (`series_crypto.json`, on
disk since 2026-08-27) plus 6 read-only REST calls tonight:**

```
  crypto series by cadence      custom 71   one_off 59   annual 51
                                HOURLY 25   monthly 24   DAILY 22
                                fifteen_min 14   weekly 8
```

Twenty-five hourly and twenty-two daily crypto series, **all settled by CF
Benchmarks, on the same indices the collector already records at 1 Hz.** The
hourly BTC directional ladder `KXBTCD` settles by exactly the rule pin
exploits — pulled live tonight:

> *"If the simple average of the sixty seconds of CF Benchmarks' Bitcoin
> Real-Time Index (BRTI) before 8 AM EDT is above 88799.99 at 8 AM EDT on
> Sep 6, 2026, then the market resolves to Yes."*

**pin's mechanism is a last-sixty-seconds mechanism.** The locked-prints
collapse depends only on how many of the 60 settlement prints are already on
disk, not on how long the contract has existed. So the mechanism transfers to
every series settling on a 60-second CF Benchmarks average **by construction**.
What does not transfer automatically is the profit — and that is what has never
been tested.

**And the reason it matters is depth, which is pin's only binding constraint.**
Measured live on the 12:00Z BTC close:

```
  KXBTCD-26SEP0608    188 strikes on ONE close, 102 of 188 carrying a bid
                      event volume 580,569 contracts, open interest 190,963
  near-money strikes  > 79,899.99   bid 0.90 (1,012)   ask 0.91 (877)    vol 266,074
                      > 79,999.99   bid 0.15 (183)     ask 0.16 (650)    vol 277,355
  vs KXBTC15M measured touch depth (HANDOFF, depth section):
                      p10 2   p25 15   MEDIAN 69   p75 193   p90 455
```

A quarter of a million contracts of volume on a *single* near-money hourly
strike, against a 15-minute book whose *median* touch is 69 contracts and where
a flat 50 fails to fill 42.3% of the time. **If pin's per-contract edge survives
on the hourly ladder at anything like the 15-minute rate, the capacity ceiling
that graded pin FAIL against $50/day is not there.**

**What it would cost to test. Zero new collection and zero new pulling code.**
The recorded `cfbenchmarks_value` tape (BRTI at 1/sec since 2026-08-25)
supplies the locked prints for **any** market settling on BRTI, whatever its
cadence — the index tape is series-agnostic and has never been used that way.
And `kalshi_fulltape.py` already takes the series as an argument
(`--series KXBTC15M KXETH15M ...`, line 8), pulling settled markets via
`/markets?status=settled` and paginating the full trade tape via
`/markets/trades`. So the pull is:

```
  python kalshi_fulltape.py --series KXBTCD KXETHD --markets 500 --out <newdir>
```

with **no new code**, and the scoring stage reuses `engine.var_factor`,
`settlewin.partial` and `endgame.outcome_of` unchanged.

**The honest limitation of that first test.** REST gives *prints*, not quotes,
so the first-pass question is *"did a trade print at a price the locked BRTI
prints already contradicted?"* — evidence the mispricing exists, not proof we
could have hit it, and it samples on trade arrivals, which is `BIASES.md`
pattern 2 (occupation-time). To get quotes, add `KXBTCD`/`KXETHD` to
`CRYPTO_15M` — one line and one file copy — though `PREREG_pin.md` §7.3 argues
against changing the collector mid-window.

**How much of pin's existing money the hourly ladder can duplicate directly.**
Measured on the cache: **245 of 992** distinct closes (**24.7%**) fall on the
top of an hour, where a `KXBTCD` ladder settles on the *same second of the same
average*. So a quarter of pin's current closes have a deeper alternative venue
available at that instant, and the hourly ladder carries 24 closes/day/coin of
its own on top of that — a surface that does not overlap the 15-minute grid at
all for the other three quarters.

**Judgement: WRONG.** The most expensive inferred constraint in the repo. It is
not that the 15-minute series were the wrong choice; it is that nobody asked
whether they were a choice.

---

# 2. "One strike per window, so ladder/basket arbitrage is undefined here"

**As written.** `CLAUDE.md` lines 256-259: *"`research/strikes.py`
independently found that the 15-minute crypto series carry **one strike per
window** (`strike(N+1) == settle(N)`), so ladder/basket arbitrage is
**undefined** for this product rather than merely unprofitable."* Reinforced by
`PLAN.md` line 66 on the Coin Race legs: *"Not an arb. Excluded from scope."*

**The inference.** "This series has one strike per window" is true and verified.
"Therefore there is no ladder on this settlement variable" does not follow. It
quietly changed the subject from *a series* to *a settlement variable*.

**What it ruled out.** At every top of the hour, three different Kalshi markets
settle on **the identical random variable** — the 60-second BRTI average ending
at :00:00:

| market | strikes | form |
|---|---|---|
| `KXBTC15M` (11:45→12:00) | 1, at `avg60(11:45)`, known at 11:45 | `avg60(12:00) >= K` |
| `KXBTCD-26SEP0608` | **188** | `avg60(12:00) > K_i` |
| `KXBTC-26SEP0608` | **188** | range bands on the same variable |

That yields hard, model-free, no-forecast relations:

```
  for hourly strikes  L < K_15M < H :
      P(X > H)  <=  P(X >= K_15M)  <=  P(X > L)

  LOCK A   if  ask(15M)      <  bid(hourly H)     buy 15M, sell H   payoff >= 0
  LOCK B   if  ask(hourly L) <  bid(15M)          buy L,  sell 15M  payoff >= 0
  and every range band = a call spread on the above/below ladder
```

**Validated, not asserted.** On settled markets, **5 of 5** on-the-hour closes
where both a `KXBTC15M` and a bracketing pair of `KXBTCD` strikes had settled
were result-consistent, **zero violations**. (Only 5 overlapped because two
1,000-market pulls cover different date ranges; a paginated pull gives hundreds.)

**Live snapshot, and it is honest about the answer.** At 11:45:48Z, 14 minutes
before the 12:00 close:

```
  15M  KXBTC15M-26SEP060800-00   K = 79,959.49   bid 0.39 (2,814)  ask 0.40 (2,557)
  hourly  > 79,899.99            bid 0.76 (1,268)  ask 0.77 (73)
  hourly  > 79,999.99            bid 0.21 (101)    ask 0.22 (1,352)

  bound:   0.21  <=  0.395  <=  0.77       SATISFIED. No lock in this snapshot.
```

**No arbitrage was found, and I am not claiming one.** My first pass printed two
"gross" figures that looked like locks; they were the wrong pairing (buying the
dominated leg and selling the dominating one is a short strangle on the strike
gap, not a lock). Corrected above.

**Then I polled the whole close, which is what settles it.** Every ~14 seconds
from 11:42Z to past 12:00Z, both books, net of taker fees on both legs
(`_hourly_poll.jsonl`, `pollan.py`):

```
  ttc s          K   15M bid/ask       L   bid(L)  ask(L)        H   bid(H)  ask(H)   lockA   lockB
    780   79959.49   0.59/0.60   79899.99   0.92    0.93   79999.99   0.33    0.34   -0.302  -0.361
    609   79959.49   0.56/0.57   79899.99   0.90    0.91   79999.99   0.20    0.21   -0.398  -0.373
    438   79959.49   0.34/0.35   79899.99   0.92    0.93   79999.99   0.10    0.11   -0.272  -0.610
    262   79959.49   0.18/0.19   79899.99   0.87    0.88   79999.99   0.01    0.02   -0.191  -0.718
    148   79959.49   0.09/0.09   79899.99   0.92    0.94   79999.99   0.00    0.01   -0.098  -0.859
     91   79959.49   0.03/0.03   79899.99   0.94    0.96   79999.99   0.00    0.01   -0.035  -0.933
     34   79959.49   0.01/0.01   79899.99   0.99    1.00   79999.99   0.00    0.01   -0.007  -0.994
      6   79959.49   0.01/0.01   79899.99   0.99    1.00   79999.99   0.00    0.01   -0.007  -0.994
     -9   79959.49   0.00/0.00   79899.99   0.99    1.00   79999.99   0.00    0.01   -0.001  -1.000

  57 samples, 11:42Z through 12:00Z.  best NET lock A over the window  -$0.0011
                                      best NET lock B over the window  -$0.3615
  (both must be <= 0 for no-arbitrage; both are, at every single sample)
```

**No lock, on any of 57 samples. But look at what lock A does into the close:**
it runs -$0.302 at 13 minutes out, -$0.098 at 148 seconds, **-$0.007 at 34
seconds**, and **-$0.0011 at the bell**. The bound is loose far out (the $100
strike grid is wider than the settlement distribution) and becomes **effectively
binding inside the last two minutes** — by the close the two markets are pinned
to each other to within a **tenth of a cent**.

That is the honest, useful finding, and it is not the one I expected:

* **There is no arbitrage at 14-second polling resolution, and I am not
  claiming one.** My first pass printed two figures that looked like a
  $0.36/contract lock; they were the wrong leg pairing (buying the dominated
  contract and selling the dominating one is a short strangle on the strike gap,
  not a lock). Corrected above. I am recording the wrong version because it
  looked exciting and would have been published.
* **In the last 120 seconds the tolerance is under a cent, and 14-second polling
  cannot see the events `pin` actually trades.** `pin` harvests quotes that are
  stale by 2-4 cents for a few seconds. A 2-cent dislocation between these two
  books inside the last minute would be a *hard, model-free lock* — no
  volatility estimate, no fair value, no settlement risk — and nothing in this
  project can currently see one, because the hourly ladder is not collected.
* **One structural caution.** Where the bound is tightest, the certain leg tends
  to be quoted **one-sided**: deep-ITM strikes show `bid 0.99 / no ask`, deep-OTM
  `no bid / ask 0.01`, with tens of thousands of contracts resting. When the
  locked average lands clearly outside the bracket there may be nothing to lift
  on the leg that completes the trade. That is a real reason to expect the lock
  to be rare — it is not a reason to have never looked.

**What it would cost to test properly.** Read-only REST polling is $0 but too
slow. The real test is one line in `CRYPTO_15M` (`KXBTCD`) plus a file copy, so
the WebSocket records the hourly ladder at book resolution — the same cost as
adding any series, and `PREREG_pin.md` §7.3 is the only thing arguing against
doing it mid-window.

**Judgement: WRONG, as a scope error.** True inside one 15-minute series; false
across the product. The error's main cost is that it hid **item 1**, which is
worth more than this arbitrage would have been. Note also that `CLAUDE.md`
line 244's exhaustive-basket kill concerns *categorical* and *far-dated numeric*
ladders elsewhere on Kalshi and does not cover this pair at all.

---

# 3. "One trade per close" — a clustering device that became a position limit

**As written.** `CLAUDE.md` hard rule 4: *"Cluster by close time; report `n` as
markets or closes, never trades."* `RUNBOOK.md` line 26: *"Report `n` as the
number of markets, never the number of trades."* Then, in code, `pin.py`
line 39: *"one trade per CLOSE (endgame.evaluate keys on close time), so n is
close-time clusters by construction"* — `endgame.evaluate` keeps
`best[r["close"]]`, one entry per close, and **every P&L table in this project
is computed off that dictionary.**

**The inference.** The rule is a *standard-error* rule and is correct as one.
`RUNBOOK.md` line 20 says so itself: *"clustering corrects STANDARD ERRORS, not
POINT ESTIMATES."* It was then implemented as a *trading* rule, so every dollar
figure in the repo's history is the P&L of a trader who takes at most one
position per quarter hour for a statistical reason.

`HANDOFF.md` line 346 already caught this and nothing changed:
*"`evaluate()` takes one trade per CLOSE, which is a statistical rule, not a
trading limit — so every table in this file measures roughly one twelfth of
what a live book could hold."*

**What it ruled out — measured tonight** (`money2.py`, cached rows + depth map,
size `min(100, 0.25 x touch depth)`, 12.1-day cached tape, in-sample):

```
  tau<=20s floor 0.5c   one/close     418 trades   $+28.93/day   peak cap $ 99   worst close $-15.68
                        every market  665 trades   $+53.30/day   peak cap $231   worst close $-25.84
                        ratio 1.84x the money for 1.65x the tail

  tau<=60s floor 0.5c   one/close     818 trades   $ -1.52/day   peak cap $ 99   maxDD $-232.41
                        every market 3141 trades   $+61.68/day   peak cap $330   maxDD $-140.46
                        one-per-close is NEGATIVE where every-market makes $62/day
```

**And there is a second, worse effect nobody has named.** `evaluate` keeps the
*earliest qualifying second* in the close — across all twelve coins. So
one-per-close does not take a random trade from the close; it takes the one at
the **largest tau**, which is the **least-locked and therefore worst-quality**
trade available. At `tau<=20` that barely matters. At `tau<=60` it inverts the
sign of the strategy.

That also explains the row `HANDOFF.md` puzzled over and attributed to
basket leverage:

> *"At `tau<=60s`, the return goes **+0.25c -> +2.99c (12.0x)** while the worst
> close goes -99.3c -> -427.4c (4.3x)."*

The 12x is not diversification. It is the removal of a selection rule that was
handing the strategy its worst trade of every close.

**What it would cost to test.** Nothing — `pin.run_portfolio` computes both and
`PREREG_pin.md` §1 already freezes the every-market variant. The cost was paid
in months of tables that used the other one, and in one strategy cell being
reported as a non-result (`+0.25c, MDE 0.56c`) when the same seconds of tape
carried $62/day.

**Judgement: CORRECT for inference, WRONG the moment it sets size — and it is
worse than a size rule, because it is also a selection rule.** The fix is one
sentence in `CLAUDE.md`: *report n as closes; trade every market.*

---

# 4. "Read-only" became "never learn anything that requires interaction"
### (the operator's own find — quantified here)

**As written.** `RUNBOOK.md` line 12: *"NEVER place, amend, or cancel an order.
No `POST /portfolio/orders`, **ever**."* `CLAUDE.md` hard rule 1 repeats it.
The closing line of `CLAUDE.md`: *"No order has ever been placed."*

**What it ruled out — pin's stated number-one risk, in the repo's own words:**

> *"THE RACE. This is the primary open risk to pin, above everything else. The
> backtest cannot test whether we win the race for a stale quote... Real fills
> will be worse than backtest fills **by an unknown amount, and the amount is
> not bounded by anything measured so far.**"*

There is no tape experiment that answers it. There is exactly one experiment
that does: send a marketable order for **one contract** on a pin signal and see
whether it fills.

**What it would cost.**

```
  1 contract, entry ~$0.93, max loss on a losing settle       $0.93
  measured per-contract expectancy at that cell              +$0.032
  100 probes:   worst case  -$93     expected  +$3.20        answers THE RACE
```

The maximum loss of the decisive experiment is under a hundred dollars on an
account of a thousand, and its expected value is **positive**. It has not been
run because a rule about not risking money was read as a rule about not
interacting.

**Judgement: CORRECT as a money-safety rule, WRONG as applied.** See item 13:
the repo's wording removes even the possibility of asking.

---

# 5. "Twelve correlated series is leverage, not diversification"

**As written.** `HANDOFF.md` line 355: *"**That is leverage, not
diversification.** Twelve correlated coins are twelve times the money AND very
nearly twelve times the loss on the close that goes wrong."* And in the verdict
entry: *"Fixing the dead series would buy leverage, not diversification, and
should not be sold as a route past the threshold."*

**What is true.** For **variance** and for **t-statistics**, exactly right:
rho ~ 0.8 gives 1.22 effective units per close, and t falls 4.6 → 3.6 when coins
are added. `IDEAS.md` B2 predicted it.

**What is not true, in the same document.** Its own measurement at the cell that
was actually frozen:

> *"At `tau<=20s`, going from 1.0 to 1.6 coins per close raises the return
> **+2.55c → +3.95c (1.55x)** and leaves the worst close **unchanged at
> -96.3c**. More money, identical tail. That is strictly better."*

**And at $1,000 the argument dissolves.** Measured tonight: peak concurrent
capital across every coin at `tau<=20` every-market is **$231**, worst close
**-$25.84**, max drawdown **-$25.84**. Correlation is dangerous when it can
compound a loss past what you can fund. Here the arithmetic maximum loss on any
close is the capital deployed into it — **3-5% of the account** — because these
are binaries bought outright, with no margin, no financing and no liquidation.
There is no mechanism by which rho ~ 0.8 hurts a $1,000 account at this
deployment.

**What it would cost to test.** Free; the numbers exist. What is needed is to
stop reporting a falling t as if it were a falling return.

**Judgement: PARTLY CORRECT — right about variance, wrong about money at this
size.** The sentence should read: *"more money, less statistical certainty, and
at a $1,000 account the tail is bounded by the capital deployed."*

---

# 6. "A stage must clear its MDE"

**As written.** `CLAUDE.md`, Writing new analysis: *"State the MDE before the
estimate."* `BIASES.md` pattern 14: *"Detection asserted without power... Print
the MDE next to every null."* Both are good rules.

**The inference.** MDE became a *pass mark*. `HANDOFF.md` 2026-09-04, on the one
cell in the project that beat its own market-is-right null:

> *"trades 705 claimed 1.87c **REALISED +0.86c** t 1.33 MDE 1.93c ... It is NOT
> proven and must not be reported as such: t = 1.33, and the MDE of 1.93c is
> larger than the effect, so this sample could never have certified 0.86c
> whether it was real or not."*

A correct statement about *detectability*, used to shelve a **+0.86 c/contract
measured expectancy over 705 trades** in the one place a result sat outside its
null. Under "positive expectancy", +0.86c on ~$0.90 of capital is roughly a
**0.95% return per turn** on a seventeen-second hold. The question is whether it
is real, not whether this sample could have proven it.

**What it would cost to test.** Free — the number exists. What is missing is the
willingness to size it, and more tape, which arrives on its own.

**Judgement: WRONG.** MDE tells you what a sample could have detected. It says
nothing about whether the money is there. Keep printing it; stop grading on it.

---

# 7. The graveyard is stale, and it contradicts the live results

**As written.** `IDEAS.md` line 298, in a table headed **"THE GRAVEYARD — do not
re-propose these"**:

> *"Making the spread, any price bucket | Realised signed markout +0.612c at
> 1s... **Loses -0.36c to -0.75c per fill in all seven price buckets.**
> `maker.py`."*

**And `HANDOFF.md`, days later:** *"MARKET-MAKING IS CONFIRMED... maker P&L
+0.48c t=6.4 on 17,139,809 fills... It also pins `maker.py`'s error precisely:
its 0.50c capture was right. It compared that capture against the ALL-FILLS
markout of 0.612c when the at-touch population is only 0.27c. Two different
populations, one comparison."*

The graveyard's largest entry is **known to be wrong** and still stands as a
prohibition — next to `CLAUDE.md` line 234: *"Do not resurrect a killed approach
without evidence that specifically overturns the stated reason it was killed."*
The evidence exists; the entry was never edited. Anyone reading `IDEAS.md`
before `HANDOFF.md` — and `CLAUDE.md` recommends the reverse order — concludes
market-making is dead.

**Two more entries that do not survive their own footnotes:**

* *"Taker trading on order-flow imbalance | ...~100x too small. **Zero** trades
  cleared the cost of crossing at any horizon."* Killed on the cost of
  **crossing**. `HANDOFF.md` itself: *"a signal far too small to pay 2c of
  spread is not too small to decide when to pull a resting quote."* The maker
  application is untested and the kill does not cover it. Cost to test: hours,
  off the warm `flow_cache`, feeding `queuesim`.
* *"Wide maker quotes earn the spread | The fee theorem: `E[P&L | fill] <=
  -fee(p)`, invariant to quote width."* The theorem's premise is *"A rational
  taker crosses only when their estimate beats the touch by more than the
  fee."* `informed.py` measured taker information at the touch at **+0.02c,
  t=0.2, on 17.1M fills** — the premise is false exactly where it matters, which
  is why the measured number is +0.48c and not -1.75c. A theorem killed a
  strategy before the strategy was measured.

**And one entry whose *wording* kills the live strategy.** `IDEAS.md`:
*"The book lags the index (stale-quote edge) | Refuted — the book **leads** by
1s, t = 29.4."* The measurement is right. But "stale-quote edge" is exactly the
phrase `HANDOFF.md` uses for `pin` — *"the race for a stale quote"*. The two are
different things: what `leadlag.py` refuted is *quote stale against the index*;
what `pin` harvests is *quote stale against the settlement average that is
already 40 seconds locked on our own disk*. A reader scanning the graveyard for
"stale quote" finds a kill sitting on top of the one live strategy. Re-word it.

**What it would cost to fix.** An edit. **Judgement: WRONG (stale).** This audit
should be re-run whenever a live result contradicts a graveyard row, and the row
should be dated and struck rather than left standing.

**`CLAUDE.md`'s own killed-approaches list has the same problem.**
*"Dutch-book basket arbitrage — killed structurally. **The fee function peaks at
p = 0.50, which prices out balanced baskets.** Monte Carlo showed **passive
legging needs implausible fill rates**."* Both halves are taker/queue arguments
made before either was measured:

* **Makers pay nothing** (`CLAUDE.md`, confirmed mechanics). A passively-legged
  basket pays no fee at all, so the quadratic-fee half of the kill does not
  apply to the passive version — which is the version the same sentence then
  kills on fill rates.
* **"Implausible fill rates"** was a judgement made when the touch was believed
  to hold 3,767 contracts (`PLAN.md` §4, since corrected to ~55) and before
  `informed.py` measured at-touch takers carrying **zero** information
  (t = 0.2 on 17.1M fills). `queuesim.py` is measuring the fill rate now. The
  kill pre-dates its own evidence.

---

# 8. "Consistently" became "statistically significant"
### (the operator's own find — recorded here with the decision it changed)

**Where it cost money, specifically.** `HANDOFF.md` on the every-market variant:
*"**But the t-stat falls, 4.6 → 3.6.** Twelve correlated coins summed within a
close add variance without adding independent observations... **More money, less
certainty.** Both are true and the report must carry both."* The report carried
both; the *verdict* followed the t and not the money. The every-market variant —
1.48x the money at 1.20x the tail, sub-linear and favourable — was written up
as making concentration worse rather than as making more money.

**Judgement: WRONG.** Already accepted by the operator.

---

# 9. "$50/day", "50 contracts", "96 closes per day"

**As written.** `CLAUDE.md` kill criteria, ORIGINAL: *"**Threshold:** net
+$50/day, after fees, at a size the depth measurement shows is actually
fillable."* Retired by the operator on the record the same day. The artefacts
are still load-bearing:

* `portfolio()` computes `day = mu * 96 * contracts / 100`. Available closes run
  **63.3/day** and the `tau<=20` cell **fires on 37.2/day**. Every published
  $/day built on 96 is inflated by up to **2.58x**. `HANDOFF.md` lists this as
  still-open item 1; the sweep has not been run.
* `HANDOFF.md` still carries, *above* the retraction, a section headed
  *"pin IS DEAD against the kill criteria"* — a FAIL that exists only because
  the interval [+$19, +$48] straddled a round number.
* Every dollar table anchored to "50 contracts" answers a question about a size
  the book does not offer 42.3% of the time.

**Judgement: retired, but not cleaned up.** The remaining work is mechanical:
grep every `96` and every `50 contracts` in `results/` and restate each as
$/contract/day + peak capital + % return.

---

# 10. "The tape is the only data source"

**As written.** Nowhere. It is the shape of the whole repo: ~40 stages, all
reading `kalshi_data`, `feed_data` or `fulltape`.

**What was actually available, free and read-only, tonight:**

1. **The REST catalogue already on disk.** `series_crypto.json` and
   `series_fin.json` were pulled 2026-08-27 and have sat unread. They settle
   `CLAUDE.md` contradiction 3 with **no API call at all** — see item 15b.
2. **Live REST.** Six calls tonight produced the hourly settlement rule, the
   188-strike ladder, the touch depth on it, and a settled-market consistency
   check. `CLAUDE.md`'s next-action list has *"Settle contradiction 3 with one
   API call"* outstanding.
3. **`feed_data`** — the constituent exchange books, *"3+ GB/day that NOTHING
   has ever read"* in `go.py`'s own description of the `feeds` stage. Read once,
   for A5; and the comparison `IDEAS.md` A5 says actually matters (our replica
   vs the **book**, not vs the published index) has never been run.

**Judgement: PARTLY CORRECT** — the tape is the only high-frequency source.
**WRONG as applied**: three free read-only sources were treated as out of scope
because they are not the tape.

---

# 11. "flow.py costs 100 minutes, so the order book is off-limits"

**As written.** `CLAUDE.md`: *"**Do not** re-run `flow` unless the book itself
is in question; it costs ~100 minutes on a cold cache and neither live result
depends on re-mining it."*

**The rule is correct, and its own text says so — "and seconds after."**
Verified tonight: `flow_cache/` is **122 MB with `v4` files for all 11 days,
20260825-20260904.** The cache is warm. The book is not expensive.

**What the behaviour ruled out.** `IDEAS.md` C2 (queue position) has been the
named next build since 2026-09-03, and `CLAUDE.md` calls it *"the only thing
between the maker result and a number in dollars."* `queuesim.py` is running as
I write, so this one is being fixed tonight.

**Judgement: the written rule is right; the behaviour it produced was wrong.**
Cost to test: seconds, off the warm cache.

---

# 12. "500 fired closes of forward tape before anything is believed"

**As written.** `CLAUDE.md` line 460: *"**Minimum sample:** 500 fired closes of
FORWARD tape, collected after the rule is frozen... At ~37 fired closes/day that
is ~14 days."*

**The inference.** 500 is a *detection* sample size — it comes from the
t-statistic bar the operator has retired. And `PREREG_pin.md` §6.7 concedes what
those 14 days buy:

> *"A forward test on **recorded tape** is still a backtest of a frozen rule; it
> is not a paper trade and it is not a live trade."*

So the plan spends 14 days producing another backtest, while the risk it does
**not** address — THE RACE — is the one the same document calls primary.
Fourteen days of the measured $53-101/day is **$750-1,400 of foregone P&L**, and
it does not answer the question that matters.

**Judgement: WRONG under the current framing.** Freezing the rule in writing is
right and costs nothing. Waiting 500 closes before any money moves is a
t-statistic requirement wearing a pre-registration's clothes. Run the frozen
rule and a 1-contract live probe **in parallel**.

---

# 13. "Never place, amend, or cancel an order, **ever**"

**As written.** `RUNBOOK.md` line 12; `CLAUDE.md` hard rule 1.
**As the operator states it:** no live orders *without explicit per-instance
sign-off*.

Those are different rules. The repo's version has no gate to open, so no session
has ever drafted the request that would let the operator say yes. The correct
wording is a permission, not a prohibition:

> *"Never place, amend or cancel an order without the operator's explicit
> per-instance sign-off. When an experiment can only be run with an order, write
> the experiment down — size, maximum loss, what it decides — and ask."*

**Judgement: the repo rule is stricter than the operator's, and it is the
mechanism by which item 4 happened.** Cost to fix: an edit.

---

# 14. "The strategy must hold to settlement" — MEASURED TONIGHT, AND IT IS RIGHT

**As written.** Nowhere as a rule; universal in the code. `endgame.evaluate`
books `pnl = 100*(won - entry) - fee`, settlement only. `informed.py` line 48:
*"the resting side's actual fill held to settlement"*. `pathstats.py` is the only
file that even mentions the alternative: *"A violation is tradeable without ever
holding to expiry — enter, wait, exit — which is a far better risk shape than
betting on the outcome."* No stage has ever priced an early exit.

**Measured** (`exit2.py`, cached `rows_tau60.pkl`, pin rule `tau<=20`, floor
0.5c, one per close, n=420, both crossings' fees charged):

```
  HOLD TO SETTLEMENT        mean  +2.641 c   sd 12.0   t +4.50   n 420

  SELL BACK AFTER H SECONDS
     H    n     mean c       t     win%      worst
     1  412     -3.098   -7.22   12.9%    -94.12
     2  408     -2.207   -4.86   25.7%    -94.12
     3  393     -1.729   -3.37   35.1%    -94.12
     5  352     -1.248   -2.17   52.6%    -80.47
     8  268     -0.153   -0.19   72.0%    -87.76
    10  203     -0.072   -0.07   71.4%    -90.66

  MATCHED on the same trades:  exit at H=1   -3.098 c  vs held  +2.692 c
                               exit at H=10  -0.072 c  vs held  +3.174 c
```

**Holding to settlement is worth +3.2 to +5.8 c/contract over exiting early, and
every early-exit horizon out to 10 seconds is at or below zero.** Two mechanical
causes: the stale quote pin buys does not re-price within ten seconds (that
staleness *is* the edge), and selling back pays a second crossing.

**And it costs nothing in capital.** Mean cost basis $0.929, mean hold
**17.5 seconds**, 2.84% return per turn. There is no capital argument for
exiting early either.

**Judgement: CORRECT — and now measured instead of assumed.** Close this item.
It is the one place tonight where the inferred constraint turned out to be the
right one.

---

# 15. Kills that do not survive the re-scope

**(a) "Exhaustive-basket arbitrage — killed empirically."** `CLAUDE.md`
line 249: *"Genuine numeric ladders ran ~13c too expensive at the median,
**best +7c at depth 0-1**."* A **positive seven cents at depth 0-1** is filed as
a kill. Depth 0-1 is precisely the size a $1,000 account trades. The kill is a
*capacity* kill — `CLAUDE.md` line 244's own wording is "no *usable* locks",
which is a size judgement. **Worth re-scoring the 467,907 priced ladders at
depth 0-1 only.** *Checked tonight: that run's output does NOT survive on this
machine* — `C:\kals` and `C:\kals-repo` contain no ladder/basket/arb output
file, and `fulltape/` holds only `markets.json` and `tapes.json` for the 15M
series. So the re-scoring costs a 16-hour re-run, unless the operator still has
the original output. That is the single reason this item sits at 15 and not
higher: it is the only one whose test is expensive.

**(b) `IDEAS.md` B3, the half-fee lever — SETTLED TONIGHT, FROM DISK, AND IT IS
DEAD.** `CLAUDE.md` contradiction 3 has been open awaiting "one API call". It
needed none — `series_fin.json`, pulled 2026-08-27, contains the answer:

```
  KXNDQ15M   fee_type quadratic   fee_multiplier 1
  KXINX15M   fee_type quadratic   fee_multiplier 1      (same as all 14 crypto 15M)
  only non-standard crypto rows:  KXBTCY / KXETHY      multiplier 0 (annual)
                                  KXBTCMAX125/150      quadratic_with_maker_fees
```

**B3 is refuted: strike it.** The operator's version of contradiction 3 wins on
the fee question. Separately, both equity 15-minute series returned **zero open
and zero settled markets** on live REST tonight, so they are catalogue entries
rather than a live universe — which also means they are not the
uncorrelated-series rescue they looked like.

**(c) "Crypto delta-neutral basis trades — yields below hurdle."** A hurdle set
for a size this account does not trade. Not re-examined here; flagged as a kill
whose stated reason is a size judgement.

**(d) `endgame` "killed".** Listed among *"eight ideas dead"* on 2026-09-03,
then four days later it is the **only** cell in the project outside its own
market-is-right null (+0.86c against a null top of +0.57c). Killed on power, and
`pin.py` exists *because* of it. Same failure mode as item 7: the graveyard says
dead, the results say the opposite.

---

## WHAT I DID NOT DO, AND WHY

* **I did not re-run any stage.** Free RAM was 3.0 GB with `queuesim.py`
  (627 MB) and another job (498 MB) live; the resource protocol forbids a second
  `load_quotes`. Everything above came from the cached pickles, the on-disk
  catalogue JSON, and read-only REST.
* **The hourly-ladder profitability is NOT measured.** I established that the
  settlement rule is identical, that the ladder is 188 strikes deep, that 102 of
  188 carry a bid, and that the near-money strikes carry 250,000+ contracts of
  volume. I did **not** measure whether pin's edge exists there. That is the
  next job and it needs no new collection.
* **No arbitrage was found, and I checked properly before saying so.** 57
  paired snapshots across a whole close, 11:42Z to 12:00Z. The bound held at
  My first pairing of the legs was wrong and is corrected in item 2. I am
  recording the wrong version as well as the right one because the wrong one
  looked like a $0.36/contract lock and would have been an exciting number.
* **The 96-vs-63.3 closes/day sweep was not run.** It is a grep over `results/`
  and it is item 9's outstanding work.
* **Nothing in the repo was edited.** Items 3, 7, 13 and 15b each imply a
  specific documentation change; I have written what the change is and left the
  decision to the operator rather than rewriting `CLAUDE.md` inside an audit.

---

## HOW TO RE-RUN THIS AUDIT

The operator wants this periodically, because it will keep happening. The
mechanical part:

1. **Diff the graveyard against the live results.** Every row of `IDEAS.md`'s
   graveyard and `CLAUDE.md`'s killed-approaches list, against `HANDOFF.md`'s
   top three sections. Any row whose stated reason has since been measured
   differently is stale (item 7 found two; item 15 found two more).
2. **Grep for the four smells.** `never`, `ever`, `always`, `must` in the `.md`
   files — most inferred constraints announce themselves with one of those
   words attached to something nobody required.
3. **Ask of every kill: was it killed on a RATIO or on a SIZE?** Ratio kills
   (delta-hedging costs 5-200x what it earns) survive a re-scope. Size kills
   ("no *usable* locks", "yields below hurdle", "implausible fill rates",
   "$50/day") do not, because the size changed.
4. **Ask of every rule: is it a statement about STANDARD ERRORS or about
   MONEY?** Items 3, 6, 8 and 12 are all the same failure — an inference rule
   applied to a trading decision.
5. **Re-read the scope sentence.** `CLAUDE.md` line 7 defines the universe.
   Check it against `series_*.json` on disk, which is free.

## CROSS-CHECK AGAINST THE PARALLEL JOB, AND ONE DISAGREEMENT TO RECONCILE

`results/overnight/FEES_AND_PRODUCTS.md` was written by another session at
07:54 tonight and independently reached the hourly ladders from the product
side. Two things to reconcile before either report is relied on:

1. **Census scope.** It reports `fifteen_min` 26, `hourly` 65, `daily` 279
   across the whole exchange. I report `fifteen_min` 14, `hourly` 25,
   `daily` 22 **within the crypto category only** (`series_crypto.json`).
   Both can be right; state the scope whenever either is quoted.
2. **Depth — a real disagreement.** That report describes the hourly crypto
   ladders as **"thin, 1c at touch"**. I measured, at 148 seconds from the
   12:00Z close on `KXBTCD`: near-money strike `>79,899.99` **bid 0.92 x
   (1,012 contracts) / ask 0.94 x (877)**, and event volume 580,569. That is
   not thin. The likely explanation is *which strike and when*: 188 strikes
   means most of the ladder is dead and only the 3-6 near-money strikes carry
   size, and size concentrates into the close. **Whoever tests item 1 must
   measure depth AT THE NEAR-MONEY STRIKE INSIDE THE LAST 120 SECONDS**, not
   pooled across the ladder — pooling across the dimension that matters is
   `BIASES.md` pattern 7, and it is the difference between item 1 being the
   biggest finding here and being nothing.

---

## COLLECTORS AND RESOURCES

```
  kalshi_collector.py   PID 2708908   ALIVE   26.8 MB
  crypto_feeds.py       PID  531268   ALIVE   14.8 MB
  free disk C:          53 GB    (protocol floor is 4 GB)
  free RAM              3.0 GB of 15.8 GB
```

Nothing under `kalshi_data/`, `feed_data/` or `fulltape/` was written or
modified. No order was placed, amended or cancelled. All API calls were
`GET /trade-api/v2/markets`.

---

## THE TWO THINGS TO DO NEXT, IN ORDER

**1. Ask for sign-off on a 1-contract live probe of pin. This is the cheapest
path to actual money and it is blocked only by item 13's wording.**

```
  what it decides   THE RACE -- whether we win a stale quote in reality.
                    Nothing on tape can answer it, and it is the repo's own
                    stated #1 risk.
  size              ONE contract per signal, taker, at the pin cell already
                    frozen in PREREG_pin.md (tau<=60, floor 0.5c, every market)
  max loss          $0.93 per probe. 100 probes: worst case -$93.
  expected value    +$0.032/contract measured  ->  +$3.20 over 100 probes
  duration          ~3 days at the measured 34 fired closes/day
  what it is not    it is not a deployment, and no size is scaled until the
                    fill rate is in hand
```

If the fills come in at the backtest rate, pin is real and the $231-peak-capital
version deploys immediately. If they do not, pin dies for under a hundred
dollars instead of after fourteen more days of tape.

**2. Backtest pin on `KXBTCD` (hourly BTC) from data already on disk.** No new
collection, no orders, no operator decision, no new pulling code: the recorded
BRTI tape supplies the locked prints and `kalshi_fulltape.py --series KXBTCD`
supplies the outcomes and prints. It is the cheapest test of the most expensive
constraint in this audit and it points straight at the only thing standing
between pin and a size worth having, which is depth.

These are independent and can run at the same time. Neither of them needs the
500-close forward window to finish first.
