#!/usr/bin/env python3
"""Realistic mix: a bank of ordinary single-fill WINS, then DOUBLED losing
closes. Which rail fires first, and does the open_pos overwrite buy the run an
extra losing close? Read-only; fake wire, DEMO base, production never armed.
"""
import sys, os, json, time as _rt, io, contextlib
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
import ordercli, pintake, pinrun

GRID, K = 60, 12               # first K closes win on a single fill
class FakeTime:
    def __init__(s, t0): s.t = t0
    def time(s): return s.t
    def sleep(s, x): s.t += 1.0
    def gmtime(s,*a): return _rt.gmtime(*a)
    def strftime(s,*a): return _rt.strftime(*a)
    def strptime(s,*a): return _rt.strptime(*a)
T0 = int(_rt.time()); ft = FakeTime(float(T0))
pinrun.time = ft; pintake.time = ft
idx_of = lambda cs: (cs - T0)//GRID - 1
def cur_close(now): return ((int(now)-T0)//GRID + 1)*GRID + T0
tk_of = lambda cs: f"KXBTC15M-AUDIT-{cs}"

def fake_get(path, params=None):
    if path == "/markets" and params:
        cs = cur_close(ft.time())
        return 200, {"markets":[{"ticker":tk_of(cs),
            "close_time":_rt.strftime("%Y-%m-%dT%H:%M:%SZ",_rt.gmtime(cs)),
            "floor_strike":100.0,
            "custom_strike":{"floor_strike":"100.0","round_digits":2},
            "exchange_index":2}]}
    if path.startswith("/markets/"):
        cs = int(path.rsplit("-",1)[-1])
        return 200, {"market":{"status":"finalized",
                               "result": "yes" if idx_of(cs) < K else "no"}}
    return 404, {}
pinrun.get = fake_get

class FakeBook:
    def __init__(s): s.seen={}
    def best(s, tk):
        cs = int(tk.rsplit("-",1)[-1]); n = s.seen.get(tk,0); s.seen[tk]=n+1
        if idx_of(cs) < K:  p = 0.95            # winners: no improvement -> 1 buy
        else:               p = 0.95 if n==0 else 0.94   # losers: doubled
        return {"yes_ask":p,"yes_ask_size":500.0,"no_ask":1-p,
                "no_ask_size":500.0,"age_ms":10,"suspect":False}
    def subscribe(s,l): pass
    def drop(s,l): pass
class FakeIdx:
    def spot(s,i): return int(ft.time()),100.0,0.1
    def sigma(s,i): return 0.02
pinrun.fair = lambda *a, **k: 0.999
SENT=[]
def fake_send(base,pk,key_id,method,path,body=None,query=None):
    SENT.append(method)
    if method!="POST": return (-1,"no cancel expected")
    c=float(body["count"]); yp=float(body["price"])
    return (201,{"order_id":f"a{len(SENT)}","client_order_id":body["client_order_id"],
                 "fill_count":f"{c:.2f}","remaining_count":"0.00",
                 "average_fill_price":yp,"average_fee_paid":0.07*yp*(1-yp)})
ordercli.send = fake_send
class A:
    live=True; minutes=40.0; loss_abort=-21.00; tau_max=30; size=5.0; max_positions=3
pinrun.SIZE=5.0
pinrun.CREDS.update({"base":pintake.DEMO,"pk":None,"key_id":"k"})
pintake.reset_ledger()
LOG=[]
def rec(kind,**kw): LOG.append(dict(kind=kind,**kw))
with contextlib.redirect_stdout(io.StringIO()):
    state,fired = pinrun.trade_loop(A,rec,FakeBook(),FakeIdx(),{"KXBTC15M":"BRTI"})

orders=[d for d in LOG if d["kind"]=="order" and float(d.get("filled") or 0)>0]
setl=[d for d in LOG if d["kind"]=="settled"]
halt=[d for d in LOG if d["kind"]=="halt"]
paid=sum(float(o["filled"])*float(o["exec_price"]) for o in orders)
fees=sum(float(o.get("fee_total") or 0) for o in orders)
won=sum(float(o["filled"]) for o in orders
        if any(s["ticker"]==o["ticker"] and s["result"]==s["want"] for s in setl))
true=(won-paid)-fees
byclose={}
for o in orders: byclose[o["ticker"]]=byclose.get(o["ticker"],0)+1
lose=[t for t in byclose if idx_of(int(t.rsplit('-',1)[-1]))>=K]
print(f"closes traded          {len(byclose)}   (doubled: {sum(1 for v in byclose.values() if v==2)})")
print(f"LOSING closes traded   {len(lose)}  -> {sorted(byclose[t] for t in lose)} buys each")
print(f"TRUE P&L               ${true:+.4f}")
print(f"BOOKED realised        ${pintake.LEDGER['realised']:+.4f}")
print(f"committed left         ${pintake.LEDGER['committed']:.4f} of ${pintake.MAX_RUN_STAKE:.2f}")
print(f"halt                   {halt[0]['why'] if halt else 'none (ran out of clock)'}")
print()
print("Counterfactual, correct booking: after losing close #1 realised would be")
w = pintake.LEDGER["realised"]
print(f"  booked-realised-before-losses  ${w + sum(-float(s['pnl_c'])/100 for s in setl if s['result']!=s['want']):+.4f}")
for s in setl:
    if s["result"]!=s["want"]:
        print(f"  loss close {s['ticker'][-10:]}  booked {float(s['pnl_c'])/100:+.4f}  "
              f"true {-2*float(s['cost'])*5 - 2*pinrun.billed_fee(float(s['cost']),5):+.4f}")
