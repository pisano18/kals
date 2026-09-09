"""GET-ONLY. Reads /portfolio/balance to check the '$38.83 crypto shard' claim."""
import sys, json
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
import kauth
from kauth import get
st, b = get("/portfolio/balance")
print("status", st)
print(json.dumps(b, indent=1)[:1200] if isinstance(b, dict) else b)
