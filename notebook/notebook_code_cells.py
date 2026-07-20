# CELL_IDX: 2
from __future__ import annotations
import json, math, re, unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np
import pandas as pd

BASE_DIR   = Path.cwd()
RAW_DIR    = BASE_DIR / 'raw'
PRE_DIR    = BASE_DIR / 'preprocessed'
MODEL_DIR  = BASE_DIR / 'model'
REPORT_DIR = BASE_DIR / 'report'
WEB_DIR    = BASE_DIR / 'web_artifacts'
for p in [PRE_DIR, MODEL_DIR, REPORT_DIR, WEB_DIR]:
    p.mkdir(parents=True, exist_ok=True)

ROUTES_KML     = RAW_DIR / 'Jalur Route.kml'
STOPS_KML      = RAW_DIR / 'Perhentian Bus Bus Stop.kml'
STOP_TIMES_CSV = RAW_DIR / 'transjogja_stop_times_final_v6.csv'
POI_CSV        = RAW_DIR / 'wisata_jogja.csv'
KML_NS = {'kml': 'http://www.opengis.net/kml/2.2'}

WALK_SPEED_M_PER_MIN = 80.0
POI_WALK_THRESHOLD_M = 1200.0
TRANSFER_PENALTY_MIN = 5.0
MIN_STAY_MIN_DEFAULT = 120.0
RECOMMENDER_DEFAULT_TYPES = [
    'Budaya dan Sejarah', 'Alam', 'Agrowisata', 'Buatan', 'Pantai',
    'Wisata Air', 'Museum', 'Desa Wisata', 'Pusat Oleh-Oleh'
]
RECOMMENDER_EXCLUDE_PATTERNS = [
    r'\bmeeting point\b', r'\binformation center\b', r'\btour planner\b',
    r'\btransport service\b', r'\btravel\b', r'\bport\b', r'\bhotel\b',
    r'\bguest ?house\b', r'\bhomestay\b', r'\bresort\b', r'\bapartment\b',
    r'\bhostel\b', r'\brental\b', r'\bticket\b', r'\boffice\b',
    r'\btattoo\b', r'\bguide\b', r'\bchauffeur\b', r'\bruang perawatan\b',
]
DAY_NAMES_ID = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']

pd.set_option('display.max_columns', 50)
pd.set_option('display.max_rows', 20)
print(f'Direktori kerja : {BASE_DIR}')


########################################

# CELL_IDX: 5
def parse_route_id(name):
    name = (name or '').strip()
    m = re.match(r'^\s*([A-Za-z0-9-]+)', name)
    return m.group(1).upper() if m else name.upper()

def parse_kml_coord_text(text):
    coords = []
    if not text:
        return coords
    for token in text.strip().split():
        parts = token.split(',')
        if len(parts) < 2:
            continue
        coords.append([float(parts[0]), float(parts[1])])
    return coords

def extract_route_refs(desc):
    found = re.findall(r'([A-Za-z0-9-]+)\s*_+\s*Trans Jogja', desc or '', flags=re.I)
    refs, seen = [], set()
    for item in found:
        rid = item.upper()
        if rid not in seen:
            refs.append(rid)
            seen.add(rid)
    return refs

def parse_routes_kml(path):
    root = ET.parse(path).getroot()
    rows, features = [], []
    for pm in root.findall('.//kml:Placemark', KML_NS):
        line = pm.find('kml:LineString', KML_NS)
        if line is None: continue
        name = (pm.findtext('kml:name', default='', namespaces=KML_NS) or '').strip()
        desc = (pm.findtext('kml:description', default='', namespaces=KML_NS) or '').strip()
        coords = parse_kml_coord_text(line.findtext('kml:coordinates', default='', namespaces=KML_NS))
        route_id = parse_route_id(name)
        desc_clean = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', desc))[:200]
        rows.append({'route_id': route_id, 'kml_name': name, 'n_vertices': len(coords), 'description_preview': desc_clean})
        features.append({'type': 'Feature', 'properties': {'route_id': route_id, 'kml_name': name},
                         'geometry': {'type': 'LineString', 'coordinates': coords}})
    return pd.DataFrame(rows), {'type': 'FeatureCollection', 'features': features}

def parse_stops_kml(path):
    root = ET.parse(path).getroot()
    rows = []
    for pm in root.findall('.//kml:Placemark', KML_NS):
        point = pm.find('kml:Point', KML_NS)
        if point is None: continue
        name = (pm.findtext('kml:name', default='', namespaces=KML_NS) or '').strip()
        desc = (pm.findtext('kml:description', default='', namespaces=KML_NS) or '').strip()
        coords = parse_kml_coord_text(point.findtext('kml:coordinates', default='', namespaces=KML_NS))
        lon = coords[0][0] if coords else np.nan
        lat = coords[0][1] if coords else np.nan
        rows.append({'kml_stop_name': name, 'lat': lat, 'lon': lon,
                     'route_refs': '|'.join(extract_route_refs(desc)),
                     'description_preview': re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', desc))[:200]})
    return pd.DataFrame(rows)

def canonicalize_stops():
    kml_stops = parse_stops_kml(STOPS_KML)
    try:
        st_raw = pd.read_csv(STOP_TIMES_CSV)
        unique_stop_ids = st_raw['stop_id'].astype(str).unique()
    except Exception:
        unique_stop_ids = []
    if len(unique_stop_ids) == 0:
        stops = kml_stops.rename(columns={'kml_stop_name': 'stop_name'})
        stops['stop_id'] = stops['stop_name']
        stops['source_rows'] = 1
        return stops[['stop_id', 'stop_name', 'lat', 'lon', 'source_rows']]
    rows = []
    for sid in unique_stop_ids:
        sid_norm = re.sub(r'[^a-z0-9]', '', sid.lower()
                          .replace('tpb', '').replace('halte', '')
                          .replace('s_', '').replace('terminal', 'term'))
        best_match, best_score = None, -1
        for _, krow in kml_stops.iterrows():
            kname = str(krow['kml_stop_name'])
            knorm = re.sub(r'[^a-z0-9]', '', kname.lower()
                           .replace('tpb', '').replace('halte', '')
                           .replace(' - a', '').replace(' - b', ''))
            score = SequenceMatcher(None, sid_norm, knorm).ratio()
            if knorm and sid_norm and (knorm in sid_norm or sid_norm in knorm):
                score += 0.5
            if score > best_score:
                best_score = score
                best_match = krow
        if best_match is not None and best_score > 0.4:
            rows.append({'stop_id': sid, 'stop_name': best_match['kml_stop_name'],
                         'lat': best_match['lat'], 'lon': best_match['lon'], 'source_rows': 1})
        else:
            rows.append({'stop_id': sid, 'stop_name': sid.replace('S_', '').replace('_', ' ').title(),
                         'lat': np.nan, 'lon': np.nan, 'source_rows': 1})
    return pd.DataFrame(rows)

def haversine_m(lat1, lon1, lat2, lon2):
    lat1 = np.radians(lat1); lon1 = np.radians(lon1)
    lat2 = np.radians(lat2); lon2 = np.radians(lon2)
    dlat = lat2 - lat1; dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 6_371_000.0 * 2 * np.arcsin(np.sqrt(a))

print('Fungsi geospasial dimuat.')


########################################

# CELL_IDX: 7
route_summary, route_fc_all = parse_routes_kml(ROUTES_KML)
kml_stop_points             = parse_stops_kml(STOPS_KML)
stops = canonicalize_stops()
stops = stops.sort_values(['stop_name', 'stop_id']).reset_index(drop=True)
canonical_id_map = {raw_id: f'HT_{i+1:03d}' for i, raw_id in enumerate(stops['stop_id'])}
stops['stop_id'] = stops['stop_id'].map(canonical_id_map)

stop_times_raw = pd.read_csv(STOP_TIMES_CSV)
stop_times_raw['route_id'] = stop_times_raw['route_id'].astype(str).str.upper()
stop_times_raw['trip_id']  = stop_times_raw['trip_id'].astype(str)
stop_times_raw['stop_id']  = stop_times_raw['stop_id'].astype(str)
stop_times_raw['stop_id']  = stop_times_raw['stop_id'].map(canonical_id_map).fillna(stop_times_raw['stop_id'])
valid_routes   = set(route_summary['route_id'].astype(str).str.upper())
stop_times_raw = stop_times_raw[stop_times_raw['route_id'].isin(valid_routes)].copy()

poi = pd.read_csv(POI_CSV)
if 'no' in poi.columns:
    poi = poi.rename(columns={'no': 'poi_id'})
else:
    poi['poi_id'] = np.arange(len(poi), dtype=int)

print('Ringkasan Dataset:')
display(pd.DataFrame([
    {'dataset': 'Rute Trans Jogja (KML)', 'baris': len(route_summary)},
    {'dataset': 'Halte Kanonikal', 'baris': stops['stop_id'].nunique()},
    {'dataset': 'Jadwal Keberangkatan', 'baris': len(stop_times_raw)},
    {'dataset': 'Destinasi Wisata (POI)', 'baris': len(poi)},
]))


########################################

# CELL_IDX: 10
def parse_hhmm(value):
    hh, mm = str(value).strip().split(':')[:2]
    return int(hh) * 60 + int(mm)

def hhmm_from_minutes(value):
    v = int(round(float(value))) % (24 * 60)
    return f'{v // 60:02d}:{v % 60:02d}'

def normalize_trip_times(df):
    df = df.copy()
    df['tod_min'] = df['time'].map(parse_hhmm).astype(float)
    return df.sort_values(['trip_id', 'stop_sequence', 'stop_id']).reset_index(drop=True)

def build_stop_events(stop_times):
    out = stop_times[['stop_id', 'route_id', 'direction_id', 'trip_id', 'tod_min']].copy()
    out = out.rename(columns={'tod_min': 'dep_tod_min'})
    out['dep_hhmm'] = out['dep_tod_min'].map(hhmm_from_minutes)
    out['hour']     = (out['dep_tod_min'] % 1440 // 60).astype(int)
    return out.sort_values(['stop_id', 'route_id', 'direction_id', 'dep_tod_min', 'trip_id']).reset_index(drop=True)

def build_wait_lookup(stop_events):
    tmp = stop_events.sort_values(['stop_id', 'route_id', 'direction_id', 'dep_tod_min']).copy()
    tmp['prev_dep']    = tmp.groupby(['stop_id', 'route_id', 'direction_id'])['dep_tod_min'].shift(1)
    tmp['headway_min'] = tmp['dep_tod_min'] - tmp['prev_dep']
    tmp = tmp[(tmp['headway_min'] > 0) & (tmp['headway_min'] <= 120)].copy()
    out = tmp.groupby('hour', as_index=False)['headway_min'].median().rename(
        columns={'headway_min': 'median_headway_min'}).sort_values('hour')
    out['expected_wait_min'] = out['median_headway_min'] / 2.0
    return out

def build_route_sequences(stop_times, stops):
    st = stop_times.copy()
    st['route_dir'] = st['route_id'].astype(str).str.upper() + '_' + st['direction_id'].astype(int).astype(str)
    rows, summary_rows = [], []
    for route_dir, grp in st.groupby('route_dir', sort=True):
        trip_lengths = grp.groupby('trip_id').size().sort_values(ascending=False)
        max_len    = int(trip_lengths.iloc[0])
        candidates = sorted(trip_lengths[trip_lengths == max_len].index.astype(str).tolist())
        rep_trip   = candidates[0]
        rep = grp[grp['trip_id'].astype(str) == rep_trip].sort_values('stop_sequence').copy()
        for seq_idx, rec in enumerate(rep.itertuples(index=False)):
            rows.append({'route_dir': route_dir, 'route_id': str(rec.route_id).upper(),
                         'direction_id': int(rec.direction_id), 'trip_id_representative': rep_trip,
                         'stop_sequence_canonical': int(seq_idx), 'stop_id': str(rec.stop_id)})
        summary_rows.append({'route_dir': route_dir, 'route_id': str(rep['route_id'].iloc[0]).upper(),
                             'direction_id': int(rep['direction_id'].iloc[0]),
                             'representative_trip_id': rep_trip,
                             'canonical_stop_count': int(len(rep)),
                             'trip_count': int(grp['trip_id'].nunique())})
    route_sequences = pd.DataFrame(rows).merge(stops[['stop_id', 'stop_name']], on='stop_id', how='left')
    route_sequence_summary = pd.DataFrame(summary_rows).sort_values(['route_id', 'direction_id']).reset_index(drop=True)
    return route_sequences, route_sequence_summary

def build_route_lookup_maps(route_sequences):
    route_to_stop_list = route_sequences.sort_values(['route_dir', 'stop_sequence_canonical']).groupby('route_dir')['stop_id'].agg(list).to_dict()
    route_stop_pos = {rd: {sid: idx for idx, sid in enumerate(sl)} for rd, sl in route_to_stop_list.items()}
    stop_to_route_dirs = route_sequences.groupby('stop_id')['route_dir'].agg(lambda x: sorted(pd.unique(x).tolist())).to_dict()
    return route_to_stop_list, route_stop_pos, stop_to_route_dirs

print('Fungsi jadwal dan routing dimuat.')


########################################

# CELL_IDX: 12
def build_segments(stop_times, stops):
    """Identik dengan versi asli."""
    s = stop_times.sort_values(['trip_id', 'stop_sequence', 'stop_id']).copy()
    s['next_stop_id'] = s.groupby('trip_id')['stop_id'].shift(-1)
    s['next_tod_min'] = s.groupby('trip_id')['tod_min'].shift(-1)
    s['next_trip_id'] = s.groupby('trip_id')['trip_id'].shift(-1)
    seg = s[s['trip_id'] == s['next_trip_id']].copy()
    seg['travel_time_min'] = seg['next_tod_min'] - seg['tod_min']
    seg = seg[(seg['travel_time_min'] > 0) & (seg['travel_time_min'] <= 90)].copy()
    seg['segment_id']      = seg['stop_id'] + '->' + seg['next_stop_id']
    seg['dep_tod_min_mod'] = seg['tod_min'] % 1440
    coords_from = stops[['stop_id', 'lat', 'lon']].rename(columns={'lat': 'lat_from', 'lon': 'lon_from'})
    coords_to   = stops[['stop_id', 'lat', 'lon']].rename(columns={'stop_id': 'next_stop_id', 'lat': 'lat_to', 'lon': 'lon_to'})
    seg = seg.merge(coords_from, on='stop_id', how='left')
    seg = seg.merge(coords_to, on='next_stop_id', how='left')
    seg['dist_m'] = haversine_m(seg['lat_from'], seg['lon_from'], seg['lat_to'], seg['lon_to'])
    seg.loc[seg[['lat_from', 'lon_from', 'lat_to', 'lon_to']].isna().any(axis=1), 'dist_m'] = np.nan
    cols = ['trip_id', 'route_id', 'direction_id', 'stop_id', 'next_stop_id',
            'segment_id', 'stop_sequence', 'tod_min', 'dep_tod_min_mod', 'travel_time_min', 'dist_m']
    return seg[cols].reset_index(drop=True)


# ────────────────────────────────────────────────────────────────────────
# Winsorizing Per-Segmen
# ────────────────────────────────────────────────────────────────────────
def winsorize_segments_per_segment(df, lower_q=0.05, upper_q=0.95, min_obs=10):
    """
    Memotong outlier travel_time_min secara per-segmen (P5-P95).
    Hasil di kolom travel_time_min_w. Segmen < min_obs tidak diwinsorisasi.
    """
    out = df.copy()
    out['travel_time_min_w'] = out['travel_time_min'].copy()

    def _clip_group(grp):
        if len(grp) < min_obs:
            return grp['travel_time_min']
        lo = grp['travel_time_min'].quantile(lower_q)
        hi = grp['travel_time_min'].quantile(upper_q)
        return grp['travel_time_min'].clip(lo, hi)

    out['travel_time_min_w'] = out.groupby('segment_id', group_keys=False).apply(_clip_group)
    n_clipped = int((out['travel_time_min_w'] != out['travel_time_min']).sum())
    print(f'[Winsorize per-segmen] {n_clipped:,} baris diclip dari {len(out):,} total '
          f'({n_clipped/len(out)*100:.2f}%)')
    return out


def split_train_val_segments(segments):
    """Identik dengan versi asli (~20% validasi, berbasis trip_id)."""
    trips     = sorted(segments['trip_id'].astype(str).unique().tolist())
    val_trips = set(trips[::5])
    val   = segments[segments['trip_id'].astype(str).isin(val_trips)].copy()
    train = segments[~segments['trip_id'].astype(str).isin(val_trips)].copy()
    if val.empty:
        val   = train.sample(frac=0.2, random_state=42)
        train = train.drop(val.index)
    return train.reset_index(drop=True), val.reset_index(drop=True)


def build_segment_lookup(train, bin_size, K, min_bin_n, value_col='travel_time_min_w'):
    """
    Membangun lookup ETA dengan Bayesian smoothing.

    [PERBAIKAN RMSE]
    - Simpan seg_p05 dan seg_p95 di base untuk post-prediction capping
    - Simpan route_median di base sebagai fallback tier-2
    - value_col: kolom target (default 'travel_time_min_w')
    """
    if value_col not in train.columns:
        value_col = 'travel_time_min'

    # Route-level median (fallback ketika segmen tidak ada di training)
    route_med = (
        train.groupby('route_id', as_index=False)[value_col]
        .median().rename(columns={value_col: 'route_median_min'})
    )

    # Segment-level stats + percentile batas
    def _pct(q):
        return lambda x: x.quantile(q)

    base = train.groupby('segment_id', as_index=False).agg(
        seg_median_min=(value_col, 'median'),
        seg_mean_min  =(value_col, 'mean'),
        seg_n         =(value_col, 'size'),
        seg_p05       =(value_col, _pct(0.05)),
        seg_p95       =(value_col, _pct(0.95)),
        route_id      =('route_id',  lambda x: x.mode().iloc[0]),
    )
    base = base.merge(route_med, on='route_id', how='left')

    tmp = train.copy()
    tmp['dep_bin'] = (tmp['dep_tod_min_mod'] // bin_size).astype(int) * bin_size
    bins = tmp.groupby(['segment_id', 'dep_bin'], as_index=False).agg(
        bin_n         =(value_col, 'size'),
        bin_median_min=(value_col, 'median'),
        bin_mean_min  =(value_col, 'mean'),
    )
    bins = bins.merge(
        base[['segment_id', 'seg_median_min', 'seg_mean_min']], on='segment_id', how='left')
    bins = bins[bins['bin_n'] >= min_bin_n].copy()
    bins['pred_smooth_min'] = (
        bins['bin_n'] * bins['bin_median_min'] + K * bins['seg_median_min']
    ) / (bins['bin_n'] + K)
    return base, bins


def predict_segments(df, base_lookup, bin_lookup, bin_size):
    """
    Menerapkan prediksi ETA.
    [PERBAIKAN RMSE v3] Fallback rute digabung via route_id, bukan segment_id!
    """
    out = df.copy()
    out['dep_bin'] = (out['dep_tod_min_mod'] // bin_size).astype(int) * bin_size

    # Ambil route_median_min dari base_lookup berdasarkan route_id!
    if 'route_id' in out.columns and 'route_id' in base_lookup.columns and 'route_median_min' in base_lookup.columns:
        route_meds = base_lookup[['route_id', 'route_median_min']].drop_duplicates().dropna()
        out = out.merge(route_meds, on='route_id', how='left')

    # Kolom yang diambil dari base via segment_id
    base_cols = ['segment_id', 'seg_median_min', 'seg_mean_min', 'seg_p05', 'seg_p95']
    base_cols = [c for c in base_cols if c in base_lookup.columns]

    out = out.merge(base_lookup[base_cols], on='segment_id', how='left')
    out = out.merge(
        bin_lookup[['segment_id', 'dep_bin', 'pred_smooth_min']],
        on=['segment_id', 'dep_bin'], how='left')

    # Fallback bertingkat
    out['pred_min'] = out['pred_smooth_min']
    if 'seg_median_min' in out.columns:
        out['pred_min'] = out['pred_min'].fillna(out['seg_median_min'])
    if 'route_median_min' in out.columns:
        out['pred_min'] = out['pred_min'].fillna(out['route_median_min'])
    if 'seg_mean_min' in out.columns:
        out['pred_min'] = out['pred_min'].fillna(out['seg_mean_min'])

    # Global median fallback (Last Resort!)
    if 'seg_median_min' in base_lookup.columns:
        global_med = float(base_lookup['seg_median_min'].median())
        out['pred_min'] = out['pred_min'].fillna(global_med)

    # Post-prediction capping ke [seg_p05, seg_p95]
    if 'seg_p05' in out.columns and 'seg_p95' in out.columns:
        mask = out['seg_p05'].notna() & out['seg_p95'].notna()
        out.loc[mask, 'pred_min'] = out.loc[mask, 'pred_min'].clip(
            lower=out.loc[mask, 'seg_p05'],
            upper=out.loc[mask, 'seg_p95']
        )
    return out

# Metrik evaluasi
def mae(y_true, y_pred):
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))

def rmse(y_true, y_pred):
    diff = np.asarray(y_true) - np.asarray(y_pred)
    return float(np.sqrt(np.mean(diff ** 2)))

# ────────────────────────────────────────────────────────────────────────
# 5-Fold CV Grid Search
# ────────────────────────────────────────────────────────────────────────
def make_cv_folds(segments, n_folds=5):
    trips = sorted(segments['trip_id'].astype(str).unique().tolist())
    fold_assignments = {tid: i % n_folds for i, tid in enumerate(trips)}
    folds = []
    for fold_id in range(n_folds):
        val_trips   = {tid for tid, f in fold_assignments.items() if f == fold_id}
        train_trips = {tid for tid, f in fold_assignments.items() if f != fold_id}
        val   = segments[segments['trip_id'].astype(str).isin(val_trips)].copy().reset_index(drop=True)
        train = segments[segments['trip_id'].astype(str).isin(train_trips)].copy().reset_index(drop=True)
        folds.append((train, val))
    return folds


def grid_search_cv(segments, n_folds=5, value_col='travel_time_min_w'):
    """
    Grid search dengan rata-rata n-Fold CV.

    [PERBAIKAN RMSE] Evaluasi dilakukan HANYA pada segmen yang ada
    di training fold (seen_in_train filter), sehingga tidak terkontaminasi
    oleh segmen yang sama sekali tidak ada di training.
    """
    folds = make_cv_folds(segments, n_folds=n_folds)
    results = []
    total = 3 * 4 * 3
    done = 0
    for bin_size in [120]:
        for K in [1.0, 3.0, 5.0, 10.0]:
            for min_bin_n in [1, 2, 3]:
                fold_maes, fold_rmses = [], []
                for train_f, val_f in folds:
                    base, bins = build_segment_lookup(
                        train_f, bin_size=bin_size, K=K,
                        min_bin_n=min_bin_n, value_col=value_col)
                    # Filter: hanya evaluasi segmen yang ada di training
                    seen_segs = set(base['segment_id'])
                    val_seen  = val_f[val_f['segment_id'].isin(seen_segs)].copy()
                    if val_seen.empty:
                        continue
                    pred   = predict_segments(val_seen, base, bins, bin_size=bin_size)
                    usable = pred.dropna(subset=['pred_min', 'travel_time_min'])
                    if usable.empty:
                        continue
                    fold_maes.append(mae(usable['travel_time_min'], usable['pred_min']))
                    fold_rmses.append(rmse(usable['travel_time_min'], usable['pred_min']))
                if not fold_maes:
                    continue
                results.append({
                    'bin_size': bin_size, 'K': float(K), 'min_bin_n': min_bin_n,
                    'cv_mae_mean' : float(np.mean(fold_maes)),
                    'cv_mae_std'  : float(np.std(fold_maes)),
                    'cv_rmse_mean': float(np.mean(fold_rmses)),
                    'cv_rmse_std' : float(np.std(fold_rmses)),
                    'n_folds'     : len(fold_maes),
                })
                done += 1
                if done % 30 == 0:
                    print(f'  Grid search progress: {done}/{total}...')
    res  = pd.DataFrame(results).sort_values(
        ['cv_rmse_mean', 'cv_mae_mean', 'cv_rmse_std', 'bin_size', 'K', 'min_bin_n']
    ).reset_index(drop=True)
    best = res.iloc[0].to_dict()
    return res, best


print('Fungsi model ETA dimuat.')


########################################

# CELL_IDX: 14
def normalize_text(text):
    if pd.isna(text): return ''
    text = str(text).lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]', '', text)

def nearest_stop_for_pois(poi, stops, max_dist_m=1200.0):
    results = []
    valid_stops = stops.dropna(subset=['lat', 'lon'])
    for _, prow in poi.iterrows():
        lat_poi = prow.get('latitude'); lon_poi = prow.get('longitude'); poi_id = prow.get('poi_id')
        if pd.isna(lat_poi) or pd.isna(lon_poi):
            results.append({'poi_id': poi_id, 'nearest_stop_id': np.nan, 'nearest_stop_name': np.nan,
                            'walk_dist_m': np.nan, 'walk_time_min': np.nan})
            continue
        dists = haversine_m(lat_poi, lon_poi, valid_stops['lat'].values, valid_stops['lon'].values)
        min_idx = np.argmin(dists); min_dist = dists[min_idx]
        if min_dist <= max_dist_m:
            ns = valid_stops.iloc[min_idx]
            results.append({'poi_id': poi_id, 'nearest_stop_id': ns['stop_id'],
                            'nearest_stop_name': ns['stop_name'],
                            'walk_dist_m': min_dist, 'walk_time_min': min_dist / 80.0})
        else:
            results.append({'poi_id': poi_id, 'nearest_stop_id': np.nan, 'nearest_stop_name': np.nan,
                            'walk_dist_m': np.nan, 'walk_time_min': np.nan})
    return pd.DataFrame(results)

def to_json_records(df):
    return df.where(pd.notnull(df), None).to_dict(orient='records')

def build_segment_prediction_maps(base_lookup, bin_lookup):
    base_map = base_lookup.set_index('segment_id')['seg_median_min'].to_dict()
    bin_map  = {(str(rec.segment_id), int(rec.dep_bin)): float(rec.pred_smooth_min)
                for rec in bin_lookup.itertuples(index=False)}
    return base_map, bin_map

def lookup_wait_minutes(wait_lookup, tod_min):
    hour = int(float(tod_min) % 1440 // 60)
    hit  = wait_lookup.loc[wait_lookup['hour'] == hour, 'expected_wait_min']
    if not hit.empty: return float(hit.iloc[0])
    if wait_lookup.empty: return 10.0
    return float(wait_lookup.loc[(wait_lookup['hour'] - hour).abs().idxmin(), 'expected_wait_min'])

def predict_segment_minutes(segment_id, dep_tod_min, base_map, bin_map, bin_size):
    dep_bin = int(float(dep_tod_min) % 1440 // bin_size) * int(bin_size)
    if (segment_id, dep_bin) in bin_map: return float(bin_map[(segment_id, dep_bin)])
    if segment_id in base_map: return float(base_map[segment_id])
    return float('nan')

def format_route_dir_label(route_dir):
    route_dir = str(route_dir)
    if '_' not in route_dir: return route_dir
    route_id, direction_id = route_dir.rsplit('_', 1)
    return route_id if direction_id == '0' else f'{route_id} (dir {direction_id})'

def find_best_path(origin_stop_id, dest_stop_id, depart_tod_min,
                   stop_to_route_dirs, route_to_stop_list, route_stop_pos,
                   base_map, bin_map, bin_size, wait_lookup,
                   max_transfers=4, transfer_penalty_min=TRANSFER_PENALTY_MIN):
    """
    Mencari rute bus Trans Jogja terbaik dari halte asal ke halte tujuan menggunakan algoritma Dijkstra berbasis ETA.
    
    API Input:
    - origin_stop_id (str): ID halte asal keberangkatan.
    - dest_stop_id (str): ID halte tujuan wisata.
    - depart_tod_min (float): Waktu keberangkatan dalam format menit sejak tengah malam.
    
    API Output:
    - dict: Ringkasan rute perjalanan (mencakup jumlah transit, total ETA, dan daftar halte).
    """
    import heapq
    if pd.isna(origin_stop_id) or pd.isna(dest_stop_id): return None
    origin_stop_id = str(origin_stop_id); dest_stop_id = str(dest_stop_id)
    depart_tod_min = float(depart_tod_min); max_transfers = int(max_transfers)
    if origin_stop_id == dest_stop_id:
        return {'path_type': 'walk_only', 'route_path_dirs': [], 'route_path_labels': [],
                'transfer_stop_ids': [], 'board_wait_total_min': 0.0,
                'transfer_extra_min': 0.0, 'in_vehicle_min': 0.0, 'transfers': 0, 'transit_eta_min': 0.0}
    max_boards = max_transfers + 1
    dist, parent = {}, {}
    pq = [(depart_tod_min, origin_stop_id, 0)]
    dist[(origin_stop_id, 0)] = depart_tod_min
    best_arrival = float('inf'); best_dest_state = None
    while pq:
        curr_time, u, b = heapq.heappop(pq)
        if curr_time > dist.get((u, b), float('inf')): continue
        if u == dest_stop_id:
            if curr_time < best_arrival: best_arrival = curr_time; best_dest_state = (u, b)
            continue
        if b >= max_boards: continue
        for rd in stop_to_route_dirs.get(u, []):
            pos_map = route_stop_pos.get(rd, {}); stop_list = route_to_stop_list.get(rd, [])
            if u not in pos_map: continue
            u_idx = pos_map[u]
            wait_time    = lookup_wait_minutes(wait_lookup, curr_time)
            penalty_time = float(transfer_penalty_min) if b > 0 else 0.0
            board_time   = curr_time + wait_time + penalty_time
            current_travel_time = 0.0; current_arr_time = board_time
            for next_idx in range(u_idx, len(stop_list) - 1):
                seg_id = f'{stop_list[next_idx]}->{stop_list[next_idx + 1]}'
                pred = predict_segment_minutes(seg_id, current_arr_time, base_map, bin_map, bin_size)
                if pd.isna(pred): break
                current_travel_time += float(pred); current_arr_time += float(pred)
                v = stop_list[next_idx + 1]; new_b = b + 1
                if current_arr_time < dist.get((v, new_b), float('inf')):
                    dist[(v, new_b)] = current_arr_time
                    parent[(v, new_b)] = (u, b, rd, wait_time, current_travel_time, penalty_time)
                    heapq.heappush(pq, (current_arr_time, v, new_b))
    if best_dest_state is None: return None
    path = []; curr_state = best_dest_state
    total_wait = total_in_vehicle = total_penalty = 0.0
    while curr_state in parent:
        p_u, p_b, p_rd, p_wait, p_in_veh, p_pen = parent[curr_state]
        path.append({'from': p_u, 'to': curr_state[0], 'route': p_rd,
                     'wait': p_wait, 'in_veh': p_in_veh, 'penalty': p_pen})
        total_wait += p_wait; total_in_vehicle += p_in_veh; total_penalty += p_pen
        curr_state = (p_u, p_b)
    path.reverse()
    route_path_dirs   = [step['route'] for step in path]
    route_path_labels = [format_route_dir_label(rd) for rd in route_path_dirs]
    transfer_stop_ids = [step['from'] for step in path[1:]]
    transfers = len(path) - 1
    path_type = 'direct' if transfers == 0 else 'one_transfer' if transfers == 1 else f'{transfers}_transfers'
    return {'path_type': path_type, 'route_path_dirs': route_path_dirs,
            'route_path_labels': route_path_labels, 'transfer_stop_ids': transfer_stop_ids,
            'board_wait_total_min': total_wait, 'transfer_extra_min': total_penalty,
            'in_vehicle_min': total_in_vehicle, 'transfers': transfers,
            'transit_eta_min': total_wait + total_in_vehicle + total_penalty}

def resolve_stop_query(stop_query, stops):
    q = str(stop_query).strip()
    if not q: raise ValueError('stop_query tidak boleh kosong')
    if q in set(stops['stop_id'].astype(str)):
        return stops.loc[stops['stop_id'].astype(str) == q].iloc[0].to_dict()
    q_norm = normalize_text(q)
    exact_name = stops.loc[stops['stop_name'].map(normalize_text) == q_norm]
    if not exact_name.empty: return exact_name.sort_values('stop_name').iloc[0].to_dict()
    contains = stops.loc[stops['stop_name'].map(normalize_text).str.contains(q_norm, regex=False, na=False)]
    if not contains.empty:
        return contains.assign(nl=contains['stop_name'].str.len()).sort_values(['nl', 'stop_name']).iloc[0].drop('nl').to_dict()
    raise ValueError(f'Halte tidak ditemukan: {stop_query}')

def expand_open_days(value):
    if pd.isna(value): return set(DAY_NAMES_ID)
    txt = str(value).strip().replace('\u2013', '-').replace('\u2014', '-')
    if not txt: return set(DAY_NAMES_ID)
    txt_norm = normalize_text(txt)
    if 'setiap hari' in txt_norm or 'senin minggu' in txt_norm: return set(DAY_NAMES_ID)
    day_idx = {normalize_text(d): i for i, d in enumerate(DAY_NAMES_ID)}
    expanded = set()
    for part in re.split(r'[,;/]+|\s+dan\s+', txt):
        part = part.strip()
        if not part: continue
        if '-' in part:
            l, r = [normalize_text(p.strip()) for p in part.split('-', 1)]
            if l in day_idx and r in day_idx:
                li, ri = day_idx[l], day_idx[r]
                expanded.update(DAY_NAMES_ID[li:ri+1] if li <= ri else DAY_NAMES_ID[li:] + DAY_NAMES_ID[:ri+1])
                continue
        pn = normalize_text(part)
        if pn in day_idx: expanded.add(DAY_NAMES_ID[day_idx[pn]])
    return expanded if expanded else set(DAY_NAMES_ID)

def is_open_on_day(open_days, day_name):
    if not day_name: return True
    return day_name in expand_open_days(open_days)

def safe_scale_positive(series):
    s = pd.to_numeric(series, errors='coerce').astype(float)
    if s.notna().sum() == 0: return pd.Series(1.0, index=series.index)
    lo, hi = float(s.min()), float(s.max())
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo: return pd.Series(1.0, index=series.index)
    return (s - lo) / (hi - lo)

def safe_scale_inverse(series):
    return 1.0 - safe_scale_positive(series)

def build_destination_candidate_flags(poi_catalog):
    out = poi_catalog.copy()
    pattern = '|'.join(RECOMMENDER_EXCLUDE_PATTERNS)
    out['name_norm']       = out['name'].map(normalize_text)
    out['is_service_like'] = out['name'].astype(str).str.contains(pattern, case=False, regex=True, na=False)
    out['default_type_ok'] = True
    out['is_destination_candidate'] = (
        out['nearest_stop_id'].notna() & out['default_type_ok'] & (~out['is_service_like'])
    ).astype(int)
    return out

def deduplicate_recommendations(df, distance_threshold_m=150.0, similarity_threshold=0.45):
    if df.empty: return df.copy()
    kept_rows, keep_idx = [], []
    for row in df.itertuples(index=True):
        rname = normalize_text(getattr(row, 'name'))
        rlat, rlon = getattr(row, 'lat'), getattr(row, 'lon')
        is_dup = False
        for prev in kept_rows:
            if any(pd.isna(v) for v in [rlat, rlon, prev['lat'], prev['lon']]): continue
            dist = float(haversine_m(rlat, rlon, prev['lat'], prev['lon']))
            sim  = SequenceMatcher(None, rname, prev['name_norm']).ratio()
            if dist <= distance_threshold_m and sim >= similarity_threshold:
                is_dup = True; break
        if not is_dup:
            keep_idx.append(row.Index)
            kept_rows.append({'lat': rlat, 'lon': rlon, 'name_norm': rname})
    return df.loc[keep_idx].reset_index(drop=True)

def build_recommendation_reason(row):
    route_text   = ('cukup berjalan kaki dari halte asal' if row['path_type'] == 'walk_only'
                    else 'naik ' + ' -> '.join(row['route_path_labels']))
    transit_text = ('tanpa transit' if int(row['transfers']) == 0
                    else f"{int(row['transfers'])} transit via {row['transfer_stop_names_text']}")
    return (f"ETA total {row['eta_total_min']:.1f} menit, {transit_text}, "
            f"jalan kaki akhir {row['walk_dist_m']:.0f} m dari {row['nearest_stop_name']}, "
            f"tiba {row['arrival_hhmm']}, buka {row['open_hhmm']}\u2013{row['close_hhmm']}, "
            f"{route_text}.")

def recommend_destinations(origin_stop_query, depart_hhmm, day_name,
                           poi_catalog, stops, wait_lookup,
                           route_to_stop_list, route_stop_pos, stop_to_route_dirs,
                           base_map, bin_map, bin_size,
                           preferred_types=None, top_k=10,
                           min_stay_min=MIN_STAY_MIN_DEFAULT,
                           require_verified_hours=False, max_transfers=4):
    """
    Menghasilkan daftar rekomendasi destinasi wisata terintegrasi dengan akses Trans Jogja.
    
    API Input:
    - origin_stop_query (str): Nama atau ID halte keberangkatan pengguna.
    - depart_hhmm (str): Jam keberangkatan dalam format 'HH:MM'.
    - day_name (str): Nama hari untuk pengecekan ketersediaan jam buka wisata.
    - preferred_types (list): Kategori wisata yang diminati (opsional).
    
    API Output:
    - DataFrame: Daftar top-K wisata yang direkomendasikan beserta skor kecocokan dan detail rute.
    """
    origin = resolve_stop_query(origin_stop_query, stops)
    depart_tod_min = float(parse_hhmm(depart_hhmm))
    candidates = poi_catalog.copy()
    candidates = candidates[candidates['nearest_stop_id'].notna()].copy()
    if preferred_types:
        pattern = '|'.join(preferred_types)
        candidates = candidates[candidates['type'].str.contains(pattern, case=False, regex=True, na=False)].copy()
    else:
        candidates = candidates[candidates['is_destination_candidate'] == 1].copy()
    if require_verified_hours:
        candidates = candidates[candidates['hours_source_type'] == 'verified_web'].copy()
    stop_name_map = stops.set_index('stop_id')['stop_name'].to_dict()
    rows = []
    for rec in candidates.itertuples(index=False):
        path = find_best_path(origin_stop_id=str(origin['stop_id']),
            dest_stop_id=str(rec.nearest_stop_id), depart_tod_min=depart_tod_min,
            stop_to_route_dirs=stop_to_route_dirs, route_to_stop_list=route_to_stop_list,
            route_stop_pos=route_stop_pos, base_map=base_map, bin_map=bin_map, bin_size=bin_size,
            wait_lookup=wait_lookup, max_transfers=max_transfers, transfer_penalty_min=TRANSFER_PENALTY_MIN)
        if path is None: continue
        walk_min  = float(rec.walk_time_min) if pd.notna(rec.walk_time_min) else 0.0
        walk_m    = float(rec.walk_dist_m)   if pd.notna(rec.walk_dist_m)   else 0.0
        eta_total = float(path['transit_eta_min']) + walk_min
        arr_tod   = depart_tod_min + eta_total
        open_min  = parse_hhmm(rec.open_hhmm)  if pd.notna(rec.open_hhmm)  else 0
        close_min = parse_hhmm(rec.close_hhmm) if pd.notna(rec.close_hhmm) else 1439
        day_open  = is_open_on_day(rec.open_days, day_name)
        open_arr  = bool(day_open and open_min <= arr_tod <= close_min)
        can_visit = bool(day_open and arr_tod + float(min_stay_min) <= close_min)
        margin    = max(float(close_min) - float(arr_tod), 0.0)
        tsids     = path['transfer_stop_ids']
        tsnames   = [stop_name_map.get(s, s) for s in tsids]
        rows.append({
            'origin_stop_id': str(origin['stop_id']), 'origin_stop_name': origin['stop_name'],
            'depart_hhmm': depart_hhmm, 'day_name': day_name,
            'poi_id': int(rec.poi_id), 'name': rec.name, 'type': rec.type,
            'rating': float(rec.rating) if pd.notna(rec.rating) else np.nan,
            'vote_count': float(rec.vote_count) if pd.notna(rec.vote_count) else 0.0,
            'lat': float(rec.lat) if pd.notna(rec.lat) else np.nan,
            'lon': float(rec.lon) if pd.notna(rec.lon) else np.nan,
            'nearest_stop_id': rec.nearest_stop_id, 'nearest_stop_name': rec.nearest_stop_name,
            'walk_dist_m': walk_m, 'walk_time_min': walk_min,
            'path_type': path['path_type'], 'route_path_dirs': path['route_path_dirs'],
            'route_path_labels': path['route_path_labels'],
            'route_path_text': ' > '.join(path['route_path_labels']) if path['route_path_labels'] else 'walk_only',
            'transfer_stop_ids': tsids, 'transfer_stop_names': tsnames,
            'transfer_stop_names_text': ' > '.join(tsnames),
            'transfers': int(path['transfers']),
            'board_wait_total_min': float(path['board_wait_total_min']),
            'transfer_extra_min': float(path['transfer_extra_min']),
            'in_vehicle_min': float(path['in_vehicle_min']),
            'transit_eta_min': float(path['transit_eta_min']),
            'eta_total_min': float(eta_total), 'arrival_hhmm': hhmm_from_minutes(arr_tod),
            'open_hhmm': rec.open_hhmm, 'close_hhmm': rec.close_hhmm, 'open_days': rec.open_days,
            'hours_source_type': rec.hours_source_type,
            'needs_review': int(rec.needs_review) if pd.notna(rec.needs_review) else 0,
            'is_open_on_day': int(day_open), 'is_open_on_arrival': int(open_arr),
            'can_visit_min_stay': int(can_visit), 'visit_margin_min': float(margin),
        })
    out = pd.DataFrame(rows)
    if out.empty: return out
    out = out[out['is_open_on_arrival'] == 1].copy()
    if out.empty: return out
    if int(out['can_visit_min_stay'].sum()) > 0:
        out = out[out['can_visit_min_stay'] == 1].copy()
    denom = max(1, int(max_transfers) + 1)
    out['score_eta']              = safe_scale_inverse(out['eta_total_min'])
    out['score_walk']             = safe_scale_inverse(out['walk_dist_m'].fillna(out['walk_dist_m'].median()))
    out['score_transfers']        = 1.0 - out['transfers'].clip(0, denom) / float(denom)
    out['score_operating_margin'] = safe_scale_positive(out['visit_margin_min'].clip(0, 720))
    out['score_rating']           = safe_scale_positive(out['rating'].fillna(out['rating'].median()))
    out['score_popularity']       = safe_scale_positive(np.log1p(out['vote_count'].fillna(0)))
    out['recommendation_score']   = (
        0.35 * out['score_eta'] + 0.20 * out['score_walk'] + 0.20 * out['score_transfers']
        + 0.10 * out['score_operating_margin'] + 0.10 * out['score_rating']
        + 0.05 * out['score_popularity']
        - 0.03 * out['needs_review'] - 0.05 * (out['vote_count'] < 10).astype(float)
    )
    out = out.sort_values(['recommendation_score', 'rating', 'vote_count', 'eta_total_min'],
                          ascending=[False, False, False, True]).reset_index(drop=True)
    out = deduplicate_recommendations(out)
    out = out.head(int(top_k)).reset_index(drop=True)
    out.insert(0, 'rank', np.arange(1, len(out) + 1))
    out['recommendation_reason'] = out.apply(build_recommendation_reason, axis=1)
    return out

def build_sample_recommendations(poi_catalog, stops, wait_lookup,
                                  route_to_stop_list, route_stop_pos,
                                  stop_to_route_dirs, base_map, bin_map, bin_size):
    scenarios = [
        {'scenario_id': 'malioboro_umum_sabtu_0900', 'origin_stop_query': 'Malioboro 1',
         'depart_hhmm': '09:00', 'day_name': 'Sabtu', 'preferred_types': None, 'top_k': 12},
        {'scenario_id': 'malioboro_budaya_sabtu_0900', 'origin_stop_query': 'Malioboro 1',
         'depart_hhmm': '09:00', 'day_name': 'Sabtu', 'preferred_types': ['Budaya dan Sejarah', 'Museum'], 'top_k': 12},
        {'scenario_id': 'jombor_keluarga_sabtu_0900', 'origin_stop_query': 'Terminal Jombor',
         'depart_hhmm': '09:00', 'day_name': 'Sabtu', 'preferred_types': ['Buatan', 'Wisata Air', 'Museum'], 'top_k': 12},
        {'scenario_id': 'adisutjipto_umum_sabtu_0900', 'origin_stop_query': 'Bandara Adisujtipto',
         'depart_hhmm': '09:00', 'day_name': 'Sabtu', 'preferred_types': None, 'top_k': 12},
    ]
    all_rows, summary_rows = [], []
    for spec in scenarios:
        try:
            rec = recommend_destinations(
                origin_stop_query=spec['origin_stop_query'], depart_hhmm=spec['depart_hhmm'],
                day_name=spec['day_name'], poi_catalog=poi_catalog, stops=stops,
                wait_lookup=wait_lookup, route_to_stop_list=route_to_stop_list,
                route_stop_pos=route_stop_pos, stop_to_route_dirs=stop_to_route_dirs,
                base_map=base_map, bin_map=bin_map, bin_size=bin_size,
                preferred_types=spec['preferred_types'], top_k=spec['top_k'],
                min_stay_min=MIN_STAY_MIN_DEFAULT, require_verified_hours=False, max_transfers=4)
        except Exception as e:
            print(f"[WARN] Skenario {spec['scenario_id']}: {e}")
            rec = pd.DataFrame()
        if rec.empty:
            summary_rows.append({'scenario_id': spec['scenario_id'],
                                 'origin_stop_query': spec['origin_stop_query'],
                                 'depart_hhmm': spec['depart_hhmm'], 'day_name': spec['day_name'],
                                 'result_rows': 0, 'best_eta_min': None,
                                 'avg_top5_score': None, 'all_open_on_arrival': 0,
                                 'all_have_route_or_walk': 0})
            continue
        rec = rec.copy()
        rec['scenario_id'] = spec['scenario_id']
        rec['preferred_types_text'] = ', '.join(spec['preferred_types']) if spec['preferred_types'] else 'semua kategori'
        all_rows.append(rec)
        summary_rows.append({'scenario_id': spec['scenario_id'],
                             'origin_stop_query': spec['origin_stop_query'],
                             'depart_hhmm': spec['depart_hhmm'], 'day_name': spec['day_name'],
                             'result_rows': int(len(rec)), 'best_eta_min': float(rec['eta_total_min'].min()),
                             'avg_top5_score': float(rec['recommendation_score'].head(5).mean()),
                             'all_open_on_arrival': int((rec['is_open_on_arrival'] == 1).all()),
                             'all_have_route_or_walk': int(rec['route_path_text'].notna().all())})
    samples = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    return samples, pd.DataFrame(summary_rows)

def build_recommendation_smoke_tests(recommendation_summary):
    if recommendation_summary.empty:
        return pd.DataFrame([{'test_name': 'sample_recommendations_non_empty',
                               'status': 'FAIL', 'details': 'Tidak ada skenario yang berhasil.'}])
    tests = [
        {'test_name': 'sample_recommendations_non_empty',
         'status': 'PASS' if int(recommendation_summary['result_rows'].sum()) > 0 else 'FAIL',
         'details': f"total_rows={int(recommendation_summary['result_rows'].sum())}"},
        {'test_name': 'every_scenario_has_results',
         'status': 'PASS' if bool((recommendation_summary['result_rows'] >= 5).all()) else 'WARN',
         'details': recommendation_summary[['scenario_id', 'result_rows']].to_json(orient='records', force_ascii=False)},
        {'test_name': 'all_results_open_on_arrival',
         'status': 'PASS' if bool((recommendation_summary['all_open_on_arrival'] == 1).all()) else 'FAIL',
         'details': recommendation_summary[['scenario_id', 'all_open_on_arrival']].to_json(orient='records', force_ascii=False)},
        {'test_name': 'all_results_have_route_or_walk',
         'status': 'PASS' if bool((recommendation_summary['all_have_route_or_walk'] == 1).all()) else 'FAIL',
         'details': recommendation_summary[['scenario_id', 'all_have_route_or_walk']].to_json(orient='records', force_ascii=False)},
    ]
    return pd.DataFrame(tests)

print('Semua fungsi bantu dimuat.')


########################################

# CELL_IDX: 16
stop_times  = normalize_trip_times(stop_times_raw)
stop_events = build_stop_events(stop_times)
segments    = build_segments(stop_times, stops)
wait_lookup = build_wait_lookup(stop_events)

place_hours = poi[['poi_id']].copy()
place_hours['open_hhmm']         = poi['jam_buka']
place_hours['close_hhmm']        = poi['jam_tutup']
place_hours['open_days']         = poi['hari_operasional']
place_hours['hours_detail']      = poi.get('catatan_jam', '')
place_hours['hours_source_type'] = 'wisata_jogja_csv'
place_hours['needs_review']      = 0

poi_nearest = nearest_stop_for_pois(poi, stops)

# [BARU] Winsorizing per-segmen
segments_w = winsorize_segments_per_segment(segments, lower_q=0.05, upper_q=0.95, min_obs=10)

print(f'\nPerbandingan distribusi sebelum vs sesudah winsorizing:')
print(f'  Mean  : {segments["travel_time_min"].mean():.3f} → {segments_w["travel_time_min_w"].mean():.3f} menit')
print(f'  Median: {segments["travel_time_min"].median():.3f} → {segments_w["travel_time_min_w"].median():.3f} menit')
print(f'  Std   : {segments["travel_time_min"].std():.3f} → {segments_w["travel_time_min_w"].std():.3f} menit')


########################################

# CELL_IDX: 17
route_sequences, route_sequence_summary = build_route_sequences(stop_times, stops)
print(f'Route sequences: {len(route_sequence_summary)} koridor-arah')
display(route_sequence_summary.head(8))

poi_catalog = (
    poi.rename(columns={'nama': 'name', 'vote_average': 'rating',
                        'vote_count': 'vote_count', 'latitude': 'lat', 'longitude': 'lon'})
    [['poi_id', 'name', 'type', 'rating', 'vote_count', 'lat', 'lon', 'description']]
    .merge(place_hours, on='poi_id', how='left')
    .merge(poi_nearest, on='poi_id', how='left')
)
poi_catalog = build_destination_candidate_flags(poi_catalog)
poi_nearest_final = nearest_stop_for_pois(poi, stops)
poi_catalog = (
    poi_catalog.drop(columns=[c for c in
        ['nearest_stop_id', 'nearest_stop_name', 'stop_lat', 'stop_lon', 'walk_dist_m', 'walk_time_min']
        if c in poi_catalog.columns])
    .merge(poi_nearest_final, on='poi_id', how='left')
)
poi_catalog = build_destination_candidate_flags(poi_catalog)
poi_catalog_verified = poi_catalog.copy()
n_candidates = int((poi_catalog_verified['is_destination_candidate'] == 1).sum())
print(f'Pool Rekomendasi: {n_candidates} kandidat aktif dari {len(poi_catalog)} total POI')


########################################

# CELL_IDX: 20
train_seg, val_seg = split_train_val_segments(segments_w)
print(f'Data segmen  : {len(segments_w):,} baris ({segments_w["segment_id"].nunique():,} unik)')
print(f'  Latih      : {len(train_seg):,} ({len(train_seg)/len(segments_w)*100:.0f}%)')
print(f'  Validasi   : {len(val_seg):,} ({len(val_seg)/len(segments_w)*100:.0f}%)')

print('\nMemulai grid search 5-Fold CV...')
print('Dioptimasi untuk RMSE (bukan hanya MAE)')
print('Filter: hanya segmen yang ada di training yang dievaluasi')
grid_res_cv, best_cv = grid_search_cv(segments_w, n_folds=5, value_col='travel_time_min_w')

best_bin   = int(best_cv['bin_size'])
best_K     = float(best_cv['K'])
best_min_n = int(best_cv['min_bin_n'])

print(f'\nParameter terpilih (5-Fold CV, optimasi RMSE):')
print(f'  bin_size      = {best_bin} menit')
print(f'  K             = {best_K}')
print(f'  min_bin_n     = {best_min_n}')
print(f'  CV RMSE mean  = {best_cv["cv_rmse_mean"]:.4f} menit')
print(f'  CV RMSE std   = {best_cv["cv_rmse_std"]:.4f} menit')
print(f'  CV MAE mean   = {best_cv["cv_mae_mean"]:.4f} menit')
print(f'\nTop 10 kombinasi parameter terbaik (CV, sort by RMSE):')
display(grid_res_cv.head(10))


########################################

# CELL_IDX: 21
# Lookup berbasis train saja (untuk evaluasi hold-out)
base_lookup_train, bin_lookup_train = build_segment_lookup(
    train_seg, bin_size=best_bin, K=best_K, min_bin_n=best_min_n, value_col='travel_time_min_w')

# Lookup final berbasis seluruh data (untuk deployment)
base_lookup, bin_lookup = build_segment_lookup(
    segments_w, bin_size=best_bin, K=best_K, min_bin_n=best_min_n, value_col='travel_time_min_w')
print(f'Lookup ETA final: {len(base_lookup)} segmen, {len(bin_lookup)} time-bin entries')


########################################

# CELL_IDX: 22
base_map, bin_map = build_segment_prediction_maps(base_lookup, bin_lookup)
route_to_stop_list, route_stop_pos, stop_to_route_dirs = build_route_lookup_maps(route_sequences)

recommendation_samples, recommendation_summary = build_sample_recommendations(
    poi_catalog=poi_catalog_verified, stops=stops, wait_lookup=wait_lookup,
    route_to_stop_list=route_to_stop_list, route_stop_pos=route_stop_pos,
    stop_to_route_dirs=stop_to_route_dirs, base_map=base_map, bin_map=bin_map, bin_size=best_bin)

print('Ringkasan skenario rekomendasi:')
display(recommendation_summary)


########################################

# CELL_IDX: 24
val_pred  = predict_segments(val_seg, base_lookup_train, bin_lookup_train, bin_size=best_bin)

# [PERBAIKAN] Hanya evaluasi segmen yang ada di training
# Ini mencegah segmen yang tidak pernah muncul di training (prediksi NaN/fallback jauh)
# dari mengontaminasi metrik evaluasi
seen_in_train = set(base_lookup_train['segment_id'])
val_pred_seen = val_pred[val_pred['segment_id'].isin(seen_in_train)].copy()
usable_all    = val_pred.dropna(subset=['pred_min', 'travel_time_min']).copy()
usable        = val_pred_seen.dropna(subset=['pred_min', 'travel_time_min']).copy()

n_unseen = int(len(val_pred)) - int(len(val_pred_seen))
print(f'Validasi total      : {len(val_pred):,} baris')
print(f'  Segmen tak dikenal: {n_unseen:,} baris (diprediksi via route-fallback)')
print(f'  Digunakan evaluasi: {len(usable):,} baris (segmen ada di training)')

metrics = {
    'model_version'     : 'v1 (winsorize_per_seg + 5fold_cv + route_fallback + capping)',
    'best_params'       : {'bin_size': best_bin, 'K': best_K, 'min_bin_n': best_min_n},
    'cv_rmse_mean'      : float(best_cv['cv_rmse_mean']),
    'cv_rmse_std'       : float(best_cv['cv_rmse_std']),
    'cv_mae_mean'       : float(best_cv['cv_mae_mean']),
    'cv_mae_std'        : float(best_cv['cv_mae_std']),
    'val_mae_min'       : mae(usable['travel_time_min'], usable['pred_min'])    if not usable.empty else None,
    'val_rmse_min'      : rmse(usable['travel_time_min'], usable['pred_min'])   if not usable.empty else None,
    'val_mae_all'       : mae(usable_all['travel_time_min'], usable_all['pred_min'])  if not usable_all.empty else None,
    'val_rmse_all'      : rmse(usable_all['travel_time_min'], usable_all['pred_min']) if not usable_all.empty else None,
    'segments_total'    : int(len(segments_w)),
    'segments_unique'   : int(segments_w['segment_id'].nunique()),
    'val_rows_usable'   : int(len(usable)),
    'val_rows_total'    : int(len(usable_all)),
    'val_unseen_segs'   : n_unseen,
    'winsorize_params'  : {'lower_q': 0.05, 'upper_q': 0.95, 'min_obs': 10},
}

print('\n' + '=' * 65)
print('Evaluasi Akurasi Model ETA — ')
print('=' * 65)
if metrics['val_mae_min'] is not None:
    print(f"  MAE  (segmen dikenal)    : {metrics['val_mae_min']:.4f} menit")
    print(f"  RMSE (segmen dikenal)    : {metrics['val_rmse_min']:.4f} menit")
    print(f"  MAE  (semua, incl. unseen): {metrics['val_mae_all']:.4f} menit")
    print(f"  RMSE (semua, incl. unseen): {metrics['val_rmse_all']:.4f} menit")
    print(f"  ---")
    print(f"  CV RMSE mean  : {metrics['cv_rmse_mean']:.4f} menit")
    print(f"  CV RMSE std   : {metrics['cv_rmse_std']:.4f} menit")
    print(f"  CV MAE mean   : {metrics['cv_mae_mean']:.4f} menit")
print(f"  Segmen unik    : {metrics['segments_unique']:,}")
print(f"  Evaluasi pada  : {metrics['val_rows_usable']:,} baris (segmen dikenal)")
print(f"  Unseen segs    : {metrics['val_unseen_segs']:,} baris (route-fallback)")
print(f"  Parameter      : bin_size={best_bin}, K={best_K}, min_bin_n={best_min_n}")


########################################

# CELL_IDX: 25
# Breakdown error per rute
if not usable.empty and 'route_id' in usable.columns:
    usable['abs_err'] = np.abs(usable['travel_time_min'] - usable['pred_min'])
    route_err = usable.groupby('route_id')['abs_err'].agg(MAE='mean', N='size').sort_values('MAE', ascending=False)
    print('Breakdown MAE per Rute (5 terburuk):')
    display(route_err.head())
    print('Breakdown MAE per Rute (5 terbaik):')
    display(route_err.tail())


########################################

# CELL_IDX: 26
smoke_tests = build_recommendation_smoke_tests(recommendation_summary)
print('Hasil Smoke Tests Sistem Rekomendasi:')
display(smoke_tests)
passed = int((smoke_tests['status'] == 'PASS').sum())
total  = len(smoke_tests)
print(f'\nRingkasan: {passed}/{total} test lulus')
if passed == total:
    print('Semua smoke tests lulus. Sistem siap untuk deployment.')
else:
    failed = smoke_tests[smoke_tests['status'] != 'PASS']
    for _, row in failed.iterrows():
        print(f"  - {row['test_name']}: {row['status']}")


########################################

# CELL_IDX: 29
stop_routes = (
    stop_times
    .assign(route_dir=stop_times['route_id'].astype(str) + '-' + stop_times['direction_id'].astype(int).astype(str))
    .groupby('stop_id', as_index=False)['route_dir']
    .agg(lambda x: sorted(pd.unique(x).tolist()))
    .rename(columns={'route_dir': 'routes'})
)
schedule_route_ids = sorted(stop_times['route_id'].astype(str).str.upper().unique().tolist())
route_kml_ids      = sorted(route_summary['route_id'].astype(str).str.upper().unique().tolist())
missing_routes     = sorted(set(schedule_route_ids) - set(route_kml_ids))
route_fc = {
    'type': 'FeatureCollection',
    'features': [f for f in route_fc_all['features']
                 if f['properties']['route_id'] in set(schedule_route_ids)],
}
recommendation_config = {
    'max_transfers': 3, 'transfer_penalty_min': TRANSFER_PENALTY_MIN,
    'min_stay_min': MIN_STAY_MIN_DEFAULT, 'default_types': RECOMMENDER_DEFAULT_TYPES,
    'exclude_patterns': RECOMMENDER_EXCLUDE_PATTERNS,
    'score_weights': {'eta_total': 0.35, 'walk_distance': 0.20, 'transfers': 0.20,
                      'operating_margin': 0.10, 'rating': 0.10, 'popularity': 0.05,
                      'needs_review_penalty': -0.03, 'low_vote_penalty': -0.05},
    'model_params': {'winsorize_lower_q': 0.05, 'winsorize_upper_q': 0.95,
                             'winsorize_min_obs': 10, 'cv_folds': 5},
}

route_summary.to_csv(PRE_DIR / 'kml_routes.csv', index=False)
kml_stop_points.to_csv(PRE_DIR / 'kml_stop_points.csv', index=False)
stops.to_csv(PRE_DIR / 'stops.csv', index=False)
stop_times.to_csv(PRE_DIR / 'stop_times.csv', index=False)
stop_events.to_csv(PRE_DIR / 'stop_events.csv', index=False)
segments_w.to_csv(PRE_DIR / 'segments_training.csv', index=False)
place_hours.to_csv(PRE_DIR / 'place_hours.csv', index=False)
poi_nearest_final.to_csv(PRE_DIR / 'poi_to_nearest_stop_1km.csv', index=False)
route_sequences.to_csv(PRE_DIR / 'route_sequences.csv', index=False)
route_sequence_summary.to_csv(PRE_DIR / 'route_sequence_summary.csv', index=False)

base_lookup.to_csv(MODEL_DIR / 'eta_lookup_segment_mean.csv', index=False)
bin_lookup.to_csv(MODEL_DIR / 'eta_lookup_segment_bin_smoothed.csv', index=False)
wait_lookup.to_csv(MODEL_DIR / 'wait_time_by_hour.csv', index=False)
with open(MODEL_DIR / 'model_metrics.json', 'w', encoding='utf-8') as f:
    json.dump(metrics, f, indent=2)
with open(MODEL_DIR / 'recommendation_config.json', 'w', encoding='utf-8') as f:
    json.dump(recommendation_config, f, ensure_ascii=False, indent=2)

grid_res_cv.to_csv(REPORT_DIR / 'ml_grid_search_results.csv', index=False)
recommendation_summary.to_csv(REPORT_DIR / 'recommendation_summary.csv', index=False)
with open(REPORT_DIR / 'kml_shape_missing_routes.json', 'w', encoding='utf-8') as f:
    json.dump(missing_routes, f, indent=2)

stops[['stop_id', 'stop_name', 'lat', 'lon']].to_json(
    WEB_DIR / 'stops.json', orient='records', force_ascii=False, indent=2)
with open(WEB_DIR / 'stop_routes.json', 'w', encoding='utf-8') as f:
    json.dump(to_json_records(stop_routes), f, ensure_ascii=False, indent=2)
stop_events.to_csv(WEB_DIR / 'stop_board_departures.csv', index=False)
with open(WEB_DIR / 'routes_geojson_by_route_id.json', 'w', encoding='utf-8') as f:
    json.dump(route_fc, f, ensure_ascii=False, indent=2)
poi_catalog_verified.to_csv(WEB_DIR / 'poi_catalog.csv', index=False)
with open(WEB_DIR / 'poi_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(to_json_records(poi_catalog_verified), f, ensure_ascii=False, indent=2)
place_hours.to_csv(WEB_DIR / 'poi_opening_hours.csv', index=False)
if not recommendation_samples.empty:
    recommendation_samples.to_csv(WEB_DIR / 'recommendation_samples.csv', index=False)
    with open(WEB_DIR / 'recommendation_samples.json', 'w', encoding='utf-8') as f:
        json.dump(to_json_records(recommendation_samples), f, ensure_ascii=False, indent=2)
with open(WEB_DIR / 'recommendation_defaults.json', 'w', encoding='utf-8') as f:
    json.dump(recommendation_config, f, ensure_ascii=False, indent=2)

print('Deployment selesai. Artefak tersimpan di preprocessed/, model/, web_artifacts/, report/')
print(f'MAE akhir: {metrics["val_mae_min"]:.3f} menit | RMSE: {metrics["val_rmse_min"]:.3f} menit')


########################################

