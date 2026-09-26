---
name: never-quote-a-bank-delta-as-profit
description: "Deposits must come from Kalshi's own records via pinxfer - three tools reported a $370 deposit as profit, and the bot's classify_bank_move still invents fake transfers"
metadata: 
  node_type: memory
  type: project
  originSessionId: 350e3ea1-7f0f-4b66-8f90-c31872b59750
  modified: 2026-09-25T07:10:28.379Z
---

**`research/pinxfer.py` reads `/portfolio/deposits` and
`/portfolio/withdrawals` and is the ONLY authority on money in and out.**
Before it existed, three separate tools reported the operator's $370.44
deposit (09-19) as profit -- the desktop app showed a >100% return and the
telegram bot showed 192%.

Money in: **$584.46** (7 deposits, net of $8.14 fees, last one 09-19),
**ZERO withdrawals ever** (`results/kalshi_transfers.json`, fetched 09-24
07:06Z). Money made, Kalshi's ledger: +$333.49 at 09-22 (the 09-21 "~$387" was
wrong); lifetime +$437.82 over 1,101 markets at 09-25 05:49Z. Quote only the
ledger (`research/pinday.py`, `results/kalshi_ledger.json`).

**`pinrun.classify_bank_move()` INVENTS TRANSFERS and this is still live
(open as of 2026-09-25).** It infers them from balance movements, and
**`realised` resets to zero on restart**, so any trading P&L straddling a
restart reads as money moving. It fabricated a **$58.37 withdrawal that never
happened**; `shift_hwm()` then moved the drawdown high-water mark by it to
$1046.43 -- a level the balance never reached -- and the brake halted the live
bot on a partly fictional drawdown that **could not clear, because a halted
bot cannot earn the balance back.** Two hours of trading lost. **Open: make it
consult `pinxfer` first.** (v-hwm-reset, 09-24, lets START on the app re-base
the mark, so a halt no longer needs a hand-edit of pinrun-hwm.json.)

Related accounting traps:
- **Never sum `realised`** from settled records -- running total, resets on
  restart. Per-market money is `pnl_c` in cents. See [[paper-log-money-fields]].
- **A hedged market writes TWO settled rows.** Sum, never overwrite.
- **A leg sum is not a day.** `pinfloor`-style leg sums under-reported 09-19;
  the bot's own logs miss markets held when a run died (09-19 is -$223.46 on
  the ledger, not the logs' -$161.14). Kalshi's settlement books are the only
  day figure to quote.
