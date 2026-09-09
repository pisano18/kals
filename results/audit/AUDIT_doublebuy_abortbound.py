#!/usr/bin/env python3
"""How much does the run REALLY lose before the -$21.00 brake stops it, when
every losing close is a doubled (same-ticker, price-improved) close?

Read-only, sends nothing (fake wire, DEMO base, production never armed).
Same harness as AUDIT_doublebuy_verify.py, but many consecutive closes.
"""
import sys, os, json, time as _rt
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
import ordercli, pintake, pinrun

class FakeTime:
    def __init__(self, t0): self.t = t0
    def time(self): return self.t
    def sleep(self, s): self.t += 1.0
    def gmtime(self, *a): return _rt.gmtime(*a)
    def strftime(self, *a): return _rt.strftime(*a)
    def strptime(self, *a): return _rt.strptime(*a)

T0 = int(_rt.time())
GRID = 60                      # a "close" every 60 fake seconds
ft = FakeTime(float(T0)); pinrun.time = ft

def cur_close(now):
    return ((int(now) - T0) // GRID + 1) * GRID + T0
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
        return 200, {"market": {"status": "finalized", "result": "no"}}
    return 404, {}
pinrun.get = fake_get

class FakeBook:
    def __init__(self): self.seen = {}
    def best(self, tk):
        n = self.seen.get(tk, 0); self.seen[tk] = n + 1
        p = 0.95 if n == 0 else 0.94          # the price IMPROVES once
        return {"yes_ask": p, "yes_ask_size": 500.0, "no_ask": 1 - p,
                "no_ask_size": 500.0, "age_ms": 10, "suspect": False}
    def subscribe(self, l): pass
    def drop(self, l): pass
class FakeIdx:
    def spot(self, iid): return int(ft.time()), 100.0, 0.1
    def sigma(self, iid): return 0.02
pinrun.fair = lambda *a, **k: 0.999

SENT = []
def fake_send(base, pk, key_id, method, path, body=None, query=None):
    SENT.append((method, dict(body or {})))
    if method != "POST": return (-1, "no cancel expected")
    c = float(body["count"]); yp = float(body["price"])
    return (201, {"order_id": f"a{len(SENT)}", "client_order_id": body["client_order_id"],
                  "fill_count": f"{c:.2f}", "remaining_count": "0.00",
                  "average_fill_price": yp, "average_fee_paid": 0.07*yp*(1-yp)})
ordercli.send = fake_send

class A:
    live=True; minutes=60.0; loss_abort=-21.00; tau_max=30; size=5.0; max_positions=3
pinrun.SIZE = 5.0
pinrun.CREDS.update({"base": pintake.DEMO, "pk": None, "key_id": "k"})
pintake.reset_ledger()
LOG=[]
def rec(kind, **kw): LOG.append(dict(kind=kind, **kw))

import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    state, fired = pinrun.trade_loop(A, rec, FakeBook(), FakeIdx(), {"KXBTC15M": "BRTI"})

orders=[d for d in LOG if d["kind"]=="order" and float(d.get("filled") or 0)>0]
halt=[d for d in LOG if d["kind"]=="halt"]
paid=sum(float(o["filled"])*float(o["exec_price"]) for o in orders)
fees=sum(float(o.get("fee_total") or 0) for o in orders)
byclose={}
for o in orders: byclose.setdefault(o["ticker"],0); byclose[o["ticker"]]+=1
print(f"closes traded        {len(byclose)}   (buys per close {sorted(byclose.values())})")
print(f"contracts bought     {sum(float(o['filled']) for o in orders)}")
print(f"TRUE money lost      ${-(paid+fees):+.4f}   (every close settled against us)")
print(f"BOOKED realised      ${pintake.LEDGER['realised']:+.4f}")
print(f"advertised brake     ${A.loss_abort:+.2f}")
print(f"halt reason          {halt[0]['why'] if halt else 'NEVER HALTED'}")
print(f"ratio true/booked    {(paid+fees)/max(1e-9,-pintake.LEDGER['realised']):.2f}x")
