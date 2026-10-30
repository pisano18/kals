"""test_fmt_merge.py -- rebuild step 12 (lane P): the number words the command modules had copied from pinphone are
botdata.fmt's now (dot, pct_of, pct1, ret, of100) and read_json is botdata.paths'; each gives the frozen legacy phone's
answer for every input tried, and the modules that held a copy use the shared one.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_fmt_merge.py
"""
import json
import os
import sys
import tempfile

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dlane import run                                              # noqa: E402
from _legacy import pp                                              # noqa: E402  (pinphone_legacy)
from botdata import fmt, paths                                      # noqa: E402

MONEY = [None, 0, 0.0, 0.004, 0.0045, 0.005, -0.004, -0.0045, -0.005, 0.01, -0.01, 1, -1, 1234.567, -0.3333]
PAIRS = [(0, 0), (0, 5), (1, 3), (3, 3), (4, 3), (-1, 3), (2, 7), (26.31, 99.0), (1, None), (5, 0.0)]


def test_same_words_as_the_legacy_phone():
    for x in MONEY:
        assert fmt.dot(x) == pp.dot(x), x
        assert fmt.of100(x) == pp._of100(x), x
        for base in (None, 0, -5, 50.0, 1234.5):
            for dg in (0, 1, 2):
                assert fmt.ret(x, base, dg) == pp.ret(x, base, dg), (x, base, dg)
    for part, whole in PAIRS:
        assert fmt.pct1(part, whole) == pp.pct1(part, whole), (part, whole)
        for dg in (0, 1, 2):
            assert fmt.pct_of(part, whole, dg) == pp.pct_of(part, whole, dg), (part, whole, dg)


def test_read_json_same_as_legacy():
    with tempfile.TemporaryDirectory() as td:
        cases = {"obj.json": json.dumps({"a": 1}), "list.json": "[1, 2]", "bad.json": "{nope", "empty.json": ""}
        for name, body in cases.items():
            with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                fh.write(body)
        for name in list(cases) + ["missing.json"]:
            p = os.path.join(td, name)
            assert paths.read_json(p) == pp.read_json(p), name


def test_the_copies_are_gone():
    from phone.commands import speed
    from phone.commands.funds import page, read
    from phone.render import botcards
    assert (speed.dot, speed.pct_of, speed.pct1, speed.ret, speed._of100) == (fmt.dot, fmt.pct_of, fmt.pct1, fmt.ret,
                                                                            fmt.of100)
    assert page.pct_of is fmt.pct_of and read.read_json is paths.read_json and read._bs is botcards._bs
    assert botcards.dot is fmt.dot and botcards.ret is fmt.ret


def test_no_page_names_pinphone_py():
    """/speed's footnote and /funds' unknown-account words named pinphone.py; the constants live elsewhere now."""
    for mod in ("speed.py", os.path.join("funds", "page.py")):
        with open(os.path.join(RESEARCH, "phone", "commands", mod), encoding="utf-8") as fh:
            src = fh.read()
        assert "in pinphone.py" not in src, mod


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_fmt_merge"))
