"""pinver -- everything the live log knows about ONE version of the bot.

WHY A FILE AND NOT A ONE-LINER. Three of these numbers have been reported
wrong from ad-hoc scripts in the last two days:

  * a glob comparison against a forward-slash cutoff silently matched every
    historical file, because Python's glob returns `results\\...` on Windows.
    Old losses appeared in a window meant to hold tonight's;
  * three fills on ONE close were counted as three losses, making NEAR look
    3-of-18 when by close it is 1-of-18. Rule 4: cluster by CLOSE;
  * a hedge leg settles under the SAME ticker as the bet it protects, so
    counting `settled` records as bets double-counts every hedged market.

VERSION BOUNDARY. `start` records carry every decision parameter. A version
ends where any of them changes. `code_sha` alone is NOT a version change --
it moves on bugfixes that cannot alter a decision -- so DECISION_KEYS lists
the fields that do, and the default window is the last run of runs sharing
them.

Loss rates here are LIVE FILLS. That is the only source CLAUDE.md rule 5
permits for a statement about our losses.
"""
import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESULTS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "results")

# Every field that can change a TRADE DECISION. code_sha and minutes are
# deliberately absent: a bugfix or a longer session is the same strategy.
DECISION_KEYS = (
    "pin", "tau_min", "tau_max", "edge_floor", "ev_floor", "price_ceiling",
    "max_per_close", "max_per_market", "improve_by", "min_level",
    "min_fill_frac", "dump_enabled", "dump_discount", "hedge_enabled",
    "hedge_belief", "hedge_max_ask", "hedge_max_tries",
    "hedge_pilot_contracts", "sigma_stress", "sigma_win", "max_book_age_ms",
    "max_index_age_s",
)


def read_run(path):
    """One run file -> (start_record, [records])."""
    recs = []
    start = None
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("kind") == "start" and start is None:
                start = r
            recs.append(r)
    return start, recs


def decision_key(start):
    return tuple((k, (start or {}).get(k)) for k in DECISION_KEYS)


def runs(results=RESULTS):
    """Every live run, oldest first, with its decision key."""
    out = []
    for p in sorted(glob.glob(os.path.join(results, "pinrun-live-*.jsonl"))):
        st, recs = read_run(p)
        if st is None:
            continue
        out.append({"path": p, "name": os.path.basename(p), "start": st,
                    "key": decision_key(st), "recs": recs})
    return out


def current_version(rs):
    """The trailing block of runs that share a decision key."""
    if not rs:
        return []
    k = rs[-1]["key"]
    block = []
    for r in reversed(rs):
        if r["key"] != k:
            break
        block.append(r)
    return list(reversed(block))


def cp_interval(k, n, conf=0.95):
    """Clopper-Pearson, both tails. Exact; the normal approximation is badly
    wrong at these counts and has flattered this project before."""
    if n <= 0:
        return 0.0, 1.0

    def _tail(p, upto):
        s, term = 0.0, (1.0 - p) ** n
        for i in range(0, upto + 1):
            if i:
                term *= (n - i + 1) / i * p / (1.0 - p) if p < 1 else 0.0
            s += term
        return s
    al = (1.0 - conf) / 2.0
    lo, hi = 0.0, 0.0
    if k > 0:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if _tail(m, k - 1) > 1 - al:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if _tail(m, k) > al:
                a = m
            else:
                b = m
        hi = (a + b) / 2
    else:
        hi = 1.0
    return lo, hi


def market_of(ticker):
    """The MARKET: ticker with the strike stripped. One series, one window.
    KXNEAR15M-26SEP122015-15 -> KXNEAR15M-26SEP122015."""
    return ticker.rsplit("-", 1)[0]


def close_of(ticker):
    """The CLOSE, which is a TIME and is SHARED BY EVERY SERIES.
    KXNEAR15M-26SEP122015-15 -> 26SEP122015.

    THIS IS RULE 4 AND IT IS EASY TO GET WRONG. An earlier version of this
    file returned market_of() and called it a close, which made 36 markets
    look like 36 independent observations. They are not: all twelve crypto
    series settle on the SAME second against correlated indices (rho ~ 0.8),
    so a close is worth ~1.22 independent observations, not 12. Clustering on
    series+time silently inflates n and tightens every interval below."""
    parts = ticker.split("-")
    return parts[1] if len(parts) >= 2 else ticker


def summarise(block):
    """Every countable thing in one version's logs."""
    s = {
        "runs": len(block), "files": [b["name"] for b in block],
        "signals": 0, "orders": 0, "asked": 0.0, "filled": 0.0,
        "order_fail": 0, "zero_fill": 0, "partial": 0, "full": 0,
        "scrap": 0, "scrap_contracts": 0.0, "dumped": 0,
        "hedge_alarm": 0, "hedge_fill": 0, "hedge_no_ask": 0,
        "hedge_gave_up": 0, "hedge_contracts": 0.0, "hedge_cost": 0.0,
        "closes_watched": set(), "markets_watched": set(),
        "closes_fired": 0,
        "looks": 0, "decided": 0, "undecided": 0, "no_offer": 0, "dust": 0,
        "tradeable": 0, "over_ceiling": 0, "neg_ev": 0,
        "prices": [], "edges": [], "takes": [],
        "settled_n": 0,
    }
    per_market = collections.defaultdict(float)     # ticker -> net $
    market_side = {}
    for b in block:
        for r in b["recs"]:
            k = r.get("kind")
            if k == "signal":
                s["signals"] += 1
                s["prices"].append(float(r.get("price") or 0))
                s["edges"].append(float(r.get("edge_c") or 0))
                s["takes"].append(float(r.get("take_n") or 0))
            elif k == "order":
                s["orders"] += 1
                want = float(r.get("filled") or 0)
                # THE REQUESTED COUNT IS body.count. filled+remaining is 0.0
                # on a zero-fill IOC -- the exchange cancels the remainder
                # rather than reporting it -- so deriving `asked` from those
                # two made the fill ratio read 100% while 11 of 47 orders got
                # nothing at all.
                try:
                    askn = float((r.get("body") or {}).get("count"))
                except (TypeError, ValueError):
                    askn = want + float(r.get("remaining") or 0)
                s["asked"] += askn
                s["filled"] += want
                if int(r.get("status_code") or 0) not in (200, 201):
                    s["order_fail"] += 1
                elif want <= 0:
                    s["zero_fill"] += 1
                elif float(r.get("remaining") or 0) > 1e-9:
                    s["partial"] += 1
                else:
                    s["full"] += 1
            elif k == "scrap":
                s["scrap"] += 1
                s["scrap_contracts"] += float(r.get("filled") or 0)
            elif k == "dumped":
                s["dumped"] += 1
            elif k == "hedge_alarm":
                s["hedge_alarm"] += 1
            elif k == "hedge":
                s["hedge_fill"] += 1
                s["hedge_contracts"] += float(r.get("filled")
                                              or r.get("n") or 0)
                s["hedge_cost"] += float(r.get("cost") or 0)
            elif k == "hedge_no_ask":
                s["hedge_no_ask"] += 1
            elif k == "hedge_gave_up":
                s["hedge_gave_up"] += 1
            elif k == "watch":
                for t in (r.get("added") or []):
                    s["closes_watched"].add(close_of(t))
                    s["markets_watched"].add(market_of(t))
            elif k == "close_summary":
                if r.get("fired"):
                    s["closes_fired"] += 1
                for f in ("looks", "decided", "undecided", "no_offer", "dust",
                          "tradeable", "over_ceiling", "neg_ev"):
                    s[f] += int(r.get(f) or 0)
            elif k == "settled":
                s["settled_n"] += 1
                # A HEDGE LEG SETTLES UNDER THE SAME TICKER. Summing per
                # ticker is what nets the pair; counting records would treat
                # a hedged market as two bets.
                per_market[market_of(r["ticker"])] += float(
                    r.get("pnl_c") or 0) / 100.0
                market_side.setdefault(r["ticker"], r.get("want"))
    s["closes_watched"] = len(s["closes_watched"])
    s["markets_watched"] = len(s["markets_watched"])

    per_close = collections.defaultdict(float)
    for t, v in per_market.items():
        per_close[close_of(t)] += v
    s["per_market"] = dict(per_market)
    s["per_close"] = dict(per_close)
    s["markets"] = len(per_market)
    s["mkt_win"] = sum(1 for v in per_market.values() if v > 0)
    s["mkt_loss"] = sum(1 for v in per_market.values() if v < 0)
    s["closes"] = len(per_close)
    s["cl_win"] = sum(1 for v in per_close.values() if v > 0)
    s["cl_loss"] = sum(1 for v in per_close.values() if v < 0)
    s["won_dollars"] = sum(v for v in per_market.values() if v > 0)
    s["lost_dollars"] = sum(v for v in per_market.values() if v < 0)
    s["net"] = sum(per_market.values())
    return s


# ---------------------------------------------------------------------------
def selftest():
    n = [0]
    fails = []

    def ck(c, m):
        n[0] += 1
        if not c:
            fails.append(m)

    ck(market_of("KXNEAR15M-26SEP122015-15") == "KXNEAR15M-26SEP122015",
       "market_of must strip the strike, not the date")
    ck(market_of("KXBTC15M-26SEP122015-5") == market_of(
        "KXBTC15M-26SEP122015-15"),
       "two STRIKES of one series/window are one market")
    ck(market_of("KXBTC15M-26SEP122015-15") != market_of(
        "KXETH15M-26SEP122015-15"),
       "but two SERIES are two different markets")
    # RULE 4. The close is a TIME, shared by every series settling on it.
    ck(close_of("KXBTC15M-26SEP122015-15") == close_of(
        "KXETH15M-26SEP122015-15") == "26SEP122015",
       f"BTC and ETH settling at 20:15 are ONE close, got "
       f"{close_of('KXBTC15M-26SEP122015-15')} and "
       f"{close_of('KXETH15M-26SEP122015-15')}")
    ck(close_of("KXBTC15M-26SEP122015-15") != close_of(
        "KXBTC15M-26SEP122030-15"),
       "but 20:15 and 20:30 are two closes")

    # THE NEAR BUG, planted. Three fills on ONE market in ONE close must be
    # one market and one close, never three losses.
    blk = [{"name": "x", "recs": [
        {"kind": "settled", "ticker": "KXNEAR15M-26SEP090300-15",
         "want": "yes", "pnl_c": -500},
        {"kind": "settled", "ticker": "KXNEAR15M-26SEP090300-15",
         "want": "yes", "pnl_c": -500},
        {"kind": "settled", "ticker": "KXNEAR15M-26SEP090300-15",
         "want": "yes", "pnl_c": -500}]}]
    g = summarise(blk)
    ck(g["settled_n"] == 3 and g["markets"] == 1 and g["closes"] == 1,
       f"3 fills on one market is 1 market and 1 close, got "
       f"{g['markets']} markets / {g['closes']} closes")
    ck(abs(g["net"] + 15.0) < 1e-9,
       f"and the money still sums to -$15.00, got {g['net']}")
    ck(g["cl_loss"] == 1, f"one losing close, got {g['cl_loss']}")

    # A HEDGE NETS AGAINST ITS OWN BET, under the same ticker.
    blk2 = [{"name": "x", "recs": [
        {"kind": "settled", "ticker": "KXZEC15M-26SEP122000-00",
         "want": "yes", "pnl_c": -1061},
        {"kind": "settled", "ticker": "KXZEC15M-26SEP122000-00",
         "want": "no", "pnl_c": 198}]}]
    g2 = summarise(blk2)
    ck(g2["markets"] == 1 and abs(g2["net"] + 8.63) < 1e-9,
       f"a hedged loss is ONE market netting -$8.63, got {g2['markets']} "
       f"markets at {g2['net']}")
    ck(g2["mkt_loss"] == 1 and g2["mkt_win"] == 0,
       "and it counts as a loss, because the pair lost money")

    # TWO SERIES, ONE CLOSE TIME -> 2 markets, 2 closes by ticker prefix.
    blk3 = [{"name": "x", "recs": [
        {"kind": "settled", "ticker": "KXBTC15M-26SEP122015-15",
         "want": "yes", "pnl_c": 100},
        {"kind": "settled", "ticker": "KXETH15M-26SEP122015-15",
         "want": "yes", "pnl_c": -100}]}]
    g3 = summarise(blk3)
    ck(g3["markets"] == 2, f"two series are two markets, got {g3['markets']}")
    ck(g3["closes"] == 1,
       f"...but ONE close, because they settle on the same second at rho~0.8 "
       f"-- counting 2 here is the rule-4 error, got {g3['closes']}")
    ck(g3["cl_win"] == 0 and g3["cl_loss"] == 0,
       "and a +$1/-$1 pair nets to exactly zero on that close, so it is "
       "neither a win nor a loss")

    # Clopper-Pearson against the closed forms.
    lo, hi = cp_interval(0, 10)
    ck(abs(lo) < 1e-9 and abs(hi - (1 - 0.025 ** (1 / 10))) < 1e-6,
       f"0 of 10 must be [0, 1-0.025^(1/10)={1 - 0.025 ** (1 / 10):.4f}], "
       f"got [{lo:.4f}, {hi:.4f}]")
    lo2, hi2 = cp_interval(10, 10)
    ck(abs(hi2 - 1.0) < 1e-9, "10 of 10 must bound at 1.0")
    lo3, hi3 = cp_interval(1, 100)
    ck(lo3 < 0.01 < hi3, f"the point estimate must sit inside its own "
                         f"interval, got [{lo3:.4f}, {hi3:.4f}]")
    ck(cp_interval(2, 20)[1] > cp_interval(2, 200)[1],
       "the same rate on more data must give a TIGHTER upper bound")

    # A version boundary ignores code_sha and minutes, and sees a rule change.
    a = {"pin": 0.995, "hedge_belief": 0.9, "code_sha": "aaa", "minutes": 10}
    b = {"pin": 0.995, "hedge_belief": 0.9, "code_sha": "bbb", "minutes": 99}
    c = {"pin": 0.995, "hedge_belief": 0.8, "code_sha": "bbb", "minutes": 99}
    ck(decision_key(a) == decision_key(b),
       "a bugfix (code_sha) or a longer session is the SAME version")
    ck(decision_key(b) != decision_key(c),
       "but a hedge-threshold move is a NEW version")
    rs = [{"key": decision_key(a), "name": "a"},
          {"key": decision_key(c), "name": "c"},
          {"key": decision_key(c), "name": "c2"}]
    ck([r["name"] for r in current_version(rs)] == ["c", "c2"],
       "current_version takes the trailing block that shares a key")

    print(f"  pinver selftest: {n[0]} checks, {len(fails)} failures")
    for f in fails:
        print(f"    FAIL {f}")
    return not fails


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if not selftest():
        sys.exit(1)

    rs = runs(a.results)
    block = current_version(rs)
    if not block:
        print("  loaded nothing")
        return
    st = block[0]["start"]
    prev = None
    for i, r in enumerate(rs):
        if r is block[0] and i:
            prev = rs[i - 1]["start"]
    print("\n" + "=" * 74)
    print("  CURRENT VERSION -- %d run file(s), first %s"
          % (len(block), block[0]["name"]))
    if prev:
        ch = {k: (prev.get(k), st.get(k)) for k in DECISION_KEYS
              if prev.get(k) != st.get(k)}
        print("  what made it a new version: %s" % (ch or "(first logged)"))
    print("=" * 74)
    for k in DECISION_KEYS:
        if st.get(k) is not None:
            print("    %-24s %s" % (k, st[k]))

    s = summarise(block)
    print("\n  OPPORTUNITY")
    print("    closes watched              %d" % s["closes_watched"])
    print("    closes we fired on          %d  (%.1f%%)"
          % (s["closes_fired"],
             100.0 * s["closes_fired"] / max(1, s["closes_watched"])))
    print("    book looks                  %d" % s["looks"])
    print("      already decided           %d" % s["decided"])
    print("      no offer resting          %d" % s["no_offer"])
    print("      dust (under MIN_LEVEL)    %d" % s["dust"])
    print("      TRADEABLE                 %d" % s["tradeable"])
    print("      refused: over ceiling     %d" % s["over_ceiling"])
    print("      refused: negative EV      %d" % s["neg_ev"])
    print("      refused: dump guard       %d" % s["dumped"])

    print("\n  EXECUTION")
    print("    signals                     %d" % s["signals"])
    print("    orders sent                 %d" % s["orders"])
    print("      filled in full            %d" % s["full"])
    print("      partial                   %d" % s["partial"])
    print("      zero fill                 %d" % s["zero_fill"])
    print("      HTTP failure              %d" % s["order_fail"])
    print("    contracts asked             %.2f" % s["asked"])
    print("    contracts filled            %.2f" % s["filled"])
    print("    FILL RATIO                  %.1f%%"
          % (100.0 * s["filled"] / max(1e-9, s["asked"])))
    if s["prices"]:
        print("    mean price paid             %.2fc"
              % (100 * sum(s["prices"]) / len(s["prices"])))
        print("    mean edge at signal         %+.2fc"
              % (sum(s["edges"]) / len(s["edges"])))
        print("    mean size wanted            %.1f contracts"
              % (sum(s["takes"]) / len(s["takes"])))
    print("    scrapped (under min fill)   %d orders, %.2f contracts"
          % (s["scrap"], s["scrap_contracts"]))

    print("\n  HEDGE")
    print("    alarms fired                %d" % s["hedge_alarm"])
    print("    hedge legs filled           %d  (%.2f contracts)"
          % (s["hedge_fill"], s["hedge_contracts"]))
    print("    no ask in time              %d" % s["hedge_no_ask"])
    print("    gave up after retries       %d" % s["hedge_gave_up"])

    print("\n  RESULT  (hedge legs netted into the market they protect)")
    print("    settled records             %d" % s["settled_n"])
    print("    MARKETS                     %d   %dW %dL"
          % (s["markets"], s["mkt_win"], s["mkt_loss"]))
    print("    CLOSES (rule 4 unit)        %d   %dW %dL"
          % (s["closes"], s["cl_win"], s["cl_loss"]))
    print("    won                         $%+.2f" % s["won_dollars"])
    print("    lost                        $%+.2f" % s["lost_dollars"])
    print("    NET                         $%+.2f" % s["net"])
    if s["markets"]:
        lo, hi = cp_interval(s["mkt_loss"], s["markets"])
        print("    loss rate, MARKETS          %.2f%%  95%% CP [%.2f, %.2f]"
              % (100.0 * s["mkt_loss"] / s["markets"], 100 * lo, 100 * hi))
    if s["closes"]:
        lo, hi = cp_interval(s["cl_loss"], s["closes"])
        print("    loss rate, CLOSES           %.2f%%  95%% CP [%.2f, %.2f]"
              % (100.0 * s["cl_loss"] / s["closes"], 100 * lo, 100 * hi))
    if s["per_close"]:
        worst = min(s["per_close"].items(), key=lambda kv: kv[1])
        best = max(s["per_close"].items(), key=lambda kv: kv[1])
        print("    worst close                 %s  $%+.2f" % worst)
        print("    best close                  %s  $%+.2f" % best)
    for t, v in sorted(s["per_market"].items(), key=lambda kv: kv[1]):
        if v < 0:
            print("      LOSS  %-30s $%+.2f" % (t, v))


if __name__ == "__main__":
    main()
