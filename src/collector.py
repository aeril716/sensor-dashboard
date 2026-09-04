"""
collector.py — turn raw sensor text into clean numbers.

What it does:
  1. Reads rows from raw_readings that it hasn't cleaned yet
     (everything newer than the newest row already in clean_readings).
  2. Interprets each raw text according to the sensor's format:
       cpu_temp      i2c integer, degrees C = raw / 16
       fan_rpm       i2c integer, rpm as-is
       power_draw    JSON, take "watts"
       mem_used      text line "Mem:  total 256G  used 83G  free 173G", take used GB
       outside_temp  JSON, take "temp_c"
  3. Joins host info (dc, city) from the hosts table.
  4. Writes one clean row per raw row into clean_readings.

Rules (PLAN.md, decided 2026-09-03):
  - The collector only cleans. It never judges values: -1 C is written as -1.0.
  - If the raw text can't be read, the row is still written with value NULL
    and a short parse_error saying why. Nothing is dropped silently.
  - parse_error texts are fixed strings so triage can count them later.

Usage:
  python collector.py            # clean everything new, print a summary
"""

import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "telemetry.db"   # <repo>/data/telemetry.db

# ---------------------------------------------------------------------------
# 1. Parsers — one per sensor. Each returns a number or raises ValueError.
# ---------------------------------------------------------------------------

def json_field(raw, key):
    """Read a JSON text and return one field from it."""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("invalid_json")
    if not isinstance(obj, dict) or key not in obj:
        raise ValueError(f"missing_field:{key}")
    return obj[key]


def parse_cpu_temp(raw):
    return round(int(raw) / 16, 1)          # i2c chip: 918 -> 57.4 C


def parse_fan_rpm(raw):
    return int(raw)                          # 4730 -> 4730 rpm


def parse_power_draw(raw):
    return json_field(raw, "watts")          # {"psu": 1, "watts": 409.6, ...} -> 409.6


def parse_mem_used(raw):
    m = re.search(r"used (\d+)G", raw)       # "... used 83G ..." -> 83
    if m is None:
        raise ValueError("pattern_not_found")
    return int(m.group(1))


def parse_outside_temp(raw):
    return json_field(raw, "temp_c")         # {"temp_c": 24.8, ...} -> 24.8


PARSERS = {
    "cpu_temp": parse_cpu_temp,
    "fan_rpm": parse_fan_rpm,
    "power_draw": parse_power_draw,
    "mem_used": parse_mem_used,
    "outside_temp": parse_outside_temp,
}


def parse(sensor, raw):
    """Returns (value, parse_error). Exactly one of the two is None."""
    fn = PARSERS.get(sensor)
    if fn is None:
        return None, "unknown_sensor"
    try:
        return float(fn(raw)), None
    except ValueError as e:
        msg = str(e)
        # int()/float() failures carry the bad text in the message ("invalid literal
        # for int() with base 10: 'ERR'"). Replace with one fixed text so errors group.
        if msg.startswith("invalid literal") or msg.startswith("could not convert"):
            msg = "not_a_number"
        return None, msg
    except TypeError:
        return None, "not_a_number"          # e.g. "watts": null


# ---------------------------------------------------------------------------
# 2. Host info
# ---------------------------------------------------------------------------

def load_hosts(con):
    """host_id -> (dc, city) for the 15 servers."""
    return {host_id: (dc, city) for host_id, dc, city in con.execute("SELECT host_id, dc, city FROM hosts")}


def host_info(host_id, hosts):
    if host_id in hosts:
        return hosts[host_id]
    if host_id.endswith("-weather"):         # dc-east-weather -> dc-east, no city
        return host_id[: -len("-weather")], None
    return None, None


# ---------------------------------------------------------------------------
# 3. Storage
# ---------------------------------------------------------------------------

def open_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS clean_readings (
            ts_utc      TEXT NOT NULL,
            host_id     TEXT NOT NULL,
            dc          TEXT,
            city        TEXT,
            sensor      TEXT NOT NULL,
            raw         TEXT NOT NULL,
            value       REAL,
            parse_error TEXT
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_clean_ts ON clean_readings(ts_utc)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_clean_host_sensor ON clean_readings(host_id, sensor, ts_utc)")
    return con


# ---------------------------------------------------------------------------
# 4. One pass = clean everything that is new
# ---------------------------------------------------------------------------

def collect_once(con):
    """Clean every raw row newer than the newest clean row. Returns (rows_written, parse_errors)."""
    hosts = load_hosts(con)
    last = con.execute("SELECT MAX(ts_utc) FROM clean_readings").fetchone()[0] or ""
    new_rows = con.execute(
        "SELECT ts_utc, host_id, sensor, raw FROM raw_readings WHERE ts_utc > ? ORDER BY ts_utc, host_id",
        (last,),
    )

    out = []
    errors = 0
    for ts, host_id, sensor, raw in new_rows:
        dc, city = host_info(host_id, hosts)
        value, err = parse(sensor, raw)
        if err is not None:
            errors += 1
        out.append((ts, host_id, dc, city, sensor, raw, value, err))

    con.executemany("INSERT INTO clean_readings VALUES (?,?,?,?,?,?,?,?)", out)
    con.commit()
    return len(out), errors


# ---------------------------------------------------------------------------
# 5. Entry point
# ---------------------------------------------------------------------------

def main():
    con = open_db()
    n, errors = collect_once(con)
    total = con.execute("SELECT COUNT(*) FROM clean_readings").fetchone()[0]
    print(f"collected {n} new rows ({errors} parse errors) -> clean_readings now has {total} rows")


if __name__ == "__main__":
    main()
