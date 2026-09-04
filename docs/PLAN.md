# Server Fleet Telemetry Triage — Project Plan

Agentic dashboard for a fake streaming-service server fleet. It continuously
queries streaming sensor data, detects failure patterns, triages them by
severity and likely root cause, and tags the data for later training.

Built as prep for the Gritt AI practicum interview. Their project is the
same thing on construction-robot sensor/log data; this one uses server
telemetry because the data shape is the same (time-ordered numeric streams
per host + host metadata) and it could be designed with input from a
hardware engineer. See "Mapping to Gritt" at the bottom.

## Working rule

- Aeri designs and decides. Claude types the code.
- Aeri must be able to explain every line before moving on. If she can't,
  stop and explain that part before doing anything else.
- Do not skip ahead or reorder tasks. If there's a concern, say why and
  let her decide.
- Explain as if coding knowledge is zero. Always include an example.
  When showing output or data, show the real full thing, no "...".
- Syntax and tool questions (how to write X, what function does Y) get a
  direct answer. Design and logic questions get a nudge, not the answer.
- Units: Celsius, metric.

## Status

- [x] Phase 1.1 — generator.py written and tested (48h backfill, seed 42,
      181,036 raw rows, 6 failures). Regenerated 2026-09-03 after weather /
      timing fixes: 180,984 raw rows, new seed-42 schedule below.
- [x] Phase 1.2 — collector.py written and tested (clean_readings: ts_utc,
      host_id, dc, city, sensor, raw, value, parse_error; 181,036 rows,
      0 parse errors; re-run adds 0 rows). Explained line by line ->
      learning/collector.md
- [x] Phase 1.3 — stream.py tick loop (collect only for now; detector and
      dashboard plug into tick() later). Tested against generator live
      --fast: 315 rows / 5 s tick, 0 parse errors -> learning/stream.md
- [ ] Phase 2 — detection
- [ ] Phase 3 — triage
- [ ] Phase 4 — dashboard
- [ ] Phase 5 — README, demo, robot mapping

## Fleet

3 datacenters x 5 servers = 15 hosts. Host info lives in the `hosts` table,
not on each reading.

| dc        | region    | city       | timezone            | outside low / high (normal) |
|-----------|-----------|------------|---------------------|-----------------------------|
| dc-east   | us-east-1 | Ashburn    | America/New_York    | 22 / 32 C                   |
| dc-west   | us-west-2 | Sacramento | America/Los_Angeles | 15 / 33 C                   |
| dc-hawaii | us-hawaii | Honolulu   | Pacific/Honolulu    | 24 / 34 C                   |

Heat wave (ambient_high): low +7, high +13 (Sacramento: 22 / 46). Ramps in
linearly over 30 h before the planned window, holds, fades over 12 h after.

Per host: host_id (e.g. dc-east-s3), model, firmware (2.3.1 or 2.4.0),
rack, slot, popularity (0.7-1.0, some servers get more traffic).

## Sensors and raw formats

The generator emits RAW values only — no tags, no units. Each sensor has its
own collection method and format. The collector's job is to undo this.

| sensor       | source | raw example                                   | interpretation        |
|--------------|--------|-----------------------------------------------|-----------------------|
| cpu_temp     | i2c    | `918`                                         | raw / 16 = 57.4 C     |
| fan_rpm      | i2c    | `4730`                                        | as-is                 |
| power_draw   | api    | `{"psu": 1, "watts": 409.6, "status": "ok"}`  | parse JSON, watts     |
| mem_used     | cli    | `Mem:  total 256G  used 83G  free 173G`       | parse text, used GB   |
| outside_temp | api    | `{"temp_c": 24.8, "provider": "weather-feed"}`| one per dc, host_id = `<dc>-weather` |

Sampling: every 1 minute. Later: detector narrows the interval when
something looks off (adaptive sampling).

Storage: SQLite `telemetry.db`
- `raw_readings(ts_utc, host_id, sensor, source, raw)`
- `hosts(host_id, dc, region, city, tz, model, firmware, rack, slot)`
- `clean_readings(ts_utc, host_id, dc, city, sensor, raw, value, parse_error)`
  — written by collector.py, one row per raw row. value NULL + parse_error
  text when raw can't be read.

## Load pattern — entertainment streaming, in LOCAL time per datacenter

- Weekday: morning bump 9-11 (50%), evening peak 16-23 (85%), Friday after
  20:00 = 95%, late night 23-02 = 40%, otherwise 15%
- Weekend and US holidays: 13-24 = 80%, 9-13 = 50%, otherwise 20%
- US holidays: Jan 1, Jul 4, Sep 7 (Labor Day 2026), Nov 26, Dec 25
- Edges are smoothed: load = 60-minute moving average of the step schedule
  (a 15% -> 85% change at 16:00 ramps from 15:30 to 16:30). Fixed 2026-09-03;
  before that the smoothing only worked inside the hour and every schedule
  change was a 6-11 C jump in one minute.

## Physics (made-up formulas — first thing to change if Nigel says the shape is wrong)

- normal cpu_temp range 40-65 C while working
- temp = 40 + load*22 + ambient_push - (fan_health - 1)*30 + noise
- ambient_push = max(0, outside - 30) * 0.6 (outside only matters above ~30 C)
- throttling above 75 C: temp pins at ~75, power drops 30%. NOT a failure.
- fan_rpm rises with load and with temp above 55
- memory follows load slowly (60 + load*100 GB target)

## Weather

Outside temp per dc: daily cycle (warmest ~15:00, coolest ~03:00) + noise.
Real basis: data centers are climate-controlled, so weather barely shows
normally, but cooling has a design envelope. In heat waves the inside/outside
gap shrinks, fans and chillers work harder, and facilities have gone down
(Google/Oracle London July 2022 at 40 C, Twitter Sacramento Sept 2022 at
47 C). So ambient_high is a whole-datacenter event driven by outside temp.

dc-west moved to Sacramento (2026-09-03) because Hillsboro at 22 C base
never reached the 30 C where ambient_push starts, so ambient_high was
invisible on the servers.

Real Sacramento numbers to model against:
- normal early September: high ~33 C, overnight low ~15 C
- Sept 2022 heat wave: 46.7 C on Sept 6 (all-time record since 1877,
  previous 43.3 C); seven straight days above 38 C; several days 43 C+
- the dangerous part was nights not cooling: overnight low 22 C vs the
  usual 15 C. Cooling never gets a chance to catch up, so each day starts
  hotter. This is what the integral / thermal-load detector is for.
- rate of change: ~2 C per DAY across the build-up; within a day roughly
  22 C at dawn to 46 C mid-afternoon = ~2.7 C/hour = ~0.045 C/min

So the heat wave must RAMP, not step. The current code adds +18 C in one
minute (25.7 -> 43.1), which rate-of-change would catch far too easily.
Fit the heat wave into 48h as "day 3-4 of an ongoing heat wave" rather
than a sudden onset.

## Failures — seeded random, written to ground_truth.csv

The detector never reads ground_truth.csv. It's the answer key for scoring
(found N of 6, M false alarms).

| failure      | what sensors show                                              | scope          | weight              |
|--------------|----------------------------------------------------------------|----------------|---------------------|
| ambient_high | outside ramps to ~46 C, all servers in dc warm up together      | one dc, 2-4h   | east .7 west .2 hi .1 |
| cooling_fail | fan_rpm drops first (~40 min), temp climbs after, throttles     | one server     | hawaii .5, others .25 |
| power_outage | all sensors in dc stop, return cool with memory reset           | one dc, 8-25m  | uniform             |
| overload     | load pinned 100%, power+temp high, memory creeps up             | one server     | uniform             |
| sensor_fault | one sensor frozen or returns -1; other sensors on host fine     | one sensor     | uniform             |
| server_stop  | all sensors from one server stop; no warning before             | one server     | uniform             |

Failure timing (2026-09-03): times are random within the window, which in
seed 42 put all failures in the small hours when load is ~15%. Nothing
reached 75 C, so throttling never happened and there is no data to test the
"throttling is not a failure" trap. Fix: weight failure start times toward
high-load hours (servers do fail more when busy), rather than changing the
physics. Seed 42 results will change.

Traps the detector must NOT fire on:
- throttling (temp pins ~75, power drops) — protective behavior
- Friday-night load spike to ~68 C on a popular server — load explains it
- sensor value -1 or 0 — bad sensor, not bad server
- server_stop shortly before power_outage in the same dc — two events, not
  one (was the case in the original seed 42; not in the current schedule)

Seed 42 result (after 2026-09-03 timing fix; UTC, local in brackets):
```
overload       dc-west-s1         09-02 22:57 -> 00:39   (Wed 15:57-17:39 Sacramento)
cooling_fail   dc-east-s1         09-02 23:02 -> 01:01   (Wed 19:02-21:01 Ashburn)  throttles 75 C for 76 min
server_stop    dc-west-s5         09-03 05:25 -> 06:14   (Wed 22:25-23:14 Sacramento)
power_outage   dc-hawaii          09-03 11:08 -> 11:21   (Thu 01:08-01:21 Honolulu)
ambient_high   dc-west            09-03 22:14 -> 02:03   (Thu 15:14-19:03 Sacramento)  outside peaks 47.2 C
sensor_fault   dc-east-s5/fan_rpm 09-04 00:09 -> 00:33   (Thu 20:09-20:33 Ashburn)
```

## Tasks

Bold = Aeri decides. Plain = Claude types, Aeri reads and explains back.

### Phase 1 — Fake data
1. generator.py — DONE. Modes: `backfill --hours 48 --seed 42`,
   `live --seed 42 [--fast]` (1 sim-minute per real minute, or per second)
2. collector.py — read raw_readings, interpret each format, join host info,
   write one clean row per reading. **Aeri: clean table schema (derive it
   from the 3 questions the detector will ask the table).**
   Decisions made 2026-09-03:
   - Collector only cleans. It does NOT judge values. A parseable number is
     written as-is even if it's physically impossible (-1 C, 0 GB). Judging
     is the detector's job.
   - Unreadable raw (garbage, truncated JSON, empty) -> still write the row,
     value empty, plus a `parse_error` note saying why. Never drop silently.
   - Repeated parse errors from the same host/sensor are themselves a
     pattern: triage should be able to flag them to engineering (collector
     bug) or field/hardware (sensor bug). Keep the note text consistent so
     grouping can count them.
   - Frozen values and silence are not the collector's business (needs
     history / needs absence). Both belong to Phase 2.
   - Generator quirk to fix later: mem_used -1 becomes `used 0G` because of
     max(0, value). Should emit an obviously bad value instead.
3. Stream loop — detection queries the DB for rows newer than last check,
   runs every tick, refreshes dashboard.

### Phase 2 — Detection (detector.py, separate from collector.py)

Principles (added 2026-09-03):
- The detector must NOT reuse generator.py's formulas or planted numbers.
  Otherwise it's writing the exam and memorizing the answers. Thresholds
  come from LOOKING AT THE CLEAN DATA (rolling baselines, peer medians,
  slopes), not from reading generator.py. **Aeri sets every number.**
- Detection = evidence only. It outputs "what is unusual, where, since
  when, how much". Naming the failure is Phase 3.
- Evaluation is part of this phase: score against ground_truth.csv
  (found N of 6, false alarms, detection delay). Change thresholds, watch
  precision/recall move. That table goes at the top of the README.

Order (easy -> hard, and by interview value):
4. Threshold — value above/below a fixed line for N minutes
5. Rate of change — slope per minute (catches "climbing fast" before the
   line is crossed)
6. Peer comparison — value minus median of same-dc peers. One server off
   = that server; all servers off = the site. This is the cooling_fail vs
   ambient_high split, and it maps 1:1 to robot fleets.
7. Silence — "no rows from host X for N minutes". Distinguish one host
   silent (server_stop) from a whole dc silent (power_outage). Needs the
   clean table to make "expected but missing" visible, so schema matters.
8. Impossible values — outside physical range (-1 C, 0 GB on a live
   server). Flag as sensor problem, not server problem.
9. Frozen values — identical readings K minutes in a row while peers vary.
   Sensor problem, not server problem.
10. Duration / integral (thermal load) — area above threshold over time;
    "how long and how much", for severity
11. CDF comparison — is this server's whole distribution shifted vs peers.
    Lowest priority; do it if time allows, ties to the stats class.

### Phase 3 — Triage
12. Label vocabulary — one-line meaning per label. Start: cooling_fail,
   ambient_high, power_outage, overload, sensor_fault, server_stop.
13. Per-label rules — when it fires AND when it must not fire. **Aeri writes
    these in plain English first; code after.**
14. Grouping — same label + same server (or dc) within a window = one
    pattern; count per week. Include firmware as a grouping key.
15. LLM step — takes grouped evidence, writes the ticket: severity, likely
    cause (hardware vs environment vs software), evidence with timestamps
    and counts. Numbers and stats come from code; LLM writes the summary.
16. Tagging — save labeled time ranges to a file.

### Phase 4 — Dashboard
17. Three views: fleet (15 servers ranked by severity), per-datacenter
    (5 servers on one chart, catches ambient_high), per-server (temp, power,
    memory, fan over time with incidents marked and tagged ranges visible).
    Evidence table (label / host / why it applies), timeline. Show UTC and
    local time.
18. Loop wrapper — runs every tick, refreshes.

### Phase 5 — Wrap-up
19. README, demo GIF, scoring against ground truth, "mapping to robots"
    section, and "what I'd add on real infra" (ticket routing, fix tracking,
    alert rate limiting, unattended operation).

## Reference: Roboto's triage agent (copied structure, not code)

- Label vocabulary: fixed list of labels the agent may apply, each with a
  one-line description. Agent can only pick from this list.
- Per-label skill: which topic/field, thresholds, log signatures, AND an
  explicit "false positives — do NOT fire when" section.
- Agent task order: dataset overview -> triage each label -> submit
  decisions -> timeline milestones -> summary report.
- Output: summary report, event timeline with links to the signal, and a
  label table with "why it applies" written as numbers, timestamps, and
  ratios (e.g. "228/366 samples (62%) above threshold from t=487s").

## Mapping to Gritt

| Gritt (robots)                              | This project (servers)                        |
|---------------------------------------------|-----------------------------------------------|
| fleet of robots at sites                    | 15 servers in 3 datacenters                   |
| motor_temp, motor_current, battery, IMU     | cpu_temp, power_draw, mem_used, fan_rpm       |
| one robot's motor/cooling fault             | cooling_fail — one server only                |
| site environment (heat, slope, mud)         | ambient_high — whole datacenter               |
| robot slows itself when overheating         | throttling — not a failure                    |
| firmware version as root-cause branch       | firmware 2.3.1 vs 2.4.0 in host info          |
| sample faster when something's off          | adaptive sampling interval                    |
| continuously queries streaming data         | DB polling loop, every tick                   |
| recurring failure patterns                  | grouping by label + host/dc + window          |
| triage by severity and likely root cause    | LLM ticket with evidence                      |
| tags data for future model training         | labeled time ranges file                      |
| feedback loop to engineering teams          | not built — README "what I'd add"             |

Interview line: "Built on server telemetry, but swap the sensor names and
it's robot telemetry — the pipeline doesn't care."

### Phase 6 — Fix feedback loop (bonus, only after 1-5 work)

Close the loop Gritt describes: ticket -> engineer fixes -> fewer repeats.

- Plant a real cause in the generator: cooling_fail happens more often on
  firmware 2.3.1 than 2.4.0. Detector/triage must DISCOVER this from the
  data ("6 incidents, all on 2.3.1, zero on 2.4.0"), not be told.
- "Apply the fix" = upgrade those hosts to 2.4.0 in the fleet config, then
  generate the next period.
- Dashboard shows before/after:
    pattern: cooling_fail (dc-east)
      before fix   Sep 1-3   6 incidents
      fix applied  Sep 4     firmware 2.3.1 -> 2.4.0
      after fix    Sep 5-7   1 incident
- Trap to avoid: do not "fix" by turning the failure off in generator
  settings. That proves nothing. The reduction has to follow from a cause
  the triage actually identified.
