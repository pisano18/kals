"""Apply v-hedge5 (build 0925w) to a COPY of the live pin build (C:\\kals-live-0925v: research\\pinrun.py code_sha
d51b131b55cf; pintake.py b3c7bb48abb5 and ordercli.py 467782077a23 are NOT touched). Patches pinrun.py in place,
CRLF preserved; every anchor must occur exactly once; refuses an already-patched tree and a tree that is not 0925v.
usage: python patch_0925w.py <build_dir>      (build_dir holds research\\pinrun.py)

One new flag, off when omitted (= 0925v exactly, byte for byte in behaviour: nothing new is subscribed or read):

  --index-5hz off|shadow|hedge   (v-hedge5) Kalshi streams the settlement index FIVE times a second
      (cfbenchmarks_value_5hz, since 2026-09-03) for BTC, ETH, SOL, XRP and DOGE; pin reads the once-a-second channel
      only, so after a move it waits for the next whole-second print (half a second on average) before its hedge
      can see it. The operator, 11-09: "the bot needs to be as utterly fast as it can possibly be."
      shadow / hedge both:
        * subscribe to the 5 Hz channel for those five indices (INDEX_5HZ_IDS) on pin's own index socket;
        * a SUB-second print never enters the settlement ticks (settlement averages the 60 top-of-second prints);
          it is kept as the index's newest fast print (IndexWS.fast, read by fast_spot());
        * a TOP-of-second print on the 5 Hz channel is the same print as the 1 Hz channel's (180 of 180 equal,
          measured 10-08) and arrives ~40 ms sooner (median receipt lag 58 ms vs 98 ms): it is stored only for a
          second NOT yet held, and the 1 Hz print still overwrites it as today, so it can only make a print EARLIER;
        * the hedge pass computes the belief on the newest fast print as well (fair5: fair()'s arithmetic, the
          same locked prints, the fast print as the current one) and writes it on every hedge_quote (belief5)
          and hedge_alarm (belief_1hz, belief5, fast_ms, by_5hz).
      shadow: NOTHING is sent on it. The first second a position's 5 Hz belief is under --hedge-belief while the
          1 Hz belief is not, ONE hedge5_shadow record says what the belief hedge would have bought then (side,
          contracts as the send site sizes them, the ask, its size, the ladder up to the limit, the extra, the
          belief on both clocks, the fast print's time and age). Written below the hedge pass, never in front of
          a hedge. A 5 Hz dip that recovers is recorded the same way (that is a false alarm, priced by the read).
      hedge: the hedge fires on the LOWER of the two beliefs (the 5 Hz belief can only ADD a trigger, never
          remove one, exactly as K3's market fallback); every filter, size and send after that is unchanged.
      A one-time index5_up record (or index5_silent after 120 s with no fast print) says whether the feed arrived.
"""
import hashlib
import os
import sys

B = sys.argv[1]
PR = os.path.join(B, "research", "pinrun.py")
BASE_PINRUN = "d51b131b55cf"


def sha12(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


class Src:
    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read().decode("utf-8")
        assert "\r\n" in raw, path + ": not CRLF"
        self.s = raw.replace("\r\n", "\n")
        assert "\r" not in self.s, path + ": stray CR"

    def once(self, anchor):
        n = self.s.count(anchor)
        assert n == 1, (self.path, n, anchor[:90])

    def after(self, anchor, text):
        self.once(anchor)
        self.s = self.s.replace(anchor, anchor + text)

    def before(self, anchor, text):
        self.once(anchor)
        self.s = self.s.replace(anchor, text + anchor)

    def replace(self, old, new):
        self.once(old)
        self.s = self.s.replace(old, new)

    def write(self):
        open(self.path, "wb").write(self.s.replace("\n", "\r\n").encode("utf-8"))


assert sha12(PR) == BASE_PINRUN, "research/pinrun.py is not 0925v (%s)" % sha12(PR)
R = Src(PR)
assert "INDEX_5HZ" not in R.s and "fast_spot" not in R.s and "hedge5_shadow" not in R.s, "already patched"
assert "HEDGE_JUMP_SHADOW" in R.s and "CHEAP_WINDOW" in R.s, "not the 0925v build"

# 1. the constants, after the v-0925v JS ones
R.after('''HEDGE_JUMP_SHADOW = None
_DEFAULT_HEDGE_JUMP_SHADOW = None
''', '''# v-hedge5 (2026-11-10; operator 11-09: "the bot needs to be as utterly fast
# as it can possibly be"). Kalshi streams the settlement index 5x a second
# (cfbenchmarks_value_5hz) for the five indices below; the hedge waited for
# the next whole-second print. The 11-09 sub-second tape study: the hedge
# side's ask rises a median 32c in the second before the print that shows
# the move is even sent, and a hedge 500 ms earlier is worth $24.81 a flip at
# 190 contracts (no false fires). --index-5hz: off (shipped = 0925v), shadow
# (read it, record what the hedge would have done, send nothing), hedge (the
# belief hedge fires on the lower of the 1 Hz and 5 Hz beliefs).
INDEX_5HZ = "off"
_DEFAULT_INDEX_5HZ = "off"
INDEX_5HZ_IDS = frozenset(("BRTI", "ETHUSD_RTI", "SOLUSD_RTI", "XRPUSD_RTI",
                           "DOGEUSD_RTI"))
INDEX_5HZ_SILENT_S = 120.0   # no fast print this long after the start -> index5_silent


def h5_shadow_fields(book, tk, want, n_orig, n_left, belief1, belief5, tau,
                     fast_ms, entry_tau=None):
    """v-hedge5: what a hedge5_shadow record says -- the belief hedge pin
    WOULD have sent this second on the 5 Hz belief, sized exactly as the
    hedge pass sizes it (hedge_want on what is still unhedged, flip_size,
    the ladder up to hedge_limit when --hedge-slip reads one), the other
    side's ask, its size and the ladder itself, the v-oddsmult extra, and
    the first thing on the belief hedge's own path that would have stopped
    the send (nothing_to_buy, no_ask, filtered) or would_send. Reads the
    book; sends nothing. Never raises: a read it cannot make leaves its
    field None (and the outcome "error")."""
    out = {"side": ("no" if want == "yes" else "yes"), "n": 0.0, "n_want": None,
           "ask": None, "ask_size": None, "limit": None, "rungs": None,
           "belief": None, "belief5": None, "fast_ms": fast_ms,
           "fast_age_ms": None, "threshold": HEDGE_BELIEF, "tau": tau,
           "panic": None, "filtered": None, "extra_n": None,
           "would_send": False, "sent": False, "outcome": "error"}
    try:
        _opp = out["side"]
        out["belief"] = round(float(belief1), 5)
        out["belief5"] = round(float(belief5), 5)
        if fast_ms is not None:
            out["fast_age_ms"] = int(round(time.time() * 1000.0 - float(fast_ms)))
        try:
            _b = book.best(tk)
        except Exception:                                # noqa: BLE001
            _b = None
        _ask = (_b or {}).get(f"{_opp}_ask")
        _asz = (_b or {}).get(f"{_opp}_ask_size")
        out["ask"] = round(float(_ask), 4) if _ask is not None else None
        out["ask_size"] = _asz
        _ok = bool(_b) and bool(_ask) and bool(_asz) and float(_ask) < 1.0
        _nw = hedge_want(n_orig, float(n_left), belief5)
        _nf = flip_size(_nw, entry_tau, tau)
        out["n_want"] = round(float(_nf), 2)
        _lim, _rg = None, []
        if _ok:
            _lim = hedge_limit(_ask, ticker=tk)
            if HEDGE_SLIP and _lim is not None:
                try:
                    _rg = book.rungs(tk, _opp, _lim)
                except Exception:                        # noqa: BLE001
                    _rg = []
        out["limit"] = round(float(_lim), 4) if _lim is not None else None
        out["rungs"] = [[round(float(_p), 4), round(float(_z), 2)]
                        for _p, _z in list(_rg or [])[:12]]
        _dep = hedge_depth(_asz, _rg, _nw) if (_ok and _asz) else 0.0
        _take = min(float(_nf), float(_dep or 0.0))
        out["n"] = round(_take, 2)
        out["panic"] = bool(hedge_panic(belief5))
        out["filtered"] = bool(_ok and (
            (not out["panic"] and not (hedge_price_ok(_ask)
                                       and hedge_normal_ok(belief5, _ask)))
            or not hedge_ask_ok(_ask)))
        out["extra_n"] = odds_extra(n_orig, "belief", belief5, tau)
        if float(_nw) <= 1e-9:
            out["outcome"] = "nothing_to_buy"
        elif not _ok:
            out["outcome"] = "no_ask"
        elif out["filtered"]:
            out["outcome"] = "filtered"
        elif _take > 1e-9:
            out["outcome"] = "would_send"
        else:
            out["outcome"] = "nothing_to_buy"
        out["would_send"] = out["outcome"] == "would_send"
    except Exception as _e:                              # noqa: BLE001
        out["err"] = type(_e).__name__
    return out
''')

# 2. IndexWS: the fast print store, the 5 Hz frames, fast_spot(), the subscription
R.replace('''        self._stop = threading.Event()
        self._thread = None

    # ---- ingest (shared by the live socket and the self-test) ----''', '''        self._stop = threading.Event()
        self._thread = None
        # v-hedge5: index_id -> (t_ms, value) of the newest SUB-second print
        # off the 5 Hz channel. Never a settlement print, never in `ticks`.
        self.fast = {}

    # ---- ingest (shared by the live socket and the self-test) ----''')
R.replace('''        if d.get("type") != "cfbenchmarks_value":
            self.stats[str(d.get("type"))] += 1
            return''', '''        _typ = d.get("type")
        # v-hedge5: the 5 Hz channel is read only with --index-5hz on; off, its
        # frames are counted and dropped exactly like any other channel's
        _is5 = (_typ == "cfbenchmarks_value_5hz" and INDEX_5HZ != "off")
        if _typ != "cfbenchmarks_value" and not _is5:
            self.stats[str(_typ)] += 1
            return''')
R.replace('''            val = float(data["value"])
            sec = int(data["time"]) // 1000
        except Exception:
            self.stats["bad_tick"] += 1
            return
''', '''            val = float(data["value"])
            _tms = int(data["time"])
            sec = _tms // 1000
        except Exception:
            self.stats["bad_tick"] += 1
            return
        if _is5:
            if _tms % 1000:
                # v-hedge5: a SUB-second print only makes the hedge's current
                # print fresher; settlement never sees it
                with self.lock:
                    _prev5 = self.fast.get(iid)
                    if _prev5 is None or _tms > _prev5[0]:
                        self.fast[iid] = (_tms, val)
                self.stats["fast_ticks"] += 1
                return
            # a TOP-of-second print: the 1 Hz channel's own print, ~40 ms
            # sooner. Stored only for a second not yet held; the 1 Hz frame
            # still overwrites it below, as it always has
            with self.lock:
                if sec in self.ticks[iid]:
                    self.stats["fast_dup"] += 1
                    return
            self.stats["fast_first"] += 1
''')
R.before('''    def _stamp(self, iid, d):''', '''    def fast_spot(self, iid, max_age_s=None):
        """v-hedge5: (t_ms, value) of the newest SUB-second print when it is
        NEWER than the newest whole second held and at most MAX_INDEX_AGE_S
        old, else None. Never raises."""
        try:
            with self.lock:
                f = self.fast.get(iid)
                d = self.ticks.get(iid)
                if f is None or not d:
                    return None
                if f[0] / 1000.0 <= max(d):
                    return None
            _lim = MAX_INDEX_AGE_S if max_age_s is None else max_age_s
            if time.time() - f[0] / 1000.0 > float(_lim):
                return None
            return f
        except Exception:                                # noqa: BLE001
            return None

''')
R.replace('''                        "params": {"channels": ["cfbenchmarks_value"],
                                   "index_ids": self.ids}}))
                    self.stats["connects"] += 1''', '''                        "params": {"channels": ["cfbenchmarks_value"],
                                   "index_ids": self.ids}}))
                    if INDEX_5HZ != "off":
                        # v-hedge5: the 5 Hz channel, for the indices it carries
                        _ids5 = [i for i in self.ids if i in INDEX_5HZ_IDS]
                        if _ids5:
                            cid += 1
                            await ws.send(json.dumps({
                                "id": cid, "cmd": "subscribe",
                                "params": {"channels": ["cfbenchmarks_value_5hz"],
                                           "index_ids": _ids5}}))
                            self.stats["sub5"] += 1
                    self.stats["connects"] += 1''')

# 3. fair5: fair()'s arithmetic with the current print handed in
R.before('''def billed_fee(price, count=1):''', '''def fair5(idx, iid, close_s, now_s, strike, sigma, spot, round_digits=None):
    """v-hedge5: fair() with the CURRENT print taken from `spot` (the newest
    5 Hz print) instead of idx.spot(); the locked prints, the remaining
    count and the arithmetic are fair()'s, line for line (projection():
    mu = (locked + r x spot) / N_AVG). None when the window or the spot
    cannot be read. The self-test proves fair5(.., idx.spot()[1]) == fair()."""
    if spot is None:
        return None
    part = idx.partial(iid, close_s, now_s)
    if part is None:
        return None
    locked, r = part
    mu = (locked + r * float(spot)) / N_AVG
    K = eff_strike(strike, round_digits)
    if r <= 0:
        return 1.0 if mu >= K else 0.0
    sd = sigma * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        return 1.0 if mu >= K else 0.0
    return conf_of((mu - K) / sd)


''')

# 4. the hedge pass: the 5 Hz belief, the hedge-mode merge, the shadow queue, the alarm's fields
R.replace('''                    if _hmkt is not None:                # K3: index stale
                        _belief = (_hmkt if _hmodel is None
                                   else min(_hmodel, _hmkt))
''', '''                    if _hmkt is not None:                # K3: index stale
                        _belief = (_hmkt if _hmodel is None
                                   else min(_hmodel, _hmkt))
                    # v-hedge5: the belief on the newest 5 Hz print, when the
                    # flag is on and the index has a print newer than its
                    # newest whole second. Same strike, sigma, widening and
                    # locked prints as the line above; only the current
                    # print is fresher. hedge: the LOWER belief fires (it can
                    # only add a trigger); shadow: recorded, never sent.
                    _hm5 = _h5ms = None
                    if INDEX_5HZ != "off" and _hsg is not None:
                        try:
                            _h5p = idx.fast_spot(_hiid)
                            if _h5p is not None:
                                _hf5 = fair5(idx, _hiid, _hcs, now_s, _hstrike,
                                             _hsg * SIGMA_STRESS
                                             * widen_factor(idx, _hiid, _hsg, _hwant),
                                             _h5p[1], round_digits=_hdig)
                                if _hf5 is not None:
                                    _hm5 = (_hf5 if _hwant == "yes" else 1.0 - _hf5)
                                    _h5ms = int(_h5p[0])
                                    last_belief5[_htk] = float(_hm5)
                        except Exception:                # noqa: BLE001
                            _hm5 = _h5ms = None
                    _hb1 = _belief           # v-hedge5: the 1/s belief, for the records
                    if INDEX_5HZ == "hedge" and _hm5 is not None:
                        _belief = min(_belief, _hm5)
''')
R.replace('''                    if _htrig != "jump" and not hedge_should_fire(_belief):
                        continue
''', '''                    # v-hedge5 shadow: the first second the 5 Hz belief is
                    # under the line while the 1 Hz belief is not -- queued
                    # here, written below the hedge pass (_h5_flush)
                    if (INDEX_5HZ == "shadow" and _hm5 is not None
                            and _htrig != "jump" and _hid not in h5_shadow_sent
                            and hedge_should_fire(_hm5)
                            and not hedge_should_fire(_belief)):
                        h5_shadow_sent.add(_hid)
                        h5_shadow_q.append((_hid, _hcs, _htk, _hwant, _hn_orig, _hn,
                                            _belief, _hm5, _h5ms, _htau, _hcost))
                    if _htrig != "jump" and not hedge_should_fire(_belief):
                        continue
''')
R.replace('''                                "market_belief": round(_hmkt, 5)}
                               if _hmkt is not None else {}))
''', '''                                "market_belief": round(_hmkt, 5)}
                               if _hmkt is not None else {}),
                            # v-hedge5: both clocks' beliefs and the fast print,
                            # whenever the 5 Hz feed is read; by_5hz = the 5 Hz
                            # belief was under the line and the 1 Hz one not
                            **({"belief_1hz": round(_hb1, 5),
                                "belief5": (round(_hm5, 5) if _hm5 is not None
                                            else None),
                                "fast_ms": _h5ms,
                                "by_5hz": bool(_hm5 is not None
                                               and hedge_should_fire(_hm5)
                                               and not hedge_should_fire(_hb1))}
                               if INDEX_5HZ != "off" else {}))
''')

# 5. the loop's state, next to v-0925v JS's
R.after('''    jump_shadow_q = []       # v-0925v JS: what the hedge pass saw, written below it
''', '''    h5_shadow_q = []         # v-hedge5: what the hedge pass saw, written below it
    h5_shadow_sent = set()   # v-hedge5: positions whose 5 Hz shadow is on record
    last_belief5 = {}        # v-hedge5: ticker -> the newest 5 Hz belief (hedge_quote)
    h5_feed = {"t0": None, "said": False}   # v-hedge5: index5_up / index5_silent, once
''')

# 6. the flush, above reconcile(), and its call below the hedge pass
R.before('''    def reconcile():
        """Book settled P&L so the loss abort is a REAL brake, not a nominal one.''', '''    def _h5_flush():
        """v-hedge5: the hedge5_shadow records the hedge pass queued (ONE per
        position: the first second its 5 Hz belief was under the line while
        the 1 Hz belief was not), written BELOW the pass; then, once, whether
        the 5 Hz feed arrived at all (index5_up with its counters, or
        index5_silent INDEX_5HZ_SILENT_S after the first look). Reads the
        book; sends nothing, spends no try, marks nothing. Never raises."""
        try:
            _q = list(h5_shadow_q)
            del h5_shadow_q[:]
            for (hid_, cs_, tk_, want_, n_orig_, n_left_, b1_, b5_, fms_,
                 tau_, entry_) in _q:
                _f = h5_shadow_fields(
                    book, tk_, want_, n_orig_, n_left_, b1_, b5_, tau_, fms_,
                    (cs_ - entry_at[hid_]) if hid_ in entry_at else None)
                rec("hedge5_shadow", ticker=tk_, close_s=cs_, want=want_,
                    entry=entry_, live=bool(live), **_f)
                print(f"  5Hz SHADOW {tk_}: belief {b5_:.3f} on the 5 Hz print vs "
                      f"{b1_:.3f}, {_f.get('outcome')}: {_f.get('side')} "
                      f"{_f.get('n')} @ {_f.get('ask')}; nothing sent")
        except Exception:                                # noqa: BLE001
            try:
                del h5_shadow_q[:]
            except Exception:                            # noqa: BLE001
                pass
        try:
            if not h5_feed["said"]:
                _now5 = time.time()
                if h5_feed["t0"] is None:
                    h5_feed["t0"] = _now5
                _st5 = dict(getattr(idx, "stats", None) or {})
                _ids5 = sorted(set(getattr(idx, "ids", None) or ()) & INDEX_5HZ_IDS)
                if _st5.get("fast_ticks", 0) > 0:
                    h5_feed["said"] = True
                    rec("index5_up", mode=INDEX_5HZ, ids=_ids5,
                        fast_ticks=_st5.get("fast_ticks", 0),
                        fast_first=_st5.get("fast_first", 0),
                        fast_dup=_st5.get("fast_dup", 0), sub5=_st5.get("sub5", 0))
                    print(f"  5Hz index feed up: {_st5.get('fast_ticks', 0)} fast prints")
                elif _now5 - h5_feed["t0"] >= INDEX_5HZ_SILENT_S:
                    h5_feed["said"] = True
                    rec("index5_silent", mode=INDEX_5HZ, ids=_ids5,
                        after_s=round(_now5 - h5_feed["t0"], 1),
                        sub5=_st5.get("sub5", 0),
                        stats={k: v for k, v in _st5.items()
                               if isinstance(v, (int, float))})
                    print(f"  !!! 5Hz index feed SILENT after "
                          f"{_now5 - h5_feed['t0']:.0f}s (ids {_ids5})")
        except Exception:                                # noqa: BLE001
            h5_feed["said"] = True

''')
R.replace('''        if jump_shadow_q:
            _js_flush()
''', '''        if jump_shadow_q:
            _js_flush()
        # v-hedge5: the 5 Hz shadow's records and the feed check, also below it
        if h5_shadow_q or (INDEX_5HZ != "off" and not h5_feed["said"]):
            _h5_flush()
''')

# 7. the per-second quote carries the 5 Hz belief while the feed is read
R.replace('''                        belief_calc_age_s=(None if _qbt is None
                                           else now_s - _qbt),''', '''                        belief_calc_age_s=(None if _qbt is None
                                           else now_s - _qbt),
                        # v-hedge5: the belief on the newest 5 Hz print
                        **({"belief5": (round(last_belief5[_qtk], 5)
                                        if last_belief5.get(_qtk) is not None
                                        else None)}
                           if INDEX_5HZ != "off" else {}),''')

# 8. pinned in every offline world, watched by the give-back guard
R.replace('''    "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW")


def _offline_trade_loop(''', '''    "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW", "INDEX_5HZ")


def _offline_trade_loop(''')
R.replace('''                 "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW")


def _selftest_body():''', '''                 "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW", "INDEX_5HZ")


def _selftest_body():''')

# 9. the offline world: a planted fast print and 5 Hz belief
R.before('''        def sigma(self, iid):
            _count("sigma")
            return 0.0005
''', '''        def fast_spot(self, iid):
            # v-hedge5: a world may plant the newest 5 Hz print, fast(t) ->
            # (t_ms, value) or None; unplanted, every world reads None
            _count("fast_spot")
            _fs = (by_iid.get(iid) or {}).get("fast")
            return _fs(clock.t - t0) if callable(_fs) else None

''')
R.before('''    def _fair(idx, iid, close_s, now_s, strike, sigma, round_digits=None):
        _count("fair")''', '''    def _fair5(idx, iid, close_s, now_s, strike, sigma, spot, round_digits=None):
        # v-hedge5: a world plants fair5(t) -> P(YES) on the fast print, at
        # WALL time (a 5 Hz print lands mid-second); unplanted reads None
        _count("fair5")
        _mf5 = by_iid[iid].get("fair5")
        return _mf5(clock.t - t0) if callable(_mf5) else None

''')
R.replace('''    saved = {k: g[k] for k in ("time", "get", "fair", "SIZE", "DAYLOSS_FILE",''',
          '''    saved = {k: g[k] for k in ("time", "get", "fair", "fair5", "SIZE", "DAYLOSS_FILE",''')
R.replace('''        g["fair"] = _fair
''', '''        g["fair"] = _fair
        g["fair5"] = _fair5
''')

# 10. the flag and the start record
R.before('''    ap.add_argument("--hedge-jump-shadow", type=float, default=None,''', '''    ap.add_argument("--index-5hz", choices=("off", "shadow", "hedge"), default=None,
                    help="v-hedge5: also read the settlement index's 5 Hz channel "
                         "(BTC ETH SOL XRP DOGE). shadow: the hedge's belief on the "
                         "newest 5 Hz print is recorded (hedge5_shadow: what the "
                         "belief hedge would have bought, first second under the "
                         "line), nothing is sent; hedge: the belief hedge fires on "
                         "the lower of the 1 Hz and 5 Hz beliefs. Off by default "
                         "(= 0925v).")
''')
R.after('''        globals()["HEDGE_JUMP_SHADOW"] = float(a.hedge_jump_shadow)
''', '''    if a.index_5hz is not None:
        globals()["INDEX_5HZ"] = str(a.index_5hz)          # v-hedge5
''')
R.after('''        hedge_jump_shadow=HEDGE_JUMP_SHADOW,                # v-0925v JS
''', '''        index_5hz=INDEX_5HZ,                                # v-hedge5
''')

# 11. the self-test: the frame parser, fast_spot, fair5 == fair, the source shape, and driven worlds
R.before('''    # ---- B: the 3rd bet out, the brake moved, SIZE and every order the same''', '''    # ---- v-hedge5 (2026-11-10): --index-5hz --------------------------------
    def _h5fr(typ, t_ms, val):
        return json.dumps({"type": typ, "sid": 7, "seq": 1,
                           "msg": {"index_id": "BRTI",
                                   "data": json.dumps({"type": "value", "time": int(t_ms),
                                                       "id": "BRTI", "value": str(val)})}})
    _h5was = INDEX_5HZ
    _h5S = int(time.time()) - 1
    try:
        globals()["INDEX_5HZ"] = "off"
        _h5i0 = IndexWS(["BRTI"])
        _h5i0.on_frame(_h5fr("cfbenchmarks_value_5hz", _h5S * 1000 + 200, "79050.0"))
        _h5i0.on_frame(_h5fr("cfbenchmarks_value_5hz", _h5S * 1000, "79050.0"))
        ck(not _h5i0.ticks.get("BRTI") and not _h5i0.fast
           and _h5i0.stats["cfbenchmarks_value_5hz"] == 2 and _h5i0.stats["ticks"] == 0
           and _h5i0.fast_spot("BRTI") is None,
           "v-hedge5 NULL: with --index-5hz off a 5 Hz frame -- sub-second or top "
           "of the second -- is counted and dropped like any other channel's")
        globals()["INDEX_5HZ"] = "shadow"
        _h5i = IndexWS(["BRTI"])
        for _h5k in range(36, 0, -1):
            _h5i.on_frame(_h5fr("cfbenchmarks_value", (_h5S - _h5k) * 1000, 79000.0 + _h5k))
        _h5i.on_frame(_h5fr("cfbenchmarks_value", _h5S * 1000, "79046.47"))
        _h5i.on_frame(_h5fr("cfbenchmarks_value_5hz", _h5S * 1000 + 200, "79050.0"))
        _h5i.on_frame(_h5fr("cfbenchmarks_value_5hz", _h5S * 1000 + 100, "79049.0"))
        _h5fs = _h5i.fast_spot("BRTI")
        ck(_h5i.ticks["BRTI"].get(_h5S) == 79046.47 and _h5S + 1 not in _h5i.ticks["BRTI"]
           and _h5i.stats["fast_ticks"] == 2 and _h5fs == (_h5S * 1000 + 200, 79050.0)
           and _h5i.spot("BRTI")[1] == 79046.47,
           "v-hedge5: a SUB-second 5 Hz print stays OUT of the settlement ticks and "
           "spot(); fast_spot() serves the NEWEST one (an older one arriving late "
           "does not replace it): %r" % (_h5fs,))
        _h5i.on_frame(_h5fr("cfbenchmarks_value_5hz", _h5S * 1000, "79999.0"))
        _h5i.on_frame(_h5fr("cfbenchmarks_value_5hz", (_h5S + 1) * 1000, "79051.0"))
        ck(_h5i.ticks["BRTI"].get(_h5S) == 79046.47 and _h5i.stats["fast_dup"] == 1
           and _h5i.ticks["BRTI"].get(_h5S + 1) == 79051.0 and _h5i.stats["fast_first"] == 1
           and _h5i.fast_spot("BRTI") is None,
           "v-hedge5: a TOP-of-second 5 Hz print enters the ticks only for a second "
           "not yet held (a held second is never overwritten from it), and a fast "
           "print older than the newest whole second is no longer served")
        _h5i.on_frame(_h5fr("cfbenchmarks_value", (_h5S + 1) * 1000, "79052.0"))
        ck(_h5i.ticks["BRTI"].get(_h5S + 1) == 79052.0,
           "v-hedge5: the 1 Hz print still overwrites the second, as it always has")
        _h5i.on_frame(_h5fr("cfbenchmarks_value_5hz", (_h5S + 1) * 1000 + 400, "79053.0"))
        _h5cs = _h5S + 25
        _h5a = fair(_h5i, "BRTI", _h5cs, _h5S + 1, 79040.0, 4.0)
        _h5b = fair5(_h5i, "BRTI", _h5cs, _h5S + 1, 79040.0, 4.0, _h5i.spot("BRTI")[1])
        _h5c = fair5(_h5i, "BRTI", _h5cs, _h5S + 1, 79040.0, 4.0, _h5i.fast_spot("BRTI")[1])
        ck(_h5a is not None and _h5b is not None and abs(_h5a - _h5b) < 1e-12
           and _h5c is not None and _h5c >= _h5a
           and fair5(_h5i, "BRTI", _h5cs, _h5S + 1, 79040.0, 4.0, None) is None,
           "v-hedge5: fair5 on the held print IS fair() (%r vs %r); on a higher fast "
           "print it is higher (%r); no print, no number" % (_h5a, _h5b, _h5c))
        _h5j = IndexWS(["BRTI"])
        _h5o = int(time.time()) - 10
        _h5j.on_frame(_h5fr("cfbenchmarks_value", _h5o * 1000, "79000.0"))
        _h5j.on_frame(_h5fr("cfbenchmarks_value_5hz", _h5o * 1000 + 600, "79001.0"))
        ck(_h5j.fast_spot("BRTI", max_age_s=2) is None
           and _h5j.fast_spot("BRTI", max_age_s=30) == (_h5o * 1000 + 600, 79001.0),
           "v-hedge5: a fast print newer than the newest second but older than "
           "MAX_INDEX_AGE_S is not served (a frozen 5 Hz feed cannot hold a belief)")
    finally:
        globals()["INDEX_5HZ"] = _h5was
    _h5run = inspect.getsource(IndexWS._run)
    ck(_h5run.index('if INDEX_5HZ != "off":') < _h5run.index('"cfbenchmarks_value_5hz"')
       and "i in INDEX_5HZ_IDS" in _h5run
       and INDEX_5HZ_IDS == frozenset(("BRTI", "ETHUSD_RTI", "SOLUSD_RTI",
                                       "XRPUSD_RTI", "DOGEUSD_RTI")),
       "v-hedge5 by source: the 5 Hz channel is subscribed only with the flag on, "
       "for the five indices it carries")
    _h5tl = inspect.getsource(trade_loop)
    ck(_h5tl.index('if INDEX_5HZ != "off" and _hsg is not None:')
       < _h5tl.index("_h5p = idx.fast_spot(_hiid)")
       < _h5tl.index('if INDEX_5HZ == "hedge" and _hm5 is not None:')
       < _h5tl.index("_belief = min(_belief, _hm5)")
       < _h5tl.index('if _htrig != "jump" and not hedge_should_fire(_belief):')
       and _h5tl.count("_belief = min(_belief, _hm5)") == 1
       and _h5tl.index("h5_shadow_q.append(") < _h5tl.index("if jump_shadow_q:")
       < _h5tl.index("\\n            _h5_flush()\\n")
       and _DEFAULT_INDEX_5HZ == "off"
       and "INDEX_5HZ" in _OFFLINE_PINNED_FLAGS and "INDEX_5HZ" in _FLAG_GLOBALS
       and 'globals()["INDEX_5HZ"] = str(a.index_5hz)' in inspect.getsource(main)
       and "index_5hz=INDEX_5HZ," in inspect.getsource(main),
       "v-hedge5 by source: the 5 Hz belief is read only with the flag on, merged "
       "(lower wins) only in hedge mode and ahead of the line test, the shadow is "
       "queued in the pass and written below it; the flag ships off, is pinned in "
       "every offline world and named in the start record")
    _h5t0 = 1_800_000_000 - 30 + 0.1

    def _h5m(n, fair_of, fast_from=None, fast_to=99.0, f5=0.30, book_of=(lambda t: _ob(0.94, 0.05))):
        m = {"tk": "KXH5%d15M-H5" % n, "series": "KXH5%d15M" % n,
             "iid": "H5%d" % n, "strike": 100.0, "fair": fair_of, "book": book_of}
        if fast_from is not None:
            m["fast"] = (lambda t: (int(1000 * (_h5t0 + t)), 100.4)
                         if fast_from <= t < fast_to else None)
            m["fair5"] = (lambda t: f5 if fast_from <= t < fast_to else 0.999)
        return m
    _h5flip = lambda t: 0.999 if t < 7.0 else 0.30           # the 1 Hz belief falls at index time 7
    _h5base = {"HEDGE_BELIEF": 0.40, "HEDGE_PROP": False}
    _h5sh = _offline_trade_loop([_h5m(1, _h5flip, fast_from=5.5)], live=True,
                                flags=dict(_h5base, INDEX_5HZ="shadow"))
    _h5shs = _kinds(_h5sh, "hedge5_shadow")
    _h5sha = _kinds(_h5sh, "hedge_alarm")
    ck(_h5sh["raised"] is None and len(_h5shs) == 1
       and 5.5 <= _h5shs[0]["t"] < 6.0 and _h5shs[0].get("side") == "no"
       and abs(float(_h5shs[0].get("n") or 0) - 5.0) < 1e-9
       and abs(float(_h5shs[0].get("ask") or 0) - 0.06) < 1e-9
       and abs(float(_h5shs[0].get("belief5") or 0) - 0.30) < 1e-9
       and abs(float(_h5shs[0].get("belief") or 0) - 0.999) < 1e-9
       and _h5shs[0].get("would_send") is True and _h5shs[0].get("sent") is False
       and _h5shs[0].get("fast_ms") is not None
       and _h5sha and _h5sha[0]["t"] >= 6.5 and _h5sha[0].get("trigger") == "belief"
       and _h5sha[0].get("by_5hz") is False
       and abs(_hedged(_h5sh, "KXH5115M-H5") - 5.0) < 1e-9,
       "v-hedge5 DRIVEN shadow: the 5 Hz belief falls to 0.30 at t 5.5, the 1 Hz one "
       "at t 7 -- ONE hedge5_shadow at t %s (no 5 @ 6c, would_send, nothing sent), "
       "and the real belief hedge still fires at t %s and covers all 5"
       % ([r["t"] for r in _h5shs][:1], [r["t"] for r in _h5sha][:1]))
    _h5hd = _offline_trade_loop([_h5m(2, _h5flip, fast_from=5.5)], live=True,
                                flags=dict(_h5base, INDEX_5HZ="hedge"))
    _h5hda = _kinds(_h5hd, "hedge_alarm")
    _h5of = _offline_trade_loop([_h5m(3, _h5flip, fast_from=5.5)], live=True,
                                flags=dict(_h5base))
    _h5ofa = _kinds(_h5of, "hedge_alarm")
    ck(_h5hd["raised"] is None and _h5hda and 5.5 <= _h5hda[0]["t"] < 6.0
       and _h5hda[0].get("by_5hz") is True
       and abs(float(_h5hda[0].get("belief5") or 0) - 0.30) < 1e-9
       and abs(float(_h5hda[0].get("belief_1hz") or 0) - 0.999) < 1e-9
       and abs(_hedged(_h5hd, "KXH5215M-H5") - 5.0) < 1e-9
       and not _kinds(_h5hd, "hedge5_shadow")
       and _h5of["raised"] is None and _h5ofa and _h5ofa[0]["t"] >= 6.5
       and "belief5" not in _h5ofa[0] and not _kinds(_h5of, "hedge5_shadow")
       and abs(_hedged(_h5of, "KXH5315M-H5") - 5.0) < 1e-9,
       "v-hedge5 DRIVEN hedge: the same market hedges at t %s on the 5 Hz print "
       "(by_5hz, all 5 covered) where the shipped flag off hedges at t %s, and off "
       "writes no 5 Hz field and no shadow"
       % ([r["t"] for r in _h5hda][:1], [r["t"] for r in _h5ofa][:1]))
    _h5won = lambda t: 0.999
    _h5rs = _offline_trade_loop([_h5m(4, _h5won, fast_from=5.5, fast_to=5.9)], live=True,
                                flags=dict(_h5base, INDEX_5HZ="shadow"))
    _h5rh = _offline_trade_loop([_h5m(5, _h5won, fast_from=5.5, fast_to=5.9)], live=True,
                                flags=dict(_h5base, INDEX_5HZ="hedge"))
    _h5nf = _offline_trade_loop([_h5m(6, _h5flip)], live=True,
                                flags=dict(_h5base, INDEX_5HZ="hedge"))
    _h5nfa = _kinds(_h5nf, "hedge_alarm")
    ck(_h5rs["raised"] is None and len(_kinds(_h5rs, "hedge5_shadow")) == 1
       and not _kinds(_h5rs, "hedge_alarm") and _hedged(_h5rs, "KXH5415M-H5") == 0
       and _h5rh["raised"] is None and _kinds(_h5rh, "hedge_alarm")
       and _kinds(_h5rh, "hedge_alarm")[0].get("by_5hz") is True
       and _h5nf["raised"] is None and _h5nfa and _h5nfa[0]["t"] >= 6.5
       and _h5nfa[0].get("belief5") is None and _h5nfa[0].get("by_5hz") is False,
       "v-hedge5 DRIVEN: a 5 Hz dip that recovers is ONE shadow record and no "
       "order in shadow mode, a hedge in hedge mode (the false alarm the shadow "
       "exists to count); an index with no 5 Hz print (BNB, ZEC ...) hedges in "
       "hedge mode exactly when it does today (t %s)" % ([r["t"] for r in _h5nfa][:1],))

''')

R.write()
print("patched", PR, sha12(PR))
print("v-0925w flag, = 0925v behaviour when omitted: --index-5hz off|shadow|hedge (off); deploy runs --index-5hz shadow")
