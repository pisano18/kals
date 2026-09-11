# THE TOOL — plan of record (2026-09-11). Read this first when resuming.

Operator's goal, verbatim: *"to be able to rip this strategy/algorithm/method
apart without doing the math... extremely open and customizable in the way of
all values, add values if that makes sense."* Plus: trackers he can set up
himself (the crazy-deal tracker is the first), profiles he can save and run, a
Learn section that explains every concept, app-like on the PC, reachable from
his phone, no Pi for now.

## The one idea everything hangs on

**The strategy becomes DATA, not constants.** A *profile* is a JSON file:

```
profiles/default.json
{ "name": "default",
  "params": { "PIN": 0.995, "PRICE_CEILING": 0.98, "TAU_MIN": 3, ... },
  "rules":  [ { "id": "dump", "name": "Crazy deal",
                "when": { "all": [ ["conf", ">=", 0.999], ["discount_c", ">", 5] ] },
                "action": "refuse",          <- or "log" = a TRACKER
                "note": "a certainty at a discount is someone else's information" } ] }
```

* Every **param** is declared once in a schema (`research/pinrules.py`) with its
  type, range, default, and a plain-English explanation. The tool renders a
  control for every param automatically — **add a param to the schema and it
  appears in the tool with its explanation, no UI work.**
* Every **rule** is a condition over the *decision record* (the fields the bot
  sees at the second it decides) plus an action: `refuse`, `log` (tracker) or
  `allow`. **A tracker is a rule with action `log`.** Every rule's would-be
  outcome is recorded whether or not it refuses, so trackers and refusals both
  resolve against settlements. The crazy-deal guard (AMENDMENT 10b) becomes the
  first rule in `default.json` instead of two Python constants.
* **The decision record** (all backward-looking, identical live and in replay):
  `fair, conf, margin_sd, want, price, discount_c, edge_c, ev_c, tau, depth,
  take_n, coin, hour_utc, sigma, spot, cond_x, cond_n, cond_own, book_age_ms,
  index_age_s`. Rules can only see these. Adding a field = one place.
* `pinsim.py --profile X` replays real tape under profile X and reports, per
  rule and overall, fills / wins / losses / P&L / mean price, **fit and holdout
  side by side, n as markets and closes, every rate with its interval,** and
  the "if every offer were ours" vs "at the 70% live fill rate" pair. **This is
  the sandbox backend.** It calls `pinrun`'s own decision code (certified for
  decision reproduction, 13/14 live signals; NOT for loss rates — CLAUDE.md).
* `pinrun.py --profile X` runs live under profile X (a later, separate
  amendment with its own self-test and quiet-window restart). Every live
  decision writes a `decision` record with the full decision record and the
  rules that fired, so live trackers resolve the same way.

## Components and build order (safest first; resume at the first unchecked box)

- [x] **`research/pinrules.py`** — param schema, condition language, profile
      load/validate/save, `decide(profile, record)`. Self-test plants rules and
      checks refuse/log/allow, range validation, and that the crazy-deal rule
      reproduces the two real losses and spares the real cheap wins.
- [x] **`profiles/default.json`** — today's live rule exactly (A9 + A10b).
- [x] **`pinsim.py --profile`** — per-rule would-be tallies, fit/holdout.
- [x] **`research/pintool.py`** (sandbox jobs run pinsim as a separate process; server never imports pinrun/pintake) — stdlib `http.server`; serves `tool/index.html`
      and JSON: `/api/live` (tail of the newest live log → state, equity curve,
      the live "number needed to sway the average", brake counters, bars
      progress), `/api/profiles` (list/get/save), `/api/sandbox/run` (background
      thread running pinsim with a profile → job id → `/api/sandbox/status`),
      `/api/control` (the ONLY writer of `results/CONTROL.json`), `/api/learn`.
      Binds `127.0.0.1` by default; `--lan` binds `0.0.0.0` for the phone.
- [x] **`tool/index.html`** (v1) — one file, four tabs: **Live · Sandbox · Profiles ·
      Learn**. Chart.js from cdnjs. Responsive so the phone works.
- [x] **Live tab** (v1) — equity curve as a stock ticker (% change today/7d/30d/all,
      OHLC by day, max drawdown in *wins-to-recover*, volume = fills, fill
      rate, per-trade hover, capital deployed vs idle); colour-coded live
      metrics; the number needed to sway the average, updating live; brake
      counters; progress to the pre-registered bars; play/pause/stop.
- [x] **Sandbox tab** (v1) — pick/edit a profile, run it on the tape, see per-rule
      results with FIT and HOLDOUT always side by side, the live setting marked
      on every control, a "you are now curve fitting" warning after N runs
      with the multiple-looks threshold shown. **No code path to the order
      API and no writer for CONTROL.json — an absent button, not a disabled
      one.**
- [x] **Profiles tab** (v1) — save the sandbox state as a named profile; deploy =
      writes `CONTROL.json {"profile": X}`; the trader validates (full
      self-test + range checks) and restarts itself cleanly; loosening a brake
      shows the worst-case dollars and needs typed confirmation; the log
      records profile name + contents + hash at start.
- [x] **Learn tab** (v1) — every param's explanation comes from the schema (the tool
      cannot show a control without its meaning); plus concept pages: the
      settlement window, sigma and margin, why price matters more than
      confidence, wins-to-recover, break-even loss rate, fit vs holdout, why a
      replay is an upper bound, what the brakes do.
- [ ] **`pinrun.py --profile` + CONTROL.json reader** — separate amendment.
      Pause = stop opening positions, keep settling; stop = finish open
      positions, write `end`, exit.

## THE SCALE OF CONTROL (operator, 2026-09-11) — this is the standard, not a stretch goal

> "I should be able to set how many contracts are being bought at each price
> point... an auto calculate best value based on different goals for each
> metric where it applies... Anything you've ever tinkered with or considered
> should be testable, changeable, or discoverable via the sandbox/strategy
> builder UI."

**Four kinds of lever, and every lever is one of them:**

| kind | what it is | examples |
|---|---|---|
| **value** | one number with a range and a meaning | `PIN`, `TAU_MAX`, `EDGE_FLOOR` |
| **schedule** | a number that depends on a field — a table of bands | **size by price** (`SIZE`), ceiling by confidence (`PRICE_CEILING`), sigma stress by conditions (`SIGMA_STRESS`), max-per-close by hour |
| **rule** | a condition → refuse / log / allow | crazy-deal guard, coin exclusions, hour-of-day, "only when 2+ coins moving", the exchange-tick veto |
| **goal search** | pick a lever + an objective; the sandbox sweeps it and reports FIT and HOLDOUT | "size-by-price that maximises P&L at ≤2% loss rate", "the ceiling that maximises fills at EV ≥ 0.3c" |

Any value can be promoted to a schedule in the UI ("make this depend on…").
Objectives available to a goal search: P&L, EV per fill, loss rate, fills/day,
worst drawdown, wins-to-recover, P&L at the 70% fill rate — **always reported on
FIT and HOLDOUT, with the multiple-looks threshold for the number of settings
tried, and a curve-fitting warning that cannot be dismissed.** A goal search is
how the operator finds the number; the holdout column is how he finds out
whether it is real.

**The lever catalog — everything investigated this week, each to be exposed:**
gate `PIN`; price ceiling; tau window; size (scalar → schedule by price);
margin-aware ceiling (schedule by `margin_sd`); sigma stress (scalar → schedule
by `cond_x` / `cond_own`); conditions gates on `cond_x` / `cond_n` / `cond_own`;
the dump guard (rule); the exchange-tick veto (rule, needs the feed replay in
pinsim — not yet); max per close; improve-by; min fill fraction; coin include /
exclude; hour-of-day; "fire at first crossing" vs "wait until margin ≥ X"
(rule on `margin_sd`); price-improvement handling; the brakes (`LOSS_ABORT`,
`MAX_LOSSES`) with worst-case dollars shown. Missing from the decision record
today and to be added when their replays exist: exchange-tick divergence,
latency, fill-race outcome.

## DESIGN (2026-09-11, before building the server) — read this before touching pintool.py

### The two nouns, and why nothing else is needed
* **A profile IS the strategy.** Params (values or schedules) + rules. Live runs
  one; the builder edits one; the sandbox replays one; a goal search sweeps one.
* **A decision record IS what happened at one second.** The same 20 fields live
  and in replay. The Live feed, the sandbox results, every rule and every
  tracker read the same record. One vocabulary → no jumble.
Everything the tool shows is a view of a profile, a set of decision records,
or the settlements those records resolved against.

### Where state lives (no database; restart-proof)
| thing | where |
|---|---|
| profiles | `profiles/*.json` (git-tracked) |
| live state | `results/pinrun-live-*.jsonl` (newest file = the running process) |
| sandbox results | `results/sandbox/<job>.json` + `runs.jsonl` (every run ever, for the multiple-looks count) |
| control | `results/CONTROL.json` — written by `/api/control` only |
| bank | read-only GET on the balance API |

### The process
`research/pintool.py` — one stdlib `http.server` on `127.0.0.1:8765` (`--lan`
to bind `0.0.0.0` for the phone), a job thread for sandbox runs, no
dependencies. **Never imports `pintake`.** `tool/index.html` — one file,
vanilla JS + Chart.js from cdnjs, tabs by URL hash, responsive, dark/light.

### Endpoints
| | |
|---|---|
| `GET /` | the page |
| `GET /api/schema` | params (type, range, default, meaning, why), fields, ops, actions, objectives — the UI draws itself from this |
| `GET /api/live` | process (alive, pid, profile, sha, since), version record, equity points, recent decisions, metrics with intervals, brakes, bars progress, bank |
| `GET /api/profiles` · `GET /api/profiles/<name>` · `POST /api/profiles` | list / get / save (validate; return problems as text, never silently coerce) |
| `POST /api/sandbox/run` | `{profile, hours, end, sweep?: {param, values}}` → job id; runs `pinsim.run()` in a thread |
| `GET /api/sandbox/jobs/<id>` | status, progress, result JSON |
| `GET /api/sandbox/history` | every run this machine has done: settings tried → multiple-looks threshold |
| `POST /api/control` | `{state}` or `{profile}` + typed confirmation; the ONLY writer of `CONTROL.json` |
| `GET /api/learn` | concept articles + the glossary built from the schema |

### The four tabs — each has one job
**LIVE — "what is it doing, how has it done."** Status strip (running/paused,
pid, profile + sha, uptime, brake counters 0/3 and $ toward the abort, bars
progress 32/180 and 0/40). Equity ticker: cumulative realised as a line, with
the standard stats — % change today / 7d / 30d / all, daily OHLC, max drawdown
**in wins-to-recover**, volume = fills, fill rate, per-trade hover, capital
deployed vs idle, **and a note that annualised past the capacity ceiling is
meaningless.** Metrics panel with intervals: loss rate (per close AND per fill),
fills/day (with hours covered — never a partial-day extrapolation), mean price,
EV per fill, and **the number needed to sway the average** = how many losses at
the run's mean loss size the run's realised P&L can absorb before going
negative, beside the break-even loss rate at the mean price paid vs the observed
rate. Decision feed: the latest closes — bought / refused (by which rule) /
skipped (why), each expandable to its decision record. Controls box: play /
pause / stop, greyed with the reason **"needs AMENDMENT 11 (control reader in
the trader)"** until that lands — an honest state, not a dead button.

**BUILDER — "change the strategy and see what it would have done."** Left:
the profile under edit — name; every param as a control drawn from the schema
with its meaning on hover and **the live value marked**; each param has "make
this depend on…" which turns it into a schedule (band editor); rules list with
add / edit rows (field · op · value, all/any, action, note); goal-search panel
(lever, objective, values). Run: hours + end (**the newest settlement is shown
and later windows are refused**). Right: results — overall and per rule, **FIT |
HOLDOUT columns always**, n as markets and closes, every rate with its
interval, the upper-bound label, the 70%-fill pair, the skips breakdown, the
losses list. Bottom: run history with the **multiple-looks threshold and a
curve-fitting warning that cannot be dismissed**. Save-as-profile. **No
control button exists on this tab.**

**PROFILES — "what strategies exist, which one is live."** Table: name, sha,
note, worst case (one losing close, closes to halt, max loss), last sandbox
result if any. Actions: load into builder; diff vs live; **deploy** = shows the
worst-case dollars, requires the name typed back, writes `CONTROL.json
{"profile": name, "sha": ...}`; the trader validates and restarts itself
(AMENDMENT 11). Until then deploy shows the same honest "needs A11" state.

**LEARN — "what does every word mean."** Glossary auto-built from PARAMS and
FIELDS (a control cannot exist without an entry here). Concept pages, each in
the plain-language register: the settlement window and why the last 60 s
decide everything; sigma and margin; why price matters more than confidence;
wins-to-recover and break-even loss rate; fit vs holdout and curve fitting;
why a replay is an upper bound; what each brake does; what a decision record
is; what a schedule is; what a tracker is.

### Venues and horizons (operator, 2026-09-11)
* **Robinhood as a second venue.** The decision code is venue-agnostic (it is
  index arithmetic); only the book/order adapters differ. So: a `venue` field on
  profiles and on the decision record, one adapter per venue, the same
  profile runnable on both, and the Live tab showing both bots. Planned, not
  built; nothing on Robinhood until its fee schedule, settlement wording and
  price divergence from the CF index are measured (the Friday list).
* **Not a trend/pattern identifier.** The edge is settlement mechanics -- the
  last 60 prints are mostly known, so the outcome is nearly arithmetic -- and it
  exists only in the final ~30 s. It does not generalise to longer horizons
  (4-11x overconfident past 30 s). It DOES generalise to any market whose
  settlement is a short time-average of a public index, whatever the market's
  length: other 15-min series, equity 15-min series (KXINX15M / KXNDQ15M, open
  question B3), and hourly/daily crypto series IF they settle on the same
  60-second average -- to be checked per series, one API call each.

### pinsim refactor the server needs
`pinsim.run(profile, hours, end, progress=None) -> summary` with the tape
window cached in-process per (hours, end) so a goal-search sweep loads the
tape once and replays N times. `main()` becomes a thin wrapper. Self-test kept.
Hours capped at 48 in the UI; the collector outranks the tool for RAM.

### Build order (each step ships usable)
1. ~~`pinsim.run()` + tape cache~~ DONE (cold 86 s / warm 15 s for 3 h, identical results) · 2. server: schema, profiles, live · 3. page:
Live + Learn (read-only, zero risk, useful at once) · 4. sandbox single run +
Builder tab · 5. sweeps + goal search + history · 6. Profiles tab · 7. control
endpoint + AMENDMENT 11 in the trader (own self-test, quiet-window restart).

## OPERATOR FEEDBACK ON v1 (2026-09-11) -- these come before anything else

1. **Design: Robinhood-like.** Clean, sparse, one big number per screen, green/red,
   thin type, rounded cards, dark. Not a dense dashboard.
2. **SIMPLE MODE by default.** One screen: running or not (with the reason if not),
   today's P&L, all-time P&L, wins / losses, bank, and one plain sentence of
   status. An "Advanced" switch reveals everything else. The operator does not
   yet know the vocabulary -- the tool must not assume it.
3. **More intuitive everywhere.** Every number has a one-line plain meaning next
   to it, not in a tooltip.
4. **THE REPLAY PLAYER -- the simulation as a live stock chart.** Pick any date
   and time in the tape (e.g. three days ago, Tuesday 14:00), press PLAY, and
   the chart advances as it looked on Kalshi: the index line, the strike, the
   settlement window; the bot's live variables changing with it -- confidence,
   margin, the price needed to sway the average, the offer on the book, what
   the rules say -- and a running tally (P&L, wins, losses, fills). Speed 1x to
   very fast, pause, step, and "play forward to <date/time>" which skips ahead.
   **The purpose is peace of mind that the backtest is real**, by seeing it
   behave live. Implementation: `pinsim.stream(profile, start, end)` yields one
   FRAME per second (index, best asks, fair, margin_sd, discount, sway price,
   decision + fired rules, tally); the server runs it in a thread into a
   buffer; the page polls `/api/replay/<id>?from=N` and renders at the chosen
   speed. Same decision code as live; the frames ARE the decision records.
5. A failed process check must never read as "not running" (fixed: unknown +
   log freshness).

## WHAT THE PLAYER SHOWED ON ITS FIRST RUN (2026-09-11) -- keep this on screen

Streamed the XRP loss window (2026-09-10 04:58:30 -> 05:00:20Z). At the live
signal second (t-21) the replay's model is IDENTICAL to live -- fair 1.0,
7.03 sd, sway 1.38882 -- but **the reconstructed book has NO yes ask at that
second** (`yes_ask: None`, `no_ask: 0.003`), so the replay says `no_offer`,
while live we were filled YES at 82c. Seven seconds later the index has
dropped, the model flips, and the replay buys NO at 84c and WINS (+$2.26).

So on this exact market the replay makes the opposite, correct trade -- and
the reason is the book: the offer we actually hit is not in the
snapshot+delta reconstruction at that second. **This is the adverse-fill
blind spot, reproducible, and the player must label it**: when a live fill
exists for a market and the replay shows no offer, say so in the frame.
Whether the missing level is a tape gap or an intra-second offer is an open
measurement (compare the live signal's book_age and the tape's deltas for
that market in the 2 s before 04:59:39).

## RESUME HERE (written 2026-09-11 ~01:0xZ, before the usage cutoff)

Done and pushed: `pinrules.py` (schema, rules, trackers, profiles, SCHEDULES --
any param as a band table over a field, e.g. SIZE by price -- self-test),
`profiles/default.json` (= the live rule), `pinsim.py --profile X --hours N
--end YYYYMMDDTHH --json out.json` (the sandbox backend: per-rule would-be
tallies, fit/holdout, 70%-fill pair). Verified on 6 settled hours ending
20260910T05: 23 traded, dump rule fired on real moments, JSON written to
`results/pinsim_default_6h.json` -- that file is the shape the tool reads.
`profiles/size_by_price_demo.json` (40 under 90c, 20 above) replays end to end
through the live decision code: `results/pinsim_demo_6h.json`.

Next, in order: `research/pintool.py` (stdlib http.server: `/api/live`,
`/api/profiles`, `/api/schema` from pinrules.PARAMS + FIELDS, `/api/sandbox/run`
spawning `pinsim --profile --json` in a thread, `/api/sandbox/status`,
`/api/control`, `/api/learn`; bind 127.0.0.1, `--lan` for the phone) then
`tool/index.html` (Live / Sandbox / Profiles / Learn; every param control drawn
from `/api/schema` with its meaning; rule editor = field/op/value rows +
action; FIT and HOLDOUT always side by side; Chart.js from cdnjs).

Three things noticed and NOT chased, for later:
* `/api/live` reads only the NEWEST log. The current version has restarted
  three times since 08:33Z, so the Live tab should aggregate every log whose
  start record carries the same profile sha / gate -- otherwise a restart
  resets the visible record to zero.
* The XRP loss (05:00Z close, live filled at 82c after bidding 95.7c) did NOT
  trip the dump rule in replay -- at the second the replay decides, the resting
  ask it sees is not the 82c we were actually filled at. The adverse-fill
  population is exactly what a replay of resting offers cannot see; the tool
  must say so wherever it shows the dump rule's would-be numbers.
* Settlements on file end 2026-09-10T05:45Z. `kalshi_fulltape.py` refreshes
  them (writes C:\kalsulltape, allowed). The tool's sandbox should show the
  newest settlement and refuse windows past it rather than "bought 0".

## Rules that do not bend

1. The sandbox build never imports `pintake` and never writes `CONTROL.json`.
2. Every rate shown carries n as markets AND closes and its exact interval.
3. Every sandbox result shows FIT and HOLDOUT side by side. Never one number.
4. Every replay result is labelled an upper bound and shows the 70%-fill pair.
5. Nothing the tool deploys skips the trader's self-test.
6. A profile that loosens a brake prints the worst-case dollars first.
