"""국립해양조사원 항행경보(khoa.go.kr/nwb) 상세 자료 → 통제 이벤트 표.
이벤트 = 구역(폴리곤) × 날짜 × 시간대. 입력: data/notices/detail/*.json
출력: data/notices/events.csv (+ events.geojson)
"""
import json, glob, re, math
import pandas as pd
from shapely.geometry import Polygon, Point, mapping
from shapely.ops import transform
from pyproj import Transformer

DMS = re.compile(r"(\d{1,3})-(\d{1,2}(?:\.\d+)?)(?:-(\d{1,2}(?:\.\d+)?))?\s*([NSEW])")
def dms(m):
    d, mi, s, h = m.groups()
    v = float(d) + float(mi)/60 + (float(s)/3600 if s else 0)
    return -v if h in "SW" else v

def parse_points(pos):
    vals = [dms(m) for m in DMS.finditer(pos or "")]
    pts = []
    for i in range(0, len(vals) - 1, 2):
        lat, lon = vals[i], vals[i+1]
        pts.append((lon, lat))
    return pts

to_m = Transformer.from_crs(4326, 5179, always_xy=True).transform
to_ll = Transformer.from_crs(5179, 4326, always_xy=True).transform

def geom(r):
    pts = parse_points(r.get("POSITION"))
    if not pts: return None
    if len(pts) >= 3:
        g = Polygon(pts)
        return g if g.is_valid else g.buffer(0)
    rad = r.get("RADIUS")
    if rad:
        try: rad = float(rad)
        except: return None
        unit = (r.get("UNIT_LENGTH") or "NM").upper()
        meters = rad * (1852 if unit == "NM" else 1000 if unit == "KM" else 1)
        return transform(to_ll, transform(to_m, Point(pts[0])).buffer(meters))
    return None  # 점 경보(반경 없음)는 통제구역 아님

def hours(slot):
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*~\s*(\d{1,2}):(\d{2})", slot or "")
    if not m: return None, None, None
    a = int(m[1]) + int(m[2])/60; b = int(m[3]) + int(m[4])/60
    if b <= a: b += 24
    return m[1]+":"+m[2], m[3]+":"+m[4], b - a

def kind(r):
    t = r.get("TITLE_KR") or ""
    if "전투기" in t or "무장" in t: return "군 사격"
    if "중국" in t and "발사" in t: return "해외 발사 낙하구역"
    if "누리호" in t or "발사체" in t: return "국내 우주발사"
    c = r.get("CODE_NM_KR")
    if c == "해상사격": return "해경 사격" if "해경" in t else "군 사격"
    if c == "해상훈련": return "해상훈련"
    if c == "해상작업": return "해상작업"
    return "기타"

rows = []
for f in glob.glob("data/notices/detail/*.json"):
    for r in json.load(open(f)).get("RESULT_DATA") or []:
        title = r.get("TITLE_KR") or ""
        if "취소" in title: continue
        g = geom(r)
        if g is None or g.is_empty: continue
        area = transform(to_m, g).area / 1e6
        dates = (r.get("ALARM_DATE") or "").split(",")
        slots = (r.get("ALARM_TIME_DETAIL") or "").split(",")
        for i, d in enumerate(dates):
            d = d.strip()
            if not re.fullmatch(r"\d{8}", d): continue
            s, e, h = hours(slots[i] if i < len(slots) else "")
            rows.append(dict(doc_id=r["DOC_M_ID"], doc_num=r.get("DOC_NUM"), title=title.strip(),
                             kind=kind(r), app_cat=r.get("APP_CAT"), region=(r.get("POSITION_NM") or "").split("~")[0].strip(),
                             name=r.get("POSITION_NM"), date=d, start=s, end=e, hours=h,
                             area_km2=round(area, 1), wkt=g.wkt))
ev = pd.DataFrame(rows)
ev["key"] = ev.wkt.str.slice(0, 200) + ev.date + ev.start.fillna("")
before = len(ev)
ev = ev.sort_values("doc_id").drop_duplicates("key", keep="last").drop(columns="key")
ev["year"] = ev.date.str[:4].astype(int)
ev = ev[ev.year.between(2021, 2025)]
ev.to_csv("data/notices/events.csv", index=False)
print("rows", before, "-> unique events", len(ev))

# 누리호 실제 해상통제구역(발사장 앞바다 '남해 동부') GeoJSON 저장
import json as _j
from shapely import wkt as _w
nuri = ev[(ev.kind=="국내 우주발사") & ev.title.str.contains("누리호") & (ev.name=="남해안 ~ 남해 동부")]
if len(nuri):
    g = _w.loads(nuri.iloc[-1].wkt)
    _j.dump({"type":"FeatureCollection","features":[{"type":"Feature","properties":{"name":"누리호 해상통제구역(항행경보 "+nuri.iloc[-1].doc_num+")","area_km2":nuri.iloc[-1].area_km2},"geometry":mapping(g)}]},
            open("data/nuri_control_zone_notice.geojson","w"),ensure_ascii=False)
