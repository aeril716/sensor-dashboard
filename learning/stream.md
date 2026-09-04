# stream.py 한 줄씩

stream.py는 "틱 루프". 정해진 간격마다 collector.collect_once를 불러서 새 raw 행을
clean_readings로 옮기고, 한 줄 상태를 찍는다. 나중에 디텍터·대시보드도 같은 틱 안에 들어간다.

## 준비물
```python
import argparse                          # 명령줄 옵션(--interval 5 같은 것) 읽는 도구
import time                              # time.sleep = 몇 초 기다리기
from datetime import datetime, timezone  # 지금 시각 찍기용
import collector                         # 우리 collector.py. open_db, collect_once를 빌려 쓴다
```
`import collector`가 되는 이유: 같은 폴더(src)에 있으니까. 이때 collector.py의
`if __name__ == "__main__"` 아래 main()은 실행되지 않는다.

## 틱 하나
```python
def tick(con):
    n, errors = collector.collect_once(con)      # 새 행 옮기기. (쓴 행 수, 실패 수)
    latest = con.execute("SELECT MAX(ts_utc) FROM clean_readings").fetchone()[0]   # 가장 늦은 시각
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")     # 지금 실제 시각을 "03:37:39" 꼴로
    print(f"[{now}] +{n} rows ({errors} parse errors)  latest reading {latest}")
    return n
```
- `strftime("%H:%M:%S")`: 시각을 글자로. %H 시, %M 분, %S 초.
- 한 줄에 "실제 시각 / 이번에 옮긴 수 / 실패 수 / 데이터의 가장 늦은 시각"이 다 들어간다.
  실제 시각과 데이터 시각의 차이 = 얼마나 뒤처져 있나.

## 실행
```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=60, help="seconds between ticks")
    ap.add_argument("--once", action="store_true", help="run one tick and exit")
    args = ap.parse_args()
```
- `--interval`: 몇 초마다 틱. 기본 60 (센서가 1분마다 1개니까). `type=float`라 `--interval 2.5`도 됨.
- `--once`: `action="store_true"` = 쓰면 True, 안 쓰면 False. 값을 안 받는 스위치.
- `args.interval`, `args.once`로 꺼내 쓴다.

```python
    con = collector.open_db()
    print(f"stream loop: tick every {args.interval:g} s  (ctrl-c to stop)")
    try:
        while True:                  # 끝없이 반복
            tick(con)
            if args.once:
                break                # --once면 한 번 하고 반복 탈출
            time.sleep(args.interval)
    except KeyboardInterrupt:        # Ctrl-C를 누르면 파이썬이 이 예외를 던진다
        print("\nstopped")
```
- `while True` + `break`: 무한 반복인데 조건이 맞으면 빠져나옴.
- `:g` 포맷: 60.0을 "60"으로, 2.5는 "2.5"로 깔끔하게.
- `try / except KeyboardInterrupt`: Ctrl-C로 끄면 빨간 에러 대신 "stopped" 한 줄.

## 테스트 결과
generator를 `live --fast`(1초 = 1분)로 돌리면서 `stream.py --interval 5`를 같이 돌림 (scratch 복사본에서):
```
stream loop: tick every 5 s  (ctrl-c to stop)
[03:37:39] +189 rows (0 parse errors)  latest reading 2026-09-04T02:34:00+00:00
[03:37:44] +315 rows (0 parse errors)  latest reading 2026-09-04T02:39:00+00:00
[03:37:49] +315 rows (0 parse errors)  latest reading 2026-09-04T02:44:00+00:00
[03:37:54] +315 rows (0 parse errors)  latest reading 2026-09-04T02:49:00+00:00
[03:37:59] +315 rows (0 parse errors)  latest reading 2026-09-04T02:54:00+00:00
```
- 5초마다 5분치 = 63행 × 5 = 315행. (한 분 = 날씨 3 + 서버 15 × 센서 4 = 63행)
- 첫 틱 189 = 3분치. generator가 3초 먼저 출발했으니까.
- 끝난 순간 raw는 02:55, clean은 02:54 — 다음 틱이 잡을 1분 차이. 정상.
