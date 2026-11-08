"""phone/render/unbooked.py -- the words for the Kalshi settlements no money total books (v-ledger-unreadable, 2026-11-07).

botdata/ledgercheck.py counts them (a row missing a number its money needs -- what a renamed Kalshi field looks like --
and voided markets); every money total already leaves them out. This says so, in two places:
  note_lines(scan)            the line at the top of every money page (phone/router.py money_note: the 'money' and
                              'one_bot' sections and MONEY_PAGES), e.g. '3 markets unreadable (Kalshi field change?)';
                              unreadable markets only (a voided market is told once, by its alert, not on every page)
  alert_text / void_alert     the ONE phone alert when the count first goes up, and the one when it is back to 0; the
                              one when more markets are voided (phone/monitor.py check_ledger)
"""
from botdata.money import describe
from phone.html import Html, esc


def _markets(n):
    return "%d market%s" % (n, "" if n == 1 else "s")


def _examples(s):
    return "; ".join("%s: %s" % (describe(tk) if tk else "a row with no ticker", why) for tk, why in s["examples"])


def note_lines(s):
    """The warning line at the top of a money page (Telegram HTML), then a blank line; [] when no market is unreadable.
    Voided markets get no line here: they are told once, by void_alert (a line on every page forever after one void
    would only teach the eye to skip the top of the page)."""
    if not s or not s.get("unreadable"):
        return []
    return ["⚠️ <b>%s unreadable (Kalshi field change?)</b>: Kalshi's record is missing a number the money is worked "
            "out from, so %s left out of every total here, not counted as a loss or a win (%s)." % (
                _markets(s["unreadable"]), "it is" if s["unreadable"] == 1 else "they are", esc(_examples(s))), ""]


def alert_text(s, before):
    """The alert for the unreadable count going from `before` markets to s["unreadable"]."""
    n = s["unreadable"]
    if n == 0:
        return Html("✅ <b>Every Kalshi settlement reads again</b>: no market is left out of the money totals now "
                    "(%s were)." % _markets(before))
    pots = ", ".join(("main account %d" if p == "0" else "subaccount " + p + " %d") % k
                     for p, k in sorted(s["by_pot"].items()))
    return Html("⚠️ <b>%s unreadable (Kalshi field change?)</b>\n"
                "Kalshi's settlement records for %s are missing a number the money is worked out from (%s). %s LEFT "
                "OUT of every money total on the phone, not counted as a loss or a win, until the records read "
                "again.\nWhere (markets): %s.\n<i>If Kalshi renamed a field, the bots may read it too: watch the next "
                "fills and /status.</i>" % (
                    _markets(n), "it" if n == 1 else "them", esc(_examples(s)), "It is" if n == 1 else "They are",
                    esc(pots)))


def void_alert(s, new=None):
    """The alert for voided markets (Kalshi gave the stake back). `new`: how many of s["void"] are news (None = all)."""
    n = s["void"] if new is None else int(new)
    head = _markets(n) if n == s["void"] else "%s more (%d in all)" % (_markets(n), s["void"])
    return Html("ℹ️ <b>%s voided by Kalshi</b> (%s): Kalshi gives the stake back, so %s left out of the money "
                "totals, never booked as a loss." % (
                    head, esc(", ".join(describe(t) for t in s["void_examples"] if t) or "no ticker"),
                    "it is" if s["void"] == 1 else "they are"))
