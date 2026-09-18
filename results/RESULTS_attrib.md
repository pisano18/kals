# RESULTS_attrib -- what each gate in the bot actually did

```
  EVERY GATE IN THE BOT, IN THE ORDER IT IS ASKED

  A gate only gets asked if every gate above it said yes, so a quiet
  row near the bottom may just mean the rows above got there first.

  gate            | stopped | closes | only  | really  | of those blocked      | $ if we had
                  |  it     |        | moved | blocked | would WIN / would LOSE|  been filled
  ----------------|---------|--------|-------|---------|-----------------------|-------------
  close_budget    |     340 |     38 |    78 |     262 |    -   (no price)     |       -
  max_per_close   |       0 |      0 |     0 |       0 |        -              |      -
  max_per_market  |       9 |      7 |     9 |       0 |    -   (no price)     |       -
  both_sides      |     149 |    134 |   149 |       0 |    -   (no price)     |       -
  market_attempts |      12 |      7 |     8 |       4 |    -   (no price)     |       -
  attempts_cap    |       0 |      0 |     0 |       0 |        -              |      -
  book_suspect    |       0 |      0 |     0 |       0 |        -              |      -
  book_stale      |      79 |     40 |     3 |      76 |    -   (no price)     |       -
  index_stale     |      27 |      3 |     0 |      27 |    -   (no price)     |       -
  no_sigma        |       0 |      0 |     0 |       0 |        -              |      -
  confidence      |     412 |    208 |   199 |     213 |    -   (no price)     |       -
  no_offer        |    3283 |    399 |    48 |    3235 |    -   (no price)     |       -
  depth_floor     |     538 |    261 |    45 |     493 |    -   (no price)     |       -
  edge_floor      |    1305 |    340 |    61 |    1244 |  1048 / 0             |     +136.51
  against_thin    |      18 |     18 |     6 |      12 |    10 / 0             |       +5.45
  jump_against    |      25 |     21 |     1 |      24 |    19 / 0             |       +3.72
  dump_guard      |       9 |      9 |     8 |       1 |     0 / 1             |      -37.85
  improve_by      |       0 |      0 |     0 |       0 |        -              |      -
  rebuy_band      |      19 |     19 |    19 |       0 |    -   (no price)     |       -
  price_ceiling   |     534 |    247 |    83 |     451 |   379 / 0             |     +122.80
  ev_floor        |       0 |      0 |     0 |       0 |        -              |      -
  early_once      |      51 |     37 |    51 |       0 |    -   (no price)     |       -
  staged_none     |       2 |      2 |     1 |       1 |    -   (no price)     |       -
  early_cheap     |       1 |      1 |     1 |       0 |    -   (no price)     |       -
  early_wide      |       6 |      6 |     2 |       4 |    -   (no price)     |       -
  hedge_wait_normal|       0 |      0 |     0 |       0 |        -              |      -

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
