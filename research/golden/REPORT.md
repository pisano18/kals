# Golden harness: step 0 report (2026-10-30)

Built by the step-0 agent; saved by the parent from its hand-back.

- Files: capture.py (server capture, read-only, writes only under C:\kals\golden), replay.py (one process per world,
  PYTHONHASHSEED=0, fixture copied to scratch with mtimes restored; --jobs --world --only --repeat --keep-work),
  gl_child.py, compare.py (case-by-case diff report, both PNGs + PIL diff, --accept PATTERN --why -> CHANGES.md;
  exit 0 = all same or accepted), gl_cases.py, gl_fence.py (file redirect + write guard, network/process/kill guards,
  frozen clock, undo of each case's writes), gl_worlds.py (8 worlds), gl_common.py, README.md (how to run), CHANGES.md.
- Outside the repo (laptop): fixture C:\kals-golden\fixtures\20261030T132932Z (317 MB, server capture 13:29Z, 201 s,
  peak 175 MB, 15 Kalshi GETs from /funds only, fake telegram.json); baseline C:\kals-golden\expected\7fb0407;
  runs of 5492870 C:\kals-golden\runs\final-1 and final-2; diff C:\kals-golden\reports\7fb0407-vs-worktree.md.
- Runtime: all 8 worlds 174 s wall on the laptop (--jobs 2); slowest cases /bars ~6 s, /brief ~3 s.
- Determinism: two runs byte-identical on all 720 case files; one chart (dst world, bot:fx) has matplotlib
  anti-aliasing noise, treated as the same (<= 24 levels on <= 2,000 pixels).
- 7fb0407 vs 5492870: 52-64 changed cases per world + 1 added, all from v-tg-active / jump band (hidden race,
  forecaster, weather; /jb page; sub 3 = jump band; 'earlier bots' lines; wording 'pin bot + coin race' -> 'pin bot').
- Not covered: Phone.run / poll / resend / chart thread, real self-tests and controls, AWS cost calls, /bars watcher
  subprocesses (refused), paper-arm logs older than 7 days (0-byte stand-ins). Record and compare on the same machine.
