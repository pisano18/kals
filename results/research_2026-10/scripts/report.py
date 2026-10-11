"""report.py -- tables a..h from live_markets.jsonl + live_versions.json -> live_ledger_report.md (and key numbers to stdout).
n is MARKETS everywhere. Loss-rate intervals are exact Clopper-Pearson 95%."""
import collections
import json
import math
import os
import random
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.dirname(os.path.abspath(__file__))
TODAY_ET = "2026-10-08"
LAST14_FROM = "2026-09-25"          # 14 ET days ending today: 09-25..10-08
PRICE_BUCKETS = [("<90", 0, 90), ("90-93", 90, 93), ("93-95", 93, 95), ("95-96", 95, 96), ("96-97", 96, 97),
                 ("97-98", 97, 98), (">=98", 98, 1000)]
TAU_BUCKETS = [("<=10", -1, 10), ("11-20", 10, 20), ("21-30", 20, 30), ("31-45", 30, 45), (">45", 45, 10000)]


# ------------------------------------------------------------------ exact binomial interval
def _log_binom_pmf(k, n, p):
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log1p(-p))


def _cdf(x, n, p):
    """P(X <= x)"""
    terms = [_log_binom_pmf(k, n, p) for k in range(0, x + 1)]
    m = max(terms)
    if m == -math.inf:
        return 0.0
    return math.exp(m) * sum(math.exp(t - m) for t in terms)


def clopper_pearson(x, n, alpha=0.05):
    """Exact two-sided interval for x successes in n trials, by bisection on the binomial tails."""
    if n == 0:
        return (float("nan"), float("nan"))
    if x == 0:
        lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):                 # P(X >= x | p) = alpha/2  <=>  1 - cdf(x-1) = alpha/2
            mid = (a + b) / 2
            if 1.0 - _cdf(x - 1, n, mid) < alpha / 2:
                a = mid
            else:
                b = mid
        lo = (a + b) / 2
    if x == n:
        hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):                 # P(X <= x | p) = alpha/2
            mid = (a + b) / 2
            if _cdf(x, n, mid) > alpha / 2:
                a = mid
            else:
                b = mid
        hi = (a + b) / 2
    return lo, hi


def selftest():
    lo, hi = clopper_pearson(0, 100)
    assert lo == 0.0 and abs(hi - (1 - 0.025 ** (1 / 100))) < 1e-6, (lo, hi)
    lo, hi = clopper_pearson(2, 59)
    assert abs(lo - 0.0041) < 0.001 and abs(hi - 0.117) < 0.002, (lo, hi)   # the CLAUDE.md example: 2 of 59 -> [0.4, 11.7]%
    lo, hi = clopper_pearson(1, 891)
    assert lo > 0 and abs(hi - 0.0061) < 0.0005, (lo, hi)                 # 1 of 891 -> [0.00, 0.61]%
    lo, hi = clopper_pearson(5, 5)
    assert hi == 1.0 and lo > 0.4
    print("report selftest: OK")


# ------------------------------------------------------------------ helpers
def fee_per_contract(p):
    return 0.07 * p * (1.0 - p)


def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return ("%%.%df" % nd) % x


def pct(x, nd=1):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return ("%%.%df%%%%" % nd) % (100.0 * x)


def bucket_of(v, buckets):
    if v is None:
        return None
    for name, lo, hi in buckets:
        if lo < v <= hi if buckets is TAU_BUCKETS else lo <= v < hi:
            return name
    return None


def first_price_c(r):
    ff = r.get("first_fill")
    if not ff or ff.get("price") is None:
        return None
    return float(ff["price"]) * 100.0


def first_tau(r):
    ff = r.get("first_fill")
    if not ff or ff.get("tau") is None:
        return None
    return float(ff["tau"])


def stats(rows):
    """n, lost, loss rate + CI, net $, bet $, contracts, net/contract, avg win/contract, avg loss/contract, measured break-even."""
    n = len(rows)
    lost = [r for r in rows if r["money"] < 0]
    won = [r for r in rows if r["money"] > 0]
    net = sum(r["money"] for r in rows)
    bet = sum(r["bet_cost"] or 0.0 for r in rows)
    contracts = sum(r["bet_count"] or 0.0 for r in rows)
    lo, hi = clopper_pearson(len(lost), n) if n else (float("nan"), float("nan"))
    wc = sum(r["bet_count"] or 0.0 for r in won)
    lc = sum(r["bet_count"] or 0.0 for r in lost)
    avg_win = (sum(r["money"] for r in won) / wc) if wc else None
    avg_loss = (sum(r["money"] for r in lost) / lc) if lc else None
    be = (avg_win / (avg_win - avg_loss)) if (avg_win is not None and avg_loss is not None and avg_win - avg_loss > 0) else None
    prices = [first_price_c(r) for r in rows if first_price_c(r) is not None]
    mean_p = (sum(prices) / len(prices) / 100.0) if prices else None
    fees = sum(r["fee"] or 0.0 for r in rows)
    return {"n": n, "lost": len(lost), "rate": (len(lost) / n) if n else None, "lo": lo, "hi": hi, "net": net, "bet": bet,
            "contracts": contracts, "net_pc": (net / contracts) if contracts else None, "avg_win_pc": avg_win,
            "avg_loss_pc": avg_loss, "be_measured": be, "mean_price": mean_p,
            "be_formula": (1 - mean_p - fee_per_contract(mean_p)) if mean_p else None,
            "fee_pc": (fees / contracts) if contracts else None, "ret": (net / bet) if bet else None}


def stat_row(label, s):
    return "| %s | %d | %d | %s [%s, %s] | %s | %s | %s | %s | %s | %s | %s |" % (
        label, s["n"], s["lost"], pct(s["rate"]), pct(s["lo"]), pct(s["hi"]), fmt(s["net"]), fmt(s["bet"], 0),
        fmt(s["net_pc"], 4), fmt(s["avg_win_pc"], 4), fmt(s["avg_loss_pc"], 4),
        pct(s["be_formula"]) + " (price " + (fmt(s["mean_price"] * 100 if s["mean_price"] else None, 1)) + "c)",
        pct(s["be_measured"]))


STAT_HDR = ("| bucket | markets | lost | loss rate per 100 [95% CI] | net $ | bet $ | net $/contract | avg win $/contract "
            "| avg loss $/contract | break-even loss rate (1-p-fee at mean price) | break-even (measured win/loss sizes) |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|")


def leg_line(o):
    sg = o.get("signal") or {}
    return ("%s#%s %s lim %s ask %s exec %s fill %s/%s tau %s | lvl_age %s ms sell3s %s tk3s %s trade_age %s s book_age %s ms "
            "| swept %s hdrm %sc | fair %s edge %sc sigma %s") % (
        o.get("leg"), o.get("leg_source", "")[:1], o.get("want"), fmt(o.get("limit_sent"), 3), fmt(o.get("ask_seen"), 3),
        fmt(o.get("exec_price"), 4), fmt(o.get("filled"), 1), fmt(o.get("asked"), 1), o.get("tau_at_send"),
        o.get("level_age_ms"), o.get("sell_share_3s"), o.get("taker_n_3s"), o.get("trade_age_s"), o.get("book_age_ms"),
        o.get("swept"), o.get("sweep_headroom_c"), sg.get("fair"), sg.get("edge_c"), sg.get("sigma"))


def seller_fields(o):
    return {"level_age_ms": o.get("level_age_ms"), "sell_share_3s": o.get("sell_share_3s"), "taker_n_3s": o.get("taker_n_3s"),
            "trade_age_s": o.get("trade_age_s"), "book_age_ms": o.get("book_age_ms")}


def conf_of(r):
    """The model's confidence on the side we bought: fair is P(YES), so a NO bet's confidence is 1 - fair."""
    ff = r.get("first_fill") or {}
    f = ff.get("fair")
    if f is None:
        return None
    return f if ff.get("want") == "yes" else 1.0 - f


def under_ask_c(r):
    """How far UNDER the ask the bot saw its first fill actually executed, in cents (a big number = the book it saw was stale
    and the real price had already collapsed)."""
    ff = r.get("first_fill") or {}
    if ff.get("ask_seen") is None or ff.get("price") is None:
        return None
    return (ff["ask_seen"] - ff["price"]) * 100.0


def anatomy_row(r):
    ff = r["first_fill"] or {}
    hd = r.get("hedge") or {}
    hrec = [h for h in (hd.get("records") or []) if (h.get("n") or 0) > 0]
    hs = "; ".join("belief %s @%sc n %s" % (fmt(h.get("belief"), 3), fmt((h.get("price") or 0) * 100, 1), fmt(h.get("n"), 1))
                   for h in hrec) or ("ledger both sides, no hedge record" if r["hedged_ledger"] else "no")
    ua = under_ask_c(r)
    return "| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        r["ticker"], r["close_et"], (r["version"]["name"] or "?")[:22], fmt(r["money"]), fmt(r["bet_cost"], 0),
        fmt(r["bet_count"], 0), r["leg_mix"], ff.get("leg"), fmt(ff.get("price"), 4), ff.get("tau"),
        fmt(ff.get("ask_seen"), 3) + "->" + fmt(ff.get("limit_sent"), 3) + (" SWEPT" if ff.get("swept") else "")
        + (" **fill %.0fc under ask**" % ua if (ua is not None and ua >= 3) else ""),
        fmt(conf_of(r), 5), fmt(ff.get("edge_c"), 2), ff.get("level_age_ms"), ff.get("sell_share_3s"), ff.get("taker_n_3s"),
        ff.get("trade_age_s"), hs + (" | hedge $ %s" % fmt(r.get("hedge_dollars_ledger")) if r["hedged_ledger"] else ""))


ANAT_HDR = ("| ticker | close ET | version | $ net | bet $ | contracts | legs filled | 1st leg | 1st price | 1st tau s "
            "| ask_seen->limit | model conf | edge c | level_age_ms | sell_share_3s | taker_n_3s | trade_age_s | hedge |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def main():
    selftest()
    rows = [json.loads(l) for l in open(os.path.join(OUT, "live_markets.jsonl"), encoding="utf-8")]
    vers = json.load(open(os.path.join(OUT, "live_versions.json"), encoding="utf-8"))
    files = vers["files"]
    by_file = {f["file"]: f for f in files}
    main_rows = [r for r in rows if r["in_main_table"] and r["money"] is not None]
    main_rows.sort(key=lambda r: r["close_utc"] or "")
    L = []
    say = L.append
    ledger_written = json.load(open(os.path.join(OUT, "build_summary.json"), encoding="utf-8"))["ledger_written"]

    # ---------------------------------------------------------------- headline
    all_s = stats(main_rows)
    l14 = [r for r in main_rows if r["et_day"] >= LAST14_FROM]
    l14_s = stats(l14)
    say("# Live ledger report -- the main bot's real-money markets, 2026-09-08 .. %s" % TODAY_ET)
    say("")
    say("Money is Kalshi's own settlement row per market (results/kalshi_ledger.json written %s; payout - both sides' cost - fees, "
        "as research/pinledger.py computes it). Decisions are the bot's live logs (results/pinrun-live-*.jsonl, %d files). "
        "n is MARKETS everywhere. Main table = the 12 fifteen-minute coin series only; coin race, commodity (the separate "
        "commodity bot), the hourly KXBTCD ladder and anything else are tabulated apart in (f). Subaccount bots (ladder, "
        "forecaster, dip-seller) are not in this ledger file and are not here." % (ledger_written, len(files)))
    say("")
    say("**All-time (main table):** %d markets, **%+.2f** net on $%.0f bet (%s), **%d losing markets** "
        "(%s per 100, 95%% interval %s..%s); %d hedged markets. **Last 14 ET days (%s..):** %d markets, %+.2f on $%.0f bet (%s), "
        "%d lost (%s per 100, %s..%s)." % (
            all_s["n"], all_s["net"], all_s["bet"], pct(all_s["ret"], 2), all_s["lost"], pct(all_s["rate"], 2), pct(all_s["lo"], 2),
            pct(all_s["hi"], 2), sum(1 for r in main_rows if r["hedged_ledger"]), LAST14_FROM, l14_s["n"], l14_s["net"],
            l14_s["bet"], pct(l14_s["ret"], 2), l14_s["lost"], pct(l14_s["rate"], 2), pct(l14_s["lo"], 2), pct(l14_s["hi"], 2)))
    say("")

    # ---------------------------------------------------------------- a) per version
    say("## a) Per version (chronological; version = the latest LIVE main-bot header in results/VERSIONS.md at the log file's start; the argv in live_versions.json is the real version)")
    say("")
    vgroups = collections.OrderedDict()
    for f in files:
        vn = f["version_name"] or "?"
        g = vgroups.setdefault(vn, {"files": [], "hours": 0.0, "first": f["start_utc"], "last": f["end_utc"], "shas": set(),
                                   "flagsets": []})
        g["files"].append(f["file"])
        g["hours"] += f["hours"] or 0.0
        g["last"] = max(g["last"] or "", f["end_utc"] or "")
        if f["code_sha"]:
            g["shas"].add(f["code_sha"])
        fl = f["flags"]
        key = json.dumps({k: fl.get(k) for k in ("pin", "tau_min", "tau_max", "size", "early_frac", "early_min_price",
                                                  "early_max_price", "price_ceiling", "toxic_fresh", "hedge_belief",
                                                  "max_full_bets", "skip_coin", "late_tau", "late_mult", "min_level")}, sort_keys=True)
        if key not in g["flagsets"]:
            g["flagsets"].append(key)
    mk_by_version = collections.defaultdict(list)
    for r in main_rows:
        mk_by_version[r["version"]["name"] or "?"].append(r)
    say("| # | version | first start UTC | last end UTC | hours up | log files | markets | net $ | bet $ | % on bet | $/day up | lost | key flags (first file; `*` = flags differ between its files) |")
    say("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    vlist = []
    for i, (vn, g) in enumerate(vgroups.items(), 1):
        mk = mk_by_version.get(vn, [])
        s = stats(mk) if mk else None
        f0 = by_file[g["files"][0]]["flags"]
        parts = []
        for lab, key in (("pin", "pin"), ("tau", None), ("early", None), ("ceil", "price_ceiling"), ("hedge@", "hedge_belief"),
                         ("fullcap", "max_full_bets"), ("skip", "skip_coin"), ("late", None), ("toxic", "toxic_fresh"),
                         ("minlvl", "min_level")):
            if key is None:
                if lab == "tau":
                    parts.append("tau %s-%s" % (f0.get("tau_min"), f0.get("tau_max")))
                elif lab == "early" and f0.get("early_frac") is not None:
                    parts.append("early x%s@%s-%s" % (f0.get("early_frac"), f0.get("early_min_price"), f0.get("early_max_price")))
                elif lab == "late" and f0.get("late_mult") not in (None, 1.0, 1):
                    parts.append("late x%s<=%ss" % (f0.get("late_mult"), f0.get("late_tau")))
            elif f0.get(key) not in (None, False, []):
                parts.append("%s %s" % (lab, f0.get(key)))
        srs = [by_file[x].get("size_range") for x in g["files"] if by_file[x].get("size_range")]
        parts.append("size %s%s" % (f0.get("size"), (" auto %g..%g" % (min(s[0] for s in srs), max(s[1] for s in srs))) if srs else ""))
        kf = " ".join(parts)
        if len(g["flagsets"]) > 1:
            kf += " *"
        days = g["hours"] / 24.0
        say("| %d | %s | %s | %s | %.1f | %d | %d | %s | %s | %s | %s | %d | %s |" % (
            i, vn, g["first"], g["last"], g["hours"], len(g["files"]), len(mk), fmt(s["net"]) if s else "-",
            fmt(s["bet"], 0) if s else "-", pct(s["ret"], 2) if s else "-", fmt(s["net"] / days) if (s and days > 0) else "-",
            s["lost"] if s else 0, kf))
        vlist.append((vn, g, mk, s))
    say("")
    say("Losing markets and the biggest win, per version (price = first filled leg, our side; tau = seconds to close at that send; size = contracts on the bet side):")
    say("")
    for vn, g, mk, s in vlist:
        if not mk:
            continue
        lost = sorted([r for r in mk if r["money"] < 0], key=lambda r: r["money"])
        big = max(mk, key=lambda r: r["money"])
        say("- **%s** (%d markets, %+.2f): biggest win %s %s %+.2f on %s contracts @%sc." % (
            vn, len(mk), s["net"], big["ticker"], big["close_et"], big["money"], fmt(big["bet_count"], 0),
            fmt(first_price_c(big), 1)))
        for r in lost:
            ff = r["first_fill"] or {}
            say("    - LOST %s %s **%+.2f** paid %sc tau %ss leg %s size %s%s" % (
                r["ticker"], r["close_et"], r["money"], fmt(first_price_c(r), 1), ff.get("tau"), r["leg_mix"],
                fmt(r["bet_count"], 0), " HEDGED (hedge side %+.2f)" % r["hedge_dollars_ledger"] if r["hedged_ledger"] else ""))
    say("")

    # ---------------------------------------------------------------- b) price / tau buckets
    say("## b) By price of the FIRST filled leg, and by its tau -- all-time and last 14 ET days")
    say("")
    with_fill = [r for r in main_rows if first_price_c(r) is not None]
    say("%d of %d main-table markets have a logged first fill (the rest: Kalshi settled them, no log order -- see h). "
        "Fee = 0.07 x p x (1-p) per contract (taker). 'break-even (measured)' = avg win / (avg win + avg loss) per contract."
        % (len(with_fill), len(main_rows)))
    say("")
    for title, sub in (("All-time", with_fill), ("Last 14 ET days (%s..)" % LAST14_FROM,
                                                  [r for r in with_fill if r["et_day"] >= LAST14_FROM])):
        say("### %s -- price buckets (cents)" % title)
        say("")
        say(STAT_HDR)
        for name, lo, hi in PRICE_BUCKETS:
            grp = [r for r in sub if bucket_of(first_price_c(r), PRICE_BUCKETS) == name]
            if grp:
                say(stat_row(name, stats(grp)))
        say(stat_row("ALL", stats(sub)))
        say("")
        say("### %s -- tau buckets (seconds to close at the first filled send)" % title)
        say("")
        say(STAT_HDR)
        for name, lo, hi in TAU_BUCKETS:
            grp = [r for r in sub if bucket_of(first_tau(r), TAU_BUCKETS) == name]
            if grp:
                say(stat_row(name, stats(grp)))
        nt = [r for r in sub if first_tau(r) is None]
        if nt:
            say(stat_row("tau unknown", stats(nt)))
        say("")

    # ---------------------------------------------------------------- c) coin / hour / weekday
    say("## c) Per coin, per ET hour of day, per weekday")
    say("")
    say("| coin | markets | lost | loss rate [95% CI] | net $ | bet $ | % on bet |")
    say("|---|---|---|---|---|---|---|")
    for coin in sorted(set(r["coin"] for r in main_rows), key=lambda c: -len(mk_by_coin) if False else c):
        pass
    by_coin = collections.defaultdict(list)
    for r in main_rows:
        by_coin[r["coin"]].append(r)
    for coin, grp in sorted(by_coin.items(), key=lambda kv: -len(kv[1])):
        s = stats(grp)
        say("| %s | %d | %d | %s [%s, %s] | %s | %s | %s |" % (coin, s["n"], s["lost"], pct(s["rate"]), pct(s["lo"]), pct(s["hi"]),
                                                            fmt(s["net"]), fmt(s["bet"], 0), pct(s["ret"], 2)))
    say("")
    say("| ET hour | markets | lost | net $ | % on bet |  | weekday | markets | lost | net $ | % on bet |")
    say("|---|---|---|---|---|---|---|---|---|---|---|")
    by_hour = collections.defaultdict(list)
    by_wd = collections.defaultdict(list)
    for r in main_rows:
        by_hour[r["hour_et"]].append(r)
        by_wd[r["weekday"]].append(r)
    wds = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for h in range(24):
        hs = stats(by_hour[h]) if by_hour.get(h) else None
        wd = wds[h] if h < 7 else None
        ws = stats(by_wd[wd]) if (wd and by_wd.get(wd)) else None
        say("| %02d | %s | %s | %s | %s |  | %s | %s | %s | %s | %s |" % (
            h, hs["n"] if hs else 0, hs["lost"] if hs else 0, fmt(hs["net"]) if hs else "-", pct(hs["ret"], 1) if hs else "-",
            wd or "", ws["n"] if ws else "", ws["lost"] if ws else "", fmt(ws["net"]) if ws else "", pct(ws["ret"], 1) if ws else ""))
    say("")

    # ---------------------------------------------------------------- d) loss anatomy
    say("## d) Loss anatomy -- every losing market, then 60 random winners (seed 7) from the same versions")
    say("")
    say("Seller-check inputs are those logged on the FIRST filled leg (sell_share_3s / taker_n_3s / trade_age_s exist only from v-tradefeed, 2026-09-25; level_age_ms from v-ladder, 09-14). "
        "'ask_seen->limit' shows the sweep: limit above the ask means the bot bid up through the ladder. Additional filled legs of each loser are listed under the table.")
    say("")
    losers = sorted([r for r in main_rows if r["money"] < 0], key=lambda r: r["money"])
    say(ANAT_HDR)
    for r in losers:
        say(anatomy_row(r))
    say("")
    say("Every filled leg of each losing market (leg#source: l=logged, d=derived from tau for pre-09-17 logs):")
    say("")
    for r in losers:
        legs = [o for o in r["legs"] if o["filled"] > 0]
        say("- %s %s %+.2f (%s), %d filled legs%s:" % (r["ticker"], r["close_et"], r["money"], r["version"]["name"], len(legs),
                                                        "; log settled %s" % fmt(r["pnl_c_sum_dollars"]) if r["pnl_c_sum_dollars"] is not None else ""))
        for o in legs:
            say("    - " + leg_line(o))
        hd = r.get("hedge") or {}
        for h in hd.get("records") or []:
            say("    - HEDGE %s side %s belief %s ask %s limit %s price %s asked %s filled %s status %s tau %s locked_loss %sc" % (
                h.get("t"), h.get("side"), fmt(h.get("belief"), 3), fmt(h.get("ask"), 3), fmt(h.get("limit_sent"), 3),
                fmt(h.get("price"), 3), fmt(h.get("asked"), 1), fmt(h.get("n"), 1), h.get("status"), h.get("tau"), h.get("locked_loss_c")))
        if hd.get("alarms"):
            a0 = hd["alarms"][0]
            say("    - first hedge_alarm %s belief %s tau %s (%d alarms; %d hedge_quote records, min belief %s)" % (
                a0.get("t"), fmt(a0.get("belief"), 3), a0.get("tau"), len(hd["alarms"]), hd.get("quotes_n") or 0,
                fmt(hd.get("quotes_min_belief"), 3)))
        gates = {k: v for k, v in (r.get("refusal_gates") or {}).items() if k != "no_offer"}
        if gates:
            say("    - refusals on this market (gate: n): %s" % json.dumps(gates, sort_keys=True))
    say("")
    loser_versions = set(r["version"]["name"] for r in losers)
    pool = [r for r in main_rows if r["money"] > 0 and r["version"]["name"] in loser_versions and r["first_fill"]]
    rng = random.Random(7)
    sample = sorted(rng.sample(pool, min(60, len(pool))), key=lambda r: r["close_utc"])
    say("### 60 random winning markets from the same versions (seed 7; pool %d winners)" % len(pool))
    say("")
    say(ANAT_HDR)
    for r in sample:
        say(anatomy_row(r))
    say("")
    # population comparison on the seller-check fields where both sides have them
    say("Population comparison (first filled leg; only markets where the field is logged):")
    say("")
    say("| field | losers: n / median | winners (the 60): n / median | all winners: n / median |")
    say("|---|---|---|---|")
    winners_all = [r for r in main_rows if r["money"] > 0 and r["first_fill"]]

    def med(vals):
        v = sorted(x for x in vals if isinstance(x, (int, float)))
        if not v:
            return "0 / -"
        return "%d / %s" % (len(v), fmt(v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2, 4))

    for fld in ("price", "tau", "level_age_ms", "sell_share_3s", "taker_n_3s", "trade_age_s", "book_age_ms", "edge_c",
                "sweep_headroom_c"):
        say("| %s | %s | %s | %s |" % (fld, med([(r["first_fill"] or {}).get(fld) for r in losers]),
                                      med([(r["first_fill"] or {}).get(fld) for r in sample]),
                                      med([(r["first_fill"] or {}).get(fld) for r in winners_all])))
    say("| model conf on the side bought | %s | %s | %s |" % (med([conf_of(r) for r in losers]), med([conf_of(r) for r in sample]),
                                                              med([conf_of(r) for r in winners_all])))
    say("| fill under the ask seen, cents | %s | %s | %s |" % (med([under_ask_c(r) for r in losers]), med([under_ask_c(r) for r in sample]),
                                                               med([under_ask_c(r) for r in winners_all])))
    say("| fill >= 3c under the ask seen (count) | %d of %d | %d of %d | %d of %d |" % (
        sum(1 for r in losers if (under_ask_c(r) or 0) >= 3), len(losers),
        sum(1 for r in sample if (under_ask_c(r) or 0) >= 3), len(sample),
        sum(1 for r in winners_all if (under_ask_c(r) or 0) >= 3), len(winners_all)))
    stale = [r for r in main_rows if (under_ask_c(r) or 0) >= 3]
    say("| stale-book fills (>= 3c under the ask seen), all main markets | %d markets, %d lost, net %+.2f | | |" % (
        len(stale), sum(1 for r in stale if r["money"] < 0), sum(r["money"] for r in stale)))
    say("| swept (count true) | %d of %d | %d of %d | %d of %d |" % (
        sum(1 for r in losers if (r["first_fill"] or {}).get("swept")), len(losers),
        sum(1 for r in sample if (r["first_fill"] or {}).get("swept")), len(sample),
        sum(1 for r in winners_all if (r["first_fill"] or {}).get("swept")), len(winners_all)))
    say("| leg mix | %s | %s | %s |" % (
        dict(collections.Counter(r["leg_mix"] for r in losers)), dict(collections.Counter(r["leg_mix"] for r in sample)),
        dict(collections.Counter(r["leg_mix"] for r in winners_all))))
    say("")

    # ---------------------------------------------------------------- e) hedges
    say("## e) Hedge / insurance accounting, lifetime (the main bot: the 12 coins since 09-08, plus its KXBTCD rung if any)")
    say("")
    say("A hedge = a `hedge` log record that filled (n > 0), or a Kalshi row holding BOTH sides. Hedge $ = the OTHER side's payout minus "
        "its cost (Kalshi's counts and costs; fees are in the market's net, not here). False alarm = the bet side won anyway. "
        "Where Kalshi's other-side count exceeds the hedge records' n, the difference is an ORDER-path buy on the other side "
        "(the A68 late flip, logged as `late_add`, or a top-up re-buy into the other side) -- counted in hedge $ here because it is insurance in effect.")
    say("")
    say("| ticker | close ET | version | bet side | bet won? | belief at hedge | hedge price c | hedge contracts (log n / Kalshi) | hedge $ | market net $ | kind |")
    say("|---|---|---|---|---|---|---|---|---|---|---|")
    hedged = [r for r in rows if r["money"] is not None and (r["hedged_ledger"] or r["hedge_filled_in_log"])
              and (r["in_main_table"] or r["series"] == "KXBTCD") and r["et_day"] >= "2026-09-08"]
    other_hedged = [r for r in rows if r["money"] is not None and (r["hedged_ledger"] or r["hedge_filled_in_log"]) and r not in hedged]
    hedged.sort(key=lambda r: r["close_utc"] or "")
    tot = collections.defaultdict(lambda: {"n": 0, "hedge": 0.0, "net": 0.0})
    tot_0927 = collections.defaultdict(lambda: {"n": 0, "hedge": 0.0, "net": 0.0})
    for r in hedged:
        hd = r.get("hedge") or {}
        hrec = [h for h in (hd.get("records") or []) if (h.get("n") or 0) > 0]
        if r["bet_won"] is None:
            kind = "unscored"
        elif r["bet_won"]:
            kind = "false alarm"
        else:
            kind = "real"
        if not hrec and r["hedged_ledger"]:
            kind += " (both sides, no hedge record)"
        belief = ", ".join(fmt(h.get("belief"), 3) for h in hrec) or "-"
        hp = ", ".join(fmt((h.get("price") or 0) * 100, 1) for h in hrec) or "-"
        hn = ", ".join(fmt(h.get("n"), 1) for h in hrec) or "-"
        say("| %s | %s | %s | %s | %s | %s | %s | %s / %s | %s | %s | %s |" % (
            r["ticker"], r["close_et"], (r["version"]["name"] or "?")[:20], r["want"], r["bet_won"], belief, hp, hn,
            fmt(r["hedge_count"], 1), fmt(r["hedge_dollars_ledger"]), fmt(r["money"]), kind))
        k = kind.split(" (")[0]
        tot[k]["n"] += 1
        tot[k]["hedge"] += r["hedge_dollars_ledger"] or 0.0
        tot[k]["net"] += r["money"]
        if r["et_day"] <= "2026-09-27":
            tot_0927[k]["n"] += 1
            tot_0927[k]["hedge"] += r["hedge_dollars_ledger"] or 0.0
            tot_0927[k]["net"] += r["money"]
    say("")
    for label, tt in (("lifetime", tot), ("through 2026-09-27 ET (memory says -$55: 9 false -$263 / 13 real +$208)", tot_0927)):
        say("- %s: %s; hedge-side total %+.2f" % (
            label, "; ".join("%s %d markets, hedge side %+.2f (market net %+.2f)" % (k, v["n"], v["hedge"], v["net"])
                             for k, v in sorted(tt.items())), sum(v["hedge"] for v in tt.values())))
    unfilled = [(r, h) for r in rows for h in ((r.get("hedge") or {}).get("records") or []) if (h.get("n") or 0) == 0]
    say("- hedge orders that did NOT fill: %d (statuses %s)" % (len(unfilled), dict(collections.Counter(h.get("status") for _r, h in unfilled))))
    say("- both-sides rows OUTSIDE the main bot's book (not counted above): %s" % (
        "; ".join("%s %s net %+.2f" % (r["ticker"], r["et_day"], r["money"]) for r in other_hedged) or "none"))
    say("")

    # ---------------------------------------------------------------- f) other books
    say("## f) The other books in this ledger file (not the main table)")
    say("")
    say("| book / series | markets | lost | net $ | bet $ (both sides) | % on bet | first ET day | last ET day | note |")
    say("|---|---|---|---|---|---|---|---|---|")
    others = [r for r in rows if r["money"] is not None and not r["in_main_table"]]
    by_series = collections.defaultdict(list)
    for r in others:
        by_series[r["series"]].append(r)
    for sr, grp in sorted(by_series.items(), key=lambda kv: -len(kv[1])):
        net = sum(r["money"] for r in grp)
        bet = sum(r["cost_total"] or 0.0 for r in grp)
        lost = sum(1 for r in grp if r["money"] < 0)
        days = sorted(r["et_day"] for r in grp if r["et_day"])
        note = ""
        g0 = grp[0]
        if sr == "KXCRYPTOLEAD15M":
            events = set((x["ledger"] or {}).get("event_ticker") for x in grp)
            note = "coin race (pinracearm, main account): %d races (events); one ticker per coin leg" % len(events)
        elif g0["book"] == "commodity":
            note = "the separate commodity bot (cmdlive), not pinrun"
        elif sr == "KXBTCD":
            n_bot = sum(1 for x in grp if x["n_filled_orders"] > 0)
            note = ("hourly BTC ladder: %d markets bought by pinrun (1 contract each, v-btcd1 09-24 on), net %+.2f; the rest predate the bot (Aug 15: %+.2f)"
                    % (n_bot, sum(x["money"] for x in grp if x["n_filled_orders"] > 0), sum(x["money"] for x in grp if x["n_filled_orders"] == 0)))
        elif g0["book"] == "crypto":
            note = "15-minute coin rows from BEFORE 2026-09-08 (manual / pre-bot)"
        else:
            note = "not a bot market (manual)"
        say("| %s | %d | %d | %s | %s | %s | %s | %s | %s |" % (sr, len(grp), lost, fmt(net), fmt(bet, 0), pct(net / bet, 2) if bet else "-",
                                                             days[0] if days else "-", days[-1] if days else "-", note))
    race = by_series.get("KXCRYPTOLEAD15M", [])
    if race:
        by_day = collections.defaultdict(lambda: [0, 0, 0.0])
        for r in race:
            d = by_day[r["et_day"]]
            d[0] += 1
            d[1] += r["money"] < 0
            d[2] += r["money"]
        say("")
        say("Coin race by ET day (markets, lost, net $): " + "; ".join("%s %d/%d %+.2f" % (k, v[0], v[1], v[2]) for k, v in sorted(by_day.items())))
    say("")

    # ---------------------------------------------------------------- g) pot math
    say("## g) Pot math per price bucket -- expected $ per 100 contracts at the measured loss rate, and the loss rate that turns it negative")
    say("")
    say("E[$ per 100] = 100 x [(1 - L) x avg win per contract - L x avg loss per contract], with L the measured loss rate; "
        "the same at the interval's low and high ends. Turns negative above L* = avg win / (avg win + avg loss). "
        "ABOVE break-even = the measured L is below L*.")
    say("")
    for title, sub in (("All-time", with_fill), ("Last 14 ET days", [r for r in with_fill if r["et_day"] >= LAST14_FROM])):
        say("### %s" % title)
        say("")
        say("| bucket | markets | L (lost per 100) [95% CI] | E[$/100] at L | at CI low | at CI high | L* (turns negative) | verdict |")
        say("|---|---|---|---|---|---|---|---|")
        for name, lo, hi in PRICE_BUCKETS + [("ALL", None, None)]:
            grp = sub if name == "ALL" else [r for r in sub if bucket_of(first_price_c(r), PRICE_BUCKETS) == name]
            if not grp:
                continue
            s = stats(grp)
            w, l = s["avg_win_pc"], s["avg_loss_pc"]
            if w is None:
                say("| %s | %d | %s | - | - | - | - | no winners in bucket |" % (name, s["n"], pct(s["rate"])))
                continue
            lmag = -l if l is not None else None

            def e_at(L):
                if lmag is None:
                    return 100 * (1 - L) * w if L == 0 else None
                return 100 * ((1 - L) * w - L * lmag)
            ls = s["be_measured"]
            verdict = "-"
            if ls is not None:
                if s["rate"] < ls:
                    verdict = "ABOVE break-even" + (" -- whole interval above" if s["hi"] <= ls
                                                    else " -- but the interval reaches past L*, so a loss rate this data cannot rule out would lose money")
                else:
                    verdict = "BELOW break-even" + (" -- whole interval below" if s["lo"] >= ls else " -- interval reaches back under L*")
            elif lmag is None:
                verdict = "no loss yet in bucket; L* unknown"
            say("| %s | %d | %s [%s, %s] | %s | %s | %s | %s | %s |" % (
                name, s["n"], pct(s["rate"], 2), pct(s["lo"], 2), pct(s["hi"], 2), fmt(e_at(s["rate"])), fmt(e_at(s["lo"])),
                fmt(e_at(s["hi"])), pct(ls, 2) if ls else "-", verdict))
        say("")

    # ---------------------------------------------------------------- h) data quality
    say("## h) Data-quality notes")
    say("")
    noorder = [r for r in main_rows if r["n_orders"] == 0]
    say("- Main-table markets Kalshi settled with NO order record in any live log (bot died / never logged): %d -- %s" % (
        len(noorder), "; ".join("%s %s %+.2f (%s)" % (r["ticker"], r["close_et"], r["money"], r["version"]["how"]) for r in noorder) or "none"))
    nosettle = [r for r in main_rows if not r["log_settled"]]
    say("- Main-table markets with no `settled` log record (position open when the run died, or settled by a later run that did not know it): %d -- %s" % (
        len(nosettle), "; ".join("%s %+.2f" % (r["ticker"], r["money"]) for r in nosettle) or "none"))
    nolog = [r for r in rows if r["money"] is None and r["n_filled_orders"] > 0]
    say("- Markets with a FILLED order in a log but no Kalshi ledger row: %d -- %s" % (
        len(nolog), "; ".join("%s (last fill %s, %s contracts)" % (r["ticker"], r["legs"][-1]["t"], fmt(sum(o["filled"] for o in r["legs"]), 1)) for r in nolog) or "none"))
    nolog2 = [r for r in rows if r["money"] is None and r["n_filled_orders"] == 0 and (r["log_settled"] or r["hedge_filled_in_log"])]
    say("- Markets a log settled/hedged with no filled order and no ledger row: %d -- %s" % (
        len(nolog2), "; ".join(r["ticker"] for r in nolog2) or "none"))
    dis = [r for r in main_rows if r["pnl_c_disagrees"]]
    say("- Main-table markets where the log's summed pnl_c disagrees with Kalshi by more than $0.05: %d of %d with both -- %s" % (
        len(dis), sum(1 for r in main_rows if r["pnl_c_sum_dollars"] is not None),
        "; ".join("%s kalshi %+.2f log %+.2f" % (r["ticker"], r["money"], r["pnl_c_sum_dollars"]) for r in dis) or "none"))
    tf = [r for r in main_rows if abs((r["money_task_formula"] or 0) - r["money"]) > 0.005]
    say("- Markets where the orchestrator's formula (revenue/100 + min(yes,no) - costs - fee) differs from pinledger's value-aware payout by > $0.005: %d -- %s" % (
        len(tf), "; ".join("%s %+.2f vs %+.2f" % (r["ticker"], r["money"], r["money_task_formula"]) for r in tf) or "none"))
    unnamed = [f for f in files if not f["version_name"] or f["version_name"].startswith("pre-VERSIONS")]
    say("- Live log files with no VERSIONS.md name (before the first entry, v-cond 2026-09-10 07:47Z): %d files, %s .. %s; their flags are in live_versions.json" % (
        len(unnamed), unnamed[0]["file"] if unnamed else "-", unnamed[-1]["file"] if unnamed else "-"))
    slack = [f for f in files if f.get("version_matched_by_slack")]
    say("- Files matched to a version whose header time is AFTER the file start (within the 10-min slack for '~hh:mx' headers): %d -- %s" % (
        len(slack), "; ".join("%s -> %s (%s)" % (f["file"], f["version_name"], f["version_when"]) for f in slack) or "none"))
    nosha = [f for f in files if not f["code_sha"]]
    say("- Files with no code_sha in the start record: %d (code_sha first appears %s)" % (
        len(nosha), next((f["file"] for f in files if f["code_sha"]), "-")))
    say("- Overlapping live log files (two live processes at once): %s" % (json.dumps(vers["overlapping_pairs"]) if vers["overlapping_pairs"] else "none"))
    err_orders = [(r["ticker"], o) for r in rows for o in r["legs"] if o.get("error")]
    say("- Order records with an exchange error: %d (%s)" % (len(err_orders), dict(collections.Counter(str(o.get("error"))[:40] for _t, o in err_orders))))
    presend = [(r["ticker"], o) for r in rows for o in r["legs"] if o.get("refused") and o.get("status") is None]
    say("- Order records refused before the send (rail): %d" % len(presend))
    unattr = [r for r in main_rows if not r["version"]["file"]]
    say("- Main-table markets attributed to no log file at all: %d -- %s" % (len(unattr), "; ".join("%s %s %+.2f" % (r["ticker"], r["close_et"], r["money"]) for r in unattr) or "none"))
    both_nohedge = [r for r in main_rows if r["hedged_ledger"] and not r["hedge_filled_in_log"]]
    say("- Main-table markets holding both sides on Kalshi with no filled `hedge` record (plant test, A68 flip buy, or a dead run's hedge): %d -- %s" % (
        len(both_nohedge), "; ".join("%s %+.2f" % (r["ticker"], r["money"]) for r in both_nohedge) or "none"))
    # count-level check: bet-side contracts in the log vs Kalshi
    mism = []
    for r in main_rows:
        if r["n_filled_orders"] == 0:
            continue
        logc = sum(o["filled"] for o in r["legs"] if o["filled"] > 0 and o["want"] == r["want"])
        if r["bet_count"] is not None and abs(logc - r["bet_count"]) > 0.5:
            mism.append((r["ticker"], logc, r["bet_count"]))
    say("- Main-table markets whose bet-side contract count in the logs differs from Kalshi's by > 0.5: %d -- %s" % (
        len(mism), "; ".join("%s log %.1f kalshi %.1f" % m for m in mism[:40]) + (" ..." if len(mism) > 40 else "") if mism else "none"))

    # ---------------------------------------------------------------- reconciliation vs pinday
    say("")
    say("## Reconciliation against `python research/pinday.py --days 60`")
    say("")
    pd_path = os.path.join(OUT, "pinday_60.txt")
    by_day_mine = collections.defaultdict(lambda: [0, 0.0, 0])
    for r in main_rows:
        d = by_day_mine[r["et_day"]]
        d[0] += 1
        d[1] += r["money"]
        d[2] += r["money"] < 0
    if os.path.exists(pd_path):
        txt = open(pd_path, encoding="utf-8", errors="replace").read()
        pd_days = {}
        for m in re.finditer(r"^\s+(\d{4}-\d\d-\d\d)\s+crypto\s+\|\s+(\d+)\s+([+-]?\d+\.\d+)\s+(\d+)\s+\|", txt, re.M):
            pd_days[m.group(1)] = (int(m.group(2)), float(m.group(3)), int(m.group(4)))
        refreshed = re.search(r"last refreshed (.+?)\n", txt)
        say("pinday run saved in pinday_60.txt (its ledger: %s; this report's ledger written %s)." % (
            refreshed.group(1).strip() if refreshed else "?", ledger_written))
        say("")
        say("| ET day | pinday crypto markets | pinday $ | pinday losses | this dataset markets | $ | losses | $ gap |")
        say("|---|---|---|---|---|---|---|---|")
        days = sorted(set(pd_days) | set(by_day_mine))
        tp = tm = 0.0
        np_ = nm = 0
        for d in days:
            if d < "2026-09-08":
                continue
            a = pd_days.get(d, (0, 0.0, 0))
            b = by_day_mine.get(d, [0, 0.0, 0])
            tp += a[1]
            tm += b[1]
            np_ += a[0]
            nm += b[0]
            flag = "" if abs(a[1] - b[1]) < 0.005 and a[0] == b[0] else " <--"
            say("| %s | %d | %+.2f | %d | %d | %+.2f | %d | %+.2f%s |" % (d, a[0], a[1], a[2], b[0], b[1], b[2], b[1] - a[1], flag))
        say("| **since 09-08** | %d | %+.2f | | %d | %+.2f | | %+.2f |" % (np_, tp, nm, tm, tm - tp))
        say("")
        say("Difference over the same days: **%+.2f** (dataset %+.2f vs pinday %+.2f; markets %d vs %d)." % (tm - tp, tm, tp, nm, np_))
    else:
        say("pinday_60.txt not found -- reconciliation NOT run.")

    with open(os.path.join(OUT, "live_ledger_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
