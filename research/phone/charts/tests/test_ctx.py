"""test_ctx.py -- ChartCtx: a picture drawn from an explicit ChartCtx is the picture drawn from the old dict with "pp"
(pinphone's Phone._chart_ctx today), and a broken provider fails the way a broken pp did.

v-tg-rebuild step 8 (2026-10-30), new.
"""
from botdata import series
from phone.charts import ChartCtx, as_ctx, build
from phone.charts.ctx import phone_markets
from phone.charts.tests.planted import (FUNDS_WHAT, NOW, NoBS, ck, is_png, kalshi_ledger_file, planted_botstats,
                                        planted_ledger, same_picture)


def pinphone_ctx(PP, ledger=None, active=None, bars=None):
    """The ChartCtx pinphone would build (the follow-up for Phone._chart_ctx), from the pinphone module's own names."""
    return ChartCtx(now=NOW, ledger=ledger, bs_getter=None, bs_procs=None, funds_what=FUNDS_WHAT, active=active,
                    bars=bars, botstats=PP._bs, markets=lambda led: phone_markets(PP, led),
                    window_stats=PP.window_stats, first_live_day=PP.FIRST_LIVE_DAY, main_words=PP.main_words)


def test_adapter_reads_pp_lazily():
    seen = []

    class PP:
        FIRST_LIVE_DAY = "2026-09-08"

        def __getattr__(self, k):
            seen.append(k)
            raise AttributeError(k)
    c = as_ctx({"now": NOW, "pp": PP(), "ledger": None, "funds_what": {1: "x"}, "active": ("pin",)})
    ck(isinstance(c, ChartCtx) and c.now == NOW and c.funds_what == {1: "x"} and c.active == ("pin",)
       and c.first_live_day == "2026-09-08" and c.main_words is None and seen == ["main_words"] and as_ctx(c) is c,
       "as_ctx: the old dict becomes a ChartCtx; pp is only asked whether it has main_words (nothing else is read "
       "until a picture asks); a ChartCtx passes through: %r" % seen)
    try:
        c.bs()
        ok = False
    except AttributeError:
        ok = True
    nopp = as_ctx({"now": NOW})
    try:
        nopp.bs()
        ok2 = False
    except KeyError:
        ok2 = True
    ck(ok and ok2 and nopp.words_main() == "pin bot + coin race",
       "a pp with no _bs fails at the picture's own botstats read (AttributeError), a dict with no pp the way "
       "ctx['pp'] did (KeyError) -- inside the pictures' try, so they fall back exactly as before")


def test_chartctx_draws_the_same_pictures():
    with planted_botstats(fx=True) as (BS, _c, _procs, _td, ctx3):
        import pinphone as PP
        led = planted_ledger()
        old = dict(ctx3, ledger=led, active=("pin", "ladder", "forecaster", "fx"))
        new = pinphone_ctx(PP, ledger=led, active=old["active"])
        for kind in ("today", "days", "stats", "funds", "losses", "bot:pin", "bot:race", "status"):
            a, b = build(kind, old), build(kind, new)
            ck(is_png(a) and is_png(b) and a[1] == b[1] and same_picture(a[0], b[0]),
               "%s: the ChartCtx picture = the old dict's (caption and pixels)" % kind)
        ck(series.all_losses(*new.bs_args())[1] == series.all_losses(BS, NOW)[1]
           and series.all_day_markets(*new.bs_args())[2] == series.all_day_markets(BS, NOW)[2],
           "botdata.series from a ChartCtx = from botstats itself")
        ck("pin bot)" in build("status", new)[1] and "pin bot + coin race" in build("status", old | {"active": None})[1],
           "main_words through the ChartCtx: 'pin bot' when the race is not active, 'pin bot + coin race' when unknown")


def test_chartctx_fallbacks():
    led = planted_ledger()
    with kalshi_ledger_file(led) as PP:
        def broken():
            raise RuntimeError("botstats cannot be read (planted)")
        new = ChartCtx(now=NOW, ledger=led, botstats=broken, markets=lambda l_: phone_markets(PP, l_),
                       window_stats=PP.window_stats, first_live_day=PP.FIRST_LIVE_DAY, main_words=PP.main_words)
        old = {"now": NOW, "ledger": led, "pp": NoBS(PP)}
        for kind in ("stats", "hedges", "today", "losses"):
            a, b = build(kind, old), build(kind, new)
            ck(is_png(a) and is_png(b) and a[1] == b[1] and same_picture(a[0], b[0])
               and (kind not in ("stats", "today") or "main account" in b[1]),
               "%s with botstats unreadable: the ChartCtx draws the main account's picture, as the old dict did" % kind)
    bare = ChartCtx(now=NOW, ledger=led, botstats=broken)
    try:
        build("hedges", bare)
        ok = False
    except RuntimeError as e:
        ok = "markets" in str(e)
    ck(ok, "/hedges with no markets provider: a clear error naming ChartCtx.markets (pinphone always gives one)")
    ck(build("bars", ChartCtx(now=NOW)) is None and build("nosuchkind", {"now": NOW}) is None,
       "no /bars numbers -> no picture; an unknown kind -> None")


TESTS = [test_adapter_reads_pp_lazily, test_chartctx_draws_the_same_pictures, test_chartctx_fallbacks]
