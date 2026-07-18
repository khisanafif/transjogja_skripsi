import json
import re

def update_notebook():
    file_path = 'transjogja_CRISP_DM.ipynb'
    with open(file_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    # Markdown replacements
    md_replacements = [
        # 0
        [
            "# Sistem Rekomendasi Destinasi Wisata Terintegrasi Trans Jogja\n",
            "\n",
            "Notebook ini merupakan dokumentasi eksekusi kode untuk penelitian skripsi yang berfokus pada perancangan sistem rekomendasi destinasi wisata di Daerah Istimewa Yogyakarta. Sistem ini diintegrasikan secara langsung dengan jaringan rute dan jadwal transportasi publik **Trans Jogja**.\n",
            "\n",
            "Penelitian ini disusun dengan menerapkan standar metodologi **CRISP-DM** (*Cross-Industry Standard Process for Data Mining*) yang mencakup tahapan-tahapan berikut:\n",
            "\n",
            "$$\\text{Business Understanding} \\to \\text{Data Understanding} \\to \\text{Data Preparation} \\to \\text{Modeling} \\to \\text{Evaluation} \\to \\text{Deployment}$$\n",
            "\n",
            "## Tujuan dan Lingkup Penelitian\n",
            "\n",
            "Fokus utama dari sistem yang dibangun dalam penelitian ini adalah untuk mengintegrasikan tiga dimensi data spasial dan temporal:\n",
            "- **Data Geometri Rute**: Jaringan operasional koridor bus Trans Jogja.\n",
            "- **Data Halte & Jadwal Historis**: Estimasi waktu kedatangan (ETA) bus antar halte.\n",
            "- **Data Destinasi Wisata**: Titik lokasi pariwisata beserta jam operasionalnya.\n",
            "\n",
            "**Luaran Utama (Output):** Sebuah daftar rekomendasi destinasi wisata yang paling optimal untuk dikunjungi dari halte keberangkatan pengguna. Penilaian rekomendasi didasarkan pada perhitungan estimasi waktu perjalanan (ETA), kemudahan akses rute (minim transit dan jarak jalan kaki), serta kecocokan jam operasional wisata.\n"
        ],
        # 1
        [
            "## Tahap Persiapan Lingkungan Kerja (Setup)\n",
            "Pada tahap awal ini, kita mendefinisikan seluruh pustaka (library) Python yang dibutuhkan dan mengatur direktori kerja untuk penyimpanan artefak penelitian.\n"
        ],
        # 2
        [
            "## 1. Pemahaman Bisnis & 2. Pemahaman Data\n",
            "Tahapan ini berfokus pada pengumpulan data sumber mentah (raw data) yang digunakan dalam penelitian dan memvalidasi struktur serta kelengkapannya.\n"
        ],
        # 3
        [
            "### Modul Fungsi Geospasial\n",
            "Kumpulan fungsi di bawah ini dirancang khusus untuk memproses data geospasial. Fungsi-fungsi ini bertugas mengekstraksi koordinat dari file KML jalur Trans Jogja dan menghitung jarak spasial antar titik halte menggunakan formula Haversine.\n"
        ],
        # 4
        [
            "### Proses Pemuatan Data Sumber\n",
            "Membaca dataset utama (rute, halte, jadwal, dan titik wisata) ke dalam memori (DataFrame) agar siap untuk dieksplorasi dan dipersiapkan lebih lanjut.\n"
        ],
        # 5
        [
            "## 3. Persiapan Data (Data Preparation)\n",
            "Tahapan ini adalah inti dari transformasi data mentah menjadi format terstruktur. Kita akan mengekstraksi fitur-fitur spasial dan membangun jaringan jadwal bus.\n"
        ],
        # 6
        [
            "### Modul Fungsi Penjadwalan dan Waktu\n",
            "Fungsi-fungsi berikut didedikasikan untuk menangani ekstraksi waktu kedatangan armada, pembuatan segmen rute antar halte berurutan, serta perhitungan median waktu tunggu (headway) per jam operasional.\n"
        ],
        # 7
        [
            "### Modul Fungsi Estimasi Waktu Perjalanan (ETA)\n",
            "Modul ini bertugas untuk menyusun data riwayat perjalanan menjadi segmen-segmen antar halte. Data segmen historis inilah yang akan dipelajari oleh model untuk memprediksi ETA pergerakan bus.\n"
        ],
        # 8
        [
            "### Modul API Pencarian Rute dan Titik Wisata (POI)\n",
            "Berisi fungsi algoritma utama untuk pencarian jalur (routing) dan evaluasi titik destinasi (POI). API ini dirancang agar parameter input dan alur logikanya mudah dipahami untuk kebutuhan evaluasi sistem rekomendasi.\n"
        ],
        # 9
        [
            "### Eksekusi Persiapan Data\n",
            "Menjalankan seluruh modul fungsi persiapan data yang telah didefinisikan di atas terhadap dataset mentah penelitian.\n"
        ],
        # 10
        [
            "## 4. Pemodelan (Modeling)\n",
            "Tahap pemodelan bertujuan untuk memprediksi Estimasi Waktu Perjalanan (ETA) bus di setiap segmen jalan menggunakan data riwayat pergerakan armada historis.\n"
        ],
        # 11
        [
            "### Pelatihan dan Optimasi Model ETA\n",
            "Pelatihan dilakukan menggunakan pendekatan *Bayesian Smoothing* pada data riwayat perjalanan. Kita juga menerapkan pencarian parameter optimal (*Grid Search*) dengan skema validasi silang (*5-Fold Cross-Validation*).\n"
        ],
        # 12
        [
            "## 5. Evaluasi (Evaluation)\n",
            "Mengukur tingkat akurasi prediksi model ETA yang telah dilatih menggunakan metrik evaluasi standar seperti RMSE (*Root Mean Square Error*) dan MAE (*Mean Absolute Error*).\n"
        ],
        # 13
        [
            "## 6. Penyebaran (Deployment)\n",
            "Tahapan akhir dalam kerangka kerja CRISP-DM. Pada tahap ini, hasil penelitian diekspor menjadi *lookup tables* statis dan artefak JSON/CSV yang siap dikonsumsi langsung oleh sistem antarmuka web.\n"
        ],
        # 14
        [
            "### Eksekusi Penyimpanan Artefak Deployment\n",
            "Menyimpan tabel model ETA, konfigurasi API rekomendasi, jaringan rute, dan katalog wisata yang sudah terverifikasi ke dalam direktori `preprocessed`, `model`, dan `web_artifacts`.\n"
        ]
    ]

    md_idx = 0
    for cell in nb['cells']:
        if cell['cell_type'] == 'markdown':
            if md_idx < len(md_replacements):
                cell['source'] = md_replacements[md_idx]
            md_idx += 1
            
        elif cell['cell_type'] == 'code':
            # Add docstring to find_best_path
            source_str = "".join(cell['source'])
            
            if 'def find_best_path(' in source_str and 'Mencari rute bus Trans Jogja terbaik' not in source_str:
                source_str = source_str.replace(
                    "def find_best_path(origin_stop_id, dest_stop_id, depart_tod_min,\n                   stop_to_route_dirs, route_to_stop_list, route_stop_pos,\n                   base_map, bin_map, bin_size, wait_lookup,\n                   max_transfers=4, transfer_penalty_min=TRANSFER_PENALTY_MIN):",
                    "def find_best_path(origin_stop_id, dest_stop_id, depart_tod_min,\n                   stop_to_route_dirs, route_to_stop_list, route_stop_pos,\n                   base_map, bin_map, bin_size, wait_lookup,\n                   max_transfers=4, transfer_penalty_min=TRANSFER_PENALTY_MIN):\n    \"\"\"\n    Mencari rute bus Trans Jogja terbaik dari halte asal ke halte tujuan menggunakan algoritma Dijkstra berbasis ETA.\n    \n    API Input:\n    - origin_stop_id (str): ID halte asal keberangkatan.\n    - dest_stop_id (str): ID halte tujuan wisata.\n    - depart_tod_min (float): Waktu keberangkatan dalam format menit sejak tengah malam.\n    \n    API Output:\n    - dict: Ringkasan rute perjalanan (mencakup jumlah transit, total ETA, dan daftar halte).\n    \"\"\""
                )
                cell['source'] = [line + ('\n' if i < len(source_str.split('\n'))-1 and not line.endswith('\n') else '') for i, line in enumerate(source_str.split('\n'))]

            # Re-join since we might have modified it
            source_str = "".join(cell['source'])
            
            if 'def recommend_destinations(' in source_str and 'Menghasilkan daftar rekomendasi destinasi wisata' not in source_str:
                source_str = source_str.replace(
                    "def recommend_destinations(origin_stop_query, depart_hhmm, day_name,\n                           poi_catalog, stops, wait_lookup,\n                           route_to_stop_list, route_stop_pos, stop_to_route_dirs,\n                           base_map, bin_map, bin_size,\n                           preferred_types=None, top_k=10,\n                           min_stay_min=MIN_STAY_MIN_DEFAULT,\n                           require_verified_hours=False, max_transfers=4):",
                    "def recommend_destinations(origin_stop_query, depart_hhmm, day_name,\n                           poi_catalog, stops, wait_lookup,\n                           route_to_stop_list, route_stop_pos, stop_to_route_dirs,\n                           base_map, bin_map, bin_size,\n                           preferred_types=None, top_k=10,\n                           min_stay_min=MIN_STAY_MIN_DEFAULT,\n                           require_verified_hours=False, max_transfers=4):\n    \"\"\"\n    Menghasilkan daftar rekomendasi destinasi wisata terintegrasi dengan akses Trans Jogja.\n    \n    API Input:\n    - origin_stop_query (str): Nama atau ID halte keberangkatan pengguna.\n    - depart_hhmm (str): Jam keberangkatan dalam format 'HH:MM'.\n    - day_name (str): Nama hari untuk pengecekan ketersediaan jam buka wisata.\n    - preferred_types (list): Kategori wisata yang diminati (opsional).\n    \n    API Output:\n    - DataFrame: Daftar top-K wisata yang direkomendasikan beserta skor kecocokan dan detail rute.\n    \"\"\""
                )
                cell['source'] = [line + ('\n' if not line.endswith('\n') and i < len(source_str.split('\n'))-1 else '') for i, line in enumerate(source_str.split('\n'))]
                
            # Formatting the lines array properly is better done via splitlines(True)
            source_str = "".join(cell['source'])
            cell['source'] = [line + '\n' for line in source_str.splitlines()]
            # Fix last element newline
            if len(cell['source']) > 0 and not source_str.endswith('\n'):
                cell['source'][-1] = cell['source'][-1].rstrip('\n')

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        
    print("Notebook updated successfully.")

if __name__ == '__main__':
    update_notebook()
