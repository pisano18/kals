"""fixes.py -- every live pin change, scored on pin's own logs: how often it engaged, when last, what is still open and
the net $ so far (+ made or saved, - cost or gave up). The data behind the phone's /fixes (/changes) page and the rules
watcher's alerts. Pure: no network, no Kalshi, no key; it only reads results\\pinrun-live-*.jsonl (through botdata's
path helpers, or an explicit list of paths for a test).

v-fixes (2026-11-04; the operator: "track them thoroughly and have a telegram command that makes it very simple to see
times any of them have been engaged and the positive or negative overall result of it").

THE CHANGES and when each counts as engaged (the push-11-04 scoring table):
  A later-buy check     a refusal with gate ws_later_fall / ws_later_skip     pinrules_watch.score_A (reused)
  B jump cap            jump_capped                                           pinrules_watch.score_B (reused)
  C bigger hedge 1.25x  hedge_extra that filled                               pinrules_watch.score_C (reused)
  D boost rail side/off boost_rail_kept: the band / late boost legs placed after it in that run (the old "any" rail had
                        switched the boost off there): their EXTRA contracts' money at the result, fee in
  E hedge tick round    a hedge whose limit was rounded onto the grid from an off-grid legacy limit: that hedge leg's own
                        settled money (the old build's order was rejected, so the leg would not have existed)
  F cheap jump skip     hedge_cheap_skip: pinrules_watch.score_B's method on the skipped hedge (bet won: + the premium
                        saved; bet lost: - what it would have got back, less what pin's later hedge got on those contracts)
  G late-mult bypass    late_bypass_refused: the (n_before - n_after) contracts at the leg's price, + if the leg lost,
                        - if it won
  H extra stake cap     extra_stake_capped: the trimmed contracts at the extra's price, + if the extra side lost, - if won
  I max positions 5     open_cap_relaxed: that leg's own settled money
  J extra on belief     hedge_extra fired on belief with another trigger label: that leg's own settled money
  K cheap morning skip  a refusal with gate cheap_window (v-cheapwin, 11-07; the operator: "log and track the difference
                        it makes and what it would've been without the rule"), priced by its own shadow
                        (cheap_window_settled): the contracts pin would have asked x CW_FILL / CW_FIRST_SHARE at the
                        ladder's average price, plus the belief hedge it would have bought; + when that shadow lost
                        (saved), - when it won (gave up). The row also says what the window as a whole made with the
                        rule and what it would have made without it.
  L jump hedge shadow   a jump_shadow record with would_send (v-0925v JS, 11-08: --hedge-jump-shadow 6 in place of
                        --hedge-jump 6; the operator: "Keep working on jump hedge. It's a big problem currently"): the
                        jump hedge pin WOULD have sent that second, sized as the send site sizes it, nothing sent. Priced
                        as F prices a skipped jump hedge (pinrules_watch.score_B's method): bet won: + the premium kept
                        (n x ask + fee), less what pin's odds-line hedge then really paid on those contracts; bet lost: -
                        what it would have got back, less what the odds-line hedge really got back on those contracts.
                        The row also says what the jump hedge itself would have made (paid on won markets vs saved on
                        flips) and how many alarms the 8 sd cap or the 5c bar would have stopped anyway (not counted).
  M 3rd bet blocked     call B (v-0925v, 11-08 14:31Z: --extra-coin 0 --late-extra 0 --bank-brake 4.5 in place of 1 /
                        1 / 3.00, the same SIZE; the operator: "Make sure we're tracking how much money is being lost
                        blocking the 3rd"; the 12-08 read reverts B only above $5/day). Two tallies, both from pin's
                        own logs, nothing scaled:
                        (1) the NET: a full buy pin DID make that the 2-bet budget held back (its signal's budget_left
                        was the binding cap) on a new coin, or inside the old late window: the contracts the old argv's
                        third SIZE of room would have let the sweep or the band boost add (pinrun's wideners read
                        close_budget_for as their room), judged by pin's own settled result of that market: + when the
                        bet lost (the stake not spent, fee in, at the fill price), - when it won (the gain not made, at
                        the order's limit, so a ceiling). This is what reverting B gives back.
                        (2) `third`, under the net and NOT in it: each close_budget refusal (written before the book is
                        read, so it carries no ask) is read against the trajectory log (pintraj-live-<stamp>.jsonl, one
                        record a second a market: ask, ask_size, fair, held): under the old argv the close had ONE more
                        SIZE, spendable by a coin not yet bought in the close at any second, or by any market inside
                        late_extra_tau; the first refused market that passes pin's own entry gates at a second takes
                        it (ask on our side, confidence at PIN, ask at or under the ceiling or a 98-99c band tenth,
                        edge and EV floors, the dump guard, the early-leg floor, the cheap window, a book of 1+);
                        n = the leg's size capped by the book and the room; the result from pin's own settled record,
                        else the trajectory's last second (fair 1.0 / 0.0), else missed.py's cache. + when it would
                        have lost (saved), - when it would have won (cost; a ceiling: its hedges are not known). It is
                        kept OUT of the net because the old build dropped the very same bet at its base check
                        (pinrun's close_budget_base, R4 2026-09-22: "the third bet is granted, priced, sized for, and
                        then dropped"): reverting B alone would place none of these.
  C's step              v-oddsmult15 (2026-11-14; the operator allows the money change only if "you can track the result of
                        each change vs if it never was implemented"): --hedge-odds-mult 1.5 in place of 1.25. C keeps its
                        total (every extra leg's own money); a line under it prices the STEP: of each hedge_extra with
                        mult 1.5, the contracts over what 1.25x would have bought -- max(0, filled - 0.25 x the position),
                        the position being the record's orig_n -- at the leg's most expensive fills when the record has a
                        per-fill `fills` list, else at the order's limit_sent (real hedge_extra records carry only the
                        average price, and the step is the deepest, dearest part of the leg: the average would flatter
                        it; the limit is the most it allowed itself to pay, never better than reality, and the line says
                        "priced at the limit, a conservative bound"; a leg with neither is said NOT PRICED, never $0),
                        won or lost by the market, fee in as score_C bills it: "of which the 1.25x->1.5x step: +$Y on Z
                        fires".
  O ladder cash limit   v-ladder-rail100 (2026-11-14, the same rule from the operator): the LADDER's money rail goes from
                        82% of its pot to 100% (--pot-per-contract 5.9756 --commit-frac 1.0 in place of --fit --commit-frac
                        0.82 --big-coins-above 7000: the same bid size, 6 bids a close instead of 5). ladder_live.py marks
                        each bid it places with over_82 (would the old 0.82 x pot rail have refused it?) and carries the
                        mark onto every live_fill of it. Priced from the ladder's own order log
                        (results\\ladder-live-orders.jsonl), per settled market: the market's live_settle pnl x (the
                        over-82 contracts filled / all contracts filled there), one event per over-82 bid that filled.
                        A bid that never filled cost nothing either way. A ladder start on the 100% rail whose record has
                        no argv / old_limit comes from the OLDER ladder code, which never marks a bid: while it is the
                        latest start, O says "ON THE 100% RAIL BUT NOT TRACKED" as its problem (a warning line in its
                        block and counted on top of /fixes), never a quiet 'none yet'; an ended such window is said as
                        a NOT TRACKED line under the net. O is the ladder's change, not pin's: its row is
                        in the report whenever a ladder order log is there to read (on the server always; a test's
                        folder of pin logs has none, so IDS stays pin's and LADDER_IDS holds O and Q).
                        WITHDRAWN 11-14 (O_WITHDRAWN; never live): no tracking design could price the bids only the 100%
                        rail places against never changing it (two refuted by reviewers), so the ladder stays at 82%.
                        While withdrawn O's row is O_NOT_LIVE whatever the log holds, never a problem, never in totals();
                        the scoring above runs only if O_WITHDRAWN is ever set False.
  P band99 late-only    v-0925x band99late (2026-11-14 18:11:41Z, --band99-max-tau 30; the operator: "make sure all of
                        this is being tracked what the results would be if it wasn't changed"): the band99 leg (a tenth
                        of the bet at up to 99c, in a market pin holds nothing in) is placed only with 30 s or less left;
                        a band leg pin skips for being earlier writes ONE band99_shadow record a market (n, ask, tau,
                        leg, ...) and spends nothing (no early leg, no fill). Scored per shadow market against never
                        changing it, once the market settles:
                        (a) GIVEN UP: what the skipped band leg would have made at the market's result: n x (1 - ask) -
                        fee if it won, -(n x ask) - fee if it lost (pinrules_watch.value, at the ask it saw: the cheapest
                        price, so never flattering the rule either way), a loss less the P_HEDGE_BACK (41%) pin's hedges
                        win back on a band loss (the 11-14 band99 read; the gross is said too). The result: pin's own
                        settled record, else the trajectory's last second (fair at 1.0 / 0.0), else missed.py's cache.
                        The trajectory is the pintraj log beside the shadow's pin log, wherever it is now
                        (logfiles.resolve: results\\ while plain, results\\archive\\<name>.gz once log_rotate has moved it,
                        two days after its last write); the close's last row of each shadow market of an archive is
                        kept in _P_CLOSES (one small row a market, never a trajectory; _load never clears it).
                        (b) GAINED: the real settled money of pin's own legs in that market the band leg would have
                        blocked (p_blocked), each with its contracts' share of the market's hedges: in pinrun's order of
                        the gates, an early leg (early_once: the band leg would have been the market's early leg), a
                        leg that would be the market's 3rd fill counting the band leg (max_per_market, 2), a later band
                        leg (band99_held: the band leg would have held the market).
                        THE TOP-UP after a blocked early leg (p_topup): pin's real top-up completed the position to the
                        full bet (pinrun.staged_take: full x the band / late multiple - early_held); the old code's
                        would have completed it from the band leg's B contracts instead of the early leg's E, so it
                        would have bought E - B more. When the real top-up filled exactly that full size, the E - B
                        contracts are priced at the top-up's price and the market's result (fee in, with their
                        contracts' share of the hedges, as a blocked leg's) and added to GIVEN UP (a negative E - B:
                        the top-up the old code's would have been smaller by); any other top-up (cut by the book or the
                        price) cannot say how much bigger the old one would have filled: listed as not counted.
                        The net is GAINED - GIVEN UP. Not counted: the full leg the old code would have cut to a top-up
                        by the band leg's contracts, the band leg's share of the close's budget, a won band leg's hedge
                        premiums.
  Q ladder midnight     v-ladder-dayreset (the ladder's 2026-11-14 17:53:01Z start): a day stop ends at the next ET
    reset               midnight (a 'day_stop_reset' record); before, it held until the ladder's process ended (up to 7
                        days). Priced from the ladder's order log: per reset, every live_settle pnl of the markets the
                        ladder filled from the reset until its next start (or the next reset), pro rata by the contracts
                        filled in that span -- the old code would have stayed halted for exactly that span. A span still
                        running, or a market of it not settled yet, is open with the money so far.
A and B count from 11-01 15:37 ET, C from 11-02 08:35 ET, D to J from the first start record after the 0925r build
(code_sha ca156bf45704) with another code_sha, K from the first start record that names a cheap_window, L from the
first start record with hedge_jump_shadow set (pinrun refuses it next to --hedge-jump, so the jump hedge is off there),
M from the first start record with extra_coin 0 and late_extra 0 (the start record carries both and bank_brake), C's
step from the first start record with hedge_odds_mult 1.5 (else its first 1.5x leg), O from the first ladder start
record whose argv has --commit-frac 1.0 (or whose auto block says commit_frac 1.0) -- while not withdrawn --, P from
the first start record with band99_max_tau set, Q from the first ladder start record with start_reads (the code that
resets at midnight: v-ladder-dayreset shipped in one commit with v-ladder-start429, which added the field).
An engagement whose market has not settled is "open" (not in net $).

A settled leg's pnl_c is pin's own figure for the whole leg, the taker fee INSIDE it (pinrun: pnl = filled * (1 - cost
or -cost) - billed_fee(cost, filled)). A leg is matched by ticker, our side (want; a hedge leg's want is its hedge side),
the nearest cost, then the nearest time; a leg is claimed once per change. Records of older builds may lack fields:
every read is a .get with a default.

    report(paths=None, now=None) -> [change dict per A..N, then O when a ladder order log is read, then P, then Q when
        a ladder order log is read]:
        {id, name, what, since (ET words or None = not live yet), since_t, engaged, last_engaged, last_t, open,
         net_usd, events: [{t, epoch, et, coin, words, usd (None while open), open}],
         off (True only for G while the launcher leaves --late-bypass-fix off: built, switched off),
         extra (lines under the net; K's with / without the rule; L's paid vs saved and the alarms not counted; M's
         held-back contracts and the true-3rd-bet line; P's given up / gained / net and the gross; Q's money after
         the resets),
         not_live (the phone's words while since is None, or None for the default),
         third (M only: the true-3rd-bet events, the same shape as events, not in net_usd; [] elsewhere),
         problem (None, or words the phone puts on a warning line and counts on top of /fixes: O_UNTRACKED while the
         latest ladder start runs the 100% rail on code that does not mark the bids -- O can then count nothing;
         never while O is withdrawn),
         withdrawn (True only for O while O_WITHDRAWN: never live, never in totals, never a problem),
         retired (None, or the short words of a change that is off for good while it is not live: O while withdrawn,
         N while shelved; the phone folds such a change into one short line, its not_live words stay whole here)}
    totals(changes) -> {engaged, open, net_usd, problems (the ids saying a problem)} over every change but J and a
        withdrawn one (problems: every change not withdrawn); J's leg is already inside C. L is in: the
        premium it keeps and the save it misses are pin's real money, as K's skipped buys are. M is in by its net
        (the held-back contracts of pin's own buys); its `third` list is not. O is in when its row is live (the
        ladder's real money on the bids only the new rail placed), never while withdrawn. P is in (pin's own blocked
        legs' real money less what the skipped band legs would have made), Q is in (the ladder's real money after its
        resets).
"""
import calendar
import json
import math
import os
import re
import time

from botdata import logs as _logs
from botdata.clock import et_clock as _et_clock
# downtime.et_offset's DST rule, not zoneinfo: the server's Python has no tz database (no tzdata), so
# ZoneInfo("America/New_York") raises there (found 11-04 rehearsing the watcher's tick with python -I)
from botdata.clock import et_offset as _et_offset
from botdata.clock import utc_epoch as _epoch
# pure at import: constants (TELEGRAM_CFG is only a path), the scorers and the Logs class; its Phone class is used
# only inside tick(), which nothing here calls
import pinrules_watch as _rw
import logfiles as _lf                    # noqa: E402  (a fix tracked past 60 days reads archived logs)
from botdata import paths as _paths       # M: missed.py's result cache (results\\missed_results_cache.json, read-only)

BASE_SHA = "ca156bf45704"                 # pin 0925r: D to J start at the first later start record with another sha
UNKNOWN_AFTER_S = _rw.UNKNOWN_AFTER_S     # a market with no result 3 h after its close: "unknown", still open
IDS = "ABCDEFGHIJKLMNP"                   # pin's changes: a row each in every report
LADDER_IDS = "OQ"                         # the ladder's (v-ladder-rail100, v-ladder-dayreset): a row each whenever a
#                                           ladder order log is read (report: A..N, O, P, Q -- in letter order)
NAMES = {"A": "later-buy check", "B": "jump cap", "C": "bigger hedge", "D": "boost rail", "E": "hedge tick",
         "F": "cheap jump skip", "G": "late-boost bypass fix", "H": "extra stake cap", "I": "max positions 5",
         "J": "extra on odds", "K": "cheap morning skip", "L": "jump hedge shadow", "M": "3rd bet blocked",
         "N": "hedge line 0.60", "O": "ladder cash limit 100%", "P": "band99 late-only", "Q": "ladder midnight reset"}
# C's step (v-oddsmult15, 2026-11-14): --hedge-odds-mult 1.5 in place of 1.25; the step is the part of each 1.5x extra
# leg over the (1.25 - 1) x position the old multiple would have bought
C_OLD_MULT = 1.25
C_NEW_MULT = 1.5
C_STEP = "the 1.25x->1.5x step"
# O (v-ladder-rail100, 2026-11-14): the ladder's money rail 82% -> 100% of its pot; ladder_live.py marks each bid the old
# rail would have refused (over_82) on its 'placed' record and on every 'live_fill' of it
O_LOG = "ladder-live-orders.jsonl"        # ladder_live.ORDER_LOG's name in results\ (bots/ladder.py Logs.path)
O_OLD_FRAC = 0.82
O_HEAD = "the bids the old 82% limit would have refused"
# WITHDRAWN 11-14 (never live): it cannot be tracked against never changing it. While True, O's row is O_NOT_LIVE
# whatever the ladder log holds -- never live, never a problem, never in totals(); its scoring runs only if set False
O_WITHDRAWN = True
O_NOT_LIVE = "withdrawn 11-14: it could not be tracked against never changing it, so the ladder stays at 82%"
O_RETIRED_HEAD = "withdrawn 11-14"         # the phone's one short line while withdrawn (change["retired"]): this, then
O_RETIRED = O_RETIRED_HEAD + ", stays at 82%"              # ', stays at 82%' -- or the 1.0 clause when it does not
# the latest ladder start runs the 100% rail on code that does not mark the bids (its start record has no argv / old_limit):
# O cannot count anything, so it is the row's problem (report: change["problem"]; /fixes puts it on top), never 'none yet'
O_UNTRACKED = "ON THE 100% RAIL BUT NOT TRACKED (the ladder code that marks the bids is not running)"
L_NOT_LIVE = "not live yet (comes with the next pin restart)"
# P (v-0925x band99late, 2026-11-14): the band99 leg only with --band99-max-tau seconds or less left
P_HEDGE_BACK = 0.41                       # the share of a band loss pin's hedges win back (the 11-14 band99 read)
P_HEAD = "early band bets skipped"
P_NOT_LIVE = "not live yet (comes with the first pin start on --band99-max-tau 30)"
P_TOPUP_TOL = 0.011                       # a real top-up 'at the full size': filled + early_held within this of the full
#                                           bet x the multiple (pinrun sends counts to the cent)
_LINE_T = re.compile(rb'"t": ?"([^"]+)"')               # a trajectory line's own time (its only "t" key)
_TAU01 = re.compile(r'"tau": ?(?:1|0|-\d+)[,}]')        # a trajectory line at the close (tau 1 or less)
# P: the close of each shadow market read from an ARCHIVED (.gz) trajectory log, kept across reports and NEVER cleared
# by _load (an archive never changes; a gzip stream cannot be searched, so each archive is read through once for the
# markets P asks of it, not once a report): (archive path, size, mtime_ns) -> {(ticker, close_s): [its last row at tau 1
# or less, tau and fair only] or [] when the archive has none}. One small row a shadow market, never a trajectory.
_P_CLOSES = {}
# Q (v-ladder-dayreset, the ladder's 2026-11-14 17:53:01Z start): a day stop ends at the next ET midnight
Q_HEAD = "money the ladder made after a midnight reset (the old code stayed halted)"
Q_NOT_LIVE = "not live yet (comes with the ladder's first start on the midnight-reset code)"
M_NOT_LIVE = "not live yet (comes with the first pin start on call B)"
N_NOT_LIVE = ("SHELVED 11-09, never deployed: the deep dive found no out-of-sample edge (-$1.79 to +$1.53 a day at "
              "today's size); counted only if pin ever starts on --hedge-belief 0.60")
N_RETIRED = "shelved 11-09"                     # the phone's one short line while not live (change["retired"])
N_OLD_LINE = 0.40                         # the line N is priced against (the live value 09-21..11-08)
N_NEW_LINE = 0.60                         # N starts at the first start record whose hedge_belief is at least this
N_READ = "the 11-22 read: back to 0.40 if N's net is under $0 (under -$50 at any look)"
M_EXTRA = 1.0                             # the old argv's allowance: ONE more SIZE a close (--extra-coin 1 / --late-extra 1
#                                           share one bet, pinrun.close_budget_for: "one extra bet, spendable either by a
#                                           new coin or in the last seconds, whichever arrives first")
M_READ = "the 12-08 read reverts B only above $5/day"
# M's reading of pin's entry gates when the start record does not say (pinrun's shipped values, 0925v)
M_RULES = {"pin": 0.995, "price_ceiling": 0.98, "band99_ceiling": 0.99, "band99_frac": 0.10, "edge_floor": 0.003,
           "ev_floor": 0.003, "measured_flip": 0.009, "dump_discount": 0.15, "early_min_price": 0.90, "early_frac": 0.333,
           "tau_max": 30, "tau_min": 3, "max_per_close": 2, "max_per_market": 2, "late_tau": 10, "late_extra_tau": 15,
           "band_mults": [[0.955, 0.981, 1.5]], "cheap_window": None, "max_edge_c": 10.0, "edge_cap_tau": 20,
           "early_max_edge": 10.0, "min_level": 1.0}
_MISSED = {"key": None, "data": None}     # missed.py's cache, read once per file state
# K's shadow scale, measured on pin's live logs 10-16..11-07: orders with an ask under 98c filled 54,063 of the 69,390
# contracts they asked for, and a market's first buy is 81% (flips) to 84% (wins) of its contracts -- the same on both
# sides, so scaling the first refused buy up to the whole market tilts the score toward neither the rule nor against it
CW_FILL = 0.78
CW_FIRST_SHARE = 0.83
_CACHE = {}                               # (path, size, mtime) tuple -> (Logs, Scan); the phone asks every /fixes


def _et(y, mo, d, hh, mm):
    """UTC epoch of an Eastern wall time: the wall time read as UTC, less the ET offset in force at that moment
    (two passes settle the offset; the one ambiguous hour a year resolves to the earlier, daylight, reading)."""
    g = calendar.timegm((y, mo, d, hh, mm, 0))
    e = g - _et_offset(g)
    return float(g - _et_offset(e))


SINCE_AB = _et(2026, 11, 1, 15, 37)       # --ws-later-fall-c 10 and --hedge-jump-max 8 went live (0925q)
SINCE_C = _et(2026, 11, 2, 8, 35)         # --hedge-odds-mult 1.25 went live (0925r)

_STAMP = re.compile(r"pinrun-live-(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z")
_TK15 = re.compile(r"^KX[A-Z0-9]+?15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-")
_TKD = re.compile(r"^KX[A-Z]+?D-(\d{2})([A-Z]{3})(\d{2})(\d{2})-")
_MON = {m: i + 1 for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV",
                                        "DEC"))}


def et_words(epoch, with_day=True):
    """'Nov 4 2:45 AM ET' (botdata.clock.et_clock); None -> None."""
    return _et_clock(epoch, with_day=with_day) if epoch is not None else None


def close_of(ticker):
    """A market's close epoch from its ticker (15-minute coins: KXZEC15M-26NOV040245-45 closes 11-04 02:45 ET; hourly
    KXBTCD-26OCT3123-T...: 23:00 ET), or None."""
    t = str(ticker or "")
    m = _TK15.match(t)
    if m:
        yy, mon, dd, hh, mm = m.groups()
    else:
        m = _TKD.match(t)
        if not m:
            return None
        yy, mon, dd, hh = m.groups()
        mm = "00"
    try:
        return _et(2000 + int(yy), _MON[mon], int(dd), int(hh), int(mm))
    except (KeyError, ValueError, OverflowError):
        return None


def stamp_of(path):
    """The run's start epoch from the log's name, or None."""
    m = _STAMP.search(os.path.basename(str(path)))
    if not m:
        return None
    return float(calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0)))


def paths_since(paths, since):
    """The logs that can hold anything from `since` on: every run started at or after it, plus the run before (the one
    live at `since`). A log with no stamp in its name is placed by its mtime."""
    rows = []
    for p in paths:
        s = stamp_of(p)
        if s is None:
            try:
                s = os.path.getmtime(p)
            except OSError:
                continue
        rows.append((s, p))
    rows.sort()
    keep = [p for s, p in rows if s >= since]
    i = len(rows) - len(keep)
    return [p for _s, p in rows[max(0, i - 1):]]


def pin_paths(since=SINCE_AB):
    """pin's live logs for the tracker (botdata.logs.pin_logs: results\\pinrun-live-*.jsonl, RESULTS injectable), the
    ones log_rotate.py archived after 60 days included: a fix read 2 months after it went live still sees its first day."""
    return paths_since(_logs.pin_logs(archived=True), since)


def off_grid(p):
    """True when `p` is not on Kalshi's tapered_deci_cent grid (0.1c steps under 10c and from 90c, 1c between)."""
    if p is None:
        return False
    try:
        p = float(p)
    except (TypeError, ValueError):
        return False
    mils = round(p * 1000.0)
    if abs(p * 1000.0 - mils) > 1e-6:
        return True
    if p < 0.10 - 1e-9 or p >= 0.90 - 1e-9:
        return False
    return mils % 10 != 0


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _value(n, p, wins):
    """Money of n contracts bought at p on a side that wins (True) or loses, fee in (pinrules_watch.value)."""
    return _rw.value([(float(n), float(p))], wins)


def _cents(p):
    return ("%.1fc" % (100 * float(p))) if p is not None else "?"


def cw_in_window(close_s, window):
    """True when a market closing at `close_s` closes inside `window` [start_h, end_h, ...) on the Eastern clock: pinrun's
    cheap_window_block without the price (a 06:00 close is in 6..10, a 10:00 close is out)."""
    try:
        cs = float(close_s)
        g = time.gmtime(cs + _et_offset(cs))
        h = g.tm_hour + g.tm_min / 60.0
        return float(window[0]) <= h < float(window[1])
    except (TypeError, ValueError, IndexError, OverflowError, OSError):
        return False


def cw_contracts(s, r=None):
    """K: the contracts a skipped market would have held: what pin would have asked for its first buy (n_ask, from the
    shadow or else the refusal), x CW_FILL / CW_FIRST_SHARE."""
    n = _f((s or {}).get("n_ask"), None)
    if n is None:
        n = _f((r or {}).get("n_ask"), _f((r or {}).get("size")))
    return max(0.0, n) * CW_FILL / CW_FIRST_SHARE


def cw_shadow_usd(s, r=None):
    """K: what one skipped market would have made (+) or lost (-) without the rule, fee in: cw_contracts at the
    ladder's average price (px), plus the belief hedge pin would have bought (hedge_mult x those contracts of the other
    side at hedge_px). None until the shadow has a yes / no result."""
    res = (s or {}).get("result")
    if res not in ("yes", "no"):
        return None
    side = s.get("want") or (r or {}).get("want")
    won = res == side
    n = cw_contracts(s, r)
    usd = _value(n, _f(s.get("px"), _f(s.get("price"), 0.98)), won) if n > 0 else 0.0
    if s.get("hedge_px") is not None and n > 0:
        usd += _value(n * _f(s.get("hedge_mult"), 1.0), _f(s.get("hedge_px")), not won)
    return usd


def _hour(h):
    """6 -> '6 AM', 12 -> '12 PM', 15 -> '3 PM', 0 or 24 -> '12 AM'."""
    h = int(round(_f(h))) % 24
    return "%d %s" % (12 if h % 12 == 0 else h % 12, "AM" if h < 12 else "PM")


def js_fills(r):
    """L: the fill the shadow jump hedge would have made, [(n, ask)] (pinrun's jump_shadow_fields has already sized n
    to the book's depth and the position's unhedged part), or [] when there is nothing to price."""
    n, ask = _f((r or {}).get("n")), _f((r or {}).get("ask"), None)
    return [(n, ask)] if n > 0 and ask is not None and 0.0 < ask < 1.0 else []


def js_premium(r):
    """L: what the shadow jump hedge would have paid up front, fee in: n x ask + Kalshi's fee (pinrules_watch.fee,
    ceil(7 x ask x (1 - ask) x n) / 100)."""
    return -_rw.value(js_fills(r), False)


def js_outcome(r):
    """L: the jump_shadow record's outcome (would_send, capped, cheap_skip, no_ask, filtered, nothing_to_buy, error);
    a record without the field is read off its flags."""
    oc = (r or {}).get("outcome")
    if oc:
        return str(oc)
    if r.get("would_send"):
        return "would_send"
    if r.get("capped"):
        return "capped"
    if r.get("cheap_skip"):
        return "cheap_skip"
    return "other"


def traj_paths(pin_path):
    """M: where the trajectory log of pin log `pin_path` can be: the same folder, pinrun-live- -> pintraj-live-, as is,
    then .gz, then the other way round. NOT results\\archive\\ (where log_rotate puts a pintraj log two days after its
    last write): M's Scan.traj reads a whole file per close, so it is left on the plain file; P, whose net depends on
    the close, finds the archive through p_traj_path (logfiles.resolve) and keeps only each market's close row."""
    d, b = os.path.split(str(pin_path))
    if "pinrun-live-" not in b:
        return []
    tb = b.replace("pinrun-live-", "pintraj-live-", 1)
    plain = tb[:-3] if tb.endswith(".gz") else tb
    return [os.path.join(d, plain), os.path.join(d, plain + ".gz")]


def m_rules(start):
    """M: pin's entry rules as the start record states them (M_RULES where it does not): the numbers the judge below
    reads. late_extra_tau is the old argv's late window (every live start record since 10-30 says 15; a record that
    says nothing takes 15, pinrun's own fallback would be late_tau)."""
    st = start or {}
    out = dict(M_RULES)
    for k in out:
        if st.get(k) is not None:
            out[k] = st[k]
    if out.get("late_extra_tau") is None:
        out["late_extra_tau"] = out.get("late_tau") or 10
    return out


def m_fee1(p):
    """Kalshi's fee on one contract at p, the way pinrun bills it (ceil to $0.0001)."""
    return math.ceil(round(0.07 * p * (1.0 - p), 9) * 10000.0) / 10000.0


def m_band_mult(price, rules):
    """pinrun.band_mult: the size multiple of a price band ([lo, hi, mult]; lo <= p < hi), never under 1."""
    m = 1.0
    for b in (rules.get("band_mults") or ()):
        try:
            lo, hi, mult = float(b[0]), float(b[1]), float(b[2])
        except (TypeError, ValueError, IndexError):
            continue
        if lo <= float(price) < hi:
            m = max(m, mult)
    return m


def m_judge(rec, rules, size, coin_bought, fills, close_s):
    """M (2): would pin have bought this trajectory second had the close had one more SIZE of budget? Returns
    (n, leg, None) when yes (n = the leg's contracts capped by the book, before the room), else (0, None, why).
    The gates read off the record, in pinrun's order: no offer (ask None), confidence (our side's fair at PIN), the
    slot (a coin already bought in the close only inside late_extra_tau: pinrun.close_budget_for), both sides,
    max_per_market, the price ceiling / the 98-99c band (a tenth, nothing held), the edge floor, the EV floor (not on
    a band buy), the dump guard, the early leg's floor and edge cap (tau over tau_max), the edge cap, the cheap window
    (a first buy), the book (min_level). Gates the record cannot settle (rebuy band, spike, wrong side, fresh level)
    are not applied: counted, as the pre-registered read says."""
    ask = rec.get("ask")
    if ask is None:
        return 0, None, "no offer"
    try:
        ask = float(ask)
        f = float(rec.get("fair"))
        tau = int(rec.get("tau"))
        depth = _f(rec.get("ask_size"))
    except (TypeError, ValueError):
        return 0, None, "no offer"
    if not (0.0 < ask < 1.0):
        return 0, None, "no offer"
    want = rec.get("want") or ("yes" if f >= 0.5 else "no")
    conf = f if want == "yes" else 1.0 - f
    if conf < float(rules["pin"]):
        return 0, None, "confidence %.2f%% under the %.1f%% line" % (100 * conf, 100 * float(rules["pin"]))
    held = rec.get("held")
    if held and held != want:
        return 0, None, "the other side is held"
    if coin_bought and tau > int(rules["late_extra_tau"]):
        return 0, None, "a coin already bought this close (only the late slot, %d s or less, could take it)" % int(rules["late_extra_tau"])
    if held == want and fills >= int(rules["max_per_market"]):
        return 0, None, "the market already holds %d buys" % fills
    gross = (f - ask) if want == "yes" else ((1.0 - f) - ask)
    edge = gross - 0.07 * ask * (1.0 - ask)
    band = False
    if ask > float(rules["price_ceiling"]) + 1e-9:
        if rules.get("band99_ceiling") is None or ask > float(rules["band99_ceiling"]) + 1e-9:
            return 0, None, "ask %s over the ceiling" % _cents(ask)
        if held:
            return 0, None, "a 98-99c offer in a market already held"
        band = True
    if edge < float(rules["edge_floor"]):
        return 0, None, "edge %.2fc under the floor" % (100 * edge)
    flip = float(rules["measured_flip"])
    ev = (1.0 - flip) * (1.0 - ask) - flip * ask - m_fee1(ask)
    if ev < float(rules["ev_floor"]) and not band:
        return 0, None, "EV %.2fc under the floor" % (100 * ev)
    if gross > float(rules["dump_discount"]):
        return 0, None, "a %.0fc discount to fair (the dump guard)" % (100 * gross)
    leg, n = "full", float(size)
    if tau > int(rules["tau_max"]):
        if ask < float(rules["early_min_price"]):
            return 0, None, "an early look under %s" % _cents(rules["early_min_price"])
        if 100 * edge > float(rules["early_max_edge"]):
            return 0, None, "an early look with a %.1fc edge (over the cap)" % (100 * edge)
        leg, n = "early", float(rules["early_frac"]) * float(size)
    elif tau > int(rules["edge_cap_tau"]) and 100 * edge > float(rules["max_edge_c"]):
        return 0, None, "a %.1fc edge with %d s left (over the cap)" % (100 * edge, tau)
    w = rules.get("cheap_window")
    if not held and isinstance(w, (list, tuple)) and len(w) == 3 and cw_in_window(close_s, w) and ask < float(w[2]) - 1e-9:
        return 0, None, "the cheap window (a first buy under %s)" % _cents(w[2])
    if band:
        leg, n = "band", max(1.0, float(int(float(rules["band99_frac"]) * float(size) + 1e-9)))
    if depth < float(rules["min_level"]):
        return 0, None, "a book of %.2f" % depth
    return min(n, depth), leg, None


def _missed_cache():
    """missed.py's result cache {ticker: yes/no} (results\\missed_results_cache.json), read-only, re-read on change."""
    p = _paths.results("missed_results_cache.json")
    try:
        st = os.stat(p)
        key = (p, st.st_size, st.st_mtime_ns)
    except OSError:
        return {}
    if _MISSED["key"] != key:
        d = _paths.read_json(p)
        _MISSED["key"], _MISSED["data"] = key, (d if isinstance(d, dict) else {})
    return _MISSED["data"] or {}


def m_result(S, tk, trajs):
    """M: a market's settled side: pin's own settled record, else the trajectory's last second (tau 1 or less, fair
    at 1.0 or 0.0 to half a point), else missed.py's cache; None while unknown. Returns (result, how)."""
    res = S.result(tk)
    if res is not None:
        return res, "pin's own settled record"
    tail = [r for r in (trajs or []) if _f(r.get("tau"), 99) <= 1 and r.get("fair") is not None]
    if tail:
        f = _f(tail[-1].get("fair"))
        if f >= 0.995:
            return "yes", "the index at the close"
        if f <= 0.005:
            return "no", "the index at the close"
    c = _missed_cache().get(tk)
    if c in ("yes", "no"):
        return c, "missed.py's result cache"
    return None, None


# ---------------------------------------------------------------------------
class Scan:
    """One pass over the logs for everything the D..J scores need (pinrules_watch.Logs holds A, B, C's)."""

    WANT = ('"start"', '"settled"', '"hedge"', '"hedge_extra"', '"hedge_quote"', '"band_boost"', '"late_boost"',
            '"boost_rail_kept"', '"hedge_cheap_skip"', '"late_bypass_refused"', '"extra_stake_capped"',
            '"open_cap_relaxed"', '"order"', '"cheap_window', '"jump_shadow"', '"close_budget"', '"signal"',
            '"autosize"', '"sweep_depth"', '"band99_shadow"')
    LISTS = {"hedge": "hedges", "hedge_extra": "extras", "boost_rail_kept": "kept", "hedge_cheap_skip": "cheap",
             "late_bypass_refused": "late_bypass", "extra_stake_capped": "stake_capped", "open_cap_relaxed": "open_cap",
             "order": "orders", "jump_shadow": "shadow", "signal": "signals", "sweep_depth": "sweeps",
             "band99_shadow": "b99s"}

    def __init__(self, paths):
        self.starts = []                      # (epoch, record, path)
        self.settled = {}                     # (ticker, want) -> [settled]
        self.by_tk = {}                       # ticker -> [settled]
        self.boosts = {}                      # path -> [band_boost / late_boost]
        self.cw_ref = []                      # K: refusals with gate cheap_window (one per skipped market)
        self.cw_set = {}                      # K: ticker -> its shadow's cheap_window_settled
        self.cb_ref = []                      # M: refusals with gate close_budget (one per market per close)
        self.sizes = {}                       # M: path -> [(epoch, SIZE)] from the start record and every autosize
        self._traj = {}                       # M: (path, close_s) -> {ticker: [traj records]}
        for v in self.LISTS.values():
            setattr(self, v, [])
        seen = set()
        quote = {}
        n_line = 0
        for path in paths:
            try:
                fh = _lf.open(path, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with fh:
                for line in fh:
                    n_line += 1
                    if not any(w in line for w in self.WANT):
                        continue
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(r, dict):
                        continue
                    k = r.get("kind")
                    t = _epoch(r.get("t"))
                    if k == "start":
                        if t is not None:
                            self.starts.append((t, r, path))
                            if r.get("size") is not None:
                                self.sizes.setdefault(path, []).append((t, _f(r.get("size")), _f(r.get("series_size_now"), None)))
                        continue
                    if k == "autosize":
                        if t is not None and r.get("new") is not None:
                            self.sizes.setdefault(path, []).append((t, _f(r.get("new")), _f(r.get("series_size"), None)))
                        continue
                    tk = r.get("ticker")
                    if not tk or t is None:
                        continue
                    if k == "hedge_quote":
                        quote[(tk, r.get("side"))] = r
                        continue
                    key = (k, tk, r.get("t"), r.get("want"), r.get("side"), r.get("cost"), r.get("price"), r.get("n"),
                           r.get("client_order_id"), r.get("leg"), r.get("which"), r.get("outcome"), r.get("entry"),
                           r.get("gate"), r.get("take_n"), r.get("budget_left"), r.get("now"))
                    if key in seen:
                        continue
                    seen.add(key)
                    r["_epoch"], r["_path"], r["_i"] = t, path, n_line
                    if k == "settled":
                        self.settled.setdefault((tk, r.get("want")), []).append(r)
                        self.by_tk.setdefault(tk, []).append(r)
                    elif k in ("band_boost", "late_boost"):
                        self.boosts.setdefault(path, []).append(r)
                    elif k == "refused":
                        if r.get("gate") == "cheap_window":
                            self.cw_ref.append(r)
                        elif r.get("gate") == "close_budget":
                            self.cb_ref.append(r)
                    elif k == "cheap_window_settled":
                        self.cw_set[tk] = r
                    elif k == "hedge_cheap_skip":
                        r["_quote"] = quote.get((tk, r.get("side")))
                        self.cheap.append(r)
                    elif k in self.LISTS:
                        getattr(self, self.LISTS[k]).append(r)
        self.starts.sort(key=lambda x: x[0])
        for v in list(self.LISTS.values()):
            getattr(self, v).sort(key=lambda r: (r["_epoch"], r["_i"]))
        self.cw_ref.sort(key=lambda r: r["_epoch"])
        self.cb_ref.sort(key=lambda r: (r["_epoch"], r["_i"]))
        for v in self.boosts.values():
            v.sort(key=lambda r: r["_epoch"])
        for v in self.sizes.values():
            v.sort()

    def result(self, tk):
        for r in self.by_tk.get(tk, []):
            if r.get("result") in ("yes", "no"):
                return r["result"]
        return None

    def leg(self, tk, want, cost=None, t=None, claimed=None):
        """The settled leg of our side `want` on `tk` nearest `cost` (then nearest `t`), not yet in `claimed` (a set of
        ids, filled here); None when there is none."""
        rows = [r for r in self.settled.get((tk, want), []) if claimed is None or id(r) not in claimed]
        if not rows:
            return None
        rows.sort(key=lambda r: ((abs(_f(r.get("cost")) - _f(cost)) if cost is not None else 0.0),
                                 (abs(r["_epoch"] - float(t)) if t is not None else 0.0)))
        if claimed is not None:
            claimed.add(id(rows[0]))
        return rows[0]

    def latest_start(self):
        return self.starts[-1][1] if self.starts else {}

    def new_build_since(self):
        """D..J's start: the first start record from SINCE_C on whose code_sha is not the 0925r build's."""
        for t, r, _p in self.starts:
            sha = r.get("code_sha")
            if t >= SINCE_C and sha and sha != BASE_SHA:
                return t
        return None

    def cw_since(self):
        """K's start and window: (epoch, [start_h, end_h, floor]) of the first start record that names a
        cheap_window, else (None, None)."""
        for t, r, _p in self.starts:
            w = r.get("cheap_window")
            if isinstance(w, (list, tuple)) and len(w) == 3:
                return t, list(w)
        return None, None

    def js_since(self):
        """L's start: (epoch, start record) of the first start record with hedge_jump_shadow set (the launcher passes
        --hedge-jump-shadow; pinrun refuses it next to --hedge-jump, so the jump hedge is off there), else (None, None)."""
        for t, r, _p in self.starts:
            if r.get("hedge_jump_shadow") is not None:
                return t, r
        return None, None

    def cb_since(self):
        """M's start: (epoch, start record) of the first start record with extra_coin 0 and late_extra 0 (call B:
        --extra-coin 0 --late-extra 0; both fields are in the start record), else (None, None)."""
        for t, r, _p in self.starts:
            ec, le = _f(r.get("extra_coin"), None), _f(r.get("late_extra"), None)
            if ec == 0.0 and le == 0.0:
                return t, r
        return None, None

    def hl_since(self):
        """N's start: (epoch, start record) of the first start record whose hedge_belief is N_NEW_LINE or more (the
        launcher passes --hedge-belief 0.60; the field is pinrun's HEDGE_BELIEF), else (None, None)."""
        for t, r, _p in self.starts:
            hb = _f(r.get("hedge_belief"), None)
            if hb is not None and hb >= N_NEW_LINE - 1e-9:
                return t, r
        return None, None

    def b99_since(self):
        """P's start: (epoch, start record) of the first start record with band99_max_tau set (the launchers pass
        --band99-max-tau 30; the start record names it; None = the band as before), else (None, None)."""
        for t, r, _p in self.starts:
            if r.get("band99_max_tau") is not None:
                return t, r
        return None, None

    def size_at(self, path, t):
        """M: (SIZE, the ladder series size) in force in `path` at epoch `t` (the start record's size, then every
        autosize's new), (None, None) when the log says nothing."""
        got, ser = None, None
        for t0, s, se in self.sizes.get(path, []):
            if t0 <= float(t) + 1e-9:
                got = s
                if se is not None:
                    ser = se
        return got, ser

    def traj(self, path, close_s):
        """M: the trajectory records of one close, {ticker: [records in time order]}, read from the pintraj log with
        the same stamp as pin log `path` (results\\pintraj-live-<stamp>.jsonl, or its .gz); {} when there is none."""
        key = (path, int(close_s))
        got = self._traj.get(key)
        if got is not None:
            return got
        out = {}
        mark = '"close_s": %d' % int(close_s)
        for tp in traj_paths(path):
            try:
                fh = _lf.open(tp, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with fh:
                for line in fh:
                    if mark not in line or '"traj"' not in line:
                        continue
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(r, dict) or r.get("kind") != "traj" or not r.get("ticker"):
                        continue
                    t = _epoch(r.get("t"))
                    if t is None:
                        continue
                    r["_epoch"] = t
                    out.setdefault(r["ticker"], []).append(r)
            break
        for v in out.values():
            v.sort(key=lambda r: r["_epoch"])
        self._traj[key] = out
        return out

    def window_net(self, since, window):
        """K: pin's own settled money, every leg, on the markets closing inside `window` from `since` on, and how many
        of those markets have settled."""
        total, n = 0.0, 0
        for tk, legs in self.by_tk.items():
            c = close_of(tk)
            if c is None or c < since or not cw_in_window(c, window):
                continue
            got = [r for r in legs if r.get("result") in ("yes", "no")]
            if got:
                total += sum(_f(r.get("pnl_c")) for r in got) / 100.0
                n += 1
        return total, n


def _load(paths):
    key = []
    for p in paths:
        try:
            st = os.stat(p)
            key.append((p, st.st_size, st.st_mtime_ns))
        except OSError:
            key.append((p, None, None))
    key = tuple(key)
    got = _CACHE.get(key)
    if got is None:
        # past 8 of its own entries (each a state of pin's logs: the live log grows between asks) _load drops ITS OWN
        # entries only -- a ladder scan (key ("ladder", path)) stays, so its incremental read is never thrown away
        mine = [k for k in _CACHE if k and isinstance(k[0], tuple)]
        if len(mine) > 8:
            for k in mine:
                del _CACHE[k]
        got = _CACHE[key] = (_rw.Logs(list(paths)), Scan(list(paths)))
    return got


# ---------------------------------------------------------------------------
def _status(tk, result, now, close_s=None):
    if result is not None:
        return "scored"
    c = close_s if close_s is not None else close_of(tk)
    return "unknown" if c is not None and now > float(c) + UNKNOWN_AFTER_S else "pending"


def _event(r, words, usd, status, coin=None):
    t = r.get("_epoch") if isinstance(r, dict) else None
    if t is None:
        t = _epoch(r.get("t"))
    return {"t": r.get("t"), "epoch": t, "et": et_words(t), "coin": coin or _rw.coin_label(r.get("ticker")),
            "words": words, "usd": (round(usd, 2) if (status == "scored" and usd is not None) else None),
            "open": status != "scored"}


def _side(s):
    return str(s or "?").capitalize()


def _abc(L, now, since, cstep=None):
    """A, B, C events off pinrules_watch's own scoring, from each rule's live moment. `cstep` (_c_step's map): a 1.5x
    extra leg's C event also says what its 1.25x->1.5x step was."""
    out = {"A": [], "B": [], "C": []}
    for ev in _rw.score_events(L, now):
        rule = ev["rule"]
        t = _epoch(ev["t"])
        if t is None or t < since[rule]:
            continue
        _mk, what = _rw.describe(ev)
        v = _rw.verdict(ev)
        words = "it %s: %s" % (what, v if ev["status"] == "scored" else "not settled yet")
        if ev["status"] == "scored" and ev["rule"] == "A" and ev.get("buy") is not None:
            words += " (the buy would have %s %s)" % ("made" if ev["buy"] >= 0 else "lost", _rw.usd(abs(ev["buy"]), False))
        if rule == "C" and cstep:
            # score_events' id for an extra leg: C|ticker|want|t|order_id
            parts = str(ev.get("id") or "").split("|", 4)
            hit = cstep.get((ev["ticker"], ev["t"], parts[4] if len(parts) == 5 else "None"))
            if hit is not None and hit[0] > 1e-9:
                words += "; %s: %s of those contracts%s%s" % (C_STEP, _g2(hit[0]), (", %s" % _rw.usd(hit[1]))
                                                              if hit[1] is not None else "", hit[2] if len(hit) > 2 else "")
            elif hit is not None:
                words += "; %s: none (it filled no more than 1.25x would have)" % C_STEP
        r = {"t": ev["t"], "_epoch": t, "ticker": ev["ticker"]}
        out[rule].append(_event(r, words, ev.get("effect"), ev["status"]))
    return out


def _d(S, now, since):
    """D: each boost_rail_kept and the money of the boost legs placed after it in that run."""
    out, claimed = [], set()
    for K in S.kept:
        if K["_epoch"] < since:
            continue
        which = K.get("which") or "band"
        kind = "late_boost" if which == "late" else "band_boost"
        later = [k2["_epoch"] for k2 in S.kept if k2["_path"] == K["_path"] and (k2.get("which") or "band") == which
                 and k2["_epoch"] > K["_epoch"]]
        end = min(later) if later else float("inf")
        legs = [b for b in S.boosts.get(K["_path"], []) if b.get("kind") == kind and K["_epoch"] < b["_epoch"] <= end]
        total, scored, opened = 0.0, 0, 0
        for b in legs:
            extra = _f(b.get("now")) - _f(b.get("was"))
            if extra <= 0:
                continue
            leg = S.leg(b["ticker"], b.get("want"), b.get("price"), b["_epoch"], claimed)
            if leg is None or leg.get("result") not in ("yes", "no"):
                opened += 1
                continue
            total += _value(extra, _f(leg.get("cost"), _f(b.get("price"), 0.97)), leg["result"] == b.get("want"))
            scored += 1
        bs = K.get("boosted_side")
        bs = "/".join(bs) if isinstance(bs, (list, tuple)) else str(bs or "?")
        words = ("a losing %s leg (%s) on a market whose %s side had the %s boost: the boost stayed on, the old rule "
                 "switched it off for the run" % (_side(K.get("leg_side")), _rw.usd(_f(K.get("pnl_c")) / 100.0),
                                                  _side(bs), which))
        if K.get("rail") == "off" and str(K.get("leg_side")) in str(K.get("boosted_side")):
            words = ("a losing boosted %s leg (%s): the rail is off, so the %s boost stayed on; the old rule switched it "
                     "off for the run" % (_side(K.get("leg_side")), _rw.usd(_f(K.get("pnl_c")) / 100.0), which))
        if legs:
            words += "; %d boosted leg%s since: the extra contracts %s %s" % (
                len(legs), "" if len(legs) == 1 else "s", "made" if total >= 0 else "lost", _rw.usd(abs(total), False))
            if opened:
                words += " (%d still open)" % opened
        else:
            words += "; no boosted leg since yet"
        out.append(_event(K, words, total, "scored" if not opened else "pending"))
        if opened:
            out[-1]["usd"] = round(total, 2) if scored else None    # the settled part counts now, the rest when it settles
    return out


def _e(S, now, since):
    """E: hedges whose limit was rounded onto the grid from an off-grid legacy limit."""
    out, claimed, seen = [], set(), {}
    for h in S.hedges:
        if h["_epoch"] < since or not h.get("tick_rounded") or not off_grid(h.get("limit_legacy")):
            continue
        key = (h["ticker"], h.get("side"))
        filled = h.get("status") == "executed" and _f(h.get("n")) > 0
        if key in seen and (seen[key] or not filled):
            continue
        seen[key] = filled
        tk, side = h["ticker"], h.get("side")
        head = "the %s hedge limit %s was rounded to %s (the old build sent %s and was refused every second)" % (
            _side(side), _cents(h.get("limit_legacy")), _cents(h.get("limit_sent")), _cents(h.get("limit_legacy")))
        if not filled:
            out.append(_event(h, head + "; the order did not fill, so no money either way", 0.0, "scored"))
            continue
        res = S.result(tk)
        leg = S.leg(tk, side, h.get("price"), h["_epoch"], claimed) if res is not None else None
        st = _status(tk, res if leg is not None else None, now)
        usd = _f(leg.get("pnl_c")) / 100.0 if leg is not None else None
        words = head + "; %.0f contracts filled at %s" % (_f(h.get("n")), _cents(h.get("price")))
        if st == "scored":
            words += ": the bet %s, so this hedge leg %s %s" % ("LOST (a flip)" if res == side else "won",
                                                                 "made" if usd >= 0 else "cost", _rw.usd(abs(usd), False))
        out.append(_event(h, words, usd, st))
    return out


def _f_cheap(L, S, now, since):
    """F: each hedge_cheap_skip scored as pinrules_watch scores a capped jump hedge (score_B)."""
    out = []
    for c in S.cheap:
        if c["_epoch"] < since:
            continue
        tk = c["ticker"]
        q = c.get("_quote") or {}
        ladder = []
        for a, s in (("ask", "size"), ("ask1", "size1"), ("ask2", "size2")):
            if q.get(a) is not None and _f(q.get(s)) > 0:
                ladder.append([_f(q.get(a)), _f(q.get(s))])
        if not ladder and c.get("ask") is not None:
            ladder = [[_f(c.get("ask")), _f(c.get("n"))]]
        e = {"ticker": tk, "want": c.get("want"), "side": c.get("side"), "n": c.get("n"), "ask": c.get("ask"),
             "ask_size": (ladder[0][1] if ladder else c.get("n")), "ladder": ladder, "t": c.get("t"),
             "jump_sd": c.get("jump_sd"), "belief": c.get("belief"), "tau": c.get("tau")}
        res = S.result(tk)
        ev = _rw.score_B(L, e, res)
        st = _status(tk, res, now)
        words = "skipped a %.0f-contract %s jump hedge asking %s (bar %s, a %s sd jump, odds %.0f%% our way)" % (
            _f(c.get("n")), _side(c.get("side")), _cents(c.get("ask")), _cents(c.get("min_ask")),
            ("%.1f" % _f(c.get("jump_sd"))) if c.get("jump_sd") is not None else "?", 100 * _f(c.get("belief")))
        if st == "scored":
            if res != c.get("side"):
                words += "; the bet won, so the skip saved the premium: %s" % _rw.usd(ev["effect"])
            else:
                words += "; the bet LOST: the skipped hedge would have got back %s, pin's later hedge on those contracts " \
                         "got back %s, net %s" % (_rw.usd(_f(ev.get("jump_hedge")), False),
                                                  _rw.usd(_f(ev.get("real_hedge")), False), _rw.usd(ev["effect"]))
        out.append(_event(c, words, ev.get("effect"), st))
    return out


def _g(S, now, since):
    """G: each late_bypass_refused: the contracts the old code would have added, at the leg's price."""
    out, claimed = [], set()
    for r in S.late_bypass:
        if r["_epoch"] < since:
            continue
        tk, side = r["ticker"], r.get("side")
        fewer = _f(r.get("n_before")) - _f(r.get("n_after"))
        res = S.result(tk)
        leg = S.leg(tk, side, r.get("price"), r["_epoch"], claimed) if res is not None else None
        st = _status(tk, res if leg is not None else None, now)
        price = _f(leg.get("cost")) if leg is not None and leg.get("cost") is not None else _f(r.get("price"))
        usd = -_value(fewer, price, res == side) if st == "scored" and fewer > 0 and price > 0 else (0.0 if st == "scored" else None)
        words = "kept the last-seconds %.1fx off a %s leg at %s (%s path, %s s left): %.0f fewer contracts" % (
            _f(r.get("mult"), 1.5), _side(side), _cents(r.get("price")), r.get("path") or "?", r.get("tau"), fewer)
        if st == "scored":
            words += "; the leg %s, so that %s %s" % ("LOST" if res != side else "won", "saved" if usd >= 0 else "gave up",
                                                   _rw.usd(abs(usd), False))
        out.append(_event(r, words, usd, st))
    return out


def _h(S, now, since):
    """H: each extra_stake_capped: the trimmed contracts at the extra's price (the nearest hedge_extra, else hedge)."""
    out = []
    for r in S.stake_capped:
        if r["_epoch"] < since:
            continue
        tk, side = r["ticker"], r.get("side")
        trimmed = _f(r.get("trimmed")) if r.get("trimmed") is not None else _f(r.get("asked")) - _f(r.get("allowed"))
        price = None
        for pool in (S.extras, S.hedges):
            near = [x for x in pool if x["ticker"] == tk and x.get("side") == side and abs(x["_epoch"] - r["_epoch"]) <= 120
                    and x.get("price") is not None]
            if near:
                price = _f(min(near, key=lambda x: abs(x["_epoch"] - r["_epoch"]))["price"])
                break
        res = S.result(tk)
        st = _status(tk, res, now)
        words = "trimmed the extra %s hedge leg by %.0f contracts (asked %.0f, allowed %.0f, %s)" % (
            _side(side), trimmed, _f(r.get("asked")), _f(r.get("allowed")), str(r.get("reason") or "cap").replace("_", " "))
        if st == "scored" and price is None:
            words += "; its price is not in the log, so no $ scored"
            out.append(_event(r, words, 0.0, st))
            continue
        usd = -_value(trimmed, price, res == side) if st == "scored" else None
        if st == "scored":
            words += " at %s; the extra side %s, so that %s %s" % (_cents(price), "won" if res == side else "lost",
                                                                 "gave up" if usd < 0 else "saved", _rw.usd(abs(usd), False))
        out.append(_event(r, words, usd, st))
    return out


def _i(S, now, since):
    """I: each open_cap_relaxed: the leg it let through (its order within 30 s) and that leg's own money."""
    out, claimed = [], set()
    for r in S.open_cap:
        if r["_epoch"] < since:
            continue
        tk, side = r["ticker"], r.get("side")
        orders = [o for o in S.orders if o["ticker"] == tk and o.get("want") == side and o.get("leg") == r.get("leg")
                  and -2 <= o["_epoch"] - r["_epoch"] <= 30]
        words = "let a %s %s buy through with %s positions open (the old cap was %s)" % (
            _side(side), r.get("leg") or "?", r.get("open_positions"), r.get("old_cap", 3))
        o = min(orders, key=lambda x: abs(x["_epoch"] - r["_epoch"])) if orders else None
        if o is None or _f(o.get("filled")) <= 0:
            out.append(_event(r, words + "; nothing filled, so no money either way", 0.0, "scored"))
            continue
        cost = o.get("exec_price") if o.get("exec_price") is not None else o.get("limit_sent")
        res = S.result(tk)
        leg = S.leg(tk, side, cost, r["_epoch"], claimed) if res is not None else None
        st = _status(tk, res if leg is not None else None, now)
        usd = _f(leg.get("pnl_c")) / 100.0 if leg is not None else None
        words += "; %.0f contracts filled at %s" % (_f(o.get("filled")), _cents(cost))
        if st == "scored":
            words += ": the leg %s %s" % ("made" if usd >= 0 else "lost", _rw.usd(abs(usd), False))
        out.append(_event(r, words, usd, st))
    return out


def _j(S, now, since):
    """J: each extra leg fired on belief with another trigger label: its own money."""
    out, claimed = [], set()
    for x in S.extras:
        if x["_epoch"] < since or not x.get("fired_on_belief") or (x.get("trigger_label") or "belief") == "belief":
            continue
        if x.get("status") != "executed" or _f(x.get("n")) <= 0:
            continue
        tk, side = x["ticker"], x.get("side")
        res = S.result(tk)
        leg = S.leg(tk, side, x.get("price"), x["_epoch"], claimed) if res is not None else None
        st = _status(tk, res if leg is not None else None, now)
        usd = _f(leg.get("pnl_c")) / 100.0 if leg is not None else None
        words = "the odds line fired while the alarm said %s: bought %.0f extra %s at %s (odds %.0f%% our way)" % (
            x.get("trigger_label"), _f(x.get("n")), _side(side), _cents(x.get("price")), 100 * _f(x.get("belief")))
        if st == "scored":
            words += "; the bet %s, so the extra %s %s" % ("LOST (a flip)" if res == side else "won",
                                                          "made" if usd >= 0 else "lost", _rw.usd(abs(usd), False))
        out.append(_event(x, words, usd, st))
    return out


def _k(S, now, since):
    """K: each market the cheap window skipped, priced by its own shadow: + saved (the skipped buy would have lost), -
    gave up (it would have won). Returns (events, {won, flipped, open, without_usd})."""
    out, tally = [], {"won": 0, "flipped": 0, "open": 0, "without_usd": 0.0}
    for r in S.cw_ref:
        if r["_epoch"] < since:
            continue
        tk, side = r["ticker"], r.get("want")
        s = S.cw_set.get(tk)
        shadow = cw_shadow_usd(s, r) if s else None
        st = _status(tk, (s or {}).get("result") if shadow is not None else None, now, r.get("close_s"))
        words = "skipped a first %s buy at %s with %s s left (about %.0f contracts)" % (
            _side(side), _cents(r.get("price")), r.get("tau", "?"), cw_contracts(s, r))
        if st == "scored":
            won = s.get("result") == side
            tally["won" if won else "flipped"] += 1
            tally["without_usd"] += shadow
            hp = s.get("hedge_px")
            hedge = (" with the %s hedge pin would have bought at %s" % (_side("no" if side == "yes" else "yes"),
                                                                          _cents(hp))) if hp is not None else ""
            words += "; it %s: the buy would have %s %s%s, so the rule %s that" % (
                "WON" if won else "FLIPPED", "made" if shadow >= 0 else "lost", _rw.usd(abs(shadow), False), hedge,
                "gave up" if shadow >= 0 else "saved")
        else:
            tally["open"] += 1
        out.append(_event(r, words, (-shadow if shadow is not None else None), st))
    return out, tally


def _k_extra(S, tally, since, window):
    """K's two lines under the net: what the skipped buys would have done, and the window with and without the rule."""
    if window is None:
        return []
    span = "%s to %s ET" % (_hour(window[0]), _hour(window[1]))
    n = tally["won"] + tally["flipped"]
    w = tally["without_usd"]
    lines = ["without the rule: the %d settled skip%s would have %s %s (%d won, %d flipped, hedges in)%s" % (
        n, "" if n == 1 else "s", "made" if w >= 0 else "lost", _rw.usd(abs(w), False), tally["won"], tally["flipped"],
        (" \u00b7 %d still open" % tally["open"]) if tally["open"] else "")]
    kept, markets = S.window_net(since, window)
    lines.append("closes %s since the rule (%d settled market%s): pin made %s with it, %s without it" % (
        span, markets, "" if markets == 1 else "s", _rw.usd(kept), _rw.usd(kept + w)))
    return lines


def _l(S, now, since):
    """L: each jump_shadow with would_send (one per position: the second the jump hedge would have sent), scored as F
    scores a skipped jump hedge (pinrules_watch.score_B's method): usd = what pin's own hedges really did on those
    contracts minus what the shadow hedge would have done, so + = premium kept by not sending, - = a save missed.
    The real hedge is pin's executed hedge records of the hedge side on that ticker from the shadow's second on, up to
    the shadow's contracts, each record's contracts claimed once across a ticker's shadow events. Returns (events,
    {won, flipped, open, paid, real_paid, saved, capped, cheap}): paid = the premiums the shadow would have paid on won
    markets, real_paid = what pin's hedges really paid there, saved = what the shadow would have saved on flips."""
    out = []
    tally = {"won": 0, "flipped": 0, "open": 0, "paid": 0.0, "real_paid": 0.0, "saved": 0.0, "capped": 0, "cheap": 0,
             "net": 0.0}                       # net = the sum of the events' rounded $ (what the page's net line shows)
    claimed = {}                              # id(hedge record) -> contracts already matched to a shadow event
    for r in S.shadow:
        if r["_epoch"] < since:
            continue
        oc = js_outcome(r)
        if oc != "would_send":
            if oc == "capped":
                tally["capped"] += 1
            elif oc == "cheap_skip":
                tally["cheap"] += 1
            continue
        tk, want = r["ticker"], r.get("want")
        side = r.get("side") or ("no" if want == "yes" else "yes")
        fills = js_fills(r)
        n = _rw.got(fills)
        res = S.result(tk)
        st = _status(tk, res, now, r.get("close_s"))
        real, left = [], n
        for h in S.hedges:
            if left <= 1e-9:
                break
            if (h["ticker"] != tk or h.get("side") != side or h["_epoch"] < r["_epoch"]
                    or h.get("status") != "executed" or h.get("price") is None):
                continue
            avail = _f(h.get("n")) - claimed.get(id(h), 0.0)
            if avail <= 1e-9:
                continue
            take = min(avail, left)
            claimed[id(h)] = claimed.get(id(h), 0.0) + take
            real.append((take, _f(h.get("price"))))
            left -= take
        rn = _rw.got(real)
        words = "a %s sd jump against %s with %s s left: it would have bought %.0f %s at %s (odds %.0f%% our way); " \
                "nothing was sent" % (("%.1f" % _f(r.get("jump_sd"))) if r.get("jump_sd") is not None else "?",
                                      _side(want), r.get("tau", "?"), n, _side(side), _cents(r.get("ask")),
                                      100 * _f(r.get("belief")))
        usd = None
        if st == "scored" and fills:
            flipped = res == side
            jv = _rw.value(fills, flipped)
            rv = _rw.value(real, flipped)
            usd = rv - jv
            if flipped:
                tally["flipped"] += 1
                tally["saved"] += jv - rv
                words += "; the bet FLIPPED: it would have got back %s, pin's odds hedge %s on those contracts, so " \
                         "going without it %s %s" % (_rw.usd(jv, False),
                                                    ("really got back %s" % _rw.usd(rv, False)) if rn > 0 else "bought nothing",
                                                    "saved" if usd >= 0 else "cost", _rw.usd(abs(usd), False))
            else:
                tally["won"] += 1
                tally["paid"] += -jv
                tally["real_paid"] += -rv
                if rn > 0:
                    words += "; the bet won: it would have paid %s, pin's odds hedge really paid %s on those contracts, " \
                             "so going without it %s %s" % (_rw.usd(-jv, False), _rw.usd(-rv, False),
                                                           "kept" if usd >= 0 else "cost", _rw.usd(abs(usd), False))
                else:
                    words += "; the bet won and no hedge was needed, so that premium stayed in the bank: %s kept" % (
                        _rw.usd(-jv, False))
        elif st == "scored":
            usd = 0.0
            words += "; nothing to price (no contracts or no ask in the record)"
        else:
            tally["open"] += 1
        if usd is not None:
            tally["net"] += round(usd, 2)
        out.append(_event(r, words, usd, st))
    return out, tally


def _l_extra(tally, start):
    """L's two lines under the net: what the jump hedge would have paid (won markets) and saved (flips), so what it
    would have made had it been live, and the alarms the 8 sd cap or the 5c bar would have stopped anyway."""
    nw, nf = tally["won"], tally["flipped"]
    made = -round(tally["net"], 2)            # minus the page's net to the cent (the unrounded parts could differ by 1c)
    first = "would have paid %s in premiums on %d won market%s · would have saved %s on %d flip%s (vs the odds hedge pin " \
            "really bought)%s" % (_rw.usd(tally["paid"], False), nw, "" if nw == 1 else "s", _rw.usd(tally["saved"], False),
                                  nf, "" if nf == 1 else "s", (" · %d still open" % tally["open"]) if tally["open"] else "")
    second = "so it would have %s %s" % ("made" if made >= 0 else "lost", _rw.usd(abs(made), False))
    if tally["real_paid"] > 0.004:
        second += " (pin's odds hedge really paid %s on those won markets)" % _rw.usd(tally["real_paid"], False)
    cap, bar = (start or {}).get("hedge_jump_max"), (start or {}).get("jump_hedge_min_ask")
    second += "; not counted: %d capped (%s sd or more), %d under the %s bar" % (
        tally["capped"], ("%.0f" % _f(cap)) if cap is not None else "8", tally["cheap"],
        _cents(bar) if bar is not None else "5.0c")
    return [first, second]


_LADDER_COIN = {"KXBTCD": "KXBTC", "KXETHD": "KXETH", "KXSOLD": "KXSOL", "KXXRPD": "KXXRP", "KXDOGED": "KXDOGE",
                "KXBNBD": "KXBNB", "KXHYPED": "KXHYPE"}


def m_coin(ticker):
    """pinrun.coin_of: the coin a ticker belongs to (KXBTC15M-... and the KXBTCD ladder are both KXBTC)."""
    t = str(ticker or "")
    head = t.split("-", 1)[0]
    if head in _LADDER_COIN:
        return _LADDER_COIN[head]
    return t.split("15M", 1)[0] or None


def m_full(ticker, size, series, start):
    """M: the full bet for one market: a ladder rung (KXBTCD...) takes the series size, a --coin-size-frac coin
    (HYPE at 0.15) max(1, floor(SIZE x frac)), every other coin SIZE."""
    head = str(ticker or "").split("-", 1)[0]
    if head in _LADDER_COIN:
        return float(series) if series else float(size)
    csf = (start or {}).get("coin_size_frac") or {}
    if head in csf:
        try:
            return float(max(1, int(float(csf[head]) * float(size) + 1e-9)))
        except (TypeError, ValueError):
            return 1.0
    return float(size)


def _m_tally():
    return {"held": 0, "won": 0, "lost": 0, "open": 0, "won_usd": 0.0, "lost_usd": 0.0, "unfilled": 0, "no_room": 0,
            "no_book": 0, "closes": 0, "refused": 0, "placed": 0, "no_offer": 0, "gate": 0, "slot_full": 0,
            "t_won": 0, "t_lost": 0, "t_open": 0, "t_won_usd": 0.0, "t_lost_usd": 0.0, "t_net": 0.0}


def _m_held(S, now, since, start, rules, tally):
    """M (1): pin's own full buys the 2-bet budget held back. A signal whose budget_left was what bound the order that
    followed it (asked >= budget_left, filled whole), on a coin not yet bought in the close or inside the old late
    window, where the old argv's room (budget_left + one SIZE) would have let the sweep or the band boost add more:
    more = min(band mult x SIZE, the book under the order's limit, the old room) - asked. The bet's own settled result
    prices it: lost -> + (more x the fill price + fee, the stake not spent); won -> - (more x (1 - the limit) - fee,
    the gain not made, at the limit: a ceiling)."""
    out, claimed = [], set()
    for sg in S.signals:
        if sg["_epoch"] < since or (sg.get("leg") or "full") != "full" or sg.get("live") is False:
            continue
        tk, want = sg["ticker"], sg.get("want")
        left = _f(sg.get("budget_left"), None)
        if left is None:
            continue
        o = None
        for x in S.orders:
            if (x["ticker"] == tk and x.get("want") == want and x["_i"] > sg["_i"] and 0 <= x["_epoch"] - sg["_epoch"] <= 2
                    and id(x) not in claimed):
                o = x
                break
        if o is None:
            continue
        claimed.add(id(o))
        asked = _f((o.get("body") or {}).get("count"), None)
        if asked is None:
            asked = _f(o.get("filled"))
        filled = _f(o.get("filled"))
        if asked < left - 0.01:
            continue                                      # the budget was not what bound this buy
        if filled < asked - 0.01:
            tally["unfilled"] += 1                        # the book did not even fill what went out
            continue
        size, series = S.size_at(sg["_path"], sg["_epoch"])
        cs = close_of(tk)
        if not size or cs is None:
            continue
        before = [x for x in S.orders if _f(x.get("filled")) > 0 and x["_i"] < o["_i"] and close_of(x["ticker"]) == cs]
        new_coin = m_coin(tk) not in {m_coin(x["ticker"]) for x in before}
        tau = o.get("tau_at_send") if o.get("tau_at_send") is not None else sg.get("tau")
        late = tau is not None and int(_f(tau)) <= int(rules["late_extra_tau"])
        if not (new_coin or late):
            tally["no_room"] += 1                         # the old argv gave this one nothing more either
            continue
        price = _f(sg.get("price"), _f(o.get("exec_price")))
        limit = _f(o.get("limit_sent"), price)
        full = m_full(tk, size, series, start)
        cap = m_band_mult(price, rules) * full
        sweep = [w for w in S.sweeps if w["ticker"] == tk and w.get("t") == sg.get("t")]
        if sweep:
            avail = _f(sweep[-1].get("ladder"), None)
        else:
            lad = sg.get("ladder")
            avail = sum(_f(x[1]) for x in lad if _f(x[0]) <= limit + 1e-9) if isinstance(lad, list) else None
        if avail is None:
            tally["no_book"] += 1
            continue
        more = min(cap, avail, left + M_EXTRA * full) - asked
        if more < 1.0:
            continue                                      # the cap or the book would have stopped it anyway
        res = S.result(tk)
        st = _status(tk, res, now, cs)
        px = _f(o.get("exec_price"), price)
        words = ("a full %s buy at %s with %s s left was held to the 2-bet budget: %.0f went out (the book had %.0f under %s; "
                 "the old argv's third bet had room for %.0f more%s)" % (
                     _side(want), _cents(px), tau if tau is not None else "?", asked, avail, _cents(limit), more,
                     ", a new coin" if new_coin else ", inside the late window"))
        usd = None
        tally["held"] += 1
        if st == "scored":
            if res == want:
                usd = -_value(more, limit, True)
                tally["won"] += 1
                tally["won_usd"] += -usd
                words += "; the bet won, so holding them back gave up %s (at the %s limit: a ceiling)" % (
                    _rw.usd(abs(usd), False), _cents(limit))
            else:
                usd = -_value(more, px, False)
                tally["lost"] += 1
                tally["lost_usd"] += usd
                words += "; the bet LOST, so holding them back saved %s" % _rw.usd(abs(usd), False)
        else:
            tally["open"] += 1
            words += "; not settled yet" if st == "pending" else "; no result 3 h after the close (unknown)"
        out.append(_event(sg, words, usd, st))
    return out


def _m_third(S, now, since, start, rules, tally):
    """M (2): the true 3rd bets. Per close with close_budget refusals: one more SIZE of room; every refused market's
    trajectory seconds from its refusal to tau_min, in time order; the first that m_judge passes takes
    min(its contracts, the room), one bet a market, until the room is under a contract."""
    third = []
    by_close = {}
    for r in S.cb_ref:
        if r["_epoch"] >= since and r.get("close_s") is not None:
            by_close.setdefault((r["_path"], int(_f(r["close_s"]))), []).append(r)
    for (path, cs), refs in sorted(by_close.items(), key=lambda kv: kv[1][0]["_epoch"]):
        tally["closes"] += 1
        tally["refused"] += len(refs)
        size = _f(refs[0].get("size"), None) or _f(refs[0].get("size_now"), None)
        s_at = S.size_at(path, refs[0]["_epoch"])
        series = s_at[1]
        if not size:
            size = s_at[0]
        if not size:
            tally["gate"] += len(refs)
            continue
        room = M_EXTRA * float(size)
        trajs = S.traj(path, cs)
        buys = [o for o in S.orders if _f(o.get("filled")) > 0 and close_of(o["ticker"]) == cs]
        cands = []
        for i, r in enumerate(refs):
            for rec in trajs.get(r["ticker"], []):
                if rec["_epoch"] >= r["_epoch"] - 1e-9 and _f(rec.get("tau"), -1) >= int(rules["tau_min"]):
                    cands.append((rec["_epoch"], i, r["ticker"], rec, r))
        cands.sort(key=lambda x: (x[0], x[1]))
        taken, reasons = set(), {}
        for ep, _i, tk, rec, r in cands:
            if room < float(rules["min_level"]):
                break
            if tk in taken:
                continue
            if any(o["ticker"] == tk and o["_epoch"] >= ep for o in buys):
                continue                                  # pin itself bought this market at or after this second: that
                #                                           offer was pin's own fill, not a 3rd bet (the refusal was a re-look)
            before = [o for o in buys if o["_epoch"] <= ep]
            coins = {m_coin(o["ticker"]) for o in before}
            fills = sum(1 for o in before if o["ticker"] == tk)
            n, leg, why = m_judge(rec, rules, m_full(tk, size, series, start), m_coin(tk) in coins, fills, cs)
            if why:
                reasons.setdefault(tk, []).append(why)
                continue
            n = min(n, room)
            room -= n
            taken.add(tk)
            want = rec.get("want")
            ask = float(rec["ask"])
            conf = _f(rec.get("fair")) if want == "yes" else 1.0 - _f(rec.get("fair"))
            res, how = m_result(S, tk, trajs.get(tk))
            st = _status(tk, res, now, cs)
            words = "a 3rd bet of %.0f %s at %s with %s s left%s (fair %.2f%% our way)" % (
                n, _side(want), _cents(ask), rec.get("tau", "?"),
                {"early": ", the early leg", "band": ", a 98-99c band tenth"}.get(leg, ""), 100 * conf)
            usd = None
            if st == "scored":
                if res == want:
                    usd = -_value(n, ask, True)
                    tally["t_won"] += 1
                    tally["t_won_usd"] += -usd
                    words += "; it WON (%s): the bet would have made %s, so blocking it cost %s (a ceiling: its hedges are " \
                             "not known)" % (how, _rw.usd(abs(usd), False), _rw.usd(abs(usd), False))
                else:
                    usd = -_value(n, ask, False)
                    tally["t_lost"] += 1
                    tally["t_lost_usd"] += usd
                    words += "; it FLIPPED (%s): the bet would have lost %s, so blocking it saved %s" % (
                        how, _rw.usd(abs(usd), False), _rw.usd(abs(usd), False))
                tally["t_net"] += round(usd, 2)
            else:
                tally["t_open"] += 1
                words += "; not settled yet" if st == "pending" else "; no result 3 h after the close (unknown)"
            third.append(_event({"t": rec.get("t"), "_epoch": ep, "ticker": tk}, words, usd, st))
        tally["placed"] += len(taken)
        for r in refs:
            tk = r["ticker"]
            if tk in taken:
                continue
            seen = reasons.get(tk)
            if not seen:
                tally["slot_full" if trajs.get(tk) else "no_offer"] += 1
            elif all(w == "no offer" for w in seen):
                tally["no_offer"] += 1
            else:
                tally["gate"] += 1
    return third


def _m(S, now, since, start):
    """M: (events, third, tally); see _m_held and _m_third."""
    rules = m_rules(start)
    tally = _m_tally()
    events = _m_held(S, now, since, start, rules, tally)
    third = _m_third(S, now, since, start, rules, tally)
    return events, third, tally


def _m_extra(tally):
    """M's two lines under the net: the held-back contracts of pin's own buys (what reverting B gives back), and the
    true 3rd bet the refusals would have placed (not in the net: the old build dropped it too)."""
    t = tally
    if t["held"]:
        first = "held back: %d full buy%s cut to the 2-bet budget where the old argv had room for a 3rd; the contracts not bought " \
                "would have made %s on %d won, lost %s on %d flipped%s" % (
                    t["held"], "" if t["held"] == 1 else "s", _rw.usd(t["won_usd"], False), t["won"],
                    _rw.usd(t["lost_usd"], False), t["lost"], (" · %d open" % t["open"]) if t["open"] else "")
    else:
        first = "held back: no full buy has been cut to the 2-bet budget yet where the old argv had room for a 3rd"
    net = t["t_net"]
    second = "a true 3rd bet, NOT in the net (the old build dropped it too, at its base check): %d close%s hit the budget, %d " \
             "would have gone out (%d had no offer, %d failed a gate, %d found the slot taken), won %s on %d, lost %s on %d, so " \
             "blocking them %s %s%s; %s" % (
                 t["closes"], "" if t["closes"] == 1 else "s", t["placed"], t["no_offer"], t["gate"], t["slot_full"],
                 _rw.usd(t["t_won_usd"], False), t["t_won"], _rw.usd(t["t_lost_usd"], False), t["t_lost"],
                 "cost" if net < 0 else "saved", _rw.usd(abs(net), False),
                 (" · %d open" % t["t_open"]) if t["t_open"] else "", M_READ)
    return [first, second]


def _m_what(start):
    """M's line, off the start record that switched call B on."""
    st = start or {}
    brake = st.get("bank_brake")
    late = m_rules(st)["late_extra_tau"]
    return ("a close spends 2 bets, never a 3rd (--extra-coin 0 --late-extra 0, brake %s, the same bet size; the old argv allowed "
            "one more on a new coin or inside %d s); the net is what that held back on pin's own buys" % (
                ("%.2f" % _f(brake)) if brake is not None else "4.50", int(_f(late, 15))))


def _n_belief_our(row, our):
    """The trajectory's belief in OUR side: its fair is the probability of its `want` side."""
    fair = _f(row.get("fair"), None)
    if fair is None:
        return None
    return fair if row.get("want") == our else 1.0 - fair


def _n_hedge_ask(row, our):
    """The hedge side's ask in a trajectory row: opp_ask when the row's want is our side, else ask."""
    a = row.get("opp_ask") if row.get("want") == our else row.get("ask")
    a = _f(a, None)
    return a if a is not None and 0.0 < a < 1.0 else None


def _n_old_line(S, h, our, line=N_OLD_LINE):
    """What the OLD line would have done after hedge `h` fired: the first trajectory second after it with the model's
    belief in our side under `line` and a hedge-side ask -> (epoch, tau, ask); None when belief never got there (the
    old line would not have hedged). The trajectory log is per second inside the last 60 s of a close."""
    cs = h.get("close_s")
    if cs is None:
        cs = close_of(h["ticker"])
    if cs is None:
        return None
    rows = S.traj(h["_path"], cs).get(h["ticker"], [])
    for row in rows:
        if row["_epoch"] <= h["_epoch"]:
            continue
        b = _n_belief_our(row, our)
        if b is None or b >= line:
            continue
        a = _n_hedge_ask(row, our)
        if a is None:
            continue
        tau = row.get("tau")
        tau = int(round(float(cs) - row["_epoch"])) if tau is None else int(_f(tau))
        return row["_epoch"], tau, a
    return None


def _n(S, now, since, start):
    """N: pin's belief hedge line at 0.60 (was 0.40), priced hedge by hedge against the old line. An event is a market
    whose first executed hedge fired with belief OVER the old line (the old line had not fired yet): usd = what pin's
    hedge legs really did (every executed hedge and extra of that side on that market, at their prices) minus what the
    old line would have done (the same contracts, and its extra when 11+ s were left, at the hedge-side ask of the first
    trajectory second with belief under 0.40; nothing when belief never got there), fees in. + = the earlier hedge
    saved money (a flip caught cheaper, or a save the old line would have missed), - = premium the old line would not
    have paid (the bet recovered and won). Hedges fired at or under the old line are both lines' hedges: not counted.
    Returns (events, {flipped, won, open, saved, paid, same, never})."""
    out = []
    tally = {"flipped": 0, "won": 0, "open": 0, "saved": 0.0, "paid": 0.0, "same": 0, "never": 0, "net": 0.0}
    mult = _f((start or {}).get("hedge_odds_mult"), 1.0)
    min_tau = _f((start or {}).get("hedge_odds_min_tau"), 11.0)
    done = set()
    for h in S.hedges:
        if h["_epoch"] < since or h.get("status") != "executed" or h.get("price") is None or _f(h.get("n")) <= 0:
            continue
        tk, side = h["ticker"], h.get("side")
        key = (h["_path"], tk, side)
        if key in done:
            continue
        done.add(key)
        bel = _f(h.get("belief"), None)
        if bel is None or bel <= N_OLD_LINE + 1e-9:
            tally["same"] += 1
            continue
        our = "no" if side == "yes" else "yes"
        legs = [h2 for h2 in S.hedges if (h2["_path"], h2["ticker"], h2.get("side")) == key
                and h2.get("status") == "executed" and h2.get("price") is not None and _f(h2.get("n")) > 0]
        extras = [x for x in S.extras if (x["_path"], x["ticker"], x.get("side")) == key
                  and x.get("status") == "executed" and x.get("price") is not None and _f(x.get("n")) > 0]
        real = [(_f(x.get("n")), _f(x.get("price"))) for x in legs + extras]
        n_hedge = sum(_f(x.get("n")) for x in legs)
        old = _n_old_line(S, h, our)
        res = S.result(tk)
        st = _status(tk, res, now, h.get("close_s"))
        words = "belief %.0f%% our way with %s s left: bought %.0f %s at %s" % (
            100 * bel, h.get("tau", "?"), n_hedge, _side(side), _cents(h.get("price")))
        if old is None:
            words += "; the 0.40 line would never have fired"
            tally["never"] += 1
            cf = []
        else:
            _t40, tau40, a40 = old
            cf = [(n_hedge, a40)]
            if mult > 1.0 and tau40 >= min_tau:
                cf.append((round((mult - 1.0) * n_hedge, 2), a40))
            words += "; the 0.40 line would have bought at %s with %s s left" % (_cents(a40), tau40)
        usd = None
        if st == "scored":
            flipped = res == side
            rv = _rw.value(real, flipped)
            cv = _rw.value(cf, flipped) if cf else 0.0
            usd = rv - cv
            if flipped:
                tally["flipped"] += 1
                tally["saved"] += usd
                words += "; the bet FLIPPED: the hedge got back %s, the 0.40 line's %s, so the earlier line %s %s" % (
                    _rw.usd(rv, False), (_rw.usd(cv, False) if cf else "nothing"), "saved" if usd >= 0 else "cost",
                    _rw.usd(abs(usd), False))
            else:
                tally["won"] += 1
                tally["paid"] += -usd
                words += "; the bet won: the hedge paid %s, the 0.40 line's %s, so the earlier line %s %s" % (
                    _rw.usd(-rv, False), (_rw.usd(-cv, False) if cf else "nothing"), "cost" if usd < 0 else "kept",
                    _rw.usd(abs(usd), False))
        else:
            tally["open"] += 1
        if usd is not None:
            tally["net"] += round(usd, 2)
        out.append(_event(h, words, usd, st))
    return out, tally


def _n_extra(tally):
    """N's lines under the net: what the earlier line saved on flips and paid on recoveries, and the hedges both lines
    share (not counted)."""
    nf, nw = tally["flipped"], tally["won"]
    first = "saved %s on %d flip%s hedged earlier · paid %s on %d bet%s that recovered%s" % (
        _rw.usd(tally["saved"], False), nf, "" if nf == 1 else "s", _rw.usd(tally["paid"], False), nw,
        "" if nw == 1 else "s", (" · %d still open" % tally["open"]) if tally["open"] else "")
    second = "not counted: %d hedge%s fired at or under 0.40 (both lines the same); %d of the counted would never have " \
             "been hedged at 0.40; %s" % (tally["same"], "" if tally["same"] == 1 else "s", tally["never"], N_READ)
    return [first, second]


def _n_what(st):
    st = st or {}
    hb = _f(st.get("hedge_belief"), None)
    return ("the belief hedge fires under %s (was %s): each hedge bought between the lines is priced against what the %s "
            "line would have done at the trajectory's asks" % (
                ("%.2f" % hb) if hb is not None else "%.2f" % N_NEW_LINE, "%.2f" % N_OLD_LINE, "%.2f" % N_OLD_LINE))


# ---------------------------------------------------------------------------
# C's step (v-oddsmult15, 2026-11-14): the part of each 1.5x extra leg over what 1.25x would have bought
def _g2(x):
    """A contract count in words: 20 -> '20', 7.5 -> '7.5', 1.333 -> '1.33'."""
    return "%g" % round(float(x), 2)


def c_is_step(x):
    """True for a hedge_extra record of the 1.5x multiple (its `mult` field, pinrun's HEDGE_ODDS_MULT at the time)."""
    return abs(_f((x or {}).get("mult"), 0.0) - C_NEW_MULT) < 1e-6


def c_position(x):
    """The position an extra leg was sized on: the record's orig_n (pinrun's odds_extra(orig_n): extra_of = (mult - 1) x
    orig_n), else extra_of / (mult - 1), else base_n (the covering hedge's fill); 0.0 when none reads."""
    x = x or {}
    n = _f(x.get("orig_n"), None)
    if n is not None and n > 0:
        return n
    m, e = _f(x.get("mult"), None), _f(x.get("extra_of"), None)
    if m is not None and m > 1.0 + 1e-9 and e is not None and e > 0:
        return e / (m - 1.0)
    return max(0.0, _f(x.get("base_n")))


def c_step_n(x):
    """The step's contracts: max(0, filled - (1.25 - 1) x the position) -- what the leg filled past the old share."""
    return max(0.0, _f((x or {}).get("n")) - (C_OLD_MULT - 1.0) * c_position(x))


def c_step_limit(x):
    """The most the leg was allowed to pay a contract: its order's limit_sent (pinrun logs it on every live hedge_extra),
    never under the leg's own average price (a buy fills at or under its limit; the dearer of the two is kept should a
    record disagree), or None when the record has no usable limit."""
    x = x or {}
    lim = _f(x.get("limit_sent"), None)
    if lim is None or not 0.0 < lim < 1.0:
        return None
    avg = _f(x.get("price"), None)
    return max(lim, avg) if avg is not None and 0.0 < avg < 1.0 else lim


def c_step_priced(x, step):
    """The step's fills [(n, price)] and how they were priced: "fills" = the leg's MOST EXPENSIVE fills when the record
    lists them (a `fills` list of [n, p] or {"n"/"count", "price"/"p"}; the step is the last part a bigger order walks
    into); "limit" = without a list (real hedge_extra records carry only the average `price`, and the step is the
    deepest, dearest part of the leg, so the average would flatter it), the step's contracts at the order's limit_sent,
    the most it allowed itself to pay -- never better than reality, a conservative bound (a listed fills total short of
    the step has its rest priced so too); None = no fills list covering the step and no limit: ([], None), NOT priced
    (never read as $0)."""
    rows = []
    for f in (x or {}).get("fills") or []:
        if isinstance(f, dict):
            n, p = f.get("n", f.get("count")), f.get("price", f.get("p"))
        elif isinstance(f, (list, tuple)) and len(f) >= 2:
            n, p = f[0], f[1]
        else:
            continue
        n, p = _f(n, None), _f(p, None)
        if n is not None and n > 0 and p is not None and 0.0 < p < 1.0:
            rows.append((p, n))
    if step <= 1e-9:
        return [], None
    out, left = [], float(step)
    for p, n in sorted(rows, reverse=True):
        if left <= 1e-9:
            break
        g = min(n, left)
        out.append((g, p))
        left -= g
    if left <= 1e-9:
        return out, "fills"
    lim = c_step_limit(x)
    if lim is None:
        return [], None
    return out + [(left, lim)], "limit"


def c_step_fills(x, step):
    """The step's fills [(n, price)] (c_step_priced without the basis): the dearest listed fills, else the limit; []
    when neither prices it."""
    return c_step_priced(x, step)[0]


def c_step_since(S):
    """The step's start: the first start record (from SINCE_C on) with hedge_odds_mult 1.5 or more, else the first 1.5x
    extra leg's time, else None (C then has no line under its total)."""
    for t, r, _p in S.starts:
        m = _f(r.get("hedge_odds_mult"), None)
        if t >= SINCE_C and m is not None and m >= C_NEW_MULT - 1e-9:
            return t
    legs = [x["_epoch"] for x in S.extras if c_is_step(x)]
    return min(legs) if legs else None


def _c_step(S, now):
    """C's step over every 1.5x extra leg that filled -> ({(ticker, t, order_id): (step contracts, usd or None, a note
    for the words)} for C's event words, C's line under its total or None). usd = the step's fills at the result, fee in (score_C's
    pinrules_watch.value): + when the hedge side won (a flip: the extra contracts paid), - when the bet won. A leg with
    no per-fill list is priced at its limit (c_step_priced: a conservative bound, counted in `limit` and said on the
    line); a leg neither prices is counted `unpriced` and said on the line, never added as $0."""
    since = c_step_since(S)
    if since is None:
        return {}, None
    t = {"fires": 0, "n": 0.0, "usd": 0.0, "flips": 0, "won": 0, "open": 0, "zero": 0, "limit": 0, "unpriced": 0}
    keys = {}
    for x in S.extras:
        if (not c_is_step(x) or x["_epoch"] < SINCE_C or x.get("status") != "executed" or _f(x.get("n")) <= 0):
            continue
        key = (x["ticker"], x.get("t"), str(x.get("order_id")))
        step = c_step_n(x)
        if step <= 1e-9:
            t["zero"] += 1                    # the book (or the stake cap) let it fill no more than 1.25x would have
            keys[key] = (0.0, 0.0, "")
            continue
        res = S.result(x["ticker"])
        if _status(x["ticker"], res, now, x.get("close_s")) != "scored":
            t["open"] += 1
            keys[key] = (step, None, "")
            continue
        flip = res == x.get("side")
        fills, basis = c_step_priced(x, step)
        if basis is None:
            t["unpriced"] += 1                # no fills list and no limit on the record: said on the line, not $0
            keys[key] = (step, None, ", NOT PRICED (no fills or limit on the record)")
            continue
        if basis == "limit":
            t["limit"] += 1
        usd = round(_rw.value(fills, flip), 2)
        t["fires"] += 1
        t["n"] += step
        t["usd"] += usd
        t["flips" if flip else "won"] += 1
        keys[key] = (step, usd, " at the limit" if basis == "limit" else "")
    return keys, _c_step_line(t, since)


def _c_step_line(t, since):
    """C's line under its total: 'of which the 1.25x->1.5x step: +$Y on Z fires (...)'; none yet reads so. The fires
    priced at their order's limit (no per-fill prices on the record) are said so, as are any it could not price."""
    if not (t["fires"] or t["open"] or t["zero"] or t.get("unpriced")):
        return "of which %s: none yet (no 1.5x extra leg has filled since %s)" % (C_STEP, et_words(since))
    line = "of which %s: %s on %d fire%s" % (C_STEP, _rw.usd(round(t["usd"], 2)), t["fires"], "" if t["fires"] == 1 else "s")
    if t.get("limit"):                        # first, so a line cut short on the phone still says it
        line += ", %s at the limit, a conservative bound" % (
            "priced" if t["limit"] == t["fires"] else "%d priced" % t["limit"])
    if t.get("unpriced"):
        line += ", %d more NOT PRICED (no fills or limit on the record)" % t["unpriced"]
    if t["fires"]:
        line += " (%s contracts over the 1.25x share: %d flip%s it paid on, %d won bet%s it cost)" % (
            _g2(t["n"]), t["flips"], "" if t["flips"] == 1 else "s", t["won"], "" if t["won"] == 1 else "s")
    if t["zero"]:
        line += " · %d filled no more than 1.25x would have" % t["zero"]
    if t["open"]:
        line += " · %d open" % t["open"]
    return line


# ---------------------------------------------------------------------------
# P (v-0925x band99late, 2026-11-14): each band leg skipped for being too early, against never changing it
def p_given_up(r, won):
    """P (a): what the skipped band leg of band99_shadow `r` would have made at its market's result, fee in
    (pinrules_watch.value): n x (1 - ask) - fee when its side won (`won`), -(n x ask) - fee when it lost, at the ask the
    record saw (the cheapest it could have paid: a won leg's gain and a lost leg's stake both read so, so the rule is
    never flattered either way). A loss counts less the P_HEDGE_BACK share pin's hedges win back on a band loss (the
    11-14 band99 read); a won leg's hedges are not known (counted as none). Returns (net, gross); (0.0, 0.0) when the
    record has no contracts or no usable ask."""
    n, ask = _f((r or {}).get("n")), _f((r or {}).get("ask"), None)
    if n <= 0 or ask is None or not 0.0 < ask < 1.0:
        return 0.0, 0.0
    gross = _value(n, ask, bool(won))
    return (gross if won else gross * (1.0 - P_HEDGE_BACK)), gross


def p_early(r):
    """True when the skipped band leg would have been the market's early leg: the record's leg, else tau over 30 s."""
    leg = (r or {}).get("leg")
    return (leg == "early") if leg else _f((r or {}).get("tau"), 0.0) > 30


def p_blocked(orders, r, max_per_market=2):
    """P (b): pin's own legs (`orders`: the market's order records in time order) that the skipped band leg of `r` would
    have blocked, [(order, why)]. The old code placed that leg at r's second: one fill, and the market's early leg when
    p_early(r). After it, in pinrun's order of the gates, each filled order of the market from r's second on is
    refused early_once (an early leg: one a market), max_per_market (it would be the market's 3rd fill counting the
    band leg; a blocked leg is no fill) or band99_held (a later band leg: the band leg would have held the market);
    any other leg is a fill as before. [] when the record would have bought nothing (n 0)."""
    if _f((r or {}).get("n")) <= 0:
        return []
    out, fills, early = [], 1, p_early(r)
    for o in orders:
        if o["_epoch"] < r["_epoch"] or _f(o.get("filled")) <= 0:
            continue
        if early and (o.get("leg") or "full") == "early":
            out.append((o, "early_once"))
        elif fills >= int(max_per_market):
            out.append((o, "max_per_market"))
        elif o.get("band99"):
            out.append((o, "band99_held"))
        else:
            fills += 1
    return out


def _p_book(S, tk, orders):
    """P: market `tk`'s money book for pricing pin's legs: each filled order's settled leg (S.leg, claimed once), the
    contracts filled by side, the hedge money by side (every settled leg of the market no order claims) and how many of
    those have settled, and a check that every executed hedge of a side has (hedges_in(side)). Returns (legs by id(order),
    n_side, hedge, hedges_in)."""
    claimed, legs, n_side = set(), {}, {}
    for o in orders:
        if _f(o.get("filled")) <= 0:
            continue
        cost = o.get("exec_price") if o.get("exec_price") is not None else o.get("limit_sent")
        legs[id(o)] = S.leg(tk, o.get("want"), cost, o["_epoch"], claimed)
        n_side[o.get("want")] = n_side.get(o.get("want"), 0.0) + _f(o.get("filled"))
    hedge, settled_n = {}, {}
    for x in S.by_tk.get(tk, []):
        if id(x) in claimed or x.get("result") not in ("yes", "no"):
            continue
        hedge[x.get("want")] = hedge.get(x.get("want"), 0.0) + _f(x.get("pnl_c")) / 100.0
        settled_n[x.get("want")] = settled_n.get(x.get("want"), 0) + 1

    def hedges_in(hs):
        sent = sum(1 for h in S.hedges + S.extras if h["ticker"] == tk and h.get("side") == hs
                   and h.get("status") == "executed" and _f(h.get("n")) > 0)
        return settled_n.get(hs, 0) >= sent
    return legs, n_side, hedge, hedges_in


def _p_share(n_side, hedge, side, n):
    """The hedge money of `n` contracts of our `side`: the other side's hedge money x n / our side's contracts."""
    hs = "no" if side == "yes" else "yes"
    return hedge.get(hs, 0.0) * float(n) / n_side[side] if n_side.get(side) else 0.0


def p_gained(S, tk, orders, blocked):
    """P (b): the real money of the blocked legs [(order, why)] in market `tk`: each leg's own settled pnl (S.leg, fee
    in) plus its contracts' share of the market's hedge money (every settled leg of the market no order claims, by
    side: the hedge side of a leg is the other one). Returns (usd, [(order, why, usd or None)], how many legs or hedges
    have not settled yet)."""
    if not blocked:
        return 0.0, [], 0
    legs, n_side, hedge, hedges_in = _p_book(S, tk, orders)
    total, parts, wait = 0.0, [], 0
    for o, why in blocked:
        side = o.get("want")
        leg = legs.get(id(o))
        if leg is None or leg.get("result") not in ("yes", "no") or not hedges_in("no" if side == "yes" else "yes"):
            wait += 1
            parts.append((o, why, None))
            continue
        usd = _f(leg.get("pnl_c")) / 100.0 + _p_share(n_side, hedge, side, _f(o.get("filled")))
        total += usd
        parts.append((o, why, usd))
    return total, parts, wait


def p_topup(orders, r, blocked, start=None):
    """P: the top-up after an early leg the band leg of `r` would have blocked (early_once; see the module note). The
    real top-up completed the position to the full bet: pinrun.staged_take, min(take_n, full x the multiple -
    early_held), the multiple the larger of the top-up price's band multiple and the late multiple (inside late_tau),
    and doubt's when that is on; the old code's top-up would have completed it from the band leg's contracts B instead
    of the early leg's E. Returns None when there is nothing to price (no early leg blocked, or no top-up of pin's after
    it the band leg leaves alone), else {"order": the real top-up, "n": E - B (what the old code's would have bought
    more; negative: fewer), "full": the full bet x the multiple, "at_full": True only when the real top-up, on the band
    leg's side, filled exactly the full size less early_held (then the old one is known: the E - B more; any other
    top-up, cut by the book or the price, cannot say how much more the old one would have filled)}."""
    early = [o for o, why in blocked if why == "early_once"]
    if not early:
        return None
    gone = {id(o) for o, _w in blocked}
    e0 = early[0]
    top = next((o for o in orders if o["_epoch"] >= e0["_epoch"] and id(o) not in gone and _f(o.get("filled")) > 0
                and o.get("leg") == "topup"), None)
    if top is None:
        return None
    side = r.get("want") or r.get("side")
    eh = _f(top.get("early_held"), None)
    if eh is None:
        eh = sum(_f(o.get("filled")) for o in early if o.get("want") == top.get("want"))
    st = start or {}
    tau = _f(top.get("tau_at_send") if top.get("tau_at_send") is not None else top.get("tau"), 99.0)
    late = _f(st.get("late_mult"), 1.0) if tau <= _f(st.get("late_tau"), 10.0) else 1.0
    px = _f(top.get("ask_seen"), _f(top.get("exec_price"), 0.0))
    mult = max(1.0, m_band_mult(px, m_rules(st)), late)
    full = _f(r.get("full"), None)
    at_full = False
    if full and top.get("want") == side and e0.get("want") == side:
        for m in {mult, max(mult, _f(st.get("doubt_mult"), 1.0))}:
            if abs(_f(top.get("filled")) + eh - full * m) <= P_TOPUP_TOL:
                at_full, mult = True, m
                break
    return {"order": top, "n": round(eh - _f(r.get("n")), 2), "early_held": eh, "full": (full * mult) if full else None,
            "at_full": at_full}


def p_topup_usd(S, tk, orders, tp, res):
    """P: what the old code's bigger top-up would have made on top of pin's real one (tp: p_topup, at_full): its E - B
    contracts at the real top-up's price (exec_price, else the limit) and the market's result `res`, fee in
    (pinrules_watch.value), with their contracts' share of the market's hedges as a blocked leg's; a negative E - B is
    what the old one would NOT have bought (the sign flips). None while the hedges of the top-up's side have not all
    settled."""
    o = tp["order"]
    side = o.get("want")
    _legs, n_side, hedge, hedges_in = _p_book(S, tk, orders)
    if not hedges_in("no" if side == "yes" else "yes"):
        return None
    n = abs(_f(tp["n"]))
    if n <= 0:
        return 0.0
    px = o.get("exec_price") if o.get("exec_price") is not None else o.get("limit_sent")
    usd = _value(n, _f(px), res == side) + _p_share(n_side, hedge, side, n)
    return usd if tp["n"] > 0 else -usd


def _line_t(ln):
    m = _LINE_T.search(ln)
    return _epoch(m.group(1).decode("ascii", "replace")) if m else None


def traj_close_rows(tp, close_s, pad=5.0):
    """P: {ticker: [trajectory rows at tau 1 or less]} of the markets closing at `close_s` in the plain pintraj log `tp`,
    found by a binary search on the file's time order (pinrun appends one record a second a market, in time order) and
    then only the seconds around the close are read: the log runs ~50 MB a day and P asks one close at a time, so a
    whole read per close would be gigabytes a /fixes. {} when the file or the rows are not there, and for an archive (a
    gzip stream cannot be searched by offset: p_traj reads one through traj_gz_rows)."""
    out = {}
    if _lf.is_gz(tp):
        return out
    try:
        fh = _lf.open(tp, "rb")                           # the builtin open for a plain file (logfiles.open)
    except OSError:
        return out
    with fh:
        try:
            lo, hi = 0, os.fstat(fh.fileno()).st_size
            target, end = float(close_s) - pad, float(close_s) + pad
            while hi - lo > (1 << 16):
                mid = (lo + hi) // 2
                fh.seek(mid)
                fh.readline()                     # the rest of the line the seek landed in
                t = None
                for _k in range(64):
                    ln = fh.readline()
                    if not ln:
                        break
                    t = _line_t(ln)
                    if t is not None:
                        break
                if t is None or t >= target:
                    hi = mid
                else:
                    lo = mid
            fh.seek(lo)
            if lo:
                fh.readline()
            mark = b'"close_s": %d' % int(close_s)
            for ln in fh:
                t = _line_t(ln)
                if t is not None and t > end:
                    break
                if mark not in ln or b'"traj"' not in ln:
                    continue
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if (isinstance(r, dict) and r.get("kind") == "traj" and r.get("ticker")
                        and _f(r.get("tau"), 99.0) <= 1):
                    out.setdefault(r["ticker"], []).append(r)
        except (OSError, ValueError, OverflowError):
            return out
    return out


def p_traj_path(pin_path):
    """P: where the trajectory log of pin log `pin_path` is NOW (logfiles.resolve): results\\pintraj-live-<stamp>.jsonl
    while it is plain, results\\archive\\pintraj-live-<stamp>.jsonl.gz once log_rotate has moved it (two days after its
    last write), None when neither is there. The results folder is the pin log's own, or its parent when the pin log is
    itself archived (results\\archive\\pinrun-live-<stamp>.jsonl.gz, 60 days on)."""
    d, b = os.path.split(str(pin_path or ""))
    if "pinrun-live-" not in b:
        return None
    name = _lf.log_name(b).replace("pinrun-live-", "pintraj-live-", 1)
    results = os.path.dirname(d) if os.path.basename(d).lower() == _lf.ARCHIVE else d
    return _lf.resolve(results, name)


def traj_gz_rows(tp, keys):
    """P: {(ticker, close_s): [its last row at tau 1 or less, tau and fair only] or []} of an archived (.gz) trajectory
    log for at least `keys` [(ticker, close_s)]. Kept in _P_CLOSES by the archive's path, size and mtime -- never in
    _CACHE, which _load clears -- so the archive is read through (a gzip stream cannot be searched) only for keys not
    looked up yet: once for the shadow markets of its run, not once a report; only those keys' last close row is kept,
    never the trajectory. {} when the file is not there."""
    try:
        st = os.stat(tp)
    except OSError:
        return {}
    fk = (tp, st.st_size, st.st_mtime_ns)
    got = _P_CLOSES.get(fk)
    if got is None:
        for k in [k for k in _P_CLOSES if k[0] == tp]:    # an older state of the same file (an archive never changes)
            del _P_CLOSES[k]
        got = _P_CLOSES[fk] = {}
    miss = {(str(t), int(_f(c))) for t, c in keys} - set(got)
    if not miss:
        return got
    found = {}
    try:
        fh = _lf.open(tp, encoding="utf-8", errors="replace")
    except OSError:
        return got                                      # not read: nothing recorded, asked again next time
    try:
        with fh:
            for line in fh:
                if '"traj"' not in line or not _TAU01.search(line):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not (isinstance(r, dict) and r.get("kind") == "traj" and r.get("ticker")
                        and r.get("close_s") is not None and r.get("fair") is not None and _f(r.get("tau"), 99.0) <= 1):
                    continue
                k = (r["ticker"], int(_f(r["close_s"])))
                if k in miss:
                    found[k] = {"tau": r.get("tau"), "fair": r.get("fair")}     # the file's order: the last row wins
    except (OSError, EOFError):
        pass                                            # a damaged archive: what was read counts, the rest has no row
    for k in miss:
        got[k] = [found[k]] if k in found else []
    return got


def p_traj(r, memo):
    """P: the trajectory rows at the close of band99_shadow `r`'s market, from r's run's pintraj log wherever it is
    (p_traj_path): the plain file by binary search, memo'd per close for one report; an archive through traj_gz_rows,
    asked for every shadow market of r's run at once (memo["want"][r's pin log]). [] when there are none."""
    tk, cs = r.get("ticker"), r.get("close_s")
    if cs is None:
        cs = close_of(tk)
    if cs is None:
        return []
    cs = int(_f(cs))
    for _try in (0, 1):
        tp = p_traj_path(r.get("_path"))
        if tp is None:
            return []
        if _lf.is_gz(tp):
            keys = set((memo.get("want") or {}).get(r.get("_path")) or ()) | {(tk, cs)}
            return traj_gz_rows(tp, keys).get((tk, cs), [])
        k = (tp, cs)
        if k not in memo:
            memo[k] = traj_close_rows(tp, cs)
        if memo[k] or os.path.exists(tp):
            return memo[k].get(tk, [])
        del memo[k]                                     # archived between the look and the read: once more, from there
    return []


def p_result(S, r, now, memo):
    """P: (result, how) of band99_shadow `r`'s market: pin's own settled record, else (once it has closed) the
    trajectory's last second, else missed.py's cache (m_result); (None, None) while unknown."""
    tk = r.get("ticker")
    res = S.result(tk)
    if res is not None:
        return res, "pin's own settled record"
    cs = r.get("close_s") if r.get("close_s") is not None else close_of(tk)
    if cs is None or float(now) < float(cs):
        return None, None
    return m_result(S, tk, p_traj(r, memo))


def _p_leg_words(o, why, mpm):
    lead = {"early_once": "pin's own early %s leg", "max_per_market": "pin's %s leg",
            "band99_held": "pin's own band %s leg"}[why] % _side(o.get("want"))
    tail = {"early_once": "the band leg would have been the market's early leg",
            "max_per_market": "a 3rd fill counting the band leg (%d a market)" % int(mpm),
            "band99_held": "the band leg would have held the market"}[why]
    tau = o.get("tau_at_send") if o.get("tau_at_send") is not None else o.get("tau")
    px = o.get("exec_price") if o.get("exec_price") is not None else o.get("limit_sent")
    return "%s at %s s (%s at %s: %s)" % (lead, tau if tau is not None else "?", _g2(_f(o.get("filled"))), _cents(px),
                                          tail)


def _p(S, now, since, start):
    """P: each band99_shadow from `since` on, one a market (the first; a restart may write another), scored against
    never changing it: usd = p_gained - (p_given_up's net + p_topup_usd when pin's top-up after a blocked early leg
    filled the full bet; each rounded to the cent first, so the line's three figures add up), + = the rule made money.
    Open until the market's result is known and every blocked leg (and its hedges) has settled. Returns (events,
    tally)."""
    t = {"won": 0, "lost": 0, "open": 0, "x": 0.0, "x_gross": 0.0, "y": 0.0, "net": 0.0, "nothing": 0,
         "early_once": 0, "max_per_market": 0, "band99_held": 0, "top_n": 0, "top_usd": 0.0, "top_not": 0}
    mpm = int(_f((start or {}).get("max_per_market"), 2.0) or 2)
    by_tk = {}
    for o in S.orders:
        by_tk.setdefault(o["ticker"], []).append(o)
    picked, seen = [], set()
    for r in S.b99s:
        if r["_epoch"] < since or r.get("live") is False or r["ticker"] in seen:
            continue
        seen.add(r["ticker"])
        picked.append(r)
    # every shadow market of a run, asked of its trajectory at once (an archive is read through once for all of them)
    want = {}
    for r in picked:
        cs = r.get("close_s") if r.get("close_s") is not None else close_of(r["ticker"])
        if cs is not None:
            want.setdefault(r.get("_path"), set()).add((r["ticker"], int(_f(cs))))
    out, memo = [], {"want": want}
    for r in picked:
        tk = r["ticker"]
        side = r.get("want") or r.get("side")
        cs = r.get("close_s") if r.get("close_s") is not None else close_of(tk)
        orders = by_tk.get(tk, [])
        blocked = p_blocked(orders, r, mpm)
        words = "an early band bet skipped: %s %s at %s with %s s left%s" % (
            _g2(_f(r.get("n"))), _side(side), _cents(_f(r.get("ask"), None)), r.get("tau", "?"),
            " (it would have been the market's early leg)" if p_early(r) else "")
        if _f(r.get("n")) <= 0 or _f(r.get("ask"), None) is None:
            t["nothing"] += 1
            out.append(_event(r, words + "; it would have bought nothing (no contracts or no ask in the record): no "
                                          "money either way", 0.0, "scored"))
            continue
        for _o, why in blocked:
            t[why] += 1
        if blocked:
            words += "; it would have blocked %s" % "; ".join(_p_leg_words(o, why, mpm) for o, why in blocked)
        else:
            words += "; it would have blocked none of pin's own bets"
        tp = p_topup(orders, r, blocked, start)
        if tp is not None:
            to = tp["order"]
            tau = to.get("tau_at_send") if to.get("tau_at_send") is not None else to.get("tau")
            px = to.get("exec_price") if to.get("exec_price") is not None else to.get("limit_sent")
            if tp["at_full"]:
                words += ("; pin's top-up at %s s (%s at %s) filled the full bet, so the old code's would have bought %s "
                          "%s (%s early less %s band)" % (
                              tau if tau is not None else "?", _g2(_f(to.get("filled"))), _cents(px),
                              _g2(abs(tp["n"])), "more" if tp["n"] >= 0 else "fewer", _g2(tp["early_held"]),
                              _g2(_f(r.get("n")))))
            else:
                words += ("; pin's top-up at %s s (%s at %s) was not at the full bet: how much more the old "
                          "code's would have bought is not counted" % (
                              tau if tau is not None else "?", _g2(_f(to.get("filled"))), _cents(px)))
        res, how = p_result(S, r, now, memo)
        gained, _parts, wait = p_gained(S, tk, orders, blocked)
        top_usd = None
        if tp is not None and tp["at_full"] and res is not None:
            top_usd = p_topup_usd(S, tk, orders, tp, res)
            if top_usd is None:
                wait += 1
        st = _status(tk, res if (res is not None and not wait) else None, now, cs)
        usd = None
        if st == "scored":
            won = res == side
            x, gross = p_given_up(r, won)
            top = round(top_usd, 2) if top_usd is not None else 0.0
            x, gross, y = round(x, 2) + top, round(gross, 2) + top, round(gained, 2)
            usd = y - x
            t["won" if won else "lost"] += 1
            t["x"] += x
            t["x_gross"] += gross
            t["y"] += y
            t["net"] += usd
            if tp is not None:
                if tp["at_full"]:
                    t["top_n"] += 1
                    t["top_usd"] += top
                else:
                    t["top_not"] += 1
            if won:
                words += "; it WON (%s): it would have made %s" % (how, _rw.usd(x - top, False))
            else:
                words += "; it LOST (%s): it would have lost %s, %s after pin's hedges win back %d%%" % (
                    how, _rw.usd(abs(gross - top), False), _rw.usd(abs(x - top), False), int(round(100 * P_HEDGE_BACK)))
            if top_usd is not None:
                words += "; the old code's top-up (%s %s) adds %s to that, hedges in" % (
                    _g2(abs(tp["n"])), "more" if tp["n"] >= 0 else "fewer", _rw.usd(top))
            if blocked:
                words += "; pin's blocked bets %s %s with their hedges" % ("made" if y >= 0 else "lost",
                                                                         _rw.usd(abs(y), False))
            words += "; so the rule %s %s" % ("made" if usd >= 0 else "cost", _rw.usd(abs(usd), False))
        else:
            t["open"] += 1
            words += "; not settled yet" if st == "pending" else "; no result 3 h after the close (unknown)"
        out.append(_event(r, words, usd, st))
    return out, t


def _p_extra(t, since):
    """P's lines under its net: 'net $Z: the early band bets skipped would have made $X (W won, L lost); pin's own bets
    they would have blocked made $Y' -- the NET FIRST, so the phone's 120-char cut never hides it ('early band bets
    skipped: none yet since <date>' before any) -- then the gross before the 41% (P_HEDGE_BACK), the blocked legs by kind
    and, by the early legs, the old code's top-ups after them: priced (their $ is in X and the gross) or not at the full
    bet (not counted)."""
    s = et_words(since)
    n = t["won"] + t["lost"]
    if not n and not t["nothing"]:
        line = "%s: none %syet since %s" % (P_HEAD, "settled " if t["open"] else "", s)
        return [line + ((" · %d open" % t["open"]) if t["open"] else "")]
    x, y, z = round(t["x"], 2), round(t["y"], 2), round(t["net"], 2)
    line = "net %s: the %s would have %s %s (%d won, %d lost); pin's own bets they would have blocked %s %s" % (
        _rw.usd(z), P_HEAD, "made" if x >= 0 else "lost", _rw.usd(abs(x), False), t["won"], t["lost"],
        "made" if y >= 0 else "lost", _rw.usd(abs(y), False))
    if t["open"]:
        line += " · %d open" % t["open"]
    g = round(t["x_gross"], 2)
    tops = ""
    if t["top_n"] or t["top_not"]:                       # the old code's top-up after a blocked early leg (p_topup)
        tops = " (top-ups: %s)" % ", ".join(
            ([("%d priced %s" % (t["top_n"], _rw.usd(round(t["top_usd"], 2))))] if t["top_n"] else [])
            + ([("%d not at the full bet: not counted" % t["top_not"])] if t["top_not"] else []))
    second = ("gross, before pin's hedges win back %d%% of a band loss: they would have %s %s; blocked: %d early leg%s%s, "
              "%d 3rd fill%s, %d later band leg%s" % (
                  int(round(100 * P_HEDGE_BACK)), "made" if g >= 0 else "lost", _rw.usd(abs(g), False),
                  t["early_once"], "" if t["early_once"] == 1 else "s", tops, t["max_per_market"],
                  "" if t["max_per_market"] == 1 else "s", t["band99_held"], "" if t["band99_held"] == 1 else "s"))
    return [line, second]


def _p_what(st):
    """P's line, off the start record that switched it on (30 s when it says nothing)."""
    mt = (st or {}).get("band99_max_tau")
    return ("the band99 leg (a tenth of the bet at up to 99c) only with %s s or less left; each earlier one skipped is "
            "priced by what it would have made and the bets of pin's it would have blocked" % (
                ("%d" % int(_f(mt))) if mt is not None else "30"))


# ---------------------------------------------------------------------------
# O (v-ladder-rail100, 2026-11-14): the ladder's bids the old 82% rail would have refused, priced by their markets
def ladder_paths():
    """The ladder's order log in RESULTS (results\\ladder-live-orders.jsonl) as a list, [] when it is not there."""
    p = _paths.results(O_LOG)
    return [p] if os.path.exists(p) else []


def is_ladder_log(p):
    """True for a ladder order log's path (ladder-live-orders*.jsonl), which report() reads for O, never as pin's."""
    return os.path.basename(str(p)).lower().startswith("ladder-live-orders")


class LadderScan:
    """O: what change O reads from one ladder order log (ladder_live.py's Broker log: one ever-growing file that
    log_rotate leaves alone, 26 MB on 11-14 at ~1,500 records a day): its start records, every live_fill and
    live_settle, and the 'placed' records marked over_82. Kept between calls (in _CACHE) and brought up to date by
    parsing only the bytes the log grew by; a log that shrank, or whose first or last kept bytes changed, is read
    afresh. Lines are picked by their text before any JSON is parsed (the log is ~95% placed / cancelled / live_market)."""

    MARK = 256
    CHUNK = 4 << 20                           # read 4 MB at a time (the first read of the server's log is all of it)
    TOKENS = (b'"live_fill"', b'"live_settle"', b'"start"', b'"day_stop_reset"')    # the last: Q's midnight resets

    def __init__(self, path):
        self.path = path
        self.reset()

    def reset(self):
        self.pos, self.head, self.mark = 0, b"", b""
        self.starts, self.fills, self.settles, self.placed82, self.resets = [], [], [], [], []

    def _kept(self, fh, size):
        if size < self.pos:
            return False
        fh.seek(0)
        if fh.read(len(self.head)) != self.head:
            return False
        fh.seek(self.pos - len(self.mark))
        return fh.read(len(self.mark)) == self.mark

    def update(self):
        try:
            fh = open(self.path, "rb")
        except OSError:
            return self
        try:
            with fh:
                size = os.fstat(fh.fileno()).st_size
                if self.pos and not self._kept(fh, size):
                    self.reset()
                fh.seek(self.pos)
                while self.pos < size:
                    raw = fh.read(min(self.CHUNK, size - self.pos))
                    cut = raw.rfind(b"\n") + 1    # the last line, until its newline arrives, waits for the next call
                    if not cut:
                        break
                    for ln in raw[:cut].split(b"\n"):
                        self._take(ln)
                    if self.pos == 0:
                        self.head = raw[:min(cut, self.MARK)]
                    self.pos += cut
                    self.mark = (self.mark + raw[max(0, cut - self.MARK):cut])[-self.MARK:]
                    fh.seek(self.pos)
        except OSError:
            pass
        return self

    def _take(self, ln):
        placed = b'"placed"' in ln and (b'"over_82":true' in ln or b'"over_82": true' in ln)
        if not placed and not any(k in ln for k in self.TOKENS):
            return
        try:
            r = json.loads(ln)
        except ValueError:
            return
        if not isinstance(r, dict):
            return
        t = _epoch(r.get("t"))
        if t is None:
            return
        r["_epoch"] = t
        ev = r.get("ev") or r.get("kind")
        if ev == "start":
            self.starts.append(r)
        elif ev == "live_fill":
            self.fills.append(r)
        elif ev == "live_settle":
            self.settles.append(r)
        elif ev == "placed" and r.get("over_82") is True:
            self.placed82.append(r)
        elif ev == "day_stop_reset":
            self.resets.append(r)


def _ladder_scans(paths):
    """A LadderScan per ladder log, kept in _CACHE (the phone asks every /fixes) and brought up to date."""
    out = []
    for p in paths:
        key = ("ladder", p)
        sc = _CACHE.get(key)
        if sc is None:
            sc = _CACHE[key] = LadderScan(p)
        out.append(sc.update())
    return out


def o_rail100(start):
    """True when a ladder start record runs the 100% rail: its argv's --commit-frac (or --commit-frac=) is 1.0; a
    record without the flag in its argv (or with no argv: those before v-ladder-rail100) is read off its auto block's
    commit_frac (--auto-size runs log it)."""
    st = start or {}
    argv = st.get("argv")
    if isinstance(argv, (list, tuple)):
        for i, a in enumerate(argv):
            a = str(a)
            if a == "--commit-frac" and i + 1 < len(argv):
                v = _f(argv[i + 1], None)
            elif a.startswith("--commit-frac="):
                v = _f(a.split("=", 1)[1], None)
            else:
                continue
            return v is not None and v >= 1.0 - 1e-9
    cf = _f((st.get("auto") or {}).get("commit_frac"), None)
    return cf is not None and cf >= 1.0 - 1e-9


def o_tracked(start):
    """True when a ladder start record comes from the ladder code that MARKS the bids (v-ladder-rail100: over_82 on its
    'placed' and 'live_fill' records): that code's start record always carries `argv` and `old_limit` (None under a fixed
    --size). The older code wrote neither, and never marks a bid -- on the 100% rail it would leave O at 'none yet'
    forever, so such a start is O's problem (O_UNTRACKED), never a quiet zero."""
    st = start or {}
    return "argv" in st and "old_limit" in st


def o_untracked(starts):
    """The windows the ladder ran the 100% rail on code that does not mark the bids: [(from, to or None)] in time order,
    one per such start record, each up to the next start record (None: it is the latest, so still running)."""
    out = []
    for i, r in enumerate(starts):
        if o_rail100(r) and not o_tracked(r):
            out.append((r["_epoch"], starts[i + 1]["_epoch"] if i + 1 < len(starts) else None))
    return out


def _o(scans, now):
    """O -> (since, events, tally) or (None, [], None) before the first start on the 100% rail. One event per over-82
    bid that filled (by ticker and paper_id), dated by its first fill: usd = its market's live_settle pnl (summed, a
    late fill's own settle in) x its contracts / every contract filled in that market since the start, open until the
    market has a live_settle. tally: bids (settled), won, lost, open, n (their contracts), usd, placed (over-82 bids
    placed since, filled or not), filled (of those, filled), untracked (o_untracked's windows: the 100% rail on code
    that does not mark the bids; one still open = O's problem)."""
    starts = sorted((r for sc in scans for r in sc.starts), key=lambda r: r["_epoch"])
    since = next((r["_epoch"] for r in starts if o_rail100(r)), None)
    if since is None:
        return None, [], None
    untracked = o_untracked(starts)
    fills = sorted((r for sc in scans for r in sc.fills if r["_epoch"] >= since), key=lambda r: r["_epoch"])
    markets = {}
    for r in fills:
        tk, d = r.get("ticker"), _f(r.get("delta"))
        if not tk or d <= 0:
            continue
        m = markets.setdefault(tk, {"all": 0.0, "bids": {}})
        m["all"] += d
        if r.get("over_82") is True:
            b = m["bids"].setdefault(r.get("paper_id"), {"n": 0.0, "side": r.get("side"), "px": r.get("px"), "rec": r})
            b["n"] += d
    pnl, result = {}, {}
    for sc in scans:
        for s in sc.settles:
            tk = s.get("ticker")
            if s["_epoch"] < since or tk not in markets:
                continue
            pnl[tk] = pnl.get(tk, 0.0) + _f(s.get("pnl"))
            if s.get("result") in ("yes", "no"):
                result[tk] = s["result"]
    placed = sum(1 for sc in scans for r in sc.placed82 if r["_epoch"] >= since)
    t = {"bids": 0, "won": 0, "lost": 0, "open": 0, "n": 0.0, "usd": 0.0, "placed": placed, "filled": 0,
         "untracked": untracked}
    out = []
    for tk, m in markets.items():
        for _pid, b in m["bids"].items():
            t["filled"] += 1
            share = (" (%s of the %s contracts the market filled: that share of its %s)" % (
                _g2(b["n"]), _g2(m["all"]), _rw.usd(pnl[tk]))) if tk in pnl and m["all"] > b["n"] + 1e-9 else ""
            words = "a bid the old 82%% limit would have refused: %s %s at %s filled%s" % (
                _g2(b["n"]), _side(b["side"]), _cents(_f(b["px"], None)), share)
            usd = None
            if tk in pnl:
                st = "scored"
                usd = pnl[tk] * b["n"] / m["all"]
                won = (result[tk] == b["side"]) if tk in result else usd >= 0
                t["bids"] += 1
                t["won" if won else "lost"] += 1
                t["n"] += b["n"]
                t["usd"] += round(usd, 2)
                words += "; it %s, so it %s %s" % ("won" if won else "LOST", "made" if usd >= 0 else "cost",
                                                   _rw.usd(abs(usd), False))
            else:
                st = _status(tk, None, now)
                t["open"] += 1
                words += "; not settled yet" if st == "pending" else "; no settle 3 h after the close (unknown)"
            out.append(_event({"t": b["rec"].get("t"), "_epoch": b["rec"]["_epoch"], "ticker": tk}, words, usd, st))
    return since, out, t


def o_problem(t):
    """O's problem words (the phone's warning line on /fixes) or None: the latest ladder start runs the 100% rail on code
    that does not mark the bids, so nothing past the old limit can be counted while it runs."""
    w = (t or {}).get("untracked") or []
    return O_UNTRACKED if w and w[-1][1] is None else None


def _o_extra(t, since):
    """O's lines under its net: the plain line ('the bids the old 82% limit would have refused: +$X on N bids (W won,
    L lost) since <date>', 'none yet' before any settles) and, once any was placed, how many filled. A window on the
    100% rail without the marking code is said first (never a quiet 'none yet'): still running = ON THE 100% RAIL BUT
    NOT TRACKED since its start; ended = those hours' bids are not in this row."""
    s = et_words(since)
    out = []
    for t0, t1 in t.get("untracked") or []:
        if t1 is None:
            out.append("%s since %s: no bid past the old limit is marked, so none can be counted" % (O_UNTRACKED, et_words(t0)))
        else:
            out.append("NOT TRACKED %s to %s (the 100%% rail on ladder code that does not mark the bids): the bids past "
                       "the old limit then are not in this row" % (et_words(t0), et_words(t1)))
    if not t["bids"]:
        line = "%s: none %s%syet since %s" % (O_HEAD, "marked " if out else "", "settled " if t["open"] else "", s)
    else:
        line = "%s: %s on %d bid%s (%d won, %d lost) since %s" % (
            O_HEAD, _rw.usd(round(t["usd"], 2)), t["bids"], "" if t["bids"] == 1 else "s", t["won"], t["lost"], s)
    if t["open"]:
        line += " · %d open" % t["open"]
    out.append(line)
    if t["placed"]:
        out.append("%d bid%s placed past the old limit, %d filled (%s contracts settled); a bid that never filled cost "
                   "nothing" % (t["placed"], "" if t["placed"] == 1 else "s", t["filled"], _g2(t["n"])))
    return out


def _o_what():
    return ("the ladder may rest bids up to 100% of its pot (was 82%: --commit-frac 1.0, the same bid size, 6 bids a close "
            "instead of 5); each bid the old limit would have refused is priced by its market's own result")


def _o_row(scans, now):
    """O's row. While O_WITHDRAWN: never live, whatever the log holds (no problem, no events; totals() leaves it out),
    its words O_NOT_LIVE -- and, should the ladder's latest start run --commit-frac 1.0 all the same, a clause saying so
    (never a quiet '82%' that is not true; still no problem and nothing counted). Else O's scoring (_o)."""
    if O_WITHDRAWN:
        starts = sorted((r for sc in scans for r in sc.starts), key=lambda r: r["_epoch"])
        words, short = O_NOT_LIVE, O_RETIRED
        if starts and o_rail100(starts[-1]):
            clause = ("; but the ladder's latest start (%s) runs --commit-frac 1.0: nothing of it is counted here"
                      % et_words(starts[-1]["_epoch"]))
            words += clause
            short = O_RETIRED_HEAD + clause                    # never the '82%' that is not true, in either form
        return _change("O", _o_what(), None, [], not_live=words, withdrawn=True, retired=short)
    o_since, evs, tally = _o(scans, now)
    if o_since is None:
        return _change("O", _o_what(), None, [], not_live=O_NOT_LIVE)
    return _change("O", _o_what(), o_since, evs, extra=_o_extra(tally, o_since), problem=o_problem(tally))


# ---------------------------------------------------------------------------
# Q (v-ladder-dayreset, the ladder's 2026-11-14 17:53:01Z start): the money after each midnight reset of a day stop
def q_since(starts):
    """Q's start: the epoch of the first ladder start record from the code with the midnight reset -- the first to
    carry start_reads (v-ladder-dayreset shipped in one commit with v-ladder-start429, which added it) -- else None."""
    return next((r["_epoch"] for r in starts if "start_reads" in r), None)


def _q_day(d):
    """'2026-11-14' -> 'Nov 14' (the ladder's ET day key), else the text as it is."""
    try:
        _y, m, dd = (int(x) for x in str(d).split("-"))
        return "%s %d" % (("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")[m - 1], dd)
    except (TypeError, ValueError, IndexError):
        return str(d)


def _q(scans, now):
    """Q -> (since, events, tally) or (None, [], None) before the first start on the midnight-reset code. One event per
    day_stop_reset from `since` on: its span runs to the ladder's next start or next reset (None: still running), and
    its money is every live_settle pnl of the markets the ladder filled inside the span, pro rata by the contracts
    filled inside it (a market's contracts from before the reset are not its). Open (with the money so far) while the
    span runs or one of its markets has not settled. tally: resets, usd, markets (settled), open."""
    starts = sorted((r for sc in scans for r in sc.starts), key=lambda r: r["_epoch"])
    since = q_since(starts)
    if since is None:
        return None, [], None
    resets = sorted((r for sc in scans for r in sc.resets if r["_epoch"] >= since), key=lambda r: r["_epoch"])
    marks = sorted([(r["_epoch"], "its next start") for r in starts] + [(r["_epoch"], "the next reset") for r in resets])
    fills = [r for sc in scans for r in sc.fills if r.get("ticker") and _f(r.get("delta")) > 0]
    n_all, pnl = {}, {}
    for r in fills:
        n_all[r["ticker"]] = n_all.get(r["ticker"], 0.0) + _f(r.get("delta"))
    for sc in scans:
        for s in sc.settles:
            if s.get("ticker"):
                pnl[s["ticker"]] = pnl.get(s["ticker"], 0.0) + _f(s.get("pnl"))
    t = {"resets": 0, "usd": 0.0, "markets": 0, "open": 0}
    out = []
    for rs in resets:
        t0 = rs["_epoch"]
        t1, end = next(((x, w) for x, w in marks if x > t0), (None, None))
        span = {}
        for r in fills:
            if r["_epoch"] >= t0 and (t1 is None or r["_epoch"] < t1):
                span[r["ticker"]] = span.get(r["ticker"], 0.0) + _f(r.get("delta"))
        usd, done, wait = 0.0, 0, []
        for tk, n in span.items():
            if tk in pnl and n_all.get(tk):
                usd += pnl[tk] * n / n_all[tk]
                done += 1
            else:
                wait.append(tk)
        usd = round(usd, 2)
        hp = _f(rs.get("halt_day_pnl"), None)
        words = "the day stop of %s%s ended at midnight ET and the ladder bid again: %s it %s %s on %d market%s" % (
            _q_day(rs.get("halt_day")), (" (the day at %s)" % _rw.usd(hp)) if hp is not None else "",
            ("until %s (%s)" % (end, et_words(t1))) if t1 is not None else "so far (still running)",
            "made" if usd >= 0 else "lost", _rw.usd(abs(usd), False), done, "" if done == 1 else "s")
        if wait:
            words += " (%d more not settled yet)" % len(wait)
        words += "; the old code would have stayed halted"
        if t1 is None or wait:
            st = "pending"
            if t1 is not None and all(_status(tk, None, now) == "unknown" for tk in wait):
                st = "unknown"
            t["open"] += 1
        else:
            st = "scored"
        out.append(_event(rs, words, usd, st, coin="ladder"))
        out[-1]["usd"] = usd                      # the settled part counts now, the rest when it settles (as D's)
        t["resets"] += 1
        t["usd"] += usd
        t["markets"] += done
    return since, out, t


def _q_extra(t, since):
    """Q's line under its net: 'money the ladder made after a midnight reset (the old code stayed halted): $X over N
    resets since <date>', or 'no reset yet'."""
    s = et_words(since)
    if not t["resets"]:
        return ["%s: no reset yet since %s" % (Q_HEAD, s)]
    line = "%s: %s over %d reset%s since %s (%d market%s settled)" % (
        Q_HEAD, _rw.usd(round(t["usd"], 2)), t["resets"], "" if t["resets"] == 1 else "s", s, t["markets"],
        "" if t["markets"] == 1 else "s")
    if t["open"]:
        line += " · %d open" % t["open"]
    return [line]


def _q_what():
    return "a ladder day stop ends at the next ET midnight (before, it held until the ladder's process ended, up to 7 days)"


def _q_row(scans, now):
    q_since_t, evs, tally = _q(scans, now)
    if q_since_t is None:
        return _change("Q", _q_what(), None, [], not_live=Q_NOT_LIVE)
    return _change("Q", _q_what(), q_since_t, evs, extra=_q_extra(tally, q_since_t))


# ---------------------------------------------------------------------------
def whats(start):
    """One plain line per change, read off the newest start record's flags where they matter."""
    rail = start.get("boost_rail") or "side"
    bar = start.get("jump_hedge_min_ask")
    cap = start.get("max_positions") or 5
    return {
        "A": _rw.RULE_WHAT["A"],
        "B": _rw.RULE_WHAT["B"],
        "C": "%.2fx extra contracts of the hedge side when pin's odds line fires with 11+ s left" % _f(
            start.get("hedge_odds_mult"), 1.25),
        "D": ("the 1.5x boost never switches off; a boosted-side loss is only logged" if rail == "off" else
              "the 1.5x boost switches off only on a losing boosted-side leg, not on a losing hedge leg"),
        "E": "hedge limits snap down onto Kalshi's price grid, so a sub-10c hedge is accepted instead of refused",
        "F": "no jump hedge while the hedge side asks under %s (the odds line still hedges)" % (
            _cents(bar) if bar else "the bar"),
        "G": "the last-seconds 1.5x is never applied once the late-boost rail has refused it",
        "H": "the extra hedge leg counts against the run stake cap and the loss abort",
        "I": "up to %s positions open at once (was 3)" % cap,
        "J": "the extra hedge leg fires on odds under the line whatever fired the hedge alarm",
        "K": _k_what(start.get("cheap_window")),
        "L": _l_what(start),
        "N": _n_what(start),
    }


def _k_what(w):
    if not (isinstance(w, (list, tuple)) and len(w) == 3):
        w = (6, 10, 0.98)
    return ("no first buy under %s in a market closing %s to %s ET (the market is skipped); each skip is priced by what "
            "it would have done" % (_cents(w[2]), _hour(w[0]), _hour(w[1])))


def _l_what(st):
    """L's line, off the start record that switched the shadow on (6 sd alarm, 8 sd cap, 5c bar when it says nothing)."""
    st = st or {}
    sd, cap, bar = st.get("hedge_jump_shadow"), st.get("hedge_jump_max"), st.get("jump_hedge_min_ask")
    return ("the jump hedge is in shadow: it sends nothing; this is what it would have made (%s sd alarm, %s sd cap, %s bar "
            "as before)" % (("%.0f" % _f(sd)) if sd is not None else "6", ("%.0f" % _f(cap)) if cap is not None else "8",
                            _cents(bar) if bar is not None else "5.0c"))


def _change(cid, what, since, events, off=False, extra=None, not_live=None, third=None, problem=None,
            withdrawn=False, retired=None):
    events = sorted(events, key=lambda e: e["epoch"] or 0)
    scored = [e["usd"] for e in events if e["usd"] is not None]
    last = events[-1]["epoch"] if events else None
    return {"id": cid, "name": NAMES[cid], "what": what, "since": et_words(since), "since_t": since,
            "engaged": len(events), "last_engaged": et_words(last), "last_t": last,
            "open": sum(1 for e in events if e["open"]), "net_usd": round(sum(scored), 2) if events else 0.0,
            "events": events, "off": bool(off), "extra": list(extra or []), "not_live": not_live,
            "third": sorted(third or [], key=lambda e: e["epoch"] or 0), "problem": None if withdrawn else problem,
            "withdrawn": bool(withdrawn), "retired": (retired if since is None else None)}


def report(paths=None, now=None):
    """Every change A..N scored, then O when a ladder order log is read, then P, then Q when a ladder order log is read
    (see the module note). `paths`: explicit logs (tests; a ladder-live-orders*.jsonl among them is O's and Q's, the
    rest pin's); default pin's live logs from 11-01 on and the ladder's order log in RESULTS when it is there. `now`:
    the clock (pending vs unknown)."""
    now = time.time() if now is None else float(now)
    if paths is None:
        paths, lad = pin_paths(), ladder_paths()
    else:
        paths = list(paths)
        lad = [p for p in paths if is_ladder_log(p)]
        paths = [p for p in paths if not is_ladder_log(p)]
    L, S = _load(paths)
    new = S.new_build_since()
    since = {"A": SINCE_AB, "B": SINCE_AB, "C": SINCE_C}
    cstep, c_line = _c_step(S, now)                            # v-oddsmult15: C's 1.25x->1.5x step, under its total
    abc = _abc(L, now, since, cstep)
    st = S.latest_start() if new is not None else {}
    W = whats(st)                                              # the new flags' values once the build is live
    out = [_change(k, W[k], since[k], abc[k], extra=([c_line] if k == "C" and c_line else None)) for k in "ABC"]
    later = {"D": _d, "E": _e, "G": _g, "H": _h, "I": _i, "J": _j}
    for k in "DEFGHIJ":
        if new is None:
            out.append(_change(k, W[k], None, []))
            continue
        evs = _f_cheap(L, S, now, new) if k == "F" else later[k](S, now, new)
        # G is in the build but switched off unless the launcher says --late-bypass-fix on (11-04: it would have
        # trimmed 23 winning late adds to save one loss; held as a break-even safety filter)
        off = (k == "G" and (st.get("late_bypass_fix") or "off") != "on")
        out.append(_change(k, W[k], new, evs, off))
    # K: from the first start record that names a cheap window (v-cheapwin), its words off that record
    k_since, k_window = S.cw_since()
    if k_since is None:
        out.append(_change("K", _k_what(None), None, []))
    else:
        evs, tally = _k(S, now, k_since)
        out.append(_change("K", _k_what(k_window), k_since, evs, extra=_k_extra(S, tally, k_since, k_window)))
    # L: from the first start record with hedge_jump_shadow set (v-0925v JS), its words off that record
    l_since, l_start = S.js_since()
    if l_since is None:
        out.append(_change("L", _l_what(None), None, [], not_live=L_NOT_LIVE))
    else:
        evs, tally = _l(S, now, l_since)
        out.append(_change("L", _l_what(l_start), l_since, evs, extra=_l_extra(tally, l_start)))
    # M: from the first start record with extra_coin 0 and late_extra 0 (call B), its words off that record
    m_since, m_start = S.cb_since()
    if m_since is None:
        out.append(_change("M", _m_what(None), None, [], not_live=M_NOT_LIVE))
    else:
        evs, third, tally = _m(S, now, m_since, m_start)
        out.append(_change("M", _m_what(m_start), m_since, evs, extra=_m_extra(tally), third=third))
    # N: from the first start record with hedge_belief at the new line (v-hedgeline60), its words off that record
    n_since, n_start = S.hl_since()
    if n_since is None:
        out.append(_change("N", _n_what(None), None, [], not_live=N_NOT_LIVE, retired=N_RETIRED))
    else:
        evs, tally = _n(S, now, n_since, n_start)
        out.append(_change("N", _n_what(n_start), n_since, evs, extra=_n_extra(tally)))
    # O: the ladder's change (v-ladder-rail100), whenever a ladder order log is read. WITHDRAWN 11-14 (O_WITHDRAWN):
    # its row says so whatever the log holds; else from the first ladder start on --commit-frac 1.0, the bids the old
    # 82% rail would have refused, priced by their markets
    scans = _ladder_scans(lad) if lad else []
    if lad:
        out.append(_o_row(scans, now))
    # P: from the first start record with band99_max_tau set (v-0925x band99late), its words off that record
    p_since, p_start = S.b99_since()
    if p_since is None:
        out.append(_change("P", _p_what(None), None, [], not_live=P_NOT_LIVE))
    else:
        evs, tally = _p(S, now, p_since, p_start)
        out.append(_change("P", _p_what(p_start), p_since, evs, extra=_p_extra(tally, p_since)))
    # Q: the ladder's midnight reset (v-ladder-dayreset), whenever a ladder order log is read
    if lad:
        out.append(_q_row(scans, now))
    return out


def totals(changes):
    """{engaged, open, net_usd} over every change except J and a withdrawn one (O while O_WITHDRAWN: never live, never
    counted): a J leg is also a C engagement (C scores every executed extra), so J stays out of the sum and that leg is
    counted once. L is in: what it keeps or misses is pin's real money (the premium not spent, the save the odds line
    then paid more for), as K's skipped buys are. M is in by its net (the contracts the 2-bet budget held back on pin's
    own buys); its true-3rd-bet list is not. P and Q are in. problems: the ids of every change not withdrawn (J too)
    that says one (change["problem"]: O on the 100% rail without the marking code, while O is not withdrawn)."""
    cs = [c for c in changes if c["id"] != "J" and not c.get("withdrawn")]
    return {"engaged": sum(c["engaged"] for c in cs), "open": sum(c["open"] for c in cs),
            "net_usd": round(sum(c["net_usd"] for c in cs), 2),
            "problems": [c["id"] for c in changes if c.get("problem") and not c.get("withdrawn")]}
