#!/usr/bin/env python3
# VERSION: 2026-09-12-pm1
"""pinmaker.py -- HOW TO BUY BETTER: cross the spread, or rest and wait?

THE QUESTION. The live bot is a TAKER. When the model's belief in one side
reaches PIN (99.5%) with tau <= TAU_MAX seconds left it hits the best ask and
pays the quadratic taker fee, ceil(0.07*n*p*(1-p)) to the next $0.0001. At the
prices it actually trades that fee is a large share of the edge: 84% of gate
fills sit in the 98-100c band, which pays +0.34c per contract against a fee of
~0.14c at 98c. MAKERS PAY NOTHING on these series (fee_type quadratic,
verified 2026-09-06 across 13,839 series). So: would resting a bid and waiting
for someone to sell to us beat crossing?

It is not a free lunch and the cost is obvious -- a resting bid that is never
hit buys nothing, and a close we do not trade earns zero. That trade-off is
exactly the shape that has fooled this project twice (the "wait for a 5-10c
discount" idea on 2026-09-11 and the "stop paying above 94c" idea on
2026-09-12): both looked wonderful PER CONTRACT and died PER CLOSE, because
rarity is invisible in a per-contract column. So the per-close column here is
the verdict and the per-contract column is decoration.

WHAT IS MEASURED, and from what

  The TRADE TAPE only (kalshi_data/trade/*.jsonl.gz) plus the 1/sec
  cfbenchmarks index that drives the model. Not the rebuilt order book. The
  book replay is structurally blind to offers that are dumped at us
  (AMENDMENT 2026-09-10); the trade tape is not, because every execution
  carries `taker_side`, which says who crossed. For a question of the form
  "would somebody have traded with an order resting HERE", the print is the
  evidence and the reconstructed book is not.

  At each market's FIRST second with belief >= PIN and TAU_MIN <= tau <=
  TAU_MAX -- the gate, computed by calling pinrun.fair() through pinrun's own
  IndexWS exactly as pinsim.decide does -- four purchase rules are priced:

    TAKE      buy at the best ask now, pay the taker fee.     (the current bot)
    REST-1    rest a bid one tick BELOW the best ask, R secs, no fee.
    REST-AT   rest a bid AT the best ask, R secs, no fee.
    REST-BID  rest a bid at the best BID, R secs, no fee.     (secondary)

  A resting bid at B FILLS when a print occurs on our side at or below B whose
  taker is on the OTHER side -- i.e. somebody actively sold our side into the
  book and reached our price. It fills AT B, because the exchange trades at the
  resting order's price. If no such print arrives within R seconds we buy
  nothing and the close is scored ZERO, which is the whole cost of patience.

HOW THE QUOTES ARE INFERRED, and why this is not circular
  A print with taker_side == our side was somebody LIFTING the ask on our
  side, so its price IS the ask. A print with taker_side == the other side was
  somebody HITTING the bid on our side, so its our-side price IS the bid. Both
  are read strictly backwards in time from the gate second, never forward.

REST-AT IS NOT PHYSICALLY A MAKER ORDER AND THE REPORT SAYS SO.
  A bid placed at the current ask is marketable: it crosses immediately and
  bills the taker fee. REST-AT is priced here anyway, with zero fee, because
  it is the arithmetic ceiling on "what if resting never cost us a worse
  price". Read it as an upper bound that cannot be traded, not as a rule.

WHAT THIS CANNOT TELL US, stated before any number

  * WHETHER THE FILL WOULD BE OURS. Every fill here assumes we are at the
    front of the queue at our price. We are not: at the touch we join a queue
    whose length we cannot see from prints, and the deeper the queue the more
    of these fills belong to somebody else. Live, the TAKER path fills 70% of
    the attempts it makes; the maker path has no measured analogue at all.
    Three fill definitions are reported -- optimistic (any print at or below
    our price), size-aware (enough contracts at or below our price to fill 20)
    and queue-pessimistic (only prints strictly THROUGH our price, i.e. the
    level was cleared) -- and the truth lies inside that bracket.
  * OUR LOSS RATE. The loss rates below are the TAPE's, on other people's
    fills, and per the standing house rule they are quoted for RANKING the
    rules against each other and for NOTHING else. Live loss rates come from
    live fills, full stop.
  * DEPTH AT THE ASK. TAKE is priced as a full fill of SIZE at the inferred
    ask. The trade tape cannot see resting depth.

SELF-TEST. Plants a world where a resting bid fills at a known rate and checks
the estimator recovers that rate; plants a world built by arithmetic so that
resting and taking are EXACTLY equal per close and checks the estimator finds
no advantage; plants one where resting is better by a known amount and checks
it finds exactly that amount. Also checks the side mapping in both directions,
that a same-side print can never fill our bid, and that nothing before our
placement instant can fill us.
"""
import argparse
import bisect
import calendar
import glob
import gzip
import json
import math
import os
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                  # noqa: E402
import pindata                                                 # noqa: E402
from pinsim import TapeIndex, load_ticks                       # noqa: E402
from pincross import cp_interval                               # noqa: E402
from engine import tick_at                                     # noqa: E402

DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
REPORT = r"C:\kals-repo\results\RESULTS_maker.md"

SIZE = 20.0                # contracts, the operator's live size
REST_SECS = (2, 5, 10)     # R: seconds we are willing to leave a bid resting
MAX_QUOTE_AGE = 60         # a print older than this does not define a quote
RULES = ("TAKE", "REST-1", "REST-AT", "REST-BID")
MODES = ("opt", "size", "pess")
MDE_K = 2.8016             # z(0.975) + z(0.80): 80% power at alpha 0.05


# --------------------------------------------------------------- arithmetic
def billed_fee(price, count):
    """Kalshi's actual charge: the raw quadratic ceilinged to $0.0001."""
    return math.ceil(0.07 * float(count) * price * (1 - price) * 10000.0
                     - 1e-9) / 10000.0


def one_tick_below(p):
    """The next price DOWN on the tapered grid (0.1c outside 10-90c, else 1c)."""
    return round(p - tick_at(p), 4)


def gross_pnl(price, won, count):
    return count * ((1.0 - price) if won else -price)


def gate_side(f):
    """pinrun's own gate, in one place so the self-test can reach it."""
    if f is None:
        return None, None
    if f >= pinrun.PIN:
        return "yes", f
    if f <= 1.0 - pinrun.PIN:
        return "no", 1.0 - f
    return None, None


def scan_close(close_s, tickers, step):
    """Every GATED second per ticker, walking tau DOWN from TAU_MAX so that
    time runs forward. `step(sec)` returns {ticker: fair or None} and is the
    only thing that touches the index, so the self-test can stub it.

    The whole sequence is returned, not just the first second, because the
    two entry definitions below need different members of it and neither may
    look at a second that has not happened yet.
    """
    out = {tk: [] for tk in tickers}
    for tau in range(pinrun.TAU_MAX, pinrun.TAU_MIN - 1, -1):
        fs = step(close_s - tau)
        for tk in tickers:
            f = fs.get(tk)
            if f is not None:
                out[tk].append((close_s - tau, tau, f))
    return out


# ------------------------------------------------------- quotes from prints
def infer_quotes(want, ts, sd, px, t0_end_ms, lo_ms):
    """(ask, ask_ms, bid, bid_ms) on OUR side, read strictly backwards.

    sd[i] is True when the taker bought YES. A taker on OUR side lifted our
    ask; a taker on the OTHER side hit our bid. px[i] is always the YES price.
    """
    ask = ask_ms = bid = bid_ms = None
    i = bisect.bisect_right(ts, t0_end_ms) - 1
    want_yes = (want == "yes")
    while i >= 0 and ts[i] >= lo_ms:
        ours = px[i] if want_yes else 1.0 - px[i]
        if sd[i] == want_yes:
            if ask is None:
                ask, ask_ms = ours, ts[i]
        elif bid is None:
            bid, bid_ms = ours, ts[i]
        if ask is not None and bid is not None:
            break
        i -= 1
    return ask, ask_ms, bid, bid_ms


def rest_fill(bid, want, ts, sd, px, ct, place_ms, end_ms, mode, need=SIZE):
    """ms of the print that fills a bid resting at `bid`, or None.

    OUR SIDE IS SOLD TO US: the filling print must have its taker on the OTHER
    side. A print whose taker is on our side is somebody BUYING what we are
    trying to buy and can never fill our bid.
      opt   any print at or below our price          (front of the queue)
      size  enough contracts at or below our price to fill `need`
      pess  only a print strictly THROUGH our price  (the level was cleared)
    """
    want_yes = (want == "yes")
    i = bisect.bisect_left(ts, place_ms)
    acc = 0.0
    n = len(ts)
    while i < n and ts[i] <= end_ms:
        if sd[i] != want_yes:
            ours = px[i] if want_yes else 1.0 - px[i]
            if mode == "pess":
                if ours < bid - 1e-9:
                    return ts[i]
            elif ours <= bid + 1e-9:
                if mode == "size":
                    acc += ct[i]
                    if acc >= need - 1e-9:
                        return ts[i]
                else:
                    return ts[i]
        i += 1
    return None


def first_gate(seq):
    """ENTRY A -- the first second the gate fires, whatever the offer is.
    This is the definition the operator asked for."""
    for sec, tau, f in seq:
        w, c = gate_side(f)
        if w:
            return sec, tau, w, c
    return None


def pull_ms(seq, sec0, want, thresh):
    """When a maker WATCHING ITS OWN MODEL would have its bid out of the book.

    The obvious defence of a resting rule is "we would cancel when the belief
    turns". This grants that defence a full second of reaction: the alarm is
    the first second AFTER entry at which belief in our side falls below
    `thresh`, and the order is treated as gone from the start of the NEXT
    second. Returns None when the belief never turns inside the window.

    THE WINDOW ONLY REACHES TAU_MIN, so a fill inside the last TAU_MIN seconds
    can never be cancelled by this test. That makes the cancelled numbers
    generous in one direction (no alarm is missed for lack of data) and
    ungenerous in another (the last few seconds are uncancellable), and both
    are stated rather than corrected.
    """
    for sec, tau, f in seq:
        if sec <= sec0:
            continue
        conf = f if want == "yes" else 1.0 - f
        if conf < thresh:
            return (sec + 1) * 1000
    return None


def best_in_second(want, ts, sd, px, sec):
    """(best price, its ms) among SAME-SIDE taker prints inside `sec`.

    A same-side print is somebody lifting an offer on our side, so its price
    is an offer that demonstrably existed in that second. The MINIMUM of them
    is the touch -- the best offer that was actually available.
    """
    lo, hi = sec * 1000, sec * 1000 + 999
    i = bisect.bisect_left(ts, lo)
    want_yes = (want == "yes")
    best = bms = None
    while i < len(ts) and ts[i] <= hi:
        if sd[i] == want_yes:
            ours = px[i] if want_yes else 1.0 - px[i]
            if best is None or ours < best:
                best, bms = ours, ts[i]
        i += 1
    return best, bms


def first_tradeable(seq, best_at, ceiling):
    """ENTRY B -- the first GATED second in which an offer at or below the
    live price ceiling DEMONSTRABLY traded on our side.

    This, not entry A, is the bot's entry. The bot re-reads the book every
    ~50 ms across the whole tau window and buys the first acceptable offer; a
    single snapshot at the first gated second catches it seconds before any
    acceptable offer exists. Strictly forward in time, and never earlier than
    entry A.
    """
    for sec, tau, f in seq:
        want, conf = gate_side(f)
        if want is None:
            continue
        ask, ms = best_at(sec, want)
        if ask is not None and ask <= ceiling + 1e-9:
            return sec, tau, want, conf, ask, ms
    return None


def price_rules(ask, bid):
    """The bid each rule would post, given the inferred quotes."""
    out = {"TAKE": ask, "REST-1": one_tick_below(ask), "REST-AT": ask}
    out["REST-BID"] = (min(bid, one_tick_below(ask)) if bid is not None
                       else None)
    return out


# ------------------------------------------------------------- aggregation
def per_close(entries, value):
    """One number per CLOSE -- the mean over that close's entries of `value`,
    in dollars at SIZE. A close whose entries all missed contributes 0, not a
    gap: refusing to trade is a result, and the denominator is closes."""
    byc = defaultdict(list)
    for e in entries:
        byc[e["close"]].append(value(e))
    return {c: sum(v) / len(v) for c, v in byc.items()}


def stats(xs):
    n = len(xs)
    if n < 2:
        return dict(n=n, mean=float("nan"), sd=float("nan"),
                    se=float("nan"), t=float("nan"), mde=float("nan"))
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    se = sd / math.sqrt(n)
    return dict(n=n, mean=m, sd=sd, se=se,
                t=(m / se if se > 0 else float("nan")), mde=MDE_K * se)


def paired(a, b):
    """Per-close difference a-b over the closes both saw."""
    ks = sorted(set(a) & set(b))
    return [a[k] - b[k] for k in ks]


def outcome(e, rule, R, mode):
    return e["fill"].get((rule, R, mode))


def filled(e, rule, R, mode, cancel=None):
    """Did this rule buy? With `cancel`, only a fill that lands BEFORE the
    bid would have been pulled counts."""
    fm = outcome(e, rule, R, mode)
    if fm is None:
        return False
    if cancel is not None:
        pm = e.get("pull", {}).get(cancel)
        if pm is not None and fm >= pm:
            return False
    return True


def rule_dollars(e, rule, R, mode, cancel=None):
    """Dollars at SIZE for one entry under one rule. A miss is exactly 0."""
    if rule == "TAKE":
        p = e["rules"]["TAKE"]
        if p is None:
            return 0.0
        return gross_pnl(p, e["won"], SIZE) - billed_fee(p, SIZE)
    p = e["rules"][rule]
    if p is None or not filled(e, rule, R, mode, cancel):
        return 0.0
    return gross_pnl(p, e["won"], SIZE)          # makers pay no fee


# ------------------------------------------------------------------ reading
def load_markets():
    mk = {}
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in pindata.SERIES_TO_INDEX and \
                    r.get("result") is not None:
                mk[r["ticker"]] = r
    return mk


def won_side(r, want):
    res = r["result"]
    yes = (str(res).lower() == "yes") if isinstance(res, str) \
        else float(res) >= 0.5
    return yes == (want == "yes")


def read_trades(fp, closes_of, lo_tau, hi_tau, counters):
    """Prints for the tracked tickers inside the tau band, as parallel arrays.

    Block trades are excluded: they are negotiated away from the book and can
    neither define a touch nor fill a resting order.
    """
    raw = defaultdict(list)
    try:
        with gzip.open(fp, "rt") as fh:
            for line in fh:
                if '"trade"' not in line or '15M' not in line:
                    continue
                try:
                    m = json.loads(line)["msg"]
                except Exception:
                    counters["unparseable"] += 1
                    continue
                tk = m.get("market_ticker")
                cs = closes_of.get(tk)
                if cs is None:
                    continue
                if m.get("is_block_trade"):
                    counters["block"] += 1
                    continue
                ts = int(m.get("ts_ms") or 0)
                if not ts:
                    counters["no_ts_ms"] += 1
                    continue
                tau = cs - ts // 1000
                if not (lo_tau <= tau <= hi_tau):
                    continue
                side = m.get("taker_side")
                if side not in ("yes", "no"):
                    counters["no_taker_side"] += 1
                    continue
                try:
                    y = float(m["yes_price_dollars"])
                    n = float(m.get("count_fp") or m.get("count") or 0)
                except Exception:
                    counters["bad_price"] += 1
                    continue
                if n <= 0 or not (0.0 < y < 1.0):
                    continue
                raw[tk].append((ts, side == "yes", y, n))
    except (EOFError, zlib.error, OSError):
        counters["truncated_gz"] += 1
    out = {}
    for tk, rows in raw.items():
        rows.sort(key=lambda r: r[0])
        out[tk] = ([r[0] for r in rows], [r[1] for r in rows],
                   [r[2] for r in rows], [r[3] for r in rows])
    return out


# --------------------------------------------------------------- the driver
CANCEL_AT = (0.90, 0.70)   # belief thresholds a watching maker would pull on


def build_entry(tk, info, c, sec, tau, want, conf, arr, counters, pre="",
                ask_override=None, seq=()):
    """One priced decision: the quotes at `sec`, and for every (rule, R, mode)
    whether a resting bid at that rule's price would have been filled."""
    ts, sd, px, ct = arr
    ask, ask_ms, bid, bid_ms = infer_quotes(
        want, ts, sd, px, (sec + 1) * 1000 - 1, (sec - MAX_QUOTE_AGE) * 1000)
    if ask_override is not None:
        ask, ask_ms = ask_override
    if ask is None:
        counters[pre + "drop_no_ask"] += 1
        return None
    if bid is None:
        counters[pre + "no_bid_inferable"] += 1
    qms = max(x for x in (ask_ms, bid_ms) if x is not None)
    place_ms = max(sec * 1000, qms + 1)
    rules = price_rules(ask, bid)
    e = {"ticker": tk, "close": c, "sec": sec, "tau": tau, "want": want,
         "conf": conf, "ask": ask, "bid": bid, "ask_age": sec - ask_ms // 1000,
         "series": info["series"], "won": won_side(info, want),
         "rules": rules, "fill": {},
         "pull": {t: pull_ms(seq, sec, want, t) for t in CANCEL_AT}}
    for rule in ("REST-1", "REST-AT", "REST-BID"):
        b = rules[rule]
        if b is None or b <= 0:
            continue
        for R in REST_SECS:
            end = min(place_ms + R * 1000, c * 1000)
            for mode in MODES:
                e["fill"][(rule, R, mode)] = rest_fill(
                    b, want, ts, sd, px, ct, place_ms, end, mode)
    return e


def run_hour(stamp, mk, entries, entries_b, sweep, counters):
    hstart = calendar.timegm(time.strptime(stamp, "%Y%m%dT%H"))
    # closes whose ENTIRE gate window [close-TAU_MAX, close-TAU_MIN] and fill
    # window (to `close`) lie inside this hour's trade file.
    closes = [hstart + s for s in (900, 1800, 2700, 3600)]
    byclose = defaultdict(list)
    closes_of = {}
    for c in closes:
        for tk, r in mk.items():
            if int(float(r["close"])) == c:
                byclose[c].append(r)
                closes_of[tk] = c
    if not closes_of:
        return
    ticks = load_ticks(hstart - 400, hstart + 3700)
    if not ticks:
        counters["no_ticks_hour"] += 1
        return
    idx = TapeIndex(sorted(ticks))
    pend = {k: list(v) for k, v in ticks.items()}
    tr = read_trades(os.path.join(DATA, "trade", stamp + ".jsonl.gz"),
                     closes_of, 0, pinrun.TAU_MAX + MAX_QUOTE_AGE, counters)

    for c in sorted(byclose):
        rs = byclose[c]
        tks = [r["ticker"] for r in rs]
        info = {r["ticker"]: r for r in rs}

        sig = {}

        def step(sec, _rs=rs):
            idx.now = sec
            idx.feed_upto(pend, sec)
            out = {}
            for r in _rs:
                iid = pindata.SERIES_TO_INDEX[r["series"]]
                if iid not in idx.ticks:
                    continue
                if sig.get("sec") != sec:     # sigma copies a 300 s dict
                    sig.clear()
                    sig["sec"] = sec
                if iid not in sig:
                    sig[iid] = idx.sigma(iid)
                sg = sig[iid]
                if sg is None:
                    counters["no_sigma"] += 1
                    continue
                out[r["ticker"]] = pinrun.fair(
                    idx, iid, c, sec, float(r["strike"]),
                    sg * pinrun.SIGMA_STRESS,
                    round_digits=pindata.ROUND_DIGITS.get(r["series"]))
            return out

        gated = scan_close(c, tks, step)
        for tk, seq in gated.items():
            counters["markets"] += 1
            if not seq:
                counters["no_model"] += 1
                continue
            g = first_gate(seq)
            if g is None:
                counters["never_gated"] += 1
                continue
            counters["gate"] += 1
            arr = tr.get(tk)
            if arr is None:
                counters["drop_no_prints"] += 1
                continue
            ts, sd, px, ct = arr
            e = build_entry(tk, info[tk], c, g[0], g[1], g[2], g[3], arr,
                            counters, "A_", seq=seq)
            if e is not None:
                entries.append(e)
            b = first_tradeable(
                seq, lambda s, w, _a=(ts, sd, px): best_in_second(
                    w, _a[0], _a[1], _a[2], s), pinrun.PRICE_CEILING)
            if b is None:
                counters["B_never_tradeable"] += 1
            else:
                eb = build_entry(tk, info[tk], c, b[0], b[1], b[2], b[3], arr,
                                 counters, "B_",
                                 ask_override=(b[4], b[5]), seq=seq)
                if eb is not None:
                    entries_b.append(eb)
            if e is None:
                continue

            # touch vs sweep, among takers buying OUR side inside the gate
            # window on this market: group by the true instant (ts_ms).
            groups = defaultdict(list)
            lo = (c - pinrun.TAU_MAX) * 1000
            hi = (c - pinrun.TAU_MIN) * 1000 + 999
            i = bisect.bisect_left(ts, lo)
            want_yes = (e["want"] == "yes")
            while i < len(ts) and ts[i] <= hi:
                if sd[i] == want_yes:
                    groups[ts[i]].append(
                        (px[i] if want_yes else 1.0 - px[i], ct[i]))
                i += 1
            for g in groups.values():
                best = min(p for p, _ in g)
                tot = sum(n for _, n in g)
                at = sum(n for p, n in g if p <= best + 1e-9)
                sweep["groups"] += 1
                sweep["legs"] += len(g)
                sweep["contracts"] += tot
                sweep["at_touch_contracts"] += at
                sweep["levels"] += len({round(p, 4) for p, _ in g})
                if len({round(p, 4) for p, _ in g}) == 1:
                    sweep["single_level_groups"] += 1
                sweep.setdefault("legs_hist", []).append(len(g))


# ------------------------------------------------------------------ report
def fmt_block(entries, R, mode, out):
    closes = sorted({e["close"] for e in entries})
    pc = {r: per_close(entries, lambda e, r=r: rule_dollars(e, r, R, mode))
          for r in RULES}
    take = pc["TAKE"]

    out(f"\n### R = {R}s, fill rule `{mode}`  "
        f"({len(entries):,} entries over {len(closes):,} closes)\n")
    out("| rule | entries | fills | fill rate | mean price paid | "
        "loss rate on filled (TAPE) | 95% CI | P&L/contract | "
        "**$/close at 20** | t | vs TAKE $/close | t(diff) |")
    out("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in RULES:
        sub = [e for e in entries if e["rules"][r] is not None]
        if r == "TAKE":
            fl = sub
        else:
            fl = [e for e in sub if filled(e, r, R, mode)]
        nf = len(fl)
        mp = (sum(e["rules"][r] for e in fl) / nf) if nf else float("nan")
        lost = sum(1 for e in fl if not e["won"])
        a_, b_ = cp_interval(lost, nf) if nf else (float("nan"),) * 2
        ctr = sum((gross_pnl(e["rules"][r], e["won"], SIZE)
                   - (billed_fee(e["rules"][r], SIZE) if r == "TAKE" else 0.0))
                  for e in fl)
        pcc = ctr / (nf * SIZE) if nf else float("nan")
        s = stats([pc[r][c] for c in closes])
        d = stats(paired(pc[r], take)) if r != "TAKE" else None
        out(f"| {r} | {len(sub):,} | {nf:,} | {100*nf/max(1,len(sub)):.1f}% | "
            f"{100*mp:.2f}c | {100*lost/max(1,nf):.2f}% | "
            f"[{100*a_:.2f}, {100*b_:.2f}] | {100*pcc:+.2f}c | "
            f"**${s['mean']:+.4f}** | {s['t']:+.2f} | "
            + (f"${d['mean']:+.4f} | {d['t']:+.2f} |" if d else "— | — |"))
    return pc


def mde_block(entries, mode, out):
    closes = sorted({e["close"] for e in entries})
    out(f"\n**MDE, stated before the estimates** (`{mode}`, "
        f"n={len(closes):,} closes, 80% power at alpha 0.05, paired per "
        f"close). Below this line, 'no advantage' means 'no power', not "
        f"'no effect':\n")
    out("| comparison | R | sd of per-close difference | MDE ($/close at 20) |")
    out("|---|---|---|---|")
    for R in REST_SECS:
        pc = {r: per_close(entries, lambda e, r=r: rule_dollars(e, r, R, mode))
              for r in RULES}
        for r in ("REST-1", "REST-AT", "REST-BID"):
            d = stats(paired(pc[r], pc["TAKE"]))
            out(f"| {r} - TAKE | {R}s | ${d['sd']:.4f} | "
                f"**${d['mde']:.4f}** |")


def adverse_block(entries, mode, out):
    """THE DECISIVE DIAGNOSTIC. A resting bid is filled by somebody choosing
    to sell to us. If that choice carries information, the bid fills more
    often on the markets that go on to LOSE than on the ones that win -- and
    the ratio of those two fill rates is adverse selection measured directly,
    with no price or fee in it."""
    win = [e for e in entries if e["won"]]
    los = [e for e in entries if not e["won"]]
    out(f"\n**Adverse selection: who fills us?** {len(win):,} entries went on "
        f"to WIN, {len(los):,} went on to LOSE. If resting were harmless the "
        f"two fill rates would match.\n")
    out("| rule | R | fill rate on WINNERS | fill rate on LOSERS | "
        "loser fills / winner fills |")
    out("|---|---|---|---|---|")
    for r in ("REST-1", "REST-AT", "REST-BID"):
        for R in REST_SECS:
            w = [e for e in win if e["rules"][r] is not None]
            l = [e for e in los if e["rules"][r] is not None]
            fw = sum(1 for e in w if filled(e, r, R, mode))
            fl = sum(1 for e in l if filled(e, r, R, mode))
            rw = fw / max(1, len(w))
            rl = fl / max(1, len(l))
            out(f"| {r} | {R}s | {100*rw:.1f}% ({fw:,}/{len(w):,}) | "
                f"{100*rl:.1f}% ({fl:,}/{len(l):,}) | "
                f"**{(rl/rw if rw else float('nan')):.2f}x** |")


def cancel_block(entries, mode, out):
    """THE OBVIOUS DEFENCE, TESTED. 'A resting bid only loses because you hold
    it into a collapse -- so cancel when the model turns.' Here is that rule,
    with a full second of reaction time, against the same TAKE baseline."""
    closes = sorted({e["close"] for e in entries})
    los = [e for e in entries if not e["won"]]
    out(f"\n**Cancel on alarm** (`{mode}`): pull the bid at the first second "
        f"AFTER entry at which belief in our side falls below the threshold, "
        f"effective one second later.\n")
    for t in CANCEL_AT:
        al = [e for e in entries if e.get("pull", {}).get(t) is not None]
        alag = sorted((e["pull"][t] // 1000 - e["sec"]) for e in al)
        out(f"* belief fell below {100*t:.0f}% after entry on "
            f"**{len(al):,} of {len(entries):,}** entries "
            f"({100*len(al)/max(1,len(entries)):.1f}%), "
            f"{sum(1 for e in al if not e['won']):,} of them on the "
            f"{len(los):,} that lost"
            + (f"; median {alag[len(alag)//2]}s after entry." if alag else "."))
    out("")
    out("| rule | R | cancel below | fills | fills on LOSERS | $/close at 20 | "
        "t | vs TAKE | t(diff) |")
    out("|---|---|---|---|---|---|---|---|---|")
    for r in ("REST-1", "REST-BID"):
        for R in REST_SECS:
            pt = per_close(entries,
                           lambda e, R=R: rule_dollars(e, "TAKE", R, mode))
            for cx in (None,) + CANCEL_AT:
                sub = [e for e in entries if e["rules"][r] is not None]
                nf = sum(1 for e in sub if filled(e, r, R, mode, cx))
                nl = sum(1 for e in los
                         if e["rules"][r] is not None
                         and filled(e, r, R, mode, cx))
                pc = per_close(entries,
                               lambda e, r=r, cx=cx, R=R: rule_dollars(
                                   e, r, R, mode, cx))
                s = stats([pc[c] for c in closes])
                d = stats(paired(pc, pt))
                out(f"| {r} | {R}s | "
                    f"{'never' if cx is None else f'{100*cx:.0f}%'} | "
                    f"{nf:,} | {nl:,} of {len(los):,} | ${s['mean']:+.4f} | "
                    f"{s['t']:+.2f} | ${d['mean']:+.4f} | {d['t']:+.2f} |")


def guarded(entries, R, mode, out):
    """The same comparison with the LIVE guards applied per rule to the price
    that rule would pay: PRICE_CEILING and the DUMP_DISCOUNT refusal. A refused
    entry is not a trade, so it scores zero like a miss."""
    def g(e, r):
        p = e["rules"][r]
        if p is None:
            return False
        return p <= pinrun.PRICE_CEILING + 1e-9 and \
            (e["conf"] - p) < pinrun.DUMP_DISCOUNT
    closes = sorted({e["close"] for e in entries})
    out(f"\n### With the live guards on (ceiling {100*pinrun.PRICE_CEILING:.1f}c, "
        f"refuse a discount >= {100*pinrun.DUMP_DISCOUNT:.0f}c), R={R}s, `{mode}`\n")
    out("| rule | entries allowed | fills | $/close at 20 | t | vs TAKE | t(diff) |")
    out("|---|---|---|---|---|---|---|")
    pc = {}
    for r in RULES:
        pc[r] = per_close(
            entries,
            lambda e, r=r: (rule_dollars(e, r, R, mode) if g(e, r) else 0.0))
    for r in RULES:
        allow = [e for e in entries if g(e, r)]
        fl = allow if r == "TAKE" else [e for e in allow
                                        if filled(e, r, R, mode)]
        s = stats([pc[r][c] for c in closes])
        d = stats(paired(pc[r], pc["TAKE"])) if r != "TAKE" else None
        out(f"| {r} | {len(allow):,} | {len(fl):,} | ${s['mean']:+.4f} | "
            f"{s['t']:+.2f} | "
            + (f"${d['mean']:+.4f} | {d['t']:+.2f} |" if d else "— | — |"))


def sample_note(entries, label, out):
    closes = sorted({e["close"] for e in entries})
    ds = sorted({time.strftime("%Y-%m-%d", time.gmtime(c)) for c in closes})
    med = sorted(e["ask_age"] for e in entries)
    tau = sorted(e["tau"] for e in entries)
    pr = sorted(e["ask"] for e in entries)
    out(f"* **{label}**: {len(entries):,} entries, {len(closes):,} closes, "
        f"{len(ds)} UTC days ({ds[0]} .. {ds[-1]}); median tau at entry "
        f"{tau[len(tau)//2]}s; median inferred ask "
        f"{100*pr[len(pr)//2]:.1f}c (90th pct {100*pr[int(0.9*len(pr))]:.1f}c); "
        f"median ask age {med[len(med)//2]:.0f}s; a bid was inferable for "
        f"{100*sum(1 for e in entries if e['bid'] is not None)/len(entries):.1f}%.")


def split_days(entries, hold_days=4):
    """FIT / HOLDOUT, split on the CLOSE CLOCK and not on day labels.

    The tape does not start on a midnight, so splitting on calendar labels
    gives a partial day at each end and a 5/6 split when 5/4 was asked for.
    The boundary here is `last close - hold_days`, so the holdout is exactly
    the last four days and everything earlier is the fit. The split is a
    function of the window only -- no number from the estimator touches it.
    """
    cs = sorted({e["close"] for e in entries})
    cut = cs[-1] - hold_days * 86400
    fit = [e for e in entries if e["close"] < cut]
    hold = [e for e in entries if e["close"] >= cut]

    def span(es):
        if not es:
            return "-", "-"
        k = sorted(e["close"] for e in es)
        return (time.strftime("%Y-%m-%d %H:%MZ", time.gmtime(k[0])),
                time.strftime("%Y-%m-%d %H:%MZ", time.gmtime(k[-1])))
    ds = sorted({time.strftime("%Y-%m-%d", time.gmtime(c)) for c in cs})
    return ds, fit, span(fit), hold, span(hold)


def report(entries, entries_b, sweep, counters, out):
    out("")
    out("## Sample")
    out("")
    out(f"* gate: the first second with belief >= {100*pinrun.PIN:.1f}% and "
        f"{pinrun.TAU_MIN} <= tau <= {pinrun.TAU_MAX}s, computed by calling "
        f"`pinrun.fair()` through `pinsim.TapeIndex` -- the live model itself, "
        f"not a copy of it.")
    out(f"* size {SIZE:.0f} contracts. Taker fee "
        f"`ceil(0.07*n*p*(1-p), $0.0001)`; maker fee zero "
        f"(`fee_type quadratic`, verified per series).")
    sample_note(entries, "ENTRY A -- first gated second (the question as asked)",
                out)
    if entries_b:
        sample_note(entries_b, f"ENTRY B -- first gated second whose ask is at "
                    f"or below the live ceiling "
                    f"{100*pinrun.PRICE_CEILING:.1f}c (what the bot does)", out)
    out(f"* counters: `{dict(counters)}`")
    out("")
    out("**Both entry sets are reported because entry A is not the live bot.** "
        "The bot re-reads the book every ~50 ms and buys the FIRST acceptable "
        "offer, so a single snapshot at the first gated second catches it "
        "before any acceptable offer exists: entry A's median ask sits above "
        "the live 98c ceiling, which the bot would refuse outright. Entry A "
        "answers the question exactly as posed; entry B is the one whose "
        "absolute level means anything.")

    for tag, es in (("ENTRY A (first gated second)", entries),
                    ("ENTRY B (first tradeable second, ask <= ceiling)",
                     entries_b)):
        if len(es) < 30:
            continue
        ds, fit, fd, hold, hd = split_days(es)
        out("")
        out("---")
        out("")
        out(f"# {tag}")
        out("")
        blocks = [(f"ALL — {len(ds)} UTC day labels, {ds[0]} .. {ds[-1]}", es)]
        if fit:
            blocks.append((f"FIT — everything before the cut ({fd[0]} .. "
                           f"{fd[1]})", fit))
        if hold:
            blocks.append((f"HOLDOUT — the last 4 days ({hd[0]} .. {hd[1]})",
                           hold))
        for name, sub in blocks:
            if len(sub) < 2:
                continue
            out("")
            out(f"## {name}")
            out("")
            mde_block(sub, "opt", out)
            for R in REST_SECS:
                fmt_block(sub, R, "opt", out)
            adverse_block(sub, "opt", out)
            cancel_block(sub, "opt", out)
        out("")
        out(f"## Fill-definition sensitivity ({tag}, R=5s)")
        out("")
        out("The three definitions bracket queue position, which prints "
            "cannot see: `opt` assumes we are at the front of the queue, "
            "`size` needs enough contracts through our price to fill "
            f"{SIZE:.0f}, `pess` needs the level cleared outright.")
        for mode in MODES:
            fmt_block(es, 5, mode, out)
        out("")
        out(f"## The live guards ({tag})")
        out("")
        guarded(es, 5, "opt", out)

    out("")
    out("---")
    out("")
    out("# Touch versus sweep at our gate")
    out("")
    g = int(sweep["groups"])
    if g:
        lh = sorted(sweep["legs_hist"])
        ctr = sweep["contracts"]
        out(f"* **{g:,} taker groups** (same ticker, same `ts_ms` -- the true "
            f"instant, per CLAUDE.md) buying the near-certain side inside "
            f"{pinrun.TAU_MIN}-{pinrun.TAU_MAX}s of close on the markets we "
            f"entered, {ctr:,.0f} contracts in all.")
        out(f"* **{100*sweep['single_level_groups']/g:.1f}% of groups trade at "
            f"ONE price level** -- they take the touch and stop.")
        out(f"* **{100*sweep['at_touch_contracts']/max(1e-9, ctr):.1f}% of all "
            f"contracts** transact at the group's best (touch) level; the "
            f"remaining {100*(1-sweep['at_touch_contracts']/max(1e-9, ctr)):.1f}% "
            f"are swept deeper.")
        out(f"* legs per group: mean {sweep['legs']/g:.2f}, median "
            f"{lh[len(lh)//2]}, max {lh[-1]}; price levels per group mean "
            f"{sweep['levels']/g:.2f}.")
        out("")
        out("**THE CAVEAT THIS PRODUCES, and it stands whichever way the "
            "number fell.** The level a resting bid would sit at is the level "
            "most takers hit first, so we would be joining a queue at that "
            "level behind resting size that prints cannot see. Every `opt` "
            "fill rate above therefore OVERSTATES what we would actually "
            "receive; `pess` is the floor. Nothing in the trade tape can "
            "close that gap -- only resting a real order can.")


# ---------------------------------------------------------------- self-test
def _synth(n_closes, fill_frac, take_px, rest_px, won=True, seed=7):
    """A world with one entry per close: a TAKE at `take_px` that always
    fills, and a resting bid at `rest_px` that fills on exactly the first
    `fill_frac` fraction of closes."""
    import random
    rnd = random.Random(seed)
    es = []
    for i in range(n_closes):
        c = 1700000000 + 900 * i
        fills = (i < int(round(fill_frac * n_closes)))
        e = {"ticker": f"T{i}", "close": c, "sec": c - 20, "tau": 20,
             "want": "yes", "conf": 0.999, "ask": take_px, "bid": rest_px,
             "ask_age": 0, "series": "KXBTC15M", "won": won,
             "rules": {"TAKE": take_px, "REST-1": rest_px,
                       "REST-AT": take_px, "REST-BID": rest_px},
             "fill": {}}
        e["pull"] = {t: None for t in CANCEL_AT}
        for r in ("REST-1", "REST-AT", "REST-BID"):
            for R in REST_SECS:
                for m in MODES:
                    e["fill"][(r, R, m)] = (c * 1000 if fills else None)
        es.append(e)
    rnd.shuffle(es)
    return es


def selftest():
    print("SELF-TEST -- pinmaker")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # --- arithmetic the whole file rests on -------------------------------
    ck(abs(billed_fee(0.16, 12.37) - 0.1164) < 1e-9,
       "the taker fee reproduces the account's own reconciled charge")
    ck(abs(one_tick_below(0.98) - 0.979) < 1e-9,
       "one tick below 98c is 97.9c (0.1c grid above 90c)")
    ck(abs(one_tick_below(0.50) - 0.49) < 1e-9,
       "one tick below 50c is 49c (1c grid in the middle)")
    ck(abs(gross_pnl(0.96, True, 20) - 0.80) < 1e-9,
       "a winning 96c buy of 20 pays $0.80 gross")
    ck(abs(gross_pnl(0.96, False, 20) + 19.20) < 1e-9,
       "and a losing one costs $19.20")

    # --- the gate ---------------------------------------------------------
    ck(gate_side(0.9951)[0] == "yes" and gate_side(0.0049)[0] == "no"
       and gate_side(0.5)[0] is None, "the gate fires on both tails only")
    seen = []

    def step(sec):
        seen.append(sec)
        return {"A": 0.999 if sec >= 1000 - 10 else 0.5}
    got = scan_close(1000, ["A"], step)
    ck(first_gate(got["A"])[0] == 990 and first_gate(got["A"])[1] == 10,
       "the scan returns the FIRST qualifying second, not the last")
    ck(seen == sorted(seen), "and it walks time forwards, never backwards")
    ck(len(got["A"]) == 28 and got["A"][-1][0] == 997,
       "and it keeps every second's fair, gated or not, for the cancel test")
    ck(first_gate([]) is None, "a market that never gates yields no entry")

    # --- cancel on alarm: when would a watching maker's bid be gone? -----
    path = [(100, 30, 0.999), (101, 29, 0.999), (102, 28, 0.40),
            (103, 27, 0.01)]
    ck(pull_ms(path, 100, "yes", 0.70) == 103000,
       "the bid is pulled one second after belief first breaks the threshold")
    ck(pull_ms(path, 100, "yes", 0.30) == 104000,
       "a lower threshold fires later, at the second that actually breaks it")
    ck(pull_ms(path, 102, "yes", 0.70) == 104000,
       "an alarm before entry is not an alarm -- only seconds AFTER count")
    ck(pull_ms(path[:2], 100, "yes", 0.70) is None,
       "and a belief that never turns never pulls")
    ck(pull_ms(path, 100, "no", 0.70) == 102000,
       "the threshold reads belief in OUR side, so the identical path alarms "
       "at once for a NO position and not at all for the YES one")
    ec = {"won": False, "rules": {"REST-1": 0.9}, "fill": {("REST-1", 5,
          "opt"): 103500}, "pull": {0.90: 103000, 0.70: None}}
    ck(filled(ec, "REST-1", 5, "opt") is True,
       "without a cancel the fill stands")
    ck(filled(ec, "REST-1", 5, "opt", 0.90) is False,
       "a fill after the pull does not happen")
    ck(filled(ec, "REST-1", 5, "opt", 0.70) is True,
       "and a threshold that never alarmed leaves it alone")
    ck(rule_dollars(ec, "REST-1", 5, "opt", 0.90) == 0.0
       and abs(rule_dollars(ec, "REST-1", 5, "opt") + 18.0) < 1e-9,
       "cancelling that fill turns an $18 loss into exactly $0")

    # ENTRY B: the first gated second in which an acceptable offer traded.
    seq = [(990, 10, 0.999), (991, 9, 0.999), (992, 8, 0.999)]
    asks = {990: 0.995, 991: 0.992, 992: 0.975}
    b = first_tradeable(seq, lambda s, w: (asks[s], s * 1000), 0.98)
    ck(b is not None and b[0] == 992 and abs(b[4] - 0.975) < 1e-9,
       "entry B skips the seconds the live ceiling would refuse and takes "
       "the first acceptable one, at that second's own price")
    ck(first_tradeable(seq, lambda s, w: (asks[s], s * 1000), 0.90) is None,
       "and reports nothing when no second is ever acceptable")
    ck(first_tradeable(seq, lambda s, w: (None, None), 0.99) is None,
       "and nothing when no offer traded at all")
    # best_in_second must return the TOUCH of a sweep, not its last leg
    bs = best_in_second("yes", [5000, 5100, 5200, 6000],
                        [True, True, True, True],
                        [0.96, 0.97, 0.98, 0.90], 5)
    ck(abs(bs[0] - 0.96) < 1e-9 and bs[1] == 5000,
       "the best offer in a second is the sweep's TOUCH leg, and a print in "
       "the next second is not visible")
    ck(best_in_second("yes", [5000], [False], [0.96], 5)[0] is None,
       "and an other-side print is not an offer on our side")

    # --- side mapping, both directions ------------------------------------
    # one print: taker bought NO at 40c, i.e. SOLD YES at 60c.
    ts, sd, px, ct = [5000], [False], [0.60], [50.0]
    ck(rest_fill(0.62, "yes", ts, sd, px, ct, 0, 9999, "opt") == 5000,
       "a YES bid at 62c is filled by a seller of YES printing at 60c")
    ck(rest_fill(0.58, "yes", ts, sd, px, ct, 0, 9999, "opt") is None,
       "a YES bid at 58c is NOT filled by that print -- it never reached us")
    ck(rest_fill(0.45, "no", ts, sd, px, ct, 0, 9999, "opt") is None,
       "and the same print cannot fill a NO bid: its taker BOUGHT no")
    ts2, sd2, px2, ct2 = [5000], [True], [0.60], [50.0]
    ck(rest_fill(0.41, "no", ts2, sd2, px2, ct2, 0, 9999, "opt") == 5000,
       "a NO bid at 41c is filled by a seller of NO (a YES taker) at no 40c")
    ck(rest_fill(0.62, "yes", ts2, sd2, px2, ct2, 0, 9999, "opt") is None,
       "a same-side print can never fill our own bid")

    # --- no lookahead, and the R window ----------------------------------
    ck(rest_fill(0.62, "yes", ts, sd, px, ct, 5001, 9999, "opt") is None,
       "a print BEFORE our placement instant does not fill us")
    ck(rest_fill(0.62, "yes", ts, sd, px, ct, 0, 4999, "opt") is None,
       "and one after the R window closes does not either")

    # --- fill definitions bracket -----------------------------------------
    ck(rest_fill(0.60, "yes", ts, sd, px, ct, 0, 9999, "pess") is None,
       "queue-pessimistic refuses a print AT our price (queue unknown)")
    ck(rest_fill(0.61, "yes", ts, sd, px, ct, 0, 9999, "pess") == 5000,
       "but accepts one strictly THROUGH it")
    ck(rest_fill(0.62, "yes", ts, sd, px, ct, 0, 9999, "size", need=50.0)
       == 5000 and rest_fill(0.62, "yes", ts, sd, px, ct, 0, 9999, "size",
                             need=51.0) is None,
       "size-aware fills on 50 contracts and refuses when 51 are needed")

    # --- quotes are read backwards, and both sides ------------------------
    q = infer_quotes("yes", [1000, 2000, 3000], [False, True, False],
                     [0.55, 0.62, 0.57], 3999, 0)
    ck(abs(q[0] - 0.62) < 1e-9 and abs(q[2] - 0.57) < 1e-9,
       "the ask comes from the last same-side taker, the bid from the last "
       "other-side taker")
    q2 = infer_quotes("yes", [1000, 2000, 3000], [False, True, False],
                      [0.55, 0.62, 0.57], 1999, 0)
    ck(q2[0] is None and abs(q2[2] - 0.55) < 1e-9,
       "and nothing after the cut-off instant is visible")

    # --- PLANTED: a known fill rate must come back ------------------------
    for frac in (0.25, 0.60, 1.00):
        es = _synth(400, frac, 0.96, 0.959)
        fl = sum(1 for e in es if outcome(e, "REST-1", 5, "opt"))
        ck(abs(fl / len(es) - frac) < 1e-9,
           f"a planted resting fill rate of {frac:.0%} is recovered exactly")

    # --- PLANTED: an advantage of a known size ----------------------------
    es = _synth(400, 1.00, 0.96, 0.959, won=True)
    pc_t = per_close(es, lambda e: rule_dollars(e, "TAKE", 5, "opt"))
    pc_r = per_close(es, lambda e: rule_dollars(e, "REST-1", 5, "opt"))
    d = stats(paired(pc_r, pc_t))
    want = (20 * (1 - 0.959)) - (20 * (1 - 0.96) - billed_fee(0.96, 20))
    ck(abs(d["mean"] - want) < 1e-9,
       f"a resting rule that always fills one tick cheaper is worth exactly "
       f"${want:.4f}/close and the estimator says ${d['mean']:.4f}")

    # --- PLANTED NULL: built by arithmetic so the two are EQUAL -----------
    # take:  20*(1-pt) - fee(pt)        rest: frac * 20*(1-pr)
    pt, pr = 0.96, 0.90
    frac = (20 * (1 - pt) - billed_fee(pt, 20)) / (20 * (1 - pr))
    n = 1000
    k = int(round(frac * n))
    es = _synth(n, k / n, pt, pr, won=True)
    for e in es:                     # REST-1 is the rule under test here
        e["rules"]["REST-1"] = pr
    pc_t = per_close(es, lambda e: rule_dollars(e, "TAKE", 5, "opt"))
    pc_r = per_close(es, lambda e: rule_dollars(e, "REST-1", 5, "opt"))
    d = stats(paired(pc_r, pc_t))
    ck(abs(d["mean"]) < 0.002,
       f"a world where patience is EXACTLY break-even by construction "
       f"(fill rate {frac:.3%}) returns ${d['mean']:+.5f}/close -- no "
       f"advantage found where none exists")
    ck(abs(d["mean"]) < d["mde"],
       f"and the finding sits inside its own MDE of ${d['mde']:.4f}")

    # --- a MISS must score zero, not be dropped --------------------------
    es = _synth(100, 0.50, 0.96, 0.90, won=True)
    pc_r = per_close(es, lambda e: rule_dollars(e, "REST-1", 5, "opt"))
    ck(sum(1 for v in pc_r.values() if v == 0.0) == 50,
       "half the closes miss and every one of them scores exactly $0")
    ck(abs(sum(pc_r.values()) / len(pc_r) - 0.5 * 20 * 0.10) < 1e-9,
       "so the per-close mean is halved by the misses, as it must be")

    # --- losses must reverse the sign ------------------------------------
    es = _synth(100, 1.00, 0.96, 0.90, won=False)
    pc_r = per_close(es, lambda e: rule_dollars(e, "REST-1", 5, "opt"))
    ck(abs(sum(pc_r.values()) / len(pc_r) + 18.0) < 1e-9,
       "a resting buy at 90c that loses costs $18 on 20 contracts")

    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for x in f:
        print("   - " + x)
    return not f


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--days", type=int, default=9)
    ap.add_argument("--end", default=None,
                    help="last trade hour to include, e.g. 20260912T04")
    ap.add_argument("--md", default=REPORT)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    mk = load_markets()
    files = sorted(glob.glob(os.path.join(DATA, "trade", "2026*.jsonl.gz")))[:-1]
    if a.end:
        files = [x for x in files if os.path.basename(x)[:11] <= a.end]
    # THE WINDOW IS A CLOCK RANGE, NOT A FILE COUNT. Hours are missing from
    # the tape here and there, so taking the last 24*days files silently
    # reaches further back than `days` and hands the splitter a ragged extra
    # part-day at the front.
    last = calendar.timegm(time.strptime(os.path.basename(files[-1])[:11],
                                         "%Y%m%dT%H")) + 3600
    start = time.strftime("%Y%m%dT%H", time.gmtime(last - a.days * 86400))
    files = [x for x in files if os.path.basename(x)[:11] >= start]
    print(f"\n  {len(mk):,} settled markets, {len(files)} trade hours "
          f"({os.path.basename(files[0])[:11]} .. "
          f"{os.path.basename(files[-1])[:11]}) = {a.days} days\n", flush=True)

    entries, entries_b = [], []
    sweep, counters = defaultdict(float), defaultdict(int)
    sweep["legs_hist"] = []
    t0 = time.time()
    for i, fp in enumerate(files, 1):
        stamp = os.path.basename(fp)[:11]
        run_hour(stamp, mk, entries, entries_b, sweep, counters)
        if i % 12 == 0 or i == len(files):
            print(f"    {stamp}  {i}/{len(files)}  entries {len(entries):,}  "
                  f"{time.time()-t0:.0f}s", flush=True)

    if not entries:
        print("  loaded nothing -- " + str(dict(counters)))
        return

    lines = []

    def out(s=""):
        lines.append(s)
        print(s)

    out("# RESULTS — pinmaker: how to buy better (take vs rest)")
    out("")
    out(f"`{time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}` — "
        f"`research/pinmaker.py`, trade tape only.")
    report(entries, entries_b, sweep, counters, out)
    with open(a.md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\n  wrote {a.md}")


if __name__ == "__main__":
    main()
