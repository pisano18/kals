# B_attack — adversarial audit of the 1.5x size step

**2026-09-23. Label `attack`.** My own parse of `results/pinrun-live-*.jsonl`
(129 runs, 33,328 records) joined to `results/kalshi_ledger.json` and to
Kalshi's settlements in `C:\kals\fulltape\markets.json`. **Nothing here comes
from the replay, `pindata` or `pinsim`.** Scripts: scratchpad `size15\attack\`
(`build.py`, `pair.py`, `a2.py`, `b_flight.py`, `c_worst.py`, `sim15.py`,
`d2.py`, `e_loo.py`, `f_asym.py`, `g_final.py`, `h_hedge.py`).

Collectors checked at the end: `kalshi_collector.py` pid 105304 (54 MB) and
`crypto_feeds.py` pid 105352 (42 MB) both alive. Free disk 19 GB (guard 6 GB).
Free RAM 1.05 GB — everything streamed, no `load_quotes`.

My population: **800 markets, 586 closes, 16 ET days**, every market with a
fill and a Kalshi ledger row. 485 of them (2026-09-14 onward) carry a logged
`ladder` and are the only ones that can be re-sized at all.

---

## VERDICT

**The operator's condition is not met, and it cannot be met by any
configuration.** The worst close is set by SIZE on a *single market*, so it
moves with SIZE one-for-one. Everything else — the close budget, the depth cap,
a per-coin step — leaves it alone.

| | 1x today | 1.5x (my model) |
|---|---|---|
| total, 800 markets / 586 closes / 16 days | **+$565.87** | **+$654.14** |
| delta | | **+$88.28 = +$5.52 a day** |
| worst single close | **-$108.86** | **-$160.39** (47% worse) |
| 2nd worst | -$107.95 | -$159.77 |
| most dollars committed in one close (Kalshi ledger, incl. insurance) | **$316.86** | **$460.80** |
| that against the $584.46 he has put in | 54% | **79%** |
| hard bound, all 3 legs lose at 98c, no insurance | $250.57 | **$375.38** |
| odds the 1.5x version makes LESS over a stretch like this one | — | **1 in 4** |

**The extra money and the worse worst-close are the same quantity.** 67% of our
closes hold one market and the median close uses 54 of its 256-contract budget,
so nothing between SIZE and the close is binding. I tested capping a close's
total contracts at today's number: the worst close barely moves (-$159.77), and
capping per market at today's SIZE removes the entire gain. There is no version
of this that gets the upside and leaves the downside where it is.

**A named modification does exist and it is smaller: `--bank-brake 4.00 -> 3.20`
(a 1.25x step).** +$49.25 over the same 16 days, worst close -$135.02, hard
bound $300. It is the largest step that keeps the worst close under -$150 and
the one-close bound under half of what he has put in. If the answer must be yes
or no on 1.5x, it is **no, not yet** — for the hedge reason in section 7, which
is a bug-shaped risk, not a preference.

---

## 1. The logged ladder is not an offer — it is a ~100 ms-old photograph, and on two losing markets it was almost entirely phantom

Both re-derivations price the 1.5x extra contracts off `signal.ladder`. That is
one book read (`book_age_ms` median 8, p90 54, max 447) and the order then flies
for a median **94 ms** (p90 136, p99 372, max 1,364).

**Case 1 — `KXBNB15M-26SEP191230-30`, 16:29:37Z, lost -$61.75.**

| | |
|---|---|
| `ladder_under` (contracts at/under our 98c limit) | **11,937.1** |
| of which 2,462 @ 94.8c, 3,122 @ 95.9c, 6,095 @ 97.9c | |
| asked | 171 |
| **filled** | **82.8 (48%)** |
| ladder-implied price for 82.8 contracts | ~93.1c |
| **actually paid** | **97.27c — 4.2c worse** |
| next book read, ~0.4 s later | `ladder_under` **35.0** |

A_rederive calls this market "genuinely depth-limited". The log says the
opposite: the depth was *recorded* and then evaporated in flight. 99.3% of it
was not there.

**Case 2 — `KXDOGE15M-26SEP222245-45`, 02:44:48Z (10:44 PM ET 09-22).** The
signal's ladder held **6,195.4** contracts at/under the limit. The bot's own
`sweep_depth` record, written in the same tick, said **82.0**. It asked 82 and
**filled 0**.

Two book reads in one second disagreeing by 75x, and the resulting order
filling none of it, is not a rounding error in the source both papers use to
cap the extra contracts.

**Why this matters specifically for 1.5x:** both papers validate the ladder on
the rungs we actually reached (median price error +0.000c, and I reproduce
that — shallow asks median +0.000c, deep asks +0.010c). The 1.5x extra
contracts come from rungs we have **never** reached, and these two cases are
the only direct observations we have of what is up there.

## 2. Fill quality falls as the order eats more of the book, and 1.5x moves every order up that curve

518 fills with a logged ladder.

| the ask, as a share of the ladder at/under our limit | n | full fill | contracts delivered |
|---|---|---|---|
| 0–25% | 260 | 97.3% | 98.4% |
| 25–50% | 94 | 93.6% | 96.0% |
| 50–75% | 45 | **75.6%** | **85.7%** |
| 75–100% | 98 | **68.4%** | **86.4%** |

A_rederive fills the extra contracts "at the same rate that order actually
achieved". That rate is not a constant — it is a falling function of exactly
the thing 1.5x raises. Applying the measured rate for each order's *new*
utilisation costs ~$5 of the gain; a further 20% haircut on the extra
contracts costs $18 more (+$88.28 -> +$70.62). Not fatal, but the gain is
quoted from the top of its range.

## 3. The load-bearing claim in C_decide is backwards: the losses are where the depth IS

Headroom = ladder at/under our limit / contracts asked. 485 markets, 470 win,
15 lose.

| | n | p25 | median | p75 | can take the full 1.5x |
|---|---|---|---|---|---|
| winners | 470 | 1.61x | 4.08x | 12.38x | **76.2%** |
| **losers** | **15** | **2.03x** | **5.28x** | **53.38x** | **80.0%** |

Twelve worst losses and whether the offer allowed a bigger bet:

| market | loss | asked | filled | ladder <= limit | 1.5x possible |
|---|---|---|---|---|---|
| BTC 09-19 16:00Z | -$107.95 | 110 | 110 | 482 | YES 4.4x |
| BTC 09-19 02:00Z | -$66.34 | 70 | 70 | 48,604 | YES 694x |
| XRP 09-19 23:45Z | -$64.95 | 104 | 104 | 549 | YES 5.3x |
| BNB 09-19 12:30Z | -$61.75 | 206 | 84.5 | 11,937 | YES on paper 58x |
| NEAR 09-21 12:45Z | -$59.09 | 81 | 81 | 317 | YES 3.9x |
| BNB 09-19 01:45Z | -$57.76 | 76 | 76 | 11,761 | YES 155x |
| HYPE 09-19 23:45Z | -$43.92 | 104 | 104 | 227 | YES 2.2x |
| BTC 09-14 05:30Z | -$34.26 | 60 | 60 | 676 | YES 11.3x |
| HYPE 09-21 18:15Z | -$31.27 | 55 | 55 | 55 | **NO 1.0x** |
| HYPE 09-14 16:00Z | -$29.90 | 62 | 62 | 2,139 | YES 34.5x |
| BTC 09-17 21:15Z | -$27.87 | 99 | 99 | 4,925 | YES 49.8x |
| DOGE 09-16 09:00Z | -$12.14 | 87 | 87 | 164 | YES 1.9x |

**One of our twelve worst losses was protected by thin supply. Eleven were
not.** C_decide's "all four biggest losses are in the half size cannot reach"
is false against our own records, and it is the sentence the whole
"+63% for +13% worse" table rests on.

## 4. The population that holds every loss dollar is the one 1.5x scales hardest

Split the 518 fills by what the fill did against the ask we were quoted:

| bucket | fills | markets | P&L (ledger) | losing mkts | median headroom | extra allowed at 1.5x |
|---|---|---|---|---|---|---|
| **came back >= 2c CHEAPER** | 17 | 16 | **-$115.05** | **5** | 5.84x | **+47.5%** |
| cheaper 0.5–2c | 16 | 16 | +$6.51 | 1 | 17.41x | +48.2% |
| as quoted | 383 | 364 | +$248.95 | 9 | 3.65x | +42.3% |
| dearer (we swept up) | 102 | 100 | +$218.20 | 1 | 6.39x | +45.6% |

The cheap bucket **filled 100% of what it asked** — a collapsing book hands us
*more*, not less — it is the only negative bucket, and the ladder allows **more**
extra there than anywhere else. The depth cap is doing its protecting in the
wrong half of the record.

## 5. The close budget is scale-invariant — both papers got this wrong, and it helps the case for the step

`close_budget` compares **contracts** spent against `MAX_PER_CLOSE x SIZE`.
Multiply SIZE by 1.5 and the budget, the spend and the new ask all multiply by
1.5, so the same markets are refused. Measured on all **489** `close_budget`
refusals (73 closes):

- Testing with `spent` left at 1x (what A_rederive's "54 of 69 would now pass"
  does): **476 of 489 pass = 97%**.
- Testing with `spent` scaled by the multiple that close actually realises
  (median 1.48x; the closes behind a budget refusal are deep ones): **0 of 489
  pass.**
- The refused market is never marginal: `(spent + size_now) / budget` has a
  median of **1.50** and a minimum of 1.33.

So 1.5x adds **no** new markets and **no** new correlated concentration.
C_decide's worry 3 and A_rederive's "+24 closes" are both artefacts. What does
grow is dollars per close, exactly 1.5x, which is section 6.

## 6. The gain rests on three days, and a quarter of the time it is not a gain

| ET day | mkts | losing | 1x | 1.5x | delta |
|---|---|---|---|---|---|
| 09-08 .. 09-13 | 307 | 11 | +$162.46 | +$162.46 | $0 (no ladder logged) |
| 09-14 | 61 | 2 | +$81.10 | +$91.62 | +$10.52 |
| 09-15 | 36 | 0 | +$77.97 | +$112.89 | +$34.92 |
| 09-16 | 45 | 3 | +$85.21 | +$114.68 | +$29.46 |
| 09-17 | 54 | 1 | +$98.12 | +$112.12 | +$14.00 |
| 09-18 | 68 | 0 | +$91.85 | +$118.24 | +$26.40 |
| **09-19** | 73 | 6 | **-$223.46** | **-$347.52** | **-$124.05** |
| 09-20 | 55 | 0 | +$112.65 | +$161.79 | +$49.14 |
| 09-21 | 46 | 2 | -$5.99 | -$4.57 | +$1.43 |
| 09-22 | 35 | 1 | +$54.26 | +$86.23 | +$31.97 |
| 09-23 | 20 | 0 | +$31.69 | +$46.20 | +$14.50 |

Leave one ET day out and the delta runs from **+$39.14** (drop 09-20) to
**+$212.33** (drop 09-19). **The single best day is 56% of the whole delta;
the best three are 131% of it** — the other thirteen days are net negative
together.

Cluster bootstrap, B=4,000:

- resampling **closes** (n=586): +$88.28, 95% [-$141.27, +$288.49], negative in
  **18.8%** of draws.
- resampling **ET days** (n=16), which is the right cluster because the market
  regime is a day-level thing: +$88.28, 95% [-$236.11, +$312.85], negative in
  **25.5%** of draws.

**One stretch in four like this one, 1.5x makes less money than 1x.** A_rederive
quotes 10.8%; the difference is entirely the clustering unit, and the day is the
honest one — 09-19 was one day and it is 56% of our lifetime loss dollars.

## 7. What actually binds: the insurance, independently re-measured

This is the one place where 1.5x is not a preference but a fault.

- Hedge orders with a real ask: **37**. Short of what they asked: **12 = 32%**.
  Contracts asked **1,321**, filled **953 = 72.1%**. Short at least once in
  **6 of the 19 markets** a hedge ever fired on.
- The other side's book while we were exposed (`hedge_quote`, n=1,428, median
  199, p25 38):

| cover needed | share of exposed seconds the book could supply it |
|---|---|
| 85 (one market today) | 64.4% |
| **128 (one market at 1.5x)** | **56.5%** |
| 190 (one late-boosted market at 1.5x) | 51.1% |
| 256 (a whole close today) | 44.7% |

A 1.5x position with a 1x hedge is a 1.5x naked loss, and that is exactly the
09-19 shape. `--late-tau 10 --late-mult 1.5` is live, so one order inside the
last ten seconds may already reach 1.5x SIZE — 128 contracts today, **190** at
the step, on a single market.

`--loss-cap 200` is fixed dollars and does not scale: at 1.5x one worst close
(-$160) leaves $40 of the day. If the step is taken it has to come down with it.

## 8. The basket, measured on Kalshi's own settlements

2,202 closes where all nine coins settled:

- **55.3%** had **8 or more of 9** settle the same way. Independent coins would
  give 3.9%.
- **33.3%** had **all nine** settle the same way.
- 09-11 16:30Z (12:30 PM ET): 7 no, 2 yes — real, but unremarkable against that
  base rate. We held one market there (XRP) and won +$0.42, plus ETH at 16:45Z
  +$0.43. It has never touched our money and does not at 1.5x.

The coins are one asset at this horizon. That does not make our bets fail
together — we only buy after most of the settlement is locked, and in 586
closes we have had 24 with one loser and exactly one with two. But it means the
number to govern is **dollars assembled in one close**, and that number is
$316.86 today and $460.80 at the step.

## 9. Refuted, including one of A_rederive's own recommendations

- **"Take the step per coin — BTC, ETH and XRP only, where the book is deep."**
  Backwards on the ledger. **BTC is our single worst loss coin (-$237.52 of loss
  dollars over 139 markets, more than any other) and it has the deepest book**,
  so a depth-targeted step scales our biggest losses hardest. Measured:
  BTC+ETH+XRP+SOL only gives **+$50.95** (58% of the gain) and the worst close
  still goes to **-$159.77** (all of the damage — the 2nd-worst close is BTC
  alone). **BTC+ETH only is -$11.40: worse than not stepping at all.**
- **"The close budget grows and adds markets."** No — section 5.
- **"The four biggest losses are where size cannot reach."** No — section 3.
- **A close-contract cap saves the worst close.** No: capping a close at today's
  256 contracts leaves the worst close at -$159.77, because the worst closes use
  110 and 208 contracts, far under the cap. 67% of closes hold one market; the
  median close uses 54 of 256.

## 10. Could not measure

- **315 of 800 markets (everything before 2026-09-14) have no logged ladder**
  and get no extra contracts in my model at all. My delta is therefore an
  under-estimate of both the gain and the harm on those days.
- **Whether the deep rungs exist.** Two observations, both phantom, both on
  losing markets. That is the whole evidence base for the rungs 1.5x would buy.
- **What the insurance book does at 1.5x demand.** `hedge_quote` is the ask at
  the touch, not a ladder; I cannot price walking it.
- **The 476 markets a bigger budget would admit** — 138 have a ledger row from
  another close, 338 were never held and have no outcome. Moot after section 5.

## 11. What I would do instead

1. **Take 1.25x, not 1.5x** (`--bank-brake 4.00 -> 3.20`, size 85 -> 106).
   +$49.25 on this record, worst close **-$135.02**, one-close bound **$300**
   (51% of what he has put in, against 64% at 1.5x). Blocks nothing, gates
   nothing, cannot touch a hedge. Validate on live fills: 150 closes, bar
   written first — cents per contract no worse than live and no close committing
   more than $320.
2. **Fix the hedge's reach before the position grows** (section 7). Log the
   ask-side ladder at the alarm second, not just the touch. Blocks nothing.
3. **Cut `--loss-cap` with any step** — 200 -> 160 at 1.25x, 135 at 1.5x — so
   the day-stop still needs two bad closes, not one.
4. **Put "dollars committed in this close" on the desktop app.** It is the only
   number that governs the tail, and it does not exist today.
5. **Log a second book read at order-response time.** Two of our loss markets
   show the ladder evaporating inside 100 ms and we only know because the sweep
   happened to disagree with the signal in the same tick. Blocks nothing.

---

## Does the operator's condition hold?

**No — and it cannot be made to hold at 1.5x by any modification.** "Worst close
genuinely unchanged" and "more money" are the same quantity here: our worst
closes are single-market or two-market closes using a fifth to a half of the
close budget, so only SIZE sets them, and SIZE is what the step raises. Worst
close -$108.86 -> -$160.39; one-close commitment $316.86 -> $460.80 (79% of the
$584.46 he has put in); hard bound $250.57 -> $375.38.

**Only with a named modification: take 1.25x instead** (`--bank-brake 3.20`),
**cut `--loss-cap` to 160 at the same time, and fix the hedge's reach first.**
That buys +$49 of the +$88 on this record, holds the worst close to -$135 and
the one-close bound to $300, and leaves the one genuine fault — a 1.5x position
the insurance book can only cover 56.5% of the time — out of the trade.
