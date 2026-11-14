"""/fixes (/changes) -- every live pin change: what it does, since when, how many times it engaged, when last, what is
still open, and the net $ so far (+ made or saved, - cost or gave up) with its % of the bank; the last 3 engagements of
each, one line each; then one total line.

v-fixes (2026-11-04; the operator: "track them thoroughly and have a telegram command that makes it very simple to see
times any of them have been engaged and the positive or negative overall result of it"). The numbers are
botdata.fixes.report (pin's own logs, pinrules_watch's scorers for rules A, B, C); nothing here reads Kalshi. The bank
for the % is the ledger's bank now (pindesk.Ledger.bank_at), else the pin bot's own pinrun-live-size.json.

v-ladder-rail100 tracking (2026-11-14): a change that says a problem (botdata.fixes: change["problem"] -- O while the
ladder runs its 100% rail on code that does not mark the bids, so O could only ever read 'none yet') gets a ⚠️ line in
its own block (before 'not engaged yet', never cut) and is counted on a ⚠️ line at the top of the page.

v-tg-fixes-PQ (2026-11-14; the operator: "make sure all of this is being tracked what the results would be if it
wasn't changed"): P (band99 late-only: the band legs skipped for being earlier than 30 s, against pin's own legs they
would have blocked) and Q (the ladder's midnight reset: what it made after each reset, the old code stayed halted)
render like every other change, their lines under the net. O is WITHDRAWN (change["withdrawn"]): its block says so,
and it never gets a problem line here, whatever it carries (fixes.totals leaves it out of the total too).

Page room (11-14, the server's logs ran the page to 3,880 of 3,900 chars with every last-engagement line gone): a change
that is off for good while it is not live (fixes: change["retired"] -- N shelved, O withdrawn) is folded with the others
into ONE short 'not live' line in the first one's place, never a block (~230 chars back; their whole words stay in
fixes' not_live); P's line puts its net first; and no cut ever lands inside a money figure (_cut stops before it).
"""
import re

from botdata import fixes as _fixes
from botdata import paths as _paths
from botdata.fmt import usd
from phone.command import Command, declare
from phone.html import MAX_LEN, Html, esc, i_

SHOWN = 3                                         # the last engagements of each change (when they fit)
HEAD = "🔧 <b>Pin changes</b> (every live change: times engaged, net $ so far)"
NOTE = ("engaged = the change did something pin would not have done before · net = what that made or saved (+) or "
        "cost or gave up (-), fee in, on markets that have settled · open = engaged, the market not settled yet · "
        "the total leaves J out (a J leg is already counted in C)")
# a change that cannot be tracked as it runs (fixes: change["problem"]; O on the ladder's 100% rail without the code that
# marks its bids): a line in its block and, counted, a line on top of the page -- both kept at every shrink step
PROBLEM = "⚠️ <b>%s</b>"


def problems_line(changes):
    """The page's top line when any change says a problem: '⚠️ 1 PROBLEM: O ladder cash limit 100%: <its words>'; None
    when none does (a withdrawn change never counts: fixes' O while O_WITHDRAWN)."""
    bad = [c for c in changes if c.get("problem") and not c.get("withdrawn")]
    if not bad:
        return None
    return "⚠️ <b>%d PROBLEM%s</b>: %s" % (len(bad), "" if len(bad) == 1 else "S", "; ".join(
        "%s %s: %s" % (esc(c["id"]), esc(c["name"]), esc(c["problem"])) for c in bad))


def _bank(ctx):
    try:
        b = ctx.ledger.bank_at(ctx.now())
        if b:
            return float(b)
    except Exception:                                       # noqa: BLE001  (no ledger planted, or no reading yet)
        pass
    d = _paths.read_json(_paths.results("pinrun-live-size.json")) or {}
    try:
        return float(d.get("bank") or 0) or None
    except (TypeError, ValueError):
        return None


def load(ctx):
    """{"changes": botdata.fixes.report at ctx.now(), "bank": the bank now or None}."""
    return {"changes": _fixes.report(now=ctx.now()), "bank": _bank(ctx)}


def _mark(x):
    return "🟢" if x > 0.004 else ("🔴" if x < -0.004 else "⚪")


def _pct(x, bank):
    if not bank:
        return ""
    return " (%s%.2f%% of the bank)" % ("+" if x >= 0 else "-", abs(x) / bank * 100)


_MONEY = re.compile(r"[-+]?\$\d[\d,]*(?:\.\d+)?")     # a money figure: -$1,234.56, +$0.32, $12


def _cut(words, n):
    """`words` at most n characters (an ellipsis closes a cut), or whole when n is None. A cut never lands inside a money
    figure: it stops before the figure instead (a half figure, '$1.…' for $1.22, would read as another amount); a line
    that opens with one keeps it whole."""
    w = str(words)
    if n is None or len(w) <= n:
        return w
    k = max(1, n - 1)
    for m in _MONEY.finditer(w):
        if m.start() >= k:
            break
        if k < m.end():
            k = m.start() if m.start() > 0 else m.end()
            break
    return w[:k].rstrip() + "…"


def retired_line(changes):
    """ONE short line for every change that is off for good while it is not live (fixes: change["retired"]; N shelved,
    O withdrawn): 'not live: <b>N hedge line 0.60</b> (shelved 11-09) · <b>O ...</b> (withdrawn 11-14, ...)'; None when
    there is none. A change with a problem is never folded (its block carries the warning)."""
    rs = [c for c in changes if _folded(c)]
    if not rs:
        return None
    return "not live: " + " · ".join("<b>%s %s</b> (%s)" % (esc(c["id"]), esc(c["name"]), esc(c["retired"])) for c in rs)


def _folded(c):
    return bool(c.get("retired")) and not c.get("since") and not (c.get("problem") and not c.get("withdrawn"))


def block(c, bank, shown, cut=None, extra_cut=None, what_cut=None):
    """One change: name, what (cut to `what_cut` chars; 0 = left out), since, engaged / last, net, its extra lines (cut
    to `extra_cut` chars; 0 = left out), the last `shown` events (their words cut to `cut` chars)."""
    out = ["<b>%s %s</b>" % (esc(c["id"]), esc(c["name"]))]
    if what_cut != 0:
        out.append(esc(_cut(c["what"], what_cut)))
    if c.get("problem") and not c.get("withdrawn"):       # never cut, never behind 'not engaged yet' (fixes.O_UNTRACKED);
        out.append(PROBLEM % esc(c["problem"]))           # never on a withdrawn change (O: fixes.O_WITHDRAWN)
    if not c["since"]:
        # L, M, N, O (withdrawn), P, Q: their own words (fixes.L_NOT_LIVE ... Q_NOT_LIVE)
        out.append(esc(c.get("not_live") or "not live yet (comes with the new build)"))
        return out
    out.append("since %s" % esc(c["since"]))
    if c.get("off") and not c["engaged"]:
        out.append("in the build but switched OFF (the launcher leaves --late-bypass-fix off): nothing to count")
        return out
    if not c["engaged"]:
        out.append("not engaged yet")
        return out
    out.append("engaged %d time%s, last %s%s" % (c["engaged"], "" if c["engaged"] == 1 else "s",
                                                 esc(c["last_engaged"] or "?"),
                                                 (" · %d open" % c["open"]) if c["open"] else ""))
    out.append("%s net <b>%s</b>%s" % (_mark(c["net_usd"]), esc(usd(c["net_usd"])), esc(_pct(c["net_usd"], bank))))
    if extra_cut != 0:                                    # K: the skips without the rule, the window with and without;
        #                                                   L: what the shadowed jump hedge would have paid / saved / made;
        #                                                   M: the held-back contracts and the true 3rd bet (not in its net)
        out += [esc(_cut(x, extra_cut)) for x in c.get("extra") or []]
    for e in c["events"][-shown:] if shown else []:
        out.append("  %s · %s · %s · %s" % (esc(e["et"] or "?"), esc(e["coin"]),
                                         esc(usd(e["usd"]) if e["usd"] is not None else "open"), esc(_cut(e["words"], cut))))
    return out


# how the page shrinks to one message: fewer events first, then shorter event words, then shorter extra lines (K, L, M's
# lines under their nets), then no events (the blocks stay), then no extra lines. Each step is (events shown, their
# words' cut, the extra lines' cut: None whole, 0 none). The 30-char step came with L (12 changes): one 60-char event per
# change no longer fits one message, one 30-char event (the time, coin, $ and the first words) still does. The extra
# cuts came with M (13 changes, 11-08): with K, L and M all live their six lines alone are a third of a message, so
# measured on the 11-08 logs the blocks with whole lines and no events ran to 4,398 chars; cutting the lines to 120
# chars keeps one 30-char event per change on the page (the test holds every step). The what-less steps came with N
# (14 changes, 11-08): with K, L, M and N live the blocks with their lines no longer fit even without events, and the
# money lines matter more than the one-line descriptions (the operator knows the changes; /fixes is read for the $), so
# the "what" lines go (fourth element 0) before any money line is cut, and the events come back when that makes room.
PLAN = ((SHOWN, None, None, None), (2, None, None, None), (1, None, None, None), (1, 110, None, None),
        (1, 60, None, None), (1, 30, None, None), (1, 30, 120, None), (0, None, None, None), (0, None, 120, None),
        (1, 30, 120, 0), (0, None, None, 0), (0, None, 120, 0), (1, 30, 0, None), (0, None, 0, None), (0, None, 0, 0))


def render(d, ctx):
    changes, bank = d["changes"], d.get("bank")
    T = _fixes.totals(changes)
    total = "%s <b>All changes: net %s</b>%s · engaged %d time%s%s" % (
        _mark(T["net_usd"]), esc(usd(T["net_usd"])), esc(_pct(T["net_usd"], bank)), T["engaged"],
        "" if T["engaged"] == 1 else "s", (" · %d open" % T["open"]) if T["open"] else "")
    top = problems_line(changes)
    gone = retired_line(changes)
    for shown, cut, extra_cut, what_cut in PLAN:
        out = [HEAD, i_(NOTE)] + ([top] if top else [])
        folded = False
        for c in changes:
            if _folded(c):                                # N, O: one shared short line, in the first one's place
                if not folded:
                    out += ["", gone]
                    folded = True
                continue
            out += [""] + block(c, bank, shown, cut, extra_cut, what_cut)
        out += ["", total]
        msg = "\n".join(out)
        if len(msg) <= MAX_LEN:
            break
    return Html(msg)


COMMAND = declare(Command(
    names=("/fixes", "/changes"), section="now", order=65,
    help_line="/fixes — every live pin change: times engaged, net $ so far",
    chart=None, load=load, render=render,
    fail=lambda e: "Could not build /fixes: %s" % str(e)[:200]))
