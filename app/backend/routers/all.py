"""
routers/all.py — semua endpoints dalam satu file.
"""
from __future__ import annotations
from typing import Any, List, Optional
import math

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

import startup as S
from engine.geo import nearest_stops, haversine
from engine.eta import hhmm_to_min, min_to_hhmm, walk_time
from engine.routing import sssp_from_origin, build_route_to_poi
from engine.recommender import recommend as _recommend, _enrich_legs
from engine.planner import plan_day

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Stops
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stops", tags=["Stops"])
def get_stops():
    """Semua halte berkoordinat untuk marker peta."""
    return [s for s in S.stops_list if s.get("lat") is not None]


@router.get("/stops/nearest", tags=["Stops"])
def get_nearest_stops(
    lat: float = Query(..., description="Latitude pengguna"),
    lon: float = Query(..., description="Longitude pengguna"),
    limit: int = Query(5, ge=1, le=20),
):
    """5 halte terdekat dari koordinat GPS pengguna."""
    return nearest_stops(lat, lon, S.stops_list, limit=limit)


@router.get("/stops/{stop_id}", tags=["Stops"])
def get_stop(stop_id: str):
    s = S.stops_by_id.get(stop_id)
    if not s:
        raise HTTPException(404, "Stop not found")
    routes = S.stop_to_route_dirs.get(stop_id, [])
    return {**s, "route_dirs": routes}


# ─────────────────────────────────────────────────────────────────────────────
# POI
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/poi", tags=["POI"])
def get_poi(type: Optional[str] = None):
    """Semua POI eligible, opsional filter per tipe."""
    data = S.poi_list
    if type:
        data = [p for p in data if p.get("type") == type]
    return data


@router.get("/poi/types", tags=["POI"])
def get_poi_types():
    """Daftar tipe wisata yang tersedia."""
    types = sorted(set(p.get("type", "") for p in S.poi_list if p.get("type")))
    counts = {t: sum(1 for p in S.poi_list if p.get("type") == t) for t in types}
    return [{"type": t, "count": counts[t]} for t in types]


@router.get("/poi/{poi_id}", tags=["POI"])
def get_poi_detail(poi_id: int):
    p = S.poi_by_id.get(poi_id)
    if not p:
        raise HTTPException(404, "POI not found")
    # Tambahkan rute yang lewat halte terdekat
    nearest_sid = p.get("nearest_stop_id")
    routes = S.stop_to_route_dirs.get(nearest_sid, []) if nearest_sid else []
    return {**p, "nearest_stop_routes": routes}


# ─────────────────────────────────────────────────────────────────────────────
# Recommend
# ─────────────────────────────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    origin_stop_id: str
    origin_walk_min: float = 0.0
    depart_hhmm: str = "09:00"
    weekday: str = "Sabtu"
    filters: dict = {}
    limit: int = 15

    @field_validator("depart_hhmm")
    @classmethod
    def validate_hour(cls, v: str) -> str:
        try:
            h = int(v.split(":")[0])
        except Exception:
            raise ValueError("Format hhmm tidak valid")
        if h < 5 or h > 20:
            raise ValueError("Trans Jogja beroperasi 05:30–20:30")
        return v


@router.post("/recommend", tags=["Recommend"])
def post_recommend(req: RecommendRequest):
    if req.origin_stop_id not in S.stops_by_id:
        raise HTTPException(400, f"origin_stop_id '{req.origin_stop_id}' tidak ditemukan")

    results = _recommend(
        origin_stop_id=req.origin_stop_id,
        origin_walk_min=req.origin_walk_min,
        depart_hhmm=req.depart_hhmm,
        weekday=req.weekday,
        filters=req.filters,
        poi_list=S.poi_list,
        stops_by_id=S.stops_by_id,
        route_to_stop_list=S.route_to_stop_list,
        route_stop_pos=S.route_stop_pos,
        stop_to_route_dirs=S.stop_to_route_dirs,
        eta_exact=S.eta_exact,
        route_avg_eta=S.route_avg_eta,
        wait_lookup=S.wait_lookup,
        limit=req.limit,
    )
    return {"count": len(results), "results": results}


# ─────────────────────────────────────────────────────────────────────────────
# Route (single POI routing)
# ─────────────────────────────────────────────────────────────────────────────

class RouteRequest(BaseModel):
    origin_stop_id: str
    origin_walk_min: float = 0.0
    dest_poi_id: int
    depart_hhmm: str = "09:00"

    @field_validator("depart_hhmm")
    @classmethod
    def validate_hour(cls, v: str) -> str:
        h = int(v.split(":")[0])
        if h < 5 or h > 20:
            raise ValueError("Trans Jogja beroperasi 05:30–20:30")
        return v


@router.post("/route", tags=["Route"])
def post_route(req: RouteRequest):
    poi = S.poi_by_id.get(req.dest_poi_id)
    if not poi:
        raise HTTPException(404, "POI tidak ditemukan")
    if req.origin_stop_id not in S.stops_by_id:
        raise HTTPException(400, "origin_stop_id tidak ditemukan")

    depart_hour = int(req.depart_hhmm.split(":")[0])
    dist, pred = sssp_from_origin(
        origin_stop_id=req.origin_stop_id,
        origin_walk_min=req.origin_walk_min,
        depart_hour=depart_hour,
        route_to_stop_list=S.route_to_stop_list,
        route_stop_pos=S.route_stop_pos,
        stop_to_route_dirs=S.stop_to_route_dirs,
        eta_exact=S.eta_exact,
        route_avg_eta=S.route_avg_eta,
        wait_lookup=S.wait_lookup,
    )

    result = build_route_to_poi(dist, pred, poi)
    if result is None:
        return {"found": False, "message": "Tidak ada rute Trans Jogja yang menjangkau destinasi ini"}

    arrive_min = hhmm_to_min(req.depart_hhmm) + result["eta_total_min"]
    return {
        "found": True,
        "poi_name": poi.get("name"),
        "eta_total_min": result["eta_total_min"],
        "transfers": result["transfers"],
        "arrive_hhmm": min_to_hhmm(arrive_min),
        "route_legs": _enrich_legs(result["route_legs"], S.stops_by_id),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Itinerary (day planner)
# ─────────────────────────────────────────────────────────────────────────────

class ItineraryRequest(BaseModel):
    origin_stop_id: str
    origin_walk_min: float = 0.0
    depart_hhmm: str = "09:00"
    end_hhmm: str = "17:00"
    weekday: str = "Sabtu"
    min_stay_min: int = 60
    filters: dict = {}
    max_destinations: int = 5


@router.post("/itinerary", tags=["Itinerary"])
def post_itinerary(req: ItineraryRequest):
    if req.origin_stop_id not in S.stops_by_id:
        raise HTTPException(400, "origin_stop_id tidak ditemukan")
    if hhmm_to_min(req.end_hhmm) <= hhmm_to_min(req.depart_hhmm):
        raise HTTPException(400, "end_hhmm harus setelah depart_hhmm")

    result = plan_day(
        origin_stop_id=req.origin_stop_id,
        origin_walk_min=req.origin_walk_min,
        depart_hhmm=req.depart_hhmm,
        end_hhmm=req.end_hhmm,
        weekday=req.weekday,
        min_stay_min=req.min_stay_min,
        filters=req.filters,
        max_destinations=req.max_destinations,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Schedule — cek jadwal halte
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/schedule", tags=["Schedule"])
def get_schedule(
    stop_id: str = Query(...),
    day_type: str = Query("weekday", pattern="^(weekday|weekend)$"),
):
    if stop_id not in S.stops_by_id:
        raise HTTPException(404, "Stop tidak ditemukan")

    stop_sched = S.stop_schedule.get(stop_id, {})
    routes = []
    for rid, times in stop_sched.items():
        headway_avg = None
        if len(times) > 1:
            mins = [hhmm_to_min(t) for t in times]
            gaps = [mins[i+1] - mins[i] for i in range(len(mins)-1) if mins[i+1] > mins[i]]
            headway_avg = round(sum(gaps) / len(gaps), 0) if gaps else None
        routes.append({
            "route_id": rid,
            "departures": times,
            "headway_avg_min": headway_avg,
        })
    routes.sort(key=lambda x: x["route_id"])
    return {
        "stop_id": stop_id,
        "stop_name": S.stops_by_id[stop_id].get("name"),
        "day_type": day_type,
        "routes": routes,
        "note": "Jadwal estimasi berbasis data historis Trans Jogja.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Routes — cek rute
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/routes/geojson", tags=["Routes"])
def get_routes_geojson(route_id: Optional[str] = None):
    """GeoJSON jalur rute untuk Leaflet RouteLayer."""
    features = S.routes_geojson.get("features", [])
    if route_id:
        features = [f for f in features
                    if f.get("properties", {}).get("route_id") == route_id.upper()]
    return {"type": "FeatureCollection", "features": features}


@router.get("/routes", tags=["Routes"])
def get_routes_list():
    """Daftar semua route_dir dengan ringkasan halte."""
    result = []
    for rd, stops in S.route_to_stop_list.items():
        result.append({
            "route_dir": rd,
            "route_id": rd.rsplit("_", 1)[0],
            "direction_id": rd.rsplit("_", 1)[1],
            "total_stops": len(stops),
            "first_stop": S.stops_by_id.get(stops[0], {}).get("name", stops[0]) if stops else None,
            "last_stop": S.stops_by_id.get(stops[-1], {}).get("name", stops[-1]) if stops else None,
        })
    result.sort(key=lambda x: x["route_dir"])
    return result


@router.get("/routes/{route_dir}", tags=["Routes"])
def get_route_detail(route_dir: str):
    stops = S.route_to_stop_list.get(route_dir)
    if not stops:
        raise HTTPException(404, "Route tidak ditemukan")
    stops_detail = []
    for sid in stops:
        s = S.stops_by_id.get(sid, {})
        stops_detail.append({
            "stop_id": sid,
            "stop_name": s.get("name", sid),
            "lat": s.get("lat"),
            "lon": s.get("lon"),
        })
    return {
        "route_dir": route_dir,
        "route_id": route_dir.rsplit("_", 1)[0],
        "direction_id": route_dir.rsplit("_", 1)[1],
        "total_stops": len(stops),
        "stops": stops_detail,
    }


@router.get("/routes/between/stops", tags=["Routes"])
def get_routes_between(
    from_stop: str = Query(...),
    to_stop: str = Query(...),
):
    """Temukan rute yang menghubungkan dua halte (direct atau 1 transfer)."""
    direct = []
    one_transfer = []

    for rd, slist in S.route_to_stop_list.items():
        if from_stop in slist and to_stop in slist:
            pf = slist.index(from_stop)
            pt = slist.index(to_stop)
            if pt > pf:
                direct.append({
                    "type": "direct",
                    "route_dir": rd,
                    "route_id": rd.rsplit("_", 1)[0],
                    "n_stops": pt - pf,
                })

    if not direct:
        # 1-transfer: cari halte transfer
        from_routes = {rd for rd, sl in S.route_to_stop_list.items() if from_stop in sl}
        to_routes   = {rd for rd, sl in S.route_to_stop_list.items() if to_stop   in sl}
        for fr in from_routes:
            for tr in to_routes:
                if fr == tr:
                    continue
                # cari common stop setelah from_stop di fr dan sebelum to_stop di tr
                fr_stops = S.route_to_stop_list[fr]
                tr_stops = S.route_to_stop_list[tr]
                pf = fr_stops.index(from_stop) if from_stop in fr_stops else -1
                pt = tr_stops.index(to_stop)   if to_stop   in tr_stops else -1
                if pf < 0 or pt < 0:
                    continue
                for sid in fr_stops[pf+1:]:
                    if sid in tr_stops:
                        sp = tr_stops.index(sid)
                        if sp < pt:
                            one_transfer.append({
                                "type": "1_transfer",
                                "leg1_route_dir": fr,
                                "leg1_route_id": fr.rsplit("_",1)[0],
                                "transfer_stop_id": sid,
                                "transfer_stop_name": S.stops_by_id.get(sid,{}).get("name",sid),
                                "leg2_route_dir": tr,
                                "leg2_route_id": tr.rsplit("_",1)[0],
                            })
                            break

    return {
        "from_stop": from_stop,
        "from_stop_name": S.stops_by_id.get(from_stop, {}).get("name"),
        "to_stop": to_stop,
        "to_stop_name": S.stops_by_id.get(to_stop, {}).get("name"),
        "direct": direct[:5],
        "one_transfer": one_transfer[:5],
    }
