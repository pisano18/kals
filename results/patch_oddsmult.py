"""Apply v-oddsmult to a COPY of the live pin build (C:\\kals-live-0925q's research\\pinrun.py, code_sha 0f49ba3ae221).
CRLF preserved; every anchor must occur exactly once; refuses an already-patched file.
usage: python patch_oddsmult.py <path to pinrun.py>

v-oddsmult (--hedge-odds-mult M, --hedge-odds-min-tau S): when the hedge fires on the BELIEF line (pin's odds in our
side under --hedge-belief; never the jump trigger, never a stale-index alarm) with at least S seconds left, pin ALSO
buys (M - 1) x the position of the hedge side as a SECOND order sent right after the covering hedge. The covering
hedge is byte-for-byte the order it was; the extra is new exposure and pintake judges it as such. One try per
position; logs kind hedge_extra (and hedge_extra_skipped / hedge_extra_refused). 1.0 = off (the shipped value).
Operator 2026-11-02: "Go. Push it yourself without me needing to do anything." Start 1.25x (the tiny-test rule)."""
import sys

P = sys.argv[1]
src = open(P, 'rb').read().decode('utf-8')
assert '\r\n' in src
s = src.replace('\r\n', '\n')
assert '\r' not in s
assert 'HEDGE_ODDS_MULT' not in s and 'odds_extra(' not in s, 'already patched'


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


# 1. the constants, next to the v-jumpcap8 ones
after('HEDGE_JUMP_MAX = None\n_DEFAULT_HEDGE_JUMP_MAX = None\n', '''# v-oddsmult (2026-11-02; operator: "Go. Push it yourself without me needing
# to do anything."). At the odds line (belief under --hedge-belief, the
# "belief" trigger) pin's index runs about a second ahead of the book, and the
# hedge side it buys there won 27 of 37 times (09-23..11-01) at ~65c. A
# covering hedge only cancels the loss; EXTRA contracts of the hedge side turn
# the save into a profit. Replay on pin's own hedge quotes at 299-contract
# bets: 2x +$350..+$550 per 40 days over 1x (extrahedge.py / hedgeprop.py);
# the extra lost money only inside 10 s (8 fires, -$136), hence the tau floor.
# 11-02 ZEC 7:30 ET: No 297 @94.5c lost $281.63, the 1x hedge Yes 297 @14c
# made $253.07; 2x would have added +$180..+$225. The extra rides ONLY with a
# belief-triggered hedge (never the jump trigger, never a stale-index alarm),
# goes out as its OWN order right after the covering hedge (pintake judges it
# as new exposure; the covering hedge is exactly the order it was), once per
# position. 1.0 = off (the shipped value). Live from 1.25 (the tiny-test rule).
HEDGE_ODDS_MULT = 1.0
_DEFAULT_HEDGE_ODDS_MULT = 1.0
HEDGE_ODDS_MIN_TAU = 11
_DEFAULT_HEDGE_ODDS_MIN_TAU = 11
''')

# 2. the pure decision, after jump_capped
after('''        return float(jump_sd) >= float(c)
    except (TypeError, ValueError):
        return False
''', '''

def odds_extra(orig_n, trigger, belief, tau, mult=None, min_tau=None,
               threshold=None):
    """v-oddsmult: EXTRA contracts of the hedge side to buy over the covering
    hedge: (mult - 1) x the position, only when the hedge fired on the belief
    line (trigger "belief" with belief under the line) with at least `min_tau`
    seconds left. 0.0 otherwise: at a multiple of 1 or less, on the jump
    trigger whatever the belief, on a stale-index alarm, inside the tau floor,
    on an empty position or on garbage. Cannot raise."""
    m = HEDGE_ODDS_MULT if mult is None else mult
    mt = HEDGE_ODDS_MIN_TAU if min_tau is None else min_tau
    try:
        m = float(m)
        mt = float(mt)
        n = float(orig_n)
        t = float(tau)
    except (TypeError, ValueError):
        return 0.0
    if m <= 1.0 or not (n > 0.0) or trigger != "belief" or t < mt:
        return 0.0
    try:
        if not hedge_should_fire(belief, threshold):
            return 0.0
    except (TypeError, ValueError):
        return 0.0
    return round((m - 1.0) * n, 2)
''')

# 3. the offline loop pins both flags at their shipped defaults
replace('''    "BAND99_CEILING", "BAND99_FRAC", "WS_LATER_FALL_C", "HEDGE_JUMP_MAX")
''', '''    "BAND99_CEILING", "BAND99_FRAC", "WS_LATER_FALL_C", "HEDGE_JUMP_MAX",
    "HEDGE_ODDS_MULT", "HEDGE_ODDS_MIN_TAU")
''')

# 4. per-run state
after('''    jump_capped_said = set() # v-jumpcap8: (close_s, ticker) logged once
''', '''    hedge_extra_done = set() # v-oddsmult: positions whose extra leg was tried
''')

# 5. the hedge pass: decide the extra right after the A54 size
after('''                    _hn_want = flip_size(_hn, _entry_tau, _htau)
''', '''                    # v-oddsmult: the EXTRA leg of the hedge side, decided
                    # here, sent BELOW as its own order right after the
                    # covering hedge. Nothing about the covering hedge's own
                    # size, limit, depth or bookkeeping changes.
                    _hx_n = 0.0
                    if (_hid not in hedge_extra_done
                            and not HEDGE_PILOT_CONTRACTS):
                        _hx_n = odds_extra(_hn_orig, _htrig, _belief, _htau)
''')
# ...and what the same ladder leaves for it, after the covering hedge's take size
before('''                    # A hedge order still spends the ENTRY budget -- an order is an
''', '''                    # v-oddsmult: the ladder up to the same limit, less what the
                    # covering hedge takes, capped at the extra wanted
                    _hx_take = 0.0
                    if _hx_n > 0:
                        try:
                            _hx_take = max(0.0, min(
                                float(_hx_n),
                                float(hedge_depth(_asz, _hrungs,
                                                  float(_hn) + float(_hx_n)))
                                - float(_hn_take)))
                        except (TypeError, ValueError):
                            _hx_take = 0.0
''')

# 6. paper: book the extra at the ladder price the covering hedge did not use
before('''                        print(f"  HEDGE(paper) {_htk} buy {_opp.upper()} {_hn_take:g} @ "
                              f"{_hpaper:.3f} -> locked {100*hedge_locked_loss(_hcost,_hpaper):+.1f}c")
                        continue
''', '''                        # v-oddsmult (paper): the extra leg, priced on what the
                        # ladder holds past the covering hedge (its limit when
                        # the ladder cannot say). Guarded: a fault here can
                        # only lose the extra, never the hedge above.
                        if _hx_n > 0:
                            hedge_extra_done.add(_hid)
                            try:
                                if _hx_take > 1e-9:
                                    _hxv = hedge_vwap(_hrungs, _hn_take + _hx_take, None)
                                    _hxp = (float(_hlimit) if _hxv is None else max(
                                        float(_ask), (float(_hxv) * (_hn_take + _hx_take)
                                                      - _hpaper * _hn_take) / _hx_take))
                                    _hxoid = f"hedge-extra-paper-{_hid}-{now_s}"
                                    open_pos[_hxoid] = (_hcs, _opp, _hxp, _hx_take, _htk)
                                    state["hedge_extras"] = state.get("hedge_extras", 0) + 1
                                    rec("hedge_extra", ticker=_htk, side=_opp, price=_hxp,
                                        n=_hx_take, asked=_hx_take, extra_of=_hx_n,
                                        mult=HEDGE_ODDS_MULT, min_tau=HEDGE_ODDS_MIN_TAU,
                                        base_n=_hn_take, orig_n=_hn_orig, ask=float(_ask),
                                        ask_size=float(_asz), limit_sent=round(float(_hlimit), 4),
                                        ladder_n=round(float(_hdepth), 2), entry=_hcost,
                                        tau=_htau, belief=round(_belief, 5), trigger=_htrig,
                                        status="executed", live=False)
                                    print(f"  HEDGE EXTRA(paper) {_htk} buy {_opp.upper()} "
                                          f"{_hx_take:g} @ {_hxp:.3f} (x{HEDGE_ODDS_MULT:g})")
                                else:
                                    rec("hedge_extra_skipped", ticker=_htk, side=_opp,
                                        why="no depth past the covering hedge", extra_of=_hx_n,
                                        mult=HEDGE_ODDS_MULT, ladder_n=round(float(_hdepth), 2),
                                        tau=_htau, live=False)
                            except Exception as _ex9:                # noqa: BLE001
                                rec("error", where="hedge_extra_paper", ticker=_htk,
                                    err=str(_ex9)[:300])
''')

# 7. live: the extra as its own order, after the covering hedge's record and print
after('''                    print(f"  HEDGE {_htk} buy {_opp.upper()} {_hfilled:g}/{_hn_take:g} @ "
                          f"{_hcost2:.3f} -> locked {100*hedge_locked_loss(_hcost,_hcost2):+.1f}c")
''', '''                    # v-oddsmult: the EXTRA leg, its own order, only behind a
                    # covering hedge that filled, one try per position. pintake
                    # sees an order larger than the position is not a covering
                    # hedge and judges it with every dollar rail; a refusal
                    # costs the extra and nothing else. Guarded: a fault here
                    # can only lose the extra, never the hedge above.
                    if _hx_n > 0 and _hfilled > 0:
                        hedge_extra_done.add(_hid)
                        try:
                            if _hx_take <= 1e-9:
                                rec("hedge_extra_skipped", ticker=_htk, side=_opp,
                                    why="no depth past the covering hedge", extra_of=_hx_n,
                                    mult=HEDGE_ODDS_MULT, ladder_n=round(float(_hdepth), 2),
                                    tau=_htau, live=True)
                            else:
                                attempts[_hcs] = attempts.get(_hcs, 0) + 1
                                hedge_attempts[_hcs] += 1
                                _hxt_ms = int(round(time.time() * 1000.0))
                                _hxout = pintake.take(CREDS["base"], CREDS["pk"], CREDS["key_id"],
                                                      _htk, _opp, float(_hlimit), _hx_take,
                                                      float(_hcs), exchange_index=2,
                                                      hedge=True)
                                _hxref = _hxout.get("refused") or []
                                if _hxref or _hxout.get("status_code") is None:
                                    rec("hedge_extra_refused", ticker=_htk, side=_opp,
                                        asked=_hx_take, err=str(_hxref)[:300], tau=_htau,
                                        status_code=_hxout.get("status_code"))
                                    print(f"  HEDGE EXTRA {_htk} refused: {str(_hxref)[:120]}")
                                else:
                                    _hxf = float(_hxout.get("filled") or 0)
                                    _hxpx = _hxout.get("exec_price")
                                    _hxc = float(_hxpx) if _hxpx is not None else float(_hlimit)
                                    if _hxf > 0:
                                        _hxoid = (f"hedge-extra-{_hid}-"
                                                  f"{_hxout.get('order_id') or now_s}")
                                        open_pos[_hxoid] = (_hcs, _opp, _hxc, _hxf, _htk)
                                        state["hedge_extras"] = state.get("hedge_extras", 0) + 1
                                    _hxsc = _hxout.get("status_code")
                                    _hxun = _hxout.get("unrest")
                                    _hxunk = (not (isinstance(_hxsc, int) and 400 <= _hxsc < 500)
                                              and (not pintake._readable(_hxout)
                                                   or (_hxun is not None
                                                       and not _hxun.get("reconciled"))))
                                    if _hxunk and not hedge_never_sent(_hxout):
                                        # looked up on Kalshi by its own id (v-safety2);
                                        # nothing is counted covered, so the resolver
                                        # books only what really filled and re-opens
                                        # no hedge
                                        _kt_note_unknown("hedge_extra", _hxout, _htk, _opp,
                                                         _hcs, _hlimit, _hx_take, _hxf,
                                                         parent=_hid, assumed=0.0)
                                    rec("hedge_extra", ticker=_htk, side=_opp, price=_hxc,
                                        n=_hxf, asked=_hx_take, extra_of=_hx_n,
                                        mult=HEDGE_ODDS_MULT, min_tau=HEDGE_ODDS_MIN_TAU,
                                        base_n=_hfilled, orig_n=_hn_orig, ask=float(_ask),
                                        ask_size=float(_asz), limit_sent=round(float(_hlimit), 4),
                                        ladder_n=round(float(_hdepth), 2),
                                        swept=bool(_hxpx is not None
                                                   and float(_hxpx) > float(_ask) + 1e-9),
                                        entry=_hcost, tau=_htau, belief=round(_belief, 5),
                                        trigger=_htrig, order_id=_hxout.get("order_id"),
                                        status=_hxout.get("status"), status_code=_hxsc,
                                        unknown=bool(_hxunk), live=True,
                                        t_ms_decide=_ht_decide_ms, t_ms_send=_hxt_ms,
                                        conn=_hxout.get("conn"), conn_ms=_hxout.get("conn_ms"),
                                        conn_result=_hxout.get("conn_result"))
                                    print(f"  HEDGE EXTRA {_htk} buy {_opp.upper()} {_hxf:g}/"
                                          f"{_hx_take:g} @ {_hxc:.3f} (x{HEDGE_ODDS_MULT:g} at "
                                          f"the odds line)")
                        except Exception as _ex9:                    # noqa: BLE001
                            state["order_errors"] = state.get("order_errors", 0) + 1
                            rec("error", where="hedge_extra", ticker=_htk,
                                err=str(_ex9)[:300])
''')

# 8. flags
before('''    ap.add_argument("--ws-later-fall-c", type=float, default=None,
''', '''    ap.add_argument("--hedge-odds-mult", type=float, default=None,
                    metavar="M",
                    help="v-oddsmult: when the belief line fires with at least "
                         "--hedge-odds-min-tau seconds left, ALSO buy (M - 1) x "
                         "the position of the hedge side as a second order right "
                         "after the covering hedge (never on the jump trigger). "
                         "1 = off (default); at most 3.")
    ap.add_argument("--hedge-odds-min-tau", type=float, default=None,
                    metavar="S",
                    help="v-oddsmult: the extra leg needs at least S seconds "
                         "left (default %d: inside 10 s the extra lost money)."
                         % _DEFAULT_HEDGE_ODDS_MIN_TAU)
''')
after('''        globals()["HEDGE_JUMP_MAX"] = float(a.hedge_jump_max)
''', '''    if a.hedge_odds_mult is not None:
        if not (1.0 <= float(a.hedge_odds_mult) <= 3.0):
            raise SystemExit("--hedge-odds-mult must be in [1, 3], got %r"
                             % (a.hedge_odds_mult,))
        globals()["HEDGE_ODDS_MULT"] = float(a.hedge_odds_mult)
    if a.hedge_odds_min_tau is not None:
        if not (0.0 <= float(a.hedge_odds_min_tau) <= 60.0):
            raise SystemExit("--hedge-odds-min-tau is seconds in [0, 60], got %r"
                             % (a.hedge_odds_min_tau,))
        globals()["HEDGE_ODDS_MIN_TAU"] = float(a.hedge_odds_min_tau)
''')
after('''        ws_later_fall_c=WS_LATER_FALL_C, hedge_jump_max=HEDGE_JUMP_MAX,
''', '''        # v-oddsmult: the multiple and its tau floor, so a read can tell the runs apart
        hedge_odds_mult=HEDGE_ODDS_MULT, hedge_odds_min_tau=HEDGE_ODDS_MIN_TAU,
''')

# 9a. v-safety2's source check counted the two unknown-order sites (entry, hedge); the extra leg is a third
replace('''       and _ksrc.count("_kt_note_unknown(\\"") == 2
       and "_kt_holding()" in _ksrc[_ks_risk:],
       "v-safety2 (1) by source: the Kalshi read runs BELOW the hedge pass "
       "and ABOVE the risk check; both unknown sites (entry, hedge) register; "
       "the drain waits on it")
''', '''       and _ksrc.count("_kt_note_unknown(\\"") == 3
       and "_kt_holding()" in _ksrc[_ks_risk:],
       "v-safety2 (1) by source: the Kalshi read runs BELOW the hedge pass "
       "and ABOVE the risk check; all three unknown sites (entry, hedge, and "
       "v-oddsmult's extra leg) register; the drain waits on it")
''')

# 9. self-tests, after the v-wsfall10 / v-jumpcap8 block
before('''    _la_hg = _offline_trade_loop([_k1_A()], flags={"REBUY_LATE_TAU": 15})
''', '''    # ---- v-oddsmult (2026-11-02) ------------------------------------------
    # The pure decision, every call naming its multiple, floor and line.
    ck(odds_extra(297.0, "belief", 0.34, 18, mult=2.0, min_tau=11, threshold=0.40) == 297.0
       and odds_extra(297.0, "belief", 0.34, 18, mult=1.25, min_tau=11, threshold=0.40) == 74.25
       and odds_extra(297.0, "belief", 0.34, 11, mult=2.0, min_tau=11, threshold=0.40) == 297.0
       and odds_extra(101.23, "belief", 0.001, 40, mult=1.5, min_tau=11, threshold=0.40) == 50.62,
       "v-oddsmult: on the belief line with the floor met the extra is (M - 1) x "
       "the position, the floor itself included")
    ck(odds_extra(297.0, "belief", 0.34, 10, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, "jump", 0.64, 38, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, "jump", 0.34, 38, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, "market_index_stale", 0.34, 38, mult=2.0, min_tau=11,
                      threshold=0.40) == 0.0
       and odds_extra(297.0, "belief", 0.40, 18, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, "belief", 0.34, 18, mult=1.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(0.0, "belief", 0.34, 18, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, "belief", None, 18, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra("x", "belief", 0.34, 18, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, "belief", 0.34, None, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, None, 0.34, 18, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and _DEFAULT_HEDGE_ODDS_MULT == 1.0 and _DEFAULT_HEDGE_ODDS_MIN_TAU == 11,
       "v-oddsmult NULL: nothing inside the floor, on the jump trigger whatever "
       "the belief, on a stale-index alarm, at or over the line, at 1x, on an "
       "empty position or garbage; ships OFF with an 11 s floor")
    # DRIVEN, the real loop. _k1_A: YES bought at tau 30, belief collapses to
    # 0.10 at t 4 (tau 26, over the floor): the covering hedge of 5 NO as it
    # always was, plus ONE extra leg of 5 NO (2x) on its own record.
    _ox_on = {"HEDGE_ODDS_MULT": 2.0, "HEDGE_ODDS_MIN_TAU": 11}
    _oxa = _offline_trade_loop([_k1_A()], flags=_ox_on)
    _oxx = _kinds(_oxa, "hedge_extra", _kA)
    ck(_oxa["raised"] is None and abs(_hedged(_oxa, _kA) - 5.0) < 1e-9
       and len(_oxx) == 1 and abs(float(_oxx[0].get("n") or 0) - 5.0) < 1e-9
       and _oxx[0].get("mult") == 2.0 and _oxx[0].get("trigger") == "belief"
       and _oxx[0].get("side") == "no" and _oxx[0].get("live") is False
       and float(_oxx[0].get("price") or 0) > 0 and _oxx[0].get("tau") is not None
       and abs(float(_oxx[0].get("extra_of") or 0) - 5.0) < 1e-9
       and abs(float(_oxx[0].get("base_n") or 0) - 5.0) < 1e-9
       and not _kinds(_oxa, "hedge_extra_skipped", _kA),
       "v-oddsmult DRIVEN (paper): the collapse hedges all 5 as before AND one "
       "hedge_extra of 5 more No rides with it at 2x (hedged %g, extras %d)"
       % (_hedged(_oxa, _kA), len(_oxx)))
    _oxb = _offline_trade_loop([_k1_A()], tau0=12, flags=_ox_on)
    _oxc = _offline_trade_loop([_k1_A()])
    _oxd = _offline_trade_loop([_k1_A()], flags={"HEDGE_ODDS_MULT": 2.0,
                                                 "HEDGE_ODDS_MIN_TAU": 27})
    ck(all(w["raised"] is None and abs(_hedged(w, _kA) - 5.0) < 1e-9
           and not _kinds(w, "hedge_extra", _kA) for w in (_oxb, _oxc, _oxd)),
       "v-oddsmult NULL DRIVEN: a collapse inside the floor (tau 8 of 11), the "
       "flag OFF, and a floor above the collapse's tau (27 vs 26) each hedge "
       "exactly the 5 held and buy no extra (hedged %g / %g / %g)"
       % (_hedged(_oxb, _kA), _hedged(_oxc, _kA), _hedged(_oxd, _kA)))
    # the two triggers that must never carry an extra: the 7 sd jump at belief
    # 0.85 (trigger jump), and the belief line reached through a CAPPED 9 sd
    # jump (trigger belief; the 11-02 ZEC shape) which must carry one
    # (HEDGE_PROP off, as live runs: under proportional hedging a jump alarm
    # at belief 0.85 buys nothing at all, so the jump hedge itself needs it)
    _oxj = _offline_trade_loop([_jc_m(5, _jc_f85, _jc_7)],
                               flags=dict(_jc_on, HEDGE_PROP=False, **_ox_on))
    _oxz = _offline_trade_loop([_jc_m(6, _jc_f02, _jc_9)],
                               flags=dict(_jc_on, **_ox_on))
    _oxj_t = [r.get("trigger") for r in _kinds(_oxj, "hedge_alarm")]
    _oxz_t = [r.get("trigger") for r in _kinds(_oxz, "hedge_alarm")]
    ck(_oxj["raised"] is None and "jump" in _oxj_t
       and abs(_hedged(_oxj, "KXJC515M-JC") - 5.0) < 1e-9
       and not _kinds(_oxj, "hedge_extra"),
       "v-oddsmult NULL DRIVEN: the JUMP trigger (belief 0.85, whole-position "
       "hedging as live) hedges the 5 held and buys no extra (triggers %r, "
       "hedged %g, extras %d, raised %r)"
       % (_oxj_t, _hedged(_oxj, "KXJC515M-JC"), len(_kinds(_oxj, "hedge_extra")),
          _oxj["raised"]))
    ck(_oxz["raised"] is None and "belief" in _oxz_t
       and abs(_hedged(_oxz, "KXJC615M-JC") - 5.0) < 1e-9
       and len(_kinds(_oxz, "hedge_extra")) == 1
       and abs(float(_kinds(_oxz, "hedge_extra")[0].get("n") or 0) - 5.0) < 1e-9,
       "v-oddsmult DRIVEN: the belief line reached through a capped 9 sd jump "
       "(the 11-02 ZEC shape) hedges the 5 and buys 5 extra (triggers %r)"
       % (_oxz_t,))
    # LIVE order path: THREE orders -- the entry, the covering hedge, the extra
    _oxkt, _oxkc = _k1_take(False)
    _oxl = _offline_trade_loop([_k1_A()], live=True, take=_oxkt, flags=_ox_on)
    _oxl_no = [c for c in _oxkc if c[0] == _kA and c[1] == "no"]
    _oxl_x = _kinds(_oxl, "hedge_extra", _kA)
    ck(_oxl["raised"] is None and len(_oxl_no) == 2
       and all(abs(c[2] - 5.0) < 1e-9 for c in _oxl_no)
       and abs(_hedged(_oxl, _kA) - 5.0) < 1e-9
       and len(_oxl_x) == 1 and _oxl_x[0].get("live") is True
       and abs(float(_oxl_x[0].get("n") or 0) - 5.0) < 1e-9
       and _oxl_x[0].get("order_id") is not None
       and _oxl_x[0].get("unknown") is False
       and len(_kinds(_oxl, "hedge", _kA)) == 1,
       "v-oddsmult LIVE PATH: two NO orders of 5 (the covering hedge, then the "
       "extra), one hedge record and one live hedge_extra record with its "
       "order id (NO orders %d, hedged %g, extras %d)"
       % (len(_oxl_no), _hedged(_oxl, _kA), len(_oxl_x)))
    _oxkt0, _oxkc0 = _k1_take(False)
    _oxl0 = _offline_trade_loop([_k1_A()], live=True, take=_oxkt0)
    ck(_oxl0["raised"] is None
       and len([c for c in _oxkc0 if c[0] == _kA and c[1] == "no"]) == 1
       and not _kinds(_oxl0, "hedge_extra"),
       "v-oddsmult NULL LIVE PATH: with the flag off exactly ONE NO order, as "
       "before")
    _oxsrc = inspect.getsource(trade_loop)
    ck(_oxsrc.count("odds_extra(") == 1
       and _oxsrc.index("_hn_want = flip_size(_hn, _entry_tau, _htau)")
       < _oxsrc.index("odds_extra(")
       < _oxsrc.index("_hn_take = min(float(_hn_want), float(_hdepth))")
       and _oxsrc.count('rec("hedge_extra"') == 2
       and _oxsrc.index('rec("hedge", ticker=_htk, side=_opp, price=_hcost2')
       < _oxsrc.rindex('rec("hedge_extra"')
       and _oxsrc.count("hedge_extra_done.add(_hid)") == 2
       and "_hdepth = hedge_depth(_asz, _hrungs, _hn)" in _oxsrc
       and "_left76 = float(_unhedged) - _hfilled" in _oxsrc
       and _oxsrc.count("hedge_attempts[_hcs] = ") == 1
       and 'assumed=0.0)' in _oxsrc,
       "v-oddsmult by source: one decision between the A54 size and the take "
       "size; two hedge_extra records (paper, live), the live one AFTER the "
       "covering hedge's own record; the extra is marked tried at both send "
       "sites; the covering hedge's depth, 'done' and attempt lines are "
       "untouched; an unknown extra counts nothing as covered")

''')

open(P, 'wb').write(s.replace('\n', '\r\n').encode('utf-8'))
print('patched', P)
