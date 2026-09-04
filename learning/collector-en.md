# collector.py, line by line

collector.py has five parts: ① one parser per sensor, ② attach dc/city from `hosts`, ③ create the table,
④ read only the new raw rows and write them, ⑤ entry point.

## ① Parsers — collector.py lines 25–88

**Three imports**
```python
import json      # turns JSON text into Python values
import re        # finds patterns inside text (regular expressions)
import sqlite3   # opens the SQLite database
DB_PATH = ...    # the database path, written down in one place
```

**Shared helper — pull one field out of JSON**
```python
def json_field(raw, key):
    try:
        obj = json.loads(raw)          # text -> dict. e.g. '{"watts": 409.6}' -> {"watts": 409.6}
    except json.JSONDecodeError:       # not JSON-shaped -> land here
        raise ValueError("invalid_json")
    if not isinstance(obj, dict) or key not in obj:   # not a dict, or the field is missing
        raise ValueError(f"missing_field:{key}")
    return obj[key]                    # the field's value. obj["watts"] -> 409.6
```
`try / except` means "try this; if it fails, do that instead". `raise ValueError("…")` means "stop here and
throw this reason". That reason text becomes the `parse_error` column later, unchanged.

**Five parsers — each takes one raw string and returns one number**
```python
def parse_cpu_temp(raw):
    return round(int(raw) / 16, 1)    # "918" -> 918 -> 57.375 -> 57.4

def parse_fan_rpm(raw):
    return int(raw)                   # "4730" -> 4730

def parse_power_draw(raw):
    return json_field(raw, "watts")   # '{"psu": 1, "watts": 409.6, "status": "ok"}' -> 409.6

def parse_mem_used(raw):
    m = re.search(r"used (\d+)G", raw)    # find "used 83G". \d+ = one or more digits, ( ) = remember this part
    if m is None:                         # not found
        raise ValueError("pattern_not_found")
    return int(m.group(1))                # the remembered part -> "83" -> 83

def parse_outside_temp(raw):
    return json_field(raw, "temp_c")  # '{"temp_c": 24.8, ...}' -> 24.8
```
`int("918")` turns text into an integer. If the text is not a number (`"ERR"`) Python raises `ValueError`
by itself — that is why there is no explicit `raise` there.

**Name → function**
```python
PARSERS = {
    "cpu_temp": parse_cpu_temp,
    "fan_rpm": parse_fan_rpm,
    "power_draw": parse_power_draw,
    "mem_used": parse_mem_used,
    "outside_temp": parse_outside_temp,
}
```
A dict. `PARSERS["cpu_temp"]` gives the function `parse_cpu_temp`. A new sensor is one new line.

**The one function everything else calls**
```python
def parse(sensor, raw):
    fn = PARSERS.get(sensor)              # look it up; None if unknown (no error)
    if fn is None:
        return None, "unknown_sensor"     # no value, a reason
    try:
        return float(fn(raw)), None       # success: a value, no reason
    except ValueError as e:
        msg = str(e)
        if msg.startswith("invalid literal") or msg.startswith("could not convert"):
            msg = "not_a_number"          # Python's own message varies; replace with one fixed text
        return None, msg
    except TypeError:
        return None, "not_a_number"       # e.g. "watts": null
```
Always returns **(value, reason)**, and exactly one of the two is `None`.

- success: `parse("cpu_temp", "918")` → `(57.4, None)`
- failure: `parse("cpu_temp", "ERR")` → `(None, "not_a_number")`

Why replace `msg` with a fixed string: Python's original is `invalid literal for int() with base 10: 'ERR'` —
it contains the bad value, so it is different every time and "how many times did this error happen" could not
be counted later (PLAN.md rule).

Actual results:
```
sensor       raw                                      -> value      parse_error
cpu_temp     '-16'                                    -> -1.0       None            (not judged, written as-is)
cpu_temp     'ERR'                                    -> None       not_a_number
cpu_temp     ''                                       -> None       not_a_number
fan_rpm      'nan'                                    -> None       not_a_number
power_draw   '{"psu": 1, "watts": '                   -> None       invalid_json
power_draw   '{"psu": 1, "status": "ok"}'             -> None       missing_field:watts
power_draw   '{"psu": 1, "watts": null}'              -> None       not_a_number
mem_used     'Mem:  total 256G  used ?G  free ?G'     -> None       pattern_not_found
mem_used     'Mem:  total 256G  used 0G  free 256G'   -> 0.0        None
gpu_temp     '77'                                     -> None       unknown_sensor
```

## ② Attach dc/city from hosts — collector.py lines 91–105

```python
def load_hosts(con):
    """host_id -> (dc, city) for the 15 servers."""
    return {host_id: (dc, city)
            for host_id, dc, city in con.execute("SELECT host_id, dc, city FROM hosts")}
```
- `con.execute("SELECT …")` sends SQL to the database and gets rows back; the hosts table has 15.
- `for host_id, dc, city in …`: each row has 3 columns, unpacked into 3 variables at once.
- `{ key: value for … }` builds a dict while looping. Result:
  `{"dc-east-s1": ("dc-east", "Ashburn"), "dc-east-s2": ("dc-east", "Ashburn"), …}` — 15 entries.
- `(dc, city)` in parentheses is a tuple: two values as one unit.

The point of this function: ask the database once at start and keep the answers in a dict, instead of asking
180,000 times.

```python
def host_info(host_id, hosts):
    if host_id in hosts:                       # a server: it is in the dict
        return hosts[host_id]                  # ("dc-east", "Ashburn")
    if host_id.endswith("-weather"):           # weather rows are not in the hosts table
        return host_id[: -len("-weather")], None   # "dc-east-weather" -> "dc-east", no city
    return None, None                          # neither: unknown
```
- `host_id in hosts`: is this key in the dict? If so `hosts[host_id]` fetches it.
- `endswith("-weather")`: does the text end with this?
- `host_id[: -len("-weather")]`: slicing. `len("-weather")` is 8; `[:-8]` means "everything except the last 8
  characters". `"dc-east-weather"[:-8]` → `"dc-east"`.
- Always returns (dc, city); `None` where unknown.

Examples:
- `host_info("dc-west-s5", hosts)` → `("dc-west", "Sacramento")`
- `host_info("dc-hawaii-weather", hosts)` → `("dc-hawaii", None)`
- `host_info("mystery-box", hosts)` → `(None, None)`

## ③ Create the table — collector.py lines 108–128

```python
def open_db():
    con = sqlite3.connect(DB_PATH)          # open telemetry.db (created if missing)
    con.execute("""
        CREATE TABLE IF NOT EXISTS clean_readings (
            ts_utc      TEXT NOT NULL,      # time (UTC text)         NOT NULL = may not be empty
            host_id     TEXT NOT NULL,      # dc-east-s4
            dc          TEXT,               # dc-east   (weather rows have it too)
            city        TEXT,               # Ashburn   (empty for weather rows)
            sensor      TEXT NOT NULL,      # cpu_temp
            raw         TEXT NOT NULL,      # the original text, kept
            value       REAL,               # the number (decimals allowed). Empty if unreadable
            parse_error TEXT                # why it was unreadable. Empty if it parsed
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_clean_ts ON clean_readings(ts_utc)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_clean_host_sensor ON clean_readings(host_id, sensor, ts_utc)")
    return con
```
- `IF NOT EXISTS`: skip if it already exists, so running the collector repeatedly is safe.
- `TEXT` is text, `REAL` is a decimal number. SQLite types worth knowing: these two plus `INTEGER`.
- `"""…"""` is a multi-line string.
- An index is like the index at the back of a book. Two were made for "find by time" and "find this server's
  sensor in time order". Without them everything still works, just slower.

## ④ Read only the new raw rows and write them — collector.py lines 131–152

```python
def collect_once(con):
    hosts = load_hosts(con)                                          # ② the 15-entry dict
    last = con.execute("SELECT MAX(ts_utc) FROM clean_readings").fetchone()[0] or ""
    new_rows = con.execute(
        "SELECT ts_utc, host_id, sensor, raw FROM raw_readings WHERE ts_utc > ? ORDER BY ts_utc, host_id",
        (last,),
    )
```
- `MAX(ts_utc)`: the latest time already in the clean table. `.fetchone()` is the first result row, `[0]` its first column.
- `or ""`: if the table is empty MAX is `None`, which becomes `""` (empty text). Empty text sorts before any
  text, so `ts_utc > ""` matches everything → the first run reads it all.
- `WHERE ts_utc > ?`: the question mark is filled from `(last,)`. Using `?` instead of pasting the value into
  the SQL text is the proper way (safe even if the value contains quotes).
- The trailing comma in `(last,)` makes a one-element tuple; without it, it is just a string and errors.
- On the second run `last` is `2026-09-04T02:31:00+00:00`, no raw rows are later → 0 rows.

```python
    out = []
    errors = 0
    for ts, host_id, sensor, raw in new_rows:       # one raw row at a time
        dc, city = host_info(host_id, hosts)         # ②
        value, err = parse(sensor, raw)              # ①
        if err is not None:
            errors += 1                              # just counting failures
        out.append((ts, host_id, dc, city, sensor, raw, value, err))   # 8 fields = the table's column order

    con.executemany("INSERT INTO clean_readings VALUES (?,?,?,?,?,?,?,?)", out)
    con.commit()                                     # make it permanent. Without this nothing reaches the file
    return len(out), errors
```
- `out.append(...)` adds a row to the list; 180k rows are gathered in memory and then
- `executemany` inserts them in one go. Inserting one at a time with `execute` is far slower.
- Eight question marks = eight columns; the tuple order must match ③ exactly.
- Returns (rows written, failures).

Why "new" can be decided by time: the generator commits a whole minute (63 rows) at once, so any minute is
either fully present or absent. There is no half-written minute.

## ⑤ Entry point — collector.py lines 155–163

```python
def main():
    con = open_db()                                   # ③
    n, errors = collect_once(con)                     # ④
    total = con.execute("SELECT COUNT(*) FROM clean_readings").fetchone()[0]
    print(f"collected {n} new rows ({errors} parse errors) -> clean_readings now has {total} rows")

if __name__ == "__main__":
    main()
```
- `f"…{n}…"`: inserts variable values into the `{ }` slots.
- `if __name__ == "__main__"`: "run main() only when this file is executed directly". When another file does
  `import collector` to borrow the parsers, it does not run. (The tests calling `c.parse(...)` are an example.)

Run output:
```
collected 181036 new rows (0 parse errors) -> clean_readings now has 181036 rows   # 1st run
collected 0 new rows (0 parse errors) -> clean_readings now has 181036 rows        # 2nd run
```
