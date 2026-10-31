"""test_report.py -- the per-bot and all-bots reports on planted worlds: money by window, the pot %, the cache, failures,
the weather pot, the jump band and the shown bots (v-tg-active).

v-tg-rebuild step 7 (2026-10-30): moved out of botstats.py's one-piece self-test (its checks verbatim, every botstats
name read through the botstats facade, RESULTS set through botdata.paths). Run:
    C:\\Python314\\python.exe research\\botdata\\tests\\test_report.py      (or all of them: research\\botstats.py --selftest)
"""
import calendar
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run                                            # noqa: E402

import botstats as bs                                               # noqa: E402
import pinledger                                                    # noqa: E402,F401
from botdata import paths as _paths                                 # noqa: E402,F401

NOW = float(calendar.timegm((2026, 9, 30, 16, 30, 0)))          # 12:30 PM ET, Wed Sep 30


def S(tk, st, res, yn=0.0, yc=0.0, nn=0.0, nc=0.0, fee=0.0, value=None):
    v = {"yes": 100, "no": 0}.get(res) if value is None else value
    return {"ticker": tk, "settled_time": st, "market_result": res, "value": v, "event_ticker": tk[:20],
            "yes_count_fp": "%.2f" % yn, "yes_total_cost_dollars": "%.6f" % yc,
            "no_count_fp": "%.2f" % nn, "no_total_cost_dollars": "%.6f" % nc, "fee_cost": "%.6f" % fee,
            "revenue": 0, "exchange_index": 2}


def T(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def J(path, recs):
    with open(path, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def P(w, pot, pp, kind="start"):
    return (w is not None and w["pot"] is not None and abs(w["pot"] - pot) < 0.006
            and w["pot_pct"] is not None and abs(w["pot_pct"] - pp) < 0.006 and w["pot_kind"] == kind)


def _deps():
    """The planted deposits (a fresh list: a test may change it)."""
    return [{"amount_cents": 100000, "fee_cents": 0, "status": "applied", "finalized_ts": T("2026-08-01T12:00:00Z")},
            {"amount_cents": 2550, "fee_cents": 50, "status": "applied",            # $25 after the fee, 9 AM ET
             "finalized_ts": T("2026-09-30T13:00:00Z")},                            # today, sitting in POOL 0
            {"amount_cents": 50000, "fee_cents": 0, "status": "pending",            # in flight: must NOT count
             "created_ts": T("2026-09-30T15:00:00Z")}]


def test_planted_world():
    """Sections 1-4 of the old self-test: the planted world read, its pots, the cache, a resumed walk, failures."""
    sub0 = [S("KXBTC15M-26SEP301145-45", "2026-09-30T15:45:05Z", "no", nn=50, nc=49.00, fee=0.10),        # +0.90
            S("KXETH15M-26SEP301100-00", "2026-09-30T15:00:05Z", "yes", yn=40, yc=38.80, nn=40, nc=12.00,
              fee=0.50),                                                                                 # -11.30 hedged
            S("KXCRYPTOLEAD15M-26SEP301030-XRP", "2026-09-30T14:31:10Z", "yes", yn=20, yc=19.60, fee=0.03),   # +0.37
            S("KXCRYPTOLEAD15M-26SEP301015-HYPE", "2026-09-30T14:16:00Z", "scalar", nn=10, nc=9.80, fee=0.01,
              value=50),                                                                                 # -4.81 tie
            S("KXXRP15M-26SEP300000-00", "2026-09-30T04:00:05Z", "yes", yn=10, yc=9.70, fee=0.02),            # +0.28 today
            S("KXSOL15M-26SEP292345-45", "2026-09-30T03:45:05Z", "yes", yn=30, yc=29.40, fee=0.06),           # +0.54 the 29th
            S("KXWTI15M-26SEP291400-00", "2026-09-29T18:00:05Z", "no", yn=5, yc=4.50, fee=0.01),             # -4.51 other
            S("KXBTCD-26SEP2911-T82899.99", "2026-09-29T15:00:05Z", "yes", yn=1, yc=0.98),                   # +0.02
            S("KXHYPE15M-26SEP241200-00", "2026-09-24T16:00:05Z", "yes", yn=10, yc=9.80, fee=0.02),           # +0.18
            S("KXDOGE15M-26SEP221200-00", "2026-09-22T16:00:05Z", "no", nn=20, nc=19.00, fee=0.04),           # +0.96
            S("KXBNB15M-26AUG311500-00", "2026-08-31T19:00:05Z", "no", yn=10, yc=9.50, fee=0.02)]             # -9.52
    sub1 = [S("KXNEAR15M-26SEP301130-30", "2026-09-30T15:30:05Z", "yes", yn=2, yc=1.958),                  # +0.042
            S("KXBNB15M-26SEP291745-45", "2026-09-29T21:45:06Z", "yes", yn=2, yc=1.96)]                     # +0.04
    sub2 = [S("KXETH15M-26SEP301200-00", "2026-09-30T16:00:06Z", "no", yn=5, yc=2.45, fee=0.0875),         # -2.5375
            S("KXNEAR15M-26SEP300030-30", "2026-09-30T04:30:06Z", "yes", yn=2, yc=1.93, fee=0.0048),          # +0.0652
            S("KXXRP15M-26SEP292300-00", "2026-09-30T03:00:06Z", "yes", yn=3, yc=2.42, fee=0.0328)]           # +0.5472
    world = {"0": sub0, "1": sub1, "2": sub2}
    poss = {"0": [{"ticker": "KXBTC15M-26SEP301245-45", "position_fp": "-30.00", "market_exposure_dollars": "29.10",
                   "fees_paid_dollars": "0.06"},
                  {"ticker": "KXCRYPTOLEAD15M-26SEP301230-SOL", "position_fp": "20.00",
                   "market_exposure_dollars": "19.60"}],
            "1": [{"ticker": "KXNEAR15M-26SEP301245-45", "position_fp": "1.00", "market_exposure_dollars": "0.98"}],
            "2": []}
    bals = {"0": "1000.0000", "1": "15.1000", "2": "24.0000"}

    def T(s):
        return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
    # the account's books (2026-10-02, the pot). Worked by hand below.
    xfers = [{"amount_cents": 1600, "created_ts": T("2026-09-28T15:54:07Z"), "from_subaccount": 0, "to_subaccount": 1,
              "exchange_index": 2, "transfer_id": "t1"},                                  # $16 main -> ladder
             {"amount_cents": 2000, "created_ts": T("2026-09-29T00:15:30Z"), "from_subaccount": 0, "to_subaccount": 2,
              "exchange_index": 2, "transfer_id": "t2"},       # $20 main -> forecaster, 8:15 PM ET Sep 28
             {"amount_cents": 200, "created_ts": T("2026-09-29T04:19:02Z"), "from_subaccount": 2, "to_subaccount": 0,
              "exchange_index": 2, "transfer_id": "t3"},       # $2 back, 12:19 AM ET Sep 29
             {"amount_cents": 500, "created_ts": T("2026-09-30T14:00:00Z"), "from_subaccount": 0, "to_subaccount": 2,
              "exchange_index": 2, "transfer_id": "t4"}]       # $5 main -> forecaster, 10 AM ET today
    deps = _deps()
    wdrs = [{"amount_cents": 4000, "fee_cents": 0, "status": "applied", "finalized_ts": T("2026-09-25T12:00:00Z")}]
    asked = []
    fail = {"page2": False, "all": False, "ledgers": False, "cents": False}

    def fake(path, q):
        asked.append((path, dict(q or {})))
        if fail["all"]:
            return 401, {"error": "nope"}
        if path in bs.LEDGER_PATHS:
            if fail["ledgers"]:
                return 500, "boom"
            if path.endswith("/transfers"):                  # two pages, to exercise the cursor
                return 200, ({"transfers": xfers[:2], "cursor": "x2"} if not q.get("cursor")
                             else {"transfers": xfers[2:], "cursor": ""})
            if path.endswith("/balances"):
                # as Kalshi lists it since 2026-10-04: subaccounts 1 and 2 also hold an (empty) pool-0 row,
                # and subaccount 3 -- the weather pot -- lives in pool 0 only (empty in this world)
                return 200, {"subaccount_balances": [
                    {"subaccount_number": 0, "exchange_index": 0, "balance": "25.0000"},
                    {"subaccount_number": 0, "exchange_index": 2, "balance": "100000" if fail["cents"] else "1000.0000"},
                    {"subaccount_number": 1, "exchange_index": 0, "balance": "0.0000"},
                    {"subaccount_number": 1, "exchange_index": 2, "balance": "15.1000"},
                    {"subaccount_number": 2, "exchange_index": 0, "balance": "0.0000"},
                    {"subaccount_number": 2, "exchange_index": 2, "balance": "24.0000"},
                    {"subaccount_number": 5, "exchange_index": 2, "balance": "0.0000"},     # the FX taker's pot, empty here
                    {"subaccount_number": 4, "exchange_index": 0, "balance": "0.0000"},     # its currency pot (pool 0), empty here
                    {"subaccount_number": 3, "exchange_index": 0, "balance": "0.0000"},
                    {"subaccount_number": 3, "exchange_index": 2, "balance": "0.0000"}]}   # the jump band's pool (10-30), empty here
            if path.endswith("/deposits"):
                return 200, {"deposits": deps, "cursor": ""}
            return 200, {"withdrawals": wdrs}
        sub = str((q or {}).get("subaccount"))
        if path == "/portfolio/settlements":
            rows = world.get(sub, [])
            if sub == "0":           # two pages, to exercise the cursor
                if not q.get("cursor"):
                    return 200, {"settlements": rows[:6], "cursor": "c-0-2"}
                if fail["page2"]:
                    return 500, "boom"
                return 200, {"settlements": rows[6:], "cursor": ""}
            return 200, {"settlements": rows, "cursor": ""}
        if path == "/portfolio/positions":
            return 200, {"market_positions": poss.get(sub, []), "event_positions": [], "cursor": ""}
        if path == "/portfolio/balance":
            # Kalshi answers for the NAMED pool only (read live 2026-10-04); pots 0-3 and 5 trade in pool 2 (pot 3 since
            # the jump band, 10-30; it was pool 0 for the weather dip-seller), pot 4 in pool 0
            if q.get("exchange_index") != {"4": 0}.get(sub, 2):
                return 200, {"balance": 0, "balance_dollars": "0.0000"}
            return 200, {"balance": 0, "balance_dollars": bals.get(sub, "0")}
        return 404, {}

    saved = (_paths.RESULTS, dict(bs._MEMO), dict(bs._BACK))
    td = tempfile.mkdtemp(prefix="botstats-")
    try:
        _paths.set_results(td)
        bs._MEMO.update(key=None, data=None)
        bs._BACK.clear()
        # planted logs
        J(os.path.join(td, "pinrun-live-20260928T143553Z.jsonl"), [
            {"kind": "start", "t": "2026-09-28T14:35:53Z", "size": 20.0, "price_ceiling": 0.98, "tau_max": 30,
             "early_tau_max": 45, "early_frac": 0.333, "early_min_price": 0.9, "early_max_price": 0.978,
             "hedge_belief": 0.4, "loss_cap": 200.0, "max_positions": 3, "ladder_series": ["KXBTCD"],
             "code_sha": "abc"},
            {"kind": "order", "t": "2026-09-30T03:00:00Z", "filled": 91.0},        # 11 PM ET on the 29th: not today
            {"kind": "refused", "t": "2026-09-30T13:00:00Z", "gate": "no_offer"},
            {"kind": "refused", "t": "2026-09-30T13:00:01Z", "gate": "no_offer"},
            {"kind": "refused", "t": "2026-09-30T13:00:02Z", "gate": "edge_floor"},
            {"kind": "hedge", "t": "2026-09-30T14:59:30Z", "live": True},
            {"kind": "order", "t": "2026-09-30T15:30:00Z", "filled": 0.0, "status": "canceled"},
            {"kind": "order", "t": "2026-09-30T15:44:40Z", "filled": 50.0}])
        os.utime(os.path.join(td, "pinrun-live-20260928T143553Z.jsonl"), (NOW, NOW))
        with open(os.path.join(td, "pinrun-live-size.json"), "w", encoding="utf-8") as fh:
            json.dump({"size": 92.0, "bank": 1088.7, "at": "2026-09-30T16:00:00Z", "epoch": NOW - 1800}, fh)
        J(os.path.join(td, "pinracepenny-live.jsonl"), [
            {"kind": "start", "t": "2026-09-27T06:01:49Z", "argv": ["--live", "--max-contracts", "10"]},
            {"kind": "live_halt", "t": "2026-09-27T09:00:00Z", "why": "an OLD halt, before the latest start"},
            {"kind": "start", "t": "2026-09-28T02:50:14Z", "version": "2026-09-24-tie1", "stop_on_loss": True,
             "argv": ["--live", "--max-contracts", "20", "--max-stake", "60", "--live-tau-max", "30",
                      "--live-min-price", "0.90", "--live-max-legs", "5"],
             "live_rails": {"stop_on_loss": True}},
            {"kind": "live_order", "t": "2026-09-30T14:30:40Z", "filled": 20.0},
            {"kind": "live_order", "t": "2026-09-30T14:15:40Z", "filled": 0.0, "status": "canceled"},
            {"kind": "live_refused", "t": "2026-09-30T14:15:41Z", "why": ["one position per race"]},
            {"kind": "live_refused", "t": "2026-09-30T14:15:42Z", "why": ["one position per race"]},
            {"kind": "live_refused", "t": "2026-09-30T14:29:01Z", "why": ["tau 54 is past the 30s bar"]},
            {"kind": "live_refused", "t": "2026-09-30T14:29:02Z", "why": ["tau 53 is past the 30s bar"]}])
        J(os.path.join(td, "forecaster-live-orders.jsonl"), [
            {"t": "2026-09-29T04:21:01.848Z", "ev": "start", "pid": 4036456, "live": True, "variant": "race05_98",
             "rails": {"scale": "0.05"}},
            {"t": "2026-09-29T15:35:02.502Z", "ev": "start", "pid": 4196192, "live": True, "variant": "race1_98",
             "variant_params": {"race_x": 1.0, "race_p": 0.98},
             "rails": {"scale": "0.05", "per_side": 5, "per_close": 20, "max_commit": 22.0, "px": [0.75, 0.985],
                       "day_stop": -12.0, "run_stop": -20.0}},
            {"t": "2026-09-30T15:59:30.000Z", "ev": "placed", "filled": 5.0},
            {"t": "2026-09-30T15:59:30.100Z", "ev": "live_fill", "n": 5},
            {"t": "2026-09-30T15:59:40.000Z", "ev": "placed", "filled": 0.0},
            {"t": "2026-09-30T15:59:41.000Z", "ev": "refused", "why": "in_flight"},
            {"t": "2026-09-30T15:59:59.600Z", "ev": "dropped", "why": "late"},
            {"t": "2026-09-30T16:10:00.000Z", "ev": "start", "pid": 999, "live": False, "variant": "dry-run"}])
        J(os.path.join(td, "ladder-live-orders.jsonl"), [
            {"t": "2026-09-29T17:16:12.117Z", "ev": "start", "pid": 4217364, "live": True,
             "rails": {"size": 1, "max_contracts": 10, "max_commit": 12.0, "day_stop": -6.0,
                       "max_live_per_close": 9, "live_levels": [0]}},
            {"t": "2026-09-30T15:29:30Z", "ev": "placed"}, {"t": "2026-09-30T15:29:31Z", "ev": "placed"},
            {"t": "2026-09-30T15:29:32Z", "ev": "placed"},
            {"t": "2026-09-30T15:29:40Z", "ev": "live_fill", "delta": 1},
            {"t": "2026-09-30T15:29:50Z", "ev": "rail_refused", "why": "max_contracts"},
            {"t": "2026-09-30T15:30:00Z", "ev": "cancelled"}, {"t": "2026-09-30T15:30:00Z", "ev": "cancelled"},
            {"t": "2026-09-30T15:40:00Z", "ev": "stop_file"}, {"t": "2026-09-30T15:40:00Z", "ev": "exit"}])
        with open(os.path.join(td, "ladder-live.stop"), "w", encoding="utf-8") as fh:
            fh.write("")
        with open(os.path.join(td, bs.VERSIONS_NAME), "w", encoding="utf-8") as fh:
            fh.write("# Versions\n\n"
                     "# v-ladder-settlefix -- LIVE 2026-09-29 17:16:12Z (pid 4217364; research/cleanroom/ladder_live.py): x\n"
                     "# v-keepalive-cleanroom -- 2026-09-29 15:37Z (boot_all): forecaster_live and ladder_live restart\n"
                     "# v-forecaster-race1 -- LIVE 2026-09-29 15:35:02Z (pid 4196192): race1_98\n"
                     "# v-reopen98 + v-floor90 -- 2026-09-28 14:36:17Z (pid 3882400; no code change) -- LIVE: 98c\n"
                     "# v-race20 -- 2026-09-28 02:50Z (pid 3739628; pinracearm.py) -- LIVE: coin race penny bot 20\n"
                     "# v-ladder7 -- 2026-09-25 03:2xZ -- CODE ON DISK: the ladder table knows seven hourly series\n")
        PROCS = [(3882400, "2026-09-28T14:35:48Z", "C:\\Python314\\python.exe -u C:\\kals-repo\\research\\pinrun.py "
                  "--live --size 20 --max-losses 2 --series KXBTCD --series-size 1 --one-full-bet --toxic-fresh"),
                 (2966252, "2026-09-25T12:25:44Z", "python -u C:\\kals-repo\\research\\pinrun.py --size 20 --arm-name arm-x"),
                 (1111, "", "python -u C:\\kals-repo\\research\\pinrun_afternoon.py --live"),
                 (3739628, "2026-09-28T02:50:10Z", "python -u research/pinracearm.py --live --max-contracts 20 "
                  "--max-stake 60 --live-tau-max 30 --live-min-price 0.90 --live-max-legs 5"),
                 (2574672, "2026-09-24T05:56:08Z", "python -u research/pinracearm.py --paper-live --live-tau-max 60"),
                 (4196192, "2026-09-29T15:34:56Z", "python -u research\\cleanroom\\forecaster_live.py --subaccount 2 "
                  "--live --variant race1_98 --minutes 10080"),
                 (3575912, "2026-09-27T13:47:08Z", "python research\\cleanroom\\locked_average_ladder_re_paper.py")]

        # 1. the planted world, first read: a full walk of every pot
        a = bs.all_bots(now=NOW, getter=fake, procs=PROCS)
        ck(asked and all(q.get("subaccount") in bs.SUBS for p, q in asked if p in bs.POT_PATHS),
           "EVERY per-pot Kalshi request names its subaccount -- with none, settlements mix every pot's rows")
        ck(set(p for p, _ in asked) == set(bs.PATHS),
           "and only the seven read paths are ever asked for: %s" % sorted(set(p for p, _ in asked)))
        ck(sum(1 for p, q in asked if p == "/portfolio/settlements" and q["subaccount"] == "0") == 2,
           "the first read walks the main account's two settlement pages to the end")
        pin, race, fc, lad, wxb = (a["bots"][b] for b in ("pin", "race", "forecaster", "ladder", "weather"))
        ck("fx" in a["bots"] and a["bots"]["fx"]["subaccount"] == 5 and a["bots"]["fx"]["label"] == "FX taker",
           "the FX taker (subaccount 5, 2026-10-25) is a bot of its own")
        ck(bs.bot_subs("fx") == ("5", "4") and a["bots"]["fx"]["subaccounts"] == [5, 4]
           and bs.owner("KXEURUSD15M-26OCT251930-30", "4") == "fx" and bs.owner("KXBTC15M-26OCT230815-15", "4") == "other"
           and bs.owner("KXGOLD15M-26OCT251945-45", "5") == "fx" and bs.SUB_POOL["4"] == 0,
           "the FX taker owns two pots: commodities in subaccount 5 (pool 2), the currency pairs in subaccount 4 (pool 0); "
           "the old coin-race reward rows that share the number 4 are not its")
        # POT_POOL_ONLY (2026-10-26): the live books' shape -- $55 in / $42.54 back / $45 in / $27.57 back on 4's pool-2
        # side (the old reward test), then $60 into 4's pool 0. The FX taker's pot 4 = pool 0 only: $60 put in, the
        # pool-0 cash, the FX pairs; flows for the main account still count both pools' transfers.
        _led4 = {"transfers": [{"amount_cents": 5500, "created_ts": 1, "from_subaccount": 0, "to_subaccount": 4, "exchange_index": 2},
                               {"amount_cents": 4254, "created_ts": 2, "from_subaccount": 4, "to_subaccount": 0, "exchange_index": 2},
                               {"amount_cents": 4500, "created_ts": 3, "from_subaccount": 0, "to_subaccount": 4, "exchange_index": 2},
                               {"amount_cents": 2757, "created_ts": 4, "from_subaccount": 4, "to_subaccount": 0, "exchange_index": 2},
                               {"amount_cents": 6000, "created_ts": 5, "from_subaccount": 0, "to_subaccount": 4, "exchange_index": 0},
                               {"amount_cents": 12000, "created_ts": 6, "from_subaccount": 0, "to_subaccount": 5, "exchange_index": 2}],
                 "subaccount_balances": [{"subaccount_number": 4, "exchange_index": 0, "balance": "60.9681"},
                                         {"subaccount_number": 4, "exchange_index": 2, "balance": "0.0068"}]}
        _x4 = {"rows": {"a": {"ticker": "KXUSDJPY15M-26OCT252145-30"}, "b": {"ticker": "KXBTC15M-26OCT230815-15"}}}
        ck(abs(bs.flows(_led4, "4") - 60.0) < 1e-9 and abs(bs.flows(_led4, ("5", "4")) - 180.0) < 1e-9
           and abs(bs.flows(_led4, "0") - (-55.0 + 42.54 - 45.0 + 27.57 - 60.0 - 120.0)) < 1e-9
           and abs(bs._cash_all_pools(_led4, "4", 60.9681, own=True)[0] - 60.9681) < 1e-9
           and abs(bs._cash_all_pools(_led4, "4", 60.9681)[0] - 60.9749) < 1e-9
           and [r["ticker"] for r in bs.pot_rows(_x4, "4")] == ["KXUSDJPY15M-26OCT252145-30"] and len(bs.pot_rows(_x4, "4", own=False)) == 2
           and len(bs.pot_rows(_x4, "5")) == 2,
           "POT_POOL_ONLY: the FX taker's pot 4 is its pool 0 -- $60 put in (not $89.89 with the old reward test's pool-2 "
           "transfers), its pool-0 cash, its FX pairs; the whole subaccount and the main account keep both pools")
        pm = pin["money"]
        ck(pm["today"]["markets"] == 3 and abs(pm["today"]["money"] - (-10.12)) < 1e-6
           and pm["today"]["won"] == 2 and pm["today"]["lost"] == 1 and pm["today"]["hedged"] == 1,
           "pin TODAY: 3 markets, 2 won 1 lost, -$10.12 (the hedged ETH market pays its winning YES side: "
           "$40 - $50.80 - $0.50 = -$11.30, not the -$51.30 that `revenue: 0` would say)")
        ck(abs(pm["today"]["put_in"] - 109.50) < 1e-6 and abs(pm["today"]["return_pct"] - (-9.24)) < 0.01,
           "put in is both sides' cost ($109.50); return -9.24%")
        ck(pm["yesterday"]["markets"] == 2 and abs(pm["yesterday"]["money"] - 0.56) < 1e-6,
           "yesterday is +$0.56: the SOL market closing 11:45 PM ET on the 29th belongs to the 29th although "
           "Kalshi settled it at 03:45 UTC on the 30th; the XRP one closing at midnight belongs to the 30th")
        ck(pm["last_7_days"]["markets"] == 6 and abs(pm["last_7_days"]["money"] - (-9.38)) < 1e-6,
           "last 7 days (Sep 24-30) -$9.38; the Sep 22 market is outside it")
        ck(pm["this_month"]["markets"] == 7 and abs(pm["this_month"]["money"] - (-8.42)) < 1e-6
           and pm["all_time"]["markets"] == 8 and abs(pm["all_time"]["money"] - (-17.94)) < 1e-6,
           "September -$8.42; all time -$17.94 (the Aug 31 market counts only all-time)")
        ck(pm["all_time"]["worst"]["ticker"] == "KXETH15M-26SEP301100-00"
           and pm["all_time"]["best"]["ticker"] == "KXDOGE15M-26SEP221200-00",
           "worst and best are single markets (-$11.30 ETH, +$0.96 DOGE)")
        ck(len(pm["days_7"]) == 7 and pm["days_7"][0]["day"] == "2026-09-30" and pm["days_7"][6]["day"] == "2026-09-24"
           and abs(pm["days_7"][6]["money"] - 0.18) < 1e-6 and pm["days_7"][3]["markets"] == 0,
           "the per-day list is 7 ET days newest first, empty days kept as empty (not dropped)")
        _a30 = bs.avg_day(pm["days_30"])
        ck(len(pm["days_30"]) == bs.LONG_DAYS and pm["days_30"][0]["day"] == "2026-09-29"
           and pm["days_30"][-1]["day"] == "2026-08-31" and not any(d["before_first"] for d in pm["days_30"])
           and abs(sum(d["money"] for d in pm["days_30"]) - (pm["all_time"]["money"] - pm["today"]["money"])) < 1e-6
           and _a30["days"] == 30 and not _a30["young"] and abs(_a30["money"] - (-7.82 / 30)) < 1e-4
           and bs.avg_words(_a30) == "last 30 full days" and len(a["total_days_30"]) == bs.LONG_DAYS
           and abs(sum(d["money"] for d in a["total_days_30"]) - sum(d["money"] for b_ in bs.BOTS
                                                                    for d in a["bots"][b_]["money"]["days_30"])
                   - sum(d["money"] for d in a["other"]["days_30"])) < 1e-6,
           "2026-10-29, the 30-day average day: days_30 = the 30 FULL ET days before today (Sep 29 back to Aug 31, today "
           "left out), together every market but today's (-$7.82, so %s a day); all_bots' total_days_30 adds every "
           "bot and other day by day" % bs.usd(_a30["money"]))
        _ym = [{"ticker": "KXGOLD15M-X-%d" % k, "what": "x", "day": d_, "t": 0, "side": "yes", "contracts": 1.0,
                "money": v_, "put_in": 1.0, "fees": 0.0} for k, (d_, v_) in enumerate(
                    (("2026-09-26", 0.5), ("2026-09-28", 0.25), ("2026-09-30", 9.0)))]
        _yw = bs.windows(_ym, "2026-09-30")
        _y30 = bs.avg_day(_yw["days_30"])
        ck(_y30 == {"days": 4, "money": 0.1875, "pot_pct": None, "pct_days": 0, "first": "2026-09-26", "young": True}
           and bs.avg_words(_y30) == "since Sep 26, 4 days" and _yw["days_30"][0]["day"] == "2026-09-29"
           and _yw["days_30"][0]["markets"] == 0 and _yw["days_30"][3]["money"] == 0.5,
           "a bot younger than 30 days (first market Sep 26) averages its 4 full days, the quiet Sep 27 and 29 at $0 "
           "and today's $9 left out, and says so: '%s' (%s a day)" % (bs.avg_words(_y30), bs.usd(_y30["money"])))
        ck(race["money"]["today"]["markets"] == 2 and abs(race["money"]["today"]["money"] - (-4.44)) < 1e-6
           and race["money"]["today"]["lost"] == 1,
           "race today -$4.44: the tie pays 50c a contract ($5 on 10 NO), a -$4.81 loss, not -$9.81")
        ck(not any(m["ticker"].startswith("KXCRYPTOLEAD") for m in [pm["all_time"]["worst"], pm["all_time"]["best"]])
           and pm["all_time"]["markets"] == 8 and race["money"]["all_time"]["markets"] == 2,
           "race markets are never pin's and pin's never the race's, though they share a pot")
        ck(abs(a["other"]["all_time"]["money"] - (-4.51)) < 1e-6 and a["other"]["all_time"]["markets"] == 1,
           "the old oil bot's WTI market is `other`, shown -- not folded into pin")
        ck(abs(fc["money"]["today"]["money"] - (-2.4723)) < 1e-6 and fc["money"]["today"]["markets"] == 2
           and abs(fc["money"]["yesterday"]["money"] - 0.5472) < 1e-6,
           "forecaster (subaccount 2) today -$2.47 on 2 markets, yesterday +$0.55")
        ck(abs(lad["money"]["today"]["money"] - 0.042) < 1e-6 and abs(lad["money"]["all_time"]["money"] - 0.082) < 1e-6,
           "ladder (subaccount 1) today +$0.04, all time +$0.08")
        t = a["total"]
        ck(abs(t["today"]["money"] - (-10.12 - 4.44 - 2.4723 + 0.042)) < 1e-6
           and abs(t["yesterday"]["money"] - (0.56 + 0.5472 + 0.04 - 4.51)) < 1e-6
           and t["today"]["by_bot"]["forecaster"] == round(-2.4723, 4) and not t["today"]["partial"],
           "the ALL-BOTS total is the four bots plus `other`, each bot's share listed")
        ck(abs(t["all_time"]["money"] - sum(pinledger.pnl(s) for v in world.values() for s in v)) < 1e-6,
           "and all time equals every settlement in every pot, each counted once")
        ck(pin["balance"]["dollars"] == 1000.0 and pin["balance"]["shared_with"] == ["race"]
           and race["balance"]["shared_with"] == ["pin"] and "shared" in pin["balance"]["note"]
           and a["balances"]["all"] == 1039.1 and "NOT in the main" in a["note"],
           "cash: pin and race SHARE the main pot ($1,000) and say so; all pots $1,039.10")
        ck(pin["open"]["count"] == 1 and pin["open"]["positions"][0]["side"] == "no"
           and pin["open"]["positions"][0]["contracts"] == 30 and race["open"]["count"] == 1
           and lad["open"]["count"] == 1 and fc["open"]["count"] == 0,
           "open positions are split by ticker inside the shared pot (pin NO x30, race SOL)")
        ck([x["ticker"] for x in pin["last_settled"]][:2] == ["KXBTC15M-26SEP301145-45", "KXETH15M-26SEP301100-00"]
           and pin["last_settled"][1]["side"] == "both" and len(pin["last_settled"]) == 5,
           "last settled: newest first, five of them, the hedged one marked both sides")
        ck(pin["last_settled"][0]["time_et"] == "Sep 30 11:45 AM ET",
           "times are ET (15:45 UTC shows as 11:45 AM ET)")
        # running
        pr = pin["running"]
        ck(pr["alive"] is True and pr["pids"] == [3882400] and race["running"]["pids"] == [3739628]
           and pr["started_et"] == "Sep 28 10:35 AM ET",
           "pin: the --live pinrun is the bot (the paper arm and pinrun_afternoon are not); started in ET")
        ck(pr["version"] == "v-reopen98 + v-floor90" and race["running"]["version"] == "v-race20"
           and fc["running"]["version"] == "v-forecaster-race1" and lad["running"]["version"] == "v-ladder-settlefix",
           "each bot's newest VERSIONS.md entry (the clean-room keep-alive and v-ladder7 are not the ladder's)")
        ck(pr["settings"]["bet_now"] == 92.0 and "bet 92 contracts" in pr["settings_text"]
           and "97.8c" in pr["settings_text"] and "40%" in pr["settings_text"]
           and pr["settings"].get("max_losses") == 2.0,
           "pin settings: bet size from pinrun-live-size.json, the rest from its start record + command line")
        rr = race["running"]
        ck(rr["alive"] is True and rr["pid"] == 3739628 and rr["settings"]["contracts_per_bet"] == 20
           and rr["halted"] is None and "boot_all.ps1" in (rr["keepalive"] or "") and "nothing restarts" not in
           bs.text_summary("race", now=NOW + 1, getter=fake, procs=PROCS),
           "race: the --live copy (not --paper-live), 20 a bet; an OLD halt before its start is not a halt; "
           "boot_all.ps1 keeps it alive (in its keep-alive list since 09-30), so 'nothing restarts it' is not said")
        fr = fc["running"]
        ck(fr["alive"] is True and fr["settings"]["variant"] == "race1_98" and "variant_mismatch" not in fr["settings"],
           "forecaster: variant from the start record whose pid is the running process (not the later dry run)")
        lr = lad["running"]
        ck(lr["alive"] is False and lr["stop_flag"] is True and "top rung" in lr["settings_text"],
           "ladder: the ladder PAPER bot is not the live ladder; not running, stopped by its stop file")
        # activity from the logs
        ap_, ar, af, al, _aw = (a["bots"][b]["activity_today"] for b in ("pin", "race", "forecaster", "ladder", "weather"))
        ck(ap_["sent"] == 2 and ap_["filled"] == 1 and ap_["contracts_filled"] == 50 and ap_["hedges"] == 1
           and ap_["refused"] == 3 and ap_["refused_why"] == {"no_offer": 2, "edge_floor": 1},
           "pin today: 2 orders, 1 filled (50), 1 hedge, 3 passes by gate -- the 11 PM ET order is yesterday's")
        ck(ar["sent"] == 2 and ar["filled"] == 1 and ar["refused"] == 4
           and ar["refused_why"].get("tau N is past the Ns bar") == 2
           and "too early 2" in bs._bot_text(race),
           "race today: 2 sent, 1 filled, 4 refused -- reasons that differ only in their numbers group as one "
           "('too early 2'), not one line per second")
        ck(af["sent"] == 2 and af["filled"] == 1 and af["contracts_filled"] == 5 and af["refused"] == 2,
           "forecaster today: 2 sent, 1 filled (5 contracts), refused + dropped 2")
        ck(al["sent"] == 3 and al["filled"] == 1 and al["cancelled"] == 2 and al["refused"] == 1
           and any(h["what"] == "stop_file" for h in al["halts"]),
           "ladder today: 3 bids placed, 1 filled, 2 cancelled, 1 refused, and the stop file seen")
        # every bot's FILLS from its own log, each named by its bot (2026-10-26, /market and /fills)
        fl_, un_ = bs.fills_since(bs.day_start("2026-09-30"))
        ck([(f["bot"], f["contracts"]) for f in fl_] == [("race", 20.0), ("ladder", 1.0), ("pin", 50.0),
                                                           ("forecaster", 5.0)]
           and all(f["sub"] == bs.SPEC[f["bot"]]["sub"] for f in fl_) and set(un_) == {"weather", "fx", "jumpband"},
           "fills_since: today's fills from every bot's own log, oldest first, each with its bot and pot -- the 11 PM "
           "order is yesterday's, an order that got nothing and a hedge not executed are not fills; a bot with no "
           "log is named, never a zero: %r %r" % ([(f["bot"], f["contracts"]) for f in fl_], un_))
        fx4 = bs.fill_of("fx", {"kind": "fill", "t": "2026-09-30T15:44:31Z", "ticker": "KXEURUSD15M-26SEP301145-45",
                             "side": "no", "n": 10.0, "px": 0.99})
        fx5 = bs.fill_of("fx", {"kind": "fill", "t": "2026-09-30T15:44:32Z", "ticker": "KXGOLD15M-26SEP301145-45",
                             "side": "yes", "n": 10.0, "px": 0.985})
        pn = bs.fill_of("pin", {"kind": "order", "t": "2026-09-30T15:44:40Z", "ticker": "KXBTC15M-26SEP301145-45",
                             "want": "no", "filled": 38.3, "exec_price": 0.9746})
        ph_ = bs.fill_of("pin", {"kind": "hedge", "t": "2026-09-30T15:44:50Z", "ticker": "KXBTC15M-26SEP301145-45",
                              "side": "yes", "n": 4.0, "price": 0.12, "status": "executed"})
        ck(fx4["sub"] == "4" and fx5["sub"] == "5" and fx4["side"] == "no" and fx5["price"] == 0.985
           and fx4["close"] == T("2026-09-30T15:45:00Z") and fx4["what"] == "EURUSD 11:45 AM"
           and pn["side"] == "no" and pn["contracts"] == 38.3 and pn["price"] == 0.9746 and not pn["hedge"]
           and ph_["hedge"] and ph_["side"] == "yes" and ph_["contracts"] == 4.0
           and bs.fill_of("pin", {"kind": "hedge", "ticker": "X", "n": 4, "status": "canceled"}) is None
           and bs.fill_of("weather", {"ev": "fill", "ticker": "KXHIGHNY-26SEP30-B72.5", "delta": 2, "px": 0.38})["act"]
           == "sold",
           "fill_of: the FX taker's currency pairs are subaccount 4 and its commodities 5; the pin bot's side is the "
           "side it WANTED, a hedge is its own fill; the weather dip-seller sells")

        # 1b. THE POT (2026-10-02): every window as a % of what its pot held when the window began, and
        # all time as a % of the money put in. Worked by hand from the planted books:
        #   now: main $1,000 crypto pool + $25 in pool 0 (today's deposit) + open bets 29.10 + 0.06 fee
        #        + 19.60 = $1,073.76; ladder 15.10 + 0.98 = $16.08; forecaster $24.00; all $1,113.84
        #   v-tg-twr (2026-10-31): a move counts in a window's base for the share of the window after it landed
        #   (the window so far ends at the read, 12:30 PM ET = 16:30Z; today began 04:00Z, 12.5 h before), and a
        #   window of several days chains its days (each day's % of what its pot held that day).
        #   main TODAY: settled today -14.56 (pin -10.12, race -4.44); moved in since midnight ET +25.00
        #     deposit (13:00Z: 3.5 of 12.5 h left = 0.28) - 5.00 to the forecaster (14:00Z: 0.20) -> start 1073.76
        #     + 14.56 - 20 = 1068.32, + 25 x 0.28 - 5 x 0.20 = +6.00 -> 1074.32. pin -10.12 / 1074.32 = -0.94%;
        #     race -4.44 / 1074.32 = -0.41%
        #   forecaster TODAY: 24 + 2.4723 - 5 = 21.4723 at the start, + 5 x 0.20 = 22.4723 -> -11.00%
        #   ladder TODAY: 16.08 - 0.042 = 16.038 -> +0.26%
        #   all pots TODAY: 1113.84 + 16.9903 - 25 = 1105.8303, + 25 x 0.28 = 1112.8303 -> -16.9903 = -1.53%
        #   main YESTERDAY (Sep 29): settled since -18.51; moved in since +22 (t3 +2 at 12:19 AM ET, +25,
        #     -5) -> start 1070.27, + t3's 2 x (24 h - 19 min 2 s) / 24 h = 1.9736 -> 1072.24; pin +0.56 -> +0.05%,
        #     other -0.42%
        #   forecaster YESTERDAY: 24 + 1.9251 - 3 = 22.9251, - the 2 it sent back at 12:19 AM x 0.98678 = 20.9515
        #     -> +0.5472 = +2.61%
        #   main 7 DAYS, days chained: -0.87% (an implied base of $1,072.38); MONTH -0.79% ($1,063.68). ladder
        #     7 DAYS: 0 at the start (it did not exist), the $16 moved in on its first day -> +0.51%. forecaster
        #     7 DAYS: -8.68% chained ($22.19), not -1.93 / 25.93 (its $20 counted as if there all week). All pots
        #     have no day list here: span_base's weighted rule, -1.80% of $1,117.75
        #   ALL TIME, money put in: all 1000 + 25 - 40 = 985 (the PENDING $500 is not in); main 985 - 16
        #     - 20 + 2 - 5 = 946; ladder 16; forecaster 23. pin -17.94/946 = -1.90%, forecaster -8.37%,
        #     all -28.7331/985 = -2.92%
        rm, fm, lm, tt = race["money"], fc["money"], lad["money"], a["total"]
        ck(P(pm["today"], 1074.32, -0.94) and P(rm["today"], 1074.32, -0.41),
           "TODAY pin -0.94%% and race -0.41%% of the SAME main pot ($1,074.32 = cash in BOTH pools + open "
           "bets at cost - today's settled + today's deposit and the $5 moved out, each for its share of the day): "
           "%s / %s"
           % ((pm["today"]["pot"], pm["today"]["pot_pct"]), (rm["today"]["pot"], rm["today"]["pot_pct"])))
        ck(P(fm["today"], 22.4723, -11.0) and P(lm["today"], 16.038, 0.26),
           "TODAY forecaster -11.0%% of $22.47 (the $5 moved in at 10 AM for the 20%% of the day after it); ladder "
           "+0.26%% of $16.04: %s / %s"
           % ((fm["today"]["pot"], fm["today"]["pot_pct"]), (lm["today"]["pot"], lm["today"]["pot_pct"])))
        ck(P(tt["today"], 1112.83, -1.53) and tt["today"]["pot_of"] == "all pots",
           "TODAY all pots -1.53%% of $1,112.83 -- subaccount transfers cancel, the deposit does not: %s"
           % ((tt["today"]["pot"], tt["today"]["pot_pct"]),))
        ck(P(pm["yesterday"], 1072.24, 0.05) and P(a["other"]["yesterday"], 1072.24, -0.42)
           and P(fm["yesterday"], 20.95, 2.61) and P(lm["yesterday"], 15.998, 0.25)
           and P(tt["yesterday"], 1109.1931, -0.30),
           "YESTERDAY: a past window is worked back from now through today's markets and moves too; a move inside "
           "that day counts for its share of it (main +$2 back from the forecaster, the forecaster -$2)")
        ck(P(pm["last_7_days"], 1072.38, -0.87) and P(lm["last_7_days"], 16.00, 0.51)
           and P(fm["last_7_days"], 22.19, -8.68) and P(tt["last_7_days"], 1117.75, -1.80)
           and P(pm["this_month"], 1063.68, -0.79),
           "7 DAYS and MONTH: days chained, each day's % of what its pot held that day, so a deposit or a withdrawal "
           "counts only from when it landed; a pot that did not exist at the start (ladder, $0) is a % of the money "
           "moved into it, never of $0")
        ck(P(pm["all_time"], 946.0, -1.90, "money_in") and P(rm["all_time"], 946.0, 100 * -4.44 / 946, "money_in")
           and P(fm["all_time"], 23.0, -8.37, "money_in") and P(lm["all_time"], 16.0, 0.5125, "money_in")
           and P(tt["all_time"], 985.0, -2.92, "money_in"),
           "ALL TIME is of the money put in: deposits after fees - withdrawals ($985, the pending $500 left out); "
           "main = that - what moved to the bot pots ($946); a subaccount = what moved into it, net ($16, $23)")
        ck(tt["today"]["by_bot_pot_pct"] == {"pin": -0.94, "race": -0.41, "forecaster": -11.0, "ladder": 0.26,
                                            "weather": None, "fx": None, "jumpband": None, "other": None},
           "the /bots breakdown carries each bot's own %% of its own pot: %s" % tt["today"]["by_bot_pot_pct"])
        _pt = bs._bot_text(pin)
        ck("Today: -$10.12 on $109.50 in (-9.2%) = -0.94% of its bank ($1,074.32), 2 won, 1 lost" in _pt
           and "All time: -$17.94 on $" in _pt and "= -1.9% on money put in ($946.00)" in _pt
           and "the pot is the whole main account, shared with the coin race" in _pt,
           "the phone text: '= X% of its bank ($)' on every window, all time 'on money put in', and pin "
           "says the main pot is shared")
        _st = bs.text_summary("all", now=NOW + 1, getter=fake, procs=PROCS)
        ck("Today: -$16.99 on $" in _st and "= -1.5% of all pots ($1,112.83)" in _st
           and "pin -$10.12 (-0.94%) | race -$4.44 (-0.41%) | forecaster -$2.47 (-11.0%) | earlier +$0.04"
           in _st and "ladder" not in _st.split("Running:")[1],
           "/bots-style text: the all-pots % and each bot's own % in the breakdown; the ladder (stopped by its stop file in "
           "this world) is not listed, its money is on the one 'earlier' line (v-tg-active)")
        pc = a["pot_check"]
        ck(pc["1"]["off"] is False and abs(pc["1"]["unexplained"]) < 0.01
           and pc["0"]["off"] is True and abs(pc["0"]["unexplained"] - 154.65) < 0.006 and pc["2"]["off"] is True
           and "! The main account holds $154.65 more than Kalshi's books explain" in _st
           and "subaccount 1 holds" not in _st,
           "POT CHECK: the ladder's pot is explained to the cent by money in + settled (no warning); this planted "
           "main account is not ($1,073.76 now vs $946 in - $26.89 settled = $154.65 unexplained) and is said")

        # 2. the cache: a read within 60 s asks Kalshi nothing; after 60 s one page a pot, no double count
        n0 = len(asked)
        a2 = bs.all_bots(now=NOW + 30, getter=fake, procs=PROCS)
        ck(len(asked) == n0 and a2["total"]["all_time"]["money"] == t["all_time"]["money"],
           "a second read within 60 s makes NO request and gives the same totals")
        a3 = bs.all_bots(now=NOW + 90, getter=fake, procs=PROCS)
        st3 = [q for p, q in asked[n0:] if p == "/portfolio/settlements"]
        ck(len(st3) == len(bs.SUBS) and a3["total"]["all_time"]["money"] == t["all_time"]["money"],
           "after 60 s: ONE settlements page a pot (it stops at a page it holds) and nothing counted twice")
        sub2.insert(0, S("KXSOL15M-26SEP301215-15", "2026-09-30T16:15:06Z", "yes", yn=4, yc=3.80, fee=0.01))
        a4 = bs.all_bots(now=NOW + 200, getter=fake, procs=PROCS)
        ck(abs(a4["bots"]["forecaster"]["money"]["today"]["money"] - (-2.4723 + 0.19)) < 1e-6,
           "a new settlement is picked up exactly once (+$0.19)")
        with open(bs.cache_path(), encoding="utf-8") as fh:
            cj = json.load(fh)
        ck(set(cj["subs"]) == set(bs.SUBS) and all(set(r) <= set(bs.KEEP) for r in cj["subs"]["0"]["rows"].values()),
           "the cache holds the three pots, each row trimmed to the fields the money needs")
        # 2026-10-26: /funds' past days read the same rows (pot_settlements), never a second pull of their own
        n0 = len(asked)
        ps_, pw_ = bs.pot_settlements(now=NOW + 230, getter=fake)
        ck(len(asked) == n0 and pw_ == {} and sorted(ps_) == sorted(bs.SUBS)
           and all(sorted(map(pinledger.key_of, ps_[s])) == sorted(cj["subs"][s]["rows"]) for s in bs.SUBS)
           and len(ps_["2"]) == 4,
           "pot_settlements: every pot's rows as the cache holds them (the forecaster's new one included), and inside "
           "60 s of the last read it asks Kalshi nothing")
        ck(len(cj["ledgers"]["transfers"]) == 4 and len(cj["ledgers"]["deposits"]) == 3,
           "and the account's books, the transfer history walked across both its pages")
        # 2026-10-27: the phone's /server shows every pot from this cache alone (cached_pots): no request of its own
        n0 = len(asked)
        cp_ = bs.cached_pots()
        c_ = bs.load_cache()
        nows_ = {s: bs._pot_now(c_, s)[0] for s in bs.SUBS}
        ck(len(asked) == n0 and sorted(cp_["pots"]) == sorted(bs.SUBS)
           and all(cp_["pots"][s]["cash"] == cj["subs"][s].get("balance") for s in bs.SUBS)
           and all(cp_["pots"][s]["value"] == (None if nows_[s] is None else round(nows_[s], 4)) for s in bs.SUBS)
           and cp_["pots"]["0"]["cash"] == a4["bots"]["pin"]["balance"]["dollars"]
           and cp_["t"] == max(float(cj["subs"][s]["tried"]) for s in bs.SUBS)
           and ((cp_["total"] is None) if any(v is None for v in nows_.values())
                else abs(cp_["total"] - sum(nows_.values())) < 1e-3),
           "cached_pots: every pot's cash and value as /bots last read them, a total only when every pot has one, and "
           "no Kalshi request")

        # 2b. FALLBACK (2026-10-23) -- a failed read uses the pots of the last pass where every pot read, and says so
        fail["ledgers"] = True
        f1 = bs.all_bots(now=NOW + 300, getter=fake, procs=PROCS)
        g1 = bs.load_cache().get("good") or {}
        fw = [f1["bots"][b]["money"][k] for b in ("pin", "forecaster", "ladder") for k in ("today", "yesterday", "last_7_days")] \
            + [f1["total"][k] for k in ("today", "yesterday", "last_7_days")]
        aw = [a4["bots"][b]["money"][k] for b in ("pin", "forecaster", "ladder") for k in ("today", "yesterday", "last_7_days")] \
            + [a4["total"][k] for k in ("today", "yesterday", "last_7_days")]
        ck(g1.get("t") == NOW + 200 and f1["pots_as_of"] == NOW + 200
           and all(w["pot_pct"] is not None and w["pot_as_of"] == NOW + 200 for w in fw)
           and [w["pot"] for w in fw] == [w["pot"] for w in aw] and [w["pot_pct"] for w in fw] == [w["pot_pct"] for w in aw]
           and all(v is None for v in f1["pot_check"].values())
           and "latest read failed" in (bs.pot_as_of_note(fw) or ""),
           "FALLBACK: the books unreadable -> every %% from the last pass where every pot read (the same bases as "
           "that pass, to the cent), the page says from when, and no pot check is made on an older moment")
        # 2c. NULL -- no good pass to fall back on: the pot unknown means NO percentage, never a guess
        cg = bs.load_cache()
        cg.pop("good", None)
        bs.save_cache(cg)
        n1 = bs.all_bots(now=NOW + 301, getter=fake, procs=PROCS)
        ws = [n1["bots"][b]["money"][k] for b in bs.BOTS for k in bs.WINDOW_KEYS] + [n1["total"][k] for k in bs.WINDOW_KEYS]
        _nt = bs._bot_text(n1["bots"]["pin"])
        ck(all(w["pot_pct"] is None and w["pot"] is None for w in ws)
           and abs(n1["bots"]["pin"]["money"]["today"]["money"] - (-10.12)) < 1e-6
           and "of its bank (" not in _nt and "on money put in" not in _nt
           and "% of its bank: not shown -- transfers read failed (HTTP 500)" in _nt
           and all(v is None for v in n1["pot_check"].values()),
           "NULL: the books unreadable (the deposit/transfer listings fail) -> the money is still shown, NO "
           "percentage anywhere, and the page says why")
        fail["ledgers"], fail["cents"] = False, True
        n2 = bs.all_bots(now=NOW + 400, getter=fake, procs=PROCS)
        ck(n2["bots"]["pin"]["money"]["today"]["pot_pct"] is None
           and "disagree" in n2["bots"]["pin"]["money"]["today"]["pot_why"]
           and n2["total"]["today"]["pot_pct"] is None and "main account" in n2["total"]["today"]["pot_why"]
           and n2["bots"]["ladder"]["money"]["today"]["pot_pct"] is not None
           and n2["bots"]["pin"]["money"]["all_time"]["pot_pct"] is not None,
           "NULL: a cash listing whose crypto-pool figure is not /portfolio/balance's dollars (100000 vs 1000) is "
           "an unknown UNIT -- no window % for the main pot or the total (hard rule 5); the ladder's pot and the "
           "money-put-in base (which needs no cash) stand")
        fail["cents"] = False
        cj2 = bs.load_cache()
        cj2["subs"]["0"]["pos_t"] = cj2["subs"]["0"]["tried"] - 60            # an open-bets read from an older pass
        ctx2 = bs.pot_context(cj2, bs.et_day(NOW + 400))
        ck(ctx2["subs"]["0"]["now"] is None and "open-bets" in ctx2["subs"]["0"]["why"]
           and ctx2["subs"]["1"]["now"] is not None,
           "NULL: figures from two different reads are never mixed -- a stale open-bets read voids that pot")
        _tr = float(cj2["subs"]["0"]["tried"])
        cj2["good"] = {"t": _tr - 30, "pots": {"0": 1000.0, "1": 16.0, "2": 20.0, "3": 0.0, "4": 0.0, "5": 0.0}}
        ctx3 = bs.pot_context(cj2, bs.et_day(NOW + 400))
        cj2["good"]["t"] = _tr - bs.GOOD_MAX_S - 1
        ctx4 = bs.pot_context(cj2, bs.et_day(NOW + 400))
        ck(ctx3["as_of"] == _tr - 30 and [ctx3["subs"][s]["now"] for s in bs.SUBS] == [1000.0, 16.0, 20.0, 0.0, 0.0, 0.0]
           and "open-bets" in ctx3["stale_why"] and ctx4["as_of"] is None and ctx4["subs"]["0"]["now"] is None,
           "FALLBACK: one pot unreadable -> EVERY pot from the last good pass (one moment, so they add up); a good "
           "pass older than %d h is not used" % (bs.GOOD_MAX_S // 3600))

        # 3. a first walk cut short is RESUMED, and flagged partial until it is
        os.remove(bs.cache_path())
        bs._MEMO.update(key=None, data=None)
        fail["page2"] = True
        b1 = bs.bot("pin", now=NOW, getter=fake, procs=PROCS)
        ck(b1["money"]["complete"] is False and b1["money"]["all_time"]["markets"] < 8
           and "HISTORY STILL LOADING" in bs._bot_text(b1),
           "a first walk that fails on page 2 is flagged partial, never shown as the whole history")
        ps_, pw_ = bs.pot_settlements(now=NOW + 1, getter=fake)
        ck("0" not in ps_ and pw_.get("0") == "settlements read failed (HTTP 500)" and len(ps_.get("1") or []) == 2,
           "pot_settlements: a pot whose last read failed is NOT given (the caller reads it some other way); the "
           "pots that read whole are")
        fail["page2"] = False
        b2 = bs.bot("pin", now=NOW + 61, getter=fake, procs=PROCS)
        ck(b2["money"]["complete"] is True and b2["money"]["all_time"]["markets"] == 8
           and abs(b2["money"]["all_time"]["money"] - (-17.94)) < 1e-6,
           "and the next read resumes the walk to the end: all 8 pin markets, -$17.94")

        # 4. failures are failures, never $0 or 'not running'
        os.remove(bs.cache_path())
        bs._MEMO.update(key=None, data=None)
        fail["all"] = True
        f = bs.all_bots(now=NOW, getter=fake, procs=lambda: None)
        fp = f["bots"]["pin"]
        ck(fp["money"]["ok"] is False and fp["money"]["today"] is None and fp["balance"]["dollars"] is None
           and fp["open"]["ok"] is False and f["total"]["today"]["partial"] and f["balances"]["all"] is None,
           "NULL: Kalshi refusing (401) gives money None and a PARTIAL total -- never $0")
        ck(fp["running"]["alive"] is None and "COULD NOT TELL" in bs._bot_text(fp) and "COULD NOT READ KALSHI" in bs._bot_text(fp),
           "NULL: an unreadable process list is 'could not tell', never 'not running'")
        ps_, pw_ = bs.pot_settlements(now=NOW + 1, getter=fake)
        ck(ps_ == {} and sorted(pw_) == sorted(bs.SUBS) and set(pw_.values()) == {"settlements read failed (HTTP 401)"},
           "NULL: pot_settlements with Kalshi refusing gives no pot's rows -- never an empty list read as 'nothing settled'")
        fail["all"] = False
    finally:
        _paths.set_results(saved[0])
        bs._MEMO.clear()
        bs._MEMO.update(saved[1])
        bs._BACK.clear()
        bs._BACK.update(saved[2])
        shutil.rmtree(td, ignore_errors=True)


def test_empty_world():
    saved = (_paths.RESULTS, dict(bs._MEMO), dict(bs._BACK))
    # 5. the EMPTY world: no settlements, no positions, no logs, nothing running
    td = tempfile.mkdtemp(prefix="botstats-empty-")
    try:
        _paths.set_results(td)
        bs._MEMO.update(key=None, data=None)
        bs._BACK.clear()

        def empty(path, q):
            if path == "/portfolio/settlements":
                return 200, {"settlements": [], "cursor": ""}
            if path == "/portfolio/positions":
                return 200, {"market_positions": [], "cursor": ""}
            return 200, {"balance": 0, "balance_dollars": "0.0000"}
        e = bs.all_bots(now=NOW, getter=empty, procs=[])
        ck(all(e["bots"][b]["money"]["ok"] and e["bots"][b]["money"]["complete"]
               and e["bots"][b]["money"]["all_time"]["markets"] == 0
               and e["bots"][b]["money"]["all_time"]["money"] == 0.0
               and e["bots"][b]["money"]["all_time"]["return_pct"] is None
               and e["bots"][b]["money"]["all_time"]["worst"] is None
               and e["bots"][b]["money"]["first_day"] is None for b in bs.BOTS),
           "EMPTY: nothing settled gives zero markets, no return, no worst/best -- nothing invented")
        ck(all(e["bots"][b]["running"]["alive"] is False and e["bots"][b]["activity_today"]["ok"] is False
               and e["bots"][b]["last_settled"] == [] and e["bots"][b]["open"]["count"] == 0 for b in bs.BOTS),
           "EMPTY: nothing running, no logs, no open positions, no last markets")
        ck(all(e["bots"][b]["money"][k]["pot_pct"] is None for b in bs.BOTS for k in bs.WINDOW_KEYS)
           and all(e["total"][k]["pot_pct"] is None for k in bs.WINDOW_KEYS),
           "EMPTY: nothing settled, so no percentage of any pot")
        txt = bs.text_summary("all", now=NOW + 1, getter=empty, procs=[])
        ck("nothing settled" in txt and "+$" not in txt and "-$" not in txt,
           "EMPTY: the phone text says 'nothing settled' and shows no gain or loss")
        ck(all(d["before_first"] for d in e["bots"]["pin"]["money"]["days_7"]),
           "EMPTY: every day is before the first settlement, so the phone lists none")
    finally:
        _paths.set_results(saved[0])
        bs._MEMO.clear()
        bs._MEMO.update(saved[1])
        bs._BACK.clear()
        bs._BACK.update(saved[2])
        shutil.rmtree(td, ignore_errors=True)


def test_weather_pot():
    saved = (_paths.RESULTS, dict(bs._MEMO), dict(bs._BACK))
    deps = _deps()
    # 6. THE WEATHER POT (2026-10-04): subaccount 3, whose cash sits in POOL 0. Worked by hand:
    #   $1,000 deposited; $50 moved main -> sub 3 in pool 0 at 3 AM ET Sep 29 (main keeps $950 in pool 2).
    #   sub 3 settled two Sep 29 brackets: NY sold YES at 40c x2, NO won: +0.80; CHI sold at 35c x2, YES
    #   won: -1.30 -> yesterday -0.50 on $2.50 put in. Open: MIA NO x2, $1.10. Cash pool 0 = 50 - 0.50 -
    #   1.10 = 48.40; pot now = 49.50 = 50 put in - 0.50 settled (explained to the cent). Yesterday's pot:
    #   it held $0 at midnight ET Sep 29, + the $50 moved in that day = $50 -> -0.50 is -1.0%; all time
    #   -1.0% of the $50 put in. A pool-2 read of sub 3 answers $0.00, as Kalshi does.
    # v-tg-active (2026-10-30): this world is subaccount 3 as it was 10-04..10-29 -- the weather pot in pool 0. Since the
    # jump band (10-30) the number 3 trades in pool 2 (SUB_POOL, POT_POOL_ONLY); the world runs on the old settings.
    td3 = tempfile.mkdtemp(prefix="botstats-wx-")
    pool_saved = (dict(bs.SUB_POOL), dict(bs.POT_POOL_ONLY))
    try:
        _paths.set_results(td3)
        bs.SUB_POOL["3"] = 0
        bs.POT_POOL_ONLY.pop("3", None)
        bs._MEMO.update(key=None, data=None)
        bs._BACK.clear()
        wx_rows = [S("KXHIGHNY-26SEP29-B72.5", "2026-09-30T14:00:05Z", "no", nn=2, nc=1.20),       # +0.80
                   S("KXHIGHCHI-26SEP29-T65", "2026-09-30T14:00:06Z", "yes", nn=2, nc=1.30)]       # -1.30
        wx_list = [{"subaccount_number": 0, "exchange_index": 0, "balance": "0.0000"},
                   {"subaccount_number": 0, "exchange_index": 2, "balance": "950.0000"},
                   {"subaccount_number": 1, "exchange_index": 0, "balance": "0.0000"},     # the NULL: empty
                   {"subaccount_number": 1, "exchange_index": 2, "balance": "0.0000"},
                   {"subaccount_number": 2, "exchange_index": 0, "balance": "0.0000"},     # the NULL: empty
                   {"subaccount_number": 2, "exchange_index": 2, "balance": "0.0000"},
                   {"subaccount_number": 5, "exchange_index": 2, "balance": "0.0000"},
                   {"subaccount_number": 4, "exchange_index": 0, "balance": "0.0000"},
                   {"subaccount_number": 3, "exchange_index": 0, "balance": "48.4000"}]
        wx_asked = []

        def wxf(path, q):
            wx_asked.append((path, dict(q or {})))
            sub = str((q or {}).get("subaccount"))
            if path.endswith("/transfers"):
                return 200, {"transfers": [{"amount_cents": 5000, "created_ts": T("2026-09-29T07:00:00Z"),
                                            "from_subaccount": 0, "to_subaccount": 3, "exchange_index": 0,
                                            "transfer_id": "w1"}], "cursor": ""}
            if path.endswith("/subaccounts/balances"):
                return 200, {"subaccount_balances": wx_list}
            if path.endswith("/deposits"):
                return 200, {"deposits": [deps[0]], "cursor": ""}
            if path.endswith("/withdrawals"):
                return 200, {"withdrawals": [], "cursor": ""}
            if path == "/portfolio/settlements":
                return 200, {"settlements": wx_rows if sub == "3" else [], "cursor": ""}
            if path == "/portfolio/positions":
                return 200, {"market_positions": [{"ticker": "KXHIGHMIA-26SEP30-B90.5", "position_fp": "-2.00",
                                                   "market_exposure_dollars": "1.10"}] if sub == "3" else [],
                             "cursor": ""}
            if path == "/portfolio/balance":
                cash_by = {("0", 2): "950.0000", ("3", 0): "48.4000"}
                return 200, {"balance": 0, "balance_dollars": cash_by.get((sub, q.get("exchange_index")), "0.0000")}
            return 404, {}
        J(os.path.join(td3, "dipsell-live-orders.jsonl"), [
            {"t": "2026-09-29T07:56:53Z", "ev": "start", "pid": 3955508, "subaccount": 3, "live": True,
             "cash": 50.0, "pot": 50.0, "start_pot": 50.0,
             "rails": {"contracts": 2, "max_open": 5, "one_order_per_market": True, "window_s": 10800,
                       "day_stop_frac": 0.25, "kill_after": 60, "max_fills": 100, "max_days": 14, "pool": 0},
             "trigger": {"drop_c": 10.0, "mid_c": [15.0, 85.0], "hours_left": [6.0, 12.0]}},
            {"t": "2026-09-30T13:01:00Z", "ev": "trigger", "act": True, "ticker": "KXHIGHMIA-26SEP30-B90.5"},
            {"t": "2026-09-30T13:01:01Z", "ev": "placed", "ticker": "KXHIGHMIA-26SEP30-B90.5", "order_id": "K1"},
            {"t": "2026-09-30T13:20:00Z", "ev": "fill", "ticker": "KXHIGHMIA-26SEP30-B90.5", "delta": 1.0,
             "filled": 1.0},
            {"t": "2026-09-30T13:40:00Z", "ev": "fill", "ticker": "KXHIGHMIA-26SEP30-B90.5", "delta": 1.0,
             "filled": 2.0},
            {"t": "2026-09-30T14:01:00Z", "ev": "trigger", "act": True, "ticker": "KXHIGHLAX-26SEP30-B80.5"},
            {"t": "2026-09-30T14:01:00Z", "ev": "rail_refused", "ticker": "KXHIGHLAX-26SEP30-B80.5",
             "why": "max_open"},
            {"t": "2026-09-30T15:01:00Z", "ev": "cancel", "ticker": "KXHIGHDEN-26SEP30-B70.5", "status": 200}])
        with open(os.path.join(td3, bs.VERSIONS_NAME), "w", encoding="utf-8") as fh:
            fh.write("# Versions\n\n"
                     "# v-dipsell-live -- LIVE 2026-09-29 07:56:53Z (pid 3955508, subaccount 3 pool 0, $50): weather\n"
                     "# v-reopen98 -- 2026-09-28 14:36:17Z (pid 3882400) -- LIVE: 98c\n")
        WXP = [(3955508, "2026-09-29T07:56:50Z", "C:\\Python314\\python.exe -u research\\sweep\\dipsell_live.py "
                "--subaccount 3 --live --minutes 21600"),
               (77, "", "python research\\sweep\\dipsell_live.py --subaccount 3 --dry-run --minutes 10")]
        w = bs.all_bots(now=NOW, getter=wxf, procs=WXP)
        wb = w["bots"]["weather"]
        ck("weather" in bs.BOTS and wb["label"] == "Weather dip-seller" and wb["subaccount"] == 3
           and wb["shares_subaccount_with"] == [] and wb["balance"]["note"] == "its own pot (subaccount 3)",
           "WEATHER: the dip-seller is a bot of its own, in its own pot (subaccount 3; the jump band, which took the number "
           "over on 10-30, does not run in this world, so it is not named)")
        ck(any(p == "/portfolio/balance" and q == {"subaccount": "3", "exchange_index": 0} for p, q in wx_asked)
           and not any(p == "/portfolio/balance" and q.get("subaccount") == "3" and q.get("exchange_index") != 0
                       for p, q in wx_asked)
           and all(q.get("exchange_index") == 2 for p, q in wx_asked
                   if p == "/portfolio/balance" and q.get("subaccount") in ("0", "1", "2")),
           "WEATHER: its cash is read from subaccount 3 in POOL 0 (and never pool 2, where Kalshi says $0.00); "
           "pots 0-2 still read pool 2")
        ck(wb["balance"]["dollars"] == 48.4 and wb["open"]["count"] == 1 and abs(wb["open"]["at_risk"] - 1.10) < 1e-9
           and wb["open"]["positions"][0]["side"] == "no",
           "WEATHER: cash $48.40, one open bracket (MIA NO x2, $1.10)")
        wm = wb["money"]
        ck(wm["yesterday"]["markets"] == 2 and abs(wm["yesterday"]["money"] - (-0.50)) < 1e-9
           and abs(wm["yesterday"]["put_in"] - 2.50) < 1e-9 and wm["today"]["markets"] == 0
           and wm["all_time"]["worst"]["what"] == "CHI high T65",
           "WEATHER: a bracket counts on its ticker's ET day (Sep 29); yesterday -$0.50 on $2.50 put in")
        ck(P(wm["yesterday"], 50.0, -1.0) and P(wm["all_time"], 50.0, -1.0, "money_in")
           and wm["today"]["pot_pct"] is None,
           "WEATHER: -1.0%% of its $50 pot yesterday and all time: %s / %s"
           % ((wm["yesterday"]["pot"], wm["yesterday"]["pot_pct"]), (wm["all_time"]["pot"], wm["all_time"]["pot_pct"])))
        wpc = w["pot_check"]
        ck(wpc["3"] and wpc["3"]["now"] == 49.5 and wpc["3"]["off"] is False
           and wpc["1"]["now"] == 0.0 and wpc["2"]["now"] == 0.0 and wpc["all"]["now"] == 999.5
           and wpc["all"]["off"] is False and w["balances"]["all"] == 998.4 and w["balances"]["weather"] == 48.4,
           "NULL: the EMPTY pool-0 rows of subaccounts 1 and 2 add $0 -- to their own pots, never to the weather "
           "pot ($49.50 = sub 3 alone); all pots $999.50 = $1,000 in - $0.50 settled, each pot once")
        ck(w["total"]["yesterday"]["by_bot"].get("weather") == -0.5
           and abs(w["total"]["all_time"]["money"] - (-0.5)) < 1e-9,
           "WEATHER: in the ALL-BOTS total, with its share listed")
        wr = wb["running"]
        ck(wr["alive"] is True and wr["pids"] == [3955508] and wr["version"] == "v-dipsell-live"
           and bs.version_of("pin")[0] == "v-reopen98" and "2 contracts an order" in wr["settings_text"]
           and "-25% of its $50.00 start" in wr["settings_text"] and "boot_all.ps1" in wr["keepalive"],
           "WEATHER: running (the --live copy, not the dry run), its own VERSIONS entry (never pin's), its rails")
        wa = wb["activity_today"]
        ck(wa["sent"] == 1 and wa["filled"] == 1 and wa["contracts_filled"] == 2 and wa["refused"] == 1
           and wa["cancelled"] == 1 and wa["triggers"] == 2 and wa["refused_why"] == {"max_open": 1},
           "WEATHER today by its log: 2 triggers, 1 order, 1 filled (2 contracts over two fills), 1 refused, "
           "1 cancelled")
        wt = bs.text_summary("all", now=NOW + 1, getter=wxf, procs=WXP)
        ck("weather $48.40" in wt and "weather yes" in wt and "| weather -$0.50 (-1.0%)" in wt,
           "WEATHER in the all-bots text: its cash, running, and its yesterday share")
        # NULL 2: money that is sub 1's in pool 0 stays sub 1's -- the weather pot does not move
        wx_list[2] = {"subaccount_number": 1, "exchange_index": 0, "balance": "5.0000"}
        w2 = bs.all_bots(now=NOW + 61, getter=wxf, procs=WXP)
        ck(w2["pot_check"]["3"]["now"] == 49.5 and w2["pot_check"]["1"]["now"] == 5.0,
           "NULL: $5 of subaccount 1 sitting in pool 0 is subaccount 1's, never the weather pot's")
    finally:
        _paths.set_results(saved[0])
        bs._MEMO.clear()
        bs._MEMO.update(saved[1])
        bs._BACK.clear()
        bs._BACK.update(saved[2])
        bs.SUB_POOL.clear()
        bs.SUB_POOL.update(pool_saved[0])
        bs.POT_POOL_ONLY.clear()
        bs.POT_POOL_ONLY.update(pool_saved[1])
        shutil.rmtree(td3, ignore_errors=True)


def test_jumpband_and_shown():
    saved = (_paths.RESULTS, dict(bs._MEMO), dict(bs._BACK))
    # 7. v-tg-active (2026-10-30): WHICH BOTS ARE SHOWN, and THE JUMP BAND in subaccount 3's pool 2. Worked by hand:
    #   $1,000 deposited Oct 1. Sub 3 pool 0 (the weather dip-seller): $50 in Oct 4, one bracket +$0.80 (Oct 5), $50.80
    #   back Oct 15 -> $0. Sub 3 pool 2 (the jump band): $50 in at 05:38Z Oct 30 (1:38 AM ET); BNB NO x5 at 88c +$0.56,
    #   ZEC YES x5 at 80c -$4.06 (both Oct 30), HYPE x5 open ($4.25 + $0.06 fee) -> pool-2 cash 50 + 0.56 - 4.06 - 4.31
    #   = $42.19; its pot now $46.50 = $50 put in - $3.50 settled. Main: pin BTC +$0.40 and a race leg +$0.40 today ->
    #   $951.60. Today all bots: +0.40 + 0.40 - 3.50 = -$2.70; all time -$1.90 (+ the weather's +0.80).
    NOW7 = float(calendar.timegm((2026, 10, 30, 12, 30, 0)))           # 8:30 AM ET, Fri Oct 30
    td4 = tempfile.mkdtemp(prefix="botstats-jb-")
    try:
        _paths.set_results(td4)
        bs._MEMO.update(key=None, data=None)
        bs._BACK.clear()
        bs._ACTIVE.update(t=0.0, v=None)
        jb_rows = [S("KXBNB15M-26OCT300545-45", "2026-10-30T09:45:46Z", "no", nn=5, nc=4.40, fee=0.04),        # +0.56
                   S("KXZEC15M-26OCT300745-45", "2026-10-30T11:45:50Z", "no", yn=5, yc=4.00, fee=0.06),        # -4.06
                   S("KXHIGHNY-26OCT05-B72.5", "2026-10-06T14:00:05Z", "no", nn=2, nc=1.20)]                  # +0.80 weather
        w7 = {"0": [S("KXBTC15M-26OCT300100-00", "2026-10-30T05:00:05Z", "no", nn=20, nc=19.60),             # +0.40 pin
                    S("KXCRYPTOLEAD15M-26OCT300030-SOL", "2026-10-30T04:31:00Z", "yes", yn=10, yc=9.60)],    # +0.40 race
              "3": jb_rows}
        list7 = [{"subaccount_number": n, "exchange_index": ix, "balance": b} for n, ix, b in (
            (0, 0, "0.0000"), (0, 2, "951.6000"), (1, 0, "0.0000"), (1, 2, "0.0000"), (2, 0, "0.0000"), (2, 2, "0.0000"),
            (3, 0, "0.0000"), (3, 2, "42.1900"), (4, 0, "0.0000"), (4, 2, "0.0000"), (5, 2, "0.0000"))]
        xf7 = [{"amount_cents": 5000, "created_ts": T("2026-10-04T07:00:00Z"), "from_subaccount": 0, "to_subaccount": 3,
                "exchange_index": 0, "transfer_id": "w1"},
               {"amount_cents": 5080, "created_ts": T("2026-10-15T05:33:00Z"), "from_subaccount": 3, "to_subaccount": 0,
                "exchange_index": 0, "transfer_id": "w2"},
               {"amount_cents": 5000, "created_ts": T("2026-10-30T05:38:07Z"), "from_subaccount": 0, "to_subaccount": 3,
                "exchange_index": 2, "transfer_id": "j1"}]
        asked7 = []

        def f7(path, q):
            asked7.append((path, dict(q or {})))
            sub = str((q or {}).get("subaccount"))
            if path.endswith("/transfers"):
                return 200, {"transfers": xf7, "cursor": ""}
            if path.endswith("/subaccounts/balances"):
                return 200, {"subaccount_balances": list7}
            if path.endswith("/deposits"):
                return 200, {"deposits": [{"amount_cents": 100000, "fee_cents": 0, "status": "applied",
                                           "finalized_ts": T("2026-10-01T12:00:00Z")}], "cursor": ""}
            if path.endswith("/withdrawals"):
                return 200, {"withdrawals": [], "cursor": ""}
            if path == "/portfolio/settlements":
                return 200, {"settlements": w7.get(sub, []), "cursor": ""}
            if path == "/portfolio/positions":
                return 200, {"market_positions": [{"ticker": "KXHYPE15M-26OCT300845-45", "position_fp": "5.00",
                                                   "market_exposure_dollars": "4.25", "fees_paid_dollars": "0.06"}]
                             if sub == "3" else [], "cursor": ""}
            if path == "/portfolio/balance":
                if q.get("exchange_index") != {"4": 0}.get(sub, 2):
                    return 200, {"balance": 0, "balance_dollars": "0.0000"}
                return 200, {"balance": 0, "balance_dollars": {"0": "951.6000", "3": "42.1900"}.get(sub, "0.0000")}
            return 404, {}
        jb_start = {"t": "2026-10-30T08:13:26.860378Z", "kind": "start", "pid": 2972, "live": True, "paper": False,
                    "dry": False, "subaccount": 3, "max_contracts": 5, "live_max_contracts": 20, "max_cost": 20.0,
                    "stop_line": -25.0, "day_stop": -15.0, "cash": {"0": 0.0, "2": 50.0}, "line_money": 0.0,
                    "series": ["KXBNB15M", "KXHYPE15M", "KXZEC15M", "KXNEAR15M"], "k": 2.0, "lo": 0.7, "hi": 0.9,
                    "fast_k": None, "rule_override": False, "tau": [10, 60],
                    "argv": ["research\\cleanroom\\jumpband_live.py", "--live", "--subaccount", "3", "--max-contracts", "5"]}
        jb_log = [jb_start,
                  {"t": "2026-10-30T09:44:28Z", "kind": "trigger", "outcome": "out_of_band", "ticker": "KXBNB15M-26OCT300545-45"},
                  {"t": "2026-10-30T09:44:29.0Z", "kind": "trigger", "outcome": "buy", "ticker": "KXBNB15M-26OCT300545-45"},
                  {"t": "2026-10-30T09:44:29.05Z", "kind": "order_sent", "cid": "jb-1", "ticker": "KXBNB15M-26OCT300545-45"},
                  {"t": "2026-10-30T09:44:29.068Z", "kind": "order", "status": 201, "filled": 5.0, "outcome": "fill",
                   "ticker": "KXBNB15M-26OCT300545-45", "side": "no", "qty": 5, "ask": 0.88},
                  {"t": "2026-10-30T09:44:29.069Z", "kind": "fill", "ticker": "KXBNB15M-26OCT300545-45", "series": "KXBNB15M",
                   "side": "no", "qty": 5.0, "price": 0.88, "cost": 4.4, "fee": 0.04, "pool": 2},
                  {"t": "2026-10-30T09:45:46Z", "kind": "settle", "ticker": "KXBNB15M-26OCT300545-45", "side": "no", "qty": 5.0,
                   "price": 0.88, "cost": 4.4, "fee": 0.04, "result": "no", "payout": 5.0, "money": 0.56, "won": True,
                   "run_money": 0.56, "day_money": 0.56, "line_money": 0.56, "cash": 50.56},
                  {"t": "2026-10-30T12:29:26.069Z", "kind": "order", "status": 201, "filled": 0.0, "outcome": "no_fill",
                   "ticker": "KXZEC15M-26OCT300830-30", "side": "yes", "qty": 5, "ask": 0.76},
                  {"t": "2026-10-30T12:29:26.07Z", "kind": "order_fail", "why": "no_fill", "ticker": "KXZEC15M-26OCT300830-30"},
                  {"t": "2026-10-30T12:29:40Z", "kind": "no_cash", "ticker": "KXNEAR15M-26OCT300830-30", "need": 4.4, "cash": 1.0},
                  {"t": "2026-10-30T12:29:41Z", "kind": "day_stop", "day": "2026-10-29", "day_money": -15.2, "day_stop": -15.0}]
        J(os.path.join(td4, "jumpband-live.jsonl"), jb_log)
        J(os.path.join(td4, "jumpband-paper.jsonl"), [{"t": "2026-10-30T09:44:29Z", "kind": "paper_buy",
                                                      "ticker": "KXBNB15M-26OCT300545-45", "qty": 100}])
        with open(os.path.join(td4, bs.VERSIONS_NAME), "w", encoding="utf-8") as fh:
            fh.write("# v-jb-live -- LIVE 2026-10-30 08:13:26Z (jumpband_live.py pid 2972, subaccount 3 pool 2, $50)\n"
                     "# v-wrongside -- LIVE 2026-10-28 01:17:20Z (pid 444): the pin bot\n")
        with open(os.path.join(td4, bs.SPEC["race"]["stop"]), "w", encoding="utf-8") as fh:
            fh.write("paused 10-28")
        for b in ("forecaster", "weather"):
            open(os.path.join(td4, bs.SPEC[b]["stop"]), "w", encoding="utf-8").close()
        P7 = [(444, "", "C:\\Python314\\python.exe -u C:\\kals-live-0925n\\research\\pinrun.py --live --size 20"),
              (3564, "", "\"C:\\Python314\\python.exe\" -u research\\cleanroom\\ladder_live.py --subaccount 1 --live"),
              (4408, "", "\"C:\\Python314\\python.exe\" -u research/pinracearm.py --live --max-contracts 20"),
              (676, "", "\"C:\\Python314\\python.exe\" -u research\\cleanroom\\fxtake_live.py --subaccount 5 --live"),
              (4276, "", "C:\\Python314\\python.exe -u research\\cleanroom\\jumpband_live.py --minutes 20160"),
              (2972, "2026-10-30T08:13:20Z", "C:\\Python314\\python.exe  -u research\\cleanroom\\jumpband_live.py --live "
                                             "--subaccount 3 --max-contracts 5 --minutes 20160")]
        PAPER_ONLY = [r for r in P7 if r[0] != 2972]
        # -- which bots are ACTIVE: the process + stop-file combinations
        ck(bs.active_from(bs._norm_procs(P7), True) == ("pin", "ladder", "fx", "jumpband"),
           "ACTIVE: pin, ladder, FX taker and the jump band; the coin race RUNS with its stop file set -> hidden; the "
           "forecaster and the weather dip-seller (stop files, not running) -> hidden: %s" % (bs.active_from(bs._norm_procs(P7), True),))
        ck("jumpband" not in bs.active_from(bs._norm_procs(PAPER_ONLY), True) and bs.is_bot("jumpband", P7[5][2])
           and not bs.is_bot("jumpband", P7[4][2])
           and not bs.is_bot("jumpband", "python research\\cleanroom\\jumpband_live.py --live --dry-run --subaccount 3"),
           "ACTIVE: the jump band's PAPER arm (no --live) and a --live --dry-run are not the live jump band")
        ck(bs.active_from(None, False) == ("pin", "ladder", "fx", "jumpband"),
           "ACTIVE, the process table UNREADABLE: every bot without a stop file is shown (never hidden on a failed read)")

        def _boom():
            raise OSError("boom")
        ck(bs.active_bots(procs=lambda: None) == ("pin", "ladder", "fx", "jumpband")
           and bs.active_bots(procs=P7) == ("pin", "ladder", "fx", "jumpband")
           and bs.active_bots(procs=_boom) == ("pin", "ladder", "fx", "jumpband"),
           "active_bots: a planted table, a callable, a failed read and a raising read all answer (fail-safe)")
        os.remove(os.path.join(td4, bs.SPEC["race"]["stop"]))
        ck(bs.active_from(bs._norm_procs(P7), True) == ("pin", "race", "ladder", "fx", "jumpband"),
           "ACTIVE: the race's stop file removed (its process still --live) -> the race is back, no code change")
        ck(bs.active_from(bs._norm_procs([r for r in P7 if r[0] != 4408]), True) == ("pin", "ladder", "fx", "jumpband"),
           "ACTIVE: no stop file but no live race process -> hidden")
        with open(os.path.join(td4, bs.SPEC["race"]["stop"]), "w", encoding="utf-8") as fh:
            fh.write("paused 10-28")
        # -- subaccount 3: whose market is whose
        ck(bs.owner("KXBNB15M-26OCT300545-45", "3") == "jumpband" and bs.owner("KXHYPE15M-26OCT300845-45", "3") == "jumpband"
           and bs.owner("KXZEC15M-26OCT300745-45", "3") == "jumpband" and bs.owner("KXNEAR15M-26OCT300830-30", "3") == "jumpband"
           and bs.owner("KXHIGHNY-26OCT05-B72.5", "3") == "weather" and bs.owner("KXHIGHTSFO-26OCT05-B72.5", "3") == "weather"
           and bs.owner("KXBNB15M-26OCT300545-45", "0") == "pin" and bs.SUB_POOL["3"] == 2 and bs.POT_POOL_ONLY["3"] == 2,
           "OWNER: in subaccount 3 a coin market is the jump band's, a KXHIGH bracket the weather dip-seller's; its cash "
           "read asks pool 2")
        a7 = bs.all_bots(now=NOW7, getter=f7, procs=P7)
        jb = a7["bots"]["jumpband"]
        ck(a7["active"] == ["pin", "ladder", "fx", "jumpband"] and a7["hidden"] == ["race", "forecaster", "weather"],
           "all_bots names the active bots and the hidden ones: %s / %s" % (a7["active"], a7["hidden"]))
        ck(any(p == "/portfolio/balance" and q == {"subaccount": "3", "exchange_index": 2} for p, q in asked7)
           and jb["balance"]["dollars"] == 42.19 and a7["balances"]["jumpband"] == 42.19,
           "JUMP BAND cash: subaccount 3's POOL 2 balance, $42.19")
        jm = jb["money"]
        ck(jm["today"]["markets"] == 2 and abs(jm["today"]["money"] - (-3.50)) < 1e-9
           and abs(jm["today"]["put_in"] - 8.40) < 1e-9 and jm["all_time"]["markets"] == 2
           and jb["open"]["count"] == 1 and jb["open"]["positions"][0]["side"] == "yes",
           "JUMP BAND money: today -$3.50 on $8.40 put in (2 coin markets), not the weather bracket; HYPE YES x5 open")
        ck(P(jm["all_time"], 50.0, -7.0, "money_in") and P(jm["today"], 50.0, -7.0),
           "JUMP BAND pot: 'put in' $50.00 (pool 2 only -- not $50 + $50 - $50.80 over both pools); today -7.0%% of the $50 "
           "it began with: %s / %s" % ((jm["all_time"]["pot"], jm["all_time"]["pot_pct"]), (jm["today"]["pot"], jm["today"]["pot_pct"])))
        pc7 = a7["pot_check"]
        ck(pc7["3"]["now"] == 46.5 and pc7["3"]["off"] is False and pc7["all"]["now"] == 998.1 and pc7["all"]["off"] is False,
           "JUMP BAND pot check: $46.50 = $50 in - $3.50 settled; all pots $998.10 explained to the cent")
        jr = jb["running"]
        ck(jr["alive"] is True and jr["pid"] == 2972 and jr["version"] == "v-jb-live" and bs.version_of("pin")[0] == "v-wrongside"
           and "up to 5 contracts a buy, at most $20.00 an order" in jr["settings_text"]
           and "favourite at 70c-90c" in jr["settings_text"] and "2+ standard deviations" in jr["settings_text"]
           and "10-60 s before the close" in jr["settings_text"] and "coins BNB HYPE ZEC NEAR" in jr["settings_text"]
           and "-$15.00" in jr["settings_text"] and "-$25.00" in jr["settings_text"] and jr["halted"] is None,
           "JUMP BAND running: pid 2972 (not the paper arm), its own version, its settings from its start record; "
           "yesterday's day stop is no halt today: %s" % jr["settings_text"])
        ja = jb["activity_today"]
        ck(ja["sent"] == 2 and ja["filled"] == 1 and ja["contracts_filled"] == 5 and ja["not_filled"] == 1
           and ja["refused"] == 1 and ja["refused_why"] == {"no_cash": 1} and ja["triggers"] == 2,
           "JUMP BAND today by its log: 2 jumps judged, 2 orders sent, 1 filled (5 contracts), 1 got nothing, 1 no_cash")
        jf = bs.fill_of("jumpband", jb_log[5])
        ck(jf and jf["contracts"] == 5.0 and jf["price"] == 0.88 and jf["side"] == "no" and jf["sub"] == "3"
           and bs.fill_of("jumpband", jb_log[4]) is None,
           "JUMP BAND fill: its 'fill' record (qty 5 at 88c, NO, subaccount 3); the 'order' record is not a second fill")
        with open(os.path.join(td4, "jumpband-live.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": "2026-10-30T12:29:50Z", "kind": "day_stop", "day": "2026-10-30", "day_money": -15.2,
                                 "day_stop": -15.0}) + "\n")
        jr2 = bs.bot("jumpband", now=NOW7 + 1, getter=f7, procs=P7)["running"]
        ck(jr2["halted"] and jr2["halted"]["what"] == "day_stop" and "its day stop -$15.00" in jr2["halted"]["why"]
           and "jumpband" in bs.active_from(bs._norm_procs(P7), True),
           "JUMP BAND halted for TODAY by its own day stop: shown as halted, still an active bot")
        # -- the hidden bots' money: ONE 'earlier' line, the totals unchanged
        e7 = a7["earlier"]
        t7 = a7["total"]
        ck(e7["ok"] and abs(e7["today"]["money"] - 0.40) < 1e-9 and e7["today"]["markets"] == 1
           and abs(e7["all_time"]["money"] - 1.20) < 1e-9 and e7["all_time"]["markets"] == 2,
           "EARLIER: the race's leg today (+$0.40) and the weather's old bracket (+$0.80) on one line, all time +$1.20")
        ok_sum = True
        for k in bs.WINDOW_KEYS:
            sb = bs.shown_by(a7, t7[k]["by_bot"])
            ok_sum = ok_sum and abs(sum(sb.values()) - t7[k]["money"]) < 1e-6 and not (set(sb) & {"race", "forecaster", "weather"})
            ok_sum = ok_sum and abs(sum(m[k]["money"] for _n, m in bs.shown_parts(a7) if m.get(k)) - t7[k]["money"]) < 1e-6
        ck(ok_sum and abs(t7["today"]["money"] - (-2.70)) < 1e-9 and abs(t7["all_time"]["money"] - (-1.90)) < 1e-9
           and bs.shown_by(a7, t7["today"]["by_bot"]) == {"pin": 0.4, "ladder": 0.0, "fx": 0.0, "jumpband": -3.5,
                                                       "earlier": 0.4, "other": 0.0}
           and bs.shown_by(a7, t7["today"]["by_bot_pot_pct"], "none")["earlier"] is None,
           "EARLIER: every window's per-bot split (active bots + 'earlier' + other) adds up to the unchanged total "
           "(today -$2.70, all time -$1.90); no hidden bot is named")
        sc7 = bs.shown_cash(a7)
        ck([k for k, _v in sc7] == ["main", "ladder", "jumpband", "fx"] and abs(sum(v for _k, v in sc7) - a7["balances"]["all"]) < 1e-6,
           "CASH line: main, ladder, jump band, FX taker -- the empty forecaster pot is not named, and it adds up: %s" % sc7)
        tx7 = bs.text_summary("all", now=NOW7 + 2, getter=f7, procs=P7)
        ck("jumpband -$3.50" in tx7 and "earlier +$0.40" in tx7 and "race" not in tx7.replace("Main-page", "")
           and "forecaster" not in tx7 and "weather" not in tx7,
           "ALL-BOTS text: the jump band named, the race / forecaster / weather not -- their money on the 'earlier' line")
    finally:
        _paths.set_results(saved[0])
        bs._MEMO.clear()
        bs._MEMO.update(saved[1])
        bs._BACK.clear()
        bs._BACK.update(saved[2])
        bs._ACTIVE.update(t=0.0, v=None)
        shutil.rmtree(td4, ignore_errors=True)


def test_describe_brackets():
    ck(bs.describe("KXHIGHTSFO-26SEP29-B72.5") == "SFO high B72.5" and bs.describe("KXHIGHNY-26SEP29-T65") == "NY high T65",
       "a weather bracket in words: city, high, bracket")


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_report"))
