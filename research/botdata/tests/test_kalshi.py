"""test_kalshi.py -- botdata/kalshi.py's lock (concurrent callers make ONE Kalshi pass and one write) and readonly mode
(no request, no write).

v-tg-rebuild step 7 (2026-10-30). Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_kalshi.py
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run, sandbox                                   # noqa: E402

import botstats as bs                                               # noqa: E402
from botdata import kalshi, report                                  # noqa: E402

NOW = 1790000000.0


def _getter(asked, delay=0.0):
    """A Kalshi with nothing settled, no positions, $0 everywhere; each request recorded, each slowed by `delay`."""
    def get(path, q):
        asked.append((path, dict(q or {})))
        if delay:
            time.sleep(delay)
        if path == "/portfolio/settlements":
            return 200, {"settlements": [], "cursor": ""}
        if path == "/portfolio/positions":
            return 200, {"market_positions": [], "cursor": ""}
        if path == "/portfolio/subaccounts/balances":
            return 200, {"subaccount_balances": []}
        if path in kalshi.LEDGER_PATHS:
            return 200, {path.rsplit("/", 1)[-1]: [], "cursor": ""}
        return 200, {"balance": 0, "balance_dollars": "0.0000"}
    return get


def test_concurrent_callers_make_one_pass():
    with sandbox():
        asked = []
        get = _getter(asked, delay=0.01)                       # a pass takes ~0.3 s: the threads overlap
        writes = []
        saved = kalshi.save_cache

        def counting_save(c):
            writes.append(1)
            return saved(c)
        kalshi.save_cache = counting_save
        try:
            out, errs = [], []

            def call(k):
                try:
                    if k % 2:
                        out.append(bs.all_bots(now=NOW, getter=get, procs=[]))
                    else:
                        out.append(bs.pot_settlements(now=NOW, getter=get))
                except Exception as e:                          # noqa: BLE001
                    errs.append(repr(e))
            ths = [threading.Thread(target=call, args=(k,)) for k in range(4)]
            for t in ths:
                t.start()
            for t in ths:
                t.join(60)
            one_pass = len(bs.SUBS) * 3 + len(kalshi.LEDGERS)
            ck(not errs and len(out) == 4 and len(asked) == one_pass and len(writes) == 1,
               "four callers at once (all_bots x2, pot_settlements x2): ONE Kalshi pass (%d requests, %d expected) and "
               "ONE cache write (%d); errors %s" % (len(asked), one_pass, len(writes), errs))
        finally:
            kalshi.save_cache = saved


def test_readonly_asks_nothing_and_writes_nothing():
    with sandbox() as td:
        asked = []
        get = _getter(asked)
        bs.all_bots(now=NOW, getter=get, procs=[])              # a normal read fills the cache
        n0 = len(asked)
        p = kalshi.cache_path()
        m0 = os.path.getmtime(p)
        old = kalshi.set_readonly(True)
        try:
            a = bs.all_bots(now=NOW + 3600, getter=get, procs=[])
            rows, why = bs.pot_settlements(now=NOW + 3600, getter=get)
            c, changed = kalshi.load(NOW + 7200, get)
            ck(len(asked) == n0 and not changed and os.path.getmtime(p) == m0 and a["bots"]["pin"]["money"]["ok"]
               and sorted(rows) == sorted(bs.SUBS) and why == {},
               "readonly: an hour later (past REFRESH_S) all_bots / pot_settlements / load answer from the cache as it "
               "is -- no Kalshi request, no cache write")

            def boom(path, q):
                raise AssertionError("readonly must never ask Kalshi")
            report._load(NOW + 9999, boom, [])
            ck(True, "readonly: the getter is never even called")
        finally:
            kalshi.set_readonly(old)
        ck(not kalshi.is_readonly() and os.path.dirname(p) == td, "readonly switched back off")
        kalshi.load(NOW + 7200, get)
        ck(len(asked) > n0, "and the next normal read asks Kalshi again")


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_kalshi"))
