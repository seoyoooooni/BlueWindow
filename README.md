# 🌊 오션클리어 (OceanClear)

> **위성 선박 데이터 기반 우주발사장 해역 상생 관리 플랫폼**
>
> 로켓 발사로 생기는 해상 통제가 어업에 주는 영향을 위성 선박 데이터로 계산해, 발사안전구역 설계·발사일 선정·어업 보상 산정을 한 번에 지원합니다.

2026 스페이스 해커톤 · 부문 2. 위성활용 비즈니스 모델 (위성기반 서비스 모델)

**키워드:** `위성 AIS` `SAR 선박 탐지` `발사안전구역` `어업 피해 보상` `민간 우주발사` `해양 공간 갈등`

---

## 📄 문서

| 문서 | 내용 |
|---|---|
| [기획서](docs/PROPOSAL.md) | 창의성, 기획력, 사업성, 실현가능성, 지속가능성, 기대 효과, 추진 일정, 참고 문헌 |
| [개발 계획](docs/DEV_PLAN.md) | 아키텍처, 기술 스택, 데이터 수집·스키마, 예측 모델, 낙하 분산 모델, 최적화, API, 화면, 테스트, 역할, 마일스톤 |

---

## 왜 필요한가

2026년 발사와 바다에 관한 규제가 두 번 새로 생겼습니다.

- **우주개발 진흥법 개정** (2027.02 시행): 발사안전구역을 **필요 최소 범위**로 지정하고, 구역 안 해상구조물은 사전 협의
- **나로우주센터 민간 활용 가이드라인** (2026.06): 민간 발사기업이 **어업 피해 보상** 책임 부담

의무는 생겼지만, 발사가 바다에 주는 영향을 객관적으로 측정할 도구는 국내외 어디에도 없습니다. → [자세히 보기](docs/PROPOSAL.md#2-기획력-planning--design)

---

## 핵심 기능

| 모듈 | 하는 일 | 핵심 기술 |
|---|---|---|
| 0. 해역 데이터 엔진 | 해역 격자별·요일·계절별 조업 밀도 지도 | Global Fishing Watch 위성 AIS·SAR |
| 1. 안전구역 설계 | 안전 기준은 같고 어업 영향이 가장 적은 구역 경계 탐색 | 낙하물 몬테카를로 분산 모델 |
| 2. 발사일 추천 | 후보 날짜별 예상 영향 조업량 순위 | LightGBM 조업량 예측 모델 |
| 3. 영향 산정 | 발사로 줄어든 조업을 선박별로 산정 | 반사실 예측 + 이중차분 |

---

## 기술 스택

`Python 3.11` `DuckDB` `PostgreSQL/PostGIS` `GeoPandas` `LightGBM` `Optuna` `SHAP` `SciPy` `Numba` `FastAPI` `Streamlit` `pydeck`

```
[수집]  GFW API · GK2A · GOCI-II · ERA5 · 기상청
   ↓
[저장]  Parquet + DuckDB (해커톤) / PostgreSQL + PostGIS (운영)
   ↓
[분석]  ① 조업량 예측 (LightGBM)   ② 낙하 분산 (몬테카를로)
   ↓            ↘  통제구역 최적화  ↙
[화면]  Streamlit + pydeck
```

→ [개발 계획 전체 보기](docs/DEV_PLAN.md)

---

## 저장소 구조

```
oceanclear/
├─ docs/            # 기획서, 개발 계획
├─ ingest/          # 데이터 수집
├─ features/        # 특징 생성
├─ models/          # 모델 ① 조업량 예측
├─ sim/             # 모델 ② 낙하 분산
├─ optimize/        # 통제구역 최적화
├─ settle/          # 영향 산정
├─ app/             # Streamlit 화면
└─ tests/
```

## 실행 방법

```bash
git clone <저장소 주소>
cd oceanclear
pip install -r requirements.txt
cp .env.example .env        # GFW_TOKEN, CDS_KEY 입력
streamlit run app/streamlit_app.py
```

---

## 팀

| 이름 | 역할 |
|---|---|
| ○○○ | 데이터 엔지니어 |
| ○○○ | 예측 모델 |
| ○○○ | 시뮬레이션 |
| ○○○ | 화면·기획 |

## 생성형 AI 활용

주제 탐색, 자료 조사, 기획서·개발 계획 초안 작성에 Claude(Anthropic)를 활용했으며, 인용한 사실은 원 출처를 확인해 [참고 문헌](docs/PROPOSAL.md#9-참고-문헌)에 표기했습니다.
