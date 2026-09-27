# 오션클리어 개발 계획

> 해커톤 프로토타입 기준의 구체적인 개발 계획입니다. 운영 확장 계획은 각 항목의 "운영 확장"에 따로 적었습니다.

[← README로 돌아가기](../README.md) · [기획서 보기 →](PROPOSAL.md)

## 목차

1. [개발 목표와 범위](#1-개발-목표와-범위)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [기술 스택](#3-기술-스택)
4. [데이터 수집](#4-데이터-수집)
5. [데이터 저장과 스키마](#5-데이터-저장과-스키마)
6. [모델 ① 조업량 예측](#6-모델--조업량-예측)
7. [모델 ② 낙하물 몬테카를로 분산](#7-모델--낙하물-몬테카를로-분산)
8. [통제구역 최적화](#8-통제구역-최적화)
9. [영향 산정 (모듈 3)](#9-영향-산정-모듈-3)
10. [API 설계](#10-api-설계)
11. [화면 설계](#11-화면-설계)
12. [저장소 구조와 개발 환경](#12-저장소-구조와-개발-환경)
13. [테스트와 검증](#13-테스트와-검증)
14. [역할 분담](#14-역할-분담)
15. [마일스톤](#15-마일스톤)
16. [리스크와 대응](#16-리스크와-대응)

---

## 1. 개발 목표와 범위

**목표:** 고흥 나로우주센터 앞바다를 대상으로, 발사 후보일과 통제구역 대안별 예상 어업 영향을 계산해 보여주는 웹 데모를 만든다.

| 모듈 | 해커톤 구현 수준 | 핵심 기술 |
|---|---|---|
| 0. 해역 데이터 엔진 | 실제 작동 | GFW 데이터 수집, 0.01° 격자 집계 |
| 1. 안전구역 설계 | 실제 작동 | 모델 ② 낙하 분산 + 최적화 |
| 2. 발사일 추천 | 실제 작동 | 모델 ① 조업량 예측 |
| 3. 영향 산정 | 예시 계산 + 화면 | 모델 ① 반사실 예측 |
| 어민 앱 | 화면 설계만 | Figma 또는 Flutter 목업 |

**대상 해역 (분석 범위):** 북위 33.5°~34.6°, 동경 127.0°~128.2°

**발사대 기준 좌표 (근사값):** 북위 34.43°, 동경 127.53° (나로우주센터)

---

## 2. 시스템 아키텍처

```
┌──────────────────────── 수집 (ingest/) ────────────────────────┐
│ GFW 4Wings API │ GK2A 수온 │ GOCI-II 엽록소 │ ERA5 │ 기상청 │ GEBCO │
└───────────────────────────────┬────────────────────────────────┘
                                ↓  격자 통일 (0.01°), Parquet 저장
┌──────────────────────── 저장 (data/) ──────────────────────────┐
│ 해커톤: Parquet + DuckDB(spatial)   운영: PostgreSQL + PostGIS   │
└───────────────┬───────────────────────────────┬────────────────┘
                ↓                               ↓
   ┌──── 모델 ① 조업량 예측 ────┐   ┌──── 모델 ② 낙하 분산 ────┐
   │ LightGBM (Tweedie)        │   │ 3자유도 궤적 + 몬테카를로 │
   └────────────┬──────────────┘   └────────────┬─────────────┘
                └──────────→ 통제구역 최적화 ←──────┘
                                ↓
                   FastAPI (선택) / Streamlit 직접 호출
                                ↓
                  Streamlit + pydeck 웹 데모 (배포)
```

- 무거운 계산(모델 학습, 몬테카를로 1만 회)은 **미리 오프라인으로 실행**해 결과를 Parquet로 저장하고, 화면은 저장된 결과만 불러온다. 데모가 느려지지 않게 하기 위함이다.

---

## 3. 기술 스택

| 영역 | 해커톤 | 운영 확장 | 선택 이유 |
|---|---|---|---|
| 언어 | Python 3.11 | Python, TypeScript, Dart | 데이터·모델·화면을 한 언어로 |
| 패키지 관리 | uv 또는 pip + `requirements.txt` | Poetry | 설치 재현성 |
| 데이터 처리 | pandas, NumPy, xarray | Polars | 표·격자 데이터 처리 |
| 파일 형식 | Parquet (pyarrow) | 동일 | 빠르고 용량 작음 |
| DB | DuckDB + spatial 확장 | PostgreSQL 16 + PostGIS 3 | 서버 없이 공간 쿼리, 무료 배포 가능 |
| 공간 처리 | GeoPandas, Shapely 2, pyproj, pymap3d | PostGIS | 다각형 연산, 좌표 변환 |
| 예측 모델 | LightGBM, scikit-learn, Optuna, SHAP | + MLflow | 0이 많은 데이터에 강함, 설명 가능 |
| 시뮬레이션 | SciPy(solve_ivp), Numba, joblib | + Celery, Redis | 궤적 적분, 병렬 실행 |
| 확률 밀도 | scipy.stats.gaussian_kde, scikit-image | 동일 | 낙하점 → 등고선 |
| API | FastAPI + Pydantic (선택) | FastAPI + SQLAlchemy + GeoAlchemy2 | 운영 시 앱·웹 공용 |
| 화면 | Streamlit + pydeck, Plotly | React + deck.gl/MapLibre, Flutter | 빠른 데모, 대용량 격자 지도 |
| 배포 | Streamlit Community Cloud | Docker Compose → 클라우드 | 링크 하나로 시연 |
| 협업 | GitHub (private), GitHub Issues | + GitHub Actions CI | 제출 전 비공개 유지 |

---

## 4. 데이터 수집

### 4-1. 데이터 목록

| 데이터 | 출처 | 받는 방법 | 해상도 | 기간 | 저장 파일 |
|---|---|---|---|---|---|
| 조업 시간 | Global Fishing Watch `public-global-fishing-effort` | 4Wings API (토큰 필요) 또는 지도 CSV 다운로드 | 0.01°, 일별, 선박별 | 2023-01 ~ 현재 | `fishing_daily.parquet` |
| SAR 선박 탐지 | Global Fishing Watch SAR 데이터셋 | API | 탐지 지점 | 2023-01 ~ 현재 | `sar_detections.parquet` |
| 해수면온도 | 천리안 2A호(GK2A) SST 산출물 | 국가기상위성센터 | 약 2km, 일별 | 동일 | `env_sst.parquet` |
| 엽록소 | 천리안 2B호(GOCI-II) | 국가해양위성센터 | 약 250m~1km, 일별 합성 | 동일 | `env_chl.parquet` |
| 과거 바람·파고 | ERA5 재분석 | Copernicus CDS (`cdsapi`) | 0.25°, 시간별 | 동일 | `era5_surface.nc` |
| 고도별 바람 | ERA5 기압면 자료 (1000~1 hPa) | Copernicus CDS | 0.25°, 시간별 | 발사 후보 월 | `era5_levels.nc` |
| 예보 바람·파고 | 기상청 API허브 | REST API | 격자 예보 | 발사 7일 전 | 실시간 조회 |
| 수심 | GEBCO | 파일 다운로드 | 15초 | 고정 | `gebco.tif` |
| 공휴일·명절 | `holidays` 패키지 | Python | 일별 | 동일 | 코드에서 생성 |

> GFW 데이터는 비상업적 이용이 기본 조건이다. 해커톤은 해당하지 않지만, 상용화 시 라이선스 계약 또는 상용 위성 AIS 구매가 필요하다.

### 4-2. 격자 통일 규칙

- 기준 격자: GFW와 같은 **0.01° 격자** (약 1km)
- `cell_id` = `f"{round(lat*100)}_{round(lon*100)}"`
- 수온·엽록소: xarray `interp` 로 격자 중심점에 보간
- ERA5(0.25°): 최근접 격자값 사용
- 육지 격자는 GEBCO 수심 ≥ 0 인 칸으로 판단해 제거

### 4-3. 수집 스크립트

| 파일 | 역할 |
|---|---|
| `ingest/gfw.py` | 기간을 월 단위로 나눠 API 호출, 재시도·속도 제한 처리, Parquet 저장 |
| `ingest/gk2a.py`, `ingest/goci2.py` | NetCDF 다운로드, 범위 자르기, 격자 보간 |
| `ingest/era5.py` | `cdsapi` 로 지상·기압면 자료 요청 |
| `ingest/build_grid.py` | `grid_cell` 테이블 생성 (수심, 해안·항구 거리 계산) |

---

## 5. 데이터 저장과 스키마

해커톤에서는 Parquet 파일을 DuckDB로 조회하고, 운영에서는 같은 구조로 PostGIS에 올린다.

| 테이블 | 열 | 설명 |
|---|---|---|
| `grid_cell` | cell_id (PK), lat, lon, depth_m, dist_coast_km, dist_port_km, geom | 격자 고정 정보 |
| `fishing_daily` | cell_id, date, vessel_id, gear_type, flag, hours | 조업 기록 |
| `env_daily` | cell_id, date, sst, chl, wind_ms, wave_m | 환경 자료 |
| `features` | cell_id, date, 특징 열들, target_hours | 모델 학습용 |
| `prediction` | cell_id, date, pred_hours, model_version, created_at | 모델 ① 결과 |
| `launch_scenario` | scenario_id, pad_lat, pad_lon, azimuth_deg, month, params_json | 발사 조건 |
| `impact_sample` | scenario_id, run_no, lat, lon | 모델 ② 낙하점 |
| `hazard_zone` | scenario_id, prob_level, geom | 확률 등고선 다각형 |
| `settlement` | launch_id, vessel_id, expected_hours, actual_hours, loss_hours | 모듈 3 결과 |

**PostGIS 예시 (운영):**

```sql
CREATE TABLE grid_cell (
  cell_id TEXT PRIMARY KEY,
  depth_m REAL, dist_coast_km REAL, dist_port_km REAL,
  geom geometry(Polygon, 4326)
);
CREATE INDEX ON grid_cell USING GIST (geom);

-- 통제구역 안 예측 조업량 합계
SELECT p.date, SUM(p.pred_hours) AS zone_hours
FROM prediction p
JOIN grid_cell g USING (cell_id)
JOIN hazard_zone z ON ST_Intersects(g.geom, z.geom)
WHERE z.scenario_id = :sid AND z.prob_level = 1e-5
GROUP BY p.date ORDER BY zone_hours;
```

**DuckDB 예시 (해커톤):**

```python
import duckdb
con = duckdb.connect("oceanclear.duckdb")
con.execute("INSTALL spatial; LOAD spatial;")
con.execute("CREATE TABLE fishing AS SELECT * FROM 'data/processed/fishing_daily.parquet'")
```

---

## 6. 모델 ① 조업량 예측

### 6-1. 문제 정의

- **예측 대상:** 격자(0.01°) × 날짜별 조업 시간 `hours`
- **특징:** 대부분의 칸이 0인 치우친 분포 → 일반 회귀 대신 Tweedie 분포 사용

### 6-2. 특징 목록

| 분류 | 특징 | 생성 방법 |
|---|---|---|
| 달력 | 요일, 월, 연중 날짜 sin/cos | pandas |
| 달력 | 공휴일 여부, 설·추석까지 남은 날 | `holidays` (KR) |
| 과거 | 격자별 7·14·28일 이동평균 (발사일 기준 최소 30일 전까지만) | groupby + rolling |
| 과거 | 작년 같은 주 조업량 | 52주 전 값 |
| 과거 | 주변 3×3 격자 평균 | 공간 이웃 집계 |
| 환경 | 수온, 수온 7일 변화량, 엽록소 | GK2A, GOCI-II |
| 환경 | 풍속, 유의파고 | ERA5 (학습), 기상청 예보 (D-7 재예측) |
| 고정 | 수심, 해안 거리, 항구 거리 | `grid_cell` |

> **정보 누수 방지:** 발사 1~3개월 전 예측에서는 발사일 직전 조업량을 알 수 없다. 이동평균 특징은 예측 시점 기준 과거 값만 쓴다.

### 6-3. 모델 설정

| 항목 | 값 |
|---|---|
| 모델 | `lightgbm.LGBMRegressor` |
| 목적함수 | `objective="tweedie"`, `tweedie_variance_power` 1.1~1.9 탐색 |
| 튜닝 | Optuna 50회 (num_leaves, learning_rate, min_child_samples, feature_fraction, 위 power) |
| 조기 종료 | 검증 세트 기준 100라운드 |
| 설명 | SHAP TreeExplainer, 날짜별 상위 특징 3개 표시 |

### 6-4. 검증 설계

| 구분 | 기간 |
|---|---|
| 학습 | 2023-01 ~ 2024-12 |
| 검증 (튜닝) | 2025-01 ~ 2025-12 |
| 시험 (최종 발표 수치) | 2026-01 ~ 최신 |

| 지표 | 의미 | 기준 모델과 비교 |
|---|---|---|
| WAPE (통제구역 합계) | 구역 전체 조업량 오차율 | 과거 같은 요일 평균 |
| MAE (격자별) | 칸 단위 오차 | 동일 |
| **스피어만 순위 상관** | 후보일 순위를 얼마나 맞히나 (서비스 핵심) | 동일 |

### 6-5. 두 단계 예측

1. **발사 1~3개월 전:** 환경 특징에 평년값(과거 같은 주 평균) 입력 → 후보일 1차 순위
2. **발사 7일 전:** 기상청 예보 풍속·파고로 교체해 재예측 → 최종 확인

---

## 7. 모델 ② 낙하물 몬테카를로 분산

### 7-1. 물리 모델 (3자유도 질점 궤적)

상태 벡터: 위치 (x, y, z), 속도 (vx, vy, vz), 발사대 기준 지역 좌표계(ENU)

```
dv/dt = g(z) − (ρ(z) · |v_rel| / (2β)) · v_rel
v_rel = v − wind(z)
β = m / (Cd · A)          # 탄도계수
g(z) = g0 · (R / (R + z))²
```

| 요소 | 구현 |
|---|---|
| 대기 밀도 ρ(z) | 미국 표준대기 1976 (`ambiance` 패키지 또는 직접 구현) |
| 바람 wind(z) | ERA5 기압면별 u, v 성분을 고도로 변환해 보간, 48km 이상은 0 |
| 적분 | `scipy.integrate.solve_ivp` (RK45), 이벤트: z = 0 에서 종료 |
| 좌표 변환 | `pymap3d.enu2geodetic` 으로 낙하점 위경도 계산 |
| 가속 | 궤적 함수 Numba `@njit`, 실행은 `joblib` 병렬 |

### 7-2. 입력값 (가정값)

국내 발사체 실제 제원은 비공개이므로 공개된 소형 발사체 수준의 **가정값**을 쓰고 화면과 발표에 명시한다.

| 변수 | 기준값 | 분산 (1회마다 무작위) |
|---|---|---|
| 1단 분리 고도 | 60 km | 정규분포 σ 1 km |
| 분리 속도 | 1.8 km/s | 정규분포 σ 20 m/s |
| 비행 경로각 | 35° | 정규분포 σ 0.5° |
| 발사 방위각 | 시나리오 값 (예: 170°, 175°, 180°) | 정규분포 σ 0.3° |
| 탄도계수 β | 2,000 kg/m² | 균등분포 ±20% |
| 바람 | 발사 월 ERA5 | 과거 해당 월 날짜 중 무작위 1일 |
| 실행 횟수 | 10,000회 | |

### 7-3. 결과 처리

1. 낙하점 10,000개 → `gaussian_kde` 로 0.01° 격자 위 확률 밀도 계산
2. 격자별 **개별 충돌 확률** = 밀도 × 격자 면적 × 선박 크기 보정
3. `skimage.measure.find_contours` 로 확률 10⁻³, 10⁻⁵ 등고선 추출
4. Shapely 다각형으로 변환해 `hazard_zone` 에 저장
5. 선박 보호 기준 **10⁻⁵** 경계를 통제구역으로 사용 (미국 발사장 선박 보호 기준값 참고)

### 7-4. 검증

- 누리호 발사 때 공개된 **항행경보 낙하 예상 구역 좌표**와 위치·방향·크기를 비교
- 바람을 0으로 두면 낙하점이 방위각 선 위에 모이는지 단위 테스트
- 실행 횟수 5,000 / 10,000 / 20,000에서 등고선 면적 변화가 5% 이내인지 확인 (수렴 확인)

---

## 8. 통제구역 최적화

**목적:** 위험 기준을 지키면서 예상 어업 영향이 가장 작은 발사 조건 찾기

```
minimize   Σ_(cell ∈ Zone(a, m)) pred_hours(cell, d) × value(cell)
subject to Zone(a, m) ⊇ {cell | Pi(cell) ≥ 1e-5}
변수: a = 발사 방위각 후보, d = 발사 후보일, m = d의 월
```

| 단계 | 방법 |
|---|---|
| 1 | 방위각 후보(예: 5개) × 월(12개)별로 모델 ② 결과를 **미리 계산**해 저장 |
| 2 | 후보일 d마다 해당 월 구역을 불러와 모델 ① 예측값 합산 |
| 3 | 조합 전체를 전수 탐색해 순위 (후보가 수백 개 수준이라 충분히 빠름) |
| 4 | 결과 표: 날짜, 방위각, 예상 영향 조업 시간, 영향 선박 수, 절감률 |

- `value(cell)` : 초기에는 1(조업 시간 기준), 위판 통계 확보 시 격자별 시간당 어업 가치로 교체

---

## 9. 영향 산정 (모듈 3)

모델 ①을 **반사실 예측**(발사가 없었다면 조업했을 양)에 그대로 활용한다.

```
손실 시간(선박 v) = Σ_(통제 시간, 구역) [ 예측 조업 − 실제 조업 ]
```

| 단계 | 내용 |
|---|---|
| 1 | 실제 통제 구역과 시작·종료 시각 입력 |
| 2 | 선박별 기준선: 같은 계절·요일 평균 + 모델 ① 예측 |
| 3 | 발사일 실제 조업(GFW 선박별 데이터)과 비교 |
| 4 | 보정: 통제구역 바깥 인접 해역 선박의 같은 날 변화량을 빼서 날씨 등 공통 요인 제거 (이중차분) |
| 5 | 선박별 산정표 CSV/PDF 출력 |

해커톤에서는 과거 날짜 하나를 "가상 발사일"로 정해 예시 산정표를 만든다.

---

## 10. API 설계

해커톤에서는 Streamlit이 Python 함수를 직접 호출하고, 운영 시 같은 함수를 FastAPI로 감싼다.

| 메서드 | 경로 | 입력 | 출력 |
|---|---|---|---|
| GET | `/grid/heatmap` | 기간, 요일, 월 | 격자별 조업 시간 |
| POST | `/hazard/simulate` | 발사대 좌표, 방위각, 월, 실행 횟수 | 낙하점, 확률 등고선 GeoJSON |
| POST | `/launch-days/rank` | 후보 기간, 방위각 후보 | 날짜별 예상 영향 순위, SHAP 요약 |
| POST | `/zones/compare` | 구역 대안 목록 | 대안별 영향 조업 시간·선박 수 |
| POST | `/settlement` | 실제 통제 기록 | 선박별 손실 산정표 |
| GET | `/model/metrics` | - | 기준 모델 대비 성능 지표 |

---

## 11. 화면 설계

| 페이지 | 구성 | 기술 |
|---|---|---|
| 1. 해역 조업 지도 | 격자 히트맵, 월·요일 필터, 발사대 위치 | pydeck `GridCellLayer` |
| 2. 낙하 분산 | 낙하점 산점도, 확률 등고선, 방위각 선택 | pydeck `ScatterplotLayer`, `PolygonLayer` |
| 3. 발사일 추천 | 후보 기간 입력 → 순위표, 막대그래프, 날짜별 SHAP 설명 | Streamlit, Plotly |
| 4. 구역 비교 | 방위각별 구역 겹쳐 보기, 영향 비교표 | pydeck, Plotly |
| 5. 영향 산정 예시 | 가상 발사일 선박별 산정표 | Streamlit dataframe |
| 6. 모델 성능 | 기준 모델 vs LightGBM 지표 표 | Streamlit |

**발표 핵심 장면:** 페이지 3에서 "같은 주 두 날짜 중 A일의 예상 영향이 B일의 절반 이하"를 지도와 함께 보여준다.

---

## 12. 저장소 구조와 개발 환경

```
oceanclear/
├─ README.md
├─ docs/
│  ├─ PROPOSAL.md               # 기획서
│  └─ DEV_PLAN.md               # 개발 계획 (이 문서)
├─ data/
│  ├─ raw/                      # 원본 (git 제외)
│  └─ processed/                # Parquet (git 제외)
├─ ingest/                      # gfw.py, gk2a.py, goci2.py, era5.py, build_grid.py
├─ features/build_features.py
├─ models/
│  ├─ forecast.py               # 모델 ① 학습·예측
│  └─ baseline.py               # 기준 모델 (같은 요일 평균)
├─ sim/
│  ├─ atmosphere.py
│  ├─ trajectory.py             # 모델 ② 궤적
│  ├─ montecarlo.py
│  └─ hazard.py                 # KDE, 등고선
├─ optimize/zone_opt.py
├─ settle/settlement.py         # 모듈 3
├─ api/main.py                  # FastAPI (선택)
├─ app/streamlit_app.py
├─ tests/
├─ requirements.txt
└─ .env.example                 # GFW_TOKEN, CDS_KEY
```

**requirements.txt (예시)**

```
pandas
numpy
pyarrow
xarray
netCDF4
duckdb
geopandas
shapely>=2
pyproj
pymap3d
scipy
numba
joblib
scikit-image
lightgbm
scikit-learn
optuna
shap
holidays
cdsapi
requests
streamlit
pydeck
plotly
fastapi
uvicorn
pytest
```

**규칙**

- API 토큰은 `.env` 에만 두고 저장소에 올리지 않는다
- `data/` 폴더는 `.gitignore` 에 추가 (용량 문제)
- 브랜치: `main` (배포용), 기능별 `feat/모듈이름`
- 제출 마감(2026-11-05) 전까지 저장소는 **private** 유지

---

## 13. 테스트와 검증

| 대상 | 테스트 |
|---|---|
| 격자 변환 | 같은 좌표가 항상 같은 `cell_id` 로 변환되는지 |
| 통제구역 함수 | 방위각 180°일 때 구역이 정남쪽으로 뻗는지 |
| 궤적 | 바람 0, 항력 0일 때 해석해(포물선)와 오차 1% 이내 |
| 몬테카를로 | 실행 횟수 증가 시 등고선 면적 수렴 |
| 예측 모델 | 시험 기간에서 기준 모델보다 순위 상관이 높은지 |
| 산정 | 조업이 없는 선박은 손실 0이 나오는지 |

---

## 14. 역할 분담

| 역할 | 담당 모듈 | 산출물 |
|---|---|---|
| A. 데이터 엔지니어 | 4장 수집, 5장 저장, 격자 통일 | Parquet 데이터셋, `grid_cell` |
| B. 예측 모델 | 6장 모델 ①, 9장 영향 산정 | 학습된 모델, 성능 비교표 |
| C. 시뮬레이션 | 7장 모델 ②, 8장 최적화 | 확률 등고선, 최적 조합 결과 |
| D. 화면·기획 | 11장 화면, 배포, 발표, 인터뷰 | Streamlit 앱, 발표 자료 |

가장 불확실성이 큰 C(시뮬레이션)를 가장 먼저 시작한다.

---

## 15. 마일스톤

| 마일스톤 | 완료 기준 | 목표일 |
|---|---|---|
| M1 데이터 확보 | 대상 해역 3년치 조업 데이터 Parquet 저장, 격자 통일 | 2026-10-04 |
| M2 기본 데모 | 조업 지도 + 기준 모델 발사일 순위 화면 작동 | 2026-10-11 |
| M3 모델 완성 | 모델 ① 시험 성능 확보, 모델 ② 등고선 생성 | 2026-10-18 |
| M4 통합 | 최적화, 구역 비교, 산정 예시까지 화면 연결, 배포 | 2026-10-25 |
| M5 제출 | 제안서에 데모 화면·성능 수치 반영, 최종 제출 | 2026-11-05 |

---

## 16. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| GFW 데이터가 연안을 충분히 못 잡음 | SAR 탐지 병행, 데모 범위를 조업 밀집 해역 중심으로 조정 |
| 발사체 제원 비공개 | 공개 수준 가정값 사용, 민감도 분석(β, 분리 속도 ±)을 함께 제시 |
| ERA5 다운로드 지연 | 발사 후보 월만 먼저 요청, 요청은 초기에 미리 걸어두기 |
| 예측 모델이 기준 모델보다 나아지지 않음 | 특징 점검 후에도 안 되면 기준 모델로 데모하고 "고도화 계획"으로 제시 |
| 배포 용량 제한 | 화면용 결과만 경량 Parquet로 저장, 원본 데이터는 제외 |
