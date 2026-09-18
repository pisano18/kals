# RESULTS_attrib -- what each gate in the bot actually did

```
  EVERY GATE IN THE BOT, IN THE ORDER IT IS ASKED

  A gate only gets asked if every gate above it said yes, so a quiet
  row near the bottom may just mean the rows above got there first.

  EVERY ROW ADDS UP:  fired = moved + blocked, and
                      blocked = won + lost + the three 'cannot say' columns.

  HOW MUCH OF THIS IS TODAY'S BOT: 5374 of 7022 refusals (77%) come
  from runs with exactly the settings that are live now, starting
  pinrun-live-20260915T013908Z.jsonl. The rest ran under older settings and describe
  a bot that no longer exists.

  gate            | on? |  fired | moved |blocked |  won | lost |no price|no size|unsettled| $ if filled
  ----------------|-----|--------|-------|--------|------|------|--------|-------|---------|------------
  close_budget    |  on |    340 |    78 |    262 |    - |    - |    262 |     0 |       0 |      -
  max_per_close   |  on |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  max_per_market  |  on |      9 |     9 |      0 |    - |    - |      0 |     0 |       0 |      -
  both_sides      |  on |    149 |   149 |      0 |    - |    - |      0 |     0 |       0 |      -
  market_attempts |  on |     14 |     9 |      5 |    - |    - |      5 |     0 |       0 |      -
  attempts_cap    |  on |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  book_suspect    |  on |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  book_stale      |  on |     88 |     3 |     85 |    - |    - |     85 |     0 |       0 |      -
  index_stale     |  on |     27 |     0 |     27 |    - |    - |     27 |     0 |       0 |      -
  no_sigma        |  on |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  confidence      |  on |    421 |   202 |    219 |    - |    - |    219 |     0 |       0 |      -
  no_offer        |  on |   3371 |    53 |   3318 |    - |    - |   3318 |     0 |       0 |      -
  depth_floor     |  on |    551 |    47 |    504 |    - |    - |      0 |   504 |       0 |      -
  edge_floor      |  on |   1359 |    67 |   1292 | 1048 |    0 |      0 |     0 |     244 |    +136.51
  against_thin    |  on |     19 |     7 |     12 |   10 |    0 |      0 |     0 |       2 |      +5.45
  jump_against    |  on |     26 |     2 |     24 |   19 |    0 |      0 |     0 |       5 |      +3.72
  dump_guard      |  on |      9 |     8 |      1 |    0 |    1 |      0 |     0 |       0 |     -37.85
  improve_by      |  on |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  rebuy_band      |  on |     19 |    19 |      0 |    - |    - |      0 |     0 |       0 |      -
  price_ceiling   |  on |    551 |    88 |    463 |  379 |    0 |      0 |     0 |      84 |    +122.80
  ev_floor        |  on |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  early_once      |  on |     56 |    56 |      0 |    - |    - |      0 |     0 |       0 |      -
  staged_none     |  on |      3 |     2 |      1 |    - |    - |      1 |     0 |       0 |      -
  early_cheap     |  on |      1 |     1 |      0 |    - |    - |      0 |     0 |       0 |      -
  early_wide      |  on |      9 |     4 |      5 |    - |    - |      5 |     0 |       0 |      -

  WHAT THIS TABLE DOES NOT COVER: the INSURANCE decisions. Whether to
  buy the other side when a bet turns, and at what price, is decided
  somewhere else in the bot and is not recorded as a refusal, so no row
  here can ever describe it. Read those from the hedge list instead
  (`/hedges` on the phone, or the Now tab). As of 2026-09-18 that is 12
  insured quarter-hours of which 11 still ended negative.

  'on?' IS THE LIVE BOT RIGHT NOW, read from its own newest start
  record -- not from this file's defaults. A gate marked OFF is not
  running for real money, so its zero means 'switched off', not 'never
  needed'. Those are opposite facts and they used to print the same.

  WHY A BLOCKED MARKET MAY HAVE NO WIN/LOSE
    no price   the gate fired BEFORE any price existed -- nothing was
               ever on the table, so there is nothing to value. This
               will never be scorable and that is correct.
    no size    a price and a side were recorded but not the size. That
               is a LOGGING GAP in the bot, not a limit, and it is
               being closed gate by gate.
    unsettled  the market has not settled yet, or the settlement pull
               has not caught up. It resolves itself.

  WHY 'would lose' IS SO OFTEN ZERO, and why that is not a broken column.
  Every gate below `confidence` is only ever asked about a market the
  model is ALREADY at least 99.5% sure of. That is the population, not
  a sample of it. Those markets win almost every time whether we buy
  them or not, so a gate that turns them away turns away winners -- by
  construction. The outcomes behind this column were checked against
  Kalshi's own settlement record on 503 shared markets and agreed on
  503 of 503, with the underlying results running a balanced 50/50.
  A gate stopping winners is therefore the EXPECTED reading; what makes
  a gate worth keeping is the size of the loss it prevents when it is
  right, which is why one -$37.85 row can outweigh a thousand small
  forgone wins.

  `$ if we had been filled` is an UPPER BOUND, not profit and loss. A
  price showing is not a fill -- we would have been racing for it, and
  the live fill rate is about 7 in 10. A POSITIVE number means the gate
  turned away trades that would have won; a NEGATIVE number means it
  turned away trades that would have lost, which is it doing its job.

  These figures DO NOT add up to the bot's profit and never will: the
  gates share one contract budget, so refusing one trade frees money a
  later trade spends. Only a re-run with a gate switched off gives its
  true worth.

  WHAT EACH ONE IS
    close_budget     the close has already bought its contract budget
    max_per_close    the close has already had its allowed number of fills
    max_per_market   we already own this market in this close
    both_sides       we hold the other side of this market already
    market_attempts  already tried this market enough times this close
    attempts_cap     too many orders already sent on this close
    book_suspect     the order book looked wrong
    book_stale       the order book was too old to trust
    index_stale      the price index was too old to trust
    no_sigma         not enough index history to measure how jumpy it is
    confidence       the model was not sure enough
    no_offer         the model was sure but nobody was selling that side
    depth_floor      too few contracts on offer to be worth taking
    edge_floor       the profit on offer was too thin
    against_thin     thin profit AND the live price was already past the strike against us
    jump_against     the index just made a big one-second move against us -- jumps keep going more often than the model thinks
    dump_guard       priced far below fair -- someone else knew something
    improve_by       a second buy that was not cheaper than the first
    rebuy_band       a same-coin re-buy outside the 0.5-1c band
    price_ceiling    priced above the 98c ceiling
    ev_floor         expected value negative at that price
    early_once       A46: this market already holds an early leg (31-45 s); only one per market
    staged_none      A46: the staged leg came to nothing (market already at full size, or under the minimum)
    early_cheap      A49: the 31-45 s early leg wanted an ask under the 90c floor. Out that far less of the settlement average is locked, so a cheap ask is the market disagreeing with us where the model is weakest
    early_wide       A50: the 31-45 s early leg found our model MORE than the cap above the market price. Late, that disagreement is the whole edge (6c or more made 1.44 $/bet inside 30 s); early, three quarters of the settlement window has not happened yet and the same band lost 3.01 $/bet, so out there a big edge means our volatility guess is wrong rather than the market

  INSURANCE -- EVERY ALARM, AND WHETHER IT WAS WORTH ANYTHING

  The gate table above cannot see any of this: insurance decisions are
  not recorded as refusals. This is the population the gate table
  misses, and it is counted by ALARM, not by purchase -- asking only
  whether the hedges we bought paid cannot say whether buying was the
  right call in the first place.

  13 alarms on real money.
    7 times our bet went on to LOSE  -- insurance was needed
    5 times our bet went on to WIN   -- the premium was thrown away
    (1 of the needed ones we never managed to insure at all)
    1 have not settled on file yet
    1 found nobody selling the other side

  WHAT IT WAS WORTH
    paid out when needed         +85.98
    thrown away when not         -39.43
    ------------------------------------
    insurance, all in            +46.55

  A POSITIVE total does not make the rule right and a negative one does
  not make it wrong: this counts only markets where the alarm fired, and
  the alarm is the thing being judged. What matters is the HIT RATE --
  how often an alarm was followed by a real loss. Two paper tests are
  aimed at exactly that: A47 waits for the market price to agree, A51
  waits until the other side is a bet we would make on its own.

  every alarm
    KXBNB15M-26SEP131230-30        ours no  -> no       32 @ 0.100  our side won -- premium thrown away
    KXBNB15M-26SEP161230-30        ours no  -> yes       1 @ 0.470  our side lost -- insurance paid
    KXBTC15M-26SEP121100-00        ours no  -> no       20 @ 0.140  our side won -- premium thrown away
    KXBTC15M-26SEP140530-30        ours no  -> yes      60 @ 0.580  our side lost -- insurance paid
    KXBTC15M-26SEP172115-15        ours yes -> no       99 @ 0.720  our side lost -- insurance paid
    KXDOGE15M-26SEP160900-00       ours no  -> no       87 @ 0.150  our side won -- premium thrown away
    KXDOGE15M-26SEP180015-15       ours yes -> ?        34 @ 0.740  not settled on file
    KXETH15M-26SEP120545-45        ours yes -> no        0 @   -    our side lost -- UNINSURED
    KXETH15M-26SEP121115-15        ours no  -> no       20 @ 0.263  our side won -- premium thrown away
    KXHYPE15M-26SEP141600-00       ours no  -> yes      62 @ 0.510  our side lost -- insurance paid
    KXNEAR15M-26SEP160430-30       ours yes -> yes      84 @ 0.180  our side won -- premium thrown away
    KXSOL15M-26SEP120600-00        ours no  -> yes       1 @ 0.949  our side lost -- insurance paid
    KXZEC15M-26SEP122000-00        ours yes -> no       11 @ 0.809  our side lost -- insurance paid
```
