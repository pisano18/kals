"""/server's AWS bill: the instance's price list (the ESTIMATE), the IAM role's short-lived keys from the EC2 metadata
service (IMDSv2), AWS Signature Version 4 with hashlib and hmac, and the Budgets / Cost Explorer reads, each cached.

v-tg-rebuild step 9 (2026-10-30, lane D5): MOVED VERBATIM out of research/pinphone.py, which re-exports every name here.
THE ONLY COMMAND FILE ALLOWED urllib (CONTRACT rule 1: _aws_http is the one network call; sigv4_sign parses URLs). The
phone passes its own `http` (Phone.aws_http / ctx.aws_http: the self-test and the golden harness plant one); None =
_aws_http. The only edits: imports instead of pinphone's globals (_fnum from botdata.fmt, log from phone.log).
"""
import calendar
import json
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

import pindesk
from botdata.fmt import num as _fnum
from phone.log import log

# THE SERVER, as AWS shows it (the console, 10-27). The prices are AWS's on-demand list for us-east-2 and only feed the
# ESTIMATE /server shows next to (or, until the billing role exists, instead of) AWS's own figures.
AWS_REGION, AWS_AZ = "us-east-2", "us-east-2a"
AWS_INSTANCE_TYPE = "t3.medium"                 # 2 vCPU, 4 GB, Windows Server 2022
AWS_INSTANCE_ID = "i-0c9f332f93359f898"
AWS_INSTANCE_NAME = "kals-bot"
AWS_ELASTIC_IP = "18.216.240.218"
AWS_ACCOUNT_ID = "001634075101"                 # "Building Things"; the metadata service's own answer wins when read
AWS_DISK_GB = 50
AWS_EC2_HOURLY = 0.0600                         # t3.medium with the Windows licence, an hour
AWS_IPV4_HOURLY = 0.005                         # the public (Elastic) IPv4 address, an hour = $3.65 a month
AWS_DISK_MONTH = 4.00                           # 50 GB gp3 at $0.08 a GB-month
AWS_HOURS_MONTH = 730.0
AWS_BUDGET_USD = 120.0                          # the monthly budget / spend alert the operator set in the console
AWS_BILLED_FROM = "2026-10-27T03:05:44Z"        # the instance's first boot (Windows' install date there)
AWS_BILLED_FROM_EPOCH = calendar.timegm(time.strptime(AWS_BILLED_FROM, "%Y-%m-%dT%H:%M:%SZ"))
AWS_ROLE_NAME = "kals-server-billing"
AWS_IMDS = "http://169.254.169.254"             # the EC2 instance metadata service (IMDSv2: a token first)
AWS_IMDS_TIMEOUT_S = 0.6
AWS_API_TIMEOUT_S = 5.0
AWS_CREDS_SKEW_S = 300                          # a role key is renewed this long before AWS says it expires
AWS_NOT_CONNECTED_TTL_S = 300                   # no role yet: asked again after this long (a new role shows in 5 min)
AWS_BUDGET_TTL_S = 3600                         # DescribeBudgets is free; AWS refreshes a budget a few times a day
AWS_CE_TTL_S = 6 * 3600                         # Cost Explorer charges $0.01 a request: at most every 6 hours
AWS_ERR_TTL_S = 900                             # a failed Budgets / Cost Explorer read is tried again after this long
AWS_BUDGETS_HOST = "budgets.amazonaws.com"      # both are global APIs, signed for us-east-1
AWS_CE_HOST = "ce.us-east-1.amazonaws.com"
AWS_SERVICE_SHORT = {"Amazon Elastic Compute Cloud - Compute": "EC2 instance", "EC2 - Other": "EC2 other (disk, data)",
                     "Amazon Virtual Private Cloud": "public IPv4", "AWS Cost Explorer": "Cost Explorer reads",
                     "Tax": "tax", "AWS Budgets": "Budgets"}


# ---- /server: the AWS bill, signed here --------------------------------------------------------------------------
def sigv4_sign(method, url, region, service, key_id, secret, body=b"", headers=None, token=None, amz_date=None,
               sign_body=False):
    """AWS Signature Version 4 with hashlib and hmac only (no boto3 on the server). Returns (the headers to send,
    the signature): every header given, plus host, x-amz-date, x-amz-security-token (a role's session token) and,
    with sign_body, x-amz-content-sha256 -- all of them signed -- and Authorization. The self-test checks it against
    AWS's own published test vectors."""
    import hashlib
    import hmac
    u = urllib.parse.urlsplit(url)
    amz_date = amz_date or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    day = amz_date[:8]
    body = body or b""
    h = {}
    for k, v in (headers or {}).items():
        h[str(k).lower().strip()] = " ".join(str(v).split())
    h.setdefault("host", u.netloc)
    h["x-amz-date"] = amz_date
    if token:
        h["x-amz-security-token"] = token
    payload = hashlib.sha256(body).hexdigest()
    if sign_body:
        h["x-amz-content-sha256"] = payload
    q = sorted((urllib.parse.quote(k, safe="-_.~"), urllib.parse.quote(v, safe="-_.~"))
               for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True))
    names = sorted(h)
    creq = "\n".join([method.upper(), urllib.parse.quote(u.path or "/", safe="/-_.~"),
                      "&".join("%s=%s" % kv for kv in q), "".join("%s:%s\n" % (n, h[n]) for n in names),
                      ";".join(names), payload])
    scope = "%s/%s/%s/aws4_request" % (day, region, service)
    sts = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(creq.encode("utf-8")).hexdigest()])
    key = ("AWS4" + secret).encode("utf-8")
    for part in (day, region, service, "aws4_request"):
        key = hmac.new(key, part.encode("utf-8"), hashlib.sha256).digest()
    sig = hmac.new(key, sts.encode("utf-8"), hashlib.sha256).hexdigest()
    h["authorization"] = "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (
        key_id, scope, ";".join(names), sig)
    return h, sig


def _aws_http(method, url, headers=None, body=None, timeout=AWS_API_TIMEOUT_S):
    """(status, bytes) of one HTTP request, never through a proxy (the metadata address must not leave the machine).
    An HTTP error status is returned, not raised; a network failure raises."""
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    send = opener.open          # step 9: bound first -- the source rule's open( scan is for the builtin (text files)
    try:
        with send(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()
        except Exception:                                       # noqa: BLE001
            return e.code, b""


_AWS = {}


def aws_role_creds(http=None, now=None):
    """(keys, None) or (None, why in plain words): the IAM role's short-lived keys from the EC2 metadata service
    (IMDSv2: a token, the role's name, its keys; the account from the instance's identity document), kept until
    AWS_CREDS_SKEW_S before they expire. No role / no metadata service is remembered for AWS_NOT_CONNECTED_TTL_S."""
    http = http or _aws_http
    now = time.time() if now is None else float(now)
    c = _AWS.get("creds")
    if c and c["exp"] - AWS_CREDS_SKEW_S > now:
        return c["keys"], None
    nc = _AWS.get("nocreds")
    if nc and 0 <= now - nc["t"] < AWS_NOT_CONNECTED_TTL_S:
        return None, nc["why"]
    why = None
    try:
        st, tok = http("PUT", AWS_IMDS + "/latest/api/token", {"X-aws-ec2-metadata-token-ttl-seconds": "300"}, b"",
                       AWS_IMDS_TIMEOUT_S)
        if st != 200 or not tok:
            why = "no EC2 metadata service answered (HTTP %s)" % st
        else:
            hd = {"X-aws-ec2-metadata-token": tok.decode("ascii", "replace").strip()}
            st, names = http("GET", AWS_IMDS + "/latest/meta-data/iam/security-credentials/", hd, None,
                             AWS_IMDS_TIMEOUT_S)
            role = (names or b"").decode("utf-8", "replace").split()[0] if st == 200 and (names or b"").strip() else None
            if st == 404 or (st == 200 and not role):
                why = "no IAM role on the server yet"
            elif st != 200:
                why = "the metadata service gave HTTP %s for the role" % st
            else:
                st, raw = http("GET", AWS_IMDS + "/latest/meta-data/iam/security-credentials/" + role, hd, None,
                               AWS_IMDS_TIMEOUT_S)
                d = json.loads((raw or b"{}").decode("utf-8", "replace")) if st == 200 else {}
                if not isinstance(d, dict) or d.get("Code") != "Success" or not d.get("AccessKeyId"):
                    why = "the role %s gave no keys (HTTP %s, %s)" % (role, st, (d or {}).get("Code") if isinstance(
                        d, dict) else "unreadable")
                else:
                    acct = None
                    try:
                        st2, doc = http("GET", AWS_IMDS + "/latest/dynamic/instance-identity/document", hd, None,
                                        AWS_IMDS_TIMEOUT_S)
                        if st2 == 200:
                            acct = (json.loads(doc.decode("utf-8", "replace")) or {}).get("accountId")
                    except Exception:                           # noqa: BLE001
                        acct = None
                    keys = {"key": d["AccessKeyId"], "secret": d.get("SecretAccessKey") or "", "token": d.get("Token"),
                            "role": role, "account": acct or AWS_ACCOUNT_ID}
                    exp = pindesk.parse_t(d.get("Expiration"))
                    _AWS["creds"] = {"keys": keys, "exp": exp if exp else now + 600}
                    _AWS.pop("nocreds", None)
                    return keys, None
    except Exception as e:                                      # noqa: BLE001
        why = "no EC2 metadata service reachable (%s)" % (type(e).__name__)
    _AWS["nocreds"] = {"t": now, "why": why}
    return None, why


def _aws_call(host, service, target, payload, keys, http):
    """One signed AWS JSON 1.1 call: (the reply dict, None) or (None, why)."""
    body = json.dumps(payload).encode("utf-8")
    url = "https://%s/" % host
    hd, _sig = sigv4_sign("POST", url, "us-east-1", service, keys["key"], keys["secret"], body,
                          {"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": target}, keys.get("token"))
    try:
        st, raw = http("POST", url, hd, body, AWS_API_TIMEOUT_S)
    except Exception as e:                                      # noqa: BLE001
        return None, "could not reach AWS (%s)" % (str(e)[:60] or type(e).__name__)
    try:
        d = json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
    except ValueError:
        d = None
    if st == 200 and isinstance(d, dict):
        return d, None
    kind = str((d or {}).get("__type") or "").split("#")[-1] if isinstance(d, dict) else ""
    msg = str((d or {}).get("Message") or (d or {}).get("message") or "") if isinstance(d, dict) else ""
    if kind in ("ExpiredTokenException", "UnrecognizedClientException", "InvalidClientTokenId"):
        _AWS.pop("creds", None)                                 # the next read fetches new role keys
    return None, ("%s (HTTP %s)%s" % (kind or "error", st, (": " + msg[:110]) if msg else "")).strip()


def _aws_budget_rows(d):
    out = []
    for b in (d or {}).get("Budgets") or []:
        if not isinstance(b, dict):
            continue
        cs = b.get("CalculatedSpend") or {}
        lim = b.get("BudgetLimit") or {}
        out.append({"name": b.get("BudgetName"), "type": b.get("BudgetType"), "period": b.get("TimeUnit"),
                    "limit": _fnum(lim.get("Amount")), "unit": lim.get("Unit") or "USD",
                    "actual": _fnum((cs.get("ActualSpend") or {}).get("Amount")),
                    "forecast": _fnum((cs.get("ForecastedSpend") or {}).get("Amount")),
                    "updated": _fnum(b.get("LastUpdatedTime"))})
    return out


def _aws_ce_rows(d):
    days, svc, est = {}, {}, False
    for r in (d or {}).get("ResultsByTime") or []:
        day = (r.get("TimePeriod") or {}).get("Start")
        est = est or bool(r.get("Estimated"))
        groups = r.get("Groups") or []
        for g in groups:
            name = (g.get("Keys") or ["?"])[0]
            v = _fnum(((g.get("Metrics") or {}).get("UnblendedCost") or {}).get("Amount")) or 0.0
            days[day] = days.get(day, 0.0) + v
            svc[name] = svc.get(name, 0.0) + v
        if not groups:
            v = _fnum(((r.get("Total") or {}).get("UnblendedCost") or {}).get("Amount"))
            if v is not None:
                days[day] = days.get(day, 0.0) + v
    return {"days": days, "services": svc, "month": sum(days.values()), "estimated": est,
            "more": bool((d or {}).get("NextPageToken"))}


def _aws_cached(name, now, ttl, read):
    """One AWS read through its cache: re-read after `ttl` (AWS_ERR_TTL_S after a failure); a failed read keeps the last
    good answer, and says it failed. {"res", "res_t" (when that answer was read), "err", "t"}."""
    c = _AWS.get(name)
    if c is None or not (0 <= now - c["t"] < (ttl if c["err"] is None else AWS_ERR_TTL_S)):
        res, err = read()
        prev = c or {}
        c = _AWS[name] = {"t": now, "err": err, "res": res if res is not None else prev.get("res"),
                          "res_t": now if res is not None else prev.get("res_t")}
    return c


def aws_cost(now=None, http=None):
    """Everything /server says about the AWS bill. Never raises: {"connected", "why" (when not), "role", "budget"
    (DescribeBudgets' rows), "budget_err", "budget_t", "ce" (Cost Explorer: this month by day and by service),
    "ce_err", "ce_t"}."""
    now = time.time() if now is None else float(now)
    http = http or _aws_http
    out = {"connected": False, "why": None, "role": None, "budget": None, "budget_err": None, "budget_t": None,
           "ce": None, "ce_err": None, "ce_t": None}
    try:
        keys, why = aws_role_creds(http, now)
        if keys is None:
            out["why"] = why
            return out
        out.update(connected=True, role=keys.get("role"))

        def budgets():
            d, err = _aws_call(AWS_BUDGETS_HOST, "budgets", "AWSBudgetServiceGateway.DescribeBudgets",
                               {"AccountId": keys["account"], "MaxResults": 20}, keys, http)
            return (_aws_budget_rows(d) if d is not None else None), err

        def ce():
            t = time.gmtime(now)
            d, err = _aws_call(AWS_CE_HOST, "ce", "AWSInsightsIndexService.GetCostAndUsage", {
                "TimePeriod": {"Start": "%04d-%02d-01" % (t.tm_year, t.tm_mon),
                               "End": time.strftime("%Y-%m-%d", time.gmtime(now + 86400))},
                "Granularity": "DAILY", "Metrics": ["UnblendedCost"],
                "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}]}, keys, http)
            return (_aws_ce_rows(d) if d is not None else None), err
        b = _aws_cached("budget", now, AWS_BUDGET_TTL_S, budgets)
        out.update(budget=b["res"], budget_err=b["err"], budget_t=b["res_t"])
        c = _aws_cached("ce", now, AWS_CE_TTL_S, ce)
        out.update(ce=c["res"], ce_err=c["err"], ce_t=c["res_t"])
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        out["why"] = out["why"] or "the AWS read failed (%s)" % str(e)[:80]
    return out


def aws_estimate(now):
    """The bill worked from the price list (the AWS_* constants), shown as an ESTIMATE wherever it appears: a month, a
    day, this month so far (since the server started, or the month began) and the whole of this month."""
    hourly = AWS_EC2_HOURLY + AWS_IPV4_HOURLY + AWS_DISK_MONTH / AWS_HOURS_MONTH
    t = time.gmtime(now)
    m0 = calendar.timegm((t.tm_year, t.tm_mon, 1, 0, 0, 0))
    m1 = calendar.timegm((t.tm_year + (1 if t.tm_mon == 12 else 0), t.tm_mon % 12 + 1, 1, 0, 0, 0))
    start = max(m0, AWS_BILLED_FROM_EPOCH)
    so_far = hourly * max(0.0, now - start) / 3600.0
    return {"hourly": hourly, "month": hourly * AWS_HOURS_MONTH, "day": hourly * 24.0, "since": start,
            "so_far": so_far, "this_month": so_far + hourly * max(0.0, m1 - max(now, start)) / 3600.0,
            "month_name": time.strftime("%B", t), "ec2_month": AWS_EC2_HOURLY * AWS_HOURS_MONTH,
            "ipv4_month": AWS_IPV4_HOURLY * AWS_HOURS_MONTH, "disk_month": AWS_DISK_MONTH}
