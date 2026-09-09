"""Adversarial verification of the claim:
  'HARD_MAX 25 permits a single $24.70 order' and
  'MAX_RUN_STAKE $60 exceeds the $38.83 shard so the exchange rejects first'
Read-only. No orders. Simulates pinrun's own gates with the LIVE arguments.
"""
import os, sys, ast, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "research"))
import pintake

SIZE = 5.0; LOSS_ABORT = -21.00; MAX_POS = 3
print("constants: MAX_TAKE_COUNT=%r HARD_MAX=%r MAX_RUN_STAKE=%r LOSS_ABORT=%r MAX_TAU=%r"
      % (pintake.MAX_TAKE_COUNT, pintake.HARD_MAX, pintake.MAX_RUN_STAKE,
         pintake.LOSS_ABORT, pintake.MAX_TAU))

# --- 1. what count can pinrun ever pass? ------------------------------------
src = open(os.path.join(HERE, "..", "..", "research", "pinrun.py"), encoding="utf-8").read()
tree = ast.parse(src)
calls = []
for n in ast.walk(tree):
    if isinstance(n, ast.Call):
        f = n.func
        if isinstance(f, ast.Attribute) and f.attr == "take" and \
           isinstance(f.value, ast.Name) and f.value.id == "pintake":
            calls.append(n)
print("pintake.take() call sites in pinrun.py:", len(calls))
for c in calls:
    args = [ast.unparse(a) for a in c.args]
    print("   line", c.lineno, "positional args:", args)
    print("   -> count argument (7th positional) =", args[6] if len(args) > 6 else "?")

# --- 2. can HARD_MAX 25 ever be the binding rail from pinrun? ---------------
import pinrun  # noqa: E402  (import only; nothing runs)
