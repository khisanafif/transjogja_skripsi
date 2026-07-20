"""
engine/recommender.py — weighted scoring + LRU cache.

Scoring weights (sesuai proposal H.5):
  ETA           0.35  (lebih cepat = lebih baik)
  walk_dist     0.20  (halte lebih dekat = lebih baik)
  transfers     0.20  (direct > 1 transfer > ...)
  open_margin   0.10  (sisa jam buka lebih banyak = lebih baik)
  rating        0.10
  popularity    0.05
  [v4] needs_review penalty dihapus — POI needs_review=1 sudah
       dikecualikan dari pool oleh gate di startup.py
"""

from __future__ import annotations
import math
import time
from typing import Optional

from .eta import (
    hhmm_to_min, min_to_hhmm,
    is_open_with_margin, is_open_on_day,
    is_open_on_day_perhari, get_close_hhmm_for_day,  # [v4]
)
from .routing import sssp_from_origin, build_route_to_poi

# ── simple TTL cache ───────────────────────────────────────────────────────
_cache: dict[tuple, dict] = {}
_CACHE_TTL = 900  # 15 menit

MAX_WALK_M = 1200.0
MIN_OPEN_MARGIN = 120  # 2 jam


def recommend(
    origin_stop_id: str,
    origin_walk_min: float,
    depart_hhmm: str,
    weekday: str,
    filters: dict,
    # data
    poi_list: list,
    stops_by_id: dict,
    route_to_stop_list: dict,
    route_stop_pos: dict,
    stop_to_route_dirs: dict,
    eta_exact: dict,
    route_avg_eta: dict,
    wait_lookup: dict,
    limit: int = 15,
) -> list[dict]:
    """
    1 SSSP call → score all 116 POI → return top-limit.
    """
    depart_hour = int(depart_hhmm.split(":")[0])
    depart_min_of_day = hhmm_to_min(depart_hhmm)

    # ── cache key ─────────────────────────────────────────────────────────
    types_tuple = tuple(sorted(filters.get("types", []) or []))
    cache_key = (
        origin_stop_id, depart_hour,
        _day_type(weekday), types_tuple,
        filters.get("max_transfers", 99),
        filters.get("max_eta_min", 90),
        filters.get("min_stay_hours", 2),
    )
    now = time.time()
    if cache_key in _cache and now - _cache[cache_key]["ts"] < _CACHE_TTL:
        return _cache[cache_key]["data"]

    # ── 1 Dijkstra SSSP ───────────────────────────────────────────────────
    dist, pred = sssp_from_origin(
        origin_stop_id=origin_stop_id,
        origin_walk_min=origin_walk_min,
        depart_hour=depart_hour,
        route_to_stop_list=route_to_stop_list,
        route_stop_pos=route_stop_pos,
        stop_to_route_dirs=stop_to_route_dirs,
        eta_exact=eta_exact,
        route_avg_eta=route_avg_eta,
        wait_lookup=wait_lookup,
    )

    # ── score each POI ────────────────────────────────────────────────────
    candidates = []
    max_eta = float(filters.get("max_eta_min", 90))
    max_transfers = int(filters.get("max_transfers", 99))
    min_stay = int(filters.get("min_stay_hours", 2)) * 60
    type_filter = [t.strip() for t in (filters.get("types") or [])]

    for poi in poi_list:
        # type filter
        if type_filter and poi.get("type") not in type_filter:
            continue

        # coverage filter
        if not poi.get("nearest_stop_id"):
            continue

        route_result = build_route_to_poi(dist, pred, poi)
        if route_result is None:
            continue

        eta = route_result["eta_total_min"]
        transfers = route_result["transfers"]

        # ETA filter
        if eta > max_eta:
            continue
        if transfers > max_transfers:
            continue

        # jam buka filter
        arrive_hhmm = min_to_hhmm(depart_min_of_day + eta)
        # [v4] gunakan jadwal per hari jika tersedia
        close_today = get_close_hhmm_for_day(poi, weekday)
        open_ok, remaining = is_open_with_margin(
            arrive_hhmm,
            close_today,
            min_margin_min=min_stay,
        )
        if not open_ok:
            continue
        if not is_open_on_day_perhari(poi, weekday):   # [v4] per-day check
            continue

        score = _score(poi, eta, transfers, remaining)

        candidates.append({
            **_poi_fields(poi),
            "eta_total_min": eta,
            "transfers": transfers,
            "arrive_hhmm": arrive_hhmm,
            "remaining_open_min": remaining,
            "open_margin_ok": open_ok,
            "recommendation_score": round(score, 2),
            "route_legs": _enrich_legs(route_result["route_legs"], stops_by_id),
        })

    candidates.sort(key=lambda x: -x["recommendation_score"])
    result = [{"rank": i + 1, **c} for i, c in enumerate(candidates[:limit])]

    _cache[cache_key] = {"data": result, "ts": now}
    return result


def _score(poi: dict, eta: float, transfers: int, remaining_min: int) -> float:
    # norm helpers (0→1)
    def norm_inv(val, lo=0, hi=90):
        return max(0.0, 1.0 - (val - lo) / max(hi - lo, 1))

    eta_score     = norm_inv(eta, 0, 90)
    walk_score    = norm_inv(float(poi.get("walk_dist_m", 1200)), 0, 1200)
    transfer_score = max(0.0, 1.0 - transfers / 4)
    margin_score  = min(1.0, remaining_min / 480)
    rating_score  = (float(poi.get("rating", 3)) - 1) / 4
    pop_score     = min(1.0, math.log1p(float(poi.get("vote_count", 0))) / 10)
    # [v4] needs_review_penalty dihapus — POI needs_review=1 sudah dikecualikan
    review_penalty = 0  # tidak diperlukan lagi

    return (
        0.35 * eta_score
        + 0.20 * walk_score
        + 0.20 * transfer_score
        + 0.10 * margin_score
        + 0.10 * rating_score
        + 0.05 * pop_score
        # - review_penalty  [v4] dihapus
    ) * 100


def _poi_fields(poi: dict) -> dict:
    return {
        "poi_id": poi.get("poi_id"),
        "name": poi.get("name"),
        "type": poi.get("type"),
        "lat": poi.get("lat"),
        "lon": poi.get("lon"),
        "rating": poi.get("rating"),
        "vote_count": poi.get("vote_count"),
        "open_hhmm": poi.get("open_hhmm"),
        "close_hhmm": poi.get("close_hhmm"),
        "open_days": poi.get("open_days"),
        "needs_review": bool(int(poi.get("needs_review", 0))),
        "hours_source_type": poi.get("hours_source_type"),
        "nearest_stop_id": poi.get("nearest_stop_id"),
        "nearest_stop_name": poi.get("nearest_stop_name"),
        "walk_dist_m": poi.get("walk_dist_m"),
        "walk_time_min": poi.get("walk_time_min"),
        "walk_access_class": poi.get("walk_access_class"),
        "description": poi.get("description"),
        "htm_weekday": poi.get("htm_weekday"),
        "htm_weekend": poi.get("htm_weekend"),
        "image": poi.get("image"),
    }


def _enrich_legs(legs: list, stops_by_id: dict) -> list:
    """Tambahkan stop_name ke setiap leg."""
    result = []
    for leg in legs:
        l = dict(leg)
        for key in ("stop_id", "board_stop_id", "alight_stop_id",
                    "at_stop_id", "from_stop_id", "to_stop_id"):
            sid = l.get(key)
            if sid and sid in stops_by_id:
                l[key.replace("_id", "_name")] = stops_by_id[sid].get("stop_name", stops_by_id[sid].get("name", sid))
        result.append(l)
    return result


def _day_type(weekday: str) -> str:
    weekends = {"Sabtu", "Minggu", "Saturday", "Sunday"}
    return "weekend" if weekday in weekends else "weekday"
