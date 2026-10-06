r"""v-bankfix-nodd NULL (2026-10-06): the patched copy C:\kals-live-0925d (v-bankmove port +
--no-drawdown-halt) makes byte-identical decisions to the code LIVE NOW (C:\kals-live-0925c,
09-25 build + v-fullcap + v-skiphype, code_sha 3776ff66b2fb), through each module's own
_offline_trade_loop and autosize_tick. The worlds come from results/skiphype_null_2026-10-05.py.
 (A) its 12 planted worlds at the LIVE settings on both sides (MAX_FULL_BETS 1.0, SKIP_COINS
     (KXHYPE15M,)): new copy flag OFF, and new copy with NO_DD_HALT ON (no world has a
     drawdown, so it must change nothing either).
 (B) three bank-path worlds (paper, size mirror off, so autosize_tick reads the bank as live
     does): $1000 bank no mark; $750 under an $850 mark (11.8%); $750 under a $1000 mark (25%).
     Flag OFF: all three identical (the 25% one halts on DRAWDOWN in both builds). Flag ON:
     the first two identical, the 25% one DIFFERS (positive control: it buys and logs
     drawdown_no_halt instead of halting).
 (C) autosize_tick over a bank series with NO outside money (only trading): identical
     records, marks and drawdowns. The coin-race shape (-$19.07 then +$20.00, nothing
     realised): with XFER_CONFIRM False the new copy reproduces the 09-25 classifier exactly
     (records equal once the new `transfers: []` field is dropped); with it ON (the deploy
     setting) both moves are `unexplained` and the mark stays -- the intended change.
Compared: every POST body (minus client_order_id) and every record (minus order ids), as JSON.
Run: python results/bankfix_null_2026-10-06.py   (exit 0 = PASS)"""
import importlib.util, json, sys, os

def load(name, path):
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.path.pop(0)
    return m

OLD = load('pin_old', r'C:\kals-live-0925c\research\pinrun.py')
NEW = load('pin_new', r'C:\kals-live-0925d\research\pinrun.py')
DROP = {'client_order_id', 'order_id'}

def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items() if k not in DROP}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x

def si_world(M, levels_after, first=((0.960, 50.0),), fill_px=None):
    ex = {"lv": list(first), "calls": [], "first": True}
    def _asks(lim=1.0):
        return [(p, q) for p, q in ex["lv"] if p <= lim + 1e-9 and q > 0]
    def _book(t):
        lv = _asks()
        return M._ob(round(lv[0][0] - 0.02, 4), round(1.0 - lv[0][0], 4), size=lv[0][1])
    def _take(base, pk, key_id, ticker, want, price, count, mce, exchange_index=0, **kw):
        ex["calls"].append((float(price), float(count)))
        left, cost = float(count), 0.0
        for i, (p, q) in enumerate(list(ex["lv"])):
            if p > float(price) + 1e-9 or left <= 1e-9:
                continue
            k = min(q, left); cost += k * p; left -= k; ex["lv"][i] = (p, q - k)
        got = float(count) - left
        avg = fill_px(len(ex["calls"])) if fill_px else (cost / got if got > 0 else None)
        if ex["first"]:
            ex["first"] = False
            ex["lv"] = list(levels_after)
        body = M.pintake.build_take(ticker, want, price, count, exchange_index)
        out = M.pintake.normalise(201, {"order": {"order_id": "si-%d" % len(ex["calls"]),
                                                   "status": "executed", "fill_count": round(got, 2),
                                                   "remaining_count": 0, "average_fill_price": avg}}, body, base)
        out["refused"] = []
        return out
    mkt = {"tk": "KXSI15M-SI", "series": "KXSI15M", "iid": "SI", "strike": 100.0,
           "fair": (lambda t: 0.999), "book": _book,
           "buyable": (lambda t, w, lim: sum(q for p, q in _asks(lim))),
           "rungs": (lambda t, s, lim: _asks(lim))}
    return mkt, _take, ex

SI_FLAGS = {"MAX_PER_MARKET": 2, "IMPROVE_SCOPE": "market", "IMPROVE_MAX": 0.01,
            "MIN_FILL_FRAC": 0.0, "SWEEP_DEPTH": True, "REBUY_LATE_TAU": 15, "REBUY_LATE_FRAC": 0.5}


class Kx:
    """A planted Kalshi account (the v-safety2 self-test's _KtEx, cut down):
    pos0 {ticker: (net, exposure $)} plus every order the bot really sent."""

    def __init__(self, M, pos0):
        self.M, self.pos0, self.orders = M, dict(pos0), []

    def reply(self, body, n):
        st, resp = self.M._fill_all(body, n)
        p = float(body["price"])
        self.orders.append({"client_order_id": body.get("client_order_id"),
                            "ticker": body.get("ticker"), "order_id": "ex-%d" % n,
                            "status": "executed", "fill_count_fp": body["count"],
                            "remaining_count_fp": "0.00",
                            "taker_fill_cost_dollars": "%.6f" % (float(body["count"]) * (p if body.get("side") == "bid" else 1.0 - p)),
                            "taker_fees_dollars": "0.000000",
                            "outcome_side": "yes" if body.get("side") == "bid" else "no"})
        return st, resp

    def portfolio(self, path, params, t):
        if path == "/portfolio/orders":
            return 200, {"orders": [o for o in self.orders if o["ticker"] == params.get("ticker")], "cursor": ""}
        if path == "/portfolio/positions":
            net = {k: [v[0], v[1]] for k, v in self.pos0.items()}
            for o in self.orders:
                s = 1.0 if o["outcome_side"] == "yes" else -1.0
                c = net.setdefault(o["ticker"], [0.0, 0.0])
                c[0] += s * float(o["fill_count_fp"])
                c[1] += float(o["taker_fill_cost_dollars"])
            return 200, {"market_positions": [{"ticker": k, "position_fp": "%.2f" % v[0],
                                               "market_exposure_dollars": "%.4f" % v[1]}
                                              for k, v in net.items() if abs(v[0]) > 1e-9],
                         "event_positions": [], "cursor": ""}
        return -1, "not modelled"


def worlds(M, extra=None):
    out = {}
    X = dict(extra or {})

    def fl(d=None):
        return dict(d or {}, **X)
    SI = fl(SI_FLAGS)
    for lab, after, first, live in (
            ('0927 double bet, live', [(0.9535, 500.0)], [(0.960, 50.0)], True),
            ('0927 double bet, paper', [(0.9535, 500.0)], [(0.960, 50.0)], False),
            ('partial then topup, live', [(0.960, 500.0)], [(0.960, 2.0)], True),
            ('btc0923 same ask, live', [(0.860, 1000.0)], [(0.860, 1000.0)], True),
            ('cheaper touch, live', [(0.954, 3.0), (0.970, 500.0)], [(0.960, 50.0)], True)):
        m, tk, ex = si_world(M, after, first)
        r = M._offline_trade_loop([m], live=live, take=tk if live else None, run_s=2.5, tau0=18, flags=SI)
        out[lab] = dict(calls=ex["calls"], posts=r["posts"], recs=r["recs"], raised=r["raised"])
    spk = lambda n, nb=0.05: {"tk": "KXS%d15M-SPK" % n, "series": "KXS%d15M" % n, "iid": "SPK%d" % n,
                              "strike": 100.0, "fair": (lambda t: 0.999), "book": (lambda t, _nb=nb: M._ob(0.94, _nb))}
    r = M._offline_trade_loop([spk(12)], run_s=6.0, tau0=12,
                              flags=fl({"REBUY_LATE_TAU": 15, "REBUY_LATE_FRAC": 0.5, "MAX_PER_MARKET": 2,
                                        "IMPROVE_SCOPE": "market", "LATE_TAU": 10, "LATE_MULT": 1.5, "LATE_PIN": 0.9975}))
    out['late add, paper'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    r = M._offline_trade_loop([spk(11, 0.04)], run_s=4.0, tau0=40,
                              flags=fl({"EARLY_TAU_MAX": 45, "EARLY_FRAC": 0.333, "EARLY_MIN_PRICE": 0.95}))
    out['early leg, paper'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    m = {"tk": "KXFC15M-FC", "series": "KXFC15M", "iid": "FC", "strike": 100.0,
         "fair": (lambda t: 0.10 if t >= 4 else 0.999), "book": (lambda t: M._ob(0.94, 0.05))}
    r = M._offline_trade_loop([m], live=True, reply=M._fill_all, flags=fl())
    out['hedged collapse, live'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    r = M._offline_trade_loop([spk(21), spk(22, 0.03)], live=True, reply=M._fill_all, run_s=8.0, tau0=25,
                              flags=fl({"MAX_PER_MARKET": 2, "IMPROVE_SCOPE": "market"}))
    out['two coins, live'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    # v-skiphype worlds, REAL series names
    coin = lambda s, i, nb=0.05, col=None, early=0.999: {
        "tk": s + "-SK", "series": s, "iid": i, "strike": 100.0,
        "fair": (lambda t: 0.10 if (col is not None and t >= col) else early),
        "book": (lambda t, _nb=nb: M._ob(0.94, _nb))}
    r = M._offline_trade_loop([coin("KXBTC15M", "B"), coin("KXHYPE15M", "H", 0.04)], live=True,
                              reply=M._fill_all, run_s=8.0, tau0=25,
                              flags=fl({"MAX_PER_MARKET": 2, "IMPROVE_SCOPE": "market"}))
    out['BTC+HYPE, live [HYPE]'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    r = M._offline_trade_loop([coin("KXBTC15M", "B"), coin("KXHYPE15M", "H", 0.04),
                               coin("KXETH15M", "E", 0.03, col=5)], run_s=10.0, tau0=25, flags=fl())
    out['BTC+HYPE+ETH, paper [HYPE]'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    kx = Kx(M, {"KXHYPE15M-SK": (5.0, 4.75)})
    r = M._offline_trade_loop([coin("KXHYPE15M", "H", col=8, early=0.5), coin("KXBTC15M", "B")],
                              live=True, reply=kx.reply, run_s=70.0, tau0=30,
                              portfolio=kx.portfolio, result={"KXHYPE15M-SK": "no", "KXBTC15M-SK": "yes"},
                              flags=fl())
    out['HYPE held at restart, live [HYPE]'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    return out


import contextlib, io, tempfile
LIVE = {'MAX_FULL_BETS': 1.0, 'SKIP_COINS': ('KXHYPE15M',)}


def jd(x):
    return json.dumps(clean(x), sort_keys=True, default=str)


def bank_worlds(M, extra):
    """Paper, size mirror off: autosize_tick reads the (planted) bank as a live bot does.
    The live build has no `hwm0` argument, so its mark is planted by wrapping write_hwm's
    FIRST call (the loop's first sizing tick) -- the same file, the same moment."""
    out = {}
    mk = lambda: [{"tk": "KXBTC15M-ND", "series": "KXBTC15M", "iid": "NDB", "strike": 100.0,
                   "fair": (lambda t: 0.999), "book": (lambda t: M._ob(0.94, 0.05, size=500.0))}]
    for lab, bank, hw in (('bank 1000, no mark', 1000.0, None),
                          ('bank 750 under 850 (11.8%)', 750.0, 850.0),
                          ('bank 750 under 1000 (25%) [DD]', 750.0, 1000.0)):
        real = M.write_hwm
        done = {'n': 0}

        def _w(b, path=None, _hw=hw, _real=real):
            if done['n'] == 0 and _hw is not None:
                done['n'] = 1
                _real(_hw, path)
            return _real(b, path)
        M.write_hwm = _w
        try:
            r = M._offline_trade_loop(mk(), bank=bank, flags=dict(extra, SIZE_MIRROR_ON=False))
        finally:
            M.write_hwm = real
        out[lab] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    return out


def tick_series(M, banks, realised, confirm=None):
    d = tempfile.mkdtemp(prefix='bfnull-')
    h = os.path.join(d, 'hwm.json')
    M.write_hwm(1093.25, h)
    got, st, marks = [], {}, []

    class A(object):
        live = False
        auto_size = True
        size = 20
        max_positions = 3
        loss_abort = -60.0
    sv = dict(M.pintake.LEDGER)
    lim = (M.pintake.LOSS_ABORT, M.pintake.MAX_RUN_STAKE, M.pintake.MAX_TAKE_COUNT, M.pintake.HARD_MAX)
    sz = M.SIZE
    xc = getattr(M, 'XFER_CONFIRM', None)
    try:
        if confirm is not None:
            M.XFER_CONFIRM = confirm
        for i, (b, rl) in enumerate(zip(banks, realised)):
            M.pintake.LEDGER['realised'] = rl
            kw = dict(rec=lambda k, **kw: got.append((k, kw)), now=1e9 + 1000.0 * i,
                      bank_reader=(lambda _b=b: _b), hwm_path=h)
            if hasattr(M, 'XFER_CONFIRM'):
                kw['xfer_get'] = lambda p, q: (200, {"deposits": [], "withdrawals": [], "transfers": []})
            M.autosize_tick(st, A(), {}, **kw)
            marks.append(M.read_hwm(h))
    finally:
        M.pintake.LEDGER.clear()
        M.pintake.LEDGER.update(sv)
        (M.pintake.LOSS_ABORT, M.pintake.MAX_RUN_STAKE, M.pintake.MAX_TAKE_COUNT, M.pintake.HARD_MAX) = lim
        M.SIZE = sz
        if xc is not None:
            M.XFER_CONFIRM = xc
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
        os.rmdir(d)
    return dict(recs=[(k, {x: y for x, y in kw.items() if x != 'transfers'}) for k, kw in got],
                marks=marks, dd=st.get('drawdown'), bank=st.get('bank'), resets=st.get('loss_resets'))


ok = True
with contextlib.redirect_stdout(io.StringIO()):
    a = worlds(OLD, LIVE)
    b = worlds(NEW, LIVE)
    b1 = worlds(NEW, dict(LIVE, NO_DD_HALT=True))
    ba = bank_worlds(OLD, LIVE)
    bb = bank_worlds(NEW, LIVE)
    bb1 = bank_worlds(NEW, dict(LIVE, NO_DD_HALT=True))
for tag, bx in (('flag OFF', b), ('NO_DD_HALT ON', b1)):
    same = sum(1 for k in a if jd(a[k]) == jd(bx[k]))
    print('(A) %-14s %d of %d planted worlds byte-identical to the live 0925c build' % (tag, same, len(a)))
    for k in a:
        if jd(a[k]) != jd(bx[k]):
            print('    DIFFERENT', k)
    ok &= same == len(a)
for k in ba:
    s0 = jd(ba[k]) == jd(bb[k])
    s1 = jd(ba[k]) == jd(bb1[k])
    halts = lambda w: [str(r.get('why'))[:24] for r in w[k]['recs'] if r.get('kind') == 'halt']
    sig = lambda w: sum(1 for r in w[k]['recs'] if r.get('kind') == 'signal')
    print('(B) %-31s flag OFF %s | flag ON %s  (live: halts %s, buys %d; new ON: halts %s, buys %d, drawdown_no_halt %d)'
          % (k, 'IDENTICAL' if s0 else 'DIFFERENT', 'IDENTICAL' if s1 else 'DIFFERENT',
             halts(ba), sig(ba), halts(bb1), sig(bb1),
             sum(1 for r in bb1[k]['recs'] if r.get('kind') == 'drawdown_no_halt')))
    ok &= s0 and (s1 != ('[DD]' in k))
banks = (1020.11, 1031.40, 1009.52, 1012.00, 1100.00)
real = (0.0, 11.29, -10.59, -8.11, 79.89)
t_old = tick_series(OLD, banks, real)
t_new = tick_series(NEW, banks, real)
s = jd(t_old) == jd(t_new)
print('(C) trading-only bank series: %s (marks %s)' % ('IDENTICAL' if s else 'DIFFERENT', t_new['marks']))
ok &= s
race = (1020.11, 1001.04, 1021.04)
t_old = tick_series(OLD, race, (0.0, 0.0, 0.0))
t_new0 = tick_series(NEW, race, (0.0, 0.0, 0.0), confirm=False)
t_new1 = tick_series(NEW, race, (0.0, 0.0, 0.0), confirm=True)
s = jd(t_old) == jd(t_new0)
print('(C) race shape, XFER_CONFIRM off: %s to the live build (marks %s, %s)'
      % ('IDENTICAL' if s else 'DIFFERENT', t_old['marks'],
         [(k, kw.get('move'), kw.get('amount')) for k, kw in t_old['recs'] if k != 'autosize']))
print('(C) race shape, XFER_CONFIRM ON (the deploy setting): marks %s, records %s  <- the intended change'
      % (t_new1['marks'], [(k, kw.get('amount')) for k, kw in t_new1['recs'] if k != 'autosize']))
ok &= s and t_new1['marks'] == [1093.25, 1093.25, 1093.25]
print('NULL %s' % ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
