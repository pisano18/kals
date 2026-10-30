"""fmt.py -- money, percentages and counts in the phone's words. The EXISTING implementations, copied verbatim.

v-tg-rebuild step 2 (2026-10-30). Nothing in production calls these yet (the registry's bot files do). The old copies
are NOT merged: where two differ, both are here under their own names, so each caller stays on its own behaviour until
step 12 decides (each change then accepted in golden/CHANGES.md with a reason):

  usd        botstats.usd == pinphone.usd (identical; pinphone keeps its copy so a broken botstats costs only the pages
             that need it): '+$1,234.56' / '-$4.57' / '$0.00'; ZERO BAND |x| <= 0.004 -> '$0.00', so x in
             (0.004, 0.005) prints '+$0.00' (and -0.0045 '-$0.00'): a sign on a zero-looking amount.
  usd_chart  tgcharts.usd(x, signed=True): ZERO BAND |x| < 0.005 -> '$0.00' (so 0.0045 is '$0.00' there, '+$0.00' in
             usd), and signed=False drops the '+'. STEP 12: pick one threshold (0.005 is the one that never prints a
             signed zero).
  dollars    pinphone.dollars: no sign, '$1,294.50'.
  pct        botstats.pct: x is ALREADY a percent, '%+.1f%%', None -> 'n/a'. NOT pindesk.pct(x, sign=True), which
             pinphone imports under the same name: x is a FRACTION (x 100), two decimals, None -> '-'. Kept apart as
             pct_frac.
  pot_pct_txt botstats.pot_pct_txt: two decimals under 1%, one above.
  cnt / nof  pinphone._cnt / _nof: '1,234' or '26.31' (decimals kept under 100), 'N word(s)' on that count.
  plural     botstats._n: '%d word(s)' (an int count; nof is the pinphone one, which takes fractions).
  cash       pinphone._cash and botstats.text_summary's inner cash(): '?' or the unsigned usd.
  num / cents / fmt_g   botstats._num / _c / _fmt_g (settings words: 0.978 -> '97.8c').
"""


def usd(x):
    """+$1,234.56 / -$4.57 / $0.00. None -> '?'.  (botstats.usd == pinphone.usd)"""
    if x is None:
        return "?"
    s = "{:,.2f}".format(abs(x))
    return ("+$" if x > 0.004 else ("-$" if x < -0.004 else "$")) + s


def usd_chart(x, signed=True):
    """tgcharts.usd: |x| < 0.005 -> '$0.00'; signed=False never writes '+'. (See the module note: differs from usd.)"""
    if x is None:
        return "?"
    s = "{:,.2f}".format(abs(x))
    if abs(x) < 0.005:
        return "$0.00"
    return ("-" if x < 0 else ("+" if signed else "")) + "$" + s


def dollars(x):
    """An amount with no sign (a bank, a stake): $1,294.50. None -> '?'.  (pinphone.dollars)"""
    return "?" if x is None else "$" + "{:,.2f}".format(x)


def pct(x):
    """x already in percent -> '+1.2%'; None -> 'n/a'.  (botstats.pct)"""
    return "n/a" if x is None else "%+.1f%%" % x


def pct_frac(x, sign=True):
    """x a FRACTION -> '+12.34%'; None -> '-'.  (pindesk.pct, which pinphone imports as `pct`)"""
    if x is None:
        return "-"
    return ("%+.2f%%" if sign else "%.2f%%") % (100 * x)


def pot_pct_txt(x):
    """A share of a pot: two decimals under 1% (a big pot's day is often -0.4%), one above.  (botstats.pot_pct_txt)"""
    if x is None:
        return "n/a"
    return ("%+.2f%%" % x) if abs(x) < 1 else ("%+.1f%%" % x)


def _f(x, default=0.0):
    """(pinphone._f)"""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def cnt(n):
    """A count with thousands separators. Kalshi sells fractional contracts
    (26.31 of them, say): under 100 the decimals are kept, past it they are
    noise on a total and rounded away.  (pinphone._cnt)"""
    n = _f(n)
    if abs(n - round(n)) < 0.005 or n >= 100:
        return "{:,}".format(int(round(n)))
    return "{:,.2f}".format(n)


def nof(k, word):
    """(pinphone._nof)"""
    return "%s %s%s" % (cnt(k), word, "" if _f(k) == 1 else "s")


def plural(k, word):
    """(botstats._n)"""
    return "%d %s%s" % (k, word, "" if k == 1 else "s")


def cash(x):
    """'?' or the unsigned usd.  (pinphone._cash, botstats.text_summary's cash)"""
    return "?" if x is None else usd(x).lstrip("+")


def num(x):
    """(botstats._num)"""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def cents(p):
    """0.978 -> '97.8c', 0.98 -> '98c'.  (botstats._c)"""
    if p is None:
        return "?"
    c = round(float(p) * 100, 1)
    return ("%dc" % c) if abs(c - round(c)) < 1e-9 else ("%.1fc" % c)


def fmt_g(x):
    """(botstats._fmt_g)"""
    try:
        return "%g" % float(x)
    except (TypeError, ValueError):
        return "?"
