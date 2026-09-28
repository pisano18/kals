"""missed.py -- the daily MISSED-TRADES report for the live bot (read-only).

The operator's standing watch on the "safe" live build (v-toxic-live,
v-ceiling978, v-onefull, early leg at a third): what did each safety gate turn
down, what happened to those markets, and did any gate look at a market we
then LOST on?

For a window (default: the last 24 h; --since UTC ISO; --all = since
2026-09-27 05:08Z, the first safe-build run) it reads every live pinrun log
(results/pinrun-live-*.jsonl) and groups every `refused` record by gate. Per
gate it reports:

  * distinct markets refused, and how many distinct closes they sat in
    (twelve coins settle on the same quarter hour, so a close is the unit);
  * how many of those markets we BOUGHT ANYWAY (already held before the
    refusal, or bought later) -- those are not missed trades;
  * for the rest, the market's settled result against the side we wanted:
    "would have won" / "would have lost" / not settled;
  * the price and size we would have taken (the gate's FIRST priced refusal
    in that market; size = min(offered, our bet), the bet being the run's
    size, a third of it on the 45-second leg, 1 contract on hourly BTC);
  * an UPPER-BOUND dollar figure: wins at the refused price, losses at full
    cost, taker fee included.

THE DOLLARS ARE AN UPPER BOUND, NOT OUR LOSS RATE (CLAUDE.md amendment
2026-09-10 rule 5). A refused market's result is the market's, i.e. the tape
population ("an offer was sitting there"). Ours is "someone sold it to us",
which loses far more often (0.11% tape vs 3.4% live, 09-11). So a gate's
"would have lost" count is a LOWER bound on what it saved and "would have won"
an UPPER bound on what it cost.

It also lists every LIVE LOSS in the window (from Kalshi's own ledger,
results/kalshi_ledger.json) and which gates, if any, refused that market
before or after our buy, plus the seller-gate readings at our entry.

Market results: our ledger, our own settled records, a cache
(results/missed_results_cache.json), then -- only for tickers still unknown
and closed > 2 min -- the PUBLIC GET /markets?tickers= endpoint (no key, no
order endpoint; --no-fetch turns it off).

  python research/missed.py                 # last 24 h
  python research/missed.py --all           # since 2026-09-27 05:08Z
  python research/missed.py --since 2026-09-28T04:00:00Z --out results/x.md
  python research/missed.py --selftest

stdlib only. Runs its own self-test first unless KALS_SELFTESTED=1.
"""
import argparse
import calendar
import collections
import glob
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
LEDGER = os.path.join(RESULTS, "kalshi_ledger.json")
CACHE = os.path.join(RESULTS, "missed_results_cache.json")
SAFE_START = "2026-09-27T05:08:00Z"
API = "https://api.elections.kalshi.com/trade-api/v2/markets"

# Gate display order. The first eight are the operator's named list; every
# other gate seen is listed after them under its own name.
NAMED = [
    ("price_ceiling", "price ceiling (no buys over 97.8c)"),
    ("price_ceiling_978", "  of which 97.9-98.0c (the 09-27 v-ceiling978 change)"),
    ("toxic_fresh", "seller gate (fresh offer while takers sell our side)"),
    ("rebuy_band", "second full bet (one-full-bet / cheaper-offer band)"),
    ("early_cheap", "45-second leg floor (under 95c)"),
    ("edge_floor", "edge floor (model edge under 0.3c)"),
    ("confidence", "confidence (model not sure enough)"),
    ("depth_floor", "depth (too few contracts offered)"),
    ("spike", "spike (confidence jumped in one second)"),
]
NAMES = dict(NAMED)
# Gates that refuse EXTRA size on a market we usually already hold.
SIZE_GATES = {"rebuy_band", "early_once", "max_per_market", "close_budget",
              "market_attempts", "late_boost", "staged_none"}
NOTHING_TO_BUY = {"no_offer"}
EARLY_TAU = 30           # tau > 30 s is the 45-second (early) leg
EARLY_FRAC = 0.333       # live --early-frac
HOURLY_BET = 1.0         # v-btcd1: hourly BTC ladder is 1 contract


# ---------------------------------------------------------------- helpers
def epoch(stamp):
    try:
        return calendar.timegm(time.strptime(str(stamp)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def et(ep):
    """UTC epoch -> 'MM-DD h:MM AM ET' (EDT Mar-Nov, EST otherwise)."""
    y = time.gmtime(ep).tm_year

    def nth_sunday(month, n):
        d = calendar.timegm((y, month, 1, 0, 0, 0))
        wd = time.gmtime(d).tm_wday          # Mon=0
        first = 1 + (6 - wd) % 7
        return calendar.timegm((y, month, first + 7 * (n - 1), 0, 0, 0))
    dst0 = nth_sunday(3, 2) + 7 * 3600
    dst1 = nth_sunday(11, 1) + 6 * 3600
    off = -4 if dst0 <= ep < dst1 else -5
    g = time.gmtime(ep + off * 3600)
    h = g.tm_hour % 12 or 12
    return "%02d-%02d %d:%02d %s ET" % (g.tm_mon, g.tm_mday, h, g.tm_min,
                                         "AM" if g.tm_hour < 12 else "PM")


def fee(p, n):
    return 0.07 * p * (1.0 - p) * n


def coin(tk):
    s = tk.split("-")[0]
    return s.replace("KX", "").replace("15M", "")


def is_hourly(tk):
    return tk.startswith("KXBTCD-")


def f(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def upper_bound(want, result, price, take):
    """$ if the refused buy had filled: win at the price, loss at full cost."""
    if price is None or take is None or result not in ("yes", "no") or not want:
        return None
    if result == want:
        return take * (1.0 - price) - fee(price, take)
    return -(take * price + fee(price, take))


def take_of(rec):
    """Contracts we would have taken on this refusal (None if unknowable)."""
    tk = rec.get("ticker", "")
    bet = f(rec.get("size_now"))
    if bet is None:
        return None
    if is_hourly(tk):
        bet = min(bet, HOURLY_BET)
    else:
        leg = rec.get("leg")
        tau = f(rec.get("tau"), 0)
        if leg == "early" or (leg is None and tau > EARLY_TAU
                              and rec.get("gate") not in SIZE_GATES):
            bet = bet * EARLY_FRAC
        if rec.get("gate") == "late_boost":
            bet = bet * 0.5            # --late-mult 1.5 adds half a bet
    off = f(rec.get("size"))
    if rec.get("gate") in ("spike", "late_boost"):
        off = None                     # their `size` is our size, not the offer
    return bet if off is None else min(off, bet)


def want_of(rec, bought_want=None):
    w = rec.get("want") or rec.get("wanted_side")
    if w in ("yes", "no"):
        return w
    if rec.get("gate") == "confidence" and f(rec.get("fair")) is not None:
        return "yes" if f(rec["fair"]) >= 0.5 else "no"
    return bought_want


# ---------------------------------------------------------------- loading
def load_logs(paths, since_ep, until_ep):
    """(refusals, entries, failed_orders, hedges). Deduplicated: the restored
    09-25 log and a crash-restart can repeat records."""
    refusals, entries, failed, hedge_ids = [], [], [], set()
    seen_r, seen_o = set(), set()
    orders = []
    signals = collections.defaultdict(list)
    for p in paths:
        try:
            fh = open(p, encoding="utf-8")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"kind"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                k = r.get("kind")
                if k not in ("refused", "late_refused", "order", "hedge",
                             "signal"):
                    continue
                ep = epoch(r.get("t"))
                if ep is None:
                    continue
                if k == "signal":
                    if r.get("live") is not False:
                        signals[r.get("ticker")].append(
                            (ep, r.get("leg"), r.get("level_age_ms")))
                    continue
                if k == "hedge":
                    if r.get("order_id"):
                        hedge_ids.add(r["order_id"])
                    continue
                if k == "order":
                    key = r.get("order_id") or (r.get("t"), r.get("ticker"),
                                                r.get("client_order_id"))
                    if key in seen_o:
                        continue
                    seen_o.add(key)
                    r["_ep"] = ep
                    orders.append(r)
                    continue
                if not (since_ep <= ep < until_ep):
                    continue
                if k == "late_refused":
                    r = dict(r, gate="late_boost")
                key = (r.get("t"), r.get("gate"), r.get("ticker"), r.get("tau"),
                       r.get("price"))
                if key in seen_r:
                    continue
                seen_r.add(key)
                r["_ep"] = ep
                refusals.append(r)
    for o in orders:
        if o.get("order_id") in hedge_ids or o.get("leg") == "hedge":
            continue
        if o.get("level_age_ms") is None:
            # the order record does not carry the offer's age; its signal does
            c = [s for s in signals.get(o.get("ticker"), [])
                 if s[0] <= o["_ep"] and s[1] == o.get("leg")]
            if c:
                o["level_age_ms"] = max(c)[2]
        n = f(o.get("filled"), 0.0)
        if n > 0:
            entries.append(o)
        elif since_ep <= o["_ep"] < until_ep:
            failed.append(o)
    return refusals, entries, failed


def ledger_rows(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return {}
    rows = d.get("settlements") if isinstance(d, dict) else None
    return rows if isinstance(rows, dict) else {}


def ledger_pnl(s):
    """pinledger.pnl: payout from result x contracts held, NOT `revenue`
    (Kalshi reports revenue 0 when we held both sides -- every insured
    market -- which once turned -$27.87 into -$126.87)."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import pinledger
    return pinledger.pnl(s)


def fetch_results(tickers, cache, log=print):
    """Public GET /markets?tickers=... in batches of 50. Fills `cache`."""
    tickers = sorted(tickers)
    got = 0
    for i in range(0, len(tickers), 50):
        chunk = tickers[i:i + 50]
        url = API + "?limit=100&tickers=" + ",".join(chunk)
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                b = json.loads(r.read().decode())
        except Exception as e:           # report, never guess
            log("  (result lookup failed for %d tickers: %s)" % (len(chunk), e))
            continue
        for mk in b.get("markets") or []:
            if mk.get("status") in ("finalized", "settled") and \
                    mk.get("result") in ("yes", "no"):
                cache[mk["ticker"]] = mk["result"]
                got += 1
        time.sleep(0.5)
    return got


# ---------------------------------------------------------------- analysis
def analyse(refusals, entries, results, losses_rows):
    """Pure function. results: {ticker: 'yes'|'no'}; losses_rows: ledger
    rows settled in the window. Returns a dict the report prints."""
    ent_by_tk = collections.defaultdict(list)
    for e in entries:
        ent_by_tk[e.get("ticker")].append(e)
    by_gate = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in refusals:
        by_gate[r.get("gate") or "?"][r.get("ticker")].append(r)
        p0 = f(r.get("price"))
        if r.get("gate") == "price_ceiling" and p0 is not None and 0.978 < p0 <= 0.9805:
            # the slice the 09-27 change added (the old ceiling was 98c)
            by_gate["price_ceiling_978"][r.get("ticker")].append(
                dict(r, gate="price_ceiling_978"))

    gates = {}
    for g, mk in by_gate.items():
        row = {"gate": g, "markets": 0, "records": 0, "closes": set(),
               "held_before": 0, "bought_later": 0, "bought_won": 0,
               "bought_lost": 0, "won": 0, "lost": 0, "open": 0, "noside": 0,
               "ub_win": 0.0, "ub_loss": 0.0, "noprice": 0, "contracts": 0.0,
               "prices": [], "lost_list": [], "extra_ub": 0.0, "extra_n": 0,
               "won_list": []}
        for tk, recs in mk.items():
            recs.sort(key=lambda r: r["_ep"])
            row["markets"] += 1
            row["records"] += len(recs)
            first = recs[0]
            cl = f(first.get("close_s"))
            row["closes"].add(cl if cl is not None else tk)
            priced = [r for r in recs if f(r.get("price")) is not None]
            rec = priced[0] if priced else first
            ents = ent_by_tk.get(tk, [])
            res = results.get(tk)
            if ents:
                bw = ents[0].get("want")
                if any(e["_ep"] <= first["_ep"] for e in ents):
                    row["held_before"] += 1
                else:
                    row["bought_later"] += 1
                if res in ("yes", "no"):
                    row["bought_won" if res == bw else "bought_lost"] += 1
                if g in SIZE_GATES and priced:
                    w = want_of(rec, bw)
                    ub = upper_bound(w, res, f(rec.get("price")), take_of(rec))
                    if ub is not None:
                        row["extra_ub"] += ub
                        row["extra_n"] += 1
                continue
            w = want_of(rec)
            if w is None:
                row["noside"] += 1
                continue
            if res not in ("yes", "no"):
                row["open"] += 1
                continue
            price = f(rec.get("price"))
            take = take_of(rec) if price is not None else None
            ub = upper_bound(w, res, price, take)
            item = {"ticker": tk, "want": w, "result": res, "price": price,
                    "take": take, "ub": ub, "tau": rec.get("tau"),
                    "ep": rec["_ep"], "share": rec.get("sell_share_3s"),
                    "age": rec.get("level_age_ms")}
            if res == w:
                row["won"] += 1
                row["won_list"].append(item)
            else:
                row["lost"] += 1
                row["lost_list"].append(item)
            if ub is None:
                row["noprice"] += 1
            else:
                row["ub_win" if ub > 0 else "ub_loss"] += ub
                row["contracts"] += take
                row["prices"].append(price)
        row["closes"] = len(row["closes"])
        row["net_ub"] = row["ub_win"] + row["ub_loss"]
        known = row["won"] + row["lost"]
        # FLAG: the gate refused mostly winners -- on the TAPE population its
        # refusals made money even counting every loss at full cost.
        row["flag"] = bool(known >= 3 and row["won"] / known >= 0.9
                           and row["net_ub"] > 0 and g not in NOTHING_TO_BUY)
        gates[g] = row

    # live losses (ledger = Kalshi's own money) and which gates looked
    ref_by_tk = collections.defaultdict(collections.Counter)
    for r in refusals:
        ref_by_tk[r.get("ticker")][r.get("gate")] += 1
    losses = []
    for s in losses_rows:
        pnl = ledger_pnl(s)
        if pnl >= 0:
            continue
        tk = s.get("ticker", "")
        ents = sorted(ent_by_tk.get(tk, []), key=lambda e: e["_ep"])
        both = f(s.get("yes_count_fp"), 0) > 0 and f(s.get("no_count_fp"), 0) > 0
        losses.append({"ticker": tk, "pnl": pnl, "result": s.get("market_result"),
                       "insured": both,
                       "settled": s.get("settled_time"),
                       "gates": dict(ref_by_tk.get(tk, {})),
                       "entries": [{"leg": e.get("leg"), "want": e.get("want"),
                                    "n": f(e.get("filled")),
                                    "price": f(e.get("exec_price")),
                                    "tau": e.get("tau_at_send"),
                                    "share": e.get("sell_share_3s"),
                                    "age": e.get("level_age_ms"),
                                    "ep": e["_ep"]} for e in ents]})
    losses.sort(key=lambda x: x["pnl"])
    return {"gates": gates, "losses": losses}


def need_results(refusals, entries, results, now_ep):
    held = {e.get("ticker") for e in entries}
    out = set()
    for r in refusals:
        tk = r.get("ticker")
        cl = f(r.get("close_s"))
        if tk and tk not in results and cl is not None and cl < now_ep - 120:
            if r.get("gate") in NOTHING_TO_BUY and tk not in held:
                # still wanted: tells us if an empty book was a winner
                pass
            out.add(tk)
    return out


# ---------------------------------------------------------------- report
def money(x):
    return ("-$%.2f" % -x) if x < 0 else ("+$%.2f" % x)


def detect_line(known, lost):
    if known == 0:
        return "no settled market to judge"
    if lost == 0:
        return ("0 losers in %d: only a loser rate of about %d in 100 or more "
                "would likely have shown" % (known, min(100, round(300.0 / known))))
    return "%d loser(s) in %d" % (lost, known)


def render(an, since_ep, until_ep, extra, out):
    say = out
    gates = an["gates"]
    order = [g for g, _ in NAMED] + sorted(
        (g for g in gates if g not in NAMES),
        key=lambda g: -gates[g]["markets"])
    say("# Missed trades -- %s to %s" % (et(since_ep), et(until_ep)))
    say("")
    say("Written by `python research/missed.py` (read-only). Our money is from "
        "Kalshi's ledger. A refused market's win/loss is the MARKET's result "
        "(everyone's offers, not the ones sold to us): the $ column is the MOST "
        "a gate could have cost us, and its loser count is the FEWEST losses it "
        "saved us. Never read it as how often we lose.")
    say("")
    for line in extra.get("head", []):
        say(line)
    say("")
    say("## Per gate")
    say("")
    say("| gate | markets refused (closes) | we bought anyway (our result: won / lost) | never bought: would have won / lost / not settled | contracts we'd have taken, typical price | most it could have cost us (wins) | losses it saved at least | net | one loss like these would cost | flag |")
    say("|---|---|---|---|---|---|---|---|---|---|")
    for g in order:
        r = gates.get(g)
        if r is None:
            if g in NAMES:
                say("| %s | 0 | - | - | - | - | - | - | - | |" % NAMES[g])
            continue
        name = NAMES.get(g, g)
        pr = sorted(r["prices"])
        typ = ("%.0f at %.1fc" % (r["contracts"], 100 * pr[len(pr) // 2])) if pr else "no price logged"
        bought = r["held_before"] + r["bought_later"]
        bl = "%d (%d held already, %d later; %d / %d)" % (
            bought, r["held_before"], r["bought_later"], r["bought_won"], r["bought_lost"])
        n_pr = len(pr)
        one = ("%s" % money(-(r["contracts"] / n_pr) * (sum(pr) / n_pr))) if n_pr else "-"
        wl = "%d / %d / %d" % (r["won"], r["lost"], r["open"])
        if r["noside"]:
            wl += " (+%d no side)" % r["noside"]
        if g in NOTHING_TO_BUY:
            flag = "nothing offered"
        else:
            flag = "FLAG: mostly winners" if r["flag"] else ""
        say("| %s | %d (%d) | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            name, r["markets"], r["closes"], bl, wl, typ,
            money(r["ub_win"]) if pr else "-", money(r["ub_loss"]) if pr else "-",
            money(r["net_ub"]) if pr else "-", one, flag))
    say("")
    say("## What each gate's sample can show")
    say("")
    for g in order:
        r = gates.get(g)
        if not r or g in NOTHING_TO_BUY:
            continue
        known = r["won"] + r["lost"]
        extra_s = ""
        if r["extra_n"]:
            extra_s = ("; on %d market(s) we already held, the refused EXTRA bet "
                       "would have made at most %s" % (r["extra_n"], money(r["extra_ub"])))
        if known == 0 and r["held_before"] + r["bought_later"] == r["markets"]:
            dl = "every refused market was bought anyway (ours: %d won, %d lost)" % (
                r["bought_won"], r["bought_lost"])
        else:
            dl = detect_line(known, r["lost"])
            if r["prices"] and r["net_ub"] > 0:
                avg_loss = (r["contracts"] / len(r["prices"])) * (sum(r["prices"]) / len(r["prices"]))
                dl += ("; the most it cost is about %.1f loss(es) of a typical size here (%s each)"
                       % (r["net_ub"] / avg_loss, money(-avg_loss)))
        say("- %s: %s%s." % (NAMES.get(g, g), dl, extra_s))
        for it in sorted(r["lost_list"], key=lambda x: x["ep"]):
            say("  - would have LOST: %s %s, %s at %s, %s s left%s" % (
                et(it["ep"]), it["ticker"], it["want"].upper(),
                ("%.1fc" % (100 * it["price"])) if it["price"] is not None else "no price",
                it["tau"],
                (", %.0f contracts = %s" % (it["take"], money(it["ub"]))) if it["ub"] is not None else ""))
    say("")
    say("## Live losses in the window (Kalshi ledger)")
    say("")
    if not an["losses"]:
        say("None.")
    for L in an["losses"]:
        sides = {e["want"] for e in L["entries"]}
        verdict = ""
        if len(sides) == 1 and L["result"] in ("yes", "no"):
            won = L["result"] in sides
            if won and L.get("insured"):
                verdict = " Our bet WON; the loss is the insurance we bought."
            elif won:
                verdict = " Our bet WON."
            else:
                verdict = " Our bet LOST%s." % (" (insured)" if L.get("insured") else "")
        say("- %s: %s, market settled %s.%s Gates that refused this market in the "
            "window: %s." % (
                L["ticker"], money(L["pnl"]), (L["result"] or "?").upper(), verdict,
                ", ".join("%s x%d" % (k, v) for k, v in sorted(L["gates"].items()))
                or "none"))
        for e in L["entries"]:
            say("  - our buy: %s %s %.0f @ %.1fc, %s s left, sellers %s of our side "
                "in 3 s, offer %s ms old" % (
                    et(e["ep"]), (e["want"] or "?").upper(), e["n"] or 0,
                    100 * (e["price"] or 0), e["tau"],
                    ("%d in 100" % round(100 * e["share"])) if isinstance(e["share"], (int, float)) else "?",
                    e["age"] if e["age"] is not None else "?"))
    for line in extra.get("tail", []):
        say(line)


# ---------------------------------------------------------------- self-test
def selftest():
    fails = []

    def ck(c, m):
        if not c:
            fails.append(m)
    T0 = epoch("2026-09-27T10:00:00Z")

    def R(gate, tk, dt, **kw):
        d = {"kind": "refused", "gate": gate, "ticker": tk, "close_s": T0 + 900,
             "size_now": 90.0, "t": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                   time.gmtime(T0 + dt))}
        d.update(kw)
        return d

    recs = [
        # price ceiling: two markets never bought, one won one lost
        R("price_ceiling", "KXA15M-X", 870, want="yes", price=0.98, size=500, tau=25),
        R("price_ceiling", "KXA15M-X", 871, want="yes", price=0.99, size=500, tau=24),  # later, ignored
        R("price_ceiling", "KXB15M-X", 870, want="no", price=0.99, size=10, tau=25),
        R("price_ceiling", "KXB15M-X", 870, want="no", price=0.99, size=10, tau=25),    # duplicate
        # early floor on the 45-second leg: take a third of 90 = 29.97
        R("early_cheap", "KXC15M-X", 860, leg="early", want="yes", price=0.90, size=1000, tau=40),
        # toxic refused, then we bought it anyway later
        R("toxic_fresh", "KXD15M-X", 870, leg="full", want="no", price=0.97, size=50, tau=25),
        # confidence: no want, fair 0.2 -> lean NO, no price
        R("confidence", "KXE15M-X", 860, fair=0.2, tau=40),
        # outside window -> ignored
        R("spike", "KXF15M-X", -5000, want="yes", price=0.95, size=90, tau=5),
        # a rebuy_band on a held market (size gate): extra bet valued
        R("rebuy_band", "KXD15M-X", 880, want="no", price=0.96, size=40, tau=15),
        # unsettled market
        R("edge_floor", "KXG15M-X", 870, want="yes", price=0.99, size=20, tau=25),
    ]
    orders = [
        {"kind": "order", "ticker": "KXD15M-X", "order_id": "o1", "filled": 90,
         "exec_price": 0.96, "want": "no", "leg": "full", "tau_at_send": 20,
         "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T0 + 875))},
        # a hedge order on KXA must NOT count as buying KXA
        {"kind": "order", "ticker": "KXA15M-X", "order_id": "h1", "filled": 90,
         "exec_price": 0.3, "want": "no", "t": time.strftime(
             "%Y-%m-%dT%H:%M:%SZ", time.gmtime(T0 + 880))},
        {"kind": "hedge", "ticker": "KXA15M-X", "order_id": "h1",
         "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T0 + 880))},
        # a failed order
        {"kind": "order", "ticker": "KXBTCD-X", "order_id": "o2", "filled": 0,
         "status_code": 400, "error": {"code": "invalid_price"},
         "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T0 + 870))},
    ]
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, "pinrun-live-test.jsonl")
    with open(p, "w") as fh:
        for r in recs + orders:
            fh.write(json.dumps(r) + "\n")
    ref, ent, failed = load_logs([p], T0, T0 + 86400)
    ck(len(ref) == len(recs) - 2, "dedupe+window: %d refusals" % len(ref))
    ck(len(ent) == 1 and ent[0]["ticker"] == "KXD15M-X", "hedge excluded from entries")
    ck(len(failed) == 1, "failed order kept")
    results = {"KXA15M-X": "yes", "KXB15M-X": "yes", "KXC15M-X": "yes",
               "KXD15M-X": "no", "KXE15M-X": "no"}
    loss_rows = [{"ticker": "KXD15M-X", "market_result": "yes", "revenue": 0,
                  "value": 100, "no_count_fp": "90.00",
                  "no_total_cost_dollars": "86.4", "fee_cost": "0.2"},
                 # insured market: both sides held, revenue 0, true pnl -4
                 {"ticker": "KXH15M-X", "market_result": "yes", "revenue": 0,
                  "value": 100, "yes_count_fp": "10.00", "no_count_fp": "10.00",
                  "yes_total_cost_dollars": "9.0", "no_total_cost_dollars": "5.0",
                  "fee_cost": "0.0"},
                 {"ticker": "KXZ15M-X", "market_result": "yes", "revenue": 1000,
                  "value": 100, "yes_count_fp": "10.00",
                  "yes_total_cost_dollars": "9.5", "fee_cost": "0.0"}]
    an = analyse(ref, ent, results, loss_rows)
    g = an["gates"]
    pc = g["price_ceiling"]
    ck(pc["markets"] == 2 and pc["won"] == 1 and pc["lost"] == 1,
       "ceiling won/lost %s/%s" % (pc["won"], pc["lost"]))
    exp_w = 90 * 0.02 - fee(0.98, 90)            # A: first priced record, take 90
    exp_l = -(10 * 0.99 + fee(0.99, 10))         # B: offered 10 < bet 90
    ck(abs(pc["ub_win"] - exp_w) < 1e-9, "ceiling win bound %.4f vs %.4f" % (pc["ub_win"], exp_w))
    ck(abs(pc["ub_loss"] - exp_l) < 1e-9, "ceiling loss bound %.4f vs %.4f" % (pc["ub_loss"], exp_l))
    ec = g["early_cheap"]
    exp_e = 90 * EARLY_FRAC * 0.10 - fee(0.90, 90 * EARLY_FRAC)
    ck(abs(ec["ub_win"] - exp_e) < 1e-9, "early third %.4f vs %.4f" % (ec["ub_win"], exp_e))
    tx = g["toxic_fresh"]
    ck(tx["bought_later"] == 1 and tx["won"] + tx["lost"] == 0 and tx["bought_won"] == 1,
       "toxic bought-anyway")
    cf = g["confidence"]
    ck(cf["won"] == 1 and cf["noprice"] == 1 and cf["ub_win"] == 0, "confidence lean, no price")
    ck("spike" not in g, "out-of-window refusal dropped")
    rb = g["rebuy_band"]
    exp_x = 40 * 0.04 - fee(0.96, 40)
    ck(rb["held_before"] == 1 and rb["extra_n"] == 1 and abs(rb["extra_ub"] - exp_x) < 1e-9,
       "size gate extra bet %.4f vs %.4f" % (rb["extra_ub"], exp_x))
    ck(g["edge_floor"]["open"] == 1, "unsettled counted open")
    # a refusal in the SAME second as our buy counts as already held
    same = [dict(R("max_per_market", "KXD15M-X", 875, tau=20), _ep=T0 + 875)]
    an3 = analyse(same, ent, results, [])
    ck(an3["gates"]["max_per_market"]["held_before"] == 1, "same-second = held")
    ck(any(L["ticker"] == "KXH15M-X" and abs(L["pnl"] + 4.0) < 1e-9
           for L in an["losses"]), "both-sides market paid its winning side")
    ck(len(an["losses"]) == 2 and an["losses"][0]["ticker"] == "KXD15M-X"
       and abs(an["losses"][0]["pnl"] + 86.6) < 1e-9
       and an["losses"][0]["gates"].get("toxic_fresh") == 1, "live loss + gate that looked")
    ck(not pc["flag"], "ceiling (1 of 2 lost) must not be flagged")
    # a gate refusing only winners must be flagged
    many = [R("depth_floor", "KXW%d15M-X" % i, 870, want="yes", price=0.95, size=5, tau=20)
            for i in range(5)]
    an2 = analyse([dict(r, _ep=epoch(r["t"])) for r in many], [],
                  {"KXW%d15M-X" % i: "yes" for i in range(5)}, [])
    ck(an2["gates"]["depth_floor"]["flag"], "all-winner gate flagged")
    # EMPTY WORLD: nothing refused, nothing lost -> nothing reported, no flag
    an0 = analyse([], [], {}, [])
    ck(an0["gates"] == {} and an0["losses"] == [], "empty world finds nothing")
    lines = []
    render(an0, T0, T0 + 3600, {}, lines.append)
    ck(any("None." in x for x in lines), "empty render says None")
    lines = []
    render(an, T0, T0 + 86400, {}, lines.append)
    ck(sum("FLAG" in x for x in lines) == 0, "no flag in the planted world")
    # ET conversion: 09-27 14:00Z = 10:00 AM ET; 12-01 14:00Z = 9:00 AM ET
    ck(et(epoch("2026-09-27T14:00:00Z")) == "09-27 10:00 AM ET", et(epoch("2026-09-27T14:00:00Z")))
    ck(et(epoch("2026-12-01T14:00:00Z")) == "12-01 9:00 AM ET", "EST in December")
    try:
        os.remove(p)
        os.rmdir(d)
    except OSError:
        pass
    for m in fails:
        print("SELFTEST FAIL:", m)
    print("missed selftest: %s (%d checks failed)" % ("PASS" if not fails else "FAIL", len(fails)))
    return not fails


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", help="UTC ISO start, e.g. 2026-09-28T04:00:00Z")
    ap.add_argument("--until", help="UTC ISO end (default now)")
    ap.add_argument("--all", action="store_true", help="since " + SAFE_START)
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--out", help="also write the report here (markdown)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        sys.exit("self-test failed; not reading real data")
    now = time.time()
    until_ep = epoch(a.until) if a.until else int(now)
    if a.all:
        since_ep = epoch(SAFE_START)
    elif a.since:
        since_ep = epoch(a.since)
    else:
        since_ep = int(until_ep - a.hours * 3600)
    if since_ep is None or until_ep is None:
        sys.exit("bad --since/--until")
    paths = [p for p in sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl")))
             if os.path.getmtime(p) >= since_ep - 3600]
    refusals, entries, failed = load_logs(paths, since_ep, until_ep)

    rows = ledger_rows(LEDGER)
    results = {}
    try:
        with open(CACHE, encoding="utf-8") as fh:
            results.update(json.load(fh))
    except (OSError, ValueError):
        pass
    for s in rows.values():
        if isinstance(s, dict) and s.get("market_result") in ("yes", "no"):
            results[s.get("ticker")] = s["market_result"]
    head = []
    need = need_results(refusals, entries, results, now)
    need |= {o.get("ticker") for o in failed
             if o.get("ticker") and o.get("ticker") not in results
             and o["_ep"] < now - 120}
    fetched = 0
    if need and not a.no_fetch:
        cache = {}
        fetched = fetch_results(need, cache, log=lambda s: head.append(s))
        results.update(cache)
        try:
            old = {}
            if os.path.exists(CACHE):
                with open(CACHE, encoding="utf-8") as fh:
                    old = json.load(fh)
            old.update(cache)
            with open(CACHE, "w", encoding="utf-8") as fh:
                json.dump(old, fh, sort_keys=True)
        except (OSError, ValueError):
            pass
    win_rows = []
    for s in rows.values():
        if not isinstance(s, dict):
            continue
        ep = epoch(s.get("settled_time"))
        if ep is not None and since_ep <= ep < until_ep:
            win_rows.append(s)
    an = analyse(refusals, entries, results, win_rows)

    # money in the window, by book, from the ledger
    books = collections.defaultdict(lambda: [0, 0, 0.0])
    for s in win_rows:
        tk = s.get("ticker", "")
        b = ("15-minute coins" if "15M-" in tk and not tk.startswith("KXCRYPTO")
             else "hourly BTC" if tk.startswith("KXBTCD") else "other (race etc.)")
        pnl = ledger_pnl(s)
        books[b][0] += 1
        books[b][1] += pnl < 0
        books[b][2] += pnl
    head.append("Logs read: %d live file(s); %d refusal records; %d of our buys "
                "(insurance excluded); results looked up online this run: %d; "
                "markets still without a result: %d." % (
                    len(paths), len(refusals),
                    sum(1 for e in entries if since_ep <= e["_ep"] < until_ep), fetched,
                    len(need_results(refusals, entries, results, now))))
    head.append("")
    head.append("Our real money in the window (Kalshi ledger, by settle time): " + "; ".join(
        "%s %d markets, %d lost, %s" % (b, v[0], v[1], money(v[2]))
        for b, v in sorted(books.items())) + ".")
    ew = [e for e in entries if since_ep <= e["_ep"] < until_ep]
    early_in = {e.get("ticker") for e in ew if e.get("leg") == "early"}
    early_tox = {r.get("ticker") for r in refusals
                 if r.get("gate") == "toxic_fresh" and r.get("leg") == "early"}
    tried = early_in | early_tox
    # the gate only acts with more than 20 s left: that is the other reading
    # of POSTMORTEM_2026-09-27's "early entries"; both are printed
    act_in = {e.get("ticker") for e in ew if f(e.get("tau_at_send"), 0) > 20}
    act_tox = {r.get("ticker") for r in refusals if r.get("gate") == "toxic_fresh"}
    act = act_in | act_tox
    if tried or act:
        head.append("")
        head.append("Seller gate share (its OFF line: more than 25 in 100 of early "
                    "entries): on the 45-second leg it refused %d of %d markets that "
                    "leg wanted (%d in 100); counting every buy with more than 20 s "
                    "left, %d of %d (%d in 100)." % (
                        len(early_tox - early_in), len(tried),
                        round(100.0 * len(early_tox - early_in) / max(1, len(tried))),
                        len(act_tox - act_in), len(act),
                        round(100.0 * len(act_tox - act_in) / max(1, len(act)))))
    tail = []
    if failed:
        errs = collections.Counter()
        for o in failed:
            e = o.get("error")
            code = e.get("code") if isinstance(e, dict) else (str(e)[:40] if e else "filled nothing")
            errs[("KXBTCD hourly" if is_hourly(o.get("ticker", "")) else "15-minute", o.get("status_code"), code)] += 1
        tail.append("")
        tail.append("## Orders we SENT that bought nothing")
        tail.append("")
        for (b, st, code), n in errs.most_common():
            tail.append("- %s: %d order(s), status %s, %s" % (b, n, st, code))
        tail.append("")
        tail.append("| ET | market | side | offer seen | contracts asked | why nothing | market result | most it could have made |")
        tail.append("|---|---|---|---|---|---|---|---|")
        tot = 0.0
        for o in sorted(failed, key=lambda o: o["_ep"]):
            e = o.get("error")
            code = e.get("code") if isinstance(e, dict) else "filled nothing"
            p0 = f(o.get("ask_seen"))
            n0 = f((o.get("body") or {}).get("count"))
            res = results.get(o.get("ticker"))
            ub = upper_bound(o.get("want"), res, p0, n0)
            tot += ub or 0.0
            tail.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                et(o["_ep"]), o.get("ticker"), (o.get("want") or "?").upper(),
                ("%.1fc" % (100 * p0)) if p0 is not None else "?",
                ("%.0f" % n0) if n0 is not None else "?", code,
                (res or "not settled").upper(), money(ub) if ub is not None else "-"))
        tail.append("")
        tail.append("Total, if every one had filled at the offer seen: %s (upper bound)." % money(tot))
    lines = []
    render(an, since_ep, until_ep, {"head": head, "tail": tail}, lines.append)
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    if a.out:
        if os.path.dirname(a.out):
            os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)


if __name__ == "__main__":
    main()
