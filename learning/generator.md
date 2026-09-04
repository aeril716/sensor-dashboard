# generator.py 수정 기록

## 2026-09-03 — live 모드가 ground_truth.csv를 덮어쓰던 문제

**전:** `write_truth`가 항상 `"w"`(write = 새로 쓰기)로 파일을 열어서, `live`를 시작하면
48시간 backfill 정답 6개가 지워지고 새 6시간 정답만 남았다.

**후:**
```python
def write_truth(plans, seed, append=False):
    with open(TRUTH_PATH, "a" if append else "w", newline="") as f:   # append면 "a"(뒤에 붙이기), 아니면 "w"
        w = csv.writer(f)
        if f.tell() == 0:                                             # 파일 위치가 0 = 비어 있음 -> 헤더 한 번만
            w.writerow(["seed", "failure", "scope", "start_utc", "end_utc", "note"])
        for p in plans:
            w.writerow([...])
```
- `append=False`: 기본값. 안 넘기면 예전처럼 덮어쓴다 (backfill은 그대로).
- `"a" if append else "w"`: 한 줄 if. append가 True면 "a", 아니면 "w".
- `f.tell()`: 지금 파일의 어느 위치에 있나(바이트). "a"로 열면 끝에 가 있으므로 0이면 빈 파일 →
  헤더가 필요하다는 뜻. 이미 내용이 있으면 헤더를 또 쓰지 않는다.

live 쪽 호출만 바꿈:
```python
write_truth(plans, args.seed, append=True)
```

**확인 (scratch 복사본):** live 4초 → ground_truth.csv가 헤더 1 + 원래 6 + 새 6 = 13줄.
backfill 1시간 → 7줄 (덮어쓰기 유지). 진짜 data/ground_truth.csv는 7줄 그대로.

## 2026-09-03 — ambient_high가 서버에 안 보여서 물리 조정 (아에리 결정)

바꾼 것 두 줄:
```python
"dc-west": {"region": "us-west-2", "city": "Sacramento", "tz": "America/Los_Angeles", "outside_base": 30.0},
                                                                                       # Hillsboro 22.0 -> Sacramento 30.0
temp += 18.0                                     # heat wave     (12.0 -> 18.0)
```
왜: `ambient_push = max(0, outside - 30) * 0.6`이라 바깥이 30 °C를 넘어야 서버가 더워진다.
Hillsboro는 base 22, 새벽 히트웨이브 +12 해도 29 °C → 효과 0.6 °C. Sacramento 30 + 18 → 43~45 °C
→ push 8~9 °C.

재생성: `telemetry.db` 지우고 `backfill --hours 48 --seed 42 --start 2026-09-02T02:32:00+00:00`,
그 다음 `collector.py`. 고장 계획은 rng 순서가 같아서 ground_truth.csv **동일**.

결과: ambient_high 동안 dc-west cpu 중앙값 50.8 °C vs 다른 dc 43.3 (+7.5). 스로틀링(75 °C)은 여전히 0분.

## 2026-09-03 — 날씨 램프 + 고장 시각 가중 (PLAN.md Weather / Failure timing 반영)

### A. 데이터센터 상수: 기저 온도 하나 → 하루 최저/최고 둘
```python
"dc-west": {..., "low": 15.0, "high": 33.0},     # 새크라멘토 9월 평상시: 밤 15, 낮 33
HEAT_WAVE_LOW_PLUS = 7.0      # 폭염 때 밤 최저 +7  (15 -> 22, "밤에 안 식는다")
HEAT_WAVE_HIGH_PLUS = 13.0    # 폭염 때 낮 최고 +13 (33 -> 46)
HEAT_RAMP_UP_H = 30           # 폭염이 0에서 100%까지 차오르는 데 30시간
HEAT_RAMP_DOWN_H = 12         # 끝난 뒤 12시간에 걸쳐 빠짐
```

### B. 날씨 함수 세 개
```python
def daily_curve(local_dt):
    h = local_dt.hour + local_dt.minute / 60
    return 0.5 + 0.5 * math.sin((h - 9) / 24 * 2 * math.pi)
```
하루 중 "얼마나 더운 시각인가"를 0~1로. sin은 -1~1이라 `0.5 + 0.5*sin`으로 0~1에 맞춤.
`(h-9)/24*2π`: h=15일 때 sin=1(최고), h=3일 때 sin=-1(최저). 예: 15:00 → 1.0, 03:00 → 0.0, 09:00 → 0.5.

```python
def heat_wave_strength(dc_id, now_utc, plans):
    for p in plans:
        if p["failure"] == "ambient_high" and p["scope"] == dc_id:
            up = timedelta(hours=HEAT_RAMP_UP_H)
            down = timedelta(hours=HEAT_RAMP_DOWN_H)
            if p["start"] - up <= now_utc < p["start"]:
                return (now_utc - (p["start"] - up)) / up      # 램프 올라가는 중: 0 -> 1
            if p["start"] <= now_utc < p["end"]:
                return 1.0                                       # 계획된 구간: 100%
            if p["end"] <= now_utc < p["end"] + down:
                return 1.0 - (now_utc - p["end"]) / down        # 빠지는 중: 1 -> 0
    return 0.0
```
폭염 세기 0~1. `(now - 시작) / up`은 timedelta ÷ timedelta = 비율(소수). 시작 30시간 전이면 0,
15시간 전이면 0.5, 시작 시각에 1. 직선이라 점프가 없다.

```python
def outside_temp(dc_id, now_utc, plans, rng):
    dc = DATACENTERS[dc_id]
    local = now_utc.astimezone(ZoneInfo(dc["tz"]))
    strength = heat_wave_strength(dc_id, now_utc, plans)
    low = dc["low"] + strength * HEAT_WAVE_LOW_PLUS         # 오늘의 최저
    high = dc["high"] + strength * HEAT_WAVE_HIGH_PLUS      # 오늘의 최고
    return low + (high - low) * daily_curve(local) + rng.gauss(0, 0.4)
```
"최저 + (최고-최저) × 하루곡선". 예: 새크라멘토 폭염 100%, 15:00 → 22 + 24×1.0 = 46.
평상시 03:00 → 15 + 18×0 = 15. `rng.gauss(0, 0.4)` = 표준편차 0.4 °C 잡음.

### C. 고장 시각: 균등 랜덤 → 바쁜 시간 가중
```python
def rand_time(min_minutes_before_end, tz, weight_fn):
    span = int((end - start).total_seconds() / 60) - min_minutes_before_end
    minutes = list(range(60, max(61, span)))                 # 후보: 시작 60분 후 ~ 끝 여유 전, 1분 단위
    weights = [weight_fn((start + timedelta(minutes=m)).astimezone(ZoneInfo(tz))) for m in minutes]
    return start + timedelta(minutes=rng.choices(minutes, weights=weights)[0])
```
- 후보 분마다 가중치 = `weight_fn(그 분의 현지 시각)`. 서버 고장은 `load_at`(부하 0.15~0.95),
  ambient_high는 `daily_curve`(더운 시각).
- `rng.choices(후보, weights=가중치)`: 가중치에 비례해 하나 뽑기. 저녁(0.85)이 새벽(0.15)보다 약 6배.
- 물리식은 안 건드림. 언제 나느냐만 바뀜.
- 호출부: `rand_time(180, host["tz"], load_at)` 처럼 시간대와 가중 함수를 넘김. 그래서 host를
  `["host_id"]`가 아니라 dict 통째로 들고 다니다가 scope에 넣을 때만 `host["host_id"]`.

### 결과 (seed 42, 같은 --start)
- 고장 6개 전부 시각 이동. cooling_fail이 Ashburn 저녁 19:01 → **dc-east-s1 스로틀링 77분 (최고 76.2 °C)**.
- ambient_high Thu 15:14~19:03 Sacramento, 바깥 최고 47.2. dc-west 서버 5대 오후 42 → 52.7 °C 동반 상승,
  저녁 피크엔 64.6 (전날 같은 시각 59.0).
- 바깥 온도 변화율: 30분 평균 기준 최대 0.058 °C/min (목표 0.045 근처). 분 단위 원시값은 잡음 0.4 때문에
  중앙값 0.40, 최대 2.5 °C/min — 잡음 크기는 아에리 결정 사항.

## 2026-09-03 — 부하 계단 수정 (PLAN "Edges are smoothed"가 거짓이었음)

**문제:** 옛 `load_at`은 `base * (0.9 + 0.1*sin(...))`로 한 시간 *안*에서만 살짝 흔들었고, 정각에
base가 0.15 → 0.85로 바뀌는 건 그대로 계단. 서버 온도가 1분에 -11 °C까지 튀는 일이 48시간에 92번.

**수정:** 함수를 둘로 나눔.
```python
def schedule(local_dt):
    """계단 그대로. 이 시각의 부하가 얼마인가 (0.15 / 0.5 / 0.85 / 0.95 / 0.4 …)"""
    ...
    if 16 <= h < 23:
        if is_friday and h >= 20:
            return 0.95
        return 0.85
    ...

def load_at(local_dt):
    samples = [schedule(local_dt + timedelta(minutes=m)) for m in range(-30, 30)]
    return sum(samples) / len(samples)
```
- `schedule`: 예전 if/elif를 `return`으로 바꾼 것. 값만 돌려주고 끝.
- `load_at`: 지금 시각의 앞뒤 30분, 총 60개 시각의 schedule 값을 **평균**. 이게 이동평균(moving average).
  경계 30분 전부터 새 값이 조금씩 섞여 들어와서 직선 램프가 된다.
- `range(-30, 30)` = -30, -29, …, 29 → 60개.

확인 (Ashburn 수요일):
```
15:30 0.150   15:40 0.267   15:50 0.383   16:00 0.500   16:10 0.617   16:20 0.733   16:30 0.850
```
재생성 후 1분 6 °C 초과 점프: 92 → 3 (남은 3개는 overload 시작과 침묵 복귀).
**주의:** `load_at`이 고장 시각 가중치에도 쓰여서 seed 42 정답이 살짝 움직였다:
overload 23:04 → 22:57, cooling_fail 23:01 → 23:02. 나머지 4개 동일.

내가 처음 패치할 때 `s.replace(...)` 결과를 변수에 다시 넣지 않아서(`s = s.replace` 빠짐) 파일이 안 바뀐 채
"patched"라고 찍혔다. 두 번째에 고침. 교훈: 패치 뒤에는 `grep`으로 실제 파일을 확인.

## 2026-09-03 — 폴더 정리: 경로를 파일 기준으로

폴더를 `raw_data/` → `src/`(코드) + `data/`(DB, 정답지)로 나눴다. 예전엔 `DB_PATH = "telemetry.db"`라서
"지금 셸이 서 있는 폴더"에 DB를 만들었다 — 다른 폴더에서 실행하면 엉뚱한 곳에 새 DB가 생겼다.
```python
from pathlib import Path
DATA_DIR = Path(__file__).resolve().parent.parent / "data"   # 이 파일(src/generator.py) → src/ → 레포 루트 → data/
DB_PATH = DATA_DIR / "telemetry.db"
TRUTH_PATH = DATA_DIR / "ground_truth.csv"
```
- `__file__` = 이 파이썬 파일의 경로. `.resolve()` = 절대경로로. `.parent` = 한 단계 위 폴더.
- `Path / "이름"` = 경로 이어 붙이기. 슬래시가 연산자.
- collector.py, detector.py도 같은 한 줄. 이제 어디서 실행해도 `<레포>/data/telemetry.db`.
