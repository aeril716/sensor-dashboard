# detector.py 한 줄씩

detector.py는 clean_readings에서 "이상한 것"을 찾는다. 이름은 안 붙인다(그건 Phase 3).
출력은 **에피소드**: 어느 호스트, 어느 센서, 언제부터 언제까지, 몇 분, 얼마나(peak), 어떤 규칙.
숫자는 전부 인자(파라미터). PLAN.md: 숫자는 아에리가 정한다.

## ① 불러오기 — 센서 하나, 모든 호스트, 시간순
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
- `value IS NOT NULL`: parse_error 난 행(값 없음)은 건너뜀.
- `series.setdefault(host_id, [])`: 사전에 그 호스트 칸이 없으면 빈 리스트를 만들고, 있으면 있는 걸 돌려줌.
  그 뒤 `.append((ts, value))`로 한 점 추가.
- 결과: `{"dc-east-s1": [("2026-09-02T02:32:00+00:00", 57.4), ("…02:33…", 57.6), …], "dc-east-s2": […], …}`

## ② 규칙: threshold — 선을 N분 연속 넘으면 에피소드
```python
def threshold(series, sensor, line, minutes, below=False):
    sign = "<" if below else ">"
    rule = f"{sensor} {sign} {line:g} for >= {minutes} min"     # 사람이 읽는 규칙 문장. {line:g} = 65.0을 "65"로
    episodes = []
```
```python
    def close(host_id, run):
        if len(run) >= minutes:                    # 연속 구간이 N분 이상일 때만 에피소드
            values = [v for _, v in run]           # (ts, v) 목록에서 v만 뽑기
            episodes.append({
                "host_id": host_id, "sensor": sensor,
                "start": run[0][0], "end": run[-1][0],    # 첫 점의 ts, 마지막 점의 ts
                "minutes": len(run),
                "peak": min(values) if below else max(values),   # 아래쪽 규칙이면 최저가 peak
                "rule": rule,
            })
```
함수 안의 함수. 바깥의 `episodes`, `minutes`, `rule`을 그대로 쓸 수 있어서 인자를 덜 넘긴다.

```python
    for host_id, points in series.items():
        run = []                                   # 지금 "선 넘은 채로 이어지는" 구간
        for ts, value in points:
            past = value < line if below else value > line
            if past:
                run.append((ts, value))            # 넘었으면 구간에 추가
            else:
                close(host_id, run)                # 안 넘었으면 구간 끊고 (길면 저장)
                run = []                           # 새 구간 시작
        close(host_id, run)                        # 데이터 끝까지 넘고 있던 구간도 마무리
    return sorted(episodes, key=lambda e: e["start"])
```
- 호스트 하나씩, 점 하나씩 본다. 점이 선을 넘으면 `run`에 쌓고, 안 넘는 순간 `run`을 닫는다.
- 마지막 `close`: 데이터가 끝나는 순간까지 넘고 있으면 for 안에서는 닫힐 기회가 없어서 한 번 더.
- `sorted(..., key=lambda e: e["start"])`: 시작 시각 순으로 정렬. `lambda e: e["start"]` = "각 에피소드에서 start를 꺼내 그걸로 비교".
- "분" = "행 수". 1분에 1행이라 같지만, 침묵 구간이 있으면 행이 빠져서 실제 시간보다 짧게 셈. 지금은 그대로 둠.

예: dc-east-s1 cpu_temp가 23:17부터 00:59까지 103행 연속 65 초과, 최고 76.2 →
`{"host_id": "dc-east-s1", "sensor": "cpu_temp", "start": "…23:17…", "end": "…00:59…", "minutes": 103, "peak": 76.2, "rule": "cpu_temp > 65 for >= 10 min"}`

## ③ 출력
```python
def print_episodes(episodes):
    if not episodes:
        print("no episodes"); return
    print(f"{'host_id':<16}{'sensor':<12}{'start (UTC)':<26}{'end (UTC)':<26}{'min':>5}{'peak':>8}   rule")
    for e in episodes:
        print(f"{e['host_id']:<16}{e['sensor']:<12}{e['start']:<26}{e['end']:<26}{e['minutes']:>5}{e['peak']:>8.1f}   {e['rule']}")
```
`:<16` 왼쪽 정렬 16칸, `:>5` 오른쪽 정렬 5칸, `:>8.1f` 소수 1자리 8칸.

## ④ 실행 — 서브커맨드
```python
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="rule", required=True)      # 첫 단어가 규칙 이름. threshold, (나중에) slope, peer …
    t = sub.add_parser("threshold")
    t.add_argument("sensor")                                 # 위치 인자: 순서대로
    t.add_argument("line", type=float)
    t.add_argument("--minutes", type=int, default=10)
    t.add_argument("--below", action="store_true")
```
`python detector.py threshold cpu_temp 65 --minutes 10` → args.rule="threshold", sensor="cpu_temp", line=65.0, minutes=10, below=False.
규칙이 늘면 `sub.add_parser("slope")`처럼 하나씩 추가.

## 첫 실행 결과 (2026-09-03, 숫자는 아직 후보)
```
cpu_temp > 65 for >= 10 min
dc-east-s1   09-02 23:17 -> 00:59  103 min  peak 76.2   <- cooling_fail (정답)
dc-west-s4   09-03 23:00 -> 00:31   92 min  peak 68.6   <- ambient_high 구간 안 (dc 전체 더움 + 저녁 피크)
dc-west-s1   09-03 23:16 -> 23:38   23 min  peak 67.0   <- 같은 이유
dc-west-s4   09-04 00:33 -> 00:45   13 min  peak 66.9

fan_rpm < 2000 for >= 10 min
dc-east-s1   09-02 23:40 -> 00:59   80 min  low 1651    <- cooling_fail, 온도보다 23분 늦게 잡힘(선이 낮아서)

power_draw > 450 / mem_used > 150 for >= 10 min
dc-west-s1 만                                             <- overload (정답)
```
고정 선 하나로는 "서버 한 대 고장"과 "dc 전체가 더움"을 못 가른다 — 그게 6번(peer comparison)이 필요한 이유.
