"""Apply v-wsfall10 + v-jumpcap8 to a COPY of the live pin build (C:\\kals-live-0925p's research\\pinrun.py,
code_sha 24eec22bbaa7). CRLF preserved; every anchor must occur exactly once; refuses an already-patched file.
usage: python patch_rules2.py <path to pinrun.py>

v-wsfall10 (--ws-later-fall-c C): a LATER buy (pin already holds this side of this 15-minute market) with the index
across the strike from our side and our side's mid DOWN >= C cents over the last 5 s is refused (ws_later_fall); the
rest of that side is skipped for the close (ws_later_skip). Logs what the buy would have asked for.
v-jumpcap8 (--hedge-jump-max SD): the A52 jump trigger fires only for jumps under SD; a capped jump while belief is
still over the --hedge-belief line logs jump_capped once per market per close with the hedge it would have sent.
Operator 2026-11-01: "Push it live, skip the slash approve.\""""
import sys

P = sys.argv[1]
src = open(P, 'rb').read().decode('utf-8')
assert '\r\n' in src
s = src.replace('\r\n', '\n')
assert '\r' not in s
assert 'WS_LATER_FALL_C' not in s and 'HEDGE_JUMP_MAX' not in s, 'already patched'


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


# 1. v-wsfall10 constant + pure helper, right before early_wide_block
before('def early_wide_block(leg, edge, cap=_EW_UNSET):\n', '''# v-wsfall10 (2026-11-01; operator: "Push it live, skip the slash approve.").
# A LATER buy -- pin already holds THIS side of this 15-minute market (a top-up,
# a late add, a rebuy, any second leg) -- with the index across the strike from
# our side AND our side's mid DOWN by at least WS_LATER_FALL_C cents over the
# last WS_LOOKBACK_S seconds is refused, and the rest of that side is skipped
# for the close. v-wrongside judges FIRST buys only; this is the same warning on
# the legs it leaves alone, at a much stricter bar (a fall, not "no rise").
# Evidence (11-01 replay of every live log, scratchpad backtest2.py /
# firstfall.py): later buys across the line 15, 1 lost (HYPE 11-01 9:15 ET
# topup, 41 NO @93.6c, our mid -24c in 5 s, -$38.56); a fall >= 10c picks ONLY
# that one (0 winners skipped, +$37.73). Independent check on FIRST wrong-side
# buys: 2 had a 10c+ fall, ETH 10-27 lost -$147.81, DOGE 10-10 won +$12.98; both
# sets 51 bets 4 lost, the 3 big-fall bets hold 2 (luck ~1.4%, cut picked by
# looking). No mid 5 s back or a one-sided book is no opinion and never blocks;
# the hourly ladder and the hedge pass are untouched. 0 = off.
WS_LATER_FALL_C = 0.0        # --ws-later-fall-c; 0 = off (the shipped value)
_DEFAULT_WS_LATER_FALL_C = 0.0


def later_fall_block(wrong, rise_c, held_same, ladder=False, fall_c=None):
    """True when a LATER buy must be refused: this side is already held
    (`held_same`), `wrong` is True (the index strictly across the strike from
    our side, as wrongside_block() returns it) and our side's mid moved
    `rise_c` cents (wrongside_block()'s third value) by -bar or less. Bar off,
    nothing held, the ladder, an unknown side or rise: False. Cannot raise."""
    bar = WS_LATER_FALL_C if fall_c is None else fall_c
    try:
        if (not bar or float(bar) <= 0 or not held_same or ladder
                or wrong is not True or rise_c is None):
            return False
        return float(rise_c) <= -float(bar) + 1e-9
    except (TypeError, ValueError):
        return False


''')

# 2. v-jumpcap8 constant next to the A52 one, helper after jump_against
after('HEDGE_JUMP_SIGMA = None\n_DEFAULT_HEDGE_JUMP_SIGMA = None\n', '''# v-jumpcap8 (2026-11-01; operator: "Push it live, skip the slash approve.").
# The A52 jump trigger fires only for jumps UNDER this many sd. Every real flip
# the jump hedge caught was a 6.0-7.5 sd jump; jumps of 8 sd or more with
# belief still over the 0.40 line never flipped: live 10-24..11-01 8 fires,
# 0 flips, -$33.04 of hedges; replay 09-12..10-20 19 fires, 0 flips, -$35.43.
# A capped jump logs jump_capped (with the hedge it would have sent); the belief
# line is unchanged and still hedges if belief falls under it. None = off.
HEDGE_JUMP_MAX = None
_DEFAULT_HEDGE_JUMP_MAX = None
''')
after('''        sgn = 1.0 if want == "no" else -1.0
        return max(sgn * float(m) / float(sigma) for m in moves)
    except (TypeError, ValueError):
        return None
''', '''

_JC_UNSET = object()


def jump_capped(jump_sd, cap=_JC_UNSET):
    """v-jumpcap8: True when a jump the A52 trigger would fire on is at or over
    the cap (--hedge-jump-max), i.e. the jump hedge must NOT fire on it. Reads
    HEDGE_JUMP_MAX at call time unless `cap` is given; a cap of None is off.
    None or garbage: False (never blocks). Cannot raise."""
    c = HEDGE_JUMP_MAX if cap is _JC_UNSET else cap
    try:
        if c is None or jump_sd is None:
            return False
        return float(jump_sd) >= float(c)
    except (TypeError, ValueError):
        return False
''')

# 3. the offline loop pins both flags at their shipped defaults
replace('''    "KEEP_CONN", "KEEP_WARM", "COIN_SIZE_FRAC", "WS_RISE_C",
    "BAND99_CEILING", "BAND99_FRAC")
''', '''    "KEEP_CONN", "KEEP_WARM", "COIN_SIZE_FRAC", "WS_RISE_C",
    "BAND99_CEILING", "BAND99_FRAC", "WS_LATER_FALL_C", "HEDGE_JUMP_MAX")
''')

# 4. the fake index may plant one-second moves (every existing world reads [])
replace('''        def recent_moves(self, iid, n=3):
            return []
''', '''        def recent_moves(self, iid, n=3):
            # v-jumpcap8: a world may plant the recent one-second moves
            # (newest first); unplanted, every existing world reads []
            _mv = (by_iid.get(iid) or {}).get("moves")
            return list(_mv(clock.t - t0)) if callable(_mv) else []
''')

# 5. per-close state
after('''    ws_blocked = set()       # v-wrongside: (close_s, ticker) refused once =
                             # refused for the close (the rule skips a market)
''', '''    ws_later_blocked = set() # v-wsfall10: (close_s, ticker, side) refused once
                             # = the rest of that side skipped for the close
    jump_capped_said = set() # v-jumpcap8: (close_s, ticker) logged once
''')

# 6. the two logging helpers, next to _ws_note
before('''    def _ws_note(key, tk_, t_):
''', '''    def _wl_detail(tk_, want_, price_, f_, take_n_, prev_, ssz_, csz_,
                   hedged_):
        """v-wsfall10: what a refused later buy WOULD have asked for -- the
        limit the send path would use (sweep_limit), our side's ask ladder up
        to it (book.rungs), the contracts after the depth and the caps, and
        what this side already holds -- so its outcome can be priced. An
        ESTIMATE of the send path (no taper / widener / late multiple).
        Logging only; any piece it cannot read is None. Cannot raise."""
        out = {"would_n": None, "limit": None, "ladder": None,
               "held_n": None}
        try:
            _sd = ((prev_ or {}).get("sides") or {}).get(tk_)
            out["held_n"] = (round(float(((prev_ or {}).get("n_tk") or {})
                                         .get(tk_, 0.0)), 2)
                             if _sd == want_ else 0.0)
        except Exception:                                # noqa: BLE001
            pass
        try:
            _lm = float(sweep_limit(f_, price_, want_))
            out["limit"] = round(_lm, 4)
        except Exception:                                # noqa: BLE001
            return out
        try:
            out["ladder"] = [[round(float(_p), 4), round(float(_z), 2)]
                             for _p, _z in (book.rungs(tk_, want_, _lm) or [])]
        except Exception:                                # noqa: BLE001
            pass
        try:
            _dp = (float(book.buyable(tk_, want_, _lm))
                   if (SWEEP_DEPTH and _lm > float(price_) + 1e-9) else 0.0)
            _n = max(float(take_n_ or 0.0), min(float(SIZE), _dp))
            for _c in (ssz_, csz_):
                if _c is not None:
                    _n = min(_n, float(_c))
            # the v-fullcap room, inline (full_bet_room's own rule: no cap
            # once insured, none off --max-full-bets; less what is held)
            if MAX_FULL_BETS and float(MAX_FULL_BETS) > 0 and hedged_ is None:
                _bet = float(ssz_ if ssz_ is not None else
                             csz_ if csz_ is not None else SIZE)
                _n = min(_n, max(0.0, float(MAX_FULL_BETS) * _bet
                                 - float(out["held_n"] or 0.0)))
            out["would_n"] = round(max(0.0, _n), 2)
        except Exception:                                # noqa: BLE001
            pass
        return out

    def _jc_note(cs_, tk_, want_, jmp_, belief_, tau_):
        """v-jumpcap8: one record for a jump the cap stopped from hedging,
        with the hedge the A52 trigger would have sent (contracts still
        naked on that side, the other side's ask, its depth and ladder up to
        hedge_limit). Logging only; cannot raise."""
        _opp = "no" if want_ == "yes" else "yes"
        _d = dict(ticker=tk_, close_s=cs_, want=want_, side=_opp,
                  jump_sd=None, belief=None, tau=tau_,
                  jump_threshold=HEDGE_JUMP_SIGMA, jump_max=HEDGE_JUMP_MAX,
                  n=None, ask=None, ask_size=None, ladder=None, limit=None)
        try:
            _d["jump_sd"] = round(float(jmp_), 2)
            _d["belief"] = round(float(belief_), 5)
        except Exception:                                # noqa: BLE001
            pass
        try:
            _d["n"] = round(sum(float(hedge_remain.get(_i, _p[3]))
                                for _i, _p in list(open_pos.items())
                                if _p[4] == tk_ and _p[1] == want_
                                and _p[0] == cs_ and _i not in hedged
                                and not str(_i).startswith("hedge-")), 2)
        except Exception:                                # noqa: BLE001
            pass
        try:
            _hb = book.best(tk_) or {}
            _a = _hb.get(f"{_opp}_ask")
            _az = _hb.get(f"{_opp}_ask_size")
            _d["ask"] = float(_a) if _a is not None else None
            _d["ask_size"] = float(_az) if _az is not None else None
            if _a is not None and float(_a) < 1.0:
                _lm = hedge_limit(float(_a))
                _lm = float(_a) if _lm is None else float(_lm)
                _d["limit"] = round(_lm, 4)
                _d["ladder"] = [[round(float(_p), 4), round(float(_z), 2)]
                                for _p, _z in (book.rungs(tk_, _opp, _lm) or [])]
        except Exception:                                # noqa: BLE001
            pass
        try:
            rec("jump_capped", **_d)
            print(f"  jump CAPPED {tk_} {_d.get('jump_sd')} sd, belief "
                  f"{_d.get('belief')}: no jump hedge (cap {HEDGE_JUMP_MAX})")
        except Exception:                                # noqa: BLE001
            pass

''')

# 7. the hedge pass: a capped jump is not a trigger; logged once
replace('''                    _htrig = "belief"
                    _hjmp = None
''', '''                    _htrig = "belief"
                    _hjmp = None
                    _hcap = False            # v-jumpcap8: a jump at/over the cap
''')
replace('''                        if _hjmp is not None and _hjmp >= HEDGE_JUMP_SIGMA:
                            _htrig = "jump"
''', '''                        if _hjmp is not None and _hjmp >= HEDGE_JUMP_SIGMA:
                            if jump_capped(_hjmp):
                                _hcap = True     # v-jumpcap8: not a trigger
                            else:
                                _htrig = "jump"
''')
before('''                    if _htrig != "jump" and not hedge_should_fire(_belief):
                        continue
''', '''                    # v-jumpcap8: a capped jump while belief is still over the
                    # line hedges NOTHING; it is written down once per market
                    # with the hedge it would have sent. Below the line the
                    # ordinary belief hedge fires as it always did.
                    if (_hcap and _htrig != "jump"
                            and not hedge_should_fire(_belief)
                            and (_hcs, _htk) not in jump_capped_said):
                        jump_capped_said.add((_hcs, _htk))
                        _jc_note(_hcs, _htk, _hwant, _hjmp, _belief, _htau)
''')

# 8. the mid recorder also runs for the new rule
replace('''                    if (WS_RISE_C > 0 and _jtau <= WS_HIST_TAU_S
                            and ladder_head(_jtk) is None):
''', '''                    if ((WS_RISE_C > 0 or WS_LATER_FALL_C > 0)
                            and _jtau <= WS_HIST_TAU_S
                            and ladder_head(_jtk) is None):
''')

# 9. the skip, above the attempt counters
before('''                sig = dict(ticker=tk, want=want, price=round(price, 4),
''', '''                # v-wsfall10: a side refused ws_later_fall stays refused for
                # the close, HERE, above the attempt counters, so its later
                # looks spend none of the close's attempts. Only 15-minute
                # markets are ever in the set, so there is no ladder size.
                if (WS_LATER_FALL_C > 0
                        and (close_s, tk, want) in ws_later_blocked):
                    _wlk = (close_s, tk, "ws_later_skip")
                    _wld = ({} if _wlk in gate_seen else
                            _wl_detail(tk, want, price, f, take_n, prev,
                                       None, _csz, hedged_side.get(tk)))
                    _gate("ws_later_skip", close_s, tk, want=want, leg=None,
                          tau=tau, price=round(price, 4), size=float(size),
                          **_wld)
                    continue
''')

# 10. the gate itself: right after the v-wrongside gate, before the signal
replace('''                _ws = wrongside_block(
                    want, spot, strike, book_mid(b),
                    mid_at(ws_mid.get(_ws_k), now - WS_LOOKBACK_S),
                    held=_ws_held, ladder=_lad is not None)
''', '''                _ws_now = book_mid(b)
                _ws_then = mid_at(ws_mid.get(_ws_k), now - WS_LOOKBACK_S)
                _ws = wrongside_block(
                    want, spot, strike, _ws_now, _ws_then,
                    held=_ws_held, ladder=_lad is not None)
''')
before('''                sig["spot_wrong"] = _ws[1]
                sig["mid_rise_c"] = _ws[2]
''', '''                # v-wsfall10: a LATER buy on this side, across the line, with
                # our side's mid down >= WS_LATER_FALL_C in the last 5 s.
                # After every other gate (so it judges only a buy that would
                # otherwise go out) and before the signal record.
                if (WS_LATER_FALL_C > 0 and _lad is None
                        and later_fall_block(
                            _ws[1], _ws[2],
                            ((prev or {}).get("sides") or {}).get(tk) == want)):
                    ws_later_blocked.add((close_s, tk, want))
                    _gate("ws_later_fall", close_s, tk, want=want, leg=_leg46,
                          tau=tau, price=round(price, 4), size=float(size),
                          fair=round(f, 5), spot=spot, strike=strike,
                          mid_now=_ws_now, mid_then=_ws_then,
                          fall_c=(round(-float(_ws[2]), 3)
                                  if _ws[2] is not None else None),
                          min_fall_c=float(WS_LATER_FALL_C),
                          lookback_s=float(WS_LOOKBACK_S),
                          **_wl_detail(tk, want, price, f, take_n, prev, _ssz,
                                       _csz, hedged_side.get(tk)))
                    continue
''')

# 11. flags
before('''    ap.add_argument("--wrongside-rise-c", type=float, default=None,
''', '''    ap.add_argument("--ws-later-fall-c", type=float, default=None,
                    metavar="C",
                    help="v-wsfall10: refuse a LATER buy (this side of this "
                         "15-minute market already held) whose index is "
                         "across the strike from our side when our side's "
                         "mid FELL at least C cents over the last %g s; the "
                         "rest of that side is skipped for the close. "
                         "Default 0 = off." % WS_LOOKBACK_S)
    ap.add_argument("--hedge-jump-max", type=float, default=None,
                    metavar="SD",
                    help="v-jumpcap8: the --hedge-jump trigger fires only for "
                         "jumps UNDER SD sigma; a capped jump is logged as "
                         "jump_capped and the --hedge-belief line still "
                         "hedges. Needs --hedge-jump. Default off.")
''')
after('''        globals()["WS_RISE_C"] = float(a.wrongside_rise_c)
''', '''    if a.ws_later_fall_c is not None:
        if not (0.0 <= float(a.ws_later_fall_c) <= 50.0):
            raise SystemExit("--ws-later-fall-c must be in [0, 50], got %r"
                             % (a.ws_later_fall_c,))
        globals()["WS_LATER_FALL_C"] = float(a.ws_later_fall_c)
    if a.hedge_jump_max is not None:
        if (HEDGE_JUMP_SIGMA is None
                or not (float(HEDGE_JUMP_SIGMA) < float(a.hedge_jump_max)
                        <= 100.0)):
            raise SystemExit("--hedge-jump-max needs --hedge-jump and must be "
                             "above it and at most 100, got %r"
                             % (a.hedge_jump_max,))
        globals()["HEDGE_JUMP_MAX"] = float(a.hedge_jump_max)
''')
after('''        wrongside_rise_c=WS_RISE_C, wrongside_lookback_s=WS_LOOKBACK_S,
''', '''        # v-wsfall10 / v-jumpcap8: the bars, so a read can tell the runs apart
        ws_later_fall_c=WS_LATER_FALL_C, hedge_jump_max=HEDGE_JUMP_MAX,
''')

# 12. self-tests, after the v-wrongside block
before('''    _la_hg = _offline_trade_loop([_k1_A()], flags={"REBUY_LATE_TAU": 15})
''', '''    # ---- v-wsfall10 + v-jumpcap8 (2026-11-01) ---------------------------
    # The pure pieces, every call naming its bar (the startup self-test runs
    # with the operator's flags applied).
    ck(later_fall_block(True, -24.0, True, fall_c=10.0) is True
       and later_fall_block(True, -10.0, True, fall_c=10.0) is True
       and later_fall_block(True, -9.99, True, fall_c=10.0) is False
       and later_fall_block(True, 0.0, True, fall_c=10.0) is False
       and later_fall_block(True, 5.0, True, fall_c=10.0) is False,
       "v-wsfall10: across the line with this side held, a fall of 10c or "
       "more is BLOCKED; 9.99c, flat and a rise pass")
    ck(later_fall_block(False, -24.0, True, fall_c=10.0) is False
       and later_fall_block(None, -24.0, True, fall_c=10.0) is False
       and later_fall_block(True, -24.0, False, fall_c=10.0) is False
       and later_fall_block(True, -24.0, True, ladder=True,
                            fall_c=10.0) is False
       and later_fall_block(True, None, True, fall_c=10.0) is False
       and later_fall_block(True, -24.0, True, fall_c=0.0) is False
       and later_fall_block(True, "x", True, fall_c=10.0) is False
       and _DEFAULT_WS_LATER_FALL_C == 0.0,
       "v-wsfall10 NULL: never blocks on the right side, an unknown side, "
       "with nothing held on this side, on the hourly ladder, with no mid 5 s "
       "back, with the bar off, or on garbage; ships OFF")
    ck(jump_capped(9.0, cap=8.0) is True and jump_capped(8.0, cap=8.0) is True
       and jump_capped(7.99, cap=8.0) is False
       and jump_capped(9.0, cap=None) is False
       and jump_capped(None, cap=8.0) is False
       and jump_capped("x", cap=8.0) is False
       and _DEFAULT_HEDGE_JUMP_MAX is None,
       "v-jumpcap8: a jump at or over the cap is capped, under it is not; "
       "cap off, no jump or garbage never caps; ships OFF")

    # DRIVEN, the real loop. Index 100.5: strike 101 puts YES across the
    # line, 100 on the right side. tau0 38: buys start at tau 30 (t 8), the
    # sampler keeps mids from t 0, the book falls at t 10 (tau 28). A top-up
    # (the position unfinished) is the later buy rebuy_ok lets through.
    def _wl_m(n, strike, book_of, fair_of=None):
        return {"tk": "KXWL%d15M-WL" % n, "series": "KXWL%d15M" % n,
                "iid": "WL%d" % n, "strike": strike,
                "fair": fair_of or (lambda t: 0.999), "book": book_of}
    _wl_on = {"WS_LATER_FALL_C": 10.0, "MAX_PER_MARKET": 2,
              "IMPROVE_SCOPE": "market"}
    _wl_off = {"MAX_PER_MARKET": 2, "IMPROVE_SCOPE": "market"}
    # the first offer (3 of the 5 wanted, so a top-up stays open) is there
    # for ONE look at tau 30, then our side has no ask until t 10, when it
    # comes back 11c (or 9c) lower; the mid 5 s back is the 0.945 before it
    _wl_fall = lambda t: (_ob(0.94, 0.05, size=3.0) if t < 7.99 else
                          _ob(0.94, None) if t < 10.0 else _ob(0.77, 0.10))
    _wl_small = lambda t: (_ob(0.94, 0.05, size=3.0) if t < 7.99 else
                           _ob(0.94, None) if t < 10.0 else _ob(0.81, 0.10))
    _wlc = _offline_trade_loop([_wl_m(1, 101.0, _wl_fall)], run_s=16.0,
                               tau0=38, flags=_wl_off)
    _wlw = _offline_trade_loop([_wl_m(2, 101.0, _wl_fall)], run_s=16.0,
                               tau0=38, flags=_wl_on)
    _wlr = _refusals(_wlw, "ws_later_fall")
    _wls = _refusals(_wlw, "ws_later_skip")
    ck(_wlc["raised"] is None and len(_kinds(_wlc, "signal")) == 2,
       "v-wsfall10 DRIVEN control: with the flag OFF the wrong-side market "
       "is bought, then bought AGAIN after its mid falls 11c (signals %d)"
       % len(_kinds(_wlc, "signal")))
    ck(_wlw["raised"] is None and len(_kinds(_wlw, "signal")) == 1
       and len(_wlr) == 1 and len(_wls) == 1
       and _wlr[0].get("want") == "yes"
       and 10.9 <= float(_wlr[0].get("fall_c") or 0) <= 11.1
       and _wlr[0].get("min_fall_c") == 10.0
       and _wlr[0].get("mid_now") is not None
       and _wlr[0].get("mid_then") is not None
       and float(_wlr[0].get("held_n") or 0) > 0
       and _wlr[0].get("would_n") is not None
       and _wlr[0].get("limit") is not None
       and isinstance(_wlr[0].get("ladder"), list)
       and _wlr[0].get("spot") == 100.5 and _wlr[0].get("strike") == 101.0
       and _wlr[0].get("price") is not None and _wlr[0].get("tau") is not None
       and _wls[0].get("want") == "yes" and _wls[0].get("price") is not None
       and "would_n" in _wls[0] and "ladder" in _wls[0],
       "v-wsfall10 DRIVEN: ON, the first buy is made, the later buy after an "
       "11c fall across the line is refused ONCE as ws_later_fall naming the "
       "fall, the bar, both mids, what is held and what it would have bought; "
       "the next looks are ws_later_skip (signals %d, fall %r, skip %d)"
       % (len(_kinds(_wlw, "signal")),
          _wlr[0].get("fall_c") if _wlr else None, len(_wls)))
    _wlg = _offline_trade_loop([_wl_m(3, 100.0, _wl_fall)], run_s=16.0,
                               tau0=38, flags=_wl_on)
    _wln = _offline_trade_loop([_wl_m(4, 101.0, _wl_small)], run_s=16.0,
                               tau0=38, flags=_wl_on)
    _wlh = _offline_trade_loop(
        [_wl_m(5, 101.0, _wl_fall,
               lambda t: 0.5 if t < 11.0 else 0.999)],
        run_s=16.0, tau0=38, flags=_wl_on)
    ck(all(w["raised"] is None and not _refusals(w, "ws_later_fall")
           and not _refusals(w, "ws_later_skip") for w in (_wlg, _wln, _wlh))
       and len(_kinds(_wlg, "signal")) == 2
       and len(_kinds(_wln, "signal")) == 2
       and len(_kinds(_wlh, "signal")) >= 1,
       "v-wsfall10 NULL DRIVEN: the same 11c fall on the RIGHT side is bought "
       "again; a 9c fall across the line is bought again; a FIRST buy after "
       "the fall (nothing held) is bought (signals %d / %d / %d)"
       % (len(_kinds(_wlg, "signal")), len(_kinds(_wln, "signal")),
          len(_kinds(_wlh, "signal"))))
    _wll = _offline_trade_loop([_wl_m(6, 101.0, _wl_fall)], live=True,
                               take=_k1_take(False)[0], run_s=16.0, tau0=38,
                               flags=_wl_on)
    ck(_wll["raised"] is None and len(_kinds(_wll, "order")) == 1
       and len(_refusals(_wll, "ws_later_fall")) == 1,
       "v-wsfall10 LIVE PATH: one order (the first buy), the later one "
       "refused (orders %d)" % len(_kinds(_wll, "order")))
    # the jump cap. sigma is 0.0005, so a -0.0045 move is 9 sd against a YES
    # holder and -0.0035 is 7 sd; moves start at t 4, after the entry.
    def _jc_m(n, fair_of, moves_of):
        return {"tk": "KXJC%d15M-JC" % n, "series": "KXJC%d15M" % n,
                "iid": "JC%d" % n, "strike": 100.0, "fair": fair_of,
                "book": (lambda t: _ob(0.94, 0.05)), "moves": moves_of}
    _jc_on = {"HEDGE_JUMP_SIGMA": 6.0, "HEDGE_JUMP_MAX": 8.0,
              "HEDGE_BELIEF": 0.40}
    _jc_f85 = lambda t: 0.999 if t < 4.0 else 0.85
    _jc_f02 = lambda t: 0.999 if t < 4.0 else 0.02
    _jc_9 = lambda t: [-0.0045] if t >= 4.0 else []
    _jc_7 = lambda t: [-0.0035] if t >= 4.0 else []
    _jca = _offline_trade_loop([_jc_m(1, _jc_f85, _jc_9)], flags=_jc_on)
    _jcar = _kinds(_jca, "jump_capped")
    _jcan = "KXJC115M-JC"
    ck(_jca["raised"] is None and len(_jcar) == 1
       and not _kinds(_jca, "hedge_alarm") and _hedged(_jca, _jcan) == 0.0
       and _jcar[0].get("want") == "yes" and _jcar[0].get("side") == "no"
       and 8.9 <= float(_jcar[0].get("jump_sd") or 0) <= 9.1
       and abs(float(_jcar[0].get("belief") or 0) - 0.85) < 1e-6
       and float(_jcar[0].get("n") or 0) > 0
       and _jcar[0].get("ask") is not None
       and _jcar[0].get("ask_size") is not None
       and _jcar[0].get("limit") is not None
       and isinstance(_jcar[0].get("ladder"), list)
       and _jcar[0].get("close_s") is not None
       and _jcar[0].get("tau") is not None,
       "v-jumpcap8 DRIVEN: a 9 sd jump at belief 0.85 logs jump_capped ONCE "
       "(side, sd, belief, naked n, ask, depth, limit, ladder) and hedges "
       "nothing (records %d, alarms %d, hedged %g)"
       % (len(_jcar), len(_kinds(_jca, "hedge_alarm")),
          _hedged(_jca, _jcan)))
    _jcb = _offline_trade_loop([_jc_m(2, _jc_f85, _jc_7)], flags=_jc_on)
    _jcc = _offline_trade_loop([_jc_m(3, _jc_f02, _jc_9)], flags=_jc_on)
    _jcd = _offline_trade_loop([_jc_m(4, _jc_f85, _jc_9)],
                               flags={"HEDGE_JUMP_SIGMA": 6.0,
                                      "HEDGE_BELIEF": 0.40})
    _jcb_t = [r.get("trigger") for r in _kinds(_jcb, "hedge_alarm")]
    _jcc_t = [r.get("trigger") for r in _kinds(_jcc, "hedge_alarm")]
    _jcd_t = [r.get("trigger") for r in _kinds(_jcd, "hedge_alarm")]
    ck(_jcb["raised"] is None and "jump" in _jcb_t
       and not _kinds(_jcb, "jump_capped"),
       "v-jumpcap8 DRIVEN: a 7 sd jump (under the cap) still fires the jump "
       "hedge (alarm triggers %r)" % (_jcb_t,))
    ck(_jcc["raised"] is None and "belief" in _jcc_t
       and not _kinds(_jcc, "jump_capped")
       and abs(_hedged(_jcc, "KXJC315M-JC") - 5.0) < 1e-9,
       "v-jumpcap8 DRIVEN: a 9 sd jump with belief 0.02 is hedged in full by "
       "the belief line (triggers %r, hedged %g)"
       % (_jcc_t, _hedged(_jcc, "KXJC315M-JC")))
    ck(_jcd["raised"] is None and "jump" in _jcd_t
       and not _kinds(_jcd, "jump_capped"),
       "v-jumpcap8 NULL DRIVEN: with the cap OFF the same 9 sd jump fires the "
       "jump hedge, as before (triggers %r)" % (_jcd_t,))
    _wlsrc = inspect.getsource(trade_loop)
    ck(_wlsrc.count('_gate("ws_later_fall"') == 1
       and _wlsrc.count('_gate("ws_later_skip"') == 1
       and _wlsrc.find('_gate("ws_later_skip"')
       < _wlsrc.find("if not ATTEMPTS_ON_SEND:")
       and _wlsrc.find('_gate("wrong_side"') < _wlsrc.find('_gate("ws_later_fall"')
       < _wlsrc.find('rec("signal", live=live, **sig)')
       and _wlsrc.count("later_fall_block(") == 1
       and "later_fall_block(" not in _wlsrc[:_wlsrc.find("hedge_quote")]
       and _wlsrc.count("jump_capped(") == 1
       and _wlsrc.find("jump_capped(")
       < _wlsrc.find('if _htrig != "jump" and not hedge_should_fire(_belief)')
       and _wlsrc.count('rec("jump_capped"') == 1,
       "v-wsfall10 / v-jumpcap8 by source: one later-fall gate after "
       "wrong_side and before the signal; its skip above the attempt "
       "counters; one cap test inside the hedge pass, before the belief "
       "test; one jump_capped record")

''')

open(P, 'wb').write(s.replace('\n', '\r\n').encode('utf-8'))
print('patched', P)
