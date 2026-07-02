"""Diagnosa sumber RMSE tinggi pada model ETA Trans Jogja."""
import sys, pathlib
import pandas as pd
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from transjogja_CRISP_DM import (
    parse_routes_kml, canonicalize_stops,
    normalize_trip_times, build_segments, build_segment_lookup,
    split_train_val_segments, predict_segments, mae, rmse
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

print("=== Statistik Data Segmen ===")
print(f"Total baris   : {len(segments):,}")
print(f"Segmen unik   : {segments['segment_id'].nunique():,}")
print(segments['travel_time_min'].describe())

# Model baseline
base, bins = build_segment_lookup(train, bin_size=3, K=1.0, min_bin_n=1)
pred = predict_segments(val, base, bins, bin_size=3)
usable = pred.dropna(subset=['pred_min', 'travel_time_min']).copy()
usable['abs_err'] = np.abs(usable['travel_time_min'] - usable['pred_min'])
usable['sq_err']  = usable['abs_err'] ** 2

print(f"\n=== Metrik Model (bin=3, K=1, minN=1) ===")
print(f"MAE  = {mae(usable['travel_time_min'], usable['pred_min']):.4f} menit")
print(f"RMSE = {rmse(usable['travel_time_min'], usable['pred_min']):.4f} menit")
print(f"MedAE= {float(np.median(usable['abs_err'])):.4f} menit")

print(f"\n=== Distribusi Absolute Error ===")
for p in [25, 50, 75, 90, 95, 99, 100]:
    print(f"  P{p:3d}: {np.percentile(usable['abs_err'], p):.4f} menit")

pct_zero = (usable['abs_err'] == 0).mean() * 100
pct_gt5  = (usable['abs_err'] > 5).mean() * 100
pct_gt10 = (usable['abs_err'] > 10).mean() * 100
pct_gt20 = (usable['abs_err'] > 20).mean() * 100
print(f"\n  Error = 0   : {pct_zero:.1f}%")
print(f"  Error > 5   : {pct_gt5:.2f}%")
print(f"  Error > 10  : {pct_gt10:.2f}%")
print(f"  Error > 20  : {pct_gt20:.2f}%")

# Kontribusi ke MSE dari kelompok error
total_mse = float(usable['sq_err'].mean())
mask_big  = usable['abs_err'] > 10
print(f"\n  Kontribusi error > 10 mnt ke MSE: {usable.loc[mask_big, 'sq_err'].sum() / usable['sq_err'].sum() * 100:.1f}%")
print(f"  Jumlah baris error > 10 mnt     : {mask_big.sum():,} dari {len(usable):,} ({mask_big.mean()*100:.2f}%)")

print(f"\n=== Top 15 Baris Error Terbesar ===")
top = usable.nlargest(15, 'abs_err')[
    ['segment_id', 'route_id', 'travel_time_min', 'pred_min', 'abs_err', 'dep_tod_min_mod']
]
print(top.to_string())

# Distribusi jumlah obs per segmen
seg_counts = train.groupby('segment_id').size()
print(f"\n=== Distribusi Observasi per Segmen (training) ===")
print(seg_counts.describe())
print(f"  Segmen dengan < 5 obs : {(seg_counts < 5).sum()}")
print(f"  Segmen dengan < 10 obs: {(seg_counts < 10).sum()}")
print(f"  Segmen dengan 1 obs   : {(seg_counts == 1).sum()}")

# Apakah error besar berasal dari segmen jarang?
usable2 = usable.merge(seg_counts.rename('train_n'), on='segment_id', how='left')
print(f"\n=== Error berdasarkan kelompok observasi training ===")
bins_obs = [0, 1, 5, 10, 20, 50, float('inf')]
labels   = ['=1','2-5','6-10','11-20','21-50','>50']
usable2['obs_grp'] = pd.cut(usable2['train_n'], bins=bins_obs, labels=labels, right=True)
grp = usable2.groupby('obs_grp', observed=True).agg(
    MAE=('abs_err', 'mean'),
    RMSE=('sq_err', lambda x: float(np.sqrt(x.mean()))),
    N=('abs_err', 'size')
).reset_index()
print(grp.to_string())
