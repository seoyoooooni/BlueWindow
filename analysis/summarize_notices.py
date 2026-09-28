"""항행경보 통제 이벤트 집계 → analysis/results_notices.md"""
import pandas as pd
from shapely import wkt
from shapely.geometry import box
ev = pd.read_csv("data/notices/events.csv", dtype={"date": str})
ev["area_hours"] = ev.area_km2 * ev.hours
order = ["군 사격", "해경 사격", "해상훈련", "해상작업", "국내 우주발사", "해외 발사 낙하구역", "기타"]
cnt = pd.crosstab(ev.year, ev.kind).reindex(columns=order, fill_value=0); cnt["합계"] = cnt.sum(1)
hrs = ev.pivot_table(index="year", columns="kind", values="hours", aggfunc="sum").reindex(columns=order).fillna(0).round(0).astype(int); hrs["합계"] = hrs.sum(1)
naro = box(127.40, 33.70, 127.66, 34.40)
g = ev.wkt.apply(wkt.loads)
nb = ev[g.apply(lambda x: x.intersects(naro))]
ncnt = pd.crosstab(nb.year, nb.kind).reindex(columns=order, fill_value=0).loc[:, lambda d: d.sum() > 0]
nhrs = nb.pivot_table(index="year", columns="kind", values="hours", aggfunc="sum").fillna(0).round(0).astype(int)
nb_days = nb.groupby("year").date.nunique()
launch = ev[ev.kind == "국내 우주발사"].groupby("doc_num").agg(제목=("title", "first"), 날짜=("date", lambda s: ",".join(sorted(set(s)))), 구역수=("name", "size"))
md = f"""# 항행경보 해상 통제 분석 (2021~2025)

데이터: 국립해양조사원 항행경보 상황판(khoa.go.kr/nwb) 문서 {ev.doc_id.nunique():,}건의 구역·일시
이벤트 정의: 통제구역(폴리곤) × 날짜 × 시간대. 같은 구역·날짜·시작시각 중복은 하나로. 제목에 '취소'가 있는 문서 제외.
주의: **공지 기준**이다. 연기돼 실제로 통제하지 않은 날(예: 누리호 2차 6/15·6/16)도 포함될 수 있다. 사격 구역은 공지된 최대 범위다.
재현: `python analysis/parse_notices.py && python analysis/summarize_notices.py`

## 1. 전국 연도별 통제 이벤트 수
{cnt.to_markdown()}

## 2. 전국 연도별 통제 시간 합계 (구역별 시간 합, 시간)
{hrs.to_markdown()}

## 3. 나로 해역(가정 통제구역 24×78km)과 겹치는 통제
{ncnt.to_markdown()}

통제 시간 합계:
{nhrs.to_markdown()}

통제가 있었던 날 수: {", ".join(f"{y}년 {d}일" for y, d in nb_days.items())}

## 4. 국내 우주발사 관련 항행경보
{launch.to_markdown()}

## 해석
- 전국에서 해마다 약 {int(cnt['합계'].min()):,}~{int(cnt['합계'].max()):,}건의 해상 통제가 공지된다. 대부분이 군 사격훈련이다.
- 같은 나로 해역만 봐도 우주발사는 연 1~2회지만, 군 사격·해상훈련 통제는 2023년 이후 해마다 200건 이상 겹친다.
- 따라서 어민 입장에서 '바다가 막히는 일'은 발사보다 사격훈련이 훨씬 잦다. 같은 엔진으로 모든 통제의 어업 영향을 계산하면 분석 건수가 연 수천 건 단위가 된다.
- 누리호 발사장 앞 실제 해상통제구역 좌표를 확보했다(`data/nuri_control_zone_notice.geojson`, 약 1,719km²). 기존 가정 구역(1,869km²)을 대체할 수 있다.
"""
open("analysis/results_notices.md", "w").write(md)
print(md)
