"""context.py -- Ctx: everything a phone command reads, in one object (DESIGN section 2: phone/context.py).

v-tg-rebuild step 9 (2026-10-30). A command module (research/phone/commands/<x>.py) gets a Ctx and nothing else: no
Phone `self`, no module globals of pinphone reached by name. Until the integration flip (step 10) the Ctx is built FROM
a Phone (Ctx.from_phone): every seam is the very value that Phone holds, and every provider applies the very default
the old Phone.text_* method applied, AT CALL TIME (a module global the self-test or the golden harness patches --
pinphone.machine_read, kalshi_ping, python_procs ... -- is looked up on the old module when the provider runs, exactly
when the old method looked it up). So a new handler sees exactly what the old method saw. FakeCtx is a Ctx for unit
tests: plant what the command reads; anything not planted raises CtxMissing (a test never reads the real machine).

THE FIELDS (the Phone attribute each one is, in from_phone)
  the message      cmd ('/today': lower-case, '@bot' cut), arg (the rest, as typed), text (the whole, stripped),
                   chat_id
  pp               the helpers module: the runtime's `pp` attribute (phone.app.Phone.pp = phone.shared since step 11), else
                   the Phone's own module (a legacy Phone: pinphone_legacy): the helpers and constants not moved out yet
                   (ctx.pp.usd, ctx.pp.nice_coin, ...)
  ledger           pindesk.Ledger (Phone.ledger; the router refreshes it before the command runs)
  results          the results folder the ledger reads (ledger.results)
  now_fn           Phone.now                  -> ctx.now()
  health_fn        Phone.health_fn            -> ctx.health()
  procs_fn         Phone.procs_fn             -> ctx.procs(), ctx.procs_cached()
  versions_path    Phone.versions_path        (VERSIONS.md; the self-test plants its own)
  race30_epoch     Phone.race30_epoch
  bs_getter        Phone.bs_getter            (botstats' Kalshi getter; None = botstats' own)
  bs_procs         Phone.bs_procs             (botstats' process table / reader; None = botstats' own)
  funds_getter     Phone.funds_getter         -> ctx.funds_get()
  bars_fn          Phone.bars_fn              (/bars' planted text; None = research/bars.py)
  chart_fn         Phone.chart_fn             (None = tgcharts.build)
  chart_stale_s    Phone.chart_stale_s        (None = tgcharts.STALE_S)
  machine_fn       Phone.machine_fn           -> ctx.machine()
  ping_fn          Phone.ping_fn              -> ctx.ping()
  pots_fn          Phone.pots_fn              -> ctx.pots()
  aws_http         Phone.aws_http             (pass as-is: aws_cost(now, http=ctx.aws_http))
  cfg, cfg_path    Phone.cfg, Phone.cfg_path  (telegram.json's dict and where it is saved)
  say              Phone.say                  (a worker's later messages: controls, /update)
  state            the runtime's mutable state: muted, busy, _bars_d, _updating, _exit_now ... (from_phone: the Phone
                   itself until step 11 moves that state into phone/app.py). Read and write it ONLY for the state the
                   old method wrote (self.muted = True -> ctx.state.muted = True).

THE PROVIDERS (each one the old method's expression, verbatim)
  now()            self.now()
  health()         self.health_fn()
  procs()          self.procs_fn()
  procs_cached()   cached_python_procs() if self.procs_fn is python_procs else self.procs_fn()   (/racestats)
  bs()             _bs(): the botstats module, imported late (a broken botstats costs only the pages that need it)
  bs_get(name)     self._bs_get(name): botstats.all_bots(...) for 'all', else botstats.bot(name, ...)
  active()         self.active(): botstats.active_bots(procs=bs_procs); any error -> every bot (logged)
  funds_get()      self.funds_getter or _bs().default_getter()
  machine()        (self.machine_fn or machine_read)()
  ping()           (self.ping_fn or kalshi_ping)()
  pots()           (self.pots_fn or _bs().cached_pots)()
  sides()          self._sides()
  markets()        self._markets()
"""
import os
import sys
import traceback

from phone.log import log


class CtxMissing(LookupError):
    """FakeCtx: the command read something the test did not plant."""


_SEAMS = ("health_fn", "procs_fn", "versions_path", "race30_epoch", "bs_getter", "bs_procs", "funds_getter", "bars_fn",
          "chart_fn", "chart_stale_s", "machine_fn", "ping_fn", "pots_fn", "aws_http", "cfg", "cfg_path")
FIELDS = ("cmd", "arg", "text", "chat_id", "pp", "ledger", "results", "now_fn") + _SEAMS + ("say", "state")


def split_command(text):
    """(text stripped, cmd, arg) exactly as Phone.handle splits a message: '/Stop@kalsbot yes' -> ('/stop', 'yes')."""
    text = (text or "").strip()
    cmd, _, arg = text.partition(" ")
    return text, cmd.lower().split("@")[0], arg


class Ctx:
    """What a command reads. Build it with Ctx.from_phone(phone, text) (steps 9-10) or FakeCtx(...) (tests)."""

    def __init__(self, **kw):
        bad = sorted(set(kw) - set(FIELDS))
        if bad:
            raise TypeError("Ctx: unknown field(s) %s" % ", ".join(bad))
        for k in FIELDS:
            setattr(self, k, kw.get(k))
        if self.cmd is None:
            self.cmd = ""
        if self.arg is None:
            self.arg = ""
        if self.text is None:
            self.text = ""
        if self.results is None and self.ledger is not None:
            self.results = getattr(self.ledger, "results", None)

    @classmethod
    def from_phone(cls, phone, text="", chat_id=None):
        """The Ctx for one message to `phone` (a pinphone.Phone): every seam is the value the Phone holds right now."""
        text, cmd, arg = split_command(text)
        kw = {k: getattr(phone, k) for k in _SEAMS}
        # pp: the module of helpers the commands reach as ctx.pp -- the runtime names it (phone.app.Phone.pp =
        # phone.shared, rebuild step 11); an older Phone (pinphone_legacy's) is its own module
        pp = getattr(phone, "pp", None) or sys.modules[type(phone).__module__]
        return cls(cmd=cmd, arg=arg, text=text, chat_id=phone.chat_id if chat_id is None else chat_id,
                   pp=pp, ledger=phone.ledger, results=phone.ledger.results,
                   now_fn=phone.now, say=phone.say, state=phone, **kw)

    def with_message(self, text, chat_id=None):
        """The same context for another message (the same seams)."""
        kw = {k: getattr(self, k) for k in FIELDS}
        kw["text"], kw["cmd"], kw["arg"] = split_command(text)
        if chat_id is not None:
            kw["chat_id"] = chat_id
        return type(self)(**kw)

    # ---- providers: the old Phone expressions, verbatim, resolved at call time -----------------------------------
    def now(self):
        return self.now_fn()

    def health(self):
        return self.health_fn()

    def procs(self):
        return self.procs_fn()

    def procs_cached(self):
        pp = self.pp
        return pp.cached_python_procs() if self.procs_fn is pp.python_procs else self.procs_fn()

    def bs(self):
        """botstats, imported late: a broken edit there costs these commands, never the phone. (pinphone._bs)"""
        import botstats
        return botstats

    def bs_get(self, name):
        """botstats' dict for one bot, or for 'all'. Kalshi is read at most once a minute. (Phone._bs_get)"""
        bs = self.bs()
        if name == "all":
            return bs.all_bots(now=self.now(), getter=self.bs_getter, procs=self.bs_procs)
        return bs.bot(name, now=self.now(), getter=self.bs_getter, procs=self.bs_procs)

    def active(self):
        """The bots shown now (v-tg-active): botstats.active_bots -- a live copy running and no stop file; the pin bot
        always. Fail-safe: any error shows every bot (a command never dies on it). (Phone.active)"""
        bs = self.bs()
        try:
            return tuple(bs.active_bots(procs=self.bs_procs))
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            return tuple(bs.BOTS)

    def funds_get(self):
        return self.funds_getter or self.bs().default_getter()

    def machine(self):
        return (self.machine_fn or self.pp.machine_read)()

    def ping(self):
        return (self.ping_fn or self.pp.kalshi_ping)()

    def pots(self):
        return (self.pots_fn or self.bs().cached_pots)()

    def sides(self):
        """{ticker: entry side} from the bot's own records: a hedge record names the side the hedge BOUGHT, so the entry
        is the other one; markets with no hedge record take the ledger's `want`. (Phone._sides)"""
        out = {}
        for g in self.ledger.hedges:
            if g.get("tk") and g.get("side") in ("yes", "no"):
                out[g["tk"]] = "no" if g["side"] == "yes" else "yes"
        for x in self.ledger.settled:
            if x.get("tk") and x["tk"] not in out and x.get("want") in ("yes", "no"):
                out[x["tk"]] = x["want"]
        return out

    def markets(self):
        """(Phone._markets)"""
        pp = self.pp
        return pp.markets_from(pp.raw_ledger(os.path.join(self.ledger.results, pp.pinday.LEDGER_NAME)), self.sides())


class _Unplanted:
    """FakeCtx's stand-in for anything not planted: reading it raises CtxMissing naming the field."""

    def __init__(self, name):
        self._name = name

    def __getattr__(self, attr):
        raise CtxMissing("FakeCtx: %s.%s was not planted" % (self._name, attr))

    def __call__(self, *a, **k):
        raise CtxMissing("FakeCtx: %s was not planted" % self._name)

    def __bool__(self):
        raise CtxMissing("FakeCtx: %s was not planted" % self._name)


class FakeCtx(Ctx):
    """A Ctx for unit tests. Plant what the command reads:

        FakeCtx(text="/hedges", now=T, ledger=fake_ledger)            # now= a number -> a frozen clock
        FakeCtx(text="/bots", now=T, bs_get={"all": {...}}, active=("pin",), pp=pinphone)

    Extra plantings (besides every Ctx field): now (epoch), active (tuple), bs_get ({name: dict} or a function),
    health / machine / ping / pots (the value returned), bs (a module or namespace), sides / markets (the value).
    A field not planted is an object that raises CtxMissing when used; `pp` not planted likewise (plant the pinphone
    module, or a SimpleNamespace with just the helpers the command uses)."""

    _VALUES = ("active", "bs_get", "health", "machine", "ping", "pots", "bs", "sides", "markets")

    def __init__(self, now=None, **kw):
        planted = {k: kw.pop(k) for k in list(kw) if k in self._VALUES}
        if now is not None and "now_fn" not in kw:
            kw["now_fn"] = (lambda t=float(now): t)
        if "text" in kw and "cmd" not in kw:
            kw["text"], kw["cmd"], kw["arg"] = split_command(kw["text"])
        fields = {k: kw.get(k, _Unplanted(k)) for k in FIELDS}
        for k in ("cmd", "arg", "text"):
            if isinstance(fields[k], _Unplanted):
                fields[k] = ""
        if isinstance(fields["results"], _Unplanted) and not isinstance(fields["ledger"], _Unplanted):
            fields["results"] = getattr(fields["ledger"], "results", None)
        if isinstance(fields["chat_id"], _Unplanted):
            fields["chat_id"] = None
        super().__init__(**fields)
        self._planted = planted
        self.said = []                       # what say() was asked to send, when say was not planted
        if kw.get("say") is None:
            self.say = lambda text, chat_id=None: self.said.append((chat_id, text))

    def _value(self, name):
        if name not in self._planted:
            raise CtxMissing("FakeCtx: %s() was not planted" % name)
        return self._planted[name]

    def active(self):
        return tuple(self._value("active"))

    def bs_get(self, name):
        v = self._value("bs_get")
        return v(name) if callable(v) else v[name]

    def bs(self):
        return self._value("bs")

    def health(self):
        return self._value("health")

    def machine(self):
        return self._value("machine")

    def ping(self):
        return self._value("ping")

    def pots(self):
        return self._value("pots")

    def sides(self):
        return self._value("sides") if "sides" in self._planted else Ctx.sides(self)

    def markets(self):
        return self._value("markets")
