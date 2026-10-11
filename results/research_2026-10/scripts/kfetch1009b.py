"""Read-only Kalshi pulls for the 10-07 reads: main-account settlements (cache + new rows, in memory, saved to this
scratchpad only), subaccount 1 (ladder) settlements + fills, subaccount 3 (dip-seller) settlements, balances,
deposits / withdrawals / subaccount transfers since 10-06."""
import sys, os, json
sys.path.insert(0, r"C:\kals-repo\research")
os.environ.setdefault("KALS_SELFTESTED", "1")
import pinledger, pintake, ordercli, kauth
SP = os.path.dirname(os.path.abspath(__file__))
creds = {"base": pintake.PROD_ELECTIONS, "key_id": kauth.KEY_ID, "pk": ordercli.load_key(pintake.PROD_KEY_FILE)}
def get(path, q):
    return pintake._get(creds["base"], creds["pk"], creds["key_id"], path, q)
rows = pinledger.load_cache()
had = len(rows)
added, pages = pinledger.fetch(rows, creds, getter=get)
print("main ledger rows", had, "+", added, "pages", pages, "newest", max((s.get("settled_time") or "") for s in rows.values()))
json.dump({"settlements": rows}, open(os.path.join(SP, "ledger_1009b.json"), "w"))

def pull(path, key, q0, stop_before, field):
    out = []; cursor = None
    for i in range(60):
        q = dict(q0, limit=200)
        if cursor:
            q["cursor"] = cursor
        st, d = get(path, q)
        if st != 200 or not isinstance(d, dict):
            print(path, q0, "status", st, str(d)[:200]); return out
        got = d.get(key) or []
        out += got
        cursor = d.get("cursor")
        if not got or not cursor:
            break
        if field and min((s.get(field) or "9") for s in got) < stop_before:
            break
    return out

for sub in (1, 3):
    s = pull("/portfolio/settlements", "settlements", {"subaccount": sub}, "2026-09-28", "settled_time")
    print("sub", sub, "settlements", len(s))
    json.dump(s, open(os.path.join(SP, "sub%d_1009b.json" % sub), "w"))
f = pull("/portfolio/fills", "fills", {"subaccount": 1}, "2026-09-29", "created_time")
print("sub 1 fills", len(f))
json.dump(f, open(os.path.join(SP, "sub1_fills_1009b.json"), "w"))
x = {}
for path, key in (("/portfolio/deposits", "deposits"), ("/portfolio/withdrawals", "withdrawals"),
                  ("/portfolio/subaccounts/transfers", "transfers")):
    st, d = get(path, {"limit": 100})
    x[path] = {"status": st, "body": d}
    rows_ = (d or {}).get(key) if isinstance(d, dict) else None
    print(path, st, "rows", None if rows_ is None else len(rows_))
    for r in (rows_ or [])[:8]:
        print("   ", json.dumps(r)[:300])
json.dump(x, open(os.path.join(SP, "xfers_1009b.json"), "w"), default=str)
for q in ({}, {"subaccount": 1}, {"subaccount": 1, "exchange_index": 2}, {"subaccount": 3}, {"subaccount": 2}):
    st, d = get("/portfolio/balance", q)
    print("balance", q, st, json.dumps(d)[:300])
