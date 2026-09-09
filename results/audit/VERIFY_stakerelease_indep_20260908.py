"""INDEPENDENT verification of the claimed per-CONTRACT stake release.

Adversarial design notes:
  * The COMMIT side is not simulated: pintake.take()/_book() are the real
    functions, driven through a stubbed ordercli.send so nothing reaches a
    wire.  Guards assert the stub is installed and that pintake shares it.
  * The RELEASE side is not retyped: the two statements are EXTRACTED
    VERBATIM from research/pinrun.py and exec()'d, so the probe follows the
    file rather than my memory of it.
  * Every rail is read from the CONSTANTS (pintake.MAX_RUN_STAKE,
    pintake.MAX_TAKE_COUNT), never from a literal -- repo rule.
"""
import os, re, sys, time, textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "research"))
import ordercli, pintake

SIZE  = 5.0      # the LIVE argument of pid 3997812
PRICE = 0.975    # the LIVE fill actually observed 2026-09-08T16:59:49Z

# ---- stub the wire.  Nothing may leave this process. ------------------------
SENT = []
def _fake_send(base, pk, key_id, method, path, body=None, **kw):
    SENT.append((method, path))
    c = float(body["count"]); p = float(body["price"])
    return 201, {"order": {"order_id": "probe-%d" % len(SENT), "status": "executed",
                           "fill_count": c, "remaining_count": 0.0,
                           "average_fill_price": p, "average_fee_paid": 0.0017}}
ordercli.send = _fake_send
assert pintake.ordercli is ordercli and ordercli.send is _fake_send

# ---- extract the release, verbatim, from pinrun.py --------------------------
src = open(os.path.join(ROOT, "research", "pinrun.py"), encoding="utf-8").read()
i = src.index('pintake.LEDGER["committed"] = max(\n', src.index("def reconcile"))
j = src.index('pintake.LEDGER["positions"].pop(tk, None)\n', i)
RELEASE_SRC = textwrap.dedent(
    src[src.rindex("\n", 0, i) + 1: j + len('pintake.LEDGER["positions"].pop(tk, None)\n')])
print("RELEASE STATEMENTS EXACTLY AS THEY STAND IN research/pinrun.py:")
for ln in RELEASE_SRC.rstrip().splitlines():
    print("    | " + ln)
print()

CODE = compile(RELEASE_SRC, "pinrun-release", "exec")
def release(tk, cost):
    exec(CODE, {"pintake": pintake, "max": max, "float": float},
         {"tk": tk, "cost": cost})

# ---- drive it ---------------------------------------------------------------
pintake.reset_ledger()
now = time.time(); close = now + 20.0
print("constants: MAX_RUN_STAKE=$%.2f  MAX_TAKE_COUNT=%s  SIZE=%s  PRICE=%s"
      % (pintake.MAX_RUN_STAKE, pintake.MAX_TAKE_COUNT, SIZE, PRICE))
print("per-ORDER stake (ordercli.collateral) = $%.4f ; per-CONTRACT price = $%.4f\n"
      % (SIZE * PRICE, PRICE))

n = 0; leak = None
while n < 60:
    n += 1
    tk = "T%d" % n
    v = pintake.check_take(pintake.build_take(tk, "no", PRICE, SIZE, 2),
                           close, now, base=pintake.DEMO)
    if v:
        print("trade %d: REFUSED BY THE RAIL -> %s" % (n, v[0]))
        break
    out = pintake.take(pintake.DEMO, "pk", "kid", tk, "no", PRICE, SIZE,
                       close, exchange_index=2, now_epoch=now)
    assert not out["refused"] and out["filled"] == SIZE, out
    after_fill = pintake.LEDGER["committed"]
    pos = dict(pintake.LEDGER["positions"][tk])
    release(tk, out["exec_price"])
    after_settle = pintake.LEDGER["committed"]
    if leak is None:
        leak = after_settle
    if n <= 3 or n >= 13:
        print("trade %2d: committed after fill $%7.4f -> after settlement $%7.4f"
              "   | position record held cost $%.4f over %.1f contracts"
              % (n, after_fill, after_settle, pos["cost"], pos["contracts"]))

print()
print("sends that reached the (stubbed) wire: %d" % len(SENT))
print("leak per settled trade: $%.4f   ==  (SIZE-1)*price = $%.4f"
      % (leak, (SIZE - 1) * PRICE))
print("committed now $%.4f" % pintake.LEDGER["committed"])
print("risk_abort stake test  committed >= MAX_RUN_STAKE ($%.2f)  ->  %s"
      % (pintake.MAX_RUN_STAKE, pintake.LEDGER["committed"] >= pintake.MAX_RUN_STAKE))
print("open positions in ledger: %d  (position cap cannot fire)"
      % len(pintake.LEDGER["positions"]))
print("realised $%.4f  (loss abort cannot fire)" % pintake.LEDGER["realised"])
