"""/open -- open bets in EVERY pot: the pin bot's own (from its log, with the seconds to each close), then every other
bot's from Kalshi's positions (botstats), with what is at risk and its share of that bot's cash.

v-tg-rebuild step 9, lane D2 (2026-10-30): Phone.text_open as a command module (load + render), byte-identical (golden
shadow). No wall around the whole (as before); the other bots' part has its own: any error there costs only those lines
('could not read: the other bots ...'), the traceback logged.
"""
import traceback

import pinflat
from phone.command import Command, declare
from phone.html import Html, esc, i_, pre, table
from phone.log import log
from phone.render.botcards import DESK_BOT, _active_of, _cash, nice_coin
from pindesk import close_et


def load(ctx):
    """{'pin': [(ticker, contracts, close words, close epoch, now)], 'a': all_bots or None, 'bs': botstats or None}.
    The reads in Phone.text_open's order: health, the pin bot's open positions, each one's contracts and the clock,
    then botstats (a failure there is logged and leaves 'a' None)."""
    h = ctx.health()
    opn = pinflat.positions(ctx.ledger.newest_rows) if h["alive"] else {}
    pin = []
    for t in opn:
        c = pinflat.close_epoch(t)
        pin.append((t, ctx.ledger.contracts_for(t), close_et(t), c, ctx.now()))
    a = bs = None
    try:
        a = ctx.bs_get("all")
        bs = ctx.bs()
    except Exception:                                           # noqa: BLE001
        log(traceback.format_exc())
        a = None
    return {"pin": pin, "a": a, "bs": bs}


def render(d, ctx):
    pct_of = ctx.pp.pct_of
    L = []
    if d["pin"]:
        rows = []
        for t, n, close_words, c, now in d["pin"]:
            rows.append((nice_coin(t), "x%g" % n, "closes %s" % close_words, "(%d s)" % max(0, (c or 0) - now)))
        L += ["📂 <b>Pin bot: %d open</b>" % len(rows), pre(table(rows, "lrll"))]
    others, unread = [], []
    if d["a"] is None:
        unread.append("the other bots (Kalshi could not be read)")
    else:
        try:
            a, bs = d["a"], d["bs"]
            act = _active_of(a)
            for nm in bs.BOTS:
                if nm == DESK_BOT:                          # its own open bets are listed above (the Ledger)
                    continue
                bt = a["bots"][nm]
                o = bt["open"]
                if nm not in act and not (o["ok"] and o["count"]):
                    continue                             # v-tg-active: a hidden bot only if it still holds a bet
                label = bt["label"] if nm in act else "Earlier bot (not running)"
                if not o["ok"]:
                    unread.append(label.lower())
                    continue
                if not o["count"]:
                    continue
                cash = (bt.get("balance") or {}).get("dollars")
                others.append("📂 <b>%s: %d open</b> · %s at risk%s" % (
                    esc(label), o["count"], esc(_cash(o["at_risk"])),
                    (" (%s of its cash)" % esc(pct_of(o["at_risk"], cash + o["at_risk"], 1))) if cash else ""))
                for p_ in o["positions"][:8]:
                    others.append("  %s %s x%g · %s" % (esc(p_["what"]), esc(str(p_["side"]).upper()), p_["contracts"],
                                                       esc(_cash(p_["at_risk"]))))
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            unread.append("the other bots (Kalshi could not be read)")
    L += others
    if not L:
        L.append("📂 <b>No open bets</b> in any pot.")
    if unread:
        L.append(i_("could not read: %s" % ", ".join(unread)))
    return Html("\n".join(L))


COMMAND = declare(Command(
    names=("/open",), section="now", order=20,
    help_line="/open — open bets in every pot",
    chart=None, load=load, render=render))
