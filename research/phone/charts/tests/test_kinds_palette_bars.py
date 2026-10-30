"""test_kinds_palette_bars.py -- which command gets which picture, one colour a bot (from the registry), the 30-day line's
colour, /bars, and the tgcharts facade's names.

v-tg-rebuild step 8 (2026-10-30): moved out of tgcharts.selftest unchanged, plus the registry and facade checks.
"""
import colorsys

import bots
from phone.charts import CMD_KIND, build, kind_of
from phone.charts.base import (AVG30, BOT_COLOUR, BOT_ORDER, BOT_SHORT, DOWN, GREY, INK2, MUTED, ORANGE, UP)
from phone.charts.tests.planted import NOW, ck, is_png


def test_bars_only_running_tests():
    # /bars: only a RUNNING test is drawn
    d = {"fresh": {"arm": "arm-fresh500", "days": 3.2, "window_days": 7, "net": -12.43, "losers": 2,
                   "h2h": {"arm_extra_losers": [1]}, "verdict": "TOO EARLY", "arm_running": True},
         "btcd": {"paper": {"fired": 19, "contracts": 31.0, "lost_le30": 0}, "paper_arm": "arm-btcd", "paper_days": 24.0,
                  "window_days": 7, "verdict": "KILL"},
         "race": {"z3": {"log": True, "races": 134, "losses": 1, "first50_losses": 1, "verdict": "TOO EARLY",
                         "ran": "STOPPED: ran Sep 22 to Oct 01"}, "gap075_ran": "STOPPED: ran Sep 24 to Sep 27"},
         "controls": {"a": None}}
    got = build("bars", {"now": NOW, "bars": d})
    ck(is_png(got) and "hourly BTC paper: KILL" in got[1] and "z3: STOPPED" in got[1],
       "/bars: the running fresh test is drawn; the decided and the stopped ones are named, not drawn")
    d["fresh"]["arm_running"] = False
    ck(build("bars", {"now": NOW, "bars": d}) is None, "/bars: no running test -> no picture")


def test_words_only_commands():
    ck(kind_of("/open") is None and kind_of("/stop") is None and kind_of("/pause") is None and kind_of("/help") is None
       and kind_of("/mute") is None and kind_of("/today") == "today" and kind_of("/fc") == "bot:forecaster",
       "words-only commands get no picture; the controls never queue one")
    every = {c: "bot:" + b.name for b in bots.all_bots() for c in tuple(b.commands) + tuple(b.extra_commands)}
    ck(all(CMD_KIND.get(c) == k for c, k in every.items()),
       "every registry bot's commands draw that bot's page (%d commands)" % len(every))


def test_one_colour_a_bot():
    def _hs(hexc):
        h_, s_, _v = colorsys.rgb_to_hsv(*(int(hexc[i:i + 2], 16) / 255.0 for i in (1, 3, 5)))
        return 360.0 * h_, s_
    hs = {b: _hs(x) for b, x in BOT_COLOUR.items()}
    ck(len(set(BOT_COLOUR.values())) == len(BOT_COLOUR) == len(BOT_ORDER) and set(BOT_ORDER) == set(BOT_SHORT)
       and all(s_ < 0.25 or (min(h_, 360.0 - h_) >= 20 and abs(h_ - 120.0) >= 40) for h_, s_ in hs.values()),
       "one colour a bot, none of them the red or green of a loss or gain: %s"
       % ", ".join("%s %.0f deg" % (b, h_) for b, (h_, _s) in hs.items()))
    ck(BOT_COLOUR == bots.BOT_COLOUR and BOT_SHORT == bots.BOT_SHORT and BOT_ORDER == bots.BOT_ORDER,
       "the names and colours are the registry's (bots/<name>.py short= / colour=)")
    _h30, _s30, _v30 = colorsys.rgb_to_hsv(*(int(AVG30[i:i + 2], 16) / 255.0 for i in (1, 3, 5)))
    ck(AVG30 not in BOT_COLOUR.values() and AVG30 not in (UP, DOWN, ORANGE, GREY, MUTED, INK2) and _s30 < 0.25,
       "the 30-day line's colour %s is a muted slate (saturation %.2f): not a bot's, not the red or green of money, not "
       "the 7-day orange" % (AVG30, _s30))


def test_facade_names():
    import tgcharts as T
    names = ("build", "kind_of", "STALE_S", "CMD_KIND", "LEDGER_KINDS", "BOT_SHORT", "BOT_COLOUR", "BOT_ORDER",
             "ACCOUNT_NAME", "POT_WHAT", "all_losses", "all_day_markets", "by_now", "usd", "prev_day", "LONG_DAYS",
             "AVG_DAYS", "MAX_BYTES", "ChartCtx", "selftest")
    missing = [n for n in names if not hasattr(T, n)]
    ck(not missing and T.CMD_KIND is CMD_KIND and T.kind_of("/jb") == "bot:jumpband" and T.STALE_S == 120,
       "tgcharts (the facade) keeps every name pinphone, bars, the golden harness and the registry tests use: %s"
       % (missing or "all there"))


TESTS = [test_bars_only_running_tests, test_words_only_commands, test_one_colour_a_bot, test_facade_names]
