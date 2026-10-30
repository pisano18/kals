"""botdata -- the phone's DATA layer (phone rebuild, DESIGN section 2): the bots' numbers for the phone, the desktop
and server_sync. Never imports the phone.

v-tg-rebuild step 2 (2026-10-30): paths (RESULTS in one place + the test write fence), clock and fmt (the existing date
and money helpers, copied verbatim). Step 4: procs (one process table) and status (each bot's state, fleet, the SHOWN
policy). Step 7: botstats.py split into tables, kalshi, money, pots, logs, activity, versions, running, report and
words; botstats.py is a facade over them (every old name, the same objects). series.py (the charts' data) is step 8's.

Rule: a module calls another through its module attribute (`_kalshi.load_cache()`, never a copied name), so a name
set on botstats (a test, the golden harness) reaches every caller. Tests: botdata/tests/test_*.py, all run by
`research\\botstats.py --selftest`.
"""
