"""v-wrongside2: on top of v-wrongside (0925n), refuse ONLY WHILE the warning holds instead of for the whole close.
The refused look is given back the attempt it was charged above the late gates (it sends no order), so a market
refused at 20 Hz is not locked out by market_attempts. CRLF preserved; every anchor must occur exactly once.
usage: python patch_ws_while.py <path to the v-wrongside pinrun.py>"""
import sys

P = sys.argv[1]
src = open(P, 'rb').read().decode('utf-8')
assert '\r\n' in src
s = src.replace('\r\n', '\n')


def replace(old, new):
    global s
    n = s.count(old)
    assert n == 1, (n, old[:90])
    s = s.replace(old, new)


# 1. the constants comment
replace('''# hedge pass. A market it refuses stays refused for that close, because the
# rule measured skips the MARKET. No mid 5 s back (a fresh watch) or a
# one-sided book is no opinion and never blocks. 0 = off.''',
        '''# hedge pass. v-wrongside2 (operator 10-27: "Does it need to stay out of the
# market until close or just while it's happening?"): it refuses only WHILE
# the warning holds. Replayed on the 22 markets it skips: 7 of the 16 winners
# come back later (+$28.32), none of the 6 losers do (in every one the model
# had stopped wanting the bet before the warning cleared). A refused look is
# given back the attempt it was charged, because it sends no order. No mid
# 5 s back (a fresh watch) or a one-sided book is no opinion and never
# blocks. 0 = off.''')

# 2. loop state: no per-close block set
replace('''    ws_blocked = set()       # v-wrongside: (close_s, ticker) refused once =
                             # refused for the close (the rule skips a market)
''', '')

# 3. the early skip goes
replace('''                # v-wrongside: a market the wrong_side gate refused stays
                # refused for the close, HERE, above the attempt counters, so
                # its later looks spend none of the close's attempts (the late
                # gate's one refusal spends one, like every gate below them).
                if WS_RISE_C > 0 and (close_s, tk) in ws_blocked:
                    _gate("wrong_side_skip", close_s, tk, tau=tau)
                    continue
''', '')

# 4. the prune of the block set goes
replace('''                for _dk in [k for k in ws_blocked if k[0] < now_s - 900]:
                    ws_blocked.discard(_dk)
''', '')

# 5. the gate: only while it holds, attempt refunded
replace('''                # WS_RISE_C over the last WS_LOOKBACK_S s; refused once =
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
                    _gate("wrong_side",''',
        '''                # WS_RISE_C over the last WS_LOOKBACK_S s, judged afresh on
                # every look (v-wrongside2: only WHILE the warning holds). The
                # side and the rise are logged on every signal either way.
                _ws_k = (close_s, tk)
                _ws_held = bool(((prev or {}).get("sides") or {}).get(tk))
                _ws = wrongside_block(
                    want, spot, strike, book_mid(b),
                    mid_at(ws_mid.get(_ws_k), now - WS_LOOKBACK_S),
                    held=_ws_held, ladder=_lad is not None)
                if WS_RISE_C > 0 and not _ws_held and _lad is None and _ws[0]:
                    # THE ATTEMPT IS GIVEN BACK. Both counters were charged
                    # above the early gates for this look, and it sends no
                    # order; kept, three refused looks (150 ms) would lock the
                    # market out for the close through market_attempts, which
                    # is exactly the whole-close skip this version removes.
                    if not ATTEMPTS_ON_SEND:
                        attempts[close_s] = max(0, attempts.get(close_s, 0) - 1)
                        attempts_tk[(close_s, tk)] = max(
                            0, attempts_tk.get((close_s, tk), 0) - 1)
                    _gate("wrong_side",''')

# 6. argparse help
replace('''                         "cents over the last %g s; a refused market stays "
                         "refused for the close. Default 0 = off."''',
        '''                         "cents over the last %g s, judged afresh on every "
                         "look (the refused look keeps its attempt). Default "
                         "0 = off."''')

# 7. self-tests: the whole-close test becomes the comes-back test; the source check follows
replace('''    # refused once = refused for the close: flat until 10 s, then our mid
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
          sorted({r.get("gate") for r in _kinds(_wsl, "refused")})))''',
        '''    # v-wrongside2: refused only WHILE the warning holds. Flat until 10 s,
    # then our mid climbs 0.3c a second -- refused from ~30 s left for ~5 s
    # (about a hundred looks), never locked out by market_attempts because
    # every refused look keeps its attempt, and BOUGHT once the 5 s rise
    # passes 1c (13.4 s in)
    _ws_late = lambda t: (_ob(0.94, 0.05) if t < 10.0 else
                          _ob(round(0.94 + 0.003 * (t - 10.0), 4),
                              round(0.05 - 0.003 * (t - 10.0), 4)))
    _wsl = _offline_trade_loop([_ws_m(5, 101.0, _ws_late)], run_s=16.0,
                               tau0=38, flags=_ws_on)
    _wsls = _kinds(_wsl, "signal")
    ck(_wsl["raised"] is None and len(_wsls) >= 1
       and len(_refusals(_wsl, "wrong_side")) == 1
       and not _refusals(_wsl, "market_attempts")
       and not _refusals(_wsl, "attempts_cap")
       and float(_wsls[0].get("t") or 0) >= 13.0
       and float(_wsls[0].get("mid_rise_c") or 0) >= 1.0
       and _wsls[0].get("spot_wrong") is True,
       "v-wrongside2 DRIVEN: a market refused at ~30 s is NOT locked out "
       "(no market_attempts / attempts_cap) and is BOUGHT once its mid has "
       "risen 1c in 5 s (signals %d, first at %r s, rise %r, gates %s)"
       % (len(_wsls), _wsls[0].get("t") if _wsls else None,
          _wsls[0].get("mid_rise_c") if _wsls else None,
          sorted({r.get("gate") for r in _kinds(_wsl, "refused")})))''')

replace('''       and _wssrc.count('_gate("wrong_side_skip"') == 1
       and _wssrc.find('_gate("wrong_side_skip"')
       < _wssrc.find("if not ATTEMPTS_ON_SEND:")
''', '''       and '_gate("wrong_side_skip"' not in _wssrc
       and "ws_blocked" not in _wssrc
       and _wssrc.count("attempts[close_s] = max(0, attempts.get(close_s, 0) - 1)") == 1
       and _wssrc.find("if not ATTEMPTS_ON_SEND:")
       < _wssrc.find("attempts[close_s] = max(0, attempts.get(close_s, 0) - 1)")
       < _wssrc.find('_gate("wrong_side"')
''')
replace('''"after full_cap and before the signal record; the close-long skip sits "
       "above the attempt counters; it passes the held "''',
        '''"after full_cap and before the signal record; there is no close-long "
       "skip and a refused look refunds its attempt; it passes the held "''')

_left = [ln for ln in s.split(chr(10)) if ('ws_blocked' in ln or 'wrong_side_skip' in ln)
         and 'not in _wssrc' not in ln]
assert not _left, _left
open(P, 'wb').write(s.replace('\n', '\r\n').encode('utf-8'))
print('patched', P)
