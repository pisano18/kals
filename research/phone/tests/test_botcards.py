"""test_botcards.py -- phone/render/botcards.py: the bot cards moved out of pinphone (v-tg-rebuild step 9, lane D2).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_botcards.py   (exit 0 = every test passed)
The renderers' own behaviour is held by pinphone's self-test and the golden replay (byte-identical); here: pinphone's
names ARE botcards' (one implementation, re-exported), botcards never imports pinphone, and a few direct checks.
"""
import ast
import os
import re

from _dlane import RESEARCH, pp, run

import phone.render.botcards as B

SRC = os.path.join(RESEARCH, "phone", "render", "botcards.py")


def _defined():
    with open(SRC, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            out.append(node.name)
        elif isinstance(node, ast.Assign):
            out += [t.id for t in node.targets if isinstance(t, ast.Name)]
    return out


def test_pinphone_reexports_every_name():
    names = _defined()
    assert len(names) >= 60, names
    for n in ("bs_bot_html", "bs_all_html", "bs_all_text", "bs_money_table", "bs_days_table", "bs_headline",
              "bots_window_table", "bots_avg_table", "earlier_lines", "main_words", "nice_coin", "halt_words", "dot", "ret"):
        assert n in names, n
    for n in names:
        assert getattr(pp, n) is getattr(B, n), "pinphone.%s is not botcards.%s" % (n, n)


def test_no_pinphone_import_and_utf8_opens():
    with open(SRC, encoding="utf-8") as fh:
        src = fh.read()
    for bad in (r"(?<!\w)import\s+pinphone(?!\w)", r"(?<!\w)from\s+pinphone\s+import(?!\w)", r"(?<!\w)urllib(?!\w)",
                r"(?<!\w)subprocess(?!\w)", r"(?<!\w)do_(start|pause|stop)(?!\w)"):
        assert not re.search(bad, src), bad
    for m in re.finditer(r"(?<![\w.])open\(([^()]*)\)", src):
        assert "encoding=" in m.group(1), m.group(0)


def test_small_helpers():
    assert (B.dot(None), B.dot(0.004), B.dot(0.01), B.dot(-0.01)) == ("⚪", "⚪", "🟢", "🔴")
    assert (B.ret(1.0, 50.0), B.ret(1.0, 0), B.ret(None, 5), B.ret(-1, 300, 2)) == ("+2.0%", "", "", "-0.33%")
    assert B.halt_words("stop_file", "").startswith("its stop file")
    assert B.nice_coin("KXCRYPTOLEAD15M-26OCT301300") == "coin race" and B.nice_coin("KXBTCD-26OCT3012-T1") == "BTC hourly"
    assert B._day_long("2026-10-25") == "Sun Oct 25" and B._day_long(None) == "None"
    assert B.main_sharers(["pin"]) == [] and B.main_shared(["pin", "race"], " and ") == "pin and race"
    assert B.BOT_CMD_OF["forecaster"] == "/fc" and B.BOT_CMDS["/wx"] == "weather"


def test_money_table_and_days_table():
    w = {"markets": 3, "money": 1.5, "return_pct": 2.0, "pot_pct": 0.5, "pot": 300.0}
    tbl, base = B.bs_money_table({"today": w, "yesterday": None, "last_7_days": {"markets": 0},
                                  "this_month": dict(w, label="October"), "all_time": dict(w, pot_kind="money_in")})
    tbl = "\n".join(tbl)
    assert base == 300.0 and "unknown -- Kalshi unread" in tbl and "nothing settled yet" in tbl and "Oct " in tbl
    assert "+0.50%*" in tbl
    # v-tg-30d (step 12): the last 30 days between the 7 days and the month -- Today, Yest, 7 days, 30 days, <month>, All
    tbl, _b = B.bs_money_table({"today": w, "yesterday": w, "last_7_days": w, "last_30_days": dict(w, money=42.0),
                                "this_month": dict(w, label="October"), "all_time": dict(w, pot_kind="money_in")})
    firsts = [ln.split()[0] for ln in tbl[1:]]
    assert firsts == ["Today", "Yest", "7", "30", "Oct", "All"], tbl
    assert "+$42.00" in tbl[4] and tbl[4].startswith("30 days"), tbl
    d = B.bs_days_table([{"label": "Thu 10/29", "markets": 2, "money": -1.0, "return_pct": None, "put_in": 40.0,
                          "pot_pct": None, "lost": 1}, {"label": "Wed 10/28", "markets": 0}], unit="leg")
    d = "\n".join(d)
    assert "Legs" in d and "-2.5%" in d and "nothing settled" in d


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_botcards"))
