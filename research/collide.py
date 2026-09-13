#!/usr/bin/env python3
# VERSION: 2026-09-13-col1
"""collide.py -- force facts that live apart into the same sentence.

THE OPERATOR'S INSTRUCTION, 2026-09-13, verbatim:

    "Take data points that aren't seemingly connected and pair it with a
    thought of something else seemingly unconnected, then put them together in
    a strange way to create a solution or original idea no one else could
    find... most will give nothing, but when it does work you have great
    ideas."

WHY A SCRIPT AND NOT JUST THINKING HARDER. The one good idea of 2026-09-13 came
from colliding three facts that lived in three different files and had never
been in the same sentence: the tape cannot measure our losses because its
population is wrong (F-R05), we lose one race in four (F-P03), and the
collector happens to record WHO did the buying (F-I04). Not one of them is
interesting alone. The reason they had never met is not that they are hard to
find -- they are all written down -- it is that nothing ever put them side by
side. That is a mechanical problem and this is the mechanical fix.

WHAT IT DOES, AND WHAT IT DELIBERATELY DOES NOT. It samples pairs of facts,
prefers pairs from DIFFERENT sections (a contract fact against an
infrastructure fact is where the value is; two performance facts are already in
the same conversation every day), writes them out with one question attached,
and REMEMBERS which pairs have been drawn so the same ground is not re-walked.

It does not think. A script cannot tell whether two facts connect. The thinking
is done by whoever reads the output -- a person or a scheduled agent -- and the
verdict comes back in with `--verdict`, so the ledger accumulates what has been
tried and what came of it. That ledger is the actual asset; the sampler is
trivial.

THE EXPECTED YIELD IS NEARLY ZERO AND THAT IS NOT A FAILURE. 2026-09-13's run
of this method by hand produced one dead hypothesis and one deployed change
worth a few dollars a day. Anything that treats a barren night as a bug will
get itself switched off inside a week.
"""
import argparse
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FACTS_DEFAULT = os.path.join(REPO, "FACTS.md")
LEDGER_DEFAULT = os.path.join(REPO, "results", "collisions.jsonl")
OUT_DIR = os.path.join(REPO, "results")

ROW = re.compile(r"^\|\s*(F-[A-Z]\d{2})\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")
SECTION = re.compile(r"^##\s+([A-Z])\s+[-—]\s+(.+?)\s*$")

QUESTION = (
    "Is there a MEASUREMENT that connects these two? Not a story -- a number "
    "we could go and compute from data we already hold. If yes, say what it "
    "is and what would have to be true for it to be an artefact. If no, say "
    "'nothing' and move on."
)


# ---------------------------------------------------------------------------
def load_facts(path):
    """[(id, section_letter, section_name, fact, source)] from FACTS.md.

    Parsed out of the markdown tables rather than a second data file on
    purpose: a fact that is not in the document a human reads will rot, and a
    document that is not the one the machine reads will drift from it.
    """
    out = []
    sec_l, sec_n = "?", "unsectioned"
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = SECTION.match(line.rstrip("\n"))
            if m:
                sec_l, sec_n = m.group(1), m.group(2)
                continue
            m = ROW.match(line.rstrip("\n"))
            if m:
                out.append((m.group(1), sec_l, sec_n, m.group(2), m.group(3)))
    return out


def load_ledger(path):
    """{frozenset(pair): record} of everything ever drawn."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            p = d.get("pair")
            if isinstance(p, list) and len(p) == 2:
                out[frozenset(p)] = d
    return out


def append_ledger(path, recs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


def draw(facts, ledger, n, seed=None, cross_bias=0.8):
    """n unseen pairs, `cross_bias` of them from DIFFERENT sections.

    The bias is the whole point. Two facts from the same section are already
    in the same conversation every day; the value is in a contract fact
    meeting an infrastructure fact. It is a BIAS and not a rule because
    same-section pairs occasionally matter too -- F-M05 and F-M06 are both
    model facts and together they say the obvious fix does not work.
    """
    rnd = random.Random(seed)
    by_id = {f[0]: f for f in facts}
    ids = sorted(by_id)
    if len(ids) < 2:
        return []
    want_cross = int(round(n * cross_bias))
    picked = []
    seen = set(ledger)
    # every pair, partitioned -- the fact count is small (tens), so this is
    # exact rather than rejection-sampled, and it cannot loop forever when the
    # space is nearly exhausted.
    cross, same = [], []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            key = frozenset((a, b))
            if key in seen:
                continue
            (cross if by_id[a][1] != by_id[b][1] else same).append((a, b))
    rnd.shuffle(cross)
    rnd.shuffle(same)
    picked.extend(cross[:want_cross])
    picked.extend(same[:n - len(picked)])
    if len(picked) < n:                       # cross ran out, top up from same
        picked.extend(cross[len(picked):n - len(picked) + len(picked)])
    return picked[:n]


def render(pairs, facts, stamp):
    by_id = {f[0]: f for f in facts}
    out = ["# COLLIDE %s" % stamp, "",
           "*%d pairs drawn by `research/collide.py`. One question each. Most "
           "of these are nothing -- that is the expected yield, not a bug. "
           "Record what came of each with "
           "`python research/collide.py --verdict <id> <id> nothing|lead`.*"
           % len(pairs), "",
           "**%s**" % QUESTION, ""]
    for k, (a, b) in enumerate(pairs, 1):
        fa, fb = by_id[a], by_id[b]
        out.append("## %d. %s x %s   *(%s x %s)*"
                   % (k, a, b, fa[2], fb[2]))
        out.append("")
        out.append("- **%s** — %s" % (a, fa[3]))
        out.append("- **%s** — %s" % (b, fb[3]))
        out.append("")
    return "\n".join(out) + "\n"


def verdict(path, a, b, what, note=""):
    rec = {"pair": sorted([a, b]), "verdict": what, "note": note,
           "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    append_ledger(path, [rec])
    return rec


def stats(ledger):
    c = {}
    for d in ledger.values():
        v = d.get("verdict", "drawn")
        c[v] = c.get(v, 0) + 1
    return c


# ---------------------------------------------------------------------------
def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    import tempfile
    tmp = tempfile.mkdtemp(prefix="collide-")
    try:
        fp = os.path.join(tmp, "FACTS.md")
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write("# FACTS\n\nprose that is not a fact row\n\n")
            fh.write("## C — The contract\n\n")
            fh.write("| id | fact | source |\n|---|---|---|\n")
            for i in range(1, 5):
                fh.write("| F-C0%d | contract fact %d | src |\n" % (i, i))
            fh.write("\n## I — Infrastructure\n\n")
            fh.write("| id | fact | source |\n|---|---|---|\n")
            for i in range(1, 5):
                fh.write("| F-I0%d | infra fact %d | src |\n" % (i, i))
        facts = load_facts(fp)
        ck(len(facts) == 8,
           "load_facts reads only the fact ROWS, not the header or the prose "
           "(%d found)" % len(facts))
        ck(facts[0][1] == "C" and facts[-1][1] == "I",
           "and tags each fact with the section it came from")
        ck(all(f[3] and f[4] for f in facts),
           "and carries the fact text and its source")

        lp = os.path.join(tmp, "ledger.jsonl")
        ck(load_ledger(lp) == {}, "a ledger that does not exist reads empty")

        got = draw(facts, {}, 4, seed=1)
        ck(len(got) == 4, "draw returns what was asked for")
        ck(len({frozenset(p) for p in got}) == 4,
           "and never the same pair twice in one draw")
        ncross = sum(1 for a, b in got
                     if a[2] != b[2])
        ck(ncross >= 3,
           "and prefers pairs from DIFFERENT sections (%d of 4) -- two facts "
           "from the same section are already in the same conversation"
           % ncross)

        # the memory: a drawn pair must never come back
        led = {frozenset(p): {"pair": list(p)} for p in got}
        got2 = draw(facts, led, 4, seed=1)
        ck(not (set(map(frozenset, got2)) & set(led)),
           "a pair already in the ledger is never drawn again")

        # exhaustion must terminate, not spin
        allp = {}
        ids = sorted(f[0] for f in facts)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                allp[frozenset((ids[i], ids[j]))] = {"pair": [ids[i], ids[j]]}
        ck(draw(facts, allp, 5, seed=1) == [],
           "when every pair has been drawn it returns nothing instead of "
           "looping forever")

        verdict(lp, "F-C01", "F-I01", "lead", "note")
        verdict(lp, "F-C02", "F-I02", "nothing")
        led2 = load_ledger(lp)
        ck(len(led2) == 2, "verdicts round-trip through the ledger file")
        ck(stats(led2).get("lead") == 1 and stats(led2).get("nothing") == 1,
           "and stats counts what came of them")
        ck(load_ledger(lp)[frozenset(("F-C01", "F-I01"))]["note"] == "note",
           "including the note")

        txt = render(got, facts, "test")
        ck(all(("**%s**" % a) in txt and ("**%s**" % b) in txt
               for a, b in got),
           "the rendered page names both facts of every pair")
        ck(QUESTION in txt,
           "and asks the one question, which is about a MEASUREMENT and not "
           "about a story")

        # the real file must parse, if it is there
        real = load_facts(FACTS_DEFAULT)
        if real:
            ck(len(real) >= 20,
               "the real FACTS.md parses and holds %d facts" % len(real))
            ck(len({f[0] for f in real}) == len(real),
               "and every fact id in it is unique")
            ck(len({f[1] for f in real}) >= 4,
               "across %d sections" % len({f[1] for f in real}))
    finally:
        for root, dirs, files in os.walk(tmp, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(tmp)
    print("collide selftest: %d checks OK" % n[0])
    return 0


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--facts", default=FACTS_DEFAULT)
    ap.add_argument("--ledger", default=LEDGER_DEFAULT)
    ap.add_argument("-n", "--draw", type=int, default=6,
                    help="how many pairs to draw")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--verdict", nargs="+", metavar="ARG",
                    help="<id> <id> <nothing|lead|measured> [note...]")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc

    ledger = load_ledger(a.ledger)
    if a.verdict:
        if len(a.verdict) < 3:
            print("--verdict needs <id> <id> <nothing|lead|measured> [note]")
            return 2
        rec = verdict(a.ledger, a.verdict[0], a.verdict[1], a.verdict[2],
                      " ".join(a.verdict[3:]))
        print("recorded: %s" % json.dumps(rec))
        return 0
    if a.stats:
        print("ledger: %d pairs drawn; %s"
              % (len(ledger), stats(ledger) or "none scored yet"))
        return 0

    facts = load_facts(a.facts)
    if not facts:
        print("collide: no fact rows in %s -- nothing to analyse" % a.facts)
        return 0
    pairs = draw(facts, ledger, a.draw, seed=a.seed)
    if not pairs:
        print("collide: every pair of the %d facts has already been drawn. "
              "Add facts, or re-open the ledger." % len(facts))
        return 0
    stamp = time.strftime("%Y%m%dT%H%MZ", time.gmtime())
    out = a.out or os.path.join(OUT_DIR, "COLLIDE_%s.md" % stamp)
    txt = render(pairs, facts, stamp)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(txt)
    append_ledger(a.ledger, [{"pair": sorted(p), "verdict": "drawn",
                              "t": stamp} for p in pairs])
    print(txt)
    print("written: %s   (%d facts, %d pairs drawn to date)"
          % (out, len(facts), len(ledger) + len(pairs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
