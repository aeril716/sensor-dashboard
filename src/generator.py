"""
generator.py — fake sensors for a streaming-service server fleet.

What it does:
  1. Builds 3 datacenters x 5 servers with host info.
  2. Every minute, computes load -> temp / fan / power / memory for each server.
  3. Injects random failures (seeded) and writes the answer key to ground_truth.csv.
  4. Emits RAW sensor readings only (no tags, no units) into SQLite table raw_readings.
     The collector script (next step) is the one that interprets and tags them.

Usage:
  python generator.py backfill --hours 48 --seed 42      # write 48h of history at once
  python generator.py live --seed 42                     # then keep adding one minute per real minute
  python generator.py live --seed 42 --fast              # one minute per second (demo)
"""

import argparse
import csv
import json
import math
import random
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# data lives in <repo>/data, next to src/, whatever folder the script is run from
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "telemetry.db"
TRUTH_PATH = DATA_DIR / "ground_truth.csv"

# ---------------------------------------------------------------------------
# 1. Fleet definition (host info)
# ---------------------------------------------------------------------------

# outside temp: normal early-September daily low (~03:00) and high (~15:00), Celsius
DATACENTERS = {
    "dc-east":   {"region": "us-east-1", "city": "Ashburn",    "tz": "America/New_York",    "low": 22.0, "high": 32.0},
    "dc-west":   {"region": "us-west-2", "city": "Sacramento", "tz": "America/Los_Angeles", "low": 15.0, "high": 33.0},
    "dc-hawaii": {"region": "us-hawaii", "city": "Honolulu",   "tz": "Pacific/Honolulu",    "low": 24.0, "high": 34.0},
}

# heat wave, modelled on Sacramento Sept 2022: overnight low 22 vs usual 15, high 46 vs usual 33.
# It ramps in over HEAT_RAMP_UP_H hours, holds at full strength during the planned
# ambient_high window, then fades over HEAT_RAMP_DOWN_H hours. No steps.
HEAT_WAVE_LOW_PLUS = 7.0
HEAT_WAVE_HIGH_PLUS = 13.0
HEAT_RAMP_UP_H = 30
HEAT_RAMP_DOWN_H = 12

MODELS = ["SuperServer 2U EPYC 9654", "Dell R7625", "HPE DL385 Gen11"]
FIRMWARE = ["2.3.1", "2.3.1", "2.4.0"]  # most on 2.3.1, some on 2.4.0

US_HOLIDAYS = {"2026-01-01", "2026-07-04", "2026-09-07", "2026-11-26", "2026-12-25"}


def build_fleet(rng):
    """Returns a list of 15 host dicts. Each server gets a model, firmware, rack slot."""
    fleet = []
    for dc_id, dc in DATACENTERS.items():
        for n in range(1, 6):
            fleet.append({
                "host_id": f"{dc_id}-s{n}",
                "dc": dc_id,
                "region": dc["region"],
                "city": dc["city"],
                "tz": dc["tz"],
                "model": rng.choice(MODELS),
                "firmware": rng.choice(FIRMWARE),
                "rack": f"R{rng.randint(1, 12):02d}",
                "slot": n,
                "popularity": rng.uniform(0.7, 1.0),  # some servers just get more traffic
            })
    return fleet


# ---------------------------------------------------------------------------
# 2. Load curve — entertainment streaming, in LOCAL time
# ---------------------------------------------------------------------------

def schedule(local_dt):
    """The load schedule as steps: fraction 0..1 of how busy a streaming server is at this local time."""
    h = local_dt.hour + local_dt.minute / 60
    is_weekend = local_dt.weekday() >= 5 or local_dt.strftime("%Y-%m-%d") in US_HOLIDAYS
    is_friday = local_dt.weekday() == 4

    if is_weekend:
        # heavy from early afternoon through night
        if 13 <= h < 24:
            return 0.80
        if 9 <= h < 13:
            return 0.50
        return 0.20
    if 9 <= h < 11:
        return 0.50                         # morning bump
    if 16 <= h < 23:
        if is_friday and h >= 20:
            return 0.95                     # friday night highest
        return 0.85                         # evening peak
    if 23 <= h or h < 2:
        return 0.40
    return 0.15


def load_at(local_dt):
    """Smoothed load: the average of the schedule over the surrounding hour (30 min back,
    30 min forward). A 0.15 -> 0.85 step at 16:00 becomes a straight ramp from 15:30 to 16:30,
    so no sensor jumps at the hour."""
    samples = [schedule(local_dt + timedelta(minutes=m)) for m in range(-30, 30)]
    return sum(samples) / len(samples)


# ---------------------------------------------------------------------------
# 3. Failure injection (seeded random) + ground truth
# ---------------------------------------------------------------------------

FAILURE_WEIGHTS = {
    "ambient_high": {"dc-east": 0.7, "dc-west": 0.2, "dc-hawaii": 0.1},
    "cooling_fail": {"dc-east": 0.25, "dc-west": 0.25, "dc-hawaii": 0.5},
}


def pick_dc(rng, weights):
    dcs = list(weights.keys())
    return rng.choices(dcs, weights=[weights[d] for d in dcs])[0]


def plan_failures(rng, fleet, start, hours):
    """Decide which failures happen where and when. Returns a list of dicts."""
    end = start + timedelta(hours=hours)

    def rand_time(min_minutes_before_end, tz, weight_fn):
        """Pick a start minute. Every minute is possible, but a minute's chance is
        proportional to weight_fn(local time) — busy hours for server failures
        (servers fail more when busy), hot hours for the heat wave."""
        span = int((end - start).total_seconds() / 60) - min_minutes_before_end
        minutes = list(range(60, max(61, span)))
        weights = [weight_fn((start + timedelta(minutes=m)).astimezone(ZoneInfo(tz))) for m in minutes]
        return start + timedelta(minutes=rng.choices(minutes, weights=weights)[0])

    def servers_in(dc):
        return [h for h in fleet if h["dc"] == dc]

    plans = []

    dc = pick_dc(rng, FAILURE_WEIGHTS["ambient_high"])
    t = rand_time(240, DATACENTERS[dc]["tz"], daily_curve)
    plans.append({"failure": "ambient_high", "scope": dc, "start": t, "end": t + timedelta(minutes=rng.randint(120, 240)), "note": "outside temp exceeds cooling design envelope"})

    dc = pick_dc(rng, FAILURE_WEIGHTS["cooling_fail"])
    host = rng.choice(servers_in(dc))
    t = rand_time(180, host["tz"], load_at)
    plans.append({"failure": "cooling_fail", "scope": host["host_id"], "start": t, "end": t + timedelta(minutes=rng.randint(90, 150)), "note": "fan degrades over ~40 min, temp follows"})

    dc = rng.choice(list(DATACENTERS))
    t = rand_time(60, DATACENTERS[dc]["tz"], load_at)
    plans.append({"failure": "power_outage", "scope": dc, "start": t, "end": t + timedelta(minutes=rng.randint(8, 25)), "note": "whole DC goes silent, returns cool"})

    host = rng.choice(fleet)
    t = rand_time(120, host["tz"], load_at)
    plans.append({"failure": "overload", "scope": host["host_id"], "start": t, "end": t + timedelta(minutes=rng.randint(60, 120)), "note": "load pinned at 100%, memory creeps up"})

    host = rng.choice(fleet)
    sensor = rng.choice(["cpu_temp", "mem_used", "fan_rpm"])
    t = rand_time(60, host["tz"], load_at)
    plans.append({"failure": "sensor_fault", "scope": f"{host['host_id']}/{sensor}", "start": t, "end": t + timedelta(minutes=rng.randint(20, 60)), "note": "sensor returns frozen or invalid value"})

    host = rng.choice(fleet)
    t = rand_time(60, host["tz"], load_at)
    plans.append({"failure": "server_stop", "scope": host["host_id"], "start": t, "end": t + timedelta(minutes=rng.randint(15, 50)), "note": "server goes silent with no warning signs"})

    return sorted(plans, key=lambda p: p["start"])


def active_failures(plans, now):
    return [p for p in plans if p["start"] <= now < p["end"]]


# ---------------------------------------------------------------------------
# 4. Physics — one minute for one server
# ---------------------------------------------------------------------------

def daily_curve(local_dt):
    """Where in the day's temperature swing we are: 0 = coolest (~03:00), 1 = warmest (~15:00)."""
    h = local_dt.hour + local_dt.minute / 60
    return 0.5 + 0.5 * math.sin((h - 9) / 24 * 2 * math.pi)


def heat_wave_strength(dc_id, now_utc, plans):
    """0 = normal weather, 1 = full heat wave. Ramps up before the planned ambient_high
    window, holds at 1 during it, ramps down after. Linear, so no jumps."""
    for p in plans:
        if p["failure"] == "ambient_high" and p["scope"] == dc_id:
            up = timedelta(hours=HEAT_RAMP_UP_H)
            down = timedelta(hours=HEAT_RAMP_DOWN_H)
            if p["start"] - up <= now_utc < p["start"]:
                return (now_utc - (p["start"] - up)) / up
            if p["start"] <= now_utc < p["end"]:
                return 1.0
            if p["end"] <= now_utc < p["end"] + down:
                return 1.0 - (now_utc - p["end"]) / down
    return 0.0


def outside_temp(dc_id, now_utc, plans, rng):
    """Outside air temp for a datacenter: today's low..high scaled by the daily curve, plus noise.
    A heat wave raises both the low (nights don't cool) and the high."""
    dc = DATACENTERS[dc_id]
    local = now_utc.astimezone(ZoneInfo(dc["tz"]))
    strength = heat_wave_strength(dc_id, now_utc, plans)
    low = dc["low"] + strength * HEAT_WAVE_LOW_PLUS
    high = dc["high"] + strength * HEAT_WAVE_HIGH_PLUS
    return low + (high - low) * daily_curve(local) + rng.gauss(0, 0.4)


def simulate_server(host, now_utc, plans, rng, state):
    """
    Returns dict of sensor -> true value, or None if the server is silent.
    `state` keeps per-server memory between minutes (memory creep, fan degradation).
    """
    active = active_failures(plans, now_utc)
    dc_id = host["dc"]
    hid = host["host_id"]

    # silence: power outage (whole DC) or server_stop (one server)
    for p in active:
        if (p["failure"] == "power_outage" and p["scope"] == dc_id) or \
           (p["failure"] == "server_stop" and p["scope"] == hid):
            state[hid]["mem"] = 40.0          # reboot clears memory
            state[hid]["fan_health"] = 1.0
            return None

    local = now_utc.astimezone(ZoneInfo(host["tz"]))
    load = load_at(local) * host["popularity"]

    for p in active:
        if p["failure"] == "overload" and p["scope"] == hid:
            load = 1.0

    # fan degradation for cooling_fail: health goes 1.0 -> 0.3 over 40 minutes
    fan_health = 1.0
    for p in active:
        if p["failure"] == "cooling_fail" and p["scope"] == hid:
            minutes_in = (now_utc - p["start"]).total_seconds() / 60
            fan_health = max(0.3, 1.0 - 0.7 * min(1.0, minutes_in / 40))
    state[hid]["fan_health"] = fan_health

    outside = state["outside"][dc_id]
    ambient_push = max(0.0, outside - 30.0) * 0.6            # only matters above ~30°C outside

    # temperature model: idle 40°C, load adds up to ~22°C, fan removes heat, ambient adds
    temp = 40.0 + load * 22.0 + ambient_push - (fan_health - 1.0) * 30.0 + rng.gauss(0, 0.6)

    # throttling: server protects itself above 75°C, power drops as it slows down
    throttled = temp > 75.0
    if throttled:
        temp = 75.0 + rng.gauss(0, 0.5)

    fan_rpm = (2500 + load * 2500 + max(0, temp - 55) * 80) * fan_health + rng.gauss(0, 60)
    power = 180 + load * 300 + rng.gauss(0, 8)
    if throttled:
        power *= 0.7

    # memory: follows load slowly, creeps during overload
    target_mem = 60 + load * 100
    state[hid]["mem"] += (target_mem - state[hid]["mem"]) * 0.05
    for p in active:
        if p["failure"] == "overload" and p["scope"] == hid:
            state[hid]["mem"] += 0.8
    mem = min(250.0, state[hid]["mem"] + rng.gauss(0, 1.0))

    values = {"cpu_temp": temp, "fan_rpm": fan_rpm, "power_draw": power, "mem_used": mem}

    # sensor fault: one sensor lies
    for p in active:
        if p["failure"] == "sensor_fault" and p["scope"].startswith(hid + "/"):
            sensor = p["scope"].split("/")[1]
            kind = state["fault_kind"].setdefault(p["scope"], rng.choice(["frozen", "invalid"]))
            if kind == "frozen":
                frozen = state["frozen"].setdefault(p["scope"], values[sensor])
                values[sensor] = frozen
            else:
                values[sensor] = -1.0
    return values


# ---------------------------------------------------------------------------
# 5. Raw encoding — what each sensor actually spits out (no tags, no units)
# ---------------------------------------------------------------------------

def encode_raw(sensor, value):
    """Return (source, raw_text). This is the messy part the collector has to undo."""
    if sensor == "cpu_temp":
        # i2c temp chips give a raw integer; degrees = raw / 16
        return "i2c", str(int(round(value * 16)))
    if sensor == "fan_rpm":
        return "i2c", str(int(round(value)))
    if sensor == "power_draw":
        return "api", json.dumps({"psu": 1, "watts": round(value, 1), "status": "ok"})
    if sensor == "mem_used":
        total = 256
        used = max(0, value)
        return "cli", f"Mem:  total {total}G  used {used:.0f}G  free {total - used:.0f}G"
    if sensor == "outside_temp":
        return "api", json.dumps({"temp_c": round(value, 1), "provider": "weather-feed"})
    raise ValueError(sensor)


# ---------------------------------------------------------------------------
# 6. Storage
# ---------------------------------------------------------------------------

def open_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw_readings (
            ts_utc   TEXT NOT NULL,
            host_id  TEXT NOT NULL,
            sensor   TEXT NOT NULL,
            source   TEXT NOT NULL,
            raw      TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS hosts (
            host_id TEXT PRIMARY KEY, dc TEXT, region TEXT, city TEXT, tz TEXT,
            model TEXT, firmware TEXT, rack TEXT, slot INTEGER
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_raw_ts ON raw_readings(ts_utc)")
    return con


def write_hosts(con, fleet):
    con.executemany(
        "INSERT OR REPLACE INTO hosts VALUES (?,?,?,?,?,?,?,?,?)",
        [(h["host_id"], h["dc"], h["region"], h["city"], h["tz"], h["model"], h["firmware"], h["rack"], h["slot"]) for h in fleet],
    )
    con.commit()


def write_truth(plans, seed, append=False):
    """backfill overwrites the answer key; live appends to it so the backfill answers survive."""
    with open(TRUTH_PATH, "a" if append else "w", newline="") as f:
        w = csv.writer(f)
        if f.tell() == 0:                       # empty/new file -> write the header once
            w.writerow(["seed", "failure", "scope", "start_utc", "end_utc", "note"])
        for p in plans:
            w.writerow([seed, p["failure"], p["scope"], p["start"].isoformat(), p["end"].isoformat(), p["note"]])


# ---------------------------------------------------------------------------
# 7. One tick = one minute for the whole fleet
# ---------------------------------------------------------------------------

def tick(con, fleet, plans, now_utc, rng, state):
    rows = []
    ts = now_utc.isoformat()

    for dc_id in DATACENTERS:
        out = outside_temp(dc_id, now_utc, plans, rng)
        state["outside"][dc_id] = out
        src, raw = encode_raw("outside_temp", out)
        rows.append((ts, f"{dc_id}-weather", "outside_temp", src, raw))

    for host in fleet:
        values = simulate_server(host, now_utc, plans, rng, state)
        if values is None:
            continue                          # silent server writes nothing — that IS the signal
        for sensor, v in values.items():
            src, raw = encode_raw(sensor, v)
            rows.append((ts, host["host_id"], sensor, src, raw))

    con.executemany("INSERT INTO raw_readings VALUES (?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def fresh_state(fleet):
    return {
        "outside": {},
        "frozen": {},
        "fault_kind": {},
        **{h["host_id"]: {"mem": 80.0, "fan_health": 1.0} for h in fleet},
    }


# ---------------------------------------------------------------------------
# 8. Entry point
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["backfill", "live"])
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fast", action="store_true", help="live mode: 1 simulated minute per real second")
    ap.add_argument("--start", default=None, help="backfill start, ISO UTC. default: now - hours")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    fleet = build_fleet(rng)
    DATA_DIR.mkdir(exist_ok=True)
    con = open_db()
    write_hosts(con, fleet)
    state = fresh_state(fleet)

    if args.mode == "backfill":
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        start = datetime.fromisoformat(args.start) if args.start else now - timedelta(hours=args.hours)
        plans = plan_failures(rng, fleet, start, args.hours)
        write_truth(plans, args.seed)
        t = start
        total = 0
        while t < start + timedelta(hours=args.hours):
            total += tick(con, fleet, plans, t, rng, state)
            t += timedelta(minutes=1)
        print(f"backfill done: {args.hours}h, {total} raw rows, {len(plans)} failures -> {TRUTH_PATH.name}")

    else:  # live
        # continue from the last timestamp in the DB, or from now
        row = con.execute("SELECT MAX(ts_utc) FROM raw_readings").fetchone()
        t = datetime.fromisoformat(row[0]) + timedelta(minutes=1) if row[0] else datetime.now(timezone.utc).replace(second=0, microsecond=0)
        plans = plan_failures(rng, fleet, t, 6)          # plan a fresh 6h of failures ahead
        write_truth(plans, args.seed, append=True)
        print(f"live from {t.isoformat()}  (ctrl-c to stop)")
        while True:
            n = tick(con, fleet, plans, t, rng, state)
            print(f"{t.isoformat()}  +{n} rows")
            t += timedelta(minutes=1)
            time.sleep(1 if args.fast else 60)


if __name__ == "__main__":
    main()
