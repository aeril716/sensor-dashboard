# collector.py 한 줄씩

collector.py는 5부분: ① 센서별 파서, ② hosts에서 dc/city 붙이기, ③ 테이블 만들기,
④ 새 raw 행만 읽어서 쓰기, ⑤ 실행.

## ① 파서 — collector.py 25~88줄

**준비물 3줄**
```python
import json      # JSON 글자를 파이썬 값으로 바꾸는 도구
import re        # 글자 속에서 패턴 찾는 도구 (정규식)
import sqlite3   # SQLite DB 여는 도구
DB_PATH = "telemetry.db"   # 파일 이름을 한 곳에만 적어둠
```

**공용 도우미 — JSON에서 칸 하나 꺼내기**
```python
def json_field(raw, key):
    try:
        obj = json.loads(raw)          # 글자 -> 사전(dict). 예: '{"watts": 409.6}' -> {"watts": 409.6}
    except json.JSONDecodeError:       # JSON 모양이 아니면 여기로 옴
        raise ValueError("invalid_json")
    if not isinstance(obj, dict) or key not in obj:   # 사전이 아니거나 그 칸이 없으면
        raise ValueError(f"missing_field:{key}")
    return obj[key]                    # 사전에서 key 칸의 값. obj["watts"] -> 409.6
```
`try / except`는 "해보고, 실패하면 이렇게 해". `raise ValueError("…")`는 "여기서 멈추고 이 이유를
던진다". 이 이유 글자가 나중에 그대로 `parse_error` 컬럼이 된다.

**센서별 파서 5개 — 각각 raw 글자 하나 받아서 숫자 하나 돌려줌**
```python
def parse_cpu_temp(raw):
    return round(int(raw) / 16, 1)    # "918" -> 918 -> 57.375 -> 57.4

def parse_fan_rpm(raw):
    return int(raw)                   # "4730" -> 4730

def parse_power_draw(raw):
    return json_field(raw, "watts")   # '{"psu": 1, "watts": 409.6, "status": "ok"}' -> 409.6

def parse_mem_used(raw):
    m = re.search(r"used (\d+)G", raw)    # "used 83G" 패턴 찾기. \d+ = 숫자 1개 이상, ( ) = 이 부분만 기억
    if m is None:                         # 못 찾으면
        raise ValueError("pattern_not_found")
    return int(m.group(1))                # 기억한 괄호 부분 -> "83" -> 83

def parse_outside_temp(raw):
    return json_field(raw, "temp_c")  # '{"temp_c": 24.8, ...}' -> 24.8
```
`int("918")`은 글자를 정수로. 글자가 숫자가 아니면(`"ERR"`) 파이썬이 스스로 `ValueError`를
던진다 — 그래서 저기엔 `raise`를 따로 안 썼다.

**이름표 → 함수 연결**
```python
PARSERS = {
    "cpu_temp": parse_cpu_temp,
    "fan_rpm": parse_fan_rpm,
    "power_draw": parse_power_draw,
    "mem_used": parse_mem_used,
    "outside_temp": parse_outside_temp,
}
```
사전이다. `PARSERS["cpu_temp"]`라고 하면 `parse_cpu_temp` 함수가 나온다. 센서가 늘면 여기 한 줄 추가.

**총괄 — 어떤 센서든 이걸 부르면 됨**
```python
def parse(sensor, raw):
    fn = PARSERS.get(sensor)              # 사전에서 찾기. 없으면 None (에러 안 남)
    if fn is None:
        return None, "unknown_sensor"     # 값 없음, 이유 있음
    try:
        return float(fn(raw)), None       # 성공: 값 있음, 이유 없음
    except ValueError as e:
        msg = str(e)
        if msg.startswith("invalid literal") or msg.startswith("could not convert"):
            msg = "not_a_number"          # 파이썬 기본 메시지는 매번 달라서 고정 글자로 바꿈
        return None, msg
    except TypeError:
        return None, "not_a_number"       # "watts": null 같은 경우
```
항상 **(값, 이유)** 두 개를 돌려주고, 둘 중 하나는 반드시 `None`.

- 성공: `parse("cpu_temp", "918")` → `(57.4, None)`
- 실패: `parse("cpu_temp", "ERR")` → `(None, "not_a_number")`

`msg`를 고정 글자로 바꾸는 이유: 파이썬 원문은 `invalid literal for int() with base 10: 'ERR'`처럼
나쁜 값이 안에 들어가서 매번 다르다. 그러면 나중에 "같은 에러 몇 번"을 셀 수 없다 (PLAN.md 규칙).

실제 결과:
```
sensor       raw                                      -> value      parse_error
cpu_temp     '-16'                                    -> -1.0       None            (판단 안 함, 그대로)
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

## ② hosts에서 dc/city 붙이기 — collector.py 91~105줄

```python
def load_hosts(con):
    """host_id -> (dc, city) for the 15 servers."""
    return {host_id: (dc, city)
            for host_id, dc, city in con.execute("SELECT host_id, dc, city FROM hosts")}
```
- `con.execute("SELECT …")`: DB에 SQL 질문을 보내고 행들을 받는다. hosts 테이블 15행.
- `for host_id, dc, city in …`: 행 하나가 3칸이라 변수 3개에 한 번에 풀어 담는다.
- `{ 키: 값 for … }`: 반복하면서 사전을 만드는 문법. 결과는
  `{"dc-east-s1": ("dc-east", "Ashburn"), "dc-east-s2": ("dc-east", "Ashburn"), …}` 15개.
- `(dc, city)`처럼 괄호로 묶은 건 튜플 — 값 두 개를 한 덩어리로.

DB를 15만 번 물어보지 않고, 시작할 때 한 번 읽어서 사전에 담아두는 게 이 함수의 이유.

```python
def host_info(host_id, hosts):
    if host_id in hosts:                       # 서버면 사전에 있음
        return hosts[host_id]                  # ("dc-east", "Ashburn")
    if host_id.endswith("-weather"):           # 날씨 행은 hosts 테이블에 없음
        return host_id[: -len("-weather")], None   # "dc-east-weather" -> "dc-east", 도시는 없음
    return None, None                          # 둘 다 아니면 모름
```
- `host_id in hosts`: 사전에 그 키가 있나. 있으면 `hosts[host_id]`로 꺼냄.
- `endswith("-weather")`: 글자가 이걸로 끝나나.
- `host_id[: -len("-weather")]`: 글자 자르기. `len("-weather")`는 8, `[:-8]`은 "뒤에서 8글자 뺀 앞부분".
  `"dc-east-weather"[:-8]` → `"dc-east"`.
- 항상 (dc, city) 두 개를 돌려준다. 없으면 `None`.

예:
- `host_info("dc-west-s5", hosts)` → `("dc-west", "Hillsboro")`
- `host_info("dc-hawaii-weather", hosts)` → `("dc-hawaii", None)`
- `host_info("mystery-box", hosts)` → `(None, None)`

## ③ 테이블 만들기 — collector.py 108~128줄

```python
def open_db():
    con = sqlite3.connect(DB_PATH)          # telemetry.db 열기 (없으면 새로 만듦)
    con.execute("""
        CREATE TABLE IF NOT EXISTS clean_readings (
            ts_utc      TEXT NOT NULL,      # 시각 (UTC 글자)          NOT NULL = 비면 안 됨
            host_id     TEXT NOT NULL,      # dc-east-s4
            dc          TEXT,               # dc-east   (weather 행도 있음)
            city        TEXT,               # Ashburn   (weather 행은 비어 있음)
            sensor      TEXT NOT NULL,      # cpu_temp
            raw         TEXT NOT NULL,      # 원문 그대로 보관
            value       REAL,               # 숫자 (소수 가능). 못 읽었으면 비어 있음
            parse_error TEXT                # 못 읽은 이유. 읽었으면 비어 있음
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_clean_ts ON clean_readings(ts_utc)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_clean_host_sensor ON clean_readings(host_id, sensor, ts_utc)")
    return con
```
- `IF NOT EXISTS`: 이미 있으면 그냥 넘어감. 그래서 collector를 몇 번 돌려도 안전.
- `TEXT` 글자, `REAL` 소수. SQLite 자료형은 이 둘 + `INTEGER` 정도만 알면 됨.
- `"""…"""` 세 따옴표: 여러 줄 글자.
- 인덱스 = 책 뒤의 색인. "시각으로 찾기", "이 서버의 이 센서를 시간 순으로 찾기"를 빨리 하기 위해
  두 개 만들었다. 없어도 동작은 같고 느리기만 함.

## ④ 새 raw 행만 읽어서 쓰기 — collector.py 131~152줄

```python
def collect_once(con):
    hosts = load_hosts(con)                                          # ② 사전 15개
    last = con.execute("SELECT MAX(ts_utc) FROM clean_readings").fetchone()[0] or ""
    new_rows = con.execute(
        "SELECT ts_utc, host_id, sensor, raw FROM raw_readings WHERE ts_utc > ? ORDER BY ts_utc, host_id",
        (last,),
    )
```
- `MAX(ts_utc)`: clean 테이블에서 가장 늦은 시각. `.fetchone()`은 결과 첫 행, `[0]`은 그 행의 첫 칸.
- `or ""`: 테이블이 비어 있으면 MAX가 `None`인데, 그러면 `""`(빈 글자)로 바꿈.
  빈 글자는 어떤 글자보다 "작아서" `ts_utc > ""`는 전부 통과 → 처음엔 전부 읽음.
- `WHERE ts_utc > ?`: 물음표 자리에 `(last,)`가 들어감. 직접 글자를 붙이지 않고 `?`를 쓰는 게
  SQL의 정석 (값에 따옴표가 있어도 안전).
- `(last,)` 끝의 쉼표: 값 하나짜리 튜플. 쉼표 없으면 그냥 글자라서 에러.
- 두 번째 실행에서 `last`는 `2026-09-04T02:31:00+00:00` → 그보다 늦은 raw는 없음 → 0행.

```python
    out = []
    errors = 0
    for ts, host_id, sensor, raw in new_rows:       # raw 행 하나씩
        dc, city = host_info(host_id, hosts)         # ②
        value, err = parse(sensor, raw)              # ①
        if err is not None:
            errors += 1                              # 실패 개수만 셈
        out.append((ts, host_id, dc, city, sensor, raw, value, err))   # 8칸 = 테이블 컬럼 순서

    con.executemany("INSERT INTO clean_readings VALUES (?,?,?,?,?,?,?,?)", out)
    con.commit()                                     # 저장 확정. 이게 없으면 파일에 안 남음
    return len(out), errors
```
- `out.append(...)`: 리스트 끝에 한 줄 추가. 18만 줄을 메모리에 모아서
- `executemany`: 한 번에 넣음. 한 줄씩 `execute` 하면 훨씬 느림.
- 물음표 8개 = 컬럼 8개. 튜플 순서가 ③의 컬럼 순서와 정확히 같아야 함.
- 돌려주는 값: (쓴 행 수, 실패 수).

왜 시각 기준으로 "새 행"을 정하나: generator는 1분치(78행)를 한 번에 commit하므로 어떤 분은
"전부 있음" 아니면 "아직 없음" 둘 중 하나. 반쯤 들어온 분은 없다.

## ⑤ 실행 — collector.py 155~163줄

```python
def main():
    con = open_db()                                   # ③
    n, errors = collect_once(con)                     # ④
    total = con.execute("SELECT COUNT(*) FROM clean_readings").fetchone()[0]
    print(f"collected {n} new rows ({errors} parse errors) -> clean_readings now has {total} rows")

if __name__ == "__main__":
    main()
```
- `f"…{n}…"`: 글자 속 `{ }` 자리에 변수 값을 끼워 넣음.
- `if __name__ == "__main__"`: "이 파일을 직접 실행했을 때만 main()을 돌려라".
  다른 파일이 `import collector`로 파서만 빌려 쓸 때는 실행 안 됨. (테스트에서 `c.parse(...)`만
  불러 쓴 게 그 예.)

실행 결과:
```
collected 181036 new rows (0 parse errors) -> clean_readings now has 181036 rows   # 1회
collected 0 new rows (0 parse errors) -> clean_readings now has 181036 rows        # 2회
```
