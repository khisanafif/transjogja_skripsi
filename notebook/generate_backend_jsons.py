import pandas as pd
import json
import os
import shutil

PRE_DIR = "c:/Users/User/Downloads/transjogja_skripsi/notebook/preprocessed"
MOD_DIR = "c:/Users/User/Downloads/transjogja_skripsi/notebook/model"
WEB_DIR = "c:/Users/User/Downloads/transjogja_skripsi/notebook/web_artifacts"
DATA_DIR = "c:/Users/User/Downloads/transjogja_skripsi/app/backend/data"

print("Generating backend JSONs...")

# 1. eta_lookup.json
try:
    eta_df = pd.read_csv(f"{MOD_DIR}/eta_lookup_segment_mean.csv")
    eta_dict = {}
    for _, row in eta_df.iterrows():
        eta_dict[row['segment_id']] = {
            'seg_median_min': float(row['seg_median_min']),
            'seg_n': int(row['seg_n'])
        }
    with open(f"{DATA_DIR}/eta_lookup.json", "w") as f:
        json.dump(eta_dict, f)
    print("eta_lookup.json created.")
except Exception as e:
    print("Error eta_lookup:", e)

# 2. route_sequences.json
try:
    rseq_df = pd.read_csv(f"{PRE_DIR}/route_sequences.csv")
    stops_df = pd.read_csv(f"{PRE_DIR}/stops.csv")
    stops_map = {row['stop_id']: {'stop_name': row['stop_name'], 'lat': row['lat'], 'lon': row['lon']} for _, row in stops_df.iterrows()}
    
    rseq_dict = {}
    for route_dir, group in rseq_df.groupby('route_dir'):
        rid, did = route_dir.split('_')
        stops = []
        for _, row in group.sort_values('stop_sequence_canonical').iterrows():
            sid = row['stop_id']
            if sid in stops_map:
                stops.append({
                    'stop_id': sid,
                    'stop_name': stops_map[sid]['stop_name'],
                    'seq': int(row['stop_sequence_canonical']),
                    'lat': float(stops_map[sid]['lat']),
                    'lon': float(stops_map[sid]['lon'])
                })
        rseq_dict[route_dir] = {
            'route_id': rid,
            'direction_id': int(did),
            'stops': stops
        }
    with open(f"{DATA_DIR}/route_sequences.json", "w") as f:
        json.dump(rseq_dict, f)
    print("route_sequences.json created.")
except Exception as e:
    print("Error route_sequences:", e)

# 3. wait_time_lookup.json
try:
    wait_df = pd.read_csv(f"{MOD_DIR}/wait_time_by_hour.csv")
    wait_dict = {}
    for _, row in wait_df.iterrows():
        sid = row['stop_id']
        rid = row['route_id']
        hr = str(int(row['hour']))
        val = float(row['mean_wait_time_min'])
        if sid not in wait_dict: wait_dict[sid] = {}
        if rid not in wait_dict[sid]: wait_dict[sid][rid] = {}
        wait_dict[sid][rid][hr] = val
    with open(f"{DATA_DIR}/wait_time_lookup.json", "w") as f:
        json.dump(wait_dict, f)
    print("wait_time_lookup.json created.")
except Exception as e:
    print("Error wait_time_lookup:", e)

# Copy stops.json directly
try:
    shutil.copy(f"{WEB_DIR}/stops.json", f"{DATA_DIR}/stops.json")
    print("stops.json copied.")
except Exception as e:
    print("Error stops.json:", e)

# routes_geojson.json (from routes_geojson_by_route_id.json)
try:
    shutil.copy(f"{WEB_DIR}/routes_geojson_by_route_id.json", f"{DATA_DIR}/routes_geojson.json")
    print("routes_geojson.json copied.")
except Exception as e:
    print("Error routes_geojson:", e)

# route_avg_eta.json (from model_metrics.json?)
# wait let's just make a dummy or pull from wait_time_by_hour?
# route_avg_eta.json is used for average route eta. We will just load the old one and keep it.
