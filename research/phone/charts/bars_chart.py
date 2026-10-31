"""bars_chart.py -- /bars: each RUNNING test's numbers against its pre-registered bar (one strip a criterion).

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py (_crit, bars_tests, chart_bars). Not named bars.py:
research/bars.py is the module this picture reads (DESIGN 2: module names avoid open, bars, brief, help).
"""
from phone.charts.base import (DOWN, DOWN_T, INK, INK2, SURF, UP, UP_T, fig_new, headline, no_axis, png, value_axis)


def crit(name, value, unit, lines, good, bad, show=None):
    """One strip: `value` against threshold `lines` [(x, words)]; `good`/`bad` = (lo, hi) zones (None = open)."""
    return {"name": name, "value": value, "unit": unit, "lines": lines, "good": good, "bad": bad, "show": show}


def bars_tests(d, B):
    """[(title, [criteria])] for every test still RUNNING (verdict TOO EARLY / EXTEND, its arm not stopped),
    and the words for the ones not drawn."""
    tests, other = [], []
    f = d.get("fresh")
    if f:
        if f.get("verdict") in ("TOO EARLY", "EXTEND") and f.get("arm_running"):
            extra = len((f.get("h2h") or {}).get("arm_extra_losers") or [])
            tests.append(("Fresh-offer test (%s) · day %.1f of %d · %s" % (f["arm"], f["days"], f["window_days"], f["verdict"]), [
                crit("Money made by live's fresh fills", f["net"], "$",
                     [(B.FRESH_DEPLOY_NET, "deploy at or under"), (B.FRESH_KILL_NET, "kill at or over")],
                     (None, B.FRESH_DEPLOY_NET), (B.FRESH_KILL_NET, None)),
                crit("Fresh fills that lost", f["losers"], "",
                     [(B.FRESH_DEPLOY_LOSERS, "deploy needs at least")], (B.FRESH_DEPLOY_LOSERS, None), None),
                crit("Losers only the arm had", extra, "", [(0, "deploy needs")], (None, 0.5), (0.5, None)),
                crit("Days into the window", f["days"], "d", [(f["window_days"], "window")], None, None)]))
        else:
            other.append("fresh-offer test: %s" % f.get("verdict"))
    b = d.get("btcd")
    if b:
        p = b.get("paper")
        if p and b.get("verdict") == "TOO EARLY":
            tests.append(("Hourly BTC paper (%s) · day %.1f of %d · %s" % (b["paper_arm"], b["paper_days"], b["window_days"], b["verdict"]), [
                crit("Fired closes", p["fired"], "", [(B.BTCD_BAR_FIRED, "needs")], (B.BTCD_BAR_FIRED, None), None),
                crit("Contracts captured", p["contracts"], "", [(B.BTCD_BAR_CONTRACTS, "needs")], (B.BTCD_BAR_CONTRACTS, None), None),
                crit("Losses inside 30 s", p["lost_le30"], "", [(0, "allowed")], (None, 0.5), (0.5, None)),
                crit("Days into the window", b["paper_days"], "d", [(b["window_days"], "window")], None, None)]))
        else:
            other.append("hourly BTC paper: %s" % b.get("verdict"))
    r = d.get("race") or {}
    z = r.get("z3")
    if z:
        if z.get("log") and z.get("verdict") == "TOO EARLY" and not z.get("ran"):
            tests.append(("z3 race arm (paper) · %s" % z["verdict"], [
                crit("Races entered", z["races"], "", [(B.Z3_PASS[0], "pass at")], (B.Z3_PASS[0], None), None),
                crit("Losses (a tie is a loss)", z["losses"], "", [(B.Z3_PASS[1], "at most")], (None, B.Z3_PASS[1] + 0.5),
                     (B.Z3_PASS[1] + 0.5, None)),
                crit("Losses in the first 50", z["first50_losses"], "", [(B.Z3_KILL[0], "kill at")], (None, B.Z3_KILL[0] - 0.5),
                     (B.Z3_KILL[0] - 0.5, None))]))
        else:
            other.append("z3: %s" % (z.get("ran") or z.get("verdict")))
    if r.get("gap075_ran"):
        other.append("gap075: %s" % r["gap075_ran"])
    if d.get("controls"):
        other.append("%d control arms (no bar)" % len(d["controls"]))
    return tests, other


def chart_bars(ctx):
    d = ctx.bars
    if not d:
        return None
    import bars as B
    tests, other = bars_tests(d, B)
    if not tests:
        return None
    rows = []
    for title, crits in tests:
        for i, c in enumerate(crits):
            rows.append((title if i == 0 else None, c))
    fig, axs = fig_new(len(rows), 1.05 * len(rows) + 0.9 + 0.35 * len(tests))
    for ax, (title, c) in zip(axs, rows):
        v = float(c["value"])
        xs = [v] + [x for x, _w in c["lines"]]
        # the strip's scale: the value, its bar lines and 0, through the engine (nice ticks, the unit's own labels)
        lim = value_axis(ax, xs + [0.0], unit="$" if c["unit"] == "$" else "", kind="level", axis="x",
                         integer=c["unit"] == "", signed=c["unit"] == "$")
        lo, hi = lim["lo"], lim["hi"]
        no_axis(ax, "y", 0, 1)
        for zone, col in ((c["good"], UP_T), (c["bad"], DOWN_T)):
            if zone:
                a = lo if zone[0] is None else zone[0]
                z = hi if zone[1] is None else zone[1]
                ax.axvspan(a, z, color=col, zorder=0, lw=0)
        for x, _w in c["lines"]:
            ax.axvline(x, color=INK2, lw=1.4, zorder=2)
        good = c["good"] and (c["good"][0] is None or v >= c["good"][0]) and (c["good"][1] is None or v <= c["good"][1])
        badz = c["bad"] and (c["bad"][0] is None or v >= c["bad"][0]) and (c["bad"][1] is None or v <= c["bad"][1])
        col = UP if good else (DOWN if badz else INK)
        ax.scatter([v], [0.5], marker="D", s=70, color=col, edgecolor=SURF, linewidth=1.5, zorder=4)
        vs = ("%s$%.2f" % ("-" if v < 0 else "+", abs(v))) if c["unit"] == "$" else (("%.1f" % v) if c["unit"] == "d" else "%g" % v)
        bar_w = "; ".join("%s %s" % (w, (("%s$%g" % ("-" if x < 0 else "+", abs(x))) if c["unit"] == "$" else "%g" % x))
                          for x, w in c["lines"])
        ax.set_title("%s: %s  (%s)" % (c["name"], vs, bar_w), fontsize=10, color=INK)
        ax.grid(False)
        if title:
            ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(0, 22), textcoords="offset points",
                        fontsize=11.5, fontweight="bold", color=INK2, va="bottom", annotation_clip=False)
    headline(fig, "Running tests against their bars")
    cap = ("Each running test's numbers (research/bars.py, the /bars words) against the bar written before its data: "
           "green zone = where the bar passes, red = where it kills, the diamond = now.%s" % (
               (" Not drawn: " + "; ".join(other) + ".") if other else ""))
    return png(fig), cap
