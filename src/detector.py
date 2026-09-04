"""
detector.py — finds what is unusual in clean_readings. Evidence only, no failure names.

Each rule is a function. Every number (the line, how many minutes) is a parameter —
PLAN.md: Aeri sets every number, from looking at the clean data.
The detector never reads generator.py or ground_truth.csv.

Output = episodes. One episode = one host, one sensor, one stretch of time where the rule
held, with how long, how far, and which rule. That is the evidence Phase 3 will name.

Usage:
  python detector.py threshold cpu_temp 65 --minutes 10           # above the line
  python detector.py threshold fan_rpm 2000 --below --minutes 10  # below the line
"""

import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "telemetry.db"   # <repo>/data/telemetry.db


# ---------------------------------------------------------------------------
# 1. Load — one sensor, all hosts, time-ordered
# ---------------------------------------------------------------------------

def load_series(con, sensor):
    """host_id -> list of (ts_utc, value) for one sensor. Rows with no value are skipped."""
    series = {}
    rows = con.execute(
        "SELECT host_id, ts_utc, value FROM clean_readings WHERE sensor = ? AND value IS NOT NULL ORDER BY host_id, ts_utc",
        (sensor,),
    )
    for host_id, ts, value in rows:
        series.setdefault(host_id, []).append((ts, value))
    return series


# ---------------------------------------------------------------------------
# 2. Rule: threshold — past a fixed line for at least N readings in a row
# ---------------------------------------------------------------------------

def threshold(series, sensor, line, minutes, below=False):
    """Episodes where value is above `line` (or below, if below=True) for >= `minutes`
    consecutive readings. Readings are one per minute, so readings == minutes."""
    sign = "<" if below else ">"
    rule = f"{sensor} {sign} {line:g} for >= {minutes} min"
    episodes = []

    def close(host_id, run):
        if len(run) >= minutes:
            values = [v for _, v in run]
            episodes.append({
                "host_id": host_id,
                "sensor": sensor,
                "start": run[0][0],
                "end": run[-1][0],
                "minutes": len(run),
                "peak": min(values) if below else max(values),
                "rule": rule,
            })

    for host_id, points in series.items():
        run = []                                   # the current stretch past the line
        for ts, value in points:
            past = value < line if below else value > line
            if past:
                run.append((ts, value))
            else:
                close(host_id, run)
                run = []
        close(host_id, run)                        # stretch still open at the end of data

    return sorted(episodes, key=lambda e: e["start"])


# ---------------------------------------------------------------------------
# 3. Print evidence
# ---------------------------------------------------------------------------

def print_episodes(episodes):
    if not episodes:
        print("no episodes")
        return
    print(f"{'host_id':<16}{'sensor':<12}{'start (UTC)':<26}{'end (UTC)':<26}{'min':>5}{'peak':>8}   rule")
    for e in episodes:
        print(f"{e['host_id']:<16}{e['sensor']:<12}{e['start']:<26}{e['end']:<26}{e['minutes']:>5}{e['peak']:>8.1f}   {e['rule']}")


# ---------------------------------------------------------------------------
# 4. Entry point
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="rule", required=True)
    t = sub.add_parser("threshold", help="value past a fixed line for N minutes")
    t.add_argument("sensor")
    t.add_argument("line", type=float)
    t.add_argument("--minutes", type=int, default=10)
    t.add_argument("--below", action="store_true", help="fire when value is BELOW the line")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    if args.rule == "threshold":
        series = load_series(con, args.sensor)
        print_episodes(threshold(series, args.sensor, args.line, args.minutes, args.below))


if __name__ == "__main__":
    main()
