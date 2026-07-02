import nbformat
import json

nb = nbformat.v4.new_notebook()

md_intro = """# Eksperimen Model ETA yang Lebih Robust
Sesuai arahan, notebook ini mengimplementasikan tiga level perbaikan pada model ETA Trans Jogja:
1. **Level Data**: Penanganan Outlier (Capping/Winsorizing) & Filter Trip Anomali.
2. **Level Model**: Statistik Robust (MAD per segmen) & Pemisahan Jalur Smoothing (Peak vs Off-Peak).
3. **Level Evaluasi**: Breakdown performa (Route/Time-bin) dan penambahan metrik MedAE & P90.
"""

code_setup = """import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from sklearn.metrics import median_absolute_error

from transjogja_CRISP_DM import (
    canonicalize_stops, normalize_trip_times, build_segments, 
    split_train_val_segments, predict_segments, mae, rmse
)

# Metric helpers
def p90_error(y_true, y_pred):
    return np.percentile(np.abs(np.asarray(y_true) - np.asarray(y_pred)), 90)

# Load data baseline
stop_times_raw = pd.read_csv("raw/transjogja_stop_times_final_v6.csv")
stops = canonicalize_stops()
stop_times_norm = normalize_trip_times(stop_times_raw)
segments = build_segments(stop_times_norm, stops)

# Kita filter sedikit lebih ketat untuk trip anomali
segments = segments[segments['travel_time_min'] > 0]
segments = segments[segments['travel_time_min'] <= 60] # max 60 min per segment

train, val = split_train_val_segments(segments)
print(f"Data latih: {len(train):,} | Data validasi: {len(val):,}")
"""

md_data = """## 1. Level Data: Capping & Winsorizing
Memotong nilai travel_time_min di luar persentil 1 dan 99 secara global."""

code_data = """# Winsorizing secara global
q1, q99 = train['travel_time_min'].quantile([0.01, 0.99])
train['travel_time_min_capped'] = train['travel_time_min'].clip(q1, q99)

print(f"Batas bawah (P1): {q1:.2f} menit")
print(f"Batas atas (P99): {q99:.2f} menit")
"""

md_model = """## 2. Level Model: MAD per Segmen & Peak/Off-Peak Separation
Di sini kita menghitung Median Absolute Deviation (MAD) untuk setiap segmen, 
dan juga memisahkan prior smoothing untuk Peak Hour (06:00-09:00 dan 15:00-18:00) vs Off-Peak."""

code_model = """def is_peak(tod_min):
    # Peak: 06:00-09:00 (360-540) or 15:00-18:00 (900-1080)
    return ((tod_min >= 360) & (tod_min <= 540)) | ((tod_min >= 900) & (tod_min <= 1080))

train['is_peak'] = is_peak(train['dep_tod_min_mod'])
val['is_peak'] = is_peak(val['dep_tod_min_mod'])

# Hitung base (prior) secara terpisah berdasarkan peak/off-peak, 
# menggunakan median dan MAD.
def calc_mad(x):
    return np.median(np.abs(x - np.median(x)))

base_robust = train.groupby(['segment_id', 'is_peak'], as_index=False).agg(
    seg_median_min=('travel_time_min_capped', 'median'),
    seg_mad=('travel_time_min_capped', calc_mad),
    seg_n=('travel_time_min_capped', 'size')
)

def build_robust_segment_lookup(train_df, bin_size, K, min_bin_n):
    # Base prior
    base = train_df.groupby(['segment_id', 'is_peak'], as_index=False).agg(
        seg_median_min=('travel_time_min_capped', 'median'),
        seg_n=('travel_time_min_capped', 'size')
    )
    
    tmp = train_df.copy()
    tmp['dep_bin'] = (tmp['dep_tod_min_mod'] // bin_size).astype(int) * bin_size
    
    # Hitung bin median
    bins = tmp.groupby(['segment_id', 'is_peak', 'dep_bin'], as_index=False).agg(
        bin_median_min=('travel_time_min_capped', 'median'),
        bin_n=('travel_time_min_capped', 'size')
    )
    bins = bins.merge(base[['segment_id', 'is_peak', 'seg_median_min']], on=['segment_id', 'is_peak'], how='left')
    bins = bins[bins['bin_n'] >= min_bin_n].copy()
    
    # Bayesian Smoothing ke arah MEDIAN Prior
    bins['pred_smooth_min'] = (
        bins['bin_n'] * bins['bin_median_min'] + K * bins['seg_median_min']
    ) / (bins['bin_n'] + K)
    
    return base, bins

def predict_robust_segments(df, base_lookup, bin_lookup, bin_size):
    out = df.copy()
    out['dep_bin'] = (out['dep_tod_min_mod'] // bin_size).astype(int) * bin_size
    out = out.merge(base_lookup[['segment_id', 'is_peak', 'seg_median_min']], on=['segment_id', 'is_peak'], how='left')
    out = out.merge(bin_lookup[['segment_id', 'is_peak', 'dep_bin', 'pred_smooth_min']], on=['segment_id', 'is_peak', 'dep_bin'], how='left')
    out['pred_min'] = out['pred_smooth_min'].fillna(out['seg_median_min'])
    # fallback jika data peak/off-peak tidak ada di training
    global_median = out['seg_median_min'].median()
    out['pred_min'] = out['pred_min'].fillna(global_median)
    return out

# Train model robust
best_bin_size = 3
best_K = 1.0
best_min_bin_n = 3

base_rob, bins_rob = build_robust_segment_lookup(train, bin_size=best_bin_size, K=best_K, min_bin_n=best_min_bin_n)
pred_rob = predict_robust_segments(val, base_rob, bins_rob, bin_size=best_bin_size)

# Baseline as comparison (Original build_segment_lookup logic using original un-capped column)
from transjogja_CRISP_DM import build_segment_lookup
base_orig, bins_orig = build_segment_lookup(train, bin_size=best_bin_size, K=best_K, min_bin_n=best_min_bin_n)
pred_orig = predict_segments(val, base_orig, bins_orig, bin_size=best_bin_size)
"""

md_eval = """## 3. Level Evaluasi: Granular & Metrik Lengkap
Membandingkan MAE, RMSE, MedAE (Median Absolute Error), dan P90 Error.
Kita breakdown hasil ini berdasarkan Rute dan kondisi Peak/Off-Peak."""

code_eval = """# Prepare results
usable_rob = pred_rob.dropna(subset=['pred_min', 'travel_time_min'])
usable_orig = pred_orig.dropna(subset=['pred_min', 'travel_time_min'])

def get_metrics(y_true, y_pred, name):
    return {
        'Model': name,
        'MAE': mae(y_true, y_pred),
        'RMSE': rmse(y_true, y_pred),
        'MedAE': median_absolute_error(y_true, y_pred),
        'P90 Error': p90_error(y_true, y_pred)
    }

metrics = []
metrics.append(get_metrics(usable_orig['travel_time_min'], usable_orig['pred_min'], '1. Baseline (Original)'))
metrics.append(get_metrics(usable_rob['travel_time_min'], usable_rob['pred_min'], '2. Robust Model'))

df_metrics = pd.DataFrame(metrics).set_index('Model')
print("=== PERBANDINGAN METRIK GLOBAL ===")
print(df_metrics)

# --- Breakdown per Route ---
print("\\n=== BREAKDOWN MAE PER RUTE (TOP 5 WORST di Robust Model) ===")
usable_rob['abs_err'] = np.abs(usable_rob['travel_time_min'] - usable_rob['pred_min'])
route_err = usable_rob.groupby('route_id')['abs_err'].agg(['mean', 'median', 'size']).rename(columns={'mean':'MAE', 'median':'MedAE', 'size':'N_Trips'})
route_err = route_err.sort_values('MAE', ascending=False)
print(route_err.head())

# --- Breakdown Peak vs Off-Peak ---
print("\\n=== BREAKDOWN PEAK vs OFF-PEAK ===")
peak_err = usable_rob.groupby('is_peak')['abs_err'].agg(['mean', 'median', 'size']).rename(columns={'mean':'MAE', 'median':'MedAE', 'size':'N_Trips'})
peak_err.index = ['Off-Peak', 'Peak']
print(peak_err)
"""

nb['cells'] = [
    nbformat.v4.new_markdown_cell(md_intro),
    nbformat.v4.new_code_cell(code_setup),
    nbformat.v4.new_markdown_cell(md_data),
    nbformat.v4.new_code_cell(code_data),
    nbformat.v4.new_markdown_cell(md_model),
    nbformat.v4.new_code_cell(code_model),
    nbformat.v4.new_markdown_cell(md_eval),
    nbformat.v4.new_code_cell(code_eval)
]

with open('c:/Users/User/Downloads/transjogja_skripsi/notebook/robust_eta_experiment.ipynb', 'w') as f:
    nbformat.write(nb, f)
print('robust_eta_experiment.ipynb created.')
