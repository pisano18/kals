"""legacy_selftest.py -- pinphone.py's own self-test (2,400 lines of checks written with the code since 09-17), kept as
it was and run against the rebuilt phone (v-tg-rebuild step 11, 2026-10-30).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\legacy_selftest.py   (exit 0 = every check passed; also stage 1 of
      `pinphone.py --selftest`)

The checks were written inside pinphone.py and read its module globals by name, patch them through globals() (LOG,
BOOT_ALL, LADDER_PY, UPDATE_FLAG), and talk to a Phone. After the split those globals live in research/phone/shared.py
and the Phone in research/phone/app.py, so run() executes selftest() WITH phone.shared's namespace AS ITS GLOBALS (the
very dict the helpers read: a globals()["LOG"] patch is a patch of phone.shared.LOG), lending it the runtime's names
(Phone, Ctx, the router) for the run only. selftest() is never called any other way; its names resolve only there.
Step 10 already moved its routing checks from the deleted Phone.text_* methods to the router (ph.handle) or to a command
module run as the old method ran (_cmdrun); step 13 splits it into per-module tests.
"""
import os
import sys
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)


# noqa: the names below resolve in phone.shared's namespace (see run())
def selftest():
    import tempfile
    import calendar
    # v-tg-rebuild step 2 (2026-10-30): a self-test never writes a LIVE file -- botdata/paths.py's fence refuses any
    # write under the real results\ or C:\kals while KALS_TESTING=1 (before this the pinphone self-test appended its
    # fake sends to the real results\pinphone.log)
    os.environ["KALS_TESTING"] = "1"

    def ck(cond, msg):
        cprint(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinphone selftest: FAILED -- " + msg)

    def P(x):
        """What the phone shows: an Html reply without its tags; a plain reply as it is."""
        return html_to_plain(x) if getattr(x, "is_html", False) else ("" if x is None else str(x))

    def _cmdrun(ph, text):
        """One command module's reply to `text` on phone `ph`, as the old Phone.text_* method gave it (no ledger refresh,
        no paused-bot check: the router's steps are left out) -- v-tg-rebuild step 10."""
        from phone import command as _pcm0
        c = ph.ctx(text)
        return _pcm0.by_name(c.cmd).run(c)

    def fits(x):
        """Every message the transport would send for this reply is under Telegram's limit, and each
        one's tags are balanced (no tag left open across a cut)."""
        parts = split_html(x) if getattr(x, "is_html", False) else split_text(x)
        return all(len(c) <= MAX_LEN and not _open_after([], c) for c in parts)

    # ---- the presentation layer (2026-10-18) -------------------------------------------------------
    ck(esc("a<b & c>d") == "a&lt;b &amp; c&gt;d" and html_to_plain(Html("<b>x &lt; y &amp; z</b>")) == "x < y & z",
       "esc() escapes & < >; html_to_plain() gives back what the phone shows")
    ck(norm_money("Made $+1008.55, worst $-131.98, fees $248.98, $83,156 risked, per $100") ==
       "Made +$1,008.55, worst -$131.98, fees $248.98, $83,156 risked, per $100"
       and norm_money("stake $N + $N would pass the $N cap") == "stake $N + $N would pass the $N cap",
       "norm_money: one money style ('+$1,008.55'), the digits untouched, non-money '$N' left alone")
    ck(usd(1008.554) == "+$1,008.55" and usd(-4.57) == "-$4.57" and usd(0.004) == "$0.00" and usd(None) == "?"
       and dollars(1294.5) == "$1,294.50", "usd / dollars: sign first, thousands separators")
    ck(table([("Day", "Money", "Lost"), ("10-18", "+$7.10", "0/8"), ("10-17", "+$90.46", "0/34"),
              ("x", "nothing settled")]) ==
       ["Day     Money Lost", "10-18  +$7.10  0/8", "10-17 +$90.46 0/34", "x     nothing settled"],
       "table(): the first column left, numbers right-aligned; a short row spans and does not widen columns")
    ck(ret(7.10, 262.73, 2) == "+2.70%" and ret(-0.91, 3.907) == "-23.3%" and ret(1.0, 0) == "" and ret(None, 5) == ""
       and pct1(8, 8) == "100%" and pct1(0, 3) == "0%" and pct1(87, 88) == "98.9%" and pct1(1, 0) == "-",
       "ret(): money on what bought it, signed, '' with no base; pct1(): one decimal, '100%' / '0%' kept narrow")
    ck(tg_html_problems("<b>a</b> <i>b &amp; c &lt;</i> <pre>x\ny</pre> <blockquote expandable><b>t</b>\nz"
                        "</blockquote> <code>c</code>") == []
       and tg_html_problems("a < b") and tg_html_problems("<blockquote><pre>x</pre></blockquote>")
       and tg_html_problems("<b><code>x</code></b>") and tg_html_problems("<b>open") and tg_html_problems("<p>x</p>")
       and tg_html_problems("&nbsp;") and tg_html_problems("<b>x</i>"),
       "tg_html_problems(): Telegram's rules -- a raw <, pre/code inside a quote or a bold, an unclosed or "
       "unknown tag, an unknown entity, a tag closed out of order")
    # ---- the 30-day average day (2026-10-29), beside the 7-day one, which must not move -----------------------------
    _bsx = _bs()
    _td = "2026-10-29"
    _d7 = [{"day": _bsx.shift_day(_td, -k), "money": 9.0 if k == 0 else 1.0, "pot_pct": p_, "before_first": False}
           for k, p_ in enumerate((9.0, 1.0, 2.0, 0.0, 1.5, 0.5, 1.0))]
    _d30 = [{"day": _bsx.shift_day(_td, -k), "markets": 1, "money": 5.0 if k <= 10 else 2.0,
             "pot_pct": 2.5 if k <= 10 else 1.0, "before_first": False} for k in range(1, 31)]
    _m30 = {"days_7": _d7, "days_30": _d30}
    ck(bs_avg_day_line(_m30) == "📈 <b>Average day, last 6 full days: +1.0% of its bank</b>"
       and bs_avg_day_line(_m30, 1.0) == ("📈 <b>Average day, last 6 full days: +1.0% of its bank</b> (goal 1.0%) · "
                                          "4 of 6 days at 1.0%+"),
       "the 7-day line is unchanged by the 30-day one: today left out, 6 full days, mean of each day's %% (%s)"
       % bs_avg_day_line(_m30))
    _a30 = _bsx.avg_day(_d30)
    ck(_a30 == {"days": 30, "money": 3.0, "pot_pct": 1.5, "pct_days": 30, "first": "2026-09-29", "young": False}
       and bs_avg30_line(_m30) == "📈 <b>Average day, last 30 full days: +1.5% of its bank</b> (+$3.00 a day)"
       and bs_avg30_line(_m30, 1.0).endswith(" · 30 of 30 days at 1.0%+"),
       "the 30-day line: the 30 full days before today, $ a day = (10 x 5 + 20 x 2) / 30, %% = the mean of each "
       "day's %% of its bank (10 x 2.5 + 20 x 1.0) / 30; the ladder's goal count over the same days: %s"
       % bs_avg30_line(_m30, 1.0))
    _young = [dict(d, before_first=k >= 4, markets=0 if k >= 4 else 1, money=0.0 if k >= 4 else d["money"])
              for k, d in enumerate(_d30)]
    _young[2] = dict(_young[2], markets=0, money=0.0, pot_pct=0.0)                 # a quiet day after its first: $0, 0%
    _young[3] = dict(_young[3], pot_pct=None)                                      # its first day's bank unknown
    _ay = _bsx.avg_day(_young)
    ck(_ay["days"] == 4 and _ay["young"] and _ay["first"] == "2026-10-25" and abs(_ay["money"] - 15.0 / 4) < 1e-9
       and abs(_ay["pot_pct"] - 5.0 / 3) < 1e-3 and _ay["pct_days"] == 3
       and bs_avg30_line({"days_30": _young}) == ("📈 <b>Average day, since Oct 25, 4 days: +1.7% of its bank</b> "
                                                  "(+$3.75 a day) · % over the 3 days its bank is known"),
       "a bot younger than 30 days (first market Oct 25): every day it has, labelled 'since Oct 25, 4 days'; a quiet "
       "day after its first counts $0 and 0%%; a day whose bank is unknown leaves only the %% mean: %s"
       % bs_avg30_line({"days_30": _young}))
    ck(_bsx.avg_day([dict(d, before_first=True) for d in _d30]) is None and bs_avg30_line({"days_30": []}) is None,
       "no day on its books in the 30 -> no 30-day line")
    _run = {"alive": True, "stop_flag": False}
    _opn = {"ok": True, "count": 0}
    _aa = {"bots": {b_: {"running": _run, "open": _opn, "money": {"ok": True, "days_30": _young if b_ == "fx" else _d30,
                                                                    "last_7_days": {"markets": 1}}}
                    for b_ in _bsx.BOTS},
           "other": {"ok": True, "days_30": [dict(d, markets=0, money=0.0) for d in _d30]},
           "total_days_30": _d30}
    _tb = bots_avg_table(_aa)
    _tl = html_to_plain(Html("\n".join(_tb))).split("\n")
    ck(_tl[1] == "📈 Average day, last 30 full days" and _tl[2].split() == ["Bot", "a", "day", "of", "bank", "Days"]
       and _tl[3].split() == ["pin", "+$3.00", "+1.5%", "30"] and _tl[-2].split() == ["ALL", "+$3.00", "+1.5%", "30"]
       and any(x_.split() == ["fx", "+$3.75", "+1.7%", "4*"] for x_ in _tl) and not any(x_.startswith("other") for x_ in _tl)
       and "* every day it has: fx since Oct 25" in _tl[-1] and max(len(x_) for x_ in _tl[2:-1]) <= 40
       and not tg_html_problems(Html("\n".join(_tb))),
       "/days and /bots: the 30-day table, a row a bot and ALL, the young FX taker starred with its first day, "
       "'other' with nothing in the 30 days left out, <= 40 characters wide, Telegram-valid")
    # log() NEVER RAISES: boot_all redirects stdout to a file, which on this box is cp1252 and cannot hold an
    # emoji. Before 2026-10-18 the raise came out of say() after the send and out of poll_once() before
    # Telegram heard the update was handled -- the process died and its restart answered the command again.
    import io as _io
    _so, _lg0 = sys.stdout, globals()["LOG"]
    with tempfile.TemporaryDirectory() as _tdl:
        globals()["LOG"] = os.path.join(_tdl, "x.log")
        sys.stdout = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252", errors="strict")
        try:
            log("SENT: 🟢 Today +$7.10 · ▁▂█ → ok")
            _raised = None
        except Exception as e:                                  # noqa: BLE001
            _raised = e
        finally:
            sys.stdout.flush()
            _con = sys.stdout.buffer.getvalue().decode("cp1252")
            sys.stdout = _so
        with open(globals()["LOG"], encoding="utf-8") as _fh:
            _filed = _fh.read()
        globals()["LOG"] = _lg0
    ck(_raised is None and "\\U0001f7e2 Today +$7.10" in _con and "🟢 Today +$7.10 · ▁▂█ → ok" in _filed,
       "log(): a cp1252 console cannot print an emoji -- the console copy falls back to escapes, the utf-8 log "
       "keeps the real line, and nothing raises (raised: %r)" % (_raised,))
    ck(hbar(10, 10, 5) == "█████" and hbar(5, 10, 5) == "██▌" and hbar(-3, 10, 5) == "░░" and hbar(0, 10) == ""
       and hbar(0.01, 1000, 5) == "▏" and spark([1, 2, 3]) == "▁▅█",
       "text charts: full blocks and eighths, light shade for a loss, a sliver for a tiny gain")
    _big = Html("<b>Head</b>\n\n" + "\n".join("line %d %s" % (k, "x" * 60) for k in range(40)) + "\n<pre>"
                + "\n".join("row %d %s" % (k, "y" * 50) for k in range(80)) + "</pre>\n"
                + details([esc("detail %d %s" % (k, "z" * 70)) for k in range(30)]))
    _parts = split_html(_big, 1500)
    ck(len(_parts) > 3 and all(len(c) <= 1500 and not _open_after([], c) for c in _parts)
       and html_to_plain("\n".join(_parts)).replace("\n", "") == html_to_plain(_big).replace("\n", ""),
       "split_html: every message under the limit, every tag closed in the message that opened it and opened "
       "again in the next, nothing lost (%d parts)" % len(_parts))
    ck(split_html(Html("short")) == ["short"], "split_html: a short reply is one message, untouched")
    _sent = []

    def _fake_call(method, params, http_timeout=45):
        _sent.append(dict(params))
    _tr = Telegram("tok")
    _tr._call = _fake_call
    _tr.send(1, Html("<b>hi</b>"))
    _tr.send(1, "plain <b>as before</b>")
    ck(_sent[0].get("parse_mode") == "HTML" and _sent[0]["text"] == "<b>hi</b>"
       and "parse_mode" not in _sent[1] and _sent[1]["text"] == "plain <b>as before</b>",
       "the transport: an Html reply goes with parse_mode=HTML; a plain str goes exactly as it always did")
    _sent[:] = []

    def _refuse_html(method, params, http_timeout=45):
        if params.get("parse_mode"):
            raise urllib.error.HTTPError("x", 400, "Bad Request: can't parse entities", None, None)
        _sent.append(dict(params))
    _tr._call = _refuse_html
    _st_log0 = globals()["LOG"]
    with tempfile.TemporaryDirectory() as _tdl:
        globals()["LOG"] = os.path.join(_tdl, "x.log")
        _tr.send(1, Html("<b>LOSS -$4.57</b> x &lt; y"))
        globals()["LOG"] = _st_log0
    ck(_sent == [{"chat_id": 1, "text": "LOSS -$4.57 x < y"}],
       "...and if Telegram refuses the markup (HTTP 400) the same words go again as plain text -- never lost")
    with tempfile.TemporaryDirectory() as _tdl:
        globals()["LOG"] = os.path.join(_tdl, "x.log")
        _fp = fmt_or_plain(lambda: 1 / 0, lambda: "plain words")
        _fp2 = fmt_or_plain(lambda: Html("<b>laid out</b>"), lambda: "plain words")
        globals()["LOG"] = _st_log0
    ck(_fp == "plain words" and getattr(_fp2, "is_html", False) and _fp2 == "<b>laid out</b>",
       "fmt_or_plain: an alert whose layout fails goes out in its plain words; one that lays out goes as Html")

    _st_log = LOG
    with tempfile.TemporaryDirectory() as td:
        # every log() line the self-test causes (each "sent" reply) goes to this temp folder: the live phone
        # bot appends to results/pinphone.log, and a self-test's fake replies there would read as sent
        globals()["LOG"] = os.path.join(td, "pinphone.log")
        p = os.path.join(td, "pinrun-live-20260916T135734Z.jsonl")
        c1, c2 = "KXBNB15M-26SEP161000-00", "KXBTC15M-26SEP161015-15"
        rows = [
            {"kind": "start", "t": "2026-09-16T13:00:00Z", "size": 20, "hedge_belief": 0.6},
            {"kind": "autosize", "t": "2026-09-16T13:00:01Z", "old": 20, "new": 85, "why": "bank $500.00"},
            {"kind": "signal", "t": "2026-09-16T13:59:30Z", "ticker": c1, "want": "no", "price": 0.98, "edge_c": 1.5, "size": 85, "take_n": 85, "tau": 29, "fair": 0.004, "spot": 700.1, "strike": 700.2, "digits": 2},
            {"kind": "order", "t": "2026-09-16T13:59:31Z", "ticker": c1, "filled": 85.0, "exec_price": 0.979, "status": "executed", "body": {"count": "85.00"}},
            {"kind": "settled", "t": "2026-09-16T14:00:20Z", "ticker": c1, "want": "no", "result": "no", "cost": 0.979, "pnl_c": 166.26, "realised": 1.6626},
            {"kind": "close_summary", "t": "2026-09-16T14:00:05Z", "close": calendar.timegm((2026, 9, 16, 14, 0, 0)), "looks": 1000, "no_offer": 600, "tradeable": 100, "fired": True, "gates": {}},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        L = Ledger(results=td)
        L.refresh()
        # PIN THE DEPOSITS. deposited() reads the REAL account's deposit
        # records (pinxfer), so this fixture's "+0.33% of $500" read +0.28%
        # the day real deposits reached $584.46 -- the self-test was failing
        # on the operator's money, not on the code.
        L.deposited = lambda: 500.0
        state = {"h": {"pid": 4242, "alive": True, "flag": None, "quiet_s": 12, "watchdog_s": 5, "open": {},
                       "halt": None, "kalshi_ok": True, "feeds_ok": True, "disk_gb": 30.0}}
        now = {"t": calendar.timegm((2026, 9, 16, 15, 0, 0))}           # 11 AM ET Sep 16
        tg = FakeTelegram()
        cfgp = os.path.join(td, "telegram.json")
        ph = Phone({"token": "x", "secret": "open sesame"}, tg, ledger=L, health_fn=lambda: state["h"],
                   cfg_path=cfgp, now_fn=lambda: now["t"])
        ck(ph.bs_getter is None and ph.bs_procs is None,
           "by default /bots /pin /fc /ladder read Kalshi through botstats' own getter (kauth.get, GET only)")

        # ---- the botstats sandbox ------------------------------------------
        # /race (below) and /bots /pin /forecaster /ladder read Kalshi through
        # botstats. A self-test must never reach the real Kalshi nor write the
        # real cache, so botstats' results folder moves into this temp dir and
        # the phone gets a fake Kalshi and a process table. Every number the
        # checks expect was worked by hand from the rows planted here; the
        # phone's clock is 11:00 AM ET, Wed Sep 16.
        import botstats as _bsm
        _bs_saved = (_bsm.RESULTS, dict(_bsm._MEMO), dict(_bsm._BACK))

        def _bs_sandbox(name):
            d = os.path.join(td, name)
            os.makedirs(d)
            _bsm.RESULTS = d
            _bsm._MEMO.update(key=None, data=None)
            _bsm._BACK.clear()
            return d

        def _S(tk, st, res, yn=0.0, yc=0.0, nn=0.0, nc=0.0, fee=0.0):
            return {"ticker": tk, "settled_time": st, "market_result": res, "value": {"yes": 100, "no": 0}[res],
                    "yes_count_fp": "%.2f" % yn, "yes_total_cost_dollars": "%.6f" % yc,
                    "no_count_fp": "%.2f" % nn, "no_total_cost_dollars": "%.6f" % nc,
                    "fee_cost": "%.6f" % fee, "revenue": 0}
        _bs_world = {
            "0": [_S("KXBTC15M-26SEP161030-30", "2026-09-16T14:30:05Z", "no", nn=50, nc=49.00, fee=0.10),     # pin +0.90
                  _S("KXETH15M-26SEP160945-45", "2026-09-16T13:45:05Z", "yes", yn=40, yc=38.80, nn=40, nc=12.00,
                     fee=0.50),                                     # pin, both sides: 40 - 50.80 - 0.50 = -11.30
                  _S("KXSOL15M-26SEP152345-45", "2026-09-16T03:45:05Z", "yes", yn=30, yc=29.40, fee=0.06),    # pin +0.54, Sep 15
                  _S("KXCRYPTOLEAD15M-26SEP161015-XRP", "2026-09-16T14:16:00Z", "yes", yn=20, yc=19.60, fee=0.03),  # race +0.37
                  _S("KXWTI15M-26SEP151400-00", "2026-09-15T18:00:05Z", "no", yn=5, yc=4.50, fee=0.01)],     # other -4.51
            "1": [_S("KXNEAR15M-26SEP161030-30", "2026-09-16T14:30:05Z", "yes", yn=2, yc=1.958)],             # ladder +0.042
            "2": [_S("KXETH15M-26SEP161000-00", "2026-09-16T14:00:06Z", "no", yn=5, yc=2.45, fee=0.09),       # fc -2.54
                  _S("KXXRP15M-26SEP152300-00", "2026-09-16T03:00:06Z", "yes", yn=3, yc=2.42, fee=0.0328)]}   # fc +0.5472, Sep 15
        _bs_pos = {"0": [{"ticker": "KXBTC15M-26SEP161115-15", "position_fp": "-30.00", "market_exposure_dollars": "29.10"},
                         {"ticker": "KXCRYPTOLEAD15M-26SEP161100-SOL", "position_fp": "20.00",
                          "market_exposure_dollars": "19.60"}]}
        _bs_bal = {"0": "1000.0000", "1": "15.1000", "2": "24.0000"}
        _bs_mode = {"m": "planted"}
        _bs_asked = []

        # The account's books (2026-10-02, the pot percentages). Planted so every pot RECONCILES: cash +
        # open bets = money put in + every settled market (main 1048.70 = 1062.70 - 14.00; ladder 15.10 =
        # 15.06 + 0.042; forecaster 24.00 = 25.99 - 1.9928), so no pot-check warning is due.
        def _T(s):
            return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
        _bs_books = {
            "transfers": [{"amount_cents": 2000, "created_ts": _T("2026-09-14T12:00:00Z"), "from_subaccount": 0,
                           "to_subaccount": 2},                                   # $20 main -> forecaster
                          {"amount_cents": 200, "created_ts": _T("2026-09-15T20:00:00Z"), "from_subaccount": 2,
                           "to_subaccount": 0},                                   # $2 back, 4 PM ET Sep 15
                          {"amount_cents": 1506, "created_ts": _T("2026-09-16T13:00:00Z"), "from_subaccount": 0,
                           "to_subaccount": 1},                                   # $15.06 -> ladder, 9 AM today
                          {"amount_cents": 799, "created_ts": _T("2026-09-16T13:30:00Z"), "from_subaccount": 0,
                           "to_subaccount": 2}],                                  # $7.99 -> forecaster today
            "deposits": [{"amount_cents": 100575, "fee_cents": 0, "status": "applied",
                          "finalized_ts": _T("2026-09-01T12:00:00Z")},
                         {"amount_cents": 10000, "fee_cents": 200, "status": "applied",   # $98 after the fee,
                          "finalized_ts": _T("2026-09-15T14:00:00Z")}],                   # 10 AM ET yesterday
            "withdrawals": [],
            # as Kalshi lists it since 2026-10-04: subaccounts 1 and 2 also hold an empty pool-0 row, and
            # subaccount 3 (the weather dip-seller) lives in pool 0 -- empty in this world
            "subaccount_balances": [{"subaccount_number": 0, "exchange_index": 0, "balance": "0.0000"},
                                    {"subaccount_number": 0, "exchange_index": 2, "balance": "1000.0000"},
                                    {"subaccount_number": 1, "exchange_index": 0, "balance": "0.0000"},
                                    {"subaccount_number": 1, "exchange_index": 2, "balance": "15.1000"},
                                    {"subaccount_number": 2, "exchange_index": 0, "balance": "0.0000"},
                                    {"subaccount_number": 2, "exchange_index": 2, "balance": "24.0000"},
                                    {"subaccount_number": 5, "exchange_index": 2, "balance": "0.0000"},   # the FX taker's pot (2026-10-25), empty here
                                    {"subaccount_number": 4, "exchange_index": 0, "balance": "0.0000"},   # its currency pot (pool 0, 10-25), empty here
                                    {"subaccount_number": 3, "exchange_index": 2, "balance": "0.0000"},   # the jump band's pool (10-30), empty here
                                    {"subaccount_number": 3, "exchange_index": 0, "balance": "0.0000"}]}
        # the WEATHER world (2026-10-04): $50 moved main -> subaccount 3 in POOL 0 at 3 AM ET Sep 15; one Sep 15
        # bracket settled (NY: sold YES at 40c x2, NO won, +0.80) and one is open (MIA NO x2, $1.10). Cash in
        # pool 0 = 50 + 0.80 - 1.10 = 49.70; the pot held $0 at midnight Sep 15 + the $50 moved in = $50.
        _wx_books = dict(_bs_books)
        _wx_books["transfers"] = _bs_books["transfers"] + [
            {"amount_cents": 5000, "created_ts": _T("2026-09-15T07:00:00Z"), "from_subaccount": 0, "to_subaccount": 3,
             "exchange_index": 0}]
        _wx_books["subaccount_balances"] = _bs_books["subaccount_balances"][:-1] + [
            {"subaccount_number": 3, "exchange_index": 0, "balance": "49.7000"}]

        def _bs_fake(path, q):
            _bs_asked.append((path, dict(q or {})))
            if _bs_mode["m"] == "down":
                return 401, {"error": "unauthorized"}
            wx = _bs_mode["m"] == "weather"
            for _lp, _lk, _pg in _bsm.LEDGERS:
                if path == _lp:
                    if _bs_mode["m"] == "noledger":
                        return 404, {}
                    return 200, {_lk: [] if _bs_mode["m"] == "empty" else (_wx_books if wx else _bs_books)[_lk],
                                 "cursor": ""}
            sub, empty = str((q or {}).get("subaccount")), _bs_mode["m"] == "empty"
            if wx and sub == "3":
                if path == "/portfolio/settlements":
                    return 200, {"settlements": [_S("KXHIGHNY-26SEP15-B72.5", "2026-09-16T14:00:05Z", "no", nn=2,
                                                    nc=1.20)], "cursor": ""}
                if path == "/portfolio/positions":
                    return 200, {"market_positions": [{"ticker": "KXHIGHMIA-26SEP16-B90.5", "position_fp": "-2.00",
                                                       "market_exposure_dollars": "1.10"}], "cursor": ""}
            if path == "/portfolio/settlements":
                return 200, {"settlements": [] if empty else _bs_world.get(sub, []), "cursor": ""}
            if path == "/portfolio/positions":
                return 200, {"market_positions": [] if empty else _bs_pos.get(sub, []), "cursor": ""}
            if path == "/portfolio/balance":
                # Kalshi answers for the NAMED pool only: each pot's trading pool as botstats has it (SUB_POOL: pot 3 is
                # pool 2 since the jump band, 10-30; the weather world below runs on its old pool 0)
                if (q or {}).get("exchange_index") != _bsm.SUB_POOL.get(sub, 2):
                    return 200, {"balance": 0, "balance_dollars": "0.0000"}
                if wx and sub == "3":
                    return 200, {"balance": 0, "balance_dollars": "49.7000"}
                return 200, {"balance": 0, "balance_dollars": "0.0000" if empty else _bs_bal.get(sub, "0")}
            return 404, {}
        _bs_procs = [
            (3882400, "2026-09-16T11:59:50Z", r"C:\Python314\python.exe -u C:\kals-repo\research\pinrun.py --live "
                                              r"--size 20 --max-losses 2"),
            (3739628, "2026-09-16T02:49:58Z", "python -u research/pinracearm.py --live --max-contracts 20 --max-stake 60 "
                                              "--live-tau-max 30 --live-min-price 0.90 --live-max-legs 5"),
            (2574672, "2026-09-15T05:56:08Z", "python -u research/pinracearm.py --paper-live --live-tau-max 60"),
            (4196192, "2026-09-16T12:34:56Z", r"python -u research\cleanroom\forecaster_live.py --subaccount 2 --live "
                                              r"--variant race1_98")]
        _bsdir = _bs_sandbox("botstats-planted")
        with open(os.path.join(_bsdir, "VERSIONS.md"), "w", encoding="utf-8") as _fh:
            _fh.write("# Versions\n\n"
                      "# v-ladder-settlefix -- LIVE 2026-09-16 13:16:12Z (pid 5; research/cleanroom/ladder_live.py): "
                      "the penny ladder waits for yes/no\n"
                      "# v-keepalive-cleanroom -- 2026-09-16 12:37Z (boot_all.ps1): the clean-room bots restart "
                      "themselves -- LIVE forecaster_live and ladder_live\n"
                      "# v-forecaster-race1 -- LIVE 2026-09-16 12:35:02Z (pid 4196192): race1_98\n"
                      "# v-reopen98 + v-floor90 -- 2026-09-16 12:00:17Z (pid 3882400; no code change) -- LIVE: 98c\n"
                      "# v-race20 -- 2026-09-16 02:50Z (pid 3739628; pinracearm.py) -- LIVE: coin race penny bot 20\n")
        with open(os.path.join(_bsdir, "forecaster-live-orders.jsonl"), "w", encoding="utf-8") as _fh:
            for _r in ({"t": "2026-09-16T12:35:02.502Z", "ev": "start", "pid": 4196192, "live": True,
                        "variant": "race1_98", "rails": {"scale": "0.05", "per_side": 5, "per_close": 20,
                                                         "max_commit": 22.0, "px": [0.75, 0.985],
                                                         "day_stop": -12.0, "run_stop": -20.0}},
                       {"t": "2026-09-16T13:59:30.000Z", "ev": "placed", "filled": 5.0},
                       {"t": "2026-09-16T13:59:30.100Z", "ev": "live_fill", "n": 5, "ticker": "KXETH15M-26SEP161000-00",
                        "side": "yes", "px": 0.49},
                       {"t": "2026-09-16T13:59:41.000Z", "ev": "refused", "why": "in_flight"}):
                _fh.write(json.dumps(_r) + "\n")
        os.utime(os.path.join(_bsdir, "forecaster-live-orders.jsonl"), (now["t"] - 30, now["t"] - 30))
        with open(os.path.join(_bsdir, "ladder-live.stop"), "w", encoding="utf-8") as _fh:
            _fh.write("stood down by the operator")
        ph.bs_getter, ph.bs_procs = _bs_fake, _bs_procs

        # Plant a Kalshi ledger for the fixture: money comes from Kalshi now,
        # so a test that wants a TODAY figure has to provide Kalshi's books.
        import pinledger as _pl
        _pl_sv = _pl.LEDGER
        _pl.LEDGER = os.path.join(td, "kalshi_ledger.json")
        with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
            json.dump({"settlements": {"k1": {
                "ticker": c1, "market_result": "no",
                "no_count_fp": "85.00", "no_total_cost_dollars": "83.30",
                "yes_count_fp": "0.00", "yes_total_cost_dollars": "0.00",
                "revenue": 8500, "fee_cost": "0.0374",
                "settled_time": "2026-09-16T14:00:20Z"}}}, _fh)
        ck(ph.handle(111, "/status") is None, "before pairing, every message is ignored")
        ck(ph.handle(111, "/pair wrong words") is None and ph.chat_id is None, "a wrong secret is refused silently")
        r = ph.handle(111, "/pair open sesame")
        ck(r and P(r).startswith("Paired") and ph.chat_id == 111 and "Commands" in P(r),
           "the right secret pairs the chat, and the reply carries the help")
        ck(json.load(open(cfgp))["chat_id"] == 111, "...and the chat id is saved to the config file")
        ck(ph.handle(222, "/status") is None, "another chat is still ignored after pairing")
        s = ph.handle(111, "/status")
        ck("TRADING" in P(s) and "Checked just now" in P(s) and "process 4242 is OPEN" in P(s),
           "/status carries the state and its evidence")
        ck(P(s).split("\n")[0].startswith("🟢 TRADING"), "/status: the state is the headline")
        # MONEY COMES FROM KALSHI NOW, not from the log this test plants, so
        # "today" is legitimately empty here. The bank still comes from the
        # bot's own autosize record, which is ours to read.
        ck("Main account $500.00 (pin bot + coin race)" in P(s) and "Pin + race today " in P(s)
           and "💼 All pots $1,039.10" in P(s) and "+19." not in P(s),
           "/status carries the main account's bank (no % against every pot's money -- 10-26), every pot's cash and "
           "the main account's Today line, named as such")
        t = ph.handle(111, "/today")
        _tl = P(t).split("\n")
        # 2026-10-23 (operator: "/today doesn't show the right total it says 11.22 right now it's really 24.85"): the
        # headline is EVERY bot's money (botstats.all_bots, the /bots number); the main account follows, as before
        # 2026-10-26 ("/yesterday doesn't look good or show % of bank return"): a bot-by-bot table with each bot's
        # % of its own bank, its return on the bets and its losers; the main account's block behind a tap
        ck(_tl[0].split(" ", 1)[-1].startswith("All bots today") and "% of all pots)" in _tl[0]
           and "🏦 Pin bot + coin race (main account)" in P(t) and "📊 By bot" in P(t)
           and any(x.split() == ["ALL", "-$12.53", "-1.1%", "-10.1%", "2/5"] for x in _tl)
           and any(x.split() == ["forecaster", "-$2.54", "-9.6%", "-103.7%", "1/1"] for x in _tl)
           and "🟢 Pin + race +$1.66 (+0.33% of the bank)" in _tl and "1 of 1 closes won (100.0%), 0 lost" in P(t)
           and "of the $500.00 it held at the start of the ET day" in P(t) and not tg_html_problems(t),
           "/today: every bot's money as the headline, then the main account's money and its %% of the bank at day "
           "start, then closes won with their %%: %r" % P(t)[:600])
        ck("+2.00% on the $83.34 staked" in P(t),
           "/today: the return on what the bets cost, from Kalshi's books (+1.6626 on 83.30 + 0.0374 fees) -- "
           "shown because Kalshi's money for the day is the headline's money")
        ck("No settled bets" in P(ph.handle(111, "/yesterday")), "/yesterday with nothing settled says so")
        # /market (2026-10-26, operator: "include which bot made the trades"): the FX taker's own log, planted for this
        # check and /fills' below (removed after them): three fills on markets closing at 10:00 AM ET and an order that
        # got nothing; the forecaster's planted fill is ETH 10:00 YES x5
        _fxlog = os.path.join(_bsdir, "fxtake-live-orders.jsonl")
        with open(_fxlog, "w", encoding="utf-8") as _fh:
            for _r in ({"t": "2026-09-16T13:59:31Z", "kind": "fill", "ticker": "KXEURUSD15M-26SEP161000-00", "side": "no",
                        "n": 10.0, "px": 0.99},
                       {"t": "2026-09-16T13:59:32Z", "kind": "fill", "ticker": "KXGOLD15M-26SEP161000-00", "side": "yes",
                        "n": 10.0, "px": 0.99},
                       {"t": "2026-09-16T13:59:33Z", "kind": "fill", "ticker": "KXWTI15M-26SEP161000-00", "side": "yes",
                        "n": 10.0, "px": 0.985},
                       {"t": "2026-09-16T13:59:34Z", "kind": "placed", "ticker": "KXSILVER15M-26SEP161000-00",
                        "filled": 0.0}):
                _fh.write(json.dumps(_r) + "\n")
        # v-tg-active (2026-10-30): the FX taker runs for /market and /fills (a bot that does not run is not named)
        _fxp = (676, "2026-09-16T00:00:00Z", r"python -u research\cleanroom\fxtake_live.py --subaccount 5 --live")
        ph.bs_procs = _bs_procs + [_fxp]
        _mk = P(ph.handle(111, "/market"))
        _mk10 = [x for x in _mk.split("\n") if x.startswith("10:00 AM · ")]
        ck("Sellers:" in _mk and _mk10 == ["10:00 AM · sellers 40.00% · pin bot bought 85 (BNB NO) · forecaster 5 "
                                           "(ETH YES) · FX taker 3 markets x10"] and "BOUGHT" not in _mk,
           "/market: each close names who bought -- the pin bot's own count with its coin and side (its signal), then "
           "every other bot's buys on the markets closing then, from its own log (the FX taker's 3 summed): %r" % _mk)
        ck(buys_words("forecaster", [{"ticker": "KXETH15M-26SEP161000-00", "side": "yes", "contracts": 26},
                                     {"ticker": "KXBTC15M-26SEP161000-00", "side": "yes", "contracts": 2.02}])
           == "forecaster 26 (ETH YES) + 2.02 (BTC YES)"
           and buys_words("race", [{"ticker": "KXCRYPTOLEAD15M-26SEP161000-SOL", "side": "yes", "contracts": 2}])
           == "coin race 2 (SOL YES)"
           and buys_words("ladder", [{"ticker": "KXNEAR15M-X", "side": "yes", "contracts": 96},
                                     {"ticker": "KXZEC15M-X", "side": "no", "contracts": 96},
                                     {"ticker": "KXXRP15M-X", "side": "yes", "contracts": 95}])
           == "ladder 3 markets, 287 contracts",
           "/market's words a bot: one or two markets each named with its side; three or more summed")
        # THE DAILY BRIEFING REACHES THE PHONE, and a failure inside it must
        # not take the command down -- he reads this when the app is not in
        # front of him.
        # /fills -- the operator's ask: filled, paid, seconds out, per order.
        _fl = ph.handle(111, "/fills")
        ck("Pin bot orders today:" in P(_fl) or "No pin bot orders today" in P(_fl),
           "/fills answers with the pin bot's orders today or says there were none")
        ck("🧾 Other bots' fills today: 4 (each bot's own log)\nforecaster 1 fill, 5 contracts · FX taker 3 fills, 30 "
           "contracts\n9:59a · FX taker · WTI 10:00 AM YES x10 · 98.5c\n9:59a · FX taker · GOLD 10:00 AM YES x10 · 99.0c\n"
           "9:59a · FX taker · EURUSD 10:00 AM NO x10 · 99.0c\n9:59a · forecaster · ETH 10:00 AM YES x5 · 49.0c" in P(_fl),
           "/fills (10-26): every other bot's fills today from its own log, a count a bot, then newest first, each line "
           "naming its bot -- the order that got nothing is not a fill: %r" % P(_fl))
        ck(ph.handle(111, "/bets") == _fl, "/bets is the same command")
        ph.bs_procs = _bs_procs                     # the FX taker stops: its fills are 'earlier bots', never named
        _fl0, _mk0 = P(ph.handle(111, "/fills")), P(ph.handle(111, "/market"))
        ck("FX taker" not in _fl0 and "earlier bots 3 fills, 30 contracts" in _fl0
           and "9:59a · earlier bots · GOLD 10:00 AM YES x10 · 99.0c" in _fl0
           and "forecaster 5 (ETH YES) · earlier bots 3 markets x10" in _mk0 and "FX taker" not in _mk0,
           "v-tg-active: a bot that is not running is not named on /fills or /market; a fill in its log (there should "
           "be none) is said as 'earlier bots', never dropped")
        _sv_o = L.orders
        L.orders = [
            {"t": now["t"], "tk": "KXBTC15M-26SEP180100-00", "filled": 77.0,
             "asked": 77.0, "price": 0.968, "tau": 12},
            {"t": now["t"], "tk": "KXETH15M-26SEP180100-00", "filled": 0.0,
             "asked": 50.0, "price": None, "tau": 30},
            {"t": now["t"], "tk": "KXWTI15M-26SEP180100-00", "filled": 20.0,
             "asked": 20.0, "ask_seen": 0.945, "tau": None},
        ]
        try:
            _f2 = P(ph.handle(111, "/fills"))
            _row = [x for x in _f2.split("\n") if "77/77" in x]
            ck(len(_row) == 1 and "96.8c" in _row[0] and _row[0].rstrip().endswith("12s"),
               "an order shows what filled, the price PAID in cents, and how "
               "many seconds were left -- the three things he asked for, on one table row")
            ck("0/50" in _f2 and "1 lost the race" in _f2 and _f2.split("\n")[0] ==
               "🧾 Pin bot orders today: 3 · 2 filled · 1 filled nothing (33%)",
               "a ZERO-FILL order is shown, not hidden -- about one order in "
               "five fills nothing, and dropping them would report a 100% fill "
               "rate; the headline counts it with its share")
            ck("94.5c" in _f2 and "(oil)" in _f2,
               "an oil order shows its price from `ask_seen` and says (oil) "
               "where the seconds would be, because cmdlive does not record a "
               "tau on the order")
            ck("got 97 (65.99%)" in _f2, "...and the footer totals contracts asked vs got, with the share")
            ck(max(len(x) for x in _f2.split("\n")[2:6]) <= 36, "/fills: the table fits a phone's width")
        finally:
            L.orders = _sv_o
        os.remove(_fxlog)                       # the FX taker's planted log: only for /market and /fills above
        _br = ph.handle(111, "/brief")
        ck("THE DAY --" in _br or "Could not build" in _br,
           "/brief answers with the daily briefing, or says plainly that it "
           "could not build one")
        # the briefing reads the live clock and live files, so two calls a
        # second apart can differ; assert the ROUTING, not the wording
        from phone import command as _pcm           # v-tg-rebuild step 10: one Command answers both names
        ck(_pcm.by_name("/summary") is _pcm.by_name("/brief") is not None
           and _pcm.by_name("/brief").module == "phone.commands.brief_cmd",
           "/summary is the same command under its other name")
        ck("THE DAY --" not in P(ph.handle(111, "/today") or ""),
           "and /today is UNTOUCHED -- it already existed and gives the plain "
           "money for the day; taking its name would have quietly replaced "
           "something he uses with something longer")
        # THE OPPORTUNITY TREND REACHES THE PHONE, and a health dict that does
        # not carry it must not break the command -- the operator reads
        # /market from his phone when the app is not in front of him.
        state["h"]["supply_lines"] = ["Cheap offers: up 7% on a normal day."]
        state["h"]["supply_age_d"] = 0.5
        mk = P(ph.handle(111, "/market"))
        ck("IS THE OPPORTUNITY GOING AWAY?" in mk and "up 7%" in mk,
           "/market carries the opportunity trend, from the same lines the "
           "desktop shows, so the two cannot drift apart")
        ck("0.5 days ago" in mk,
           "...and says how old the measurement is, because a stale trend is a "
           "reassuring number about a week that already ended")
        state["h"].pop("supply_lines")
        ck("Sellers:" in P(ph.handle(111, "/market")),
           "NULL: a health reading with no opportunity block still answers")
        _lo = P(ph.handle(111, "/losses"))
        _lb = _lo.split("By bot")
        ck(_lo.startswith("🔴 3 losing markets of 8 settled, every bot (37.5%)")
           and "Wed Sep 16\n-$2.54 (" in _lo and "Forecaster · ETH 10:00 AM YES x5" in _lo
           and "Pin bot · ETH 9:45 AM hedged x80" in _lo and "Tue Sep 15\n-$4.51" in _lo and "Other · WTI 2:00 PM YES x5" in _lo
           and _lo.index("Forecaster · ETH") < _lo.index("Pin bot · ETH") < _lo.index("Other · WTI")
           and len(_lb) == 2 and "Coin race" not in _lb[0] and "Ladder" not in _lb[1] and "Earlier bots  0/1" in _lb[1]
           and "ALL" in _lb[1] and "3/8" in _lb[1]                  # v-tg-active: the stopped ladder is 'Earlier bots'
           and fits(ph.handle(111, "/losses")),
           "/losses (10-26): EVERY bot's losing markets from Kalshi's books -- the forecaster's and the old oil bot's "
           "too -- each named by bot, newest day first, with side and contracts; the pin's hedged market on its own "
           "line; a bot-by-bot table: %r" % _lo)
        ck(ph.handle(111, "/hedges") == "No hedges yet.", "/hedges with none")
        _op = P(ph.handle(111, "/open"))
        ck(_op.startswith("📂 Coin race: 1 open · $19.60 at risk") and "race SOL 11:00 AM YES x20 · $19.60" in _op
           and "Pin bot" not in _op,
           "/open: every pot -- no pin bet open here (its own log), the coin race's one open leg from Kalshi's "
           "positions (botstats), with what is at risk: %r" % _op)
        _dd = P(ph.handle(111, "/days"))
        ck(_dd.startswith("🔴 All bots last 7 days -$15.95 (-10.0% on $160.13 staked · -1.4% of all pots)")
           and "all time -$15.95 (-1.4% on the $1,103.75 put in)" in _dd
           and any(x.split()[:6] == ["Sep", "16", "-$12.53", "-1.1%", "-10.1%", "2/5"] for x in _dd.split("\n"))
           and any(x.split() == ["ALL", "-$15.95", "-1.4%", "-10.0%", "3/8"] for x in _dd.split("\n"))
           and "Sep 16: +$1.66 (+0.33% of the bank) · 0 of 1 closes lost" in _dd,
           "/days: every bot's week as the headline with its % of all pots, all time on the money put in, each day's "
           "% of all pots, the week bot by bot, the main account's own days (with % of its bank) behind a tap")
        # ---- /stats, /race, /racestats -----------------------------------
        # A planted world: Kalshi's books (the ONLY money source), the bots'
        # order records (only for seconds-left), a VERSIONS.md, the live
        # bot's size / high-water / day-loss files, a process table, the
        # penny bot's log and two paper race arms' logs. Every expected
        # number below was worked by hand from the rows planted here.
        _led0 = open(_pl.LEDGER, encoding="utf-8").read()

        def _row(tk, res, yes_n=0, yes_c=0, no_n=0, no_c=0, fee=0.0, value=None,
                 st="2026-09-16T14:00:20Z"):
            r = {"ticker": tk, "market_result": res,
                 "yes_count_fp": "%.2f" % yes_n, "yes_total_cost_dollars": "%.6f" % yes_c,
                 "no_count_fp": "%.2f" % no_n, "no_total_cost_dollars": "%.6f" % no_c,
                 "fee_cost": "%.6f" % fee, "revenue": 0, "settled_time": st}
            if value is not None:
                r["value"] = value
            return r
        B_ = "KXBTC15M-26SEP151015-15"          # 09-15: lost 40 NO at 97c, no hedge  -38.80
        C_ = "KXETH15M-26SEP141030-30"          # 09-14: hedged loss -14.10, hedge got back +5.00
        D_ = "KXSOL15M-26SEP091200-00"          # 09-09: won +2.45 (lifetime only)
        E_ = "KXWTI15M-26SEP070500-00"          # 09-07: BEFORE live -- must be excluded
        F_ = "KXXRP15M-26SEP091300-00"          # 09-09: a FULL hedge (equal counts), lost -36.50
        G_ = "KXDOGE15M-26SEP091400-00"         # 09-09: hedge BIGGER than the entry, won by net +29.80
        R1X, R1B = "KXCRYPTOLEAD15M-26SEP160500-XRP", "KXCRYPTOLEAD15M-26SEP160500-BTC"
        R2X, R2H = "KXCRYPTOLEAD15M-26SEP160715-XRP", "KXCRYPTOLEAD15M-26SEP160715-HYPE"
        R3_ = "KXCRYPTOLEAD15M-26SEP150930-ETH"
        _plant = json.loads(_led0)
        _plant["settlements"].update({
            "b": _row(B_, "yes", no_n=40, no_c=38.80, st="2026-09-15T14:15:20Z"),
            "c": _row(C_, "yes", yes_n=10, yes_c=5.00, no_n=20, no_c=19.00, fee=0.10, st="2026-09-14T14:30:20Z"),
            "d": _row(D_, "yes", yes_n=50, yes_c=47.50, fee=0.05, st="2026-09-09T16:00:20Z"),
            "e": _row(E_, "yes", yes_n=10, yes_c=9.00, st="2026-09-07T09:00:20Z"),
            "f": _row(F_, "yes", yes_n=79, yes_c=40.00, no_n=79, no_c=75.00, fee=0.50, st="2026-09-09T17:00:20Z"),
            "g": _row(G_, "yes", yes_n=79, yes_c=23.70, no_n=26, no_c=25.20, fee=0.30, st="2026-09-09T18:00:20Z"),
            "r1x": _row(R1X, "yes", yes_n=1, yes_c=0.97, fee=0.0021, value=100, st="2026-09-16T09:00:38Z"),
            "r1b": _row(R1B, "no", no_n=1, no_c=0.98, fee=0.0014, value=0, st="2026-09-16T09:00:38Z"),
            "r2x": _row(R2X, "scalar", yes_n=1, yes_c=0.97, fee=0.0021, value=50, st="2026-09-16T11:15:38Z"),
            "r2h": _row(R2H, "scalar", no_n=1, no_c=0.98, fee=0.0014, value=50, st="2026-09-16T11:15:38Z"),
            "r3": _row(R3_, "yes", no_n=1, no_c=0.85, fee=0.006, value=100, st="2026-09-15T13:30:38Z"),
        })
        with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
            json.dump(_plant, _fh)
        os.utime(_pl.LEDGER, (time.time() + 20, time.time() + 20))
        with open(os.path.join(td, "VERSIONS.md"), "w", encoding="utf-8") as _fh:
            _fh.write("# v-race-tie1 -- 2026-09-16 ~14:0xZ -- COIN RACE, LIVE penny test: ties\n\nbody\n\n"
                      "# v-pinfix -- 2026-09-16 12:30Z (pid 1, code_sha abc) -- LIVE: a fix\n\n"
                      "# v-older -- 2026-09-15 -- LIVE: no time on this one\n")
        for _nm, _d in (("pinrun-live-size.json", {"size": 79.0, "bank": 930.04, "at": "2026-09-16T14:21:42Z"}),
                        ("pinrun-hwm.json", {"hwm": 1037.33, "at": "2026-09-15T23:48:38Z"}),
                        ("pinrun-dayloss.json", {"day": "2026-09-16", "realised": 11.1424})):
            with open(os.path.join(td, _nm), "w", encoding="utf-8") as _fh:
                json.dump(_d, _fh)
        _procs = [
            (2554960, r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinrun.py --live --size 20 --hedge-belief 0.40 --loss-cap 200 --bank-brake 4.00'),
            (11, r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinrun.py --size 20 --hedge-belief 0.40 --pin 0.985 --arm-name arm-pin0.985'),
            (12, r'"C:\Python314\python.exe" -u C:\kals-repo\research\cmdarm.py --minutes 4320 --series KXWTI15M --out C:\kals-repo\results\cmdarm-wide230.jsonl'),
            (13, r'C:\Python314\python.exe -u research/pinracearm.py --minutes 4320 --log C:/kals-repo/results/pinracearm-racectl.jsonl --model fair'),
            (14, r'C:\Python314\python.exe -u research/pinracearm.py --paper-live --minutes 10080 --min-z 3.0 --log C:/kals-repo/results/pinracearm-z3.jsonl'),
            (15, r'C:\Python314\python.exe -u research/pinracearm.py --live --max-contracts 1 --max-stake 20 --live-rolling-stake --live-tau-max 30 --minutes 10080 --log C:/kals-repo/results/pinracepenny-live.jsonl'),
            (16, r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinphone.py'),
            (17, r'"C:\Python314\python.exe" kalshi_collector.py --key-id x --out ./kalshi_data'),
        ]
        ph.procs_fn = lambda: _procs
        ph.versions_path = os.path.join(td, "VERSIONS.md")
        ph.race30_epoch = calendar.timegm((2026, 9, 16, 0, 0, 0))
        _rails = {"max_contracts": 1.0, "max_stake": 20.0, "tau_max": 30, "min_price": 0.9,
                  "max_legs": 5, "confirm": 5, "clock_tau": 20, "rolling": True,
                  "stop_on_loss": True, "paper": False}
        _penny = os.path.join(td, "pinracepenny-live.jsonl")

        def _w(path, recs, mode="a"):
            with open(path, mode, encoding="utf-8") as _fh:
                for r in recs:
                    _fh.write(json.dumps(r) + "\n")
        _w(_penny, [
            {"kind": "start", "t": "2026-09-16T08:00:00Z", "live": True, "live_rails": _rails},
            {"kind": "live_order", "t": "2026-09-16T08:59:20Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "ticker": R1X, "side": "yes", "filled": 1.0, "exec_price": 0.97, "staked": 0.97},
            {"kind": "live_order", "t": "2026-09-16T08:59:30Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "ticker": R1B, "side": "no", "filled": 1.0, "exec_price": 0.98, "staked": 1.95},
            {"kind": "live_settled", "t": "2026-09-16T09:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "positions": 2, "won": 2, "pnl": 0.0465, "staked_open": 0.0},
            {"kind": "live_order", "t": "2026-09-16T11:14:40Z", "event": "KXCRYPTOLEAD15M-26SEP160715",
             "ticker": R2X, "side": "yes", "filled": 1.0, "exec_price": 0.97, "staked": 0.97},
            {"kind": "live_order", "t": "2026-09-16T11:14:41Z", "event": "KXCRYPTOLEAD15M-26SEP160715",
             "ticker": R2H, "side": "no", "filled": 1.0, "exec_price": 0.98, "staked": 1.95},
            {"kind": "live_settled", "t": "2026-09-16T11:16:15Z", "event": "KXCRYPTOLEAD15M-26SEP160715",
             "positions": 2, "won": 2, "pnl": 0.0465, "staked_open": 0.0},
            {"kind": "live_halt", "t": "2026-09-16T13:31:15Z", "staked": 2.81, "sends": 4,
             "why": "first real loss: KXCRYPTOLEAD15M-26SEP160930 no at 85c"},
        ], "w")
        _w(os.path.join(td, "pinracearm-z3.jsonl"), [
            {"kind": "start", "t": "2026-09-15T00:00:00Z", "paper_live": True},
            {"kind": "settled", "t": "2026-09-16T09:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "positions": 1, "won": 1, "pnl": 4.65},                       # size-250 paper leg: IGNORED
            {"kind": "live_settled", "paper": True, "t": "2026-09-16T09:01:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP160500", "positions": 1, "won": 1, "pnl": 0.0186},
            {"kind": "live_settled", "paper": True, "t": "2026-09-16T11:16:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP160715", "positions": 1, "won": 1, "pnl": 0.0186},
            {"kind": "live_settled", "paper": True, "t": "2026-09-16T12:31:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP160830", "positions": 1, "won": 0, "pnl": -0.98},
            {"kind": "live_settled", "paper": True, "t": "2026-09-15T13:31:15Z",
             "event": "KXCRYPTOLEAD15M-26SEP150930", "positions": 0, "won": 0, "pnl": 0.0},
        ], "w")
        _w(os.path.join(td, "pinracearm-racectl.jsonl"), [
            {"kind": "settled", "t": "2026-09-16T09:01:15Z", "event": "KXCRYPTOLEAD15M-26SEP160500",
             "positions": 2, "won": 2, "pnl": 5.0},
            {"kind": "settled", "t": "2026-09-16T11:16:15Z", "event": "KXCRYPTOLEAD15M-26SEP160715",
             "positions": 1, "won": 1, "pnl": 4.0},
            {"kind": "settled", "t": "2026-09-15T13:31:15Z", "event": "KXCRYPTOLEAD15M-26SEP150930",
             "positions": 1, "won": 0, "pnl": -212.5},
        ], "w")
        _sv_o, _sv_g = L.orders, L.hedges
        # the bot's hedge record for F: it BOUGHT yes, so the entry was no
        L.hedges = [{"t": calendar.timegm((2026, 9, 9, 16, 59, 58)), "kind": "hedge", "tk": F_,
                     "belief": 0.3, "n": 79, "price": 0.51, "status": "executed", "side": "yes",
                     "entry": 0.95, "tau": 2, "file": "x"},
                    {"t": calendar.timegm((2026, 9, 9, 17, 59, 58)), "kind": "hedge", "tk": G_,
                     "belief": 0.2, "n": 79, "price": 0.30, "status": "executed", "side": "yes",
                     "entry": 0.97, "tau": 3, "file": "x"}]
        L.orders = [
            {"t": calendar.timegm((2026, 9, 16, 13, 59, 48)), "tk": c1, "filled": 85.0, "asked": 85.0, "price": 0.98, "tau": 12},
            {"t": calendar.timegm((2026, 9, 16, 13, 59, 55)), "tk": c1, "filled": 10.0, "asked": 10.0, "price": 0.99, "tau": 5},
            {"t": calendar.timegm((2026, 9, 15, 14, 14, 30)), "tk": B_, "filled": 40.0, "asked": 40.0, "price": 0.97, "tau": 30},
            {"t": calendar.timegm((2026, 9, 14, 14, 29, 20)), "tk": C_, "filled": 20.0, "asked": 20.0, "price": 0.95, "tau": 40},
            {"t": calendar.timegm((2026, 9, 9, 15, 59, 52)), "tk": D_, "filled": 50.0, "asked": 50.0, "price": 0.95, "tau": 8},
        ]
        try:
            # the pure pieces first
            _vs = versions(ph.versions_path)
            ck([v[0] for v in _vs] == ["v-race-tie1", "v-pinfix", "v-older"],
               "VERSIONS.md: every `# v-... -- <date>` header is read, newest first")
            ck(_vs[0][2] is True and _vs[0][1] == calendar.timegm((2026, 9, 16, 14, 0, 0)),
               "a `~14:0xZ` time reads as 14:00 and is marked approximate")
            ck(_vs[1][2] is False and _vs[1][1] == calendar.timegm((2026, 9, 16, 12, 30, 0)),
               "`12:30Z (pid ...)` reads as 12:30 exactly, the pid in brackets ignored")
            ck(_vs[2][1] == et_day_start("2026-09-15") and _vs[2][2] is True,
               "a header with no time is midnight ET of its date, marked approximate")
            ck(live_version(ph.versions_path)[0] == "v-pinfix",
               "the LIVE version skips the coin race's header sitting on top -- v-race-tie1 "
               "is the penny bot's, and dating the up/down bot's window from it would be wrong")
            _fl = fleet_roles(_procs)
            ck(_fl["live"][0] == 2554960 and _fl["penny"][0] == 15,
               "the process table: pinrun --live is the money bot, pinracearm --live (not "
               "--paper-live) is the penny bot")
            ck(_fl["arms"] == ["arm-pin0.985", "cmdarm-wide230"] and _fl["race_arms"] == ["racectl", "z3"],
               "paper arms are named from --arm-name / --out, race arms from --log; the "
               "phone, the collector and the live bots are not arms")
            import re as _re
            with open(os.path.join(HERE, "pinrun.py"), encoding="utf-8", errors="replace") as _fh:
                _mdd = _re.search(r"^MAX_DRAWDOWN = ([0-9.]+)", _fh.read(), _re.M)
            ck(_mdd and abs(float(_mdd.group(1)) - MAX_DRAWDOWN) < 1e-12,
               "the halt line copied here (%.2f) is pinrun.MAX_DRAWDOWN -- drift fails" % MAX_DRAWDOWN)
            _mk = markets_from(raw_ledger(_pl.LEDGER))
            ck(abs(_mk[C_]["pnl"] + 14.10) < 1e-9 and _mk[C_]["hedged"] and _mk[C_]["side"] == "no"
               and abs(_mk[C_]["hedge_pnl"] - 5.00) < 1e-9,
               "a hedged market is ONE market at its net (-14.10), the entry is the bigger side, "
               "and the hedge leg's own take (+5.00) is what it got back")
            ck(_mk[R2X]["tie"] and abs(_mk[R2X]["pnl"] + 0.4721) < 1e-9 and not _mk[R1X]["tie"],
               "Kalshi's value 50 is a tie, paid 50c: -47.21c on a 97c leg")
            ck(abs(_mk[E_]["pnl"] - 1.00) < 1e-9 and _mk[E_]["day"] == "2026-09-07",
               "the pre-live row is parsed (day 09-07)... ")
            ck(_mk[F_]["hedged"] and _mk[F_]["side"] is None and _mk[F_]["hedge_pnl"] is None,
               "a FULL hedge has equal counts: with nothing to break the tie there is no side "
               "and no hedge figure -- never a guess")
            _mkf = markets_from(raw_ledger(_pl.LEDGER), {F_: "no"})
            ck(_mkf[F_]["side"] == "no" and abs(_mkf[F_]["hedge_pnl"] - 39.00) < 1e-9
               and abs(_mkf[F_]["pnl"] + 36.50) < 1e-9,
               "...and the bot's own side breaks it: entry NO, the 79 YES hedge got back "
               "79.00 - 40.00 = +39.00 of a -36.50 market")
            ck(sides_of(ph.ledger).get(F_) == "no",
               "the phone takes that side from the bot's hedge record (it bought YES, so "
               "the entry was NO)")
            _mkg = markets_from(raw_ledger(_pl.LEDGER), sides_of(ph.ledger))
            ck(_mkg[G_]["side"] == "no" and _mkg[G_]["won"] and abs(_mkg[G_]["hedge_pnl"] - 55.30) < 1e-9,
               "a hedge BIGGER than its entry (79 YES over 26 NO): the bot's record, not the "
               "count, names the entry, so the hedge's take is 79.00 - 23.70 = +55.30 on a "
               "market that won +29.80 by its net -- the count rule had booked -25.20")
            _fu = fleet_roles(None)
            ck(_fu["unknown"] and _fu["live"] is None and _fu["arms"] == [],
               "NULL: a process table that could not be read is UNKNOWN, not empty")
            ck(first_entries(L.orders)[c1] == 12,
               "...and the FIRST filled order sets the seconds-left, not the later top-up")

            # /stats
            s = ph.handle(111, "/stats")
            ck(fits(s) and len(split_html(s)) == 1, "/stats fits one Telegram message on this world (%d chars)" % len(s))
            ps = P(s)
            ck(ps.split("\n")[0].startswith("🔴 Lifetime -$57.25 (") and " on $" in ps.split("\n")[0],
               "/stats: lifetime money and its return on what was risked is the headline")
            ck("LIVE v-pinfix since 09/16 08:30 AM ET, pid 2554960." in ps,
               "/stats names the live version, its start in ET and the pid")
            ck("Hedge trigger: belief 40%. Size 79 contracts (auto), bank $930.04 read 10:21 AM." in ps,
               "the hedge trigger from the live argv, the size and bank from the bot's size file")
            ck("Halt if the bank falls to $829.86 (20% under its high of $1,037.33): $100.18 of room (10.8% of the "
               "bank)." in ps,
               "the halt line is 20% under the high-water mark, with the room left in dollars and as a share")
            ck("Today by the bot's own count: +$11.14 (stops at -$200 for the day)." in ps,
               "the day figure from the bot's own file is labelled as the bot's, with the cap")
            ck("Paper arms: 2 (pin0.985, cmdarm-wide230) + 2 race arms (racectl, z3)." in ps,
               "the fleet, counted and named from the process table")
            ck("Coin race: 2 races since 09/15: 1 won (50.0%), 1 tie, 0 lost, -$0.91 (/race)." in ps,
               "the coin race summary line: the tie is a tie, not a win")
            ck(any(x.split() == ["Today", "+$0.76", "+0.9%", "+0.17%", "60.0%", "2"] for x in ps.split("\n"))
               and "of bank = of the main account's bank when the window began" in ps,
               "the window table: money, return on what was risked (0.76 / 87.24), its % of the bank that began the "
               "day (10-26), markets won, losses")
            _blk, _cur = {}, None
            for _ln in ps.split("\n"):                      # the windows' sentences, inside the one quote
                _k = _ln.split(" (")[0].split(":")[0]
                if _k in ("LIFETIME", "LAST 7 DAYS", "LAST 3 DAYS", "TODAY") or _k.startswith("SINCE v-"):
                    _cur = _k
                    _blk[_cur] = _ln
                elif _cur:
                    _blk[_cur] += "\n" + _ln
            ck(set(_blk) >= {"LIFETIME", "LAST 7 DAYS", "LAST 3 DAYS", "TODAY", "SINCE v-pinfix"}
               and s.count("<blockquote expandable>") == 1,
               "five windows: lifetime, 7 days, 3 days, today, since the live version -- in ONE tap-to-open quote")
            _t = _blk["TODAY"]
            ck("Made +$0.76 on $87 risked; 5 mkts, 3 closes, 89 contracts; fees $0.04." in _t,
               "TODAY: 1.6626 + 0.0279 + 0.0186 - 0.4721 - 0.4814 = +0.76 on the 87.24 risked; "
               "5 markets on 3 closes; 89 contracts")
            ck("Best day" not in _t, "a one-day window has no best/worst day line")
            ck("Won 3 of 5 mkts (60.0 of 100); 98.9 of 100 contracts paid; by $ risked 97.8." in _t,
               "win rate by market (3 of 5), by contracts paid (88 of 89: the tie paid half) "
               "and by dollars (85.29 of 87.24)")
            ck("Break-even 98.0 of 100 contracts at 98.0c avg paid (fee in): margin +0.8 pts = +$0.87 per "
               "$100 risked. By count 97.7 of 100 mkts must win; 60.0 did." in _t,
               "break-even = dollars paid / contracts (87.24 / 89 = 98.0c); the margin is against "
               "the contracts paid (98.9 - 98.0) and matches the real profit per $100 risked; "
               "the count version beside it")
            ck("Losses 2: -$0.95, avg -$0.48, worst -$0.48 (coin race, HYPE 09/16); 0 hedged, their hedge legs netted "
               "+$0.00." in _t,
               "TODAY's losses are the two tied legs; the worst names its bot (10-26): the main account holds pin and race")
            _7 = _blk["LAST 7 DAYS"]
            ck("Made -$53.00 on" in _7 and "8 mkts" in _7,
               "LAST 7 DAYS adds 09-15 and 09-14: -38.80 -14.10 -0.856 on top of today (09-09 is outside it)")
            ck("Losses 5: -$54.71, avg -$10.94, worst -$38.80 (pin bot, BTC 09/15); 1 hedged, their hedge legs netted "
               "+$5.00." in _7,
               "...five losses, the worst named, the hedged one counted with what its hedge got back")
            ck("LAST 3 DAYS: the same 8 markets as LAST 7 DAYS, so the same numbers." in _blk["LAST 3 DAYS"],
               "LAST 3 DAYS holds the same markets, so it says so instead of repeating every sentence")
            _l = _blk["LIFETIME"]
            ck("Made -$57.25 on" in _l and "11 mkts" in _l,
               "LIFETIME adds 09-09 (+2.45, the -36.50 full hedge, the +29.80 over-hedge) and "
               "EXCLUDES the 09-07 row: 11 markets, not 12")
            ck("Best day +$0.76 (09/16), worst -$39.66 (09/15); avg -$6.36/day over 9 days." in _l,
               "best and worst ET day, and the average over the calendar days since 09/08")
            ck("Losses 6: -$91.21, avg -$15.20, worst -$38.80 (pin bot, BTC 09/15); 2 hedged, their hedge legs "
               "netted +$44.00; hedge legs on won mkts netted +$55.30." in _l,
               "the FULL hedge counts (5.00 + 39.00 on two hedged losses) and the over-hedge's "
               "+55.30 sits with the won markets")
            ck("First buys: 50% with 20 s or less left (2 mkts, +$4.11), 50% at 21-45 s (2 mkts, -$52.90); 7 not timed." in _l,
               "seconds-left split from the ORDER records, money per bucket, untimed markets counted")
            ck("Lifetime by bot: coin race -$1.76, pin bot -$55.49." in ps,
               "the lifetime money split by bot, by the names a person knows")
            ck("Made +$1.66 on" in _blk["SINCE v-pinfix"] and "1 mkts" in _blk["SINCE v-pinfix"],
               "SINCE the version: only the market that closed after 12:30Z")
            # this planted world's order rows are /stats-shaped (no "close"), so the per-day loop is stubbed
            # out; the since-version line reads Kalshi's books through _markets(), which this world has
            _days0 = ph.ledger.days
            try:
                ph.ledger.days = lambda: []
                _dy = _cmdrun(ph, "/days")
            finally:
                ph.ledger.days = _days0
            ck("Pin bot since v-pinfix (" in P(_dy) and ": +$1.66, 1 markets, 0 lost (0.0%)" in P(_dy)
               and P(_dy).startswith("🔴 All bots last 7 days "),
               "/days carries the running version's own line (a deploy day mixes two versions), same money as /stats; "
               "all time is its headline")

            # /race
            r = P(ph.handle(111, "/race"))
            ck("RUNNING, pid 15" in r and "Fixed size: 1 contract a leg, $20 out at most (settled bets give it back)"
               in r and "Buys only inside 30 s, 90c or better, up to 5 legs a race, stops on the first loss." in r,
               "/race: the live race's size and rails in words, from its own start record (a start record with no "
               "bank_sizing is a fixed size, and says so)")
            ck("penny" not in r.lower().replace("pinracepenny", ""),
               "/race never calls the live coin race a penny bot (2026-10-18: it sizes from the bank since "
               "v-race-snowball)")
            ck("STOP RAIL FIRED 09/16 09:31 AM ET: first real loss: KXCRYPTOLEAD15M-26SEP160930 no at 85c. No real order since." in r,
               "the stop-on-first-loss state, with when and why")
            ck(r.split("\n")[0] == "🔴 Coin race today -$0.91 (-23.2% on $3.91 staked) · 1 of 2 won (50%) · 1 tie, 0 lost",
               "today's coin-race money from Kalshi's books is the headline, with its return on what the legs cost "
               "(-0.907 on 3.90 + 0.007 fees) and the races won")
            _lines = r.split("\n")
            _i = _lines.index("🏆 Last 10 races (Kalshi's books)")
            ck(_lines[_i + 1:_i + 8] == ["Wed Sep 16", "7:15a HYPE no 98c -$0.95 TIE", "      XRP yes 97c",
                                         "5:00a BTC no 98c  +$0.05 WON", "      XRP yes 97c", "Tue Sep 15",
                                         "9:30a ETH no 85c  -$0.86 LOST"],
               "the last races newest first, a heading a day: legs, side, price paid, money, TIE / WON / LOST")
            ck("Paper race arms running: racectl, z3." in r, "the race arms from the process table")
            ph.procs_fn = lambda: None
            _ru = P(ph.handle(111, "/race"))
            ck("Running? The process table could not be read." in _ru
               and "Paper race arms running: process table could not be read." in _ru
               and "(process table could not be read)" in P(ph.handle(111, "/stats")),
               "NULL: when the process table cannot be read, /race and /stats SAY so -- "
               "never 'not running' or 'no arms'")
            ph.procs_fn = lambda: _procs
            # a restart clears the halt; a leg on the race closing now is 'holding'
            _w(_penny, [
                {"kind": "start", "t": "2026-09-16T14:40:00Z", "live": True, "live_rails": _rails},
                {"kind": "live_order", "t": "2026-09-16T14:59:40Z", "event": "KXCRYPTOLEAD15M-26SEP161115",
                 "ticker": "KXCRYPTOLEAD15M-26SEP161115-SOL", "side": "yes", "filled": 1.0,
                 "exec_price": 0.98, "staked": 0.98},
            ])
            r2 = P(ph.handle(111, "/race"))
            ck("Stop rail: not fired since the restart at 09/16 10:40 AM ET." in r2,
               "after a restart the rail reads as not fired -- a halt before the restart is history")
            ck("Now: race closing 11:15 AM ET (15:00 left) -- holding SOL yes 98c x1. $0.98 out." in r2,
               "the race closing next, the legs held on it and the dollars out")

            # /racestats
            qh = ph.handle(111, "/racestats")
            q = P(qh)
            ck("ALL TIME (since 09/15): 3 races: 1 won, 1 tie, 1 lost. -$1.76. 5 legs at 95.0c avg; "
               "break-even 95.3 of 100 legs must pay, actual 60.0." in q,
               "/racestats: races won/tie/lost, money, avg leg price, break-even vs actual per leg")
            ck("TODAY: 2 races: 1 won, 1 tie, 0 lost. -$0.91." in q, "...and today's")
            ck(q.split("\n")[0].startswith("🔴 Coin race all time -$1.76 (") and "3 races, 33.3% won" in q.split("\n")[0],
               "the all-time money, its return on what the legs cost and the share of races won lead the page")
            ck(any(x.split() == ["Today", "-$0.91", "-23.2%", "2", "50%", "1/0"] for x in q.split("\n")),
               "the window table: money, return, races, won, ties / losses")
            # the arms: in this world both are RUNNING (the process table names them) and nothing is re-scored
            ck("z3 · PAPER, RUNNING (since Sep 14)" in q and "racectl · PAPER, RUNNING (since Sep 16)" in q,
               "every arm is labelled PAPER, with whether it runs (the process table) and since when (its log)")
            ck(any(x.split() == ["z3", "2", "100%", "50.0%", "1/1/0"] for x in q.split("\n"))
               and any(x.split() == ["racectl", "2", "100%", "50.0%", "1/1/0"] for x in q.split("\n")),
               "a --paper-live arm and a plain arm on the same races: in 2 of 2, 1 won, the race Kalshi tied is a tie")
            ck(any(x.split() == ["z3", "+$0.04*", "-", "-$0.91"] for x in q.split("\n"))
               and any(x.split() == ["racectl", "+$9.00*", "-", "-$0.91"] for x in q.split("\n"))
               and "* = the arm's own log money (no Kalshi re-scoring on file" in q
               and "z3's and racectl's own logs booked a tie as a win" in q,
               "with no re-scoring on file: the arm's own-log money, starred and said so (its log booked the tie "
               "as a win), no live-size figure invented, and the live bot's money on the same races beside it")
            ck("raceedge0: no log." in q and "gap075: no log." in q, "an arm without a log says so")
            ck("z3 bar: 3 races so far, 2 losses (first 50: 2). Pass = 125 races with 0 losses, or 250 "
               "with at most 1. Kill = 2 losses in the first 50 -- AT THE KILL LINE." in q,
               "the z3 bar counts EVERY race the arm entered, a tie as a loss, and names the kill line")
            ck(fits(qh) and not tg_html_problems(qh), "/racestats: one message, Telegram-valid")
            # THE ARMS RE-SCORED ON KALSHI (results/race_arms_scored.json, 2026-10-18): used only while the arm's
            # log is the size it was scored at; z3 here is scored, racectl's file size does not match
            _zsz = os.path.getsize(os.path.join(td, "pinracearm-z3.jsonl"))
            with open(os.path.join(td, RACE_ARMS_SCORED), "w", encoding="utf-8") as _fh:
                json.dump({"made": "2026-10-18T10:00:00Z", "arms": {
                    "z3": {"log_size": _zsz, "own_size": "1 contract a leg",
                           "same": {"races": 2, "own": -0.47, "own_log": 0.04, "at_live": -9.40, "live": -0.91},
                           "run": {"races": 3, "won": 1, "tie": 1, "lost": 1, "own": -1.45, "at_live": -29.0}},
                    "racectl": {"log_size": 1, "own_size": "up to 250 a leg (avg 1)",
                                "same": {"races": 2, "own": 1.0, "own_log": 9.0, "at_live": 1.0, "live": -0.91}}}},
                          _fh)
            q2 = P(ph.handle(111, "/racestats"))
            ck(any(x.split() == ["z3", "-$0.47", "-$9.40", "-$0.91"] for x in q2.split("\n"))
               and any(x.split() == ["racectl", "+$9.00*", "-", "-$0.91"] for x in q2.split("\n"))
               and "z3 · PAPER, RUNNING (since Sep 14) · 1 contract a leg" in q2
               and "their own logs said z3 +$0.04 (a log books a tie as a win" in q2
               and "z3, whole run: 3 races, 1 won, 1 tie, 1 lost; own size -$1.45, at the live bot's size -$29.00." in q2
               and "* = the arm's own log money (its log changed after it was re-scored" in q2,
               "re-scored on Kalshi: z3's own-size money with the tie paid 50c and its money at the live bot's size, "
               "its own log's figure named; racectl's log changed, so its own-log money stays, starred")
            # STOPPED: an arm out of the process table whose log ended is PAPER, STOPPED, with its dates; z3's bar
            # says it cannot move
            _w(os.path.join(td, "pinracearm-z3.jsonl"), [{"kind": "end", "t": "2026-09-16T12:40:00Z"}])
            ph.procs_fn = lambda: [x for x in _procs if x[0] not in (13, 14)]
            q3 = P(ph.handle(111, "/racestats"))
            ck("z3 · PAPER, STOPPED · ran Sep 14 to Sep 16" in q3 and "racectl · PAPER, " in q3
               and "PAPER ARMS -- no real money" in q3,
               "an arm that left the process table, its log ended, reads PAPER, STOPPED with the dates it ran")
            ck(any(x.split() == ["z3", "+$0.04*", "-", "-$0.91"] for x in q3.split("\n")),
               "...and its log grew after it was scored, so the scored figures are no longer used")
            ck("paper made 41% more than real fills" in q3 and "walking the book cuts it 30-66%" in q3,
               "the legend gives the skeptic's paper-optimism figures (41% on the live bot's own legs; touch "
               "pricing of the 250-a-leg arms, 30-66%), not the milder 25%")
            # /racestats on the REAL table reader never reads Windows on the poll thread: with a cold cache it
            # shows the arms from their logs alone and list_python_procs is not called; a fresh cache is used
            # (v-tg-rebuild step 10: the table is botdata.procs'; its synchronous read is read_all)
            _lpp_calls, _lpp0, _procs0 = [], _bdprocs.read_all, dict(_bdprocs._TABLE)

            def _lpp_spy(*a, **k):
                _lpp_calls.append(1)
                return []
            _bdprocs.read_all = _lpp_spy
            try:
                _bdprocs._store(None, 0.0)
                ph.procs_fn = python_procs
                q4 = P(ph.handle(111, "/racestats"))
                _fresh_ok = (cached_python_procs() is None
                             and (_bdprocs._store([[7, "", "x"]]) or cached_python_procs()) == [(7, "x")]
                             and (_bdprocs._store([[7, "", "x"]], time.time() - 3 * PROC_REFRESH_S)
                                  or cached_python_procs()) is None)
            finally:
                _bdprocs.read_all = _lpp0
                _bdprocs._TABLE.clear()
                _bdprocs._TABLE.update(_procs0)
            ck(not _lpp_calls and _fresh_ok and "z3 · PAPER, STOPPED · ran Sep 14 to Sep 16" in q4
               and "PAPER ARMS -- no real money" in q4,
               "/racestats with the real reader and a cold cache: no synchronous WMI read (alerts never wait behind "
               "it), the arms still labelled from their logs; a fresh cache is used, a stale one reads as unknown")
            ph.procs_fn = lambda: _procs
            os.remove(os.path.join(td, RACE_ARMS_SCORED))
            ck(all("/%s" % c in HELP_TEXT for c in ("stats", "race", "racestats", "bars")), "the four are in /help")
            # /bars -- the operator's one-word verdicts. The text is bars.py's,
            # never rebuilt here; the phone only routes it.
            ph.bars_fn = lambda: "BARS-STUB"
            ck(P(ph.handle(111, "/bars")) == "BARS-STUB", "/bars returns bars.py's words unchanged (laid out only)")
            ph.bars_fn = None
            _bt = ph.handle(111, "/bars")
            ck("BARS  " in P(_bt) and "VERDICT:" in P(_bt) and "FRESH OFFER TEST" in P(_bt),
               "...and the real module answers on this world with its header and a verdict")
            _bl = P(_bt).split("\n")
            _okb = (_bl[0].startswith("📏 Bars: ") and "VERDICT: " not in _bl[1]
                    and any(x.startswith(("✅ ", "❌ ", "🔁 ", "⏳ ")) and "FRESH OFFER TEST" in x for x in _bl[:8]))
            ck(_okb, "/bars leads with the verdicts counted, then one line a test named by its section (never the "
                     "verdict line itself)" + ("" if _okb else " -- got %r" % (_bl[:6],)))
            ck(fits(_bt) and not any(tg_html_problems(c) for c in split_html(_bt)),
               "...in messages under Telegram's limit, each one Telegram-valid")
        finally:
            L.orders, L.hedges = _sv_o, _sv_g
            with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
                _fh.write(_led0)
            os.utime(_pl.LEDGER, (time.time() + 30, time.time() + 30))
            L.refresh()

        # ---- /bots /pin /forecaster /ladder, and /race's money windows -----
        # READ ONLY, BY CONSTRUCTION: the new code is scanned for any order,
        # cancel, transfer or process-control word. The words are assembled
        # from pieces so this check does not find itself.
        import inspect as _insp
        from phone.commands import race as _cmd_race, bots_page as _cmd_bots, bot_page as _cmd_bot, day as _cmd_day
        _newfns = (_bs, _nof, _cash, _ago, bs_window_line, _short, bs_running_lines, bs_setup_lines, bs_money_lines,
                   bs_open_lines, bs_cash_line, bs_last_lines, bs_activity_lines, bs_bot_text, bs_errors_line,
                   bs_all_text, _cmd_race.money_load, _cmd_race.money_lines, Ctx.bs_get, _cmd_bots.load,
                   _cmd_bots.render, _cmd_bot.page, _cmd_race.load, _cmd_race.render,
                   # 2026-10-18, the phone layout: every new reader and formatter
                   log_span, race_arms_scored, race_size_words, race_rule_words, race_rows, _cmd_day.staked,
                   _cmd_day.day_data, _cmd_day.day_lines, pct1, ret, tg_html_problems, split_html, bs_bot_html,
                   bs_all_html, bs_money_html, _funds_days_html, _funds_page, fmt_or_plain, _alerts.alert_loss_text,
                   alert_daily_text, cprint,
                   # v-tg-rebuild step 10: the router and the runtime's own code
                   _router, Phone)
        _nsrc = "\n".join(_insp.getsource(f) for f in _newfns)
        _bad = [w for w in (r"\b" + "PO" + r"ST\b", r"\b" + "DEL" + r"ETE\b", r"\b" + "PA" + r"TCH\b", r"\b" + "PU" + r"T\b",
                            "portfolio/" + "orders", "subaccounts/" + "transfer", "order" + "cli", "pin" + "take",
                            "url" + "open", "urllib" + r"\.request", r"do_" + "(stop|pause|start)", r"self\." + "control",
                            "Stop-" + "Process", r"\b" + "kill", "termin" + "ate", "sub" + "process", r"os\." + "remove")
                if re.search(w, _nsrc)]
        ck(not _bad and len(_nsrc) > 5000,
           "the new commands' code holds no order, cancel, transfer or process-control call (found: %s)" % _bad)
        _nb = len(_bs_asked)
        ck(_nb > 0 and all(q.get("subaccount") in _bsm.SUBS for _p, q in _bs_asked if _p in _bsm.POT_PATHS)
           and set(_p for _p, _q in _bs_asked) <= set(_bsm.PATHS),
           "every Kalshi read the phone caused (%d, all from /race above) is one of botstats' read paths, and "
           "every per-pot one names its subaccount -- with none, settlements mix every pot" % _nb)
        # the pin version: joined names and 'LIVE <date>' headers, and the SAME pick as botstats
        _vp = os.path.join(_bsdir, "VERSIONS.md")
        ck([v[0] for v in versions(_vp)] == ["v-ladder-settlefix", "v-keepalive-cleanroom", "v-forecaster-race1",
                                             "v-reopen98 + v-floor90", "v-race20"],
           "VERSIONS.md: a 'v-a + v-b' name and a 'LIVE <date>' header are read too")
        ck(live_version(_vp)[0] == "v-reopen98 + v-floor90" == _bsm.version_of("pin")[0]
           and live_version(_vp)[1] == calendar.timegm((2026, 9, 16, 12, 0, 0)),
           "/stats' pin version skips the ladder, the clean-room keep-alive and the forecaster and names "
           "v-reopen98 + v-floor90 -- the same entry botstats picks (it used to name v-keepalive-cleanroom)")
        _bsm.RESULTS = _bs_saved[0]
        try:
            _lv, _bv = live_version(VERSIONS_MD), _bsm.version_of("pin")
        finally:
            _bsm.RESULTS = _bsdir
        ck((_lv[0] if _lv else None) == (_bv[0] if _bv else None),
           "DRIFT: on the real VERSIONS.md the phone and botstats name the same pin version (%s / %s)"
           % (_lv[0] if _lv else None, _bv[0] if _bv else None))

        # /bots on the planted world
        bh_ = ph.handle(111, "/bots")
        b_ = P(bh_)
        ck(b_.split("\n")[1] == "🤖 ALL BOTS · Sep 16 11:00 AM ET", "/bots: header in ET")
        ck(b_.split("\n")[0] == "🔴 All bots today -$12.53 (-10.1% on $123.81 staked · -1.1% of all pots)",
           "/bots: today's money over every pot is the headline, with its return and its share of all pots")
        ck(fits(bh_) and not any(tg_html_problems(c) for c in split_html(bh_)), "/bots: Telegram-valid messages")
        # THE POT (2026-10-02), worked by hand. Now: main 1000 + open 29.10 + 19.60 = 1048.70; ladder
        # 15.10; forecaster 24.00; all 1087.80. TODAY: main settled -10.03, moved out 15.06 + 7.99 ->
        # 1048.70 + 10.03 + 23.05 = 1081.78 (pin -10.40 = -0.96%, race +0.37 = +0.03%); forecaster
        # 24 + 2.54 - 7.99 = 18.55 at midnight, + the 7.99 moved in = 26.54 (-9.6%); ladder ~0 at
        # midnight + 15.06 moved in = 15.06 (+0.28%); all 1087.80 + 12.528 = 1100.33 (-1.1%).
        # YESTERDAY: main 1048.70 + 14.00 - 76.95 = 985.75 at the start + 98 deposit + 2 back = 1085.75
        # (pin +0.05%, other -0.42%); forecaster 24 + 1.9928 - 5.99 = 20.00 (+2.7%); all 1103.75 (-0.31%).
        # v-tg-active (2026-10-30): in this world the ladder is stopped by its stop file and the weather dip-seller, the FX
        # taker and the jump band do not run -- none is named; the ladder's +$0.04 sits on the one 'earlier' entry
        ck("Today: -$12.53 on $123.81 put in (-10.1%) = -1.1% of all pots ($1,100.33); 5 markets, 3 won, 2 lost\n"
           "  pin -$10.40 (-0.96%) | race +$0.37 (+0.03%) | forecaster -$2.54 (-9.6%) | earlier +$0.04"
           in b_,
           "/bots TODAY is all four pots: -10.40 + 0.37 - 2.54 + 0.042 = -12.53 on 99.80 + 19.60 + 2.45 + 1.958 "
           "put in = -1.1% of the $1,100.33 all pots held at midnight; each running bot's share of ITS OWN pot listed, "
           "the stopped ladder's money on the 'earlier' entry (no pot %%: earlier bots' pots differ)")
        ck("Yesterday: -$3.42 on $36.32 put in (-9.4%) = -0.31% of all pots ($1,103.75); 3 markets, 2 won, 1 lost\n"
           "  pin +$0.54 (+0.05%) | race none | forecaster +$0.55 (+2.7%) | other -$4.51 (-0.42%)"
           in b_ and "ladder" not in b_.lower().replace("/ladder", "") and "weather" not in b_.lower()
           and "fx" not in b_.lower() and "jump" not in b_.lower(),
           "YESTERDAY: the SOL and XRP markets that closed before midnight ET count on Sep 15 though Kalshi "
           "settled them on the 16th (UTC); the oil market that is no bot's is shown as `other`; the $98 "
           "deposit made during the day is part of the pot")
        ck("All time: -$15.95 on $160.13 put in (-10.0%) = -1.4" in b_
           and "% on money put in ($1,103.75); 8 markets, 5 won, 3 lost" in b_,
           "ALL TIME: every settlement in every pot, each once; as a share of the $1,103.75 deposited after fees")
        ck("The % after '=' or in brackets = share of the pot when the window began" in b_
           and "Kalshi's books explain" not in b_,
           "/bots says once what the percentages are; every planted pot reconciles, so no pot warning")
        ck("  Sep 16: -$12.53, 5 markets (pin -$10.40, race +$0.37, forecaster -$2.54, earlier +$0.04)" in b_
           and "  Sep 15: -$3.42, 3 markets (pin +$0.54, forecaster +$0.55, other -$4.51)" in b_
           and "Sep 14" not in b_,
           "by day, with each bot's part; no line for the days before anything settled")
        ck("Cash: main account (pin bot + coin race) $1,000.00, forecaster $24.00, earlier bots' pots $15.10 -- all pots "
           "$1,039.10." in b_ and "counts the main account only (pin bot + coin race)" in b_,
           "the cash of every pot -- a stopped bot's pot on one 'earlier bots' pots' entry, so it still adds up -- and HIS "
           "QUESTION answered: the main page counts the main account only")
        ck("Kalshi's own app shows the MAIN account only. The $39.10 sitting in the other pots" in b_,
           "/bots says why Kalshi's app reads lower than all pots: the bot pots' cash (24.00 + 15.10) is outside it")
        # 2026-10-26 (operator: "a green emoji for a negative bank makes no sense"): a card's dot is the bot's money
        # TODAY -- the pin bot is running and DOWN, so red -- and whether it runs is in words on the line under it
        ck("🔴 PIN BOT · main account · /pin\nrunning since Sep 16 7:59 AM ET · v-reopen98 + v-floor90\ntoday -$10.40 "
           "(-10.4% on bets · -0.96% of bank) · 7 days -$9.86 (-7.6% on bets · -0.93% of bank) · all time -$9.86 "
           "(-7.6% on bets · -0.93% of bank) · open: 1 ($29.10 at risk)" in b_,
           "a card a bot: its dot is its money today (pin is running and down: red), running since (ET) in words, "
           "version, money with its share of the pot, open bets, its command")
        ck("LADDER ·" not in b_ and "STOPPED by its stop file" not in b_
           and "🔴 FORECASTER · subaccount 2 · /fc\nrunning since Sep 16 8:34 AM ET · v-forecaster-race1" in b_
           and "🟢 COIN RACE · main account · /race\nrunning since Sep 15 10:49 PM ET · v-race20" in b_
           and "⏸ EARLIER BOTS (paused or stopped, not listed): today +$0.04 (+2.1% on bets), 7 days +$0.04 (+2.1% on "
               "bets), all time +$0.04 on 1 market -- in every total above." in b_,
           "the paper race arm is not the live race (the race runs: its card); the ladder with a stop file gets NO card "
           "(v-tg-active, 2026-10-30) -- its money is one 'earlier bots' line, in every total; the forecaster runs and is "
           "down (red)")
        ck("WEATHER" not in b_ and "FX TAKER" not in b_ and "JUMP BAND" not in b_ and "NOT RUNNING" not in b_
           and "🟠" not in b_ and "A bot's dot = its money today" in b_
           and "One bot in full: /pin /race /fc · every account's cash: /funds" in b_,
           "bots that do not run (the weather dip-seller, the FX taker, the jump band) get no card and no command; the "
           "legend lists only the running bots' commands: %r" % b_[-300:])
        ck("🔴 NOT ANY BOT'S (main account): all time -$4.51 on 1 market; worst -$4.51 WTI 2:00 PM (Sep 15)." in b_,
           "a main-account market that is no bot's is shown on its own, never folded into pin; its dot is its money")
        _r0 = {"alive": True, "started_et": "Sep 16 7:59 AM ET", "halted": None, "stop_flag": False}
        ck(money_dot({"ok": True, "today": {"markets": 2, "money": -10.4}}) == "🔴"
           and money_dot({"ok": True, "today": {"markets": 1, "money": 0.9}}) == "🟢"
           and money_dot({"ok": True, "today": {"markets": 0, "money": 0.0}}) == "⚪"
           and money_dot({"ok": False, "today": None}) == "❔"
           and run_words(_r0) == "running since Sep 16 7:59 AM ET"
           and run_words(dict(_r0, halted={"t_et": "Sep 16 9:00 AM ET", "what": "day_stop", "why": ""}))
           == "🛑 <b>HALTED Sep 16 9:00 AM ET</b> -- no new bets (running since Sep 16 7:59 AM ET)"
           and run_words(dict(_r0, alive=False, stop_flag=True, stop_flag_et="Sep 10 5:47 AM ET"))
           == "⏸ <b>STOPPED</b> by its stop file (Sep 10 5:47 AM ET)"
           and run_words(dict(_r0, alive=False, log_last_et="Sep 16 10:58 AM ET"))
           == "⚠️ <b>NOT RUNNING</b> since about Sep 16 10:58 AM ET (its log's last write) -- no stop file, it stopped on its own"
           and run_words(dict(_r0, alive=None)).startswith("❔ <b>running? could not tell</b>")
           and run_words(dict(_r0, stop_flag=True)).endswith("its stop file is set: it stops at its next check")
           and [state_icon(dict(_r0, **x)) for x in ({}, {"halted": {"t_et": "x"}}, {"alive": False, "stop_flag": True},
                                                     {"alive": False}, {"alive": None})] == ["▶️", "🛑", "⏸", "⚠️", "❔"],
           "a dot is money (up / down / nothing / unread); the running state is words -- running since, HALTED, STOPPED, "
           "NOT RUNNING since its log's last write, could not tell -- and an icon that is not a money colour")
        # /pin
        ph_ = ph.handle(111, "/pin")
        p_ = P(ph_)
        ck(fits(ph_) and len(split_html(ph_)) == 1 and not tg_html_problems(ph_),
           "/pin fits one Telegram message on this world (%d chars), Telegram-valid" % len(ph_))
        ck(p_.split("\n")[0] == "🔴 Pin bot today -$10.40 (-10.4% on $99.80 staked · -0.96% of its bank)",
           "/pin: today's money, its return on what the bets cost and its share of the pot lead the page")
        ck(p_.split("\n")[1] == "▶️ PIN BOT -- 15-minute coin markets + hourly Bitcoin" and "🟢" not in p_.split("\n")[1],
           "/pin (10-26): under the red money headline the running state is an icon that is not a money colour")
        for _want, _why in (
                ("Pot: main account, shared with the coin race.", "its pot, and who shares it"),
                ("Running: YES, pid 3882400, since Sep 16 7:59 AM ET.", "running, pid, since when in ET"),
                ("Version: v-reopen98 + v-floor90, live since Sep 16 8:00 AM ET.", "its version from VERSIONS.md"),
                ("Settings: halts after 2 losing bets.", "its settings from its command line"),
                ("Keep-alive: watch_bot.ps1 restarts it", "what restarts it"),
                ("Money (Kalshi settlements, main account, read Sep 16 11:00 AM ET;", "where the money comes from"),
                ("Today: -$10.40 on $99.80 put in (-10.4%) = -0.96% of its bank ($1,081.78); 2 markets, 1 won, 1 lost",
                 "today: the both-sides ETH market pays its winning YES side (-$11.30, not -$51.30); -0.96% of the "
                 "main pot at midnight ET"),
                ("Yesterday: +$0.54 on $29.40 put in (+1.8%) = +0.05% of its bank ($1,085.75); 1 market, 1 won, 0 lost",
                 "yesterday"),
                ("Last 7 days: -$9.86 on $129.20 put in (-7.6%) = -0.93% of its bank ($1,062.70); 3 markets, 2 won, "
                 "1 lost; 1 day up, 1 down", "7 days, with days up and down"),
                ("All time (since Sep 15): -$9.86 on $129.20 put in (-7.6%) = -0.93% on money put in ($1,062.70)",
                 "all time, since its first day, of the main account's money put in (1103.75 deposited - 41.05 "
                 "moved to the bot pots)"),
                ("% of its bank = of what the pot held when the window began (cash + open bets, + any money moved in "
                 "during it); all time = of the money put in -- the pot is the whole main account, shared with the "
                 "coin race.", "what the percentages are, and that pin's pot is shared"),
                ("Worst market today: -$11.30 ETH 9:45 AM; best +$0.90 BTC 10:30 AM.", "worst and best today"),
                ("Worst market all time: -$11.30 ETH 9:45 AM (Sep 16); best +$0.90 BTC 10:30 AM (Sep 16).",
                 "worst and best all time, with the day"),
                ("Best day +$0.54 (Sep 15), worst day -$10.40 (Sep 16), over 2 days with a settlement.",
                 "best and worst day"),
                ("Fees all time: $0.66", "fees: 0.10 + 0.50 + 0.06"),
                ("Bought both sides (hedged): 1 market all time.", "hedged markets"),
                ("Open now: 1 bet, $29.10 at risk:\n  BTC 11:15 AM NO x30, $29.10 at risk",
                 "open bets from Kalshi: the race's SOL leg in the same pot is NOT pin's"),
                ("Cash: $1,000.00 -- shared: the coin race's cash sits in the same pot.", "cash, said to be shared"),
                ("  Sep 16 ETH 9:45 AM BOTH SIDES x80: -$11.30 on $50.80 put in", "the last markets, newest first"),
                ("Today, its own log: no log file found.", "no log is said, not shown as zero orders"),
                ("More on pin: /stats", "and where the rest of pin's numbers are")):
            ck(_want in p_, "/pin: " + _why)
        ck(p_.index("BTC 10:30 AM NO x50: +$0.90") < p_.index("ETH 9:45 AM BOTH SIDES") < p_.index("SOL 11:45 PM YES x30"),
           "/pin: last settled newest first")
        # /forecaster and /fc
        f_ = P(ph.handle(111, "/forecaster"))
        ck(P(ph.handle(111, "/fc")) == f_, "/fc is /forecaster")
        for _want, _why in (
                ("FORECASTER -- buys the 15-minute coin side its own forecast calls decided", "the forecaster's own page"),
                ("Pot: subaccount 2.", "its own pot"),
                ("Running: YES, pid 4196192, since Sep 16 8:34 AM ET.", "running"),
                ("Its log last wrote Sep 16 10:59 AM ET (30 s ago).", "how fresh its log is"),
                ("Version: v-forecaster-race1, live since Sep 16 8:35 AM ET.", "its version, not the keep-alive entry"),
                ("Settings: variant race1_98; 5% of paper size; up to 5 a side, 20 a quarter-hour; at most $22.00 in "
                 "play; buys 75c to 98.5c; stops the day at -$12.00, the run at -$20.00.", "its rails from its start record"),
                ("Today: -$2.54 on $2.45 put in (-103.7%) = -9.6% of its bank ($26.54); 1 market, 0 won, 1 lost",
                 "subaccount 2's money today: -$2.54 is -9.6% of the $26.54 it had (18.55 at midnight + 7.99 moved in)"),
                ("Yesterday: +$0.55 on $2.42 put in (+22.6%) = +2.7% of its bank ($20.00); 1 market, 1 won, 0 lost",
                 "and yesterday"),
                ("= -7.7% on money put in ($25.99)", "all time: of the 20 - 2 + 7.99 moved into its pot"),
                ("Cash: $24.00 -- its own pot (subaccount 2).", "its own cash"),
                ("1 order sent, 1 filled (5 contracts).", "what its log did today"),
                ("  Refused 1 time: order already in flight 1.", "its refusals in words")):
            ck(_want in f_, "/forecaster: " + _why)
        # /ladder: stopped by its stop file, so the command says so and nothing else (v-tg-active); its page, built
        # directly, still says why it is not running
        lh_ = P(ph.handle(111, "/ladder"))
        ck(lh_.startswith("⏸ Ladder is not running now (its stop file is set)") and "comes back by itself" in lh_
           and "Today:" not in lh_ and lh_.endswith("The bots running now: /pin /race /fc"),
           "/ladder while its stop file is set: one short answer -- not running, why, that it comes back by itself -- "
           "and the bots that do run: %r" % lh_)
        l_ = P(_cmdrun(ph, "/ladder"))
        ck("⏸ Running: NO -- stopped by its stop file (set " in l_ and ': "stood down by the operator".' in l_
           and "stopped on its own" not in l_ and l_.split("\n")[0].startswith("🟢 Ladder today +$0.04")
           and l_.split("\n")[1].startswith("⏸ LADDER -- "),
           "/ladder: NOT running, and WHY -- its stop file, with what the file says, said loud under a headline whose "
           "dot is its money (up: green)")
        ck("Today: +$0.04 on $1.96 put in (+2.1%) = +0.28% of its bank ($15.06); 1 market, 1 won, 0 lost" in l_
           and "Cash: $15.10 -- its own pot (subaccount 1)." in l_
           and "Version: v-ladder-settlefix, live since Sep 16 9:16 AM ET." in l_,
           "/ladder: subaccount 1's money, cash and version")
        # /race keeps everything it said and adds the windows
        rh_ = ph.handle(111, "/race")
        r_ = P(rh_)
        ck("COIN RACE · " in r_ and "Last 10 races (Kalshi's books)" in r_ and "Paper race arms running:" in r_,
           "/race still says everything it said before")
        ck("Money (Kalshi settlements, main account, read Sep 16 11:00 AM ET; a leg counts on the ET day it closed)"
           in r_ and "Today: +$0.37 on $19.60 put in (+1.9%) = +0.03% of its bank ($1,081.78); 1 leg, 1 won, 0 lost"
           in r_ and "All time (since Sep 16): +$0.37 on $19.60 put in (+1.9%) = +0.03% on money put in ($1,062.70); "
           "1 leg, 1 won, 0 lost" in r_,
           "/race adds the race's money by window, legs not races, each a share of the main pot it shares with pin")
        ck(r_.index("Paper race arms running:") < r_.index("Money (Kalshi settlements"),
           "...AFTER what /race already said")
        ck("Version: v-race20, live since Sep 15 10:50 PM ET." in r_
           and "Keep-alive: boot_all.ps1 (every 10 min) restarts it unless the stop file is there." in r_
           and "nothing restarts it" not in r_
           and "Open now: 1 leg, $19.60 at risk:\n  race SOL 11:00 AM YES x20, $19.60 at risk" in r_
           and "Cash: $1,000.00 -- shared: the pin bot's cash sits in the same pot." in r_,
           "/race: its version, its keep-alive (boot_all.ps1 has restarted the live race since 09-30, so 'nothing "
           "restarts it' is no longer said), the leg Kalshi holds open, the shared cash")
        ck("Settings: " not in r_ and "penny" not in r_.lower().replace("pinracepenny", ""),
           "/race: botstats' command-line Settings line (the 20 / $40 it STARTS from) is not shown -- 'How it bets' "
           "reads the size from the race's own log -- and nothing calls it a penny bot")
        ck(fits(rh_) and not any(tg_html_problems(c) for c in split_html(rh_)), "/race: Telegram-valid messages")
        ck(all(q.get("subaccount") in _bsm.SUBS for _p, q in _bs_asked if _p in _bsm.POT_PATHS)
           and set(_p for _p, _q in _bs_asked) <= set(_bsm.PATHS),
           "still every per-pot Kalshi read names its subaccount and every read is a read path")

        # v-tg-active (2026-10-30, the operator: "remove the paused and removed until they're added back, and show the
        # details for the new one in any relevant commands"): the server's shape -- the coin race RUNS with its stop file
        # set, the ladder is stopped, the jump band runs live beside its paper arm (which is never the bot)
        with open(os.path.join(_bsdir, "jumpband-live.jsonl"), "w", encoding="utf-8") as _fh:
            _fh.write(json.dumps({"t": "2026-09-16T08:13:26.86Z", "kind": "start", "pid": 2972, "live": True, "paper": False,
                                  "subaccount": 3, "max_contracts": 5, "max_cost": 20.0, "stop_line": -25.0,
                                  "day_stop": -15.0, "series": ["KXBNB15M", "KXHYPE15M", "KXZEC15M", "KXNEAR15M"],
                                  "k": 2.0, "lo": 0.7, "hi": 0.9, "tau": [10, 60]}) + "\n")
            _fh.write(json.dumps({"t": "2026-09-16T14:44:29Z", "kind": "trigger", "outcome": "buy"}) + "\n")
            _fh.write(json.dumps({"t": "2026-09-16T14:44:29.05Z", "kind": "order", "filled": 5.0, "status": 201}) + "\n")
            _fh.write(json.dumps({"t": "2026-09-16T14:44:29.06Z", "kind": "fill", "ticker": "KXBNB15M-26SEP161045-45",
                                  "side": "no", "qty": 5.0, "price": 0.88, "cost": 4.4, "fee": 0.04}) + "\n")
        _jbp = [(2972, "2026-09-16T08:13:20Z", r"C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --live "
                                               r"--subaccount 3 --max-contracts 5 --minutes 20160"),
                (4276, "2026-09-16T08:00:00Z", r"C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --minutes 20160")]
        with open(os.path.join(_bsdir, _bsm.SPEC["race"]["stop"]), "w", encoding="utf-8") as _fh:
            _fh.write("paused by the operator")
        ph.bs_procs = _bs_procs + _jbp
        ck(ph.active() == ("pin", "forecaster", "jumpband"),
           "ACTIVE on the server's shape: the pin bot, the forecaster and the jump band -- not the race (running, stop "
           "file set), not the ladder (stop file), not the paper arm: %s" % (ph.active(),))
        _hp = P(ph.handle(111, "/help"))
        ck("/jb (or /jumpband) — the jump band" in _hp and "/fc" in _hp and "/race" not in _hp and "/racestats" not in _hp
           and "/ladder" not in _hp and "/weather" not in _hp and "/fx" not in _hp and "coin race apart" not in _hp
           and P(help_text(("pin", "race"))).count("/race") == 2 and not tg_html_problems(ph.handle(111, "/help"))
           and fits(ph.handle(111, "/help")),
           "/help lists only the running bots' commands (the jump band's included); the paused race, the stopped ladder "
           "and the bots not running are left out")
        _rh = P(ph.handle(111, "/race"))
        ck(_rh.startswith("⏸ Coin race is not running now (its stop file is set)") and "Last 10 races" not in _rh
           and P(ph.handle(111, "/racestats")) == _rh and P(ph.handle(111, "/fx")).startswith(
               "⏸ FX taker is not running now (no live copy of it is running)"),
           "/race and /racestats while the race's stop file is set: one short answer, no page; /fx (not running) the same")
        _jh = ph.handle(111, "/jb")
        _jp = P(_jh)
        for _want, _why in (
                ("JUMP BAND -- buys the 70-90c favourite on BNB/HYPE/ZEC/NEAR when the price jumps 2+ standard deviations "
                 "in the last minute, 5 contracts, holds to the end", "its own page, in plain words"),
                ("Pot: subaccount 3.", "its own pot (the weather dip-seller, stopped, is not named)"),
                ("Running: YES, pid 2972, since Sep 16 4:13 AM ET.", "the --live copy, not the paper arm"),
                ("up to 5 contracts a buy, at most $20.00 an order; buys the favourite at 70c-90c when the price moves 2+ "
                 "standard deviations in its last minute, 10-60 s before the close; coins BNB HYPE ZEC NEAR; stops the "
                 "day at -$15.00 settled; stands down for good at -$25.00 since it went live", "its settings, from its start record"),
                ("Keep-alive: NONE -- if it dies, nothing restarts it.", "it is not in boot_all, said plainly"),
                ("Today, its own log (what it did, not money): 1 order sent, 1 filled (5 contracts).", "what its log did today"),
                ("1 price jump judged today", "its triggers"),
                ("its pot (subaccount 3, crypto pool): /funds", "where its cash is")):
            ck(_want in _jp, "/jb: " + _why + ": %r" % _jp[:200])
        ck(P(ph.handle(111, "/jumpband")) == _jp and fits(_jh) and not tg_html_problems(_jh)
           and "weather" not in _jp.lower(), "/jumpband is /jb; Telegram-valid; no word of the weather dip-seller")
        _bj = P(ph.handle(111, "/bots"))
        ck("JUMP BAND · subaccount 3 · /jb\nrunning since Sep 16 4:13 AM ET" in _bj and "COIN RACE" not in _bj
           and "LADDER ·" not in _bj and "⏸ EARLIER BOTS (paused or stopped, not listed): today +$0.41" in _bj
           and "One bot in full: /pin /fc /jb ·" in _bj and "race +$" not in _bj and "| earlier +$0.41" in _bj
           and "Cash: main account (pin bot) $1,000.00, forecaster $24.00, jump band $0.00, earlier bots' pots $15.10 -- "
               "all pots $1,039.10." in _bj,
           "/bots: the jump band's card and command; the race (paused) and the ladder (stopped) are gone, their money on "
           "the one 'earlier bots' line (+0.37 + 0.04), every total and the cash still adding up: %r" % _bj[-900:])
        _s2 = P(ph.handle(111, "/status"))
        ck("Main account $500.00 (pin bot)" in _s2 and "coin race" not in _s2 and "Main account today" in _s2,
           "/status with the race paused names the main account's pin bot only")
        _fe = P(ph.handle(111, "/features"))
        ck("Jump band (LIVE, subaccount 3)" in _fe and "started by hand on the server" in _fe
           and "settings: up to 5 contracts a buy" in _fe and "Coin race (LIVE" not in _fe and "Penny ladder (LIVE" not in _fe
           and "Weather dip-seller" not in _fe,
           "/features: the jump band's block (started by hand, its settings), no block for a paused or stopped money bot")
        os.remove(os.path.join(_bsdir, _bsm.SPEC["race"]["stop"]))
        _hp2 = P(ph.handle(111, "/help"))
        ck(ph.active() == ("pin", "race", "forecaster", "jumpband") and "/race" in _hp2 and "/racestats" in _hp2
           and "COIN RACE · " in P(ph.handle(111, "/race")) and "COIN RACE · main account · /race" in P(ph.handle(111, "/bots")),
           "the race's stop file removed (its process still --live): it is back in /help, /race and /bots, no code change")
        ph.bs_procs = _bs_procs
        os.remove(os.path.join(_bsdir, "jumpband-live.jsonl"))

        # /weather and /wx (2026-10-04): the weather dip-seller, subaccount 3, cash in POOL 0
        _wxdir = _bs_sandbox("botstats-weather")
        _bs_mode["m"] = "weather"
        # v-tg-active (2026-10-30): this world is subaccount 3 as it was 10-04..10-29 (the weather pot, pool 0); since the
        # jump band the number 3 trades in pool 2. The world runs on the old settings, restored below.
        _wx_pool = (dict(_bsm.SUB_POOL), dict(_bsm.POT_POOL_ONLY))
        _bsm.SUB_POOL["3"] = 0
        _bsm.POT_POOL_ONLY.pop("3", None)
        with open(os.path.join(_wxdir, "dipsell-live-orders.jsonl"), "w", encoding="utf-8") as _fh:
            _fh.write(json.dumps({"t": "2026-09-15T07:56:53Z", "ev": "start", "pid": 3955508, "subaccount": 3,
                                  "live": True, "start_pot": 50.0,
                                  "rails": {"contracts": 2, "max_open": 5, "window_s": 10800, "day_stop_frac": 0.25,
                                            "kill_after": 60, "max_fills": 100, "max_days": 14, "pool": 0},
                                  "trigger": {"drop_c": 10.0, "hours_left": [6.0, 12.0]}}) + "\n")
        with open(os.path.join(_wxdir, "VERSIONS.md"), "w", encoding="utf-8") as _fh:
            _fh.write("# Versions\n\n# v-dipsell-live -- LIVE 2026-09-15 07:56:53Z (pid 3955508, subaccount 3 pool 0, "
                      "$50): weather\n# v-reopen98 + v-floor90 -- 2026-09-16 12:00:17Z (pid 3882400) -- LIVE: 98c\n")
        _wx_n0 = len(_bs_asked)
        ph.bs_procs = _bs_procs + [(3955508, "2026-09-15T07:56:50Z", r"C:\Python314\python.exe -u "
                                    r"research\sweep\dipsell_live.py --subaccount 3 --live --minutes 21600")]
        w_ = P(ph.handle(111, "/weather"))
        ck(P(ph.handle(111, "/wx")) == w_, "/wx is /weather")
        for _want, _why in (
                ("WEATHER DIP-SELLER -- sells YES on a daily-high temperature bracket", "its own page"),
                ("Pot: subaccount 3.", "its own pot, shared with no bot"),
                ("Running: YES, pid 3955508, since Sep 15 3:56 AM ET.", "running: the --live dipsell_live.py"),
                ("Version: v-dipsell-live, live since Sep 15 3:56 AM ET.", "its VERSIONS.md entry"),
                ("2 contracts an order, one order a market", "its rails from its start record"),
                ("Keep-alive: boot_all.ps1 (every 10 min) restarts it unless the stop file is there.", "its keep-alive"),
                ("Yesterday: +$0.80 on $1.20 put in (+66.7%) = +1.6% of its bank ($50.00); 1 market, 1 won, 0 lost",
                 "yesterday's bracket, +1.6% of the $50 moved into its pot that day"),
                ("Open now: 1 bet, $1.10 at risk:\n  MIA high B90.5 NO x2, $1.10 at risk", "the bracket Kalshi holds open"),
                ("Cash: $49.70 -- its own pot (subaccount 3).", "its cash, read from POOL 0")):
            ck(_want in w_, "/weather: " + _why)
        ck(any(_p == "/portfolio/balance" and _q == {"subaccount": "3", "exchange_index": 0}
               for _p, _q in _bs_asked[_wx_n0:])
           and not any(_p == "/portfolio/balance" and _q.get("subaccount") == "3" and _q.get("exchange_index") != 0
                       for _p, _q in _bs_asked[_wx_n0:]),         # before this world: pool 2, the jump band's (10-30)
           "/weather: its cash is read from subaccount 3 in pool 0, never pool 2 (where Kalshi says $0.00)")
        wb_ = P(ph.handle(111, "/bots"))
        ck("WEATHER DIP-SELLER · subaccount 3 · /weather\nrunning since Sep 15 3:56 AM ET · v-dipsell-live" in wb_
           and "/weather" in wb_ and "| weather none" in wb_ and "weather +$0.80 (+1.6%)" in wb_
           and "forecaster $24.00, weather $49.70, earlier bots' pots $15.10 -- all pots $1,088.80." in wb_
           and "The $88.80 sitting in the other pots" in wb_ and "One bot in full: /pin /race /fc /weather ·" in wb_
           and "JUMP BAND" not in wb_ and "FX TAKER" not in wb_,
           "/bots: the weather bot's line while it runs, its share of yesterday, its cash in the all-pots cash (1000 + "
           "24 + 49.70 + the stopped ladder's 15.10 on the 'earlier bots' pots' entry, each pot once -- the empty pool-0 "
           "rows of subaccounts 1 and 2 add $0), and that Kalshi's app does not show it")
        ck(live_version(os.path.join(_wxdir, "VERSIONS.md"))[0] == "v-reopen98 + v-floor90" == _bsm.version_of("pin")[0],
           "/stats' pin version skips the weather entry, as botstats does")
        ph.bs_procs = _bs_procs
        _bsm.SUB_POOL.clear()
        _bsm.SUB_POOL.update(_wx_pool[0])
        _bsm.POT_POOL_ONLY.clear()
        _bsm.POT_POOL_ONLY.update(_wx_pool[1])

        # NULL (2026-10-02): the account's books unreadable -> the money stands, NO pot %, and the reason
        _bs_sandbox("botstats-noledger")
        _bs_mode["m"] = "noledger"
        n_, nb_ = P(ph.handle(111, "/pin")), P(ph.handle(111, "/bots"))
        ck("Today: -$10.40 on $99.80 put in (-10.4%); 2 markets, 1 won, 1 lost" in n_
           and "of its bank (" not in n_ and "on money put in" not in n_ and "of its bank)" not in n_
           and "% of its bank: not shown -- transfers read failed (HTTP 404)." in n_
           and "Today: -$12.53 on $123.81 put in (-10.1%); 5 markets, 3 won, 2 lost\n"
               "  pin -$10.40 | race +$0.37 | forecaster -$2.54 | earlier +$0.04\n" in nb_   # v-tg-active: ladder stopped
           and "today -$10.40 (-10.4% on bets) · 7 days -$9.86 (-7.6% on bets) · all time -$9.86 (-7.6% on bets) ·" in nb_
           and "% of the pots: not shown -- main account: transfers read failed (HTTP 404)." in nb_,
           "NULL: the deposit/transfer listings unreadable -> every dollar figure still shown, NO percentage of "
           "any pot anywhere (never a guessed base), and the reason said once")

        # EMPTY: nothing settled, nothing open, nothing running, no logs
        _bs_sandbox("botstats-empty")
        _bs_mode["m"], ph.bs_procs = "empty", []
        e_, eb_ = P(ph.handle(111, "/pin")), P(ph.handle(111, "/bots"))
        ck("Today: nothing settled yet" in e_ and "All time: nothing settled yet" in e_
           and "Nothing settled yet on Kalshi for this bot." in e_ and "Open now: none." in e_
           and "Running: NO, and there is no stop file -- it stopped on its own." in e_
           and "Version: no entry for it in VERSIONS.md." in e_ and "+$" not in e_ and "-$" not in e_,
           "EMPTY /pin: nothing settled YET, nothing open, not running and why -- no gain or loss invented")
        ck("Nothing settled yet in any pot." in eb_ and "today nothing yet · 7 days nothing yet · all time nothing yet"
           in eb_ and "+$" not in eb_ and "-$" not in eb_ and "By day:" not in eb_ and "By day (all pots)" not in eb_,
           "EMPTY /bots: says nothing has settled yet, no gain or loss, no empty day list")
        ck(P(ph.handle(111, "/losses")) == "No losing markets in any pot (0 settled).",
           "EMPTY /losses: no losing market in any pot, said plainly: %r" % P(ph.handle(111, "/losses")))
        # DOWN: Kalshi refuses and the process list cannot be read -- unknown, never $0 or 'not running'
        _bs_sandbox("botstats-down")
        _bs_mode["m"], ph.bs_procs = "down", (lambda: None)
        d_, db_ = P(ph.handle(111, "/pin")), P(ph.handle(111, "/bots"))
        ck("MONEY: COULD NOT READ KALSHI (settlements read failed (HTTP 401))" in d_
           and "Running: COULD NOT TELL" in d_ and "Open now: COULD NOT READ" in d_
           and "Cash: COULD NOT READ" in d_ and "$0.00" not in d_ and "nothing settled" not in d_,
           "DOWN /pin: a failed read is said as a failure -- never $0, never 'nothing settled', never 'not running'")
        ck("Today: unknown -- Kalshi could not be read" in db_ and "Last 7 days: unknown" in db_
           # v-tg-active: the process table unreadable (and no stop file in this sandbox), every bot is shown -- never
           # hidden on a failed read
           and "PARTIAL: these totals leave out pin, race, forecaster, ladder, weather, fx, jumpband, other" in db_
           and "running? could not tell" in db_ and "money: COULD NOT READ KALSHI" in db_
           and "money: settlements read failed (HTTP 401): forecaster, fx, jumpband, ladder, pin, race, weather" in db_
           and "JUMP BAND · subaccount 3 · /jb" in db_
           and "nothing settled" not in db_ and "Nothing settled" not in db_,
           "DOWN /bots: every total is 'unknown', the missing pots are named, each error said once")
        _lo = P(ph.handle(111, "/losses"))
        ck("every bot" not in _lo and "No losing markets" not in _lo and (_lo == "No losing closes." or "losing closes" in _lo),
           "DOWN /losses: no pot readable -> the main account's own ledger (never 'no losing markets'): %r" % _lo[:120])
        # BROKEN botstats: those commands say so; /race still answers
        _sv_b, _sv_a = _bsm.bot, _bsm.all_bots

        def _boom(*a, **k):
            raise RuntimeError("planted botstats failure")
        _bsm.bot = _bsm.all_bots = _boom
        _sv_log = LOG
        globals()["LOG"] = os.path.join(td, "pinphone.log")    # its planted tracebacks stay out of the real log
        try:
            ck(ph.handle(111, "/pin").startswith("Could not build /pin: planted botstats failure")
               and ph.handle(111, "/bots").startswith("Could not build /bots: planted botstats failure"),
               "a botstats failure is said by the command that hit it")
            _rb = P(ph.handle(111, "/race"))
            ck("Last 10 races (Kalshi's books)" in _rb
               and "Money by window: could not build it (planted botstats failure)." in _rb,
               "...and /race still gives everything it gave before, with the windows' failure said")
        finally:
            _bsm.bot, _bsm.all_bots = _sv_b, _sv_a
            globals()["LOG"] = _sv_log
        ck(all(c in HELP_TEXT for c in ("/bots", "/pin", "/forecaster", "/fc", "/ladder", "/weather", "/wx", "/fx")),
           "/bots /pin /forecaster /fc /ladder /weather /wx /fx are in /help")
        # the FX taker everywhere a bot is named (operator 10-26: "there's nothing for fx in the commands list ... Make
        # sure it's fully implemented"): its two pots by name, each pot's cash, /bots' pointer, /features' roster
        _fxb = {"subaccount": 5, "subaccounts": [5, 4]}
        _fxc = bs_cash_line({"ok": True, "dollars": 184.27, "by_sub": {"5": 123.30, "4": 60.97},
                             "note": "its own pots (subaccount 5 + subaccount 4)"})
        ck(_pot_words(_fxb) == "subaccount 5 + subaccount 4" and _pot_words({"subaccount": 1, "subaccounts": [1]}) == "subaccount 1"
           and _fxc == "Cash: $184.27 (subaccount 5 $123.30, subaccount 4 $60.97) -- its own pots (subaccount 5 + subaccount 4)."
           and "/fx" in BOT_CMDS and BOT_CMD_OF["fx"] == "/fx"
           and "One bot in full: /pin /race /fc /ladder /weather /fx" in "\n".join(bs_all_html(ph.ctx().bs_get("all")))
           and any(r[0] == "fxtake_live.py" and "subaccounts 5 + 4" in r[3] for r in FEATURES)
           and FUNDS_SIZE_BOTS.get(4) == ("fx",) and FUNDS_SIZE_BOTS.get(5) == ("fx",),
           "the FX taker: both pots named (5 + 4), each pot's cash on its card, /fx on /bots' pointer line, a /features "
           "row, a bet size under both accounts in /funds: %r" % _fxc)
        # ---- /features (2026-10-22): the settings come from boot_all.ps1's text, the rails from ladder_live.py's
        _ps = ('$repo = "C:\\kals-repo"\n$res = "$repo\\results"\n'
               '$live = @("-u", "$repo\\research\\pinrun.py", "--size", "20", "--minutes", "4320",\n'
               '          "--loss-abort", "-60.00", "--sweep-depth")\n'
               '@{ n = "arm-b-control"; x = $band + @("--early-tau", "45") + $m15 },\n'
               '@{ n = "arm-pin0.97"; x = @("--pin", "0.97") }\n'
               'if ($false -and -not (RunningPy \'*cmdlive.py*\')) {\n'
               '    Start-Process -FilePath $py -ArgumentList @("-u", "$repo\\research\\cmdlive.py", "--live", "--signoff", '
               '\'"commodity penny test"\', "--size", "20") -WorkingDirectory $repo\n}\n'
               'if (-not (RunningPy \'*pinledgerd.py*\')) {\n'
               '    Start-Process -FilePath $py -ArgumentList @("-u", "$repo\\research\\pinledgerd.py") `\n'
               '        -WorkingDirectory $repo\n}\n'
               '$cleanroom = @(\n'
               '    @{ n = "ladder_live (LIVE, subaccount 1)"; like = "*ladder_live.py*--live*"; unlike = @("*a*", "*b*"); stop = "$res\\ladder-live.stop";\n'
               '       a = @("-u", "research\\cleanroom\\ladder_live.py", "--subaccount", "1", "--live", "--auto-size", '
               '"--market-cap-x", "2", "--levels", "0,1", "--coins", "KXNEAR15M,KXZEC15M", "--minutes", "10080");\n'
               '       o = "$res\\ladder-live-stdout.log"; e = "$res\\ladder-live-stderr.log" },\n'
               '    @{ n = "coin race (LIVE, main account)"; like = "*pinracearm.py --live*"; unlike = ""; stop = "";\n'
               '       a = @("-u", "research/pinracearm.py", "--live", "--max-contracts", "20", "--log", '
               '"C:/kals-repo/results/pinracepenny-live.jsonl");\n'
               '       o = "$res\\x.out"; e = "$res\\x.err" }\n)\n')
        _ls = boot_launches(_ps)
        ck([(x["label"], x["script"]) for x in _ls] ==
           [(None, "pinrun.py"), (None, "pinledgerd.py"), ("ladder_live (LIVE, subaccount 1)", "ladder_live.py"),
            ("coin race (LIVE, main account)", "pinracearm.py")]
           and _ls[0]["arms"] == ["arm-b-control", "arm-pin0.97"] and _ls[0]["argv"][1] == "C:\\kals-repo\\research\\pinrun.py"
           and _ls[2]["argv"][-2:] == ["--minutes", "10080"] and _ls[2]["label"].startswith("ladder_live"),
           "boot_launches: the three launch shapes in file order, $repo filled, the arm names, and the `$false -and` "
           "(OFF) launch left out")
        ck(argv_lines(_ls[0]["argv"]) == ["contracts a bet: 20", "runs for (minutes): 4320", "day stop (dollars): -60.00",
                                          "sweep depth: on"]
           and argv_lines(_ls[2]["argv"])[1:4] == ["real money: on", "bet size follows the pot: on", "cap per market (x bid size): 2"]
           and "coins: KXNEAR15M, KXZEC15M" in argv_lines(_ls[2]["argv"])
           and argv_lines(_ls[3]["argv"])[-1] == "log file: pinracepenny-live.jsonl",
           "argv_lines: -u and the script hidden, a negative number is a value, a bare flag is 'on', paths by name")
        ck(py_consts("X = 1\nDAY_STOP_FRAC, COMMIT_FRAC = 0.20, 0.70\nMAX_CONTRACTS = 10\nMAX_CONTRACTS = 99\n",
                     ("COMMIT_FRAC", "DAY_STOP_FRAC", "MAX_CONTRACTS")) == {"DAY_STOP_FRAC": 0.2, "COMMIT_FRAC": 0.7,
                                                                            "MAX_CONTRACTS": 10.0},
           "py_consts: a tuple line and a plain line; the first assignment wins")
        with tempfile.TemporaryDirectory() as _tdf:
            _bp, _lp = os.path.join(_tdf, "boot_all.ps1"), os.path.join(_tdf, "ladder_live.py")
            with open(_bp, "w", encoding="utf-8") as _fh:
                # this temp folder's stop file, not the real results\ one (2026-10-27: since the bots moved to the
                # server the laptop keeps real stop files, and this check read them and failed there)
                _fh.write(_ps.replace('stop = "$res\\ladder-live.stop"', 'stop = "%s"' % os.path.join(_tdf, "ladder-live.stop")))
            with open(_lp, "w", encoding="utf-8") as _fh:
                _fh.write("SIZE = Decimal('1')\nMAX_CONTRACTS = 10\nDAY_STOP_FRAC, COMMIT_FRAC = 0.20, 0.70\n")
            _sv_paths = globals()["BOOT_ALL"], globals()["LADDER_PY"]
            globals()["BOOT_ALL"], globals()["LADDER_PY"] = _bp, _lp
            try:
                r = ph.handle(111, "/features")
                t_ = P(r)
                ck(getattr(r, "is_html", False) and not tg_html_problems(r) and fits(r) and t_.startswith("🧩 Features")
                   and "Penny ladder (LIVE, subaccount 1)\n" in t_ and "goal 1%/day of its bank" in t_
                   and "98c rung: buy the already-decided side 2c below fair\n95c rung: the same at 5c below fair\n" in t_
                   and "rungs (levels): 0, 1" in t_ and "coins: KXNEAR15M, KXZEC15M" in t_
                   and "Pin bot (LIVE, main account)\n" in t_ and "not started by boot_all" in t_
                   and "Pin bot paper arms\n" in t_ and "arms: 2 -- arm-b-control, arm-pin0.97" in t_
                   and "Weather dip-seller (LIVE, subaccount 3)\nSells daily high-temperature markets (KXHIGH) into "
                       "dips, in Kalshi's weather cash pool.\nnot started by boot_all\n" in t_
                   and "Rules the bots run under (ladder_live.py)\nOpen bids: at most 70% of the bank" in t_
                   and "Daily loss stop: down 20% of the day's first pot" in t_
                   and "Contracts out at once: at most 10x the bid size" in t_ and "cmdlive" not in t_,
                   "/features: a block a bot with its live flags from boot_all.ps1, the ladder's goal and both rungs "
                   "(--levels 0,1), 'not started by boot_all' for the pin bot, the arms counted, the rails from "
                   "ladder_live.py, the OFF launch absent; valid HTML that fits Telegram's limit")
                globals()["BOOT_ALL"] = os.path.join(_tdf, "missing.ps1")
                t_ = P(ph.handle(111, "/features"))
                ck("could not read it" in t_ and t_.count("not started by boot_all") == len(FEATURES)
                   and "Open bids: at most 70%" in t_, "/features without boot_all.ps1: says so, every bot unstarted, rules kept")
                with open(_bp, "w", encoding="utf-8") as _fh:
                    _fh.write('$cleanroom = @(@{ n = "new thing"; a = @("-u", "research\\new_bot.py", "--x", "1") })\n')
                globals()["BOOT_ALL"] = _bp
                t_ = P(ph.handle(111, "/features"))
                ck("new thing\nstarted by boot_all; not written up here yet\nx: 1" in t_,
                   "/features: a launch boot_all has that the roster does not know is still shown, by boot_all's label")
            finally:
                globals()["BOOT_ALL"], globals()["LADDER_PY"] = _sv_paths
        t_ = P(ph.handle(111, "/features"))
        ck("/features" in HELP_TEXT and t_.startswith("🧩 Features") and "Rules the bots run under" in t_
           and fits(ph.handle(111, "/features")), "/features is in /help and the real boot_all.ps1 renders")
        _bs_mode["m"], ph.bs_procs = "planted", _bs_procs
        r = ph.handle(111, "/stop")
        ck("/stop yes" in P(r) and "STOP stops right now" in P(r) and not ph.busy,
           "/stop without yes only explains; nothing is stopped")
        ck(P(ph.handle(111, "/mute")) == "🔕 Alerts off. /unmute to turn them back on." and ph.muted, "/mute")
        ck(P(ph.handle(111, "/unmute")) == "🔔 Alerts on." and not ph.muted, "/unmute")
        _sv_flag, _sv_upd, _ups = UPDATE_FLAG, ph.update_start, []
        try:
            globals()["UPDATE_FLAG"] = os.path.join(td, "pinphone.update")
            ph.update_start = lambda ctx: (_ups.append(1), Html("🔄 <b>Checking the newest phone code</b>"))[1]
            _n0 = len(tg.sent)
            _r0 = ph.update_flag_tick()
            open(UPDATE_FLAG, "w").close()
            _r1 = ph.update_flag_tick()
            _r2 = ph.update_flag_tick()
            ck(_r0 is None and _r2 is None and _ups == [1] and not os.path.exists(UPDATE_FLAG)
               and "Checking the newest phone code" in P(_r1) and "update flag file" in P(_r1)
               and len(tg.sent) == _n0 + 1,
               "update flag (10-26): no file -> nothing; the file -> /update runs ONCE (the file removed first) and the "
               "operator is told it came from the file")
        finally:
            globals()["UPDATE_FLAG"], ph.update_start = _sv_flag, _sv_upd
        ck("Commands" in P(ph.handle(111, "/help")) and "I did not understand that." in P(ph.handle(111, "what"))
           and "Commands" in P(ph.handle(111, "what")), "/help, and an unknown message gets the help")
        ck("Commands" in P(ph.handle(111, "/help@PinBotBot")), "a command with the @botname suffix still works")
        ck(all(not tg_html_problems(x) for x in (HELP_TEXT, STOP_ASK, UP_TEXT) + tuple(CONTROL_REPLY.values()))
           and all(getattr(x, "is_html", False) for x in tuple(CONTROL_REPLY.values()) + (HELP_TEXT, STOP_ASK)),
           "/help, the STOP question, the start-up line and the control replies are valid Telegram HTML")
        ck([P(CONTROL_REPLY[k]) for k in ("start", "pause", "stop", "busy")] ==
           ["▶️ Starting…", "⏸ Pausing: no new bets; waiting for open ones to settle…", "⏹ Stopping now…",
            "⏳ Still working on the last command."],
           "the control replies say what they always said (the work itself is unchanged: Phone.control)")

        # alerts: first tick only records; a change sends once
        ck(ph.alerts_tick() == [] and ph.last_state == "TRADING", "the first alert tick sends nothing, it only learns the state")
        ck(ph.alerts_tick() == [], "NULL: no change, no message")
        state["h"] = dict(state["h"], alive=False)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "TRADING -> DOWN" in P(sent[0]) and P(sent[0]).startswith("🔴 STATE CHANGED"),
           "the bot going down sends one alert, its new state as the headline")
        ck(not tg_html_problems(sent[0]) and getattr(sent[0], "is_html", False)
           and P(tg.sent[-1][1]) == P(sent[0]), "...valid Telegram HTML, and it is what went to the chat")
        ck(ph.alerts_tick() == [], "...and not a second one while it stays down")
        state["h"] = dict(state["h"], alive=True)
        ck("DOWN -> TRADING" in P(ph.alerts_tick()[0]), "coming back sends one too")
        state["h"] = dict(state["h"], blind={"since": None, "bad": 12, "why": "it cannot reach Kalshi"})
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "TRADING -> BLIND" in P(sent[0]) and "NOT TRADING" in P(sent[0]),
           "THE 09-21 NIGHT: alive but blind sends an alert -- it used to stay TRADING")
        state["h"] = dict(state["h"], blind=None)
        ck("BLIND -> TRADING" in P(ph.alerts_tick()[0]), "and seeing again sends one")
        state["h"] = dict(state["h"], kalshi_ok=False)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "RECORDER SILENT: Kalshi recorder" in P(sent[0]) and not tg_html_problems(sent[0]),
           "a silent Kalshi recorder sends one alert")
        ck(ph.alerts_tick() == [], "...and not a second while it stays silent")
        state["h"] = dict(state["h"], kalshi_ok=True)
        ck("WRITING AGAIN" in P(ph.alerts_tick()[0]), "and writing again sends one")
        # A LAYOUT BUG MUST NEVER SWALLOW AN ALERT: the state-change layout planted to fail -> the plain words go
        _sv_ast = _alerts.alert_state_text            # (v-tg-rebuild step 10: the layouts live in phone/alerts.py)
        try:
            _alerts.alert_state_text = lambda *a: 1 / 0
            state["h"] = dict(state["h"], alive=False)
            sent = ph.alerts_tick()
        finally:
            _alerts.alert_state_text = _sv_ast
        ck(len(sent) == 1 and not getattr(sent[0], "is_html", False)
           and sent[0].startswith("STATE CHANGED: TRADING -> DOWN\n"),
           "a state-change alert whose layout fails still goes, in the plain words it always had")
        state["h"] = dict(state["h"], alive=True)
        ck("DOWN -> TRADING" in P(ph.alerts_tick()[0]), "...and the next change is laid out again")
        # THE DISK. The pure function first, exact words; then the tick.
        ck(disk_alert(0, 30.0) == (0, None) and disk_alert(0, 9.01) == (0, None), "disk: plenty free, nothing")
        ck(disk_alert(0, 7.5) == (8, "DISK 7.5 GB free, under 8 GB. The recorders stop themselves for good at 5 GB and "
           "that tape cannot be recreated; at about 4 GB a day that is roughly 0.6 days. Next warning under 6 GB."),
           "disk: under 8 GB sends the first warning, with the days left to the hard stop")
        ck(disk_alert(8, 7.2) == (8, None), "...not again while it stays under 8")
        ck(disk_alert(8, 5.9) == (6, "DISK 5.9 GB FREE -- 0.9 GB from the 5 GB line where the recorders STOP FOR GOOD "
           "and the tape ends. Free space or plug in the new drive NOW. (Sent again only if it climbs over 9 GB and "
           "falls back.)"), "disk: under 6 GB sends the second, louder one")
        ck(disk_alert(0, 5.9)[0] == 6, "...straight to the under-6 alert if the first was never sent")
        ck(disk_alert(6, 5.5) == (6, None) and disk_alert(6, 7.5) == (6, None) and disk_alert(6, 8.5) == (6, None),
           "...and nothing more between 5 and 9 GB")
        ck(disk_alert(6, 9.5) == (0, None) and disk_alert(8, 9.5) == (0, None), "over 9 GB re-arms, silently")
        ck(disk_alert(8, None) == (8, None) and disk_alert(0, None) == (0, None), "NULL: an unreadable disk changes nothing")
        state["h"] = dict(state["h"], disk_gb=7.5)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and P(sent[0]).startswith("⚠️ DISK 7.5 GB free, under 8 GB.") and ph.disk_level == 8
           and P(sent[0]).replace("⚠️ ", "", 1).replace("\n", " ") == disk_alert(0, 7.5)[1],
           "the tick sends the under-8 alert once, disk_alert's exact words under a headline")
        state["h"] = dict(state["h"], disk_gb=7.1)
        ck(ph.alerts_tick() == [], "...and not again at 7.1")
        state["h"] = dict(state["h"], disk_gb=5.9)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and P(sent[0]).startswith("🚨 DISK 5.9 GB FREE") and ph.disk_level == 6
           and P(sent[0]).replace("🚨 ", "", 1).replace("\n", " -- ", 1) == disk_alert(8, 5.9)[1],
           "under 6 sends the second, its exact words")
        state["h"] = dict(state["h"], disk_gb=8.5)
        ck(ph.alerts_tick() == [] and ph.disk_level == 6, "8.5 GB: nothing, still armed at 6")
        state["h"] = dict(state["h"], disk_gb=9.5)
        ck(ph.alerts_tick() == [] and ph.disk_level == 0, "9.5 GB: re-armed, nothing sent")
        state["h"] = dict(state["h"], disk_gb=7.9)
        ck(len(ph.alerts_tick()) == 1, "...so the next dip under 8 is announced again")
        ph.muted = True
        state["h"] = dict(state["h"], disk_gb=5.0)
        ck(ph.alerts_tick() == [] and ph.disk_level == 6, "muted: the disk line is tracked but not sent")
        ph.muted = False
        state["h"] = dict(state["h"], disk_gb=30.0)
        ck(ph.alerts_tick() == [] and ph.disk_level == 0, "back to 30 GB: re-armed")
        # a new losing close
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "order", "t": "2026-09-16T14:14:31Z", "ticker": c2, "filled": 40.0, "exec_price": 0.97, "status": "executed", "body": {"count": "40.00"}}) + "\n")
            pass
        # THE LOSS ARRIVES IN KALSHI'S BOOKS, not in our log -- that is where
        # money lives now, and it is why the alert can no longer mistake one
        # leg of a hedged market for a losing trade.
        _led = json.load(open(_pl.LEDGER, encoding="utf-8"))
        _led["settlements"]["k2"] = {
            "ticker": c2, "market_result": "yes",
            "no_count_fp": "40.00", "no_total_cost_dollars": "38.80",
            "yes_count_fp": "0.00", "yes_total_cost_dollars": "0.00",
            "revenue": 0, "fee_cost": "0.00",
            "settled_time": "2026-09-16T14:15:20Z"}
        with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
            json.dump(_led, _fh)
        os.utime(_pl.LEDGER, (time.time() + 5, time.time() + 5))
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and P(sent[0]).startswith("🔴 LOSS -$38.80 (-")
           and "% of the bank) · pin bot (main account) · the quarter-hour closing 10:15 AM ET on Sep 16"
           in P(sent[0]).split("\n")[0]
           and "\n• BTC NO at 97.0c, 40 contracts → settled YES: -$38.80" in P(sent[0]) and "WHY IT HURTS" in P(sent[0])
           and not tg_html_problems(sent[0]),
           "a new losing close is sent with its story: the loss as the headline naming the bot and its account (10-26), "
           "one line a leg")
        _mix = P(_alerts.alert_loss_text(L, calendar.timegm((2026, 9, 16, 14, 15, 0)), -37.0, [
            {"tk": c2, "want": "no", "cost": 0.97, "result": "yes", "pnl": -38.80},
            {"tk": "KXCRYPTOLEAD15M-26SEP161015-SOL", "want": "yes", "cost": 0.9, "result": "yes", "pnl": 1.80, "n": 20.0}],
            sys.modules[__name__]))
        ck(" · pin bot + coin race (main account) · " in _mix.split("\n")[0]
           and "\n• pin bot · BTC NO at 97.0c, 40 contracts" in _mix and "\n• coin race · SOL YES at 90.0c, 20 contracts" in _mix,
           "a losing close holding both main-account bots' legs names both, and each leg its bot (the race leg's "
           "contracts are Kalshi's, not the pin bot's orders): %r" % _mix)
        ck(ph.alerts_tick() == [], "...once")
        ph.muted = True
        state["h"] = dict(state["h"], alive=False)
        ck(ph.alerts_tick() == [] and ph.last_state == "DOWN", "muted: the change is tracked but not sent")
        ph.muted = False
        ck(not any("YESTERDAY" in P(t_).split("\n")[0] for _c, t_ in tg.sent),
           "a summary already due at startup is NOT re-sent (it started at 11 AM ET)")
        # next day, 9 AM ET: the daily summary of the 16th goes out once
        now["t"] += 86400 - 2 * 3600
        sent = ph.alerts_tick()
        _dl = [m for m in sent if "YESTERDAY" in P(m).split("\n")[0]]
        ck(len(_dl) == 1 and P(_dl[0]).startswith("☀️ YESTERDAY, Wed Sep 16 · every bot")
           and "All bots yesterday" in P(_dl[0]) and "📊 By bot" in P(_dl[0])
           and "☀️ YESTERDAY -$37.14 (-7.43%) · Wed Sep 16" in P(_dl[0])
           and "MONEY: -$37.14, which is -7.43% of the $500.00" in P(_dl[0]) and not tg_html_problems(_dl[0]),
           "after 8 AM ET the daily summary of yesterday goes out: every bot's day with its % of all pots and each "
           "bot's % of its bank, then the main account's money and % of its day-start bank behind a tap")
        ck(not any("YESTERDAY" in P(m).split("\n")[0] for m in ph.alerts_tick()), "...once per day")
        ck(all(cid == 111 for cid, _t in tg.sent), "every alert went to the paired chat")
        # long messages are split by the real transport's rule
        big = "x" * (MAX_LEN * 2 + 5)
        chunks = split_text(big)
        ck(len(chunks) == 3 and sum(len(c) for c in chunks) == len(big), "a long reply is split under Telegram's limit")
        ck(split_text("a\n\nb\n\nc", 3) == ["a", "b", "c"] and split_text("ab\ncd\nef", 5) == ["ab", "cd\nef"]
           and split_text("", 5) == [""], "...at a blank line when one is there, else a line, else hard")
        _calls = []
        _real = Telegram("tok")
        _real._call = lambda method, params, http_timeout=45: _calls.append(params["text"])
        _real.send(111, "A" * 2500 + "\n\n" + "B" * 2500)
        ck(_calls == ["A" * 2500, "B" * 2500],
           "the real transport sends a long /bars in whole paragraphs, never mid-sentence")
        # poll_once routes replies to the sender and advances the offset
        tg.push(111, "/help")
        tg.push(333, "/status")
        ph.poll_once()
        ck(tg.sent[-1][0] == 111 and "Commands" in P(tg.sent[-1][1]) and ph.offset == 3, "poll: the paired chat gets its reply, the stranger nothing, offset advances")

        # ---- charts after the words (2026-10-18) -------------------------------------------------------
        # The picture is queued AFTER the words are sent and drawn on one background thread: poll_once never
        # waits for it, alerts run meanwhile, the controls never queue one, a stranger gets none, a failing or
        # late picture only logs, and a full queue drops (never blocks). tgcharts' own --selftest draws them.
        import threading as _thr
        _tgcm = _tgc()
        ck(all(_tgcm.kind_of(c_) is None for c_ in ("/open", "/help", "/pause", "/start", "/stop", "/mute", "/unmute",
                                                     "/pair"))
           and _tgcm.kind_of("/today") == "today" and _tgcm.kind_of("/funds") == "funds" and ph.charts_on is False,
           "charts: off unless main() turns them on; the controls, /open and /help never get a picture")
        _pb = photo_body(111, b"\x89PNG\r\n\x1a\nDATA", "Today +$1.00", "BND")
        ck(_pb.startswith(b"--BND\r\n") and b'name="chat_id"\r\n\r\n111\r\n' in _pb
           and b'name="caption"\r\n\r\nToday +$1.00\r\n' in _pb
           and _pb.endswith(b'filename="chart.png"\r\nContent-Type: image/png\r\n\r\n\x89PNG\r\n\x1a\nDATA\r\n--BND--\r\n'),
           "sendPhoto's multipart body: chat_id, caption, the PNG byte for byte, the closing boundary")
        _posted = []
        _tp = Telegram("tok")
        _tp._post = lambda method, body, ctype, http_timeout=60: (_posted.append((method, ctype, body)), {"ok": True})[1]
        _tp.send_photo(111, b"PNG", "cap")
        ck(_posted and _posted[0][0] == "sendPhoto" and _posted[0][1].startswith("multipart/form-data; boundary=pinphone")
           and (b"--" + _posted[0][1].split("=", 1)[1].encode() + b"--\r\n") in _posted[0][2],
           "the transport posts the picture to sendPhoto with its own boundary")
        _tp._post = lambda *a, **k: {"ok": False, "description": "Bad Request"}
        try:
            _tp.send_photo(111, b"PNG", "cap")
            _rf = None
        except RuntimeError as e:
            _rf = e
        ck(_rf is not None, "a refused sendPhoto raises (the chart thread logs it; the words already went)")
        _in, _gate, _seen = _thr.Event(), _thr.Event(), []

        def _slow_chart(kind, ctx):
            _seen.append((kind, ctx))
            _in.set()
            _gate.wait(20)
            return (b"\x89PNG fake", "caption " + kind)
        ph.chart_fn, ph.charts_on = _slow_chart, True
        _n0 = len(tg.sent)
        tg.push(111, "/today")
        _t0 = time.time()
        ph.poll_once()
        _dtp = time.time() - _t0
        ck(len(tg.sent) == _n0 + 1 and tg.photos == [] and _dtp < 5,
           "charts: the words go first; poll_once returns without waiting for the picture (%.2f s)" % _dtp)
        ck(_in.wait(20), "charts: the picture is drawn on the background thread")
        _sv = (ph.last_state, ph.last_rec, ph.seen_losses, ph.last_daily, ph.disk_level, list(tg.sent))
        ck(isinstance(ph.alerts_tick(), list), "charts: an alert check runs while a picture is still drawing")
        ph.last_state, ph.last_rec, ph.seen_losses, ph.last_daily, ph.disk_level, tg.sent[:] = _sv
        tg.push(111, "/stop")
        tg.push(111, "/help")
        tg.push(333, "/today")
        ph.poll_once()
        ck(ph._chart_q.qsize() == 0, "charts: /stop (its confirm question), /help and a stranger's /today queue nothing")
        tg.push(111, "/days")
        tg.push(111, "/losses")
        tg.push(111, "/stats")
        ph.poll_once()
        ck(ph._chart_q.qsize() == CHART_QUEUE,
           "charts: while one draws, %d wait and the next is dropped -- the poll loop never blocks" % CHART_QUEUE)
        _gate.set()
        ph._chart_q.join()
        ck([(c_, k_) for c_, _p, k_ in tg.photos] == [(111, "caption today"), (111, "caption days"), (111, "caption losses")]
           and tg.photos[0][1] == b"\x89PNG fake", "charts: each picture goes to the paired chat after its words, in order")
        _cx = _seen[0][1]
        ck(_seen[0][0] == "today" and _cx.ledger is not ph.ledger and _cx.ledger.settled == ph.ledger.settled
           and _cx.ledger.settled is not ph.ledger.settled and _cx.now == now["t"] and _cx.markets is chart_markets
           and _cx.window_stats is window_stats and _cx.first_live_day == FIRST_LIVE_DAY,
           "charts: the picture reads a private copy of the ledger taken with the words, on the phone's clock (a "
           "ChartCtx since v-tg-rebuild step 10: the main account's markets, window_stats and FIRST_LIVE_DAY named)")
        _n1 = len(tg.photos)
        for _fn, _why in ((lambda kind, ctx: 1 / 0, "ZeroDivisionError"), (lambda kind, ctx: None, "nothing live to draw")):
            ph.chart_fn = _fn
            tg.push(111, "/days")
            ph.poll_once()
            ph._chart_q.join()
            with open(LOG, encoding="utf-8") as _fh:
                _lgc = _fh.read()
            ck(len(tg.photos) == _n1 and _why in _lgc and ("All bots last 7 days" in P(tg.sent[-1][1]).split("\n")[0]
                                                            or "All time" in P(tg.sent[-1][1]).split("\n")[0]),
               "charts: a picture that fails or has nothing to draw only logs (%s); the words went as always" % _why)
        ph.chart_fn, ph.chart_stale_s = _slow_chart, -1
        tg.push(111, "/days")
        ph.poll_once()
        ph._chart_q.join()
        with open(LOG, encoding="utf-8") as _fh:
            _lgc = _fh.read()
        ck(len(tg.photos) == _n1 and "dropped: its turn came" in _lgc, "charts: a picture whose turn comes late is dropped, never sent stale")

        def _no_mpl(kind, ctx):
            raise ImportError("No module named 'matplotlib'")
        ph.chart_fn, ph.chart_stale_s = _no_mpl, None
        tg.push(111, "/days")
        ph.poll_once()
        ph._chart_q.join()
        tg.push(111, "/today")
        ph.poll_once()
        ck(ph.charts_on is False and ph._chart_q.qsize() == 0 and len(tg.photos) == _n1,
           "charts: without matplotlib the phone turns pictures off (logged once) and keeps sending the words")
        ph.chart_fn = None

        # ---- /funds /bank /accounts (2026-10-11) ----------------------------------------------------
        # A fake Kalshi with 3 accounts across 2 cash pools. Worked by hand: main = 500.00 + 1.50 cash +
        # 29.10 open = 530.60 (the 0-contract row's 9.99 is not a bet); sub 1 = 80.25; sub 3 = 40.00 +
        # 1.10 open = 41.10; all = 651.95 = cash 621.75 + open 30.20. Kalshi's whole-account cash: pool 0 =
        # 1.50 + 40.00 = 41.50, pool 2 = 580.25 -> 621.75. /portfolio/balance's `balance` is CENTS here
        # (as Kalshi sends it), so a reader that used it instead of balance_dollars would be 100x off.
        fw_list = [{"subaccount_number": 0, "exchange_index": 2, "balance": "500.0000"},
                   {"subaccount_number": 0, "exchange_index": 0, "balance": "1.5000"},
                   {"subaccount_number": 1, "exchange_index": 0, "balance": "0.0000"},
                   {"subaccount_number": 1, "exchange_index": 2, "balance": "80.2500"},
                   {"subaccount_number": 3, "exchange_index": 0, "balance": "40.0000"},
                   {"subaccount_number": 3, "exchange_index": 2, "balance": "0.0000"}]
        fw_pos = {0: [{"ticker": "KXBTC15M-26SEP161115-15", "position_fp": "-30.00", "market_exposure_dollars": "29.10"},
                      {"ticker": "KXETH15M-26SEP161115-15", "position_fp": "0.00", "market_exposure_dollars": "9.99"}],
                  3: [{"ticker": "KXHIGHNY-26SEP16-B70.5", "position_fp": "-2.00", "market_exposure_dollars": "1.10"}]}
        fw_break = [{"balance": "41.5000", "exchange_index": 0}, {"balance": "0.0000", "exchange_index": 1},
                    {"balance": "580.2500", "exchange_index": 2}]

        # PAST DAYS: the same 3 accounts' settlement rows, pages newest first, in BOTH cash pools (ix). The
        # phone's clock for these checks: 11:00 AM ET Wed Sep 16, so the 7 days are Thu Sep 10 .. Wed Sep 16.
        # Worked by hand, per market = payout - cost - fee:
        #   main: Wed 16 = ETH 12:15 AM -19.62 (lost) + race +0.14 = -19.48 | Tue 15 = BTC 11:30 PM +0.19 +
        #         BTC hourly +1.00 = +1.19 | Mon 14 = BTC 12:00 PM in TWO rows (+0.57, -0.90) = ONE market
        #         -0.33 (lost) + NY high (pool 0) +0.80 = +0.47 -> 7 days -17.82 (2 of 6 lost) = main bot
        #         -19.76 (2 of 3) + race +0.14 (0 of 1) + other +1.80 (0 of 2); -3.4% of its $530.60.
        #   sub 1: Wed 16 +0.05; Sat 12 (9:15 PM ET, settled the 13th UTC) -9.90 -> -9.85 (1 of 2 lost),
        #          -12.3% of $80.25 -- the $50 moved into it that week is NOT a gain.
        #   sub 3 (pool 0): Tue 15 +0.50 (a ticker with no date: its settled time 11:40 PM ET, the 16th in
        #          UTC) + Mon 14 -1.70 (lost) -> -1.20 (1 of 2 lost), -2.9% of $41.10.
        def _R(tk, st, res, yn=0.0, yc=0.0, nn=0.0, nc=0.0, fee=0.0, ix=2):
            return {"ticker": tk, "settled_time": st, "market_result": res, "value": {"yes": 100, "no": 0}[res],
                    "yes_count_fp": "%.2f" % yn, "yes_total_cost_dollars": "%.6f" % yc, "no_count_fp": "%.2f" % nn,
                    "no_total_cost_dollars": "%.6f" % nc, "fee_cost": "%.6f" % fee, "revenue": 0, "exchange_index": ix}
        fr_race = _R("KXCRYPTOLEAD15M-26SEP160930-XRP", "2026-09-16T13:30:20Z", "yes", yn=5, yc=4.85, fee=0.01)
        fr_eth0015 = _R("KXETH15M-26SEP160015-15", "2026-09-16T04:15:03.2Z", "no", yn=20, yc=19.60, fee=0.02)
        fr_btc2330 = _R("KXBTC15M-26SEP152330-30", "2026-09-16T03:30:03.1Z", "no", nn=10, nc=9.80, fee=0.01)
        fr_hourly = _R("KXBTCD-26SEP1511-T60000", "2026-09-15T15:00:10Z", "yes", yn=2, yc=1.00)
        fr_wx0 = _R("KXHIGHNY-26SEP14-B70.5", "2026-09-15T12:00:00Z", "no", nn=2, nc=1.20, ix=0)
        fr_two_b = _R("KXBTC15M-26SEP141200-00", "2026-09-14T16:00:05Z", "no", yn=30, yc=0.90)
        fr_two_a = _R("KXBTC15M-26SEP141200-00", "2026-09-14T16:00:03Z", "no", nn=30, nc=29.40, fee=0.03)
        fr_old = _R("KXBTC15M-26SEP090900-00", "2026-09-09T13:00:03Z", "no", yn=50, yc=49.00)       # Sep 9: out
        fr_older = _R("KXBTC15M-26SEP081000-00", "2026-09-08T14:00:03Z", "no", yn=60, yc=59.00)     # never asked
        fw_xfer = {"amount_cents": 5000, "from_subaccount": 0, "to_subaccount": 1, "created_ts": 1789900000}
        fw_stl = {0: [[fr_race, fr_eth0015, fr_btc2330], [fr_hourly, fr_wx0, fr_two_b],
                      [dict(fr_two_b), fr_two_a, fr_old], [fr_older]],   # fr_two_b again: it slid across a page edge
                  1: [[_R("KXNEAR15M-26SEP160300-00", "2026-09-16T07:00:03Z", "no", nn=5, nc=4.95),
                       dict(fw_xfer, settled_time="2026-09-15T12:00:00Z", revenue=5000),   # money, but not a market
                       _R("KXBNB15M-26SEP122115-15", "2026-09-13T01:15:03Z", "yes", nn=10, nc=9.90)]],
                  3: [[_R("KXODD-XYZ", "2026-09-16T03:40:00Z", "yes", yn=1, yc=0.50, ix=0),
                       _R("KXHIGHNY-26SEP14-B71.5", "2026-09-15T12:00:00Z", "yes", nn=2, nc=1.70, ix=0)]]}

        def fw_get(asked, bad=lambda path, q: None, rows=None, pos=None, brk=None, stl=None):
            def get(path, q):
                asked.append((path, dict(q)))
                b = bad(path, q)
                if b == "raise":
                    raise OSError("connection reset")
                if b is not None:
                    return b
                if path == "/portfolio/settlements":          # pages per account, newest first (below)
                    pg = (stl if stl is not None else fw_stl).get(q["subaccount"], [[]])
                    i = int(q.get("cursor") or 0)
                    return 200, {"settlements": pg[i], "cursor": str(i + 1) if i + 1 < len(pg) else ""}
                if path in ("/portfolio/subaccounts/transfers", "/portfolio/deposits"):
                    return 200, {"transfers": [fw_xfer], "deposits": [{"amount_cents": 100000, "status": "applied"}],
                                 "cursor": ""}
                if path == "/portfolio/subaccounts/balances":
                    return 200, {"subaccount_balances": rows if rows is not None else fw_list}
                if path == "/portfolio/balance":
                    for r in (rows if rows is not None else fw_list):
                        if (r["subaccount_number"], r["exchange_index"]) == (q["subaccount"], q["exchange_index"]):
                            return 200, {"balance": int(round(100 * float(r["balance"]))), "balance_dollars": r["balance"],
                                         "balance_breakdown": brk if brk is not None else fw_break}
                    return 404, {"error": "not found"}
                if path == "/portfolio/positions":
                    return 200, {"market_positions": (pos if pos is not None else fw_pos).get(q["subaccount"], []),
                                 "event_positions": [], "cursor": ""}
                return 404, "unknown path"
            return get

        fa = []
        f_ = funds_read(fw_get(fa))
        _fw_act = ("pin", "race", "ladder")      # v-tg-active: the bots running in this world (the weather pot's stopped)
        t_ = funds_text(f_, {}, now["t"], active=_fw_act)
        cprint("    --- /funds, the fake world (as the phone shows it) ---\n    " + P(t_).replace("\n", "\n    "))
        ck(sorted(f_["subs"]) == [0, 1, 3] and f_["list_err"] is None, "/funds: the 3 listed accounts, from Kalshi's list")
        ck(getattr(t_, "is_html", False) and not tg_html_problems(t_) and fits(t_), "/funds: Telegram-valid, one message")
        tp_ = P(t_)
        ck("MAIN ACCOUNT (0) -- main bot (pin) + coin race: $530.60" in tp_
           and "\ncash: weather pool $1.50, crypto pool $500.00; open bets: $29.10 on 1 market" in tp_,
           "/funds: main = cash in BOTH pools + what its open bet cost = $530.60 (a 0-contract row is not a bet)")
        ck("SUBACCOUNT 1 -- penny ladder: $80.25" in tp_ and "SUBACCOUNT 3 -- weather pool: nothing runs here now "
           "(stopped); crypto pool: nothing runs here now (stopped): $41.10" in tp_ and "weather dip-seller" not in tp_,
           "/funds: each subaccount's total, and what runs in it from FUNDS_WHAT -- only the running bots named")
        ck(tp_.split("\n")[0] == "🏦 ALL ACCOUNTS: $651.95 = cash $621.75 + open bets $30.20.",
           "/funds: the grand total, 3 accounts x 2 pools, is the headline")
        ck(any(x.split() == ["0", "main+race", "530.60", "81.4%"] for x in tp_.split("\n"))
           and any(x.split() == ["1", "ladder", "80.25", "12.3%"] for x in tp_.split("\n"))
           and any(x.split() == ["3", "idle", "41.10", "6.3%"] for x in tp_.split("\n")),
           "/funds: one row an account, its total and its share of all of them (530.60 / 651.95 = 81.4%)")
        ck("💤 Idle: $41.10 (6.3% of all) sits in an account that runs nothing now (3: weather pool: nothing runs here "
           "now (stopped); crypto pool: nothing runs here now (stopped))." in tp_,
           "/funds: money in an account whose bots are all stopped is named as idle, with its share")
        # v-tg-active (2026-10-30): the jump band runs in subaccount 3's crypto pool; the coin race is paused
        _tj = P(funds_text(f_, {3: ["jump band up to 5 contracts a buy"]}, now["t"], active=("pin", "ladder", "jumpband")))
        ck("MAIN ACCOUNT (0) -- main bot (pin): $530.60" in _tj and "coin race" not in _tj
           and "SUBACCOUNT 3 -- weather pool: nothing runs here now (stopped); crypto pool: jump band: BNB/HYPE/ZEC/NEAR "
               "after a price jump (live stage 1, 2026-10-30): $41.10" in _tj
           and any(x.split() == ["3", "jump", "band", "41.10", "6.3%"] for x in _tj.split("\n"))
           and any(x.split() == ["0", "main", "530.60", "81.4%"] for x in _tj.split("\n"))
           and "Idle" not in _tj and "bet size now: jump band up to 5 contracts a buy" in _tj
           and funds_what(3) == FUNDS_WHAT[3] and funds_idle(2, ("pin",)) and not funds_idle(3, ("jumpband",)),
           "/funds with the jump band running and the race paused: the main account names the pin bot only, subaccount 3 "
           "its crypto pool's jump band and its bet size, no idle money: %r" % _tj[:400])
        ck("The cash adds up to Kalshi's own whole-account figure ($621.75)." in tp_,
           "/funds: checked against Kalshi's whole-account cash by pool")
        ck(not any(p == "/portfolio/balance" and (q["subaccount"], q["exchange_index"]) in ((1, 0), (3, 2)) for p, q in fa),
           "/funds: a pool listed at 0 is $0 in any unit -- not read again")
        ck(set(p for p, _q in fa) <= set(FUNDS_PATHS) and set(p for p, _q in f_["asked"]) == set(FUNDS_PATHS)
           and all("subaccount" in q for p, q in fa if p != FUNDS_PATHS[0])
           and all("exchange_index" in q for p, q in fa if p == "/portfolio/balance"),
           "/funds: only the three GET paths; every balance read names its account AND pool, every open-bets read its account")
        ck("SUBACCOUNT 7 -- unknown" in P(funds_text(funds_read(fw_get([], rows=fw_list + [
            {"subaccount_number": 7, "exchange_index": 2, "balance": "2.0000"}])), {}, now["t"])),
           "/funds: an account not in FUNDS_WHAT is shown as unknown, not dropped")
        t_ = P(funds_text(funds_read(fw_get([], brk=[{"balance": "41.5000", "exchange_index": 0},
                                                     {"balance": "600.0000", "exchange_index": 2}])), {}, now["t"]))
        ck("CHECK: Kalshi's own whole-account cash is $641.50, but the accounts above add to $621.75" in t_,
           "/funds: cash Kalshi holds that no listed account explains is said")
        # unreadable reads: said, never $0, never a crash
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (503, "busy") if p == "/portfolio/balance"
                                            and q["subaccount"] == 1 else None)), {}, now["t"]))
        ck("SUBACCOUNT 1 -- penny ladder: $80.25" in t_ and "crypto pool $80.25 (from Kalshi's list; the direct read failed: "
           "HTTP 503)" in t_ and "ALL ACCOUNTS: $651.95" in t_,
           "/funds: one direct cash read fails -> the list's figure, marked, because other pools proved its unit")
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == "/portfolio/balance" else None)),
                          {}, now["t"]))
        ck("$500.00" not in t_ and "$80.25" not in t_ and "crypto pool COULD NOT READ (HTTP 500)" in t_
           and t_.split("\n")[0] == "🏦 ALL ACCOUNTS: at least $30.20 (cash $0.00 + open bets $30.20)"
           and "That leaves out what could not be read: main account weather pool cash, main account crypto pool "
           "cash, subaccount 1 crypto pool cash, subaccount 3 weather pool cash." in t_ and "adds up" not in t_
           and "CHECK:" not in t_ and any(x.split() == ["0", "main+race", ">=29.10", "-"] for x in t_.split("\n")),
           "/funds: EVERY direct cash read fails -> the list's unit is unproven, so no cash figure is shown (hard rule 5), "
           "and no account's share is worked from totals that leave money out")
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == FUNDS_PATHS[0] else
                                            "raise" if p == "/portfolio/balance" and q["subaccount"] == 1
                                            and q["exchange_index"] == 2 else None)), {}, now["t"]))
        ck("list of subaccounts could not be read (HTTP 500)" in t_
           and "MAIN ACCOUNT (0) -- main bot (pin) + coin race: $530.60" in t_
           and "SUBACCOUNT 1 -- penny ladder: at least $0.00" in t_
           and "crypto pool COULD NOT READ (error: connection reset)" in t_
           and "SUBACCOUNT 4 -- weather pool: FX taker: the 5 currency pairs (penny test, 2026-10-25); crypto pool: coin-race reward test (stopped): at least" in t_ and "ALL ACCOUNTS: at least" in t_,
           "/funds: the list fails and a read raises -> the known accounts are tried, what failed is named, no crash")
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == "/portfolio/positions"
                                            and q["subaccount"] == 3 else None,
                                            pos={0: [{"ticker": "KXBTC15M-26SEP161115-15", "position_fp": "-30.00",
                                                      "market_exposure_dollars": "29.10"}],
                                                 1: [{"ticker": "KXNEAR15M-26SEP161115-15", "position_fp": "5.00",
                                                      "market_exposure": 110}]})), {}, now["t"], active=_fw_act))
        ck("SUBACCOUNT 3 -- weather pool: nothing runs here now (stopped); crypto pool: nothing runs here now (stopped): "
           "at least $40.00" in t_
           and "open bets: COULD NOT READ (HTTP 500)" in t_
           and "open bets: COULD NOT READ (a bet came without market_exposure_dollars)" in t_
           and "ALL ACCOUNTS: at least $650.85 (cash $621.75 + open bets $29.10)\n" in t_
           and "That leaves out what could not be read: subaccount 1 open bets, subaccount 3 open bets." in t_,
           "/funds: an unreadable open-bets read, and a bet with only cents (never read as dollars), are said")
        clk = {"t": 0.0}

        def _tick():
            clk["t"] += 1.0
            return clk["t"]
        fa = []
        t_ = P(funds_text(funds_read(fw_get(fa), clock=_tick, deadline_s=2), {}, now["t"]))
        ck(len(fa) == 2 and "the 2 s limit for /funds ran out first" in t_ and "ALL ACCOUNTS: at least" in t_,
           "/funds: a slow Kalshi hits the time limit -> the rest is said as not read, the phone is not stalled")
        # bet sizes from each bot's own log
        szd = os.path.join(td, "funds_sizes")
        os.makedirs(szd)
        ck(funds_sizes(szd) == {}, "/funds sizes: no logs -> no size invented")

        def _wl(name, recs):
            with open(os.path.join(szd, name), "w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r) + "\n")
        with open(os.path.join(szd, "pinrun-live-size.json"), "w", encoding="utf-8") as fh:
            json.dump({"size": 77.0, "bank": 900.0, "at": "2026-10-11T08:00:00Z"}, fh)
        ck(funds_sizes(szd) == {0: ["main bot 77 contracts a bet (sized Oct 11 4:00 AM ET on a $900.00 bank)"]},
           "/funds sizes: no live log yet -> the main bot's size file")
        _wl("pinrun-live-20261010T020723Z.jsonl", [{"kind": "autosize", "t": "2026-10-10T08:00:00Z", "old": 40, "new": 50,
                                                    "why": "bank $600.00"}])
        _wl("pinrun-live-20261010T221608Z.jsonl", [
            {"kind": "start", "t": "2026-10-10T22:16:08Z", "size": 20},
            {"kind": "autosize", "t": "2026-10-11T08:27:42Z", "old": 95.0, "new": 90.0, "why": "bank $1069.74"},
            {"kind": "autosize", "t": "2026-10-11T08:32:42Z", "old": 90.0, "new": 91.0, "why": "bank $1070.44"},
            {"kind": "signal", "t": "2026-10-11T08:33:00Z", "size": 91}])
        _wl("pinracepenny-live.jsonl", [{"kind": "start", "t": "2026-10-10T06:20:08Z",
                                         "live_rails": {"max_contracts": 20.0, "max_stake": 40.0}}])
        _wl("ladder-live-orders.jsonl", [
            {"t": "2026-10-07T12:14:18.105Z", "ev": "start", "subaccount": 1, "pot": 76.7293, "rails": {"size": 5}},
            {"t": "2026-10-11T04:00:10.450Z", "ev": "rescale", "old": 5, "new": 6, "pot": 84.5, "rails": {"size": 6}},
            {"t": "2026-10-11T04:01:00Z", "ev": "order", "count": 6}])
        _wl("forecaster-live-orders.jsonl", [
            {"t": "2026-10-10T06:20:10.831Z", "ev": "start", "pot": 83.9334, "rails": {"scale": "0.1332", "per_side": 13}},
            {"t": "2026-10-11T04:00:07.723Z", "ev": "rescale", "old": 0.1332, "new": 0.146, "pot": 91.9692,
             "rails": {"scale": "0.146", "per_side": 15}}])
        sz_ = funds_sizes(szd)
        ck(sz_ == {0: ["main bot 91 contracts a bet (sized Oct 11 4:32 AM ET on a $1,070.44 bank)",
                       "coin race 20 contracts a bet, at most $40 in play (set at its start Oct 10 2:20 AM ET)"],
                   1: ["ladder 6-contract bids (sized Oct 11 12:00 AM ET on a $84.50 pot)"],
                   2: ["forecaster 14.6% of the paper bot's size, up to 15 contracts a side "
                       "(sized Oct 11 12:00 AM ET on a $91.97 pot)"]},
           "/funds sizes: main = newest autosize in the NEWEST live log; ladder and forecaster = their newest "
           "rescale, not the older start")
        # v-race-snowball (2026-10-11): a start record with bank_sizing sizes from the bank -- the size in force is the
        # newest bank_size record after it, not the start-up live_rails (2026-10-18: /funds had said "20 contracts")
        _wl("pinracepenny-live.jsonl", [
            {"kind": "start", "t": "2026-10-10T06:20:08Z", "live_rails": {"max_contracts": 20.0, "max_stake": 40.0},
             "bank_sizing": {"contracts_per_bank": 0.019048, "stake_per_bank": 0.038095}},
            {"kind": "bank_size", "t": "2026-10-11T15:54:00Z", "bank": 1254.6932, "contracts": 23.0, "stake": 47.79}])
        ck(funds_sizes(szd)[0][1] == "coin race 23 contracts a leg, at most $47.79 in play (3.81% of a $1,254.69 bank; "
                                     "sized Oct 11 11:54 AM ET, grows with the bank)",
           "/funds sizes: the bank-sized coin race shows the size it last took from the bank (23 = floor(1254.69 x "
           "0.019048); stake cap 1254.69 x 0.038095 = $47.79)")
        th_ = funds_text(funds_read(fw_get([])), sz_, now["t"])
        t_ = P(th_)
        ck("\nbet size now: main bot 91 contracts a bet" in t_ and "\nbet size now: ladder 6-contract bids" in t_
           and "\nSUBACCOUNT 3" in t_ and len(th_) < MAX_LEN, "/funds: each account carries its bots' bet sizes; one message")
        # ---- /funds PAST DAYS (2026-10-11): the world and the hand-worked figures are above fw_get ----
        fnow = calendar.timegm((2026, 9, 16, 15, 0, 0))                 # 11:00 AM ET Wed Sep 16
        ck([funds_book(t) for t in ("KXBTC15M-X", "KXNEWCOIN15M-X", "KXCRYPTOLEAD15M-X", "KXCRYPTOCOMP15M-X",
                                    "KXGOLD15M-X", "KXBTCD-X", "KXHIGHNY-X", "")]
           == ["bot", "bot", "race", "race", "other", "bot", "other", "other"],
           "/funds past days: main bot = 15-minute coin series + its hourly coin series (as /pin); race = the coin "
           "race; weather, oil = other")
        ha = []
        hm = {}
        h_ = funds_settled(fw_get(ha), [0, 1, 3], fnow, memo=hm)
        ck(set(p for p, _q in ha) == {FUNDS_HIST_PATH} and all(q.get("subaccount") in (0, 1, 3) for _p, q in ha)
           and [q.get("cursor") for _p, q in ha if q["subaccount"] == 0] == [None, "1", "2"]
           and sorted(h_) == [0, 1, 3] and all(h_[n]["err"] is None for n in h_),
           "/funds past days: only GET /portfolio/settlements, every request names its account; main's walk stops "
           "on the page that reaches back past Thu Sep 10 (3 pages, the 4th never asked)")
        hd0 = funds_days(h_[0], "2026-09-16")
        hday = {x["day"]: x for x in hd0["days"]}
        ck([x["day"] for x in hd0["days"]] == ["2026-09-16", "2026-09-15", "2026-09-14", "2026-09-13", "2026-09-12",
                                               "2026-09-11", "2026-09-10"] and all(x["read"] for x in hd0["days"]),
           "/funds past days: the last 7 ET days, newest first, all read")
        ck(abs(hday["2026-09-15"]["bot"]["money"] - 1.19) < 1e-9 and hday["2026-09-15"]["bot"]["n"] == 2   # + hourly
           and abs(hday["2026-09-16"]["bot"]["money"] + 19.62) < 1e-9 and hday["2026-09-16"]["bot"]["n"] == 1,
           "/funds past days: an 11:30 PM ET close is that ET day (Tue 15, settled the 16th UTC); a 12:15 AM ET "
           "close is the next (Wed 16)")
        ck(hday["2026-09-14"]["bot"] == {"money": hday["2026-09-14"]["bot"]["money"], "n": 1, "lost": 1}
           and abs(hday["2026-09-14"]["bot"]["money"] + 0.33) < 1e-9,
           "/funds past days: a market with two rows is ONE market, its rows summed (-0.33, lost), and a row read "
           "twice across a page edge counts once")
        hd1, hd3 = funds_days(h_[1], "2026-09-16"), funds_days(h_[3], "2026-09-16")
        ck(hd1["total"]["all"]["n"] == 2 and abs(hd1["total"]["all"]["money"] + 9.85) < 1e-9
           and hd1["days"][4]["all"]["n"] == 1 and hd1["days"][4]["day"] == "2026-09-12",
           "/funds past days: a transfer is never a gain -- a transfer row among the settlements is not a market, "
           "the $50 moved into sub 1 is not read, its 7 days are its 2 settlements (-$9.85); 9:15 PM ET is Sat 12")
        ck(abs(hd3["days"][1]["all"]["money"] - 0.50) < 1e-9 and hd3["days"][0]["all"]["n"] == 0
           and abs(hd3["total"]["all"]["money"] + 1.20) < 1e-9,
           "/funds past days: a ticker with no date falls back to its settled time ON THE ET CLOCK (11:40 PM ET Tue "
           "15, not the 16th UTC); pool-0 weather rows count")
        ck(abs(hd0["total"]["all"]["money"] + 17.82) < 1e-9 and hd0["total"]["all"]["n"] == 6
           and hd0["total"]["all"]["lost"] == 2 and abs(hd0["total"]["bot"]["money"] + 18.76) < 1e-9
           and hd0["total"]["bot"]["n"] == 4 and abs(hd0["total"]["race"]["money"] - 0.14) < 1e-9
           and abs(hd0["total"]["other"]["money"] - 0.80) < 1e-9 and hd0["other_series"] == ["KXHIGHNY"],
           "/funds past days: main split -- main bot -18.76 (4 markets, BTC hourly +1.00 among them), race +0.14, "
           "other +0.80 (the pool-0 NY high); the Sep 9 market is outside the 7 days")
        th_ = funds_text(funds_read(fw_get([])), {}, fnow, h_)
        t_ = P(th_)
        cprint("    --- /funds with past days, the fake world ---\n    " + t_.replace("\n", "\n    "))
        _tl = [x.split() for x in t_.split("\n")]
        _i0 = t_.index("MAIN ACCOUNT (0)")
        _main = t_[_i0:t_.index("SUBACCOUNT 1")]
        ck(["Wed", "16*", "-$19.48", "1/2"] in _tl and ["Tue", "15", "+$1.19", "0/2"] in _tl
           and ["Mon", "14", "+$0.47", "1/2"] in _tl and ["Thu", "10-Sun", "13", "nothing", "settled"] in _tl
           and "7 days: -$17.82 (2 of 6 lost) = -3.4% of the $530.60 it holds now" in _main
           and "Split: main bot -$18.76 (2 of 4 lost) · race +$0.14 (0 of 1 lost) · other +$0.80 (0 of 1 lost; "
               "KXHIGHNY)" in _main
           and "Wed Sep 16 so far: -$19.48 = main bot -$19.62 (1 of 1 lost) + race +$0.14 (0 of 1 lost)\n"
               "Tue Sep 15: +$1.19 = main bot +$1.19 (0 of 2 lost)\n"
               "Mon Sep 14: +$0.47 = main bot -$0.33 (1 of 1 lost) + other +$0.80 (0 of 1 lost)\n"
               "Thu Sep 10 to Sun Sep 13: nothing settled" in _main
           and "Liquidity rewards are paid outside these records and are not counted." in t_,
           "/funds past days: the main account's days newest first (money, lost of settled), its 7-day total and "
           "its % of what it holds now, the main bot / race / other split, and each day split behind a tap")
        ck(any(x.split() == ["0", "main+race", "530.60", "81.4%", "-17.82", "(-3.4%)"] for x in t_.split("\n")),
           "/funds: the summary table carries each account's 7 days too, with its share of what it holds now")
        _s1, _s3 = t_[t_.index("SUBACCOUNT 1"):t_.index("SUBACCOUNT 3")], t_[t_.index("SUBACCOUNT 3"):]
        ck(["Wed", "16*", "+$0.05", "0/1"] in [x.split() for x in _s1.split("\n")]
           and ["Sun", "13-Tue", "15", "nothing", "settled"] in [x.split() for x in _s1.split("\n")]
           and ["Sat", "12", "-$9.90", "1/1"] in [x.split() for x in _s1.split("\n")]
           and "7 days: -$9.85 (1 of 2 lost) = -12.3% of the $80.25 it holds now" in _s1
           and ["Wed", "16*", "nothing", "settled"] in [x.split() for x in _s3.split("\n")]
           and ["Tue", "15", "+$0.50", "0/1"] in [x.split() for x in _s3.split("\n")]
           and ["Mon", "14", "-$1.70", "1/1"] in [x.split() for x in _s3.split("\n")]
           and "7 days: -$1.20 (1 of 2 lost) = -2.9% of the $41.10 it holds now" in _s3
           and t_.count("Past 7 ET days") == 3 and "Deposits and transfers are not gains." in t_
           and "to fit one message" not in t_ and len(th_) <= MAX_LEN and "Split:" not in _s1 + _s3,
           "/funds past days: each subaccount's days unsplit, empty days as one line, one message")
        # the 60 s cache
        hclk = {"t": 1000.0}
        ha = []
        hm = {}
        funds_settled(fw_get(ha), [0, 1, 3], fnow, clock=lambda: hclk["t"], memo=hm)
        n1 = len(ha)
        hclk["t"] += 30
        h2 = funds_settled(fw_get(ha), [0, 1, 3], fnow, clock=lambda: hclk["t"], memo=hm)
        n2 = len(ha)
        hclk["t"] += 31
        funds_settled(fw_get(ha), [0, 1, 3], fnow, clock=lambda: hclk["t"], memo=hm)
        ck(n1 == 5 and n2 == n1 and all(h2[n]["cached"] for n in h2) and len(ha) == 2 * n1
           and abs(funds_days(h2[0], "2026-09-16")["total"]["all"]["money"] + 17.82) < 1e-9,
           "/funds past days: a second /funds within 60 s reads nothing from Kalshi (same figures); after 60 s it "
           "reads again")
        hclk["t"] += 1
        funds_settled(fw_get(ha), [0], fnow + 86400, clock=lambda: hclk["t"], memo=hm)
        ck(len(ha) > 2 * n1, "/funds past days: a new ET day reads again even inside the 60 s")
        # failed reads: what is known is shown, the gap is named, nothing failed is kept
        ha = []
        hm = {}
        h_ = funds_settled(fw_get(ha, bad=lambda p, q: (503, "busy") if p == FUNDS_HIST_PATH and q["subaccount"] == 0
                                  and q.get("cursor") == "2" else (500, {}) if p == FUNDS_HIST_PATH
                                  and q["subaccount"] == 1 else None), [0, 1, 3], fnow, memo=hm)
        t_ = P(funds_text(funds_read(fw_get([])), {}, fnow, h_))
        ck(["Tue", "15", "+$1.19", "0/2"] in [x.split() for x in t_.split("\n")]
           and ["Thu", "10-Mon", "14", "NOT", "READ"] in [x.split() for x in t_.split("\n")]
           and "2 days read: -$18.29 (1 of 4 lost) = -3.4% of the $530.60 it holds now" in t_
           and "Split: main bot -$18.43 (1 of 3 lost) · race +$0.14 (0 of 1 lost)" in t_
           and "Tue Sep 15: +$1.19 = main bot +$1.19 (0 of 2 lost)\nThu Sep 10 to Mon Sep 14: NOT READ" in t_
           and "NOT READ: Mon 14, Sun 13, Sat 12, Fri 11, Thu 10 (HTTP 503)" in t_
           and "SUBACCOUNT 1 -- penny ladder: $80.25\ncash: crypto pool $80.25; open bets: none\n"
           "past 7 ET days: COULD NOT READ (HTTP 500)" in t_ and "7 days: -$1.20 (1 of 2 lost)" in t_
           and sorted(hm) == [3],
           "/funds past days: main's 3rd page fails -> the 2 whole days are shown, Sep 10-14 named NOT READ (the "
           "half-read Sep 14 is not shown); sub 1 fails -> said; neither failed pull is kept")
        h_ = funds_settled(fw_get([], bad=lambda p, q: "raise" if p == FUNDS_HIST_PATH and q["subaccount"] == 3
                                  else (200, {"cursor": ""}) if p == FUNDS_HIST_PATH else None), [0, 3], fnow, memo={})
        ck(h_[0]["err"] == "no 'settlements' list in Kalshi's reply" and h_[3]["err"] == "error: connection reset"
           and "past 7 ET days: COULD NOT READ (no 'settlements' list in Kalshi's reply)"
           in P(funds_text(funds_read(fw_get([])), {}, fnow, h_)),
           "/funds past days: a reply without the settlements list is an error, never 'nothing settled'; a raise is "
           "said")
        t_ = P(funds_text(funds_read(fw_get([], bad=lambda p, q: (500, {}) if p == "/portfolio/balance" else None)),
                          {}, fnow, funds_settled(fw_get([]), [0, 1, 3], fnow, memo={})))
        ck("7 days: -$17.82 (2 of 6 lost); % not shown: what it holds now was not read whole" in t_
           and "% of the $" not in t_,
           "/funds past days: no % on a balance that was not read whole")
        t_ = P(funds_text(funds_read(fw_get([], rows=[{"subaccount_number": 0, "exchange_index": 2, "balance": "0.5000"}],
                                            pos={}, brk=[])), {}, fnow, funds_settled(fw_get([]), [0], fnow, memo={})))
        cprint("    --- /funds past days, an account holding 50c ---\n    " + t_.replace("\n", "\n    "))
        ck("7 days: -$17.82 (2 of 6 lost); % not shown: it holds under $1" in t_ and "% of the $" not in t_,
           "/funds past days: no % of an account holding under $1 (a % of cents is noise)")
        hclk2 = {"t": 0.0}

        def _htick():
            hclk2["t"] += 1.0
            return hclk2["t"]
        ha = []
        hm = {}
        h_ = funds_settled(fw_get(ha), [0, 1, 3], fnow, clock=_htick, deadline_s=3, memo=hm)
        ck(h_[0]["err"] is None and h_[1]["err"] == h_[3]["err"] == "the 3 s limit for /funds ran out first"
           and sorted(hm) == [0] and "past 7 ET days: COULD NOT READ (the 3 s limit for /funds ran out first)"
           in P(funds_text(funds_read(fw_get([])), {}, fnow, h_)),
           "/funds past days: a slow Kalshi hits the history time limit -> the accounts not reached are said, not "
           "kept, and the phone is not stalled")
        # the length limit: 9 busy accounts do not fit 7 day lines each -> fewer, said, every 7-day total kept
        big_rows = [{"subaccount_number": k, "exchange_index": 2, "balance": "1000.0000"} for k in range(9)]
        big_stl = {k: [[_R("%s-26SEP%02d%s-00" % ("KXBTC15M" if j % 2 else "KXCRYPTOLEAD15M", 16 - d, "1015"),
                           "2026-09-%02dT14:15:03Z" % (16 - d), "no", yn=5, yc=1.0 + j) for d in range(7)
                        for j in range(2)] + [_R("KXBTCD-26SEP%02d10-T1" % (16 - d), "2026-09-%02dT14:00:09Z" % (16 - d),
                                                 "yes", yn=5, yc=4.0) for d in range(7)]] for k in range(9)}
        bg = fw_get([], rows=big_rows, brk=[], stl=big_stl)
        bf, bh = funds_read(bg), funds_settled(bg, range(9), fnow, memo={})
        t7 = _funds_page(bf, {}, fnow, bh, 7)
        th_ = funds_text(bf, {}, fnow, bh)
        t_ = P(th_)
        # (subaccount 4 is the FX pairs' pool-0 pot: its coin rows are the old reward test's, left out and said)
        ck(len(t7) > MAX_LEN and len(th_) <= MAX_LEN and t_.count("to fit one message") == 1
           and t_.count("\n7 days: ") == 8 and "left out: 21 markets of the old coin-race test" in t_,
           "/funds past days: when 7 day lines do not fit one message (%d chars), fewer are listed and that is said "
           "once (%d chars); all 9 accounts keep their 7-day total" % (len(t7), len(th_)))
        # routed: /funds /bank /accounts, through handle() and the poll loop
        ck(ph.funds_getter is None, "/funds reads Kalshi through botstats' getter (kauth.get, GET only) by default")
        _FUNDS_HIST.clear()
        _bs_sandbox("botstats-funds-down")                  # botstats cannot read Kalshi: /funds pulls its past days
        _bs_mode["m"] = "down"
        fa = []
        ph.funds_getter = fw_get(fa)
        ck(all(P(ph.handle(111, c_) or "").startswith("🏦 ALL ACCOUNTS: $651.95")
               and "MONEY IN EVERY ACCOUNT" in P(ph.handle(111, c_))
               for c_ in ("/funds", "/bank", "/accounts", "/Funds@pinbot")),
           "/funds, /bank and /accounts are routed to the funds page")
        t_ = P(ph.handle(111, "/funds"))
        ck(["Thu", "17*", "nothing", "settled"] in [x.split() for x in t_.split("\n")]
           and "\nThu Sep 17 so far: nothing settled\nWed Sep 16: -$19.48 = main bot" in t_
           and "Split: main bot -$18.76" in t_ and "7 days: -$17.82 (2 of 6 lost)" in t_
           and "7 days: -$9.85 (1 of 2 lost)" in t_
           and sum(1 for p, _q in fa if p == FUNDS_HIST_PATH) == 5,
           "/funds through handle() carries every account's past days (phone clock: Thu Sep 17); botstats cannot read "
           "Kalshi here, so /funds pulls them itself, and nine /funds inside 60 s read them once")
        ck(ph.handle(333, "/funds") is None, "/funds: a stranger gets nothing")
        ck("/funds" in HELP_TEXT and "/bank" in HELP_TEXT and "/accounts" in HELP_TEXT, "/funds is in /help")
        tg.push(111, "/funds")
        ph.poll_once()
        ck(tg.sent[-1][0] == 111 and "ALL ACCOUNTS: $651.95" in P(tg.sent[-1][1])
           and "main bot 85 contracts a bet" in P(tg.sent[-1][1]) and "Past 7 ET days" in P(tg.sent[-1][1]),
           "/funds through the poll loop: the paired chat gets the page, with the live log's bet size and past days")
        with open(LOG, encoding="utf-8") as _fh:
            _lg = _fh.read()
        ck(os.path.dirname(LOG) == td and "SENT: 🏦 ALL ACCOUNTS: $651.95" in _lg,
           "the self-test logs what it 'sent' to its own temp folder (the phone's words, utf-8), never the live "
           "phone bot's results/pinphone.log")
        # ONE READ (2026-10-26): botstats reads every pot whole -> the past days are its rows and /funds asks Kalshi
        # for no settlements itself; the page is exactly the one its own pull of the same rows gives
        _bs_sandbox("botstats-funds")
        _bs_mode["m"] = "planted"
        _FUNDS_HIST.clear()
        fa = []
        ph.funds_getter = fw_get(fa)
        t_ = ph.handle(111, "/funds")
        _own = funds_text(funds_read(fw_get([])), funds_sizes(ph.ledger.results, ph.active()), now["t"],
                          funds_settled(lambda p, q: _bs_fake(p, dict(q, subaccount=str(q["subaccount"]))), [0, 1, 3],
                                        now["t"], memo={}), active=ph.active())
        ck(str(t_) == str(_own) and not any(p == FUNDS_HIST_PATH for p, _q in fa) and not _FUNDS_HIST
           and "7 days: -$14.00 (2 of 5 lost)" in P(t_) and "7 days: +$0.04 (0 of 1 lost)" in P(t_),
           "/funds past days from botstats' rows: no settlements read of its own, and the same page (main -$14.00, "
           "ladder +$0.04) as this page's own pull of the same rows")
        _FUNDS_HIST.clear()
    globals()["LOG"] = _st_log
    _pl.LEDGER = _pl_sv
    _bsm.RESULTS = _bs_saved[0]
    _bsm._MEMO.clear()
    _bsm._MEMO.update(_bs_saved[1])
    _bsm._BACK.clear()
    _bsm._BACK.update(_bs_saved[2])

    # 2026-10-23: a send the CONNECTION drops is sent again, marked late; a refused one (HTTP 400) is not
    class _FlakyTG(FakeTelegram):
        def __init__(self):
            FakeTelegram.__init__(self)
            self.fail = []

        def send(self, chat_id, text):
            if self.fail:
                raise self.fail.pop(0)
            FakeTelegram.send(self, chat_id, text)
    _ftg = _FlakyTG()
    _rclk = {"t": 1792800000.0}
    _rph = Phone({"chat_id": 5}, _ftg, ledger=Ledger(results=tempfile.mkdtemp()), now_fn=lambda: _rclk["t"])
    _ftg.fail = [urllib.error.URLError("_ssl.c:1064: The handshake operation timed out")]
    _rph.say(Html("🟢 <b>STATE CHANGED</b>: DOWN -> TRADING"))
    _q1 = len(_rph._resend)
    _rph.resend_tick()                                      # not due yet: nothing sent
    _n_early = len(_ftg.sent)
    for _x in _rph._resend:
        _x["next"] = 0.0
    _ftg.fail = [ConnectionResetError(10054, "forcibly closed")]
    _rph.resend_tick()                                      # still down: kept for later
    _kept = len(_rph._resend)
    for _x in _rph._resend:
        _x["next"] = 0.0
    _rclk["t"] += 120
    _rph.resend_tick()
    _late = P(_ftg.sent[-1][1]) if _ftg.sent else ""
    ck(_q1 == 1 and _n_early == 0 and _kept == 1 and not _rph._resend and len(_ftg.sent) == 1
       and _late.startswith("⏱ Sent late -- from ") and "STATE CHANGED: DOWN -> TRADING" in _late,
       "RESEND: an alert the connection dropped waits, is tried again while the connection is down, and goes "
       "once it is back, marked late: %r" % _late[:80])
    _ftg.fail = [urllib.error.HTTPError("u", 400, "Bad Request", None, None)]
    _rph.say("plain words")
    _rclk["t"] += 10 * RESEND_FOR_S
    _ftg.fail = [urllib.error.URLError("timed out")]
    _rph.say("old news")
    for _x in _rph._resend:
        _x["next"] = 0.0
    _rclk["t"] += RESEND_FOR_S + 1
    _rph.resend_tick()
    ck(not _rph._resend and len(_ftg.sent) == 1 and net_error(ConnectionResetError()) and not net_error(
        urllib.error.HTTPError("u", 400, "x", None, None)) and net_error(urllib.error.HTTPError("u", 502, "x", None, None)),
       "RESEND: a message Telegram refused (400) is not repeated, and one older than %d min is given up"
       % (RESEND_FOR_S // 60))
    ck(halt_words("halt", "pintake halted: order pin-1 outcome UNKNOWN (status -1)").startswith("stopped itself")
       and halt_words("stop_file", "") .startswith("its stop file") and halt_words("exit", "stop file") == "it exited (stop file)"
       and halt_words("odd", "x" * 300) == ("odd " + "x" * 300)[:140],
       "a logged stop reads in plain words; an unknown one keeps its own text, one line")

    # ---- /speed and /server (2026-10-27: every bot moved to the AWS server in Ohio) ----------------------------------
    # SigV4 against AWS's own published test vectors (the aws-sig-v4 test suite, as kept in awslabs/aws-c-auth:
    # get-vanilla, get-vanilla-query-order-key-case, and post-x-www-form-urlencoded with the body hash signed)
    _ak, _sk, _adt = "AKIDEXAMPLE", "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", "20150830T123600Z"
    _sh1, _sg1 = sigv4_sign("GET", "https://example.amazonaws.com/", "us-east-1", "service", _ak, _sk, amz_date=_adt)
    _sh2, _sg2 = sigv4_sign("GET", "https://example.amazonaws.com/?Param2=value2&Param1=value1", "us-east-1", "service",
                            _ak, _sk, amz_date=_adt)
    _sh3, _sg3 = sigv4_sign("POST", "https://example.amazonaws.com/", "us-east-1", "service", _ak, _sk, b"Param1=value1",
                            {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": "13"},
                            amz_date=_adt, sign_body=True)
    ck(_sg1 == "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31"
       and _sh1["authorization"] == ("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20150830/us-east-1/service/aws4_request, "
                                     "SignedHeaders=host;x-amz-date, Signature=" + _sg1)
       and _sg2 == "b97d918cfa904a5beff61c982a1b6f458b799221646efd99d3219ec94cdf2500"
       and _sg3 == "d3875051da38690788ef43de4db0d8f280229d82040bfac253562e56c3f20e0b"
       and _sh3["x-amz-content-sha256"] == "9095672bbd1f56dfc5b65f3e153adc8731a4a654192329106275f4c7b24d0b6e",
       "SigV4 signer (hashlib + hmac, no boto3) matches AWS's published test vectors: get-vanilla, the query sorted by "
       "key, and a signed POST body")
    ck(SERVER_SINCE == "2026-10-27T04:20:52Z" and SERVER_SINCE_EPOCH == 1793074852 and SPEED_HOME_DAYS == 14,
       "the move's moment is one constant (SERVER_SINCE, 00:20:52 ET 10-27); home = the 14 days before it")

    _lg_sv, _aws_sv, _tails_sv = globals()["LOG"], dict(_AWS), dict(_TAILS)
    with tempfile.TemporaryDirectory() as _tds:
        globals()["LOG"] = os.path.join(_tds, "pinphone.log")
        _sv = SERVER_SINCE_EPOCH
        _srvf, _homef = "pinrun-live-20261027T042114Z.jsonl", "pinrun-live-20261018T110121Z.jsonl"

        def _iso(e):
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(e))

        def _po(dt, tk, asked, got, ms, f=_homef):
            return {"t": _sv + dt, "tk": tk, "filled": got, "asked": asked, "latency_ms": ms, "file": f,
                    "status": "executed" if got else "canceled"}
        # home (the 14 days before the move): 4 orders, 1 got nothing, 30 of 50 contracts, 40/45/50/70 ms
        # server (from the move on): 3 orders, none empty, 35 of 40 contracts, 12/15/18 ms; the one AT the move is the
        # server's, the one a second before it home's; 15 days back and another bot's log are left out
        _pord = [_po(-15 * 86400, "OLD", 10, 0, 500), _po(-13 * 86400, "H4", 10, 10, 70), _po(-5 * 86400, "H3", 20, 10, 45),
                 _po(-3 * 86400, "H2", 10, 0, 50), _po(-1, "H1", 10, 10, 40),
                 dict(_po(-2, "CMD", 10, 0, 999), file="cmdlive-20260917T000000Z.jsonl"),
                 _po(0, "KXA15M-X", 10, 10, 15, _srvf), _po(120, "KXB15M-X", 10, 5, 12, _srvf),
                 _po(180, "KXC15M-X", 20, 20, 18, _srvf)]

        def _wj(name, rows, mtime):
            p_ = os.path.join(_tds, name)
            with open(p_, "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
            os.utime(p_, (mtime, mtime))
            return p_
        # the server log's settled legs: A +20c, B +10c and its hedge -5c (= +$0.25 on the 15 contracts got in A and B);
        # `realised` is the run's running total and must NOT be read; a leg before the move, a market not ordered on
        # the server, and the home log's rows (written before the move) are left out; C is still open
        _srvp = _wj(_srvf, [
            {"kind": "start", "t": _iso(_sv + 22)},
            {"kind": "order", "t": _iso(_sv), "ticker": "KXA15M-X", "filled": 10.0},
            {"kind": "settled", "t": _iso(_sv - 10), "ticker": "KXA15M-X", "pnl_c": 1000.0, "realised": 10.0},
            {"kind": "settled", "t": _iso(_sv + 900), "ticker": "KXA15M-X", "pnl_c": 20.0, "realised": 99.0},
            {"kind": "settled", "t": _iso(_sv + 900), "ticker": "KXB15M-X", "want": "no", "pnl_c": 10.0, "realised": 99.1},
            {"kind": "settled", "t": _iso(_sv + 915), "ticker": "KXB15M-X", "want": "yes", "pnl_c": -5.0, "realised": 99.05},
            {"kind": "settled", "t": _iso(_sv + 930), "ticker": "KXZZZ15M-X", "pnl_c": 500.0}], _sv + 3600)
        _wj(_homef, [{"kind": "settled", "t": _iso(_sv + 5), "ticker": "KXA15M-X", "pnl_c": 777.0}], _sv - 86400)
        # the FX taker: home 2 orders Kalshi took (one empty), a refusal (404) left out; server 1 order at 15 ms.
        # The coin race: one home order; no forecaster log here at all.
        _wj("fxtake-live-orders.jsonl", [
            {"t": _iso(_sv - 2 * 86400) + "", "kind": "placed", "status": 201, "filled": 10.0, "rtt": 0.140,
             "body": {"ticker": "KXGOLD15M-X", "count": "10.00"}},
            {"t": _iso(_sv - 2 * 86400 + 900), "kind": "placed", "status": 201, "filled": 0.0, "rtt": 0.150,
             "body": {"ticker": "KXWTI15M-X", "count": "10.00"}},
            {"t": _iso(_sv - 86400), "kind": "placed", "status": 404, "filled": 0.0, "rtt": 0.142,
             "body": {"ticker": "KXEURUSD15M-X", "count": "10.00"}},
            {"t": _iso(_sv - 86400), "kind": "fill", "ticker": "KXGOLD15M-X", "n": 10.0},
            {"t": _iso(_sv + 600), "kind": "placed", "status": 201, "filled": 10.0, "rtt": 0.015,
             "body": {"ticker": "KXGOLD15M-Y", "count": "10.00"}}], _sv + 600)
        _wj("pinracepenny-live.jsonl", [{"kind": "live_order", "t": _iso(_sv - 86400), "ticker": "KXCRYPTOLEAD15M-X",
                                         "count_asked": 1.0, "filled": 1.0, "status": "executed", "status_code": 201}],
            _sv - 86400)
        _snow = _sv + 3 * 86400                                   # the phone's clock: 3 days after the move
        _TAILS.clear()
        _sd = speed_gather(_tds, _pord, _snow)
        _hs, _ss, _sm, _se = _sd["pin"]["home"], _sd["pin"]["server"], _sd["pin"]["money"], _sd["pin"]["est"]
        ck(_hs["n"] == 4 and _hs["zero"] == 1 and _hs["got"] == 30 and _hs["asked"] == 50
           and abs(_hs["got_share"] - 0.6) < 1e-9 and _hs["med_ms"] == 47.5 and _hs["p90_ms"] == 70
           and _ss["n"] == 3 and _ss["zero"] == 0 and _ss["got"] == 35 and _ss["asked"] == 40
           and abs(_ss["got_share"] - 0.875) < 1e-9 and _ss["med_ms"] == 15 and _ss["p90_ms"] == 18,
           "/speed: home vs server split at SERVER_SINCE (an order AT the move is the server's, one a second before it "
           "home's; 15 days back and another bot's log left out): home 4 orders, 47.5 ms median, 1 empty, 30/50 "
           "contracts; server 3 orders, 15 ms, none empty, 35/40")
        ck(abs(_sm["usd"] - 0.25) < 1e-9 and _sm["contracts"] == 15 and _sm["markets"] == 2 and _sm["open_contracts"] == 20
           and abs(_sm["per"] - 0.25 / 15) < 1e-12,
           "/speed: $ per filled contract on the server = the settled legs' pnl_c (+20c, +10c, a -5c hedge = +$0.25) "
           "over the 15 contracts got in those markets; `realised` (the run's running total), a leg before the move, a "
           "market not ordered there and the home log are left out; the open market's 20 contracts wait")
        ck(abs(_se["d_share"] - 0.275) < 1e-9 and abs(_se["extra"] - 11.0) < 1e-9
           and abs(_se["usd"] - 11.0 * 0.25 / 15) < 1e-9 and abs(_se["per_day"] - _se["usd"] / 3.0) < 1e-9,
           "/speed's $ estimate on the planted case: (87.5% - 60%) x 40 asked on the server = 11 extra contracts, x "
           "$0.25/15 a filled contract = +$0.1833 (+$0.0611 a day over 3 days)")
        _st1 = speed_html(_sd, 1000.0)
        _pt1 = P(_st1)
        ck(_pt1.startswith("⏳ SPEED: too early to tell, 3 orders so far on the server (the bar is 50)")
           and "(87.5% - 60.0%) x 40 asked on the server = +11 extra contracts" in _pt1
           and "x +$0.0167 a filled contract (+$0.25 on 15 contracts in 2 markets settled on the server) = +$0.18 "
               "(+0.02% of the main account's $1,000.00 bank)" in _pt1
           and "extra contracts = (server got/asked - home got/asked) x contracts asked on the server; $ = extra "
               "contracts x the $ made per filled contract on the server" in _pt1
           and "an estimate, not a proof" in _pt1 and "⏳ Too early to tell: 3 orders so far" in _pt1
           and "Median        48 ms  15 ms" in _pt1 and "Got nothing   25.0%     0%" in _pt1,
           "/speed under 50 server orders says 'too early to tell, 3 orders so far', and still shows the formula, worked, "
           "with the bank's %%: %r" % _pt1[:120])
        ck("FX taker: home 50% got something (1 of 2 orders, 145 ms) · server 100% got something (1 of 1 order, 15 ms) "
           "· too few on the server to tell" in _pt1
           and "Forecaster: skipped: no log here (forecaster-live-orders.jsonl)" in _pt1
           and "Coin race: home 100% got something (1 of 1 order) · server: no orders · its log keeps no send time" in _pt1
           and "Ladder: skipped: its bids rest on the book" in _pt1,
           "/speed's other bots: the FX taker home vs server (a 404 refusal left out), a missing log says so, the coin "
           "race has no send time, the ladder is skipped and says why")
        ck(not tg_html_problems(_st1) and fits(_st1) and len(split_html(_st1)) == 1 and "\u2014" not in _pt1,
           "/speed: Telegram-valid, one message, no em-dash")
        _st2 = P(speed_html(_sd, 1000.0, min_orders=3))
        ck(_st2.startswith("⚡ SPEED: 15 ms on the server, was 48 ms at home (median, send to answer)")
           and "Too early" not in _st2 and "About +$0.06 a day at this pace" in _st2,
           "/speed past the bar: the headline is the two medians, and the $ a day shows")
        _st3 = P(speed_html(speed_gather(_tds, [o for o in _pord if o["t"] < _sv], _snow), 1000.0))
        ck(_st3.startswith("⏳ SPEED: too early to tell, no pin orders on the server yet")
           and "Not yet: no pin orders on the server yet." in _st3,
           "/speed with no server orders: too early, and no $ guessed")
        # read once, then only what was added: a second gather reads no byte; a leg appended is picked up
        _off0 = _TAILS[(_srvp, "kind", "settled")]["off"]
        speed_gather(_tds, _pord, _snow)
        _off1 = _TAILS[(_srvp, "kind", "settled")]["off"]
        _sz0 = os.path.getsize(_srvp)
        with open(_srvp, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "settled", "t": _iso(_sv + 1900), "ticker": "KXC15M-X", "pnl_c": 30.0}) + "\n")
        os.utime(_srvp, (_sv + 3700, _sv + 3700))
        _sd4 = speed_gather(_tds, _pord, _snow)
        ck(_off0 == _off1 == _sz0 and _TAILS[(_srvp, "kind", "settled")]["off"] == os.path.getsize(_srvp)
           and abs(_sd4["pin"]["money"]["usd"] - 0.55) < 1e-9 and _sd4["pin"]["money"]["contracts"] == 35,
           "/speed reads each log once, then only the bytes added (a new settled leg: +$0.30 on C's 20 contracts)")
        # through the phone: the paired chat, the Ledger's own orders and bank
        _sL = Ledger(results=_tds)
        _sL.refresh = lambda: False
        _sL.orders = list(_pord)
        _sL.bank = lambda: {"bank": 1000.0, "t": _snow}
        _sclk = {"t": _snow}
        _sph = Phone({"chat_id": 111}, FakeTelegram(), ledger=_sL, now_fn=lambda: _sclk["t"])
        _t0 = time.time()
        _hsp = _sph.handle(111, "/speed")
        ck(P(_hsp).startswith("⏳ SPEED: too early to tell, 3 orders so far") and str(_hsp) == str(speed_html(
            speed_gather(_tds, _pord, _snow, active=_sph.active()), 1000.0)) and _sph.handle(333, "/speed") is None
           and time.time() - _t0 < 2.0,
           "/speed through handle(): the paired chat gets the page in under 2 s; a stranger gets nothing")

        # ---- /server: planted machine, Kalshi, pots and AWS
        _AWS.clear()
        _mach = {"host": "EC2AMAZ-TEST", "ncpu": 2, "cpu": 23.4, "py_cpu": 18.2, "py_n": 14, "py_mem": 1.6e9,
                 "mem_total": 4.0e9, "mem_avail": 1.1e9, "mem_load": 72, "commit": 3.1e9, "commit_limit": 5.2e9,
                 "disk_free": 31.2e9, "disk_total": 53.7e9, "uptime_s": 6120.0, "reboot": False, "reboot_why": None,
                 "sample_s": 0.5, "errs": []}
        _pots = {"pots": {"0": {"value": 1246.86, "open": 12.30, "cash": 1234.56, "why": None, "t": _snow - 600},
                          "1": {"value": 683.54, "open": 0, "cash": 683.54, "why": None, "t": _snow - 600},
                          "2": {"value": None, "open": None, "cash": 129.49, "why": "the last cash read failed",
                                "t": _snow - 600}},
                 "total": None, "t": _snow - 600}
        _sph.machine_fn = lambda: dict(_mach)
        _sph.ping_fn = lambda: {"ms": [4.1, 5.2, 6.3], "dns_ms": 1.2, "ip": "1.2.3.4", "err": None, "t": _snow}
        _sph.pots_fn = lambda: _pots
        _awsq = []

        def _no_imds(method, url, headers=None, body=None, timeout=None):
            _awsq.append((method, url))
            raise urllib.error.URLError("timed out")
        _sph.aws_http = _no_imds
        _sv1 = _sph.handle(111, "/server")
        _pv1 = P(_sv1)
        ck(_pv1.startswith("🖥 SERVER: CPU 23% · memory 72% used · disk 31.2 GB free · Kalshi 4.1 ms")
           and "this machine: EC2AMAZ-TEST" in _pv1 and "CPU now   23% (2 cores, 0.5 s)" in _pv1
           and "  python  18% · 14 processes" in _pv1 and "Memory    2.9 GB of 4.0 GB (72%)" in _pv1
           and "Disk C:   31.2 GB free of 54 GB" in _pv1 and "Up        1 h 42 min" in _pv1
           and "Windows Update: no restart waiting" in _pv1
           and "Kalshi: 4.1 ms to connect (best of 3: 4.1 ms, 5.2 ms, 6.3 ms; name lookup 1.2 ms)" in _pv1
           and "The pin bot's own orders here: median 15 ms send to answer, 0% got nothing (home: 48 ms, 25.0%)" in _pv1,
           "/server's machine section from planted readings: CPU and the python share, memory, disk, uptime, Windows "
           "Update, the time to Kalshi, the pin bot's own order times: %r" % _pv1[:100])
        ck("AWS cost: not connected yet (needs the read-only billing role on the server, see /server help)" in _pv1
           and "Estimate from the price list: about $51.45 a month ($1.69 a day)" in _pv1
           and "Windows t3.medium $0.06 an hour ($43.80), 50 GB disk $4.00, public IPv4 $3.65" in _pv1
           and "budget $120.00 a month" in _pv1 and _awsq == [("PUT", AWS_IMDS + "/latest/api/token")],
           "/server with no metadata service (the call fails): AWS cost says not connected, points to /server help, and "
           "the price-list estimate shows, labelled; one metadata call, nothing else")
        # v-tg-active: a pot is named for the bots running now (this Phone reads this machine's process table)
        _sact = _sph.active()
        _n0, _n2 = funds_short(0, _sact), funds_short(2, _sact)
        ck("Funds: all pots ?" in _pv1 and any(x.split()[:2] == [_n0, "1,246.86"] for x in _pv1.split("\n"))
           and any(x.split()[:2] == [_n2, "?"] for x in _pv1.split("\n"))
           and "⚠️ %s: the last cash read failed; its cash alone $129.49" % _n2 in _pv1,
           "/server's funds from botstats' cache: a pot whose last read failed shows '?' and why, and no total is made up")
        _spl = "\n".join(_server_pots_lines(_pots, _snow, ("pin", "ladder", "fx", "jumpband"))[0])
        ck(any(x.split()[:2] == ["main", "1,246.86"] for x in _spl.split("\n"))
           and any(x.split()[:2] == ["idle", "?"] for x in _spl.split("\n")) and "forecaster" not in _spl
           and funds_short(3, ("pin", "jumpband")) == "jump band" and funds_short(0, ("pin", "race")) == "main+race",
           "/server's pots with the coin race paused and the forecaster stopped: 'main' and 'idle', never a hidden bot's "
           "name; subaccount 3 is the jump band's")
        _sph.handle(111, "/server")
        ck(len(_awsq) == 1, "/server: a missing metadata service is remembered for 5 minutes (no second call)")
        ck(not tg_html_problems(_sv1) and fits(_sv1) and len(split_html(_sv1)) == 1 and "\u2014" not in _pv1,
           "/server: Telegram-valid, one message, no em-dash")
        # the role exists: IMDSv2 token -> role -> keys -> identity; then Budgets and Cost Explorer, signed
        _AWS.clear()
        _awsq[:] = []

        def _aws_world(method, url, headers=None, body=None, timeout=None):
            _awsq.append((method, url, dict(headers or {}), body))
            if url == AWS_IMDS + "/latest/api/token":
                return (200, b"TOKEN123") if method == "PUT" and headers.get(
                    "X-aws-ec2-metadata-token-ttl-seconds") else (400, b"")
            if url.startswith(AWS_IMDS) and (headers or {}).get("X-aws-ec2-metadata-token") != "TOKEN123":
                return 401, b""
            if url == AWS_IMDS + "/latest/meta-data/iam/security-credentials/":
                return 200, b"kals-server-billing"
            if url == AWS_IMDS + "/latest/meta-data/iam/security-credentials/kals-server-billing":
                return 200, json.dumps({"Code": "Success", "AccessKeyId": "ASIATEST", "SecretAccessKey": "SECRETTEST",
                                        "Token": "SESSIONTOKEN", "Expiration": _iso(_snow + 6 * 3600)}).encode()
            if url == AWS_IMDS + "/latest/dynamic/instance-identity/document":
                return 200, json.dumps({"accountId": "001634075101", "region": "us-east-2"}).encode()
            tgt = (headers or {}).get("x-amz-target")
            if url == "https://budgets.amazonaws.com/" and tgt == "AWSBudgetServiceGateway.DescribeBudgets":
                return 200, json.dumps({"Budgets": [{"BudgetName": "kals-monthly", "BudgetType": "COST",
                                                     "TimeUnit": "MONTHLY",
                                                     "BudgetLimit": {"Amount": "120.0", "Unit": "USD"},
                                                     "CalculatedSpend": {"ActualSpend": {"Amount": "1.234", "Unit": "USD"},
                                                                         "ForecastedSpend": {"Amount": "8.4",
                                                                                             "Unit": "USD"}},
                                                     "LastUpdatedTime": _snow - 7200}]}).encode()
            if url == "https://ce.us-east-1.amazonaws.com/" and tgt == "AWSInsightsIndexService.GetCostAndUsage":
                yd = time.strftime("%Y-%m-%d", time.gmtime(_snow - 86400))
                return 200, json.dumps({"ResultsByTime": [
                    {"TimePeriod": {"Start": yd}, "Estimated": True, "Groups": [
                        {"Keys": ["Amazon Elastic Compute Cloud - Compute"],
                         "Metrics": {"UnblendedCost": {"Amount": "1.00", "Unit": "USD"}}},
                        {"Keys": ["EC2 - Other"], "Metrics": {"UnblendedCost": {"Amount": "0.20", "Unit": "USD"}}}]}]}
                ).encode()
            return 404, b"{}"
        _sph.aws_http = _aws_world
        _pots2 = {"pots": {"0": {"value": 2000.0, "open": 0, "cash": 2000.0, "why": None, "t": _snow - 60}},
                  "total": 2000.0, "t": _snow - 60}
        _sph.pots_fn = lambda: _pots2
        _mach["reboot"], _mach["reboot_why"] = True, "Windows Update"
        _pv2 = P(_sph.handle(111, "/server"))
        _bq = [x for x in _awsq if x[1] == "https://budgets.amazonaws.com/"]
        _bh = _bq[0][2] if _bq else {}
        _rh, _rsig = sigv4_sign("POST", "https://budgets.amazonaws.com/", "us-east-1", "budgets", "ASIATEST",
                                "SECRETTEST", _bq[0][3] if _bq else b"",
                                {"Content-Type": "application/x-amz-json-1.1",
                                 "X-Amz-Target": "AWSBudgetServiceGateway.DescribeBudgets"}, "SESSIONTOKEN",
                                amz_date=_bh.get("x-amz-date"))
        ck(len(_bq) == 1 and _bh.get("authorization") == _rh["authorization"] and _bh.get("x-amz-security-token")
           == "SESSIONTOKEN" and json.loads(_bq[0][3].decode()) == {"AccountId": "001634075101", "MaxResults": 20}
           and "SignedHeaders=content-type;host;x-amz-date;x-amz-security-token;x-amz-target," in _bh["authorization"],
           "/server's Budgets call: the role's short-lived keys from IMDSv2, the account from the instance's identity, "
           "the request signed (SigV4, the session token signed too)")
        ck("This month so far: $1.23 of the $120.00 budget (1%) = 0.06% of all pots" in _pv2
           and "AWS's forecast for October: $8.40 = 0.42% of all pots" in _pv2
           and "Cost Explorer: this month $1.20 = 0.06% of all pots · yesterday (UTC) $1.20" in _pv2
           and "By service: EC2 instance $1.00, EC2 other (disk, data) $0.20" in _pv2
           and "⚠️ Windows Update waits for a restart" in _pv2 and "a restart is waiting (Windows Update)" in _pv2
           and "not connected" not in _pv2,
           "/server connected: this month's spend against the budget, AWS's forecast, Cost Explorer by service, each "
           "with its share of all pots; a waiting Windows restart is said loudly")
        _n0 = len(_awsq)
        _sclk["t"] = _snow + 1800
        _sph.handle(111, "/server")
        _n1 = len(_awsq)
        _sclk["t"] = _snow + 3601
        _sph.handle(111, "/server")
        _new = [x[1] for x in _awsq[_n1:]]
        ck(_n1 == _n0 and _new == ["https://budgets.amazonaws.com/"],
           "/server's AWS reads are cached: nothing again inside an hour; after an hour the free Budgets read only "
           "(Cost Explorer, $0.01 a read, waits 6 hours); the role's keys are kept until they near expiry")
        _hl = P(_sph.handle(111, "/server help"))
        ck(_hl.startswith("🖥 /server help: connect the AWS cost") and "IAM → Roles → Create role" in _hl
           and "Use case: EC2" in _hl and "Role name kals-server-billing" in _hl
           and "EC2 → Instances → tick kals-bot → Actions → Security → Modify IAM role → pick kals-server-billing" in _hl
           and '"budgets:ViewBudget","ce:GetCostAndUsage"' in _hl and not tg_html_problems(SERVER_HELP)
           and fits(SERVER_HELP) and "\u2014" not in _hl,
           "/server help: the console steps (the read-only policy, the role for EC2, attaching it to kals-bot)")
        ck("/speed" in HELP_TEXT and "/server" in HELP_TEXT and "<code>/server help</code>" in HELP_TEXT
           and not tg_html_problems(HELP_TEXT) and fits(HELP_TEXT),
           "/speed and /server are in /help")
        ck(_tgc().kind_of("/speed") is None and _tgc().kind_of("/server") is None,
           "/speed and /server send words only (no chart; /help says so)")
    globals()["LOG"] = _lg_sv
    _AWS.clear()
    _AWS.update(_aws_sv)
    _TAILS.clear()
    _TAILS.update(_tails_sv)
    # the real readers on this machine: Windows answers, nothing raises, and a waiting restart is a yes / no / unknown
    _mr = machine_read(0.1)
    _rb = reboot_pending()
    ck(_mr["mem_total"] and _mr["disk_free"] and _mr["uptime_s"] and _mr["cpu"] is not None and 0 <= _mr["cpu"] <= 100
       and _mr["py_n"] and _mr["py_n"] >= 1 and _mr["mem_load"] is not None and _rb[0] in (True, False, None),
       "machine_read on this machine (ctypes, no psutil): CPU %.0f%%, memory %s%%, %s free on C:, %d python "
       "process(es), up %s; errors: %s" % (_mr["cpu"] or -1, _mr["mem_load"], _gb(_mr["disk_free"]), _mr["py_n"] or 0,
                                          _span_words(_mr["uptime_s"] or 0), _mr["errs"] or "none"))

    # 2026-10-30: the clock-change days. Every 'today', 'yesterday', 'since midnight' and 7-day window on the phone
    # starts at et_day_start / bs.day_start, which read the ET offset at NOON until today: on 2026-11-01 (clocks back
    # at 2 AM) that put midnight at 05:00Z, an hour late (the 12-1 AM hour booked to Oct 31, the 8 AM brief an hour
    # late); on 2026-03-08 an hour early.
    import botstats as _bsd
    _starts = {"2026-10-29": (2026, 10, 29, 4), "2026-11-01": (2026, 11, 1, 4), "2026-11-02": (2026, 11, 2, 5),
               "2026-03-08": (2026, 3, 8, 5), "2026-03-09": (2026, 3, 9, 4)}
    ck(all(et_day_start(k) == _bsd.day_start(k) == calendar.timegm(v + (0, 0)) for k, v in _starts.items()),
       "et_day_start and bs.day_start across both clock changes: Oct 29 04:00Z, Nov 1 04:00Z, Nov 2 05:00Z, Mar 8 "
       "05:00Z, Mar 9 04:00Z")
    ck(all(et_day(et_day_start(k)) == k and et_day(et_day_start(k) - 1) == day_minus(k, 1) == _bsd.shift_day(k, -1)
           for k in _starts)
       and {k: (et_day_start(day_minus(k, -1)) - et_day_start(k)) / 3600.0 for k in _starts}
       == {"2026-10-29": 24.0, "2026-11-01": 25.0, "2026-11-02": 24.0, "2026-03-08": 23.0, "2026-03-09": 24.0},
       "day_minus and shift_day agree with the clock across both changes and the days join up: Nov 1 is 25 hours, "
       "Mar 8 is 23, the rest 24")
    print("pinphone legacy checks: OK")


def run():
    """selftest() with phone.shared's module dict as its globals, the runtime's names lent for the run (removed after).
    Raises SystemExit('pinphone selftest: FAILED -- ...') on the first failing check, as it always did."""
    os.environ["KALS_TESTING"] = "1"
    from phone import app as A
    from phone import router as RT
    from phone import shared as S
    from phone.context import Ctx
    g = vars(S)
    lent = {"Phone": A.Phone, "Ctx": Ctx, "_router": RT}
    added = [k for k in lent if k not in g]
    for k in added:
        g[k] = lent[k]
    try:
        types.FunctionType(selftest.__code__, g, "selftest")()
    finally:
        for k in added:
            g.pop(k, None)


if __name__ == "__main__":
    run()
