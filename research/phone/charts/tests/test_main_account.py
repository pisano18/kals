"""test_main_account.py -- the pictures drawn from the main account's own ledger (pindesk.Ledger) and Kalshi ledger file:
/today /yesterday /days /losses when botstats cannot be read, /status /fills /market, /stats' fallback and /hedges.

v-tg-rebuild step 8 (2026-10-30): moved out of tgcharts.selftest unchanged; the ctx is still the OLD dict with a
planted "pp" (build adapts it), as pinphone passes it today.
"""
import time

from phone.charts import build
from phone.charts.tests.planted import NOW, NoBS, ck, empty_ledger, is_png, kalshi_ledger_file, planted_ledger, planted_pp


def test_every_ledger_picture():
    ctx = {"now": NOW, "ledger": planted_ledger(), "pp": planted_pp()}
    for kind in ("today", "yesterday", "days", "losses", "status", "fills", "market"):
        t0 = time.time()
        got = build(kind, ctx)
        ck(is_png(got), "%s: a PNG (%d KB, %.1f s), caption %r" % (kind, len(got[0]) // 1024 if got else 0,
                                                                  time.time() - t0, (got or ("", ""))[1][:60]))


def test_nothing_to_draw():
    ck(all(build(k, {"now": NOW, "ledger": empty_ledger(), "pp": planted_pp()}) is None
           for k in ("today", "yesterday", "days", "losses", "fills", "market")),
       "nothing settled / no orders / no closes -> no picture (the words already say so)")


def test_stats_and_hedges_from_pinphone_markets():
    # /stats and /hedges through pinphone's own market functions (a planted kalshi ledger, read from a temp file)
    led = planted_ledger()
    with kalshi_ledger_file(led) as PP:
        ctx2 = {"now": NOW, "ledger": led, "pp": NoBS(PP)}
        for kind in ("stats", "hedges"):
            got = build(kind, ctx2)
            ck(is_png(got) and (kind != "stats" or "main account" in got[1]),
               "%s: a PNG from pinphone.markets_from / window_stats (%d KB)%s" % (
                   kind, len(got[0]) // 1024 if got else 0,
                   "; botstats unreadable -> the main account's picture" if kind == "stats" else ""))


TESTS = [test_every_ledger_picture, test_nothing_to_draw, test_stats_and_hedges_from_pinphone_markets]
