import json
import re

docstrings = {
    'parse_route_id': 'Mengurai dan membersihkan ID rute dari string mentah KML.',
    'parse_kml_coord_text': 'Mengekstrak list koordinat (longitude, latitude) dari format string teks KML.',
    'extract_route_refs': 'Mengekstrak referensi rute Trans Jogja yang ada dalam deskripsi KML.',
    'parse_routes_kml': 'Membaca file KML rute dan mengekstrak properti geometri (LineString).',
    'parse_stops_kml': 'Membaca file KML perhentian/halte dan mengekstrak koordinat (Point).',
    'canonicalize_stops': 'Menghasilkan ID dan nama halte kanonikal dengan mencocokkan data KML dan CSV.',
    'parse_hhmm': 'Mengkonversi string waktu (HH:MM) menjadi format menit sejak tengah malam.',
    'hhmm_from_minutes': 'Mengkonversi nilai menit (float) menjadi format string waktu (HH:MM).',
    'normalize_trip_times': 'Menormalkan data jadwal dengan konversi format waktu menjadi numerik.',
    'build_stop_events': 'Membuat tabel peristiwa kedatangan di setiap halte.',
    'build_wait_lookup': 'Menghitung waktu tunggu median per jam operasional (headway) berdasarkan historis.',
    'build_route_sequences': 'Menyusun urutan halte kanonikal untuk setiap rute bus.',
    'build_route_lookup_maps': 'Membangun tabel pencarian (lookup) rute ke halte dan halte ke rute.',
    'build_segments': 'Membangun segmen perjalanan antar dua halte berurutan berdasarkan jadwal.',
    'winsorize_segments_per_segment': 'Memotong data outlier waktu perjalanan per segmen menggunakan kuantil P5-P95.',
    'split_train_val_segments': 'Memisahkan data segmen menjadi himpunan pelatihan (train) dan validasi (val).',
    'build_segment_lookup': 'Membangun tabel lookup prediksi ETA menggunakan pendekatan Bayesian smoothing.',
    'predict_segments': 'Memprediksi waktu perjalanan segmen (ETA) berdasarkan tabel lookup.',
    'mae': 'Menghitung metrik evaluasi Mean Absolute Error (MAE).',
    'rmse': 'Menghitung metrik evaluasi Root Mean Square Error (RMSE).',
    'make_cv_folds': 'Membagi data perjalanan menjadi beberapa lipatan (folds) untuk Cross-Validation.',
    'grid_search_cv': 'Mencari parameter model (Grid Search) dengan skema n-Fold Cross Validation.',
    'to_json_records': 'Mengkonversi DataFrame menjadi list of dict (JSON records) tanpa nilai NaN.',
    'build_segment_prediction_maps': 'Membangun peta pencarian cepat (dictionary) untuk prediksi segmen ETA.',
    'lookup_wait_minutes': 'Mendapatkan estimasi waktu tunggu penumpang di halte pada jam tertentu.',
    'predict_segment_minutes': 'Memprediksi waktu tempuh segmen spesifik menggunakan peta prediksi ETA.',
    'format_route_dir_label': 'Memformat label ID rute dan arahnya agar mudah dibaca.',
    'find_best_path': 'Mencari rute bus terbaik dari halte asal ke halte tujuan menggunakan algoritma Dijkstra berbasis ETA.',
    'resolve_stop_query': 'Mencari data halte berdasarkan query input teks (ID atau nama).',
    'expand_open_days': 'Mengekstrak dan menerjemahkan teks deskripsi hari buka menjadi set string nama hari.',
    'is_open_on_day': 'Mengecek apakah suatu destinasi buka pada hari yang ditentukan.',
    'safe_scale_positive': 'Melakukan normalisasi skala min-max (0-1) secara aman pada nilai positif.',
    'safe_scale_inverse': 'Melakukan normalisasi skala min-max terbalik (semakin kecil semakin bagus, mendekati 1).',
    'build_destination_candidate_flags': 'Menandai POI yang valid sebagai kandidat rekomendasi wisata (memfilter layanan publik).',
    'build_recommendation_reason': 'Membangun teks alasan/penjelasan rute perjalanan untuk diberikan kepada pengguna.'
}

def inject_docstrings():
    with open('transjogja_CRISP_DM.ipynb', 'r', encoding='utf-8') as f:
        nb = json.load(f)

    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
            
        source = "".join(cell['source'])
        
        for func_name, docstring in docstrings.items():
            # Regex to find: def func_name(args):
            pattern = re.compile(rf'^(def {func_name}\b.*?:)\s*\n', re.MULTILINE)
            
            # Check if function exists in this cell
            if pattern.search(source):
                # Check if it already has a docstring
                match = pattern.search(source)
                end_pos = match.end()
                
                # Look at the next few characters to see if there is already a docstring (""" or \'\'\')
                if not re.match(r'\s*(?:"""|\'\'\')', source[end_pos:]):
                    # Inject docstring
                    replacement = f'\\1\n    """\n    {docstring}\n    """\n'
                    source = pattern.sub(replacement, source, count=1)
                    
        # Update cell lines
        lines = [line + '\n' for line in source.split('\n')]
        if lines:
            lines[-1] = lines[-1].rstrip('\n')
        cell['source'] = lines

    with open('transjogja_CRISP_DM.ipynb', 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

if __name__ == '__main__':
    inject_docstrings()
