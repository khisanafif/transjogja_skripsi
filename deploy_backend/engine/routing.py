"""
engine/routing.py — Single-Source Shortest Path (SSSP) Dijkstra.

Aturan transit (final):
- WALK hanya di awal (user → stop_awal) dan akhir (stop_akhir → dest)
- TRANSFER hanya pada stop_id yang SAMA (same-stop)
- Multi-transfer diizinkan asal selalu same-stop
- Tidak ada walking antar halte saat transit
"""

from __future__ import annotations
import heapq
import itertools
from typing import Optional

_cnt = itertools.count()

from .eta import seg_eta, get_wait, TRANSFER_PENALTY

MAX_COST_MIN = 90.0   # pruning: abaikan path > 90 menit
_counter = itertools.count()  # tiebreaker agar dict tidak dicompare


def sssp_from_origin(
    origin_stop_id: str,
    origin_walk_min: float,
    depart_hour: int,
    route_to_stop_list: dict[str, list[str]],
    route_stop_pos: dict[str, dict[str, int]],
    stop_to_route_dirs: dict[str, list[str]],
    eta_exact: dict[str, float],
    route_avg_eta: dict[str, float],
    wait_lookup: dict,
) -> tuple[dict, dict]:
    """
    Dijkstra SSSP dari origin_stop_id.

    Returns:
      dist  : {(stop_id, route_dir) → min_cost_menit}
      pred  : {(stop_id, route_dir) → list_of_legs}

    Node = (stop_id, route_dir):
      route_dir=None → sedang di halte, belum naik / sudah turun
      route_dir=X    → sedang dalam perjalanan dengan rute X

    Edge types:
      BOARD     : (stop, None)    → (stop, rd)       cost=wait
      RIDE      : (stop_A, rd)    → (stop_B, rd)     cost=Σ seg_eta
      ALIGHT    : (stop_B, rd)    → (stop_B, None)   cost=0
      TRANSFER  : (stop_X, rd_A) → (stop_X, rd_B)   cost=wait_rd_B (same stop!)
    """
    dist: dict[tuple, float] = {}
    pred: dict[tuple, list] = {}

    # State: (cost, stop_id, route_dir, legs_so_far)
    init_key = (origin_stop_id, None)
    heap = [(origin_walk_min, next(_cnt), origin_stop_id, None, [
        {"type": "WALK_START",
         "to_stop_id": origin_stop_id,
         "walk_time_min": origin_walk_min}
    ])]

    while heap:
        cost, _tc, stop, rd, legs = heapq.heappop(heap)
        key = (stop, rd)

        if key in dist:
            continue
        dist[key] = cost
        pred[key] = legs

        if cost > MAX_COST_MIN:
            continue

        cur_hour = min(int(depart_hour + cost / 60), 20)

        # ── Case A: di halte, belum naik rute ─────────────────────────────
        if rd is None:
            for next_rd in stop_to_route_dirs.get(stop, []):
                route_id = next_rd.rsplit("_", 1)[0]
                wait = get_wait(stop, route_id, cur_hour, wait_lookup)
                new_cost = cost + wait
                if new_cost > MAX_COST_MIN:
                    continue
                new_key = (stop, next_rd)
                if new_key in dist:
                    continue
                new_legs = legs + [{
                    "type": "BOARD",
                    "stop_id": stop,
                    "route_dir": next_rd,
                    "route_id": route_id,
                    "wait_min": round(wait, 2),
                }]
                heapq.heappush(heap, (new_cost, next(_cnt), stop, next_rd, new_legs))

        # ── Case B: sedang dalam rute rd ──────────────────────────────────
        else:
            stops_in_route = route_to_stop_list.get(rd, [])
            pos = route_stop_pos.get(rd, {}).get(stop)
            if pos is None:
                continue

            accum = 0.0
            board_stop = _get_board_stop(legs)
            prev = stop

            for next_stop in stops_in_route[pos + 1:]:
                seg_key = f"{prev}->{next_stop}"
                seg_t = seg_eta(seg_key, rd, eta_exact, route_avg_eta)
                accum += seg_t
                new_cost = cost + accum

                if new_cost > MAX_COST_MIN:
                    break

                ride_leg = {
                    "type": "BUS",
                    "route_dir": rd,
                    "route_id": rd.rsplit("_", 1)[0],
                    "board_stop_id": board_stop,
                    "alight_stop_id": next_stop,
                    "ride_min": round(accum, 2),
                    "n_stops": stops_in_route.index(next_stop) - pos,
                }

                # Opsi ALIGHT (turun di next_stop)
                alight_key = (next_stop, None)
                if alight_key not in dist:
                    alight_legs = legs + [ride_leg]
                    heapq.heappush(heap,
                        (new_cost, next(_cnt), next_stop, None, alight_legs))

                # Opsi TRANSFER di next_stop (same-stop only)
                arr_hour = min(int(depart_hour + new_cost / 60), 20)
                for other_rd in stop_to_route_dirs.get(next_stop, []):
                    if other_rd == rd:
                        continue
                    other_key = (next_stop, other_rd)
                    if other_key in dist:
                        continue
                    other_rid = other_rd.rsplit("_", 1)[0]
                    wait_next = get_wait(next_stop, other_rid, arr_hour, wait_lookup)
                    transfer_cost = new_cost + wait_next
                    if transfer_cost > MAX_COST_MIN:
                        continue
                    transfer_legs = legs + [ride_leg, {
                        "type": "TRANSFER",
                        "at_stop_id": next_stop,
                        "from_route_dir": rd,
                        "to_route_dir": other_rd,
                        "to_route_id": other_rid,
                        "wait_min": round(wait_next, 2),
                        "penalty_min": TRANSFER_PENALTY,
                    }]
                    heapq.heappush(heap, (
                        transfer_cost + TRANSFER_PENALTY,
                        next(_cnt), next_stop, other_rd, transfer_legs
                    ))

                prev = next_stop

    return dist, pred


def build_route_to_poi(
    dist: dict,
    pred: dict,
    poi: dict,
) -> Optional[dict]:
    """
    Dari SSSP result, kembalikan rute ke satu POI.
    poi harus punya: nearest_stop_id, walk_time_min, walk_dist_m.
    """
    dest_stop = poi.get("nearest_stop_id")
    if not dest_stop:
        return None

    stop_key = (dest_stop, None)
    if stop_key not in dist:
        return None

    transit_cost = dist[stop_key]
    walk_end_min = float(poi.get("walk_time_min", 0))
    eta_total = round(transit_cost + walk_end_min, 2)

    legs = pred[stop_key] + [{
        "type": "WALK_END",
        "from_stop_id": dest_stop,
        "dest_name": poi.get("name", ""),
        "walk_dist_m": round(float(poi.get("walk_dist_m", 0)), 1),
        "walk_time_min": round(walk_end_min, 2),
    }]

    transfers = sum(1 for l in legs if l["type"] == "TRANSFER")
    return {
        "eta_total_min": eta_total,
        "transfers": transfers,
        "route_legs": legs,
    }


def _get_board_stop(legs: list) -> str:
    for leg in reversed(legs):
        if leg.get("type") == "BOARD":
            return leg["stop_id"]
    return ""
