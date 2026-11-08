"""test_fixes.py -- botdata/fixes.py (v-fixes, 2026-11-04): every live pin change A..L scored on synthetic pin logs.

Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_fixes.py   (exit 0 = every test passed; botstats.py
--selftest runs it too). Synthetic runs: the 0925r build (code_sha ca156bf45704; rules A, B, C), a later build with
another sha (D..J), the 0925u cheap-window run (K) and the 0925v jump-hedge-shadow run (L). Every $ below is worked by
hand from the scoring table (Kalshi's taker fee ceil(7 * p * (1 - p) * n) / 100 inside); the phone test
(phone/tests/test_fixes_cmd.py) renders the same logs.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import _kit                                                          # noqa: E402  (sys.path, KALS_TESTING=1)
from _kit import ck                                                  # noqa: E402

from botdata import fixes as F                                       # noqa: E402
from botdata import paths                                            # noqa: E402

NOW = 1793862000.0                 # 2026-11-05T07:00:00Z = 2:00 AM ET (every 11-05 market closed under 3 h ago)
NEW_SHA = "0f0f0f0f0f0f"


def _r(kind, t, **kw):
    kw.update(kind=kind, t=t)
    return kw


def run_r(recs):
    """The 0925r run (11-02 08:35 ET on): rules A, B, C."""
    recs += [
        _r("start", "2026-11-02T13:35:22Z", code_sha="ca156bf45704", ws_later_fall_c=10.0, hedge_jump_max=8.0,
           hedge_odds_mult=1.25, max_positions=3),
        # A: a later buy refused; the bet LOST, so the skipped 41 No at 86c would have lost 35.26 + fee 0.35 = 35.61
        _r("refused", "2026-11-02T14:00:00Z", gate="ws_later_fall", ticker="KXHYPE15M-26NOV020915-15", close_s=1793628900,
           want="no", leg="topup", tau=7, price=0.86, size=41.0, would_n=41.0, limit=0.98, ladder=[[0.86, 100.0]],
           fall_c=24.0),
        _r("settled", "2026-11-02T14:15:20Z", ticker="KXHYPE15M-26NOV020915-15", want="no", result="yes", cost=0.93,
           pnl_c=-1000.0),
        # B: a 9 sd jump hedge of 50 Yes at 10c skipped; the bet won: saved 5.00 + fee 0.32 = 5.32
        _r("jump_capped", "2026-11-02T14:29:35Z", ticker="KXNEAR15M-26NOV020930-30", close_s=1793629800, want="no",
           side="yes", n=50.0, jump_sd=9.0, belief=0.85, tau=25, ask=0.10, ask_size=80.0, ladder=[[0.10, 80.0]], limit=0.20),
        _r("settled", "2026-11-02T14:30:20Z", ticker="KXNEAR15M-26NOV020930-30", want="no", result="no", cost=0.97,
           pnl_c=100.0),
        # C: 100 extra Yes at 14c on a flip: 86.00 - fee 0.85 = 85.15
        _r("hedge_extra", "2026-11-02T15:14:42Z", ticker="KXZEC15M-26NOV021015-15", side="yes", price=0.14, n=100.0,
           asked=100.0, extra_of=100.0, mult=2.0, base_n=100.0, tau=18, belief=0.342, trigger="belief", order_id="x-1",
           status="executed", live=True),
        _r("settled", "2026-11-02T15:15:20Z", ticker="KXZEC15M-26NOV021015-15", want="no", result="yes", cost=0.9446,
           pnl_c=-28163.0),
        # C, open: an extra leg whose market never settled in the log (3 h past its close: "unknown", still open)
        _r("hedge_extra", "2026-11-02T16:44:50Z", ticker="KXSOL15M-26NOV021145-45", side="no", price=0.30, n=20.0,
           asked=20.0, extra_of=20.0, mult=1.25, base_n=80.0, tau=12, belief=0.30, trigger="belief", order_id="x-2",
           status="executed", live=True),
        # a hedge_extra that did NOT fill is not an engagement
        _r("hedge_extra", "2026-11-02T16:59:50Z", ticker="KXDOGE15M-26NOV021200-00", side="no", price=0.30, n=0.0,
           asked=20.0, extra_of=20.0, mult=1.25, base_n=80.0, tau=12, belief=0.30, trigger="belief", order_id=None,
           status=None, live=True),
        # a 0925r band boost and a losing hedge leg: nothing for D (not live yet)
        _r("band_boost", "2026-11-02T17:14:40Z", ticker="KXETH15M-26NOV021215-15", want="yes", tau=20, price=0.98, mult=1.5,
           was=20.0, now=30.0),
        _r("settled", "2026-11-02T17:15:20Z", ticker="KXETH15M-26NOV021215-15", want="yes", result="yes", cost=0.98,
           pnl_c=60.0),
    ]
    return recs


def run_new(recs):
    """The new build's run (11-05 00:00 ET on): D..J, plus the shapes that must NOT count."""
    T = "2026-11-05T05:%02d:%02dZ"
    recs += [
        _r("start", T % (0, 0), code_sha=NEW_SHA, ws_later_fall_c=10.0, hedge_jump_max=8.0, hedge_odds_mult=1.25,
           max_positions=5, boost_rail="side", hedge_tick="round", jump_hedge_min_ask=0.05),
        # a band boost BEFORE the rail was kept: not D's
        _r("band_boost", T % (14, 40), ticker="KXBNB15M-26NOV050015-15", want="yes", tau=20, price=0.98, mult=1.5, was=20.0,
           now=30.0),
        _r("settled", T % (15, 20), ticker="KXBNB15M-26NOV050015-15", want="yes", result="yes", cost=0.98, pnl_c=60.0),
        # D: a losing No hedge leg on a market whose boosted Yes won: the band boost stays on
        _r("boost_rail_kept", T % (30, 35), which="band", ticker="KXHYPE15M-26NOV050030-30", close_s=1793858400,
           leg_side="no", boosted_side=["yes"], cost=0.07, pnl_c=-158.65, rail="side", live=True),
        # ... then two band-boosted legs: +10 Yes at 98c won (0.20 - fee 0.02 = +0.18), +10 No at 97c LOST
        # (-9.70 - fee 0.03 = -9.73): D net -9.55
        _r("band_boost", T % (44, 42), ticker="KXZEC15M-26NOV050045-45", want="yes", tau=18, price=0.98, mult=1.5, was=20.0,
           now=30.0),
        _r("settled", T % (45, 20), ticker="KXZEC15M-26NOV050045-45", want="yes", result="yes", cost=0.98, pnl_c=60.0),
        _r("band_boost", T % (59, 42), ticker="KXXRP15M-26NOV050100-00", want="no", tau=18, price=0.97, mult=1.5, was=20.0,
           now=30.0),
        _r("settled", "2026-11-05T06:00:20Z", ticker="KXXRP15M-26NOV050100-00", want="no", result="yes", cost=0.97,
           pnl_c=-1940.0),
        # a LATE boost after a BAND kept record: not that engagement's
        _r("late_boost", "2026-11-05T06:14:57Z", ticker="KXNEAR15M-26NOV050115-15", want="no", tau=3, was=20.0, now=30.0,
           mult=1.5),
        _r("settled", "2026-11-05T06:15:20Z", ticker="KXNEAR15M-26NOV050115-15", want="no", result="no", cost=0.99,
           pnl_c=27.0),
        # E: a 1.5c Yes hedge: the legacy 11.5c limit is off the grid, rounded to 11c; filled 50, the bet won, so the
        # hedge leg lost 0.80
        _r("hedge", T % (29, 50), ticker="KXDOGE15M-26NOV050030-30", side="yes", price=0.015, n=50.0, asked=50.0,
           status="executed", tick_mode="round", limit_legacy=0.115, limit_sent=0.11, tick_rounded=True,
           ladder=[[0.015, 200.0]], live=True),
        _r("settled", T % (30, 20), ticker="KXDOGE15M-26NOV050030-30", want="no", result="no", cost=0.97, pnl_c=100.0),
        _r("settled", T % (30, 35), ticker="KXDOGE15M-26NOV050030-30", want="yes", result="no", cost=0.015, pnl_c=-80.0),
        # E, rounded but the legacy limit was ON the grid (90.5c + 10c = 99.9c cap): not an engagement
        _r("hedge", T % (29, 55), ticker="KXDOGE15M-26NOV050030-30", side="no", price=0.905, n=5.0, asked=5.0,
           status="executed", tick_mode="round", limit_legacy=0.999, limit_sent=0.999, tick_rounded=False, live=True),
        # E, rounded and off-grid but never filled: engaged, no money
        _r("hedge", T % (44, 50), ticker="KXSOL15M-26NOV050045-45", side="yes", price=0.025, n=0.0, asked=50.0,
           status=None, order_id=None, tick_mode="round", limit_legacy=0.125, limit_sent=0.12, tick_rounded=True,
           live=True),
        _r("settled", T % (45, 25), ticker="KXSOL15M-26NOV050045-45", want="no", result="no", cost=0.97, pnl_c=100.0),
        # F: a cheap jump hedge skipped (40 Yes asking 3c, bar 5c) and the bet won: saved 1.20 + fee 0.09 = +1.29
        _r("hedge_quote", T % (14, 30), ticker="KXAVAX15M-26NOV050015-15", side="yes", ask=0.03, size=100.0, tau=30,
           belief=0.9),
        _r("hedge_cheap_skip", T % (14, 40), ticker="KXAVAX15M-26NOV050015-15", side="yes", ask=0.03, min_ask=0.05,
           jump_sd=7.1, belief=0.9, tau=20, want="no", n=40.0, entry=0.97, live=True),
        _r("settled", T % (15, 25), ticker="KXAVAX15M-26NOV050015-15", want="no", result="no", cost=0.97, pnl_c=100.0),
        # F: skipped at 4c, then the bet LOST and pin's odds hedge bought the same 40 at 60c: the skipped hedge would
        # have got back 38.40 - 0.11 = 38.29, the real one got 16.00 - 0.68 = 15.32: gave up 22.97
        _r("hedge_cheap_skip", T % (29, 40), ticker="KXLTC15M-26NOV050030-30", side="yes", ask=0.04, min_ask=0.05,
           jump_sd=6.5, belief=0.8, tau=20, want="no", n=40.0, entry=0.97, live=True),
        _r("hedge", T % (29, 50), ticker="KXLTC15M-26NOV050030-30", side="yes", price=0.60, n=40.0, asked=40.0,
           ladder_n=40.0, limit_sent=0.70, status="executed", live=True),
        _r("settled", T % (30, 20), ticker="KXLTC15M-26NOV050030-30", want="no", result="yes", cost=0.97, pnl_c=-3900.0),
        _r("settled", T % (30, 35), ticker="KXLTC15M-26NOV050030-30", want="yes", result="yes", cost=0.60, pnl_c=1500.0),
        # G: the late 1.5x refused on a 96c Yes leg (30 -> 20); the leg won, so 10 x 4c - fee 0.03 = 0.37 given up
        _r("late_bypass_refused", T % (44, 52), ticker="KXADA15M-26NOV050045-45", close_s=1793859300, side="yes",
           path="fullcap", tau=8, price=0.96, n_before=30.0, n_after=20.0, mult=1.5, live=True),
        _r("settled", T % (45, 20), ticker="KXADA15M-26NOV050045-45", want="yes", result="yes", cost=0.96, pnl_c=76.0),
        # H: the extra Yes leg trimmed 50 -> 30 at 20c; the extra side LOST: 20 x 20c + fee 0.23 = 4.23 saved
        _r("extra_stake_capped", T % (59, 50), ticker="KXLINK15M-26NOV050100-00", close_s=1793860200, side="yes",
           asked=50.0, allowed=30.0, trimmed=20.0, reason="max_run_stake", mult=1.25, live=True),
        _r("hedge_extra", T % (59, 50), ticker="KXLINK15M-26NOV050100-00", side="yes", price=0.20, n=30.0, asked=30.0,
           extra_of=30.0, mult=1.25, base_n=120.0, tau=12, belief=0.35, trigger="belief", trigger_label="belief",
           fired_on_belief=True, order_id="x-3", status="executed", live=True),
        _r("settled", "2026-11-05T06:00:20Z", ticker="KXLINK15M-26NOV050100-00", want="no", result="no", cost=0.95,
           pnl_c=150.0),
        _r("settled", "2026-11-05T06:00:35Z", ticker="KXLINK15M-26NOV050100-00", want="yes", result="no", cost=0.20,
           pnl_c=-620.0),
        # I: a full No buy let through with 3 open; 32 filled at 99c, the leg made 29.78 (pnl_c is cents)
        _r("open_cap_relaxed", "2026-11-05T06:14:44Z", ticker="KXETH15M-26NOV050115-15", close_s=1793861100, side="no",
           open_positions=3, old_cap=3, leg="full", live=True),
        _r("order", "2026-11-05T06:14:45Z", ticker="KXETH15M-26NOV050115-15", want="no", leg="full", filled=32.0,
           exec_price=0.99, limit_sent=0.99, status="executed", body={"count": "32.00"}),
        _r("settled", "2026-11-05T06:15:20Z", ticker="KXETH15M-26NOV050115-15", want="no", result="no", cost=0.99,
           pnl_c=2978.0),
        # J: the odds line fired while the alarm still said "jump": 25 extra Yes at 30c, the bet flipped: +17.00
        # (C counts this leg too, by its own fee: 17.50 - 0.37 = 17.13)
        _r("hedge_extra", "2026-11-05T06:29:40Z", ticker="KXBCH15M-26NOV050130-30", side="yes", price=0.30, n=25.0,
           asked=25.0, extra_of=25.0, mult=1.25, base_n=100.0, tau=15, belief=0.35, trigger="jump", trigger_label="jump",
           fired_on_belief=True, order_id="x-4", status="executed", live=True),
        _r("settled", "2026-11-05T06:30:20Z", ticker="KXBCH15M-26NOV050130-30", want="no", result="yes", cost=0.97,
           pnl_c=-9700.0),
        _r("settled", "2026-11-05T06:30:35Z", ticker="KXBCH15M-26NOV050130-30", want="yes", result="yes", cost=0.30,
           pnl_c=1700.0),
        # J, pending: fired on belief under a jump label, the market not settled yet (closes 01:45 ET; NOW is 02:00)
        _r("hedge_extra", "2026-11-05T06:44:40Z", ticker="KXTRX15M-26NOV050145-45", side="no", price=0.25, n=10.0,
           asked=10.0, extra_of=10.0, mult=1.25, base_n=40.0, tau=15, belief=0.30, trigger="jump", trigger_label="jump",
           fired_on_belief=True, order_id="x-5", status="executed", live=True),
    ]
    return recs


def write_logs(d, older=True):
    """The synthetic logs in folder `d`: an older build's log (10-31), the 0925r run and the new build's run. Returns
    their paths (name order = time order)."""
    out = []
    runs = [("pinrun-live-20261102T133522Z.jsonl", run_r([])), ("pinrun-live-20261105T050000Z.jsonl", run_new([]))]
    if older:   # another sha BEFORE 0925r must not start D..J; a garbage line and a record with no t are skipped
        runs.insert(0, ("pinrun-live-20261031T101116Z.jsonl",
                        [_r("start", "2026-10-31T10:11:16Z", code_sha="24eec22bbaa7"),
                         _r("settled", "2026-10-31T11:30:20Z", ticker="KXHYPE15M-26OCT310730-30", want="yes",
                            result="yes", cost=0.98, pnl_c=39.0)]))
    for name, recs in runs:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
            if name.startswith("pinrun-live-20261031"):
                fh.write("this is not json\n")
                fh.write(json.dumps({"kind": "settled", "ticker": "KXNOTIME15M-26OCT310745-45", "want": "yes"}) + "\n")
                fh.write(json.dumps({"kind": "hedge", "ticker": "KXBAD15M-26OCT310800-00", "t": "2026-10-31T12:00:00Z",
                                     "tick_rounded": True, "limit_legacy": "garbage"}) + "\n")
        out.append(p)
    return out


def _by_id(rep):
    return {c["id"]: c for c in rep}


def _report(paths=None, now=NOW):
    F._CACHE.clear()
    return _by_id(F.report(paths=paths, now=now))


def test_shape_and_sinces():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    rep = _report(write_logs(d))
    ck("".join(sorted(rep)) == F.IDS == "ABCDEFGHIJKL", "twelve changes A..L, one row each")
    for c in rep.values():
        ck(set(c) >= {"id", "name", "what", "since", "engaged", "last_engaged", "open", "net_usd", "events", "extra",
                      "not_live"}, "%s carries every field" % c["id"])
        for e in c["events"]:
            ck(set(e) >= {"t", "coin", "words", "usd"} and "\u2014" not in e["words"], "%s event fields, no em dash" % c["id"])
        ck("\u2014" not in c["what"], "%s what has no em dash" % c["id"])
    ck(rep["A"]["since"] == "Nov 1 3:37 PM ET" and rep["B"]["since"] == "Nov 1 3:37 PM ET", "A and B since 11-01 15:37 ET")
    ck(rep["C"]["since"] == "Nov 2 8:35 AM ET", "C since 11-02 08:35 ET")
    for k in "DEFGHIJ":
        ck(rep[k]["since"] == "Nov 5 12:00 AM ET", "%s since the new build's start (not the 10-31 sha before 0925r)" % k)
    ck(rep["K"]["since"] is None and rep["K"]["engaged"] == 0 and rep["K"]["extra"] == [],
       "K is not live before a start record names a cheap_window")
    ck(rep["L"]["since"] is None and rep["L"]["engaged"] == 0 and rep["L"]["extra"] == []
       and rep["L"]["not_live"] == F.L_NOT_LIVE == "not live yet (comes with the next pin restart)"
       and all(rep[k]["not_live"] is None for k in "ABCDEFGHIJK"),
       "L is not live before a start record has hedge_jump_shadow set, and says what it waits for: %s" % rep["L"]["not_live"])


def test_rules_abc_reuse_pinrules_watch():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    rep = _report(write_logs(d))
    A, B, C = rep["A"], rep["B"], rep["C"]
    ck(A["engaged"] == 1 and A["net_usd"] == 35.61 and A["open"] == 0, "A: one refusal, saved 35.61 (score_A): %s" % A["net_usd"])
    ck("skipped a topup buy of 41 No" in A["events"][0]["words"] and A["events"][0]["coin"] == "HYPE", "A words")
    ck(B["engaged"] == 1 and B["net_usd"] == 5.32, "B: one capped jump, saved 5.32 (score_B): %s" % B["net_usd"])
    ck(C["engaged"] == 5 and C["open"] == 2 and C["net_usd"] == 95.94,
       "C: 5 filled extra legs (two open): 85.15 - 6.34 (H's trimmed leg, 30 at 20c lost) + 17.13 (score_C): %s" % C["net_usd"])
    opn = [e for e in C["events"] if e["usd"] is None]
    ck([e["coin"] for e in opn] == ["SOL", "TRX"] and all("not settled" in e["words"] for e in opn), "C's open events say so")
    ck(C["last_engaged"] == "Nov 5 1:44 AM ET" and C["events"][-1]["coin"] == "TRX", "C last engaged = J's pending leg")


def test_d_boost_rail():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    D = _report(write_logs(d))["D"]
    ck(D["engaged"] == 1 and D["open"] == 0, "D: one kept record")
    ck(D["net_usd"] == -9.55, "D: the two boosted legs after it, extra 10 contracts each: +0.18 - 9.73 = -9.55: %s" % D["net_usd"])
    w = D["events"][0]["words"]
    ck("losing No leg" in w and "Yes side had the band boost" in w and "2 boosted legs since" in w and "lost $9.55" in w,
       "D words: %s" % w)
    ck(D["events"][0]["coin"] == "HYPE" and D["events"][0]["et"] == "Nov 5 12:30 AM ET", "D event time and coin")


def test_e_hedge_tick():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    E = _report(write_logs(d))["E"]
    ck(E["engaged"] == 2 and E["open"] == 0, "E: the filled rounded hedge and the unfilled one; the on-grid one not")
    ck(E["net_usd"] == -0.80, "E: the filled hedge leg's own pnl_c: -0.80: %s" % E["net_usd"])
    w = {e["coin"]: e for e in E["events"]}
    ck("11.5c was rounded to 11.0c" in w["DOGE"]["words"] and "cost $0.80" in w["DOGE"]["words"], "E words: %s" % w["DOGE"]["words"])
    ck(w["SOL"]["usd"] == 0.0 and "did not fill" in w["SOL"]["words"], "E unfilled: no money either way")


def test_f_cheap_jump_skip():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    Fx = _report(write_logs(d))["F"]
    ck(Fx["engaged"] == 2 and Fx["open"] == 0, "F: two skips")
    w = {e["coin"]: e for e in Fx["events"]}
    ck(w["AVAX"]["usd"] == 1.29 and "saved the premium" in w["AVAX"]["words"], "F bet won: +1.29: %s" % w["AVAX"])
    ck(w["LTC"]["usd"] == -22.97 and "got back $38.29" in w["LTC"]["words"] and "got back $15.32" in w["LTC"]["words"],
       "F bet lost: 15.32 - 38.29 = -22.97: %s" % w["LTC"])
    ck(Fx["net_usd"] == -21.68, "F net: %s" % Fx["net_usd"])


def test_g_h_i_j():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    rep = _report(write_logs(d))
    G, H, I, J = rep["G"], rep["H"], rep["I"], rep["J"]
    ck(G["engaged"] == 1 and G["net_usd"] == -0.37 and "10 fewer contracts" in G["events"][0]["words"]
       and "gave up $0.37" in G["events"][0]["words"], "G: the leg won, 10 fewer at 96c gave up 0.37: %s" % G["events"])
    ck(H["engaged"] == 1 and H["net_usd"] == 4.23 and "trimmed the extra Yes hedge leg by 20" in H["events"][0]["words"]
       and "at 20.0c" in H["events"][0]["words"], "H: the extra side lost, 20 at 20c saved 4.23: %s" % H["events"])
    ck(I["engaged"] == 1 and I["net_usd"] == 29.78 and "32 contracts filled at 99.0c" in I["events"][0]["words"],
       "I: the leg's own 29.78: %s" % I["events"])
    ck(J["engaged"] == 2 and J["open"] == 1 and J["net_usd"] == 17.0, "J: one scored (17.00), one pending: %s" % J)
    ck(J["events"][0]["coin"] == "BCH" and "alarm said jump" in J["events"][0]["words"] and "made $17.00" in J["events"][0]["words"],
       "J words: %s" % J["events"][0]["words"])
    ck(J["events"][1]["usd"] is None and J["events"][1]["open"], "J pending has no $ yet")
    T = F.totals(list(rep.values()))
    ck(T["engaged"] == 15 and T["open"] == 2
       and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2),
       "totals add up without J (its 2 engagements, 1 open, +17.00 are C's legs too): %s" % T)
    ck(G["off"] is True and all(rep[k]["off"] is False for k in "ABCDEFHIJ"),
       "only G is marked off while the start record lacks late_bypass_fix on: %s" % {k: rep[k]["off"] for k in rep})


def test_not_live_yet_and_empty():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    rep = _report(ps[:2])                                  # the 0925r run only: D..L are not live
    for k in "DEFGHIJKL":
        ck(rep[k]["since"] is None and rep[k]["engaged"] == 0 and rep[k]["net_usd"] == 0.0 and rep[k]["events"] == [],
           "%s not live yet" % k)
    ck(rep["I"]["what"] == "up to 5 positions open at once (was 3)", "the new flags' words before the build is live")
    ck(rep["C"]["engaged"] == 2 and rep["C"]["net_usd"] == 85.15, "C counts its two 0925r legs (one open)")
    rep = _report([])
    ck(all(c["engaged"] == 0 for c in rep.values()) and rep["A"]["since"] and rep["D"]["since"] is None, "no logs at all")
    rep = _report([os.path.join(d, "missing.jsonl")])
    ck(all(c["engaged"] == 0 for c in rep.values()), "a missing log is tolerated")


NOW_K = 1794080400.0               # 2026-11-07T19:00:00Z = 2:00 PM ET


def run_k(recs):
    """The 0925u run (11-07 07:00 ET on, --cheap-window 6 10 0.98): K. Every $ worked by hand: a skipped market holds
    n_ask x 0.78 / 0.83 contracts at the ladder's average price, plus its shadow hedge (hedge_mult x those, fee in)."""
    T = "2026-11-07T%s:%s:%sZ"
    recs += [
        _r("start", T % ("12", "00", "00"), code_sha="0e0e0e0e0e0e", cheap_window=[6.0, 10.0, 0.98]),
        # K, FLIPPED (BNB 8:15 AM): 193.81 x 0.78 / 0.83 = 182.13 No at 97.287c lost 177.19 + fee 0.34 = -177.53; the
        # shadow hedge, 1.25 x = 227.67 Yes at 70c, made 68.30 - fee 3.35 = +64.95: the buy would have lost 112.58
        _r("refused", T % ("13", "14", "15"), gate="cheap_window", ticker="KXBNB15M-26NOV070815-15", close_s=1794057300,
           want="no", leg="early", tau=45, price=0.97, fair=0.00013, window=[6.0, 10.0, 0.98], size=110.76,
           n_ask=193.81, px=0.97287, lim=0.98, got=193.81, size_now=388.0),
        _r("cheap_window_settled", T % ("13", "15", "40"), ticker="KXBNB15M-26NOV070815-15", close_s=1794057300,
           result="yes", won=False, want="no", price=0.97, n_ask=193.81, px=0.97287, got=193.81, lim=0.98, tau=45,
           leg="early", hedge_px=0.70, hedge_tau=23, hedge_belief=0.34116, hedge_mult=1.25, window=[6.0, 10.0, 0.98]),
        # K, WON (ETH 7:30 AM): 50 x 0.78 / 0.83 = 46.99 Yes at 97.5c made 1.17 - fee 0.09 = +1.08: the rule gave it up
        _r("refused", T % ("12", "29", "40"), gate="cheap_window", ticker="KXETH15M-26NOV070730-30", close_s=1794054600,
           want="yes", leg="full", tau=20, price=0.975, fair=0.996, window=[6.0, 10.0, 0.98], size=50.0, n_ask=50.0,
           px=0.975, lim=0.98, got=50.0, size_now=388.0),
        _r("cheap_window_settled", T % ("12", "30", "45"), ticker="KXETH15M-26NOV070730-30", close_s=1794054600,
           result="yes", won=True, want="yes", price=0.975, n_ask=50.0, px=0.975, hedge_px=None, window=[6.0, 10.0, 0.98]),
        # K, OPEN (SOL 9:45 AM): no shadow result yet (1 h 15 m past its close at NOW_K: pending, not unknown)
        _r("refused", T % ("14", "44", "30"), gate="cheap_window", ticker="KXSOL15M-26NOV070945-45", close_s=1794062700,
           want="no", leg="full", tau=30, price=0.96, fair=0.003, window=[6.0, 10.0, 0.98], size=20.0, n_ask=40.0,
           px=0.962, lim=0.98, got=40.0, size_now=388.0),
        # another gate's refusal is not K's
        _r("refused", T % ("13", "29", "50"), gate="wrong_side", ticker="KXXRP15M-26NOV070830-30", close_s=1794058200,
           want="yes", tau=10, price=0.97),
        # the window as pin traded it: a kept 98.5c buy closing 8:30 AM (+1.50) counts, an 11:30 AM close does not
        _r("settled", T % ("13", "30", "20"), ticker="KXZEC15M-26NOV070830-30", want="yes", result="yes", cost=0.985,
           pnl_c=150.0),
        _r("settled", T % ("16", "30", "20"), ticker="KXETH15M-26NOV071130-30", want="no", result="no", cost=0.99,
           pnl_c=500.0),
    ]
    return recs


def test_k_cheap_window():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    p = os.path.join(d, "pinrun-live-20261107T101819Z.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        for r in run_k([]):
            fh.write(json.dumps(r) + "\n")
    rep = _report(ps + [p], now=NOW_K)
    K = rep["K"]
    ck(K["since"] == "Nov 7 7:00 AM ET" and K["engaged"] == 3 and K["open"] == 1,
       "K: since the first start naming a cheap window; three skips, one open: %s" % {x: K[x] for x in ("since", "engaged", "open")})
    w = {e["coin"]: e for e in K["events"]}
    ck(w["BNB"]["usd"] == 112.58 and "FLIPPED" in w["BNB"]["words"] and "would have lost $112.58" in w["BNB"]["words"]
       and "Yes hedge pin would have bought at 70.0c" in w["BNB"]["words"] and "saved" in w["BNB"]["words"]
       and "skipped a first No buy at 97.0c with 45 s left (about 182 contracts)" in w["BNB"]["words"],
       "K flipped: -177.53 + 64.95 = -112.58 without the rule, +112.58 saved: %s" % w["BNB"])
    ck(w["ETH"]["usd"] == -1.08 and "WON" in w["ETH"]["words"] and "would have made $1.08" in w["ETH"]["words"]
       and "gave up" in w["ETH"]["words"] and "hedge" not in w["ETH"]["words"],
       "K won: +1.08 without the rule, -1.08 given up: %s" % w["ETH"])
    ck(w["SOL"]["usd"] is None and w["SOL"]["open"] and "XRP" not in w,
       "K open: no $ until its shadow settles; another gate's refusal is not K's")
    ck(K["net_usd"] == 111.5, "K net: +112.58 - 1.08 = +111.50: %s" % K["net_usd"])
    ck(K["extra"] == ["without the rule: the 2 settled skips would have lost $111.50 (1 won, 1 flipped, hedges in) "
                      "\u00b7 1 still open",
                      "closes 6 AM to 10 AM ET since the rule (1 settled market): pin made +$1.50 with it, -$110.00 without it"],
       "K extra: the skips without the rule, and the window with (+1.50) and without (+1.50 - 111.50): %s" % K["extra"])
    ck(K["what"] == "no first buy under 98.0c in a market closing 6 AM to 10 AM ET (the market is skipped); each skip is "
                    "priced by what it would have done", "K what, off the start record: %s" % K["what"])
    T = F.totals(list(rep.values()))
    ck(T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2) and T["engaged"] == 18,
       "totals take K in (15 + 3 engagements): %s" % T)
    ck(F.cw_in_window(1794054600, [6, 10]) and F.cw_in_window(1794049200, [6, 10]) and not F.cw_in_window(1794063600, [6, 10])
       and not F.cw_in_window(1794048300, [6, 10]) and F.cw_in_window(1792836000, [6, 10]) and not F.cw_in_window(None, [6, 10]),
       "cw_in_window: 7:30 and 6:00 in, 10:00 and 5:45 out (EST), 06:00 EDT on 10-24 in, no close out")
    ck(F.cw_shadow_usd({"result": None}) is None and F.cw_shadow_usd({"result": "no", "want": "no", "n_ask": 0}) == 0.0
       and F._hour(6) == "6 AM" and F._hour(10) == "10 AM" and F._hour(12) == "12 PM" and F._hour(15) == "3 PM"
       and F._hour(24) == "12 AM", "K helpers")


NOW_L = 1794177600.0               # 2026-11-08T22:40:00Z = 5:40 PM ET


def run_l(recs):
    """The 0925v shadow run (11-08 14:00 ET on, --hedge-jump-shadow 6 in place of --hedge-jump 6, the 8 sd cap and the
    5c bar kept): L. Every $ worked by hand: the shadow hedge is n x ask plus Kalshi's fee ceil(7 x ask x (1 - ask) x n)
    / 100; the real hedge is pin's own hedge record on those contracts, the same way."""
    T = "2026-11-08T%s:%s:%sZ"
    JS = dict(threshold=6.0, cap=8.0, min_ask=0.05, panic=False, filtered=False, belief_fires=False, extra_n=0.0,
              sent=False, live=True)
    recs += [
        _r("start", T % ("19", "00", "00"), code_sha="d51b131b55cf", hedge_jump=None, hedge_jump_shadow=6.0, hedge_jump_max=8.0,
           jump_hedge_min_ask=0.05, cheap_window=[6.0, 10.0, 0.98], max_positions=5, boost_rail="off", hedge_tick="round",
           hedge_odds_mult=1.25, ws_later_fall_c=10.0),
        # L, WON, no hedge bought (ZEC 2:15 PM): 40 No at 12c = 4.80 + fee ceil(0.07 x 40 x 0.12 x 0.88 x 100 = 29.57)
        # / 100 = 0.30: the 5.10 premium stayed in the bank (+5.10)
        _r("jump_shadow", T % ("19", "14", "40"), ticker="KXZEC15M-26NOV081415-15", close_s=1794167700, want="yes", entry=0.97,
           side="no", n=40.0, n_want=40.0, ask=0.12, ask_size=200.0, limit=0.22, belief=0.88, jump_sd=6.7, tau=20,
           capped=False, cheap_skip=False, would_send=True, outcome="would_send", **JS),
        _r("settled", T % ("19", "15", "20"), ticker="KXZEC15M-26NOV081415-15", want="yes", result="yes", cost=0.97, pnl_c=111.0),
        # L, FLIPPED (BNB 2:30 PM): 100 Yes at 10c would have got back 90.00 - fee 0.63 = 89.37; pin's odds hedge then
        # really bought the same 100 at 60c: 40.00 - fee 1.68 = 38.32; going without the jump hedge cost 51.05
        _r("jump_shadow", T % ("19", "29", "35"), ticker="KXBNB15M-26NOV081430-30", close_s=1794168600, want="no", entry=0.97,
           side="yes", n=100.0, n_want=100.0, ask=0.10, ask_size=150.0, limit=0.20, belief=0.80, jump_sd=7.2, tau=25,
           capped=False, cheap_skip=False, would_send=True, outcome="would_send", **JS),
        _r("hedge", T % ("19", "29", "45"), ticker="KXBNB15M-26NOV081430-30", close_s=1794168600, side="yes", price=0.60, n=100.0,
           asked=100.0, ask=0.60, ask_size=120.0, limit_sent=0.70, entry=0.97, tau=15, belief=0.33, status="executed", live=True,
           tick_mode="round", limit_legacy=0.70, tick_rounded=False),
        _r("settled", T % ("19", "30", "20"), ticker="KXBNB15M-26NOV081430-30", want="no", result="yes", cost=0.97, pnl_c=-9700.0),
        _r("settled", T % ("19", "30", "35"), ticker="KXBNB15M-26NOV081430-30", want="yes", result="yes", cost=0.60, pnl_c=3832.0),
        # L, not counted: a 9.1 sd alarm the 8 sd cap stops (BTC 2:45 PM) and a 2c ask under the 5c bar (DOGE 2:45 PM)
        _r("jump_shadow", T % ("19", "44", "50"), ticker="KXBTC15M-26NOV081445-45", close_s=1794169500, want="no", entry=0.98,
           side="yes", n=37.0, n_want=37.0, ask=0.001, ask_size=706484.0, limit=0.101, belief=1.0, jump_sd=9.1, tau=10,
           capped=True, cheap_skip=True, would_send=False, outcome="capped", **JS),
        _r("settled", T % ("19", "45", "20"), ticker="KXBTC15M-26NOV081445-45", want="no", result="no", cost=0.98, pnl_c=70.0),
        _r("jump_shadow", T % ("19", "44", "52"), ticker="KXDOGE15M-26NOV081445-45", close_s=1794169500, want="yes", entry=0.975,
           side="no", n=50.0, n_want=50.0, ask=0.02, ask_size=300.0, limit=0.12, belief=0.95, jump_sd=6.3, tau=8,
           capped=False, cheap_skip=True, would_send=False, outcome="cheap_skip", **JS),
        _r("settled", T % ("19", "45", "20"), ticker="KXDOGE15M-26NOV081445-45", want="yes", result="yes", cost=0.975, pnl_c=120.0),
        # L, WON but pin's odds hedge fired anyway (XRP 3:00 PM): the jump hedge would have paid 20 x 10c + fee 0.13 =
        # 2.13 and pre-empted the odds hedge, which really paid 20 x 50c + fee 0.35 = 10.35: going without it cost 8.22
        _r("jump_shadow", T % ("19", "59", "40"), ticker="KXXRP15M-26NOV081500-00", close_s=1794170400, want="yes", entry=0.97,
           side="no", n=20.0, n_want=20.0, ask=0.10, ask_size=90.0, limit=0.20, belief=0.82, jump_sd=6.1, tau=20,
           capped=False, cheap_skip=False, would_send=True, outcome="would_send", **JS),
        _r("hedge", T % ("19", "59", "50"), ticker="KXXRP15M-26NOV081500-00", close_s=1794170400, side="no", price=0.50, n=20.0,
           asked=20.0, ask=0.50, ask_size=40.0, limit_sent=0.60, entry=0.97, tau=10, belief=0.36, status="executed", live=True,
           tick_mode="round", limit_legacy=0.60, tick_rounded=False),
        _r("settled", "2026-11-08T20:00:20Z", ticker="KXXRP15M-26NOV081500-00", want="yes", result="yes", cost=0.97, pnl_c=60.0),
        _r("settled", "2026-11-08T20:00:35Z", ticker="KXXRP15M-26NOV081500-00", want="no", result="yes", cost=0.50, pnl_c=-1035.0),
        # a hedge that did NOT fill (order refused, n 0) is nobody's real hedge
        _r("hedge", T % ("19", "59", "52"), ticker="KXXRP15M-26NOV081500-00", close_s=1794170400, side="no", price=0.50, n=0.0,
           asked=20.0, status=None, order_id=None, live=True),
        # L, OPEN (SOL 4:45 PM): no settled record yet (15 min past its close at NOW_L: pending)
        _r("jump_shadow", T % ("21", "44", "30"), ticker="KXSOL15M-26NOV081645-45", close_s=1794176700, want="no", entry=0.96,
           side="yes", n=30.0, n_want=30.0, ask=0.08, ask_size=100.0, limit=0.18, belief=0.90, jump_sd=6.4, tau=30,
           capped=False, cheap_skip=False, would_send=True, outcome="would_send", **JS),
    ]
    return recs


def test_l_jump_shadow():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    pk = os.path.join(d, "pinrun-live-20261107T101819Z.jsonl")
    pl = os.path.join(d, "pinrun-live-20261108T190000Z.jsonl")
    for p, recs in ((pk, run_k([])), (pl, run_l([]))):
        with open(p, "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
    rep = _report(ps + [pk, pl], now=NOW_L)
    L = rep["L"]
    ck(L["since"] == "Nov 8 2:00 PM ET" and L["engaged"] == 4 and L["open"] == 1 and L["not_live"] is None,
       "L: since the first start with hedge_jump_shadow set; four would_send alarms, one open: %s" % {
           x: L[x] for x in ("since", "engaged", "open")})
    w = {e["coin"]: e for e in L["events"]}
    ck(sorted(w) == ["BNB", "SOL", "XRP", "ZEC"], "L: one event per would_send; the capped BTC and the cheap DOGE are not events: %s" % sorted(w))
    ck(w["ZEC"]["usd"] == 5.10 and w["ZEC"]["words"] == (
        "a 6.7 sd jump against Yes with 20 s left: it would have bought 40 No at 12.0c (odds 88% our way); nothing was "
        "sent; the bet won and no hedge was needed, so that premium stayed in the bank: $5.10 kept"),
       "L won, no hedge: 4.80 + fee 0.30 kept: %s" % w["ZEC"])
    ck(w["BNB"]["usd"] == -51.05 and "FLIPPED" in w["BNB"]["words"] and "would have got back $89.37" in w["BNB"]["words"]
       and "really got back $38.32" in w["BNB"]["words"] and "going without it cost $51.05" in w["BNB"]["words"],
       "L flipped: 38.32 - 89.37 = -51.05 (the save missed): %s" % w["BNB"])
    ck(w["XRP"]["usd"] == -8.22 and "the bet won: it would have paid $2.13" in w["XRP"]["words"]
       and "really paid $10.35" in w["XRP"]["words"] and "going without it cost $8.22" in w["XRP"]["words"],
       "L won with the odds hedge anyway: -10.35 + 2.13 = -8.22 (the unfilled hedge not counted): %s" % w["XRP"])
    ck(w["SOL"]["usd"] is None and w["SOL"]["open"] and w["SOL"]["et"] == "Nov 8 4:44 PM ET", "L open: no $ until it settles")
    ck(L["net_usd"] == -54.17, "L net: 5.10 - 51.05 - 8.22 = -54.17: %s" % L["net_usd"])
    ck(L["extra"] == ["would have paid $7.23 in premiums on 2 won markets · would have saved $51.05 on 1 flip (vs the odds "
                      "hedge pin really bought) · 1 still open",
                      "so it would have made $54.17 (pin's odds hedge really paid $10.35 on those won markets); not counted: "
                      "1 capped (8 sd or more), 1 under the 5.0c bar"],
       "L extra: paid 5.10 + 2.13, saved 51.05, made 51.05 - 7.23 + 10.35 = 54.17 = -net; the cap and bar counts: %s" % L["extra"])
    ck(L["what"] == ("the jump hedge is in shadow: it sends nothing; this is what it would have made (6 sd alarm, 8 sd cap, "
                     "5.0c bar as before)"), "L what, off the start record: %s" % L["what"])
    ck(L["last_engaged"] == "Nov 8 4:44 PM ET" and L["events"][0]["coin"] == "ZEC", "L events in time order")
    ck(rep["K"]["since"] == "Nov 7 7:00 AM ET" and rep["K"]["engaged"] == 3, "K unchanged by the shadow run (its start also names the window)")
    T = F.totals(list(rep.values()))
    ck(T["engaged"] == 22 and T["open"] == 4
       and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2),
       "totals take L in (15 + 3 + 4 engagements; its kept premium and missed save are pin's real money): %s" % T)
    # helpers: the shadow fill and its premium; the outcome off the flags for a record without the field
    ck(F.js_fills({"n": 40, "ask": 0.12}) == [(40.0, 0.12)] and F.js_fills({"n": 0, "ask": 0.12}) == []
       and F.js_fills({"n": 5, "ask": None}) == [] and F.js_fills({"n": 5, "ask": 1.0}) == [] and F.js_fills(None) == []
       and F.js_premium({"n": 40, "ask": 0.12}) == 5.10 and F.js_premium({"n": 100, "ask": 0.10}) == 10.63
       and F.js_premium({}) == 0.0, "js_fills / js_premium")
    ck(F.js_outcome({"outcome": "no_ask"}) == "no_ask" and F.js_outcome({"would_send": True}) == "would_send"
       and F.js_outcome({"capped": True}) == "capped" and F.js_outcome({"cheap_skip": True}) == "cheap_skip"
       and F.js_outcome({}) == "other", "js_outcome, with and without the field")
    # before the shadow start: the same records in a run whose start record has no hedge_jump_shadow count for nothing
    with open(pl, "w", encoding="utf-8") as fh:
        for r in run_l([]):
            if r["kind"] == "start":
                r = dict(r, hedge_jump=6.0, hedge_jump_shadow=None)
            fh.write(json.dumps(r) + "\n")
    rep = _report(ps + [pk, pl], now=NOW_L)
    ck(rep["L"]["since"] is None and rep["L"]["engaged"] == 0 and rep["L"]["not_live"] == F.L_NOT_LIVE,
       "L: a run with --hedge-jump 6 (no shadow flag) is not live, whatever records it holds")


def test_l_two_positions_share_the_real_hedge():
    """Two shadowed positions on one market (an early and a full leg) each take their own part of pin's hedges: the
    real hedge's contracts are claimed once, in time order."""
    d = tempfile.mkdtemp(prefix="fixes-test-")
    T = "2026-11-08T%s:%s:%sZ"
    JS = dict(threshold=6.0, cap=8.0, min_ask=0.05, capped=False, cheap_skip=False, would_send=True, outcome="would_send",
              sent=False, live=True)
    recs = [
        _r("start", T % ("19", "00", "00"), code_sha="d51b131b55cf", hedge_jump=None, hedge_jump_shadow=6.0, hedge_jump_max=8.0,
           jump_hedge_min_ask=0.05),
        # the early leg (60) and the full leg (40) both alarm at 2:29:35; pin's odds hedge then buys 60 at 50c and 40 at 55c
        _r("jump_shadow", T % ("19", "29", "35"), ticker="KXETH15M-26NOV081430-30", close_s=1794168600, want="no", entry=0.97,
           side="yes", n=60.0, ask=0.10, ask_size=500.0, belief=0.80, jump_sd=6.5, tau=25, **JS),
        _r("jump_shadow", T % ("19", "29", "35"), ticker="KXETH15M-26NOV081430-30", close_s=1794168600, want="no", entry=0.975,
           side="yes", n=40.0, ask=0.10, ask_size=500.0, belief=0.80, jump_sd=6.5, tau=25, **JS),
        _r("hedge", T % ("19", "29", "45"), ticker="KXETH15M-26NOV081430-30", side="yes", price=0.50, n=60.0, asked=60.0,
           status="executed", live=True),
        _r("hedge", T % ("19", "29", "46"), ticker="KXETH15M-26NOV081430-30", side="yes", price=0.55, n=40.0, asked=40.0,
           status="executed", live=True),
        _r("settled", T % ("19", "30", "20"), ticker="KXETH15M-26NOV081430-30", want="no", result="yes", cost=0.97, pnl_c=-9700.0),
        _r("settled", T % ("19", "30", "35"), ticker="KXETH15M-26NOV081430-30", want="yes", result="yes", cost=0.52, pnl_c=4500.0),
    ]
    p = os.path.join(d, "pinrun-live-20261108T190000Z.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    L = _report([p], now=NOW_L)["L"]
    # first: 60 at 10c would get back 54.00 - fee 0.38 = 53.62; the real 60 at 50c got 30.00 - fee 1.05 = 28.95: -24.67
    # second: 40 at 10c: 36.00 - 0.26 = 35.74; the real 40 at 55c: 18.00 - fee ceil(69.3)/100 = 0.70 -> 17.30: -18.44
    ck(L["engaged"] == 2 and [e["usd"] for e in L["events"]] == [-24.67, -18.44] and L["net_usd"] == -43.11,
       "two positions, one market: 28.95 - 53.62 and 17.30 - 35.74, the 100 real contracts claimed once: %s" % [
           (e["usd"], e["words"][-80:]) for e in L["events"]])
    ck(L["extra"][0].startswith("would have paid $0.00 in premiums on 0 won markets · would have saved $43.11 on 2 flips"),
       "the saves add up: %s" % L["extra"][0])

def test_l_real_hedge_bigger_than_shadow():
    """pin's real hedge record can hold MORE contracts than the shadow would have bought (a later, larger odds-line fill,
    or one record covering two positions): only the shadow's contracts are claimed, never the whole record."""
    d = tempfile.mkdtemp(prefix="fixes-test-")
    T = "2026-11-08T%s:%s:%sZ"
    JS = dict(threshold=6.0, cap=8.0, min_ask=0.05, capped=False, cheap_skip=False, would_send=True, outcome="would_send",
              sent=False, live=True)
    recs = [
        _r("start", T % ("19", "00", "00"), code_sha="d51b131b55cf", hedge_jump=None, hedge_jump_shadow=6.0, hedge_jump_max=8.0,
           jump_hedge_min_ask=0.05),
        # FLIP (LTC 2:30 PM): the shadow would have bought 100 Yes at 10c; pin's odds hedge then bought 250 at 50c in one
        # record. Only 100 of the 250 count: 100 at 50c got back 50.00 - fee 1.75 = 48.25 against the shadow's 90.00 -
        # 0.63 = 89.37, so going without it cost 41.12 (claiming all 250 would say +31.25: 125.00 - 4.38 - 89.37)
        _r("jump_shadow", T % ("19", "29", "35"), ticker="KXLTC15M-26NOV081430-30", close_s=1794168600, want="no", entry=0.97,
           side="yes", n=100.0, ask=0.10, ask_size=500.0, belief=0.80, jump_sd=6.5, tau=25, **JS),
        _r("hedge", T % ("19", "29", "45"), ticker="KXLTC15M-26NOV081430-30", side="yes", price=0.50, n=250.0, asked=250.0,
           status="executed", live=True),
        _r("settled", T % ("19", "30", "20"), ticker="KXLTC15M-26NOV081430-30", want="no", result="yes", cost=0.97, pnl_c=-9700.0),
        _r("settled", T % ("19", "30", "35"), ticker="KXLTC15M-26NOV081430-30", want="yes", result="yes", cost=0.50, pnl_c=12500.0),
        # WON (NEAR 2:45 PM, the 11-07 20:45 ET shape from the real log): the shadow would have bought 300 Yes at 17c =
        # 51.00 + fee 2.97 = 53.97; pin's odds hedge really bought 195.8 at 16c and then 392.2 at 19.65c: the first
        # record whole (31.33 + fee 1.85 = 33.18) and 104.2 of the second (20.48 + fee 1.16 = 21.64) = 54.81, so going
        # without it cost 0.84 (claiming all 392.2 of the second would say 114.59 paid and -60.62)
        _r("jump_shadow", T % ("19", "44", "40"), ticker="KXNEAR15M-26NOV081445-45", close_s=1794169500, want="no", entry=0.97,
           side="yes", n=300.0, ask=0.17, ask_size=300.0, belief=0.75, jump_sd=6.2, tau=20, **JS),
        _r("hedge", T % ("19", "44", "48"), ticker="KXNEAR15M-26NOV081445-45", side="yes", price=0.16, n=195.8, asked=195.8,
           status="executed", live=True),
        _r("hedge", T % ("19", "44", "52"), ticker="KXNEAR15M-26NOV081445-45", side="yes", price=0.1965, n=392.2, asked=392.2,
           status="executed", live=True),
        _r("settled", T % ("19", "45", "20"), ticker="KXNEAR15M-26NOV081445-45", want="no", result="no", cost=0.97, pnl_c=1200.0),
        _r("settled", T % ("19", "45", "35"), ticker="KXNEAR15M-26NOV081445-45", want="yes", result="no", cost=0.18, pnl_c=-10800.0),
    ]
    p = os.path.join(d, "pinrun-live-20261108T190000Z.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    L = _report([p], now=NOW_L)["L"]
    ck(L["engaged"] == 2 and [e["usd"] for e in L["events"]] == [-41.12, -0.84] and L["net_usd"] == -41.96,
       "only the shadow's contracts are claimed from a bigger real hedge: 48.25 - 89.37 and 53.97 - 54.81: %s" % [
           (e["usd"], e["words"][-90:]) for e in L["events"]])
    ck("pin's odds hedge really paid $54.81 on those contracts, so going without it cost $0.84" in L["events"][1]["words"],
       "the real hedge is 195.8 at 16c plus 104.2 of the 392.2 at 19.65c: %s" % L["events"][1]["words"])
    ck(L["extra"][0].startswith("would have paid $53.97 in premiums on 1 won market · would have saved $41.12 on 1 flip")
       and L["extra"][1].startswith("so it would have made $41.96 (pin's odds hedge really paid $54.81 on those won markets)"),
       "the made line is minus the net to the cent: %s" % L["extra"])


def test_default_paths_through_botdata():
    with _kit.sandbox() as td:
        write_logs(td)
        with open(os.path.join(td, "pinrun-live-20261001T000000Z.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(_r("start", "2026-10-01T00:00:00Z", code_sha="aaaaaaaaaaaa")) + "\n")
        got = [os.path.basename(p) for p in F.pin_paths()]
        ck(got == ["pinrun-live-20261031T101116Z.jsonl", "pinrun-live-20261102T133522Z.jsonl",
                   "pinrun-live-20261105T050000Z.jsonl"], "pin_paths: the runs from 11-01 on plus the one before: %s" % got)
        rep = _report()
        ck(rep["A"]["net_usd"] == 35.61 and rep["J"]["net_usd"] == 17.0, "report() reads RESULTS through botdata.paths")
        ck(paths.RESULTS == td, "the sandbox's RESULTS")


def test_helpers():
    ck(F.off_grid(0.115) and F.off_grid(0.185) and not F.off_grid(0.11) and not F.off_grid(0.015)
       and not F.off_grid(0.999) and not F.off_grid(0.905) and not F.off_grid(None) and not F.off_grid("x")
       and F.off_grid(0.1234), "off_grid: the tapered_deci_cent grid")
    ck(F.close_of("KXZEC15M-26NOV040245-45") == 1793778300.0 and F.close_of("KXBTCD-26OCT3123-T77599.99") == 1793502000.0
       and F.close_of("nonsense") is None, "close_of from the ticker (ET, DST-aware)")
    ck(F.stamp_of(r"C:\x\pinrun-live-20261102T133522Z.jsonl") == 1793626522.0 and F.stamp_of("other.jsonl") is None,
       "stamp_of")
    ps = ["pinrun-live-20261030T213241Z.jsonl", "pinrun-live-20261031T101116Z.jsonl", "pinrun-live-20261101T203732Z.jsonl",
          "pinrun-live-20261102T133522Z.jsonl"]
    ck(F.paths_since(ps, F.SINCE_AB) == ps[1:], "paths_since keeps the run live at `since` and every later one")
    ck(F.paths_since(ps, 0) == ps and F.paths_since([], F.SINCE_AB) == [], "paths_since edges")
    ck(F.et_words(F.SINCE_AB) == "Nov 1 3:37 PM ET" and F.et_words(F.SINCE_C) == "Nov 2 8:35 AM ET"
       and F.et_words(None) is None, "the ET words of the two live moments (EST after 11-01)")


if __name__ == "__main__":
    sys.exit(_kit.run(dict(globals()), "test_fixes"))
