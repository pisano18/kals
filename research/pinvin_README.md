# pinvin_*.py -- the bot as it was, running beside the bot as it is

The operator, 2026-09-18: *"Run any version posted on the 12th 12am through
13th end of day and run them and put them in the lab."*

Each file is `research/pinrun.py` extracted VERBATIM from a commit in that
window. Nothing is adapted: they import today's `engine`, `replay`,
`pintake` and `livebook`, and all six tested passed their own self-tests
unchanged, which is itself a useful fact about how stable those interfaces
are.

| file | commit | posted (ET) | what landed in it |
|---|---|---|---|
| `pinvin_0912a.py` | `7b6e7d7` | 09-12 00:11 | A15, the belief-collapse hedge, built and not yet deployed |
| `pinvin_0912b.py` | `c0f8e33` | 09-12 19:13 | A16, SIZE follows the bank |
| `pinvin_0913a.py` | `3f393ea` | 09-12 21:49 | A17, a close is capped on CONTRACTS |
| `pinvin_0913b.py` | `a8973c1` | 09-13 09:52 | v-a21, the confidence gate 0.995 -> 0.990 |
| `pinvin_0913c.py` | `6ee8409` | 09-13 18:33 | A28/A29, spend the budget we already allow |
| *(not kept)* | `783929c` | 09-13 19:51 | already running as `research/pinrun913.py` |

**They run on their OWN shipped defaults -- no flags.** That is deliberate:
the question is what the version as POSTED does, not what it would do under
today's configuration. So the 09-12 arms hedge at 0.90 and 0.80 where we now
hedge at 0.60, have no bank brake, no jump gate and no close budget, because
those did not exist yet.

**There were 36 commits to `pinrun.py` in that window; these are five of
them.** They were chosen as the points where trading BEHAVIOUR changed --
the amendments that were deployed -- rather than the many commits that moved
logging, tooling or comments. Running all 36 would cost about 2.5 GB of
memory and would mostly compare a version against itself.

To add another: `git show <sha>:research/pinrun.py > research/pinvin_<tag>.py`,
run `--selftest`, start it with `--size 20 --minutes 4320`, read its
`code_sha` from the first line of its log, and add a `pinlab.py` entry
selecting on that sha. The sha is the hash of the file itself, so it cannot
collide with any other arm; selecting on settings would match dozens of logs.
