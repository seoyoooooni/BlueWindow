"""9/30 발표 문서용 그림 → docs/progress/0930/img/

지도 해안선: Natural Earth 10m land (https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip)
압축을 풀고 NE_LAND 환경변수에 .shp 경로를 주거나 /tmp/ne_land/ 에 둔다.
"""
import glob, json
import pandas as pd, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon as MPoly
from shapely import wkt
from shapely.geometry import box
import geopandas as gpd
import os
from matplotlib import font_manager as fm
for _f in [os.path.expanduser("~/.fonts/NotoSansKR.ttf"), "/Library/Fonts/NotoSansKR.ttf"]:
    if os.path.exists(_f): fm.fontManager.addfont(_f)

OUT = "docs/progress/0930/img/"
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#9a9893"
INK, INK2, SURF, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e6e5e1"
plt.rcParams.update({"font.family": ["Noto Sans KR", "AppleGothic", "Noto Sans CJK JP"], "font.size": 11, "axes.edgecolor": GRID,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF,
    "axes.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 13,
    "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left"})

def bars(ax, x, y, color):
    ax.bar(x, y, color=color, width=0.62, edgecolor=SURF, linewidth=2, zorder=3)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0); ax.tick_params(length=0)

# GFW
frames = []
for f in sorted(glob.glob("data/20*/public-global-fishing-effort*.csv")):
    d = pd.read_csv(f, usecols=["Lat", "Lon", "Time Range", "Apparent Fishing Hours"])
    frames.append(d)
g = pd.concat(frames); g["date"] = pd.to_datetime(g["Time Range"])
g["y"], g["m"] = g.date.dt.year, g.date.dt.month

# 1. 월별 조업시간
mon = g.groupby(["y", "m"])["Apparent Fishing Hours"].sum().unstack(0)
med, lo, hi = mon.median(1), mon.min(1), mon.max(1)
fig, ax = plt.subplots(figsize=(8, 3.8))
bars(ax, mon.index, med, BLUE)
ax.vlines(mon.index, lo, hi, color=INK2, lw=1.2, zorder=4)
for m in (2, 7):
    ax.annotate(f"{med[m]:,.0f}", (m, hi[m]), xytext=(0, 4), textcoords="offset points", ha="center", color=INK, fontsize=10)
ax.set_xticks(range(1, 13), [f"{m}월" for m in range(1, 13)])
ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(4000)); ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
ax.set_title("나로 해역 월별 조업시간 (2022~2025 중앙값, 선은 최소~최대)")
ax.set_ylabel("조업시간 (시간)")
fig.tight_layout(); fig.savefig(OUT + "fig1_monthly.png", dpi=160); plt.close()

# 2·3. 항행경보
ev = pd.read_csv("data/notices/events.csv", dtype={"date": str})
ev = ev[ev.year.between(2022, 2025)]
tot = ev.groupby("year").size()
fig, ax = plt.subplots(figsize=(6.5, 3.6))
bars(ax, tot.index.astype(str), tot.values, BLUE)
for i, v in enumerate(tot.values): ax.text(i, v + 120, f"{v:,}", ha="center", color=INK)
ax.set_title("전국 해상 통제 공지 건수 (항행경보, 구역×날짜×시간대)")
ax.set_ylim(0, tot.max() * 1.15); ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
fig.tight_layout(); fig.savefig(OUT + "fig2_controls_national.png", dpi=160); plt.close()

naro = box(127.40, 33.70, 127.66, 34.40)
ev["geom"] = ev.wkt.apply(wkt.loads)
nb = ev[ev.geom.apply(lambda x: x.intersects(naro))]
launch = nb[nb.kind == "국내 우주발사"].groupby("year").size().reindex(range(2022, 2026), fill_value=0)
other = nb[nb.kind != "국내 우주발사"].groupby("year").size().reindex(range(2022, 2026), fill_value=0)
x = np.arange(4); w = 0.36
fig, ax = plt.subplots(figsize=(7, 3.8))
ax.bar(x - w/2 - 0.01, launch, w, color=ORANGE, edgecolor=SURF, lw=2, zorder=3, label="우주발사")
ax.bar(x + w/2 + 0.01, other, w, color=BLUE, edgecolor=SURF, lw=2, zorder=3, label="사격·해상훈련")
for i in x:
    ax.text(i - w/2, launch.iloc[i] + 6, launch.iloc[i], ha="center", color=INK)
    ax.text(i + w/2, other.iloc[i] + 6, other.iloc[i], ha="center", color=INK)
ax.set_xticks(x, [str(y) for y in range(2022, 2026)]); ax.grid(axis="y", color=GRID, zorder=0); ax.tick_params(length=0)
ax.legend(frameon=False, loc="upper left"); ax.set_ylim(0, other.max() * 1.18)
ax.set_title("나로 해역과 겹친 해상 통제 건수")
fig.tight_layout(); fig.savefig(OUT + "fig3_controls_naro.png", dpi=160); plt.close()

# 4. 지도
ext = (126.9, 128.3, 33.35, 34.75)
land = gpd.read_file(os.environ.get("NE_LAND", "/tmp/ne_land/ne_10m_land.shp"), bbox=(ext[0], ext[2], ext[1], ext[3]))
cell = g.groupby(["Lat", "Lon"])["Apparent Fishing Hours"].sum() / g.y.nunique()
fig, ax = plt.subplots(figsize=(7.2, 7.2))
ax.set_facecolor("#f1f4f7")
vmax = cell.quantile(0.95)
cmap = matplotlib.colors.LinearSegmentedColormap.from_list("b", ["#dce9f8", BLUE, "#0d3b73"])
for (la, lo_), v in cell.items():
    ax.add_patch(Rectangle((lo_ - .05, la - .05), .1, .1, color=cmap(min(v / vmax, 1)), lw=0, zorder=2))
fire = nb[nb.kind != "국내 우주발사"].drop_duplicates("wkt")
for gg in fire.geom:
    for p in getattr(gg, "geoms", [gg]):
        xs, ys = p.exterior.xy; ax.plot(xs, ys, color=INK2, lw=0.7, alpha=0.55, zorder=3)
land.plot(ax=ax, color="#e3e1da", edgecolor="#b9b7b0", lw=0.5, zorder=4)
xs, ys = naro.exterior.xy; ax.plot(xs, ys, color=INK, lw=1.4, ls="--", zorder=5)
nuri = json.load(open("data/nuri_control_zone_notice.geojson"))["features"][0]["geometry"]["coordinates"][0]
ax.add_patch(MPoly(nuri, fill=False, ec=ORANGE, lw=2.4, zorder=6))
ax.plot(127.535, 34.431, marker="^", color=ORANGE, ms=10, mec=SURF, zorder=7)
ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.set_aspect(1 / np.cos(np.radians(34)))
ax.tick_params(length=0); [s.set_visible(False) for s in ax.spines.values()]
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], color=ORANGE, lw=2.4, label="누리호 실제 해상통제구역 (항행경보)"),
    Line2D([], [], color=INK, lw=1.4, ls="--", label="지금까지 쓴 가정 구역"),
    Line2D([], [], color=INK2, lw=0.9, alpha=.6, label=f"겹치는 사격·훈련 구역 ({len(fire)}종)"),
    Rectangle((0, 0), 1, 1, color=BLUE, label="연평균 조업시간 (진할수록 많음)")],
    loc="lower left", frameon=True, facecolor=SURF, edgecolor=GRID, fontsize=9.5)
ax.set_title("나로 해역: 조업 밀도와 통제구역")
fig.tight_layout(); fig.savefig(OUT + "fig4_map.png", dpi=160); plt.close()
print("ok", len(fire), launch.to_dict(), other.to_dict())
