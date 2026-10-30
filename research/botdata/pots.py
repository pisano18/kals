"""pots.py -- THE POT (2026-10-02): what each bot's money is a percentage OF. See botstats' docstring, "THE POT".
Every figure is from Kalshi: cash by pool, open bets' cost, settlements, deposits, withdrawals, subaccount transfers. A
pot that cannot be worked out from one consistent read is None with the reason -- never a guess.

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata).
"""
import pinxfer
from botdata import kalshi as _kalshi
from botdata import money as _money
from botdata import tables as _tables
from botdata.clock import day_start, shift_day
from botdata.fmt import num as _num, usd


# ---- the pot (2026-10-02): what each bot's money is a percentage OF ------------
# See "THE POT" in botstats' docstring. Every figure here is from Kalshi: cash by pool, open bets'
# cost, settlements, deposits, withdrawals, subaccount transfers. Nothing is guessed: a pot that cannot
# be worked out from one consistent read is None with the reason.
MIN_POT = 1.0                   # a pot under $1 is no base for a percentage
POT_CHECK = 1.0                 # cash + open bets vs money put in + all settled: off by more -> said


def _int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def flows(led, sub, t0=None, t1=None):
    """Net dollars moved INTO pot `sub` ('0', '1', '2'; None = the whole account) at or after epoch t0
    and before t1 (None = unbounded; both None = all time, undated records included). Deposits
    (finished, after Kalshi's fee -- pinxfer's rules) and withdrawals land in the main account;
    subaccount transfers move money between pots and cancel out for the whole account."""
    if isinstance(sub, tuple):                                   # a bot with several pots: their flows added
        return sum(flows(led, s, t0, t1) for s in sub)

    def inside(t):
        if t0 is None and t1 is None:
            return True
        return t is not None and (t0 is None or t >= t0) and (t1 is None or t < t1)
    net = 0.0
    if sub in (None, "0"):
        for r in led.get("deposits") or []:
            if pinxfer.is_done(r) and inside(pinxfer.when(r)):
                net += pinxfer.net_cents(r) / 100.0
        for r in led.get("withdrawals") or []:
            if pinxfer.is_done(r) and inside(pinxfer.when(r)):
                net -= abs(pinxfer.net_cents(r)) / 100.0
    if sub is not None:
        for r in led.get("transfers") or []:
            if not inside(_int(r.get("created_ts"))) or not xfer_in_pot(r, sub):
                continue
            a = (_num(r.get("amount_cents")) or 0.0) / 100.0      # cents, by the field's name
            if str(r.get("to_subaccount")) == sub:
                net += a
            if str(r.get("from_subaccount")) == sub:
                net -= a
    return net


def xfer_in_pot(r, sub):
    """True when subaccount transfer `r` is pot `sub`'s: any pool, except a POT_POOL_ONLY pot's own pool only."""
    return sub not in _tables.POT_POOL_ONLY or _int(r.get("exchange_index")) == _tables.POT_POOL_ONLY[sub]


def pot_rows(x, sub, own=True):
    """Pot `sub`'s settled rows (x = c['subs'][sub]): all of them, except that a POT_POOL_ONLY pot's own view keeps
    only its bot's (subaccount 4: the FX pairs, not the old reward test's coin legs; subaccount 3: the jump band's coins,
    not the weather dip-seller's brackets -- POT_OWNER)."""
    rows = list((x.get("rows") or {}).values())
    if own and sub in _tables.POT_POOL_ONLY:
        rows = [r for r in rows if _tables.owner(r.get("ticker"), sub) == _tables.POT_OWNER[sub]]
    return rows


def _cash_all_pools(led, sub, bal_dollars, own=False):
    """(dollars, why): pot `sub`'s cash summed over EVERY pool -- a new deposit can sit in pool 0, where
    the pool-2 balance never sees it (v-onepool). The listing's field is `balance`, a name that does not
    say its unit (hard rule 5), so it is trusted only when its figure for the pot's own trading pool
    (SUB_POOL: 2, or 0 for the weather pot) equals /portfolio/balance's `balance_dollars` for the same pot
    and pool to the cent; otherwise None, never a guess. Rows are matched on subaccount number, so
    another pot's row in the same pool (subaccounts 1 and 2 sit, empty, in pool 0 too) is never counted
    here."""
    vals = {}
    pool = _tables.SUB_POOL[sub]
    for r in led.get("subaccount_balances") or []:
        if str(r.get("subaccount_number")) != sub:
            continue
        v, ix = _num(r.get("balance")), _int(r.get("exchange_index"))
        if v is None or ix is None:
            return None, "the %s's cash listing is unreadable" % _tables.SUB_NAME[sub]
        if own and sub in _tables.POT_POOL_ONLY and ix != _tables.POT_POOL_ONLY[sub]:
            continue                                     # the other pool's side of the number is not this pot's
        vals[ix] = vals.get(ix, 0.0) + v
    if pool not in vals:
        return None, "Kalshi listed no pool-%d cash for the %s" % (pool, _tables.SUB_NAME[sub])
    if bal_dollars is None or abs(vals[pool] - bal_dollars) > 0.011:
        # Two reads a few seconds apart: a bet filling between them trips this as surely as a unit change
        # does, so the words name both and promise nothing about which (2026-10-02 verifier).
        return None, ("the two cash reads of the %s disagree (%s vs %s) -- a bet filled between them, or the "
                      "unit is not what it seems -- so it is left out until the next read (within a minute)"
                      % (_tables.SUB_NAME[sub], vals[pool], bal_dollars))
    return sum(vals.values()), None


def _pot_now(c, sub, own=False):
    """(dollars, why): pot `sub` NOW = its cash in every pool + what its open bets cost (fees paid on
    them included), every figure from the SAME refresh. (`balance_dollars` is gross of resting orders --
    measured 2026-09-06 -- so a resting bid does not move it.) own=True: a POT_POOL_ONLY pot's own pool and
    its own bot's bets only."""
    x = (c.get("subs") or {}).get(sub) or {}
    led = c.get("ledgers") or {}
    t = x.get("tried")
    if t is None:
        return None, "Kalshi has not been read yet"
    if not x.get("complete"):
        return None, "its history is still loading"
    if x.get("err") or x.get("fetched") != t:
        return None, "the last settlements read failed"
    if x.get("pos_err") or x.get("pos_t") != t or x.get("positions") is None:
        return None, "the last open-bets read failed"
    if x.get("bal_err") or x.get("bal_t") != t or x.get("balance") is None:
        return None, "the last cash read failed"
    if led.get("err") or led.get("fetched") != t:
        return None, led.get("err") or "the deposit and transfer books were not read with the rest"
    cash, why = _cash_all_pools(led, sub, x["balance"], own)
    if cash is None:
        return None, why
    ps = [p for p in x["positions"] if not (own and sub in _tables.POT_POOL_ONLY and _tables.owner(p.get("ticker"), sub) != _tables.POT_OWNER[sub])]
    return cash + sum(float(p.get("at_risk") or 0.0) + float(p.get("fees") or 0.0) for p in ps), None


def pot_context(c, today):
    """What every pot percentage in one report needs, worked out once: per pot its value now (or why
    not) and its settled money by ET close day -- EVERY market in the pot, whichever bot's -- plus the
    account's books."""
    ctx = {"today": today, "led": c.get("ledgers") or {}, "subs": {}, "as_of": None, "stale_why": None}
    cur = {sub: _pot_now(c, sub) for sub in _tables.SUBS}
    # A failed read: every pot from the last pass where ALL of them read (one moment, so the pots still add up),
    # with only the markets settled by then -- each window's start is worked back from that moment.
    g = c.get("good") or {}
    last = max([float(((c.get("subs") or {}).get(s) or {}).get("tried") or 0.0) for s in _tables.SUBS])
    if any(v is None for v, _w in cur.values()) and isinstance(g.get("pots"), dict) \
            and all(s in g["pots"] for s in _tables.SUBS) and g.get("t") and 0.0 <= last - float(g["t"]) <= _kalshi.GOOD_MAX_S:
        ctx["as_of"] = float(g["t"])
        ctx["stale_why"] = next(("%s: %s" % (_tables.SUB_NAME[s], cur[s][1]) for s in _tables.SUBS if cur[s][0] is None), None)
    for sub in _tables.SUBS:
        x = (c.get("subs") or {}).get(sub) or {}
        now_v, why = (float(g["pots"][sub]), None) if ctx["as_of"] is not None else cur[sub]
        ctx["subs"][sub] = {"now": now_v, "why": why, "days": _days_of(pot_rows(x, sub, own=False), ctx["as_of"]),
                            "complete": bool(x.get("complete"))}
        if sub in _tables.POT_POOL_ONLY:                     # the bot's own pot: its pool only (POT_POOL_ONLY)
            if ctx["as_of"] is None:
                ov, ow = _pot_now(c, sub, own=True)
            elif (sub + ":own") in g["pots"]:
                ov, ow = float(g["pots"][sub + ":own"]), None
            else:
                ov, ow = None, "the last good read did not keep its pool-%d side" % _tables.POT_POOL_ONLY[sub]
            ctx["subs"][sub]["own"] = {"now": ov, "why": ow, "days": _days_of(pot_rows(x, sub), ctx["as_of"]),
                                       "complete": bool(x.get("complete"))}
    return ctx


def _days_of(rows, as_of):
    """{ET close day: settled $} over `rows`, leaving out what settled after `as_of` (when set)."""
    days = {}
    for s in rows:
        m = _money.market(s)
        if as_of is not None and m["t"] is not None and m["t"] > as_of:
            continue
        days[m["day"]] = days.get(m["day"], 0.0) + m["money"]
    return days


def _pv(ctx, s, sub):
    """Pot s's numbers for a report on `sub`: all pots (None) read the whole subaccount, a bot's pot its own view."""
    p = ctx["subs"][s]
    return p if sub is None else (p.get("own") or p)


def pot_for(ctx, sub, key):
    """(dollars, kind, why): the base of window `key`'s percentage for pot `sub` (None = all pots).
    kind 'start': what the pot held when the window began, + money moved into it during the window;
    kind 'money_in': all time -- the net money put in."""
    led = ctx["led"]
    subs = _tables.SUBS if sub is None else (sub if isinstance(sub, tuple) else (sub,))
    kind = "money_in" if key == "all_time" else "start"
    for s in subs:
        if not ctx["subs"][s]["complete"]:
            return None, kind, "the %s's history is still loading" % _tables.SUB_NAME[s]
    if key == "all_time":
        if led.get("err") or not led.get("fetched"):
            return None, kind, led.get("err") or "the deposit and transfer books are not read yet"
        v = flows(led, sub)
        if v < MIN_POT:
            return None, kind, "no money put in (%s)" % usd(v)
        return v, kind, None
    first, end = _money.window_span(key, ctx["today"])
    now_v = settled = 0.0
    for s in subs:
        p = _pv(ctx, s, sub)
        if p["now"] is None:
            return None, kind, (("%s: %s" % (_tables.SUB_NAME[s], p["why"])) if sub is None else p["why"])
        now_v += p["now"]
        settled += sum(v for d, v in p["days"].items() if d and d >= first)
    t0 = day_start(first)
    cut = ctx.get("as_of")
    if cut is not None and t0 > cut:
        return None, kind, "Kalshi has not answered a full read since before this window began (%s)" % ctx.get("stale_why")
    start = now_v - settled - flows(led, sub, t0, cut)
    if start < -MIN_POT:
        return None, kind, "it works back to %s at the start, so a read was out of step" % usd(start)
    pot = max(0.0, start) + max(0.0, flows(led, sub, t0, day_start(end) if end else None))
    if pot < MIN_POT:
        return None, kind, "the pot held under $1 then"
    return pot, kind, None


def attach_pots(block, ctx, sub):
    """Give each window of a money block its pot: pot ($), pot_kind, pot_of, pot_pct (% of the pot), pot_why."""
    for k in _money.WINDOW_KEYS:
        w = block.get(k)
        if not w:
            continue
        pot, kind, why = pot_for(ctx, sub, k)
        w["pot"] = None if pot is None else round(pot, 2)
        w["pot_kind"], w["pot_why"] = kind, why
        w["pot_of"] = _tables.sub_name(sub)
        w["pot_pct"] = round(100.0 * w["money"] / pot, 2) if (pot is not None and w["markets"]) else None
        w["pot_as_of"] = ctx.get("as_of") if pot is not None and kind == "start" else None
    # 2026-10-22: each of the 7 days as a % of what the pot held THAT day (+ money moved in that day), so an
    # average day is not divided by a later deposit (the ladder's $550 on 10-22 made its week read 0.14%/day)
    for d in (block.get("days_7") or []) + (block.get("days_30") or []):
        pot = day_pot(ctx, sub, d["day"])
        d["pot"] = None if pot is None else round(pot, 2)
        d["pot_pct"] = round(100.0 * d["money"] / pot, 2) if pot is not None else None
    return block


def day_pot(ctx, sub, day):
    """pot_for's 'start' rule for the single ET day `day`: what pot `sub` (None = all) held at midnight ET starting
    it + money moved in during it. None when it cannot be worked out."""
    led = ctx["led"]
    subs = _tables.SUBS if sub is None else (sub if isinstance(sub, tuple) else (sub,))
    now_v = settled = 0.0
    for s in subs:
        p = _pv(ctx, s, sub)
        if p["now"] is None or not p["complete"]:
            return None
        now_v += p["now"]
        settled += sum(v for d, v in p["days"].items() if d and d >= day)
    t0, t1 = day_start(day), day_start(shift_day(day, 1))
    cut = ctx.get("as_of")
    if cut is not None and t0 > cut:
        return None
    start = now_v - settled - flows(led, sub, t0, cut)
    if start < -MIN_POT:
        return None
    pot = max(0.0, start) + max(0.0, flows(led, sub, t0, t1))
    return pot if pot >= MIN_POT else None


def pot_check(ctx):
    """Per pot and for all: value now - money put in - every settled market. Zero when Kalshi's books
    explain the pot (2026-10-02: main $0.03, subaccounts $0.00). A gap is money moving that no listing
    shows (a reward, a missed deposit), and a window's percentage may be off by up to that much."""
    out = {}
    led = ctx["led"]
    for sub in _tables.SUBS + (None,):
        subs = _tables.SUBS if sub is None else (sub,)
        k = "all" if sub is None else sub
        if any(_pv(ctx, s, sub)["now"] is None for s in subs) or led.get("err") or not led.get("fetched") \
                or ctx.get("as_of") is not None:            # an older moment's pots are no check of today's books
            out[k] = None
            continue
        now_v = sum(_pv(ctx, s, sub)["now"] for s in subs)
        settled = sum(sum(_pv(ctx, s, sub)["days"].values()) for s in subs)
        money_in = flows(led, sub)
        gap = now_v - money_in - settled
        out[k] = {"now": round(now_v, 2), "money_in": round(money_in, 2), "settled": round(settled, 2),
                  "unexplained": round(gap, 2), "off": abs(gap) > POT_CHECK,
                  "of": "all pots" if sub is None else _tables.SUB_NAME[sub]}
    return out
