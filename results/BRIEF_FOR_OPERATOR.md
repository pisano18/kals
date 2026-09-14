# Brief for the operator — written 2026-09-13 11:3x PM ET, to be read to him when he is back

He said: *"Remember everything you're saying and know I'm not reading it,
you'll have to tell me again when I'm back."* This file exists so that briefing
survives a `/clear` or a compaction. **Read it out, then delete it.**

---

## 1. What he asked for and what he got

| he asked | status |
|---|---|
| Allow same-coin double buys | **LIVE** (`--max-per-market 2`) |
| Buy smaller when the full size is not available | **LIVE** (`--min-fill-frac 0.10` — floor fell from 26 contracts to ~5) |
| Top up a part-filled coin when more appears | **LIVE** (AMENDMENT 29 — no price-improvement needed below a full size) |
| Keep BANK_BRAKE at 3 | **unchanged** |
| Re-size immediately on a loss | **LIVE** |
| Stop at 1/5 of bank OR 3 losses, whichever first | **LIVE** |
| Reset the 1/5 when the balance recovers | **LIVE** (high-water mark on disk) |

Live command:
`--live --size 20 --minutes 4320 --loss-abort -60.00 --max-positions 3
--max-losses 3 --improve-scope market --pick best --max-per-market 2
--improve-max 0.010 --min-fill-frac 0.10`

## 2. The three things he most needs to hear

**(a) Break-even was WRONG in our own notes, and the correction is good news.**
It said 3.58%, which assumed no hedge and every loss total. Computed from our
actual closes it is **8.55% all-time, 19.11% over the last 100**. We lose
**4.31%**, 95% range **[2.09%, 7.78%]**. The worst end is still under the most
conservative break-even, so **the strategy is profitable at 95% confidence** —
the old figure said it was not. What is genuinely uncertain now is the *size*
of a loss (ten events, fat tail, worst −$52.60), not the rate.

**(b) I took the bot down for ~3 minutes.** The new drawdown brake tripped on
its first start because a self-test feeds it a fake $1,000,000 bank and the new
code wrote that into the real high-water file. No position open, nothing traded
in the window. Fixed by isolating tests from production files, with a test that
fails if they can ever reach them again. I also tried a narrower fix first that
would have sent the *live* high-water mark to a temp file — caught before it
ran.

**(c) Two live bots traded his account for 24 minutes earlier** (20:35–20:59
ET). The restart script matches processes on a command-line field Windows
returns EMPTY to a caller that cannot open the process, so its kill matched
nothing and it started a second bot. **Nothing traded in the overlap.** Fixed:
the bot writes a pid file and refuses to start a second live copy; the script
proves the old one is dead by pid and aborts rather than falling through.

## 3. Answered earlier, still worth repeating

- **His max loss:** one worst close is **$101.92 = 33% of a $310 bank**. Three
  of them is 99% — which is why the new 1/5 brake matters. To cap a worst
  close at 1/5 he would need **31 contracts** (`BANK_BRAKE 5.0`,
  `size = bank / 9.8`). He chose to leave it at 3.
- **A tighter brake buys a smaller hole, not a faster recovery.** Measured on
  695 closes: 3.0 → 4.0 cuts earnings 24% and improves recovery 2.5 → 2.4 days.
- **Kalshi lists no perpetuals** — 0 hits across 60,000 open markets for
  "perp"/"funding". He says there is a section; he owes me the name it is
  listed under.
- **Hourly markets:** books ARE quoted through the close (68–94% of reads carry
  an ask, against 56–94% on ours). An earlier "0 of 612" was a bug in the
  probe's own strike selection. Still untested: whether anyone sells the
  *winning* side at a price we would pay. Best untested lead.

## 4. Open decisions for him

1. **When the drawdown brake trips it stays stopped until he restarts it.** He
   said "wait"; with him away that was the safe reading. Does he want an
   automatic resume after a cooldown instead?
2. **BANK_BRAKE stays at 3** (worst close 33% of bank). 5.0 would make it 20%
   for ~40% less earning. His call, already deferred once.

## 5. Running right now

Live bot, plus four paper arms: old buy-order (control for `--pick best`),
same-coin re-buy, low depth floor, and pin 0.990. Collector and feeds alive
since Sep 9. The per-gate tracker (AMENDMENT 25) is recording — first real
per-close reasons are arriving.
