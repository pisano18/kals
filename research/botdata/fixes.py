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
A and B count from 11-01 15:37 ET, C from 11-02 08:35 ET, D to J from the first start record after the 0925r build
(code_sha ca156bf45704) with another code_sha, K from the first start record that names a cheap_window, L from the
first start record with hedge_jump_shadow set (pinrun refuses it next to --hedge-jump, so the jump hedge is off there),
M from the first start record with extra_coin 0 and late_extra 0 (the start record carries both and bank_brake).
An engagement whose market has not settled is "open" (not in net $).

A settled leg's pnl_c is pin's own figure for the whole leg, the taker fee INSIDE it (pinrun: pnl = filled * (1 - cost
or -cost) - billed_fee(cost, filled)). A leg is matched by ticker, our side (want; a hedge leg's want is its hedge side),
the nearest cost, then the nearest time; a leg is claimed once per change. Records of older builds may lack fields:
every read is a .get with a default.

    report(paths=None, now=None) -> [change dict per A..M]:
        {id, name, what, since (ET words or None = not live yet), since_t, engaged, last_engaged, last_t, open,
         net_usd, events: [{t, epoch, et, coin, words, usd (None while open), open}],
         off (True only for G while the launcher leaves --late-bypass-fix off: built, switched off),
         extra (lines under the net; K's with / without the rule; L's paid vs saved and the alarms not counted; M's
         held-back contracts and the true-3rd-bet line),
         not_live (the phone's words while since is None, or None for the default),
         third (M only: the true-3rd-bet events, the same shape as events, not in net_usd; [] elsewhere)}
    totals(changes) -> {engaged, open, net_usd} over every change but J; J's leg is already inside C. L is in: the
        premium it keeps and the save it misses are pin's real money, as K's skipped buys are. M is in by its net
        (the held-back contracts of pin's own buys); its `third` list is not.
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
IDS = "ABCDEFGHIJKLMN"
NAMES = {"A": "later-buy check", "B": "jump cap", "C": "bigger hedge", "D": "boost rail", "E": "hedge tick",
         "F": "cheap jump skip", "G": "late-boost bypass fix", "H": "extra stake cap", "I": "max positions 5",
         "J": "extra on odds", "K": "cheap morning skip", "L": "jump hedge shadow", "M": "3rd bet blocked",
         "N": "hedge line 0.60"}
L_NOT_LIVE = "not live yet (comes with the next pin restart)"
M_NOT_LIVE = "not live yet (comes with the first pin start on call B)"
N_NOT_LIVE = ("SHELVED 11-09, never deployed: the deep dive found no out-of-sample edge (-$1.79 to +$1.53 a day at "
              "today's size); counted only if pin ever starts on --hedge-belief 0.60")
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
    then .gz (log_rotate), then the other way round."""
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
            '"autosize"', '"sweep_depth"')
    LISTS = {"hedge": "hedges", "hedge_extra": "extras", "boost_rail_kept": "kept", "hedge_cheap_skip": "cheap",
             "late_bypass_refused": "late_bypass", "extra_stake_capped": "stake_capped", "open_cap_relaxed": "open_cap",
             "order": "orders", "jump_shadow": "shadow", "signal": "signals", "sweep_depth": "sweeps"}

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
        if len(_CACHE) > 8:
            _CACHE.clear()
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


def _abc(L, now, since):
    """A, B, C events off pinrules_watch's own scoring, from each rule's live moment."""
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


def _change(cid, what, since, events, off=False, extra=None, not_live=None, third=None):
    events = sorted(events, key=lambda e: e["epoch"] or 0)
    scored = [e["usd"] for e in events if e["usd"] is not None]
    last = events[-1]["epoch"] if events else None
    return {"id": cid, "name": NAMES[cid], "what": what, "since": et_words(since), "since_t": since,
            "engaged": len(events), "last_engaged": et_words(last), "last_t": last,
            "open": sum(1 for e in events if e["open"]), "net_usd": round(sum(scored), 2) if events else 0.0,
            "events": events, "off": bool(off), "extra": list(extra or []), "not_live": not_live,
            "third": sorted(third or [], key=lambda e: e["epoch"] or 0)}


def report(paths=None, now=None):
    """Every change A..M scored (see the module note). `paths`: explicit logs (tests); default pin's live logs from
    11-01 on. `now`: the clock (pending vs unknown)."""
    now = time.time() if now is None else float(now)
    paths = pin_paths() if paths is None else list(paths)
    L, S = _load(paths)
    new = S.new_build_since()
    since = {"A": SINCE_AB, "B": SINCE_AB, "C": SINCE_C}
    abc = _abc(L, now, since)
    st = S.latest_start() if new is not None else {}
    W = whats(st)                                              # the new flags' values once the build is live
    out = [_change(k, W[k], since[k], abc[k]) for k in "ABC"]
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
        out.append(_change("N", _n_what(None), None, [], not_live=N_NOT_LIVE))
    else:
        evs, tally = _n(S, now, n_since, n_start)
        out.append(_change("N", _n_what(n_start), n_since, evs, extra=_n_extra(tally)))
    return out


def totals(changes):
    """{engaged, open, net_usd} over every change except J: a J leg is also a C engagement (C scores every executed
    extra), so J stays out of the sum and that leg is counted once. L is in: what it keeps or misses is pin's real
    money (the premium not spent, the save the odds line then paid more for), as K's skipped buys are. M is in by
    its net (the contracts the 2-bet budget held back on pin's own buys); its true-3rd-bet list is not."""
    cs = [c for c in changes if c["id"] != "J"]
    return {"engaged": sum(c["engaged"] for c in cs), "open": sum(c["open"] for c in cs),
            "net_usd": round(sum(c["net_usd"] for c in cs), 2)}
