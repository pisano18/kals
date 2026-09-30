"""Live fills only: did a buy that came within N s AFTER a 'dumped' record (price far under fair, someone
dumping) on the same market lose more often than other buys? Outcome per market from the 'settled' records.
Money per market = sum of ALL settled pnl_c on that ticker (buy legs + hedge legs)."""
import glob, json, calendar, collections

def ts(t):
    return calendar.timegm(__import__("time").strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))

dumped = {}      # (ticker) -> first dump time, per close via ticker (ticker includes the close)
orders = collections.defaultdict(list)   # ticker -> [(t, tau, ask_seen, leg)]
settled = {}     # ticker -> (result, want, pnl_c)
files = sorted(glob.glob(r"C:\kals-repo\results\pinrun-live-*.jsonl"))
for f in files:
    for l in open(f, encoding="utf-8", errors="replace"):
        if '"kind": "dumped"' not in l and '"kind": "order"' not in l and '"kind": "settled"' not in l:
            continue
        try:
            r = json.loads(l)
        except Exception:
            continue
        k, tk = r.get("kind"), r.get("ticker")
        if not tk or not r.get("t"):
            continue
        t = ts(r["t"])
        if k == "dumped":
            dumped.setdefault(tk, (t, r.get("want"), r.get("disc_c")))
        elif k == "order" and r.get("status_code") in (200, 201) and r.get("want"):
            orders[tk].append((t, r.get("tau_at_send"), r.get("ask_seen"), r.get("leg"), r.get("want")))
        elif k == "settled" and r.get("pnl_c") is not None:
            o = settled.get(tk, (r.get("result"), None, 0.0))
            settled[tk] = (o[0], None, o[2] + float(r["pnl_c"]))

rows = []
for tk, os_ in orders.items():
    if tk not in settled:
        continue
    res, _, pnl = settled[tk]
    want = os_[0][4]
    lost = pnl < 0
    d = dumped.get(tk)
    first = min(o[0] for o in os_)
    gap = None
    if d and d[1] == want:
        # any buy on the same side at or after the dump, within 15 s
        after = [o[0] - d[0] for o in os_ if 0 <= o[0] - d[0] <= 15]
        gap = min(after) if after else None
    rows.append((tk, gap, lost, pnl / 100.0, first))

def summ(name, rs):
    n = len(rs); nl = sum(1 for r in rs if r[2]); m = sum(r[3] for r in rs)
    print("%-44s markets %4d  lost %3d (%.1f in 100)  money %+9.2f" % (name, n, nl, 100.0 * nl / n if n else 0, m))

print("live logs:", len(files), "files; markets with a buy and a settle:", len(rows))
summ("buy within 0-15 s after a same-side dump", [r for r in rows if r[1] is not None])
summ("  of which within 0-3 s", [r for r in rows if r[1] is not None and r[1] <= 3])
summ("all other buys", [r for r in rows if r[1] is None])
print("\nthe dump-then-buy markets:")
for r in sorted([r for r in rows if r[1] is not None], key=lambda x: x[4]):
    print("  %s  gap %2ds  %s  %+8.2f" % (r[0], r[1], "LOST" if r[2] else "won ", r[3]))
