"""test_botstats_charts.py -- the pictures drawn from botstats (every pot, Kalshi's books): /bots /funds, each bot's page,
/losses, /today /yesterday, /stats, the 30-day lines, stopped bots, the jump band and the paused race.

v-tg-rebuild step 8 (2026-10-30): moved out of tgcharts.selftest unchanged. The old test was one sequence over one
planted cache; here each test plants its own (planted.planted_botstats) in the state that sequence had reached.
"""
import os
import time

import pindesk
from pindesk import et_day
from botdata import series
from phone.charts import build, kind_of
from phone.charts.base import AVG30, BOT_COLOUR, BOT_SHORT, usd
from phone.charts.tests.planted import FX_PROC, NOW, ck, is_png, planted_botstats, px_count


def test_funds_and_the_fx_taker():
    with planted_botstats(fx=False) as (BS, c, procs, _td, ctx3):
        got = build("funds", ctx3)
        ck(is_png(got) and "subaccount 3;" in got[1] and "subaccounts 5 + 4." in got[1]
           and "4 ()" not in got[1] and "weather" not in got[1] and "fx taker" not in got[1].lower(),
           "/funds: a PNG of the running accounts; the stopped weather account and the stopped FX taker's two pots are "
           "not drawn, and named by account only -- never by a paused or retired bot (v-tg-active): %s"
           % (got[1] if got else None))
        ck(build("bot:fx", ctx3) is None, "/fx: not in the process table -> no picture")
        procs.append(FX_PROC)
        got = build("funds", ctx3)
        _pts, _v, _why, _each = series.account_series(BS, c, ("5", "4"), NOW)
        _won = sum(BS.market(r_)["money"] for s_ in ("4", "5") for r_ in c["subs"][s_]["rows"].values()
                   if not r_["ticker"].startswith("KXBTC"))
        ck(is_png(got) and "fx taker" not in got[1] and _why is None and _each == [100.0, 100.0] and _v == 200.0
           and abs(_pts[-1][1] - (200.0 + _won)) < 1e-6,
           "/funds with the FX taker running: ONE panel for its two pots, $200 now = $100 + $100; its line = the $200 "
           "moved into 5 and 4's pool 0 + its own markets (the $55 moved into 4's pool 2 and the reward-test leg "
           "left out): %r" % (((_pts[-1][1] if _pts else None), _v, _each, _why),))
        ck(kind_of("/fx") == "bot:fx" and is_png(build("bot:fx", ctx3)), "/fx: a PNG of the FX taker over both pots")


def test_losses_bot_pages_today():
    with planted_botstats(fx=True) as (BS, _c, _procs, _td, ctx3):
        _bsl, _lrows, _lper, _lmiss = series.all_losses(BS, NOW)
        got = build("losses", ctx3)
        ck(is_png(got) and "every bot" in got[1] and not _lmiss
           and {r["bot"] for r in _lrows} >= {"pin", "race", "forecaster", "fx"}
           and all(r["money"] < 0 for r in _lrows) and sum(p["lost"] for p in _lper.values()) == len(_lrows)
           and [(r["day"], r["t"]) for r in _lrows] == sorted([(r["day"], r["t"]) for r in _lrows], reverse=True),
           "/losses (10-26): every bot's losing markets (pin, race, forecaster, fx ...), newest day first, one PNG "
           "coloured by bot: %d losers" % len(_lrows))
        for b in ("pin", "race", "forecaster", "ladder"):
            got = build("bot:" + b, ctx3)
            ck(is_png(got), "/%s: a PNG (%d KB)" % (b, len(got[0]) // 1024 if got else 0))
        _bs3, _p3, _rows3, _miss3 = series.all_day_markets(BS, NOW)
        _want = round(sum(v for d_, _t, v, _b in _rows3 if d_ == et_day(NOW)), 4)
        got = build("today", ctx3)
        ck(is_png(got) and "every bot's money" in got[1] and not _miss3
           and {b for _d, _t, _v, b in _rows3} >= {"pin", "race", "forecaster", "ladder"},
           "/today from botstats: every pot's markets (pin, race, forecaster, ladder), not the main account only; "
           "today %s" % usd(_want))
        ck(abs(_want - sum(BS._money_block(BS._load(NOW, None, None)[0], b_, et_day(NOW), _p3)["today"]["money"]
                           for b_ in tuple(BS.BOTS) + ("other",))) < 1e-6,
           "/today's all-bots total = the sum of every bot's botstats 'today' (the /bots number)")
        _each = {}
        for d_, _t, v, b_ in _rows3:
            if d_ == et_day(NOW):
                _each[b_] = _each.get(b_, 0.0) + v
        ck(all(("%s %s" % (BOT_SHORT[b_], usd(v))) in got[1] for b_, v in _each.items()) and "named by its bot" in got[1],
           "/today (10-26): each bot's money that day is said (%s) and the losing markets are named by bot"
           % ", ".join("%s %s" % (b_, usd(v)) for b_, v in sorted(_each.items())))
        ck(is_png(build("yesterday", ctx3)), "/yesterday from botstats: a PNG")


def test_stats_one_colour_a_bot():
    # /stats (10-26): every bot's money, one colour a bot. A bot with only LOSSES still draws (planted: every
    # weather market lost): its colour is on the picture, and none of it when it has no market at all
    with planted_botstats(fx=True) as (BS, c, _procs, _td, ctx3):
        sv_w = c["subs"]["3"]["rows"]
        try:
            c["subs"]["3"]["rows"] = {k_: dict(r_, market_result="no", revenue=0, value=0) for k_, r_ in sv_w.items()}
            _r4 = series.all_day_markets(BS, NOW)[2]
            # v-tg-active (2026-10-30): the stopped weather bot is drawn and named as 'Earlier bots', never by name
            _wx = sum(v for _d, _t, v, b_ in _r4 if b_ == "earlier")
            got = build("stats", ctx3)
            n_with = px_count(got[0], BOT_COLOUR["earlier"]) if is_png(got) else 0
            c["subs"]["3"]["rows"] = {}
            got0 = build("stats", ctx3)
            n_without = px_count(got0[0], BOT_COLOUR["earlier"]) if is_png(got0) else -1
        finally:
            c["subs"]["3"]["rows"] = sv_w
        ck(is_png(got) and "every bot, every pot" in got[1] and _wx < 0
           and all(v < 0 for _d, _t, v, b_ in _r4 if b_ == "earlier") and not any(b_ == "weather" for *_x, b_ in _r4)
           and ("Earlier bots %s" % usd(_wx)) in got[1] and "Weather" not in got[1]
           and all(BOT_SHORT[b_] in got[1] for b_ in ("pin", "race", "forecaster", "ladder", "fx"))
           and n_with > 400 and 0 <= n_without < 30,
           "/stats (10-26): every bot, every pot, one colour a bot; the stopped weather bot with ONLY losses (%s) "
           "draws as 'Earlier bots' (%d px of that colour; %d with no market), never by its name (v-tg-active): %r"
           % (usd(_wx), n_with, n_without, got[1][:90] if got else None))
        ck(is_png(got0) and "Weather" not in got0[1] and "Earlier bots" not in got0[1],
           "/stats: a bot with no market at all is neither drawn nor named")


def test_thirty_day_lines_on_botstats_pictures():
    # the 30-day lines on the botstats pictures: drawn where the record has more days than the 7-day line
    # averages (the planted pin bot: ~14 days), not drawn for a bot younger than that (the FX taker: ~1 day)
    with planted_botstats(fx=True) as (BS, c, _procs, _td, ctx3):
        _pc_pin = series.pace_curves(BS, BS.pot_context(c, et_day(NOW)), "0",
                                     sorted((m_ for m_ in BS._money_block(c, "pin", et_day(NOW))["markets"]), key=lambda m_: m_["t"]),
                                     et_day(NOW), NOW)
        _ms_fx = sorted(BS._money_block(c, "fx", et_day(NOW))["markets"], key=lambda m_: m_["t"])
        _pc_fx = series.pace_curves(BS, BS.pot_context(c, et_day(NOW)), ("5", "4"), _ms_fx, et_day(NOW), NOW)
        _gp, _gf = build("bot:pin", ctx3), build("bot:fx", ctx3)
        # the planted main-account tickers all name Oct 18, so every pin and race market would close that one ET
        # day: dated by when each settled instead, they spread over ~14 days for /losses and /stats
        _sv0 = c["subs"]["0"]["rows"]
        try:
            c["subs"]["0"]["rows"] = {k_: dict(r_, ticker=r_["ticker"].replace("26OCT18", time.strftime(
                "%y%b%d", time.gmtime(BS._epoch(r_["settled_time"]) + pindesk.et_offset(BS._epoch(r_["settled_time"])))).upper(), 1))
                for k_, r_ in _sv0.items()}
            _gl, _gs = build("losses", ctx3), build("stats", ctx3)
        finally:
            c["subs"]["0"]["rows"] = _sv0
        ck(_pc_pin["avg30"] and _pc_pin["n30"] > _pc_pin["n7"] == series.PACE_DAYS and _pc_fx["avg30"] is None
           and px_count(_gp[0], AVG30) > 300 and px_count(_gf[0], AVG30) < 30 and px_count(_gl[0], AVG30) > 300
           and px_count(_gs[0], AVG30) > 300 and "30 days" in _gp[1] and "average week" in _gl[1],
           "30-day lines (10-29): the pin bot's pace panel (%d days against the 7), /losses (an average week of the "
           "last 30 days) and /stats draw one; the young FX taker's pace panel does not (it has no more days than "
           "the 7-day line): %d / %d / %d / %d px" % (_pc_pin["n30"], px_count(_gp[0], AVG30), px_count(_gf[0], AVG30),
                                                     px_count(_gl[0], AVG30), px_count(_gs[0], AVG30)))


def test_stopped_bots_jumpband_and_the_paused_race():
    with planted_botstats(fx=True) as (BS, c, procs, td, ctx3):
        ck(build("bot:weather", ctx3) is None, "/weather: its stop file is set -> no picture of a stopped bot")
        procs.pop(3)
        ck(build("bot:ladder", ctx3) is None, "/ladder: not in the process table -> no picture")
        # v-tg-active (2026-10-30): the jump band (subaccount 3's coin markets) runs live, beside its paper arm; the coin
        # race RUNS with its stop file set -> no picture of its own, its markets drawn and counted as 'Earlier bots'
        for k in range(8):
            tk = "KXBNB15M-26OCT18%04d-45" % k
            c["subs"]["3"]["rows"]["%s|jb" % tk] = {
                "ticker": tk, "settled_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - k * 3000)),
                "market_result": "no" if k != 2 else "yes", "yes_count_fp": "0.00", "no_count_fp": "5.00",
                "yes_total_cost_dollars": "0.00", "no_total_cost_dollars": "4.40", "fee_cost": "0.04",
                "revenue": 0, "value": 0 if k != 2 else 100}
        procs += [(6, "x", "python research/cleanroom/jumpband_live.py --live --subaccount 3 --max-contracts 5"),
                  (7, "x", "python research/cleanroom/jumpband_live.py --minutes 20160")]
        open(os.path.join(td, BS.SPEC["race"]["stop"]), "w", encoding="utf-8").close()
        _jb = build("bot:jumpband", ctx3)
        _bl, _lr, _lp, _lm = series.all_losses(BS, NOW)
        _st = build("stats", ctx3)
        ck(kind_of("/jb") == kind_of("/jumpband") == "bot:jumpband" and is_png(_jb) and "Jump band" in _jb[1]
           and build("bot:race", ctx3) is None and "race" not in _lp and "earlier" in _lp
           and "jumpband" in _lp and not any(r["bot"] in ("race", "weather") for r in _lr)
           and is_png(_st) and "Coin race" not in _st[1] and "Earlier bots" in _st[1] and "Jump band" in _st[1],
           "v-tg-active: /jb draws the jump band (its own colour); the paused race gets no picture, and on /losses and "
           "/stats its markets (and the stopped weather bot's) are 'Earlier bots', never named: %r" % (_st[1][:200] if _st else None))
        os.remove(os.path.join(td, BS.SPEC["race"]["stop"]))
        ck(is_png(build("bot:race", ctx3)) and "race" in series.all_losses(BS, NOW)[2],
           "v-tg-active: the race's stop file removed -> its picture and its own /losses row are back")


TESTS = [test_funds_and_the_fx_taker, test_losses_bot_pages_today, test_stats_one_colour_a_bot,
         test_thirty_day_lines_on_botstats_pictures, test_stopped_bots_jumpband_and_the_paused_race]
