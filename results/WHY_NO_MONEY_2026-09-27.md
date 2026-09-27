# WHY THE BOT STOPPED MAKING MONEY -- 2026-09-27

Written for the operator after the -$165 night of 09-26/27. Every dollar below is
OUR OWN FILLS from Kalshi's ledger (970 crypto up/down markets, 09-09..09-27 ET,
$621 total, tied to the ledger to the cent on every day). Nothing here is priced
from trades we did not make. Six angles were run, each was attacked by three
independent checkers, and a seventh checked what all six missed; what survived
is below, what died is named so nobody re-runs it. Long tables and scripts:
`scratchpad\why\*` (see the file list at the end); week arithmetic: `why\synth\week.py`.

"Week 1" = 09-09..09-17 ET (the week that made money). "Week 2" = 09-18..09-27.

---

## 1. THE DIAGNOSIS (8 lines)

1. **The bot picks as well as it ever did.** Week 1 lost 11 markets of 471 (2.3 in 100); week 2 lost 10 of 499 (2.0 in 100). Nothing broke in the picking.
2. **What changed is the size of one loss against the size of one win.** A winning market paid $1.69 then and $1.93 now (+14%). A losing market cost $25 then and $80 now (3.2x). One loss used to wipe out 15 wins; now it wipes out 41.
3. **The loss grew because the bet follows the bank** ($190 -> $1,150; 40 -> 61 contracts a market), and the two worst markets were DOUBLE bets: two full-size orders in the same second on one BTC market (176 contracts 09-23, -$130; 198 contracts 09-27, -$132). A single-size loss is about $80-95; those two were the whole gap between the weeks.
4. **The win did not grow because the cheap contracts are gone and we buy dearer.** Average price paid rose 95.1c -> 96.4c, so a win pays 3.0c a contract instead of 4.2c (a quarter less). Offers under 97.5c at the moment we fire went from 30-68 contracts a day (09-14..16) to zero on 9 of the 10 days since 09-17. Two thirds of week-2 markets are now the 45-seconds-left leg, which buys a third of the bet at 97c.
5. **Money: week 1 +$545 ($61 a day); week 2 +$76 ($8 a day).** Take out the two bad nights (09-19 -$223, 09-26/27 -$149) and week 2 made $53-57 a day, the same as week 1. Ordinary days are fine. Each bad night ate about 3.5 ordinary weeks.
6. **Insurance (the hedge) is roughly break-even, not a leak:** -$29 lifetime (13 real saves +$234, 9 false alarms -$263); +$41 in week 1, -$70 in week 2. All three week-2 false alarms were photo finishes -- the price a hair over the line -- at 88-104 contracts each ($172 together). They cost more now only because the position is bigger.
7. **The bank arithmetic nobody had written down:** for every $100 bet, week 1 kept 39 cents; week 2 keeps 2 cents, with the same 6%-of-bank swing on every loss. At 50 markets a day that is about $11 a day expected against a day-to-day swing of about $85. A week is a coin flip at that ratio. A bigger bet buys more swing, not more return.
8. **No rule that "identifies the loser" holds in both weeks.** Every candidate (toxic cell, big wall at the touch, the 45-second confidence cell, BTC, the 98c band, the 0.998 belief bin) is one to two events, fitted after seeing them. That is the honest answer to "identify better": the record cannot yet.

---

## 2. THE POLICY, ranked

Money is valued only by shrinking or removing entries we actually made (hedges follow the position). "On top of live" means on top of what the bot runs right now (toxic gate since 05:08Z, 97.8c ceiling since 07:05Z). Every number is in-sample: the rule was written after the losses it removes.

### P1 -- ONE MARKET NEVER HOLDS MORE THAN ONE FULL BET (deploy tonight; code change)
Refuse the second full-size order sent in the same second on a market that already holds a full bet. Today one market may hold two (`--max-per-market 2`).
- **Money:** all +$107 (week 1 -$13, week 2 +$120). Losses shrunk: BTC 09-23 and BTC 09-27 (-$131 removed together). Winners given up: -$22 (7 double-bet winners, $4-16 each). **On top of live: +$43-51**, all of it 09-23 (09-27 is already refused by the toxic gate).
- **Per day:** 09-19 $0; 09-23 -$42 -> about +$9; 09-26 $0; 09-27 -$149 -> about -$83 (but the toxic gate already gets that one).
- **Downside if wrong:** about $1.50-$2 a day of winning double bets (week 1: -$13 over 9 days). Nothing else.
- **Why it ranks first anyway:** it is not a money claim, it is a size-of-the-worst-market claim. Today the worst market can be two bets = $193 at 198 contracts; after, one bet = about $95. It also halves the biggest hedge false alarm, because the hedge is the same contracts. It gates no hedge, needs no new signal, and does not fight any pre-registered test (it confounds the 97.8c watch by about $2 a day -- say so in the version entry).
- **How:** NOT the flag `--max-per-market 1` -- that also kills the 45-second leg's top-up (+$56 over the record) and the late add (+$10). Two lines in `rebuy_ok` (refuse after the top-up / late-add returns), entry path only, plus its startup self-test, a `results/VERSIONS.md` entry at deploy, `python research/versioncheck.py`.

### P2 -- ALREADY LIVE, read them, do not add to them
- **97.8c price ceiling (v-ceiling978, live 07:05Z).** All +$77 (week 1 +$26, week 2 +$51); the only rule positive in both weeks, but luck alone spans about ±$170 so the money is not distinguishable from zero. Stake -32% (15,900 fewer contracts at 98c). Per day 09-19 +$75, 09-23 -$25, 09-26 +$80, 09-27 -$1. Read: contracts a day should fall about a third; income a day should not fall.
- **Toxic gate (v-toxic-live, live 05:08Z).** All +$354 (week 1 -$50, week 2 +$404). Per day 09-19 +$371, 09-23 -$3, 09-26 -$30, 09-27 +$132. Idle cost about $8-17 a day in a quiet week; that is the price of the test. Read 10-01 as pre-registered.

### P3 -- INSURANCE ONLY WHEN THE PRICE IS CLEARLY THROUGH THE LINE (pre-register now, read live, no code until it passes)
Keep the 0.40 trigger, but skip the hedge when the projected settle is less than 2 rounding steps (2 cents for BTC/ETH/BNB) past the strike against us; a stale index counts as "hedge".
- **Money:** +$151 vs today's rule (week 1 $0 -- it never fires in a quiet week; week 2 +$151). Removes all 3 false alarms (+$172: XRP 09-19, BNB 09-26, ETH 09-27), gives up 1 real save (-$21, BNB 09-19 12:30). Per day 09-19 -$174 -> -$127; 09-23 unchanged; 09-26 +$47 -> +$105; 09-27 -$157 -> -$111.
- **Downside if wrong:** a market that goes a hair through the line and STAYS lost gets no insurance: about -$60 more per wrong skip at today's size, against +$46-67 per right skip. Break-even: skipping pays if hair-over crashes come back more than 31 times in 100.
- **Why not deploy:** it is 3 events on 3 nights, threshold picked after seeing them; the record can only tell a $372 difference from luck. The index feed (all markets, not our fills) says hair-over crashes come back 47 in 100 vs 23 in 100 for deeper ones -- the right direction, but a 7-in-100 chance of luck, and the model's own uncertainty ruler (skip under half a width) separates better there (1 in 100). **Pre-register BOTH rulers now.** No paper arm needed: the live bot hedges every such alarm, so each hair-over alarm is an exact reading. Bar: 5 hair-over alarms with the settle side recorded (about 17 days at the recent rate).

### P4 -- DEAD on our fills (do not re-test without a genuinely new angle)
| rule | why dead |
|---|---|
| Big wall at the touch (offer >= 10x our order): cap or skip | every loser sits within 0.35 of the 10x line; at 10.5x its week-2 money falls from +$229 to +$66; a threshold placed on the losers |
| Refuse markets the 45-second look called uncertain, bought at 21-30 s | week-1 holdout LOSES $170; in the good week the whole profit came from markets that became certain late -- late certainty is the edge, not the danger |
| BTC-only cap of 40 contracts | -$100 on top of the live rules: all four week-2 BTC losers are already refused; worst-of-12-coins chance about 1 in 1 |
| Skip BTC | 6 losers in 167 markets is chance; one series of nine looked at |
| Cap every market at 40 / 80 | -$88 / week 1 -$30; gives up more winners than it saves |
| Sweep limit 97.5c | -$56 (-$47 week 2): removes 46% of stake, the ceiling at 97.8c is the honest version and is live |
| Max 2 coins per close / no extra coin | 0 losers among 3rd markets in 700 closes, -$57 |
| Turn the 45-second leg off | paper arm without it made $22 vs live $90 on the same 43 hours; it adds markets |
| Skip the jumpiest coins by last 7 days; resting bids; book-confirmed hedge alarm; no hedge inside 5 s; 10c cap at every second; entry margin floors | negative in both weeks or one event (already in IDEA_LEDGER R02-R14, P01-P09) |

---

## 3. WHAT A NORMAL WEEK LOOKS LIKE (from the 19 recorded ET days, reshuffled 20,000 times; `week.py`)

| | as banked | with P1 on top of live (09-23 +$51) | if every fitted rule had been on (NOT a forecast) |
|---|---|---|---|
| average day | +$33 | +$36 | +$67 |
| middle day | +$54 | +$54 | +$81 |
| worst day on record | -$223 (09-19) | -$223 | -$19 |
| typical week (7 days) | +$257 | +$277 | +$466 |
| chance a week loses money | 16 in 100 | 14 in 100 | ~0 |
| days worse than -$140 | 2 of 19 | 2 of 19 | 0 |
| chance a week holds a -$140-or-worse day | 54 in 100 | 54 in 100 | ~0 |

Read the third column as the proof the rules were fitted to the 21 losses: a
stack that erases every losing day on the record is describing the past, not the
future. The honest forward number is the first two columns, and the average-day
figure leans on week 1 (small bank, cheaper fills, 9 of 19 days). Week 2 alone
averages $8 a day ($13 with P1) with a 52-in-100 chance of a -$140 day in any
week. **Expect $10-55 a day depending on whether a bad night lands; the record
has one bad night per 9-10 days; P1 makes the worst single market about $95
instead of $193 and does nothing to how often one happens.**

---

## 4. IDEAS FROM THE DIFFERENT ANGLES THAT SURVIVED, and what a $20 test looks like

1. **Full-size 45-second leg.** `arm-live-frozen` (09-20 settings, full early bet) is +$98 ahead of live on the same 88 markets over 43 hours -- paper fills at the ask, one no-loss window, and 09-19's $403 fell in the four days the early leg ran full size. Test: relaunch `arm-early-full` paper; read only against a night with a loser. $0 at risk.
2. **The other two thirds never get bought.** 328 week-2 markets opened with a third-size early leg; only 28 ever topped up. Nobody knows whether the price ran past the ceiling, a gate refused, or the supply was not there. Measurement from our own logs, $0; it decides whether the win can be grown at all.
3. **Huge cheap wall far below our belief** (BTC 09-23: 176 contracts swept 86c->87c into a ~2,000-lot wall with 12c of headroom, missed by the toxic gate: sellers only 34 in 100). One event. Pre-register "cap sweep headroom when the touch shows >= N contracts" before valuing; paper arm, $0.
4. **The spike gate refused BTC 09-27 at 32 s and the bot bought at 30 s.** One event. Measurement: how often an entry follows a spike refusal within 5 s, and how those markets did. $0.
5. **Our share of the cheap supply.** Offers under 97.5c fell 54% while our order grew 4x. From the trade tape: what fraction of the taker volume under 97.5c each day is us. Decides whether the price rise is the market or us. $0.
6. **Insurance ruler (P3):** the $20 test is free -- each hair-over alarm the live bot already hedges is a reading.
7. **Collector gap 09-23 23:00Z-09-24 01:00Z:** no index prints, so the -$130 loss cannot be examined; check what else that gap hides before the next post-mortem depends on it.

Not a test: anything BTC-specific (three events), a bigger bet (buys swing at 2 cents per $100), a second insurance rule change before P3's bar is met.

---

## 5. WHAT 21 LOSSES CANNOT TELL HIM

- Whether the bot has ANY edge at 97c and up at today's size: contracts lost 2.9 per 100 against a 3.6-per-100 break-even at 96.4c, and with 10 losing closes the range straddles break-even. Week 1 at 95.1c was clearly positive; week 2 is not distinguishable from zero.
- Whether any rule that removes one or two losers is real. A rule needs about 400 markets (60-160 days at today's pace) to tell 5 losers per 100 from 2.
- Whether the toxic gate is real (its quiet-week half is negative; 10-01 read), whether the insurance ruler is real (3 events), whether BTC is special (chance about 1 in 1 for the worst of 12 coins).
- Whether the cheap supply comes back. If it does not, the honest forward number under everything live is $8-45 a day with a $70-95 loss per event at today's bank, and two events are possible in one night; nothing in the record supports promising more.
- What the two weeks' size steps did on their own: 09-18/19 changed three rules at once (1.5x late boost, third coin, 96.5c early floor), 09-20 halved the bet's share of the bank, 09-22 cut the early leg to a third; size is not the only thing that changed at the split.

---

## Files
Angles: `why\size-vs-edge\SIZE_VS_EDGE*.md`, `why\loss-anatomy\LOSS_ANATOMY_tables.md`, `why\hedge-economics\HEDGE_ECONOMICS.md`, `why\when-money\WHEN_MONEY*.md`, `why\different-angle\DIFFERENT_ANGLE_2026-09-27.md`; refutations `why\refute-*\`; critic `why\critic\CRITIC.md`; this section's week arithmetic `why\synth\week.py` (self-test: planted days, empty world, 00:00 ET close stays on its day). All under `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\`. Recorders alive after every job (kalshi_collector ~28 MB, crypto_feeds ~19 MB); free disk 69.4 GB; `C:\kals` read-only; no orders sent; no replay used for money.

---

## What I need from you

1. **P1 tonight -- yes or no:** change the bot so one market never holds more than one full bet (code change in `rebuy_ok`, not the flag; costs about $2 a day of winning double bets; caps the worst market at about $95 instead of $193).
2. **P3 pre-registration -- yes or no:** write down now that we will read the next 5 hair-over insurance alarms under both rulers (2 rounding steps; half a model width) before any change to the hedge rule; no code, no risk, about 17 days.
3. **Paper arm `arm-early-full` -- relaunch, yes or no** (full-size 45-second leg, paper only, read against the next bad night).
4. **Bet size while the reads run:** keep SIZE = bank/12 (grows with the bank; more swing at 2 cents per $100) or freeze the bet at today's size until the 97.8c and toxic reads land -- your call, it is a risk setting you set.
