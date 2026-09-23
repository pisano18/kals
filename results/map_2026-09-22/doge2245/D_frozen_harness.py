"""D_frozen_index harness -- why the DOGE-2245 hold wrote no hedge_blind.

Extends the K3 harness (results/map_2026-09-22/verify/K3-frozen-index-code.md,
scratchpad/map/verify2/K3-frozen-index-code/harness.py) with the TWO code
paths that harness did not have, because they did not exist yet when it ran:

  * the `hedged` skip, pinrun.py 10967-10968, which runs BEFORE the K3 check
  * the K3 check itself, pinrun.py 11021-11036 (index_age / market_belief /
    hedge_blind index_stale), shipped as v-safety1
  * the hedge_quote record, pinrun.py 11447-11465, which only READS
    last_belief (written at 11066, below the skip)

Imports pinrun's own IndexWS, fair, widen_factor, index_age, market_belief,
hedge_should_fire, hedge_want, hedge_fraction, hedge_panic. kauth is stubbed
before the import, so no key is read and no socket is opened.

Worlds, all: one held position, entered on a fresh index (age <= 2 s).
  C1  fresh index, NOT hedged, real collapse      -> must alarm (harness works)
  C2  frozen index, NOT hedged, no collapse       -> null: K3 must not invent
  W1  frozen index, NOT hedged, collapse          -> K3 works: hedge_blind
  W2  frozen index, ALREADY HEDGED at tau 10      -> THE BUG: no record at all
  W3  FRESH  index, ALREADY HEDGED at tau 10      -> log is IDENTICAL to W2
  W4  the real DOGE index for close 02:45:00Z     -> reproduces the live beliefs
  F2/F3 W2/W3 with the proposed fix applied       -> W2 and W3 now differ
"""
import os
import sys
import types
import math
import gzip
import glob
import json
import random
import ctypes

os.environ.setdefault("KALSHI_KEY_ID", "stub")
os.environ.setdefault("KALSHI_KEY_FILE", "stub")
_k = types.ModuleType("kauth")
_k.KEY_ID, _k.KEY_FILE = "stub", "stub"


def _no_net(*a, **kw):
    raise RuntimeError("harness: network forbidden")


_k.get = _no_net
sys.modules["kauth"] = _k

# Prefer the worktree this was written in; fall back to the repo, so the
# artefact still runs after the worktree is gone. Either way the file read is
# the one whose SHA-256 prefix is b359cfa7f841, unless pinrun has since moved.
for _p in (r"C:\kals-repo\.claude\worktrees\wf_a51a5354-b5e-1\research",
           r"C:\kals-repo\research"):
    if os.path.isfile(os.path.join(_p, "pinrun.py")):
        sys.path.insert(0, _p)
        break
import pinrun                                                     # noqa: E402
import time as _real_time                                         # noqa: E402

print("pinrun read from:", pinrun.__file__)


class FakeTime:
    """pinrun.time shim: IndexWS.spot()'s age is measured on OUR clock."""

    def __init__(self):
        self.t = 0.0

    def time(self):
        return self.t

    def __getattr__(self, n):
        return getattr(_real_time, n)


CLOCK = FakeTime()
pinrun.time = CLOCK

# THE LIVE FLAGS, from the `start` record of the run that holds the loss
# (results/pinrun-live-20260923T003317Z.jsonl): hedge_belief 0.25,
# hedge_panic 0.40, hedge_prop false, hedge_jump null, jump_widen false,
# sigma_stress 1.0, sigma_ruler live, max_index_age_s 2, max_book_age_ms 2000.
pinrun.HEDGE_BELIEF = 0.25
pinrun.HEDGE_PANIC = 0.40
pinrun.HEDGE_PROP = False
pinrun.HEDGE_JUMP_SIGMA = None
pinrun.WIDEN_ENABLED = False
pinrun.SIGMA_STRESS = 1.0
pinrun.SIGMA_RULER = "live"
pinrun.MAX_INDEX_AGE_S = 2
pinrun.MAX_BOOK_AGE_MS = 2000
pinrun.HEDGE_ENABLED = True

IID = "BRTI"
OTHER = "ETHUSD_RTI"
C = 1790100000
SIG = 4.0


def frame(iid, sec, val):
    return {"type": "cfbenchmarks_value",
            "msg": {"index_id": iid,
                    "data": {"time": sec * 1000, "value": str(val)}}}


# ---------------------------------------------------------------------------
# The hedge pass, TODAY, transcribed in order with the live line numbers.
# Decision + records only: no order is built and nothing is sent.
# ---------------------------------------------------------------------------
def hedge_pass(idx, bookf, now_s, open_pos, st, fix=False, skip_at="top"):
    """pinrun.py 10946-11083 plus the hedge_quote block at 11447-11465.

    `st` carries the live loop's own state: hedged, hedge_remain, last_belief,
    _hq71, hedge_quote_at, recs, plus `fill` (a callable that says whether a
    hedge send would fill, so a world can hedge at a chosen second).

    `fix=True` applies the proposed fix and NOTHING else.
    `skip_at` moves the `hedged` skip, to price the two obvious alternatives:
      "top"      -- where it is today (10967), above the K3 check
      "after_k3" -- below the index_stale record, above the belief/alarm/send
      "never"    -- removed, so a hedged position runs the whole pass
    """
    recs = st["recs"]

    def rec(kind, **kw):
        recs.append(dict(kind=kind, now_s=now_s, **kw))

    def _done(_hid):
        return _hid in st["hedged"] or _hid.startswith("hedge-")

    if pinrun.HEDGE_ENABLED:
        for _hid, (_hcs, _hwant, _hcost, _hn_orig, _htk) in list(open_pos.items()):
            _hn = st["hedge_remain"].get(_hid, _hn_orig)              # 10966
            if skip_at == "top" and _done(_hid):                      # 10967
                continue                                              # 10968

            def _hquiet(_why, _hid=_hid, _htk=_htk, _hcs=_hcs, **_kw):  # 10983
                _key = (_hid, _why)
                if _key in st["_hq71"]:
                    return
                st["_hq71"].add(_key)
                rec("hedge_blind", ticker=_htk, why=_why,
                    tau=_hcs - now_s, **_kw)

            _meta = st["hedge_meta"].get(_hid)                         # 10992
            if _meta is None:
                _hquiet("no_hedge_meta")
                continue
            _hstrike, _hdig, _hiid = _meta                            # 10997
            _htau = _hcs - now_s
            if _htau < 1:                                             # 10999
                continue
            _hage = pinrun.index_age(idx, _hiid)                      # 11021
            _hmkt = None
            if _hage is None or _hage > pinrun.MAX_INDEX_AGE_S:        # 11023
                _hbk3 = bookf(_htk, now_s)
                _hmkt = pinrun.market_belief(_hbk3, _hwant)            # 11028
                _hquiet("index_stale", iid=_hiid,                      # 11029
                        age_s=(round(_hage, 2) if _hage is not None else None),
                        market_belief=(round(_hmkt, 4)
                                       if _hmkt is not None else None),
                        book_age_ms=(_hbk3 or {}).get("age_ms"))
            _hsg = idx.sigma(_hiid)                                    # 11037
            if _hsg is None:
                _hquiet("no_sigma", iid=_hiid)
                if _hmkt is None:
                    continue
                _hf = None
            else:
                _hf = pinrun.fair(idx, _hiid, _hcs, now_s, _hstrike,
                                  _hsg * pinrun.SIGMA_STRESS
                                  * pinrun.widen_factor(idx, _hiid, _hsg,
                                                        _hwant),
                                  round_digits=_hdig)                  # 11044
                if _hf is None:
                    _hquiet("no_fair", iid=_hiid)
                    if _hmkt is None:
                        continue
            _hmodel = (None if _hf is None                             # 11053
                       else (_hf if _hwant == "yes" else 1.0 - _hf))
            _belief = _hmodel
            if _hmkt is not None:                                      # 11056
                _belief = (_hmkt if _hmodel is None
                           else min(_hmodel, _hmkt))
            if skip_at == "after_k3" and _done(_hid):
                continue          # the skip, moved below the K3 record
            if _hmodel is not None:                                    # 11065
                st["last_belief"][_htk] = float(_hmodel)
                st["belief_t"][_htk] = now_s
            _htrig = "belief"
            if (_hmkt is not None
                    and (_hmodel is None or _hmkt < _hmodel)):         # 11079
                _htrig = "market_index_stale"
            if not pinrun.hedge_should_fire(_belief):                   # 11082
                continue
            if st["hedge_last_try"].get(_hid) == now_s:                 # 11089
                continue
            st["hedge_last_try"][_hid] = now_s
            if _hid not in st["hedge_alarmed"]:                         # 11099
                st["hedge_alarmed"].add(_hid)
                rec("hedge_alarm", ticker=_htk, want=_hwant, n=_hn,
                    belief=round(_belief, 5), tau=_htau, trigger=_htrig)
            _unhedged = float(_hn)                                      # 11129
            _hn_now = pinrun.hedge_want(_hn_orig, _unhedged, _belief)   # 11130
            if _hn_now <= 1e-9:
                continue
            _filled = st["fill"](_htk, now_s, _hn_now)                  # the send
            rec("hedge", ticker=_htk, n=_filled, tau=_htau,
                belief=round(_belief, 5))
            if _filled > 0:                                             # 11329
                _left = float(_unhedged) - _filled
                if _left <= 1e-9:
                    st["hedged"].add(_hid)                              # 11343
                    st["hedge_remain"].pop(_hid, None)
                else:
                    st["hedge_remain"][_hid] = _left

    # ---- hedge_quote, pinrun.py 11447-11465 (below the pass, read-only) ----
    _hq_held = {}
    for _qid, (_qcs, _qwant, _qc, _qn, _qtk) in open_pos.items():
        if not _qid.startswith("hedge-") and _qcs - now_s >= 1:
            _hq_held.setdefault(_qtk, (_qcs, _qwant, _qid))
    for _qtk, (_qcs, _qwant, _qid) in _hq_held.items():
        if st["hedge_quote_at"].get(_qtk) == now_s:
            continue
        st["hedge_quote_at"][_qtk] = now_s
        _qopp = "no" if _qwant == "yes" else "yes"
        _qb = bookf(_qtk, now_s) or {}
        extra = {}
        if fix:
            # THE PROPOSED FIX, and nothing else: two read-only fields on a
            # record that already exists, already runs once per held market
            # per second, and already sits below the hedge pass inside its
            # own try/except. It cannot block, delay or change a hedge.
            _qm = st["hedge_meta"].get(_qid)
            _qiid = _qm[2] if _qm else None
            extra["index_age_s"] = (
                None if _qiid is None
                else (lambda _a: None if _a is None else round(_a, 2))(
                    pinrun.index_age(idx, _qiid)))
            extra["belief_age_s"] = (
                None if st["belief_t"].get(_qtk) is None
                else now_s - st["belief_t"][_qtk])
        recs.append(dict(kind="hedge_quote", now_s=now_s, ticker=_qtk,
                         side=_qopp, ask=_qb.get(f"{_qopp}_ask"),
                         tau=_qcs - now_s,
                         belief=st["last_belief"].get(_qtk), **extra))


def fresh_state():
    return dict(hedged=set(), hedge_remain={}, last_belief={}, belief_t={},
                _hq71=set(), hedge_quote_at={}, hedge_last_try={},
                hedge_alarmed=set(), hedge_meta={}, recs=[],
                fill=lambda tk, s, n: 0.0)


# ---------------------------------------------------------------------------
# Synthetic worlds
# ---------------------------------------------------------------------------
def truth_path(seed, entry_tau, collapse):
    rng = random.Random(seed)
    v = 100000.0
    out = {}
    for s in range(C - 3700, C):
        v += rng.gauss(0.0, SIG)
        if collapse and s >= C - entry_tau + 3:
            v -= 9.0
        out[s] = round(v, 2)
    return out


def world(name, entry_tau=30, collapse=True, freeze_at=None, hedge_at=None,
          fix=False, skip_at="top", seed=7, want="yes"):
    """freeze_at: the tau from which the HELD market's index stops arriving.
    OTHER indices keep flowing, so the socket's 30 s recv timeout
    (pinrun.py 2650) never fires -- one frozen index behind healthy ones.
    hedge_at: the tau at which a hedge send fills in full (as DOGE's did).
    The BOOK is fresh every second in every world: the book was flowing."""
    tp = truth_path(seed, entry_tau, collapse)
    entry_s = C - entry_tau
    idx0 = pinrun.IndexWS([IID])
    for s in range(C - 3700, entry_s + 1):
        idx0.on_frame(frame(IID, s, tp[s]), rx_ms=s * 1000)
    locked, r = idx0.partial(IID, C, entry_s)
    sd = idx0.sigma(IID) * math.sqrt(pinrun.var_factor(int(r), [1.0]))
    strike = round((locked + r * tp[entry_s]) / 60.0 - 2.4 * sd, 2)

    idx = pinrun.IndexWS([IID, OTHER])
    for s in range(C - 3700, entry_s + 1):
        idx.on_frame(frame(IID, s, tp[s]), rx_ms=s * 1000)
    CLOCK.t = entry_s + 0.3

    st = fresh_state()
    pid = "pos-1"
    tk = "KXTEST15M-X"
    open_pos = {pid: (C, want, 0.93, 13.0, tk)}
    st["hedge_meta"][pid] = (strike, 2, IID)

    def bookf(_tk, now_s, _collapse=collapse):
        # our side is YES. In a collapsing world the market repriced it to
        # ~1c (so the K3 market fallback CAN fire); in a calm world our side
        # is still 99c (so it must NOT).
        if _collapse:
            return {"age_ms": 5, "suspect": False,
                    "yes_bid": 0.010, "yes_ask": 0.013,
                    "no_bid": 0.985, "no_ask": 0.990}
        return {"age_ms": 5, "suspect": False,
                "yes_bid": 0.985, "yes_ask": 0.990,
                "no_bid": 0.010, "no_ask": 0.013}

    def fill(_tk, now_s, n, _hedge_at=hedge_at):
        # insurance has depth from `hedge_at` onward, as DOGE's did from
        # tau 9 (ask 98.7c, 74.41 offered). Before then nothing fills.
        return float(n) if (_hedge_at is not None
                            and C - now_s <= _hedge_at) else 0.0

    st["fill"] = fill
    for now_s in range(entry_s + 1, C + 1):
        CLOCK.t = now_s + 0.05
        if freeze_at is None or (C - now_s) > freeze_at:
            idx.on_frame(frame(IID, now_s - 1, tp[now_s - 1]),
                         rx_ms=now_s * 1000)
        else:
            idx.on_frame(frame(OTHER, now_s - 1, 3000.0), rx_ms=now_s * 1000)
        hedge_pass(idx, bookf, now_s, open_pos, st, fix=fix, skip_at=skip_at)
    avg = sum(tp[s] for s in range(C - 60, C)) / 60.0
    return dict(name=name, st=st, strike=strike,
                yes_wins=round(avg, 2) >= strike,
                freeze_at=freeze_at, hedge_at=hedge_at, fix=fix,
                skip_at=skip_at)


def report(w):
    recs = w["st"]["recs"]
    hq = [r for r in recs if r["kind"] == "hedge_quote"]
    blind = [r for r in recs if r["kind"] == "hedge_blind"]
    alarms = [r for r in recs if r["kind"] == "hedge_alarm"]
    beliefs = [r["belief"] for r in hq if r["tau"] <= 9]
    distinct = sorted({b for b in beliefs if b is not None})
    hedges = [r for r in recs if r["kind"] == "hedge"]
    out = [f"{w['name']}",
           f"   index {'freezes at tau %s' % w['freeze_at'] if w['freeze_at'] is not None else 'fresh all through'}; "
           f"hedge fills at tau {w['hedge_at']}; skip {w['skip_at']}; "
           f"YES {'wins' if w['yes_wins'] else 'LOSES'}",
           f"   hedge sends: {len(hedges)} at tau "
           f"{[h['tau'] for h in hedges]} filling {[h['n'] for h in hedges]}",
           f"   hedge_blind records: {len(blind)} "
           f"{sorted({b['why'] for b in blind})}"
           + (f" first at tau {blind[0]['tau']}" if blind else ""),
           f"   hedge_alarm: {len(alarms)}"
           + (f" first tau {alarms[0]['tau']} trigger {alarms[0]['trigger']}"
              if alarms else ""),
           f"   hedge_quote at tau<=9: {len(hq and beliefs)} rows, "
           f"{len(distinct)} distinct belief value(s) {distinct[:3]}"]
    if any("index_age_s" in r for r in hq):
        ages = [r.get("index_age_s") for r in hq if r["tau"] <= 9]
        bags = [r.get("belief_age_s") for r in hq if r["tau"] <= 9]
        out.append(f"   FIX fields at tau<=9: index_age_s "
                   f"{min(a for a in ages if a is not None):.2f}"
                   f"..{max(a for a in ages if a is not None):.2f} s, "
                   f"belief_age_s {min(b for b in bags if b is not None)}"
                   f"..{max(b for b in bags if b is not None)} s")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# W4: the real DOGE index for close 2026-09-23T02:45:00Z
# ---------------------------------------------------------------------------
def real_doge():
    """Replay the actual DOGEUSD_RTI prints and the actual strike through
    pinrun's own fair(), one second at a time, to answer: is a belief that is
    byte-identical between tau 10 and tau 9 evidence of a frozen feed?

    Read-only, one hour file, values only (48k floats at most)."""
    close_s = 1790131500
    strike, digits = 0.1017036, 7
    ticks = {}
    for p in sorted(glob.glob(r"C:\kals\kalshi_data\cfbenchmarks_value\20260923T0[12].jsonl.gz")):
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                if "DOGEUSD_RTI" not in ln:
                    continue
                try:
                    d = json.loads(ln)
                    m = d.get("msg") or {}
                    if m.get("index_id") != "DOGEUSD_RTI":
                        continue
                    da = m.get("data")
                    da = json.loads(da) if isinstance(da, str) else da
                    ticks[int(da["time"]) // 1000] = float(da["value"])
                except Exception:                              # noqa: BLE001
                    continue
    idx = pinrun.IndexWS(["DOGEUSD_RTI"])
    have = sorted(s for s in ticks if s <= close_s - 1)
    for s in have:
        idx.on_frame(frame("DOGEUSD_RTI", s, ticks[s]), rx_ms=s * 1000)
    win = [s for s in range(close_s - 60, close_s) if s in ticks]
    settle = sum(ticks[s] for s in win) / 60.0
    rows = []
    # partial() ends the locked window at the NEWEST PRINT HELD (2610), so the
    # belief is a function of the prints held, not of the clock. Feed the bot
    # exactly the prints up to each second and read what fair() says.
    for newest in range(close_s - 14, close_s):
        sub = pinrun.IndexWS(["DOGEUSD_RTI"])
        for s in have:
            if s <= newest:
                sub.on_frame(frame("DOGEUSD_RTI", s, ticks[s]), rx_ms=s * 1000)
        # any pass whose newest print is `newest` sees this; the clock only
        # sets the age, not the belief. Use the earliest such pass.
        now_s = newest
        CLOCK.t = now_s + 0.05
        sg = sub.sigma("DOGEUSD_RTI")
        f = pinrun.fair(sub, "DOGEUSD_RTI", close_s, now_s, strike,
                        sg * pinrun.SIGMA_STRESS, round_digits=digits)
        bel = None if f is None else 1.0 - f     # we held NO
        rows.append((newest, ticks.get(newest),
                     None if bel is None else repr(bel),
                     None if sg is None else round(sg, 8)))
    return dict(n_ticks=len(ticks), n_window=len(win), settle=settle,
                strike=strike, rows=rows, close_s=close_s)


def peak_mb():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    fn = ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    fn(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PeakWorkingSetSize / 1e6


if __name__ == "__main__":
    out, ok = [], True

    def ck(cond, msg):
        global ok
        ok = ok and bool(cond)
        out.append(("PASS " if cond else "FAIL ") + msg)

    c1 = world("C1 control: fresh index all through, never hedged, collapse",
               freeze_at=None, collapse=True, hedge_at=None)
    c2 = world("C2 null: index freezes at tau 28, never hedged, NO collapse, "
               "calm book",
               freeze_at=28, collapse=False, hedge_at=None)
    w1 = world("W1 index freezes at tau 28, NEVER hedged, collapse "
               "(K3 as designed)",
               freeze_at=28, collapse=True, hedge_at=None)
    w2 = world("W2 THE DOGE SHAPE: fresh until the hedge fills at tau 10, "
               "index freezes at tau 9",
               freeze_at=9, collapse=True, hedge_at=10)
    w3 = world("W3 the SAME but the index stays perfectly healthy",
               freeze_at=None, collapse=True, hedge_at=10)
    f2 = world("F2 = W2 with the fix", freeze_at=9, collapse=True,
               hedge_at=10, fix=True)
    f3 = world("F3 = W3 with the fix", freeze_at=None, collapse=True,
               hedge_at=10, fix=True)
    x1 = world("X1 = W2 with the skip moved BELOW the K3 record",
               freeze_at=9, collapse=True, hedge_at=10, skip_at="after_k3")
    x2 = world("X2 = W2 with the skip REMOVED (the obvious 'let it check')",
               freeze_at=9, collapse=True, hedge_at=10, skip_at="never")
    for w in (c1, c2, w1, w2, w3, f2, f3, x1, x2):
        out.append(report(w))
        out.append("")

    def sig(w, with_fix_fields=True):
        """The log a reader would see from tau 9 down."""
        keys = ("kind", "tau", "ticker", "why", "belief", "ask")
        if with_fix_fields:
            keys = keys + ("index_age_s", "belief_age_s")
        return [tuple(r.get(k) for k in keys) for r in w["st"]["recs"]
                if r.get("tau") is not None and r["tau"] <= 9]

    ck(any(r["kind"] == "hedge_alarm" for r in c1["st"]["recs"]),
       "C1: a fresh feed through a collapse DOES alarm (the harness can see one)")
    ck(not c1["yes_wins"], "C1/W*: the planted collapse really loses the bet")
    ck([r for r in c2["st"]["recs"]
        if r["kind"] == "hedge_blind" and r["why"] == "index_stale"]
       and not [r for r in c2["st"]["recs"] if r["kind"] == "hedge_alarm"]
       and not [r for r in c2["st"]["recs"] if r["kind"] == "hedge"]
       and c2["yes_wins"],
       "C2 NULL (catches the sign): a frozen index on a CALM book is "
       "recorded but buys NOTHING -- no alarm, no hedge")
    ck([r for r in w1["st"]["recs"]
        if r["kind"] == "hedge_blind" and r["why"] == "index_stale"],
       "W1: K3 WORKS -- an unhedged hold on a frozen index writes "
       "hedge_blind index_stale")
    ck(not [r for r in w2["st"]["recs"] if r["kind"] == "hedge_blind"],
       "W2 THE BUG: the same freeze on an ALREADY-HEDGED hold writes NO "
       "hedge_blind at all")
    ck(len({r["belief"] for r in w2["st"]["recs"]
            if r["kind"] == "hedge_quote" and r["tau"] <= 9
            and r["belief"] is not None}) == 1,
       "W2: hedge_quote's belief is byte-identical for every second after "
       "the hedge")
    ck(len({r["belief"] for r in w3["st"]["recs"]
            if r["kind"] == "hedge_quote" and r["tau"] <= 9
            and r["belief"] is not None}) == 1,
       "W3: a FULLY HEALTHY index gives the byte-identical belief too")
    ck(sig(w2, False) == sig(w3, False),
       "W2 vs W3: today's log from tau 9 down is IDENTICAL for a frozen and "
       "a healthy index -- the symptom is not evidence of a freeze")
    ck(sig(f2, True) != sig(f3, True),
       "FIX: with the two fields, a frozen index and a healthy one no longer "
       "produce the same log")
    ck([r.get("index_age_s") for r in f2["st"]["recs"]
        if r["kind"] == "hedge_quote" and r["tau"] == 1][0] > pinrun.MAX_INDEX_AGE_S,
       "FIX: F2's last hedge_quote names an index age over the 2 s bar")
    ck(([r.get("index_age_s") for r in f3["st"]["recs"]
         if r["kind"] == "hedge_quote" and r["tau"] == 1][0]
        or 99) <= pinrun.MAX_INDEX_AGE_S,
       "FIX NULL: F3 (healthy index) never reports an age over the bar")
    ck(sig(f2, False) == sig(w2, False) and sig(f3, False) == sig(w3, False),
       "FIX: every field that existed before is UNCHANGED -- no decision, "
       "alarm, hedge or refusal moved")
    ck([r for r in f2["st"]["recs"] if r["kind"] == "hedge"]
       == [r for r in w2["st"]["recs"] if r["kind"] == "hedge"],
       "FIX: the hedge sends are identical, same seconds, same sizes")
    _x1h = [r for r in x1["st"]["recs"] if r["kind"] == "hedge"]
    _x2h = [r for r in x2["st"]["recs"] if r["kind"] == "hedge"]
    _w2h = [r for r in w2["st"]["recs"] if r["kind"] == "hedge"]
    ck(_x1h == _w2h and [r for r in x1["st"]["recs"]
                         if r["kind"] == "hedge_blind"
                         and r["why"] == "index_stale"],
       "X1: the skip moved below the K3 record DOES write the record and "
       "sends nothing extra -- correct, but it runs inside the hedge pass")
    ck(len(_x2h) > len(_w2h)
       and sum(h["n"] for h in _x2h) > sum(h["n"] for h in _w2h),
       "X2 THE LANDMINE: removing the skip re-buys the hedge it already "
       "owns (hedge_remain was popped, so hedge_want returns the FULL size)")

    out.append("\n--- W4: the REAL DOGE index, close 2026-09-23T02:45:00Z ---")
    # what the live log actually recorded, ticker KXDOGE15M-26SEP222245-45
    LIVE = {12: "0.9955949944046358", 11: "0.9955949944046358",
            10: "0.9986709079754776", 9: "0.0514329175139725",
            8: "0.0514329175139725", 7: "0.0514329175139725",
            6: "0.0514329175139725", 5: "0.0514329175139725",
            4: "0.0514329175139725", 3: "0.0514329175139725",
            2: "0.0514329175139725", 1: "0.0514329175139725"}
    try:
        d = real_doge()
        out.append(f"   DOGEUSD_RTI prints loaded {d['n_ticks']}, "
                   f"settlement window {d['n_window']}/60, "
                   f"settle {d['settle']:.8f} vs strike {d['strike']}")
        out.append("   newest print held | its value | model belief in NO "
                   "(repr) | live hedge_quote that matches")
        seen = {}
        for newest, val, bel, sg in d["rows"]:
            seen[bel] = newest
            hits = sorted(t for t, v in LIVE.items() if v == bel)
            out.append(f"   {newest} (tau {d['close_s'] - newest:>2}) | {val} "
                       f"| {bel} | {'tau ' + ','.join(map(str, hits)) if hits else '-'}")
        b = {newest: bel for newest, val, bel, sg in d["rows"]}
        ck(b[d["close_s"] - 12] == LIVE[12] == LIVE[11],
           "W4: the live tau-12 AND tau-11 belief is what the bot computes "
           "from the print for second close-12 -- one print, two passes")
        ck(b[d["close_s"] - 11] == LIVE[10],
           "W4: the live tau-10 belief is the NEXT print, so a print DID "
           "arrive between tau 11 and tau 10")
        ck(b[d["close_s"] - 10] == LIVE[9],
           "W4: the live tau-9 belief is the print for second close-10 -- "
           "a healthy feed one print behind, not a dead feed")
        ck(b[d["close_s"] - 9] != LIVE[9],
           "W4: had the next print been in hand the belief WOULD have "
           "changed, so a repeated value means 'no new print in that pass'")
        ck(len({LIVE[t] for t in (9, 8, 7, 6, 5, 4, 3, 2, 1)}) == 1
           and len({b[s] for s in range(d["close_s"] - 10, d["close_s"] - 1)}) > 1,
           "W4: the index kept MOVING through tau 8..1 (the bot's own fair() "
           "gives a different answer each second) while the live log repeated "
           "one number -- the log stopped, not the model")
    except Exception as e:                                     # noqa: BLE001
        ck(False, f"W4 FAILED to run: {type(e).__name__}: {e}")

    print("\n".join(out))
    print(f"\npeak working set {peak_mb():.0f} MB")
    print("ALL PASS" if ok else "SOME CHECK FAILED")
    sys.exit(0 if ok else 1)
