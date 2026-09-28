"""오션클리어 해커톤 데모.

실행:  streamlit run app/streamlit_app.py
화면:  ① 해역 조업 지도  ② 후보일 비교  ③ 영향근거 리포트  ④ 과거 발사일 확인
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

st.set_page_config(page_title="오션클리어 데모", page_icon="🌊", layout="wide")

INK = "#0b3a53"
ACCENT = "#1f9e89"
ZONE_COLORS = {"A": "#d1495b", "B": "#edae49", "C": "#00798c"}


@st.cache_data
def load():
    return core.load_data()


def zone_trace(z: core.Zone) -> go.Scattermap:
    lon, lat = zip(*z.polygon())
    return go.Scattermap(lon=lon, lat=lat, mode="lines", name=z.name,
                         line=dict(width=3, color=ZONE_COLORS[z.name[0]]), hoverinfo="name")


def pad_trace() -> go.Scattermap:
    return go.Scattermap(lat=[core.PAD[0]], lon=[core.PAD[1]], mode="markers+text",
                         marker=dict(size=12, color=INK), text=["나로우주센터"],
                         textposition="top right", name="발사장", hoverinfo="text")


def map_layout(fig, height=560):
    fig.update_layout(
        map=dict(style="carto-positron", center=dict(lat=34.05, lon=127.55), zoom=8.3),
        margin=dict(l=0, r=0, t=0, b=0), height=height,
        legend=dict(orientation="h", yanchor="bottom", y=0.01, x=0.01, bgcolor="rgba(255,255,255,.85)"))
    return fig


df = load()
GRID_YEARS = core.grid_years(df)
ALL_YEARS = sorted(df.year.unique().tolist())

st.title("🌊 오션클리어")
st.caption("발사운영팀이 제시한 후보 일정·통제구역을 위성 AIS 조업 패턴과 비교해, "
           "어업영향이 가장 작은 대안과 협의 근거를 만드는 데모입니다. "
           "보상액을 계산하거나 안전구역을 설계하지 않습니다.")

with st.sidebar:
    st.header("입력")
    st.markdown("**통제구역 대안**  \n발사기업·발사장이 안전성을 확인해 제시했다고 **가정한** 값입니다.")
    zone_names = [z.name for z in core.ZONES]
    picked = st.multiselect("비교할 구역", zone_names, default=zone_names[:1])
    zones = [z for z in core.ZONES if z.name in picked] or core.ZONES[:1]
    control_hours = st.slider("통제 시간(시간)", 1, 24, 4,
                              help="발사 당일 해상 통제가 유지되는 시간. 하루 조업에 이 비율을 곱해 조업기회를 근사합니다.")
    half = st.slider("기준선 범위 (연중 ±일)", 7, 30, 15)
    st.divider()
    st.caption(f"자료: Global Fishing Watch AIS 조업 추정 v4.0 · {ALL_YEARS[0]}~{ALL_YEARS[-1]} · "
               f"격자 자료 {', '.join(map(str, GRID_YEARS)) or '없음'}")

tab1, tab2, tab3, tab4 = st.tabs(["① 해역 조업 지도", "② 후보일 비교", "③ 영향근거 리포트", "④ 과거 발사일 확인"])

# ── ① 해역 조업 지도 ─────────────────────────────
with tab1:
    c1, c2 = st.columns([3, 2])
    with c1:
        months = st.multiselect("월 선택", list(range(1, 13)), default=[], format_func=lambda m: f"{m}월",
                                placeholder="전체 월")
        cells = core.cell_density(df, months=months or None)
        if cells.empty:
            st.info("격자(위경도)가 있는 자료가 없어 지도를 그릴 수 없습니다.")
        else:
            gj = core.cells_geojson(cells)
            fig = go.Figure(go.Choroplethmap(
                geojson=gj, locations=[f["id"] for f in gj["features"]], z=cells.hours_per_day,
                colorscale="Teal", marker_opacity=0.75, marker_line_width=0.3,
                colorbar=dict(title="시간/일"),
                customdata=cells[["lat", "lon", "vessels"]],
                hovertemplate="격자 %{customdata[0]:.1f}°N %{customdata[1]:.1f}°E<br>"
                              "하루 평균 %{z:.1f}시간<br>선박 %{customdata[2]}척<extra></extra>"))
            for z in zones:
                fig.add_trace(zone_trace(z))
            fig.add_trace(pad_trace())
            st.plotly_chart(map_layout(fig), width="stretch")
            st.caption(f"격자 0.1°(약 9×11km) · 하루 평균 조업시간 · 격자 자료 연도: {', '.join(map(str, GRID_YEARS))}")
    with c2:
        st.subheader("월별 조업 (구역 A 전체)")
        a = df[core.ZONES[0].mask(df)]
        idx = core.all_days(a)
        d = core.daily(a, idx)
        m = d.groupby([d.index.year, d.index.month]).hours.mean().unstack(0)
        figm = go.Figure()
        for y in m.columns:
            figm.add_trace(go.Scatter(x=[f"{i}월" for i in m.index], y=m[y], mode="lines+markers", name=str(y)))
        figm.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="하루 평균 조업시간",
                           legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(figm, width="stretch")
        yr = d.groupby(d.index.year).agg(조업시간=("hours", "sum"))
        yr["선박 수"] = a.groupby("year").mmsi.nunique()
        st.dataframe(yr.round(0).astype(int), width="stretch")
        st.caption("4년 모두 2월·7월이 적고 가을이 많습니다. 요일별 차이는 해마다 달라 기준에서 뺐습니다.")

# ── ② 후보일 비교 ──────────────────────────────
with tab2:
    st.markdown("발사운영팀이 **발사창·기상·궤도 조건을 이미 만족한다고 판단한 후보일**을 넣으면, "
                "과거 같은 시기의 조업을 기준으로 영향이 작은 순서를 보여줍니다.")
    default_dates = [pd.Timestamp("2027-02-10"), pd.Timestamp("2027-05-12"), pd.Timestamp("2027-09-15")]
    n = st.number_input("후보일 개수", 2, 6, 3)
    cols = st.columns(int(n))
    dates = []
    for i, col in enumerate(cols):
        dflt = default_dates[i] if i < len(default_dates) else default_dates[-1] + pd.Timedelta(days=7 * i)
        dates.append(col.date_input(f"후보 {i + 1}", dflt.date(), key=f"d{i}"))
    res = core.compare(df, dates, zones, control_hours=control_hours, half=half)
    st.session_state["compare"] = res
    best = res.iloc[0]
    worst = res.iloc[-1]
    k1, k2, k3 = st.columns(3)
    k1.metric(f"영향이 가장 작은 조합 ({best['통제구역'][:1]}구역)", f"{best['후보일']}")
    diff = best["예상 조업기회(시간, 중앙값)"] - worst["예상 조업기회(시간, 중앙값)"]
    k2.metric("예상 조업기회", f"{best['예상 조업기회(시간, 중앙값)']:.0f}시간",
              f"{diff:.0f}시간 (가장 큰 조합 대비)", delta_color="inverse")
    k3.metric("하루 조업 선박(중앙값)", f"{best['하루 조업 선박(중앙값)']:.0f}척")
    figc = go.Figure()
    for zn in res["통제구역"].unique():
        r = res[res["통제구역"] == zn].sort_values("후보일")
        figc.add_trace(go.Bar(
            x=r["후보일"].astype(str), y=r["예상 조업기회(시간, 중앙값)"], name=zn,
            marker_color=ZONE_COLORS[zn[0]],
            error_y=dict(type="data", symmetric=False,
                         array=(r["많은 날(P75)"] - r["예상 조업기회(시간, 중앙값)"]).clip(lower=0))))
    figc.update_layout(barmode="group", height=360, margin=dict(l=0, r=0, t=10, b=0),
                       yaxis_title=f"통제 {control_hours}시간 중 예상 조업기회(시간)",
                       legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(figc, width="stretch")
    st.dataframe(res, width="stretch", hide_index=True)
    yrs = res.attrs.get("years", [])
    note = f"기준 자료: {', '.join(map(str, yrs))}년, 연중 ±{half}일. 막대 위 선은 조업이 많은 날(P75)."
    if len(yrs) < len(ALL_YEARS):
        note += " 구역 B·C는 격자 자료가 있는 연도만 쓸 수 있어, 비교를 공정하게 하려고 A도 같은 연도로 계산했습니다."
    st.caption(note + " 기상은 반영하지 않았습니다(발사 7일 전 예보로 재확인 필요).")

# ── ③ 영향근거 리포트 ───────────────────────────
with tab3:
    res = st.session_state.get("compare")
    if res is None or res.empty:
        st.info("② 후보일 비교를 먼저 확인하세요.")
    else:
        opts = [f"{r['후보일']} · {r['통제구역']}" for _, r in res.iterrows()]
        pick = st.selectbox("리포트를 만들 조합", opts)
        dt, zn = pick.split(" · ", 1)
        zone = next(z for z in core.ZONES if z.name == zn)
        b = core.baseline(df, zone, dt, half, control_hours, years=res.attrs.get("years"))
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(f"예상 조업기회 (많은 날 {b['exposed_hours_p75']:.0f})", f"{b['exposed_hours']:.0f}시간")
        k2.metric(f"하루 조업 선박 (많은 날 {b['vessels_p75']:.0f})", f"{b['vessels_median']:.0f}척")
        k3.metric("정기 조업 선박", f"{len(b['regular_vessels'])}척")
        k4.metric("조업 없는 날", f"{b['zero_day_share'] * 100:.0f}%")
        c1, c2 = st.columns([2, 3])
        with c1:
            st.subheader("어구 구성")
            g = b["gear_share"].head(6)
            figg = go.Figure(go.Bar(x=g.values[::-1], y=g.index[::-1], orientation="h", marker_color=ACCENT))
            figg.update_layout(height=280, margin=dict(l=0, r=0, t=0, b=0), xaxis_title="조업시간 비중(%)")
            st.plotly_chart(figg, width="stretch")
        with c2:
            st.subheader("정기 조업 선박")
            rv = b["regular_vessels"].rename(columns={
                "vessel": "선박명", "flag": "선적", "gear_ko": "어구", "years": "조업 연도 수",
                "hours_per_year": "연평균 조업시간", "days": "조업일 합계"})
            st.dataframe(rv[["선박명", "선적", "어구", "조업 연도 수", "연평균 조업시간", "조업일 합계"]].round(1),
                         width="stretch", hide_index=True, height=280)
        md = core.report_markdown(b)
        with st.expander("리포트 미리보기", expanded=False):
            st.markdown(md)
        d1, d2 = st.columns(2)
        d1.download_button("리포트 내려받기 (.md)", md, file_name=f"oceanclear_report_{dt}.md")
        d2.download_button("선박 목록 내려받기 (.csv)", rv.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"oceanclear_vessels_{dt}.csv")
        st.warning("이 리포트는 보상액이 아니라 **영향 규모와 근거**입니다. 통제로 줄어든 조업이 모두 손실은 아니며, "
                   "AIS 미탑재 소형 어선은 포함되지 않습니다.")

# ── ④ 과거 발사일 확인 ──────────────────────────
with tab4:
    st.markdown("실제 누리호 발사일의 조업을 **다른 해 같은 시기**와 비교했습니다 (구역 A, 일 단위 UTC).")
    lc = core.launch_check(df, core.ZONES[0], half)
    st.dataframe(lc, width="stretch", hide_index=True)
    name = st.selectbox("발사 선택", list(core.LAUNCHES))
    t = pd.Timestamp(core.LAUNCHES[name])
    a = df[core.ZONES[0].mask(df)]
    idx = core.all_days(a)
    d = core.daily(a, idx)
    rng = pd.date_range(t - pd.Timedelta(days=20), t + pd.Timedelta(days=20))
    ref = []
    for day in rng:
        w = core.window_days(idx, day, 3, exclude_year=t.year)
        ref.append(d.loc[w].hours.quantile([.25, .5, .75]).values)
    ref = pd.DataFrame(ref, index=rng, columns=["p25", "p50", "p75"])
    figl = go.Figure()
    figl.add_trace(go.Scatter(x=rng, y=ref.p75, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    figl.add_trace(go.Scatter(x=rng, y=ref.p25, fill="tonexty", fillcolor="rgba(31,158,137,.18)",
                              line=dict(width=0), name="다른 해 같은 시기 (P25~P75)"))
    figl.add_trace(go.Scatter(x=rng, y=ref.p50, line=dict(color=ACCENT, dash="dot"), name="다른 해 중앙값"))
    figl.add_trace(go.Scatter(x=rng, y=d.reindex(rng).hours, line=dict(color=INK, width=2), name=f"{t.year}년 실제"))
    figl.add_vline(x=t, line_color="#d1495b", line_dash="dash")
    figl.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="하루 조업시간",
                       legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(figl, width="stretch")
    st.info("일 단위 자료로는 몇 시간짜리 통제의 효과가 뚜렷하게 보이지 않습니다(3차만 낮은 편, 2차는 오히려 높음). "
            "그래서 오션클리어는 '측정된 손실'이 아니라 '통제 시간대에 노출되는 조업 규모'를 제시합니다. "
            "직접 측정은 시간 단위 항적(V-Pass 등) 연계 후 가능합니다.")
