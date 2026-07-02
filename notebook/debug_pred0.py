"""
Verifikasi bug prediksi 0.0 dan analisis segmen HT_078->HT_079.
"""
import sys, pathlib
import pandas as pd
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from transjogja_CRISP_DM import (
    parse_routes_kml, canonicalize_stops,
    normalize_trip_times, build_segments, build_segment_lookup,
    split_train_val_segments, predict_segments
)

RAW = pathlib.Path('raw')
route_summary, _ = parse_routes_kml(RAW / 'Jalur Route.kml')
stops = canonicalize_stops()
stops = stops.sort_values(['stop_name', 'stop_id']).reset_index(drop=True)
cmap = {raw: f'HT_{i+1:03d}' for i, raw in enumerate(stops['stop_id'])}
stops['stop_id'] = stops['stop_id'].map(cmap)

st_raw = pd.read_csv(RAW / 'transjogja_stop_times_final_v6.csv')
st_raw['route_id'] = st_raw['route_id'].astype(str).str.upper()
st_raw['trip_id']  = st_raw['trip_id'].astype(str)
st_raw['stop_id']  = st_raw['stop_id'].astype(str).map(cmap).fillna(st_raw['stop_id'].astype(str))
valid_routes = set(route_summary['route_id'].astype(str).str.upper())
st_raw = st_raw[st_raw['route_id'].isin(valid_routes)]

stop_times = normalize_trip_times(st_raw)
segments   = build_segments(stop_times, stops)
train, val = split_train_val_segments(segments)

# Cek segmen HT_078->HT_079 di training
seg_id = 'HT_078->HT_079'
train_seg = train[train['segment_id'] == seg_id].copy()
val_seg   = val[val['segment_id'] == seg_id].copy()

print(f"=== Segmen '{seg_id}' ===")
print(f"Di training: {len(train_seg)} baris")
print(f"Di validasi: {len(val_seg)} baris")

if not train_seg.empty:
    print(f"\nDistribusi travel_time_min (training):")
    print(train_seg['travel_time_min'].describe())
    print(f"\nDistribusi dep_tod_min_mod (training):")
    print(train_seg['dep_tod_min_mod'].describe())

print(f"\nDistribusi travel_time_min (validasi):")
print(val_seg['travel_time_min'].describe())
print(f"\nDistribusi dep_tod_min_mod (validasi):")
print(val_seg['dep_tod_min_mod'].describe())

# Build lookup dan cek prediksi
base, bins = build_segment_lookup(train, bin_size=3, K=1.0, min_bin_n=1)
base_seg = base[base['segment_id'] == seg_id]
bins_seg = bins[bins['segment_id'] == seg_id]

print(f"\nBase lookup untuk '{seg_id}':")
print(base_seg.to_string())
print(f"\nBins lookup untuk '{seg_id}' (jika ada):")
print(bins_seg.to_string() if not bins_seg.empty else "TIDAK ADA entri di bins!")

# Prediksi pada val
pred = predict_segments(val_seg, base, bins, bin_size=3)
print(f"\nHasil prediksi di validasi:")
print(pred[['travel_time_min', 'dep_tod_min_mod', 'dep_bin', 'seg_median_min', 'pred_smooth_min', 'pred_min']].to_string())

# Kenapa pred_min = 0? Cek apakah seg_mean_min = 0
print(f"\nseg_mean_min = {base_seg['seg_mean_min'].values}")
print(f"seg_median_min = {base_seg['seg_median_min'].values}")

# Cek data asli train
print(f"\nData training untuk '{seg_id}':")
print(train_seg[['trip_id','tod_min','dep_tod_min_mod','travel_time_min']].to_string())
