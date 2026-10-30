"""kalshi.py -- every Kalshi read botstats makes (GET only, through `getter`), and botstats_cache.json.

What is asked: per pot /portfolio/settlements (paged, append-only rows), /portfolio/positions and /portfolio/balance
(its trading pool, tables.SUB_POOL), and four account-wide listings (transfers, cash by pool, deposits, withdrawals),
at most every REFRESH_S. Every request names its subaccount. The cache: rows trimmed to KEEP, when each pot was read,
whether its whole history was walked, the last pass where every pot read ('good'), botstats' process table.

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata).
Added here (no output change):
  LOCK       one lock around load + refresh + save (report._load, pot_settlements): the phone's poll thread and its
             chart thread used to refresh at once -- two Kalshi passes on a key the live bots share (429s) and two
             writers of the cache. A caller that arrives while a refresh is IN FLIGHT waits for it and then finds the
             cache just read (tried within REFRESH_S), so it asks Kalshi nothing: the calls coalesce into one.
  readonly   set_readonly(True) (or readonly=True on load): the cache is read but never refreshed (no getter is ever
             built, so no Kalshi request) and never written -- for a smoke run on the server's real data (DESIGN
             risk 3).
"""
import json
import os
import threading
import time

import pinledger
from botdata import paths as _paths
from botdata import pots as _pots
from botdata import tables as _tables


CACHE_NAME = "botstats_cache.json"

REFRESH_S = 60                  # Kalshi and the process table are re-read at most this often

PAGE = 200
MAX_PAGES = 200                 # 40,000 settlements a pot: a runaway pager stops loudly

# the only things this file ever asks Kalshi for -- every one a GET, through `getter`
POT_PATHS = ("/portfolio/settlements", "/portfolio/positions", "/portfolio/balance")    # each names its pot
# account-wide LISTINGS (2026-10-02, for the pot): (path, the list's key, paged?)
LEDGERS = (("/portfolio/subaccounts/transfers", "transfers", True),
           ("/portfolio/subaccounts/balances", "subaccount_balances", False),
           ("/portfolio/deposits", "deposits", True),
           ("/portfolio/withdrawals", "withdrawals", True))
LEDGER_PATHS = tuple(p for p, _, _ in LEDGERS)
PATHS = POT_PATHS + LEDGER_PATHS
LEDGER_PAGES = 50               # a runaway pager on a listing stops loudly
LEDGER_KEEP = {"transfers": ("amount_cents", "created_ts", "from_subaccount", "to_subaccount", "exchange_index",
                             "transfer_id"),
               "subaccount_balances": ("subaccount_number", "exchange_index", "balance", "updated_ts"),
               "deposits": ("amount_cents", "fee_cents", "status", "finalized_ts", "created_ts", "updated_ts", "id"),
               "withdrawals": ("amount_cents", "fee_cents", "status", "finalized_ts", "created_ts", "updated_ts",
                               "id")}

KEEP = ("ticker", "settled_time", "market_result", "value", "yes_count_fp", "no_count_fp",
        "yes_total_cost_dollars", "no_total_cost_dollars", "fee_cost", "revenue")

# ---- the cache and the Kalshi reads -----------------------------------------
_MEMO = {"key": None, "data": None}
# v-tg-rebuild step 7 (2026-10-30): one lock around load + refresh + save; a caller arriving during a refresh waits for
# it and finds the cache just read (no second Kalshi pass). Re-entrant: report._load holds it around procs_for too.
LOCK = threading.RLock()
_RO = {"on": False}                     # readonly: never refresh (no getter, no request), never write the cache


def set_readonly(on=True):
    """Read the cache only: no Kalshi request, no write (a smoke run on real data). Returns the old setting."""
    old, _RO["on"] = _RO["on"], bool(on)
    return old


def is_readonly():
    return _RO["on"]


def load(now, getter=None, readonly=None):
    """(c, changed): the cache, brought up to date from Kalshi (at most every REFRESH_S) and saved when anything was
    read -- all under LOCK, so concurrent callers make ONE pass. readonly (default: set_readonly's) reads the cache as it
    is: no request, no write."""
    ro = _RO["on"] if readonly is None else bool(readonly)
    with LOCK:
        c = load_cache()
        if ro:
            return c, False
        changed = refresh(c, now, getter)
        if changed:
            save_cache(c)
        return c, changed


def cache_path():
    return os.path.join(_paths.RESULTS, CACHE_NAME)


def load_cache():
    p = cache_path()
    try:
        st = os.stat(p)
        key = (p, st.st_mtime, st.st_size)
        if _MEMO["key"] == key:
            return json.loads(json.dumps(_MEMO["data"]))         # a private copy
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        if not isinstance(d, dict):
            raise ValueError("not a dict")
        _MEMO.update(key=key, data=d)
        return json.loads(json.dumps(d))
    except (OSError, ValueError):
        return {"v": 1, "subs": {}, "procs": None}


def save_cache(c):
    p = cache_path()
    c["written"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    tmp = "%s.%d.tmp" % (p, os.getpid())
    try:
        # v-tg-rebuild step 2 (2026-10-30): under KALS_TESTING=1 the LIVE cache is never written (a test that patched a
        # dead name would overwrite it); WriteFenced is an OSError, so this returns False like any failed write
        _paths.check_write(p)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(c, fh, separators=(",", ":"))
        for _ in range(3):
            try:
                os.replace(tmp, p)
                st = os.stat(p)
                _MEMO.update(key=(p, st.st_mtime, st.st_size), data=json.loads(json.dumps(c)))
                return True
            except PermissionError:          # a reader on Windows holds it open; the next call retries
                time.sleep(0.2)
    except OSError:
        pass
    try:
        os.remove(tmp)
    except OSError:
        pass
    return False


def default_getter():
    """kauth.get: signed, and GET only by construction (kauth has no other method)."""
    import kauth

    def get(path, params):
        # 2026-10-22: Kalshi answers 429 when the live bots and this read land in the same second (the cash
        # reads failed that way all morning, so every bot's '% of its bank' was blank). Retry, then give up.
        for k in range(4):
            st, body = kauth.get(path, params)
            if st != 429:
                return st, body
            time.sleep(0.8 * (k + 1))
        return st, body
    return get


def fetch_settlements(c, sub, getter):
    """Walk /portfolio/settlements for one pot. Until a walk has reached the end once, every walk
    is a full one (so a cut-short first walk is resumed, not trusted); after that it stops at the
    first page it already holds. Returns an error string or None."""
    rows = c.setdefault("rows", {})
    backfill = not c.get("complete")
    cursor, pages = None, 0
    while True:
        q = {"limit": PAGE, "subaccount": sub}
        if cursor:
            q["cursor"] = cursor
        st, d = getter("/portfolio/settlements", q)
        pages += 1
        if st != 200 or not isinstance(d, dict):
            return "settlements read failed (HTTP %s)" % st
        got = d.get("settlements") or []
        new = 0
        for s in got:
            if not isinstance(s, dict):
                continue
            k = pinledger.key_of(s)
            if k not in rows:            # append-only: Kalshi's record of a settlement never changes
                rows[k] = {f: s[f] for f in KEEP if f in s}
                new += 1
        cursor = d.get("cursor")
        if not got or not cursor:
            c["complete"] = True
            return None
        if not backfill and new == 0:
            return None
        if pages >= MAX_PAGES:
            return "settlements: stopped after %d pages without reaching the end" % pages


def fetch_positions(sub, getter):
    st, d = getter("/portfolio/positions", {"subaccount": sub, "settlement_status": "unsettled",
                                            "count_filter": "position", "limit": PAGE})
    if st != 200 or not isinstance(d, dict) or not isinstance(d.get("market_positions"), list):
        return None, "positions read failed (HTTP %s)" % st
    out = []
    for x in d["market_positions"]:
        if not isinstance(x, dict):
            continue
        tk = x.get("ticker") or x.get("market_ticker")
        n = pinledger.money(x, "position_fp", "position")
        if not tk or abs(n) < 1e-9:
            continue
        out.append({"ticker": tk, "net": n,
                    "at_risk": pinledger.money(x, "market_exposure_dollars"),
                    "fees": pinledger.money(x, "fees_paid_dollars")})
    return out, None


def fetch_balance(sub, getter):
    """balance_dollars is DOLLARS; `balance` is cents. The unit is read from the field name, never
    guessed from the size (hard rule 5), so a body with no balance_dollars is unreadable. The pool is
    the one this pot trades in (SUB_POOL): Kalshi answers for the named pool only."""
    st, d = getter("/portfolio/balance", {"subaccount": sub, "exchange_index": _tables.SUB_POOL[sub]})
    if st != 200 or not isinstance(d, dict) or "balance_dollars" not in d:
        return None, "balance read failed (HTTP %s)" % st
    try:
        return float(d["balance_dollars"]), None
    except (TypeError, ValueError):
        return None, "balance unreadable: %r" % d.get("balance_dollars")


def fetch_ledgers(getter):
    """The account's own books of money moving IN and BETWEEN pots, and every pot's cash in every pool:
    four GET listings, each walked to its end. All or nothing -- ({key: rows}, None) or (None, error):
    a pot worked out from half the books would be a guess. A listing whose key is missing is an error,
    not an empty list (a renamed field once read as 'no data' for 68 million rows)."""
    out = {}
    for path, key, paged in LEDGERS:
        rows, cursor = [], None
        for _ in range(LEDGER_PAGES if paged else 1):
            q = {"limit": PAGE} if paged else {}
            if cursor:
                q["cursor"] = cursor
            st, d = getter(path, q)
            name = path.rsplit("/", 1)[-1]
            if st != 200 or not isinstance(d, dict):
                return None, "%s read failed (HTTP %s)" % (name, st)
            got = d.get(key, "missing")
            if got is None:
                got = []
            if not isinstance(got, list):
                return None, "%s unreadable (no '%s' list)" % (name, key)
            rows += [{f: r[f] for f in LEDGER_KEEP[key] if f in r} for r in got if isinstance(r, dict)]
            cursor = d.get("cursor") if paged else None
            if not got or not cursor:
                break
        else:
            return None, "%s: stopped after %d pages without reaching the end" % (path.rsplit("/", 1)[-1],
                                                                                    LEDGER_PAGES)
        out[key] = rows
    return out, None


def refresh(c, now, getter):
    """Bring each pot up to date, at most once every REFRESH_S. Returns True when anything was read.
    The account-wide listings are read in the SAME pass as the pots (same `now`), so a pot's
    percentage is worked out from one consistent read or not at all."""
    subs = c.setdefault("subs", {})
    did = False
    led = c.setdefault("ledgers", {})
    # Another process sharing this cache (the desktop app, running an older botstats) may have read the
    # pots without the listings. A cache whose pots and listings are not from one pass is read again
    # whole, now -- otherwise the pot percentages could stay unknown for as long as it keeps doing that.
    aligned = led.get("tried") is not None and all(
        (subs.get(s) or {}).get("tried") == led.get("tried") for s in _tables.SUBS)
    for sub in _tables.SUBS:
        x = subs.setdefault(sub, {"rows": {}, "complete": False})
        if aligned and now - float(x.get("tried") or 0) < REFRESH_S:
            continue
        if getter is None:
            getter = default_getter()
        did = True
        x["tried"] = now
        err = fetch_settlements(x, sub, getter)
        x["err"] = err
        if err is None:
            x["fetched"] = now
        pos, perr = fetch_positions(sub, getter)
        x["pos_err"] = perr
        if pos is not None:
            x["positions"], x["pos_t"] = pos, now
        bal, berr = fetch_balance(sub, getter)
        x["bal_err"] = berr
        if bal is not None:
            x["balance"], x["bal_t"] = bal, now
    if did:
        led["tried"] = now
        got, lerr = fetch_ledgers(getter)
        led["err"] = lerr
        if got is not None:
            led.update(got)
            led["fetched"] = now
        _remember_good(c, now)
    return did


GOOD_MAX_S = 3 * 3600           # a failed read falls back to the last pass where EVERY pot read, if no older than this


def _remember_good(c, now):
    """2026-10-23: after a pass where every pot read, keep each pot's value at that one moment (c['good']). When a
    later read fails (the 10-23 21:4x connection trouble blanked every '% of its bank' and the pace chart),
    pot_context uses these instead of showing nothing, and says from when."""
    pots = {}
    for sub in _tables.SUBS:
        v, _why = _pots._pot_now(c, sub)
        if v is None:
            return False
        pots[sub] = round(v, 4)
    for sub in _tables.POT_POOL_ONLY:
        v, _why = _pots._pot_now(c, sub, own=True)
        if v is not None:
            pots[sub + ":own"] = round(v, 4)
    c["good"] = {"t": now, "pots": pots}
    return True


def pot_settlements(now=None, getter=None):
    """({pot: [settled rows]}, {pot: why not}): every pot's settlement rows from the cache, after the same refresh
    /bots and every chart make (Kalshi re-read at most every REFRESH_S). A pot is given only when its LATEST read
    reached Kalshi and its whole history is on file; any other pot is in the second dict, for the caller to read
    some other way. The process table is not read.

    2026-10-26, the operator: "check if ... you're collecting or doing something with the same data multiple times
    anywhere across the project". /funds paged every account's last 7 days of settlements from Kalshi itself (7
    GETs on the live books), seconds before its own picture refreshed this cache with the same rows; its past days
    read these now."""
    now = time.time() if now is None else float(now)
    c, _changed = load(now, getter)
    rows, why = {}, {}
    for sub in _tables.SUBS:
        x = (c.get("subs") or {}).get(sub) or {}
        if x.get("tried") is None:
            why[sub] = "Kalshi has not been read yet"
        elif x.get("err") or x.get("fetched") != x.get("tried"):
            why[sub] = x.get("err") or "the last settlements read failed"
        elif not x.get("complete"):
            why[sub] = "its history is still loading"
        else:
            rows[sub] = list((x.get("rows") or {}).values())
    return rows, why


def cached_pots():
    """Every pot's money as this cache holds it from the LAST Kalshi read, with NO read of its own: a page that must
    answer at once (the phone's /server, 2026-10-27) shows the cash /bots, /funds and the charts last saw, and when.
    {"pots": {sub: {"cash": its trading pool's balance_dollars, "cash_t", "open": what its open bets cost (fees in),
    "open_n", "value": _pot_now (cash in every pool + open bets, all from one read) or None, "why": why not, "t": when
    the pot was last read}}, "total": every pot's value added (None unless every pot has one), "t": the newest read}."""
    c = load_cache()
    pots = {}
    for sub in _tables.SUBS:
        x = (c.get("subs") or {}).get(sub) or {}
        ps = x.get("positions")
        v, why = _pots._pot_now(c, sub)
        pots[sub] = {"cash": x.get("balance"), "cash_t": x.get("bal_t"),
                     "open": (round(sum(float(p.get("at_risk") or 0.0) + float(p.get("fees") or 0.0) for p in ps), 4)
                              if isinstance(ps, list) else None),
                     "open_n": len(ps) if isinstance(ps, list) else None,
                     "value": None if v is None else round(v, 4), "why": why, "t": x.get("tried")}
    vals = [p["value"] for p in pots.values()]
    ts = [float(p["t"]) for p in pots.values() if p["t"]]
    return {"pots": pots, "total": round(sum(vals), 4) if all(v is not None for v in vals) else None,
            "t": max(ts) if ts else None}
