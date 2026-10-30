"""report.py -- the per-bot report and the all-bots report: bot(name), all_bots(); their money / open / cash blocks,
the 'earlier bots' block (v-tg-active), and _load (the cache brought up to date + the process table, under kalshi.LOCK).

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata).
all_bots() is a contract: the laptop's pindesk reads it from server_bots.json (server_sync), possibly with older code --
additive changes only.
"""
import time

from botdata import activity as _activity
from botdata import kalshi as _kalshi
from botdata import money as _money
from botdata import pots as _pots
from botdata import procs as _procs
from botdata import running as _running
from botdata import status as _status
from botdata import tables as _tables
from botdata.clock import day_label, day_start, et_clock, et_day, shift_day
from botdata.fmt import usd


# ---- the per-bot report ------------------------------------------------------
def _money_block(c, name, today, ctx=None):
    subs = _tables.bot_subs(name)                      # 2026-10-25: the FX taker trades from two pots (5 and 4)
    sub = subs[0]
    xs = [(s, (c.get("subs") or {}).get(s) or {}) for s in subs]
    x = xs[0][1]
    have = any(bool(y.get("fetched")) or bool(y.get("rows")) for _, y in xs)
    err = next((y.get("err") for _, y in xs if y.get("err")), None)
    base = {"ok": have, "subaccount": int(sub), "source": "Kalshi settlements, %s" % _tables.sub_name(subs if len(subs) > 1 else sub),
            "complete": all(bool(y.get("complete")) for _, y in xs), "error": err,
            "as_of_et": et_clock(x.get("fetched")) if x.get("fetched") else None,
            "stale": bool(err) and have}
    if not have:
        for k in ("today", "yesterday", "last_7_days", "this_month", "all_time", "first_day"):
            base[k] = None
        base["days_7"], base["days_30"], base["all_days"], base["markets"] = [], [], [], []
        base["error"] = base["error"] or "Kalshi has not been read yet"
        return base
    ms = [_money.market(s) for sb, y in xs for s in (y.get("rows") or {}).values() if _tables.owner(s.get("ticker"), sb) == name]
    ms.sort(key=lambda m: (m["t"] or 0), reverse=True)
    base.update(_money.windows(ms, today))
    base["markets"] = ms
    _pots.attach_pots(base, ctx if ctx is not None else _pots.pot_context(c, today), subs if len(subs) > 1 else sub)
    base["pot_shared_with"] = [b for b in _tables.BOTS if b != name and _tables.SPEC[b]["sub"] in subs]
    return base


def _earlier_block(c, hidden, today):
    """v-tg-active (2026-10-30): every HIDDEN bot's settled markets as one money block (the shape of _money_block's, no
    pot % -- the bots' pots differ), so a per-bot split still adds up to the all-bots total: 'earlier bots'."""
    subs = [s for s in _tables.SUBS if any(s in _tables.bot_subs(b) for b in hidden)]
    xs = [(s, (c.get("subs") or {}).get(s) or {}) for s in subs]
    have = bool(xs) and all(bool(y.get("fetched")) or bool(y.get("rows")) for _, y in xs)
    err = next((y.get("err") for _, y in xs if y.get("err")), None)
    base = {"ok": have, "names": list(hidden), "label": _status.EARLIER_LABEL, "complete": all(bool(y.get("complete")) for _, y in xs),
            "error": err, "stale": bool(err) and have}
    if not have:
        for k in ("today", "yesterday", "last_7_days", "this_month", "all_time", "first_day"):
            base[k] = None
        base["days_7"], base["days_30"], base["all_days"] = [], [], []
        base["error"] = base["error"] or ("nothing hidden" if not hidden else "Kalshi has not been read yet")
        return base
    hid = set(hidden)
    ms = [_money.market(s) for sb, y in xs for s in (y.get("rows") or {}).values() if _tables.owner(s.get("ticker"), sb) in hid]
    ms.sort(key=lambda m: (m["t"] or 0), reverse=True)
    base.update(_money.windows(ms, today))
    return base


def _open_block(c, name):
    subs = _tables.bot_subs(name)
    xs = [(s, (c.get("subs") or {}).get(s) or {}) for s in subs]
    x = xs[0][1]
    if any(y.get("positions") is None for _, y in xs):
        return {"ok": False, "error": next((y.get("pos_err") for _, y in xs if y.get("pos_err")), None) or "not read yet",
                "positions": [], "count": None, "at_risk": None}
    ps = []
    for sb, y in xs:
        for p in y["positions"]:
            if _tables.owner(p["ticker"], sb) != name:
                continue
            ps.append({"ticker": p["ticker"], "what": _money.describe(p["ticker"]), "side": "yes" if p["net"] > 0 else "no",
                       "contracts": abs(p["net"]), "at_risk": p["at_risk"]})
    err = next((y.get("pos_err") for _, y in xs if y.get("pos_err")), None)
    return {"ok": True, "error": err, "stale": bool(err),
            "as_of_et": et_clock(x.get("pos_t")), "positions": ps, "count": len(ps),
            "at_risk": round(sum(p["at_risk"] for p in ps), 4)}


def _balance_block(c, name):
    subs = _tables.bot_subs(name)
    sub = subs[0]
    xs = [(s, (c.get("subs") or {}).get(s) or {}) for s in subs]
    x = xs[0][1]
    shared = [b for b in _tables.BOTS if b != name and _tables.SPEC[b]["sub"] in subs]
    note = ("shared: the %s's cash sits in the same pot" % " and ".join(_tables.SPEC[b]["label"].lower() for b in shared)
            if shared else "its own pot%s (%s)" % ("s" if len(subs) > 1 else "", _tables.sub_name(subs if len(subs) > 1 else sub)))
    vals = [y.get("balance") for _, y in xs]
    dollars = round(sum(vals), 4) if all(v is not None for v in vals) else None
    return {"ok": dollars is not None, "dollars": dollars, "subaccount": int(sub), "subaccounts": [int(s) for s in subs],
            "by_sub": {s: v for (s, _y), v in zip(xs, vals)} if len(xs) > 1 else None,
            "shared_with": shared, "note": note, "as_of_et": et_clock(x.get("bal_t")),
            "error": next((y.get("bal_err") for _, y in xs if y.get("bal_err")), None)}


def _bot_from(c, name, now, rows, ok, ctx=None):
    today = et_day(now)
    money = _money_block(c, name, today, ctx)
    last = [{"time_et": et_clock(m["t"]), "ticker": m["ticker"], "what": m["what"], "side": m["side"],
             "contracts": m["contracts"], "money": round(m["money"], 4), "put_in": round(m["put_in"], 4),
             "result": m["result"]} for m in (money.get("markets") or [])[:5]]
    money.pop("markets", None)
    out = {"name": name, "label": _tables.SPEC[name]["label"], "what": _tables.SPEC[name]["what"],
           "subaccount": int(_tables.SPEC[name]["sub"]), "subaccounts": [int(s) for s in _tables.bot_subs(name)],
           "shares_subaccount_with": [b for b in _tables.BOTS if b != name and _tables.SPEC[b]["sub"] == _tables.SPEC[name]["sub"]],
           "running": _running.running(name, rows, ok, now), "money": money, "open": _open_block(c, name),
           "balance": _balance_block(c, name), "last_settled": last,
           "activity_today": _activity.activity(name, day_start(today)), "errors": []}
    for k in ("money", "open", "balance"):
        if out[k].get("error"):
            out["errors"].append("%s: %s" % (k, out[k]["error"]))
    # v-tg-active (2026-10-30): a pot it shares with a bot that is not shown is said as its own -- the pin bot's main
    # account while the coin race is paused, subaccount 3 (the jump band's pool 2, the old weather pool 0) -- so a paused
    # or retired bot is never named on another bot's page
    act = _status.active_from(rows, ok)
    out["active"] = list(act)
    out["shares_subaccount_with"] = [b for b in out["shares_subaccount_with"] if b in act]
    if isinstance(money.get("pot_shared_with"), list):
        money["pot_shared_with"] = [b for b in money["pot_shared_with"] if b in act]
    bal = out["balance"]
    sh = [b for b in bal.get("shared_with") or [] if b in act]
    if sh != (bal.get("shared_with") or []):
        subs = _tables.bot_subs(name)
        bal["shared_with"] = sh
        bal["note"] = ("shared: the %s's cash sits in the same pot" % " and ".join(_tables.SPEC[b]["label"].lower() for b in sh)
                       if sh else "its own pot%s (%s)" % ("s" if len(subs) > 1 else "",
                                                         _tables.sub_name(subs if len(subs) > 1 else subs[0])))
    return out


def _load(now, getter, procs):
    """(cache, process rows, ok): the cache brought up to date (kalshi: at most every REFRESH_S) and the process table
    (procs_for), saved once when either changed. v-tg-rebuild step 7 (2026-10-30): under kalshi.LOCK -- the phone's poll
    and chart threads no longer refresh at once (one Kalshi pass, one writer); in readonly mode nothing is asked or
    written."""
    ro = _kalshi.is_readonly()
    with _kalshi.LOCK:
        c = _kalshi.load_cache()
        changed = False if ro else _kalshi.refresh(c, now, getter)
        rows, ok, pchanged = _procs.procs_for(c, now, procs)
        if (changed or pchanged) and not ro:
            _kalshi.save_cache(c)
    return c, rows, ok


def _balances(bots):
    """all_bots' balances: one cash figure a POT (pot_groups), in the order of each pot's first bot (main, forecaster,
    ladder, jumpband, fx), from its key bot's balance block ('main' from the main account's first bot, the pin bot);
    'all' adds them; then every other bot of a subaccount pot keeps that same figure under its own name for older
    readers, never added twice (subaccount 3 is the jump band's pot now and was the weather dip-seller's: 'weather');
    main_holds and pot_bots name who is in which pot."""
    order = {b: i for i, b in enumerate(_tables.BOTS)}
    groups = _tables.pot_groups()
    bal = {}
    for key, names in sorted(groups, key=lambda kv: min(order[b] for b in kv[1])):
        src = names[0] if key == "main" else key
        bal[key] = bots[src]["balance"]["dollars"]
    bal["all"] = round(sum(bal.values()), 4) if all(v is not None for v in bal.values()) else None
    for key, names in groups:
        if key != "main":
            for n in names:
                if n != key:
                    bal[n] = bal[key]
    bal["main_holds"] = list(dict(groups)["main"])
    bal["pot_bots"] = {key: list(names) for key, names in groups}
    return bal


def bot(name, now=None, getter=None, procs=None):
    """One bot's full report (see the module docstring for what each block means)."""
    if name not in _tables.SPEC:
        raise ValueError("unknown bot %r (one of %s)" % (name, ", ".join(_tables.BOTS)))
    now = time.time() if now is None else float(now)
    c, rows, ok = _load(now, getter, procs)
    return _bot_from(c, name, now, rows, ok)


def all_bots(now=None, getter=None, procs=None):
    """Every bot, the `other` main-account markets, and the ALL-BOTS total with each bot's share."""
    now = time.time() if now is None else float(now)
    c, rows, ok = _load(now, getter, procs)
    today = et_day(now)
    ctx = _pots.pot_context(c, today)
    bots = {b: _bot_from(c, b, now, rows, ok, ctx) for b in _tables.BOTS}
    active = _status.active_from(rows, ok)                       # v-tg-active: what the phone lists bot by bot
    hidden = [b for b in _tables.BOTS if b not in active]
    other = _money_block(c, "other", today, ctx)
    other.pop("markets", None)
    other["label"] = "Other main-account markets (the old oil bot, anything unlisted)"
    total, missing = {}, [b for b in _tables.BOTS if not bots[b]["money"]["ok"]] + ([] if other["ok"] else ["other"])
    parts = [(b, bots[b]["money"]) for b in _tables.BOTS] + [("other", other)]
    for w in ("today", "yesterday", "last_7_days", "this_month", "all_time"):
        got = [(b, m[w]) for b, m in parts if m.get(w)]
        mk = sum(x["markets"] for _, x in got)
        money = sum(x["money"] for _, x in got)
        put_in = sum(x["put_in"] for _, x in got)
        total[w] = {"label": got[0][1]["label"] if got else w, "markets": mk,
                    "won": sum(x["won"] for _, x in got), "lost": sum(x["lost"] for _, x in got),
                    "money": round(money, 4), "put_in": round(put_in, 4),
                    "return_pct": round(100.0 * money / put_in, 2) if put_in > 0 else None,
                    "by_bot": {b: round(x["money"], 4) for b, x in got},
                    "by_bot_put_in": {b: round(x["put_in"], 4) for b, x in got},
                    "by_bot_markets": {b: x["markets"] for b, x in got},
                    "by_bot_pot_pct": {b: x.get("pot_pct") for b, x in got},
                    "partial": bool(missing), "missing": missing}
        _pots.attach_pots({w: total[w]}, ctx, None)
        if missing:                                  # money that leaves a pot out is no base for a share
            total[w].update(pot_pct=None, pot_why="these totals leave out %s" % ", ".join(missing))
    days_7 = []
    for k in range(7):
        d = shift_day(today, -k)
        by = {}
        for b, m in parts:
            for x in m.get("days_7") or []:
                if x["day"] == d:
                    by[b] = x
        mo = round(sum(x["money"] for x in by.values()), 4)
        pi = round(sum(x["put_in"] for x in by.values()), 4)
        pot = None if missing else _pots.day_pot(ctx, None, d)
        days_7.append({"day": d, "label": day_label(d), "markets": sum(x["markets"] for x in by.values()),
                       "won": sum(x["won"] for x in by.values()), "lost": sum(x["lost"] for x in by.values()),
                       "money": mo, "put_in": pi, "return_pct": round(100.0 * mo / pi, 2) if pi > 0 else None,
                       "pot": None if pot is None else round(pot, 2),
                       "pot_pct": round(100.0 * mo / pot, 2) if pot else None,
                       "by_bot": {b: x["money"] for b, x in by.items()},
                       "by_bot_pot_pct": {b: x.get("pot_pct") for b, x in by.items()}})
    # the LONG_DAYS full days before today, every bot together (avg_day's rule: a day before the first market on ANY
    # pot's books is left out); each day's % is of what all the pots held when it began (day_pot, the days_7 base)
    firsts = [m.get("first_day") for _b, m in parts if m.get("first_day")]
    days_30 = []
    for k in range(1, _money.LONG_DAYS + 1):
        d = shift_day(today, -k)
        mo = round(sum(x["money"] for _b, m in parts for x in m.get("days_30") or [] if x["day"] == d), 4)
        pot = None if missing else _pots.day_pot(ctx, None, d)
        days_30.append({"day": d, "money": mo, "pot": None if pot is None else round(pot, 2),
                        "pot_pct": round(100.0 * mo / pot, 2) if pot else None,
                        "before_first": not firsts or d < min(firsts)})
    bal = _balances(bots)
    note = ("The main account's cash%s holds the pin bot and the coin race together; the forecaster "
            "(subaccount 2), the ladder (subaccount 1), the jump band (subaccount 3, once the weather dip-seller's) "
            "and the FX taker (subaccounts 5 + 4) are separate pots and are NOT in the main account's cash or "
            "its money totals."
            % (" (%s)" % usd(bal["main"]).lstrip("+") if bal["main"] is not None else ""))
    errors = [("%s: %s" % (b, e)) for b in _tables.BOTS for e in bots[b]["errors"]]
    return {"as_of_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "as_of_et": et_clock(now),
            "today_et": today, "bots": bots, "other": other, "total": total, "total_days_7": days_7,
            "active": list(active), "hidden": hidden, "earlier": _earlier_block(c, hidden, today),
            "total_days_30": days_30,
            "balances": bal, "note": note, "errors": sorted(set(errors)), "pot_check": _pots.pot_check(ctx),
            "pots_as_of": ctx.get("as_of")}
