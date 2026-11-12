"""test_share.py -- /share_today /share_days /share_funds: drawn from planted botstats, and the leak check refuses every
kind of give-away it guards against (v-tg-share, 2026-11-12)."""
from phone.charts import build, kind_of, share
from phone.charts.base import fig_new, money_axis
from phone.charts.tests.planted import ck, is_png, planted_botstats

LEAKY = ("Nov 11", "november", "Tuesday", "11/12", "2026-11-12", "2026", "3:15", "6 PM", "midnight ET", "Kalshi",
         "Subaccount 3", "Main account", "the pots", "BTC", "crypto", "a coin", "losing market", "the hedge", "bets",
         "97c", "15-min", "Pin bot", "pin", "Coin race", "ladder", "Weather", "wx", "FX taker", "fx", "jb", "Jump band",
         "currencies", "commodities", "earlier bots")
SAFE = ("Today: made +$20.24 (+0.60% of the account)", "Last 30 days: made +$1,439.62 (+75.1%) · 23 of 30 days up",
        "Account $3,347 · made +$1,500.00 in 30 days (+81.2%)", "hours into the day", "day", "days", "+$2,000",
        "Average day, last 7 (+$48.10)", "Money made each day", share.CAPTION)


def test_the_leak_check():
    for t in LEAKY:
        ck(share.leaks([t]), "share.leaks catches %r" % t)
    found = share.leaks(SAFE)
    ck(not found, "share.leaks passes the share pictures' own words: %s" % found)


def test_a_leaky_picture_is_not_sent():
    fig, (ax,) = fig_new(1, 4.0)
    ax.plot([0, 1], [0, 5])
    money_axis(ax, [0, 5])
    ax.set_title("Money made on Nov 11")
    ck(share.finish(fig, "test") is None, "a picture with a date on it is not sent")
    fig, (ax,) = fig_new(1, 4.0)
    ax.plot([0, 1], [0, 5])
    money_axis(ax, [0, 5])
    ax.set_title("Money made")
    ck(share.finish(fig, "test", caption="every pin bot market") is None, "a leaky caption stops the picture too")


def test_share_pictures_from_botstats():
    ck(kind_of("/share_today") == "share_today" and kind_of("/share_yesterday") == "share_yesterday"
       and kind_of("/share_days") == "share_days" and kind_of("/share_funds") == kind_of("/share_bots") == "share_funds"
       and kind_of("/share") is None, "the share commands' picture kinds")
    with planted_botstats(fx=False) as (_BS, _c, _procs, _td, ctx3):
        for kind in ("share_today", "share_yesterday", "share_days", "share_funds"):
            got = build(kind, ctx3)
            ck(is_png(got) and got[1] == share.CAPTION, "%s: a PNG with the safe caption (%r)"
               % (kind, got[1] if got else None))
            orig = build(kind[6:], ctx3)
            ck(is_png(orig) and orig[1] != share.CAPTION, "%s: the original still draws as before" % kind[6:])


def test_hourly_hides_each_market():
    pts = [(600, 1.0), (1500, 3.0), (4000, 2.5), (4100, 6.0)]
    ck(share.hourly(pts, 7200) == [(0, 0.0), (3600, 3.0), (7200, 6.0)],
       "hourly: the running total on each full hour, never at a market's own minute: %r" % share.hourly(pts, 7200))
    ck(share.hourly(pts, 5000) == [(0, 0.0), (3600, 3.0), (5000, 6.0)],
       "hourly: money after the last full hour lands at the end: %r" % share.hourly(pts, 5000))


TESTS = (test_the_leak_check, test_a_leaky_picture_is_not_sent, test_share_pictures_from_botstats,
         test_hourly_hides_each_market)
