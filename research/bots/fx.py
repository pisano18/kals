"""The FX taker (research/cleanroom/fxtake_live.py, 2026-10-25): the 8 commodities from subaccount 5 (pool 2) and the
5 currency pairs from subaccount 4 (pool 0). Every fact copied verbatim from botstats.py / pinphone.py / tgcharts.py at
8a9c5e1 (v-tg-rebuild step 1, 2026-10-30)."""
from bots.spec import Bot, Feature, Logs, Pot, Records, Speed, VersionRule, live_flag
from botdata.fmt import cents as _c, usd

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


BOT = Bot(
    name="fx", label="FX taker", short="FX taker", word="FX taker",
    what="buys the side already bid 98c+ at 99c or less 45 to 15 s before the close of the 15-minute markets (30 to 15 s "
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
    funds_size=True,
    speed=Speed(rank=1, field="kind", kind="placed"),
    features=(
        Feature("fxtake_live.py", "--live", None, "FX taker (LIVE, subaccounts 5 + 4)",
                "In the last 45 to 15 seconds of each 15-minute currency and commodity market (30 to 15 until 10-30), "
                "buys the side already bid 98c or more at 99c or less, 10 contracts: the 5 currency pairs from "
                "subaccount 4, the 8 commodities from subaccount 5.", pos=5, hides=True),
    ),
)
