"""2026-10-17 ~07:3xZ: READS_DUE entries for the four paper tests built from the strategy hunt (workflow wf_e47c9b2f-e42,
each built, independently reviewed, fixed and re-checked GO). Bars quoted from their specs, written before any result."""
import json
P = r"C:\kals-repo\results\READS_DUE.json"
d = json.load(open(P, encoding="utf-8"))
have = {it["id"] for it in d["items"]}
NEW = [
 {"id": "fc-fast-paper",
  "due": "2026-10-27T12:00Z",
  "what": "PAPER research/cleanroom/fc_fast_paper.py (code_sha b24768ce9f8c, start results/start_fc_fast.ps1, log results/fc-fast-paper.jsonl): the live clean-room forecaster's exact rule (ctrl: decide 0.2 s after the print's second, fill only if still shown 1.0 s later -- what live does) beside a FAST arm (decide on the print, fill if still shown 75 ms later, same caps/price cap/crash guard), on one WebSocket. From the hunt's lose-less lead A: live orders reach Kalshi ~1.26 s after the print; the 76 in 100 contracts lost by waiting were +3.21c winners (upper bound).",
  "how": "python research/cleanroom/fc_fast_paper.py --read (refuses a verdict unless the ctrl arm reproduces the live forecaster's own fills from results/forecaster-live*.jsonl)",
  "bar": "PRE-REGISTERED 2026-10-17 before any run: read after >= 200 fast-variant paper fills over >= 100 closes (~7-10 days); PASS if the fast variant is >= +2.0c a contract better after fee than the control on the same decisions AND both halves positive; KILL if it is <= 0 better. Paper cannot see who we lose to; a PASS is a reason to ask the operator about a live change, not a switch.",
  "status": "open"},
 {"id": "racev2-shadow",
  "due": "2026-10-20T12:00Z",
  "what": "SHADOW research/sweep/racev2_shadow.py (code_sha 291531c22395, start results/start_racev2-shadow.ps1, stop results/racev2-shadow.stop): replays each closed hour of our own coin-race tape and scores the v2 1c reward filler (exit 115 s by server-side expiry, $1.25 credit floor, size 1,100; spec .sweep/hunt-2026-10-15/spec-20261015-R1-C2-02/SPEC.md) -- credit vs fills. Tape only; one /incentive_programs read an hour.",
  "how": "the shadow's report (see its --help) after 3 full ET days of --follow",
  "bar": "PRE-REGISTERED (spec 4.1) before any forward number: read after the first 3 full ET days of --follow (>= 250 scored races with a program and all 5 legs clean), open rails, conservative cost. HOLD the live test if ANY: x99 (replace-adjusted) cost > 70% of paid-model credit (10-07..10-15 gave 47.8%); placed legs < 0.7 per race (was 2.0); programs missing on > 5% of races. Otherwise recommend the 20-race live test to the operator (spec 4.2: PASS C <= 0.25 M AND P >= 0.90 M; KILL C > 0.50 M or P < 0.50 M at 48 h). The gate cannot PASS the idea; only live fills can.",
  "status": "open"},
 {"id": "fxreward-paper-1024",
  "due": "2026-10-24T12:00Z",
  "what": "FX 15M reward paper: research/sweep/fxbook_rec.py (dfd61e06057a; READ-ONLY recorder of the FX 15M Kalshi books + Kraken FX books into results/fxbook/) + research/sweep/fxreward_paper.py (7e2cdf290fe9; paper quoter over the latency/queue grid), 5 weekdays Mon 10-19..Fri 10-23. Spec .sweep/hunt-2026-10-15/spec-20261015-R1-C2-03/SPEC.md.",
  "how": "python research/sweep/fxreward_paper.py --report (any V1-V5 validity failure voids the read)",
  "bar": "PRE-REGISTERED (spec section 5) before any FX book was recorded: variant of record S=60, join, T_STOP 300 s, net cap 60, band 10-90c, payout 0.9, fifo_prorata; net per window = credit + fills marked at 60 s. GO to a live micro (operator sign-off still required) for a pair only if ALL: G1 at L=300 ms mean net >= +$1.00/window, 95% lower bound > $0, late half (days 3-5) >= +$0.50; G2 at L=300 ms under 'last' queue >= $0; G3 settlement mean not below markout mean by > 2 SE; G4 >= 1 stale fill per 10 windows at L=300 (zero = blind -> void); G5 worst window >= -$45, worst ET day >= -$150. KILL the pair if at L=150 ms fifo_prorata mean < $0 with 95% upper bound < +$1.00, OR mean credit at S=60 < $1.50/window. Otherwise INCONCLUSIVE: extend once by 5 weekdays, then GO only on G1-G5, else KILL. MDE ~$0.70/window; if markout SD > $10/window report 'no power'.",
  "status": "open"},
 {"id": "ratehreward-paper",
  "due": "2026-10-21T21:30Z",
  "what": "PAPER research/sweep/ratehreward_paper.py (start results/start_ratehreward_paper.ps1, log results/ratehreward-paper.jsonl): Treasury hourly ladders (KX2/5/7/10/30YRRATEH), 1c/1c reward pairs on strikes 6-9 bp from the yield, cancel-all on the first sweep anywhere; weekdays 07:00-20:59Z from Mon 10-19. Spec .sweep/hunt-2026-10-15/spec-20261015-R1-C2-01/SPEC.md. KILL read Wed 10-21 5:30 PM ET; PASS read Fri 10-23 5:30 PM ET.",
  "how": "python research/sweep/ratehreward_paper.py --report. FIRST the 6.4 reproduction gate: --history 2026-10-16 must reproduce 6 +-1 sweeps over 3.15 +-10% stack-hours, else the recorder is not read.",
  "bar": "PRE-REGISTERED (spec section 6) before any output: population = weekday non-blackout hours 07:00-20:59Z, WS continuous, audit clean; cluster = the hour. KILL (after >= 3 weekdays / >= 30 hours) if any: V2 net-if-paid <= $0 per strike-hour at the point burst share; even E_low V2 net-if-paid <= $0; sweeper present in >= 80% of observable hours; mean credit-if-paid < $3.00; programs not listed 2 consecutive weekdays. PASS (-> put the payment probe to the operator) if all: >= 50 observable non-blackout hours on >= 5 weekdays; V2 net-if-paid >= +$2.00 per strike-hour posted (first sweep of each sweeper hour hits one ghost, burst share at its 90% upper bound); positive in both halves; V2 mean credit-if-paid >= $5.00 per strike-hour; >= 60 V2 strike-hours per weekday.",
  "status": "open"},
]
added = [n["id"] for n in NEW if n["id"] not in have]
d["items"].extend(n for n in NEW if n["id"] not in have)
json.dump(d, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("added", added)
