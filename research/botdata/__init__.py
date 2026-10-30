"""botdata -- the phone's DATA layer (phone rebuild, DESIGN section 2): the bots' numbers for the phone, the desktop
and server_sync. Never imports the phone.

v-tg-rebuild step 2 (2026-10-30): only paths (RESULTS in one place + the test write fence), clock and fmt (the
existing date and money helpers, copied verbatim) live here so far; nothing in production calls them yet except
botstats' RESULTS, which is paths.RESULTS (the same string it always computed).
"""
