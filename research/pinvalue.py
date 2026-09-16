#!/usr/bin/env python3
"""pinvalue.py -- money per hour, not buys per hour. Where the value actually
comes from, and whether any of it is predictable.

THE OPERATOR, 2026-09-15: "total percentage return on buys instead of quantity
of buys in a time period because that's a deeper way to finding total value...
then we can see if it's truly random or has any correlation, then maybe we can
figure out how to profit on that correlation."

THE DECOMPOSITION, which is the whole point. Money in an hour is three separate
things multiplied together, and each can move on its own:

    $ per hour  =  buys per hour  x  dollars staked per buy  x  return per dollar

`pinwhen` already showed the FIRST factor is higher in calm markets (59% of
closes buy when calm, 31% when choppy). But a calm market's near-certainties
are EXPENSIVE -- a 97c buy can only return 3% -- so the third factor should run
the other way. If the two cancel, then chasing calm hours is worth nothing and
the counts were a distraction. That is the question this file answers.

HOW A TRADE'S MONEY IS COMPUTED, and why not from the log's own field. The
`settled` record carries `pnl_c` and `realised`, and their meaning changed
across bot versions (one run's `pnl_c` is a per-trade figure, a later run's
equals `realised * 100`, a running total). So nothing here reads either. Each
market's money is rebuilt from the FILLS:

    profit = filled x (1 - price) - fee     if the side we bought settled true
    profit = -filled x price   - fee        otherwise
    stake  = filled x price

HEDGES ARE SEPARATED. A hedge buys the OTHER side of the same market, so an
order whose book side differs from the entry's is a hedge leg and wins exactly
when the entry loses. Counting one as the other would report a hedged loss as
two losses.

AND THE TOTAL IS RECONCILED against the account's own bank movement over the
same window before any of it is believed. If those two disagree by more than a
few percent, the report says so and stops.

    python research/pinvalue.py --selftest
    python research/pinvalue.py
"""
import collections
import datetime as dt
import glob
import json
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import downtime                                              # noqa: E402

OUT_MD = os.path.join(REPO, "results", "VALUE.md")
OUT_ROWS = os.path.join(REPO, "results", "value_trades.jsonl")


def trade_money(filled, price, fee_total, won):
    """(profit, stake) in dollars for one fill."""
    stake = filled * price
    profit = (filled * (1.0 - price) if won else -stake) - (fee_total or 0.0)
    return profit, stake


def close_of_ticker(tk):
    """KXBTC15M-26SEP151745-45 -> epoch of that close. The stamp is EASTERN."""
    m = re.match(r"^KX[A-Z]+15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-", tk)
    if not m:
        return None
    yy, mon, dd, hh, mi = m.groups()
    try:
        day = dt.datetime.strptime(yy + mon + dd, "%y%b%d")
    except ValueError:
        return None
    naive = day.replace(hour=int(hh), minute=int(mi))
    secs = int((naive - dt.datetime(1970, 1, 1)).total_seconds())
    # the stamp is wall-clock Eastern; subtracting that day's offset gives UTC
    return secs - downtime.et_offset(secs + 4 * 3600)


def rank_corr(xs, ys):
    """Spearman rank correlation, -1 to 1, robust to the fat tails here."""
    n = len(xs)
    if n < 10:
        return None
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return None if dx == 0 or dy == 0 else num / (dx * dy)


def corr_p(xs, ys, n_shuffle=2000, seed=31):
    """How often chance alone produces a correlation this strong."""
    obs = rank_corr(xs, ys)
    if obs is None:
        return None, None
    rng = random.Random(seed)
    pool = list(ys)
    worse = 0
    for _ in range(n_shuffle):
        rng.shuffle(pool)
        r = rank_corr(xs, pool)
        if r is not None and abs(r) >= abs(obs):
            worse += 1
    return obs, (worse + 1) / float(n_shuffle + 1)


def bucket_p(labels, values, n_shuffle=2000, seed=77):
    """How unusual the spread in AVERAGE VALUE across buckets is.

    Money is not a coin flip: one loss at 95c wipes out thirty-odd wins, so a
    bucket's average is dominated by whether a loss happened to land in it. The
    labels are shuffled against the per-trade values, which keeps the same
    handful of losses and asks how often chance drops them this unevenly."""
    def spread(lab):
        agg = collections.defaultdict(list)
        for l, v in zip(lab, values):
            agg[l].append(v)
        means = [sum(v) / len(v) for v in agg.values() if len(v) >= 10]
        return (max(means) - min(means)) if len(means) >= 2 else None

    obs = spread(labels)
    if obs is None:
        return None, None
    rng = random.Random(seed)
    pool = list(labels)
    worse = 0
    for _ in range(n_shuffle):
        rng.shuffle(pool)
        sp = spread(pool)
        if sp is not None and sp >= obs - 1e-12:
            worse += 1
    return obs, (worse + 1) / float(n_shuffle + 1)


def load_trades():
    """One row per MARKET we bought: entry and hedge legs combined.

    Returns (rows, warnings)."""
    orders, settled, warn = [], {}, []
    for p in sorted(glob.glob(os.path.join(REPO, "results", "pinrun-live-*.jsonl"))):
        for line in open(p, encoding="utf-8", errors="ignore"):
            if '"order"' not in line and '"settled"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("kind") == "settled":
                settled.setdefault(d["ticker"], d)
            elif d.get("kind") == "order" and (d.get("filled") or 0) > 0:
                orders.append(d)
    by_mkt = collections.defaultdict(list)
    for o in orders:
        by_mkt[o["ticker"]].append(o)
    rows = []
    for tk, legs in by_mkt.items():
        s = settled.get(tk)
        if not s:
            warn.append("no settlement on file for " + tk)
            continue
        want, res = s.get("want"), s.get("result")
        if want not in ("yes", "no") or res not in ("yes", "no"):
            continue
        entry_side = "bid" if want == "yes" else "ask"
        prof = stake = hedge_stake = 0.0
        contracts = 0.0
        entry_px = None
        for o in legs:
            side = (o.get("body") or {}).get("side")
            px = o.get("exec_price")
            if px is None:
                continue
            is_entry = (side == entry_side)
            won = (res == want) if is_entry else (res != want)
            pr, st = trade_money(float(o["filled"]), float(px),
                                 float(o.get("fee_total") or 0.0), won)
            prof += pr
            stake += st
            if is_entry:
                contracts += float(o["filled"])
                entry_px = px if entry_px is None else entry_px
            else:
                hedge_stake += st
        cs = close_of_ticker(tk)
        if cs is None or stake <= 0:
            continue
        rows.append({"ticker": tk, "close": cs, "won": res == want,
                     "profit": round(prof, 4), "stake": round(stake, 4),
                     "contracts": contracts, "price": entry_px,
                     "hedged": hedge_stake > 0,
                     "ret_pct": round(100.0 * prof / stake, 4)})
    rows.sort(key=lambda r: r["close"])
    return rows, warn


def bank_series():
    """[(epoch, bank)] from the bot's own autosize records."""
    out = []
    for p in sorted(glob.glob(os.path.join(REPO, "results", "pinrun-live-*.jsonl"))):
        for line in open(p, encoding="utf-8", errors="ignore"):
            if '"autosize"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = re.search(r"bank \$([\d.]+)", d.get("why", ""))
            if m:
                t = dt.datetime.strptime(d["t"], "%Y-%m-%dT%H:%M:%SZ")
                out.append((int((t - dt.datetime(1970, 1, 1)).total_seconds()),
                            float(m.group(1))))
    out.sort()
    return out


def add_sigma(rows):
    """The index's own 1-second volatility over the 5 minutes before each close."""
    try:
        import idxload
        D = idxload.load(["BRTI"], verbose=False).get("BRTI")
    except Exception:                                        # noqa: BLE001
        return 0
    if D is None:
        return 0
    n = 0
    for r in rows:
        vals = [D.get(s) for s in range(r["close"] - 300, r["close"])]
        rr = [math.log(b / a) for a, b in zip(vals, vals[1:])
              if a and b and a > 0 and b > 0]
        if len(rr) > 200:
            m = sum(rr) / len(rr)
            r["sigma"] = math.sqrt(sum((x - m) ** 2 for x in rr) / (len(rr) - 1))
            n += 1
    return n


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    p, s = trade_money(100, 0.97, 0.21, True)
    ck(abs(s - 97.0) < 1e-9 and abs(p - (3.0 - 0.21)) < 1e-9,
       "100 contracts at 97c stake $97 and win $2.79 after the fee")
    ck(abs(100 * p / s - 2.88) < 0.01,
       "which is a %.2f%% return on the money at risk -- the number that "
       "compounds, and it is small BECAUSE the bet was nearly certain"
       % (100 * p / s))
    p2, s2 = trade_money(100, 0.97, 0.21, False)
    ck(abs(p2 - (-97.21)) < 1e-9,
       "and a loss costs the whole $97 plus the fee, not the 3c of upside")
    lab = ["a"] * 20 + ["b"] * 20
    vals = [1.0] * 39 + [-30.0]
    o, pp0 = bucket_p(lab, vals, 400, seed=2)
    ck(o is not None and pp0 > 0.2,
       "NULL: 39 small wins and ONE big loss split between two buckets is not "
       "a pattern (p %.2f) -- the loss has to land somewhere" % pp0)
    lab2 = ["a", "b"] * 20
    vals2 = [5.0 if i % 2 == 0 else -5.0 for i in range(40)]
    o2, pp2 = bucket_p(lab2, vals2, 400, seed=3)
    ck(pp2 < 0.02,
       "while a bucket that wins every time and one that loses every time is "
       "caught (p %.3f)" % pp2)
    ck(abs(p2 / p) > 34,
       "one loss undoes %.0f wins at that price" % abs(p2 / p))
    p3, _ = trade_money(100, 0.50, 0.0, True)
    ck(abs(p3 - 50.0) < 1e-9, "a coin flip at 50c doubles or dies")

    cs = close_of_ticker("KXBTC15M-26SEP151745-45")
    got = dt.datetime.fromtimestamp(cs, dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    ck(got == "2026-09-15 21:45Z",
       "a ticker's close reads as EASTERN: 26SEP15 17:45 ET = %s" % got)
    ck(close_of_ticker("rubbish") is None and close_of_ticker("KXBTC15M-bad-45") is None,
       "NULL: an unparseable ticker is refused, never guessed")

    xs = list(range(60))
    ck(abs(rank_corr(xs, xs) - 1.0) < 1e-9 and abs(rank_corr(xs, xs[::-1]) + 1.0) < 1e-9,
       "rank correlation is +1 with itself and -1 reversed")
    ck(rank_corr([1, 2], [1, 2]) is None, "NULL: two points is not a correlation")
    ck(rank_corr([1] * 30, list(range(30))) is None,
       "NULL: a column that never varies correlates with nothing")
    rng = random.Random(3)
    noise = [rng.random() for _ in range(200)]
    r, pp = corr_p(list(range(200)), noise, 400, seed=4)
    ck(pp > 0.05,
       "NULL: 200 random numbers show no trend (r %.2f, p %.2f)" % (r, pp))
    trend = [i + rng.random() * 40 for i in range(200)]
    r2, p2b = corr_p(list(range(200)), trend, 400, seed=5)
    ck(r2 > 0.8 and p2b < 0.01,
       "while a planted trend is found (r %.2f, p %.3f)" % (r2, p2b))
    print("pinvalue selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    rows, warn = load_trades()
    if len(rows) < 50:
        print("loaded nothing -- only %d settled markets with fills" % len(rows))
        return 0
    add_sigma(rows)
    with open(OUT_ROWS, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    total_profit = sum(r["profit"] for r in rows)
    total_stake = sum(r["stake"] for r in rows)
    lines = []
    w = lines.append
    w("# VALUE -- where the money actually comes from\n")
    w("`research/pinvalue.py`. %d markets bought, rebuilt from the fills "
      "themselves. Saved in `results/value_trades.jsonl`.\n" % len(rows))

    # ---- reconcile against the bank before believing anything ----------
    bank = bank_series()
    recon = ""
    if bank:
        lo = min(b for t, b in bank if t >= rows[0]["close"] - 3600) if bank else None
        first = [b for t, b in bank if t >= rows[0]["close"]]
        last = bank[-1][1]
        if first:
            moved = last - first[0]
            recon = ("Bank moved **$%+.2f** over the same window; the fills add "
                     "up to **$%+.2f**." % (moved, total_profit))
            if abs(moved) > 1 and abs(total_profit - moved) / abs(moved) > 0.15:
                recon += (" **These disagree by more than 15%, so read every "
                          "figure below as approximate** -- restarts orphan "
                          "some settlements and withdrawals move the bank.")
            else:
                recon += " They agree."
    w(recon + "\n")
    w("Total staked **$%.0f**, total profit **$%+.2f**, which is "
      "**%.2f%% on every dollar put at risk**.\n"
      % (total_stake, total_profit, 100 * total_profit / total_stake))
    if warn:
        w("(%d markets had fills but no settlement on file and were dropped.)\n"
          % len(warn))

    # ---- the decomposition ---------------------------------------------
    sig = [r for r in rows if r.get("sigma")]
    w("\n## The three things that make money\n")
    w("Money in an hour is *how often a bet appears* x *how big it is* x "
      "*what it returns*. Here is each, by how calm the market was:\n")
    if len(sig) >= 50:
        sig.sort(key=lambda r: r["sigma"])
        fifth = max(1, len(sig) // 5)
        names = ("calmest fifth", "2nd calmest", "middle fifth",
                 "2nd choppiest", "choppiest fifth")
        w("| market | buys | losses | avg price | avg contracts | "
          "return per $ staked | profit | profit per buy |")
        w("|---|---|---|---|---|---|---|---|")
        for i in range(5):
            part = sig[i * fifth:(i + 1) * fifth] if i < 4 else sig[4 * fifth:]
            if not part:
                continue
            pr = sum(r["profit"] for r in part)
            stk = sum(r["stake"] for r in part)
            w("| %s | %d | %d | %.1fc | %.0f | %.2f%% | $%+.2f | $%+.3f |"
              % (names[i], len(part), sum(1 for r in part if not r["won"]),
                 100 * sum(r["price"] for r in part) / len(part),
                 sum(r["contracts"] for r in part) / len(part),
                 100 * pr / stk, pr, pr / len(part)))
        w("")
        lo_r = sig[:fifth]
        hi_r = sig[4 * fifth:]
        vlab = [i if i < 4 else 4 for i, r in
                ((min(4, j // fifth), r) for j, r in enumerate(sig))]
        _, pv = bucket_p(vlab, [r["profit"] for r in sig])
        w("Spread in profit per buy across those fifths: p = %.3f against "
          "chance. **%d of the %d buys lost.** One loss at 95c undoes about "
          "thirty wins, so a fifth's average is mostly a record of where those "
          "losses landed -- which is why the column is not in order even though "
          "the COUNT of chances (pinwhen) is."
          % (pv, sum(1 for r in sig if not r["won"]), len(sig)))
        w("")
        w("Return per dollar, calmest **%.2f%%** against choppiest **%.2f%%**."
          % (100 * sum(r["profit"] for r in lo_r) / sum(r["stake"] for r in lo_r),
             100 * sum(r["profit"] for r in hi_r) / sum(r["stake"] for r in hi_r)))

    # ---- is the return correlated with anything? ------------------------
    w("\n## Is any of it predictable?\n")
    w("| pair | rank correlation | p (2,000 shuffles) | reading |")
    w("|---|---|---|---|")
    pairs = []
    if len(sig) >= 30:
        pairs.append(("how choppy vs return per $",
                      [r["sigma"] for r in sig], [r["ret_pct"] for r in sig]))
        pairs.append(("how choppy vs price paid",
                      [r["sigma"] for r in sig], [r["price"] for r in sig]))
    pairs.append(("price paid vs return per $",
                  [r["price"] for r in rows], [r["ret_pct"] for r in rows]))
    pairs.append(("contracts bought vs return per $",
                  [r["contracts"] for r in rows], [r["ret_pct"] for r in rows]))
    for name, xs, ys in pairs:
        r, p = corr_p(xs, ys)
        if r is None:
            continue
        rd = ("**real**" if p < 0.01 else ("maybe" if p < 0.05 else "chance"))
        if name.startswith("price paid"):
            rd = "ARITHMETIC, not a finding"
        w("| %s | %+.2f | %.3f | %s |" % (name, r, p, rd))
    w("")
    w("*Price against return is near -1 by construction: winning a contract "
      "bought at 90c returns 11%, one bought at 98c returns 2%. It says nothing "
      "about when to trade.*")

    # ---- money by hour of day, tested ------------------------------------
    w("\n## Money by hour of the day\n")
    per_hour = collections.defaultdict(lambda: [0.0, 0.0, 0])
    lost_in = collections.Counter()
    for r in rows:
        if not r["won"]:
            lost_in[dt.datetime.fromtimestamp(
                r["close"] + downtime.et_offset(r["close"]),
                dt.timezone.utc).hour // 4] += 1
        h = dt.datetime.fromtimestamp(r["close"] + downtime.et_offset(r["close"]),
                                      dt.timezone.utc).hour
        a = per_hour[h // 4]
        a[0] += r["profit"]
        a[1] += r["stake"]
        a[2] += 1
    w("| hours (ET) | buys | losses | staked | profit | return per $ |")
    w("|---|---|---|---|---|---|")
    for b in sorted(per_hour):
        pr, stk, n = per_hour[b]
        w("| %02d:00-%02d:00 | %d | %d | $%.0f | $%+.2f | %.2f%% |"
          % (b * 4, b * 4 + 4, n, lost_in[b], stk, pr,
             100 * pr / stk if stk else 0))
    hlab = [dt.datetime.fromtimestamp(r["close"] + downtime.et_offset(r["close"]),
                                      dt.timezone.utc).hour // 4 for r in rows]
    _, ph = bucket_p(hlab, [r["profit"] for r in rows])
    w("")
    w("Spread in profit per buy across those blocks: p = %.3f. %s"
      % (ph, "**That is beyond chance -- worth a second look as more days "
             "arrive.**" if ph < 0.05 else
             "That is what chance produces when a dozen losses fall somewhere "
             "in 391 buys, so there is nothing here to act on yet."))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\nwrote %s and %s" % (os.path.basename(OUT_MD), os.path.basename(OUT_ROWS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
