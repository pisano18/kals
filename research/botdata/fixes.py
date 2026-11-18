"""fixes.py -- every live pin change, scored on pin's own logs: how often it engaged, when last, what is still open and
the net $ so far (+ made or saved, - cost or gave up). The data behind the phone's /fixes (/changes) page and the rules
watcher's alerts. Pure: no network, no Kalshi, no key; it only reads results\\pinrun-live-*.jsonl (through botdata's
path helpers, or an explicit list of paths for a test).

v-fixes (2026-11-04; the operator: "track them thoroughly and have a telegram command that makes it very simple to see
times any of them have been engaged and the positive or negative overall result of it").

THE CHANGES and when each counts as engaged (the push-11-04 scoring table):
  A later-buy check     a refusal with gate ws_later_fall / ws_later_skip     pinrules_watch.score_A (reused)
  B jump cap            jump_capped, re-scored here (_b; the 11-14 retro found score_B's -$34.83 wrong, real -$25.12):
                        the jump hedge the cap stopped against pin's real later hedges AND extra legs on that side; $0
                        where it could never have filled (the jump hedge in shadow, an off-grid limit before --hedge-tick
                        round, an ask under the 5c bar); plus, before the J build, a 'belief' alarm on a capped jump: the
                        odds extra fired only because of the cap (ZEC 11-04 +$2.66). Those extra legs are C's legs too:
                        B carries them as overlap_usd and totals() counts them once.
  C bigger hedge 1.25x  hedge_extra that filled                               pinrules_watch.score_C (reused)
  D boost rail side/off re-scored (_d, the retro's d_cf.py; the old 'now - was' of the band_boost records showed +$109.38,
                        real -$22.26): from the old "any" rule's trip in a run (its first boost_rail_kept of each kind),
                        every market of that run whose first fill came after it is re-sized ORDER BY ORDER at the old
                        rule's multiple (the staged-entry limits size 1.5x without a band_boost record), its hedges
                        scaled with the position, the late add's refill in (d_market); real - that, at the result.
                        Only while D was ON: a run whose start record says boost_rail "off" (11-04..11-16).
                        REVERTED 11-16 11:08:53Z (v-railany, results\\pin_railany.ps1: --boost-rail any, the operator: "if
                        d is now proven more profitable on total then switch it on"): from the first start on "any" or
                        "side" the row scores the revert against KEEPING D (row["undo"], the undo convention below):
                        in each such run, from its first band_boost_off / late_boost_off (pinrun switched that boost
                        off for the rest of the run), every market whose first fill came after it is re-sized UP order
                        by order to what the boost would have bought (d_keep: the inverse of d_market, never past the
                        book the order's own sweep saw at its limit (else its signal's ladder), the close's budget,
                        the drawdown headroom or a partly filled order's fill), hedges scaled with the position;
                        real - that, at the result
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
                        (cheap_window_settled) on the retro skeptic's model (cw_shadow_usd: a win at K_WIN of n_ask x the
                        edge, pin's own hedge-free 6-10 ET cheap first buys; a flip at the K_FILL_FLIP fill, lost, plus
                        the belief hedge the shadow says would have fired; skips of one close share its budget); + when
                        that shadow lost (saved), - when it won (gave up). The row also says what the window as a whole
                        made with the rule and what it would have made without it.
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
                        (1) the NET: a buy pin DID make that the 2-bet budget held back (its OWN signal's budget_left --
                        the latest signal before the order in the file, never a same-second record of another order --
                        was the binding cap) on a coin new to the close after its first fill, or inside the old late
                        window: the contracts the old argv's third SIZE of room would have let the sweep (its tapered
                        depth), the late boost or the band boost (the UNTAPERED book at the limit, the one-coin room)
                        add (m_take_old, the retro's retro_m.py), priced on the signal's ladder PAST what filled, at the
                        market's result, fee and hedge share in: + when the bet lost (the stake not spent), - when it
                        won (the gain not made). This is what reverting B gives back.
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
                        price, so never flattering the rule either way); when pin held that side in the market, plus
                        its pro-rata share of the market's real hedges, won or lost (the old code's leg would have
                        drawn them as pin's blocked legs do in (b); fixed 11-18 after the BNB 2:45 AM close charged the
                        rule -$58.19 of hedges); else a loss less the P_HEDGE_BACK (41%) pin's hedges
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
  R 5 Hz hedge          v-hedge5live (2026-11-16 13:08:56Z, results\\pin_hedge5live.ps1: --index-5hz shadow -> hedge; the
                        operator's yes 11-16): pin's belief hedge fires on the LOWER of the 1 Hz and 5 Hz beliefs (BTC ETH
                        SOL XRP DOGE, + BTCD). From the first start record with index_5hz "hedge", while it is (rule_spans:
                        a start back on "shadow" stops it), every market with a hedge_alarm whose by_5hz is true (the 5 Hz
                        belief under the line while the 1 Hz one was not) is ONE event, priced against the 1 Hz line
                        (hedge5live-read's HOW): the 1 Hz line fires at the first pintraj row of that market at or after
                        the alarm's second, before the close, whose 1 Hz belief in the held side (the alarm's want: conf
                        when the row's want is the held side, else 1 - conf) is under the start record's hedge_belief. Its
                        moment is the EARLIEST second whose print could have crossed: the second after the last print
                        seen not crossing (r_print_second: a row is written as its second begins, often before that
                        second's print arrives, index_age_s ~1.0, so the print that crossed is a row late or in no row),
                        priced at the hedge-side ask (opp_ask when the row's want is the held side, else ask:
                        _n_hedge_ask) of the row AT that second (r_one_hz: on the shadow week's 4 markets this is when
                        pin's real 1 Hz alarms fired and what their books asked; the crossing rows were a second later
                        in 3 of them and 4-9c dearer). The 5 Hz path is pin's REAL executed hedge and hedge_extra legs
                        of the hedge side in that market from the alarm on. At the market's result, fee in
                        (pinrules_watch.value):
                        1 Hz also fired: the real legs - the same contracts at the 1 Hz price ((1 Hz price - real fill) x
                        n: + = the 5 Hz hedge bought cheaper); the extra leg the same way while the 1 Hz moment has 11+ s
                        left (hedge_odds_min_tau), else the 1 Hz line would not have bought it: its real money is the 5 Hz
                        path's own (+ or -).
                        1 Hz never fired before the close: the real legs' whole money (a false alarm: - when our side won;
                        + when it flipped anyway, a save the 1 Hz line would have missed).
                        Open until the market settles; a market whose trajectory has no row after the alarm is NOT PRICED
                        (said under the net, never $0). The operator's STOP RULE (11-16): back to shadow if the net falls
                        below -$25: while the latest start still runs "hedge", a net under R_STOP_USD is the row's problem
                        (the phone's warning line) and pinrules_watch sends one alert once the net reads the same on two
                        ticks.
  Q ladder midnight     v-ladder-dayreset (the ladder's 2026-11-14 17:53:01Z start): a day stop ends at the next ET
    reset               midnight (a 'day_stop_reset' record); before, it held until the ladder's process ended (up to 7
                        days). Priced from the ladder's order log: per reset, every live_settle pnl of the markets the
                        ladder filled from the reset until its next start (or the next reset), pro rata by the contracts
                        filled in that span -- the old code would have stayed halted for exactly that span. A span still
                        running, or a market of it not settled yet, is open with the money so far.
  WS wrong-side skip    v-wrongside / LS20 (--wrongside-rise-c 1.0, live 10-27 9:07 PM ET): each market's first
                        wrong_side refusal, against never having the rule (the retro skeptic's method): a cheap-window
                        market (K on) is skipped anyway ($0); else WON = the coin's bet x what pin's own never-hedged won
                        markets made per contract of bet at that first-ask bucket, a FLIP = the contracts pin holds per
                        contract of bet there, lost; plus the hedge the trajectory says would have fired (ws_hedge: the
                        belief hedge, the jump hedge only while it was live and could fill). A hedge covers only what
                        the buy could hold by its second (ws_position: the refusal's own contracts + one top-up the
                        trajectory allows before it), and that is the position (pin buys no more of a side it has
                        hedged): ZEC 11-01, refused 147 at tau 17, hedged at tau 15, is 147, not the bucket's 1.12 x
                        299. Priced from pin's fills up to the undo. + = saved, - = gave up.
  LAD the ladder's 4    cplus + fit + single98 + the 82% rail as ONE row against the Option C setting before them, and
  STOP the 4 stops      FX, jump band, coin race, forecaster as ONE row: both MEASURED ONCE by the 11-14 retro (no log
                        the phone can re-read prices them: _fixed_row, row["fixed"]), their dates and assumptions said.
THE UNDO (results\\pin_undo1114.ps1: pin restarted with M, K and WS off and B's cap dropped): each of M, K, WS finds its
own periods off the start records (rule_spans: extra_coin / late_extra back above 0, cheap_window gone, wrongside_rise_c
0 or none); its rule's events count only while it was ON, and from the first OFF start on the row scores the UNDO
against KEEPING the rule (row["undo"], + = the undo made money): M = the excess of every order filled past the 2-bet
budget (the 3rd bet the rule blocked), K = the whole money of every market closing in the old window whose first buy was
under the old floor, WS = the whole money of every market whose first buy was on the wrong side without the 1c rise (a
market both would have skipped is WS's: the earlier gate; a 3rd bet in a market K's or WS's undo counts whole is
theirs, not M's: never twice). The row's net STAYS the rule's money against never having it (from the undo on pin
trades as if the rule had never been); the undo's money, against KEEPING the rule, sits beside it (row["undo"]; the
phone's net line: 'with the rule: net $X · since the undo (vs keeping it): $Y on N markets'), never in the net nor in
totals()' net (its own undo_usd). WS's rule figure prices off pin's fills up to the undo, so it stops moving then. B
says when its cap was dropped. D's revert (v-railany, 11-16) is scored the same way: rule_spans(_d_on), its rule
figure only from trips in ON spans (boost_rail "off"), its undo (_d_undo) from the first start on "any" / "side": the
markets after each band_boost_off / late_boost_off re-sized up to KEEPING the boost (+ = the revert made money: the
boosted extra would have lost). pinrules_watch's 9 PM daily line carries D beside M, K, WS (its UNDO_IDS); its loss
alerts never do (UNDO_NO_LOSS): keeping D only ever ADDS size, so no loss of pin's is one D would have stopped, and a won
bet the revert sized smaller is not a loss.
TRAJECTORIES: M's 3rd bets, P's and WS's results and WS's hedge replay read pin's pintraj log wherever it is now
(traj_window: plain = a binary search on time, never the whole file; archived = read through once for every market a
report asks, only those markets' rows kept, persisted in results\\fixes_traj_cache.json keyed by the archive's name, size
and mtime, so the watcher's fresh process each tick does not read an archive again). _load keeps at most LOAD_KEEP (2)
states of pin's logs.
A and B count from 11-01 15:37 ET, C from 11-02 08:35 ET, D to J from the first start record after the 0925r build
(code_sha ca156bf45704) with another code_sha, K from the first start record that names a cheap_window, L from the
first start record with hedge_jump_shadow set (pinrun refuses it next to --hedge-jump, so the jump hedge is off there),
M from the first start record with extra_coin 0 and late_extra 0 (the start record carries both and bank_brake), C's
step from the first start record with hedge_odds_mult 1.5 (else its first 1.5x leg), O from the first ladder start
record whose argv has --commit-frac 1.0 (or whose auto block says commit_frac 1.0) -- while not withdrawn --, P from
the first start record with band99_max_tau set, R from the first start record with index_5hz "hedge" (only its ON
spans count), Q from the first ladder start record with start_reads (the code that
resets at midnight: v-ladder-dayreset shipped in one commit with v-ladder-start429, which added the field).
An engagement whose market has not settled is "open" (not in net $).

A settled leg's pnl_c is pin's own figure for the whole leg, the taker fee INSIDE it (pinrun: pnl = filled * (1 - cost
or -cost) - billed_fee(cost, filled)). A leg is matched by ticker, our side (want; a hedge leg's want is its hedge side),
the nearest cost, then the nearest time; a leg is claimed once per change. Records of older builds may lack fields:
every read is a .get with a default.

    report(paths=None, now=None) -> [change dict per A..N, then O when a ladder order log is read, then P, R, WS, then Q
        when a ladder order log is read, then LAD and STOP (measured once, in every report)]; each dict also carries undo
        (None, or {since, since_t, net_usd, engaged, open, events, note, line}: the undo vs keeping the rule, never in
        the row's net_usd), rule_usd (the rule's own net vs never having it: net_usd's figure), fixed (LAD, STOP),
        overlap_usd (B: its extra legs C also counts), group (pin / ladder / stops):
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
         never while O is withdrawn; R's stop rule while pin still runs --index-5hz hedge and R's net is under -$25),
         withdrawn (True only for O while O_WITHDRAWN: never live, never in totals, never a problem),
         retired (None, or the short words of a change that is off for good while it is not live: O while withdrawn,
         N while shelved; the phone folds such a change into one short line, its not_live words stay whole here)}
    totals(changes) -> {engaged, open, net_usd, overlap_usd, groups {pin, ladder, stops}, undo_usd, undo_engaged,
        undo_open, undos, problems (the ids saying a problem)} over every change but J and a withdrawn one (problems:
        every change not withdrawn); J's leg is already inside C; B's overlap_usd (the extra legs only its cap made
        happen, C's too) is taken off once; engaged and open leave the measured-once rows and the undos out (the undos'
        money, vs keeping the rules, is undo_usd, never in net_usd). L is in: the
        premium it keeps and the save it misses are pin's real money, as K's skipped buys are. M is in by its net
        (the held-back contracts of pin's own buys); its `third` list is not. O is in when its row is live (the
        ladder's real money on the bids only the new rail placed), never while withdrawn. P is in (pin's own blocked
        legs' real money less what the skipped band legs would have made), Q is in (the ladder's real money after its
        resets), R is in (pin's real 5 Hz hedge legs against the 1 Hz line's price).
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
IDS = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "P", "R", "WS")   # pin's: a row each,
#                                           always
LADDER_IDS = ("O", "Q")                   # the ladder's (v-ladder-rail100, v-ladder-dayreset): a row each whenever a
#                                           ladder order log is read (report: A..N, O, P, R, WS, Q, LAD, STOP)
FIXED_IDS = ("LAD", "STOP")               # measured once by the 11-14 retro (no log the phone can re-read): every report
NAMES = {"A": "later-buy check", "B": "jump cap", "C": "bigger hedge", "D": "boost rail", "E": "hedge tick",
         "F": "cheap jump skip", "G": "late-boost bypass fix", "H": "extra stake cap", "I": "max positions 5",
         "J": "extra on odds", "K": "cheap morning skip", "L": "jump hedge shadow", "M": "3rd bet blocked",
         "N": "hedge line 0.60", "O": "ladder cash limit 100%", "P": "band99 late-only", "Q": "ladder midnight reset",
         "R": "5 Hz hedge", "WS": "wrong-side skip", "LAD": "ladder's 4 changes", "STOP": "the 4 stops"}
GROUP = {"LAD": "ladder", "O": "ladder", "Q": "ladder", "STOP": "stops"}   # every other row is pin's
LOAD_KEEP = 2                             # _load keeps at most this many states of pin's logs (the newest)
# WS (v-wrongside / LS20, --wrongside-rise-c 1.0, live 2026-10-28 01:07:25Z = 10-27 9:07 PM ET): a FIRST buy with the
# index across the strike and our side's mid not up 1c in 5 s is refused (gate wrong_side) and the market skipped for
# the close. pin_paths reads from this run on (the run before it too).
SINCE_WS = 1793149645.0                   # 2026-10-28T01:07:25Z
WS_BUCKETS = ((0.0, 0.94), (0.94, 0.96), (0.96, 0.97), (0.97, 0.975), (0.975, 0.9801), (0.9801, 1.0))
WS_NOT_LIVE = "not live yet (comes with a pin start on --wrongside-rise-c above 0)"
UNDO_WORDS = "since the undo (vs keeping it)"
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
# R (v-hedge5live, 2026-11-16 13:08:56Z): the belief hedge fires on the LOWER of the 1 Hz and 5 Hz beliefs
R_LINE = 0.40                             # the belief line when the start record does not say (pinrun HEDGE_BELIEF)
R_MIN_TAU = 11.0                          # the extra leg's floor when the start record does not say (hedge_odds_min_tau)
R_STOP_USD = -25.0                        # the operator's stop rule (11-16): back to shadow once the net is under this
R_STOP = "stop rule: back to shadow if the net falls below -$25 (operator 11-16)"
R_REVERT = "results\\pin_hedge5live.ps1 -Revert + restart while flat"
R_NOT_LIVE = "not live yet (comes with the first pin start on --index-5hz hedge)"
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
# K's prices (the 11-14 retro: analyst retro_K, skeptic retro_skeptic_K s9_final.py, measured on pin's own cheap first
# buys in 6-10 ET closes before the rule, 10-15..11-08). The old 0.78 fill / 0.94 size were off (first-order fill
# 0.874; a market holds 1.03-1.12 x the first ask) and the win ratio it implied carried jump-hedge costs that cannot
# happen since 11-08 (the jump hedge is in shadow).
K_FILL = 0.874                            # the first order's fill (contracts filled / asked), the close's budget share
K_FILL_FLIP = 0.903                       # a flip is priced on the early leg's fill (it flips before the full leg)
K_WIN = {"full": 0.909, "early": 1.064}   # a won market's money per contract of n_ask x (1 - px), hedge-free, by leg
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
    if keep and abs(rows[i][0] - since) < 1.0:
        return keep                                     # a run starts AT `since`: the one before holds nothing of it
    return [p for _s, p in rows[max(0, i - 1):]]


def pin_paths(since=SINCE_WS):
    """pin's live logs for the tracker (botdata.logs.pin_logs: results\\pinrun-live-*.jsonl, RESULTS injectable), the
    ones log_rotate.py archived after 60 days included: a fix read 2 months after it went live still sees its first day.
    From WS's run on (10-28 01:07:25Z, the oldest change tracked from pin's logs)."""
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


def cw_n_ask(s, r=None):
    """K: what pin would have asked for the skipped first buy: n_ask from the shadow, else the refusal (else its size)."""
    n = _f((s or {}).get("n_ask"), None)
    if n is None:
        n = _f((r or {}).get("n_ask"), _f((r or {}).get("size")))
    return max(0.0, n)


def cw_contracts(s, r=None, scale=1.0):
    """K: the contracts a skipped first buy would have filled: n_ask x K_FILL (pin's own first-order fill on cheap
    first buys in 6-10 ET closes), x `scale` (the close's budget share, _k)."""
    return cw_n_ask(s, r) * K_FILL * float(scale)


def cw_shadow_usd(s, r=None, scale=1.0):
    """K: what one skipped market would have made (+) or lost (-) without the rule (the 11-14 skeptic's model D,
    retro_skeptic_K s9_final.py), fee in. WON: K_WIN[leg] x n_ask x (1 - px) x scale -- the money per contract of
    edge pin's own hedge-free 6-10 ET cheap first buys made before the rule (fill, later legs, slip and fees inside;
    the jump-hedge costs the analyst's 0.852 carried cannot happen since 11-08, the jump hedge is in shadow), less the
    shadow's belief hedge when the trajectory says one would have fired (hedge_mult x the filled contracts at
    hedge_px: it can still fire). FLIPPED: n_ask x K_FILL_FLIP x scale at px, lost, plus that belief hedge's pay-off.
    None until the shadow has a yes / no result."""
    res = (s or {}).get("result")
    if res not in ("yes", "no"):
        return None
    side = s.get("want") or (r or {}).get("want")
    won = res == side
    leg = (r or {}).get("leg") or s.get("leg") or "full"
    n_ask = cw_n_ask(s, r)
    px = _f(s.get("px"), _f(s.get("price"), 0.98))
    if won:
        usd = K_WIN.get(leg, K_WIN["full"]) * n_ask * (1.0 - px) * float(scale)
        n = n_ask * K_FILL * float(scale)
    else:
        n = n_ask * K_FILL_FLIP * float(scale)
        usd = _value(n, px, False) if n > 0 else 0.0
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
    """The names the trajectory log of pin log `pin_path` can have in its own folder: pinrun-live- -> pintraj-live-, as
    is, then .gz. (Kept for callers that look in the pin log's folder only; the tracker itself finds a trajectory
    wherever it is now, results\\archive\\ included, through p_traj_path / traj_window.)"""
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
            '"autosize"', '"sweep_depth"', '"band99_shadow"', '"wrong_side"', '"jump_capped"', '"hedge_alarm"',
            '"taper"', '"late_refused"', '"band_boost_off"', '"late_boost_off"', '"hedge5_shadow"')
    # band_boost_off / late_boost_off (D's revert, v-railany): the rail switched that boost off for the rest of the run;
    # hedge5_shadow (v-hedge5 shadow, 11-10..11-16): the hedge the 5 Hz belief would have sent (R's shadow-period check)
    LISTS = {"hedge": "hedges", "hedge_extra": "extras", "boost_rail_kept": "kept", "hedge_cheap_skip": "cheap",
             "band_boost_off": "boost_offs", "late_boost_off": "boost_offs", "hedge5_shadow": "h5s",
             "late_bypass_refused": "late_bypass", "extra_stake_capped": "stake_capped", "open_cap_relaxed": "open_cap",
             "order": "orders", "jump_shadow": "shadow", "signal": "signals", "sweep_depth": "sweeps",
             "band99_shadow": "b99s", "jump_capped": "capped", "hedge_alarm": "alarms", "taper": "tapers",
             "late_refused": "late_refused"}

    def __init__(self, paths):
        self.starts = []                      # (epoch, record, path)
        self.settled = {}                     # (ticker, want) -> [settled]
        self.by_tk = {}                       # ticker -> [settled]
        self.boosts = {}                      # path -> [band_boost / late_boost]
        self.cw_ref = []                      # K: refusals with gate cheap_window (one per skipped market)
        self.cw_set = {}                      # K: ticker -> its shadow's cheap_window_settled
        self.cb_ref = []                      # M: refusals with gate close_budget (one per market per close)
        self.ws_ref = []                      # WS: refusals with gate wrong_side (pinrun writes each one twice)
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
                    # (pinrun writes some records twice; two orders of one market in one second each write their own
                    # taper / order record, which the depth and fill fields tell apart)
                    key = (k, tk, r.get("t"), r.get("want"), r.get("side"), r.get("cost"), r.get("price"), r.get("n"),
                           r.get("client_order_id"), r.get("leg"), r.get("which"), r.get("outcome"), r.get("entry"),
                           r.get("gate"), r.get("take_n"), r.get("budget_left"), r.get("now"), r.get("tapered"),
                           r.get("flat"), r.get("filled"), r.get("order_id"))
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
                        elif r.get("gate") == "wrong_side":
                            self.ws_ref.append(r)
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
        self.ws_ref.sort(key=lambda r: (r["_epoch"], r["_i"]))
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

    def start_at(self, t):
        """The start record in force at epoch `t` (the latest at or before it), {} before the first."""
        got = {}
        for t0, r, _p in self.starts:
            if t0 > float(t) + 1e-9:
                break
            got = r
        return got

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

    def traj(self, path, close_s, wants=None):
        """The trajectory records of one close, {ticker: [records in time order]}, from the pintraj log of pin log
        `path` WHEREVER it is now (traj_window: results\\ while plain, read by a binary search on time, never the whole
        file; results\\archive\\<name>.gz once log_rotate moved it, through the small persisted row cache). `wants`
        {ticker: from epoch}: the markets asked and the second each is needed from (default: every market of the close
        from 120 s before it, as N reads it); {} when there is none. Memo'd per (path, close) for one report."""
        cs = int(_f(close_s))
        key = (path, cs, tuple(sorted((wants or {}).items())))
        got = self._traj.get(key)
        if got is not None:
            return got
        w = {(tk, cs): float(t0) for tk, t0 in (wants or {}).items()}
        got = traj_window(path, w, every=(None if wants else float(cs) - 120.0), close_s=cs)
        out = {}
        for (tk, _c), rows in got.items():
            out[tk] = rows
        self._traj[key] = out
        return out

    def window_net(self, since, window, until=None):
        """K: pin's own settled money, every leg, on the markets closing inside `window` from `since` on (to `until`),
        and how many of those markets have settled."""
        total, n = 0.0, 0
        for tk, legs in self.by_tk.items():
            c = close_of(tk)
            if c is None or c < since or (until is not None and c >= until) or not cw_in_window(c, window):
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
        # at most LOAD_KEEP of its own entries (each a state of pin's logs, ~41 MB parsed on the server's: the live log
        # grows between asks): the oldest go first, and only _load's own -- a ladder scan (key ("ladder", path)) stays,
        # so its incremental read is never thrown away
        mine = [k for k in _CACHE if k and isinstance(k, tuple) and isinstance(k[0], tuple)]
        for k in mine[:max(0, len(mine) - (LOAD_KEEP - 1))]:
            del _CACHE[k]
        got = _CACHE[key] = (_rw.Logs(list(paths)), Scan(list(paths)))
    return got


# ---------------------------------------------------------------------------
# A rule's periods (the 11-14 undo: results\pin_undo1114.ps1 restarts pin with M, K and WS off and B's cap dropped):
# from the first start record that switches the rule on, every start record's state until the next one. A rule's own
# events count only in its ON spans; from the first OFF span on, its row scores the UNDO against keeping the rule.
def rule_spans(S, on):
    """[(from epoch, to epoch or None, on?, start record)] from the first start record with on(record) True."""
    out, started = [], False
    for i, (t, r, _p) in enumerate(S.starts):
        o = bool(on(r))
        if not (started or o):
            continue
        started = True
        out.append((t, S.starts[i + 1][0] if i + 1 < len(S.starts) else None, o, r))
    return out


def span_at(spans, e):
    """The span of `spans` that epoch `e` falls in, or None (before the first)."""
    got = None
    for sp in spans:
        if e + 1e-9 >= sp[0] and (sp[1] is None or e < sp[1] - 1e-9):
            got = sp
    return got


def undo_since(spans):
    """The epoch of the first OFF span after an ON one (the undo), or None while the rule has never been switched off."""
    return next((sp[0] for sp in spans if not sp[2]), None)


def _m_on(r):
    return _f(r.get("extra_coin"), None) == 0.0 and _f(r.get("late_extra"), None) == 0.0


def _k_on(r):
    w = r.get("cheap_window")
    return isinstance(w, (list, tuple)) and len(w) == 3


def _ws_on(r):
    return _f(r.get("wrongside_rise_c"), 0.0) > 0.0


def _d_on(r):
    """D (v-boostrail, 0925t): the run's start record says boost_rail "off" (no rail ever trips; every losing leg of a
    boosted market writes boost_rail_kept). "any" (the revert, v-railany 11-16, and every build before 0925t's field)
    and "side" trip the rail: band_boost_off / late_boost_off."""
    return str(r.get("boost_rail") or "").strip().lower() == "off"


def _r_on(r):
    """R (v-hedge5live, 11-16): the run's start record says index_5hz "hedge" (the 5 Hz belief SENDS the hedge).
    "shadow" (v-hedge5, 11-10..11-16: recorded, nothing sent), "off" and a record without the field do not."""
    return str((r or {}).get("index_5hz") or "").strip().lower() == "hedge"


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


def _other(side):
    return "no" if side == "yes" else "yes"


def jump_live(st):
    """True when start record `st` runs the jump hedge for real: no --hedge-jump-shadow (pinrun refuses it next to
    --hedge-jump), and --hedge-jump set (a record of an older build without the field ran it: 10-24..11-08)."""
    st = st or {}
    return st.get("hedge_jump_shadow") is None and ("hedge_jump" not in st or st.get("hedge_jump") is not None)


def _b(S, now, since):
    """B (--hedge-jump-max 8) against never having the cap, from pin's own logs (the 11-14 retro's score_b.py):
    (a) each jump_capped (the first a position): the jump hedge the cap stopped, walked up the logged ladder to its
    limit, against what pin's real later hedges AND extra legs on that side did (a jump hedge covers the whole
    position, so the belief-line hedge and its extra never go out). It moves no money when it could not have filled:
    while the jump hedge is in shadow (11-08 on), an off-grid limit before --hedge-tick round (Kalshi refused every
    such order 11-01..11-04), an ask under --jump-hedge-min-ask (nothing is sent). (b) before the build that let the
    odds extra fire on any label (J's), a 'belief' hedge alarm on a jump at or over the cap: the cap turned the label
    to belief, so the 1.25x extra fired only because of it -- its own money is B's (+ when it paid). The extra legs in
    both are C's legs too (tally "extras": the total counts them once). Returns (events, tally)."""
    out = []
    t = {"priced": 0, "zero": 0, "label": 0, "extras": 0.0, "open": 0}
    seen, capped_tk = set(), set()
    for c in S.capped:
        if c["_epoch"] < since:
            continue
        key = (c["ticker"], c.get("want"))
        if key in seen:
            continue
        seen.add(key)
        capped_tk.add(c["ticker"])
        tk, want = c["ticker"], c.get("want")
        side = c.get("side") or _other(want)
        st = S.start_at(c["_epoch"])
        res = S.result(tk)
        status = _status(tk, res, now, c.get("close_s"))
        n, ask = _f(c.get("n")), _f(c.get("ask"), None)
        lim = _f(c.get("limit"), None)
        if lim is None and ask is not None:
            lim = min(ask + 0.10, 0.999)
        head = "a %s sd jump against %s with %s s left: the cap skipped a jump hedge of %s %s asking %s" % (
            ("%.1f" % _f(c.get("jump_sd"))) if c.get("jump_sd") is not None else "?", _side(want), c.get("tau", "?"),
            _g2(n), _side(side), _cents(ask))
        why = None
        bar = st.get("jump_hedge_min_ask")
        if not jump_live(st):
            why = "the jump hedge was in shadow then (it sends nothing either way)"
        elif ask is None or n <= 0:
            why = "nothing to hedge"
        elif (st.get("hedge_tick") or "") != "round" and off_grid(lim):
            why = ("its %s limit was off Kalshi's price grid (before --hedge-tick round Kalshi refused every such order): "
                   "nothing would have filled" % _cents(lim))
        elif bar is not None and ask < _f(bar) - 1e-9:
            why = "under the %s bar nothing would have been sent" % _cents(bar)
        if why:
            t["zero"] += 1
            out.append(_event(c, head + "; " + why + ": no money either way", 0.0, "scored"))
            continue
        fills = _rw.walk(c.get("ladder"), n, lim, [(ask, c.get("ask_size") or n)])
        if status != "scored":
            t["open"] += 1
            out.append(_event(c, head + "; not settled yet", None, status))
            continue
        flip = res == side
        jv = _rw.value(fills, flip)
        legs = [h for h in S.hedges + S.extras if h["ticker"] == tk and h.get("side") == side
                and h["_epoch"] >= c["_epoch"] - 1e-9 and h.get("status") == "executed" and _f(h.get("n")) > 0
                and h.get("price") is not None]
        rv = sum(_value(_f(h.get("n")), _f(h.get("price")), flip) for h in legs)
        xv = sum(_value(_f(h.get("n")), _f(h.get("price")), flip) for h in legs if h.get("kind") == "hedge_extra")
        usd = rv - jv
        t["priced"] += 1
        t["extras"] += round(xv, 2)
        words = head + "; the bet %s: pin's later hedges on that side %s %s%s, the jump hedge (%s at %s) would have %s %s, " \
                       "so the cap %s %s" % (
                           "LOST (a flip)" if flip else "won", "made" if rv >= 0 else "lost", _rw.usd(abs(rv), False),
                           (" (%s of it extra legs, C's too)" % _rw.usd(xv)) if abs(xv) > 0.004 else "",
                           _g2(_rw.got(fills)), _cents(_rw.avg_px(fills)), "made" if jv >= 0 else "lost",
                           _rw.usd(abs(jv), False), "made" if usd >= 0 else "cost", _rw.usd(abs(usd), False))
        out.append(_event(c, words, usd, "scored"))
    j_since = S.new_build_since()
    seen_a = set()
    for a in S.alarms:
        if a["_epoch"] < since or (j_since is not None and a["_epoch"] >= j_since) or a.get("trigger") != "belief":
            continue
        cap = S.start_at(a["_epoch"]).get("hedge_jump_max")
        if cap is None or a.get("jump_sd") is None or _f(a.get("jump_sd")) < _f(cap) - 1e-9:
            continue
        tk, want = a["ticker"], a.get("want")
        if tk in capped_tk or (tk, want) in seen_a:
            continue
        seen_a.add((tk, want))
        side = _other(want)
        res = S.result(tk)
        status = _status(tk, res, now, a.get("close_s"))
        ex = [x for x in S.extras if x["ticker"] == tk and x.get("side") == side and x["_epoch"] >= a["_epoch"] - 1e-9
              and x.get("status") == "executed" and _f(x.get("n")) > 0 and x.get("price") is not None]
        words = ("a %.1f sd jump at %.0f%% odds our way: the cap turned the alarm to 'belief', so the odds extra fired "
                 "(before the J build it rode only that label)" % (_f(a.get("jump_sd")), 100 * _f(a.get("belief"))))
        if not ex:
            t["label"] += 1
            out.append(_event(a, words + "; no extra leg filled: no money either way", 0.0, "scored"))
            continue
        if status != "scored":
            t["open"] += 1
            out.append(_event(a, words + "; not settled yet", None, status))
            continue
        usd = sum(_value(_f(x.get("n")), _f(x.get("price")), res == side) for x in ex)
        t["label"] += 1
        t["extras"] += round(usd, 2)
        words += "; %s extra %s at %s %s %s (C counts these too)" % (
            _g2(sum(_f(x.get("n")) for x in ex)), _side(side), _cents(_f(ex[0].get("price"))),
            "made" if usd >= 0 else "lost", _rw.usd(abs(usd), False))
        out.append(_event(a, words, usd, "scored"))
    return out, t


def _b_extra(t, dropped):
    """B's lines under its net: when the cap was dropped, then the capped alarms that moved no money. The extra legs
    only the cap made happen (C's legs too) are row["overlap_usd"]: the phone says them ON B's net line ('of it +$X is
    C's extra legs too'), where no shrink step drops them (the 11-14 review), and totals() takes them once."""
    out = []
    if dropped is not None:                              # (its since line says DROPPED too)
        out.append("the cap was DROPPED %s (pin started without --hedge-jump-max): nothing to count since"
                   % et_words(dropped))
    if t["zero"]:
        out.append("%d capped alarm%s moved no money (the jump hedge in shadow since 11-08, an off-grid limit before "
                   "--hedge-tick round, or under the 5c bar)" % (t["zero"], "" if t["zero"] == 1 else "s"))
    return out


D_BAND = (0.955, 0.981, 1.5)              # the old rule's band boost (0925r: BAND_MULTS), switched off after a trip
D_LATE_MULT, D_LATE_TAU = 1.5, 10         # ... and its late boost (LATE_MULT inside LATE_TAU)
D_EARLY_FRAC = 0.333                      # the early leg's share of the bet (pinrun EARLY_FRAC)


def _d_bm(p, on, band=D_BAND):
    """The old code's band multiple at ask p: 1.5 in the band while the band boost is on, else 1."""
    if not on or p is None:
        return 1.0
    return band[2] if band[0] - 1e-9 <= float(p) <= band[1] + 1e-9 else 1.0


def _d_count(o):
    try:
        return float((o.get("body") or {}).get("count"))
    except (TypeError, ValueError):
        return _f(o.get("filled"))


def _start_of(S, path):
    for _t, r, p in S.starts:
        if p == path:
            return r
    return {}


def d_market(S, path, tk, lst, band_off, late_off, res):
    """D: one market of a run after the old rule's trip, re-sized order by order the way the 0925r code would have
    (the analyst's d_cf.py, 11-14 retro): after a band trip band_mult is 1 everywhere in pin's sizing (the staged
    caps too: early = EARLY_FRAC x S x m, top-up / full = S x m - held, late add = min(take, 0.5 S, 1.5 S - held)),
    after a late trip LATE_MULT is 1; each order's counterfactual = min(its real count, that cap), its fill = min(the
    real fill, that count) (the same IOC limit and book). The late add tops the position up to 1.5 S - held: with a
    smaller position it buys MORE, from the book the smaller earlier legs left within 15 s (the refill). Hedges scale
    with the position they cover (the covering hedge by the covered order's cf / real fill, an extra leg by (mult - 1)
    x base_n x that). Money at the market's result, fee in per order. Returns (effect, legs, hedges, changed): effect
    = real - counterfactual (+ = the rail off made more)."""
    st = _start_of(S, path)
    sc = _f(((st.get("coin_size_frac") or {}).get(str(tk).split("-", 1)[0])), 1.0) or 1.0
    held_cf = {"yes": 0.0, "no": 0.0}
    legs, eff, changed = [], 0.0, False
    boosts = [b for b in S.boosts.get(path, []) if b.get("ticker") == tk]
    orders = [r for r in lst if r.get("kind") == "order"]
    for r in orders:
        fill = _f(r.get("filled"))
        if fill <= 0:
            continue
        want = r.get("want")
        px = _f(r.get("exec_price") if r.get("exec_price") is not None else r.get("limit_sent"))
        p = r.get("ask_seen")
        tau = _f(r.get("tau_at_send"), 99.0)
        leg = r.get("leg") or "full"
        size = S.size_at(path, r["_epoch"])[0] or 0.0
        S_ = float(size) * sc
        c = _d_count(r)
        late_cf = D_LATE_MULT if (tau <= D_LATE_TAU and not late_off) else 1.0
        m_cf = max(_d_bm(p, not band_off), late_cf)
        prev = max([o["_i"] for o in orders if o.get("want") == want and o["_i"] < r["_i"]] or [-1])
        bb = [b for b in boosts if b.get("kind") == "band_boost" and b.get("want") == want
              and prev < b["_i"] < r["_i"] and 0 <= r["_epoch"] - b["_epoch"] <= 2]
        lb = [b for b in boosts if b.get("kind") == "late_boost" and b.get("want") == want
              and prev < b["_i"] < r["_i"] and 0 <= r["_epoch"] - b["_epoch"] <= 2]
        if leg == "early":
            cap = D_EARLY_FRAC * S_ * m_cf
        elif leg in ("topup", "full"):
            cap = max(0.0, S_ * m_cf - held_cf.get(want, 0.0))
        elif leg == "late_add":
            cap = min(0.5 * S_, max(0.0, 1.5 * S_ - held_cf.get(want, 0.0)))
        else:
            cap = c
        if tau <= D_LATE_TAU and band_off and not late_off and bb:
            cap = min(cap, _f(bb[-1].get("was"), c))           # the band boost widened it in the late window
        if tau <= D_LATE_TAU and late_off and lb and m_cf < D_LATE_MULT:
            cap = min(cap, _f(lb[-1].get("was"), c),
                      max(0.0, S_ * m_cf - held_cf.get(want, 0.0)) if leg != "late_add" else c)
        f_cf = min(fill, min(c, cap))
        if leg == "late_add":
            left = sum(L["fill"] - L["fill_cf"] for L in legs if L["want"] == want and r["_epoch"] - L["e"] <= 15)
            take = _f(bb[-1].get("was"), c) if bb else c + left
            f_cf = max(0.0, min(take, cap, fill + left))
        if not size:
            f_cf = fill                                   # no SIZE in the log: nothing to re-size it by
        if abs(fill - f_cf) > 1e-6:
            changed = True
        if res is not None:
            eff += _value(fill, px, res == want) - (_value(f_cf, px, res == want) if f_cf > 0 else 0.0)
        held_cf[want] = held_cf.get(want, 0.0) + f_cf
        legs.append({"e": r["_epoch"], "leg": leg, "want": want, "px": px, "fill": fill, "fill_cf": f_cf})
    hedges = []
    for h in lst:
        if h.get("kind") not in ("hedge", "hedge_extra") or h.get("status") != "executed" or _f(h.get("n")) <= 0:
            continue
        n, side = _f(h.get("n")), h.get("side")
        pos_side = "no" if side == "yes" else "yes"
        pos = _f(h.get("asked"), n) if h.get("kind") == "hedge" else _f(h.get("base_n"))
        ent = h.get("entry")
        cand = [L for L in legs if L["want"] == pos_side and L["e"] <= h["_epoch"] + 1e-6]
        scale = 1.0
        if cand:
            L0 = min(cand, key=lambda L: (abs(L["fill"] - pos), abs(L["px"] - _f(ent, L["px"]))))
            scale = (L0["fill_cf"] / L0["fill"]) if L0["fill"] > 0 else 1.0
        if h.get("kind") == "hedge":
            n_cf = min(n, _f(h.get("asked"), n) * scale)
        else:
            n_cf = min(n, (_f(h.get("mult"), 1.25) - 1.0) * _f(h.get("base_n")) * scale)
        hp = _f(h.get("price"))
        if abs(n - n_cf) > 1e-6:
            changed = True
        if res is not None:
            eff += _value(n, hp, res == side) - (_value(n_cf, hp, res == side) if n_cf > 0 else 0.0)
        hedges.append({"n": n, "n_cf": n_cf, "side": side})
    return eff, legs, hedges, changed


def _d(S, now, since, spans=None):
    """D: the boost rail off (0925t, --boost-rail off) against the 0925r rule "any", which switched the band boost
    (and, on its own trip, the late boost) off for the rest of a run at the first losing leg of a boosted market. The
    trip is where pinrun writes boost_rail_kept (the first of each kind in a run, from `since` on); every market of
    that run whose first fill came after it is re-sized order by order (d_market) -- not only the band_boost records:
    the staged-entry limits size 1.5x without one -- hedges and the late-add refill in. One event per market whose
    contracts differ, usd = real - counterfactual, open until the market settles. `spans` (rule_spans(S, _d_on)): only
    a trip, and a market first filled, inside an ON span (boost_rail "off") counts -- after the revert (v-railany,
    --boost-rail any) pinrun writes no boost_rail_kept, and should one ever appear there it is not D's. None = every
    trip from `since` on (no span test). Returns (events, tally)."""
    out = []
    tally = {"trips": 0, "runs": 0, "markets": 0, "changed": 0, "open": 0, "same": 0}
    trips = {}

    def _on(e):
        if spans is None:
            return True
        sp = span_at(spans, e)
        return sp is not None and bool(sp[2])
    for K in S.kept:
        if K["_epoch"] < since or not _on(K["_epoch"]):
            continue
        trips.setdefault(K["_path"], {}).setdefault(K.get("which") or "band", K)
    tally["runs"] = len(trips)
    tally["trips"] = sum(len(v) for v in trips.values())
    recs = {}
    for pool in (S.orders, S.hedges, S.extras):
        for r in pool:
            if r["_path"] in trips:
                recs.setdefault((r["_path"], r["ticker"]), []).append(r)
    for (path, tk), lst in sorted(recs.items(), key=lambda kv: min(r["_epoch"] for r in kv[1])):
        lst.sort(key=lambda r: r["_i"])
        fills = [r for r in lst if r.get("kind") == "order" and _f(r.get("filled")) > 0]
        if not fills:
            continue
        t0 = fills[0]["_epoch"]
        tp = trips[path]
        band_off = "band" in tp and t0 > tp["band"]["_epoch"]
        late_off = "late" in tp and t0 > tp["late"]["_epoch"]
        if not (band_off or late_off) or not _on(t0):
            continue
        tally["markets"] += 1
        res = S.result(tk)
        eff, legs, hedges, changed = d_market(S, path, tk, lst, band_off, late_off, res)
        if not changed:
            tally["same"] += 1
            continue
        tally["changed"] += 1
        st = _status(tk, res, now)
        trip = tp["band"] if band_off else tp["late"]
        real = sum(L["fill"] for L in legs)
        cf = sum(L["fill_cf"] for L in legs)
        notes = (["its hedges scaled with it"] if hedges else []) + (["the late add's refill in"] if any(
            L["leg"] == "late_add" and L["fill_cf"] > L["fill"] + 1e-6 for L in legs) else [])
        words = ("bought after the old rule's %s-boost trip (%s, a losing %s leg): the boost stayed on, so %s contracts "
                 "instead of the old rule's %s%s" % (
                     "band" if band_off else "late", et_words(trip["_epoch"], with_day=False), _side(trip.get("leg_side")),
                     _g2(real), _g2(cf), (" (%s)" % ", ".join(notes)) if notes else ""))
        if st == "scored":
            won = res == fills[0].get("want")
            words += "; the bet %s: the boost rail off %s %s" % ("won" if won else "LOST", "made" if eff >= 0 else "cost",
                                                                 _rw.usd(abs(eff), False))
        else:
            tally["open"] += 1
            words += "; not settled yet"
        out.append(_event(fills[0], words, eff if st == "scored" else None, st))
    return out, tally


def _d_extra(t):
    if not t["runs"]:
        return ["the old rule has not tripped in any run since the build (no boost_rail_kept yet): nothing to re-size"]
    return ["re-sized order by order as the old rule would have: %d market%s after %d trip%s, %d sized the same%s; the "
            "boost itself (1.5x on every 95.5-98.1c buy) is not this row" % (
                t["changed"], "" if t["changed"] == 1 else "s", t["trips"], "" if t["trips"] == 1 else "s", t["same"],
                (" · %d open" % t["open"]) if t["open"] else "")]


# ---------------------------------------------------------------------------
# D's revert (v-railany, 2026-11-16 11:08:53Z, results\pin_railany.ps1: pin restarted on --boost-rail any): in a run on
# "any" (or "side") the first losing leg on a boosted market switches that boost off for the rest of the run (pinrun
# writes band_boost_off / late_boost_off and sets BAND_MULTS = () / LATE_MULT = 1). The undo prices, market by market
# after such a trip, what KEEPING D -- the boost staying on -- would have bought (d_keep, the inverse of d_market).
D_REBUY_LATE_FRAC = 0.5                   # the late add's share of the bet (pinrun REBUY_LATE_FRAC; d_market's 0.5 / 1.5)


def d_bands(start, trip=None):
    """[(lo, hi, mult)] of the band boost KEEPING D would have run: the band trip's `was` (pinrun writes the band mults
    it switched off), else the run's start record's band_mults, else D_BAND."""
    for src in ((trip or {}).get("was"), (start or {}).get("band_mults")):
        out = []
        for b in (src if isinstance(src, (list, tuple)) else []):
            if isinstance(b, (list, tuple)) and len(b) >= 3:
                lo, hi, m = _f(b[0], None), _f(b[1], None), _f(b[2], None)
                if None not in (lo, hi, m):
                    out.append((lo, hi, m))
        if out:
            return out
    return [D_BAND]


def d_band_mult(p, bands):
    """pinrun.band_mult: the largest multiple of a band with lo <= p < hi, else 1.0 (never under 1)."""
    if p is None:
        return 1.0
    p = _f(p, None)
    if p is None:
        return 1.0
    return max([1.0] + [m for lo, hi, m in bands if lo - 1e-9 <= p < hi - 1e-9])


def d_depth(ladder, limit):
    """The contracts an ask ladder [[price, size], ...] holds at or under `limit`: what an order at that limit could
    take (pinrun's book.buyable at the sweep limit, the band boost's `avail`)."""
    return sum(_f(lv[1]) for lv in (ladder or []) if isinstance(lv, (list, tuple)) and len(lv) >= 2
               and _f(lv[0], 9.0) <= float(limit) + 1e-9)


def d_book(o, sg, recs, size, px):
    """The book order `o` could have taken at its limit -- _band53's `avail`, pinrun's book.buyable at the sweep limit --
    read off the order's OWN records between its signal and it (`recs`: the market's taper / sweep_depth records of its
    side, any order): A35's taper record's `flat` (written when the taper cut the depth), else its sweep_depth record's
    `ladder` (the depth it swept, untapered when no taper record was written). With neither, when the touch alone was
    under SIZE, the sweep found nothing past it: the order's own count (nothing to add). Else (the touch was SIZE or
    more, the sweep had nothing to raise) its signal's ladder at or under its limit_sent; no signal: its own fill. The
    11-16 check on the real 'off' runs: the signal's ladder alone read up to twice the book the sweep saw a moment
    later (NEAR 11-06 8:15 AM: 255 against 121), so d_keep would have bought on depth that was gone."""
    if sg is None:
        return _f(o.get("filled"))
    lo, hi = sg["_i"], o["_i"]
    mine = [r for r in recs if lo < r["_i"] < hi]
    tap = [r for r in mine if r.get("kind") == "taper" and r.get("flat") is not None]
    if tap:
        return _f(tap[-1].get("flat"))
    swp = [r for r in mine if r.get("kind") == "sweep_depth" and r.get("ladder") is not None]
    if swp:
        return _f(swp[-1].get("ladder"))
    touch = _f(sg.get("take_n"), None)
    if touch is not None and size and touch < float(size) - 0.01:
        return max(_d_count(o), _f(o.get("filled")))
    return d_depth(sg.get("ladder"), _f(o.get("limit_sent"), px))


def d_cents(n_cf, n):
    """A kept count as pinrun would send it: to 2 decimals (pin's order path sends counts to the cent), and the real count
    itself when within a cent of it (0.333 x 342 x 1.5 = 170.829 is the 170.83 that went out, not a change)."""
    return float(n) if abs(float(n_cf) - float(n)) < 0.01 - 1e-9 else round(float(n_cf), 2)


def d_trip_side(S, trip):
    """The side of the losing leg that tripped the rail: the trip ticker's settled leg nearest its cost and pnl_c
    (band_boost_off / late_boost_off carry no side), else None."""
    legs = [r for r in S.by_tk.get(trip.get("ticker"), []) if r.get("result") in ("yes", "no")]
    if not legs:
        return None
    legs.sort(key=lambda r: (abs(_f(r.get("cost")) - _f(trip.get("cost"))),
                             abs(_f(r.get("pnl_c")) - _f(trip.get("pnl_c")))))
    return legs[0].get("want")


def d_keep(S, path, tp, mkts, ctx):
    """D's revert, ONE run: the markets `mkts` {ticker: its orders, hedges and extras} (each first filled after the
    run's trip; `tp` {"band"/"late": the first band_boost_off / late_boost_off}) re-sized UP to what KEEPING D (the boost
    never switched off) would have bought -- the inverse of d_market. The orders go in file order across the markets
    (one close's budget is shared). Each filled order's multiple m is the boost's with both boosts on: the band
    multiple at its ask, the late multiple inside late_tau; it sets the order's cap the staged way (pinrun _stage46 /
    _fullcap): an early leg EARLY_FRAC x S x m, a top-up or full leg S x m less what that side holds by then, a late add
    min(0.5 S, 1.5 S - held) (no widener raises a late add: it can only shrink). The order can GROW only where the
    boost the rail switched off would have widened it (_band53: the band trip came first and its ask is in the band;
    _late48: the late trip came first, inside late_tau, the signal's confidence at late_pin -- the boost's own bar):
    then it buys up to that cap, held to the close's budget its signal had left (less what keeping D bought before it
    in that close), to the drawdown headroom (one_coin_cap off the latest bank reading, when the log has one) and to the
    BOOK: an order that filled LESS than it asked had the book as its limit (the IOC remainder was cancelled), so it
    fills the same; one that filled whole adds at most the book it could have taken past what it filled (d_book: its
    own sweep's reading, else its signal's ladder at or under its limit_sent -- the signal the latest within 3 s,
    m_contexts; no signal: nothing added). The 11-16 check on the real 'off' runs (the boost really on, each run's
    first boost_rail_kept read as a trip): d_keep kept 652 of 657 markets exactly as pinrun sized them (-$5.23 in
    all). Any other order fills min(its fill, that cap, that budget) -- a top-up after a bigger kept early leg buys
    less. A band99 leg, a ladder rung and a --coin-size-frac coin stay as they were (pinrun skips both boosts there;
    _ssz / _csz cap after every widener). Hedges scale with the position they cover as d_market scales them (the covered leg's kept / real fill),
    never past their own book (the hedge record's ladder at its limit_sent, less what an earlier hedge leg of the same
    second took; a partly filled hedge fills the same). Returns {ticker: (legs, hedges)}: legs [{e, leg, want, px, fill,
    fill_cf, held_by}] (held_by: None, "book", "partial", "budget", "headroom"), hedges [{n, n_cf, side, hp}]."""
    st = _start_of(S, path)
    tb, tl = tp.get("band"), tp.get("late")
    bands = d_bands(st, tb)
    late_m = _f((tl or {}).get("was"), None) or _f(st.get("late_mult"), None) or D_LATE_MULT
    late_tau = _f(st.get("late_tau"), D_LATE_TAU)
    late_pin = _f(st.get("late_pin"), M_LATE_PIN)
    efrac = _f(st.get("early_frac"), None) or D_EARLY_FRAC
    skip = set(_LADDER_COIN) | set(st.get("ladder_series") or []) | set((st.get("coin_size_frac") or {}).keys())
    own = {}                                  # (ticker, want) -> the run's taper / sweep_depth records of these markets
    for r in S.tapers + S.sweeps:
        if r["_path"] == path and r["ticker"] in mkts:
            own.setdefault((r["ticker"], r.get("want")), []).append(r)
    held_cf, extra = {}, {}
    legs = {tk: [] for tk in mkts}
    for o in sorted((r for lst in mkts.values() for r in lst if r.get("kind") == "order"), key=lambda r: r["_i"]):
        fill = _f(o.get("filled"))
        if fill <= 0:
            continue
        tk, want, e = o["ticker"], o.get("want"), o["_epoch"]
        sg = (ctx.get(id(o)) or {}).get("sg")
        px = _f(o.get("exec_price") if o.get("exec_price") is not None else o.get("limit_sent"))
        p = o.get("ask_seen") if o.get("ask_seen") is not None else (sg or {}).get("price")
        tau = _f(o.get("tau_at_send") if o.get("tau_at_send") is not None else (sg or {}).get("tau"), 99.0)
        leg = o.get("leg") or "full"
        c = _d_count(o)
        cs = close_of(tk)
        size = S.size_at(path, e)[0]
        h_cf = held_cf.get((tk, want), 0.0)
        bm = d_band_mult(p, bands)
        late_in = tau <= late_tau + 1e-9
        m_cf = max(bm, late_m if late_in else 1.0)
        held_by = None
        if (o.get("band99") or leg not in ("early", "topup", "full", "late_add") or not size
                or str(tk).split("-", 1)[0] in skip):
            f_cf = fill
        else:
            S_ = float(size)
            if leg == "early":
                cap = efrac * S_ * m_cf
            elif leg == "late_add":
                cap = max(0.0, min(D_REBUY_LATE_FRAC * S_, (1.0 + D_REBUY_LATE_FRAC) * S_ - h_cf))
            else:
                cap = max(0.0, S_ * m_cf - h_cf)
            bl = _f((sg or {}).get("budget_left"), None)
            room = (bl - extra.get(cs, 0.0)) if bl is not None else None
            conf = None
            if sg is not None and sg.get("fair") is not None:
                conf = _f(sg.get("fair")) if want == "yes" else 1.0 - _f(sg.get("fair"))
            band_w = tb is not None and e > tb["_epoch"] and bm > 1.0
            late_w = (tl is not None and e > tl["_epoch"] and late_in and conf is not None
                      and conf >= late_pin - 1e-12)
            limit = min(cap, room) if room is not None else cap
            if leg != "late_add" and (band_w or late_w) and limit > fill + 1e-6:
                bank, hwm = _m_bank(S, path, e)
                if bank is not None and hwm:
                    hr = m_one_coin_cap(S_, bank, hwm, max(bm if band_w else 1.0, late_m if late_w else 1.0))
                    if hr < limit - 1e-9:
                        limit, held_by = hr, "headroom"
                if fill < c - 0.01:
                    f_cf, held_by = fill, "partial"          # the book was its limit: the IOC remainder cancelled
                else:
                    book = d_book(o, sg, own.get((tk, want), []), S_, px)
                    add = min(limit - fill, max(0.0, book - fill))
                    if add < limit - fill - 1e-6:
                        held_by = "book"
                    elif room is not None and room <= cap and held_by is None:
                        held_by = "budget"
                    f_cf = fill + max(0.0, add)
            else:
                f_cf = max(0.0, min(fill, limit))
        f_cf = d_cents(f_cf, fill)
        held_cf[(tk, want)] = h_cf + f_cf
        extra[cs] = extra.get(cs, 0.0) + f_cf - fill
        legs[tk].append({"e": e, "leg": leg, "want": want, "px": px, "fill": fill, "fill_cf": f_cf, "held_by": held_by})
    out = {}
    for tk, lst in mkts.items():
        L, hedges, used = legs[tk], [], {}
        for h in sorted(lst, key=lambda r: r["_i"]):
            if h.get("kind") not in ("hedge", "hedge_extra") or h.get("status") != "executed" or _f(h.get("n")) <= 0:
                continue
            n, side = _f(h.get("n")), h.get("side")
            pos_side = "no" if side == "yes" else "yes"
            asked = _f(h.get("asked"), n)
            pos = asked if h.get("kind") == "hedge" else _f(h.get("base_n"))
            ent = h.get("entry")
            cand = [x for x in L if x["want"] == pos_side and x["e"] <= h["_epoch"] + 1e-6]
            scale = 1.0
            if cand:
                L0 = min(cand, key=lambda x: (abs(x["fill"] - pos), abs(x["px"] - _f(ent, x["px"]))))
                scale = (L0["fill_cf"] / L0["fill"]) if L0["fill"] > 0 else 1.0
            if h.get("kind") == "hedge":
                want_n = asked * scale
            else:
                want_n = (_f(h.get("mult"), 1.25) - 1.0) * _f(h.get("base_n")) * scale
            key = (side, h.get("t_ms_decide") or h.get("t"))
            if want_n <= n + 1e-9:
                n_cf = max(0.0, want_n)
            elif n < asked - 0.01:
                n_cf = n                                     # a partly filled hedge: the book was its limit
            else:
                book = d_depth(h.get("ladder"), _f(h.get("limit_sent"), _f(h.get("price"))))
                n_cf = n + max(0.0, min(want_n - n, book - used.get(key, 0.0) - n))
            n_cf = d_cents(n_cf, n)
            used[key] = used.get(key, 0.0) + n_cf
            hedges.append({"n": n, "n_cf": n_cf, "side": side, "hp": _f(h.get("price"))})
        out[tk] = (L, hedges)
    return out


def _d_undo(S, now, spans):
    """D after the revert (a start record on boost_rail "any" or "side" after an "off" one): in each such run, from its
    first band_boost_off / late_boost_off, every market whose first fill came after it, re-sized up to KEEPING D
    (d_keep); one event per market whose contracts differ, usd = real - kept, at the market's result, fee in per order
    (+ = the revert made money: the boosted extra would have lost; - = it would have won). Open until the market
    settles. Returns (events, tally)."""
    out = []
    t = {"trips": 0, "runs": 0, "markets": 0, "changed": 0, "open": 0, "same": 0}
    if undo_since(spans) is None:
        return out, t
    trips = {}
    for K in S.boost_offs:
        sp = span_at(spans, K["_epoch"])
        if sp is None or sp[2]:
            continue
        trips.setdefault(K["_path"], {}).setdefault("band" if K.get("kind") == "band_boost_off" else "late", K)
    t["runs"] = len(trips)
    t["trips"] = sum(len(v) for v in trips.values())
    if not trips:
        return out, t
    by = {}
    for pool in (S.orders, S.hedges, S.extras):
        for r in pool:
            if r["_path"] in trips:
                by.setdefault(r["_path"], {}).setdefault(r["ticker"], []).append(r)
    ctx = {id(x["o"]): x for x in m_contexts(S)}
    for path, tp in trips.items():
        mkts, first = {}, {}
        for tk, lst in by.get(path, {}).items():
            fills = sorted((r for r in lst if r.get("kind") == "order" and _f(r.get("filled")) > 0),
                           key=lambda r: r["_i"])
            if not fills:
                continue
            t0 = fills[0]["_epoch"]
            if not any(t0 > K["_epoch"] for K in tp.values()):
                continue                                  # bought before the trip: the boost was on for it
            sp = span_at(spans, t0)
            if sp is None or sp[2]:
                continue
            mkts[tk], first[tk] = lst, fills[0]
        kept = d_keep(S, path, tp, mkts, ctx)
        for tk in sorted(mkts, key=lambda k: (first[k]["_epoch"], first[k]["_i"])):
            L, H = kept[tk]
            t["markets"] += 1
            changed = any(abs(x["fill"] - x["fill_cf"]) > 1e-6 for x in L) or any(
                abs(h["n"] - h["n_cf"]) > 1e-6 for h in H)
            if not changed:
                t["same"] += 1
                continue
            t["changed"] += 1
            res = S.result(tk)
            st = _status(tk, res, now)
            o0 = first[tk]
            trip = tp["band"] if ("band" in tp and o0["_epoch"] > tp["band"]["_epoch"]) else tp["late"]
            real = sum(x["fill"] for x in L)
            cf = sum(x["fill_cf"] for x in L)
            notes = (["its hedges scaled with it"] if any(abs(h["n"] - h["n_cf"]) > 1e-6 for h in H) else []) + (
                ["the book held it"] if any(x["held_by"] in ("book", "partial") and x["fill_cf"] > x["fill"] - 1e-6
                                            for x in L) else [])
            side = d_trip_side(S, trip)
            sized = ("so %s contracts instead of keeping D's %s" % (_g2(real), _g2(cf)) if abs(real - cf) >= 0.005 else
                     "and keeping D would have bought the same %s contracts, spread over its legs differently" % _g2(real))
            words = "%s: bought after the %s-boost trip (%s, a losing %sleg): the rail kept the boost off, %s%s" % (
                UNDO_WORDS, "band" if trip.get("kind") == "band_boost_off" else "late",
                et_words(trip["_epoch"], with_day=False), (_side(side) + " ") if side else "", sized,
                (" (%s)" % ", ".join(notes)) if notes else "")
            eff = None
            if st == "scored":
                eff = 0.0
                for x in L:
                    w = res == x["want"]
                    eff += _value(x["fill"], x["px"], w) - (_value(x["fill_cf"], x["px"], w) if x["fill_cf"] > 0 else 0.0)
                for h in H:
                    w = res == h["side"]
                    eff += _value(h["n"], h["hp"], w) - (_value(h["n_cf"], h["hp"], w) if h["n_cf"] > 0 else 0.0)
                won = res == o0.get("want")
                words += "; the bet %s: the revert %s %s" % ("won" if won else "LOST",
                                                             "cost" if eff < 0 else ("made" if won else "saved"),
                                                             _rw.usd(abs(eff), False))
            else:
                t["open"] += 1
                words += "; not settled yet" if st == "pending" else "; no result 3 h after the close (unknown)"
            out.append(_event(o0, words, eff, st))
    return out, t


def _d_undo_note(t):
    """The undo's note under D's row (the phone's last line, and the end of its undo line)."""
    if not t["trips"]:
        return "no rail trip yet (no band_boost_off / late_boost_off): nothing to re-size"
    if t["same"]:
        return "%d more market%s after the trip%s the boost would not have changed (the book, the budget or the leg's " \
               "own cap)" % (t["same"], "" if t["same"] == 1 else "s", "" if t["trips"] == 1 else "s")
    return None


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


def market_money(S, tk):
    """pin's own settled money in market `tk`, every leg (its buys, hedges and extras, fee in: pinrun writes one
    settled record per side and cost, legs at one price merged), or None until the market has settled. pinrun books
    each leg on its own (one GET per ticker every 15 s): measured 11-14, 261 of 1,573 settled markets had 2+ legs, a
    median 15 s apart (max 45 s), so a read between them sees a part (this page reads again and heals; a one-shot
    alert must wait for two equal reads, pinrules_watch.new_undo_losses)."""
    legs = [r for r in S.by_tk.get(tk, []) if r.get("result") in ("yes", "no")]
    if not legs:
        return None
    return sum(_f(r.get("pnl_c")) for r in legs) / 100.0


def first_looks(S, spans):
    """[(ticker, its first filled order, the signals of it up to that order)] for every market whose first filled order
    falls in an OFF span of `spans` (after the undo): the looks a rule judging FIRST buys would have judged."""
    first, sigs = {}, {}
    for o in S.orders:
        if _f(o.get("filled")) > 0:
            k = o["ticker"]
            if k not in first or (o["_epoch"], o["_i"]) < (first[k]["_epoch"], first[k]["_i"]):
                first[k] = o
    for sg in S.signals:
        if sg.get("live") is not False:
            sigs.setdefault(sg["ticker"], []).append(sg)
    out = []
    for tk, o in sorted(first.items(), key=lambda kv: kv[1]["_epoch"]):
        sp = span_at(spans, o["_epoch"])
        if sp is None or sp[2]:
            continue
        looks = [s for s in sigs.get(tk, []) if s["_i"] <= o["_i"] and s["_epoch"] >= sp[0] - 1e-9]
        out.append((tk, o, looks, sp))
    return out


def _undo_event(S, now, tk, o, words, verb_won="made"):
    """One market the undone rule would have skipped: its whole money (every leg of pin's, hedges in) is what the undo
    made (+) or lost (-) against keeping the rule. Open until every leg has settled."""
    usd = market_money(S, tk)
    res = S.result(tk)
    st = _status(tk, res if usd is not None else None, now)
    if st == "scored":
        words += "; the market %s: the undo %s %s" % ("won" if usd >= 0 else "LOST", verb_won if usd >= 0 else "cost",
                                                     _rw.usd(abs(usd), False))
    else:
        words += "; not settled yet" if st == "pending" else "; no result 3 h after the close (unknown)"
    return _event(o, words, usd if st == "scored" else None, st)


def _k(S, now, spans):
    """K: each market the cheap window skipped while the rule was ON (the first refusal a market), priced by
    cw_shadow_usd: + saved (the skipped buy would have lost), - gave up (it would have won). Skips of one close share
    its budget in refusal order (a later one gets only what the earlier ones left of the refusal's budget_left).
    Returns (events, {won, flipped, open, without_usd})."""
    out, tally = [], {"won": 0, "flipped": 0, "open": 0, "without_usd": 0.0}
    picked, seen = [], set()
    for r in S.cw_ref:
        sp = span_at(spans, r["_epoch"])
        if sp is None or not sp[2] or r["ticker"] in seen:
            continue
        seen.add(r["ticker"])
        picked.append(r)
    scale, spent = {}, {}
    for r in picked:
        cs = int(_f(r.get("close_s"), close_of(r["ticker"]) or 0))
        w = cw_n_ask(S.cw_set.get(r["ticker"]), r) * K_FILL
        bl = _f(r.get("budget_left"), None)
        room = max(0.0, (bl if bl is not None else 1e12) - spent.get(cs, 0.0))
        got = min(w, room)
        scale[id(r)] = (got / w) if w > 0 else 1.0
        spent[cs] = spent.get(cs, 0.0) + got
    for r in picked:
        tk, side = r["ticker"], r.get("want")
        s = S.cw_set.get(tk)
        shadow = cw_shadow_usd(s, r, scale[id(r)]) if s else None
        st = _status(tk, (s or {}).get("result") if shadow is not None else None, now, r.get("close_s"))
        words = "skipped a first %s buy at %s with %s s left (about %.0f contracts%s)" % (
            _side(side), _cents(r.get("price")), r.get("tau", "?"), cw_contracts(s, r, scale[id(r)]),
            ", the close's budget shared" if scale[id(r)] < 0.999 else "")
        if st == "scored":
            won = s.get("result") == side
            tally["won" if won else "flipped"] += 1
            tally["without_usd"] += round(shadow, 2)     # the events' cents, so the line and the net agree
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


def _k_extra(S, tally, since, window, until=None):
    """K's lines under the net: what the skipped buys would have done, the window with and without the rule (from
    `since` to `until`, the undo, when there is one) and the assumptions its prices rest on."""
    if window is None:
        return []
    span = "%s to %s ET" % (_hour(window[0]), _hour(window[1]))
    n = tally["won"] + tally["flipped"]
    w = tally["without_usd"]
    lines = ["without the rule: the %d settled skip%s would have %s %s (%d won, %d flipped, hedges in)%s" % (
        n, "" if n == 1 else "s", "made" if w >= 0 else "lost", _rw.usd(abs(w), False), tally["won"], tally["flipped"],
        (" \u00b7 %d still open" % tally["open"]) if tally["open"] else "")]
    kept, markets = S.window_net(since, window, until)
    lines.append("closes %s %s (%d settled market%s): pin made %s with it, %s without it" % (
        span, "while the rule was on" if until else "since the rule", markets, "" if markets == 1 else "s",
        _rw.usd(kept), _rw.usd(kept + w)))
    lines.append("priced on pin's own 6-10 ET cheap first buys before the rule: a win at %.3f (full leg) / %.3f (early "
                 "leg) of n_ask x the edge, hedge-free; a flip at a %.3f fill (assumptions)" % (
                     K_WIN["full"], K_WIN["early"], K_FILL_FLIP))
    return lines


def _k_undo(S, now, spans, skip_tks=()):
    """K after the undo (a start record without cheap_window): each market closing inside the old window whose first
    buy -- any look of pin's before its first fill -- was under the old floor: the rule would have skipped the whole
    market, so its whole money is what the undo made (+) or lost (-) against keeping the rule. A market the wrong-side
    rule would have skipped first (pinrun's gate order) is WS's, not counted here (skip_tks). Returns (events, tally,
    the tickers counted: M's undo leaves their 3rd bets to this row, the whole market is here)."""
    out, t, tks = [], {"n": 0, "open": 0, "ws": 0}, set()
    last_on = [sp[3] for sp in spans if sp[2]]
    if not last_on or undo_since(spans) is None:
        return out, t, tks
    w = last_on[-1].get("cheap_window")
    for tk, o, looks, _sp in first_looks(S, spans):
        cs = close_of(tk)
        if cs is None or not cw_in_window(cs, w):
            continue
        cheap = [s for s in looks if s.get("price") is not None and _f(s.get("price")) < float(w[2]) - 1e-9]
        if not cheap:
            continue
        if tk in skip_tks:
            t["ws"] += 1
            continue
        s0 = cheap[0]
        words = "%s: a first %s buy at %s with %s s left in a %s close (the rule skipped such markets)" % (
            UNDO_WORDS, _side(s0.get("want")), _cents(_f(s0.get("price"))), s0.get("tau", "?"),
            et_words(cs, with_day=False))
        ev = _undo_event(S, now, tk, o, words)
        tks.add(tk)
        t["n"] += 1
        t["open"] += 1 if ev["open"] else 0
        out.append(ev)
    return out, t, tks


# ---------------------------------------------------------------------------
# WS (v-wrongside / LS20, --wrongside-rise-c 1.0, live 10-27 9:07 PM ET): each first buy refused as wrong_side, priced
# against never having the rule (the 11-14 retro's skeptic, retro_skeptic_WS mine.py / mine2.py, the conservative one)
def ws_bucket(p):
    """The first-ask bucket (WS_BUCKETS) a price falls in (under 94c: the first; 98.01c and over: the last)."""
    p = _f(p)
    for lo, hi in WS_BUCKETS:
        if lo <= p < hi:
            return (lo, hi)
    return WS_BUCKETS[0] if p < WS_BUCKETS[0][1] else WS_BUCKETS[-1]


def ws_stats(S, since, until=None):
    """pin's OWN 15-minute markets with a fill from `since` on (and, with `until` -- the undo --, a first fill before
    it: the rule's figure stops moving once the rule is off), by the first fill's ask bucket: {bucket: {"won":
    [market money / the coin's bet] of the won markets pin never hedged (top-ups, slip, fees in), "held": [contracts on
    the first side / the bet] of every settled market}} -- what a skipped first buy at that price would have become."""
    first = {}
    for o in S.orders:
        if "15M-" not in str(o["ticker"]) or _f(o.get("filled")) <= 0 or o["_epoch"] < since:
            continue
        if until is not None and o["_epoch"] >= until - 1e-9:
            continue
        k = o["ticker"]
        if k not in first or (o["_epoch"], o["_i"]) < (first[k]["_epoch"], first[k]["_i"]):
            first[k] = o
    hedged = {h["ticker"] for h in S.hedges + S.extras if h.get("status") == "executed" and _f(h.get("n")) > 0}
    out = {}
    for tk, o in first.items():
        usd = market_money(S, tk)
        res = S.result(tk)
        size = S.size_at(o["_path"], o["_epoch"])[0]
        if usd is None or res is None or not size:
            continue
        bet = m_full(tk, size, None, _start_of(S, o["_path"]))
        if bet <= 0:
            continue
        b = out.setdefault(ws_bucket(o.get("ask_seen") if o.get("ask_seen") is not None else o.get("exec_price")),
                           {"won": [], "held": []})
        held = sum(_f(x.get("filled")) for x in S.orders if x["ticker"] == tk and x.get("want") == o.get("want"))
        b["held"].append((o.get("leg") or "full", held / bet))
        if res == o.get("want") and tk not in hedged:
            b["won"].append(usd / bet)
    return out


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def ws_rates(stats, bucket, leg="full"):
    """(won $ per contract of bet, contracts held per contract of bet -- over the markets whose first fill was the same
    kind of leg --, how many won markets priced it) for `bucket`; a bucket pin has no market in takes every bucket's
    pool (n 0, said on the line)."""
    b = stats.get(bucket) or {}
    u = _mean(b.get("won") or [])
    n = len(b.get("won") or [])
    h = _mean([x for lg, x in b.get("held") or [] if lg == leg]) or _mean([x for _lg, x in b.get("held") or []])
    if u is None:
        u = _mean([x for v in stats.values() for x in v.get("won") or []])
        n = 0
    if h is None:
        h = _mean([x for v in stats.values() for lg, x in v.get("held") or [] if lg == leg])
    return (u or 0.0), (h if h is not None else 1.0), n


def ws_hedge(rows, want, st):
    """The hedge pin would have bought on a skipped position, replayed on the trajectory's seconds after the refusal
    (rows in time order, tau 1 or more) with the start record `st` in force: the belief hedge the first second our
    side's belief (the row's fair is the Yes probability) is under hedge_belief and the other side has an ask (x
    hedge_odds_mult with hedge_odds_min_tau or more left); the jump hedge only while it is LIVE (hedge_jump set, no
    hedge_jump_shadow), on a 1-s index move against us of hedge_jump sd or more, under hedge_jump_max, at or over
    jump_hedge_min_ask, and on Kalshi's grid before --hedge-tick round (else Kalshi refused it). Returns (kind, tau,
    ask, mult, the second's epoch) or None."""
    hb = _f(st.get("hedge_belief"), 0.40)
    mult = _f(st.get("hedge_odds_mult"), 1.0) or 1.0
    min_tau = _f(st.get("hedge_odds_min_tau"), 11.0)
    live = jump_live(st)
    jsd, jmax, bar = _f(st.get("hedge_jump"), 6.0), st.get("hedge_jump_max"), st.get("jump_hedge_min_ask")
    slip = _f(st.get("hedge_slip"), 0.10)
    sign = 1.0 if want == "no" else -1.0
    prev, worst = None, None
    for x in rows:
        tau = _f(x.get("tau"), 0.0)
        if tau < 1:
            continue
        sp, sg = _f(x.get("spot"), None), _f(x.get("sigma"), None)
        if prev is not None and sp is not None and sg:
            mv = (sp - prev) * sign / sg
            worst = mv if worst is None else max(worst, mv)
        if sp is not None:
            prev = sp
        ask = _f(x.get("opp_ask") if x.get("want") == want else x.get("ask"), None)
        if ask is None or not 0.0 < ask < 1.0 or x.get("want") not in ("yes", "no"):
            continue
        fair = _f(x.get("fair"), None)
        if fair is not None and (fair if want == "yes" else 1.0 - fair) < hb:
            return ("belief", int(tau), ask, mult if (mult > 1.0 and tau >= min_tau) else 1.0, x["_epoch"])
        if (live and worst is not None and worst >= jsd and not (jmax is not None and worst >= _f(jmax))
                and not (bar is not None and ask < _f(bar) - 1e-9)
                and not ((st.get("hedge_tick") or "") != "round" and off_grid(min(ask + slip, 0.999)))):
            return ("jump", int(tau), ask, 1.0, x["_epoch"])
    return None


def ws_position(rows, r, want, hedge, n_held, rules):
    """WS: the fills [(n, price)] a skipped first buy could hold by the second its replayed hedge fires -- the refusal's
    own contracts (its `size`, what pin was about to take) at its price, plus ONE top-up (pinrun's max_per_market 2) at
    the first trajectory second after the refusal and before the hedge where pin's confidence and price gates pass on
    our side (belief at PIN or more, our ask at or under the price ceiling, tau_min or more left, a book): min(its ask
    size, what is left of n_held) at that ask; n_held at most in all. pin buys no more of a side once it has hedged
    into the other (pinrun A63, _both_sides_block), so that is the position the hedge covers and the market settles
    (the 11-14 review: ZEC 11-01 was refused 147 at tau 17 and its jump hedge fired at tau 15; the bucket's 1.12 x the
    bet, 335, could never be held two seconds after a 147-contract order). None when the refusal carries no size (an
    older record: the bucket's n_held stands) or no hedge fires."""
    take = _f(r.get("size"), None)
    if take is None or take <= 0 or hedge is None:
        return None
    fills = [(min(take, n_held), _f(r.get("price")))]
    room = n_held - fills[0][0]
    for x in rows:
        if x["_epoch"] <= r["_epoch"] + 1e-9:
            continue                                      # the refusal's own second
        if x["_epoch"] >= hedge[4] - 1e-9 or room < float(rules["min_level"]):
            break
        if x.get("want") != want:
            continue                                      # the favoured side is the other: our belief is under 50%
        ask, size, fair = _f(x.get("ask"), None), _f(x.get("ask_size"), 0.0), _f(x.get("fair"), None)
        if ask is None or fair is None or size <= 0 or _f(x.get("tau"), 0.0) < float(rules["tau_min"]):
            continue
        if (fair if want == "yes" else 1.0 - fair) < float(rules["pin"]) or ask > float(rules["price_ceiling"]) + 1e-9:
            continue
        fills.append((min(size, room), ask))
        break
    return fills


def _ws(S, now, spans, stats):
    """WS while the rule is ON: each market's first wrong_side refusal (pinrun refuses the market for the close). Never
    having the rule, the buy goes on to the gates below it -- a cheap-window market (K on, closing in its window, under
    its floor) is skipped there anyway: $0 -- and is held to the market's result: WON = the coin's bet x what pin's own
    never-hedged won markets made per contract of bet at that first-ask bucket (ws_stats); a FLIP = the contracts pin
    holds per contract of bet at that bucket, lost at the refusal's price; either way plus the hedge the trajectory
    says would have fired (ws_hedge: its premium on a win, its pay-off on a flip). When a hedge fires the position is
    what the buy could hold by the hedge's second (ws_position: the refusal's own contracts + one top-up the
    trajectory allows before it; pin buys no more of a side once it has hedged into the other), won or lost at its
    own prices, and the hedge covers exactly that. + = the rule saved (the buy would have lost), - = it gave up. The
    result: pin's own settled record, else the trajectory's last second, else missed.py's cache. `stats`: ws_stats up
    to the undo, so the rule's figure stops moving once it is off. Returns (events, tally)."""
    out = []
    t = {"won": 0, "flipped": 0, "open": 0, "k": 0, "without": 0.0, "hedges": 0, "pooled": 0, "by_hedge": 0}
    picked, seen = [], set()
    for r in S.ws_ref:
        sp = span_at(spans, r["_epoch"])
        k = (int(_f(r.get("close_s"))), r["ticker"])
        if sp is None or not sp[2] or k in seen:
            continue
        seen.add(k)
        picked.append(r)
    wants = {}
    for r in picked:
        cs = int(_f(r.get("close_s"), close_of(r["ticker"]) or 0))
        wants.setdefault(r["_path"], {})[(r["ticker"], cs)] = r["_epoch"]
    rows = {path: traj_window(path, w) for path, w in wants.items()}
    for r in picked:
        tk, want = r["ticker"], r.get("want")
        cs = int(_f(r.get("close_s"), close_of(tk) or 0))
        p = _f(r.get("price"))
        st = S.start_at(r["_epoch"])
        trj = (rows.get(r["_path"]) or {}).get((tk, cs), [])
        words = "refused a first %s buy at %s with %s s left (the index across the strike, our mid %s in 5 s)" % (
            _side(want), _cents(p), r.get("tau", "?"),
            ("up %.1fc" % _f(r.get("mid_rise_c"))) if _f(r.get("mid_rise_c"), 0.0) > 0 else
            ("down %.1fc" % abs(_f(r.get("mid_rise_c")))) if r.get("mid_rise_c") is not None else "unknown")
        w = st.get("cheap_window")
        if _k_on(st) and cw_in_window(cs, w) and p < float(w[2]) - 1e-9:
            t["k"] += 1
            out.append(_event(r, words + "; the cheap window would have skipped it too: no money either way", 0.0, "scored"))
            continue
        res, how = m_result(S, tk, trj)
        status = _status(tk, res, now, cs)
        if status != "scored":
            t["open"] += 1
            out.append(_event(r, words + ("; not settled yet" if status == "pending" else
                                          "; no result 3 h after the close (unknown)"), None, status))
            continue
        bet = m_full(tk, _f(r.get("size_now"), S.size_at(r["_path"], r["_epoch"])[0] or 0.0), None, st)
        u, hr, nmk = ws_rates(stats, ws_bucket(p), r.get("leg") or "full")
        if not nmk:
            t["pooled"] += 1
        n_held = bet * hr
        won = res == want
        after = [x for x in trj if x["_epoch"] >= r["_epoch"] - 1e-9]
        hedge = ws_hedge(after, want, st) if n_held > 0 else None
        pos = ws_position(after, r, want, hedge, n_held, m_rules(st))
        if pos is not None:                               # hedged: the position is frozen at what it held by then
            n_pos = _rw.got(pos)
            cf = _rw.value(pos, won)
            t["by_hedge"] += 1
            held = "%s contracts, all it could hold by its hedge's second (the refusal's %s at %s%s; pin buys no more " \
                   "of a side it has hedged), %s" % (_g2(n_pos), _g2(pos[0][0]), _cents(pos[0][1]),
                                                     (" + a %s top-up at %s" % (_g2(pos[1][0]), _cents(pos[1][1])))
                                                     if len(pos) > 1 else "", "won" if won else "lost")
        else:
            n_pos = n_held
            cf = bet * u if won else _value(n_held, p, False)
            held = ("the bet of %s at pin's own %.4f a contract on won markets first bought at that price" % (_g2(bet), u)
                    if won else "%s contracts, what pin holds at that price, lost" % _g2(n_held))
            if hedge is not None:                         # an older refusal record without its size
                held += "; no size on the refusal, so its hedge covers the bucket's %s contracts" % _g2(n_held)
        hv = 0.0
        if hedge is not None:
            hv = _value(n_pos * hedge[3], hedge[2], not won)
            t["hedges"] += 1
        cf += hv
        t["won" if won else "flipped"] += 1
        t["without"] += round(cf, 2)
        words += "; it %s (%s): the buy would have %s %s (%s%s)" % (
            "WON" if won else "FLIPPED", how, "made" if cf >= 0 else "lost", _rw.usd(abs(cf), False), held,
            ("; its %s hedge at %s with %d s left %s %s" % (hedge[0], _cents(hedge[2]), hedge[1],
                                                           "cost" if hv < 0 else "got back", _rw.usd(abs(hv), False)))
            if hedge is not None else "")
        words += ", so the rule %s that" % ("gave up" if cf >= 0 else "saved")
        out.append(_event(r, words, -cf, "scored"))
    return out, t


def _ws_undo(S, now, spans):
    """WS after the undo (a start record with wrongside_rise_c 0 or none): each market whose first buy -- any look of
    pin's before its first fill (the signal logs the side and the rise either way) -- was on the wrong side with our
    mid up less than the old bar (known: an unknown rise never blocks): the rule would have skipped the market, so
    its whole money is what the undo made (+) or lost (-) against keeping the rule. Returns (events, tally, tickers)."""
    out, t, tks = [], {"n": 0, "open": 0}, set()
    last_on = [sp[3] for sp in spans if sp[2]]
    if not last_on or undo_since(spans) is None:
        return out, t, tks
    bar = _f(last_on[-1].get("wrongside_rise_c"), 1.0)
    for tk, o, looks, _sp in first_looks(S, spans):
        if "15M-" not in str(tk):
            continue                                      # the hourly ladder: the rule never judged it
        bad = [s for s in looks if s.get("spot_wrong") is True and s.get("mid_rise_c") is not None
               and _f(s.get("mid_rise_c")) < bar - 1e-9]
        if not bad:
            continue
        s0 = bad[0]
        words = "%s: a first %s buy at %s with %s s left on the wrong side, our mid %s in 5 s (the rule skipped such " \
                "markets)" % (UNDO_WORDS, _side(s0.get("want")), _cents(_f(s0.get("price"))), s0.get("tau", "?"),
                              ("up %.1fc" % _f(s0.get("mid_rise_c"))) if _f(s0.get("mid_rise_c")) > 0 else
                              ("down %.1fc" % abs(_f(s0.get("mid_rise_c")))))
        ev = _undo_event(S, now, tk, o, words)
        tks.add(tk)
        t["n"] += 1
        t["open"] += 1 if ev["open"] else 0
        out.append(ev)
    return out, t, tks


def _ws_extra(t):
    n = t["won"] + t["flipped"]
    line = "without the rule: the %d settled refusal%s would have %s %s (%d won, %d flipped%s)" % (
        n, "" if n == 1 else "s", "made" if t["without"] >= 0 else "lost", _rw.usd(abs(t["without"]), False), t["won"],
        t["flipped"], (", %d with the hedge the trajectory says would have fired" % t["hedges"]) if t["hedges"] else "")
    if t["k"]:
        line += " · %d the cheap window would have skipped anyway ($0)" % t["k"]
    if t["open"]:
        line += " · %d open" % t["open"]
    return [line, "priced on pin's own fills since 10-28%s: a win at what its never-hedged won markets made a contract of "
                  "bet at that first price, a flip at the contracts it holds there; a replayed hedge covers only what the "
                  "buy could hold by its second, the refusal's own contracts + one top-up the trajectory allows (pin buys "
                  "no more of a side it has hedged)%s (assumptions; a flip costs $90-180)" % (
                      (" to the undo" if t.get("until") else ""),
                      (", %d so sized" % t["by_hedge"]) if t.get("by_hedge") else "")]


def _ws_what(st):
    return ("no first buy with the index across the strike unless our mid rose %sc in 5 s (the market is skipped); each "
            "refusal is priced by what it would have done" % ("%g" % _f((st or {}).get("wrongside_rise_c"), 1.0)))


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


M_LATE_PIN = 0.9975                       # the late boost's confidence bar (pinrun LATE_PIN, the shipped --late-pin)


def m_ladder_slice(ladder, limit, skip, n):
    """[(contracts, price)] of `n` contracts off the ask ladder at or under `limit`, after its first `skip` (what the
    order itself filled): the book past the real fill, where a bigger order would have walked."""
    out, got, left_skip = [], 0.0, float(skip)
    for lv in sorted((x for x in (ladder or []) if isinstance(x, (list, tuple)) and len(x) >= 2),
                     key=lambda x: _f(x[0])):
        p, q = _f(lv[0]), _f(lv[1])
        if p > float(limit) + 1e-9 or got >= float(n) - 1e-9:
            break
        eat = min(q, left_skip)
        q -= eat
        left_skip -= eat
        if q <= 0:
            continue
        g = min(q, float(n) - got)
        out.append((g, p))
        got += g
    return out


def m_one_coin_cap(full, bank, hwm, mult):
    """pinrun's one-coin room for a widened buy: mult x full, held to (bank - 0.8 x hwm) / 0.98, never under full; the
    full bet alone (1x) when no bank reading is in the log (the smaller room: never flattering the rule's cost)."""
    if bank is None or hwm is None or hwm <= 0:
        return float(full)
    return max(float(full), min(float(mult) * float(full), (float(bank) - 0.8 * float(hwm)) / 0.98))


def m_contexts(S):
    """Every entry order of pin's logs, in each log's own order, with what M reads around it: its own signal (the
    latest of that ticker and side before it in the file, within 3 s), the contracts the close filled before it
    (spent_before), whether its coin is new in the close, what this side of the market already held, SIZE then."""
    got = getattr(S, "_mctx", None)
    if got is not None:
        return got
    import bisect
    sig_by = {}
    for s in S.signals:
        sig_by.setdefault((s["_path"], s["ticker"], s.get("want")), []).append(s)
    for v in sig_by.values():
        v.sort(key=lambda s: s["_i"])
    keys = {k: [s["_i"] for s in v] for k, v in sig_by.items()}
    by_path = {}
    for o in S.orders:
        by_path.setdefault(o["_path"], []).append(o)
    out = []
    for path, ords in by_path.items():
        ords.sort(key=lambda o: o["_i"])
        spent, coins, held = {}, {}, {}
        for o in ords:
            tk, want = o["ticker"], o.get("want")
            cs = close_of(tk)
            k = (path, tk, want)
            j = bisect.bisect_left(keys.get(k, []), o["_i"])
            sg = sig_by[k][j - 1] if j > 0 else None
            if sg is not None and not (0 <= o["_epoch"] - sg["_epoch"] <= 3):
                sg = None
            filled = _f(o.get("filled"))
            asked = _f((o.get("body") or {}).get("count"), None)
            if asked is None:
                asked = filled
            before = spent.get(cs, 0.0)
            size, series = S.size_at(path, o["_epoch"])
            tau = o.get("tau_at_send") if o.get("tau_at_send") is not None else (sg or {}).get("tau")
            out.append({"o": o, "sg": sg, "tk": tk, "want": want, "cs": cs, "filled": filled, "asked": asked,
                        "spent_before": before, "new_coin": m_coin(tk) not in coins.get(cs, set()), "size": size,
                        "series": series, "held_tk": held.get((tk, want), 0.0), "tau": tau, "path": path})
            if filled > 0:
                spent[cs] = before + filled
                coins.setdefault(cs, set()).add(m_coin(tk))
                held[(tk, want)] = held.get((tk, want), 0.0) + filled
    S._mctx = out
    return out


def _m_bank(S, path, e):
    """The bank and its high-water mark pin's boost records carry, the latest at or before epoch `e` in log `path`."""
    best = None
    for r in S.boosts.get(path, []):
        if r.get("bank") is None or r["_epoch"] > e + 1e-9:
            continue
        if best is None or r["_epoch"] >= best["_epoch"]:
            best = r
    return (_f(best.get("bank"), None), _f(best.get("hwm"), None)) if best else (None, None)


def _m_hedge_share(S, tk, side, n):
    """The hedge money of `n` contracts of our `side` in market `tk` (_p_book: the other side's settled legs no order
    claims, pro rata by our side's contracts); 0.0 when there is none."""
    orders = [o for o in S.orders if o["ticker"] == tk]
    _legs, n_side, hedge, _in = _p_book(S, tk, orders)
    return _p_share(n_side, hedge, side, n)


def m_take_old(S, x, start, rules):
    """M: what the old argv (--extra-coin 1 --late-extra 1, one more SIZE of close budget) would have asked for the
    budget-bound order of context `x` (the 11-14 retro's retro_m.py, pinrun's wideners): its room is budget_left +
    one full bet; the sweep takes min(full, the TAPERED depth the order's own taper record read (else the book at the
    limit), the room); the late boost (10 s or less left, a late_boost record or confidence at LATE_PIN with no
    late_refused) and the band boost (95.5-98.1c) take min(the one-coin room at their multiple, the UNTAPERED book at
    the limit, the room); a side already held stops at full x the multiple less what it holds; never over 1.5 x full.
    Returns (take, how)."""
    o, sg = x["o"], x["sg"]
    tk = x["tk"]
    full = m_full(tk, x["size"], x["series"], start)
    bl = _f(sg.get("budget_left"))
    limit = _f(o.get("limit_sent"), _f(o.get("exec_price")))
    ladder = sg.get("ladder") if isinstance(sg.get("ladder"), list) else []
    flat = sum(_f(lv[1]) for lv in ladder if isinstance(lv, (list, tuple)) and len(lv) >= 2
               and _f(lv[0]) <= limit + 1e-9)
    tp = None
    for r in S.tapers:
        if r["_path"] == x["path"] and r["ticker"] == tk and sg["_i"] - 1 < r["_i"] < o["_i"]:
            tp = r
    deep = _f(tp.get("tapered")) if tp else flat
    price = _f(sg.get("price"))
    tau = int(_f(x["tau"]))
    late_tau = int(_f(rules.get("late_tau"), 10) or 10)
    room = bl + M_EXTRA * full
    take, how = x["asked"], "the sweep"
    if deep > take:
        take = max(take, min(full, deep, room))
    bank, hwm = _m_bank(S, x["path"], o["_epoch"])
    if tau <= late_tau:
        lb = [b for b in S.boosts.get(x["path"], []) if b.get("kind") == "late_boost" and b["ticker"] == tk
              and b.get("t") == o.get("t")]
        lr = [r for r in S.late_refused if r["ticker"] == tk and r.get("t") == o.get("t")]
        conf = _f(sg.get("fair")) if x["want"] == "yes" else 1.0 - _f(sg.get("fair"))
        if lb or (not lr and conf >= M_LATE_PIN):
            t2 = min(m_one_coin_cap(full, bank, hwm, D_LATE_MULT), flat, room)
            if t2 > take + 1e-9:
                take, how = t2, "the late boost"
    bm = m_band_mult(price, rules)
    if bm > 1.0:
        t2 = min(m_one_coin_cap(full, bank, hwm, bm), flat, room)
        if t2 > take + 1e-9:
            take, how = t2, "the band boost"
    mult46 = max(bm, D_LATE_MULT if tau <= late_tau else 1.0)
    if x["held_tk"] > 0:
        take = min(take, full * mult46 - x["held_tk"])
    return min(take, 1.5 * full), how


def _m_held(S, now, spans, start, rules, tally):
    """M (1), while the rule is ON: pin's own buys the 2-bet budget held back. An order whose signal's budget_left was
    what bound it (asked >= budget_left), on a coin new to the close after its first fill or inside the old late window
    (late_extra_tau), filled whole: the old argv would have asked m_take_old; the contracts over what went out are
    priced on the signal's ladder PAST what the order filled, up to its limit (the book a bigger order walks; not the
    limit, which is a floor on the gain), at the market's result, fee in, with their share of the market's hedges. +
    when the bet lost (the stake not spent), - when it won (the gain not made). What reverting B gives back."""
    out = []
    for x in m_contexts(S):
        o, sg = x["o"], x["sg"]
        sp = span_at(spans, o["_epoch"])
        if sp is None or not sp[2] or sg is None or not x["size"]:
            continue
        bl = _f(sg.get("budget_left"), None)
        if bl is None or x["asked"] < bl - 0.01:
            continue                                      # the budget was not what bound this buy
        late = x["tau"] is not None and int(_f(x["tau"])) <= int(rules["late_extra_tau"])
        if not (late or (x["new_coin"] and x["spent_before"] > 0)):
            tally["no_room"] += 1                         # the old argv gave this one nothing more either
            continue
        if x["filled"] < x["asked"] - 0.01:
            tally["unfilled"] += 1                        # the book did not even fill what went out
            continue
        take, how = m_take_old(S, x, start, rules)
        more = max(0.0, take - x["asked"])
        limit = _f(o.get("limit_sent"), _f(o.get("exec_price")))
        fills = m_ladder_slice(sg.get("ladder"), limit, x["filled"], more)
        got = _rw.got(fills)
        if got < 1.0:
            tally["no_book"] += 1                         # the cap or the book would have stopped it anyway
            continue
        tk, want = x["tk"], x["want"]
        res = S.result(tk)
        st = _status(tk, res, now, x["cs"])
        words = ("a %s buy at %s with %s s left was held to the 2-bet budget: %s went out; with the old 3rd bet %s would "
                 "have bought %s more (at %s, the book past what filled, under the %s limit%s)" % (
                     _side(want), _cents(_f(o.get("exec_price"), _f(sg.get("price")))),
                     x["tau"] if x["tau"] is not None else "?", _g2(x["asked"]), how, _g2(got),
                     _cents(_rw.avg_px(fills)), _cents(limit), ", inside the late window" if late else ", a new coin"))
        usd = None
        tally["held"] += 1
        if st == "scored":
            gain = _rw.value(fills, res == want) + _m_hedge_share(S, tk, want, got)
            usd = -gain
            if res == want:
                tally["won"] += 1
                tally["won_usd"] += gain
                words += "; the bet won, so holding them back gave up %s" % _rw.usd(abs(usd), False)
            else:
                tally["lost"] += 1
                tally["lost_usd"] += -gain
                words += "; the bet LOST, so holding them back saved %s" % _rw.usd(abs(usd), False)
        else:
            tally["open"] += 1
            words += "; not settled yet" if st == "pending" else "; no result 3 h after the close (unknown)"
        out.append(_event(o, words, usd, st))
    return out


def _m_undo(S, now, spans, skip_tks=()):
    """M after the undo (a start record with extra_coin and late_extra back above 0): every order that filled past the
    2-bet budget (filled > 2 x SIZE - what the close had filled before it): its excess contracts -- the deepest fills of
    that order, off its signal's ladder (else at its average price) -- are the 3rd bet the rule would have blocked;
    their money at the market's result, fee in, with their share of the market's hedges, is what the undo made (+) or
    lost (-) against keeping the rule (retro_m.py's PRE method). A market K's or WS's undo counts whole (skip_tks: the
    cheap window or the wrong-side rule would have skipped it, so its 3rd bet is inside their figure) is theirs, never
    counted twice (the 11-14 review: a 3rd bet is often the first buy of a new coin, so a losing one would count
    $200-400 twice). Returns (events, tally)."""
    out, t = [], {"n": 0, "open": 0, "kws": 0}
    if undo_since(spans) is None:
        return out, t
    for x in m_contexts(S):
        o, sg = x["o"], x["sg"]
        sp = span_at(spans, o["_epoch"])
        if sp is None or sp[2] or not x["size"]:
            continue
        base_left = 2.0 * float(x["size"]) - x["spent_before"]
        if x["filled"] <= base_left + 0.01:
            continue
        if x["tk"] in skip_tks:
            t["kws"] += 1
            continue
        excess = x["filled"] - max(0.0, base_left)
        limit = _f(o.get("limit_sent"), _f(o.get("exec_price")))
        fills = m_ladder_slice((sg or {}).get("ladder"), limit, x["filled"] - excess, excess)
        if _rw.got(fills) < excess - 0.5:
            fills = [(excess, _f(o.get("exec_price"), limit))]
        tk, want = x["tk"], x["want"]
        res = S.result(tk)
        st = _status(tk, res, now, x["cs"])
        words = "%s: a %s buy filled %s past the 2-bet budget at %s with %s s left (the 3rd bet the rule blocked)" % (
            UNDO_WORDS, _side(want), _g2(_rw.got(fills)), _cents(_rw.avg_px(fills)),
            x["tau"] if x["tau"] is not None else "?")
        usd = None
        t["n"] += 1
        if st == "scored":
            usd = _rw.value(fills, res == want) + _m_hedge_share(S, tk, want, _rw.got(fills))
            words += "; the bet %s: the undo %s %s" % ("won" if res == want else "LOST", "made" if usd >= 0 else "cost",
                                                      _rw.usd(abs(usd), False))
        else:
            t["open"] += 1
            words += "; not settled yet" if st == "pending" else "; no result 3 h after the close (unknown)"
        out.append(_event(o, words, usd, st))
    return out, t


def _m_third(S, now, spans, start, rules, tally):
    """M (2): the true 3rd bets, while the rule is ON. Per close with close_budget refusals: one more SIZE of room;
    every refused market's trajectory seconds from its refusal to tau_min, in time order (the trajectory wherever it is
    now: traj_window, every market of a run asked at once); the first that m_judge passes takes min(its contracts, the
    room), one bet a market, until the room is under a contract."""
    third = []
    by_close = {}
    for r in S.cb_ref:
        sp = span_at(spans, r["_epoch"])
        if sp is not None and sp[2] and r.get("close_s") is not None:
            by_close.setdefault((r["_path"], int(_f(r["close_s"]))), []).append(r)
    wants = {}
    for (path, cs), refs in by_close.items():
        w = wants.setdefault(path, {})
        for r in refs:
            k = (r["ticker"], cs)
            w[k] = min(w.get(k, r["_epoch"]), r["_epoch"])
    got = {path: traj_window(path, w) for path, w in wants.items()}
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
        trajs = {tk: rows for (tk, c), rows in got.get(path, {}).items() if c == cs}
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


def _m(S, now, spans, start, skip_tks=()):
    """M: (events, third, tally, undo events, undo tally); see _m_held, _m_third and _m_undo (`skip_tks`: the markets
    K's and WS's undos count whole)."""
    rules = m_rules(start)
    tally = _m_tally()
    events = _m_held(S, now, spans, start, rules, tally)
    third = _m_third(S, now, spans, start, rules, tally)
    undo, ut = _m_undo(S, now, spans, skip_tks)
    return events, third, tally, undo, ut


def _m_extra(tally):
    """M's two lines under the net: the held-back contracts of pin's own buys (what reverting B gives back), and the
    true 3rd bet the refusals would have placed (not in the net: the old build dropped it too)."""
    t = tally
    if t["held"]:
        first = "held back: would have made %s on %d won, lost %s on %d flipped%s (%d buy%s cut to the 2-bet budget where " \
                "the old argv had room for a 3rd; priced on the book past each fill, hedges in)" % (
                    _rw.usd(t["won_usd"], False), t["won"], _rw.usd(t["lost_usd"], False), t["lost"],
                    (" · %d open" % t["open"]) if t["open"] else "", t["held"], "" if t["held"] == 1 else "s")
    else:
        first = "held back: no buy has been cut to the 2-bet budget yet where the old argv had room for a 3rd"
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
# R (v-hedge5live, 2026-11-16): each market whose belief hedge the 5 Hz index sent first, against the 1 Hz line
def r_belief_held(row, held):
    """The 1 Hz belief in the HELD side on a trajectory row. conf is the belief in the row's want (the side the model
    favours that second: 'want no, fair 0.17, conf 0.83'), so conf when the row's want is the held side, else 1 - conf.
    A row without conf (an archived row keeps TRAJ_KEEP's fields) reads fair, the probability of YES. None when
    neither is there."""
    row = row or {}
    c = _f(row.get("conf"), None)
    if c is not None and row.get("want") in ("yes", "no"):
        return c if row.get("want") == held else 1.0 - c
    f = _f(row.get("fair"), None)
    if f is None:
        return None
    return f if held == "yes" else 1.0 - f


def r_print_second(row):
    """The second of the 1 Hz print a trajectory row's belief was computed on: the row's own second less its index age,
    rounded. pinrun writes a market's row as its second begins, often BEFORE that second's print arrives (~0.1 s in):
    index_age_s ~1.0 then, and the row still carries the previous second's print. A row without index_age_s is its own
    second."""
    age = _f(row.get("index_age_s"), 0.0)
    return float(row["_epoch"]) - float(max(0, int(round(age))))


def r_one_hz(rows, held, t0, close_s, line=R_LINE, fast_ms=None):
    """R: what the 1 Hz line would have done after a 5 Hz alarm at epoch `t0` -> (epoch, tau, ask) of the 1 Hz moment.
    The line fires at the first trajectory row, from the alarm's second to the close, whose 1 Hz belief in the held side
    is under `line` (pinrun hedge_should_fire: belief < line). Its MOMENT is the earliest second whose print could have
    crossed: the second after the last print seen NOT crossing (each row's print second: r_print_second; the alarm's
    own -- the 1 Hz print of the 5 Hz print's second (`fast_ms`) was in and above the line, by_5hz's meaning), never past
    the crossing row's print. A row is written as its second begins, so the print that crossed is often in no row at
    all (row S on print S-1, row S+1 already on print S+1) or a row late (row S+1 on print S). The shadow week
    (11-10..11-16, 4 markets, pin's REAL 1 Hz alarms): every one fired at that earliest second, the second after the
    5 Hz print, while the crossing row came a second later in 3 of the 4. Priced at the hedge-side ask (_n_hedge_ask:
    opp_ask when the row's want is the held side, else ask) of the row AT the moment's second -- the book as it began,
    the last before that print: 69c / 88c / 54c / 20c against the real 1 Hz hedges' 70c / 88c / 57c / 21-25c asks,
    where the crossing rows said 73c / 93.6c / 63c -- else of the crossing row; with neither, the first later row still
    under the line that shows one (pin retries each second while it is), as (that row's epoch, tau, ask). (epoch, tau,
    None) when it crossed but no row to the close showed a hedge-side offer (the 1 Hz hedge would have had nothing to
    buy); None when no row before the close crossed (the 1 Hz line never fired)."""
    s0 = math.floor(float(t0) + 1e-9)
    ok = float(s0 - 1)                                    # the last 1 Hz print known NOT under the line
    fm = _f(fast_ms, None)
    if fm is not None:
        ok = max(ok, float(math.floor(fm / 1000.0 + 1e-9)))
    by_s = {}
    for row in rows or []:
        if row.get("_epoch") is not None:
            by_s.setdefault(int(round(float(row["_epoch"]))), row)
    first = None
    for row in rows or []:
        e = row.get("_epoch")
        if e is None or e < s0 - 1e-9 or e >= float(close_s) - 1e-9:
            continue
        b = r_belief_held(row, held)
        if b is None:
            continue
        if first is None:
            if b >= float(line):
                ok = max(ok, r_print_second(row))
                continue
            m = min(max(ok + 1.0, float(s0)), max(float(s0), r_print_second(row)))
            at = by_s.get(int(round(m)))
            a = _n_hedge_ask(at, held) if at is not None else None
            if a is None:
                a = _n_hedge_ask(row, held)
            first = (m, int(round(float(close_s) - m)), a)
            if a is not None:
                return first
            continue
        if b < float(line):                               # crossed with no offer: pin tries again each second
            a = _n_hedge_ask(row, held)
            if a is not None:
                tau = row.get("tau")
                return e, (int(round(float(close_s) - e)) if tau is None else int(_f(tau))), a
    return first


def r_price(legs, extras, one, hedge_wins, min_tau=R_MIN_TAU):
    """R's money of one market, fee in (pinrules_watch.value): `legs` / `extras` [(n, price)] the 5 Hz path's real
    hedge and extra fills, `one` r_one_hz's (epoch, tau, ask) or None, `hedge_wins` the hedge side won (a flip).
    1 Hz fired (an ask): the real legs - the same contracts at the 1 Hz ask (leg by leg: each real order's contracts
    as one order at the 1 Hz ask, so the fee's rounding is the same on both sides), so + = the 5 Hz hedge bought
    cheaper; the extra the same way while the 1 Hz moment had min_tau+ s left, else its own real money (the 1 Hz line
    would not have bought it). 1 Hz never fired (or found no offer): the real legs' whole money. Returns (usd,
    extra_usd), the extra's part inside usd."""
    rh, rx = _rw.value(legs, hedge_wins), _rw.value(extras, hedge_wins)
    if one is None or one[2] is None:
        return rh + rx, rx
    a1 = float(one[2])
    uh = rh - _rw.value([(n, a1) for n, _p in legs], hedge_wins)
    ux = rx - (_rw.value([(n, a1) for n, _p in extras], hedge_wins) if int(one[1]) >= float(min_tau) else 0.0)
    return uh + ux, ux


def _r_fills(pool, path, tk, side, t0):
    """The executed legs [(n, price)] of `side` on `tk` in run `path` from epoch `t0` on (pin's hedge / hedge_extra
    records: status executed, a price, contracts filled)."""
    return [(_f(h.get("n")), _f(h.get("price"))) for h in pool
            if h["_path"] == path and h["ticker"] == tk and h.get("side") == side and h["_epoch"] >= t0 - 1e-9
            and h.get("status") == "executed" and h.get("price") is not None and _f(h.get("n")) > 0]


def _r_later(dt):
    dt = int(round(dt))
    return "the same second" if dt <= 0 else ("a second later" if dt == 1 else "%d s later" % dt)


def r_market(S, now, path, tk, held, t0, legs, extras, a0=None, n_pos=1):
    """R: one market whose hedge the 5 Hz belief fired first at epoch `t0` (held = our side; `legs` / `extras` the 5 Hz
    path's fills; `a0` the alarm record for its words: belief5, belief_1hz, fast_ms, tau) -> (usd or None, words,
    status, kind, result): kind 'both' (the 1 Hz line fired too), 'never' (it never did, or found no offer), 'nothing'
    (no leg filled), 'unpriced' (no trajectory row after the alarm: the 1 Hz line cannot be read). The same pricing
    reads the shadow period (hedge5_shadow swept for n) in the sanity check."""
    a0 = a0 or {}
    hs = _other(held)
    cs = close_of(tk)
    st0 = S.start_at(t0)
    line = _f(st0.get("hedge_belief"), R_LINE) or R_LINE
    min_tau = _f(st0.get("hedge_odds_min_tau"), R_MIN_TAU)
    rows = S.traj(path, cs, {tk: float(t0) - 2.0}).get(tk, []) if cs is not None else []
    res, _how = m_result(S, tk, rows)
    st = _status(tk, res, now, cs)
    nh, ph, nx, px = _rw.got(legs), _rw.avg_px(legs), _rw.got(extras), _rw.avg_px(extras)
    tau5 = a0.get("tau")
    if tau5 is None and cs is not None:
        tau5 = int(round(float(cs) - float(t0)))
    pos = (" (%d positions)" % n_pos) if n_pos > 1 else ""
    b5, b1 = _f(a0.get("belief5"), None), _f(a0.get("belief_1hz"), None)
    seen = ("belief %s on the 5 Hz print, %s on the 1 Hz" % (
        ("%.0f%%" % (100 * b5)) if b5 is not None else "?", ("%.0f%%" % (100 * b1)) if b1 is not None else "?"))
    live = [r for r in rows if r.get("_epoch") is not None and float(t0) - 1.0 <= r["_epoch"] < float(cs or 0) - 1e-9]
    later = "; not settled yet" if st == "pending" else "; no result 3 h after the close (unknown)"
    if nh <= 1e-9 and nx <= 1e-9:
        words = "a 5 Hz alarm with %s s left%s (%s): no hedge leg filled" % (tau5, pos, seen)
        return (0.0 if st == "scored" else None), words + ("" if st == "scored" else later), st, "nothing", res
    if not live:
        words = ("a 5 Hz hedge with %s s left%s (%s): %s %s at %s%s; no trajectory row after it, so the 1 Hz line cannot "
                 "be read: NOT PRICED" % (tau5, pos, seen, _g2(nh), _side(hs), _cents(ph),
                                          (" + %s extra at %s" % (_g2(nx), _cents(px))) if nx > 1e-9 else ""))
        return None, words, st, "unpriced", res
    one = r_one_hz(rows, held, t0, cs, line, a0.get("fast_ms"))
    if one is not None and one[2] is not None:
        e1, tau1, a1 = one
        fm = _f(a0.get("fast_ms"), None)
        lead = max(0.0, e1 - (fm / 1000.0 if fm is not None else float(t0)))
        words = "a 5 Hz hedge %.2f s before the 1 Hz print%s: %s %s at %s instead of %s %s" % (
            lead, pos, _g2(nh), _side(hs), _cents(ph), _cents(a1), _r_later(e1 - float(t0)))
        if nx > 1e-9:
            if tau1 >= min_tau:
                words += "; + %s extra at %s (the 1 Hz line, with %d s left, would have bought them at %s too)" % (
                    _g2(nx), _cents(px), tau1, _cents(a1))
            else:
                words += "; + %s extra at %s only the 5 Hz path bought (the 1 Hz line came with %d s left, under %d)" % (
                    _g2(nx), _cents(px), tau1, int(min_tau))
        kind = "both"
    else:
        words = "a 5 Hz hedge with %s s left%s (%s): %s %s at %s%s; the 1 Hz line %s" % (
            tau5, pos, seen, _g2(nh), _side(hs), _cents(ph), (" + %s extra at %s" % (_g2(nx), _cents(px))) if nx > 1e-9
            else "", ("never crossed %.2f before the close" % line) if one is None else
            ("crossed with %d s left but found no %s offer before the close" % (one[1], _side(hs))))
        kind = "never"
    if st != "scored":
        return None, words + later, st, kind, res
    flipped = res == hs
    usd, ux = r_price(legs, extras, one, flipped, min_tau)
    if kind == "both":
        words += "; the bet %s: %s %s" % ("FLIPPED" if flipped else "WON", "saved" if usd >= 0 else "cost",
                                          _rw.usd(abs(usd), False))
        if nx > 1e-9 and one[1] < min_tau:
            words += " (the extra alone %s %s)" % ("made" if ux >= 0 else "lost", _rw.usd(abs(ux), False))
    elif flipped:
        words += "; the bet FLIPPED: the 5 Hz hedge got back %s the 1 Hz line would have missed" % _rw.usd(usd, False)
    else:
        words += "; the bet WON: the false alarm cost %s" % _rw.usd(abs(usd), False)
    return usd, words, st, kind, res


def _r(S, now, spans):
    """R: every market with a hedge_alarm whose by_5hz is true in an ON span (a start record on index_5hz "hedge"):
    ONE event, at its first such alarm, priced by r_market on pin's real hedge / hedge_extra legs of the hedge side in
    that market from the alarm on. Returns (events, tally)."""
    out = []
    t = {"markets": 0, "both": 0, "never": 0, "flips": 0, "won": 0, "both_usd": 0.0, "never_usd": 0.0, "open": 0,
         "unpriced": 0, "nothing": 0, "net": 0.0}
    groups = {}
    for a in S.alarms:
        if a.get("by_5hz") is not True:
            continue
        sp = span_at(spans, a["_epoch"])
        if sp is None or not sp[2]:
            continue
        groups.setdefault((a["_path"], a["ticker"]), []).append(a)
    for (path, tk), als in sorted(groups.items(), key=lambda kv: (kv[1][0]["_epoch"], kv[1][0]["_i"])):
        a0 = als[0]
        held = a0.get("want")
        if held not in ("yes", "no"):
            continue
        hs = _other(held)
        legs = _r_fills(S.hedges, path, tk, hs, a0["_epoch"])
        extras = _r_fills(S.extras, path, tk, hs, a0["_epoch"])
        n_pos = len({(a.get("entry"), a.get("n")) for a in als})
        usd, words, st, kind, res = r_market(S, now, path, tk, held, a0["_epoch"], legs, extras, a0, n_pos)
        t["markets"] += 1
        if kind == "unpriced":
            t["unpriced"] += 1
        elif st != "scored":
            t["open"] += 1
        elif kind == "nothing":
            t["nothing"] += 1
        else:
            t[kind] += 1
            t["%s_usd" % kind] += round(usd, 2)
            if kind == "both":
                t["flips" if res == hs else "won"] += 1
        if usd is not None and st == "scored":
            t["net"] += round(usd, 2)
        out.append(_event(a0, words, usd, st))
    return out, t


def _r_extra(t, back=None):
    """R's lines under the net: what the 5 Hz-first hedges did against the 1 Hz line (where it followed, and the false
    alarms it never confirmed), the stop rule, and the revert to shadow when pin runs it again."""
    nb, nn = t["both"], t["never"]
    parts = []
    if nb:
        parts.append("the 1 Hz line followed on %d market%s: %s (%d flip%s, %d won bet%s)" % (
            nb, "" if nb == 1 else "s", _rw.usd(round(t["both_usd"], 2)), t["flips"], "" if t["flips"] == 1 else "s",
            t["won"], "" if t["won"] == 1 else "s"))
    if nn:
        parts.append("%d false alarm%s the 1 Hz line never confirmed: %s" % (nn, "" if nn == 1 else "s",
                                                                         _rw.usd(round(t["never_usd"], 2))))
    if t["open"]:
        parts.append("%d open" % t["open"])
    if t["unpriced"]:
        parts.append("%d NOT PRICED (no trajectory row after the alarm)" % t["unpriced"])
    if t["nothing"]:
        parts.append("%d with no hedge leg filled" % t["nothing"])
    out = [" · ".join(parts)] if parts else []
    out.append(R_STOP)
    if back is not None:
        out.append("back to shadow since %s (a pin start without --index-5hz hedge): the net no longer moves" % (
            et_words(back)))
    return out


def _md(epoch):
    """'11-16': an epoch's Eastern month and day."""
    g = time.gmtime(float(epoch) + _et_offset(float(epoch)))
    return "%d-%d" % (g.tm_mon, g.tm_mday)


def _r_what(since):
    return ("the hedge fires on the 5 Hz index when it crosses first (%s); each such hedge priced against what the 1 Hz "
            "line would have done" % (("live %s %s" % (_md(since), et_words(since, with_day=False))) if since is not None
                                      else "not live yet"))


def r_problem(net, live, since):
    """R's stop rule as the row's problem (the phone's warning line, counted on top of /fixes): while pin still runs
    --index-5hz hedge (`live`) and the settled net is under R_STOP_USD; None otherwise."""
    if not live or net is None or float(net) >= R_STOP_USD - 1e-9:
        return None
    return "net %s since %s, under the operator's -$25 stop: back to shadow (%s)" % (
        _rw.usd(float(net)), _md(since) if since is not None else "?", R_REVERT)


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
def p_given_up(r, won, share=None):
    """P (a): what the skipped band leg of band99_shadow `r` would have made at its market's result, fee in
    (pinrules_watch.value): n x (1 - ask) - fee when its side won (`won`), -(n x ask) - fee when it lost, at the ask the
    record saw (the cheapest it could have paid: a won leg's gain and a lost leg's stake both read so, so the rule is
    never flattered either way). `share`: when pin held this side in the market, its real hedges' money pro rata to the
    leg's n (_p_share; pin sizes hedges to the position, so the old code's band leg would have drawn the same hedges,
    won or lost; p_gained charges pin's blocked legs theirs the same way, so the hedges cancel -- 11-18 BNB 2:45 AM:
    without it the rule was charged -$58.19 of hedges, +$5.39 with it). Without `share`: a loss counts less the
    P_HEDGE_BACK share pin's hedges win back on a band loss (the 11-14 band99 read); a won leg's hedges are not known
    (counted as none). Returns (net, gross); (0.0, 0.0) when the record has no contracts or no usable ask."""
    n, ask = _f((r or {}).get("n")), _f((r or {}).get("ask"), None)
    if n <= 0 or ask is None or not 0.0 < ask < 1.0:
        return 0.0, 0.0
    gross = _value(n, ask, bool(won))
    if share is not None:
        return gross + share, gross
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
    return traj_plain_window(tp, close_s, float(close_s) - pad, float(close_s) + pad, max_tau=1)


def traj_plain_window(tp, close_s, t_start, t_end, max_tau=None):
    """{ticker: [trajectory rows of the close `close_s`, each with _epoch]} written from `t_start` to `t_end` in the
    PLAIN pintraj log `tp` (rows at tau `max_tau` or less only, when given): a binary search on the file's time order to
    `t_start`, then only those seconds are read -- never the whole file (it runs ~50 MB a day). {} when the file or the
    rows are not there, and for an archive (a gzip stream cannot be searched: traj_gz_window reads those)."""
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
            target, end = float(t_start), float(t_end)
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
                if not (isinstance(r, dict) and r.get("kind") == "traj" and r.get("ticker")):
                    continue
                if max_tau is not None and _f(r.get("tau"), 99.0) > max_tau:
                    continue
                e = _epoch(r.get("t"))
                if e is None or e < target - 1e-6:
                    continue
                r["_epoch"] = e
                out.setdefault(r["ticker"], []).append(r)
        except (OSError, ValueError, OverflowError):
            return out
    return out


# ---------------------------------------------------------------------------
# The trajectory of an ARCHIVED run (results\archive\pintraj-live-<stamp>.jsonl.gz, log_rotate two days after its last
# write): a gzip stream cannot be searched, so it is read through ONCE for every market a report asks of it, and only
# those markets' rows (the fields below) are kept -- in memory, and in a small JSON next to the results folder's logs
# (TRAJ_CACHE) keyed by the archive's name + size + mtime, so a fresh process (the 5-minute watcher) does not read the
# archive again. An archive never changes; an entry whose archive is gone or changed is dropped at the next write.
TRAJ_CACHE = "fixes_traj_cache.json"
TRAJ_KEEP = ("t", "tau", "want", "held", "fair", "ask", "ask_size", "opp_ask", "spot", "sigma", "conf", "index_age_s")
#            (conf, index_age_s: R reads the held side's belief and dates the print a row was computed on)
_TRAJ_WIN = {}                            # (archive path, size, mtime_ns) -> {(ticker, close_s): {"from", "rows"}}
_TRAJ_DISK = {"path": None, "key": None, "data": None}


def _fk_str(fk):
    return "%s|%s|%s" % (os.path.basename(fk[0]), fk[1], fk[2])


def traj_cache_path(tp):
    """The persisted row cache of archive `tp`: results\\fixes_traj_cache.json (the archive's results folder)."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(str(tp)))), TRAJ_CACHE)


def _disk(tp):
    """The persisted cache next to archive `tp`, read once per file state: {"closes": {...}, "windows": {...}}."""
    p = traj_cache_path(tp)
    try:
        st = os.stat(p)
        key = (st.st_size, st.st_mtime_ns)
    except OSError:
        key = None
    if _TRAJ_DISK["path"] != p or _TRAJ_DISK["key"] != key:
        d = _paths.read_json(p) if key is not None else None
        if not isinstance(d, dict):
            d = {}
        d.setdefault("closes", {})
        d.setdefault("windows", {})
        _TRAJ_DISK.update(path=p, key=key, data=d)
    return _TRAJ_DISK["data"]


def _disk_save(tp, section, fk, entries):
    """Write one archive's entries into the persisted cache (atomic; a failure -- a test's write fence, a full disk --
    only costs a re-read next time). Entries of archives that are gone or changed are dropped."""
    d = _disk(tp)
    p = traj_cache_path(tp)
    d.setdefault(section, {})[_fk_str(fk)] = entries
    ad = os.path.dirname(os.path.abspath(str(tp)))
    for sec in ("closes", "windows"):
        for k in list(d.get(sec, {})):
            name, size, mt = (k.split("|") + ["", "", ""])[:3]
            try:
                st = os.stat(os.path.join(ad, name))
                if str(st.st_size) != size or str(st.st_mtime_ns) != mt:
                    del d[sec][k]
            except OSError:
                del d[sec][k]
    try:
        _paths.write_json_atomic(p, d)
        st = os.stat(p)
        _TRAJ_DISK.update(path=p, key=(st.st_size, st.st_mtime_ns), data=d)
    except Exception:                                   # noqa: BLE001  (the fence, a locked file: read again next time)
        pass


def _trim(r):
    return {k: r.get(k) for k in TRAJ_KEEP if r.get(k) is not None or k in ("fair", "ask", "opp_ask")}


def traj_gz_window(tp, wants):
    """{(ticker, close_s): [its trajectory rows from its `from` epoch on, the TRAJ_KEEP fields and _epoch]} of ARCHIVE
    `tp` for `wants` {(ticker, close_s): from epoch}. Rows come from memory, else the persisted cache, else ONE read
    through the archive for every key not held yet (then kept in both); [] for a market the archive has no row of."""
    try:
        st = os.stat(tp)
    except OSError:
        return {}
    fk = (tp, st.st_size, st.st_mtime_ns)
    mem = _TRAJ_WIN.get(fk)
    if mem is None:
        for k in [k for k in _TRAJ_WIN if k[0] == tp]:
            del _TRAJ_WIN[k]
        mem = _TRAJ_WIN[fk] = {}
        for ks, v in (_disk(tp).get("windows", {}).get(_fk_str(fk)) or {}).items():
            tk, _s, cs = ks.rpartition("|")
            try:
                mem[(tk, int(cs))] = {"from": float(v["from"]), "rows": list(v["rows"])}
            except (KeyError, TypeError, ValueError):
                continue
    want = {(str(t), int(_f(c))): float(f0) for (t, c), f0 in wants.items()}
    miss = {k: f0 for k, f0 in want.items() if k not in mem or mem[k]["from"] > f0 + 1e-6}
    if miss:
        marks = {b'"close_s": %d' % c for _t, c in miss}
        found = {k: [] for k in miss}
        try:
            fh = _lf.open(tp, "rb")
        except OSError:
            fh = None
        if fh is not None:
            try:
                with fh:
                    for ln in fh:
                        if b'"traj"' not in ln or not any(m in ln for m in marks):
                            continue
                        try:
                            r = json.loads(ln)
                        except ValueError:
                            continue
                        if not (isinstance(r, dict) and r.get("kind") == "traj" and r.get("ticker")):
                            continue
                        k = (r["ticker"], int(_f(r.get("close_s"))))
                        if k not in miss:
                            continue
                        e = _epoch(r.get("t"))
                        if e is None or e < miss[k] - 1e-6:
                            continue
                        found[k].append(_trim(r))
            except (OSError, EOFError):
                pass                                    # a damaged archive: what was read counts
            for k, rows in found.items():
                mem[k] = {"from": miss[k], "rows": rows}
            _disk_save(tp, "windows", fk, {"%s|%d" % k: v for k, v in mem.items()})
    out = {}
    for k, f0 in want.items():
        rows = []
        for r in (mem.get(k) or {}).get("rows") or []:
            e = _epoch(r.get("t"))
            if e is not None and e >= f0 - 1e-6:
                rows.append(dict(r, _epoch=e))
        rows.sort(key=lambda r: r["_epoch"])
        out[k] = rows
    return out


def traj_window(pin_path, wants, every=None, close_s=None):
    """{(ticker, close_s): [trajectory rows from its `from` epoch on, in time order, each with _epoch]} for `wants`
    {(ticker, close_s): from epoch}, from pin log `pin_path`'s pintraj log wherever it is now (p_traj_path): plain = a
    binary search per close (traj_plain_window), archived = traj_gz_window (read once, persisted). `every` (an epoch,
    with `close_s`): every market of that close from then on -- plain logs only (N, shelved). A trajectory archived
    between the look and the read is looked up once more."""
    for _try in (0, 1):
        tp = p_traj_path(pin_path)
        if tp is None:
            return {}
        if _lf.is_gz(tp):
            return {} if every is not None else traj_gz_window(tp, wants)
        by_cs = {}
        for (tk, cs), t0 in wants.items():
            by_cs.setdefault(int(_f(cs)), {})[tk] = float(t0)
        if every is not None and close_s is not None:
            by_cs.setdefault(int(_f(close_s)), {})
        out = {}
        for cs, tks in by_cs.items():
            t_start = min(list(tks.values()) + ([float(every)] if every is not None else []))
            rows = traj_plain_window(tp, cs, t_start - 2.0, float(cs) + 5.0)
            for tk, rs in rows.items():
                if tk not in tks and every is None:
                    continue
                t0 = tks.get(tk, every)
                out[(tk, cs)] = [r for r in rs if r["_epoch"] >= float(t0) - 1e-6]
        if out or os.path.exists(tp):
            return out
    return {}


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
        # the persisted rows (results\fixes_traj_cache.json): a fresh process (the watcher's tick) reads no archive again
        for ks, v in (_disk(tp).get("closes", {}).get(_fk_str(fk)) or {}).items():
            tk, _s, cs = ks.rpartition("|")
            try:
                got[(tk, int(cs))] = [dict(x) for x in v]
            except (TypeError, ValueError):
                continue
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
    _disk_save(tp, "closes", fk, {"%s|%d" % k: v for k, v in got.items()})
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
        _lg, n_side, hedge, hedges_in = _p_book(S, tk, orders)
        share = _p_share(n_side, hedge, side, _f(r.get("n"))) if n_side.get(side) else None
        if share is not None and not hedges_in("no" if side == "yes" else "yes"):
            wait += 1
        top_usd = None
        if tp is not None and tp["at_full"] and res is not None:
            top_usd = p_topup_usd(S, tk, orders, tp, res)
            if top_usd is None:
                wait += 1
        st = _status(tk, res if (res is not None and not wait) else None, now, cs)
        usd = None
        if st == "scored":
            won = res == side
            x, gross = p_given_up(r, won, share)
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
            if share is not None and abs(share) >= 0.005:
                words += "; it %s (%s): %s %s, %s with its share of the market's hedges" % (
                    "WON" if won else "LOST", how, "it would have made" if won else "it would have lost",
                    _rw.usd(abs(gross - top), False), _rw.usd(x - top))
            elif share is not None and not won:
                words += "; it LOST (%s): it would have lost %s (the market had no hedges)" % (
                    how, _rw.usd(abs(x - top), False))
            elif won:
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
    second = ("gross, before hedges (the market's own, pro rata, where pin held the side; else %d%% of a band loss): they "
              "would have %s %s; blocked: %d early leg%s%s, %d 3rd fill%s, %d later band leg%s" % (
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
    TOKENS = (b'"live_fill"', b'"live_settle"', b'"start"', b'"day_stop_reset"',    # the last: Q's midnight resets
              b'"rescale"')                     # rescale (and start): the ladder's pot, the base of its rows' % (pot)

    def __init__(self, path):
        self.path = path
        self.reset()

    def reset(self):
        self.pos, self.head, self.mark = 0, b"", b""
        self.starts, self.fills, self.settles, self.placed82, self.resets = [], [], [], [], []
        self.pot = None                       # (epoch, $) of the newest start / rescale record that names the pot

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
        if ev in ("start", "rescale"):
            pot = _f(r.get("pot"), None)
            if pot is not None and pot >= 1.0 and (self.pot is None or t >= self.pot[0]):
                self.pot = (t, pot)
            if ev == "rescale":
                return
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


def ladder_pot(scans):
    """The ladder's pot now: the newest 'pot' of its start / rescale records (ladder_live writes it at every start and
    every auto-size reread, rescale), $; None when no ladder log names one (then a ladder row's net has no %)."""
    got = [sc.pot for sc in scans or [] if getattr(sc, "pot", None)]
    return max(got)[1] if got else None


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
# LAD and STOP: measured ONCE by the 11-14 retro (two reviewers each; RETRO.md section 1, the conservative figure),
# because no log the phone can read prices them again: the ladder's never-changed world is a replay of the paper
# engine's order stream (ladder-live.jsonl, 600+ MB; the ladder's order log alone over the same days gives $193.02,
# 57% over the replay, so it is not used), and the stopped bots write no logs to price (FX and the jump band would have
# stopped themselves by 11-13, the race's run ended 11-03, the forecaster stays paused). Their rows say so and when.
RETRO_T = 1794680160.0                    # 2026-11-14T18:16:00Z = 1:16 PM ET, the log copies the retro priced
LAD_SINCE = 1792683635.0                  # 2026-10-22T15:40:35Z: cplus, the first of the four
LAD_PARTS = ((LAD_SINCE, "all four vs the Option C argv (pot/7.8, 98c only, one bid a market, 70% rail)", 123.40),)
LAD_WHAT = ("the ladder's cplus (2 bids a market), fit sizing, single98 and the 82% cash rail, together against the Option "
            "C setting before them")
LAD_LINES = ("the 11-14 replay's central fill model; $119.42 to $140.63 across both reviewers' methods; not re-run (it "
             "needs the paper engine's 600 MB log)",
             "risk not yet paid for: the worst single-market loss rose from ~$170 to ~$443 (two 226-lot bids)")
STOP_PARTS = ((1793971712.0, "FX", "FX taker cut 11-06 (subs 4/5, $182.13 moved)", 31.6),          # 13:28:32Z
              (1793971802.0, "jump band", "jump-band live cut 11-06 (sub 3, $52.09 moved)", -6.7),   # 13:30:02Z
              (1793152932.0, "race", "coin race pause 10-27", -20.0),                                # 10-28 02:02:12Z
              (1793155002.0, "forecaster", "forecaster pause 10-27 ($114.56 to the ladder)", 23.0))  # 10-28 02:36:42Z
STOP_WHAT = "the FX taker cut, the jump-band cut, the coin race and forecaster pauses, against keeping them"
STOP_LINES = ("rests on the moved money earning ~2.2%/day in pin and the ladder (~$67, an assumption); the bots alone "
              "would have made ~$21 more kept",
              "the 11-14 retro's conservative reviewer, per stop; not running: the stopped bots write no logs to price "
              "after their windows")


def _fixed_row(cid, what, parts, lines, coin=None):
    """A row measured once (LAD, STOP): one event per measured part, scored, dated at the change; net = their sum."""
    evs = []
    for p in parts:
        t0, c, words, usd = (p[0], p[1], p[2], p[3]) if len(p) == 4 else (p[0], coin, p[1], p[2])
        evs.append(_event({"t": None, "_epoch": t0, "ticker": None},
                          "%s: %s %s (measured to %s)" % (words, "made" if usd >= 0 else "cost", _rw.usd(abs(usd), False),
                                                          et_words(RETRO_T)), usd, "scored", coin=c))
    row = _change(cid, what, min(p[0] for p in parts), evs, extra=list(lines))
    row["fixed"] = True
    return row


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
              "the boost rail is back on: a losing leg on a boosted market switches the 1.5x boost off for the rest of "
              "the run (reverted 11-16)" if rail == "any" else
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
            "withdrawn": bool(withdrawn), "retired": (retired if since is None else None), "undo": None,
            "fixed": False, "overlap_usd": 0.0, "group": GROUP.get(cid, "pin"), "dropped": None, "pot": None}


def report(paths=None, now=None):
    """Every change A..N scored, then O when a ladder order log is read, then P, R, WS, then Q when a ladder order log is
    read (see the module note). `paths`: explicit logs (tests; a ladder-live-orders*.jsonl among them is O's and Q's, the
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
    b_evs, b_tally = _b(S, now, SINCE_AB)                      # B re-scored (the 11-14 retro): no longer score_B's
    b_drop = next((t for t, r, _p in S.starts if t > SINCE_AB and r.get("hedge_jump_max") is None
                   and any(t0 < t and r0.get("hedge_jump_max") is not None for t0, r0, _p0 in S.starts)), None)
    st = S.latest_start() if new is not None else {}
    W = whats(st)                                              # the new flags' values once the build is live
    out = []
    for k in "ABC":
        if k == "B":
            row = _change("B", W["B"], since["B"], b_evs, extra=_b_extra(b_tally, b_drop))
            row["overlap_usd"] = round(b_tally["extras"], 2)   # C counts these extra legs too: totals() takes them once
            row["dropped"] = et_words(b_drop)                  # the undo dropped the cap: the phone says so
            out.append(row)
        else:
            out.append(_change(k, W[k], since[k], abc[k], extra=([c_line] if k == "C" and c_line else None)))
    later = {"E": _e, "G": _g, "H": _h, "I": _i, "J": _j}
    for k in "DEFGHIJ":
        if new is None:
            out.append(_change(k, W[k], None, []))
            continue
        extra = None
        if k == "D":
            # D's periods: ON while boost_rail "off" (0925t v-boostrail); reverted 11-16 (v-railany, "any")
            d_spans = rule_spans(S, _d_on)
            evs, dt = _d(S, now, new, d_spans)
            extra = _d_extra(dt)
        else:
            evs = _f_cheap(L, S, now, new) if k == "F" else later[k](S, now, new)
        # G is in the build but switched off unless the launcher says --late-bypass-fix on (11-04: it would have
        # trimmed 23 winning late adds to save one loss; held as a break-even safety filter)
        off = (k == "G" and (st.get("late_bypass_fix") or "off") != "on")
        row = _change(k, W[k], new, evs, off, extra=extra)
        if k == "D":
            # the revert against KEEPING D, beside the net (never in it): the markets after each rail trip re-sized up
            d_since = undo_since(d_spans)
            u_evs, ut = _d_undo(S, now, d_spans)
            row = _with_undo(row, d_since, u_evs, ut, _d_undo_note(ut) if d_since is not None else None)
        out.append(row)
    # WS's undo first: a market both WS and K would have skipped is WS's (wrong_side is the earlier gate in pinrun)
    ws_spans = rule_spans(S, _ws_on)
    ws_u, ws_ut, ws_tks = _ws_undo(S, now, ws_spans)
    # K: from the first start record that names a cheap window (v-cheapwin), its words off that record
    k_spans = rule_spans(S, _k_on)
    k_since, k_window = S.cw_since()
    k_tks = set()
    if k_since is None:
        out.append(_change("K", _k_what(None), None, []))
    else:
        evs, tally = _k(S, now, k_spans)
        k_undo = undo_since(k_spans)
        extra = _k_extra(S, tally, k_since, k_window, k_undo)
        u_evs, ut, k_tks = _k_undo(S, now, k_spans, ws_tks)
        row = _change("K", _k_what(k_window), k_since, evs, extra=extra)
        out.append(_with_undo(row, k_undo, u_evs, ut, ("%d more the wrong-side rule would have skipped first: in WS's "
                                                       "row" % ut["ws"]) if ut.get("ws") else None))
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
        m_spans = rule_spans(S, _m_on)
        # a market K's or WS's undo counts whole is theirs: its 3rd bet is inside their figure (never counted twice)
        evs, third, tally, u_evs, ut = _m(S, now, m_spans, m_start, ws_tks | k_tks)
        row = _change("M", _m_what(m_start), m_since, evs, extra=_m_extra(tally), third=third)
        out.append(_with_undo(row, undo_since(m_spans), u_evs, ut, ("%d more in a market K's or WS's row counts whole"
                                                                    % ut["kws"]) if ut.get("kws") else None))
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
    # R: from the first start record with index_5hz "hedge" (v-hedge5live), only its ON spans; the stop rule is its
    # problem while pin still runs it
    r_spans = rule_spans(S, _r_on)
    if not r_spans:
        out.append(_change("R", _r_what(None), None, [], not_live=R_NOT_LIVE))
    else:
        r_since, r_live = r_spans[0][0], r_spans[-1][2]
        evs, rt = _r(S, now, r_spans)
        row = _change("R", _r_what(r_since), r_since, evs, extra=_r_extra(rt, None if r_live else r_spans[-1][0]))
        row["problem"] = r_problem(row["net_usd"], r_live, r_since)
        out.append(row)
    # WS: from the first start record with wrongside_rise_c above 0 (v-wrongside), its words off that record
    if not ws_spans:
        out.append(_change("WS", _ws_what(None), None, [], not_live=WS_NOT_LIVE))
    else:
        ws_until = undo_since(ws_spans)                    # the rule's figure stops moving once the rule is off
        evs, wt = _ws(S, now, ws_spans, ws_stats(S, ws_spans[0][0], ws_until))
        wt["until"] = ws_until
        row = _change("WS", _ws_what(ws_spans[0][3]), ws_spans[0][0], evs, extra=_ws_extra(wt))
        out.append(_with_undo(row, undo_since(ws_spans), ws_u, ws_ut))
    # Q: the ladder's midnight reset (v-ladder-dayreset), whenever a ladder order log is read
    if lad:
        out.append(_q_row(scans, now))
    # LAD and STOP: measured once by the 11-14 retro, in every report
    out.append(_fixed_row("LAD", LAD_WHAT, LAD_PARTS, LAD_LINES, coin="ladder"))
    out.append(_fixed_row("STOP", STOP_WHAT, STOP_PARTS, STOP_LINES))
    # the base of each row's % (operator 11-16: "they only affect pin"): a pin row's is pin's bank (the phone's), a
    # ladder row's the ladder's pot (None when no ladder log names it: no %), the stops' none (pot stays None)
    lpot = ladder_pot(scans) if lad else None
    for c in out:
        if c["group"] == "ladder":
            c["pot"] = lpot
    return out


def _with_undo(row, since, evs, t, note=None):
    """A row from its rule's undo on (`since`: the first start record with the rule off; None = never undone): the
    UNDO is scored against keeping the rule (`evs`: + = the undo made money), its events kept apart from the rule's
    (row["undo"]: {since, since_t, net_usd, engaged, open, events, note, line}). The row's net STAYS the rule's money
    against never having it (row["rule_usd"], the same figure): from the undo on pin trades as if the rule had never
    been, so against never making it the undo adds nothing. The undo's own money answers another question (against
    KEEPING the rule), so it sits beside the net, never inside it nor in totals()' net (the 11-14 review: summed, an
    undone rule the retro found costly drifts toward + as the undo's expected wins come in, and can turn green). The
    phone puts both on the net line ('with the rule: net $X · since the undo (vs keeping it): $Y on N markets'), so no
    shrink step can drop either; a note (another row counts some of its markets whole) is the row's last line."""
    row["rule_usd"] = row["net_usd"]
    if since is None:
        row["undo"] = None
        return row
    evs = sorted(evs, key=lambda e: e["epoch"] or 0)
    u = round(sum(e["usd"] for e in evs if e["usd"] is not None), 2)
    row["undo"] = {"since": et_words(since), "since_t": since, "net_usd": u, "engaged": len(evs),
                   "open": sum(1 for e in evs if e["open"]), "events": evs, "note": note}
    row["undo"]["line"] = undo_line(row)
    if note:
        row["extra"] = list(row["extra"]) + ["since the undo: " + note]
    return row


def undo_counted(row):
    """What an undone row's undo money is on: 'on 2 bets · 1 open' (M: the 3rd bets), 'on 1 market' (K, WS, D)."""
    u = row.get("undo") or {}
    n = int(u.get("engaged") or 0)
    return "on %d %s%s%s" % (n, "bet" if row.get("id") == "M" else "market", "" if n == 1 else "s",
                             (" · %d open" % u["open"]) if u.get("open") else "")


def undo_line(row):
    """'with the rule: -$57.62 (to Nov 14 2:30 PM ET) · since the undo (vs keeping it): +$3.10 on 2 bets · 1 open': an
    undone row's two periods, each against its own alternative, in words (row["undo"]["line"]; the note at the end
    when there is one). The phone builds its net line from the same figures (undo_counted), the money never cut."""
    u = row.get("undo") or {}
    line = "with the rule: %s (to %s) · %s: %s %s" % (
        _rw.usd(row.get("rule_usd", 0.0)), u.get("since") or "?", UNDO_WORDS, _rw.usd(u.get("net_usd", 0.0)),
        undo_counted(row))
    if u.get("note"):
        line += " · " + u["note"]
    return line


def totals(changes):
    """{engaged, open, net_usd} over every change except J and a withdrawn one (O while O_WITHDRAWN: never live, never
    counted): a J leg is also a C engagement (C scores every executed extra), so J stays out of the sum and that leg is
    counted once. L is in: what it keeps or misses is pin's real money (the premium not spent, the save the odds line
    then paid more for), as K's skipped buys are. M is in by its net (the contracts the 2-bet budget held back on pin's
    own buys); its true-3rd-bet list is not. P, Q and R are in. problems: the ids of every change not withdrawn (J too)
    that says one (change["problem"]: O on the 100% rail without the marking code, while O is not withdrawn; R's stop
    rule while pin still runs --index-5hz hedge with R's net under -$25).
    An undone rule (M, K, WS, D) is in by its net, the rule's money against never having it; the undos' money (against
    KEEPING the rules, another question) is never in net_usd, engaged or open: undo_usd, undo_engaged (their markets
    or bets), undo_open and undos (the undone ids) carry it beside the total.
    PIN'S OWN (the operator 11-16: "All changes on /fixes uses ladder to calculate the total affect of changes which
    isn't right, they only affect pin"): pin_net_usd (groups' pin, B's overlap taken off), pin_engaged and pin_open
    (pin's live rows only) are the /fixes headline; ladder_net_usd and stops_net_usd (LAD, O, Q / STOP) are said on
    their own line, never summed into pin's; ladder_pot (the ladder rows' pot, None when unread) is the base of the
    ladder's %. net_usd / engaged / open stay every row's (the older callers' fields)."""
    cs = [c for c in changes if c["id"] != "J" and not c.get("withdrawn")]
    live = [c for c in cs if not c.get("fixed")]
    overlap = round(sum(_f(c.get("overlap_usd")) for c in cs), 2)
    groups = {}
    for c in cs:
        g = GROUP.get(c["id"], "pin")
        groups[g] = groups.get(g, 0.0) + c["net_usd"] - _f(c.get("overlap_usd"))
    und = [c for c in cs if c.get("undo")]
    pin = [c for c in live if c.get("group", GROUP.get(c["id"], "pin")) == "pin"]
    lpots = [c.get("pot") for c in changes if c.get("group") == "ladder" and c.get("pot")]
    return {"pin_net_usd": round(groups.get("pin", 0.0), 2), "pin_engaged": sum(c["engaged"] for c in pin),
            "pin_open": sum(c["open"] for c in pin), "ladder_net_usd": round(groups.get("ladder", 0.0), 2),
            "stops_net_usd": round(groups.get("stops", 0.0), 2), "ladder_pot": lpots[0] if lpots else None,
            "engaged": sum(c["engaged"] for c in live), "open": sum(c["open"] for c in live),
            "net_usd": round(sum(c["net_usd"] for c in cs) - overlap, 2), "overlap_usd": overlap,
            "groups": {g: round(v, 2) for g, v in groups.items()},
            "undo_usd": round(sum(_f(c["undo"].get("net_usd")) for c in und), 2),
            "undo_engaged": sum(int(c["undo"].get("engaged") or 0) for c in und),
            "undo_open": sum(int(c["undo"].get("open") or 0) for c in und), "undos": [c["id"] for c in und],
            "problems": [c["id"] for c in changes if c.get("problem") and not c.get("withdrawn")]}
