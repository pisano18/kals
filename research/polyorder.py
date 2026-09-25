#!/usr/bin/env python3
# VERSION: 2026-09-25-po1
"""polyorder.py -- the ORDER PATH for the operator's Polymarket US account.
The only file in this repo that can send a writing request to Polymarket US.

IT DOES NOTHING BY DEFAULT. Every invocation is a dry run: it builds the exact
order body, signs it with the real key (proving the key loads and signs), prints
it, and sends nothing. A live send needs --live AND --signoff <token>, where the
token is printed by the dry run of THAT order and is bound to the venue, base
URL, market, side, price, size, order style and intent id. Change any of them
and the token changes, so one sign-off authorises one order, once.

THE VENUE (primary sources, fetched 2026-09-25; see results/POLYMARKET_ORDERS.md)
  api.polymarket.us, QCX LLC -- the CFTC-licensed US exchange. Retail API:
    create   POST /v1/orders           (docs api-reference/orders/create-order)
    read     GET  /v1/order/{id}, GET /v1/orders/open?slugs=...
    account  GET  /v1/account/balances, /v1/portfolio/positions,
                  /v1/portfolio/activities
  Auth: Ed25519 over "{ms timestamp}{METHOD}{path}", path WITHOUT the query --
  the scheme C:\\kals\\poly_us.py already uses. THE SIGNATURE DOES NOT COVER
  THE BODY: anyone holding a fresh signature for the create route could send
  a different order with it inside the 30-second window. So this file never
  prints or logs a full signature.
  No idempotency key exists. The official SDK (polymarket-us 1.0.2,
  _retry.py) says so in as many words and never retries an order. So
  idempotency is OURS: every order carries an intent id, written to the ledger
  (fsync) BEFORE the request goes out, and an intent id is sent at most once,
  ever. A lost reply is resolved by READING THE ACCOUNT, never by re-sending.

HOW UP AND DOWN ARE SENT (docs orders/overview, "Understanding Price with
Order Intent"; confirmed on the operator's own filled order CPZBEBJ5YXPK)
  Only the long side (Up = YES) is an instrument. price.value is ALWAYS the
  Up price:
    buy Up   at p  ->  intent ORDER_INTENT_BUY_LONG,  price.value p
    buy Down at q  ->  intent ORDER_INTENT_BUY_SHORT, price.value (1 - q)
  The operator's real order: BUY_SHORT, price.value 0.12, avgPx 0.22, 2.52
  filled, fee $0.03 -- he bought Down at 0.78 (= 1 - 0.22) with a limit of
  0.88 (= 1 - 0.12). The position record shows avgPx 0.78: the POSITION is in
  Down terms, the ORDER is in Up terms. Mixing the two is the bug to avoid.
  Max loss of a Down buy at q is q (buying power falls by 1 - sale price).

THE RAILS (every one refuses BEFORE signing or sending)
  * entry only: BUY_LONG or BUY_SHORT, ORDER_TYPE_LIMIT. No sells, no market
    orders, no modify, no close-position, no cancel-all, no batches.
  * TIME_IN_FORCE_IMMEDIATE_OR_CANCEL always: take what is there at our
    limit, the rest dies. It never rests. The single exception is
    --post-only, which sends participateDontInitiate=true with a
    GOOD_TILL_DATE expiry <= MAX_REST_S seconds out, then cancels its OWN
    order and verifies. Built and fake-tested; never run live.
  * market slug must be a BTC up/down 15m or 1h window (the only contracts
    the operator's account offers); the market must read MARKET_STATUS_OPEN
    and its window must not have ended.
  * price in dollars, 0 < p < 1, never inferred from magnitude (CLAUDE.md
    rule 5: "97" is refused, not read as 97c); a multiple of the market's
    orderPriceMinTickSize; <= MAX_PRICE (98c, pinrun's ceiling).
  * quantity a positive multiple of minimumTradeQty, <= MAX_QTY.
  * worst case (qty x price + fee) <= MAX_COST per order.
  * per UTC day: money put at risk (filled cost + every unresolved order at
    its worst case) <= DAY_MAX_RISK; realised losses read from the exchange
    <= DAY_MAX_LOSS (an unreadable history REFUSES -- "could not read" is
    never "nothing lost"); <= MAX_SENDS_PER_DAY sends; <= MAX_SENDS_PER_SLUG
    per window.
  * an unresolved order (lost reply that reading could not settle, or an IOC
    that rested) HALTS every further send until --resolve settles it.
  * pre-send reads must all succeed: market, balances (buying power >= worst
    case), open orders (must be EMPTY -- this path never leaves one), the
    position in this market (the baseline a lost reply is resolved against).

    python research/polyorder.py --selftest
    python research/polyorder.py --show balance|positions|open|fills|resolutions
    python research/polyorder.py --show order --order-id ID
    python research/polyorder.py --slug cpc-btc-updown-15m-2026-09-25-1300z \\
        --side up --price 0.97 --qty 1                    # dry run
    python research/polyorder.py ... --live --signoff <token>   # operator only
    python research/polyorder.py --resolve <intent id>    # read-only
    python research/polyorder.py --ledger

Logs: results/polyorder-<UTC yyyymmdd>.jsonl -- every request and response
(key id masked, signature never written), every intent, refusal and result.
"""
import argparse
import ast
import base64
import calendar
import decimal
import email.utils
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

D = decimal.Decimal
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
CREDS = r"C:\kals\polymarket_key.json"
BASE = "https://api.polymarket.us"
VENUE = "polymarket-us"
ORDER_ROUTE = "/v1/orders"
SLUG_PREFIXES = ("cpc-btc-updown-15m-", "cpc-btc-updown-1h-")

# ---- HARD RAILS. Not arguments. Raising one is a code edit and a commit. ----
MAX_QTY = D("5")             # contracts per order
MAX_COST = D("5.00")         # dollars per order, worst case incl. fee
MAX_PRICE = D("0.98")        # never pay more than pinrun.PRICE_CEILING
MIN_PRICE = D("0.01")        # exchange floor
DAY_MAX_RISK = D("10.00")    # dollars put at risk per UTC day
DAY_MAX_LOSS = D("5.00")     # realised losses per UTC day, read from exchange
MAX_SENDS_PER_DAY = 20
MAX_SENDS_PER_SLUG = 1       # one order per window while testing
MAX_REST_S = 60              # --post-only only
MAX_CLOCK_SKEW_S = 10        # their tolerance is 30 s
TAKER_THETA = D("0.0695")    # docs fees.md, effective 2026-09-25
HTTP_TIMEOUT_S = 10
SYNC_BLOCK_S = "5"           # maxBlockTime, seconds (int64 as string)

INTENT_UP = "ORDER_INTENT_BUY_LONG"
INTENT_DOWN = "ORDER_INTENT_BUY_SHORT"
TIF_IOC = "TIME_IN_FORCE_IMMEDIATE_OR_CANCEL"
TIF_GTD = "TIME_IN_FORCE_GOOD_TILL_DATE"
BODY_KEYS = {"marketSlug", "intent", "type", "price", "quantity", "tif",
             "manualOrderIndicator", "synchronousExecution", "maxBlockTime",
             "participateDontInitiate", "goodTillTime"}
LIVE_STATES = {"ORDER_STATE_NEW", "ORDER_STATE_PARTIALLY_FILLED",
               "ORDER_STATE_PENDING_NEW", "ORDER_STATE_PENDING_REPLACE",
               "ORDER_STATE_PENDING_CANCEL", "ORDER_STATE_PENDING_RISK"}
FILL_EXEC = {"EXECUTION_TYPE_FILL", "EXECUTION_TYPE_PARTIAL_FILL"}
FINAL_EXEC = {"EXECUTION_TYPE_FILL", "EXECUTION_TYPE_CANCELED",
              "EXECUTION_TYPE_REJECTED", "EXECUTION_TYPE_EXPIRED",
              "EXECUTION_TYPE_DONE_FOR_DAY"}
STOPGAP_TEXT = "Global Rate Limit Exceeded"   # docs rate-limits: a LATENCY reject

CREATED_IDS = set()          # order ids THIS process created; only these may be cancelled


# ------------------------------------------------------------------ numbers
def dec(x):
    """Decimal from str/int/float without binary-float artefacts."""
    if isinstance(x, D):
        return x
    if isinstance(x, float):
        return D(repr(x))
    return D(str(x).strip())


def fmt(x):
    """Plain decimal string: D('0.03') -> '0.03', D('1.00') -> '1'."""
    s = format(dec(x).normalize(), "f")
    return s


def fee(price, qty):
    """Taker fee billed on an order: theta*C*p*(1-p), banker's rounding to the
    cent (docs fees.md). Symmetric in p, so Up or Down price gives the same."""
    p, c = dec(price), dec(qty)
    return (TAKER_THETA * c * p * (1 - p)).quantize(D("0.01"),
                                                     rounding=decimal.ROUND_HALF_EVEN)


def worst_case(order):
    """Most this order can lose: every contract filled at our limit, then lost."""
    return order["qty"] * order["price"] + fee(order["price"], order["qty"])


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def parse_ts(s):
    """'2026-09-25T05:53:50.065833315Z' -> epoch seconds (UTC). None if unreadable."""
    if not s:
        return None
    s = str(s).strip()
    for suf in ("Z", "+00:00"):
        if s.endswith(suf):
            s = s[:-len(suf)]
    frac = 0.0
    if "." in s:
        s, f = s.split(".", 1)
        digits = "".join(ch for ch in f if ch.isdigit())[:9]
        frac = float("0." + (digits or "0"))
    try:
        return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%S")) + frac
    except ValueError:
        return None


def utc_day(t):
    return time.strftime("%Y%m%d", time.gmtime(t))


# ------------------------------------------------------------------ the order
def make_order(slug, side, price, qty, post_only=False, rest_s=0, intent_id=None):
    """Our terms: side 'up'|'down', price = what WE pay for that side, in dollars."""
    o = {"slug": str(slug), "side": str(side).lower(), "price": dec(price),
         "qty": dec(qty), "post_only": bool(post_only),
         "rest_s": int(rest_s) if post_only else 0}
    if not intent_id:
        blob = "|".join((o["slug"], o["side"], fmt(o["price"]), fmt(o["qty"]),
                         "po%d" % o["rest_s"] if post_only else "ioc"))
        intent_id = "pi-" + hashlib.sha256(blob.encode()).hexdigest()[:12]
    o["intent_id"] = str(intent_id)
    return o


def long_price(order):
    """price.value on the wire: ALWAYS the Up price."""
    return order["price"] if order["side"] == "up" else (D(1) - order["price"])


def build_body(order, now):
    q = order["qty"]
    body = {
        "marketSlug": order["slug"],
        "intent": INTENT_UP if order["side"] == "up" else INTENT_DOWN,
        "type": "ORDER_TYPE_LIMIT",
        "price": {"value": fmt(long_price(order)), "currency": "USD"},
        "quantity": int(q) if q == q.to_integral_value() else float(q),
        "tif": TIF_IOC,
        "manualOrderIndicator": "MANUAL_ORDER_INDICATOR_AUTOMATIC",
        "synchronousExecution": True,
        "maxBlockTime": SYNC_BLOCK_S,
        "participateDontInitiate": False,
    }
    if order["post_only"]:
        body["tif"] = TIF_GTD
        body["participateDontInitiate"] = True
        body["synchronousExecution"] = False
        body.pop("maxBlockTime")
        body["goodTillTime"] = iso(now + order["rest_s"])
    return body


def token_for(order, base):
    """Sign-off token: bound to venue, base, and every field of the order.
    goodTillTime is excluded (it moves with the clock); rest_s is included."""
    static = {k: v for k, v in build_body(order, 0).items() if k != "goodTillTime"}
    blob = json.dumps({"venue": VENUE, "base": base, "slug": order["slug"],
                       "side": order["side"], "price": fmt(order["price"]),
                       "qty": fmt(order["qty"]), "post_only": order["post_only"],
                       "rest_s": order["rest_s"], "intent_id": order["intent_id"],
                       "body": static}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _multiple(x, step):
    try:
        return step > 0 and (x / step) == (x / step).to_integral_value()
    except (decimal.InvalidOperation, ZeroDivisionError):
        return False


def check_order(order, body, tick=D("0.01"), min_qty=D("0.01")):
    """Static rails. Returns a list of violations; empty means allowed."""
    bad = []
    s = order["slug"]
    if not any(s.startswith(p) for p in SLUG_PREFIXES) or len(s) > 60:
        bad.append("market %r is not a BTC up/down 15m or 1h window" % s)
    if order["side"] not in ("up", "down"):
        bad.append("side %r is not up or down" % order["side"])
    p, q = order["price"], order["qty"]
    if not (D(0) < p < D(1)):
        bad.append("price %s is not strictly between 0 and 1 dollars -- the unit "
                   "is dollars and is never inferred from the size of the "
                   "number" % p)
    else:
        if p < MIN_PRICE:
            bad.append("price %s below the exchange floor %s" % (p, MIN_PRICE))
        if p > MAX_PRICE:
            bad.append("price %s above MAX_PRICE %s" % (p, MAX_PRICE))
        if not _multiple(p, tick):
            bad.append("price %s is not a multiple of the market tick %s" % (p, tick))
        lp = long_price(order)
        if not (D("0.01") <= lp <= D("0.99")):
            bad.append("wire price %s outside the exchange's 0.01..0.99" % lp)
    if q <= 0:
        bad.append("quantity %s is not positive" % q)
    else:
        if q < min_qty:
            bad.append("quantity %s below the market minimum %s" % (q, min_qty))
        if not _multiple(q, min_qty):
            bad.append("quantity %s is not a multiple of the market minimum %s"
                       % (q, min_qty))
        if q > MAX_QTY:
            bad.append("quantity %s exceeds MAX_QTY %s" % (q, MAX_QTY))
    if D(0) < p < D(1) and q > 0 and worst_case(order) > MAX_COST:
        bad.append("worst case $%s exceeds MAX_COST $%s" % (worst_case(order), MAX_COST))
    # the body itself -- what actually goes on the wire
    extra = set(body) - BODY_KEYS
    if extra:
        bad.append("body carries fields this path never sends: %s" % sorted(extra))
    if body.get("intent") not in (INTENT_UP, INTENT_DOWN):
        bad.append("intent %r is not a BUY" % body.get("intent"))
    if body.get("type") != "ORDER_TYPE_LIMIT":
        bad.append("type %r is not ORDER_TYPE_LIMIT" % body.get("type"))
    want = INTENT_UP if order["side"] == "up" else INTENT_DOWN
    if body.get("intent") != want:
        bad.append("intent %s does not match side %s" % (body.get("intent"), order["side"]))
    try:
        if dec(body["price"]["value"]) != long_price(order):
            bad.append("wire price %s does not equal the Up-terms price %s"
                       % (body["price"]["value"], long_price(order)))
    except (KeyError, TypeError, decimal.InvalidOperation):
        bad.append("wire price missing or unreadable")
    if order["post_only"]:
        if body.get("tif") != TIF_GTD or body.get("participateDontInitiate") is not True:
            bad.append("post-only order is not GTD + participateDontInitiate")
        if not (1 <= order["rest_s"] <= MAX_REST_S):
            bad.append("rest %ss outside 1..%s" % (order["rest_s"], MAX_REST_S))
    else:
        if body.get("tif") != TIF_IOC:
            bad.append("tif %r is not IMMEDIATE_OR_CANCEL -- this order could REST"
                       % body.get("tif"))
        if body.get("participateDontInitiate") is not False:
            bad.append("participateDontInitiate is not False on a taking order")
    return bad


def check_market(m, now):
    """The market record from GET /v1/market/slug/{slug}. Returns (violations,
    tick, min_qty, window_end)."""
    bad = []
    if not isinstance(m, dict):
        return ["market record unreadable"], None, None, None
    if m.get("status") != "MARKET_STATUS_OPEN":
        bad.append("market status is %r, not MARKET_STATUS_OPEN" % m.get("status"))
    if m.get("closed") is True:
        bad.append("market is closed")
    apt = m.get("assetPriceTerms") or {}
    end = parse_ts(apt.get("windowEnd"))
    if end is None:
        bad.append("market has no readable windowEnd")
    elif now >= end - 1:
        bad.append("window ended at %s" % apt.get("windowEnd"))
    try:
        tick = dec(m.get("orderPriceMinTickSize"))
        mq = dec(m.get("minimumTradeQty"))
        if tick <= 0 or mq <= 0:
            raise decimal.InvalidOperation
    except (decimal.InvalidOperation, TypeError, ValueError):
        bad.append("market tick / minimum size unreadable")
        tick = mq = None
    return bad, tick, mq, end


# ------------------------------------------------------------------ signing
class Signer:
    def __init__(self, key_id, priv):
        self.key_id = key_id
        self.priv = priv

    @classmethod
    def from_secret(cls, key_id, secret_b64):
        from cryptography.hazmat.primitives.asymmetric import ed25519
        raw = base64.b64decode(secret_b64)
        return cls(key_id, ed25519.Ed25519PrivateKey.from_private_bytes(raw[:32]))

    @classmethod
    def from_creds(cls, path=CREDS):
        with open(path, encoding="utf-8-sig") as f:
            c = json.load(f)
        return cls.from_secret(c["key_id"], c["secret"])

    def headers(self, method, path, ts_ms=None):
        """Sign '{ts}{METHOD}{path}' -- path WITHOUT the query string."""
        ts = str(int(time.time() * 1000)) if ts_ms is None else str(ts_ms)
        msg = "%s%s%s" % (ts, method, path)
        sig = base64.b64encode(self.priv.sign(msg.encode())).decode()
        return {"X-PM-Access-Key": self.key_id, "X-PM-Timestamp": ts,
                "X-PM-Signature": sig, "Content-Type": "application/json",
                "Accept": "application/json"}, msg


def mask(s):
    s = str(s or "")
    return (s[:4] + "..." + s[-2:]) if len(s) > 8 else "***"


# ------------------------------------------------------------------ logging
class Log:
    def __init__(self, log_dir=RESULTS):
        self.dir = log_dir

    def path(self, t):
        return os.path.join(self.dir, "polyorder-%s.jsonl" % utc_day(t))

    def write(self, rec):
        rec = dict(rec)
        rec.setdefault("t", round(time.time(), 3))
        line = json.dumps(rec, default=str, separators=(",", ":"))
        os.makedirs(self.dir, exist_ok=True)
        with open(self.path(rec["t"]), "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def http(self, method, path, query, body, status, resp, ms, hdrs):
        self.write({"kind": "http", "method": method, "path": path,
                    "query": query or "", "body": body, "status": status,
                    "resp": resp if not isinstance(resp, str) else resp[:800],
                    "ms": ms, "key": mask(hdrs.get("X-PM-Access-Key")),
                    "ts": hdrs.get("X-PM-Timestamp")})   # signature NEVER logged


# ------------------------------------------------------------------ transport
class HttpTransport:
    """The real wire. request() returns (status, json-or-text, headers)."""

    def __init__(self, base, signer, log):
        self.base, self.signer, self.log = base, signer, log

    def request(self, method, path, query=None, body=None):
        q = urllib.parse.urlencode(query, doseq=True) if query else ""
        url = self.base + path + ("?" + q if q else "")
        hdrs, _ = self.signer.headers(method, path)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        t0 = time.time()
        rh = {}
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as r:
                status, raw, rh = r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
            rh = dict(e.headers or {})
        except Exception as e:                                    # noqa: BLE001
            status, raw = -1, ("transport error: %s" % e).encode()
        try:
            resp = json.loads(raw.decode("utf-8", "replace") or "{}")
        except ValueError:
            resp = raw.decode("utf-8", "replace")[:800]
        ms = round(1000 * (time.time() - t0))
        self.log.http(method, path, q, body, status, resp, ms, hdrs)
        return status, resp, rh


def _post_order(tp, body):
    """THE create call. The only place an order leaves this file."""
    return tp.request("POST", ORDER_ROUTE, body=body)


def _cancel_own(tp, order_id, slug):
    """Cancel an order THIS process created (post-only rest, or an IOC the
    exchange left resting). Refuses any other id."""
    if order_id not in CREATED_IDS:
        return None, "refused: %s was not created by this process" % order_id, {}
    return tp.request("POST", "/v1/order/%s/cancel" % order_id,
                      body={"marketSlug": slug})


def _get(tp, path, query=None):
    st, r, h = tp.request("GET", path, query=query)
    return st, r, h


# ------------------------------------------------------------------ parsing
def _amt(x):
    try:
        return dec((x or {}).get("value"))
    except (decimal.InvalidOperation, AttributeError, TypeError):
        return None


def side_of(intent):
    return {"ORDER_INTENT_BUY_LONG": "up", "ORDER_INTENT_SELL_LONG": "up",
            "ORDER_INTENT_BUY_SHORT": "down",
            "ORDER_INTENT_SELL_SHORT": "down"}.get(intent)


def side_price(intent, long_px):
    """Up-terms price -> the price of the side the intent trades."""
    if long_px is None:
        return None
    return long_px if side_of(intent) == "up" else (D(1) - long_px)


def parse_order_record(o, want_qty=None):
    """An Order object (GET /v1/order/{id}, open orders, a trade's aggressor)."""
    state = o.get("state")
    cum = dec(o.get("cumQuantity") or 0)
    leaves = dec(o.get("leavesQuantity") or 0)
    intent = o.get("intent")
    avg = _amt(o.get("avgPx"))
    r = {"order_id": o.get("id"), "state": state, "filled": cum,
         "leaves": leaves, "intent": intent, "side": side_of(intent),
         "long_avg": avg, "avg": side_price(intent, avg) if cum > 0 else None,
         "fee": _amt(o.get("commissionNotionalTotalCollected")),
         "limit_long": _amt(o.get("price")), "qty": dec(o.get("quantity") or 0)}
    if state == "ORDER_STATE_FILLED":
        r["outcome"] = "filled"
    elif state in LIVE_STATES:
        r["outcome"] = "live"
    elif state in ("ORDER_STATE_CANCELED", "ORDER_STATE_EXPIRED",
                   "ORDER_STATE_REPLACED"):
        r["outcome"] = "partial" if cum > 0 else "none"
    elif state == "ORDER_STATE_REJECTED":
        r["outcome"] = "rejected"
    else:
        r["outcome"] = "unknown"
    return r


def classify_create(status, resp, order):
    """The create response. NOTE: orderRejectReason is POPULATED ON FILLS
    (the operator's real fill carries ORD_REJECT_REASON_EXCHANGE_OPTION), so
    only an execution of TYPE REJECTED or an order in state REJECTED is a
    reject. Never key on the presence of a reason field."""
    r = {"http": status, "order_id": None, "outcome": None, "filled": D(0),
         "avg": None, "fee": None, "state": None, "reject": None, "text": None,
         "source": "create_response"}
    if status in (400, 401, 403, 404):
        # the gateway refused the request itself: no order exists
        r.update(outcome="rejected", reject="http_%d" % status, text=str(resp)[:300])
        return r
    if status != 200 or not isinstance(resp, dict):
        # timeout, connection error, 408/429/5xx: the order MAY exist
        r.update(outcome="unknown", text=str(resp)[:300])
        return r
    r["order_id"] = resp.get("id")
    ex = resp.get("executions") or []
    shares, notional, fees = D(0), D(0), D(0)
    types = []
    for e in ex:
        t = e.get("type")
        types.append(t)
        if t in FILL_EXEC:
            n = dec(e.get("lastShares") or 0)
            px = _amt(e.get("lastPx")) or D(0)
            shares += n
            notional += n * px
        c = _amt(e.get("commissionNotionalCollected"))
        if c is not None:
            fees += c
        if e.get("order", {}).get("state"):
            r["state"] = e["order"]["state"]
    r["filled"] = shares
    r["fee"] = fees if ex else None
    intent = INTENT_UP if order["side"] == "up" else INTENT_DOWN
    if shares > 0:
        r["avg"] = side_price(intent, notional / shares)
    rej = [e for e in ex if e.get("type") == "EXECUTION_TYPE_REJECTED"]
    if rej:
        txt = " ".join(str(e.get("text") or "") for e in rej)
        r.update(outcome="rejected", text=txt[:300],
                 reject=("latency_stopgap" if STOPGAP_TEXT in txt
                         else rej[-1].get("orderRejectReason")))
    elif any(t in FINAL_EXEC for t in types):
        r["outcome"] = ("filled" if shares >= order["qty"]
                        else "partial" if shares > 0 else "none")
    else:
        r["outcome"] = "pending"          # accepted, not final: read the record
    return r


def net_position(resp, slug):
    """Net position in this market from GET /v1/portfolio/positions; None if
    unreadable. Negative = holding Down (the operator's Down bet read -2.52)."""
    if not isinstance(resp, dict) or not isinstance(resp.get("positions"), dict):
        return None
    p = resp["positions"].get(slug)
    if not p:
        return D(0)
    try:
        return dec(p.get("netPositionDecimal") if p.get("netPositionDecimal")
                   is not None else p.get("netPosition") or 0)
    except decimal.InvalidOperation:
        return None


def _is_ours(o, body, t_send):
    if not isinstance(o, dict):
        return False
    try:
        return (o.get("marketSlug") == body["marketSlug"]
                and o.get("intent") == body["intent"]
                and _amt(o.get("price")) == dec(body["price"]["value"])
                and dec(o.get("quantity") or -1) == dec(body["quantity"])
                and (parse_ts(o.get("createTime")) or 0) >= t_send - 5)
    except (decimal.InvalidOperation, KeyError, TypeError):
        return False


def resolve(tp, order, body, order_id, t_send, pre_pos, sleep=time.sleep, tries=4):
    """Settle an order whose outcome is not yet known BY READING THE ACCOUNT.
    Never re-sends. Returns a result dict; outcome 'unknown' if reading fails."""
    last = "no read attempted"
    for i in range(tries):
        if i:
            sleep(0.7)
        if order_id:
            st, r, _ = _get(tp, "/v1/order/%s" % order_id)
            if st == 200 and isinstance(r, dict) and isinstance(r.get("order"), dict):
                rec = parse_order_record(r["order"])
                rec["source"] = "order_record"
                if rec["outcome"] in ("live", "unknown") and i < tries - 1:
                    last = "order %s still %s" % (order_id, rec["state"])
                    continue
                return rec
            last = "GET order %s -> %s" % (order_id, st)
            continue
        st1, r1, _ = _get(tp, "/v1/orders/open", {"slugs": body["marketSlug"]})
        st2, r2, _ = _get(tp, "/v1/portfolio/activities",
                          {"marketSlug": body["marketSlug"],
                           "types": "ACTIVITY_TYPE_TRADE", "limit": 50})
        st3, r3, _ = _get(tp, "/v1/portfolio/positions", {"market": body["marketSlug"]})
        if not (st1 == st2 == st3 == 200 and isinstance(r1, dict)
                and isinstance(r2, dict)):
            last = "account reads failed (%s %s %s)" % (st1, st2, st3)
            continue
        cands = list(r1.get("orders") or [])
        for a in r2.get("activities") or []:
            tr = (a or {}).get("trade") or {}
            cands += [tr.get("aggressor"), tr.get("passive")]
        mine = [o for o in cands if _is_ours(o, body, t_send)]
        if mine:
            order_id = mine[0].get("id")
            last = "found our order %s by read-back" % order_id
            # one more pass reads its record; guarantee that pass exists
            st, r, _ = _get(tp, "/v1/order/%s" % order_id)
            if st == 200 and isinstance(r, dict) and isinstance(r.get("order"), dict):
                rec = parse_order_record(r["order"])
                rec["source"] = "readback_then_record"
                if rec["outcome"] not in ("live", "unknown"):
                    return rec
            continue
        pos = net_position(r3, body["marketSlug"])
        if pos is None:
            last = "position unreadable"
            continue
        if pre_pos is not None and pos == pre_pos:
            return {"outcome": "none", "order_id": None, "filled": D(0),
                    "avg": None, "fee": None, "state": None,
                    "source": "readback_position_unchanged"}
        last = ("position moved %s -> %s but no order of ours was found"
                % (pre_pos, pos))
    return {"outcome": "unknown", "order_id": order_id, "filled": D(0),
            "avg": None, "fee": None, "state": None, "source": "readback_failed",
            "text": last}


# ------------------------------------------------------------------ ledger
def read_ledger(log_dir):
    intents, results = {}, {}
    for f in sorted(glob.glob(os.path.join(log_dir, "polyorder-*.jsonl"))):
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r.get("kind") == "intent":
                        intents[r["intent_id"]] = r
                    elif r.get("kind") == "result":
                        results[r["intent_id"]] = r       # last one wins
        except OSError:
            continue
    return intents, results


def ledger_state(log_dir, now):
    intents, results = read_ledger(log_dir)
    day = utc_day(now)
    st = {"unresolved": [], "at_risk": D(0), "sends_today": 0, "per_slug": {},
          "intents": intents, "results": results}
    for iid, it in intents.items():
        res = results.get(iid)
        slug = it.get("slug")
        st["per_slug"][slug] = st["per_slug"].get(slug, 0) + 1
        today = utc_day(it.get("t", 0)) == day
        if today:
            st["sends_today"] += 1
        if res is None or res.get("outcome") in ("unknown", "live", "pending"):
            st["unresolved"].append(iid)
            if today:
                st["at_risk"] += dec(it.get("worst_case") or 0)
        elif today and dec(res.get("filled") or 0) > 0:
            st["at_risk"] += (dec(res["filled"]) * dec(res.get("avg") or it["price"])
                              + dec(res.get("fee") or 0))
    return st


def realised_loss_today(tp, now):
    """Sum of realised LOSSES today from the exchange's position resolutions.
    Returns (loss, ok). ok False = unreadable = refuse."""
    day = utc_day(now)
    loss, cursor = D(0), None
    for _ in range(5):
        q = {"types": "ACTIVITY_TYPE_POSITION_RESOLUTION", "limit": 100}
        if cursor:
            q["cursor"] = cursor
        st, r, _ = _get(tp, "/v1/portfolio/activities", q)
        if st != 200 or not isinstance(r, dict):
            return None, False
        acts = r.get("activities") or []
        older = False
        for a in acts:
            pr = (a or {}).get("positionResolution") or {}
            t = parse_ts(pr.get("updateTime"))
            if t is None or utc_day(t) != day:
                older = older or (t is not None and utc_day(t) < day)
                continue
            b = _amt((pr.get("beforePosition") or {}).get("realized")) or D(0)
            a2 = _amt((pr.get("afterPosition") or {}).get("realized")) or D(0)
            if a2 - b < 0:
                loss += b - a2
        cursor = r.get("nextCursor")
        if r.get("eof") or not cursor or older or not acts:
            return loss, True
    return None, False


# ------------------------------------------------------------------ live path
def preflight(tp, order, now):
    """Every read must succeed. Returns (violations, snapshot)."""
    v, snap = [], {}
    st, r, h = _get(tp, "/v1/market/slug/%s" % order["slug"])
    m = r.get("market") if isinstance(r, dict) else None
    if st != 200 or not isinstance(m, dict):
        return ["market %s unreadable (HTTP %s)" % (order["slug"], st)], snap
    mv, tick, mq, end = check_market(m, now)
    v += mv
    if tick is not None:
        v += [x for x in check_order(order, build_body(order, now), tick, mq)
              if "tick" in x or "minimum" in x]
    snap.update(tick=tick, min_qty=mq, window_end=end)
    date = (h or {}).get("Date") or (h or {}).get("date")
    if date:
        try:
            skew = abs(email.utils.parsedate_to_datetime(date).timestamp() - now)
            snap["clock_skew_s"] = round(skew, 1)
            if skew > MAX_CLOCK_SKEW_S:
                v.append("local clock is %.0f s off the exchange's (limit %d)"
                         % (skew, MAX_CLOCK_SKEW_S))
        except (TypeError, ValueError):
            pass
    st, r, _ = _get(tp, "/v1/account/balances")
    try:
        bp = dec(r["balances"][0]["buyingPower"])
        snap["buying_power"] = bp
        if bp < worst_case(order):
            v.append("buying power $%s below this order's worst case $%s"
                     % (bp, worst_case(order)))
    except (KeyError, IndexError, TypeError, decimal.InvalidOperation):
        v.append("balances unreadable (HTTP %s) -- refusing to trade blind" % st)
    st, r, _ = _get(tp, "/v1/orders/open")
    if st != 200 or not isinstance(r, dict) or not isinstance(r.get("orders"), list):
        v.append("open orders unreadable (HTTP %s)" % st)
    elif r["orders"]:
        v.append("%d order(s) already open on the account; this path never "
                 "leaves one, so something else is trading -- refusing"
                 % len(r["orders"]))
    st, r, _ = _get(tp, "/v1/portfolio/positions", {"market": order["slug"]})
    pos = net_position(r, order["slug"]) if st == 200 else None
    if pos is None:
        v.append("position in %s unreadable (HTTP %s)" % (order["slug"], st))
    snap["pre_position"] = pos
    loss, ok = realised_loss_today(tp, now)
    if not ok:
        v.append("today's realised losses unreadable -- refusing")
    else:
        snap["loss_today"] = loss
        if loss > DAY_MAX_LOSS:
            v.append("realised losses today $%s exceed DAY_MAX_LOSS $%s"
                     % (loss, DAY_MAX_LOSS))
    return v, snap


def _refuse(log, order, why, token=None):
    log.write({"kind": "refused", "intent_id": order["intent_id"],
               "slug": order["slug"], "side": order["side"],
               "price": fmt(order["price"]), "qty": fmt(order["qty"]),
               "why": why})
    return {"sent": False, "refused": why, "intent_id": order["intent_id"]}


def _book(log, order, res, extra=None):
    rec = {"kind": "result", "intent_id": order["intent_id"],
           "slug": order["slug"], "side": order["side"],
           "outcome": res.get("outcome"), "order_id": res.get("order_id"),
           "filled": fmt(res.get("filled") or 0),
           "avg": fmt(res["avg"]) if res.get("avg") is not None else None,
           "fee": fmt(res["fee"]) if res.get("fee") is not None else None,
           "state": res.get("state"), "reject": res.get("reject"),
           "source": res.get("source"), "text": res.get("text")}
    rec.update(extra or {})
    log.write(rec)


def run_live(order, signoff, tp, base, log, now_fn=time.time, sleep=time.sleep):
    """Check everything, then -- only with no violations -- send ONE order.
    Returns a dict; 'sent' says whether a create request left this process."""
    now = now_fn()
    body = build_body(order, now)
    token = token_for(order, base)
    bad = check_order(order, body)
    if not signoff:
        bad.append("no sign-off token given")
    elif signoff != token:
        bad.append("sign-off token mismatch (this order's token is %s)" % token)
    st = ledger_state(log.dir, now)
    if order["intent_id"] in st["intents"]:
        bad.append("intent %s was already sent once; an intent is never "
                   "re-sent (the API has no idempotency key)" % order["intent_id"])
    if st["unresolved"]:
        bad.append("HALTED: unresolved order(s) %s -- run --resolve first"
                   % st["unresolved"])
    if st["sends_today"] >= MAX_SENDS_PER_DAY:
        bad.append("MAX_SENDS_PER_DAY %d reached" % MAX_SENDS_PER_DAY)
    if st["per_slug"].get(order["slug"], 0) >= MAX_SENDS_PER_SLUG:
        bad.append("MAX_SENDS_PER_SLUG %d reached for %s"
                   % (MAX_SENDS_PER_SLUG, order["slug"]))
    if D(0) < order["price"] < D(1) and st["at_risk"] + worst_case(order) > DAY_MAX_RISK:
        bad.append("day at-risk $%s + this $%s exceeds DAY_MAX_RISK $%s"
                   % (st["at_risk"], worst_case(order), DAY_MAX_RISK))
    if bad:
        return _refuse(log, order, bad)
    pv, snap = preflight(tp, order, now)
    if pv:
        return _refuse(log, order, pv)
    body = build_body(order, now_fn())       # fresh goodTillTime for post-only
    t_send = now_fn()
    log.write({"kind": "intent", "intent_id": order["intent_id"],
               "slug": order["slug"], "side": order["side"],
               "price": fmt(order["price"]), "qty": fmt(order["qty"]),
               "post_only": order["post_only"], "token": token,
               "worst_case": fmt(worst_case(order)), "body": body,
               "pre_position": fmt(snap["pre_position"]), "t": t_send})
    status, resp, _ = _post_order(tp, body)
    res = classify_create(status, resp, order)
    if res.get("order_id"):
        CREATED_IDS.add(res["order_id"])
    if res["outcome"] != "rejected" or res.get("order_id"):
        # the order record is the authority whenever an order may exist
        rec = resolve(tp, order, body, res.get("order_id"), t_send,
                      snap["pre_position"], sleep)
        if rec.get("order_id"):
            CREATED_IDS.add(rec["order_id"])
        if rec["outcome"] != "unknown" or res["outcome"] == "unknown":
            if (res["outcome"] in ("filled", "partial", "none")
                    and rec["outcome"] in ("filled", "partial", "none")
                    and dec(rec.get("filled") or 0) != res["filled"]):
                rec["disagree"] = "create said %s, record says %s" % (
                    res["filled"], rec.get("filled"))
            rec.setdefault("reject", res.get("reject"))
            rec.setdefault("text", res.get("text"))
            rec["http"] = status
            res = rec
    extra = {"http": status, "t_send": t_send}
    if res["outcome"] == "live":
        # an IOC that rested, or a post-only order: rest (post-only), then
        # cancel OUR OWN order and verify it is gone.
        res = _finish_live(tp, order, body, res, t_send, snap, sleep, now_fn)
        extra["cancel"] = res.get("cancel")
        if not order["post_only"]:
            extra["ioc_rested"] = True
    _book(log, order, res, extra)
    res["sent"] = True
    res["token"] = token
    res["snapshot"] = {k: (fmt(v) if isinstance(v, D) else v) for k, v in snap.items()}
    return res


def _finish_live(tp, order, body, res, t_send, snap, sleep, now_fn):
    oid = res.get("order_id")
    if order["post_only"]:
        deadline = t_send + order["rest_s"]
        while now_fn() < deadline:
            sleep(2.0)
            st, r, _ = _get(tp, "/v1/order/%s" % oid)
            if st == 200 and isinstance(r, dict) and isinstance(r.get("order"), dict):
                rec = parse_order_record(r["order"])
                if rec["outcome"] != "live":
                    rec["source"] = "order_record"
                    return rec
    st, r, _ = _cancel_own(tp, oid, order["slug"])
    cancel = {"http": st}
    for i in range(4):
        if i:
            sleep(0.6)
        s2, r2, _ = _get(tp, "/v1/order/%s" % oid)
        if s2 == 200 and isinstance(r2, dict) and isinstance(r2.get("order"), dict):
            rec = parse_order_record(r2["order"])
            if rec["outcome"] != "live":
                rec["source"] = "record_after_cancel"
                rec["cancel"] = dict(cancel, verified=True)
                return rec
    out = dict(res)
    out["outcome"] = "live"
    out["cancel"] = dict(cancel, verified=False)
    out["text"] = "CANCEL NOT VERIFIED -- order %s may still rest. HALTED." % oid
    return out


# ------------------------------------------------------------------ read-only views
def show(tp, what, order_id=None, out=print):
    if what == "balance":
        st, r, _ = _get(tp, "/v1/account/balances")
        out("GET /v1/account/balances -> %s" % st)
        for b in (r.get("balances") or []) if isinstance(r, dict) else []:
            out("  buying power $%s   balance $%s   withdrawable $%s   bonus held $%s"
                "   deposit not yet available $%s   open orders $%s"
                % (b.get("buyingPower"), b.get("currentBalance"),
                   b.get("availableToWithdraw"), b.get("bonusHold"),
                   b.get("depositReservation"), b.get("openOrders")))
        return st, r
    if what == "positions":
        st, r, _ = _get(tp, "/v1/portfolio/positions")
        out("GET /v1/portfolio/positions -> %s" % st)
        for slug, p in ((r or {}).get("positions") or {}).items() if isinstance(r, dict) else []:
            out("  %s net %s cost %s" % (slug, p.get("netPositionDecimal"),
                                         (p.get("cost") or {}).get("value")))
        return st, r
    if what == "open":
        st, r, _ = _get(tp, "/v1/orders/open")
        out("GET /v1/orders/open -> %s  (%s open)" % (
            st, len((r or {}).get("orders") or []) if isinstance(r, dict) else "?"))
        return st, r
    if what == "order":
        st, r, _ = _get(tp, "/v1/order/%s" % order_id)
        if st == 200 and isinstance(r, dict) and isinstance(r.get("order"), dict):
            rec = parse_order_record(r["order"])
            out("order %s: %s, %s %s filled at %s, fee %s" % (
                order_id, rec["state"], rec["side"], rec["filled"], rec["avg"], rec["fee"]))
        else:
            out("GET /v1/order/%s -> %s %s" % (order_id, st, str(r)[:200]))
        return st, r
    if what in ("fills", "resolutions"):
        typ = "ACTIVITY_TYPE_TRADE" if what == "fills" else "ACTIVITY_TYPE_POSITION_RESOLUTION"
        st, r, _ = _get(tp, "/v1/portfolio/activities", {"types": typ, "limit": 50})
        out("GET /v1/portfolio/activities (%s) -> %s" % (what, st))
        for a in (r.get("activities") or []) if isinstance(r, dict) else []:
            if what == "fills":
                tr = a.get("trade") or {}
                o = tr.get("aggressor") if tr.get("isAggressor") else tr.get("passive")
                o = o or {}
                px = side_price(o.get("intent"), _amt(tr.get("price")))
                out("  %s %s %s %s @ %s (%s)" % (
                    tr.get("createTime"), tr.get("marketSlug"), side_of(o.get("intent")),
                    tr.get("qtyDecimal"), px,
                    "took" if tr.get("isAggressor") else "was hit"))
            else:
                pr = a.get("positionResolution") or {}
                out("  %s %s %s realised %s" % (
                    pr.get("updateTime"), pr.get("marketSlug"), pr.get("side"),
                    ((pr.get("afterPosition") or {}).get("realized") or {}).get("value")))
        return st, r
    raise ValueError(what)


# ------------------------------------------------------------------ self-test
class _FakeTransport:
    """Scripted responses. routes: {(METHOD, path): [(status, resp), ...]} --
    each call pops the next; the last one repeats. 'TIMEOUT' = lost reply."""

    SIGS = []                    # every signature any fake request carried

    def __init__(self, routes, log, signer, date_t=None):
        self.routes, self.log, self.signer, self.date_t = routes, log, signer, date_t
        self.calls = []

    def request(self, method, path, query=None, body=None):
        q = urllib.parse.urlencode(query, doseq=True) if query else ""
        hdrs, msg = self.signer.headers(method, path)
        _FakeTransport.SIGS.append(hdrs["X-PM-Signature"])
        self.calls.append((method, path, q, body, msg))
        seq = self.routes.get((method, path))
        if callable(seq):
            st, r = seq(self)
        elif not seq:
            st, r = 404, "no fake route %s %s" % (method, path)
        else:
            st, r = seq.pop(0) if len(seq) > 1 else seq[0]
        if r == "TIMEOUT":
            st, r = -1, "transport error: timed out"
        self.log.http(method, path, q, body, st, r, 1, hdrs)
        h = {}
        if self.date_t is not None:
            h["Date"] = email.utils.formatdate(self.date_t, usegmt=True)
        return st, r, h

    def posts(self):
        return [c for c in self.calls if c[0] == "POST"]

    def cancelled(self, oid):
        return any(c[0] == "POST" and c[1] == "/v1/order/%s/cancel" % oid
                   for c in self.calls)


def _with(routes, extra):
    out = dict(routes)
    out.update(extra)
    return out


def selftest(verbose=True):
    ok = [True]
    n = [0, 0]

    def ck(c, m):
        n[0] += 1
        if not c:
            n[1] += 1
            ok[0] = False
        if verbose or not c:
            print(("  ok: " if c else "FAIL: ") + m)

    global MAX_QTY
    tmp = tempfile.mkdtemp(prefix="polyorder-st-")
    seed = bytes(range(32)) + bytes(range(32))
    secret = base64.b64encode(seed).decode()
    signer = Signer.from_secret("00000000-test-key-id-000000000000", secret)
    now = 1_790_340_000.0               # 2026-09-25T12:40:00Z
    slug = "cpc-btc-updown-15m-2026-09-25-1230z"

    def market(status="MARKET_STATUS_OPEN", end=now + 300):
        return {"market": {"slug": slug, "status": status, "closed": False,
                           "orderPriceMinTickSize": 0.01, "minimumTradeQty": 0.01,
                           "assetPriceTerms": {"windowEnd": iso(end)}}}

    def base_routes(bp=60.52, open_orders=None, pos=None, resolutions=None):
        return {
            ("GET", "/v1/market/slug/" + slug): [(200, market())],
            ("GET", "/v1/account/balances"): [(200, {"balances": [{"buyingPower": bp}]})],
            ("GET", "/v1/orders/open"): [(200, {"orders": open_orders or []})],
            ("GET", "/v1/portfolio/positions"): [(200, {"positions": pos or {}})],
            ("GET", "/v1/portfolio/activities"): [(200, {"activities": resolutions or [],
                                                         "eof": True})],
        }

    def ex(typ, shares="0", px="0.97", state="ORDER_STATE_FILLED", text="", reason=None):
        return {"type": typ, "lastShares": shares, "lastPx": {"value": px, "currency": "USD"},
                "text": text, "orderRejectReason": reason or "ORD_REJECT_REASON_EXCHANGE_OPTION",
                "commissionNotionalCollected": {"value": "0.00", "currency": "USD"},
                "order": {"state": state}}

    def rec(oid, state, cum, avg, intent=INTENT_UP, qty=1, price="0.97", fee_="0.00", ct=None):
        return {"order": {"id": oid, "marketSlug": slug, "state": state,
                          "cumQuantity": cum, "leavesQuantity": 0 if state not in LIVE_STATES else qty - cum,
                          "quantity": qty, "intent": intent,
                          "price": {"value": price, "currency": "USD"},
                          "avgPx": {"value": avg, "currency": "USD"} if avg else None,
                          "commissionNotionalTotalCollected": {"value": fee_, "currency": "USD"},
                          "createTime": ct or iso(now + 1)}}

    def fresh(name):
        d = os.path.join(tmp, name)
        os.makedirs(d, exist_ok=True)
        return Log(d)

    clock = lambda: now                  # noqa: E731

    def FT(routes, lg, date_t=now):
        return _FakeTransport(routes, lg, signer, date_t)

    def sec(m):
        if verbose:
            print(m)
    nosleep = lambda s: None             # noqa: E731

    try:
        sec("-- A. the wire body: Up and Down, exact decimals")
        up = make_order(slug, "up", "0.97", "1")
        dn = make_order(slug, "down", "0.97", "1")
        bu, bd = build_body(up, now), build_body(dn, now)
        ck(bu["intent"] == INTENT_UP and bu["price"]["value"] == "0.97",
           "buy Up at 97c -> BUY_LONG, price.value '0.97'")
        ck(bd["intent"] == INTENT_DOWN and bd["price"]["value"] == "0.03",
           "buy Down at 97c -> BUY_SHORT, price.value '0.03' (the Up price), "
           "exact -- not 0.030000000000000027")
        ck(bu["tif"] == TIF_IOC and bu["participateDontInitiate"] is False
           and bu["synchronousExecution"] is True and bu["quantity"] == 1
           and bu["manualOrderIndicator"] == "MANUAL_ORDER_INDICATOR_AUTOMATIC",
           "IOC, not post-only, synchronous, quantity 1, flagged AUTOMATIC")
        ck(check_order(up, bu) == [] and check_order(dn, bd) == [],
           "both legal 1-contract orders pass every rail")
        ck(worst_case(up) == D("0.97") and fee("0.97", 1) == D("0.00"),
           "1 contract at 97c: fee rounds to $0.00, worst case $0.97")
        ck(fee("0.97", 60) == D("0.12") and fee("0.22", "2.52") == D("0.03"),
           "fee: 60 @ 97c = $0.12; the operator's 2.52 @ 22c = $0.03 (his real bill)")

        sec("-- B. the operator's REAL filled order parses correctly")
        real = {"id": "CPZBEBJ5YXPK", "marketSlug": "cpc-btc-updown-15m-2026-09-25-0545z",
                "side": "ORDER_SIDE_SELL", "type": "ORDER_TYPE_LIMIT",
                "price": {"value": "0.12", "currency": "USD"}, "quantity": 2.52,
                "cumQuantity": 2.52, "leavesQuantity": 0, "tif": "TIME_IN_FORCE_DAY",
                "intent": "ORDER_INTENT_BUY_SHORT", "state": "ORDER_STATE_FILLED",
                "commissionNotionalTotalCollected": {"value": "0.0300", "currency": "USD"},
                "avgPx": {"value": "0.2200", "currency": "USD"},
                "createTime": "2026-09-25T05:53:50.065833315Z"}
        pr = parse_order_record(real)
        ck(pr["outcome"] == "filled" and pr["side"] == "down"
           and pr["filled"] == D("2.52") and pr["avg"] == D("0.78")
           and pr["fee"] == D("0.03"),
           "BUY_SHORT, avgPx 0.22 (Up terms) -> Down 2.52 filled at 0.78, fee $0.03")
        ck(abs(parse_ts(real["createTime"]) - 1790315630.0658) < 0.001,
           "nanosecond timestamps parse to UTC epoch")
        fill_with_reason = classify_create(200, {"id": "X1", "executions": [
            ex("EXECUTION_TYPE_FILL", "1", "0.97", reason="ORD_REJECT_REASON_EXCHANGE_OPTION")]}, up)
        ck(fill_with_reason["outcome"] == "filled",
           "a FILL that carries orderRejectReason (as the real one does) is a fill, "
           "not a reject")

        sec("-- C. every rail refuses")
        cases = [
            ("price 97 (unit guessed from size)", make_order(slug, "up", "97", "1")),
            ("price 0.975 (off the 1c tick)", make_order(slug, "up", "0.975", "1")),
            ("price 0.99 (above MAX_PRICE)", make_order(slug, "up", "0.99", "1")),
            ("price 0", make_order(slug, "up", "0", "1")),
            ("price 1", make_order(slug, "up", "1", "1")),
            ("quantity 6 (above MAX_QTY)", make_order(slug, "up", "0.50", "6")),
            ("quantity 0", make_order(slug, "up", "0.50", "0")),
            ("quantity 0.005 (below the minimum)", make_order(slug, "up", "0.50", "0.005")),
            ("quantity 1.005 (not a multiple)", make_order(slug, "up", "0.50", "1.005")),
            ("a Kalshi ticker", make_order("KXBTC15M-26SEP251245-45", "up", "0.97", "1")),
            ("an unrelated Polymarket market", make_order("aec-cbb-usc-iowa-2026-01-28", "up", "0.97", "1")),
            ("side 'yes'", make_order(slug, "yes", "0.97", "1")),
            ("post-only resting 120 s", make_order(slug, "up", "0.50", "1", True, 120)),
        ]
        for label, o in cases:
            ck(bool(check_order(o, build_body(o, now))), "REFUSED: " + label)
        MAX_QTY = D("10")
        try:
            o = make_order(slug, "up", "0.95", "6")
            v = check_order(o, build_body(o, now))
            ck(any("MAX_COST" in x for x in v),
               "REFUSED: 6 @ 95c = $5.70 > MAX_COST (tested with MAX_QTY raised; at "
               "the shipped MAX_QTY 5 the most any order can cost is $%s, so the "
               "quantity cap binds first)" % (5 * MAX_PRICE))
        finally:
            MAX_QTY = D("5")
        for label, mut in (("tif GTC", {"tif": "TIME_IN_FORCE_GOOD_TILL_CANCEL"}),
                           ("a market order", {"type": "ORDER_TYPE_MARKET"}),
                           ("a SELL intent", {"intent": "ORDER_INTENT_SELL_LONG"}),
                           ("wire price flipped to 0.97 on a Down buy", {"price": {"value": "0.97", "currency": "USD"}}),
                           ("an extra cashOrderQty field", {"cashOrderQty": {"value": "5", "currency": "USD"}})):
            b = dict(bd)
            b.update(mut)
            ck(bool(check_order(dn, b)), "REFUSED body: " + label)
        mv = check_market(market("MARKET_STATUS_HALTED")["market"], now)[0]
        ck(bool(mv), "REFUSED: market status HALTED (seen live on 12:00-12:30Z 15m windows)")
        mv = check_market(market(end=now - 5)["market"], now)[0]
        ck(bool(mv), "REFUSED: window already ended")

        sec("-- D. the sign-off token binds to the exact order and venue")
        t0 = token_for(up, BASE)
        variants = {"market": make_order(slug.replace("1230z", "1245z"), "up", "0.97", "1", intent_id=up["intent_id"]),
                    "side": make_order(slug, "down", "0.97", "1", intent_id=up["intent_id"]),
                    "price": make_order(slug, "up", "0.96", "1", intent_id=up["intent_id"]),
                    "size": make_order(slug, "up", "0.97", "2", intent_id=up["intent_id"]),
                    "post-only": make_order(slug, "up", "0.97", "1", True, 20, intent_id=up["intent_id"]),
                    "intent id": make_order(slug, "up", "0.97", "1", intent_id="other")}
        for k, o in variants.items():
            ck(token_for(o, BASE) != t0, "token changes with " + k)
        ck(token_for(up, "https://api.example.test") != t0, "token changes with the base URL")
        ck(token_for(make_order(slug, "up", "0.97", "1"), BASE) == t0,
           "the same order gives the same token (dry run and live agree)")

        sec("-- E. nothing is sent without --live AND the matching token")
        lg = fresh("e")
        tp = FT(_with(base_routes(), {
            ("POST", ORDER_ROUTE): [(200, {"id": "O1", "executions": [
                ex("EXECUTION_TYPE_FILL", "1", "0.97")]})],
            ("GET", "/v1/order/O1"): [(200, rec("O1", "ORDER_STATE_FILLED", 1, "0.97"))]}), lg)
        r = run_live(up, "", tp, BASE, lg, clock, nosleep)
        ck(not r["sent"] and not tp.calls, "no token -> refused, zero requests of any kind")
        r = run_live(up, "0123456789abcdef", tp, BASE, lg, clock, nosleep)
        ck(not r["sent"] and not tp.calls, "wrong token -> refused, zero requests")
        big = make_order(slug, "up", "0.97", "6")
        r = run_live(big, token_for(big, BASE), tp, BASE, lg, clock, nosleep)
        ck(not r["sent"] and not tp.calls,
           "oversize order WITH its own valid token -> refused before any request")
        r = run_live(up, t0, tp, BASE, lg, clock, nosleep)
        ck(r["sent"] and len(tp.posts()) == 1 and tp.posts()[0][1] == ORDER_ROUTE,
           "matching token -> exactly one create request")
        ck(r["outcome"] == "filled" and r["filled"] == D(1) and r["avg"] == D("0.97"),
           "... and it books 1 Up filled at 97c from the order record")
        r2 = run_live(up, t0, tp, BASE, lg, clock, nosleep)
        ck(not r2["sent"] and len(tp.posts()) == 1 and "already sent" in str(r2["refused"]),
           "replaying the same token -> refused by the ledger (one intent, one send, ever)")

        sec("-- F. outcomes from the create response, confirmed by the record")

        def one(name, create, record=None, order=up, extra_routes=None):
            lg_ = fresh(name)
            routes = base_routes()
            routes[("POST", ORDER_ROUTE)] = [create]
            if record is not None:
                routes[("GET", "/v1/order/" + record[1]["order"]["id"])] = [record]
            routes.update(extra_routes or {})
            tp_ = FT(routes, lg_)
            return run_live(order, token_for(order, BASE), tp_, BASE, lg_, clock, nosleep), tp_, lg_

        r, _, _ = one("f1", (200, {"id": "D1", "executions": [ex("EXECUTION_TYPE_FILL", "1", "0.03")]}),
                      (200, rec("D1", "ORDER_STATE_FILLED", 1, "0.03", INTENT_DOWN, price="0.03")), dn)
        ck(r["outcome"] == "filled" and r["avg"] == D("0.97") and r["side"] == "down",
           "Down fill at Up-price 0.03 is booked as Down at 97c")
        o3 = make_order(slug, "up", "0.97", "3")
        r, _, _ = one("f2", (200, {"id": "P1", "executions": [
            ex("EXECUTION_TYPE_PARTIAL_FILL", "1", "0.96", "ORDER_STATE_PARTIALLY_FILLED"),
            ex("EXECUTION_TYPE_CANCELED", "0", "0", "ORDER_STATE_CANCELED")]}),
            (200, rec("P1", "ORDER_STATE_CANCELED", 1, "0.96", qty=3)), o3)
        ck(r["outcome"] == "partial" and r["filled"] == D(1) and r["avg"] == D("0.96"),
           "IOC partial: 1 of 3 at 96c, rest cancelled -> partial, 1 contract")
        r, _, _ = one("f3", (200, {"id": "N1", "executions": [ex("EXECUTION_TYPE_CANCELED", "0", "0", "ORDER_STATE_CANCELED")]}),
                      (200, rec("N1", "ORDER_STATE_CANCELED", 0, None)))
        ck(r["outcome"] == "none" and r["filled"] == D(0), "IOC with nothing at our price -> none")
        r, _, _ = one("f4", (200, {"id": "R1", "executions": [ex(
            "EXECUTION_TYPE_REJECTED", "0", "0", "ORDER_STATE_REJECTED",
            reason="ORD_REJECT_REASON_PRICE_OUT_OF_BOUNDS")]}),
            (200, rec("R1", "ORDER_STATE_REJECTED", 0, None)))
        ck(r["outcome"] == "rejected" and r["reject"] == "ORD_REJECT_REASON_PRICE_OUT_OF_BOUNDS",
           "exchange reject -> rejected, reason kept")
        r, _, _ = one("f5", (200, {"id": "S1", "executions": [ex(
            "EXECUTION_TYPE_REJECTED", "0", "0", "ORDER_STATE_REJECTED", text=STOPGAP_TEXT)]}),
            (200, rec("S1", "ORDER_STATE_REJECTED", 0, None)))
        ck(r["outcome"] == "rejected" and r["reject"] == "latency_stopgap",
           "'Global Rate Limit Exceeded' is labelled the 5-second latency stopgap, not a rate limit")
        r, tpx, _ = one("f6", (400, {"code": 3, "message": "invalid quantity"}))
        ck(r["outcome"] == "rejected" and r["reject"] == "http_400"
           and not any(c[1].startswith("/v1/order/") for c in tpx.calls),
           "HTTP 400 -> rejected by the gateway, no order to read back")
        r, _, _ = one("f7", (200, {"id": "Q1"}), (200, rec("Q1", "ORDER_STATE_FILLED", 1, "0.97")))
        ck(r["outcome"] == "filled" and r["source"] == "order_record",
           "accepted with no executions -> the order record settles it (filled)")

        sec("-- G. a lost reply is resolved by reading the account, never by re-sending")
        trade = {"type": "ACTIVITY_TYPE_TRADE", "trade": {
            "marketSlug": slug, "isAggressor": True, "qtyDecimal": "1.0000",
            "aggressor": rec("T1", "ORDER_STATE_FILLED", 1, "0.97")["order"]}}
        routes = base_routes()
        routes[("POST", ORDER_ROUTE)] = [(-1, "TIMEOUT")]
        routes[("GET", "/v1/portfolio/activities")] = [
            (200, {"activities": [], "eof": True}), (200, {"activities": [trade], "eof": True})]
        routes[("GET", "/v1/order/T1")] = [(200, rec("T1", "ORDER_STATE_FILLED", 1, "0.97"))]
        lg = fresh("g1")
        tp = FT(routes, lg)
        r = run_live(up, t0, tp, BASE, lg, clock, nosleep)
        ck(r["outcome"] == "filled" and r["order_id"] == "T1" and len(tp.posts()) == 1,
           "timeout, no id -> found our order in the trade history -> filled; one create only")
        routes = base_routes()
        routes[("POST", ORDER_ROUTE)] = [(-1, "TIMEOUT")]
        lg = fresh("g2")
        tp = FT(routes, lg)
        r = run_live(up, t0, tp, BASE, lg, clock, nosleep)
        ck(r["outcome"] == "none" and r["source"] == "readback_position_unchanged",
           "timeout, nothing found, position unchanged -> none (proved by the position)")
        routes = base_routes()
        routes[("POST", ORDER_ROUTE)] = [(-1, "TIMEOUT")]
        routes[("GET", "/v1/portfolio/positions")] = lambda t: (200, {"positions": (
            {slug: {"netPositionDecimal": "1.0000"}} if t.posts() else {})})
        lg = fresh("g2b")
        tp = FT(routes, lg)
        r = run_live(up, t0, tp, BASE, lg, clock, nosleep)
        ck(r["outcome"] == "unknown" and "position moved" in str(r.get("text")),
           "timeout, no order of ours found, but the position MOVED -> UNKNOWN, not none")
        routes = base_routes()
        routes[("POST", ORDER_ROUTE)] = [(503, "upstream error")]
        routes[("GET", "/v1/orders/open")] = [(200, {"orders": []}), (500, "x")]
        lg = fresh("g3")
        tp = FT(routes, lg)
        r = run_live(up, t0, tp, BASE, lg, clock, nosleep)
        ck(r["outcome"] == "unknown", "503 and the account unreadable -> UNKNOWN, never assumed")
        o2 = make_order(slug.replace("1230z", "1245z"), "up", "0.97", "1")
        r2 = run_live(o2, token_for(o2, BASE), tp, BASE, lg, clock, nosleep)
        ck(not r2["sent"] and "HALTED" in str(r2["refused"]) and len(tp.posts()) == 1,
           "an unresolved order HALTS the next send, even with a valid token")
        routes2 = base_routes()
        routes2[("GET", "/v1/order/T1")] = [(200, rec("T1", "ORDER_STATE_FILLED", 1, "0.97"))]
        routes2[("GET", "/v1/portfolio/activities")] = [(200, {"activities": [trade], "eof": True})]
        tp2 = FT(routes2, lg)
        rr = resolve_intent(up["intent_id"], tp2, lg, nosleep)
        ck(rr["outcome"] == "filled" and not tp2.posts(),
           "--resolve settles it by GETs alone (filled), sending nothing")
        st = ledger_state(lg.dir, now)
        ck(not st["unresolved"], "... and the halt lifts")

        sec("-- H. an IOC the exchange left resting is cancelled and the halt is raised")
        routes = base_routes()
        routes[("POST", ORDER_ROUTE)] = [(200, {"id": "L1", "executions": [ex("EXECUTION_TYPE_NEW", "0", "0", "ORDER_STATE_NEW")]})]
        routes[("GET", "/v1/order/L1")] = lambda t: (200, rec(
            "L1", "ORDER_STATE_CANCELED" if t.cancelled("L1") else "ORDER_STATE_NEW", 0, None))
        routes[("POST", "/v1/order/L1/cancel")] = [(200, {})]
        lg = fresh("h1")
        tp = FT(routes, lg)
        r = run_live(up, t0, tp, BASE, lg, clock, nosleep)
        posts = [c[1] for c in tp.posts()]
        ck(posts == [ORDER_ROUTE, "/v1/order/L1/cancel"] and r["outcome"] == "none"
           and r["cancel"]["verified"] is True,
           "IOC read back as NEW -> cancel OUR id, verified gone, booked as none")
        st, msg, _ = _cancel_own(tp, "SOMEONE-ELSES", slug)
        ck(st is None and "refused" in msg and len(tp.posts()) == 2,
           "cancelling an order this process did not create is refused, nothing sent")

        sec("-- I. day caps and pre-send reads")
        lg = fresh("i1")
        for k in range(10):
            lg.write({"kind": "intent", "intent_id": "old%d" % k, "slug": "s%d" % k,
                      "price": "0.95", "qty": "1", "worst_case": "0.95", "t": now - 60})
            lg.write({"kind": "result", "intent_id": "old%d" % k, "outcome": "filled",
                      "filled": "1", "avg": "0.95", "fee": "0", "t": now - 59})
        tp = FT(base_routes(), lg)
        r = run_live(up, t0, tp, BASE, lg, clock, nosleep)
        ck(not r["sent"] and "DAY_MAX_RISK" in str(r["refused"]) and not tp.calls,
           "$9.50 already at risk today + $0.97 > $10 -> refused before any request")
        lg = fresh("i1b")
        lg.write({"kind": "intent", "intent_id": "yday", "slug": "sy", "price": "0.95",
                  "qty": "5", "worst_case": "4.75", "t": now - 86400})
        lg.write({"kind": "result", "intent_id": "yday", "outcome": "filled",
                  "filled": "5", "avg": "0.95", "fee": "0", "t": now - 86400})
        ck(ledger_state(lg.dir, now)["at_risk"] == D(0), "yesterday's fills do not count against today")
        loss_act = [{"type": "ACTIVITY_TYPE_POSITION_RESOLUTION", "positionResolution": {
            "marketSlug": "x", "updateTime": iso(now - 100),
            "beforePosition": {"realized": {"value": "0"}},
            "afterPosition": {"realized": {"value": "-5.20"}}}}]
        for label, routes, frag in (
                ("realised loss $5.20 today", base_routes(resolutions=loss_act), "DAY_MAX_LOSS"),
                ("loss history unreadable", _with(base_routes(), {("GET", "/v1/portfolio/activities"): [(500, "x")]}), "losses unreadable"),
                ("balances unreadable", _with(base_routes(), {("GET", "/v1/account/balances"): [(401, "x")]}), "balances unreadable"),
                ("buying power $0.50", base_routes(bp=0.50), "buying power"),
                ("an order already open", base_routes(open_orders=[{"id": "Z"}]), "already open"),
                ("market halted", _with(base_routes(), {("GET", "/v1/market/slug/" + slug): [(200, market("MARKET_STATUS_HALTED"))]}), "HALTED")):
            lg = fresh("i-" + label[:6].replace(" ", "_"))
            tp = FT(routes, lg)
            r = run_live(up, t0, tp, BASE, lg, clock, nosleep)
            ck(not r["sent"] and frag in str(r["refused"]) and not tp.posts(),
               "REFUSED, nothing sent: " + label)
        lg = fresh("i-skew")
        tp = FT(base_routes(), lg, date_t=now + 60)
        r = run_live(up, t0, tp, BASE, lg, clock, nosleep)
        ck(not r["sent"] and "clock" in str(r["refused"]) and not tp.posts(),
           "REFUSED, nothing sent: local clock 60 s off the exchange's Date header")

        sec("-- J. signing, and what the logs may never contain")
        from cryptography.hazmat.primitives.asymmetric import ed25519
        h, msg = signer.headers("POST", ORDER_ROUTE, ts_ms=1790340000000)
        pub = ed25519.Ed25519PrivateKey.from_private_bytes(seed[:32]).public_key()
        try:
            pub.verify(base64.b64decode(h["X-PM-Signature"]), msg.encode())
            good = True
        except Exception:                                    # noqa: BLE001
            good = False
        ck(msg == "1790340000000POST/v1/orders" and good,
           "signs '{ts}POST/v1/orders' and the signature verifies against the key")
        try:
            sys.path.insert(0, r"C:\kals")
            import poly_us
            same = (poly_us.message("1790340000000", "POST", ORDER_ROUTE) == msg
                    and poly_us.load_key(secret).sign(msg.encode())
                    == base64.b64decode(h["X-PM-Signature"]))
            ck(same, "byte-identical to C:\\kals\\poly_us.py's message and key loader")
        except ImportError:
            sec("  (poly_us.py not importable here; cross-check skipped)")
        tpq = FT(base_routes(), fresh("j"))
        tpq.request("GET", "/v1/orders/open", {"slugs": slug})
        ck(tpq.calls[0][4].endswith("GET/v1/orders/open") and "slugs" not in tpq.calls[0][4],
           "a query string is sent but never signed (signing it breaks auth)")
        leaked = []
        sigs = set(_FakeTransport.SIGS)
        for f in glob.glob(os.path.join(tmp, "*", "polyorder-*.jsonl")):
            txt = open(f, encoding="utf-8").read()
            if secret in txt or "X-PM-Signature" in txt or any(s in txt for s in sigs):
                leaked.append(f)
        nrec = sum(1 for f in glob.glob(os.path.join(tmp, "*", "polyorder-*.jsonl"))
                   for _ in open(f, encoding="utf-8"))
        ck(not leaked and nrec > 50 and len(sigs) > 50,
           "%d log lines written; the secret and none of the %d signatures sent "
           "appear in any of them" % (nrec, len(sigs)))
        lgE = os.path.join(tmp, "e")
        kinds = [json.loads(x)["kind"] for f in glob.glob(os.path.join(lgE, "*.jsonl"))
                 for x in open(f, encoding="utf-8")]
        ck(kinds.count("refused") == 4 and kinds.count("intent") == 1
           and kinds.count("result") == 1 and kinds.count("http") >= 7,
           "every refusal, the intent, the result and every request are logged "
           "(%d refused, %d intent, %d result, %d http)" % (
               kinds.count("refused"), kinds.count("intent"),
               kinds.count("result"), kinds.count("http")))

        sec("-- J2. the REAL transport, with urlopen stubbed (no network)")
        seen = []

        class _Resp:
            def __init__(self, status, payload):
                self.status, self._p = status, payload
                self.headers = {"Date": email.utils.formatdate(now, usegmt=True)}

            def read(self):
                return self._p

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            seen.append(req)
            if "boom" in req.full_url:
                raise OSError("connection reset")
            return _Resp(200, b'{"orders": []}')
        real_urlopen = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            lgR = fresh("real")
            ht = HttpTransport(BASE, signer, lgR)
            st1, r1, h1 = ht.request("GET", "/v1/orders/open", {"slugs": slug})
            st2, r2, _ = ht.request("POST", ORDER_ROUTE, body=bu)
            st3, r3, _ = ht.request("GET", "/v1/boom")
        finally:
            urllib.request.urlopen = real_urlopen
        g, p = seen[0], seen[1]
        gts = g.get_header("X-pm-timestamp")
        try:
            pub.verify(base64.b64decode(g.get_header("X-pm-signature")),
                       ("%sGET/v1/orders/open" % gts).encode())
            gver = True
        except Exception:                                    # noqa: BLE001
            gver = False
        ck(st1 == 200 and r1 == {"orders": []} and g.full_url == BASE + "/v1/orders/open?slugs=" + slug
           and g.get_method() == "GET" and gver and "Date" in h1,
           "real GET: query on the URL, signature over the path alone verifies")
        ck(p.get_method() == "POST" and json.loads(p.data) == bu
           and p.full_url == BASE + ORDER_ROUTE
           and p.get_header("X-pm-access-key") == signer.key_id,
           "real POST: exact body as JSON, key id header, create route")
        ck(st3 == -1 and "connection reset" in str(r3),
           "a transport failure comes back as status -1 (-> UNKNOWN), never as an exception")
        rtxt = "".join(open(f, encoding="utf-8").read()
                       for f in glob.glob(os.path.join(lgR.dir, "*.jsonl")))
        ck(rtxt.count('"kind":"http"') == 3 and g.get_header("X-pm-signature") not in rtxt
           and p.get_header("X-pm-signature") not in rtxt,
           "the real transport logs all 3 requests and neither signature")

        sec("-- K. post-only (built, never run live): rests, then cancels its own order")
        po = make_order(slug, "up", "0.50", "1", True, 10)
        bp_ = build_body(po, now)
        ck(bp_["tif"] == TIF_GTD and bp_["participateDontInitiate"] is True
           and bp_["goodTillTime"] == iso(now + 10) and check_order(po, bp_) == [],
           "post-only body: GTD 10 s out, participateDontInitiate true")
        routes = base_routes()
        routes[("POST", ORDER_ROUTE)] = [(200, {"id": "M1"})]
        routes[("GET", "/v1/order/M1")] = lambda t: (200, rec(
            "M1", "ORDER_STATE_CANCELED" if t.cancelled("M1") else "ORDER_STATE_NEW",
            0, None, price="0.5"))
        routes[("POST", "/v1/order/M1/cancel")] = [(200, {})]
        lg = fresh("k1")
        tp = FT(routes, lg)
        tick = [now]

        def adv(s):
            tick[0] += s
        r = run_live(po, token_for(po, BASE), tp, BASE, lg, lambda: tick[0], adv)
        ck([c[1] for c in tp.posts()] == [ORDER_ROUTE, "/v1/order/M1/cancel"]
           and r["outcome"] == "none" and r.get("cancel", {}).get("verified") is True,
           "rests its 10 s, cancels M1 (its own), verifies CANCELED")
        routes[("GET", "/v1/order/M1")] = [(200, rec("M1", "ORDER_STATE_NEW", 0, None, price="0.5"))]
        routes[("POST", ORDER_ROUTE)] = [(200, {"id": "M2"})]
        routes[("GET", "/v1/order/M2")] = [(200, rec("M2", "ORDER_STATE_NEW", 0, None, price="0.5"))]
        routes[("POST", "/v1/order/M2/cancel")] = [(500, "x")]
        lg = fresh("k2")
        tp = FT(routes, lg)
        tick[0] = now
        r = run_live(po, token_for(po, BASE), tp, BASE, lg, lambda: tick[0], adv)
        ck(r["outcome"] == "live" and "NOT VERIFIED" in str(r.get("text"))
           and ledger_state(lg.dir, now)["unresolved"],
           "a cancel that cannot be verified is said loudly and HALTS further sends")
        ck(tick[0] - now >= po["rest_s"],
           "and it did rest its full %ds before cancelling (%.1fs on the fake clock)"
           % (po["rest_s"], tick[0] - now))

        sec("-- L. static: where a writing request can come from")
        src = open(os.path.abspath(__file__), encoding="utf-8").read()
        tree = ast.parse(src)
        where, wire, dyn, opens = {}, set(), [], set()
        TEST = ("selftest", "_FakeTransport")      # ownership is sticky inside these

        def walk(node, owner):
            for ch in ast.iter_child_nodes(node):
                own = owner
                if isinstance(ch, (ast.FunctionDef, ast.ClassDef)) and owner not in TEST:
                    own = ch.name
                if (isinstance(ch, ast.Expr) and isinstance(getattr(ch, "value", None), ast.Constant)
                        and isinstance(ch.value.value, str)):
                    continue                                   # docstrings
                if isinstance(ch, ast.Constant) and isinstance(ch.value, str):
                    where.setdefault(own, []).append(ch.value)
                if (isinstance(ch, ast.Call) and isinstance(ch.func, ast.Attribute)
                        and own not in TEST):
                    if ch.func.attr == "request":
                        a0 = ch.args[0] if ch.args else None
                        if isinstance(a0, ast.Constant):
                            wire.add((own, a0.value))
                        else:
                            dyn.append(own)
                    if ch.func.attr == "urlopen":
                        opens.add(own)
                walk(ch, own)
        walk(tree, "<module>")
        work = {k: v for k, v in where.items() if k not in TEST}
        verb = "PO" + "ST"
        want_wire = {("_post_order", verb), ("_cancel_own", verb), ("_get", "GET")}
        ck(wire == want_wire and not dyn and opens == {"request"},
           "wire map: requests leave only from _post_order (create), _cancel_own "
           "(own order) and _get (reads); urlopen only in HttpTransport.request "
           "%s" % ("" if wire == want_wire and not dyn else repr((sorted(wire), dyn))))
        needles = ["/v1/orders/open" + "/cancel", "close" + "-position", "/mod" + "ify",
                   "/bat" + "ched", "DEL" + "ETE", "cashOrder" + "Qty", "ORDER_TYPE_" + "MARKET",
                   "SELL_" + "LONG", "SELL_" + "SHORT"]
        hits = sorted({nd for k, v in work.items() for s in v for nd in needles
                       if nd in s and not (nd.startswith("SELL") and k == "side_of")})
        ck(not hits, "no cancel-all, close-position, modify, batch, delete, market "
                     "order, cash-sized order or SELL in the working code %s" % (hits or ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("polyorder selftest: %s (%d checks, %d failed)" % (
        "OK" if ok[0] else "FAILED", n[0], n[1]))
    return ok[0]


def resolve_intent(intent_id, tp, log, sleep=time.sleep):
    """Read-only settlement of a recorded intent; appends a result."""
    intents, _ = read_ledger(log.dir)
    it = intents.get(intent_id)
    if not it:
        return {"outcome": "no such intent"}
    order = make_order(it["slug"], it["side"], it["price"], it["qty"],
                       it.get("post_only"), 0, intent_id)
    body = it.get("body") or build_body(order, it["t"])
    _, results = read_ledger(log.dir)
    prev = results.get(intent_id) or {}
    pre = it.get("pre_position")
    rec = resolve(tp, order, body, prev.get("order_id"), it["t"],
                  dec(pre) if pre not in (None, "None") else None, sleep)
    _book(log, order, rec, {"resolved_by": "--resolve"})
    return rec


# ------------------------------------------------------------------ CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show", choices=["balance", "positions", "open", "fills",
                                       "resolutions", "order"])
    ap.add_argument("--order-id")
    ap.add_argument("--slug")
    ap.add_argument("--side", choices=["up", "down"])
    ap.add_argument("--price", help="dollars for the side you buy, e.g. 0.97")
    ap.add_argument("--qty", default="1")
    ap.add_argument("--post-only", action="store_true")
    ap.add_argument("--rest", type=int, default=0, help="post-only: seconds to rest")
    ap.add_argument("--intent-id")
    ap.add_argument("--offline", action="store_true", help="dry run without the market GET")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--signoff", default="")
    ap.add_argument("--resolve", metavar="INTENT_ID")
    ap.add_argument("--ledger", action="store_true")
    ap.add_argument("--creds", default=CREDS)
    a = ap.parse_args()

    if a.selftest:
        return 0 if selftest(True) else 1
    if not selftest(False):
        print("self-test FAILED; refusing to touch the API")
        return 1
    log = Log(RESULTS)
    if a.ledger:
        st = ledger_state(RESULTS, time.time())
        print("sends today %d, at risk today $%s, unresolved %s" % (
            st["sends_today"], st["at_risk"], st["unresolved"] or "none"))
        return 0
    signer = Signer.from_creds(a.creds)
    tp = HttpTransport(BASE, signer, log)
    if a.show:
        show(tp, a.show, a.order_id)
        return 0
    if a.resolve:
        r = resolve_intent(a.resolve, tp, log)
        print(json.dumps(r, default=str, indent=1))
        return 0
    if not (a.slug and a.side and a.price):
        ap.error("--slug, --side and --price are required for an order")
    try:
        order = make_order(a.slug, a.side, a.price, a.qty, a.post_only, a.rest, a.intent_id)
    except decimal.InvalidOperation:
        ap.error("price and qty must be plain decimal numbers")
    now = time.time()
    body = build_body(order, now)
    tick, mq = D("0.01"), D("0.01")
    mv = []
    if not a.offline:
        st, r, _ = _get(tp, "/v1/market/slug/%s" % order["slug"])
        m = r.get("market") if isinstance(r, dict) else None
        mv, t2, m2, _ = check_market(m, now)
        tick, mq = t2 or tick, m2 or mq
        if st != 200:
            mv = ["market GET -> HTTP %s" % st] + mv
    bad = check_order(order, body, tick, mq) + mv
    tok = token_for(order, BASE)
    h, msg = signer.headers("POST", ORDER_ROUTE)
    print("=" * 72)
    print("POLYMARKET US ORDER -- %s" % ("LIVE REQUEST" if a.live else "DRY RUN, NOT SENT"))
    print("=" * 72)
    print("  buy %s %s contract(s) at up to $%s each in %s" % (
        order["side"].upper(), fmt(order["qty"]), fmt(order["price"]), order["slug"]))
    print("  worst case $%s (every contract filled, then lost); fee at that price $%s"
          % (fmt(worst_case(order)), fmt(fee(order["price"], order["qty"]))))
    print("  POST %s%s" % (BASE, ORDER_ROUTE))
    print("  body %s" % json.dumps(body))
    print("  signed message '%s' with key %s -> signature %s... (%d bytes; never shown in full:"
          " it does not cover the body)" % (msg, mask(signer.key_id),
                                           h["X-PM-Signature"][:6],
                                           len(base64.b64decode(h["X-PM-Signature"]))))
    print("  intent id %s" % order["intent_id"])
    if bad:
        print("\n  REFUSED BY THE RAILS:")
        for b in bad:
            print("    - " + b)
        _refuse(log, order, bad)
        return 1
    print("\n  SIGN-OFF TOKEN: %s" % tok)
    if not a.live:
        log.write({"kind": "dryrun", "intent_id": order["intent_id"], "token": tok,
                   "slug": order["slug"], "side": order["side"],
                   "price": fmt(order["price"]), "qty": fmt(order["qty"]), "body": body})
        print("  DRY RUN. Nothing was sent. The operator approves THIS order, then:")
        print("    python research/polyorder.py --slug %s --side %s --price %s --qty %s%s"
              " --live --signoff %s" % (order["slug"], order["side"], fmt(order["price"]),
                                        fmt(order["qty"]),
                                        " --intent-id " + a.intent_id if a.intent_id else "",
                                        tok))
        return 0
    r = run_live(order, a.signoff, tp, BASE, log)
    print(json.dumps({k: (fmt(v) if isinstance(v, D) else v) for k, v in r.items()},
                     default=str, indent=1))
    return 0 if r.get("sent") else 1


if __name__ == "__main__":
    sys.exit(main())
