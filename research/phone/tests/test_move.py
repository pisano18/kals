"""test_move.py -- /move: phone/commands/move.py and phone/actions/money.py (the phone's only POST to Kalshi).

v-tg-step12 (2026-10-30, lane R). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_move.py
NO REAL KALSHI: the getter is a fake Kalshi holding every pot's cash and open bets in memory; money.SENDER is a recorder
that applies the transfer to that fake (the real sender refuses under KALS_TESTING=1, checked); botdata.paths.RESULTS is
a temp folder (the journal). Also proves on botdata.pots that a move reads as money moved between pots, not money made.
"""
import copy
import json
import os
import sys
import tempfile
import time
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

from botdata import paths as P                                      # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_move_")
REAL_RESULTS = P.set_results(TMP)

import ordercli                                                      # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone.actions import confirm as CF                              # noqa: E402
from phone.actions import journal as J                               # noqa: E402
from phone.actions import money as M                                 # noqa: E402
from phone.commands import move as MV                                # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402

T = 1793448000.0                    # 2026-10-31 12:00Z (8:00 AM ET)
CASH0 = {(0, 2): 812.40, (0, 0): 40.00, (1, 2): 300.00, (2, 2): 0.0, (3, 2): 48.10, (3, 0): 0.0, (4, 0): 60.00,
         (4, 2): 0.01, (5, 2): 120.00}
OPEN0 = {0: [4.40, 7.90], 1: [], 2: [], 3: [4.40], 4: [], 5: [9.90]}


class FakeKalshi:
    """GET /portfolio/subaccounts/balances, /portfolio/balance, /portfolio/positions over in-memory pots; POSTs applied
    by apply()."""

    def __init__(self):
        self.cash = dict(CASH0)
        self.open = copy.deepcopy(OPEN0)
        self.fail = set()               # (path, sub) that answer 500
        self.gets = []
        self.posts = []
        self.answer = (200, {"ok": True})

    def get(self, path, params=None):
        params = dict(params or {})
        self.gets.append((path, params))
        if (path, params.get("subaccount")) in self.fail:
            return 500, "planted"
        if path == "/portfolio/subaccounts/balances":
            return 200, {"subaccount_balances": [{"subaccount_number": s, "exchange_index": p, "balance": v}
                                                 for (s, p), v in sorted(self.cash.items())]}
        if path == "/portfolio/balance":
            k = (int(params["subaccount"]), int(params["exchange_index"]))
            if k not in self.cash:
                return 404, "no such pot"
            return 200, {"balance_dollars": "%.4f" % self.cash[k]}
        if path == "/portfolio/positions":
            s = int(params["subaccount"])
            return 200, {"market_positions": [{"ticker": "KXBTC15M-X%d" % i, "position_fp": "5",
                                               "market_exposure_dollars": "%.2f" % v}
                                              for i, v in enumerate(self.open.get(s, []))], "cursor": ""}
        return 404, "unknown path %s" % path

    def send(self, path, body):
        self.posts.append((path, json.loads(json.dumps(body))))
        st, ans = self.answer
        if st in (200, 201):
            if path == M.SUB_PATH:
                a, p = body["amount_cents"] / 100.0, body["exchange_index"]
                self.cash[(body["from_subaccount"], p)] -= a
                self.cash[(body["to_subaccount"], p)] += a
            else:
                a = body["amount"] / 10000.0
                self.cash[(0, body["source_exchange_shard"])] -= a
                self.cash[(0, body["destination_exchange_shard"])] += a
        return st, ans


K = FakeKalshi()
M.SENDER = lambda path, body: K.send(path, body)
CF.CODE = lambda: "4821"
SLEPT = []
_REAL_EXECUTE = M.execute


def fresh():
    global K
    K = FakeKalshi()
    M.SENDER = lambda path, body: K.send(path, body)
    CF.drop()
    for f in os.listdir(TMP):
        os.remove(os.path.join(TMP, f))
    del SLEPT[:]


M.execute = lambda plan, getter, cfg=None, moved_today=0.0, sleep=None: _REAL_EXECUTE(
    plan, getter, cfg, moved_today, sleep=SLEPT.append)


def run(text, now=T, cfg=None, chat=7):
    c = FakeCtx(text=text, now=now, chat_id=chat, funds_getter=lambda path, params=None: K.get(path, params),
                cfg=cfg or {})
    return str(CM.by_name(c.cmd).run(c))


# ---- the page ---------------------------------------------------------------------------------------------------------
def test_listing_shows_every_pot_and_how():
    fresh()
    r = run("/move")
    for s in ("<b>main</b> · Main account, crypto pool: $812.40", "<b>pool0</b> · Main account, weather pool: $40.00",
              "<b>ladder</b> · subaccount 1 (Ladder), crypto pool: $300.00",
              "<b>jb</b> · subaccount 3 (Jump band), crypto pool: $48.10",
              "<b>fx</b> · subaccount 5 (FX taker), crypto pool: $120.00", "<b>sub4</b> · subaccount 4 (FX taker)",
              "open bets in account 0: $12.30 (2)", "/move 50 main jb", "$500.00 a move, $1,000.00 a day",
              "Cash in all pots"):
        assert s in r, (s, r)
    assert K.posts == [] and all(p != "POST" for p, _q in K.gets)


def test_listing_survives_kalshi_down():
    fresh()
    K.fail |= {("/portfolio/subaccounts/balances", None)}
    r = run("/move")
    assert "could not be read" in r or "could not read" in r, r
    assert not r.startswith("Could not build")


# ---- a move -------------------------------------------------------------------------------------------------------------
def test_plan_then_yes_moves_once():
    fresh()
    r = run("/move 50 main jb")
    assert "Move $50.00</b> from main (Main account, crypto pool) to jb (subaccount 3 (Jump band), crypto pool)?" in r, r
    assert "main: $812.40 → $762.40 (keeps $14.30 for its open bets)" in r and "jb: $48.10 → $98.10" in r, r
    assert "the pin bot resizes" in r and "the jump band is fixed size" in r and "/move yes 4821" in r, r
    assert K.posts == [], "a plan sends nothing"
    r = run("/move yes 4821", now=T + 30)
    assert "Moved $50.00" in r and "main: $812.40 → $762.40" in r and "jb: $48.10 → $98.10" in r, r
    assert "not money made" in r and SLEPT == [2], r
    assert len(K.posts) == 1
    path, body = K.posts[0]
    assert path == "/portfolio/subaccounts/transfer"
    assert set(body) == M.SUB_KEYS and body["from_subaccount"] == 0 and body["to_subaccount"] == 3
    assert body["amount_cents"] == 5000 and body["exchange_index"] == 2 and len(body["client_transfer_id"]) == 36
    j = J.read(kinds=("move",))
    assert len(j) == 1 and j[0]["ok"] and j[0]["amount"] == 50.0 and j[0]["status"] == 200 and j[0]["chat"] == 7
    assert "SIGNATURE" not in json.dumps(j) and "pem" not in json.dumps(j).lower()
    # the same message again: nothing waits, nothing moves
    assert "No move is waiting" in run("/move yes 4821", now=T + 31) and len(K.posts) == 1


def test_bot_to_main_and_sub_by_number():
    fresh()
    run("/move 25 fx main")
    assert "Moved $25.00" in run("/move yes 4821", now=T + 1)
    assert K.posts[-1][1]["from_subaccount"] == 5 and K.posts[-1][1]["to_subaccount"] == 0
    assert K.posts[-1][1]["exchange_index"] == 2
    run("/move 10 sub4 main", now=T + 2)
    assert "Moved $10.00" in run("/move yes 4821", now=T + 3)
    assert K.posts[-1][1]["from_subaccount"] == 4 and K.posts[-1][1]["exchange_index"] == 0, "sub 4 trades in pool 0"


def test_between_the_main_accounts_pools():
    fresh()
    r = run("/move 20 main pool0 pool2")
    assert "Move $20.00</b> from pool0 (Main account, weather pool) to main (Main account, crypto pool)?" in r, r
    assert "Moved $20.00" in run("/move yes 4821", now=T + 1)
    path, body = K.posts[-1]
    assert path == "/portfolio/intra_exchange_instance_transfer" and body == ordercli.build_transfer(20, 0, 2)
    assert body["amount"] == 200000 and K.cash[(0, 0)] == 20.0
    assert "Move $5.00</b> from pool0" in run("/move 5 pool0 pool2", now=T + 2)


def test_rails():
    fresh()
    for text, why in (("/move 600 main jb", "at most $500.00 a move"),
                      ("/move 60 jb main", "the source holds $48.10"),
                      ("/move 45 jb main", "under its open bets' cost $4.40 + $2.00 margin"),
                      ("/move 10 sub4 jb", "different pools"),
                      ("/move 10 main main", "same account"),
                      ("/move 10 main moon", "no pot is called 'moon'"),
                      ("/move ten main jb", "not an amount"),
                      ("/move 0 main jb", "at least $0.01"),
                      ("/move 10 main", "say it as /move 50 main jb"),
                      ("/move 10 sub9 main", "Kalshi does not list"),
                      ("/move 10 jb pool0 pool2", "main account's only"),
                      ("/move 10 main pool1 pool2", "pool 1 is not one the bots use")):
        r = run(text)
        assert "Not moved" in r and why in r, (text, r)
    assert "Nothing moved" in run("/move yes 4821") and K.posts == []
    # open bets unreadable -> refuse blind
    K.fail |= {("/portfolio/positions", 3)}
    assert "open bets could not be read" in run("/move 5 jb main")
    # cash unreadable at the send -> refuse blind (funds_read may still show the list's figure for the plan)
    fresh()
    run("/move 5 jb main")
    K.fail |= {("/portfolio/balance", 3)}
    r = run("/move yes 4821", now=T + 1)
    assert "Not moved" in r and "could not be read -- refusing blind" in r, r
    assert K.posts == []


def test_open_bets_keep_their_cost_and_margin():
    fresh()
    K.cash[(0, 2)] = 20.0                        # main holds open bets costing $12.30
    assert "under its open bets' cost $12.30 + $2.00 margin" in run("/move 10 main jb")
    assert "Move $5.70" in run("/move 5.70 main jb")
    # the weather pool of the main account is not where its bets are: no keep there
    assert "Move $40.00" in run("/move 40 main pool0 pool2")


def test_day_limit_counts_the_journal():
    fresh()
    K.cash[(0, 2)] = 2000.0
    for i, a in enumerate((400, 400)):
        run("/move %d main ladder" % a, now=T + 10 * i)
        assert "Moved" in run("/move yes 4821", now=T + 10 * i + 1)
    r = run("/move 300 main ladder", now=T + 100)
    assert "at most $1,000.00 a day" not in r and "at most $1000.00 a day: $800.00 moved today already" in r, r
    assert "Move $200.00" in run("/move 200 main ladder", now=T + 101)
    # the next ET day starts again
    assert "Move $300.00" in run("/move 300 main ladder", now=T + 86400)
    # configurable
    assert "at most $50.00 a move" in run("/move 60 main ladder", cfg={"move_max_usd": 50}, now=T + 86400)


def test_code_expiry_and_no():
    fresh()
    run("/move 5 main jb")
    assert "not the code" in run("/move yes 1111", now=T + 1)
    assert "expired" in run("/move yes 4821", now=T + MV.ASK_TTL_S + 1)
    run("/move 5 main jb", now=T + 200)
    assert "Forgotten" in run("/move no", now=T + 201)
    assert "No move is waiting" in run("/move yes 4821", now=T + 202)
    assert K.posts == []


def test_checked_again_on_fresh_cash():
    fresh()
    run("/move 40 jb main")
    K.cash[(3, 2)] = 30.0                        # it bought in the meantime
    r = run("/move yes 4821", now=T + 5)
    assert "Not moved" in r and "the source holds $30.00" in r and K.posts == [], r
    j = J.read(kinds=("move",))
    assert len(j) == 1 and j[0]["ok"] is False and j[0]["status"] is None


def test_kalshi_refusal_and_timeout_are_said():
    fresh()
    K.answer = (400, {"error": {"code": "insufficient_balance"}})
    run("/move 5 main jb")
    r = run("/move yes 4821", now=T + 1)
    assert "Not moved" in r and "Kalshi answered 400" in r and "insufficient_balance" in r, r
    K.answer = (-1, "could not reach Kalshi: TimeoutError")
    run("/move 5 main jb", now=T + 2)
    r = run("/move yes 4821", now=T + 3)
    assert "did not answer" in r and "check the cash below" in r, r
    assert MV.moved_today(T + 4) == 0.0, "a move Kalshi did not accept is not counted"


def test_idempotent_transfer_id():
    fresh()
    f = __import__("phone.commands.funds.read", fromlist=["funds_read"]).funds_read(K.get)
    a = M.plan_move(["50", "main", "jb"], f, now=T, plan_id="abc")
    b = M.plan_move(["50", "main", "jb"], f, now=T + 60, plan_id="abc")
    c = M.plan_move(["50", "main", "jb"], f, now=T, plan_id="abd")
    assert a["body"] == b["body"] and a["body"]["client_transfer_id"] != c["body"]["client_transfer_id"]
    want = ordercli.build_sub_transfer(50, 0, 3, "2026-10-31|pool2|abc")["client_transfer_id"]
    assert a["body"]["client_transfer_id"] == want, "ordercli's uuid5 of the move"


def test_the_one_door():
    for path, body in (("/portfolio/orders", {}), ("/portfolio/subaccounts", {"exchange_index": 2}),
                       (M.SUB_PATH, {"amount_cents": 1}),
                       (M.POOL_PATH, dict(ordercli.build_transfer(1, 0, 2), source_subaccount=3)),
                       (M.POOL_PATH, dict(ordercli.build_sub_transfer(1, 0, 3, "d")))):
        try:
            M.post(path, body)
        except M.Refused:
            continue
        raise AssertionError("got through: %s %s" % (path, body))
    try:
        M._signed_post("/portfolio/orders", {})
    except M.Refused:
        pass
    else:
        raise AssertionError("the real sender took an order path")
    assert P.testing() and M._signed_post(M.SUB_PATH, ordercli.build_sub_transfer(1, 0, 3, "d"))[0] == -1, \
        "the real sender refuses under KALS_TESTING=1"


def test_a_move_is_a_transfer_not_money_made():
    """botdata.pots: the transfer Kalshi lists for the move (the body we send + created_ts) moves 'money put in' from one
    pot to the other; every pot's unexplained gap and the whole account's money in stay the same."""
    from botdata import pots
    from botdata import tables
    subs = tables.SUBS
    body = M.plan_move(["50", "main", "jb"], __import__("phone.commands.funds.read", fromlist=["x"]).funds_read(
        FakeKalshi().get), now=T, plan_id="z")["body"]
    dep = {"amount_cents": 150000, "fee_cents": 0, "status": "completed", "created_ts": int(T - 86400 * 9)}
    fund3 = {"amount_cents": 5000, "from_subaccount": 0, "to_subaccount": 3, "exchange_index": 2,
             "created_ts": int(T - 86400 * 2)}

    def ctx(now_by_sub, transfers):
        led = {"deposits": [dep], "withdrawals": [], "transfers": transfers, "fetched": T, "err": None}
        return {"today": "2026-10-31", "led": led, "as_of": None,
                "subs": {s: {"now": now_by_sub.get(s, 0.0), "why": None, "days": {"2026-10-30": settled.get(s, 0.0)},
                             "complete": True} for s in subs}}
    settled = {"0": -1.90, "3": 2.30}
    before = ctx({"0": 1450.0 - 1.90, "3": 50.0 + 2.30}, [fund3])
    moved = dict(body, created_ts=int(T))
    after = ctx({"0": 1400.0 - 1.90, "3": 100.0 + 2.30}, [fund3, moved])
    cb, ca = pots.pot_check(before), pots.pot_check(after)
    for k in ("0", "3", "all"):
        assert cb[k]["unexplained"] == ca[k]["unexplained"] == 0.0, (k, cb[k], ca[k])
        assert cb[k]["settled"] == ca[k]["settled"], "a move is no money made"
    assert ca["3"]["money_in"] - cb["3"]["money_in"] == 50.0 and ca["0"]["money_in"] - cb["0"]["money_in"] == -50.0
    assert ca["all"]["money_in"] == cb["all"]["money_in"] == 1500.0
    assert pots.flows(after["led"], "3", T - 1, T + 1) == 50.0 and pots.flows(after["led"], None, T - 1, T + 1) == 0.0


def test_declaration():
    c = CM.of_module("phone.commands.move")
    assert len(c) == 1 and c[0].names == ("/move",) and c[0].section == "controls" and c[0].chart is None
    import tgcharts
    assert tgcharts.kind_of("/move") is None


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    try:
        for name, fn in tests:
            try:
                fn()
                passed += 1
                print("  ok   %s" % name, flush=True)
            except Exception:                                   # noqa: BLE001
                failed.append(name)
                print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    finally:
        P.set_results(REAL_RESULTS)
    print("test_move: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
