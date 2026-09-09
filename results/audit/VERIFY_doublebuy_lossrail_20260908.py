#!/usr/bin/env python3
"""ADVERSARIAL VERIFICATION of the claim that the same-ticker double buy lets
a -$21.00 loss abort run to a TRUE -$42.20 drawdown.

The bookkeeping defect is real (AUDIT_doublebuy_verify.py proves it by driving
the real trade_loop). This probe asks the NEXT question: after one halved loss
is booked, can the run take ANY further risk?

pintake.LOSS_ABORT is -2.00 and pinrun never overrides it, so check_take()
should refuse every take once realised <= -2.00 -- long before the -$21.00
figure the abort was configured with.

Read-only. Sends nothing: ordercli.send is replaced, base is DEMO, production
is never armed, pinrun.get is replaced so no HTTP leaves the box.
"""
import sys, os, json, time as _rt
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"

import ordercli, pintake, pinrun

IID = "BRTI"
MK1 = "KXBTC15M-AUDIT-A"          # double-bought, then LOSES
MK2 = "KXBTC15M-AUDIT-B"          # the next close, after the loss is booked


class FakeTime:
    def __init__(self, t0): self.t = t0
    def time(self): return self.t
    def sleep(self, s): self.t += 1.0
    def gmtime(self, *a): return _rt.gmtime(*a)
    def strftime(self, *a): return _rt.strftime(*a)
    def strptime(self, *a): return _rt.strptime(*a)


T0 = _rt.time()
C1 = int(T0) + 25
C2 = int(T0) + 120
ft = FakeTime(T0)
pinrun.time = ft
iso = lambda s: _rt.strftime("%Y-%m-%dT%H:%M:%SZ", _rt.gmtime(s))


def mkt(tk, cs):
    return {"ticker": tk, "close_time": iso(cs), "floor_strike": 100.0,
            "custom_strike": {"floor_strike": "100.0", "round_digits": 2},
            "exchange_index": 2}


def fake_get(path, params=None):
    if path == "/markets" and params:
        now = ft.time()
        out = [m for m, cs in ((mkt(MK1, C1), C1), (mkt(MK2, C2), C2))
               if now < cs]
        return 200, {"markets": out}
    if path.startswith("/markets/"):
        return 200, {"market": {"status": "finalized", "result": "no"}}
    return 404, {}


pinrun.get = fake_get


class FakeBook:
    def __init__(self): self.n = {}
    def best(self, tk):
        i = self.n.get(tk, 0)
        self.n[tk] = i + 1
        p = 0.95 if (tk != MK1 or i == 0) else 0.94   # MK1's price improves 1c
        return {"yes_ask": p, "yes_ask_size": 500.0,
                "no_ask": 1.0 - p, "no_ask_size": 500.0,
                "age_ms": 10, "suspect": False}
    def subscribe(self, l): pass
    def drop(self, l): pass


class FakeIdx:
    def spot(self, iid): return int(ft.time()), 100.0, 0.1
    def sigma(self, iid): return 0.02


pinrun.fair = lambda *a, **k: 0.999

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


class A:
    live = True
    minutes = 200.0 / 60.0
    loss_abort = -21.00
    tau_max = 30
    size = 5.0
    max_positions = 3


pinrun.SIZE = 5.0
pinrun.CREDS.update({"base": pintake.DEMO, "pk": None, "key_id": "k"})
pintake.reset_ledger()
LOG = []


def rec(kind, **kw): LOG.append(dict(kind=kind, **kw))


print("LIVE ARGS: --size 5 --loss-abort -21.00 --max-positions 3, tau 3-30")
print(f"pintake.LOSS_ABORT (module rail, never overridden) = "
      f"{pintake.LOSS_ABORT:+.2f}\n")

state, fired = pinrun.trade_loop(A, rec, FakeBook(), FakeIdx(),
                                 {"KXBTC15M": IID})

print("=" * 74)
orders = [d for d in LOG if d["kind"] == "order"]
posts = sum(1 for m in SENT if m[0] == "POST")
for o in orders:
    print(f"  order {o['ticker']:<22} filled {o.get('filled')} "
          f"@ {o.get('exec_price')}  refused={o.get('refused')}")
print(f"\n  POSTs that reached the (fake) wire : {posts}")
print(f"  BOOKED realised                    : "
      f"${pintake.LEDGER['realised']:+.4f}")
paid = sum(float(o["filled"]) * float(o["exec_price"])
           for o in orders if o.get("filled"))
fees = sum(float(o.get("fee_total") or 0.0) for o in orders if o.get("filled"))
print(f"  TRUE cash lost (all fills settled NO): ${-(paid + fees):+.4f}")
print(f"  state['halted']                    : {state.get('halted')}")
mk2 = [o for o in orders if o["ticker"] == MK2]
print("\n" + "=" * 74)
if not mk2:
    print("  MK2: no order was even attempted at the second close")
else:
    r = mk2[0].get("refused") or []
    ok = any("LOSS ABORT" in s for s in r) and not mk2[0].get("filled")
    print(f"  MK2 attempted and REFUSED by the rail: {ok}")
    for s in r:
        print(f"    - {s}")
print(f"\n  ledger positions still open: "
      f"{json.dumps(pintake.LEDGER['positions'])}")
print(f"  committed: ${pintake.LEDGER['committed']:.4f}  "
      f"(MAX_RUN_STAKE ${pintake.MAX_RUN_STAKE:.2f})")
