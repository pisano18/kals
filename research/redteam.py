"""redteam.py -- plant real-world faults into the REAL live trade loop, offline.

WHAT IT DOES. Drives pinrun's own `trade_loop` through
`pinrun._offline_trade_loop` (a fake clock, a fake book, a fake index, a fake
order wire; `ordercli.send` is replaced and the base is DEMO, so nothing can
leave this machine). It never passes --live to anything, never imports
kauth, and never writes outside its own temp dirs and the one report.

Each scenario runs TWICE: a CONTROL world where nothing goes wrong, and the
same world with one fault planted. The verdict is the difference.

THE WIRE KNOWS THE TRUTH. `_offline_trade_loop`'s stock wire fills every
order at its own limit, which cannot tell a hedge sent at a stale price
from a good one. The wire here holds the TRUE book of each market at each
fake second and fills an IOC only if its limit reaches the true ask; a
fault can make the answer the BOT SEES differ from what the exchange DID
(a 500 on an order that did not fill; a timeout on one that did). Money is
scored on what the exchange did, never on what the bot believed.

MONEY. Every world trades 5 contracts. Live auto-size is ~88 at a ~$1,043
bank (CURRENT_STATE 09-25), so money columns are also shown x17.6. That
scale-up is arithmetic on a planted world, NOT a measured loss: the reason
for a red is the mechanism, the dollars are its size if it fires once.

    python research/redteam.py --selftest
    python research/redteam.py            # self-test, then every scenario
    python research/redteam.py --json out.json
"""
import argparse
import json
import os
import sys
import time as _time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CLOSE = 1_800_000_000          # _offline_trade_loop's fixed close
LIVE_SCALE = 88.0 / 5.0        # live contracts / world contracts

# The live hedge settings (restart_bot.ps1 argv, v-zerotake). The offline
# loop pins every flag to its SHIPPED default; these are handed back in so
# the hedge behaves the way the live one does.
LIVE_FLAGS = {"HEDGE_BELIEF": 0.40, "HEDGE_SLIP": 0.10, "HEDGE_PROP": False}


def _pr():
    import pinrun
    return pinrun


def ob(yes_bid, no_bid, size=50.0, age_ms=5):
    return _pr()._ob(yes_bid, no_bid, size=size, age_ms=age_ms)


# ---------------------------------------------------------------------------
# the world
# ---------------------------------------------------------------------------
HEALTHY_A = (0.94, 0.05)       # yes ask 95c: A is bought on the first look
COLLAPSED_A = (0.28, 0.66)     # yes ask 34c, NO ask 72c: the hedge's price


def mkt_A(collapse_at=4.0, result="no", **kw):
    """Held from the first look at 95c; belief falls to 0.30 at collapse_at,
    and the TRUE book falls with it. Settles `result`."""
    def fair(t):
        return 0.30 if (collapse_at is not None and t >= collapse_at) else 0.999

    def truth(t):
        # wall time t reaches index second s at s - 0.1 (t0 = close-tau0+0.1)
        if collapse_at is not None and t >= collapse_at - 0.1 - 1e-9:
            # after the collapse the market grows MORE sure every second,
            # so a hedge that is late costs money: NO ask 72c rising 2c/s
            yb = max(0.02, COLLAPSED_A[0] - 0.02 * max(0.0, t - collapse_at))
            return ob(round(yb, 2), COLLAPSED_A[1])
        return ob(*HEALTHY_A)
    m = {"tk": "KXAAA15M-RT", "series": "KXAAA15M", "iid": "RTA",
         "strike": 100.0, "fair": fair, "truth": truth, "book": truth,
         "result": result}
    m.update(kw)
    return m


def mkt_B(decided_at=2.0, result="yes", tk="KXBBB15M-RT", **kw):
    """Undecided until decided_at, then a 93c buy that wins."""
    def truth(t):
        return ob(0.92, 0.07)
    m = {"tk": tk, "series": tk.split("-")[0], "iid": "RT" + tk[2:5],
         "strike": 100.0,
         "fair": (lambda t: 0.999 if t >= decided_at else 0.5),
         "truth": truth, "book": truth, "result": result}
    m.update(kw)
    return m


class Wire:
    """The fake exchange. fill() decides what REALLY happened; `fault` may
    replace what the bot is TOLD. Every true fill is kept in self.fills."""

    def __init__(self, markets, tau0, fault=None):
        self.by_tk = {m["tk"]: m for m in markets}
        self.t0 = CLOSE - tau0 + 0.1
        self.fault = fault
        self.fills = []           # (t, tk, want, n, px)
        self.sent = []            # (t, tk, want, count, limit, told_status)
        self.oid = 0

    def now(self):
        return _pr().time.t - self.t0

    def true_fill(self, body, t):
        m = self.by_tk.get(body.get("ticker"))
        want = "yes" if body.get("side") == "bid" else "no"
        lim = float(body["price"]) if want == "yes" else 1.0 - float(body["price"])
        cnt = float(body.get("count"))
        if m is None:
            return want, 0.0, None
        b = m["truth"](t)
        ask = b.get("yes_ask") if want == "yes" else b.get("no_ask")
        asz = b.get("yes_ask_size") if want == "yes" else b.get("no_ask_size")
        if ask is None or lim + 1e-9 < float(ask):
            return want, 0.0, None
        return want, min(cnt, float(asz or 0.0)), float(ask)

    def response(self, body, want, n, px):
        self.oid += 1
        yes_px = None if px is None else (px if want == "yes" else 1.0 - px)
        return 201, {"order_id": "rt-%d" % self.oid,
                     "client_order_id": body.get("client_order_id"),
                     "fill_count": "%.2f" % n, "remaining_count": "0.00",
                     "status": "executed" if n > 0 else "canceled",
                     "average_fill_price": (None if yes_px is None
                                            else "%.4f" % yes_px),
                     "average_fee_paid": "0.0000"}

    def __call__(self, body, n):
        t = self.now()
        want, fn, px = self.true_fill(body, t)
        told = None
        if self.fault is not None:
            told = self.fault(self, body, t, want, fn, px)
        if told is not None:
            # the fault decides both: (really_filled, status, resp)
            real_n, st, resp = told
            if real_n:
                self.fills.append((round(t, 3), body["ticker"], want,
                                   float(real_n), px))
            self.sent.append((round(t, 3), body["ticker"], want,
                              float(body["count"]), body["price"], st))
            return st, resp
        if fn > 0:
            self.fills.append((round(t, 3), body["ticker"], want, fn, px))
        st, resp = self.response(body, want, fn, px)
        self.sent.append((round(t, 3), body["ticker"], want,
                          float(body["count"]), body["price"], st))
        return st, resp


def true_pnl(wire, markets):
    """Dollars the EXCHANGE would settle, from true fills and planted results.
    Returns (pnl, per-ticker {yes, no, cost})."""
    res = {m["tk"]: m.get("result") for m in markets}
    pnl, per = 0.0, {}
    for (_t, tk, want, n, px) in wire.fills:
        d = per.setdefault(tk, {"yes": 0.0, "no": 0.0, "cost": 0.0})
        d[want] += n
        d["cost"] += n * px
        won = (res.get(tk) == want)
        pnl += n * ((1.0 - px) if won else -px)
    return round(pnl, 4), per


def run(markets, tau0=30, run_s=12.0, fault=None, flags=None, pre=None,
        post=None, **kw):
    """One world through the real loop. `pre(pinrun)` may patch before the run
    and must return an undo(); kw goes to _offline_trade_loop."""
    pr = _pr()
    wire = Wire(markets, tau0, fault)
    f = dict(LIVE_FLAGS)
    f.update(flags or {})
    undo = pre(pr, wire) if pre else None
    t_wall = _time.time()
    try:
        res = pr._offline_trade_loop(markets, live=True, reply=wire,
                                     tau0=tau0, run_s=run_s, flags=f, **kw)
    finally:
        if undo:
            undo()
    res["wire"] = wire
    res["pnl"], res["per"] = true_pnl(wire, markets)
    res["wall_s"] = round(_time.time() - t_wall, 2)
    return res


def kinds(res, kind, tk=None):
    return [r for r in res["recs"] if r["kind"] == kind
            and (tk is None or r.get("ticker") == tk)]


def naked(res, tk):
    """Contracts of `tk` held on the side that LOST with nothing opposite.
    For A (bought YES, settles NO) that is yes - no."""
    d = res["per"].get(tk) or {"yes": 0.0, "no": 0.0}
    return round(d["yes"] - d["no"], 4)


def summary(res, tk="KXAAA15M-RT"):
    w = res["wire"]
    return {"raised": res["raised"], "ran_s": res["ran_s"],
            "pnl": res["pnl"], "naked_A": naked(res, tk),
            "sent": len(w.sent), "fills": len(w.fills),
            "halts": [str(r.get("why"))[:90] for r in kinds(res, "halt")],
            "pending": [str(r.get("why"))[:90] for r in kinds(res, "halt_pending")],
            "errors": [(r.get("where"), str(r.get("err"))[:60])
                       for r in kinds(res, "error")][:4],
            "hedge_unknown": len(kinds(res, "hedge_unknown")),
            "hedge_not_sent": len(kinds(res, "hedge_not_sent")),
            "hedge_blind": [r.get("why") for r in kinds(res, "hedge_blind")],
            "first_hedge_t": next((f[0] for f in w.fills
                                   if f[1] == tk and f[2] == "no"), None)}


# ---------------------------------------------------------------------------
# patch helpers: things _offline_trade_loop has no knob for
# ---------------------------------------------------------------------------
def patch_get(fn):
    """Wrap pinrun.get INSIDE the run: trade_loop is looked up by name at
    call time, so a wrapper installed around it sees the harness's fake get
    and can alter its answers. The harness restores `get` itself."""
    def pre(pr, wire):
        real_tl = pr.trade_loop

        def tl(*a, **k):
            inner = pr.get
            pr.get = (lambda path, params=None, **kw_:
                      fn(inner, path, params, wire, **kw_))
            return real_tl(*a, **k)
        pr.trade_loop = tl

        def undo():
            pr.trade_loop = real_tl
        return undo
    return pre


def settle_with(status_of):
    """GET /markets/<tk> answers with the planted result once the close is
    20 s past; status_of(tk) is the status string sent."""
    def fn(inner, path, params, wire, **kw):
        if path.startswith("/markets/"):
            tk = path.split("/")[-1]
            m = wire.by_tk.get(tk)
            if m is not None and _pr().time.t > CLOSE + 20:
                return 200, {"market": {"status": status_of(tk),
                                        "result": m.get("result")}}
        return inner(path, params, **kw)
    return fn


# ---------------------------------------------------------------------------
# faults on the wire: each returns None (pass through) or
# (contracts REALLY filled, status the bot sees, response the bot sees)
# ---------------------------------------------------------------------------
def _is_hedge(body, tk="KXAAA15M-RT"):
    return body.get("ticker") == tk and body.get("side") == "ask"


def hedge_status(codes, really_fills=False):
    """The first len(codes) hedge POSTs on A answer codes[i]; the order
    REALLY filled only if really_fills. Then the wire is healthy."""
    st = {"n": 0}

    def f(w, body, t, want, fn, px):
        if not _is_hedge(body) or st["n"] >= len(codes):
            return None
        code = codes[st["n"]]
        st["n"] += 1
        real = fn if really_fills else 0.0
        if code == -1:
            return real, -1, "timed out"
        return real, code, json.dumps({"error": {"code": "planted",
                                                 "message": str(code)}})
    return f


def entry_status(tk, code, really_fills=True):
    """The first entry on `tk` answers `code` though it REALLY filled."""
    st = {"n": 0}

    def f(w, body, t, want, fn, px):
        if body.get("ticker") != tk or body.get("side") != "bid" or st["n"]:
            return None
        st["n"] += 1
        real = fn if really_fills else 0.0
        if code == -1:
            return real, -1, "timed out"
        return real, code, json.dumps({"error": {"code": "planted"}})
    return f


def partial_then_drop(first_n=2.0):
    """The first hedge fills first_n contracts; every later hedge POST times
    out and really does NOT fill (the connection dropped)."""
    st = {"n": 0}

    def f(w, body, t, want, fn, px):
        if not _is_hedge(body):
            return None
        st["n"] += 1
        if st["n"] == 1:
            n = min(first_n, fn)
            code, resp = w.response(body, want, n, px)
            return n, code, resp
        return 0.0, -1, "timed out"
    return f


def slow_ack(tk, hang_s, code=201):
    """The first entry on `tk` hangs `hang_s` fake seconds (the loop is
    single-threaded, so everything waits) and then answers `code`; it
    really filled either way."""
    st = {"n": 0}

    def f(w, body, t, want, fn, px):
        if body.get("ticker") != tk or body.get("side") != "bid" or st["n"]:
            return None
        st["n"] += 1
        _pr().time.t += float(hang_s)
        if code == -1:
            return fn, -1, "timed out"
        c, resp = w.response(body, want, fn, px)
        return fn, c, resp
    return f


def dup_ids():
    """Every acknowledgement carries the SAME order_id."""
    def f(w, body, t, want, fn, px):
        c, resp = w.response(body, want, fn, px)
        resp["order_id"] = "dup-1"
        return fn, c, resp
    return f


def _stale_book(m, from_t, to_t, how="frozen"):
    """What the BOT sees of market m: from from_t to to_t the Kalshi socket
    is down. 'frozen' = the last snapshot, ageing; 'none' = no book;
    'empty' = a book with no prices at all."""
    snap = m["truth"](from_t - 0.01)
    truth = m["truth"]

    def book(t):
        if from_t <= t < to_t:
            if how == "none":
                return None
            if how == "empty":
                return ob(None, None)
            b = dict(snap)
            b["age_ms"] = int(1000 * (t - from_t)) + 5
            return b
        return truth(t)
    return book


def _S(sid, title, fault_note, run_ctl, run_flt, judge):
    return {"id": sid, "title": title, "fault": fault_note,
            "run_ctl": run_ctl, "run_flt": run_flt, "judge": judge}


def _b_falls(tk="KXBBB15M-RT", at=6.0):
    """B, bought at +2, falls at +`at` and settles NO."""
    m = mkt_B(decided_at=2.0, result="no", tk=tk)
    f0 = m["fair"]
    m["fair"] = lambda t: 0.30 if t >= at else f0(t)

    def tr(t):
        if t >= at - 0.1:
            return ob(round(max(0.02, 0.28 - 0.02 * (t - at)), 2), 0.66)
        return ob(0.92, 0.07)
    m["truth"] = m["book"] = tr
    return m


def scenarios():
    A, B = mkt_A, mkt_B
    out = []
    base = lambda **k: run([A(), B()], **k)          # noqa: E731

    out.append(_S("idx_all", "Index feed drops for ALL coins mid-hold",
                  "every index stops at +3; A's market falls at +4 and only "
                  "the book shows it", base,
                  lambda: base(freeze_at=3), "hedge"))
    out.append(_S("idx_one", "Index frozen for ONE coin only",
                  "A's index stops at +3, B's keeps printing; A falls at +4",
                  base, lambda: run([A(freeze_at=3), B()]), "hedge"))
    a3 = A()
    a3["book"] = _stale_book(a3, 3.0, 9.0, "frozen")
    out.append(_S("book_frozen", "Kalshi book socket drops mid-hedge (stale snapshot)",
                  "A's book frozen at the pre-fall snapshot from +3 to +9",
                  base, lambda: run([a3, B()]), "hedge"))
    a3n = A()
    a3n["book"] = _stale_book(a3n, 3.0, 9.0, "none")
    out.append(_S("book_gone", "Kalshi book socket drops mid-hedge (no book)",
                  "A's book reads None from +3 to +9",
                  base, lambda: run([a3n, B()]), "hedge"))
    out.append(_S("hedge_429", "Order wire 429 (rate limit) on the hedge, twice",
                  "first two hedge POSTs answer 429; nothing placed",
                  base, lambda: base(fault=hedge_status([429, 429])), "hedge"))
    for code in (500, 503):
        out.append(_S("hedge_%d" % code,
                      "Order wire %d on the hedge (order NOT placed)" % code,
                      "first hedge POST answers %d; the exchange placed "
                      "nothing" % code, base,
                      (lambda c=code: base(fault=hedge_status([c]))), "hedge"))
    out.append(_S("hedge_timeout", "Order wire TIMEOUT on the hedge (order NOT placed)",
                  "first hedge POST times out (-1); the exchange placed nothing",
                  base, lambda: base(fault=hedge_status([-1])), "hedge"))
    for code in (500, -1):
        nm = "500" if code == 500 else "timeout"
        out.append(_S("entry_" + nm,
                      "Entry answered %s but it REALLY filled" % nm,
                      "B's entry fills at the exchange, the bot is told %s; "
                      "B falls at +6" % nm,
                      lambda: run([A(collapse_at=None, result="yes"), _b_falls()]),
                      (lambda c=code: run([A(collapse_at=None, result="yes"),
                                           _b_falls()],
                                          fault=entry_status("KXBBB15M-RT", c))),
                      "B"))
    out.append(_S("partial_drop", "Partial hedge fill, then the connection drops",
                  "the hedge fills 2 of 5; every later hedge POST times out "
                  "and is never placed", base,
                  lambda: base(fault=partial_then_drop(2.0)), "hedge"))
    out.append(_S("slow_ack", "An entry acknowledgement hangs 20 s",
                  "B's entry at +3 hangs 20 s (the order client's timeout) "
                  "then times out, really filled; A falls at +4",
                  lambda: base(run_s=28.0),
                  lambda: base(run_s=28.0,
                               fault=slow_ack("KXBBB15M-RT", 20.0, code=-1)),
                  "hedge"))
    out.append(_S("fill_after_close", "A fill acknowledged AFTER the close",
                  "B's entry at +3 hangs 30 s, then reports filled",
                  lambda: run([A(collapse_at=None, result="yes"), B()], run_s=40.0),
                  lambda: run([A(collapse_at=None, result="yes"), B()], run_s=40.0,
                              fault=slow_ack("KXBBB15M-RT", 30.0, code=201)),
                  "survive"))
    for dt in (2.0, -2.0):
        out.append(_S("clock%+d" % dt, "Clock jumps %+d s mid-hold" % dt,
                      "the wall clock steps %+g s at +3.5" % dt, base,
                      (lambda d=dt: base(stall=(3.5, d))), "hedge"))
    out.append(_S("slow_universe", "Universe refresh takes 5 s per call",
                  "every GET /markets costs 5 s; start 90 s out; A falls at "
                  "20 s to go",
                  lambda: run([A(collapse_at=70.0), B(decided_at=62.0)],
                              tau0=90, run_s=85.0),
                  lambda: run([A(collapse_at=70.0), B(decided_at=62.0)],
                              tau0=90, run_s=85.0, get_delay=5.0),
                  "hedge"))
    a10 = A()
    a10["book"] = _stale_book(a10, 3.0, 1e9, "empty")
    c10 = B(decided_at=6.0, tk="KXCCC15M-RT")
    c10["book"] = _stale_book(c10, 3.0, 1e9, "empty")
    out.append(_S("rename_book", "Kalshi renames the book's price field",
                  "from +3 every book is empty (livebook drops an unknown key "
                  "without a word); A falls at +4; C would be bought at +6",
                  lambda: run([A(), B(decided_at=6.0, tk="KXCCC15M-RT")]),
                  lambda: run([a10, c10]), "hedge"))

    def _no_strike(inner, path, params, wire, **kw):
        st, b = inner(path, params, **kw)
        if path == "/markets" and isinstance(b, dict):
            for m in b.get("markets") or []:
                m["floor_strike_dollars"] = m.pop("floor_strike", None)
                m.pop("custom_strike", None)
        return st, b
    out.append(_S("rename_strike", "Kalshi renames floor_strike in /markets",
                  "every listed market arrives with no floor_strike",
                  base, lambda: base(pre=patch_get(_no_strike)), "survive"))
    out.append(_S("status_new", "Settlement arrives under a NEW status word",
                  "GET /markets/A answers status 'settled' (not 'finalized'), "
                  "result 'no'; A was not hedged",
                  lambda: run([A(collapse_at=None)], run_s=60.0,
                              pre=patch_get(settle_with(lambda tk: "finalized"))),
                  lambda: run([A(collapse_at=None)], run_s=960.0,
                              pre=patch_get(settle_with(lambda tk: "settled"))),
                  "book"))
    a13 = A()
    a13["truth"] = a13["book"] = _stale_book(A(), 3.5, 1e9, "empty")
    out.append(_S("closes_early", "A held market closes early (book empties)",
                  "A's book and the exchange empty at +3.5; A's model falls "
                  "at +4", base, lambda: run([a13, B()]), "survive"))
    out.append(_S("dup_ack", "Duplicate order ids in acknowledgements",
                  "every ack carries order_id 'dup-1'; A falls at +6, after "
                  "B's entry at +3",
                  lambda: run([A(collapse_at=6.0), B()]),
                  lambda: run([A(collapse_at=6.0), B()], fault=dup_ids()),
                  "hedge"))

    def _disk(kind, kw):
        if _pr().time.t - (CLOSE - 30 + 0.1) >= 3.0:
            raise OSError(28, "No space left on device")
    out.append(_S("disk_full", "Disk fills: every record write raises",
                  "rec() raises OSError(28) from +3 (live rec() swallows it; "
                  "this is the harsher case)", base,
                  lambda: base(rec_fault=_disk), "hedge"))
    c16 = B(decided_at=0.0, result="no", tk="KXCCC15M-RT")
    c16["fair"] = lambda t: 0.5 if t < 3 else 0.999
    c16["truth"] = lambda t: ob(0.40, 0.55) if t < 3 else ob(0.35, 0.58)

    def _c16_book(t):
        if t < 3:
            return ob(0.40, 0.55)
        b = ob(0.92, 0.07)               # a stale, confident-looking book
        b["age_ms"] = 5 if t >= 25 else int(1000 * (t - 3)) + 5
        return b
    c16["book"] = _c16_book
    a16 = A()
    a16["book"] = _stale_book(a16, 3.0, 25.0, "frozen")
    out.append(_S("sleep_resume", "Windows sleep/resume (15 s asleep)",
                  "clock jumps +15 s at +3; every index frozen from +3; books "
                  "frozen and ageing until +25; A falls at +4 (while asleep); "
                  "C looks like a 93c buy on the stale book, really 42c",
                  lambda: run([A(), B()], run_s=26.0),
                  lambda: run([a16, B(), c16], run_s=26.0, freeze_at=3,
                              stall=(3.0, 15.0)),
                  "hedge+C"))
    out.append(_S("run_end", "The run's --minutes ends while holding",
                  "the loop's time is up at +6; A falls at +8",
                  lambda: run([A(collapse_at=8.0), B()], run_s=12.0),
                  lambda: run([A(collapse_at=8.0), B()], run_s=6.0),
                  "hedge"))
    out.append(_S("dup_ack_settle", "Duplicate order ids: are both SETTLED?",
                  "every ack carries order_id 'dup-1'; run to settlement "
                  "(A loses unhedged, B wins)",
                  lambda: run([A(collapse_at=None), B()], run_s=60.0,
                              pre=patch_get(settle_with(lambda tk: "finalized"))),
                  lambda: run([A(collapse_at=None), B()], run_s=60.0,
                              fault=dup_ids(),
                              pre=patch_get(settle_with(lambda tk: "finalized"))),
                  "book"))
    return out


# ---------------------------------------------------------------------------
# verdicts
# ---------------------------------------------------------------------------
def judge(s, c, f):
    """(colour, why, extra loss in the world $, same x live scale)."""
    extra = round(c["pnl"] - f["pnl"], 4)
    live = round(extra * LIVE_SCALE, 2)
    if f["raised"]:
        return "RED", "the loop died: " + f["raised"][:80], extra, live
    j = s["judge"]
    if j in ("hedge", "hedge+C"):
        nk = naked(f, "KXAAA15M-RT")
        if j == "hedge+C" and (f["per"].get("KXCCC15M-RT") or {}).get("yes"):
            return "RED", "bought on a stale book", extra, live
        if nk > 1e-9:
            return ("RED", "%g of 5 contracts left with NO hedge" % nk,
                    extra, live)
        if extra > 1e-6:
            return ("AMBER", "hedged, but late (first hedge fill +%s s vs +%s s)"
                    % (summary(f)["first_hedge_t"], summary(c)["first_hedge_t"]),
                    extra, live)
        return "GREEN", "hedged as in the control", extra, live
    if j == "B":
        nk = naked(f, "KXBBB15M-RT")
        if nk > 1e-9:
            return ("RED", "%g contracts filled that the bot does not know it "
                    "holds: never hedged" % nk, extra, live)
        return "GREEN", "tracked and hedged", extra, live
    if j == "book":
        cs, fs = len(kinds(c, "settled")), len(kinds(f, "settled"))
        if fs < cs:
            return ("RED", "%d of %d settlements never booked: the loss brakes "
                    "cannot see them" % (cs - fs, cs), extra, live)
        return "GREEN", "every settlement booked (%d)" % fs, extra, live
    # survive
    if len(f["wire"].sent) == 0 and len(c["wire"].sent) > 0:
        return ("AMBER", "no crash, but it stopped trading and said nothing",
                extra, live)
    return "GREEN", "no crash, nothing lost", extra, live


def run_all(only=None):
    rows = []
    for s in scenarios():
        if only and s["id"] not in only:
            continue
        c = s["run_ctl"]()
        f = s["run_flt"]()
        col, why, extra, live = judge(s, c, f)
        rows.append({"id": s["id"], "title": s["title"], "fault": s["fault"],
                     "verdict": col, "why": why, "extra_loss_world": extra,
                     "extra_loss_live_scale": live,
                     "ctl": summary(c), "flt": summary(f),
                     "flt_sent": f["wire"].sent, "flt_fills": f["wire"].fills,
                     "ctl_settled": len(kinds(c, "settled")),
                     "flt_settled": len(kinds(f, "settled"))})
    return rows


# ---------------------------------------------------------------------------
# self-test: the harness must see a planted fault and must see nothing in a
# world with nothing planted
# ---------------------------------------------------------------------------
def selftest():
    fails = []

    def ck(ok, msg):
        print("  %s  %s" % ("ok  " if ok else "FAIL", msg))
        if not ok:
            fails.append(msg)
    print("SELF-TEST -- redteam")
    # 1. true_pnl arithmetic on a hand-built wire (known answer)
    w = Wire([mkt_A()], 30)
    w.fills = [(0, "KXAAA15M-RT", "yes", 5.0, 0.95),
               (4, "KXAAA15M-RT", "no", 5.0, 0.72)]
    p, per = true_pnl(w, [mkt_A()])
    ck(abs(p - (-4.75 + 1.40)) < 1e-9 and per["KXAAA15M-RT"]["yes"] == 5.0,
       "true_pnl: 5 YES at 95c lost + 5 NO at 72c won = -$3.35 (got %s)" % p)
    # 2. the truth-aware wire refuses a limit under the true ask
    w2 = Wire([mkt_A()], 30)
    b = _pr().pintake.build_take("KXAAA15M-RT", "no", 0.20, 5, 2)
    ck(w2.true_fill(b, 5.0)[1] == 0.0 and w2.true_fill(b, 1.0)[1] == 5.0,
       "wire: a 20c NO limit fills before the fall (ask 6c), not after (72c+)")
    # 3. CONTROL: the real loop hedges all of A (a world where the answer is known)
    c = run([mkt_A(), mkt_B()])
    ck(c["raised"] is None and naked(c, "KXAAA15M-RT") == 0.0
       and summary(c)["first_hedge_t"] is not None,
       "control: A is bought and hedged in full, nothing raised")
    # 4. NULL: a fault hook that never fires changes nothing at all
    n = run([mkt_A(), mkt_B()], fault=lambda *a: None)
    ck(n["wire"].fills == c["wire"].fills and n["pnl"] == c["pnl"],
       "null fault: identical fills and money to the control")
    col, _w, _e, _l = judge({"judge": "hedge"}, c, n)
    ck(col == "GREEN", "null fault is judged GREEN (got %s)" % col)
    # 5. PLANTED: a hedge that times out and was never placed leaves 5 naked
    f = run([mkt_A(), mkt_B()], fault=hedge_status([-1]))
    col, why, extra, _l = judge({"judge": "hedge"}, c, f)
    ck(col == "RED" and naked(f, "KXAAA15M-RT") == 5.0 and extra > 0,
       "planted lost hedge is found: RED, 5 naked (%s)" % why)
    # 6. PLANTED lateness: a 429 then success is AMBER, not RED, not GREEN
    f2 = run([mkt_A(), mkt_B()], fault=hedge_status([429]))
    col2, why2, _e2, _l2 = judge({"judge": "hedge"}, c, f2)
    ck(col2 == "AMBER", "planted one-second delay is AMBER (got %s: %s)"
       % (col2, why2))
    # 7. no real network: the wire is the only sender and the base is DEMO
    ck(all(isinstance(x[5], int) for x in f["wire"].sent),
       "every order in every world went to the fake wire")
    print("SELF-TEST %s (%d failed)" % ("PASSED" if not fails else "FAILED",
                                        len(fails)))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- nothing ran")
    rows = run_all(a.only)
    order = {"RED": 0, "AMBER": 1, "GREEN": 2}
    rows.sort(key=lambda r: (order[r["verdict"]], -r["extra_loss_live_scale"]))
    print("\n%-16s %-6s %9s %9s  %s" % ("scenario", "", "world $", "x17.6 $", "why"))
    for r in rows:
        print("%-16s %-6s %9.2f %9.2f  %s" % (r["id"], r["verdict"],
              r["extra_loss_world"], r["extra_loss_live_scale"], r["why"]))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
