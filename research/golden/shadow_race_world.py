"""Golden SHADOW in worlds where the coin race is ACTIVE (rebuild step 9, lane D3). Never imported by production code.

The fixture (captured 10-30) has the race paused -- results/pinracepenny.stop is set -- so in all 8 golden worlds
/race and /racestats are the router's 'hidden' answer and shadow.py does not compare them. This file is shadow.py
with extra worlds: each is a golden world with the race's stop file removed (its live copy is in the fixture's process
table, pid 4408; the race_stop procs step adds one if a fixture lacks it), so botstats.active_bots() shows the race and
the old /race, /racestats pages run beside the new modules.

    C:\\Python314\\python.exe research\\golden\\shadow_race_world.py --code <research> --module phone.commands.race
                                      --module phone.commands.racestats [--world race-active ...] [--jobs 2]

Every shadow.py option works. With no --world it runs every race-active world below (RACE_WORLDS). The worlds are
registered into gl_worlds in this process AND in each child (the child is this file again: shadow.py starts
`__file__` with --child, and shadow.__file__ is pointed here), so gl_worlds.py itself is untouched.
"""
import os
import sys

GOLDEN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, GOLDEN)
import gl_worlds               # noqa: E402
import shadow                  # noqa: E402

# race-active world -> the golden world it starts from
BASES = {"race-active": "base", "race-active-procs-unreadable": "procs-unreadable",
         "race-active-kalshi-down": "kalshi-down", "race-active-dst": "dst-2026-11-01",
         "race-active-empty-logs": "empty-logs"}
RACE_WORLDS = list(BASES)


def _no_race_stop(files):
    def f(res, T):
        if files:
            files(res, T)
        gl_worlds._rm(os.path.join(res, gl_worlds.RACE_STOP))
    return f


def _race_live(procs):
    def p(rows, T):
        rows = procs(rows, T)
        return gl_worlds._race_stop_procs(rows, T)          # a live race row unless one is there (None stays None)
    return p


def register():
    for name, base in BASES.items():
        if name in gl_worlds.WORLDS:
            continue
        w = dict(gl_worlds.WORLDS[base])
        w["desc"] = "%s; the coin race ACTIVE (its live copy running, pinracepenny.stop removed)" % w["desc"]
        w["files"] = _no_race_stop(w.get("files"))
        w["procs"] = _race_live(w["procs"])
        gl_worlds.WORLDS[name] = w


def main():
    register()
    shadow.__file__ = os.path.abspath(__file__)             # shadow.run_world starts this file as the child
    if "--child" not in sys.argv and "--world" not in sys.argv:
        for w in RACE_WORLDS:
            sys.argv += ["--world", w]
    return shadow.main()


if __name__ == "__main__":
    sys.exit(main())
