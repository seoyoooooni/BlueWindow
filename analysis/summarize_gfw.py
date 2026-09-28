"""GFW ACTIVE VESSELS(daily) CSV 요약: data/<연도>/*.csv 를 모두 읽어 연도·월·요일·어구별 집계."""
import glob, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / "data"
H = "Apparent Fishing Hours"
files = sorted(glob.glob(str(ROOT / "*" / "public-global-fishing-effort*.csv")))
d = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
d["date"] = pd.to_datetime(d["Time Range"])
d["year"] = d.date.dt.year
print("files:", len(files), "| rows:", len(d))
y = d.groupby("year").agg(hours=(H, "sum"), vessels=("MMSI", "nunique"))
days = d.groupby(["year", "date"])[H].sum().groupby("year").mean()
y["daily_mean_hours(active days)"] = days
print("\n[연도별]\n", y.round(0))
print("\n[월별 합계]\n", d.pivot_table(index=d.date.dt.month, columns="year", values=H, aggfunc="sum").round(0))
print("\n[요일별 합계, 0=월]\n", d.pivot_table(index=d.date.dt.dayofweek, columns="year", values=H, aggfunc="sum").round(0))
g = d.groupby("Gear Type").agg(hours=(H, "sum"), vessels=("MMSI", "nunique")).sort_values("hours", ascending=False)
g["share%"] = (g.hours / g.hours.sum() * 100).round(1)
print("\n[어구별]\n", g.round(0).head(10))
print("\n[선적별 척수]\n", d.groupby("Flag").MMSI.nunique())
