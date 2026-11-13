"""test_share.py -- /share_today /share_days /share_funds: drawn from planted botstats, and the leak check refuses every
kind of give-away it guards against (v-tg-share, 2026-11-12)."""
from botdata import series
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


def test_brag_timeline_shuffled_in_stretches():
    import random
    from phone.charts.ctx import as_ctx
    ck(kind_of("/share_brag") == "share_brag", "brag kind")
    ck(share.brag_pct(0.8099) == 80 and share.brag_pct(0.81) == 81 and share.brag_pct(-0.023) == -3,
       "brag_pct rounds DOWN: never more than was made")
    gen = random.Random(7)
    book = []
    for i in range(60):                                 # a deposit of 500 on day 12 spilling 20 into day 13, a 3 fee
        moved = 500.0 if i == 11 else (20.0 if i == 12 else (-3.0 if i == 30 else 0.0))
        book.append((round(gen.uniform(-60, 120), 2), 1000.0 + 20 * i, moved))
    start = 900.0
    real_path, _m = share.bankroll_path(book, list(range(60)), start)
    for seed in range(40):
        rng = random.Random(seed)
        st = share.stretches(book, random.Random(seed))
        ck(st[0][0] == 0 and st[-1][1] == 59 and all(b + 1 == c for (_a, b), (c, _d) in zip(st, st[1:])),
           "stretches cover every day once, in sequence: %r" % st)
        ck(any(b == 11 for _a, b in st), "the deposit's first day ends a stretch: %r" % st)
        ck(all(b - a + 1 <= 19 for a, b in st), "no stretch longer than 19 days: %r" % st)
        order = share.shuffle_book(book, rng)
        ck(sorted(order) == list(range(60)) and all(a <= order[i] <= b for a, b in st for i in range(a, b + 1)),
           "every day stays inside its own stretch")
        path, _m = share.bankroll_path(book, order, start)
        ck(all(abs(path[b + 1] - real_path[b + 1]) < 1e-6 for _a, b in st),
           "the bankroll is exactly real at every stretch's end (seed %d)" % seed)
        ck(abs(path[-1] - (start + sum(m for m, _p, _f in book) + 517.0)) < 1e-6, "and ends at the real bankroll")
    with planted_botstats(fx=False) as (_BS, _c, _procs, _td, ctx3):    # its record: 3 whole days before today
        ctx = as_ctx(ctx3)
        got = share.window_book(ctx, 3)
        ck(got is not None and len(got[0]) == 3, "window_book: the last 3 whole days")
        bk, end = got
        ck(abs(bk[0][1] + sum(m + f for m, _p, f in bk) - end) < 1e-6,
           "window_book: made + moved add up to the next morning's bankroll, ending at today's")
        ck(share.window_book(ctx, 4) is None and build("share_brag", ctx3) is None,
           "a window longer than the record: no picture")
        got = share.chart_brag(ctx, 3, rng=random.Random(1))
        ck(is_png(got) and got[1] == share.CAPTION, "chart_brag: a PNG with the safe caption (leak check passed)")


TESTS = (test_the_leak_check, test_a_leaky_picture_is_not_sent, test_share_pictures_from_botstats,
         test_hourly_hides_each_market, test_brag_timeline_shuffled_in_stretches)
