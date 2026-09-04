# generator.py — change log with explanations

## 2026-09-03 — live mode overwrote ground_truth.csv

**Before:** `write_truth` always opened the file with `"w"` (write = start over), so starting
`live` erased the six 48-hour backfill answers and left only the six new 6-hour ones.

**After:**
```python
def write_truth(plans, seed, append=False):
    with open(TRUTH_PATH, "a" if append else "w", newline="") as f:   # "a" = append to the end, else "w"
        w = csv.writer(f)
        if f.tell() == 0:                                             # position 0 = empty file -> header once
            w.writerow(["seed", "failure", "scope", "start_utc", "end_utc", "note"])
        for p in plans:
            w.writerow([...])
```
- `append=False` is the default; callers that pass nothing overwrite as before (backfill).
- `"a" if append else "w"` is a one-line if: `"a"` when append is True, otherwise `"w"`.
- `f.tell()` is the current position in the file (bytes). Opened with `"a"` we sit at the end, so 0 means
  the file is empty and needs a header. Otherwise the header is not written again.

Only the live call changed: `write_truth(plans, args.seed, append=True)`.

**Check (scratch copy):** live for 4 s → ground_truth.csv had header + original 6 + new 6 = 13 lines.
backfill 1 h → 7 lines (still overwrites). The real data/ground_truth.csv stayed at 7 lines.

## 2026-09-03 — ambient_high was invisible on the servers (Aeri's decision)

Two lines changed:
```python
"dc-west": {"region": "us-west-2", "city": "Sacramento", "tz": "America/Los_Angeles", "outside_base": 30.0},
                                                                                       # Hillsboro 22.0 -> Sacramento 30.0
temp += 18.0                                     # heat wave     (12.0 -> 18.0)
```
Why: `ambient_push = max(0, outside - 30) * 0.6`, so the outside temperature has to pass 30 °C before
servers feel it. Hillsboro's base is 22; even a +12 heat wave at 02:00 gives 29 °C → 0.6 °C of effect.
Sacramento 30 + 18 → 43–45 °C → push 8–9 °C.

Regenerated: delete `telemetry.db`, `backfill --hours 48 --seed 42 --start 2026-09-02T02:32:00+00:00`,
then `collector.py`. The failure plan uses the same rng sequence, so ground_truth.csv was **identical**.

Result: during ambient_high, dc-west cpu median 50.8 °C vs 43.3 in the other dcs (+7.5). Throttling (75 °C): still 0 minutes.

## 2026-09-03 — weather ramp + load-weighted failure times (PLAN.md Weather / Failure timing)

### A. Datacenter constants: one base temperature → a daily low and high
```python
"dc-west": {..., "low": 15.0, "high": 33.0},     # Sacramento, early September: 15 at night, 33 by day
HEAT_WAVE_LOW_PLUS = 7.0      # heat wave: overnight low +7  (15 -> 22, "nights don't cool")
HEAT_WAVE_HIGH_PLUS = 13.0    # heat wave: daytime high +13 (33 -> 46)
HEAT_RAMP_UP_H = 30           # hours for the heat wave to build from 0 to 100%
HEAT_RAMP_DOWN_H = 12         # hours to fade after the window
```

### B. Three weather functions
```python
def daily_curve(local_dt):
    h = local_dt.hour + local_dt.minute / 60
    return 0.5 + 0.5 * math.sin((h - 9) / 24 * 2 * math.pi)
```
"How hot a time of day is", 0..1. sin runs -1..1, so `0.5 + 0.5*sin` maps it to 0..1.
`(h-9)/24*2π`: sin = 1 at h = 15 (warmest), -1 at h = 3 (coolest). E.g. 15:00 → 1.0, 03:00 → 0.0, 09:00 → 0.5.

```python
def heat_wave_strength(dc_id, now_utc, plans):
    for p in plans:
        if p["failure"] == "ambient_high" and p["scope"] == dc_id:
            up = timedelta(hours=HEAT_RAMP_UP_H)
            down = timedelta(hours=HEAT_RAMP_DOWN_H)
            if p["start"] - up <= now_utc < p["start"]:
                return (now_utc - (p["start"] - up)) / up      # ramping up: 0 -> 1
            if p["start"] <= now_utc < p["end"]:
                return 1.0                                       # planned window: 100%
            if p["end"] <= now_utc < p["end"] + down:
                return 1.0 - (now_utc - p["end"]) / down        # fading: 1 -> 0
    return 0.0
```
Heat-wave strength 0..1. `(now - start) / up` is timedelta ÷ timedelta = a fraction. 30 h before the
window it is 0, 15 h before 0.5, at the window start 1. A straight line, so no jumps.

```python
def outside_temp(dc_id, now_utc, plans, rng):
    dc = DATACENTERS[dc_id]
    local = now_utc.astimezone(ZoneInfo(dc["tz"]))
    strength = heat_wave_strength(dc_id, now_utc, plans)
    low = dc["low"] + strength * HEAT_WAVE_LOW_PLUS         # today's low
    high = dc["high"] + strength * HEAT_WAVE_HIGH_PLUS      # today's high
    return low + (high - low) * daily_curve(local) + rng.gauss(0, 0.4)
```
"low + (high − low) × daily curve". Example: Sacramento, heat wave at 100%, 15:00 → 22 + 24 × 1.0 = 46.
Normal 03:00 → 15 + 18 × 0 = 15. `rng.gauss(0, 0.4)` is noise with standard deviation 0.4 °C.

### C. Failure start times: uniform random → weighted toward busy hours
```python
def rand_time(min_minutes_before_end, tz, weight_fn):
    span = int((end - start).total_seconds() / 60) - min_minutes_before_end
    minutes = list(range(60, max(61, span)))                 # candidates: 60 min after start .. before the end margin, 1-min steps
    weights = [weight_fn((start + timedelta(minutes=m)).astimezone(ZoneInfo(tz))) for m in minutes]
    return start + timedelta(minutes=rng.choices(minutes, weights=weights)[0])
```
- Each candidate minute gets weight = `weight_fn(that minute in local time)`. Server failures use
  `load_at` (load 0.15–0.95); ambient_high uses `daily_curve` (hot hours).
- `rng.choices(candidates, weights=...)` picks one in proportion to the weights. Evening (0.85) is about 6× more likely than the small hours (0.15).
- The physics is untouched; only *when* things happen changed.
- Callers pass the timezone and the weight function: `rand_time(180, host["tz"], load_at)`. That is why
  `host` is now carried as a whole dict and `host["host_id"]` is only pulled out for the scope field.

### Result (seed 42, same --start)
- All six failures moved. cooling_fail landed at 19:01 Ashburn → **dc-east-s1 throttles for 77 min (max 76.2 °C)**.
- ambient_high Thu 15:14–19:03 Sacramento, outside max 47.2. All five dc-west servers rose together 42 → 52.7 °C
  in the afternoon, 64.6 at the evening peak (59.0 the evening before at the same hour).
- Outside-temperature rate of change: max 0.058 °C/min on 30-minute averages (target ~0.045). Raw per-minute
  deltas are dominated by the 0.4 noise: median 0.40, max 2.5 °C/min — noise size is Aeri's call.

## 2026-09-03 — load steps fixed (PLAN's "Edges are smoothed" was false)

**Problem:** the old `load_at` did `base * (0.9 + 0.1*sin(...))`, a small wobble *inside* each hour, while
the base itself jumped 0.15 → 0.85 exactly on the hour. Server temperatures moved up to -11 °C in one minute,
92 times in 48 hours.

**Fix:** split into two functions.
```python
def schedule(local_dt):
    """The steps as they are: the load at this time (0.15 / 0.5 / 0.85 / 0.95 / 0.4 ...)"""
    ...
    if 16 <= h < 23:
        if is_friday and h >= 20:
            return 0.95
        return 0.85
    ...

def load_at(local_dt):
    samples = [schedule(local_dt + timedelta(minutes=m)) for m in range(-30, 30)]
    return sum(samples) / len(samples)
```
- `schedule`: the old if/elif chain, now returning values directly.
- `load_at`: the **average** of `schedule` over the 60 minutes around now (30 back, 30 forward) — a moving
  average. The new value starts blending in 30 minutes before the boundary, giving a straight ramp.
- `range(-30, 30)` = -30, -29, …, 29 → 60 samples.

Check (Ashburn, Wednesday):
```
15:30 0.150   15:40 0.267   15:50 0.383   16:00 0.500   16:10 0.617   16:20 0.733   16:30 0.850
```
After regenerating, one-minute jumps over 6 °C: 92 → 3 (the remaining three are the overload onset and returns from silence).
**Note:** `load_at` also feeds the failure-time weights, so the seed-42 answers shifted slightly:
overload 23:04 → 22:57, cooling_fail 23:01 → 23:02. The other four are unchanged.

My first patch printed "patched" but had not changed the file — I forgot to assign the result of
`s.replace(...)` back to `s`. Fixed on the second try. Lesson: after a patch, `grep` the actual file.

## 2026-09-03 — folder cleanup: paths relative to the file

Folders were split `raw_data/` → `src/` (code) + `data/` (DB, answer key). Before, `DB_PATH = "telemetry.db"`
created the DB in "whatever folder the shell is in" — running from elsewhere made a stray new DB.
```python
from pathlib import Path
DATA_DIR = Path(__file__).resolve().parent.parent / "data"   # this file (src/generator.py) -> src/ -> repo root -> data/
DB_PATH = DATA_DIR / "telemetry.db"
TRUTH_PATH = DATA_DIR / "ground_truth.csv"
```
- `__file__` is the path of this Python file. `.resolve()` makes it absolute. `.parent` is one folder up.
- `Path / "name"` joins paths; the slash is an operator.
- collector.py and detector.py got the same one-liner. Now every script uses `<repo>/data/telemetry.db` regardless of cwd.
