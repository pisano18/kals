"""Apply v-band99 (the 98-99c band test) + the drop_seen log to a COPY of the live pin build (C:\\kals-live-0925n's
research\\pinrun.py). CRLF preserved; every anchor must occur exactly once; refuses an already-patched file.
usage: python patch_band99.py <path to pinrun.py>"""
import sys

P = sys.argv[1]
src = open(P, 'rb').read().decode('utf-8')
assert '\r\n' in src
s = src.replace('\r\n', '\n')
assert '\r' not in s
assert 'BAND99_CEILING' not in s and 'drop_hist' not in s, 'already patched'


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


# 1. constants + pure helpers, before sweep_limit
before('def sweep_limit(f, price, want, ceiling=None, edge_floor=None, ev_floor=None):\n', '''# v-band99 (2026-10-31; operator: "I like the test you came up with, do
# that."). THE 98-99c BAND, A SMALL LIVE TEST. Over pin's whole live history
# (09-14..10-31, the ceil99 study) offers priced over the 98c ceiling and at or
# under 99c, in markets pin held NOTHING in, were 2,967 markets with 3 lost:
# +$3,679 at today's size IF every order filled. The same offers in markets pin
# bought anyway were the toxic group (317 markets, 17 lost, -$1,566), so the
# band buys only a market with nothing held in it, and only BAND99_FRAC of the
# coin's full bet. What nobody knows is the FILL RATE on winners vs losers
# (losers are where sellers happily sell at 99c); the test exists to measure it.
# EVERY OTHER GATE STILL APPLIES (PIN, the 0.3c model edge floor, dump guard,
# jump / against / wrong-side, depth floor, the early leg's own rules, budgets)
# EXCEPT the expected-value floor: its 0.9% flip rate is the whole book's and at
# 99c it refuses everything (EV +0.03c < 0.3c), so the test would measure
# nothing. One band buy a market; after it the market counts as held. A band
# order's limit never passes BAND99_CEILING. None = off (the shipped value).
BAND99_CEILING = None        # --band99-ceiling; None = off
_DEFAULT_BAND99_CEILING = None
BAND99_FRAC = 0.10           # --band99-frac: the band buy's share of the coin's bet
_DEFAULT_BAND99_FRAC = 0.10
# v-band99 add-on (coordinator, 10-31): every signal and order record carries
# drop_seen = [the highest own-side ask of the last DROP_SEEN_S s, its tau], so
# the "99c then 98c = a flip coming" warning can be re-tested on full data (the
# 10-31 study had only sampled looks). LOG ONLY: nothing reads it to decide.
DROP_SEEN_S = 60.0


def band99_size(full):
    """Contracts a band buy asks for: floor(BAND99_FRAC x the coin's full bet),
    at least 1; fails SMALL (1) on garbage."""
    try:
        return float(max(1, int(math.floor(float(BAND99_FRAC) * float(full)
                                           + 1e-9))))
    except (TypeError, ValueError):
        return 1.0


def band99_held(prev, open_pos, tk):
    """True when pin holds, or already bought this close, anything in market
    `tk`: a side on the close record, a fill count, or an open position (any
    leg, a hedge included)."""
    if ((prev or {}).get("sides") or {}).get(tk):
        return True
    if ((prev or {}).get("per_tk") or {}).get(tk):
        return True
    return any(len(v) > 4 and v[4] == tk for v in (open_pos or {}).values())


def band99_why(price, ladder, held):
    """None = the band may buy at `price` (an offer already over the ceiling);
    else the refusal's gate name. Off, or a ladder rung: 'price_ceiling',
    exactly as before the band existed."""
    if BAND99_CEILING is None or ladder:
        return "price_ceiling"
    try:
        p = float(price)
    except (TypeError, ValueError):
        return "price_ceiling"
    if p > float(BAND99_CEILING) + 1e-9:
        return "band99_over"
    if held:
        return "band99_held"
    return None


def drop_note(hist, key, t, price, tau):
    """LOG ONLY: remember our side's ask in market `key` when it CHANGES,
    keeping DROP_SEEN_S seconds (plus the price in force when the window
    opened). Decides nothing."""
    h = hist.setdefault(key, [])
    if not h or h[-1][1] != price:
        h.append((t, price, tau))
    while len(h) > 1 and h[1][0] < t - DROP_SEEN_S:
        h.pop(0)
    if len(hist) > 600:
        for k in [k for k, v in hist.items()
                  if not v or v[-1][0] < t - 2 * DROP_SEEN_S]:
            del hist[k]


def drop_seen(hist, key, t):
    """[highest own-side ask in force during the last DROP_SEEN_S s, the tau
    it was first seen at], or None. Never raises."""
    try:
        h = hist.get(key) or []
        cut = t - DROP_SEEN_S
        w = [x for i, x in enumerate(h)
             if i == len(h) - 1 or h[i + 1][0] >= cut]
        if not w:
            return None
        top = max(w, key=lambda x: x[1])
        return [round(float(top[1]), 4), top[2]]
    except Exception:                                    # noqa: BLE001
        return None


''')

# 2. the flag lists (pinned to their _DEFAULT_ twins in the offline worlds; handed back after the self-test)
replace('    "KEEP_CONN", "KEEP_WARM", "COIN_SIZE_FRAC", "WS_RISE_C")',
        '    "KEEP_CONN", "KEEP_WARM", "COIN_SIZE_FRAC", "WS_RISE_C",\n'
        '    "BAND99_CEILING", "BAND99_FRAC")')
replace('                 "COIN_SIZE_FRAC")',
        '                 "COIN_SIZE_FRAC", "BAND99_CEILING", "BAND99_FRAC")')

# 3. the trade loop's own state: the drop_seen history
before('    ws_blocked = set()       # v-wrongside: (close_s, ticker) refused once =\n',
       '    drop_hist = {}           # v-band99 add-on: (close_s, ticker, side) ->\n'
       '                             # [(t, ask, tau)] as our side\'s ask CHANGES (log only)\n')

# 4. every look with a side of its own notes the ask (log only)
before('                # ---- D_plan SECTION 5, THE HALF THE 1 Hz GRID CANNOT SEE ----\n', '''                # v-band99 add-on: our side's ask as it CHANGES, so every signal
                # and order can say the top price of the last 60 s. LOG ONLY.
                if want is not None and price is not None:
                    try:
                        drop_note(drop_hist, (close_s, tk, want), now,
                                  float(price), tau)
                    except Exception:                        # noqa: BLE001
                        pass
''')

# 5. the ceiling gate: an offer over the ceiling may be a band buy
replace('''                if price > _ceil_fr:
                    nb["over_ceiling"] = nb.get("over_ceiling", 0) + 1
''', '''                # v-band99: over the ceiling and at or under BAND99_CEILING, in a
                # market with nothing held, is a band buy (a tenth of a bet);
                # off, or a ladder rung, it is refused below exactly as before.
                _band99_now = False
                if price > _ceil_fr:
                    _b99 = band99_why(price, _lad is not None,
                                      band99_held(prev, open_pos, tk))
                    if _b99 is None:
                        _band99_now = True
                    elif _b99 != "price_ceiling":
                        nb.update(over_ceiling=nb.get("over_ceiling", 0) + 1)
                        _gate(_b99, close_s, tk, want=want,
                              price=round(price, 4), ceiling=_ceil_fr,
                              band99_ceiling=BAND99_CEILING,
                              fair=round(f, 5), tau=tau, size=float(size))
                        continue
                if price > _ceil_fr and not _band99_now:
                    nb["over_ceiling"] = nb.get("over_ceiling", 0) + 1
''')

# 6. the EV floor does not judge a band buy (see the block at BAND99_CEILING)
replace('                if ev < _evf_fr:\n', '                if ev < _evf_fr and not _band99_now:\n')

# 7. the signal: drop_seen always; a band buy is a tenth of a bet and says so
after('                sig["early_held"] = _held46\n', '''                sig["drop_seen"] = drop_seen(drop_hist, (close_s, tk, want), now)
                if _band99_now:            # v-band99
                    take_n = min(float(take_n), band99_size(_fsz))
                    sig["take_n"] = take_n
                    sig["band99"] = True
                    sig["band99_ev_c"] = round(100 * ev, 3)
''')

# 8. live: the band order's limit stops at the band ceiling
after('                        _limit = sweep_limit(f, price, want)\n', '''                        if _band99_now:            # v-band99: never past the band ceiling
                            _limit = sweep_limit(f, price, want,
                                                 ceiling=float(BAND99_CEILING),
                                                 ev_floor=-1.0)
''')

# 9. both paths: the band size again AFTER every widener (the same tenth)
replace('                        take_n = _fullcap(take_n)\n                        # v-zerotake backstop (live)',
        '                        take_n = _fullcap(take_n)\n'
        '                        if _band99_now:            # v-band99 (live): a tenth of a bet, after every widener\n'
        '                            take_n = min(float(take_n), band99_size(_fsz))\n'
        '                        # v-zerotake backstop (live)')
after('                    take_n = _fullcap(take_n)  # v-fullcap (paper), LAST\n',
      '                    if _band99_now:                # v-band99 (paper): a tenth of a bet, after every widener\n'
      '                        take_n = min(float(take_n), band99_size(_fsz))\n')

# 10. the order record
replace('                                leg=_leg46, early_held=_held46,\n',
        '                                leg=_leg46, early_held=_held46,\n'
        '                                # v-band99: a band buy, and the top ask of the last 60 s\n'
        '                                band99=bool(_band99_now),\n'
        '                                drop_seen=sig.get("drop_seen"),\n')

# 11. the start record
after('        wrongside_rise_c=WS_RISE_C, wrongside_lookback_s=WS_LOOKBACK_S,\n',
      '        # v-band99: the band, so a read can tell the runs apart\n'
      '        band99_ceiling=BAND99_CEILING, band99_frac=BAND99_FRAC,\n')

# 12. the flags
before('    ap.add_argument("--wrongside-rise-c", type=float, default=None,\n', '''    ap.add_argument("--band99-ceiling", type=float, default=None, metavar="P",
                    help="v-band99: also buy an offer over --price-ceiling and "
                         "at or under P (0.981..0.99) when pin holds nothing in "
                         "that market, at --band99-frac of the coin's bet; off "
                         "by default")
    ap.add_argument("--band99-frac", type=float, default=None, metavar="F",
                    help="v-band99: the band buy's share of the coin's full bet "
                         "(default %.2f; 0.01..0.25)" % _DEFAULT_BAND99_FRAC)
''')
before('    if a.wrongside_rise_c is not None:\n', '''    if a.band99_frac is not None and a.band99_ceiling is None:
        raise SystemExit("--band99-frac needs --band99-ceiling")
    if a.band99_ceiling is not None:
        if not (0.981 <= float(a.band99_ceiling) <= 0.99):
            raise SystemExit("--band99-ceiling must be in [0.981, 0.99], got %r"
                             % (a.band99_ceiling,))
        globals()["BAND99_CEILING"] = float(a.band99_ceiling)
    if a.band99_frac is not None:
        if not (0.01 <= float(a.band99_frac) <= 0.25):
            raise SystemExit("--band99-frac must be in [0.01, 0.25], got %r"
                             % (a.band99_frac,))
        globals()["BAND99_FRAC"] = float(a.band99_frac)
''')

# 13. the self-test
before('    # DRIVEN, through the real loop. The harness index sits at 100.5, so a\n', '''    # ---- v-band99 (2026-10-31): the 98-99c band test + the drop_seen log ----
    _b99_was = (BAND99_CEILING, BAND99_FRAC)
    try:
        globals()["BAND99_CEILING"], globals()["BAND99_FRAC"] = None, 0.10
        _b99_off = (band99_why(0.985, False, False),
                    band99_why(0.999, False, True),
                    band99_why(0.985, True, False))
        globals()["BAND99_CEILING"] = 0.99
        _b99_on = (band99_why(0.985, False, False), band99_why(0.99, False, False),
                   band99_why(0.9901, False, False), band99_why(0.985, False, True),
                   band99_why(0.985, True, False), band99_why("x", False, False))
        _b99_sz = (band99_size(281.0), band99_size(5.0), band99_size(None),
                   band99_size(19.99), band99_size(50.0))
    finally:
        globals()["BAND99_CEILING"], globals()["BAND99_FRAC"] = _b99_was
    ck(_DEFAULT_BAND99_CEILING is None and _DEFAULT_BAND99_FRAC == 0.10
       and _b99_off == ("price_ceiling",) * 3
       and _b99_on == (None, None, "band99_over", "band99_held",
                       "price_ceiling", "price_ceiling")
       and _b99_sz == (28.0, 1.0, 1.0, 1.0, 5.0)
       and 28.0 * 0.99 <= 281.0 * 0.98,
       "v-band99 PURE: ships OFF (an offer over the ceiling is refused "
       "price_ceiling exactly as before); on, 98.5c and 99c pass, 99.01c is "
       "band99_over, a held market band99_held, a ladder rung and garbage stay "
       "price_ceiling; the size is floor(10%% of the bet), at least 1 (281 -> "
       "28), so its worst case (28 x 99c) is a tenth of one full bet's "
       "(got %r %r %r)" % (_b99_off, _b99_on, _b99_sz))
    ck(band99_held({"sides": {"A": "yes"}}, {}, "A")
       and band99_held({"per_tk": {"A": 1}}, {}, "A")
       and band99_held(None, {"o1": (1, "yes", 0.9, 5.0, "A")}, "A")
       and not band99_held({"sides": {"B": "no"}},
                           {"o1": (1, "yes", 0.9, 5.0, "B")}, "A")
       and not band99_held(None, None, "A"),
       "v-band99 PURE: held = a side, a fill count or an open position in "
       "THAT market (any leg, a hedge included); another market's do not count")
    _dh = {}
    _dk = (1, "A", "yes")
    drop_note(_dh, _dk, 100.0, 0.99, 40)
    drop_note(_dh, _dk, 101.0, 0.98, 39)
    drop_note(_dh, _dk, 101.5, 0.98, 38)
    _ds1 = drop_seen(_dh, _dk, 102.0)
    _dn1 = len(_dh[_dk])
    drop_note(_dh, _dk, 170.0, 0.97, 10)
    _ds2 = drop_seen(_dh, _dk, 170.0)
    ck(_ds1 == [0.99, 40] and _dn1 == 2 and _ds2 == [0.98, 39]
       and len(_dh[_dk]) == 2 and drop_seen(_dh, (1, "B", "no"), 170.0) is None
       and drop_seen(None, _dk, 1.0) is None,
       "v-band99 drop_seen PURE: 99c then 98c -> the top of the last 60 s is "
       "99c at tau 40; a repeat price is not stored; 70 s later the 99c is out "
       "of the window and the 98c that was in force when it opened is the top; "
       "an unseen market or garbage -> None (got %r %r %r)" % (_ds1, _ds2, _dh))
    _b99_src = inspect.getsource(trade_loop)
    ck(_b99_src.count("drop_hist") == 3
       and _b99_src.count("drop_note(drop_hist") == 1
       and _b99_src.count("drop_seen(drop_hist") == 1
       and _b99_src.count('drop_seen=sig.get("drop_seen")') == 1
       and _b99_src.count("_band99_now = True") == 1
       and _b99_src.count("if _band99_now:") == 4
       and _b99_src.count("not _band99_now") == 2,
       "v-band99 by source: drop_hist is written once (every look) and read "
       "once (into the signal), never by a decision; the band is set at ONE "
       "place and read by the size (signal, live, paper), the limit, the EV "
       "skip and the old ceiling refusal only")

    def _b99_m(n, book_of):
        return {"tk": "KXBNDX%d15M-B99" % n, "series": "KXBNDX%d15M" % n,
                "iid": "B99%d" % n, "strike": 100.0,
                "fair": (lambda t: 0.999), "book": book_of}
    _b99_on_f = {"BAND99_CEILING": 0.99, "BAND99_FRAC": 0.10}
    _b99_985 = lambda t: _ob(0.94, 0.015)              # YES at 98.5c
    _b99_99 = lambda t: _ob(0.94, 0.01)                # YES at 99c: the EV floor alone would refuse it
    _bo = _offline_trade_loop([_b99_m(1, _b99_985)], run_s=6.0, size=50.0)
    ck(_bo["raised"] is None and not _kinds(_bo, "signal")
       and len(_refusals(_bo, "price_ceiling")) == 1
       and not _refusals(_bo, "band99_held") and not _refusals(_bo, "band99_over"),
       "v-band99 DRIVEN NULL: flags off, a 98.5c offer is refused price_ceiling "
       "once and never bought (signals %d)" % len(_kinds(_bo, "signal")))
    # 99c first, then 98.5c: a little cheaper, so the re-buy band lets the
    # second look reach the ceiling, where the held market is refused
    _bn = _offline_trade_loop([_b99_m(2, lambda t: _b99_99(t) if t < 2.0
                                      else _b99_985(t))],
                              run_s=6.0, size=50.0,
                              flags=dict(_b99_on_f, MAX_PER_MARKET=2,
                                         IMPROVE_SCOPE="market"))
    _bns = _kinds(_bn, "signal")
    ck(_bn["raised"] is None and len(_bns) == 1
       and _bns[0].get("band99") is True and _bns[0].get("take_n") == 5.0
       and _bns[0].get("price") == 0.99
       and (_bns[0].get("drop_seen") or [None])[0] == 0.99
       and len(_refusals(_bn, "band99_held")) == 1
       and not _refusals(_bn, "price_ceiling"),
       "v-band99 DRIVEN, paper: on (2 buys a market, scope market, as live), a "
       "99c offer is bought ONCE at a tenth of the bet (5 of 50), the signal says band99 and drop_seen; the next "
       "look finds the market held and is refused band99_held (signals %d: %r)"
       % (len(_bns), [(x.get("take_n"), x.get("band99")) for x in _bns]))
    _bv = _offline_trade_loop([_b99_m(3, lambda t: _ob(0.94, 0.005))], run_s=6.0,
                              size=50.0, flags=_b99_on_f)
    ck(_bv["raised"] is None and not _kinds(_bv, "signal")
       and len(_refusals(_bv, "band99_over")) == 1,
       "v-band99 DRIVEN: on, a 99.5c offer is refused band99_over and never "
       "bought")
    _b9t, _b9c = _k1_take(False)
    _bl = _offline_trade_loop([_b99_m(4, _b99_99)], live=True, take=_b9t,
                              run_s=6.0, size=50.0, flags=_b99_on_f)
    _blo = _kinds(_bl, "order")
    ck(_bl["raised"] is None and len(_b9c) == 1 and _b9c[0][2] == 5.0
       and len(_blo) == 1 and _blo[0].get("band99") is True
       and float(_blo[0].get("limit_sent") or 9) <= 0.99 + 1e-9
       and (_blo[0].get("drop_seen") or [None])[0] == 0.99,
       "v-band99 DRIVEN, live path: ONE order for 5 (a tenth of 50) with its "
       "limit at or under 99c; the order record says band99 and drop_seen "
       "(orders %r)" % (_b9c,))
    _bc = _offline_trade_loop([_k1_A()], live=True, take=_k1_take(False)[0])
    _bco = _kinds(_bc, "order")
    ck(_bc["raised"] is None and _bco and _bco[0].get("band99") is False
       and "drop_seen" in _bco[0] and "drop_seen" in _kinds(_bc, "signal")[0],
       "v-band99 add-on: an ordinary buy's signal and order carry drop_seen "
       "too, and band99 False")

''')

open(P, 'wb').write(s.replace('\n', '\r\n').encode('utf-8'))
print('patched', P)
