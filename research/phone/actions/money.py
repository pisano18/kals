"""phone/actions/money.py -- move money between the account's pots from the phone. THE ONLY PHONE CODE THAT POSTS TO KALSHI.

v-tg-step12 (2026-10-30, lane R; the operator: "telegram controls so I can see each subaccount and send commands to move
money between them myself through telegram ... and everything that needs to would adapt and react to that
automatically"). Until now ordercli.py was the repo's only sender of a non-GET request; this module reuses its transfer
builders and checks (ordercli.build_sub_transfer / check_sub_transfer, build_transfer / check_transfer) and adds the
phone's own rails. phone/tests/test_actions_safety.py holds every other phone file to no POST.

TWO PATHS, NOTHING ELSE (ALLOWED_POST; post() refuses any other path and any body that is not exactly the transfer):
  POST /portfolio/subaccounts/transfer               one pool, pot -> pot   {client_transfer_id, from_subaccount,
                                                                            to_subaccount, amount_cents, exchange_index}
  POST /portfolio/intra_exchange_instance_transfer   the main account, pool -> pool (ordercli.build_transfer: centicents)

THE RAILS, checked on the plan and again just before sending (the source cash is read again then):
  - an amount from $0.01 to MAX_MOVE_USD ($500) a move, and at most MAX_DAY_USD ($1,000) moved per ET day (counted from
    results\\phone_actions.jsonl, so a restart does not reset it); telegram.json may set move_max_usd, move_day_max_usd,
    move_margin_usd;
  - the source has the cash (a cash read that failed refuses: never blind);
  - a pot holding open bets keeps in cash at least what those bets cost + MARGIN_USD ($2): a move never leaves a bot's
    open bets short;
  - only accounts and pools Kalshi lists (no new subaccount), two different pots, the same pool for a pot -> pot move
    (a move across pools goes through the main account: two commands);
  - ordercli's own checks (subaccount 0..63, positive whole cents / centicents, the source's balance).
IDEMPOTENT: client_transfer_id is ordercli's uuid5 of the move, keyed on the UTC day, the pool and the plan's own id, so
the same plan sent twice is the same transfer (Kalshi refuses the repeat), and the plan is taken once (confirm.take).

KEYS: kauth's (the very key the phone's signed GETs already load through kauth; nothing new is read); kauth.headers
signs 'timestamp + POST + /trade-api/v2/<path>'. No key, signature or header is ever logged, returned or said.
SEAM: SENDER(path, body) -> (status, body). The real one refuses under KALS_TESTING=1; the tests plant a recorder.
"""
import json
import time
import uuid

import bots as _bots
from botdata import paths as _paths

SUB_PATH = "/portfolio/subaccounts/transfer"
POOL_PATH = "/portfolio/intra_exchange_instance_transfer"
ALLOWED_POST = (SUB_PATH, POOL_PATH)
SUB_KEYS = {"client_transfer_id", "from_subaccount", "to_subaccount", "amount_cents", "exchange_index"}
POOL_KEYS = {"source", "destination", "amount", "source_exchange_shard", "destination_exchange_shard",
             "source_subaccount", "destination_subaccount"}
POOLS = (0, 2)                  # the pools the bots use: 0 (weather / FX pairs), 2 (crypto & commodities)
POOL_NAME = {0: "weather pool", 2: "crypto pool"}
MAX_MOVE_USD = 500.0
MAX_DAY_USD = 1000.0
MARGIN_USD = 2.0
POST_TIMEOUT_S = 20


class Refused(Exception):
    """A move the rails refuse (the words say why)."""


def _ordercli():
    import ordercli                                             # (late: it is a big module and only a move needs it)
    return ordercli


def limits(cfg=None):
    """(max a move, max a day, margin) in dollars: the defaults, or telegram.json's move_max_usd / move_day_max_usd /
    move_margin_usd when they are positive numbers."""
    cfg = cfg if isinstance(cfg, dict) else {}
    out = []
    for k, d in (("move_max_usd", MAX_MOVE_USD), ("move_day_max_usd", MAX_DAY_USD), ("move_margin_usd", MARGIN_USD)):
        try:
            v = float(cfg.get(k, d))
            out.append(v if v >= 0 else d)
        except (TypeError, ValueError):
            out.append(d)
    return tuple(out)


# ---- naming the pots --------------------------------------------------------------------------------------------------
def pot_label(sub, pool):
    """'Main account, crypto pool' / 'subaccount 3 (Jump band), crypto pool'."""
    names = [b.label for b in _bots.all_bots(retired=False) for p in b.pots if int(p.sub) == int(sub) and p.pool == pool]
    head = "Main account" if int(sub) == 0 else "subaccount %d" % int(sub)
    if names and int(sub) != 0:
        head += " (%s)" % " + ".join(names)
    return "%s, %s" % (head, POOL_NAME.get(pool, "pool %s" % pool))


def bots_in(sub, pool):
    return [b for b in _bots.all_bots(retired=False) for p in b.pots if int(p.sub) == int(sub) and p.pool == pool]


def word_of(sub, pool):
    """The word the operator types for this pot: 'main', a bot's command word ('jb', 'fx'), else 'sub4'."""
    if int(sub) == 0:
        return "main"
    for b in _bots.all_bots(retired=False):
        p = b.pots[0]
        if int(p.sub) == int(sub) and p.pool == pool:
            return b.command.lstrip("/")
    return "sub%d" % int(sub)


def parse_pot(word):
    """A typed pot -> (sub, pool or None). 'main' / 'pin' / '0' -> (0, None); a bot's word -> its first pot;
    'sub3' / '3' -> (3, None); 'pool0' / 'pool2' -> (0, pool). Raises Refused."""
    w = str(word or "").strip().lower().lstrip("/")
    if w in ("main", "0", "sub0", "pin"):
        return 0, None
    if w.startswith("pool") and w[4:].isdigit():
        return 0, int(w[4:])
    if w.startswith("sub") and w[3:].isdigit():
        return int(w[3:]), None
    if w.isdigit():
        return int(w), None
    for b in _bots.all_bots(retired=False):
        if w in [b.name] + [c.lstrip("/") for c in tuple(b.commands) + tuple(b.extra_commands)]:
            p = b.pots[0]
            return int(p.sub), p.pool
    raise Refused("no pot is called '%s' (main, a bot: jb fx ladder fc race, subN, or pool0 / pool2)" % w)


def parse_amount(word):
    try:
        v = float(str(word).replace("$", "").replace(",", ""))
    except ValueError:
        raise Refused("'%s' is not an amount in dollars" % word)
    if not (v == v) or v < 0.01:
        raise Refused("the amount must be at least $0.01")
    return round(v, 2)


# ---- the plan ---------------------------------------------------------------------------------------------------------
def cash(funds, sub, pool):
    """Kalshi's cash in (sub, pool) from a funds_read() result, or None (not listed / not read)."""
    s = (funds.get("subs") or {}).get(int(sub)) or {}
    p = (s.get("pools") or {}).get(int(pool)) or {}
    return p.get("dollars")


def listed(funds, sub, pool):
    return int(pool) in (((funds.get("subs") or {}).get(int(sub)) or {}).get("pools") or {})


def open_cost(funds, sub):
    """(dollars, error): what the pot's open bets cost (funds_read: per account)."""
    s = (funds.get("subs") or {}).get(int(sub)) or {}
    if s.get("open") is None:
        return None, s.get("open_err") or "not read"
    return float(s["open"]), None


def trades_in(sub):
    """The pool the bots of account `sub` trade in (bots.cash_pool), or None for an account no bot uses."""
    try:
        return _bots.cash_pool(str(int(sub)))
    except KeyError:
        return None


def plan_move(words, funds, cfg=None, now=None, moved_today=0.0, plan_id=None):
    """The move '/move <amount> <from> <to> [<to pool>]' asks for, checked: a dict, or Refused with the reasons."""
    now = time.time() if now is None else float(now)
    if len(words) not in (3, 4):
        raise Refused("say it as /move 50 main jb (amount, from, to)")
    amount = parse_amount(words[0])
    if len(words) == 4:                                         # '/move 20 main pool0 pool2'
        if parse_pot(words[1])[0] != 0:
            raise Refused("a move between pools is the main account's only: /move 20 main pool0 pool2")
        src, dst = parse_pot(words[2]), parse_pot(words[3])
        if src[1] is None or dst[1] is None:
            raise Refused("name both pools: /move 20 main pool0 pool2")
    else:
        src, dst = parse_pot(words[1]), parse_pot(words[2])
    kind = "pool" if (src[0] == dst[0] == 0 and src[1] is not None and dst[1] is not None) else "sub"
    if kind == "sub":
        if src[0] == dst[0]:
            raise Refused("that is the same account; between the main account's pools: /move 20 main pool0 pool2")
        # a subaccount named by number ('sub4') means the pool its bots trade in; the main account takes the other side's
        src, dst = [(s_, p_ if p_ is not None or s_ == 0 else trades_in(s_)) for s_, p_ in (src, dst)]
        pools = {p for p in (src[1], dst[1]) if p is not None}
        if len(pools) > 1:
            raise Refused("those pots trade in different pools (%s): move it to the main account first, then across "
                          "pools (/move N main pool%d pool%d), then on" % (
                              " and ".join(POOL_NAME.get(p, str(p)) for p in sorted(pools)), src[1], dst[1]))
        pool = pools.pop() if pools else (trades_in(dst[0] if dst[0] else src[0]) or 2)
        src, dst = (src[0], pool), (dst[0], pool)
    for s_, p_ in (src, dst):
        if p_ not in POOLS:
            raise Refused("pool %s is not one the bots use (%s)" % (p_, ", ".join(str(x) for x in POOLS)))
        if not listed(funds, s_, p_):
            raise Refused("Kalshi does not list %s (the phone moves money only between pots that exist)"
                          % pot_label(s_, p_))
    plan_id = plan_id or uuid.uuid4().hex[:12]
    oc = _ordercli()
    if kind == "sub":
        day = "%s|pool%d|%s" % (time.strftime("%Y-%m-%d", time.gmtime(now)), src[1], plan_id)
        body = oc.build_sub_transfer(amount, src[0], dst[0], day)
        body["exchange_index"] = src[1]
        path = SUB_PATH
    else:
        body = oc.build_transfer(amount, src[1], dst[1])
        path = POOL_PATH
    plan = {"id": plan_id, "kind": kind, "amount": amount, "src": src, "dst": dst, "path": path, "body": body,
            "src_cash": cash(funds, *src), "dst_cash": cash(funds, *dst), "t": now}
    plan["open"], plan["open_err"] = open_cost(funds, src[0])
    bad = check(plan, plan["src_cash"], plan["dst_cash"], cfg, moved_today)
    if bad:
        raise Refused("; ".join(bad))
    return plan


def keep_of(plan, cfg=None):
    """What the source pool must keep in cash: its open bets' cost + the margin, when the pool is the one its bots trade
    in and it holds open bets; else 0."""
    _mx, _day, margin = limits(cfg)
    s_sub, s_pool = plan["src"]
    if plan.get("open") and trades_in(s_sub) in (None, s_pool):
        return round(float(plan["open"]) + margin, 2)
    return 0.0


def check(plan, src_cash, dst_cash, cfg=None, moved_today=0.0):
    """Every rail, as a list of reasons (empty = may send)."""
    mx, day_max, _margin = limits(cfg)
    bad = []
    a = float(plan["amount"])
    if a > mx + 1e-9:
        bad.append("at most $%.2f a move (asked $%.2f)" % (mx, a))
    if moved_today + a > day_max + 1e-9:
        bad.append("at most $%.2f a day: $%.2f moved today already" % (day_max, moved_today))
    if src_cash is None:
        bad.append("the source's cash could not be read -- refusing blind")
    elif a > src_cash + 1e-9:
        bad.append("the source holds $%.2f" % src_cash)
    if plan.get("open") is None:
        bad.append("the source's open bets could not be read (%s) -- refusing blind" % plan.get("open_err"))
    elif src_cash is not None:
        keep = keep_of(plan, cfg)
        if keep and src_cash - a < keep - 1e-9:
            bad.append("it would leave %s $%.2f in cash, under its open bets' cost $%.2f + $%.2f margin"
                       % (pot_label(*plan["src"]), src_cash - a, float(plan["open"]), keep - float(plan["open"])))
    oc = _ordercli()
    if plan["kind"] == "sub":
        b = plan["body"]
        bad += [x for x in oc.check_sub_transfer(b, src_cash, dst_cash) if not x.startswith("exchange_index")
                and not x.startswith("amount exceeds")]
        if b.get("exchange_index") not in POOLS:
            bad.append("pool %s is not one the bots use" % b.get("exchange_index"))
        if int(b["amount_cents"]) != int(round(a * 100)):
            bad.append("the transfer's cents do not match the amount")
    else:
        bad += [x for x in oc.check_transfer(plan["body"], src_cash) if not x.startswith("amount $")
                and not x.startswith("source pool balance unreadable")]
    return bad


# ---- sending ----------------------------------------------------------------------------------------------------------
def _signed_post(path, body):
    """POST `body` (JSON) to Kalshi at /trade-api/v2<path>, signed with kauth's key. (status, parsed body or text)."""
    if path not in ALLOWED_POST:
        raise Refused("refused: %s is not a transfer path" % path)
    if _paths.testing():
        return -1, "refused: KALS_TESTING=1 (a test never sends a POST)"
    import urllib.error
    import urllib.request
    import kauth
    full = kauth.PREFIX + path
    hd = dict(kauth.headers("POST", full))
    hd["Content-Type"] = "application/json"
    req = urllib.request.Request(kauth.BASE + full, data=json.dumps(body).encode(), method="POST", headers=hd)
    try:
        with urllib.request.urlopen(req, timeout=POST_TIMEOUT_S) as r:
            raw = r.read().decode("utf-8", "replace")
            st = r.status
    except urllib.error.HTTPError as e:
        raw, st = e.read().decode("utf-8", "replace")[:400], e.code
    except Exception as e:                                      # noqa: BLE001
        return -1, ("could not reach Kalshi: %s" % type(e).__name__)
    try:
        return st, json.loads(raw)
    except ValueError:
        return st, raw[:400]


SENDER = _signed_post


def post(path, body):
    """The one door: the path must be a transfer path and the body exactly that transfer's fields."""
    if path not in ALLOWED_POST:
        raise Refused("refused: %s is not a transfer path" % path)
    keys = set(body) if isinstance(body, dict) else set()
    if keys != (SUB_KEYS if path == SUB_PATH else POOL_KEYS):
        raise Refused("refused: the body is not a transfer (%s)" % sorted(keys))
    if path == POOL_PATH and (body.get("source_subaccount") != 0 or body.get("destination_subaccount") != 0
                              or body.get("source") != "event_contract" or body.get("destination") != "event_contract"):
        raise Refused("refused: a pool move is the main account's event-contract cash only")
    return SENDER(path, body)


def read_cash(getter, sub, pool):
    """One pot's cash now: GET /portfolio/balance {subaccount, exchange_index} -> balance_dollars, or None."""
    try:
        st, d = getter("/portfolio/balance", {"subaccount": int(sub), "exchange_index": int(pool)})
    except Exception:                                           # noqa: BLE001
        return None
    if st != 200 or not isinstance(d, dict):
        return None
    try:
        return float(d["balance_dollars"])
    except (KeyError, TypeError, ValueError):
        return None


def execute(plan, getter, cfg=None, moved_today=0.0, sleep=time.sleep):
    """Check again on fresh cash, send, read back. Returns {"ok", "status", "answer", "before", "after", "why"}."""
    before = (read_cash(getter, *plan["src"]), read_cash(getter, *plan["dst"]))
    bad = check(plan, before[0], before[1], cfg, moved_today)
    if bad:
        return {"ok": False, "status": None, "answer": None, "before": before, "after": None, "why": "; ".join(bad)}
    st, ans = post(plan["path"], plan["body"])
    ok = st in (200, 201)
    sleep(2)                                    # read back either way: a timed-out POST may still have moved the money
    after = (read_cash(getter, *plan["src"]), read_cash(getter, *plan["dst"]))
    why = None
    if not ok:
        why = ("Kalshi did not answer (%s) -- check the cash below before trying again" % str(ans)[:120] if st == -1
               else "Kalshi answered %s: %s" % (st, str(ans)[:200]))
    return {"ok": ok, "status": st, "answer": ans if not ok else None, "before": before, "after": after, "why": why}
