# Server Fleet Telemetry Triage

An agentic triage pipeline for a simulated streaming-service server fleet. It
continuously reads streaming sensor data, detects failure patterns, triages them
by severity and likely root cause, and tags the affected time ranges for later
model training.

The sensors are server telemetry (CPU temperature, fan speed, power, memory,
outside air temperature), but the data shape — time-ordered numeric streams per
host plus host metadata — is the same as robot or industrial-equipment
telemetry. Swap the sensor names and the pipeline does not care.

## Status

| Phase | What | State |
|---|---|---|
| 1.1 | `generator.py` — fake fleet, physics, seeded failures, raw encodings | done |
| 1.2 | `collector.py` — parse raw formats into a clean table | done |
| 1.3 | `stream.py` — tick loop that collects new rows every interval | done |
| 2 | `detector.py` — detection rules (threshold done; slope, peer comparison, silence, impossible values, frozen values, thermal load next) | in progress |
| 3 | triage — label vocabulary, per-label rules, grouping, LLM-written tickets, tagging | not started |
| 4 | dashboard — fleet / per-datacenter / per-server views | not started |
| 5 | wrap-up — scoring against ground truth, demo, robot mapping | not started |
| 6 | fix feedback loop — plant a firmware-correlated cause, discover it, fix it, show before/after | bonus |

Detailed plan, decisions, and design notes: [`claude_code/PLAN.md`](claude_code/PLAN.md).

## Layout

```
raw_data/
  generator.py      fake sensors -> telemetry.db (raw_readings, hosts) + ground_truth.csv
  collector.py      raw_readings -> clean_readings (parsed values, host info, parse errors)
  stream.py         tick loop: runs the collector every N seconds
  detector.py       detection rules on clean_readings; prints evidence episodes
  ground_truth.csv  answer key for scoring (the detector never reads it)
  telemetry.db      SQLite, generated, not committed
reports/
  data_summary.md   data distributions, per-failure views, threshold sweeps (for choosing numbers)
learning/           line-by-line explanations of each script (Korean)
claude_code/        PLAN.md and working rules
```

## Quick start

Python 3.11+ (standard library only — `sqlite3`, `json`, `re`, `zoneinfo`).

```bash
cd raw_data
python generator.py backfill --hours 48 --seed 42     # 48 h of raw readings + ground_truth.csv
python collector.py                                    # raw -> clean_readings
python detector.py threshold cpu_temp 65 --minutes 10  # evidence: who was above 65 C for 10+ min
python detector.py threshold fan_rpm 2000 --below --minutes 10
```

Live mode, for watching the loop work:

```bash
python generator.py live --seed 42 --fast   # one simulated minute per real second
python stream.py --interval 5               # in a second terminal
```

To reproduce the exact seed-42 dataset described in PLAN.md, pass
`--start 2026-09-02T02:32:00+00:00` to `backfill`.

## The fleet

3 datacenters × 5 servers = 15 hosts, each with model, firmware (2.3.1 or
2.4.0), rack, slot, and a popularity factor. Load follows a streaming-service
schedule in each datacenter's local time (evening peak, Friday night highest,
weekends and US holidays differ), smoothed with a 60-minute moving average.

| dc | city | timezone | normal outside low / high |
|---|---|---|---|
| dc-east | Ashburn | America/New_York | 22 / 32 °C |
| dc-west | Sacramento | America/Los_Angeles | 15 / 33 °C |
| dc-hawaii | Honolulu | Pacific/Honolulu | 24 / 34 °C |

## Sensors and raw formats

The generator emits raw values only — no units, no tags. Each sensor has its own
collection path and format; the collector's job is to undo that.

| sensor | source | raw example | meaning |
|---|---|---|---|
| cpu_temp | i2c | `918` | raw / 16 = 57.4 °C |
| fan_rpm | i2c | `4730` | rpm as-is |
| power_draw | api | `{"psu": 1, "watts": 409.6, "status": "ok"}` | watts |
| mem_used | cli | `Mem:  total 256G  used 83G  free 173G` | used GB |
| outside_temp | api | `{"temp_c": 24.8, "provider": "weather-feed"}` | one per datacenter |

Storage is SQLite (`telemetry.db`):

- `raw_readings(ts_utc, host_id, sensor, source, raw)`
- `hosts(host_id, dc, region, city, tz, model, firmware, rack, slot)`
- `clean_readings(ts_utc, host_id, dc, city, sensor, raw, value, parse_error)` — one row
  per raw row. The collector only cleans; it never judges values. A parseable
  but impossible number (-1 °C) is written as-is; unreadable raw text is written
  with `value = NULL` and a fixed `parse_error` string so repeats can be counted.

## Failures

Six failure types are planted per run, at seeded-random times weighted toward
busy hours, and written to `ground_truth.csv`:

| failure | what the sensors show | scope |
|---|---|---|
| ambient_high | outside temp ramps to ~46 °C over 30 h; every server in the datacenter warms together | one dc, 2–4 h |
| cooling_fail | fan_rpm drops first (~40 min), temperature follows, then throttles at 75 °C | one server |
| power_outage | all sensors in the datacenter stop; return cool with memory reset | one dc, 8–25 min |
| overload | load pinned at 100%; power and temperature high, memory creeps up | one server |
| sensor_fault | one sensor frozen or returning -1; the host's other sensors are fine | one sensor |
| server_stop | all sensors from one server stop with no warning | one server |

Things the detector must **not** fire on: throttling (protective behaviour),
a Friday-night load spike on a popular server, a sensor reading -1 or 0 (bad
sensor, not bad server), and a server_stop shortly before a power_outage in the
same datacenter (two events, not one).

## Detection principles

- The detector never reads `generator.py`'s formulas or `ground_truth.csv`.
  Thresholds come from looking at the clean data (`reports/data_summary.md`).
- Detection produces evidence only — what is unusual, where, since when, by how
  much. Naming the failure is the triage step.
- Scoring against the ground truth (found N of 6, false alarms, detection delay)
  is part of the detection phase, and the precision/recall table will sit at the
  top of this README.

## Mapping to robot fleets

| robots | this project |
|---|---|
| fleet of robots at sites | 15 servers in 3 datacenters |
| motor temperature, current, battery, IMU | cpu_temp, power_draw, mem_used, fan_rpm |
| one robot's motor or cooling fault | cooling_fail — one server |
| site environment (heat, slope, mud) | ambient_high — whole datacenter |
| robot slows itself when overheating | throttling — not a failure |
| firmware version as a root-cause branch | firmware 2.3.1 vs 2.4.0 in host info |
| sample faster when something looks off | adaptive sampling interval |
| recurring failure patterns | grouping by label + host/dc + window |
| triage by severity and root cause | LLM-written ticket with numeric evidence |
| tag data for future training | labelled time-range file |

## How this is built

Design and every decision (schemas, thresholds, rules) are made by the author;
the code is typed with Claude Code and explained line by line before moving on.
Those explanations live in `learning/`.
