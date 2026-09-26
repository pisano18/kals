# PICK UP HERE -- 2026-09-26 ~07:30Z -- end of the 09-24..26 session (context gone after this)

**A new session: read this whole section first.** Then `CURRENT_STATE.md`, then
`OPEN_WORK.md` (the operator's topic index; he names topics by their "Say:"
handle), then `results/IDEA_LEDGER.md` (every money idea ever checked -- read it
before proposing one). All times below are UTC; say them to him in ET (EDT =
UTC-4). His reporting rules are in CLAUDE.md: plain language, short, reason
first, anything he must do in a final `## What I need from you` section.

## 0. What the operator said in his LAST message (2026-09-26 ~07:2xZ) -- act on it

1. **"Yes combine all the cash."** -> job P1 below.
2. **"Run the reward test."** -> job P2 below (APPROVED by him; blocked only by
   the permission rule, see P0).
3. **State and sportsbook history:** "Virginia I think. I've had a DraftKings and
   FanDuel account, maybe probably not BetMGM, and definitely no Caesars or
   Fanatics." (Virginia has legal online sportsbooks, so the prediction-app
   sign-up bonuses that need a no-sportsbook state do not apply; DK/FD new-user
   bonuses are used. Kalshi sports orders were accepted from Virginia on 09-06.)
4. **"Can coin race scale up yet"** -> answered: NOT YET (section 4, B1).
5. He had NOT yet run the Polymarket 1-cent wire test (his first try named a
   closed window; the rails refused it -- correct).
6. **"give another [command] that'll be a permanent fix and I'll do it"** -- the
   permission rule in P0. He said he would run it.

## 1. Pick-up jobs, in order ("Say:" phrases he can use)

- **P0 -- permission rule (he runs it; never edit permissions yourself).** Claude
  Code's auto-mode classifier blocks real-money orders from the Bash tool
  ("Real-World Transactions") even with his chat "yes". He was given this
  one-liner to run in the terminal (it appends two allow rules to
  `C:\kals-repo\.claude\settings.local.json` and keeps the existing ones; tested
  on a copy):
  `! python -c "import json;p='C:/kals-repo/.claude/settings.local.json';d=json.load(open(p));a=d['permissions'].setdefault('allow',[]);[a.append(r) for r in ('Bash(python research/polyorder.py:*)','Bash(python research/ordercli.py:*)') if r not in a];json.dump(d,open(p,'w'),indent=2);print(a)"`
  Check first: `cat .claude/settings.local.json` shows both rules. **The rule only
  matches a command that STARTS with `python research/polyorder.py` or
  `python research/ordercli.py`** -- no `cd ... &&`, no `PYTHONIOENCODING=...`
  prefix, no `timeout`. If it is not there, ask him to run the one-liner.
- **P1 -- "combine the cash" (APPROVED).** Kalshi keeps cash in pools; crypto
  orders draw only on the crypto pool. An automatic 85/15 split is on and parked
  ~$139 of the 09-19 deposit outside pinrun's reach, while pinrun sizes on the
  account total (~$1,086 vs ~$947 spendable, ~13% oversize; no harm seen yet).
  He said yes to: switch the automatic split OFF and move the money into the
  crypto pool (the sweep suggested keeping ~$60 aside for the reward test --
  only if the reward test needs a different pool; check). Kalshi subaccounts are
  API-only: read `GET /portfolio/subaccounts/balances` and the transfer history
  (`/portfolio/intra_exchange_instance_transfers`), find the documented
  endpoints for the allocation setting and a transfer, and build it on the
  ordercli.py pattern (dry-run + token). It moves his own money between his own
  pools (no market risk) but it is a write; the classifier may still block it
  -- if so, tell him it is a Kalshi-app setting or needs a rule like P0.
  Evidence: `results/IDEA_SWEEP_2026-09-25.md` "Found along the way" (N03/I49 in
  `results/idea_sweep_2026-09-25.json`). Afterwards pinrun sizes on real
  spendable cash; watch the autosize record.
- **P2 -- "run the reward test" (APPROVED).** Kalshi's liquidity-incentive
  programs pay daily pots to resting orders; 7 sweep ideas (IDEA_SWEEP rows 1-4,
  I02/I05/I16/I19/I20/I21/I22) hinge on whether Kalshi pays THIS account. Test:
  2-4 resting 1c BUY orders of 500-1,000 contracts on quiet reward markets
  (weekly politics / Trump approval / Rotten Tomatoes, early in the week; NOT
  Miami temperature -- stacks there get bought within minutes), each on the
  empty side where the program's rules pay; max ~$60 at risk (a 1c order can
  lose only its cost). Log the book every 5 min; read the balance 48-72 h later;
  keep it apart from the ~$1.2 Kalshi interest credit due Oct 1-15.
  **Pass:** credit >= 50% of the rules' prediction on >= 2 sides. **Kill:** $0
  after 72 h where >= $3/side was predicted. Tool: `research/ordercli.py`
  (always post_only, dry-run + token, `--live --signoff`). Read the program
  rules first (`/incentive_programs` or the docs; the sweep's
  `combine-wild-card/lip_status.py` in the old scratchpad read `paid_out`).
  Note the risks the sweep named: Kalshi can revoke reward eligibility; a
  resting order in a market the live bot also trades would be adopted/hedged by
  v-safety2 -- keep the reward test OUT of the bot's series (crypto 15M,
  KXBTCD, coin race) or use a subaccount.
- **P3 -- "run the Polymarket wire test".** 1 Up contract at 1c on an OPEN
  window (should not fill, <= 1c at risk) proves his key can trade. Get a fresh
  code each time (a code binds one window):
  `python research/polyorder.py --slug cpc-btc-updown-15m-YYYY-MM-DD-HHMMz --side up --price 0.01 --qty 1`
  then the printed `... --live --signoff <code>` line (window start in UTC;
  pick one with >= 4 min left). He also said "Yes do what you want on
  polymarket": after the wire test passes, Step 2 in
  `results/POLYMARKET_ORDERS.md` (20 windows x 1 contract, <= 98c; stop on 2
  losses) needs the paper bot's decision wired to polyorder -- described in
  that file, NOT built. Polymarket money: $50 promo bonus (held) + $10 Apple Pay
  deposit (was pending) + $0.52 cash. If polyorder is refused 401/403: new key at
  polymarket.us/developer -> `C:\kals\polymarket_trade_key.json`, `--creds`.
- **P4 -- ~2026-09-28 ~06Z: "read the Polymarket paper results".** Recorder
  `scan_poly_ws.py` (scratchpad, pid 3080604, ends ~09-28 06:11Z) and paper bot
  `research/polypaper.py` (pid 3088064, `--report`) -- both restarted 09-25
  22:26Z with the subscribe fix (before it, ~4 in 10 windows were missed).
  Decides whether Polymarket gets a funded leg.
- **P5 -- ~2026-10-01/02: "read the bars".** `python research/bars.py` (or /bars
  on the phone). Fixed 09-25: bars read from their pre-registered start
  (fresh test starts 09-24 08:08Z). Arms re-synced 09-25 12:25Z onto
  v-scalein-caps.
- **P6 -- "coin race size"**: not yet (section 4).
- **P7 -- rungwatch**: create `results/rungwatch.stop` (the far-rung idea is dead;
  the watcher is still running and can stop any time).

## 2. Live money right now

- **pinrun --live** pid 2951024 since 2026-09-25 12:23:53Z, code_sha
  f9548c5571ff = **v-scalein-caps** on top of **v-safety2**, v-zerotake,
  v-ladder7, v-farrung (all flags of the last two OFF). Argv = restart_bot.ps1
  (`--series KXBTCD --series-size 1`: hourly BTC at 1 contract). `--minutes 4320`
  -> exits ~09-28 12:23Z, watch_bot restarts it. Bank ~$1,086 (Kalshi total),
  auto-size ~88-90. Caps now 133.5 contracts / $544 per run (designed values).
- **Coin race live** pid 2707284 since 09-24 15:16Z, 5 contracts a leg, ends
  ~10-01 15:16Z (relaunch by hand with the v-race5 argv in VERSIONS.md).
- **Tonight's live changes (each has a VERSIONS.md entry with a revert):**
  - v-ladder7 (03:2xZ 09-25, paper only): 7 hourly ladders known to the code.
  - v-farrung (code, flags OFF): far-rung 99c code; the idea is DEAD.
  - v-zerotake (06:25Z): never send a 0-contract order (a HYPE late add on a
    1.5x-full position halted the bot at 06:15Z).
  - v-safety2 (09:36Z): asks Kalshi what it holds at startup and after any lost
    reply; books/hedges a fill it did not see; re-sends a lost hedge that did
    not fill; "0.00" orders are zero; paper bookings no longer collide. Record
    kind `ktruth`. Measured: no slowdown (near-close worst gap 994 -> 973 ms).
  - v-scalein-caps (12:23Z): a same-market scale-in needs a genuinely cheaper
    ASK (A23 used to compare against the sweep-inflated average paid: 6 such
    buys since 09-18 netted -$50.83) and buys only the cheaper contracts;
    pintake rails back at designed size with HEDGES exempt from the stake cap
    and loss abort (0 of 1,467 entries / 41 hedges would have been refused).
    pintake.py changed too; coin race is unaffected (never passes hedge=True).
- Money: 09-24 ET +$93.68; Kalshi ledger lifetime +$460.26 over 1,115 markets
  (to 09-25 07Z), fees $131.26; the account reconciles to 3 cents; the old
  "$16 gap" is explained (09-17 21:15 ET close, two unlogged markets).

## 3. Everything else running

| what | pid | ends / read |
|---|---|---|
| kalshi_collector / crypto_feeds (run_all.ps1 101860) | 2532788 / 105352 | always; disk ~84 GB free after the operator deleted a game |
| watch_bot.ps1 / pindesk (app) / pinphone (Telegram) | 2839244 / 2842980 / 2916264 | always |
| paper arms (sync_arms.ps1 rows): brake3, btcd, early-off, edge2c, fresh500, lateadd-off, toxic, hourly-all | 2972504, 2967156, 2971452, 2929736, 2968932, 2966252, 2836048, 2972548 | started 09-25 12:25Z, 10080 min -> ~10-02 |
| arm-live-frozen (09-20 settings, pinned) | 2896212 | ~10-02 06:30Z |
| arm-afternoon (manual, pinrun_afternoon.py) | 2564788 | ~09-27 03:51Z; let it lapse |
| coin race paper arms z3, gap075 | 2574672, 2577788 | ~10-01 |
| race controls racectl/raceedge0/racetau40, cmdarm x2 | 2592448.. / 2695900, 2703040 | ended/ending ~09-27; let lapse |
| kalshiwatch.py (hourly Kalshi change watcher; alerts -> results/kalshiwatch-alerts.jsonl) | 2917772 | stop: results/kalshiwatch.stop. First real test: Kalshi removes `liquidity_dollars` Oct 1 -- it must warn |
| polypaper.py / scan_poly_ws.py | 3088064 / 3080604 | ~09-28 |
| wxwatch / quakewatch / rungwatch | 2617292 / 2616700 / 2855812 | ~09-28 / ~10-08 / stop any time |
| cdc_record.py, pinledgerd.py | 345648, 802568 | old daemons; leave |

Windows: Update may NOT reboot while he is signed in (policy set 09-25; revert
in CURRENT_STATE). After a reboot nothing restarts until he signs in (KalsBoot
is interactive) -- automatic sign-in is still his to-do.

## 4. Answers and decisions from this session (do not re-open without new data)

- **Coin race scale-up: NOT YET.** Since v-race5 (5 contracts, 09-24 15:16Z): 18
  races, 18 won, +$3.80. Since 09-22: 85 races, 84 won, 1 tie (a tie = loss for
  the stop rail). The risk agent said hold at 5. Next step waits on the
  photo-finish arm (gap075) and ~100 races at 5 contracts with 0 losses.
- **Far rungs at 99c: dead** (results/FAR_RUNG_2026-09-25.md verdict).
- **Market making on 15-min crypto: dead** (MAKER_SIM_2026-09-24 section 9).
- **Hedge "cash out AND hedge" (flip): dead** (results/HEDGE_FLIP_2026-09-25.md).
  Hedging at 0.40 beats earlier/later/half. Lead: slow slides revert 45/100 vs
  14/100 for jumps -- check on our fills when there are more hedges.
- **Combos: dead** for our strategy (results/COMBOS_2026-09-25.md).
- **Model calibration:** fair() is 20-80x overconfident above P 0.999 on the
  index tape, roughly right below 0.995; no index-side fix pays on our fills --
  the loss signal is market-side (who sells to us), i.e. the toxic/fresh tests.
- **Speed:** a nearby server is worth ~$1-2/day on speed alone; reusing ONE
  HTTPS connection per order would recover ~40 ms for free (ordercli.send opens
  a new one each time) -- a live change not yet built (results/LATENCY_2026-09-25.md).
- **Time-of-week sizing:** nothing survives (results/TIME_EDGE_2026-09-25.md).
- **Constituent-exchange predictor:** no gain without peeking (CONSTITUENT_PREDICT).
- **Rival bots:** no new warning sign; "people selling our side" is the one
  separator (results/COMPETITORS_2026-09-25.md).
- **Red team:** reds 1-2 fixed by v-safety2; others in results/RED_TEAM_2026-09-25.md
  (e.g. the ET day key hard-codes UTC-4 -> from 2026-11-02 04:00Z the $200 day
  cap rolls at 23:00 ET: FIX BEFORE NOV 1; a --minutes end can exit mid-bet).
- **Taxes:** Kalshi sends no form for event-contract trades; treatment is
  unsettled ($460 to $1,529 of taxable income depending on the rule); he should
  book a preparer before Jan 15 2027 (results/TAX_NOTES_2026-09-25.md;
  research/taxledger.py rebuilds the CSV, kept out of git).
- **60-day money projection:** results/PROJECTION_2026-09-25.md, research/moneyproj.py;
  chart page (private artifact) https://claude.ai/artifact/WeWnNH1dKZ2TZ5Z6MBgBh3 .
  Headline: middle $2,924 on day 60 from $1,045; the 20% stop fires in 97/100
  paths on the headline week (one bug day), 19/100 without it.
- **The money sweep** (119 agents): nothing proven; top lead = the reward test
  (P2); all 63 checked ideas are rows in results/IDEA_LEDGER.md. Re-run:
  research/sweep/README.md ("run the money sweep").
- **Unverified open lead:** does pinrun's profit grow with bet size? If not,
  ideas cut for "displacing pinrun's cash" come back (IDEA_SWEEP).

## 5. Traps that cost time this session

- Bash heredocs HALVE backslashes (a revert path shipped with a CR; a Python
  string got split): write scripts with the Write tool and run by path.
- `"out = pintake.take("` is a substring of the hedge's `"_hout = pintake.take("`.
- The harness reaps its own background shells when free RAM nears 1 GB; detach
  anything that must live with Start-Process (launchers then linger -- harmless).
- Git Bash turns `/v` into a path: `MSYS_NO_PATHCONV=1` before `reg`.
- A progress count of FILES is not a count of hours (maker sim).
- Supply on the wrong market: "99c offers" were on the next-to-settle rung.
- Polymarket rejects a WHOLE subscribe request that repeats an already
  subscribed slug.
- git: fetch + merge only (pindesk auto-commits LEADS/collide files).
- `!` lines typed from the phone app do NOT run on the laptop.

---

# 2026-09-25 ~07:2xZ -- DOCS HOUSEKEEPING (no code, no process touched)

HANDOFF.md keeps sections from 2026-09-23 on; everything older moved verbatim
to `HANDOFF_ARCHIVE_2026-09.md` (417 KB -> 31 KB here). `CURRENT_STATE.md`
rewritten for v-zerotake. `CLAUDE.md` tightened (every rule, date and quote
kept) with a "where to read what" table and **two open questions for the
operator** (priority order 09-13 vs 09-17; per-order sign-off vs the 09-07
blanket money permission in memory). Replaced text of CURRENT_STATE, CLAUDE.md
and 18 memory notes is verbatim in `DOCS_ARCHIVE_2026-09.md`. RUNBOOK,
IDEAS, TOOL_PLAN and the dated HANDOFF_* files carry "superseded" banners.

---

# 2026-09-25 ~06:4xZ -- BEFORE THE /clear: everything running, every read date, every open item

The operator is clearing context after this. **A new session: read this
section, then `OPEN_WORK.md` (his topic index, "Say:" handles), then
`results/IDEA_LEDGER.md` (every money idea ever checked).** All times below
are UTC; say them to him in ET (EDT = UTC-4).

## Live money right now

- **pinrun --live** pid 2894452 since 06:25:05Z, code_sha 52b3e5fb28f8
  (`v-zerotake` on top of the v-ladder7 / v-farrung code, whose flags are all
  OFF). Argv = `restart_bot.ps1` (includes `--series KXBTCD --series-size 1`:
  hourly BTC at 1 contract). Bank $1,043, auto-size 88. `--minutes 4320`, so
  it exits ~09-28 06:25Z and watch_bot restarts it. Watchdog pid 2839244
  (watch_bot.ps1), app pindesk pid 2842980, phone pinphone pid 2844724.
- **v-zerotake (new, 06:25Z):** at 06:14:55Z a late add on a HYPE position the
  late boost had already filled to 1.5 x SIZE went out for ZERO contracts;
  pintake refused it twice and two order errors halt the run (watchdog
  restarted it in a minute, no money lost; the market won +$5.77). Fixed: a
  `late_add_full` gate plus a `zero_take` backstop. **Watch for either record
  in the live log** -- each one is a halt that did not happen.
- **Coin race live** pid 2707284 since 09-24 15:16Z, 5 contracts a leg,
  `--minutes 10080` -> ends ~10-01 15:16Z (relaunch by hand, v-race5 argv in
  VERSIONS.md).
- Money today (ET 09-25) at 05:49Z: +$13.46, 0 losses. Lifetime on Kalshi's
  ledger +$437.82 over 1,101 markets.

## Paper arms (read with `python research/bars.py` or /bars on the phone)

| arm | pid | started | ends | question | read |
|---|---|---|---|---|---|
| arm-fresh500, arm-toxic, arm-btcd, arm-edge2c, arm-lateadd-off, arm-early-off, arm-brake3 | 2615520, 2845916, 2846712, 2845952, 2845588, 2836048, 2846328 | 09-25 02:27Z | ~10-02 02:27Z | PREREG_fresh / PREREG_toxic bars; hourly BTC; 2c floor; controls | ~10-01 |
| arm-hourly-all | 2853628 | 09-25 03:06Z | ~10-02 03:06Z | do the six other coins' hourly ladders fill us? (v-ladder7) | ~10-02 |
| arm-live-frozen | 2896212 (relaunched 06:30:07Z by sync_arms -Only live-frozen) | 09-25 06:30Z | ~10-02 06:30Z | the 09-20 settings, pinned baseline. Its 3-day run ended 06:21Z at +$309 paper, 1 loss | any time |
| arm-afternoon | 2564788 (manual, pinrun_afternoon.py) | 09-24 03:51Z | ~09-27 03:51Z | code of the afternoon of 09-23 | relaunch by hand if still wanted |
| coin race z3, gap075 | 2574672, 2577788 | 09-24 05:56Z | ~10-01 | earlier entry; photo-finish filter (OPEN_WORK B2/B3) | ~10-01 |
| coin race racectl, raceedge0, racetau40 | 2592448, 2589516, 2591752 | 09-24 05:56Z | ~09-27 05:56Z | older race controls | lapse is fine |
| cmdarm x2 (commodities) | 2695900, 2703040 | 09-24 15:40Z | ~09-27 15:40Z | commodity 15-min paper | lapse is fine |

The live code hash moved twice tonight (v-ladder7/v-farrung, then v-zerotake).
The arms were NOT re-synced on purpose: their paper path is unaffected and a
restart would reset the 7-day windows. `arm-farrung` was stopped and its row
retired (idea dead).

## Watchers and recorders

- `kalshi_collector.py` 2532788 and `crypto_feeds.py` 105352 (run_all.ps1
  101860). **Disk 14.5 GB free at 06:10Z, falling ~1 GB/day; the collector
  STOPS for good at 5 GB (~09-29/30).** The operator is buying a 2 TB drive.
  *(Correction, 07:02Z docs pass: 11.9 GB free -- down 2.6 GB in 52 min; the
  1 GB/day rate was never measured, other notes say ~4 GB/day, and the phone
  sent 5.9-7.9 GB alerts at 09-24 22:20Z. `.claude/worktrees` held 1.9 GB.
  Drive NOT bought yet.)*
- `research/wxwatch.py` 2617292 (hourly temperature, to ~09-28) and
  `research/quakewatch.py` 2616700 (to ~10-08): `--report` on each.
- `research/rungwatch.py` 2855812: far-rung book depth; runs until
  `results/rungwatch.stop` exists. **Create that file after the 09-25
  ~23:00Z close** (the idea is dead; the daytime reads are the last check).
- **Polymarket US real-time recorder** pid 2855732 (`scan_poly_ws.py
  259200`, read key), started 06:11Z, ends ~09-28 06:11Z, writes
  `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\scan_poly_ws.jsonl.gz`
  (~70 MB/day). Read it with `python scan_poly_ws_report.py` in that folder
  (copies in `research/poly/`). That decides IDEA_LEDGER U1 / OPEN_WORK A11.
- Scratch scans from the Kalshi-wide scan agent (scan_ladder, scan_poly,
  scan_poly2, scan_poly_book) end by themselves within hours; nothing reads
  them further.
- `C:\kals\cdc_record.py` pid 345648 (Crypto.com recorder from 09-16) and
  `research/pinledgerd.py` 802568 are older daemons; leave them.

## The money-idea sweep (running at the /clear)

Workflow run `wf_a10c880e-f3b` (Scout -> Combine -> Merge -> Check -> Refute ->
Critic -> Write), read-only, ~7 agents at a time. Its writer produces
`results/IDEA_SWEEP_2026-09-25.md` + `results/idea_sweep_2026-09-25.json`.
**This run's writer does not know the ledger** (the ledger was built while it
ran): after it lands, merge its rows into `results/IDEA_LEDGER.md` by hand,
commit, and add any survivor to OPEN_WORK with a "Say:" handle. To run it
again later: `research/sweep/README.md` ("run the money sweep").

## Decided tonight (do not re-open without new data)

- **Far rungs at 99c: dead** -- 0 safe-side buys at >=97c on rungs $150+ from
  the settlement in 68 hourly closes (`research/rungtrades.py`); the live
  bot's 99c offers were the rung next to the settlement.
- **Market making on 15-min crypto: dead** -- 61 hours, 968 markets, 12
  variants, every one negative every day (MAKER_SIM section 9).
- **Polymarket US** offers the operator ONLY BTC 15-min and 1-hour; he is
  funded (~$60) and eligible.

## Look out for

- The seven-coin arm adds ~1.4 s to each universe refresh (10 more GETs) --
  a hedge blackout if ever taken live; fix before any live use.
- `research/bars.py` counts KXBTCD only (`BTCD_SERIES`), not the six new
  ladders.
- `early_dear` (97.5c early-leg ceiling) keeps any 99c ladder entry to <= 30 s
  (moot while far rungs are dead).
- The live hourly BTC leg sent ZERO orders in its first 10 hours (70
  refusals: no_offer 33, book_stale 26, confidence 6, price_ceiling 5).
- Harness habits that cost time tonight: Bash heredocs halve backslashes
  (write scripts with the Write tool); `"out = pintake.take("` is a substring
  of the hedge's `"_hout = pintake.take("` (anchor on the whole line); the
  harness kills its own background shells when free RAM falls near 1 GB
  (detach anything that must survive with Start-Process); the maker sim's
  "hours" progress was a file count (2 per hour); subagents can die on the
  model's usage limit -- re-check their files.
- Old memory items still open: re-walk the pickoff tracker; reconcile the
  day total against the balance ($16 gap).

## Operator actions pending

1. Buy the 2 TB drive (the deadline is the disk, ~4-5 days).
2. Enable Windows automatic sign-in (KalsBoot is an interactive-logon task).
3. AWS Lightsail Ohio ($124/mo) after a good weekend (`results/VM_PLAN_2026-09-24.md`).

---

# 2026-09-25 04:0xZ -- SECOND INCOME hunt: far rungs of the hourly BTC ladder at 99c (built, OFF, needs sign-off); Polymarket US lists our exact contract; seven-coin hourly paper arm; scan of everything else

Operator's brief: "seriously find a second income source... anything on
Kalshi or even Polymarket... search hard and wide and test vigorously."
Three hunts ran in parallel; everything below is read-only measurement
except code that ships OFF.

**1. FAR RUNGS -- KILLED 05:4xZ, no supply (FAR_RUNG verdict; rungtrades.py: 0 safe-side buys at >=97c at $150+ in 68 closes; the live bot's 99c offers were the rung next to the settlement). Original write-up below.**
On the hourly BTC ladder a rung $150+ from the projection with 45 s left was
crossed on 0 of 2,136 closes since 09-01 (index tape, 60-print mean
reconciled to the exchange's own average 2,133/2,133; worst miss $136 at
45 s, $101 at 30 s). Those rungs sit at 99c with 800-12,600 contracts
resting; the live bot refused five of them `price_ceiling` on 09-24. Worth
0.93c a contract, break-even 0.93 crossings per 100; bank-limited (25% of
bank a side): ~$68-85/day at today's bank, -$225 per crossing at that size.
Honest limit: 24 days of tape with no flash crash; the worst rate the tape
allows (95%) is 0.14%, which still nets +0.79c. Pre-registered 1-contract
bar in the file's section 0 (>=100 fills over >=30 closes, ZERO crossings,
net >=0.8c, fill rate >=50%, depth >=500 at C). **Built as `v-farrung`
(dfefa2a): seven flags, all OFF; paper arm `arm-farrung` running.** The
live test is the same flags on restart_bot.ps1 with a `v-farrung1` entry --
NOT done, it needs the operator's sign-off (new family, 99c). Known limit:
`early_dear` keeps rungs to tau <= 30 s.

**2. POLYMARKET US (results/SECOND_INCOME_SCAN_2026-09-25.md section 2).**
Since 09-22 15:15Z polymarket.us lists BTC 15-minute and 1-hour up/down on
the SAME BRTI 60-s average with the SAME strike to the cent (verified on
the 03:15Z close). Taker fee 0.0695 p(1-p); makers PAID 0.0125 p(1-p).
Book is 1/10-1/50 of Kalshi's (median 4,423 shares a window, 47% of
windows zero). The cached public gateway showed "riskless" cross-venue
packages at $0.89-0.99; every one vanished on the real-time feed (30-s
cache). Realistic: $0-15/day incremental, unknown. The real-time recorder
(`scratchpad/scan_poly_ws.py`, read key, GET/WS only) relaunches itself
for 3 days; bar in the file. This reverses the 09-06/09-24 "no short-dated
crypto there" kills, which were true when written.

**3. SEVEN-COIN HOURLY LADDERS (`v-ladder7`, ad700c5, paper).** ETH SOL XRP
DOGE BNB HYPE hourly ladders exist on indexes the bot already follows;
`arm-hourly-all` trades all seven at 1 contract a rung on paper (log
pinrun-paper-20260925T030630Z). First refresh: 7 ladder records, 3 rungs
each, 0 errors; universe refresh 0.9 -> 2.3 s (10 more GETs; a hedge
blackout concern before any live use). Live path proven byte-identical.

**4. Everything else scanned (section 1 of the scan):** crypto one-touch
monthlies $2-10/day needs-data (33 crosses Jul-Sep, $3,738 gross bought
<=97c in the last 10 min, 3 events); ladder both-sides arbitrage 0 of
1,496 polls; sports final minute unmeasured (ESPN 403 from this box);
S&P/Nasdaq close, Crypto.com, ForecastEx, Robinhood/Rothera, PrizePicks,
Sporttrade, air quality/box office/app rankings/Trends: killed with
reasons. Market-making sim (six days) still running at 126/132 hours.

**Harness lesson:** the Bash tool's heredoc halves backslashes (a VERSIONS
revert path shipped with a CR in it); write scripts with the Write tool.

---

# 2026-09-24 02:22Z -- v-cap20 LIVE; the whole rule set re-priced on a per-second rebuild; what was measured and NOT changed

Operator's brief tonight: "make the final profit number bigger... don't change
things for the sake of changing... make no errors." Everything below is on
Kalshi's ledger money, per-second belief rebuilt from the index tape with
pinrun's own maths, and the market's best ask from the ticker tape, for all
820 markets we ever entered (`results/cf_2026-09-24/`: cf_build.py builds
`cf_dataset.jsonl.gz`, cf_sim.py prices rules). It is a re-implemented
decision, NOT the certified backtest: rows are compared to each other on one
engine, never to Kalshi's number directly. Top-up / add fills at the tape ask
are an upper bound (live fills ~70%); a 70% column is always printed.

**LIVE NOW (pid 2543296, code_sha 3f37c9c0d7b6): v-cap20.** The 10c edge
cap applies only with MORE than 20 s left (`EDGE_CAP_TAU = 20`; `None` is
the v-nospike every-tau cap), and the early-leg floor is 0.95 (was 0.90).
Same engine: rules as of 9:13 PM +$500.70 -> cap only above 20 s +$633.37
-> plus the 95c floor +$664.97; both weeks improve. A >10c gap with <=20 s
left is the pin edge (19 markets, 1 loser -$2.12, +$102); with >20 s left
it lost 3 of 19 (-$200). NOTE the v-nospike write-up counted a refusal as a
lost MARKET ($213 of winners given up); the bot re-looks every second and
buys once the gap closes, so the real give-up is ~$15. Kalshi's ledger,
ET 09-23: 48 markets -$49.68; under these rules 47 markets +$80.73.

**Where the money is (825 first entries):** <=20 s left: 233 markets, 6
losses -$71, net +$435; 21-45 s: 592 markets, 21 losses -$824, net +$39.
A loser entered at <=10 s costs 4c per $1 risked; at 21-45 s, 71c, hedged
or not. Late entries are also cheaper (94c vs 96c average).

**Measured and NOT changed (do not re-propose without new data):**
- Half size at 21-30 s with a top-up at <=20 s (operator's idea; the code
  already does it via `staged_take`, flags `--tau-max 20 --early-frac 0.5`):
  -$41 vs the cap alone, -$21/-$20 by week, worst loss unchanged (-$65).
  "No entries before 20 s": +$507 vs +$633, fewer losses AND fewer wins,
  hostage to late fills. Sizing ladders A-F all within +-$60 of each other.
- Hedge trigger: on 820 positions, 0.40 all-at-once (live) is the best of
  {0.40..0.90} x {proportional, all} x {drop-from-peak 0.1..0.5} x
  {seconds-left-aware 0.40/0.60, 0.40/0.80, 0.30/0.40, 0.25/0.50, 0.50/0.40}.
  The simulation is +$190 over what actually happened; +$145 of it is the
  09-19 bug day (blocked/false hedges, fixed by v-safety1). No change.
- Spike gate: adds ~$5 on the engine (refusals re-enter a second later) but
  is the direct defence when the BTC shape has a gap under 10c; kept.
- 90c floor at 21-30 s: -$10 (refused markets re-enter at <=20 s and lose
  anyway). Fee rounding: Kalshi bills the formula (-1%), no per-order leak.
  Our locked-sum arithmetic vs Kalshi's own `avg_60s_data`: median 0.08 bp,
  1 of 64 markets over 1 bp (SOL 09-11, 1.56 bp) -- not a loss source.
- Same-second double fills on one market at >20 s (the BTC 176 = 88 + 88,
  318 ms apart; DOGE 09-23 11:15Z proves the second pass does not see the
  first fill yet, so the improve band is bypassed): 6 pairs on record, 5
  small winners +$5.7, BTC's second leg -$75.79. A correctness fix (a pass
  cannot re-send on a market whose fill from the last ~1 s is unbooked) is
  pending; not a money rule on n=6.
- From the 22-agent review (results/cf_2026-09-24/ + task output): killed
  with numbers -- confidence tightening at 21-45 s (z-floors 3.0/3.5/4.0,
  honest table, sigma x1.25/1.5: all -$91..-$194 per 16 days), late boost
  2.0x (binding rail miscounted, no money at this bank), momentum term (beta
  0.03-0.11, no signal), jump gate 2 sd (no flag exists; no money), spot
  cushion floor (its avoided losses are already the cap's), 3rd/4th coin
  budget (premise false: close_budget fires before the signal gates),
  98-99c ceiling inside 20 s (fills at exactly 98.0c are the sweep cap,
  not a population), TAU_MIN 3->1 (winner-side ask absent 98.9% of ticks
  at 0-3 s), resting bids on the winner (99.5-99.9c with ~6,900 queued),
  yes_ask+no_ask<1 (no buyable population), new coins.

**THE 04:0xZ AUDIT (16 agents: code diff, failure modes, coin race; full
output in the session task file, findings verified adversarially):**
- FOUND AND FIXED (v-lateadd-fix, 04:21Z): the early-leg gates were dead for
  73 min under v-lateadd-live (block nesting); a late add could be widened
  by the late boost to 1.5 x SIZE; a 21-30 s band re-buy was relabelled and
  halved. All three now have DRIVEN checks. Lesson: a source-text self-test
  cannot see a nesting change -- every gate needs a world that refuses.
- OPEN, ranked by the audit's expected cost: (a) same-second double sends
  build 2.0-2.67 x SIZE positions (SOL 09-23 04:59Z 218.69 contracts at
  size 82; DOGE 85+85; BTC 88+88 = -$75.79 of the -$130.41); `--one-coin-max`
  exists (1.0..MAX_PER_CLOSE) and is NOT in the live argv -- measure it on
  the record before using it; (b) the drawdown brake line is $829.86 against
  a $925.66 bank: one more -$96 day trips a HALT LOOP that needs a human to
  edit pinrun-hwm.json (09-20 precedent) -- decide whether the loss cap
  should re-base daily; (c) disk 21.2 GB at 3.93 GB/day reaches run_all's
  5 GB stop about 2026-09-28 03Z -- a full disk takes the MONEY bot down,
  not just the tape; (d) RAM commit 22.6 of 27.8 GB after retiring the
  sigma arms -- consider a bigger page file; (e) the Thursday 07Z Kalshi
  gap: bot refuses on no_offer/book_stale, recorders stay up, only a 07:00Z
  position hedged against a frozen book is exposed (~$2), the phone will say
  BLIND ~03:05 ET -- expected, not a fault.
- COIN RACE (ledger, races = closes): the live penny test since v-race30
  (09-22 07:03Z) is 58 races, 57 won, 0 lost, 1 TIE (+$1.13); the tie
  (26SEP230715) cost -$0.95 and the bot booked it +$0.05 and did not halt.
  Paper arms scored tie-aware, 1 contract a leg: racectl 19/19 +$1.33;
  raceedge0 76 races 75W 1T +$2.32; racetau40 28 races 26W 1L 1T (loss at
  tau 40); z3 50 races 49W 1T, of which its EARLY (>30 s) races 21/21 +$0.56.
  Own-log money is WRONG on ties (raceedge0/racetau40 book +$7.50 where the
  ledger says -$118 at their paper size). Photo finishes under 0.75 bp are
  14.7% of penny races vs 7.2% of all races, and 3 of them were resolved
  outright and won: no gap threshold separates ties from results. NEXT:
  tie-aware `winner_from` + halt on Kalshi money, then the z3 early rule's
  bar (21/21 so far; the bar is 125 races 0 losses).

**v-tradefeed (22:20Z, pid 2836976, code_sha ab19f2baf0a0): the live bot
subscribes to Kalshi's `trade` channel and logs `sell_share_3s` /
`taker_n_3s` / `trade_age_s` on every signal, order and priced refusal; the
`toxic_fresh` gate ships OFF and `arm-toxic` runs it ON.** results/PREREG_toxic.md
(the AND of PREREG_fresh's 500 ms and toxicity.md's sell share > 0.5: 87
markets, 8 of 12 early losers, -$285; every other cell positive; read
~2026-10-01). A trade-channel error can never mark a book suspect or resync.
Also 22:26Z: `/bars` on the phone (research/bars.py) reads every test against
its bar; DISK alerts under 8 / 6 GB; arms now run 7 days (sync_arms --minutes
10080; a 3-day arm would have died on day 3 of a 7-day bar). 22:13Z:
v-daycap-brake (watchdog 2839244, app 2842980). FEED LEAD (results/
FEED_LEAD_2026-09-24.md): books explain 70-79% of the next print, but the
"moved against us before the send" gate does NOT separate our losers (Q3,
651 entries, p 0.13-0.8) -- killed as a gate. GUARDIAN.md + SCALING_PLAN:
next size step = a $1,500 bank (size 127) after a clean weekend, ~30 hourly
fills and the disk; KalsBoot is LogonType Interactive -- Joe must enable
automatic sign-in before leaving.

**v-btcd1 (16:48Z, pid 2727204): the HOURLY BTC ladder trades live at ONE
contract** (`--series KXBTCD --series-size 1`). Operator: "run hourly btc full
on exactly how we would to make real money but at 1 contract instead." No
separate close budget -- measured first: budget gates fired on 6% of 425
closes and only 2 closes in five days lost a market that would really have
traded ($0.05-0.20/day), and the budget counts contracts (1 of 156). The cap
is applied at the signal point AND after every widener on both send paths;
--series live is refused without --series-size. 1,168 checks green plain and
under the deployed argv. NOTE: the first draft re-parented the early-leg
gates by inserting the cap above them -- the identical 04:4xZ regression --
and the DRIVEN early-floor check caught it in one run. Any insert between
`sig["take_n"] = take_n` and the early gates does this; put new code after
the `staged_none` continue.

**v-race5 (15:16Z): the coin race penny test is now 5 contracts a leg**
(`--max-contracts 5 --max-stake 60`, pid 2707284; everything else unchanged).
Operator gave the boost; 5 and not more because the break-even margin is
+1.2 points on 95 legs, which cannot be told from zero. Safe only because
v-race-tie1 makes a tie a LOSS for the stop rail. Revert argv in VERSIONS.

**HOURLY BTC IS THE SCALING PATH (arm-btcd, first 7.5 h):** the hourly
ladder's books are ~30x deeper at OUR price -- median 838 contracts resting
where we buy, against 28 on the 15-minute markets; under the 98c ceiling
3,486/3,449 vs a median 168. 4 signals, 3 settled, all won. So the $14/day
ceiling in IDEAS item 2 is OUR close budget, not the market: on the
15-minute markets more bank buys nothing past ~3x, on the hourly ones it
buys proportionally. Next: the 7-day bar, then a per-series close budget.

**TEMPERATURE: the prediction is perfect and the supply is not there.**
wxwatch after 7.5 h: settlement == the index at the close minute 240 of 240;
with a >= 1 F margin the index ended on the other side 0 times in 3,072
polls at EVERY lead (<=7 min, 7-10 min, >10 min). But only 8 polls in 7.5 h
had a real offer at 50-97c on the index side -- 3 markets, ~$13/day ceiling,
NYC and LA zero all day. Let it finish the 3 days, expect nothing.

**results/LEADS_20260924.md (the scheduled collide job, no data) -- both leads
are answered by tonight's live-fill work, do not build them as proposed:**
lead 1 ("informed counterparty vs sigma") = the fresh-level and toxicity
findings (PREREG_fresh.md: 6 of 7 surviving early losers on a level 19-229 ms
old, resting levels 0 of 155; toxicity.md: taker selling of our side in the
last 3 s) -- our own fills, no tape study needed; lead 2 ("capacity ceiling
in bank dollars") = the 09-23 scale table in this session's report: resting
depth under 98c at our fills median 325 contracts vs size 78 (ratio ~4x at
signal time, ~0.77 of it realised), so the ceiling binds around 3-4x today's
size, i.e. a $2.5-3k bank.

**09:2xZ: second low-memory shell kill** (the harness's own shell; bot,
recorders and arms untouched; free RAM 3.5 GB, commit 21/27.8). Retired
arm-friday and arm-hedge-slip0. arm-btcd's 15M universe matched live's on
real data at 09:15Z (9 of 9 tickers).

**TWO MORE PAPER ARMS (08:xxZ-09:0xZ, both flags SHIP OFF, live unchanged):**
`arm-btcd` (`--series KXBTCD`, the hourly BTC strike ladder, 3 rungs nearest
BRTI; first real rungs at 09:45Z; bar in IDEAS item 2) and `arm-fresh500`
(`--fresh-min-age-ms 500 --fresh-tau-min 20`: with >20 s left refuse a level
posted under 500 ms ago; results/PREREG_fresh.md -- on OUR fills since 09-13,
6 of the 7 early losers that survive the live rules hit a level 19-229 ms old,
resting levels 0 of 155, money a wash; read the bar after 7 days with
armh2h2.py: live = arm + the fresh entries). The tape hypothesis behind it is
results/RESULTS_select.md; the live record was built for exactly this since
09-13. Self-test 1,162 checks green plain and under the live argv.

**SHADOW WATCHERS RUNNING (07:54Z): `research/wxwatch.py` (hourly temperature
pin: Kalshi's public minute index for Miami/NYC/LA/Chicago vs the hourly
markets' thresholds, index age, the index-side book, would-buy decisions,
settlement == index check; bar in its docstring: 3-5 days, age p90 < 7 min,
>= 50 offered contracts/day/city at <= 97c with >= 1 F margin, zero >= 1 F
crossings) and `research/quakewatch.py` (USGS vs KXBIGGESTQUAKE locks).
Logs: results/wxwatch-<start>.jsonl, quakewatch-<start>.jsonl; report:
`python research/wxwatch.py --report`. Read-only, no orders. Not restarted by
boot_all -- relaunch by hand (commands in the agents' reports / .out headers).

**VM PLAN (results/VM_PLAN_2026-09-24.md):** Kalshi's exchange is AWS
us-east-2 (Ohio) -- FIX hosts in Amazon's Ohio ranges, Glassnode agrees; the
bot's API host is a CloudFront relay (Ashburn edge from here). Recommended:
Lightsail Ohio, Windows Server 16 GB, $124/mo, move as-is (~1 day); Linux
$84/mo but 7-10 days of porting. Tape to S3 Glacier IR / Backblaze B2 (~$3-8
per month) -- upload the 98 GB tape first (3 h at 9 MB/s), which also ends
the laptop disk deadline. Laptop clock is 13 ms off NIST (checked 08:49Z).

**THE NEW-EDGES HUNT (07:xxZ, 54 agents): results/IDEAS_2026-09-24.md** -- 46
ideas, 1 promising (hourly TEMPERATURE pin on Kalshi's own public minute
index, published 5-6 min late; tape ~$175/day Miami, realistic $20-80/day;
3-5 day read-only shadow first), 6 testable-now (hourly BTC strike ladder
KXBTCD as a paper arm; two-sided 1-contract maker quotes -- sim only, needs
>2 GB RAM we do not have with the fleet up; USGS quake lock watch; fresh-
level entry skip at >20 s; explicit size cap; deep resting race bids), 7
needs-data, 32 killed with reasons (perp hedge, Polymarket US, Gemini pin,
daily highs, sell-the-winner, lottery tickets, ...). Every tape dollar is a
TAPE figure, never our loss rate; the same metric reads -$5/day on
KXBTC15M where we really lost -$469 since 09-17.

**Telegram (06:45Z restart, pid 2597696): `/stats`, `/race`, `/racestats`**
(research/pinphone.py, self-test 50 -> 104). Money from the ledger only;
log-only items labelled. First real /stats: lifetime +$421 on $41,122
risked, 1,020 markets, break-even 95.2 of 100 contracts vs 96.1 paid (+1.0
pt); LAST 7 DAYS -$26.75 and UNDER break-even (96.0 paid vs 96.1 needed),
the 21-45 s first buys carrying -$168.90 on 281 markets while <=20 s buys
made +$169.32 on 59. Coin race since v-race30: 60 races, 59 won, 1 tie, 0
lost, +$1.17. GOTCHA: a `-like '*pinphone.py*'` / `'*pindesk.py*'` process
query matches the querying shell's own command line -- count only python
processes, or you will "find" and kill your own bash (02:2xZ: exit 255).

**v-hwm-reset (06:5xZ, operator: "yes to drawdown halt"):** after a DRAWDOWN
halt the watchdog HOLDS (no 15-min restart loop); START on the app writes
`results/pinrun-hwm.reset`; at the bot's next start the 20% mark is re-based
to the balance (`hwm_rebased` record + a dated line in VERSIONS.md). Deployed:
watchdog replaced (pid 2593104), app relaunched (it runs as ~5 pindesk.py
processes -- main + workers; do not count them as duplicates); the live bot
picks it up at its next start; the phone bot after its restart. Also fixed:
the app had never shown SAFETY BRAKE for a real halt (`last_halt` read the
`end` record).

**v-race-tie1 (06:0xZ): the coin-race scorer reads Kalshi's own result** --
a tie pays 50c to both tied coins and is a LOSS for the penny test's stop
rail; unscorable races stay pending with the stake held (results/VERSIONS.md).
The penny bot and every race arm (z3, gap075, racectl, raceedge0, racetau40)
were restarted on it at ~05:57Z; the penny bot's argv is the `--live` one in
the process table (also in VERSIONS/v-race-tie1). One old real leg (09-22
07:59Z XRP YES 98c) stays unscored in the log; the ledger has it.

**PAPER FLEET TRIMMED 04:3xZ for memory** (the harness killed a shell for low
memory; commit was 22.5 of 27.8 GB with 40 python processes): retired the 7
sigma arms, the hedge family (nohedge, hedge60, hedgeprice60, hedgeprop-on;
the 820-position replay settled the trigger), pin 0.97/0.975/0.98, band15,
early60, brake6. Rows are in git. 14 arms remain: afternoon (manual),
lateadd-off, edge2c, live-frozen, friday, early-full, early-off,
early-cap975, doubt15, doubt125, attempt-send, hedge-slip0, brake3,
pin0.985, pin0.99. RAM 15.8 GB, commit limit 27.8 GB (page file
system-managed) -- keep the fleet under ~15.

**CONTROL ARMS (operator: "keep something running to compare the version we
had running this afternoon to the version we just created"):** `arm-afternoon`
= the 09-23 afternoon CODE (commit 9aa5f13, copied to
`research/pinrun_afternoon.py`; no spike gate, no edge cap, no late add) with
the afternoon's live flags (hedge-belief 0.25, early floor 0.90, slip 0.03),
paper, launched by hand 2026-09-24 03:51Z (pid 2564788), stdout in
`results/arm-afternoon.out`. It is NOT in sync_arms.ps1 and NOT restarted by
boot_all -- relaunch by hand after a reboot (the command is in this session's
scratchpad / the arm's .out header). `arm-lateadd-off` = tonight's code and
flags minus the late add (in sync_arms). Compare with
`results/cf_2026-09-24/armh2h2.py`.

**Open, measured positive, not yet live:**
- LATE SAME-MARKET ADD. On a FULL position, at <=15 s, when the ask is at or
  above what we paid (-0.5c) and every entry gate passes, add 0.5 x size:
  +$95 over 16 days (141 fires, ONE losing add -$3.23), +$66 at 70% fills;
  at <=20 s +$115 (4 losing adds -$25); at <=10 s +$62 (0 losing adds);
  both weeks positive. Today `rebuy_ok` refuses every not-cheaper re-buy on
  a full position (60 `rebuy_band` refusals in one close). Needs: a flag
  (`--rebuy-late-tau 15 --rebuy-late-frac 0.5`, default off), the
  double-send fix first, a PREREG bar, a paper arm; close budget and
  max-per-market still apply (the engine did not model them -> upper bound).
- Hedge slip 0.03 -> 0.10: live hedges paid ~$60 over the first-try ask
  because the touch was thin (BTC tonight: 946 shown at 77c, 21 filled at
  the 80c limit); a taker IOC pays the ladder's prices, so a wider limit
  only sweeps deeper when the touch is gone. `arm-hedge-slip0` is -$32 vs
  live on the same markets. Small (+$5-10 on this record), flag only.
- Paper arms since 09-20 (own-log money, same markets, closes both were up;
  paper fills): pin 0.97-0.99 / sigma 0.2-0.4 show +$60..220 over 2-3 days
  but every dollar is extra trades in the early/low-confidence class that
  produced every big loss, at fills we would not all get -- not evidence
  against the bar. `brake3` +$32 on 138 identical markets (the size step),
  `early-cap975` +$49 on 100 identical markets: worth a closer look.
  Tool: scratchpad armh2h2.py (copied to results/cf_2026-09-24/).
- TRADE-TAPE TOXICITY -- THE BEST "IDENTIFY BETTER" LEAD OF THE NIGHT
  (results/cf_2026-09-24/toxicity.md, 793 of 825 entries covered; the BTC
  09-23 loss is in the recorder's dead hours). In the 3 s before our order,
  takers had SOLD more of our side than they bought on 17 of 25 losers
  (68%) vs 245 of 746 winners (33%): loss rate 6.5% flagged vs 1.5%
  unflagged, rank-sum p = 0.0004 (clears the 24-look bar), survives
  leave-one-out, close-level and by-day splits; it is direction, not
  activity; gone at 10-30 s. Lives at 21-45 s (14 of 20 losers flagged,
  p = 0.0008, +$216 in-sample if skipped); inside 20 s a skip COSTS money
  (-$126). Of the flagged 21-45 s losers, v-cap20's rules already refuse
  ~6; the rest (BTC 09-19 16:00 -$108, XRP 09-19 -$65, BNB 09-19 12:30
  -$62, HYPE 09-21 -$31, SOL 09-11 23:00 -$20, BNB 09-10 -$18, XRP 09-10
  -$17) are exactly the "nothing at entry separates them" class. FRAGILE
  on money (two losers are $174 of it) and the flag marks losers more than
  it forecasts them (93.5% of flagged entries still win). NOT a live skip.
  NEXT: (1) pinrun subscribes to orderbook_delta only -- add the `trade`
  channel, keep a 3 s rolling taker-flow per watched market, write
  `sell_share_3s` on every signal/order/refused record, NO behaviour
  change, with the bar pre-registered ("sell share > 0.5 in the last 3 s,
  entries with > 20 s left": 400 more entries ~8 days confirm 6.5% vs 1.5%);
  (2) then a paper arm that DELAYS a flagged >20 s entry 3-5 s and
  re-evaluates (losers move -8 sigma in those 5 s, winners barely move),
  flag `--tox-delay`, default off. Not built tonight: a new socket
  subscription on the live bot after two restarts is not "careful".

---

# OLDER SECTIONS (2026-09-22 and earlier) -- moved verbatim to `HANDOFF_ARCHIVE_2026-09.md` on 2026-09-25 (newest first, grep it by date).
