"""/move -- every pot's cash, and money moved between pots from the phone (a plan, a code, then the transfer).

v-tg-step12 (2026-10-30, lane R; the operator: "telegram controls so I can see each subaccount and send commands to move
money between them myself through telegram ... and everything that needs to would adapt and react to that
automatically"):

  /move                      every account and pool Kalshi lists, with its cash and open bets (/funds' own read, GET
                             only), the word to type for each, and how to move
  /move 50 main jb           a plan: $50 from the main account to the jump band's pot (subaccount 3, crypto pool), each
                             side's cash before and after, the rails it passed, what adapts after; and a 4-digit code
  /move 25 fx main           a bot's word means its main pot (the FX taker: subaccount 5; its currency pairs: sub4)
  /move 20 main pool0 pool2  between the main account's two pools
  /move yes 4821             within 2 minutes: checks again on fresh cash, sends the ONE transfer, reads both sides back
  /move no                   forgets the plan

The work and every rail are phone/actions/money.py's (the only phone code that posts to Kalshi). What adapts after a
move, by itself: the pin bot re-reads its cash and resizes (only while flat); the ladder rescales from its pot; the FX
taker resizes from both its pots as one bank (v-fx-onepot, only while flat); the jump band is fixed size. The phone's money pages read Kalshi's transfer books, so a move shows as money
moved between pots, never as money made (phone/tests/test_move.py proves it on botdata.pots).
"""
import traceback

from botdata.fmt import dollars
from phone.actions import confirm as _confirm
from phone.actions import journal as _journal
from phone.actions import money as _money
from phone.command import Command, declare
from phone.commands.funds.read import funds_read
from phone.html import Html, esc, i_
from phone.log import log
from pindesk import et_day, et_day_start

ASK_TTL_S = 120                 # a plan's code stands 2 minutes
SIZE_AFTER = {                  # what each bot does with more (or less) cash, in words
    "pin": "the pin bot resizes from its cash by itself (it re-reads it every 5 minutes, only while flat; rises damped)",
    "ladder": "the ladder rescales its rungs from its pot by itself",
    "fx": ("the FX taker sizes from both its pots as one bank ($20 a contract; it re-reads the cash every minute and "
           "resizes only while flat, rises damped); each pool's cash still has to cover that pool's bets"),
    "jumpband": "the jump band is fixed size (5 contracts a buy): the cash only has to cover its bets",
}


def moved_today(now):
    """Dollars moved from the phone since midnight ET (results\\phone_actions.jsonl: the moves Kalshi accepted)."""
    t0 = et_day_start(et_day(now))
    return round(sum(float(r.get("amount") or 0.0) for r in _journal.read(kinds=("move",), since=t0) if r.get("ok")), 2)


def _usage(cfg):
    mx, day, margin = _money.limits(cfg)
    return i_("Move: /move 50 main jb (amount, from, to) · /move 25 fx main · between the main account's pools: "
              "/move 20 main pool0 pool2. You get the plan and a code; /move yes CODE within %d minutes sends it. "
              "Limits: %s a move, %s a day; a pot holding open bets keeps their cost + %s in cash."
              % (ASK_TTL_S // 60, dollars(mx), dollars(day), dollars(margin)))


def listing(ctx):
    try:
        f = funds_read(ctx.funds_get())
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        return Html("💸 <b>Move money</b>: Kalshi could not be read (%s).\n%s" % (esc(str(e)[:160]), _usage(ctx.cfg)))
    L = ["💸 <b>Every pot's cash</b> (Kalshi, now)"]
    subs = f.get("subs") or {}
    known = [p.get("dollars") for s in subs.values() for p in (s.get("pools") or {}).values() if p.get("dollars") is not None]
    total = sum(known) if known else None
    for n in sorted(subs):
        s = subs[n]
        for ix in sorted(s.get("pools") or {}):
            p = s["pools"][ix]
            word = _word(n, ix)
            cash = p.get("dollars")
            share = (" (%.0f%% of all cash)" % (100.0 * cash / total)) if cash is not None and total else ""
            L.append("• <b>%s</b> · %s: %s%s" % (esc(word), esc(_money.pot_label(n, ix)),
                                                 esc(dollars(cash) if cash is not None else "could not read"), esc(share)))
        if s.get("open"):
            L.append("   " + i_("open bets in account %d: %s (%d)" % (n, dollars(s["open"]), s.get("open_n") or 0)))
        elif s.get("open_err"):
            L.append("   " + i_("open bets in account %d: could not read (%s)" % (n, s["open_err"])))
    if f.get("list_err"):
        L.append(i_("Kalshi's list of accounts could not be read (%s)" % f["list_err"]))
    if total is not None:
        L.append("Cash in all pots: <b>%s</b>" % esc(dollars(total)))
    L.append(_usage(ctx.cfg))
    return Html("\n".join(L))


def _word(sub, pool):
    """What to type for (sub, pool): 'main' / 'pool0' for the main account, a bot's word or 'subN' for its trading pool,
    'subNpoolP' for one of its other pools (v-fx-onepot; was '-')."""
    if int(sub) == 0:
        return "main" if pool == _money.trades_in(0) else "pool%d" % pool
    if _money.trades_in(sub) not in (None, pool):
        return "sub%dpool%d" % (int(sub), int(pool))
    return _money.word_of(sub, pool)


def _side(sub, pool):
    return "%s (%s)" % (_word(sub, pool), _money.pot_label(sub, pool))


def _adapts(plan):
    out = []
    for sub, pool in (plan["src"], plan["dst"]):
        for b in _money.bots_in(sub, pool):
            w = SIZE_AFTER.get(b.name)
            if w and w not in out:
                out.append(w)
    return out


def plan_reply(ctx, words):
    now = ctx.now()
    try:
        f = funds_read(ctx.funds_get())
        plan = _money.plan_move(words, f, ctx.cfg, now, moved_today(now))
    except _money.Refused as e:
        _confirm.drop(ctx.chat_id, "move")
        return Html("⛔ <b>Not moved</b>: %s.\n%s" % (esc(str(e)), _usage(ctx.cfg)))
    code = _confirm.ask(ctx.chat_id, "move", plan["id"], now, ASK_TTL_S, plan=plan, code=True)
    a = plan["amount"]
    keep = _money.keep_of(plan, ctx.cfg)
    L = ["💸 <b>Move %s</b> from %s to %s?" % (esc(dollars(a)), esc(_side(*plan["src"])), esc(_side(*plan["dst"]))),
         "%s: %s → %s%s" % (esc(_word(*plan["src"])), esc(dollars(plan["src_cash"])), esc(dollars(plan["src_cash"] - a)),
                            esc(" (keeps %s for its open bets)" % dollars(keep) if keep else "")),
         "%s: %s → %s" % (esc(_word(*plan["dst"])), esc(dollars(plan["dst_cash"])),
                          esc(dollars((plan["dst_cash"] or 0.0) + a)))]
    ad = _adapts(plan)
    if ad:
        L.append(i_("After: " + "; ".join(ad) + "."))
    L.append(i_("One %s transfer, checked again on fresh cash before it is sent." % (
        "subaccount" if plan["kind"] == "sub" else "pool-to-pool")))
    L.append("To send it, reply <code>/move yes %s</code> within %d minutes (<code>/move no</code> forgets it)." % (
        code, ASK_TTL_S // 60))
    return Html("\n".join(L))


def send_reply(ctx, code):
    now = ctx.now()
    got, why = _confirm.take(ctx.chat_id, "move", now, code=code)
    if got is None:
        head = {"expired": "That plan has expired.", "code": "That is not the code."}.get(why, "No move is waiting.")
        return Html("%s Nothing moved. Send <code>/move 50 main jb</code> for a new plan." % head)
    plan = got["plan"]
    done = moved_today(now)
    try:
        res = _money.execute(plan, ctx.funds_get(), ctx.cfg, done)
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        _journal.record("move", t=now, chat=ctx.chat_id, ok=False, amount=plan["amount"], src=plan["src"],
                        dst=plan["dst"], path=plan["path"], body=plan["body"], error=str(e)[:200])
        return "The move failed before an answer came back: %s\nCheck /move or /funds before trying again." % str(e)[:200]
    _journal.record("move", t=now, chat=ctx.chat_id, ok=res["ok"], amount=plan["amount"], src=plan["src"],
                    dst=plan["dst"], path=plan["path"], body=plan["body"], status=res["status"], before=res["before"],
                    after=res["after"], why=res["why"])
    b, af = res["before"], res["after"] or (None, None)
    rows = ["%s: %s → %s" % (esc(_word(*plan["src"])), esc(dollars(b[0]) if b[0] is not None else "?"),
                             esc(dollars(af[0]) if af[0] is not None else "?")),
            "%s: %s → %s" % (esc(_word(*plan["dst"])), esc(dollars(b[1]) if b[1] is not None else "?"),
                             esc(dollars(af[1]) if af[1] is not None else "?"))]
    if not res["ok"]:
        return Html("⛔ <b>Not moved</b>: %s.\n%s" % (esc(res["why"]), "\n".join(rows)))
    ad = _adapts(plan)
    return Html("✅ <b>Moved %s</b> from %s to %s.\n%s\n%s" % (
        esc(dollars(plan["amount"])), esc(_side(*plan["src"])), esc(_side(*plan["dst"])), "\n".join(rows),
        i_(("What adapts: " + "; ".join(ad) + ". " if ad else "")
           + "The money pages count it as money moved between pots, not money made.")))


def move(ctx):
    words = ctx.arg.split()
    if not words:
        return listing(ctx)
    if words[0].lower() == "yes":
        return send_reply(ctx, words[1] if len(words) > 1 else "")
    if words[0].lower() == "no":
        _confirm.drop(ctx.chat_id, "move")
        return "Forgotten: nothing moved."
    return plan_reply(ctx, words)


COMMAND = declare(Command(
    # the bare form only reads (Kalshi GET, as /funds); '/move yes <code>' is the one that sends
    names=("/move",), section="controls", order=70,
    help_line="/move — every pot's cash, and move money between them (/move 50 main jb), with a plan and a code",
    chart=None, handle=move, examples=("/move 50 main jb", "/move no")))
