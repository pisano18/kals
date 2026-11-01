"""hedgeplay.py -- what the BET did and what the HEDGE did, for every pin market (v-hedge-split, 2026-11-01).

THE CLASS THIS FIXES. Kalshi books a hedged market as ONE row (both sides' counts and costs, one fee, one result), and
every phone surface scored that row by its net alone: a market whose bet WON but whose hedge cost a little more than the
bet made was a "loss". On 10-31 the phone said the pin bot lost five times; four of those were bets that won (HYPE 7:30,
HYPE 1:15 PM, ETH 1:30 PM, BTC hourly 11 PM: the jump hedge fired and was not needed, -$0.01 to -$1.20 each) and only one
was a lost bet (NEAR 4:45 PM: -$93.11, the hedge got back $51.80 and the buy after the flip $18.36, -$22.96 net). The
alert for that one printed the market as a single leg ("NO at 62.5c, 194.48 contracts") and hid the YES bet.
The operator, 11-01: "Sure that can be fixed but add a separate area wherever you fix that to show how many times and
what the hedge did so it's still tracked and appreciated."

THE RULE (every phone surface asks this module; phone/tests/test_hedgeplay.py enforces it)
  A market is split ONLY when the bot's own records say which side was the BET: an executed hedge record names the side
  the hedge BOUGHT, so the bet is the other side. No record -> no split, the market keeps today's reading (net < 0 =
  lost). Never a guess.
    bet       the bet side's contracts, average price and dollars
    hedge     the contracts the hedge records bought (capped at what Kalshi holds on that side), their price and dollars
    flip      any other contracts on the hedge's side: the bot's own buys after the market flipped (NEAR 10-31 16:45:
              97 NO at 80c, bought 3 s before the close)
  The market's one fee is shared out by Kalshi's fee shape (contracts x price x (1 - price)), and the last part takes
  the rounding, so bet + hedge + flip == the market's money EXACTLY. Money totals never change.
  kind:  "won"          the market made money (net >= 0)
         "hedge_cost"   the BET WON but the market lost a little: the hedge cost more than the bet made
         "lost_hedged"  the bet lost and the hedge paid some of it back
         (a market not split has kind None: is_loss() falls back to the surface's own net rule; an unhedged pin loss is
          exactly that)
  is_loss(m): a split market counts as lost only when its BET lost; hedge_cost is counted on its own (hedge_costs).
  A tie (value strictly between 0 and 1: the coin race) is never split.

THE HEDGE AREA: tally(markets) -> fired / needed (the bet lost: what the hedge got back of how much the bet lost) / not
needed (what it cost) / net, and the same by trigger ("belief": the odds fell under the hedge line; "jump": the price
jumped 6+ standard deviations right after the fill; "not logged": older records with no trigger). hedge_line() says it.

WHERE THE RECORDS COME FROM. This module is pure. The phone registers the pin bot's hedge records once (set_source: the
pindesk Ledger's `hedges` list, which it refreshes before every command); botdata.report tags the pin bot's markets
with them and phone.shared.markets_from_rows tags the main account's. With no source registered (botstats.py on its
own, the laptop's server_sync) nothing is split and every number is what it was.
"""
from botdata.fmt import usd

KINDS = ("won", "hedge_cost", "lost_hedged")
LOSS_KINDS = ("lost_hedged",)
EPS = 0.004                       # botdata's own "zero-looking amount" (fmt.usd prints +$0.00 inside it)
TRIGGERS = ("belief", "jump", "not logged")
TRIGGER_WORDS = {"belief": "odds hedge", "jump": "jump hedge", "not logged": "trigger not logged"}


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


# ---- the records -> one entry a market ------------------------------------------------------------------------------
def index(records):
    """{ticker: {"side": the side the hedge BOUGHT, "n", "cost", "price", "trigger", "fires", "tau", "belief"}} from
    hedge / hedge_alarm records (pindesk.Ledger.hedges' shape: kind, tk, side, n, price, status, trigger; or the bot's
    raw log records: kind, ticker, ...). Only EXECUTED hedges count; several tries on one market add up. The trigger
    is the first alarm's ('belief' / 'jump'), else 'not logged'."""
    out, alarms = {}, {}
    for g in records or ():
        tk = g.get("tk") or g.get("ticker")
        if not tk:
            continue
        k = g.get("kind")
        if k == "hedge_alarm":
            if tk not in alarms and g.get("trigger") in ("belief", "jump"):
                alarms[tk] = g.get("trigger")
            continue
        if k != "hedge" or str(g.get("status")) != "executed" or g.get("side") not in ("yes", "no"):
            continue
        n = _f(g.get("n"))
        p = _f(g.get("price"), None)
        if n <= 0 or p is None:
            continue
        e = out.get(tk)
        if e is None:
            e = out[tk] = {"side": g["side"], "n": 0.0, "cost": 0.0, "fires": 0, "tau": g.get("tau"),
                           "belief": g.get("belief")}
        if g["side"] != e["side"]:             # a hedge of the hedge: never seen; the first side stays the hedge
            continue
        e["n"] += n
        e["cost"] += n * p
        e["fires"] += 1
    for tk, e in out.items():
        e["price"] = e["cost"] / e["n"] if e["n"] else None
        e["trigger"] = alarms.get(tk, "not logged")
    return out


_SOURCE = {"fn": None, "key": None, "ix": {}}


def set_source(fn):
    """Register where the pin bot's hedge records come from: fn() -> a list of records (the phone: its Ledger's
    `hedges`). None unregisters (nothing is split)."""
    _SOURCE.update(fn=fn, key=None, ix={})


def current():
    """The registered records as index(), remembered while the list is the same list with the same length."""
    fn = _SOURCE["fn"]
    if fn is None:
        return {}
    try:
        recs = fn()
    except Exception:                                   # noqa: BLE001 -- a broken source splits nothing, never breaks a page
        recs = None
    if not recs:
        _SOURCE.update(key=None, ix={})
        return {}
    key = (id(recs), len(recs))
    if _SOURCE["key"] != key:
        _SOURCE.update(key=key, ix=index(recs))
    return _SOURCE["ix"]


def version():
    """A token that changes when the registered records do (a cache keyed on money blocks adds it)."""
    current()
    return _SOURCE["key"]


# ---- one market -----------------------------------------------------------------------------------------------------
def split(yes_n, no_n, yes_cost, no_cost, fee, value, h):
    """The parts of one settled market (Kalshi's per-side counts and costs, its one fee, value = the settlement per YES
    contract 0..1) given its hedge entry h (index()'s). None when it cannot be split: no hedge, a tie, no bet side held,
    or nothing on the hedge's side."""
    if not h or value is None or h.get("side") not in ("yes", "no"):
        return None
    if 0.0 < value < 1.0:
        return None
    hside = h["side"]
    bside = "no" if hside == "yes" else "yes"
    bn, bc = (yes_n, yes_cost) if bside == "yes" else (no_n, no_cost)
    hn_all, hc_all = (yes_n, yes_cost) if hside == "yes" else (no_n, no_cost)
    if bn <= 0 or hn_all <= 0:
        return None
    hn = min(h["n"], hn_all)
    hc = min(hn * (h["price"] or 0.0), hc_all)
    fn_, fc = max(hn_all - hn, 0.0), max(hc_all - hc, 0.0)
    if fn_ < 0.005:
        fn_, fc, hc = 0.0, 0.0, hc_all              # the hedge is everything on that side: its cost is Kalshi's
    vb = value if bside == "yes" else 1.0 - value
    vh = 1.0 - vb

    def w(n, c):
        p = (c / n) if n else 0.0
        return n * p * (1.0 - p)
    ws = [w(bn, bc), w(hn, hc), w(fn_, fc)]
    tot = sum(ws)
    if tot <= 0:
        ns = [bn, hn, fn_]
        tot, ws = sum(ns), ns
    fees = [fee * x / tot for x in ws] if tot else [0.0, 0.0, 0.0]
    bet = bn * vb - bc - fees[0]
    hedge = hn * vh - hc - fees[1]
    flip = fn_ * vh - fc - fees[2]
    net = (yes_n * value + no_n * (1.0 - value)) - yes_cost - no_cost - fee
    if fn_ > 0:
        flip = net - bet - hedge                     # the last part takes the rounding: the parts add up EXACTLY
    else:
        hedge = net - bet
    won = vb >= 0.5
    kind = "won" if net >= 0 else ("hedge_cost" if won else "lost_hedged")
    return {"kind": kind, "bet_won": won, "net": net,
            "bet": {"side": bside, "n": bn, "price": bc / bn, "money": bet},
            "hedge": {"side": hside, "n": hn, "price": (hc / hn) if hn else None, "money": hedge,
                      "trigger": h.get("trigger") or "not logged", "fires": h.get("fires", 1)},
            "flip": ({"side": hside, "n": fn_, "price": fc / fn_, "money": flip} if fn_ > 0 else None)}


def _value_of(row_value, result):
    if row_value is not None:
        v = _f(row_value, None)
        if v is not None and 0.0 <= v <= 100.0:
            return v / 100.0
    r = str(result or "").strip().lower()
    return 1.0 if r == "yes" else (0.0 if r == "no" else None)


def split_row(s, h):
    """split() of a Kalshi settlement row (pinledger's field names)."""
    if not h:
        return None
    return split(_f(s.get("yes_count_fp")), _f(s.get("no_count_fp")), _f(s.get("yes_total_cost_dollars")),
                 _f(s.get("no_total_cost_dollars")), _f(s.get("fee_cost")), _value_of(s.get("value"), s.get("market_result")),
                 h)


def tag(m, parts):
    """Put a split on a market dict (botdata's or phone.shared's): m["kind"], m["play"] (the parts). A market not split
    is left exactly as it was."""
    if parts:
        m["kind"] = parts["kind"]
        m["play"] = parts
    return m


# ---- the rule every surface asks ------------------------------------------------------------------------------------
def _net(m, key):
    if key is not None:
        return _f(m.get(key))
    return _f(m["money"] if "money" in m else m.get("pnl"))


def is_loss(m, key=None, eps=EPS):
    """A LOST market: a split one only when its bet lost (and it lost money); any other market by the surface's own
    net rule (net < -eps; pass eps=0 for 'net < 0')."""
    v = _net(m, key)
    if m.get("kind") is not None:
        return m["kind"] in LOSS_KINDS and v < -eps
    return v < -eps


def is_hedge_cost(m, key=None, eps=EPS):
    """The bet won but the hedge cost more than it made (the market lost money)."""
    return m.get("kind") == "hedge_cost" and _net(m, key) < -eps


def counts(ms, key=None, eps=EPS):
    """(lost, hedge_costs) over markets ms."""
    lost = sum(1 for m in ms if is_loss(m, key, eps))
    return lost, sum(1 for m in ms if is_hedge_cost(m, key, eps))


def lost_words(lost, hedge_costs, unit="lost"):
    """'1 lost, 4 hedge costs' -- or '5 lost' when there is no hedge cost (today's words, unchanged)."""
    if not hedge_costs:
        return "%d %s" % (lost, unit)
    return "%d %s, %d hedge cost%s" % (lost, unit, hedge_costs, "" if hedge_costs == 1 else "s")


def lost_cell(lost, hedge_costs, markets):
    """A table's 'Lost' cell: '5/114' as before, '1+4h/114' when hedge costs are split out ('h' = hedge cost)."""
    if not hedge_costs:
        return "%d/%d" % (lost, markets)
    return "%d+%dh/%d" % (lost, hedge_costs, markets)


# ---- the hedge area -------------------------------------------------------------------------------------------------
def _blank():
    return {"fired": 0, "needed": 0, "got_back": 0.0, "bet_lost": 0.0, "net_needed": 0.0,
            "not_needed": 0, "cost": 0.0, "net": 0.0, "hedge_cost_markets": 0}


def tally(ms):
    """What the hedges did over markets ms (split ones only): {"fired", "needed", "got_back" (what the hedge legs made
    on markets whose bet lost), "bet_lost" (what those bets lost), "net_needed" (those markets' net), "not_needed",
    "cost" (what the hedge legs lost on markets whose bet won), "net" (every hedge leg added), "hedge_cost_markets",
    "by_trigger": {trigger: the same}} or None when no market in ms was split."""
    tot, by = _blank(), {}
    for m in ms:
        p = m.get("play")
        if not p:
            continue
        hv = p["hedge"]["money"]
        for t in (tot, by.setdefault(p["hedge"]["trigger"], _blank())):
            t["fired"] += 1
            if p["bet_won"]:
                t["not_needed"] += 1
                t["cost"] += hv
                if p["kind"] == "hedge_cost":
                    t["hedge_cost_markets"] += 1
            else:
                t["needed"] += 1
                t["got_back"] += hv
                t["bet_lost"] += p["bet"]["money"]
                t["net_needed"] += p["net"]
            t["net"] += hv
    if not tot["fired"]:
        return None
    tot["by_trigger"] = {k: by[k] for k in TRIGGERS if k in by}
    return tot


def hedge_line(t, emoji=True):
    """'🛡️ Hedges: 5 fired · 1 needed: got back $51.80 of a $93.11 loss · 4 not needed: cost $6.53 · net +$45.27'
    (the hedge legs' own money), or None when nothing was hedged."""
    if not t:
        return None
    bits = ["%s%d fired" % ("🛡️ Hedges: " if emoji else "Hedges: ", t["fired"])]
    if t["needed"]:
        bits.append("%d needed: got back %s of a %s loss" % (t["needed"], usd(t["got_back"]).lstrip("+"),
                                                           usd(-t["bet_lost"]).lstrip("+")))
    if t["not_needed"]:
        bits.append("%d not needed: cost %s" % (t["not_needed"], usd(-t["cost"]).lstrip("+")))
    bits.append("net %s" % usd(t["net"]))
    return " · ".join(bits)


def part_words(p, what):
    """'bet YES 97.24 at 95.4c -> lost -$93.11' for a part of a split ('bet', 'hedge', 'flip')."""
    x = p[what]
    if x is None:
        return None
    label = {"bet": "bet", "hedge": "hedge", "flip": "after the flip"}[what]
    if what == "bet":
        res = "won" if p["bet_won"] else "lost"
    else:
        res = "won" if not p["bet_won"] else "lost"
    return "%s %s %g at %.1fc → %s %s" % (label, x["side"].upper(), round(x["n"], 2), 100.0 * (x["price"] or 0.0), res,
                                         usd(x["money"]))


def play_lines(p):
    """A split market in words, one line a part, then the outcome (plain text; the caller escapes):
        bet YES 97.24 at 95.4c → lost -$93.11
        hedge NO 97.24 at 45.0c (odds hedge) → won +$51.80
        after the flip NO 97.24 at 80.0c → won +$18.36
        market -$22.96: the hedge cut the loss from -$93.11 to -$41.31; the buy after the flip made it -$22.96
    """
    L = [part_words(p, "bet"),
         part_words(p, "hedge").replace(" → ", " (%s) → " % TRIGGER_WORDS.get(p["hedge"]["trigger"], "hedge"), 1)]
    if p["flip"]:
        L.append(part_words(p, "flip"))
    L.append("market %s: %s" % (usd(p["net"]), outcome_words(p)))
    return L


def outcome_words(p):
    """What the hedge did to this market, in one clause."""
    b, h, f = p["bet"]["money"], p["hedge"]["money"], (p["flip"]["money"] if p["flip"] else 0.0)
    if p["bet_won"]:
        if p["net"] < 0:
            return "the bet won; the hedge was not needed and cost %s, more than the bet made" % usd(-h).lstrip("+")
        return "the bet won; the hedge was not needed (cost %s)" % usd(-h).lstrip("+")
    s = "the hedge cut the loss from %s to %s" % (usd(b), usd(b + h))
    if p["flip"]:
        s += "; the buy after the flip made it %s" % usd(b + h + f)
    return s


__all__ = ["KINDS", "LOSS_KINDS", "TRIGGERS", "TRIGGER_WORDS", "index", "set_source", "current", "version", "split",
           "split_row", "tag", "is_loss", "is_hedge_cost", "counts", "lost_words", "lost_cell", "tally", "hedge_line",
           "part_words", "play_lines", "outcome_words"]
