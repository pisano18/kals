#!/usr/bin/env python3
"""INDEPENDENT VERIFICATION of the claim:

  "Two buys on the same ticker in one close overwrite each other in
   open_pos, so reconcile() books HALF the contracts."

Read-only. Sends nothing: ordercli.send is replaced by a fake wire, the base
is DEMO, production is never armed, and pinrun.get is replaced so no HTTP
leaves the box. Drives the REAL trade_loop with a REAL pintake.take (so every
pintake rail actually runs) and reports what reconcile() books against what
was really paid.
"""
import sys, os, json, time as _rt, calendar
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"

import ordercli, pintake, pinrun

TK = "KXBTC15M-AUDIT-T0"
IID = "BRTI"

# ---------------- fake clock inside pinrun only -----------------------------
class FakeTime:
    def __init__(self, t0): self.t = t0
    def time(self): return self.t
    def sleep(self, s): self.t += 1.0
    def gmtime(self, *a): return _rt.gmtime(*a)
    def strftime(self, *a): return _rt.strftime(*a)
    def strptime(self, *a): return _rt.strptime(*a)

T0 = _rt.time()
CLOSE_S = int(T0) + 25
ft = FakeTime(T0)
pinrun.time = ft

# ---------------- fake REST ------------------------------------------------
iso = _rt.strftime("%Y-%m-%dT%H:%M:%SZ", _rt.gmtime(CLOSE_S))
FINAL = {"on": False}
def fake_get(path, params=None):
    if path == "/markets" and params:
        return 200, {"markets": [{"ticker": TK, "close_time": iso,
                                  "floor_strike": 100.0,
                                  "custom_strike": {"floor_strike": "100.0",
                                                    "round_digits": 2},
                                  "exchange_index": 2}]}
    if path.startswith("/markets/"):
        # we buy YES; the market settles NO -> a LOSING close
        return 200, {"market": {"status": "finalized", "result": "no"}}
    return 404, {}
pinrun.get = fake_get

# ---------------- fake book: the price IMPROVES by 1c ----------------------
PRICES = [0.95, 0.94]
class FakeBook:
    def __init__(self): self.i = 0
    def best(self, tk):
        p = PRICES[min(self.i, len(PRICES) - 1)]
        self.i += 1
        return {"yes_ask": p, "yes_ask_size": 500.0,
                "no_ask": 1.0 - p, "no_ask_size": 500.0,
                "age_ms": 10, "suspect": False}
    def subscribe(self, l): pass
    def drop(self, l): pass

class FakeIdx:
    def spot(self, iid): return int(ft.time()), 100.0, 0.1
    def sigma(self, iid): return 0.02

pinrun.fair = lambda *a, **k: 0.999          # model says YES is a lock

# ---------------- fake wire: every order fills in full ---------------------
SENT = []
def fake_send(base, pk, key_id, method, path, body=None, query=None):
    SENT.append((method, path, dict(body or {})))
    if method != "POST":
        return (-1, "no cancel expected")
    c = float(body["count"]); yp = float(body["price"])
    return (201, {"order_id": f"audit-{len(SENT)}",
                  "client_order_id": body["client_order_id"],
                  "fill_count": f"{c:.2f}", "remaining_count": "0.00",
                  "average_fill_price": yp,
                  "average_fee_paid": 0.07 * yp * (1 - yp)})
ordercli.send = fake_send

# ---------------- run ------------------------------------------------------
class A:
    live = True; minutes = 0.0; loss_abort = -21.00
    tau_max = 30; size = 5.0; max_positions = 3
A.minutes = 90.0 / 60.0            # 90 FAKE seconds: fires, close, settle

pinrun.SIZE = 5.0
pinrun.CREDS.update({"base": pintake.DEMO, "pk": None, "key_id": "k"})
pintake.reset_ledger()
LOG = []
def rec(kind, **kw): LOG.append(dict(kind=kind, **kw))

state, fired = pinrun.trade_loop(A, rec, FakeBook(), FakeIdx(), {"KXBTC15M": IID})

# ---------------- what happened -------------------------------------------
orders = [d for d in LOG if d["kind"] == "order"]
setl   = [d for d in LOG if d["kind"] == "settled"]
paid   = sum(float(o["filled"]) * float(o["exec_price"]) for o in orders)
fees   = sum(float(o.get("fee_total") or 0.0) for o in orders)
conts  = sum(float(o["filled"]) for o in orders)

print("=" * 72)
print(f"signals             {state.get('signals')}")
print(f"orders SENT to wire {sum(1 for m in SENT if m[0]=='POST')}")
for o in orders:
    print(f"   fill {o['filled']} @ {o['exec_price']}  ticker {o['ticker']}")
print(f"pintake position    {json.dumps(pintake.LEDGER['positions'])}")
print(f"contracts really held  {conts}")
print(f"dollars really paid    ${paid:.4f}  (+ fees ${fees:.4f})")
print(f"TRUE loss on a NO settle  ${-(paid+fees):+.4f}")
print("-" * 72)
for s in setl:
    print(f"reconcile booked: {s['ticker']} {s['want']} vs {s['result']} "
          f"cost {s['cost']} pnl {s['pnl_c']}c")
print(f"BOOKED realised       ${pintake.LEDGER['realised']:+.4f}")
print(f"state['open_cost']    ${state.get('open_cost', 0.0):.4f}")
print(f"halted                {state.get('halted')}")
print("=" * 72)
short = (-(paid + fees)) - pintake.LEDGER["realised"]
print(f"UNBOOKED LOSS         ${short:+.4f}   "
      f"({100*short/max(1e-9,(paid+fees)):.1f}% of the real loss invisible)")
