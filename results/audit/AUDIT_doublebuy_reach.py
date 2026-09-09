#!/usr/bin/env python3
"""Reachability: with the LIVE arguments, does the open_pos overwrite ever let
the run take a trade that correctly-booked P&L would have refused?

Two runs, identical except for the settlement result:
  A) every close WINS  -> how long can the run go, and what does `committed` do
  B) a bank of wins, then DOUBLED losing closes -> does it trade past the point
     correct booking would have stopped it?

Read-only. Fake wire, DEMO base, production never armed, no HTTP.
"""
import sys, os, json, time as _rt, io, contextlib
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
import ordercli, pintake, pinrun

GRID = 60
def build(result_for, seed_realised=0.0, minutes=30.0, improve=True):
    class FakeTime:
        def __init__(s, t0): s.t = t0
        def time(s): return s.t
        def sleep(s, x): s.t += 1.0
        def gmtime(s, *a): return _rt.gmtime(*a)
        def strftime(s, *a): return _rt.strftime(*a)
        def strptime(s, *a): return _rt.strptime(*a)
    T0 = int(_rt.time()); ft = FakeTime(float(T0))
    pinrun.time = ft; pintake.time = ft   # check_take must see the same clock
    def cur_close(now): return ((int(now) - T0) // GRID + 1) * GRID + T0
    def tkname(cs): return f"KXBTC15M-AUDIT-{cs}"
    def fake_get(path, params=None):
        if path == "/markets" and params:
            cs = cur_close(ft.time())
            return 200, {"markets": [{"ticker": tkname(cs),
                "close_time": _rt.strftime("%Y-%m-%dT%H:%M:%SZ", _rt.gmtime(cs)),
                "floor_strike": 100.0,
                "custom_strike": {"floor_strike": "100.0", "round_digits": 2},
                "exchange_index": 2}]}
        if path.startswith("/markets/"):
            tk = path.split("/")[-1]
            cs = int(tk.rsplit("-", 1)[-1])
            n = (cs - T0)//GRID
            return 200, {"market": {"status": "finalized", "result": result_for(n)}}
        return 404, {}
    pinrun.get = fake_get
    class FakeBook:
        def __init__(s): s.seen = {}
        def best(s, tk):
            n = s.seen.get(tk, 0); s.seen[tk] = n+1
            p = 0.95 if (n == 0 or not improve) else 0.94
            return {"yes_ask": p, "yes_ask_size": 500.0, "no_ask": 1-p,
                    "no_ask_size": 500.0, "age_ms": 10, "suspect": False}
        def subscribe(s, l): pass
        def drop(s, l): pass
    class FakeIdx:
        def spot(s, iid): return int(ft.time()), 100.0, 0.1
        def sigma(s, iid): return 0.02
    pinrun.fair = lambda *a, **k: 0.999
    SENT = []
    def fake_send(base, pk, key_id, method, path, body=None, query=None):
        SENT.append(method)
        if method != "POST": return (-1, "no cancel expected")
        c = float(body["count"]); yp = float(body["price"])
        return (201, {"order_id": f"a{len(SENT)}",
                      "client_order_id": body["client_order_id"],
                      "fill_count": f"{c:.2f}", "remaining_count": "0.00",
                      "average_fill_price": yp,
                      "average_fee_paid": 0.07*yp*(1-yp)})
    ordercli.send = fake_send
    class A:
        live=True; minutes=0; loss_abort=-21.00; tau_max=30; size=5.0; max_positions=3
    A.minutes = minutes
    pinrun.SIZE = 5.0
    pinrun.CREDS.update({"base": pintake.DEMO, "pk": None, "key_id": "k"})
    pintake.reset_ledger(); pintake.LEDGER["realised"] = seed_realised
    LOG=[]
    def rec(kind, **kw): LOG.append(dict(kind=kind, **kw))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        state, fired = pinrun.trade_loop(A, rec, FakeBook(), FakeIdx(),
                                         {"KXBTC15M": "BRTI"})
    return state, LOG

def summarise(tag, state, LOG, seed):
    orders=[d for d in LOG if d["kind"]=="order" and float(d.get("filled") or 0)>0]
    setl=[d for d in LOG if d["kind"]=="settled"]
    halt=[d for d in LOG if d["kind"]=="halt"]
    paid=sum(float(o["filled"])*float(o["exec_price"]) for o in orders)
    fees=sum(float(o.get("fee_total") or 0) for o in orders)
    won =sum(float(o["filled"]) for o in orders
             if any(s["ticker"]==o["ticker"] and s["result"]==s["want"] for s in setl))
    lost=sum(float(o["filled"])*float(o["exec_price"]) for o in orders
             if any(s["ticker"]==o["ticker"] and s["result"]!=s["want"] for s in setl))
    true_pnl = seed + (won - paid) - fees
    print(f"--- {tag}")
    print(f"    closes settled     {len(setl)}   orders filled {len(orders)}")
    print(f"    TRUE P&L           ${true_pnl:+.4f}")
    print(f"    BOOKED realised    ${pintake.LEDGER['realised']:+.4f}")
    print(f"    committed left     ${pintake.LEDGER['committed']:.4f} "
          f"(cap ${pintake.MAX_RUN_STAKE:.2f})")
    print(f"    halt               {halt[0]['why'] if halt else 'none'}")
    return true_pnl

print("=" * 74)
s, L = build(lambda n: "yes", seed_realised=0.0, minutes=25.0)
summarise("A: every close WINS (doubled buys)", s, L, 0.0)
print()
print("=" * 74)
SEED = 3.00
s, L = build(lambda n: "no", seed_realised=SEED, minutes=25.0)
t = summarise(f"B: bank ${SEED:.2f} of wins, then every close LOSES (doubled)",
              s, L, SEED)
