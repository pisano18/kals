"""phone.charts -- the phone's pictures: real x-y charts, sent right after a command's words (research/tgcharts.py is
the facade pinphone imports).

THE OPERATOR, 2026-10-18: "Telegram still looks very bad, do actual x y charts and that solution should
work for most commands. For the others figure something out."

v-tg-rebuild step 8 (2026-10-30): tgcharts.py split into one module a picture family, the numbers into
botdata/series.py, the per-bot names and colours from the registry (research/bots), and ctx["pp"] (the pinphone module
passed in) replaced by an explicit ChartCtx (ctx.py). build() takes a ChartCtx or the old dict.

WHAT EACH COMMAND GETS (one PNG, sent by pinphone with sendPhoto after the text):
  /today /yesterday        day.py: every bot's running total market by market on the ET clock (each losing market
                           marked and named by its bot and $); orange dashes = the average day of the 7 days before,
                           slate dash-dots = of the 30 days before; right axis = % of all pots at the start of the day
  /days /brief /summary    days.py: every ET day: $ bars, % of the bank bars (7-day and 30-day average lines), the
                           running total ($ and % of money put in)
  /stats                   stats.py: every bot, one colour a bot: $ each day stacked by bot, the day's net as % of all
                           pots, each bot's running total. The main account's old picture when botstats cannot be read
  /bots /funds /bank /accounts   funds.py: every RUNNING account's money over time, a panel each, in its bot's colour
  each bot's commands      bot.py: that bot's pace today, running total and win rate over its last 50 markets (races)
  /losses                  losses.py: every bot's losing markets, coloured by bot
  /hedges /status /fills /bets /market   small.py: the pin bot's own log (each says "pin bot")
  /bars                    bars_chart.py: each RUNNING test's numbers against its pre-registered bar
  no picture: /open, /help, /pair, /pause /start /stop, /mute /unmute.

RULES
  * Every figure is computed by the function the command's words use (pindesk.Ledger, botstats,
    pinphone.markets_from / window_stats, bars.gather, botdata.series) -- nothing recomputed a second way.
  * Live only: data is read at the request -- a copy of the ledger taken right after the words were built,
    botstats re-read at most once a minute exactly as the words are -- and pinphone drops a picture whose
    turn comes more than STALE_S late. A STOPPED bot, account or test is never drawn; it is named in the
    caption instead.
  * Off the poll loop: pinphone draws on one background thread; alerts, PAUSE and STOP never wait.
  * matplotlib (Agg, no pyplot, no window) is imported on first use (base.mpl). Missing -> pinphone sends words only.
"""
import bots
from phone.charts.base import STALE_S                                # noqa: F401
from phone.charts.ctx import ChartCtx, as_ctx                         # noqa: F401
from phone.charts import bars_chart, bot, day, days, funds, losses, small, stats

# command -> picture. Words-only commands are simply absent. Each bot's commands (its page and its aliases) come from
# the registry, in tgcharts' old order: the shared pages, the one-bot pages, the race's own page, then the pin bot's.
_SHARED = (("/status", "status"), ("/s", "status"), ("/today", "today"), ("/yesterday", "yesterday"),
           ("/days", "days"), ("/brief", "days"), ("/summary", "days"), ("/stats", "stats"),
           ("/bots", "funds"), ("/funds", "funds"), ("/bank", "funds"), ("/accounts", "funds"))
_PIN_LOG = (("/losses", "losses"), ("/hedges", "hedges"), ("/fills", "fills"), ("/bets", "fills"),
            ("/market", "market"), ("/bars", "bars"))
CMD_KIND = dict(_SHARED + tuple(bots.CMD_KIND_BOTS.items()) + _PIN_LOG)
# the pictures that read the ledger copy (pinphone puts ctx["ledger"] / ChartCtx.ledger only for these)
LEDGER_KINDS = frozenset(["status", "today", "yesterday", "days", "stats", "losses", "hedges", "fills", "market"])


def kind_of(cmd):
    return CMD_KIND.get(cmd)


def build(kind, ctx):
    """(png bytes, caption) for picture `kind`, or None when there is nothing live to draw. `ctx`: a ChartCtx, or the
    old dict with "pp" (pinphone's Phone._chart_ctx), adapted by ctx.as_ctx."""
    ctx = as_ctx(ctx)
    if kind in ("today", "yesterday"):
        return day.chart_day(ctx, kind)
    if kind == "stats":
        return stats.chart_stats(ctx)
    if kind == "days":
        return days.chart_days(ctx, kind)
    if kind == "funds":
        return funds.chart_funds(ctx)
    if kind.startswith("bot:"):
        return bot.chart_bot(ctx, kind[4:])
    fn = {"losses": losses.chart_losses, "hedges": small.chart_hedges, "status": small.chart_status,
          "fills": small.chart_fills, "market": small.chart_market, "bars": bars_chart.chart_bars}.get(kind)
    return fn(ctx) if fn else None
