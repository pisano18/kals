# CROSS-VENUE — survey and pricing of everything outside Kalshi

Job run 2026-09-06, ~11:35-12:45 UTC. All calls read-only. No order placed, amended
or cancelled on any venue. No money moved.

---

## BOTTOM LINE

**There is a real, same-event, near-identical cross-venue overlap: Kalshi `KXBTC15M`
and Polymarket `btc-updown-15m`. It is the cleanest event-identity this project has
measured — 99.00% outcome agreement over 1,198 matched 15-minute windows. And the
operator, sitting on a US IP, cannot legally trade the other side of it.**

That is the whole finding in one sentence. The rest of this document is the evidence,
the five other venues I killed, and the one legally-reachable overlap I found instead
(Kalshi vs Polymarket **US**, daily high temperature), which is measured and is
**arbed out**: mean net edge **-2.53 cents**.

**Money found: none.** Not "none reachable" — none. The reachable overlap (weather) is
**negative after fees, mean -2.53c**. The unreachable one (crypto) is on a geoblocked
venue, and when I measured its price gap properly **the gap turned out to be my own
data going stale**, twice, in opposite directions. I have no trustworthy measurement
that a cross-venue price gap exists at all.

Three results here are worth keeping, and none of them is an arb:

1. **The event identity is real and precisely bounded.** 99.00% agreement on 1,198
   windows, and 100% of the disagreements sit in the 3.5% of windows that move less
   than $5. That is a genuine measurement and it took the largest sample in the job.
2. **Kalshi's REST `/markets` quote fields are stale by tens of seconds** — wrong by
   up to 17 cents, verified against Kalshi's own candlesticks. This is a hazard for any
   future live monitoring in this project and it is section 7.4.
3. **Polymarket US pays makers `0.0125*p*(1-p)` where Kalshi pays zero** — +0.31c per
   contract at 50c, unconditional, no market-is-wrong required. Section 6. This is the
   only thing in this document that could plausibly turn into money.

---

## 1. THE LEGAL WALL — read this before the numbers

There are two different Polymarkets and they are not the same product.

| | Polymarket **Global** | Polymarket **US** |
|---|---|---|
| entity | offshore, Polygon / USDC | QCX LLC, CFTC-designated DCM + DCO |
| US retail access | **geoblocked by IP** (2022 CFTC settlement condition) | legal, KYC'd, USD |
| KYC | none | gov ID + SSN + proof of residency + selfie |
| lists 15-min BTC up/down? | **YES** — this is the overlap | **NO** |
| shortest crypto market listed | 5 minutes | **36.8 hours** (measured, section 5) |

Every profitable-looking number in section 3 is on **Polymarket Global**. Its geoblock
is by IP; there is no KYC to fail, which is exactly why using a VPN is a
terms-of-service violation rather than an impossibility. I am not recommending that
and have not tested it.

The same wall killed the derivatives venues. Measured directly from this box:

```
Binance  eapi.binance.com/eapi/v1/exchangeInfo   -> HTTP 451
   "Service unavailable from a restricted location according to 'b. Eligibility'"
Bybit    api.bybit.com/v5/market/instruments-info -> HTTP 403
   "The Amazon CloudFront distribution is configured to block access from your country"
```

---

## 2. VENUE SURVEY — what is dead and why

| venue | sub-hour crypto? | US retail? | verdict |
|---|---|---|---|
| **Polymarket Global** | yes — 5m, 15m, hourly | **no, IP geoblocked** | real overlap, unreachable |
| **Polymarket US** | **no** (min 36.8h) | yes | no crypto overlap; weather overlap measured and dead (section 5) |
| **Deribit** | **no — nearest expiry 20.3h** | no (excludes US persons) | dead twice over |
| **Binance options** | n/a | **HTTP 451** | dead |
| **Bybit options** | n/a | **HTTP 403** | dead |
| **Robinhood predictions** | yes, BTC 15m | yes | **routes to Kalshi's own order book**, +$0.02/contract/side. Strictly worse than Kalshi. Not a second venue. |

### The options-replication idea is dead on contract structure, not on price

The job asked me to price a 15-minute binary as a replication built from short-dated
options. **It cannot be built.** Live from Deribit's public API:

```
nearest BTC option expiries: 2026-09-07 08:00 (+20.3h), 09-08 08:00 (+44.3h),
                             09-09, 09-10, 09-11, then weekly
median gap between the first 10 expiries: 168.0 h
```

Expiries are **daily at 08:00 UTC only**. A digital payoff needs a tight call spread
at the binary's own expiry. There is no intraday expiry on any accessible venue, so
for 95 of the 96 daily 15-minute windows there is no option to build the spread from.
A perp is linear delta and cannot replicate a digital — hedging a binary with a perp
converts it into a gamma/variance bet, not a lock. **This branch is closed. It is a
contract-listing fact, not a pricing result.**

Robinhood deserves one line of its own because it looks like a venue and is not:
orders placed there are routed to Kalshi's book and fill against the same liquidity,
with an extra $0.01 commission and $0.01 exchange fee per contract per side. There is
no price to arbitrage against, only a worse fee.

---

## 3. THE REAL OVERLAP — Kalshi KXBTC15M vs Polymarket btc-updown-15m

### 3.1 Do they resolve on the identical event? Almost — and I measured how "almost"

**Kalshi**, verbatim from `rules_primary` on the live market:

> "If the simple average of the sixty seconds of CF Benchmarks' BRTI before 7:45 AM
> EDT on Sep 6, 2026 **is at least** the simple average of the sixty seconds of CF
> Benchmarks' BRTI before 7:30 AM EDT on September 6, 2026, then the market resolves
> to Yes."

**Polymarket**, verbatim from the live market description:

> "This market will resolve to 'Up' if the **time-weighted average price (TWAP)** of
> Bitcoin, generated by Chainlink, of the time range specified in the title is
> **greater than or equal to** the price at the beginning of that range."

Source: `data.chain.link/streams/btc-usd-twap-60s-streams`. Polymarket moved these
markets from a snapshot price to a 60-second Chainlink TWAP in early August 2026;
before that change the two contracts were materially different.

| | Kalshi | Polymarket Global |
|---|---|---|
| window | quarter hour, e.g. 11:30-11:45 UTC | **identical** quarter hour |
| end reference | 60-second average | 60-second TWAP |
| start reference | 60-second average at window open | start of range (60s TWAP stream) |
| tie rule | "**is at least**" -> Yes | "**greater than or equal to**" -> Up |
| index | **CF Benchmarks BRTI** | **Chainlink BTC/USD TWAP** |
| tick | tapered (0.1c in tails, 1c mid) | flat 1c |
| min order | 1 contract | 5 shares |

Window boundaries align, averaging length aligns, **and the tie rule is identical** —
that last one usually breaks cross-venue pairs and here it does not. The only real
difference is the index.

### 3.2 The basis, measured exactly — 1,198 windows, no model

Rather than argue about wording I compared **realised outcomes**: Kalshi's settled
`result` from the local `fulltape` against Polymarket's `outcomePrices` from
`gamma-api`, for every matched window 2026-08-24 to 2026-09-06.

```
Kalshi settled windows              1198
Polymarket market missing              0
present but unresolved                 0
MATCHED, both resolved              1198
AGREE                               1186   99.00%
DISAGREE                              12    1.00%
   Kalshi Up / PM Down                10
   Kalshi Down / PM Up                 2
```

**And the disagreements are not scattered — they live entirely inside the near-ties:**

| \|settle - strike\| | windows | share | disagree rate |
|---|---|---|---|
| <= $2 | 13 | 1.1% | **46.15%** |
| <= $5 | 42 | 3.5% | **28.57%** |
| <= $10 | 93 | 7.8% | 12.90% |
| <= $20 | 214 | 17.9% | 5.61% |
| <= $50 | 472 | 39.4% | 2.54% |
| all | 1198 | 100% | 1.00% |

**All 12 disagreements had |settle - strike| <= $4.96.** Outside the $5 band the two
venues agreed **1,156 out of 1,156 times.** The median window moves $68.88, so the
BRTI-vs-Chainlink basis is bounded at roughly **$5 on an $80,000 underlying, about
0.006%.** These really are the same event except when the move is smaller than the
index disagreement.

**This is the honest answer to "arb or correlated bet with basis risk."** It is 99% an
arb and 1% a coin flip, and the 1% sits where the binary is near 50c at the close.

Live confirmation while writing this: the window closing 12:00:00Z resolved Down on
Polymarket (`["0","1"]`) and `no` on Kalshi; 11:45:00Z resolved Up and `yes`.

### 3.3 What the basis costs, per direction

A broken pair is a 100% loss of that pair's stake:

```
EV of $1 notional pair, long Kalshi YES + long PM Down : $1.00668   ( +0.668 c )
EV of $1 notional pair, long Kalshi NO  + long PM Up   : $0.99332   ( -0.668 c )
bootstrap 95% CI on the second (4,000 draws): [-1.252, -0.167] cents
```

The asymmetry rests on 10-of-12 disagreements falling one way. **Do not bank the
+0.67c** — it is 10 versus 2 events, binomial p = 0.039 two-sided, and it could flip.
**Budget the -0.67c**, because you will not know in advance which direction a gap will
point you.

Note carefully what this drag is and is not. It is not a fee and not a spread: it is
the price of the two indices disagreeing, and it is paid as a **total loss of the pair
roughly 1 window in 100**. Sized at S contracts, that is a -$1.00 x S event arriving
about once a day at 96 windows/day. Against a gross edge of a couple of cents that is
survivable in expectation but it is the fattest tail in the trade, and at a $1,000
account it is the thing that decides whether you can sit through the drawdown.

*An earlier draft of this section asserted that the observed price gap pointed at the
losing direction, and that the gap and the basis were the same phenomenon. Section 7
shows the observed gap was a data artefact. That assertion is withdrawn — I have no
trustworthy measurement of which direction the gap points.*

### 3.4 Both fee schedules

| | taker | maker | notes |
|---|---|---|---|
| **Kalshi** | `0.07*p*(1-p)` | **0** | 1.75c at p=0.50 |
| **Polymarket Global**, crypto | `0.07*p*(1-p)` | **0** | *identical curve to Kalshi.* 100% of taker fees redistributed to makers; docs state a 20% maker rebate |
| **Polymarket US** | `0.06*p*(1-p)` | **-0.0125*p*(1-p)** | **makers are PAID.** Confirmed on the market object itself: `feeCoefficient: 0.06`. Volume rebates 10/25/50% above $250k/$1M/$10M monthly taker volume |

Two things fall out of this table, and the second matters more than the arb:

1. **A cross-venue taker-taker pair at 50c must clear 3.5 cents of combined fees.**
   That is a wall. It is why every at-the-money gap I sampled is unprofitable and why
   the only net-positive observations sit in the tails, where `p(1-p)` collapses.
2. **Polymarket US pays makers `0.0125*p*(1-p)`, up to +0.31c per contract at 50c,
   where Kalshi pays zero.** Nothing cross-venue about it. See section 6.

### 3.5 The price gap — one measurement thrown away, one kept

**The measurement I threw away, and why.** I first paired 15,492 minute-observations
across 1,195 windows using Kalshi's public 1-minute candlesticks against Polymarket's
`clob.polymarket.com/prices-history`. It reported a mid-gap sd of 14.1 cents and a
"net edge" of +6.13c on 72.3% of minutes. **That is a bug, and it failed two checks:**

- *Algebra.* Over the two pair directions, `A + B = -(Kalshi spread) - (PM spread)`,
  so `max(A,B) === |gap| - 1c` identically. The statistic was not measuring an edge,
  it was measuring the mean absolute value of the gap noise. The reported `+8.641c`
  reconciles by hand against mean|gap| ~ 9.6c. A symmetric "edge" with mean +0.20c and
  sd 14c is noise wearing a maximum operator.
- *Direct check.* A simultaneous three-way snapshot showed `prices-history` **stuck at
  p=0.315 for 264 seconds** while the live CLOB book walked from 0.18/0.19 down to
  0.05/0.06. **`prices-history` returns Polymarket's LAST TRADE, not its mid.** The
  historical study compared Kalshi's live mid against Polymarket's stale last print.
  Discarded in full. Its file is retained only so the error is reproducible.

This is the fourth time in this project that a large edge turned out to be a
measurement artefact, and the pattern held: it looked best where the data was worst.

**The measurement I kept: simultaneous top-of-book on both venues**, Polymarket via
`clob.polymarket.com/book` and Kalshi via its public markets endpoint, both fetched
inside the same 0.24-1.25 seconds. Results in section 7.

### 3.6 Capital, and the constraint the operator asked me to test

The stated fear was "$500 a side, days to move money between venues."
**Measured, that is wrong about the trade cycle and right about the rebalance.**

*Round trip is fast on both sides:*

```
Polymarket: window closed  3.5 min ago -> already umaResolutionStatus = resolved
            (checked across 8 consecutive windows, all resolved)
Kalshi    : close 12:00:00Z -> expected_expiration 12:05:00Z, status = finalized
```

Capital frees **~3.5 minutes after close on Polymarket, ~5 minutes on Kalshi**. A pair
costs about **$1.00 total across the two venues** (the legs sum to 1 minus the gross
edge) and is held for at most 15 minutes. That is **~96 turns per day**, not days.
Peak concurrent capital is roughly `contracts x $1.00`, split across the venues in
whatever ratio the prices dictate.

*What is actually slow is rebalancing.* Each pair pays $1 on exactly one venue, so the
two balances random-walk apart. At S contracts per window over n windows the drift is
about `S * sqrt(n)` dollars. At S=10 and 96 windows/day that is **+/-$98 of drift per
day, +/-$259 per week**. Correcting it means an off-ramp from Polygon USDC to a US
bank to Kalshi: days, fees, and a taxable crossing. **At $1,000 total this is the
binding constraint, not the per-trade lockup.** A +/-$259/week drift against a ~$500
per-side float is survivable for roughly two weeks before a transfer is forced.

So the operator's honest constraint does not kill this on lockup. **It is killed by
the geoblock first, and the fee wall second.**

### 3.7 Latency and API access on the non-Kalshi side — measured from this box

```
Polymarket CLOB /book            median 158.1 ms   ** only 6 of 12 requests succeeded **
Polymarket US gateway /markets   median  79.0 ms   12/12
Kalshi REST /markets             median  81.0 ms   12/12   (repo: 30-36 ms on WebSocket)
Deribit public index             median 167.6 ms   10/10
```

**Polymarket Global's CLOB is ~2x Kalshi's REST latency and dropped half of a light
12-request burst.** For a trade whose entire thesis is "hedge the second leg before
the price moves", a venue that silently fails half a burst is a serious execution risk
independent of everything else above. Both sides are documented, free, REST plus
WebSocket. Polymarket order placement additionally needs an EIP-712 signature and a
funded Polygon wallet.

---

## 4. Capacity on the Polymarket side

```
Polymarket 15m BTC volume per market : median $26,110   mean $30,113   (n = 1,164)
Polymarket touch size, live book     : 25-334 shares per side, min order 5, tick 1c
Kalshi open interest, live 15m market: 30,667 - 185,505 contracts
```

Polymarket's 15m BTC book carries real depth — hundreds of shares at the touch and
~$26k of volume per 15-minute market. **Capacity is not the binding constraint here;
legality is.** Kalshi is the deeper venue; public trackers put the 15m crypto split
at roughly 88.5% Kalshi / 11.5% Polymarket.

---

## 5. THE LEGALLY-REACHABLE OVERLAP — Kalshi vs Polymarket US, daily high temperature

Polymarket US lists no short-dated crypto. Verified against its public gateway: 57
crypto markets, shortest **36.8 hours**, the rest monthly and yearly price milestones.
So I went looking for what it *does* list that Kalshi also lists. Both are CFTC DCMs,
both legal for US retail, both settle in USD.

**Same-day high-temperature markets, and the contracts line up almost perfectly:**

| | Kalshi | Polymarket US |
|---|---|---|
| ticker / slug | `KXHIGHNY-26SEP06-B75.5` | `tc-temp-nychigh-2026-09-06-gte75lt76f` |
| bucket label | "75 to 76" | "**75 to 76**" |
| station | CLINYC | **KNYC (Central Park)** |
| tick | 1c | 1c |
| taker fee | `0.07*p*(1-p)` | `0.06*p*(1-p)` |
| maker | 0 | **-0.0125*p*(1-p) (paid)** |

Buckets, boundaries and stations match on NYC (Central Park), Miami (KMIA), LAX (KLAX)
and Chicago (KMDW). Polymarket US lists a **subset** of Kalshi's ladder, 4-5 of
Kalshi's 6 buckets per city. The slug reads `gte75lt76f` but the market title and
description both say "75 to 76" / "between 75F and 76F", matching Kalshi's two-degree
bucket exactly — I checked this explicitly because getting it wrong would have made
every comparison below meaningless.

### The brutal part: the resolution sources are NOT the same

```
Kalshi        : "... according to The Weather Company"
Polymarket US : "... as reported by the National Weather Service's Climatological
                 Report (Daily). Outcome verified from NWS Climatological Report."
```

Same thermometer, **different publisher**. The Weather Company (IBM) and the NWS CLI
report can differ on a daily maximum through observation-window definition, rounding,
and preliminary-versus-corrected reports. On a two-degree bucket that only bites when
the max lands on a boundary — but it bites for the full stake when it does.
**This is a correlated bet with basis risk, not an arb.**

I could not measure its disagreement rate. Polymarket US launched December 2025 and I
have no settled paired history for it, unlike the 1,198 crypto windows. **That is an
unmeasured risk, not a small one.**

### And it does not matter, because it is already arbed out

I ran a paired sampler for ~35 minutes, 12 aligned buckets per sweep across 5 cities,
**107 comparable simultaneous observations**:

```
GROSS best-direction cross-venue edge : mean -0.92c   median -1.00c   max +2.00c
NET of Kalshi 0.07 + PM-US 0.06 taker : mean -2.53c   median -2.24c   max +0.72c
observations with a positive net lock : 11 / 107  = 10.3%
observations with a positive gross gap: 12 / 107  = 11.2%
```

The best net lock anywhere in that sample was **+0.72 cents**, on a NYC 77-78 bucket,
on a contract that does not settle for ~14 hours. And the identical +2.0c gross gap
reappeared on the *same* bucket across consecutive sweeps, so it is **one standing
quote nobody is lifting**, not a stream of opportunities — which usually means it is
not liftable at size, or that the source basis is exactly why nobody wants it.

**Verdict: dead as a taker arb.** Peak capital ~$1.00/contract locked ~14 hours for at
best 0.7c, which is **~1.2c per contract per day**, available in 10% of snapshots on
one bucket, before any basis loss. At the operator's $1,000 that is a theoretical
ceiling of well under a dollar a day even if every snapshot were fillable at size, and
it is not.

**Is this result contaminated by the Kalshi REST staleness of section 7.1?** Checked,
and no. Over the 35-minute sample the Kalshi `yes_bid` on these markets moved a
**median of 1 cent (mean 2.1c, max 7c) per series**, because a daily-high-temperature
market with 14 hours to run barely moves. A quote feed lagging by tens of seconds
cannot manufacture or conceal a multi-cent gap in a market that static. Additionally
the finding here is **negative**, and staleness on a near-static market would tend to
create spurious positives rather than hide real ones. The conclusion stands.

---

## 6. THE ONE THING WORTH MORE THAN THE ARB

**Polymarket US pays makers. Kalshi does not.**

```
Polymarket US maker fee coefficient : -0.0125  ->  maker is PAID 0.0125*p*(1-p)
                                                   = +0.31c per contract at p = 0.50
Kalshi maker fee                    :  0       ->  paid nothing
```

The repo's live result `informed.py` measures Kalshi at-touch market-making at
**+0.48c per fill, t = +6.4** on 17.1M fills, with takers at the touch carrying zero
information. The identical strategy on a venue that adds **+0.31c per contract of
unconditional rebate** is worth **+65% more per fill at the money**, from the fee
schedule alone, with no requirement that the market be wrong about anything.

Polymarket US also charges takers `0.06` against Kalshi's `0.07`, so the venue is
cheaper on both sides of the book.

**This is not measured here and I am not claiming it.** It is a lead, and it is the
cheapest one this job produced, because it reuses an estimator that already exists and
already passed its self-test. What is unknown and decisive: **whether Polymarket US's
books are deep enough to receive fills at all.** 327 of 500 live markets were
two-sided, but spreads ran from 0.1c (`0.110 / 0.111`) to 33c (`0.039 / 0.368`) —
wildly uneven, which is what a young venue looks like. There is also no crypto there,
so this would be market-making in sports, politics, culture and weather, which is a
different flow problem from the one `informed.py` was calibrated on.

---

## 7. LIVE SIMULTANEOUS BOOK SAMPLE — Kalshi vs Polymarket Global, 15m BTC

Sampler: both books fetched within the same 0.24-1.25 s, every ~14 s, top of book
only. This is the only price-gap number in this document I trust.

```
simultaneous paired snapshots : 29      distinct 15-min windows : 1
SIMULTANEOUS MID GAP (Kalshi P(Up) mid - Polymarket P(Up) mid), cents
  mean +0.79   median -1.00   sd 6.22   min -6.0   max +19.0
BEST-DIRECTION TAKER-TAKER LOCK, cents
  GROSS: mean +3.17  median +1.00  max +18.00   positive 69.0%
  NET  : mean -0.20  median -2.02  max +14.70   positive 27.6%
Polymarket touch size (min of bid/ask): median 64 shares, p10 26, p90 180
```

**Do not use these numbers. They are an artefact and I found the cause.**

### 7.1 THE ARTEFACT — Kalshi's REST `/markets` endpoint serves stale quotes

The raw tape shows the whole story in six rows:

```
utc        tau  KALSHI bid/ask   PM bid/ask     gap
12:05:18   582  0.510/0.520      0.55/0.56      -4.0c
12:05:33   567  0.510/0.520      0.35/0.36     +16.0c
12:05:47   553  0.510/0.520      0.37/0.38     +14.0c
12:06:01   539  0.510/0.520      0.32/0.33     +19.0c
12:06:16   524  0.380/0.390      0.29/0.30      +9.0c
12:06:44   496  0.320/0.330      0.30/0.31      +2.0c
```

Polymarket fell 20 cents in 15 seconds. Kalshi's REST quote sat at `0.510/0.520`
for 43 seconds and then jumped 13 cents in one step. A live book does not jump 13
cents in one step; it walks. So I checked Kalshi against **Kalshi's own 1-minute
candlesticks**, which are built from the real book:

```
minute ending 12:06:00   yes_bid o/h/l/c = 0.49 / 0.51 / 0.31 / 0.33
                         yes_ask o/h/l/c = 0.50 / 0.52 / 0.32 / 0.34
```

**Kalshi's book traded down to 0.31/0.32 inside the very minute my REST snapshots
were reporting 0.510/0.520.** Scored across every snapshot:

```
REST snapshots checked against Kalshi's own 1-min candlestick bid range : 45
snapshots whose REST bid was OUTSIDE the true range for that minute     : 8 (17.8%)
when outside: error mean 7.3c, median 7.0c, MAX 17.0c
```

The 17.8% is a **floor**, not an estimate: a minute whose true bid ranged over
[0.31, 0.51] cannot detect a 30-second lag inside it. The test only catches snapshots
so stale they fall outside a whole minute's range. An interim scoring at n=34 gave
8.8%; extending to n=45 doubled it, so the figure is still rising with sample and
should be treated as a lower bound on both frequency and size.

### 7.2 What this reverses

**There is no measured cross-venue price gap on 15-minute BTC.** Every large gap in
the sample appears exactly in the fast-moving moments where the staleness is largest,
and decays to ~0-2c within a minute once Kalshi's feed catches up. That is the
signature of a lagging data source, not of two venues disagreeing.

It also retracts the one encouraging-looking result from earlier in this job: a run of
eight consecutive snapshots showing "Kalshi rich by +3 to +7 cents". That window was
falling fast (0.22 down to 0.088 in three minutes), which is precisely the condition
under which a stale Kalshi quote reads high. **I withdraw it.**

Combined with section 3.5, the honest position is: **the historical gap study is
invalid (Polymarket last-trade), and the live gap study is invalid (Kalshi REST
staleness). I have no trustworthy measurement of the Kalshi/Polymarket price gap, and
the two failures point in opposite directions, so I cannot even sign it.**

### 7.3 The one number that survives, and it is a warning not an edge

The fee wall is arithmetic and does not depend on any of the above. Combined taker
fees are `0.07*p*(1-p)` on each side: **3.5 cents at the money, ~1.3 cents at
10c/90c.** Any cross-venue pair near 50c needs a gap wider than 3.5c before the basis
drag of section 3.3 is even considered. Nothing I trust shows a gap that wide.

### 7.4 A finding for the rest of the project, not just this job

**Kalshi's REST `/markets` quote fields (`yes_bid_dollars`, `yes_ask_dollars`) are
stale by tens of seconds and were wrong by up to 17 cents in a 30-sample window.**

- The repo's stages read the **WebSocket tape** in `kalshi_data/`, which is a different
  path and is not implicated here.
- But any future work that reaches for the REST market endpoint to get a quote — a
  live monitor, a dashboard, an execution sanity check, a pre-trade guard — will be
  reading numbers that are wrong exactly when the market is moving, which is exactly
  when it matters.
- **Kalshi's `/candlesticks` endpoint appears sound** and is the cheap public
  alternative: it gave open/high/low/close of both `yes_bid` and `yes_ask` per minute
  and is what exposed the staleness.

This did not cost this job anything except the crypto gap number, and it is worth more
than that number would have been.

---

## 8. WHAT I COULD NOT DO

- **No settled paired history for Polymarket US.** The weather basis risk (The Weather
  Company vs NWS CLI) is therefore **unmeasured**. It is the single biggest unknown in
  section 5 and it is the reason I will not call that overlap "small basis" even
  though the crypto one demonstrably is.
- **I have no valid cross-venue price gap measurement for crypto, in either
  direction.** The historical series is Polymarket's last trade (section 3.5); the
  live series is Kalshi's stale REST quote (section 7.1). A correct measurement needs
  a sampler that reads **Kalshi's WebSocket tape** (which the collector is already
  writing) against **Polymarket's CLOB book**, forward-collected. That is buildable
  from what exists but I did not build it, because the geoblock makes the answer
  unactionable anyway.
- **n = 1 window on the live crypto sampler.** 29 snapshots inside a single 15-minute
  market. Even without the staleness bug that would not have been a distribution.
- **Polymarket Global order-book depth beyond the touch** was not walked. I have top
  of book and displayed size only.
- **I did not test whether the gaps are liftable.** Everything here is quote-based. A
  displayed 25-share bid is not a promise.
- **Binance and Bybit could not be surveyed at all** — HTTP 451 and 403 from this IP.
  I cannot say what their products look like, only that they are unreachable.
- **Sports overlap was not priced.** Polymarket US lists 426 live sports markets and
  Kalshi lists the same leagues; a game result is a genuinely identical event with no
  index basis at all. I ran out of time to build the ticker mapping. **This is the
  most promising unexplored branch in this document** and it is strictly better than
  weather on event identity.

---

## 8b. EVERYTHING IN THE OPERATOR'S UNITS

Reported as $ per contract per day, peak concurrent capital, and % return on capital
deployed — not as $/day at an assumed 50 contracts.

### The one reachable trade: Kalshi vs Polymarket US weather

| | |
|---|---|
| best net edge observed | **+0.72c per contract** (one bucket, NYC 77-78) |
| peak concurrent capital | **$1.00 per contract** (the two legs sum to ~$1.00) |
| holding period | **~14 hours** (entry to next-morning settlement) |
| **$ per contract per day** | **+1.24c** |
| **% return on capital deployed** | **0.72% per turn, ~1.24% per day** |
| availability | **10.3% of snapshots**, and repeatedly on the *same* bucket |
| mean across all snapshots | **-2.53c**, i.e. the typical state is a loss |

At $1,000 of capital that is a ceiling of ~$12/day **if** 1,000 contracts were
fillable at the best price seen, which they are not — this was one standing quote on
one bucket that nobody was lifting. The realistic figure is a few contracts, so **a
few cents a day**, before the unmeasured Weather-Company-vs-NWS basis risk. **Dead.**

### The unreachable trade: Kalshi vs Polymarket Global 15m BTC

I cannot quote a $/contract/day because I have no valid gap measurement. What I can
quote is **the bar any gap would have to clear**, which is arithmetic:

```
net per pair (cents) = G - 7.0*p*(1-p)*2 - 0.67
                         \___fee wall___/   \basis drag/
   at p = 0.50 :  need G > 4.2c just to break even
   at p = 0.25 :  need G > 3.3c
   at p = 0.10 :  need G > 1.9c
```

| | |
|---|---|
| peak concurrent capital | **$1.00 per contract**, split across two venues |
| holding period | **<= 15 minutes**; free ~3.5 min (PM) / ~5 min (Kalshi) after close |
| turns per day | **~96** |
| % return per turn, if a 2c net edge existed | **2.0%** |
| $ per contract per day, same assumption | **+$1.92** |
| rebalancing drift at S=10 contracts | **+/-$98/day, +/-$259/week**, days to correct |

The capital efficiency is genuinely excellent — 96 turns a day on $1.00 per contract
is the best cycle in anything this project has looked at. **That is what makes the
geoblock expensive rather than merely annoying.** But note the last row: at $1,000
split $500/$500, a +/-$259 weekly drift forces a cross-venue transfer roughly
fortnightly, and each transfer is days of Polygon-USDC-to-bank-to-Kalshi friction plus
a taxable crossing. Even with a legal path, **$1,000 is around the smallest account
this could work in, and the drift is the binding constraint — not the per-trade
lockup, which the operator's stated fear had backwards.**

---

## 9. THE SINGLE CHEAPEST NEXT ACTION

**Price the Kalshi vs Polymarket US same-day SPORTS overlap.**

Reasons, in order:

1. It is the only overlap that is simultaneously **legal for US retail**, **settles the
   same day** (capital free in hours, not months), and has **zero index basis** — a
   game result is a game result, so the entire "is it the identical event" problem
   that killed crypto and weakens weather simply does not exist.
2. Polymarket US charges `0.06` taker against Kalshi's `0.07` and **pays makers
   `0.0125*p*(1-p)`**, so the fee wall is ~0.4c lower per pair than the crypto case
   and turns negative if either leg rests.
3. It reuses everything built today: the paired sampler in
   `xvenue/wx_sampler.py` needs only a new ticker map.

Cost: a few hours, entirely read-only, no new infrastructure.

**Do not spend more time on the Kalshi/Polymarket-Global crypto arb.** The event
identity is beautiful, the numbers are interesting, and the operator cannot legally
take the trade. Recording that clearly is the result.

---

## Resource protocol

```
Free disk    : 53 GB on C: at start AND at finish (880 GB total, 95% used)
Free RAM     : 2.84 GB at start -> 3.63 GB mid-run -> 3.23 GB at finish
kalshi_collector.py : ALIVE at start, mid-run and at finish (pid 2708908, 25-26 MB)
crypto_feeds.py     : ALIVE at start, mid-run and at finish (pid  531268, 14 MB)
```

This job's own processes peaked at 58 MB. **`replay.load_quotes` was never called.**
`depth_map.pkl` was loaded, read for KXBTC15M coverage, and released. Nothing under
`kalshi_data/`, `feed_data/` or `fulltape/` was written to; all three were read only.

My two samplers were stopped at the end with a `*xsample*`/`*wx_sampler*` command-line
filter, never a broad `python.exe` kill, and both collectors were re-verified alive
afterwards. Their tasks report exit 127 — that is my own deliberate `Stop-Process`,
not a crash.

Samples collected before shutdown: **48** simultaneous crypto book snapshots, **216**
paired weather quotes.

## Artefacts

All under `C:\Users\Joe\AppData\Local\Temp\kals-work\xvenue\`:

| file | contents |
|---|---|
| `pm_outcomes.json` | Polymarket resolved outcome for all 1,198 matched windows |
| `kalshi_candles.json` | Kalshi 1-min candlesticks, 1,198 windows |
| `pm_hist.json` | Polymarket price history — **known bad, last-trade not mid** |
| `gap_rows.json` | 15,492 rows of the discarded study, kept for reproducibility |
| `xsamples.jsonl` | simultaneous Kalshi/Polymarket-Global top of book |
| `wx_samples.jsonl` | paired Kalshi/Polymarket-US weather quotes |
| `agree.py`, `fetch_quotes.py`, `gap.py`, `xsample.py`, `xan.py`, `wx_sampler.py`, `sim_snap.py` | the scripts, all read-only |
