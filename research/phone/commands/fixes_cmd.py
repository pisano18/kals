"""/fixes (/changes) -- every live pin change: what it does, since when, how many times it engaged, when last, what is
still open, and the net $ so far (+ made or saved, - cost or gave up) with its % of the bank; the last 3 engagements of
each, one line each; then one total line.

v-fixes (2026-11-04; the operator: "track them thoroughly and have a telegram command that makes it very simple to see
times any of them have been engaged and the positive or negative overall result of it"). The numbers are
botdata.fixes.report (pin's own logs, pinrules_watch's scorers for rules A, B, C); nothing here reads Kalshi. The bank
for the % is the ledger's bank now (pindesk.Ledger.bank_at), else the pin bot's own pinrun-live-size.json.
"""
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


def _cut(words, n):
    """`words` at most n characters (an ellipsis closes a cut), or whole when n is None."""
    w = str(words)
    return w if n is None or len(w) <= n else w[:max(1, n - 1)].rstrip() + "…"


def block(c, bank, shown, cut=None):
    """One change: name, what, since, engaged / last, net, the last `shown` events (their words cut to `cut` chars)."""
    out = ["<b>%s %s</b>" % (esc(c["id"]), esc(c["name"])), esc(c["what"])]
    if not c["since"]:
        out.append(c.get("not_live") or "not live yet (comes with the new build)")   # L: its own words (fixes.L_NOT_LIVE)
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
    out += [esc(x) for x in c.get("extra") or []]         # K: the skips without the rule, the window with and without;
    #                                                       L: what the shadowed jump hedge would have paid / saved / made
    for e in c["events"][-shown:] if shown else []:
        out.append("  %s · %s · %s · %s" % (esc(e["et"] or "?"), esc(e["coin"]),
                                         esc(usd(e["usd"]) if e["usd"] is not None else "open"), esc(_cut(e["words"], cut))))
    return out


# how the page shrinks to one message: fewer events first, then shorter event words, then no events (the blocks stay).
# The 30-char step came with L (12 changes): one 60-char event per change no longer fits one message, one 30-char
# event (the time, coin, $ and the first words) still does.
PLAN = ((SHOWN, None), (2, None), (1, None), (1, 110), (1, 60), (1, 30), (0, None))


def render(d, ctx):
    changes, bank = d["changes"], d.get("bank")
    T = _fixes.totals(changes)
    total = "%s <b>All changes: net %s</b>%s · engaged %d time%s%s" % (
        _mark(T["net_usd"]), esc(usd(T["net_usd"])), esc(_pct(T["net_usd"], bank)), T["engaged"],
        "" if T["engaged"] == 1 else "s", (" · %d open" % T["open"]) if T["open"] else "")
    for shown, cut in PLAN:
        out = [HEAD, i_(NOTE)]
        for c in changes:
            out += [""] + block(c, bank, shown, cut)
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
