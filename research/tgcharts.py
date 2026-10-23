#!/usr/bin/env python3
r"""tgcharts.py -- the phone's pictures: real x-y charts, sent right after a command's words.

THE OPERATOR, 2026-10-18: "Telegram still looks very bad, do actual x y charts and that solution should
work for most commands. For the others figure something out."

WHAT EACH COMMAND GETS (one PNG, sent by pinphone with sendPhoto after the text):
  /today /yesterday        the day's running total close by close on the ET clock (losing closes marked;
                           /today has yesterday beside it in grey); right axis = the same dollars as % of
                           the bank at the start of the day
  /days /brief /summary    every ET day: $ bars, % of the bank bars, the running total ($ and % of money put in)
  /stats                   the same from /stats' own source (Kalshi's books since the first live day), plus
                           each day's won % of markets against its break-even
  /bots /funds /bank /accounts   every RUNNING account's money over time (cash + open bets at cost), a panel each
  /pin /fc /ladder /weather /race /racestats   that bot's running total and its win rate over its last
                           50 markets (races for /race) against break-even
  /losses                  every losing close: dollars, and % of the bank at that moment
  /hedges                  what the insurance legs made, running total; each hedged bet's net by verdict
  /status                  the bank over the last 7 days, hour by hour (pindesk's bank_at)
  /fills /bets             today's orders: price by time, filled vs filled nothing
  /market                  sellers' share of looks over the last 48 quarter-hours against the record's quartiles
  /bars                    each RUNNING test's numbers against its pre-registered bar (one strip a criterion)
  no picture: /open (one short table already), /help, /pair, /pause /start /stop, /mute /unmute.

RULES
  * Every figure is computed by the function the command's words use (pindesk.Ledger, botstats,
    pinphone.markets_from / races_from / window_stats, bars.gather) -- nothing recomputed a second way.
  * Live only: data is read at the request -- a copy of the ledger taken right after the words were built,
    botstats re-read at most once a minute exactly as the words are -- and pinphone drops a picture whose
    turn comes more than STALE_S late. A STOPPED bot, account or test is never drawn; it is named in the
    caption instead.
  * Off the poll loop: pinphone draws on one background thread; alerts, PAUSE and STOP never wait.
  * One measure per axis. A right-hand axis is only ever the SAME numbers in other units (dollars as a %
    of one fixed base), never a second measure.
  * matplotlib (Agg, no pyplot, no window) is imported on first use. Missing -> pinphone sends words only.

    python research/tgcharts.py --selftest      # every chart drawn from planted data, no file or network read
"""
import bisect
import datetime as _dt
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pindesk                                                       # noqa: E402
from pindesk import Ledger, et_day, et_day_start                     # noqa: E402

W_IN, DPI = 7.2, 150                    # 1080 px wide: a phone screen's width, no scaling by Telegram
MAX_BYTES = 2_000_000                   # Telegram allows 10 MB a photo; a chart over 2 MB is a bug
STALE_S = 120                           # a picture whose turn comes later than this is dropped, not sent
ROLL = 50                               # win rate over the last ROLL markets (races)
WINDOW_DAYS = 45                        # day-by-day pictures show this many days (their totals count all)

# colours (the dataviz reference palette, light surface)
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#b4b2a9"
UP, DOWN = "#0ca30c", "#d03b3b"
UP_T, DOWN_T, MID_T = "#d7efd7", "#f6d9d9", "#efeee9"

# command -> picture. Words-only commands are simply absent.
CMD_KIND = {"/status": "status", "/s": "status", "/today": "today", "/yesterday": "yesterday",
            "/days": "days", "/brief": "days", "/summary": "days", "/stats": "stats",
            "/bots": "funds", "/funds": "funds", "/bank": "funds", "/accounts": "funds",
            "/pin": "bot:pin", "/forecaster": "bot:forecaster", "/fc": "bot:forecaster",
            "/ladder": "bot:ladder", "/weather": "bot:weather", "/wx": "bot:weather",
            "/race": "bot:race", "/racestats": "bot:race",
            "/losses": "losses", "/hedges": "hedges", "/fills": "fills", "/bets": "fills",
            "/market": "market", "/bars": "bars"}
LEDGER_KINDS = frozenset(["status", "today", "yesterday", "days", "stats", "losses", "hedges", "fills", "market"])
ACCOUNT_NAME = {"0": "Main account", "1": "Subaccount 1", "2": "Subaccount 2", "3": "Subaccount 3"}


def kind_of(cmd):
    return CMD_KIND.get(cmd)


# ---- matplotlib, on first use ------------------------------------------------------------------------
_M = {}


def mpl():
    if not _M:
        import matplotlib
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        import matplotlib.dates as mdates
        import matplotlib.ticker as mticker
        matplotlib.rcParams.update({
            "font.size": 10.5, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.facecolor": SURF,
            "figure.facecolor": SURF, "savefig.facecolor": SURF, "xtick.color": AXIS, "ytick.color": AXIS,
            "xtick.labelcolor": INK2, "ytick.labelcolor": INK2, "xtick.labelsize": 10, "ytick.labelsize": 10,
            "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
            "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.titlesize": 11.5,
            "axes.titlelocation": "left", "axes.titlecolor": INK2, "axes.titlepad": 6, "lines.linewidth": 2.0,
            "ytick.major.size": 0, "xtick.major.size": 3, "legend.frameon": False, "legend.fontsize": 9.5,
            "text.parse_math": False})               # "$" is money here, never TeX
        _M.update(Figure=Figure, Canvas=FigureCanvasAgg, dates=mdates, ticker=mticker,
                  version=matplotlib.__version__)
    return _M


def fig_new(n, h, ratios=None, sharex=False):
    M = mpl()
    fig = M["Figure"](figsize=(W_IN, h), dpi=DPI, layout="constrained")
    M["Canvas"](fig)
    axs = fig.subplots(n, 1, sharex=sharex, squeeze=False,
                       gridspec_kw={"height_ratios": ratios} if ratios else None)[:, 0]
    return fig, list(axs)


def png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI)
    fig.clear()
    return buf.getvalue()


def headline(fig, text):
    """The number that matters, bold, top left; smaller type for a long one so it never runs off a phone."""
    fig.suptitle(text, x=0.012, ha="left", fontsize=min(14.0, 14.0 * 64 / max(1, len(text))), fontweight="bold",
                 color=INK)


def legend(ax):
    """A legend that finds the emptiest corner and sits on the surface colour, so it never hides a mark."""
    ax.legend(loc="best", frameon=True, facecolor=SURF, edgecolor="none", framealpha=0.92)


# ---- words and numbers (the phone's own money style: sign first, thousands) ---------------------------
def usd(x, signed=True):
    if x is None:
        return "?"
    s = "{:,.2f}".format(abs(x))
    if abs(x) < 0.005:
        return "$0.00"
    return ("-" if x < 0 else ("+" if signed else "")) + "$" + s


def pctx(x, digits=1, signed=True):
    if x is None:
        return "?"
    return ("%+.*f%%" if signed else "%.*f%%") % (digits, 100.0 * x)


def etdt(e):
    """epoch -> a naive datetime on the ET clock (pindesk's offset, so DST is the same as the words')."""
    return _dt.datetime(1970, 1, 1) + _dt.timedelta(seconds=float(e) + pindesk.et_offset(e))


def et_clock(e, fmt="%I:%M %p"):
    return pindesk.et_str(e, fmt)


def money_axis(ax, signed=True, axis="y"):
    T = mpl()["ticker"]

    def f(v, _p=None):
        lo, hi = ax.get_ylim() if axis == "y" else ax.get_xlim()
        span = abs(hi - lo)
        d = 2 if span < 4 else (1 if span < 20 else 0)
        tiny = 0.5 * 10 ** -d
        s = "{:,.{d}f}".format(abs(v), d=d)
        return ("-" if v < -tiny else ("+" if signed and v > tiny else "")) + "$" + s
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(T.FuncFormatter(f))


def pct_ticks(ax, signed=True, axis="y"):
    T = mpl()["ticker"]

    def f(v, _p=None):
        lo, hi = ax.get_ylim() if axis == "y" else ax.get_xlim()
        span = abs(hi - lo)
        d = 2 if span < 0.5 else (1 if span < 5 else 0)
        if abs(v) < 0.5 * 10 ** -d:
            return "0%"
        return ("%+.*f%%" if signed else "%.*f%%") % (d, v)
    a = ax.yaxis if axis == "y" else ax.xaxis
    a.set_major_locator(T.MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))
    a.set_major_formatter(T.FuncFormatter(f))


def pct_of_axis(ax, base, label):
    """The SAME dollars read as % of one fixed base, on the right. Not a second measure."""
    if not base or base <= 0:
        return None
    sec = ax.secondary_yaxis("right", functions=(lambda v: v / base * 100.0, lambda p: p * base / 100.0))
    T = mpl()["ticker"]

    def f(p, _q=None):
        lo, hi = ax.get_ylim()
        span = abs(hi - lo) / base * 100.0
        d = 2 if span < 0.5 else (1 if span < 5 else 0)
        return "0%" if abs(p) < 0.5 * 10 ** -d else "%+.*f%%" % (d, p)
    sec.yaxis.set_major_formatter(T.FuncFormatter(f))
    sec.tick_params(axis="y", length=0, labelsize=9.5, labelcolor=MUTED)
    sec.spines["right"].set_visible(False)
    sec.set_ylabel(label, fontsize=9, color=MUTED)
    return sec


def date_axis(ax, span_days=None):
    D, T = mpl()["dates"], mpl()["ticker"]
    if span_days is not None and span_days <= 1.5:
        ax.xaxis.set_major_locator(D.HourLocator(byhour=range(0, 24, 3)))
        ax.xaxis.set_major_formatter(T.FuncFormatter(
            lambda v, _p: (lambda h: "%d %s" % ((h % 12) or 12, "AM" if h < 12 else "PM"))(D.num2date(v).hour)))
        return
    if span_days is not None and span_days <= 8:
        ax.xaxis.set_major_locator(D.DayLocator())
        ax.xaxis.set_major_formatter(T.FuncFormatter(
            lambda v, _p: (lambda d: d.strftime("%a ") + str(d.day))(D.num2date(v))))
        return
    ax.xaxis.set_major_locator(D.AutoDateLocator(minticks=3, maxticks=6))
    ax.xaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: (lambda d: d.strftime("%b ") + str(d.day))(D.num2date(v))))


def zero_line(ax):
    ax.axhline(0, color=AXIS, lw=1.0, zorder=1)


def note(ax, x, y, text, dx=0, dy=8, ha="center", color=INK, weight="bold", size=9.5):
    ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va="bottom" if dy >= 0 else "top",
                fontsize=size, color=color, fontweight=weight, zorder=6)


def ups_downs(vals):
    return [UP if (v or 0) >= 0 else DOWN for v in vals]


def roll(vals, n):
    """Trailing mean over the last n values (fewer at the start)."""
    out, acc = [], 0.0
    for i, v in enumerate(vals):
        acc += v
        if i >= n:
            acc -= vals[i - n]
        out.append(acc / min(i + 1, n))
    return out


# ---- what the words use -------------------------------------------------------------------------------
def closes_cum(rows):
    """[(close epoch, running total, that close's net)] -- Ledger.by_close, the /today sparkline's source."""
    closes = Ledger.by_close(rows)
    out, cum = [], 0.0
    for k in sorted(c for c in closes if c is not None):
        cum += closes[k]
        out.append((k, cum, closes[k]))
    return out


def ledger_days(led):
    """[(ET day, net)] for every day Ledger.days() lists; net = Ledger.summary(settled_on(day))['net']."""
    by = {}
    for s in led.settled:
        if s["t"]:
            d = et_day(s["close"] or s["t"])
            by[d] = by.get(d, 0.0) + s["pnl"]
    return [(d, by.get(d, 0.0)) for d in led.days()]


def markets_of(ctx):
    """/stats' and /hedges' markets: pinphone.markets_from(raw_ledger) with Phone._sides, on the snapshot."""
    pp, led = ctx["pp"], ctx["ledger"]

    class _S:
        ledger = led
    sides = pp.Phone._sides(_S())
    return pp.markets_from(pp.raw_ledger(os.path.join(led.results, pp.pinday.LEDGER_NAME)), sides)


def bot_stopped(bs, name, prows, ok):
    """True when its stop file is set, or the process table was read and holds no live copy of it."""
    if os.path.exists(os.path.join(bs.RESULTS, bs.SPEC[name]["stop"])):
        return True
    return bool(ok) and not any(bs.is_bot(name, r[2]) for r in (prows or []))


def bs_load(ctx):
    bs = ctx["pp"]._bs()
    c, prows, ok = bs._load(ctx["now"], ctx.get("bs_getter"), ctx.get("bs_procs"))
    return bs, c, prows, ok


# =======================================================================================================
# the charts. Each returns (png bytes, caption) or None when there is nothing live to draw.
# =======================================================================================================
def chart_day(ctx, which):
    led, now = ctx["ledger"], ctx["now"]
    today = et_day(now)
    day = today if which == "today" else et_day(now - 86400)
    rows = led.settled_on(day)
    pts = closes_cum(rows)
    if not pts:
        return None
    s = Ledger.summary(rows)
    d0 = et_day_start(day)
    b0 = led.bank_at(d0)
    fig, (ax,) = fig_new(1, 5.6)
    label = "Today" if day == today else "Yesterday"
    end = min(now, d0 + 86400) if day == today else d0 + 86400
    X = [etdt(d0)] + [etdt(k) for k, _c, _v in pts] + [etdt(max(end, pts[-1][0]))]
    Y = [0.0] + [c for _k, c, _v in pts] + [pts[-1][1]]
    if day == today:
        y = et_day(now - 86400)
        ypts = closes_cum(led.settled_on(y))
        if ypts:
            sh = d0 - et_day_start(y)
            ax.step([etdt(d0)] + [etdt(k + sh) for k, _c, _v in ypts] + [etdt(d0 + 86400)],
                    [0.0] + [c for _k, c, _v in ypts] + [ypts[-1][1]], where="post", color=GREY, lw=1.6,
                    label="Yesterday %s" % usd(ypts[-1][1]), zorder=2)
    ax.step(X, Y, where="post", color=BLUE, lw=2.2, label="%s %s" % (label, usd(s["net"])), zorder=3)
    lost = [(k, c) for k, c, v in pts if v < 0]
    if lost:
        ax.scatter([etdt(k) for k, _c in lost], [c for _k, c in lost], s=46, color=DOWN, edgecolor=SURF,
                   linewidth=1.5, zorder=5, label="a losing close")
    zero_line(ax)
    ax.set_xlim(etdt(d0), etdt(d0 + 86400))
    date_axis(ax, 1)
    money_axis(ax)
    note(ax, X[-1], Y[-1], usd(Y[-1]), dx=-4, ha="right")
    pct_of_axis(ax, b0, "%% of the %s bank at midnight ET" % usd(b0, False) if b0 else "")
    ax.set_title("Running total, close by close (ET)")
    legend(ax)
    r = (s["net"] / b0) if b0 else None
    headline(fig, "%s %s%s · %d of %d closes won" % (label, usd(s["net"]), (" (%s of the bank)" % pctx(r, 2)) if r is not None else "",
                                                   s["won"], s["closes"]))
    cap = ("%s: the day's money close by close, Kalshi's books, main account (pin + coin race). Right axis: the same "
           "dollars as %% of the bank at the start of the ET day." % label)
    return png(fig), cap


def _bars_by_day(ax, days, vals, fmt_last):
    xs = [etdt(et_day_start(d) + 43200) for d in days]
    ax.bar(xs, vals, width=0.78, color=ups_downs(vals), zorder=3)
    zero_line(ax)
    if xs:
        note(ax, xs[-1], vals[-1], fmt_last(vals[-1]), dy=6 if vals[-1] >= 0 else -6)
    return xs


def chart_days(ctx, src):
    led, now = ctx["ledger"], ctx["now"]
    pp = ctx["pp"]
    today = et_day(now)
    winrate = None
    if src == "days":
        rows = ledger_days(led)
        if not rows:
            return None
        s = Ledger.summary(led.settled)
        dep = led.deposited()
        head = "All time %s%s" % (usd(s["net"]), (" (%s on the %s put in)" % (pctx(s["net"] / dep, 2), usd(dep, False))) if dep else "")
        src_words = "Kalshi's books, main account (pin + coin race), every ET day it traded"
    else:
        fl = pp.FIRST_LIVE_DAY
        ms = [m for m in markets_of(ctx).values() if m["day"] >= fl]
        if not ms:
            return None
        life = pp.window_stats(ms, {})
        dep = led.deposited()
        by = {}
        for m in ms:
            by.setdefault(m["day"], []).append(m)
        days, d = [], fl
        while d <= today:
            days.append(d)
            d = pp.day_minus(d, -1)
        rows = [(d, sum(m["pnl"] for m in by.get(d, []))) for d in days]
        winrate = []
        for d in days:
            st = pp.window_stats(by[d], {}) if by.get(d) else None
            winrate.append((d, st["win_c"] if st else None, st["breakeven_c"] if st else None))
        head = "Lifetime %s%s" % (usd(life["net"]), (" (%s on %s risked)" % (pctx(life["net"] / life["risked"], 2),
                                                                         usd(life["risked"], False))) if life["risked"] else "")
        src_words = "Kalshi's books, main account, since %s (the /stats source)" % fl
    cum, runs = 0.0, []
    for _d, v in rows:                                  # the running total counts EVERY day ...
        cum += v
        runs.append(cum)
    cut = et_day(now - WINDOW_DAYS * 86400)             # ... the picture shows the last WINDOW_DAYS of them
    keep = [i for i, (d, _v) in enumerate(rows) if d >= cut] or list(range(len(rows)))
    if winrate is not None:
        winrate = [winrate[i] for i in keep]
    days = [rows[i][0] for i in keep]
    nets = [rows[i][1] for i in keep]
    run = [runs[i] for i in keep]
    b0s = [led.bank_at(et_day_start(d)) for d in days]
    n = 4 if winrate is not None else 3
    fig, axs = fig_new(n, 3.0 * n + 1.2, sharex=True)
    xs = _bars_by_day(axs[0], days, nets, usd)
    money_axis(axs[0])
    axs[0].set_title("$ each ET day")
    pc = [(100.0 * v / b) if b else 0.0 for v, b in zip(nets, b0s)]
    _bars_by_day(axs[1], days, pc, lambda v: "%+.2f%%" % v)
    pct_ticks(axs[1])
    axs[1].set_title("% of the bank each day (the bank at the start of that ET day)")
    ax = axs[2]
    ax.plot(xs, run, color=BLUE, lw=2.2, zorder=3, marker="o", ms=3.5)
    ax.fill_between(xs, run, 0, color=BLUE, alpha=0.08, lw=0)
    zero_line(ax)
    money_axis(ax)
    note(ax, xs[-1], run[-1], usd(run[-1]), dx=-4, ha="right")
    pct_of_axis(ax, dep, "%% of the %s put in" % usd(dep, False) if dep else "")
    ax.set_title("Running total")
    if winrate is not None:
        ax = axs[3]
        wx = [x for x, (_d, w, _b) in zip(xs, winrate) if w is not None]
        wv = [100.0 * w for _d, w, _b in winrate if w is not None]
        bv = [100.0 * b for _d, w, b in winrate if w is not None and b is not None]
        bx = [x for x, (_d, w, b) in zip(xs, winrate) if w is not None and b is not None]
        ax.plot(wx, wv, color=BLUE, lw=2.0, marker="o", ms=3.5, label="won % of markets", zorder=3)
        ax.plot(bx, bv, color=MUTED, lw=1.6, ls="--", label="break-even %", zorder=2)
        pct_ticks(ax, signed=False)
        ax.set_title("Each day: won % of markets vs the break-even it needed")
        legend(ax)
    date_axis(axs[-1])
    headline(fig, head)
    cap = ("%s: %s; the last %d days drawn, the running total counts all of them. Top: each day's money; then the "
           "same day as %% of the bank it began with; then the running total (right axis: %% of the money put in)%s." % (
               "/stats" if src == "stats" else "/days", src_words, len(days),
               "; bottom: won % of markets each day against the break-even win rate its prices needed"
               if winrate is not None else ""))
    return png(fig), cap


def _account_series(bs, c, sub, now):
    """[(epoch, dollars)] for pot `sub`: money moved in (botstats.flows) + every settlement (botstats.market),
    hour by hour, worked forward from Kalshi's books; plus the pot now (botstats._pot_now) or why not."""
    x = (c.get("subs") or {}).get(sub) or {}
    led = c.get("ledgers") or {}
    sett = sorted((m["t"], m["money"]) for m in (bs.market(s) for s in (x.get("rows") or {}).values())
                  if m["t"] is not None)
    times = [t for t, _m in sett]
    cum, run = [], 0.0
    for _t, v in sett:
        run += v
        cum.append(run)
    flow_t = []
    if sub == "0":
        for k in ("deposits", "withdrawals"):
            for r in led.get(k) or []:
                if bs.pinxfer.is_done(r) and bs.pinxfer.when(r) is not None:
                    flow_t.append(bs.pinxfer.when(r))
    for r in led.get("transfers") or []:
        t = bs._int(r.get("created_ts"))
        if t is not None and sub in (str(r.get("to_subaccount")), str(r.get("from_subaccount"))):
            flow_t.append(t)
    first = min(times[:1] + flow_t) if (times or flow_t) else None
    if first is None:
        return [], None, "nothing on Kalshi's books yet"
    grid = list(range(max(int(first) - 1800, int(now - WINDOW_DAYS * 86400)), int(now), 3600)) + [now]
    pts = []
    for g in grid:
        k = bisect.bisect_right(times, g)
        pts.append((g, bs.flows(led, sub, None, g + 1e-6) + (cum[k - 1] if k else 0.0)))
    v, why = bs._pot_now(c, sub)
    return pts, v, why


def chart_funds(ctx):
    bs, c, prows, ok = bs_load(ctx)
    now = ctx["now"]
    drawn, stopped = [], []
    for sub in bs.SUBS:
        bots = [b for b in bs.BOTS if bs.SPEC[b]["sub"] == sub]
        live = [b for b in bots if not bot_stopped(bs, b, prows, ok)]
        if not live:
            stopped.append("%s (%s)" % (ACCOUNT_NAME.get(sub, sub).lower(), ", ".join(bs.SPEC[b]["label"].lower() for b in bots)))
            continue
        pts, v, why = _account_series(bs, c, sub, now)
        if pts:
            drawn.append((sub, live, pts, v, why))
    for k, w in sorted((ctx.get("funds_what") or {}).items()):
        if str(k) not in bs.SUBS:
            ws = " ".join(w.values()) if isinstance(w, dict) else str(w)
            if "stopped" in ws:
                stopped.append("subaccount %s (%s)" % (k, ws.replace(" (stopped)", "")))
    if not drawn:
        return None
    fig, axs = fig_new(len(drawn), 2.7 * len(drawn) + 1.0, sharex=True)
    total, whole = 0.0, True
    for ax, (sub, live, pts, v, why) in zip(axs, drawn):
        X = [etdt(t) for t, _y in pts]
        Y = [y for _t, y in pts]
        ax.plot(X, Y, color=BLUE, lw=2.0, zorder=3)
        ax.fill_between(X, Y, 0, color=BLUE, alpha=0.07, lw=0)
        nowv = v if v is not None else Y[-1]
        total += nowv
        whole = whole and v is not None
        ax.scatter([X[-1]], [nowv], s=50, color=BLUE, edgecolor=SURF, linewidth=1.5, zorder=5)
        note(ax, X[-1], nowv, usd(nowv, False), dx=-4, ha="right")
        lo = min(Y + [nowv])
        ax.set_ylim(bottom=min(0.0, lo))
        money_axis(ax, signed=False)
        ax.set_title("%s · %s: %s%s" % (ACCOUNT_NAME.get(sub, sub), " + ".join(bs.SPEC[b]["label"].lower() for b in live),
                                        usd(nowv, False), " now" if v is not None else " (from the books; %s)" % str(why)[:44]),
                     color=INK, fontsize=11)
    date_axis(axs[-1])
    headline(fig, "Every running account: %s%s" % ("" if whole else "about ", usd(total, False)))
    cap = ("Each running account's money over time = cash + open bets at cost, worked forward from Kalshi's own "
           "deposits, transfers and settlements (botstats); the dot is the account now.%s"
           % ((" Stopped, not drawn: " + "; ".join(stopped) + ".") if stopped else ""))
    return png(fig), cap


def _race_rows(bs, c):
    """The coin race from botstats' rows: [(close epoch, race net, won, tie)] -- a race = the legs of one event;
    a TIE when any leg settled at 50c (Kalshi's `value`), WON when not a tie and its net >= 0 (races_from's rule)."""
    rows = ((c.get("subs") or {}).get("0") or {}).get("rows") or {}
    ev = {}
    for s in rows.values():
        if bs.owner(s.get("ticker"), "0") != "race":
            continue
        m = bs.market(s)
        if m["t"] is None:
            continue
        e = ev.setdefault(m["ticker"].rsplit("-", 1)[0], {"t": m["t"], "net": 0.0, "tie": False})
        e["t"] = min(e["t"], m["t"])
        e["net"] += m["money"]
        try:
            v = float(s.get("value"))
            e["tie"] = e["tie"] or (0.0 < v < 100.0)
        except (TypeError, ValueError):
            pass
    out = [(e["t"], e["net"], (not e["tie"]) and e["net"] >= 0, e["tie"]) for e in ev.values()]
    out.sort()
    return out


# ---- today's pace (operator 10-22: "for each bot ... a graph of today with an overlay of yesterday and then
# another overlay of the last 7 days so I can see if it's on track above or behind") ---------------------------
PACE_DAYS = 7


def day_base(bs, pctx_, sub, day):
    """What pot `sub` held at midnight ET starting `day`, + money moved in during that day -- botstats.pot_for's
    rule for one day (so a mid-day top-up only ever makes that day's % smaller). None when it cannot be known."""
    p = (pctx_.get("subs") or {}).get(sub) or {}
    if p.get("now") is None or not p.get("complete", True):
        return None
    t0, t1 = bs.day_start(day), bs.day_start(bs.shift_day(day, 1))
    settled = sum(v for d, v in (p.get("days") or {}).items() if d and d >= day)
    start = p["now"] - settled - bs.flows(pctx_["led"], sub, t0)
    if start < -bs.MIN_POT:
        return None
    pot = max(0.0, start) + max(0.0, bs.flows(pctx_["led"], sub, t0, t1))
    return pot if pot >= bs.MIN_POT else None


def pace_curves(bs, pctx_, sub, ms, today, now):
    """{'today': [(hour, cum %)], 'yesterday': [...], 'avg7': [...] (the mean of the PACE_DAYS days before today,
    on a 15-minute grid; days before the bot's first market are left out), 'n7': days averaged}. A day whose base
    is unknown is left out."""
    def curve(day):
        base = day_base(bs, pctx_, sub, day)
        if base is None:
            return None
        t0 = bs.day_start(day)
        pts, cum = [(0.0, 0.0)], 0.0
        for m in ms:
            if bs.et_day(m["t"]) == day:
                cum += m["money"]
                pts.append(((m["t"] - t0) / 3600.0, 100.0 * cum / base))
        return pts

    def at(pts, h):
        v = 0.0
        for x, y in pts:
            if x > h:
                break
            v = y
        return v
    first = min((m["t"] for m in ms), default=None)
    out = {"today": curve(today), "yesterday": curve(bs.shift_day(today, -1)), "avg7": None, "n7": 0}
    if out["today"] is not None:
        out["today"].append((min(24.0, (now - bs.day_start(today)) / 3600.0), out["today"][-1][1]))
    if out["yesterday"] is not None:
        out["yesterday"].append((24.0, out["yesterday"][-1][1]))
    days = [bs.shift_day(today, -k) for k in range(1, PACE_DAYS + 1)]
    cs = [c for d in days if first is not None and bs.day_start(bs.shift_day(d, 1)) > first
          for c in [curve(d)] if c is not None]
    if cs:
        grid = [i / 4.0 for i in range(0, 97)]
        out["avg7"] = [(h, sum(at(c, h) for c in cs) / len(cs)) for h in grid]
        out["n7"] = len(cs)
    return out


def draw_pace(ax, pc, now_h, goal=None):
    """Today (blue, to now) over yesterday (grey) and the 7-day average day (orange dashes), as % of the bank."""
    T = mpl()["ticker"]
    if pc["avg7"]:
        ax.plot([h for h, _ in pc["avg7"]], [v for _, v in pc["avg7"]], color=ORANGE, lw=1.8, ls="--", zorder=2,
                label="average of the last %d days (%s by now)" % (pc["n7"], pctx(_at_h(pc["avg7"], now_h) / 100.0, 2)))
    if pc["yesterday"]:
        ax.step([h for h, _ in pc["yesterday"]], [v for _, v in pc["yesterday"]], where="post", color=GREY, lw=1.6,
                zorder=2, label="yesterday %s (%s by now)" % (pctx(pc["yesterday"][-1][1] / 100.0, 2),
                                                             pctx(_at_h(pc["yesterday"], now_h) / 100.0, 2)))
    if pc["today"]:
        ax.step([h for h, _ in pc["today"]], [v for _, v in pc["today"]], where="post", color=BLUE, lw=2.4, zorder=3,
                label="today %s" % pctx(pc["today"][-1][1] / 100.0, 2))
        note(ax, pc["today"][-1][0], pc["today"][-1][1], pctx(pc["today"][-1][1] / 100.0, 2), dx=-4, ha="right")
    if goal is not None:
        ax.plot([0, 24], [0, goal], color=MUTED, lw=1.0, ls=":", zorder=1, label="goal %s a day, spread evenly" % pctx(goal / 100.0, 1, False))
    ax.axvline(now_h, color=AXIS, lw=1.0, ls=":", zorder=1)
    zero_line(ax)
    ax.set_xlim(0, 24)
    ax.xaxis.set_major_locator(T.FixedLocator(list(range(0, 25, 3))))
    ax.xaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: "%d %s" % ((int(v) % 12) or 12, "AM" if int(v) % 24 < 12 else "PM")))
    ax.yaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: "%+.2f%%" % v if abs(v) >= 0.005 else "0%"))
    ax.set_title("Today's pace, % of its bank, by ET clock (dotted line = now)")
    legend(ax)


def _at_h(pts, h):
    v = 0.0
    for x, y in pts:
        if x > h:
            break
        v = y
    return v


def chart_bot(ctx, name):
    bs, c, prows, ok = bs_load(ctx)
    if name not in bs.SPEC or bot_stopped(bs, name, prows, ok):
        return None
    now = ctx["now"]
    today = bs.et_day(now)
    pctx_ = bs.pot_context(c, today)
    blk = bs._money_block(c, name, today, pctx_)
    if not blk.get("ok") or not blk.get("markets"):
        return None
    ms = sorted((m for m in blk["markets"] if m["t"] is not None), key=lambda m: m["t"])
    sub = bs.SPEC[name]["sub"]
    label = bs.SPEC[name]["label"]
    fig, axs3 = fig_new(3, 11.0, ratios=[1.15, 1.25, 1])
    try:
        pc = pace_curves(bs, pctx_, sub, ms, today, now)
        draw_pace(axs3[0], pc, (now - bs.day_start(today)) / 3600.0, goal=1.0 if name == "ladder" else None)
    except Exception as e:                              # noqa: BLE001 -- the pace panel never costs the rest
        axs3[0].set_title("Today's pace: could not be drawn (%s)" % str(e)[:60])
    axs = axs3[1:]
    axs[0].sharex(axs[1])
    ax = axs[0]
    run, cum = [], 0.0
    for m in ms:                                        # the running total counts every market ...
        cum += m["money"]
        run.append(cum)
    cut = now - WINDOW_DAYS * 86400                     # ... the picture shows the last WINDOW_DAYS
    i0 = next((i for i, m in enumerate(ms) if m["t"] >= cut), len(ms) - 1)
    Xall = [etdt(m["t"]) for m in ms]
    X, R, W = Xall[i0:], run[i0:], ms[i0:]
    ax.step(X, R, where="post", color=BLUE, lw=2.0, zorder=3)
    lx = [x for x, m in zip(X, W) if m["money"] < -0.004]
    ly = [y for y, m in zip(R, W) if m["money"] < -0.004]
    run = R
    if lx:
        ax.scatter(lx, ly, s=22, color=DOWN, edgecolor=SURF, linewidth=1.0, zorder=4, label="a losing %s" % ("leg" if name == "race" else "market"))
        legend(ax)
    zero_line(ax)
    money_axis(ax)
    note(ax, X[-1], run[-1], usd(run[-1]), dx=-4, ha="right")
    base, _k, _why = bs.pot_for(pctx_, sub, "all_time")
    pct_of_axis(ax, base, ("%% of the %s's %s put in" % (bs.SUB_NAME[sub], usd(base, False))) if base else "")
    ax.set_title("Running total, market by market (Kalshi's books, %s)" % bs.SUB_NAME[sub])
    ax = axs[1]
    # a rolling rate is drawn only where its window is full (n markets / races behind it)
    if name == "race":
        races = _race_rows(bs, c)
        n = min(ROLL, max(5, len(races) // 4))
        rr = roll([100.0 if w else 0.0 for _t, _v, w, _tie in races], n)
        j0 = max(n - 1, next((i for i, r in enumerate(races) if r[0] >= cut), len(races)))
        ax.plot([etdt(r[0]) for r in races[j0:]], rr[j0:], color=BLUE, lw=2.0,
                label="won %% of the last %d races" % n, zorder=3)
        what = "races (a tie counts as not won)"
    else:
        n = min(ROLL, max(5, len(ms) // 4))
        j0 = max(n - 1, i0)
        ax.plot(Xall[j0:], roll([100.0 if m["money"] > 0.004 else 0.0 for m in ms], n)[j0:], color=BLUE, lw=2.0,
                label="won %% of the last %d markets" % n, zorder=3)
        pe = [((m["put_in"] + m["fees"]) / m["contracts"], 1.0) if m["contracts"] > 0 else (0.0, 0.0) for m in ms]
        acc = []
        sv = sw = 0.0
        for i, (v, w) in enumerate(pe):
            sv += v
            sw += w
            if i >= n:
                sv -= pe[i - n][0]
                sw -= pe[i - n][1]
            acc.append(100.0 * sv / sw if sw else None)
        ax.plot([x for x, a in zip(Xall[j0:], acc[j0:]) if a is not None], [a for a in acc[j0:] if a is not None],
                color=MUTED, lw=1.6, ls="--", label="break-even % (what its prices needed)", zorder=2)
        what = "markets"
    pct_ticks(ax, signed=False)
    ax.set_title("Win rate over time (%s)" % what)
    legend(ax)
    date_axis(axs[-1])
    at, td = blk.get("all_time") or {}, blk.get("today") or {}
    headline(fig, "%s: all time %s%s · today %s" % (
        label, usd(at.get("money")), (" (%+.1f%% of its bank)" % at["pot_pct"]) if at.get("pot_pct") is not None else "",
        usd(td.get("money") or 0.0)))
    cap = ("%s: every settled %s from Kalshi's books (botstats, %s), its running total and its win rate over "
           "time (the last %d days drawn; the total counts all). Right axis: the same dollars as %% of the money put into that account." % (
               label, "leg" if name == "race" else "market", bs.SUB_NAME[sub], WINDOW_DAYS))
    return png(fig), cap


def chart_losses(ctx):
    led = ctx["ledger"]
    lc = [(k, net, legs) for k, net, legs in led.losing_closes() if k]
    if not lc:
        return None
    lc.sort(key=lambda x: x[0])
    s = Ledger.summary(led.settled)
    X = [etdt(k) for k, _n, _l in lc]
    Y = [net for _k, net, _l in lc]
    P = []
    for k, net, _l in lc:
        b = led.bank_at(k)
        P.append((100.0 * net / b) if b else None)
    fig, axs = fig_new(2, 7.6, sharex=True)
    ax = axs[0]
    ax.vlines(X, 0, Y, color=DOWN, lw=1.4, zorder=3)
    ax.scatter(X, Y, s=26, color=DOWN, edgecolor=SURF, linewidth=1.0, zorder=4)
    mid = lc[0][0] + (lc[-1][0] - lc[0][0]) / 2.0
    for r, i in enumerate(sorted(range(len(Y)), key=lambda i: Y[i])[:3]):       # the 3 worst, staggered
        coins = ", ".join(sorted({pindesk.coin(lg["tk"]) for lg in lc[i][2]}))
        left = lc[i][0] < mid
        note(ax, X[i], Y[i], "%s %s %s" % (coins, et_clock(lc[i][0], "%m/%d"), usd(Y[i])), dx=6 if left else -6,
             dy=4 + 13 * r, ha="left" if left else "right", size=8.5, weight="normal")
    zero_line(ax)
    money_axis(ax)
    ax.set_title("Each losing close, dollars")
    ax = axs[1]
    px = [x for x, p in zip(X, P) if p is not None]
    pv = [p for p in P if p is not None]
    ax.vlines(px, 0, pv, color=DOWN, lw=1.4, zorder=3)
    ax.scatter(px, pv, s=26, color=DOWN, edgecolor=SURF, linewidth=1.0, zorder=4)
    zero_line(ax)
    pct_ticks(ax)
    ax.set_title("The same loss as % of the bank at that moment")
    date_axis(axs[-1])
    headline(fig, "%d losing closes of %d (%.1f%%) · worst %s" % (s["lost"], s["closes"], s["loss_rate"] or 0.0, usd(min(Y))))
    cap = ("Every losing close, all time (Kalshi's books, main account; one close = every market settling at that "
           "quarter-hour, as /losses counts them). Bottom: the loss as % of the bank then (pindesk's bank_at).")
    return png(fig), cap


def chart_hedges(ctx):
    led = ctx["ledger"]
    hm = sorted((m for m in markets_of(ctx).values() if m["hedged"] and m["hedge_pnl"] is not None and m["close"]),
                key=lambda m: m["close"])
    ho = [g for g in led.hedge_outcomes() if g.get("t") and g.get("net") is not None]
    if not hm and not ho:
        return None
    fig, axs = fig_new(2, 7.6, sharex=True)
    ax = axs[0]
    tot = 0.0
    if hm:
        run, cum = [], 0.0
        for m in hm:
            cum += m["hedge_pnl"]
            run.append(cum)
        tot = cum
        X = [etdt(m["close"]) for m in hm]
        ax.step(X, run, where="post", color=BLUE, lw=2.0, zorder=3)
        note(ax, X[-1], run[-1], usd(run[-1]), dx=-4, ha="right")
    zero_line(ax)
    money_axis(ax)
    ax.set_title("What the insurance legs made on their own, running total")
    ax = axs[1]
    for verdict, col, lab in (("WASTED", GREY, "WASTED (the bet held)"), ("NEEDED", BLUE, "NEEDED (the bet lost)"),
                              (None, ORANGE, "not settled")):
        g = [x for x in ho if x.get("verdict") == verdict]
        if g:
            ax.scatter([etdt(x["t"]) for x in g], [x["net"] for x in g], s=30, color=col, edgecolor=SURF, linewidth=1.0,
                       zorder=4, label="%s: %d" % (lab, len(g)))
    zero_line(ax)
    money_axis(ax)
    if ho:
        legend(ax)
    ax.set_title("Each hedged bet: what the whole market netted")
    date_axis(axs[-1])
    headline(fig, "Insurance: %s all time on %d hedged markets" % (usd(tot), len(hm)))
    cap = ("Top: each hedged market's other side, on its own (pinphone.markets_from's hedge_pnl, Kalshi's books), "
           "added up. Bottom: every executed hedge (the bot's records) and its market's net, by verdict.")
    return png(fig), cap


def chart_status(ctx):
    led, now = ctx["ledger"], ctx["now"]
    t0 = now - 7 * 86400
    grid = list(range(int(t0), int(now), 3600)) + [now]
    pts = [(g, led.bank_at(g)) for g in grid]
    pts = [(g, b) for g, b in pts if b is not None]
    if len(pts) < 2:
        return None
    fig, (ax,) = fig_new(1, 5.4)
    X = [etdt(g) for g, _b in pts]
    Y = [b for _g, b in pts]
    ax.plot(X, Y, color=BLUE, lw=2.0, zorder=3)
    reads = [(a["t"], a["bank"]) for a in led.autosize if a["bank"] is not None and a["t"] and a["t"] >= t0]
    if reads:
        ax.scatter([etdt(t) for t, _b in reads], [b for _t, b in reads], s=14, color=INK2, zorder=4,
                   label="the bot's own bank reads")
    mv = [e for e in led.external if e.get("t") and e["t"] >= t0 and abs(float(e.get("amount") or 0)) >= Ledger.TRANSFER_MIN]
    for e in mv:
        ax.axvline(etdt(e["t"]), color=ORANGE, lw=1.2, ls=":", zorder=2)
    if mv:
        ax.plot([], [], color=ORANGE, lw=1.2, ls=":", label="money moved in or out")
    note(ax, X[-1], Y[-1], usd(Y[-1], False), dx=-4, ha="right")
    money_axis(ax, signed=False)
    date_axis(ax, 7)
    ax.set_title("The bank, hour by hour, last 7 days")
    if reads or mv:
        legend(ax)
    headline(fig, "Bank %s · 7 days ago %s" % (usd(Y[-1], False), usd(Y[0], False)))
    cap = ("The main account's bank over the last 7 days: the bot's last bank read plus every settlement since "
           "(pindesk's bank_at, the figure /status shows). A deposit or withdrawal moves it too -- never profit.")
    return png(fig), cap


def chart_fills(ctx):
    led, now = ctx["ledger"], ctx["now"]
    day = et_day(now)
    rows = sorted((o for o in led.orders if o.get("t") and et_day(o["t"]) == day), key=lambda o: o["t"])
    if not rows:
        return None

    def px(o, *keys):
        for k in keys:
            try:
                v = float(o.get(k))
                if v > 0:
                    return 100.0 * v
            except (TypeError, ValueError):
                pass
        return None
    got = [(o, px(o, "price", "ask_seen")) for o in rows if float(o.get("filled") or 0) > 0]
    zero = [(o, px(o, "ask_seen", "limit_sent", "price")) for o in rows if float(o.get("filled") or 0) <= 0]
    fig, (ax,) = fig_new(1, 5.6)
    g = [(o, p) for o, p in got if p is not None]
    if g:
        ax.scatter([etdt(o["t"]) for o, _p in g], [p for _o, p in g],
                   s=[min(220, 18 + 4 * float(o.get("filled") or 0)) for o, _p in g], color=BLUE, alpha=0.85,
                   edgecolor=SURF, linewidth=1.0, zorder=4, label="filled: %d (dot size = contracts)" % len(got))
    z = [(o, p) for o, p in zero if p is not None]
    if z:
        ax.scatter([etdt(o["t"]) for o, _p in z], [p for _o, p in z], marker="x", s=40, color=ORANGE, linewidth=1.8,
                   zorder=5, label="filled nothing: %d (at the price it saw)" % len(zero))
    d0 = et_day_start(day)
    ax.set_xlim(etdt(d0), etdt(d0 + 86400))
    date_axis(ax, 1)
    T = mpl()["ticker"]
    ax.yaxis.set_major_locator(T.MaxNLocator(nbins=7, steps=[1, 2, 5, 10]))
    ax.yaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: ("%.1fc" if abs(ax.get_ylim()[1] - ax.get_ylim()[0]) < 6
                                                               else "%.0fc") % v))
    ax.set_title("Each order today: the price, by time sent (ET) · got %g of %g contracts" % (
        sum(float(o.get("filled") or 0) for o in rows), sum(float(o.get("asked") or 0) for o in rows)))
    legend(ax)
    headline(fig, "Orders today: %d · %d filled · %d filled nothing" % (len(rows), len(got), len(zero)))
    cap = "Today's orders from the bot's own records (as /fills lists them): what it paid, and the ones that lost the race."
    return png(fig), cap


def chart_market(ctx):
    led = ctx["ledger"]
    cl = [c for c in led.closes[-48:] if c.get("close")]
    pts = [(c, Ledger.offer_share(c)) for c in cl]
    pts = [(c, s) for c, s in pts if s is not None]
    if len(pts) < 2:
        return None
    act = led.activity()
    fig, (ax,) = fig_new(1, 5.6)
    X = [etdt(c["close"]) for c, _s in pts]
    Y = [100.0 * s for _c, s in pts]
    ax.plot(X, Y, color=BLUE, lw=1.8, zorder=3)
    f = [(x, y) for (c, _s), x, y in zip(pts, X, Y) if c.get("fired")]
    if f:
        ax.scatter([x for x, _y in f], [y for _x, y in f], s=34, color=BLUE, edgecolor=SURF, linewidth=1.2, zorder=4,
                   label="a quarter-hour it bought")
    for k, ls, lab in (("p25", ":", "quiet below"), ("median", "--", "typical"), ("p75", ":", "busy above")):
        if act.get(k) is not None:
            ax.axhline(100.0 * act[k], color=MUTED, lw=1.1, ls=ls, zorder=2)
            note(ax, X[0], 100.0 * act[k], "%s %.0f%%" % (lab, 100.0 * act[k]), dx=2, dy=2, ha="left", color=INK2,
                 weight="normal", size=8.5)
    ax.yaxis.set_major_formatter(mpl()["ticker"].FuncFormatter(lambda v, _p: "%.0f%%" % v))
    date_axis(ax, (pts[-1][0]["close"] - pts[0][0]["close"]) / 86400.0)
    ax.set_title("Share of looks with someone selling the winning side, each quarter-hour")
    if f:
        legend(ax)
    headline(fig, "Sellers: %s%s" % (act["level"], (" · %.0f%% of looks lately" % (100 * act["recent"])) if act.get("recent") is not None else ""))
    cap = ("The last %d quarter-hours from the bot's close summaries (as /market reads them); the dashed and dotted "
           "lines are the whole record's typical and quartile levels." % len(pts))
    return png(fig), cap


# ---- /bars: each running test against its bar --------------------------------------------------------
def _crit(name, value, unit, lines, good, bad, show=None):
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
                _crit("Net of live's fresh fills", f["net"], "$",
                      [(B.FRESH_DEPLOY_NET, "deploy at or under"), (B.FRESH_KILL_NET, "kill at or over")],
                      (None, B.FRESH_DEPLOY_NET), (B.FRESH_KILL_NET, None)),
                _crit("Fresh fills that lost", f["losers"], "",
                      [(B.FRESH_DEPLOY_LOSERS, "deploy needs at least")], (B.FRESH_DEPLOY_LOSERS, None), None),
                _crit("Losers only the arm had", extra, "", [(0, "deploy needs")], (None, 0.5), (0.5, None)),
                _crit("Days into the window", f["days"], "d", [(f["window_days"], "window")], None, None)]))
        else:
            other.append("fresh-offer test: %s" % f.get("verdict"))
    b = d.get("btcd")
    if b:
        p = b.get("paper")
        if p and b.get("verdict") == "TOO EARLY":
            tests.append(("Hourly BTC paper (%s) · day %.1f of %d · %s" % (b["paper_arm"], b["paper_days"], b["window_days"], b["verdict"]), [
                _crit("Fired closes", p["fired"], "", [(B.BTCD_BAR_FIRED, "needs")], (B.BTCD_BAR_FIRED, None), None),
                _crit("Contracts captured", p["contracts"], "", [(B.BTCD_BAR_CONTRACTS, "needs")], (B.BTCD_BAR_CONTRACTS, None), None),
                _crit("Losses inside 30 s", p["lost_le30"], "", [(0, "allowed")], (None, 0.5), (0.5, None)),
                _crit("Days into the window", b["paper_days"], "d", [(b["window_days"], "window")], None, None)]))
        else:
            other.append("hourly BTC paper: %s" % b.get("verdict"))
    r = d.get("race") or {}
    z = r.get("z3")
    if z:
        if z.get("log") and z.get("verdict") == "TOO EARLY" and not z.get("ran"):
            tests.append(("z3 race arm (paper) · %s" % z["verdict"], [
                _crit("Races entered", z["races"], "", [(B.Z3_PASS[0], "pass at")], (B.Z3_PASS[0], None), None),
                _crit("Losses (a tie is a loss)", z["losses"], "", [(B.Z3_PASS[1], "at most")], (None, B.Z3_PASS[1] + 0.5),
                      (B.Z3_PASS[1] + 0.5, None)),
                _crit("Losses in the first 50", z["first50_losses"], "", [(B.Z3_KILL[0], "kill at")], (None, B.Z3_KILL[0] - 0.5),
                      (B.Z3_KILL[0] - 0.5, None))]))
        else:
            other.append("z3: %s" % (z.get("ran") or z.get("verdict")))
    if r.get("gap075_ran"):
        other.append("gap075: %s" % r["gap075_ran"])
    if d.get("controls"):
        other.append("%d control arms (no bar)" % len(d["controls"]))
    return tests, other


def chart_bars(ctx):
    d = ctx.get("bars")
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
        lo, hi = min(xs + [0.0]), max(xs + [0.0])
        pad = max(1.0, 0.15 * (hi - lo))
        lo, hi = lo - pad, hi + pad
        ax.set_xlim(lo, hi)
        ax.set_ylim(0, 1)
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
        ax.set_yticks([])
        ax.grid(False)
        ax.spines["left"].set_visible(False)
        if c["unit"] == "$":
            money_axis(ax, axis="x")
        elif c["unit"] == "":
            ax.xaxis.set_major_locator(mpl()["ticker"].MaxNLocator(integer=True))
        if title:
            ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(0, 22), textcoords="offset points",
                        fontsize=11.5, fontweight="bold", color=INK2, va="bottom", annotation_clip=False)
    headline(fig, "Running tests against their bars")
    cap = ("Each running test's numbers (research/bars.py, the /bars words) against the bar written before its data: "
           "green zone = where the bar passes, red = where it kills, the diamond = now.%s" % (
               (" Not drawn: " + "; ".join(other) + ".") if other else ""))
    return png(fig), cap


def build(kind, ctx):
    """(png bytes, caption) for picture `kind`, or None when there is nothing live to draw."""
    if kind in ("today", "yesterday"):
        return chart_day(ctx, kind)
    if kind in ("days", "stats"):
        return chart_days(ctx, kind)
    if kind == "funds":
        return chart_funds(ctx)
    if kind.startswith("bot:"):
        return chart_bot(ctx, kind[4:])
    fn = {"losses": chart_losses, "hedges": chart_hedges, "status": chart_status, "fills": chart_fills,
          "market": chart_market, "bars": chart_bars}.get(kind)
    return fn(ctx) if fn else None


# =======================================================================================================
def selftest():
    """Every chart drawn from planted data (no file, no network), each a real PNG under MAX_BYTES; empty data
    gives no picture; a stopped bot gives no picture; nothing stopped is drawn."""
    import calendar
    import tempfile
    import types

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg, flush=True)
        if not cond:
            raise SystemExit("tgcharts selftest: FAILED -- " + msg)

    def is_png(x):
        return isinstance(x, tuple) and x[0][:8] == b"\x89PNG\r\n\x1a\n" and 1000 < len(x[0]) < MAX_BYTES and x[1]

    now = calendar.timegm((2026, 10, 18, 15, 30, 0))                  # 11:30 AM ET Sun Oct 18
    led = Ledger(results=tempfile.gettempdir())
    led.deposited = lambda: 1000.0
    st, ords, auto, closes, hed = [], [], [], [], []
    for k in range(10 * 96):                                          # ten days of quarter-hours
        c = now - k * 900 - 60
        pnl = -4.0 if k % 37 == 5 else 0.6
        tk = "KXBTC15M-26OCT%02d%02d%02d-00" % (18, 0, 0)
        st.append({"t": c + 30, "tk": "%s-%d" % (tk, k), "pnl": pnl, "close": c, "result": "yes", "want": "yes", "file": "kalshi"})
        ords.append({"t": c - 30, "tk": "%s-%d" % (tk, k), "filled": 0.0 if k % 5 == 0 else 10.0, "asked": 10.0,
                     "price": 0.96, "ask_seen": 0.96, "limit_sent": 0.97, "tau": 25, "close": c})
        closes.append({"t": c, "close": c, "looks": 100, "no_offer": 40 + (k % 30), "fired": k % 3 == 0, "gates": {}})
        if k % 12 == 0:
            auto.append({"t": c, "bank": 1000.0 + 0.5 * (960 - k), "size": 20})
        if k % 50 == 7:
            hed.append({"t": c - 20, "kind": "hedge", "tk": "%s-%d" % (tk, k), "status": "executed", "side": "no", "n": 5,
                        "price": 0.1, "belief": 0.6})
    led.settled = sorted(st, key=lambda s: s["t"])
    led.orders = sorted(ords, key=lambda o: o["t"])
    led.autosize = sorted(auto, key=lambda a: a["t"])
    led.closes = sorted(closes, key=lambda c: c["close"])
    led.hedges = hed
    led.external = [{"t": now - 3 * 86400, "move": "deposit", "amount": 200.0}]
    pp = types.SimpleNamespace(FIRST_LIVE_DAY="2026-10-09", window_stats=None)
    ctx = {"now": now, "ledger": led, "pp": pp}
    for kind in ("today", "yesterday", "days", "losses", "status", "fills", "market"):
        t0 = time.time()
        got = build(kind, ctx)
        ck(is_png(got), "%s: a PNG (%d KB, %.1f s), caption %r" % (kind, len(got[0]) // 1024 if got else 0,
                                                                  time.time() - t0, (got or ("", ""))[1][:60]))
    empty = Ledger(results=tempfile.gettempdir())
    empty.deposited = lambda: None
    ck(all(build(k, {"now": now, "ledger": empty, "pp": pp}) is None for k in ("today", "yesterday", "days", "losses", "fills", "market")),
       "nothing settled / no orders / no closes -> no picture (the words already say so)")

    # /stats and /hedges through pinphone's own market functions (a planted kalshi ledger, read from a temp file)
    import pinphone as PP
    with tempfile.TemporaryDirectory() as td:
        rows = []
        for k in range(200):
            c = now - k * 3600
            tm = time.strftime("%y%b%d%H%M", time.gmtime(c + pindesk.et_offset(c))).upper()   # v-etclock: ET, not a fixed -4 h
            win = k % 25 != 3
            hedged = k % 40 == 0
            rows.append({"ticker": "KXBTC15M-%s-00" % tm, "settled_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(c + 60)),
                         "market_result": "yes" if win else "no", "yes_count_fp": "10.00", "no_count_fp": "10.00" if hedged else "0.00",
                         "yes_total_cost_dollars": "9.60", "no_total_cost_dollars": "1.00" if hedged else "0.0000",
                         "fee_cost": "0.07", "revenue": 1000 if win else 0, "value": 100 if win else 0})
        import pinledger
        with open(os.path.join(td, PP.pinday.LEDGER_NAME), "w", encoding="utf-8") as fh:
            import json
            json.dump({"rows": {"%s|%s" % (r["ticker"], r["settled_time"]): r for r in rows}}, fh)
        led.results = td
        sv = pinledger.load_cache
        try:
            pinledger.load_cache = lambda path=None: {"%s|%s" % (r["ticker"], r["settled_time"]): r for r in rows}
            ctx2 = {"now": now, "ledger": led, "pp": PP}
            for kind in ("stats", "hedges"):
                got = build(kind, ctx2)
                ck(is_png(got), "%s: a PNG from pinphone.markets_from / window_stats (%d KB)" % (kind, len(got[0]) // 1024 if got else 0))
        finally:
            pinledger.load_cache = sv

    # /bots /funds and one bot: a planted botstats cache and process table
    import botstats as BS
    with tempfile.TemporaryDirectory() as td:
        sv = (BS.RESULTS, BS._load)
        try:
            BS.RESULTS = td
            open(os.path.join(td, BS.SPEC["weather"]["stop"]), "w").close()          # weather: stopped
            subs = {}
            for sub, n in (("0", 300), ("1", 40), ("2", 60), ("3", 20)):
                r = {}
                for k in range(n):
                    t = now - k * 4000
                    tk = ("KXBTC15M-26OCT%02d%02d%02d-%02d" % (18, k % 24, 0, k % 60)) if sub == "0" else "KXX-%s-%d" % (sub, k)
                    if sub == "0" and k % 3 == 0:
                        tk = "KXCRYPTOLEAD15M-26OCT18%04d-%s" % (k, ("BTC", "ETH")[k % 2])
                    win = k % 19 != 4
                    r["%s|%d" % (tk, k)] = {"ticker": tk, "settled_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)),
                                            "market_result": "yes" if win else "no", "yes_count_fp": "5.00", "no_count_fp": "0.00",
                                            "yes_total_cost_dollars": "4.80", "no_total_cost_dollars": "0.00", "fee_cost": "0.03",
                                            "revenue": 500 if win else 0, "value": 100 if win else 0}
                subs[sub] = {"rows": r, "complete": True, "tried": now, "fetched": now, "positions": [], "pos_t": now,
                             "balance": 100.0, "bal_t": now}
            c = {"subs": subs, "ledgers": {"tried": now, "fetched": now,
                                           "deposits": [{"amount_cents": 150000, "fee_cents": 0, "status": "applied",
                                                         "created_ts": int(now - 20 * 86400), "finalized_ts": int(now - 20 * 86400)}],
                                           "withdrawals": [],
                                           "transfers": [{"amount_cents": 10000, "from_subaccount": 0, "to_subaccount": s,
                                                          "created_ts": int(now - 15 * 86400)} for s in (1, 2, 3)],
                                           "subaccount_balances": [{"subaccount_number": int(s), "exchange_index": BS.SUB_POOL[s],
                                                                    "balance": 100.0} for s in BS.SUBS]}}
            procs = [(1, "x", "python research/pinrun.py --live"), (2, "x", "python research/pinracearm.py --live"),
                     (3, "x", "python research/forecaster_live.py --live"), (4, "x", "python research/ladder_live.py --live")]
            BS._load = lambda now_, getter, procs_: (c, BS._norm_procs(procs), True)
            ctx3 = {"now": now, "pp": PP, "funds_what": {4: "coin-race reward test (stopped)"}}
            got = build("funds", ctx3)
            ck(is_png(got) and "subaccount 3 (weather dip-seller)" in got[1] and "subaccount 4 (coin-race reward test)" in got[1],
               "/funds: a PNG of the running accounts; the stopped weather account and subaccount 4 are named, not drawn")
            for b in ("pin", "race", "forecaster", "ladder"):
                got = build("bot:" + b, ctx3)
                ck(is_png(got), "/%s: a PNG (%d KB)" % (b, len(got[0]) // 1024 if got else 0))
            ck(build("bot:weather", ctx3) is None, "/weather: its stop file is set -> no picture of a stopped bot")
            procs.pop(3)
            ck(build("bot:ladder", ctx3) is None, "/ladder: not in the process table -> no picture")
        finally:
            BS.RESULTS, BS._load = sv

    # /bars: only a RUNNING test is drawn
    import bars as B
    d = {"fresh": {"arm": "arm-fresh500", "days": 3.2, "window_days": 7, "net": -12.43, "losers": 2,
                   "h2h": {"arm_extra_losers": [1]}, "verdict": "TOO EARLY", "arm_running": True},
         "btcd": {"paper": {"fired": 19, "contracts": 31.0, "lost_le30": 0}, "paper_arm": "arm-btcd", "paper_days": 24.0,
                  "window_days": 7, "verdict": "KILL"},
         "race": {"z3": {"log": True, "races": 134, "losses": 1, "first50_losses": 1, "verdict": "TOO EARLY",
                         "ran": "STOPPED: ran Sep 22 to Oct 01"}, "gap075_ran": "STOPPED: ran Sep 24 to Sep 27"},
         "controls": {"a": None}}
    got = build("bars", {"now": now, "bars": d})
    ck(is_png(got) and "hourly BTC paper: KILL" in got[1] and "z3: STOPPED" in got[1],
       "/bars: the running fresh test is drawn; the decided and the stopped ones are named, not drawn")
    d["fresh"]["arm_running"] = False
    ck(build("bars", {"now": now, "bars": d}) is None, "/bars: no running test -> no picture")
    ck(kind_of("/open") is None and kind_of("/stop") is None and kind_of("/pause") is None and kind_of("/help") is None
       and kind_of("/mute") is None and kind_of("/today") == "today" and kind_of("/fc") == "bot:forecaster",
       "words-only commands get no picture; the controls never queue one")
    print("tgcharts selftest: OK (matplotlib %s)" % mpl()["version"])


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
