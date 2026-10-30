"""The FX taker (research/cleanroom/fxtake_live.py, 2026-10-25): the 8 commodities from subaccount 5 (pool 2) and the
5 currency pairs from subaccount 4 (pool 0). Every fact copied verbatim from botstats.py / pinphone.py / tgcharts.py at
8a9c5e1 (v-tg-rebuild step 1, 2026-10-30)."""
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
    return s, "; ".join(bits)


def settings(si):
    return settings_fx(si.start)


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
    n = si.sub
    r = si.last_record(os.path.join(si.results, "fxtake-live-orders.jsonl"), ("start",))
    size = si.num((r or {}).get("size"))
    if size is None:
        return None
    # since v-fx-twopots its start names a pot per cash pool ({"0": 4, "2": 5}) and each pool's cash: account n's
    # own pot is the pool it holds; an older start had one pot (sub_balance)
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
    path = os.path.join(wi.results, "fxtake-live-orders.jsonl")
    st = wi.last_record(path, ("start",))
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
         "until 10-30, v-fx-from45): the 5 currency pairs (subaccount 4) and the 8 commodities (subaccount 5), 10 "
         "contracts a market",
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
    records=Records(fills=("fill",), fill_qty="n", halts=("halt", "day_stop"),
                    # the FX taker's (fxtake_live.decide)
                    refusal_words=((r"^unfunded_pool$", "no cash in that market's pool"),
                                   (r"^per_close$", "6 already this quarter-hour"), (r"^held$", "$70 already in play"))),
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
                "buys the side already bid 98c or more at 99c or less, 10 contracts: the 5 currency pairs from "
                "subaccount 4, the 8 commodities from subaccount 5.", pos=5, hides=True),
    ),
)
