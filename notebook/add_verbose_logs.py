import json

def update_prints():
    with open('transjogja_CRISP_DM.ipynb', 'r', encoding='utf-8') as f:
        nb = json.load(f)
        
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            source = "".join(cell['source'])
            
            # Replace "Fungsi geospasial dimuat."
            if "print('Fungsi geospasial dimuat.')" in source or 'print("Fungsi geospasial dimuat.")' in source:
                new_print = (
                    "print('\\n\\u2705 Fungsi geospasial berhasil dimuat:')\n"
                    "print('  - parse_routes_kml(), parse_stops_kml(), haversine_m(), dll.')\n"
                    "print('\\n\\u27a1\\ufe0f Silakan jalankan Cell di bawah ini untuk melihat hasil ekstraksi datanya!')"
                )
                source = source.replace("print('Fungsi geospasial dimuat.')", new_print)
                source = source.replace('print("Fungsi geospasial dimuat.")', new_print)
                
            # Replace "Fungsi jadwal dan routing dimuat."
            if "print('Fungsi jadwal dan routing dimuat.')" in source or 'print("Fungsi jadwal dan routing dimuat.")' in source:
                new_print = (
                    "print('\\n\\u2705 Fungsi jadwal dan routing berhasil dimuat:')\n"
                    "print('  - build_stop_events(), build_wait_lookup(), dll.')\n"
                    "print('\\n\\u27a1\\ufe0f Silakan jalankan Cell di bawah ini untuk mengeksekusi pembuatan jadwal!')"
                )
                source = source.replace("print('Fungsi jadwal dan routing dimuat.')", new_print)
                source = source.replace('print("Fungsi jadwal dan routing dimuat.")', new_print)
                
            # Replace "Fungsi model ETA dimuat."
            if "print('Fungsi model ETA dimuat.')" in source or 'print("Fungsi model ETA dimuat.")' in source:
                new_print = (
                    "print('\\n\\u2705 Fungsi model ETA berhasil dimuat:')\n"
                    "print('  - build_segments(), split_train_val_segments(), grid_search_cv(), dll.')\n"
                    "print('\\n\\u27a1\\ufe0f Silakan jalankan Cell di bawah ini untuk melihat hasil pemodelan dan evaluasi!')"
                )
                source = source.replace("print('Fungsi model ETA dimuat.')", new_print)
                source = source.replace('print("Fungsi model ETA dimuat.")', new_print)
                
            # Add logging to recommend_destinations
            if 'def recommend_destinations(' in source and 'print(f"Mencari rekomendasi' not in source:
                source = source.replace(
                    "origin = resolve_stop_query(origin_stop_query, stops)",
                    "print(f\"Mencari rekomendasi wisata dari halte: {origin_stop_query} pada hari {day_name} jam {depart_hhmm}...\")\n    origin = resolve_stop_query(origin_stop_query, stops)"
                )
                source = source.replace(
                    "return deduplicate_recommendations(",
                    "print(f\"Berhasil menemukan {len(out)} rekomendasi awal. Memfilter duplikat dan mengambil top {top_k}...\")\n    return deduplicate_recommendations("
                )
                
            # Add logging to nearest_stop_for_pois
            if 'def nearest_stop_for_pois(' in source and 'print(f"Mencari halte terdekat' not in source:
                source = source.replace(
                    "valid_stops = stops.dropna(subset=['lat', 'lon'])",
                    "print(f\"Mencari halte terdekat untuk {len(poi)} titik wisata...\")\n    valid_stops = stops.dropna(subset=['lat', 'lon'])"
                )
                
            lines = [line + '\n' for line in source.split('\n')]
            if lines:
                lines[-1] = lines[-1].rstrip('\n')
            cell['source'] = lines

    with open('transjogja_CRISP_DM.ipynb', 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

if __name__ == '__main__':
    update_prints()
