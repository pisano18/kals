# phone/commands: the contract for command-module authors (rebuild step 9)

> **Since steps 10-11 (2026-10-30) these modules ARE the phone.** `phone/router.py` dispatches every message to the
> Command a module here declares (pairing, the paired chat, the ledger refresh, the paused-bot page and the unknown
> answer are the router's); `Phone.text_*` is gone. `ctx.pp` is `research/phone/shared.py` (the helpers pinphone's
> module level held); the runtime is `phone/app.py`; `pinphone.py` is a launcher. A new command is a new module here:
> declare it, add a test under `phone/tests/`, and it is routed, listed in /help (section + order + help_line) and drawn
> after (chart) with no other edit. The old-vs-new tests compare against the frozen `research/pinphone_legacy.py` (until
> step 14). The rules below still hold; read "the old method" as "the frozen legacy phone".

Step 9 ADDS one module per phone command next to the old code. Nothing is switched over: `pinphone.Phone.handle` and
every `Phone.text_*` method keep answering the phone until the integration flip (step 10, one agent). Your module is
proven byte-identical to the old method by `research\golden\shadow.py` in all 8 golden worlds. The reference example is
`hedges.py` (/hedges).

## 1. Files you own (one lane per row; never edit another lane's files)

| lane | files (research\phone\...) | commands |
|---|---|---|
| D1 | `commands\status.py`, `commands\day.py`, `commands\days.py` | /status /s, /today /yesterday, /days |
| D2 | `commands\bots_page.py`, `commands\bot_page.py`, `commands\open_bets.py`, `commands\fills.py`, `commands\losses.py`, **`render\botcards.py`** (+ `render\__init__.py`) | /bots, every registry bot page (/pin /forecaster /fc /ladder /weather /wx /fx /jb /jumpband), /open, /fills /bets, /losses |
| D3 | `commands\race.py`, `commands\racestats.py` (+ the race helpers bars.py imports) | /race, /racestats |
| D4 | `commands\funds\` (`__init__.py` declares; `read.py`, `page.py`) | /funds /bank /accounts |
| D5 | `commands\speed.py`, `commands\server\` (`__init__.py` declares; `page.py`, `machine.py`, `aws.py`) | /speed, /server (+ `help ? aws setup`) |
| D6 | `commands\market.py`, `commands\brief_cmd.py`, `commands\bars_cmd.py`, `commands\features.py`, `commands\stats.py` | /market, /brief /summary, /bars, /features, /stats (hedges.py is done) |
| D7 | `commands\help_cmd.py`, `commands\pair.py`, `commands\mute.py`, `commands\controls.py`, `commands\update.py` | /help /?, /pair, /mute /unmute, /pause /start /stop, /update |

Your tests go in `research\phone\commands\tests\test_<module>.py` (create `tests\__init__.py` only if it is missing;
it is an empty file -- if two lanes both add it, it is the same empty file). **`render\botcards.py` (the shared `bs_*`
renderers: bs_bot_html, bs_all_html, bs_money_table, bs_days_table ... ) is owned by D2**; D1 and D3 import it once D2
has committed it, or use `ctx.pp.bs_*` until then. Do not edit `pinphone.py`, `botstats.py`, `tgcharts.py`,
`phone\context.py`, `phone\command.py`, `research\golden\*`, `bots\*`, `botdata\*`: if you need a change there, write it
in your final report (the integrator makes it).

Module names avoid `open`, `bars`, `brief`, `help` (they shadow modules: hence open_bets, bars_cmd, brief_cmd,
help_cmd).

## 2. The shape of a module

```python
"""/hedges -- one line: what the page is.  v-tg-rebuild step 9: Phone.text_hedges as a command module."""
from botdata.fmt import usd                      # pure helpers that already moved: import them
from phone.command import Command, declare
from phone.html import Html, esc, i_
from pindesk import et_str, pct


def load(ctx):                                    # ALL reading: ledger, files, botstats, Kalshi, the clock
    ho = list(reversed(ctx.ledger.hedge_outcomes()))[:8]
    return [(g, ctx.ledger.bank_at(g["t"]) if g.get("t") and g.get("net") is not None else None) for g in ho]


def render(rows, ctx):                            # render(data) or render(data, ctx): builds the reply from data only
    ...
    return Html("\n".join(out))


COMMAND = declare(Command(
    names=("/hedges",), section="now", order=60,
    help_line="/hedges — the pin bot's insurance, whether it was needed, % of the bank",
    chart="hedges", load=load, render=render))
```

- `load(ctx) -> data` reads; `render(data)` or `render(data, ctx) -> Html | str | None` formats. Keep reads out of
  render (render(data, ctx) is for `ctx.pp.<helper>` and `ctx.cmd`, not for reading). A command that cannot be split
  without changing its bytes (a worker, a state change: controls, /update, /mute, /pair) uses `handle=fn(ctx)` instead.
- `fail=lambda e: "Could not build /x: %s\n..." % str(e)[:200]` reproduces the old method's
  `except Exception as e: log(traceback.format_exc()); return "..."` wall: Command.run catches, logs the traceback
  with phone.log.log and returns fail(e). Where the old method had NO try/except, give no `fail` (the exception
  propagates, exactly as before). If the old wall covers only part of the work, put that part's try/except in your own
  code instead and leave `fail` out.
- Several commands in one module: `COMMANDS = declare(Command(...), Command(...))`. A subpackage declares in its
  `__init__.py`.
- Keep the exact text: copy the old method's string literals, order of reads, `%` formats, `.replace(" 0", " ")`
  tricks, emoji. **No behaviour change of any kind** -- not a typo fix, not a cache, not a reordered Kalshi read
  (shadow compares the Kalshi requests and fence events too). A bug you see: report it, keep it.

### Command fields (phone/command.py)

| field | meaning |
|---|---|
| `names` | every name, main first: `("/fills", "/bets")`. lower-case, slash, no `@`. The router splits `/Fills@kalsbot x` -> `ctx.cmd == "/fills"`, `ctx.arg == "x"` exactly as Phone.handle does. |
| `section`, `order`, `help_line` | /help (generated in step 10): section one of `money one_bot now server controls` (or None = not listed), position, and the line copied **verbatim** from `pinphone.HELP_TEXT`. The one-bot pages (D2 bot_page, D3 race/racestats) use `section="one_bot"`, `help_line=None`: their lines are the registry's `Bot.help`. Orders: money -- /today·/yesterday 10, /days 20, /stats 30, /funds 40, /bots 50; now -- /status 10, /open 20, /fills 30, /market 40, /losses 50, /hedges 60, /brief 70, /bars 80, /features 90; server -- /speed 10, /server 20; controls -- /pause 10, /start 20, /stop 30 (line `<code>/stop yes</code> — stop right now`), /mute·/unmute 40, /update 50. /help, /pair: section None. |
| `chart` | the picture after the words: None, one kind for every name, or `{name: kind}`. Must equal `tgcharts.kind_of(name)` for every name (shadow checks): status (/status /s), today, yesterday, days (/days /brief /summary), stats, funds (/bots /funds /bank /accounts), `bot:<name>` per registry bot (/race and /racestats -> bot:race), losses, hedges, fills (/fills /bets), market, bars; everything else None. |
| `needs_ledger` | default True: the router refreshes `ctx.ledger` first (Phone.handle refreshes for every command). |
| `runs_in_worker` | True for commands that start a thread that later calls `ctx.say` (controls, /update). |
| `examples` | extra message texts shadow.py runs besides the bare names: `("/server help", "/server ?", "/server aws", "/server setup")`, `("/stop yes", "/stop no")`. |

What the router (step 10), not your module, does -- so leave it out: pairing and the paired-chat check, the ledger
refresh, the paused/retired-bot answer (`Phone.text_hidden`: shadow marks those pairs `hidden` and does not compare
them), the unknown-command answer (D7 provides the words in help_cmd), the chart after the words.

## 3. Ctx (phone/context.py)

Built with `Ctx.from_phone(phone, text)`: every field is the value the Phone holds; every provider is the old method's
expression verbatim, resolved at call time (so a planted seam or a patched pinphone global is seen exactly as before).

| field / provider | the old code |
|---|---|
| `ctx.cmd`, `ctx.arg`, `ctx.text`, `ctx.chat_id` | handle's `cmd`, `arg`, the stripped text, the chat |
| `ctx.pp` | the old pinphone MODULE (`__main__` under `pinphone.py --selftest`): helpers and constants not moved yet |
| `ctx.ledger`, `ctx.results` | `self.ledger`, `self.ledger.results` |
| `ctx.now()` | `self.now()` |
| `ctx.health()` | `self.health_fn()` |
| `ctx.procs()` | `self.procs_fn()` |
| `ctx.procs_cached()` | `cached_python_procs() if self.procs_fn is python_procs else self.procs_fn()` (/racestats) |
| `ctx.versions_path`, `ctx.race30_epoch` | `self.versions_path`, `self.race30_epoch` |
| `ctx.bs()` | `_bs()` (botstats, imported late) |
| `ctx.bs_get(name)` | `self._bs_get(name)` ('all' or a bot) |
| `ctx.bs_getter`, `ctx.bs_procs` | `self.bs_getter`, `self.bs_procs` (pass them on exactly as the old code did) |
| `ctx.active()` | `self.active()` |
| `ctx.funds_get()` | `self.funds_getter or _bs().default_getter()`; raw: `ctx.funds_getter` |
| `ctx.machine()`, `ctx.ping()`, `ctx.pots()` | `(self.machine_fn or machine_read)()`, `(self.ping_fn or kalshi_ping)()`, `(self.pots_fn or _bs().cached_pots)()` |
| `ctx.aws_http` | `self.aws_http` (pass as-is: `aws_cost(now, http=ctx.aws_http)`) |
| `ctx.bars_fn`, `ctx.chart_fn`, `ctx.chart_stale_s` | the same Phone attributes |
| `ctx.sides()`, `ctx.markets()` | `self._sides()`, `self._markets()` |
| `ctx.cfg`, `ctx.cfg_path` | `self.cfg`, `self.cfg_path` |
| `ctx.say(text)` | `self.say(text)` |
| `ctx.state` | the mutable runtime state (`muted`, `busy`, `_bars_d`, `_updating`, `_exit_now`, `last_*`): the Phone itself until step 11. Write only what the old method wrote (`ctx.state.muted = True`; /bars sets `ctx.state._bars_d`). |

`FakeCtx` (tests): `FakeCtx(text="/hedges", now=T, ledger=fake, pp=pinphone, active=("pin",), bs_get={"all": {...}},
health={...}, machine={...}, ping={...}, pots={...}, markets={...})`; anything not planted raises `CtxMissing`.

**Helpers.** Use what has already moved: `phone.html` (Html, esc, b_, i_, table, pre, details, elines, hbar, spark,
split_*), `phone.log.log`, `botdata.*` (fmt: `usd` == pinphone.usd, `dollars`; clock; ...), `bots` (the registry),
`pindesk` (et_str, et_day, pct, coin, money, ...). Any OTHER pinphone module-level name -- a helper, a constant, a
table, a cache dict, a patched global -- is used as `ctx.pp.<name>` (e.g. `ctx.pp.nice_coin`, `ctx.pp.RESULTS`,
`ctx.pp.FUNDS_WHAT`). **Never `import pinphone`** (under `--selftest` pinphone runs as `__main__`; an import is a second
copy whose patched globals are not the ones the test set). You may COPY a pinphone helper into your module only when
your group alone uses it and it reads no pinphone global or cache (copy it verbatim, with a `# from pinphone.<name>`
comment); when in doubt, `ctx.pp`. The integrator moves the shared ones out in steps 10-12.

## 4. Rules (test_context.py's source scan checks the first five on every file under phone\commands)

1. No `urllib` except the /server AWS module (`commands\server\aws.py`); HTTP goes through phone/transport or
   `ctx.aws_http`.
2. No `subprocess` except the /update module (`commands\update.py`).
3. No `pindesk.do_start / do_pause / do_stop` except the controls module (`commands\controls.py`).
4. No `import pinphone` / `from pinphone import` (use `ctx.pp`).
5. Every text `open()` passes `encoding=` (utf-8, as the old code did).
6. No behaviour change: same bytes, same reads, same Kalshi requests, same log lines.
7. Keep the old Phone methods and every other existing file untouched -- you only ADD files.
8. Laptop only: no ssh, no Kalshi, no Telegram, no keys; never `C:\kals-live-0925n`, `boot_all.ps1` or a trading bot.
   One git worktree per lane; commit there; never push, rebase or reset.

## 5. Prove it: shadow.py for your group

From YOUR worktree (the harness runs from the folder it is in; `--code` is the tree under test):

```powershell
C:\Python314\python.exe research\golden\shadow.py --code <worktree>\research --module phone.commands.hedges [--module ...] [--jobs 2]
C:\Python314\python.exe research\golden\shadow.py --code <worktree>\research --case "/server help=phone.commands.server"
C:\Python314\python.exe research\golden\shadow.py --code <worktree>\research --only "^(fills|losses) "    # pair ids 'module /text'
```

Every name and `examples` text of each module is run in all 8 worlds (`--world W` to narrow while iterating; the
fixture defaults to the newest under `C:\kals-golden\fixtures`). Per pair it compares reply text, type, split chunks,
say() messages, mute state, exception, chart kind, Kalshi requests and fence events. The last line must read
`shadow: IDENTICAL in all 8 world(s)`; exit 0. Differences: `<out>\shadow.md` (unified diffs); a traceback in the new
path is in that file too. One world takes ~7 s plus the copy.

Before you finish: `C:\Python314\python.exe research\phone\tests\test_context.py` (the source rules), your own tests,
`pinphone.py --selftest`, `botstats.py --selftest`, `tgcharts.py --selftest` all pass (unchanged: you only added files),
and shadow is identical in all 8 worlds for every module you wrote. Report: commit, files, shadow's last line, and any
helper you copied or anything the integrator must change.

## 6. Pictures: new charts must use base.money_axis / time_axis (10-30)

A command's picture is a `chart=` kind drawn by a module in `research\phone\charts\` (one function per kind, wired in
`phone/charts/__init__.py: build`). Every axis goes through the layout engine in `phone/charts/base.py` (its docstring
is the reference): `money_axis` / `value_axis` / `pct_axis` for values (the scale from the data's own range and typical
move, nice 1/2/2.5/5 ticks, never an offset or 1e6), `time_axis` / `clock_axis` / `category_axis` for x (each panel
its own span), and `mark_last` / `annotate_change` / `ref` / `shade` for the words on the data. A chart module never
calls `set_xlim` / `set_ylim` / `set_*ticks*` / locators / formatters itself: `phone/charts/tests/test_layout_rules.py`
(run by `tgcharts.py --selftest`) scans the sources for that and checks every picture the tests draw (base.audit: 4-7
ticks, the data fill 60% of each axis, no overlapping tick labels, under 300 KB). A golden replay with
`KALS_CHART_STRICT=1` set raises on any broken rule, so the fixture's real pictures are checked the same way.

**Money words (10-31, v-tg-money-words).** Money MADE is said as made: a headline or panel title with a signed amount
(`+$x` / `-$x`), and every panel whose dollar axis is money made (`money_axis(kind="pnl")`), says "made" / "lost" /
"profit" / "loss" in words (`base.made(v)` gives `made +$18.40` / `lost -$5.00`). A bot's own picture opens with what its
pot holds now, through `base.bot_headline` (`Pin bot · bank $2,461.68 · made +$1,406.27 all time · +$0.23 today`), so a
deposit is seen to land. base.audit checks both on every picture (MADE_WORDS, BANK_WORDS); test_layout_rules.py
test_money_words / test_bot_pictures_open_with_their_bank. Text pages: `bs_headline` says `Pin bot made +$5.31 today`.

**Settings a bot changes by itself (10-31, v-tg-settings-now).** A bot that resizes itself declares the records it writes
then in `Records.resize` (+ `resize_as_start`); every reader of its settings goes through `botdata.logs.settings_now`
(the start record with its newest self-changes laid over). botdata/tests/test_settings_now.py checks every live
script's self-change kinds are declared and scans bots/ and botdata/ for a start-record read without them (a deliberate
one says `# start-only: <why>`). A % of a bank counts a deposit or withdrawal only from when it landed
(`botdata.pots.span_base`; several days: each day's % chained).

## 7. Every one-bot page states its strategy (v-tg-strategy, 10-31)

A bot's own page -- the registry bot pages (`render/botcards.bs_bot_html`), /race, and the paused-bot answer
(`router.hidden_reply`, legacy `Phone.text_hidden`) -- shows `botcards.strategy_html(name)`: the registry's
`Bot.strategy` (a required field; `bots.validate` refuses an empty one, a dash, a sentence with no full stop) under the
header. A new bot or a new one-bot page goes through that one helper; `phone/tests/test_strategy.py` checks every
registry bot on every such page, and keeps the sentences under 600 characters so a page still fits one message.
