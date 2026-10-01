"""seller-gate (v-toxic-live, --toxic-fresh) read, as POSTMORTEM_2026-09-27 section 3 wrote it:
refused set 09-27 05:08Z .. now; each refused MARKET's result (tape population: upper bound on cost,
lower bound on benefit); early-entry refusal share."""
import glob, json, sys, time, collections
sys.path.insert(0, r"C:\kals-repo\research")
import kauth

START = "2026-09-27T05:08"
ref = {}                     # ticker -> first refusal record
early_orders, early_refused = set(), set()
full_orders = set()
for f in sorted(glob.glob(r"C:\kals-repo\results\pinrun-live-*.jsonl")):
    for l in open(f, encoding="utf-8", errors="replace"):
        if '"kind": "refused"' not in l and '"kind": "order"' not in l:
            continue
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if str(r.get("t", "")) < START:
            continue
        tk = r.get("ticker")
        if r.get("kind") == "refused" and r.get("gate") == "toxic_fresh":
            ref.setdefault(tk, r)
            if r.get("leg") == "early":
                early_refused.add(tk)
        elif r.get("kind") == "order" and r.get("status_code") in (200, 201):
            (early_orders if r.get("leg") == "early" else full_orders).add(tk)

print("refused markets: %d (%d on the early leg)" % (len(ref), len(early_refused)))
against = []
up_skipped = 0.0
rows = []
for tk, r in sorted(ref.items(), key=lambda kv: kv[1]["t"]):
    s, j = kauth.get("/markets/" + tk, {})
    res = (j.get("market") or {}).get("result") if s == 200 else None
    time.sleep(0.15)
    want, px = r["want"], float(r["price"])
    n = min(float(r.get("size") or 0), float(r.get("size_now") or r.get("size") or 0)) or float(r.get("size_now") or 0)
    bought_later = tk in early_orders or tk in full_orders
    if res not in ("yes", "no"):
        rows.append((r["t"], tk, want, px, n, res, None, bought_later)); continue
    won = res == want
    fee = 0.07 * px * (1 - px) * n
    pnl = (n * (1 - px) - fee) if won else -(n * px + fee)
    if won:
        up_skipped += pnl
    else:
        against.append((tk, pnl))
    rows.append((r["t"], tk, want, px, n, res, pnl, bought_later))
for t, tk, want, px, n, res, pnl, bl in rows:
    print("  %s %-28s %-3s %.3f x %5.1f -> %-4s %s%s" % (t[5:16], tk, want, px, n, res,
          "n/a" if pnl is None else "%+8.2f" % pnl, "  (bought later anyway)" if bl else ""))
print("settled AGAINST us: %d  %s" % (len(against), ", ".join("%s %+.2f" % a for a in against)))
print("skipped-wins UPPER bound: $%.2f" % up_skipped)
den = len(early_orders | early_refused)
print("early-leg markets: %d ordered, %d refused by the gate -> %.0f in 100 refused"
      % (len(early_orders), len(early_refused), 100.0 * len(early_refused) / den if den else 0))
