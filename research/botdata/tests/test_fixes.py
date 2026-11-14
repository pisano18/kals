"""test_fixes.py -- botdata/fixes.py (v-fixes, 2026-11-04): every live pin change A..Q scored on synthetic pin logs.

Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_fixes.py   (exit 0 = every test passed; botstats.py
--selftest runs it too). Synthetic runs: the 0925r build (code_sha ca156bf45704; rules A, B, C), a later build with
another sha (D..J), the 0925u cheap-window run (K), the 0925v jump-hedge-shadow run (L), the call-B run with its
trajectory log (M), the 0925x band99late run with its trajectory log (P) and the ladder's order log (O, withdrawn; Q).
Every $ below is worked by hand from the scoring table (Kalshi's taker fee ceil(7 * p * (1 - p) * n) / 100 inside); the
phone test (phone/tests/test_fixes_cmd.py) renders the same logs.
"""
import contextlib
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
        # (D's markets are their own run, run_d: this run's orders, I's 32 at 99c among them, are never re-sized)
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


NEW_START = dict(code_sha=NEW_SHA, ws_later_fall_c=10.0, hedge_jump_max=8.0, hedge_odds_mult=1.25, max_positions=5,
                 boost_rail="side", hedge_tick="round", jump_hedge_min_ask=0.05)


def _o(t, tk, want, n, px, tau, leg="full", ask=None, filled=None):
    """An entry order record the way pinrun writes it (the count it asked in body, what it filled, the ask it saw)."""
    return _r("order", t, ticker=tk, want=want, leg=leg, tau_at_send=tau, ask_seen=(px if ask is None else ask),
              filled=(n if filled is None else filled), exec_price=px, limit_sent=0.99, status="executed",
              body={"count": "%.2f" % n, "ticker": tk})


def run_d(recs):
    """A later run of the new build (11-05 1:00 AM ET on, SIZE 20, the 0925r-style rail 'side'): D. The old rule 'any'
    tripped at 1:00:35 AM (a losing No leg on a boosted market: boost_rail_kept); every market whose first fill came
    after it is re-sized order by order at the old 1x (hand-worked, Kalshi's fee ceil(7 x p x (1 - p) x n) / 100 an
    order):
      ZEC  30 Yes at 98c (a band buy, 1.5 x 20), won: 30 -> 20: 0.55 - 0.37 = +0.18
      XRP  30 No at 97c, LOST, its Yes hedge 30 at 30c: 30 -> 20 and the hedge 30 -> 20: (-29.17 + 19.45) + (20.55 -
           13.70) = -2.87
      SUI  an early leg 9.99 at 96.5c and a top-up 20.01 at 97c, no band_boost record (the staged limits sized it 1.5x),
           won: 9.99 -> 6.66, 20.01 -> 13.34: (0.31965 + 0.5503) - (0.2131 + 0.3702) = +0.29
      NEAR 30 No at 99c with 3 s left: the LATE boost, which the band trip left on: the same, not an event
      BNB  bought before the trip: not D's
    D net +0.18 - 2.87 + 0.29 = -2.40."""
    T = "2026-11-05T06:%02d:%02dZ"
    recs += [
        _r("start", T % (0, 0), size=20.0, coin_size_frac={"KXHYPE15M": 0.15}, **NEW_START),
        _o(T % (0, 10), "KXBNB15M-26NOV050115-15", "yes", 30.0, 0.98, 20),
        _r("settled", T % (15, 21), ticker="KXBNB15M-26NOV050115-15", want="yes", result="yes", cost=0.98, pnl_c=55.0),
        _r("boost_rail_kept", T % (0, 35), which="band", ticker="KXHYPE15M-26NOV050100-00", close_s=1793858400,
           leg_side="no", boosted_side=["yes"], cost=0.07, pnl_c=-158.65, rail="side", live=True),
        _r("band_boost", T % (14, 42), ticker="KXZEC15M-26NOV050115-15", want="yes", tau=18, price=0.98, mult=1.5,
           was=20.0, now=30.0),
        _o(T % (14, 42), "KXZEC15M-26NOV050115-15", "yes", 30.0, 0.98, 18),
        _r("settled", T % (15, 20), ticker="KXZEC15M-26NOV050115-15", want="yes", result="yes", cost=0.98, pnl_c=55.0),
        _r("band_boost", T % (14, 43), ticker="KXXRP15M-26NOV050115-15", want="no", tau=17, price=0.97, mult=1.5,
           was=20.0, now=30.0),
        _o(T % (14, 43), "KXXRP15M-26NOV050115-15", "no", 30.0, 0.97, 17),
        _r("hedge", T % (14, 50), ticker="KXXRP15M-26NOV050115-15", side="yes", price=0.30, n=30.0, asked=30.0,
           entry=0.97, status="executed", tick_mode="round", limit_sent=0.40, live=True),
        _r("settled", T % (15, 20), ticker="KXXRP15M-26NOV050115-15", want="no", result="yes", cost=0.97, pnl_c=-2917.0),
        _r("settled", T % (15, 22), ticker="KXXRP15M-26NOV050115-15", want="yes", result="yes", cost=0.30, pnl_c=2055.0),
        _r("late_boost", T % (29, 57), ticker="KXNEAR15M-26NOV050130-30", want="no", tau=3, was=20.0, now=30.0, mult=1.5),
        _o(T % (29, 57), "KXNEAR15M-26NOV050130-30", "no", 30.0, 0.99, 3),
        _r("settled", T % (30, 20), ticker="KXNEAR15M-26NOV050130-30", want="no", result="no", cost=0.99, pnl_c=27.0),
        _o(T % (29, 20), "KXSUI15M-26NOV050130-30", "yes", 9.99, 0.965, 40, leg="early"),
        _o(T % (29, 35), "KXSUI15M-26NOV050130-30", "yes", 20.01, 0.97, 25, leg="topup"),
        _r("settled", T % (30, 21), ticker="KXSUI15M-26NOV050130-30", want="yes", result="yes", cost=0.965, pnl_c=32.0),
        _r("settled", T % (30, 22), ticker="KXSUI15M-26NOV050130-30", want="yes", result="yes", cost=0.97, pnl_c=55.0),
    ]
    return recs


def write_logs(d, older=True):
    """The synthetic logs in folder `d`: an older build's log (10-31), the 0925r run, the new build's run and its later
    run (D's). Returns their paths (name order = time order)."""
    out = []
    runs = [("pinrun-live-20261102T133522Z.jsonl", run_r([])), ("pinrun-live-20261105T050000Z.jsonl", run_new([])),
            ("pinrun-live-20261105T060000Z.jsonl", run_d([]))]
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
    ck(sorted(rep) == sorted(F.IDS + F.FIXED_IDS) and F.LADDER_IDS == ("O", "Q") and F.FIXED_IDS == ("LAD", "STOP")
       and F.IDS == tuple("ABCDEFGHIJKLMNP") + ("WS",)
       and [c["id"] for c in F.report(paths=write_logs(d), now=NOW)] == list("ABCDEFGHIJKLMNP") + ["WS", "LAD", "STOP"],
       "sixteen pin changes A..N, P and WS, one row each, then the two measured once (LAD, STOP); the ladder's O and Q "
       "only when a ladder order log is read (none here)")
    ck(rep["WS"]["since"] is None and rep["WS"]["not_live"] == F.WS_NOT_LIVE and rep["WS"]["engaged"] == 0,
       "WS is not live before a start record has wrongside_rise_c above 0: %s" % rep["WS"]["not_live"])
    ck(all(c["undo"] is None for c in rep.values()) and all(c["fixed"] == (k in F.FIXED_IDS) for k, c in rep.items()),
       "no undo before an undo start; LAD and STOP are the measured-once rows")
    ck(rep["P"]["since"] is None and rep["P"]["engaged"] == 0 and rep["P"]["extra"] == []
       and rep["P"]["not_live"] == F.P_NOT_LIVE == "not live yet (comes with the first pin start on --band99-max-tau 30)",
       "P is not live before a start record has band99_max_tau set, and says what it waits for: %s" % rep["P"]["not_live"])
    ck(all(c["withdrawn"] is False and c["problem"] is None for c in rep.values()), "no pin change is withdrawn")
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


def run_b(recs):
    """B re-scored (the 11-14 retro: score_B's -$34.83 credited premiums on hedges that could never fill and missed the
    label case; real -$25.12): one log, four builds. Hand-worked, Kalshi's fee ceil(7 x p x (1 - p) x n) / 100 a leg.
      NEAR  capped, ask 0.1c, limit 10.1c, before --hedge-tick round: off-grid, Kalshi refused every such order: $0
      BNB   capped, 192 No: the ladder gives 100 at 61c + 92 at 65c; the bet LOST, so the jump hedge would have made
            37.33 + 30.73 = 68.06; pin's real later hedge (192 at 80c: 36.24) and its extra (48 at 83c: 7.68) made 43.92:
            the cap cost 24.14 (7.68 of it an extra leg C counts too)
      ZEC   a 'belief' alarm on an 11.6 sd jump before the J build: the extra (14.12 Yes at 80c) fired only because of
            the cap; the bet flipped: +2.66 (C's leg too)
      BTC   capped under the 5c bar (the round build): $0;  ETH capped while the jump hedge was in shadow: $0
    B = -24.14 + 2.66 = -21.48; the overlap with C 7.68 + 2.66 = 10.34; then a start without --hedge-jump-max."""
    def cap(t, tk, want, side, n, ask, lim, ladder, sd=9.0, tau=30):
        return _r("jump_capped", t, ticker=tk, want=want, side=side, n=n, ask=ask, limit=lim, ladder=ladder, jump_sd=sd,
                  belief=0.9, tau=tau, jump_threshold=6.0, jump_max=8.0)
    recs += [
        _r("start", "2026-11-03T00:00:00Z", code_sha="ca156bf45704", hedge_jump=6.0, hedge_jump_max=8.0,
           hedge_odds_mult=1.25),
        cap("2026-11-03T00:14:55Z", "KXNEAR15M-26NOV021915-15", "no", "yes", 229.0, 0.001, 0.101, [[0.001, 5000.0]], tau=5),
        _r("settled", "2026-11-03T00:15:20Z", ticker="KXNEAR15M-26NOV021915-15", want="no", result="no", cost=0.99,
           pnl_c=200.0),
        cap("2026-11-03T00:29:16Z", "KXBNB15M-26NOV021930-30", "yes", "no", 192.0, 0.61, 0.71,
            [[0.61, 100.0], [0.65, 200.0]], sd=9.6, tau=44),
        _r("hedge", "2026-11-03T00:29:30Z", ticker="KXBNB15M-26NOV021930-30", side="no", price=0.80, n=192.0,
           asked=192.0, status="executed", live=True),
        _r("hedge_extra", "2026-11-03T00:29:31Z", ticker="KXBNB15M-26NOV021930-30", side="no", price=0.83, n=48.0,
           asked=48.0, mult=1.25, base_n=192.0, extra_of=48.0, order_id="x-b", status="executed", live=True),
        _r("settled", "2026-11-03T00:30:20Z", ticker="KXBNB15M-26NOV021930-30", want="yes", result="no", cost=0.97,
           pnl_c=-18624.0),
        _r("settled", "2026-11-03T00:30:21Z", ticker="KXBNB15M-26NOV021930-30", want="no", result="no", cost=0.80,
           pnl_c=3624.0),
        _r("hedge_alarm", "2026-11-03T00:44:18Z", ticker="KXZEC15M-26NOV021945-45", want="no", entry=0.97, n=56.5,
           belief=0.149, tau=42, threshold=0.4, trigger="belief", jump_sd=11.6),
        _r("hedge_extra", "2026-11-03T00:44:19Z", ticker="KXZEC15M-26NOV021945-45", side="yes", price=0.80, n=14.12,
           asked=14.12, mult=1.25, base_n=56.5, extra_of=14.12, order_id="x-z", status="executed", live=True),
        _r("settled", "2026-11-03T00:45:20Z", ticker="KXZEC15M-26NOV021945-45", want="no", result="yes", cost=0.97,
           pnl_c=-5481.0),
        _r("start", "2026-11-03T01:00:00Z", code_sha="9e04c0252ac9", hedge_jump=6.0, hedge_jump_max=8.0,
           hedge_odds_mult=1.25, hedge_tick="round", jump_hedge_min_ask=0.05),
        cap("2026-11-03T01:14:59Z", "KXBTC15M-26NOV022015-15", "no", "yes", 37.0, 0.001, 0.10, [[0.001, 9000.0]], tau=1),
        _r("settled", "2026-11-03T01:15:20Z", ticker="KXBTC15M-26NOV022015-15", want="no", result="no", cost=0.99,
           pnl_c=30.0),
        _r("start", "2026-11-03T02:00:00Z", code_sha="d51b131b55cf", hedge_jump=None, hedge_jump_shadow=6.0,
           hedge_jump_max=8.0, hedge_odds_mult=1.25, hedge_tick="round", jump_hedge_min_ask=0.05),
        cap("2026-11-03T02:29:28Z", "KXETH15M-26NOV022130-30", "no", "yes", 38.0, 0.30, 0.40, [[0.30, 100.0]], tau=32),
        _r("settled", "2026-11-03T02:30:20Z", ticker="KXETH15M-26NOV022130-30", want="no", result="yes", cost=0.97,
           pnl_c=-3700.0),
        _r("start", "2026-11-03T03:00:00Z", code_sha="d51b131b55cf", hedge_jump=None, hedge_jump_shadow=6.0,
           hedge_jump_max=None, hedge_odds_mult=1.25, hedge_tick="round", jump_hedge_min_ask=0.05),
    ]
    return recs


def test_b_rescored():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    p = _write(d, "pinrun-live-20261103T000000Z.jsonl", run_b([]))
    rep = _report([p], now=1793700000.0)
    B, C = rep["B"], rep["C"]
    w = {e["coin"]: e for e in B["events"]}
    ck(sorted(w) == ["BNB", "BTC", "ETH", "NEAR", "ZEC"] and B["engaged"] == 5 and B["net_usd"] == -21.48,
       "B: -24.14 + 2.66; NEAR, BTC and ETH $0: %s %s" % (B["net_usd"], sorted(w)))
    ck(w["NEAR"]["usd"] == 0.0 and "off Kalshi's price grid" in w["NEAR"]["words"]
       and w["BTC"]["usd"] == 0.0 and "under the 5.0c bar nothing would have been sent" in w["BTC"]["words"]
       and w["ETH"]["usd"] == 0.0 and "in shadow" in w["ETH"]["words"],
       "B: no saved premium on a hedge that could never have filled: %s" % [w[k]["words"] for k in ("NEAR", "BTC", "ETH")])
    ck(w["BNB"]["usd"] == -24.14 and w["BNB"]["words"] == (
        "a 9.6 sd jump against Yes with 44 s left: the cap skipped a jump hedge of 192 No asking 61.0c; the bet LOST (a "
        "flip): pin's later hedges on that side made $43.92 (+$7.68 of it extra legs, C's too), the jump hedge (192 at "
        "62.9c) would have made $68.06, so the cap cost $24.14"), "B priced: %s" % w["BNB"]["words"])
    ck(w["ZEC"]["usd"] == 2.66 and "the cap turned the alarm to 'belief', so the odds extra fired" in w["ZEC"]["words"]
       and "14.12 extra Yes at 80.0c made $2.66 (C counts these too)" in w["ZEC"]["words"],
       "B: the label case before the J build: %s" % w["ZEC"]["words"])
    ck(B["overlap_usd"] == 10.34 and C["net_usd"] == 10.34 and B["dropped"] == "Nov 2 10:00 PM ET"
       and B["extra"][0].startswith("the cap was DROPPED Nov 2 10:00 PM ET")
       and not any("10.34" in x for x in B["extra"]),
       "B's extra legs are C's too (overlap 10.34: the phone says it on B's net line, never a line a shrink step drops), "
       "then the dropped cap (its since line says DROPPED too): %s" % B["extra"])
    T = F.totals(list(rep.values()))
    ck(T["overlap_usd"] == 10.34 and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J") - 10.34, 2),
       "totals take the B/C extra legs once: %s" % T)
    ck(F.jump_live({}) and F.jump_live({"hedge_jump": 6.0}) and not F.jump_live({"hedge_jump": None})
       and not F.jump_live({"hedge_jump_shadow": 6.0}), "jump_live: an older record without the field ran it")


def test_d_boost_rail():
    """D re-sized order by order from the old rule's trip (the 11-14 retro: the band_boost records' 'now - was' showed
    +$109.38 on the server's logs, real -$22.26): run_d's markets, hand-worked in its docstring."""
    d = tempfile.mkdtemp(prefix="fixes-test-")
    D = _report(write_logs(d))["D"]
    ck(D["engaged"] == 3 and D["open"] == 0, "D: three markets sized differently after the trip: %s" % D["engaged"])
    ck(D["net_usd"] == -2.40, "D: ZEC +0.18, XRP -2.87 (its hedge scaled 30 -> 20), SUI +0.29 (no band_boost record: the "
                              "staged limits) = -2.40: %s" % D["net_usd"])
    w = {e["coin"]: e for e in D["events"]}
    ck(sorted(w) == ["SUI", "XRP", "ZEC"], "NEAR's late boost (left on by the band trip) and BNB (before it) are not D's")
    ck(w["XRP"]["usd"] == -2.87 and w["XRP"]["words"] == (
        "bought after the old rule's band-boost trip (1:00 AM ET, a losing No leg): the boost stayed on, so 30 contracts "
        "instead of the old rule's 20 (its hedges scaled with it); the bet LOST: the boost rail off cost $2.87"),
       "D words: %s" % w["XRP"]["words"])
    ck(w["ZEC"]["usd"] == 0.18 and w["SUI"]["usd"] == 0.29 and "instead of the old rule's 20;" in w["SUI"]["words"],
       "D: a won band buy and a staged (early + top-up) market: %s %s" % (w["ZEC"], w["SUI"]))
    ck(D["extra"] == ["re-sized order by order as the old rule would have: 3 markets after 1 trip, 1 sized the same; the "
                      "boost itself (1.5x on every 95.5-98.1c buy) is not this row"], "D extra: %s" % D["extra"])
    ck(w["ZEC"]["et"] == "Nov 5 1:14 AM ET", "an event is dated by the market's first fill")
    # the late add's refill: a smaller old position, so the old late add buys MORE (from the book the smaller earlier
    # legs left within 15 s): 30 Yes at 97c (a band full leg, 1.5 x 20) then a late add of 5 at 98c, the market won.
    # The old 1x: the full leg 20; the late add tops up to 1.5 x 20 - 20 = 10, min(its take 5 + the 10 left, 10) = 10
    p = _write(d, "pinrun-live-20261105T063100Z.jsonl", [
        _r("start", "2026-11-05T06:31:00Z", size=20.0, **NEW_START),
        _r("boost_rail_kept", "2026-11-05T06:31:05Z", which="band", ticker="KXHYPE15M-26NOV050145-45", leg_side="no",
           boosted_side=["yes"], pnl_c=-10.0, rail="side", live=True),
        _o("2026-11-05T06:44:40Z", "KXDOT15M-26NOV050145-45", "yes", 30.0, 0.97, 20),
        _o("2026-11-05T06:44:50Z", "KXDOT15M-26NOV050145-45", "yes", 5.0, 0.98, 10, leg="late_add"),
        _r("settled", "2026-11-05T06:45:20Z", ticker="KXDOT15M-26NOV050145-45", want="yes", result="yes", cost=0.97,
           pnl_c=80.0)])
    D2 = _report([p], now=NOW + 3600)["D"]
    # real 30 at 97c (0.90 - 0.07) + 5 at 98c (0.10 - 0.01); old 20 at 97c (0.60 - 0.05) + 10 at 98c (0.20 - 0.02):
    # 0.83 + 0.09 - 0.55 - 0.18 = +0.19
    ck(D2["net_usd"] == 0.19 and "the late add's refill in" in D2["events"][0]["words"],
       "D: the late add's refill (the old one buys 10, not 5): %s" % D2["events"])


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
    ck(T["engaged"] == 17 and T["open"] == 2
       and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2)
       and T["groups"] == {"pin": round(sum(c["net_usd"] for k, c in rep.items() if k not in ("J", "LAD", "STOP")), 2),
                           "ladder": 123.40, "stops": 27.9},
       "totals add up without J (its 2 engagements, 1 open, +17.00 are C's legs too); the measured-once rows in the net "
       "and their groups, not in the engagements: %s" % T)
    ck(G["off"] is True and all(rep[k]["off"] is False for k in "ABCDEFHIJ"),
       "only G is marked off while the start record lacks late_bypass_fix on: %s" % {k: rep[k]["off"] for k in rep})


def test_not_live_yet_and_empty():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    rep = _report(ps[:2])                                  # the 0925r run only: D..M and P are not live
    for k in "DEFGHIJKLMP":
        ck(rep[k]["since"] is None and rep[k]["engaged"] == 0 and rep[k]["net_usd"] == 0.0 and rep[k]["events"] == [],
           "%s not live yet" % k)
    ck(rep["I"]["what"] == "up to 5 positions open at once (was 3)", "the new flags' words before the build is live")
    ck(rep["C"]["engaged"] == 2 and rep["C"]["net_usd"] == 85.15, "C counts its two 0925r legs (one open)")
    rep = _report([])
    ck(all(c["engaged"] == 0 for k, c in rep.items() if k not in F.FIXED_IDS) and rep["A"]["since"]
       and rep["D"]["since"] is None and rep["LAD"]["net_usd"] == 123.40 and rep["STOP"]["net_usd"] == 27.9,
       "no logs at all: nothing engaged; the two measured-once rows are there all the same")
    rep = _report([os.path.join(d, "missing.jsonl")])
    ck(all(c["engaged"] == 0 for k, c in rep.items() if k not in F.FIXED_IDS), "a missing log is tolerated")


NOW_K = 1794080400.0               # 2026-11-07T19:00:00Z = 2:00 PM ET
T_K = "2026-11-07T%s:%s:%sZ"


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
    # the 11-14 retro's prices (the skeptic's model D): a flip at the early leg's 0.903 fill, lost, with the shadow's
    # belief hedge; a win at 0.909 (a full leg) / 1.064 (an early leg) of n_ask x the edge, hedge-free
    ck(w["BNB"]["usd"] == 108.18 and "FLIPPED" in w["BNB"]["words"] and "would have lost $108.18" in w["BNB"]["words"]
       and "Yes hedge pin would have bought at 70.0c" in w["BNB"]["words"] and "saved" in w["BNB"]["words"]
       and "skipped a first No buy at 97.0c with 45 s left (about 169 contracts)" in w["BNB"]["words"],
       "K flipped: 193.81 x 0.903 = 175.01 No at 97.287c lost 170.26 + fee 0.33, the 1.25x Yes hedge (218.76 at 70c) "
       "made 65.63 - fee 3.22: -108.18 without the rule, +108.18 saved (169 = 193.81 x 0.874 the first order's fill): %s"
       % w["BNB"])
    ck(w["ETH"]["usd"] == -1.14 and "WON" in w["ETH"]["words"] and "would have made $1.14" in w["ETH"]["words"]
       and "gave up" in w["ETH"]["words"] and "hedge" not in w["ETH"]["words"],
       "K won, a full leg: 0.909 x 50 x 2.5c = +1.14 without the rule, -1.14 given up: %s" % w["ETH"])
    ck(w["SOL"]["usd"] is None and w["SOL"]["open"] and "XRP" not in w,
       "K open: no $ until its shadow settles; another gate's refusal is not K's")
    ck(K["net_usd"] == 107.04, "K net: +108.18 - 1.14 = +107.04: %s" % K["net_usd"])
    ck(K["extra"] == ["without the rule: the 2 settled skips would have lost $107.04 (1 won, 1 flipped, hedges in) "
                      "\u00b7 1 still open",
                      "closes 6 AM to 10 AM ET since the rule (1 settled market): pin made +$1.50 with it, -$105.54 without it",
                      "priced on pin's own 6-10 ET cheap first buys before the rule: a win at 0.909 (full leg) / 1.064 "
                      "(early leg) of n_ask x the edge, hedge-free; a flip at a 0.903 fill (assumptions)"],
       "K extra: the skips without the rule, the window with (+1.50) and without (+1.50 - 107.04), the assumptions: %s"
       % K["extra"])
    # two skips in ONE close share its budget (the refusal's budget_left): the second gets what the first left
    pk2 = _write(d, "pinrun-live-20261107T101819Z.jsonl", run_k([]) + [
        _r("refused", T_K % ("13", "29", "40"), gate="cheap_window", ticker="KXZEC15M-26NOV070830-30", close_s=1794058200,
           want="yes", leg="full", tau=20, price=0.97, budget_left=100.0, n_ask=100.0, px=0.97),
        _r("cheap_window_settled", T_K % ("13", "30", "40"), ticker="KXZEC15M-26NOV070830-30", close_s=1794058200,
           result="yes", want="yes", n_ask=100.0, px=0.97, hedge_px=None),
        _r("refused", T_K % ("13", "29", "45"), gate="cheap_window", ticker="KXDOGE15M-26NOV070830-30", close_s=1794058200,
           want="yes", leg="full", tau=15, price=0.97, budget_left=100.0, n_ask=100.0, px=0.97),
        _r("cheap_window_settled", T_K % ("13", "30", "41"), ticker="KXDOGE15M-26NOV070830-30", close_s=1794058200,
           result="yes", want="yes", n_ask=100.0, px=0.97, hedge_px=None)])
    w2 = {e["coin"]: e for e in _report(ps + [pk2], now=NOW_K)["K"]["events"]}
    # ZEC: 100 x 0.874 = 87.4 of the 100 left: whole, 0.909 x 100 x 3c = 2.73; DOGE: 12.6 left of its 87.4: a scale of
    # 0.1442, 0.909 x 100 x 3c x 0.1442 = 0.39
    ck(w2["ZEC"]["usd"] == -2.73 and w2["DOGE"]["usd"] == -0.39 and "the close's budget shared" in w2["DOGE"]["words"]
       and "budget" not in w2["ZEC"]["words"], "K: the close's budget shared in refusal order: %s %s" % (w2["ZEC"], w2["DOGE"]))
    ck(K["what"] == "no first buy under 98.0c in a market closing 6 AM to 10 AM ET (the market is skipped); each skip is "
                    "priced by what it would have done", "K what, off the start record: %s" % K["what"])
    T = F.totals(list(rep.values()))
    ck(T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2) and T["engaged"] == 20,
       "totals take K in (17 + 3 engagements): %s" % T)
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
    ck(T["engaged"] == 24 and T["open"] == 4
       and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2),
       "totals take L in (17 + 3 + 4 engagements; its kept premium and missed save are pin's real money): %s" % T)
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
        # the bank pin's boost records carry: the one-coin room of a 1.5x widener is min(1.5 x 100, (1000 - 0.8 x 1000)
        # / 0.98 = 204) = 150
        _r("band_boost", "2026-11-08T21:00:02Z", ticker="KXSOL15M-26NOV081615-15", want="yes", tau=20, price=0.97,
           mult=1.5, was=100.0, now=150.0, size=100.0, bank=1000.0, hwm=1000.0),
        # E (4:45 PM): XRP took 140 of the 200; NEAR (a new coin, 11 s left) got 60, the budget's last contracts; the old
        # argv's room (60 + 100) and the 1.5x band boost (96.5c: its one-coin room 150, the UNTAPERED book under the 98c
        # limit 401) allowed 150 (the sweep alone: min(100, the tapered 331, 160)): 90 more, off the book past the 60 that
        # filled: 90 at 97c. NEAR won, so the 90 would have made 2.70 - fee ceil(7 x 90 x 0.97 x 0.03 = 18.33) / 100 =
        # 0.19: 2.51 given up (the old tracker took the tapered 331 and priced the win at the 98c limit)
        _order(_ts(E - 25), "KXXRP15M-26NOV081645-45", "yes", 140.0, 0.975, 25),
        _r("signal", _ts(E - 11), live=True, ticker="KXNEAR15M-26NOV081645-45", want="no", price=0.965, tau=11, size=1.0,
           take_n=1.0, leg="full", budget_left=60.0, fair=0.00355, ladder=[[0.965, 1.0], [0.97, 400.0], [0.985, 20.0]]),
        _r("taper", _ts(E - 11), ticker="KXNEAR15M-26NOV081645-45", want="no", tau=11, touch=0.965, rungs=3, flat=401.0,
           tapered=331.0, limit=0.98),
        _r("sweep_depth", _ts(E - 11), ticker="KXNEAR15M-26NOV081645-45", want="no", touch=1.0, ladder=331.0, was=1.0,
           now=60.0, limit=0.98),
        _order(_ts(E - 11), "KXNEAR15M-26NOV081645-45", "no", 60.0, 0.9699, 11, limit=0.98),
        _r("settled", _ts(E + 20), ticker="KXXRP15M-26NOV081645-45", want="yes", result="yes", cost=0.975, pnl_c=350.0),
        _r("settled", _ts(E + 20), ticker="KXNEAR15M-26NOV081645-45", want="no", result="no", cost=0.9699, pnl_c=180.6),
        # F (6:00 PM): BNB took 150; DOGE (new, 8 s left) got the last 50 of a 500 book at 97.8c; the old room 150 and the
        # late boost (8 s left, confidence 99.99%: its one-coin room 150) allowed 150: 100 more. DOGE LOST, so the 100
        # would have lost 100 x 97.8c + fee ceil(7 x 100 x 0.978 x 0.022 = 15.06) / 100 = 0.16: 97.96 saved
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
        for r in sorted(traj_m([]), key=lambda r: r["t"]):    # pinrun appends in time order (the reader searches it)
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
    ck(M["engaged"] == 2 and M["open"] == 0 and M["net_usd"] == 95.45, "M: two held-back buys, -2.51 + 97.96 = +95.45: %s" % {
        x: M[x] for x in ("engaged", "open", "net_usd")})
    w = {e["coin"]: e for e in M["events"]}
    ck(w["NEAR"]["usd"] == -2.51 and w["NEAR"]["words"] == (
        "a No buy at 97.0c with 11 s left was held to the 2-bet budget: 60 went out; with the old 3rd bet the band boost "
        "would have bought 90 more (at 97.0c, the book past what filled, under the 98.0c limit, inside the late window); "
        "the bet won, so holding them back gave up $2.51"),
       "M held-back, won: min(150, the untapered 401, 60 + 100) - 60 = 90, priced on the book past the fill: %s" % w["NEAR"])
    ck(w["DOGE"]["usd"] == 97.96 and "50 went out; with the old 3rd bet the late boost would have bought 100 more (at "
       "97.8c" in w["DOGE"]["words"] and w["DOGE"]["words"].endswith("the bet LOST, so holding them back saved $97.96"),
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
        "held back: would have made $2.51 on 1 won, lost $97.96 on 1 flipped (2 buys cut to the 2-bet budget where the old "
        "argv had room for a 3rd; priced on the book past each fill, hedges in)",
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
    ck(T["engaged"] == 26 and T["open"] == 4 and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2),
       "totals take M's net in (17 + 3 + 4 + 2 engagements), never its third list: %s" % T)
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
    ck(M["engaged"] == 2 and M["net_usd"] == 95.45 and M["third"] == [], "held-back buys scored, no third bet priced")
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
        ck(got == ["pinrun-live-20261001T000000Z.jsonl", "pinrun-live-20261031T101116Z.jsonl",
                   "pinrun-live-20261102T133522Z.jsonl", "pinrun-live-20261105T050000Z.jsonl",
                   "pinrun-live-20261105T060000Z.jsonl"],
           "pin_paths: the runs from WS's 10-28 01:07:25Z on plus the one live then: %s" % got)
        with open(os.path.join(td, "pinrun-live-20261028T010725Z.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(_r("start", "2026-10-28T01:07:25Z", code_sha="e51a465d8b5c", wrongside_rise_c=1.0)) + "\n")
        got = [os.path.basename(p) for p in F.pin_paths()]
        ck(got[0] == "pinrun-live-20261028T010725Z.jsonl" and len(got) == 5,
           "a run starting AT 10-28 01:07:25Z: the one before it holds nothing of it, so it is left out: %s" % got)
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


@contextlib.contextmanager
def o_live():
    """O's scoring as if it had not been withdrawn (F.O_WITHDRAWN False), for the tests that keep its machinery
    checked; the withdrawn row (the shipped value) is test_o_withdrawn's."""
    saved = F.O_WITHDRAWN
    F.O_WITHDRAWN = False
    try:
        yield
    finally:
        F.O_WITHDRAWN = saved


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
    with o_live():
        _test_o_ladder_rail100()


def _test_o_ladder_rail100():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    pl = _write(d, "ladder-live-orders.jsonl", run_o([]), compact=True)   # ladder_live's own (compact) JSON
    rep = _report(ps + [pl], now=NOW_O)
    ck(sorted(rep) == sorted(F.IDS + F.LADDER_IDS + F.FIXED_IDS)
       and [c["id"] for c in F.report(paths=ps + [pl], now=NOW_O)] == list("ABCDEFGHIJKLMNOP") + ["WS", "Q", "LAD", "STOP"],
       "a ladder order log adds the O and Q rows, in letter order around P (WS after P, the measured-once rows "
       "last): %s" % sorted(rep))
    ck(rep["Q"]["since"] is None and rep["Q"]["not_live"] == F.Q_NOT_LIVE,
       "Q is not live on ladder starts before the midnight-reset code (no start_reads): %s" % rep["Q"]["not_live"])
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
    ck(T["engaged"] == 21 and T["open"] == 3
       and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2),
       "totals take O in (17 + 4 engagements; the ladder's real money): %s" % T)
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
    ck(O3["since"] is None and O3["engaged"] == 0 and O3["not_live"] == F.O_NOT_LIVE and O3["withdrawn"] is False,
       "O before the restart on --commit-frac 1.0 (only the 0.82 start): not live, its own words: %s" % O3["not_live"])


def test_o_none_yet_and_helpers():
    with o_live():
        _test_o_none_yet_and_helpers()


def _test_o_none_yet_and_helpers():
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
    once the marking code starts, the problem goes and the untracked hours stay said under the net. (O's machinery,
    run as if O had not been withdrawn: while it is, none of this is a problem -- test_o_withdrawn.)"""
    with o_live():
        _test_o_untracked_is_a_problem()


def _old_code_base():
    """The 0.82 day, then the 100% argv started on the OLDER ladder code with its unmarked placed / live_fill."""
    return run_o([], with_rail100=False) + [_old_code_start("2026-11-15T09:50:00.000Z"),
                                            _ev("placed", "2026-11-15T09:59:31.000Z", order_id="k-2001", resp="{}",
                                                body={"ticker": "KXNEAR15M-26NOV150500-00", "count": "224.00"}),
                                            _ev("live_fill", "2026-11-15T09:59:40.000Z", ticker="KXNEAR15M-26NOV150500-00",
                                                paper_id=2001, kid="k-2001", side="yes", px="0.9800", delta=224,
                                                filled=224)]


def test_o_withdrawn():
    """v-ladder-rail100 WITHDRAWN 11-14 (F.O_WITHDRAWN, the shipped value): O's row is never live whatever the ladder log
    holds -- its words say withdrawn and that the ladder stays at 82% --, never a problem, never in totals(); a 100%
    start in the log all the same is said in its words (never a quiet '82%' that is not true), still no problem."""
    ck(F.O_WITHDRAWN is True and F.O_NOT_LIVE == "withdrawn 11-14: it could not be tracked against never changing it, so "
       "the ladder stays at 82%", "O ships withdrawn, in those words: %s" % F.O_NOT_LIVE)
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    # the 82% days only (the server's log today): withdrawn, exactly those words
    pl = _write(d, "ladder-live-orders.jsonl", run_o([], with_rail100=False), compact=True)
    rep = _report(ps + [pl], now=NOW_O)
    O = rep["O"]
    ck(O["since"] is None and O["engaged"] == 0 and O["net_usd"] == 0.0 and O["events"] == [] and O["extra"] == []
       and O["problem"] is None and O["withdrawn"] is True and O["not_live"] == F.O_NOT_LIVE,
       "O withdrawn on the 0.82 log: %s" % {k: O[k] for k in ("since", "engaged", "problem", "withdrawn", "not_live")})
    # the logs that made O live, tracked (-213.04) and untracked (a problem): withdrawn, neither counts
    for name, recs in (("tracked", run_o([])), ("untracked", _old_code_base())):
        pl = _write(d, "ladder-live-orders.jsonl", recs, compact=True)
        rep = _report(ps + [pl], now=NOW_O)
        O, T = rep["O"], F.totals(list(rep.values()))
        ck(O["since"] is None and O["engaged"] == 0 and O["problem"] is None and O["withdrawn"] is True
           and O["not_live"] == F.O_NOT_LIVE + "; but the ladder's latest start (Nov 15 4:50 AM ET) runs --commit-frac "
                                               "1.0: nothing of it is counted here"
           and T["problems"] == [] and T["engaged"] == 17 and T["open"] == 2
           and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k not in ("J", "O")), 2),
           "O withdrawn on the %s 100%% log: not live, no problem, not in the totals (17 engaged = A..N's), and its words "
           "say the 100%% start: %s | %s" % (name, O["not_live"], T))
    # totals() leaves a withdrawn row out even if one carried money or a problem
    fake = dict(rep["O"], engaged=3, open=1, net_usd=-50.0, problem="x")
    T2 = F.totals([fake, rep["A"]])
    ck(T2["engaged"] == rep["A"]["engaged"] and T2["net_usd"] == rep["A"]["net_usd"] and T2["problems"] == [],
       "totals(): a withdrawn row never counts, never a problem: %s" % T2)


def _test_o_untracked_is_a_problem():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    base = _old_code_base()                    # the old code's records: placed / live_fill with no over_82 at all
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


# ---- v-0925x band99late (2026-11-14): P, each band leg skipped for being earlier than 30 s ---------------------------
NOW_P = 1794684000.0               # 2026-11-14T19:20:00Z = 2:20 PM ET (the 2:15 PM market: 5 min past its close)
PC = {"ZEC": 1794680100, "ETH": 1794680100, "BNB": 1794681000, "XRP": 1794681900, "DOGE": 1794682800,
      "SOL": 1794683700}           # the closes: 1:15, 1:15, 1:30, 1:45, 2:00, 2:15 PM ET
PT = {"ZEC": "KXZEC15M-26NOV141315-15", "ETH": "KXETH15M-26NOV141315-15", "BNB": "KXBNB15M-26NOV141330-30",
      "XRP": "KXXRP15M-26NOV141345-45", "DOGE": "KXDOGE15M-26NOV141400-00", "SOL": "KXSOL15M-26NOV141415-15"}
P_START = dict(code_sha="3a19b0019e9c", band99_max_tau=30, band99_ceiling=0.99, band99_frac=0.1, max_per_market=2,
               tau_max=30, early_tau_max=45, hedge_odds_mult=1.5, hedge_odds_min_tau=11.0, size=447.0)


def _b99(coin, tau, want, ask, n, leg="early", cs=None, tk=None, **kw):
    """A band99_shadow record as pinrun 0925x writes it (the fields of the server's 11-14 18:14:25Z XRP record)."""
    cs = PC[coin] if cs is None else cs
    rec = dict(ticker=tk or PT[coin], close_s=cs, want=want, side=want, ask=ask, ask_seen=ask, ask_size=155.0, tau=tau,
               max_tau=30, fair=(0.997 if want == "yes" else 0.003), edge_c=0.9, strike=1.0, digits=2, spot=1.0,
               sigma=0.0002, book_age_ms=6, index_age_s=0.05, exchange_index=2, full=447.0, coin_size=None,
               early_held=0.0, drop_seen=[ask, tau], budget_left=894.0, band99=True, band99_ceiling=0.99, band99_frac=0.1,
               live=True, sent=False, leg=leg, n=n, n_band=44.0, limit=0.99, sweep_headroom_c=0.5,
               ladder=[[ask, 155.0]], buyable=155.0, band99_ev_c=0.5)
    rec.update(kw)
    return _r("band99_shadow", _ts(cs - tau), **rec)


def _p_order(coin, tau, want, n, px, leg="full", band99=False, early_held=0.0, cs=None, tk=None):
    cs = PC[coin] if cs is None else cs
    o = _order(_ts(cs - tau), tk or PT[coin], want, n, px, tau, leg=leg, limit=0.99)
    o.update(band99=band99, early_held=early_held, ask_seen=px)
    return o


def run_p(recs):
    """The 0925x run (11-14 1:11 PM ET on, --band99-max-tau 30): P. Every $ worked by hand with Kalshi's fee
    ceil(7 x p x (1 - p) x n) / 100: a skipped band leg n at its ask, a loss less the 41% pin's hedges win back."""
    def st(coin, want, res, cost, pnl_c):
        return _r("settled", _ts(PC[coin] + 20), ticker=PT[coin], want=want, result=res, cost=cost, pnl_c=pnl_c)
    recs += [
        _r("start", "2026-11-14T18:11:41Z", **P_START),
        # ZEC 1:15 PM, WON, a blocked early leg that won: the band's 40 Yes at 98.5c would have made 0.60 - fee 0.05 =
        # 0.55; it was the market's early leg, so pin's own early leg (100 at 97c, +2.79) is early_once; the topup at
        # 20 s is the 2nd fill, not blocked. The rule made 2.79 - 0.55 = +2.24. The topup's 200 (+ 100 held) is not the
        # full bet (447 x the 97.5c band's 1.5): the book cut it, so how much more the old one would have bought is not
        # counted (test_p_early_topup prices the ones that were at the full bet)
        _b99("ZEC", 40, "yes", 0.985, 40.0),
        _b99("ZEC", 30, "yes", 0.985, 40.0),          # a 2nd shadow of the same market (after a restart): not counted
        _p_order("ZEC", 38, "yes", 100.0, 0.97, leg="early"),
        _p_order("ZEC", 20, "yes", 200.0, 0.975, leg="topup", early_held=100.0),
        st("ZEC", "yes", "yes", 0.97, 279.0), st("ZEC", "yes", "yes", 0.975, 465.0),
        # ETH 1:15 PM, untraded: the trajectory's last second says No (fair 0.0), the band's 44 No at 98.9c would have
        # made 0.484 - fee 0.04 = 0.44; nothing blocked: the rule cost 0.44
        _b99("ETH", 40, "no", 0.989, 44.0),
        # BNB 1:30 PM, LOST: the band's 30 No at 98.8c would have lost 29.64 + fee 0.03 = 29.67, x 0.59 = 17.51 after
        # pin's hedges; it would have blocked pin's own early No leg (60 at 96c: -57.77) whose hedge (60 Yes at 40c:
        # +34.99) is all that leg's: -22.78. The rule cost -22.78 - (-17.51) = 5.27
        _b99("BNB", 42, "no", 0.988, 30.0),
        _p_order("BNB", 36, "no", 60.0, 0.96, leg="early"),
        _r("hedge", _ts(PC["BNB"] - 10), ticker=PT["BNB"], close_s=PC["BNB"], side="yes", price=0.40, n=60.0, asked=60.0,
           status="executed", live=True),
        st("BNB", "no", "yes", 0.96, -5777.0), st("BNB", "yes", "yes", 0.40, 3499.0),
        # XRP 1:45 PM, the server's 11-14 shape: the band's 44 Yes at 98.1c (35 s) would have made 0.836 - fee 0.06 =
        # 0.78 and held the market, so pin's own band leg at 22 s (28.8 at 98.8c, +0.32) is band99_held: -0.46
        _b99("XRP", 35, "yes", 0.981, 44.0, ladder=[[0.981, 20.0], [0.982, 20.0], [0.983, 65.0]]),
        _p_order("XRP", 22, "yes", 28.8, 0.988, band99=True),
        st("XRP", "yes", "yes", 0.988, 32.16),
        # DOGE 2:00 PM: the band's 20 Yes at 99c (0.20 - fee 0.02 = 0.18) is the 1st fill, pin's 100 at 97.5c the 2nd,
        # its 50 at 97c at 12 s would be the 3rd: max_per_market (+1.39). The rule made 1.39 - 0.18 = +1.21
        _b99("DOGE", 44, "yes", 0.99, 20.0),
        _p_order("DOGE", 25, "yes", 100.0, 0.975),
        _p_order("DOGE", 12, "yes", 50.0, 0.97),
        st("DOGE", "yes", "yes", 0.975, 232.0), st("DOGE", "yes", "yes", 0.97, 139.0),
        # SOL 2:15 PM, OPEN: no settled record, no trajectory row (5 min past its close at NOW_P: pending)
        _b99("SOL", 40, "no", 0.985, 30.0),
        # a paper (live false) shadow is not pin's
        _b99("SOL", 41, "no", 0.985, 30.0, live=False, ticker="KXHYPE15M-26NOV141415-15"),
    ]
    return recs


def traj_p(recs):
    """The trajectory log of run_p: a filler market every second from the start to NOW_P (so the log is ~2 MB and the
    close is found by the binary search, not by reading it all), and ETH's and XRP's last seconds."""
    def tj(tk, cs, tau, want, fair, held=None):
        return _r("traj", _ts(cs - tau), ticker=tk, close_s=cs, tau=tau, want=want, held=held, fair=fair,
                  conf=(fair if want == "yes" else 1.0 - fair), spot=1.0, strike=1.0, eff_strike=1.0, mu=1.0, sd=0.001,
                  cushion_sd=100.0, remaining=tau, sigma=0.0002, ask=None, ask_size=None, opp_ask=0.001,
                  opp_size=40000.0, book_age_ms=7, index_age_s=1.0, gate="no_offer", gate_pass_ago=1, near=True,
                  entries_stopped=False, paused=False)
    t0 = 1794679901                                  # 18:11:41Z
    for ep in range(t0, int(NOW_P)):
        cs = ep - ep % 900 + 900                     # the close of the quarter it is in
        recs.append(tj("KXBTC15M-filler", cs, cs - ep, "yes", 0.6))
        if cs == PC["ETH"] and cs - ep <= 2:
            recs.append(tj(PT["ETH"], cs, cs - ep, "no", 0.0))
        if cs == PC["XRP"] and cs - ep <= 2:
            recs.append(tj(PT["XRP"], cs, cs - ep, "yes", 1.0, held="yes"))
    return recs


def write_p(d):
    pp = os.path.join(d, "pinrun-live-20261114T181141Z.jsonl")
    with open(pp, "w", encoding="utf-8") as fh:
        for r in run_p([]):
            fh.write(json.dumps(r) + "\n")
    with open(os.path.join(d, "pintraj-live-20261114T181141Z.jsonl"), "w", encoding="utf-8") as fh:
        for r in traj_p([]):
            fh.write(json.dumps(r) + "\n")
    return pp


def archive_traj(d, name="pintraj-live-20261114T181141Z.jsonl"):
    """Archive folder d's log `name` the way log_rotate.py does: results\\archive\\<name>.gz (the same bytes, gzip), the
    plain file gone. Returns the archive's path."""
    import gzip
    src, ad = os.path.join(d, name), os.path.join(d, "archive")
    os.makedirs(ad, exist_ok=True)
    dst = os.path.join(ad, name + ".gz")
    with open(src, "rb") as a, gzip.open(dst, "wb") as b:
        b.write(a.read())
    os.remove(src)
    return dst


def test_p_band99_late():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    pp = write_p(d)
    rep = _report([pp], now=NOW_P)
    P = rep["P"]
    ck(P["name"] == "band99 late-only" and P["since"] == "Nov 14 1:11 PM ET" and P["not_live"] is None,
       "P since the first start record with band99_max_tau: %s" % P["since"])
    ck(P["engaged"] == 6 and P["open"] == 1 and P["net_usd"] == -2.72,
       "P: 6 shadow markets (the 2nd ZEC shadow and the paper one not), SOL open: +2.24 - 0.44 - 5.27 - 0.46 + 1.21 = "
       "-2.72: %s" % {x: P[x] for x in ("engaged", "open", "net_usd")})
    w = {e["coin"]: e for e in P["events"]}
    ck(sorted(w) == ["BNB", "DOGE", "ETH", "SOL", "XRP", "ZEC"], "P events by coin: %s" % sorted(w))
    ck(w["ZEC"]["usd"] == 2.24 and w["ZEC"]["words"] == (
        "an early band bet skipped: 40 Yes at 98.5c with 40 s left (it would have been the market's early leg); it would "
        "have blocked pin's own early Yes leg at 38 s (100 at 97.0c: the band leg would have been the market's early leg); "
        "pin's top-up at 20 s (200 at 97.5c) was not at the full bet: how much more the old code's would have bought is "
        "not counted; it WON (pin's own settled record): it would have made $0.55; pin's blocked bets made $2.79 with "
        "their hedges; so the rule made $2.24") and w["ZEC"]["et"] == "Nov 14 1:14 PM ET",
       "P won, a blocked early leg that won: 2.79 - 0.55 = +2.24 (the topup, the 2nd fill, not blocked; not at the full "
       "bet, so not priced): %s" % w["ZEC"])
    ck(w["BNB"]["usd"] == -5.27 and "it LOST (pin's own settled record): it would have lost $29.67, $17.51 after pin's "
       "hedges win back 41%; pin's blocked bets lost $22.78 with their hedges; so the rule cost $5.27" in w["BNB"]["words"]
       and "pin's own early No leg at 36 s (60 at 96.0c" in w["BNB"]["words"],
       "P lost: the band's -29.67 x 0.59 = -17.51 against pin's early leg -57.77 + its hedge +34.99: %s" % w["BNB"])
    ck(w["ETH"]["usd"] == -0.44 and w["ETH"]["words"].endswith(
        "it would have blocked none of pin's own bets; it WON (the index at the close): it would have made $0.44; so the "
        "rule cost $0.44"), "P untraded, the result off the trajectory's last second: %s" % w["ETH"])
    ck(w["XRP"]["usd"] == -0.46 and "pin's own band Yes leg at 22 s (28.8 at 98.8c: the band leg would have held the "
       "market)" in w["XRP"]["words"] and "made $0.78" in w["XRP"]["words"] and "made $0.32" in w["XRP"]["words"],
       "P band99_held: 0.32 - 0.78: %s" % w["XRP"])
    ck(w["DOGE"]["usd"] == 1.21 and "pin's Yes leg at 12 s (50 at 97.0c: a 3rd fill counting the band leg (2 a market))"
       in w["DOGE"]["words"] and "pin's blocked bets made $1.39" in w["DOGE"]["words"],
       "P max_per_market: the 3rd fill (+1.39) - 0.18 = +1.21: %s" % w["DOGE"])
    ck(w["SOL"]["usd"] is None and w["SOL"]["open"] and w["SOL"]["words"].endswith("; not settled yet"),
       "P open: no result yet: %s" % w["SOL"])
    ck(P["extra"] == [
        "net -$2.72: the early band bets skipped would have lost $15.56 (4 won, 1 lost); pin's own bets they would have "
        "blocked lost $18.28 · 1 open",
        "gross, before pin's hedges win back 41% of a band loss: they would have lost $27.72; blocked: 2 early legs "
        "(top-ups: 1 not at the full bet: not counted), 1 3rd fill, 1 later band leg"],
       "P's lines, the NET FIRST: X = 0.55 + 0.44 - 17.51 + 0.78 + 0.18 = -15.56, Y = 2.79 - 22.78 + 0.32 + 1.39 = "
       "-18.28, Y - X = -2.72; the gross -27.72: %s" % P["extra"])
    ck(P["what"] == ("the band99 leg (a tenth of the bet at up to 99c) only with 30 s or less left; each earlier one "
                     "skipped is priced by what it would have made and the bets of pin's it would have blocked"),
       "P what, off the start record: %s" % P["what"])
    for e in P["events"]:
        ck("—" not in e["words"], "no em dash in P's words")
    T = F.totals(list(rep.values()))
    ck(T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items() if k != "J"), 2) and T["engaged"] >= 6,
       "P is in the totals (pin's real money and the band legs it skipped): %s" % T)
    # 4 h on, still no result for SOL: unknown, still open
    P4 = _report([pp], now=NOW_P + 4 * 3600)["P"]
    s4 = next(e for e in P4["events"] if e["coin"] == "SOL")
    ck(s4["open"] and s4["words"].endswith("; no result 3 h after the close (unknown)") and P4["net_usd"] == -2.72,
       "P unknown 3 h after the close: %s" % s4["words"])
    # the trajectory by binary search equals a whole read, at every close of the log and between them
    tp = os.path.join(d, "pintraj-live-20261114T181141Z.jsonl")
    ck(os.path.getsize(tp) > 1 << 20, "the planted trajectory log is over 1 MB (the search has work to do)")
    rows = [json.loads(ln) for ln in open(tp, encoding="utf-8")]
    for cs in sorted(set(PC.values())) + [1794679200, 1794685000]:
        want = {}
        for r in rows:
            if r["close_s"] == cs and r["tau"] <= 1:
                want.setdefault(r["ticker"], []).append(r)
        got = F.traj_close_rows(tp, cs)
        ck({k: [x["t"] for x in v] for k, v in got.items()} == {k: [x["t"] for x in v] for k, v in want.items()},
           "traj_close_rows at %d: the binary search finds what a whole read finds: %s" % (cs, sorted(got)))
    ck(F.traj_close_rows(os.path.join(d, "missing.jsonl"), PC["ETH"]) == {}, "a missing trajectory log: {}")
    # the trajectory archived the way log_rotate does it (results\archive\<name>.gz, two days after its last write) while
    # the pin log is still plain: P finds it there (test_p_archived_trajectory: the read, the cache, an archived pin log)
    gz = archive_traj(d)
    ck(not os.path.exists(tp) and F.p_traj_path(pp) == gz, "p_traj_path resolves the archive: %s" % F.p_traj_path(pp))
    Pg = _report([pp], now=NOW_P)["P"]
    ck(Pg["net_usd"] == -2.72 and next(e for e in Pg["events"] if e["coin"] == "ETH")["usd"] == -0.44,
       "P reads results\\archive\\pintraj-*.jsonl.gz once the plain one is archived: %s" % Pg["net_usd"])
    # no trajectory log at all (the archive kept in _P_CLOSES is not asked: there is no file to resolve): ETH has no
    # result (open), the rest unchanged
    os.remove(gz)
    Pn = _report([pp], now=NOW_P)["P"]
    ck(Pn["open"] == 2 and Pn["net_usd"] == -2.28 and next(e for e in Pn["events"] if e["coin"] == "ETH")["usd"] is None,
       "P without a trajectory log: ETH open until a result is known (-2.72 + 0.44): %s" % Pn["net_usd"])
    # helpers
    r0 = _b99("ZEC", 40, "yes", 0.985, 40.0)
    ck([round(x, 4) for x in F.p_given_up(r0, True)] == [0.55, 0.55] and F.p_given_up(dict(r0, n=0), True) == (0.0, 0.0)
       and F.p_given_up(dict(r0, ask=None), False) == (0.0, 0.0)
       and [round(x, 4) for x in F.p_given_up(_b99("BNB", 42, "no", 0.988, 30.0), False)] == [-17.5053, -29.67]
       and F.p_early(r0) and not F.p_early(dict(r0, leg="full")) and F.p_early({"tau": 31}) and not F.p_early({"tau": 30}),
       "p_given_up (won, nothing, no ask, lost x 0.59) and p_early")
    ck(F.p_blocked([], dict(r0, n=0)) == [], "a shadow that would have bought nothing blocks nothing")


def test_p_none_yet():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    p = _write(d, "pinrun-live-20261114T181141Z.jsonl", run_p([])[:1])
    P = _report([p], now=NOW_P)["P"]
    ck(P["since"] == "Nov 14 1:11 PM ET" and P["engaged"] == 0 and P["net_usd"] == 0.0 and P["not_live"] is None
       and P["extra"] == ["early band bets skipped: none yet since Nov 14 1:11 PM ET"],
       "P live with no shadow yet reads 'none yet': %s" % P["extra"])
    # only an open shadow: 'none settled yet'
    p = _write(d, "pinrun-live-20261114T181141Z.jsonl", run_p([])[:1] + [_b99("SOL", 40, "no", 0.985, 30.0)])
    P = _report([p], now=NOW_P)["P"]
    ck(P["engaged"] == 1 and P["open"] == 1 and P["extra"] == ["early band bets skipped: none settled yet since Nov 14 "
                                                               "1:11 PM ET · 1 open"], "P open only: %s" % P["extra"])


def test_p_archived_trajectory():
    """log_rotate moves a pintraj log to results\\archive\\<name>.gz two days after its last write (11-19 for the 0925x
    run's): P must still price every skipped band leg in a market pin did not trade (its result is the trajectory's last
    second). The archive is read through ONCE for all of the run's shadow markets and only each one's close row is kept
    (_P_CLOSES, never _CACHE: _load clears that as the live log grows) -- never the trajectory; an archived pin log
    finds its trajectory in the same archive; a file moved between the look and the read is asked for again."""
    d = tempfile.mkdtemp(prefix="fixes-test-")
    pp = write_p(d)
    gz = archive_traj(d)
    F._P_CLOSES.clear()
    opened, real_open = [], F._lf.open

    def counting(path, *a, **k):
        if "pintraj-live-" in str(path):
            opened.append(str(path))
        return real_open(path, *a, **k)
    F._lf.open = counting
    try:
        P1 = _report([pp], now=NOW_P)["P"]
        n1 = list(opened)
        for i in range(11):                            # the live log grows: a new _load key each ask; then _CACHE cleared
            with open(pp, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(_r("heartbeat", _ts(NOW_P - 60 + i))) + "\n")
            F.report(paths=[pp], now=NOW_P)
        F._CACHE.clear()
        P2 = _by_id(F.report(paths=[pp], now=NOW_P))["P"]
    finally:
        F._lf.open = real_open
    eth = [e["usd"] for P_ in (P1, P2) for e in P_["events"] if e["coin"] == "ETH"]
    ck(P1["net_usd"] == P2["net_usd"] == -2.72 and eth == [-0.44, -0.44],
       "P priced off the archived trajectory, ETH's No off its last second: %s %s" % (P1["net_usd"], eth))
    ck(n1 == [gz] and opened == [gz], "the archive read through once for the run's six shadow markets, never again (12 "
                                      "more reports, _load's eviction and _CACHE cleared): %s" % opened)
    # a FRESH process (the 5-minute watcher: every memory cache empty) reads the close rows persisted next to the logs
    # (results\fixes_traj_cache.json, keyed by the archive's name, size and mtime), never the archive
    F._lf.open = counting
    try:
        opened.clear()
        F._P_CLOSES.clear()
        F._TRAJ_DISK.update(path=None, key=None, data=None)
        F._CACHE.clear()
        P_fresh = _by_id(F.report(paths=[pp], now=NOW_P))["P"]
    finally:
        F._lf.open = real_open
    saved = json.load(open(os.path.join(d, F.TRAJ_CACHE), encoding="utf-8"))
    ck(P_fresh["net_usd"] == -2.72 and opened == [] and len(saved["closes"]) == 1
       and saved["closes"][F._fk_str((gz, os.stat(gz).st_size, os.stat(gz).st_mtime_ns))]["%s|%d" % (PT["ETH"], PC["ETH"])]
       == [{"tau": 1, "fair": 0.0}],
       "a fresh process prices P off the persisted close rows (a few bytes a market), the archive never opened: %s"
       % opened)
    st = os.stat(gz)
    kept = F._P_CLOSES[(gz, st.st_size, st.st_mtime_ns)]
    ck(set(kept) == {(PT[c], PC[c]) for c in ("ZEC", "ETH", "BNB", "XRP", "DOGE", "SOL")}
       and kept[(PT["ETH"], PC["ETH"])] == [{"tau": 1, "fair": 0.0}] and kept[(PT["XRP"], PC["XRP"])] == [{"tau": 1, "fair": 1.0}]
       and kept[(PT["SOL"], PC["SOL"])] == [] and not any(k[0] == "KXBTC15M-filler" for k in kept)
       and not any(isinstance(k, tuple) and k and k[0] == "trajgz" for k in F._CACHE),
       "what is kept: the close row (tau, fair) of each shadow market, [] where the archive has none -- not the filler "
       "market, not the trajectory, nothing in _CACHE: %s" % kept)
    # an archived PIN log too (60 days on): its trajectory resolves from the results folder above results\archive
    import gzip
    ppg = os.path.join(d, "archive", os.path.basename(pp) + ".gz")
    with open(pp, "rb") as a, gzip.open(ppg, "wb") as b:
        b.write(a.read())
    os.remove(pp)
    P3 = _report([ppg], now=NOW_P)["P"]
    ck(F.p_traj_path(ppg) == gz and P3["net_usd"] == -2.72, "an archived pin log's trajectory: %s" % F.p_traj_path(ppg))
    # moved to the archive between the look and the read: asked again, from the archive
    plain = os.path.join(d, "pintraj-live-20261114T181141Z.jsonl")
    with open(plain, "w", encoding="utf-8") as fh:
        for r in traj_p([]):
            fh.write(json.dumps(r) + "\n")
    ck(F.p_traj_path(pp) == plain and F.p_traj_path(ppg) == plain, "plain and archived both there: the plain one")
    real_rows = F.traj_close_rows

    def rotated(tp, cs, pad=5.0):
        os.remove(tp)                                  # log_rotate's delete, right after p_traj_path's look
        return {}
    F.traj_close_rows = rotated
    try:
        rows = F.p_traj({"ticker": PT["ETH"], "close_s": PC["ETH"], "_path": pp}, {})
    finally:
        F.traj_close_rows = real_rows
    ck(rows == [{"tau": 1, "fair": 0.0}] and not os.path.exists(plain), "a trajectory archived mid-read: %s" % rows)
    ck(F.p_traj_path(os.path.join(d, "ladder-live-orders.jsonl")) is None and F.p_traj_path(None) is None
       and F.p_traj_path(os.path.join(d, "pinrun-live-20261101T000000Z.jsonl")) is None
       and F.traj_close_rows(gz, PC["ETH"]) == {},
       "p_traj_path: None for a log that is not pin's, and when neither file is there; the binary search never takes "
       "an archive (traj_gz_rows reads those)")


# the 0925x run's later closes (2:30 to 3:15 PM ET), for the top-up after a blocked early leg
NOW_PT = 1794688200.0              # 2026-11-14T20:30:00Z = 3:30 PM ET
PTC = {"NEAR": 1794684600, "BNB": 1794685500, "DOGE": 1794686400, "SOL": 1794687300}
PTT = {"NEAR": "KXNEAR15M-26NOV141430-30", "BNB": "KXBNB15M-26NOV141445-45", "DOGE": "KXDOGE15M-26NOV141500-00",
       "SOL": "KXSOL15M-26NOV141515-15"}


def run_pt(recs):
    """Four markets where the skipped band leg (B contracts) would have been the early leg, so pin's own early leg (E) is
    blocked (early_once) and pin's real top-up completed the position from E. The old code's top-up would have completed
    it from B: when the real one filled the full bet (447 x the multiple - early_held), it would have bought E - B more,
    priced at the top-up's price and the result with their share of the hedges, and added to what the rule gave up."""
    def b(c, tau, want, ask, n):
        return _b99(c, tau, want, ask, n, cs=PTC[c], tk=PTT[c])

    def o(c, tau, want, n, px, leg, eh=0.0):
        return _p_order(c, tau, want, n, px, leg=leg, early_held=eh, cs=PTC[c], tk=PTT[c])

    def st(c, want, res, cost, pnl_c):
        return _r("settled", _ts(PTC[c] + 20), ticker=PTT[c], want=want, result=res, cost=cost, pnl_c=pnl_c)
    recs += [
        _r("start", "2026-11-14T19:20:00Z", **dict(P_START, late_mult=1.5, late_tau=10, doubt_mult=1.0,
                                                    band_mults=[[0.955, 0.981, 1.5]])),
        # NEAR 2:30 PM, WON, at the full bet (98.3c: no band multiple; 20 s: not the late one): 100 held + 347 = 447. The
        # band's 40 at 98.5c would have made 0.55; pin's early 100 at 98.2c made 1.67; the old top-up's 60 more at 98.3c
        # would have made 1.02 - fee ceil(7 x 0.983 x 0.017 x 60 = 7.02) / 100 = 0.94. Given up 0.55 + 0.94 = 1.49:
        # the rule made 1.67 - 1.49 = +0.18
        b("NEAR", 40, "yes", 0.985, 40.0),
        o("NEAR", 38, "yes", 100.0, 0.982, "early"),
        o("NEAR", 20, "yes", 347.0, 0.983, "topup", 100.0),
        st("NEAR", "yes", "yes", 0.982, 167.0), st("NEAR", "yes", "yes", 0.983, 548.9),
        # BNB 2:45 PM, LOST, at the full bet x 1.5 (97c is in the 95.5-98.1c band): 60 held + 610.5 = 670.5, hedged by
        # 600 Yes at 40c (+349.92). The band's 30 No at 98.8c: -29.67, x 0.59 = -17.51; pin's early 60 at 96c: -57.77 +
        # 349.92 x 60 / 670.5 = -26.46; the old top-up's 30 more at 97c: -29.17 + 349.92 x 30 / 670.5 = -13.51. Given up
        # -17.51 - 13.51 = -31.02: the rule made -26.46 + 31.02 = +4.56
        b("BNB", 42, "no", 0.988, 30.0),
        o("BNB", 36, "no", 60.0, 0.96, "early"),
        o("BNB", 20, "no", 610.5, 0.97, "topup", 60.0),
        _r("hedge", _ts(PTC["BNB"] - 10), ticker=PTT["BNB"], close_s=PTC["BNB"], side="yes", price=0.40, n=600.0,
           asked=600.0, status="executed", live=True),
        st("BNB", "no", "yes", 0.96, -5777.0), st("BNB", "no", "yes", 0.97, -59343.5), st("BNB", "yes", "yes", 0.40, 34992.0),
        # DOGE 3:00 PM, WON, NOT at the full bet (100 held + 150: the book cut it): not counted; 1.67 - 0.55 = +1.12
        b("DOGE", 40, "yes", 0.985, 40.0),
        o("DOGE", 38, "yes", 100.0, 0.982, "early"),
        o("DOGE", 20, "yes", 150.0, 0.983, "topup", 100.0),
        st("DOGE", "yes", "yes", 0.982, 167.0), st("DOGE", "yes", "yes", 0.983, 237.0),
        # SOL 3:15 PM, WON, at the full bet with E (20) under B (40): the old top-up would have been 20 SMALLER, 20 at
        # 98.3c it would not have bought (0.34 - 0.03 = 0.31 off the given up): 0.55 - 0.31 = 0.24; pin's early 20 at
        # 98.2c made 0.33: +0.09 (the real 20 at 98.2c + 427 against 40 at 98.5c + 407: 0.33 - 0.55 + 0.31)
        b("SOL", 40, "yes", 0.985, 40.0),
        o("SOL", 38, "yes", 20.0, 0.982, "early"),
        o("SOL", 20, "yes", 427.0, 0.983, "topup", 20.0),
        st("SOL", "yes", "yes", 0.982, 33.0), st("SOL", "yes", "yes", 0.983, 675.0),
    ]
    return recs


def test_p_early_topup():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    p = _write(d, "pinrun-live-20261114T192000Z.jsonl", run_pt([]))
    P = _report([p], now=NOW_PT)["P"]
    w = {e["coin"]: e for e in P["events"]}
    ck({c: w[c]["usd"] for c in w} == {"NEAR": 0.18, "BNB": 4.56, "DOGE": 1.12, "SOL": 0.09} and P["net_usd"] == 5.95
       and P["open"] == 0, "P with the old code's top-up: +0.18 + 4.56 + 1.12 + 0.09 = +5.95: %s"
       % {c: w[c]["usd"] for c in w})
    ck(w["NEAR"]["words"] == (
        "an early band bet skipped: 40 Yes at 98.5c with 40 s left (it would have been the market's early leg); it would "
        "have blocked pin's own early Yes leg at 38 s (100 at 98.2c: the band leg would have been the market's early leg); "
        "pin's top-up at 20 s (347 at 98.3c) filled the full bet, so the old code's would have bought 60 more (100 early "
        "less 40 band); it WON (pin's own settled record): it would have made $0.55; the old code's top-up (60 more) adds "
        "+$0.94 to that, hedges in; pin's blocked bets made $1.67 with their hedges; so the rule made $0.18"),
       "P at the full bet, won: %s" % w["NEAR"]["words"])
    ck("filled the full bet, so the old code's would have bought 30 more (60 early less 30 band); it LOST (pin's own "
       "settled record): it would have lost $29.67, $17.51 after pin's hedges win back 41%; the old code's top-up (30 "
       "more) adds -$13.51 to that, hedges in; pin's blocked bets lost $26.46 with their hedges; so the rule made $4.56"
       in w["BNB"]["words"], "P at the full bet x the band's 1.5, lost, the hedge shared by contracts: %s" % w["BNB"]["words"])
    ck("pin's top-up at 20 s (150 at 98.3c) was not at the full bet: how much more the old code's would have bought is "
       "not counted; it WON" in w["DOGE"]["words"] and "old code's top-up (" not in w["DOGE"]["words"],
       "P not at the full bet: said, not priced: %s" % w["DOGE"]["words"])
    ck("so the old code's would have bought 20 fewer (20 early less 40 band)" in w["SOL"]["words"]
       and "the old code's top-up (20 fewer) adds -$0.31 to that" in w["SOL"]["words"],
       "P with E under B: the old top-up smaller: %s" % w["SOL"]["words"])
    ck(P["extra"] == [
        "net +$5.95: the early band bets skipped would have lost $28.74 (3 won, 1 lost); pin's own bets they would have "
        "blocked lost $22.79",
        "gross, before pin's hedges win back 41% of a band loss: they would have lost $40.90; blocked: 4 early legs "
        "(top-ups: 3 priced -$12.88, 1 not at the full bet: not counted), 0 3rd fills, 0 later band legs"],
       "P's lines: X = 1.49 - 31.02 + 0.55 + 0.24 = -28.74, Y = 1.67 - 26.46 + 1.67 + 0.33 = -22.79, the top-ups "
       "0.94 - 13.51 - 0.31 = -12.88: %s" % P["extra"])
    # the helpers: the multiple (band, late, none), the full-bet test, nothing to price
    S = F._load([p])[1]
    by = {}
    for o_ in S.orders:
        by.setdefault(o_["ticker"], []).append(o_)
    b0 = next(r for r in S.b99s if r["ticker"] == PTT["BNB"])
    tp = F.p_topup(by[PTT["BNB"]], b0, F.p_blocked(by[PTT["BNB"]], b0), S.latest_start())
    ck(tp["at_full"] and tp["n"] == 30.0 and tp["early_held"] == 60.0 and tp["full"] == 670.5,
       "p_topup: 97c is the band's 1.5 x 447 = 670.5: %s" % {k: tp[k] for k in ("at_full", "n", "full")})
    ck(F.p_topup(by[PTT["BNB"]], b0, F.p_blocked(by[PTT["BNB"]], b0), dict(S.latest_start(), band_mults=[]))["at_full"]
       is False, "without the band multiple 670.5 is not 447: not at the full bet")
    late = [dict(o_, tau_at_send=8) if o_.get("leg") == "topup" else o_ for o_ in by[PTT["NEAR"]]]
    n0 = next(r for r in S.b99s if r["ticker"] == PTT["NEAR"])
    ck(F.p_topup(late, n0, F.p_blocked(late, n0), S.latest_start())["at_full"] is False
       and F.p_topup(late, n0, F.p_blocked(late, n0), dict(S.latest_start(), late_mult=1.0))["at_full"] is True,
       "inside late_tau the late 1.5 is the multiple: 447 is then not the full bet")
    ck(F.p_topup(by[PTT["NEAR"]], n0, [], S.latest_start()) is None
       and F.p_topup([x for x in by[PTT["NEAR"]] if x.get("leg") != "topup"], n0,
                     F.p_blocked(by[PTT["NEAR"]], n0), S.latest_start()) is None
       and F.p_topup(by[PTT["NEAR"]], dict(n0, full=None), F.p_blocked(by[PTT["NEAR"]], n0), S.latest_start())["at_full"]
       is False, "p_topup: nothing blocked or no top-up -> None; no full in the record -> not at the full bet")
    # a hedge of the market not settled yet: open, the top-up not priced either (BNB without its hedge's settled record)
    p2 = _write(d, "pinrun-live-20261114T192000Z.jsonl",
                [r for r in run_pt([]) if not (r.get("kind") == "settled" and r.get("want") == "yes"
                                               and r.get("ticker") == PTT["BNB"])])
    P2 = _report([p2], now=NOW_PT)["P"]
    ck(next(e for e in P2["events"] if e["coin"] == "BNB")["usd"] is None and P2["open"] == 1,
       "P open while the top-up side's hedge has not settled")


# ---- v-ladder-dayreset (the ladder's 2026-11-14 17:53:01Z start): Q, the money after a midnight reset ---------------
NOW_Q = 1794743400.0               # 2026-11-15T11:50:00Z = 6:50 AM ET


def _q_start(t):
    """A start record of the ladder code with the midnight reset (its start record carries start_reads)."""
    return dict(_lad_start(t, O_ARGV82, 0.82), start_reads=[200])


def _q_fill(t, tk, side, n):
    return _ev("live_fill", t, ticker=tk, paper_id=int(n), kid="k-q", side=side, px="0.9800", delta=n, filled=n,
               over_82=False)


def run_q(recs, end_start=True):
    """The ladder's order log: the old code's start, the midnight-reset code's start (11-14 12:53 PM ET), a day stop on
    11-14, its reset at midnight ET, the markets after it and (end_start) the ladder's next start at 4:50 AM ET 11-15.
    Each market's money is its live_settle pnl (98c bids: a win +2c a contract, a loss -98c)."""
    recs += [
        _lad_start("2026-11-14T10:00:14.128Z", O_ARGV82, 0.82),
        _q_start("2026-11-14T17:53:01.311Z"),
        # 11-14 3:00 PM ET: the ZEC loss that trips the day stop -- before the reset, not Q's
        _q_fill("2026-11-14T19:59:40.000Z", "KXZEC15M-26NOV141500-00", "no", 226),
        _settle("2026-11-14T20:00:23.000Z", "KXZEC15M-26NOV141500-00", "no", "yes", 226),
        _ev("day_stop", "2026-11-14T20:00:23.100Z", day="2026-11-14", day_pnl=-280.0),
        # a market filled before the reset that settles after it: its contracts are not the reset's
        _q_fill("2026-11-15T04:59:30.000Z", "KXNEAR15M-26NOV150000-00", "yes", 226),
        _ev("day_stop_reset", "2026-11-15T05:00:00.020Z", halt_day="2026-11-14", day="2026-11-15", halt_day_pnl=-280.0,
            day_stop=-270.46),
        _settle("2026-11-15T05:00:20.000Z", "KXNEAR15M-26NOV150000-00", "yes", "yes", 226),
        # after the reset: NEAR +4.52, ZEC +4.52, DOGE (two fills) +2.00, HYPE +1.00 = +12.04
        _q_fill("2026-11-15T05:14:40.000Z", "KXNEAR15M-26NOV150015-15", "yes", 226),
        _settle("2026-11-15T05:15:30.000Z", "KXNEAR15M-26NOV150015-15", "yes", "yes", 226),
        _q_fill("2026-11-15T05:29:40.000Z", "KXZEC15M-26NOV150030-30", "no", 226),
        _settle("2026-11-15T05:30:30.000Z", "KXZEC15M-26NOV150030-30", "no", "no", 226),
        _q_fill("2026-11-15T05:44:40.000Z", "KXDOGE15M-26NOV150045-45", "yes", 60),
        _q_fill("2026-11-15T05:44:45.000Z", "KXDOGE15M-26NOV150045-45", "yes", 40),
        _settle("2026-11-15T05:45:30.000Z", "KXDOGE15M-26NOV150045-45", "yes", "yes", 100),
        _q_fill("2026-11-15T09:44:50.000Z", "KXHYPE15M-26NOV150445-45", "no", 50),
        _settle("2026-11-15T09:45:30.000Z", "KXHYPE15M-26NOV150445-45", "no", "no", 50),
    ]
    if end_start:
        recs += [
            _q_start("2026-11-15T09:50:00.000Z"),
            # after the next start: the old code would have bid again too, not Q's
            _q_fill("2026-11-15T09:59:40.000Z", "KXXRP15M-26NOV150500-00", "yes", 226),
            _settle("2026-11-15T10:00:30.000Z", "KXXRP15M-26NOV150500-00", "yes", "yes", 226),
        ]
    return recs


def test_q_midnight_reset():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    pl = _write(d, "ladder-live-orders.jsonl", run_q([]), compact=True)
    rep = _report(ps + [pl], now=NOW_Q)
    Q = rep["Q"]
    ck(Q["name"] == "ladder midnight reset" and Q["since"] == "Nov 14 12:53 PM ET" and Q["not_live"] is None,
       "Q since the first ladder start with start_reads (not the old code's 5:00 AM one): %s" % Q["since"])
    ck(Q["engaged"] == 1 and Q["open"] == 0 and Q["net_usd"] == 12.04,
       "Q: one reset, the markets filled from it to the next start: 4.52 + 4.52 + 2.00 + 1.00 = +12.04 (the 11:59:30 PM "
       "fill and the 5:00 AM market after the next start not): %s" % {x: Q[x] for x in ("engaged", "open", "net_usd")})
    e = Q["events"][0]
    ck(e["usd"] == 12.04 and e["coin"] == "ladder" and e["et"] == "Nov 15 12:00 AM ET" and not e["open"]
       and e["words"] == ("the day stop of Nov 14 (the day at -$280.00) ended at midnight ET and the ladder bid again: "
                          "until its next start (Nov 15 4:50 AM ET) it made $12.04 on 4 markets; the old code would have "
                          "stayed halted"), "Q event: %s" % e)
    ck(Q["extra"] == ["money the ladder made after a midnight reset (the old code stayed halted): +$12.04 over 1 reset "
                      "since Nov 14 12:53 PM ET (4 markets settled)"], "Q's line: %s" % Q["extra"])
    ck(Q["what"] == "a ladder day stop ends at the next ET midnight (before, it held until the ladder's process ended, up "
                    "to 7 days)", "Q what: %s" % Q["what"])
    T = F.totals(list(rep.values()))
    ck(T["engaged"] == 18 and T["open"] == 2 and T["net_usd"] == round(sum(c["net_usd"] for k, c in rep.items()
                                                                           if k not in ("J", "O")), 2)
       and T["groups"]["ladder"] == round(123.40 + rep["Q"]["net_usd"], 2),
       "Q is in the totals and the ladder's group (17 + 1 engagements; O withdrawn is not): %s" % T)
    # still running (no next start yet), a market not settled yet, and a second reset the next night: each reset's span
    # ends at the next one; the open span shows the money so far
    recs = run_q([], end_start=False) + [
        _q_fill("2026-11-15T09:59:40.000Z", "KXXRP15M-26NOV150500-00", "yes", 226),
        _ev("day_stop_reset", "2026-11-16T05:00:00.010Z", halt_day="2026-11-15", day="2026-11-16", halt_day_pnl=-275.0,
            day_stop=-270.46),
        _q_fill("2026-11-16T05:14:40.000Z", "KXZEC15M-26NOV160015-15", "no", 226),
        _settle("2026-11-16T05:15:30.000Z", "KXZEC15M-26NOV160015-15", "no", "no", 226)]
    pl = _write(d, "ladder-live-orders.jsonl", recs, compact=True)
    now2 = 1794806400.0                # 2026-11-16T05:20:00Z
    Q2 = _report([pl], now=now2)["Q"]
    e1, e2 = Q2["events"]
    ck(Q2["engaged"] == 2 and Q2["open"] == 2 and Q2["net_usd"] == 16.56
       and e1["usd"] == 12.04 and e1["open"] and e1["words"].startswith(
           "the day stop of Nov 14 (the day at -$280.00) ended at midnight ET and the ladder bid again: until the next reset "
           "(Nov 16 12:00 AM ET) it made $12.04 on 4 markets (1 more not settled yet)")
       and e2["usd"] == 4.52 and e2["open"] and "so far (still running) it made $4.52 on 1 market;" in e2["words"],
       "Q two resets, one running: [reset 1, reset 2) +12.04 with XRP unsettled, [reset 2, now) +4.52: %s" % [
           (x["usd"], x["words"]) for x in Q2["events"]])
    ck(Q2["extra"] == ["money the ladder made after a midnight reset (the old code stayed halted): +$16.56 over 2 resets "
                       "since Nov 14 12:53 PM ET (5 markets settled) · 2 open"], "Q's line, open: %s" % Q2["extra"])
    # 'no reset yet', and not live before the midnight-reset code
    pl = _write(d, "ladder-live-orders.jsonl", run_q([])[:2], compact=True)
    Q3 = _report([pl], now=NOW_Q)["Q"]
    ck(Q3["since"] == "Nov 14 12:53 PM ET" and Q3["engaged"] == 0 and Q3["net_usd"] == 0.0
       and Q3["extra"] == ["money the ladder made after a midnight reset (the old code stayed halted): no reset yet since "
                           "Nov 14 12:53 PM ET"], "Q live, no reset: %s" % Q3["extra"])
    pl = _write(d, "ladder-live-orders.jsonl", run_q([])[:1], compact=True)
    Q4 = _report([pl], now=NOW_Q)["Q"]
    ck(Q4["since"] is None and Q4["not_live"] == F.Q_NOT_LIVE == "not live yet (comes with the ladder's first start on "
       "the midnight-reset code)" and Q4["engaged"] == 0, "Q not live on the old code: %s" % Q4["not_live"])
    ck(F.q_since([{"_epoch": 1.0}, {"_epoch": 2.0, "start_reads": [200]}]) == 2.0 and F.q_since([{"_epoch": 1.0}]) is None
       and F._q_day("2026-11-14") == "Nov 14" and F._q_day("x") == "x", "q_since, _q_day")


def test_retired_rows():
    """change["retired"]: the short words of a change off for good while it is not live -- N shelved, O withdrawn (the
    phone folds them into one line; their whole words stay in not_live) -- None on every other row, and None once N
    goes live or O is not withdrawn."""
    d = tempfile.mkdtemp(prefix="fixes-test-")
    ps = write_logs(d)
    pl = _write(d, "ladder-live-orders.jsonl", run_q([]), compact=True)
    rep = _report(ps + [pl], now=NOW_Q)
    ck(rep["N"]["retired"] == F.N_RETIRED == "shelved 11-09" and rep["N"]["not_live"] == F.N_NOT_LIVE
       and rep["O"]["retired"] == F.O_RETIRED == "withdrawn 11-14, stays at 82%" and rep["O"]["not_live"] == F.O_NOT_LIVE
       and all(c["retired"] is None for k, c in rep.items() if k not in "NO"),
       "retired: N and O only: %s" % {k: c["retired"] for k, c in rep.items()})
    # the 100% start all the same: the short words say it too, never the '82%' that is not true
    pl = _write(d, "ladder-live-orders.jsonl", run_o([]), compact=True)
    O = _report(ps + [pl], now=NOW_O)["O"]
    ck(O["retired"] == ("withdrawn 11-14; but the ladder's latest start (Nov 15 4:50 AM ET) runs --commit-frac 1.0: "
                        "nothing of it is counted here") and "82%" not in O["retired"], "O retired on 1.0: %s" % O["retired"])
    with o_live():
        ck(_report(ps + [pl], now=NOW_O)["O"]["retired"] is None, "O not withdrawn: not retired")
    # N live (a start on --hedge-belief 0.60): not retired
    pn = _write(d, "pinrun-live-20261109T000000Z.jsonl", [_r("start", "2026-11-09T00:00:00Z", hedge_belief=0.60)])
    ck(_report(ps + [pn], now=NOW)["N"]["retired"] is None, "N live: not retired")


WS_T0 = "2026-10-28T01:07:25Z"
NOW_WS = 1793217600.0              # 2026-10-28T20:00:00Z = 4:00 PM ET (EDT): the 3 PM market is an hour past its close
WS_CS = {"DOGE": 1793153700, "BNB": 1793154600, "NEAR": 1793155500, "ZEC": 1793156400, "BTC": 1793185200,
         "SOL2": 1793200500, "HYPE": 1793214000}


def _ws_tk(c, cs):
    import time as _t
    g = _t.gmtime(cs - 4 * 3600)                            # the close on the Eastern (EDT) clock
    return "KX%s15M-26OCT%02d%02d%02d-%02d" % (c.rstrip("2"), g.tm_mday, g.tm_hour, g.tm_min, g.tm_min)


def run_ws(recs):
    """v-wrongside (LS20) from its first run (10-28 01:07:25Z): WS. pin's own buys at a 96-97c first ask (the bucket
    every refusal here falls in): SOL won 3.00 on a bet of 100 and ETH 3.60 on 120 contracts (never hedged: 0.030 and
    0.036 a contract of bet, mean 0.033), XRP lost, hedged (held 1.0); held 1.0, 1.2, 1.0: 1.0667 a contract of bet.
    The refusals (the coin's bet 100; each refusal's own take 5, ZEC's 50), hand-worked (Kalshi's fee ceil(7 x p x
    (1 - p) x n) / 100). A market whose hedge fires holds what it could by the hedge's second (ws_position: the
    refusal's take + ONE top-up at the first later second pin's gates pass, at most the bucket's 106.67) and no more:
      DOGE  won (the trajectory's last second), no hedge: 100 x 0.033 = +3.30 without the rule: -3.30
      BNB   FLIPPED: the belief hedge (our belief 0.30 under 0.40 at 12 s) after a top-up at 19 s (fair 0.999, ask 97c,
            500 on the book): 5 at 96.8c (-4.84 - 0.02) + 101.67 at 97c (-98.62 - 0.21) lost 103.69; 106.67 No at 55c
            got back 48.00 - 1.85 = 46.15: -57.54 without the rule: +57.54
      NEAR  won, a 7 sd jump against our No at 10 s while the jump hedge is live, after the same top-up: 5 at 96.5c
            (0.175 - 0.02) + 101.67 at 97c (3.05 - 0.21) = 2.995; the hedge 106.67 at 20c: -21.33 - 1.20: -19.54: +19.54
      ZEC   (the 11-14 review's ZEC 11-01) refused 50 at 96.1c with 17 s left, the jump hedge at 15 s; at 16 s our ask is
            99.5c (over the 98c ceiling): no top-up, so 50 is all it holds: 50 x 3.9c = 1.95 - 0.14 = 1.81, won; the
            hedge 50 Yes at 14c: -7.00 - 0.43 = -7.43: -5.62 without the rule: +5.62 (the bucket's 106.67 would say
            3.30 - 15.83 = -12.53)
      BTC   a 7:00 AM close at 97c with the cheap window on: K would have skipped it: $0
      SOL2  the same jump as NEAR after the jump hedge went to shadow: no hedge, +3.30: -3.30
      HYPE  open (no result yet)
    WS net = -3.30 + 57.54 + 19.54 + 5.62 + 0 - 3.30 = +76.10."""
    st = dict(code_sha="e51a465d8b5c", wrongside_rise_c=1.0, hedge_jump=6.0, hedge_belief=0.40, hedge_slip=0.10,
              size=100.0)

    def ref(c, want, price, tau=20, cs=None, size=5.0):
        cs = cs or WS_CS[c]
        return _r("refused", _ts(cs - tau), gate="wrong_side", ticker=_ws_tk(c, cs), close_s=cs, size_now=100.0,
                  leg="full", tau=tau, price=price, fair=0.999, want=want, spot=1.0, strike=1.0, mid_rise_c=-2.0,
                  min_rise_c=1.0, lookback_s=5.0, size=size, budget_left=200.0)
    c0 = 1793152800                                         # 10-27 10:00 PM ET: pin's own markets
    recs += [
        _r("start", WS_T0, **st),
        _o(_ts(c0 - 20), _ws_tk("SOL", c0), "yes", 100.0, 0.965, 20),
        _r("settled", _ts(c0 + 20), ticker=_ws_tk("SOL", c0), want="yes", result="yes", cost=0.965, pnl_c=300.0),
        _o(_ts(c0 - 19), _ws_tk("ETH", c0), "no", 120.0, 0.966, 19),
        _r("settled", _ts(c0 + 20), ticker=_ws_tk("ETH", c0), want="no", result="no", cost=0.966, pnl_c=360.0),
        _o(_ts(c0 - 18), _ws_tk("XRP", c0), "yes", 100.0, 0.962, 18),
        _r("hedge", _ts(c0 - 10), ticker=_ws_tk("XRP", c0), side="no", price=0.30, n=100.0, asked=100.0,
           status="executed", live=True),
        _r("settled", _ts(c0 + 20), ticker=_ws_tk("XRP", c0), want="yes", result="no", cost=0.962, pnl_c=-9620.0),
        _r("settled", _ts(c0 + 21), ticker=_ws_tk("XRP", c0), want="no", result="no", cost=0.30, pnl_c=6855.0),
        ref("DOGE", "yes", 0.965), ref("DOGE", "yes", 0.965, tau=15),          # refused once = refused for the close
        ref("BNB", "yes", 0.968), ref("NEAR", "no", 0.965), ref("ZEC", "no", 0.961, tau=17, size=50.0),
        _r("start", "2026-10-28T10:00:00Z", cheap_window=[6.0, 10.0, 0.98], **st),
        ref("BTC", "yes", 0.97),
        _r("start", "2026-10-28T12:00:00Z", cheap_window=[6.0, 10.0, 0.98], hedge_jump_shadow=6.0,
           **dict(st, hedge_jump=None)),
        ref("SOL2", "no", 0.965), ref("HYPE", "yes", 0.97),
    ]
    return recs


def traj_ws(recs):
    """The trajectory of run_ws's refused markets, one record a second from the refusal (tau 20) to tau 1: fair is the
    Yes probability; want the favoured side (its ask; opp_ask the other side's)."""
    def tj(c, tau, fair, spot=100.0, sigma=0.01, yn=None):
        cs = WS_CS[c]
        want = "yes" if fair >= 0.5 else "no"
        ya, na = (0.97, 0.03) if fair >= 0.5 else (0.45, 0.55)
        if fair < 0.5 and c in ("NEAR", "SOL2"):
            ya, na = (0.20, 0.97)                             # our No favoured: its ask 97c, the Yes hedge side 20c
        if yn is not None:
            ya, na = yn
        ask, opp = (ya, na) if want == "yes" else (na, ya)
        return _r("traj", _ts(cs - tau), ticker=_ws_tk(c, cs), close_s=cs, tau=tau, want=want, held=None, fair=fair,
                  conf=(fair if want == "yes" else 1.0 - fair), spot=spot, strike=100.0, sigma=sigma, ask=ask,
                  ask_size=500.0, opp_ask=opp, opp_size=500.0, gate="wrong_side_skip", near=True)
    for tau in range(20, 0, -1):
        recs.append(tj("DOGE", tau, 0.999 if tau > 1 else 1.0))
        recs.append(tj("BNB", tau, 0.999 if tau > 12 else (0.30 if tau > 1 else 0.0)))
        for c in ("NEAR", "SOL2"):
            recs.append(tj(c, tau, 0.001 if tau > 1 else 0.0, spot=(100.0 if tau > 10 else 100.07)))
        if tau <= 17:                                         # ZEC: our No at 99.5c (over the ceiling) until the jump
            recs.append(tj("ZEC", tau, 0.001 if tau > 1 else 0.0, spot=(100.0 if tau > 15 else 100.07),
                           yn=((0.005, 0.995) if tau > 15 else (0.14, 0.97))))
    return sorted(recs, key=lambda r: r["t"])


def write_ws(d):
    p = _write(d, "pinrun-live-20261028T010725Z.jsonl", run_ws([]))
    _write(d, "pintraj-live-20261028T010725Z.jsonl", traj_ws([]))
    return p


def test_ws_wrong_side():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    p = write_ws(d)
    WS = _report([p], now=NOW_WS)["WS"]
    ck(WS["since"] == "Oct 27 9:07 PM ET" and WS["engaged"] == 7 and WS["open"] == 1 and WS["net_usd"] == 76.10,
       "WS: seven markets refused (DOGE's second refusal is the same market), HYPE open: -3.30 + 57.54 + 19.54 + 5.62 + 0 "
       "- 3.30 = +76.10: %s" % {k: WS[k] for k in ("since", "engaged", "open", "net_usd")})
    w = {e["coin"]: e for e in WS["events"]}
    ck(w["DOGE"]["usd"] == -3.30 and w["DOGE"]["words"] == (
        "refused a first Yes buy at 96.5c with 20 s left (the index across the strike, our mid down 2.0c in 5 s); it WON "
        "(the index at the close): the buy would have made $3.30 (the bet of 100 at pin's own 0.0330 a contract on won "
        "markets first bought at that price), so the rule gave up that"), "WS won: %s" % w["DOGE"]["words"])
    ck(w["BNB"]["usd"] == 57.54 and "it FLIPPED (the index at the close): the buy would have lost $57.54 (106.67 contracts, "
       "all it could hold by its hedge's second (the refusal's 5 at 96.8c + a 101.67 top-up at 97.0c; pin buys no more of a "
       "side it has hedged), lost; its belief hedge at 55.0c with 12 s left got back $46.15), so the rule saved that"
       in w["BNB"]["words"], "WS flipped, with the belief hedge: %s" % w["BNB"]["words"])
    ck(w["NEAR"]["usd"] == 19.54 and "its jump hedge at 20.0c with 10 s left cost $22.53" in w["NEAR"]["words"]
       and w["SOL"]["usd"] == -3.30 and "hedge" not in w["SOL"]["words"],
       "WS: the jump hedge while it was live, never once it went to shadow: %s | %s" % (w["NEAR"]["words"], w["SOL"]["words"]))
    # the 11-14 review's ZEC 11-01: hedged two seconds after a 50-contract refusal with no top-up possible in between
    # (our ask over the ceiling): the position and its hedge are the 50, never the bucket's 106.67 (that said +12.53)
    ck(w["ZEC"]["usd"] == 5.62 and "the buy would have lost $5.62 (50 contracts, all it could hold by its hedge's second "
       "(the refusal's 50 at 96.1c; pin buys no more of a side it has hedged), won; its jump hedge at 14.0c with 15 s left "
       "cost $7.43)" in w["ZEC"]["words"], "WS: the hedge sized at what the buy could hold by its second: %s" % w["ZEC"]["words"])
    ck(w["BTC"]["usd"] == 0.0 and "the cheap window would have skipped it too" in w["BTC"]["words"]
       and w["HYPE"]["usd"] is None and w["HYPE"]["words"].endswith("; not settled yet"), "WS: K's market $0, one open")
    ck(WS["extra"][0] == "without the rule: the 5 settled refusals would have lost $76.10 (4 won, 1 flipped, 3 with the hedge "
                         "the trajectory says would have fired) · 1 the cheap window would have skipped anyway ($0) "
                         "· 1 open"
       and WS["extra"][1].startswith("priced on pin's own fills since 10-28: a win at")
       and "a replayed hedge covers only what the buy could hold by its second, the refusal's own contracts + one top-up "
           "the trajectory allows (pin buys no more of a side it has hedged), 3 so sized (assumptions" in WS["extra"][1],
       "WS extra: %s" % WS["extra"])
    ck(WS["what"].startswith("no first buy with the index across the strike unless our mid rose 1c in 5 s"), WS["what"])
    S = F._load([p])[1]
    stats = F.ws_stats(S, F.SINCE_WS)
    u, h, n = F.ws_rates(stats, (0.96, 0.97))
    c0 = 1793152800
    u2, h2, n2 = F.ws_rates(F.ws_stats(S, F.SINCE_WS, c0 - 18.5), (0.96, 0.97))
    ck(abs(u - 0.033) < 1e-9 and abs(h - 3.2 / 3) < 1e-9 and n == 2 and F.ws_bucket(0.965) == (0.96, 0.97)
       and F.ws_bucket(0.5) == (0.0, 0.94) and F.ws_bucket(0.995) == (0.9801, 1.0)
       and abs(u2 - 0.033) < 1e-9 and abs(h2 - 1.1) < 1e-9 and n2 == 2,
       "ws_stats / ws_rates / ws_bucket (until: XRP's first fill after it is out, held 1.0, 1.2): %s %s %s | %s %s %s"
       % (u, h, n, u2, h2, n2))
    rules = F.m_rules({})
    hz = ("jump", 15, 0.14, 1.0, float(WS_CS["ZEC"] - 15))
    ck(F.ws_position([], {"price": 0.961}, "no", hz, 106.0, rules) is None
       and F.ws_position([], {"price": 0.961, "size": 50.0}, "no", None, 106.0, rules) is None
       and F.ws_position([], {"price": 0.961, "size": 500.0, "_epoch": 0.0}, "no", hz, 106.0, rules) == [(106.0, 0.961)],
       "ws_position: no size (an older record) or no hedge -> None (the bucket's n_held stands); never past n_held")
    # the undo: pin's fills after it never move the rule's figure (the 11-14 review: -31.00 went to -31.41 once fills
    # after the undo came in): a start without the rule, then a won 96.5c market that made 10.00 on a bet of 100
    d2 = tempfile.mkdtemp(prefix="fixes-test-")
    later = 1793217600 + 900                                 # 10-28 4:15 PM ET
    tkl = _ws_tk("ADA", later)
    p2 = _write(d2, "pinrun-live-20261028T010725Z.jsonl", run_ws([]) + [
        _r("start", "2026-10-28T19:55:00Z", code_sha="e51a465d8b5c", wrongside_rise_c=0.0, hedge_jump=6.0,
           hedge_belief=0.40, hedge_slip=0.10, size=100.0),
        _o(_ts(later - 20), tkl, "yes", 100.0, 0.965, 20),
        _r("settled", _ts(later + 20), ticker=tkl, want="yes", result="yes", cost=0.965, pnl_c=1000.0)])
    _write(d2, "pintraj-live-20261028T010725Z.jsonl", traj_ws([]))
    WS2 = _report([p2], now=later + 3600)["WS"]
    ck(WS2["net_usd"] == 76.10 and WS2["undo"] is not None and WS2["undo"]["engaged"] == 0
       and WS2["extra"][1].startswith("priced on pin's own fills since 10-28 to the undo: a win at"),
       "WS's rule figure off pin's fills up to the undo only (ADA's +10.00 after it would make it %s): %s | %s"
       % (WS2["net_usd"], WS2["undo"], WS2["extra"][1][:60]))
    # the trajectory archived (log_rotate, two days on): read through ONCE, its rows kept in results\fixes_traj_cache.json
    # keyed by the archive's name, size and mtime; a fresh process (memory caches gone) reads no archive at all
    gz = archive_traj(d, "pintraj-live-20261028T010725Z.jsonl")
    opened, real_open = [], F._lf.open

    def counting(path, *a, **k):
        if "pintraj-live-" in str(path):
            opened.append(str(path))
        return real_open(path, *a, **k)
    F._lf.open = counting
    try:
        F._TRAJ_WIN.clear()
        F._TRAJ_DISK.update(path=None, key=None, data=None)
        W1 = _report([p], now=NOW_WS)["WS"]
        n1 = list(opened)
        F._TRAJ_WIN.clear()
        F._TRAJ_DISK.update(path=None, key=None, data=None)
        W2 = _report([p], now=NOW_WS)["WS"]
    finally:
        F._lf.open = real_open
    cache = os.path.join(d, F.TRAJ_CACHE)
    ck(W1["net_usd"] == W2["net_usd"] == 76.10 and n1 == [gz] and opened == [gz] and os.path.getsize(cache) < 20000,
       "WS off the archive: read once (%s), a fresh process reads the persisted rows (%d bytes), never the archive: %s"
       % (n1, os.path.getsize(cache), opened))


def run_u(recs):
    """The 11-14 undo (results\\pin_undo1114.ps1): a run with M, K and WS on (call B, the cheap window, the wrong-side
    skip) and B's cap, then a start with extra_coin / late_extra 1, bank_brake 3.00, no cheap_window, wrongside_rise_c 0
    and no hedge_jump_max. From then on M, K and WS score the UNDO against keeping the rule (hand-worked):
      M   XRP (11 AM close) filled 100 when BTC had filled 150 of the 2 x 100: 50 past the budget, the deepest of the
          order off its signal's ladder (10 at 96c + 40 at 97c), won: 0.37 + 1.11 = +1.48 the undo made
      K   ETH (7:30 AM close), a first buy at 97c: the rule would have skipped it; the market made +2.00
      WS  SOL (8 AM close) at 97c on the wrong side, our mid up 0.2c: both rules would have skipped it -- WS's (the
          earlier gate): the market LOST -50.00; DOGE (2 PM) wrong side, mid down 1c: +1.50; ADA wrong side but mid up
          1.5c (the rule let it through) and NEAR on the right side: not counted. WS's undo -48.50.
      SOL filled 250, 50 past the 2-bet budget: a 3rd bet, but in a market WS's undo counts whole (its -50.00 holds
          those 50): M leaves it to WS (counted, it would be -48.61 more, twice).
    The rules' own nets stay $0.00 (nothing while they were on); the undos' money is beside them, never in them."""
    on = dict(code_sha="0925x0000000", extra_coin=0.0, late_extra=0.0, bank_brake=4.5, late_extra_tau=15,
              cheap_window=[6.0, 10.0, 0.98], wrongside_rise_c=1.0, hedge_jump_max=8.0, hedge_jump_shadow=6.0,
              hedge_jump=None, size=100.0)
    off = dict(on, extra_coin=1.0, late_extra=1.0, bank_brake=3.0, cheap_window=None, wrongside_rise_c=0.0,
               hedge_jump_max=None)

    def sig(t, tk, want, price, tau, wrong=False, rise=None, ladder=None, bl=200.0):
        return _r("signal", t, live=True, ticker=tk, want=want, price=price, tau=tau, size=100.0, take_n=100.0,
                  leg="full", budget_left=bl, fair=(0.999 if want == "yes" else 0.001), spot_wrong=wrong, mid_rise_c=rise,
                  ladder=ladder or [[price, 500.0]])

    def settle(t, tk, want, res, pnl):
        return _r("settled", t, ticker=tk, want=want, result=res, cost=0.97, pnl_c=pnl)
    recs += [
        _r("start", "2026-11-15T10:00:00Z", **on),
        _r("start", "2026-11-15T11:00:00Z", **off),
        sig("2026-11-15T12:29:40Z", "KXETH15M-26NOV150730-30", "yes", 0.97, 20),
        _o("2026-11-15T12:29:40Z", "KXETH15M-26NOV150730-30", "yes", 100.0, 0.97, 20),
        settle("2026-11-15T12:30:20Z", "KXETH15M-26NOV150730-30", "yes", "yes", 200.0),
        sig("2026-11-15T12:59:40Z", "KXSOL15M-26NOV150800-00", "yes", 0.97, 20, wrong=True, rise=0.2),
        _o("2026-11-15T12:59:40Z", "KXSOL15M-26NOV150800-00", "yes", 250.0, 0.97, 20),
        settle("2026-11-15T13:00:20Z", "KXSOL15M-26NOV150800-00", "yes", "no", -5000.0),
        _o("2026-11-15T15:59:30Z", "KXBTC15M-26NOV151100-00", "yes", 150.0, 0.99, 30),
        sig("2026-11-15T15:59:40Z", "KXXRP15M-26NOV151100-00", "yes", 0.985, 20,
            ladder=[[0.96, 60.0], [0.97, 200.0]], bl=50.0),
        _o("2026-11-15T15:59:40Z", "KXXRP15M-26NOV151100-00", "yes", 100.0, 0.968, 20),
        settle("2026-11-15T16:00:20Z", "KXBTC15M-26NOV151100-00", "yes", "yes", 150.0),
        settle("2026-11-15T16:00:21Z", "KXXRP15M-26NOV151100-00", "yes", "yes", 290.0),
        sig("2026-11-15T18:59:40Z", "KXDOGE15M-26NOV151400-00", "no", 0.985, 20, wrong=True, rise=-1.0),
        _o("2026-11-15T18:59:40Z", "KXDOGE15M-26NOV151400-00", "no", 50.0, 0.985, 20),     # 50 + 50 + 50: inside the
        settle("2026-11-15T19:00:20Z", "KXDOGE15M-26NOV151400-00", "no", "no", 150.0),       # close's 2 x 100
        sig("2026-11-15T18:59:41Z", "KXADA15M-26NOV151400-00", "no", 0.985, 20, wrong=True, rise=1.5),
        _o("2026-11-15T18:59:41Z", "KXADA15M-26NOV151400-00", "no", 50.0, 0.985, 20),
        settle("2026-11-15T19:00:20Z", "KXADA15M-26NOV151400-00", "no", "no", 150.0),
        sig("2026-11-15T18:59:42Z", "KXNEAR15M-26NOV151400-00", "no", 0.985, 20, wrong=False, rise=-3.0),
        _o("2026-11-15T18:59:42Z", "KXNEAR15M-26NOV151400-00", "no", 50.0, 0.985, 20),
        settle("2026-11-15T19:00:20Z", "KXNEAR15M-26NOV151400-00", "no", "no", 150.0),
    ]
    return recs


def test_undo_scores_against_keeping_the_rule():
    d = tempfile.mkdtemp(prefix="fixes-test-")
    p = _write(d, "pinrun-live-20261115T100000Z.jsonl", run_u([]))
    rep = _report([p], now=1794780000.0)                   # 2026-11-15T21:00:00Z
    M, K, WS, B = rep["M"], rep["K"], rep["WS"], rep["B"]
    for c in (M, K, WS):
        ck(c["undo"] is not None and c["undo"]["since"] == "Nov 15 6:00 AM ET" and c["rule_usd"] == 0.0
           and c["engaged"] == 0, "%s: undone at the start without it, nothing while the rule was on: %s" % (c["id"], c["undo"]))
    ck(M["undo"]["net_usd"] == 1.48 and M["net_usd"] == 0.0 and M["undo"]["engaged"] == 1
       and M["undo"]["line"] == ("with the rule: +$0.00 (to Nov 15 6:00 AM ET) · since the undo (vs keeping it): +$1.48 "
                                 "on 1 bet · 1 more in a market K's or WS's row counts whole")
       and M["extra"][-1] == "since the undo: 1 more in a market K's or WS's row counts whole"
       and not any(x.startswith("with the rule") for x in M["extra"])
       and M["undo"]["events"][0]["words"] == (
           "since the undo (vs keeping it): a Yes buy filled 50 past the 2-bet budget at 96.8c with 20 s left (the 3rd bet "
           "the rule blocked); the bet won: the undo made $1.48"),
       "M after the undo: the 50 past the budget (10 at 96c + 40 at 97c, won); SOL's 3rd bet is WS's; the row's net "
       "stays the rule's $0.00: %s | %s" % (M["extra"], M["undo"]))
    ck(K["undo"]["net_usd"] == 2.0 and K["net_usd"] == 0.0 and [e["coin"] for e in K["undo"]["events"]] == ["ETH"]
       and K["undo"]["line"] == ("with the rule: +$0.00 (to Nov 15 6:00 AM ET) · since the undo (vs keeping it): +$2.00 "
                                 "on 1 market · 1 more the wrong-side rule would have skipped first: in WS's row")
       and K["extra"][-1] == "since the undo: 1 more the wrong-side rule would have skipped first: in WS's row",
       "K after the undo: ETH's whole market; SOL is WS's: %s | %s" % (K["undo"]["line"], K["extra"]))
    ck(WS["undo"]["net_usd"] == -48.5 and sorted(e["coin"] for e in WS["undo"]["events"]) == ["DOGE", "SOL"]
       and WS["net_usd"] == 0.0 and WS["rule_usd"] == 0.0 and "the market LOST: the undo cost $50.00" in
       next(e for e in WS["undo"]["events"] if e["coin"] == "SOL")["words"],
       "WS after the undo: SOL (both rules: WS's) and DOGE; ADA (rose 1.5c) and NEAR (right side) not: %s" % WS["undo"])
    ck(B["extra"][0] == "the cap was DROPPED Nov 15 6:00 AM ET (pin started without --hedge-jump-max): nothing to count since",
       "B says its cap was dropped: %s" % B["extra"])
    T = F.totals(list(rep.values()))
    ck(T["engaged"] == 0 and T["open"] == 0 and T["net_usd"] == round(123.40 + 27.9, 2)
       and T["undo_usd"] == round(1.48 + 2.0 - 48.5, 2) and T["undo_engaged"] == 4 and T["undo_open"] == 0
       and T["undos"] == ["K", "M", "WS"],
       "totals: the rules' nets (vs never) in the net, the undos' money (vs keeping them) beside it, never in it: %s" % T)
    # the 11-14 review: summed, the undo's expected wins would drift an undone rule's net toward + (and turn it green);
    # against never making it, the undo adds nothing (pin trades as if the rule had never been)
    ck(M["net_usd"] == M["rule_usd"] and K["net_usd"] == K["rule_usd"] and WS["net_usd"] == WS["rule_usd"],
       "an undone rule's net is its rule_usd: %s" % [(c["id"], c["net_usd"], c["rule_usd"]) for c in (M, K, WS)])
    ck(F.undo_since([]) is None and F.span_at([], 1.0) is None
       and F.rule_spans(F._load([p])[1], F._m_on)[0][2] is True, "span helpers")


def test_m_own_records():
    """M reads each order's OWN records -- its signal (the latest before it in the file), the taper record between that
    signal and the order -- never a same-second record of another order (the 11-14 retro: ETH 11-12 14:30 grabbed an
    earlier order's sweep record by ticker and second and was dropped, -$38.58 missing)."""
    d = tempfile.mkdtemp(prefix="fixes-test-")
    cs = 1794175200                                          # 11-08 5:00 PM ET
    tk = "KXETH15M-26NOV081700-00"
    t0 = _ts(cs - 10)
    recs = [_r("start", "2026-11-08T21:00:00Z", **M_START),
            _r("autosize", "2026-11-08T21:00:01Z", old=20.0, new=100.0),
            _r("signal", t0, live=True, ticker=tk, want="no", price=0.87, tau=10, leg="full", budget_left=60.0,
               fair=0.001, ladder=[[0.87, 20.0], [0.88, 400.0]]),
            _r("taper", t0, ticker=tk, want="no", tau=10, flat=420.0, tapered=20.0, limit=0.98),
            dict(_order(t0, tk, "no", 20.0, 0.87, 10, limit=0.98), client_order_id="pin-1"),
            _r("signal", t0, live=True, ticker=tk, want="no", price=0.88, tau=10, leg="full", budget_left=40.0,
               fair=0.001, ladder=[[0.88, 400.0]]),
            _r("taper", t0, ticker=tk, want="no", tau=10, flat=400.0, tapered=300.0, limit=0.98),
            dict(_order(t0, tk, "no", 40.0, 0.88, 10, limit=0.98), client_order_id="pin-2"),
            _r("taper", t0, ticker=tk, want="no", tau=10, flat=360.0, tapered=5.0, limit=0.98),   # a later order's
            _r("settled", _ts(cs + 20), ticker=tk, want="no", result="no", cost=0.88, pnl_c=700.0)]
    p = _write(d, "pinrun-live-20261108T210000Z.jsonl", recs)
    M = _report([p], now=NOW_M)["M"]
    # the second order: bound (40 of 40), the late window; its own taper 300: the sweep min(100, 300, 40 + 100) = 100,
    # this side holds 20, so at most 1.5 x 100 - 20: 100, 60 more, off the book past its 40: 60 at 88c, won: 7.20 - fee
    # ceil(7 x 60 x 0.88 x 0.12 = 44.35) / 100 = 0.45: 6.75 given up
    ck(M["engaged"] == 1 and M["net_usd"] == -6.75 and "the sweep would have bought 60 more (at 88.0c" in M["events"][0]["words"],
       "M: the order's own taper record, not a later one of the same second: %s" % M["events"])


def test_fixed_rows():
    rep = _report([])
    LAD, STOP = rep["LAD"], rep["STOP"]
    ck(LAD["fixed"] and LAD["net_usd"] == 123.40 and LAD["since"] == "Oct 22 11:40 AM ET" and LAD["group"] == "ladder"
       and LAD["events"][0]["words"].startswith("all four vs the Option C argv")
       and "measured to Nov 14 1:16 PM ET" in LAD["events"][0]["words"]
       and LAD["extra"][0].startswith("the 11-14 replay's central fill model; $119.42 to $140.63"),
       "LAD: the ladder's four changes against Option C, measured once: %s" % LAD)
    ck(STOP["fixed"] and STOP["net_usd"] == 27.9 and STOP["group"] == "stops"
       and sorted(e["coin"] for e in STOP["events"]) == ["FX", "forecaster", "jump band", "race"]
       and [e["usd"] for e in STOP["events"]] == [-20.0, 23.0, 31.6, -6.7]
       and STOP["extra"][0].startswith("rests on the moved money earning ~2.2%/day"),
       "STOP: the four stops, measured once, their assumption first: %s" % STOP)
    T = F.totals(list(rep.values()))
    ck(T["engaged"] == 0 and T["net_usd"] == 151.3 and T["groups"]["ladder"] == 123.4 and T["groups"]["stops"] == 27.9,
       "the measured-once rows are in the net and their groups, never in the engagements: %s" % T)


def test_load_keeps_the_ladder_scan():
    """_load keeps at most LOAD_KEEP (2) of its own entries (each a state of pin's logs, ~41 MB parsed on the server's:
    the live log grows between asks), the oldest dropped first, never a ladder scan's (O / Q read the ladder's 26 MB log
    incrementally; wiping it re-reads it all)."""
    d = tempfile.mkdtemp(prefix="fixes-test-")
    pp = write_logs(d)[-1]
    pl = _write(d, "ladder-live-orders.jsonl", run_q([]), compact=True)
    F._CACHE.clear()
    F.report(paths=[pp, pl], now=NOW_Q)
    sc = F._CACHE[("ladder", pl)]
    for i in range(12):
        with open(pp, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(_r("heartbeat", "2026-11-05T06:59:%02dZ" % i)) + "\n")
        F.report(paths=[pp, pl], now=NOW_Q)
    mine = [k for k in F._CACHE if k and isinstance(k[0], tuple)]
    ck(F._CACHE.get(("ladder", pl)) is sc and len(mine) == F.LOAD_KEEP == 2 and mine[-1][0][1] == os.path.getsize(pp),
       "12 more states of pin's logs: _load keeps the newest 2 (%d), the ladder scan the same object" % len(mine))


if __name__ == "__main__":
    sys.exit(_kit.run(dict(globals()), "test_fixes"))
