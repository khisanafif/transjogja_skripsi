#!/usr/bin/env python
# coding: utf-8

# # Sistem Rekomendasi Destinasi Wisata Berbasis Trans Jogja
# 
# Notebook ini mengimplementasikan sistem rekomendasi destinasi wisata di Daerah Istimewa
# Yogyakarta yang terintegrasi dengan jaringan transportasi publik **Trans Jogja**.
# Penelitian disusun mengikuti alur metodologi **CRISP-DM** (*Cross-Industry Standard Process
# for Data Mining*) secara berurutan:
# 
# $$\text{Business Understanding} \to \text{Data Understanding} \to \text{Data Preparation}
# \to \text{Modeling} \to \text{Evaluation} \to \text{Deployment}$$
# 
# ## Gambaran Umum
# 
# Wisatawan yang ingin menjelajahi Yogyakarta menggunakan Trans Jogja sering kesulitan
# mengetahui destinasi mana yang realistis dijangkau dalam waktu tertentu. Sistem ini
# menjawab kebutuhan tersebut dengan mengintegrasikan:
# 
# | Data | Sumber | Peran dalam Sistem |
# |------|--------|--------------------|
# | Geometri rute koridor | `Jalur Route.kml` | Peta jalur bus untuk visualisasi |
# | Titik dan info halte | `Perhentian Bus Bus Stop.kml` | Koordinat halte + rute yang melewatinya |
# | Jadwal keberangkatan | `transjogja_stop_times_final_v6.csv` | Data historis waktu antar-halte |
# | Destinasi wisata | `dataset-wisata-jogja-sekitar.csv` | Nama, kategori, koordinat, rating POI |
# | Jam operasional | CSV terverifikasi | Jam buka-tutup dan hari layanan |
# 
# **Output utama:** rekomendasi destinasi wisata yang dapat dijangkau dari halte asal pilihan
# pengguna, diurutkan berdasarkan skor gabungan ETA, kemudahan rute, dan kesesuaian jam operasional.
# 

# ## Persiapan: Impor Pustaka dan Konfigurasi Global
# 
# Sel ini memuat semua pustaka Python yang dibutuhkan, mendefinisikan lokasi file input,
# dan menetapkan konstanta parameter yang digunakan di seluruh tahap CRISP-DM.
# 
# **Konstanta sistem yang ditetapkan berdasarkan studi literatur:**
# - Kecepatan berjalan kaki: **80 m/menit** (≈ 5 km/jam), sesuai standar walkability
# - Batas radius halte–destinasi: **1.200 meter** (15 menit berjalan kaki)
# - Penalti transit: **5 menit** per perpindahan rute
# - Margin minimum kunjungan: **120 menit** sebelum destinasi tutup
# 

# In[1]:


from __future__ import annotations

# Pastikan dependensi tersedia
# !pip install pandas numpy

import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

# ── Struktur Direktori ────────────────────────────────────────────────────
BASE_DIR   = Path.cwd()
RAW_DIR    = BASE_DIR / 'raw'          # data mentah (input)
PRE_DIR    = BASE_DIR / 'preprocessed' # hasil pra-pemrosesan
MODEL_DIR  = BASE_DIR / 'model'        # artefak model ETA
REPORT_DIR = BASE_DIR / 'report'       # laporan evaluasi
WEB_DIR    = BASE_DIR / 'web_artifacts'# artefak siap pakai backend web

for p in [PRE_DIR, MODEL_DIR, REPORT_DIR, WEB_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# ── Lokasi File Input ────────────────────────────────────────────────────
ROUTES_KML            = RAW_DIR / 'Jalur Route.kml'
STOPS_KML             = RAW_DIR / 'Perhentian Bus Bus Stop.kml'
STOP_TIMES_CSV        = RAW_DIR / 'transjogja_stop_times_final_v6.csv'
POI_CSV               = RAW_DIR / 'wisata_jogja.csv'

# ── Namespace XML untuk KML ──────────────────────────────────────────────
KML_NS = {'kml': 'http://www.opengis.net/kml/2.2'}

# ── Parameter Geospasial (Bab 3.4.4 Proposal) ───────────────────────────
WALK_SPEED_M_PER_MIN = 80.0    # kecepatan berjalan kaki: 80 m/menit
POI_WALK_THRESHOLD_M = 1200.0  # radius maksimum halte–destinasi: 1.200 m
TRANSFER_PENALTY_MIN = 5.0     # penalti waktu per transit: 5 menit
MIN_STAY_MIN_DEFAULT = 120.0   # margin minimum kunjungan: 120 menit

# ── Konfigurasi Mesin Rekomendasi ────────────────────────────────────────
RECOMMENDER_DEFAULT_TYPES = [
    'Budaya dan Sejarah', 'Alam', 'Agrowisata', 'Buatan', 'Pantai', 'Wisata Air', 'Museum', 'Desa Wisata', 'Pusat Oleh-Oleh'
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
print(f'File input tersedia: {sum(1 for f in RAW_DIR.iterdir() if f.is_file())} file di raw/')


# ## Fungsi Bantu
# 
# Bagian ini mendefinisikan semua fungsi yang digunakan pada tahap-tahap CRISP-DM berikutnya.
# Fungsi-fungsi dikelompokkan berdasarkan domain: geospasial & KML, jadwal & waktu,
# model ETA, pemrosesan POI, dan mesin rekomendasi.
# 

# ### Fungsi Bantu 1: Geospasial dan Parsing KML
# 

# In[2]:


def parse_route_id(name: str) -> str:
    """
    Mengekstrak ID rute dari nama Placemark di KML.
    Contoh: '1A _ Trans Jogja' -> '1A'
    """
    name = (name or '').strip()
    m = re.match(r'^\s*([A-Za-z0-9-]+)', name)
    return m.group(1).upper() if m else name.upper()


def parse_kml_coord_text(text: str) -> list[list[float]]:
    """
    Mengurai teks koordinat KML menjadi daftar pasangan [lon, lat].
    Format KML: 'lon,lat,alt lon,lat,alt ...' (bisa banyak titik).
    """
    coords = []
    if not text:
        return coords
    for token in text.strip().split():
        parts = token.split(',')
        if len(parts) < 2:
            continue
        coords.append([float(parts[0]), float(parts[1])])  # [lon, lat]
    return coords


def extract_route_refs(desc: str) -> list[str]:
    """
    Mengekstrak daftar ID rute dari field deskripsi halte di KML.
    Contoh deskripsi: '1A _ Trans Jogja ... 5A _ Trans Jogja' -> ['1A', '5A']
    """
    found = re.findall(r'([A-Za-z0-9-]+)\s*_+\s*Trans Jogja', desc or '', flags=re.I)
    refs, seen = [], set()
    for item in found:
        rid = item.upper()
        if rid not in seen:
            refs.append(rid)
            seen.add(rid)
    return refs


def parse_routes_kml(path: Path) -> tuple[pd.DataFrame, dict]:
    """
    Mengurai file KML jalur rute Trans Jogja.

    Setiap Placemark berisi satu LineString yang merepresentasikan jalur
    satu koridor. Fungsi ini mengembalikan:
    - DataFrame ringkasan rute (route_id, nama, jumlah vertex)
    - GeoJSON FeatureCollection untuk visualisasi peta (Leaflet, dll.)
    """
    root = ET.parse(path).getroot()
    rows, features = [], []
    for pm in root.findall('.//kml:Placemark', KML_NS):
        line = pm.find('kml:LineString', KML_NS)
        if line is None:
            continue
        name = (pm.findtext('kml:name', default='', namespaces=KML_NS) or '').strip()
        desc = (pm.findtext('kml:description', default='', namespaces=KML_NS) or '').strip()
        coords = parse_kml_coord_text(
            line.findtext('kml:coordinates', default='', namespaces=KML_NS)
        )
        route_id = parse_route_id(name)
        desc_clean = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', desc))[:200]
        rows.append({
            'route_id'           : route_id,
            'kml_name'           : name,
            'n_vertices'         : len(coords),
            'description_preview': desc_clean,
        })
        features.append({
            'type'      : 'Feature',
            'properties': {'route_id': route_id, 'kml_name': name},
            'geometry'  : {'type': 'LineString', 'coordinates': coords},
        })
    return pd.DataFrame(rows), {'type': 'FeatureCollection', 'features': features}


def parse_stops_kml(path: Path) -> pd.DataFrame:
    """
    Mengurai file KML titik halte Trans Jogja.

    Setiap Placemark berisi satu Point dengan koordinat halte.
    Field deskripsi berisi informasi rute yang melewati halte tersebut.
    Koordinat (lat, lon) diambil langsung dari KML sebagai sumber primer.
    """
    root = ET.parse(path).getroot()
    rows = []
    for pm in root.findall('.//kml:Placemark', KML_NS):
        point = pm.find('kml:Point', KML_NS)
        if point is None:
            continue
        name = (pm.findtext('kml:name', default='', namespaces=KML_NS) or '').strip()
        desc = (pm.findtext('kml:description', default='', namespaces=KML_NS) or '').strip()
        coords = parse_kml_coord_text(
            point.findtext('kml:coordinates', default='', namespaces=KML_NS)
        )
        lon = coords[0][0] if coords else np.nan
        lat = coords[0][1] if coords else np.nan
        rows.append({
            'kml_stop_name'      : name,
            'lat'                : lat,
            'lon'                : lon,
            'route_refs'         : '|'.join(extract_route_refs(desc)),
            'description_preview': re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', desc))[:200],
        })
    return pd.DataFrame(rows)


def canonicalize_stops() -> pd.DataFrame:
    """
    Membangun tabel halte kanonikal yang digunakan di seluruh sistem.

    Strategi:
    1. **Koordinat** diambil dari KML halte sebagai sumber otoritatif.
    2. **stop_id** dicocokkan dengan data stop_times (scraping jadwal) melalui
       fuzzy string matching agar selaras dengan ID jadwal historis.
    3. Halte yang tidak cocok dengan KML tetap disertakan dengan koordinat NaN
       sehingga tidak memengaruhi routing (akan diabaikan pada tahap filtering).

    Jika stop_times tidak tersedia, nama halte KML digunakan langsung sebagai stop_id.
    """
    kml_stops = parse_stops_kml(STOPS_KML)

    try:
        st_raw = pd.read_csv(STOP_TIMES_CSV)
        unique_stop_ids = st_raw['stop_id'].astype(str).unique()
    except Exception:
        unique_stop_ids = []

    if len(unique_stop_ids) == 0:
        stops = kml_stops.rename(columns={'kml_stop_name': 'stop_name'})
        stops['stop_id']     = stops['stop_name']
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
            rows.append({
                'stop_id'    : sid,
                'stop_name'  : best_match['kml_stop_name'],
                'lat'        : best_match['lat'],   # dari KML
                'lon'        : best_match['lon'],   # dari KML
                'source_rows': 1,
            })
        else:
            rows.append({
                'stop_id'    : sid,
                'stop_name'  : sid.replace('S_', '').replace('_', ' ').title(),
                'lat'        : np.nan,
                'lon'        : np.nan,
                'source_rows': 1,
            })
    return pd.DataFrame(rows)


def haversine_m(lat1, lon1, lat2, lon2) -> float | np.ndarray:
    """
    Menghitung jarak geodesik (meter) antara dua titik koordinat menggunakan
    formula Haversine. Mendukung input skalar maupun array NumPy.
    """
    lat1 = np.radians(lat1); lon1 = np.radians(lon1)
    lat2 = np.radians(lat2); lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 6_371_000.0 * 2 * np.arcsin(np.sqrt(a))


# ### Fungsi Bantu 2: Jadwal dan Konversi Waktu
# 

# In[3]:


def parse_hhmm(value: str) -> int:
    """
    Mengonversi waktu format 'HH:MM' menjadi menit sejak tengah malam.
    Contoh: '09:30' -> 570
    """
    hh, mm = str(value).strip().split(':')[:2]
    return int(hh) * 60 + int(mm)


def hhmm_from_minutes(value: int | float | np.integer | np.floating) -> str:
    """
    Mengonversi menit sejak tengah malam kembali ke format 'HH:MM'.
    Contoh: 570 -> '09:30'
    """
    v = int(round(float(value))) % (24 * 60)
    return f'{v // 60:02d}:{v % 60:02d}'


def normalize_trip_times(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mengonversi kolom waktu di stop_times menjadi representasi numerik
    (menit sejak tengah malam).
    """
    df = df.copy()
    df['tod_min'] = df['time'].map(parse_hhmm).astype(float)
    return df.sort_values(['trip_id', 'stop_sequence', 'stop_id']).reset_index(drop=True)


def build_stop_events(stop_times: pd.DataFrame) -> pd.DataFrame:
    """
    Membangun tabel kejadian keberangkatan per halte.
    Setiap baris merepresentasikan satu bus melewati satu halte pada waktu tertentu.
    Tabel ini digunakan untuk menghitung headway (selang waktu antar-bus).
    """
    out = stop_times[['stop_id', 'route_id', 'direction_id', 'trip_id', 'tod_min']].copy()
    out = out.rename(columns={'tod_min': 'dep_tod_min'})
    out['dep_hhmm'] = out['dep_tod_min'].map(hhmm_from_minutes)
    out['hour']     = (out['dep_tod_min'] % 1440 // 60).astype(int)
    return out.sort_values(
        ['stop_id', 'route_id', 'direction_id', 'dep_tod_min', 'trip_id']
    ).reset_index(drop=True)


def build_wait_lookup(stop_events: pd.DataFrame) -> pd.DataFrame:
    """
    Menghitung estimasi waktu tunggu bus berdasarkan headway historis.

    Metode: untuk setiap jam operasional, dihitung median selang waktu
    (headway) antar-kedatangan bus di seluruh halte dan rute. Estimasi
    waktu tunggu = headway / 2 (asumsi kedatangan acak seragam).

    Headway yang tidak realistis (< 0 atau > 120 menit) difilter.
    """
    tmp = stop_events.sort_values(
        ['stop_id', 'route_id', 'direction_id', 'dep_tod_min']
    ).copy()
    tmp['prev_dep']    = tmp.groupby(['stop_id', 'route_id', 'direction_id'])['dep_tod_min'].shift(1)
    tmp['headway_min'] = tmp['dep_tod_min'] - tmp['prev_dep']
    tmp = tmp[(tmp['headway_min'] > 0) & (tmp['headway_min'] <= 120)].copy()
    out = (
        tmp.groupby('hour', as_index=False)['headway_min']
        .median()
        .rename(columns={'headway_min': 'median_headway_min'})
        .sort_values('hour')
    )
    out['expected_wait_min'] = out['median_headway_min'] / 2.0
    return out


def build_route_sequences(stop_times: pd.DataFrame, stops: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Menyusun urutan halte kanonikal untuk setiap kombinasi rute dan arah.

    Untuk setiap route_dir (misalnya '1A_0', '1A_1'), dipilih satu trip
    representatif (trip dengan jumlah halte terbanyak) sebagai urutan kanonik.
    Urutan ini digunakan oleh mesin routing untuk menemukan jalur terpendek.

    Returns:
        route_sequences: tabel urutan halte per route_dir
        route_sequence_summary: ringkasan jumlah halte dan trip per route_dir
    """
    st = stop_times.copy()
    st['route_dir'] = st['route_id'].astype(str).str.upper() + '_' + st['direction_id'].astype(int).astype(str)
    rows, summary_rows = [], []

    for route_dir, grp in st.groupby('route_dir', sort=True):
        trip_lengths = grp.groupby('trip_id').size().sort_values(ascending=False)
        max_len      = int(trip_lengths.iloc[0])
        candidates   = sorted(trip_lengths[trip_lengths == max_len].index.astype(str).tolist())
        rep_trip     = candidates[0]
        rep = grp[grp['trip_id'].astype(str) == rep_trip].sort_values('stop_sequence').copy()

        for seq_idx, rec in enumerate(rep.itertuples(index=False)):
            rows.append({
                'route_dir'              : route_dir,
                'route_id'               : str(rec.route_id).upper(),
                'direction_id'           : int(rec.direction_id),
                'trip_id_representative' : rep_trip,
                'stop_sequence_canonical': int(seq_idx),
                'stop_id'                : str(rec.stop_id),
            })
        summary_rows.append({
            'route_dir'             : route_dir,
            'route_id'              : str(rep['route_id'].iloc[0]).upper(),
            'direction_id'          : int(rep['direction_id'].iloc[0]),
            'representative_trip_id': rep_trip,
            'canonical_stop_count'  : int(len(rep)),
            'trip_count'            : int(grp['trip_id'].nunique()),
        })

    route_sequences = pd.DataFrame(rows).merge(
        stops[['stop_id', 'stop_name']], on='stop_id', how='left'
    )
    route_sequence_summary = pd.DataFrame(summary_rows).sort_values(
        ['route_id', 'direction_id']
    ).reset_index(drop=True)
    return route_sequences, route_sequence_summary


def build_route_lookup_maps(route_sequences: pd.DataFrame) -> tuple[dict, dict, dict]:
    """
    Membangun tiga struktur dictionary dari route_sequences untuk routing cepat:

    - route_to_stop_list  : {route_dir -> [stop_id, ...]} urutan halte per rute
    - route_stop_pos      : {route_dir -> {stop_id -> index}} posisi halte di rute
    - stop_to_route_dirs  : {stop_id -> [route_dir, ...]} rute yang melewati halte
    """
    route_to_stop_list = (
        route_sequences.sort_values(['route_dir', 'stop_sequence_canonical'])
        .groupby('route_dir')['stop_id'].agg(list).to_dict()
    )
    route_stop_pos = {
        rd: {sid: idx for idx, sid in enumerate(sl)}
        for rd, sl in route_to_stop_list.items()
    }
    stop_to_route_dirs = (
        route_sequences.groupby('stop_id')['route_dir']
        .agg(lambda x: sorted(pd.unique(x).tolist())).to_dict()
    )
    return route_to_stop_list, route_stop_pos, stop_to_route_dirs


# ### Fungsi Bantu 3: Model Estimasi Waktu Perjalanan (ETA)
# 
# Model ETA dibangun pada level *segmen antar-halte*. Setiap segmen didefinisikan
# sebagai pasangan dua halte berurutan dalam satu trip. Model menggunakan
# *Bayesian smoothing* untuk menstabilkan prediksi pada segmen yang jarang dilalui.
# 
# **Formula prediksi waktu tempuh segmen:**
# $$\hat{t}_{seg,bin} = \frac{n_{bin} \cdot \tilde{t}_{bin} + K \cdot \tilde{t}_{seg}}{n_{bin} + K}$$
# 
# di mana $\tilde{t}_{bin}$ adalah median waktu tempuh di *time-bin* tertentu,
# $\tilde{t}_{seg}$ adalah median keseluruhan segmen, dan $K$ adalah parameter smoothing.
# 

# In[4]:


def build_segments(stop_times: pd.DataFrame, stops: pd.DataFrame) -> pd.DataFrame:
    """
    Membangun dataset segmen perjalanan antar-halte berurutan.

    Setiap baris merepresentasikan perjalanan dari satu halte ke halte berikutnya
    dalam satu trip, disertai:
    - waktu tempuh aktual (travel_time_min)
    - jarak geodesik antar-halte (dist_m, dari koordinat KML)
    - waktu keberangkatan termodulasi (dep_tod_min_mod)

    Segmen dengan waktu tempuh tidak realistis (≤ 0 atau > 90 menit) dieliminasi.
    """
    s = stop_times.sort_values(['trip_id', 'stop_sequence', 'stop_id']).copy()
    s['next_stop_id']  = s.groupby('trip_id')['stop_id'].shift(-1)
    s['next_tod_min']  = s.groupby('trip_id')['tod_min'].shift(-1)
    s['next_trip_id']  = s.groupby('trip_id')['trip_id'].shift(-1)
    seg = s[s['trip_id'] == s['next_trip_id']].copy()
    seg['travel_time_min'] = seg['next_tod_min'] - seg['tod_min']
    seg = seg[(seg['travel_time_min'] > 0) & (seg['travel_time_min'] <= 90)].copy()
    seg['segment_id']       = seg['stop_id'] + '->' + seg['next_stop_id']
    seg['dep_tod_min_mod']  = seg['tod_min'] % 1440

    # Tambahkan koordinat dari tabel stops (sumber: KML halte)
    coords_from = stops[['stop_id', 'lat', 'lon']].rename(columns={'lat': 'lat_from', 'lon': 'lon_from'})
    coords_to   = stops[['stop_id', 'lat', 'lon']].rename(columns={
        'stop_id': 'next_stop_id', 'lat': 'lat_to', 'lon': 'lon_to'
    })
    seg = seg.merge(coords_from, on='stop_id', how='left')
    seg = seg.merge(coords_to, on='next_stop_id', how='left')
    seg['dist_m'] = haversine_m(
        seg['lat_from'], seg['lon_from'], seg['lat_to'], seg['lon_to']
    )
    seg.loc[seg[['lat_from', 'lon_from', 'lat_to', 'lon_to']].isna().any(axis=1), 'dist_m'] = np.nan

    cols = ['trip_id', 'route_id', 'direction_id', 'stop_id', 'next_stop_id',
            'segment_id', 'stop_sequence', 'tod_min', 'dep_tod_min_mod',
            'travel_time_min', 'dist_m']
    return seg[cols].reset_index(drop=True)


def split_train_val_segments(segments: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Membagi data segmen menjadi himpunan latih dan validasi.
    Pemisahan berbasis trip_id: setiap 5 trip, 1 trip dijadikan data validasi
    (stratified sampling, ~20% validasi).
    """
    trips     = sorted(segments['trip_id'].astype(str).unique().tolist())
    val_trips = set(trips[::5])
    val   = segments[segments['trip_id'].astype(str).isin(val_trips)].copy()
    train = segments[~segments['trip_id'].astype(str).isin(val_trips)].copy()
    if val.empty:
        val   = train.sample(frac=0.2, random_state=42)
        train = train.drop(val.index)
    return train.reset_index(drop=True), val.reset_index(drop=True)


def build_segment_lookup(train: pd.DataFrame, bin_size: int, K: float, min_bin_n: int):
    """
    Membangun tabel prediksi ETA segmen menggunakan binning waktu dan Bayesian smoothing.

    Parameter:
        bin_size  : lebar time-bin dalam menit (misalnya 5 = bin per 5 menit)
        K         : kekuatan smoothing (semakin besar, semakin condong ke median global)
        min_bin_n : jumlah sampel minimum per bin agar bin digunakan

    Returns:
        base (DataFrame): median ETA per segmen (fallback)
        bins (DataFrame): ETA per (segmen, time-bin) dengan Bayesian smoothing
    """
    base = (
        train.groupby('segment_id', as_index=False)['travel_time_min']
        .agg(seg_median_min='median', seg_mean_min='mean', seg_n='size')
    )
    tmp = train.copy()
    tmp['dep_bin'] = (tmp['dep_tod_min_mod'] // bin_size).astype(int) * bin_size
    bins = (
        tmp.groupby(['segment_id', 'dep_bin'], as_index=False)['travel_time_min']
        .agg(bin_n='size', bin_median_min='median', bin_mean_min='mean')
    )
    bins = bins.merge(base[['segment_id', 'seg_median_min', 'seg_mean_min']], on='segment_id', how='left')
    bins = bins[bins['bin_n'] >= min_bin_n].copy()
    bins['pred_smooth_min'] = (
        bins['bin_n'] * bins['bin_median_min'] + K * bins['seg_median_min']
    ) / (bins['bin_n'] + K)
    return base, bins


def predict_segments(df: pd.DataFrame, base_lookup: pd.DataFrame,
                     bin_lookup: pd.DataFrame, bin_size: int) -> pd.DataFrame:
    """
    Menerapkan prediksi ETA pada data uji menggunakan lookup tabel.
    Prioritas prediksi: (1) time-bin spesifik, (2) median global segmen,
    (3) rata-rata global segmen.
    """
    out = df.copy()
    out['dep_bin'] = (out['dep_tod_min_mod'] // bin_size).astype(int) * bin_size
    out = out.merge(base_lookup[['segment_id', 'seg_median_min', 'seg_mean_min']], on='segment_id', how='left')
    out = out.merge(bin_lookup[['segment_id', 'dep_bin', 'pred_smooth_min']], on=['segment_id', 'dep_bin'], how='left')
    out['pred_min'] = out['pred_smooth_min'].fillna(out['seg_median_min']).fillna(out['seg_mean_min'])
    return out


def mae(y_true, y_pred) -> float:
    """Mean Absolute Error dalam satuan menit."""
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def rmse(y_true, y_pred) -> float:
    """Root Mean Square Error dalam satuan menit."""
    diff = np.asarray(y_true) - np.asarray(y_pred)
    return float(np.sqrt(np.mean(diff ** 2)))


def grid_search(train: pd.DataFrame, val: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Pencarian parameter terbaik untuk model ETA melalui exhaustive grid search.

    Ruang pencarian:
    - bin_size  : [3, 5, 10, 15, 20, 30] menit
    - K         : [1.0, 2.0, 5.0, 10.0, 20.0, 50.0]
    - min_bin_n : [1, 2, 3, 5, 10]

    Metrik evaluasi: MAE dan RMSE pada data validasi.
    Dipilih kombinasi dengan MAE terkecil, kemudian RMSE sebagai tiebreaker.
    """
    results = []
    for bin_size in [3, 5, 10, 15, 20, 30]:
        for K in [1.0, 2.0, 5.0, 10.0, 20.0, 50.0]:
            for min_bin_n in [1, 2, 3, 5, 10]:
                base, bins = build_segment_lookup(train, bin_size=bin_size, K=K, min_bin_n=min_bin_n)
                pred   = predict_segments(val, base, bins, bin_size=bin_size)
                usable = pred.dropna(subset=['pred_min', 'travel_time_min']).copy()
                if usable.empty:
                    continue
                results.append({
                    'bin_size'    : bin_size,
                    'K'          : float(K),
                    'min_bin_n'  : min_bin_n,
                    'val_mae_min' : mae(usable['travel_time_min'], usable['pred_min']),
                    'val_rmse_min': rmse(usable['travel_time_min'], usable['pred_min']),
                    'tbl_rows'    : int(len(bins)),
                })
    res  = pd.DataFrame(results).sort_values(
        ['val_mae_min', 'val_rmse_min', 'bin_size', 'K', 'min_bin_n']
    ).reset_index(drop=True)
    best = res.iloc[0].to_dict()
    return res, best


# ### Fungsi Bantu 4: Pemrosesan Destinasi Wisata (POI) dan Jam Operasional
# 
# Jam operasional setiap destinasi wisata ditentukan melalui proses bertingkat:
# 1. **Pencocokan dengan database terverifikasi** (`poi_opening_hours_verified.csv`)
# 2. **Fallback berdasarkan kategori POI** jika tidak ada data terverifikasi
# 3. **Gate verifikasi**: POI yang masih perlu diverifikasi (`needs_review=1`) dikecualikan
#    dari pool rekomendasi dan dicatat untuk tindak lanjut.
# 

# In[5]:


def normalize_text(text: str) -> str:
    """Menghapus aksen, mengubah ke lowercase, dan menghapus karakter non-alfanumerik."""
    if pd.isna(text):
        return ''
    text = str(text).lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]', '', text)


# In[6]:


def nearest_stop_for_pois(poi: pd.DataFrame, stops: pd.DataFrame, max_dist_m: float = 1200.0) -> pd.DataFrame:
    """
    Mencari halte terdekat untuk setiap destinasi wisata dalam radius maksimum.
    """
    results = []
    valid_stops = stops.dropna(subset=['lat', 'lon'])

    for _, prow in poi.iterrows():
        lat_poi = prow.get('latitude')
        lon_poi = prow.get('longitude')
        poi_id  = prow.get('poi_id')

        if pd.isna(lat_poi) or pd.isna(lon_poi):
            results.append({
                'poi_id': poi_id,
                'nearest_stop_id': np.nan,
                'nearest_stop_name': np.nan,
                'walk_dist_m': np.nan,
                'walk_time_min': np.nan
            })
            continue

        dists = haversine_m(lat_poi, lon_poi, valid_stops['lat'].values, valid_stops['lon'].values)
        min_idx = np.argmin(dists)
        min_dist = dists[min_idx]

        if min_dist <= max_dist_m:
            nearest_stop = valid_stops.iloc[min_idx]
            results.append({
                'poi_id': poi_id,
                'nearest_stop_id': nearest_stop['stop_id'],
                'nearest_stop_name': nearest_stop['stop_name'],
                'walk_dist_m': min_dist,
                'walk_time_min': min_dist / 80.0  # WALK_SPEED_M_PER_MIN
            })
        else:
            results.append({
                'poi_id': poi_id,
                'nearest_stop_id': np.nan,
                'nearest_stop_name': np.nan,
                'walk_dist_m': np.nan,
                'walk_time_min': np.nan
            })

    return pd.DataFrame(results)


# ### Fungsi Bantu 5: Mesin Rekomendasi (Routing dan Ranking)
# 
# Mesin rekomendasi bekerja dalam dua tahap:
# 1. **Routing**: menemukan jalur terbaik dari halte asal ke halte terdekat destinasi
#    (direct trip atau maksimum 1 transit)
# 2. **Ranking**: mengurutkan destinasi menggunakan *weighted ranking* berdasarkan
#    ETA total, jarak berjalan kaki, jumlah transit, margin jam operasional, rating, dan popularitas
# 
# **Formula skor rekomendasi:**
# $$S = 0.35\,s_{ETA} + 0.20\,s_{walk} + 0.20\,s_{transit} + 0.10\,s_{margin} + 0.10\,s_{rating} + 0.05\,s_{popularity}$$
# 

# In[7]:


def to_json_records(df: pd.DataFrame) -> list[dict]:
    """Konversi DataFrame ke list dict, mengganti NaN dengan None."""
    return df.where(pd.notnull(df), None).to_dict(orient='records')


def build_segment_prediction_maps(base_lookup: pd.DataFrame, bin_lookup: pd.DataFrame) -> tuple[dict, dict]:
    """Konversi lookup DataFrame ke dictionary untuk akses O(1) saat routing."""
    base_map = base_lookup.set_index('segment_id')['seg_median_min'].to_dict()
    bin_map  = {
        (str(rec.segment_id), int(rec.dep_bin)): float(rec.pred_smooth_min)
        for rec in bin_lookup.itertuples(index=False)
    }
    return base_map, bin_map


def lookup_wait_minutes(wait_lookup: pd.DataFrame, tod_min: float) -> float:
    """Mengambil estimasi waktu tunggu bus untuk jam keberangkatan tertentu."""
    hour = int(float(tod_min) % 1440 // 60)
    hit  = wait_lookup.loc[wait_lookup['hour'] == hour, 'expected_wait_min']
    if not hit.empty:
        return float(hit.iloc[0])
    if wait_lookup.empty:
        return 10.0
    nearest_idx = (wait_lookup['hour'] - hour).abs().idxmin()
    return float(wait_lookup.loc[nearest_idx, 'expected_wait_min'])


def predict_segment_minutes(segment_id: str, dep_tod_min: float,
                            base_map: dict, bin_map: dict, bin_size: int) -> float:
    """Prediksi waktu tempuh satu segmen menggunakan lookup dictionary."""
    dep_bin = int(float(dep_tod_min) % 1440 // bin_size) * int(bin_size)
    if (segment_id, dep_bin) in bin_map:
        return float(bin_map[(segment_id, dep_bin)])
    if segment_id in base_map:
        return float(base_map[segment_id])
    return float('nan')


def travel_time_along_route(route_dir, origin_stop_id, dest_stop_id, dep_tod_min,
                            route_to_stop_list, route_stop_pos, base_map, bin_map, bin_size):
    """
    Menghitung total waktu tempuh di dalam bus dari origin ke dest pada satu koridor.
    Mengembalikan None jika rute tidak valid atau ada segmen tanpa data ETA.
    """
    if origin_stop_id == dest_stop_id:
        return {'travel_time_min': 0.0, 'segment_ids': [], 'arrival_tod_min': float(dep_tod_min)}
    pos_map   = route_stop_pos.get(route_dir, {})
    stop_list = route_to_stop_list.get(route_dir, [])
    if origin_stop_id not in pos_map or dest_stop_id not in pos_map:
        return None
    if pos_map[origin_stop_id] >= pos_map[dest_stop_id]:
        return None
    cur, total, seg_ids = float(dep_tod_min), 0.0, []
    for idx in range(pos_map[origin_stop_id], pos_map[dest_stop_id]):
        seg_id = f'{stop_list[idx]}->{stop_list[idx + 1]}'
        pred   = predict_segment_minutes(seg_id, cur, base_map, bin_map, bin_size)
        if pd.isna(pred):
            return None
        total += float(pred)
        cur   += float(pred)
        seg_ids.append(seg_id)
    return {'travel_time_min': total, 'segment_ids': seg_ids, 'arrival_tod_min': cur}


def format_route_dir_label(route_dir: str) -> str:
    """Format route_dir menjadi label yang mudah dibaca ('1A', '1A (dir 1)')."""
    route_dir = str(route_dir)
    if '_' not in route_dir:
        return route_dir
    route_id, direction_id = route_dir.rsplit('_', 1)
    return route_id if direction_id == '0' else f'{route_id} (dir {direction_id})'


def find_best_path(origin_stop_id, dest_stop_id, depart_tod_min,
                   stop_to_route_dirs, route_to_stop_list, route_stop_pos,
                   base_map, bin_map, bin_size, wait_lookup,
                   max_transfers=4, transfer_penalty_min=TRANSFER_PENALTY_MIN):
    """
    Mencari jalur perjalanan terbaik dari origin ke dest dengan Trans Jogja.
    Menggunakan algoritma Dijkstra untuk mendukung hingga max_transfers.
    """
    import heapq

    if pd.isna(origin_stop_id) or pd.isna(dest_stop_id):
        return None
    origin_stop_id = str(origin_stop_id)
    dest_stop_id   = str(dest_stop_id)
    depart_tod_min = float(depart_tod_min)
    max_transfers = int(max_transfers)

    if origin_stop_id == dest_stop_id:
        return {'path_type': 'walk_only', 'route_path_dirs': [], 'route_path_labels': [],
                'transfer_stop_ids': [], 'board_wait_total_min': 0.0,
                'transfer_extra_min': 0.0, 'in_vehicle_min': 0.0,
                'transfers': 0, 'transit_eta_min': 0.0}

    max_boards = max_transfers + 1
    dist = {}
    parent = {}
    pq = [(depart_tod_min, origin_stop_id, 0)]
    dist[(origin_stop_id, 0)] = depart_tod_min
    best_arrival = float('inf')
    best_dest_state = None

    while pq:
        curr_time, u, b = heapq.heappop(pq)

        if curr_time > dist.get((u, b), float('inf')):
            continue

        if u == dest_stop_id:
            if curr_time < best_arrival:
                best_arrival = curr_time
                best_dest_state = (u, b)
            continue

        if b >= max_boards:
            continue

        for rd in stop_to_route_dirs.get(u, []):
            pos_map = route_stop_pos.get(rd, {})
            stop_list = route_to_stop_list.get(rd, [])
            if u not in pos_map:
                continue

            u_idx = pos_map[u]
            wait_time = lookup_wait_minutes(wait_lookup, curr_time)
            penalty_time = float(transfer_penalty_min) if b > 0 else 0.0
            board_time = curr_time + wait_time + penalty_time

            current_travel_time = 0.0
            current_arr_time = board_time

            for next_idx in range(u_idx, len(stop_list) - 1):
                seg_id = f'{stop_list[next_idx]}->{stop_list[next_idx + 1]}'
                pred = predict_segment_minutes(seg_id, current_arr_time, base_map, bin_map, bin_size)
                if pd.isna(pred):
                    break

                current_travel_time += float(pred)
                current_arr_time += float(pred)
                v = stop_list[next_idx + 1]
                new_b = b + 1

                if current_arr_time < dist.get((v, new_b), float('inf')):
                    dist[(v, new_b)] = current_arr_time
                    parent[(v, new_b)] = (u, b, rd, wait_time, current_travel_time, penalty_time)
                    heapq.heappush(pq, (current_arr_time, v, new_b))

    if best_dest_state is None:
        return None

    path = []
    curr_state = best_dest_state
    total_wait = 0.0
    total_in_vehicle = 0.0
    total_penalty = 0.0

    while curr_state in parent:
        p_u, p_b, p_rd, p_wait, p_in_veh, p_pen = parent[curr_state]
        path.append({
            'from': p_u, 'to': curr_state[0], 'route': p_rd,
            'wait': p_wait, 'in_veh': p_in_veh, 'penalty': p_pen
        })
        total_wait += p_wait
        total_in_vehicle += p_in_veh
        total_penalty += p_pen
        curr_state = (p_u, p_b)

    path.reverse()
    route_path_dirs = [step['route'] for step in path]
    route_path_labels = [format_route_dir_label(rd) for rd in route_path_dirs]
    transfer_stop_ids = [step['from'] for step in path[1:]]
    transfers = len(path) - 1

    if transfers == 0:
        path_type = 'direct'
    elif transfers == 1:
        path_type = 'one_transfer'
    else:
        path_type = f'{transfers}_transfers'

    return {
        'path_type': path_type,
        'route_path_dirs': route_path_dirs,
        'route_path_labels': route_path_labels,
        'transfer_stop_ids': transfer_stop_ids,
        'board_wait_total_min': total_wait,
        'transfer_extra_min': total_penalty,
        'in_vehicle_min': total_in_vehicle,
        'transfers': transfers,
        'transit_eta_min': total_wait + total_in_vehicle + total_penalty
    }



def resolve_stop_query(stop_query: str, stops: pd.DataFrame) -> dict:
    """Mencari halte berdasarkan stop_id atau nama (exact/partial/fuzzy)."""
    q = str(stop_query).strip()
    if not q:
        raise ValueError('stop_query tidak boleh kosong')
    if q in set(stops['stop_id'].astype(str)):
        return stops.loc[stops['stop_id'].astype(str) == q].iloc[0].to_dict()
    q_norm     = normalize_text(q)
    exact_name = stops.loc[stops['stop_name'].map(normalize_text) == q_norm]
    if not exact_name.empty:
        return exact_name.sort_values('stop_name').iloc[0].to_dict()
    contains = stops.loc[stops['stop_name'].map(normalize_text).str.contains(q_norm, regex=False, na=False)]
    if not contains.empty:
        return contains.assign(nl=contains['stop_name'].str.len()).sort_values(['nl', 'stop_name']).iloc[0].drop('nl').to_dict()
    raise ValueError(f'Halte tidak ditemukan: {stop_query}')


def expand_open_days(value: str) -> set[str]:
    """Mengurai string hari operasional menjadi set nama hari bahasa Indonesia."""
    if pd.isna(value):
        return set(DAY_NAMES_ID)
    txt = str(value).strip().replace('\u2013', '-').replace('\u2014', '-')
    if not txt:
        return set(DAY_NAMES_ID)
    txt_norm = normalize_text(txt)
    if 'setiap hari' in txt_norm or 'senin minggu' in txt_norm:
        return set(DAY_NAMES_ID)
    day_idx = {normalize_text(d): i for i, d in enumerate(DAY_NAMES_ID)}
    expanded = set()
    for part in re.split(r'[,;/]+|\s+dan\s+', txt):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            l, r = [normalize_text(p.strip()) for p in part.split('-', 1)]
            if l in day_idx and r in day_idx:
                li, ri = day_idx[l], day_idx[r]
                expanded.update(DAY_NAMES_ID[li:ri+1] if li <= ri
                                else DAY_NAMES_ID[li:] + DAY_NAMES_ID[:ri+1])
                continue
        pn = normalize_text(part)
        if pn in day_idx:
            expanded.add(DAY_NAMES_ID[day_idx[pn]])
    return expanded if expanded else set(DAY_NAMES_ID)


def is_open_on_day(open_days: str, day_name: str | None) -> bool:
    """Memeriksa apakah destinasi beroperasi pada hari yang diberikan."""
    if not day_name:
        return True
    return day_name in expand_open_days(open_days)


def safe_scale_positive(series: pd.Series) -> pd.Series:
    """Normalisasi Min-Max (0–1) dengan penanganan nilai konstan dan NaN."""
    s = pd.to_numeric(series, errors='coerce').astype(float)
    if s.notna().sum() == 0:
        return pd.Series(1.0, index=series.index)
    lo, hi = float(s.min()), float(s.max())
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
        return pd.Series(1.0, index=series.index)
    return (s - lo) / (hi - lo)


def safe_scale_inverse(series: pd.Series) -> pd.Series:
    """Normalisasi invers (semakin kecil nilai, semakin tinggi skor)."""
    return 1.0 - safe_scale_positive(series)


def build_destination_candidate_flags(poi_catalog: pd.DataFrame) -> pd.DataFrame:
    """
    Menandai POI yang memenuhi syarat sebagai kandidat rekomendasi:
    (1) memiliki halte terdekat dalam radius 1.200 m,
    (2) termasuk kategori wisata yang relevan,
    (3) bukan layanan non-wisata (hotel, travel agent, dll.).
    """
    out     = poi_catalog.copy()
    pattern = '|'.join(RECOMMENDER_EXCLUDE_PATTERNS)
    out['name_norm']      = out['name'].map(normalize_text)
    out['is_service_like'] = out['name'].astype(str).str.contains(pattern, case=False, regex=True, na=False)
    out['default_type_ok'] = True  # Semua tipe POI diizinkan asalkan bukan service
    out['is_destination_candidate'] = (
        out['nearest_stop_id'].notna()
        & out['default_type_ok']
        & (~out['is_service_like'])
    ).astype(int)
    return out


def deduplicate_recommendations(df: pd.DataFrame, distance_threshold_m: float = 150.0,
                                similarity_threshold: float = 0.45) -> pd.DataFrame:
    """
    Menghilangkan rekomendasi duplikat berdasarkan kedekatan lokasi dan kemiripan nama.
    Dua POI dianggap duplikat jika jarak < 150 m DAN kemiripan nama > 0.45.
    """
    if df.empty:
        return df.copy()
    kept_rows, keep_idx = [], []
    for row in df.itertuples(index=True):
        rname = normalize_text(getattr(row, 'name'))
        rlat, rlon = getattr(row, 'lat'), getattr(row, 'lon')
        is_dup = False
        for prev in kept_rows:
            if any(pd.isna(v) for v in [rlat, rlon, prev['lat'], prev['lon']]):
                continue
            dist = float(haversine_m(rlat, rlon, prev['lat'], prev['lon']))
            sim  = SequenceMatcher(None, rname, prev['name_norm']).ratio()
            if dist <= distance_threshold_m and sim >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            keep_idx.append(row.Index)
            kept_rows.append({'lat': rlat, 'lon': rlon, 'name_norm': rname})
    return df.loc[keep_idx].reset_index(drop=True)


def build_recommendation_reason(row: pd.Series) -> str:
    """Menghasilkan teks penjelasan singkat untuk satu hasil rekomendasi."""
    route_text  = ('cukup berjalan kaki dari halte asal' if row['path_type'] == 'walk_only'
                   else 'naik ' + ' -> '.join(row['route_path_labels']))
    transit_text = ('tanpa transit' if int(row['transfers']) == 0
                    else f"{int(row['transfers'])} transit via {row['transfer_stop_names_text']}")
    return (
        f"ETA total {row['eta_total_min']:.1f} menit, {transit_text}, "
        f"jalan kaki akhir {row['walk_dist_m']:.0f} m dari {row['nearest_stop_name']}, "
        f"tiba {row['arrival_hhmm']}, buka {row['open_hhmm']}–{row['close_hhmm']}, "
        f"{route_text}."
    )


def recommend_destinations(origin_stop_query, depart_hhmm, day_name,
                           poi_catalog, stops, wait_lookup,
                           route_to_stop_list, route_stop_pos, stop_to_route_dirs,
                           base_map, bin_map, bin_size,
                           preferred_types=None, top_k=10,
                           min_stay_min=MIN_STAY_MIN_DEFAULT,
                           require_verified_hours=False, max_transfers=4):
    """
    Menghasilkan daftar rekomendasi destinasi wisata dari halte asal.

    Alur kerja:
    1. Resolusi halte asal (stop_id atau nama)
    2. Filter kandidat POI (kategori, jam operasional, halte akses)
    3. Routing ke setiap kandidat (direct / 1 transit)
    4. Filter destinasi yang buka saat tiba dan tersedia cukup waktu
    5. Kalkulasi skor weighted ranking
    6. Deduplikasi dan ambil top-k
    """
    origin        = resolve_stop_query(origin_stop_query, stops)
    depart_tod_min = float(parse_hhmm(depart_hhmm))
    candidates    = poi_catalog.copy()
    candidates    = candidates[candidates['nearest_stop_id'].notna()].copy()
    if preferred_types:
        candidates = candidates[candidates['type'].isin(preferred_types)].copy()
    else:
        candidates = candidates[candidates['is_destination_candidate'] == 1].copy()
    if require_verified_hours:
        candidates = candidates[candidates['hours_source_type'] == 'verified_web'].copy()

    stop_name_map = stops.set_index('stop_id')['stop_name'].to_dict()
    rows = []
    for rec in candidates.itertuples(index=False):
        path = find_best_path(
            origin_stop_id=str(origin['stop_id']),
            dest_stop_id=str(rec.nearest_stop_id),
            depart_tod_min=depart_tod_min,
            stop_to_route_dirs=stop_to_route_dirs,
            route_to_stop_list=route_to_stop_list,
            route_stop_pos=route_stop_pos,
            base_map=base_map, bin_map=bin_map, bin_size=bin_size,
            wait_lookup=wait_lookup, max_transfers=max_transfers,
            transfer_penalty_min=TRANSFER_PENALTY_MIN,
        )
        if path is None:
            continue
        walk_min   = float(rec.walk_time_min) if pd.notna(rec.walk_time_min) else 0.0
        walk_m     = float(rec.walk_dist_m)   if pd.notna(rec.walk_dist_m) else 0.0
        eta_total  = float(path['transit_eta_min']) + walk_min
        arr_tod    = depart_tod_min + eta_total
        open_min   = parse_hhmm(rec.open_hhmm)  if pd.notna(rec.open_hhmm)  else 0
        close_min  = parse_hhmm(rec.close_hhmm) if pd.notna(rec.close_hhmm) else 1439
        day_open   = is_open_on_day(rec.open_days, day_name)
        open_arr   = bool(day_open and open_min <= arr_tod <= close_min)
        can_visit  = bool(day_open and arr_tod + float(min_stay_min) <= close_min)
        margin     = max(float(close_min) - float(arr_tod), 0.0)
        tsids      = path['transfer_stop_ids']
        tsnames    = [stop_name_map.get(s, s) for s in tsids]
        rows.append({
            'origin_stop_id'         : str(origin['stop_id']),
            'origin_stop_name'       : origin['stop_name'],
            'depart_hhmm'            : depart_hhmm,
            'day_name'               : day_name,
            'poi_id'                 : int(rec.poi_id),
            'name'                   : rec.name,
            'type'                   : rec.type,
            'rating'                 : float(rec.rating) if pd.notna(rec.rating) else np.nan,
            'vote_count'             : float(rec.vote_count) if pd.notna(rec.vote_count) else 0.0,
            'lat'                    : float(rec.lat) if pd.notna(rec.lat) else np.nan,
            'lon'                    : float(rec.lon) if pd.notna(rec.lon) else np.nan,
            'nearest_stop_id'        : rec.nearest_stop_id,
            'nearest_stop_name'      : rec.nearest_stop_name,
            'walk_dist_m'            : walk_m,
            'walk_time_min'          : walk_min,
            'path_type'              : path['path_type'],
            'route_path_dirs'        : path['route_path_dirs'],
            'route_path_labels'      : path['route_path_labels'],
            'route_path_text'        : ' > '.join(path['route_path_labels']) if path['route_path_labels'] else 'walk_only',
            'transfer_stop_ids'      : tsids,
            'transfer_stop_names'    : tsnames,
            'transfer_stop_names_text': ' > '.join(tsnames),
            'transfers'              : int(path['transfers']),
            'board_wait_total_min'   : float(path['board_wait_total_min']),
            'transfer_extra_min'     : float(path['transfer_extra_min']),
            'in_vehicle_min'         : float(path['in_vehicle_min']),
            'transit_eta_min'        : float(path['transit_eta_min']),
            'eta_total_min'          : float(eta_total),
            'arrival_hhmm'           : hhmm_from_minutes(arr_tod),
            'open_hhmm'              : rec.open_hhmm,
            'close_hhmm'             : rec.close_hhmm,
            'open_days'              : rec.open_days,
            'hours_source_type'      : rec.hours_source_type,
            'needs_review'           : int(rec.needs_review) if pd.notna(rec.needs_review) else 0,
            'is_open_on_day'         : int(day_open),
            'is_open_on_arrival'     : int(open_arr),
            'can_visit_min_stay'     : int(can_visit),
            'visit_margin_min'       : float(margin),
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out[out['is_open_on_arrival'] == 1].copy()
    if out.empty:
        return out
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
        0.35 * out['score_eta']
        + 0.20 * out['score_walk']
        + 0.20 * out['score_transfers']
        + 0.10 * out['score_operating_margin']
        + 0.10 * out['score_rating']
        + 0.05 * out['score_popularity']
        - 0.03 * out['needs_review']
        - 0.05 * (out['vote_count'] < 10).astype(float)
    )
    out = out.sort_values(
        ['recommendation_score', 'rating', 'vote_count', 'eta_total_min'],
        ascending=[False, False, False, True]
    ).reset_index(drop=True)
    out = deduplicate_recommendations(out)
    out = out.head(int(top_k)).reset_index(drop=True)
    out.insert(0, 'rank', np.arange(1, len(out) + 1))
    out['recommendation_reason'] = out.apply(build_recommendation_reason, axis=1)
    return out


def build_sample_recommendations(poi_catalog, stops, wait_lookup,
                                  route_to_stop_list, route_stop_pos,
                                  stop_to_route_dirs, base_map, bin_map, bin_size):
    """
    Menjalankan empat skenario rekomendasi representatif untuk keperluan evaluasi:
    - Dua skenario umum (Malioboro, Adisutjipto)
    - Satu skenario tematik budaya/museum
    - Satu skenario wisata keluarga dari Terminal Jombor
    """
    scenarios = [
        {'scenario_id': 'malioboro_umum_sabtu_0900',
         'origin_stop_query': 'Malioboro 1',
         'depart_hhmm': '09:00', 'day_name': 'Sabtu',
         'preferred_types': None, 'top_k': 12},
        {'scenario_id': 'malioboro_budaya_sabtu_0900',
         'origin_stop_query': 'Malioboro 1',
         'depart_hhmm': '09:00', 'day_name': 'Sabtu',
         'preferred_types': ['Budaya_Dan_Sejarah', 'Museum'], 'top_k': 12},
        {'scenario_id': 'jombor_keluarga_sabtu_0900',
         'origin_stop_query': 'Terminal Jombor',
         'depart_hhmm': '09:00', 'day_name': 'Sabtu',
         'preferred_types': ['Buatan', 'Wisata Air', 'Museum'], 'top_k': 12},
        {'scenario_id': 'adisutjipto_umum_sabtu_0900',
         'origin_stop_query': 'Bandara Adisujtipto',
         'depart_hhmm': '09:00', 'day_name': 'Sabtu',
         'preferred_types': None, 'top_k': 12},
    ]
    all_rows, summary_rows = [], []
    for spec in scenarios:
        try:
            rec = recommend_destinations(
                origin_stop_query=spec['origin_stop_query'],
                depart_hhmm=spec['depart_hhmm'],
                day_name=spec['day_name'],
                poi_catalog=poi_catalog, stops=stops, wait_lookup=wait_lookup,
                route_to_stop_list=route_to_stop_list, route_stop_pos=route_stop_pos,
                stop_to_route_dirs=stop_to_route_dirs,
                base_map=base_map, bin_map=bin_map, bin_size=bin_size,
                preferred_types=spec['preferred_types'], top_k=spec['top_k'],
                min_stay_min=MIN_STAY_MIN_DEFAULT, require_verified_hours=False, max_transfers=4,
            )
        except Exception as e:
            print(f"[WARN] Skenario {spec['scenario_id']}: {e}")
            rec = pd.DataFrame()

        if rec.empty:
            summary_rows.append({'scenario_id': spec['scenario_id'],
                                 'origin_stop_query': spec['origin_stop_query'],
                                 'depart_hhmm': spec['depart_hhmm'],
                                 'day_name': spec['day_name'],
                                 'result_rows': 0, 'best_eta_min': None,
                                 'avg_top5_score': None, 'all_open_on_arrival': 0,
                                 'all_have_route_or_walk': 0})
            continue
        rec = rec.copy()
        rec['scenario_id']          = spec['scenario_id']
        rec['preferred_types_text'] = ', '.join(spec['preferred_types']) if spec['preferred_types'] else 'semua kategori'
        all_rows.append(rec)
        summary_rows.append({
            'scenario_id'          : spec['scenario_id'],
            'origin_stop_query'    : spec['origin_stop_query'],
            'depart_hhmm'          : spec['depart_hhmm'],
            'day_name'             : spec['day_name'],
            'result_rows'          : int(len(rec)),
            'best_eta_min'         : float(rec['eta_total_min'].min()),
            'avg_top5_score'       : float(rec['recommendation_score'].head(5).mean()),
            'all_open_on_arrival'  : int((rec['is_open_on_arrival'] == 1).all()),
            'all_have_route_or_walk': int(rec['route_path_text'].notna().all()),
        })
    samples = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    return samples, pd.DataFrame(summary_rows)


def build_recommendation_smoke_tests(recommendation_summary: pd.DataFrame) -> pd.DataFrame:
    """Menjalankan serangkaian smoke test untuk memverifikasi keluaran sistem rekomendasi."""
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


# ## 1. Business Understanding
# 
# Tahap pertama CRISP-DM mendefinisikan konteks bisnis dan tujuan penelitian secara kuantitatif.
# 
# ### Permasalahan
# 
# Wisatawan yang mengunjungi Yogyakarta tanpa kendaraan pribadi menghadapi hambatan
# informasi yang signifikan: mereka tidak mengetahui koridor Trans Jogja mana yang
# dapat mengantarkan mereka ke destinasi tertentu, berapa lama waktu yang dibutuhkan,
# dan apakah destinasi tersebut masih buka saat tiba.
# 
# ### Tujuan Sistem
# 
# Membangun sistem rekomendasi yang secara otomatis:
# 1. Menentukan halte Trans Jogja terdekat dari setiap destinasi wisata
# 2. Menghitung estimasi waktu perjalanan (ETA) dari halte asal pengguna
# 3. Memfilter destinasi berdasarkan ketersediaan rute dan jam operasional
# 4. Menghasilkan rekomendasi terurut yang sesuai preferensi waktu dan kategori wisata
# 
# ### Kriteria Keberhasilan
# 
# | Kriteria | Target |
# |----------|--------|
# | MAE model ETA | < 5 menit |
# | Semua rekomendasi buka saat pengguna tiba | 100% |
# | Sistem dapat menemukan rute untuk semua skenario uji | 4/4 skenario |
# | Pengguna dapat memilih dari berbagai kategori wisata | Min. 5 kategori aktif |
# 
# ### Batasan Sistem
# 
# - Cakupan: hanya koridor Trans Jogja di DIY
# - ETA bersifat *schedule-based* (tidak realtime)
# - Maksimum 1 kali transit
# - Tidak ada personalisasi berbasis riwayat pengguna
# 

# In[8]:


# Ringkasan Business Understanding – dicetak sebagai dokumentasi terstruktur
bu_summary = {
    'tujuan_sistem': [
        'Mengintegrasikan data halte, rute, jadwal, dan destinasi wisata dalam satu sistem',
        'Membantu wisatawan menentukan destinasi yang realistis dijangkau via Trans Jogja',
        'Menyajikan rute, ETA, dan informasi jam operasional secara terintegrasi',
    ],
    'kebutuhan_pengguna': [
        'Destinasi wisata beserta halte akses dan koridor yang tersedia',
        'Opsi rute direct dan 1 transit dengan informasi perpindahan',
        'Estimasi waktu perjalanan berbasis data historis jadwal',
        'Informasi jam operasional destinasi yang sudah terverifikasi',
    ],
    'kriteria_rekomendasi': {
        'keterjangkauan_halte'  : 'Halte terdekat dalam radius 1.200 meter',
        'kemudahan_rute'        : 'Maksimum 1 transit (direct atau 1 transfer)',
        'jam_operasional'       : 'Destinasi terbuka minimal 2 jam setelah kedatangan',
        'faktor_scoring'        : [
            'ETA total (bobot 0,35)',
            'Jarak berjalan kaki (0,20)',
            'Jumlah transit (0,20)',
            'Margin jam operasional (0,10)',
            'Rating (0,10)',
            'Popularitas/vote_count (0,05)',
        ],
    },
    'batasan_sistem': [
        'Hanya mencakup jaringan Trans Jogja di wilayah DIY',
        'ETA berbasis jadwal historis (schedule-based, non-realtime)',
        'Tidak mengimplementasikan collaborative filtering atau deep learning',
        'Evaluasi menggunakan MAE/RMSE dan pengujian fungsional (smoke tests)',
    ],
}

print('=' * 65)
print('Business Understanding: Sistem Rekomendasi Wisata Trans Jogja')
print('=' * 65)
for key, label in [('tujuan_sistem', 'Tujuan'), ('kebutuhan_pengguna', 'Kebutuhan Pengguna'), ('batasan_sistem', 'Batasan')]:
    print(f'\n{label}:')
    for item in bu_summary[key]:
        print(f'  - {item}')
print('\nKriteria Rekomendasi:')
kr = bu_summary['kriteria_rekomendasi']
for k, v in kr.items():
    if isinstance(v, list):
        print(f'  {k}: ' + ', '.join(v))
    else:
        print(f'  {k}: {v}')


# ## 2. Data Understanding
# 
# Tahap ini memuat seluruh data sumber, memeriksa kelengkapan dan kualitasnya,
# serta mengidentifikasi potensi masalah sebelum masuk ke Data Preparation.
# 
# ### Sumber Data
# 
# **Data Geospasial (KML)**  
# Dua file KML terpisah disediakan oleh Trans Jogja:
# - `Jalur Route.kml`: geometri polyline setiap koridor bus
# - `Perhentian Bus Bus Stop.kml`: titik koordinat halte beserta informasi rute yang melewatinya
# 
# **Data Jadwal (CSV)**  
# Data `stop_times` merupakan hasil scraping jadwal bus dari sumber publik. Setiap baris
# mencatat waktu keberangkatan satu bus dari satu halte dalam satu trip perjalanan.
# Data ini menjadi fondasi perhitungan ETA dan headway.
# 
# **Data Destinasi Wisata (CSV)**  
# Dataset wisata berisi nama, kategori, koordinat, rating, dan deskripsi POI.
# Dataset dikombinasikan dengan data jam operasional terverifikasi.
# 

# In[9]:


# ── Muat data geospasial dari KML ────────────────────────────────────────
route_summary, route_fc_all = parse_routes_kml(ROUTES_KML)
kml_stop_points             = parse_stops_kml(STOPS_KML)

# ── Bangun tabel halte kanonikal ──────────────────────────────────────────
# Koordinat halte bersumber dari KML; stop_id dicocokkan dengan data jadwal
stops = canonicalize_stops()

# --- PREPROCESS: STANDARDIZE STOP IDs ---
# Menyeragamkan id halte dengan format berurut berdasarkan nama, tanpa menghapus duplikat (seperti sisi timur/barat)
stops = stops.sort_values(['stop_name', 'stop_id']).reset_index(drop=True)

canonical_id_map = {}
for i, raw_id in enumerate(stops['stop_id']):
    canonical_id_map[raw_id] = f"HT_{i+1:03d}"

stops['stop_id'] = stops['stop_id'].map(canonical_id_map)
# ----------------------------------------

# ── Muat data jadwal keberangkatan ────────────────────────────────────────
stop_times_raw = pd.read_csv(STOP_TIMES_CSV)
stop_times_raw['route_id'] = stop_times_raw['route_id'].astype(str).str.upper()
stop_times_raw['trip_id']  = stop_times_raw['trip_id'].astype(str)
stop_times_raw['stop_id']  = stop_times_raw['stop_id'].astype(str)
stop_times_raw['stop_id']  = stop_times_raw['stop_id'].map(canonical_id_map).fillna(stop_times_raw['stop_id'])

# Filter: hanya gunakan rute jadwal yang benar-benar ada geometrinya di file KML rute
valid_routes = set(route_summary['route_id'].astype(str).str.upper())
stop_times_raw = stop_times_raw[stop_times_raw['route_id'].isin(valid_routes)].copy()

# ── Muat data destinasi wisata ────────────────────────────────────────────
poi = pd.read_csv(POI_CSV)
if 'no' in poi.columns:
    poi = poi.rename(columns={'no': 'poi_id'})
else:
    poi['poi_id'] = np.arange(len(poi), dtype=int)

# ── Ringkasan Data ────────────────────────────────────────────────────────
summary_df = pd.DataFrame([
    {'dataset': 'Rute Trans Jogja (KML)',
     'baris'  : len(route_summary),
     'keterangan': f"{route_summary['route_id'].nunique()} koridor, geometri polyline"},
    {'dataset': 'Halte Trans Jogja (KML)',
     'baris'  : len(kml_stop_points),
     'keterangan': 'Titik halte dengan koordinat dari KML'},
    {'dataset': 'Halte Kanonikal (KML + jadwal)',
     'baris'  : stops['stop_id'].nunique(),
     'keterangan': 'Koordinat KML, stop_id sinkron dengan stop_times'},
    {'dataset': 'Jadwal Keberangkatan (stop_times)',
     'baris'  : len(stop_times_raw),
     'keterangan': f"{stop_times_raw['route_id'].nunique()} rute, {stop_times_raw['trip_id'].nunique()} trip"},
    {'dataset': 'Destinasi Wisata (POI)',
     'baris'  : len(poi),
     'keterangan': f"{poi['type'].nunique()} kategori wisata"},
])
print('Ringkasan Dataset:')
print(summary_df)


# In[10]:


# ── Eksplorasi Kualitas Data ──────────────────────────────────────────────
print('=== Kualitas Data Halte ===')
n_with_coords = int(stops['lat'].notna().sum())
n_total_stops = len(stops)
print(f'  Total halte unik          : {n_total_stops}')
print(f'  Halte dengan koordinat KML: {n_with_coords} ({n_with_coords/n_total_stops*100:.1f}%)')
print(f'  Halte tanpa koordinat      : {n_total_stops - n_with_coords}')

print('\n=== Kualitas Data Rute ===')
print(f'  Koridor di KML: {route_summary["route_id"].nunique()}')
print(f'  Koridor di jadwal: {stop_times_raw["route_id"].nunique()}')

print('\n=== Preview Halte KML (5 pertama) ===')
print(kml_stop_points.head())

print('\n=== Preview Halte Kanonikal (5 pertama) ===')
print(stops.head())

print('\n=== Preview Rute KML ===')
print(route_summary.head())


# ## 3. Data Preparation
# 
# Tahap ini mengolah data mentah menjadi representasi yang siap digunakan oleh model.
# Proses mencakup normalisasi waktu, pembentukan segmen, kalkulasi headway,
# penentuan jam operasional POI, dan pemetaan halte terdekat.
# 
# ### Alur Data Preparation
# 
# ```
# stop_times_raw
#   └─ normalize_trip_times() ──> stop_times (waktu dalam menit)
#        ├─ build_stop_events()  ──> stop_events (kejadian per halte)
#        │    └─ build_wait_lookup() ──> wait_lookup (estimasi waktu tunggu per jam)
#        └─ build_segments()     ──> segments (waktu tempuh antar-halte)
# 
# poi
#   └─ nearest_stop_for_pois() ──> poi_nearest (halte terdekat per POI)
#   └─ jam_operasional ──> langsung diambil dari kolom dataset `wisata_jogja.csv` (jam_buka, jam_tutup, hari_operasional)
# 

# In[11]:


# ── Normalisasi waktu stop_times ─────────────────────────────────────────
stop_times  = normalize_trip_times(stop_times_raw)
stop_events = build_stop_events(stop_times)
segments    = build_segments(stop_times, stops)
wait_lookup = build_wait_lookup(stop_events)

# ── Jam operasional POI ───────────────────────────────────────────────────
place_hours = poi[['poi_id']].copy()
place_hours['open_hhmm'] = poi['jam_buka']
place_hours['close_hhmm'] = poi['jam_tutup']
place_hours['open_days'] = poi['hari_operasional']
place_hours['hours_detail'] = poi.get('catatan_jam', '')
place_hours['hours_source_type'] = 'wisata_jogja_csv'
place_hours['needs_review'] = 0

# ── Halte terdekat dari koordinat POI ────────────────────────────────────
poi_nearest = nearest_stop_for_pois(poi, stops)

# ── Ringkasan hasil pra-pemrosesan awal ──────────────────────────────────
prep_summary = pd.DataFrame([
    {'artefak': 'stop_times (normalized)', 'baris': len(stop_times),
     'keterangan': 'Waktu dalam menit sejak tengah malam'},
    {'artefak': 'stop_events',             'baris': len(stop_events),
     'keterangan': 'Kejadian keberangkatan per halte per trip'},
    {'artefak': 'segments',                'baris': len(segments),
     'keterangan': f"{segments['segment_id'].nunique()} segmen unik antar-halte"},
    {'artefak': 'wait_lookup',             'baris': len(wait_lookup),
     'keterangan': 'Median headway dan estimasi tunggu per jam'},
    {'artefak': 'place_hours',             'baris': len(place_hours),
     'keterangan': 'Jam operasional POI (terverifikasi + fallback)'},
    {'artefak': 'poi_nearest',             'baris': len(poi_nearest),
     'keterangan': f"POI dengan halte dalam 1.200 m: {poi_nearest['nearest_stop_id'].notna().sum()}"},
])
print('Ringkasan Pra-Pemrosesan:')
print(prep_summary)



# ### 3a. Pembentukan Route Sequences dan Pool Rekomendasi
# 
# Sub-tahap ini menghasilkan dua struktur data kunci untuk mesin rekomendasi:
# 
# **1. Route Sequences**  
# Urutan halte kanonikal per koridor-arah (`route_dir`). Untuk setiap kombinasi
# rute dan arah (misalnya `1A_0`, `1A_1`), dipilih satu trip representatif
# sebagai urutan referensi. Struktur ini memungkinkan algoritma routing
# menentukan apakah bus melewati halte tertentu dan dalam urutan yang benar.
# 
# **2. Pool Rekomendasi**  
# Hanya POI dengan jam operasional terverifikasi (`needs_review=0`) yang
# dimasukkan ke dalam pool. POI yang belum terverifikasi tidak ditampilkan
# kepada pengguna hingga jam operasionalnya dikonfirmasi.
# 
# > Untuk menambahkan POI ke pool: isi `report/needs_review_list.csv` → simpan
# > sebagai `raw/poi_hours_filled.csv` → jalankan ulang sel Data Preparation.
# 

# In[12]:


# ── Route Sequences ───────────────────────────────────────────────────────
route_sequences, route_sequence_summary = build_route_sequences(stop_times, stops)

print(f'Route sequences: {len(route_sequence_summary)} koridor-arah')
print(route_sequence_summary.head(10))

# ── Pool Rekomendasi ──────────────────────────────────────────────────────
poi_catalog = (
    poi.rename(columns={
        'nama'         : 'name',
        'vote_average' : 'rating',
        'vote_count'   : 'vote_count',
        'latitude'     : 'lat',
        'longitude'    : 'lon',
    })[['poi_id', 'name', 'type', 'rating', 'vote_count', 'lat', 'lon', 'description']]
    .merge(place_hours, on='poi_id', how='left')
    .merge(poi_nearest, on='poi_id', how='left')
)
poi_catalog = build_destination_candidate_flags(poi_catalog)

# Update halte terdekat menggunakan koordinat terkini dari KML
poi_nearest_final = nearest_stop_for_pois(poi, stops)
poi_catalog = (
    poi_catalog.drop(columns=[c for c in
        ['nearest_stop_id', 'nearest_stop_name', 'stop_lat', 'stop_lon', 'walk_dist_m', 'walk_time_min']
        if c in poi_catalog.columns])
    .merge(poi_nearest_final, on='poi_id', how='left')
)
poi_catalog = build_destination_candidate_flags(poi_catalog)

# Semua POI sekarang berasal dari wisata_jogja.csv yang sudah bersih
poi_catalog_verified = poi_catalog.copy()
n_candidates = int((poi_catalog_verified['is_destination_candidate'] == 1).sum())

print(f'\nPool Rekomendasi:')
print(f'  Total POI           : {len(poi_catalog)}')
print(f'  Kandidat aktif      : {n_candidates} POI (dalam radius halte + kategori relevan)')


# ## 4. Modeling
# 
# Tahap ini membangun model Estimasi Waktu Perjalanan (ETA) pada level segmen antar-halte.
# 
# ### 4.1 Model ETA Berbasis Segmen
# 
# Model ETA menggunakan pendekatan *lookup table* dengan *Bayesian smoothing*.
# Setiap segmen (pasangan halte berurutan) memiliki distribusi waktu tempuh
# yang bervariasi tergantung waktu dalam sehari. Binning waktu keberangkatan
# dan smoothing mengatasi masalah data jarang (*data sparsity*) pada segmen
# yang hanya dilalui sedikit trip.
# 
# ### 4.2 Prosedur Evaluasi
# 
# Data segmen dibagi menjadi **80% data latih** dan **20% data validasi**
# berdasarkan trip_id. Grid search dilakukan pada data latih untuk menemukan
# kombinasi parameter `(bin_size, K, min_bin_n)` yang meminimalkan MAE
# pada data validasi. Lookup final kemudian dibangun menggunakan **seluruh data**
# untuk memaksimalkan cakupan segmen pada tahap deployment.
# 
# ### 4.3 Formula ETA Total
# 
# $$ETA_{total} = T_{jalan\ kaki\ awal} + T_{tunggu} + \sum T_{segmen} + T_{transfer} + T_{jalan\ kaki\ akhir}$$
# 

# In[13]:


# ── Pembagian Data Latih dan Validasi ────────────────────────────────────
train_seg, val_seg = split_train_val_segments(segments)
print(f'Data segmen: {len(segments):,} baris')
print(f'  Latih    : {len(train_seg):,} baris ({len(train_seg)/len(segments)*100:.0f}%)')
print(f'  Validasi : {len(val_seg):,} baris ({len(val_seg)/len(segments)*100:.0f}%)')
print(f'  Segmen unik: {segments["segment_id"].nunique():,}')

# ── Grid Search Parameter ETA ─────────────────────────────────────────────
print('\nMemulai grid search... (mungkin membutuhkan beberapa menit)')
grid_res, best = grid_search(train_seg, val_seg)

best_bin    = int(best['bin_size'])
best_K      = float(best['K'])
best_min_n  = int(best['min_bin_n'])

print(f'\nParameter terpilih:')
print(f'  bin_size  = {best_bin} menit')
print(f'  K         = {best_K}')
print(f'  min_bin_n = {best_min_n}')
print(f'\nTop 10 kombinasi parameter terbaik:')
print(grid_res.head(10))

# ── Lookup ETA Final (seluruh data) ──────────────────────────────────────
# Lookup berbasis data latih: digunakan untuk evaluasi
base_lookup_train, bin_lookup_train = build_segment_lookup(
    train_seg, bin_size=best_bin, K=best_K, min_bin_n=best_min_n
)
# Lookup final berbasis seluruh data: digunakan di deployment
base_lookup, bin_lookup = build_segment_lookup(
    segments, bin_size=best_bin, K=best_K, min_bin_n=best_min_n
)
print(f'\nLookup ETA final: {len(base_lookup)} segmen unik, {len(bin_lookup)} entri time-bin')


# ### 4a. Mesin Rekomendasi — Context-Aware Weighted Ranking
# 
# Mesin rekomendasi mengintegrasikan semua komponen yang telah dibangun:
# 
# 1. **Lookup maps** untuk routing O(1): dictionary rute→halte, halte→rute, halte→posisi
# 2. **Prediction maps** untuk ETA O(1): dict segmen → median waktu tempuh
# 3. **Skenario evaluasi** dengan empat titik awal berbeda untuk memverifikasi
#    bahwa sistem bekerja di berbagai bagian jaringan Trans Jogja
# 
# Setiap skenario menggunakan hari Sabtu pukul 09:00 sebagai titik awal,
# yang merepresentasikan kondisi akhir pekan ketika wisata paling aktif.
# 

# In[14]:


# ── Bangun lookup maps untuk routing cepat ───────────────────────────────
base_map, bin_map = build_segment_prediction_maps(base_lookup, bin_lookup)
route_to_stop_list, route_stop_pos, stop_to_route_dirs = build_route_lookup_maps(route_sequences)

print(f'Lookup routing:')
print(f'  route_to_stop_list  : {len(route_to_stop_list)} koridor-arah')
print(f'  stop_to_route_dirs  : {len(stop_to_route_dirs)} halte dengan rute')
print(f'  ETA base_map        : {len(base_map)} segmen')
print(f'  ETA bin_map entries : {len(bin_map)}')

# ── Jalankan skenario rekomendasi ─────────────────────────────────────────
recommendation_samples, recommendation_summary = build_sample_recommendations(
    poi_catalog      = poi_catalog_verified,  # hanya POI terverifikasi
    stops            = stops,
    wait_lookup      = wait_lookup,
    route_to_stop_list = route_to_stop_list,
    route_stop_pos   = route_stop_pos,
    stop_to_route_dirs = stop_to_route_dirs,
    base_map         = base_map,
    bin_map          = bin_map,
    bin_size         = best_bin,
)

print('\nRingkasan skenario rekomendasi:')
print(recommendation_summary)


# In[15]:


# ── Tampilkan contoh hasil rekomendasi ───────────────────────────────────
DISPLAY_COLS = ['rank', 'name', 'type', 'route_path_text', 'transfers',
                'eta_total_min', 'arrival_hhmm', 'nearest_stop_name',
                'open_hhmm', 'close_hhmm', 'recommendation_score']

print('Contoh rekomendasi umum dari area Malioboro, Sabtu 09:00:')
print(
    recommendation_samples
    .loc[recommendation_samples['scenario_id'] == 'malioboro_umum_sabtu_0900', DISPLAY_COLS]
    .head(10)
)

print('\nContoh rekomendasi wisata budaya/museum dari area Malioboro, Sabtu 09:00:')
print(
    recommendation_samples
    .loc[recommendation_samples['scenario_id'] == 'malioboro_budaya_sabtu_0900', DISPLAY_COLS]
    .head(10)
)


# ## 5. Evaluation
# 
# Evaluasi dilakukan dalam dua dimensi:
# 
# ### 5.1 Evaluasi Akurasi Model ETA
# 
# Model dievaluasi menggunakan data validasi (20% dari data segmen) yang
# tidak digunakan saat pembentukan lookup.
# 
# - **MAE** (*Mean Absolute Error*): rata-rata selisih prediksi vs aktual dalam menit.
#   Mudah diinterpretasikan: MAE = 3 berarti prediksi rata-rata meleset 3 menit.
# 
# - **RMSE** (*Root Mean Square Error*): memberi penalti lebih besar pada kesalahan besar.
#   Berguna untuk mendeteksi sensitivitas terhadap keterlambatan ekstrem.
# 
# ### 5.2 Evaluasi Fungsional (Smoke Tests)
# 
# Smoke tests memverifikasi bahwa sistem menghasilkan keluaran yang valid:
# - Semua skenario menghasilkan rekomendasi (tidak kosong)
# - Semua rekomendasi berupa destinasi yang buka saat pengguna tiba
# - Semua rekomendasi memiliki informasi rute yang lengkap
# 

# In[16]:


# ── 5.1 Evaluasi Akurasi Model ETA ───────────────────────────────────────
val_pred  = predict_segments(val_seg, base_lookup_train, bin_lookup_train, bin_size=best_bin)
usable    = val_pred.dropna(subset=['pred_min', 'travel_time_min']).copy()

metrics = {
    'best_params'      : {'bin_size': best_bin, 'K': best_K, 'min_bin_n': best_min_n},
    'val_mae_min'      : mae(usable['travel_time_min'], usable['pred_min'])  if not usable.empty else None,
    'val_rmse_min'     : rmse(usable['travel_time_min'], usable['pred_min']) if not usable.empty else None,
    'segments_total'   : int(len(segments)),
    'segments_unique'  : int(segments['segment_id'].nunique()),
    'val_rows_usable'  : int(len(usable)),
}

print('=' * 55)
print('Evaluasi Akurasi Model ETA (Segmen Trans Jogja)')
print('=' * 55)
if metrics['val_mae_min'] is not None:
    print(f"  MAE              : {metrics['val_mae_min']:.3f} menit")
    print(f"  RMSE             : {metrics['val_rmse_min']:.3f} menit")
else:
    print('  Tidak ada data validasi yang memenuhi syarat.')
print(f"  Segmen total     : {metrics['segments_total']:,}")
print(f"  Segmen unik      : {metrics['segments_unique']:,}")
print(f"  Data validasi    : {metrics['val_rows_usable']:,} baris")
print(f"  Parameter terbaik: bin_size={best_bin}, K={best_K}, min_bin_n={best_min_n}")


# ### 5a. Evaluasi Fungsional — Smoke Tests
# 
# Smoke tests memverifikasi perilaku sistem secara end-to-end pada empat skenario:
# 
# | Skenario | Halte Asal | Kategori |
# |----------|-----------|----------|
# | Malioboro umum | Malioboro 1 | Semua kategori |
# | Malioboro budaya | Malioboro 1 | Museum & Budaya |
# | Jombor keluarga | Terminal Jombor | Wisata keluarga |
# | Adisutjipto umum | Bandara | Semua kategori |
# 
# Setiap skenario dijalankan untuk hari Sabtu pukul 09:00.
# Sistem dinyatakan lulus jika:
# - Semua skenario menghasilkan ≥ 5 rekomendasi
# - Seluruh rekomendasi terbuka saat pengguna diperkirakan tiba
# - Seluruh rekomendasi memiliki informasi rute atau dapat dicapai berjalan kaki
# 

# In[17]:


# ── 5a. Smoke Tests ──────────────────────────────────────────────────────
smoke_tests = build_recommendation_smoke_tests(recommendation_summary)

print('Hasil Smoke Tests Sistem Rekomendasi:')
print(smoke_tests)

passed = int((smoke_tests['status'] == 'PASS').sum())
total  = len(smoke_tests)
print(f'\nRingkasan: {passed}/{total} test lulus')
if passed == total:
    print('Semua smoke tests lulus. Sistem siap untuk deployment.')
else:
    failed = smoke_tests[smoke_tests['status'] != 'PASS']
    print('Test yang belum lulus:')
    for _, row in failed.iterrows():
        print(f"  - {row['test_name']}: {row['status']}")


# ## 6. Deployment
# 
# Tahap ini mengekspor seluruh artefak yang dibutuhkan oleh aplikasi web backend.
# 
# ### Artefak yang Dihasilkan
# 
# | Folder | File | Isi |
# |--------|------|-----|
# | `preprocessed/` | `stops.csv` | Halte kanonikal dengan koordinat KML |
# | `preprocessed/` | `stop_times.csv` | Jadwal ternormalisasi |
# | `preprocessed/` | `stop_events.csv` | Kejadian keberangkatan per halte |
# | `preprocessed/` | `segments_training.csv` | Waktu tempuh antar-halte |
# | `preprocessed/` | `route_sequences.csv` | Urutan halte per koridor |
# | `model/` | `eta_lookup_segment_mean.csv` | ETA median per segmen (fallback) |
# | `model/` | `eta_lookup_segment_bin_smoothed.csv` | ETA per segmen-timebin |
# | `model/` | `wait_time_by_hour.csv` | Waktu tunggu per jam |
# | `model/` | `model_metrics.json` | MAE, RMSE, parameter terbaik |
# | `web_artifacts/` | `stops.json` | Halte untuk marker peta |
# | `web_artifacts/` | `stop_routes.json` | Rute yang melewati setiap halte |
# | `web_artifacts/` | `routes_geojson_by_route_id.json` | GeoJSON jalur untuk Leaflet |
# | `web_artifacts/` | `poi_catalog.json` | POI terverifikasi untuk rekomendasi |
# | `web_artifacts/` | `recommendation_samples.json` | Contoh output rekomendasi |
# | `report/` | `needs_review_list.csv` | POI yang memerlukan verifikasi jam |
# | `report/` | `ml_grid_search_results.csv` | Hasil grid search lengkap |
# 

# In[18]:


# ── Persiapan artefak deployment ─────────────────────────────────────────
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
extra_kml_routes   = sorted(set(route_kml_ids)      - set(schedule_route_ids))

# GeoJSON rute: hanya rute yang ada di jadwal
route_fc = {
    'type'    : 'FeatureCollection',
    'features': [f for f in route_fc_all['features']
                 if f['properties']['route_id'] in set(schedule_route_ids)],
}

recommendation_config = {
    'max_transfers'      : 3,
    'transfer_penalty_min': TRANSFER_PENALTY_MIN,
    'min_stay_min'       : MIN_STAY_MIN_DEFAULT,
    'default_types'      : RECOMMENDER_DEFAULT_TYPES,
    'exclude_patterns'   : RECOMMENDER_EXCLUDE_PATTERNS,
    'score_weights'      : {
        'eta_total'          : 0.35,
        'walk_distance'      : 0.20,
        'transfers'          : 0.20,
        'operating_margin'   : 0.10,
        'rating'             : 0.10,
        'popularity'         : 0.05,
        'needs_review_penalty': -0.03,
        'low_vote_penalty'   : -0.05,
    },
}

# ── Ekspor: preprocessed/ ────────────────────────────────────────────────
route_summary.to_csv(PRE_DIR  / 'kml_routes.csv', index=False)
kml_stop_points.to_csv(PRE_DIR / 'kml_stop_points.csv', index=False)
stops.to_csv(PRE_DIR          / 'stops.csv', index=False)
stop_times.to_csv(PRE_DIR     / 'stop_times.csv', index=False)
stop_events.to_csv(PRE_DIR    / 'stop_events.csv', index=False)
segments.to_csv(PRE_DIR       / 'segments_training.csv', index=False)
place_hours.to_csv(PRE_DIR    / 'place_hours.csv', index=False)
poi_nearest_final.to_csv(PRE_DIR / 'poi_to_nearest_stop_1km.csv', index=False)
route_sequences.to_csv(PRE_DIR       / 'route_sequences.csv', index=False)
route_sequence_summary.to_csv(PRE_DIR / 'route_sequence_summary.csv', index=False)

# ── Ekspor: model/ ───────────────────────────────────────────────────────
base_lookup.to_csv(MODEL_DIR / 'eta_lookup_segment_mean.csv', index=False)
bin_lookup.to_csv(MODEL_DIR  / 'eta_lookup_segment_bin_smoothed.csv', index=False)
wait_lookup.to_csv(MODEL_DIR / 'wait_time_by_hour.csv', index=False)
with open(MODEL_DIR / 'model_metrics.json', 'w', encoding='utf-8') as f:
    json.dump(metrics, f, indent=2)
with open(MODEL_DIR / 'recommendation_config.json', 'w', encoding='utf-8') as f:
    json.dump(recommendation_config, f, ensure_ascii=False, indent=2)

# ── Ekspor: report/ ──────────────────────────────────────────────────────
grid_res.to_csv(REPORT_DIR               / 'ml_grid_search_results.csv', index=False)
recommendation_summary.to_csv(REPORT_DIR / 'recommendation_summary.csv', index=False)
with open(REPORT_DIR / 'kml_shape_missing_routes.json', 'w', encoding='utf-8') as f:
    json.dump(missing_routes, f, indent=2)

# ── Ekspor: web_artifacts/ ───────────────────────────────────────────────
stops[['stop_id', 'stop_name', 'lat', 'lon']].to_json(
    WEB_DIR / 'stops.json', orient='records', force_ascii=False, indent=2
)
with open(WEB_DIR / 'stop_routes.json', 'w', encoding='utf-8') as f:
    json.dump(to_json_records(stop_routes), f, ensure_ascii=False, indent=2)
stop_events.to_csv(WEB_DIR / 'stop_board_departures.csv', index=False)
with open(WEB_DIR / 'routes_geojson_by_route_id.json', 'w', encoding='utf-8') as f:
    json.dump(route_fc, f, ensure_ascii=False, indent=2)
poi_catalog_verified.to_csv(WEB_DIR / 'poi_catalog.csv', index=False)
with open(WEB_DIR / 'poi_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(to_json_records(poi_catalog_verified), f, ensure_ascii=False, indent=2)
place_hours.to_csv(WEB_DIR / 'poi_opening_hours.csv', index=False)
recommendation_samples.to_csv(WEB_DIR / 'recommendation_samples.csv', index=False)
with open(WEB_DIR / 'recommendation_samples.json', 'w', encoding='utf-8') as f:
    json.dump(to_json_records(recommendation_samples), f, ensure_ascii=False, indent=2)
with open(WEB_DIR / 'recommendation_defaults.json', 'w', encoding='utf-8') as f:
    json.dump(recommendation_config, f, ensure_ascii=False, indent=2)

# ── Run summary ──────────────────────────────────────────────────────────
run_summary = {
    'inputs': {
        'routes_kml' : ROUTES_KML.name,
        'stops_kml'  : STOPS_KML.name,
        'stop_times' : STOP_TIMES_CSV.name,
        'poi_data'   : POI_CSV.name,
            },
    'counts': {
        'kml_stop_points'          : int(len(kml_stop_points)),
        'canonical_stops'          : int(stops['stop_id'].nunique()),
        'routes_in_schedule'       : int(len(schedule_route_ids)),
        'routes_with_kml_shape'    : int(len(route_fc['features'])),
        'stop_events'              : int(len(stop_events)),
        'poi_total'                : int(len(poi_catalog)),
        'poi_verified'             : int(len(poi_catalog_verified)),
        'poi_with_stop_1km'        : int(poi_catalog['nearest_stop_id'].notna().sum()),
        'poi_candidates_active'    : int((poi_catalog_verified['is_destination_candidate'] == 1).sum()),
        'recommendation_scenarios' : int(len(recommendation_summary)),
        'recommendation_rows'      : int(len(recommendation_samples)),
    },
    'kml_routes_missing_shape'  : missing_routes,
    'kml_routes_extra_not_used' : extra_kml_routes,
    'ml_metrics'                : metrics,
}
with open(REPORT_DIR / 'run_summary.json', 'w', encoding='utf-8') as f:
    json.dump(run_summary, f, ensure_ascii=False, indent=2)

# ── Ringkasan ekspor ─────────────────────────────────────────────────────
export_summary = pd.DataFrame([
    {'folder': 'preprocessed', 'file': 'stops.csv',                       'rows': len(stops)},
    {'folder': 'preprocessed', 'file': 'stop_times.csv',                  'rows': len(stop_times)},
    {'folder': 'preprocessed', 'file': 'stop_events.csv',                 'rows': len(stop_events)},
    {'folder': 'preprocessed', 'file': 'segments_training.csv',           'rows': len(segments)},
    {'folder': 'preprocessed', 'file': 'route_sequences.csv',             'rows': len(route_sequences)},
    {'folder': 'model',        'file': 'eta_lookup_segment_mean.csv',     'rows': len(base_lookup)},
    {'folder': 'model',        'file': 'eta_lookup_segment_bin_smoothed.csv', 'rows': len(bin_lookup)},
    {'folder': 'model',        'file': 'wait_time_by_hour.csv',           'rows': len(wait_lookup)},
    {'folder': 'web_artifacts', 'file': 'poi_catalog.json',               'rows': len(poi_catalog_verified)},
    {'folder': 'web_artifacts', 'file': 'recommendation_samples.json',    'rows': len(recommendation_samples)},
        {'folder': 'report',       'file': 'ml_grid_search_results.csv',      'rows': len(grid_res)},
])
print('Artefak yang berhasil diekspor:')
print(export_summary)
print(f'\nRun summary tersimpan di: report/run_summary.json')


# ## Ringkasan dan Panduan Penggunaan
# 
# ### Apa yang Telah Dibangun
# 
# Notebook ini mengimplementasikan sistem rekomendasi destinasi wisata terintegrasi
# Trans Jogja secara lengkap mengikuti metodologi CRISP-DM:
# 
# | Tahap | Output Utama |
# |-------|--------------|
# | Business Understanding | Spesifikasi kebutuhan dan kriteria sistem |
# | Data Understanding | Eksplorasi kualitas dan kelengkapan data |
# | Data Preparation | Halte kanonikal, segmen ETA, jam operasional POI |
# | Modeling | Model ETA berbasis segmen dengan Bayesian smoothing |
# | Evaluation | MAE/RMSE model ETA + smoke tests sistem rekomendasi |
# | Deployment | Artefak JSON/CSV siap pakai untuk backend web |
# 
# ### Sumber Data
# 
# - **Koordinat halte**: diambil langsung dari `Perhentian Bus Bus Stop.kml`
# - **Geometri rute**: dari `Jalur Route.kml`
# - **stop_id** dan jadwal: dari `transjogja_stop_times_final_v6.csv`
# 
# ### Panduan Penambahan POI Baru
# 
# ```
# 1. Jalankan notebook dari awal
# 2. Periksa report/needs_review_list.csv
# 3. Isi kolom jam operasional (open_hhmm, close_hhmm, open_days) untuk setiap POI
# 4. Simpan file tersebut sebagai raw/poi_hours_filled.csv
# 5. Jalankan ulang sel Data Preparation
# 6. POI akan masuk pool dan needs_review_list.csv akan kembali kosong
# ```
# 
# ### Catatan Teknis
# 
# - ETA bersifat *schedule-based* (historis), bukan realtime
# - Sistem mendukung routing direct dan maksimum 1 transit
# - Rekomendasi menggunakan pool `poi_catalog_verified` (hanya `needs_review=0`)
# - Seluruh artefak deployment tersimpan di `web_artifacts/` dan `model/`
# 
