"""test_bots_page.py -- phone/commands/bots_page.py (/bots) against Phone.text_bots (v-tg-rebuild step 9, lane D2).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_bots_page.py   (exit 0 = every test passed)
The page on real data: golden shadow (8 worlds). Here: the declaration, botstats failing (the old wall's words), and
that the page is bs_all_html over all_bots' dict, asked with the Phone's seams.
"""
from _dlane import CM, CX, Html, botstats, boom, chart_and_help, new_reply, patched, phone, quiet, run, same

import phone.commands.bots_page as M


def test_declaration():
    (c,) = CM.of_module("phone.commands.bots_page")
    assert c.names == ("/bots",) and c.section == "money" and c.order == 50 and CM.by_name("/bots") is c
    chart_and_help("phone.commands.bots_page")


def test_botstats_fails_like_the_old_wall():
    ph = phone()
    with patched((botstats, "all_bots", boom)), quiet():
        old, new = ph.text_bots(), new_reply("phone.commands.bots_page", ph, "/bots")
    same(old, new, "/bots, botstats failing")
    assert isinstance(new, str) and new.startswith("Could not build /bots: planted failure\n")


def test_render_is_bs_all_html_of_all_bots():
    asked, a = [], {"planted": True}
    ph = phone()
    ph.bs_getter, ph.bs_procs = object(), [[1, "", "x"]]

    def all_bots(now, getter, procs):
        asked.append((now, getter, procs))
        return a
    import phone.monitor as MON                 # step 12 (lane Q): no DOWN warning line in this planted world
    with patched((botstats, "all_bots", all_bots), (M, "bs_all_html", lambda x: ["page of", str(x is a)]),
                 (MON, "down_lines", lambda ctx: [])):
        got = M.COMMAND.run(CX.Ctx.from_phone(ph, "/bots"))
    assert isinstance(got, Html) and str(got) == "page of\nTrue"
    assert asked == [(ph.now(), ph.bs_getter, ph.bs_procs)]


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_bots_page"))
