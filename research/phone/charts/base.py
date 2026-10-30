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

THE LAYOUT ENGINE (10-30; the operator: "ladder chart is 0-800, it counts by twos and starts somewhere a little under
800 ... Make it a fix that applies to this chart and any future ones"). Every axis of every picture goes through it;
tests/test_layout_rules.py fails a chart module that sets limits, ticks, locators or formatters itself, and base.audit
checks every drawn picture (the selftest; a golden replay with KALS_CHART_STRICT=1 raises on a broken rule).

  value axes   value_axis(ax, ys, unit='$'|'%'|'c'|'', kind='balance'|'pnl'|'level', xs=, move=, refs=, room_top=,
               room_bottom=, floor=, cap=, axis='y'|'x')   (money_axis = unit '$', kind 'pnl' by default; pct_axis = '%')
                 * the scale comes from the data's OWN behaviour: its range over what is drawn, padded PAD a side, and
                   its typical move (typical_move: the mean absolute change a day, an hour for a day's picture, or the
                   `move` given) -- the smallest range drawn is three typical moves (a flat line stays flat), and the
                   unlabelled minor grid is spaced one typical move (a $3-a-day bot on an $800 pot gets $5 lines under
                   $20 ticks; the pin bot's $30 days get $50 lines under $200 ticks)
                 * 'balance' (a bank, a pot): zoomed to the money, $0 only when the data come within NEAR_ZERO of it;
                   'pnl' (money / % made): 0 always shown, with the zero line; 'level' (win rate, share, price): zoomed
                   inside floor..cap
                 * ticks: 1 / 2 / 2.5 / 5 x 10^n, TICKS_MIN..TICKS_MAX of them; labels with thousands separators and
                   only the decimals the step needs ($825, $1,360, $50.5, $0.10); never an offset or 1e6 (rcParams too)
                 * refs: numbers that must fit, or ref(y, label, optional=True) lines (break-even, a goal, a stop line):
                   an optional one too far from the data is left off and its words come back in ['far'] for a note
  time axes    time_axis(ax, x0, x1 | xs=, pad=, pad_days=, clock=False, fixed=False): the panel covers its OWN span
               (+ pad), ticks fit it (hours for a day, 6/12-hourly for a few days, days for a week, Mondays for weeks,
               months beyond), ET. Panels share a time axis (fig_new(sharex=True)) only when they cover the same span;
               otherwise each panel gets its own. clock_axis(ax): a 12 AM..12 AM pace in hours. category_axis(ax,
               labels): named slots. no_axis(ax): an axis that carries no numbers. pct_of_axis(ax, base, label): the
               same dollars as % of one base on the right, its ticks the engine's.
  marks        mark_last (dot + bold value), annotate_change (the change over what is drawn, '$729.56 -> $825.16 ·
               +$95.60 (+13.1%) since Sep 28', low / high, extra lines, in the emptiest corner), mark_high_low,
               corner_box / free_corner (a key takes a corner the words and the data left free), ref / draw_ref,
               shade (a stretch of time: a pause, quiet hours), mark_empty (a panel with nothing yet says why).
  A NEW CHART: fig_new -> draw the series -> value_axis/money_axis for each panel's values (all of them, as ys) ->
  time_axis (or clock_axis / category_axis) -> mark_last / annotate_change -> png(fig). Nothing else touches the axes.
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
            "text.parse_math": False,                # "$" is money here, never TeX
            # 10-30 (operator: "ladder chart is 0-800, it counts by twos and starts somewhere a little under 800"):
            # never an offset ("+7.9e2") or scientific tick label; every axis prints the plain number
            "axes.formatter.useoffset": False, "axes.formatter.limits": (-9, 9)})
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
    out = buf.getvalue()
    _check(fig, len(out))                               # the layout rules (only when STRICT / AUDIT: the tests)
    fig.clear()
    return out


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


# ==== THE LAYOUT ENGINE (10-30) ========================================================================================
# Every axis of every picture goes through here (tests/test_layout_rules.py fails a chart module that sets limits,
# ticks, locators or formatters itself). See the module docstring for the rules and the API.
NICE = (1.0, 2.0, 2.5, 5.0)             # tick steps: these x 10^n
TICKS_MIN, TICKS_MAX, TICKS_GOAL = 4, 7, 5.5
PAD = 0.06                              # each end of a value axis: this share of the data's range
NEAR_ZERO = 0.35                        # a balance axis shows $0 only when the data come this close (share of range)
MIN_FILL = 0.6                          # the data (and its reference lines) fill at least this share of an axis
PNG_LIMIT = 300_000                     # a phone picture over this many bytes is a bug (rules check)
STRICT = os.environ.get("KALS_CHART_STRICT") == "1"    # the golden fixture check: a broken rule raises
AUDIT = None                            # a list: png() appends every broken rule to it (the selftest)


class ChartRuleError(AssertionError):
    pass


def _decimals(step):
    """The decimals a tick step needs: 25 -> 0, 2.5 -> 1, 0.25 -> 2."""
    for d in range(0, 7):
        if abs(round(step, d) - step) < 1e-9 * max(1.0, abs(step)):
            return d
    return 6


def _n_ticks(lo, hi, step):
    import math
    return int(math.floor(hi / step + 1e-9) - math.ceil(lo / step - 1e-9) + 1)


def nice_step(lo, hi, integer=False):
    """The tick step for [lo, hi]: 1, 2, 2.5 or 5 x 10^n giving TICKS_MIN..TICKS_MAX ticks, nearest TICKS_GOAL;
    a fractional 2.5 (0.25, 2.5) only when nothing else fits (a quarter of a dollar reads worse than a half)."""
    import math
    span = max(hi - lo, 1e-12)
    e = int(math.floor(math.log10(span / TICKS_GOAL)))
    best = None
    for k in range(e - 2, e + 3):
        for m in NICE:
            st = m * 10.0 ** k
            if integer and (st < 1 or abs(st - round(st)) > 1e-9):
                continue
            n = _n_ticks(lo, hi, st)
            score = (abs(n - TICKS_GOAL) + (0.6 if m == 2.5 and _decimals(st) > 0 else 0.0)
                     + (0 if TICKS_MIN <= n <= TICKS_MAX else 50))
            if best is None or score < best[0]:
                best = (score, st)
    return best[1]


def _is_nice(v):
    import math
    if v <= 0:
        return False
    k = math.floor(math.log10(v))
    return any(abs(v - m * 10.0 ** k) < 1e-9 * v for m in NICE)


def minor_step(step, move):
    """Finer, unlabelled grid lines on the scale of what the series typically moves (its average day): the largest
    divisor of the tick step (a half, a quarter, a fifth) at or above that move -- none when a move is half a step or
    more (the labelled ticks already show it) or when it would draw more than five lines a step."""
    if not move or move <= 0 or move >= step / 2.0:
        return None
    for k in (5, 4, 2):                                   # the finest NICE division still at least one move wide
        mn = step / k
        if mn >= move * 0.999 and _is_nice(mn):
            return mn
    return None


def typical_move(xs, ys):
    """What the series typically moves: its mean absolute change a day (an hour, for a span under two days), from its
    last value each day (hour). xs: datetimes (ET clock) or hours; None when it cannot be told."""
    if not xs or len(xs) < 2:
        return None
    try:
        if isinstance(xs[0], _dt.datetime):
            span_d = (xs[-1] - xs[0]).total_seconds() / 86400.0
            key = (lambda x: x.date()) if span_d >= 2 else (lambda x: (x.date(), x.hour))
        else:
            span_d = (float(xs[-1]) - float(xs[0])) / 24.0
            key = (lambda x: int(float(x)))
        last = {}
        for x, y in zip(xs, ys):
            if y is not None:
                last[key(x)] = y
        vals = [last[k] for k in sorted(last)]
        moves = [abs(b - a) for a, b in zip(vals, vals[1:])]
        return (sum(moves) / len(moves)) if moves else None
    except (TypeError, ValueError, AttributeError):
        return None


def _fmt_value(v, unit, d, signed, tiny):
    if unit == "%":
        if abs(v) < tiny:
            return "0%"
        return ("%+.*f%%" if signed else "%.*f%%") % (d, v)
    sign = "-" if v < -tiny else ("+" if signed and v > tiny else "")
    if unit == "$":
        return sign + "$" + "{:,.{d}f}".format(abs(v), d=d)
    if unit == "c":
        return sign + "{:,.{d}f}c".format(abs(v), d=d)
    return sign + "{:,.{d}f}".format(abs(v), d=d)


def _money_decimals(step, unit):
    d = _decimals(step)
    if unit == "$" and d > 0 and step < 1:
        return max(2, d)                                  # cents under a dollar: $0.10, never $0.1
    return d


def _install_ticks(axis_obj, view, unit, signed, move=None, integer=False):
    """A locator that re-picks the nice step from the view it is asked about (a chart that changes its limits later
    still gets nice ticks) and a formatter whose decimals are the step's own."""
    T = mpl()["ticker"]

    class Nice(T.Locator):
        def __call__(self):
            lo, hi = sorted(view())
            return self.tick_values(lo, hi)

        def tick_values(self, lo, hi):
            import math
            st = nice_step(lo, hi, integer)
            k0, k1 = math.ceil(lo / st - 1e-9), math.floor(hi / st + 1e-9)
            return [round(k * st, 10) for k in range(int(k0), int(k1) + 1)]

    class Minor(T.Locator):
        def __call__(self):
            import math
            lo, hi = sorted(view())
            st = nice_step(lo, hi, integer)
            mn = minor_step(st, move)
            if not mn:
                return []
            k0, k1 = math.ceil(lo / mn - 1e-9), math.floor(hi / mn + 1e-9)
            return [k * mn for k in range(int(k0), int(k1) + 1) if abs(k * mn / st - round(k * mn / st)) > 1e-6]

    def f(v, _p=None):
        lo, hi = sorted(view())
        st = nice_step(lo, hi, integer)
        d = _money_decimals(st, unit)
        return _fmt_value(v, unit, d, signed, 0.5 * 10 ** -d)
    axis_obj.set_major_locator(Nice())
    axis_obj.set_major_formatter(T.FuncFormatter(f))
    axis_obj.set_minor_locator(Minor())
    axis_obj.set_minor_formatter(T.NullFormatter())


def ref(y, label="", color=None, ls="--", lw=1.2, optional=False, where="right"):
    """A reference line for value_axis(refs=...): break-even, a goal, a stop line. optional=True: drawn only when it
    sits within half the data's range of the data (a far stop line would flatten the series) -- otherwise its words
    come back from value_axis (['far'] ) for the chart to say in a note."""
    return {"y": float(y), "label": label, "color": color or MUTED, "ls": ls, "lw": lw, "optional": optional,
            "where": where}


def value_axis(ax, ys, unit="$", kind="balance", signed=None, axis="y", move=None, xs=None, refs=(), room_top=0.0,
               room_bottom=0.0, integer=False, floor=None, cap=None):
    """THE value axis (y, or x for a strip): limits, ticks, labels, the zero line, reference lines.

    ys       every value the axis must show (all its series; bars: their tops and bottoms)
    unit     '$' | '%' (values already in percent) | 'c' (cents) | '' (a count)
    kind     'balance' a level of money (a bank, a pot): zoomed to the data; $0 only when the data come near it
             'pnl'     money or % made: always shows 0, with the zero line
             'level'   any other level (a win rate, a share, a price): zoomed, kept inside floor..cap
    move     what the series typically moves (its average day); default: typical_move(xs, ys). It sets the unlabelled
             minor grid and the smallest range drawn (a flat line is never blown up into cliffs)
    refs     numbers that must be inside (a series drawn elsewhere), or ref(...) lines to draw
    room_top, room_bottom   extra room for a key or names, as a share of the data's range (declared, so the rules
             check does not count it as wasted space)
    Returns {'lo', 'hi', 'step', 'far': [words of optional refs left out]}."""
    vals = [float(v) for v in ys if v is not None]
    must = [float(r) for r in refs if not isinstance(r, dict)]
    lines = [r for r in refs if isinstance(r, dict)]
    data = vals + must
    if not data:
        data = [0.0]
    dlo, dhi = min(data), max(data)
    dspan = dhi - dlo
    if move is None and xs is not None:
        move = typical_move(list(xs), list(ys))
    far = []
    for r in lines:                                       # optional refs: in only when near the data
        if r["optional"] and not (dlo - 0.5 * max(dspan, abs(dhi) * 0.02) <= r["y"] <= dhi + 0.5 * max(dspan, abs(dhi) * 0.02)):
            far.append(r)
    drawn = [r for r in lines if r not in far]
    lo, hi = min([dlo] + [r["y"] for r in drawn]), max([dhi] + [r["y"] for r in drawn])
    if kind == "pnl":
        lo, hi = min(lo, 0.0), max(hi, 0.0)
    elif kind == "balance":
        span0 = max(hi - lo, 1e-9)
        if 0.0 < lo <= NEAR_ZERO * span0:
            lo = 0.0
        elif -NEAR_ZERO * span0 <= hi < 0.0:
            hi = 0.0
    # the smallest range drawn: three typical moves, 1% of the level, or the unit's floor -- a flat line stays flat
    floor_u = {"$": 0.5, "%": 0.1, "c": 1.0, "": 4.0 if integer else 1.0}.get(unit, 1.0)
    least = max(3.0 * (move or 0.0), 0.01 * max(abs(lo), abs(hi)), floor_u)
    declared, widened = (lo, hi), hi - lo < least
    if widened:
        mid = (hi + lo) / 2.0
        if kind == "pnl" and lo >= 0.0:
            lo, hi = 0.0, max(hi, least)
        elif kind == "pnl" and hi <= 0.0:
            lo, hi = min(lo, -least), 0.0
        else:
            lo, hi = mid - least / 2.0, mid + least / 2.0
            if floor is not None and lo < floor:
                lo, hi = floor, floor + least
            if cap is not None and hi > cap:
                lo, hi = cap - least, cap
    span = hi - lo
    p0, p1 = PAD * span, PAD * span
    lo_v, hi_v = lo - p0 - room_bottom * span, hi + p1 + room_top * span
    if floor is not None:
        lo_v = max(lo_v, floor - (PAD * span if lo <= floor else 0.0))
    if cap is not None:
        hi_v = min(hi_v, cap + (PAD * span if hi >= cap else 0.0))
    if signed is None:
        signed = kind == "pnl"
    if axis == "y":
        ax.set_ylim(lo_v, hi_v)
        _install_ticks(ax.yaxis, ax.get_ylim, unit, signed, move, integer)
        ax.grid(True, which="minor", axis="y", color=GRID, lw=0.45, alpha=0.6)
        ax.yaxis.set_tick_params(which="minor", length=0)
    else:
        ax.set_xlim(lo_v, hi_v)
        _install_ticks(ax.xaxis, ax.get_xlim, unit, signed, move, integer)
    if kind == "pnl" and axis == "y":
        zero_line(ax)
    for r in drawn:
        draw_ref(ax, r, axis)
    setattr(ax, "_kals_" + axis, {"kind": "value", "unit": unit, "room": (room_top + room_bottom) * span,
                                  "move": move, "data": declared, "widened": widened})
    return {"lo": lo_v, "hi": hi_v, "step": nice_step(lo_v, hi_v, integer), "far": far}


def money_axis(ax, ys, kind="pnl", **kw):
    """value_axis in dollars (kind 'pnl' by default: money made; 'balance' for a bank or a pot)."""
    return value_axis(ax, ys, unit="$", kind=kind, **kw)


def pct_axis(ax, ys, kind="pnl", **kw):
    """value_axis in percent (the values already x 100)."""
    return value_axis(ax, ys, unit="%", kind=kind, **kw)


def draw_ref(ax, r, axis="y"):
    if axis == "y":
        ax.axhline(r["y"], color=r["color"], lw=r["lw"], ls=r["ls"], zorder=2)
        if r["label"]:
            right = r["where"] == "right"
            ax.__dict__.setdefault("_kals_reflabels", []).append((r["y"], right))   # keys keep off it
            ax.annotate(r["label"], (1.0 if right else 0.0, r["y"]), xycoords=("axes fraction", "data"),
                        xytext=(-4 if right else 4, 3), textcoords="offset points", ha="right" if right else "left",
                        va="bottom", fontsize=8.5, color=INK2, zorder=6)
    else:
        ax.axvline(r["y"], color=r["color"], lw=r["lw"], ls=r["ls"], zorder=2)


def pct_of_axis(ax, base, label):
    """The SAME dollars read as % of one fixed base, on the right. Not a second measure. Its ticks: the engine's."""
    if not base or base <= 0:
        return None
    sec = ax.secondary_yaxis("right", functions=(lambda v: v / base * 100.0, lambda p: p * base / 100.0))
    lo_hi = (lambda: tuple(v / base * 100.0 for v in ax.get_ylim()))
    _install_ticks(sec.yaxis, lo_hi, "%", True)
    sec.yaxis.set_minor_locator(mpl()["ticker"].NullLocator())
    sec.tick_params(axis="y", length=0, labelsize=9.5, labelcolor=MUTED)
    sec.spines["right"].set_visible(False)
    sec.set_ylabel(label, fontsize=9, color=MUTED)
    sec._kals_y = {"kind": "value", "unit": "%", "room": 0.0, "secondary": True}
    return sec


def zero_line(ax):
    ax.axhline(0, color=AXIS, lw=1.0, zorder=1)


def _as_dt(x):
    if isinstance(x, _dt.datetime):
        return x
    return etdt(x)


def _hour_label(d):
    return "%d %s" % ((d.hour % 12) or 12, "AM" if d.hour < 12 else "PM")


def time_axis(ax, x0=None, x1=None, xs=None, pad=0.02, pad_days=0.0, clock=False, fixed=False):
    """THE time axis. x0, x1: the span the panel covers (ET datetimes or epochs); default: the span of xs, else of
    what is drawn. The axis covers that span (+ pad of it each side, at least pad_days: a day's bar needs half a day)
    and only that; its ticks fit the span: hours for a day, days for a week, Mondays for weeks, months beyond.
    clock=True: a fixed clock day (today's 12 AM .. 12 AM), drawn whole whatever the data; fixed=True: any other
    window the picture means to show whole (the last 30 days of losses), however little falls in it.
    Panels that share x (fig_new(sharex=True)) get it once, on the bottom one -- only when they cover the same span."""
    D, T = mpl()["dates"], mpl()["ticker"]
    if x0 is None or x1 is None:
        if xs:
            dts = sorted(_as_dt(x) for x in xs)
            x0, x1 = dts[0], dts[-1]
        else:
            lo, hi = ax.dataLim.intervalx
            if not (hi >= lo) or abs(hi) == float("inf"):
                lo, hi = ax.get_xlim()
            x0, x1 = D.num2date(lo).replace(tzinfo=None), D.num2date(hi).replace(tzinfo=None)
    x0, x1 = _as_dt(x0), _as_dt(x1)
    if x1 <= x0:
        x0, x1 = x0 - _dt.timedelta(hours=12), x1 + _dt.timedelta(hours=12)
    span = x1 - x0
    if clock:
        p = _dt.timedelta(0)
    else:
        p = max(span * pad, _dt.timedelta(days=pad_days))
    ax.set_xlim(x0 - p, x1 + p)
    days = (span + 2 * p).total_seconds() / 86400.0
    ax.xaxis.set_minor_locator(T.NullLocator())
    if days <= 1.6:
        step = next(h for h in (1, 2, 3, 6) if days * 24 / h <= 9)
        ax.xaxis.set_major_locator(D.HourLocator(byhour=range(0, 24, step)))
        ax.xaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: _hour_label(D.num2date(v))))
    elif days <= 4:
        ax.xaxis.set_major_locator(D.HourLocator(byhour=(0, 12) if days > 2.5 else (0, 6, 12, 18)))
        ax.xaxis.set_major_formatter(T.FuncFormatter(
            lambda v, _p: (lambda d: d.strftime("%a ") + str(d.day) if d.hour == 0 else _hour_label(d))(D.num2date(v))))
    elif days <= 12:
        ax.xaxis.set_major_locator(D.DayLocator(interval=1 if days <= 9 else 2))
        ax.xaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: (lambda d: d.strftime("%a ") + str(d.day))(D.num2date(v))))
    elif days <= 75:
        ax.xaxis.set_major_locator(D.WeekdayLocator(byweekday=D.MO))
        ax.xaxis.set_minor_locator(D.DayLocator())
        ax.xaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: (lambda d: d.strftime("%b ") + str(d.day))(D.num2date(v))))
    else:
        ax.xaxis.set_major_locator(D.MonthLocator())
        ax.xaxis.set_minor_locator(D.WeekdayLocator(byweekday=D.MO))
        ax.xaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: D.num2date(v).strftime("%b")))
    ax.tick_params(axis="x", which="minor", length=2, color=AXIS)
    info = {"kind": "clock" if clock else ("fixed" if fixed else "time"), "span": (x0, x1)}
    for a in ax.get_shared_x_axes().get_siblings(ax):
        a._kals_x = info
    return info


def date_axis(ax, span_days=None):
    """time_axis over what is drawn (the old name; span_days is worked out from the data now)."""
    return time_axis(ax)


def clock_axis(ax, hours=True):
    """A 12 AM .. 12 AM clock in hours (0..24) on x: a pace through the ET day."""
    T = mpl()["ticker"]
    ax.set_xlim(0, 24)
    ax.xaxis.set_major_locator(T.FixedLocator(list(range(0, 25, 3))))
    ax.xaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: "%d %s" % ((int(v) % 12) or 12, "AM" if int(v) % 24 < 12 else "PM")))
    ax._kals_x = {"kind": "clock"}


def category_axis(ax, labels, axis="x", positions=None, fontsize=9.5, top_first=False, pad=0.5, lo_pad=None):
    """Named slots (weeks, bots) instead of numbers: ticks at 0..n-1 (or positions), each with its label; no grid on
    that axis. top_first: the first slot at the top (a y axis read like a list)."""
    pos = list(positions) if positions is not None else list(range(len(labels)))
    lo, hi = (min(pos) - (pad if lo_pad is None else lo_pad), max(pos) + pad) if pos else (-0.5, 0.5)
    if axis == "x":
        ax.set_xticks(pos)
        ax.set_xticklabels(labels, fontsize=fontsize)
        ax.set_xlim(lo, hi)
        ax.grid(False, axis="x")
    else:
        ax.set_yticks(pos)
        ax.set_yticklabels(labels, fontsize=fontsize)
        ax.set_ylim((hi, lo) if top_first else (lo, hi))
        ax.grid(False, axis="y")
    setattr(ax, "_kals_" + axis, {"kind": "category"})


def no_axis(ax, axis="y", lo=0.0, hi=1.0):
    """An axis that carries no numbers (a strip's height): fixed limits, no ticks, no grid, no spine."""
    if axis == "y":
        ax.set_ylim(lo, hi)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
    else:
        ax.set_xlim(lo, hi)
        ax.set_xticks([])
    ax.grid(False, axis=axis)
    setattr(ax, "_kals_" + axis, {"kind": "none"})


def mark_empty(ax, words):
    """A panel with nothing to draw yet says why, in the middle, and carries no axes numbers."""
    ax.text(0.5, 0.5, words, transform=ax.transAxes, ha="center", va="center", color=MUTED, fontsize=10, wrap=True)
    no_axis(ax, "y")
    ax._kals_empty = True


# ---- marks on the data -------------------------------------------------------------------------------------------
def mark_last(ax, x, y, text, color=None, dx=-4, ha="right"):
    """The newest point: a dot in the series' colour and its value in bold."""
    if color:
        ax.scatter([x], [y], s=34, color=color, edgecolor=SURF, linewidth=1.3, zorder=5)
    note(ax, x, y, text, dx=dx, ha=ha)


def mark_start(ax, x, y, text):
    """The first point's value, small and muted, just right of it (under the line when the line rises from there)."""
    ax.annotate(text, (x, y), xytext=(4, -6), textcoords="offset points", ha="left", va="top", fontsize=8.5,
                color=INK2, zorder=6)


def mark_high_low(ax, xs, ys, fmt, color=INK2):
    """The highest and lowest points, named, when they are not the first or the last one (those carry their own)."""
    if len(ys) < 3:
        return
    span = (max(ys) - min(ys)) or 1.0
    for k, top in ((max(range(len(ys)), key=lambda i: ys[i]), True), (min(range(len(ys)), key=lambda i: ys[i]), False)):
        if min(abs(ys[k] - ys[0]), abs(ys[k] - ys[-1])) < 0.06 * span or k in (0, len(ys) - 1):
            continue
        ax.annotate(("high " if top else "low ") + fmt(ys[k]), (xs[k], ys[k]), xytext=(0, 5 if top else -5),
                    textcoords="offset points", ha="center", va="bottom" if top else "top", fontsize=8.5,
                    color=color, zorder=6)


def _corner_hits(ax, w, h):
    """corner -> how many drawn points (lines, dots, bar tops) fall in a w x h (axes fractions) box in that corner."""
    import numpy as np
    pts = []
    for ln in ax.get_lines():
        xy = np.asarray(ln.get_xydata(), dtype=float)
        if len(xy):
            pts.append(xy)
    for c in ax.collections:
        try:
            off = np.asarray(c.get_offsets(), dtype=float)
            if len(off):
                pts.append(off)
        except Exception:                               # noqa: BLE001
            pass
    for p in ax.patches:
        try:
            bb = p.get_bbox()
            pts.append(np.array([[bb.x0, bb.y0], [bb.x1, bb.y1], [(bb.x0 + bb.x1) / 2, bb.y1]]))
        except Exception:                               # noqa: BLE001
            pass
    frac = np.zeros((0, 2))
    if pts:
        xy = np.vstack([p for p in pts if p.ndim == 2 and p.shape[1] == 2])
        xy = xy[np.isfinite(xy).all(axis=1)]
        if len(xy):
            frac = ax.transAxes.inverted().transform(ax.transData.transform(xy))
    import numpy as _np
    for y, right in getattr(ax, "_kals_reflabels", []):  # a reference line's words weigh as 40 points
        yf = ax.transAxes.inverted().transform(ax.transData.transform([[0.0, y]]))[0][1]
        xs_ = _np.linspace(0.55, 0.99, 40) if right else _np.linspace(0.01, 0.45, 40)
        frac = _np.vstack([frac, _np.column_stack([xs_, _np.full(40, yf + 0.03)])])
    boxes = {"upper left": (0, 1 - h, w, 1), "upper right": (1 - w, 1 - h, 1, 1), "lower left": (0, 0, w, h),
             "lower right": (1 - w, 0, 1, h)}

    def hits(c):
        x0, y0, x1, y1 = boxes[c]
        return int(((frac[:, 0] >= x0) & (frac[:, 0] <= x1) & (frac[:, 1] >= y0) & (frac[:, 1] <= y1)).sum())
    return hits


def corner_box(ax, text, prefer=("upper left", "lower right", "upper right", "lower left")):
    """Words in a quiet box in the panel's emptiest corner (the fewest drawn points under it); returns that corner, so
    a key can take another (free_corner). Call after the limits are set."""
    nl = text.count("\n") + 1
    nl = text.count("\n") + 1
    hits = _corner_hits(ax, 0.55, min(0.5, 0.07 * nl + 0.06))
    best = min(prefer, key=lambda c: (hits(c), prefer.index(c)))
    x = 0.015 if "left" in best else 0.985
    y = 0.97 if "upper" in best else 0.03
    ax.text(x, y, text, transform=ax.transAxes, ha="left" if "left" in best else "right",
            va="top" if "upper" in best else "bottom", fontsize=9, color=INK2, zorder=7, linespacing=1.25,
            bbox=dict(facecolor=SURF, edgecolor=GRID, boxstyle="round,pad=0.3", alpha=0.94))
    ax._kals_corner = best
    return best


def free_corner(ax, rows=1):
    """The corner a key of `rows` lines should take: the emptiest one corner_box did not take (the newest point's
    label counts against its corner)."""
    used = getattr(ax, "_kals_corner", None)
    hits = _corner_hits(ax, 0.5, min(0.5, 0.07 * rows + 0.06))
    order = [c for c in ("lower right", "upper right", "upper left", "lower left") if c != used]
    return min(order, key=lambda c: (hits(c), order.index(c)))


def change_words(v0, v1, base=None, since=None, unit="$", ends=False):
    """'+$95.60 (+13.1%) since Sep 28': the change over what is drawn, in dollars and as % of `base` (default: the
    starting value, when it is a level above $0; False: no %). ends=True (a balance): '$729.56 -> $825.16 · ' first."""
    d = v1 - v0
    b = base if base is not None else (v0 if v0 > 0 else None)
    b = b if b is not False else None
    pc = (" (%+.1f%%)" % (100.0 * d / b)) if b else ""
    when = (" since " + (since.strftime("%b ") + str(since.day) if isinstance(since, _dt.datetime) else str(since))
            ) if since is not None else ""
    head = ("%s \u2192 %s · " % (usd(v0, False), usd(v1, False))) if ends and unit == "$" else ""
    return "%s%s%s%s" % (head, usd(d) if unit == "$" else "%+.2f%%" % d, pc, when)


def annotate_change(ax, xs, ys, base=None, unit="$", extra=(), lows=True, ends=False):
    """The change over the panel in its emptiest corner: '+$95.60 (+13.1%) since Sep 28' (a balance, ends=True:
    '$729.56 -> $825.16 · +$95.60 ...'), then 'low $x · high $y' when they differ from the ends, then any `extra`
    lines. Returns the corner."""
    if not ys:
        return None
    lines = [change_words(ys[0], ys[-1], base=base, since=xs[0] if xs else None, unit=unit, ends=ends)]
    if lows and len(ys) > 2:
        lo, hi = min(ys), max(ys)
        span = (hi - lo) or 1.0
        f = (lambda v: usd(v, not ends)) if unit == "$" else (lambda v: "%+.2f%%" % v)   # money made: signed
        bits = []
        if min(ys[0], ys[-1]) - lo > 0.04 * span:
            bits.append("low " + f(lo))
        if hi - max(ys[0], ys[-1]) > 0.04 * span:
            bits.append("high " + f(hi))
        if bits:
            lines.append(" · ".join(bits))
    lines += [e for e in extra if e]
    return corner_box(ax, "\n".join(lines))


def shade(ax, x0, x1, label="", color=None):
    """A shaded stretch of time (a pause, quiet hours), named at its top."""
    ax.axvspan(_as_dt(x0) if not isinstance(x0, (int, float)) or x0 > 1e6 else x0,
               _as_dt(x1) if not isinstance(x1, (int, float)) or x1 > 1e6 else x1, color=color or MID_T, zorder=0, lw=0)
    if label:
        ax.annotate(label, (_as_dt(x0) if not isinstance(x0, (int, float)) or x0 > 1e6 else x0, 1.0),
                    xycoords=("data", "axes fraction"), xytext=(3, -3), textcoords="offset points", ha="left",
                    va="top", fontsize=8.5, color=INK2)


# ---- the rules check ----------------------------------------------------------------------------------------------
def audit(fig, size=None):
    """Every rule a phone picture keeps, checked on the drawn figure (png() runs it when STRICT or AUDIT is set):
    no offset / scientific tick text; every numbered axis went through the engine; TICKS_MIN..TICKS_MAX labelled
    value ticks; the data (+ reference lines) fill MIN_FILL of each value axis and of each time axis; no two tick
    labels overlap; the PNG under PNG_LIMIT. Returns ['problem', ...]."""
    import math
    out = []
    if size is not None and size > PNG_LIMIT:
        out.append("PNG %d bytes > %d" % (size, PNG_LIMIT))
    rnd = fig.canvas.get_renderer()
    title = (fig._suptitle.get_text() if fig._suptitle is not None else "")[:40]
    for i, ax in enumerate(fig.axes):
        if not ax.get_visible() or (getattr(ax, "_kals_y", None) or {}).get("secondary"):
            continue                                    # a right-hand axis is checked with its panel
        name = "%s | panel %d (%s)" % (title, i, (ax.get_title(loc="left") or ax.get_title())[:40])
        axes_list = [(ax, ax)] + [(c, ax) for c in getattr(ax, "child_axes", [])]
        for a, host in axes_list:
            for which in ("x", "y"):
                axis_obj = a.xaxis if which == "x" else a.yaxis
                if not axis_obj.get_visible():
                    continue
                off = axis_obj.get_offset_text().get_text()
                if off:
                    out.append("%s: %s offset text %r" % (name, which, off))
                labs = [t for t in axis_obj.get_ticklabels() if t.get_visible() and t.get_text()]
                lim = sorted(a.get_xlim() if which == "x" else a.get_ylim())
                locs = [v for v in axis_obj.get_majorticklocs() if lim[0] - 1e-9 <= v <= lim[1] + 1e-9]
                texts = [t.get_text() for t in labs]
                if any(("e+" in s or "e-" in s or "×" in s or "1e" in s) for s in texts):
                    out.append("%s: %s scientific tick text %r" % (name, which, texts))
                info = getattr(a, "_kals_" + which, None)
                if labs and info is None and not getattr(host, "_kals_empty", False):
                    out.append("%s: %s axis has numbers but did not go through the engine" % (name, which))
                if info and info.get("kind") == "value" and labs:
                    n = len(locs)
                    if not (TICKS_MIN <= n <= TICKS_MAX):
                        out.append("%s: %s has %d ticks (%s)" % (name, which, n, texts))
                bbs = sorted((t.get_window_extent(rnd) for t in labs), key=lambda b: (b.x0, b.y0))
                for b0, b1 in zip(bbs, bbs[1:]):
                    if b0.overlaps(b1) and b0.width > 0 and b1.width > 0:
                        out.append("%s: %s tick labels overlap (%s)" % (name, which, texts))
                        break
                if a is not host or getattr(host, "_kals_empty", False):
                    continue
                dl = a.dataLim
                d0, d1 = (dl.intervalx if which == "x" else dl.intervaly)
                if which == "x":                        # panels sharing a time axis: what they draw together
                    for sib in a.get_shared_x_axes().get_siblings(a):
                        s0, s1 = sib.dataLim.intervalx
                        if math.isfinite(s0) and math.isfinite(s1):
                            d0, d1 = (min(d0, s0), max(d1, s1)) if math.isfinite(d0) and math.isfinite(d1) else (s0, s1)
                if not (math.isfinite(d0) and math.isfinite(d1)):
                    continue
                if info and info.get("data"):           # what the chart asked the axis to hold counts as drawn
                    d0, d1 = min(d0, info["data"][0]), max(d1, info["data"][1])
                if info and info.get("widened"):        # a flat series the engine widened on purpose
                    continue
                if info and (info.get("kind") == "value" or info.get("kind") == "time"):
                    vspan = (lim[1] - lim[0]) - (info.get("room") or 0.0)
                    cov = max(0.0, min(d1, lim[1]) - max(d0, lim[0]))
                    if vspan > 0 and d1 > d0 and cov / vspan < MIN_FILL - 1e-6:     # (one moment: centred)
                        out.append("%s: the data fill %.0f%% of the %s axis" % (name, 100 * cov / vspan, which))
    return out


def _check(fig, size):
    if not (STRICT or AUDIT is not None):
        return
    probs = audit(fig, size)
    if AUDIT is not None:
        AUDIT.extend(probs)
    if STRICT and probs:
        raise ChartRuleError("; ".join(probs))


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
