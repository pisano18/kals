# RESULTS_attrib -- what each gate in the bot actually did

```
  EVERY GATE IN THE BOT, IN THE ORDER IT IS ASKED

  A gate only gets asked if every gate above it said yes, so a quiet
  row near the bottom may just mean the rows above got there first.

  EVERY ROW ADDS UP:  fired = moved + blocked, and
                      blocked = won + lost + the three 'cannot say' columns.

  gate            |  fired | moved |blocked |  won | lost |no price|no size|unsettled| $ if filled
  ----------------|--------|-------|--------|------|------|--------|-------|---------|------------
  close_budget    |    340 |    78 |    262 |    - |    - |    262 |     0 |       0 |      -
  max_per_close   |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  max_per_market  |      9 |     9 |      0 |    - |    - |      0 |     0 |       0 |      -
  both_sides      |    149 |   149 |      0 |    - |    - |      0 |     0 |       0 |      -
  market_attempts |     13 |     9 |      4 |    - |    - |      4 |     0 |       0 |      -
  attempts_cap    |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  book_suspect    |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  book_stale      |     83 |     3 |     80 |    - |    - |     80 |     0 |       0 |      -
  index_stale     |     27 |     0 |     27 |    - |    - |     27 |     0 |       0 |      -
  no_sigma        |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  confidence      |    417 |   201 |    216 |    - |    - |    216 |     0 |       0 |      -
  no_offer        |   3327 |    52 |   3275 |    - |    - |   3275 |     0 |       0 |      -
  depth_floor     |    545 |    46 |    499 |    - |    - |      0 |   499 |       0 |      -
  edge_floor      |   1340 |    66 |   1274 | 1048 |    0 |      0 |     0 |     226 |    +136.51
  against_thin    |     19 |     7 |     12 |   10 |    0 |      0 |     0 |       2 |      +5.45
  jump_against    |     25 |     1 |     24 |   19 |    0 |      0 |     0 |       5 |      +3.72
  dump_guard      |      9 |     8 |      1 |    0 |    1 |      0 |     0 |       0 |     -37.85
  improve_by      |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  rebuy_band      |     19 |    19 |      0 |    - |    - |      0 |     0 |       0 |      -
  price_ceiling   |    545 |    87 |    458 |  379 |    0 |      0 |     0 |      79 |    +122.80
  ev_floor        |      0 |     0 |      0 |    - |    - |      - |     - |       - |      -
  early_once      |     55 |    55 |      0 |    - |    - |      0 |     0 |       0 |      -
  staged_none     |      2 |     1 |      1 |    - |    - |      1 |     0 |       0 |      -
  early_cheap     |      1 |     1 |      0 |    - |    - |      0 |     0 |       0 |      -
  early_wide      |      8 |     4 |      4 |    - |    - |      4 |     0 |       0 |      -
  hedge_wait_normal|      0 |     0 |      0 |    - |    - |      - |     - |       - |      -

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
    hedge_wait_normal A51: insurance held off because the OTHER side was not yet a bet we would make on its own -- our model was not PIN sure of it, or it cost more than the price ceiling. The old rule fired on the model alone and 11 of 12 insured closes still ended negative, five of them paying 10-18c while the market still liked our side
```
