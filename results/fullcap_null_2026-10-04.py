"""NULL: the patched copy with --max-full-bets OFF makes byte-identical decisions to the
UNPATCHED 09-25 build on planted worlds, through each module's own _offline_trade_loop.
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

OLD = load('pin_old', r'C:\kals-live-0925\research\pinrun.py')
NEW = load('pin_new', r'C:\kals-live-0925b\research\pinrun.py')
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

def worlds(M, extra=None):
    out = {}
    SI = dict(SI_FLAGS, **(extra or {}))
    for lab, after, first, live in (
            ('0927 double bet, live', [(0.9535, 500.0)], [(0.960, 50.0)], True),
            ('0927 double bet, paper', [(0.9535, 500.0)], [(0.960, 50.0)], False),
            ('partial then topup, live', [(0.960, 500.0)], [(0.960, 2.0)], True),
            ('btc0923 same ask, live', [(0.860, 1000.0)], [(0.860, 1000.0)], True),
            ('cheaper touch, live', [(0.954, 3.0), (0.970, 500.0)], [(0.960, 50.0)], True)):
        m, tk, ex = si_world(M, after, first)
        r = M._offline_trade_loop([m], live=live, take=tk if live else None, run_s=2.5, tau0=18, flags=SI)
        out[lab] = dict(calls=ex["calls"], posts=r["posts"], recs=r["recs"], raised=r["raised"])
    # late add inside the boost window (paper)
    spk = lambda n, nb=0.05: {"tk": "KXS%d15M-SPK" % n, "series": "KXS%d15M" % n, "iid": "SPK%d" % n,
                              "strike": 100.0, "fair": (lambda t: 0.999), "book": (lambda t, _nb=nb: M._ob(0.94, _nb))}
    r = M._offline_trade_loop([spk(12)], run_s=6.0, tau0=12,
                              flags={"REBUY_LATE_TAU": 15, "REBUY_LATE_FRAC": 0.5, "MAX_PER_MARKET": 2,
                                     "IMPROVE_SCOPE": "market", "LATE_TAU": 10, "LATE_MULT": 1.5, "LATE_PIN": 0.9975})
    out['late add, paper'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    r = M._offline_trade_loop([spk(11, 0.04)], run_s=4.0, tau0=40,
                              flags={"EARLY_TAU_MAX": 45, "EARLY_FRAC": 0.333, "EARLY_MIN_PRICE": 0.95})
    out['early leg, paper'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    # a collapse that is hedged, live through the real pintake against a fake wire
    m = {"tk": "KXFC15M-FC", "series": "KXFC15M", "iid": "FC", "strike": 100.0,
         "fair": (lambda t: 0.10 if t >= 4 else 0.999), "book": (lambda t: M._ob(0.94, 0.05))}
    r = M._offline_trade_loop([m], live=True, reply=M._fill_all)
    out['hedged collapse, live'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    # two coins in one close, live
    r = M._offline_trade_loop([spk(21), spk(22, 0.03)], live=True, reply=M._fill_all, run_s=8.0, tau0=25,
                              flags={"MAX_PER_MARKET": 2, "IMPROVE_SCOPE": "market"})
    out['two coins, live'] = dict(posts=r["posts"], recs=r["recs"], raised=r["raised"])
    return out

import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    a = worlds(OLD)
    b = worlds(NEW, {'MAX_FULL_BETS': float(os.environ['FC_X'])} if os.environ.get('FC_X') else None)
same = 0
for k in a:
    ja = json.dumps(clean(a[k]), sort_keys=True, default=str)
    jb = json.dumps(clean(b[k]), sort_keys=True, default=str)
    nrec = len(a[k]['recs']); npost = len(a[k]['posts'])
    kinds = sorted(set(r.get('kind') for r in a[k]['recs']))
    if ja == jb:
        same += 1
        print('IDENTICAL  %-28s posts %2d recs %4d raised %s kinds %s' % (k, npost, nrec, a[k]['raised'], kinds[:12]))
    else:
        print('DIFFERENT  %-28s' % k)
        ra, rb = clean(a[k]['recs']), clean(b[k]['recs'])
        for i, (x, y) in enumerate(zip(ra, rb)):
            if x != y:
                print('   first diff at rec', i, json.dumps(x)[:300], '|', json.dumps(y)[:300]); break
print('NULL: %d of %d worlds byte-identical (flag OFF vs the unpatched 09-25 build)' % (same, len(a)))
sys.exit(0 if same == len(a) else 1)
