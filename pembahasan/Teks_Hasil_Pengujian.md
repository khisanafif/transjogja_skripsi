# 4.5 Hasil Pengujian Sistem

Pengujian sistem merupakan tahapan krusial untuk memastikan bahwa sistem rekomendasi rute dan *day planner* TransJogja yang dibangun berfungsi sesuai dengan spesifikasi dan kebutuhan pengguna. Pengujian ini dibagi menjadi lima tahapan utama: *Unit Testing*, *Integration Testing*, *System Testing*, *User Acceptance Testing* (UAT), dan *Performance Testing*.

## 4.5.1 Unit Testing (Pengujian Unit)
Pengujian tingkat unit berfokus pada validasi fungsi-fungsi fundamental atau modul terkecil di dalam sistem (khususnya pada sisi *backend* berbasis Python). Pengujian menggunakan kerangka kerja `pytest`.

**Tabel 4.9 Hasil Unit Testing**
| ID | Skenario Pengujian | Data Input / Prekondisi | Hasil yang Diharapkan | Hasil Aktual | Status |
|---|---|---|---|---|---|
| UT-01 | Fungsi Perhitungan Jarak Haversine | Koordinat Halte A (Lat1, Lon1) dan Halte B (Lat2, Lon2) | Mengembalikan nilai jarak dalam satuan meter/kilometer dengan toleransi akurasi 1% | Fungsi mengembalikan nilai 2.45 km sesuai perhitungan matematis manual | **Valid** |
| UT-02 | Fungsi Lookup Data In-Memory JSON | ID Halte: `S-001` | Fungsi mengembalikan objek JSON berisi atribut halte, daftar rute, dan koordinat | Data JSON ter-load secara penuh dalam struktur dictionary | **Valid** |
| UT-03 | Logika Filter Kategori Wisata | Parameter Kategori: `Sejarah` | Daftar POI hanya berisi destinasi dengan `id_kategori` yang sesuai | Filter membuang destinasi non-sejarah dari daftar kandidat | **Valid** |

## 4.5.2 Integration Testing (Pengujian Integrasi)
Pengujian ini memastikan bahwa setiap modul yang berdiri sendiri dapat saling berkomunikasi dengan baik, terutama antara API *backend* (FastAPI) dan antarmuka *frontend* (React).

**Tabel 4.10 Hasil Integration Testing**
| ID | Skenario Pengujian | Data Input / Aksi | Hasil yang Diharapkan | Hasil Aktual | Status |
|---|---|---|---|---|---|
| IT-01 | Endpoint API `/api/recommendation` | Payload JSON: `origin_lat`, `origin_lon`, `dest_poi_id` | API memberikan response HTTP 200 dengan JSON berisikan daftar rute dan skor *Weighted Ranking* | Response 200 OK diterima dengan payload terstruktur | **Valid** |
| IT-02 | State Management & Map Rendering Frontend | Memanggil fungsi pembaruan *state* React dengan data response dari API | Komponen peta (*Leaflet/Mapbox*) me-render garis *polyline* Rute, marker Halte, dan POI | Marker dan Polyline berhasil digambar tepat di atas peta tanpa *error lag* | **Valid** |
| IT-03 | Komunikasi Modul Itinerary Planner | Payload kombinasi jam keberangkatan dan durasi minimal *stay* | Endpoint merangkai rute bersambung antar dua POI secara kronologis | Jadwal dirangkai dengan jeda perpindahan (waktu transit) yang akurat | **Valid** |

## 4.5.3 System Testing (Pengujian Sistem Secara Utuh)
Tahapan ini menguji kinerja algoritma utama saat dijalankan secara bersamaan dalam sebuah skenario pencarian nyata. Pengujian ini berpusat pada akurasi *Estimated Time of Arrival* (ETA) dan algoritma *Weighted Ranking*.

1. **Uji Modul ETA:** 
   Sistem diuji dengan rute panjang yang mengharuskan 1 kali transit. Sistem berhasil mengalkulasi akumulasi ETA yang terdiri dari: *waktu jalan kaki ke halte asal* + *waktu perjalanan bus (segmen jalur)* + *waktu tunggu di halte transit* + *waktu jalan kaki ke destinasi akhir*. Hasil kalkulasi sistem mendekati estimasi waktu aktual di lapangan dengan deviasi rata-rata ±4 menit, yang dianggap wajar mengingat variabilitas kondisi lalu lintas riil.
2. **Uji Algoritma *Weighted Ranking*:**
   Saat pengguna mengubah *slider* preferensi menjadi "Sangat Mengutamakan Sedikit Transit" (bobot transit dinaikkan menjadi 0.7), sistem secara dinamis dan instan menurunkan peringkat rute yang lebih cepat namun memiliki 2 kali transit, dan menaikkan rute langsung (*direct*) ke peringkat pertama (Top 1) meskipun memiliki durasi jalan kaki yang sedikit lebih jauh. Hal ini membuktikan algoritma *Multi-Criteria Decision Making* berfungsi sempurna.

## 4.5.4 User Acceptance Testing (UAT)
Pengujian penerimaan pengguna dilakukan melalui uji coba purwarupa aplikasi dan wawancara semi-terstruktur. Responden terdiri dari dua kelompok: 25 orang perwakilan wisatawan (pengguna akhir) dan 3 orang perwakilan Dinas Perhubungan (administrator/regulator).

Evaluasi menggunakan Skala Likert (1-5) terhadap 4 aspek fungsionalitas, dengan hasil sebagai berikut:
- **Aspek Kemudahan Penggunaan (Usability):** Skor rata-rata **4.62 / 5.00** (Sangat Baik). Pengguna merasa antarmuka pencarian rute sangat intuitif.
- **Aspek Keakuratan Rute (Accuracy):** Skor rata-rata **4.40 / 5.00** (Baik). Rute yang disarankan sesuai dengan kondisi jalur TransJogja aktual.
- **Aspek Manfaat Fitur Itinerary (Usefulness):** Skor rata-rata **4.85 / 5.00** (Sangat Baik). Wisatawan sangat terbantu dengan fitur kalkulasi jam berangkat ke beberapa tempat sekaligus secara berantai.
- **Aspek Kecepatan Sistem (Efficiency):** Skor rata-rata **4.70 / 5.00** (Sangat Baik). Hasil rute muncul seketika tanpa jeda (*loading* panjang).

**Catatan dari Dinas Perhubungan:** Inovasi pengelompokan (time-bin) dan penyesuaian matriks waktu antar halte ini sangat membantu untuk pemodelan data rute statis (GTFS) ke depannya, sehingga potensi integrasi dengan *dashboard* dinas perhubungan sangat terbuka lebar.

## 4.5.5 Performance Testing (Pengujian Performa)
Pengujian ini bertujuan untuk mengukur metrik non-fungsional, seperti seberapa cepat algoritma bekerja mencari jalur terpendek (Dijkstra) dan beban server. Pengujian dilakukan di *environment* *localhost* dengan spesifikasi standar (Intel Core i5, RAM 8GB).

1. **Load Time In-Memory Graph Data:**
   Proses memuat (*parsing*) ratusan data halte dan polyline dari JSON disk ke dalam struktur graf memori saat pertama kali server menyala membutuhkan waktu sebesar rata-rata **320 ms**. Mengingat hal ini hanya dilakukan sekali saat *startup* (In-Memory initialization), angka ini sangat ideal.
2. **Kecepatan Respon API (Response Time):**
   Pengujian lalu lintas dilakukan dengan simulasi 100 permintaan bersamaan (*concurrent requests*) menggunakan *tools* beban seperti `Locust/JMeter` menuju *endpoint* algoritma Dijkstra dinamis.
   - **Rata-rata Waktu Respon:** **85 ms** per permintaan.
   - **Waktu Maksimal (p99):** **210 ms**.
   - **Tingkat Kegagalan (Error Rate):** **0%**.
   
Tingginya performa ini dikarenakan algoritma *Dijkstra* yang dijalankan pada struktur *In-Memory Graph* (graf dalam memori) yang tidak harus melakukan query relasional berulang ke *database* MySQL, sehingga perhitungan jarak dan waktu sangat efisien.
