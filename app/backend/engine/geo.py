"""engine/geo.py — Haversine & nearest stop."""
from __future__ import annotations
import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) *
         math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def nearest_stops(
    lat: float,
    lon: float,
    stops_list: list[dict],
    limit: int = 5,
    max_dist_m: float = 3000,
) -> list[dict]:
    results = []
    for s in stops_list:
        slat, slon = s.get("lat"), s.get("lon")
        if slat is None or slon is None:
            continue
        d = haversine(lat, lon, float(slat), float(slon))
        if d <= max_dist_m:
            results.append({
                "stop_id":      s["stop_id"],
                "stop_name":    s.get("name", s["stop_id"]),
                "lat":          slat,
                "lon":          slon,
                "distance_m":   round(d, 1),
                "walk_time_min": round(d / 80, 2),
            })
    results.sort(key=lambda x: x["distance_m"])
    return results[:limit]
