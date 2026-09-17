# PRE-REGISTRATION -- THE COMMODITY PENNY TEST (`research/cmdlive.py`)
## Written 2026-09-17 ~16:1xZ, BEFORE the first live commodity order

**Rule (CLAUDE.md amendment 2026-09-10, item 4): the bar is written before the
number is seen.** Nothing in this file may be edited after the first fill
except to record what happened; a moved bar gets its own dated amendment,
stated loudly.

**Sign-off (hard rule 1, as narrowed 2026-09-06):** the operator, 2026-09-17:
*"I'm ready for commodity penny testing."* That is the per-instance sign-off
for this run. It is enforced in code: production arms only when BOTH `--live`
and `--signoff "commodity penny test"` are given.

## Why live at all, when the paper arm has barely started

Because the paper arm cannot answer the question, and never will. It records
"an offer sat there inside the window". Live records "somebody chose to sell
it to us". On crypto those two populations differed by **31x** in loss rate
(tape 0.11%, live 3.4%, 2026-09-11, intervals not overlapping), and the gap IS
the loss class that hurts. Paper can KILL this idea. Only fills can pass it.

The operator was told the paper arm would run ~40 bets first and chose to go
sooner. That is his call and it is recorded here rather than quietly adopted.
**The paper arm keeps running as the control**, on the same windows by import,
so the two populations can be compared directly at the end.

## What it risks, exactly

| cap | value | why |
|---|---|---|
| contracts per order | **1** | the whole point; `--size` refuses above 5 |
| total cost, whole run | **$10.00** | counted from FILLS, not intents |
| orders that reach the wire | 60 | a refused-order runaway once sent 160 in one close |
| losses | **2, then it stops itself** and writes the stop file | lose less first |
| account floor | $300 | the crypto bot's working capital is not available to this test |
| seconds left | never under 2 | an order later than that can land after the close |
| price | 90-99c only | outside that the window is not the window |

Worst case the operator can suffer is the $10 ceiling. Realistic worst case is
the 2-loss brake at about **$2**. Balance at the start: $578.99.

It also stops when the desktop app's `results/pinrun-live.stop` appears, so
standing the crypto bot down stands this down too.

## The windows, and where they came from

Imported from `cmdarm.BANDS` **by reference**, so the live test and the paper
control cannot drift apart. They are the grid's BY-MARKETS table (rule 4:
cluster by close; the first cut counted trades and three big markets made a
cell look safe), `results/RESULTS_grid.md`, 5 days:

| series | window | tape evidence, by markets |
|---|---|---|
| GOLD near | 2-15 s, 90-99c, **skips 08-14 ET** | outside the COMEX session 117 markets / 0 lost; inside it 32 / 2 |
| GOLD far | 91-180 s, 98-99c | **129 markets / 0 lost** -- the safest cell found anywhere |
| WTI | 2-60 s at 95-99c; 2-45 s at 90-95c | 153 / 3 (2.0%) against ~3% break-even |
| SILVER | 2-5 s, 90-99c | **74 / 4 (5.4%) -- the NEGATIVE control** |

**Silver is in the test to fail.** If silver comes out ahead, the test is
measuring something other than what it claims to.

## THE BAR, fixed now

Scored over the first **30 filled orders**, or 5 trading days, whichever comes
first. Every count is markets, never trades (rule 4).

**KILL -- stop, and commodities go back to paper only:**

1. **3 or more losses in the first 30 fills** (10%). Break-even at 95c is 1 in
   20; at 98.5c it is 1 in 67. The automatic brake is tighter still and fires
   at 2, so in practice this bar is reached by the brake first.
2. Net negative after 30 fills.
3. **Silver's loss rate is at or below gold's and WTI's** over the same
   period with at least 10 fills each. That means the screen is not reading
   the world.

**PROCEED to a larger size (and only then):**

1. At most 1 loss in the first 30 fills, AND
2. net positive, AND
3. **the fill rate is high enough to matter**: at least 20 fills out of the
   attempts the windows generate. A window that never fills is not a strategy,
   and this is the number the paper arm cannot produce.
4. Silver behind gold and WTI, as the control predicts.

Anything in between: keep running at one contract to 60 fills and read again.
**No size increase without a fresh sign-off from the operator**, whatever the
numbers say.

## What gets recorded, so the read is not a reconstruction

`results/cmdlive-<ts>.jsonl`, one line per event: `start` (every cap and the
opening balance), `look` (a close passed, did we bet), `refused` (with the
exact reasons), `order` (the whole pintake response, ask seen, latency, book
age, spend after), `settled`, `brake`, `end`. The fill rate is
`order` records with a fill over `order` records total. The loss rate is
`settled` records.

## Revert

```
type nul > C:\kals-repo\results\cmdlive.stop
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ? { $_.CommandLine -like '*cmdlive.py*' } | % { Stop-Process -Id $_.ProcessId -Force }"
```

The stop file alone is enough: the loop checks it before every order and at
the top of every pass. Deleting the file is what allows a restart.
