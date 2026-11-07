"""Apply v-0925u to a COPY of the live pin build (C:\\kals-live-0925t: research\\pinrun.py code_sha
9e04c0252ac9; pintake.py b3c7bb48abb5 and ordercli.py 467782077a23 are NOT touched). Patches pinrun.py in place,
CRLF preserved; every anchor must occur exactly once; refuses an already-patched tree and a tree that is not 0925t.
usage: python patch_0925u.py <build_dir>      (build_dir holds research\\pinrun.py)

One new flag, off when omitted (= 0925t exactly):

  --cheap-window START_H END_H FLOOR   (v-cheapwin) a FIRST buy (nothing held on the market) whose ask is under
      FLOOR, in a market closing START_H <= Eastern hour < END_H, is refused, and the market is refused for the
      rest of its close (the rule skips a market, as v-wrongside does). After every other gate, so it judges only
      a buy that would otherwise go out; before the signal record. Live runs 6 10 0.98.

      THE SHADOW, so "what it would have been without the rule" comes from this log alone:
        * the first refusal (kind refused, gate cheap_window) carries what the send site would have ASKED for the
          buy (cw_shadow_size: A35's sweep, the A45 / A48 / A53 wideners, A46's leg re-cap, the coin and series
          caps; the close budget left out) and the ladder's average price for that many (cw_vwap);
        * each second until the close, the trajectory sampler's own reading of the market (the fair the gate saw,
          the same book read) is checked for the belief hedge pin would have bought: the first second the shadow
          side's belief is under --hedge-belief, the other side's ask and 1.0x or (at >= --hedge-odds-min-tau s)
          --hedge-odds-mult x the contracts -- the panic leg plus the v-oddsmult extra;
        * from 20 s after the close, one throttled GET /markets/<ticker> (reconcile()'s read) books the result as
          kind cheap_window_settled. Below the hedge pass, guarded, decides nothing.
      The phone's /fixes prices it (research/botdata/fixes.py, change K).
"""
import hashlib
import os
import sys

B = sys.argv[1]
PR = os.path.join(B, "research", "pinrun.py")
BASE_PINRUN = "9e04c0252ac9"


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


assert sha12(PR) == BASE_PINRUN, "research/pinrun.py is not 0925t (%s)" % sha12(PR)
R = Src(PR)
assert "CHEAP_WINDOW" not in R.s and "cheap_window" not in R.s and "cw_shadow" not in R.s, "already patched"
assert "LATE_BYPASS_FIX" in R.s and "JUMP_HEDGE_MIN_ASK" in R.s, "not the 0925t build"

# 1. the constant, after the v-0925t ones
R.after('''# v-latebypass (2026-11-04): --late-bypass-fix on = the late multiple only past late_boost_ok; off (shipped) = 0925r sizing
LATE_BYPASS_FIX = False
_DEFAULT_LATE_BYPASS_FIX = False
''', '''# v-cheapwin (2026-11-07). The operator, after two morning losses: "It's
# always whenever the morning starts REALLY good this happens. Why" -- and on
# the answer, "Sure. Make sure to log and track the difference it makes and
# what it would've been without the rule". 2,909 live markets 09-08..11-07:
# the losses do NOT follow good mornings (after the best quarter of mornings
# 1.48% of markets flipped, against 1.86% overall); they sit in markets
# CLOSING 06:00-10:00 ET, the only stretch of the day that lost money from
# October on (10-01..10-15 -$123.26, 10-16..10-31 -$9.51, 11-01..11-07
# -$140.41, while the rest of the day made +$1,767.17), and inside it on FIRST
# buys under 98c (all 60 days: 287 markets, -$73.31; at 98c and up +$72.64).
# A shuffle of the hours makes a 4-hour window that bad 3.5% of the time, and
# September went the other way (+$272.52), so this is a trial with a shadow,
# not a settled fact. --cheap-window START END FLOOR: a FIRST buy (nothing
# held on the market) whose ask is under FLOOR, in a market closing
# START <= Eastern hour < END, is refused and the market is refused for the
# close (as v-wrongside skips one). Every first refusal opens a shadow (what
# the send site would have asked, the belief hedge it would have bought, the
# result), booked as cheap_window_settled, so the tracker prices "without
# the rule" from this log alone. None = off (the shipped value).
CHEAP_WINDOW = None             # (start_h, end_h, floor)
_DEFAULT_CHEAP_WINDOW = None
''')

# 2. the pure helpers, next to band_blocked (A53's band skip, the same family)
R.before('def band_mult(price, bands=_PB_UNSET):\n', '''def cheap_window_block(price, close_s, window=_PB_UNSET):
    """v-cheapwin: True when `window` (CHEAP_WINDOW unless given) is set, the
    market closes inside its Eastern hours [start, end) and `price` is under
    its floor. The close's own Eastern wall clock (et_offset_s: zoneinfo or
    the US rule, never a bare offset), so for 6..10 a 06:00 close is in and a
    10:00 close is out. Bad input is never a refusal."""
    w = CHEAP_WINDOW if window is _PB_UNSET else window
    if not w:
        return False
    try:
        start, end, floor = float(w[0]), float(w[1]), float(w[2])
        p, cs = float(price), float(close_s)
        _tm = globals().get("_REAL_TIME", time)         # the self-test fakes time()
        g = _tm.gmtime(cs + et_offset_s(cs))
        h = g.tm_hour + g.tm_min / 60.0
    except (TypeError, ValueError, IndexError, OverflowError, OSError):
        return False
    return start <= h < end and p < floor - 1e-9


def cw_shadow_size(take_n, size, touch, flat, tapered, caps=(), stage_cap=None,
                   hard_caps=()):
    """v-cheapwin: the contracts the send site would have ASKED for a refused
    buy, by its steps in its order, from numbers read at the refusal: A35's
    sweep (min(SIZE, the tapered depth under the limit) when that is more than
    the leg's take), each widener's max(n, min(cap, avail)) with avail the
    touch or the flat depth (A45 one-coin, A48 late, A53 band), A46's leg
    re-cap, then the coin / series caps. The close budget is left out: it
    binds only when other markets in the same close already spent it. Never
    raises; a bad input gives the leg's own take."""
    try:
        n = max(0.0, float(take_n))
        deep = tapered if tapered is not None else flat
        if deep is not None and float(deep) > n:
            n = min(float(size), float(deep))
        avail = max(float(touch or 0.0), float(flat or 0.0))
        for c in caps or ():
            if c is not None:
                n = max(n, min(float(c), avail))
        if stage_cap is not None:
            n = min(n, float(stage_cap))
        for c in hard_caps or ():
            if c is not None:
                n = min(n, float(c))
        return round(n, 2)
    except (TypeError, ValueError):
        try:
            return round(max(0.0, float(take_n)), 2)
        except (TypeError, ValueError):
            return 0.0


def cw_vwap(ladder, n, limit):
    """v-cheapwin: (average price, contracts) of the first `n` contracts of
    `ladder` -- [[price, size], ...] cheapest first, as the signal stores it --
    at or under `limit`. (None, 0.0) when nothing is there. Never raises."""
    got = cost = 0.0
    try:
        want_n, lim = float(n), float(limit)
        for px, sz in ladder or ():
            px, sz = float(px), float(sz)
            if px > lim + 1e-9 or got >= want_n - 1e-9:
                break
            take = min(sz, want_n - got)
            got += take
            cost += take * px
    except (TypeError, ValueError):
        pass
    return (round(cost / got, 5) if got > 0 else None), round(got, 2)


''')

# 3. the flag
R.before('    ap.add_argument("--jump-hedge-min-ask", type=float, default=None,\n', '''    ap.add_argument("--cheap-window", type=float, nargs=3, default=None,
                    metavar=("START_H", "END_H", "FLOOR"),
                    help="v-cheapwin: refuse a FIRST buy whose ask is under "
                         "FLOOR in a market closing START_H <= Eastern hour < "
                         "END_H, and skip that market for the close; every "
                         "refusal is shadowed (the size it would have asked, "
                         "the belief hedge, the result: cheap_window_settled). "
                         "Off by default; live runs 6 10 0.98.")
''')
R.after('        globals()["JUMP_HEDGE_MIN_ASK"] = float(a.jump_hedge_min_ask)\n', '''    if a.cheap_window is not None:
        _cw_s, _cw_e, _cw_f = (float(_x) for _x in a.cheap_window)
        if not (0.0 <= _cw_s < _cw_e <= 24.0 and 0.5 < _cw_f <= 1.0):
            raise SystemExit("--cheap-window needs 0 <= START_H < END_H <= 24 "
                             "and 0.5 < FLOOR <= 1, got %r" % (a.cheap_window,))
        globals()["CHEAP_WINDOW"] = (_cw_s, _cw_e, _cw_f)
''')

# 4. pinned in every offline world, watched by the give-back guard, named in the start record
R.replace('''    "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX")


def _offline_trade_loop(''', '''    "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX",
    "CHEAP_WINDOW")


def _offline_trade_loop(''')
R.replace('''                 "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX")


def _selftest_body():''', '''                 "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX",
                 "CHEAP_WINDOW")


def _selftest_body():''')
R.after('        late_bypass_fix=("on" if LATE_BYPASS_FIX else "off"),\n', '''        # v-cheapwin: the window and its floor (None = off), so a read can tell the runs apart
        cheap_window=(list(CHEAP_WINDOW) if CHEAP_WINDOW else None),
''')

# 5. the loop's state, next to v-wrongside's
R.before('    jump_capped_said = set() # v-jumpcap8: (close_s, ticker) logged once\n', '''    cw_blocked = set()       # v-cheapwin: (close_s, ticker) refused once =
                             # refused for the close (the rule skips a market)
    cw_shadow = {}           # v-cheapwin: (close_s, ticker) -> the refused buy's
                             # shadow, until cheap_window_settled is written
''')

# 6. the shadow's three helpers, above reconcile() (whose GET the settle reuses)
R.before('''    def reconcile():
        """Book settled P&L so the loss abort is a REAL brake, not a nominal one.
''', '''    def _cw_open(tk_, want_, price_, f_, take_n_, touch_, tau_, leg_, held_,
                 fsz_, ssz_, csz_, ladder_):
        """v-cheapwin: a refused buy's shadow -- what the send site would have
        asked for it and at what average price -- from pure reads: the book's
        depth and rungs under the same sweep limit, the bank and the mark the
        wideners read. Never raises; a failed read leaves the leg's own take at
        its own ask (est_err says which)."""
        sh = {"want": want_, "price": round(float(price_), 4),
              "fair": round(float(f_), 5), "tau": tau_, "leg": leg_,
              "window": list(CHEAP_WINDOW) if CHEAP_WINDOW else None,
              "n_ask": round(float(take_n_ or 0.0), 2),
              "px": round(float(price_), 4), "got": None, "lim": None}
        try:
            _lim = sweep_limit(f_, price_, want_)
            if leg_ in ("early", "early_once") and EARLY_MAX_PRICE < 1.0:
                _lim = min(_lim, EARLY_MAX_PRICE)
            _flat = _tap = None
            if SWEEP_DEPTH and _lim > price_ + 1e-9:
                _flat = float(book.buyable(tk_, want_, _lim))
                if TAPER:
                    _rungs = book.rungs(tk_, want_, _lim)
                    if _rungs:
                        _tap = taper_take(
                            _rungs, float(SIZE),
                            lambda _p, _f=f_, _w=want_: net_edge(_f, _p, _w))
            _bank, _hwm = state.get("bank"), state.get("hwm")
            _ours = f_ if want_ == "yes" else 1.0 - f_
            _late = (LATE_MULT > 1.0 and tau_ <= LATE_TAU
                     and csz_ is None and ssz_ is None
                     and (LATE_PIN is None or _ours >= LATE_PIN))
            _m = band_mult(price_)
            _caps = (one_coin_cap(SIZE, _bank, _hwm) if ONE_COIN_DEPTH else None,
                     one_coin_cap(SIZE, _bank, _hwm, mult=LATE_MULT) if _late else None,
                     one_coin_cap(SIZE, _bank, _hwm, mult=_m) if _m > 1.0 else None)
            _n = cw_shadow_size(take_n_, SIZE, touch_, _flat, _tap, _caps)
            if EARLY_TAU_MAX > TAU_MAX and leg_ != "full":
                _mult = max(_m, LATE_MULT if tau_ <= LATE_TAU else 1.0)
                _n = cw_shadow_size(_n, SIZE, 0.0, None, None,
                                    stage_cap=staged_take(tau_, _n, fsz_ * _mult, held_)[0])
            _n = cw_shadow_size(_n, SIZE, 0.0, None, None, hard_caps=(ssz_, csz_))
            _px, _got = cw_vwap(ladder_, _n, _lim)
            sh.update(n_ask=_n, lim=round(float(_lim), 4), got=_got,
                      px=(_px if _px is not None else sh["px"]),
                      flat=(None if _flat is None else round(_flat, 2)),
                      tapered=(None if _tap is None else round(float(_tap), 2)),
                      band_mult=_m, late=bool(_late), size=float(SIZE))
        except Exception as _cwe:                        # noqa: BLE001
            sh["est_err"] = type(_cwe).__name__
        return sh

    def _cw_watch(key_, f_, b_, tau_):
        """v-cheapwin: one second of a refused buy's shadow, off the trajectory
        sampler's own reading (the fair the gate saw, the same book read). The
        FIRST second the shadow side's belief is under HEDGE_BELIEF with the
        close still ahead marks the belief hedge pin would have bought: the
        other side's ask then, and 1.0x or (at >= HEDGE_ODDS_MIN_TAU s)
        HEDGE_ODDS_MULT x the shadow's contracts -- the panic leg plus the
        v-oddsmult extra. Decides nothing; never raises."""
        try:
            sh = cw_shadow.get(key_)
            if (sh is None or sh.get("hedge_px") is not None or f_ is None
                    or tau_ is None or tau_ < 1):
                return
            _bel = float(f_) if sh.get("want") == "yes" else 1.0 - float(f_)
            if _bel >= float(HEDGE_BELIEF):
                return
            _opp = "no" if sh.get("want") == "yes" else "yes"
            _ask = (b_ or {}).get(_opp + "_ask")
            if _ask is None or not (0.0 < float(_ask) < 1.0):
                return
            sh["hedge_px"] = round(float(_ask), 4)
            sh["hedge_tau"] = int(tau_)
            sh["hedge_belief"] = round(_bel, 5)
            sh["hedge_mult"] = (float(HEDGE_ODDS_MULT)
                                if tau_ >= HEDGE_ODDS_MIN_TAU else 1.0)
        except Exception:                                # noqa: BLE001
            pass

    def _cw_settle():
        """v-cheapwin: a shadowed market's result, read the way reconcile()
        reads one -- GET /markets/<ticker> no sooner than 20 s after the close
        and at most once per 15 s per market. Finalized: cheap_window_settled
        (side, result, won, the asked size and its price, the shadow hedge).
        Not final 900 s after the close: written with result None and
        dropped, so the dict stays bounded. One market's failure is kept to
        that market."""
        _now = time.time()
        for _k in list(cw_shadow):
            sh = cw_shadow.get(_k) or {}
            try:
                _cs, _tk = _k
                if (_now < _cs + 20
                        or _now < float(sh.get("recon_at") or 0.0) + 15.0):
                    continue
                sh["recon_at"] = _now
                _st, _b = trade_get("/markets/" + _tk)
                _m = ((_b.get("market") or {})
                      if (_st == 200 and isinstance(_b, dict)) else {})
                _res = _m.get("result") if _m.get("status") == "finalized" else None
                if _res not in ("yes", "no"):
                    if _now <= _cs + 900:
                        continue
                    _res = None
                cw_shadow.pop(_k, None)
                rec("cheap_window_settled", ticker=_tk, close_s=_cs, result=_res,
                    won=(None if _res is None else _res == sh.get("want")),
                    **{_x: sh.get(_x) for _x in (
                        "want", "price", "n_ask", "px", "got", "lim", "tau", "leg",
                        "fair", "size", "band_mult", "late", "est_err",
                        "hedge_px", "hedge_tau", "hedge_belief", "hedge_mult",
                        "window")})
            except Exception:                            # noqa: BLE001
                try:
                    if _now > float(_k[0]) + 900:
                        cw_shadow.pop(_k, None)
                except Exception:                        # noqa: BLE001
                    cw_shadow.pop(_k, None)

''')

# 7. the gate: after the LAST gate (v-wsfall10), before the signal record
R.before('                sig["spot_wrong"] = _ws[1]\n', '''                # v-cheapwin: a FIRST buy under the floor in a market closing
                # inside the window is refused, and the market for the close (as
                # v-wrongside). After every other gate, so it judges only a buy
                # that would otherwise go out; before the signal record, so a
                # refusal can never read as a lost race. The first refusal opens
                # the market's shadow (_cw_open), which the trajectory sampler
                # watches for the hedge and _cw_settle books after the close.
                _cw_k = (close_s, tk)
                if CHEAP_WINDOW and (_cw_k in cw_blocked or (
                        not _ws_held and cheap_window_block(price, close_s))):
                    if _cw_k not in cw_blocked:
                        cw_blocked.add(_cw_k)
                        cw_shadow[_cw_k] = _cw_open(
                            tk, want, price, f, take_n, size, tau, _leg46,
                            _held46, _fsz, _ssz, _csz, sig.get("ladder"))
                    _cw_sh = cw_shadow.get(_cw_k) or {}
                    _gate("cheap_window", close_s, tk, want=want, leg=_leg46,
                          tau=tau, price=round(price, 4), fair=round(f, 5),
                          window=list(CHEAP_WINDOW), size=float(take_n or SIZE),
                          n_ask=_cw_sh.get("n_ask"), px=_cw_sh.get("px"),
                          lim=_cw_sh.get("lim"), got=_cw_sh.get("got"),
                          est_err=_cw_sh.get("est_err"))
                    continue
''')

# 8. the shadow's hedge watch, off the trajectory sampler's own second
R.after('''                        entries_stopped=bool(state.get("entries_stopped")),
                        paused=bool(state.get("paused_on")))
''', '''                    if _jkey in cw_shadow:     # v-cheapwin: the shadow's hedge, this second's reading
                        _cw_watch(_jkey, _jf, _jb, _jtau)
''')

# 9. the shadow's settlement, below the hedge pass and the sampler, above the risk check
R.before('        # A69: THE RISK CHECK, NOW BELOW THE HEDGE PASS. It used to sit above\n', '''        # v-cheapwin: each refused cheap-window buy's shadow settles here,
        # BELOW the hedge pass (bookkeeping never outranks insurance, A71): one
        # throttled GET per market from 20 s after its close. Guarded; decides
        # nothing; an empty dict is no work.
        if cw_shadow:
            try:
                _cw_settle()
            except Exception:                            # noqa: BLE001
                pass

''')

# 10. the self-test: pure checks, the source shape, and two driven worlds
R.before('    _vs_ex = _vs_tl[_vs_tl.index("if _hx_n > 0 and _hfilled > 0:"):]\n', '''    # ---- v-cheapwin (2026-11-07) ------------------------------------------
    _cw_w = (6.0, 10.0, 0.98)
    _cw_utc = lambda y, mo, d, h, mi: calendar.timegm((y, mo, d, h, mi, 0))
    ck(cheap_window_block(0.9729, _cw_utc(2026, 11, 7, 13, 15), _cw_w)      # BNB 08:15 EST
       and not cheap_window_block(0.98, _cw_utc(2026, 11, 7, 13, 15), _cw_w)
       and not cheap_window_block(0.985, _cw_utc(2026, 11, 7, 13, 15), _cw_w)
       and cheap_window_block(0.97, _cw_utc(2026, 11, 7, 11, 0), _cw_w)        # 06:00 EST: in
       and not cheap_window_block(0.97, _cw_utc(2026, 11, 7, 10, 45), _cw_w)   # 05:45 EST: out
       and cheap_window_block(0.97, _cw_utc(2026, 11, 7, 14, 45), _cw_w)       # 09:45 EST: in
       and not cheap_window_block(0.97, _cw_utc(2026, 11, 7, 15, 0), _cw_w)    # 10:00 EST: out
       and cheap_window_block(0.97, _cw_utc(2026, 10, 20, 10, 0), _cw_w)       # 06:00 EDT: in
       and not cheap_window_block(0.97, _cw_utc(2026, 10, 20, 14, 0), _cw_w)   # 10:00 EDT: out
       and not cheap_window_block(0.97, _cw_utc(2026, 11, 7, 13, 15), None)
       and not cheap_window_block(None, _cw_utc(2026, 11, 7, 13, 15), _cw_w)
       and not cheap_window_block(0.97, None, _cw_w),
       "v-cheapwin: the window reads the CLOSE's Eastern hour on both sides of "
       "the 11-01 clock change (06:00 in, 10:00 out, 05:45 out), the floor is "
       "strict (98c itself trades), and no window / bad input refuses nothing")
    ck(cw_shadow_size(110.76, 388, 110.76, 505.77, 388.0, (None, None, 582.0)) == 505.77
       and cw_shadow_size(505.77, 388, 0.0, None, None, stage_cap=193.81) == 193.81
       and cw_shadow_size(40.0, 388, 40.0, 30.0, None, ()) == 40.0
       and cw_shadow_size(50.0, 388, 50.0, 900.0, 300.0, (), hard_caps=(None, 58.2)) == 58.2
       and cw_shadow_size("x", 388, 1, 1, 1) == 0.0
       and cw_vwap([[0.97, 110.76], [0.971, 23.01], [0.98, 242.0], [0.982, 18.0]], 193.81, 0.98)
       == (round((0.97 * 110.76 + 0.971 * 23.01 + 0.98 * 60.04) / 193.81, 5), 193.81)
       and cw_vwap([[0.97, 10.0], [0.99, 500.0]], 100.0, 0.98) == (0.97, 10.0)
       and cw_vwap(None, 5, 0.98) == (None, 0.0),
       "v-cheapwin sizing: the BNB 11-07 08:14 order is rebuilt from its own "
       "numbers (touch 110.76, flat 505.77, tapered 388, band cap 582 -> 505.77, "
       "the early re-cap -> 193.81 = what pin asked and filled); a depth under the "
       "take never shrinks it; coin caps bind last; the average price walks the "
       "ladder only to the limit")
    ck(_DEFAULT_CHEAP_WINDOW is None
       and 'globals()["CHEAP_WINDOW"] = (_cw_s, _cw_e, _cw_f)' in _vs_mn
       and "CHEAP_WINDOW" in _OFFLINE_PINNED_FLAGS and "CHEAP_WINDOW" in _FLAG_GLOBALS
       and "cheap_window=(list(CHEAP_WINDOW) if CHEAP_WINDOW else None)," in _vs_mn
       and "0.0 <= _cw_s < _cw_e <= 24.0 and 0.5 < _cw_f <= 1.0" in _vs_mn,
       "v-cheapwin FLAG: --cheap-window ships OFF, is checked and set by main(), "
       "pinned in every offline world, watched by the give-back guard and named "
       "in the start record (this process: %r)" % (CHEAP_WINDOW,))
    _cw_g = _vs_tl.index('_gate("cheap_window"')
    ck(_vs_tl.count('_gate("cheap_window"') == 1
       and _vs_tl.index('_gate("ws_later_fall"') < _cw_g
       < _vs_tl.index('sig["spot_wrong"] = _ws[1]') < _vs_tl.index('rec("signal", live=live, **sig)')
       and "not _ws_held and cheap_window_block(price, close_s)" in _vs_tl
       and _vs_tl.count("_cw_watch(_jkey, _jf, _jb, _jtau)") == 1
       and _vs_tl.index("_cw_watch(_jkey, _jf, _jb, _jtau)") > _vs_tl.index('"traj", ticker=_jtk, close_s=_jcs')
       and _vs_tl.count("                _cw_settle()\\n") == 1
       and _vs_tl.index("# ---------------- AMENDMENT 15")
       < _vs_tl.index("                _cw_settle()\\n")
       < _vs_tl.index("stop = risk_abort(state, a)")
       and _vs_tl.count('rec("cheap_window_settled"') == 1,
       "v-cheapwin by source: the gate is the LAST gate (after v-wsfall10, before "
       "the signal), judges FIRST buys only, the hedge watch reads the "
       "trajectory sampler's own second, and the settle runs once a pass BELOW "
       "the hedge pass and ABOVE the risk check")
    # DRIVEN: the fixture close is 1_800_000_000 = 03:00 ET (EST). A's YES ask
    # is 95c, its fair 0.999 until t = 4 s and then 0.10 (a flip), and the
    # market settles NO. A window over 03:00 with a 98c floor: no signal, no
    # order, one refusal, a shadow hedge at the NO ask, the settled shadow.
    _cw_live = _offline_trade_loop([_k1_A(collapse_at=4)], live=True, run_s=70.0,
                                   tau0=30, result={_kA: "no"},
                                   flags={"CHEAP_WINDOW": (3.0, 4.0, 0.98)})
    _cw_ref = _refusals(_cw_live, "cheap_window")
    _cw_set = _kinds(_cw_live, "cheap_window_settled", _kA)
    ck(_cw_live["raised"] is None and len(_cw_ref) == 1
       and not _kinds(_cw_live, "signal", _kA) and not _cw_live["posts"]
       and len(_cw_set) == 1 and _cw_set[0].get("want") == "yes"
       and _cw_set[0].get("result") == "no" and _cw_set[0].get("won") is False
       and _cw_set[0].get("hedge_px") is not None
       and float(_cw_set[0].get("n_ask") or 0) > 0
       and _cw_ref[0].get("price") == 0.95 and _cw_ref[0].get("window") == [3.0, 4.0, 0.98],
       "v-cheapwin DRIVEN: inside the window a 95c first buy sends nothing and "
       "signals nothing (%d posts), is refused once, and its shadow books the "
       "flip with the hedge it would have bought (hedge at %r, result %r)"
       % (len(_cw_live["posts"]), (_cw_set[0].get("hedge_px") if _cw_set else None),
          (_cw_set[0].get("result") if _cw_set else None)))
    _cw_out = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=20.0,
                                  tau0=30, flags={"CHEAP_WINDOW": (6.0, 10.0, 0.98)})
    _cw_lo = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=20.0,
                                 tau0=30, flags={"CHEAP_WINDOW": (3.0, 4.0, 0.94)})
    ck(_cw_out["raised"] is None and _cw_out["posts"]
       and not _refusals(_cw_out, "cheap_window")
       and _cw_lo["raised"] is None and _cw_lo["posts"]
       and not _refusals(_cw_lo, "cheap_window"),
       "v-cheapwin NULL: outside the window (6..10 against a 03:00 close) and "
       "under a floor the ask clears (94c against 95c) the same buy goes out "
       "(%d and %d posts)" % (len(_cw_out["posts"]), len(_cw_lo["posts"])))
''')

R.write()
print("patched", PR, sha12(PR))
print("v-0925u flag, = 0925t behaviour when omitted: --cheap-window (off); live runs --cheap-window 6 10 0.98")
