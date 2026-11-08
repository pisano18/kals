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
A and B count from 11-01 15:37 ET, C from 11-02 08:35 ET, D to J from the first start record after the 0925r build
(code_sha ca156bf45704) with another code_sha, K from the first start record that names a cheap_window. An engagement
whose market has not settled is "open" (not in net $).

A settled leg's pnl_c is pin's own figure for the whole leg, the taker fee INSIDE it (pinrun: pnl = filled * (1 - cost
or -cost) - billed_fee(cost, filled)). A leg is matched by ticker, our side (want; a hedge leg's want is its hedge side),
the nearest cost, then the nearest time; a leg is claimed once per change. Records of older builds may lack fields:
every read is a .get with a default.

    report(paths=None, now=None) -> [change dict per A..K]:
        {id, name, what, since (ET words or None = not live yet), since_t, engaged, last_engaged, last_t, open,
         net_usd, events: [{t, epoch, et, coin, words, usd (None while open), open}],
         off (True only for G while the launcher leaves --late-bypass-fix off: built, switched off),
         extra (lines under the net; K's with / without the rule)}
    totals(changes) -> {engaged, open, net_usd} over every change but J; J's leg is already inside C.
"""
import calendar
import json
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

BASE_SHA = "ca156bf45704"                 # pin 0925r: D to J start at the first later start record with another sha
UNKNOWN_AFTER_S = _rw.UNKNOWN_AFTER_S     # a market with no result 3 h after its close: "unknown", still open
IDS = "ABCDEFGHIJK"
NAMES = {"A": "later-buy check", "B": "jump cap", "C": "bigger hedge", "D": "boost rail", "E": "hedge tick",
         "F": "cheap jump skip", "G": "late-boost bypass fix", "H": "extra stake cap", "I": "max positions 5",
         "J": "extra on odds", "K": "cheap morning skip"}
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


# ---------------------------------------------------------------------------
class Scan:
    """One pass over the logs for everything the D..J scores need (pinrules_watch.Logs holds A, B, C's)."""

    WANT = ('"start"', '"settled"', '"hedge"', '"hedge_extra"', '"hedge_quote"', '"band_boost"', '"late_boost"',
            '"boost_rail_kept"', '"hedge_cheap_skip"', '"late_bypass_refused"', '"extra_stake_capped"',
            '"open_cap_relaxed"', '"order"', '"cheap_window')
    LISTS = {"hedge": "hedges", "hedge_extra": "extras", "boost_rail_kept": "kept", "hedge_cheap_skip": "cheap",
             "late_bypass_refused": "late_bypass", "extra_stake_capped": "stake_capped", "open_cap_relaxed": "open_cap",
             "order": "orders"}

    def __init__(self, paths):
        self.starts = []                      # (epoch, record, path)
        self.settled = {}                     # (ticker, want) -> [settled]
        self.by_tk = {}                       # ticker -> [settled]
        self.boosts = {}                      # path -> [band_boost / late_boost]
        self.cw_ref = []                      # K: refusals with gate cheap_window (one per skipped market)
        self.cw_set = {}                      # K: ticker -> its shadow's cheap_window_settled
        for v in self.LISTS.values():
            setattr(self, v, [])
        seen = set()
        quote = {}
        for path in paths:
            try:
                fh = _lf.open(path, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with fh:
                for line in fh:
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
                        continue
                    tk = r.get("ticker")
                    if not tk or t is None:
                        continue
                    if k == "hedge_quote":
                        quote[(tk, r.get("side"))] = r
                        continue
                    key = (k, tk, r.get("t"), r.get("want"), r.get("side"), r.get("cost"), r.get("price"), r.get("n"),
                           r.get("client_order_id"), r.get("leg"), r.get("which"))
                    if key in seen:
                        continue
                    seen.add(key)
                    r["_epoch"], r["_path"] = t, path
                    if k == "settled":
                        self.settled.setdefault((tk, r.get("want")), []).append(r)
                        self.by_tk.setdefault(tk, []).append(r)
                    elif k in ("band_boost", "late_boost"):
                        self.boosts.setdefault(path, []).append(r)
                    elif k == "refused":
                        if r.get("gate") == "cheap_window":
                            self.cw_ref.append(r)
                    elif k == "cheap_window_settled":
                        self.cw_set[tk] = r
                    elif k == "hedge_cheap_skip":
                        r["_quote"] = quote.get((tk, r.get("side")))
                        self.cheap.append(r)
                    elif k in self.LISTS:
                        getattr(self, self.LISTS[k]).append(r)
        self.starts.sort(key=lambda x: x[0])
        for v in list(self.LISTS.values()):
            getattr(self, v).sort(key=lambda r: r["_epoch"])
        self.cw_ref.sort(key=lambda r: r["_epoch"])
        for v in self.boosts.values():
            v.sort(key=lambda r: r["_epoch"])

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
    }


def _k_what(w):
    if not (isinstance(w, (list, tuple)) and len(w) == 3):
        w = (6, 10, 0.98)
    return ("no first buy under %s in a market closing %s to %s ET (the market is skipped); each skip is priced by what "
            "it would have done" % (_cents(w[2]), _hour(w[0]), _hour(w[1])))


def _change(cid, what, since, events, off=False, extra=None):
    events = sorted(events, key=lambda e: e["epoch"] or 0)
    scored = [e["usd"] for e in events if e["usd"] is not None]
    last = events[-1]["epoch"] if events else None
    return {"id": cid, "name": NAMES[cid], "what": what, "since": et_words(since), "since_t": since,
            "engaged": len(events), "last_engaged": et_words(last), "last_t": last,
            "open": sum(1 for e in events if e["open"]), "net_usd": round(sum(scored), 2) if events else 0.0,
            "events": events, "off": bool(off), "extra": list(extra or [])}


def report(paths=None, now=None):
    """Every change A..K scored (see the module note). `paths`: explicit logs (tests); default pin's live logs from
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
    return out


def totals(changes):
    """{engaged, open, net_usd} over every change except J: a J leg is also a C engagement (C scores every executed
    extra), so J stays out of the sum and that leg is counted once."""
    cs = [c for c in changes if c["id"] != "J"]
    return {"engaged": sum(c["engaged"] for c in cs), "open": sum(c["open"] for c in cs),
            "net_usd": round(sum(c["net_usd"] for c in cs), 2)}
