"""2026-10-17 ~12:0xZ READS_DUE update: the four reads of workflow wf_85547317-3b6 (each reader + independent checker AGREE)."""
import json
P = r"C:\kals-repo\results\READS_DUE.json"
d = json.load(open(P, encoding="utf-8"))
by = {it["id"]: it for it in d["items"]}

def note(iid, text, status=None, due=None):
    it = by[iid]
    it.setdefault("read_log", []).append(text)
    it["read_note"] = text
    if status: it["status"] = status
    if due: it["due"] = due

note("fastconn-live",
     "10-17 11:5xZ READ (reader + independent checker AGREE): KEEP. 223 orders (219 entries + 4 hedges) on 166 markets / 125 closes, deploy 10-12 11:15Z..10-17 11:51Z (~95 bot-hours; due point = the 150th order 10-16 10:59Z). No REVERT trigger: no order placed twice (checked against Kalshi GET /portfolio/orders), every insurance order placed with no connection delay, no halt from a connection event, no connection Traceback. KEEP tests: warm entry median well over 30 ms faster than the 86.7-93.7 ms pre-deploy daily medians; >= 80% of last-60-s entries warm (1 cold entry, 10-16 07:29Z during the bad Wi-Fi, IOC canceled 0 filled, placed once); 0 outcome-UNKNOWN. Watch items: 2 read_retry GETs took ~3.6 s (10-16 06:55Z, 23:55Z; Kalshi reset the idle kept connection, retry ok, nothing held); warm median drifted to 56-61 ms on 10-15/16, 44 ms on 10-17; 11 conn_events in all (7 in the current run).",
     status="read")
note("stp-maker-live",
     "10-17 11:5xZ (reader + checker AGREE): RUN-ON, 7 of the 10 alarms the bar needs (6 markets, 10-10..10-15). No REVERT trigger: 0 insurance orders refused/errored/cancelled for self-trade (0 hedge_refused/not_sent/unknown/no_ask/gave_up/blind; every hedge send writes a record). All 7 insurance orders GET /portfolio/orders: self_trade_prevention_type 'maker', executed, filled = asked (302.66 of 302.66 contracts, 100%) vs the previous 14 alarms 700.52 of 789.52 (88.7%). The case 'maker' protects against (a hedge crossing our own resting ladder bid) has not happened yet: no ladder bid was resting on any alarmed market at the insurance send. Next read at alarm 10.",
     due="2026-10-24T12:00Z")
note("rain-weekly",
     "10-17 11:5xZ (reader + checker AGREE, same numbers): BAR FAIL on 3 of 4 lines -- 3-10c rung 273 markets / 64 dates (bar 400), losses 7 of 273 = 2.56 per 100 (bar <= 2.5), net +2.55c a contract (PASS), 13 Oct/Nov dates (bar 15). The bar's kill clause 'the loss bar failing in October -> dead for the winter' is met: October-only 3-10c 1 loss in 34 = 2.94 per 100. VERDICT BY THE PRE-REGISTERED BAR: DEAD FOR THE WINTER; weekly re-runs stop. Also measured: Kalshi's settled list covers only the last 68 market-dates, so the sample cannot grow as the item assumed (309 -> 277 -> 273); the 11-20c rung lost 7 of 26 in October (-12.83c a contract).",
     status="read")
note("arm-attempts",
     "10-17 11:5xZ (reader + checker AGREE): CANNOT BE READ -- the arm (pid 3363744, results/pinrun-paper-20261010T094736Z.jsonl) died at the 10-14 03:29Z shutdown and never restarted; 2 full ET days of shared closes (bar 7), and live changed build 3 times while it ran. So far: 13 live lock-outs (refused gate market_attempts), the arm bought all 13, live already held 10 -> 3 extra markets, 0 lost, +$9.70 paper. RELAUNCHED 12:00:57Z as arm-attempts2 (results/start_arm_attempts2.ps1, pid 717680, log results/pinrun-paper-20261017T120103Z.jsonl) on today's live build 0925j with today's exact argv minus --live + --attempts-on-send; see READS_DUE arm-attempts2.",
     status="read")
if "arm-attempts2" not in by:
    d["items"].append({
        "id": "arm-attempts2",
        "due": "2026-10-24T13:00Z",
        "what": "PAPER arm-attempts2 (pid 717680 since 2026-10-17 12:00:57Z, results/start_arm_attempts2.ps1, log results/pinrun-paper-20261017T120103Z.jsonl, code C:\\kals-live-0925j d8c3c7dcb888 = the live build): today's exact live argv minus --live, no-brake pair, --minutes 10080, plus --attempts-on-send (an attempt counts only when an order is SENT, so refusals without an order cannot lock a market out). Replaces arm-attempts (died 10-14, 3 extra markets 0 lost +$9.70 in its 2 days -- carried as context, not pooled: different build).",
        "how": "Markets where the arm bought and LIVE did not on the same closes, each with live's lock-out reason (refused gate market_attempts) and the Kalshi outcome; paper $ per market; any market where the flag made the arm hold MORE than one full bet.",
        "bar": "Same bar as arm-attempts, PRE-REGISTERED 2026-10-10, unchanged: after 7 ET days, PROPOSE LIVE if the extra markets number >= 4 with 0 lost and net paper $ > 0; DROP if any extra market lost or there are < 2 extra markets.",
        "status": "open"})
json.dump(d, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("ok")
