"""test_fast2.py -- v-tg-fast2 (2026-10-31): every phone command made cheaper without changing one answer.

The operator: "Speed up every command as much as possible." The rules this file enforces:

  1. botdata.filefold.fold gives exactly what folding every line of the file NOW gives -- unchanged, appended in many
     small steps (a half-written last line, a split \\r\\n, a split UTF-8 character), shrunk, rewritten at the same size
     -- hands each caller its own copy, empties its memo when the bytes change, and keeps at most MAX_ENTRIES;
  2. bars.load_run (/bars) and pinlab.summarise_log (/brief) on top of it give the old full read's answer;
  3. bars.ep, pindesk.parse_t and pindesk.et_day give the old strptime / downtime answers;
  4. botdata.dirlist.glob is glob.glob outside a tap and inside one (listing order, hidden names, folder wildcards);
  5. report._money_block and pots.pot_context, remembered per cache version (kalshi.version), give the raw answers,
     each caller its own block, nothing shared changed by a caller, and nothing remembered for an unversioned dict;
  6. phone.shared.markets_from, remembered per ledger file version and sides, gives markets_from_rows' answer, a copy.

Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_fast2.py      (or all of them: research\\botstats.py --selftest)
"""
import calendar
import glob
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run, sandbox                                   # noqa: E402

from botdata import dirlist, filefold, kalshi, pots, report         # noqa: E402

NOW = float(calendar.timegm((2026, 10, 30, 16, 30, 0)))


def _write(path, raw, mtime=None):
    with open(path, "wb") as fh:
        fh.write(raw)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _full(path, new, feed):
    """The reference: fold every line of a text-mode read (what fold must equal)."""
    st = new()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            feed(st, line)
    return st


def _lines_state():
    return {"lines": [], "n": 0}


def _lines_feed(st, line):
    st["lines"].append(line)
    st["n"] += 1


def _lines_copy(st):
    return {"lines": list(st["lines"]), "n": st["n"]}


# ---- 1. filefold ----------------------------------------------------------------------------------------------------
def test_fold_matches_a_full_read_as_a_log_grows():
    rnd = random.Random(7)
    body = []
    for i in range(400):
        rec = {"t": "2026-10-30T12:%02d:%02dZ" % (i // 60 % 60, i % 60), "kind": rnd.choice(["loop", "settled", "x"]),
               "s": "caf\u00e9 \u2192 %d" % i}
        body.append(json.dumps(rec, ensure_ascii=False))
    raw = ("\r\n".join(body[:150]) + "\r\n" + "\n".join(body[150:]) + "\n").encode("utf-8")
    raw += b"\xff\xfe broken bytes\n\rlone cr\n"
    with sandbox() as td:
        p = os.path.join(td, "x.jsonl")
        cuts = sorted(set(rnd.sample(range(1, len(raw)), 120))) + [len(raw)]
        bad = 0
        for k in cuts:
            _write(p, raw[:k])
            for _ in range(2):                                  # a grown file, then the same file unchanged
                got, e = filefold.fold(p, "t", _lines_state, _lines_feed, _lines_copy)
                if got != _full(p, _lines_state, _lines_feed):
                    bad += 1
        ck(bad == 0, "fold == a full text-mode read at %d cut points (half lines, split \\r\\n and UTF-8), each twice"
           % len(cuts))
        got["lines"].append("caller's own")
        again, _e = filefold.fold(p, "t", _lines_state, _lines_feed, _lines_copy)
        ck(again == _full(p, _lines_state, _lines_feed), "a caller changing its answer does not change the next one")
        e["memo"]["hi"] = 1
        _same, e2 = filefold.fold(p, "t", _lines_state, _lines_feed, _lines_copy)
        ck(e2["memo"] == {"hi": 1}, "an unchanged file keeps the caller's memo")
        st0 = os.stat(p)
        _write(p, raw.replace(b"settled", b"settlex", 1), st0.st_mtime + 5)          # same size, other bytes
        got, e3 = filefold.fold(p, "t", _lines_state, _lines_feed, _lines_copy)
        ck(got == _full(p, _lines_state, _lines_feed) and e3["memo"] == {}, "a same-size rewrite is read afresh")
        _write(p, raw[:500])
        got, _e = filefold.fold(p, "t", _lines_state, _lines_feed, _lines_copy)
        ck(got == _full(p, _lines_state, _lines_feed), "a shrunk file is read afresh")
        os.remove(p)
        ck(filefold.fold(p, "t", _lines_state, _lines_feed, _lines_copy) == (None, None), "a missing file: (None, None)")


def test_fold_memory_is_bounded():
    with sandbox() as td:
        old = filefold.MAX_ENTRIES
        filefold.MAX_ENTRIES = 5
        try:
            for i in range(12):
                p = os.path.join(td, "f%d.jsonl" % i)
                _write(p, b"a\nb\n")
                filefold.fold(p, "t", _lines_state, _lines_feed, _lines_copy)
            ck(len(filefold._E) <= 5, "at most MAX_ENTRIES files are remembered (%d)" % len(filefold._E))
        finally:
            filefold.MAX_ENTRIES = old


# ---- 2. the readers on top of it ------------------------------------------------------------------------------------
def _load_run_reference(path, since_e=None, keep=(), count=None):
    """bars.load_run before v-tg-fast2, verbatim (one full read of the file)."""
    import bars
    needles = {k: '"kind": "%s"' % k for k in set(keep) | {"start", "settled"}}
    count = count or {}
    out = dict(path=path, start=None, lo=None, hi=None, settled={}, kept=[], counts={k: 0 for k in count})
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            if out["lo"] is None:
                try:
                    d0 = json.loads(line)
                except ValueError:
                    d0 = None
                if isinstance(d0, dict) and d0.get("t"):
                    out["lo"] = _strptime_epoch(d0["t"])
            for name, needle in count.items():
                if needle in line:
                    out["counts"][name] += 1
            if not any(n in line for n in needles.values()):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            k = d.get("kind")
            if k == "start":
                if out["start"] is None:
                    out["start"] = d
            elif k == "settled":
                tk = d.get("ticker")
                t = _strptime_epoch(d.get("t"))
                if tk and d.get("pnl_c") is not None and t is not None and (since_e is None or t >= since_e):
                    out["settled"][tk] = out["settled"].get(tk, 0.0) + bars._f(d["pnl_c"]) / 100.0
            if k in keep:
                out["kept"].append(d)
    out["hi"] = bars._tail_t(path)
    if out["lo"] is None and out["start"]:
        out["lo"] = _strptime_epoch(out["start"].get("t"))
    return out


def _strptime_epoch(t):
    try:
        return calendar.timegm(time.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def _pin_log(rnd, n):
    out = [{"t": "2026-10-30T10:00:00Z", "kind": "start", "size": 20, "pin": 0.995}]
    for i in range(n):
        t = "2026-10-30T%02d:%02d:%02d.123Z" % (10 + i // 3600, i // 60 % 60, i % 60)
        k = rnd.choice(["universe", "loop", "signal", "order", "settled", "refused", "settled"])
        r = {"t": t, "kind": k, "ticker": "KXBTC15M-26OCT30%04d-00" % (i % 97)}
        if k == "settled":
            r["pnl_c"] = rnd.choice([12.5, -98.0, 3.0, None, "7"])
        if k == "refused" and rnd.random() < 0.3:
            r["gate"] = "fresh_level"
        out.append(r)
    return "".join(json.dumps(r) + "\n" for r in out).encode("utf-8")


def test_bars_load_run_is_the_old_full_read():
    import bars
    rnd = random.Random(11)
    raw = _pin_log(rnd, 2500)
    specs = [((), None), (("signal", "order"), None), (("signal",), {"fresh_level": '"gate": "fresh_level"'})]
    since = calendar.timegm((2026, 10, 30, 10, 20, 0))
    with sandbox() as td:
        p = os.path.join(td, "pinrun-paper-20261030T100000Z.jsonl")
        bad = 0
        cuts = sorted(rnd.sample(range(1, len(raw)), 40)) + [len(raw)]
        for k in cuts:
            _write(p, raw[:k])
            for keep, cnt in specs:
                for _ in range(2):
                    a = _load_run_reference(p, since, keep, cnt)
                    b = bars.load_run(p, since, keep, cnt)
                    bad += a != b
        ck(bad == 0, "bars.load_run == the old full read over %d growth steps x 3 specs, each twice" % len(cuts))
        b = bars.load_run(p, since, ("signal",), None)
        b["name"] = "arm-x"
        b["settled"]["zz"] = 1.0
        b["kept"].append({})
        ck(bars.load_run(p, since, ("signal",), None) == _load_run_reference(p, since, ("signal",), None),
           "arm_groups naming a run (x['name'] = ...) never reaches the remembered answer")


def test_pinlab_summarise_log_is_the_old_full_read():
    import pinlab
    rnd = random.Random(3)

    def reference(path):
        n = won = lost = 0
        net = 0.0
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            return None
        with fh:
            for line in fh:
                if '"settled"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("kind") != "settled":
                    continue
                v = pinlab._settled_pnl(r)
                if v is pinlab._NOPOS:
                    continue
                n += 1
                net += v
                if v < 0:
                    lost += 1
                else:
                    won += 1
        return {"settled": n, "won": won, "lost": lost, "net": net}
    recs = []
    for i in range(1500):
        k = rnd.choice(["settled", "loop", "settled"])
        r = {"t": "2026-10-30T10:%02d:%02dZ" % (i // 60 % 60, i % 60), "kind": k}
        if k == "settled":
            r.update(rnd.choice([{"pnl_c": rnd.uniform(-90, 5)}, {"pnl": rnd.uniform(-3, 1), "positions": [1]},
                                 {"pnl": 0.5, "positions": []}, {}]))
        recs.append(r)
    raw = "".join(json.dumps(r) + "\n" for r in recs).encode("utf-8")
    with sandbox() as td:
        p = os.path.join(td, "pinrun-paper-20261030T100000Z.jsonl")
        bad = 0
        for k in sorted(rnd.sample(range(1, len(raw)), 30)) + [len(raw)]:
            _write(p, raw[:k])
            bad += pinlab.summarise_log(p) != reference(p)
            bad += pinlab.summarise_log(p) != reference(p)
        ck(bad == 0, "pinlab.summarise_log == the old full read as the log grows")
        ck(pinlab.summarise_log(os.path.join(td, "nope.jsonl")) is None, "a missing log is None")
        ck(pinlab.summarise_log([p, p])["settled"] == 2 * reference(p)["settled"], "a list of logs still adds up")


# ---- 3. stamps and ET days ------------------------------------------------------------------------------------------
def test_stamp_and_day_readers():
    import bars
    import pindesk
    from downtime import et_offset
    rnd = random.Random(9)
    cases = [None, 12, 3.5, "", "x", "2026-10-31T09:00:13Z", "2026-10-31T09:00:13.773Z", "2026-02-29T00:00:00",
             "2024-02-29T00:00:00Z", "2026-09-31T00:00:00", "2026-10-31T23:59:60", "2026-10-31T23:59:61",
             "2026-13-01T00:00:00", "0999-01-01T00:00:00", "2026-1-01T00:00:00", "\uff12\uff10\uff12\uff16-10-31T09:00:13"]
    for _ in range(5000):
        cases.append("%04d-%02d-%02dT%02d:%02d:%02d%s" % (rnd.choice([1900, 2026, 2099]), rnd.randint(0, 13),
                     rnd.randint(0, 32), rnd.randint(0, 25), rnd.randint(0, 61), rnd.randint(0, 62),
                     rnd.choice(["", "Z", ".5Z"])))
    bad = [c for c in cases if bars.ep(c) != _strptime_epoch(c) or pindesk.parse_t(c) != _strptime_epoch(c)]
    ck(not bad, "bars.ep and pindesk.parse_t == the old strptime reader on %d inputs%s" % (len(cases), bad[:3] or ""))
    ck(all(type(bars.ep(c)) is int for c in cases if bars.ep(c) is not None), "bars.ep still answers an int")
    old = lambda e: time.strftime("%Y-%m-%d", time.gmtime(e + et_offset(e)))          # noqa: E731
    es = [calendar.timegm((2026, 11, 1, 6, 0, 0)) + d for d in range(-5, 6)] + \
         [calendar.timegm((2026, 3, 8, 7, 0, 0)) + d for d in range(-5, 6)] + \
         [rnd.uniform(1.7e9, 1.9e9) for _ in range(5000)] + [int(rnd.uniform(1.7e9, 1.9e9)) for _ in range(500)]
    ck(all(pindesk.et_day(e) == old(e) for e in es), "pindesk.et_day == the old arithmetic (%d moments, both clock "
       "changes)" % len(es))


# ---- 4. dirlist -----------------------------------------------------------------------------------------------------
def test_dirlist_is_glob():
    with sandbox() as td:
        for n in ("pinrun-live-1.jsonl", "pinrun-live-2.jsonl", ".pinrun-live-h.jsonl", "PINRUN-LIVE-3.JSONL",
                  "pinrun-paper-1.jsonl", "other.txt"):
            _write(os.path.join(td, n), b"x\n")
        os.makedirs(os.path.join(td, "sub"))
        _write(os.path.join(td, "sub", "pinrun-live-9.jsonl"), b"x\n")
        pats = [os.path.join(td, p) for p in ("pinrun-live-*.jsonl", ".pinrun-*", "*", "*.JSONL", "pinrun-[lp]*",
                                              "nothing-*", "other.txt", "*/pinrun-live-*.jsonl", "**")]
        ck(all(dirlist.glob(p) == glob.glob(p) for p in pats), "outside a tap: glob.glob itself")
        with dirlist.tap():
            ck(all(dirlist.glob(p) == glob.glob(p) for p in pats), "inside a tap: the same names, same order")
            ck(all(dirlist.glob(p) == glob.glob(p) for p in pats), "... twice, from the tap's listing")
            _write(os.path.join(td, "pinrun-live-4.jsonl"), b"x\n")
            st = os.stat(td)
            os.utime(td, ns=(st.st_atime_ns, st.st_mtime_ns + 10 ** 7))
            p = os.path.join(td, "pinrun-live-*.jsonl")
            ck(dirlist.glob(p) == glob.glob(p), "a new file (the folder's time moved) is seen inside the tap")
        ck(getattr(dirlist._LOCAL, "dirs", None) is None, "the tap's listings are dropped when it ends")


# ---- 5. per cache version -------------------------------------------------------------------------------------------
def _row(tk, st, res, yn=0.0, yc=0.0, nn=0.0, nc=0.0, fee=0.0):
    return {"ticker": tk, "settled_time": st, "market_result": res, "value": {"yes": 100, "no": 0}.get(res),
            "event_ticker": tk[:20], "yes_count_fp": "%.2f" % yn, "yes_total_cost_dollars": "%.6f" % yc,
            "no_count_fp": "%.2f" % nn, "no_total_cost_dollars": "%.6f" % nc, "fee_cost": "%.6f" % fee,
            "revenue": 0, "exchange_index": 2}


def _cache():
    rows0 = [_row("KXBTC15M-26OCT301145-45", "2026-10-30T15:45:05Z", "no", nn=50, nc=49.0, fee=0.1),
             _row("KXETH15M-26OCT301100-00", "2026-10-30T15:00:05Z", "yes", yn=40, yc=38.8, nn=40, nc=12.0, fee=0.5),
             _row("KXXRP15M-26OCT290000-00", "2026-10-29T04:00:05Z", "yes", yn=10, yc=9.7, fee=0.02)]
    rows1 = [_row("KXNEAR15M-26OCT301130-30", "2026-10-30T15:30:05Z", "yes", yn=118, yc=115.64)]
    sub = lambda rows, bal: {"fetched": NOW - 60, "tried": NOW - 60, "complete": True,      # noqa: E731
                             "rows": {r["ticker"]: r for r in rows}, "positions": [], "pos_t": NOW - 60,
                             "balance": bal, "bal_t": NOW - 60}
    return {"v": 1, "subs": {"0": sub(rows0, 2400.0), "1": sub(rows1, 830.0)}, "procs": None,
            "ledgers": {"fetched": NOW - 60, "tried": NOW - 60, "transfers": [], "deposits": [], "withdrawals": [],
                        "subaccount_balances": []}}


def test_money_blocks_per_cache_version():
    from botdata import tables
    with sandbox():
        today = "2026-10-30"
        raw_c = _cache()
        c = json.loads(json.dumps(raw_c))
        names = tuple(tables.BOTS) + ("other",)
        want = {n: report._money_block_raw(c, n, today) for n in names}
        ck(kalshi.version(c) is None and all(report._money_block(c, n, today) == want[n] for n in names)
           and not report._BLOCKS and not pots._CTX, "an unversioned dict: the raw answer, nothing remembered")
        kalshi.set_version(c, ("v1",))
        ctx = pots.pot_context(c, today)
        ck(ctx is pots.pot_context(c, today) and ctx == pots._pot_context_raw(c, today),
           "pot_context: built once per (version, day), the raw answer")
        snap = json.dumps(want, sort_keys=True, default=str)
        for n in names:
            a = report._money_block(c, n, today, ctx)
            ck(a == want[n] and a is not report._money_block(c, n, today), "%s: the raw block, a fresh dict each" % n)
            a.pop("markets", None)
            a["pot_shared_with"] = ["x"]
            for k, v in a.items():
                if isinstance(v, list):
                    v.append("caller's")
        ck(json.dumps({n: report._money_block(c, n, today) for n in names}, sort_keys=True, default=str) == snap,
           "what a caller changes in its block (pop, lists) never reaches the next caller")
        c2 = json.loads(json.dumps(raw_c))
        kalshi.set_version(c2, ("v1",))
        ck(all(report._money_block(c2, n, today) == want[n] for n in names), "another dict of the same version: same")
        c3 = json.loads(json.dumps(raw_c))
        c3["subs"]["0"]["rows"].pop("KXBTC15M-26OCT301145-45")
        kalshi.set_version(c3, ("v2",))
        ck(report._money_block(c3, "pin", today) == report._money_block_raw(c3, "pin", today)
           and report._money_block(c3, "pin", today) != want["pin"], "a new version is worked out again")
        other_ctx = pots._pot_context_raw(c, today)
        ck(report._money_block(c, "pin", today, other_ctx) == report._money_block_raw(c, "pin", today, other_ctx),
           "a context that is not the remembered one: the raw path")
        for i in range(20):
            kalshi.set_version(json.loads(json.dumps(raw_c)), ("v%d" % i,))
        ck(len(kalshi._VER) <= kalshi._VER_MAX, "the version table is bounded")


def test_load_sets_the_version():
    with sandbox():
        kalshi.set_readonly(True)
        try:
            c0 = _cache()
            with open(kalshi.cache_path(), "w", encoding="utf-8") as fh:
                json.dump(c0, fh)
            c, _rows, _ok = report._load(NOW, None, [])
            ck(kalshi.version(c) is not None and kalshi.version(c) == kalshi.served_key(),
               "report._load: a dict read and not refreshed carries the file's version")
            os.remove(kalshi.cache_path())
            c, _rows, _ok = report._load(NOW, None, [])
            ck(kalshi.version(c) is None, "no cache file: no version (nothing remembered for the default)")
        finally:
            kalshi.set_readonly(False)


# ---- 6. markets_from ------------------------------------------------------------------------------------------------
def test_markets_from_per_ledger_version():
    from phone import shared as S
    with sandbox() as td:
        p = os.path.join(td, "kalshi_ledger.json")
        rows = {r["ticker"]: r for r in _cache()["subs"]["0"]["rows"].values()}
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"settlements": rows}, fh)
        raw = S.raw_ledger(p)
        ck(len(raw) == 3, "the planted ledger is read (%d rows)" % len(raw))
        sides = {"KXETH15M-26OCT301100-00": "yes"}
        want = S.markets_from_rows(raw, sides)
        a = S.markets_from(raw, sides)
        ck(a == want and S.markets_from(raw, sides) == want, "markets_from == markets_from_rows, twice")
        a["KXETH15M-26OCT301100-00"]["pnl"] = 999
        a.pop("KXBTC15M-26OCT301145-45")
        ck(S.markets_from(raw, sides) == want, "a caller's changes never reach the next answer")
        ck(S.markets_from(raw, {"KXETH15M-26OCT301100-00": "no"}) == S.markets_from_rows(raw, {
            "KXETH15M-26OCT301100-00": "no"}), "other sides: worked out again")
        ck(S.markets_from(list(raw), sides) == want, "rows that are not raw_ledger's own list: the plain answer")


if __name__ == "__main__":
    sys.exit(run(globals(), "test_fast2"))
