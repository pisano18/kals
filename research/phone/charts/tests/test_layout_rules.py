"""test_layout_rules.py -- the layout engine (phone/charts/base.py) and the rules every phone picture keeps.

2026-10-30 (the operator: "ladder chart is 0-800, it counts by twos and starts somewhere a little under 800 ... Make it a
fix that applies to this chart and any future ones"). The rules (base.audit, run on every picture every chart test
draws -- run.py turns base.AUDIT on around each test):
  * no offset ('+7.9e2') or scientific tick text, ever
  * every axis that carries numbers went through the engine (value_axis / money_axis / pct_axis, time_axis /
    clock_axis, category_axis, no_axis)
  * TICKS_MIN..TICKS_MAX labelled ticks on a value axis
  * the data (and its reference lines) fill at least MIN_FILL of each value axis and each time axis (room a chart
    declares for a key or names is not counted against it)
  * no two tick labels overlap; the PNG is under PNG_LIMIT bytes
plus, here: the engine on edge data (a flat line, one point, a huge spike, a tiny pot, money lost, one day, millions),
every chart kind drawn from planted data, and a source scan: a chart module never sets limits, ticks, locators or
formatters itself (only base.py does). The golden fixture's pictures are checked the same way by a replay with
KALS_CHART_STRICT=1 (a broken rule raises in base.png; research/golden/README.md).
"""
import datetime as _dt
import os
import re

from phone.charts import base, build
from phone.charts.base import (BLUE, annotate_change, fig_new, headline, mark_last, money_axis, png, ref, time_axis,
                               usd, value_axis)
from phone.charts.tests.planted import NOW, NoBS, ck, is_png, kalshi_ledger_file, planted_botstats, planted_ledger, \
    planted_pp

CHART_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# what only base.py may do to an axis
FORBIDDEN = re.compile(r"\.set_[xy]lim\(|\.set_[xy]bound\(|set_(major|minor)_(locator|formatter)|\.set_[xy]ticks\("
                       r"|\.set_[xy]ticklabels\(|ticklabel_format|\.axis\(|\.margins\(|Locator\(|Formatter\("
                       r"|\[\"ticker\"\]|\[\"dates\"\]|import matplotlib|from matplotlib")


def _audited(fn):
    """Run fn() with the rules check on; the problems it found."""
    old, base.AUDIT = base.AUDIT, []
    try:
        fn()
        return list(base.AUDIT)
    finally:
        base.AUDIT = old


def test_source_scan():
    bad = []
    for fn in sorted(os.listdir(CHART_DIR)):
        if not fn.endswith(".py") or fn == "base.py":
            continue
        with open(os.path.join(CHART_DIR, fn), encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                code = line.split("  #")[0]
                if FORBIDDEN.search(code):
                    bad.append("%s:%d: %s" % (fn, i, line.strip()))
    ck(not bad, "no chart module sets limits, ticks, locators or formatters itself -- only base.py's engine does "
                "(new charts use base.money_axis / value_axis / time_axis)%s" % (("\n      " + "\n      ".join(bad)) if bad else ""))


def test_nice_steps_and_labels():
    ranges = [(0, 1), (729.5, 825.2), (431, 1365), (49.98, 50.61), (-118, 96), (0, 0.56), (97.4, 100), (1e6, 1.1e6),
              (-0.03, 0.02), (0, 7), (3, 1500), (175.3, 207.9), (0.001, 0.0013)]
    bad = []
    for lo, hi in ranges:
        st = base.nice_step(lo, hi)
        n = base._n_ticks(lo, hi, st)
        if not (base.TICKS_MIN <= n <= base.TICKS_MAX) or not base._is_nice(st):
            bad.append((lo, hi, st, n))
    ck(not bad, "nice_step: a 1 / 2 / 2.5 / 5 x 10^n step and %d-%d ticks on every range: %r"
       % (base.TICKS_MIN, base.TICKS_MAX, bad))
    f = base._fmt_value
    ck(f(1250000.0, "$", 0, False, 0.5) == "$1,250,000" and f(50.5, "$", 1, False, 0.05) == "$50.5"
       and f(-25.0, "$", 0, True, 0.5) == "-$25" and f(0.0, "%", 1, True, 0.05) == "0%" and f(2.5, "%", 1, True, 0.05) == "+2.5%"
       and base._money_decimals(0.1, "$") == 2 and base._money_decimals(2.5, "$") == 1 and base._money_decimals(25, "$") == 0,
       "labels: thousands separators, decimals only when the step needs them (cents under a dollar), signs on money made")
    ck(base.minor_step(20, 3.1) == 5 and base.minor_step(200, 31) == 50 and base.minor_step(25, 3) == 5
       and base.minor_step(50, 30) is None,
       "the unlabelled grid follows the series' typical move: $20 steps for a $3/day bot get $5 lines, $200 steps for a "
       "$31/day bot get $50 lines, none when a move is half a step or more")


def _series(kind):
    t0 = _dt.datetime(2026, 10, 1)
    hours = [t0 + _dt.timedelta(hours=h) for h in range(0, 24 * 20, 6)]
    if kind == "flat":
        return hours, [800.0] * len(hours)
    if kind == "one point":
        return [t0], [50.0]
    if kind == "spike":
        return hours, [800.0 + (4200.0 if i == 30 else 0.0) + i * 0.5 for i in range(len(hours))]
    if kind == "tiny pot":
        return hours, [5.0 + 0.001 * i for i in range(len(hours))]
    if kind == "money lost":
        return hours, [-1.5 * i for i in range(len(hours))]
    if kind == "one day":
        day = [t0 + _dt.timedelta(minutes=15 * k) for k in range(96)]
        return day, [100.0 + (k % 7) * 0.3 for k in range(96)]
    if kind == "millions":
        return hours, [1234567.0 + 1000.0 * i for i in range(len(hours))]
    raise KeyError(kind)


EDGES = ("flat", "one point", "spike", "tiny pot", "money lost", "one day", "millions")


def test_edge_data():
    for kind in EDGES:
        X, Y = _series(kind)
        out = {}

        def draw():
            fig, axs = fig_new(2, 6.0)
            ax = axs[0]                                 # a balance, like /funds
            ax.plot(X, Y, color=BLUE, marker="o" if len(X) < 3 else None)
            money_axis(ax, Y, kind="balance", xs=X, room_top=0.12)
            time_axis(ax, X[0], X[-1])
            mark_last(ax, X[-1], Y[-1], usd(Y[-1], False), color=BLUE)
            annotate_change(ax, X, Y, ends=True)
            ax = axs[1]                                 # money made, like a bot's running total, with a far stop line
            R = [y - Y[0] for y in Y]
            ax.step(X, R, where="post", color=BLUE, marker="o" if len(X) < 3 else None)
            lim = money_axis(ax, R, xs=X, refs=[ref(min(R) - 10 * (max(R) - min(R) + 1), "stop", optional=True)])
            time_axis(ax, X[0], X[-1])
            annotate_change(ax, X, R, base=False, extra=[r["label"] for r in lim["far"]])
            headline(fig, "Edge: %s" % kind)
            labels = [t.get_text() for a in axs for t in a.get_yticklabels()]
            out["png"] = png(fig)
            out["labels"] = labels
        found = _audited(draw)
        ck(not found and 1000 < len(out["png"]) < base.PNG_LIMIT,
           "edge data '%s': drawn inside the rules (%d KB)%s" % (kind, len(out["png"]) // 1024,
                                                                ("\n      " + "\n      ".join(found)) if found else ""))
    X, Y = _series("millions")
    fig, (ax,) = fig_new(1, 3.0)
    ax.plot(X, Y)
    money_axis(ax, Y, kind="balance")
    fig.canvas.draw()
    labs = [t.get_text() for t in ax.get_yticklabels() if t.get_text()]
    fig.clear()
    ck(labs and all(re.fullmatch(r"\$\d{1,3}(,\d{3})+", s) for s in labs) and not ax.yaxis.get_offset_text().get_text(),
       "millions read as '$1,250,000', never an offset or 1e6: %r" % labs)
    X, Y = _series("flat")
    fig, (ax,) = fig_new(1, 3.0)
    ax.plot(X, Y)
    money_axis(ax, Y, kind="balance")
    lo, hi = ax.get_ylim()
    fig.clear()
    ck(lo > 700 and hi - lo < 50, "a flat $800 line stays a flat line near $800, not a $0 axis or a magnified wiggle "
                                  "(%.2f .. %.2f)" % (lo, hi))


def test_balance_zoom_and_pnl_zero():
    fig, (a1, a2, a3) = fig_new(3, 6.0)
    money_axis(a1, [729.56, 760.0, 825.16], kind="balance")
    money_axis(a2, [12.0, 95.6], kind="pnl")
    value_axis(a3, [98.0, 100.0, 97.9], unit="%", kind="level", floor=0, cap=100)
    l1, l2, l3 = a1.get_ylim(), a2.get_ylim(), a3.get_ylim()
    fig.clear()
    ck(700 < l1[0] < 729.56 and 825.16 < l1[1] < 860, "a balance zooms to its own money ($729.56 .. $825.16 -> %.0f .. "
                                                       "%.0f), never from $0" % l1)
    ck(l2[0] <= 0 < l2[1], "money made always shows its $0 line (%.1f .. %.1f)" % l2)
    ck(97 < l3[0] < 97.9 and 100 <= l3[1] < 100.5, "a win rate zooms to 97.9 .. 100%% and never runs far past 100%% "
                                                  "(%.2f .. %.2f)" % l3)


def test_the_check_catches_the_old_pictures():
    """The 10-30 complaint, drawn the old way, must FAIL the rules check: the ladder's $730 -> $825 on a $0..$850 axis
    with matplotlib's own ticks (an offset), and the same line forced to $0 after the engine set it."""
    T = base.mpl()["ticker"]
    X, _Y = _series("flat")
    Y = [729.56 + 95.6 * i / (len(X) - 1) for i in range(len(X))]

    def old_way():
        fig, (ax,) = fig_new(1, 3.0)
        ax.plot(X, Y)
        ax.set_ylim(799.2001, 799.2009)
        ax.yaxis.set_major_formatter(T.ScalarFormatter(useOffset=True))
        png(fig)

    def forced_zero():
        fig, (ax,) = fig_new(1, 3.0)
        ax.plot(X, Y)
        money_axis(ax, Y, kind="balance")
        time_axis(ax, X[0], X[-1])
        ax.set_ylim(0, 850)
        png(fig)
    a, b = _audited(old_way), _audited(forced_zero)
    ck(any("engine" in p for p in a) and any("offset" in p for p in a) and any("fill" in p for p in b),
       "the rules check catches an axis drawn outside the engine, an offset tick label and a $0-based balance: %r"
       % (a + b))


def test_every_kind_keeps_the_rules():
    kinds_bs = ("funds", "stats", "days", "today", "yesterday", "losses", "bot:pin", "bot:ladder", "bot:fx", "bot:race",
                "bot:forecaster")
    drawn = []

    def draw():
        with planted_botstats(fx=True) as (_BS, _c, _procs, _td, ctx3):
            for k in kinds_bs:
                got = build(k, ctx3)
                if got is not None:
                    drawn.append(k)
                    ck(is_png(got) and len(got[0]) < base.PNG_LIMIT, "%s: a PNG under %d KB" % (k, base.PNG_LIMIT // 1000))
        led = planted_ledger()
        ctx = {"now": NOW, "ledger": led, "pp": planted_pp()}
        for k in ("status", "fills", "market"):
            got = build(k, ctx)
            if got is not None:
                drawn.append(k)
        with kalshi_ledger_file(led) as PP:
            got = build("hedges", {"now": NOW, "ledger": led, "pp": NoBS(PP)})
            if got is not None:
                drawn.append("hedges")
    found = _audited(draw)
    ck(not found and len(drawn) >= 14, "every chart kind (%s) keeps the layout rules%s"
       % (", ".join(drawn), ("\n      " + "\n      ".join(found)) if found else ""))


TESTS = [test_source_scan, test_nice_steps_and_labels, test_edge_data, test_balance_zoom_and_pnl_zero,
         test_the_check_catches_the_old_pictures, test_every_kind_keeps_the_rules]
