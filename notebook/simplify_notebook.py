import json
import re

def update_notebook():
    file_path = 'transjogja_CRISP_DM.ipynb'
    with open(file_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
            
        source = "".join(cell['source'])
        
        # 1. nearest_stop_for_pois
        if 'def nearest_stop_for_pois' in source:
            new_func = '''def nearest_stop_for_pois(poi, stops, max_dist_m=1200.0):
    """
    Mencari halte terdekat untuk setiap destinasi wisata (POI).
    Menggunakan perhitungan jarak Haversine (vektorisasi numpy).
    """
    results = []
    valid_stops = stops.dropna(subset=['lat', 'lon'])
    lat_stops = valid_stops['lat'].values
    lon_stops = valid_stops['lon'].values
    
    for _, row in poi.iterrows():
        lat_poi = row.get('latitude')
        lon_poi = row.get('longitude')
        poi_id = row.get('poi_id')
        
        if pd.isna(lat_poi) or pd.isna(lon_poi):
            results.append({'poi_id': poi_id, 'nearest_stop_id': np.nan, 'nearest_stop_name': np.nan, 'walk_dist_m': np.nan, 'walk_time_min': np.nan})
            continue
            
        dists = haversine_m(lat_poi, lon_poi, lat_stops, lon_stops)
        min_idx = np.argmin(dists)
        min_dist = dists[min_idx]
        
        if min_dist <= max_dist_m:
            ns = valid_stops.iloc[min_idx]
            results.append({
                'poi_id': poi_id, 'nearest_stop_id': ns['stop_id'], 'nearest_stop_name': ns['stop_name'],
                'walk_dist_m': min_dist, 'walk_time_min': min_dist / 80.0
            })
        else:
            results.append({'poi_id': poi_id, 'nearest_stop_id': np.nan, 'nearest_stop_name': np.nan, 'walk_dist_m': np.nan, 'walk_time_min': np.nan})
            
    return pd.DataFrame(results)'''
            source = re.sub(r'def nearest_stop_for_pois\(.*?\):.*?(?=def |\Z)', new_func + '\n\n', source, flags=re.DOTALL)
            
        # 2. deduplicate_recommendations
        if 'def deduplicate_recommendations' in source:
            new_func = '''def deduplicate_recommendations(df, distance_threshold_m=150.0, similarity_threshold=0.45):
    """
    Menghapus destinasi wisata duplikat berdasarkan kemiripan nama dan kedekatan jarak.
    """
    if df.empty:
        return df.copy()
        
    kept_rows, keep_idx = [], []
    for row in df.itertuples(index=True):
        rname = normalize_text(getattr(row, 'name'))
        rlat = getattr(row, 'lat')
        rlon = getattr(row, 'lon')
        is_dup = False
        
        for prev in kept_rows:
            if pd.isna(rlat) or pd.isna(rlon) or pd.isna(prev['lat']) or pd.isna(prev['lon']):
                continue
            dist = float(haversine_m(rlat, rlon, prev['lat'], prev['lon']))
            sim = SequenceMatcher(None, rname, prev['name_norm']).ratio()
            
            if dist <= distance_threshold_m and sim >= similarity_threshold:
                is_dup = True
                break
                
        if not is_dup:
            keep_idx.append(row.Index)
            kept_rows.append({'lat': rlat, 'lon': rlon, 'name_norm': rname})
            
    return df.loc[keep_idx].reset_index(drop=True)'''
            source = re.sub(r'def deduplicate_recommendations\(.*?\):.*?(?=def |\Z)', new_func + '\n\n', source, flags=re.DOTALL)
            
        # 3. haversine_m
        if 'def haversine_m' in source:
            new_func = '''def haversine_m(lat1, lon1, lat2, lon2):
    """
    Menghitung jarak bumi menggunakan formula Haversine. 
    Menerima input tunggal maupun array (vektorisasi).
    """
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return 6_371_000.0 * 2 * np.arcsin(np.sqrt(a))'''
            source = re.sub(r'def haversine_m\(.*?\):.*?(?=def |\Z)', new_func + '\n\n', source, flags=re.DOTALL)

        # 4. normalize_text
        if 'def normalize_text' in source:
            new_func = '''def normalize_text(text):
    """
    Menormalkan teks ke huruf kecil dan menghapus karakter khusus.
    """
    if pd.isna(text): 
        return ''
    text = str(text).lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]', '', text)'''
            source = re.sub(r'def normalize_text\(.*?\):.*?(?=def |\Z)', new_func + '\n\n', source, flags=re.DOTALL)
            
        # 5. recommend_destinations
        if 'def recommend_destinations' in source:
            new_func = '''def recommend_destinations(origin_stop_query, depart_hhmm, day_name, poi_catalog, stops, wait_lookup, route_to_stop_list, route_stop_pos, stop_to_route_dirs, base_map, bin_map, bin_size, preferred_types=None, top_k=10, min_stay_min=MIN_STAY_MIN_DEFAULT, require_verified_hours=False, max_transfers=4):
    """
    Sistem Rekomendasi Destinasi Wisata Terintegrasi Trans Jogja.
    
    Fungsi utama untuk menghasilkan daftar rekomendasi. 
    Tahapan:
    1. Filter POI berdasarkan jam operasional dan hari buka.
    2. Hitung ETA dan rute terbaik menggunakan Dijkstra (find_best_path).
    3. Normalisasi skor (Skor Jarak, Skor Waktu, Skor Transfer).
    4. Pembobotan kriteria dan pengurutan rekomendasi terbaik.
    """
    # 1. Resolusi asal dan parameter
    origin = resolve_stop_query(origin_stop_query, stops)
    depart_tod_min = float(parse_hhmm(depart_hhmm))
    candidates = poi_catalog.copy()
    
    # 2. Filter kandidat wisata yang valid
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
    
    # 3. Hitung Rute dan ETA ke masing-masing destinasi
    for rec in candidates.itertuples(index=False):
        path = find_best_path(
            origin_stop_id=str(origin['stop_id']), dest_stop_id=str(rec.nearest_stop_id), 
            depart_tod_min=depart_tod_min, stop_to_route_dirs=stop_to_route_dirs, 
            route_to_stop_list=route_to_stop_list, route_stop_pos=route_stop_pos, 
            base_map=base_map, bin_map=bin_map, bin_size=bin_size, wait_lookup=wait_lookup, 
            max_transfers=max_transfers, transfer_penalty_min=TRANSFER_PENALTY_MIN
        )
        if path is None: 
            continue
            
        walk_min = float(rec.walk_time_min) if pd.notna(rec.walk_time_min) else 0.0
        walk_m = float(rec.walk_dist_m) if pd.notna(rec.walk_dist_m) else 0.0
        eta_total = float(path['transit_eta_min']) + walk_min
        arr_tod = depart_tod_min + eta_total
        
        open_min = parse_hhmm(rec.open_hhmm) if pd.notna(rec.open_hhmm) else 0
        close_min = parse_hhmm(rec.close_hhmm) if pd.notna(rec.close_hhmm) else 1439
        day_open = is_open_on_day(rec.open_days, day_name)
        
        open_arr = bool(day_open and open_min <= arr_tod <= close_min)
        can_visit = bool(day_open and arr_tod + float(min_stay_min) <= close_min)
        margin = max(float(close_min) - float(arr_tod), 0.0)
        
        tsids = path['transfer_stop_ids']
        tsnames = [stop_name_map.get(s, s) for s in tsids]
        
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
    
    # 4. Filter akhir dan Pembobotan Skor
    out = out[out['is_open_on_arrival'] == 1].copy()
    if out.empty: return out
    if int(out['can_visit_min_stay'].sum()) > 0:
        out = out[out['can_visit_min_stay'] == 1].copy()
        
    denom = max(1, int(max_transfers) + 1)
    out['score_eta'] = safe_scale_inverse(out['eta_total_min'])
    out['score_walk'] = safe_scale_inverse(out['walk_dist_m'].fillna(out['walk_dist_m'].median()))
    out['score_transfers'] = 1.0 - out['transfers'].clip(0, denom) / float(denom)
    out['score_operating_margin'] = safe_scale_positive(out['visit_margin_min'].clip(0, 720))
    out['score_rating'] = safe_scale_positive(out['rating'].fillna(out['rating'].median()))
    out['score_popularity'] = safe_scale_positive(np.log1p(out['vote_count'].fillna(0)))
    
    out['recommendation_score'] = (
        0.35 * out['score_eta'] + 0.20 * out['score_walk'] + 0.20 * out['score_transfers'] +
        0.10 * out['score_operating_margin'] + 0.10 * out['score_rating'] +
        0.05 * out['score_popularity'] - 0.03 * out['needs_review'] - 0.05 * (out['vote_count'] < 10).astype(float)
    )
    
    return deduplicate_recommendations(out.sort_values('recommendation_score', ascending=False)).head(top_k).reset_index(drop=True)'''
            source = re.sub(r'def recommend_destinations\(.*?\):.*?(?=def |\Z)', new_func + '\n\n', source, flags=re.DOTALL)

        # Write back to cell
        lines = [line + '\n' for line in source.split('\n')]
        if lines:
            lines[-1] = lines[-1].rstrip('\n')
        cell['source'] = lines

    with open('transjogja_CRISP_DM.ipynb', 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

if __name__ == '__main__':
    update_notebook()
