# stream.py, line by line

stream.py is the "tick loop". Every interval it calls collector.collect_once to move new raw rows into
clean_readings and prints one status line. Later phases add the detector and the dashboard to the same tick.

## Imports
```python
import argparse                          # reads command-line options (like --interval 5)
import time                              # time.sleep = wait a number of seconds
from datetime import datetime, timezone  # for printing the current time
import collector                         # our collector.py; we borrow open_db and collect_once
```
`import collector` works because it is in the same folder (src). collector.py's `main()` under
`if __name__ == "__main__"` does not run on import.

## One tick
```python
def tick(con):
    n, errors = collector.collect_once(con)      # move new rows. (rows written, failures)
    latest = con.execute("SELECT MAX(ts_utc) FROM clean_readings").fetchone()[0]   # latest reading time
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")     # the real current time as "03:37:39"
    print(f"[{now}] +{n} rows ({errors} parse errors)  latest reading {latest}")
    return n
```
- `strftime("%H:%M:%S")` formats a time as text: %H hours, %M minutes, %S seconds.
- One line carries "real time / rows moved this tick / failures / latest data time". Real time minus data
  time = how far behind we are.

## Entry point
```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=60, help="seconds between ticks")
    ap.add_argument("--once", action="store_true", help="run one tick and exit")
    args = ap.parse_args()
```
- `--interval`: seconds per tick. Default 60 (one reading per minute). `type=float` allows `--interval 2.5`.
- `--once`: `action="store_true"` = True if given, False otherwise. A switch that takes no value.
- Read back as `args.interval`, `args.once`.

```python
    con = collector.open_db()
    print(f"stream loop: tick every {args.interval:g} s  (ctrl-c to stop)")
    try:
        while True:                  # repeat forever
            tick(con)
            if args.once:
                break                # with --once, do one tick and leave the loop
            time.sleep(args.interval)
    except KeyboardInterrupt:        # Ctrl-C makes Python raise this
        print("\nstopped")
```
- `while True` + `break`: an endless loop that exits when the condition is met.
- `:g` formatting: 60.0 prints as "60", 2.5 as "2.5".
- `try / except KeyboardInterrupt`: stopping with Ctrl-C prints "stopped" instead of a red error.

## Test result
`generator.py live --fast` (1 s = 1 minute) and `stream.py --interval 5` running together (on a scratch copy):
```
stream loop: tick every 5 s  (ctrl-c to stop)
[03:37:39] +189 rows (0 parse errors)  latest reading 2026-09-04T02:34:00+00:00
[03:37:44] +315 rows (0 parse errors)  latest reading 2026-09-04T02:39:00+00:00
[03:37:49] +315 rows (0 parse errors)  latest reading 2026-09-04T02:44:00+00:00
[03:37:54] +315 rows (0 parse errors)  latest reading 2026-09-04T02:49:00+00:00
[03:37:59] +315 rows (0 parse errors)  latest reading 2026-09-04T02:54:00+00:00
```
- 5 seconds = 5 minutes of data = 63 rows × 5 = 315. (One minute = 3 weather + 15 servers × 4 sensors = 63 rows.)
- The first tick's 189 = 3 minutes, because the generator started 3 seconds earlier.
- At the end raw was at 02:55 and clean at 02:54 — the one-minute gap the next tick picks up. Normal.
