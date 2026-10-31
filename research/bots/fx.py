"""The FX taker (research/cleanroom/fxtake_live.py, 2026-10-25): the 8 commodities from subaccount 5 (pool 2) and the
5 currency pairs from subaccount 4 (pool 0). Every fact copied verbatim from botstats.py / pinphone.py / tgcharts.py at
8a9c5e1 (v-tg-rebuild step 1, 2026-10-30).

v-fx-onepot (2026-10-30): its size comes from both pots as ONE bank. Its start record says how it is laid out:
two-sub (pool 0 from subaccount 4, pool 2 from 5) or one-sub (both pools from 5: subs {"0": 5, "2": 5}, once
subaccount 4 is empty in pool 0 and 5 holds pool-0 cash). In one-sub its /funds size line and its balance-check book
are ONE pot (subaccount 5, every pool); the registry keeps subaccount 4's pot so its past FX-pair trades (claimed by
ticker) stay in FX's money."""
from bots.spec import Book, Bot, Feature, Gauge, Logs, Pot, Records, Speed, VersionRule, live_flag
from botdata.fmt import cents as _c, num as _num, usd

# 4: the FX taker's currency pairs (pool 0, created 2026-10-25 ~21:0xZ). The NUMBER 4 also names the old coin-race reward
# test's pot in pool 2 (stopped 10-23, ~1c left), never counted here: in subaccount 4 only an FX pair is the FX taker's.
FX_PAIRS = frozenset(["KXEURUSD15M", "KXGBPUSD15M", "KXUSDJPY15M", "KXAUDUSD15M", "KXUSDCAD15M"])


def _pairs(series, ticker):
    """botstats.owner, subaccount 4: an FX pair is the FX taker's, anything else 'other'."""
    return series in FX_PAIRS


def settings_fx(start):
    """The FX taker's settings, all from its own start record (fxtake_live.py writes size, fav, cap, entry window, caps).
    (botstats.settings_fx, verbatim)"""
    s = dict(start or {})
    for k in ("t", "kind", "pid", "argv", "series", "minutes"):
        s.pop(k, None)
    bits = []
    if s.get("size") is not None:
        bits.append("%s contracts a market" % s["size"])
    if s.get("fav") is not None and s.get("cap") is not None:
        bits.append("buys the side bid %s+ at %s or less" % (_c(s["fav"]), _c(s["cap"])))
    if s.get("hold_s"):                                  # v-fx-hold5 (2026-10-26)
        bits.append("only once that bid has held %g s" % float(s["hold_s"]))
    if s.get("entry_from") is not None and s.get("entry_to") is not None:
        bits.append("%g to %g s before the close" % (float(s["entry_from"]), float(s["entry_to"])))
    if s.get("max_per_close") is not None:
        bits.append("up to %s markets a quarter-hour, %s in play" % (s["max_per_close"], usd(float(s.get("max_held") or 0)).lstrip("+")))
    if s.get("day_stop") is not None:
        bits.append("stops the day at %s" % usd(float(s["day_stop"])))
    if s.get("bank_sizing") and s.get("bank_per_contract"):      # v-fx-onepot (2026-10-30)
        bits.append("sized from its whole bank (both pools), %s a contract" % usd(float(s["bank_per_contract"])).lstrip("+"))
    if s.get("layout") == "one-sub":
        bits.append("both pools from subaccount %s" % (s.get("subaccount")))
    return s, "; ".join(bits)


def one_sub(r):
    """The subaccount a start record trades BOTH pools from (v-fx-onepot's one-sub layout: {"0": 5, "2": 5}), else None."""
    subs = (r or {}).get("subs") or {}
    vals = set(str(v) for v in subs.values())
    return vals.pop() if len(subs) > 1 and len(vals) == 1 else None


def settings(si):
    return settings_fx(si.start)


# v-tg-settings-now (2026-10-31): fxtake_live resizes from its whole bank by itself (FxTaker.maybe_resize), writing a
# 'resize' record with the new size and the caps that scale with it
RESIZE = ("resize",)


def resize_as_start(r):
    return {k: r.get(k) for k in ("size", "bank", "pool_cash", "bank_per_contract", "max_held", "day_stop",
                                  "stop_line")}


def activity(k, r, out, why, st):
    """botstats.activity's fx branch (verbatim)."""
    import pinledger
    # fxtake_live.py: one immediate-or-cancel buy a market ('placed'), its fill ('fill'), the rule's refusals
    if k == "placed":
        out["sent"] += 1
        if pinledger.money(r, "filled") <= 0:
            out["not_filled"] += 1
    elif k == "fill":
        out["filled"] += 1
        out["contracts_filled"] += pinledger.money(r, "n")
    elif k in ("refused", "dropped", "body_refused"):
        out["refused"] += 1
        g = str(r.get("why") or k)
        why[g] = why.get(g, 0) + 1


# v-tg-rebuild step 5 (2026-10-30): /funds' bet-size reader, moved verbatim from pinphone.funds_sizes (where it was a
# closure over its `when` and `results`; spec.SizeIn hands it those and the phone's readers).
def size_words(si):
    """/funds: the FX taker's size now, for account si.sub -- one start record, a pot per account."""
    import os
    from botdata.logs import settings_now
    n = si.sub
    path = os.path.join(si.results, "fxtake-live-orders.jsonl")
    r = settings_now(path, si.last_record(path, ("start",)), RESIZE, resize_as_start)    # v-tg-settings-now
    size = si.num((r or {}).get("size"))
    if size is None:
        return None
    # since v-fx-twopots its start names a pot per cash pool ({"0": 4, "2": 5}) and each pool's cash: account n's
    # own pot is the pool it holds; an older start had one pot (sub_balance)
    if r.get("bank_sizing"):                                     # v-fx-onepot: ONE size from the whole bank
        one = one_sub(r)
        if one is not None and n is not None and str(n) != one:
            return None                                          # this account is no longer one of its pots
        src, at = (r, "its start")
        if r.get("changed_t"):                                   # resized since it started (v-tg-settings-now)
            src, at = {"t": r["changed_t"], "bank": r.get("bank"), "pool_cash": r.get("pool_cash")}, "its last resize"
        cash = src.get("pool_cash") or {}
        parts = " + ".join("%s %s" % ("currencies" if str(p) == "0" else "commodities", si.usd2(si.num(v)))
                           for p, v in sorted(cash.items()) if si.num(v) is not None)
        return "FX taker %g contracts a market (set at %s %s from its whole %s bank: %s%s)" % (
            size, at, si.when(src), si.usd2(si.num(src.get("bank")) or 0.0), parts,
            (", both in subaccount %s" % one) if one is not None else
            ", subaccounts %s" % " + ".join(str(s_) for _p, s_ in sorted((r.get("subs") or {}).items())))
    pot, what = r.get("sub_balance"), ""
    for pool, sb in (r.get("subs") or {}).items():
        if n is not None and si.num(sb) == n:
            pot = (r.get("pool_cash") or {}).get(pool)
            what = " (%s)" % ("the currency pairs" if str(pool) == "0" else "the commodities")
    return "FX taker%s %g contracts a market (set at its start %s%s)" % (
        what, size, si.when(r), (" on a %s pot" % si.usd2(pot)) if si.num(pot) is not None else "")


# v-tg-rebuild step 12, lane Q (2026-10-30): the phone's early warnings before the FX taker's stops trip
def stop_gauges(wi):
    """The FX taker's two stops, from its own records (fxtake_live.py): the stop line (settled money since
    stop_line_since: its start's line_pnl + this run's run_pnl; warned $5 and $2.50 before it) and the day stop (its
    day_pnl; warned at 60% and 80% of it)."""
    import os
    from botdata.logs import settings_now
    path = os.path.join(wi.results, "fxtake-live-orders.jsonl")
    # v-fx-onepot: the stop line and the day stop scale with the size; v-tg-settings-now: its newest resize carries them
    st = settings_now(path, wi.last_record(path, ("start",)), RESIZE, resize_as_start)
    if not st:
        return []
    t0 = wi.epoch(st.get("t")) or 0.0
    r = wi.last_record(path, ("settle", "health")) or {}
    rt = wi.epoch(r.get("t"))
    if rt is None or rt < t0:
        r, rt = {"run_pnl": 0.0, "day_pnl": 0.0}, t0
    run = _num(r.get("run_pnl")) or 0.0
    out = []
    line, base = _num(st.get("stop_line")), _num(st.get("line_pnl"))
    if line is not None and base is not None:
        since = str(st.get("stop_line_since") or "")
        hit = bool(wi.last_record(path, ("stop_line",), lambda x: str(x.get("since") or "") == since))
        out.append(Gauge(key="line", what="its stop line", money=round(base + run, 2), line=line,
                         warn_at=(line + 5.0, line + 2.5), period="since %s" % since,
                         counted="settled since %s" % since[:10],
                         trips="it stands down for good (it writes its stop file; boot_all will not start it again)",
                         tripped=hit))
    ds = _num(st.get("day_stop"))
    if ds is not None and ds < 0:
        day = (_num(r.get("day_pnl")) or 0.0) if wi.et_day(rt) == wi.today else 0.0
        d = wi.last_record(path, ("day_stop",)) or {}
        out.append(Gauge(key="day", what="its day stop", money=round(day, 2), line=ds,
                         warn_at=(round(0.6 * ds, 2), round(0.8 * ds, 2)), period=wi.today, counted="settled today",
                         trips="it stops for the rest of the day", tripped=str(d.get("day") or "") == wi.today))
    return out


# v-tg-rebuild step 12, lane Q (2026-10-30): the phone's balance check -- both pots as its own log has them
def books(wi, upto):
    """Each of its two pots as its newest start read it (start.pool_cash by pool, start.subs = which subaccount each pool
    is), plus every market it settled since (settle.pnl, fees in), up to `upto`. A market bought before the start and
    settled after it adds its whole payout (its cost had left the cash the start read)."""
    import os
    path = os.path.join(wi.results, "fxtake-live-orders.jsonl")
    # start-only: the book's origin is the cash its start read (start.pool_cash) and how its pools map to subaccounts
    st = wi.last_record(path, ("start",), lambda r: (wi.epoch(r.get("t")) or 0) <= upto)
    t0 = wi.epoch((st or {}).get("t"))
    if not st or t0 is None or not st.get("subs") or not st.get("pool_cash"):
        return []
    acc = {str(pool): [0.0, 0, set(), None] for pool in st["subs"]}
    filled = set()
    for x in wi.read_since(path, t0) or []:
        t = wi.epoch(x.get("t"))
        if t is None or t <= t0 or t > upto:
            continue
        tk = str(x.get("ticker"))
        pool = "0" if tk.split("-")[0] in FX_PAIRS else "2"
        if pool not in acc:
            continue
        if x.get("kind") == "fill":
            filled.add(tk)
            acc[pool][3] = t
        elif x.get("kind") == "settle":
            a = acc[pool]
            a[0] += (_num(x.get("pnl")) or 0.0) + (0.0 if tk in filled else
                                                   (_num(x.get("cost")) or 0.0) + (_num(x.get("fee")) or 0.0))
            a[1] += 1
            a[2].add(tk)
            a[3] = t
    out = []
    one = one_sub(st)
    if one is not None:                     # v-fx-onepot one-sub: ONE pot, both pools (Kalshi's side sums every pool)
        v0s = [_num((st.get("pool_cash") or {}).get(str(pool))) for pool in st["subs"]]
        if any(v is None for v in v0s):
            return []                       # half a pot is no book
        lasts = [a[3] for a in acc.values() if a[3] is not None]
        return [Book(sub=one, t0=t0, value0=round(sum(v0s), 4), settled=round(sum(a[0] for a in acc.values()), 4),
                     markets=sum(a[1] for a in acc.values()), tickers=frozenset(set().union(*[a[2] for a in acc.values()])),
                     since="its start", part="", last_t=max(lasts) if lasts else None)]
    for pool, sub in sorted(st["subs"].items()):
        v0 = _num((st.get("pool_cash") or {}).get(str(pool)))
        if v0 is None:
            continue
        s, n, tks, last = acc[str(pool)]
        out.append(Book(sub=str(sub), t0=t0, value0=v0, settled=round(s, 4), markets=n, tickers=frozenset(tks),
                        since="its start", part="currencies" if str(pool) == "0" else "commodities", last_t=last))
    return out


BOT = Bot(
    name="fx", label="FX taker", short="FX taker", word="FX taker",
    what="buys the side already bid 98c+ at 99c or less 30 to 15 s before the close of the 15-minute markets (45 to 15 s on 10-30 only; 30 to 15 s "
         "until 10-30, v-fx-from45): the 5 currency pairs (subaccount 4) and the 8 commodities (subaccount 5) as ONE "
         "bank: $20 of it a contract (10 contracts a market at ~$207; v-fx-onepot)",
    strategy=(
        "Buys the favourite in the 15-minute currency (5 pairs) and commodity (8) markets 30 to 15 seconds before"
        " the close.",
        "Only when its bid has held 98c or more for 5 seconds and it is still sold at 99c or less; one order a "
        "market.",
        "It wins because a 98c bid that late almost never flips; a win earns about 1c a contract, a loss costs "
        "99c.",
        "A bet is the bank divided by $20 in contracts.",
        "It stops for the day at -$25 and for good at -$10 since its stop line was set (at 10 contracts; both "
        "scale).",
        "Quiet on weekends: Friday about 5 PM ET to Sunday about 6 PM ET.",
    ),
    help=("/fx — the FX taker: the 5 currency pairs (subaccount 4) and the 8 commodities (subaccount 5), the same detail "
          "as /pin",),
    command="/fx", commands=("/fx",),
    # 5 = commodities (pool 2), 4 = the 5 currency pairs (pool 0), since 10-25. 2026-10-26: for a BOT's pot (its % of
    # bank, its chart, the per-pot check) subaccount 4 is its POOL 0 only (the pool-2 side is the old reward test's)
    pots=(Pot("5", 2, what="FX taker: the 8 commodities (penny test, 2026-10-25)", short="fx commod",
              part="commodities"),
          Pot("4", 0, claims=_pairs, priority=10, pool_only=True,
              what="FX taker: the 5 currency pairs (penny test, 2026-10-25)", short="fx pairs", part="currencies")),
    script="fxtake_live.py", is_live=live_flag("--live"), stop_file="fxtake-live.stop",
    logs=Logs(path="fxtake-live-orders.jsonl"),
    records=Records(fills=("fill",), fill_qty="n", halts=("halt", "day_stop"), resize=RESIZE,
                    resize_as_start=resize_as_start,
                    # the FX taker's (fxtake_live.decide)
                    refusal_words=((r"^unfunded_pool$", "no cash in that market's pool"),
                                   (r"^per_close$", "6 already this quarter-hour"), (r"^held$", "its money cap already in play"))),
    settings=settings,
    # its own name wins over words about the pots it shares
    version=VersionRule(part=lambda n: "fxtake" in n or n.startswith("v-fx"),
                        text=lambda vname, low: "fxtake" in low or vname.startswith("v-fx"), override="v-fx"),
    colour="#8a5a00",          # brown-gold
    order=6,
    keepalive="boot_all.ps1 (every 10 min) restarts it unless the stop file is there",   # since 10-26 (add_fx_keepalive.ps1)
    page_footer="Every bot: /bots · both FX pots' cash: /funds.",
    activity=activity,
    funds_size=size_words,
    stop_gauges=stop_gauges,     # step 12 (lane Q): the phone's early warnings
    books=books,                 # step 12 (lane Q): the phone's balance check
    speed=Speed(rank=1, field="kind", kind="placed"),
    features=(
        Feature("fxtake_live.py", "--live", None, "FX taker (LIVE, subaccounts 5 + 4)",
                "In the last 30 to 15 seconds of each 15-minute currency and commodity market (45 to 15 for one day, 10-30), "
                "buys the side already bid 98c or more at 99c or less: the 5 currency pairs from subaccount 4, the 8 "
                "commodities from subaccount 5, sized from both pots as one bank ($20 a contract: 10 at ~$207).",
                pos=5, hides=True),
    ),
)
