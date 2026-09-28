"""블루윈도우 데모 계산 로직 (화면과 분리해 테스트 가능하게 둠).

데이터: data/<연도>/public-global-fishing-effort*.csv
  (GFW 지도 ACTIVE VESSELS 다운로드, 일 단위, 0.1° 격자, 선박별)
"""
from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CELL = 0.1  # GFW 저해상도 격자 크기(도)
PAD = (34.43, 127.53)  # 나로우주센터 근사 좌표 (lat, lon)

# 과거 누리호 발사 (UTC 날짜 기준. 4차는 KST 11-27 새벽 → UTC 11-26)
LAUNCHES = {
    "누리호 2차 (2022-06-21 16:00 KST)": "2022-06-21",
    "누리호 3차 (2023-05-25 18:25 KST)": "2023-05-25",
    "누리호 4차 (2025-11-27 새벽 KST)": "2025-11-26",
}

GEAR_KO = {
    "TRAWLERS": "트롤(끌그물)",
    "SET_GILLNETS": "고정자망",
    "FISHING": "어선(어구 미분류)",
    "FIXED_GEAR": "고정어구",
    "SET_LONGLINES": "연승(주낙)",
    "OTHER_PURSE_SEINES": "기타 선망",
    "POLE_AND_LINE": "채낚기",
    "SEINERS": "선망",
    "PURSE_SEINES": "선망(건착)",
    "INCONCLUSIVE": "판별 불가",
}


@dataclass(frozen=True)
class Zone:
    """발사기업·발사장이 안전성을 확인해 제시한 통제구역 대안(여기서는 가정값)."""
    name: str
    full: bool  # True면 GFW에 올린 다각형 전체 (격자 없는 합계 자료도 포함)
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    def polygon(self):
        return [
            (self.lon_min, self.lat_max), (self.lon_max, self.lat_max),
            (self.lon_max, self.lat_min), (self.lon_min, self.lat_min),
            (self.lon_min, self.lat_max),
        ]

    def mask(self, df: pd.DataFrame) -> pd.Series:
        if self.full:
            return pd.Series(True, index=df.index)
        # 격자 중심이 구역 안(경계 반 칸 여유)에 있는 칸만 포함. 격자 없는 합계 자료는 제외
        h = CELL / 2
        return (
            df.lat.between(self.lat_min - h + 1e-6, self.lat_max + h - 1e-6)
            & df.lon.between(self.lon_min - h + 1e-6, self.lon_max + h - 1e-6)
        )


# 가정 대안: 모두 '안전성이 확인됐다'고 가정한 입력값이며 블루윈도우가 설계한 구역이 아님
ZONES = [
    Zone("A. 기본 통제구역 (24×78km)", True, 33.70, 34.40, 127.40, 127.66),
    Zone("B. 북쪽 연안 제외 대안", False, 33.70, 34.15, 127.40, 127.66),
    Zone("C. 남쪽 축소 대안", False, 33.85, 34.40, 127.40, 127.66),
]


def load_data(data_dir: Path = DATA_DIR, fishing_only: bool = False) -> pd.DataFrame:
    """fishing_only: GFW 선박 유형이 FISHING인 배만 사용할지 여부 (기본 False).
    주의: 다운로드 방식에 따라 같은 배의 선박 유형·어구 분류가 다르게 붙어 나옴
    (2022 파일은 세부 어구, 2023~2025 파일은 '미분류·비어선'이 많음). 유형으로 거르면
    연도 간 비교가 오히려 틀어지므로 기본은 전체 합계(GFW 화면 수치와 일치)를 쓴다.
    선박 분류 통일은 GFW Vessels API로 MMSI별 재조회해 해결할 예정 (DEV_PLAN 4-4)."""
    files = sorted(glob.glob(str(data_dir / "*" / "public-global-fishing-effort*.csv")))
    if not files:
        raise FileNotFoundError(f"{data_dir}/<연도>/ 아래 GFW CSV가 없습니다")
    frames = []
    for f in files:
        part = pd.read_csv(f)
        tr = part["Time Range"].astype(str)
        if not tr.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
            raise ValueError(
                f"{f}: 날짜가 일 단위가 아닙니다 (예: {tr.iloc[0]}). "
                "GFW 다운로드에서 GROUP TIME BY를 DAY로 선택해 다시 받아주세요.")
        frames.append(part)
    raw = pd.concat(frames, ignore_index=True)
    df = pd.DataFrame({
        "lat": raw["Lat"].round(2) if "Lat" in raw else float("nan"),
        "lon": raw["Lon"].round(2) if "Lon" in raw else float("nan"),
        "date": pd.to_datetime(raw["Time Range"]),
        "flag": raw["Flag"].fillna("?"),
        "vessel": raw["Vessel Name"].fillna("(이름 없음)"),
        "gear": raw["Gear Type"].fillna("INCONCLUSIVE"),
        "mmsi": raw["MMSI"].astype("Int64").astype(str),
        "hours": raw["Apparent Fishing Hours"].astype(float),
        "vtype": raw["Vessel Type"].fillna("?"),
    })
    df = df[df.hours.notna()]
    if fishing_only:
        df = df[df.vtype == "FISHING"]
    df = df.copy()
    df["gear_ko"] = df.gear.map(GEAR_KO).fillna(df.gear)
    df["year"] = df.date.dt.year
    df["month"] = df.date.dt.month
    return df


def all_days(df: pd.DataFrame, years=None) -> pd.DatetimeIndex:
    years = sorted(years if years is not None else df.year.unique())
    idx = pd.date_range(f"{min(years)}-01-01", f"{max(years)}-12-31")
    return idx[idx.year.isin(years)]


def grid_years(df: pd.DataFrame) -> list[int]:
    """격자(위경도)가 있는 연도. 구역 대안 비교와 지도는 이 연도만 가능."""
    return sorted(df.loc[df.lat.notna(), "year"].unique().tolist())


def usable_years(df: pd.DataFrame, zones) -> list[int]:
    """선택한 구역들을 같은 조건으로 비교할 수 있는 연도."""
    if all(z.full for z in zones):
        return sorted(df.year.unique().tolist())
    return grid_years(df)


def daily(df: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """조업이 없는 날도 0으로 채운 일별 조업시간·선박 수."""
    g = df.groupby("date").agg(hours=("hours", "sum"), vessels=("mmsi", "nunique"))
    return g.reindex(idx, fill_value=0)


def _doy_distance(idx: pd.DatetimeIndex, target: pd.Timestamp) -> pd.Series:
    d = (idx.dayofyear - target.dayofyear) % 365
    return pd.Series(pd.Series(d).where(d <= 182, 365 - d).values, index=idx)


def window_days(idx: pd.DatetimeIndex, target: pd.Timestamp, half: int = 15,
                exclude_year: int | None = None) -> pd.DatetimeIndex:
    dist = _doy_distance(idx, target)
    keep = dist <= half
    if exclude_year is not None:
        keep &= idx.year != exclude_year
    return idx[keep.values]


def baseline(df: pd.DataFrame, zone: Zone, target, half: int = 15,
             control_hours: float = 24.0, exclude_year: int | None = None,
             years=None) -> dict:
    """후보일과 같은 시기(연중 ±half일, 과거 모든 해)의 조업을 기준선으로 요약."""
    target = pd.Timestamp(target)
    years = years if years is not None else usable_years(df, [zone])
    df = df[df.year.isin(years)]
    idx = all_days(df, years)
    z = df[zone.mask(df)]
    days = window_days(idx, target, half, exclude_year)
    d = daily(z, idx).loc[days]
    zw = z[z.date.isin(days)]
    n_years = zw.year.nunique() or 1
    # 정기 조업 선박: 같은 시기에 2개 연도 이상(자료가 1년뿐이면 1년) 이 구역에서 조업한 배
    min_years = 2 if len(years) >= 2 else 1
    per_v = zw.groupby(["mmsi", "vessel", "flag", "gear_ko"]).agg(
        years=("year", "nunique"), hours=("hours", "sum"), days=("date", "nunique"))
    per_v["hours_per_year"] = per_v.hours / n_years
    regular = per_v[per_v.years >= min_years].sort_values("hours_per_year", ascending=False).reset_index()
    frac = control_hours / 24.0
    gear = (zw.groupby("gear_ko").hours.sum() / max(zw.hours.sum(), 1e-9) * 100).sort_values(ascending=False)
    return {
        "date": target,
        "zone": zone.name,
        "years": list(years),
        "n_days": len(days),
        "hours_median": float(d.hours.median()),
        "hours_p25": float(d.hours.quantile(0.25)),
        "hours_p75": float(d.hours.quantile(0.75)),
        "vessels_median": float(d.vessels.median()),
        "vessels_p75": float(d.vessels.quantile(0.75)),
        "zero_day_share": float((d.hours == 0).mean()),
        "control_hours": control_hours,
        "exposed_hours": float(d.hours.median() * frac),
        "exposed_hours_p75": float(d.hours.quantile(0.75) * frac),
        "regular_vessels": regular,
        "min_years": min_years,
        "gear_share": gear,
        "daily": d,
    }


def compare(df: pd.DataFrame, dates, zones, control_hours: float = 24.0, half: int = 15) -> pd.DataFrame:
    rows = []
    years = usable_years(df, zones)
    for dt in dates:
        for zn in zones:
            b = baseline(df, zn, dt, half, control_hours, years=years)
            rows.append({
                "후보일": pd.Timestamp(dt).date(),
                "통제구역": zn.name,
                "예상 조업기회(시간, 중앙값)": round(b["exposed_hours"], 1),
                "많은 날(P75)": round(b["exposed_hours_p75"], 1),
                "하루 조업 선박(중앙값)": round(b["vessels_median"], 1),
                "정기 조업 선박(척)": len(b["regular_vessels"]),
                "조업 없는 날 비율": f"{b['zero_day_share']*100:.0f}%",
            })
    out = pd.DataFrame(rows)
    out["순위"] = out["예상 조업기회(시간, 중앙값)"].rank(method="min").astype(int)
    out = out.sort_values(["순위", "많은 날(P75)"]).reset_index(drop=True)
    out.attrs["years"] = years
    return out


def cell_density(df: pd.DataFrame, months=None, years=None) -> pd.DataFrame:
    """격자별 하루 평균 조업시간 (선택 기간 전체 일수로 나눔)."""
    sub = df[df.lat.notna()]
    idx = all_days(sub)
    if months:
        sub = sub[sub.month.isin(months)]
        idx = idx[idx.month.isin(months)]
    if years:
        sub = sub[sub.year.isin(years)]
        idx = idx[idx.year.isin(years)]
    g = sub.groupby(["lat", "lon"]).agg(hours=("hours", "sum"), vessels=("mmsi", "nunique")).reset_index()
    g["hours_per_day"] = g.hours / max(len(idx), 1)
    return g


def cells_geojson(cells: pd.DataFrame) -> dict:
    h = CELL / 2
    feats = []
    for i, r in cells.iterrows():
        la, lo = r.lat, r.lon
        feats.append({
            "type": "Feature", "id": str(i),
            "geometry": {"type": "Polygon", "coordinates": [[
                [lo - h, la - h], [lo + h, la - h], [lo + h, la + h], [lo - h, la + h], [lo - h, la - h]]]},
            "properties": {},
        })
    return {"type": "FeatureCollection", "features": feats}


def launch_check(df: pd.DataFrame, zone: Zone, half: int = 15) -> pd.DataFrame:
    """과거 발사일 조업을 다른 해 같은 시기와 비교 (자연실험, 일 단위라 한계 큼)."""
    years = usable_years(df, [zone])
    df = df[df.year.isin(years)]
    idx = all_days(df, years)
    d = daily(df[zone.mask(df)], idx)
    rows = []
    for name, day in LAUNCHES.items():
        t = pd.Timestamp(day)
        if t not in d.index:
            continue
        ref = d.loc[window_days(idx, t, half, exclude_year=t.year)].hours
        rows.append({
            "발사": name,
            "발사일(UTC) 조업시간": round(d.loc[t, "hours"]),
            "다른 해 같은 시기 중앙값": round(ref.median()),
            "P25~P75": f"{ref.quantile(.25):.0f}~{ref.quantile(.75):.0f}",
            "백분위": int(round((ref < d.loc[t, "hours"]).mean() * 100)),
        })
    return pd.DataFrame(rows)


def report_markdown(b: dict) -> str:
    rv = b["regular_vessels"]
    gear = "\n".join(f"- {k}: {v:.0f}%" for k, v in b["gear_share"].head(5).items())
    top = "\n".join(
        f"| {r.vessel} | {r.flag} | {r.gear_ko} | {r.years} | {r.hours_per_year:.1f} |"
        for r in rv.head(15).itertuples())
    return f"""# 블루윈도우 영향근거 리포트

- 후보일: {b['date'].date()}
- 통제구역: {b['zone']}
- 기준 자료 연도: {', '.join(map(str, b['years']))}
- 통제 시간(입력): {b['control_hours']:.0f}시간

## 1. 예상 영향 규모 (과거 같은 시기 ±15일 기준)
- 통제 시간 중 예상 조업기회: 약 {b['exposed_hours']:.0f}시간 (많은 날 {b['exposed_hours_p75']:.0f}시간)
- 하루 조업 선박: 중앙값 {b['vessels_median']:.0f}척 (많은 날 {b['vessels_p75']:.0f}척)
- 이 시기 이 구역에서 {b['min_years']}개 연도 이상 조업한 정기 조업 선박: {len(rv)}척
- 조업이 전혀 없던 날 비율: {b['zero_day_share']*100:.0f}%

## 2. 어구 구성 (조업시간 비중)
{gear}

## 3. 정기 조업 선박 (상위 15척)
| 선박명 | 선적 | 어구 | 조업 연도 수 | 연평균 조업시간 |
|---|---|---|---|---|
{top}

## 4. 이 리포트가 말하지 않는 것
- 보상액을 계산하지 않습니다. 최종 보상은 민간발사안전통제협의회 등 기존 협의 절차에서 결정합니다.
- 조업기회 = 과거 같은 시기 하루 조업시간 × (통제 시간 ÷ 24). 하루 중 조업이 고르게 분포한다고 가정한 근사치입니다.
- 통제로 줄어든 조업이 모두 손실은 아닙니다. 어민은 다른 시간·해역에서 조업할 수 있습니다.
- 통제구역은 발사기업·발사장이 제시한 값을 그대로 씁니다. 블루윈도우는 안전구역을 설계·인증하지 않습니다.

## 5. 데이터와 한계
- Global Fishing Watch 위성 AIS 조업 추정(public-global-fishing-effort v4.0), 0.1° 격자, 일 단위, 비상업 연구용 이용.
- AIS를 달지 않은 소형 연안어선은 빠져 있습니다 (V-Pass 연계로 보완 예정).
- 기상은 반영하지 않았습니다. 발사 7일 전 기상 예보로 재확인이 필요합니다.
"""
