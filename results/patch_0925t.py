"""Apply v-0925t to a COPY of the live pin build (C:\\kals-live-0925r: research\\pinrun.py code_sha
ca156bf45704, research\\pintake.py sha12 9150d6b65968). Patches BOTH files in place, CRLF preserved; every
anchor must occur exactly once; refuses an already-patched tree and a tree that is not 0925r.
usage: python patch_0925t.py <build_dir>      (build_dir holds research\\pinrun.py and research\\pintake.py)

The 0925s flags are folded in (defaults = 0925r's behaviour) and the post-11-10 bundle is added:

  --hedge-tick {legacy,round}     (v-hedgetick) "round" snaps the hedge limit (ask + --hedge-slip) DOWN to the
      market's own price grid. pin keeps no market object (price_level_structure / price_ranges are never
      stored), so the grid is read from the SERIES in the ticker: a 15-minute crypto series (name ends "15M")
      is tapered_deci_cent (0.1c under 10c and from 90c, 1c between); KXBTCD and every other series is
      linear_cent (1c everywhere, so the 99.9c wall rounds to 99c there). Never under the ask, never over
      HEDGE_MAX_ASK - 0.001; the YES-terms complement (1 - limit) is on the same grid. "legacy" = 0925r.
  --jump-hedge-min-ask X          (v-cheapjump) a JUMP-labelled hedge (belief still over the line, no panic)
      whose hedge side asks under X sends nothing that second, keeps its tries (refund), is not marked hedged,
      and logs hedge_cheap_skip once per position. 0 = off.
  --boost-rail {any,side,off}     (v-boostrail) the A53 band / A55 late "off at the first boosted loss" rails:
      "any" = every losing leg of the boosted market (0925r); "side" = only a losing leg on the boosted side;
      "off" = no rail ever trips, and every losing leg of a boosted market writes boost_rail_kept (rail "off")
      so the tracker can price what the rail would have done.
  --late-bypass-fix {off,on}      (v-latebypass) the late-mult bypass fix, BUILT BUT OFF BY DEFAULT. "on":
      _fullcap and _stage46 apply LATE_MULT only when late_boost_ok let THIS order's boost through, and
      late_bypass_refused records what the old line would have sized. "off" (the default): both sites size
      exactly as 0925r -- max(band_mult(price), _doubt_on[0], LATE_MULT if tau <= LATE_TAU else 1.0) -- and
      no late_bypass_refused is ever written. Gated OFF on the 11-04 audit: as always-on code it trimmed every
      late add on a refused-boost market to 0, and those legs were 23 of 23 winners (+$88.58 at size 322)
      against one event saved (BNB 10-19, -$133.52); the operator's rule is no break-even safety filters.
  Always on (code, no flag):
    * hedge / hedge_extra records carry tick_mode, limit_legacy, tick_rounded, ladder (<= 8 levels of _hrungs),
      close_s; the live hedge record carries status_code and err.
    * the v-oddsmult extra fires whenever belief < HEDGE_BELIEF with tau >= HEDGE_ODDS_MIN_TAU whatever the
      alarm's label (jump included); never on a stale-index alarm (market-price belief). hedge_extra carries
      trigger_label and fired_on_belief.
    * pintake: take(..., extra=True) -- covers_held no longer exempts the extra from MAX_RUN_STAKE / LOSS_ABORT;
      pinrun pre-trims the extra to the room and writes extra_stake_capped; the covering hedge is unchanged.
    * open_cap_relaxed: an entry that proceeds with >= 3 x SIZE contracts open (the old --max-positions 3
      would have paused) is recorded.
    * --hedge-odds-mult accepts [1.0, 2.0].
    * three wrong comments corrected (full_cap / late_add_full "burns no attempt"; the taper's "47 instead of
      114"; the extra's "pintake judges it as new exposure").
"""
import hashlib
import os
import sys

B = sys.argv[1]
PR = os.path.join(B, "research", "pinrun.py")
PT = os.path.join(B, "research", "pintake.py")
BASE_PINRUN, BASE_PINTAKE = "ca156bf45704", "9150d6b65968"


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


assert sha12(PR) == BASE_PINRUN, "research/pinrun.py is not 0925r (%s)" % sha12(PR)
assert sha12(PT) == BASE_PINTAKE, "research/pintake.py is not 0925r (%s)" % sha12(PT)
R = Src(PR)
T = Src(PT)
assert ("HEDGE_TICK" not in R.s and "JUMP_HEDGE_MIN_ASK" not in R.s and "BOOST_RAIL" not in R.s
        and "LATE_BYPASS_FIX" not in R.s
        and "late_bypass_refused" not in R.s and "extra_stake_capped" not in R.s
        and "open_cap_relaxed" not in R.s), "already patched"
assert "extra=False" not in T.s and "v-extracap" not in T.s, "already patched (pintake)"
assert "HEDGE_ODDS_MULT" in R.s and "odds_extra(" in R.s, "not the 0925r build (v-oddsmult missing)"

# ===========================================================================================================
# pinrun.py
# ===========================================================================================================

# 1. the constants, next to the v-oddsmult ones
R.after('HEDGE_ODDS_MIN_TAU = 11\n_DEFAULT_HEDGE_ODDS_MIN_TAU = 11\n', '''# v-hedgetick (2026-11-04). Kalshi's 15-minute crypto markets have
# price_level_structure "tapered_deci_cent": prices step 0.1c in [0, 10c) and
# [90c, $1], 1c in [10c, 90c). KXBTCD (the hourly ladder) is "linear_cent": 1c
# everywhere. hedge_limit() sends ask + --hedge-slip (0.10 live), so a
# deci-cent hedge ask under 10c -- 1.5c -- became an 11.5c limit, which is OFF
# the grid. Kalshi rejected every one: 202 of 202 such hedge sends since the
# slip went live came back with order_id null and n 0, and the pass re-sent
# the same off-grid price every second, 30-42 times; 19 of 19 on-grid hedge
# sends were accepted. "round" snaps the limit DOWN to the market's grid
# (integer mils, so float noise cannot move a step), never under the ask (the
# ask is always on the grid) and still under the $1 wall. pin keeps NO market
# object (the universe refresh stores ticker, close, strike and index only;
# price_ranges is never read), so the grid is chosen from the SERIES in the
# ticker (price_grid_for): a series whose name ends in "15M" is tapered;
# KXBTCD and every other series is linear, where the 99.9c wall rounds to 99c.
# Orders go out in YES terms (1 - limit for a NO buy) and both grids are
# symmetric, so an on-grid limit stays on the grid on the wire. "legacy" =
# 0925r exactly (the shipped value). The ladder read (book.rungs up to the
# limit) cannot change: no rung can sit strictly between the rounded and the
# legacy limit, because that interval holds no grid price.
HEDGE_TICK = "legacy"
_DEFAULT_HEDGE_TICK = "legacy"
GRID_TAPERED = "tapered_deci_cent"
GRID_LINEAR = "linear_cent"
# v-cheapjump (2026-11-04). The A52 JUMP trigger fires on a 6-8 sd index move
# while pin's belief is still OVER the 0.40 line; when the hedge side then
# asks only a few cents the market still prices our side at 95c+, and the
# cheap legs bought there are exactly the hedge legs that lost on markets our
# side won (the 11-01 tally: jump hedges -$30 on 18 fires). --jump-hedge-min-ask
# X: a jump-triggered hedge whose hedge-side ask is UNDER X sends nothing that
# second -- never on the belief line (belief under --hedge-belief, whatever
# the trigger label says), never in a panic, never on a stale-index alarm.
# The position is NOT marked hedged and the second's try is REFUNDED, so the
# belief line keeps all of its HEDGE_MAX_TRIES and fires exactly as today if
# belief later crosses it; a dearer ask hedges on the jump as today. Logged
# once per position as kind hedge_cheap_skip. 0.0 = off (the shipped value);
# at most 0.10.
JUMP_HEDGE_MIN_ASK = 0.0
_DEFAULT_JUMP_HEDGE_MIN_ASK = 0.0
# v-boostrail (2026-11-04). The A53 band boost and the A55 late boost each
# switch themselves off for the run at the first losing leg on a boosted
# market (reconcile, `if not won:`). A hedge fill is booked into open_pos as
# its own leg, so a hedge that LOSES on a market our boosted side WON trips the
# rail too: all 3 band trips since 10-21 and both late trips ever were exactly
# that -- a losing leg on the side OPPOSITE the boosted order (a cheap false
# jump hedge, or an unboosted leg) on a market whose boosted side won.
# --boost-rail side: each rail trips only on a losing leg on the SIDE the boost
# was recorded for. --boost-rail off: no rail ever trips, and every losing leg
# of a boosted market is written down as boost_rail_kept (rail "off") so the
# tracker can price what the rail would have switched off. "any" = 0925r
# exactly (the shipped value): every losing leg. Sizing is untouched in every
# mode; only the off-switch reads the side.
BOOST_RAIL = "any"
_DEFAULT_BOOST_RAIL = "any"
# v-latebypass (2026-11-04): --late-bypass-fix on = the late multiple only past late_boost_ok; off (shipped) = 0925r sizing
LATE_BYPASS_FIX = False
_DEFAULT_LATE_BYPASS_FIX = False
''')

# 2. hedge_limit: the grid, behind the flag; "legacy" returns the very same value as before
R.replace('def hedge_limit(ask, slip=None):\n', 'def hedge_limit(ask, slip=None, tick=None, ticker=None):\n')
R.replace('''    # a hedge leg at or over $1 cannot beat holding (hedge_ask_ok), so the
    # limit stops one tenth of a cent below it however big the slip is.
    return min(a + s, HEDGE_MAX_ASK - 0.001)
''', '''    # a hedge leg at or over $1 cannot beat holding (hedge_ask_ok), so the
    # limit stops one tenth of a cent below it however big the slip is.
    lim = min(a + s, HEDGE_MAX_ASK - 0.001)
    # v-hedgetick: `tick` (HEDGE_TICK unless given) "round" snaps that limit
    # DOWN to the market's price grid (price_grid_for(ticker): tapered for a
    # 15M series, linear 1c for KXBTCD and everything else) -- 1.5c + 10c =
    # 11.5c is off the tapered grid and was rejected 202 times of 202; 11c is
    # on it; on KXBTCD the 99.9c wall becomes 99c. Never under the ask (an
    # on-grid ask is a grid price at or under the limit, so the floor cannot
    # pass it), never over the $1 wall above. Anything else -- the shipped
    # "legacy", or garbage -- returns `lim` itself, unchanged.
    t = HEDGE_TICK if tick is None else tick
    if t != "round":
        return lim
    fl = tick_floor(lim, price_grid_for(ticker))
    if fl is None:
        return lim
    return max(fl, min(a, lim))


def price_grid_for(ticker):
    """v-hedgetick: which Kalshi price grid a market trades on, from its
    SERIES (the ticker up to the first "-"). pin never keeps the market
    object's price_level_structure / price_ranges, so this is the rule: a
    15-minute crypto series (name ends in "15M") is tapered_deci_cent; KXBTCD
    and every other series is linear_cent. None or garbage: tapered (the 15M
    default, i.e. what 0925s assumed for every market). Cannot raise."""
    if ticker is None:
        return GRID_TAPERED
    try:
        s = str(ticker).split("-", 1)[0].strip().upper()
    except Exception:                                    # noqa: BLE001
        return GRID_TAPERED
    if not s:
        return GRID_TAPERED
    return GRID_TAPERED if s.endswith("15M") else GRID_LINEAR


def grid_from_ranges(ranges):
    """v-hedgetick: classify a Kalshi market's `price_ranges`
    ([{start, end, step}, ...], dollars) into one of the two grids, for the
    day pin keeps the market object: one 0.01 step over the whole dollar is
    linear_cent; 0.001 under 0.10 and from 0.90 with 0.01 between is
    tapered_deci_cent. None when it is neither or unreadable. Not wired into
    the hedge pass today (pin has no market object there); price_grid_for is."""
    try:
        rs = sorted(((float(r["start"]), float(r["end"]), float(r["step"]))
                     for r in ranges), key=lambda x: x[0])
    except Exception:                                    # noqa: BLE001
        return None
    if not rs:
        return None
    _m = lambda x: int(round(float(x) * 1000.0))
    steps = [_m(st) for _s, _e, st in rs]
    if len(rs) == 1 and steps == [10] and _m(rs[0][0]) <= 1 and _m(rs[0][1]) >= 990:
        return GRID_LINEAR
    if (len(rs) == 3 and steps == [1, 10, 1]
            and _m(rs[0][1]) == 100 and _m(rs[1][0]) == 100
            and _m(rs[1][1]) == 900 and _m(rs[2][0]) == 900):
        return GRID_TAPERED
    return None


def tick_floor(price, grid=GRID_TAPERED):
    """v-hedgetick: the highest price on `grid` at or under `price`.
    tapered_deci_cent: 0.1c steps in [0, 10c) and [90c, $1], 1c steps between;
    linear_cent: 1c steps everywhere. Integer mils with a one-micro-mil
    allowance, so float noise -- 0.083 + 0.10 is 0.18300000000000002, and a
    sum can as easily land a hair UNDER a step -- can never move a step. None
    on garbage. Cannot raise."""
    try:
        m = int(math.floor(float(price) * 1000.0 + 1e-6))
    except (TypeError, ValueError, OverflowError):
        return None
    if grid == GRID_LINEAR or (100 <= m < 900):
        m -= m % 10
    return m / 1000.0


def deci_tick_floor(price):
    """v-hedgetick: tick_floor on the tapered_deci_cent grid (the 15M one)."""
    return tick_floor(price, GRID_TAPERED)


def hedge_ladder_log(rungs, n=8):
    """v-0925t: the hedge-side ask ladder as [[price, size], ...], at most `n`
    levels, for the hedge / hedge_extra records (the depth question the
    1.25x fills cannot answer). Unreadable rungs are skipped. Cannot raise."""
    out = []
    for r in (rungs or ()):
        try:
            out.append([round(float(r[0]), 4), round(float(r[1]), 2)])
        except (TypeError, ValueError, IndexError):
            continue
        if len(out) >= n:
            break
    return out


def extra_stake_cap(asked, price, side, ledger, max_run_stake, loss_abort):
    """v-extracap (2026-11-04): how much of the v-oddsmult EXTRA leg the two
    dollar rails leave room for, judged the way pintake.check_take judges a
    non-covering order: (allowed, reason). `price` is what we pay per
    contract of `side`; the collateral is computed as the wire body will
    carry it (a NO buy goes out as a YES ask at round(1 - price, 4)).
      realised <= LOSS_ABORT          -> (0.0, "loss_abort")
      committed + asked x p <= cap    -> (asked, None)
      otherwise                       -> (the 2-dp count that still fits,
                                          "max_run_stake")
    Garbage anywhere: (asked, None) -- no pre-trim; pintake's own rails
    (extra=True) then judge the order and hedge_extra_refused says why."""
    try:
        n = float(asked)
        p = float(price)
        committed = float((ledger or {}).get("committed") or 0.0)
        realised = float((ledger or {}).get("realised") or 0.0)
        mrs = float(max_run_stake)
        la = float(loss_abort)
        if str(side).lower() == "no":
            p_eff = 1.0 - round(1.0 - p, 4)
        else:
            p_eff = round(p, 4)
    except (TypeError, ValueError):
        return asked, None
    if not (n > 0.0) or not (p_eff > 0.0):
        return 0.0, None
    if realised <= la:
        return 0.0, "loss_abort"
    if committed + n * p_eff <= mrs + 1e-9:
        return n, None
    allowed = max(0.0, math.floor(((mrs - committed) / p_eff) * 100.0 + 1e-9) / 100.0)
    while allowed > 0.0 and committed + allowed * p_eff > mrs + 1e-9:
        allowed = max(0.0, round(allowed - 0.01, 2))
    return allowed, "max_run_stake"
''')

# 3. the two pure decisions, after jump_capped (where v-oddsmult put odds_extra)
R.after('''        return float(jump_sd) >= float(c)
    except (TypeError, ValueError):
        return False
''', '''

def cheap_jump_skip(trigger, panic, belief, ask, min_ask=None, threshold=None):
    """v-cheapjump (--jump-hedge-min-ask X): True when the hedge pass must SEND
    NOTHING this second -- the JUMP trigger fired while the hedge side still
    asks under X, i.e. the market still prices our side at 1 - ask. Never when
    X is 0 (off, the shipped value), never in a panic, never on the belief
    line (belief under --hedge-belief: the A52 label stays "jump" while a jump
    is still inside the lookback even after belief has crossed the line, so
    the label alone is not enough), never on the belief or stale-index
    triggers. Garbage anywhere: False, i.e. hedge exactly as today. Cannot
    raise."""
    x = JUMP_HEDGE_MIN_ASK if min_ask is None else min_ask
    try:
        x = float(x)
        a = float(ask)
        b = float(belief)
    except (TypeError, ValueError):
        return False
    if not (x > 0.0) or trigger != "jump" or panic or b != b:
        return False
    try:
        if hedge_should_fire(b, threshold):
            return False
    except (TypeError, ValueError):
        return False
    return 0.0 < a < x


def boost_rail_trips(mode, boosted_side, leg_side):
    """v-boostrail (--boost-rail): does a LOSING leg on a boosted market switch
    that boost off for the rest of the run? "any" (the shipped value, 0925r
    exactly): yes, every losing leg -- hedge legs included, since a hedge fill
    is booked into open_pos as its own leg. "side": only a losing leg whose own
    side is the side the boost was recorded for (`boosted_side`: one side, or
    a collection when both sides of one market were boosted). "off": never --
    the caller writes boost_rail_kept instead, for every losing leg. Anything
    it cannot read -- an unknown mode, no recorded side, garbage -- trips, i.e.
    falls back to today's rail. Cannot raise."""
    if mode == "off":
        return False
    if mode != "side":
        return True
    try:
        if boosted_side is None:
            return True
        if isinstance(boosted_side, str):
            return leg_side == boosted_side
        _sides = set(boosted_side)
        if not _sides:
            return True
        return leg_side in _sides
    except Exception:                                    # noqa: BLE001
        return True
''')

# 4. the extra fires on the belief line whatever the alarm's label (never a stale-index alarm)
R.replace('''    """v-oddsmult: EXTRA contracts of the hedge side to buy over the covering
    hedge: (mult - 1) x the position, only when the hedge fired on the belief
    line (trigger "belief" with belief under the line) with at least `min_tau`
    seconds left. 0.0 otherwise: at a multiple of 1 or less, on the jump
    trigger whatever the belief, on a stale-index alarm, inside the tau floor,
    on an empty position or on garbage. Cannot raise."""
''', '''    """v-oddsmult: EXTRA contracts of the hedge side to buy over the covering
    hedge: (mult - 1) x the position, only when the MODEL's belief in our side
    is under the hedge line with at least `min_tau` seconds left. v-0925t: the
    alarm's LABEL no longer matters -- a 6-8 sd jump alarm (label "jump") with
    belief already under the line carries the extra too (the 11-04 ZEC shape
    fired it only because its 11.6 sd jump was capped and the label fell back
    to "belief"). What is kept: never on a stale-index alarm (label
    "market_index_stale": that belief is the MARKET's ask, the model's own
    number is frozen, and K3's rule is that the market fallback never moves
    NEW exposure), nothing at a multiple of 1 or less, inside the tau floor,
    with belief at or over the line (a jump alarm at belief 0.85 still buys
    no extra), on an empty position, on a label that is neither "belief" nor
    "jump", or on garbage. Cannot raise."""
''')
R.replace('''    if m <= 1.0 or not (n > 0.0) or trigger != "belief" or t < mt:
        return 0.0
''', '''    if m <= 1.0 or not (n > 0.0) or trigger not in ("belief", "jump") or t < mt:
        return 0.0
''')
R.replace('''# made $253.07; 2x would have added +$180..+$225. The extra rides ONLY with a
# belief-triggered hedge (never the jump trigger, never a stale-index alarm),
# goes out as its OWN order right after the covering hedge (pintake judges it
# as new exposure; the covering hedge is exactly the order it was), once per
# position. 1.0 = off (the shipped value). Live from 1.25 (the tiny-test rule).
''', '''# made $253.07; 2x would have added +$180..+$225. The extra rides with any
# hedge fired with the model's belief UNDER the line (v-0925t: whatever the
# alarm's label, so a 6-8 sd jump alarm at belief 0.30 carries it; never a
# stale-index alarm, whose belief is the market's), goes out as its OWN order
# right after the covering hedge (pintake judges it with the stake cap and
# the loss abort -- take(..., extra=True); the covering hedge is exactly the
# order it was), once per position. 1.0 = off (the shipped value). Live from
# 1.25 (the tiny-test rule); at most 2.0.
''')

# 5. the offline loop pins all four flags at their shipped defaults
R.replace('''    "HEDGE_ODDS_MULT", "HEDGE_ODDS_MIN_TAU")
''', '''    "HEDGE_ODDS_MULT", "HEDGE_ODDS_MIN_TAU",
    "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX")
''')
# ...and the self-test's own "gave every live setting back" guard watches them
R.replace('''                 "COIN_SIZE_FRAC", "BAND99_CEILING", "BAND99_FRAC")
''', '''                 "COIN_SIZE_FRAC", "BAND99_CEILING", "BAND99_FRAC",
                 "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX")
''')

# 6. per-run state
R.after('''    hedge_extra_done = set() # v-oddsmult: positions whose extra leg was tried
''', '''    hedge_cheap_said = set() # v-cheapjump: positions whose cheap jump skip was logged
    band_boost_sides = {}    # v-boostrail: (close_s, ticker) -> sides A53 widened
    late_boost_sides = {}    # v-boostrail: the same, for the A55 late boost
    late_bypass_said = set() # v-latebypass: (close_s, ticker, path) already on the record
''')

# 7. the boosts record WHICH side they widened (read only by the rails, and only under --boost-rail side/off)
R.after('''                        _boosted48.add((close_s, tk))
''', '''                        late_boost_sides.setdefault((close_s, tk), set()).add(want)
''')
R.after('''                        boosted.add((close_s, tk))
''', '''                        band_boost_sides.setdefault((close_s, tk), set()).add(want)
''')

# 8. the two rails, in reconcile's loss branch. `want` there is the settling LEG's own side (open_pos values are
# (close_s, want, cost, nfill, tk); a hedge leg is booked with its own side). "any": the helper is True and the
# branch is the line as it was; "side": a losing leg on the other side keeps the boost on and says so once;
# "off": every losing leg on a boosted market keeps it on and says so.
R.replace('''                if BAND_MULTS and (close_s, tk) in boosted:
''', '''                # v-boostrail: under --boost-rail side only a losing leg on
                # the boosted SIDE trips this; under off nothing does; "any"
                # (the shipped value) is the line as it was -- every losing
                # leg on the market.
                if (BAND_MULTS and (close_s, tk) in boosted
                        and boost_rail_trips(BOOST_RAIL, band_boost_sides.get((close_s, tk)), want)):
''')
R.replace('''                    print(f"  *** A BOOSTED LOSS on {tk}: --band-mult is OFF "
                          f"for the rest of this run ***")
''', '''                    print(f"  *** A BOOSTED LOSS on {tk}: --band-mult is OFF "
                          f"for the rest of this run ***")
                elif BAND_MULTS and (close_s, tk) in boosted:
                    # v-boostrail (side / off): the rail did not trip -- the
                    # losing leg is not the boosted side (a hedge leg on a
                    # market the boost won), or the rail is off -- said once
                    rec("boost_rail_kept", which="band", ticker=tk, close_s=close_s,
                        leg_side=want, boosted_side=sorted(band_boost_sides.get((close_s, tk)) or []),
                        cost=round(cost, 4), pnl_c=round(100 * pnl, 2), rail=BOOST_RAIL,
                        live=bool(live))
                    print(f"  boost rail KEPT on {tk} (--boost-rail {BOOST_RAIL}): the losing "
                          f"leg is {want}, the band boost was on "
                          f"{sorted(band_boost_sides.get((close_s, tk)) or [])}")
''')
R.replace('''                if LATE_MULT > 1.0 and (close_s, tk) in _boosted48:
''', '''                # v-boostrail: the same rule for the late boost
                if (LATE_MULT > 1.0 and (close_s, tk) in _boosted48
                        and boost_rail_trips(BOOST_RAIL, late_boost_sides.get((close_s, tk)), want)):
''')
R.replace('''                    print(f"  *** A LATE-BOOSTED LOSS on {tk}: --late-mult is "
                          f"OFF for the rest of this run ***")
''', '''                    print(f"  *** A LATE-BOOSTED LOSS on {tk}: --late-mult is "
                          f"OFF for the rest of this run ***")
                elif LATE_MULT > 1.0 and (close_s, tk) in _boosted48:
                    rec("boost_rail_kept", which="late", ticker=tk, close_s=close_s,
                        leg_side=want, boosted_side=sorted(late_boost_sides.get((close_s, tk)) or []),
                        cost=round(cost, 4), pnl_c=round(100 * pnl, 2), rail=BOOST_RAIL,
                        live=bool(live))
                    print(f"  boost rail KEPT on {tk} (--boost-rail {BOOST_RAIL}): the losing "
                          f"leg is {want}, the late boost was on "
                          f"{sorted(late_boost_sides.get((close_s, tk)) or [])}")
''')

# 9. the hedge pass: the cheap jump skip, AFTER every existing filter (each keeps its own record, set and try exactly
# as before) and BEFORE anything that sizes, counts an attempt or sends -- so one site serves the paper AND the live
# send, which both sit below it (`if not live:` / pintake.take)
R.before('''                    # A54: if this position was opened on the EARLY leg and the
''', '''                    # v-cheapjump (--jump-hedge-min-ask X): a JUMP-triggered
                    # hedge whose hedge side still asks under X sends NOTHING
                    # this second (never the belief line, never a panic -- see
                    # cheap_jump_skip). Here, below every filter above, so each
                    # of them keeps its own record, set and try exactly as
                    # before, and above everything below, so nothing is sized,
                    # counted as an attempt or sent -- paper or live. The try
                    # this second took is REFUNDED: thirty seconds of a cheap
                    # ask must not spend the belief line's tries (a give-up
                    # marks the position hedged for good), and it is NOT added
                    # to `hedged`, so the belief line -- or a dearer ask on the
                    # jump -- still hedges exactly as today.
                    if cheap_jump_skip(_htrig, _panic, _belief, _ask):
                        hedge_tries[_hid] = _tries  # v-cheapjump REFUND
                        if _hid not in hedge_cheap_said:
                            hedge_cheap_said.add(_hid)
                            rec("hedge_cheap_skip", ticker=_htk, close_s=_hcs, side=_opp,
                                ask=float(_ask), min_ask=JUMP_HEDGE_MIN_ASK,
                                jump_sd=(round(_hjmp, 2) if _hjmp is not None else None),
                                belief=round(_belief, 5), tau=_htau, want=_hwant,
                                n=_hn, entry=_hcost, live=bool(live))
                            print(f"  hedge SKIPPED (cheap jump) {_htk}: {_opp} asks "
                                  f"{float(_ask):.3f} under {JUMP_HEDGE_MIN_ASK:.3f}, "
                                  f"belief {_belief:.3f}")
                        continue
''')

# 10. the limit on the market's grid, the legacy limit beside it, the ladder for the records
R.replace('''                    _hlimit = hedge_limit(_ask)
                    if _hlimit is None:
                        _hlimit = float(_ask)
''', '''                    _hlimit = hedge_limit(_ask, ticker=_htk)
                    if _hlimit is None:
                        _hlimit = float(_ask)
                    # v-hedgetick: the limit the OLD line would have sent, so
                    # every hedge record can say whether the grid moved it
                    _hlim_legacy = hedge_limit(_ask, tick="legacy")
                    if _hlim_legacy is None:
                        _hlim_legacy = float(_ask)
                    _htick_rounded = (round(float(_hlimit), 4) != round(float(_hlim_legacy), 4))
''')
R.replace('''                    _hdepth = hedge_depth(_asz, _hrungs, _hn)
                    _hn_take = min(float(_hn_want), float(_hdepth))
''', '''                    _hdepth = hedge_depth(_asz, _hrungs, _hn)
                    _hladder = hedge_ladder_log(_hrungs)   # v-0925t: <= 8 levels, for the records
                    _hn_take = min(float(_hn_want), float(_hdepth))
''')
# the paper hedge record
R.replace('''                            n=_hn_take, entry=_hcost, tau=_htau, belief=round(_belief, 5),
                            locked_loss_c=round(100 * hedge_locked_loss(_hcost, _hpaper), 2),
                            edge_c=hedge_edge_c(_belief, _hpaper), live=False)
''', '''                            n=_hn_take, entry=_hcost, tau=_htau, belief=round(_belief, 5),
                            locked_loss_c=round(100 * hedge_locked_loss(_hcost, _hpaper), 2),
                            edge_c=hedge_edge_c(_belief, _hpaper), live=False,
                            # v-0925t: the grid, the old limit, and the ladder
                            close_s=_hcs, tick_mode=HEDGE_TICK,
                            limit_legacy=round(float(_hlim_legacy), 4),
                            tick_rounded=bool(_htick_rounded), ladder=_hladder)
''')
# the paper extra record
R.replace('''                                        tau=_htau, belief=round(_belief, 5), trigger=_htrig,
                                        status="executed", live=False)
''', '''                                        tau=_htau, belief=round(_belief, 5), trigger=_htrig,
                                        status="executed", live=False,
                                        # v-0925t: the label it fired under, and why
                                        close_s=_hcs, trigger_label=_htrig,
                                        fired_on_belief=bool(hedge_should_fire(_belief)),
                                        tick_mode=HEDGE_TICK,
                                        limit_legacy=round(float(_hlim_legacy), 4),
                                        tick_rounded=bool(_htick_rounded), ladder=_hladder)
''')
# the live hedge record: the exchange's answer (0925s) + the grid fields
R.replace('''                        past_halt=_hout.get("past_halt"),
''', '''                        past_halt=_hout.get("past_halt"),
                        # v-hedgetick: the exchange's answer on EVERY live hedge
                        # record -- 202 off-grid sends came back 400 and the
                        # record said only order_id null, n 0
                        status_code=_hsc,
                        err=(str(_hout.get("error"))[:200]
                             if _hout.get("error") is not None else None),
                        # v-0925t: the grid, the old limit, and the ladder
                        close_s=_hcs, tick_mode=HEDGE_TICK,
                        limit_legacy=round(float(_hlim_legacy), 4),
                        tick_rounded=bool(_htick_rounded), ladder=_hladder,
''')
# the live extra: the right comment, the pre-trim, extra=True on the wire, the record's new fields
R.replace('''                    # v-oddsmult: the EXTRA leg, its own order, only behind a
                    # covering hedge that filled, one try per position. pintake
                    # sees an order larger than the position is not a covering
                    # hedge and judges it with every dollar rail; a refusal
                    # costs the extra and nothing else. Guarded: a fault here
                    # can only lose the extra, never the hedge above.
                    if _hx_n > 0 and _hfilled > 0:
                        hedge_extra_done.add(_hid)
                        try:
                            if _hx_take <= 1e-9:
''', '''                    # v-oddsmult: the EXTRA leg, its own order, only behind a
                    # covering hedge that filled, one try per position.
                    # v-extracap (2026-11-04): THE OLD COMMENT HERE WAS WRONG.
                    # It said pintake "sees an order larger than the position
                    # is not a covering hedge and judges it with every dollar
                    # rail". It does not: pintake books the cover into the
                    # SAME position (contracts 2 x n after the cover), and
                    # covers_held compares the extra's count with that, so a
                    # (mult - 1) x n extra up to 2.0x passed as a cover and
                    # skipped MAX_RUN_STAKE and LOSS_ABORT. Now the extra goes
                    # out with extra=True (pintake judges it with both dollar
                    # rails; the covering hedge keeps its exemption exactly),
                    # and it is TRIMMED here first to the room those rails
                    # leave (extra_stake_cap), written as extra_stake_capped,
                    # so a cap costs contracts, not the whole leg. A refusal
                    # costs the extra and nothing else. Guarded: a fault here
                    # can only lose the extra, never the hedge above.
                    if _hx_n > 0 and _hfilled > 0:
                        hedge_extra_done.add(_hid)
                        try:
                            _hx_allow, _hx_why = float(_hx_take), None
                            if _hx_take > 1e-9:
                                _hx_allow, _hx_why = extra_stake_cap(
                                    _hx_take, float(_hlimit), _opp, pintake.LEDGER,
                                    pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT)
                                if float(_hx_allow) < float(_hx_take) - 1e-9:
                                    rec("extra_stake_capped", ticker=_htk, close_s=_hcs,
                                        side=_opp, asked=round(float(_hx_take), 2),
                                        allowed=round(float(_hx_allow), 2),
                                        trimmed=round(float(_hx_take) - float(_hx_allow), 2),
                                        reason=_hx_why, mult=HEDGE_ODDS_MULT, live=True)
                                    print(f"  HEDGE EXTRA {_htk} capped by {_hx_why}: "
                                          f"{float(_hx_take):g} -> {float(_hx_allow):g}")
                            if _hx_take <= 1e-9:
''')
R.replace('''                                    mult=HEDGE_ODDS_MULT, ladder_n=round(float(_hdepth), 2),
                                    tau=_htau, live=True)
                            else:
                                attempts[_hcs] = attempts.get(_hcs, 0) + 1
                                hedge_attempts[_hcs] += 1
                                _hxt_ms = int(round(time.time() * 1000.0))
                                _hxout = pintake.take(CREDS["base"], CREDS["pk"], CREDS["key_id"],
                                                      _htk, _opp, float(_hlimit), _hx_take,
                                                      float(_hcs), exchange_index=2,
                                                      hedge=True)
''', '''                                    mult=HEDGE_ODDS_MULT, ladder_n=round(float(_hdepth), 2),
                                    tau=_htau, live=True)
                            elif float(_hx_allow) <= 1e-9:
                                # v-extracap: the dollar rails leave no room --
                                # extra_stake_capped above says so; nothing sent
                                pass
                            else:
                                _hx_take = float(_hx_allow)
                                attempts[_hcs] = attempts.get(_hcs, 0) + 1
                                hedge_attempts[_hcs] += 1
                                _hxt_ms = int(round(time.time() * 1000.0))
                                _hxout = pintake.take(CREDS["base"], CREDS["pk"], CREDS["key_id"],
                                                      _htk, _opp, float(_hlimit), _hx_take,
                                                      float(_hcs), exchange_index=2,
                                                      hedge=True, extra=True)
''')
R.replace('''                                        unknown=bool(_hxunk), live=True,
                                        t_ms_decide=_ht_decide_ms, t_ms_send=_hxt_ms,
''', '''                                        unknown=bool(_hxunk), live=True,
                                        # v-0925t: the label it fired under, and why
                                        close_s=_hcs, trigger_label=_htrig,
                                        fired_on_belief=bool(hedge_should_fire(_belief)),
                                        tick_mode=HEDGE_TICK,
                                        limit_legacy=round(float(_hlim_legacy), 4),
                                        tick_rounded=bool(_htick_rounded), ladder=_hladder,
                                        t_ms_decide=_ht_decide_ms, t_ms_send=_hxt_ms,
''')
# the jump_capped note's limit on the market's grid too
R.replace('''                _lm = hedge_limit(float(_a))
''', '''                _lm = hedge_limit(float(_a), ticker=tk_)
''')

# 11. the late-mult bypass: _fullcap and _stage46 read whether late_boost_ok refused THIS order's boost -- only
# under --late-bypass-fix on. OFF by default: both sites then size exactly as 0925r and write no record.
R.replace('''                _doubt_on = [1.0]

                def _doubt(take_n):
''', '''                _doubt_on = [1.0]
                # v-latebypass (2026-11-04): False once late_boost_ok has
                # refused THIS order's late boost. `_fullcap` and `_stage46`
                # apply LATE_MULT at tau <= LATE_TAU regardless (0925r), so a
                # top-up or a late add on a market whose boost the confidence
                # or jump bar had just REFUSED is still sized against the 1.5x
                # room. Under --late-bypass-fix on both read this flag and use
                # the late multiple only while it is True, writing
                # late_bypass_refused with what the old line would have sized;
                # off (the shipped value) they size exactly as 0925r and this
                # flag is set but never read. Gated OFF on the 11-04 audit:
                # those refused-boost late adds were 23 of 23 winners (+$88.58
                # at size 322) against one event saved (BNB 10-19, -$133.52).
                _late_ok46 = [True]

                def _doubt(take_n):
''')
R.replace('''                    if not late_boost_ok(_ours48, _jmp48):
                        boost_why[(close_s, tk)] = (
''', '''                    if not late_boost_ok(_ours48, _jmp48):
                        _late_ok46[0] = False        # v-latebypass: no 1.5x room below either
                        boost_why[(close_s, tk)] = (
''')
R.replace('''                    _mult_fc = max(band_mult(price), _doubt_on[0],
                                   LATE_MULT if tau <= LATE_TAU else 1.0)
                    _room_fc = full_bet_room(prev, tk, want, _mult_fc,
                                             hedged=hedged_side.get(tk),
                                             size=_ssz if _ssz is not None else _csz)
                    if _room_fc is None or float(take_n) <= _room_fc + 1e-9:
                        return take_n
''', '''                    _late_fc = LATE_MULT if tau <= LATE_TAU else 1.0
                    # v-latebypass: under --late-bypass-fix on, the late
                    # multiple only when late_boost_ok let THIS order's boost
                    # through; off (the shipped value) = the 0925r line exactly
                    _mult_fc = max(band_mult(price), _doubt_on[0],
                                   _late_fc if (_late_ok46[0] or not LATE_BYPASS_FIX) else 1.0)
                    _room_fc = full_bet_room(prev, tk, want, _mult_fc,
                                             hedged=hedged_side.get(tk),
                                             size=_ssz if _ssz is not None else _csz)
                    if LATE_BYPASS_FIX and not _late_ok46[0] and _late_fc > 1.0:
                        # what the OLD line (the late multiple whatever the
                        # bar said) would have sized this order at, on the
                        # record when it differs
                        _room_fc0 = full_bet_room(prev, tk, want,
                                                  max(band_mult(price), _doubt_on[0], _late_fc),
                                                  hedged=hedged_side.get(tk),
                                                  size=_ssz if _ssz is not None else _csz)
                        _n_fc0 = (float(take_n) if (_room_fc0 is None or float(take_n) <= _room_fc0 + 1e-9)
                                  else max(0.0, float(_room_fc0)))
                        _n_fc1 = (float(take_n) if (_room_fc is None or float(take_n) <= _room_fc + 1e-9)
                                  else max(0.0, float(_room_fc)))
                        # once per market and path: the old line would have
                        # sent this order ONCE; a trim to zero is retried by
                        # the next pass (zero_take) until the attempt cap
                        if (abs(_n_fc0 - _n_fc1) > 1e-9
                                and (close_s, tk, "fullcap") not in late_bypass_said):
                            late_bypass_said.add((close_s, tk, "fullcap"))
                            rec("late_bypass_refused", ticker=tk, close_s=close_s, side=want,
                                path="fullcap", tau=tau, price=round(float(price), 4),
                                n_before=round(_n_fc0, 2), n_after=round(_n_fc1, 2),
                                mult=float(_late_fc), leg=_leg46, live=bool(live))
                    if _room_fc is None or float(take_n) <= _room_fc + 1e-9:
                        return take_n
''')
R.replace('''                    if EARLY_TAU_MAX > TAU_MAX and _leg46 != "full":
                        _mult46 = max(band_mult(price), _doubt_on[0],
                                      LATE_MULT if tau <= LATE_TAU else 1.0)
                        return min(take_n, staged_take(tau, take_n,
                                                       _fsz * _mult46,
                                                       _held46)[0])
                    return take_n
''', '''                    if EARLY_TAU_MAX > TAU_MAX and _leg46 != "full":
                        _late46 = LATE_MULT if tau <= LATE_TAU else 1.0
                        # v-latebypass: under --late-bypass-fix on, the late
                        # multiple only when late_boost_ok let THIS order's
                        # boost through; off (the shipped value) = the 0925r
                        # line exactly
                        _mult46 = max(band_mult(price), _doubt_on[0],
                                      _late46 if (_late_ok46[0] or not LATE_BYPASS_FIX) else 1.0)
                        _n46 = min(take_n, staged_take(tau, take_n,
                                                       _fsz * _mult46,
                                                       _held46)[0])
                        if LATE_BYPASS_FIX and not _late_ok46[0] and _late46 > 1.0:
                            _n46o = min(take_n, staged_take(
                                tau, take_n,
                                _fsz * max(band_mult(price), _doubt_on[0], _late46),
                                _held46)[0])
                            if (abs(float(_n46o) - float(_n46)) > 1e-9
                                    and (close_s, tk, "stage46") not in late_bypass_said):
                                late_bypass_said.add((close_s, tk, "stage46"))
                                rec("late_bypass_refused", ticker=tk, close_s=close_s, side=want,
                                    path="stage46", tau=tau, price=round(float(price), 4),
                                    n_before=round(float(_n46o), 2), n_after=round(float(_n46), 2),
                                    mult=float(_late46), leg=_leg46, live=bool(live))
                        return _n46
                    return take_n
''')

# 12. open_cap_relaxed at the send site: an entry that proceeds with >= 3 x SIZE contracts open
R.replace('''                if ATTEMPTS_ON_SEND:
                    attempts[close_s] = attempts.get(close_s, 0) + 1
                    attempts_tk[(close_s, tk)] = attempts_tk.get((close_s, tk), 0) + 1

                if not live:
                    take_n = _widen45(take_n)  # paper
''', '''                if ATTEMPTS_ON_SEND:
                    attempts[close_s] = attempts.get(close_s, 0) + 1
                    attempts_tk[(close_s, tk)] = attempts_tk.get((close_s, tk), 0) + 1

                # v-opencap5 (2026-11-04): --max-positions 3 paused every entry
                # while 3 x SIZE contracts were open, and a 1.5x boosted
                # position plus its cover already reaches 3.0x SIZE (ETH
                # 10-27: 387 >= 351 paused entries). The live argv now says 5;
                # an entry that goes out past the old line is written down so
                # the tracker can price what the old cap would have refused.
                # Records only; the cap itself is risk_abort's, as before.
                if float(getattr(a, "max_positions", 3) or 3) > 3.0:
                    try:
                        _oc_n = open_contracts(pintake.LEDGER)
                        if float(SIZE) > 0 and _oc_n >= 3.0 * float(SIZE) - 1e-9:
                            rec("open_cap_relaxed", ticker=tk, close_s=close_s, side=want,
                                open_positions=round(_oc_n / float(SIZE), 2),
                                open_contracts=round(_oc_n, 2), size=float(SIZE),
                                old_cap=3, new_cap=int(a.max_positions),
                                leg=_leg46, live=bool(live))
                    except Exception:                    # noqa: BLE001
                        pass

                if not live:
                    take_n = _widen45(take_n)  # paper
''')

# 13. the wrong comments
R.replace('''                # v-fullcap: a market already holding X full bets on this side
                # is refused HERE, after every other gate and before the signal
                # (burns no attempt). The multiple is the LARGEST the send site
                # can use, so this never refuses an order the trim would allow.
''', '''                # v-fullcap: a market already holding X full bets on this side
                # is refused HERE, after every other gate and before the signal.
                # (CORRECTED 2026-11-04: this DOES burn an attempt with
                # --attempts-on-send off, which is how live runs -- both entry
                # attempt counters are spent at the signal site ABOVE this
                # gate, "if not ATTEMPTS_ON_SEND:"; 25-52 of 326 market_attempts
                # lockouts followed a full_cap refusal. Only --attempts-on-send
                # moves the counters to the send site, below.) The multiple is
                # the LARGEST the send site can use, so this never refuses an
                # order the trim would allow.
''')
R.replace('''                    # 1.5 x SIZE before any add -- so the add is ZERO. Refuse
                    # it here, before the signal point (burns no attempt).
''', '''                    # 1.5 x SIZE before any add -- so the add is ZERO. Refuse
                    # it here, before the signal point. (CORRECTED 2026-11-04:
                    # with --attempts-on-send off, as live runs, the attempt
                    # counters were already spent above this line.)
''')
R.replace('''# THE RULE. Weight each price level by how much of the touch's edge survives
# there. Full size at the best price, proportionally less as the edge decays,
# nothing once it is gone. On the BNB book that asks for ~47 instead of 114.
''', '''# THE RULE. Weight each price level by how much of the touch's edge survives
# there. Full size at the best price, proportionally less as the edge decays,
# nothing once it is gone. (CORRECTED 2026-11-04: "~47 instead of 114" was the
# self-test's TWO-level simplification of that book -- 23 at 91.5c and the
# rest at 98c, at size 110. On the logged 37-level BNB book the shipped taper
# asks the full 114 = SIZE, and 93% of 1,366 live taper records cut nothing.)
''')
R.replace('''        ck(_flat_bnb > 11000 and _tap < 50.0,
           "A67: the real BNB book offered 11,937 contracts under the 98c "
           "limit and A35 sized the order to all of it; the taper asks for "
           "%.0f, because only 23 of them carried the 7.8c edge the trade "
           "was justified by" % _tap)
''', '''        ck(_flat_bnb > 11000 and _tap < 50.0,
           "A67: a TWO-LEVEL simplification of the real BNB book (23 at "
           "91.5c, the rest at 98c; the logged book had 37 levels and the "
           "shipped taper asked the full SIZE there) offers 11,937 contracts "
           "under the 98c limit and A35 sized the order to all of it; the "
           "taper asks for %.0f of 110, because only 23 of them carried the "
           "7.8c edge the trade was justified by" % _tap)
''')

# 14. flags
R.after('''                         "left (default %d: inside 10 s the extra lost money)."
                         % _DEFAULT_HEDGE_ODDS_MIN_TAU)
''', '''    ap.add_argument("--hedge-tick", default=None, choices=("legacy", "round"),
                    help="v-hedgetick: 'round' snaps the hedge limit (ask + "
                         "--hedge-slip) DOWN to the market's price grid (a "
                         "15M series: 0.1c steps under 10c and from 90c up, 1c "
                         "between; KXBTCD and any other series: 1c), never "
                         "under the ask; 'legacy' (default) sends ask + slip "
                         "as before, which is off the grid for a sub-10c "
                         "deci-cent ask and is rejected.")
    ap.add_argument("--jump-hedge-min-ask", type=float, default=None,
                    metavar="X",
                    help="v-cheapjump: a hedge fired by the --hedge-jump "
                         "trigger (belief still over --hedge-belief, no "
                         "panic) whose hedge side asks under X dollars sends "
                         "nothing that second, keeps its tries and is logged "
                         "once as hedge_cheap_skip; the belief line still "
                         "hedges. 0 = off (default); at most 0.10.")
    ap.add_argument("--boost-rail", default=None, choices=("any", "side", "off"),
                    help="v-boostrail: 'side' switches the --band-mult / "
                         "--late-mult boost off only on a losing leg on the "
                         "side the boost was for (not a losing hedge leg on a "
                         "market the boost won); 'off' never switches it off "
                         "and records every losing boosted-market leg as "
                         "boost_rail_kept; 'any' (default) is every losing "
                         "leg, as before.")
    ap.add_argument("--late-bypass-fix", default="off", choices=("off", "on"),
                    help="v-latebypass: 'on' applies the --late-mult multiple in the full-cap trim and the stage re-cap only when the late boost's own bar let this order through (logs late_bypass_refused); 'off' (default) sizes exactly as 0925r.")
''')
R.replace('''                         "after the covering hedge (never on the jump trigger). "
                         "1 = off (default); at most 3.")
''', '''                         "after the covering hedge (whatever the alarm's "
                         "label, never a stale-index alarm). "
                         "1 = off (default); at most 2.")
''')
R.replace('''    if a.hedge_odds_mult is not None:
        if not (1.0 <= float(a.hedge_odds_mult) <= 3.0):
            raise SystemExit("--hedge-odds-mult must be in [1, 3], got %r"
                             % (a.hedge_odds_mult,))
''', '''    if a.hedge_odds_mult is not None:
        # v-0925t: at most 2.0 -- the per-order count cap is 1.5 x SIZE, so a
        # 3x extra (2 x SIZE) could never be sent and a 2x one is the largest
        # the sizing evidence covers (2x worth $2-34/day at size 308)
        if not (1.0 <= float(a.hedge_odds_mult) <= 2.0):
            raise SystemExit("--hedge-odds-mult must be in [1.0, 2.0] (1 = off, 2 = the "
                             "extra equals the position), got %r"
                             % (a.hedge_odds_mult,))
''')
R.after('''        globals()["HEDGE_ODDS_MIN_TAU"] = float(a.hedge_odds_min_tau)
''', '''    if a.hedge_tick is not None:
        if a.hedge_tick not in ("legacy", "round"):
            raise SystemExit("--hedge-tick must be legacy or round, got %r"
                             % (a.hedge_tick,))
        globals()["HEDGE_TICK"] = str(a.hedge_tick)
    if a.jump_hedge_min_ask is not None:
        if not (0.0 <= float(a.jump_hedge_min_ask) <= 0.10):
            raise SystemExit("--jump-hedge-min-ask is dollars in [0, 0.10], got %r"
                             % (a.jump_hedge_min_ask,))
        globals()["JUMP_HEDGE_MIN_ASK"] = float(a.jump_hedge_min_ask)
    if a.boost_rail is not None:
        if a.boost_rail not in ("any", "side", "off"):
            raise SystemExit("--boost-rail must be any, side or off, got %r"
                             % (a.boost_rail,))
        globals()["BOOST_RAIL"] = str(a.boost_rail)
    # v-latebypass: --late-bypass-fix {off,on}, OFF by default -- 0925t sizes
    # exactly as 0925r unless the operator turns the fix on
    globals()["LATE_BYPASS_FIX"] = (a.late_bypass_fix == "on")
''')
R.after('''        hedge_odds_mult=HEDGE_ODDS_MULT, hedge_odds_min_tau=HEDGE_ODDS_MIN_TAU,
''', '''        # v-0925t: the hedge grid, the cheap-jump bar, the boost rail and the
        # late-bypass gate (off by default), so a read can tell the runs apart
        hedge_tick=HEDGE_TICK, jump_hedge_min_ask=JUMP_HEDGE_MIN_ASK,
        boost_rail=BOOST_RAIL,
        late_bypass_fix=("on" if LATE_BYPASS_FIX else "off"),
''')

# 15. existing self-tests whose asserted facts this build changes (each amended, not deleted)
# (a) v-oddsmult: the jump label with belief under the line now carries the extra
R.replace('''    ck(odds_extra(297.0, "belief", 0.34, 18, mult=2.0, min_tau=11, threshold=0.40) == 297.0
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
''', '''    ck(odds_extra(297.0, "belief", 0.34, 18, mult=2.0, min_tau=11, threshold=0.40) == 297.0
       and odds_extra(297.0, "belief", 0.34, 18, mult=1.25, min_tau=11, threshold=0.40) == 74.25
       and odds_extra(297.0, "belief", 0.34, 11, mult=2.0, min_tau=11, threshold=0.40) == 297.0
       and odds_extra(101.23, "belief", 0.001, 40, mult=1.5, min_tau=11, threshold=0.40) == 50.62
       # v-0925t: the JUMP label with belief under the line carries it too
       and odds_extra(297.0, "jump", 0.34, 38, mult=2.0, min_tau=11, threshold=0.40) == 297.0
       and odds_extra(297.0, "jump", 0.399, 11, mult=1.25, min_tau=11, threshold=0.40) == 74.25,
       "v-oddsmult: with belief under the line and the floor met the extra is "
       "(M - 1) x the position, the floor itself included -- on the belief "
       "label AND (v-0925t) on the jump label")
    ck(odds_extra(297.0, "belief", 0.34, 10, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, "jump", 0.64, 38, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, "jump", 0.40, 38, mult=2.0, min_tau=11, threshold=0.40) == 0.0
       and odds_extra(297.0, "market_index_stale", 0.34, 38, mult=2.0, min_tau=11,
                      threshold=0.40) == 0.0
''')
R.replace('''       "v-oddsmult NULL: nothing inside the floor, on the jump trigger whatever "
       "the belief, on a stale-index alarm, at or over the line, at 1x, on an "
       "empty position or garbage; ships OFF with an 11 s floor")
''', '''       "v-oddsmult NULL: nothing inside the floor, on a jump alarm with belief "
       "still at or over the line, on a stale-index alarm (its belief is the "
       "market's, kept out of NEW exposure), at or over the line, at 1x, on an "
       "empty position or garbage; ships OFF with an 11 s floor")
''')
# (b) v-fullcap / v-coinfrac: full_bet_room is now called three times in trade_loop (the gate, the trim, the
# trim's shadow), each reading the coin's / series' size
R.replace('''       and _cf_src.count("size=_ssz if _ssz is not None else _csz)") == 2
''', '''       and _cf_src.count("size=_ssz if _ssz is not None else _csz)") == 3
''')
R.replace('''       "trim); the full-bet room reads it (2 calls); the early re-cap reads "
''', '''       "trim); the full-bet room reads it (3 calls: the gate, the trim and "
       "v-latebypass's shadow of the old trim line); the early re-cap reads "
''')
R.replace('''    ck(len(_fc_calls) == 2 and all(i > _fc_ssz for i in _fc_calls)
       and _fcsrc.rindex("hedged_side[_htk] = _opp") < _fc_ssz
       and _fcsrc.index('_gate("full_cap"') < _fcsrc.index('rec("signal", live=live, **sig)'),
       "v-fullcap by source: full_bet_room is called exactly twice, both on "
       "the ENTRY scan (after the series-size line, which follows the whole "
       "hedge pass), and the full_cap refusal sits before the signal point")
''', '''    ck(len(_fc_calls) == 3 and all(i > _fc_ssz for i in _fc_calls)
       and _fcsrc.rindex("hedged_side[_htk] = _opp") < _fc_ssz
       and _fcsrc.index('_gate("full_cap"') < _fcsrc.index('rec("signal", live=live, **sig)'),
       "v-fullcap by source: full_bet_room is called exactly three times (the "
       "gate, the trim, and v-latebypass's shadow of the old trim line), all "
       "on the ENTRY scan (after the series-size line, which follows the whole "
       "hedge pass), and the full_cap refusal sits before the signal point")
''')

# 16. the new self-tests, after the v-ladderboost block (its _cf_* fixtures, and the _k1_ / _jc_ / _ox_ ones, are all
# in scope)
R.before('''    # ---- v-bankfix-nodd (2026-10-06): --no-drawdown-halt ------------------
''', '''    # ---- v-0925t (2026-11-04): v-hedgetick, v-cheapjump, v-boostrail, -----
    # ---- v-latebypass, v-extracap, v-opencap5, the extra on belief --------
    # v-hedgetick, pure. The grid, then the limit in both modes, every call
    # naming its slip and its mode (the process may be running either).
    ck(deci_tick_floor(0.115) == 0.11 and deci_tick_floor(0.183) == 0.18
       and deci_tick_floor(0.101) == 0.10 and deci_tick_floor(0.0999) == 0.099
       and deci_tick_floor(0.999) == 0.999 and deci_tick_floor(0.90) == 0.90
       and deci_tick_floor(0.8999) == 0.89 and deci_tick_floor(0.10) == 0.10
       and deci_tick_floor(0.015 + 0.10) == 0.11
       and deci_tick_floor(0.083 + 0.10) == 0.18
       and deci_tick_floor(None) is None and deci_tick_floor("x") is None
       and deci_tick_floor(float("nan")) is None,
       "v-hedgetick: deci_tick_floor snaps DOWN to the tapered_deci_cent grid "
       "(0.1c under 10c and from 90c, 1c between), through float noise; None "
       "on garbage")
    ck(tick_floor(0.115, GRID_LINEAR) == 0.11 and tick_floor(0.999, GRID_LINEAR) == 0.99
       and tick_floor(0.105, GRID_LINEAR) == 0.10 and tick_floor(0.0999, GRID_LINEAR) == 0.09
       and tick_floor(0.901, GRID_LINEAR) == 0.90 and tick_floor(0.10, GRID_LINEAR) == 0.10
       and tick_floor(0.015 + 0.10, GRID_LINEAR) == 0.11
       and tick_floor(0.001, GRID_LINEAR) == 0.0
       and tick_floor(None, GRID_LINEAR) is None and tick_floor("x", GRID_LINEAR) is None
       and tick_floor(0.115) == deci_tick_floor(0.115) and tick_floor(0.999) == 0.999,
       "v-hedgetick: tick_floor on the LINEAR grid (KXBTCD) snaps to whole "
       "cents everywhere, 99.9c included; with no grid named it is the "
       "tapered one")
    ck(price_grid_for("KXBTC15M-26NOV040245-45") == GRID_TAPERED
       and price_grid_for("KXZEC15M-26NOV040245-45") == GRID_TAPERED
       and price_grid_for("KXHYPE15M-X") == GRID_TAPERED
       and price_grid_for("KXBTCD-26NOV0412-T77999.99") == GRID_LINEAR
       and price_grid_for("KXBTCD") == GRID_LINEAR
       and price_grid_for("KXINXU-26NOV04-T6000") == GRID_LINEAR
       and price_grid_for(None) == GRID_TAPERED and price_grid_for("") == GRID_TAPERED
       and price_grid_for(7) == GRID_LINEAR,
       "v-hedgetick: the grid comes from the SERIES in the ticker (pin keeps "
       "no market object): a 15M series is tapered, KXBTCD and any other "
       "series linear, None/empty the 15M default")
    _gr_tap = [{"start": 0.0, "end": 0.10, "step": 0.001},
               {"start": 0.10, "end": 0.90, "step": 0.01},
               {"start": 0.90, "end": 1.0, "step": 0.001}]
    _gr_lin = [{"start": 0.0, "end": 1.0, "step": 0.01}]
    ck(grid_from_ranges(_gr_tap) == GRID_TAPERED and grid_from_ranges(_gr_lin) == GRID_LINEAR
       and grid_from_ranges(list(reversed(_gr_tap))) == GRID_TAPERED
       and grid_from_ranges([{"start": 0.0, "end": 1.0, "step": 0.005}]) is None
       and grid_from_ranges(None) is None and grid_from_ranges([]) is None
       and grid_from_ranges("x") is None
       and all(tick_floor(_m / 1000.0, grid_from_ranges(_gr_tap)) == deci_tick_floor(_m / 1000.0)
               and tick_floor(_m / 1000.0, grid_from_ranges(_gr_lin)) == tick_floor(_m / 1000.0, GRID_LINEAR)
               for _m in range(1, 1000)),
       "v-hedgetick: Kalshi's price_ranges shapes classify to the same two "
       "grids (for the day pin keeps the market object), and the floor agrees "
       "at every mil price with the named grid")
    _ht_want = ((0.015, 0.11), (0.083, 0.18), (0.093, 0.19), (0.057, 0.15),
                (0.62, 0.72), (0.85, 0.95), (0.905, 0.999), (0.001, 0.10))
    _ht_got = [(_a, hedge_limit(_a, 0.10, "round")) for _a, _w in _ht_want]
    _ht_got15 = [(_a, hedge_limit(_a, 0.10, "round", ticker="KXBTC15M-X")) for _a, _w in _ht_want]
    ck(all(_g == _w for (_a, _g), (_a2, _w) in zip(_ht_got, _ht_want))
       and _ht_got15 == _ht_got and HEDGE_MAX_ASK == 1.0,
       "v-hedgetick ROUND at slip 0.10 (no ticker and a 15M ticker alike): %s" % (_ht_got,))
    _ht_wantL = ((0.015, 0.11), (0.085, 0.18), (0.09, 0.19), (0.62, 0.72),
                 (0.85, 0.95), (0.89, 0.99), (0.905, 0.99), (0.95, 0.99), (0.01, 0.11))
    _ht_gotL = [(_a, hedge_limit(_a, 0.10, "round", ticker="KXBTCD-26NOV0412-T77999.99"))
                for _a, _w in _ht_wantL]
    ck(all(_g == _w for (_a, _g), (_a2, _w) in zip(_ht_gotL, _ht_wantL))
       and hedge_limit(0.905, 0.10, "legacy", ticker="KXBTCD-X") == 0.999
       and hedge_limit(0.905, 0.10, "round", ticker="KXBTC15M-X") == 0.999,
       "v-hedgetick ROUND on KXBTCD (linear grid) at slip 0.10: the 99.9c wall "
       "becomes 99c, everything else whole cents; legacy still sends 99.9c "
       "there and a 15M market keeps 99.9c (%s)" % (_ht_gotL,))
    ck(_DEFAULT_HEDGE_TICK == "legacy"
       and hedge_limit(0.015, 0.10, "legacy") == min(0.015 + 0.10, HEDGE_MAX_ASK - 0.001)
       and abs(hedge_limit(0.015, 0.10, "legacy") - 0.115) < 1e-12
       and hedge_limit(0.015, 0.10, "bogus") == hedge_limit(0.015, 0.10, "legacy")
       and hedge_limit(0.015, 0.10) == hedge_limit(0.015, 0.10, HEDGE_TICK)
       and hedge_limit(None, 0.10, "round") is None
       and hedge_limit(0.0, 0.10, "round") is None
       and hedge_limit(0.015, "junk", "round") == 0.015,
       "v-hedgetick LEGACY ships: 1.5c + 10c is the 11.5c it always was; an "
       "unknown mode is legacy; no mode given reads HEDGE_TICK; an unusable "
       "ask is still None and a garbage slip still no slip")
    _ht_cap = HEDGE_MAX_ASK - 0.001
    _ht_bad = []
    for _htm in range(1, 999):
        _hta = _htm / 1000.0
        if 100 <= _htm < 900 and _htm % 10:
            continue                       # not a grid ask: Kalshi never shows one
        for _hts in (0.0, 0.003, 0.01, 0.03, 0.05, 0.10):
            _htl = hedge_limit(_hta, _hts, "legacy")
            _htr = hedge_limit(_hta, _hts, "round", ticker="KXVT15M-X")
            _hty = round(1.0 - _htr, 4)
            _htnx = _htr + (0.001 if (_htr < 0.10 - 1e-9 or _htr >= 0.90 - 1e-9) else 0.01)
            if not (_htl == min(_hta + _hts, _ht_cap)
                    and deci_tick_floor(_htr) == _htr
                    and deci_tick_floor(_hty) == _hty
                    and _hta - 1e-12 <= _htr <= _htl + 1e-9
                    and (_htnx > _htl + 1e-9 or _htr >= _ht_cap - 1e-9)
                    and (deci_tick_floor(_htl) != round(_htl, 6)
                         or abs(_htr - _htl) < 1e-9)):
                _ht_bad.append((_hta, _hts, _htl, _htr))
    ck(not _ht_bad,
       "v-hedgetick SWEEP over every tapered grid ask 0.1c..99.8c x six slips: "
       "legacy is min(ask + slip, $1 wall) exactly; round is ON the grid in its "
       "own terms AND in YES terms (1 - limit, how a NO buy goes out), never "
       "under the ask, never over legacy, the HIGHEST grid price at or under "
       "it, and equal to legacy whenever legacy is already on the grid (bad: %s)"
       % (_ht_bad[:5],))
    _ht_badL = []
    for _htc in range(1, 100):
        _hta = _htc / 100.0
        for _hts in (0.0, 0.003, 0.01, 0.03, 0.05, 0.10):
            _htl = hedge_limit(_hta, _hts, "legacy")
            _htr = hedge_limit(_hta, _hts, "round", ticker="KXBTCD-26NOV0412-T77999.99")
            _hty = round(1.0 - _htr, 4)
            if not (tick_floor(_htr, GRID_LINEAR) == _htr
                    and tick_floor(_hty, GRID_LINEAR) == _hty
                    and _hta - 1e-12 <= _htr <= _htl + 1e-9
                    and _htr <= _ht_cap + 1e-12
                    and _htr + 0.01 > _htl + 1e-9
                    and (tick_floor(_htl, GRID_LINEAR) != round(_htl, 6)
                         or abs(_htr - _htl) < 1e-9)):
                _ht_badL.append((_hta, _hts, _htl, _htr))
    ck(not _ht_badL,
       "v-hedgetick SWEEP over every LINEAR grid ask 1c..99c x six slips "
       "(KXBTCD): round is a whole cent in its own terms AND in YES terms, "
       "never under the ask, never over legacy or the $1 wall, the highest "
       "whole cent at or under legacy, and equal to legacy whenever legacy is "
       "already a whole cent (bad: %s)" % (_ht_badL[:5],))
    ck(hedge_ladder_log([(0.05, 10), (0.06, 20)]) == [[0.05, 10.0], [0.06, 20.0]]
       and len(hedge_ladder_log([(0.01 * i, i) for i in range(1, 12)])) == 8
       and hedge_ladder_log([]) == [] and hedge_ladder_log(None) == []
       and hedge_ladder_log([("x", 1), (0.05, 10)]) == [[0.05, 10.0]],
       "v-0925t: the ladder on the hedge records is [[price, size], ...] "
       "capped at 8 levels, garbage rungs skipped")
    # v-cheapjump, pure. True only on the jump trigger, outside a panic, over
    # the belief line, with the hedge side under the bar.
    ck(cheap_jump_skip("jump", False, 0.85, 0.045, min_ask=0.05, threshold=0.40) is True
       and cheap_jump_skip("jump", False, 0.64, 0.015, min_ask=0.05, threshold=0.40) is True,
       "v-cheapjump: a 7 sd jump at belief 0.85 with the hedge side at 4.5c "
       "under a 5c bar is skipped")
    ck(not cheap_jump_skip("jump", False, 0.85, 0.045, min_ask=0.0, threshold=0.40)
       and not cheap_jump_skip("belief", False, 0.30, 0.045, min_ask=0.05, threshold=0.40)
       and not cheap_jump_skip("market_index_stale", False, 0.85, 0.045, min_ask=0.05,
                               threshold=0.40)
       and not cheap_jump_skip("jump", True, 0.85, 0.045, min_ask=0.05, threshold=0.40)
       and not cheap_jump_skip("jump", False, 0.30, 0.045, min_ask=0.05, threshold=0.40)
       and not cheap_jump_skip("jump", False, 0.85, 0.05, min_ask=0.05, threshold=0.40)
       and not cheap_jump_skip("jump", False, 0.85, 0.06, min_ask=0.05, threshold=0.40)
       and not cheap_jump_skip("jump", False, 0.85, 0.0, min_ask=0.05, threshold=0.40)
       and not cheap_jump_skip("jump", False, 0.85, None, min_ask=0.05, threshold=0.40)
       and not cheap_jump_skip("jump", False, None, 0.045, min_ask=0.05, threshold=0.40)
       and not cheap_jump_skip("jump", False, float("nan"), 0.045, min_ask=0.05,
                               threshold=0.40)
       and not cheap_jump_skip("jump", False, 0.85, 0.045, min_ask="x", threshold=0.40)
       and not cheap_jump_skip(None, False, 0.85, 0.045, min_ask=0.05, threshold=0.40)
       and _DEFAULT_JUMP_HEDGE_MIN_ASK == 0.0,
       "v-cheapjump NULL: off at 0; never on the belief or stale-index "
       "trigger; never in a panic; never with belief under the line even when "
       "the label says jump; not at or over the bar; garbage hedges as today; "
       "ships OFF")
    # v-boostrail, pure: any / side / off
    ck(all(boost_rail_trips("any", _bs, _ls)
           for _bs in ({"yes"}, "yes", {"no"}, None, set(), 7)
           for _ls in ("yes", "no", None))
       and boost_rail_trips("side", {"yes"}, "yes") is True
       and boost_rail_trips("side", "yes", "yes") is True
       and boost_rail_trips("side", {"yes"}, "no") is False
       and boost_rail_trips("side", "no", "yes") is False
       and boost_rail_trips("side", {"yes", "no"}, "no") is True
       and boost_rail_trips("side", None, "no") is True
       and boost_rail_trips("side", set(), "no") is True
       and boost_rail_trips("side", 7, "no") is True
       and boost_rail_trips("bogus", {"yes"}, "no") is True
       and all(boost_rail_trips("off", _bs, _ls) is False
               for _bs in ({"yes"}, "yes", {"no"}, None, set(), 7)
               for _ls in ("yes", "no", None))
       and _DEFAULT_BOOST_RAIL == "any",
       "v-boostrail: 'any' trips on every losing leg (today); 'side' only on "
       "the boosted side (both sides boosted: either); 'off' never, whatever "
       "the leg; no side recorded, an unknown mode or garbage falls back to "
       "tripping; ships 'any'")
    # v-extracap, pure: the room the two dollar rails leave for the extra
    _xc_led = {"committed": 5.20, "realised": 0.0}
    ck(extra_stake_cap(5.0, 0.06, "no", _xc_led, 1e6, -1e9) == (5.0, None)
       and extra_stake_cap(5.0, 0.06, "no", _xc_led, 5.50, -1e9) == (5.0, None)
       and extra_stake_cap(5.0, 0.06, "no", _xc_led, 5.35, -1e9) == (2.5, "max_run_stake")
       and extra_stake_cap(5.0, 0.06, "no", _xc_led, 5.20, -1e9) == (0.0, "max_run_stake")
       and extra_stake_cap(5.0, 0.06, "no", _xc_led, 5.00, -1e9) == (0.0, "max_run_stake")
       and extra_stake_cap(5.0, 0.06, "no", dict(_xc_led, realised=-5.0), 1e6, -1.0)
       == (0.0, "loss_abort")
       and extra_stake_cap(5.0, 0.06, "no", dict(_xc_led, realised=-1.0), 1e6, -1.0)
       == (0.0, "loss_abort")
       and extra_stake_cap(5.0, 0.06, "no", dict(_xc_led, realised=-0.99), 1e6, -1.0) == (5.0, None)
       and extra_stake_cap(74.25, 0.14, "yes", {"committed": 300.0, "realised": 0.0}, 305.0, -1e9)
       == (35.71, "max_run_stake")
       and extra_stake_cap(0.0, 0.06, "no", _xc_led, 1e6, -1e9) == (0.0, None)
       and extra_stake_cap(5.0, "x", "no", _xc_led, 1e6, -1e9) == (5.0, None)
       and extra_stake_cap(5.0, 0.06, "no", None, 1e6, -1e9) == (5.0, None),
       "v-extracap PURE: room -> the whole extra; the stake cap trims to the "
       "2-dp count that still fits (0.15 of room at 6c -> 2.5; $5 at 14c -> "
       "35.71) or refuses; the loss abort refuses at or under the line; "
       "garbage leaves the extra to pintake's own rails")
    _xc_bad = []
    for _xcp in (0.06, 0.14, 0.235, 0.5, 0.77, 0.80):
        for _xcroom in (0.0, 0.01, 0.15, 0.333, 1.0, 4.4444, 12.5):
            _xca, _xcw = extra_stake_cap(100.0, _xcp, "no", {"committed": 10.0, "realised": 0.0},
                                         10.0 + _xcroom, -1e9)
            _xcbody = pintake.build_take("KXT15M-T", "no", _xcp, max(_xca, 0.01), 2, "xc")
            _xcpe = 1.0 - round(1.0 - _xcp, 4)
            if _xca > 0 and (10.0 + pintake.stake(_xcbody) > 10.0 + _xcroom + 1e-9
                             or round(_xca, 2) != _xca
                             or (_xcw == "max_run_stake"
                                 and 10.0 + (_xca + 0.01) * _xcpe <= 10.0 + _xcroom + 1e-9)
                             or (_xcw is None and _xca != 100.0)):
                _xc_bad.append((_xcp, _xcroom, _xca, _xcw))
            if _xca <= 0 and _xcroom >= _xcpe * 0.01 + 1e-9:
                _xc_bad.append((_xcp, _xcroom, _xca, "refused with room"))
    ck(not _xc_bad,
       "v-extracap SWEEP: for six hedge-side prices x seven rooms the trimmed "
       "count, priced the way pintake prices the wire body, fits under the "
       "cap, is at 2 dp, and when it was trimmed one more cent of count would "
       "not fit; with room the whole extra passes (bad: %s)"
       % (_xc_bad[:4],))
    # BY SOURCE: the wiring
    _vs_tl = inspect.getsource(trade_loop)
    _vs_cj = _vs_tl.index("if cheap_jump_skip(")
    _vs_cje = _vs_tl.index("continue", _vs_cj)
    ck(_vs_tl.count("cheap_jump_skip(") == 1
       and _vs_tl.count('rec("hedge_cheap_skip"') == 1
       and _vs_tl.index("hedge_tries[_hid] = _tries + 1") < _vs_cj
       and _vs_tl.index("_panic = hedge_panic(_belief)") < _vs_cj
       and _vs_tl.index("if not _panic and not hedge_price_ok(_ask):") < _vs_cj
       and _vs_tl.index("if not _panic and not hedge_normal_ok(_belief, _ask):") < _vs_cj
       and _vs_tl.index("if not hedge_ask_ok(_ask):") < _vs_cj
       and _vs_cj < _vs_tl.index("_hn_want = flip_size(_hn, _entry_tau, _htau)")
       and _vs_cj < _vs_tl.index("_hlimit = hedge_limit(_ask, ticker=_htk)")
       and _vs_cj < _vs_tl.index("hedge_attempts[_hcs] = hedge_attempts.get(_hcs, 0) + 1")
       and _vs_cj < _vs_tl.index("_hpaper = float(hedge_vwap(")
       and _vs_cj < _vs_tl.index("_hout = pintake.take(")
       and "hedge_tries[_hid] = _tries  # v-cheapjump REFUND" in _vs_tl[_vs_cj:_vs_cje]
       and "hedged.add(" not in _vs_tl[_vs_cj:_vs_cje]
       and "attempts[" not in _vs_tl[_vs_cj:_vs_cje]
       and _vs_tl.count("hedge_cheap_said.add(_hid)") == 1,
       "v-cheapjump by source: ONE skip site, after the try is counted, the "
       "panic is decided and every filter has run, before the A54 size, the "
       "limit, the attempt counters and BOTH send paths (paper vwap, live "
       "take); its block refunds the try, never marks the position hedged, "
       "counts no attempt and logs once per position")
    ck(_vs_tl.count("boost_rail_trips(BOOST_RAIL, ") == 2
       and ("(close_s, tk) in boosted\\n                        and boost_rail_trips("
            "BOOST_RAIL, band_boost_sides.get((close_s, tk)), want)") in _vs_tl
       and ("(close_s, tk) in _boosted48\\n                        and boost_rail_trips("
            "BOOST_RAIL, late_boost_sides.get((close_s, tk)), want)") in _vs_tl
       and "close_s, want, cost, nfill, tk = open_pos[_oid]" in _vs_tl
       and ("boosted.add((close_s, tk))\\n                        "
            "band_boost_sides.setdefault((close_s, tk), set()).add(want)") in _vs_tl
       and ("_boosted48.add((close_s, tk))\\n                        "
            "late_boost_sides.setdefault((close_s, tk), set()).add(want)") in _vs_tl
       and _vs_tl.count("band_boost_sides.setdefault(") == 1
       and _vs_tl.count("late_boost_sides.setdefault(") == 1
       and _vs_tl.count('rec("boost_rail_kept"') == 2,
       "v-boostrail by source: BOTH rails ask boost_rail_trips with the "
       "SETTLING leg's own side (reconcile unpacks `want` from the leg), and "
       "each boost records its side right where it marks the market boosted")
    _vs_hr = _vs_tl[_vs_tl.index('rec("hedge", ticker=_htk, side=_opp, price=_hcost2'):]
    _vs_hr = _vs_hr[:_vs_hr.index('print(f"  HEDGE {_htk} buy')]
    ck("status_code=_hsc," in _vs_hr and 'err=(str(_hout.get("error"))[:200]' in _vs_hr
       and _vs_tl.index("_hsc = _hout.get(\\"status_code\\")")
       < _vs_tl.index('rec("hedge", ticker=_htk, side=_opp, price=_hcost2')
       and _vs_tl.count("hedge_limit(") == 3
       and "_hlimit = hedge_limit(_ask, ticker=_htk)" in _vs_tl
       and '_hlim_legacy = hedge_limit(_ask, tick="legacy")' in _vs_tl
       and "_lm = hedge_limit(float(_a), ticker=tk_)" in _vs_tl
       and _vs_tl.count("tick_mode=HEDGE_TICK,") == 4
       and _vs_tl.count("ladder=_hladder") == 4
       and _vs_tl.count("fired_on_belief=bool(hedge_should_fire(_belief))") == 2
       and _vs_tl.count("trigger_label=_htrig") == 2,
       "v-hedgetick by source: the LIVE hedge record carries the exchange's "
       "status_code and error; the hedge pass (the market's grid and the legacy "
       "shadow) and the jump_capped note are the only three hedge_limit calls; "
       "all four hedge / hedge_extra records carry the grid fields and the "
       "ladder, both hedge_extra records the label and fired_on_belief")
    _vs_mn = inspect.getsource(main)
    ck(all(('globals()["%s"] = ' % _n) in _vs_mn and _n in _OFFLINE_PINNED_FLAGS
           and _n in _FLAG_GLOBALS
           for _n in ("HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX"))
       and "hedge_tick=HEDGE_TICK, jump_hedge_min_ask=JUMP_HEDGE_MIN_ASK" in _vs_mn
       and "boost_rail=BOOST_RAIL" in _vs_mn
       and 'late_bypass_fix=("on" if LATE_BYPASS_FIX else "off")' in _vs_mn
       and "if not (1.0 <= float(a.hedge_odds_mult) <= 2.0):" in _vs_mn
       and "<= 3.0" not in _vs_mn[_vs_mn.index("a.hedge_odds_mult is not None"):
                                  _vs_mn.index("a.hedge_odds_mult is not None") + 400]
       and 'choices=("any", "side", "off")' in _vs_mn,
       "v-0925t: all four flags are set by main(), pinned in every offline "
       "world, watched by the give-back guard, and named in the start record; "
       "--hedge-odds-mult is refused outside [1.0, 2.0]")
    ck(_DEFAULT_LATE_BYPASS_FIX is False and isinstance(LATE_BYPASS_FIX, bool)
       and '"--late-bypass-fix", default="off", choices=("off", "on")' in _vs_mn
       and 'globals()["LATE_BYPASS_FIX"] = (a.late_bypass_fix == "on")' in _vs_mn
       and _vs_mn.index('globals()["BOOST_RAIL"] = str(a.boost_rail)')
       < _vs_mn.index('globals()["LATE_BYPASS_FIX"] = (a.late_bypass_fix == "on")')
       < _vs_mn.index('late_bypass_fix=("on" if LATE_BYPASS_FIX else "off")'),
       "v-latebypass FLAG: --late-bypass-fix is {off,on} with default off "
       "(argparse refuses any other value), ships OFF (_DEFAULT False, so every "
       "offline world runs the 0925r sizing unless it asks), is set by main() "
       "right after --boost-rail, and the start record carries late_bypass_fix "
       "on/off (this process: %s)" % ("on" if LATE_BYPASS_FIX else "off"))
    _vs_ex = _vs_tl[_vs_tl.index("if _hx_n > 0 and _hfilled > 0:"):]
    _vs_ex = _vs_ex[:_vs_ex.index('rec("hedge_extra", ticker=_htk, side=_opp, price=_hxc')]
    _vs_hoi = _vs_tl.index("_hout = pintake.take(")
    _vs_ho = _vs_tl[_vs_hoi:_vs_tl.index("hedge=True)", _vs_hoi) + len("hedge=True)")]
    ck(_vs_ex.count("extra_stake_cap(") == 1 and _vs_ex.count('rec("extra_stake_capped"') == 1
       and "hedge=True, extra=True)" in _vs_ex
       and _vs_ex.index("extra_stake_cap(") < _vs_ex.index('rec("extra_stake_capped"')
       < _vs_ex.index("_hxout = pintake.take(")
       and _vs_tl.count("hedge=True, extra=True)") == 1
       and _vs_tl.count("extra=True)") == 1
       and _vs_tl.count("pintake.take(") == 4      # entry, cover, extra, the planted hedge
       and "extra" not in _vs_ho and _vs_ho.count("pintake.take(") == 1
       and "_htk, _opp, float(_hlimit), _hn_take," in _vs_ho
       and "float(_hcs), exchange_index=2," in _vs_ho,
       "v-extracap by source: the live extra is pre-trimmed by extra_stake_cap, "
       "the trim is on the record before the send, and the extra alone goes "
       "out with extra=True (one of the four take calls); the covering hedge's "
       "take call is byte for byte what it was")
    ck(_vs_tl.count("_late_ok46 = [True]") == 1
       and _vs_tl.count("_late_ok46[0] = False") == 1
       and _vs_tl.index("if not late_boost_ok(_ours48, _jmp48):")
       < _vs_tl.index("_late_ok46[0] = False") < _vs_tl.index('rec("late_refused"')
       and _vs_tl.count('rec("late_bypass_refused"') == 2
       and 'path="fullcap"' in _vs_tl and 'path="stage46"' in _vs_tl
       and "_late_fc if (_late_ok46[0] or not LATE_BYPASS_FIX) else 1.0" in _vs_tl
       and "_late46 if (_late_ok46[0] or not LATE_BYPASS_FIX) else 1.0" in _vs_tl
       and "if LATE_BYPASS_FIX and not _late_ok46[0] and _late_fc > 1.0:" in _vs_tl
       and "if LATE_BYPASS_FIX and not _late_ok46[0] and _late46 > 1.0:" in _vs_tl
       and _vs_tl.count("LATE_BYPASS_FIX") == 4
       and "_late_fc if _late_ok46[0] else 1.0" not in _vs_tl
       and "_late46 if _late_ok46[0] else 1.0" not in _vs_tl
       and _vs_tl.count("LATE_MULT if tau <= LATE_TAU else 1.0") == 3
       and _vs_tl.index("_late_ok46 = [True]") < _vs_tl.index("def _doubt(take_n):")
       < _vs_tl.index("def _fullcap(take_n):") < _vs_tl.index("def _stage46(take_n):"),
       "v-latebypass by source: one per-order flag, cleared exactly where "
       "late_boost_ok refuses, read by _fullcap and _stage46 ONLY under "
       "--late-bypass-fix on -- the gate appears in both sizing sites and both "
       "record conditions (4 reads), and with it off each site is the 0925r "
       "expression max(band, doubt, LATE_MULT if tau <= LATE_TAU else 1.0) "
       "(the full_cap GATE keeps the largest multiple, so it still never "
       "refuses an order the trim would allow); two late_bypass_refused sites, "
       "one per path")
    ck(_vs_tl.count('rec("open_cap_relaxed"') == 1
       and _vs_tl.index('rec("signal", live=live, **sig)') < _vs_tl.index('rec("open_cap_relaxed"')
       < _vs_tl.index("take_n = _widen45(take_n)  # paper")
       and "_oc_n = open_contracts(pintake.LEDGER)" in _vs_tl
       and "3.0 * float(SIZE) - 1e-9" in _vs_tl
       and "_open_cap = float(a.max_positions) * float(SIZE)" in inspect.getsource(risk_abort),
       "v-opencap5 by source: one open_cap_relaxed record at the send site "
       "(after the signal, before either send path), measured as risk_abort "
       "measures the cap -- contracts against 3 x SIZE; the cap itself is "
       "still a.max_positions x SIZE")
    # DRIVEN (iii), the LIVE wire. A fake Kalshi that REJECTS an off-grid
    # price (400 invalid_parameters, as the 202 did) and fills an on-grid one
    # at its limit. YES bought at 96c; at t 4 the belief collapses and the NO
    # ask is the deci-cent 1.5c (YES bid 98.5c, from t 2). The REAL pintake.take builds
    # the body, so the price checked is the one on the wire, in YES terms.
    def _vt_wire(body, n):
        try:
            _vm = int(round(float(body.get("price")) * 1000.0))
        except (TypeError, ValueError):
            _vm = -1
        if not (1 <= _vm <= 999) or (100 <= _vm < 900 and _vm % 10):
            return 400, ('{"error": {"code": "invalid_parameters", "message": '
                         '"price is not on the tapered_deci_cent grid"}}')
        return _fill_all(body, n)

    def _vt_m(n):
        return {"tk": "KXVT%d15M-VT" % n, "series": "KXVT%d15M" % n,
                "iid": "VT%d" % n, "strike": 100.0,
                "fair": (lambda t: 0.10 if t >= 4.0 else 0.999),
                "book": (lambda t: _ob(0.985, 0.01) if t >= 2.0 else _ob(0.94, 0.04))}
    _vtl = _offline_trade_loop([_vt_m(1)], live=True, reply=_vt_wire,
                               flags={"HEDGE_SLIP": 0.10})
    _vtr = _offline_trade_loop([_vt_m(2)], live=True, reply=_vt_wire,
                               flags={"HEDGE_SLIP": 0.10, "HEDGE_TICK": "round"})
    _vt_no = lambda r, tk: [p.get("price") for p in r["posts"]
                            if p.get("ticker") == tk and p.get("side") == "ask"]
    _vt_yes = lambda r, tk: [p.get("price") for p in r["posts"]
                             if p.get("ticker") == tk and p.get("side") == "bid"]
    _vtl_h = _kinds(_vtl, "hedge", "KXVT115M-VT")
    _vtr_h = _kinds(_vtr, "hedge", "KXVT215M-VT")
    ck(_vtl["raised"] is None and len(_vt_no(_vtl, "KXVT115M-VT")) >= 2
       and set(_vt_no(_vtl, "KXVT115M-VT")) == {"0.8850"}
       and _hedged(_vtl, "KXVT115M-VT") == 0.0 and _vtl_h
       and all(r.get("status_code") == 400 and r.get("order_id") is None
               and "invalid_parameters" in str(r.get("err"))
               and abs(float(r.get("limit_sent") or 0) - 0.115) < 1e-9
               and r.get("tick_mode") == "legacy" and r.get("tick_rounded") is False
               and r.get("limit_legacy") == r.get("limit_sent")
               and isinstance(r.get("ladder"), list) and r.get("close_s") is not None
               for r in _vtl_h),
       "v-hedgetick CONTROL, live wire, legacy: every NO hedge goes out at YES "
       "88.5c (= NO 11.5c, off the grid), is rejected 400 and re-sent each "
       "second (%d sends %s), hedges nothing -- the 202-of-202 shape -- and "
       "each hedge record now SAYS so (status_code %s, err %r) and carries "
       "tick_mode legacy / tick_rounded False / limit_legacy = limit_sent"
       % (len(_vt_no(_vtl, "KXVT115M-VT")), sorted(set(_vt_no(_vtl, "KXVT115M-VT"))),
          [r.get("status_code") for r in _vtl_h][:2],
          (str(_vtl_h[0].get("err"))[:60] if _vtl_h else None)))
    ck(_vtr["raised"] is None and _vt_no(_vtr, "KXVT215M-VT") == ["0.8900"]
       and abs(_hedged(_vtr, "KXVT215M-VT") - 5.0) < 1e-9 and len(_vtr_h) == 1
       and _vtr_h[0].get("limit_sent") == 0.11 and _vtr_h[0].get("status_code") == 201
       and _vtr_h[0].get("err") is None and abs(float(_vtr_h[0].get("ask")) - 0.015) < 1e-9
       and _vtr_h[0].get("tick_mode") == "round" and _vtr_h[0].get("tick_rounded") is True
       and _vtr_h[0].get("limit_legacy") == 0.115
       and all(deci_tick_floor(float(_p)) == float(_p)
               for _p in _vt_yes(_vtr, "KXVT215M-VT") + _vt_yes(_vtl, "KXVT115M-VT")),
       "v-hedgetick DRIVEN, live wire, round: ONE NO hedge at YES 89c (= NO "
       "11c, on the grid) fills all 5 first time (sends %s, limit_sent %s, "
       "status_code %s, err %r; tick_rounded True, limit_legacy 0.115); the "
       "entry's own limit is on the grid either way (%s)"
       % (_vt_no(_vtr, "KXVT215M-VT"), [r.get("limit_sent") for r in _vtr_h],
          [r.get("status_code") for r in _vtr_h], [r.get("err") for r in _vtr_h],
          _vt_yes(_vtr, "KXVT215M-VT")))
    # the LINEAR grid on the wire: a KXBTCD rung (2 of SIZE 10), the NO ask
    # 91c when the belief collapses, so legacy sends the 99.9c wall (YES
    # 0.1c, not a whole cent) and round sends 99c (YES 1c). A fake Kalshi
    # that only takes whole cents, as the hourly market does.
    def _vt_wire_lin(body, n):
        try:
            _vm = int(round(float(body.get("price")) * 1000.0))
        except (TypeError, ValueError):
            _vm = -1
        if not (10 <= _vm <= 990) or _vm % 10:
            return 400, ('{"error": {"code": "invalid_parameters", "message": '
                         '"price is not on the linear_cent grid"}}')
        return _fill_all(body, n)

    def _vt_lin(n):
        return {"tk": "KXBTCD-26NOV04%02d-T99.99" % n, "series": "KXBTCD", "iid": "VL%d" % n,
                "strike": 100.0, "fair": (lambda t: 0.10 if t >= 4.0 else 0.999),
                "book": (lambda t: _ob(0.09, 0.05) if t >= 2.0 else _ob(0.94, 0.05))}
    _vll = _offline_trade_loop([_vt_lin(1)], live=True, reply=_vt_wire_lin, size=10.0,
                               flags={"SERIES_SIZE_FRAC": 0.2, "HEDGE_SLIP": 0.10})
    _vlr = _offline_trade_loop([_vt_lin(2)], live=True, reply=_vt_wire_lin, size=10.0,
                               flags={"SERIES_SIZE_FRAC": 0.2, "HEDGE_SLIP": 0.10,
                                      "HEDGE_TICK": "round"})
    _vll_h = _kinds(_vll, "hedge", _vt_lin(1)["tk"])
    _vlr_h = _kinds(_vlr, "hedge", _vt_lin(2)["tk"])
    ck(_vll["raised"] is None and _vll_h and _hedged(_vll, _vt_lin(1)["tk"]) == 0.0
       and set(_vt_no(_vll, _vt_lin(1)["tk"])) == {"0.0010"}
       and all(r.get("status_code") == 400 and abs(float(r.get("limit_sent")) - 0.999) < 1e-9
               for r in _vll_h)
       and _vlr["raised"] is None and len(_vlr_h) == 1
       and _vt_no(_vlr, _vt_lin(2)["tk"]) == ["0.0100"]
       and abs(_hedged(_vlr, _vt_lin(2)["tk"]) - 2.0) < 1e-9
       and _vlr_h[0].get("limit_sent") == 0.99 and _vlr_h[0].get("limit_legacy") == 0.999
       and _vlr_h[0].get("tick_rounded") is True and _vlr_h[0].get("status_code") == 201,
       "v-hedgetick DRIVEN on KXBTCD (linear grid), live wire: legacy sends the "
       "99.9c wall as YES 0.1c and is rejected every second (%d sends, hedged "
       "%g); round sends 99c (YES 1c) and fills the 2 held first time (sends "
       "%s, limit_sent %s, limit_legacy %s)"
       % (len(_vt_no(_vll, _vt_lin(1)["tk"])), _hedged(_vll, _vt_lin(1)["tk"]),
          _vt_no(_vlr, _vt_lin(2)["tk"]), [r.get("limit_sent") for r in _vlr_h],
          [r.get("limit_legacy") for r in _vlr_h]))
    # DRIVEN (ii), v-cheapjump. The _jc_ world with the hedge side CHEAP: YES
    # bought at 96c, NO asks 4.5c; a 7 sd jump from t 4 (it stays inside the
    # lookback); whole-position hedging, as live.
    def _cj_m(n, fair_of, book_of=(lambda t: _ob(0.955, 0.04))):
        return {"tk": "KXCJ%d15M-CJ" % n, "series": "KXCJ%d15M" % n,
                "iid": "CJ%d" % n, "strike": 100.0, "fair": fair_of,
                "book": book_of, "moves": _jc_7}
    _cj_on = dict(_jc_on, HEDGE_PROP=False, JUMP_HEDGE_MIN_ASK=0.05)
    _cja = _offline_trade_loop([_cj_m(1, _jc_f85)], flags=_cj_on)
    _cjar = _kinds(_cja, "hedge_cheap_skip")
    _cja_t = [r.get("trigger") for r in _kinds(_cja, "hedge_alarm")]
    ck(_cja["raised"] is None and _cja_t == ["jump"] and len(_cjar) == 1
       and _hedged(_cja, "KXCJ115M-CJ") == 0.0
       and not _kinds(_cja, "hedge_gave_up")
       and _cjar[0].get("side") == "no" and abs(float(_cjar[0].get("ask")) - 0.045) < 1e-9
       and _cjar[0].get("min_ask") == 0.05
       and 6.9 <= float(_cjar[0].get("jump_sd") or 0) <= 7.1
       and abs(float(_cjar[0].get("belief") or 0) - 0.85) < 1e-6
       and _cjar[0].get("tau") is not None and _cjar[0].get("live") is False
       and _cjar[0].get("close_s") is not None
       and float(_cjar[0].get("n") or 0) == 5.0,
       "v-cheapjump DRIVEN (paper): a 7 sd jump at belief 0.85 with NO at 4.5c "
       "under a 5c bar buys NOTHING, logs hedge_cheap_skip ONCE (side, ask, "
       "bar, sd, belief, tau, close_s) over 8 seconds of the same jump, and never gives "
       "up (triggers %r, records %d, hedged %g)"
       % (_cja_t, len(_cjar), _hedged(_cja, "KXCJ115M-CJ")))
    _cjb = _offline_trade_loop([_cj_m(2, _jc_f85)],
                               flags=dict(_cj_on, JUMP_HEDGE_MIN_ASK=0.0))
    _cjc = _offline_trade_loop([_cj_m(3, _jc_f85)],
                               flags=dict(_cj_on, JUMP_HEDGE_MIN_ASK=0.04))
    ck(all(w["raised"] is None and abs(_hedged(w, _t) - 5.0) < 1e-9
           and not _kinds(w, "hedge_cheap_skip")
           for w, _t in ((_cjb, "KXCJ215M-CJ"), (_cjc, "KXCJ315M-CJ"))),
       "v-cheapjump NULL DRIVEN: the flag OFF, and a 4c bar under the 4.5c "
       "ask, each hedge the 5 on the jump exactly as today (hedged %g / %g)"
       % (_hedged(_cjb, "KXCJ215M-CJ"), _hedged(_cjc, "KXCJ315M-CJ")))
    # the belief line still fires while the jump is still in the lookback:
    # in a panic (0.02), and with the panic OFF at 0.30 under the 0.40 line
    _cj_f7 = lambda t: 0.999 if t < 4.0 else (0.85 if t < 7.0 else 0.02)
    _cj_f7b = lambda t: 0.999 if t < 4.0 else (0.85 if t < 7.0 else 0.30)
    _cjd = _offline_trade_loop([_cj_m(4, _cj_f7)], flags=_cj_on)
    _cje = _offline_trade_loop([_cj_m(5, _cj_f7b)],
                               flags=dict(_cj_on, HEDGE_PANIC=None))
    _cj_first = lambda r, tk: min([float(x["t"]) for x in _kinds(r, "hedge", tk)] or [-1.0])
    ck(all(w["raised"] is None and abs(_hedged(w, _t) - 5.0) < 1e-9
           and len(_kinds(w, "hedge_cheap_skip")) == 1 and _cj_first(w, _t) >= 6.5
           for w, _t in ((_cjd, "KXCJ415M-CJ"), (_cje, "KXCJ515M-CJ"))),
       "v-cheapjump DRIVEN: skipped on the jump from t 4, then the BELIEF LINE "
       "hedges all 5 once belief crosses at index t 7 (wall t >= 6.9) with "
       "the jump still in the lookback -- in a "
       "panic (0.02) and with the panic off at 0.30 (first hedge t %g / %g)"
       % (_cj_first(_cjd, "KXCJ415M-CJ"), _cj_first(_cje, "KXCJ515M-CJ")))
    # THE REFUND: three tries only, six seconds of cheap skips, then the line.
    # Without the refund try 4 gives up at t 7 and marks the position hedged
    # for good, and the collapse at t 10 is never hedged (the CONTROL shows a
    # try-spending wait -- no NO ask at all -- doing exactly that).
    _cj_f10 = lambda t: 0.999 if t < 4.0 else (0.85 if t < 10.0 else 0.02)
    _cjf = _offline_trade_loop([_cj_m(6, _cj_f10)], run_s=16.0,
                               flags=dict(_cj_on, HEDGE_MAX_TRIES=3))
    _cjg = _offline_trade_loop(
        [_cj_m(7, _cj_f10, (lambda t: _ob(None, 0.04) if 4.0 <= t < 10.0
                            else _ob(0.955, 0.04)))],
        run_s=16.0, flags=dict(_cj_on, HEDGE_MAX_TRIES=3))
    ck(_cjf["raised"] is None and not _kinds(_cjf, "hedge_gave_up")
       and len(_kinds(_cjf, "hedge_cheap_skip")) == 1
       and abs(_hedged(_cjf, "KXCJ615M-CJ") - 5.0) < 1e-9
       and _cj_first(_cjf, "KXCJ615M-CJ") >= 9.5
       and _cjg["raised"] is None and _kinds(_cjg, "hedge_gave_up")
       and _hedged(_cjg, "KXCJ715M-CJ") == 0.0,
       "v-cheapjump REFUND DRIVEN: at HEDGE_MAX_TRIES 3, six seconds of cheap "
       "skips spend no try -- no give-up, and the collapse at t 10 hedges all "
       "5 (hedged %g at t %g); CONTROL: six seconds with no NO ask spend the "
       "three, give up, and the same collapse is never hedged (gave_up %d, "
       "hedged %g)"
       % (_hedged(_cjf, "KXCJ615M-CJ"), _cj_first(_cjf, "KXCJ615M-CJ"),
          len(_kinds(_cjg, "hedge_gave_up")), _hedged(_cjg, "KXCJ715M-CJ")))
    _cjkt, _cjkc = _k1_take(False)
    _cjl = _offline_trade_loop([_cj_m(8, _jc_f85)], live=True, take=_cjkt, flags=_cj_on)
    _cjkt0, _cjkc0 = _k1_take(False)
    _cjl0 = _offline_trade_loop([_cj_m(9, _jc_f85)], live=True, take=_cjkt0,
                                flags=dict(_cj_on, JUMP_HEDGE_MIN_ASK=0.0))
    ck(_cjl["raised"] is None
       and len([c for c in _cjkc if c[0] == "KXCJ815M-CJ" and c[1] == "yes"]) == 1
       and not [c for c in _cjkc if c[0] == "KXCJ815M-CJ" and c[1] == "no"]
       and len(_kinds(_cjl, "hedge_cheap_skip")) == 1
       and _kinds(_cjl, "hedge_cheap_skip")[0].get("live") is True
       and _cjl0["raised"] is None
       and [c[2] for c in _cjkc0 if c[0] == "KXCJ915M-CJ" and c[1] == "no"] == [5.0]
       and not _kinds(_cjl0, "hedge_cheap_skip"),
       "v-cheapjump LIVE PATH: with the bar on the entry is the only order "
       "(no NO order, one live hedge_cheap_skip); with it off the jump sends "
       "ONE NO order of 5, as today")
    # DRIVEN, the extra on BELIEF whatever the label (v-0925t). The live
    # shape under --jump-hedge-min-ask: the _cj_ world (NO asks 4.5c), a 7 sd
    # jump from t 4 at belief 0.85 is SKIPPED as cheap, then the belief
    # collapses to 0.02 at t 7 with the jump still inside the lookback, so
    # the A52 label is still "jump" when the hedge fires: the cover AND the
    # extra, the extra saying trigger_label jump / fired_on_belief True
    # (0925r: no extra, "never on the jump trigger"). Then the same on the
    # shipped proportional hedging (HEDGE_PROP on): a jump at t 3 with
    # belief 0.999 buys nothing, the collapse at t 4 under the same label
    # buys the cover and the extra. The 0.85 world (belief over the line)
    # still buys no extra; a stale-index alarm (K3: the belief is the
    # market's) still buys no extra.
    _oxjb = _offline_trade_loop([_cj_m(11, _cj_f7)],
                                flags=dict(_cj_on, **_ox_on))
    _oxjb_t = [r.get("trigger") for r in _kinds(_oxjb, "hedge_alarm")]
    _oxjb_x = _kinds(_oxjb, "hedge_extra", "KXCJ1115M-CJ")
    _oxjb_h = _kinds(_oxjb, "hedge", "KXCJ1115M-CJ")
    ck(_oxjb["raised"] is None and _oxjb_t == ["jump"]
       and len(_kinds(_oxjb, "hedge_cheap_skip")) == 1
       and abs(_hedged(_oxjb, "KXCJ1115M-CJ") - 5.0) < 1e-9 and _cj_first(_oxjb, "KXCJ1115M-CJ") >= 6.5
       and len(_oxjb_x) == 1 and abs(float(_oxjb_x[0].get("n") or 0) - 5.0) < 1e-9
       and _oxjb_x[0].get("trigger_label") == "jump" and _oxjb_x[0].get("trigger") == "jump"
       and _oxjb_x[0].get("fired_on_belief") is True
       and abs(float(_oxjb_x[0].get("belief") or 0) - 0.02) < 1e-6
       and _oxjb_x[0].get("tick_mode") == "legacy" and _oxjb_x[0].get("tick_rounded") is False
       and isinstance(_oxjb_x[0].get("ladder"), list) and _oxjb_x[0].get("close_s") is not None
       and _oxjb_x[0].get("limit_legacy") is not None
       and len(_oxjb_h) == 1 and _oxjb_h[0].get("tick_mode") == "legacy",
       "v-0925t DRIVEN (live shape): the cheap 7 sd jump is skipped at belief "
       "0.85, then the collapse to 0.02 at t 7 hedges the 5 under the SAME "
       "jump label AND buys the 5 extra, the record saying trigger_label jump "
       "/ fired_on_belief True (triggers %r, first hedge t %g, extras %d)"
       % (_oxjb_t, _cj_first(_oxjb, "KXCJ1115M-CJ"), len(_oxjb_x)))
    _jc_f10b = lambda t: 0.999 if t < 4.0 else 0.10
    _jc_7e = lambda t: [-0.0035] if t >= 3.0 else []
    _oxjp = _offline_trade_loop([_jc_m(13, _jc_f10b, _jc_7e)],
                                flags=dict(_jc_on, **_ox_on))
    _oxjp_t = [r.get("trigger") for r in _kinds(_oxjp, "hedge_alarm")]
    _oxjp_x = _kinds(_oxjp, "hedge_extra", "KXJC1315M-JC")
    ck(_oxjp["raised"] is None and _oxjp_t == ["jump"]
       and abs(_hedged(_oxjp, "KXJC1315M-JC") - 5.0) < 1e-9
       and len(_oxjp_x) == 1 and abs(float(_oxjp_x[0].get("n") or 0) - 5.0) < 1e-9
       and _oxjp_x[0].get("trigger_label") == "jump" and _oxjp_x[0].get("fired_on_belief") is True
       and abs(float(_oxjp_x[0].get("belief") or 0) - 0.10) < 1e-6,
       "v-0925t DRIVEN (proportional hedging, the shipped default): the 7 sd "
       "jump alarm at belief 0.999 buys nothing, the collapse to 0.10 a second "
       "later hedges the 5 under the jump label AND buys the 5 extra "
       "(triggers %r, extras %d)" % (_oxjp_t, len(_oxjp_x)))
    _oxj2 = _offline_trade_loop([_jc_m(12, _jc_f85, _jc_7)],
                                flags=dict(_jc_on, HEDGE_PROP=False, **_ox_on))
    _oxj2_t = [r.get("trigger") for r in _kinds(_oxj2, "hedge_alarm")]
    ck(_oxj2["raised"] is None and "jump" in _oxj2_t
       and abs(_hedged(_oxj2, "KXJC1215M-JC") - 5.0) < 1e-9
       and not _kinds(_oxj2, "hedge_extra"),
       "v-0925t NULL DRIVEN: the same jump alarm at belief 0.85 (over the "
       "line) hedges the 5 and buys NO extra (triggers %r)" % (_oxj2_t,))

    def _ox_stale(n):
        m = _k1_A(collapse_at=4)
        m["tk"], m["series"], m["iid"] = "KXOS%d15M-OS" % n, "KXOS%d15M" % n, "OS%d" % n
        m["book"] = (lambda t: _ob(0.06, 0.90) if t >= 4.0 else _ob(0.94, 0.05))
        return m
    _oxs = _offline_trade_loop([_ox_stale(1)], freeze_at=2, flags=_ox_on)
    _oxs_t = [r.get("trigger") for r in _kinds(_oxs, "hedge_alarm")]
    ck(_oxs["raised"] is None and _oxs_t == ["market_index_stale"]
       and abs(_hedged(_oxs, "KXOS115M-OS") - 5.0) < 1e-9
       and not _kinds(_oxs, "hedge_extra") and not _kinds(_oxs, "hedge_extra_skipped"),
       "v-0925t PRESERVED: a stale-index alarm (frozen index, the market's "
       "10c as the belief) still hedges all 5 and still buys NO extra "
       "(triggers %r, hedged %g)" % (_oxs_t, _hedged(_oxs, "KXOS115M-OS")))
    # DRIVEN, v-extracap. The _k1_A LIVE world through the REAL pintake.take
    # and a fake wire that fills at the limit. At the alarm (committed = the
    # entry only) the stake cap is moved to leave the cover's $0.30 plus
    # $0.15 of room: the cover (exempt, covers_held) fills in full, the extra
    # is TRIMMED to 2.5 (0.15 / 6c) and says so. Then no room at all: the
    # cover still fills, the extra is refused (allowed 0), nothing sent.
    # Then the loss abort: realised put under the line at the alarm, the
    # cover fills, the extra is refused with reason loss_abort.
    def _xc_run(room, realised=None, loss_abort=-1e9):
        def _fault(kind, kw):
            if kind == "hedge_alarm":
                if room is not None:
                    pintake.MAX_RUN_STAKE = float(pintake.LEDGER["committed"]) + 0.30 + float(room)
                if realised is not None:
                    pintake.LEDGER["realised"] = float(realised)
        _sv = (pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT)
        try:
            pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT = 1e6, float(loss_abort)
            return _offline_trade_loop([_k1_A()], live=True, reply=_fill_all,
                                       rec_fault=_fault, flags=_ox_on)
        finally:
            pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT = _sv
    _xc_posts = lambda r: [(p.get("side"), float(p.get("count"))) for p in r["posts"]]
    _xca = _xc_run(0.15)
    _xca_c = _kinds(_xca, "extra_stake_capped", _kA)
    _xca_x = _kinds(_xca, "hedge_extra", _kA)
    ck(_xca["raised"] is None and abs(_hedged(_xca, _kA) - 5.0) < 1e-9
       and _xc_posts(_xca) == [("bid", 5.0), ("ask", 5.0), ("ask", 2.5)]
       and len(_xca_c) == 1 and _xca_c[0].get("reason") == "max_run_stake"
       and _xca_c[0].get("asked") == 5.0 and _xca_c[0].get("allowed") == 2.5
       and _xca_c[0].get("trimmed") == 2.5 and _xca_c[0].get("side") == "no"
       and _xca_c[0].get("mult") == 2.0 and _xca_c[0].get("live") is True
       and _xca_c[0].get("close_s") is not None
       and len(_xca_x) == 1 and abs(float(_xca_x[0].get("n") or 0) - 2.5) < 1e-9
       and _xca_x[0].get("order_id") is not None
       and not _kinds(_xca, "hedge_extra_refused"),
       "v-extracap DRIVEN (live wire, real pintake): with $0.15 of room past "
       "the cover the cover fills all 5 (exempt as before) and the extra is "
       "TRIMMED to 2.5, filled, and extra_stake_capped says asked 5 / allowed "
       "2.5 / max_run_stake (wire %s)" % (_xc_posts(_xca),))
    _xcb = _xc_run(-0.10)
    _xcb_c = _kinds(_xcb, "extra_stake_capped", _kA)
    ck(_xcb["raised"] is None and abs(_hedged(_xcb, _kA) - 5.0) < 1e-9
       and _xc_posts(_xcb) == [("bid", 5.0), ("ask", 5.0)]
       and len(_xcb_c) == 1 and _xcb_c[0].get("allowed") == 0.0
       and _xcb_c[0].get("reason") == "max_run_stake" and _xcb_c[0].get("trimmed") == 5.0
       and not _kinds(_xcb, "hedge_extra") and not _kinds(_xcb, "hedge_extra_refused"),
       "v-extracap DRIVEN: with the cap already under the cover the COVER "
       "still fills (its exemption is untouched) and the extra is refused "
       "before the wire (allowed 0, nothing sent; wire %s)" % (_xc_posts(_xcb),))
    _xcc = _xc_run(None, realised=-5.0, loss_abort=-1.0)
    _xcc_c = _kinds(_xcc, "extra_stake_capped", _kA)
    ck(_xcc["raised"] is None and abs(_hedged(_xcc, _kA) - 5.0) < 1e-9
       and _xc_posts(_xcc) == [("bid", 5.0), ("ask", 5.0)]
       and len(_xcc_c) == 1 and _xcc_c[0].get("reason") == "loss_abort"
       and _xcc_c[0].get("allowed") == 0.0 and not _kinds(_xcc, "hedge_extra"),
       "v-extracap DRIVEN: at the loss abort the cover still fills and the "
       "extra is refused with reason loss_abort (wire %s)" % (_xc_posts(_xcc),))
    _xcd = _xc_run(None)
    ck(_xcd["raised"] is None and _xc_posts(_xcd) == [("bid", 5.0), ("ask", 5.0), ("ask", 5.0)]
       and not _kinds(_xcd, "extra_stake_capped")
       and len(_kinds(_xcd, "hedge_extra", _kA)) == 1,
       "v-extracap NULL DRIVEN: with room the extra goes out whole, no "
       "extra_stake_capped (wire %s)" % (_xc_posts(_xcd),))
    # pintake's own rail, pure: the same body that covers_held exempts as a
    # cover is refused at the stake cap and the loss abort once extra=True
    _xp_tk = "KXXP15M-XP"
    _xp_led = dict(pintake._fresh_ledger(), committed=pintake.MAX_RUN_STAKE,
                   positions={_xp_tk: {"want": "yes", "contracts": 10.0, "cost": 9.6,
                                       "order_ids": ["xp"]}})
    _xp_body = pintake.build_take(_xp_tk, "no", 0.06, 5, 2, "xp-x")
    _xp_now = 1_800_000_000.0
    _xp_close = _xp_now + 20.0
    _xp_cov = pintake.check_take(_xp_body, _xp_close, _xp_now, ledger=_xp_led, hedge=True)
    _xp_ext = pintake.check_take(_xp_body, _xp_close, _xp_now, ledger=_xp_led, hedge=True, extra=True)
    _xp_la = dict(pintake._fresh_ledger(), realised=pintake.LOSS_ABORT - 1.0,
                  positions=_xp_led["positions"])
    _xp_cov2 = pintake.check_take(_xp_body, _xp_close, _xp_now, ledger=_xp_la, hedge=True)
    _xp_ext2 = pintake.check_take(_xp_body, _xp_close, _xp_now, ledger=_xp_la, hedge=True, extra=True)
    _xp_room = dict(pintake._fresh_ledger(), positions=_xp_led["positions"])
    ck(not _xp_cov and len(_xp_ext) == 1 and "MAX_RUN_STAKE" in _xp_ext[0]
       and not _xp_cov2 and len(_xp_ext2) == 1 and "LOSS ABORT" in _xp_ext2[0]
       and not pintake.check_take(_xp_body, _xp_close, _xp_now, ledger=_xp_room, hedge=True, extra=True)
       and not pintake.check_take(_xp_body, _xp_close, _xp_now, ledger=_xp_room, hedge=True)
       and "extra=False" in inspect.getsource(pintake.take)
       and "extra=extra" in inspect.getsource(pintake.take)
       and "_cover = bool(hedge) and not extra and covers_held(body, L)" in inspect.getsource(pintake.check_take),
       "v-extracap in pintake: the order covers_held would exempt (NO 5 against "
       "10 held) passes the stake cap and the loss abort as a cover and is "
       "REFUSED at both once extra=True; with room both pass; take() carries "
       "the flag through")
    # DRIVEN, v-opencap5: ONE market reaches 3 x SIZE in the ledger (5 YES +
    # 5 NO cover + 5 NO extra at 2x); a second market decides at t 6. Under
    # --max-positions 3 (the old live value) risk_abort pauses the loop and
    # the second is never bought; under 5 it is, and open_cap_relaxed says
    # the old line was crossed.
    _oc5 = _offline_trade_loop([_k1_A(), _k1_B(1, decided_at=6)], live=True,
                               reply=_fill_all, max_positions=5, flags=_ox_on)
    _oc3 = _offline_trade_loop([_k1_A(), _k1_B(1, decided_at=6)], live=True,
                               reply=_fill_all, max_positions=3, flags=_ox_on)
    _oc5_r = _kinds(_oc5, "open_cap_relaxed")
    ck(_oc5["raised"] is None and abs(_hedged(_oc5, _kA) - 5.0) < 1e-9
       and len(_kinds(_oc5, "hedge_extra", _kA)) == 1
       and _kinds(_oc5, "order", "KXB115M-K1")
       and len(_oc5_r) == 1 and _oc5_r[0].get("ticker") == "KXB115M-K1"
       and _oc5_r[0].get("open_positions") == 3.0 and _oc5_r[0].get("open_contracts") == 15.0
       and _oc5_r[0].get("old_cap") == 3 and _oc5_r[0].get("new_cap") == 5
       and _oc5_r[0].get("leg") == "full" and _oc5_r[0].get("side") == "yes"
       and _oc5_r[0].get("live") is True and _oc5_r[0].get("close_s") is not None
       and not _kinds(_oc5, "pause"),
       "v-opencap5 DRIVEN (--max-positions 5): A holds 15 = 3 x SIZE (entry, "
       "cover, extra), B is still bought at t 6 and open_cap_relaxed records "
       "open_positions 3.0 / old_cap 3 / new_cap 5 / leg full (%s)"
       % ([(r.get("ticker"), r.get("open_positions"), r.get("open_contracts")) for r in _oc5_r],))
    ck(_oc3["raised"] is None and abs(_hedged(_oc3, _kA) - 5.0) < 1e-9
       and _kinds(_oc3, "pause") and not _kinds(_oc3, "order", "KXB115M-K1")
       and not _kinds(_oc3, "open_cap_relaxed"),
       "v-opencap5 CONTROL (--max-positions 3, the old live line): the same 15 "
       "open pauses the loop (%d pause records), B is never bought, no "
       "open_cap_relaxed" % len(_kinds(_oc3, "pause")))
    # DRIVEN (i), v-boostrail, on the v-coinfrac live world (SIZE 99, deep
    # book, bank sized to exactly 99): BTC alone, the belief collapses at +3 s
    # and is hedged; the market then settles. Band world: bought at 96c at
    # tau 20 (inside the 95.5-98.1c band, outside the late window) -> A53
    # widens to 148.5. Late world: 95c at tau 8 -> A55 widens to 148.5.
    # `snap` reads the LIVE globals at every settled record (written right
    # after the rails), i.e. whether the boost is still on after each leg.
    _br_F = dict(_CF_LIVE, COIN_SIZE_FRAC={}, BAND_MULTS=((0.955, 0.981, 1.5),))

    def _br_run(ask, tau0, res, rail):
        _snaps = []

        def _snap(kind, kw):
            if kind == "settled":
                _snaps.append((kw.get("want"), globals()["BAND_MULTS"],
                               globals()["LATE_MULT"]))
        try:
            pintake.MAX_TAKE_COUNT, pintake.HARD_MAX = 99.0 * 1.5, 99.0 * 1.5 * 1.5
            pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT = 1e6, -1e9
            _r = _offline_trade_loop(
                [_cf_mk("KXBTC15M", "B", _cf_deep(ask), fair=_cf_lose)],
                live=True, reply=_cf_reply95, run_s=70.0, tau0=tau0, size=99.0,
                bank=_CF_BANK99, result={_cfBX: res}, rec_fault=_snap,
                flags=dict(_br_F, BOOST_RAIL=rail))
        finally:
            (pintake.MAX_TAKE_COUNT, pintake.HARD_MAX,
             pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT) = _cf_rails
        return _r, _snaps
    _brA, _brAs = _br_run(0.96, 20, "yes", "any")
    _brS, _brSs = _br_run(0.96, 20, "yes", "side")
    _brN, _brNs = _br_run(0.96, 20, "no", "side")
    _brO, _brOs = _br_run(0.96, 20, "yes", "off")
    _brON, _brONs = _br_run(0.96, 20, "no", "off")
    _br_on = ((0.955, 0.981, 1.5),)
    _br_desc = lambda r, k: [(x.get("want"), x.get("pnl_c")) for x in _cf_kind(r, k, _cfBX)]
    ck(all(w["raised"] is None and _cf_kind(w, "band_boost", _cfBX)
           and not _cf_kind(w, "late_boost", _cfBX)
           and _cf_kind(w, "hedge", _cfBX) and len(_cf_kind(w, "settled", _cfBX)) >= 2
           for w in (_brA, _brS, _brN, _brO, _brON)),
       "v-boostrail worlds: the 96c order at tau 20 is band-boosted (not "
       "late), hedged on the collapse, and both legs settle (band %s)"
       % ([(x.get("was"), x.get("now")) for x in _cf_kind(_brA, "band_boost", _cfBX)],))
    ck(_cf_kind(_brA, "band_boost_off", _cfBX)
       and [s_[1] for s_ in _brAs if s_[0] == "no"] == [()]
       and not _cf_kind(_brA, "boost_rail_kept", None),
       "v-boostrail CONTROL ('any', today): the LOSING NO hedge leg on a "
       "market the boosted YES won switches the band boost off for the run "
       "(settled %s, BAND_MULTS after the NO leg %s)"
       % (_br_desc(_brA, "settled"), [s_[1] for s_ in _brAs if s_[0] == "no"]))
    _brS_k = _cf_kind(_brS, "boost_rail_kept", _cfBX)
    ck(not _cf_kind(_brS, "band_boost_off", None)
       and all(s_[1] == _br_on for s_ in _brSs)
       and len(_brS_k) == 1 and _brS_k[0].get("which") == "band"
       and _brS_k[0].get("leg_side") == "no" and _brS_k[0].get("boosted_side") == ["yes"]
       and _brS_k[0].get("rail") == "side" and _brS_k[0].get("live") is True
       and _brS_k[0].get("close_s") is not None and _brS_k[0].get("pnl_c") is not None
       and _brS_k[0].get("cost") is not None,
       "v-boostrail DRIVEN ('side'): the same losing NO hedge leg leaves "
       "--band-mult ON (BAND_MULTS at every settled record %s) and says so "
       "once (boost_rail_kept %s)"
       % ([s_[1] for s_ in _brSs], [(x.get("which"), x.get("leg_side"),
                                      x.get("boosted_side"), x.get("rail")) for x in _brS_k]))
    ck(_cf_kind(_brN, "band_boost_off", _cfBX)
       and [s_[1] for s_ in _brNs if s_[0] == "yes"] == [()]
       and not _cf_kind(_brN, "boost_rail_kept", None),
       "v-boostrail NULL DRIVEN ('side'): when the BOOSTED YES leg itself "
       "loses (the market settles NO) the band boost still goes off at once "
       "(settled %s)" % (_br_desc(_brN, "settled"),))
    _brO_k = _cf_kind(_brO, "boost_rail_kept", _cfBX)
    _brON_k = _cf_kind(_brON, "boost_rail_kept", _cfBX)
    ck(not _cf_kind(_brO, "band_boost_off", None) and all(s_[1] == _br_on for s_ in _brOs)
       and len(_brO_k) == 1 and _brO_k[0].get("rail") == "off"
       and _brO_k[0].get("leg_side") == "no" and _brO_k[0].get("boosted_side") == ["yes"]
       and not _cf_kind(_brON, "band_boost_off", None) and all(s_[1] == _br_on for s_ in _brONs)
       and len(_brON_k) == 1 and _brON_k[0].get("rail") == "off"
       and _brON_k[0].get("leg_side") == "yes" and _brON_k[0].get("boosted_side") == ["yes"]
       and float(_brON_k[0].get("pnl_c") or 0) < 0,
       "v-boostrail DRIVEN ('off'): neither a losing NO hedge leg (boost won) "
       "nor the losing BOOSTED YES leg itself switches the band boost off; "
       "each is written as boost_rail_kept with rail off (%s / %s)"
       % ([(x.get("leg_side"), x.get("rail")) for x in _brO_k],
          [(x.get("leg_side"), x.get("rail"), x.get("pnl_c")) for x in _brON_k]))
    _blA, _blAs = _br_run(0.95, 8, "yes", "any")
    _blS, _blSs = _br_run(0.95, 8, "yes", "side")
    _blN, _blNs = _br_run(0.95, 8, "no", "side")
    _blO, _blOs = _br_run(0.95, 8, "no", "off")
    ck(all(w["raised"] is None and _cf_kind(w, "late_boost", _cfBX)
           and not _cf_kind(w, "band_boost", _cfBX) and _cf_kind(w, "hedge", _cfBX)
           for w in (_blA, _blS, _blN, _blO))
       and _cf_kind(_blA, "late_boost_off", _cfBX)
       and [s_[2] for s_ in _blAs if s_[0] == "no"] == [1.0]
       and not _cf_kind(_blS, "late_boost_off", None)
       and all(s_[2] == 1.5 for s_ in _blSs)
       and [x.get("which") for x in _cf_kind(_blS, "boost_rail_kept", _cfBX)] == ["late"]
       and _cf_kind(_blN, "late_boost_off", _cfBX)
       and not _cf_kind(_blN, "boost_rail_kept", None)
       and not _cf_kind(_blO, "late_boost_off", None)
       and all(s_[2] == 1.5 for s_ in _blOs)
       and [(x.get("which"), x.get("rail"), x.get("leg_side"))
            for x in _cf_kind(_blO, "boost_rail_kept", _cfBX)] == [("late", "off", "yes")],
       "v-boostrail DRIVEN, the LATE rail (95c at tau 8, A55 1.5x): 'any' -- "
       "the losing NO hedge leg on a won market switches --late-mult off "
       "(today); 'side' -- it stays 1.5 (LATE_MULT at the settled records %s); "
       "'side' with the boosted YES losing -- off at once; 'off' with the "
       "boosted YES losing -- stays 1.5, boost_rail_kept rail off"
       % ([s_[2] for s_ in _blSs],))
    # DRIVEN, v-latebypass, on the same live world, with the fix ON
    # (LATE_BYPASS_FIX True handed to the world the way every driven test
    # pins a flag; the offline worlds pin it to its shipped default, off).
    # (a) the _fullcap path: BTC at 95c, tau 8, the confidence bar RAISED to
    # 0.9995 so late_boost_ok refuses the 0.999 model: the first order is the
    # plain 99, and the late add that follows is sized against the 1.0x room
    # (0) instead of the old line's 1.5x room (49.5) -- late_bypass_refused
    # says 49.5 -> 0 and the add is a zero_take, never sent. CONTROL: the bar
    # at 0.9975 lets the boost through (148.5, no bypass record). NULL:
    # LATE_MULT 1.0, nothing to bypass. Then the DEFAULT (flag off): the same
    # refused-boost late add is sized as 0925r sized it, 49.5, and sent, with
    # no record.
    def _lb_run(flags, mkts, tau0, run_s, reply=_cf_reply95):
        try:
            pintake.MAX_TAKE_COUNT, pintake.HARD_MAX = 99.0 * 1.5, 99.0 * 1.5 * 1.5
            pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT = 1e6, -1e9
            return _offline_trade_loop(mkts, live=True, reply=reply, run_s=run_s,
                                       tau0=tau0, size=99.0, bank=_CF_BANK99, flags=flags)
        finally:
            (pintake.MAX_TAKE_COUNT, pintake.HARD_MAX,
             pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT) = _cf_rails
    _lb_F = dict(_CF_LIVE, COIN_SIZE_FRAC={})
    _lb_n = lambda r, tk: [float(p.get("count")) for p in r["posts"]
                           if p.get("ticker") == tk and p.get("side") == "bid"]
    _lb_ON = dict(_lb_F, LATE_BYPASS_FIX=True)      # the fix ON for these worlds
    _lbF = _lb_run(dict(_lb_ON, LATE_PIN=0.9995),
                   [_cf_mk("KXBTC15M", "B", _cf_deep(0.95))], 8, 6.0)
    _lbF_r = _cf_kind(_lbF, "late_bypass_refused", _cfBX)
    _lbF_legs = [x.get("leg") for x in _cf_kind(_lbF, "signal", _cfBX)]
    ck(_lbF["raised"] is None and _lb_n(_lbF, _cfBX) == [99.0]
       and _cf_kind(_lbF, "late_refused", _cfBX) and not _cf_kind(_lbF, "late_boost", _cfBX)
       and len(_lbF_r) == 1 and _lbF_r[0].get("path") == "fullcap"
       and _lbF_r[0].get("n_before") == 49.5 and _lbF_r[0].get("n_after") == 0.0
       and _lbF_r[0].get("mult") == 1.5 and _lbF_r[0].get("leg") == "late_add"
       and _lbF_r[0].get("side") == "yes" and _lbF_r[0].get("live") is True
       and _lbF_r[0].get("tau") is not None and _lbF_r[0].get("tau") <= 10
       and _lbF_r[0].get("price") == 0.95 and _lbF_r[0].get("close_s") is not None
       and _cf_kind(_lbF, "zero_take", _cfBX)
       and _lbF_legs[:1] == ["full"] and len(_lbF_legs) >= 2
       and set(_lbF_legs[1:]) == {"late_add"},
       "v-latebypass DRIVEN (_fullcap path, --late-bypass-fix on): with the boost REFUSED (bar "
       "0.9995 over the 0.999 model) the first order is the plain 99 and the "
       "late add is sized against the 1.0x room -- late_bypass_refused says "
       "49.5 -> 0 ONCE (the old line's 1.5x room), the add is a zero_take and "
       "never sent, retried until the attempt cap (orders %s, legs %s, record %s)"
       % (_lb_n(_lbF, _cfBX), _lbF_legs,
          [(x.get("path"), x.get("n_before"), x.get("n_after"), x.get("tau"), x.get("price"))
           for x in _lbF_r]))
    _lbC = _lb_run(_lb_ON, [_cf_mk("KXBTC15M", "B", _cf_deep(0.95))], 8, 6.0)
    _lbN = _lb_run(dict(_lb_ON, LATE_PIN=0.9995, LATE_MULT=1.0),
                   [_cf_mk("KXBTC15M", "B", _cf_deep(0.95))], 8, 6.0)
    ck(_lbC["raised"] is None and _lb_n(_lbC, _cfBX) == [148.5]
       and _cf_kind(_lbC, "late_boost", _cfBX)
       and not _cf_kind(_lbC, "late_bypass_refused", None)
       and _lbN["raised"] is None and _lb_n(_lbN, _cfBX) == [99.0]
       and not _cf_kind(_lbN, "late_bypass_refused", None)
       and not _cf_kind(_lbN, "late_refused", _cfBX),
       "v-latebypass CONTROL / NULL (fix on): the boost allowed -> 148.5 and no "
       "bypass record; --late-mult 1.0 -> 99 and no bypass record (orders %s / %s)"
       % (_lb_n(_lbC, _cfBX), _lb_n(_lbN, _cfBX)))
    # the DEFAULT (--late-bypass-fix off, the shipped value, pinned by the
    # offline world): the same refused-boost late add is sized as 0925r sized
    # it -- against the 1.5x room, 49.5 -- and SENT, and no
    # late_bypass_refused is written. The late boost's own refusal
    # (late_refused) is still on the record, as it was in 0925r.
    _lbF0 = _lb_run(dict(_lb_F, LATE_PIN=0.9995),
                    [_cf_mk("KXBTC15M", "B", _cf_deep(0.95))], 8, 6.0)
    _lbF0_o = _lb_n(_lbF0, _cfBX)
    _lbF0_legs = [x.get("leg") for x in _cf_kind(_lbF0, "signal", _cfBX)]
    ck(_lbF0["raised"] is None and len(_lbF0_o) == 2 and _lbF0_o[0] == 99.0
       and abs(_lbF0_o[1] - 49.5) < 0.05
       and _cf_kind(_lbF0, "late_refused", _cfBX) and not _cf_kind(_lbF0, "late_boost", _cfBX)
       and not _cf_kind(_lbF0, "late_bypass_refused", None)
       and _lbF0_legs[:2] == ["full", "late_add"],
       "v-latebypass DEFAULT OFF (_fullcap path, --late-bypass-fix off): the same "
       "refused-boost late add is sized against the 1.5x room exactly as 0925r "
       "sized it -- 49.5, SENT -- and NO late_bypass_refused is written (orders "
       "%s, legs %s)" % (_lbF0_o, _lbF0_legs))
    # (b) the _stage46 path: an EARLY leg at tau 40 (a third, 33), no offer
    # until tau 9, then a deep 94c offer (outside the band) with the one-coin
    # widener ON (the only live widener besides the boost itself): A45
    # widens the top-up to 198, the boost is refused, and the A46 re-cap
    # used to let the top-up complete to 1.5 x SIZE (115.5 = 148.5 - 33);
    # now it completes to SIZE (66) and late_bypass_refused says so.
    def _lb46_book(t):
        return (_ob(0.92, 0.06, size=500.0) if (t < 2.0 or t >= 31.0)
                else _ob(None, None, size=500.0))
    _lb46_m = {"tk": "KXLB15M-LB", "series": "KXLB15M", "iid": "LB", "strike": 100.0,
               "fair": (lambda t: 0.999), "book": _lb46_book,
               "buyable": (lambda t, w, lim: 500.0 if ((t < 2.0 or t >= 31.0)
                                                      and 0.94 <= lim + 1e-9) else 0.0),
               "rungs": (lambda t, s, lim: [(0.94, 500.0)] if ((t < 2.0 or t >= 31.0)
                                                              and 0.94 <= lim + 1e-9) else [])}
    _lb46 = _lb_run(dict(_lb_ON, LATE_PIN=0.9995, ONE_COIN_DEPTH=True), [_lb46_m], 40, 36.0,
                    reply=_fill_all)
    _lb46_r = _cf_kind(_lb46, "late_bypass_refused", "KXLB15M-LB")
    _lb46_sig = [(x.get("leg"), x.get("tau")) for x in _cf_kind(_lb46, "signal", "KXLB15M-LB")]
    _lb46_o = _lb_n(_lb46, "KXLB15M-LB")
    ck(_lb46["raised"] is None and len(_lb46_o) == 2 and abs(_lb46_o[0] - 99.0 / 3.0) < 0.05
       and abs(_lb46_o[1] - (99.0 - _lb46_o[0])) < 0.05
       and [s_[0] for s_ in _lb46_sig] == ["early", "topup"] and _lb46_sig[1][1] <= 10
       and _cf_kind(_lb46, "one_coin_depth", "KXLB15M-LB")
       and _cf_kind(_lb46, "late_refused", "KXLB15M-LB")
       and len(_lb46_r) == 1 and _lb46_r[0].get("path") == "stage46"
       and abs(float(_lb46_r[0].get("n_before")) - (148.5 - _lb46_o[0])) < 0.05
       and abs(float(_lb46_r[0].get("n_after")) - (99.0 - _lb46_o[0])) < 0.05
       and _lb46_r[0].get("leg") == "topup" and _lb46_r[0].get("mult") == 1.5,
       "v-latebypass DRIVEN (_stage46 path, --late-bypass-fix on): early 33 at tau 40, a widened "
       "top-up inside the late window with the boost REFUSED completes the "
       "position to SIZE (66), not to 1.5 x SIZE (115.5) as the old re-cap "
       "allowed; late_bypass_refused path stage46 (orders %s, legs %s, record %s)"
       % (_lb46_o, _lb46_sig, [(x.get("path"), x.get("n_before"), x.get("n_after"))
                               for x in _lb46_r]))
    # the DEFAULT (flag off) on the same _stage46 world: the widened top-up
    # completes to 1.5 x SIZE (115.5 = 148.5 - 33), exactly the old re-cap,
    # and no late_bypass_refused is written
    _lb460 = _lb_run(dict(_lb_F, LATE_PIN=0.9995, ONE_COIN_DEPTH=True), [_lb46_m], 40, 36.0,
                     reply=_fill_all)
    _lb460_o = _lb_n(_lb460, "KXLB15M-LB")
    _lb460_sig = [(x.get("leg"), x.get("tau")) for x in _cf_kind(_lb460, "signal", "KXLB15M-LB")]
    ck(_lb460["raised"] is None and len(_lb460_o) == 2 and abs(_lb460_o[0] - 99.0 / 3.0) < 0.05
       and abs(_lb460_o[1] - (148.5 - _lb460_o[0])) < 0.05
       and [s_[0] for s_ in _lb460_sig] == ["early", "topup"] and _lb460_sig[1][1] <= 10
       and _cf_kind(_lb460, "one_coin_depth", "KXLB15M-LB")
       and _cf_kind(_lb460, "late_refused", "KXLB15M-LB")
       and not _cf_kind(_lb460, "late_bypass_refused", None),
       "v-latebypass DEFAULT OFF (_stage46 path, --late-bypass-fix off): the same "
       "widened top-up with the boost REFUSED completes the position to 1.5 x "
       "SIZE (115.5) exactly as the 0925r re-cap did, and NO late_bypass_refused "
       "is written (orders %s, legs %s)" % (_lb460_o, _lb460_sig))
    # every new record's KEY SET, as the tracker reads it
    _ks = lambda recs, need: all(set(need) <= set(r.keys()) for r in recs) and bool(recs)
    ck(_ks(_lbF_r + _lb46_r, ("kind", "t", "ticker", "close_s", "live", "side", "path", "tau",
                              "price", "n_before", "n_after", "mult"))
       and _ks(_xca_c + _xcb_c + _xcc_c, ("kind", "t", "ticker", "close_s", "live", "side",
                                           "asked", "allowed", "trimmed", "reason", "mult"))
       and _ks(_oc5_r, ("kind", "t", "ticker", "close_s", "live", "side", "open_positions",
                        "old_cap", "leg"))
       and _ks(_brS_k + _brO_k + _brON_k, ("kind", "t", "which", "ticker", "close_s", "leg_side",
                                           "boosted_side", "cost", "pnl_c", "rail", "live"))
       and _ks(_cjar, ("kind", "t", "ticker", "close_s", "side", "ask", "min_ask", "jump_sd",
                       "belief", "tau", "want", "n", "entry", "live"))
       and _ks(_vtl_h + _vtr_h + _vlr_h + _kinds(_oxjb, "hedge"),
               ("kind", "t", "ticker", "close_s", "live", "tick_mode", "limit_legacy",
                "tick_rounded", "ladder", "limit_sent", "ask", "n", "side"))
       and _ks(_vtl_h + _vtr_h + _vlr_h, ("status_code", "err"))
       and _ks(_oxjb_x + _xca_x + _kinds(_oc5, "hedge_extra"),
               ("kind", "t", "ticker", "close_s", "live", "tick_mode", "limit_legacy",
                "tick_rounded", "ladder", "trigger_label", "fired_on_belief", "trigger",
                "side", "n", "asked", "extra_of", "mult", "base_n", "belief", "tau")),
       "v-0925t RECORD SPEC: late_bypass_refused, extra_stake_capped, "
       "open_cap_relaxed, boost_rail_kept, hedge_cheap_skip, hedge (paper and "
       "live, with status_code/err live) and hedge_extra each carry every key "
       "the tracker reads")

''')

# ===========================================================================================================
# pintake.py
# ===========================================================================================================
T.replace('''def check_take(body, market_close_epoch, now_epoch, base=None, ledger=None,
               max_tau=None, hedge=False):
    """Every reason NOT to send. Empty list == ok. Runs before signing.

    `hedge=True` (K2, 2026-09-22) skips exactly ONE rail: the ledger halt.
    Every other rail -- count, HARD_MAX, price, IOC, post_only, side, tau,
    the stake cap, the loss abort, the environment -- applies to a hedge as
    to anything else. See the note at the halt check below.

    v-scalein-caps (2026-09-25): a hedge that COVERS a held position (see
    covers_held) also skips the two DOLLAR rails, the stake cap and the loss
    abort. Every count, price, IOC, side, tau and environment rail stays."""
    bad = []
    L = LEDGER if ledger is None else ledger
    _cover = bool(hedge) and covers_held(body, L)
''', '''def check_take(body, market_close_epoch, now_epoch, base=None, ledger=None,
               max_tau=None, hedge=False, extra=False):
    """Every reason NOT to send. Empty list == ok. Runs before signing.

    `hedge=True` (K2, 2026-09-22) skips exactly ONE rail: the ledger halt.
    Every other rail -- count, HARD_MAX, price, IOC, post_only, side, tau,
    the stake cap, the loss abort, the environment -- applies to a hedge as
    to anything else. See the note at the halt check below.

    v-scalein-caps (2026-09-25): a hedge that COVERS a held position (see
    covers_held) also skips the two DOLLAR rails, the stake cap and the loss
    abort. Every count, price, IOC, side, tau and environment rail stays.

    v-extracap (2026-11-04): `extra=True` marks pinrun's v-oddsmult EXTRA leg
    -- (mult - 1) x the position of the hedge side, bought over the covering
    hedge. It is NEW exposure, but _book() folds the cover into the same
    position (contracts 2 x n), so covers_held took the extra for a cover too
    and it skipped both dollar rails. With extra=True the two dollar rails
    apply; the halt skip (hedge=True) and every other rail are exactly as
    before. The covering hedge itself never passes extra=True."""
    bad = []
    L = LEDGER if ledger is None else ledger
    _cover = bool(hedge) and not extra and covers_held(body, L)
''')
T.replace('''def take(base, pk, key_id, ticker, want, price, count, market_close_epoch,
         exchange_index=0, client_id=None, now_epoch=None, max_tau=None,
         hedge=False):
    """Build, CHECK, then -- only with an empty violation list -- POST.

    Returns the normalised dict from normalise(), plus "refused": [...] and
    status_code None when the rails said no. The self-test reads this
    function's source and fails if the wire call appears before the check.

    hedge=True: this order buys the other side of a position already held.
    It is checked by every rail except the ledger halt (see check_take), and
    when it goes out PAST a halt that is written to the ledger and flagged
    on the result as out["past_halt"]. v-scalein-caps: when it COVERS a
    position the ledger holds (covers_held) it also skips the stake cap and
    the loss abort.
    """
''', '''def take(base, pk, key_id, ticker, want, price, count, market_close_epoch,
         exchange_index=0, client_id=None, now_epoch=None, max_tau=None,
         hedge=False, extra=False):
    """Build, CHECK, then -- only with an empty violation list -- POST.

    Returns the normalised dict from normalise(), plus "refused": [...] and
    status_code None when the rails said no. The self-test reads this
    function's source and fails if the wire call appears before the check.

    hedge=True: this order buys the other side of a position already held.
    It is checked by every rail except the ledger halt (see check_take), and
    when it goes out PAST a halt that is written to the ledger and flagged
    on the result as out["past_halt"]. v-scalein-caps: when it COVERS a
    position the ledger holds (covers_held) it also skips the stake cap and
    the loss abort. v-extracap: extra=True (pinrun's v-oddsmult extra leg,
    sent with hedge=True) keeps the halt skip but NOT the dollar exemption:
    the stake cap and the loss abort judge it like any new exposure.
    """
''')
T.replace('''    violations = check_take(body, market_close_epoch, now, base=base,
                            max_tau=max_tau, hedge=hedge)
''', '''    violations = check_take(body, market_close_epoch, now, base=base,
                            max_tau=max_tau, hedge=hedge, extra=extra)
''')
# pintake's own self-test: the extra flag, next to the covers_held checks it amends
T.before('''    # DRIVEN through take(): committed AT the cap, a real booked YES fill;
    # the covering hedge reaches the wire, the entry does not.
''', '''    # v-extracap (2026-11-04): the SAME covering body with extra=True is
    # refused at the stake cap and the loss abort (pinrun's extra leg, which
    # _book() would otherwise let covers_held wave through); with room it
    # passes, and extra=True without hedge=True is judged like an entry.
    for desc, led in (
            ("stake cap", dict(_fresh_ledger(), committed=MAX_RUN_STAKE,
                               positions=sc_held)),
            ("loss abort", dict(_fresh_ledger(), realised=LOSS_ABORT - 1.0,
                                positions=sc_held))):
        if not check_take(sc_h, close_ok, now, ledger=led, hedge=True, extra=True):
            fails.append("v-extracap: the extra (hedge=True, extra=True) was let "
                         "past the %s" % desc)
        if check_take(sc_h, close_ok, now, ledger=led, hedge=True):
            fails.append("v-extracap: the covering hedge must still pass the %s" % desc)
        if not check_take(sc_h, close_ok, now, ledger=led, extra=True):
            fails.append("v-extracap: extra=True without hedge=True must still be "
                         "refused at the %s" % desc)
        sc_n += 3
    if check_take(sc_h, close_ok, now, ledger=sc_room, hedge=True, extra=True):
        fails.append("v-extracap NULL: with room under every rail the extra passes")
    sc_n += 1
''')
T.replace('''    print(f"    {sc_n} checks: covering hedges pass the stake cap and the loss "
          f"abort; entries, unlabelled, same-side, unheld and oversized orders "
          f"do not; 7 other rails still bind; driven take() at the cap: wire "
          f"{sc_posts}")
''', '''    print(f"    {sc_n} checks: covering hedges pass the stake cap and the loss "
          f"abort; entries, unlabelled, same-side, unheld, oversized and "
          f"extra=True orders do not; 7 other rails still bind; driven take() "
          f"at the cap: wire {sc_posts}")
''')

R.write()
T.write()
print("patched", PR, sha12(PR))
print("patched", PT, sha12(PT))
print("v-0925t flags, each = 0925r behaviour when omitted: --hedge-tick legacy, --jump-hedge-min-ask 0, "
      "--boost-rail any, --late-bypass-fix off")
print("  the late-mult bypass fix is BUILT but OFF by default (0925t sizes exactly as 0925r); "
      "--late-bypass-fix on turns it on")
