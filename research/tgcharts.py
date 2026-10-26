#!/usr/bin/env python3
r"""tgcharts.py -- the phone's pictures: real x-y charts, sent right after a command's words.

THE OPERATOR, 2026-10-18: "Telegram still looks very bad, do actual x y charts and that solution should
work for most commands. For the others figure something out."

WHAT EACH COMMAND GETS (one PNG, sent by pinphone with sendPhoto after the text):
  /today /yesterday        every bot's running total market by market on the ET clock (each losing market marked
                           and named by its bot and $; the title line gives each bot's money that day; /today has
                           yesterday beside it in grey); orange dashes = the average day of the 7 days before
                           (10-23); right axis = the same dollars as % of all pots at the start of the day
  /days /brief /summary    every ET day: $ bars, % of the bank bars (each with its 7-day average line), the
                           running total ($ and % of money put in)
  /stats                   every bot, one colour a bot (10-26): $ each day stacked by bot, the day's net as % of all
                           pots, each bot's running total (the small bots again on their own scale). The main
                           account's old picture (with won % against break-even) when botstats cannot be read
  /bots /funds /bank /accounts   every RUNNING account's money over time (cash + open bets at cost), a panel each,
                           in its bot's colour
  /pin /fc /ladder /weather /race /racestats   that bot's running total and its win rate over its last
                           50 markets (races for /race) against break-even
  /losses                  every bot's losing markets, coloured by bot: dollars, and % of that bot's pot that day
  /hedges                  what the pin bot's insurance legs made, running total; each hedged bet's net by verdict
  /status                  the main account's bank over the last 7 days, hour by hour (pindesk's bank_at)
  /fills /bets             the pin bot's orders today: price by time, filled vs filled nothing
  /market                  sellers' share of the pin bot's looks over the last 48 quarter-hours against the record's
                           quartiles
  (/hedges /status /fills /market read the pin bot's own log, so each says "pin bot"; every bot-split picture uses
   BOT_COLOUR, one colour a bot, never the green or red of a gain or a loss)
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
            "/ladder": "bot:ladder", "/weather": "bot:weather", "/wx": "bot:weather", "/fx": "bot:fx",
            "/race": "bot:race", "/racestats": "bot:race",
            "/losses": "losses", "/hedges": "hedges", "/fills": "fills", "/bets": "fills",
            "/market": "market", "/bars": "bars"}
LEDGER_KINDS = frozenset(["status", "today", "yesterday", "days", "stats", "losses", "hedges", "fills", "market"])
ACCOUNT_NAME = {"0": "Main account", "1": "Subaccount 1", "2": "Subaccount 2", "3": "Subaccount 3", "4": "Subaccount 4",
                "5": "Subaccount 5"}
POT_WHAT = {"4": "currencies", "5": "commodities"}       # a bot with two pots names each one's part (the FX taker)


def account_name(key):
    """'Main account' / 'Subaccount 1' for one pot, 'Subaccounts 5 + 4' for a bot's pots (a tuple)."""
    if len(key) == 1:
        return ACCOUNT_NAME.get(key[0], "Subaccount %s" % key[0])
    return "Subaccounts " + " + ".join(key)


def kind_of(cmd):
    return CMD_KIND.get(cmd)


# ---- matplotlib, on first use ------------------------------------------------------------------------
_M = {}


def mpl():
    if not _M:
        for _blas in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):    # see pinphone.py: one BLAS
            os.environ.setdefault(_blas, "1")                                          # thread, not 16 buffers (10-26)
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
    fig.suptitle(text, x=0.012, ha="left", fontsize=min(14.0, 14.0 * 54 / max(1, len(text))), fontweight="bold",
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


def place_notes(ax, items, size=8.5):
    """Name points without covering anything: items = [(x, y, text)] in data units (x may be a datetime). Each name
    takes the first spot around its point that covers no other words, no legend and no line, inside the axes (the
    least bad spot when none is free). Call it last, after the limits, the legend and the other notes are set."""
    if not items:
        return
    import numpy as np
    from matplotlib import cbook
    fig = ax.figure
    fig.canvas.draw()                                   # the layout settles: from here positions are real pixels
    rnd = fig.canvas.get_renderer()
    box = ax.get_window_extent(rnd)
    taken = [t.get_window_extent(rnd).expanded(1.0, 1.0) for t in ax.texts]
    if ax.get_legend() is not None:
        taken.append(ax.get_legend().get_window_extent(rnd))
    marks, weight = [], []                              # every line, a point each ~3 px (a thick line costs more)
    for ln in ax.get_lines():
        xy = np.asarray(ln.get_xydata(), dtype=float)
        if len(xy) < 2:
            continue
        if ln.get_drawstyle().startswith("steps"):
            xs, ys = cbook.pts_to_poststep(xy[:, 0], xy[:, 1])
            xy = np.column_stack([xs, ys])
        p = ax.transData.transform(xy)
        for a, b in zip(p[:-1], p[1:]):
            n = max(1, int(np.hypot(*(b - a)) / 3.0))
            marks.append(a + (b - a) * np.linspace(0.0, 1.0, n + 1)[:, None])
            weight.append(np.full(n + 1, float(ln.get_linewidth()) ** 2))
    dots = [ax.transData.transform(np.asarray(c.get_offsets(), dtype=float)) for c in ax.collections
            if hasattr(c, "get_offsets") and len(c.get_offsets())]
    marks = np.vstack(marks) if marks else np.zeros((0, 2))
    weight = np.concatenate(weight) if weight else np.zeros(0)
    dots = np.vstack(dots) if dots else np.zeros((0, 2))
    spots = [(-7, 0, "right", "center"), (7, -10, "left", "top"), (-7, -12, "right", "top"), (7, 10, "left", "bottom"),
             (-7, 12, "right", "bottom"), (0, -16, "center", "top"), (0, 16, "center", "bottom"), (7, 0, "left", "center"),
             (-7, -26, "right", "top"), (7, -24, "left", "top"), (-7, 26, "right", "bottom"), (7, 24, "left", "bottom")]

    def inside(bb, pts, pad, w=None):
        if not len(pts):
            return 0.0
        hit = ((pts[:, 0] >= bb.x0 - pad) & (pts[:, 0] <= bb.x1 + pad) & (pts[:, 1] >= bb.y0 - pad) & (pts[:, 1] <= bb.y1 + pad))
        return float(np.sum(w[hit])) if w is not None else float(np.sum(hit))
    for x, y, text in items:
        best = None
        two = text.replace(" -$", "\n-$").replace(" +$", "\n+$")      # narrower, on two lines: tried after one
        for words in (text, two) if two != text else (text,):
            for dx, dy, ha, va in spots:
                far = abs(dy) > 14
                a = ax.annotate(words, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=size,
                                color=INK, zorder=6, linespacing=1.0,
                                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7, shrinkA=0, shrinkB=4) if far else None)
                bb = a.get_window_extent(rnd)
                score = (0 if (bb.x0 >= box.x0 and bb.x1 <= box.x1 and bb.y0 >= box.y0 and bb.y1 <= box.y1) else 1000)
                score += 1000 * sum(1 for t in taken if bb.overlaps(t))
                score += inside(bb, marks, 1.0, weight) + 40 * inside(bb, dots, 6.0) + (2 if words is two else 0) + (2 if far else 0)
                if best is None or score < best[0]:
                    if best is not None:
                        best[1].remove()
                    best = (score, a, bb)
                else:
                    a.remove()
                if score == 0:
                    break
            if best[0] == 0:
                break
        taken.append(best[2])


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


# ---- the 7-day average (operator 10-23: "The 7 day average should be on the other charts too where possible.
# Like on /today as a 3rd line.") -- always the AVG_DAYS ET days BEFORE the day drawn (today never averages itself);
# a calendar day inside that span with nothing settled counts as $0; days before the first day on the books are
# left out (so the first week averages the days there are) ------------------------------------------------------
AVG_DAYS = 7


def prev_day(day):
    return et_day(et_day_start(day) - 3600)


def day_avg(led, day):
    """The average day of the AVG_DAYS ET days before `day`, close by close on the ET clock:
    ([(seconds after midnight ET, mean running $)] on a 15-minute grid, days averaged) -- ([], 0) when none."""
    listed = led.days()
    if not listed:
        return [], 0
    ds, d = [], day
    for _ in range(AVG_DAYS):
        d = prev_day(d)
        if d >= listed[0]:
            ds.append(d)
    if not ds:
        return [], 0
    curves = []
    for d in ds:
        t0 = et_day_start(d)
        curves.append([(k - t0, c) for k, c, _v in closes_cum(led.settled_on(d))])

    def at(pts, g):
        v = 0.0
        for x, y in pts:
            if x > g:
                break
            v = y
        return v
    grid = list(range(0, 86400 + 1, 900))
    return [(g, sum(at(c, g) for c in curves) / len(curves)) for g in grid], len(ds)


def avg_by_day(vals, days):
    """{day: mean of `vals` (a {day: number} dict) over that day and the AVG_DAYS-1 calendar days before it}, for
    each of `days` (sorted ET days); a day missing from `vals` counts as 0; days before min(vals) are left out."""
    if not vals:
        return {}
    first = min(vals)
    out = {}
    for day in days:
        span, d = [], day
        for _ in range(AVG_DAYS):
            if d < first:
                break
            span.append(vals.get(d, 0.0))
            d = prev_day(d)
        out[day] = (sum(span) / len(span)) if span else None
    return out


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
def _all_markets(ctx):
    """Every bot's settled markets from botstats, whole: (bs, c, process rows, process table read?, pot context,
    [(bot, botstats.market row)] by settled time, [bots whose pots could not be read])."""
    bs, c, prows, ok = bs_load(ctx)
    today = bs.et_day(ctx["now"])
    pctx_ = bs.pot_context(c, today)
    out, missing = [], []
    for name in tuple(bs.BOTS) + ("other",):
        blk = bs._money_block(c, name, today, pctx_)
        if not blk.get("ok"):
            missing.append(name)
            continue
        out += [(name, m) for m in blk.get("markets") or [] if m["t"] is not None and m["day"]]
    out.sort(key=lambda r: r[1]["t"])
    return bs, c, prows, ok, pctx_, out, missing


def all_day_markets(ctx):
    """Every bot's settled markets from botstats (the /bots source, Kalshi's books, every pot):
    (bs, pot context, [(ET close day, settled epoch, $, bot)] by time, [pots that could not be read])."""
    bs, _c, _prows, _ok, pctx_, ms, missing = _all_markets(ctx)
    return bs, pctx_, [(m["day"], m["t"], m["money"], name) for name, m in ms], missing


BOT_SHORT = {"pin": "Pin bot", "race": "Coin race", "forecaster": "Forecaster", "ladder": "Ladder",
             "weather": "Weather", "fx": "FX taker", "other": "Other"}
# One colour a bot, the same in every picture that splits by bot (/stats /losses /bots, each bot's page). Green and red mean
# gain and loss on these charts, so no bot is either (operator 10-26: "every bank in different colors"). The five
# running bots pass the dataviz palette check on every pair, colour-blind included (validate_palette.js --pairs all).
BOT_COLOUR = {"pin": "#2a78d6",          # blue
              "race": "#ef7f1a",         # orange, yellower than the 7-day dashes' so it never reads as a loss
              "forecaster": "#a0479f",   # plum
              "ladder": "#1aa3a3",       # teal
              "weather": "#4b3fa0",      # indigo (stopped)
              "fx": "#8a5a00",           # brown-gold
              "other": "#8f8d86"}        # grey
BOT_ORDER = ("pin", "race", "forecaster", "ladder", "weather", "fx", "other")
LOSS_NAMES = 8                          # /today: the losing markets named on the picture (the biggest, when more)


def _wrap(text, width, sep=" · "):
    """Break a ' · ' list onto as many lines as it needs, `width` characters a line at most (where it can)."""
    out, line = [], ""
    for part in text.split(sep):
        cand = (line + sep + part) if line else part
        if line and len(cand) > width:
            out.append(line)
            line = part
        else:
            line = cand
    return "\n".join(out + [line])


def all_losses(ctx, week_days=7):
    """Every bot's LOSING markets from botstats (the /bots source, Kalshi's books, every pot). Operator 10-26: "Make
    it so /losses outputs losses not just for pin and race and show which bot it lost" -- /losses was the main
    account only (pin + race, one row a quarter-hour). (bs, losers newest day first and newest settled first in a
    day, {bot: totals}, [bots whose pots could not be read]). A loser is botstats.market's row plus bot, pot (that
    bot's pot when its day began + money moved in that day: botstats.day_pot, the /bots base) and pct (None when
    the pot is unknown -- never a guessed base). Totals: settled, lost, lost_7d, money_lost, worst."""
    bs, c, _prows, _ok = bs_load(ctx)
    today = bs.et_day(ctx["now"])
    pctx_ = bs.pot_context(c, today)
    week = {bs.shift_day(today, -k) for k in range(week_days)}
    out, per, missing, pots = [], {}, [], {}
    for name in tuple(bs.BOTS) + ("other",):
        blk = bs._money_block(c, name, today, pctx_)
        if not blk.get("ok"):
            missing.append(name)
            continue
        subs = bs.bot_subs(name)
        key = subs if len(subs) > 1 else subs[0]
        ms = blk.get("markets") or []
        lost = [m for m in ms if m["money"] < -0.004]
        won_days = {}
        for m in ms:
            if m["money"] > 0.004 and m["day"]:
                won_days[m["day"]] = won_days.get(m["day"], 0.0) + m["money"]
        per[name] = {"settled": len(ms), "lost": len(lost), "lost_7d": sum(1 for m in lost if m["day"] in week),
                     "money_lost": round(sum(m["money"] for m in lost), 4),
                     "worst": min((m["money"] for m in lost), default=None),
                     "won_days": won_days}                  # ET day -> $ its winning markets made (the chart)
        for m in lost:
            if (key, m["day"]) not in pots:
                pots[(key, m["day"])] = bs.day_pot(pctx_, key, m["day"]) if m["day"] else None
            pot = pots[(key, m["day"])]
            out.append(dict(m, bot=name, pot=pot, pct=(100.0 * m["money"] / pot) if pot else None))
    out.sort(key=lambda r: (r["day"] or "", r["t"] or 0), reverse=True)
    return bs, out, per, missing


def by_now(rows, bs, day, now, n=AVG_DAYS):
    """(money so far on `day`, the average of the n days before it at the same ET clock -- rounded down to the
    quarter-hour, as /today's orange line is drawn -- and how many days were averaged) from all_day_markets' rows.
    The average is None when there is no earlier day. Days before the first market are left out."""
    d0 = bs.day_start(day)
    g = (max(0.0, now - d0) // 900) * 900
    so_far = sum(v for dd, _t, v, _b in rows if dd == day)
    first = min((r[0] for r in rows), default=None)
    ds, d = [], day
    for _ in range(n):
        d = bs.shift_day(d, -1)
        if first is not None and d >= first:
            ds.append(d)
    if not ds:
        return so_far, None, 0
    tot = 0.0
    for d in ds:
        t0 = bs.day_start(d)
        tot += sum(v for dd, t, v, _b in rows if dd == d and min(max(t, t0), t0 + 86400) - t0 <= g)
    return so_far, tot / len(ds), len(ds)


def chart_day(ctx, which):
    """/today /yesterday: EVERY bot's money that ET day (operator 10-23: "/today doesn't show the right total it
    says 11.22 right now it's really 24.85" -- the old picture was the main account only). Falls back to the main
    account's own ledger (chart_day_main) when botstats cannot be read."""
    try:
        bs, pctx_, rows, missing = all_day_markets(ctx)
    except Exception:                                   # noqa: BLE001 -- no botstats: the main account's picture
        return chart_day_main(ctx, which) if ctx.get("ledger") is not None else None
    now = ctx["now"]
    today = bs.et_day(now)
    day = today if which == "today" else bs.shift_day(today, -1)
    first = min((r[0] for r in rows), default=None)

    def curve(d):
        t0 = bs.day_start(d)
        t1 = bs.day_start(bs.shift_day(d, 1))
        pts, cum, lost = [], 0.0, []
        for dd, t, v, b in rows:
            if dd == d:
                cum += v
                pts.append((min(max(t, t0), t1) - t0, cum))
                if v < -0.004:
                    lost.append((min(max(t, t0), t1) - t0, cum, v, b))
        return pts, lost
    pts, lost = curve(day)
    if not pts:
        return None
    ms = [r for r in rows if r[0] == day]
    net = sum(r[2] for r in ms)
    won = sum(1 for r in ms if r[2] > 0.004)
    d0 = bs.day_start(day)
    b0 = bs.day_pot(pctx_, None, day) if not missing else None
    fig, (ax,) = fig_new(1, 5.6)
    label = "Today" if day == today else "Yesterday"
    end = min(now, d0 + 86400) if day == today else d0 + 86400
    X = [etdt(d0)] + [etdt(d0 + s) for s, _c in pts] + [etdt(max(end, d0 + pts[-1][0]))]
    Y = [0.0] + [c for _s, c in pts] + [pts[-1][1]]
    if day == today:
        ypts, _yl = curve(bs.shift_day(day, -1))
        if ypts:
            ax.step([etdt(d0)] + [etdt(d0 + s) for s, _c in ypts] + [etdt(d0 + 86400)],
                    [0.0] + [c for _s, c in ypts] + [ypts[-1][1]], where="post", color=GREY, lw=1.6,
                    label="Yesterday %s" % usd(ypts[-1][1]), zorder=2)
    ds, d = [], day
    for _ in range(AVG_DAYS):
        d = bs.shift_day(d, -1)
        if first is not None and d >= first:
            ds.append(d)
    if ds:
        cs = [curve(x)[0] for x in ds]

        def at(c, g):
            v = 0.0
            for s, y in c:
                if s > g:
                    break
                v = y
            return v
        avg = [(g, sum(at(c, g) for c in cs) / len(cs)) for g in range(0, 86400 + 1, 900)]
        if day == today:
            by_now = at(avg, now - d0)
            alab = "Average of the last %d days %s (%s by now)" % (len(ds), usd(avg[-1][1]), usd(by_now))
        else:
            alab = "Average of the %d days before %s" % (len(ds), usd(avg[-1][1]))
        ax.plot([etdt(d0 + g) for g, _v in avg], [v for _g, v in avg], color=ORANGE, lw=1.8, ls="--",
                label=alab, zorder=2)
    # every bot together is the dark line (/stats' 'all bots'); blue is the pin bot's own colour now (10-26)
    ax.step(X, Y, where="post", color=INK, lw=2.2, label="%s %s" % (label, usd(net)), zorder=3)
    named = sorted(sorted(lost, key=lambda x: x[2])[:LOSS_NAMES], key=lambda x: x[0])
    if lost:
        ax.scatter([etdt(d0 + s) for s, _c, _v, _b in lost], [c for _s, c, _v, _b in lost], s=46, color=DOWN,
                   edgecolor=SURF, linewidth=1.5, zorder=5,
                   label="a losing market, named by bot" if len(named) == len(lost)
                   else "a losing market (the %d biggest named)" % len(named))
        lo, hi = ax.get_ylim()                          # room under the lowest loss for its name
        low = min(c for _s, c, _v, _b in named)
        if low - lo < 0.12 * (hi - lo):
            ax.set_ylim(low - 0.12 * (hi - lo), hi)
    zero_line(ax)
    ax.set_xlim(etdt(d0), etdt(d0 + 86400))
    date_axis(ax, 1)
    money_axis(ax)
    note(ax, X[-1], Y[-1], usd(Y[-1]), dx=-4, ha="right")
    pct_of_axis(ax, b0, "%% of all pots at midnight ET (%s)" % usd(b0, False) if b0 else "")
    each = {}                                           # each bot's money that day: who made the day
    for _d, _t, v, b in ms:
        each[b] = each.get(b, 0.0) + v
    by_bot = " · ".join("%s %s" % (BOT_SHORT.get(b, b), usd(v)) for b, v in sorted(each.items(), key=lambda kv: kv[1]))
    ax.set_title("Every bot, running total market by market (ET)\n%s" % _wrap("By bot: " + by_bot, 78))
    legend(ax)
    place_notes(ax, [(etdt(d0 + s), c, "%s %s" % (BOT_SHORT.get(b, b), usd(v))) for s, c, v, b in named])
    r = (net / b0) if b0 else None
    headline(fig, "%s %s%s · %d of %d markets won" % (label, usd(net), (" (%s of all pots)" % pctx(r, 2)) if r is not None else "",
                                                    won, len(ms)))
    cap = ("%s: every bot's money market by market (pin, coin race, forecaster, ladder, FX taker; Kalshi's books, every pot; "
           "a market counts on the ET day it closed). By bot: %s. Red dots: a losing market, named by its bot. Orange "
           "dashes: the average day of the %d days before, on the same clock. Right axis: the same dollars as %% of all "
           "pots at the start of the ET day.%s" % (
               label, by_bot, AVG_DAYS, (" PARTIAL: leaves out %s (Kalshi could not be read)." % ", ".join(missing)) if missing else ""))
    return png(fig), cap


def chart_day_main(ctx, which):
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
    avg, navg = day_avg(led, day)
    if avg:
        if day == today:
            by_now = avg[0][1]
            for g, v in avg:
                if g > now - d0:
                    break
                by_now = v
            alab = "Average of the last %d days %s (%s by now)" % (navg, usd(avg[-1][1]), usd(by_now))
        else:
            alab = "Average of the %d days before %s" % (navg, usd(avg[-1][1]))
        ax.plot([etdt(d0 + g) for g, _v in avg], [v for _g, v in avg], color=ORANGE, lw=1.8, ls="--",
                label=alab, zorder=2)
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
    cap = ("%s: the day's money close by close, Kalshi's books, main account (pin + coin race). Orange dashes: the "
           "average day of the %d days before, on the same clock. Right axis: the same dollars as %% of the bank at "
           "the start of the ET day." % (label, AVG_DAYS))
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
    pct_words = "% of the bank each day (the bank at the start of that ET day)"

    def bank(d):
        return led.bank_at(et_day_start(d))
    if src == "days":
        # 2026-10-26: /days' words cover EVERY bot (operator: "add the percentage anywhere it applied"), so its
        # picture does too -- each day's money over all pots, as % of what all the pots held when it began
        # (botstats.day_pot, the /days table's own rule). The main account alone when botstats cannot be read.
        try:
            bs, pctx_, mrows, missing = all_day_markets(ctx)
        except Exception:                               # noqa: BLE001
            bs, mrows, missing = None, [], ["all"]
        if bs is not None and mrows and not missing:
            per = {}
            for d_, _t, v_, _b in mrows:
                per[d_] = per.get(d_, 0.0) + v_
            rows, d_ = [], min(per)
            while d_ <= today:
                rows.append((d_, per.get(d_, 0.0)))
                d_ = bs.shift_day(d_, 1)
            dep = bs.pot_for(pctx_, None, "all_time")[0]
            tot = sum(per.values())
            head = "Every bot, all time %s%s" % (usd(tot), (" (%s on the %s put in)" % (pctx(tot / dep, 2), usd(dep, False)))
                                                if dep else "")
            src_words = "Kalshi's books, every pot (every bot), every ET day"
            pct_words = "% of all pots each day (what they held when that ET day began)"

            def bank(d):                                # noqa: F811 -- all pots, not the main account
                return bs.day_pot(pctx_, None, d)
        else:
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
    lo = days[0]                                        # the % average reaches AVG_DAYS-1 days left of the picture
    for _ in range(AVG_DAYS - 1):
        lo = prev_day(lo)
    b0 = {d: bank(d) for d, _v in rows if d >= lo}
    b0s = [b0[d] for d in days]
    pct_by = {d: ((100.0 * v / b0[d]) if b0[d] else 0.0) for d, v in rows if d >= lo}
    avg_net = avg_by_day(dict(rows), days)
    avg_pct = avg_by_day(pct_by, days)
    n = 4 if winrate is not None else 3
    fig, axs = fig_new(n, 3.0 * n + 1.2, sharex=True)
    xs = _bars_by_day(axs[0], days, nets, usd)
    # the average line stops at yesterday: today's bar is half a day, and the last point then equals /today's
    # "average of the last 7 days"
    an = [avg_net.get(d) if d < today else None for d in days]
    ap = [avg_pct.get(d) if d < today else None for d in days]
    lan = next((a for a in reversed(an) if a is not None), None)
    lap = next((a for a in reversed(ap) if a is not None), None)
    if lan is not None:
        axs[0].plot([x for x, a in zip(xs, an) if a is not None], [a for a in an if a is not None], color=ORANGE,
                    lw=1.8, ls="--", zorder=4, label="%d-day average, to yesterday (%s a day)" % (AVG_DAYS, usd(lan)))
        legend(axs[0])
    money_axis(axs[0])
    axs[0].set_title("$ each ET day")
    pc = [(100.0 * v / b) if b else 0.0 for v, b in zip(nets, b0s)]
    _bars_by_day(axs[1], days, pc, lambda v: "%+.2f%%" % v)
    if lap is not None:
        axs[1].plot([x for x, a in zip(xs, ap) if a is not None], [a for a in ap if a is not None], color=ORANGE,
                    lw=1.8, ls="--", zorder=4, label="%d-day average, to yesterday (%+.2f%% a day)" % (AVG_DAYS, lap))
        legend(axs[1])
    pct_ticks(axs[1])
    axs[1].set_title(pct_words)
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
        w7x, w7v = [], []                               # won % of every market in that day and the 6 before it
        for x, d in zip(xs, days):
            span, e = [], d
            for _ in range(AVG_DAYS):
                if e < fl:
                    break
                span.extend(by.get(e, []))
                e = prev_day(e)
            st = pp.window_stats(span, {}) if span else None
            if st and st.get("win_c") is not None:
                w7x.append(x)
                w7v.append(100.0 * st["win_c"])
        if w7v:
            ax.plot(w7x, w7v, color=ORANGE, lw=1.8, ls="--", label="won %% over %d days (%.1f%% now)" % (AVG_DAYS, w7v[-1]),
                    zorder=2)
        pct_ticks(ax, signed=False)
        ax.set_title("Each day: won % of markets vs the break-even it needed")
        legend(ax)
    date_axis(axs[-1])
    headline(fig, head)
    cap = ("%s: %s; the last %d days drawn, the running total counts all of them. Top: each day's money; then the "
           "same day as %% of what it began with (orange dashes: the average of that day and the %d before it, "
           "drawn to yesterday); "
           "then the running total (right axis: %% of the money put in)%s." % (
               "/stats" if src == "stats" else "/days", src_words, len(days), AVG_DAYS - 1,
               "; bottom: won % of markets each day against the break-even win rate its prices needed"
               if winrate is not None else ""))
    return png(fig), cap


def chart_stats_main(ctx):
    """The old /stats picture: the main account only (pin bot + coin race, pinphone.markets_from since the first live
    day), with each day's won % of markets against its break-even. Drawn when botstats cannot be read."""
    return chart_days(ctx, "stats")


def chart_stats(ctx):
    """/stats (operator 10-26: "The command slash stats graph shows only pins bank. Perhaps every bank in different
    colors would be better."): EVERY bot's money from botstats (Kalshi's books, every pot), one colour a bot
    (BOT_COLOUR, the same as /losses, /bots and each bot's page):
      top     $ each ET day stacked by bot, gains up and losses down; the dark dot is the day's net over every bot;
      middle  that net as % of what all the pots held when the day began (botstats.day_pot, the /bots and /days base;
              a day whose pots are unknown is left out, never guessed), with its 7-day average;
      bottom  the running total: every bot together (dark, thick) and each big bot; then the bots too small to see
              on that scale, on their own; each key carries each bot's all-time $ (a stopped bot says so).
    The won % against break-even panel of the old picture is not drawn: the bots buy at very different prices (race
    legs near 50c, the pin bot and the ladder near 96-98c), so one won % over all of them follows the mix of bots
    that day, not how well any one did; each bot's own is on its page (/pin /fc /ladder /race /fx).
    The main account's picture (chart_stats_main) when botstats cannot be read."""
    try:
        bs, _c, prows, ok, pctx_, ms, missing = _all_markets(ctx)
    except Exception:                                   # noqa: BLE001 (no botstats: the main account's picture)
        return chart_stats_main(ctx) if ctx.get("ledger") is not None else None
    if not ms:
        return chart_stats_main(ctx) if ctx.get("ledger") is not None else None
    now = ctx["now"]
    today = bs.et_day(now)
    names = {n for n, _m in ms}
    bots = [b for b in BOT_ORDER if b in names] + sorted(names - set(BOT_ORDER))
    per = {}                                            # (ET day, bot) -> that bot's money that day
    for n, m in ms:
        per[(m["day"], n)] = per.get((m["day"], n), 0.0) + m["money"]
    first = min(m["day"] for _n, m in ms)
    days_all, d = [], first
    while d <= today:
        days_all.append(d)
        d = bs.shift_day(d, 1)
    cut = bs.et_day(now - WINDOW_DAYS * 86400)          # the picture shows the last WINDOW_DAYS; totals count all
    days = [d for d in days_all if d >= cut] or days_all
    acc = {b: 0.0 for b in bots}
    run = {b: {} for b in bots}
    for d in days_all:
        for b in bots:
            acc[b] += per.get((d, b), 0.0)
            run[b][d] = acc[b]
    life = {b: acc[b] for b in bots}
    total = sum(life.values())
    born = {b: min(m["day"] for n, m in ms if n == b) for b in bots}
    stopped = {b for b in bots if b in bs.SPEC and bot_stopped(bs, b, prows, ok)}

    def name(b):
        return BOT_SHORT.get(b, b) + (" (stopped)" if b in stopped else "")
    xs = [etdt(bs.day_start(d) + 43200) for d in days]
    nets = [sum(per.get((d, b), 0.0) for b in bots) for d in days]
    allv = [sum(run[b][d] for b in bots) for d in days]
    # a bot whose running total is small next to every bot's would be a flat line at $0: it gets a panel of its
    # own scale under the big ones
    big_span = max([abs(v) for v in allv] + [1.0])
    reach = {b: max([abs(run[b][d]) for d in days if d >= born[b]] + [0.0]) for b in bots}
    big = [b for b in bots if reach[b] >= 0.3 * big_span]
    small = [b for b in bots if b not in big and any(d >= born[b] for d in days)]
    n = 4 if small else 3
    fig, axs = fig_new(n, 14.4 if small else 11.6, ratios=[1.2, 0.8, 1.0, 1.0][:n], sharex=True)

    # top: each day's money, stacked by bot
    ax = axs[0]
    up, dn = [0.0] * len(days), [0.0] * len(days)
    for b in bots:
        v = [per.get((d, b), 0.0) for d in days]
        if not any(abs(x) > 0.004 for x in v):
            continue
        pv = [max(0.0, x) for x in v]
        nv = [min(0.0, x) for x in v]
        ax.bar(xs, pv, width=0.8, bottom=up, color=BOT_COLOUR.get(b, GREY), edgecolor=SURF, linewidth=0.5, zorder=3,
               label=BOT_SHORT.get(b, b))
        ax.bar(xs, nv, width=0.8, bottom=dn, color=BOT_COLOUR.get(b, GREY), edgecolor=SURF, linewidth=0.5, zorder=3)
        up = [a + x for a, x in zip(up, pv)]
        dn = [a + x for a, x in zip(dn, nv)]
    ax.scatter(xs, nets, s=16, color=INK, edgecolor=SURF, linewidth=0.8, zorder=5, label="net, every bot")
    zero_line(ax)
    hi, lo = max(up + [0.0]), min(dn + [0.0])
    span = max(hi - lo, 1.0)
    ax.set_ylim(lo - 0.08 * span, hi + 0.28 * span)     # headroom: the key, two rows
    note(ax, xs[-1], nets[-1], usd(nets[-1]), dy=8 if nets[-1] >= 0 else -8, ha="right", dx=4)
    money_axis(ax)
    ax.set_title("$ each ET day, by bot: gains up, losses down (dot = the day's net)")
    ax.legend(loc="upper left", fontsize=8.5, ncol=4, frameon=True, facecolor=SURF, edgecolor="none", framealpha=0.92,
              columnspacing=1.0, handlelength=1.2)

    # middle: the day's net as % of all pots when it began
    ax = axs[1]
    pot = {}
    lo_d = days[0]
    for _ in range(AVG_DAYS - 1):
        lo_d = bs.shift_day(lo_d, -1)
    for d in days_all:
        if d >= lo_d:
            pot[d] = bs.day_pot(pctx_, None, d) if not missing else None
    pct = {d: 100.0 * sum(per.get((d, b), 0.0) for b in bots) / pot[d] for d in pot if pot[d]}
    px = [x for x, d in zip(xs, days) if d in pct]
    pv = [pct[d] for d in days if d in pct]
    if pv:
        ax.bar(px, pv, width=0.8, color=ups_downs(pv), zorder=3)
        note(ax, px[-1], pv[-1], "%+.2f%%" % pv[-1], dy=6 if pv[-1] >= 0 else -6, ha="right", dx=4)
        ax_x, ax_v = [], []                             # the average of that day and the 6 before it (known days)
        for x, d in zip(xs, days):
            if d >= today:
                continue
            span_d, e = [], d
            for _ in range(AVG_DAYS):
                if e in pct:
                    span_d.append(pct[e])
                e = bs.shift_day(e, -1)
            if span_d:
                ax_x.append(x)
                ax_v.append(sum(span_d) / len(span_d))
        if ax_v:
            ax.plot(ax_x, ax_v, color=INK2, lw=1.6, ls="--", zorder=4,
                    label="%d-day average, to yesterday (%+.2f%% a day)" % (AVG_DAYS, ax_v[-1]))
            legend(ax)
    else:
        ax.text(0.5, 0.5, "what the pots held could not be worked out", transform=ax.transAxes, ha="center",
                va="center", color=MUTED, fontsize=10)
    zero_line(ax)
    pct_ticks(ax)
    ax.set_title("% of all pots each day (what they held when that ET day began)")

    # the running totals: every bot (dark) and the big bots; then the small ones on their own scale
    def lines(ax, which):
        vals = []
        for b in which:
            bx = [x for x, d in zip(xs, days) if d >= born[b]]
            by = [run[b][d] for d in days if d >= born[b]]
            if bx:
                ax.plot(bx, by, color=BOT_COLOUR.get(b, GREY), lw=2.0, zorder=3, label="%s %s" % (name(b), usd(life[b])))
                vals += by
        return vals
    ax = axs[2]
    vals = lines(ax, big)
    ax.plot(xs, allv, color=INK, lw=2.8, zorder=4, label="Every bot %s" % usd(total))
    note(ax, xs[-1], allv[-1], usd(allv[-1]), dx=-4, ha="right")
    zero_line(ax)
    lo_r, hi_r = min([0.0] + allv + vals), max([0.0] + allv + vals)
    span = max(hi_r - lo_r, 1.0)
    ax.set_ylim(lo_r - 0.06 * span, hi_r + 0.14 * span)
    money_axis(ax)
    dep = bs.pot_for(pctx_, None, "all_time")[0] if not missing else None
    pct_of_axis(ax, dep, "%% of the %s put in" % usd(dep, False) if dep else "")
    bign = ["the " + BOT_SHORT.get(b, b).lower() for b in big]
    ax.set_title("Running total: every bot together (dark)%s" % (
        (" and " + (", ".join(bign[:-1]) + " and " if len(bign) > 1 else "") + bign[-1]) if bign else ""))
    h, lab = ax.get_legend_handles_labels()
    ax.legend(h[-1:] + h[:-1], lab[-1:] + lab[:-1], loc="upper left", fontsize=9, frameon=True,
              facecolor=SURF, edgecolor="none", framealpha=0.92, handlelength=1.4)
    if small:
        ax = axs[3]
        vals = lines(ax, small)
        zero_line(ax)
        lo_r, hi_r = min([0.0] + vals), max([0.0] + vals)
        span = max(hi_r - lo_r, 1.0)
        ax.set_ylim(lo_r - 0.08 * span, hi_r + 0.42 * span)     # headroom: the key
        money_axis(ax)
        ax.set_title("Running total of the other bots, on their own scale")
        ax.legend(loc="upper left", fontsize=8.5, ncol=2, frameon=True, facecolor=SURF, edgecolor="none",
                  framealpha=0.92, columnspacing=1.0, handlelength=1.4)
    date_axis(axs[-1])
    headline(fig, "Every bot, all time %s%s" % (usd(total), (" (%s on the %s put in)" % (pctx(total / dep, 1), usd(dep, False)))
                                                if dep else ""))
    cap = ("/stats: every bot, every pot (Kalshi's books through botstats), one colour a bot; the last %d days drawn, "
           "the totals count every day since %s. Top: each ET day's money by bot, gains up and losses down; the dark "
           "dot is the day's net over every bot. Middle: that net as %% of what all the pots held when the day began "
           "(a day whose pots are unknown is left out); dashes: its %d-day average, to yesterday. Bottom: each bot's "
           "running total and every bot together. All time: %s.%s" % (
               len(days), first, AVG_DAYS, ", ".join("%s %s" % (name(b), usd(life[b])) for b in bots),
               (" PARTIAL: leaves out %s (Kalshi could not be read)." % ", ".join(missing)) if missing else ""))
    return png(fig), cap


def _account_series(bs, c, sub, now):
    """[(epoch, dollars)] for pot `sub`, or a tuple of pots added up (the FX taker's 5 + 4): money moved in
    (botstats.flows) + every settlement (botstats.market), hour by hour, worked forward from Kalshi's books; plus the
    pot now (botstats._pot_now) or why not, and each pot's part now (None for one pot). A pool-only pot
    (botstats.POT_POOL_ONLY: subaccount 4 = its pool 0) counts its own pool's money, cash and markets only."""
    subs = sub if isinstance(sub, tuple) else (sub,)
    led = c.get("ledgers") or {}
    sett = sorted((m["t"], m["money"]) for s in subs
                  for m in (bs.market(r) for r in bs.pot_rows((c.get("subs") or {}).get(s) or {}, s))
                  if m["t"] is not None)
    times = [t for t, _m in sett]
    cum, run = [], 0.0
    for _t, v in sett:
        run += v
        cum.append(run)
    flow_t = []
    if "0" in subs:
        for k in ("deposits", "withdrawals"):
            for r in led.get(k) or []:
                if bs.pinxfer.is_done(r) and bs.pinxfer.when(r) is not None:
                    flow_t.append(bs.pinxfer.when(r))
    for r in led.get("transfers") or []:
        t = bs._int(r.get("created_ts"))
        if t is not None and any(s in (str(r.get("to_subaccount")), str(r.get("from_subaccount"))) and bs.xfer_in_pot(r, s)
                                 for s in subs):
            flow_t.append(t)
    first = min(times[:1] + flow_t) if (times or flow_t) else None
    if first is None:
        return [], None, "nothing on Kalshi's books yet", None
    grid = list(range(max(int(first) - 1800, int(now - WINDOW_DAYS * 86400)), int(now), 3600)) + [now]
    pts = []
    for g in grid:
        k = bisect.bisect_right(times, g)
        pts.append((g, bs.flows(led, sub, None, g + 1e-6) + (cum[k - 1] if k else 0.0)))
    nows = [bs._pot_now(c, s, own=True) for s in subs]
    why = next((w for v, w in nows if v is None), None)
    v = None if why is not None else sum(v for v, _w in nows)
    return pts, v, why, ([v_ for v_, _w in nows] if len(subs) > 1 else None)


def chart_funds(ctx):
    bs, c, prows, ok = bs_load(ctx)
    now = ctx["now"]
    drawn, stopped = [], []
    groups = {}
    for b in bs.BOTS:
        groups.setdefault(bs.bot_subs(b), []).append(b)
    for key in sorted(groups, key=lambda k: bs.SUBS.index(k[0]) if k[0] in bs.SUBS else len(bs.SUBS)):
        bots = groups[key]
        live = [b for b in bots if not bot_stopped(bs, b, prows, ok)]
        if not live:
            stopped.append("%s (%s)" % (account_name(key).lower(), ", ".join(bs.SPEC[b]["label"].lower() for b in bots)))
            continue
        pts, v, why, each = _account_series(bs, c, key if len(key) > 1 else key[0], now)
        if pts:
            drawn.append((key, live, pts, v, why, each))
    for k, w in sorted((ctx.get("funds_what") or {}).items()):
        if str(k) not in bs.SUBS:
            ws = " ".join(w.values()) if isinstance(w, dict) else str(w)
            if "stopped" in ws:
                stopped.append("subaccount %s (%s)" % (k, ws.replace(" (stopped)", "")))
    if not drawn:
        return None
    fig, axs = fig_new(len(drawn), 2.7 * len(drawn) + 1.0, sharex=True)
    total, whole = 0.0, True
    for ax, (key, live, pts, v, why, each) in zip(axs, drawn):
        X = [etdt(t) for t, _y in pts]
        Y = [y for _t, y in pts]
        col = BOT_COLOUR.get(live[0], BLUE)             # the account's (first) bot's colour, as on /stats (10-26)
        ax.plot(X, Y, color=col, lw=2.0, zorder=3)
        ax.fill_between(X, Y, 0, color=col, alpha=0.08, lw=0)
        nowv = v if v is not None else Y[-1]
        total += nowv
        whole = whole and v is not None
        ax.scatter([X[-1]], [nowv], s=50, color=col, edgecolor=SURF, linewidth=1.5, zorder=5)
        note(ax, X[-1], nowv, usd(nowv, False), dx=-4, ha="right")
        lo = min(Y + [nowv])
        ax.set_ylim(bottom=min(0.0, lo))
        money_axis(ax, signed=False)
        if each:                                        # each pot's part, inside the panel (the title has no room)
            ax.text(0.01, 0.95, " + ".join("%s (%s) %s" % (POT_WHAT.get(k, "subaccount " + k), k, usd(x, False))
                                           for k, x in zip(key, each)),
                    transform=ax.transAxes, va="top", ha="left", fontsize=9.5, color=INK2, zorder=6,
                    bbox=dict(facecolor=SURF, edgecolor=GRID, boxstyle="round,pad=0.3"))
        ax.set_title("%s · %s: %s%s" % (account_name(key), " + ".join(bs.SPEC[b]["label"].lower() for b in live),
                                        usd(nowv, False), " now" if v is not None else " (from the books)"),
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
    rule for one day (so a mid-day top-up only ever makes that day's % smaller). None when it cannot be known.
    It IS botstats.day_pot, which also falls back to the last good read when the latest one failed."""
    if any((pctx_.get("subs") or {}).get(s) is None for s in (sub if isinstance(sub, tuple) else (sub,))):
        return None
    return bs.day_pot(pctx_, sub, day)


def pace_curves(bs, pctx_, sub, ms, today, now):
    """{'today': [(hour, cum %)], 'yesterday': [...], 'avg7': [...] (the mean of the PACE_DAYS days before today,
    on a 15-minute grid; days before the bot's first market are left out), 'n7': days averaged, 'unit': '%'}. A day
    whose base is unknown is left out. When TODAY's base is unknown (no good balance read at all), every curve is
    in dollars instead ('unit': '$') -- the panel is never left blank (operator 10-23: 'the top most one was blank')."""
    dollars = day_base(bs, pctx_, sub, today) is None

    def curve(day):
        base = 100.0 if dollars else day_base(bs, pctx_, sub, day)       # 100 * cum / 100 = the dollars themselves
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
    out = {"today": curve(today), "yesterday": curve(bs.shift_day(today, -1)), "avg7": None, "n7": 0,
           "unit": "$" if dollars else "%"}
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
    """Today (blue, to now) over yesterday (grey) and the 7-day average day (orange dashes), as % of the bank --
    or in dollars when the bank could not be read (pc['unit'] == '$')."""
    T = mpl()["ticker"]
    dollars = pc.get("unit") == "$"

    def f(v):
        return usd(v) if dollars else pctx(v / 100.0, 2)
    if pc["avg7"]:
        ax.plot([h for h, _ in pc["avg7"]], [v for _, v in pc["avg7"]], color=ORANGE, lw=1.8, ls="--", zorder=2,
                label="average of the last %d days (%s by now)" % (pc["n7"], f(_at_h(pc["avg7"], now_h))))
    if pc["yesterday"]:
        ax.step([h for h, _ in pc["yesterday"]], [v for _, v in pc["yesterday"]], where="post", color=GREY, lw=1.6,
                zorder=2, label="yesterday %s (%s by now)" % (f(pc["yesterday"][-1][1]), f(_at_h(pc["yesterday"], now_h))))
    if pc["today"]:
        ax.step([h for h, _ in pc["today"]], [v for _, v in pc["today"]], where="post", color=BLUE, lw=2.4, zorder=3,
                label="today %s" % f(pc["today"][-1][1]))
        note(ax, pc["today"][-1][0], pc["today"][-1][1], f(pc["today"][-1][1]), dx=-4, ha="right")
    if dollars:
        goal = None                                       # the goal is a % of the bank: nothing to draw it against
    if goal is not None:
        ax.plot([0, 24], [0, goal], color=MUTED, lw=1.0, ls=":", zorder=1, label="goal %s a day, spread evenly" % pctx(goal / 100.0, 1, False))
    ax.axvline(now_h, color=AXIS, lw=1.0, ls=":", zorder=1)
    zero_line(ax)
    ax.set_xlim(0, 24)
    ax.xaxis.set_major_locator(T.FixedLocator(list(range(0, 25, 3))))
    ax.xaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: "%d %s" % ((int(v) % 12) or 12, "AM" if int(v) % 24 < 12 else "PM")))
    if dollars:
        money_axis(ax)
        ax.set_title("Today's pace in dollars, by ET clock (its bank could not be read for the %)")
    else:
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
    subs = bs.bot_subs(name)                            # the FX taker: 5 + 4, one picture
    sub = subs if len(subs) > 1 else subs[0]
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
    ax.step(X, R, where="post", color=BOT_COLOUR.get(name, BLUE), lw=2.0, zorder=3)    # its /stats colour (10-26)
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
    pct_of_axis(ax, base, (("%% of the %s's %s put in" % (bs.SUB_NAME[sub], usd(base, False))) if len(subs) == 1 else
                           ("%% of the %s put into %s" % (usd(base, False), bs.sub_name(sub)))) if base else "")
    ax.set_title("Running total, market by market (Kalshi's books, %s)" % bs.sub_name(sub))
    ax = axs[1]
    # a rolling rate is drawn only where its window is full (n markets / races behind it)
    if name == "race":
        races = _race_rows(bs, c)
        n = min(ROLL, max(5, len(races) // 4))
        rr = roll([100.0 if w else 0.0 for _t, _v, w, _tie in races], n)
        j0 = max(n - 1, next((i for i, r in enumerate(races) if r[0] >= cut), len(races)))
        ax.plot([etdt(r[0]) for r in races[j0:]], rr[j0:], color=BOT_COLOUR.get(name, BLUE), lw=2.0,
                label="won %% of the last %d races" % n, zorder=3)
        what = "races (a tie counts as not won)"
    else:
        n = min(ROLL, max(5, len(ms) // 4))
        j0 = max(n - 1, i0)
        ax.plot(Xall[j0:], roll([100.0 if m["money"] > 0.004 else 0.0 for m in ms], n)[j0:], color=BOT_COLOUR.get(name, BLUE),
                lw=2.0, label="won %% of the last %d markets" % n, zorder=3)
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
               label, "leg" if name == "race" else "market", bs.sub_name(sub), WINDOW_DAYS))
    return png(fig), cap


LOSS_WEEKS = 8                          # /losses: the weekly bars
LOSS_LANE_DAYS = 30                     # /losses: the timeline


def _week_of(day):
    """'2026-10-28' -> the Monday that starts its ET week, '2026-10-26'."""
    d = _dt.date.fromisoformat(day)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def chart_losses(ctx):
    """/losses (operator 10-26: "That losses chart is pretty bad it's really hard to notice any trends or anything
    meaningful and it's also just hard to see what's what. New kind of chart/graph"). Every bot's losses from
    all_losses (the words' own source), two ways:
      top     each ET week (Monday-Sunday), the last LOSS_WEEKS: what the winning markets made (green, up) against
              what the losing ones cost (down, stacked, one colour a bot) and the week's loss total -- is losing
              growing, which bot does it, and how big it is next to what was won;
      bottom  every loss of the last LOSS_LANE_DAYS days on its own bot's row, the circle's AREA = the dollars, the
              biggest named; each row's label carries its count and total -- what happened when, at a glance.
    The main account's losing closes (chart_losses_main) when botstats cannot be read."""
    try:
        bs, rows, per, missing = all_losses(ctx)
    except Exception:                                   # noqa: BLE001 -- no botstats: the main account's picture
        return chart_losses_main(ctx) if ctx.get("ledger") is not None else None
    rows = [r for r in rows if r["t"] and r["day"]]
    if not rows:
        return None
    now = ctx["now"]
    today = bs.et_day(now)
    order = [b for b in tuple(bs.BOTS) + ("other",) if b in per]
    first = min([r["day"] for r in rows] + [d for p in per.values() for d in p["won_days"]])
    weeks = [_week_of(today)]
    while len(weeks) < LOSS_WEEKS:
        w = (_dt.date.fromisoformat(weeks[0]) - _dt.timedelta(days=7)).isoformat()
        if w < _week_of(first):
            break
        weeks.insert(0, w)
    wi = {w: k for k, w in enumerate(weeks)}
    won = [0.0] * len(weeks)
    lost = {b: [0.0] * len(weeks) for b in order}
    nlost = [0] * len(weeks)
    for b in order:
        for d, v in per[b]["won_days"].items():
            k = wi.get(_week_of(d))
            if k is not None:
                won[k] += v
    for r in rows:
        k = wi.get(_week_of(r["day"]))
        if k is not None:
            lost[r["bot"]][k] += r["money"]
            nlost[k] += 1
    fig, axs = fig_new(2, 9.4, ratios=[1.15, 1.0])
    ax = axs[0]
    xs = list(range(len(weeks)))
    ax.bar(xs, won, width=0.62, color=UP, alpha=0.45, zorder=3, label="won")
    base = [0.0] * len(weeks)
    for b in order:
        if not any(lost[b]):
            continue
        ax.bar(xs, lost[b], width=0.62, bottom=base, color=BOT_COLOUR.get(b, GREY), zorder=3,
               label=BOT_SHORT.get(b, b))
        base = [x + y for x, y in zip(base, lost[b])]
    zero_line(ax)
    span = max(max(won or [0]), -min(base or [0]), 1.0)
    for k in xs:
        if nlost[k]:
            ax.annotate("%s\n%d lost" % (usd(base[k]), nlost[k]), (k, base[k]), xytext=(0, -3),
                        textcoords="offset points", ha="center", va="top", fontsize=8.5, color=DOWN, fontweight="bold")
        if won[k] > 0.005:
            ax.annotate(usd(won[k]), (k, won[k]), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                        fontsize=8.5, color=INK2)
    ax.set_ylim(min(base or [0]) - 0.32 * span, max(won or [0]) + 0.45 * span)      # headroom: the key, 2 rows
    ax.set_xticks(xs)
    ax.set_xticklabels([(lambda d: d.strftime("%b ") + str(d.day))(_dt.date.fromisoformat(w))
                        + ("\nso far" if k == len(weeks) - 1 else "") for k, w in enumerate(weeks)], fontsize=9.5)
    ax.grid(False, axis="x")
    money_axis(ax)
    ax.set_title("Each week (Mon-Sun ET): won by every bot, up; lost, down, by bot")
    ax.legend(loc="upper center", fontsize=8.5, ncol=4, frameon=True, facecolor=SURF, edgecolor="none", framealpha=0.92,
              columnspacing=1.0, handlelength=1.2)

    ax = axs[1]
    t_lo = now - LOSS_LANE_DAYS * 86400
    day_lo = bs.et_day(t_lo)
    lane = [r for r in rows if r["t"] >= t_lo]
    active = [b for b in order if any(d >= day_lo for d in per[b]["won_days"]) or any(r["bot"] == b for r in lane)]
    active = active or order
    yi = {b: k for k, b in enumerate(active)}
    biggest = max((-r["money"] for r in lane), default=1.0) or 1.0
    for b in active:
        rs = [r for r in lane if r["bot"] == b]
        if rs:
            ax.scatter([etdt(r["t"]) for r in rs], [yi[b]] * len(rs), s=[24 + 520 * (-r["money"]) / biggest for r in rs],
                       color=BOT_COLOUR.get(b, GREY), alpha=0.75, edgecolor=SURF, linewidth=0.8, zorder=4)
    big = sorted(sorted(lane, key=lambda r: r["money"])[:4], key=lambda r: r["t"])     # the 4 biggest, named,
    for k, r in enumerate(big):                                                      # above / below in turn
        what = r["what"].split(" ")[0] if r["bot"] != "race" else r["what"].replace("race ", "").split(" ")[0]
        up = k % 2 == 0
        ax.annotate("%s %s" % (what, usd(r["money"])), (etdt(r["t"]), yi[r["bot"]]), xytext=(0, 11 if up else -11),
                    textcoords="offset points", ha="center", va="bottom" if up else "top", fontsize=8.5, color=INK,
                    zorder=6)
    labels = []
    for b in active:
        rs = [r for r in lane if r["bot"] == b]
        labels.append("%s\n%s" % (BOT_SHORT.get(b, b), ("%d lost, %s" % (len(rs), usd(sum(r["money"] for r in rs))))
                                  if rs else "no losses"))
    ax.set_yticks(range(len(active)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_ylim(len(active) - 0.4, -0.75)                                    # first bot on top
    ax.set_xlim(etdt(t_lo), etdt(now + 0.6 * 86400))
    ax.grid(True, axis="x", color=GRID, lw=0.6)
    ax.grid(False, axis="y")
    for k in range(len(active)):
        ax.axhline(k, color=GRID, lw=0.6, zorder=1)
    date_axis(ax, LOSS_LANE_DAYS)
    ax.set_title("Every loss, last %d days (circle size = dollars)" % LOSS_LANE_DAYS)

    d7 = bs.shift_day(today, -6)                       # the last 7 ET days, today in -- the words' '7d' count
    d35 = bs.shift_day(today, -34)
    week = [r for r in rows if r["day"] >= d7]
    before = [r for r in rows if d35 <= r["day"] < d7]
    nb = min(4, max(0, sum(1 for k in range(7, 35) if bs.shift_day(today, -k) >= first) // 7))
    head = "Last 7 days: %s lost in %d market%s" % (usd(sum(r["money"] for r in week)), len(week),
                                                    "" if len(week) == 1 else "s")
    if nb >= 1:
        head += " · %s a week before" % usd(sum(r["money"] for r in before) / nb)
    headline(fig, head)
    cap = ("Losses, every bot (Kalshi's books, every pot; colour = the bot). Top: each ET week's winning markets (green) "
           "against its losing ones (down, by bot), the newest week so far. Bottom: each loss of the last %d days on "
           "its bot's row, circle area = dollars. Last 7 days = today and the 6 ET days before (as /losses counts "
           "them); 'a week before' = the average of the 4 weeks before those.%s" % (
               LOSS_LANE_DAYS, (" Left out (Kalshi could not be read): " + ", ".join(missing) + ".") if missing else ""))
    return png(fig), cap


def chart_losses_main(ctx):
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
                              (None, INK, "not settled")):           # not orange: the coin race's colour
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
    headline(fig, "Pin bot insurance: %s all time on %d hedged markets" % (usd(tot), len(hm)))
    cap = ("The pin bot's insurance. Top: each hedged market's other side, on its own (pinphone.markets_from's "
           "hedge_pnl, Kalshi's books, main account), added up. Bottom: every executed hedge (the pin bot's records) "
           "and its market's net, by verdict.")
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
                   label="the pin bot's own bank reads")
    mv = [e for e in led.external if e.get("t") and e["t"] >= t0 and abs(float(e.get("amount") or 0)) >= Ledger.TRANSFER_MIN]
    for e in mv:
        ax.axvline(etdt(e["t"]), color=INK2, lw=1.2, ls=":", zorder=2)
    if mv:
        ax.plot([], [], color=INK2, lw=1.2, ls=":", label="money moved in or out")
    note(ax, X[-1], Y[-1], usd(Y[-1], False), dx=-4, ha="right")
    money_axis(ax, signed=False)
    date_axis(ax, 7)
    ax.set_title("Main account (pin bot + coin race), hour by hour, last 7 days")
    if reads or mv:
        legend(ax)
    headline(fig, "Bank %s · 7 days ago %s" % (usd(Y[-1], False), usd(Y[0], False)))
    cap = ("The main account's bank (pin bot + coin race) over the last 7 days: the pin bot's last bank read plus every settlement since "
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
                   s=[min(220, 18 + 4 * float(o.get("filled") or 0)) for o, _p in g], color=BOT_COLOUR["pin"], alpha=0.85,
                   edgecolor=SURF, linewidth=1.0, zorder=4, label="filled: %d (dot size = contracts)" % len(got))
    z = [(o, p) for o, p in zero if p is not None]
    if z:                                               # dark, not orange: orange is the coin race's colour (10-26)
        ax.scatter([etdt(o["t"]) for o, _p in z], [p for _o, p in z], marker="x", s=40, color=INK, linewidth=1.8,
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
    headline(fig, "Pin bot orders today: %d · %d filled · %d filled nothing" % (len(rows), len(got), len(zero)))
    cap = ("Today's orders from the pin bot's own records (main account): what it paid, and the ones that lost the "
           "race. Pin bot only.")
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
                   label="a quarter-hour the pin bot bought")
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
    cap = ("The last %d quarter-hours from the pin bot's close summaries (as /market reads them); the dashed and dotted "
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
    if kind == "stats":
        return chart_stats(ctx)
    if kind == "days":
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
    today = et_day(now)
    avg, navg = day_avg(led, today)
    nets = dict(ledger_days(led))
    want, d = [], today
    for _ in range(AVG_DAYS):
        d = prev_day(d)
        want.append(nets.get(d, 0.0))
    ck(navg == AVG_DAYS and len(avg) == 97 and abs(avg[-1][1] - sum(want) / AVG_DAYS) < 1e-9 and avg[0][1] == 0.0,
       "/today's 7-day line: the %d days before today, ends at their mean day %s (= the ledger's own day totals)"
       % (navg, usd(avg[-1][1] if avg else None)))
    ab = avg_by_day({"2026-10-10": 7.0, "2026-10-12": 14.0}, ["2026-10-10", "2026-10-12", "2026-10-20"])
    ck(ab == {"2026-10-10": 7.0, "2026-10-12": 7.0, "2026-10-20": 0.0},
       "/days' 7-day line: a gap day counts $0, days before the first are left out: %s" % ab)
    ck(day_avg(Ledger(results=tempfile.gettempdir()), today) == ([], 0), "/today: nothing on the books -> no 7-day line")
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
            class _NoBS:                                # botstats unreadable: /stats falls back to the main account
                def __getattr__(self, k):
                    if k == "_bs":
                        raise RuntimeError("botstats cannot be read (planted)")
                    return getattr(PP, k)
            ctx2 = {"now": now, "ledger": led, "pp": _NoBS()}
            for kind in ("stats", "hedges"):
                got = build(kind, ctx2)
                ck(is_png(got) and (kind != "stats" or "main account" in got[1]),
                   "%s: a PNG from pinphone.markets_from / window_stats (%d KB)%s" % (
                       kind, len(got[0]) // 1024 if got else 0,
                       "; botstats unreadable -> the main account's picture" if kind == "stats" else ""))
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
            for sub, n in (("0", 300), ("1", 40), ("2", 60), ("3", 20), ("4", 12), ("5", 30)):
                r = {}
                for k in range(n):
                    t = now - k * 4000
                    tk = ("KXBTC15M-26OCT%02d%02d%02d-%02d" % (18, k % 24, 0, k % 60)) if sub == "0" else "KXX-%s-%d" % (sub, k)
                    if sub == "4":                       # the currency pairs; its first row is the old reward test's
                        tk = "KXUSDJPY15M-26OCT18%04d-30" % k if k else "KXBTC15M-26OCT180000-00"
                    if sub == "5":
                        tk = "KXGOLD15M-26OCT18%04d-45" % k
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
                                                          "exchange_index": BS.SUB_POOL[str(s)],
                                                          "created_ts": int(now - 15 * 86400)} for s in (1, 2, 3, 4, 5)]
                                           + [{"amount_cents": 5500, "from_subaccount": 0, "to_subaccount": 4, "exchange_index": 2,
                                               "created_ts": int(now - 18 * 86400)}],
                                           "subaccount_balances": [{"subaccount_number": int(s), "exchange_index": BS.SUB_POOL[s],
                                                                    "balance": 100.0} for s in BS.SUBS]}}
            procs = [(1, "x", "python research/pinrun.py --live"), (2, "x", "python research/pinracearm.py --live"),
                     (3, "x", "python research/forecaster_live.py --live"), (4, "x", "python research/ladder_live.py --live")]
            BS._load = lambda now_, getter, procs_: (c, BS._norm_procs(procs), True)
            ctx3 = {"now": now, "pp": PP, "funds_what": {4: {0: "FX taker: the 5 currency pairs", 2: "coin-race reward test (stopped)"}}}
            got = build("funds", ctx3)
            ck(is_png(got) and "subaccount 3 (weather dip-seller)" in got[1] and "subaccounts 5 + 4 (fx taker)" in got[1]
               and "4 ()" not in got[1],
               "/funds: a PNG of the running accounts; the stopped weather account and the stopped FX taker's two pots are "
               "named, not drawn: %s" % (got[1] if got else None))
            ck(build("bot:fx", ctx3) is None, "/fx: not in the process table -> no picture")
            procs.append((5, "x", "python research/cleanroom/fxtake_live.py --subaccount 5 --fx-subaccount 4 --live"))
            got = build("funds", ctx3)
            _pts, _v, _why, _each = _account_series(BS, c, ("5", "4"), now)
            _won = sum(BS.market(r_)["money"] for s_ in ("4", "5") for r_ in c["subs"][s_]["rows"].values()
                       if not r_["ticker"].startswith("KXBTC"))
            ck(is_png(got) and "fx taker" not in got[1] and _why is None and _each == [100.0, 100.0] and _v == 200.0
               and abs(_pts[-1][1] - (200.0 + _won)) < 1e-6,
               "/funds with the FX taker running: ONE panel for its two pots, $200 now = $100 + $100; its line = the $200 "
               "moved into 5 and 4's pool 0 + its own markets (the $55 moved into 4's pool 2 and the reward-test leg "
               "left out): %r" % (((_pts[-1][1] if _pts else None), _v, _each, _why),))
            ck(kind_of("/fx") == "bot:fx" and is_png(build("bot:fx", ctx3)), "/fx: a PNG of the FX taker over both pots")
            _bsl, _lrows, _lper, _lmiss = all_losses(ctx3)
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
            _bs3, _p3, _rows3, _miss3 = all_day_markets(ctx3)
            _want = round(sum(v for d_, _t, v, _b in _rows3 if d_ == et_day(now)), 4)
            got = build("today", ctx3)
            ck(is_png(got) and "every bot's money" in got[1] and not _miss3
               and {b for _d, _t, _v, b in _rows3} >= {"pin", "race", "forecaster", "ladder"},
               "/today from botstats: every pot's markets (pin, race, forecaster, ladder), not the main account only; "
               "today %s" % usd(_want))
            ck(abs(_want - sum(BS._money_block(BS._load(now, None, None)[0], b_, et_day(now), _p3)["today"]["money"]
                               for b_ in tuple(BS.BOTS) + ("other",))) < 1e-6,
               "/today's all-bots total = the sum of every bot's botstats 'today' (the /bots number)")
            _each = {}
            for d_, _t, v, b_ in _rows3:
                if d_ == et_day(now):
                    _each[b_] = _each.get(b_, 0.0) + v
            ck(all(("%s %s" % (BOT_SHORT[b_], usd(v))) in got[1] for b_, v in _each.items()) and "named by its bot" in got[1],
               "/today (10-26): each bot's money that day is said (%s) and the losing markets are named by bot"
               % ", ".join("%s %s" % (b_, usd(v)) for b_, v in sorted(_each.items())))
            ck(is_png(build("yesterday", ctx3)), "/yesterday from botstats: a PNG")

            # /stats (10-26): every bot's money, one colour a bot. A bot with only LOSSES still draws (planted: every
            # weather market lost): its colour is on the picture, and none of it when it has no market at all
            import matplotlib.image as _mi

            def _px(png_, hexc):
                a_ = _mi.imread(io.BytesIO(png_))[:, :, :3]
                want_ = [int(hexc[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
                return int((abs(a_ - want_) < 0.02).all(axis=2).sum())
            sv_w = c["subs"]["3"]["rows"]
            try:
                c["subs"]["3"]["rows"] = {k_: dict(r_, market_result="no", revenue=0, value=0) for k_, r_ in sv_w.items()}
                _r4 = all_day_markets(ctx3)[2]
                _wx = sum(v for _d, _t, v, b_ in _r4 if b_ == "weather")
                got = build("stats", ctx3)
                n_with = _px(got[0], BOT_COLOUR["weather"]) if is_png(got) else 0
                c["subs"]["3"]["rows"] = {}
                got0 = build("stats", ctx3)
                n_without = _px(got0[0], BOT_COLOUR["weather"]) if is_png(got0) else -1
            finally:
                c["subs"]["3"]["rows"] = sv_w
            ck(is_png(got) and "every bot, every pot" in got[1] and _wx < 0
               and all(v < 0 for _d, _t, v, b_ in _r4 if b_ == "weather")
               and ("Weather (stopped) %s" % usd(_wx)) in got[1]
               and all(BOT_SHORT[b_] in got[1] for b_ in ("pin", "race", "forecaster", "ladder", "fx"))
               and n_with > 400 and 0 <= n_without < 30,
               "/stats (10-26): every bot, every pot, one colour a bot; the weather bot with ONLY losses (%s) draws "
               "(%d px of its colour; %d with no market) and is named stopped: %r" % (usd(_wx), n_with, n_without,
                                                                                    got[1][:90] if got else None))
            ck(is_png(got0) and "Weather" not in got0[1], "/stats: a bot with no market at all is neither drawn nor named")
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
    import colorsys

    def _hs(hexc):
        h_, s_, _v = colorsys.rgb_to_hsv(*(int(hexc[i:i + 2], 16) / 255.0 for i in (1, 3, 5)))
        return 360.0 * h_, s_
    hs = {b: _hs(x) for b, x in BOT_COLOUR.items()}
    ck(len(set(BOT_COLOUR.values())) == len(BOT_COLOUR) == len(BOT_ORDER) and set(BOT_ORDER) == set(BOT_SHORT)
       and all(s_ < 0.25 or (min(h_, 360.0 - h_) >= 20 and abs(h_ - 120.0) >= 40) for h_, s_ in hs.values()),
       "one colour a bot, none of them the red or green of a loss or gain: %s"
       % ", ".join("%s %.0f deg" % (b, h_) for b, (h_, _s) in hs.items()))
    print("tgcharts selftest: OK (matplotlib %s)" % mpl()["version"])


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
