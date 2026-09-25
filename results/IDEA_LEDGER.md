# IDEA_LEDGER -- every money idea ever checked, one row each, never deleted

**Read this before proposing anything new.** Every money-idea sweep
(`research/sweep/README.md`) reads it first and updates it last. A dead idea
stays here so nobody re-proposes it; it can come back only with a genuinely new
angle, stated in its new row.

Status: **live** (trading real money) · **testing** (paper arm / watcher /
1-contract test running) · **viable** (survived a check and a refutation, not
yet tested) · **needs-data** · **dead**. Money is Kalshi's books; $/day is the
realistic figure at the bank of the time, never the tape's.

Started 2026-09-25 from IDEAS_2026-09-24.md, SECOND_INCOME_SCAN_2026-09-25.md,
FAR_RUNG_2026-09-25.md and MAKER_SIM_2026-09-24.md. The 2026-09-25 multi-agent
sweep (`results/IDEA_SWEEP_2026-09-25.md`) adds its rows below when it lands.

---

## HOT AREAS -- where the next sweep should look first

- **Kalshi liquidity rewards (sweep 2026-09-25 #1)** -- Kalshi pays daily pots to
  resting orders; 7 reward ideas hinge on ONE unproven fact: does Kalshi pay THIS
  account. Test: 2-4 resting 1c orders on quiet reward markets, <= ~$60 at risk,
  answer in 2-3 days (needs the operator's yes; placing orders is his call).
- **Does pinrun's profit grow with bet size?** Unmeasured; if extra contracts earn
  little, several ideas cut for 'displacing pinrun's cash' come back.

- **Polymarket US BTC 15-min / 1-h** -- the same contract as our live market on a
  second book; operator funded (~$60) and eligible. Real-time recorder running
  to ~2026-09-28 (see UNRESOLVED U1). Questions: pin supply there; maker rebate +
  hedge on Kalshi; cross-book gaps.
- **Hourly crypto ladders, all seven coins** -- paper arm `arm-hourly-all` since
  2026-09-25 03:06Z; hourly BTC live at 1 contract since 2026-09-24. The only
  place more bank buys more contracts (books ~30x deeper than 15-min).
- **Sports** -- 66M contracts/day, 1,121 series, barely examined before this
  sweep; ESPN's API is blocked from this box, other league feeds are not.
- **Parlay / combination markets** -- crypto-combo pricing vs our legs
  CHECKED 2026-09-25 (D27): no gain for our strategy; sports/other combos
  still unexamined.
- **Loss hedges for the live bot** -- the operator's #1 priority is lose less;
  every hedge idea so far died on cost (rows D08, D15).

## UNRESOLVED -- decide these when the data exists

| id | item | what decides it | when |
|---|---|---|---|
| U1 | Polymarket US pin / maker / cross-book | `research/poly/poly_ws_report.py` on the 3-day recording (scratch path in OPEN_WORK A11); bar in SECOND_INCOME_SCAN section 1 row 1 | ~2026-09-28 |
| U2 | Seven-coin hourly ladders | `arm-hourly-all` vs live via armh2h2 | ~2026-10-02 |
| U3 | Hourly BTC at 1 contract (live) | ~30 fired closes; fill rate and price | ~2026-10-01 |
| U4 | Crypto one-touch monthlies (KXBTCMAXMON etc.) | replicate the trimmed-mean rule from the tape, time crosses vs trades, then a 14-day watcher | open |
| U5 | Sports final minute | a working free score feed, then books in the last 2 min of 20 games | open |
| U6 | Earthquake "biggest quake" markets | `python research/quakewatch.py --report` | ~2026-10-08 |
| U7 | Hourly temperature markets | `python research/wxwatch.py --report` (supply ~0 so far) | ~2026-09-28 |
| U8 | Fresh-offer gate / toxic-offer gate / 2c edge floor | `python research/bars.py` (or /bars on the phone) | ~2026-10-01 |

---

## LEDGER

| id | name | family | status | $/day | one-line reason | evidence |
|---|---|---|---|---|---|---|
| L01 | 15-min crypto late pin (pinrun) | crypto 15M | live | +$438 lifetime to 09-25 (all families, 1,101 markets; 09-24: +$92) | buy the near-certain side in the last 45 s off the settlement-index feed | CURRENT_STATE.md, VERSIONS.md |
| L02 | Coin race late pin | crypto coin race | live (5 contracts) | ~$1-2 | 59 won, 1 tie, 0 lost at 1 contract to 09-24 | OPEN_WORK B1 |
| L03 | Hourly BTC ladder near rungs | crypto hourly | live (1 contract) | unknown | same gates as 15-min, 30x deeper books | VERSIONS v-btcd1, OPEN_WORK A2 |
| T01 | Seven-coin hourly ladders | crypto hourly | testing (paper) | unknown | ETH SOL XRP DOGE BNB HYPE ladders on indexes we already follow | VERSIONS v-ladder7 |
| T02 | Polymarket US BTC 15-min/1-h | cross-venue | testing (recorder) | $0-15 est. | same contract, 1/10-1/50 the book, makers paid a rebate | SECOND_INCOME_SCAN s1-2 |
| T03 | Earthquake markets after USGS confirms | science | testing (watcher) | $0-10 | decided market sometimes still below 97c | OPEN_WORK A6 |
| T04 | Hourly temperature (Kalshi's own index) | weather | testing (watcher) | ~$0 | prediction perfect (240/240) but nobody sells | OPEN_WORK A5 |
| N01 | Crypto one-touch monthlies | crypto monthly | needs-data | $2-10 | $3,738 bought <=97c in last 10 min before early close, 3 events | SECOND_INCOME_SCAN s1 row 3 |
| N02 | Sports final minute | sports | needs-data | unknown | needs a score feed (ESPN 403) | SECOND_INCOME_SCAN s1 row 5 |
| D01 | Daily-high temperature brackets | weather | dead | ~$4 | locked money was the 1 F rounding-boundary case | IDEAS_2026-09-24 s3 #1 |
| D02 | KXWTI daily oil | commodities | dead | ~$3 | winner 98-99c by 30 s; wrong settlement proxy | IDEAS s3 #2 |
| D03 | AAA gas price ladders | economics | dead | negative | certainty from a private feed we lack; takers lost $9,800 | IDEAS s3 #3 |
| D04 | Equity-index / hourly-commodity / FX 15M | financials | dead | negative | one value at one instant, no partly-written average; lost real money | IDEAS s3 #4 |
| D05 | Daily-low temperature | weather | dead | ~$0.50 | whole-Celsius feed makes false locks | IDEAS s3 #5 |
| D06 | KXRAIN | weather | dead | ~0 | money gone within 15 min of first rain; radar prices it | IDEAS s3 #6 |
| D07 | Gemini Predictions pin | cross-venue | dead | 0 | winning side never <=98c inside 45 s | IDEAS s3 #7 |
| D08 | Kalshi perpetual as hedge leg | hedging | dead | negative | hedge size explodes near 50%; fees 449x a binary hedge | IDEAS s3 #8 |
| D09 | Top-of-hour 15-min YES + ladder NO package | crypto consistency | dead | 0 | 0 riskless packages in 60 reads, cheapest $1.0067 | IDEAS s3 #9 |
| D10 | Offshore crypto binaries (Deribit etc.) | cross-venue | dead | 0 | none US-accessible on a 60-s average | IDEAS s3 #11 |
| D11 | Kalshi vs Gemini cross-venue package | cross-venue | dead | negative | different strikes and indices; pays $0 on 4% of closes | IDEAS s3 #12 |
| D12 | Robinhood/Coinbase as second book | cross-venue | dead | 0 | they ARE Kalshi's book | IDEAS s3 #13 |
| D13 | Coin race favourite-longshot maker | crypto coin race | dead | -$0.62 | not significant; loses on holdout | IDEAS s3 #14 |
| D14 | Resting the hedge as a maker bid | hedging | dead | negative | a resting bid fills only when we are winning | IDEAS s3 #15 |
| D15 | Selling our winner into the 99.5c queue | exits | dead | negative | the bid vanishes 4-8 s before the flip | IDEAS s3 #16 |
| D16 | Selling lottery tickets at 1-5c | crypto 15M | dead | negative | the buyer is informed; one market cost makers $370k | IDEAS s3 #17 |
| D17 | Market making on 15-min crypto | crypto 15M | dead | -$2,800 at sim volume | every one of 12 variants loses every day, even first-in-line and instant | MAKER_SIM_2026-09-24 s9 |
| D18 | Far rungs of hourly BTC at 99c | crypto hourly | dead | ~0 | 0 safe-side buys >=97c at $150+ in 68 closes; the 99c offers were the next-to-settle rung | FAR_RUNG_2026-09-25 verdict |
| D19 | Ladder both-sides / monotonicity arbitrage | crypto hourly | dead | 0 | 0 violations in 1,496 polls | SECOND_INCOME_SCAN s1 row 4 |
| D20 | S&P / Nasdaq daily close ranges | financials | dead | 0 | one instant; strikes finer than auction noise | SECOND_INCOME_SCAN s1 row 7 |
| D21 | Crypto.com 5/15/20-min binaries | cross-venue | dead | 0 | 8-24c spreads, book dies at 42 s | SECOND_INCOME_SCAN s1 row 8 |
| D22 | ForecastEx / Rothera / PrizePicks / Sporttrade | cross-venue | dead | 0 | weekly+, Kalshi's book, sports-only, or exited US | SECOND_INCOME_SCAN s5 |
| D23 | Air quality / box office / app ranks / Trends / river levels | misc | dead (for now) | 0 | one-off or custom series, no repeatable close | SECOND_INCOME_SCAN s1 row 9 |
| D24 | Truth Social weekly post count | politics | dead | <$1 | one close a week, thin | SECOND_INCOME_SCAN s1 row 6 |
| D25 | Exchange-feed "move against us" gate | crypto 15M | dead (as a gate) | 0 | does not separate our losers | FEED_LEAD_2026-09-24 |
| D26 | Cash out AND hedge (flip to a full reversal bet at the alarm) | hedging | dead | ~0, worse tail | the other side is fairly priced at the alarm; +$59 on 10 hedges but range -$124..+$185; 09-19 -$223 -> -$275 | results/HEDGE_FLIP_2026-09-25.md |
| D27 | Buy our pin legs as a Kalshi combo | crypto 15M | dead | -$2.2..-2.6/day | combos priced 0.0-0.4c ABOVE what we paid at our moments (26 orders); same bet at equal size; needs simultaneous legs (ours are 11 s apart) and a 0.6-7 s RFQ | results/COMBOS_2026-09-25.md |

## Rows from the 2026-09-25 multi-agent sweep (63 checked; S = sweep id)

| id | name | family | status | $/day | reason | evidence |
|---|---|---|---|---|---|---|
| SI01 | Kill the same-second double send (pin bot) | lose less / order str... | dead | I01 as written: $0 a day at $900 and at $5k. It would block 0 order... | The mechanism is absent. Orders are sent synchronously, and 0 of 27 millisecond-stamped duplicates were in flight. The proposed gate would be a no-... | IDEA_SWEEP_2026-09-25 (json id I01) |
| SI02 | LIP payment decider: Kalshi's paid_out scoreboard plus a $30 probe | identify better / Kal... | needs-data | I02 itself makes $0 a day. The probe would cost about $6-12 expecte... | The checker's key premise is wrong: filling the empty side is NOT the only missing piece, and we would NOT be the only filler. 1) Most of the busy ... | IDEA_SWEEP_2026-09-25 (json id I02) |
| SI03 | Late-dry rain NO (KXRAIN after 8 PM local), with sensor-down gate a... | weather / daily rain,... | needs-data | $900 bank: about $1-4/day, most likely about $2. - **How it adds up... | The "1 loss in 255" figure comes from how the backtest was built. It reads the YES bid only at the close of each minute. A live bot sees the price ... | IDEA_SWEEP_2026-09-25 (json id I03) |
| SI04 | Miami hourly dead-side 1c filler (KXTEMPMIAH LIP unlock, with cross... | incentive programs (K... | dead | Negative at both bank sizes. The pool caps the size, not the bank, ... | 1) The killer: people paying 99c for the safe side buy out a 1,000 contract 1c stack about 4 minutes after it appears, and come back within seconds... | IDEA_SWEEP_2026-09-25 (json id I04) |
| SI05 | Coin-race YES-only dead-side 1c filler | incentive programs (K... | needs-data | These are replay numbers, so a hypothesis, not evidence. If Kalshi ... | I could not refute it. My own data makes the cost side look better than the checker thought, so what remains is two things nobody has checked with ... | IDEA_SWEEP_2026-09-25 (json id I05) |
| SI06 | Frechet combo desk: quote 15-min crypto/commodity combos only at pr... | combos (RFQ layer) x ... | plausible-needs-data (refut... | As designed (hedge-then-confirm): $0/day. The core step is barred b... | Kalshi's own rulebook forbids the step that makes this "riskless". Rule 5.3(g) was filed with the CFTC on 2025-11-25 and took effect 2025-12-11. It... | IDEA_SWEEP_2026-09-25 (json id I06) |
| SI07 | Print-to-Fed staircase: read the jobs/CPI number, beat the Fed-deci... | economics x Fed-decis... | needs-data | $900 bank, of which about $650 is free at the 12:30:00Z print. All ... | The profit only exists in a gap of about 1.6 seconds, and two named competitors are closing it. On the latest big print (CPI 2026-09-11), all of th... | IDEA_SWEEP_2026-09-25 (json id I07) |
| SI08 | Sign-up bonuses at other US venues (prediction venues and sportsboo... | promotions x Kalshi s... | needs-data | This is not money per day. It is a one-time amount, most of it coll... | I found nothing that stops this from making money. I did find four things that change the verdict. 1. It is not established as viable. Everything d... | IDEA_SWEEP_2026-09-25 (json id I08) |
| SI09 | PortWatch Tuesday sniper (chokepoint transit counts) | politics/shipping cho... | needs-data | $10-20/day at a $900 bank, arriving as one lump per Tuesday: most T... | The checker's best-case profit assumes every cheap winning-side offer traded 10 s or more after the first price jump could have been ours. That ass... | IDEA_SWEEP_2026-09-25 (json id I09) |
| SI10 | Poly pin: the 1-cent tick gift on Polymarket US BTC 15-min and 1-ho... | cross-venue / crypto ... | needs-data | - About $2-4 a day at the current $60 Poly bank: 60 contracts a hit... | I could not show the narrowed 1-hour rule loses money. What I could show is that it is small, and that the checker's next test will probably read F... | IDEA_SWEEP_2026-09-25 (json id I10) |
| SI11 | Two books, one print: riskless Kalshi-Polymarket package at the ext... | cross-venue arbitrage... | needs-data | $900 BANK (Polymarket leg capped near 60 contracts): - Measured $0.... | The price gap is real, so I could not kill the idea on the data. What stands against it is that the money is small and easy to lose, and running it... | IDEA_SWEEP_2026-09-25 (json id I11) |
| SI12 | CPI two-complex consistency (MoM vs YoY on the same release) | economics / CPI relea... | needs-data | About $0/day at the current ~$1,050 bank, and possibly negative, if... | The money tied up in the pair is not free on this account, and the checker priced it as free. pinrun sets its bet size from Kalshi's cash balance: ... | IDEA_SWEEP_2026-09-25 (json id I12) |
| SI13 | Same-number twin books: gas daily vs weekly/monthly (and other pair... | economics / cross-hor... | needs-data | About $0.5-2.5 a day, central estimate about $1. That is roughly $3... | The gaps are not left for us. One bot already takes them, firing its two legs 59-61 ms apart (median; p90 at most 77 ms). It did this on 8 of the 9... | IDEA_SWEEP_2026-09-25 (json id I13) |
| SI14 | Convert the Polymarket US promo credit into withdrawable cash (risk... | promotions x cross-ve... | needs-data | $0 recurring; it pays once. - Hedged: about +$28 locked (my own cal... | I could not find anything that makes this lose money, so it is not refuted. The real objections are about its size and about the hedged version the... | IDEA_SWEEP_2026-09-25 (json id I14) |
| SI15 | Slow-market LIP unlock, only where a 1c bid can rest (crossing guard) | incentive programs (K... | dead | About $0-10/day at best, and negative wherever the big pools are. -... | The checker's leftover $0-40/day depends on one series: KXYTDAILYTOPVIDEOG supplies $170 of the $191/day "uncontested, not eaten" half-pool. That s... | IDEA_SWEEP_2026-09-25 (json id I15) |
| SI16 | Cheap-side LIP stack joining on slow markets (culture, politics, sp... | incentive programs (K... | needs-data | If Kalshi pays exactly as its filed rules say: - Political group: a... | I could not show it loses money, so it is not refuted. The checker's biggest block of value is still overstated about 4x. The political group ($128... | IDEA_SWEEP_2026-09-25 (json id I16) |
| SI17 | AI-usage share markets: running-average pin on public OpenRouter/Ve... | science-tech / AI usa... | plausible-needs-data (refut... | At the current $900-1,040 bank: - $0 or worse. The sweep earns abou... | The refutation covers the checker's money figure at the current bank. The idea itself survives at a larger bank. 1) At a ~$900-1,040 bank there is ... | IDEA_SWEEP_2026-09-25 (json id I17) |
| SI18 | Crypto one-touch lock: the trimmed-mean index already crossed, Kals... | crypto / monthly and ... | needs-data | $300 per event, out of the ~$900 bank: - Steady part, fixed rules, ... | What it means first: this is a bet that Kalshi's own process breaks now and then, not a steady edge. I found nothing that makes it lose money outri... | IDEA_SWEEP_2026-09-25 (json id I18) |
| SI19 | Two-sided LIP quoting that steps out around scheduled information e... | incentive programs x ... | needs-data | $0 if the liquidity credit does not land. That has never been teste... | The checker's ceiling comes from one good moment, and that moment turns against a newcomer. I watched the book live today from 07:50 to 10:20 ET. T... | IDEA_SWEEP_2026-09-25 (json id I19) |
| SI20 | Table-tennis LIP, pre-match only | incentive programs x ... | needs-data | $0 if Kalshi blocks sports in his state. First check, free: open an... | Two things could sink it. Neither is proven, and neither shows the idea loses money on average. (1) HE MAY NOT BE ALLOWED TO TRADE SPORTS AT ALL, a... | IDEA_SWEEP_2026-09-25 (json id I20) |
| SI21 | Coin-race LIP at the reference price with index-triggered pulls | incentive programs x ... | plausible-needs-data (refut... | These rest only on the replay, so they are a hypothesis, not our lo... | The checker's replay only fills our bids when a trade prints, and that leaves out the fill that decides the result. When a coin surges, the big inc... | IDEA_SWEEP_2026-09-25 (json id I21) |
| SI22 | New-listing LIP on the monthly one-touch ladders (Oct 1 listings) | incentive programs x ... | plausible-needs-data (refut... | $0-3 a day averaged over the month. This is not measured and nothin... | The checker's money rests on one assumption: a 1,000-contract bid at 1c on the cheap side shares that side's pool with the other 1c bids. Kalshi's ... | IDEA_SWEEP_2026-09-25 (json id I22) |
| SI23 | Lottery Desk: sell longshots as a maker in slow, feed-less markets ... | calibration bias (fav... | dead | Two different pictures: the full 30 days, and the recent half, whic... | 1. There is no edge in the recent half. On Sep 9-23 the realistic rules net -0.07c to -0.20c per contract, and the taker control is +0.19c at t 0.4... | IDEA_SWEEP_2026-09-25 (json id I23) |
| SI24 | Slow-market pin: buy determined-but-open favourites at 95-98c after... | generic answer-is-pub... | dead | General form: about $0/day at either bank. Without information the ... | (1) The market reprices at the source. Once the White House count or an executive-order signing settles a strike, YES is 99c within hours: 19 of 20... | IDEA_SWEEP_2026-09-25 (json id I24) |
| SI25 | 24-hour-ahead weather favourite NO taker (far KXHIGH tails; dry-cit... | calibration bias x pu... | plausible-needs-data (refut... | At today's roughly $1,000 bank: - Rain: about +$3/day on its own, b... | At today's bank, the rain trade makes less than the same money makes in pinrun, so taking it lowers total profit. The rain edge itself looks real. ... | IDEA_SWEEP_2026-09-25 (json id I25) |
| SI26 | Post-final cash-out desk: rest a 99c bid on the winner after the ga... | sports / settlement m... | dead | $900 bank: $0 a day as measured on tennis, table tennis, esports an... | 1) Queue position. The step is 1c and 99c is the top, so priority goes purely by time. On every finished market I watched, a queue of 170k-450k con... | IDEA_SWEEP_2026-09-25 (json id I26) |
| SI27 | In-play two-book parity and cross-series arithmetic breaks (buy bot... | sports / in-play inte... | dead | $0/day at the $900 bank and $0/day at $5k. Price-taking arithmetic:... | 1) There is no standing mispricing. At random instants the two books add to $1.00-1.02 (MLB 99.7% of minutes at or above $1.00). The rare sub-$1 mo... | IDEA_SWEEP_2026-09-25 (json id I27) |
| SI28 | Sports combo desk: sell parlays to recreational requesters (markup,... | combos/parlays (RFQ l... | dead | Upper bounds assume Kalshi leg mids are the true odds, we win every... | - Measured markup vs fresh mids after the combo maker fee is 1.0-4.2% of premium for 2-7 legs. That is inside fair-value noise. - The large markups... | IDEA_SWEEP_2026-09-25 (json id I28) |
| SI29 | Pin supply through combo requests (requester side) | combos x pin bot | needs-data | Realistic: $0 to 8 a day on the $900 bank, sign not proven on our o... | I could not refute the checker's verdict; I could only make it narrower. On the index tape the sign comes out positive, better than the checker fou... | IDEA_SWEEP_2026-09-25 (json id I29) |
| SI30 | Pre-game MLB prop maker with a lineup guard | player props (making) | dead | $0-2 a day for about 5 weeks (3 regular-season days, then 1-4 posts... | The checker's money figure assumes the ~$900 bank is free to hold MLB positions, and it is not. The live crypto bot sizes from Kalshi's gross cash ... | IDEA_SWEEP_2026-09-25 (json id I30) |
| SI31 | Mention-market ASR sniper (buy YES the moment a listed word is said) | mentions: live speech... | dead | $900 bank: about $0/day, and more likely negative. With a public we... | 1. The whole supply of cheap contracts goes in one sub-second order from established buyers. A follower gets about 5% of the clean-utterance supply... | IDEA_SWEEP_2026-09-25 (json id I31) |
| SI32 | KXRT review-burst sniper (stale LIP-farmer quotes) | Rotten Tomatoes page ... | dead | Sniper as proposed (I32): supply is the limit, not money, so $900 a... | (1) The speed race is already lost. 56% of the cheap volume left after the move went in the first second to one sweeper, and 44% of jumps were over... | IDEA_SWEEP_2026-09-25 (json id I32) |
| SI33 | White House presidential-actions sniper (page-count series) | politics running coun... | needs-data | The idea as written, taking what is left 3 s or more after a postin... | Most of the money comes from two days. Three strikes on those two days produced 73% of all the money (after fees) that takers made in 10 weeks: SEP... | IDEA_SWEEP_2026-09-25 (json id I33) |
| SI34 | RCP 1 PM snapshot watcher (Trump approval brackets) | polling-average snaps... | needs-data | Weekdays: about $0. All takers combined made about $14/day after ou... | The weekday version is dead, and the idea's claimed "main value" is dead too. What is left is a Sunday-only bet that rests on 2 days. 1) WEEKDAYS: ... | IDEA_SWEEP_2026-09-25 (json id I34) |
| SI35 | Brazil election-night count-order projection (Oct 4, runoff Oct 25) | foreign elections x o... | needs-data | These are estimates, not measurements. Two nights at most: Oct 4 an... | The checker's main money scenario doesn't show up in any of the four past count nights I could check. That scenario: the crowd follows the misleadi... | IDEA_SWEEP_2026-09-25 (json id I35) |
| SI36 | House/Senate seat ladders: D and R cannot both reach 218 (package n... | elections / cross-ser... | dead | PACKAGE, one-off, measured: - $5k bank, with $3,349 idle for 129 da... | 1) SIZE KILLS IT: the only riskless package in the whole House/Senate complex is worth $37.82 once, on $3,349 locked for 129 days, which is 1.1% ab... | IDEA_SWEEP_2026-09-25 (json id I36) |
| SI37 | Company KPI release sweep (markets stay open after the press release) | financials / company ... | plausible-needs-data (refut... | **With the free sources I measured (SEC feed and API, PR Newswire a... | The checker's money case assumed we could place orders within 10 seconds of the release. I timed today the free sources a laptop could use, and non... | IDEA_SWEEP_2026-09-25 (json id I37) |
| SI38 | Fear & Greed 4 PM snapshot (KXFEAR) | financials / index on... | dead | Under $0.60 a day. Weeks far from a line: at most $1.19 a day, and ... | The idea assumes the category is decided at 4 PM ET, so a bot can read the result right afterwards and buy it. That assumption is wrong. The contra... | IDEA_SWEEP_2026-09-25 (json id I38) |
| SI39 | Hurricane markets: NHC b-deck/recon lead and the first-Atlantic-hur... | weather / hurricanes ... | needs-data | About $2-6/day during the June-November season. That assumes a bot ... | What's left of this idea is a speed race against traders who are already in these markets. It is not a lead nobody else has. The $2,405 Fausto wind... | IDEA_SWEEP_2026-09-25 (json id I39) |
| SI40 | Big-surprise macro gate for the pin bot's next closes (lose less) | combination: econ cal... | dead | $0/day at $900, measured: the gate would have skipped 0 live trades... | (1) The idea's own must-be-true #1 is false: the bot's volatility reading is a 5-minute look-back, fully inside the post-print storm by the 45-seco... | IDEA_SWEEP_2026-09-25 (json id I40) |
| SI41 | Synoptic push-stream: rebuild Kalshi's hourly temperature index ~4 ... | weather hourly temper... | dead | Gain over the free public-index version already being watched (T04)... | 1) Sellers who know: offered-book markets lost 3 of 37 (8%) at 0.5F, against 0.9% for all strikes at that margin. That is about break-even at ~90c.... | IDEA_SWEEP_2026-09-25 (json id I41) |
| SI42 | CME fed-funds/SOFR futures mirror into the Kalshi Fed complex (non-... | cross-asset (CME futu... | dead | $900 bank: about -$1 to $0 a day. The measured edge per contract af... | The number that kills it: after a futures-led move, Kalshi's remaining catch-up averages only 2.3-3.6 points, even with zero delay. That is less th... | IDEA_SWEEP_2026-09-25 (json id I42) |
| SI43 | Maker on Polymarket US, hedge on Kalshi (cheap-side longshot premiu... | cross-venue market ma... | dead | $900 bank ($60 is on Poly): - Capacity: $60 / $0.88 per contract = ... | 1. Poly's best price is already about Kalshi ask + 1c, so being strictly better only buys the fills that come right after Kalshi has moved against ... | IDEA_SWEEP_2026-09-25 (json id I43) |
| SI44 | Route BTC entries and hedges to the cheaper book (Kalshi vs Polymar... | cross-venue execution... | dead | $0 to $0.35 a day at the $900 bank, with a central estimate of abou... | The money is not there once you simulate an actual router instead of comparing prices second by second. When the pin really buys BTC, Kalshi prices... | IDEA_SWEEP_2026-09-25 (json id I44) |
| SI45 | Top-of-hour corridor: 1-hour window vs the xx:45 15-min window on t... | cross-venue / single-... | dead | $0/day at both $900 and $5k. Bank size does not matter because the ... | 1) The winner leg does not exist: Polymarket's market makers do not offer a near-certain winner below 99c in the last 45 s, and usually offer nothi... | IDEA_SWEEP_2026-09-25 (json id I45) |
| SI46 | Long-dated crypto vs the options market: sell moonshots/crash tails... | cross-asset (Deribit/... | dead | At the $900 bank: $0/day. Doing it costs money. pinrun made +$437.8... | 1) There is no evidence the options model beats Kalshi on real outcomes. - Kalshi's own crypto longshots at 1-5c came true 2-3 times more often tha... | IDEA_SWEEP_2026-09-25 (json id I46) |
| SI47 | Incentive-program and volume-rebate watcher | infrastructure for 'i... | dead | Now, at either bank size: $0/day, because no volume program exists ... | The number that kills it: 0.5c per contract x 1,218 eligible contracts/day = a $6.09/day ceiling that no program design can exceed. Realistic payou... | IDEA_SWEEP_2026-09-25 (json id I47) |
| SI48 | Watch for new Polymarket US crypto listings | cross-venue option value | needs-data | $0.00 a day today, at both $900 and $5k: Polymarket US lists only B... | Under the Polymarket limits written into research/polyorder.py, a new coin listing adds $0.00 a day. The limits are $10 of money put at risk per da... | IDEA_SWEEP_2026-09-25 (json id I48) |
| SI49 | Kalshi APY on cash and positions (check it is being paid) | capital efficiency | needs-data | - **Gross:** $0.094 a day at today's $1,058, about $0.073 after tax... | The facts are right, but this is not a way to make more money. The interest has been building up automatically since 2026-09-14, so doing I49 adds ... | IDEA_SWEEP_2026-09-25 (json id I49) |
| SI50 | Long-dated crypto structural packages (nested one-touch pairs, touc... | crypto / annual one-t... | dead | At the $900 bank this loses money overall. Best case: SOL +$4.6 to ... | 1) Too small: the whole thing is a one-time $5-20 expected profit on about $348 of cash, not a steady stream. The high SOL bids showed up this week... | IDEA_SWEEP_2026-09-25 (json id I50) |
| SI51 | In-game longshot pricing (late-game step-like calibration; in-game ... | sports / in-play cali... | needs-data | Expected value today is $0, because the sign for a laptop bot is no... | The only money in this idea is the 1c gap between the buy price and the sell price. That gap goes to whoever is first in line at a price and quicke... | IDEA_SWEEP_2026-09-25 (json id I51) |
| SI52 | Mention markets: NO-side fades (pre-event YES overpricing, in-event... | mentions / calibration | dead | About $0/day, and more likely a small loss. At 20 contracts a word,... | The "YES has been overpriced since April 2026" story, which is the whole basis of the checker's +6c a contract and $8.6 a day, does not hold up on ... | IDEA_SWEEP_2026-09-25 (json id I52) |
| SI53 | Polymarket US BTC mid-window stale quotes vs our index fair (incl. ... | cross-venue: Polymark... | dead | Expected about $0 a day. The rule as the idea states it (both sides... | Nothing here is a slow Polymarket quote we could beat to. The one profitable slice, favourites at the second of the index print, has three problems... | IDEA_SWEEP_2026-09-25 (json id I53) |
| SI54 | Blowout pin: MLB leader entering the 9th up 6 or more | sports / late-game ne... | dead | REALISTIC, $900 bank: about $0/day, and likely slightly negative. B... | (1) No one sells below the cap: 0 contracts at 98c or less in 39 of 39 football games at 17+ with 5:00 left and in 10 of 10 MLB games with a 6+ lea... | IDEA_SWEEP_2026-09-25 (json id I54) |
| SI55 | Post-play stale-offer races (walk-offs, totals locking, first-5 dec... | sports / in-play late... | dead | About $0/day at either bank size. - Ceiling at $900, on a full regu... | - MLB's free feed is deliberately late: a median 9.2 s behind the pitch, 90th percentile 16 s, flagged "isDelay": true. Every free endpoint and the... | IDEA_SWEEP_2026-09-25 (json id I55) |
| SI56 | Replay-review window pricing | sports / rules x offi... | dead | The idea as proposed (buy the long shot during the review) loses mo... | 1) The premise is wrong: game-ending calls are overturned 7 times in 100 for non-robot reviews (4 of 54), not about 45. Robot challenges are overtu... | IDEA_SWEEP_2026-09-25 (json id I56) |
| SI57 | Sports settlement quirks: tennis walkovers and MLB called/suspended... | sports / settlement r... | dead | About $0.30-0.50 a day with the risk actually capped (100 contracts... | The checker's plan to rest 49c bids after a sweep relied on "bid both sides so a filled pair always pays $1, and the leftover risk is capped near $... | IDEA_SWEEP_2026-09-25 (json id I57) |
| SI58 | Obscure-league thin books with free score feeds | sports / thin markets | dead | Expected: $0 a day at the $900 bank and $0 a day at $5k. Buying aft... | 1) Speed. The market moves a median 7 s before ESPN even timestamps the goal, and most stale offers are gone within 10 s. Any free feed (ESPN, open... | IDEA_SWEEP_2026-09-25 (json id I58) |
| SI59 | Sharp-book anchor for Kalshi sports (pregame) | calibration x externa... | dead | $900 bank: about $0 a day in trading gains, because nothing qualifi... | - Kalshi's pregame sports books are already priced off the sharp line. Mid is within 0.64c of Pinnacle's no-vig price (99th percentile 2.9c), and t... | IDEA_SWEEP_2026-09-25 (json id I59) |
| SI60 | Pregame sports calibration bets: tennis favourites and longshot pro... | calibration bias (spo... | dead | $0 at both banks. - Tennis: pooled -0.26c a contract × about 3.7 qu... | - Tennis favourites: 2 of 3 separate windows are negative. Pooled -0.26c a contract over all 297 matches Kalshi has ever listed in the band. The se... | IDEA_SWEEP_2026-09-25 (json id I60) |
| SN01 | Stale derived ladder: NFL wins-by-week priced exactly from game mon... | sports / derivative-v... | needs-data | $900 bank: about $0 per day. Each window is worth roughly -$8 to +$... | I could not refute it. The cheap quote is real, is still there, and I can explain why it exists. The strongest objection is money at the operator's... | IDEA_SWEEP_2026-09-25 (json id N01) |
| SN02 | Two books, two thermometers: ForecastEx NO plus Kalshi YES on the s... | cross-venue / settlem... | dead | Guaranteed part: about $0-2/day at a $900 or $5k bank. We would sit... | Someone is already running this exact package with a fast bot, so the under-$1 flow the checker counted is either that bot's own fills or what it l... | IDEA_SWEEP_2026-09-25 (json id N02) |
| SN03 | Use Kalshi's own cash pools as the second account (index 0 for ever... | capital efficiency / ... | dead | $0 directly, at both bank sizes, and no net gain on money that is a... | 1) The premise is wrong. The pools separate the bookkeeping, not the money. Cash moves between pools in about 4 seconds, so any dollar used for poo... | IDEA_SWEEP_2026-09-25 (json id N03) |
