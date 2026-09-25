"""taxledger.py -- a tax-ready record of the Kalshi account, from Kalshi's books.

WHY THIS EXISTS. Kalshi does not send a tax form that covers event-contract
trades (its help page, updated 2026-06-22, lists 1099-INT for interest,
1099-MISC for rewards, and 1099-B / 1099-DA for crypto transfers only). So
the operator has to self-report every dollar these bots made or lost, and
the IRS has not said HOW such contracts are taxed. See
results/TAX_NOTES_2026-09-25.md for the plain-language explanation and the
sources. This file only builds the record; it gives no tax opinion.

WHAT IT READS -- nothing it computes itself:
  results/kalshi_ledger.json    /portfolio/settlements, one row per market
                                (research/pinledger.py writes it)
  results/kalshi_transfers.json /portfolio/deposits and /withdrawals
                                (research/pinxfer.py writes it)
Money per market is `pinledger.pnl` -- payout minus both sides' cost minus
fees, as Kalshi settled it -- so this file and pinday can never disagree.
A hedged market (both YES and NO held) is ONE row, netted, exactly as the
exchange settled it.

WHAT IT WRITES: results/tax/kalshi_<year>_ledger.csv, one file, filterable on
the `section` column:
  MARKET       one row per settled market: date (ET, from the ticker's own
               clock), ticker, contracts, cost, proceeds, fees, net
  DEPOSIT      each finished deposit: gross, fee, credited (no ids)
  WITHDRAWAL   each finished withdrawal (none on this account as of writing)
  MONTH        per ET month: markets, cost, proceeds, fees, net, and the sum
               of winning markets and losing markets separately
  YTD          the year to date, the same columns; plus YTD_BY_DAY, which
               nets each ET day first (the "session" view some preparers use)
  SET_ASIDE_ILLUSTRATIVE
               what a few flat rates would put aside on three different
               taxable bases. ILLUSTRATIVE ONLY: not a tax calculation, not
               advice, and the right base is a question for a CPA.

Every date column is ET because a tax year is a calendar year where the
operator lives; `settled_utc` is kept beside it, as Kalshi sent it.

No account numbers, key ids, transfer ids or subaccount numbers are written.

    python research/taxledger.py                 # 2026, writes the CSV
    python research/taxledger.py --year 2026 --check-balance   # + a GET of
                                                 # /portfolio/balance to
                                                 # reconcile deposits + P&L
    python research/taxledger.py --selftest
"""
import argparse
import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pinday                                                    # noqa: E402
import pinledger                                                 # noqa: E402
import pinxfer                                                   # noqa: E402

RESULTS = os.path.join(os.path.dirname(HERE), "results")
LEDGER = os.path.join(RESULTS, "kalshi_ledger.json")
TRANSFERS = os.path.join(RESULTS, "kalshi_transfers.json")
OUTDIR = os.path.join(RESULTS, "tax")

# Flat federal rates used ONLY to illustrate a set-aside. 12/22/24/32 are
# four of the 2026 federal brackets; which one applies depends on all of the
# operator's income, which this file does not know and must not guess.
FED_RATES = (0.12, 0.22, 0.24, 0.32)
# One state rate, again purely illustrative. States range from 0% to over 10%.
STATE_RATE = 0.05
# If Section 1256 applied (it is an aggressive, unconfirmed position): 60% is
# taxed at the long-term rate and 40% at the ordinary rate. Shown for the 22%
# bracket, whose long-term capital-gains rate is 15%.
S1256_22 = 0.60 * 0.15 + 0.40 * 0.22
# 26 USC 165(d) as amended in 2025: for tax years after 2025, only 90% of
# wagering losses are deductible, and only up to wagering gains.
WAGER_LOSS_FRACTION = 0.90

COLUMNS = ["section", "date_et", "settled_utc", "ticker", "book", "result",
           "yes_contracts", "no_contracts", "contracts",
           "cost_usd", "proceeds_usd", "fees_usd", "net_usd",
           "n_markets", "winning_usd", "losing_usd",
           "transfer_gross_usd", "transfer_fee_usd", "transfer_net_usd",
           "method", "rate", "base_usd", "set_aside_usd", "label"]


def _f(x, nd=4):
    return "%.*f" % (nd, x)


def _year_of(day):
    try:
        return int(str(day)[:4])
    except ValueError:
        return None


def market_rows(settlements):
    """([row], skipped). One dict per settled market, money from Kalshi."""
    rows, skipped = [], 0
    for s in (settlements or {}).values():
        if not isinstance(s, dict):
            skipped += 1
            continue
        tk = s.get("ticker") or ""
        day = pinday.et_day_of_ticker(tk)
        if day is None:
            e = pinday._epoch_of(s.get("settled_time"))
            day = pinday.et_day_of_epoch(e) if e is not None else None
        if not tk or day is None:
            skipped += 1
            continue
        yes_n = pinledger.money(s, "yes_count_fp")
        no_n = pinledger.money(s, "no_count_fp")
        cost = (pinledger.money(s, "yes_total_cost_dollars")
                + pinledger.money(s, "no_total_cost_dollars"))
        fees = pinledger.money(s, "fee_cost")
        proceeds = pinledger.payout(s)
        net = proceeds - cost - fees
        rows.append({"date_et": day, "settled_utc": str(s.get("settled_time") or ""),
                     "ticker": tk, "book": pinday.book_of(tk),
                     "result": str(s.get("market_result") or ""),
                     "yes": yes_n, "no": no_n, "cost": cost, "proceeds": proceeds,
                     "fees": fees, "net": net, "check": pinledger.pnl(s)})
    rows.sort(key=lambda r: (r["date_et"], r["settled_utc"], r["ticker"]))
    return rows, skipped


def transfer_rows(xfer):
    """[row] for finished deposits and withdrawals. Ids are never copied."""
    out = []
    for kind, recs in (("DEPOSIT", xfer.get("deposits") or []),
                       ("WITHDRAWAL", xfer.get("withdrawals") or [])):
        for r in recs:
            if not pinxfer.is_done(r):
                continue
            t = pinxfer.when(r)
            gross = pinxfer._num(r, "amount_cents") / 100.0
            fee = pinxfer._num(r, "fee_cents") / 100.0
            out.append({"section": kind,
                        "date_et": pinday.et_day_of_epoch(t) if t else "",
                        "gross": gross, "fee": fee, "net": gross - fee,
                        "method": str(r.get("type") or "")})
    out.sort(key=lambda r: (r["section"], r["date_et"]))
    return out


def pending_transfers(xfer):
    return sum(1 for k in ("deposits", "withdrawals")
               for r in (xfer.get(k) or []) if not pinxfer.is_done(r))


def _agg(rows):
    a = {"n": 0, "cost": 0.0, "proceeds": 0.0, "fees": 0.0, "net": 0.0,
         "win": 0.0, "lose": 0.0}
    for r in rows:
        a["n"] += 1
        for k in ("cost", "proceeds", "fees", "net"):
            a[k] += r[k]
        if r["net"] > 0:
            a["win"] += r["net"]
        else:
            a["lose"] += -r["net"]
    return a


def by_day(rows):
    days = {}
    for r in rows:
        days.setdefault(r["date_et"], 0.0)
        days[r["date_et"]] += r["net"]
    win = sum(v for v in days.values() if v > 0)
    lose = sum(-v for v in days.values() if v < 0)
    return days, win, lose


def bases(ytd, day_win, day_lose):
    """The three taxable bases the set-aside is shown on. None of them is
    asserted to be right; they differ by how the IRS might classify the
    income, which it has not done."""
    net = max(0.0, ytd["net"])
    win, lose = ytd["win"], ytd["lose"]
    wager_item = win - min(WAGER_LOSS_FRACTION * lose, win)
    return [
        ("A", "net result for the year (the base if treated as capital gain or other income)", net),
        ("B", "per-market gains minus 90% of per-market losses (the base if treated as gambling AND you itemize)",
         max(0.0, wager_item)),
        ("C", "per-market gains only (the base if treated as gambling and you take the standard deduction, "
              "which gives no gambling-loss deduction at all)", win),
    ]


def build(settlements, xfer, year):
    """Everything the CSV holds, as a dict. Pure: no I/O."""
    mk_all, skipped = market_rows(settlements)
    mk = [r for r in mk_all if _year_of(r["date_et"]) == year]
    tr = [r for r in transfer_rows(xfer) if _year_of(r["date_et"]) == year]
    months = {}
    for r in mk:
        months.setdefault(r["date_et"][:7], []).append(r)
    month_agg = [(m, _agg(v)) for m, v in sorted(months.items())]
    ytd = _agg(mk)
    days, dwin, dlose = by_day(mk)
    set_aside = []
    for code, what, base in bases(ytd, dwin, dlose):
        for rate in FED_RATES:
            set_aside.append((code, what, "federal %d%%" % round(rate * 100), rate, base))
        if code == "A":
            set_aside.append((code, what, "Section 1256 60/40 blend at the 22%% bracket (%.1f%%)"
                              % (S1256_22 * 100), S1256_22, base))
            set_aside.append((code, what, "state %d%%" % round(STATE_RATE * 100), STATE_RATE, base))
    worst_mismatch = max([abs(r["net"] - r["check"]) for r in mk_all] or [0.0])
    dep_in, dep_out, dep_gross, dep_fees = pinxfer.totals(xfer.get("deposits"),
                                                          xfer.get("withdrawals"))
    return {"year": year, "markets": mk, "markets_all": mk_all, "skipped": skipped,
            "other_years": len(mk_all) - len(mk), "transfers": tr,
            "months": month_agg, "ytd": ytd, "days": days, "day_win": dwin,
            "day_lose": dlose, "set_aside": set_aside, "worst_mismatch": worst_mismatch,
            "all_time_net": sum(r["net"] for r in mk_all),
            "dep_in_net": dep_in, "wd_out": dep_out, "dep_gross": dep_gross,
            "dep_fees": dep_fees, "pending": pending_transfers(xfer)}


def to_csv(b):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in b["markets"]:
        w.writerow({"section": "MARKET", "date_et": r["date_et"], "settled_utc": r["settled_utc"],
                    "ticker": r["ticker"], "book": r["book"], "result": r["result"],
                    "yes_contracts": _f(r["yes"], 2), "no_contracts": _f(r["no"], 2),
                    "contracts": _f(r["yes"] + r["no"], 2),
                    "cost_usd": _f(r["cost"]), "proceeds_usd": _f(r["proceeds"]),
                    "fees_usd": _f(r["fees"]), "net_usd": _f(r["net"])})
    for r in b["transfers"]:
        w.writerow({"section": r["section"], "date_et": r["date_et"],
                    "transfer_gross_usd": _f(r["gross"], 2), "transfer_fee_usd": _f(r["fee"], 2),
                    "transfer_net_usd": _f(r["net"], 2), "method": r["method"],
                    "label": "deposit fee is Kalshi's card-processing fee; it is not in any market's fees"
                    if r["section"] == "DEPOSIT" and r["fee"] > 0 else ""})

    def agg_row(section, key, a, label=""):
        w.writerow({"section": section, "date_et": key, "n_markets": a["n"],
                    "cost_usd": _f(a["cost"]), "proceeds_usd": _f(a["proceeds"]),
                    "fees_usd": _f(a["fees"]), "net_usd": _f(a["net"]),
                    "winning_usd": _f(a["win"]), "losing_usd": _f(a["lose"]), "label": label})
    for m, a in b["months"]:
        agg_row("MONTH", m, a, "ET calendar month; winning/losing = sum over markets that made / lost money")
    agg_row("YTD", str(b["year"]), b["ytd"], "year to date, ET; netted per market as Kalshi settled it")
    w.writerow({"section": "YTD_BY_DAY", "date_et": str(b["year"]), "n_markets": len(b["days"]),
                "net_usd": _f(sum(b["days"].values())), "winning_usd": _f(b["day_win"]),
                "losing_usd": _f(b["day_lose"]),
                "label": "each ET day netted first; n_markets here counts DAYS"})
    dep = [r for r in b["transfers"] if r["section"] == "DEPOSIT"]
    wd = [r for r in b["transfers"] if r["section"] == "WITHDRAWAL"]
    w.writerow({"section": "TRANSFERS_YTD", "date_et": str(b["year"]),
                "transfer_gross_usd": _f(sum(r["gross"] for r in dep), 2),
                "transfer_fee_usd": _f(sum(r["fee"] for r in dep), 2),
                "transfer_net_usd": _f(sum(r["net"] for r in dep), 2), "method": "deposits",
                "label": "money you put in is NOT income"})
    w.writerow({"section": "TRANSFERS_YTD", "date_et": str(b["year"]),
                "transfer_gross_usd": _f(sum(r["gross"] for r in wd), 2),
                "transfer_fee_usd": _f(sum(r["fee"] for r in wd), 2),
                "transfer_net_usd": _f(sum(r["net"] for r in wd), 2), "method": "withdrawals",
                "label": "money you take out is NOT income either; only the market results are"})
    for code, what, name, rate, base in b["set_aside"]:
        w.writerow({"section": "SET_ASIDE_ILLUSTRATIVE", "date_et": str(b["year"]),
                    "rate": "%.4f" % rate, "base_usd": _f(base, 2),
                    "set_aside_usd": _f(base * rate, 2), "method": "base %s" % code,
                    "label": "ILLUSTRATIVE ONLY, NOT TAX ADVICE: %s on base %s = %s" % (name, code, what)})
    return buf.getvalue()


def report(b, out=print):
    y = b["ytd"]
    out("TAX LEDGER %d -- from Kalshi's own settlement and transfer records" % b["year"])
    if not b["markets"]:
        out("  NO SETTLED MARKETS IN %d. Nothing to report; the CSV holds only headers "
            "and zero totals. (%d markets in other years, %d rows skipped as unreadable.)"
            % (b["year"], b["other_years"], b["skipped"]))
    out("  markets settled: %d   (rows skipped as unreadable: %d; markets in other years: %d)"
        % (y["n"], b["skipped"], b["other_years"]))
    out("  paid for contracts $%.2f   paid back at settlement $%.2f   trading fees $%.2f"
        % (y["cost"], y["proceeds"], y["fees"]))
    out("  NET for the year: $%.2f  =  $%.2f won on winning markets  -  $%.2f lost on losing markets"
        % (y["net"], y["win"], y["lose"]))
    out("  same, each ET day netted first: $%.2f won on up days - $%.2f lost on down days (%d days)"
        % (b["day_win"], b["day_lose"], len(b["days"])))
    for m, a in b["months"]:
        out("    %s  %4d markets  net $%9.2f   (won $%.2f, lost $%.2f, fees $%.2f)"
            % (m, a["n"], a["net"], a["win"], a["lose"], a["fees"]))
    dep = [r for r in b["transfers"] if r["section"] == "DEPOSIT"]
    wd = [r for r in b["transfers"] if r["section"] == "WITHDRAWAL"]
    out("  deposits: %d, $%.2f sent, $%.2f in card fees, $%.2f credited;  withdrawals: %d, $%.2f"
        % (len(dep), sum(r["gross"] for r in dep), sum(r["fee"] for r in dep),
           sum(r["net"] for r in dep), len(wd), sum(r["net"] for r in wd)))
    if b["pending"]:
        out("  NOTE: %d transfer(s) still pending -- not counted" % b["pending"])
    if b["worst_mismatch"] > 1e-9:
        out("  MISMATCH vs pinledger.pnl: worst $%.6f -- DO NOT USE THIS FILE" % b["worst_mismatch"])
    out("  set-aside (ILLUSTRATIVE ONLY):")
    for code, what, name, rate, base in b["set_aside"]:
        out("    base %s $%9.2f x %-48s = $%8.2f" % (code, base, name, base * rate))


def check_balance(b, out=print):
    """GET /portfolio/balance and reconcile: credited deposits - withdrawals +
    every settled market's net should equal cash + open positions."""
    import kauth
    st, bal = kauth.get("/portfolio/balance")
    if st != 200 or not isinstance(bal, dict):
        out("  BALANCE CHECK FAILED: HTTP %s -- not reconciled" % st)
        return None
    cash = float(bal.get("balance") or 0) / 100.0
    pv = float(bal.get("portfolio_value") or 0) / 100.0
    expect = b["dep_in_net"] - b["wd_out"] + b["all_time_net"]
    gap = (cash + pv) - expect
    out("  RECONCILE: deposits credited $%.2f - withdrawals $%.2f + all settled markets $%.2f = $%.2f;"
        " Kalshi shows cash $%.2f + open positions $%.2f = $%.2f;  gap $%.2f"
        % (b["dep_in_net"], b["wd_out"], b["all_time_net"], expect, cash, pv, cash + pv, gap))
    if pv > 0:
        out("  (open positions are valued at market, not at cost, so a gap of that size is expected)")
    return gap


# --------------------------------------------------------------------------
# SELF-TEST: a world where every answer is known, and a world with nothing.
# --------------------------------------------------------------------------

def selftest():
    fails = []

    def ck(cond, msg):
        if not cond:
            fails.append(msg)

    def row(tk, result, yes_n=0.0, yes_cost=0.0, no_n=0.0, no_cost=0.0, fee=0.0,
            st="2026-09-19T12:00:05Z", value=None):
        v = {"yes": 100, "no": 0}.get(result, value)
        return {"ticker": tk, "market_result": result, "value": v,
                "yes_count_fp": "%.2f" % yes_n, "yes_total_cost_dollars": "%.6f" % yes_cost,
                "no_count_fp": "%.2f" % no_n, "no_total_cost_dollars": "%.6f" % no_cost,
                "fee_cost": "%.6f" % fee, "revenue": 0, "settled_time": st}

    SECRET_ID = "deadbeef-0000-4000-8000-SECRETIDXXXX"
    led = {
        # A: 10 YES bought for $9.00, fee $0.05, settles YES -> +$0.95
        "a": row("KXBTC15M-26SEP190800-00", "yes", yes_n=10, yes_cost=9.00, fee=0.05),
        # B: 5 NO bought for $4.90, fee $0.02, settles YES -> -$4.92
        "b": row("KXETH15M-26SEP190815-15", "yes", no_n=5, no_cost=4.90, fee=0.02),
        # C: hedged, 4 YES for $3.80 and 4 NO for $0.40, settles NO -> 4 - 4.20 - 0.01 = -0.21
        "c": row("KXSOL15M-26SEP190830-30", "no", yes_n=4, yes_cost=3.80, no_n=4, no_cost=0.40, fee=0.01),
        # D: a tie on the coin race pays 50c: 2 YES for $1.94 -> 1.00 - 1.94 = -0.94
        "d": row("KXCRYPTOLEAD15M-26SEP190845", "scalar", yes_n=2, yes_cost=1.94, value=50),
        # E: August, 20 NO for $19.60, fee $0.04, settles NO -> +$0.36
        "e": row("KXXRP15M-26AUG200100-00", "no", no_n=20, no_cost=19.60, fee=0.04,
                 st="2026-08-20T05:00:05Z"),
        # F: closes 23:45 ET Sep 30 but settles 03:45 UTC Oct 1 -> belongs to SEPTEMBER
        "f": row("KXBNB15M-26SEP302345-45", "yes", yes_n=1, yes_cost=0.90,
                 st="2026-10-01T03:45:05Z"),
        # G: a 2025 market, must be excluded from 2026 and counted as other-year
        "g": row("KXBTC15M-25DEC311200-00", "yes", yes_n=1, yes_cost=0.50,
                 st="2025-12-31T17:00:05Z"),
        # H: unreadable: no ticker
        "h": {"market_result": "yes", "settled_time": "2026-09-19T12:00:05Z"},
    }
    xfer = {"deposits": [
        {"id": SECRET_ID, "amount_cents": 10000, "fee_cents": 0, "status": "applied",
         "type": "ach", "finalized_ts": 1787000000},
        {"id": SECRET_ID, "amount_cents": 5000, "fee_cents": 100, "status": "applied",
         "type": "debit", "finalized_ts": 1788000000},
        {"id": SECRET_ID, "amount_cents": 99900, "fee_cents": 0, "status": "pending",
         "type": "ach", "finalized_ts": 1788500000},
        {"id": SECRET_ID, "amount_cents": 7777, "fee_cents": 0, "status": "applied",
         "type": "ach", "finalized_ts": 1735000000},   # Dec 2024, other year
    ], "withdrawals": [
        {"id": SECRET_ID, "amount_cents": 2000, "fee_cents": 0, "status": "applied",
         "type": "ach", "finalized_ts": 1788100000}]}

    b = build(led, xfer, 2026)
    near = lambda a, e: abs(a - e) < 1e-6  # noqa: E731
    nets = {r["ticker"]: r["net"] for r in b["markets"]}
    ck(near(nets.get("KXBTC15M-26SEP190800-00", 9), 0.95), "A net %s != 0.95" % nets.get("KXBTC15M-26SEP190800-00"))
    ck(near(nets.get("KXETH15M-26SEP190815-15", 9), -4.92), "B net != -4.92")
    ck(near(nets.get("KXSOL15M-26SEP190830-30", 9), -0.21), "hedged C net != -0.21")
    ck(near(nets.get("KXCRYPTOLEAD15M-26SEP190845", 9), -0.94), "tie D net != -0.94 (tie must pay half)")
    ck(near(nets.get("KXXRP15M-26AUG200100-00", 9), 0.36), "E net != 0.36")
    ck(near(nets.get("KXBNB15M-26SEP302345-45", 9), 0.10), "F net != 0.10")
    ck("KXBTC15M-25DEC311200-00" not in nets, "2025 market leaked into 2026")
    ck(b["other_years"] == 1, "other-year count %s != 1" % b["other_years"])
    ck(b["skipped"] == 1, "skipped %s != 1 (the no-ticker row)" % b["skipped"])
    ck(b["ytd"]["n"] == 6, "ytd markets %s != 6" % b["ytd"]["n"])
    exp_net = 0.95 - 4.92 - 0.21 - 0.94 + 0.36 + 0.10
    ck(near(b["ytd"]["net"], exp_net), "ytd net %.6f != %.6f" % (b["ytd"]["net"], exp_net))
    ck(near(b["ytd"]["win"], 0.95 + 0.36 + 0.10), "ytd winning != 1.41")
    ck(near(b["ytd"]["lose"], 4.92 + 0.21 + 0.94), "ytd losing != 6.07")
    ck(near(b["ytd"]["fees"], 0.05 + 0.02 + 0.01 + 0.04), "ytd fees != 0.12")
    ck(near(b["ytd"]["proceeds"] - b["ytd"]["cost"] - b["ytd"]["fees"], b["ytd"]["net"]),
       "proceeds - cost - fees != net")
    mon = dict(b["months"])
    ck(sorted(mon) == ["2026-08", "2026-09"], "months %s" % sorted(mon))
    ck(near(mon["2026-08"]["net"], 0.36), "August net != 0.36")
    ck(mon["2026-09"]["n"] == 5, "Sep must hold 5 markets incl. the 03:45-UTC-Oct-1 one")
    ck(near(sum(a["net"] for a in mon.values()), b["ytd"]["net"]), "months do not sum to ytd")
    # per-day view: Sep 19 nets -5.12, Sep 30 +0.10, Aug 20 +0.36
    ck(near(b["day_win"], 0.46) and near(b["day_lose"], 5.12),
       "day view win %.4f lose %.4f" % (b["day_win"], b["day_lose"]))
    ck(b["worst_mismatch"] < 1e-9, "disagrees with pinledger.pnl")
    # transfers: two finished 2026 deposits, pending and 2024 excluded; one withdrawal
    dep = [r for r in b["transfers"] if r["section"] == "DEPOSIT"]
    wd = [r for r in b["transfers"] if r["section"] == "WITHDRAWAL"]
    ck(len(dep) == 2 and near(sum(r["gross"] for r in dep), 150.0), "deposits gross != 150")
    ck(near(sum(r["fee"] for r in dep), 1.0) and near(sum(r["net"] for r in dep), 149.0),
       "deposit fee/net wrong")
    ck(len(wd) == 1 and near(wd[0]["net"], 20.0), "withdrawal wrong")
    ck(b["pending"] == 1, "pending count %s != 1" % b["pending"])
    # set-aside: ytd net is NEGATIVE -> base A is 0, never a negative set-aside
    sa = {(c, n): base * rate for c, _, n, rate, base in b["set_aside"]}
    ck(near(sa[("A", "federal 22%")], 0.0), "negative year must set aside 0 on base A")
    # base B: gains 1.41 - min(0.9*6.07, 1.41) = 0 ; base C: 1.41 at 22% = 0.3102
    ck(near(sa[("B", "federal 22%")], 0.0), "base B wrong")
    ck(near(sa[("C", "federal 22%")], 1.41 * 0.22), "base C wrong")
    # CSV: parses, sections present, no identifier leaked
    text = to_csv(b)
    ck(SECRET_ID not in text, "a transfer id leaked into the CSV")
    rows = list(csv.DictReader(io.StringIO(text)))
    secs = {r["section"] for r in rows}
    for s in ("MARKET", "DEPOSIT", "WITHDRAWAL", "MONTH", "YTD", "YTD_BY_DAY",
              "TRANSFERS_YTD", "SET_ASIDE_ILLUSTRATIVE"):
        ck(s in secs, "CSV lacks section %s" % s)
    ck(all("ILLUSTRATIVE" in r["label"] for r in rows if r["section"] == "SET_ASIDE_ILLUSTRATIVE"),
       "a set-aside row is not labelled illustrative")
    csv_net = sum(float(r["net_usd"]) for r in rows if r["section"] == "MARKET")
    ck(abs(csv_net - exp_net) < 0.001, "CSV market rows sum %.4f != %.4f" % (csv_net, exp_net))
    ck(any(r["section"] == "MARKET" and r["ticker"] == "KXBNB15M-26SEP302345-45"
           and r["date_et"] == "2026-09-30" for r in rows), "F dated wrong in CSV")

    # A POSITIVE planted year: base A must be the net, B and C as computed.
    led2 = {"p": row("KXBTC15M-26SEP190800-00", "yes", yes_n=100, yes_cost=90.0),   # +10
            "q": row("KXETH15M-26SEP190815-15", "no", yes_n=4, yes_cost=3.0)}       # -3
    b2 = build(led2, {}, 2026)
    sa2 = {(c, n): base * rate for c, _, n, rate, base in b2["set_aside"]}
    ck(near(sa2[("A", "federal 24%")], 7.0 * 0.24), "positive base A wrong")
    ck(near(sa2[("B", "federal 24%")], (10 - 2.7) * 0.24), "positive base B wrong (90% of losses)")
    ck(near(sa2[("C", "federal 24%")], 10 * 0.24), "positive base C wrong")

    # NULL WORLD: nothing on file. Must produce zeros and say so, never invent.
    b0 = build({}, {}, 2026)
    ck(b0["ytd"]["n"] == 0 and b0["ytd"]["net"] == 0.0, "null world has markets")
    ck(all(base == 0.0 for _, _, _, _, base in b0["set_aside"]), "null world has a set-aside")
    lines = []
    report(b0, out=lines.append)
    ck(any("NO SETTLED MARKETS" in s for s in lines), "null world is not flagged loudly")
    rows0 = list(csv.DictReader(io.StringIO(to_csv(b0))))
    ck(not any(r["section"] == "MARKET" for r in rows0), "null world wrote market rows")
    # A world of only 2025 must not leak into 2026.
    b25 = build({"g": led["g"]}, {}, 2026)
    ck(b25["ytd"]["n"] == 0 and b25["other_years"] == 1, "2025-only world leaked into 2026")

    if fails:
        print("SELFTEST FAIL (%d):" % len(fails))
        for f in fails:
            print("  -", f)
        return False
    print("SELFTEST PASS: planted nets, hedged/tie/month-boundary/other-year cases, "
          "transfers, set-aside bases, no id leak, and the null world all as expected")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--transfers", default=TRANSFERS)
    ap.add_argument("--outdir", default=OUTDIR)
    ap.add_argument("--check-balance", action="store_true",
                    help="GET /portfolio/balance and reconcile (read-only)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        sys.exit(1)
    led, why = pinday.load_ledger(a.ledger)
    if led is None:
        print("NO LEDGER: %s -- nothing written" % why)
        sys.exit(2)
    xfer = pinxfer.load_cache(a.transfers)
    b = build(led["rows"], xfer, a.year)
    report(b)
    print("  ledger written %s UTC; transfers fetched %s UTC"
          % (led.get("written"), xfer.get("fetched")))
    if a.check_balance:
        check_balance(b)
    os.makedirs(a.outdir, exist_ok=True)
    path = os.path.join(a.outdir, "kalshi_%d_ledger.csv" % a.year)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(to_csv(b))
    os.replace(tmp, path)
    print("  wrote %s" % path)


if __name__ == "__main__":
    main()
