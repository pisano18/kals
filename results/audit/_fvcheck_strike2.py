"""READ-ONLY: strike_type / cap_strike / rules, per series. GET only."""
import sys, json
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get
SER = ["KXBTC15M","KXETH15M","KXSOL15M","KXXRP15M","KXDOGE15M","KXBNB15M",
       "KXBCH15M","KXZEC15M","KXHYPE15M","KXNEAR15M","KXADA15M"]
print(f"{'series':<12}{'strike_type':<20}{'cap_strike':>12}{'floor':>14}"
      f"{'settlement_timer':>18}{'notional':>10}")
for s in SER:
    st,b = get("/markets", {"series_ticker": s, "status":"open","limit":"2"})
    ms = (b or {}).get("markets") or []
    if not ms:
        print(f"{s:<12}(no open markets)"); continue
    m = ms[0]
    print(f"{s:<12}{str(m.get('strike_type')):<20}{str(m.get('cap_strike')):>12}"
          f"{str(m.get('floor_strike')):>14}"
          f"{str(m.get('settlement_timer_seconds')):>18}"
          f"{str(m.get('notional_value_dollars')):>10}")
