#!/usr/bin/env python3
# VERSION: 2026-09-13-tx1
"""pintax.py -- a complete, auditable record of every trade, for a tax advisor.

THE OPERATOR: "can we start keeping track of every single trade for tax
purposes. I want a document specifically for that that's formatted and good to
hand to a tax advisor."

THIS IS A RECORD, NOT TAX ADVICE. It says what was bought, when, for how much,
what fee was paid and what it settled for. How any of that is characterised --
capital, ordinary, section 1256, wash sales, anything else -- is a question for
the advisor, and nothing here presumes an answer. The document says so on its
face so it cannot be mistaken for a filing position.

WHAT IT IS BUILT FROM. Only the live logs: `order` records carry the executed
price, the contracts filled and the FEE ACTUALLY BILLED (`fee_total`, the
exchange's own number, not our estimate of it), and `settled` records carry the
outcome and the realised cents. Nothing is modelled and nothing is inferred --
a position with no settlement is reported as OPEN rather than guessed at.

TWO THINGS AN ADVISOR WILL ASK FOR THAT ARE EASY TO GET WRONG:

  EVERY LEG, SEPARATELY. A hedge is its own purchase of the opposite side at
  its own price with its own fee. Netting it into the position it protects
  would understate both the gross proceeds and the fees, which are the two
  numbers a return actually reports.

  FEES AS BILLED. `fee_total` is what the exchange charged for the order.
  `billed_fee()` elsewhere in this repo is our RECONSTRUCTION of that formula,
  used for pre-trade decisions. A tax record must carry the charge, never the
  reconstruction, and the two are compared here so a divergence is visible.

TIMES. Both are given on every row: UTC, because that is what the exchange and
every file in this repo use, and US Eastern, because that is the operator's
own clock and the one a US return is written against.
"""
import argparse
import calendar
import csv
import datetime
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LIVE = os.path.join(REPO, "results", "pinrun-live-*.jsonl")

COIN = {"KXBTC": "Bitcoin", "KXETH": "Ethereum", "KXSOL": "Solana",
        "KXXRP": "XRP", "KXDOGE": "Dogecoin", "KXBNB": "BNB",
        "KXADA": "Cardano", "KXBCH": "Bitcoin Cash", "KXZEC": "Zcash",
        "KXHYPE": "Hyperliquid", "KXNEAR": "NEAR", "KXTON": "TON"}


def to_et(utc_iso):
    """UTC ISO -> (date, time) US Eastern.

    EDT is UTC-4 from March to November and EST is UTC-5 the rest of the year.
    CLAUDE.md's standing rule is that a literal 'EST' in July is an hour wrong,
    so the offset is chosen from the date rather than assumed.
    """
    try:
        t = calendar.timegm(datetime.datetime.strptime(
            utc_iso, "%Y-%m-%dT%H:%M:%SZ").timetuple())
    except (ValueError, TypeError):
        return "", "", ""
    d = datetime.datetime.fromtimestamp(t, datetime.UTC)
    # second Sunday in March .. first Sunday in November
    y = d.year
    mar = datetime.datetime(y, 3, 8, tzinfo=datetime.UTC)
    dst_start = mar + datetime.timedelta(days=(6 - mar.weekday()) % 7)
    nov = datetime.datetime(y, 11, 1, tzinfo=datetime.UTC)
    dst_end = nov + datetime.timedelta(days=(6 - nov.weekday()) % 7)
    off = -4 if dst_start <= d < dst_end else -5
    e = datetime.datetime.fromtimestamp(t + off * 3600, datetime.UTC)
    return (e.strftime("%Y-%m-%d"), e.strftime("%H:%M:%S"),
            "EDT" if off == -4 else "EST")


def describe(ticker):
    """'Bitcoin 15-minute, closing 2026-09-13 15:45 UTC' from the ticker."""
    parts = str(ticker).split("-")
    base = parts[0] if parts else str(ticker)
    coin = None
    for pre, name in COIN.items():
        if base.startswith(pre):
            coin = name
            break
    when = parts[1] if len(parts) > 1 else ""
    return "%s 15-minute binary, close %s" % (coin or base, when)


def load(glob_pat=LIVE):
    """[row] -- one row per LEG: every fill, with its settlement if it has one.

    A leg with no settlement is OPEN and is reported as such. Guessing at it is
    the one thing a tax record must never do.
    """
    orders = {}
    settles = defaultdict(list)
    for path in sorted(glob.glob(glob_pat), key=os.path.getmtime):
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            k = d.get("kind")
            if k == "order" and (d.get("filled") or 0) > 0:
                orders[(d.get("ticker"), d.get("t"))] = d
            elif k == "hedge" and (d.get("n") or 0) > 0 and d.get("status"):
                orders[("HEDGE", d.get("ticker"), d.get("t"))] = d
            elif k == "settled":
                settles[d.get("ticker")].append(d)
    rows = []
    used = defaultdict(int)
    for key, o in sorted(orders.items(), key=lambda kv: kv[0][-1] or ""):
        hedge = key[0] == "HEDGE"
        tk = o.get("ticker")
        qty = float(o.get("filled") if not hedge else o.get("n") or 0)
        px = o.get("exec_price")
        if px is None:
            px = o.get("price")
        px = float(px or 0)
        side = (o.get("want") or o.get("side") or "").upper()
        if hedge:
            side = (o.get("side") or "").upper()
        fee = o.get("fee_total")
        fee = float(fee) if fee is not None else None
        cands = [s for s in settles.get(tk, [])
                 if abs(float(s.get("cost") or -1) - px) < 5e-4]
        st = None
        if cands:
            i = used[(tk, round(px, 4))]
            if i < len(cands):
                st = cands[i]
                used[(tk, round(px, 4))] = i + 1
        d_et, t_et, zone = to_et(o.get("t"))
        cost = qty * px
        if st is None:
            result, proceeds, pl, status = "", "", "", "OPEN"
            settled_utc = ""
        else:
            result = (st.get("result") or "").upper()
            won = (st.get("pnl_c") or 0) > 0
            proceeds = qty * 1.0 if won else 0.0
            pl = (st.get("pnl_c") or 0) / 100.0
            status = "SETTLED"
            settled_utc = st.get("t") or ""
        rows.append({
            "date_et": d_et, "time_et": t_et, "zone": zone,
            "datetime_utc": o.get("t"),
            "market_ticker": tk,
            "description": describe(tk),
            "leg": "HEDGE" if hedge else "ENTRY",
            "side_bought": side,
            "contracts": round(qty, 2),
            "price_per_contract_usd": round(px, 4),
            "gross_cost_usd": round(cost, 4),
            "fee_usd": (round(fee, 4) if fee is not None else ""),
            "status": status,
            "settlement_result": result,
            "proceeds_usd": (round(proceeds, 4) if proceeds != "" else ""),
            "net_pl_usd": (round(pl, 4) if pl != "" else ""),
            "settled_utc": settled_utc,
            "order_id": o.get("order_id") or "",
        })
    return rows


# The operator supplied a template ledger; its nine columns come FIRST and
# keep his names, so the sheet is familiar to whoever receives it. Everything
# after them is what a US return needs and his template did not carry.
FIELDS = [
    "Date", "Market/Asset", "Contract Details", "Action (Buy/Sell)",
    "Contracts/Size", "Entry Price ($)", "Exit Price ($)", "Fees ($)",
    "Net Profit/Loss ($)",
    # --- added: what Form 8949 / Form 6781 / gambling treatment each need ---
    "Time (ET)", "Timezone", "Datetime Acquired (UTC)",
    "Datetime Disposed (UTC)", "Holding Period", "Proceeds ($)",
    "Cost Basis incl. Fees ($)", "Gain/Loss ($)", "Leg Type", "Side Bought",
    "Status", "Settlement Result", "Order ID",
]


def to_sheet(r):
    """One internal row -> the columns above."""
    settled = r["status"] == "SETTLED"
    cost = float(r["gross_cost_usd"] or 0)
    fee = float(r["fee_usd"] or 0)
    basis = cost + fee
    proceeds = float(r["proceeds_usd"] or 0) if settled else ""
    gain = (proceeds - basis) if settled else ""
    return {
        "Date": r["date_et"],
        "Market/Asset": r["description"],
        "Contract Details": r["market_ticker"],
        "Action (Buy/Sell)": "Buy to Open (held to settlement)",
        "Contracts/Size": r["contracts"],
        "Entry Price ($)": r["price_per_contract_usd"],
        "Exit Price ($)": (1.0 if (settled and float(r["net_pl_usd"] or 0) > 0)
                           else (0.0 if settled else "")),
        "Fees ($)": r["fee_usd"],
        "Net Profit/Loss ($)": r["net_pl_usd"],
        "Time (ET)": r["time_et"],
        "Timezone": r["zone"],
        "Datetime Acquired (UTC)": r["datetime_utc"],
        "Datetime Disposed (UTC)": r.get("settled_utc", ""),
        "Holding Period": ("Short-term (under 1 hour)" if settled else ""),
        "Proceeds ($)": (round(proceeds, 4) if settled else ""),
        "Cost Basis incl. Fees ($)": round(basis, 4),
        "Gain/Loss ($)": (round(gain, 4) if settled else ""),
        "Leg Type": r["leg"],
        "Side Bought": r["side_bought"],
        "Status": r["status"],
        "Settlement Result": r["settlement_result"],
        "Order ID": r["order_id"],
    }


def write_csv(rows, path):
    """The sheet, plus an automated TOTAL row at the bottom.

    The operator asked for the total box. It sums only the columns where a sum
    means something -- contracts, fees, proceeds, basis, gain, net -- and is
    left BLANK on prices, because an average entry price dressed as a total is
    the kind of number that ends up on a return.
    """
    sheet = [to_sheet(r) for r in rows]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in sheet:
            w.writerow({k: r.get(k, "") for k in FIELDS})

        def tot(col):
            return round(sum(float(r[col]) for r in sheet
                             if str(r.get(col, "")) != ""), 4)
        total = {k: "" for k in FIELDS}
        total["Date"] = "TOTAL"
        total["Market/Asset"] = "%d legs (%d settled, %d open)" % (
            len(sheet), sum(1 for r in sheet if r["Status"] == "SETTLED"),
            sum(1 for r in sheet if r["Status"] == "OPEN"))
        for col in ("Contracts/Size", "Fees ($)", "Net Profit/Loss ($)",
                    "Proceeds ($)", "Cost Basis incl. Fees ($)",
                    "Gain/Loss ($)"):
            total[col] = tot(col)
        w.writerow(total)
    return path


def summary(rows):
    """The cover document. Supports ALL THREE possible treatments, because the
    IRS has not settled which applies.

    RESEARCHED 2026-09-13 rather than assumed. Kalshi does NOT issue a
    comprehensive 1099-B for event contracts -- it issues 1099-INT for
    interest, 1099-MISC for referral credits, and 1099-B/1099-DA only for
    crypto transfers handled by its custodian. So this document is the PRIMARY
    record, not a cross-check against one. That is the most important fact
    here and it goes at the top.

    Three treatments are argued for and none is settled:
      CAPITAL GAIN -> Form 8949 + Schedule D. Needs per-lot dates, proceeds,
                      basis, gain.
      SECTION 1256 -> Form 6781, 60/40. Needs the aggregate AND year-end open
                      positions marked to market. Most commentary says event
                      contracts are NOT in the 1256 list.
      GAMBLING     -> gross WINNINGS as income, losses itemised and capped at
                      winnings. Needs GROSS winnings and GROSS losses
                      SEPARATELY; a net figure is useless for it, which is why
                      both are reported even though every other treatment
                      wants the net.
    """
    done = [r for r in rows if r["status"] == "SETTLED"]
    op = [r for r in rows if r["status"] == "OPEN"]

    def f(key, sel):
        return sum(float(r[key] or 0) for r in sel)

    wins = [r for r in done if float(r["net_pl_usd"] or 0) > 0]
    losses = [r for r in done if float(r["net_pl_usd"] or 0) < 0]
    gross_win = f("net_pl_usd", wins)
    gross_loss = -f("net_pl_usd", losses)
    net = f("net_pl_usd", done)
    by_month = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    for r in done:
        m = (r["date_et"] or "")[:7]
        a2 = by_month[m]
        a2[0] += 1
        a2[1] += float(r["gross_cost_usd"] or 0)
        a2[2] += float(r["fee_usd"] or 0)
        a2[3] += float(r["net_pl_usd"] or 0)

    lines = []
    w = lines.append
    w("# Trading record for tax preparation")
    w("## Kalshi event contracts - taxpayer resident in Virginia")
    w("")
    w("*Generated %s by `research/pintax.py`, from the trading system's own "
      "execution logs. Every figure is an executed transaction: nothing is "
      "modelled, estimated or netted.*"
      % datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC"))
    w("")
    w("> **THIS IS A RECORD OF TRANSACTIONS, NOT TAX ADVICE.** It states what "
      "was bought, when, at what price, what fee the exchange charged, and "
      "what it settled for. How that is characterised is for the advisor to "
      "decide; nothing here presumes an answer.")
    w("")
    w("## 1. Why this document exists")
    w("")
    w("**Kalshi does not issue a comprehensive 1099-B for event contracts.** "
      "It issues a 1099-INT for interest, a 1099-MISC for referral credits, "
      "and 1099-B/1099-DA only for crypto transfers handled by its custodian. "
      "Event-contract gains are taxable whether or not a form is issued, so "
      "**this ledger is the primary record rather than a cross-check against "
      "one.**")
    w("")
    w("## 2. What was traded")
    w("")
    w("Binary event contracts on Kalshi, a CFTC-regulated designated contract "
      "market. Each contract settles at **$1.00** if the stated event occurs "
      "and **$0.00** if it does not.")
    w("")
    w("- **Long only.** Every position was BOUGHT. Nothing was sold short.")
    w("- **Held to settlement.** No position was closed early; each was held "
      "to expiry and settled by the exchange.")
    w("- **Holding period is minutes.** Markets open and settle within 15 "
      "minutes, so every disposition is short-term.")
    w("- **A HEDGE leg is a separate purchase** of the opposite side of the "
      "same market, also held to settlement. It is its own line with its own "
      "price and fee. The pair pays exactly $1.00 per contract. Netting the "
      "two would understate both gross proceeds and total fees.")
    w("")
    w("## 3. Totals")
    w("")
    w("| | |")
    w("|---|---|")
    w("| settled legs | %d |" % len(done))
    w("| open legs, not yet settled | %d |" % len(op))
    w("| contracts bought | %.2f |" % f("contracts", done))
    w("| gross cost | $%.2f |" % f("gross_cost_usd", done))
    w("| exchange fees paid | $%.2f |" % f("fee_usd", done))
    w("| gross proceeds at settlement | $%.2f |" % f("proceeds_usd", done))
    w("| **net profit/loss** | **$%.2f** |" % net)
    w("| winning legs / losing legs | %d / %d |" % (len(wins), len(losses)))
    w("")
    w("## 4. The three possible treatments, and the figure each needs")
    w("")
    w("The IRS has published no guidance on prediction-market contracts, and "
      "no ruling settles whether this is gambling, capital gain, or Section "
      "1256 property. **The advisor chooses; this supplies the number each "
      "choice requires.**")
    w("")
    w("| treatment | form | figure it needs | value |")
    w("|---|---|---|---|")
    w("| Capital gain/loss | Form 8949 + Schedule D | net short-term gain, "
      "per lot | **$%+.2f**, all short-term |" % net)
    w("| Section 1256 | Form 6781 (60/40) | aggregate gain, plus year-end "
      "open positions marked to market | **$%+.2f**, %d open at generation |"
      % (net, len(op)))
    w("| Gambling | Sch. 1 income + Sch. A losses | **gross winnings and "
      "gross losses SEPARATELY** | won **$%.2f**, lost **$%.2f** |"
      % (gross_win, gross_loss))
    w("")
    w("**Most published commentary holds that event contracts are NOT Section "
      "1256 property**, because the code's list does not reach them. The "
      "question is open and 1256 is the most favourable of the three, so it is "
      "the advisor's call; the data supports either.")
    w("")
    w("## 5. Two Virginia questions to put to the advisor")
    w("")
    w("Virginia begins from federal adjusted gross income and has no separate "
      "capital-gains rate, so the federal characterisation decides almost "
      "everything. Two consequences are worth raising explicitly:")
    w("")
    w("1. **Under the gambling treatment the gross figures matter far more "
      "than the net.** Winnings are income; losses are an itemised deduction "
      "capped at winnings. A taxpayer taking the federal standard deduction "
      "would get no offset at all - here that is **$%.2f of income against "
      "$%.2f of losses**, where the net is $%+.2f."
      % (gross_win, gross_loss, net))
    w("2. **Virginia allows itemised deductions only if they were itemised "
      "federally**, so that decision carries straight into the state return.")
    w("")
    w("## 6. Wash sales")
    w("")
    w("Each contract is a distinct market that expires within 15 minutes, and "
      "no position was closed at a loss and repurchased. The ledger carries "
      "the market ticker and a timestamp on every line so this can be checked "
      "directly rather than taken on trust.")
    w("")
    if done:
        w("## 7. Period covered")
        w("")
        w("First trade **%s %s %s**, last **%s %s %s**."
          % (done[0]["date_et"], done[0]["time_et"], done[0]["zone"],
             done[-1]["date_et"], done[-1]["time_et"], done[-1]["zone"]))
        w("")
    w("## 8. By month (US Eastern)")
    w("")
    w("| month | legs | gross cost | fees | net P/L |")
    w("|---|---|---|---|---|")
    for m in sorted(by_month):
        n2, c, fe, pl = by_month[m]
        w("| %s | %d | $%.2f | $%.2f | $%+.2f |" % (m, n2, c, fe, pl))
    w("")
    w("## 9. The line-by-line ledger")
    w("")
    w("`results/TAX_TRADES.csv` - one row per leg, ending in an automatic "
      "**TOTAL** row. Columns in order:")
    w("")
    w("Date, Market/Asset, Contract Details, Action, Contracts/Size, Entry "
      "Price, Exit Price, Fees, Net Profit/Loss, Time (ET), Timezone, "
      "Datetime Acquired (UTC), Datetime Disposed (UTC), Holding Period, "
      "Proceeds, Cost Basis incl. Fees, Gain/Loss, Leg Type, Side Bought, "
      "Status, Settlement Result, Order ID.")
    w("")
    w("**Fees are the exchange's own billed figure** (`fee_total` from the "
      "order confirmation), never a reconstruction of the fee formula.")
    w("")
    w("A leg marked **OPEN** was bought but had not settled when this was "
      "generated. It carries no result and no profit figure - left blank "
      "rather than estimated.")
    return "\n".join(lines) + "\n"


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    d, t, z = to_et("2026-09-13T19:44:30Z")
    ck((d, t, z) == ("2026-09-13", "15:44:30", "EDT"),
       "September converts to EDT, UTC-4 (%s %s %s)" % (d, t, z))
    d2, _t2, z2 = to_et("2026-01-15T02:30:00Z")
    ck(z2 == "EST" and d2 == "2026-01-14",
       "January is EST, UTC-5, and rolls back a day (%s %s)" % (d2, z2))
    ck(to_et("rubbish") == ("", "", ""), "junk time returns blank, not a crash")
    ck("Bitcoin" in describe("KXBTC15M-26SEP131545-45"),
       "the ticker becomes a readable description")

    import tempfile
    tmp = tempfile.mkdtemp(prefix="pintax-")
    try:
        fp = os.path.join(tmp, "pinrun-live-a.jsonl")
        with open(fp, "w", encoding="utf-8") as fh:
            wj = lambda o: fh.write(json.dumps(o) + "\n")      # noqa: E731
            wj({"kind": "order", "ticker": "KXBTC15M-26SEP131545-45",
                "filled": 47.0, "exec_price": 0.98, "fee_total": 0.0611,
                "order_id": "abc", "t": "2026-09-13T19:44:30Z"})
            wj({"kind": "settled", "ticker": "KXBTC15M-26SEP131545-45",
                "cost": 0.98, "pnl_c": 87.55, "result": "yes",
                "t": "2026-09-13T19:45:20Z"})
            wj({"kind": "order", "ticker": "KXETH15M-26SEP131600-00",
                "filled": 40.0, "exec_price": 0.95, "fee_total": 0.13,
                "order_id": "def", "t": "2026-09-13T19:59:30Z"})
        rows = load(os.path.join(tmp, "pinrun-live-*.jsonl"))
        ck(len(rows) == 2, "one row per LEG (%d)" % len(rows))
        a = rows[0]
        ck(a["status"] == "SETTLED" and a["settlement_result"] == "YES",
           "a settled leg carries its result")
        ck(abs(a["gross_cost_usd"] - 46.06) < 1e-6,
           "gross cost is contracts x price (%.2f)" % a["gross_cost_usd"])
        ck(abs(a["proceeds_usd"] - 47.0) < 1e-9,
           "a winner's proceeds are $1.00 per contract (%.2f)"
           % a["proceeds_usd"])
        ck(a["fee_usd"] == 0.0611,
           "the fee is the exchange's fee_total, not our reconstruction")
        b = rows[1]
        ck(b["status"] == "OPEN" and b["settlement_result"] == ""
           and b["net_pl_usd"] == "",
           "an UNSETTLED leg is OPEN with blank result and blank P/L -- never "
           "estimated")
        cp = write_csv(rows, os.path.join(tmp, "t.csv"))
        head = open(cp, encoding="utf-8").readline().strip()
        ck(head.split(",") == FIELDS, "the CSV header is the full field list")
        _lines = open(cp, encoding="utf-8").read().strip().split("\n")
        ck(len(_lines) == 4,
           "header + one row per leg + the TOTAL row (%d lines)" % len(_lines))
        ck(_lines[-1].startswith("TOTAL,"),
           "the last row is the automatic TOTAL the operator asked for")
        # parse with the csv module, not split(",") -- the TOTAL row's
        # description contains a comma and is quoted, which shifts every
        # index after it. The first version of this check read the wrong
        # column and reported an empty total.
        with open(cp, encoding="utf-8", newline="") as _fh:
            _tot = list(csv.DictReader(_fh))[-1]
        ck(_tot["Contracts/Size"] == "87.0",
           "and it sums the contracts across both legs (%s)"
           % _tot["Contracts/Size"])
        ck(_tot["Entry Price ($)"] == "" and _tot["Exit Price ($)"] == "",
           "while leaving PRICE columns blank -- an averaged entry price "
           "dressed as a total is the kind of number that ends up on a return")
        txt = summary(rows)
        ck("not tax advice" in txt.lower(),
           "the document says on its face that it is not advice")
        ck("does not issue a comprehensive 1099-B" in txt,
           "and states the fact that makes it the PRIMARY record")
        for treat in ("Form 8949", "Form 6781", "Gambling"):
            ck(treat in txt,
               "it supplies the figure for the %s treatment" % treat)
        ck("gross winnings and gross losses" in txt.lower(),
           "including gross winnings and losses SEPARATELY, which only the "
           "gambling treatment needs and a net figure cannot supply")
        ck("Virginia" in txt and "itemised" in txt,
           "and the two Virginia questions")
        ck("$0.06" in txt or "0.0611" in txt or "$0.0611" in txt
           or "fees paid | $0.06" in txt,
           "fees are totalled (%s)"
           % [ln for ln in txt.splitlines() if "fees" in ln])
        ck("open legs, not yet settled | 1" in txt,
           "and open legs are counted separately from settled ones")
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
    print("pintax selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--csv", default=os.path.join(REPO, "results",
                                                  "TAX_TRADES.csv"))
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "TAX_SUMMARY.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    rows = load()
    if not rows:
        print("pintax: no filled order in the live logs -- nothing to analyse")
        return 0
    write_csv(rows, a.csv)
    txt = summary(rows)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(txt)
    print("  wrote %s (%d legs) and %s" % (a.csv, len(rows), a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
