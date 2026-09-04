# detector.py, line by line

detector.py finds "what is unusual" in clean_readings. It does not name failures (that is Phase 3).
Output = **episodes**: which host, which sensor, from when to when, how many minutes, how far (peak), which rule.
Every number is a parameter. PLAN.md: Aeri sets the numbers.

## ① Load — one sensor, all hosts, in time order
```python
def load_series(con, sensor):
    series = {}
    rows = con.execute(
        "SELECT host_id, ts_utc, value FROM clean_readings WHERE sensor = ? AND value IS NOT NULL ORDER BY host_id, ts_utc",
        (sensor,),
    )
    for host_id, ts, value in rows:
        series.setdefault(host_id, []).append((ts, value))
    return series
```
- `value IS NOT NULL`: rows with a parse_error (no value) are skipped.
- `series.setdefault(host_id, [])`: if the dict has no entry for this host, create an empty list; otherwise
  return the existing one. Then `.append((ts, value))` adds one point.
- Result: `{"dc-east-s1": [("2026-09-02T02:32:00+00:00", 57.4), ("…02:33…", 57.6), …], "dc-east-s2": […], …}`

## ② Rule: threshold — past a line for N minutes in a row
```python
def threshold(series, sensor, line, minutes, below=False):
    sign = "<" if below else ">"
    rule = f"{sensor} {sign} {line:g} for >= {minutes} min"     # the human-readable rule. {line:g} prints 65.0 as "65"
    episodes = []
```
```python
    def close(host_id, run):
        if len(run) >= minutes:                    # only a stretch of N+ readings becomes an episode
            values = [v for _, v in run]           # just the values out of the (ts, v) list
            episodes.append({
                "host_id": host_id, "sensor": sensor,
                "start": run[0][0], "end": run[-1][0],    # ts of the first point, ts of the last
                "minutes": len(run),
                "peak": min(values) if below else max(values),   # for a "below" rule the lowest value is the peak
                "rule": rule,
            })
```
A function inside a function. It can use the outer `episodes`, `minutes`, `rule` directly, so fewer arguments.

```python
    for host_id, points in series.items():
        run = []                                   # the current stretch that is past the line
        for ts, value in points:
            past = value < line if below else value > line
            if past:
                run.append((ts, value))            # past the line: extend the stretch
            else:
                close(host_id, run)                # not past: end the stretch (save it if long enough)
                run = []                           # start a new one
        close(host_id, run)                        # a stretch still open at the end of the data
    return sorted(episodes, key=lambda e: e["start"])
```
- One host at a time, one point at a time. Past the line → pile into `run`; the moment it is not, close `run`.
- The final `close`: a stretch that lasts to the end of the data never gets closed inside the loop, so once more after it.
- `sorted(..., key=lambda e: e["start"])`: sort by start time. `lambda e: e["start"]` = "take start from each episode and compare on that".
- "minutes" = "row count". One row per minute, so equal — but silence removes rows, which makes a stretch look
  shorter than real time. Left as is for now.

Example: dc-east-s1's cpu_temp stays above 65 for 103 rows from 23:17 to 00:59, max 76.2 →
`{"host_id": "dc-east-s1", "sensor": "cpu_temp", "start": "…23:17…", "end": "…00:59…", "minutes": 103, "peak": 76.2, "rule": "cpu_temp > 65 for >= 10 min"}`

## ③ Print
```python
def print_episodes(episodes):
    if not episodes:
        print("no episodes"); return
    print(f"{'host_id':<16}{'sensor':<12}{'start (UTC)':<26}{'end (UTC)':<26}{'min':>5}{'peak':>8}   rule")
    for e in episodes:
        print(f"{e['host_id']:<16}{e['sensor']:<12}{e['start']:<26}{e['end']:<26}{e['minutes']:>5}{e['peak']:>8.1f}   {e['rule']}")
```
`:<16` left-aligned in 16 columns, `:>5` right-aligned in 5, `:>8.1f` one decimal in 8 columns.

## ④ Entry point — subcommands
```python
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="rule", required=True)      # the first word is the rule name: threshold, (later) slope, peer …
    t = sub.add_parser("threshold")
    t.add_argument("sensor")                                 # positional: by order
    t.add_argument("line", type=float)
    t.add_argument("--minutes", type=int, default=10)
    t.add_argument("--below", action="store_true")
```
`python detector.py threshold cpu_temp 65 --minutes 10` → args.rule="threshold", sensor="cpu_temp", line=65.0, minutes=10, below=False.
Each new rule is one more `sub.add_parser("slope")`.

## First run (2026-09-03, numbers are candidates, not decisions)
```
cpu_temp > 65 for >= 10 min
dc-east-s1   09-02 23:17 -> 00:59  103 min  peak 76.2   <- cooling_fail (answer key)
dc-west-s4   09-03 23:00 -> 00:31   92 min  peak 68.6   <- inside the ambient_high window (whole dc hot + evening peak)
dc-west-s1   09-03 23:16 -> 23:38   23 min  peak 67.0   <- same
dc-west-s4   09-04 00:33 -> 00:45   13 min  peak 66.9

fan_rpm < 2000 for >= 10 min
dc-east-s1   09-02 23:40 -> 00:59   80 min  low 1651    <- cooling_fail, 23 min later than the temperature rule (the line is low)

power_draw > 450 / mem_used > 150 for >= 10 min
dc-west-s1 only                                           <- overload (answer key)
```
One fixed line cannot tell "one server broke" from "the whole dc is hot" — that is why rule 6 (peer comparison) exists.
