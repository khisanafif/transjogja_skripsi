import nbformat
import json

nb = nbformat.v4.new_notebook()

code_setup = '''import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from transjogja_CRISP_DM import (
    canonicalize_stops,
    normalize_trip_times,
    build_segments,
    split_train_val_segments,
    build_segment_lookup,
    predict_segments,
    mae,
    rmse
)

# Load data
stop_times_raw = pd.read_csv("raw/transjogja_stop_times_final_v6.csv")
stops = canonicalize_stops()
stop_times_norm = normalize_trip_times(stop_times_raw)

# Build segments
segments = build_segments(stop_times_norm, stops)
train, val = split_train_val_segments(segments)

print(f"Total segmen: {len(segments):,}")
print(f"Data latih: {len(train):,} baris")
print(f"Data validasi: {len(val):,} baris")
'''

code_true_median = '''def weighted_median(values, weights):
    """Menghitung weighted median dari array values dengan bobot weights."""
    values = np.array(values)
    weights = np.array(weights)
    
    sorted_indices = np.argsort(values)
    values_sorted = values[sorted_indices]
    weights_sorted = weights[sorted_indices]
    
    cum_weights = np.cumsum(weights_sorted)
    cutoff = cum_weights[-1] / 2.0
    idx = np.searchsorted(cum_weights, cutoff)
    
    if idx >= len(values_sorted):
        idx = len(values_sorted) - 1
        
    return values_sorted[idx]

def build_segment_lookup_median_smoothing(train: pd.DataFrame, bin_size: int, K: float, min_bin_n: int):
    """
    Bayesian smoothing yang BENAR-BENAR menggunakan Median.
    Menggabungkan raw data di dalam bin (bobot 1) dengan median global (bobot K).
    """
    base = (
        train.groupby('segment_id', as_index=False)['travel_time_min']
        .agg(seg_median_min='median', seg_mean_min='mean', seg_n='size')
    )
    
    tmp = train.copy()
    tmp['dep_bin'] = (tmp['dep_tod_min_mod'] // bin_size).astype(int) * bin_size
    tmp = tmp.merge(base[['segment_id', 'seg_median_min']], on='segment_id', how='left')
    
    results = []
    for name, group in tmp.groupby(['segment_id', 'dep_bin']):
        n = len(group)
        if n < min_bin_n:
            continue
            
        vals = group['travel_time_min'].tolist() + [group['seg_median_min'].iloc[0]]
        weights = [1.0] * n + [float(K)]
        
        wm = weighted_median(vals, weights)
        
        results.append({
            'segment_id': name[0],
            'dep_bin': name[1],
            'bin_n': n,
            'bin_median_min': group['travel_time_min'].median(),
            'seg_median_min': group['seg_median_min'].iloc[0],
            'pred_smooth_min': wm
        })
        
    bins = pd.DataFrame(results)
    return base, bins
'''

code_eval = '''best_bin_size = 3
best_min_bin_n = 3

results = []
for k in [1.0, 2.0, 3.0, 5.0, 10.0]:
    # 1. Baseline (Weighted Mean dari Median)
    base_orig, bins_orig = build_segment_lookup(train, bin_size=best_bin_size, K=k, min_bin_n=best_min_bin_n)
    pred_orig = predict_segments(val, base_orig, bins_orig, bin_size=best_bin_size)
    usable_orig = pred_orig.dropna(subset=['pred_min', 'travel_time_min'])
    mae_orig = mae(usable_orig['travel_time_min'], usable_orig['pred_min'])
    rmse_orig = rmse(usable_orig['travel_time_min'], usable_orig['pred_min'])
    
    # 2. Metode Baru (True Median dari Raw Data + Pseudo Data)
    base_new, bins_new = build_segment_lookup_median_smoothing(train, bin_size=best_bin_size, K=k, min_bin_n=best_min_bin_n)
    pred_new = predict_segments(val, base_new, bins_new, bin_size=best_bin_size)
    usable_new = pred_new.dropna(subset=['pred_min', 'travel_time_min'])
    mae_new = mae(usable_new['travel_time_min'], usable_new['pred_min'])
    rmse_new = rmse(usable_new['travel_time_min'], usable_new['pred_min'])
    
    results.append({
        'K': k,
        'Metode': '1. Mean of Medians (Lama)',
        'MAE': mae_orig,
        'RMSE': rmse_orig
    })
    results.append({
        'K': k,
        'Metode': '2. True Median (Baru)',
        'MAE': mae_new,
        'RMSE': rmse_new
    })

df_results = pd.DataFrame(results)
df_pivot = df_results.pivot(index='K', columns='Metode')
print("=== PERBANDINGAN PERFORMA ===")
print(df_pivot)
'''

nb['cells'] = [
    nbformat.v4.new_markdown_cell("# Eksperimen: True Median Bayesian Smoothing\n\nNotebook ini membandingkan rumus Bayesian smoothing lama (berbasis perhitungan rata-rata antar median) dengan rumus baru yang murni menghitung *Weighted Median* dari seluruh baris data di bin ditambah *pseudo-data* (median global) dengan bobot K."),
    nbformat.v4.new_code_cell(code_setup),
    nbformat.v4.new_code_cell(code_true_median),
    nbformat.v4.new_code_cell(code_eval)
]

with open('c:/Users/User/Downloads/transjogja_skripsi/notebook/compare_median_smoothing.ipynb', 'w') as f:
    nbformat.write(nb, f)

print('Notebook compare_median_smoothing.ipynb created successfully.')
