"""activity.py -- what each bot DID today by its own log (activity) and every bot's FILLS (fill_of, fills_since),
each counted by the bot's registry hooks (research/bots/<name>.py: activity / activity_note / halt_why, Records).

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata).
"""
import os

import bots as _reg
import pinledger
from bots import jumpband as _b_jb
from botdata import logs as _logs
from botdata import money as _money
from botdata import paths as _paths
from botdata import tables as _tables
from botdata.clock import et_clock
from botdata.fmt import num as _num, usd


def _halt_why(r):
    """A halt record in words from the bots' own halt_why hooks (only the jump band has one: its day_stop / stop_line
    records), else ''. v-tg-rebuild step 3 (2026-10-30): asked of EVERY bot's halt records, exactly as botstats always
    asked _jb_why -- a record of another bot never has the jump band's fields, so this only ever names the jump band's."""
    for b in _reg.all_bots():
        if b.halt_why is not None:
            w = b.halt_why(r)
            if w:
                return w
    return ""


def activity(name, since):
    """Counts from the bot's own log since `since` (midnight ET): what it DID, not what it made.
    v-tg-rebuild step 3 (2026-10-30): the per-bot counting is each bot's own activity hook (research/bots/<name>.py,
    the old elif bodies verbatim) and its note its activity_note hook; the log is its Logs (pin: every pinrun-live-*.jsonl
    written since `since`)."""
    b = _reg.get(name)
    if b.logs.glob:
        paths = [p for p in _logs.pin_logs() if os.path.getmtime(p) >= since]
        if not _logs.pin_logs():
            paths = None
    else:
        p = os.path.join(_paths.RESULTS, _tables.SPEC[name]["log"])
        paths = [p] if os.path.exists(p) else None
    out = {"ok": paths is not None, "source": None, "sent": 0, "filled": 0, "contracts_filled": 0.0,
           "not_filled": 0, "refused": 0, "refused_why": {}, "cancelled": 0, "hedges": 0,
           "halts": [], "note": None}
    if paths is None:
        out["note"] = "no log file found"
        return out
    out["source"] = [os.path.basename(p) for p in paths]
    why = {}
    st = {"triggers": 0, "filled_tk": set()}            # the counters a bot's hook keeps across records
    for p in paths:
        for r in _logs.read_since(p, since) or []:
            k = r.get("kind") or r.get("ev")
            if b.activity is not None:
                b.activity(k, r, out, why, st)
            if k in _tables.HALT_KINDS[name] or k in ("stop_file", "exit"):
                w = r.get("why") or r.get("day_pnl") or r.get("run_pnl") or _halt_why(r) or ""
                if k == "exit" and r.get("stopped") is True and not r.get("why"):
                    w = "stop file, its run %s" % usd(_num(r.get("run_pnl")) or 0.0)
                out["halts"].append({"t_et": et_clock(_logs._t_of(r)), "what": k, "why": str(w)[:120]})
    out["refused_why"] = dict(sorted(why.items(), key=lambda kv: -kv[1]))
    out["contracts_filled"] = round(out["contracts_filled"], 2)
    if b.activity_note is not None:
        b.activity_note(out, st)
    return out


_jb_why = _b_jb.jb_why                  # (compatibility name: the jump band's halt words, bots/jumpband.py)


# ---- every bot's FILLS, from its own log (2026-10-26) ------------------------------
# The operator, 2026-10-26: "On /market it lists the last closes can you include which bot made the trades. Also
# anywhere that trades or transactions are listed list the account or which bot." Kalshi's books say which pot a market
# SETTLED in; a fill (what a bot bought, when, at what price) is only in that bot's own log. fills_since reads each
# bot's log backwards from its end (read_since: only the hours asked for, a few hundredths of a second) and tags every
# fill with its bot and its pot. What a bot DID, never money: money stays Kalshi's settlements.
def fill_sub(name, ticker):
    """The pot one of a bot's fills is in: a pot of its own that claims the ticker (the FX taker's currency pairs are
    subaccount 4), else its main pot.  (bots.fill_sub)"""
    return _reg.fill_sub(name, ticker)


def fill_of(name, r):
    """One record of bot `name`'s own log -> {"bot", "sub", "ticker", "what", "side", "contracts", "price", "t", "close",
    "hedge", "act"}, or None when it is not a fill (an order that got nothing, a hedge not executed, any other record).
    `side` is the side bought, 'yes' / 'no', or None when the log does not say; the weather dip-seller SELLS yes
    (act 'sold'). `close` is the market's close (epoch) from its ticker, None for a market without a quarter-hour.
    v-tg-rebuild step 3 (2026-10-30): which records are fills, their contracts field, side field, fixed side and verb
    are the bot's Records in the registry."""
    if not isinstance(r, dict):
        return None
    b = _reg.get(name)
    if b is None:
        return None
    rec = b.records
    k = r.get("kind") or r.get("ev")
    if k not in rec.fills:
        return None
    hedge = rec.hedge is not None and k == rec.hedge
    if hedge and str(r.get("status")) != "executed":
        return None
    n = pinledger.money(r, "n" if hedge else rec.fill_qty)
    if n <= 0:
        return None
    tk = r.get("ticker")
    side = str(r.get("side" if hedge else rec.fill_side) or "").lower()
    px = next((_num(r.get(f)) for f in ("exec_price", "px", "price") if r.get(f) is not None), None)
    close = None
    if tk:
        try:
            import pinflat
            close = pinflat.close_epoch(tk)
        except Exception:                                       # noqa: BLE001
            close = None
    return {"bot": name, "sub": fill_sub(name, tk), "ticker": tk, "what": _money.describe(tk) if tk else "?",
            "side": rec.fixed_side or (side if side in ("yes", "no") else None),
            "contracts": round(n, 2), "price": px, "t": _logs._t_of(r), "close": close, "hedge": hedge,
            "act": rec.act}


def fills_since(since, names=None):
    """(every fill the bots' own logs hold from `since` (epoch) on, oldest first -- fill_of's dicts; {bot: why} for a bot
    whose log is missing or could not be read). The pin bot's logs are every pinrun-live-*.jsonl written since `since`."""
    names = _tables.BOTS if names is None else tuple(names)
    out, unread = [], {}
    for name in names:
        if _reg.get(name).logs.glob:
            logs = _logs.pin_logs()
            paths = []
            for p in logs:
                try:
                    if os.path.getmtime(p) >= since:
                        paths.append(p)
                except OSError:
                    pass
        else:
            p = os.path.join(_paths.RESULTS, _tables.SPEC[name]["log"])
            logs = paths = [p] if os.path.exists(p) else []
        if not logs:
            unread[name] = "no log file found"
        for p in paths:
            rows = _logs.read_since(p, since)
            if rows is None:
                unread[name] = "its log could not be read"
                continue
            for r in rows:
                f = fill_of(name, r)
                if f is not None:
                    out.append(f)
    out.sort(key=lambda f: f["t"] or 0)
    return out, unread
