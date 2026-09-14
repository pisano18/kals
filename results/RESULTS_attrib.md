# RESULTS_attrib -- what each gate in the bot actually did

```
  EVERY GATE IN THE BOT, IN THE ORDER IT IS ASKED

  A gate only gets asked if every gate above it said yes, so a quiet
  row near the bottom may just mean the rows above got there first.

  gate            | stopped | closes | only  | really  | of those blocked      | $ if we had
                  |  it     |        | moved | blocked | would WIN / would LOSE|  been filled
  ----------------|---------|--------|-------|---------|-----------------------|-------------
  close_budget    |       0 |      0 |     0 |       0 |        -              |      -
  max_per_close   |       0 |      0 |     0 |       0 |        -              |      -
  max_per_market  |       0 |      0 |     0 |       0 |        -              |      -
  both_sides      |       0 |      0 |     0 |       0 |        -              |      -
  market_attempts |       0 |      0 |     0 |       0 |        -              |      -
  attempts_cap    |       0 |      0 |     0 |       0 |        -              |      -
  book_suspect    |       0 |      0 |     0 |       0 |        -              |      -
  book_stale      |       0 |      0 |     0 |       0 |        -              |      -
  index_stale     |       0 |      0 |     0 |       0 |        -              |      -
  no_sigma        |       0 |      0 |     0 |       0 |        -              |      -
  confidence      |       0 |      0 |     0 |       0 |        -              |      -
  no_offer        |       9 |      1 |     0 |       9 |    -   (no price)     |       -
  depth_floor     |       0 |      0 |     0 |       0 |        -              |      -
  edge_floor      |       0 |      0 |     0 |       0 |        -              |      -
  dump_guard      |       0 |      0 |     0 |       0 |        -              |      -
  improve_by      |       0 |      0 |     0 |       0 |        -              |      -
  rebuy_band      |       0 |      0 |     0 |       0 |        -              |      -
  price_ceiling   |       0 |      0 |     0 |       0 |        -              |      -
  ev_floor        |       0 |      0 |     0 |       0 |        -              |      -

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
    dump_guard       priced far below fair -- someone else knew something
    improve_by       a second buy that was not cheaper than the first
    rebuy_band       a same-coin re-buy outside the 0.5-1c band
    price_ceiling    priced above the 98c ceiling
    ev_floor         expected value negative at that price
```
