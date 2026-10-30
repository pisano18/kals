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

# the race-active worlds live in gl_worlds.WORLDS since rebuild step 10 (RACE_BASES); this file only narrows shadow.py
# to them
BASES = gl_worlds.RACE_BASES
RACE_WORLDS = list(BASES)


def register():
    """Kept for callers: the worlds are already in gl_worlds."""


def main():
    shadow.__file__ = os.path.abspath(__file__)             # shadow.run_world starts this file as the child
    if "--child" not in sys.argv and "--world" not in sys.argv:
        for w in RACE_WORLDS:
            sys.argv += ["--world", w]
    return shadow.main()


if __name__ == "__main__":
    sys.exit(main())
