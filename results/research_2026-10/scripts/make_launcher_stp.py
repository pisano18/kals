"""results\restart_bot.stpmaker.ps1 = today's restart_bot.ps1 with ONLY the code path moved to C:\kals-live-0925e
(insurance orders carry self_trade_prevention_type=maker). The argv is byte-identical. Nothing deployed."""
import hashlib, re
src = r"C:\kals-repo\restart_bot.ps1"
dst = r"C:\kals-repo\results\restart_bot.stpmaker.ps1"
sha = hashlib.sha256(open(r"C:\kals-live-0925e\research\pinrun.py", "rb").read()).hexdigest()[:12]
s = open(src, encoding="utf-8").read()
a0 = re.search(r"\$botArgs = @\((.*?)\n\)", s, re.S).group(1)
reps = [
    ('$code = "C:\\kals-live-0925d"', '# v-stp-maker (2026-10-09, results/FINAL_SYNTHESIS_2026-10-09.md): the SAME argv on\n# C:\\kals-live-0925e, whose only behaviour change with these flags is that insurance\n# orders carry self_trade_prevention_type=maker (our own ladder bid can never cancel\n# insurance). Revert: results\\restart_bot.before-seen.ps1 (= the 0925d launcher).\n$code = "C:\\kals-live-0925e"'),
    ('$codeSha = "c0fe4953e891"', '$codeSha = "%s"' % sha),
    ('expected $codeSha (the 09-25 build + v-fullcap + v-skiphype + v-bankfix-nodd, C:\\kals-live-0925d)',
     'expected $codeSha (the 09-25 build + v-fullcap + v-skiphype + v-bankfix-nodd + v-stp-maker, C:\\kals-live-0925e)'),
]
for a, b in reps:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
a1 = re.search(r"\$botArgs = @\((.*?)\n\)", s, re.S).group(1)
assert a0.replace("0925d", "0925e") == a1 or a0 == a1, "argv changed"
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("sha", sha, "->", dst)
