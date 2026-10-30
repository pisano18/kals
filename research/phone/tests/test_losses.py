"""test_losses.py -- phone/commands/losses.py (/losses) against Phone.text_losses (v-tg-rebuild step 9, lane D2).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_losses.py   (exit 0 = every test passed)
Planted through tgcharts.all_losses (what both paths ask): many long losing markets (the page shrinks five at a time
to fit one message), none at all, a partial read; and the main account's fallback -- all_losses failing, or knowing no
bot -- with and without losing closes in the Ledger.
"""
from _dlane import (CM, SETTLED, T, Html, botstats, boom, chart_and_help, fake_ledger, new_reply, patched, phone, pp,
                    quiet, run, same, settled_row, tgcharts)
from botdata import series          # the module's source since v-tg-rebuild step 10 (the legacy Phone asks tgcharts)


def _rows(n):
    bots_ = ["pin", "race", "fx", "earlier", "other"]
    out = []
    for k in range(n):
        b = bots_[k % len(bots_)]
        out.append({"bot": b, "what": ("race BTC leg %d " % k if b in ("race", "earlier") else "EURUSD 1.08%d " % k) * 8,
                    "side": ("yes", "no", "both", "-")[k % 4], "contracts": 2.5 + k, "money": -1.25 * (k + 1),
                    "pct": (-0.1 * k) if k % 3 else None, "day": "2026-10-%02d" % (30 - k // 4)})
    return out


PER = {"pin": {"lost": 20, "settled": 400, "lost_7d": 3, "money_lost": 55.5, "worst": -12.0},
       "race": {"lost": 9, "settled": 60, "lost_7d": 1, "money_lost": 20.0, "worst": -7.5},
       "fx": {"lost": 4, "settled": 0, "lost_7d": 0, "money_lost": 0.0, "worst": None},
       "earlier": {"lost": 6, "settled": 30, "lost_7d": 0, "money_lost": 9.0, "worst": -3.0}}


def _patch(rows, per, missing=()):
    """One planted all_losses for both sides: the legacy Phone asks tgcharts.all_losses, the module botdata.series."""
    return _Two((tgcharts, "all_losses", lambda ctx, week_days=7: (botstats, list(rows), dict(per), list(missing))),
                (series, "all_losses", lambda bs, now, getter=None, procs=None, week_days=7:
                 (botstats, list(rows), dict(per), list(missing))))


class _Two(tuple):
    """Two patches that go together (patched() takes them as one)."""

    def __new__(cls, *triples):
        return tuple.__new__(cls, triples)


_BOOM = _Two((tgcharts, "all_losses", boom), (series, "all_losses", boom))


def _both(ph):
    return ph.text_losses(), new_reply("phone.commands.losses", ph, "/losses")


def test_declaration():
    (c,) = CM.of_module("phone.commands.losses")
    assert c.names == ("/losses",) and c.section == "now" and c.order == 50
    chart_and_help("phone.commands.losses")


def test_every_bot_and_the_shrink_loop():
    ph = phone()
    for n, missing in ((40, ()), (3, ("ladder",)), (12, ())):
        with patched(_patch(_rows(n), PER, missing)):
            old, new = _both(ph)
        same(old, new, "/losses, %d rows" % n)
        assert isinstance(new, Html) and "losing markets" in str(new)
    with patched(_patch(_rows(40), PER)):
        s = str(new_reply("phone.commands.losses", ph, "/losses"))
    assert len(s) <= pp.MAX_LEN and "the last 30," not in s and "the last 2" in s, "the page shrank to fit one message"


def test_no_losing_market():
    ph = phone()
    for missing in ((), ("fx", "ladder")):
        with patched(_patch([], PER, missing)):
            old, new = _both(ph)
        same(old, new, "/losses, none")
        assert str(new).startswith("No losing markets in any pot")


def test_main_account_fallback():
    led = fake_ledger(settled=SETTLED + [settled_row(T - 7200, -0.5, tk="KXCRYPTOLEAD15M-26OCT300845-SOL",
                                                     close=T - 3600 * 2)], bank_at=1200.0)
    for patch in (_BOOM, _patch(_rows(5), {})):
        for ledger in (led, fake_ledger()):
            ph = phone(ledger)
            with patched(patch), quiet():
                old, new = _both(ph)
            same(old, new, "/losses, fallback")
            assert "losing closes" in str(new) or str(new) == "No losing closes."


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_losses"))
