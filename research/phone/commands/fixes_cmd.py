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

v-tg-fixes-acc (2026-11-14, the 11-14 retro: "/fixes must show, for every change, the money vs NEVER making it, losses
included"): the rows the retro found missing -- WS (the wrong-side skip), LAD (the ladder's four changes against the
Option C setting) and STOP (the four stops) -- render like the others; LAD and STOP are measured once (change["fixed"]:
their since line says 'measured once, to <date>', never 'engaged'). A rule the 11-14 undo switched off (M, K, WS:
change["undo"]) says so on its since line ('UNDONE <date>', the date its rule figure runs to) and its NET LINE carries
both periods: '🔴 with the rule: net -$X (..% of the bank) · 🟢 since the undo (vs keeping it): +$Y (..%) on N markets'.
The bold net and its dot stay the rule's money against never making it (fixes: net_usd is rule_usd; from the undo on
pin trades as if the rule had never been), the undo's money against keeping the rule has its own dot, and neither is
ever on a line a shrink step can drop (the 11-14 review: at the last step every 'since the undo' line was gone). B's net
line says the share of it C counts too. The total line splits pin's, the ladder's and the stops' money, says B's
cap-made extra legs (also C's) are counted once, and puts the undos' money beside the total, never in it.

v-tg-fixes-pin (2026-11-16; the operator: "All changes on /fixes uses ladder to calculate the total affect of changes
which isn't right, they only affect pin"): the headline total is PIN'S changes only (fixes.totals' pin_net_usd, B's
overlap netted) with its % of pin's bank, its engagements pin's rows'; the ladder's rows (LAD, O, Q) and the stops
(STOP) are said on their own line under it, never summed in -- the ladder's % against the ladder's pot (fixes: the
newest pot its order log names, change["pot"]), the stops' with none. Each row's net line takes the same base: pin's
bank for a pin row, the ladder's pot for a ladder row (no % while it is unread), none for the stops.
"""
import re

from botdata import fixes as _fixes
from botdata import paths as _paths
from botdata.fmt import usd
from phone.command import Command, declare
from phone.html import MAX_LEN, Html, esc, i_

SHOWN = 3                                         # the last engagements of each change (when they fit)
HEAD = "🔧 <b>Pin changes</b> (every live change: times engaged, net $ so far)"
NOTE = ("net = what the change made or saved (+) or cost or gave up (-) against never making it, fee and losses in, "
        "on settled markets · open = not settled yet · an UNDONE rule's net ends at its undo; the undo's money (vs "
        "keeping the rule) is beside it, not in the total · the total is pin's only, leaves J out and takes B's "
        "cap-made extra legs once (C counts them too)")
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


def _pct(x, bank, of="the bank"):
    if not bank:
        return ""
    return " (%s%.2f%% of %s)" % ("+" if x >= 0 else "-", abs(x) / bank * 100, of)


def base_of(c, bank):
    """(the $ a row's % is of, its words): pin's bank for a pin row; the ladder's pot for a ladder row (LAD, O, Q:
    fixes' change["pot"], (None, ...) while no ladder log names it -- never pin's bank); none for the stops (STOP)."""
    g = c.get("group") or "pin"
    if g == "pin":
        return bank, "the bank"
    if g == "ladder":
        return c.get("pot"), "the ladder's pot"
    return None, ""


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


def net_line(c, bank):
    """The row's net line, never cut at any shrink step: '🔴 net <b>-$25.12</b> (-0.64% of the bank)'; B's adds the
    share of it C counts too ('· of it +$11.57 is C's extra legs too': fixes' overlap_usd, the extra legs only the cap
    made happen; the total takes them once); an UNDONE rule's carries both periods, each with its own
    dot and % -- '🔴 with the rule: net <b>-$57.50</b> (..) · 🟢 since the undo (vs keeping it): <b>+$3.10</b> (..) on 2
    bets' -- the bold net the rule's money against never making it (fixes' net_usd), the undo's beside it."""
    x = c["net_usd"]
    u = c.get("undo") or {}
    bank, of = base_of(c, bank)
    if u.get("since"):
        y = _fixes._f(u.get("net_usd"))
        return "%s with the rule: net <b>%s</b>%s · %s %s: <b>%s</b>%s %s" % (
            _mark(x), esc(usd(x)), esc(_pct(x, bank, of)), _mark(y), esc(_fixes.UNDO_WORDS), esc(usd(y)),
            esc(_pct(y, bank, of)), esc(_fixes.undo_counted(c)))
    line = "%s net <b>%s</b>%s" % (_mark(x), esc(usd(x)), esc(_pct(x, bank, of)))
    ov = _fixes._f(c.get("overlap_usd"))
    if abs(ov) > 0.004:
        line += " · of it %s is C's extra legs too" % esc(usd(ov))
    return line


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
    u = c.get("undo") or {}
    if c.get("fixed"):
        out.append("since %s · measured once, to %s (not running)" % (esc(c["since"]), esc(_fixes.et_words(_fixes.RETRO_T))))
    else:
        out.append("since %s%s" % (esc(c["since"]), (" · UNDONE %s" % esc(u["since"])) if u.get("since") else
                                   (" · DROPPED %s" % esc(c["dropped"])) if c.get("dropped") else ""))
    if c.get("off") and not c["engaged"]:
        out.append("in the build but switched OFF (the launcher leaves --late-bypass-fix off): nothing to count")
        return out
    if not c["engaged"] and not u.get("since") and not c.get("fixed") and not c.get("dropped"):
        out.append("not engaged yet")
        return out
    if c.get("fixed"):
        pass
    elif c["engaged"]:
        out.append("engaged %d time%s, last %s%s" % (c["engaged"], "" if c["engaged"] == 1 else "s",
                                                     esc(c["last_engaged"] or "?"),
                                                     (" · %d open" % c["open"]) if c["open"] else ""))
    else:
        out.append("not engaged" + (" while the rule was on" if (u.get("since") or c.get("dropped")) else " yet"))
    out.append(net_line(c, bank))
    if extra_cut != 0:                                   # K: the skips without the rule, the window with and without;
        #                                                   L: what the shadowed jump hedge would have paid / saved / made;
        #                                                   M: the held-back contracts and the true 3rd bet (not in its net)
        #                                                   (k, n): only each row's first k lines, cut to n -- P's net,
        #                                                   K's and WS's skips, LAD's and STOP's assumptions;
        #                                                   (k, n, "fixed"): only the measured-once rows' (LAD, STOP)
        lines = list(c.get("extra") or [])
        if isinstance(extra_cut, tuple):
            if len(extra_cut) > 2 and extra_cut[2] == "fixed" and not c.get("fixed"):
                lines = []
            lines, extra_cut = lines[:extra_cut[0]], extra_cut[1]
        out += [esc(_cut(x, extra_cut)) for x in lines]
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
# The (k, n) steps came with WS, LAD and STOP (19 rows, 11-14): on the real logs the blocks with every line cut to 120
# ran over one message, so each row keeps its FIRST line (P's net, K's and WS's skips without the rule, the measured
# figure's range) before the lines go altogether. The money that must never go (an undone rule's 'since the undo',
# B's share C counts too) is on the NET LINE itself since the 11-14 review (on the server's logs plus a day of undo
# events the page fell from (1, 90) straight to no lines at all): the (1, 60) and (1, 40) steps keep each row's first
# words a while longer, then (1, 90, "fixed") keeps only the measured-once rows' assumption lines (LAD's fill model and
# range, STOP's ~2.2%/day: an estimate says what it rests on), before the last step drops every line under a net.
PLAN = ((SHOWN, None, None, None), (2, None, None, None), (1, None, None, None), (1, 110, None, None),
        (1, 60, None, None), (1, 30, None, None), (1, 30, 120, None), (0, None, None, None), (0, None, 120, None),
        (1, 30, 120, 0), (0, None, None, 0), (0, None, 120, 0), (0, None, (2, 100), 0), (0, None, (1, 120), 0),
        (0, None, (1, 90), 0), (0, None, (1, 60), 0), (0, None, (1, 40), 0), (0, None, (1, 90, "fixed"), 0),
        (1, 30, 0, None), (0, None, 0, None), (0, None, 0, 0))


def total_lines(changes, bank):
    """The page's last line(s): PIN'S changes only -- '🔴 <b>Pin's changes: net -$81.76</b> (-2.07% of pin's bank) ·
    engaged N times · K open · the undos (vs keeping the rules): +$30.23' -- then, never summed into it, 'Ladder's
    changes (not pin): +$123.40 (+8.63% of the ladder's pot) · stops: +$27.90' (the ladder's % only while its pot is
    read; the stops' figure has none)."""
    T = _fixes.totals(changes)
    g = T.get("groups") or {}
    x = T.get("pin_net_usd", g.get("pin", 0.0))
    n, k = T.get("pin_engaged", T["engaged"]), T.get("pin_open", T["open"])
    line = "%s <b>Pin's changes: net %s</b>%s · engaged %d time%s%s" % (
        _mark(x), esc(usd(x)), esc(_pct(x, bank, "pin's bank")), n, "" if n == 1 else "s",
        (" · %d open" % k) if k else "")
    if T.get("undos"):                                    # beside the total, never in it (vs keeping the rules)
        line += " · the undos (vs keeping the rules): %s%s" % (esc(usd(T["undo_usd"])), (" · %d open" % T["undo_open"])
                                                              if T.get("undo_open") else "")
    other = []
    if "ladder" in g:
        lx = T.get("ladder_net_usd", g["ladder"])
        other.append("Ladder's changes (not pin): %s%s" % (esc(usd(lx)), esc(_pct(lx, T.get("ladder_pot"),
                                                                                  "the ladder's pot"))))
    if "stops" in g:
        other.append("stops: %s" % esc(usd(T.get("stops_net_usd", g["stops"]))))
    return line + (("\n" + " · ".join(other)) if other else "")


def render(d, ctx):
    changes, bank = d["changes"], d.get("bank")
    total = total_lines(changes, bank)
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
