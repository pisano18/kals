"""Apply v-0925v to a COPY of the 0925u pin build (research\\pinrun.py code_sha e0ba3543e7be = 0925t 9e04c0252ac9 +
results\\patch_0925u.py; pintake.py b3c7bb48abb5 and ordercli.py 467782077a23 are NOT touched). Patches pinrun.py in
place, CRLF preserved; every anchor must occur exactly once; refuses an already-patched tree, a tree that is not 0925u,
and any result whose sha is not EXPECTED_PINRUN (nothing is written then). Every refusal is an explicit exit, not an
assert, so `python -O` cannot skip one.
usage: python patch_0925v.py <build_dir>      (build_dir holds research\\pinrun.py)

THE FAIL-SAFE BUILD (operator 11-07: "Anything that could cause the 1k+ loss needs to be addressed immediately. I'm
serious. And the answer isn't betting less" / "Everything else that's possible to fix needs addressing as well as
possible"). No new flag: every change is always on, and none of them changes a trading rule, threshold, size, gate or
hedge trigger. Each closes one way the bot could keep BUYING while it could not see, book, hedge or account for what it
already held, and each does it the same way: NEW ENTRIES are blocked (the K1 `_mk = []` line, so a block can never
reach a hedge, a cancel, the drain or an exit, and never moves a size), the condition clears itself, and it writes one
record of its own kind so a watcher can alarm on it:

  bankread   read_bank accepts balance_dollars alone (cents optional; both present must agree to $0.01)
  unbooked   a market is booked on determined/amended/finalized(/settled) with result yes/no, never disputed (one
             booked before it is paid holds the sizer until finalized; a different final result is corrected); a leg
             still unbooked 900 s after its close is PARKED (the caps and the sizer let go, as 0925u's release did)
             and read on -- every minute, every 10 min after 6 h, never inside a held market's last 90 s, never
             released by time -- and its worst case counts as a PROVISIONAL loss against the run abort and (its
             own ET day only) the day cap: entries blocked when it reaches the stop
  hedgefail  a hedge send (cover or extra) whose answer is not 2xx is counted; hedge_fail per market per close; 3 in a
             row -> hedge_broken
  hedgeexi   the hedge (and its extra leg) goes to the market's own exchange_index, not a hard-coded 2
  universe   GET /markets limit 20 chosen by close_time; robust close_time; one bad row skips that row; a missing
             exchange_index is 2 (never 0); 3 refreshes where every series answered 200 with an EMPTY list (outside
             Thursday 3-5 AM ET) -> the /events fallback, at most once a minute; HTTP failures never count as empty
  expiry     nothing is bought once --minutes has run out; the run exits only when flat, or at the end + 30 min
  startbank  no entry before the first balance read: retried 1, 2, 4, 8, 16 s; after 60 s the size mirror's bank
             (< 24 h) sets the day stop (size can only go down); neither -> entries stay blocked
  clockskew  the fast end (5th percentile) of (box receipt - Kalshi stamp) on the index prints -- feed lag cannot
             raise it; |offset| > 750 ms for 60 s blocks
  logfail    3 failed decision-log writes block entries (one stderr line); the day-loss file write is atomic (and
             waits out a reader) and a failed one blocks entries until it lands; print() can no longer raise, in
             pinrun or in pintake / ordercli / livebook / kauth; the sizer call is guarded
  importpath the TEMP kals-work folder is no longer put on sys.path, by pinrun or (through _default_key) by livebook
  apishape   one api_shape record per unexpected API shape (balance, market status/result, order status, positions,
             orderbook frames, close_time, exchange_index, /events nested status)

ROUND 3 (2026-11-08), from the verified rule scan (rules1107 REPORT.md sections 2 and 7). THE "NO NEW FLAG / NO
TRADING RULE MOVES" SENTENCE ABOVE IS ROUND 2's AND NO LONGER HOLDS WHOLE: round 3 adds one flag (off, not launched)
and four changes that move what the bot does, each in one narrow, stated way (all always on):
  D2  the day cap and the run abort see a market's NET from its first booked leg (the unbooked siblings priced on the
      result the booked leg carried, market_pending / mk_view), never one leg alone: a hedged market's legs book ~15 s
      apart and the 20 Hz check saw the main leg's whole loss first (11-02 ZEC -$281.63 then +$253.07; at today's
      size a false all-day halt on 09-27)
  D4  a jump give-up (not a panic) ends the JUMP's retries only: the position is no longer marked hedged, and the
      belief line gets its own HEDGE_MAX_TRIES (5 positions 10-24..11-03 lost their belief hedge to it)
  D5  hedge sends no longer spend the close's 24-send ENTRY budget (attempts_cap 84 times in 9 closes); their own
      counters (HEDGE_MAX_TRIES, MAX_HEDGE_ATTEMPTS_PER_CLOSE) still bound them
  D6  --max-positions counts UNHEDGED contracts (pintake's ledger less 2 x min(yes, no) per market from pin's own
      legs): a hedged pair no longer looks twice as big
  P7  the paused loop naps 0.05 s, not 1 s, so a held position's hedge is re-checked at the ordinary rate
  JS  --hedge-jump-shadow SD (OFF; refused with --hedge-jump): the jump alarm without its orders, one jump_shadow
      record per position (what would have gone out, and whether the 8 sd cap / the 5c floor would have skipped it)
  F2  the logfail self-test closes the trajectory handle before deleting its TEMP folder (one leaked per restart)
  cost: five no-work early returns in the per-pass guard and the unbooked bookkeeping (same answers)
Call B is argv only (pin_0925v.ps1): --extra-coin 0 --late-extra 0 --bank-brake 4.5 -- SIZE and the largest single
order identical (the brake's divisor is the same 8.82 to the bit), the close budget 3x -> 2x SIZE; a SECOND boosted
coin in the same close is now capped at 0.5x SIZE (196, not 588, at SIZE 392) -- the 3rd bet's room (round 4 wording:
round 3 said "every single order", which the money review corrected).

ROUND 4 (2026-11-08), from the money and tests reviews of round 3 (the rev3 and rt3 folders): the round-3 fixes closed for their
whole class, each in one narrow, stated way (all always on):
  D2  every leg of a market books from the SAME read in the SAME pass (reconcile's one-GET-per-ticker-per-15-s
      throttle WAS the split: the first leg's loss sat alone in the run, the day file and pintake's own rail); a pass
      that books one leg and then fails is round 3's market view, and while pintake's per-leg rail is under its line
      but the market is not, new entries are blocked (entries_blocked reason leg_dip) instead of refused twice into a
      halt; an unpriceable sibling adds nothing (a NaN poisoned every market's view); the correction and the leg
      selection are pure helpers (mk_res_correct, market_pending_legs)
  D4  the close's hedge cap (MAX_HEDGE_ATTEMPTS_PER_CLOSE) on a jump-only second ends the jump's retries only, like
      the 30-try give-up
  D5  hedge_broken needs its HEDGE_FAIL_BLOCK failures on HEDGE_FAIL_MARKETS (2) different markets: one market's
      reject loop is that market's hedge_fail and no longer locks the close's other markets out
  JS  the shadow is read every second until the second the jump hedge WOULD have sent (one record per outcome:
      would_send, capped, cheap_skip, no_ask, filtered, nothing_to_buy), queued by the hedge pass and written below
      it; its two argv checks are pure (jump_shadow_arg_error, jump_max_arg_error)
  F2  the two TEMP folders every self-test still left (pinmirror-, pintraj-selftest-) are removed, selftest()
      records every mkdtemp of the run, sweeps stragglers, and a check proves none is left
  cost: selftest() memoizes inspect.getsource for its own length (trade_loop was tokenized 19 times)

ROUND 5 (2026-11-08), from the three reviews of round 4 (rev4_money, rev4_tests, rev4_deploy; all three said DEPLOY):
in pinrun only F2's verdict moves; the rest is new self-test checks (no live behaviour changes) and the deploy script
  F2  the TEMP check judges what is STILL THERE AFTER the retrying sweep (sweep_temp_verdict): round 4 failed on the
      list taken BEFORE the sweep, so one folder a virus scanner held for a moment failed the startup self-test --
      pin refused to start, and inside pin_0925v.ps1's watch that read as a dead pin (a false rollback); a folder the
      retries remove is reported in the check's line, one still there after every retry (a handle pin code holds,
      i.e. a real leak) fails it; and so the sweep cannot hide a folder its own code never removes, selftest()
      records every shutil.rmtree call before it runs (_SELFTEST_RM) and round 4's two leak sites (pinmirror-,
      pintraj-selftest-) must each have handed their folder to rmtree themselves -- a record no lock can change
  tests  the tests review's cheap gaps, each with a world that tells the code from its mutation: leg_dip reads
      pintake.LOSS_ABORT (not --loss-abort), blocks AT the line (<=), reads the RUN view (not the day's) and clears
      on the market view; a 2xx ends hedge_broken's streak AND its markets; the pass's shared read is per ticker; the
      close's hedge cap on a jump-only second ends the jump's retries (one hedge_refused, not one a second)
"""
import hashlib
import os
import sys

BASE_PINRUN = "e0ba3543e7be"
EXPECTED_PINRUN = "d51b131b55cf"   # the reviewed result (the patch refuses to write anything else)


def refuse(msg):
    sys.stderr.write("REFUSED: " + msg + "\n")
    sys.exit(2)


if len(sys.argv) != 2:
    sys.stderr.write("usage: python patch_0925v.py <build_dir>   (build_dir holds research\\pinrun.py)\n")
    sys.exit(2)
B = sys.argv[1]
PR = os.path.join(B, "research", "pinrun.py")
if not os.path.isfile(PR):
    refuse("%s does not exist" % PR)


def sha12(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


class Src:
    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read().decode("utf-8")
        if "\r\n" not in raw:
            refuse(path + ": not CRLF")
        self.s = raw.replace("\r\n", "\n")
        if "\r" in self.s:
            refuse(path + ": stray CR")

    def once(self, anchor):
        n = self.s.count(anchor)
        if n != 1:
            refuse("%s: anchor found %d times (need exactly 1), nothing written: %r"
                   % (self.path, n, anchor[:90]))

    def after(self, anchor, text):
        self.once(anchor)
        self.s = self.s.replace(anchor, anchor + text)

    def before(self, anchor, text):
        self.once(anchor)
        self.s = self.s.replace(anchor, text + anchor)

    def replace(self, old, new):
        self.once(old)
        self.s = self.s.replace(old, new)

    def span(self, start, end, new):
        """Replace from the start of `start` to the end of `end` (each once, in that order)."""
        self.once(start)
        self.once(end)
        i = self.s.index(start)
        j = self.s.index(end)
        if not i < j:
            refuse("%s: span out of order: %r .. %r" % (self.path, start[:60], end[:60]))
        self.s = self.s[:i] + new + self.s[j + len(end):]

    def write(self, expected=None):
        data = self.s.replace("\n", "\r\n").encode("utf-8")
        got = hashlib.sha256(data).hexdigest()[:12]
        if expected is not None and got != expected:
            refuse("%s: the patched file would be %s, not the reviewed %s; nothing written"
                   % (self.path, got, expected))
        open(self.path, "wb").write(data)
        return got


if sha12(PR) != BASE_PINRUN:
    refuse("research/pinrun.py is not 0925u (%s, want %s); nothing written" % (sha12(PR), BASE_PINRUN))
R = Src(PR)
if "v-0925v" in R.s or "entry_blocks" in R.s or "api_shape" in R.s:
    refuse("already patched (v-0925v is in it); nothing written")
if "CHEAP_WINDOW" not in R.s or "_cw_settle" not in R.s:
    refuse("not the 0925u build (no cheap-window code); nothing written")

# ============================================================================ 1. importpath + a print() that cannot raise
R.replace(r'''sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get                                       # noqa: E402
''', r'''# v-0925v importpath (2026-11-07): THE TEMP FOLDER IS OFF THE PATH. This
# line used to put C:\Users\Joe\AppData\Local\Temp\kals-work AHEAD of the
# build's own research folder, so a stray kauth.py (or pinxfer.py, pinflat.py,
# downtime.py, a websockets package) left in TEMP would have loaded in place
# of the build's -- code no sha256 in the launcher could see. kauth.py has
# lived in the repo since 2026-09-15 ("retire the TEMP one on the next
# versioned pinrun change"); every module that folder could shadow is in this
# build's research folder (kauth, ordercli, pinxfer, pinflat, downtime) or in
# site-packages (websockets, cryptography); the folder does not exist on the
# server (Administrator / SYSTEM) nor on the laptop any more. The modules this
# file imports LATER, inside functions, are imported HERE as well, from the
# research folder, so a path entry another module adds at run time can never
# shadow them. And none is added any more: livebook._default_key() puts the
# same folder back at sys.path[0] whenever KALSHI_KEY_ID is unset (the
# launcher sets none), and the index socket and main()'s book both called it
# -- review 11-07 measured the folder at sys.path[0] for the whole run. They
# take their key from ws_key() below now, and scrub_temp_path() takes the
# folder off again should anything still add it. The self-test checks every
# module resolves from this folder and that building the socket adds nothing.
from kauth import get                                       # noqa: E402
_V_PREIMPORTED = []             # v-0925v importpath: what the loop below loaded
for _v_mod in ("pinxfer", "downtime", "pinflat", "websockets"):
    try:
        __import__(_v_mod)
        _V_PREIMPORTED.append(_v_mod)
    except Exception:                                       # noqa: BLE001
        pass                     # imported again where used; a miss is that call's
del _v_mod
import builtins as _builtins                                # noqa: E402
_PRINT_FAILS = [0]


def print(*args, **kwargs):                                 # noqa: A001
    """v-0925v logfail: print() that cannot raise. The bot runs `python -u`
    with stdout redirected to a file; on a full disk (or a closed handle) the
    builtin raises OSError / ValueError from INSIDE the hedge pass -- after a
    hedge was sent and before it was booked, a K1 hedge-step error that stops
    entries and can leave a filled hedge unrecorded. A line that cannot be
    printed is counted (_PRINT_FAILS) and dropped; the records are the
    accounts, the console is not."""
    try:
        _builtins.print(*args, **kwargs)
    except (OSError, ValueError):
        _PRINT_FAILS[0] += 1


# v-0925v logfail: pintake, ordercli, livebook and kauth print as well --
# pintake when it raises its rails (set_limits, reached from autosize_tick in
# the loop), livebook from its socket threads -- and the builtin there raises
# the same OSError on a full disk (review 11-07). Their module-level `print`
# is this one, so none of them can raise out of a console write either.
for _v_mod in (pintake, getattr(pintake, "ordercli", None), livebook,
               sys.modules.get("kauth")):
    if _v_mod is not None:
        try:
            _v_mod.print = print
        except Exception:                                   # noqa: BLE001
            pass
del _v_mod


def ws_key():
    """v-0925v importpath: the WebSocket key id and key file, chosen exactly
    as livebook._default_key() chooses them -- both environment variables
    when both are set, else kauth's -- WITHOUT its sys.path.insert of the
    TEMP kals-work folder. kauth is the module this file already imported
    from the build's research folder. Never raises."""
    kid = os.environ.get("KALSHI_KEY_ID")
    kf = os.environ.get("KALSHI_KEY_FILE")
    if kid and kf:
        return kid, kf
    try:
        _k = sys.modules["kauth"]
        return _k.KEY_ID, _k.KEY_FILE
    except (KeyError, AttributeError):
        return kid, kf


def scrub_temp_path():
    """v-0925v importpath: take every TEMP kals-work entry off sys.path (a
    module may still add one); returns how many were removed. Never
    raises."""
    try:
        _bad = [p for p in list(sys.path)
                if "kals-work" in os.path.normcase(str(p))]
        for p in _bad:
            while p in sys.path:
                sys.path.remove(p)
        return len(_bad)
    except Exception:                                       # noqa: BLE001
        return 0
''')

# ============================================================================ 2. constants + pure helpers (module level)
R.after('''CHEAP_WINDOW = None             # (start_h, end_h, floor)
_DEFAULT_CHEAP_WINDOW = None
''', r'''
# ===========================================================================
# v-0925v (2026-11-07): THE FAIL-SAFE BUILD. The operator: "Anything that
# could cause the 1k+ loss needs to be addressed immediately. I'm serious.
# And the answer isn't betting less" -- and "Everything else that's possible
# to fix needs addressing as well as possible". Eleven ways the bot could keep
# BUYING while it could not see, book, hedge or account for what it already
# held. Each is closed the same way: when in doubt, NEW ENTRIES are blocked
# (trade_loop's entry_blocks -- never a hedge, a cancel or an exit; never a
# larger size; no existing brake loosened); the block clears itself when its
# condition does; each condition writes ONE record of its own kind so a
# watcher can alarm on it. Always on, no flag; no trading rule, threshold,
# size, gate or hedge trigger moves. Self-test messages carry "v-0925v".
#   bankread    balance_dollars alone is enough; cents optional
#   unbooked    determined/amended/finalized books; 900 s unbooked = provisional loss
#   hedgefail   HEDGE_FAIL_BLOCK failed hedge sends in a row block entries
#   hedgeexi    a hedge goes to the market's own exchange_index
#   universe    limit 20 by close_time, robust close_time, the /events fallback
#   expiry      no exit holding a bet when --minutes runs out
#   startbank   no entry before the first balance read (or the size mirror)
#   clockskew   the box clock against Kalshi's own stamps
#   logfail     a log that cannot be written stops new entries
#   importpath  the TEMP import folder is gone
#   apishape    one api_shape record per unexpected API shape
# ===========================================================================
# v-0925v unbooked. Kalshi's REST market statuses (docs, market lifecycle):
# initialized, active, inactive, closed, determined ("result is known,
# settlement timer is running"), disputed ("result has been challenged; may
# be re-determined"), amended ("re-determined after a dispute"), finalized
# ("settlement complete; terminal"); "settled" is the FILTER word for
# finalized and is accepted in case a response ever carries it. reconcile()
# booked ONLY "finalized" and, 900 s after the close, released a leg it had
# not booked: the day cap and the run abort never saw that money, win or
# lose. A rename of one status word would have made EVERY loss invisible to
# both stops, with the drawdown halt off (--no-drawdown-halt).
# Review round 11-07: a leg past UNBOOKED_AFTER_S is PARKED, not kept whole:
# the stake cap, the open cap and the sizer let go of it exactly as 0925u's
# release did (else a stuck 516-lot held the open cap and froze the sizer for
# hours), while reconcile keeps it, reads it, and books it whenever Kalshi
# answers -- once a minute, then every 10 minutes after 6 h, never released
# unbooked by time (a void is still released as it always was).
SETTLE_BOOK_STATUSES = ("determined", "amended", "finalized", "settled")
SETTLE_TERMINAL_STATUSES = ("finalized", "settled")
MARKET_STATUSES_KNOWN = ("initialized", "active", "inactive", "closed",
                         "determined", "disputed", "amended", "finalized",
                         "settled")
UNBOOKED_AFTER_S = 900.0       # a leg unbooked this long after its close is PROVISIONAL (parked)
UNBOOKED_POLL_S = 60.0         # its GET /markets/<ticker> cadence from then on...
UNBOOKED_SLOW_AFTER_S = 6 * 3600.0  # ...and from 6 h after the close
UNBOOKED_SLOW_POLL_S = 600.0   # ...every 10 minutes, for the rest of the run
UNBOOKED_HEDGE_WINDOW_S = 90.0  # no late poll (a blocking GET above the hedge
                               # pass) while a held market closes this soon
# v-0925v hedgefail: consecutive hedge sends (any market) that came back
# non-2xx before new entries are blocked, and how long a block outlives the
# close it happened in when no later hedge send succeeds ("the rest of the
# current close and the next close")
HEDGE_FAIL_BLOCK = 3
HEDGE_BROKEN_HOLD_S = 900.0
# v-0925v hedgeexi / universe: every series pin trades is crypto, on shard 2
# (checked live 2026-09-08 across all 11 series; KXBTCD the same)
CRYPTO_EXCHANGE_INDEX = 2
UNI_LIMIT = "20"               # rows per series per refresh (was "4")
UNI_EMPTY_REFRESHES = 3        # all-empty refreshes in a row before /events
UNI_EVENTS_EVERY_S = 60.0      # ...and then at most one /events try a minute
# v-0925v expiry: from the end of --minutes nothing is bought; the loop then
# runs until flat, at most EXPIRY_GRACE_S past the end, and keeps itself
# EXPIRY_MARGIN_S ahead of a stalled pass. EXPIRY_DRAIN_S is how long BEFORE
# the end the buying stops: 0. It was 1200 s, and the review (11-07) priced
# that: the 05:00 and 05:15 ET closes it gave up made $0.58 + $0.92 a day
# (10-15..11-07), ~$1.50 every 72-h run, for no safety -- a fill settles
# 20-65 s after its close and the grace already keeps the run alive until it
# holds nothing, so a bet bought one second before the end is watched,
# hedged and booked like any other.
EXPIRY_DRAIN_S = 0.0
EXPIRY_GRACE_S = 1800.0
EXPIRY_MARGIN_S = 60.0
# v-0925v startbank
STARTUP_BANK_BACKOFF_S = (1.0, 2.0, 4.0, 8.0, 16.0)
STARTUP_BANK_WAIT_S = 60.0     # then the size mirror's bank, when fresh
STARTUP_BANK_RETRY_S = 60.0    # ...and the balance read once a minute after
STARTUP_MIRROR_MAX_AGE_S = 86400.0
# v-0925v clockskew: Kalshi relays an index print ~66 ms after its stamp and
# this box gets it ~87 ms after (results/FEED_LEAD_2026-09-24.md,
# CLEANROOM_2026-09-27.md). (receipt - stamp) is the clock offset PLUS that
# lag, and lag only ever ADDS: so the offset is read from the LOW end of the
# window (CLOCK_SKEW_Q, the 5th percentile -- the fastest prints, which a
# single odd stamp cannot move), not the median. Review 11-07 replayed the
# median on the laptop collector's tape: it crossed 750 ms on feed lag alone
# (10-28 02Z three times, 410 s over the line) where the window's fast end
# never did -- as built it was an index-lag entry gate. A real offset of
# either sign moves every print, the fastest included, and still crosses.
CLOCK_SKEW_MAX_MS = 750.0
CLOCK_SKEW_HOLD_S = 60.0
CLOCK_SKEW_WINDOW_S = 60.0
CLOCK_SKEW_MIN_N = 20
CLOCK_SKEW_Q = 0.05
# v-0925v logfail
LOG_FAIL_BLOCK = 3
GUARD_ERROR_HOLD_S = 5.0       # a guard part that raised blocks at least this long
ENTRY_BLOCK_BEAT_S = 300.0     # while blocked: one entries_still_blocked record this often
DAYLOSS_REPLACE_TRIES = 4      # os.replace of the day file: a reader holding it
DAYLOSS_REPLACE_WAIT_S = 0.025  # open (the phone's stats) is waited out, not failed
ORDER_STATUSES_KNOWN = (None, "executed", "canceled", "cancelled", "resting",
                        "partially_filled_then_canceled", "pending")

# ---- v-0925v apishape: the sentinel -----------------------------------------
_API_SHAPE_SEEN = set()        # (endpoint, field, what) already queued
_API_SHAPE_Q = deque(maxlen=200)
_API_SHAPE_DROPPED = [0]


def api_shape(endpoint, field, what, **detail):
    """v-0925v apishape: queue ONE `api_shape` record per (endpoint, field,
    what) for the life of the process -- an expected field missing, a value
    of a kind never seen, a timestamp that will not parse. RECORDING ONLY: it
    decides nothing (the fixes that block entries do that themselves). Safe
    from any thread and from pure helpers that hold no `rec`; the trade loop
    writes the queue BELOW the hedge pass (api_shape_flush). Returns True the
    first time a key is seen. Never raises."""
    try:
        key = (str(endpoint), str(field), str(what))
        if key in _API_SHAPE_SEEN:
            return False
        _API_SHAPE_SEEN.add(key)
        ev = {}
        for k, v in detail.items():
            if k in ("kind", "t", "endpoint", "field", "what"):
                k = k + "_"                 # rec(kind, **kw) takes kind positionally
            ev[k] = (v if isinstance(v, (bool, int, float, type(None)))
                     else str(v)[:200])
        ev.update(endpoint=key[0], field=key[1], what=key[2])
        if len(_API_SHAPE_Q) == _API_SHAPE_Q.maxlen:
            _API_SHAPE_DROPPED[0] += 1
        _API_SHAPE_Q.append(ev)
        return True
    except Exception:                                    # noqa: BLE001
        return False


def api_shape_flush(rec, limit=50):
    """v-0925v apishape: write up to `limit` queued records. Never raises."""
    n = 0
    try:
        while _API_SHAPE_Q and n < limit:
            rec("api_shape", **_API_SHAPE_Q.popleft())
            n += 1
    except Exception:                                    # noqa: BLE001
        pass
    return n


def parse_close_time(ct):
    """v-0925v universe: a Kalshi ISO-8601 time -> UTC epoch seconds (int), or
    None. Everything the strict "%Y-%m-%dT%H:%M:%SZ" accepted, plus fractional
    seconds ("13:15:00.000Z", "13:15:00.123456Z", floored) and a numeric
    offset ("+00:00", "-05:00", "+0000"), converted to UTC. A time with no
    zone is refused (ambiguous). Never reads the local zone, never needs
    tzdata, never raises."""
    try:
        s = str(ct).strip()
        if len(s) < 20:
            return None
        base, rest = s[:19], s[19:]
        if (base[4] != "-" or base[7] != "-" or base[10] not in "Tt "
                or base[13] != ":" or base[16] != ":"):
            return None
        y, mo, d = int(base[0:4]), int(base[5:7]), int(base[8:10])
        h, mi, se = int(base[11:13]), int(base[14:16]), int(base[17:19])
        if rest[:1] == ".":
            i = 1
            while i < len(rest) and rest[i].isdigit():
                i += 1
            if i == 1:
                return None
            rest = rest[i:]
        if rest in ("Z", "z"):
            off = 0
        elif rest[:1] in ("+", "-") and len(rest) in (5, 6):
            if len(rest) == 6 and rest[3] != ":":
                return None
            hh, mm = int(rest[1:3]), int(rest[-2:])
            if hh > 23 or mm > 59:
                return None
            off = (hh * 3600 + mm * 60) * (1 if rest[0] == "+" else -1)
        else:
            return None
        if not (1 <= mo <= 12 and 1 <= d <= 31 and 0 <= h <= 23
                and 0 <= mi <= 59 and 0 <= se <= 60):
            return None
        return int(calendar.timegm((y, mo, d, h, mi, se, 0, 0, 0))) - off
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def market_exchange_index(m, endpoint="/markets"):
    """v-0925v universe: a market row's exchange_index as an int. A missing or
    unreadable one is NEVER 0 -- the general shard, where a crypto order is
    rejected or, worse, rests where _unrest's cancel cannot find it -- but
    CRYPTO_EXCHANGE_INDEX (every series pin trades is crypto), with one
    api_shape record. Never raises."""
    v = None
    try:
        v = (m or {}).get("exchange_index")
        if v is None or isinstance(v, bool):
            raise ValueError("missing")
        return int(v)
    except (TypeError, ValueError, AttributeError):
        api_shape(endpoint, "exchange_index",
                  "missing" if v is None else "unreadable", value=v,
                  used=CRYPTO_EXCHANGE_INDEX)
        return CRYPTO_EXCHANGE_INDEX


def hedge_exchange_index(ticker, *facts, crypto=None):
    """v-0925v hedgeexi: the exchange_index a HEDGE on `ticker` goes to --
    the first universe fact tuple (iid, close_s, strike, digits, exi) that
    carries one, i.e. the value the entry was sent with -- else
    CRYPTO_EXCHANGE_INDEX for a crypto series (every series pin trades),
    else 0 (Kalshi's general shard); either fallback is recorded once
    (api_shape). It used to be a hard-coded 2 at both hedge sends. Never
    raises."""
    for f in facts:
        try:
            if (f is not None and len(f) >= 5 and f[4] is not None
                    and not isinstance(f[4], bool)):
                return int(f[4])
        except (TypeError, ValueError):
            continue
    try:
        _ser = str(ticker).split("-")[0]
        _c = (bool(crypto) if crypto is not None
              else (_ser in SERIES_TO_INDEX or _ser in LADDER_SERIES))
    except Exception:                                    # noqa: BLE001
        _c = True
    api_shape("hedge", "exchange_index", "missing", ticker=ticker, crypto=_c)
    return CRYPTO_EXCHANGE_INDEX if _c else 0


def universe_facts(rows, iid, now_s, endpoint="/markets", horizon_s=900):
    """v-0925v universe: the [(ticker, (iid, close_s, strike, digits, exi))]
    the refresh keeps from ONE series' market rows -- every row closing inside
    [now_s, now_s + horizon_s], nearest close first (then ticker): the market
    is chosen by its close_time, never by its place in the answer. The reads
    are the refresh's own, kept exactly:
      * THE STRIKE IS RETURNED TWICE AND THEY DIFFER. Top-level floor_strike
        is TRUNCATED to the display precision; custom_strike.floor_strike is
        exact. Live 2026-09-08: DOGE 0.08926 vs '0.0892605'. DOGE's
        round_digits is 7, so the rounding correction is 5e-8 while the
        truncation error is 5e-7 -- ten times larger than the effect it was
        meant to model. The exact field wins wherever the exchange gives it;
        round_digits is custom_strike's; a row with no top-level floor_strike
        is skipped (as before).
      * EXCHANGE_INDEX IS NOT OPTIONAL. Checked live 2026-09-08 across all 11
        series: every open crypto 15M market reads exchange_index 2, not 0.
        take() defaults it to 0, so every live order was going to be routed
        to the wrong shard. Read from the row; missing = 2, never 0
        (market_exchange_index).
    And two changes: close_time goes through parse_close_time (fractional
    seconds and offsets accepted), and a row that cannot be read is SKIPPED
    with one api_shape record instead of raising out of the whole refresh
    (one strptime ValueError used to lose every series' markets for 20 s).
    Never raises."""
    out = []
    for m in rows or ():
        try:
            if not isinstance(m, dict):
                api_shape(endpoint, "market", "not_an_object",
                          type=type(m).__name__)
                continue
            tk = m.get("ticker")
            ct, sk = m.get("close_time"), m.get("floor_strike")
            if not tk or not ct:
                api_shape(endpoint, "ticker/close_time", "missing",
                          ticker=tk)
                continue
            if sk is None:
                api_shape(endpoint, "floor_strike", "missing", ticker=tk)
                continue
            _st = m.get("status")
            if _st is not None and _st not in MARKET_STATUSES_KNOWN:
                api_shape(endpoint, "status", "unknown", value=_st, ticker=tk)
            cs = parse_close_time(ct)
            if cs is None:
                api_shape(endpoint, "close_time", "unparsable", value=ct,
                          ticker=tk)
                continue
            if cs - now_s > horizon_s or cs < now_s:
                continue
            cs_ = m.get("custom_strike") or {}
            if not isinstance(cs_, dict):
                api_shape(endpoint, "custom_strike", "not_an_object",
                          ticker=tk)
                cs_ = {}
            d = cs_.get("round_digits")
            if cs_.get("floor_strike") is not None:
                try:
                    sk = float(cs_["floor_strike"])
                except (TypeError, ValueError):
                    pass
            try:
                sk = float(sk)
                d = int(d) if d is not None else None
            except (TypeError, ValueError):
                api_shape(endpoint, "floor_strike/round_digits", "unreadable",
                          ticker=tk, strike=sk, digits=d)
                continue
            out.append((int(cs), str(tk),
                        (iid, int(cs), sk, d,
                         market_exchange_index(m, endpoint))))
        except Exception as _e:                          # noqa: BLE001
            api_shape(endpoint, "market", "unreadable",
                      err=type(_e).__name__)
            continue
    out.sort(key=lambda r: (r[0], r[1]))
    return [(tk, f) for (_cs, tk, f) in out]


def events_rows(body):
    """v-0925v universe: the market rows nested in a GET /events
    ?with_nested_markets=true answer (events[].markets[]) whose status says
    they are OPEN ("active", or "open"): the event filter matches on ANY
    child market, so a nested market is taken only on its own word. One
    with no status at all is dropped and recorded once (api_shape) -- the
    review's case (11-07): it used to be read as open. [] when there are
    none. Never raises."""
    out = []
    try:
        evs = body.get("events")
        if not isinstance(evs, list):
            api_shape("/events", "events", "missing")
            return out
        for ev in evs:
            ms = ev.get("markets") if isinstance(ev, dict) else None
            if not isinstance(ms, list):
                continue
            for m in ms:
                if not isinstance(m, dict):
                    continue
                if m.get("status") is None:
                    api_shape("/events", "markets[].status", "missing",
                              ticker=m.get("ticker"))
                    continue
                if m.get("status") not in ("active", "open"):
                    continue
                out.append(m)
    except Exception:                                    # noqa: BLE001
        pass
    return out


def kalshi_maintenance(t):
    """v-0925v universe: True inside Kalshi's weekly maintenance, Thursday
    03:00-05:00 ET (the close's own Eastern clock: et_offset_s, no tzdata),
    when an empty market list is expected and is not a failure. Never
    raises."""
    try:
        _tm = globals().get("_REAL_TIME", time)         # the self-test fakes time()
        t = float(t)
        g = _tm.gmtime(t + et_offset_s(t))
        return g.tm_wday == 3 and 3 <= g.tm_hour < 5
    except Exception:                                    # noqa: BLE001
        return False


def settle_read(market, ticker=None):
    """v-0925v unbooked: (status, result) when `market` -- GET /markets/<t>'s
    "market" object -- can be BOOKED, else (None, None).
      * determined / amended / finalized / settled with result yes or no:
        bookable. determined is "result known, settlement timer running";
        amended is the result re-determined after a dispute.
      * disputed: NEVER booked -- the result is being challenged.
      * finalized / settled with no yes/no result (void, scalar): returned
        as-is, and reconcile releases that leg unbooked as it always did --
        terminal, nothing more will come.
      * anything else (closed, a determined market whose result has not
        arrived, an unknown word): not bookable yet.
    Status and result are compared lower-cased; an unknown status word, a
    missing status and a terminal non-yes/no result are each recorded once
    (api_shape). Never raises."""
    if not isinstance(market, dict):
        api_shape("/markets/<ticker>", "market", "not_an_object",
                  ticker=ticker)
        return None, None
    st, res = market.get("status"), market.get("result")
    st_n = st.strip().lower() if isinstance(st, str) else st
    res_n = res.strip().lower() if isinstance(res, str) else res
    if st_n is None:
        api_shape("/markets/<ticker>", "status", "missing", ticker=ticker)
        return None, None
    if st_n not in MARKET_STATUSES_KNOWN:
        api_shape("/markets/<ticker>", "status", "unknown", value=st,
                  ticker=ticker)
        return None, None
    if st_n in SETTLE_TERMINAL_STATUSES:
        if res_n not in ("yes", "no"):
            api_shape("/markets/<ticker>", "result", "terminal_not_yes_no",
                      value=res, status=st, ticker=ticker)
        return st_n, res_n
    if st_n in SETTLE_BOOK_STATUSES and res_n in ("yes", "no"):
        return st_n, res_n
    return None, None


def unbooked_worst(legs):
    """v-0925v unbooked: the most a market's unbooked legs [(want, cost, n),
    ...] can lose together, in dollars (<= 0): the worse of the two results,
    each leg paying 1 - cost or losing cost, less the taker fee. A single
    unhedged leg is its full cost; a hedged pair is what the pair can lose.
    Never raises; an unreadable leg counts its whole cost."""
    try:
        worst = None
        for r in ("yes", "no"):
            tot = 0.0
            for (w, p, n) in legs:
                p, n = float(p), float(n)
                tot += n * ((1.0 - p) if w == r else -p) - billed_fee(p, n)
            worst = tot if worst is None else min(worst, tot)
        return min(0.0, worst if worst is not None else 0.0)
    except Exception:                                    # noqa: BLE001
        tot = 0.0
        for leg in legs or ():
            try:
                tot -= float(leg[1]) * float(leg[2])
            except Exception:                            # noqa: BLE001
                pass
        return min(0.0, tot)


def unbooked_bound(unbooked, realised, day, loss_abort, live=True,
                   day_unbooked=None):
    """v-0925v unbooked: why a PROVISIONAL loss (`unbooked`, dollars <= 0)
    reaches the stop -- the run abort (realised + unbooked <= loss_abort) or,
    live, the ET day cap (the A79 day total, nothing on file = 0, + the part
    of the provisional loss that belongs to TODAY, `day_unbooked`, default
    all of it, <= loss_abort) -- or None. The same two comparisons
    risk_abort makes on settled money, with the unbooked worst case added:
    the brake sees the loss it cannot book yet. A market that closed on an
    earlier ET day counts against the run only (review 11-07: charged to
    every later day's cap it counted one loss against more than one day).
    Unreadable input is a reason (fail safe)."""
    try:
        u = float(unbooked)
        if not u < -1e-9:
            return None
        lim = float(loss_abort)
        r = float(realised or 0.0)
        if r + u <= lim:
            return ("run: realised $%+.2f + unbooked $%+.2f <= $%.2f"
                    % (r, u, lim))
        if live:
            dd = 0.0 if day is None else float(day)
            ud = u if day_unbooked is None else float(day_unbooked)
            if ud < -1e-9 and dd + ud <= lim:
                return ("day: today $%+.2f + unbooked today $%+.2f <= $%.2f"
                        % (dd, ud, lim))
        return None
    except (TypeError, ValueError):
        return "unreadable provisional loss"


def unbooked_split(markets, now):
    """v-0925v unbooked: (run, today) from {(close_s, ticker): worst}: the
    provisional loss over every market, and over the markets whose close
    falls on now's ET day (et_day_key; no tzdata). Unreadable = its whole
    worst on both (fail safe). Never raises."""
    run = day = 0.0
    try:
        _today = et_day_key(now)
    except Exception:                                    # noqa: BLE001
        _today = None
    for k, w in (markets or {}).items():
        try:
            w = min(0.0, float(w))
        except (TypeError, ValueError):
            continue
        run += w
        try:
            if _today is None or et_day_key(float(k[0])) == _today:
                day += w
        except Exception:                                # noqa: BLE001
            day += w
    return round(run, 4), round(day, 4)


def order_shape(out, what="entry"):
    """v-0925v apishape: one api_shape record for a 2xx order answer of a NEW
    shape -- a status word never seen, a fill or remaining count missing
    (pintake then reads the outcome as UNKNOWN, which K2 / v-safety2 already
    handle; this only says so, once). Recording only. Never raises."""
    try:
        if not isinstance(out, dict):
            return
        sc = out.get("status_code")
        if not (isinstance(sc, int) and 200 <= sc < 300):
            return
        _ep = str(getattr(pintake, "ENDPOINT", "/portfolio/orders"))
        if (out.get("status_source") == "response"
                and out.get("status") not in ORDER_STATUSES_KNOWN):
            api_shape(_ep, "status", "unknown", value=out.get("status"),
                      order=what)
        if out.get("parsed") and not out.get("fill_known"):
            api_shape(_ep, "fill_count", "missing", order=what)
        if out.get("parsed") and out.get("remaining") is None:
            api_shape(_ep, "remaining_count", "missing", order=what)
    except Exception:                                    # noqa: BLE001
        pass


def book_shape_wrap(book):
    """v-0925v apishape: wrap a LiveBook's snapshot and delta handlers so an
    orderbook frame of a NEW shape is recorded once -- a delta without
    price_dollars / delta_fp / side (livebook counts it as malformed and drops
    it), a snapshot with neither yes_dollars_fp nor no_dollars_fp but other
    keys (a rename: the book would silently read EMPTY), a level array that
    is not a list. The real handler always runs, after the look; the look is
    a few dict reads and cannot raise into the WebSocket thread. main() only;
    returns True when installed."""
    try:
        _snap, _delta = book.apply_snapshot, book.apply_delta
    except AttributeError:
        return False
    _known = ("market_ticker", "market_id", "yes_dollars_fp", "no_dollars_fp")

    def apply_snapshot(msg, sid, seq, rx_ms):
        try:
            if isinstance(msg, dict):
                if "yes_dollars_fp" not in msg and "no_dollars_fp" not in msg:
                    _x = sorted(str(k) for k in msg if k not in _known)
                    if _x:
                        api_shape("ws orderbook_snapshot",
                                  "yes_dollars_fp/no_dollars_fp",
                                  "absent_with_other_keys",
                                  keys=",".join(_x[:12]))
                else:
                    for _k in ("yes_dollars_fp", "no_dollars_fp"):
                        _v = msg.get(_k)
                        if _v is not None and not isinstance(_v, list):
                            api_shape("ws orderbook_snapshot", _k,
                                      "not_a_list", type=type(_v).__name__)
        except Exception:                                # noqa: BLE001
            pass
        return _snap(msg, sid, seq, rx_ms)

    def apply_delta(msg, sid, seq, rx_ms):
        try:
            if isinstance(msg, dict):
                for _k in ("price_dollars", "delta_fp", "side"):
                    if _k not in msg:
                        api_shape("ws orderbook_delta", _k, "missing",
                                  keys=",".join(sorted(str(k) for k in msg)[:12]))
        except Exception:                                # noqa: BLE001
            pass
        return _delta(msg, sid, seq, rx_ms)
    book.apply_snapshot = apply_snapshot
    book.apply_delta = apply_delta
    return True


# ---- v-0925v logfail: the write health of the two logs ----------------------
_LOG_HEALTH = {"log": {"streak": 0, "fails": 0, "said": False, "err": None},
               "traj": {"streak": 0, "fails": 0, "said": False, "err": None}}


def log_write_ok(which="log"):
    """v-0925v logfail: a write landed; the streak is over."""
    h = _LOG_HEALTH.get(which)
    if h is not None and h["streak"]:
        h["streak"] = 0
        h["said"] = False


def log_write_failed(which="log", exc=None):
    """v-0925v logfail: a write failed. At LOG_FAIL_BLOCK in a row ONE line
    goes to stderr (the log itself is what is failing). Never raises."""
    try:
        h = _LOG_HEALTH.setdefault(which, {"streak": 0, "fails": 0,
                                           "said": False, "err": None})
        h["streak"] += 1
        h["fails"] += 1
        h["err"] = ((type(exc).__name__ + ": " + str(exc))[:200]
                    if exc is not None else None)
        if h["streak"] >= LOG_FAIL_BLOCK and not h["said"]:
            h["said"] = True
            try:
                sys.stderr.write(
                    "pinrun v-0925v: %d %s writes in a row FAILED (%s) -- new "
                    "entries blocked until one lands; hedges continue\n"
                    % (h["streak"], which, h["err"]))
                sys.stderr.flush()
            except Exception:                            # noqa: BLE001
                pass
    except Exception:                                    # noqa: BLE001
        pass


def log_writes_failing(which="log"):
    """v-0925v logfail: True while the last LOG_FAIL_BLOCK writes failed."""
    h = _LOG_HEALTH.get(which) or {}
    return int(h.get("streak") or 0) >= LOG_FAIL_BLOCK


def log_append(path, kw):
    """v-0925v logfail: main()'s rec() write -- one JSON line appended -- with
    the outcome COUNTED instead of swallowed, so a full disk stops new
    entries (cannot account = cannot trade) rather than trading on with no
    records. Returns True when written. Never raises."""
    try:
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(kw, default=str) + "\n")
    except Exception as _e:                              # noqa: BLE001
        log_write_failed("log", _e)
        return False
    log_write_ok("log")
    return True


def v0925v_settings():
    """v-0925v: the fail-safe constants in force, for the start record."""
    return {"book_statuses": list(SETTLE_BOOK_STATUSES),
            "unbooked_after_s": UNBOOKED_AFTER_S,
            "unbooked_poll_s": UNBOOKED_POLL_S,
            "unbooked_slow_after_s": UNBOOKED_SLOW_AFTER_S,
            "unbooked_slow_poll_s": UNBOOKED_SLOW_POLL_S,
            "hedge_fail_block": HEDGE_FAIL_BLOCK,
            "hedge_broken_hold_s": HEDGE_BROKEN_HOLD_S,
            "uni_limit": UNI_LIMIT, "uni_empty_refreshes": UNI_EMPTY_REFRESHES,
            "uni_events_every_s": UNI_EVENTS_EVERY_S,
            "expiry_drain_s": EXPIRY_DRAIN_S, "expiry_grace_s": EXPIRY_GRACE_S,
            "startup_bank_wait_s": STARTUP_BANK_WAIT_S,
            "clock_skew_max_ms": CLOCK_SKEW_MAX_MS,
            "clock_skew_hold_s": CLOCK_SKEW_HOLD_S,
            "clock_skew_q": CLOCK_SKEW_Q,
            "log_fail_block": LOG_FAIL_BLOCK,
            "entry_block_beat_s": ENTRY_BLOCK_BEAT_S}


def v0925v_reset_process_state():
    """v-0925v: empty the api_shape sentinel, the log health, the pending day
    totals and the print-failure count. main() calls it right after the
    startup self-test: these were empty when the process started, the
    self-test plants every one of them and hands them back, and if a future
    check ever leaked one the live run would dedupe its first real api_shape
    against a test's key or start with a planted log failure. Returns what
    it found non-empty (for the start record)."""
    found = {"api_shape_seen": len(_API_SHAPE_SEEN),
             "api_shape_queued": len(_API_SHAPE_Q),
             "dayloss_pending": len(_DAYLOSS_PENDING),
             "log_streaks": sum(int((h or {}).get("streak") or 0)
                                for h in _LOG_HEALTH.values()),
             "print_fails": int(_PRINT_FAILS[0])}
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    _API_SHAPE_DROPPED[0] = 0
    _DAYLOSS_PENDING.clear()
    for _h in _LOG_HEALTH.values():
        _h.update(streak=0, fails=0, said=False, err=None)
    _PRINT_FAILS[0] = 0
    return found
''')

# ============================================================================ 3. the day-loss file: atomic, and a failed write is kept
R.before('''def day_loss(path=None, now=None):
''', r'''# v-0925v logfail: a day total whose write FAILED, by path. It is still the
# day's total: day_loss() reads it ahead of the stale file and the next
# add_day_loss() adds to it, and the trade loop blocks new entries until
# retry_day_loss() gets it onto the disk.
_DAYLOSS_PENDING = {}


def write_day_loss(path, d):
    """v-0925v logfail: the day file, atomically -- a temp file, flushed to
    the disk, then os.replace -- so a crash or a full disk can never leave a
    half-written file the day cap would read as "nothing on file". True when
    written. On Windows os.replace fails (PermissionError) while another
    process holds the target open -- the phone's stats command reads this
    file -- so the replace is tried DAYLOSS_REPLACE_TRIES times,
    DAYLOSS_REPLACE_WAIT_S apart (~75 ms at most), before the write counts
    as failed (review 11-07 reproduced it). Never raises."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        for _try in range(int(DAYLOSS_REPLACE_TRIES)):
            try:
                os.replace(tmp, path)
                break
            except OSError:
                if _try + 1 >= int(DAYLOSS_REPLACE_TRIES):
                    raise
                globals().get("_REAL_TIME", time).sleep(
                    float(DAYLOSS_REPLACE_WAIT_S))
        return True
    except (OSError, TypeError, ValueError):
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def retry_day_loss(path=None):
    """v-0925v logfail: write a pending day total. True when nothing is
    pending for `path` any more."""
    p = path or DAYLOSS_FILE
    d = _DAYLOSS_PENDING.get(p)
    if d is None:
        return True
    if write_day_loss(p, d):
        _DAYLOSS_PENDING.pop(p, None)
        return True
    return False


''')
R.replace('''    try:
        with open(path or DAYLOSS_FILE, encoding="utf-8") as fh:
            d = json.load(fh) or {}
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("day") != et_day_key(now):
''', '''    # v-0925v logfail: a total whose write failed is still today's total
    _pend = _DAYLOSS_PENDING.get(path or DAYLOSS_FILE)
    if _pend is not None and _pend.get("day") == et_day_key(now):
        try:
            return float(_pend["realised"])
        except (KeyError, TypeError, ValueError):
            pass
    try:
        with open(path or DAYLOSS_FILE, encoding="utf-8") as fh:
            d = json.load(fh) or {}
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("day") != et_day_key(now):
''')
R.replace('''    key = et_day_key(now)
    cur = day_loss(path, now)
    new = (cur or 0.0) + delta
    p = path or DAYLOSS_FILE
    try:
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"day": key, "realised": round(new, 4),
                       "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, fh)
        os.replace(tmp, p)
    except OSError:
        return new                       # in memory is better than nothing
    return new
''', '''    key = et_day_key(now)
    cur = day_loss(path, now)            # v-0925v: a pending total included
    new = (cur or 0.0) + delta
    p = path or DAYLOSS_FILE
    _drec = {"day": key, "realised": round(new, 4),
             "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if write_day_loss(p, _drec):
        _DAYLOSS_PENDING.pop(p, None)
    else:
        # v-0925v logfail: "in memory is better than nothing" was the old
        # answer, and the day cap then read a stale file. The total is kept
        # as PENDING: day_loss() reads it, the next settlement adds to it, and
        # the trade loop blocks new entries until it is on the disk.
        _DAYLOSS_PENDING[p] = _drec
    return new
''')

# ============================================================================ 4. read_bank: balance_dollars alone is enough
R.replace('''    """Live cash, in DOLLARS, or None.

    THE UNIT IS READ FROM THE RESPONSE, NEVER INFERRED FROM THE MAGNITUDE
    (CLAUDE.md hard rule 5). /portfolio/balance carries `balance` in cents AND
    `balance_dollars` as a decimal string. Both are required and they must
    agree, because the failure mode is not subtle: 19215 read as dollars asks
    for size 6535.
    """''', '''    """Live cash, in DOLLARS, or None.

    THE UNIT IS READ FROM THE RESPONSE, NEVER INFERRED FROM THE MAGNITUDE
    (CLAUDE.md hard rule 5). /portfolio/balance carries `balance` in cents AND
    `balance_dollars` as a decimal string. When both are there they must
    agree, because the failure mode is not subtle: 19215 read as dollars asks
    for size 6535.

    v-0925v bankread (2026-11-07): `balance_dollars` ALONE IS ENOUGH. Its unit
    is in its name (a fixed-point DOLLAR string, Kalshi's schema), so the
    cents field is a cross-check, not the source: requiring both meant one
    dropped field (Kalshi has removed fields with a week's notice: liquidity
    10-01, available_on_brokers 09-10) froze the bank for the run -- no
    resize, no day stop that follows the bank, and at startup the argv's
    -$60 stop for good. A missing `balance` is recorded once (api_shape) and
    the dollars are used; a cents value that is present must still agree to
    $0.01 (unreadable or disagreeing = None); `balance` alone is still
    refused -- dividing it by 100 would be inferring the unit.
    """''')
R.replace('''    cents, dollars = j.get("balance"), j.get("balance_dollars")
    if cents is None or dollars is None:
        return None
    try:
        a, b = float(cents) / 100.0, float(dollars)
    except (TypeError, ValueError):
        return None
    if abs(a - b) > 0.01:
        return None
    return b
''', '''    cents, dollars = j.get("balance"), j.get("balance_dollars")
    if dollars is None:
        api_shape("/portfolio/balance", "balance_dollars", "missing",
                  cents_present=cents is not None)
        return None
    try:
        b = float(dollars)
    except (TypeError, ValueError):
        b = None
    if b is None or b != b or abs(b) == float("inf"):
        api_shape("/portfolio/balance", "balance_dollars", "unreadable",
                  value=dollars)
        return None
    if cents is None:
        api_shape("/portfolio/balance", "balance", "missing",
                  used="balance_dollars")
        return b
    try:
        a = float(cents) / 100.0
    except (TypeError, ValueError):
        api_shape("/portfolio/balance", "balance", "unreadable", value=cents)
        return None
    if abs(a - b) > 0.01:
        api_shape("/portfolio/balance", "balance", "disagrees",
                  cents=cents, dollars=dollars)
        return None
    return b
''')

# ============================================================================ 5. ktruth: positions shape, market facts close_time / exchange_index
R.replace('''        rows = body.get("market_positions")
        if not isinstance(rows, list):
            return None
''', '''        rows = body.get("market_positions")
        if not isinstance(rows, list):
            api_shape("/portfolio/positions", "market_positions", "missing")
            return None
''')
R.replace('''            n = _ktf(x.get("position_fp"))
            if n is None:
                n = _ktf(x.get("position"))
            if not tk or n is None:
                continue
''', '''            n = _ktf(x.get("position_fp"))
            if n is None:
                n = _ktf(x.get("position"))
            if n is None:                        # v-0925v apishape
                api_shape("/portfolio/positions", "position_fp", "missing",
                          ticker=tk)
            if not tk or n is None:
                continue
''')
R.replace('''        cs = calendar.timegm(_REAL_TIME.strptime(ct, "%Y-%m-%dT%H:%M:%SZ"))
        d = cs_.get("round_digits")
        return (iid, int(cs), float(sk), int(d) if d is not None else None,
                int(m.get("exchange_index") or 0))
''', '''        cs = parse_close_time(ct)          # v-0925v universe
        if cs is None:
            api_shape("/markets/<ticker>", "close_time", "unparsable",
                      value=ct, ticker=tk)
            return None
        d = cs_.get("round_digits")
        return (iid, int(cs), float(sk), int(d) if d is not None else None,
                market_exchange_index(m, "/markets/<ticker>"))
''')
# the ladder's own rows: the same two reads
R.replace('''        try:
            cs = calendar.timegm(_REAL_TIME.strptime(ct, "%Y-%m-%dT%H:%M:%SZ"))
        except (TypeError, ValueError):
            continue
        if cs - now_s > LADDER_HORIZON_S or cs < now_s:
''', '''        cs = parse_close_time(ct)          # v-0925v universe
        if cs is None:
            api_shape("/markets?event_ticker", "close_time", "unparsable",
                      value=ct, ticker=m.get("ticker"))
            continue
        if cs - now_s > LADDER_HORIZON_S or cs < now_s:
''')
R.replace('''        cands.append((str(m["ticker"]), cs, sk,
                      int(d) if d is not None else None,
                      int(m.get("exchange_index") or 0)))
''', '''        cands.append((str(m["ticker"]), cs, sk,
                      int(d) if d is not None else None,
                      market_exchange_index(m, "/markets?event_ticker")))
''')

# ============================================================================ 6. clockskew: the index socket keeps (receipt - Kalshi stamp)
R.after('''        self.last_rx = {}                   # index_id -> local ms of last tick
''', '''        # v-0925v clockskew: (local receipt ms, receipt - Kalshi's stamp ms)
        # for every NEW print -- sending_ts_ms where the frame carries it
        # (Kalshi added it 2026-10-01), else the print's own time
        self.skew = deque(maxlen=2400)
''')
R.replace('''        kid, kfile = livebook._default_key()
        self.key_id = key_id or kid
''', '''        # v-0925v importpath: ws_key(), never livebook._default_key(), which
        # puts the TEMP kals-work folder at sys.path[0] when KALSHI_KEY_ID is
        # unset -- it was, on the live launcher, for the whole run
        kid, kfile = ws_key()
        self.key_id = key_id or kid
''')
R.replace('''        except Exception:
            self.stats["bad_tick"] += 1
            return
        with self.lock:
            old = self.ticks[iid].get(sec)
''','''        except Exception:
            self.stats["bad_tick"] += 1
            return
        try:                                    # v-0925v clockskew
            _sts = d.get("sending_ts_ms")
            _skref = (int(_sts) if _sts is not None and not isinstance(_sts, bool)
                      else int(data["time"]))
        except (TypeError, ValueError):
            _skref = None
        with self.lock:
            old = self.ticks[iid].get(sec)
''')
R.replace('''            self.last_rx[iid] = rx_ms
        self.stats["ticks"] += 1
''', '''            self.last_rx[iid] = rx_ms
            if old is None and _skref is not None:   # v-0925v: a NEW print only
                self.skew.append((rx_ms, rx_ms - _skref))
        self.stats["ticks"] += 1
''')
R.before('''    # ---- reads ----
    def recent_moves(self, iid, n=3):
''', '''    def clock_skew_ms(self, window_s=None, now_ms=None, q=None):
        """v-0925v clockskew: (estimate, n) of (local receipt ms - Kalshi's
        stamp ms) over the new prints RECEIVED in the last `window_s`
        seconds, or (None, 0). The estimate is the q-quantile, default
        CLOCK_SKEW_Q (the 5th percentile): receipt - stamp is the clock
        offset plus relay and network lag, lag only ever adds, so the
        fastest prints carry the offset and the median carries the lag too
        (q=0.5 gives the median, for the record). pin computes tau and index
        age from this box's clock; a healthy socket reads ~30-120 ms here,
        so an estimate hundreds of ms away is the clock, which then
        mis-times every gate that reads tau. The window is this box's clock
        on both ends, so a skew cannot hide itself. Never raises."""
        try:
            w = 1000.0 * float(CLOCK_SKEW_WINDOW_S if window_s is None
                               else window_s)
            nm = float(livebook.now_ms() if now_ms is None else now_ms)
            qq = float(CLOCK_SKEW_Q if q is None else q)
            with self.lock:
                xs = sorted(float(s) for (r, s) in self.skew if nm - r <= w)
            n = len(xs)
            if not n:
                return None, 0
            if qq >= 0.5 - 1e-12 and qq <= 0.5 + 1e-12:
                return ((xs[n // 2] if n % 2
                         else 0.5 * (xs[n // 2 - 1] + xs[n // 2])), n)
            return xs[min(n - 1, max(0, int(qq * n)))], n
        except Exception:                                # noqa: BLE001
            return None, 0

''')

# ============================================================================ 7. the trajectory writer counts its failures
R.replace('''            _s = int(_clk())
            if _sec[0] != _s or kind != "traj":
                _sec[0] = _s
                _fh[0].flush()
        except Exception:                                # noqa: BLE001
            try:
                if _fh[0] is not None:
                    _fh[0].close()
            except Exception:                            # noqa: BLE001
                pass
            _fh[0] = None
''', '''            _s = int(_clk())
            if _sec[0] != _s or kind != "traj":
                _sec[0] = _s
                _fh[0].flush()
            log_write_ok("traj")                         # v-0925v logfail
        except Exception as _e5:                         # noqa: BLE001
            log_write_failed("traj", _e5)                # v-0925v logfail: counted
            try:
                if _fh[0] is not None:
                    _fh[0].close()
            except Exception:                            # noqa: BLE001
                pass
            _fh[0] = None
''')

# ============================================================================ 8. trade_loop state
R.before('''    jump_capped_said = set() # v-jumpcap8: (close_s, ticker) logged once
''', '''    entry_blocks = {}        # v-0925v: reason -> {since, kind} while a fail-
                             # safe condition holds; ANY reason empties the
                             # scan (new entries only -- never a hedge)
    ub_said = set()          # v-0925v unbooked: (close_s, ticker, what) on record
    ub_parked = set()        # v-0925v unbooked: open_pos ids past UNBOOKED_AFTER_S
                             # (the caps and the sizer let go; still booked)
    ub_seen = {}             # v-0925v unbooked: ticker -> (status, result) last read
    ub_unpaid = {}           # v-0925v unbooked: ticker -> a market booked on a
                             # status Kalshi has not PAID yet (determined /
                             # amended): the sizer waits for finalized
    hf = {"streak": 0, "mkt": {}, "said": set(), "broken": None}
                             # v-0925v hedgefail: failed hedge sends in a row
                             # (any market / per market), hedge_fail already
                             # written per (close, ticker), the broken state
    _sb = {"pending": bool(live and AUTO_SIZE and getattr(a, "auto_size", True)),
           "t0": None, "seen": 0, "src": None}
                             # v-0925v startbank: no entry before the first
                             # balance read (live, auto-sized runs only)
''')

# ============================================================================ 9. the unbooked helpers, beside reconcile()
R.before('''    def reconcile():
        """Book settled P&L so the loss abort is a REAL brake, not a nominal one.
''', '''    def _ub_note(cs_, tk_, what_, **kw):
        """v-0925v unbooked: one `unbooked` record per (close, ticker, what):
        what = provisional (still unbooked UNBOOKED_AFTER_S after the close:
        parked, and its worst case now counts against the stops), booked (it
        booked late; the provisional amount is replaced by the real P&L),
        slow (still unbooked UNBOOKED_SLOW_AFTER_S after the close: read
        every UNBOOKED_SLOW_POLL_S from now on, still provisional) or
        unpaid_timeout (booked on determined/amended, never seen finalized
        within UNBOOKED_AFTER_S of the close: the sizer stops waiting).
        Never raises."""
        _k = (cs_, tk_, what_)
        if _k in ub_said:
            return
        ub_said.add(_k)
        try:
            rec("unbooked", what=what_, ticker=tk_, close_s=cs_,
                late_s=int(time.time() - float(cs_)), **kw)
        except Exception:                                # noqa: BLE001
            pass
        try:
            print(f"  *** UNBOOKED {tk_}: {what_} {kw}")
        except Exception:                                # noqa: BLE001
            pass

    def _ub_park(oid_, tk_, cost_, nfill_):
        """v-0925v unbooked: a leg still unbooked UNBOOKED_AFTER_S after its
        close is PARKED. Its stake goes back to the stake cap, and pintake
        drops the ticker's position (the open cap) once every leg on it is
        parked -- exactly what 0925u's give-up _release did at +900 s -- so
        a market Kalshi has not settled can no longer hold the caps for
        hours (review 11-07: kept whole, a stuck 516-lot sat in the open
        cap and froze the sizer for up to 6 h). The leg stays in open_pos:
        reconcile keeps reading it and books it when Kalshi answers, and
        _release then gives back nothing a second time. Never raises."""
        if oid_ in ub_parked:
            return
        ub_parked.add(oid_)
        try:
            pintake.LEDGER["committed"] = max(
                0.0, float(pintake.LEDGER.get("committed", 0.0))
                - committed_for(cost_, nfill_))
            if all(_o in ub_parked for _o, _v in open_pos.items()
                   if _v[4] == tk_):
                pintake.LEDGER["positions"].pop(tk_, None)
        except Exception:                                # noqa: BLE001
            pass

    def _ub_update():
        """v-0925v unbooked: the PROVISIONAL loss, recomputed from the parked
        legs at the end of every reconcile(): each market with a parked leg
        counts the worst its parked legs can lose together (unbooked_worst):
        a lone leg its full cost, a hedged pair what the pair can lose. A leg
        that books leaves open_pos, which is how the real P&L replaces the
        provisional amount. state["unbooked_mk"] keeps it per (close,
        ticker) -- the guard splits it by ET day. Never raises."""
        try:
            _per = {}
            for _o, (_c, _w, _p, _n, _t) in open_pos.items():
                if _o in ub_parked:
                    _per.setdefault((_c, _t), []).append((_w, _p, _n))
            _mk = {}
            for (_c, _t), _legs in _per.items():
                _wst = unbooked_worst(_legs)
                _mk[(_c, _t)] = round(_wst, 4)
                _seen = ub_seen.get(_t) or (None, None)
                _ub_note(_c, _t, "provisional", legs=len(_legs),
                         contracts=round(sum(float(_l[2]) for _l in _legs), 2),
                         worst=round(_wst, 2), status=_seen[0],
                         result=_seen[1])
            state["unbooked_mk"] = _mk
            state["unbooked_prov"] = round(sum(_mk.values()), 4)
        except Exception:                                # noqa: BLE001
            pass

    def _ub_sizer_view():
        """v-0925v unbooked: what autosize_tick is told is held -- open_pos
        WITHOUT the parked legs (their cost is already out of the cash it
        reads, so sizing on cash errs small; 0925u's release at +900 s did
        the same), PLUS one entry per market booked on a status Kalshi has
        not paid yet (ub_unpaid), so the A30 re-read after a loss cannot read
        a bank still short the same market's winning leg. Never raises."""
        try:
            _v = {k: x for k, x in open_pos.items() if k not in ub_parked}
            for _t, _u in ub_unpaid.items():
                _v["unpaid:" + str(_t)] = _u.get("close_s")
            return _v
        except Exception:                                # noqa: BLE001
            return open_pos

    def _ub_hedge_window():
        """v-0925v unbooked: True while a held, unparked position's market
        closes within UNBOOKED_HEDGE_WINDOW_S. A late poll is a blocking GET
        in reconcile, ABOVE the hedge pass, up to 20 s when Kalshi hangs; it
        waits until that close is over (v-cheapwin put its own late GETs
        below the hedge pass for this reason, A71). Never raises; a fault
        reads True (the poll waits, a hedge never does)."""
        try:
            _tn = time.time()
            for _o, _v in open_pos.items():
                if _o not in ub_parked and 0.0 < float(_v[0]) - _tn < UNBOOKED_HEDGE_WINDOW_S:
                    return True
            return False
        except Exception:                                # noqa: BLE001
            return True

    def _ub_unpaid_add(tk_, cs_, st_, res_, want_, cost_, nfill_, pnl_):
        """v-0925v unbooked: a leg was booked on determined / amended -- the
        result is known, the money is not paid. The market is kept for the
        sizer (_ub_sizer_view) and for a final read (_ub_unpaid_poll), with
        what was booked. Never raises."""
        try:
            _u = ub_unpaid.setdefault(tk_, {"close_s": cs_, "status": st_,
                                            "result": res_, "legs": [],
                                            "at": time.time()})
            _u["legs"].append((want_, float(cost_), float(nfill_), float(pnl_)))
        except Exception:                                # noqa: BLE001
            pass

    def _ub_unpaid_poll():
        """v-0925v unbooked: a market booked on determined / amended is read
        again every 15 s (never while a held market closes within
        UNBOOKED_HEDGE_WINDOW_S) until Kalshi calls it finalized / settled --
        then the sizer may read the bank -- or UNBOOKED_AFTER_S after its
        close (unbooked what=unpaid_timeout). A FINAL result that is not the
        one booked (a dispute re-determined it) is CORRECTED: the difference
        goes into the run's realised and, live, the day file, with one
        settle_changed record (review 11-07: booked on determined, a later
        amendment was never re-read). Never raises."""
        try:
            _tn = time.time()
            for _t in list(ub_unpaid):
                _u = ub_unpaid[_t]
                _cs = float(_u.get("close_s") or 0.0)
                if _tn > _cs + UNBOOKED_AFTER_S:
                    ub_unpaid.pop(_t, None)
                    _ub_note(_cs, _t, "unpaid_timeout", status=_u.get("status"),
                             result=_u.get("result"),
                             legs=len(_u.get("legs") or ()))
                    continue
                if _tn < float(_u.get("at") or 0.0) + 15.0 or _ub_hedge_window():
                    continue
                _u["at"] = _tn
                try:
                    _st9, _b9 = trade_get("/markets/" + _t)
                except Exception:                        # noqa: BLE001
                    continue
                if _st9 != 200 or not isinstance(_b9, dict):
                    continue
                _m9 = _b9.get("market") or {}
                _fs, _fr = settle_read(_m9, _t)
                if _fs not in SETTLE_TERMINAL_STATUSES:
                    continue
                ub_unpaid.pop(_t, None)
                if _fr == _u.get("result"):
                    continue
                _d = 0.0
                if _fr in ("yes", "no"):
                    for (_w9, _p9, _n9, _pl9) in (_u.get("legs") or ()):
                        _d += (_n9 * ((1.0 - _p9) if _w9 == _fr else -_p9)
                               - billed_fee(_p9, _n9)) - _pl9
                    pintake.record_pnl(_d, note=f"{_t} final {_fr}, booked "
                                                f"{_u.get('result')} on {_u.get('status')}")
                _dd = (add_day_loss(_d) if (live and abs(_d) > 1e-12) else None)
                rec("settle_changed", ticker=_t, close_s=_cs,
                    was=_u.get("result"), final=_fr, status=_fs,
                    booked_status=_u.get("status"),
                    legs=len(_u.get("legs") or ()),
                    delta_c=(round(100 * _d, 2) if _fr in ("yes", "no") else None),
                    corrected=bool(_fr in ("yes", "no")),
                    day_realised=(round(_dd, 4) if _dd is not None else None),
                    realised=round(float(pintake.LEDGER.get("realised", 0.0)), 4))
                print(f"  *** RESULT CHANGED {_t}: booked {_u.get('result')} on "
                      f"{_u.get('status')}, final {_fr} -> {100 * _d:+.2f}c corrected")
        except Exception:                                # noqa: BLE001
            pass

''')
R.replace('''        owed = committed_for(cost, nfill)
        pintake.LEDGER["committed"] = max(
            0.0, float(pintake.LEDGER.get("committed", 0.0)) - owed)
        open_pos.pop(oid, None)
''', '''        # v-0925v unbooked: a PARKED leg gave its stake back when it was
        # parked (_ub_park); it is given back exactly once
        owed = 0.0 if oid in ub_parked else committed_for(cost, nfill)
        ub_parked.discard(oid)
        pintake.LEDGER["committed"] = max(
            0.0, float(pintake.LEDGER.get("committed", 0.0)) - owed)
        open_pos.pop(oid, None)
''')

# ============================================================================ 10. reconcile(): book on any result-bearing status; park at 15 min; never release by time
R.replace('''        not finalised yet is left for the next pass.
        """
        for _oid in list(open_pos):
''', '''        not finalised yet is left for the next pass.
        """
        _ub_read = {}       # v-0925v: one late read per market per pass
        for _oid in list(open_pos):
''')
R.replace('''            if time.time() < recon_at.get(tk, 0.0) + 15.0:
                continue
            recon_at[tk] = time.time()
            try:
                # v-fastconn: trade_get is exactly get() unless --keep-warm
                st, b = trade_get("/markets/" + tk)
            except Exception:
                continue
            if st != 200 or not isinstance(b, dict):
                continue
            m = b.get("market") or {}
            if m.get("status") != "finalized":
                if time.time() > close_s + 900:
                    _release(_oid, tk, cost, nfill)   # give up, do not leak
                    _count_market(close_s, tk, None)  # v-countmkt: a leg gone
                continue
            res = m.get("result")
            if res not in ("yes", "no"):
''', '''            # v-0925v unbooked: BOOK ON ANY STATUS THAT CARRIES THE RESULT,
            # AND NEVER LET A LEG GO UNBOOKED BY TIME. Only "finalized" booked
            # before, and 900 s after the close a leg it had not booked was
            # RELEASED UNBOOKED: the day cap and the run abort never saw that
            # money, win or lose. Now (settle_read) determined, amended,
            # finalized and settled book with a yes/no result -- never
            # disputed -- and a leg not bookable UNBOOKED_AFTER_S after its
            # close is PARKED (_ub_park: the caps and the sizer let go, as the
            # old release did) and read on: once a minute, every 10 minutes
            # after 6 h, never inside a held market's last
            # UNBOOKED_HEDGE_WINDOW_S (the GET blocks, above the hedge pass),
            # and for as long as the run lasts. Its worst case is a
            # PROVISIONAL loss (_ub_update, below) that can block new
            # entries; when it books, the real P&L replaces it. A terminal
            # status with no yes/no result (void) is released unbooked as it
            # always was.
            _late = time.time() > close_s + UNBOOKED_AFTER_S
            if _late and _oid not in ub_parked:
                _ub_park(_oid, tk, cost, nfill)
            if _late and tk in _ub_read:
                st, b = _ub_read[tk]           # this pass's read of the market
            else:
                if time.time() < recon_at.get(tk, 0.0) + (
                        15.0 if not _late
                        else UNBOOKED_POLL_S
                        if time.time() <= close_s + UNBOOKED_SLOW_AFTER_S
                        else UNBOOKED_SLOW_POLL_S):
                    continue
                if _late and _ub_hedge_window():
                    continue
                recon_at[tk] = time.time()
                try:
                    # v-fastconn: trade_get is exactly get() unless --keep-warm
                    st, b = trade_get("/markets/" + tk)
                except Exception:
                    continue
                if _late:
                    _ub_read[tk] = (st, b)
            if st != 200 or not isinstance(b, dict):
                continue
            m = b.get("market") or {}
            _vst, res = settle_read(m, tk)
            ub_seen[tk] = ((m.get("status"), m.get("result"))
                           if isinstance(m, dict) else (None, None))
            if _vst is None:
                if _late and time.time() > close_s + UNBOOKED_SLOW_AFTER_S:
                    _ub_note(close_s, tk, "slow", status=ub_seen[tk][0],
                             result=ub_seen[tk][1],
                             poll_s=UNBOOKED_SLOW_POLL_S)
                continue
            if res not in ("yes", "no"):
''')
R.after('''            print(f"  SETTLED {tk} {want} vs {res} -> {100 * pnl:+.2f}c "
                  f"(run realised ${pintake.LEDGER['realised']:+.4f})")
''', '''            if _vst not in SETTLE_TERMINAL_STATUSES:
                # v-0925v unbooked: booked on a result Kalshi has not PAID yet
                # (determined / amended): the sizer waits for finalized, and a
                # different final result is corrected (_ub_unpaid_poll)
                _ub_unpaid_add(tk, close_s, _vst, res, want, cost, nfill, pnl)
            if _late:
                # v-0925v unbooked: booked late; the provisional amount is
                # replaced by this P&L at the _ub_update() below
                _ub_note(close_s, tk, "booked", status=_vst, result=res,
                         pnl_c=round(100 * pnl, 2))
''')
R.after('''        state["open_cost"] = sum(c * n for (_, _, c, n, _tk)
                                 in open_pos.values())
''', '''        _ub_unpaid_poll()                # v-0925v unbooked: the final read
        _ub_update()                     # v-0925v unbooked: the provisional loss
''')

# ============================================================================ 11. the guard: entry blocks, hedge failures, startup bank, skew, logs
R.before('''    # v-fastconn: the first conn_stats record CONN_STATS_FIRST_S into the loop
    _cs_next = [time.time() + CONN_STATS_FIRST_S]
''', r'''    # ===================================================================
    # v-0925v (2026-11-07): THE FAIL-SAFE GUARD -- NEW ENTRIES ONLY.
    #
    # The operator: "Anything that could cause the 1k+ loss needs to be
    # addressed immediately. I'm serious. And the answer isn't betting less."
    # Each condition here is one way pin could keep BUYING while it could not
    # see, book, hedge or account for what it already held. All act the same
    # way: a reason goes into `entry_blocks`, and while any reason is there
    # the scan sees no market -- the K1 `_mk = []` line, so a block can never
    # reach the hedge pass (above the scan), reconcile, a cancel, the drain or
    # an exit, and it never changes a size or a rail. A block is NOT a halt:
    # nothing here ends the run, every block clears itself when its condition
    # does (entries_resumed), and each condition writes one record of its own
    # kind when it starts, so a watcher can alarm on it:
    #   hedge_broken       HEDGE_FAIL_BLOCK hedge sends in a row came back
    #                      non-2xx (any market; hedge_fail per market/close)
    #   clock_skew         this box's clock is off Kalshi's by > 750 ms, 60 s
    #   expiry_drain       --minutes has run out (and no exit holding a bet)
    #   log_write_fail     the decision log cannot be written
    #   dayloss_write_fail the day-loss file cannot be written
    #   entries_blocked    reason "unbooked" (a provisional loss reaches the
    #                      day / run stop), "startup_bank" (no balance read
    #                      yet), "guard_error" (a part of this guard raised)
    #   entries_still_blocked  every ENTRY_BLOCK_BEAT_S while any block holds
    # ===================================================================
    state["entry_blocks"] = entry_blocks
    _vg = {"skew_since": None, "skew_at": None, "bk_at": None,
           "dl_at": None, "traj_said": False, "err_at": None,
           "err_said": set(), "as_said": set(), "beat_at": None}

    def _eb_set(reason, kind="entries_blocked", **detail):
        """v-0925v: start blocking NEW entries for `reason` (once; a block
        already in force is left alone). Writes `kind`. Never raises."""
        if reason in entry_blocks:
            return False
        entry_blocks[reason] = {"since": round(time.time(), 3), "kind": kind}
        try:
            rec(kind, reason=reason,
                blocks="new entries only; hedges, cancels, settlement and "
                       "exits run as before", **detail)
        except Exception:                                # noqa: BLE001
            pass
        try:
            print(f"  *** NEW ENTRIES BLOCKED ({reason}): {detail}. Hedging "
                  f"continues.")
        except Exception:                                # noqa: BLE001
            pass
        return True

    def _eb_clear(reason, **detail):
        """v-0925v: the condition behind `reason` is over; entries resume
        unless another reason still holds. Writes entries_resumed. Never
        raises."""
        _b = entry_blocks.pop(reason, None)
        if _b is None:
            return False
        try:
            rec("entries_resumed", reason=reason,
                blocked_s=round(time.time() - float(_b.get("since") or 0.0), 1),
                still_blocked=sorted(entry_blocks), **detail)
        except Exception:                                # noqa: BLE001
            pass
        try:
            print(f"  --- entries resume ({reason} cleared)"
                  + (f"; still blocked: {sorted(entry_blocks)}"
                     if entry_blocks else ""))
        except Exception:                                # noqa: BLE001
            pass
        return True

    def _hedge_exi(tk_):
        """v-0925v hedgeexi: the market's own exchange_index -- the value its
        entry was sent with (seen_markets / skip_facts / the ktruth facts)."""
        return hedge_exchange_index(
            tk_, seen_markets.get(tk_), skip_facts.get(tk_),
            _kt["facts"].get(tk_),
            crypto=(str(tk_).split("-")[0] in series_index))

    def _hf_note(cs_, tk_, code_, body_, tau_):
        """v-0925v hedgefail: one hedge send that did not come back 2xx -- a
        4xx, a refusal (status None), a -1 / 5xx, an exception. pintake books
        a 4xx as "rejected: nothing placed" (pintake._book), so the hedge
        pass read it as an empty fill and sent it again every second, and
        nothing said the insurance was not working: 202 of 202 off-grid
        hedges 10-31..11-04. Counted per market and across markets; the
        first per market per close is written as hedge_fail; at
        HEDGE_FAIL_BLOCK in a row (any market) NEW ENTRIES are blocked
        (hedge_broken) -- a bot whose insurance cannot be bought must not
        open positions that need it. The hedge itself is untouched: next
        second's try goes out exactly as before. Never raises."""
        try:
            hf["streak"] += 1
            hf["mkt"][tk_] = hf["mkt"].get(tk_, 0) + 1
            _b = None if body_ is None else str(body_)[:200]
            if (cs_, tk_) not in hf["said"]:
                hf["said"].add((cs_, tk_))
                rec("hedge_fail", ticker=tk_, close_s=cs_, status_code=code_,
                    body=_b, tau=tau_, streak=hf["streak"],
                    market_streak=hf["mkt"][tk_])
                print(f"  !!! HEDGE SEND FAILED {tk_}: status {code_} {_b} "
                      f"({hf['streak']} in a row)")
            if hf["streak"] >= HEDGE_FAIL_BLOCK:
                _until = float(cs_) + HEDGE_BROKEN_HOLD_S
                if hf["broken"] is None:
                    hf["broken"] = {"since": round(time.time(), 3),
                                    "until": _until}
                    _eb_set("hedge_broken", kind="hedge_broken",
                            streak=hf["streak"], ticker=tk_, close_s=cs_,
                            status_code=code_, body=_b, tau=tau_,
                            until_s=_until,
                            then="until a hedge send comes back 2xx, or the "
                                 "rest of this close and the next one pass")
                else:
                    hf["broken"]["until"] = max(float(hf["broken"]["until"]),
                                                _until)
        except Exception:                                # noqa: BLE001
            pass

    def _hf_ok(tk_):
        """v-0925v hedgefail: a hedge send came back 2xx -- the streak is over
        and a hedge_broken block clears. Never raises."""
        try:
            hf["streak"] = 0
            hf["mkt"].pop(tk_, None)
            if hf["broken"] is not None:
                hf["broken"] = None
                _eb_clear("hedge_broken", why="a hedge send came back 2xx",
                          ticker=tk_)
        except Exception:                                # noqa: BLE001
            pass

    def _hf_result(cs_, tk_, out_, tau_):
        """v-0925v hedgefail: judge one live hedge answer (2xx or not)."""
        try:
            _sc = (out_ or {}).get("status_code")
            if isinstance(_sc, int) and not isinstance(_sc, bool) and 200 <= _sc < 300:
                _hf_ok(tk_)
                order_shape(out_, "hedge")
            else:
                _hf_note(cs_, tk_, _sc,
                         (out_ or {}).get("error") or (out_ or {}).get("raw"),
                         tau_)
        except Exception:                                # noqa: BLE001
            pass

    def _vg_apishape(now_):
        """v-0925v apishape: write what the sentinel queued; once a second,
        a malformed-frame counter of either socket that has moved off zero
        is recorded once."""
        if _API_SHAPE_Q:
            api_shape_flush(rec)
        if _vg["bk_at"] == int(now_):
            return
        _vg["bk_at"] = int(now_)
        for _src, _obj in (("ws orderbook", book), ("ws cfbenchmarks_value", idx)):
            _st = getattr(_obj, "stats", None)
            if not hasattr(_st, "get"):
                continue
            for _k in ("delta_malformed", "bad_level", "snapshot_no_ticker",
                       "bad_ts_ms", "unparseable", "bad_tick"):
                _n = _st.get(_k, 0)
                if isinstance(_n, (int, float)) and _n > 0:
                    api_shape(_src, _k, "counted", count=int(_n))

    def _vg_unbooked(now_):
        """v-0925v unbooked: the run abort and the day cap, with the
        PROVISIONAL loss added -- risk_abort's two comparisons, which see
        settled money only. Every parked market counts against the run; only
        a market that closed on TODAY's ET day counts against the day cap
        (unbooked_split). Reaching either blocks new entries until the legs
        book (or the stop really trips)."""
        _u, _ud = unbooked_split(state.get("unbooked_mk") or {}, now_)
        if _u >= -1e-9:
            _eb_clear("unbooked", unbooked=0.0)
            return
        _why = unbooked_bound(_u, pintake.LEDGER.get("realised", 0.0),
                              (day_loss() if live else None), a.loss_abort,
                              live=bool(live), day_unbooked=_ud)
        if _why:
            _eb_set("unbooked", why=_why, unbooked=round(_u, 2),
                    unbooked_today=round(_ud, 2),
                    markets=len(state.get("unbooked_mk") or {}),
                    loss_abort=float(a.loss_abort))
        else:
            _eb_clear("unbooked", unbooked=round(_u, 2))

    def _vg_hedgefail(now_):
        """v-0925v hedgefail: no hedge send has succeeded, but the rest of the
        failing close and the next one have passed -- retry normally."""
        _br = hf.get("broken")
        if _br is not None and now_ >= float(_br["until"]):
            hf["broken"] = None
            hf["streak"] = 0
            _eb_clear("hedge_broken",
                      why="no hedge send came back 2xx, but the rest of that "
                          "close and the next one have passed: retrying "
                          "normally")

    def _vg_startbank(now_):
        """v-0925v startbank: NO ENTRY BEFORE THE FIRST BALANCE READ. Until it
        lands, the day stop is the argv's --loss-abort (-$60) and the size the
        argv's; with --loss-cap-frac the real stop exists only once a bank is
        read, and the sizer re-reads every AUTO_SIZE_EVERY_S (5 min). So: the
        read is retried STARTUP_BANK_BACKOFF_S apart (1, 2, 4, 8, 16 s); after
        STARTUP_BANK_WAIT_S (60 s), while flat, the bank the live bot itself
        last published with its size (pinrun-live-size.json, publish_size)
        sets the day stop if it is under 24 h old -- and the size only ever
        DOWN from the argv's (min with size_for_bank), never up; with no
        fresh mirror entries stay blocked and the read is retried once a
        minute. startup_bank says which source was used."""
        if not _sb["pending"]:
            return
        if state.get("bank") is not None:
            _sb["pending"] = False
            if _sb["t0"] is not None:                    # the first read had failed
                rec("startup_bank", source="api",
                    bank=round(float(state["bank"]), 2),
                    tries=int(state.get("autosize_fails", 0) or 0) + 1,
                    waited_s=round(now_ - float(_sb["t0"]), 1),
                    loss_cap=LOSS_CAP, loss_abort=float(a.loss_abort),
                    size=float(SIZE))
            _eb_clear("startup_bank", source="api")
            return
        if _sb["t0"] is None:
            _sb["t0"] = now_
        _fails = int(state.get("autosize_fails", 0) or 0)
        _eb_set("startup_bank", why="no balance read yet: the day stop is "
                                    "the argv's until one lands",
                loss_abort=float(a.loss_abort), size=float(SIZE),
                fails=_fails)
        _waited = now_ - float(_sb["t0"])
        if _waited >= STARTUP_BANK_WAIT_S and _sb["src"] is None and not open_pos:
            _mb = read_mirror_bank(max_age_s=STARTUP_MIRROR_MAX_AGE_S, now=now_)
            if _mb is not None:
                apply_loss_cap(a, _mb, rec=rec,
                               why="startup: the size mirror's bank (balance "
                                   "unreadable)")
                _want = min(float(SIZE), float(size_for_bank(_mb)))
                if _want < float(SIZE) - 1e-9:
                    apply_size(_want, a, f"startup: mirror bank ${_mb:.2f}",
                               rec=rec)
                _sb["src"] = "mirror"
                _sb["pending"] = False
                rec("startup_bank", source="mirror", bank=round(float(_mb), 2),
                    tries=_fails, waited_s=round(_waited, 1),
                    loss_cap=LOSS_CAP, loss_abort=float(a.loss_abort),
                    size=float(SIZE), max_age_s=STARTUP_MIRROR_MAX_AGE_S)
                _eb_clear("startup_bank", source="mirror")
                return
            _sb["src"] = "none"
            rec("startup_bank", source="none", tries=_fails,
                waited_s=round(_waited, 1), loss_abort=float(a.loss_abort),
                why="the balance cannot be read and the size mirror is "
                    "missing or older than 24 h: new entries stay blocked; "
                    "the read is retried once a minute")
        if _fails > _sb["seen"]:
            _sb["seen"] = _fails
            _dl = (STARTUP_BANK_BACKOFF_S[min(_fails - 1, len(STARTUP_BANK_BACKOFF_S) - 1)]
                   if _waited < STARTUP_BANK_WAIT_S else STARTUP_BANK_RETRY_S)
            # autosize_tick reads again once AUTO_SIZE_EVERY_S has passed
            # since autosize_at: back-date it so the next read is _dl away
            state["autosize_at"] = now_ - float(AUTO_SIZE_EVERY_S) + float(_dl)

    def _vg_clockskew(now_):
        """v-0925v clockskew: once a second, the index socket's clock offset
        -- the FAST end (CLOCK_SKEW_Q) of (receipt - Kalshi's stamp) over the
        window, which feed lag cannot raise -- past CLOCK_SKEW_MAX_MS either
        way, over at least CLOCK_SKEW_MIN_N prints, for CLOCK_SKEW_HOLD_S:
        blocked until it is back inside (and the hold starts again from
        zero)."""
        if _vg["skew_at"] == int(now_):
            return
        _vg["skew_at"] = int(now_)
        _fn = getattr(idx, "clock_skew_ms", None)
        if not callable(_fn):
            return
        _off, _n = _fn(CLOCK_SKEW_WINDOW_S, q=CLOCK_SKEW_Q)
        if (_off is not None and int(_n or 0) >= CLOCK_SKEW_MIN_N
                and abs(float(_off)) > CLOCK_SKEW_MAX_MS):
            if _vg["skew_since"] is None:
                _vg["skew_since"] = now_
            if now_ - float(_vg["skew_since"]) >= CLOCK_SKEW_HOLD_S:
                _med = _fn(CLOCK_SKEW_WINDOW_S, q=0.5)[0]
                _eb_set("clock_skew", kind="clock_skew",
                        offset_ms=round(float(_off), 1),
                        median_ms=(None if _med is None else round(float(_med), 1)),
                        n=int(_n), q=CLOCK_SKEW_Q, limit_ms=CLOCK_SKEW_MAX_MS,
                        held_s=round(now_ - float(_vg["skew_since"]), 1),
                        source="index prints: receipt - sending_ts_ms "
                               "(else the print time), the window's fast end")
        else:
            _vg["skew_since"] = None
            _eb_clear("clock_skew",
                      offset_ms=(None if _off is None else round(float(_off), 1)),
                      n=int(_n or 0))

    def _vg_logfail(now_):
        """v-0925v logfail: the decision log and (live) the day-loss file.
        A log that cannot be written blocks new entries (cannot account =
        cannot trade); a day total that could not be written is retried once
        a second and blocks new entries until it lands. The trajectory file
        is an instrument, not the accounts: its failures are recorded once
        and block nothing."""
        _h = _LOG_HEALTH.get("log") or {}
        if log_writes_failing("log"):
            _eb_set("log_write", kind="log_write_fail", which="log",
                    streak=int(_h.get("streak") or 0),
                    fails=int(_h.get("fails") or 0), err=_h.get("err"))
        else:
            _eb_clear("log_write", which="log")
        _ht = _LOG_HEALTH.get("traj") or {}
        if log_writes_failing("traj"):
            if not _vg["traj_said"]:
                _vg["traj_said"] = True
                rec("log_write_fail", which="traj",
                    streak=int(_ht.get("streak") or 0), err=_ht.get("err"),
                    blocks="nothing: the trajectory is an instrument")
        else:
            _vg["traj_said"] = False
        if live:
            if _DAYLOSS_PENDING.get(DAYLOSS_FILE) is not None:
                if _vg["dl_at"] != int(now_):
                    _vg["dl_at"] = int(now_)
                    retry_day_loss(DAYLOSS_FILE)
                _pd = _DAYLOSS_PENDING.get(DAYLOSS_FILE)
                if _pd is not None:
                    _eb_set("dayloss_write", kind="dayloss_write_fail",
                            path=DAYLOSS_FILE, day=_pd.get("day"),
                            realised=_pd.get("realised"))
                else:
                    _eb_clear("dayloss_write", path=DAYLOSS_FILE)
            else:
                _eb_clear("dayloss_write", path=DAYLOSS_FILE)

    def _vg_beat(now_):
        """v-0925v: while any new-entry block holds, ONE entries_still_blocked
        record every ENTRY_BLOCK_BEAT_S with every reason and when it began.
        A block is recorded once, when it starts; a reader of the log's TAIL
        (the phone reads its last 256 KB, a few minutes of a busy log) would
        otherwise lose a long block the moment that record scrolled out --
        and an alarm needs to know how long it has lasted."""
        if not entry_blocks:
            _vg["beat_at"] = None
            return
        if _vg["beat_at"] is None:
            _vg["beat_at"] = now_
            return
        if now_ - float(_vg["beat_at"]) < ENTRY_BLOCK_BEAT_S:
            return
        _vg["beat_at"] = now_
        _since = {r: round(float(b.get("since") or now_), 1)
                  for r, b in entry_blocks.items()}
        rec("entries_still_blocked", reasons=sorted(entry_blocks),
            since=_since, blocked_s=round(now_ - min(_since.values()), 1),
            kinds={r: b.get("kind") for r, b in entry_blocks.items()},
            blocks="new entries only; hedges, cancels, settlement and exits "
                   "run as before")

    _VG_PARTS = (("apishape", _vg_apishape), ("unbooked", _vg_unbooked),
                 ("hedgefail", _vg_hedgefail), ("startbank", _vg_startbank),
                 ("clockskew", _vg_clockskew), ("logfail", _vg_logfail),
                 ("beat", _vg_beat))

    def _v_guard(now_):
        """v-0925v: every part, once a pass, each guarded on its own. A part
        that RAISES blocks new entries (guard_error) for at least
        GUARD_ERROR_HOLD_S -- when in doubt, no new bet -- and is recorded
        once per (part, error type). Never raises."""
        try:
            _bad = []
            for _nm, _fn in _VG_PARTS:
                try:
                    _fn(now_)
                except Exception as _eg:                 # noqa: BLE001
                    _bad.append(_nm)
                    _ke = (_nm, type(_eg).__name__)
                    if _ke not in _vg["err_said"]:
                        _vg["err_said"].add(_ke)
                        _k1_error("guard_" + _nm, None, None, _eg)
            if _bad:
                _vg["err_at"] = now_
                _eb_set("guard_error", parts=_bad)
            elif (_vg["err_at"] is not None
                  and now_ - float(_vg["err_at"]) >= GUARD_ERROR_HOLD_S):
                _vg["err_at"] = None
                _eb_clear("guard_error")
        except Exception as _evg:                        # noqa: BLE001
            try:
                _vg["err_at"] = now_
                _k1_error("v_guard", None, None, _evg)
                _eb_set("guard_error", parts=["v_guard"])
            except Exception:                            # noqa: BLE001
                pass

    def _v_expiry(now_, end_):
        """v-0925v expiry: THE RUN DOES NOT END HOLDING A BET. When --minutes
        (4320 live) ran out the loop simply returned -- with a position on
        the books, no hedge watch for the rest of its close and no settlement
        booked -- and watch_bot's restart started a process that knows
        nothing of it (the startup read skips a closed market). Now nothing
        is bought from EXPIRY_DRAIN_S before the end (0: the end itself;
        expiry_drain), and from EXPIRY_MARGIN_S before it the loop's bound is kept that
        far ahead -- hedge pass, reconcile, everything but entries -- until
        it is FLAT (no open position, no unknown order, nothing in the
        ledger) or EXPIRY_GRACE_S past the end; expiry_exit says which. Not
        A74's drain: that is a halt (a halt record, a 600 s cap) and this is
        the run's ordinary end. Returns the loop's new bound; never raises
        (a fault keeps the loop alive, inside the grace)."""
        try:
            if now_ >= _vxp["drain_at"]:
                _eb_set("expiry_drain", kind="expiry_drain",
                        end_in_s=round(_vxp["end0"] - now_, 1),
                        grace_s=EXPIRY_GRACE_S, open_positions=len(open_pos))
            if now_ < _vxp["end0"] - EXPIRY_MARGIN_S:
                return end_
            _xflat = (not open_pos and not _kt_holding()
                      and open_contracts(pintake.LEDGER) <= 1e-9)
            _xgrace = now_ >= _vxp["end0"] + EXPIRY_GRACE_S
            if now_ >= _vxp["end0"] and (_xflat or _xgrace):
                _vxp["done"] = True
                rec("expiry_exit", flat=bool(_xflat),
                    why=("flat" if _xflat else
                         "grace: still holding %d position(s) EXPIRY_GRACE_S "
                         "after the end" % len(open_pos)),
                    past_end_s=round(now_ - _vxp["end0"], 1),
                    open_positions=len(open_pos))
                return now_
            # the cap sits a little past the grace, so the pass that writes
            # expiry_exit always comes before the loop's own bound
            return min(_vxp["end0"] + EXPIRY_GRACE_S + 5.0,
                       max(_vxp["end0"], now_ + EXPIRY_MARGIN_S))
        except Exception as _exe:                        # noqa: BLE001
            try:
                _k1_error("expiry", None, None, _exe)
            except Exception:                            # noqa: BLE001
                pass
            return max(end_, min(_vxp["end0"] + EXPIRY_GRACE_S + 5.0,
                                 now_ + EXPIRY_MARGIN_S))

    # v-0925v expiry: `end` is the loop's own bound. It is only ever pushed
    # LATER, while something is still held (or a pass could stall past it),
    # and never past the original end + EXPIRY_GRACE_S. The offline worlds
    # say expiry_drain=False; main()'s args do not carry it, so live is on.
    _vxp = {"on": bool(getattr(a, "expiry_drain", True)), "end0": float(end),
           "done": False}
    _vxp["drain_at"] = _vxp["end0"] - max(0.0, min(
        float(EXPIRY_DRAIN_S), 0.25 * max(0.0, float(a.minutes) * 60.0)))

''')

# the per-pass call, BELOW the hedge pass and the cheap-window settle, ABOVE the risk check
R.before('''        # A69: THE RISK CHECK, NOW BELOW THE HEDGE PASS. It used to sit above
''', r'''        # v-0925v: THE FAIL-SAFE GUARD, once a pass. HERE because it is below
        # the hedge pass (nothing here may delay or skip a hedge) and above the
        # risk check, the pause and the drain, so it runs on every pass --
        # paused, draining or trading. It can only ADD a reason to
        # entry_blocks; the scan below then sees no market. Neither call can
        # raise (each part is guarded inside; a part that raises blocks).
        _v_guard(now)
        # v-0925v expiry: THE RUN DOES NOT END HOLDING A BET (_v_expiry).
        if _vxp["on"] and not _vxp["done"]:
            end = _v_expiry(now, end)

''')

# the scan sees no market while any block holds
R.replace('''        if state.get("entries_stopped"):
            _mk = []        # K1: no NEW entries (belt and braces: the drain
                            # above already skips the scan while it holds)
''', '''        if state.get("entries_stopped"):
            _mk = []        # K1: no NEW entries (belt and braces: the drain
                            # above already skips the scan while it holds)
        if entry_blocks:
            _mk = []        # v-0925v: a fail-safe block -- NEW entries only;
                            # the hedge pass above never reads entry_blocks
''')

# ============================================================================ 12. the hedge sends: exchange_index, failures counted
R.before('''                    _ht_send_ms = int(round(time.time() * 1000.0))     # (5)
''', '''                    _hexi = _hedge_exi(_htk)     # v-0925v hedgeexi: the market's own shard
''')
R.replace('''                        _hout = pintake.take(CREDS["base"], CREDS["pk"], CREDS["key_id"],
                                             _htk, _opp, float(_hlimit), _hn_take,
                                             float(_hcs), exchange_index=2,
                                             hedge=True)
                    except Exception as _e:                      # noqa: BLE001
                        state["order_errors"] = state.get("order_errors", 0) + 1
                        rec("error", where="hedge_take", ticker=_htk, err=str(_e)[:300])
                        continue
                    _href = _hout.get("refused") or []
                    if _href or _hout.get("status_code") is None:
                        rec("hedge_refused", ticker=_htk, why="take_refused",
                            err=str(_href)[:300], tau=_htau)
                        continue
''', '''                        _hout = pintake.take(CREDS["base"], CREDS["pk"], CREDS["key_id"],
                                             _htk, _opp, float(_hlimit), _hn_take,
                                             float(_hcs), exchange_index=_hexi,
                                             hedge=True)
                    except Exception as _e:                      # noqa: BLE001
                        state["order_errors"] = state.get("order_errors", 0) + 1
                        rec("error", where="hedge_take", ticker=_htk, err=str(_e)[:300])
                        _hf_note(_hcs, _htk, None, type(_e).__name__ + ": "
                                 + str(_e)[:160], _htau)        # v-0925v hedgefail
                        continue
                    _href = _hout.get("refused") or []
                    if _href or _hout.get("status_code") is None:
                        rec("hedge_refused", ticker=_htk, why="take_refused",
                            err=str(_href)[:300], tau=_htau)
                        _hf_note(_hcs, _htk, _hout.get("status_code"),
                                 _href or _hout.get("raw"), _htau)  # v-0925v hedgefail
                        continue
''')
R.replace('''                    _hsc = _hout.get("status_code")
                    _hunr = _hout.get("unrest")
''', '''                    _hsc = _hout.get("status_code")
                    _hunr = _hout.get("unrest")
                    # v-0925v hedgefail: a 2xx ends the failure streak; a 4xx
                    # (pintake: "rejected: nothing placed"), -1 or 5xx counts
                    _hf_result(_hcs, _htk, _hout, _htau)
''')
R.replace('''                                                      float(_hcs), exchange_index=2,
                                                      hedge=True, extra=True)
''', '''                                                      float(_hcs), exchange_index=_hexi,
                                                      hedge=True, extra=True)
''')
# the extra (odds) leg's ANSWER counts like the cover's (review 11-07: its 4xx went uncounted). A REFUSAL of the extra
# (status None) is not counted: that is pintake's stake cap / loss abort refusing new exposure (v-extracap), not
# insurance failing -- the cover it rides behind already filled.
R.replace('''                                    _hxsc = _hxout.get("status_code")
                                    _hxun = _hxout.get("unrest")
''', '''                                    _hxsc = _hxout.get("status_code")
                                    _hxun = _hxout.get("unrest")
                                    # v-0925v hedgefail: the extra's answer is
                                    # judged like the cover's (a refusal is the
                                    # dollar rails, above, and is not counted)
                                    _hf_result(_hcs, _htk, _hxout, _htau)
''')

# the sizer: told what is really held (parked legs out, unpaid markets in), and guarded (pintake prints from inside it)
R.replace('''        _asz = autosize_tick(state, a, open_pos, rec=rec)
        if _asz:
            print(f"  --- AUTO-SIZE: {_asz}")
''', '''        # v-0925v unbooked: the sizer is told what is really held -- the
        # parked legs out (0925u released them at +900 s; kept whole they
        # froze the sizer for up to 6 h), the markets booked but not yet paid
        # in (_ub_sizer_view). And it is GUARDED, like reconcile above: it
        # reads the balance and moves pintake's rails, and an exception there
        # (pintake's own console line on a full disk was one) used to leave
        # trade_loop; now it is counted, written once per kind, and the pass
        # goes on to the hedge pass.
        try:
            _asz = autosize_tick(state, a, _ub_sizer_view(), rec=rec)
        except Exception as _eas:                        # noqa: BLE001
            _asz = None
            state["autosize_errors"] = state.get("autosize_errors", 0) + 1
            if type(_eas).__name__ not in _vg["as_said"]:
                _vg["as_said"].add(type(_eas).__name__)
                try:
                    rec("error", where="autosize", err=str(_eas)[:300],
                        n=state["autosize_errors"])
                except Exception:                        # noqa: BLE001
                    pass
        if _asz:
            print(f"  --- AUTO-SIZE: {_asz}")
''')
# the existing check pins the call line; it moves inside the guard
R.replace('''        ck("        _asz = autosize_tick(state, a, open_pos, rec=rec)"
           in _lb.splitlines(),
           "autosize_tick must be called in the trade loop")''', '''        ck("            _asz = autosize_tick(state, a, _ub_sizer_view(), rec=rec)"
           in _lb.splitlines(),
           "autosize_tick must be called in the trade loop (v-0925v: inside a "
           "counted guard, told what is really held)")''')

# the entry's answer: shape only
R.before('''                        _kt_note_unknown("entry", out, tk, want, close_s,
''', '''                        order_shape(out, "entry")      # v-0925v apishape: records only
''')

# ============================================================================ 13. the universe refresh
R.after('''            _uni_n = None                       # R2: markets THIS refresh built
''', '''            _uni_src, _uni_rows, _uni_n15, _uni_http = "markets", 0, 0, []
            _uni_ok = 0                         # v-0925v universe: which path
                                                # supplied markets, 15M rows
                                                # answered, 15M series asked,
                                                # failures, series answering 200
''')
R.span('''                    # v-fastconn: trade_get is exactly get() unless
                    # --keep-warm (then: the same GET, kept connection)
                    st, b = trade_get("/markets", {"series_ticker": series,
''', '''                            _skf[m["ticker"]] = _fct
                            continue
                        fresh[m["ticker"]] = _fct
''', '''                    # v-0925v universe: limit UNI_LIMIT (20), not 4 -- the
                    # market closing next is chosen by its close_time
                    # (universe_facts sorts by it), never by its place in the
                    # first four rows -- and every row is read by
                    # universe_facts(): fractional seconds and offsets in
                    # close_time are accepted, a row that cannot be read is
                    # skipped with one api_shape record instead of raising out
                    # of the whole refresh, and a missing exchange_index is
                    # the crypto shard 2, never 0. (The strike and
                    # exchange_index notes that lived here are in its
                    # docstring.)
                    # v-fastconn: trade_get is exactly get() unless
                    # --keep-warm (then: the same GET, kept connection)
                    _uni_n15 += 1
                    st, b = trade_get("/markets", {"series_ticker": series,
                                                   "status": "open",
                                                   "limit": UNI_LIMIT})
                    if st != 200 or not isinstance(b, dict):
                        rec("skip", why=f"universe_http_{st}", series=series)
                        _uni_http.append(st)
                        continue
                    _rows15 = b.get("markets")
                    if not isinstance(_rows15, list):
                        api_shape("/markets", "markets", "missing",
                                  series=series)
                        _rows15 = []
                    _uni_ok += 1
                    _uni_rows += len(_rows15)
                    for _ftk, _fct in universe_facts(_rows15, iid, now_s,
                                                     "/markets"):
                        if SKIP_COINS and series in SKIP_COINS:
                            # v-skiphype: OUT OF THE UNIVERSE. Never scanned,
                            # never watched; its facts kept only so a held
                            # position in it can be adopted and protected.
                            _skf[_ftk] = _fct
                            continue
                        fresh[_ftk] = _fct
                # v-0925v universe: EVERY 15-minute series answered 200 with
                # an EMPTY list on UNI_EMPTY_REFRESHES refreshes in a row --
                # about a minute -- outside Kalshi's Thursday 03:00-05:00 ET
                # maintenance: the same markets are asked for the other way,
                # GET /events with nested markets, at most once every
                # UNI_EVENTS_EVERY_S (the next refreshes try /markets first
                # again). A status filter or field Kalshi renames would
                # otherwise leave the bot watching nothing, silently. An HTTP
                # failure is NOT an empty list (review 11-07): in an outage the
                # fallback would only add 12 signed GETs to a host that is
                # already failing, each able to hang 20 s in the loop -- a
                # refresh with failures and no rows leaves the count as it is.
                # universe_empty says so once per streak (and again when
                # /markets recovers); every universe record says which path
                # supplied markets.
                if _uni_n15:
                    if _uni_rows > 0:
                        if state.get("uni_empty_said"):
                            rec("universe_empty", what="recovered",
                                refreshes=int(state.get("uni_empty", 0)),
                                rows=_uni_rows)
                        state["uni_empty"] = 0
                        state["uni_empty_said"] = False
                    elif _uni_ok == _uni_n15:
                        state["uni_empty"] = int(state.get("uni_empty", 0)) + 1
                    if (int(state.get("uni_empty", 0)) >= UNI_EMPTY_REFRESHES
                            and not kalshi_maintenance(now)
                            and now - float(state.get("uni_events_at", -1e18))
                            >= UNI_EVENTS_EVERY_S):
                        state["uni_events_at"] = now
                        _uni_src = "events"
                        _uni_evn = 0
                        for series, iid in series_index.items():
                            if series in LADDER_SERIES:
                                continue
                            st, b = trade_get("/events", {
                                "series_ticker": series, "status": "open",
                                "with_nested_markets": "true",
                                "limit": UNI_LIMIT})
                            if st != 200 or not isinstance(b, dict):
                                rec("skip", why=f"universe_events_http_{st}",
                                    series=series)
                                continue
                            for _ftk, _fct in universe_facts(
                                    events_rows(b), iid, now_s, "/events"):
                                _uni_evn += 1
                                if SKIP_COINS and series in SKIP_COINS:
                                    _skf[_ftk] = _fct
                                    continue
                                fresh[_ftk] = _fct
                        if not state.get("uni_empty_said"):
                            state["uni_empty_said"] = True
                            rec("universe_empty", what="fallback",
                                refreshes=int(state["uni_empty"]),
                                series=_uni_n15,
                                http=sorted(set(str(_x) for _x in _uni_http))[:6],
                                path="/events?with_nested_markets=true",
                                events_markets=_uni_evn)
''')
R.after('''                    deferred_s=_uni_waited,
''', '''                    source=_uni_src, rows=_uni_rows,    # v-0925v universe
''')

# ============================================================================ 14. main(): the log write counted, the book watched, the settings recorded
R.replace('''        kw["kind"] = kind
        try:
            with open(logpath, "a", encoding="utf-8", newline="\\n") as fh:
                fh.write(json.dumps(kw, default=str) + "\\n")
        except Exception:
            pass
''', '''        kw["kind"] = kind
        # v-0925v logfail: the write is COUNTED, not swallowed -- three in a
        # row block new entries (trade_loop's guard) and one stderr line says
        # so; it still never raises into the loop
        log_append(logpath, kw)
''')
R.replace('''    book = livebook.LiveBook()
    book.start()
''', '''    # v-0925v importpath: the key from ws_key(), so livebook's own
    # _default_key() -- which puts the TEMP kals-work folder at sys.path[0]
    # whenever KALSHI_KEY_ID is unset -- is never reached; and should anything
    # still have added the folder, it comes off the path here
    _v_wk = ws_key()
    book = livebook.LiveBook(key_id=_v_wk[0], key_file=_v_wk[1])
    scrub_temp_path()
    book_shape_wrap(book)        # v-0925v apishape: a new frame shape is recorded
    book.start()
''')
# the process state the startup self-test planted: empty again before anything live runs
R.replace('''    if not selftest():
        raise SystemExit("self-test failed -- nothing ran")
''', '''    if not selftest():
        raise SystemExit("self-test failed -- nothing ran")
    # v-0925v: the api_shape sentinel, the log health, the pending day totals
    # and the print-failure count were empty when this process started; the
    # self-test plants every one and hands them back, and this makes sure of
    # it before anything live runs -- whatever a future check might leak, the
    # run never dedupes its first real api_shape against a test's key nor
    # starts with a planted log failure
    _v_leak = v0925v_reset_process_state()
''')
R.after('''        cheap_window=(list(CHEAP_WINDOW) if CHEAP_WINDOW else None),
''', '''        # v-0925v: the fail-safe constants in force, and anything the
        # startup self-test had left in the process state (all 0 expected)
        fail_safe=v0925v_settings(), selftest_leak=_v_leak,
''')

# ============================================================================ 15. existing self-test checks the new shapes change, said plainly
R.replace('''    ck('int(m.get("exchange_index") or 0)' in src,
       "exchange_index is read from the market record in the universe pass")
''', '''    ck("market_exchange_index(m, endpoint)" in src
       and ('int(m.get("exchange_index")' + ' or 0)') not in src,
       "v-0925v universe (an existing check, reworded): exchange_index is read "
       "from the market record in the universe pass, the ladder's and the "
       "startup facts' alike -- a missing one is the crypto shard 2, never 0")
''')
R.replace('''       and "float(_hcs), exchange_index=2," in _vs_ho,''',
          '''       and "float(_hcs), exchange_index=_hexi," in _vs_ho,''')
# the 15-minute GET is limit UNI_LIMIT now (was "4"); the three checks that pin its shape say so
R.replace('''               and g[1]["limit"] == "4" and g[1]["status"] == "open"
               for g in _ld_off_g)''', '''               and g[1]["limit"] == UNI_LIMIT and g[1]["status"] == "open"
               for g in _ld_off_g)''')
R.replace('''       "one series_ticker/status=open/limit=4, no event_ticker, no ladder "''',
          '''       "one series_ticker/status=open/limit=UNI_LIMIT (v-0925v: 20, was 4), "
       "no event_ticker, no ladder "''')
R.replace('''       and _lm_g15 and all(g[1] == {"series_ticker": "KXAAA15M", "status": "open",
                                    "limit": "4"} for g in _lm_g15),''',
          '''       and _lm_g15 and all(g[1] == {"series_ticker": "KXAAA15M", "status": "open",
                                    "limit": UNI_LIMIT} for g in _lm_g15),''')
R.replace('''       "one (series_ticker/status/limit=4) and the universe holds both "''',
          '''       "one (series_ticker/status/limit=UNI_LIMIT; v-0925v: 20, was 4) and the "
       "universe holds both "''')
R.replace('''       and _l7_g15 and all(g[1] == {"series_ticker": "KXAAA15M", "status": "open",
                                     "limit": "4"} for g in _l7_g15)''',
          '''       and _l7_g15 and all(g[1] == {"series_ticker": "KXAAA15M", "status": "open",
                                     "limit": UNI_LIMIT} for g in _l7_g15)''')

# a leg still unbooked 15 min after its close is PARKED (its stake given back once, by _ub_park) and booked later,
# never released unbooked by time: two existing source checks counted the old give-up path
R.replace('''        ck(_body.count("_release(") >= 4,
           f"every exit path releases the stake -- finalized, both give-ups, "
           f"and the definition ({_body.count('_release(')} references)")''',
          '''        ck(_body.count("_release(") >= 3 and _body.count("_ub_park(") >= 2,
           f"every exit path releases the stake -- finalized, the void, and "
           f"the definition; v-0925v: a leg still unbooked 15 min after its "
           f"close gives it back ONCE when it is parked, and is booked later "
           f"({_body.count('_release(')} _release, "
           f"{_body.count('_ub_park(')} _ub_park references)")''')
R.replace('''       and _cm_rc.count("_count_market(close_s, tk, None)") == 2
       and min(_cm_ix) >= 0 and _cm_ix[0] < _cm_ix[1] < _cm_ix[2],
       "v-countmkt by source: the count goes up in ONE place (_count_market, "
       "never on a losing leg in reconcile), which runs after the release on "
       "the settled path and on both give-up paths")''',
          '''       and _cm_rc.count("_count_market(close_s, tk, None)") == 1
       and min(_cm_ix) >= 0 and _cm_ix[0] < _cm_ix[1] < _cm_ix[2],
       "v-countmkt by source: the count goes up in ONE place (_count_market, "
       "never on a losing leg in reconcile), which runs after the release on "
       "the settled path and on the void path (v-0925v: there is no give-up "
       "path any more -- a leg unbooked 15 min after its close is parked and "
       "counted when it books)")''')

# ============================================================================ 15b. ROUND 3 (2026-11-08): D2 D4 D5 D6 P7 JS, the cost
# From the verified rule scan (rules1107 REPORT.md sections 2 and 7). The operator, 11-07: "Anything that could cause the
# 1k+ loss needs to be addressed immediately ... And the answer isn't betting less". Each item names its scan entry.
#   D2  the day cap and the run abort see a market's NET from its first booked leg, never one leg alone
#   D4  a jump give-up stops the jump's retries only; it no longer marks the position hedged
#   D5  hedge sends no longer spend the close's 24-send ENTRY budget
#   D6  --max-positions counts UNHEDGED contracts only
#   P7  the paused loop re-checks hedges every 0.05 s (was once a second)
#   JS  --hedge-jump-shadow SD: the jump alarm without its orders (jump_shadow records), off by default
#   cost: five no-work early returns in the per-pass guard and the unbooked bookkeeping (same answers)

# ---- D6: the open cap's count, beside open_contracts ---------------------------------------------------------------
R.before('''def drawdown(bank, hwm):
''', '''def open_unhedged(led, sides=None):
    """v-0925v D6 (2026-11-08): what the OPEN CAP counts -- contracts held
    open that the other side of the same market does NOT cover. `sides` is
    {ticker: (yes_contracts, no_contracts)} over pin's own open legs
    (open_pos: entries, hedges, extras). A market holding both sides pays $1
    on min(yes, no) of them whichever way it settles, so those
    2 x min(yes, no) contracts are not exposure. Per market: pintake's
    ledger count less 2 x min(yes, no), never below 0. A market `sides`
    does not know, or no `sides` at all, counts every contract -- exactly
    open_contracts(), the fail-safe side. Never raises."""
    n = 0.0
    try:
        _pos = (led.get("positions") or {}).items()
    except Exception:                                    # noqa: BLE001
        return open_contracts(led)
    for tk, v in _pos:
        if not isinstance(v, dict):
            continue
        try:
            c = float(v.get("contracts") or 0.0)
        except (TypeError, ValueError):
            continue
        try:
            _s = (sides or {}).get(tk)
            if _s is not None:
                _y, _o = float(_s[0]), float(_s[1])
                c = max(0.0, c - 2.0 * max(0.0, min(_y, _o)))
        except (TypeError, ValueError, IndexError, AttributeError):
            pass
        n += c
    return n


''')
R.replace('''    _open_n = open_contracts(led)
    _open_cap = float(a.max_positions) * float(SIZE)
    if _open_n >= _open_cap - 1e-9:
        return (f"open cap: {_open_n:g} contracts held >= {_open_cap:g} "
                f"({a.max_positions} x size {SIZE:g})")
''', '''    _open_n = open_contracts(led)
    # v-0925v D6 (2026-11-08): THE CAP COUNTS ONLY UNHEDGED CONTRACTS. It
    # counted every contract in pintake's ledger, and pintake books a hedge
    # into the SAME position as the bet it covers, so a hedged pair -- which
    # is SAFER than the bet alone: it pays $1 on the pair whatever happens --
    # looked twice as big (NEAR 11-07: 588 NO + 588 YES read as 1,176 open,
    # and under the old 3x line 9 of 16 pauses were pushed over it by hedge
    # contracts). open_unhedged() takes 2 x min(yes, no) off each market,
    # from pin's own legs (trade_loop's open_sides); without them (a test
    # calling risk_abort bare) it counts everything, as before.
    _open_u = open_unhedged(led, state.get("open_sides"))
    _open_cap = float(a.max_positions) * float(SIZE)
    if _open_u >= _open_cap - 1e-9:
        return (f"open cap: {_open_u:g} unhedged contracts held >= "
                f"{_open_cap:g} ({a.max_positions} x size {SIZE:g}; "
                f"{_open_n:g} held in all)")
''')

# ---- D2: the market's net, pure, beside the unbooked helpers -------------------------------------------------------
R.before('''def order_shape(out, what="entry"):
''', '''def market_pending(legs, results, now):
    """v-0925v D2 (2026-11-08): what the brakes add for markets whose legs
    are only PARTLY booked. `legs` = [(close_s, ticker, want, cost, n)] --
    the unbooked, unparked legs; `results` = {(close_s, ticker): "yes" or
    "no"}, the result a booked leg of that market was booked on. Every leg
    of such a market counts what it WILL book under that result -- the
    arithmetic reconcile books with: n x (1 - cost) won, n x cost lost, less
    the taker fee -- so from its first booked leg the brakes see the
    market's NET, never one leg alone. A market with no booked leg adds
    nothing (open bets are not losses, A73). Returns (run, today): every
    such market, and the ones closing on now's ET day (et_day_key, no
    tzdata). A leg it cannot price counts its whole cost (fail safe). Never
    raises."""
    run = day = 0.0
    if not legs:
        return 0.0, 0.0
    try:
        _today = et_day_key(now)
    except Exception:                                    # noqa: BLE001
        _today = None
    for leg in legs:
        try:
            _cs, _tk, _w, _p, _n = leg
        except (TypeError, ValueError):
            continue
        _r = (results or {}).get((_cs, _tk))
        if _r not in ("yes", "no"):
            continue
        try:
            _p, _n = float(_p), float(_n)
            _v = _n * ((1.0 - _p) if _w == _r else -_p) - billed_fee(_p, _n)
            if _v != _v or abs(_v) == float("inf"):
                raise ValueError("not a number")
        except Exception:                                # noqa: BLE001
            try:
                _v = -abs(float(_p) * float(_n))
            except Exception:                            # noqa: BLE001
                continue
        run += _v
        try:
            if _today is None or et_day_key(float(_cs)) == _today:
                day += _v
        except Exception:                                # noqa: BLE001
            day += _v
    return round(run, 4), round(day, 4)


def mk_view(total, state, which="run"):
    """v-0925v D2: a settled total -- the run's `realised` ("run") or the
    day file's ("day") -- as the brakes see it: plus what the unbooked legs
    of markets ALREADY PARTLY BOOKED will book (state["mk_pending_run"] /
    ["mk_pending_day"], market_pending). None stays None (no day file); an
    unreadable pending adds 0, i.e. the brake sees the booked legs exactly as
    before. Never raises."""
    if total is None:
        return None
    try:
        _t = float(total)
    except (TypeError, ValueError):
        return total
    try:
        _p = float((state or {}).get("mk_pending_" + str(which), 0.0) or 0.0)
        if _p != _p or abs(_p) == float("inf"):
            _p = 0.0
    except (TypeError, ValueError, AttributeError):
        _p = 0.0
    return _t + _p


''')
R.replace('''    _dl = day_loss() if getattr(a, "live", False) else None
    if _dl is not None and _dl <= a.loss_abort:
        return (f"DAY loss cap: ${_dl:.2f} lost today (ET) <= "
''', '''    _dl = day_loss() if getattr(a, "live", False) else None
    # v-0925v D2 (2026-11-08): THE CAP AND THE ABORT SEE A MARKET'S NET, NOT
    # ONE LEG. reconcile books each leg on its own and a hedged market's legs
    # land ~15 s apart (one GET per ticker per 15 s), so this check -- 20
    # times a second -- saw the main leg's whole loss before the hedge's gain:
    # 11-02 07:30 ET ZEC, main -$281.63 then the hedge +$253.07 fifteen
    # seconds later (net -$28.56) dipped the day to -$310.37; at today's size
    # that shape would have halted 09-27 for the day (-$765.33 by leg against
    # -$645.80 by market, stop -$647.77). mk_view adds what the unbooked legs
    # of a partly booked market will book under the result its booked leg
    # carried (trade_loop's _mk_pending_update): the market's net from its
    # first booked leg on. Nothing is added for a market with no booked leg.
    _dl = mk_view(_dl, state, "day")
    if _dl is not None and _dl <= a.loss_abort:
        return (f"DAY loss cap: ${_dl:.2f} lost today (ET) <= "
''')
R.replace('''    if float(led.get("realised", 0.0)) <= a.loss_abort:
        return (f"loss abort: realised ${led['realised']:.2f} <= "
                f"${a.loss_abort:.2f}")
''', '''    _rv = mk_view(led.get("realised", 0.0), state, "run")   # v-0925v D2
    if float(_rv) <= a.loss_abort:
        return (f"loss abort: realised ${float(_rv):.2f} <= "
                f"${a.loss_abort:.2f}")
''')

# ---- JS: the flag, its startup refusal, beside the jump cap ----------------------------------------------------------
R.after('''HEDGE_JUMP_MAX = None
_DEFAULT_HEDGE_JUMP_MAX = None
''', '''# v-0925v JS (2026-11-08): --hedge-jump-shadow SD. The rule scan (11-07,
# call A) found the jump hedge -$186 at today's size over 15-16 live days
# (27 false alarms, 3 real saves) while the study that approved it made
# money; dropping it needs its alarm kept as a SHADOW so a flip the belief
# hedge then misses can be priced. With this flag (and --hedge-jump OFF)
# the jump alarm is computed exactly as the jump hedge computes it -- the
# largest one-second move against our side since entry, in sigma, from the
# same lookback -- and the first time it reaches SD on a position ONE
# jump_shadow record says what would have gone out: the side, the
# contracts (hedge_want / flip_size / the ladder depth, as the send site
# sizes them), the ask and its size, the belief, the sd, tau, and whether
# --hedge-jump-max (the 8 sd cap) or --jump-hedge-min-ask (the 5c floor)
# would have skipped it. NOTHING IS SENT, no try is spent, no position is
# marked; the belief hedge runs exactly as it does today. Both flags
# together are refused at startup (jump_shadow_conflict). None = off.
HEDGE_JUMP_SHADOW = None
_DEFAULT_HEDGE_JUMP_SHADOW = None


def jump_shadow_conflict(hedge_jump, hedge_jump_shadow):
    """v-0925v JS: the startup refusal, or None. With --hedge-jump ON the
    shadow would describe orders that really go out -- one rule, two
    records, and a read that double-counts. Pure; cannot raise."""
    if hedge_jump is not None and hedge_jump_shadow is not None:
        return ("--hedge-jump and --hedge-jump-shadow are refused together: "
                "the shadow records the jump hedge's alarm while the jump "
                "hedge is OFF; with it on it would shadow orders that really "
                "go out. Give one.")
    return None


def jump_shadow_fields(book, tk, want, n_orig, n_left, jump_sd, belief, tau,
                       entry_tau=None):
    """v-0925v JS: what a jump_shadow record says -- the hedge the A52 jump
    trigger WOULD have sent this second, sized exactly as the hedge pass
    sizes it (hedge_want on what is still unhedged, flip_size, the ladder up
    to hedge_limit when --hedge-slip reads one), the other side's ask and its
    size, and whether --hedge-jump-max (jump_capped) or --jump-hedge-min-ask
    (cheap_jump_skip) would have skipped it. Reads the book; sends nothing.
    A module function so the hedge pass's own call sites (one each of
    jump_capped, cheap_jump_skip, hedge_limit, odds_extra) stay one each.
    Never raises: a read it cannot make leaves its field None."""
    out = {"side": ("no" if want == "yes" else "yes"), "n": 0.0, "n_want": None,
           "ask": None, "ask_size": None, "limit": None,
           "belief": None, "jump_sd": None, "threshold": HEDGE_JUMP_SHADOW,
           "tau": tau, "capped": None, "cap": HEDGE_JUMP_MAX,
           "cheap_skip": None, "min_ask": JUMP_HEDGE_MIN_ASK, "panic": None,
           "belief_fires": None, "extra_n": None, "would_send": False,
           "sent": False}
    try:
        _opp = out["side"]
        out["belief"] = round(float(belief), 5)
        out["jump_sd"] = round(float(jump_sd), 2)
        try:
            _b = book.best(tk)
        except Exception:                                # noqa: BLE001
            _b = None
        _ask = (_b or {}).get(f"{_opp}_ask")
        _asz = (_b or {}).get(f"{_opp}_ask_size")
        out["ask"] = round(float(_ask), 4) if _ask is not None else None
        out["ask_size"] = _asz
        _ok = _ask is not None and 0.0 < float(_ask) < 1.0
        _nw = hedge_want(n_orig, float(n_left), belief)
        _nf = flip_size(_nw, entry_tau, tau)
        out["n_want"] = round(float(_nf), 2)
        _lim, _rg = None, []
        if _ok:
            _lim = hedge_limit(_ask, ticker=tk)
            if HEDGE_SLIP and _lim is not None:
                try:
                    _rg = book.rungs(tk, _opp, _lim)
                except Exception:                        # noqa: BLE001
                    _rg = []
        out["limit"] = round(float(_lim), 4) if _lim is not None else None
        _dep = hedge_depth(_asz, _rg, _nw) if (_ok and _asz) else 0.0
        _take = min(float(_nf), float(_dep or 0.0))
        out["n"] = round(_take, 2)
        out["capped"] = bool(jump_capped(jump_sd))
        out["panic"] = bool(hedge_panic(belief))
        out["cheap_skip"] = bool(_ok and cheap_jump_skip("jump", out["panic"], belief, _ask))
        out["belief_fires"] = bool(hedge_should_fire(belief))
        out["extra_n"] = odds_extra(n_orig, "jump", belief, tau)
        out["would_send"] = bool(_ok and _take > 1e-9 and not out["capped"]
                                 and not out["cheap_skip"])
    except Exception as _e:                              # noqa: BLE001
        out["err"] = type(_e).__name__
    return out
''')
R.before('''    ap.add_argument("--jump-hedge-min-ask", type=float, default=None,
''', '''    ap.add_argument("--hedge-jump-shadow", type=float, default=None,
                    metavar="SD",
                    help="v-0925v JS: with --hedge-jump OFF, compute the jump "
                         "alarm exactly as the jump hedge would (a one-second "
                         "move of SD sigma or more against our side since "
                         "entry) and write ONE jump_shadow record per "
                         "position with the hedge it would have sent (and "
                         "whether --hedge-jump-max / --jump-hedge-min-ask "
                         "would have skipped it); sends nothing, changes "
                         "nothing. Refused with --hedge-jump. Off by default.")
''')
R.after('''    a = ap.parse_args()
''', '''    # v-0925v JS: refused BEFORE any flag is applied, so a refused start
    # changes nothing in the process
    _js_why = jump_shadow_conflict(a.hedge_jump, a.hedge_jump_shadow)
    if _js_why:
        raise SystemExit(_js_why)
''')
R.replace('''        globals()["HEDGE_JUMP_SIGMA"] = float(a.hedge_jump)
''', '''        globals()["HEDGE_JUMP_SIGMA"] = float(a.hedge_jump)
    if a.hedge_jump_shadow is not None:
        if not (1.0 <= a.hedge_jump_shadow <= 50.0):
            raise SystemExit("--hedge-jump-shadow is in SIGMA and must be in "
                             "[1, 50], got %r" % (a.hedge_jump_shadow,))
        globals()["HEDGE_JUMP_SHADOW"] = float(a.hedge_jump_shadow)
''')
R.replace('''    if a.hedge_jump_max is not None:
        if (HEDGE_JUMP_SIGMA is None
                or not (float(HEDGE_JUMP_SIGMA) < float(a.hedge_jump_max)
                        <= 100.0)):
            raise SystemExit("--hedge-jump-max needs --hedge-jump and must be "
                             "above it and at most 100, got %r"
                             % (a.hedge_jump_max,))
''', '''    if a.hedge_jump_max is not None:
        # v-0925v JS: the shadow reads the same cap, so it may carry it too
        _jsd = (HEDGE_JUMP_SIGMA if HEDGE_JUMP_SIGMA is not None
                else HEDGE_JUMP_SHADOW)
        if (_jsd is None
                or not (float(_jsd) < float(a.hedge_jump_max) <= 100.0)):
            raise SystemExit("--hedge-jump-max needs --hedge-jump (or "
                             "--hedge-jump-shadow) and must be above it and "
                             "at most 100, got %r" % (a.hedge_jump_max,))
''')
R.replace('''    "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX",
    "CHEAP_WINDOW")
''', '''    "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX",
    "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW")
''')
R.replace('''                 "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX",
                 "CHEAP_WINDOW")
''', '''                 "HEDGE_TICK", "JUMP_HEDGE_MIN_ASK", "BOOST_RAIL", "LATE_BYPASS_FIX",
                 "CHEAP_WINDOW", "HEDGE_JUMP_SHADOW")
''')
R.replace('''        hedge_normal=HEDGE_NORMAL, hedge_jump=HEDGE_JUMP_SIGMA,
''', '''        hedge_normal=HEDGE_NORMAL, hedge_jump=HEDGE_JUMP_SIGMA,
        hedge_jump_shadow=HEDGE_JUMP_SHADOW,                # v-0925v JS
''')

# ---- the loop's state ------------------------------------------------------------------------------------------------
R.before('''    jump_capped_said = set() # v-jumpcap8: (close_s, ticker) logged once
''', '''    mk_res = {}              # v-0925v D2: (close_s, ticker) -> the result a
                             # booked leg of that market was booked on, while
                             # another leg of it is still unbooked
    jump_gave_up = set()     # v-0925v D4: positions whose JUMP retries gave up
                             # (the belief line keeps all of its own)
    jump_shadow_said = set() # v-0925v JS: positions with a jump_shadow on record
''')

# ---- D2 / D6 / JS helpers, beside the unbooked ones (above reconcile) ------------------------------------------------
R.before('''    def reconcile():
        """Book settled P&L so the loss abort is a REAL brake, not a nominal one.
''', '''    def _mk_pending_update(now_):
        """v-0925v D2: state["mk_pending_run"] / ["mk_pending_day"] -- what the
        still-unbooked legs of every PARTLY booked market will book under the
        result its booked leg carried (market_pending), for risk_abort and the
        unbooked guard (mk_view). Once a pass, below the hedge pass, from
        open_pos as it stands, so a pass that booked a sibling cannot count it
        twice. A parked leg is not in it: the unbooked guard already counts
        its worst case. A market with no leg left is dropped. Never raises; a
        fault adds nothing (the brakes see the booked legs, as before)."""
        try:
            if not mk_res:
                state["mk_pending_run"] = state["mk_pending_day"] = 0.0
                return
            _legs, _live_k = [], set()
            for _o, (_c, _w, _p, _n, _t) in open_pos.items():
                if (_c, _t) in mk_res:
                    _live_k.add((_c, _t))
                    if _o not in ub_parked:
                        _legs.append((_c, _t, _w, _p, _n))
            for _k in [k for k in mk_res if k not in _live_k]:
                mk_res.pop(_k, None)
            state["mk_pending_run"], state["mk_pending_day"] = market_pending(
                _legs, mk_res, now_)
        except Exception:                                # noqa: BLE001
            state["mk_pending_run"] = state["mk_pending_day"] = 0.0

    def _open_sides():
        """v-0925v D6: {ticker: (yes, no)} contracts over pin's own open legs
        -- entries, hedges, extras -- for the open cap (open_unhedged). None
        on a fault, which counts every contract (the old cap). Never
        raises."""
        try:
            _s = {}
            for (_c, _w, _p, _n, _t) in open_pos.values():
                _y, _no = _s.get(_t, (0.0, 0.0))
                if _w == "yes":
                    _y += float(_n)
                else:
                    _no += float(_n)
                _s[_t] = (_y, _no)
            return _s
        except Exception:                                # noqa: BLE001
            return None

    def _js_note(hid_, cs_, tk_, want_, n_orig_, n_left_, jsd_, belief_,
                 tau_, entry_):
        """v-0925v JS: ONE jump_shadow record (jump_shadow_fields: the hedge
        the jump trigger WOULD have sent this second, sized as the send site
        sizes it, and whether the 8 sd cap or the 5c floor would have skipped
        it). Reads the book; sends nothing, spends no try, marks nothing.
        Never raises."""
        try:
            _f = jump_shadow_fields(
                book, tk_, want_, n_orig_, n_left_, jsd_, belief_, tau_,
                (cs_ - entry_at[hid_]) if hid_ in entry_at else None)
            rec("jump_shadow", ticker=tk_, close_s=cs_, want=want_, entry=entry_,
                live=bool(live), **_f)
            print(f"  jump SHADOW {tk_}: {jsd_:.1f} sd against {want_}, would "
                  f"buy {_f.get('side')} {_f.get('n')} @ {_f.get('ask')} "
                  f"(capped {_f.get('capped')}, cheap {_f.get('cheap_skip')}); "
                  f"nothing sent")
        except Exception:                                # noqa: BLE001
            pass

''')

# ---- D2: the booked result, kept per market --------------------------------------------------------------------------
R.replace('''            pintake.record_pnl(pnl, note=f"{tk} {want} vs {res}")
''', '''            pintake.record_pnl(pnl, note=f"{tk} {want} vs {res}")
            mk_res[(close_s, tk)] = res      # v-0925v D2: its siblings' result
''')
R.replace('''                _d = 0.0
                if _fr in ("yes", "no"):
                    for (_w9, _p9, _n9, _pl9) in (_u.get("legs") or ()):
''', '''                _d = 0.0
                if _fr in ("yes", "no"):
                    # v-0925v D2: a sibling still unbooked is priced on the
                    # corrected result from now on
                    for _k9 in [k for k in mk_res if k[1] == _t]:
                        mk_res[_k9] = _fr
                    for (_w9, _p9, _n9, _pl9) in (_u.get("legs") or ()):
''')

# ---- D2 / D6: what the brakes see, computed once a pass below the hedge pass ------------------------------------------
R.replace('''        _v_guard(now)
        # v-0925v expiry: THE RUN DOES NOT END HOLDING A BET (_v_expiry).
''', '''        _mk_pending_update(now)          # v-0925v D2: a market's net, for the brakes
        _v_guard(now)
        # v-0925v expiry: THE RUN DOES NOT END HOLDING A BET (_v_expiry).
''')
R.replace('''        try:
            stop = risk_abort(state, a)
''', '''        state["open_sides"] = _open_sides()   # v-0925v D6: the open cap's sides
        try:
            stop = risk_abort(state, a)
''')
R.replace('''        _why = unbooked_bound(_u, pintake.LEDGER.get("realised", 0.0),
                              (day_loss() if live else None), a.loss_abort,
                              live=bool(live), day_unbooked=_ud)
''', '''        # v-0925v D2: settled money as risk_abort now sees it -- with the
        # unbooked legs of a partly booked market at what they will book
        _why = unbooked_bound(_u, mk_view(pintake.LEDGER.get("realised", 0.0), state, "run"),
                              mk_view((day_loss() if live else None), state, "day"), a.loss_abort,
                              live=bool(live), day_unbooked=_ud)
''')

# ---- D4 + JS: the jump trigger -----------------------------------------------------------------------------------------
R.replace('''                        if _hjmp is not None and _hjmp >= HEDGE_JUMP_SIGMA:
                            if jump_capped(_hjmp):
                                _hcap = True     # v-jumpcap8: not a trigger
                            else:
                                _htrig = "jump"
''', '''                        if _hjmp is not None and _hjmp >= HEDGE_JUMP_SIGMA:
                            if jump_capped(_hjmp):
                                _hcap = True     # v-jumpcap8: not a trigger
                            elif _hid in jump_gave_up:
                                pass             # v-0925v D4: its jump retries are over
                            else:
                                _htrig = "jump"
                    # v-0925v JS: the jump alarm WITHOUT its orders, while the
                    # jump hedge is off -- the same move, sigma and lookback;
                    # one jump_shadow record per position; nothing below sees
                    # it (no trigger, no try, no mark)
                    if (HEDGE_JUMP_SIGMA is None and HEDGE_JUMP_SHADOW is not None
                            and _hsg is not None and _hid not in jump_shadow_said):
                        _since_js = int(now_s - entry_at.get(_hid, now_s))
                        _hjs = jump_against(
                            idx.recent_moves(_hiid, max(1, min(HEDGE_JUMP_LOOKBACK_MAX, _since_js))),
                            _hsg, _hwant)
                        if _hjs is not None and _hjs >= HEDGE_JUMP_SHADOW:
                            jump_shadow_said.add(_hid)
                            _js_note(_hid, _hcs, _htk, _hwant, _hn_orig, _hn, _hjs,
                                     _belief, _htau, _hcost)
''')
R.replace('''                    if _tries + 1 > HEDGE_MAX_TRIES and not hedge_panic(_belief):
                        hedged.add(_hid)
                        rec("hedge_gave_up", ticker=_htk, tries=_tries, tau=_htau)
                        continue
''', '''                    if _tries + 1 > HEDGE_MAX_TRIES and not hedge_panic(_belief):
                        # v-0925v D4 (2026-11-08): A JUMP GIVE-UP ENDS THE
                        # JUMP'S RETRIES ONLY. It used to mark the position
                        # hedged for good, so when belief later collapsed the
                        # belief hedge -- the rule worth +$28.6/day -- skipped
                        # it: 5 positions 10-24..11-03 (off-grid sends, all
                        # given up 2-7 s before close; markets we won, so $0
                        # lost, but up to ~$570 on a 588-lot that flips). Now
                        # a give-up on a jump-only second (belief still over
                        # the line, no panic) puts the position in
                        # jump_gave_up -- the jump never triggers on it again
                        # -- and hands the belief line a fresh
                        # HEDGE_MAX_TRIES. A give-up with belief under the
                        # line is the belief line's own, and ends it as
                        # before.
                        if _htrig == "jump" and not hedge_should_fire(_belief):
                            jump_gave_up.add(_hid)
                            hedge_tries[_hid] = 0
                            rec("hedge_gave_up", ticker=_htk, tries=_tries,
                                tau=_htau, trigger="jump", jump_only=True,
                                belief=round(_belief, 5),
                                still_armed="the belief line")
                            continue
                        hedged.add(_hid)
                        rec("hedge_gave_up", ticker=_htk, tries=_tries, tau=_htau)
                        continue
''')

# ---- D5: a hedge send no longer spends the ENTRY budget ----------------------------------------------------------------
R.replace('''                    # A hedge order still spends the ENTRY budget -- an order is an
                    # order and a hedge outranks a new bet -- but the entry budget
                    # no longer spends the HEDGE's.
                    attempts[_hcs] = attempts.get(_hcs, 0) + 1
                    hedge_attempts[_hcs] = hedge_attempts.get(_hcs, 0) + 1
''', '''                    # v-0925v D5 (2026-11-08): A HEDGE NO LONGER SPENDS THE
                    # ENTRY BUDGET. It did ("an order is an order and a hedge
                    # outranks a new bet"), so a hedge Kalshi kept rejecting
                    # or not filling, re-sent once a second, used up the
                    # close's MAX_ATTEMPTS_PER_CLOSE (24) sends and locked
                    # every OTHER market of that close out: attempts_cap fired
                    # 84 times in 9 closes 10-24..11-03, each with 20-42
                    # unfilled hedge sends against 1-8 entry orders. A hedge
                    # now counts against its own budget only -- one try a
                    # second, HEDGE_MAX_TRIES (30) per position, and
                    # MAX_HEDGE_ATTEMPTS_PER_CLOSE -- which no entry can
                    # touch, the way A71 made the entry budget unable to touch
                    # the hedge's.
                    hedge_attempts[_hcs] = hedge_attempts.get(_hcs, 0) + 1
''')
R.replace('''                                _hx_take = float(_hx_allow)
                                attempts[_hcs] = attempts.get(_hcs, 0) + 1
                                hedge_attempts[_hcs] += 1
''', '''                                _hx_take = float(_hx_allow)
                                hedge_attempts[_hcs] += 1   # v-0925v D5: its own budget only
''')

# ---- P7: the paused loop naps at the ordinary pass rate ----------------------------------------------------------------
R.replace('''            # R2 (review fix): a PAUSE sleeps a whole second, so the next
            # pass books a ~1,000 ms gap that is not a stall at all. The
            # bar reads gaps as evidence for deferring the universe
            # refresh, and a pause is not that. Named, not hidden: the
            # hedge pass really did run only once in that second, which is
            # worth recording -- but as `why="pause"`, never as a stall.
            _pass_why = "pause"
            time.sleep(1.0)
            continue
''', '''            # R2 (review fix): a PAUSE used to sleep a whole second, so the
            # next pass booked a ~1,000 ms gap that is not a stall at all;
            # such a gap is labelled `why="pause"`, never a stall.
            # v-0925v P7 (2026-11-08): THE PAUSE NAPS 0.05 s, THE ORDINARY
            # PASS RATE. The hedge pass sits above this branch and runs every
            # pass, but a paused pass slept a WHOLE SECOND -- so while the
            # open cap (or any transient halt) paused entries, a held
            # position's hedge was re-checked once a second, and a collapse
            # in the last seconds of its close could wait up to a second for
            # its insurance. A pause only ever meant "no new bets"; it now
            # costs the hedge nothing. The label is kept for any gap a
            # paused pass still makes.
            _pass_why = "pause"
            time.sleep(0.05)
            continue
''')
R.replace('''               TRANSIENT "open cap:" halt after the first fill, which is the
               only way to reach the loop's 1 s PAUSE branch offline.''',
          '''               TRANSIENT "open cap:" halt after the first fill, which is the
               only way to reach the loop's PAUSE branch offline (v-0925v P7:
               it naps 0.05 s now, not 1 s).''')

# ---- the cost: the per-pass guard does no work when there is none (same answers) ---------------------------------------
R.replace('''    worst on both (fail safe). Never raises."""
    run = day = 0.0
    try:
        _today = et_day_key(now)
''', '''    worst on both (fail safe). Never raises."""
    run = day = 0.0
    if not markets:
        return 0.0, 0.0          # v-0925v (11-08): the common case, 20 Hz, no work
    try:
        _today = et_day_key(now)
''')
R.replace('''        try:
            _per = {}
            for _o, (_c, _w, _p, _n, _t) in open_pos.items():
                if _o in ub_parked:
''', '''        try:
            if not ub_parked:
                # v-0925v (11-08): nothing parked -- the common case, 20
                # times a second -- is no work and the same answer
                if state.get("unbooked_mk") != {}:
                    state["unbooked_mk"] = {}
                state["unbooked_prov"] = 0.0
                return
            _per = {}
            for _o, (_c, _w, _p, _n, _t) in open_pos.items():
                if _o in ub_parked:
''')

# _eb_clear() of a reason that is not blocking writes nothing and returns False -- but it built its keyword dict first,
# three times a pass; the guard now asks whether the reason is blocking before calling it (the same records, always)
R.replace('''        else:
            _eb_clear("log_write", which="log")
''', '''        elif "log_write" in entry_blocks:     # v-0925v (11-08): no block, no work
            _eb_clear("log_write", which="log")
''')
R.replace('''                else:
                    _eb_clear("dayloss_write", path=DAYLOSS_FILE)
            else:
                _eb_clear("dayloss_write", path=DAYLOSS_FILE)
''', '''                else:
                    _eb_clear("dayloss_write", path=DAYLOSS_FILE)
            elif "dayloss_write" in entry_blocks:   # v-0925v (11-08): no block, no work
                _eb_clear("dayloss_write", path=DAYLOSS_FILE)
''')
R.replace('''        if _u >= -1e-9:
            _eb_clear("unbooked", unbooked=0.0)
            return
''', '''        if _u >= -1e-9:
            if "unbooked" in entry_blocks:    # v-0925v (11-08): no block, no work
                _eb_clear("unbooked", unbooked=0.0)
            return
''')

# ---- existing self-test checks the round-3 shapes change, said plainly --------------------------------------------------
# P7: the R2 review check counted ~1,000 ms gaps a pause created; a pause makes none now
R.replace('''    ck(_r2p["raised"] is None and _kinds(_r2p, "pause") and len(_r2pp) >= 20
       and all(900.0 <= float(r["ms"]) <= 1200.0 for r in _r2pp)
       and len(_r2pp) == len(_r2pl),
       "R2: every ~1,000 ms gap a PAUSE creates is labelled why='pause' -- "
       "including the FIRST one, the pass that chose to sleep, which a "
       "label carried in _prev_pass would have missed by one pass (%d "
       "loop records, %d of them pauses, ms %s)"
       % (len(_r2pl), len(_r2pp), [r["ms"] for r in _r2pp][:3]))''',
          '''    ck(_r2p["raised"] is None and _kinds(_r2p, "pause") and not _r2pl
       and int((_r2p.get("calls") or {}).get("sigma", 0)) >= 300,
       "v-0925v P7 (the R2 pause check, reworded): a PAUSE naps 0.05 s like "
       "every pass now, so 30 s paused while holding make NO ~1,000 ms gap "
       "at all (%d loop records; it was 20+, each labelled why='pause') and "
       "the hedge pass re-reads the held position ~20 times a second (%d "
       "sigma reads; once a second, ~30, before)"
       % (len(_r2pl), int((_r2p.get("calls") or {}).get("sigma", 0))))''')
# D5: the A15 check that every send is preceded by an attempt increment read the ENTRY counter at the hedge's sends
R.replace(r'''    _incs9 = [m.start() for m in
              _re9.finditer(r"attempts\[\w+\] = attempts\.get\(\w+, 0\) \+ 1", _b9)]
    ck(len(_takes9) >= 2 and all(any(i < t for i in _incs9) for t in _takes9)
       and all(max(i for i in _incs9 if i < t) >
               (max((u for u in _takes9 if u < t), default=-1)) for t in _takes9),
       "and an attempt is counted BEFORE the order is sent, so a send that "
       "never returns still consumes one")''', r'''    _incs9 = [m.start() for m in
              _re9.finditer(r"(?:hedge_)?attempts\[\w+\] = (?:hedge_)?attempts\.get\(\w+, 0\) \+ 1"
                            r"|hedge_attempts\[\w+\] \+= 1", _b9)]
    ck(len(_takes9) >= 2 and all(any(i < t for i in _incs9) for t in _takes9)
       and all(max(i for i in _incs9 if i < t) >
               (max((u for u in _takes9 if u < t), default=-1)) for t in _takes9),
       "v-0925v D5 (the A15 attempt check, reworded): an attempt is counted "
       "BEFORE every order is sent, so a send that never returns still "
       "consumes one -- an entry on the entry counter, a hedge (cover or "
       "extra) on the hedge's own")''')
# D6: the v-opencap5 CONTROL paused on 15 contracts of which 10 are a cover and an extra on the other side
R.replace('''    ck(_oc3["raised"] is None and abs(_hedged(_oc3, _kA) - 5.0) < 1e-9
       and _kinds(_oc3, "pause") and not _kinds(_oc3, "order", "KXB115M-K1")
       and not _kinds(_oc3, "open_cap_relaxed"),
       "v-opencap5 CONTROL (--max-positions 3, the old live line): the same 15 "
       "open pauses the loop (%d pause records), B is never bought, no "
       "open_cap_relaxed" % len(_kinds(_oc3, "pause")))''',
          '''    ck(_oc3["raised"] is None and abs(_hedged(_oc3, _kA) - 5.0) < 1e-9
       and not _kinds(_oc3, "pause") and _kinds(_oc3, "order", "KXB115M-K1")
       and not _kinds(_oc3, "open_cap_relaxed"),
       "v-0925v D6 (the v-opencap5 CONTROL, reworded): under --max-positions 3 "
       "(the old live line) the same 15 open -- 5 YES, its 5 NO cover, the 5 "
       "NO extra -- is 5 UNHEDGED contracts, under the 15 cap: it no longer "
       "pauses the loop (%d pause records) and B is bought; no "
       "open_cap_relaxed (that record is for --max-positions over 3)"
       % len(_kinds(_oc3, "pause")))''')
# D4: the v-cheapjump REFUND CONTROL showed a JUMP give-up blocking the later belief hedge -- the defect D4 fixes
R.replace('''    ck(_cjf["raised"] is None and not _kinds(_cjf, "hedge_gave_up")
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
          len(_kinds(_cjg, "hedge_gave_up")), _hedged(_cjg, "KXCJ715M-CJ")))''',
          '''    _cjg_gu = _kinds(_cjg, "hedge_gave_up")
    ck(_cjf["raised"] is None and not _kinds(_cjf, "hedge_gave_up")
       and len(_kinds(_cjf, "hedge_cheap_skip")) == 1
       and abs(_hedged(_cjf, "KXCJ615M-CJ") - 5.0) < 1e-9
       and _cj_first(_cjf, "KXCJ615M-CJ") >= 9.5
       and _cjg["raised"] is None and len(_cjg_gu) == 1
       and _cjg_gu[0].get("trigger") == "jump" and _cjg_gu[0].get("jump_only") is True
       and abs(_hedged(_cjg, "KXCJ715M-CJ") - 5.0) < 1e-9
       and _cj_first(_cjg, "KXCJ715M-CJ") >= 9.5,
       "v-0925v D4 (the v-cheapjump REFUND check, reworded): at "
       "HEDGE_MAX_TRIES 3, six seconds of cheap skips spend no try -- no "
       "give-up, and the collapse at t 10 hedges all 5 (hedged %g at t %g); "
       "CONTROL: six seconds with no NO ask spend the three and the JUMP gives "
       "up (%d hedge_gave_up, trigger %r) -- which used to mark the position "
       "hedged so the collapse was never hedged; now the belief line still "
       "hedges all 5 at the collapse (hedged %g at t %g)"
       % (_hedged(_cjf, "KXCJ615M-CJ"), _cj_first(_cjf, "KXCJ615M-CJ"),
          len(_cjg_gu), (_cjg_gu[0].get("trigger") if _cjg_gu else None),
          _hedged(_cjg, "KXCJ715M-CJ"), _cj_first(_cjg, "KXCJ715M-CJ")))''')

# ============================================================================ 15c. ROUND 4 (2026-11-08): the two reviews of round 3
# The money and tests reviews of round 3 (rev3\, rt3\) found the round-3 fixes right but not closed for their whole
# class. Each edit below names its finding. The operator, 11-07: "Anything that could cause the 1k+ loss needs to be
# addressed immediately ... And the answer isn't betting less".
#   D2  every leg of a market books from the SAME read in the SAME pass (the 15 s split was the per-ticker GET
#       throttle's); pintake's own per-leg loss rail is never sent an entry while a leg-only dip is below it
#       (entries_blocked reason leg_dip, so no refusal can reach the 2-order-error halt); market_pending's unpriceable
#       leg adds nothing and cannot poison the others; the correction and the leg selection are pure helpers
#   D4  the per-close hedge cap on a jump-only second ends the JUMP's retries only, like the 30-try give-up
#   D5  hedge_broken needs failures on TWO markets in the streak: one market's reject loop no longer blocks the rest
#   JS  the shadow follows the jump hedge every second until it would send (one record per outcome), and its records
#       are written BELOW the hedge pass; its argv checks are pure functions
#   F2  every TEMP folder the self-test makes is removed (pinmirror-, pintraj-selftest- were left on every run)

# ---- D2: every leg of a market books from one read, in one pass ---------------------------------------------------
R.replace('''        _ub_read = {}       # v-0925v: one late read per market per pass
''', '''        _ub_read = {}       # v-0925v: one read per market per pass (round 4: every leg's)
''')
R.replace('''            if _late and tk in _ub_read:
                st, b = _ub_read[tk]           # this pass's read of the market
            else:
''', '''            # v-0925v D2 (round 4, 11-08): EVERY LEG OF A MARKET BOOKS FROM
            # THE SAME READ, IN THE SAME PASS. The ~15 s between a hedged
            # market's legs (11-02 07:30 ET ZEC: -$281.63, then +$253.07) was
            # THIS throttle's: one GET per ticker per 15 s, so every leg after
            # the first found its ticker read a moment ago and waited the 15 s
            # out -- and the first leg's whole loss sat ALONE in the run's
            # realised, the day file and pintake's own loss rail, which see
            # legs, not markets. The pass's own answer for the ticker now
            # books every leg of it (one GET fewer per hedged market, never
            # one more). Round 3's market view (mk_view) stays under it for a
            # pass that books one leg and then fails.
            if tk in _ub_read:
                st, b = _ub_read[tk]           # this pass's read of the market
            else:
''')
R.replace('''                if _late:
                    _ub_read[tk] = (st, b)
''', '''                _ub_read[tk] = (st, b)         # v-0925v D2 (round 4): for every leg
''')

# ---- D2: the correction and the leg selection, pure; an unpriceable leg adds nothing ------------------------------
R.replace('''    nothing (open bets are not losses, A73). Returns (run, today): every
    such market, and the ones closing on now's ET day (et_day_key, no
    tzdata). A leg it cannot price counts its whole cost (fail safe). Never
    raises."""''', '''    nothing (open bets are not losses, A73). Returns (run, today): every
    such market, and the ones closing on now's ET day (et_day_key, no
    tzdata). A leg it cannot price -- a cost or a count that is not a
    finite number -- ADDS NOTHING: the brakes then see that market's booked
    legs alone, exactly as before round 3, and one bad leg cannot poison
    the others (round 4: it counted -|cost x n|, and a NaN there turned the
    whole total into NaN, which mk_view reads as 0 for EVERY market). Never
    raises."""''')
R.replace('''        try:
            _p, _n = float(_p), float(_n)
            _v = _n * ((1.0 - _p) if _w == _r else -_p) - billed_fee(_p, _n)
            if _v != _v or abs(_v) == float("inf"):
                raise ValueError("not a number")
        except Exception:                                # noqa: BLE001
            try:
                _v = -abs(float(_p) * float(_n))
            except Exception:                            # noqa: BLE001
                continue
        run += _v
''', '''        try:
            _p, _n = float(_p), float(_n)
            _v = _n * ((1.0 - _p) if _w == _r else -_p) - billed_fee(_p, _n)
            if _v != _v or abs(_v) == float("inf"):
                raise ValueError("not a number")
        except Exception:                                # noqa: BLE001
            continue                     # v-0925v D2 (round 4): adds nothing
        run += _v
''')
R.before('''def mk_view(total, state, which="run"):
''', '''def market_pending_legs(open_pos, mk_res, parked=()):
    """v-0925v D2 (round 4, from _mk_pending_update so it can be tested):
    the legs market_pending prices -- every open leg of a PARTLY booked
    market (its (close_s, ticker) in mk_res) that is NOT parked: the
    unbooked guard already counts a parked leg at its worst, so pricing it
    here as well would count it twice. Returns (legs, live): the legs as
    market_pending takes them, and every market still holding any leg
    (parked or not) -- a market in mk_res with none is done. Never raises."""
    legs, live = [], set()
    try:
        for _o, _v in (open_pos or {}).items():
            try:
                _c, _w, _p, _n, _t = _v
            except (TypeError, ValueError):
                continue
            if (_c, _t) in mk_res:
                live.add((_c, _t))
                if _o not in parked:
                    legs.append((_c, _t, _w, _p, _n))
    except Exception:                                    # noqa: BLE001
        return [], set()
    return legs, live


def mk_res_correct(mk_res, ticker, result):
    """v-0925v D2 (round 4, from _ub_unpaid_poll so it can be tested): a
    FINAL result other than the one a market was booked on re-prices every
    still-unbooked leg of that ticker on the final one. Returns the keys it
    moved; a result that is not yes / no moves nothing. Never raises."""
    if result not in ("yes", "no"):
        return []
    try:
        _ks = [k for k in mk_res if k[1] == ticker]
        for _k in _ks:
            mk_res[_k] = result
        return _ks
    except Exception:                                    # noqa: BLE001
        return []


''')
R.replace('''                    # v-0925v D2: a sibling still unbooked is priced on the
                    # corrected result from now on
                    for _k9 in [k for k in mk_res if k[1] == _t]:
                        mk_res[_k9] = _fr
''', '''                    # v-0925v D2: a sibling still unbooked is priced on the
                    # corrected result from now on
                    mk_res_correct(mk_res, _t, _fr)
''')
R.replace('''            _legs, _live_k = [], set()
            for _o, (_c, _w, _p, _n, _t) in open_pos.items():
                if (_c, _t) in mk_res:
                    _live_k.add((_c, _t))
                    if _o not in ub_parked:
                        _legs.append((_c, _t, _w, _p, _n))
''', '''            _legs, _live_k = market_pending_legs(open_pos, mk_res, ub_parked)
''')

# ---- D2: pintake's own loss rail is never sent an entry while a LEG-only dip is under it ---------------------------
R.replace('''    def _vg_hedgefail(now_):
''', '''    def _vg_legdip(now_):
        """v-0925v D2 (round 4, money review 1): PINTAKE'S OWN LOSS RAIL SEES
        LEGS, NOT MARKETS. pintake refuses every non-cover take while its
        per-process `realised` is at or under pintake.LOSS_ABORT (pintake is
        not touched by 0925v), and pin counts a refused entry as an ORDER
        ERROR -- two halt the run for good ("2 errors on the ORDER path").
        Round 3 let the run abort see a market's net, so while a market's
        legs were split the entries went on and met this rail instead: two of
        them refused and pin halted on a dip the market never had. Since
        round 4 a market's legs book in one pass, so this needs a pass that
        booked one leg and then failed; then, while the ledger by LEG is at
        or under pintake's line but the market view (mk_view) is above it,
        new entries are BLOCKED (reason leg_dip) -- nothing is sent for
        pintake to refuse -- and the block clears the moment the sibling
        books. Below the line by MARKET too, nothing is blocked here: a real
        loss reaches risk_abort (whose line is never looser than pintake's)
        and pintake's refusals count as they always did."""
        try:
            _r = float(pintake.LEDGER.get("realised", 0.0) or 0.0)
            _la = float(pintake.LOSS_ABORT)
            _mv = float(mk_view(_r, state, "run"))
        except (TypeError, ValueError, AttributeError):
            return
        if _r <= _la and _mv > _la:
            _eb_set("leg_dip", realised=round(_r, 2),
                    market_view=round(_mv, 2), pintake_loss_abort=_la,
                    why="a market's legs are booked apart: by leg the run is "
                        "at pintake's loss line, by market it is not; pintake "
                        "would refuse every entry")
        elif "leg_dip" in entry_blocks:
            _eb_clear("leg_dip", realised=round(_r, 2),
                      market_view=round(_mv, 2))

    def _vg_hedgefail(now_):
''')
R.replace('''    _VG_PARTS = (("apishape", _vg_apishape), ("unbooked", _vg_unbooked),
                 ("hedgefail", _vg_hedgefail), ("startbank", _vg_startbank),
''', '''    _VG_PARTS = (("apishape", _vg_apishape), ("unbooked", _vg_unbooked),
                 ("legdip", _vg_legdip),                 # v-0925v D2 (round 4)
                 ("hedgefail", _vg_hedgefail), ("startbank", _vg_startbank),
''')
R.replace('''    #   entries_blocked    reason "unbooked" (a provisional loss reaches the
    #                      day / run stop), "startup_bank" (no balance read
    #                      yet), "guard_error" (a part of this guard raised)
''', '''    #   entries_blocked    reason "unbooked" (a provisional loss reaches the
    #                      day / run stop), "startup_bank" (no balance read
    #                      yet), "guard_error" (a part of this guard raised),
    #                      "leg_dip" (round 4: pintake's per-leg loss rail
    #                      would refuse every entry while a market's legs
    #                      are booked apart)
''')

# ---- D5: hedge_broken needs failures on TWO markets in the streak --------------------------------------------------
R.replace('''HEDGE_FAIL_BLOCK = 3
HEDGE_BROKEN_HOLD_S = 900.0
''', '''HEDGE_FAIL_BLOCK = 3
HEDGE_BROKEN_HOLD_S = 900.0
# v-0925v D5 (round 4, 11-08): ...and on how many DIFFERENT markets those
# failures must fall before the block, so one market's reject loop no longer
# locks every other market of the close out (hedge_broken was round 2's
# "any market": the tests review found it blocking the very entries D5 frees)
HEDGE_FAIL_MARKETS = 2
''')
R.replace('''            "hedge_fail_block": HEDGE_FAIL_BLOCK,
''', '''            "hedge_fail_block": HEDGE_FAIL_BLOCK,
            "hedge_fail_markets": HEDGE_FAIL_MARKETS,
''')
R.replace('''    hf = {"streak": 0, "mkt": {}, "said": set(), "broken": None}
''', '''    hf = {"streak": 0, "mkt": {}, "said": set(), "broken": None,
          "streak_mk": set()}
''')
R.replace('''        HEDGE_FAIL_BLOCK in a row (any market) NEW ENTRIES are blocked
        (hedge_broken) -- a bot whose insurance cannot be bought must not
        open positions that need it. The hedge itself is untouched: next
        second's try goes out exactly as before. Never raises."""
        try:
            hf["streak"] += 1
            hf["mkt"][tk_] = hf["mkt"].get(tk_, 0) + 1
''', '''        HEDGE_FAIL_BLOCK in a row (any market) NEW ENTRIES are blocked
        (hedge_broken) -- a bot whose insurance cannot be bought must not
        open positions that need it. The hedge itself is untouched: next
        second's try goes out exactly as before. Never raises.

        v-0925v D5 (round 4, 11-08): ...but only once the streak has failed
        on HEDGE_FAIL_MARKETS (2) DIFFERENT markets. One market's hedge
        rejected again and again -- the 10-24..11-03 shape behind D5's 84
        attempts_cap fires -- is that market's insurance failing, and it
        locked every OTHER market of the close out exactly as the entry
        budget did (the tests review: 29 rejected sends on A, B never
        bought, 0 attempts_cap, 1 hedge_broken). Replayed on the local live
        logs 10-24..11-04, the any-market rule would have blocked 9 filled
        entries (every one won, ~$16 at the time's size), the two-market
        rule 2 (~$1). A broken hedge PATH still blocks: it fails on the next
        market that needs a hedge, and hedge_fail still says so per market
        per close from the first failure."""
        try:
            hf["streak"] += 1
            hf["mkt"][tk_] = hf["mkt"].get(tk_, 0) + 1
            hf["streak_mk"].add(tk_)             # v-0925v D5 (round 4)
''')
R.replace('''                rec("hedge_fail", ticker=tk_, close_s=cs_, status_code=code_,
                    body=_b, tau=tau_, streak=hf["streak"],
                    market_streak=hf["mkt"][tk_])
''', '''                rec("hedge_fail", ticker=tk_, close_s=cs_, status_code=code_,
                    body=_b, tau=tau_, streak=hf["streak"],
                    market_streak=hf["mkt"][tk_],
                    streak_markets=len(hf["streak_mk"]))
''')
R.replace('''            if hf["streak"] >= HEDGE_FAIL_BLOCK:
                _until = float(cs_) + HEDGE_BROKEN_HOLD_S
''', '''            if (hf["streak"] >= HEDGE_FAIL_BLOCK
                    and len(hf["streak_mk"]) >= HEDGE_FAIL_MARKETS):
                _until = float(cs_) + HEDGE_BROKEN_HOLD_S
''')
R.replace('''                    _eb_set("hedge_broken", kind="hedge_broken",
                            streak=hf["streak"], ticker=tk_, close_s=cs_,
''', '''                    _eb_set("hedge_broken", kind="hedge_broken",
                            streak=hf["streak"], ticker=tk_, close_s=cs_,
                            markets=sorted(hf["streak_mk"]),
''')
R.replace('''            hf["streak"] = 0
            hf["mkt"].pop(tk_, None)
            if hf["broken"] is not None:
''', '''            hf["streak"] = 0
            hf["mkt"].pop(tk_, None)
            hf["streak_mk"].clear()              # v-0925v D5 (round 4)
            if hf["broken"] is not None:
''')
R.replace('''        if _br is not None and now_ >= float(_br["until"]):
            hf["broken"] = None
            hf["streak"] = 0
''', '''        if _br is not None and now_ >= float(_br["until"]):
            hf["broken"] = None
            hf["streak"] = 0
            hf["streak_mk"].clear()              # v-0925v D5 (round 4)
''')
R.replace('''    #   hedge_broken       HEDGE_FAIL_BLOCK hedge sends in a row came back
    #                      non-2xx (any market; hedge_fail per market/close)
''', '''    #   hedge_broken       HEDGE_FAIL_BLOCK hedge sends in a row came back
    #                      non-2xx, on HEDGE_FAIL_MARKETS different markets
    #                      (round 4; hedge_fail per market/close)
''')

# ---- D4: the close's hedge cap on a jump-only second ends the jump only --------------------------------------------
R.replace('''                    if (hedge_attempts.get(_hcs, 0) >= MAX_HEDGE_ATTEMPTS_PER_CLOSE
                            and not hedge_panic(_belief)):
                        hedged.add(_hid)
''', '''                    if (hedge_attempts.get(_hcs, 0) >= MAX_HEDGE_ATTEMPTS_PER_CLOSE
                            and not hedge_panic(_belief)):
                        # v-0925v D4 (round 4, 11-08; both reviews): THE
                        # SAME RULE AT THE CLOSE'S HEDGE CAP. Round 3 kept a
                        # jump give-up from marking the position hedged at
                        # the 30-try line but not here: a jump-only second
                        # (belief still over the line, no panic) refused at
                        # MAX_HEDGE_ATTEMPTS_PER_CLOSE still marked it hedged
                        # for good, and a belief collapse after it was never
                        # hedged. Live this needs 120 hedge sends in one
                        # close (the most seen is 42); round 3 made it a
                        # little easier (a jump's 30 tries, then the belief
                        # line's). Now the jump's retries end, and the
                        # belief line keeps its own.
                        if _htrig == "jump" and not hedge_should_fire(_belief):
                            jump_gave_up.add(_hid)
                            hedge_tries[_hid] = 0
                            rec("hedge_refused", ticker=_htk, why="hedge_attempt_cap",
                                tried=hedge_attempts.get(_hcs, 0),
                                cap=MAX_HEDGE_ATTEMPTS_PER_CLOSE, tau=_htau,
                                trigger="jump", jump_only=True,
                                belief=round(_belief, 5),
                                still_armed="the belief line")
                            continue
                        hedged.add(_hid)
''')

# ---- JS: every second until it would send; written BELOW the hedge pass; pure argv checks --------------------------
R.replace('''    jump_shadow_said = set() # v-0925v JS: positions with a jump_shadow on record
''', '''    jump_shadow_said = set() # v-0925v JS: (position, outcome) on record (round 4)
    jump_shadow_sent = set() # v-0925v JS: positions whose shadow WOULD have sent
    jump_shadow_last = {}    # v-0925v JS: position -> the second it was last read
    jump_shadow_q = []       # v-0925v JS: what the hedge pass saw, written below it
''')
R.replace('''                    # v-0925v JS: the jump alarm WITHOUT its orders, while the
                    # jump hedge is off -- the same move, sigma and lookback;
                    # one jump_shadow record per position; nothing below sees
                    # it (no trigger, no try, no mark)
                    if (HEDGE_JUMP_SIGMA is None and HEDGE_JUMP_SHADOW is not None
                            and _hsg is not None and _hid not in jump_shadow_said):
                        _since_js = int(now_s - entry_at.get(_hid, now_s))
                        _hjs = jump_against(
                            idx.recent_moves(_hiid, max(1, min(HEDGE_JUMP_LOOKBACK_MAX, _since_js))),
                            _hsg, _hwant)
                        if _hjs is not None and _hjs >= HEDGE_JUMP_SHADOW:
                            jump_shadow_said.add(_hid)
                            _js_note(_hid, _hcs, _htk, _hwant, _hn_orig, _hn, _hjs,
                                     _belief, _htau, _hcost)
''', '''                    # v-0925v JS: the jump alarm WITHOUT its orders, while the
                    # jump hedge is off -- the same move, sigma and lookback;
                    # nothing below sees it (no trigger, no try, no mark).
                    # Round 4 (tests review 3, money review 3): read ONCE A
                    # SECOND, the jump hedge's own cadence, until the second
                    # it WOULD have sent -- a first second skipped (a 4.5c
                    # ask under the 5c floor) is not the end of the alarm,
                    # the jump hedge sends a second later -- and only QUEUED
                    # here: the flush below the hedge pass writes it, so no
                    # book read, file append or print sits in front of a
                    # hedge.
                    if (HEDGE_JUMP_SIGMA is None and HEDGE_JUMP_SHADOW is not None
                            and _hsg is not None and _hid not in jump_shadow_sent
                            and jump_shadow_last.get(_hid) != now_s):
                        _since_js = int(now_s - entry_at.get(_hid, now_s))
                        _hjs = jump_against(
                            idx.recent_moves(_hiid, max(1, min(HEDGE_JUMP_LOOKBACK_MAX, _since_js))),
                            _hsg, _hwant)
                        if _hjs is not None and _hjs >= HEDGE_JUMP_SHADOW:
                            jump_shadow_last[_hid] = now_s
                            jump_shadow_q.append((_hid, _hcs, _htk, _hwant, _hn_orig, _hn,
                                                  _hjs, _belief, _htau, _hcost))
''')
R.replace('''    def _js_note(hid_, cs_, tk_, want_, n_orig_, n_left_, jsd_, belief_,
                 tau_, entry_):
        """v-0925v JS: ONE jump_shadow record (jump_shadow_fields: the hedge
        the jump trigger WOULD have sent this second, sized as the send site
        sizes it, and whether the 8 sd cap or the 5c floor would have skipped
        it). Reads the book; sends nothing, spends no try, marks nothing.
        Never raises."""
        try:
            _f = jump_shadow_fields(
                book, tk_, want_, n_orig_, n_left_, jsd_, belief_, tau_,
                (cs_ - entry_at[hid_]) if hid_ in entry_at else None)
            rec("jump_shadow", ticker=tk_, close_s=cs_, want=want_, entry=entry_,
                live=bool(live), **_f)
            print(f"  jump SHADOW {tk_}: {jsd_:.1f} sd against {want_}, would "
                  f"buy {_f.get('side')} {_f.get('n')} @ {_f.get('ask')} "
                  f"(capped {_f.get('capped')}, cheap {_f.get('cheap_skip')}); "
                  f"nothing sent")
        except Exception:                                # noqa: BLE001
            pass
''', '''    def _js_flush():
        """v-0925v JS (round 4): the jump_shadow records for what the hedge
        pass queued this pass, written BELOW it. Per position, one record
        per OUTCOME (jump_shadow_fields: would_send, capped, cheap_skip,
        no_ask, filtered, nothing_to_buy) -- the hedge the jump trigger WOULD
        have sent this second, sized as the send site sizes it -- and once
        one says would_send the position is not read again (the jump hedge
        would have sent then). Reads the book; sends nothing, spends no try,
        marks nothing. Never raises."""
        try:
            _q = list(jump_shadow_q)
            del jump_shadow_q[:]
            for (hid_, cs_, tk_, want_, n_orig_, n_left_, jsd_, belief_,
                 tau_, entry_) in _q:
                if hid_ in jump_shadow_sent:
                    continue
                _f = jump_shadow_fields(
                    book, tk_, want_, n_orig_, n_left_, jsd_, belief_, tau_,
                    (cs_ - entry_at[hid_]) if hid_ in entry_at else None)
                if _f.get("would_send"):
                    jump_shadow_sent.add(hid_)
                if (hid_, _f.get("outcome")) in jump_shadow_said:
                    continue
                jump_shadow_said.add((hid_, _f.get("outcome")))
                rec("jump_shadow", ticker=tk_, close_s=cs_, want=want_, entry=entry_,
                    live=bool(live), **_f)
                print(f"  jump SHADOW {tk_}: {jsd_:.1f} sd against {want_}, "
                      f"{_f.get('outcome')}: {_f.get('side')} {_f.get('n')} @ "
                      f"{_f.get('ask')}; nothing sent")
        except Exception:                                # noqa: BLE001
            try:
                del jump_shadow_q[:]
            except Exception:                            # noqa: BLE001
                pass
''')
R.replace('''        # ---------------- end AMENDMENT 15 ----------------

        # R2 (review fix 2026-09-22): THE SLOW-PASS RECORD IS WRITTEN HERE,
''', '''        # ---------------- end AMENDMENT 15 ----------------

        # v-0925v JS (round 4): the shadow's records, BELOW the hedge pass --
        # queued by it, never written in front of a hedge
        if jump_shadow_q:
            _js_flush()

        # R2 (review fix 2026-09-22): THE SLOW-PASS RECORD IS WRITTEN HERE,
''')
R.span('''def jump_shadow_fields(book, tk, want, n_orig, n_left, jump_sd, belief, tau,
                       entry_tau=None):
''', '''        out["would_send"] = bool(_ok and _take > 1e-9 and not out["capped"]
                                 and not out["cheap_skip"])
    except Exception as _e:                              # noqa: BLE001
        out["err"] = type(_e).__name__
    return out
''', '''def jump_shadow_fields(book, tk, want, n_orig, n_left, jump_sd, belief, tau,
                       entry_tau=None):
    """v-0925v JS: what a jump_shadow record says -- the hedge the A52 jump
    trigger WOULD have sent this second, sized exactly as the hedge pass
    sizes it (hedge_want on what is still unhedged, flip_size, the ladder up
    to hedge_limit when --hedge-slip reads one), the other side's ask and its
    size, and whether --hedge-jump-max (jump_capped) or --jump-hedge-min-ask
    (cheap_jump_skip) would have skipped it. Reads the book; sends nothing.
    A module function so the hedge pass's own call sites (one each of
    jump_capped, cheap_jump_skip, hedge_limit, odds_extra) stay one each.
    Round 4: `outcome` names the FIRST thing on the jump hedge's own path
    that would have stopped this second's send, in the order the hedge pass
    meets them -- capped (not a trigger at all), nothing_to_buy (A76),
    no_ask, filtered (--hedge-price / --hedge-normal, never at panic),
    cheap_skip -- or would_send. Never raises: a read it cannot make leaves
    its field None (and the outcome "error")."""
    out = {"side": ("no" if want == "yes" else "yes"), "n": 0.0, "n_want": None,
           "ask": None, "ask_size": None, "limit": None,
           "belief": None, "jump_sd": None, "threshold": HEDGE_JUMP_SHADOW,
           "tau": tau, "capped": None, "cap": HEDGE_JUMP_MAX,
           "cheap_skip": None, "min_ask": JUMP_HEDGE_MIN_ASK, "panic": None,
           "filtered": None, "belief_fires": None, "extra_n": None,
           "would_send": False, "sent": False, "outcome": "error"}
    try:
        _opp = out["side"]
        out["belief"] = round(float(belief), 5)
        out["jump_sd"] = round(float(jump_sd), 2)
        try:
            _b = book.best(tk)
        except Exception:                                # noqa: BLE001
            _b = None
        _ask = (_b or {}).get(f"{_opp}_ask")
        _asz = (_b or {}).get(f"{_opp}_ask_size")
        out["ask"] = round(float(_ask), 4) if _ask is not None else None
        out["ask_size"] = _asz
        # the hedge pass's own no-ask test (hedge_no_ask)
        _ok = bool(_b) and bool(_ask) and bool(_asz) and float(_ask) < 1.0
        _nw = hedge_want(n_orig, float(n_left), belief)
        _nf = flip_size(_nw, entry_tau, tau)
        out["n_want"] = round(float(_nf), 2)
        _lim, _rg = None, []
        if _ok:
            _lim = hedge_limit(_ask, ticker=tk)
            if HEDGE_SLIP and _lim is not None:
                try:
                    _rg = book.rungs(tk, _opp, _lim)
                except Exception:                        # noqa: BLE001
                    _rg = []
        out["limit"] = round(float(_lim), 4) if _lim is not None else None
        _dep = hedge_depth(_asz, _rg, _nw) if (_ok and _asz) else 0.0
        _take = min(float(_nf), float(_dep or 0.0))
        out["n"] = round(_take, 2)
        out["capped"] = bool(jump_capped(jump_sd))
        out["panic"] = bool(hedge_panic(belief))
        # the hedge pass's three filters, in its order: the price and the
        # normal-bet waits (never at panic), then the $1 ask refusal
        out["filtered"] = bool(_ok and (
            (not out["panic"] and not (hedge_price_ok(_ask)
                                       and hedge_normal_ok(belief, _ask)))
            or not hedge_ask_ok(_ask)))
        out["cheap_skip"] = bool(_ok and cheap_jump_skip("jump", out["panic"], belief, _ask))
        out["belief_fires"] = bool(hedge_should_fire(belief))
        out["extra_n"] = odds_extra(n_orig, "jump", belief, tau)
        if out["capped"]:
            out["outcome"] = "capped"
        elif float(_nw) <= 1e-9:
            out["outcome"] = "nothing_to_buy"
        elif not _ok:
            out["outcome"] = "no_ask"
        elif out["filtered"]:
            out["outcome"] = "filtered"
        elif out["cheap_skip"]:
            out["outcome"] = "cheap_skip"
        elif _take > 1e-9:
            out["outcome"] = "would_send"
        else:
            out["outcome"] = "nothing_to_buy"
        out["would_send"] = out["outcome"] == "would_send"
    except Exception as _e:                              # noqa: BLE001
        out["err"] = type(_e).__name__
    return out
''')
R.replace('''def jump_shadow_conflict(hedge_jump, hedge_jump_shadow):
''', '''def jump_shadow_arg_error(sd):
    """v-0925v JS (round 4, from main() so it can be tested): the refusal
    for --hedge-jump-shadow SD, or None. In SIGMA, [1, 50] like
    --hedge-jump. Pure; cannot raise."""
    try:
        if 1.0 <= float(sd) <= 50.0:
            return None
    except (TypeError, ValueError):
        pass
    return ("--hedge-jump-shadow is in SIGMA and must be in [1, 50], got %r"
            % (sd,))


def jump_max_arg_error(jump_sigma, shadow_sigma, jump_max):
    """v-0925v JS (round 4, from main() so it can be tested): the refusal
    for --hedge-jump-max, or None. The cap needs a jump line to sit above
    -- --hedge-jump's, or with the jump hedge off the shadow's, which reads
    the same cap -- and is at most 100. Pure; cannot raise."""
    _jsd = jump_sigma if jump_sigma is not None else shadow_sigma
    try:
        if _jsd is not None and float(_jsd) < float(jump_max) <= 100.0:
            return None
    except (TypeError, ValueError):
        pass
    return ("--hedge-jump-max needs --hedge-jump (or --hedge-jump-shadow) "
            "and must be above it and at most 100, got %r" % (jump_max,))


def jump_shadow_conflict(hedge_jump, hedge_jump_shadow):
''')
R.replace('''    if a.hedge_jump_shadow is not None:
        if not (1.0 <= a.hedge_jump_shadow <= 50.0):
            raise SystemExit("--hedge-jump-shadow is in SIGMA and must be in "
                             "[1, 50], got %r" % (a.hedge_jump_shadow,))
        globals()["HEDGE_JUMP_SHADOW"] = float(a.hedge_jump_shadow)
''', '''    if a.hedge_jump_shadow is not None:
        _js_bad = jump_shadow_arg_error(a.hedge_jump_shadow)   # v-0925v JS
        if _js_bad:
            raise SystemExit(_js_bad)
        globals()["HEDGE_JUMP_SHADOW"] = float(a.hedge_jump_shadow)
''')
R.replace('''    if a.hedge_jump_max is not None:
        # v-0925v JS: the shadow reads the same cap, so it may carry it too
        _jsd = (HEDGE_JUMP_SIGMA if HEDGE_JUMP_SIGMA is not None
                else HEDGE_JUMP_SHADOW)
        if (_jsd is None
                or not (float(_jsd) < float(a.hedge_jump_max) <= 100.0)):
            raise SystemExit("--hedge-jump-max needs --hedge-jump (or "
                             "--hedge-jump-shadow) and must be above it and "
                             "at most 100, got %r" % (a.hedge_jump_max,))
''', '''    if a.hedge_jump_max is not None:
        # v-0925v JS: the shadow reads the same cap, so it may carry it too
        _jm_bad = jump_max_arg_error(HEDGE_JUMP_SIGMA, HEDGE_JUMP_SHADOW,
                                     a.hedge_jump_max)
        if _jm_bad:
            raise SystemExit(_jm_bad)
''')

# ---- F2: the two TEMP folders every self-test left ------------------------------------------------------------------
R.replace('''        finally:
            globals()["SIZE"] = _sv66
            pintake.LOSS_ABORT = _svla
''', '''        finally:
            globals()["SIZE"] = _sv66
            pintake.LOSS_ABORT = _svla
            # v-0925v F2 (round 4, 11-08): the sandbox folder was never
            # removed -- one pinmirror- folder in TEMP per self-test, i.e.
            # per live restart (788 on the laptop)
            __import__("shutil").rmtree(os.path.dirname(_mp), ignore_errors=True)
''')
R.replace('''    finally:
        _shr4.rmtree(_r4w_dir, ignore_errors=True)
''', '''    finally:
        # v-0925v F2 (round 4, 11-08): the --traj-log writer (BBB) HOLDS its
        # file open -- one handle, flushed once a second -- and on Windows a
        # folder with an open file in it cannot be deleted: rmtree(ignore_
        # errors) left one pintraj-selftest- folder per self-test (805 on the
        # laptop). Closed first, then deleted.
        try:
            _r4w_h = getattr(_r4w_w1, "handle", None)
            if _r4w_h and _r4w_h[0] is not None:
                _r4w_h[0].close()
                _r4w_h[0] = None
        except Exception:                                # noqa: BLE001
            pass
        _shr4.rmtree(_r4w_dir, ignore_errors=True)
''')
R.before('''def v0925v_settings():
''', '''# v-0925v F2 (round 4, 11-08): every TEMP folder the startup self-test makes
# through tempfile.mkdtemp, recorded by selftest() for the run's length (its
# finally sweeps any straggler and empties this). Two of them were left on
# every run -- one each per live restart.
_SELFTEST_TEMP = []


def sweep_selftest_temp(paths=None, tries=10, wait_s=0.05):
    """v-0925v F2 (round 4): remove every folder in `paths` (default: all
    the self-test recorded) that is still on disk. A removal that fails is
    retried `tries` times `wait_s` apart -- a scanner can hold a file it
    just saw closed for a moment -- with the REAL clock (an offline world's
    fake clock is never running here). Returns the folders still there.
    Never raises."""
    import shutil as _shs
    _left = []
    for _p in list(_SELFTEST_TEMP if paths is None else paths):
        try:
            for _i in range(int(tries)):
                if not os.path.exists(_p):
                    break
                _shs.rmtree(_p, ignore_errors=True)
                if os.path.exists(_p):
                    globals().get("_REAL_TIME", time).sleep(float(wait_s))
            if os.path.exists(_p):
                _left.append(_p)
        except Exception:                                # noqa: BLE001
            _left.append(_p)
    return _left


''')
# the offline harness: a world may plant moves that honour the LOOKBACK (moves_n(t, n)), so a check can see whether
# a read starts at entry; every existing world plants `moves` (newest first, the lookback ignored) and reads the same
R.replace('''            _mv = (by_iid.get(iid) or {}).get("moves")
            return list(_mv(clock.t - t0)) if callable(_mv) else []
''', '''            _mv = (by_iid.get(iid) or {}).get("moves")
            _mvn = (by_iid.get(iid) or {}).get("moves_n")   # v-0925v JS (round 4)
            if callable(_mvn):
                return list(_mvn(clock.t - t0, n))
            return list(_mv(clock.t - t0)) if callable(_mv) else []
''')

# ---- existing self-test checks the round-4 shapes change, said plainly ---------------------------------------------
# D2: v-safety2 (1a) read "books both legs and only then exits" as a halt after t 50 -- the cover used to book 15 s
# after the main leg (t ~65); both now book in one pass at t ~50, so the claim is checked as what it says: the halt
# comes after the LAST leg is booked
R.replace('''       and len(_kt_settled(_kt9)) == 2 and len(_kt9h) == 1
       and float(_kt9h[0]["t"]) > 50.0,
       "v-safety2 (1a) DRIVEN: a bot HALTED on its first pass still reads "
       "Kalshi, adopts the unknown 5 YES, hedges it, books both legs and only "
       "then exits (halt at %s s; before: exited at 0.05 s, never hedged)"
       % ([r.get("t") for r in _kt9h],))''', '''       and len(_kt_settled(_kt9)) == 2 and len(_kt9h) == 1
       and float(_kt9h[0]["t"]) >= 45.0
       and float(_kt9h[0]["t"]) >= max(float(r["t"]) for r in _kt9["recs"]
                                       if r.get("kind") == "settled") - 1e-9,
       "v-0925v D2 (round 4; the v-safety2 (1a) check, reworded): a bot HALTED "
       "on its first pass still reads Kalshi, adopts the unknown 5 YES, hedges "
       "it, books both legs and only then exits (halt at %s s, the last leg "
       "booked at %s s -- both legs book in one pass now, not 15 s apart; "
       "before v-safety2: exited at 0.05 s, never hedged)"
       % ([r.get("t") for r in _kt9h],
          [r.get("t") for r in _kt9["recs"] if r.get("kind") == "settled"]))''')

# ============================================================================ 15d. ROUND 5 (2026-11-08): the three reviews of round 4
# The money, tests and deploy reviews of round 4 (rev4_money\, rev4_tests\, rev4_deploy\) all said DEPLOY; round 5 fixes
# what they found anyway. In pinrun only F2's verdict moves -- everything else in round 5 is new self-test checks (no
# live behaviour changes) and the deploy script (pin_0925v.ps1: a fresh restart output per call, a rollback confirmed
# from the next pin log, a restart only well clear of a close).
#   F2  the TEMP check judges what is still there AFTER the retrying sweep: one briefly locked folder (a virus scanner)
#       failed the startup self-test, so pin refused to start -- and inside the deploy's watch, a false rollback

# ---- F2: the verdict is what the sweep could NOT remove -------------------------------------------------------------
R.after('''            if os.path.exists(_p):
                _left.append(_p)
        except Exception:                                # noqa: BLE001
            _left.append(_p)
    return _left
''', '''

# v-0925v F2 (round 5, 11-08): every path the startup self-test hands to
# shutil.rmtree, recorded by selftest() BEFORE the real call (emptied in its
# finally) -- so the F2 check can tell a folder its own code never removed
# from one a passing lock held while its code removed it
_SELFTEST_RM = []


def sweep_temp_verdict(made, tries=40, wait_s=0.05):
    """v-0925v F2 (round 5, 11-08; the money and deploy reviews of round 4):
    THE VERDICT ON THE SELF-TEST'S TEMP FOLDERS IS WHAT THE SWEEP COULD NOT
    REMOVE. Round 4's check failed on the folders still on disk BEFORE its
    retrying sweep ran, so one folder an antivirus scan held for a moment
    (rmtree(ignore_errors) then removes nothing, silently) failed the
    startup self-test: pin refused to start, and inside pin_0925v.ps1's
    watch that read as a dead pin -- a false rollback. Every folder of
    `made` still on disk is swept (sweep_selftest_temp: `tries` x `wait_s`,
    2 s at most, spent only while something is held -- round 4's sweep
    gave a lock 0.5 s). Returns (swept, left): the folders the retries
    removed -- a passing lock, REPORTED in the check's line, never a
    failure -- and the folders still there after every retry, which only a
    handle that stays open can keep (pin code's own, round 4's pintraj-
    shape: a real leak) -- the failure. Never raises."""
    try:
        _there = [p for p in (made or []) if os.path.exists(p)]
    except Exception:                                    # noqa: BLE001
        _there = list(made or [])
    _left = sweep_selftest_temp(_there, tries=tries, wait_s=wait_s)
    return [p for p in _there if p not in _left], _left
''')

# ============================================================================ 16. the self-test harness and the new checks
# ---- 16a. the offline harness: what the v-0925v worlds need to plant, and its state kept per world
R.replace('''                        strict_book=False, hwm0=None, max_losses=0):
    """Run the REAL trade_loop for `run_s` fake seconds on one close.''',
          '''                        strict_book=False, hwm0=None, max_losses=0,
                        loss_abort=-1e9, settle=None, events_only=False,
                        skew=None, expiry=False, stdout=None, day0=None,
                        book_stats=None):
    """Run the REAL trade_loop for `run_s` fake seconds on one close.''')
R.before('''    Returns {"recs", "posts", "raised", "ran_s", "state"}. A record's `t` is
    fake wall time since the start, in seconds.
''', '''    v-0925v (2026-11-07), every one off by default, so every existing world
    runs exactly as it did:
    loss_abort the run's --loss-abort (default -1e9: no stop), for the
               provisional-loss bound (unbooked).
    settle     settle(ticker, t) -> a "market" dict (status, result) or None
               for GET /markets/<ticker>, ahead of `result` -- determined,
               disputed, a market that stays closed, a late finalized.
    events_only GET /markets answers an empty list for every series and GET
               /events (with nested markets) answers the rows (the fallback);
               a callable events_only(t) says so per refresh. A market may
               also plant "close_time" (a string) and "exi" (an
               exchange_index; None = the key is missing) on its own rows.
               GET /markets now honours `limit` (rows in `markets` order), as
               Kalshi does -- every existing world asks for fewer rows than it
               plants per series, so none reads differently.
    skew       skew(t) -> (offset_ms, n): the index socket's clock reading
               (whatever quantile is asked); it may raise (a guard fault).
    day0       a day-loss total already on file for today (the A79 file).
    book_stats the book's malformed-frame counters (book.stats).
    expiry     the --minutes drain (expiry_drain); False = the old exit at
               the end, which every existing world was written against.
    stdout     the stream the loop prints to (a planted failing console).
    `bank` may be a callable bank(t) -> dollars or None (a failing read).

''')
R.replace('''        def conditions(self, iid):
            f = (by_iid.get(iid) or {}).get("cond_raise")
''', '''        def clock_skew_ms(self, window_s=None, now_ms=None, q=None):
            # v-0925v clockskew: a world may plant the socket's reading
            if skew is None:
                return None, 0
            return skew(clock.t - t0)

        def conditions(self, iid):
            f = (by_iid.get(iid) or {}).get("cond_raise")
''')
R.replace('''    def _get(path, params=None, **kw):
        if str(path).startswith("/portfolio/"):
''', '''    def _v_row(m):
        # v-0925v: the 15M row as before, with a planted close_time / exi
        r = {"ticker": m["tk"], "close_time": m.get("close_time", iso),
             "floor_strike": m["strike"],
             "custom_strike": {"floor_strike": m["strike"],
                               "round_digits": 2},
             "exchange_index": m.get("exi", 2)}
        if "exi" in m and m["exi"] is None:
            r.pop("exchange_index")
        return r

    def _get(path, params=None, **kw):
        if str(path).startswith("/portfolio/"):
''')
R.replace('''        if (result is not None and str(path).startswith("/markets/")
                and path[len("/markets/"):] in result):
''', '''        if settle is not None and str(path).startswith("/markets/"):
            _sm = settle(path[len("/markets/"):], round(clock.t - t0, 3))
            if _sm is not None:                  # v-0925v: a planted status
                return 200, {"market": dict(_sm)}
        if path == "/events":                    # v-0925v universe: the fallback
            gets.append((path, dict(params or {}, _t=round(clock.t - t0, 3))))
            s = (params or {}).get("series_ticker")
            return 200, {"events": [
                {"event_ticker": m["tk"].rsplit("-", 1)[0],
                 "markets": [dict(_v_row(m), status="active")]}
                for m in markets if m["series"] == s], "cursor": ""}
        if (result is not None and str(path).startswith("/markets/")
                and path[len("/markets/"):] in result):
''')
R.replace('''            s = (params or {}).get("series_ticker")
            return 200, {"markets": [
                {"ticker": m["tk"], "close_time": iso,
                 "floor_strike": m["strike"],
                 "custom_strike": {"floor_strike": m["strike"],
                                   "round_digits": 2},
                 "exchange_index": 2}
                for m in markets if m["series"] == s]}
''', '''            s = (params or {}).get("series_ticker")
            if (events_only(round(clock.t - t0, 3)) if callable(events_only)
                    else events_only):           # v-0925v universe
                return 200, {"markets": []}
            _lim = int((params or {}).get("limit") or 10 ** 6)
            return 200, {"markets": [_v_row(m) for m in markets
                                     if m["series"] == s][:_lim]}
''')
R.replace('''    saved_ledger = _cp.deepcopy(pintake.LEDGER)
    tmp = _tf.mkdtemp(prefix="pinloop-")
''', '''    saved_ledger = _cp.deepcopy(pintake.LEDGER)
    # v-0925v: the sentinel, the log health and the pending day totals are
    # PROCESS state; each world starts clean and hands them back, so no world
    # can dedupe another's record or inherit a planted failure
    _v_saved = (set(_API_SHAPE_SEEN), list(_API_SHAPE_Q),
                _cp.deepcopy(_LOG_HEALTH), dict(_DAYLOSS_PENDING))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    _DAYLOSS_PENDING.clear()
    for _hv in _LOG_HEALTH.values():
        _hv.update(streak=0, fails=0, said=False, err=None)
    tmp = _tf.mkdtemp(prefix="pinloop-")
''')
R.replace('''        g["read_bank"] = (_no_net if bank is None
                          else (lambda *_a, **_k: float(bank)))
''', '''        if day0 is not None:         # v-0925v: a day total already on file
            with open(g["DAYLOSS_FILE"], "w", encoding="utf-8") as _v_fh:
                json.dump({"day": et_day_key(t0), "realised": float(day0),
                           "at": "planted"}, _v_fh)
        def _v_bank(*_a, **_k):
            # v-0925v startbank: a world may plant a read that fails (None)
            return (bank(round(clock.t - t0, 3)) if callable(bank)
                    else float(bank))
        g["read_bank"] = (_no_net if bank is None else _v_bank)
''')
R.replace('''                           auto_size=bank is not None, loss_abort=-1e9,
''', '''                           auto_size=bank is not None,
                           loss_abort=float(loss_abort),
                           expiry_drain=bool(expiry),
''')
R.replace('''        with _cl.redirect_stdout(_io.StringIO()):
''', '''        with _cl.redirect_stdout(stdout if stdout is not None
                                 else _io.StringIO()):
''')
R.replace('''        pintake.LEDGER.clear()
        pintake.LEDGER.update(saved_ledger)
        _sh.rmtree(tmp, ignore_errors=True)
''', '''        pintake.LEDGER.clear()
        pintake.LEDGER.update(saved_ledger)
        _API_SHAPE_SEEN.clear()
        _API_SHAPE_SEEN.update(_v_saved[0])
        _API_SHAPE_Q.clear()
        _API_SHAPE_Q.extend(_v_saved[1])
        _LOG_HEALTH.clear()
        _LOG_HEALTH.update(_v_saved[2])
        _DAYLOSS_PENDING.clear()
        _DAYLOSS_PENDING.update(_v_saved[3])
        _sh.rmtree(tmp, ignore_errors=True)
''')

R.replace('''    class _Book:
        def best(self, tk):
            _count("best")
''', '''    class _Book:
        stats = {} if book_stats is None else book_stats   # v-0925v: the counters

        def best(self, tk):
            _count("best")
''')

# ---- 16b. selftest(): the whole self-test hands the v-0925v process state back
R.replace('''    _lcf_real, _lcb_real = LOSS_CAP_FRAC, LOSS_CAP_BASE
    globals()["LOSS_CAP_FRAC"] = _DEFAULT_LOSS_CAP_FRAC
    try:
        return _selftest_body()
    finally:
        globals()["LOSS_CAP_FRAC"] = _lcf_real
''', '''    _lcf_real, _lcb_real = LOSS_CAP_FRAC, LOSS_CAP_BASE
    globals()["LOSS_CAP_FRAC"] = _DEFAULT_LOSS_CAP_FRAC
    # v-0925v: the api_shape sentinel, the log health and the pending day
    # totals are PROCESS state. The startup self-test plants every one of
    # them (a balance with no cents, a failing log, an unwritable day file);
    # handed back here, or the live run would start with a test's records in
    # its queue, a test's key deduping a real one, or a planted failure.
    import copy as _cpv
    _v_real = (set(_API_SHAPE_SEEN), list(_API_SHAPE_Q), _API_SHAPE_DROPPED[0],
               _cpv.deepcopy(_LOG_HEALTH), dict(_DAYLOSS_PENDING),
               _PRINT_FAILS[0])
    # v-0925v F2 (round 4, 11-08): EVERY TEMP FOLDER THE SELF-TEST MAKES IS
    # RECORDED AND REMOVED. Two sections left one each on every run --
    # pinmirror- (never removed) and pintraj-selftest- (a held handle) -- and
    # this runs at every live start; each mkdtemp of the run is kept in
    # _SELFTEST_TEMP (a v-0925v check proves none is left near the body's
    # end) and any straggler is swept below. And inspect.getsource is
    # MEMOIZED for the run's length: 19 checks tokenized the 8,000-line
    # trade_loop afresh (0.7 s of every start); a function object's source
    # cannot change inside one process. Both handed back in the finally.
    import tempfile as _v_tfm
    _v_mkd_real, _v_gs_real = _v_tfm.mkdtemp, inspect.getsource
    del _SELFTEST_TEMP[:]
    _v_gs_memo = {}

    def _v_mkdtemp(*_a, **_k):
        _p = _v_mkd_real(*_a, **_k)
        _SELFTEST_TEMP.append(_p)
        return _p

    def _v_getsource(obj):
        _h = _v_gs_memo.get(id(obj))
        if _h is not None and _h[0] is obj:
            return _h[1]
        _s = _v_gs_real(obj)
        _v_gs_memo[id(obj)] = (obj, _s)
        return _s
    _v_tfm.mkdtemp, inspect.getsource = _v_mkdtemp, _v_getsource
    # v-0925v F2 (round 5, 11-08): ...and every path handed to shutil.rmtree
    # is recorded (_SELFTEST_RM) BEFORE the real call. Since round 5 the F2
    # check passes a folder its retrying sweep removes (a scanner's passing
    # lock must not stop pin starting), so the sweep alone would also hide a
    # folder its own code NEVER removes -- round 4's pinmirror- shape; the
    # record tells the two apart, and a lock cannot change it (the call is
    # recorded whether or not the delete then works).
    import shutil as _v_shm
    _v_rm_real = _v_shm.rmtree
    del _SELFTEST_RM[:]

    def _v_rmtree(path, *_a, **_k):
        try:
            _SELFTEST_RM.append(os.path.normcase(os.path.abspath(str(path))))
        except Exception:                                # noqa: BLE001
            pass
        return _v_rm_real(path, *_a, **_k)
    _v_rmtree.avoids_symlink_attacks = getattr(_v_rm_real, "avoids_symlink_attacks", False)
    _v_shm.rmtree = _v_rmtree
    try:
        return _selftest_body()
    finally:
        _v_tfm.mkdtemp, inspect.getsource = _v_mkd_real, _v_gs_real
        _v_shm.rmtree = _v_rm_real                    # v-0925v F2 (round 5)
        sweep_selftest_temp()
        del _SELFTEST_TEMP[:]
        del _SELFTEST_RM[:]
        _API_SHAPE_SEEN.clear()
        _API_SHAPE_SEEN.update(_v_real[0])
        _API_SHAPE_Q.clear()
        _API_SHAPE_Q.extend(_v_real[1])
        _API_SHAPE_DROPPED[0] = _v_real[2]
        _LOG_HEALTH.clear()
        _LOG_HEALTH.update(_v_real[3])
        _DAYLOSS_PENDING.clear()
        _DAYLOSS_PENDING.update(_v_real[4])
        _PRINT_FAILS[0] = _v_real[5]
        globals()["LOSS_CAP_FRAC"] = _lcf_real
''')

# ---- 16c. the new checks, before the end-of-body guard that proves every live setting was handed back
R.before('''    # THE SELF-TEST MUST LEAVE NO LIVE SETTING CHANGED. It runs at startup
''', r'''    # ==== v-0925v (2026-11-07): THE FAIL-SAFE BUILD ==========================
    # The operator: "Anything that could cause the 1k+ loss needs to be
    # addressed immediately." Every fix gets a DRIVEN world where its
    # condition happens (through the REAL trade_loop where it lives there)
    # and a NULL world where it does not and the bot does what it always did.
    # Every message starts "v-0925v <fix>": pin_0925v.ps1 counts them, and
    # mutate.py (shipped beside patch_0925v.py) proves each fix's checks FAIL with the fix
    # switched off. The sentinel, the log health and the pending day totals
    # are process state: cleared here, handed back by selftest()'s finally.
    # Review round (11-07, four reviews): the checks a weak test missed are
    # added -- the day cap with a provisional loss, a guard part that raises,
    # 503 / -1 / refused hedges, the extra leg, "in a row", a box clock
    # behind Kalshi, the hold restarting, an unknown order at the end, the
    # mirror lowering the size and waiting for flat, the exact 3rd failure,
    # the trajectory writer, $0.50 and inf balances, a hedged pair, the
    # refresh count resetting, Kalshi's own row limit, the socket counters.
    import io as _v_io
    import contextlib as _v_cl
    import tempfile as _v_tf
    import shutil as _v_sh
    _v_src = open(os.path.abspath(__file__), encoding="utf-8").read()
    _v_tl = inspect.getsource(trade_loop)
    _v_close = 1_800_000_000                      # the offline loop's close
    _v_iso = _REAL_TIME.strftime("%Y-%m-%dT%H:%M:%SZ", _REAL_TIME.gmtime(_v_close))

    def _v_shape(endpoint=None, field=None, what=None):
        return [e for e in _API_SHAPE_Q
                if (endpoint is None or e.get("endpoint") == endpoint)
                and (field is None or e.get("field") == field)
                and (what is None or e.get("what") == what)]

    def _v_posts(res, tk, side=None):
        return [p for p in res["posts"] if p.get("ticker") == tk
                and (side is None or p.get("side") == side)]

    def _v_ts(res, kind, **match):
        return [r["t"] for r in res["recs"] if r["kind"] == kind
                and all(r.get(k) == v for k, v in match.items())]

    def _v_blocked(res, reason):
        return reason in ((res["state"] or {}).get("entry_blocks") or {})

    def _v_A(n, collapse_at=4, decided_at=None, close_time=None, exi=None):
        # an A-like market of its own series: YES bought at 95c as soon as
        # it is decided, its belief collapsing to 0.10 at `collapse_at`
        m = {"tk": "KXA%d15M-K1" % n, "series": "KXA%d15M" % n,
             "iid": "K1A%d" % n, "strike": 100.0,
             "fair": (lambda t: 0.10 if (collapse_at is not None and t >= collapse_at)
                      else (0.999 if (decided_at is None or t >= decided_at)
                            else 0.5)),
             "book": (lambda t: _ob(0.94, 0.05))}
        if close_time is not None:
            m["close_time"] = close_time
        if exi is not None:
            m["exi"] = exi
        return m

    # a bank the default sizer turns into exactly the worlds' size 5
    _v_bank5 = 5.5 * float(worst_close_cost(1.0)) * float(_DEFAULT_BANK_BRAKE)

    def _v_reads():
        # a fake balance that records when it was read
        _r = []

        def _b(t):
            _r.append(t)
            return _v_bank5
        _b.reads = _r
        return _b

    _v_kB = "KXB115M-K1"

    # ---- bankread ------------------------------------------------------
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    _v_fk = {"base": "b", "pk": "k", "key_id": "i"}

    def _v_bget(payload, status=200):
        def _g(base, pk, key_id, path, query=None):
            return status, payload
        return _g
    _v_pg = pintake._get
    try:
        pintake._get = _v_bget({"balance_dollars": "1234.5600"})
        _vb1, _vb1b = read_bank(_v_fk), read_bank(_v_fk)
        _vb1q = _v_shape("/portfolio/balance", "balance", "missing")
        pintake._get = _v_bget({"balance": 123456, "balance_dollars": "1234.56"})
        _vb2 = read_bank(_v_fk)
        pintake._get = _v_bget({"balance": 19215, "balance_dollars": "19215.00"})
        _vb3 = read_bank(_v_fk)
        pintake._get = _v_bget({"balance": 19215})
        _vb4 = read_bank(_v_fk)
        pintake._get = _v_bget({"balance": 100001, "balance_dollars": "1000.00"})
        _vb5 = read_bank(_v_fk)
        _vb_bad = []
        for _pl in ({"balance_dollars": "nan"}, {"balance_dollars": "x"},
                    {"balance": "junk", "balance_dollars": "10.00"},
                    {"balance_dollars": "inf"}, {"balance_dollars": "-inf"},
                    {"balance": 100050, "balance_dollars": "1000.00"}):
            pintake._get = _v_bget(_pl)
            _vb_bad.append(read_bank(_v_fk))
    finally:
        pintake._get = _v_pg
    ck(_vb1 is not None and abs(_vb1 - 1234.56) < 1e-9 and _vb1b == _vb1
       and len(_vb1q) == 1 and _vb1q[0].get("used") == "balance_dollars"
       and _vb2 is not None and abs(_vb2 - 1234.56) < 1e-9
       and _vb5 == 1000.0
       and _vb3 is None and _vb4 is None and _vb_bad == [None] * 6,
       "v-0925v bankread: balance_dollars ALONE reads $%s (cents optional), the "
       "missing cents recorded ONCE over two reads (%d api_shape); both present "
       "and agreeing (to the cent) read; disagreeing (the 19215-as-dollars shape, "
       "and by 50c), cents alone, NaN / inf / garbage dollars and garbage cents "
       "are all refused (%r)" % (_vb1, len(_vb1q), [_vb3, _vb4] + _vb_bad))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()

    # ---- unbooked: pure ------------------------------------------------
    ck(settle_read({"status": "determined", "result": "yes"}) == ("determined", "yes")
       and settle_read({"status": "amended", "result": "no"}) == ("amended", "no")
       and settle_read({"status": "finalized", "result": "no"}) == ("finalized", "no")
       and settle_read({"status": "settled", "result": "yes"}) == ("settled", "yes")
       and settle_read({"status": "Finalized", "result": "YES"}) == ("finalized", "yes")
       and settle_read({"status": "disputed", "result": "yes"}) == (None, None)
       and settle_read({"status": "closed", "result": ""}) == (None, None)
       and settle_read({"status": "determined", "result": ""}) == (None, None)
       and settle_read({"status": "finalized", "result": ""}) == ("finalized", "")
       and settle_read({"status": "resolved", "result": "yes"}) == (None, None)
       and settle_read({"result": "yes"}) == (None, None)
       and settle_read(None) == (None, None)
       and len(_v_shape("/markets/<ticker>", "status", "unknown")) == 1
       and len(_v_shape("/markets/<ticker>", "status", "missing")) == 1,
       "v-0925v unbooked: settle_read BOOKS determined / amended / finalized / "
       "settled with a yes-no result (case-blind); NEVER disputed; not closed, "
       "not a determined market whose result has not arrived; a terminal void "
       "comes back for the old unbooked release; an unknown or missing status "
       "books nothing and is recorded once each")
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    _vw1 = unbooked_worst([("yes", 0.95, 10.0)])
    _vw2 = unbooked_worst([("yes", 0.95, 10.0), ("no", 0.10, 10.0)])
    ck(abs(_vw1 + 9.5 + billed_fee(0.95, 10.0)) < 1e-9
       and abs(_vw2 - (-0.5 - billed_fee(0.95, 10.0) - billed_fee(0.10, 10.0))) < 1e-9
       and unbooked_worst([]) == 0.0
       and unbooked_bound(-5.0, 0.0, None, -3.0) is not None
       and unbooked_bound(-2.0, 0.0, None, -3.0) is None
       and unbooked_bound(-2.0, -1.5, None, -3.0) is not None
       and unbooked_bound(-2.0, 0.0, -1.5, -3.0, live=True) is not None
       and unbooked_bound(-2.0, 0.0, -1.5, -3.0, live=False) is None
       and unbooked_bound(-2.0, 0.0, -1.5, -3.0, live=True, day_unbooked=0.0) is None
       and str(unbooked_bound(-2.0, 0.0, -1.5, -3.0, live=True,
                              day_unbooked=-2.0)).startswith("day:")
       and unbooked_bound(0.0, -100.0, -100.0, -3.0) is None
       and unbooked_bound("x", 0.0, None, -3.0) is not None,
       "v-0925v unbooked: the provisional loss is the WORST the unbooked legs "
       "can lose together (one 95c leg: its full cost $%.4f; a 95c leg and its "
       "10c cover: $%.4f), and it trips the run abort or (live) the day cap "
       "exactly where settled money would -- the day cap with TODAY's part only; "
       "nothing unbooked trips nothing; garbage is a reason (fail safe)"
       % (_vw1, _vw2))
    _v_now7 = calendar.timegm((2026, 11, 7, 18, 0, 0))          # 13:00 EST
    _v_sp = unbooked_split({(_v_now7 - 3600, "T-A"): -2.0,
                            (_v_now7 - 86400, "T-B"): -3.0,
                            (_v_now7 - 7200, "T-C"): 0.5}, _v_now7)
    ck(_v_sp == (-5.0, -2.0) and unbooked_split({}, _v_now7) == (0.0, 0.0)
       and unbooked_split(None, _v_now7) == (0.0, 0.0),
       "v-0925v unbooked: a market that closed YESTERDAY (ET) counts against the "
       "run abort only, today's against both (run %s, today %s): a stuck "
       "market is never charged to every later day's cap" % _v_sp)

    # ---- unbooked: DRIVEN through the real loop --------------------------
    # A: YES 5 @98c at t 0, the close at t 30. Shrunk clocks: parked and
    # provisional 60 s after the close, read every 5 s, every 20 s from 150 s
    # after it. Run abort -$3, which the provisional $4.90 + fee reaches and
    # nothing else does.
    _v_ubf = {"UNBOOKED_AFTER_S": 60.0, "UNBOOKED_POLL_S": 5.0,
              "UNBOOKED_SLOW_AFTER_S": 150.0, "UNBOOKED_SLOW_POLL_S": 20.0}

    def _v_settle(status, result=None, until=None, then=None, tk_=None, calls=None):
        def _s(tk, t):
            if tk != (tk_ or _kA):
                return None
            if calls is not None:
                calls.append(t)
            if until is not None and t >= until:
                return then
            return {"status": status, "result": result}
        return _s
    _v_ud = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=70.0,
                                settle=_v_settle("determined", "yes"))
    _v_udp = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=70.0,
                                 settle=_v_settle("disputed", "yes"))
    _v_uds = _kinds(_v_ud, "settled", _kA)
    ck(_v_ud["raised"] is None and len(_v_uds) == 1
       and _v_uds[0].get("result") == "yes" and float(_v_uds[0]["pnl_c"]) > 0
       and _v_udp["raised"] is None and not _kinds(_v_udp, "settled", _kA),
       "v-0925v unbooked DRIVEN: a market Kalshi calls DETERMINED (result yes) "
       "is booked like a finalized one (%d settled, %s c); the same market "
       "DISPUTED is not booked (%d settled)"
       % (len(_v_uds), (_v_uds[0].get("pnl_c") if _v_uds else None),
          len(_kinds(_v_udp, "settled", _kA))))
    _v_upk = []

    def _v_upk_f(kind, kw):
        # at the provisional record the leg has just been PARKED: what the
        # stake cap and the open cap see of it then
        if kind == "unbooked" and kw.get("what") == "provisional":
            _v_upk.append((float(pintake.LEDGER.get("committed", 0.0)),
                           _kA in (pintake.LEDGER.get("positions") or {})))
    _v_up = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=120.0,
                                loss_abort=-3.0, flags=dict(_v_ubf),
                                settle=_v_settle("closed"), rec_fault=_v_upk_f)
    _v_upr = [r for r in _kinds(_v_up, "unbooked", _kA) if r.get("what") == "provisional"]
    _v_upb = _v_ts(_v_up, "entries_blocked", reason="unbooked")
    ck(_v_up["raised"] is None and len(_v_upr) == 1
       and _v_upr[0]["t"] >= 30.0 + 60.0 - 0.1
       and abs(float(_v_upr[0]["worst"]) + 4.9 + billed_fee(0.98, 5.0)) < 0.011
       and _v_upr[0].get("status") == "closed"
       and len(_v_upb) == 1 and _v_upb[0] >= _v_upr[0]["t"] - 1e-9
       and _v_blocked(_v_up, "unbooked")
       and not _kinds(_v_up, "settled", _kA)
       and _kinds(_v_up, "order", _kA),
       "v-0925v unbooked DRIVEN: a market that stays CLOSED is no longer "
       "released unbooked -- 60 s after its close it is PROVISIONAL (one "
       "unbooked record at t %s, worst %s) and, reaching the -$3 run abort, "
       "blocks new entries (entries_blocked at %s) while it waits"
       % ((_v_upr[0]["t"] if _v_upr else None),
          (_v_upr[0].get("worst") if _v_upr else None), _v_upb))
    ck(_v_upk and _v_upk[0][0] < 1e-9 and _v_upk[0][1] is False,
       "v-0925v unbooked DRIVEN: the PARKED leg lets go of the caps exactly as "
       "0925u's release did -- the stake cap's committed and pintake's open "
       "position for it are given back (%r) -- so a stuck market cannot hold "
       "the open cap for hours" % (_v_upk,))
    _v_ul = _offline_trade_loop(
        [_k1_A(collapse_at=None)], live=True, run_s=130.0, loss_abort=-3.0,
        flags=dict(_v_ubf),
        settle=_v_settle("closed", until=110.0,
                         then={"status": "finalized", "result": "yes"}))
    _v_ulb = [r for r in _kinds(_v_ul, "unbooked", _kA) if r.get("what") == "booked"]
    _v_ulr = _v_ts(_v_ul, "entries_resumed", reason="unbooked")
    _v_uls = _kinds(_v_ul, "settled", _kA)
    ck(_v_ul["raised"] is None and len(_v_ulb) == 1 and len(_v_uls) == 1
       and float(_v_ulb[0]["pnl_c"]) > 0 and _v_ulb[0]["t"] >= 110.0
       and _v_ts(_v_ul, "entries_blocked", reason="unbooked")
       and len(_v_ulr) == 1 and _v_ulr[0] >= _v_ulb[0]["t"] - 1e-9
       and not _v_blocked(_v_ul, "unbooked"),
       "v-0925v unbooked DRIVEN: the same market FINALIZED late (t 110) is "
       "booked then (%s c), the real P&L replaces the provisional loss, and "
       "entries resume (at %s)"
       % ((_v_ulb[0].get("pnl_c") if _v_ulb else None), _v_ulr))
    _v_ugc = []
    _v_ug = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=240.0,
                                loss_abort=-3.0, flags=dict(_v_ubf),
                                settle=_v_settle("closed", until=210.0, calls=_v_ugc,
                                                 then={"status": "finalized",
                                                       "result": "yes"}))
    _v_ugs = [r for r in _kinds(_v_ug, "unbooked", _kA) if r.get("what") == "slow"]
    _v_ugb = [r for r in _kinds(_v_ug, "unbooked", _kA) if r.get("what") == "booked"]
    _v_ugq = [t for t in _v_ugc if 185.0 <= t < 210.0]
    ck(_v_ug["raised"] is None and len(_v_ugs) == 1
       and _v_ugs[0]["t"] >= 30.0 + 150.0 - 0.1
       and len(_v_ugq) <= 2
       and all(b - a >= 19.9 for a, b in zip(_v_ugq, _v_ugq[1:]))
       and len(_v_ugb) == 1 and 210.0 <= _v_ugb[0]["t"] <= 231.0
       and len(_kinds(_v_ug, "settled", _kA)) == 1
       and not _v_blocked(_v_ug, "unbooked"),
       "v-0925v unbooked DRIVEN: a market still not booked 6 h after its close "
       "(150 s here) is NOT released: slow at t %s, read every 10 min (20 s "
       "here: %s), and when Kalshi finally answers it is booked (t %s) and the "
       "block lifts" % ((_v_ugs[0]["t"] if _v_ugs else None), _v_ugq,
                        (_v_ugb[0]["t"] if _v_ugb else None)))

    def _v_settle_dead(tk, t):
        raise RuntimeError("planted: GET /markets/<ticker> never answers")
    _v_ux = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=200.0,
                                loss_abort=-3.0, flags=dict(_v_ubf),
                                settle=_v_settle_dead)
    _v_uxp = [r for r in _kinds(_v_ux, "unbooked", _kA) if r.get("what") == "provisional"]
    ck(_v_ux["raised"] is None and len(_v_uxp) == 1
       and _v_blocked(_v_ux, "unbooked") and not _kinds(_v_ux, "settled", _kA),
       "v-0925v unbooked DRIVEN: a market whose GET never answers is "
       "provisional from 60 s after its close and stays so -- never released "
       "unbooked, never booked on a guess -- so it keeps counting against the "
       "stop until Kalshi answers")
    _v_un = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=120.0,
                                loss_abort=-3.0, flags=dict(_v_ubf),
                                result={_kA: "yes"})
    ck(_v_un["raised"] is None and len(_kinds(_v_un, "settled", _kA)) == 1
       and not _kinds(_v_un, "unbooked") and not _kinds(_v_un, "entries_blocked")
       and not ((_v_un["state"] or {}).get("entry_blocks") or {}),
       "v-0925v unbooked NULL: a market finalized on time books at once, writes "
       "no unbooked record and blocks nothing (%d settled)"
       % len(_kinds(_v_un, "settled", _kA)))
    # the DAY cap with a provisional loss (review: every driven world tripped
    # the RUN abort): $2 already lost today on file, the run at $0, stop -$6
    # -- the run alone (-$4.97) does not reach it, today's file plus the
    # provisional does; and the same world with nothing on file blocks nothing
    _v_udc = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=120.0,
                                 loss_abort=-6.0, flags=dict(_v_ubf), day0=-2.0,
                                 settle=_v_settle("closed"))
    _v_udc0 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=120.0,
                                  loss_abort=-6.0, flags=dict(_v_ubf),
                                  settle=_v_settle("closed"))
    _v_udcb = [r for r in _kinds(_v_udc, "entries_blocked") if r.get("reason") == "unbooked"]
    ck(_v_udc["raised"] is None and len(_v_udcb) == 1
       and str(_v_udcb[0].get("why")).startswith("day:")
       and _v_udc0["raised"] is None and not _kinds(_v_udc0, "entries_blocked")
       and [r for r in _kinds(_v_udc0, "unbooked") if r.get("what") == "provisional"],
       "v-0925v unbooked DRIVEN: the DAY cap sees the provisional loss -- $2 "
       "lost earlier today plus the parked $4.97 reach the -$6 stop the run "
       "alone does not (%r); with nothing on file the same world blocks nothing"
       % ([r.get("why") for r in _v_udcb],))
    # a HEDGED pair parked together counts what the PAIR can lose
    _v_upp = _offline_trade_loop([_k1_A(collapse_at=4)], live=True, run_s=120.0,
                                 flags=dict(_v_ubf), settle=_v_settle("closed"))
    _v_uppr = [r for r in _kinds(_v_upp, "unbooked", _kA) if r.get("what") == "provisional"]
    ck(_v_upp["raised"] is None and abs(_hedged(_v_upp, _kA) - 5.0) < 1e-9
       and len(_v_uppr) == 1 and _v_uppr[0].get("legs") == 2
       and -1.5 < float(_v_uppr[0].get("worst")) < 0.0,
       "v-0925v unbooked DRIVEN: a 98c leg parked WITH its cover counts what the "
       "pair can lose together ($%s over %s legs), not each leg's full cost "
       "(about -$5.2)" % ((_v_uppr[0].get("worst") if _v_uppr else None),
                         (_v_uppr[0].get("legs") if _v_uppr else None)))
    # the SIZER is not frozen by a parked leg (review: up to 6 h without a
    # balance read): reads resume once the leg is parked
    _v_szb = _v_reads()
    _v_sz = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=120.0,
                                bank=_v_szb, settle=_v_settle("closed"),
                                flags=dict(_v_ubf, AUTO_SIZE_EVERY_S=5))
    ck(_v_sz["raised"] is None and _v_szb.reads and _v_szb.reads[0] < 1.0
       and not [t for t in _v_szb.reads if 1.0 < t < 89.0]
       and [t for t in _v_szb.reads if t >= 90.0],
       "v-0925v unbooked DRIVEN: the sizer reads the bank again once a stuck leg "
       "is parked (reads at %s; none while it was really held, as before)"
       % ([round(t, 1) for t in _v_szb.reads][:8],))
    # booked on DETERMINED, paid later: the sizer waits for finalized, and a
    # final result other than the one booked is CORRECTED
    _v_dpb = _v_reads()
    _v_dp = _offline_trade_loop(
        [_k1_A(collapse_at=None)], live=True, run_s=110.0, bank=_v_dpb,
        flags={"AUTO_SIZE_EVERY_S": 5},
        settle=_v_settle("determined", "yes", until=70.0,
                         then={"status": "finalized", "result": "no"}))
    _v_dps = _kinds(_v_dp, "settled", _kA)
    _v_dpc = _kinds(_v_dp, "settle_changed", _kA)
    _v_dpw = (_v_dps[0]["t"] if _v_dps else 0.0)
    _v_dpx = (_v_dpc[0]["t"] if _v_dpc else 0.0)
    # the contracts bought (the sizer may have moved the size off 5): a YES
    # booked as won and finally lost is worth exactly $1 a contract less
    _v_dpn = sum(float(p.get("count")) for p in _v_posts(_v_dp, _kA, "bid"))
    ck(_v_dp["raised"] is None and len(_v_dps) == 1 and _v_dps[0].get("result") == "yes"
       and _v_dpn > 0
       and len(_v_dpc) == 1 and _v_dpc[0].get("was") == "yes"
       and _v_dpc[0].get("final") == "no" and _v_dpc[0].get("corrected") is True
       and abs(float(_v_dpc[0].get("delta_c")) + 100.0 * _v_dpn) < 1e-6
       and abs(float(_v_dpc[0].get("day_realised"))
               - (float(_v_dps[0]["day_realised"]) - _v_dpn)) < 1e-6
       and abs(float(_v_dpc[0].get("realised")) - float(_v_dpc[0]["day_realised"])) < 1e-6
       and not [t for t in _v_dpb.reads if _v_dpw + 0.5 < t < _v_dpx - 0.5]
       and [t for t in _v_dpb.reads if t >= _v_dpx - 1e-9],
       "v-0925v unbooked DRIVEN: booked on determined (t %s) the sizer does not "
       "read the bank until Kalshi calls it finalized (t %s; reads %s), and the "
       "final NO where YES was booked is corrected in the run and the day file "
       "(%s c, day %s)"
       % (_v_dpw, _v_dpx, [round(t, 1) for t in _v_dpb.reads][:8],
          (_v_dpc[0].get("delta_c") if _v_dpc else None),
          (_v_dpc[0].get("day_realised") if _v_dpc else None)))
    # the late poll WAITS while another held market is in its last 90 s (it
    # is a blocking GET above the hedge pass): A closes at 30 and is parked at
    # 40; A2 (its close planted at 80) is bought at 50 -- no read of A from
    # then until A2's close
    _v_hwc = []
    _v_hw = _offline_trade_loop(
        [_k1_A(collapse_at=None),
         _v_A(2, collapse_at=None, decided_at=50,
              close_time=_REAL_TIME.strftime("%Y-%m-%dT%H:%M:%SZ",
                                             _REAL_TIME.gmtime(_v_close + 50)))],
        live=True, run_s=110.0,
        flags={"UNBOOKED_AFTER_S": 10.0, "UNBOOKED_POLL_S": 5.0},
        settle=_v_settle("closed", calls=_v_hwc))
    _v_hwA2 = _v_posts(_v_hw, "KXA215M-K1", "bid")
    _v_hwt0 = (min(p["_t"] for p in _v_hwA2) if _v_hwA2 else None)
    ck(_v_hw["raised"] is None and _v_hwA2 and 45.0 <= _v_hwt0 <= 52.0
       and [t for t in _v_hwc if 40.0 <= t < _v_hwt0]
       and not [t for t in _v_hwc if _v_hwt0 + 0.5 < t < 80.0 - 0.5]
       and [t for t in _v_hwc if t >= 80.0],
       "v-0925v unbooked DRIVEN: the parked market's late reads (%s) skip the "
       "last 90 s of another held market (bought at t %s, closing at 80) and "
       "go on after it" % ([round(t, 1) for t in _v_hwc][:12], _v_hwt0))
    _v_rc = _v_tl[_v_tl.index("    def reconcile():"):_v_tl.index("    def report_closes(")]
    ck("close_s + 900" not in _v_rc
       and "_vst, res = settle_read(m, tk)" in _v_rc
       and "_ub_park(_oid, tk, cost, nfill)" in _v_rc
       and _v_rc.count("_count_market(close_s, tk, None)") == 1
       and _v_rc.count("_release(_oid, tk, cost, nfill)") == 2
       and _v_rc.rstrip().endswith("_ub_update()                     # v-0925v unbooked: the provisional loss")
       and "_ub_unpaid_poll()" in _v_rc,
       "v-0925v unbooked by source: reconcile no longer gives a leg up 900 s "
       "after its close (it parks it), reads the status through settle_read, "
       "releases only a booked or void leg, re-reads an unpaid booking and "
       "recomputes the provisional loss last")

    # ---- hedgefail -----------------------------------------------------
    # A: YES at t 0, belief collapses at t 4, so its NO hedge goes out every
    # second; B: undecided until t 8, then a 93c buy. A planted Kalshi
    # rejects A's hedge (400) -- every time, or the first three only.
    # v-0925v D5 (round 4, reworded): hedge_broken now needs its failures on
    # TWO markets, so these worlds hold A2 as well (also collapsing at t 4,
    # its hedge rejected the same way; the close budget raised to three legs)
    # -- one market's loop alone is the D5 (round 4) check's world.
    _v_hfmk = [_k1_A(collapse_at=4), _v_A(2), _k1_B(1, decided_at=8)]

    def _v_hf_reply(n_fail):
        _c = {"n": 0}

        def _r(body, n):
            if body.get("ticker") in (_kA, "KXA215M-K1") and body.get("side") == "ask":
                _c["n"] += 1
                if n_fail is None or _c["n"] <= n_fail:
                    return 400, ('{"error": {"code": "invalid_parameters", '
                                 '"message": "planted hedge rejection"}}')
            return _fill_all(body, n)
        return _r
    _v_h1 = _offline_trade_loop(list(_v_hfmk), live=True, run_s=16.0,
                                reply=_v_hf_reply(None), flags={"MAX_PER_CLOSE": 3})
    _v_h1f = _kinds(_v_h1, "hedge_fail", _kA)
    _v_h1b = _kinds(_v_h1, "hedge_broken")
    ck(_v_h1["raised"] is None and len(_v_posts(_v_h1, _kA, "ask")) >= 5
       and len(_v_h1f) == 1 and _v_h1f[0].get("status_code") == 400
       and "invalid_parameters" in str(_v_h1f[0].get("body"))
       and _v_h1f[0].get("tau") is not None
       and len(_v_h1b) == 1 and int(_v_h1b[0].get("streak") or 0) == HEDGE_FAIL_BLOCK
       and sorted(_v_h1b[0].get("markets") or []) == sorted([_kA, "KXA215M-K1"])
       and not _v_posts(_v_h1, _v_kB)
       and _hedged(_v_h1, _kA) == 0.0,
       "v-0925v hedgefail DRIVEN: a hedge Kalshi rejects 400 is still re-sent "
       "every second (%d sends) but now says so -- ONE hedge_fail (status %s, "
       "body %r) -- and at %d in a row ON TWO MARKETS (round 4) hedge_broken "
       "blocks NEW entries: B's 93c buy at t 8 is never sent (%d B posts)"
       % (len(_v_posts(_v_h1, _kA, "ask")),
          (_v_h1f[0].get("status_code") if _v_h1f else None),
          (str(_v_h1f[0].get("body"))[:50] if _v_h1f else None),
          HEDGE_FAIL_BLOCK, len(_v_posts(_v_h1, _v_kB))))
    _v_h2 = _offline_trade_loop(list(_v_hfmk), live=True, run_s=16.0,
                                reply=_v_hf_reply(3), flags={"MAX_PER_CLOSE": 3})
    _v_h2r = _v_ts(_v_h2, "entries_resumed", reason="hedge_broken")
    ck(_v_h2["raised"] is None and len(_kinds(_v_h2, "hedge_broken")) == 1
       and len(_v_h2r) == 1 and abs(_hedged(_v_h2, _kA) - 5.0) < 1e-9
       and abs(_hedged(_v_h2, "KXA215M-K1") - 5.0) < 1e-9
       and _v_posts(_v_h2, _v_kB)
       and min(p["_t"] for p in _v_posts(_v_h2, _v_kB)) >= _v_h2r[0] - 1e-9,
       "v-0925v hedgefail DRIVEN: three rejections then a hedge that FILLS -- "
       "the block clears the moment a hedge send comes back 2xx (resumed at "
       "%s), A is covered (%g) and B is bought after it"
       % (_v_h2r, _hedged(_v_h2, _kA)))
    _v_h4 = _offline_trade_loop(list(_v_hfmk), live=True, run_s=40.0,
                                reply=_v_hf_reply(None),
                                flags={"HEDGE_BROKEN_HOLD_S": 5.0, "MAX_PER_CLOSE": 3})
    _v_h4r = [r for r in _kinds(_v_h4, "entries_resumed")
              if r.get("reason") == "hedge_broken"]
    ck(_v_h4["raised"] is None and len(_v_h4r) == 1
       and _v_h4r[0]["t"] >= 30.0 + 5.0 - 0.1
       and "retrying normally" in str(_v_h4r[0].get("why"))
       and not _v_posts(_v_h4, _v_kB),
       "v-0925v hedgefail DRIVEN: with no hedge send ever succeeding the block "
       "lasts the rest of that close and the next (hold shrunk to 5 s here: "
       "lifted at t %s, after the close at 30), then the bot retries normally"
       % ([r["t"] for r in _v_h4r],))
    _v_h3 = _offline_trade_loop([_k1_A(collapse_at=4), _k1_B(1, decided_at=8)],
                                live=True, run_s=16.0)
    ck(_v_h3["raised"] is None and not _kinds(_v_h3, "hedge_fail")
       and not _kinds(_v_h3, "hedge_broken") and abs(_hedged(_v_h3, _kA) - 5.0) < 1e-9
       and _v_posts(_v_h3, _v_kB),
       "v-0925v hedgefail NULL: hedges Kalshi accepts write no hedge_fail and "
       "block nothing: A covered (%g), B bought (%d posts)"
       % (_hedged(_v_h3, _kA), len(_v_posts(_v_h3, _v_kB))))
    # 503 and -1 (a timeout: the commonest real failure) answers COUNT -- and
    # are never read as a success that clears a block. Each is counted
    # covered (K2) and not resent, so three markets (the close budget raised
    # to three legs) give the three in a row.
    def _v_hf_answer(st_, body_):
        def _r(body, n):
            if str(body.get("ticker", "")).startswith("KXA") and body.get("side") == "ask":
                return st_, body_
            return _fill_all(body, n)
        return _r
    _v_h5 = {}
    for _v_case, _v_ans in (("503", (503, "Service Unavailable")),
                            ("-1", (-1, "planted: read timed out"))):
        _v_h5[_v_case] = _offline_trade_loop(
            [_v_A(1), _v_A(2), _v_A(3)], live=True, run_s=14.0,
            reply=_v_hf_answer(*_v_ans), flags={"MAX_PER_CLOSE": 3})
    _v_real_take = pintake.take

    def _v_refuse_hedges(*_a, **_k):
        if _k.get("hedge"):
            return {"refused": ["planted: refused by a rail"], "status_code": None}
        return _v_real_take(*_a, **_k)
    _v_h5["refused"] = _offline_trade_loop(
        list(_v_hfmk), live=True, run_s=14.0, take=_v_refuse_hedges,
        flags={"MAX_PER_CLOSE": 3})
    _v_h5b = {k: _kinds(v, "hedge_broken") for k, v in _v_h5.items()}
    ck(all(v["raised"] is None for v in _v_h5.values())
       and all(len(b) == 1 and int(b[0].get("streak") or 0) == HEDGE_FAIL_BLOCK
               for b in _v_h5b.values())
       and _v_h5b["503"][0].get("status_code") == 503
       and _v_h5b["-1"][0].get("status_code") == -1
       and _v_h5b["refused"][0].get("status_code") is None
       and not any(_v_posts(v, _v_kB) for v in _v_h5.values())
       and not any(_v_ts(v, "entries_resumed", reason="hedge_broken")
                   for v in _v_h5.values()),
       "v-0925v hedgefail DRIVEN: hedge answers of 503, -1 (timed out) and a "
       "pintake REFUSAL (status None) each count -- hedge_broken at %d in a row "
       "(%r) -- and none of them clears the block"
       % (HEDGE_FAIL_BLOCK, {k: [r.get("status_code") for r in b]
                             for k, b in _v_h5b.items()}))
    # IN A ROW: fail, fail, a fill (A), then one more failure (A2) is not a
    # block -- a success ends the streak
    def _v_hf_mixed():
        _c = {}

        def _r(body, n):
            tk = body.get("ticker")
            if body.get("side") == "ask" and tk in (_kA, "KXA215M-K1"):
                _c[tk] = _c.get(tk, 0) + 1
                if _c[tk] <= (2 if tk == _kA else 1):
                    return 400, '{"error": {"code": "invalid_parameters"}}'
            return _fill_all(body, n)
        return _r
    _v_h6 = _offline_trade_loop([_k1_A(collapse_at=4), _v_A(2, collapse_at=9)],
                                live=True, run_s=18.0, reply=_v_hf_mixed())
    ck(_v_h6["raised"] is None and not _kinds(_v_h6, "hedge_broken")
       and len(_kinds(_v_h6, "hedge_fail")) == 2
       and abs(_hedged(_v_h6, _kA) - 5.0) < 1e-9
       and abs(_hedged(_v_h6, "KXA215M-K1") - 5.0) < 1e-9
       and not _v_ts(_v_h6, "entries_blocked", reason="hedge_broken"),
       "v-0925v hedgefail DRIVEN: two rejections, a fill, then one more "
       "rejection on another market is NOT three in a row: no hedge_broken "
       "(%d hedge_fail), both covered, nothing blocked"
       % len(_kinds(_v_h6, "hedge_fail")))
    _v_hs = _v_tl[_v_tl.index("_ht_send_ms = int(round(time.time() * 1000.0))"):
                  _v_tl.index("_hfilled = float(_hout.get(\"filled\") or 0)")]
    ck(_v_hs.count("_hf_note(") == 2 and "_hf_result(_hcs, _htk, _hout, _htau)" in _v_tl
       and "_hf_result(_hcs, _htk, _hxout, _htau)" in _v_tl
       and _v_tl.index("_hsc = _hout.get(\"status_code\")")
       < _v_tl.index("_hf_result(_hcs, _htk, _hout, _htau)")
       and "if entry_blocks:\n            _mk = []" in _v_tl,
       "v-0925v hedgefail by source: an exception and a refusal at the hedge "
       "send are counted, every answered hedge (the extra leg's too) is judged "
       "2xx-or-not, and a block empties the scan the way K1's stop does (never "
       "the hedge pass)")

    # ---- hedgeexi ------------------------------------------------------
    def _v_xm(exi):
        m = _k1_A(collapse_at=4)
        m["exi"] = exi
        return m
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    _v_x1 = _offline_trade_loop([_v_xm(1)], live=True, run_s=12.0)
    _v_x2 = _offline_trade_loop([_v_xm(None)], live=True, run_s=12.0)
    _v_x2s = [r for r in _kinds(_v_x2, "api_shape") if r.get("field") == "exchange_index"]
    ck(_v_x1["raised"] is None and _v_posts(_v_x1, _kA, "bid") and _v_posts(_v_x1, _kA, "ask")
       and all(p.get("exchange_index") == 1 for p in _v_posts(_v_x1, _kA))
       and abs(_hedged(_v_x1, _kA) - 5.0) < 1e-9
       and _v_x2["raised"] is None and _v_posts(_v_x2, _kA, "ask")
       and all(p.get("exchange_index") == 2 for p in _v_posts(_v_x2, _kA))
       and len(_v_x2s) == 1 and _v_x2s[0].get("what") == "missing"
       and _v_x2s[0].get("endpoint") == "/markets"
       and hedge_exchange_index("KXBTC15M-26NOV071715-15", None, None, None) == 2
       and hedge_exchange_index("KXFOO-1", None, crypto=False) == 0
       and hedge_exchange_index("T", (1, 2, 3, 4, 0)) == 0
       and hedge_exchange_index("T", None, (1, 2, 3, 4, 5)) == 5,
       "v-0925v hedgeexi DRIVEN: the hedge goes to the market's OWN "
       "exchange_index, the value its entry used (planted shard 1: posts %s), "
       "not a hard-coded 2; a row missing it is the crypto shard 2 for entry "
       "and hedge alike, never 0, recorded once (%d api_shape)"
       % ([p.get("exchange_index") for p in _v_x1["posts"]], len(_v_x2s)))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    # the EXTRA (odds) leg rides the same shard, and its answer is judged too
    def _v_xx_run(reply_):
        _sv = (pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT)
        try:
            pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT = 1e6, -1e9
            return _offline_trade_loop([_v_xm(1)], live=True, reply=reply_,
                                       flags=_ox_on)
        finally:
            pintake.MAX_RUN_STAKE, pintake.LOSS_ABORT = _sv

    def _v_xx_reject_extra():
        _c = {"n": 0}

        def _r(body, n):
            if body.get("ticker") == _kA and body.get("side") == "ask":
                _c["n"] += 1
                if _c["n"] == 2:
                    return 400, '{"error": {"code": "invalid_parameters", "message": "planted extra rejection"}}'
            return _fill_all(body, n)
        return _r
    _v_xx1 = _v_xx_run(_fill_all)
    _v_xx2 = _v_xx_run(_v_xx_reject_extra())
    _v_xx2f = _kinds(_v_xx2, "hedge_fail", _kA)
    ck(_v_xx1["raised"] is None and len(_v_posts(_v_xx1, _kA)) == 3
       and len(_kinds(_v_xx1, "hedge_extra", _kA)) == 1
       and all(p.get("exchange_index") == 1 for p in _v_posts(_v_xx1, _kA))
       and _v_xx2["raised"] is None and abs(_hedged(_v_xx2, _kA) - 5.0) < 1e-9
       and len(_v_xx2f) == 1 and _v_xx2f[0].get("status_code") == 400
       and not _kinds(_v_xx2, "hedge_broken"),
       "v-0925v hedgeexi/hedgefail DRIVEN: the extra (odds) leg goes to the "
       "market's own shard as well (posts %s), and an extra Kalshi rejects 400 "
       "is a hedge_fail like the cover's (%d; one alone blocks nothing)"
       % ([p.get("exchange_index") for p in _v_xx1["posts"]], len(_v_xx2f)))

    # ---- universe: pure ------------------------------------------------
    _v_ct = calendar.timegm((2026, 11, 7, 13, 15, 0))
    ck(parse_close_time("2026-11-07T13:15:00Z") == _v_ct
       == calendar.timegm(_REAL_TIME.strptime("2026-11-07T13:15:00Z", "%Y-%m-%dT%H:%M:%SZ"))
       and parse_close_time("2026-11-07T13:15:00.000Z") == _v_ct
       and parse_close_time("2026-11-07T13:15:00.123456Z") == _v_ct
       and parse_close_time("2026-11-07T08:15:00-05:00") == _v_ct
       and parse_close_time("2026-11-07T13:15:00+00:00") == _v_ct
       and parse_close_time("2026-11-07T14:15:00+0100") == _v_ct
       and parse_close_time("2026-11-07T13:15:00") is None
       and parse_close_time("2026-11-07T13:15:00.Z") is None
       and parse_close_time("2026-13-07T13:15:00Z") is None
       and parse_close_time("garbage") is None and parse_close_time(None) is None,
       "v-0925v universe: close_time parses exactly as the strict format did and "
       "ALSO with fractional seconds and +00:00 / -05:00 / +0100 offsets; no "
       "zone, a bad month or garbage is None, never an exception")
    _v_rows = ([{"ticker": "S-F%d" % k, "close_time": _REAL_TIME.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", _REAL_TIME.gmtime(_v_close + 900 * k)),
                 "floor_strike": 1.0, "exchange_index": 2} for k in (4, 3, 2, 1)]
               + [{"ticker": "S-BAD", "close_time": "not a time", "floor_strike": 1.0},
                  {"ticker": "S-STR", "close_time": _v_iso, "floor_strike": "abc"},
                  "junk",
                  {"ticker": "S-NOW", "close_time": _v_iso[:-1] + ".000Z",
                   "floor_strike": 100.12, "status": "active",
                   "custom_strike": {"floor_strike": "100.123", "round_digits": 3}}])
    _v_uf = universe_facts(_v_rows, "IID", _v_close - 30, "/markets")
    ck(_v_uf == [("S-NOW", ("IID", _v_close, 100.123, 3, 2))]
       and len(_v_shape("/markets", "close_time", "unparsable")) == 1
       and len(_v_shape("/markets", "floor_strike/round_digits", "unreadable")) == 1
       and len(_v_shape("/markets", "market", "not_an_object")) == 1
       and len(_v_shape("/markets", "exchange_index", "missing")) == 1
       and universe_facts(None, "IID", 0) == [],
       "v-0925v universe: from 8 rows -- four later closes FIRST, a bad "
       "close_time, a bad strike, a non-object -- the market closing next is "
       "the one kept (%r), with its exact custom strike and the crypto shard "
       "for its missing exchange_index; each bad row is skipped and recorded "
       "once" % (_v_uf,))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    _v_uw = universe_facts([{"ticker": "S-W", "close_time": _v_iso, "floor_strike": 1.0,
                             "status": "paused_for_review", "exchange_index": 2}],
                           "IID", _v_close - 30, "/markets")
    _v_ev = events_rows({"events": [{"markets": [
        {"ticker": "E-1", "status": "active"}, {"ticker": "E-2", "status": "closed"},
        {"ticker": "E-3"}, {"ticker": "E-4", "status": "open"}, "junk"]}]})
    ck(_v_uw and len(_v_shape("/markets", "status", "unknown")) == 1
       and [m.get("ticker") for m in _v_ev] == ["E-1", "E-4"]
       and len(_v_shape("/events", "markets[].status", "missing")) == 1
       and events_rows({"x": 1}) == [] and events_rows(None) == [],
       "v-0925v universe: a market status never seen is recorded (the row is "
       "still read); a nested /events market is taken only when its own status "
       "says open -- one with NO status is dropped and recorded (%r)"
       % ([m.get("ticker") for m in _v_ev],))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    ck(kalshi_maintenance(calendar.timegm((2026, 11, 5, 8, 30, 0)))       # Thu 03:30 EST
       and not kalshi_maintenance(calendar.timegm((2026, 11, 5, 7, 30, 0)))   # Thu 02:30 EST
       and kalshi_maintenance(calendar.timegm((2026, 10, 29, 7, 30, 0)))      # Thu 03:30 EDT
       and not kalshi_maintenance(calendar.timegm((2026, 10, 29, 9, 30, 0)))  # Thu 05:30 EDT
       and not kalshi_maintenance(calendar.timegm((2026, 11, 6, 8, 30, 0)))   # Fri
       and not kalshi_maintenance(None)
       and UNI_LIMIT == "20" and '"limit": UNI_LIMIT})' in _v_tl
       and "and not kalshi_maintenance(now)" in _v_tl,
       "v-0925v universe: the /events fallback never fires in Kalshi's Thursday "
       "03:00-05:00 ET maintenance (both sides of the clock change), and the "
       "15M GET asks for 20 rows")

    # ---- universe: DRIVEN ----------------------------------------------
    def _v_cm(close_time):
        m = _k1_A(collapse_at=None)
        m["close_time"] = close_time
        return m
    _v_c = {"tk": "KXCCC15M-K1", "series": "KXCCC15M", "iid": "K1C",
            "strike": 100.0, "fair": (lambda t: 0.5),
            "book": (lambda t: _ob(0.50, 0.49)), "close_time": "garbage"}
    _v_u1 = _offline_trade_loop([_v_c, _v_cm(_v_iso[:-1] + ".000Z")], live=True,
                                run_s=6.0)
    _v_u1s = [r for r in _kinds(_v_u1, "api_shape") if r.get("field") == "close_time"]
    ck(_v_u1["raised"] is None and _v_posts(_v_u1, _kA, "bid")
       and not [r for r in _kinds(_v_u1, "error") if r.get("where") == "universe"]
       and len(_v_u1s) == 1 and _v_u1s[0].get("ticker") == "KXCCC15M-K1",
       "v-0925v universe DRIVEN: a close_time with fractional seconds is read "
       "(A bought: %d posts) and ANOTHER series' unparsable one skips that one "
       "market with one api_shape (%d), not the whole refresh (no universe "
       "error)" % (len(_v_posts(_v_u1, _kA, "bid")), len(_v_u1s)))
    _v_u2 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=60.0,
                                tau0=75, events_only=True)
    _v_u2e = _kinds(_v_u2, "universe_empty")
    _v_u2u = _kinds(_v_u2, "universe")
    _v_u2p = _v_posts(_v_u2, _kA, "bid")
    ck(_v_u2["raised"] is None and len(_v_u2e) == 1
       and _v_u2e[0].get("what") == "fallback"
       and int(_v_u2e[0].get("refreshes") or 0) == UNI_EMPTY_REFRESHES
       and any(r.get("source") == "events" for r in _v_u2u)
       and _v_u2p and min(p["_t"] for p in _v_u2p) >= _v_u2e[0]["t"] - 1e-9
       and any(g[0] == "/events" and g[1].get("with_nested_markets") == "true"
               for g in _v_u2["gets"]),
       "v-0925v universe DRIVEN: GET /markets answering EVERY series with an "
       "empty list for %d refreshes switches that refresh to GET /events with "
       "nested markets (universe_empty at t %s, source events), and the market "
       "it finds is traded (first post t %s)"
       % (UNI_EMPTY_REFRESHES, (_v_u2e[0]["t"] if _v_u2e else None),
          (min(p["_t"] for p in _v_u2p) if _v_u2p else None)))
    # ...and while the lists stay empty /events is asked at most once a
    # minute, not on every 20 s refresh (the market closes far beyond the
    # horizon here, so nothing defers the refresh)
    _v_u2c = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=130.0,
                                 tau0=2000, events_only=True)
    _v_u2g = [g[1].get("_t") for g in _v_u2c["gets"] if g[0] == "/events"
              and g[1].get("series_ticker") == "KXAAA15M"]
    _v_u2r = [g[1].get("series_ticker") for g in _v_u2c["gets"] if g[0] == "/markets"]
    ck(_v_u2c["raised"] is None and len(_v_u2g) == 2 and len(_v_u2r) >= 6
       and all(b - a >= UNI_EVENTS_EVERY_S - 0.5 for a, b in zip(_v_u2g, _v_u2g[1:]))
       and len(_kinds(_v_u2c, "universe_empty")) == 1,
       "v-0925v universe DRIVEN: through %d empty refreshes /events is asked "
       "once a minute (at %s), and universe_empty is written once per streak"
       % (len(_v_u2r), _v_u2g))
    _v_u3 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=60.0,
                                tau0=75)
    ck(_v_u3["raised"] is None and not _kinds(_v_u3, "universe_empty")
       and all(r.get("source") == "markets" for r in _kinds(_v_u3, "universe"))
       and not [g for g in _v_u3["gets"] if g[0] == "/events"]
       and _v_posts(_v_u3, _kA, "bid"),
       "v-0925v universe NULL: a /markets that answers is the only path used "
       "(no universe_empty, no /events GET) and the same market is traded")
    # an OUTAGE is not an empty list: every GET /markets 500 -> no fallback
    _v_u4 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=90.0,
                                tau0=100, get_fail_after=0.0)
    ck(_v_u4["raised"] is None and not _kinds(_v_u4, "universe_empty")
       and not [g for g in _v_u4["gets"] if g[0] == "/events"]
       and [r for r in _v_u4["recs"] if r["kind"] == "skip"
            and str(r.get("why")).startswith("universe_http_")],
       "v-0925v universe DRIVEN: refreshes where /markets FAILS (500) are not "
       "empty lists: no /events fallback, which would only add signed GETs to "
       "a host already failing")
    # the empty count RESETS when rows come back: empty refreshes at 0, 20,
    # 40, 60 (fallback at 40), rows at 80, empty again from 100 -- the next
    # streak starts from one, so no second fallback by 130
    _v_u5 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=130.0,
                                tau0=2000,
                                events_only=(lambda t: t < 70.0 or t >= 90.0))
    _v_u5g = [g[1].get("_t") for g in _v_u5["gets"] if g[0] == "/events"
              and g[1].get("series_ticker") == "KXAAA15M"]
    _v_u5r = [r for r in _kinds(_v_u5, "universe_empty") if r.get("what") == "recovered"]
    ck(_v_u5["raised"] is None and len(_v_u5g) == 1 and _v_u5g[0] < 70.0
       and len(_v_u5r) == 1,
       "v-0925v universe DRIVEN: rows coming back reset the empty-refresh count "
       "(recovered once) -- the next empty stretch needs %d refreshes again, so "
       "/events is asked only at %s" % (UNI_EMPTY_REFRESHES, _v_u5g))
    # Kalshi's own row LIMIT: four later closes listed before the market
    # closing now -- limit 4 (the old ask) would never have seen it
    _v_dec = [{"tk": "KXAAA15M-D%d" % k, "series": "KXAAA15M", "iid": "K1A",
               "strike": 100.0, "fair": (lambda t: 0.5),
               "book": (lambda t: _ob(0.50, 0.49)),
               "close_time": _REAL_TIME.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                 _REAL_TIME.gmtime(_v_close + 900 * k))}
              for k in (4, 3, 2, 1)]
    _v_u6 = _offline_trade_loop(_v_dec + [_k1_A(collapse_at=None)], live=True, run_s=6.0)
    ck(_v_u6["raised"] is None and _v_posts(_v_u6, _kA, "bid")
       and all(g[1].get("limit") == UNI_LIMIT for g in _v_u6["gets"]
               if g[0] == "/markets" and g[1].get("series_ticker") == "KXAAA15M"),
       "v-0925v universe DRIVEN: with Kalshi answering in ITS order and "
       "honouring the row limit, the market closing now listed FIFTH is still "
       "found and traded (limit %s)" % UNI_LIMIT)

    # ---- expiry --------------------------------------------------------
    # A: YES at t 0, close at 30, belief collapses at 27 -- AFTER --minutes
    # runs out at 25; Kalshi settles NO. B: decided at 26, after the end.
    _v_e1 = _offline_trade_loop([_k1_A(collapse_at=27), _k1_B(1, decided_at=26)],
                                live=True, run_s=25.0, expiry=True,
                                result={_kA: "no", _v_kB: "yes"})
    _v_e1x = _kinds(_v_e1, "expiry_exit")
    _v_e1h = _kinds(_v_e1, "hedge", _kA)
    ck(_v_e1["raised"] is None and len(_kinds(_v_e1, "expiry_drain")) == 1
       and _kinds(_v_e1, "expiry_drain")[0]["t"] >= 25.0 - 1e-9
       and not _v_posts(_v_e1, _v_kB)
       and _v_e1h and all(float(r["t"]) >= 25.0 for r in _v_e1h)
       and abs(_hedged(_v_e1, _kA) - 5.0) < 1e-9
       and len(_kinds(_v_e1, "settled", _kA)) == 2
       and len(_v_e1x) == 1 and _v_e1x[0].get("flat") is True
       and 50.0 <= _v_e1["ran_s"] <= 25.0 + EXPIRY_GRACE_S,
       "v-0925v expiry DRIVEN: once --minutes has run out nothing is bought (B "
       "at t 26 not sent), and the run does NOT exit holding A: it hedges A's "
       "collapse at t 27 (%g), books both legs and exits FLAT (ran %.1f of "
       "25 s, expiry_exit flat %s)"
       % (_hedged(_v_e1, _kA), _v_e1["ran_s"],
          (_v_e1x[0].get("flat") if _v_e1x else None)))
    _v_e1b = _offline_trade_loop([_k1_A(collapse_at=None), _k1_B(1, decided_at=20)],
                                 live=True, run_s=25.0, expiry=True,
                                 result={_kA: "yes", _v_kB: "yes"})
    ck(_v_e1b["raised"] is None and _v_posts(_v_e1b, _v_kB, "bid")
       and EXPIRY_DRAIN_S == 0.0,
       "v-0925v expiry: nothing is given up BEFORE the end (EXPIRY_DRAIN_S 0; "
       "the review priced 20 min at ~$1.50 a run): B decided at t 20 of 25 is "
       "bought")
    _v_e2 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=25.0,
                                expiry=True, flags={"EXPIRY_GRACE_S": 40.0})
    _v_e2x = _kinds(_v_e2, "expiry_exit")
    ck(_v_e2["raised"] is None and len(_v_e2x) == 1
       and _v_e2x[0].get("flat") is False and "grace" in str(_v_e2x[0].get("why"))
       and 64.9 <= _v_e2["ran_s"] <= 66.0,
       "v-0925v expiry DRIVEN: a position that never settles holds the run at "
       "most the grace past the end (40 s here, 30 min live): ran %.1f s, "
       "expiry_exit %r" % (_v_e2["ran_s"], (_v_e2x[0].get("why") if _v_e2x else None)))
    # an entry whose answer was LOST (-1): nothing in open_pos, the order
    # still unknown on Kalshi -- the run must not end calling itself flat
    def _v_lost_entry(body, n):
        if body.get("ticker") == _kA and body.get("side") == "bid":
            return -1, "planted: read timed out"
        return _fill_all(body, n)
    _v_e4 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=25.0,
                                expiry=True, reply=_v_lost_entry,
                                flags={"EXPIRY_GRACE_S": 40.0})
    _v_e4x = _kinds(_v_e4, "expiry_exit")
    ck(_v_e4["raised"] is None and len(_v_e4x) == 1
       and _v_e4x[0].get("flat") is False and _v_e4["ran_s"] >= 64.9,
       "v-0925v expiry DRIVEN: an entry whose answer was lost (unknown on "
       "Kalshi, nothing on our books) keeps the run alive to the grace (ran "
       "%.1f s, flat %s) -- it is not read as flat"
       % (_v_e4["ran_s"], (_v_e4x[0].get("flat") if _v_e4x else None)))
    _v_e3 = _offline_trade_loop([_k1_B(1, decided_at=999)], live=True, run_s=25.0,
                                expiry=True)
    _v_e3x = _kinds(_v_e3, "expiry_exit")
    _v_e0 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=25.0)
    ck(_v_e3["raised"] is None and len(_v_e3x) == 1 and _v_e3x[0].get("flat") is True
       and 25.0 <= _v_e3["ran_s"] <= 25.2
       and _v_e0["raised"] is None and 25.0 <= _v_e0["ran_s"] <= 25.2
       and not _kinds(_v_e0, "expiry_exit") and not _kinds(_v_e0, "expiry_drain")
       and 'bool(getattr(a, "expiry_drain", True))' in _v_tl
       and "expiry_drain" not in inspect.getsource(main),
       "v-0925v expiry NULL: holding nothing, the run ends ON TIME (%.2f s of "
       "25); the offline worlds' old exit (expiry off) is unchanged (%.2f s); "
       "live runs it on (main never turns it off)"
       % (_v_e3["ran_s"], _v_e0["ran_s"]))

    # ---- startbank -----------------------------------------------------
    _v_s1 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=25.0,
                                bank=(lambda t: None if t < 10.0 else 40.0))
    _v_s1b = [r for r in _kinds(_v_s1, "startup_bank")]
    _v_s1p = _v_posts(_v_s1, _kA, "bid")
    ck(_v_s1["raised"] is None and len(_v_s1b) == 1
       and _v_s1b[0].get("source") == "api" and int(_v_s1b[0].get("tries") or 0) >= 4
       and _v_ts(_v_s1, "entries_blocked", reason="startup_bank")
       and _v_s1p and min(p["_t"] for p in _v_s1p) >= 10.0,
       "v-0925v startbank DRIVEN: the balance read fails at the start -- no "
       "entry until it lands (retried 1, 2, 4, 8 s: %s tries), then trading "
       "starts (first post t %s, the market had been buyable from t 0)"
       % ((_v_s1b[0].get("tries") if _v_s1b else None),
          (min(p["_t"] for p in _v_s1p) if _v_s1p else None)))
    _v_mir = SIZE_MIRROR

    def _v_mirror(bank_, age_s):
        with open(_v_mir, "w", encoding="utf-8") as _fh:
            json.dump({"size": 125.0, "bank": float(bank_), "at": "x",
                       "epoch": _v_close - float(age_s)}, _fh)
    try:
        _v_mirror(1000.0, 190)
        _v_s2 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True,
                                    run_s=80.0, tau0=90,
                                    bank=(lambda t: None),
                                    flags={"LOSS_CAP_FRAC": 0.187})
        _v_mirror(1000.0, 200000)
        _v_s3 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True,
                                    run_s=80.0, tau0=90,
                                    bank=(lambda t: None),
                                    flags={"LOSS_CAP_FRAC": 0.187})
        _v_mirror(20.0, 190)
        _v_s5 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True,
                                    run_s=80.0, tau0=90,
                                    bank=(lambda t: None),
                                    flags={"LOSS_CAP_FRAC": 0.187})
        _v_mirror(1000.0, 190)
        _v_kx_s = _KtEx(_kt_fill, pos0={_ktA: (5.0, 4.75)})
        _v_s6 = _offline_trade_loop([_kt_mkt(None, early=0.999)], live=True,
                                    reply=_v_kx_s.reply, run_s=130.0, tau0=90,
                                    portfolio=_v_kx_s.portfolio,
                                    bank=(lambda t: None), result={_ktA: "yes"},
                                    flags={"LOSS_CAP_FRAC": 0.187})
    finally:
        try:
            os.remove(_v_mir)
        except OSError:
            pass
    _v_s2b = _kinds(_v_s2, "startup_bank")
    _v_s2p = _v_posts(_v_s2, _kA, "bid")
    ck(_v_s2["raised"] is None and len(_v_s2b) == 1
       and _v_s2b[0].get("source") == "mirror" and _v_s2b[0].get("bank") == 1000.0
       and abs(float(_v_s2b[0].get("loss_cap") or 0) - 187.0) < 1e-9
       and float(_v_s2b[0].get("size")) == 5.0
       and _v_s2p and min(p["_t"] for p in _v_s2p) >= STARTUP_BANK_WAIT_S - 1e-9
       and all(p.get("count") == "5.00" for p in _v_s2p),
       "v-0925v startbank DRIVEN: a balance that never reads -- after %g s the "
       "size mirror's own bank ($1000, under 24 h old) sets the day stop "
       "(loss cap $%s) and trading starts (first post t %s) at the SAME size "
       "(%s; the mirror's 125 is never taken up)"
       % (STARTUP_BANK_WAIT_S, (_v_s2b[0].get("loss_cap") if _v_s2b else None),
          (min(p["_t"] for p in _v_s2p) if _v_s2p else None),
          sorted(set(p.get("count") for p in _v_s2p))))
    _v_s3b = _kinds(_v_s3, "startup_bank")
    ck(_v_s3["raised"] is None and len(_v_s3b) == 1
       and _v_s3b[0].get("source") == "none" and not _v_posts(_v_s3, _kA)
       and _v_blocked(_v_s3, "startup_bank"),
       "v-0925v startbank DRIVEN: no balance and a size mirror over 24 h old -- "
       "startup_bank source none and NOTHING is bought (%d posts)"
       % len(_v_posts(_v_s3, _kA)))
    # a block that LASTS says so again every ENTRY_BLOCK_BEAT_S (10 s here),
    # so the tail of the log always shows it; a world with no block writes none
    _v_bt = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=35.0,
                                bank=(lambda t: None), flags={"ENTRY_BLOCK_BEAT_S": 10.0})
    _v_btr = _kinds(_v_bt, "entries_still_blocked")
    ck(_v_bt["raised"] is None and len(_v_btr) >= 2
       and all(r.get("reasons") == ["startup_bank"] for r in _v_btr)
       and all(b["t"] - a["t"] >= 10.0 - 0.2 for a, b in zip(_v_btr, _v_btr[1:]))
       and float(_v_btr[-1].get("blocked_s") or 0) >= 20.0 - 0.5
       and not _kinds(_v_h3, "entries_still_blocked")
       and not _kinds(_v_un, "entries_still_blocked"),
       "v-0925v guard DRIVEN: a block that lasts is written again every beat "
       "(%d entries_still_blocked, blocked %s s at the last), so a reader of "
       "the log's tail never loses it; no block, no beat"
       % (len(_v_btr), (_v_btr[-1].get("blocked_s") if _v_btr else None)))
    _v_s5b = _kinds(_v_s5, "startup_bank")
    _v_s5w = float(min(5.0, size_for_bank(20.0)))
    ck(_v_s5["raised"] is None and _v_s5w < 5.0 and len(_v_s5b) == 1
       and _v_s5b[0].get("source") == "mirror"
       and abs(float(_v_s5b[0].get("size")) - _v_s5w) < 1e-9
       and _v_posts(_v_s5, _kA, "bid")
       and all(abs(float(p.get("count")) - _v_s5w) < 1e-9
               for p in _v_posts(_v_s5, _kA, "bid")),
       "v-0925v startbank DRIVEN: a mirror bank that supports LESS than the "
       "argv's size lowers it (size %g from 5 for a $20 bank) -- the mirror can "
       "only ever bring the size down" % _v_s5w)
    _v_s6b = _kinds(_v_s6, "startup_bank")
    _v_s6s = [r for r in _v_s6["recs"] if r["kind"] == "settled"]
    _v_s6a = _kt_kinds(_v_s6, "ktruth", "adopted")
    ck(_v_s6["raised"] is None and len(_v_s6a) == 1 and _v_s6s
       and len(_v_s6b) == 1 and _v_s6b[0].get("source") == "mirror"
       and _v_s6b[0]["t"] >= max(STARTUP_BANK_WAIT_S, max(r["t"] for r in _v_s6s)) - 1e-9,
       "v-0925v startbank DRIVEN: holding a position (adopted from the account "
       "at the start) the mirror waits until it is booked (mirror at t %s, "
       "booked at t %s): the stop is never re-set under a held bet"
       % ((_v_s6b[0]["t"] if _v_s6b else None),
          ([r["t"] for r in _v_s6s] if _v_s6s else None)))
    _v_s4 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=12.0,
                                bank=40.0)
    ck(_v_s4["raised"] is None and not _kinds(_v_s4, "startup_bank")
       and not _kinds(_v_s4, "entries_blocked") and _v_posts(_v_s4, _kA, "bid")
       and min(p["_t"] for p in _v_posts(_v_s4, _kA, "bid")) < 0.5,
       "v-0925v startbank NULL: a balance that reads at once blocks nothing and "
       "writes nothing -- the first look buys, as before")

    # ---- clockskew -----------------------------------------------------
    _v_ix = IndexWS(["BRTI"])
    _v_b0 = 1_700_000_000_000
    for _i in range(30):
        _v_ix.on_frame(json.dumps({"type": "cfbenchmarks_value", "msg": {
            "index_id": "BRTI", "data": {"value": 100.0 + _i,
                                         "time": _v_b0 + 1000 * _i}}}),
            _v_b0 + 1000 * _i + 1000)
    _v_ixa = _v_ix.clock_skew_ms(60, now_ms=_v_b0 + 30000)
    _v_ix.on_frame(json.dumps({"type": "cfbenchmarks_value", "msg": {
        "index_id": "BRTI", "data": {"value": 1.0, "time": _v_b0}}}), _v_b0 + 5000)
    _v_ixb = _v_ix.clock_skew_ms(60, now_ms=_v_b0 + 30000)
    _v_iy = IndexWS(["BRTI"])
    for _i in range(25):
        _v_iy.on_frame(json.dumps({"type": "cfbenchmarks_value",
                                   "sending_ts_ms": _v_b0 + 1000 * _i + 60, "msg": {
            "index_id": "BRTI", "data": {"value": 100.0, "time": _v_b0 + 1000 * _i}}}),
            _v_b0 + 1000 * _i + 90)
    _v_iya = _v_iy.clock_skew_ms(60, now_ms=_v_b0 + 25000)
    _v_iyb = _v_iy.clock_skew_ms(5, now_ms=_v_b0 + 200000)
    # a LAGGING feed, not a clock: 15 of 25 prints arrive 900 ms late, the
    # fastest 10 at 60 ms -- the median is 900, the fast end 60
    _v_iz = IndexWS(["BRTI"])
    for _i in range(25):
        _v_iz.on_frame(json.dumps({"type": "cfbenchmarks_value",
                                   "sending_ts_ms": _v_b0 + 1000 * _i, "msg": {
            "index_id": "BRTI", "data": {"value": 100.0, "time": _v_b0 + 1000 * _i}}}),
            _v_b0 + 1000 * _i + (900 if _i % 5 < 3 else 60))
    _v_iza = _v_iz.clock_skew_ms(60, now_ms=_v_b0 + 25000)
    _v_izm = _v_iz.clock_skew_ms(60, now_ms=_v_b0 + 25000, q=0.5)
    # a box clock BEHIND Kalshi's by 1 s
    _v_iw = IndexWS(["BRTI"])
    for _i in range(25):
        _v_iw.on_frame(json.dumps({"type": "cfbenchmarks_value",
                                   "sending_ts_ms": _v_b0 + 1000 * _i, "msg": {
            "index_id": "BRTI", "data": {"value": 100.0, "time": _v_b0 + 1000 * _i}}}),
            _v_b0 + 1000 * _i - 1000 + 80)
    _v_iwa = _v_iw.clock_skew_ms(60, now_ms=_v_b0 + 25000)
    ck(_v_ixa == (1000.0, 30) and _v_ixb == (1000.0, 30)
       and _v_iya == (30.0, 25) and _v_iyb == (None, 0)
       and _v_iza == (60.0, 25) and _v_izm == (900.0, 25)
       and _v_iwa == (-920.0, 25),
       "v-0925v clockskew: the index socket's clock offset is the FAST end of "
       "(receipt - Kalshi stamp): a box 1 s ahead reads 1000 ms over 30 prints "
       "(%r), a revised print of a second already held is ignored, "
       "sending_ts_ms is preferred where the frame has it (%r), a LAGGING feed "
       "reads its fast prints, not its median (%r vs median %r), a box BEHIND "
       "reads negative (%r), and an empty window is no opinion (%r)"
       % (_v_ixa, _v_iya, _v_iza, _v_izm, _v_iwa, _v_iyb))
    _v_k1 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=45.0,
                                tau0=60, skew=(lambda t: (1000.0, 40)),
                                flags={"CLOCK_SKEW_HOLD_S": 10.0})
    _v_k1s = _kinds(_v_k1, "clock_skew")
    ck(_v_k1["raised"] is None and len(_v_k1s) == 1
       and _v_k1s[0].get("offset_ms") == 1000.0 and _v_k1s[0]["t"] >= 10.0 - 1e-9
       and not _v_posts(_v_k1, _kA)
       and _v_blocked(_v_k1, "clock_skew"),
       "v-0925v clockskew DRIVEN: a clock 1000 ms off Kalshi's for the hold "
       "(10 s here, 60 s live) blocks new entries (clock_skew at t %s) and the "
       "market buyable from t 30 is never bought (%d posts)"
       % ((_v_k1s[0]["t"] if _v_k1s else None), len(_v_posts(_v_k1, _kA))))
    _v_k4 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=45.0,
                                tau0=60, skew=(lambda t: (-1000.0, 40)),
                                flags={"CLOCK_SKEW_HOLD_S": 10.0})
    _v_k5 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=45.0,
                                tau0=60, flags={"CLOCK_SKEW_HOLD_S": 10.0},
                                skew=(lambda t: (1000.0, 40) if (t < 8.0 or t >= 10.0)
                                      else (90.0, 40)))
    _v_k5s = _kinds(_v_k5, "clock_skew")
    ck(_v_k4["raised"] is None and len(_kinds(_v_k4, "clock_skew")) == 1
       and not _v_posts(_v_k4, _kA)
       and _v_k5["raised"] is None and len(_v_k5s) == 1
       and _v_k5s[0]["t"] >= 20.0 - 1e-9,
       "v-0925v clockskew DRIVEN: a box clock BEHIND Kalshi's by 1 s blocks "
       "too, and a clock that recovers for 2 s starts the hold again from zero "
       "(blocked at t %s, not 10)" % ((_v_k5s[0]["t"] if _v_k5s else None),))
    _v_k2 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=45.0,
                                tau0=60, flags={"CLOCK_SKEW_HOLD_S": 10.0},
                                skew=(lambda t: (1000.0, 40) if t < 20 else (90.0, 40)))
    _v_k2r = _v_ts(_v_k2, "entries_resumed", reason="clock_skew")
    _v_k3 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=45.0,
                                tau0=60, flags={"CLOCK_SKEW_HOLD_S": 10.0},
                                skew=(lambda t: (90.0, 40) if t < 15 else (1000.0, 5)))
    ck(_v_k2["raised"] is None and len(_v_k2r) == 1 and _v_posts(_v_k2, _kA)
       and min(p["_t"] for p in _v_posts(_v_k2, _kA)) >= _v_k2r[0] - 1e-9
       and _v_k3["raised"] is None and not _kinds(_v_k3, "clock_skew")
       and _v_posts(_v_k3, _kA),
       "v-0925v clockskew: a clock that comes back clears the block (resumed "
       "at %s) and the market is bought; NULL: a 90 ms socket, or a skewed "
       "reading over too few prints, blocks nothing" % (_v_k2r,))

    # ---- the guard itself: a part that RAISES blocks, and clears -------
    def _v_skew_raises(t):
        if t < 5.0:
            raise RuntimeError("planted: the socket's reading raised")
        return 90.0, 40
    _v_g1 = _offline_trade_loop([_k1_A(collapse_at=None), _k1_B(1, decided_at=2)],
                                live=True, run_s=16.0, skew=_v_skew_raises)
    _v_g1e = [r for r in _kinds(_v_g1, "error") if r.get("where") == "guard_clockskew"]
    _v_g1b = [r for r in _kinds(_v_g1, "entries_blocked") if r.get("reason") == "guard_error"]
    _v_g1r = _v_ts(_v_g1, "entries_resumed", reason="guard_error")
    _v_g1p = _v_posts(_v_g1, _v_kB, "bid")
    ck(_v_g1["raised"] is None and len(_v_g1e) == 1 and len(_v_g1b) == 1
       and "clockskew" in (_v_g1b[0].get("parts") or [])
       and len(_v_g1r) == 1 and _v_g1r[0] >= 5.0 + GUARD_ERROR_HOLD_S - 1.1
       and _v_g1p and min(p["_t"] for p in _v_g1p) >= _v_g1r[0] - 1e-9,
       "v-0925v guard DRIVEN: a guard part that RAISES is written once "
       "(error where guard_clockskew), blocks new entries (guard_error) while "
       "it raises and %g s after, then clears (resumed at %s; B bought after)"
       % (GUARD_ERROR_HOLD_S, _v_g1r))

    # ---- logfail -------------------------------------------------------
    _v_td = _v_tf.mkdtemp(prefix="pin0925v-")
    _v_tw = _v_tw2 = None        # round 3: closed in the finally (F2)
    try:
        _v_bad = os.path.join(_v_td, "missing-dir", "pinrun-live-x.jsonl")
        _v_eb = _v_io.StringIO()
        with _v_cl.redirect_stderr(_v_eb):
            _v_w2 = [log_append(_v_bad, {"kind": "x", "n": _i}) for _i in range(LOG_FAIL_BLOCK - 1)]
            _v_f2 = log_writes_failing("log")
            _v_w3 = [log_append(_v_bad, {"kind": "x", "n": LOG_FAIL_BLOCK})]
            _v_f3 = log_writes_failing("log")
            _v_w = _v_w2 + _v_w3 + [log_append(_v_bad, {"kind": "x", "n": 99})]
        _v_fail = log_writes_failing("log")
        _v_ok = log_append(os.path.join(_v_td, "ok.jsonl"), {"kind": "y"})
        _v_clear = not log_writes_failing("log")
        try:
            _v_okt = open(os.path.join(_v_td, "ok.jsonl"), encoding="utf-8").read()
        except OSError:
            _v_okt = ""
        ck(_v_w == [False] * (LOG_FAIL_BLOCK + 1) and _v_f2 is False and _v_f3 is True
           and _v_fail
           and _v_ok and _v_clear
           and _v_eb.getvalue().count("writes in a row FAILED") == 1
           and '"kind": "y"' in _v_okt
           and _LOG_HEALTH["log"]["fails"] >= 4,
           "v-0925v logfail: a decision-log write that fails is COUNTED (it was "
           "swallowed): %d in a row are not yet failing, the %dth is, and ONE "
           "stderr line says so (%d lines); the next write that lands clears it"
           % (LOG_FAIL_BLOCK - 1, LOG_FAIL_BLOCK,
              _v_eb.getvalue().count("writes in a row FAILED")))
        # the trajectory writer counts its failures too (it blocks nothing)
        def _v_bad_open(*_a, **_k):
            raise OSError(28, "planted: No space left on device")
        _v_tp, _v_tw = traj_writer(True, False, _v_td, "live", "V", _open=_v_bad_open)
        with _v_cl.redirect_stderr(_v_io.StringIO()):
            for _i in range(LOG_FAIL_BLOCK):
                _v_tw("traj", n=_i)
        _v_tfail = log_writes_failing("traj")
        _v_tp2, _v_tw2 = traj_writer(True, False, _v_td, "live", "V2")
        _v_tw2("traj", n=1)
        ck(_v_tfail and _LOG_HEALTH["traj"]["fails"] >= LOG_FAIL_BLOCK
           and not log_writes_failing("traj"),
           "v-0925v logfail: the trajectory writer's failures are counted (%d) "
           "and a write that lands clears them" % _LOG_HEALTH["traj"]["fails"])
        _v_dp = os.path.join(_v_td, "sub", "day.json")
        _v_t79 = calendar.timegm((2026, 9, 19, 18, 0, 0))
        _v_d1 = add_day_loss(-50.0, _v_dp, _v_t79)
        _v_dpend = _v_dp in _DAYLOSS_PENDING
        _v_d2 = day_loss(_v_dp, _v_t79)
        _v_d3 = add_day_loss(-30.0, _v_dp, _v_t79)
        _v_r1 = retry_day_loss(_v_dp)
        os.mkdir(os.path.join(_v_td, "sub"))
        _v_r2 = retry_day_loss(_v_dp)
        try:
            _v_onfile = json.load(open(_v_dp, encoding="utf-8"))
        except (OSError, ValueError):
            _v_onfile = {}
        ck(_v_d1 == -50.0 and _v_dpend and _v_d2 == -50.0 and _v_d3 == -80.0
           and _v_r1 is False and _v_r2 is True and _v_dp not in _DAYLOSS_PENDING
           and _v_onfile.get("realised") == -80.0
           and day_loss(_v_dp, _v_t79) == -80.0
           and not os.path.exists(_v_dp + ".tmp")
           and "os.replace(tmp, path)" in inspect.getsource(write_day_loss),
           "v-0925v logfail: a day-loss write that fails is KEPT as pending -- "
           "day_loss reads it (%s), the next settlement adds to it (%s), and once "
           "the disk takes it the file holds -80.00, written atomically (temp "
           "file, fsync, os.replace)" % (_v_d2, _v_d3))
        # a READER holding the file (the phone's stats) is waited out, not a failure
        _v_rp = os.path.join(_v_td, "busy.json")
        _v_osr = os.replace
        _v_rc2 = {"n": 0}

        def _v_flaky_replace(a_, b_):
            _v_rc2["n"] += 1
            if _v_rc2["n"] <= DAYLOSS_REPLACE_TRIES - 1:
                raise PermissionError(13, "planted: the file is open in another process")
            return _v_osr(a_, b_)
        os.replace = _v_flaky_replace
        try:
            _v_wr1 = write_day_loss(_v_rp, {"day": "x", "realised": -1.0})
            _v_rc2["n"] = -100
            _v_wr2 = write_day_loss(_v_rp, {"day": "x", "realised": -2.0})
        finally:
            os.replace = _v_osr
        ck(_v_wr1 is True and _v_wr2 is False
           and json.load(open(_v_rp, encoding="utf-8")).get("realised") == -1.0
           and not os.path.exists(_v_rp + ".tmp"),
           "v-0925v logfail: os.replace refused %d times by a reader holding the "
           "day file still lands on the next try; refused every time it is a "
           "failed write (kept pending by add_day_loss), the old file untouched"
           % (DAYLOSS_REPLACE_TRIES - 1))
    finally:
        # round 3 (11-08, F2): the trajectory writer HOLDS its file open (one
        # handle, flushed once a second -- traj_writer); on Windows a folder
        # with an open file in it cannot be deleted, and rmtree(ignore_errors)
        # silently left one pin0925v- folder in TEMP per self-test, i.e. per
        # live restart on the server. Closed first, then deleted.
        for _v_twx in (_v_tw, _v_tw2):
            try:
                _v_twh = getattr(_v_twx, "handle", None)
                if _v_twh and _v_twh[0] is not None:
                    _v_twh[0].close()
                    _v_twh[0] = None
            except Exception:                            # noqa: BLE001
                pass
        _v_sh.rmtree(_v_td, ignore_errors=True)
        _DAYLOSS_PENDING.clear()
        for _hv in _LOG_HEALTH.values():
            _hv.update(streak=0, fails=0, said=False, err=None)
    ck(not os.path.exists(_v_td),
       "v-0925v logfail: the logfail checks leave NOTHING in TEMP -- the "
       "trajectory writer's held handle is closed before its folder is deleted "
       "(it left one pin0925v- folder behind per self-test: one per live "
       "restart on the server)")

    def _v_lf_book(until):
        def _bk(t):
            if until is None or t < until:
                if not log_writes_failing("log"):
                    for _i in range(LOG_FAIL_BLOCK):
                        log_write_failed("log", OSError(28, "planted: No space left on device"))
            else:
                log_write_ok("log")
            return _ob(0.92, 0.07)
        return _bk
    _v_lfB = _k1_B(1, decided_at=3)
    _v_lfB["book"] = _v_lf_book(None)
    _v_lfB2 = _k1_B(1, decided_at=3)
    _v_lfB2["book"] = _v_lf_book(6.0)
    with _v_cl.redirect_stderr(_v_io.StringIO()):   # the planted failures' stderr line
        _v_l1 = _offline_trade_loop([_v_lfB], live=True, run_s=12.0)
        _v_l2 = _offline_trade_loop([_v_lfB2], live=True, run_s=12.0)
    _v_l2r = _v_ts(_v_l2, "entries_resumed", reason="log_write")
    _v_l0 = _offline_trade_loop([_k1_B(1, decided_at=3)], live=True, run_s=12.0)
    ck(_v_l1["raised"] is None and len(_kinds(_v_l1, "log_write_fail")) == 1
       and not _v_posts(_v_l1, _v_kB)
       and _v_l2["raised"] is None and len(_v_l2r) == 1 and _v_posts(_v_l2, _v_kB)
       and min(p["_t"] for p in _v_posts(_v_l2, _v_kB)) >= _v_l2r[0] - 1e-9
       and _v_l0["raised"] is None and _v_posts(_v_l0, _v_kB)
       and not _kinds(_v_l0, "log_write_fail"),
       "v-0925v logfail DRIVEN: a decision log that cannot be written blocks new "
       "entries (B decided at t 3 never bought; log_write_fail), entries resume "
       "when a write lands (at %s, then B is bought); NULL: a healthy log "
       "blocks nothing" % (_v_l2r,))
    _v_wreal = write_day_loss
    _v_wc = {"n": 0}

    def _v_wflaky(p, d):
        _v_wc["n"] += 1
        return False if _v_wc["n"] <= 3 else _v_wreal(p, d)
    _v_l3 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=60.0,
                                result={_kA: "yes"},
                                flags={"write_day_loss": _v_wflaky})
    _v_l3f = _kinds(_v_l3, "dayloss_write_fail")
    _v_l3r = _v_ts(_v_l3, "entries_resumed", reason="dayloss_write")
    ck(_v_l3["raised"] is None and len(_kinds(_v_l3, "settled", _kA)) == 1
       and len(_v_l3f) == 1 and abs(float(_v_l3f[0].get("realised") or 0) - float(
           _kinds(_v_l3, "settled", _kA)[0]["pnl_c"]) / 100.0) < 1e-4
       and len(_v_l3r) == 1 and _v_l3r[0] > _v_l3f[0]["t"]
       and write_day_loss is _v_wreal,
       "v-0925v logfail DRIVEN: a settlement whose day-loss write fails blocks "
       "new entries (dayloss_write_fail, realised %s) until the retry lands it "
       "(resumed at %s) -- never trading on a stale on-disk cap"
       % ((_v_l3f[0].get("realised") if _v_l3f else None), _v_l3r))

    class _V_BadOut(_v_io.TextIOBase):
        def write(self, s):
            raise OSError(28, "No space left on device")
    _v_pf0 = _PRINT_FAILS[0]
    _v_l4 = _offline_trade_loop([_k1_A(collapse_at=4)], run_s=12.0, stdout=_V_BadOut())
    ck(_v_l4["raised"] is None and abs(_hedged(_v_l4, _kA) - 5.0) < 1e-9
       and not [r for r in _kinds(_v_l4, "error") if r.get("where") in ("hedge", "scan")]
       and not _kinds(_v_l4, "entries_stopped") and _PRINT_FAILS[0] > _v_pf0,
       "v-0925v logfail DRIVEN: with the console raising OSError (a full disk "
       "under `python -u`) the hedge pass still hedges all of A (%g) with no "
       "hedge-step error and no stopped entries; %d prints were dropped"
       % (_hedged(_v_l4, _kA), _PRINT_FAILS[0] - _v_pf0))
    _v_pf1 = _PRINT_FAILS[0]
    _v_mrs = pintake.MAX_RUN_STAKE
    _v_pt, _v_pte = None, None
    try:
        with _v_cl.redirect_stdout(_V_BadOut()):
            _v_pt = pintake.set_limits(max_run_stake=float(pintake.MAX_RUN_STAKE) + 1.0,
                                       why="v-0925v selftest")
    except Exception as _e_pt:                     # noqa: BLE001
        _v_pte = _e_pt
    finally:
        pintake.MAX_RUN_STAKE = _v_mrs
    ck(getattr(pintake, "print", None) is print
       and getattr(pintake.ordercli, "print", None) is print
       and getattr(livebook, "print", None) is print and _v_pt and _v_pte is None
       and _PRINT_FAILS[0] > _v_pf1,
       "v-0925v logfail: pintake, ordercli and livebook print through the same "
       "print that cannot raise -- pintake.set_limits (reached from the sizer) "
       "writes to a failing console without an exception")

    # the sizer RAISING (its first read lands, every later one raises) no
    # longer leaves trade_loop: B, decided at t 6, is still bought
    _v_l5c = {"n": 0}

    def _v_bank_raises(t):
        _v_l5c["n"] += 1
        if _v_l5c["n"] > 1:
            raise OSError(28, "planted: the sizer's path raised")
        return _v_bank5
    _v_l5 = _offline_trade_loop([_k1_B(1, decided_at=6)], live=True, run_s=12.0,
                                bank=_v_bank_raises, flags={"AUTO_SIZE_EVERY_S": 1})
    _v_l5e = [r for r in _kinds(_v_l5, "error") if r.get("where") == "autosize"]
    ck(_v_l5["raised"] is None and len(_v_l5e) == 1
       and (_v_l5["state"] or {}).get("autosize_errors", 0) >= 2
       and _v_posts(_v_l5, _v_kB, "bid"),
       "v-0925v logfail DRIVEN: the sizer raising on every pass no longer "
       "leaves trade_loop -- counted (%s), written once, and B is still bought "
       "when it is decided" % ((_v_l5["state"] or {}).get("autosize_errors"),))

    # ---- importpath ----------------------------------------------------
    _v_here = os.path.normcase(os.path.abspath(HERE))
    _v_mods = {}
    for _m in ("kauth", "pintake", "livebook", "ordercli", "engine", "pinxfer",
               "downtime", "pinflat"):
        _mm = sys.modules.get(_m)
        _v_mods[_m] = (None if _mm is None or not getattr(_mm, "__file__", None)
                       else os.path.normcase(os.path.dirname(os.path.abspath(_mm.__file__))))
    _v_ws = sys.modules.get("websockets")
    _v_tmp = "Temp" + "\\" + "kals-work"
    _v_ins = "sys.path.insert(0, r\"C:\\Users\\Joe\\AppData\\Local\\" + _v_tmp + "\")"
    ck(all(_v == _v_here for _v in _v_mods.values())
       and (_v_ws is None or "kals-work" not in str(getattr(_v_ws, "__file__", "")))
       and _v_ins not in _v_src
       and all(_m in _V_PREIMPORTED for _m in ("pinxfer", "downtime", "pinflat")),
       "v-0925v importpath: the TEMP kals-work folder is no longer put on the "
       "path, every module it could have shadowed resolves from this build's "
       "own folder (%s) or site-packages (websockets), and the lazily imported "
       "ones were loaded at import (%s)"
       % (sorted(_m for _m, _v in _v_mods.items() if _v == _v_here), _V_PREIMPORTED))
    _v_path0 = list(sys.path)
    _v_kid = os.environ.pop("KALSHI_KEY_ID", None)
    try:
        _v_pre = [p for p in sys.path if "kals-work" in os.path.normcase(str(p))]
        _v_ixk = IndexWS(["BRTI"])
        _v_wk = ws_key()
        _v_post = [p for p in sys.path if "kals-work" in os.path.normcase(str(p))]
        sys.path.insert(0, "C:\\x\\Temp\\kals-work")
        _v_scr = scrub_temp_path()
        _v_post2 = [p for p in sys.path if "kals-work" in os.path.normcase(str(p))]
    finally:
        if _v_kid is not None:
            os.environ["KALSHI_KEY_ID"] = _v_kid
        sys.path[:] = _v_path0
    _v_mnk = inspect.getsource(main)
    ck(not _v_pre and not _v_post and _v_scr == 1 and not _v_post2
       and _v_wk[0] == sys.modules["kauth"].KEY_ID and _v_ixk.key_id == _v_wk[0]
       and "book = livebook.LiveBook(key_id=_v_wk[0], key_file=_v_wk[1])" in _v_mnk
       and _v_mnk.index("book = livebook.LiveBook(key_id=") < _v_mnk.index("    scrub_temp_path()")
       < _v_mnk.index("book.start()")
       and "= livebook._default_key()" not in inspect.getsource(IndexWS.__init__)
       and "kid, kfile = ws_key()" in inspect.getsource(IndexWS.__init__),
       "v-0925v importpath: at run time too -- with KALSHI_KEY_ID unset (as the "
       "launcher leaves it) building the index socket adds no kals-work entry "
       "(it takes kauth's key through ws_key, never livebook._default_key), "
       "main() builds the book the same way, and scrub_temp_path takes off one "
       "that something else added")

    # ---- apishape ------------------------------------------------------
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    _v_a1 = api_shape("E", "f", "missing", kind="x", t=1, value=object())
    _v_a2 = api_shape("E", "f", "missing", value=2)
    _v_a3 = api_shape("E", "f", "unknown", value="zz")
    _v_ar = []
    _v_an = api_shape_flush(lambda kind, **kw: _v_ar.append(dict(kw, kind=kind)))
    ck(_v_a1 is True and _v_a2 is False and _v_a3 is True and _v_an == 2
       and len(_v_ar) == 2 and _v_ar[0]["kind"] == "api_shape"
       and (_v_ar[0]["endpoint"], _v_ar[0]["field"], _v_ar[0]["what"]) == ("E", "f", "missing")
       and _v_ar[0].get("kind_") == "x" and _v_ar[0].get("t_") == 1
       and isinstance(_v_ar[0].get("value"), str) and not _API_SHAPE_Q,
       "v-0925v apishape: one record per (endpoint, field, what) for the life "
       "of the process, a detail named kind/t renamed (rec takes kind "
       "positionally), anything not a plain value written as text")
    _v_p1 = ktruth_positions(200, {"positions": []})
    _v_p2 = ktruth_positions(200, {"market_positions": [{"ticker": "T", "pos": 3}]})
    order_shape({"status_code": 201, "status": "weird", "status_source": "response",
                 "parsed": True, "fill_known": True, "remaining": 0.0}, "entry")
    order_shape({"status_code": 201, "status": None, "parsed": True,
                 "fill_known": False, "remaining": None}, "hedge")
    order_shape({"status_code": 400, "status": "weird", "status_source": "response"})
    order_shape({"status_code": 201, "status": "executed", "status_source": "response",
                 "parsed": True, "fill_known": True, "remaining": 0.0})
    _v_lb = livebook.LiveBook(key_id="selftest", key_file="none")
    _v_lbw = book_shape_wrap(_v_lb)
    _v_lb.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 7, "seq": 1, "msg": {
        "market_ticker": "T1", "market_id": "m", "yes_levels": [["0.5000", "3.00"]]}}), 1000)
    _v_lb.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 7, "seq": 2, "msg": {
        "market_ticker": "T2", "market_id": "m",
        "yes_dollars_fp": [["0.4000", "2.00"]], "no_dollars_fp": [["0.5500", "4.00"]]}}), 1001)
    _v_lb.on_frame(json.dumps({"type": "orderbook_delta", "sid": 7, "seq": 3, "msg": {
        "market_ticker": "T2", "price": "0.4000", "delta_fp": "1.00", "side": "yes"}}), 1002)
    _v_q = list(_API_SHAPE_Q)
    _v_qk = sorted((e["endpoint"], e["field"], e["what"]) for e in _v_q)
    _v_lb.on_frame(json.dumps({"type": "orderbook_delta", "sid": 7, "seq": 4, "msg": {
        "market_ticker": "T2", "price_dollars": "0.4000", "side": "yes"}}), 1003)
    _v_lb.on_frame(json.dumps({"type": "orderbook_delta", "sid": 7, "seq": 5, "msg": {
        "market_ticker": "T2", "price_dollars": "0.4000", "delta_fp": "1.00"}}), 1004)
    _v_lbt2 = _v_lb.best("T2") or {}
    _v_qk2 = sorted((e["endpoint"], e["field"], e["what"]) for e in _API_SHAPE_Q)
    ck(_v_p1 is None and _v_p2 == {} and _v_lbw is True
       and ("/portfolio/positions", "market_positions", "missing") in _v_qk
       and ("/portfolio/positions", "position_fp", "missing") in _v_qk
       and (pintake.ENDPOINT, "status", "unknown") in _v_qk
       and (pintake.ENDPOINT, "fill_count", "missing") in _v_qk
       and (pintake.ENDPOINT, "remaining_count", "missing") in _v_qk
       and ("ws orderbook_snapshot", "yes_dollars_fp/no_dollars_fp",
            "absent_with_other_keys") in _v_qk
       and ("ws orderbook_delta", "price_dollars", "missing") in _v_qk
       and len(_v_qk) == 7
       and ("ws orderbook_delta", "delta_fp", "missing") in _v_qk2
       and ("ws orderbook_delta", "side", "missing") in _v_qk2
       and len(_v_qk2) == 9
       and _v_lbt2.get("yes_bid") == 0.4 and _v_lbt2.get("yes_bid_size") == 2.0
       and _v_lbt2.get("no_bid") == 0.55,
       "v-0925v apishape: a positions answer without market_positions or a row "
       "without position_fp, an order status never seen, a 2xx without fill or "
       "remaining counts, a snapshot whose level arrays are renamed and a delta "
       "without price_dollars, delta_fp or side are each recorded once (%d "
       "records); a normal answer records nothing and the wrapped book still "
       "reads its levels (T2 %s / %s)"
       % (len(_v_qk2), _v_lbt2.get("yes_bid"), _v_lbt2.get("no_bid")))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()
    _v_a4 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=4.0,
                                book_stats={"delta_malformed": 3, "bad_level": 0})
    _v_a4s = [r for r in _kinds(_v_a4, "api_shape") if r.get("endpoint") == "ws orderbook"]
    _v_a5 = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=4.0)
    ck(_v_a4["raised"] is None and len(_v_a4s) == 1
       and _v_a4s[0].get("field") == "delta_malformed" and _v_a4s[0].get("count") == 3
       and _v_a5["raised"] is None and not _kinds(_v_a5, "api_shape"),
       "v-0925v apishape DRIVEN: a socket counter of malformed frames that moves "
       "off zero is written once (%r); a clean world writes no api_shape"
       % ([(r.get("field"), r.get("count")) for r in _v_a4s],))
    _API_SHAPE_SEEN.clear()
    _API_SHAPE_Q.clear()

    # ==== v-0925v ROUND 3 (2026-11-08): D2 D4 D5 D6 P7 JS B =================
    # From the verified rule scan (rules1107 REPORT.md sections 2 and 7). Each
    # item gets a DRIVEN world through the real trade_loop where the defect
    # bit and a NULL / CONTROL world where the old behaviour must stay; each
    # message starts "v-0925v <item>" so mutate.py can prove its own checks
    # FAIL with the fix switched off.

    # ---- D2: the brakes see a market's NET, never one leg -----------------
    _v_d2t = calendar.timegm((2026, 11, 2, 12, 30, 0))     # 07:30 ET 11-02
    _v_d2k = (_v_d2t, "KXZEC15M-26NOV020730-30")
    # pure: market_pending prices an unbooked sibling on its market's booked
    # result; no booked result = nothing; a market of an earlier ET day
    # counts against the run only; garbage counts its whole cost
    _v_d2p = market_pending([(_v_d2k[0], _v_d2k[1], "yes", 0.13951, 297.0)],
                            {_v_d2k: "yes"}, _v_d2t + 40)
    _v_d2p0 = market_pending([(_v_d2k[0], _v_d2k[1], "yes", 0.13951, 297.0)],
                             {}, _v_d2t + 40)
    _v_d2py = market_pending([(_v_d2t - 86400, "T-Y", "no", 0.95, 10.0)],
                             {(_v_d2t - 86400, "T-Y"): "yes"}, _v_d2t + 40)
    _v_d2pg = market_pending([(_v_d2t, "T-G", "no", "x", 10.0)],
                             {(_v_d2t, "T-G"): "yes"}, _v_d2t + 40)
    ck(abs(_v_d2p[0] - 253.07) < 0.005 and abs(_v_d2p[1] - 253.07) < 0.005
       and _v_d2p0 == (0.0, 0.0) and market_pending([], {}, _v_d2t) == (0.0, 0.0)
       and abs(_v_d2py[0] + 9.5 + billed_fee(0.95, 10.0)) < 1e-6 and _v_d2py[1] == 0.0
       and _v_d2pg == (0.0, 0.0)
       and mk_view(None, {"mk_pending_day": 5.0}, "day") is None
       and mk_view(-3.0, {}, "run") == -3.0
       and mk_view(-3.0, {"mk_pending_run": float("nan")}, "run") == -3.0,
       "v-0925v D2: market_pending prices the still-unbooked cover (YES 297 @ "
       "13.951c) on its market's booked result: +$%.2f, the 11-02 ZEC hedge to "
       "the cent; a market with no booked leg adds nothing, an earlier ET "
       "day's counts against the run only, an unpriceable leg (no result) "
       "nothing; mk_view leaves a missing day file None" % _v_d2p[0])
    # pure risk_abort, the 11-02 07:30 ET numbers: the day stood at -$28.74,
    # the main leg booked -$281.63 (the day file reads -$310.37, the run
    # -$281.63) and the cover is still unbooked. Stop -$300.
    _v_d2sv = (dict(pintake.LEDGER), DAYLOSS_FILE, LOSS_BOUND_OPEN, SIZE)
    _v_d2td = _v_tf.mkdtemp(prefix="pin0925v-d2-")
    try:
        globals()["DAYLOSS_FILE"] = os.path.join(_v_d2td, "day.json")
        globals()["LOSS_BOUND_OPEN"] = False
        globals()["SIZE"] = 297.0
        with open(DAYLOSS_FILE, "w", encoding="utf-8") as _v_fh:
            json.dump({"day": et_day_key(time.time()), "realised": -310.37,
                       "at": "planted"}, _v_fh)
        pintake.LEDGER.clear()
        pintake.LEDGER.update({"halt": None, "realised": -281.63, "committed": 0.0,
                               "positions": {}, "losses": 0})

        class _V_A2:
            live = True
            loss_abort = -300.0
            max_positions = 99
        _v_d2st = {"halted": False, "errors": 0}
        _v_d2now = time.time()
        _v_d2leg = market_pending([(_v_d2now, "KXZEC15M-X", "yes", 0.13951, 297.0)],
                                  {(_v_d2now, "KXZEC15M-X"): "yes"}, _v_d2now)
        _v_d2r0 = risk_abort(dict(_v_d2st), _V_A2)
        _v_d2r1 = risk_abort(dict(_v_d2st, mk_pending_run=_v_d2leg[0],
                                  mk_pending_day=_v_d2leg[1]), _V_A2)
        pintake.LEDGER["realised"] = -281.63 - 30.0     # a run already down: the abort
        with open(DAYLOSS_FILE, "w", encoding="utf-8") as _v_fh:
            json.dump({"day": et_day_key(time.time()), "realised": -100.0,
                       "at": "planted"}, _v_fh)
        _v_d2r2 = risk_abort(dict(_v_d2st, mk_pending_run=_v_d2leg[0],
                                  mk_pending_day=_v_d2leg[1]), _V_A2)
        _v_d2r3 = risk_abort(dict(_v_d2st), _V_A2)
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(_v_d2sv[0])
        globals()["DAYLOSS_FILE"] = _v_d2sv[1]
        globals()["LOSS_BOUND_OPEN"] = _v_d2sv[2]
        globals()["SIZE"] = _v_d2sv[3]
        _v_sh.rmtree(_v_d2td, ignore_errors=True)
    ck(str(_v_d2r0).startswith("DAY loss cap") and "-310.37" in str(_v_d2r0)
       and _v_d2r1 is None and _v_d2r2 is None
       and str(_v_d2r3).startswith("loss abort") and not os.path.exists(_v_d2td),
       "v-0925v D2 (the 11-02 07:30 ET ZEC replay): main NO 297 booked -$281.63 "
       "with its YES cover (+$%.2f) still unbooked -- leg by leg the day reads "
       "-$310.37 and the -$300 stop trips (%r); seen by MARKET (net -$28.56, "
       "the day -$57.30) it does not (%r), and the same for the run abort "
       "(%r without the market view)" % (_v_d2leg[0], _v_d2r0, _v_d2r1, _v_d2r3))
    # DRIVEN, the same shape through the real loop at the worlds' size: A buys
    # YES 5 @ 95c, collapses at t 4 and is covered NO 5 @ 6c; Kalshi says NO.
    # The run abort is -$3: the main leg (-$4.77) alone crosses it, the
    # market (-$0.09) does not. risk_abort is watched.
    # v-0925v D2 (round 4, reworded): round 3's world booked the cover 15 s
    # after the main leg (one GET per ticker per 15 s) and showed the market
    # view hiding the dip; since round 4 both legs book from ONE read in ONE
    # pass, so there is no dip at all -- the split is the FALLBACK check's.
    _v_d2rd = []

    def _v_d2set(tk_, t_):
        if tk_ == _kA:
            _v_d2rd.append(t_)
            return {"status": "finalized", "result": "no"}
        return None
    _v_d2seen = []
    _v_d2ra = risk_abort

    def _v_d2probe(state_, a_):
        _v_d2seen.append((float(pintake.LEDGER.get("realised", 0.0)),
                          float(mk_view(pintake.LEDGER.get("realised", 0.0), state_, "run")),
                          mk_view(day_loss(), state_, "day")))
        return _v_d2ra(state_, a_)
    globals()["risk_abort"] = _v_d2probe
    try:
        _v_d2w = _offline_trade_loop([_k1_A(collapse_at=4)], live=True, run_s=80.0,
                                     loss_abort=-3.0, settle=_v_d2set)
        _v_d2wv = list(_v_d2seen)
        _v_d2seen[:] = []
        _v_d2c = _offline_trade_loop([_k1_A(collapse_at=None)], live=True, run_s=80.0,
                                     loss_abort=-3.0, result={_kA: "no"})
    finally:
        globals()["risk_abort"] = _v_d2ra
    _v_d2s = _kinds(_v_d2w, "settled", _kA)
    _v_d2h = [r for r in _kinds(_v_d2w, "halt_pending") + _kinds(_v_d2w, "halt")]
    _v_d2ch = [r for r in _kinds(_v_d2c, "halt_pending") + _kinds(_v_d2c, "halt")]
    _v_d2rk = [t for t in _v_d2rd if 49.0 <= t <= 79.0]
    ck(_v_d2w["raised"] is None and len(_v_d2s) == 2
       and float(_v_d2s[0]["pnl_c"]) < -400.0 and float(_v_d2s[1]["pnl_c"]) > 400.0
       and abs(_v_d2s[1]["t"] - _v_d2s[0]["t"]) < 1e-6 and len(_v_d2rk) == 1
       and min(x[0] for x in _v_d2wv) > -1.0
       and min(x[1] for x in _v_d2wv) > -1.0
       and min(x[2] for x in _v_d2wv if x[2] is not None) > -1.0
       and not _v_d2h and _v_d2w["ran_s"] >= 79.0,
       "v-0925v D2 DRIVEN (round 4, reworded): the main leg books %s c and its "
       "cover %s c %.1f s later -- the SAME pass, from the one read of the "
       "market (%d reads after the close) -- so the ledger never dips: the "
       "run abort and the day cap never see under $%.2f / $%.2f (the market's "
       "net); no halt against the -$3 stop, the run goes on (%r)"
       % ((_v_d2s[0]["pnl_c"] if _v_d2s else None),
          (_v_d2s[1]["pnl_c"] if len(_v_d2s) > 1 else None),
          ((_v_d2s[1]["t"] - _v_d2s[0]["t"]) if len(_v_d2s) > 1 else -1.0),
          len(_v_d2rk),
          (min(x[1] for x in _v_d2wv) if _v_d2wv else 0.0),
          (min([x[2] for x in _v_d2wv if x[2] is not None] or [0.0])),
          [r.get("why") for r in _v_d2h][:2]))
    ck(_v_d2c["raised"] is None and len(_kinds(_v_d2c, "settled", _kA)) == 1
       and _v_d2ch and any(str(r.get("why")).startswith(("DAY loss cap", "loss abort"))
                           for r in _v_d2ch),
       "v-0925v D2 CONTROL: the same main leg with NO cover still trips the -$3 "
       "stop the moment it books (%r) -- a real loss is seen at once"
       % ([r.get("why") for r in _v_d2ch][:1],))
    ck("_mk_pending_update(now)" in _v_tl
       and _v_tl.index("_mk_pending_update(now)") < _v_tl.index("        _v_guard(now)\n")
       < _v_tl.index("stop = risk_abort(state, a)")
       and 'mk_res[(close_s, tk)] = res' in _v_tl
       and '_dl = mk_view(_dl, state, "day")' in inspect.getsource(risk_abort)
       and '_rv = mk_view(led.get("realised", 0.0), state, "run")' in inspect.getsource(risk_abort)
       and 'mk_view(pintake.LEDGER.get("realised", 0.0), state, "run")' in _v_tl,
       "v-0925v D2 by source: a booked leg keeps its market's result, the "
       "pending siblings are priced once a pass below the hedge pass and above "
       "the guard and the risk check, and the day cap, the run abort and the "
       "unbooked guard all read them")

    # ---- D4: a jump give-up stops the JUMP only ---------------------------
    # YES bought at t 0; a 7 sd jump against it from t 4 with belief 0.85 (the
    # jump trigger alone); Kalshi rejects the first three hedge sends (the
    # 10-24..11-03 off-grid 400s); HEDGE_MAX_TRIES 3, so the jump gives up at
    # t 7; belief collapses to 0.30 at t 10 (live --hedge-belief 0.40).
    def _v_d4m(n, fair_of, moves_of=_jc_7):
        return {"tk": "KXD4%d15M-D4" % n, "series": "KXD4%d15M" % n,
                "iid": "D4%d" % n, "strike": 100.0, "fair": fair_of,
                "book": (lambda t: _ob(0.94, 0.05)), "moves": moves_of}

    def _v_d4_reply(n_fail):
        _c = {"n": 0}

        def _r(body, n):
            if str(body.get("ticker", "")).startswith("KXD4") and body.get("side") == "ask":
                _c["n"] += 1
                if n_fail is None or _c["n"] <= n_fail:
                    return 400, ('{"error": {"code": "invalid_parameters", '
                                 '"message": "planted off-grid hedge"}}')
            return _fill_all(body, n)
        return _r
    _v_d4on = dict(_jc_on, HEDGE_PROP=False, HEDGE_MAX_TRIES=3)
    _v_d4f = lambda t: 0.999 if t < 4.0 else (0.85 if t < 10.0 else 0.30)
    _v_d4a = _offline_trade_loop([_v_d4m(1, _v_d4f)], live=True, run_s=16.0,
                                 reply=_v_d4_reply(3), flags=_v_d4on)
    _v_d4b = _offline_trade_loop([_v_d4m(2, _v_d4f)], live=True, run_s=16.0,
                                 reply=_v_d4_reply(3), flags=dict(_v_d4on, HEDGE_PANIC=None))
    _v_d4ga = _kinds(_v_d4a, "hedge_gave_up")
    _v_d4pa = [p["_t"] for p in _v_posts(_v_d4a, "KXD4115M-D4", "ask")]
    _v_d4pb = [p["_t"] for p in _v_posts(_v_d4b, "KXD4215M-D4", "ask")]
    ck(_v_d4a["raised"] is None and len(_v_d4ga) == 1
       and _v_d4ga[0].get("trigger") == "jump" and _v_d4ga[0].get("jump_only") is True
       and len([t for t in _v_d4pa if t < 9.5]) == 3
       and not [t for t in _v_d4pa if _v_d4ga[0]["t"] - 0.01 < t < 9.5]
       and [t for t in _v_d4pa if t >= 9.5]
       and abs(_hedged(_v_d4a, "KXD4115M-D4") - 5.0) < 1e-9,
       "v-0925v D4 DRIVEN: three failed JUMP hedge sends (t %s), the jump gives "
       "up (t %s, trigger jump) -- and no more jump retries follow -- but the "
       "position is NOT marked hedged: belief falls under 0.40 at t 10 and the "
       "belief hedge is SENT (t %s) and covers all 5 (it used to be skipped "
       "for good: 5 positions 10-24..11-03)"
       % ([round(t, 1) for t in _v_d4pa if t < 9.5],
          (_v_d4ga[0]["t"] if _v_d4ga else None),
          [round(t, 1) for t in _v_d4pa if t >= 9.5]))
    ck(_v_d4b["raised"] is None and [t for t in _v_d4pb if t >= 9.5]
       and abs(_hedged(_v_d4b, "KXD4215M-D4") - 5.0) < 1e-9
       and not [r for r in _kinds(_v_d4b, "hedge_gave_up") if not r.get("jump_only")],
       "v-0925v D4 DRIVEN (no panic bypass: --hedge-panic off): the belief line "
       "starts with its OWN tries after the jump's give-up -- the 0.30 collapse "
       "is hedged (sent at t %s, covered %g) instead of giving up at once on "
       "tries the jump spent" % ([round(t, 1) for t in _v_d4pb if t >= 9.5],
                                  _hedged(_v_d4b, "KXD4215M-D4")))
    _v_d4c = _offline_trade_loop(
        [_v_d4m(3, (lambda t: 0.999 if t < 4.0 else 0.30), moves_of=(lambda t: []))],
        live=True, run_s=16.0, reply=_v_d4_reply(None), flags=dict(_v_d4on, HEDGE_PANIC=None))
    _v_d4gc = _kinds(_v_d4c, "hedge_gave_up")
    ck(_v_d4c["raised"] is None and len(_v_posts(_v_d4c, "KXD4315M-D4", "ask")) == 3
       and len(_v_d4gc) == 1 and _v_d4gc[0].get("jump_only") is None
       and _hedged(_v_d4c, "KXD4315M-D4") == 0.0,
       "v-0925v D4 NULL: the BELIEF line's own give-up is unchanged -- belief "
       "0.30 with no jump, every send rejected: 3 sends, one hedge_gave_up of "
       "the old shape, then nothing (%d sends)"
       % len(_v_posts(_v_d4c, "KXD4315M-D4", "ask")))

    # ---- D5: hedge sends do not spend the ENTRY budget --------------------
    # A: bought at t 10 (tau 30, the window's edge), belief 0.10 from t 11, so its NO hedge goes
    # out once a second -- and Kalshi fills none of it (201, fill 0: the lost
    # race); by t 35 that is 24+ sends, the close's entry budget. B decides at
    # t 35 (tau 5): it must still be bought.
    def _v_d5_reply(body, n):
        if body.get("ticker") == "KXA115M-K1" and body.get("side") == "ask":
            return 201, {"order_id": "d5-%d" % n,
                         "client_order_id": body.get("client_order_id"),
                         "fill_count": "0.00", "remaining_count": "0.00"}
        return _fill_all(body, n)
    _v_d5 = _offline_trade_loop([_v_A(1, collapse_at=11),
                                 _k1_B(1, decided_at=35)],
                                live=True, run_s=44.0, tau0=40, reply=_v_d5_reply)
    _v_d5h = [p["_t"] for p in _v_posts(_v_d5, "KXA115M-K1", "ask")]
    _v_d5b = [p["_t"] for p in _v_posts(_v_d5, _v_kB, "bid")]
    ck(_v_d5["raised"] is None
       and len([t for t in _v_d5h if t < 35.0]) >= MAX_ATTEMPTS_PER_CLOSE
       and _v_d5b and min(_v_d5b) >= 34.5
       and not _refusals(_v_d5, "attempts_cap")
       and _hedged(_v_d5, "KXA115M-K1") == 0.0,
       "v-0925v D5 DRIVEN: %d unfilled hedge sends on A before t 35 (the close's "
       "entry budget is %d) and B, deciding at t 35, is STILL bought (t %s; "
       "attempts_cap refusals %d) -- hedges count against their own budget only"
       % (len([t for t in _v_d5h if t < 35.0]), MAX_ATTEMPTS_PER_CLOSE,
          [round(t, 1) for t in _v_d5b][:2], len(_refusals(_v_d5, "attempts_cap"))))
    _re_d5 = __import__("re")
    ck(not _re_d5.search(r"(?<!hedge_)attempts\[_hcs\]", _v_tl)
       and "hedge_attempts[_hcs] = hedge_attempts.get(_hcs, 0) + 1" in _v_tl
       and "attempts.get(close_s, 0) >= MAX_ATTEMPTS_PER_CLOSE" in _v_tl,
       "v-0925v D5 by source: neither hedge send (cover nor extra) touches the "
       "entry counter; both count on the hedge's own, and the entry cap is "
       "still there for entries")

    # ---- D6: the open cap counts UNHEDGED contracts -----------------------
    _v_d6l = {"positions": {"A": {"contracts": 15.0}, "B": {"contracts": 4.0}}}
    ck(open_unhedged(_v_d6l, {"A": (7.5, 7.5)}) == 4.0
       and open_unhedged(_v_d6l, {"A": (5.0, 10.0)}) == 9.0
       and open_unhedged(_v_d6l, None) == 19.0 == open_contracts(_v_d6l)
       and open_unhedged(_v_d6l, {"A": (15.0, 0.0)}) == 19.0
       and open_unhedged(_v_d6l, {"A": ("x", 1)}) == 19.0
       and open_unhedged({}, {"A": (1, 1)}) == 0.0,
       "v-0925v D6: open_unhedged takes 2 x min(yes, no) off each market -- a "
       "7.5 + 7.5 pair counts 0, 5 YES against 10 NO counts the 5 naked; no "
       "sides, an unknown market or garbage counts every contract (the old cap)")
    _v_d6sv = (dict(pintake.LEDGER), SIZE, LOSS_BOUND_OPEN)
    try:
        globals()["SIZE"] = 5.0
        globals()["LOSS_BOUND_OPEN"] = False

        class _V_A6:
            live = False
            loss_abort = -1e9
            max_positions = 3
        pintake.LEDGER.clear()
        pintake.LEDGER.update({"halt": None, "realised": 0.0, "committed": 0.0,
                               "positions": {"KXP15M-P": {"contracts": 15.0}}})
        _v_d6a = risk_abort({"halted": False, "errors": 0,
                             "open_sides": {"KXP15M-P": (7.5, 7.5)}}, _V_A6)
        _v_d6b = risk_abort({"halted": False, "errors": 0,
                             "open_sides": {"KXP15M-P": (15.0, 0.0)}}, _V_A6)
        _v_d6c = risk_abort({"halted": False, "errors": 0}, _V_A6)
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(_v_d6sv[0])
        globals()["SIZE"] = _v_d6sv[1]
        globals()["LOSS_BOUND_OPEN"] = _v_d6sv[2]
    ck(_v_d6a is None and str(_v_d6b).startswith("open cap:")
       and halt_is_transient(_v_d6b) and str(_v_d6c).startswith("open cap:"),
       "v-0925v D6: a HEDGED PAIR at 3 x SIZE (7.5 YES + 7.5 NO, size 5, "
       "--max-positions 3) does not pause (%r); the same 15 unhedged does (%r), "
       "and a bare call with no sides counts everything as before"
       % (_v_d6a, _v_d6b))
    _v_oc1 = _offline_trade_loop([_k1_A(), _k1_B(1, decided_at=6)], live=True,
                                 reply=_fill_all, max_positions=1, flags=_ox_on)
    ck(_v_oc1["raised"] is None and abs(_hedged(_v_oc1, _kA) - 5.0) < 1e-9
       and _kinds(_v_oc1, "pause") and not _kinds(_v_oc1, "order", "KXB115M-K1")
       and str(_kinds(_v_oc1, "pause")[0].get("why")).startswith("open cap: 5 unhedged"),
       "v-0925v D6 CONTROL: the cap still binds on what is NOT covered -- the "
       "same 15 (5 YES, 5 NO cover, 5 NO extra) is 5 unhedged, at the cap of 1 "
       "x SIZE: paused (%r), B never bought"
       % ([r.get("why") for r in _kinds(_v_oc1, "pause")][:1],))
    ck('_open_u = open_unhedged(led, state.get("open_sides"))' in inspect.getsource(risk_abort)
       and 'state["open_sides"] = _open_sides()' in _v_tl
       and _v_tl.index('state["open_sides"] = _open_sides()') < _v_tl.index("stop = risk_abort(state, a)"),
       "v-0925v D6 by source: the loop hands risk_abort its own legs' sides "
       "every pass, right before the check")

    # ---- P7: the paused loop naps 0.05 s ----------------------------------
    _v_p7 = _v_tl[_v_tl.index('_pass_why = "pause"'):]
    _v_p7 = _v_p7[:_v_p7.index("continue")]
    ck("time.sleep(0.05)" in _v_p7 and "time.sleep(1.0)" not in _v_tl,
       "v-0925v P7 by source: the pause branch naps 0.05 s, the ordinary pass "
       "rate (%r), and no pass of the loop sleeps a second any more"
       % _v_p7.strip().splitlines()[-1:])

    # ---- JS: --hedge-jump-shadow ------------------------------------------
    _v_js6 = lambda t: [-0.00325] if t >= 4.0 else []        # 6.5 sd against YES

    def _v_jsm(n, fair_of, moves_of=_v_js6, book_of=(lambda t: _ob(0.94, 0.05))):
        return {"tk": "KXJS%d15M-JS" % n, "series": "KXJS%d15M" % n,
                "iid": "JS%d" % n, "strike": 100.0, "fair": fair_of,
                "book": book_of, "moves": moves_of}
    _v_js_on = {"HEDGE_JUMP_SHADOW": 6.0, "HEDGE_JUMP_MAX": 8.0,
                "HEDGE_BELIEF": 0.40, "JUMP_HEDGE_MIN_ASK": 0.05,
                "HEDGE_PROP": False}
    _v_js1 = _offline_trade_loop([_v_jsm(1, _jc_f85)], live=True, flags=_v_js_on)
    _v_js1s = _kinds(_v_js1, "jump_shadow")
    ck(_v_js1["raised"] is None and len(_v_js1s) == 1
       and _v_js1s[0].get("ticker") == "KXJS115M-JS" and _v_js1s[0].get("side") == "no"
       and abs(float(_v_js1s[0].get("n") or 0) - 5.0) < 1e-9
       and abs(float(_v_js1s[0].get("ask") or 0) - 0.06) < 1e-9
       and float(_v_js1s[0].get("ask_size") or 0) == 50.0
       and abs(float(_v_js1s[0].get("belief") or 0) - 0.85) < 1e-6
       and 6.4 <= float(_v_js1s[0].get("jump_sd") or 0) <= 6.6
       and _v_js1s[0].get("tau") is not None
       and _v_js1s[0].get("capped") is False and _v_js1s[0].get("cheap_skip") is False
       and _v_js1s[0].get("would_send") is True and _v_js1s[0].get("sent") is False
       and not _v_posts(_v_js1, "KXJS115M-JS", "ask")
       and not _kinds(_v_js1, "hedge_alarm") and not _kinds(_v_js1, "hedge"),
       "v-0925v JS DRIVEN: with the jump hedge OFF and the shadow at 6 sd, a "
       "6.5 sd jump against YES (belief 0.85) writes ONE jump_shadow -- side "
       "no, 5 contracts @ 6c (50 offered), belief, sd, tau, not capped, not "
       "cheap, would_send -- and SENDS NOTHING (%d hedge posts, %d alarms)"
       % (len(_v_posts(_v_js1, "KXJS115M-JS", "ask")), len(_kinds(_v_js1, "hedge_alarm"))))
    _v_js2 = _offline_trade_loop(
        [_v_jsm(2, lambda t: 0.999 if t < 4.0 else (0.85 if t < 7.0 else 0.30))],
        live=True, flags=_v_js_on)
    _v_js2a = _kinds(_v_js2, "hedge_alarm")
    ck(_v_js2["raised"] is None and len(_kinds(_v_js2, "jump_shadow")) == 1
       and _v_js2a and _v_js2a[0].get("trigger") == "belief" and _v_js2a[0]["t"] >= 6.5
       and abs(_hedged(_v_js2, "KXJS215M-JS") - 5.0) < 1e-9,
       "v-0925v JS DRIVEN: the belief hedge is untouched by the shadow -- the "
       "same jump shadowed at t 4, belief 0.30 at t 7: the belief alarm fires "
       "(t %s) and covers all 5" % ([r["t"] for r in _v_js2a][:1],))
    _v_js3 = _offline_trade_loop([_v_jsm(3, _jc_f85, moves_of=_jc_9)], live=True, flags=_v_js_on)
    _v_js4 = _offline_trade_loop([_v_jsm(4, _jc_f85, book_of=(lambda t: _ob(0.955, 0.04)))],
                                 live=True, flags=_v_js_on)
    _v_js0 = _offline_trade_loop([_v_jsm(5, _jc_f85)], live=True,
                                 flags=dict(_v_js_on, HEDGE_JUMP_SHADOW=None))
    _v_js3s, _v_js4s = _kinds(_v_js3, "jump_shadow"), _kinds(_v_js4, "jump_shadow")
    ck(len(_v_js3s) == 1 and _v_js3s[0].get("capped") is True
       and _v_js3s[0].get("would_send") is False
       and len(_v_js4s) == 1 and _v_js4s[0].get("cheap_skip") is True
       and _v_js4s[0].get("would_send") is False
       and abs(float(_v_js4s[0].get("ask") or 0) - 0.045) < 1e-9
       and not _v_posts(_v_js3, "KXJS315M-JS", "ask") and not _v_posts(_v_js4, "KXJS415M-JS", "ask")
       and _v_js0["raised"] is None and not _kinds(_v_js0, "jump_shadow")
       and not _v_posts(_v_js0, "KXJS515M-JS", "ask"),
       "v-0925v JS DRIVEN: a 9 sd jump is shadowed as CAPPED by the 8 sd cap, a "
       "4.5c hedge ask as SKIPPED by the 5c floor -- neither would send; "
       "NULL: the shadow off writes no jump_shadow")
    _v_jsb = _offline_trade_loop([_v_jsm(6, _jc_f85)], live=True,
                                 flags=dict(_v_js_on, HEDGE_JUMP_SIGMA=6.0))
    _v_jmn = inspect.getsource(main)
    ck(jump_shadow_conflict(6.0, 6.0) and jump_shadow_conflict(None, 6.0) is None
       and jump_shadow_conflict(6.0, None) is None and jump_shadow_conflict(None, None) is None
       and _v_jmn.index("_js_why = jump_shadow_conflict(a.hedge_jump, a.hedge_jump_shadow)")
       < _v_jmn.index('globals()["HEDGE_JUMP_SIGMA"] = float(a.hedge_jump)')
       < _v_jmn.index('globals()["HEDGE_JUMP_SHADOW"] = float(a.hedge_jump_shadow)')
       and "raise SystemExit(_js_why)" in _v_jmn
       and "hedge_jump_shadow=HEDGE_JUMP_SHADOW," in _v_jmn
       and _DEFAULT_HEDGE_JUMP_SHADOW is None
       and "HEDGE_JUMP_SHADOW" in _OFFLINE_PINNED_FLAGS and "HEDGE_JUMP_SHADOW" in _FLAG_GLOBALS
       and _v_jsb["raised"] is None and not _kinds(_v_jsb, "jump_shadow")
       and [r for r in _kinds(_v_jsb, "hedge_alarm") if r.get("trigger") == "jump"],
       "v-0925v JS: --hedge-jump with --hedge-jump-shadow is REFUSED at startup, "
       "before any flag is applied; the flag ships OFF, is pinned in every "
       "offline world and named in the start record; with the jump hedge ON "
       "the loop never shadows (the real jump alarm fires instead)")

    # ---- B: the 3rd bet out, the brake moved, SIZE and every order the same
    # pinned to the SHIPPED price ceiling: a paper arm runs this self-test under
    # its own --price-ceiling, and the claim is about the live 98c one
    _v_bsv = (EXTRA_COIN, LATE_EXTRA, LATE_EXTRA_TAU, BANK_BRAKE, PRICE_CEILING)
    _v_btk, _v_btk2 = "KXBTC15M-26NOV081200-00", "KXETH15M-26NOV081200-00"
    _v_brow = {}
    try:
        for _v_bn, (_v_bx, _v_bl, _v_bb) in (("old", (1.0, 1.0, 3.00)),
                                            ("new", (0.0, 0.0, 4.5))):
            globals()["EXTRA_COIN"], globals()["LATE_EXTRA"] = _v_bx, _v_bl
            globals()["LATE_EXTRA_TAU"], globals()["BANK_BRAKE"] = 15, _v_bb
            globals()["PRICE_CEILING"] = _DEFAULT_PRICE_CEILING
            _v_bper = float(worst_close_cost(1.0)) * float(BANK_BRAKE)
            _v_brow[_v_bn] = {"per": _v_bper, "rows": []}
            for _v_bk in (2400.0, 3000.0, 3400.0, 3464.0, 4000.0):
                _v_bS = float(size_for_bank(_v_bk, lo=1, hi=None))
                _v_bheld = {"tickers": [_v_btk], "contracts": 1.5 * _v_bS, "n": 1,
                            "sides": {_v_btk: "yes"}, "n_tk": {_v_btk: 1.5 * _v_bS}}
                _v_brow[_v_bn]["rows"].append((
                    _v_bk, _v_bS,
                    max(close_budget_for(None, _v_btk, size=_v_bS, tau=10),
                        close_budget_for(_v_bheld, _v_btk2, size=_v_bS, tau=30),
                        close_budget_for(_v_bheld, _v_btk2, size=_v_bS, tau=10)) / _v_bS,
                    full_bet_room(None, _v_btk, "yes", mult=1.5, size=_v_bS, x=1.0)))
    finally:
        (globals()["EXTRA_COIN"], globals()["LATE_EXTRA"],
         globals()["LATE_EXTRA_TAU"], globals()["BANK_BRAKE"],
         globals()["PRICE_CEILING"]) = _v_bsv
    ck(_v_brow["old"]["per"] == _v_brow["new"]["per"]
       and [r[1] for r in _v_brow["old"]["rows"]] == [r[1] for r in _v_brow["new"]["rows"]]
       and [r[3] for r in _v_brow["old"]["rows"]] == [r[3] for r in _v_brow["new"]["rows"]]
       and all(abs(r[2] - 3.0) < 1e-9 for r in _v_brow["old"]["rows"])
       and all(abs(r[2] - 2.0) < 1e-9 for r in _v_brow["new"]["rows"]),
       "v-0925v B (call B: --extra-coin 0 --late-extra 0 --bank-brake 4.5): the "
       "brake's divisor is the SAME number to the bit (%r vs %r), so SIZE at "
       "banks $2,400-$4,000 is identical (%s) and so is the largest single "
       "order (%s), while a close's main-contract budget falls from 3x to 2x "
       "SIZE (the worst close $1,153 -> $768 at SIZE 392)"
       % (_v_brow["old"]["per"], _v_brow["new"]["per"],
          [int(r[1]) for r in _v_brow["new"]["rows"]],
          [r[3] for r in _v_brow["new"]["rows"]]))

    # ==== v-0925v ROUND 4 (2026-11-08): the two reviews of round 3 ========
    # Each finding gets the world that shows it (the reviewers' probes where
    # they wrote one) and the pure / source check for what no world reaches;
    # each message starts "v-0925v <item>" so mutate.py can prove its own
    # checks FAIL with the fix switched off.

    # ---- D2: a pass that books ONE leg and then fails (the fallback) -----
    # A buys YES 5 @ 95c (close t 30), collapses at t 4 and is covered NO 5 @
    # 6c; Kalshi says NO. A planted fault makes reconcile fail on the COVER's
    # booking once, so the main leg (-$4.77) books at t 50 and the cover
    # (+$4.68) only when the ticker may be read again, ~15 s later -- the
    # split round 4 otherwise removed. A2 (close t 80) is decided at t 52,
    # inside the split. pintake's own loss line is the run's -$3 (live they
    # are the same number): by LEG the run is under it, by MARKET (-$0.09) it
    # is not. Without the leg_dip block A2's take goes to pintake, is refused
    # twice ("LOSS ABORT") and pin halts on 2 order errors (money review 1).
    _v_r4bf = billed_fee
    _v_r4bc = {"n": 0}

    def _v_r4_fee(p, n):
        if (_v_r4bc["n"] == 0 and abs(float(p) - 0.06) < 1e-6
                and sys._getframe(1).f_code.co_name == "reconcile"):
            _v_r4bc["n"] += 1
            raise RuntimeError("planted: the cover's booking fails once")
        return _v_r4bf(p, n)
    _v_r4seen = []
    _v_r4ra = risk_abort

    def _v_r4probe(state_, a_):
        _v_r4seen.append((float(pintake.LEDGER.get("realised", 0.0)),
                          float(mk_view(pintake.LEDGER.get("realised", 0.0), state_, "run"))))
        return _v_r4ra(state_, a_)
    _v_r4a2 = _v_A(2, collapse_at=None, decided_at=52,
                   close_time=_REAL_TIME.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  _REAL_TIME.gmtime(_v_close + 50)))
    _v_r4la = pintake.LOSS_ABORT
    globals()["billed_fee"] = _v_r4_fee
    globals()["risk_abort"] = _v_r4probe
    try:
        pintake.LOSS_ABORT = -3.0
        _v_r4f = _offline_trade_loop([_k1_A(collapse_at=4), _v_r4a2], live=True,
                                     run_s=90.0, loss_abort=-3.0, result={_kA: "no"})
    finally:
        globals()["billed_fee"] = _v_r4bf
        globals()["risk_abort"] = _v_r4ra
        pintake.LOSS_ABORT = _v_r4la
    _v_r4s = _kinds(_v_r4f, "settled", _kA)
    _v_r4b = _v_ts(_v_r4f, "entries_blocked", reason="leg_dip")
    _v_r4r = _v_ts(_v_r4f, "entries_resumed", reason="leg_dip")
    _v_r4p = [p["_t"] for p in _v_posts(_v_r4f, "KXA215M-K1", "bid")]
    _v_r4h = _kinds(_v_r4f, "halt_pending") + _kinds(_v_r4f, "halt")
    _v_r4e = [r for r in _kinds(_v_r4f, "error") if r.get("where") == "take_refused"]
    ck(_v_r4f["raised"] is None and _v_r4bc["n"] == 1 and len(_v_r4s) == 2
       and _v_r4s[1]["t"] - _v_r4s[0]["t"] >= 14.9
       and min(x[0] for x in _v_r4seen) < -4.0 and min(x[1] for x in _v_r4seen) > -1.0
       and len(_v_r4b) == 1 and len(_v_r4r) == 1
       and _v_r4s[0]["t"] - 0.1 <= _v_r4b[0] <= _v_r4s[0]["t"] + 0.1
       and _v_r4s[1]["t"] - 0.1 <= _v_r4r[0] <= _v_r4s[1]["t"] + 0.1
       and _v_r4p and min(_v_r4p) >= _v_r4r[0] - 1e-9
       and not _v_r4e and not _v_r4h
       and int((_v_r4f["state"] or {}).get("order_errors", 0) or 0) == 0,
       "v-0925v D2 (round 4) FALLBACK: a pass books the main leg and then fails "
       "on the cover (planted), so the legs book %.1f s apart; by leg the run "
       "dips to $%.2f, under pintake's own -$3 line, but the brakes see the "
       "market (never under $%.2f) and NEW ENTRIES ARE BLOCKED (leg_dip, t %s) "
       "until the cover books (resumed t %s): A2, decided at t 52, is bought at "
       "t %s instead of going to pintake to be refused -- %d refusals, %d order "
       "errors, no halt (2 refusals used to halt the run for good)"
       % (((_v_r4s[1]["t"] - _v_r4s[0]["t"]) if len(_v_r4s) > 1 else -1.0),
          (min(x[0] for x in _v_r4seen) if _v_r4seen else 0.0),
          (min(x[1] for x in _v_r4seen) if _v_r4seen else 0.0), _v_r4b, _v_r4r,
          [round(t, 1) for t in _v_r4p][:1], len(_v_r4e),
          int((_v_r4f["state"] or {}).get("order_errors", 0) or 0)))
    ck("            if tk in _ub_read:\n                st, b = _ub_read[tk]" in _v_tl
       and "                _ub_read[tk] = (st, b)         # v-0925v D2 (round 4): for every leg\n" in _v_tl
       and '("legdip", _vg_legdip)' in _v_tl and '_eb_set("leg_dip",' in _v_tl,
       "v-0925v D2 (round 4) by source: reconcile books every leg of a ticker "
       "from the pass's one read (late or not), and the guard runs the leg_dip "
       "part every pass")
    # pure: the day cap reads the DAY's pending and the run abort the RUN's --
    # a market of an earlier ET day still partly booked must not lift today
    _v_r4sv = (dict(pintake.LEDGER), DAYLOSS_FILE, LOSS_BOUND_OPEN, SIZE)
    _v_r4td = _v_tf.mkdtemp(prefix="pin0925v-r4-")
    try:
        globals()["DAYLOSS_FILE"] = os.path.join(_v_r4td, "day.json")
        globals()["LOSS_BOUND_OPEN"] = False
        globals()["SIZE"] = 297.0
        with open(DAYLOSS_FILE, "w", encoding="utf-8") as _v_fh:
            json.dump({"day": et_day_key(time.time()), "realised": -310.37,
                       "at": "planted"}, _v_fh)
        pintake.LEDGER.clear()
        pintake.LEDGER.update({"halt": None, "realised": -10.0, "committed": 0.0,
                               "positions": {}, "losses": 0})

        class _V_A24:
            live = True
            loss_abort = -300.0
            max_positions = 99
        _v_r4d1 = risk_abort({"halted": False, "errors": 0, "mk_pending_run": 300.0,
                              "mk_pending_day": 0.0}, _V_A24)
        _v_r4d2 = risk_abort({"halted": False, "errors": 0, "mk_pending_run": 0.0,
                              "mk_pending_day": 300.0}, _V_A24)
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(_v_r4sv[0])
        globals()["DAYLOSS_FILE"] = _v_r4sv[1]
        globals()["LOSS_BOUND_OPEN"] = _v_r4sv[2]
        globals()["SIZE"] = _v_r4sv[3]
        _v_sh.rmtree(_v_r4td, ignore_errors=True)
    ck(str(_v_r4d1).startswith("DAY loss cap") and _v_r4d2 is None,
       "v-0925v D2 (round 4): the day cap adds TODAY's pending only -- +$300 "
       "pending on an earlier day's market leaves today's -$310.37 tripping "
       "the -$300 stop (%r); the same +$300 on a market of today lifts it (%r)"
       % (_v_r4d1, _v_r4d2))
    _v_r4t = calendar.timegm((2026, 11, 2, 12, 30, 0))
    _v_r4n = market_pending([(_v_r4t, "T-N", "no", float("nan"), 10.0),
                             (_v_r4t, "T-I", "no", 0.5, float("inf")),
                             (_v_r4t, "T-G", "yes", 0.13951, 297.0)],
                            {(_v_r4t, "T-N"): "yes", (_v_r4t, "T-I"): "yes",
                             (_v_r4t, "T-G"): "yes"}, _v_r4t + 40)
    _v_r4m = {(1, "T"): "yes", (2, "U"): "yes"}
    _v_r4mc = mk_res_correct(_v_r4m, "T", "no")
    _v_r4mv = mk_res_correct(_v_r4m, "U", "void")
    _v_r4op = {"o1": (1, "yes", 0.95, 5.0, "T"), "o2": (1, "no", 0.06, 5.0, "T"),
               "o3": (2, "no", 0.06, 5.0, "U"), "o4": (3, "yes", 0.9, 5.0, "V"),
               "bad": ("x",)}
    _v_r4lg, _v_r4lv = market_pending_legs(_v_r4op, {(1, "T"): "yes", (2, "U"): "no"},
                                           {"o3"})
    ck(abs(_v_r4n[0] - 253.07) < 0.005 and abs(_v_r4n[1] - 253.07) < 0.005
       and _v_r4mc == [(1, "T")] and _v_r4m == {(1, "T"): "no", (2, "U"): "yes"}
       and _v_r4mv == []
       and _v_r4lg == [(1, "T", "yes", 0.95, 5.0), (1, "T", "no", 0.06, 5.0)]
       and _v_r4lv == {(1, "T"), (2, "U")}
       and market_pending_legs(None, {}, ()) == ([], set())
       and "mk_res_correct(mk_res, _t, _fr)" in _v_tl
       and "market_pending_legs(open_pos, mk_res, ub_parked)" in _v_tl
       and 'mk_view((day_loss() if live else None), state, "day"), a.loss_abort,' in _v_tl,
       "v-0925v D2 (round 4): an unpriceable leg (NaN cost, infinite count) adds "
       "NOTHING and cannot poison the others (+$%.2f, the good cover alone; a "
       "NaN used to zero every market's view); a final result re-prices only "
       "that ticker's unbooked legs (void moves none); a PARKED leg is left to "
       "the unbooked guard's worst case, never priced twice; and the unbooked "
       "guard reads the DAY total through the market view too" % _v_r4n[0])

    # ---- D4: the close's hedge cap on a jump-only second -----------------
    # (the tests review's probe) the jump's failing sends reach the close's
    # hedge cap (2 here; 120 live) on a jump-only second; belief 0.30 at t 10
    _v_r4c = _offline_trade_loop([_v_d4m(4, _v_d4f)], live=True, run_s=16.0,
                                 reply=_v_d4_reply(3),
                                 flags=dict(_v_d4on, HEDGE_MAX_TRIES=30,
                                            MAX_HEDGE_ATTEMPTS_PER_CLOSE=2))
    _v_r4cr = _kinds(_v_r4c, "hedge_refused")
    ck(_v_r4c["raised"] is None and abs(_hedged(_v_r4c, "KXD4415M-D4") - 5.0) < 1e-9
       and _v_r4cr and _v_r4cr[0].get("why") == "hedge_attempt_cap"
       and _v_r4cr[0].get("jump_only") is True
       and [p for p in _v_posts(_v_r4c, "KXD4415M-D4", "ask") if p["_t"] >= 9.5],
       "v-0925v D4 (round 4) DRIVEN: the jump's failing sends reach the close's "
       "hedge cap (2 here) on a jump-only second -- refused (%r, jump_only), "
       "the position is NOT marked hedged, and the belief collapse at t 10 is "
       "hedged (%g; panic bypasses the cap as before)"
       % ([r.get("why") for r in _v_r4cr][:1], _hedged(_v_r4c, "KXD4415M-D4")))
    # the belief line gets ALL of its own tries after the jump's give-up: at
    # HEDGE_MAX_TRIES 3 with no panic bypass, its first two sends are rejected
    # too and the third covers
    _v_r4t3 = _offline_trade_loop([_v_d4m(5, _v_d4f)], live=True, run_s=16.0,
                                  reply=_v_d4_reply(5),
                                  flags=dict(_v_d4on, HEDGE_PANIC=None))
    _v_r4t3p = [p["_t"] for p in _v_posts(_v_r4t3, "KXD4515M-D4", "ask")]
    ck(_v_r4t3["raised"] is None and len([t for t in _v_r4t3p if t >= 9.5]) == 3
       and abs(_hedged(_v_r4t3, "KXD4515M-D4") - 5.0) < 1e-9
       and len(_kinds(_v_r4t3, "hedge_gave_up")) == 1,
       "v-0925v D4 (round 4) DRIVEN: after the jump gives up, the belief line "
       "has a FRESH HEDGE_MAX_TRIES (3): two more rejected sends and the third "
       "covers all 5 (belief sends at t %s; one give-up, the jump's)"
       % [round(t, 1) for t in _v_r4t3p if t >= 9.5])

    # ---- D5: one market's reject loop blocks no other market -------------
    # (the tests review's probe) A's hedge is REJECTED (400, the 10-24..11-03
    # off-grid shape) every second from t 11; B decides at t 35, past the
    # close's 24-send entry budget
    def _v_r4_rej(body, n):
        if body.get("ticker") == "KXA115M-K1" and body.get("side") == "ask":
            return 400, ('{"error": {"code": "invalid_parameters", '
                         '"message": "planted off-grid hedge"}}')
        return _fill_all(body, n)
    _v_r45 = _offline_trade_loop([_v_A(1, collapse_at=11), _k1_B(1, decided_at=35)],
                                 live=True, run_s=44.0, tau0=40, reply=_v_r4_rej)
    _v_r45b = [p["_t"] for p in _v_posts(_v_r45, _v_kB, "bid")]
    _v_r45h = [p["_t"] for p in _v_posts(_v_r45, "KXA115M-K1", "ask")]
    _v_r45f = _kinds(_v_r45, "hedge_fail", "KXA115M-K1")
    ck(_v_r45["raised"] is None and len([t for t in _v_r45h if t < 35.0]) >= MAX_ATTEMPTS_PER_CLOSE
       and _v_r45b and min(_v_r45b) >= 34.5
       and not _kinds(_v_r45, "hedge_broken") and not _refusals(_v_r45, "attempts_cap")
       and len(_v_r45f) == 1 and _v_r45f[0].get("status_code") == 400
       and _v_r45f[0].get("streak_markets") == 1,
       "v-0925v D5 (round 4) DRIVEN: %d hedge sends REJECTED on A before t 35 "
       "(the case behind the 84 attempts_cap fires) and B, deciding at t 35, "
       "is still bought (t %s): one market's reject loop is that market's "
       "hedge_fail (%d, status %s), not hedge_broken (%d) and not the entry "
       "budget (%d attempts_cap)"
       % (len([t for t in _v_r45h if t < 35.0]), [round(t, 1) for t in _v_r45b][:1],
          len(_v_r45f), (_v_r45f[0].get("status_code") if _v_r45f else None),
          len(_kinds(_v_r45, "hedge_broken")), len(_refusals(_v_r45, "attempts_cap"))))

    # a SUCCESS ends the streak AND its markets: A's hedge is rejected at t 4
    # and t 5 and fills at t 6 (2 in a row, one market); A2 and A3 collapse at
    # t 8 and are each rejected once, then fill -- 2 in a row on two markets,
    # never 3. Were a 2xx to leave the count standing (H1), A's two and these
    # two would make 4 on two markets and block.
    def _v_r4_hfr():
        _c = {}
        _lim = {_kA: 2, "KXA215M-K1": 1, "KXA315M-K1": 1}

        def _r(body, n):
            tk = body.get("ticker")
            if body.get("side") == "ask" and tk in _lim:
                _c[tk] = _c.get(tk, 0) + 1
                if _c[tk] <= _lim[tk]:
                    return 400, '{"error": {"code": "invalid_parameters"}}'
            return _fill_all(body, n)
        return _r
    _v_r4hf = _offline_trade_loop([_k1_A(collapse_at=4), _v_A(2, collapse_at=8),
                                   _v_A(3, collapse_at=8)], live=True, run_s=14.0,
                                  reply=_v_r4_hfr(), flags={"MAX_PER_CLOSE": 3})
    ck(_v_r4hf["raised"] is None and not _kinds(_v_r4hf, "hedge_broken")
       and len(_kinds(_v_r4hf, "hedge_fail")) == 3
       and all(abs(_hedged(_v_r4hf, t) - 5.0) < 1e-9 for t in (_kA, "KXA215M-K1", "KXA315M-K1"))
       and not _v_ts(_v_r4hf, "entries_blocked", reason="hedge_broken"),
       "v-0925v hedgefail (round 4) DRIVEN: a 2xx ends the streak AND its "
       "markets -- 2 rejections on A, A's fill, then one each on A2 and A3 is "
       "never 3 in a row: no hedge_broken (%d hedge_fail), all three covered"
       % len(_kinds(_v_r4hf, "hedge_fail")))

    # ---- D6: the floor at 0 ------------------------------------------------
    ck(open_unhedged({"positions": {"A": {"contracts": 4.0}, "B": {"contracts": 4.0}}},
                     {"A": (5.0, 5.0)}) == 4.0
       and open_unhedged({"positions": {"A": {"contracts": 0.0}}}, {"A": (3.0, 3.0)}) == 0.0,
       "v-0925v D6 (round 4): a market can never count BELOW zero -- a ledger "
       "behind pin's legs (4 held, a 5 + 5 pair) is 0, not -6 offsetting "
       "another market's 4 naked contracts")

    # ---- JS: every second until it would send; below the hedge pass -------
    # (the tests review's probe) the NO ask is 4.5c at t 4 -- under the 5c
    # floor -- and 6c from t 5: the REAL jump hedge skips the first second and
    # sends the next; the shadow must say both, at the same seconds
    _v_r4bk = (lambda t: _ob(0.955, 0.04) if t < 5.0 else _ob(0.94, 0.05))
    _v_r4js = _offline_trade_loop([_v_jsm(7, _jc_f85, book_of=_v_r4bk)], live=True,
                                  flags=_v_js_on)
    _v_r4jr = _offline_trade_loop([_v_jsm(8, _jc_f85, book_of=_v_r4bk)], live=True,
                                  flags=dict(_v_js_on, HEDGE_JUMP_SHADOW=None,
                                             HEDGE_JUMP_SIGMA=6.0))
    _v_r4jss = _kinds(_v_r4js, "jump_shadow")
    _v_r4jrp = [p["_t"] for p in _v_posts(_v_r4jr, "KXJS815M-JS", "ask")]
    _v_r4jrc = _kinds(_v_r4jr, "hedge_cheap_skip")
    ck(_v_r4js["raised"] is None and len(_v_r4jss) == 2
       and _v_r4jss[0].get("outcome") == "cheap_skip" and _v_r4jss[0].get("would_send") is False
       and _v_r4jss[1].get("outcome") == "would_send" and _v_r4jss[1].get("would_send") is True
       and abs(float(_v_r4jss[1].get("ask") or 0) - 0.06) < 1e-9
       and _v_r4jrp and _v_r4jrc
       and abs(_v_r4jss[0]["t"] - _v_r4jrc[0]["t"]) < 0.06
       and abs(_v_r4jss[1]["t"] - min(_v_r4jrp)) < 0.06
       and not _v_posts(_v_r4js, "KXJS715M-JS", "ask"),
       "v-0925v JS (round 4) DRIVEN: the shadow follows the jump hedge second "
       "by second -- cheap_skip at t %s (the real one skipped at t %s), "
       "would_send at t %s (the real one SENT at t %s) -- and sends nothing; "
       "it used to stop at the first second (cheap_skip, nothing after)"
       % ([r["t"] for r in _v_r4jss][:1], [r["t"] for r in _v_r4jrc][:1],
          [r["t"] for r in _v_r4jss][1:2], [round(t, 2) for t in _v_r4jrp][:1]))
    # the lookback starts at ENTRY, as the jump hedge's does: a 6.5 sd jump at
    # t 4, the position bought at t 6 -- nothing to shadow (the world honours
    # the lookback through moves_n)
    def _v_r4mn(at):
        return lambda t, n: ([-0.00325] if (t >= at and t - at < n) else [])

    def _v_r4jm(n, at, fair_of):
        return {"tk": "KXJS%d15M-JS" % n, "series": "KXJS%d15M" % n,
                "iid": "JS%d" % n, "strike": 100.0, "fair": fair_of,
                "book": (lambda t: _ob(0.94, 0.05)), "moves_n": _v_r4mn(at)}
    _v_r4f6 = lambda t: 0.5 if t < 6.0 else 0.999
    _v_r4lb = _offline_trade_loop([_v_r4jm(9, 4.0, _v_r4f6)], live=True, flags=_v_js_on)
    _v_r4la2 = _offline_trade_loop([_v_r4jm(10, 8.0, _v_r4f6)], live=True, flags=_v_js_on)
    ck(_v_r4lb["raised"] is None and _v_posts(_v_r4lb, "KXJS915M-JS", "bid")
       and not _kinds(_v_r4lb, "jump_shadow")
       and _v_r4la2["raised"] is None
       and [r for r in _kinds(_v_r4la2, "jump_shadow") if r.get("would_send")],
       "v-0925v JS (round 4) DRIVEN: the shadow's lookback starts at ENTRY like "
       "the jump hedge's -- a jump 2 s before the buy is not shadowed (%d "
       "records); the same jump 2 s after it is (%d)"
       % (len(_kinds(_v_r4lb, "jump_shadow")), len(_kinds(_v_r4la2, "jump_shadow"))))
    # no try spent: shadow on, HEDGE_MAX_TRIES 1 and no panic bypass -- a
    # belief collapse after the shadowed jump still has its one try
    _v_r4nt = _offline_trade_loop(
        [_v_jsm(11, lambda t: 0.999 if t < 4.0 else (0.85 if t < 7.0 else 0.30))],
        live=True, flags=dict(_v_js_on, HEDGE_MAX_TRIES=1, HEDGE_PANIC=None))
    ck(_v_r4nt["raised"] is None and [r for r in _kinds(_v_r4nt, "jump_shadow") if r.get("would_send")]
       and abs(_hedged(_v_r4nt, "KXJS1115M-JS") - 5.0) < 1e-9
       and not _kinds(_v_r4nt, "hedge_gave_up"),
       "v-0925v JS (round 4) DRIVEN: the shadow spends NO hedge try -- with one "
       "try allowed and no panic bypass, the belief collapse after a shadowed "
       "jump is still hedged (%g) with no give-up" % _hedged(_v_r4nt, "KXJS1115M-JS"))
    _v_r4hp = _v_tl[_v_tl.index("        # ---------------- AMENDMENT 15: the hedge pass"):
                    _v_tl.index("        # ---------------- end AMENDMENT 15")]
    _v_r4mn2 = inspect.getsource(main)
    ck("jump_shadow_q.append(" in _v_r4hp and "_js_flush" not in _v_r4hp
       and 'rec("jump_shadow"' not in _v_r4hp
       and _v_tl.index("        # ---------------- end AMENDMENT 15")
       < _v_tl.index("            _js_flush()\n")
       < _v_tl.index("stop = risk_abort(state, a)")
       and jump_shadow_arg_error(6.0) is None and jump_shadow_arg_error(1.0) is None
       and jump_shadow_arg_error(50.0) is None and jump_shadow_arg_error(0.5)
       and jump_shadow_arg_error(51.0) and jump_shadow_arg_error("x")
       and jump_max_arg_error(None, 6.0, 8.0) is None
       and jump_max_arg_error(6.0, None, 8.0) is None
       and jump_max_arg_error(None, None, 8.0) and jump_max_arg_error(None, 6.0, 6.0)
       and jump_max_arg_error(None, 6.0, 101.0)
       and "_js_bad = jump_shadow_arg_error(a.hedge_jump_shadow)" in _v_r4mn2
       and "jump_max_arg_error(HEDGE_JUMP_SIGMA, HEDGE_JUMP_SHADOW," in _v_r4mn2,
       "v-0925v JS (round 4): the hedge pass only QUEUES the shadow; its book "
       "read, record and print happen below the pass (never in front of a "
       "hedge); --hedge-jump-shadow is refused outside [1, 50] sigma, and "
       "--hedge-jump-max may ride the shadow alone (above it, at most 100) -- "
       "main() refuses through these two pure checks")

    # ==== v-0925v ROUND 5 (2026-11-08): the three reviews of round 4 =======
    # The tests review's cheap gaps: a mutation of each of these survived
    # every round-4 check (rev4_tests\my_mutate.py). No live behaviour moves;
    # each gets the world that tells the code from its mutation, and each
    # message starts "v-0925v <item>" so mutate.py can prove it.

    # ---- D2 leg_dip: its line, its boundary, its view, its clear ----------
    # Round 4's FALLBACK world -- a planted fault fails the cover's booking
    # once, so A's legs book apart: the main leg (-$4.91) at t 50, the cover
    # (+$4.68) at t 65 -- run with pintake's own line and the run's stop SET
    # APART (live they are the same number, so only a world can tell which
    # one the block reads). A2 (its own close, t 80) decides at t 52.
    def _v_r5ld(markets, pin_line, run_stop, result, line_at_leg=False,
                day_split=False):
        _bc = {"n": 0}
        _bf, _ra, _dk = billed_fee, risk_abort, et_day_key
        _la0 = pintake.LOSS_ABORT
        _seen = []
        _lat = {"line": None}

        def _fee(p, n):
            if (_bc["n"] == 0 and abs(float(p) - 0.06) < 1e-6
                    and sys._getframe(1).f_code.co_name == "reconcile"):
                _bc["n"] += 1
                raise RuntimeError("planted: the cover's booking fails once")
            return _bf(p, n)

        def _probe(state_, a_):
            _r = float(pintake.LEDGER.get("realised", 0.0))
            if line_at_leg and _lat["line"] is None and _r < -4.0:
                pintake.LOSS_ABORT = _r      # pintake's line EXACTLY at the leg's loss
                _lat["line"] = _r
            _seen.append((_r, float(mk_view(_r, state_, "run")),
                          float(mk_view(_r, state_, "day"))))
            return _ra(state_, a_)

        def _day(now=None):
            # A's close falls on ANOTHER ET day (a 23:45 ET close whose main
            # leg books after midnight): its sibling's pending is the run's,
            # not today's -- the only place the run and day views part
            if (now is not None and float(now) == float(_v_close)
                    and sys._getframe(1).f_code.co_name == "market_pending"):
                return "2000-01-01"
            return _dk(now)
        globals()["billed_fee"] = _fee
        globals()["risk_abort"] = _probe
        if day_split:
            globals()["et_day_key"] = _day
        try:
            pintake.LOSS_ABORT = float(pin_line)
            _w = _offline_trade_loop(markets, live=True, run_s=90.0,
                                     loss_abort=float(run_stop), result=result)
        finally:
            globals()["billed_fee"] = _bf
            globals()["risk_abort"] = _ra
            globals()["et_day_key"] = _dk
            pintake.LOSS_ABORT = _la0
        _s = _kinds(_w, "settled", _kA)
        _w.update(planted=_bc["n"], seen=_seen, line=_lat["line"], s=_s,
                  b=_v_ts(_w, "entries_blocked", reason="leg_dip"),
                  r=_v_ts(_w, "entries_resumed", reason="leg_dip"),
                  p=[p["_t"] for p in _v_posts(_w, "KXA215M-K1", "bid")],
                  e=[r for r in _kinds(_w, "error") if r.get("where") == "take_refused"],
                  h=_kinds(_w, "halt_pending") + _kinds(_w, "halt"),
                  split=(len(_s) == 2 and _s[1]["t"] - _s[0]["t"] >= 14.9))
        return _w

    def _v_r5a2():
        return _v_A(2, collapse_at=None, decided_at=52,
                    close_time=_REAL_TIME.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                   _REAL_TIME.gmtime(_v_close + 50)))
    # the LINE: pintake's own (-$10) LOOSER than the run's stop (-$3) -- the
    # leg's -$4.91 is under the stop but over pintake's line, so pintake
    # would take the buy and nothing may be blocked
    _v_r51 = _v_r5ld([_k1_A(collapse_at=4), _v_r5a2()], -10.0, -3.0, {_kA: "no"})
    ck(_v_r51["raised"] is None and _v_r51["planted"] == 1 and _v_r51["split"]
       and not _v_r51["b"] and _v_r51["p"]
       and min(_v_r51["p"]) < _v_r51["s"][1]["t"] - 5.0
       and not _v_r51["e"] and not _v_r51["h"],
       "v-0925v D2 (round 5) leg_dip DRIVEN, its LINE: pintake's own -$10 "
       "looser than the run's -$3 stop, the legs booked %.1f s apart -- by leg "
       "the run is under its stop but pintake would take the buy, so NOTHING "
       "is blocked (%d leg_dip) and A2 is bought at t %s, before the cover "
       "books (t %s): the block reads pintake.LOSS_ABORT, never --loss-abort"
       % (((_v_r51["s"][1]["t"] - _v_r51["s"][0]["t"]) if len(_v_r51["s"]) > 1 else -1.0),
          len(_v_r51["b"]), [round(t, 2) for t in _v_r51["p"]][:1],
          [r["t"] for r in _v_r51["s"]][1:2]))
    # the BOUNDARY: pintake's line planted EXACTLY at the leg's booked loss
    # (pintake refuses at or under it: `realised <= LOSS_ABORT`)
    _v_r52 = _v_r5ld([_k1_A(collapse_at=4), _v_r5a2()], -100.0, -3.0, {_kA: "no"},
                     line_at_leg=True)
    ck(_v_r52["raised"] is None and _v_r52["planted"] == 1 and _v_r52["split"]
       and _v_r52["line"] is not None
       and min(x[0] for x in _v_r52["seen"]) == _v_r52["line"]
       and len(_v_r52["b"]) == 1 and len(_v_r52["r"]) == 1
       and _v_r52["s"][0]["t"] - 0.1 <= _v_r52["b"][0] <= _v_r52["s"][0]["t"] + 0.2
       and _v_r52["s"][1]["t"] - 0.1 <= _v_r52["r"][0] <= _v_r52["s"][1]["t"] + 0.1
       and _v_r52["p"] and min(_v_r52["p"]) >= _v_r52["r"][0] - 1e-9
       and not _v_r52["e"] and not _v_r52["h"],
       "v-0925v D2 (round 5) leg_dip DRIVEN, its BOUNDARY: realised EXACTLY on "
       "pintake's line ($%s) is blocked (t %s, resumed t %s) -- pintake refuses "
       "AT the line, so '<' would send A2 to two refusals and the 2-error halt "
       "(%d refusals, %d halts)"
       % (_v_r52["line"], _v_r52["b"], _v_r52["r"], len(_v_r52["e"]), len(_v_r52["h"])))
    # the VIEW: A's close on another ET day, so its sibling's pending is in
    # the run view only -- pintake's -$3 line tighter than the run's -$10
    # stop (looser than the day view's -$4.91, so no day-cap halt either way)
    _v_r53 = _v_r5ld([_k1_A(collapse_at=4), _v_r5a2()], -3.0, -10.0, {_kA: "no"},
                     day_split=True)
    ck(_v_r53["raised"] is None and _v_r53["planted"] == 1 and _v_r53["split"]
       and min(x[2] for x in _v_r53["seen"]) < -4.0
       and min(x[1] for x in _v_r53["seen"]) > -1.0
       and len(_v_r53["b"]) == 1 and len(_v_r53["r"]) == 1
       and _v_r53["p"] and min(_v_r53["p"]) >= _v_r53["r"][0] - 1e-9
       and not _v_r53["e"] and not _v_r53["h"],
       "v-0925v D2 (round 5) leg_dip DRIVEN, its VIEW: a market of another ET "
       "day split across its legs -- the day view sees the leg alone ($%.2f), "
       "the RUN view the market ($%.2f) -- is blocked by the run view (t %s, "
       "resumed t %s; %d refusals, %d halts): pintake's rail is per process, "
       "not per day"
       % ((min(x[2] for x in _v_r53["seen"]) if _v_r53["seen"] else 0.0),
          (min(x[1] for x in _v_r53["seen"]) if _v_r53["seen"] else 0.0),
          _v_r53["b"], _v_r53["r"], len(_v_r53["e"]), len(_v_r53["h"])))
    # the CLEAR: inside the split, A3 (its own close, t 38) books a REAL
    # -$4.91 at t 58 -- by market the run is now under pintake's -$3 line
    # too, so the block must lift at once (risk_abort and pintake's own
    # refusals take over, as they always did), not wait for the cover
    _v_r54 = _v_r5ld([_k1_A(collapse_at=4),
                      _v_A(3, collapse_at=None,
                           close_time=_REAL_TIME.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                          _REAL_TIME.gmtime(_v_close + 8)))],
                     -3.0, -50.0, {_kA: "no", "KXA315M-K1": "no"})
    _v_r54c = _kinds(_v_r54, "settled", "KXA315M-K1")
    ck(_v_r54["raised"] is None and _v_r54["planted"] == 1 and _v_r54["split"]
       and len(_v_r54c) == 1 and float(_v_r54c[0]["pnl_c"]) < -400.0
       and _v_r54["s"][0]["t"] < _v_r54c[0]["t"] < _v_r54["s"][1]["t"]
       and len(_v_r54["b"]) == 1 and len(_v_r54["r"]) == 1
       and abs(_v_r54["r"][0] - _v_r54c[0]["t"]) <= 0.1
       and min(x[1] for x in _v_r54["seen"]) < -3.0,
       "v-0925v D2 (round 5) leg_dip DRIVEN, its CLEAR: the block set at t %s "
       "lifts at t %s, when a real loss elsewhere (A3 booked at t %s) takes the "
       "MARKET view under pintake's line too (to $%.2f) -- not only once the "
       "cover books (t %s): under the line by market a loss is risk_abort's "
       "and pintake's, never a leg_dip"
       % (_v_r54["b"], _v_r54["r"], [r["t"] for r in _v_r54c][:1],
          (min(x[1] for x in _v_r54["seen"]) if _v_r54["seen"] else 0.0),
          [r["t"] for r in _v_r54["s"]][1:2]))

    # ---- D5: a 2xx ends the streak AND its markets -------------------------
    # A's hedge is rejected at t 4 and t 5 and fills at t 6; A2 collapses at
    # t 8 and is rejected three times in a row (t 8, 9, 10), then fills: three
    # in a row, on ONE market -- no hedge_broken. Were A's fill to leave A
    # among the streak's markets, A2's three would count two and block.
    def _v_r5_hfr():
        _c = {}
        _lim = {_kA: 2, "KXA215M-K1": 3}

        def _r(body, n):
            tk = body.get("ticker")
            if body.get("side") == "ask" and tk in _lim:
                _c[tk] = _c.get(tk, 0) + 1
                if _c[tk] <= _lim[tk]:
                    return 400, '{"error": {"code": "invalid_parameters"}}'
            return _fill_all(body, n)
        return _r
    _v_r55 = _offline_trade_loop([_k1_A(collapse_at=4), _v_A(2, collapse_at=8)],
                                 live=True, run_s=14.0, reply=_v_r5_hfr(),
                                 flags={"MAX_PER_CLOSE": 3})
    _v_r55f = _kinds(_v_r55, "hedge_fail")
    _v_r55p = [p["_t"] for p in _v_posts(_v_r55, "KXA215M-K1", "ask")]
    ck(_v_r55["raised"] is None and not _kinds(_v_r55, "hedge_broken")
       and not _v_ts(_v_r55, "entries_blocked", reason="hedge_broken")
       and len(_v_r55p) == 4 and len(_v_r55f) == 2
       and _v_r55f[1].get("ticker") == "KXA215M-K1"
       and _v_r55f[1].get("streak_markets") == 1
       and all(abs(_hedged(_v_r55, t) - 5.0) < 1e-9 for t in (_kA, "KXA215M-K1")),
       "v-0925v D5 (round 5) DRIVEN: a 2xx ends the streak AND its markets -- "
       "A rejected twice then filled, later A2 alone rejected three times in a "
       "row (%d sends): one market's loop, no hedge_broken (%d), A2's first "
       "hedge_fail counts %s market(s); both covered"
       % (len(_v_r55p), len(_kinds(_v_r55, "hedge_broken")),
          (_v_r55f[1].get("streak_markets") if len(_v_r55f) > 1 else None)))

    # ---- D2: the pass's one read is the TICKER's ---------------------------
    # two markets of ONE close, both bought YES 5 @ 95c, booked in the same
    # pass with different results (A yes, A2 no): each books its own answer
    _v_r56 = _offline_trade_loop([_k1_A(collapse_at=None), _v_A(2, collapse_at=None)],
                                 live=True, run_s=60.0,
                                 result={_kA: "yes", "KXA215M-K1": "no"},
                                 flags={"MAX_PER_CLOSE": 3})
    _v_r56s = {r.get("ticker"): r for r in _kinds(_v_r56, "settled")}
    ck(_v_r56["raised"] is None and sorted(_v_r56s) == sorted([_kA, "KXA215M-K1"])
       and len(_kinds(_v_r56, "settled")) == 2
       and float(_v_r56s[_kA]["pnl_c"]) > 0.0 and float(_v_r56s["KXA215M-K1"]["pnl_c"]) < -400.0
       and abs(_v_r56s[_kA]["t"] - _v_r56s["KXA215M-K1"]["t"]) < 1e-6,
       "v-0925v D2 (round 5) DRIVEN: the pass's one read is the TICKER's -- two "
       "markets of one close booked in the same pass (t %s) each book their "
       "own result (A yes %s c, A2 no %s c), never the other's"
       % (sorted(set(r["t"] for r in _v_r56s.values())),
          (_v_r56s.get(_kA) or {}).get("pnl_c"),
          (_v_r56s.get("KXA215M-K1") or {}).get("pnl_c")))

    # ---- D4: the close's hedge cap ends the JUMP's retries -----------------
    # round 4's cap world (_v_r4c, above): the jump stays at 7 sd every second
    # until the belief collapse at t 10, so a cap refusal that did not end the
    # jump's retries would be written once a SECOND until then
    _v_r57 = [r for r in _kinds(_v_r4c, "hedge_refused")
              if r.get("why") == "hedge_attempt_cap" and r.get("jump_only")]
    ck(len(_v_r57) == 1 and abs(_hedged(_v_r4c, "KXD4415M-D4") - 5.0) < 1e-9,
       "v-0925v D4 (round 5) DRIVEN: the close's hedge cap on a jump-only second "
       "ENDS the jump's retries (jump_gave_up) -- one hedge_refused (t %s), not "
       "one a second until the close; the belief collapse is still hedged"
       % [r["t"] for r in _v_r57])

    # ---- F2: the verdict is what the retrying sweep could NOT remove -------
    # a REAL leak -- a file pin code still holds open (round 4's pintraj-
    # shape) -- survives every retry and is the failure; a folder held through
    # the sweep's FIRST try as well (a slower scanner) is removed by a retry
    # and is only reported
    _v_r5rt = _v_sh.rmtree
    _v_r5lk = _v_tf.mkdtemp(prefix="pin0925v-r5leak-")
    _v_r5sl = _v_tf.mkdtemp(prefix="pin0925v-r5slow-")
    _v_r5fh = None
    _v_r5v = None
    _v_r5n = {"slow": 0}

    def _v_r5rm(p, *a_, **k_):
        _b = os.path.basename(str(p))
        if _b == os.path.basename(_v_r5sl) and _v_r5n["slow"] < 2:
            _v_r5n["slow"] += 1
            return None                  # held: rmtree(ignore_errors) removes nothing
        if _b == os.path.basename(_v_r5lk) and os.name != "nt":
            return None                  # only Windows refuses to delete an open file
        return _v_r5rt(p, *a_, **k_)
    try:
        _v_r5fh = open(os.path.join(_v_r5lk, "held.jsonl"), "w", encoding="utf-8")
        _v_r5fh.write("{}\n")
        _v_r5fh.flush()
        with open(os.path.join(_v_r5sl, "x.json"), "w", encoding="utf-8") as _v_fh:
            _v_fh.write("{}")
        _v_sh.rmtree = _v_r5rm
        _v_sh.rmtree(_v_r5sl, ignore_errors=True)       # its world's own delete: held
        # the leak with a short budget (our own handle holds it whatever the
        # budget: this costs 30 ms, not 2 s, at every start); the slow lock
        # with the check's own (a real scanner on top cannot fail it either)
        _v_r5v = (sweep_temp_verdict([_v_r5lk], tries=3, wait_s=0.01),
                  sweep_temp_verdict([_v_r5sl]))
    finally:
        _v_sh.rmtree = _v_r5rt
        if _v_r5fh is not None:
            _v_r5fh.close()
        _v_sh.rmtree(_v_r5lk, ignore_errors=True)
        _v_sh.rmtree(_v_r5sl, ignore_errors=True)
    ck(_v_r5v == (([], [_v_r5lk]), ([_v_r5sl], [])) and _v_r5n["slow"] == 2,
       "v-0925v F2 (round 5): the TEMP verdict is what the retrying sweep could "
       "NOT remove -- a folder whose file pin code still holds open is left "
       "after every retry and FAILS (a real leak); one held through the "
       "sweep's first try is removed by a retry and only reported (%r)"
       % (None if _v_r5v is None else
          [([os.path.basename(p) for p in _x[0]], [os.path.basename(p) for p in _x[1]])
           for _x in _v_r5v],))
    # the reviewers' probe, in the self-test: ONE delete fails ONCE -- the
    # first rmtree of an offline world's own pinloop- folder removes nothing
    # (what rmtree(ignore_errors) does with a file a scanner holds for a
    # moment) -- so that folder is still on disk when the check below runs
    _v_r5tn = []

    def _v_r5tr(p, *a_, **k_):
        if not _v_r5tn and os.path.basename(str(p)).startswith("pinloop-"):
            _v_r5tn.append(str(p))
            return None
        return _v_r5rt(p, *a_, **k_)
    _v_sh.rmtree = _v_r5tr
    try:
        _v_r5tw = _offline_trade_loop([_k1_B(1, decided_at=99)], run_s=1.0)
    finally:
        _v_sh.rmtree = _v_r5rt
    _v_r5tx = bool(_v_r5tn) and os.path.exists(_v_r5tn[0])

    # ---- F2: EVERY TEMP folder the self-test makes is gone ----------------
    # selftest() records every tempfile.mkdtemp of the run (and sweeps any
    # straggler in its finally); the two known leaks -- pinmirror- (never
    # removed) and pintraj-selftest- (a held handle) -- left one folder each
    # per self-test, i.e. per live restart. Checked here, near the body's end.
    # Round 5: judged on what is STILL THERE AFTER the retrying sweep
    # (sweep_temp_verdict) -- round 4 failed on the list taken before it, so
    # one folder a scanner held for a moment failed the startup self-test and
    # pin refused to start; the folder planted just above is that case. A
    # sweep that may remove what it finds would also hide a folder its own
    # code NEVER removes (round 4's pinmirror-), so round 4's two leak sites
    # must each have handed their folder to rmtree themselves -- read from
    # selftest()'s record of the calls (_SELFTEST_RM, taken before this
    # check's own sweep), which no lock can change.
    _v_r5tm = list(_SELFTEST_TEMP)
    _v_r5rs = set(_SELFTEST_RM)
    _v_r5ow = [p for p in _v_r5tm
               if os.path.basename(p).startswith(("pinmirror-", "pintraj-selftest-"))]
    _v_r5oh = [p for p in _v_r5ow if os.path.normcase(os.path.abspath(p)) in _v_r5rs]
    _v_r5sw, _v_r5tl = sweep_temp_verdict(_v_r5tm)
    ck(len(_v_r5tm) >= 50 and not _v_r5tl
       and _v_r5tx and _v_r5tn[0] in _v_r5sw and not os.path.exists(_v_r5tn[0])
       and any(os.path.basename(p).startswith("pinmirror-") for p in _v_r5ow)
       and any(os.path.basename(p).startswith("pintraj-selftest-") for p in _v_r5ow)
       and len(_v_r5oh) == len(_v_r5ow),
       "v-0925v F2 (round 5): every TEMP folder this self-test has made (%d "
       "through tempfile.mkdtemp, pinmirror- and pintraj-selftest- among them) "
       "is gone by now, judged AFTER the retrying sweep -- %d still on disk at "
       "the check were removed by its retries and are only reported (a passing "
       "lock, the planted one among them: %s); left after every retry: %s; "
       "round 4's two leak sites removed their own folders (%d of %d handed to "
       "rmtree by their own code -- the sweep is for stragglers, never the fix)"
       % (len(_v_r5tm), len(_v_r5sw), [os.path.basename(p) for p in _v_r5sw][:4],
          [os.path.basename(p) for p in _v_r5tl][:4], len(_v_r5oh), len(_v_r5ow)))
    # ---- the process state the startup self-test plants -----------------
    _v_keep = (set(_API_SHAPE_SEEN), list(_API_SHAPE_Q), _API_SHAPE_DROPPED[0],
               {k: dict(v) for k, v in _LOG_HEALTH.items()}, dict(_DAYLOSS_PENDING),
               _PRINT_FAILS[0])
    try:
        api_shape("E9", "f9", "missing")
        _DAYLOSS_PENDING["x9"] = {"day": "d", "realised": -1.0}
        log_write_failed("log", OSError("planted"))
        _PRINT_FAILS[0] += 1
        _v_lk = v0925v_reset_process_state()
        _v_empty = (not _API_SHAPE_SEEN and not _API_SHAPE_Q and not _DAYLOSS_PENDING
                    and all(int(h.get("streak") or 0) == 0 for h in _LOG_HEALTH.values())
                    and _PRINT_FAILS[0] == 0)
    finally:
        _API_SHAPE_SEEN.clear()
        _API_SHAPE_SEEN.update(_v_keep[0])
        _API_SHAPE_Q.clear()
        _API_SHAPE_Q.extend(_v_keep[1])
        _API_SHAPE_DROPPED[0] = _v_keep[2]
        _LOG_HEALTH.clear()
        _LOG_HEALTH.update(_v_keep[3])
        _DAYLOSS_PENDING.clear()
        _DAYLOSS_PENDING.update(_v_keep[4])
        _PRINT_FAILS[0] = _v_keep[5]
    _v_mnr = inspect.getsource(main)
    ck(_v_empty and _v_lk.get("api_shape_seen") == 1 and _v_lk.get("dayloss_pending") == 1
       and _v_lk.get("log_streaks") == 1
       and 0 <= _v_mnr.find("    if not selftest():")
       < _v_mnr.find("    _v_leak = v0925v_reset_process_state()")
       < _v_mnr.find("    rec(\"start\",")
       and "selftest_leak=_v_leak," in _v_mnr,
       "v-0925v: whatever the startup self-test left in the sentinel, the log "
       "health or the pending day totals is emptied before anything live runs "
       "(found %r here) and the start record says what it found" % (_v_lk,))
    _v_mn = inspect.getsource(main)
    ck(_v_mn.index("book = livebook.LiveBook(") < _v_mn.index("book_shape_wrap(book)")
       < _v_mn.index("book.start()")
       and "log_append(logpath, kw)" in _v_mn
       and "fail_safe=v0925v_settings()," in _v_mn
       and _v_tl.index("# ---------------- AMENDMENT 15") < _v_tl.index("        _v_guard(now)\n")
       < _v_tl.index("stop = risk_abort(state, a)")
       and _v_tl.count("        _v_guard(now)\n") == 1
       and "api_shape_flush(rec)" in _v_tl,
       "v-0925v by source: the book is wrapped before it starts, main()'s log "
       "write is counted, the start record names the fail-safe settings, and "
       "the guard runs once a pass BELOW the hedge pass and ABOVE the risk check")
    ck(not [p for p in sys.path if "kals-work" in os.path.normcase(str(p))],
       "v-0925v importpath: after the whole v-0925v suite -- every index socket "
       "and book it built included -- no kals-work entry is on sys.path")

''')

# a LIVE world with a bank publishes its size after a successful read; the stub writes nothing (no world may touch the
# real mirror) and no longer raises, which only the v-0925v startbank worlds (the first live + bank worlds) reach
R.replace('''        g["publish_size"] = _no_net
''', '''        g["publish_size"] = (lambda *_a, **_k: None)   # v-0925v: writes nothing, never raises
''')

_got = R.write(EXPECTED_PINRUN)
print("patched", PR, _got, ("(checked: the reviewed %s)" % EXPECTED_PINRUN) if EXPECTED_PINRUN else "(UNCHECKED)")
print("v-0925v: every fix is always on; one new flag, --hedge-jump-shadow, ships OFF and is not launched; the launcher's "
      "argv is 0925u's (--cheap-window 6 10 0.98) with call B (--extra-coin 0 --late-extra 0 --bank-brake 4.5)")
