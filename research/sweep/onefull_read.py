"""v-onefull read (READS_DUE one-full-bet): live logs since 2026-09-27 08:11:15Z.
1. Refused second full bets (gate rebuy_band while the market already held a full bet): each one's would-be result,
   priced at the refused price x the refused size (an UPPER bound on what the bot could have bought), outcome from
   our own Kalshi ledger row for that market (we held it, so the result is known).
2. The bar's first line: no market shows two full-size entry orders in one close."""
import glob, json, collections, calendar, time

START = "2026-09-27T08:11:15"
L = json.load(open(r"C:\kals-repo\results\kalshi_ledger.json", encoding="utf-8"))["settlements"]
result = {}
for s in L.values():
    result[s["ticker"]] = s.get("market_result")

ref = {}
orders = collections.defaultdict(list)
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
        if r.get("kind") == "refused" and r.get("gate") == "rebuy_band":
            ref.setdefault(tk, r)           # first refusal per market
        elif r.get("kind") == "order" and r.get("status_code") in (200, 201):
            orders[tk].append(r)

won = lost = 0
m_won = m_lost = 0.0
rows = []
for tk, r in sorted(ref.items(), key=lambda kv: kv[1]["t"]):
    res = result.get(tk)
    px, want = float(r["price"]), r["want"]
    # the second bet would have been ONE bet at most (size_now), never the whole displayed offer
    n = min(float(r.get("size") or 0), float(r.get("size_now") or r.get("size") or 0))
    if res not in ("yes", "no") or n <= 0:
        rows.append((r["t"], tk, want, px, n, res, None)); continue
    fee = 0.07 * px * (1 - px) * n
    if res == want:
        v = n * (1 - px) - fee; won += 1; m_won += v
    else:
        v = -(n * px + fee); lost += 1; m_lost += v
    rows.append((r["t"], tk, want, px, n, res, v))
for t, tk, want, px, n, res, v in rows:
    print("  %s %-26s %-3s %.3f x %5.1f -> %-4s %s" % (t[5:16], tk, want, px, n, res, "n/a" if v is None else "%+8.2f" % v))
print("refused second full bets: %d markets; would have won %d (+$%.2f), lost %d ($%.2f); net %+.2f"
      % (len(ref), won, m_won, lost, m_lost, m_won + m_lost))
# the bar "no double full bet": contracts HELD on one side vs the bet size then (late boost 1.5x and the
# half-bet late add are allowed, so > 2.0 bets on one side = a real double)
bet = {}
for tk, os_ in orders.items():
    sz = [float(o.get("size_now") or 0) for o in os_ if o.get("size_now")]
    bet[tk] = max(sz) if sz else None
big = []
for s_ in L.values():
    tk = s_["ticker"]
    if tk not in orders or s_["settled_time"] < START or "15M-" not in tk:
        continue
    y, no = float(s_["yes_count_fp"]), float(s_["no_count_fp"])
    held = max(y, no) - min(y, no) if False else max(y, no)
    b = bet.get(tk)
    if b and held > 2.0 * b + 0.5:
        big.append((tk, held, b))
print("15-min markets holding more than 2 bets on one side since the flag: %d %s" % (len(big), big[:10]))
