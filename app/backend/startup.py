"""
startup.py — load semua JSON artifacts ke memori dan bangun lookup dicts.
Dipanggil sekali saat FastAPI startup.

v4 changes:
  - Gate needs_review: poi_list hanya berisi POI dengan needs_review=0
  - Per-day schedule: support field `schedule` di poi_slim.json
  - Stops update: 534 total, hanya 472 valid (tanpa koordinat masuk invalid_stops)
"""

import json
import math
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).parent / "data"

# ==============================================================================
# STRUKTUR DATA UTAMA (RAW DATA)
# Menampung data mentah halte, rute, dan POI dari file JSON.
# ==============================================================================
# ── raw data ──────────────────────────────────────────────────────────────────
stops_list: list[dict] = []
poi_list:   list[dict] = []       # [v4] hanya needs_review=0
poi_list_all: list[dict] = []     # semua POI termasuk needs_review=1 (audit)
routes_geojson: dict   = {}

# ==============================================================================
# TABEL PENCARIAN (LOOKUP DICTS)
# Struktur data map/dictionary untuk pencarian rute, estimasi waktu (ETA), dan jadwal dengan cepat (O(1)).
# ==============================================================================
# ── lookup dicts ──────────────────────────────────────────────────────────────
stops_by_id: dict[str, dict] = {}
poi_by_id:   dict[int, dict] = {}

route_to_stop_list: dict[str, list[str]]       = {}
route_stop_pos:     dict[str, dict[str, int]]  = {}
stop_to_route_dirs: dict[str, list[str]]       = {}

eta_exact:     dict[str, float] = {}
route_avg_eta: dict[str, float] = {}

wait_lookup:   dict[str, dict[str, dict[int, float]]] = {}
stop_schedule: dict[str, dict[str, list]]             = {}
invalid_stops: set[str] = set()


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def load_all() -> None:
    global stops_list, poi_list, poi_list_all, routes_geojson

    # ── stops ─────────────────────────────────────────────────────────────────
    stops_list = json.loads((DATA / "stops.json").read_text(encoding="utf-8"))
    for s in stops_list:
        stops_by_id[s["stop_id"]] = s

    # ── invalid stops ─────────────────────────────────────────────────────────
    invalid_stops.update(json.loads((DATA / "invalid_stops.json").read_text(encoding="utf-8")))

    # ── POI — [v4] gate: hanya needs_review=0 masuk poi_list aktif ───────────
    poi_list_raw = json.loads((DATA / "poi_slim.json").read_text(encoding="utf-8"))
    
    def map_poi_type(poi: dict) -> str:
        raw_type = str(poi.get("type", "")).lower()
        raw_name = str(poi.get("name", "")).lower()
        
        if "sejarah" in raw_type or "museum" in raw_type or "budaya" in raw_type:
            return "Sejarah"
        if "kuliner" in raw_type:
            return "Kuliner"
        if "oleh" in raw_type or "belanja" in raw_type or "mall" in raw_name or "plaza" in raw_name:
            return "Belanja"
        return "Wisata"
        
    for p in poi_list_raw:
        p["original_type"] = p.get("type")
        p["type"] = map_poi_type(p)
        poi_list_all.append(p)
        if int(p.get("needs_review", 0)) == 0:
            poi_list.append(p)
            poi_by_id[int(p["poi_id"])] = p

    excluded = len(poi_list_raw) - len(poi_list)
    if excluded > 0:
        print(f"[startup][v4] gate: {excluded} POI dikecualikan (needs_review=1)")
        print(f"[startup][v4] lihat data/needs_review_list.json untuk daftar lengkap")

    # ── routes geojson ────────────────────────────────────────────────────────
    routes_geojson.update(json.loads((DATA / "routes_geojson.json").read_text(encoding="utf-8")))

    # ── route sequences ───────────────────────────────────────────────────────
    rseq_raw = json.loads((DATA / "route_sequences.json").read_text(encoding="utf-8"))
    for rd, data in rseq_raw.items():
        clean = [s["stop_id"] for s in data["stops"]
                 if s["stop_id"] not in invalid_stops
                 and stops_by_id.get(s["stop_id"], {}).get("lat") is not None]
        if len(clean) < 2:
            continue
        route_to_stop_list[rd] = clean

        # simpan posisi PERTAMA (rute sirkuler)
        pos_map: dict[str, int] = {}
        for i, sid in enumerate(clean):
            if sid not in pos_map:
                pos_map[sid] = i
        route_stop_pos[rd] = pos_map

    # deduplikasi route_dirs per stop
    _s2r: dict[str, list[str]] = defaultdict(list)
    for rd, stops in route_to_stop_list.items():
        for sid in stops:
            _s2r[sid].append(rd)
    for sid, rds in _s2r.items():
        stop_to_route_dirs[sid] = list(dict.fromkeys(rds))

    # ── ETA lookup ────────────────────────────────────────────────────────────
    eta_raw = json.loads((DATA / "eta_lookup.json").read_text(encoding="utf-8"))
    for seg_id, val in eta_raw.items():
        eta_exact[seg_id] = float(val["seg_median_min"])

    route_avg_eta.update(json.loads((DATA / "route_avg_eta.json").read_text(encoding="utf-8")))

    # ── wait lookup ───────────────────────────────────────────────────────────
    wait_raw = json.loads((DATA / "wait_time_lookup.json").read_text(encoding="utf-8"))
    for sid, routes in wait_raw.items():
        wait_lookup[sid] = {}
        for rid, hours_dict in routes.items():
            wait_lookup[sid][rid] = {int(h): float(val) for h, val in hours_dict.items()}

    # ── stop schedule ─────────────────────────────────────────────────────────
    try:
        moovit_sched = json.loads((DATA / "schedules_moovit.json").read_text(encoding="utf-8"))
    except:
        moovit_sched = {}

    for sid, rds in stop_to_route_dirs.items():
        stop_schedule[sid] = {}
        rids = list(set([rd.split('_')[0] for rd in rds]))
        for rid in rids:
            if sid in moovit_sched and rid in moovit_sched[sid]:
                stop_schedule[sid][rid] = sorted(moovit_sched[sid][rid])
            else:
                times = []
                for h in range(5, 21):
                    headway = 15
                    n_trips = int(60 / headway)
                    for j in range(n_trips):
                        minute = int((j / n_trips) * 60)
                        times.append(f"{h:02d}:{minute:02d}")
                stop_schedule[sid][rid] = times
    # summary
    dup = sum(1 for v in stop_to_route_dirs.values() if len(v) != len(set(v)))
    transfer = sum(1 for v in stop_to_route_dirs.values() if len(v) > 1)
    print(f"[startup] stops={len(stops_list)}, invalid={len(invalid_stops)}")
    print(f"[startup] poi_active={len(poi_list)}/{len(poi_list_all)}, route_dirs={len(route_to_stop_list)}")
    print(f"[startup] eta_segments={len(eta_exact)}, wait_stops={len(wait_lookup)}")
    print(f"[startup] transfer_stops={transfer}, dup_route_dirs={dup} (should be 0)")
