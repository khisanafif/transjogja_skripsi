SISTEM REKOMENDASI DESTINASI WISATA TRANS JOGJA — v4
=====================================================

CARA MENJALANKAN
----------------
1. pip install -r requirements.txt
2. jupyter notebook transjogja_CRISP_DM_v4_updated.ipynb
3. Run All Cells (dari atas ke bawah)

FILE INPUT (raw/)
-----------------
WAJIB ADA:
  - Jalur Route.kml                    ← data KML rute (sudah ada)
  - Perhentian Bus Bus Stop.kml        ← data KML halte (sudah ada)
  - dataset-wisata-jogja-sekitar.csv   ← dataset POI (sudah ada)
  - transjogja_stop_times_final_v6.csv ← jadwal (sudah ada)
  - transjogja_stops_final_v6.csv      ← daftar halte (sudah ada)
  - transjogja_stops_with_coords.csv   ← koordinat master (sudah ada)
  - poi_opening_hours_verified.csv     ← 53 POI jam web resmi (sudah ada)
  - poi_opening_hours_perhari.csv      ← 99 POI jadwal per hari (sudah ada) [v4 BARU]
  - halte_coords_verified.csv          ← koordinat 62 halte (sudah ada) [v4 BARU]

OPSIONAL:
  - poi_hours_filled.csv               ← template kosong, isi jika ada POI baru

KONSTANTA UTAMA (sesuai Bab 3)
--------------------------------
  MAX_WALK         = 1.200 m
  WALK_SPEED       = 80 m/menit
  TRANSFER_PENALTY = 5 menit
  MIN_STAY         = 120 menit (2 jam)

ALUR needs_review
-----------------
  Jika ada POI baru tanpa jam:
  1. Jalankan notebook → cek report/needs_review_list.csv
  2. Isi jam operasional
  3. Simpan sebagai raw/poi_hours_filled.csv
  4. Re-run dari Cell 13
