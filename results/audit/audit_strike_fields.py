"""READ-ONLY: does every crypto 15M market actually carry the fields pinrun
depends on -- custom_strike.floor_strike (exact) and custom_strike.round_digits?

If round_digits is absent, eff_strike() falls back to the raw strike and the
rounding band disappears -- and the band is the correction that separates the
one replayed -90.91c loss from a win.  If custom_strike.floor_strike is
absent, the TRUNCATED top-level value is used instead.
"""
import json, collections, os
P = r"C:\kals\fulltape\markets.json"
raw = json.load(open(P, encoding="utf-8"))
rows = raw if isinstance(raw, list) else (raw.get("markets") or list(raw.values()))
if isinstance(rows, dict):
    rows = list(rows.values())
per = collections.defaultdict(lambda: collections.Counter())
digits = collections.defaultdict(collections.Counter)
mism = collections.defaultdict(list)
n = 0
for m in rows:
    if not isinstance(m, dict):
        continue
    tk = m.get("ticker") or ""
    if not tk.startswith("KX") or "15M" not in tk:
        continue
    series = tk.split("-")[0]
    n += 1
    cs = m.get("custom_strike") or {}
    per[series]["markets"] += 1
    per[series]["has_custom_strike"] += int(bool(cs))
    per[series]["has_cs_floor"] += int(cs.get("floor_strike") is not None)
    per[series]["has_round_digits"] += int(cs.get("round_digits") is not None)
    if cs.get("round_digits") is not None:
        digits[series][int(cs["round_digits"])] += 1
    top = m.get("floor_strike")
    if cs.get("floor_strike") is not None and top is not None:
        try:
            if abs(float(cs["floor_strike"]) - float(top)) > 1e-12:
                mism[series].append((tk, top, cs["floor_strike"]))
        except Exception:
            pass
print(f"  {n} crypto-15M market records in {P}")
print(f"  {'series':18s} {'n':>6s} {'custom':>7s} {'cs.floor':>9s} "
      f"{'round_digits':>13s}  digits seen")
for s in sorted(per):
    c = per[s]
    print(f"  {s:18s} {c['markets']:6d} {c['has_custom_strike']:7d} "
          f"{c['has_cs_floor']:9d} {c['has_round_digits']:13d}  "
          f"{dict(digits[s])}")
print()
print("  top-level floor_strike vs custom_strike.floor_strike disagreements:")
for s in sorted(mism):
    ex = mism[s][:2]
    print(f"    {s:18s} {len(mism[s]):5d} of {per[s]['markets']}   e.g. "
          + "; ".join(f"{t}: top {a} vs exact {b}" for t, a, b in ex))
if not mism:
    print("    none")
