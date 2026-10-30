#!/usr/bin/env python3
r"""tgcharts.py -- the phone's pictures (FACADE). The code lives in research/phone/charts/ (one module a picture family:
day, days, stats, funds, bot, losses, small, bars_chart; base = matplotlib on first use, axes helpers, palette) and the
numbers in research/botdata/series.py; per-bot names and colours come from the registry (research/bots).

v-tg-rebuild step 8 (2026-10-30). This file keeps every name pinphone, bars, the golden harness and the tests use
(build, kind_of, STALE_S, CMD_KIND, LEDGER_KINDS, BOT_SHORT, BOT_COLOUR, BOT_ORDER, ACCOUNT_NAME, POT_WHAT,
all_losses, all_day_markets, by_now, usd, prev_day, ...). build() and the data calls take a phone.charts.ChartCtx or
the old dict with "pp" (the pinphone module: Phone._chart_ctx builds it today).

    python research/tgcharts.py --selftest      # every chart drawn from planted data, no file or network read
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from botdata import series                                                                    # noqa: E402
from botdata.series import (AVG_DAYS, LONG_DAYS, PACE_DAYS, WINDOW_DAYS, avg_by_day, by_now,   # noqa: E402,F401
                            closes_cum, day_avg, day_base, ledger_days, pace_curves, prev_day)
from phone.charts import CMD_KIND, LEDGER_KINDS, ChartCtx, as_ctx, build, kind_of             # noqa: E402,F401
from phone.charts.base import (ACCOUNT_NAME, BOT_COLOUR, BOT_ORDER, BOT_SHORT, DPI, MAX_BYTES,  # noqa: E402,F401
                               POT_WHAT, ROLL, STALE_S, W_IN, account_name, mpl, pctx, usd)
from phone.charts.base import et_short as et_clock                                            # noqa: E402,F401
from phone.charts.day import LOSS_NAMES                                                       # noqa: E402,F401
from phone.charts.losses import LOSS_LANE_DAYS, LOSS_WEEKS                                    # noqa: E402,F401


def all_day_markets(ctx):
    """Every bot's settled markets from botstats: (bs, pot context, [(ET close day, settled epoch, $, bot)] by time,
    [pots that could not be read]) -- botdata.series.all_day_markets for a ChartCtx or the old dict."""
    return series.all_day_markets(*as_ctx(ctx).bs_args())


def all_losses(ctx, week_days=7):
    """Every bot's LOSING markets from botstats: (bs, losers, {bot: totals}, [bots not read]) -- the /losses words'
    and picture's source, botdata.series.all_losses for a ChartCtx or the old dict."""
    return series.all_losses(*as_ctx(ctx).bs_args(), week_days=week_days)


def selftest():
    """Every chart drawn from planted data (research/phone/charts/tests, run in order); last line 'tgcharts selftest:
    OK (matplotlib X)', a failed check exits 1 with 'tgcharts selftest: FAILED -- ...'."""
    from phone.charts.tests import run
    run.main()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
