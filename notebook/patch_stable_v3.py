"""
Patch untuk memperbaiki bug route_median_min fallback di predict_segments.
"""
import json
from pathlib import Path

nb_path = Path('transjogja_CRISP_DM_stable.ipynb')
nb = json.loads(nb_path.read_text(encoding='utf-8'))

NEW_PREDICT_SEGMENTS = [
    "def predict_segments(df, base_lookup, bin_lookup, bin_size):\n",
    "    \"\"\"\n",
    "    Menerapkan prediksi ETA.\n",
    "    [PERBAIKAN RMSE v3] Fallback rute digabung via route_id, bukan segment_id!\n",
    "    \"\"\"\n",
    "    out = df.copy()\n",
    "    out['dep_bin'] = (out['dep_tod_min_mod'] // bin_size).astype(int) * bin_size\n",
    "\n",
    "    # Ambil route_median_min dari base_lookup berdasarkan route_id!\n",
    "    if 'route_id' in out.columns and 'route_id' in base_lookup.columns and 'route_median_min' in base_lookup.columns:\n",
    "        route_meds = base_lookup[['route_id', 'route_median_min']].drop_duplicates().dropna()\n",
    "        out = out.merge(route_meds, on='route_id', how='left')\n",
    "\n",
    "    # Kolom yang diambil dari base via segment_id\n",
    "    base_cols = ['segment_id', 'seg_median_min', 'seg_mean_min', 'seg_p05', 'seg_p95']\n",
    "    base_cols = [c for c in base_cols if c in base_lookup.columns]\n",
    "\n",
    "    out = out.merge(base_lookup[base_cols], on='segment_id', how='left')\n",
    "    out = out.merge(\n",
    "        bin_lookup[['segment_id', 'dep_bin', 'pred_smooth_min']],\n",
    "        on=['segment_id', 'dep_bin'], how='left')\n",
    "\n",
    "    # Fallback bertingkat\n",
    "    out['pred_min'] = out['pred_smooth_min']\n",
    "    if 'seg_median_min' in out.columns:\n",
    "        out['pred_min'] = out['pred_min'].fillna(out['seg_median_min'])\n",
    "    if 'route_median_min' in out.columns:\n",
    "        out['pred_min'] = out['pred_min'].fillna(out['route_median_min'])\n",
    "    if 'seg_mean_min' in out.columns:\n",
    "        out['pred_min'] = out['pred_min'].fillna(out['seg_mean_min'])\n",
    "\n",
    "    # Global median fallback (Last Resort!)\n",
    "    if 'seg_median_min' in base_lookup.columns:\n",
    "        global_med = float(base_lookup['seg_median_min'].median())\n",
    "        out['pred_min'] = out['pred_min'].fillna(global_med)\n",
    "\n",
    "    # Post-prediction capping ke [seg_p05, seg_p95]\n",
    "    if 'seg_p05' in out.columns and 'seg_p95' in out.columns:\n",
    "        mask = out['seg_p05'].notna() & out['seg_p95'].notna()\n",
    "        out.loc[mask, 'pred_min'] = out.loc[mask, 'pred_min'].clip(\n",
    "            lower=out.loc[mask, 'seg_p05'],\n",
    "            upper=out.loc[mask, 'seg_p95']\n",
    "        )\n",
    "    return out\n"
]

target_idx = None
for i, cell in enumerate(nb['cells']):
    if cell.get('id') == 'eta_stable_functions':
        target_idx = i
        break

if target_idx is not None:
    source = nb['cells'][target_idx]['source']
    
    # Cari indeks mulai dan akhir predict_segments
    start_idx, end_idx = -1, -1
    for j, line in enumerate(source):
        if line.startswith("def predict_segments("):
            start_idx = j
        elif start_idx != -1 and line.startswith("def mae("):
            end_idx = j - 1 # Baris kosong sebelum metrik evaluasi
            break
            
    if start_idx != -1 and end_idx != -1:
        new_source = source[:start_idx] + NEW_PREDICT_SEGMENTS + ["\n"] + source[end_idx:]
        nb['cells'][target_idx]['source'] = new_source
        print(f'predict_segments berhasil di-patch pada sel {target_idx}')
    else:
        print('Gagal menemukan batas predict_segments!')
else:
    print('Sel eta_stable_functions tidak ditemukan!')

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
