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

- [ ] **`research/pinrules.py`** — param schema, condition language, profile
      load/validate/save, `decide(profile, record)`. Self-test plants rules and
      checks refuse/log/allow, range validation, and that the crazy-deal rule
      reproduces the two real losses and spares the real cheap wins.
- [ ] **`profiles/default.json`** — today's live rule exactly (A9 + A10b).
- [ ] **`pinsim.py --profile`** — per-rule would-be tallies, fit/holdout.
- [ ] **`research/pintool.py`** — stdlib `http.server`; serves `tool/index.html`
      and JSON: `/api/live` (tail of the newest live log → state, equity curve,
      the live "number needed to sway the average", brake counters, bars
      progress), `/api/profiles` (list/get/save), `/api/sandbox/run` (background
      thread running pinsim with a profile → job id → `/api/sandbox/status`),
      `/api/control` (the ONLY writer of `results/CONTROL.json`), `/api/learn`.
      Binds `127.0.0.1` by default; `--lan` binds `0.0.0.0` for the phone.
- [ ] **`tool/index.html`** — one file, four tabs: **Live · Sandbox · Profiles ·
      Learn**. Chart.js from cdnjs. Responsive so the phone works.
- [ ] **Live tab** — equity curve as a stock ticker (% change today/7d/30d/all,
      OHLC by day, max drawdown in *wins-to-recover*, volume = fills, fill
      rate, per-trade hover, capital deployed vs idle); colour-coded live
      metrics; the number needed to sway the average, updating live; brake
      counters; progress to the pre-registered bars; play/pause/stop.
- [ ] **Sandbox tab** — pick/edit a profile, run it on the tape, see per-rule
      results with FIT and HOLDOUT always side by side, the live setting marked
      on every control, a "you are now curve fitting" warning after N runs
      with the multiple-looks threshold shown. **No code path to the order
      API and no writer for CONTROL.json — an absent button, not a disabled
      one.**
- [ ] **Profiles tab** — save the sandbox state as a named profile; deploy =
      writes `CONTROL.json {"profile": X}`; the trader validates (full
      self-test + range checks) and restarts itself cleanly; loosening a brake
      shows the worst-case dollars and needs typed confirmation; the log
      records profile name + contents + hash at start.
- [ ] **Learn tab** — every param's explanation comes from the schema (the tool
      cannot show a control without its meaning); plus concept pages: the
      settlement window, sigma and margin, why price matters more than
      confidence, wins-to-recover, break-even loss rate, fit vs holdout, why a
      replay is an upper bound, what the brakes do.
- [ ] **`pinrun.py --profile` + CONTROL.json reader** — separate amendment.
      Pause = stop opening positions, keep settling; stop = finish open
      positions, write `end`, exit.

## Rules that do not bend

1. The sandbox build never imports `pintake` and never writes `CONTROL.json`.
2. Every rate shown carries n as markets AND closes and its exact interval.
3. Every sandbox result shows FIT and HOLDOUT side by side. Never one number.
4. Every replay result is labelled an upper bound and shows the 70%-fill pair.
5. Nothing the tool deploys skips the trader's self-test.
6. A profile that loosens a brake prints the worst-case dollars first.
