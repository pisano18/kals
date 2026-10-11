"""Follow-up to idxmove.py. Window B (index move over [s-3, s], s = send second) separates our losers; window
A ([s-4, s-1]) does not. Question: did the bot already HAVE print s when it sent? If yes, a plain gate on the
1/sec feed can use the signal today. If no, the signal needs the 5/sec feed (or a wait for the print).
For every market whose order carries t_ms_send (ms precision), read the recorder's receive time (_rx_ms) of
print s for that index from the raw tape and compare. Our recorder runs on the same box as the bot, so its
receive time is a fair proxy for when the bot's own socket got the print (both ~90 ms after the second).
Read-only; streams one hourly gz at a time."""
import json, gzip, re, os, time, collections, zlib
OUT = os.path.dirname(os.path.abspath(__file__))
TAPE = r"C:\kals\kalshi_data\cfbenchmarks_value"
IID = {"BTC": "BRTI", "ETH": "ETHUSD_RTI", "SOL": "SOLUSD_RTI", "XRP": "XRPUSD_RTI", "DOGE": "DOGEUSD_RTI",
       "BNB": "BNBUSD_RTI", "HYPE": "HYPEUSD_RTI", "NEAR": "NEARUSD_RTI", "ZEC": "ZECUSD_RTI"}
RX_ID = re.compile(r'"index_id":"([A-Z_]+)"')
RX_T = re.compile(r'\\"time\\":(\d+)')
RX_RX = re.compile(r'"_rx_ms":(\d+)')

rows = {r["ticker"]: r for r in json.load(open(os.path.join(OUT, "idxmove_rows.json")))}
ms = {}
for l in open(os.path.join(OUT, "live_markets.jsonl"), encoding="utf-8"):
    d = json.loads(l)
    if d["ticker"] not in rows: continue
    legs = [g for g in d.get("legs", []) if (g.get("filled") or 0) > 0]
    if not legs: continue
    g0 = min(legs, key=lambda g: g["t"])
    if g0.get("t_ms_send"): ms[d["ticker"]] = int(g0["t_ms_send"])
need = collections.defaultdict(set)
for tk, t in ms.items():
    need[rows[tk]["iid"]].add(t // 1000)
hours = sorted(set(s // 3600 for v in need.values() for s in v))
print("markets with ms send time", len(ms), "hours", len(hours))
rx = {}
for h in hours:
    fn = os.path.join(TAPE, time.strftime("%Y%m%dT%H", time.gmtime(h * 3600)) + ".jsonl.gz")
    if not os.path.exists(fn): continue
    try:
        with gzip.open(fn, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                a = RX_ID.search(line)
                if not a or a.group(1) not in need: continue
                b = RX_T.search(line); c = RX_RX.search(line)
                if not b or not c: continue
                sec = int(b.group(1)) // 1000
                if sec in need[a.group(1)]: rx[(a.group(1), sec)] = int(c.group(1))
    except (EOFError, OSError, zlib.error):
        pass
had = {}
for tk, t in ms.items():
    r = rows[tk]; key = (r["iid"], t // 1000)
    if key in rx: had[tk] = (rx[key] <= t, t - rx[key], (t % 1000))
print("matched", len(had))
fr = [v[2] for v in had.values()]; fr.sort()
print("send time within its second (ms): median %d, p10 %d, p90 %d" % (fr[len(fr) // 2], fr[len(fr) // 10], fr[9 * len(fr) // 10]))
print("print s already received at send: %d of %d" % (sum(v[0] for v in had.values()), len(had)))
for th in (1.0, 1.5, 2.0, 2.5):
    for flag in (True, False):
        sub = [rows[tk] for tk, v in had.items() if v[0] == flag]
        hit = [r for r in sub if r.get("B") is not None and r["B"] >= th]
        print("  B >= %.1f sd | bot %s print s: %4d markets, refused %3d, lost %2d, $ refused %+8.2f  (all markets in group: %d lost, net %+.2f)" % (
            th, "HAD   " if flag else "LACKED", len(sub), len(hit), sum(r["money"] < 0 for r in hit), sum(r["money"] for r in hit),
            sum(r["money"] < 0 for r in sub), sum(r["money"] for r in sub)))
