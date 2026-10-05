r"""v-skiphype NULL (2026-10-05): the patched copy C:\kals-live-0925c with --skip-coin OFF
makes byte-identical decisions to the code LIVE NOW (C:\kals-live-0925b, 09-25 build +
v-fullcap, code_sha 269958db6d68) on planted worlds, through each module's own
_offline_trade_loop. The 9 v-fullcap worlds (results/fullcap_null_2026-10-04.py) plus 3 with
real series names: BTC+HYPE both buyable (live), BTC+HYPE+ETH (paper), and 5 HYPE YES held on
Kalshi from before a restart that collapses and settles NO (live, v-safety2 adoption).
SK=1 runs the new copy WITH --skip-coin KXHYPE15M (positive control: only the HYPE worlds may
differ). Every world also runs at MAX_FULL_BETS 1.0, the live setting, when FC_X=1.0.
Compared: every POST body (minus the random client_order_id) and every record (minus
client_order_id / order_id), in order, as JSON."""
import importlib.util, json, sys, os

def load(name, path):
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.path.pop(0)
    return m

OLD = load('pin_old', r'C:\kals-live-0925b\research\pinrun.py')
NEW = load('pin_new', r'C:\kals-live-0925c\research\pinrun.py')
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


import contextlib, io
FC = {'MAX_FULL_BETS': float(os.environ['FC_X'])} if os.environ.get('FC_X') else {}
SK = {'SKIP_COINS': ('KXHYPE15M',)} if os.environ.get('SK') else {}
with contextlib.redirect_stdout(io.StringIO()):
    a = worlds(OLD, FC)
    b = worlds(NEW, dict(FC, **SK))
same = 0
for k in a:
    ja = json.dumps(clean(a[k]), sort_keys=True, default=str)
    jb = json.dumps(clean(b[k]), sort_keys=True, default=str)
    nrec = len(a[k]['recs']); npost = len(a[k]['posts'])
    kinds = sorted(set(r.get('kind') for r in a[k]['recs']))
    hp = lambda w: sum(1 for p in w[k]['posts'] if 'HYPE' in str(p.get('ticker')))
    hedge = lambda w: [(p.get('ticker'), p.get('count')) for p in w[k]['posts'] if p.get('side') == 'ask']
    if ja == jb:
        same += 1
        print('IDENTICAL  %-34s posts %2d recs %4d raised %s' % (k, npost, nrec, a[k]['raised']))
    else:
        print('DIFFERENT  %-34s posts %d -> %d, HYPE posts %d -> %d, hedges %s -> %s, raised %s -> %s'
              % (k, npost, len(b[k]['posts']), hp(a), hp(b), hedge(a), hedge(b), a[k]['raised'], b[k]['raised']))
        ra, rb = clean(a[k]['recs']), clean(b[k]['recs'])
        for i, (x, y) in enumerate(zip(ra, rb)):
            if x != y:
                print('   first diff at rec', i, json.dumps(x)[:240], '|', json.dumps(y)[:240]); break
print('%s: %d of %d worlds byte-identical (new copy %s vs the live 0925b build; MAX_FULL_BETS %s)'
      % ('POSITIVE CONTROL' if SK else 'NULL', same, len(a),
         'WITH --skip-coin KXHYPE15M' if SK else 'flag OFF', FC.get('MAX_FULL_BETS', 0.0)))
if SK:
    bad = [k for k in a if '[HYPE]' not in k and
           json.dumps(clean(a[k]), sort_keys=True, default=str) != json.dumps(clean(b[k]), sort_keys=True, default=str)]
    print('non-HYPE worlds that differ: %s' % (bad or 'none'))
    sys.exit(0 if not bad else 1)
sys.exit(0 if same == len(a) else 1)
