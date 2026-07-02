"""
engine/planner.py — Greedy day itinerary chaining.

Algoritma:
  WHILE waktu masih ada:
    1. recommend(current_stop, current_time, exclude=visited)
    2. Ambil POI terbaik yang masih buka ≥ min_stay_min
    3. Append ke itinerary, update current_stop & current_time
    4. BREAK jika tidak ada POI feasible atau max_destinations tercapai
"""

from __future__ import annotations

from .eta import hhmm_to_min, min_to_hhmm, is_open_with_margin, is_open_on_day
from .recommender import recommend
from startup import (
    poi_list, stops_by_id,
    route_to_stop_list, route_stop_pos, stop_to_route_dirs,
    eta_exact, route_avg_eta, wait_lookup,
)


def plan_day(
    origin_stop_id: str,
    origin_walk_min: float,
    depart_hhmm: str,
    end_hhmm: str,
    weekday: str,
    min_stay_min: int = 60,
    filters: dict | None = None,
    max_destinations: int = 5,
) -> dict:
    filters = filters or {}
    depart_min = hhmm_to_min(depart_hhmm)
    end_min    = hhmm_to_min(end_hhmm)

    current_stop = origin_stop_id
    current_walk = origin_walk_min
    current_min  = depart_min
    visited: set[int] = set()
    itinerary: list[dict] = []

    while current_min < end_min - min_stay_min and len(itinerary) < max_destinations:
        current_hhmm = min_to_hhmm(current_min)

        # Recommend dari posisi sekarang
        # Exclude visited, malls, and souvenir centers
        def is_allowed(p):
            if int(p["poi_id"]) in visited:
                return False
            t = str(p.get("type", "")).lower()
            n = str(p.get("name", "")).lower()
            if "oleh" in t or "pusat oleh" in n:
                return False
            if "mall" in n or "plaza" in n or "square" in n:
                return False
            return True

        recs = recommend(
            origin_stop_id=current_stop,
            origin_walk_min=current_walk,
            depart_hhmm=current_hhmm,
            weekday=weekday,
            filters={**filters, "min_stay_hours": min_stay_min / 60},
            poi_list=[p for p in poi_list if is_allowed(p)],
            stops_by_id=stops_by_id,
            route_to_stop_list=route_to_stop_list,
            route_stop_pos=route_stop_pos,
            stop_to_route_dirs=stop_to_route_dirs,
            eta_exact=eta_exact,
            route_avg_eta=route_avg_eta,
            wait_lookup=wait_lookup,
            limit=20,
        )

        # Cari POI yang feasible dalam sisa hari
        chosen = None
        for rec in recs:
            arrive_min = current_min + rec["eta_total_min"]
            if arrive_min + min_stay_min > end_min:
                continue
            open_ok, remaining = is_open_with_margin(
                min_to_hhmm(arrive_min),
                str(rec.get("close_hhmm", "17:00")),
                min_margin_min=min_stay_min,
            )
            if not open_ok:
                continue
            chosen = rec
            arrive_min_chosen = arrive_min
            break

        if chosen is None:
            break

        depart_from_poi = arrive_min_chosen + min_stay_min
        itinerary.append({
            "order": len(itinerary) + 1,
            "poi_id": chosen["poi_id"],
            "name": chosen["name"],
            "type": chosen["type"],
            "lat": chosen["lat"],
            "lon": chosen["lon"],
            "rating": chosen["rating"],
            "open_hhmm": chosen["open_hhmm"],
            "close_hhmm": chosen["close_hhmm"],
            "needs_review": chosen["needs_review"],
            "arrive_hhmm": min_to_hhmm(arrive_min_chosen),
            "depart_hhmm": min_to_hhmm(depart_from_poi),
            "stay_min": min_stay_min,
            "eta_from_prev_min": round(chosen["eta_total_min"], 2),
            "transfers": chosen["transfers"],
            "route_legs": chosen["route_legs"],
            "description": chosen.get("description"),
            "htm_weekday": chosen.get("htm_weekday"),
            "htm_weekend": chosen.get("htm_weekend"),
            "image": chosen.get("image"),
        })

        visited.add(int(chosen["poi_id"]))
        # Update posisi: nearest_stop_id dari POI yang baru dikunjungi
        current_stop = chosen.get("nearest_stop_id", current_stop)
        current_walk = float(chosen.get("walk_time_min", 0))
        current_min  = depart_from_poi

    total_travel = sum(i["eta_from_prev_min"] for i in itinerary)
    total_visit  = len(itinerary) * min_stay_min

    return {
        "feasible": len(itinerary) > 0,
        "total_destinations": len(itinerary),
        "total_travel_min": round(total_travel, 1),
        "total_visit_min": total_visit,
        "return_hhmm": min_to_hhmm(current_min),
        "itinerary": itinerary,
    }
