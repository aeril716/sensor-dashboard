"""
stream.py — the tick loop.

Every tick it pulls whatever new raw rows the generator has written into
clean_readings (via collector.collect_once) and prints one status line.
Later phases add detection and the dashboard refresh to the same tick.

Usage:
  python stream.py                  # tick every 60 s (matches one reading per minute)
  python stream.py --interval 5     # faster ticks, for `generator.py live --fast`
  python stream.py --once           # one tick, then exit
"""

import argparse
import time
from datetime import datetime, timezone

import collector


def tick(con):
    """One pass: collect new rows, report. Returns the number of rows collected."""
    n, errors = collector.collect_once(con)
    latest = con.execute("SELECT MAX(ts_utc) FROM clean_readings").fetchone()[0]
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{now}] +{n} rows ({errors} parse errors)  latest reading {latest}")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=60, help="seconds between ticks")
    ap.add_argument("--once", action="store_true", help="run one tick and exit")
    args = ap.parse_args()

    con = collector.open_db()
    print(f"stream loop: tick every {args.interval:g} s  (ctrl-c to stop)")
    try:
        while True:
            tick(con)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
