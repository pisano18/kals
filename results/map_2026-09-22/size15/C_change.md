# C_change — the decision on the 1.5x size step

**2026-09-23. Label `specify`.** My own join of `results/pinrun-live-*.jsonl`
to `results/kalshi_ledger.json` (Kalshi's own settlement rows), plus the
sizing chain read out of `research/pinrun.py` and `restart_bot.ps1`. **No
replay, no `pinsim`, no `pindata`.** Scratchpad scripts under
`size15\specify\`. Collectors alive (`kalshi_collector.py` pid 105304, 57 MB;
`crypto_feeds.py` pid 105352, 44 MB). Disk 19 GB free (guard 6 GB). Free RAM
0.89 GB — nothing here reads the tape.

My join reproduces A_rederive to the cent where we overlap: worst close
**-$108.86**, most cash in one close **$312.79**, fill rate 94.9%.

---

## VERDICT — the condition does not hold, and the answer at 1.5x is NO

The operator: *"if ... the worst close is genuinely unchanged let's do it."*

**It cannot be unchanged, at any multiple, under any flag combination.** This
is arithmetic in the file, not a statistic (`pinrun.worst_close_cost`):

```
worst close = (MAX_PER_CLOSE + max(EXTRA_COIN, LATE_EXTRA)) x SIZE x PRICE_CEILING
            = 3 x SIZE x 0.98
```

The worst close **is** the bet size. Raising one raises the other one for one.
B_attack tested capping the close instead (worst close barely moves, -$159.77)
and A_rederive tested a per-coin step (B refuted it: BTC is both our deepest
book and our biggest loss coin). There is no version of this where the money
goes up and the worst close stays put.

At today's bank of **$1,002.27** (high-water $1,003.86), read from the live
`autosize` records:

| | brake 4.00 (today) | 3.20 (1.25x) | 2.67 (1.5x) |
|---|---|---|---|
| bet | **85** | 106 | 127 |
| hard bound, one close, everything lost at the ceiling | **$249.90** | $311.64 | **$373.38** |
| that as a share of the bank | **24.9%** | 31.0% | **37.2%** |
| worst close we have actually had, re-priced at this bet | **-$89** | -$111 | **-$133** |
| most cash ever committed in one close, re-priced | $313 | $391 | **$469** |
| one order inside the last 10 s (`--late-mult 1.5`) | 127 | 159 | 190 |
| close contract budget (+ the third-coin allowance) | 170 (+85) | 212 (+106) | 254 (+127) |
| day cap `--loss-cap 200` covers this many worst closes | 2.2 | 1.8 | 1.5 |
| 20% drawdown halt ($200.77) covers this many | 2.2 | 1.8 | 1.5 |

### Four reasons, in the order they decide it

**1. The operator already set the rule this breaks, and the bot is obeying it
exactly.** On 2026-09-18 he chose "divide by 8" after being shown that it put
the worst close at **25% of the bank instead of 33%** (`pinrun.py` line ~770,
his words *"Sure divide by 8"*). Today the worst close is **24.9% of the
bank** — his number, hit on the nose. 1.5x puts it at **37.2%**, worse than
the 33% he deliberately moved off. 1.25x puts it at 31.0%, just inside it.

**2. We have already run the 1.25x bet, at this bank, and it produced the
worst day in the bot's history.** Straight off the live `autosize` records:

```
2026-09-19T08:33:55  size 106  bank $  935.19
2026-09-19T15:01:05  size 113  bank $ 1001.97
2026-09-19T16:01:06  size 114  bank $ 1012.56     <- same bank as today, 1.34x the bet
2026-09-20T04:46:51  size  92  bank $  814.12     <- after the brake was raised
```

That day lost **-$223.46** (Kalshi's ledger) and contains our worst close
(-$108.86, at 104 contracts) and our second worst (-$107.95, at 110). The
brake was raised 3.00 -> 4.00 the next morning, **on the operator's own
instruction** — v-proportion, *"Make the bet size only a quarter smaller not
half."* So **"1.25x" is precisely undoing his 09-20 decision, and 1.5x goes
past it to a bet larger than the bot has ever placed.**

Fair to the other side: 3 of the 4 big 09-19 losses were bugs (a gate or brake
blocking a hedge) and those are fixed. The bugs made the losses; the size set
how big they were. And one of the two reasons given for the 09-20 cut — "the
cheap end of the book has halved" — was **later measured false** (`pinsupply`:
cheap offers are +7% against a normal day). The other reason, "no correlation
between size and daily money", is re-checked in section 6 and still does not
show a bigger bet earning more.

**3. The step is already coming, free, on a schedule.** SIZE follows the bank
automatically every 300 s (`autosize_tick`). At the current brake:

| bet | bank it needs | from today's $1,002.27 | at our median good day (~+$85) |
|---|---|---|---|
| 94 | $1,105.44 | +$103 | ~1-2 days |
| **106 (the 1.25x bet)** | **$1,246.56** | **+$244** | **~3 days** |
| 127 (the 1.5x bet) | $1,493.52 | +$490 | ~6 days |

**The real alternative to stepping is not "a smaller bet forever". It is "the
same bigger bet a few days later, paid for by the bank that carries it."** A
step buys those days and pays for them with one-close exposure at 31-37% of
the bank instead of 25%.

**4. The gain is small, and one time in four it is not a gain.** Both
independent re-derivations: **+$88 over 16 days** (B, depth-capped) and
**+$124 over 9 days** (A). B's day-clustered bootstrap puts it **negative in
25.5% of stretches like this one**, and 56% of the whole gain is one day.
That is about **+$5 a day** bought with **+$120 of exposure in the worst
minute**.

---

## 1. THE LARGEST STEP THAT HOLDS — today, none

Under the condition as written: **none**, because the worst close moves with
every one of them.

Under his second sentence — *"if it makes more money without much more risk
then do it"* — the largest I will put my name on is **1.25x
(`--bank-brake 4.00 -> 3.20`, bet 85 -> 106)**, and **not this week**. Two
things have to be true first, both dated and both close:

- **(a) The freeze finishes.** `results/FREEZE_2026-09-22.md` says in terms:
  *may not change — any flag in `restart_bot.ps1`; any entry gate, size, price
  limit or hedge trigger.* It is at **101 of its 300 closes** (`close_summary`
  records since 2026-09-22T11:42:12Z); at ~94
  watched closes a day it ends around **09-25 ET**. A size change also
  silently corrupts bar **B5**, whose statistic is *contracts bought at <= 30
  s* and *refused contracts at `size_now`* — both scale 1.25x with the bet,
  and `bank_brake` is not in B5's `config_keys`, so **`barcheck.py` would not
  notice**. That is a hole in the freeze's own machinery, worth fixing
  whatever is decided here.
- **(b) The loss rate is established at the current bet.** Section 5.

---

## 2. THE EXACT CHANGE, ready to fire when (a) and (b) are met

### 2.1 Which flag, and why not a new one

`--bank-brake` is the right knob and the only one that should move. The chain
is `SIZE = bank // (BANK_BRAKE * worst_close_cost(1))` and
`worst_close_cost(1) = 3 * 0.98 = 2.94`, so the divisor is `2.94 * brake`.
A new multiplier would be a second free parameter on the same quantity and
would break the one invariant the file is built on — *every rail is derived
from SIZE*, and `apply_size()` re-derives all of them together.

**`"--bank-brake", "4.00"` -> `"--bank-brake", "3.20"`** — exactly 1.25x
(4.00 / 3.20). At the $1,002.27 bank: **bet 85 -> 106**.

Not `2.67` (1.5x): section "Verdict".

### 2.2 What moves with it, every one checked in the code

| | at 85 | at 106 | moves how |
|---|---|---|---|
| bet per order | 85 | **106** | `size_for_bank` |
| one order in the last 10 s | 127 | **159** | `LATE_MULT 1.5 x SIZE` |
| contracts one close may buy | 170, +85 for a new coin | **212, +106** | `close_budget_for` |
| worst close, exact bound | $249.90 | **$311.64** | `worst_close_cost` |
| derived run abort | -$340 | -$424 | `abort_for` — **not binding, the cap is tighter** |
| `--loss-cap` | -$200 | -$200 | **fixed dollars; does NOT scale** |
| drawdown halt | -$200.77 (20% of high) | -$200.77 | **does NOT scale** |
| `pintake` count / stake rails | 163.5 / $664 | ~204 / ~$846 | `apply_size` re-derives with `max()`; `set_limits` refuses a tightening |
| hedge size | matches the position | matches the position | unchanged in kind; section 4 |

**Two rails do not scale, and both must be re-set in the same deploy.**

**`--loss-cap 200 -> 135`.** Today the day cap stops the day after ~2 worst
closes. At 106 contracts it stops after 1.5, which means one bad close ends
the trading day and very nearly trips the 20% drawdown halt at the same time
(a halt needs a human look; the cap just pauses). 135 restores "two bad closes
before the day stops" at the new bet. Measured on Kalshi's ledger over **19 ET
days**, pin markets only, flat multiple:

| day cap | days it would ever have fired | effect on the 19-day total |
|---|---|---|
| $200 (today, bet 85) | 1 (09-19, at 23:45 ET) | $0 |
| $160 or $135 (bet 85) | 1 (09-19, at **16:00 ET**) | **+$52.27** |
| $200 (bet 106) | 1 (09-19, 16:00 ET) | +$65.33 |
| **$135 (bet 106)** | 1 (09-19, at **02:00 ET**) | **+$139.67** |

The second-worst ET day we have ever had is **-$40.59**. A cap anywhere
between $100 and $200 has never touched any day but 09-19, and on 09-19
everything after every crossing was a further loss. **Confidence: the
direction is right, the size of the gain rests on one day. n = 1.** The cost
if a future day drops $135 early and would have recovered is the rest of that
day; that has never happened in 19 days.

**The drawdown mark does not need to move** and should not. It is 20% of the
high-water bank, so it scales with the bank by itself. At 106 it covers 1.8
worst closes; that is the price of the step and it is visible.

### 2.3 The exact `restart_bot.ps1` edit

Two string literals, nothing else:

```powershell
# line 463
-    "--bank-brake", "4.00",
+    "--bank-brake", "3.20",

# line 469
-    "--loss-cap", "200"
+    "--loss-cap", "135"
```

Then, in this order:

```powershell
python research/pinrun.py --selftest                       # defaults only -- NOT sufficient
# the startup path WITH the new flags, paper, because pinrun self-tests at
# STARTUP with flags applied and an old check asserting a RUNNING value has
# taken the live bot down for 6 minutes before:
python research/pinrun.py --size 20 --minutes 1 --bank-brake 3.20 --loss-cap 135 --no-auto-size
python research/versioncheck.py                            # must print "clean"
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
.\sync_arms.ps1                                            # or every paper arm is a different bot
```

`versioncheck.py` fails on a flag value VERSIONS.md does not contain, so the
entry below must be written **before** the restart, and must contain the
literal strings `3.20` and `135`.

### 2.4 The VERSIONS.md entry (paste at the top, fill the two blanks at deploy)

```markdown
# v-brake320 -- 2026-09-__ ~__:__Z -- LIVE: the bet goes up a quarter, the day cap comes down a third

**What the bot now does differently.** `--bank-brake 4.00 -> 3.20` and
`--loss-cap 200 -> 135`. At the $1,0__ bank the bet moves 85 -> 106
contracts. Every size-derived rail moves with it through `apply_size()`;
the two that do not scale are reset by hand in the same deploy -- the day
cap (above) and the 20% drawdown halt (unchanged on purpose, it scales with
the bank).

This EXACTLY REVERSES v-proportion (2026-09-20), which cut the bet a quarter
on the operator's instruction "Make the bet size only a quarter smaller not
half". One of v-proportion's two stated reasons -- "the cheap end of the book
has halved" -- was later measured FALSE (research/pinsupply.py: cheap offers
+7% against a normal day). The other, "no correlation between size and daily
money", is unresolved and is what the bar below measures.

**Evidence.** results/map_2026-09-22/size15/{A_rederive,B_attack,C_change}.md,
three independent parses of our own fills against Kalshi's ledger, no replay.
Depth-capped re-sizing says +$88 over 16 days (B) / +$124 over 9 days (A) at
1.5x; this is the 1.25x half of it, about +$49. Day-clustered bootstrap says
the gain is negative in 25.5% of stretches like this one. The worst close is
NOT unchanged: -$108.86 -> about -$135, hard bound $249.90 -> $311.64 (25% ->
31% of the bank). The operator was told this and took the step anyway; that is
recorded here so the choice is visible, not so it can be relitigated.

**Bar and kill rule: results/PREREG_brake320.md (section 3 of C_change.md),
written before the first fill at the new size.**

## Revert

```powershell
# bet back to 85 at a $1,000 bank, day cap back to 200: edit restart_bot.ps1
#   set   "--bank-brake", "4.00",
#   set   "--loss-cap", "200"
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
.\sync_arms.ps1
```
```

### 2.5 The revert, copy-pasteable

```powershell
# one command after the two literals are put back:
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

`restart_bot.ps1` refuses to run while the bot holds a position, validates the
whole argument list before it stops anything, and starts nothing but `pinrun`.
It never touches the collector. **A revert costs one restart and no trades
beyond it.**

---

## 3. PRE-REGISTERED BAR — and it is a RISK bar, not a money bar

**A money bar is not possible here and saying so is part of the answer.** A
size step is pure leverage: it multiplies the edge and the noise by the same
1.25. The delta is ~+$3 a day against a daily spread of -$223 to +$116. No
window anyone will wait for can tell +$3 from zero. **Any bar that claims to
judge "did the bigger bet make more money" in under a month is a bar that will
be misread.** So the bar judges the only thing that is newly at risk: whether
a bigger order still executes like a smaller one, and whether the tail behaves
as modelled.

Write it to `results/PREREG_brake320.md` **before the first fill at the new
size**, with the pre-step numbers frozen in it.

| | |
|---|---|
| **window** | the first **150 closes** with a fill at bet >= 100 contracts, counted from the `start` record of the deploy (~1.6 days at ~94 closes a day) |
| **unit** | close (quarter hour, every coin together) — never trades |
| **money source** | `results/kalshi_ledger.json` via `pinledger.pnl`. Never the logs' `realised`, never a replay |
| **frozen comparison** | the 150 closes immediately before the deploy, same source |

**PASS** — all three, or the step is not carried forward:

1. **Execution did not degrade.** Cents per contract over the window is no
   more than **0.5c** below the frozen 150-close figure. (Mechanism: a 1.25x
   order walks further up the ladder. A_rederive measures the extra contracts
   at +0.57c dearer; B measures full-fill falling from 97.3% to 68.4% as an
   order eats more of the book. This is the one real cost and it is
   measurable in 150 closes.)
2. **Fill rate held.** Contracts delivered / contracts asked >= **90%**
   (frozen figure 94.9%). Below that, the bet is bigger than the book and the
   step is buying air.
3. **No rail was silently exceeded.** Every `autosize` record in the window
   shows `max_take_count >= 1.5 x SIZE` and `max_run_stake >= 3 x 2 x SIZE`,
   and no `order` record was refused by a `pintake` count rail. (This is the
   2026-09-08 failure — 160 orders sent, 0 filled, no error raised.)

**FAIL on any one -> revert to `--bank-brake 4.00 --loss-cap 200` the same
day**, with the version entry.

### KILL — immediate revert, no discussion, tied to dollars in one close

Any ONE of these, at any time in the window:

- **Any single close commits more than $400 of cash** (both legs, Kalshi's own
  `yes_total_cost_dollars + no_total_cost_dollars`, summed across every market
  settling at that quarter hour). Today's lifetime maximum is **$312.79** over
  594 closes; 1.25x of it is $391. $400 is the line at which the model of this
  step is wrong, not the line at which we had a bad day.
- **The bank falls more than 12% below its high-water mark** (`pinrun-hwm.json`).
  That is more than half the 20% self-halt and it fires before the bot stops
  itself, so the decision is ours and not the brake's.
- **Any market where the insurance ends short of the position by more than
  10%** (`hedge` records: contracts got vs contracts held). 18 of our 19
  hedged markets were covered in full; the one that was not was a gate bug, not
  the book. If that changes at the bigger size, the step is over.

**Deliberately NOT a kill rule: one bad market, or one bad day.** We lose 3 to
5 closes in 100 by design; a -$135 close at this bet is the strategy working
as described, and killing on it is how a rule gets tuned on noise.

---

## 4. THE HEDGE — B_attack's blocker does not survive a per-market look

B_attack's headline is *"hedge orders short in 12 of 37 fires, 1,321 asked,
953 filled = 72.1%"* and calls it "a bug-shaped risk". **That statistic counts
retries as failures.** The hedge re-asks every second until it is covered. Per
MARKET, from the same records:

| | |
|---|---|
| markets a hedge ever fired on | **19** |
| covered the position **in full** | **18** |
| covered short | **1** — BNB 09-19 01:45Z, 76 held, 1 covered |

The one failure is the A63 gate refusing to buy the winning side while the
losing leg was on the books — a **bug, fixed** (v-safety1, K1-K3: a crash, a
pintake halt or a frozen index can no longer silence a hedge). It was not the
book.

Would the book have covered a bigger position? Taking the **deepest insurance
quote the hedge actually saw** in each market (cautious — it ignores retries
walking further up the book):

| | covers 1.25x the position | covers 1.5x |
|---|---|---|
| 18 hedged markets with a position | **17** | **15** |

The three that fail at 1.5x are **NEAR (twice) and BNB** — the two thinnest
coins in A_rederive's depth table, and the coins behind four of our seven
biggest losses. **So the hedge's reach is not the reason to refuse 1.25x.**

B's 56.5% figure comes from `hedge_quote`, which is written **every second we
hold a position** — overwhelmingly seconds at 99% confidence where the other
side is cheap and thin and no hedge is wanted. The population that matters is
the alarm second, and at the alarm second there were only **9 records in 1
market** below the 0.25 trigger (`hedge_quote` only exists since 09-22
11:52Z). **That number cannot be measured yet; it will be measurable after
~10 more alarms.**

**What a full cover actually buys — and this is the operator's question.** A
full cover makes the outcome CERTAIN. It does not give the stake back, because
the two sides together cost more than the $1.00 one of them pays. Our own
fully covered losses, `locked_loss_c` from the live `hedge` records against
Kalshi's ledger:

| market | held | covered | locked in, per contract | Kalshi's ledger |
|---|---|---|---|---|
| XRP 09-19 23:45Z | 104 | 104 = 100% | 60.7c | **-$64.95** |
| NEAR 09-21 12:45Z | 81 | 81 = 100% | 61.1c | -$59.09 |
| HYPE 09-21 18:15Z | 55 | 55 = 100% | 55.0c | -$31.27 |
| HYPE 09-19 23:45Z | 104 | 104 = 100% | 40.1c | -$43.92 |
| BTC 09-14 05:30Z | 60 | 60 = 100% | 40.2c | -$34.26 |

**Every one of those was covered in full, and every one still lost 40-61c per
contract.** The insurance turns an uncertain ~86c-a-contract loss into a
certain ~55c one. **It recovers about a third. It never returns the bet.** And
because the locked loss is *per contract*, a fully hedged loss scales exactly
1.25x with the step, like everything else.

---

## 5. THE ONE THING THAT MAKES ME SAY NOT YET

**We do not yet know we are on the right side of break-even at the CURRENT
bet, and leverage does not fix that — it multiplies it.**

Kalshi's ledger, grouped by quarter-hour close (the rule's unit), break-even
computed from our own average win and average loss:

| window | closes | losing | 95% upper bound | break-even loss rate | money |
|---|---|---|---|---|---|
| lifetime | 594 | 4.71% | 6.41% | **7.82%** | +$549.73 |
| since 09-15 | 316 | 3.80% | 6.08% | 6.19% | +$354.70 |
| **last 200 closes** | 200 | **4.00%** | **7.10%** | **4.32%** | **+$41.46** |
| since 09-20 | 121 | 3.31% | 7.40% | 5.21% | +$122.60 |

**Over the whole record the edge is established** — 4.71% losing against a
7.82% break-even, and even the pessimistic bound (6.41%) stays inside it.
**Over the last 200 closes the margin is 0.32 percentage points** (4.00%
against 4.32%) and the honest upper bound is 7.10%, well the wrong side. The
reason is not a worse hit rate; it is that **the average loss has grown faster
than the average win** ($24.83 -> $53.06 lifetime to recent, while the average
win went $1.73 -> $2.03), which is what a bigger bet plus 09-19 does.

That is exactly what the 300-close freeze is for. **It is 101 closes in and
ends around 09-25 ET.** Stepping now spends the measurement to buy ~$5 a day.

---

## 6. WHAT I CHECKED THAT THE OTHER TWO DID NOT, AND WHAT I COULD NOT

**Checked, and it matters:**

- **The step is already scheduled** (section, reason 3). Neither paper priced
  the step against *waiting*, which is the real alternative.
- **The 1.25x bet has already been run at this bank** (reason 2). It is not a
  hypothetical, it is 09-19.
- **The hedge blocker is a per-order artefact** (section 4).
- **A size change silently corrupts freeze bar B5** and `barcheck.py` cannot
  see it, because `bank_brake` is not in B5's `config_keys` while B5's
  statistic is in contracts.
- **Does a bigger bet earn more per contract?** The v-proportion claim,
  re-checked on 801 markets with a logged size, Kalshi's money:

  | bet in force | markets | contracts | cents per contract |
  |---|---|---|---|
  | under 40 | 331 | 14,760 | +1.52c |
  | 40-60 | 67 | 3,089 | +0.91c |
  | 60-80 | 67 | 3,442 | **+4.06c** |
  | 80-100 | 26 | 1,406 | +3.07c |
  | 100+ | 113 | 6,047 | **+1.38c** |

  **This does not show a bigger bet earning more, and it does not show it
  earning less either** — bet size grew monotonically with the calendar, so
  every row is also a different week, a different market regime and a
  different code base. It is a confound, not a finding, and anyone quoting
  either direction from it is quoting the date.

**Could not measure:**

- **Whether the insurance book is deep enough at the alarm second at a bigger
  position.** `hedge_quote` only records from 09-22 11:52Z and has seen **one**
  market below the hedge trigger. Needs ~10 alarms.
- **Whether the deep rungs a bigger order would buy actually exist.** B's two
  phantom-ladder cases are the only direct observations and both are on losing
  markets. My own work does not improve on that.
- **374 of our 800 markets have no logged ladder at all** (before 09-15
  07:29Z), so no re-sizing of that half is possible by anyone.

---

## 7. THE OPERATOR'S OTHER FOUR QUESTIONS, answered from the same sources

**"3,192 — do we only do that with SOL?"** Not SOL, and SOL is not even close
to the deepest. That number is `ladder_total` on the SOL 09-23 04:59:57Z
signal — the **whole** order book up to 99.9c. Only **851** of it was at or
under our 98c ceiling, and above ~99c a contract loses money on average
whatever the model says. Across the record the usable share is a median 6.6%
of the headline number. BTC is 13x deeper than SOL: one BTC signal on 09-22
carried `ladder_total` 98,298 with **17,987** usable under our limit, and we
bought 18. The thin coins are **NEAR and BNB**, and those two are behind four
of our seven worst losses. **Most of any big ladder number is unreachable by
design, not by size.**

**"5 for 5 fully covered — what does that entail?"** Section 4. It means the
insurance bought the same number of contracts on the other side, so the
outcome becomes certain. **It does not get the bet back.** The two sides
together cost more than the $1.00 that one of them pays, so a fully covered
loss still costs 40-61c a contract on our own record — -$64.95, -$59.09,
-$43.92, -$34.26, -$31.27. The hedge recovers about a third. His instinct is
right.

**"Explain the drawdown — I'm not sure what I'm clearing."** The bot writes
down the highest the account has ever been: **$1,003.86** right now
(`results/pinrun-hwm.json`). If the balance falls **20%** below that — to
**$803.09** — the bot stops itself and says STOP AND LOOK. The mark only ever
moves **up**, so **what he "clears" is getting the balance back above
$1,003.86**; the moment it makes a new high the drawdown is zero again and the
bar moves up with it. Today the balance is **$1,002.27**, i.e. **$1.59** below
the high — a 0.16% drawdown, and the halt is **$199.18** of losses away. One
absolute-worst close today (-$249.90 bound) would trip it on its own; the
worst close we have actually had (-$108.86) would not. **At the 1.25x step the
halt sits 1.8 worst closes away instead of 2.2.** A deposit also raises the
mark and a withdrawal looks exactly like a loss to it, which is why
`classify_bank_move` inventing a $58.37 withdrawal once deadlocked the bot.

**"What's the doubt rule?"** `--doubt-mult`, shipped **OFF** (1.0 = identity,
so the live bot is byte for byte unchanged) and running at 1.5 on a paper arm
only. The rule: if at any moment at least 5 seconds earlier in the same close
the model put **under 50%** on the side we eventually buy, bet **1.5x** on it.
The evidence, on 784 settled markets: those "the model doubted it earlier"
markets made **+$2.95 each with 0 losers in 66**, against +$0.70 across all
markets and **-$0.70** for markets the model was sure about the whole time.
The story is that a late-arriving confidence means the market had not made its
mind up either, so the offer is cheap for an innocent reason. **It ships off
because 0 losers in 66 does not establish a zero** (the honest upper bound is
5.3% against a 2.44% base) and its significance is a marginal fail. One
doubt-boosted loss switches it off for the rest of the run. It can only ever
make an entry we were already making bigger — it can never refuse, delay,
reprice or touch a hedge.

---

## What I need from you

- **The 1.5x step: my answer is no**, because the worst close is the bet size
  and no setting separates them — it would put 37% of the bank at risk in one
  minute against the 25% you chose on 09-18. Do you accept that, or do you
  want it anyway?
- **The 1.25x step (bet 85 -> 106) is exactly undoing your 09-20 "make the bet
  a quarter smaller" call.** I would take it around **09-25 ET**, after the
  freeze finishes, and not before. Do you want it then, or do you want to let
  the bank do it by itself — which reaches the same 106 contracts at a
  $1,246 bank, about 3 good days away, with no extra risk at all?
- **Separate from size: cut the day stop from $200 to $135?** On 19 days it
  would only ever have fired on 09-19, and on that day it would have saved
  **$52**. It costs nothing on any day that never gets there. One day of
  evidence — your call.
