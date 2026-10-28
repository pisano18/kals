"""Apply v-wrongside (LS20) to a copy of the live pin build. CRLF preserved; every anchor must occur exactly once.
usage: python patch_ws.py <path to pinrun.py>"""
import sys

P = sys.argv[1]
src = open(P, 'rb').read().decode('utf-8')
assert '\r\n' in src
s = src.replace('\r\n', '\n')
assert '\r' not in s


def once(anchor):
    n = s.count(anchor)
    assert n == 1, (n, anchor[:80])


def after(anchor, text):
    global s
    once(anchor)
    s = s.replace(anchor, anchor + text)


def before(anchor, text):
    global s
    once(anchor)
    s = s.replace(anchor, text + anchor)


def replace(old, new):
    global s
    once(old)
    s = s.replace(old, new)


# 1. constants + pure helpers, after edge_cap_block
after('''        return 100.0 * float(edge) > float(cap_c)
    except (TypeError, ValueError):
        return False
''', '''

# v-wrongside (2026-10-27, results/IDEA_LEDGER.md LS20; operator: "Implement
# it"). A FIRST buy in a 15-minute market with the index already across the
# strike from our side is refused unless our side's market mid ROSE by at
# least WS_RISE_C cents over the last WS_LOOKBACK_S seconds. Such a buy leans
# on the locked part of the 60-s average; when nobody is paying up for our
# side while it does, the market can see a move the 1-second index has not
# printed. Live record 09-08..10-27, 71 wrong-side first fills: mid NOT up
# >= 1c in 5 s, 22 markets, 6 lost, -$247.06; up >= 1c, 47 markets, 0 lost,
# +$101.60 (a shuffle finds a rule this clean 3.6% of the time; both halves
# positive; cutoffs 0..3c all +$217..+$247; the ETH 2:15 PM -$118.92 is in
# it). WHAT IT DOES NOT TOUCH: right-side buys; every later leg of a market
# already held (later wrong-side legs: 14 markets, 0 lost, +$39.55); the
# hourly ladder (never measured: its two wrong-side buys have no tape); the
# hedge pass. A market it refuses stays refused for that close, because the
# rule measured skips the MARKET. No mid 5 s back (a fresh watch) or a
# one-sided book is no opinion and never blocks. 0 = off.
WS_RISE_C = 0.0              # --wrongside-rise-c; 0 = off (the shipped value)
_DEFAULT_WS_RISE_C = 0.0
WS_LOOKBACK_S = 5.0          # the "last 5 s" of the measurement; not a flag
WS_HIST_TAU_S = 60           # mids are recorded inside this many seconds
WS_HIST_MAX = 2000           # changes kept per (close, market); 20 Hz x 60 s
                             # is 1,200, so the 5 s window is never trimmed


def book_mid(b):
    """The YES mid of a top of book, or None when either side is empty."""
    try:
        yb, ya = b.get("yes_bid"), b.get("yes_ask")
        if yb is None or ya is None:
            return None
        return (float(yb) + float(ya)) / 2.0
    except (AttributeError, TypeError, ValueError):
        return None


def mid_at(hist, t):
    """The YES mid in force at time `t` from a change list [(t, mid)]: the
    last change at or before `t`, or None when the list starts after it."""
    if not hist:
        return None
    try:
        for tt, m in reversed(hist):
            if float(tt) <= float(t):
                return m
    except (TypeError, ValueError):
        return None
    return None


def wrongside_block(want, spot, strike, mid_now, mid_then, held=False,
                    ladder=False, rise_c=None):
    """(blocked, wrong, rise_c). `wrong`: the index is strictly across the
    strike from `want` (on the line is not across it). `rise_c`: how many
    cents OUR side's mid rose from `mid_then` to `mid_now` (YES mids in,
    rounded to 0.001c), None when either is unknown. Blocked only when the
    bar is on, nothing is held, the market is not the ladder, the side is
    wrong and the rise is KNOWN and under the bar. Cannot raise."""
    bar = WS_RISE_C if rise_c is None else rise_c
    try:
        if want not in ("yes", "no") or spot is None or strike is None:
            return (False, None, None)
        sgn = 1.0 if want == "yes" else -1.0
        wrong = sgn * (float(spot) - float(strike)) < 0
        rise = None
        if mid_now is not None and mid_then is not None:
            rise = round(100.0 * sgn * (float(mid_now) - float(mid_then)), 3)
        if (not bar or float(bar) <= 0 or held or ladder or not wrong
                or rise is None):
            return (False, wrong, rise)
        return (rise < float(bar), wrong, rise)
    except (TypeError, ValueError):
        return (False, None, None)
''')

# 2. pinned flags
replace('''    "KEEP_CONN", "KEEP_WARM", "COIN_SIZE_FRAC")''',
        '''    "KEEP_CONN", "KEEP_WARM", "COIN_SIZE_FRAC", "WS_RISE_C")''')

# 3. loop state
before('''    _traj_pruned = [0]       # the second the backstop prune last ran, so it
''', '''    ws_mid = {}              # v-wrongside: (close_s, ticker) -> [(t, YES mid)],
                             # appended when the mid CHANGES, inside
                             # WS_HIST_TAU_S, only while the flag is on
    ws_blocked = set()       # v-wrongside: (close_s, ticker) refused once =
                             # refused for the close (the rule skips a market)
''')

# 4. the recorder
before('''    reported = set()
    recon_at = {}            # ticker -> when the settlement was last polled
''', '''    def _ws_note(key, tk_, t_):
        """v-wrongside: append the YES mid when it differs from the last one
        kept. One book read; a missing, suspect or one-sided book appends
        nothing. Decides nothing and cannot raise."""
        try:
            _b = book.best(tk_)
            if not _b or _b.get("suspect"):
                return
            _m = book_mid(_b)
            if _m is None:
                return
            _h = ws_mid.setdefault(key, [])
            if not _h or _h[-1][1] != _m:
                _h.append((float(t_), _m))
                if len(_h) > WS_HIST_MAX:
                    del _h[:len(_h) - WS_HIST_MAX]
        except Exception:                                # noqa: BLE001
            return

''')

# 5. sampler hook, before the one-a-second dedupe
after('''                    if not traj_due(_jtau):
                        continue
                    _jkey = (_jcs, _jtk)
''', '''                    # v-wrongside: our side's mid as it CHANGES, on EVERY pass
                    # and above the one-a-second dedupe below, so the rule
                    # reads the mid 5 s back to the pass, as the ticker tape it
                    # was measured on did. Decides nothing here; off = no read.
                    if (WS_RISE_C > 0 and _jtau <= WS_HIST_TAU_S
                            and ladder_head(_jtk) is None):
                        _ws_note(_jkey, _jtk, now)
''')

# 6. prune with the 900 s backstop
before('''                for _dk in [k for k in look_at if k[0] < now_s - 900]:
''', '''                for _dk in [k for k in ws_mid if k[0] < now_s - 900]:
                    ws_mid.pop(_dk, None)
                for _dk in [k for k in ws_blocked if k[0] < now_s - 900]:
                    ws_blocked.discard(_dk)
''')

# 7. the gate: last before the signal
before('''                sig["leg"] = _leg46
                sig["early_held"] = _held46
''', '''                # v-wrongside (LS20): the LAST gate before the signal, so it
                # judges only a buy every other gate already passed. A FIRST
                # buy (nothing held here) in a 15-minute market with the index
                # across the strike from our side needs our side's mid UP by
                # WS_RISE_C over the last WS_LOOKBACK_S s; refused once =
                # refused for the close. The side and the rise are logged on
                # every signal either way.
                _ws_k = (close_s, tk)
                _ws_held = bool(((prev or {}).get("sides") or {}).get(tk))
                _ws = wrongside_block(
                    want, spot, strike, book_mid(b),
                    mid_at(ws_mid.get(_ws_k), now - WS_LOOKBACK_S),
                    held=_ws_held, ladder=_lad is not None)
                if (WS_RISE_C > 0 and not _ws_held and _lad is None
                        and (_ws[0] or _ws_k in ws_blocked)):
                    ws_blocked.add(_ws_k)
                    _gate("wrong_side", close_s, tk, leg=_leg46, tau=tau,
                          price=round(price, 4), fair=round(f, 5), want=want,
                          spot=spot, strike=strike, mid_rise_c=_ws[2],
                          min_rise_c=float(WS_RISE_C),
                          lookback_s=float(WS_LOOKBACK_S),
                          size=float(take_n or SIZE))
                    continue
                sig["spot_wrong"] = _ws[1]
                sig["mid_rise_c"] = _ws[2]
''')

# 7b. a refused market stays refused for the close, above the attempt counters
after('''                if SKIP_COINS and skip_coin(tk):
                    _gate("skip_coin", close_s, tk, tau=tau)
                    continue
''', '''                # v-wrongside: a market the wrong_side gate refused stays
                # refused for the close, HERE, above the attempt counters, so
                # its later looks spend none of the close's attempts (the late
                # gate's one refusal spends one, like every gate below them).
                if WS_RISE_C > 0 and (close_s, tk) in ws_blocked:
                    _gate("wrong_side_skip", close_s, tk, tau=tau)
                    continue
''')

# 8. argparse
after('''                         "left (default %d)" % _DEFAULT_TOXIC_TAU_MIN)
''', '''    ap.add_argument("--wrongside-rise-c", type=float, default=None,
                    metavar="C",
                    help="v-wrongside (LS20): refuse a FIRST buy in a "
                         "15-minute market whose index is across the strike "
                         "from our side unless our side's mid rose at least C "
                         "cents over the last %g s; a refused market stays "
                         "refused for the close. Default 0 = off."
                         % WS_LOOKBACK_S)
''')

# 9. main
after('''        globals()["TOXIC_TAU_MIN"] = int(a.toxic_tau_min)
''', '''    if a.wrongside_rise_c is not None:
        if not (0.0 <= float(a.wrongside_rise_c) <= 10.0):
            raise SystemExit("--wrongside-rise-c must be in [0, 10], got %r"
                             % (a.wrongside_rise_c,))
        globals()["WS_RISE_C"] = float(a.wrongside_rise_c)
''')

# 10. start record
after('''        toxic_fresh=bool(TOXIC_FRESH), max_edge_c=MAX_EDGE_C,
        edge_cap_tau=EDGE_CAP_TAU,
''', '''        # v-wrongside: the bar and the window, so a read can tell the runs apart
        wrongside_rise_c=WS_RISE_C, wrongside_lookback_s=WS_LOOKBACK_S,
''')

# 11. self-tests, after the v-toxic source check
after('''       "AFTER the staged_none gate (an insert above the early gates "
       "re-parents them) and before edge_cap and the signal record")
''', '''
    # ---- v-wrongside (LS20) -------------------------------------------
    # The pure pieces. Every call names its bar: the startup self-test runs
    # with the operator's flags applied, so the global may be 1.0 here.
    ck(book_mid(_ob(0.94, 0.05)) == (0.94 + 0.95) / 2.0
       and book_mid(_ob(None, 0.05)) is None
       and book_mid(_ob(0.94, None)) is None
       and book_mid({}) is None and book_mid(None) is None,
       "v-wrongside: book_mid is the YES mid; None on a one-sided, empty or "
       "missing book")
    _wsh = [(10.0, 0.90), (12.0, 0.92), (15.5, 0.95)]
    ck(mid_at(_wsh, 9.9) is None and mid_at(_wsh, 10.0) == 0.90
       and mid_at(_wsh, 14.0) == 0.92 and mid_at(_wsh, 99.0) == 0.95
       and mid_at([], 5.0) is None and mid_at(None, 5.0) is None
       and mid_at(_wsh, None) is None,
       "v-wrongside: mid_at is the last change at or before t; None before "
       "the first change, on no history, or on garbage")
    _wsb = lambda *a_, **k_: wrongside_block(*a_, rise_c=1.0, **k_)
    ck(_wsb("yes", 99.9, 100.0, 0.945, 0.945) == (True, True, 0.0)
       and _wsb("yes", 99.9, 100.0, 0.95, 0.945) == (True, True, 0.5)
       and _wsb("yes", 99.9, 100.0, 0.955, 0.945) == (False, True, 1.0)
       and _wsb("yes", 99.9, 100.0, 0.935, 0.945) == (True, True, -1.0)
       and _wsb("no", 100.1, 100.0, 0.055, 0.055) == (True, True, 0.0)
       and _wsb("no", 100.1, 100.0, 0.045, 0.055) == (False, True, 1.0)
       and _wsb("no", 100.1, 100.0, 0.065, 0.055) == (True, True, -1.0),
       "v-wrongside: across the line, a rise under 1c (0, 0.5c, a fall) is "
       "BLOCKED and 1c passes -- for NO the rise is of the NO mid, i.e. the "
       "YES mid falling")
    ck(_wsb("yes", 100.1, 100.0, 0.945, 0.945) == (False, False, 0.0)
       and _wsb("no", 99.9, 100.0, 0.055, 0.055) == (False, False, 0.0)
       and _wsb("yes", 100.0, 100.0, 0.945, 0.945)[0] is False
       and _wsb("yes", 99.9, 100.0, 0.945, None) == (False, True, None)
       and _wsb("yes", 99.9, 100.0, None, 0.945) == (False, True, None)
       and _wsb("yes", 99.9, 100.0, 0.945, 0.945, held=True)[0] is False
       and _wsb("yes", 99.9, 100.0, 0.945, 0.945, ladder=True)[0] is False
       and wrongside_block("yes", 99.9, 100.0, 0.945, 0.945,
                           rise_c=0.0)[0] is False
       and _wsb(None, 99.9, 100.0, 0.945, 0.945) == (False, None, None)
       and _wsb("yes", None, 100.0, 0.945, 0.945) == (False, None, None)
       and _wsb("yes", "x", 100.0, 0.945, 0.945) == (False, None, None)
       and _DEFAULT_WS_RISE_C == 0.0 and WS_LOOKBACK_S == 5.0,
       "v-wrongside NULL: never blocks on the right side, ON the line, with "
       "no mid 5 s back, on a one-sided book now, when the market is already "
       "held, on the hourly ladder, with the bar off, or on garbage; ships "
       "OFF; the window is 5 s")

    # DRIVEN, through the real loop. The harness index sits at 100.5, so a
    # strike of 101 puts YES across the line and a strike of 100 puts NO
    # across it. tau0 38 gives the sampler 8 s of mids before tau 30.
    def _ws_m(n, strike, book_of, fair_of=None):
        return {"tk": "KXW%d15M-WS" % n, "series": "KXW%d15M" % n,
                "iid": "WS%d" % n, "strike": strike,
                "fair": fair_of or (lambda t: 0.999), "book": book_of}
    _ws_on = {"WS_RISE_C": 1.0}
    _ws_flat = lambda t: _ob(0.94, 0.05)
    _ws_up = lambda t: _ob(round(0.90 + 0.005 * t, 4),
                           round(0.09 - 0.005 * t, 4))
    _wsw = _offline_trade_loop([_ws_m(1, 101.0, _ws_flat)], run_s=12.0,
                               tau0=38, flags=_ws_on)
    _wsr = _refusals(_wsw, "wrong_side")
    ck(_wsw["raised"] is None and not _kinds(_wsw, "signal")
       and not _kinds(_wsw, "order") and len(_wsr) == 1
       and _wsr[0].get("want") == "yes" and _wsr[0].get("mid_rise_c") == 0.0
       and _wsr[0].get("min_rise_c") == 1.0
       and _wsr[0].get("lookback_s") == 5.0
       and _wsr[0].get("spot") == 100.5 and _wsr[0].get("strike") == 101.0
       and _wsr[0].get("price") is not None
       and _wsr[0].get("fair") is not None
       and _wsr[0].get("size") is not None
       and _wsr[0].get("tau") is not None,
       "v-wrongside DRIVEN: a YES buy with the index under the strike and a "
       "flat book is refused ONCE as wrong_side naming the rise, the bar, the "
       "window, spot, strike, price, fair and size (refusals %d, signals %d)"
       % (len(_wsr), len(_kinds(_wsw, "signal"))))
    _wsu = _offline_trade_loop([_ws_m(2, 101.0, _ws_up)], run_s=12.0,
                               tau0=38, flags=_ws_on)
    _wsus = _kinds(_wsu, "signal")
    ck(_wsu["raised"] is None and len(_wsus) >= 1
       and not _refusals(_wsu, "wrong_side")
       and _wsus[0].get("spot_wrong") is True
       and 2.4 <= float(_wsus[0].get("mid_rise_c") or 0) <= 2.6,
       "...and the same buy is MADE when our side's mid rose ~2.5c in the "
       "last 5 s; the signal carries spot_wrong and mid_rise_c (signals %d, "
       "rise %r)" % (len(_wsus), _wsus[0].get("mid_rise_c") if _wsus else None))
    _wsn = _offline_trade_loop([_ws_m(3, 100.0, lambda t: _ob(0.04, 0.94),
                                      lambda t: 0.001)],
                               run_s=12.0, tau0=38, flags=_ws_on)
    _wsnr = _refusals(_wsn, "wrong_side")
    _wsnu = _offline_trade_loop(
        [_ws_m(4, 100.0, lambda t: _ob(round(0.09 - 0.005 * t, 4),
                                       round(0.90 + 0.005 * t, 4)),
               lambda t: 0.001)], run_s=12.0, tau0=38, flags=_ws_on)
    _wsnus = _kinds(_wsnu, "signal")
    ck(_wsn["raised"] is None and not _kinds(_wsn, "signal")
       and len(_wsnr) == 1 and _wsnr[0].get("want") == "no"
       and _wsnu["raised"] is None and len(_wsnus) >= 1
       and _wsnus[0].get("want") == "no"
       and _wsnus[0].get("spot_wrong") is True
       and 2.4 <= float(_wsnus[0].get("mid_rise_c") or 0) <= 2.6,
       "v-wrongside DRIVEN, NO side: with the index ABOVE the strike a NO buy "
       "on a flat book is refused, and bought when the NO mid rose ~2.5c "
       "(refusals %d, signals %d)" % (len(_wsnr), len(_wsnus)))
    # refused once = refused for the close: flat until 10 s, then our mid
    # climbs 0.3c a second -- by 13.4 s the 5 s rise is past 1c, and the
    # sampler's own gate column must still say wrong_side after it
    _ws_late = lambda t: (_ob(0.94, 0.05) if t < 10.0 else
                          _ob(round(0.94 + 0.003 * (t - 10.0), 4),
                              round(0.05 - 0.003 * (t - 10.0), 4)))
    _wsl = _offline_trade_loop([_ws_m(5, 101.0, _ws_late)], run_s=16.0,
                               tau0=38, flags=_ws_on)
    _wslt = [r for r in _kinds(_wsl, "traj")
             if r.get("t", 0) >= 14.0 and r.get("gate") == "wrong_side_skip"]
    ck(_wsl["raised"] is None and not _kinds(_wsl, "signal")
       and len(_refusals(_wsl, "wrong_side")) == 1
       and len(_refusals(_wsl, "wrong_side_skip")) == 1
       and not _refusals(_wsl, "market_attempts") and len(_wslt) >= 1,
       "v-wrongside DRIVEN: a market refused at ~30 s stays refused for the "
       "close after its mid starts rising, by wrong_side_skip ABOVE the "
       "attempt counters, so it never reaches market_attempts (signals %d, "
       "late traj rows gated wrong_side_skip %d, gates %s)"
       % (len(_kinds(_wsl, "signal")), len(_wslt),
          sorted({r.get("gate") for r in _kinds(_wsl, "refused")})))
    _wsc = _offline_trade_loop([_ws_m(6, 100.0, _ws_flat)], run_s=12.0,
                               tau0=38, flags=_ws_on)
    _wsf = _offline_trade_loop([_ws_m(7, 101.0, _ws_flat)], run_s=12.0,
                               tau0=38)
    _wsx = _offline_trade_loop([_ws_m(8, 101.0, _ws_flat)], run_s=6.0,
                               tau0=30, flags=_ws_on)
    ck(all(w["raised"] is None and len(_kinds(w, "signal")) >= 1
           and not _refusals(w, "wrong_side") for w in (_wsc, _wsf, _wsx))
       and _kinds(_wsc, "signal")[0].get("spot_wrong") is False
       and _kinds(_wsf, "signal")[0].get("spot_wrong") is True
       and _kinds(_wsf, "signal")[0].get("mid_rise_c") is None
       and _kinds(_wsx, "signal")[0].get("mid_rise_c") is None,
       "v-wrongside NULL DRIVEN: bought on the RIGHT side with a flat book; "
       "bought across the line with the flag OFF (the shipped bot: no mids "
       "kept, rise None); bought across the line with no mid 5 s back (a "
       "fresh watch is no opinion)")
    _wsl2 = _offline_trade_loop([_ws_m(9, 101.0, _ws_up)], live=True,
                                run_s=12.0, tau0=38, flags=_ws_on)
    ck(_wsl2["raised"] is None and len(_kinds(_wsl2, "order")) >= 1,
       "v-wrongside LIVE PATH: with the flag on, a rising wrong-side buy "
       "reaches an ORDER (orders %d)" % len(_kinds(_wsl2, "order")))
    _ws_hg = _offline_trade_loop([_k1_A()], flags=_ws_on)
    ck(_ws_hg["raised"] is None and abs(_hedged(_ws_hg, _kA) - 5.0) < 1e-9,
       "v-wrongside: with the gate ON a collapsing position is still hedged "
       "(%g) -- the gate lives in the entry scan" % _hedged(_ws_hg, _kA))
    _wssrc = inspect.getsource(trade_loop)
    ck("wrongside_block(" not in _wssrc[:_wssrc.find("hedge_quote")]
       and _wssrc.count("wrongside_block(") == 1
       and _wssrc.count('_gate("wrong_side"') == 1
       and _wssrc.count('_gate("wrong_side_skip"') == 1
       and _wssrc.find('_gate("wrong_side_skip"')
       < _wssrc.find("if not ATTEMPTS_ON_SEND:")
       and _wssrc.find('_gate("full_cap"') < _wssrc.find('_gate("wrong_side"')
       < _wssrc.find('rec("signal", live=live, **sig)')
       and "held=_ws_held, ladder=_lad is not None" in _wssrc
       and "not _ws_held and _lad is None" in _wssrc
       and _wssrc.find("_ws_note(_jkey, _jtk, now)")
       < _wssrc.find("if traj_at.get(_jkey) == now_s:"),
       "and by source: the ONE wrongside call sits below the hedge pass, "
       "after full_cap and before the signal record; the close-long skip sits "
       "above the attempt counters; it passes the held "
       "state and the ladder test; the mid recorder sits above the sampler's "
       "one-a-second dedupe")
''')

open(P, 'wb').write(s.replace('\n', '\r\n').encode('utf-8'))
print('patched', P)
