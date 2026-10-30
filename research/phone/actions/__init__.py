"""phone/actions -- the ONLY code of the phone that changes anything outside the phone itself (v-tg-step12, lane R).

Until step 12 the phone read and never wrote: Kalshi GET only, the controls through pindesk. The operator asked
(2026-10-30) to pause / resume single bots, approve waiting changes and move money from the phone, so these modules
hold every such write, each in ONE place the safety scans name (phone/tests/test_actions_safety.py):

  journal.py      every action, one JSON line in results\\phone_actions.jsonl (who, what, when, the result)
  confirm.py      the two-step confirmations (expire; single use; a 4-digit code where money or a script is at stake)
  stopfiles.py    a bot's stop file: the only phone code that writes or removes one (the pin bot keeps pindesk's)
  launch.py       a WMI process create through PowerShell: the only phone code that starts a process for an action
  approvals.py    results\\approvals\\approvals.json: the waiting changes the operator may run, and which ran
  money.py        the ONLY phone code that sends a POST to Kalshi: two paths, signed with kauth's key, capped

The command modules (phone/commands/botctl.py, approve.py, move.py, controls.py) word the questions and the answers;
the work is done here. Every write here honours botdata.paths.check_write (KALS_TESTING=1 refuses the live folders),
and launch.py / money.py refuse outright under KALS_TESTING=1 unless a test planted its stub.
"""
