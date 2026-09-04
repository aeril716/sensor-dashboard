# Data summary report — seed 42, 48 h

Generated 2026-09-03 on the data regenerated after the load-step fix. Source: `data/telemetry.db` → `clean_readings`. This report is for a human choosing thresholds, so it consults ground_truth.csv (the detector never does).

## 1. Overview

- Period: `2026-09-02T02:32:00+00:00` ~ `2026-09-04T02:31:00+00:00` (UTC), 2,880 minutes
- Rows: 180,984 (0 parse errors). Expected 63 rows per minute (15 servers × 4 sensors + 3 weather) → 181,440; the 456 missing rows are silence (server_stop, power_outage)
- Local time: Ashburn UTC-4, Sacramento UTC-7, Honolulu UTC-10

Answer key (ground_truth.csv):

| failure | scope | UTC | local |
|---|---|---|---|
| overload | dc-west-s1 | 09-02 22:57 → 09-03 00:39 | Wed 15:57 → Wed 17:39 (dc-west) |
| cooling_fail | dc-east-s1 | 09-02 23:02 → 09-03 01:01 | Wed 19:02 → Wed 21:01 (dc-east) |
| server_stop | dc-west-s5 | 09-03 05:25 → 09-03 06:14 | Wed 22:25 → Wed 23:14 (dc-west) |
| power_outage | dc-hawaii | 09-03 11:08 → 09-03 11:21 | Thu 01:08 → Thu 01:21 (dc-hawaii) |
| ambient_high | dc-west | 09-03 22:14 → 09-04 02:03 | Thu 15:14 → Thu 19:03 (dc-west) |
| sensor_fault | dc-east-s5/fan_rpm | 09-04 00:09 → 09-04 00:33 | Thu 20:09 → Thu 20:33 (dc-east) |

## 2. Distribution per sensor (all 48 h, failures included)

| sensor | unit | n | min | p5 | p25 | median | p75 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|---|---|
| cpu_temp | °C | 43,086 | 40.5 | 42.2 | 43.4 | 46.8 | 53.8 | 58.6 | 64.9 | 76.2 |
| fan_rpm | rpm | 43,086 | 1690.0 | 2735.0 | 2829.0 | 3158.0 | 4013.0 | 4712.0 | 5193.0 | 6071.0 |
| power_draw | W | 43,086 | 186.3 | 207.4 | 219.5 | 259.9 | 360.8 | 414.6 | 433.2 | 496.9 |
| mem_used | GB | 43,086 | 41.0 | 71.0 | 73.0 | 86.0 | 120.0 | 137.0 | 144.0 | 177.0 |
| outside_temp | °C | 8,640 | 14.0 | 18.6 | 24.0 | 27.8 | 31.9 | 40.3 | 45.5 | 47.2 |

### 2a. Per datacenter

| dc | sensor | min | median | p95 | p99 | max |
|---|---|---|---|---|---|---|
| dc-east | cpu_temp | 40.5 | 45.6 | 57.5 | 59.0 | 76.2 |
| dc-east | fan_rpm | 1690.0 | 3117.0 | 4645.0 | 4756.0 | 4989.0 |
| dc-east | power_draw | 186.3 | 255.5 | 414.6 | 424.8 | 442.7 |
| dc-east | mem_used | 67.0 | 86.0 | 138.0 | 140.0 | 142.0 |
| dc-east | outside_temp | 21.0 | 27.1 | 32.1 | 32.5 | 33.3 |
| dc-west | cpu_temp | 40.6 | 48.5 | 63.2 | 65.9 | 69.1 |
| dc-west | fan_rpm | 2614.0 | 3215.0 | 5033.0 | 5562.0 | 6071.0 |
| dc-west | power_draw | 189.2 | 265.8 | 424.8 | 444.9 | 496.9 |
| dc-west | mem_used | 43.0 | 88.0 | 141.0 | 145.0 | 177.0 |
| dc-west | outside_temp | 14.0 | 26.7 | 45.1 | 46.1 | 47.2 |
| dc-hawaii | cpu_temp | 40.6 | 46.4 | 57.8 | 58.9 | 60.2 |
| dc-hawaii | fan_rpm | 2603.0 | 3175.0 | 4587.0 | 4712.0 | 4988.0 |
| dc-hawaii | power_draw | 188.0 | 261.0 | 408.3 | 418.2 | 433.8 |
| dc-hawaii | mem_used | 41.0 | 84.0 | 135.0 | 137.0 | 140.0 |
| dc-hawaii | outside_temp | 22.8 | 29.0 | 34.0 | 34.4 | 34.9 |

## 3. Normal periods only (failure windows and their hosts excluded)

A threshold above these values never fires in normal time. The heat-wave ramp (the 30 h *before* the ambient_high window) and the evening peaks count as normal.

| sensor | n(normal) | median | p95 | p99 | max | where the max occurred |
|---|---|---|---|---|---|---|
| cpu_temp | 41,696 | 46.6 | 57.9 | 59.5 | 65.0 | dc-west-s4 09-04 02:03 UTC |
| fan_rpm | 41,696 | 3120.0 | 4646.0 | 4894.0 | 5463.0 | dc-west-s4 09-04 02:13 UTC |
| power_draw | 41,696 | 254.3 | 412.7 | 429.5 | 457.9 | dc-west-s4 09-03 00:11 UTC |
| mem_used | 41,696 | 84.0 | 137.0 | 143.0 | 174.0 | dc-west-s1 09-03 00:39 UTC |

Lowest normal fan_rpm: 2550.0 rpm (dc-east-s5 09-02 19:25 UTC). cooling_fail is a *falling* fan, so it needs a lower line.

### 3a. Normal periods, by dc × local time of day (median, max)

| dc | period (local) | cpu med | cpu max | fan med | fan max | power med | power max |
|---|---|---|---|---|---|---|---|
| dc-east | night 02-09 | 42.8 | 47.1 | 2813 | 3328 | 217.2 | 275.8 |
| dc-east | morning 09-11 | 47.9 | 51.5 | 3405 | 3805 | 287.9 | 342.6 |
| dc-east | day 11-16 | 43.7 | 51.5 | 2817 | 3677 | 218.3 | 323.7 |
| dc-east | evening 16-23 | 54.1 | 59.8 | 4075 | 4989 | 369.4 | 442.7 |
| dc-east | late 23-02 | 47.0 | 53.9 | 3292 | 4004 | 275.2 | 367.7 |
| dc-west | night 02-09 | 43.0 | 47.9 | 2842 | 3376 | 221.1 | 281.2 |
| dc-west | morning 09-11 | 50.2 | 55.9 | 3520 | 3853 | 302.5 | 352.9 |
| dc-west | day 11-16 | 47.8 | 54.3 | 2847 | 3726 | 221.6 | 322.8 |
| dc-west | evening 16-23 | 56.9 | 65.0 | 4502 | 5463 | 400.3 | 457.9 |
| dc-west | late 23-02 | 47.8 | 54.1 | 3379 | 4082 | 285.5 | 368.7 |
| dc-hawaii | night 02-09 | 42.9 | 47.4 | 2824 | 3302 | 218.9 | 287.1 |
| dc-hawaii | morning 09-11 | 48.9 | 52.2 | 3482 | 3761 | 297.2 | 335.6 |
| dc-hawaii | day 11-16 | 45.0 | 52.2 | 2833 | 3658 | 219.8 | 319.6 |
| dc-hawaii | evening 16-23 | 56.3 | 60.2 | 4379 | 4988 | 392.5 | 433.8 |
| dc-hawaii | late 23-02 | 47.4 | 52.9 | 3344 | 4006 | 281.3 | 353.1 |

## 4. Each failure — summary + individual values

### 4.1 overload — dc-west-s1 — 09-02 22:57 → 09-03 00:39 UTC (Wed 15:57 → Wed 17:39 local)

**Summary (medians)**

| sensor | target: 1 h before | target: during | target: 1 h after | same-dc peers: during | target: max/min during |
|---|---|---|---|---|---|
| cpu_temp | 46.8 | 65.2 | 59.3 | 58.5 | 67.0 / 63.2 |
| fan_rpm | 2888.0 | 5804.0 | 4761.0 | 4541.0 | 6071.0 / 5621.0 |
| power_draw | 227.7 | 480.7 | 410.3 | 391.6 | 496.9 / 459.0 |
| mem_used | 74.0 | 170.0 | 145.0 | 126.0 | 177.0 / 90.0 |

**Individual values**

Every 5 min: the target server's 4 sensors + peer medians (cpu, fan), from 15 min before to 15 min after (← = answer-key window).

| ts_utc | cpu_temp | fan_rpm | power_draw | mem_used | peer cpu med | peer fan med |
|---|---|---|---|---|---|---|
| 09-02 22:42 | 49.7 | 3228 | 248.1 | 78 | 49.3 | 3084 |
| 09-02 22:47 | 51.7 | 3135 | 276.0 | 80 | 50.6 | 3333 |
| 09-02 22:52 | 50.9 | 3442 | 301.3 | 84 | 51.0 | 3455 |
| 09-02 22:57 ← | 64.2 | 5655 | 496.9 | 90 | 52.5 | 3508 |
| 09-02 23:02 ← | 65.6 | 5769 | 481.2 | 110 | 54.2 | 3635 |
| 09-02 23:07 ← | 66.0 | 5976 | 475.8 | 124 | 55.6 | 3882 |
| 09-02 23:12 ← | 64.9 | 5806 | 465.3 | 137 | 56.1 | 3965 |
| 09-02 23:17 ← | 65.1 | 5825 | 490.4 | 143 | 56.6 | 4153 |
| 09-02 23:22 ← | 65.4 | 5791 | 487.5 | 151 | 58.1 | 4481 |
| 09-02 23:27 ← | 64.4 | 5783 | 493.8 | 157 | 58.2 | 4478 |
| 09-02 23:32 ← | 65.2 | 5873 | 481.6 | 163 | 60.6 | 4759 |
| 09-02 23:37 ← | 65.6 | 5780 | 485.6 | 165 | 60.2 | 4766 |
| 09-02 23:42 ← | 64.6 | 5814 | 477.0 | 166 | 59.2 | 4828 |
| 09-02 23:47 ← | 65.6 | 5870 | 481.7 | 170 | 60.3 | 4676 |
| 09-02 23:52 ← | 64.8 | 5835 | 490.7 | 172 | 59.6 | 4772 |
| 09-02 23:57 ← | 66.0 | 5936 | 478.2 | 174 | 60.4 | 4773 |
| 09-03 00:02 ← | 66.1 | 5767 | 485.6 | 173 | 60.4 | 4790 |
| 09-03 00:07 ← | 64.8 | 5825 | 465.3 | 174 | 59.8 | 4796 |
| 09-03 00:12 ← | 64.8 | 5723 | 470.1 | 174 | 58.9 | 4727 |
| 09-03 00:17 ← | 64.0 | 5707 | 481.8 | 173 | 58.7 | 4711 |
| 09-03 00:22 ← | 64.1 | 5822 | 472.1 | 176 | 59.1 | 4749 |
| 09-03 00:27 ← | 64.4 | 5659 | 486.1 | 177 | 59.5 | 4735 |
| 09-03 00:32 ← | 64.2 | 5745 | 474.0 | 177 | 58.7 | 4683 |
| 09-03 00:37 ← | 64.6 | 5686 | 480.7 | 176 | 59.1 | 4719 |
| 09-03 00:42 | 60.6 | 4909 | 412.3 | 169 | 60.2 | 4785 |
| 09-03 00:47 | 59.5 | 4771 | 403.7 | 162 | 58.7 | 4621 |
| 09-03 00:52 | 60.2 | 4854 | 408.2 | 157 | 58.3 | 4604 |

### 4.2 cooling_fail — dc-east-s1 — 09-02 23:02 → 09-03 01:01 UTC (Wed 19:02 → Wed 21:01 local)

**Summary (medians)**

| sensor | target: 1 h before | target: during | target: 1 h after | same-dc peers: during | target: max/min during |
|---|---|---|---|---|---|
| cpu_temp | 57.4 | 74.8 | 57.3 | 53.8 | 76.2 / 57.1 |
| fan_rpm | 4646.0 | 1850.0 | 4641.0 | 4057.0 | 4617.0 / 1690.0 |
| power_draw | 418.2 | 294.4 | 412.4 | 367.1 | 431.0 / 278.6 |
| mem_used | 138.0 | 138.0 | 138.0 | 122.0 | 141.0 / 136.0 |

**Individual values**

Every 5 min: the target server's 4 sensors + peer medians (cpu, fan), from 15 min before to 15 min after (← = answer-key window).

| ts_utc | cpu_temp | fan_rpm | power_draw | mem_used | peer cpu med | peer fan med |
|---|---|---|---|---|---|---|
| 09-02 22:47 | 57.5 | 4685 | 420.5 | 136 | 54.4 | 4083 |
| 09-02 22:52 | 57.4 | 4603 | 427.6 | 140 | 54.8 | 4033 |
| 09-02 22:57 | 56.0 | 4508 | 429.6 | 139 | 53.8 | 4235 |
| 09-02 23:02 ← | 57.1 | 4575 | 431.0 | 136 | 53.8 | 4060 |
| 09-02 23:07 ← | 58.1 | 4304 | 417.7 | 139 | 53.9 | 4089 |
| 09-02 23:12 ← | 61.4 | 4049 | 398.8 | 138 | 54.8 | 4100 |
| 09-02 23:17 ← | 65.6 | 4000 | 415.6 | 139 | 53.2 | 4072 |
| 09-02 23:22 ← | 67.9 | 3597 | 417.0 | 138 | 54.9 | 4122 |
| 09-02 23:27 ← | 70.9 | 3213 | 407.0 | 138 | 53.8 | 3974 |
| 09-02 23:32 ← | 72.5 | 2785 | 415.9 | 138 | 54.4 | 4093 |
| 09-02 23:37 ← | 75.6 | 2400 | 292.5 | 138 | 54.0 | 3993 |
| 09-02 23:42 ← | 75.6 | 1845 | 289.7 | 139 | 54.2 | 4134 |
| 09-02 23:47 ← | 75.1 | 1809 | 292.0 | 137 | 55.2 | 4044 |
| 09-02 23:52 ← | 74.5 | 1742 | 299.5 | 138 | 54.2 | 4118 |
| 09-02 23:57 ← | 75.8 | 1814 | 298.8 | 138 | 53.4 | 4079 |
| 09-03 00:02 ← | 74.9 | 1748 | 297.2 | 138 | 53.9 | 4115 |
| 09-03 00:07 ← | 74.1 | 1866 | 283.3 | 139 | 54.8 | 4018 |
| 09-03 00:12 ← | 74.1 | 1774 | 285.7 | 138 | 54.4 | 4120 |
| 09-03 00:17 ← | 74.8 | 1834 | 279.6 | 138 | 53.9 | 4086 |
| 09-03 00:22 ← | 75.5 | 1718 | 294.6 | 139 | 53.2 | 4106 |
| 09-03 00:27 ← | 75.1 | 1877 | 286.6 | 138 | 53.9 | 4109 |
| 09-03 00:32 ← | 75.4 | 1887 | 293.8 | 138 | 54.8 | 4086 |
| 09-03 00:37 ← | 75.6 | 1781 | 285.3 | 138 | 54.4 | 4093 |
| 09-03 00:42 ← | 74.8 | 1847 | 293.0 | 138 | 54.1 | 4151 |
| 09-03 00:47 ← | 74.9 | 1871 | 301.4 | 139 | 54.0 | 4201 |
| 09-03 00:52 ← | 76.0 | 1859 | 292.4 | 140 | 54.2 | 4084 |
| 09-03 00:57 ← | 74.8 | 1800 | 299.4 | 138 | 54.0 | 4025 |
| 09-03 01:02 | 56.8 | 4555 | 413.9 | 139 | 54.4 | 4038 |
| 09-03 01:07 | 57.8 | 4680 | 417.2 | 138 | 53.3 | 4143 |
| 09-03 01:12 | 57.7 | 4620 | 431.5 | 139 | 53.9 | 4082 |

### 4.3 server_stop — dc-west-s5 — 09-03 05:25 → 09-03 06:14 UTC (Wed 22:25 → Wed 23:14 local)

Silence: there are no rows. Rows per minute (affected hosts vs one comparison host):

| ts_utc | dc-west-s5 | dc-west-s1 (comparison) |
|---|---|---|
| 09-03 05:22 | 4 | 4 |
| 09-03 05:23 | 4 | 4 |
| 09-03 05:24 | 4 | 4 |
| 09-03 05:25 | 0 | 4 |
| 09-03 05:26 | 0 | 4 |
| 09-03 05:27 | 0 | 4 |
| 09-03 05:28 | 0 | 4 |
| 09-03 05:29 | 0 | 4 |
| 09-03 05:30 | 0 | 4 |
| 09-03 05:31 | 0 | 4 |
| 09-03 05:32 | 0 | 4 |
| 09-03 05:33 | 0 | 4 |
| 09-03 05:34 | 0 | 4 |
| 09-03 05:35 | 0 | 4 |
| 09-03 05:36 | 0 | 4 |
| 09-03 05:37 | 0 | 4 |
| 09-03 05:38 | 0 | 4 |
| 09-03 05:39 | 0 | 4 |
| 09-03 05:40 | 0 | 4 |
| 09-03 05:41 | 0 | 4 |
| 09-03 05:42 | 0 | 4 |
| 09-03 05:43 | 0 | 4 |
| 09-03 05:44 | 0 | 4 |
| 09-03 05:45 | 0 | 4 |
| 09-03 05:46 | 0 | 4 |
| 09-03 05:47 | 0 | 4 |
| 09-03 05:48 | 0 | 4 |
| 09-03 05:49 | 0 | 4 |
| 09-03 05:50 | 0 | 4 |
| 09-03 05:51 | 0 | 4 |
| 09-03 05:52 | 0 | 4 |
| 09-03 05:53 | 0 | 4 |
| 09-03 05:54 | 0 | 4 |
| 09-03 05:55 | 0 | 4 |
| 09-03 05:56 | 0 | 4 |
| 09-03 05:57 | 0 | 4 |
| 09-03 05:58 | 0 | 4 |
| 09-03 05:59 | 0 | 4 |
| 09-03 06:00 | 0 | 4 |
| 09-03 06:01 | 0 | 4 |
| 09-03 06:02 | 0 | 4 |
| 09-03 06:03 | 0 | 4 |
| 09-03 06:04 | 0 | 4 |
| 09-03 06:05 | 0 | 4 |
| 09-03 06:06 | 0 | 4 |
| 09-03 06:07 | 0 | 4 |
| 09-03 06:08 | 0 | 4 |
| 09-03 06:09 | 0 | 4 |
| 09-03 06:10 | 0 | 4 |
| 09-03 06:11 | 0 | 4 |
| 09-03 06:12 | 0 | 4 |
| 09-03 06:13 | 0 | 4 |
| 09-03 06:14 | 4 | 4 |
| 09-03 06:15 | 4 | 4 |
| 09-03 06:16 | 4 | 4 |

### 4.4 power_outage — dc-hawaii — 09-03 11:08 → 09-03 11:21 UTC (Thu 01:08 → Thu 01:21 local)

Silence: there are no rows. Rows per minute (affected hosts vs one comparison host):

| ts_utc | dc-hawaii-s1 | dc-hawaii-s2 | dc-hawaii-s3 | dc-hawaii-s4 | dc-hawaii-s5 | dc-east-s1 (comparison) |
|---|---|---|---|---|---|---|
| 09-03 11:05 | 4 | 4 | 4 | 4 | 4 | 4 |
| 09-03 11:06 | 4 | 4 | 4 | 4 | 4 | 4 |
| 09-03 11:07 | 4 | 4 | 4 | 4 | 4 | 4 |
| 09-03 11:08 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:09 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:10 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:11 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:12 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:13 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:14 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:15 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:16 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:17 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:18 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:19 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:20 | 0 | 0 | 0 | 0 | 0 | 4 |
| 09-03 11:21 | 4 | 4 | 4 | 4 | 4 | 4 |
| 09-03 11:22 | 4 | 4 | 4 | 4 | 4 | 4 |
| 09-03 11:23 | 4 | 4 | 4 | 4 | 4 | 4 |

mem_used right after return (reset check) vs right before:

| host | last value before | first value after |
|---|---|---|
| dc-hawaii-s1 | 91.0 | 42.0 |
| dc-hawaii-s2 | 95.0 | 41.0 |
| dc-hawaii-s3 | 90.0 | 41.0 |
| dc-hawaii-s4 | 97.0 | 42.0 |
| dc-hawaii-s5 | 95.0 | 44.0 |

### 4.5 ambient_high — dc-west — 09-03 22:14 → 09-04 02:03 UTC (Thu 15:14 → Thu 19:03 local)

**Summary (medians)**

| sensor | target: 1 h before | target: during | target: 1 h after | other-dc servers: during | target: max/min during |
|---|---|---|---|---|---|
| cpu_temp | 52.4 | 63.3 | 61.9 | 52.1 | 69.1 / 50.8 |
| fan_rpm | 2828.0 | 4938.0 | 4921.0 | 3838.0 | 5723.0 / 2633.0 |
| power_draw | 219.3 | 392.8 | 403.9 | 340.2 | 458.4 / 195.1 |
| mem_used | 73.0 | 129.0 | 135.0 | 118.0 | 146.0 / 70.0 |
| outside_temp | 45.7 | 44.2 | 39.0 | — | 46.6 / 39.2 |

**Individual values**

Every 15 min: cpu_temp of each of the 5 dc-west servers + outside temp + other-dc medians, from 60 min before to 30 min after (← = answer-key window).

| ts_utc | local | outside | west-s1 | west-s2 | west-s3 | west-s4 | west-s5 | east med | hawaii med |
|---|---|---|---|---|---|---|---|---|---|
| 09-03 21:14 | 14:14 | 45.4 | 52.4 | 52.7 | 52.3 | 52.4 | 52.9 | 54.7 | 45.8 |
| 09-03 21:29 | 14:29 | 45.7 | 51.6 | 52.9 | 52.1 | 52.5 | 52.8 | 54.9 | 44.3 |
| 09-03 21:44 | 14:44 | 45.4 | 51.6 | 52.4 | 52.1 | 52.4 | 52.8 | 55.0 | 44.6 |
| 09-03 21:59 | 14:59 | 45.7 | 51.8 | 53.2 | 52.6 | 52.5 | 53.3 | 53.8 | 44.1 |
| 09-03 22:14 ← | 15:14 | 45.9 | 53.0 | 52.1 | 52.5 | 53.2 | 52.2 | 54.1 | 45.0 |
| 09-03 22:29 ← | 15:29 | 45.7 | 51.6 | 51.9 | 51.5 | 52.1 | 52.0 | 53.9 | 44.4 |
| 09-03 22:44 ← | 15:44 | 45.9 | 57.9 | 54.9 | 56.0 | 57.1 | 55.7 | 53.6 | 44.1 |
| 09-03 22:59 ← | 15:59 | 44.9 | 58.8 | 57.1 | 57.9 | 60.0 | 57.1 | 53.9 | 44.9 |
| 09-03 23:14 ← | 16:14 | 45.5 | 62.8 | 62.2 | 61.8 | 63.1 | 61.2 | 54.4 | 45.6 |
| 09-03 23:29 ← | 16:29 | 45.4 | 65.8 | 64.8 | 64.2 | 66.8 | 64.9 | 54.4 | 44.8 |
| 09-03 23:44 ← | 16:44 | 45.1 | 64.3 | 66.1 | 64.4 | 67.2 | 64.1 | 54.5 | 45.4 |
| 09-03 23:59 ← | 16:59 | 43.8 | 64.3 | 64.5 | 64.1 | 66.4 | 63.2 | 53.9 | 45.2 |
| 09-04 00:14 ← | 17:14 | 44.7 | 65.8 | 64.9 | 63.6 | 67.8 | 63.4 | 53.6 | 44.7 |
| 09-04 00:29 ← | 17:29 | 43.5 | 65.7 | 63.9 | 63.8 | 65.8 | 62.7 | 54.7 | 45.8 |
| 09-04 00:44 ← | 17:44 | 43.5 | 64.4 | 64.6 | 63.7 | 66.8 | 63.7 | 54.1 | 44.8 |
| 09-04 00:59 ← | 17:59 | 42.8 | 64.4 | 63.9 | 63.6 | 66.3 | 63.2 | 53.7 | 44.2 |
| 09-04 01:14 ← | 18:14 | 41.6 | 63.8 | 63.4 | 62.4 | 65.5 | 62.4 | 53.9 | 44.5 |
| 09-04 01:29 ← | 18:29 | 41.0 | 62.9 | 62.8 | 62.2 | 64.8 | 61.8 | 53.8 | 45.2 |
| 09-04 01:44 ← | 18:44 | 40.2 | 62.6 | 62.6 | 61.0 | 64.4 | 61.6 | 53.5 | 47.8 |
| 09-04 01:59 ← | 18:59 | 39.9 | 62.4 | 62.2 | 60.2 | 65.5 | 61.3 | 54.3 | 51.9 |
| 09-04 02:14 | 19:14 | 38.8 | 62.0 | 60.5 | 59.0 | 63.4 | 60.6 | 54.5 | 55.2 |
| 09-04 02:29 | 19:29 | 37.9 | 61.8 | 61.5 | 59.5 | 63.4 | 60.9 | 54.1 | 57.4 |

### 4.6 sensor_fault — dc-east-s5/fan_rpm — 09-04 00:09 → 09-04 00:33 UTC (Thu 20:09 → Thu 20:33 local)

Only dc-east-s5's fan_rpm is wrong; the host's other sensors and its peers are normal. Every minute, 3 min before to 3 min after (← = answer-key window):

| ts_utc | dc-east-s5 fan_rpm (raw) | dc-east-s5 cpu_temp | peer fan_rpm median |
|---|---|---|---|
| 09-04 00:06 | 4026 | 53.4 | 4618.0 |
| 09-04 00:07 | 4025 | 53.4 | 4683.0 |
| 09-04 00:08 | 4030 | 53.9 | 4581.0 |
| 09-04 00:09 ← | 3952 | 53.1 | 4615.0 |
| 09-04 00:10 ← | 3952 | 53.1 | 4503.0 |
| 09-04 00:11 ← | 3952 | 53.9 | 4558.0 |
| 09-04 00:12 ← | 3952 | 53.4 | 4666.0 |
| 09-04 00:13 ← | 3952 | 53.9 | 4524.0 |
| 09-04 00:14 ← | 3952 | 53.2 | 4580.0 |
| 09-04 00:15 ← | 3952 | 53.5 | 4634.0 |
| 09-04 00:16 ← | 3952 | 53.6 | 4735.0 |
| 09-04 00:17 ← | 3952 | 53.2 | 4554.0 |
| 09-04 00:18 ← | 3952 | 52.5 | 4533.0 |
| 09-04 00:19 ← | 3952 | 51.8 | 4486.0 |
| 09-04 00:20 ← | 3952 | 51.9 | 4523.0 |
| 09-04 00:21 ← | 3952 | 52.2 | 4610.0 |
| 09-04 00:22 ← | 3952 | 53.0 | 4655.0 |
| 09-04 00:23 ← | 3952 | 53.1 | 4594.0 |
| 09-04 00:24 ← | 3952 | 53.4 | 4686.0 |
| 09-04 00:25 ← | 3952 | 53.5 | 4638.0 |
| 09-04 00:26 ← | 3952 | 53.7 | 4474.0 |
| 09-04 00:27 ← | 3952 | 52.4 | 4600.0 |
| 09-04 00:28 ← | 3952 | 52.9 | 4560.0 |
| 09-04 00:29 ← | 3952 | 53.8 | 4653.0 |
| 09-04 00:30 ← | 3952 | 53.8 | 4560.0 |
| 09-04 00:31 ← | 3952 | 53.1 | 4570.0 |
| 09-04 00:32 ← | 3952 | 53.4 | 4571.0 |
| 09-04 00:33 | 4102 | 53.5 | 4540.0 |
| 09-04 00:34 | 4147 | 53.5 | 4532.0 |
| 09-04 00:35 | 3990 | 53.8 | 4592.0 |

## 5. Threshold candidates — inside an answer-key window (hit) / outside (false alarm)

An episode is a hit if it overlaps an answer-key window and its host is affected by that failure. Several episodes on the same failure all count as hits.

| rule | episodes | hit | false alarm | failures caught |
|---|---|---|---|---|
| cpu_temp > 58 for ≥ 5 min | 68 | 8 | 60 | ambient_high, cooling_fail, overload |
| cpu_temp > 58 for ≥ 10 min | 23 | 7 | 16 | ambient_high, cooling_fail, overload |
| cpu_temp > 58 for ≥ 20 min | 13 | 7 | 6 | ambient_high, cooling_fail, overload |
| cpu_temp > 60 for ≥ 5 min | 16 | 8 | 8 | ambient_high, cooling_fail, overload |
| cpu_temp > 60 for ≥ 10 min | 13 | 8 | 5 | ambient_high, cooling_fail, overload |
| cpu_temp > 60 for ≥ 20 min | 10 | 8 | 2 | ambient_high, cooling_fail, overload |
| cpu_temp > 62 for ≥ 5 min | 17 | 15 | 2 | ambient_high, cooling_fail, overload |
| cpu_temp > 62 for ≥ 10 min | 10 | 10 | 0 | ambient_high, cooling_fail, overload |
| cpu_temp > 62 for ≥ 20 min | 9 | 9 | 0 | ambient_high, cooling_fail, overload |
| cpu_temp > 65 for ≥ 5 min | 17 | 17 | 0 | ambient_high, cooling_fail, overload |
| cpu_temp > 65 for ≥ 10 min | 7 | 7 | 0 | ambient_high, cooling_fail, overload |
| cpu_temp > 65 for ≥ 20 min | 2 | 2 | 0 | ambient_high, cooling_fail |
| cpu_temp > 68 for ≥ 5 min | 1 | 1 | 0 | cooling_fail |
| cpu_temp > 68 for ≥ 10 min | 1 | 1 | 0 | cooling_fail |
| cpu_temp > 68 for ≥ 20 min | 1 | 1 | 0 | cooling_fail |
| cpu_temp > 70 for ≥ 5 min | 1 | 1 | 0 | cooling_fail |
| cpu_temp > 70 for ≥ 10 min | 1 | 1 | 0 | cooling_fail |
| cpu_temp > 70 for ≥ 20 min | 1 | 1 | 0 | cooling_fail |
| fan_rpm < 2600 for ≥ 5 min | 1 | 1 | 0 | cooling_fail |
| fan_rpm < 2600 for ≥ 10 min | 1 | 1 | 0 | cooling_fail |
| fan_rpm < 2500 for ≥ 5 min | 1 | 1 | 0 | cooling_fail |
| fan_rpm < 2500 for ≥ 10 min | 1 | 1 | 0 | cooling_fail |
| fan_rpm < 2200 for ≥ 5 min | 1 | 1 | 0 | cooling_fail |
| fan_rpm < 2200 for ≥ 10 min | 1 | 1 | 0 | cooling_fail |
| fan_rpm < 2000 for ≥ 5 min | 1 | 1 | 0 | cooling_fail |
| fan_rpm < 2000 for ≥ 10 min | 1 | 1 | 0 | cooling_fail |
| fan_rpm < 1500 for ≥ 5 min | 0 | 0 | 0 | — |
| fan_rpm < 1500 for ≥ 10 min | 0 | 0 | 0 | — |
| power_draw > 400 for ≥ 10 min | 94 | 9 | 85 | ambient_high, cooling_fail, overload |
| power_draw > 420 for ≥ 10 min | 26 | 8 | 18 | ambient_high, overload |
| power_draw > 450 for ≥ 10 min | 1 | 1 | 0 | overload |
| power_draw > 480 for ≥ 10 min | 0 | 0 | 0 | — |
| mem_used > 130 for ≥ 10 min | 23 | 5 | 18 | ambient_high, cooling_fail, overload |
| mem_used > 140 for ≥ 10 min | 4 | 2 | 2 | ambient_high, overload |
| mem_used > 150 for ≥ 10 min | 1 | 1 | 0 | overload |
| mem_used > 160 for ≥ 10 min | 1 | 1 | 0 | overload |

What the false alarms are (for cpu_temp > 60 for ≥ 10 min):

| host | start | end | min | peak | verdict |
|---|---|---|---|---|---|
| dc-west-s1 | 09-02 22:57 | 09-03 00:39 | 103 | 67.0 | hit |
| dc-east-s1 | 09-02 23:08 | 09-03 01:00 | 113 | 76.2 | hit |
| dc-west-s4 | 09-02 23:25 | 09-03 00:27 | 63 | 62.8 | dc-west the evening before: peak load + heat-wave ramp (outside ~36 °C) |
| dc-west-s4 | 09-03 00:29 | 09-03 00:45 | 17 | 61.7 | dc-west the evening before: peak load + heat-wave ramp (outside ~36 °C) |
| dc-west-s4 | 09-03 00:52 | 09-03 01:13 | 22 | 61.8 | dc-west the evening before: peak load + heat-wave ramp (outside ~36 °C) |
| dc-west-s4 | 09-03 23:00 | 09-04 02:31 | 212 | 69.1 | hit |
| dc-west-s1 | 09-03 23:01 | 09-04 02:31 | 211 | 67.3 | hit |
| dc-west-s2 | 09-03 23:05 | 09-04 02:31 | 207 | 66.4 | hit |
| dc-west-s3 | 09-03 23:11 | 09-04 02:13 | 183 | 65.5 | hit |
| dc-west-s5 | 09-03 23:13 | 09-04 01:45 | 153 | 66.1 | hit |
| dc-west-s5 | 09-04 01:47 | 09-04 02:10 | 24 | 62.6 | hit |
| dc-west-s3 | 09-04 02:18 | 09-04 02:28 | 11 | 61.6 | residual heat after the dc-west heat-wave window |
| dc-west-s5 | 09-04 02:20 | 09-04 02:31 | 12 | 61.6 | residual heat after the dc-west heat-wave window |

## 6. Rate of change (preview for rule 5) — absolute change per minute, consecutive minutes only

| sensor | period | median | p95 | p99 | max |
|---|---|---|---|---|---|
| cpu_temp | normal | 0.60 | 1.70 | 2.20 | 18.50 |
| cpu_temp | during failure | 0.60 | 1.80 | 2.60 | 12.50 |
| fan_rpm | normal | 60.00 | 177.00 | 239.00 | 2840.00 |
| fan_rpm | during failure | 71.00 | 223.00 | 283.00 | 2156.00 |
| power_draw | normal | 7.70 | 22.30 | 29.10 | 101.20 |
| power_draw | during failure | 7.90 | 23.10 | 30.50 | 183.70 |
| mem_used | normal | 1.00 | 3.00 | 4.00 | 6.00 |
| mem_used | during failure | 1.00 | 3.00 | 4.00 | 6.00 |
| outside_temp | normal | 0.40 | 1.10 | 1.40 | 2.50 |

The load-step bug (6–11 °C jumps at every schedule change, 92 times) was fixed in the generator on 2026-09-03; this table is post-fix data. Where the remaining big jumps come from:

| ts_utc | host | before | after | in a failure window? |
|---|---|---|---|---|
| 09-02 22:57 | dc-west-s1 | 51.7 | 64.2 | yes |
| 09-03 01:01 | dc-east-s1 | 75.6 | 57.1 | no |

How fast fan_rpm falls during cooling_fail (dc-east-s1, 10-minute differences):

| ts_utc | fan_rpm | vs 10 min earlier |
|---|---|---|
| 09-02 22:55 | 4684 |  |
| 09-02 23:05 | 4486 | -198 |
| 09-02 23:15 | 3994 | -492 |
| 09-02 23:25 | 3294 | -700 |
| 09-02 23:35 | 2473 | -821 |
| 09-02 23:45 | 1808 | -665 |
| 09-02 23:55 | 1777 | -31 |

## 7. Trap status (things the detector must not fire on)

- Throttling (≥74.5 °C): 76 minutes, all inside dc-east-s1's cooling_fail. **Throttling without a failure: 0 minutes** → no trap data yet.
- Friday-night load spike: the 48 h window ends before Friday evening → no trap data.
- Sensor value -1 / 0: 0 rows. Seed 42's sensor_fault is the frozen kind, so no -1 appears.
- server_stop right before power_outage in the same dc: not in the current seed 42 (different dcs, west / hawaii).

## 8. Decisions needed

- Line and consecutive minutes per sensor: `cpu_temp > __ for __`, `fan_rpm < __ for __`, `power_draw > __`, `mem_used > __`
- Check the hit / false-alarm trade-off in section 5. A fixed line cannot separate dc-west heat wave + evening from a single-server fault — that is rule 6, peer comparison.
- Three traps (throttling without failure, Friday night, -1) are absent from the data. Add them to the generator now, or defer until after Phase 2.