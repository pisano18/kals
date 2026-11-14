"""test_fixes.py -- botdata/fixes.py (v-fixes, 2026-11-04): every live pin change A..M scored on synthetic pin logs.

Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_fixes.py   (exit 0 = every test passed; botstats.py
--selftest runs it too). Synthetic runs: the 0925r build (code_sha ca156bf45704; rules A, B, C), a later build with
another sha (D..J), the 0925u cheap-window run (K), the 0925v jump-hedge-shadow run (L) and the call-B run with its
trajectory log (M). Every $ below is worked by hand from the scoring table (Kalshi's taker fee ceil(7 * p * (1 - p) * n)
/ 100 inside); the phone test (phone/tests/test_fixes_cmd.py) renders the same logs.
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
    ck("".join(sorted(rep)) == F.IDS == "ABCDEFGHIJKLMN" and F.LADDER_IDS == "O",
       "fourteen pin changes A..N, one row each; the ladder's O only when a ladder order log is read (none here)")
    ck(rep["C"]["extra"] == [], "C has no step line before any 1.5x start or leg: %s" % rep["C"]["extra"])
    for c in rep.values():
        ck(set(c) >= {"id", "name", "what", "since", "engaged", "last_engaged", "open", "net_usd", "events", "extra",
                      "not_live", "third"}, "%s carries every field" % c["id"])
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
    ck(rep["M"]["since"] is None and rep["M"]["engaged"] == 0 and rep["M"]["third"] == [] and rep["M"]["not_live"] == F.M_NOT_LIVE,
       "M is not live before a start record has extra_coin 0 and late_extra 0: %s" % rep["M"]["not_live"])


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
    rep = _report(ps[:2])                                  # the 0925r run only: D..M are not live
    for k in "DEFGHIJKLM":
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


NOW_M = 1794184800.0               # 2026-11-09T00:40:00Z = 7:40 PM ET
M_START = dict(code_sha="d51b131b55cf", extra_coin=0.0, late_extra=0.0, late_extra_tau=15, late_tau=10, bank_brake=4.5,
               size=20.0, max_per_close=2, max_per_market=2, pin=0.995, price_ceiling=0.98, band99_ceiling=0.99,
               band99_frac=0.1, edge_floor=0.003, ev_floor=0.003, measured_flip=0.009, dump_discount=0.15,
               early_min_price=0.9, early_frac=0.333, tau_max=30, tau_min=3, band_mults=[[0.955, 0.981, 1.5]],
               cheap_window=[6.0, 10.0, 0.98], coin_size_frac={"KXHYPE15M": 0.15}, hedge_jump_shadow=6.0, hedge_jump=None,
               hedge_jump_max=8.0, jump_hedge_min_ask=0.05, max_positions=5)
# the closes of the call-B run (UTC epoch): A third bet won (cost), B flipped (saved) with a held coin refused outside
# the late window, C the late slot (open), D unknown, E a held-back buy that won (cost), F one that lost (saved), G none
CL = {"A": 1794175200, "B": 1794176100, "C": 1794177000, "D": 1794173400, "E": 1794174300, "F": 1794178800, "G": 1794179700}


def _ts(epoch):
    import time as _t
    return _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(epoch))


def _order(t, tk, want, n, px, tau, leg="full", filled=None, limit=None):
    return _r("order", t, ticker=tk, want=want, leg=leg, tau_at_send=tau, filled=(n if filled is None else filled),
              exec_price=px, limit_sent=(px if limit is None else limit), status="executed",
              body={"count": "%.2f" % n, "ticker": tk}, client_order_id="pin-%s-%s" % (t, tk[-6:]))


def run_m(recs):
    """The call-B run (11-08 4:00 PM ET on, --extra-coin 0 --late-extra 0 --bank-brake 4.5; SIZE 100 after the autosize,
    so a close's budget is 200): M. Every $ worked by hand (Kalshi's fee ceil(7 x p x (1 - p) x n) / 100 inside)."""
    A, B, C, D, E, F, G = (CL[k] for k in "ABCDEFG")
    recs += [
        _r("start", "2026-11-08T21:00:00Z", **M_START),
        _r("autosize", "2026-11-08T21:00:01Z", old=20.0, new=100.0, series_size=10.0, why="bank $882"),
        # E (4:45 PM): XRP took 140 of the 200; NEAR (a new coin, 11 s left) got 60, the budget's last contracts, while the
        # book held 331 under 98c; the old argv's room (60 + 100) and the 1.5x band (96.5c) allowed 150: 90 more. NEAR won,
        # so the 90 would have made 90 x 2c (at the 98c limit) - fee ceil(7 x 90 x 0.98 x 0.02 = 12.35) / 100 = 0.13:
        # 1.80 - 0.13 = 1.67 given up
        _order(_ts(E - 25), "KXXRP15M-26NOV081645-45", "yes", 140.0, 0.975, 25),
        _r("signal", _ts(E - 11), live=True, ticker="KXNEAR15M-26NOV081645-45", want="no", price=0.965, tau=11, size=1.0,
           take_n=1.0, leg="full", budget_left=60.0, fair=0.00355, ladder=[[0.965, 1.0], [0.97, 400.0], [0.985, 20.0]]),
        _r("sweep_depth", _ts(E - 11), ticker="KXNEAR15M-26NOV081645-45", want="no", touch=1.0, ladder=331.0, was=1.0,
           now=60.0, limit=0.98),
        _order(_ts(E - 11), "KXNEAR15M-26NOV081645-45", "no", 60.0, 0.9699, 11, limit=0.98),
        _r("settled", _ts(E + 20), ticker="KXXRP15M-26NOV081645-45", want="yes", result="yes", cost=0.975, pnl_c=350.0),
        _r("settled", _ts(E + 20), ticker="KXNEAR15M-26NOV081645-45", want="no", result="no", cost=0.9699, pnl_c=180.6),
        # F (6:00 PM): BNB took 150; DOGE (new, 8 s left) got the last 50 of a 500 book at 97.8c; the old room 150 and the
        # band 1.5x allowed 150: 100 more. DOGE LOST, so the 100 would have lost 100 x 97.8c + fee ceil(7 x 100 x 0.978
        # x 0.022 = 15.06) / 100 = 0.16: 97.96 saved
        _order(_ts(F - 20), "KXBNB15M-26NOV081800-00", "yes", 150.0, 0.98, 20),
        _r("signal", _ts(F - 8), live=True, ticker="KXDOGE15M-26NOV081800-00", want="yes", price=0.978, tau=8, size=500.0,
           take_n=50.0, leg="full", budget_left=50.0, fair=0.9999, ladder=[[0.978, 500.0], [0.99, 100.0]]),
        _order(_ts(F - 8), "KXDOGE15M-26NOV081800-00", "yes", 50.0, 0.978, 8, limit=0.98),
        _r("settled", _ts(F + 20), ticker="KXBNB15M-26NOV081800-00", want="yes", result="yes", cost=0.98, pnl_c=300.0),
        _r("settled", _ts(F + 20), ticker="KXDOGE15M-26NOV081800-00", want="yes", result="no", cost=0.978, pnl_c=-4890.0),
        # G (6:15 PM), nothing for M: a full buy the budget did not bind (100 asked, 200 left), an early leg (its own
        # cap, not the budget's), and a bound buy the book did not even fill (20 asked, 12 filled)
        _r("signal", _ts(G - 45), live=True, ticker="KXSOL15M-26NOV081815-15", want="yes", price=0.99, tau=45, size=300.0,
           take_n=33.0, leg="early", budget_left=33.0, fair=0.999, ladder=[[0.99, 300.0]]),
        _order(_ts(G - 45), "KXSOL15M-26NOV081815-15", "yes", 33.0, 0.99, 45, leg="early"),
        _r("signal", _ts(G - 20), live=True, ticker="KXETH15M-26NOV081815-15", want="yes", price=0.97, tau=20, size=300.0,
           take_n=100.0, leg="full", budget_left=200.0, fair=0.9999, ladder=[[0.97, 300.0]]),
        _order(_ts(G - 20), "KXETH15M-26NOV081815-15", "yes", 100.0, 0.97, 20, limit=0.98),
        _r("signal", _ts(G - 10), live=True, ticker="KXZEC15M-26NOV081815-15", want="no", price=0.97, tau=10, size=300.0,
           take_n=20.0, leg="full", budget_left=20.0, fair=0.0001, ladder=[[0.97, 300.0]]),
        _order(_ts(G - 10), "KXZEC15M-26NOV081815-15", "no", 20.0, 0.97, 10, filled=12.0, limit=0.98),
        _r("settled", _ts(G + 20), ticker="KXSOL15M-26NOV081815-15", want="yes", result="yes", cost=0.99, pnl_c=30.0),
        _r("settled", _ts(G + 20), ticker="KXETH15M-26NOV081815-15", want="yes", result="yes", cost=0.97, pnl_c=280.0),
        _r("settled", _ts(G + 20), ticker="KXZEC15M-26NOV081815-15", want="no", result="no", cost=0.97, pnl_c=34.0),
        # A (5:00 PM): ZEC and BTC spent the 200; ETH, SOL and DOGE refused at 11 s. ETH never had an offer; SOL had 200
        # at 97c with fair 1.0: the one third bet, 100 Yes at 97c, and it WON: 100 x 3c - fee ceil(7 x 100 x 0.97 x 0.03 =
        # 20.37) / 100 = 0.21: 2.79 the block cost. DOGE (500 at 97.5c) found the slot taken.
        _order(_ts(A - 45), "KXZEC15M-26NOV081700-00", "yes", 33.0, 0.99, 45, leg="early"),
        _order(_ts(A - 20), "KXBTC15M-26NOV081700-00", "yes", 100.0, 0.97, 20),
    ] + [_r("refused", _ts(A - 11), gate="close_budget", ticker=tk, close_s=A, size_now=100.0, spent=200.0, budget=200.0,
            base=200.0, extra_coin=0.0, tau=11, size=100.0, budget_left=0.0)
         for tk in ("KXETH15M-26NOV081700-00", "KXSOL15M-26NOV081700-00", "KXDOGE15M-26NOV081700-00")] + [
        _r("settled", _ts(A + 20), ticker="KXZEC15M-26NOV081700-00", want="yes", result="yes", cost=0.99, pnl_c=30.0),
        _r("settled", _ts(A + 20), ticker="KXBTC15M-26NOV081700-00", want="yes", result="yes", cost=0.97, pnl_c=280.0),
        # B (5:15 PM): XRP (held, refused at 20 s with an offer) gets no third bet outside the late window and had no offer
        # inside it; BNB at 9 s: 150 at 96c, fair 99.9%: 100 Yes at 96c, and it FLIPPED: 100 x 96c + fee ceil(7 x 100 x
        # 0.96 x 0.04 = 26.88) / 100 = 0.27: 96.27 saved
        _order(_ts(B - 30), "KXXRP15M-26NOV081715-15", "yes", 100.0, 0.975, 30),
        _order(_ts(B - 25), "KXNEAR15M-26NOV081715-15", "no", 100.0, 0.98, 25),
        _r("refused", _ts(B - 20), gate="close_budget", ticker="KXXRP15M-26NOV081715-15", close_s=B, size_now=100.0,
           spent=200.0, budget=200.0, base=200.0, extra_coin=0.0, tau=20, size=100.0, budget_left=0.0),
        _r("refused", _ts(B - 9), gate="close_budget", ticker="KXBNB15M-26NOV081715-15", close_s=B, size_now=100.0,
           spent=200.0, budget=200.0, base=200.0, extra_coin=0.0, tau=9, size=100.0, budget_left=0.0),
        _r("settled", _ts(B + 20), ticker="KXXRP15M-26NOV081715-15", want="yes", result="yes", cost=0.975, pnl_c=250.0),
        _r("settled", _ts(B + 20), ticker="KXNEAR15M-26NOV081715-15", want="no", result="no", cost=0.98, pnl_c=200.0),
        # C (5:30 PM): DOGE (held) refused at 20 s with an offer; at 15 s (the late window, tau <= late_extra_tau) its 300
        # at 96.6c take the slot: 100 Yes at 96.6c, no result yet (the close is 2 h 10 min old at NOW_M: pending)
        _order(_ts(C - 30), "KXDOGE15M-26NOV081730-30", "yes", 100.0, 0.975, 30),
        _order(_ts(C - 27), "KXZEC15M-26NOV081730-30", "no", 100.0, 0.98, 27),
        _r("refused", _ts(C - 20), gate="close_budget", ticker="KXDOGE15M-26NOV081730-30", close_s=C, size_now=100.0,
           spent=200.0, budget=200.0, base=200.0, extra_coin=0.0, tau=20, size=100.0, budget_left=0.0),
        # D (4:30 PM): HYPE (a --coin-size-frac 0.15 coin: its full bet is 15) refused at 10 s with 50 at 97c; no result
        # anywhere 3 h 10 min later: unknown, still open
        _order(_ts(D - 30), "KXSOL15M-26NOV081630-30", "yes", 100.0, 0.97, 30),
        _order(_ts(D - 25), "KXBNB15M-26NOV081630-30", "no", 100.0, 0.975, 25),
        _r("refused", _ts(D - 10), gate="close_budget", ticker="KXHYPE15M-26NOV081630-30", close_s=D, size_now=100.0,
           spent=200.0, budget=200.0, base=200.0, extra_coin=0.0, tau=10, size=100.0, budget_left=0.0),
        _r("settled", _ts(D + 20), ticker="KXSOL15M-26NOV081630-30", want="yes", result="yes", cost=0.97, pnl_c=280.0),
        _r("settled", _ts(D + 20), ticker="KXBNB15M-26NOV081630-30", want="no", result="no", cost=0.975, pnl_c=230.0),
    ]
    return recs


def traj_m(recs):
    """The trajectory log of run_m's closes: one record a second a market (ask None = no offer on our side)."""
    A, B, C, D = (CL[k] for k in "ABCD")

    def tj(tk, cs, tau, ask, size, fair, want, held=None, gate="close_budget"):
        return _r("traj", _ts(cs - tau), ticker=tk, close_s=cs, tau=tau, want=want, held=held, fair=fair,
                  conf=(fair if want == "yes" else 1.0 - fair), spot=1.0, strike=1.0, eff_strike=1.0, ask=ask,
                  ask_size=(size if ask is not None else None), opp_ask=0.01, opp_size=100.0, gate=gate, near=True)
    for tau in range(11, -1, -1):
        recs.append(tj("KXETH15M-26NOV081700-00", A, tau, None, None, 1.0, "yes"))
        recs.append(tj("KXSOL15M-26NOV081700-00", A, tau, 0.97, 200.0, 1.0, "yes"))
        recs.append(tj("KXDOGE15M-26NOV081700-00", A, tau, 0.975, 500.0, 1.0, "yes"))
    for tau in range(20, -1, -1):
        recs.append(tj("KXXRP15M-26NOV081715-15", B, tau, (0.96 if tau >= 16 else None), 100.0, 1.0, "yes", held="yes"))
    for tau in range(9, -1, -1):
        recs.append(tj("KXBNB15M-26NOV081715-15", B, tau, 0.96, 150.0, (0.999 if tau >= 2 else 0.0), "yes"))
    for tau in range(20, 13, -1):
        recs.append(tj("KXDOGE15M-26NOV081730-30", C, tau, (0.965 if tau > 15 else 0.966), 300.0, 1.0, "yes", held="yes"))
    for tau in range(10, 2, -1):
        recs.append(tj("KXHYPE15M-26NOV081630-30", D, tau, 0.97, 50.0, 1.0, "yes"))
    return recs


def write_m(d):
    """run_m's pin log and its trajectory log in folder `d`; returns the pin log's path."""
    pm = os.path.join(d, "pinrun-live-20261108T210000Z.jsonl")
    with open(pm, "w", encoding="utf-8") as fh:
        for r in run_m([]):
            fh.write(json.dumps(r) + "\n")
    with open(os.path.join(d, "pintraj-live-20261108T210000Z.jsonl"), "w", encoding="utf-8") as fh:
        for r in traj_m([]):
            fh.write(json.dumps(r) + "\n")
    return pm


def test_m_third_bet_blocked():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    pk = os.path.join(d, "pinrun-live-20261107T101819Z.jsonl")
    pl = os.path.join(d, "pinrun-live-20261108T190000Z.jsonl")
    for p, recs in ((pk, run_k([])), (pl, run_l([]))):
        with open(p, "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
    pm = write_m(d)
    rep = _report(ps + [pk, pl, pm], now=NOW_M)
    M = rep["M"]
    ck(M["since"] == "Nov 8 4:00 PM ET" and M["not_live"] is None and rep["L"]["since"] == "Nov 8 2:00 PM ET",
       "M: since the first start record with extra_coin 0 and late_extra 0 (L's shadow start, without the fields, is not "
       "it): %s" % M["since"])
    # (1) the net: pin's own buys the 2-bet budget held back
    ck(M["engaged"] == 2 and M["open"] == 0 and M["net_usd"] == 96.29, "M: two held-back buys, -1.67 + 97.96 = +96.29: %s" % {
        x: M[x] for x in ("engaged", "open", "net_usd")})
    w = {e["coin"]: e for e in M["events"]}
    ck(w["NEAR"]["usd"] == -1.67 and w["NEAR"]["words"] == (
        "a full No buy at 97.0c with 11 s left was held to the 2-bet budget: 60 went out (the book had 331 under 98.0c; the "
        "old argv's third bet had room for 90 more, a new coin); the bet won, so holding them back gave up $1.67 (at the 98.0c "
        "limit: a ceiling)"), "M held-back, won: min(1.5 x 100, 331, 60 + 100) - 60 = 90 at the 98c limit: %s" % w["NEAR"])
    ck(w["DOGE"]["usd"] == 97.96 and "50 went out (the book had 500 under 98.0c; the old argv's third bet had room for 100 "
       "more, a new coin); the bet LOST, so holding them back saved $97.96" in w["DOGE"]["words"],
       "M held-back, lost: 100 x 97.8c + fee 0.16 = 97.96 saved: %s" % w["DOGE"])
    ck(sorted(w) == ["DOGE", "NEAR"] and w["NEAR"]["et"] == "Nov 8 4:44 PM ET" and w["DOGE"]["et"] == "Nov 8 5:59 PM ET",
       "M: the unbound ETH buy, the early SOL leg and the half-filled ZEC buy are not events: %s" % sorted(w))
    # (2) the true 3rd bets, under the net and not in it
    T3 = {(e["coin"], e["et"]): e for e in M["third"]}
    ck(len(M["third"]) == 4 and sorted(c for c, _t in T3) == ["BNB", "DOGE", "HYPE", "SOL"],
       "M third: one bet a close (A: SOL, B: BNB, C: DOGE, D: HYPE), never a second in the same close: %s" % sorted(T3))
    sol = T3[("SOL", "Nov 8 4:59 PM ET")]
    ck(sol["usd"] == -2.79 and sol["words"] == (
        "a 3rd bet of 100 Yes at 97.0c with 11 s left (fair 100.00% our way); it WON (the index at the close): the bet would "
        "have made $2.79, so blocking it cost $2.79 (a ceiling: its hedges are not known)"),
       "M third, won: 100 x 3c - fee 0.21 = 2.79 the block cost: %s" % sol)
    bnb = T3[("BNB", "Nov 8 5:14 PM ET")]
    ck(bnb["usd"] == 96.27 and "a 3rd bet of 100 Yes at 96.0c with 9 s left (fair 99.90% our way); it FLIPPED (the index at "
       "the close): the bet would have lost $96.27, so blocking it saved $96.27" in bnb["words"],
       "M third, flipped: 100 x 96c + fee 0.27 = 96.27 saved: %s" % bnb)
    doge = T3[("DOGE", "Nov 8 5:29 PM ET")]
    ck(doge["usd"] is None and doge["open"] and doge["t"] == "2026-11-08T22:29:45Z" and "with 15 s left" in doge["words"]
       and doge["words"].endswith("; not settled yet"),
       "M third, the late slot: a coin already bought is refused at 20 s and takes the slot at 15 s (pinrun: tau <= "
       "late_extra_tau); open: %s" % doge)
    hype = T3[("HYPE", "Nov 8 4:29 PM ET")]
    ck(hype["usd"] is None and hype["open"] and hype["words"].startswith("a 3rd bet of 15 Yes at 97.0c with 10 s left")
       and hype["words"].endswith("; no result 3 h after the close (unknown)"),
       "M third, unknown: HYPE's full bet is 15 (0.15 x 100); no result 3 h on: %s" % hype)
    ck(M["extra"] == [
        "held back: 2 full buys cut to the 2-bet budget where the old argv had room for a 3rd; the contracts not bought would "
        "have made $1.67 on 1 won, lost $97.96 on 1 flipped",
        "a true 3rd bet, NOT in the net (the old build dropped it too, at its base check): 4 closes hit the budget, 4 would "
        "have gone out (1 had no offer, 1 failed a gate, 1 found the slot taken), won $2.79 on 1, lost $96.27 on 1, so "
        "blocking them saved $93.48 \u00b7 2 open; the 12-08 read reverts B only above $5/day"],
       "M extra: the held-back line and the true-3rd-bet line (ETH no offer, XRP held outside the late window, DOGE in close "
       "A found the slot taken): %s" % M["extra"])
    ck(M["what"] == ("a close spends 2 bets, never a 3rd (--extra-coin 0 --late-extra 0, brake 4.50, the same bet size; the old "
                     "argv allowed one more on a new coin or inside 15 s); the net is what that held back on pin's own buys"),
       "M what, off the start record: %s" % M["what"])
    for e in M["events"] + M["third"]:
        ck("\u2014" not in e["words"], "no em dash in M's words")
    T = F.totals(list(rep.values()))
    ck(T["engaged"] == 24 and T["open"] == 4 and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2),
       "totals take M's net in (15 + 3 + 4 + 2 engagements), never its third list: %s" % T)
    ck(all(rep[k]["third"] == [] for k in "ABCDEFGHIJKL"), "only M carries a third list")
    # helpers: the judge's gates one by one, the fee, the band multiple, the coin and the full bet
    R = F.m_rules(M_START)
    base = dict(ask=0.97, ask_size=50.0, fair=1.0, want="yes", tau=11, held=None)
    ck(F.m_judge(base, R, 100.0, False, 0, CL["A"]) == (50.0, "full", None), "judge: a full leg capped by the book")
    ck(F.m_judge(dict(base, ask=None), R, 100.0, False, 0, CL["A"])[2] == "no offer", "judge: no ask = no offer")
    ck("confidence" in F.m_judge(dict(base, fair=0.99), R, 100.0, False, 0, CL["A"])[2], "judge: fair under PIN")
    ck("already bought" in F.m_judge(dict(base, tau=16), R, 100.0, True, 1, CL["A"])[2]
       and F.m_judge(dict(base, tau=15, held="yes"), R, 100.0, True, 1, CL["A"])[2] is None,
       "judge: a bought coin only inside the late window (15 s)")
    ck("holds 2 buys" in F.m_judge(dict(base, tau=10, held="yes"), R, 100.0, True, 2, CL["A"])[2], "judge: max per market")
    ck("other side" in F.m_judge(dict(base, held="no"), R, 100.0, True, 1, CL["A"])[2], "judge: never both sides")
    ck("over the ceiling" in F.m_judge(dict(base, ask=0.991), R, 100.0, False, 0, CL["A"])[2]
       and F.m_judge(dict(base, ask=0.985), R, 100.0, False, 0, CL["A"]) == (10.0, "band", None)
       and "already held" in F.m_judge(dict(base, ask=0.985, held="yes", tau=10), R, 100.0, True, 1, CL["A"])[2],
       "judge: 99.1c refused, 98.5c a band tenth when nothing is held")
    # (under the live argv the confidence gate and the 98c ceiling imply both floors: a 99.5% side at 98c or less always
    # clears 0.3c of edge and 0.3c of EV; the floors bind only with other numbers)
    ck("edge" in F.m_judge(dict(base, ask=0.97, fair=0.9955), dict(R, edge_floor=0.03), 100.0, False, 0, CL["A"])[2]
       and "EV" in F.m_judge(dict(base, ask=0.979, fair=1.0), dict(R, ev_floor=0.02), 100.0, False, 0, CL["A"])[2]
       and "dump guard" in F.m_judge(dict(base, ask=0.80), R, 100.0, False, 0, CL["A"])[2],
       "judge: the edge floor (2.55c gross - 0.20c fee under a 3c floor), the EV floor (1.05c under 2c), the dump guard at 80c")
    early = F.m_judge(dict(base, tau=40), R, 100.0, False, 0, CL["A"])
    ck(abs(early[0] - 33.3) < 1e-9 and early[1:] == ("early", None)
       and "early look under" in F.m_judge(dict(base, tau=40, ask=0.89), R, 100.0, False, 0, CL["A"])[2]
       and "cheap window" in F.m_judge(base, R, 100.0, False, 0, 1794054600)[2]
       and "a book of 0.50" in F.m_judge(dict(base, ask_size=0.5), R, 100.0, False, 0, CL["A"])[2],
       "judge: the early leg (a third), its 90c floor, the cheap window (a 7:30 AM close), the 1-contract book")
    ck(F.m_fee1(0.96) == 0.0027 and F.m_band_mult(0.965, R) == 1.5 and F.m_band_mult(0.981, R) == 1.0
       and F.m_coin("KXBTCD-26NOV0813-T75699.99") == "KXBTC" and F.m_coin("KXBTC15M-26NOV081300-00") == "KXBTC"
       and F.m_full("KXHYPE15M-26NOV081630-30", 100.0, 10.0, M_START) == 15.0
       and F.m_full("KXBTCD-26NOV0813-T75699.99", 100.0, 10.0, M_START) == 10.0
       and F.m_full("KXETH15M-26NOV081630-30", 100.0, 10.0, M_START) == 100.0, "fee, band multiple, coin, full bet")
    ck(F.traj_paths(r"C:\x\pinrun-live-20261108T210000Z.jsonl") == [r"C:\x\pintraj-live-20261108T210000Z.jsonl",
                                                                       r"C:\x\pintraj-live-20261108T210000Z.jsonl.gz"]
       and F.traj_paths(r"C:\x\archive\pinrun-live-20261108T210000Z.jsonl.gz")[0].endswith("pintraj-live-20261108T210000Z.jsonl")
       and F.traj_paths("other.jsonl") == [], "traj_paths")
    # the old argv's run: the same records under --extra-coin 1 count for nothing (M not live)
    with open(pm, "w", encoding="utf-8") as fh:
        for r in run_m([]):
            if r["kind"] == "start":
                r = dict(r, extra_coin=1.0, late_extra=1.0, bank_brake=3.0)
            fh.write(json.dumps(r) + "\n")
    rep = _report(ps + [pk, pl, pm], now=NOW_M)
    ck(rep["M"]["since"] is None and rep["M"]["engaged"] == 0 and rep["M"]["third"] == [] and rep["M"]["not_live"] == F.M_NOT_LIVE
       == "not live yet (comes with the first pin start on call B)",
       "M: a run on --extra-coin 1 is not live, whatever records it holds")


def test_m_without_a_trajectory_log():
    """No pintraj log next to the pin log: the refusals are counted (no offer seen), nothing is priced, the held-back
    buys still score."""
    d = tempfile.mkdtemp(prefix="fixes-test-")
    pm = write_m(d)
    os.remove(os.path.join(d, "pintraj-live-20261108T210000Z.jsonl"))
    M = _report([pm], now=NOW_M)["M"]
    ck(M["engaged"] == 2 and M["net_usd"] == 96.29 and M["third"] == [], "held-back buys scored, no third bet priced")
    ck(M["extra"][1].startswith("a true 3rd bet, NOT in the net (the old build dropped it too, at its base check): 4 closes hit "
                                "the budget, 0 would have gone out (7 had no offer, 0 failed a gate, 0 found the slot taken), "
                                "won $0.00 on 0, lost $0.00 on 0, so blocking them saved $0.00;"),
       "the line says every refusal went unpriced: %s" % M["extra"][1])


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


NA, NB, NC, ND = 1794181500, 1794182400, 1794183300, 1794184200      # 11-08 6:45 PM, 7:00, 7:15, 7:30 ET closes
NOW_N = 1794184800.0                                                   # 7:40 PM ET: the 7:30 market is 10 min past its close


def run_n(recs):
    """The v-hedgeline60 run (11-08 6:30 PM ET on, --hedge-belief 0.60 in place of 0.40, the 1.25x extra with 11+ s left): N.
    Every $ worked by hand with Kalshi's fee ceil(7 x p x (1 - p) x n) / 100 per fill."""
    recs += [
        _r("start", _ts(NA - 900), code_sha="d51b131b55cf", hedge_belief=0.6, hedge_panic=0.4, hedge_odds_mult=1.25,
           hedge_odds_min_tau=11.0, hedge_jump=None, hedge_jump_shadow=6.0, hedge_jump_max=8.0, jump_hedge_min_ask=0.05,
           cheap_window=[6.0, 10.0, 0.98], max_positions=5, boost_rail="off", hedge_tick="round", ws_later_fall_c=10.0,
           extra_coin=0.0, late_extra=0.0, size=100.0),
        # N1, FLIP (XRP 6:45 PM): belief 0.57 with 26 s left, 100 No at 40c + the 25 extra; the 0.40 line would have fired
        # with 9 s left at 66c (no extra under 11 s). Flip: live 100 x 0.60 - fee 1.68 + 25 x 0.60 - fee 0.42 = 72.90;
        # 0.40's 100 x 0.34 - fee 1.58 = 32.42; the earlier line saved 40.48
        _r("hedge", _ts(NA - 26), ticker="KXXRP15M-26NOV081845-45", close_s=NA, side="no", price=0.40, n=100.0, asked=100.0,
           ask=0.40, ask_size=400.0, limit_sent=0.50, entry=0.972, tau=26, belief=0.5712, status="executed", live=True),
        _r("hedge_extra", _ts(NA - 26), ticker="KXXRP15M-26NOV081845-45", close_s=NA, side="no", price=0.40, n=25.0,
           asked=25.0, extra_of=25.0, mult=1.25, min_tau=11.0, base_n=100.0, tau=26, belief=0.5712, trigger="belief",
           status="executed", live=True),
        _r("settled", _ts(NA + 20), ticker="KXXRP15M-26NOV081845-45", want="yes", result="no", cost=0.972, pnl_c=-9720.0),
        _r("settled", _ts(NA + 20), ticker="KXXRP15M-26NOV081845-45", want="no", result="no", cost=0.40, pnl_c=7290.0),
        # N2, WON (SOL 7:00 PM, we hold No): belief 0.55 with 20 s left, 50 Yes at 30c + the 12.5 extra; belief then went
        # back up and the 0.40 line would never have fired. Won: live paid 15.00 + fee 0.74 + 3.75 + fee 0.19 = 19.68 for
        # nothing; the earlier line cost 19.68
        _r("hedge", _ts(NB - 20), ticker="KXSOL15M-26NOV081900-00", close_s=NB, side="yes", price=0.30, n=50.0, asked=50.0,
           ask=0.30, ask_size=90.0, limit_sent=0.40, entry=0.97, tau=20, belief=0.55, status="executed", live=True),
        _r("hedge_extra", _ts(NB - 20), ticker="KXSOL15M-26NOV081900-00", close_s=NB, side="yes", price=0.30, n=12.5,
           asked=12.5, extra_of=12.5, mult=1.25, min_tau=11.0, base_n=50.0, tau=20, belief=0.55, trigger="belief",
           status="executed", live=True),
        _r("settled", _ts(NB + 20), ticker="KXSOL15M-26NOV081900-00", want="no", result="no", cost=0.97, pnl_c=150.0),
        _r("settled", _ts(NB + 20), ticker="KXSOL15M-26NOV081900-00", want="yes", result="no", cost=0.30, pnl_c=-1968.0),
        # N3, FLIP with the old line's extra (ETH 7:00 PM): belief 0.58 with 25 s left, 80 No at 35c + 20 extra; the 0.40
        # line would have fired with exactly 11 s left (the extra's floor) at 50c WITH its 20 extra. Flip: live 80 x 0.65 - 1.28 + 20 x 0.65 - 0.32 =
        # 63.40; 0.40's 80 x 0.50 - 1.40 + 20 x 0.50 - 0.35 = 48.25; saved 15.15
        _r("hedge", _ts(NB - 25), ticker="KXETH15M-26NOV081900-00", close_s=NB, side="no", price=0.35, n=80.0, asked=80.0,
           ask=0.35, ask_size=200.0, limit_sent=0.45, entry=0.975, tau=25, belief=0.58, status="executed", live=True),
        _r("hedge_extra", _ts(NB - 25), ticker="KXETH15M-26NOV081900-00", close_s=NB, side="no", price=0.35, n=20.0,
           asked=20.0, extra_of=20.0, mult=1.25, min_tau=11.0, base_n=80.0, tau=25, belief=0.58, trigger="belief",
           status="executed", live=True),
        _r("settled", _ts(NB + 20), ticker="KXETH15M-26NOV081900-00", want="yes", result="no", cost=0.975, pnl_c=-7800.0),
        _r("settled", _ts(NB + 20), ticker="KXETH15M-26NOV081900-00", want="no", result="no", cost=0.35, pnl_c=6340.0),
        # not counted: a hedge fired at belief 0.33 (both lines fire; BNB 7:15 PM), and a hedge that did not fill
        _r("hedge", _ts(NC - 10), ticker="KXBNB15M-26NOV081915-15", close_s=NC, side="no", price=0.64, n=100.0, asked=100.0,
           ask=0.64, ask_size=400.0, limit_sent=0.74, entry=0.97, tau=10, belief=0.33, status="executed", live=True),
        _r("settled", _ts(NC + 20), ticker="KXBNB15M-26NOV081915-15", want="yes", result="no", cost=0.97, pnl_c=-9700.0),
        _r("settled", _ts(NC + 20), ticker="KXBNB15M-26NOV081915-15", want="no", result="no", cost=0.64, pnl_c=3300.0),
        _r("hedge", _ts(NC - 12), ticker="KXNEAR15M-26NOV081915-15", close_s=NC, side="no", price=0.45, n=0.0, asked=60.0,
           status=None, order_id=None, live=True),
        # N4, OPEN (DOGE 7:30 PM): belief 0.50 with 15 s left, 40 Yes at 35c; no settled record yet at NOW_N (pending)
        _r("hedge", _ts(ND - 15), ticker="KXDOGE15M-26NOV081930-30", close_s=ND, side="yes", price=0.35, n=40.0, asked=40.0,
           ask=0.35, ask_size=100.0, limit_sent=0.45, entry=0.96, tau=15, belief=0.50, status="executed", live=True),
    ]
    return recs


def traj_n(recs):
    """The trajectory log of run_n's closes, one record a second a market: fair is the probability of the row's want."""
    def tj(tk, cs, tau, want, fair, ask, opp_ask):
        return _r("traj", _ts(cs - tau), ticker=tk, close_s=cs, tau=tau, want=want, held=want, fair=fair, conf=fair,
                  spot=1.0, strike=1.0, eff_strike=1.0, ask=ask, ask_size=100.0, opp_ask=opp_ask, opp_size=400.0,
                  gate="held", near=True)
    for tau in range(30, -1, -1):          # XRP: belief (want yes) 0.57, then 0.30 from 9 s; the No ask 40c, then 66c
        recs.append(tj("KXXRP15M-26NOV081845-45", NA, tau, "yes", 0.57 if tau >= 10 else 0.30, 0.60 if tau >= 10 else 0.34,
                       0.40 if tau >= 10 else 0.66))
    for tau in range(30, -1, -1):          # SOL (want no): 0.55, back to 0.95 from 15 s: never under 0.40
        recs.append(tj("KXSOL15M-26NOV081900-00", NB, tau, "no", 0.55 if tau >= 16 else 0.95, 0.60, 0.30 if tau >= 16 else 0.05))
    for tau in range(30, -1, -1):          # ETH (want yes): 0.58, then 0.35 from 11 s; the No ask 35c, then 50c
        recs.append(tj("KXETH15M-26NOV081900-00", NB, tau, "yes", 0.58 if tau >= 12 else 0.35, 0.65 if tau >= 12 else 0.50,
                       0.35 if tau >= 12 else 0.50))
    for tau in range(30, -1, -1):          # BNB: under the old line already (not counted either way)
        recs.append(tj("KXBNB15M-26NOV081915-15", NC, tau, "yes", 0.33, 0.36, 0.64))
    return recs


def write_n(d):
    pn = os.path.join(d, "pinrun-live-20261108T233000Z.jsonl")
    with open(pn, "w", encoding="utf-8") as fh:
        for r in run_n([]):
            fh.write(json.dumps(r) + "\n")
    with open(os.path.join(d, "pintraj-live-20261108T233000Z.jsonl"), "w", encoding="utf-8") as fh:
        for r in traj_n([]):
            fh.write(json.dumps(r) + "\n")
    return pn


def test_n_hedge_line():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    pn = write_n(d)
    rep = _report([pn], now=NOW_N)
    n = rep["N"]
    ck(n["name"] == "hedge line 0.60" and n["since"] == "Nov 8 6:30 PM ET" and n["not_live"] is None,
       "N starts at the first start record with hedge_belief 0.60: %s" % n["since"])
    ck("fires under 0.60 (was 0.40)" in n["what"], "N's words off the start record: %s" % n["what"])
    ck(n["engaged"] == 4 and n["open"] == 1, "N: 4 hedges fired between the lines (1 open), the 0.33 hedge and the unfilled "
       "one not counted: engaged %s open %s" % (n["engaged"], n["open"]))
    ev = {e["coin"]: e for e in n["events"]}
    ck(sorted(ev) == ["DOGE", "ETH", "SOL", "XRP"], "N's events by coin: %s" % sorted(ev))
    ck(ev["XRP"]["usd"] == 40.48 and "bought 100 No at 40.0c" in ev["XRP"]["words"]
       and "0.40 line would have bought at 66.0c with 9 s left" in ev["XRP"]["words"]
       and "FLIPPED: the hedge got back $72.90, the 0.40 line's $32.42, so the earlier line saved $40.48" in ev["XRP"]["words"],
       "N1 flip, no extra under 11 s at the old line: %s" % ev["XRP"]["words"])
    ck(ev["SOL"]["usd"] == -19.68 and "0.40 line would never have fired" in ev["SOL"]["words"]
       and "the bet won: the hedge paid $19.68, the 0.40 line's nothing, so the earlier line cost $19.68" in ev["SOL"]["words"],
       "N2 recovered, the old line never fires: %s" % ev["SOL"]["words"])
    ck(ev["ETH"]["usd"] == 15.15 and "0.40 line would have bought at 50.0c with 11 s left" in ev["ETH"]["words"]
       and "got back $63.40, the 0.40 line's $48.25, so the earlier line saved $15.15" in ev["ETH"]["words"],
       "N3 flip, the old line's extra priced at its own ask: %s" % ev["ETH"]["words"])
    ck(ev["DOGE"]["usd"] is None and ev["DOGE"]["open"], "N4 open: no $ yet")
    ck(n["net_usd"] == 35.95, "N net = 40.48 - 19.68 + 15.15: %s" % n["net_usd"])
    ck(n["extra"][0] == "saved $55.63 on 2 flips hedged earlier · paid $19.68 on 1 bet that recovered · 1 still open",
       "N's first line: %s" % n["extra"][0])
    ck(n["extra"][1].startswith("not counted: 1 hedge fired at or under 0.40 (both lines the same); 2 of the counted would "
                                "never have been hedged at 0.40; the 11-22 read"), "N's second line: %s" % n["extra"][1])
    tot = F.totals(rep.values())
    ck(abs(tot["net_usd"] - sum(c["net_usd"] for c in rep.values() if c["id"] != "J")) < 0.005 and tot["engaged"] >= 4,
       "N is in the totals (real money)")
    # the other changes are live (the start record carries their flags) with nothing to count
    ck(rep["L"]["since"] and rep["L"]["engaged"] == 0 and rep["M"]["since"] and rep["M"]["engaged"] == 0
       and rep["K"]["since"] and rep["K"]["engaged"] == 0, "K, L, M live on the same start record, nothing counted")
    # before the line moved: N is not live
    d2 = tempfile.mkdtemp(prefix="fixes-test-")
    rep2 = _report(write_logs(d2))
    ck(rep2["N"]["since"] is None and rep2["N"]["not_live"] == F.N_NOT_LIVE and rep2["N"]["engaged"] == 0,
       "N before --hedge-belief 0.60: not live, its own words")


# ---- v-oddsmult15 (2026-11-14): C's 1.25x -> 1.5x step -------------------------------------------------------------
NOW_C15 = 1794744000.0             # 2026-11-15T12:00:00Z = 7:00 AM ET (the 6:15 AM market is 45 min past its close)


def _x15(t, tk, side, orig, n, price, mult=1.5, **kw):
    """A filled extra leg as pinrun logs it (patch_oddsmult: extra_of = (mult - 1) x orig_n, n = what filled)."""
    kw.setdefault("status", "executed")
    return _r("hedge_extra", t, ticker=tk, side=side, price=price, n=n, asked=round((mult - 1) * orig, 2),
              extra_of=round((mult - 1) * orig, 2), mult=mult, min_tau=11.0, base_n=orig, orig_n=orig, tau=15,
              belief=0.3, trigger="belief", trigger_label="belief", fired_on_belief=True, order_id="x15-" + tk[2:6],
              live=True, **kw)


def run_c15(recs):
    """The --hedge-odds-mult 1.5 run (11-15 5:00 AM ET on): C's step. Every $ worked by hand with Kalshi's fee ceil(7 x p
    x (1 - p) x n) / 100: the step is filled - 0.25 x orig_n, at the leg's dearest fills (its `fills`), else at its
    order's limit_sent (real records carry only the average price: the limit is the conservative bound)."""
    recs += [
        _r("start", "2026-11-15T10:00:00Z", code_sha="15151515aaaa", hedge_odds_mult=1.5, hedge_odds_min_tau=11.0,
           max_positions=5, boost_rail="off", hedge_tick="round", jump_hedge_min_ask=0.05),
        # ZEC FLIP: 40 Yes at 30c on 80 (1.25x bought 20), limit 33c: the step's 20 at the LIMIT, 20 x 67c - fee 0.31 =
        # +13.09 (at the 30c average it would read 14.00 - 0.30 = +13.70); C's whole leg 28.00 - fee 0.59 = +27.41
        _x15("2026-11-15T10:14:45Z", "KXZEC15M-26NOV150515-15", "yes", 80.0, 40.0, 0.30, limit_sent=0.33),
        _r("settled", "2026-11-15T10:15:20Z", ticker="KXZEC15M-26NOV150515-15", want="no", result="yes", cost=0.97,
           pnl_c=-7760.0),
        # ETH, the OLD multiple in the same run: C counts it (10 x 70c - 0.15 = +6.85), the step does not
        _x15("2026-11-15T10:14:46Z", "KXETH15M-26NOV150515-15", "yes", 40.0, 10.0, 0.30, mult=1.25, limit_sent=0.32),
        _r("settled", "2026-11-15T10:15:21Z", ticker="KXETH15M-26NOV150515-15", want="no", result="yes", cost=0.97,
           pnl_c=-3880.0),
        # SOL, the bet WON: 50 No at 20c on 100 (1.25x bought 25), limit 22c: the step's 25 x 22c + fee 0.31 = -5.81 (at
        # the average: -5.28); C's leg -10.56
        _x15("2026-11-15T10:29:45Z", "KXSOL15M-26NOV150530-30", "no", 100.0, 50.0, 0.20, limit_sent=0.22),
        _r("settled", "2026-11-15T10:30:20Z", ticker="KXSOL15M-26NOV150530-30", want="yes", result="yes", cost=0.97,
           pnl_c=300.0),
        # BNB FLIP with its fills listed (10 at 20c, 10 at 30c; average 25c) on 40 (1.25x bought 10): the step is the
        # DEAREST 10 at 30c: 7.00 - fee 0.15 = +6.85 (at the 25c average it would read 7.50 - 0.14 = +7.36; the listed
        # fills cover the step, so its 32c limit is not used); C's leg 20 x 75c - fee 0.27 = +14.73
        _x15("2026-11-15T10:44:45Z", "KXBNB15M-26NOV150545-45", "yes", 40.0, 20.0, 0.25, fills=[[10.0, 0.20], [10.0, 0.30]],
             limit_sent=0.32),
        _r("settled", "2026-11-15T10:45:20Z", ticker="KXBNB15M-26NOV150545-45", want="no", result="yes", cost=0.97,
           pnl_c=-3880.0),
        # XRP: the book filled 12 of the 30 asked on 60 -- no more than 1.25x's 15, so no step (C's leg 7.20 - 0.21 = +6.99)
        _x15("2026-11-15T10:59:45Z", "KXXRP15M-26NOV150600-00", "no", 60.0, 12.0, 0.40, limit_sent=0.42),
        _r("settled", "2026-11-15T11:00:20Z", ticker="KXXRP15M-26NOV150600-00", want="yes", result="no", cost=0.97,
           pnl_c=-5820.0),
        # DOGE, OPEN: 20 Yes at 35c on 40, the market not settled at NOW_C15 (the step: 10 contracts, no $ yet)
        _x15("2026-11-15T11:14:45Z", "KXDOGE15M-26NOV150615-15", "yes", 40.0, 20.0, 0.35, limit_sent=0.37),
        # a 1.5x leg that did not fill is no fire
        _x15("2026-11-15T11:14:46Z", "KXHYPE15M-26NOV150615-15", "yes", 40.0, 0.0, 0.35, status=None, limit_sent=0.37),
    ]
    return recs


def _write(d, name, recs, compact=False):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write((json.dumps(r, separators=(",", ":")) if compact else json.dumps(r)) + "\n")
    return p


def test_c_step_oddsmult15():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    p = _write(d, "pinrun-live-20261115T100000Z.jsonl", run_c15([]))
    rep = _report([p], now=NOW_C15)
    C = rep["C"]
    ck(C["engaged"] == 6 and C["open"] == 1 and C["net_usd"] == 45.42,
       "C keeps its total over every filled extra leg (1.5x and 1.25x): 27.41 + 6.85 - 10.56 + 14.73 + 6.99 = 45.42, "
       "DOGE open: %s" % {x: C[x] for x in ("engaged", "open", "net_usd")})
    ck(C["extra"] == ["of which the 1.25x->1.5x step: +$14.13 on 3 fires, 2 priced at the limit, a conservative bound (55 "
                      "contracts over the 1.25x share: 2 flips it paid on, 1 won bet it cost) \u00b7 1 filled no more than "
                      "1.25x would have \u00b7 1 open"],
       "C's step line: 13.09 - 5.81 + 6.85 = +14.13 on ZEC, SOL (at their limits: no per-fill prices) and BNB (its "
       "dearest listed fills); XRP no step, DOGE open, ETH (1.25x) and the unfilled HYPE leg not in it: %s" % C["extra"])
    ck(C["what"] == "1.50x extra contracts of the hedge side when pin's odds line fires with 11+ s left",
       "C's what reads the new multiple off the start record: %s" % C["what"])
    w = {e["coin"]: e["words"] for e in C["events"]}
    ck(w["ZEC"] == ("it bought 40 EXTRA Yes at about 30.0c (1.50x the position at the odds line) with 15 s left: MADE "
                    "$27.41; the 1.25x->1.5x step: 20 of those contracts, +$13.09 at the limit"),
       "C's 1.5x event names its step, priced at the limit: %s" % w["ZEC"])
    ck(w["BNB"].endswith("; the 1.25x->1.5x step: 10 of those contracts, +$6.85")
       and w["SOL"].endswith("; the 1.25x->1.5x step: 25 of those contracts, -$5.81 at the limit")
       and w["XRP"].endswith("; the 1.25x->1.5x step: none (it filled no more than 1.25x would have)")
       and w["DOGE"].endswith("not settled yet; the 1.25x->1.5x step: 10 of those contracts")
       and "step" not in w["ETH"], "the step on each 1.5x event, none on the 1.25x one: %s" % w)
    # the step is never priced better than reality: each settled step reads no more than at the leg's average price
    # (where the old code priced it: +13.70 - 5.28 + 6.85 = +15.27), on a flip and on a won bet alike
    won = {"KXZEC15M-26NOV150515-15": True, "KXSOL15M-26NOV150530-30": False, "KXBNB15M-26NOV150545-45": True}
    legs = [r for r in run_c15([]) if r.get("kind") == "hedge_extra" and r["ticker"] in won and F.c_is_step(r)]
    ck(len(legs) == 3 and all(F._rw.value(F.c_step_fills(r, F.c_step_n(r)), won[r["ticker"]])
                              < F._rw.value([(F.c_step_n(r), r["price"])], won[r["ticker"]]) for r in legs),
       "each settled step reads under its average-price figure (the dearest fills, else the limit)")
    # the helpers: the position, the step, the dearest fills, else the limit, else nothing
    x = run_c15([])[7]
    ck(F.c_position(x) == 40.0 and F.c_step_n(x) == 10.0 and F.c_step_fills(x, 10.0) == [(10.0, 0.30)]
       and F.c_step_priced(x, 10.0) == ([(10.0, 0.30)], "fills")
       and F.c_step_priced(dict(x, fills=None), 10.0) == ([(10.0, 0.32)], "limit")
       and F.c_step_fills(dict(x, fills=None), 10.0) == [(10.0, 0.32)]
       and F.c_step_priced(dict(x, fills=[[4.0, 0.31]]), 10.0) == ([(4.0, 0.31), (6.0, 0.32)], "limit")
       and F.c_step_priced(dict(x, fills=None, limit_sent=None), 10.0) == ([], None)
       and F.c_step_priced(dict(x, fills=None, limit_sent=0.20), 10.0) == ([(10.0, 0.25)], "limit")
       and F.c_step_limit({"limit_sent": 0.2, "price": 0.25}) == 0.25 and F.c_step_limit({"limit_sent": 0.0}) is None
       and F.c_step_fills(dict(x, fills=[{"count": 4, "price": 0.31}, {"n": 16, "p": 0.24}]), 10.0) == [(4.0, 0.31), (6.0, 0.24)]
       and F.c_position({"mult": 1.5, "extra_of": 30.0}) == 60.0 and F.c_position({"base_n": 8.0}) == 8.0
       and F.c_step_n({"n": 12.0, "orig_n": 60.0}) == 0.0 and F.c_is_step({"mult": 1.5}) and not F.c_is_step({"mult": 1.25}),
       "c_position (orig_n, else extra_of / (mult - 1), else base_n), c_step_n, c_step_priced (dearest listed fills "
       "first, the rest at the limit -- never under the average --, else not priced), c_is_step")
    # a 1.5x leg with no fills list and no limit is NOT priced: said on the line and on its event, never read as $0
    recs = run_c15([])
    recs[1] = {k_: v_ for k_, v_ in recs[1].items() if k_ != "limit_sent"}                  # ZEC
    pU = _write(d, "pinrun-live-20261115T100000Z.jsonl", recs)
    CU = _report([pU], now=NOW_C15)["C"]
    wU = {e["coin"]: e["words"] for e in CU["events"]}
    ck(CU["extra"] == ["of which the 1.25x->1.5x step: +$1.04 on 2 fires, 1 priced at the limit, a conservative bound, "
                       "1 more NOT PRICED (no fills or limit on the record) (35 contracts over the 1.25x share: 1 flip it "
                       "paid on, 1 won bet it cost) \u00b7 1 filled no more than 1.25x would have \u00b7 1 open"]
       and wU["ZEC"].endswith("; the 1.25x->1.5x step: 20 of those contracts, NOT PRICED (no fills or limit on the record)")
       and CU["net_usd"] == C["net_usd"],
       "an unpriced step leg is said, not counted as $0 (C's own total unchanged): %s | %s" % (CU["extra"], wU["ZEC"]))
    # live with nothing filled yet: the line says so
    p2 = _write(d, "pinrun-live-20261115T100000Z.jsonl", run_c15([])[:1])
    C2 = _report([p2], now=NOW_C15)["C"]
    ck(C2["extra"] == ["of which the 1.25x->1.5x step: none yet (no 1.5x extra leg has filled since Nov 15 5:00 AM ET)"],
       "C's step before any 1.5x leg fills: %s" % C2["extra"])
    T = F.totals(list(rep.values()))
    ck(T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2),
       "the step is inside C's total, never added again: %s" % T)


# ---- v-ladder-rail100 (2026-11-14): O, the ladder's bids the old 82% rail would have refused ------------------------
NOW_O = 1794744000.0               # 2026-11-15T12:00:00Z = 7:00 AM ET (the 6:45 AM ladder market: 15 min past its close)
O_ARGV82 = ["--subaccount", "1", "--live", "--auto-size", "--market-cap-x", "2", "--levels", "0", "--coins",
            "KXNEAR15M,KXZEC15M,KXDOGE15M,KXHYPE15M,KXXRP15M", "--fit", "--commit-frac", "0.82", "--big-coins-above",
            "7000", "--minutes", "10080"]
O_ARGV100 = ["--subaccount", "1", "--live", "--auto-size", "--market-cap-x", "2", "--levels", "0", "--coins",
             "KXNEAR15M,KXZEC15M,KXDOGE15M,KXHYPE15M,KXXRP15M", "--pot-per-contract", "5.9756", "--commit-frac", "1.0",
             "--minutes", "10080"]


def _ev(ev, t, **kw):
    r = {"t": t, "ev": ev}
    r.update(kw)
    return r


def _lad_start(t, argv, frac, pot=1338.6325):
    return _ev("start", t, pid=4232, subaccount=1, live=True, sub_balance=pot, auto_size=True, pot=pot,
               auto={"pot_per_contract": 5.9756 if frac >= 1.0 else 14.0, "commit_frac": frac}, argv=argv,
               old_limit=round(0.82 * pot, 2), rails={"size": 224, "max_commit": round(frac * pot, 2)})


def _old_code_start(t, pot=1338.6325):
    """A start record of the ladder code BEFORE v-ladder-rail100 tracking, run on the 100% argv: auto.commit_frac 1.0 but
    no argv and no old_limit (that code wrote neither, and never marks a bid over_82)."""
    return _ev("start", t, pid=5150, subaccount=1, live=True, sub_balance=pot, auto_size=True, pot=pot,
               auto={"pot_per_contract": 5.9756, "commit_frac": 1.0}, rails={"size": 224, "max_commit": round(pot, 2)})


def _placed(t, tk, pid, side, over):
    return _ev("placed", t, body={"ticker": tk, "side": "bid" if side == "yes" else "ask", "count": "224.00",
                                  "price": "0.9800" if side == "yes" else "0.0200", "post_only": True,
                                  "client_order_id": "lad-%d" % pid, "subaccount": 1, "exchange_index": 2},
               order_id="k-%d" % pid, resp="{}", over_82=over, old_limit=1097.68)


def _fill(t, tk, pid, side, delta, filled, over):
    return _ev("live_fill", t, ticker=tk, paper_id=pid, kid="k-%d" % pid, side=side, px="0.9800", delta=delta,
               filled=filled, over_82=over)


def _settle(t, tk, side, result, n):
    cost = round(0.98 * n, 4)
    return _ev("live_settle", t, ticker=tk, result=result, side=side, n=n, cost=cost,
               pnl=round((n - cost) if side == result else -cost, 4), day_pnl=0.0)


def run_o(recs, with_rail100=True):
    """The ladder's order log: a day on the 82% rail, then (with_rail100) the restart on --commit-frac 1.0 at 4:50 AM
    ET 11-15. Each market's money is its live_settle pnl (no fee: the ladder's bids are post_only makers); an over-82
    bid's share is pnl x its contracts / the market's."""
    NEAR, ZEC = "KXNEAR15M-26NOV150500-00", "KXZEC15M-26NOV150515-15"
    DOGE, HYPE, XRP = "KXDOGE15M-26NOV150530-30", "KXHYPE15M-26NOV150645-45", "KXXRP15M-26NOV150515-15"
    recs += [
        _lad_start("2026-11-14T10:00:14.128Z", O_ARGV82, 0.82),
        # the 82% days: a fill and its settle before the restart count for nothing
        _placed("2026-11-14T13:59:31.000Z", "KXZEC15M-26NOV140900-00", 339, "no", False),
        _fill("2026-11-14T13:59:49.326Z", "KXZEC15M-26NOV140900-00", 339, "no", 224, 224, False),
        _settle("2026-11-14T14:00:23.357Z", "KXZEC15M-26NOV140900-00", "no", "no", 224),
    ]
    if not with_rail100:
        return recs
    recs += [
        _lad_start("2026-11-15T09:50:00.000Z", O_ARGV100, 1.0),
        # NEAR 5:00 AM: its first bid fills 224 (an old-world bid), the re-bid is the 6th of the close (over 82%) and
        # fills 224 too; the market WON: pnl 448 - 439.04 = +8.96, the over-82 share 224 / 448 = +4.48
        _placed("2026-11-15T09:59:31.000Z", NEAR, 1001, "yes", False),
        _fill("2026-11-15T09:59:40.000Z", NEAR, 1001, "yes", 224, 224, False),
        _placed("2026-11-15T09:59:42.000Z", NEAR, 1002, "yes", True),
        _fill("2026-11-15T09:59:50.000Z", NEAR, 1002, "yes", 224, 224, True),
        _settle("2026-11-15T10:00:30.000Z", NEAR, "yes", "yes", 448),
        # ZEC 5:15 AM: the same shape, and the market LOST: -439.04, the over-82 share -219.52; XRP's over-82 bid in the
        # same close never filled (placed, no money)
        _placed("2026-11-15T10:14:31.000Z", ZEC, 1011, "no", False),
        _fill("2026-11-15T10:14:40.000Z", ZEC, 1011, "no", 224, 224, False),
        _placed("2026-11-15T10:14:42.000Z", ZEC, 1012, "no", True),
        _fill("2026-11-15T10:14:50.000Z", ZEC, 1012, "no", 224, 224, True),
        _placed("2026-11-15T10:14:52.000Z", XRP, 1013, "yes", True),
        _settle("2026-11-15T10:15:30.000Z", ZEC, "no", "yes", 448),
        # DOGE 5:30 AM: the old-world bid 124 of 224 filled, the over-82 re-bid 100 (two fills: 60 then 40); WON: pnl
        # 224 - 219.52 = +4.48, the over-82 share 100 / 224 = +2.00
        _placed("2026-11-15T10:29:31.000Z", DOGE, 1021, "yes", False),
        _fill("2026-11-15T10:29:40.000Z", DOGE, 1021, "yes", 124, 124, False),
        _placed("2026-11-15T10:29:42.000Z", DOGE, 1022, "yes", True),
        _fill("2026-11-15T10:29:50.000Z", DOGE, 1022, "yes", 60, 60, True),
        _fill("2026-11-15T10:29:52.000Z", DOGE, 1022, "yes", 40, 100, True),
        _settle("2026-11-15T10:30:30.000Z", DOGE, "yes", "yes", 224),
        # HYPE 6:45 AM: an over-82 bid filled 50, the market not settled at NOW_O: open
        _placed("2026-11-15T11:44:42.000Z", HYPE, 1031, "no", True),
        _fill("2026-11-15T11:44:50.000Z", HYPE, 1031, "no", 50, 50, True),
    ]
    return recs


def test_o_ladder_rail100():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    pl = _write(d, "ladder-live-orders.jsonl", run_o([]), compact=True)   # ladder_live's own (compact) JSON
    rep = _report(ps + [pl], now=NOW_O)
    ck("".join(sorted(rep)) == F.IDS + F.LADDER_IDS, "a ladder order log adds the O row after A..N: %s" % sorted(rep))
    O = rep["O"]
    ck(O["name"] == "ladder cash limit 100%" and O["since"] == "Nov 15 4:50 AM ET" and O["not_live"] is None,
       "O since the first ladder start whose argv has --commit-frac 1.0 (not the 0.82 one): %s" % O["since"])
    ck(O["engaged"] == 4 and O["open"] == 1 and O["net_usd"] == -213.04,
       "O: 4 over-82 bids filled (1 open): +4.48 - 219.52 + 2.00 = -213.04: %s" % {x: O[x] for x in ("engaged", "open", "net_usd")})
    ck(O["extra"] == ["the bids the old 82% limit would have refused: -$213.04 on 3 bids (2 won, 1 lost) since Nov 15 "
                      "4:50 AM ET \u00b7 1 open",
                      "5 bids placed past the old limit, 4 filled (548 contracts settled); a bid that never filled cost nothing"],
       "O's plain line and the placed / filled line: %s" % O["extra"])
    w = {e["coin"]: e for e in O["events"]}
    ck(w["NEAR"]["usd"] == 4.48 and w["NEAR"]["words"] == (
        "a bid the old 82% limit would have refused: 224 Yes at 98.0c filled (224 of the 448 contracts the market filled: "
        "that share of its +$8.96); it won, so it made $4.48") and w["NEAR"]["et"] == "Nov 15 4:59 AM ET",
       "O won: half of the market's +8.96: %s" % w["NEAR"])
    ck(w["ZEC"]["usd"] == -219.52 and "it LOST, so it cost $219.52" in w["ZEC"]["words"], "O lost: %s" % w["ZEC"])
    ck(w["DOGE"]["usd"] == 2.0 and "100 Yes at 98.0c filled (100 of the 224 contracts the market filled" in w["DOGE"]["words"],
       "O's share: two fills of one bid make one event, 100 / 224 of +4.48 = +2.00: %s" % w["DOGE"])
    ck(w["HYPE"]["usd"] is None and w["HYPE"]["open"] and w["HYPE"]["words"].endswith("; not settled yet")
       and "XRP" not in w, "O open until its market settles; the unfilled XRP bid is no event: %s" % w["HYPE"])
    ck(O["what"].startswith("the ladder may rest bids up to 100% of its pot (was 82%"), "O what: %s" % O["what"])
    T = F.totals(list(rep.values()))
    ck(T["engaged"] == 19 and T["open"] == 3
       and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2),
       "totals take O in (15 + 4 engagements; the ladder's real money): %s" % T)
    for e in O["events"]:
        ck("\u2014" not in e["words"], "no em dash in O's words")
    # the log grows: only the new bytes are read (the scan is kept), and a new settled over-82 bid moves the line
    F._CACHE.clear()
    F.report(paths=[pl], now=NOW_O)
    sc = F._CACHE[("ladder", pl)]
    pos = sc.pos
    with open(pl, "a", encoding="utf-8") as fh:
        for r in (_settle("2026-11-15T11:45:30.000Z", "KXHYPE15M-26NOV150645-45", "no", "no", 50),):
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        fh.write('{"t":"2026-11-15T11:46:00.000Z","ev":"live_fi')          # a line still being written: waits
    O2 = _by_id(F.report(paths=[pl], now=NOW_O))["O"]
    ck(F._CACHE[("ladder", pl)] is sc and sc.pos > pos and O2["open"] == 0 and O2["net_usd"] == -212.04
       and O2["extra"][0] == "the bids the old 82% limit would have refused: -$212.04 on 4 bids (3 won, 1 lost) since "
                             "Nov 15 4:50 AM ET",
       "O reads only what the log grew by: HYPE settles +1.00 (50 - 49.00) -> -212.04 on 4 bids: %s" % O2["extra"])
    # rewritten shorter (another log in its place): read afresh
    _write(d, "ladder-live-orders.jsonl", run_o([], with_rail100=False), compact=True)
    O3 = _by_id(F.report(paths=[pl], now=NOW_O))["O"]
    ck(O3["since"] is None and O3["engaged"] == 0 and O3["not_live"] == F.O_NOT_LIVE and "not live yet" in O3["not_live"],
       "O before the restart on --commit-frac 1.0 (only the 0.82 start): not live, its own words: %s" % O3["not_live"])


def test_o_none_yet_and_helpers():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    pl = _write(d, "ladder-live-orders.jsonl", run_o([], with_rail100=False) + [_lad_start("2026-11-15T09:50:00.000Z",
                                                                                           O_ARGV100, 1.0)])
    O = _report([pl], now=NOW_O)["O"]
    ck(O["since"] == "Nov 15 4:50 AM ET" and O["engaged"] == 0 and O["net_usd"] == 0.0
       and O["extra"] == ["the bids the old 82% limit would have refused: none yet since Nov 15 4:50 AM ET"],
       "O live with no over-82 bid yet reads 'none yet': %s" % O["extra"])
    ck(F.o_rail100({"argv": ["--commit-frac", "1.0"]}) and F.o_rail100({"argv": ["--commit-frac=1"]})
       and not F.o_rail100({"argv": ["--commit-frac", "0.82"], "auto": {"commit_frac": 1.0}})
       and F.o_rail100({"auto": {"commit_frac": 1.0}}) and not F.o_rail100({"auto": {"commit_frac": 0.82}})
       and not F.o_rail100({"argv": ["--fit"]}) and not F.o_rail100(None),
       "o_rail100: the argv's --commit-frac first, else the auto block's commit_frac")
    ck(F.is_ladder_log(r"C:\x\ladder-live-orders.jsonl") and not F.is_ladder_log(r"C:\x\ladder-live.jsonl")
       and not F.is_ladder_log(r"C:\x\pinrun-live-20261115T100000Z.jsonl"), "is_ladder_log")
    ck(F.o_tracked(_lad_start("2026-11-15T09:50:00.000Z", O_ARGV100, 1.0))
       and F.o_tracked({"argv": [], "old_limit": None}) and not F.o_tracked(_old_code_start("2026-11-15T09:50:00.000Z"))
       and not F.o_tracked({"argv": O_ARGV100}) and not F.o_tracked(None),
       "o_tracked: the marking code's start record carries argv and old_limit; the older code's carries neither")
    with _kit.sandbox() as td:
        write_logs(td)
        ck("O" not in _report(), "no ladder log in RESULTS: no O row")
        _write(td, "ladder-live-orders.jsonl", run_o([]), compact=True)
        rep = _report(now=NOW_O)
        ck(rep["O"]["net_usd"] == -213.04 and rep["A"]["net_usd"] == 35.61,
           "report() reads RESULTS' ladder-live-orders.jsonl for O next to pin's logs: %s" % rep["O"]["net_usd"])


def test_o_untracked_is_a_problem():
    """The 100% argv started on the OLDER ladder code (auto.commit_frac 1.0, no argv / old_limit: it never marks a bid):
    O must not read 'none yet' forever -- it says ON THE 100% RAIL BUT NOT TRACKED as its problem, counted by totals();
    once the marking code starts, the problem goes and the untracked hours stay said under the net."""
    d = tempfile.mkdtemp(prefix="fixes-test-")
    base = run_o([], with_rail100=False) + [_old_code_start("2026-11-15T09:50:00.000Z"),
                                            # the old code's records: placed / live_fill with no over_82 at all
                                            _ev("placed", "2026-11-15T09:59:31.000Z", order_id="k-2001", resp="{}",
                                                body={"ticker": "KXNEAR15M-26NOV150500-00", "count": "224.00"}),
                                            _ev("live_fill", "2026-11-15T09:59:40.000Z", ticker="KXNEAR15M-26NOV150500-00",
                                                paper_id=2001, kid="k-2001", side="yes", px="0.9800", delta=224,
                                                filled=224)]
    pl = _write(d, "ladder-live-orders.jsonl", base, compact=True)
    F._CACHE.clear()
    rep = _report([pl], now=NOW_O)
    O = rep["O"]
    ck(O["since"] == "Nov 15 4:50 AM ET" and O["problem"] == F.O_UNTRACKED
       and O["problem"] == "ON THE 100% RAIL BUT NOT TRACKED (the ladder code that marks the bids is not running)"
       and O["engaged"] == 0,
       "O on the 100%% rail without the marking code: live since its start, and its PROBLEM says so: %s"
       % {k: O[k] for k in ("since", "problem", "engaged")})
    ck(O["extra"] == ["ON THE 100% RAIL BUT NOT TRACKED (the ladder code that marks the bids is not running) since Nov 15 "
                      "4:50 AM ET: no bid past the old limit is marked, so none can be counted",
                      "the bids the old 82% limit would have refused: none marked yet since Nov 15 4:50 AM ET"],
       "O's lines lead with the problem; never a quiet 'none yet': %s" % O["extra"])
    T = F.totals(list(rep.values()))
    ck(T["problems"] == ["O"] and all(c["problem"] is None for k, c in rep.items() if k != "O"),
       "totals() counts O's problem (and only it): %s" % T["problems"])
    # the marking code starts (the deploy): the problem goes; the untracked half hour stays said under the net
    pl2 = _write(d, "ladder-live-orders.jsonl", base + [_lad_start("2026-11-15T10:20:00.000Z", O_ARGV100, 1.0)],
                 compact=True)
    F._CACHE.clear()
    rep2 = _report([pl2], now=NOW_O)
    O2 = rep2["O"]
    ck(O2["problem"] is None and F.totals(list(rep2.values()))["problems"] == []
       and O2["extra"] == ["NOT TRACKED Nov 15 4:50 AM ET to Nov 15 5:20 AM ET (the 100% rail on ladder code that does not "
                           "mark the bids): the bids past the old limit then are not in this row",
                           "the bids the old 82% limit would have refused: none marked yet since Nov 15 4:50 AM ET"],
       "the marking code running: no problem; the untracked window is still said: %s" % O2["extra"])
    # the tracked days (run_o's own 100% start) are no problem at all, and the 0.82 start before never was one
    ck(_report([_write(d, "ladder-live-orders.jsonl", run_o([]), compact=True)], now=NOW_O)["O"]["problem"] is None,
       "a tracked 100% start: no problem")
    # back on the old code later (a revert of ladder_live.py with the 100% argv kept): the problem comes back
    pl3 = _write(d, "ladder-live-orders.jsonl", run_o([]) + [_old_code_start("2026-11-15T11:50:00.000Z")], compact=True)
    F._CACHE.clear()
    O3 = _report([pl3], now=NOW_O)["O"]
    ck(O3["problem"] == F.O_UNTRACKED and O3["net_usd"] == -213.04 and O3["engaged"] == 4
       and O3["extra"][0].startswith("ON THE 100% RAIL BUT NOT TRACKED") and "since Nov 15 6:50 AM ET" in O3["extra"][0],
       "the latest start untracked again: the problem is back, the tracked bids before it keep their money: %s"
       % O3["extra"][:1])


if __name__ == "__main__":
    sys.exit(_kit.run(dict(globals()), "test_fixes"))
