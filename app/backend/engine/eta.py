"""
engine/eta.py — ETA calculation with 3-level fallback.
"""

from __future__ import annotations
import math
from typing import Optional

WALK_SPEED_MPM = 80.0      # meter per menit
TRANSFER_PENALTY = 5.0     # menit penalti per transfer
DEFAULT_SEG_MIN = 3.0      # fallback Level 3


def seg_eta(
    seg_key: str,
    route_dir: str,
    eta_exact: dict[str, float],
    route_avg_eta: dict[str, float],
) -> float:
    """
    3-level ETA fallback:
      L1 - exact segment lookup        (78.5% coverage)
      L2 - route average per segment   (lebih akurat dari global)
      L3 - global default 3.0 menit
    """
    if seg_key in eta_exact:
        return eta_exact[seg_key]
    if route_dir in route_avg_eta:
        return route_avg_eta[route_dir]
    return DEFAULT_SEG_MIN


def get_wait(
    stop_id: str,
    route_id: str,
    hour: int,
    wait_lookup: dict,
) -> float:
    """
    Lookup expected wait time dengan fallback bertingkat:
      1. Exact (stop, route, hour)
      2. Jam terdekat yang ada untuk rute itu di stop itu
      3. Default half-headway 7.5 menit
    """
    stop_data = wait_lookup.get(stop_id, {})
    route_data = stop_data.get(route_id, {})
    if not route_data:
        return 7.5  # fallback default
    if hour in route_data:
        return route_data[hour]
    # closest available hour
    closest = min(route_data.keys(), key=lambda h: abs(h - hour))
    return route_data[closest]


def walk_time(dist_m: float) -> float:
    """Menit berjalan kaki dari jarak meter."""
    return round(dist_m / WALK_SPEED_MPM, 2)


def walk_dist_to_stop(
    user_lat: float,
    user_lon: float,
    stop: dict,
) -> Optional[tuple[float, float]]:
    """Returns (dist_m, walk_min) or None if stop has no coords."""
    slat = stop.get("lat")
    slon = stop.get("lon")
    if slat is None or slon is None:
        return None
    R = 6_371_000
    p = math.pi / 180
    a = (math.sin((slat - user_lat) * p / 2) ** 2 +
         math.cos(user_lat * p) * math.cos(slat * p) *
         math.sin((slon - user_lon) * p / 2) ** 2)
    dist = 2 * R * math.asin(math.sqrt(a))
    return dist, walk_time(dist)


def hhmm_to_min(hhmm: str) -> int:
    """'09:30' → 570"""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def min_to_hhmm(total_min: float) -> str:
    """570.5 → '09:31'"""
    t = int(round(total_min))
    return f"{t // 60:02d}:{t % 60:02d}"


def is_open_with_margin(
    arrive_hhmm: str,
    close_hhmm: str,
    min_margin_min: int = 120,
) -> tuple[bool, int]:
    """
    Returns (open_ok, remaining_min).
    open_ok=True jika sisa waktu buka >= min_margin_min.
    """
    arrive = hhmm_to_min(arrive_hhmm)
    close  = hhmm_to_min(close_hhmm)
    remaining = close - arrive
    return remaining >= min_margin_min, remaining


_DAY_ORDER = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

def is_open_on_day(open_days: str, weekday: str) -> bool:
    """Handles: 'Senin-Minggu' (range), 'Senin,Sabtu' (list), empty→True."""
    s = str(open_days).strip()
    if not s or s.lower() in ("nan", "none", "", "setiap hari", "setiap_hari", "daily", "every day"):
        return True
    if "-" in s and "," not in s:
        parts = [p.strip() for p in s.split("-")]
        if len(parts) == 2 and parts[0] in _DAY_ORDER and parts[1] in _DAY_ORDER:
            start = _DAY_ORDER.index(parts[0])
            end   = _DAY_ORDER.index(parts[1])
            idx   = _DAY_ORDER.index(weekday) if weekday in _DAY_ORDER else -1
            return start <= idx <= end
    days = [d.strip() for d in s.split(",")]
    return weekday in days


# ── [v4] Per-day schedule support ─────────────────────────────────────────────
_HARI_LIST = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]

def is_open_on_day_perhari(poi: dict, weekday: str) -> bool:
    """
    [v4] Cek jadwal per hari dari field `schedule` di poi_slim.json.
    Jika field tidak ada, fallback ke is_open_on_day(open_days, weekday).
    """
    schedule = poi.get("schedule")
    if not schedule:
        return is_open_on_day(poi.get("open_days",""), weekday)
    day_entry = schedule.get(weekday)
    if day_entry is None:
        return True          # hari tidak terdaftar → anggap buka
    return day_entry is not None   # None = tutup, dict = buka

def get_close_hhmm_for_day(poi: dict, weekday: str) -> str:
    """[v4] Ambil close_hhmm untuk hari tertentu dari schedule per hari."""
    schedule = poi.get("schedule")
    if schedule:
        day_entry = schedule.get(weekday)
        if isinstance(day_entry, dict):
            return day_entry.get("close", poi.get("close_hhmm","17:00"))
    return poi.get("close_hhmm","17:00")
