"""base.py -- what every picture shares: matplotlib on first use, the figure, the PNG, the axes helpers and the palette.

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py. The per-bot names and colours (BOT_SHORT,
BOT_COLOUR, BOT_ORDER) and the account names (ACCOUNT_NAME, POT_WHAT) now come from the registry (research/bots);
bots/tests/test_registry.py proved them equal to tgcharts' hand-kept tables first.

RULES (tgcharts, unchanged)
  * matplotlib (Agg, no pyplot, no window) is imported on first use (mpl()). Missing -> pinphone sends words only.
    One BLAS thread (OPENBLAS_NUM_THREADS ...=1 unless already set): the server is a 4 GB t3.medium (10-26).
  * One measure per axis. A right-hand axis is only ever the SAME numbers in other units (dollars as a % of one
    fixed base), never a second measure.
  * One colour a bot, the same in every picture that splits by bot; green and red mean gain and loss, so no bot is
    either (operator 10-26: "every bank in different colors").
"""
import datetime as _dt
import io
import os
import sys

_RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RESEARCH not in sys.path:
    sys.path.insert(0, _RESEARCH)
import pindesk                                                       # noqa: E402
import bots                                                          # noqa: E402
from botdata.fmt import usd_chart as usd                             # noqa: E402,F401  (tgcharts.usd, verbatim)
from botdata.series import WINDOW_DAYS                               # noqa: E402,F401

W_IN, DPI = 7.2, 150                    # 1080 px wide: a phone screen's width, no scaling by Telegram
MAX_BYTES = 2_000_000                   # Telegram allows 10 MB a photo; a chart over 2 MB is a bug
STALE_S = 120                           # a picture whose turn comes later than this is dropped, not sent
ROLL = 50                               # win rate over the last ROLL markets (races)

# colours (the dataviz reference palette, light surface)
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#b4b2a9"
# the 30-day average line (2026-10-29): a cool slate, muted (saturation under 0.25, so it reads as a grey, never as the
# pin bot's blue), drawn dash-dot; not red or green (money) and not a BOT_COLOUR
AVG30 = "#6e7f8d"
UP, DOWN = "#0ca30c", "#d03b3b"
UP_T, DOWN_T, MID_T = "#d7efd7", "#f6d9d9", "#efeee9"

# One name and one colour a bot (and 'earlier' / 'other'), from the registry: bots/<name>.py short= and colour=. The
# running bots pass the dataviz palette check on every pair, colour-blind included (validate_palette.js --pairs all).
BOT_SHORT = bots.BOT_SHORT
BOT_COLOUR = bots.BOT_COLOUR
BOT_ORDER = bots.BOT_ORDER
ACCOUNT_NAME = bots.ACCOUNT_NAME        # '0' -> 'Main account', '3' -> 'Subaccount 3'
POT_WHAT = bots.POT_WHAT                # a bot with two pots names each one's part (the FX taker: currencies, commodities)


def account_name(key):
    """'Main account' / 'Subaccount 1' for one pot, 'Subaccounts 5 + 4' for a bot's pots (a tuple)."""
    if len(key) == 1:
        return ACCOUNT_NAME.get(key[0], "Subaccount %s" % key[0])
    return "Subaccounts " + " + ".join(key)


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


# ---- words and numbers (the phone's own money style: sign first, thousands; usd = botdata.fmt.usd_chart) -------------
def pctx(x, digits=1, signed=True):
    if x is None:
        return "?"
    return ("%+.*f%%" if signed else "%.*f%%") % (digits, 100.0 * x)


def etdt(e):
    """epoch -> a naive datetime on the ET clock (pindesk's offset, so DST is the same as the words')."""
    return _dt.datetime(1970, 1, 1) + _dt.timedelta(seconds=float(e) + pindesk.et_offset(e))


def et_short(e, fmt="%I:%M %p"):
    """pindesk.et_str: '3:15 PM' (or `fmt`), no 'ET'. tgcharts called it et_clock, a name botstats.et_clock ('Sep 30
    12:15 AM ET') also has for a different function; renamed here (step 8), tgcharts.et_clock still answers."""
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


def wrap(text, width, sep=" · "):
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
