"""spec.py -- what a bot IS, as data: the dataclasses every research/bots/<name>.py fills in (DESIGN section 3.1).

v-tg-rebuild step 1 (2026-10-30). The operator's phone knew each bot through ~30 parallel tables in botstats.py,
pinphone.py and tgcharts.py, kept in step by hand (and by a DRIFT self-test). Here one file a bot holds every fact about
it once; bots/__init__.py derives the old tables from these, and bots/tests/test_registry.py proves each derived table
equals the live one it will replace. Nothing in production imports this package yet (step 3 is botstats' switch).

Deviations from DESIGN 3.1, each because a live table needed it:
  - Bot.command: the ONE command the phone names for a bot (BOT_CMD_OF: the forecaster's is /fc although /forecaster
    is listed first); Bot.commands keeps every alias in the old order.
  - Bot.page: None = the generic one-bot page (BOT_CMDS lists its commands); "race" = its own page (/race), whose
    commands are NOT in BOT_CMDS but ARE in tgcharts.CMD_KIND.
  - Pot.short / Pot.part: /funds' short account name (FUNDS_SHORT, joined with '+') and a two-pot bot's name for each
    pot (tgcharts.POT_WHAT).
  - Bot.funds_size: the bot's /funds bet-size reader, size_words(SizeIn) -> words or None (FUNDS_SIZE_BOTS = the bots
    that have one). v-tg-rebuild step 5 (2026-10-30): the readers moved here verbatim from pinphone.funds_sizes, where
    they were closures over its `when` and `results`; SizeIn hands them those and the phone's readers.
  - Bot.pot_word: its pot's words in the phone's cash lines (pinphone._POT_WORD) when they are not its `word` (the
    weather dip-seller's pot is 'weather'). Bot.ledger_book: pinday's book name for its main-account markets ('crypto',
    'coin race': /stats' lifetime-by-bot names and pinphone.main_bot_of's fallback). Both step 5.
  - Logs.start_rule: "first_line" (pin: the first record of its newest log), "pid_then_live" (the forecaster, ladder,
    weather, FX taker, jump band: the start record of the running pid, else the newest live one), "live" (the race).
  - Records.activity / activity_note hooks take (k, r, out, why, st) / (out, st): botstats.activity's per-bot elif
    bodies, verbatim, with the shared counters in `st` ({"triggers": 0, "filled_tk": set()}).
  - Feature.pos: the row's place in pinphone.FEATURES (bot rows and other programs' rows interleave there);
    Feature.hides: the row is in pinphone.FEATURE_BOT (shown only while its bot is active).
  - Speed: /speed's per-bot spec (SPEED_OTHERS / SPEED_SKIPPED with their order).
"""
from dataclasses import dataclass, field
from typing import Callable, Optional


def toks(cl):
    """A command line's words, quotes dropped.  (botstats._toks)"""
    return str(cl or "").replace('"', " ").split()


def opt(cl, flag):
    """The value after `flag` on a command line, or None.  (botstats.opt)"""
    t = toks(cl)
    return t[t.index(flag) + 1] if flag in t and t.index(flag) + 1 < len(t) else None


def live_flag(flag="--live", deny=()):
    """is_live for a bot whose live copy carries `flag` and none of `deny` (botstats.is_bot's rule: the jump band's
    --live --dry-run sends nothing, 2026-10-30; the race's --paper-live is a paper arm)."""
    deny = tuple(deny)

    def is_live(t):
        if flag not in t:
            return False
        return not any(d in t for d in deny)
    is_live.flag, is_live.deny = flag, deny
    return is_live


@dataclass(frozen=True)
class Pot:
    """One Kalshi pot (subaccount `sub`, cash pool `pool`) a bot trades from."""
    sub: str
    pool: int
    claims: Optional[Callable[[str, str], bool]] = None   # (series, ticker) -> mine; None = the rest of the sub
    priority: int = 50                                    # lower is asked first within the sub
    pool_only: bool = False                               # the bot's own view of the sub is this pool only
    what: Optional[str] = None                            # /funds' words for what runs there (FUNDS_WHAT)
    short: Optional[str] = None                           # /funds' short account name (FUNDS_SHORT), joined with '+'
    part: Optional[str] = None                            # a two-pot bot's name for this pot (tgcharts.POT_WHAT)


@dataclass(frozen=True)
class Logs:
    path: Optional[str] = None                            # its log, in RESULTS
    glob: Optional[str] = None                            # pin: "pinrun-live-*.jsonl"
    start_rule: str = "pid_then_live"                     # "first_line" | "pid_then_live" | "live"


@dataclass(frozen=True)
class Records:
    start: tuple = ("start",)
    fills: tuple = ()                                     # FILL_KINDS
    fill_qty: str = "delta"                               # the field a fill's contracts are in
    fill_side: str = "side"                               # the field naming the side bought
    fixed_side: Optional[str] = None                      # the weather dip-seller: always 'yes' (it SELLS yes)
    act: str = "bought"
    hedge: Optional[str] = None                           # pin: 'hedge' records (executed only, qty 'n', side 'side')
    halts: tuple = ()                                     # HALT_KINDS
    halt_lifts: tuple = ("resume",)
    halt_lifts_next_day: tuple = ()                       # the jump band's day_stop names its ET day
    refusal_words: tuple = ()                             # its part of botstats.PLAIN (pattern, words)


@dataclass(frozen=True)
class VersionRule:
    """Which VERSIONS.md headings are this bot's (botstats.version_of)."""
    part: Optional[Callable[[str], bool]] = None          # one name of a combined heading ('v-a + v-b') is mine
    text: Optional[Callable[[str, str], bool]] = None     # (vname, lower-cased 'vname rest') -> about me
    override: Optional[str] = None                        # a name starting so is mine whatever else it mentions
    default: bool = False                                 # the pin bot: every heading no other bot claims ...
    combined_not: Optional[str] = None                    # ... unless a combined heading matches this (regex)
    single_not: Optional[str] = None                      # ... or a single one matches this (regex)


@dataclass(frozen=True)
class Feature:
    """One /features row: (script, a flag it must have, a flag it must not have, label, sentence)."""
    script: str
    must: Optional[str]
    must_not: Optional[str]
    label: str
    sentence: str
    pos: int                                              # its place in pinphone.FEATURES
    hides: bool = False                                   # in FEATURE_BOT: shown only while the bot is active

    def row(self):
        return (self.script, self.must, self.must_not, self.label, self.sentence)


@dataclass(frozen=True)
class Speed:
    """/speed for a bot: measured from its log (record field + order kind), or skipped with a reason."""
    rank: int                                             # order within SPEED_OTHERS or SPEED_SKIPPED
    field: Optional[str] = None
    kind: Optional[str] = None
    skipped: Optional[str] = None


@dataclass(frozen=True)
class SettingsIn:
    """What a settings hook reads: its start record, its command line, and a reader of a RESULTS json file."""
    start: Optional[dict]
    cmdline: Optional[str]
    read_json: Callable[[str], Optional[dict]] = field(default=lambda name: None)


@dataclass(frozen=True)
class SizeIn:
    """What a /funds bet-size reader (Bot.funds_size) gets from pinphone.funds_sizes: the results folder, the account it
    is asked about, and the phone's readers -- so a bot file imports neither pinphone nor botstats. (v-tg-rebuild step 5)"""
    results: str
    sub: int                                              # the /funds account number (0 = the main account)
    when: Callable[[dict], str]                           # a record -> its ET clock words, '?' with no time
    last_record: Callable                                 # botstats.last_record(path, kinds, pred=None)
    epoch: Callable                                       # botstats._epoch
    num: Callable                                         # a float or None (pinphone._fnum)
    usd2: Callable                                        # '$1,254.69' (pinphone._usd2)
    read_json: Callable[[str], Optional[dict]]            # a json file's dict or None (pinphone.read_json)


@dataclass(frozen=True)
class Start:
    """How the phone's /resume STARTS a bot that nothing keeps alive (keepalive None): one PowerShell script in RESULTS,
    run detached through WMI (Win32_Process.Create: it outlives the phone, and an ssh session cannot kill it), with fixed
    arguments -- never anything typed in the chat. The script must refuse by itself when a live copy already runs or the
    stop file is set (results/jb_deploy.ps1 -Stage live does both). v-tg-step12 (2026-10-30, lane R)."""
    script: str                                           # a .ps1 file name in RESULTS
    args: tuple = ()                                      # its fixed arguments
    log: Optional[str] = None                             # the log it writes in RESULTS (its tail is said afterwards)
    wait_s: int = 40                                      # how long after the launch the phone reads the log back
    words: str = ""                                       # the recipe in words, for the confirm question


@dataclass(frozen=True)
class WatchIn:
    """What a monitor hook (Bot.stop_gauges, Bot.books) reads -- the bot's own log through these readers only, so a bot
    file imports neither the phone nor botstats. (v-tg-rebuild step 12, lane Q)"""
    results: str                                          # the results folder
    now: float                                            # epoch (the phone's clock)
    today: str                                            # the ET day of `now`
    last_record: Callable                                 # botdata.logs.last_record(path, kinds, pred=None)
    read_since: Callable                                  # botdata.logs.read_since(path, since) -> [records] or None
    epoch: Callable                                       # a record's 't' -> epoch or None
    et_day: Callable                                      # epoch -> 'YYYY-MM-DD' (ET)


@dataclass(frozen=True)
class Gauge:
    """One stop a bot trips by itself, read from its own records: where it stands now against the line that stops it.
    The phone warns once per level per `period` (a run, an ET day, 'live' for a line that never resets) as `money`
    falls through each of `warn_at` (money levels, highest first), and once more when it trips (money <= line, or its
    own record says so)."""
    key: str                                              # 'day', 'line', 'abort' ... (unique within the bot)
    what: str                                             # 'its day stop'
    money: float                                          # the settled $ counted against the line now
    line: float                                           # the line: it trips at money <= line (negative)
    warn_at: tuple                                        # money levels to warn at, highest first: (-15.0, -20.0)
    period: str                                           # the episode: '2026-10-30', 'run 20261028T011720Z', 'live'
    counted: str = ""                                     # what `money` is: 'settled today', 'since it went live'
    trips: str = ""                                       # what happens at the line: 'it stops for the day'
    tripped: bool = False                                 # its own record says the line was hit


@dataclass(frozen=True)
class Book:
    """What a bot's own log says one of its pots holds: `value0`, read from Kalshi by the bot itself at `t0` (its start,
    a resize, a sizing) while it held nothing open, plus every market it settled since -- so Kalshi's cash + open bets
    in that pot (its own pool for a pool_only pot) should be value0 + settled: the phone's balance check."""
    sub: str                                              # the subaccount (one of the bot's Pots)
    t0: float                                             # epoch of the record value0 is from
    value0: float                                         # the pot's money then ($)
    settled: float                                        # its settled $ after t0, up to `upto` (fees in)
    markets: int                                          # how many markets that is
    tickers: frozenset = frozenset()                      # the markets it settled after t0
    since: str = ""                                       # 'its start', 'its last sizing' ...
    part: str = ""                                        # a two-pot bot's name for this pot ('currencies')
    last_t: Optional[float] = None                        # epoch of its newest fill or settle up to `upto`


@dataclass(frozen=True)
class Bot:
    name: str
    label: str                                            # SPEC label ('Pin bot')
    short: str                                            # tgcharts.BOT_SHORT / pinphone.SPEED_LABEL
    word: str                                             # pinphone.BOT_WORD ('pin bot')
    what: str                                             # SPEC what
    help: tuple                                           # pinphone.HELP_BOT_LINES lines
    command: str                                          # pinphone.BOT_CMD_OF
    commands: tuple                                       # every alias, in order
    pots: tuple                                           # its main pot first
    script: str
    is_live: Callable[[list], bool]
    stop_file: str
    logs: Logs
    records: Records
    settings: Callable[[SettingsIn], tuple]
    version: VersionRule
    colour: str
    order: int
    keepalive: Optional[str] = None
    unit: str = "market"
    goal_pct: Optional[float] = None
    always_shown: bool = False
    retired: bool = False
    page: Optional[str] = None
    extra_commands: tuple = ()
    page_footer: Optional[str] = None
    activity: Optional[Callable] = None
    activity_note: Optional[Callable] = None
    halt_why: Optional[Callable[[dict], str]] = None
    funds_size: Optional[Callable[[SizeIn], Optional[str]]] = None   # /funds' bet-size reader (FUNDS_SIZE_BOTS)
    speed: Optional[Speed] = None
    features: tuple = ()
    pot_word: Optional[str] = None                        # pinphone._POT_WORD when not `word` (step 5)
    ledger_book: Optional[str] = None                     # pinday.book_of's name for its markets (step 5)
    start: Optional[Start] = None                         # /resume's start recipe when keepalive is None (step 12)
    # v-tg-rebuild step 12, lane Q (2026-10-30): what the phone's monitor reads from the bot's own log
    stop_gauges: Optional[Callable] = None                # (WatchIn) -> [Gauge]: its stops, for the early warnings
    books: Optional[Callable] = None                      # (WatchIn, upto) -> [Book]: its pots as its own log has them
