# PROJECT MAP 2026-09-22 -- where the money went, verified

Eight investigators, a second-by-second autopsy of every losing close, a
market/competition sweep, 18 adversarial verifiers and a completeness critic.
Every dollar is Kalshi's own ledger (`results/kalshi_ledger.json`, via
`research/pinledger.py`); decisions from the 124 live logs. Tape/replay items
are labelled. Detail: `results/map_2026-09-22/` (01-11, autopsy/, verify/).

## The answer, additive (11_critic G1, ledger, n = closes)

| since the 45 s leg went live (09-17 13:05Z), 203 closes | $ |
|---|---|
| actual | **+$60.95** |
| at the steady era's rate (09-13..09-17, 152 closes, +$2.56/close) | +$520.01 |
| **shortfall** | **-$459.06** |
| losing closes BIGGER than the steady era's average loss (-$17.20) | -$367.18 (80%) |
| winning closes paid less ($2.90 vs $3.23) | -$64.87 (14%) |
| more losing closes (8 vs 6.7 expected) | -$27.02 (6%) |

The -$367.18 by cause: hedge never ran (crash, loss-cap pause) -$135.84 FIXED;
false-alarm hedges on two WINNING bets (09-19 23:45) -$91.67 **OPEN**;
phantom-depth sizing -$44.56 FIXED; hedge refused by the price gate -$40.56
REMOVED; adverse fill + A76 waited (NEAR 09-21) -$41.89 REMOVED; ordinary late
moves -$12.66 (the strategy's cost). **68% of the shortfall is ET 09-19.**
Since the fixes (09-20 00:00 ET): 75 closes, **+$114.01, +$1.52/close** --
positive, below the steady era, on 2 losing closes (not significant).

## What is verified (verdict in brackets)

1. **Loss SIZE, not loss frequency** [confirmed across 01/05/10/critic]. Loss
   rate on our fills is flat (~2.5-3%); contracts per market 27 -> 74 (bank
   growth incl. the $370 deposit; bet/bank ratio actually fell).
2. **The steady week was a calm market** [C8 weakened-but-holds]. Takers'
   upset rate at 90c+ in the last 45 s fell on 09-15..18 (mostly 09-16/17)
   and is back to normal. Our 3 losses in 202 there were ~1-in-3.5 luck.
3. **The model is ~9x overconfident on our fills** [C2 confirmed]: 19 of 747
   markets lost (2.54%) vs 0.285% implied; flat across confidence bands (AUC
   0.53). Raising --pin cuts losses only in proportion to trades.
4. **The 45 s leg is thin, not clearly negative** [C1 weakened x3]. Ledger
   -$57 to -$70 since 09-17, but the deficit is one day (09-19) and mostly
   hedge failures/bugs on early positions; early ENTRIES are ~break-even
   (-$18.67 on 12,871 contracts). Post-fix: +0.71c/contract (+$32 on 70
   markets) vs +3.92c (+$82 on 36) for <=30 s. **It mostly ADDS markets:
   80% (163 of 203) were never offered at 90-98c later** [critic G2] -- off
   means losing them, not handing them to the <=30 s window. It explains 75%
   of the rise in average price paid (~$28/day) [G3].
5. **Fills >=2c below the ask seen lose 7 of 27 closes vs 12 of 520**
   [C6 confirmed, p 1e-5] -- the market moved in the ~100 ms before our order
   landed. They lose about as often as their lower fill price says; cost
   -$102.69 lifetime. Visible only after the fill: a hedge trigger candidate,
   not an entry gate; cannot be priced yet (no insurance quote logged).
6. **Early buys on offers <250 ms old: 6 of 86 lost vs 0 of 117** [C5
   weakened]. Real in the data, chosen after looking, fails the multiple-looks
   bar, 6 losing closes. Needs a pre-registered live/paper test.
7. **Decisions were made on wrong numbers** [C3 confirmed]. The bot's logs
   (and pinday) miss every market held when a run died: 09-19 -$161.14 in the
   logs vs **-$223.46** on Kalshi; lifetime the logs overstate profit by
   $72.34. v-nocap kept/enlarged the early leg on "+$110.67"; Kalshi said
   -$68.78. hedgetune (v-hedge25) priced on the recorder's receive time (2-6 s
   late), no staleness guard, hedged before entry, top level only [C9
   confirmed]: 0.25 beats 0.60 by ~$8-46, not $97; PREREG_hedge's "not below
   0.30" was bypassed. v-cheap's own undo bar fired and was ignored [C4:
   what the looser cap admitted is -$35.40, below the floor].
8. **Change velocity made every change unjudgeable** [07]: 52 behaviour
   changes 09-12..09-21, median 3 closes each; 13 on 09-19. All 3 in-loop
   crashes came from new code.
9. **Hedging lifetime: -$9.35** [C9 exact]: 10 saves +$149.26, 7 false alarms
   -$158.60. Decided by one close (09-19 23:45).

## Latent -- verified with offline harnesses (not yet cost money)

- **K1** no self-test runs the loop; an exception in the entry scan or hedge
  pass ends the process while holding (3 crashes so far, one cost -$66.34).
- **K2** one timed-out/5xx/odd order reply halts pintake and every later
  HEDGE in that close is refused (13 harness cells). Last night's outage
  (388 failed calls) is a realistic trigger.
- **K3** the hedge pass never reads index age: a frozen index holds belief
  at its entry value -- no alarm, no hedge, often no hedge_blind record.
- **K4** the 20% drawdown brake trips at a bank of **$767.12** ($150.80
  below the last read), terminally: each watchdog restart re-halts until a
  human edits `pinrun-hwm.json`. 18 of 19 "external transfer" records are
  other bots' money (oil, coin race), not the operator.
- Paper arms read the LIVE day-loss file (a -$200 live day kills the fleet).
- KalsBoot runs only while Joe is logged on; auto-logon is off -- after a
  Windows reboot nothing restarts until he logs in.
- Disk: ~4.8 GB/weekday; 6 GB guard ~09-27.

## Refuted

- "The market got worse" (09). "The early leg pays more for the same
  market" (+0.16c mean, -0.04c median). "The early leg displaced the <=30 s
  window" (80% not buyable later). "Sweeping deep is the leak" (+2.02c per
  contract above the touch). "Exchange feeds would have warned us" (covered by
  the jump gate). 08's -$270.91 / -$384.15 (Kalshi `revenue`=0 on hedged
  markets). "0.60 hedge was worse than never hedging."

## Open, unmeasured -- and where "make more" may be

The <=30 s window's volume fell 65% (2,654 -> 936 contracts/day) while tape
supply was flat; displacement explains ~20% at most. Those contracts earn
+3.1 to +5.6c each. Arithmetic upper bound ~$50-60/day. The refusal log is
de-duplicated and `close_summary` is not split by seconds-left, so the cause
needs a LOG FIELD, not more analysis.

## Solutions (status)

- BUILDING (worktree, adversarially reviewed before deploy): K1 loop guard +
  fill registered before logging; K2 hedges bypass the pintake halt; K3 stale
  index -> hedge_blind + market-price fallback; paper arms' day-loss only when
  live; logging (tau + budget on refusals/signals, ms decide/send times,
  per-second insurance quote while holding); pinday money from the ledger.
- OPERATOR DECISIONS: the 45 s leg (keep / a third size / off); the drawdown
  brake (see all bots? auto-clear?); KalsBoot "run whether logged on" (needs
  his Windows password) or auto-logon; a change freeze (~300 closes, bug
  fixes only) with pre-registered bars checked against the ledger.
- TEST, DON'T DEPLOY: the fresh-offer rule (C5) and the post-fill collapse
  hedge trigger (C6), pre-registered, on live logging first.
