"""test_hedgeplay.py -- botdata/hedgeplay.py (v-hedge-split, 2026-11-01) and the RULE that every phone surface counts a
market whose bet WON but whose hedge cost a little more as a hedge cost, never as a loss.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_hedgeplay.py   (exit 0 = every test passed)
The fixtures are the five 10-31 markets the phone called five losses, as Kalshi booked them (settlement rows copied
from the server's kalshi_ledger.json) with the pin bot's executed hedge records from its log:
  HYPE 7:30 AM   bet YES 20.98 at 98c +$0.39   jump hedge NO 20.98 at 7.1c -$1.59                 net -$1.20
  HYPE 1:15 PM   bet NO 14.32 at 94c +$0.80    jump hedge YES 14.32 at 6c -$0.92                  net -$0.11
  ETH 1:30 PM    bet YES 28 at 98.9c +$0.29    jump hedge NO 28 at 1c -$0.30                      net -$0.01
  NEAR 4:45 PM   bet YES 97.24 at 95.4c -$93.11  odds hedge NO 97.24 at 45c +$51.80, after the flip NO 97.24 at 80c
                 +$18.36                                                                            net -$22.96
  BTC hourly 11 PM  bet YES 35 at 92c +$2.62   jump hedge NO 35 at 10c -$3.72                     net -$1.10
So: 1 lost (NEAR), 4 hedge costs. What it proves:
  - the split's parts match the bot's own leg money to the cent and add up to Kalshi's net EXACTLY;
  - no record -> no split (never a guess); a tie, a one-sided market, a hedge on the bet's own side -> no split;
  - the tally and the words the phone shows;
  - EVERY counting surface (botdata windows, the all-bots totals, the losses list, the week/month spans, phone.shared's
    window_stats, the desk Ledger's close counts, the loss alert, /funds' day cells) counts 1 lost and 4 hedge costs;
  - another bot's markets (the jump band trades the same tickers from subaccount 3) are never split;
  - a source scan: no new net-based loss count appears outside hedgeplay (the class, not the example).
"""
import os
import re
import sys
import time
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import pinledger                                    # noqa: E402
from botdata import hedgeplay as H                  # noqa: E402
from botdata import money as M                      # noqa: E402

ROWS = [
    {"event_ticker": "KXHYPE15M-26OCT310730", "fee_cost": "0.125720", "market_result": "yes", "no_count_fp": "20.98",
     "no_total_cost_dollars": "1.489580", "revenue": 0, "settled_time": "2026-10-31T11:30:03.5747Z",
     "ticker": "KXHYPE15M-26OCT310730-30", "value": 100, "yes_count_fp": "20.98", "yes_total_cost_dollars": "20.560400"},
    {"event_ticker": "KXHYPE15M-26OCT311315", "fee_cost": "0.113200", "market_result": "no", "no_count_fp": "14.32",
     "no_total_cost_dollars": "13.460800", "revenue": 0, "settled_time": "2026-10-31T17:15:03.607397Z",
     "ticker": "KXHYPE15M-26OCT311315-15", "value": 0, "yes_count_fp": "14.32", "yes_total_cost_dollars": "0.859200"},
    {"event_ticker": "KXETH15M-26OCT311330", "fee_cost": "0.040900", "market_result": "yes", "no_count_fp": "28.00",
     "no_total_cost_dollars": "0.280000", "revenue": 0, "settled_time": "2026-10-31T17:30:03.600617Z",
     "ticker": "KXETH15M-26OCT311330-30", "value": 100, "yes_count_fp": "28.00", "yes_total_cost_dollars": "27.692000"},
    {"event_ticker": "KXNEAR15M-26OCT311645", "fee_cost": "3.069300", "market_result": "no", "no_count_fp": "194.48",
     "no_total_cost_dollars": "121.550000", "revenue": 9724, "settled_time": "2026-10-31T20:45:03.554304Z",
     "ticker": "KXNEAR15M-26OCT311645-45", "value": 0, "yes_count_fp": "97.24", "yes_total_cost_dollars": "92.816400"},
    {"event_ticker": "KXBTCD-26OCT3123", "fee_cost": "0.400900", "market_result": "yes", "no_count_fp": "35.00",
     "no_total_cost_dollars": "3.500000", "revenue": 0, "settled_time": "2026-11-01T03:12:18.977195Z",
     "ticker": "KXBTCD-26OCT3123-T77599.99", "value": 100, "yes_count_fp": "35.00", "yes_total_cost_dollars": "32.200000"},
]
# the bot's records as the desk Ledger keeps them (kind, tk, side, n, price, status; trigger on the alarm). The HYPE
# 7:30 hedge's first try (1.5c) sent nothing (status None) and must not count.
RECORDS = [
    {"kind": "hedge_alarm", "tk": "KXHYPE15M-26OCT310730-30", "trigger": "jump"},
    {"kind": "hedge", "tk": "KXHYPE15M-26OCT310730-30", "side": "no", "n": 20.98, "price": 0.015, "status": None},
    {"kind": "hedge", "tk": "KXHYPE15M-26OCT310730-30", "side": "no", "n": 20.98, "price": 0.071, "status": "executed"},
    {"kind": "hedge_alarm", "tk": "KXHYPE15M-26OCT311315-15", "trigger": "jump"},
    {"kind": "hedge", "tk": "KXHYPE15M-26OCT311315-15", "side": "yes", "n": 14.32, "price": 0.06, "status": "executed"},
    {"kind": "hedge_alarm", "tk": "KXETH15M-26OCT311330-30", "trigger": "jump"},
    {"kind": "hedge", "tk": "KXETH15M-26OCT311330-30", "side": "no", "n": 28.0, "price": 0.01, "status": "executed"},
    {"kind": "hedge_alarm", "tk": "KXNEAR15M-26OCT311645-45", "trigger": "belief"},
    {"kind": "hedge", "tk": "KXNEAR15M-26OCT311645-45", "side": "no", "n": 97.24, "price": 0.45, "status": "executed"},
    {"kind": "hedge_alarm", "tk": "KXBTCD-26OCT3123-T77599.99", "trigger": "jump"},
    {"kind": "hedge", "tk": "KXBTCD-26OCT3123-T77599.99", "side": "no", "n": 35.0, "price": 0.10, "status": "executed"},
]
# (bet $, hedge $, after-the-flip $ or None, net $, kind) -- the bot's own leg money (pnl_c of its settled records)
WANT = {"KXHYPE15M-26OCT310730-30": (0.39, -1.59, None, -1.20, "hedge_cost"),
        "KXHYPE15M-26OCT311315-15": (0.80, -0.92, None, -0.11, "hedge_cost"),
        "KXETH15M-26OCT311330-30": (0.29, -0.30, None, -0.01, "hedge_cost"),
        "KXNEAR15M-26OCT311645-45": (-93.11, 51.80, 18.36, -22.96, "lost_hedged"),
        "KXBTCD-26OCT3123-T77599.99": (2.62, -3.72, None, -1.10, "hedge_cost")}
# a plain winner and a plain (unhedged) loser on the same day, so counts are not trivially 'every market'
PLAIN = [
    {"fee_cost": "0.02", "market_result": "yes", "no_count_fp": "0", "no_total_cost_dollars": "0", "value": 100,
     "settled_time": "2026-10-31T15:00:03Z", "ticker": "KXSOL15M-26OCT311100-00", "yes_count_fp": "50",
     "yes_total_cost_dollars": "49.00"},
    {"fee_cost": "0.02", "market_result": "no", "no_count_fp": "0", "no_total_cost_dollars": "0", "value": 0,
     "settled_time": "2026-10-31T16:00:03Z", "ticker": "KXXRP15M-26OCT311200-00", "yes_count_fp": "10",
     "yes_total_cost_dollars": "9.80"},
]


def _near(a, b, tol=0.0101):
    assert abs(a - b) <= tol, (a, b)


def _ix():
    return H.index(RECORDS)


def test_five_markets_split_to_the_cent():
    ix = _ix()
    assert set(ix) == set(WANT)
    assert ix["KXHYPE15M-26OCT310730-30"]["fires"] == 1 and abs(ix["KXHYPE15M-26OCT310730-30"]["price"] - 0.071) < 1e-9
    for s in ROWS:
        p = H.split_row(s, ix[s["ticker"]])
        b, h, f, net, kind = WANT[s["ticker"]]
        assert p["kind"] == kind, (s["ticker"], p["kind"])
        _near(p["bet"]["money"], b)
        _near(p["hedge"]["money"], h)
        if f is None:
            assert p["flip"] is None
        else:
            _near(p["flip"]["money"], f)
        _near(p["net"], net)
        parts = p["bet"]["money"] + p["hedge"]["money"] + (p["flip"]["money"] if p["flip"] else 0.0)
        assert abs(parts - pinledger.pnl(s)) < 1e-9, "the parts must add up to Kalshi's net exactly"
        assert p["hedge"]["trigger"] == ("belief" if "NEAR" in s["ticker"] else "jump")
    near = H.split_row(ROWS[3], ix[ROWS[3]["ticker"]])
    assert near["bet"]["side"] == "yes" and abs(near["bet"]["n"] - 97.24) < 1e-9
    assert near["flip"]["side"] == "no" and abs(near["flip"]["price"] - 0.80) < 1e-6


def test_never_a_guess():
    ix = _ix()
    assert H.split_row(ROWS[0], None) is None                           # no record
    assert H.split_row(PLAIN[0], {"side": "no", "n": 5.0, "price": 0.1, "cost": 0.5}) is None   # nothing on that side
    tie = dict(ROWS[0], value=50, market_result="scalar")
    assert H.split_row(tie, ix[ROWS[0]["ticker"]]) is None              # a tie is never split
    wrong = dict(ix[ROWS[0]["ticker"]], side="yes")                     # the 'hedge' on the bet's own side: other side
    p = H.split_row(ROWS[0], wrong)
    assert p is None or p["bet"]["side"] == "no"
    m = M.market(PLAIN[1])
    assert H.is_loss(m) and not H.is_hedge_cost(m) and m.get("kind") is None    # unhedged loss: today's rule
    H.set_source(None)
    assert H.current() == {}
    H.set_source(lambda: RECORDS)
    assert set(H.current()) == set(WANT)
    H.set_source(lambda: (_ for _ in ()).throw(RuntimeError("broken source")))
    assert H.current() == {}                                            # a broken source splits nothing
    H.set_source(None)


def _tagged_markets():
    ix = _ix()
    out = []
    for s in ROWS + PLAIN:
        m = M.market(s)
        if ix.get(s["ticker"]):
            H.tag(m, H.split_row(s, ix[s["ticker"]]))
        out.append(m)
    return out


def test_tally_and_words():
    t = H.tally(_tagged_markets())
    assert (t["fired"], t["needed"], t["not_needed"], t["hedge_cost_markets"]) == (5, 1, 4, 4)
    _near(t["got_back"], 51.80)
    _near(t["bet_lost"], -93.11)
    _near(t["cost"], -6.53, 0.02)
    assert set(t["by_trigger"]) == {"belief", "jump"}
    assert t["by_trigger"]["jump"]["fired"] == 4 and t["by_trigger"]["jump"]["needed"] == 0
    line = H.hedge_line(t)
    assert line.startswith("🛡️ Hedges: 5 fired · 1 needed: got back $51.80 of a $93.11 loss · 4 not needed: cost $6.5"), line
    assert H.hedge_line(None) is None and H.tally([M.market(PLAIN[0])]) is None
    assert H.lost_words(1, 4) == "1 lost, 4 hedge costs" and H.lost_words(5, 0) == "5 lost"
    assert H.lost_cell(1, 4, 114) == "1+4h/114" and H.lost_cell(5, 0, 114) == "5/114"
    near = [m for m in _tagged_markets() if "NEAR" in m["ticker"]][0]
    L = H.play_lines(near["play"])
    assert L[0] == "bet YES 97.24 at 95.5c → lost -$93.11", L[0]
    assert L[1] == "hedge NO 97.24 at 45.0c (odds hedge) → won +$51.80", L[1]
    assert L[2] == "after the flip NO 97.24 at 80.0c → won +$18.36", L[2]
    assert "the hedge cut the loss from -$93.11 to -$41.31; the buy after the flip made it -$22.96" in L[3], L[3]
    hy = [m for m in _tagged_markets() if m["ticker"] == "KXHYPE15M-26OCT310730-30"][0]
    assert "the bet won; the hedge was not needed and cost $1.59" in H.play_lines(hy["play"])[-1]


# ---- THE RULE: every counting surface -------------------------------------------------------------------------------
def test_botdata_window_counts():
    w = M.window(_tagged_markets(), "Today", ["2026-10-31"])
    assert (w["markets"], w["won"], w["lost"], w["hedge_costs"]) == (7, 1, 2, 4), w      # NEAR + the plain XRP loss
    assert w["hedges"]["fired"] == 5
    assert w["money"] == round(sum(m["money"] for m in _tagged_markets()), 4)            # money never changes
    plain = M.window([M.market(s) for s in ROWS + PLAIN], "Today", ["2026-10-31"])       # not split: as before
    assert plain["lost"] == 6 and "hedge_costs" not in plain and "hedges" not in plain
    ws = M.windows(_tagged_markets(), "2026-10-31")
    d0 = ws["days_7"][0]
    assert d0["lost"] == 2 and d0["hedge_costs"] == 4


def test_report_splits_the_pin_bot_only():
    from botdata import report as R
    from botdata import tables as Tb
    H.set_source(lambda: RECORDS)
    try:
        assert R._hedges_of("pin") is True
        for b in Tb.BOTS:
            if b != "pin":
                assert R._hedges_of(b) is False, b                    # the jump band's same tickers are never split
        assert R._hedges_of("other") is False
        tot = {}
        R._hedge_keys(tot, [{"hedge_costs": 4, "hedges": {"fired": 5}}, {"lost": 1}])
        assert tot == {"hedge_costs": 4, "hedges": {"fired": 5}}
        none = {}
        R._hedge_keys(none, [{"lost": 1}])
        assert none == {}
    finally:
        H.set_source(None)


def test_period_span_counts():
    from botdata import period as P

    class BS:
        SPEC = {}
    ms = [("pin", m) for m in _tagged_markets()]
    orig = P.span_pot
    P.span_pot = lambda *a, **k: None
    try:
        sp = P.span(ms, {}, "2026-10-31", "2026-10-31", BS())
    finally:
        P.span_pot = orig
    assert sp["lost"] == 2 and sp["hedge_costs"] == 4 and sp["hedges"]["fired"] == 5, sp
    assert sp["by_bot"]["pin"]["lost"] == 2 and sp["by_bot"]["pin"]["hedge_costs"] == 4


def test_shared_window_stats_counts():
    from phone import shared as S
    H.set_source(lambda: RECORDS)
    try:
        sides = {s["ticker"]: ("no" if r["side"] == "yes" else "yes") for s in ROWS for r in RECORDS
                 if r.get("tk") == s["ticker"] and r["kind"] == "hedge"}
        ms = S.markets_from_rows(ROWS + PLAIN, sides)
        st = S.window_stats(list(ms.values()), {})
        assert (st["losses"], st["hedge_costs"]) == (2, 4), (st["losses"], st["hedge_costs"])
        assert st["hedges"]["fired"] == 5
        assert abs(st["net"] - sum(pinledger.pnl(s) for s in ROWS + PLAIN)) < 1e-9
        txt = S.stats_block("10-31", st)
        assert "Losses 2 (+4 hedge costs $-2.42):" in txt, txt
    finally:
        H.set_source(None)
    ms = S.markets_from_rows(ROWS + PLAIN, {})
    assert S.window_stats(list(ms.values()), {})["losses"] == 6          # no records: exactly as before


def _ledger_rows(close_of=None):
    """The desk Ledger's settled rows (its _load_kalshi shape) for the fixtures, split as it splits them."""
    ix = _ix()
    out = []
    for k, s in enumerate(ROWS + PLAIN):
        r = {"t": 1793440000 + 900 * k, "tk": s["ticker"], "pnl": pinledger.pnl(s), "cost": 0.9, "want": "yes",
             "result": s["market_result"], "close": (close_of or {}).get(s["ticker"], 1793440000 + 900 * k),
             "file": "kalshi", "n": 1.0, "hedged": True}
        if ix.get(s["ticker"]):
            H.tag(r, H.split_row(s, ix[s["ticker"]]))
        out.append(r)
    return out


def test_desk_ledger_close_counts():
    import pindesk
    s = pindesk.Ledger.summary(_ledger_rows())
    assert (s["closes"], s["won"], s["lost"], s["hedge_costs"]) == (7, 1, 2, 4), s
    assert s["hedges"]["fired"] == 5
    # one close holding a hedge cost AND a real loss is a lost close; a hedge cost with a winner is won or a hedge cost
    both = _ledger_rows({"KXHYPE15M-26OCT310730-30": 1, "KXNEAR15M-26OCT311645-45": 1})
    k = pindesk.Ledger.close_kinds(both)
    assert k[1] == "lost"


def test_alert_words():
    from phone import alerts as A
    from phone import shared as S

    class Led:
        def bank_at(self, t):
            return 2500.0

        def contracts_for(self, tk):
            return None
    rows = {r["tk"]: r for r in _ledger_rows()}
    hy = [rows["KXHYPE15M-26OCT310730-30"]]
    nr = [rows["KXNEAR15M-26OCT311645-45"]]
    assert A.is_hedge_cost_close(hy) and not A.is_hedge_cost_close(nr)
    assert not A.is_hedge_cost_close([rows["KXXRP15M-26OCT311200-00"]])
    t1 = str(A.alert_loss_text(Led(), 1793446200, -1.20, hy, S))
    assert t1.startswith("🛡️ <b>HEDGE COST -$1.20") and "LOSS" not in t1 and "bet YES 20.98 at 98.0c" in t1, t1
    t2 = str(A.alert_loss_text(Led(), 1793475900, -22.96, nr, S))
    assert t2.startswith("🔴 <b>LOSS -$22.96") and "bet YES 97.24 at 95.5c → lost -$93.11" in t2, t2
    assert "hedge NO 97.24 at 45.0c (odds hedge) → won +$51.80" in t2 and "after the flip NO 97.24" in t2
    assert "62.5c" not in t2                         # the 10-31 bug: the market as one 'NO at 62.5c' leg


def test_funds_day_cells():
    from phone.commands.funds import read as FR
    H.set_source(lambda: RECORDS)
    try:
        res = {"rows": ROWS + PLAIN, "err": None, "oldest": 0}
        main = FR.funds_days_of(res, "2026-10-31", days=2, sub=0)
        c = [x for x in main["days"] if x["day"] == "2026-10-31"][0]["all"]
        assert (c["n"], c["lost"], c["hc"]) == (7, 2, 4), c    # BTC hourly 11 PM: a 10-31 ticker (settled 11-01)
        sub3 = FR.funds_days_of(res, "2026-10-31", days=2, sub=3)
        c3 = [x for x in sub3["days"] if x["day"] == "2026-10-31"][0]["all"]
        assert c3.get("hc", 0) == 0 and c3["lost"] == 6, c3           # another pot: never split (5 + the plain XRP loss)
    finally:
        H.set_source(None)


# ---- the class, not the example: no net-based loss COUNT outside hedgeplay ------------------------------------------
# A line that decides 'lost' from a bare net (< 0 / < -0.004) is allowed only for WORDS or a COLOUR (made/lost, a dot)
# or a non-pin record (the coin race's legs); every COUNT of lost markets goes through hedgeplay.is_loss.
ALLOWED = {
    ("phone/charts/base.py", 'return ("lost " if v < -0.004 else "made ") + usd(v, signed)'),
    ("phone/render/botcards.py", 'made = ("lost " if w["money"] < -0.004 else "made ") + usd(w["money"])'),
    ("phone/shared.py", 'r["lost"] = (not r["tie"]) and r["pnl"] < 0'),
    # the main-ledger day picture: a losing CLOSE, already split by Ledger.close_kinds (hedgeplay's rule)
    ("phone/charts/day.py", 'lost = [(k, c) for k, c, v in pts if v < 0 and kinds.get(k) != "hedge_cost"]'),
}
PAT = re.compile(r"lost.*(<\s*-0\.00\d|<\s*0\b(?!\.))|(<\s*-0\.00\d|<\s*0\b(?!\.)).*lost", re.I)


def test_no_loss_count_bypasses_hedgeplay():
    bad = []
    for top in ("phone", "botdata"):
        for root, _d, files in os.walk(os.path.join(RESEARCH, top)):
            if os.sep + "tests" in root or "__pycache__" in root:
                continue
            for f in files:
                if not f.endswith(".py") or f == "hedgeplay.py":
                    continue
                p = os.path.join(root, f)
                rel = os.path.relpath(p, RESEARCH).replace(os.sep, "/")
                for i, line in enumerate(open(p, encoding="utf-8"), 1):
                    if PAT.search(line) and (rel, line.strip()) not in ALLOWED:
                        bad.append("%s:%d %s" % (rel, i, line.strip()))
    assert not bad, "a loss counted from the bare net (use botdata.hedgeplay.is_loss):\n" + "\n".join(bad)


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed, failed = 0, []
    t0 = time.time()
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print("  ok   %s" % name, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(name)
            print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    print("test_hedgeplay: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
