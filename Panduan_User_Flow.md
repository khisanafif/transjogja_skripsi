# Panduan Alur Pengguna (User Flow) - Sistem Rekomendasi Trans Jogja

Panduan ini menjabarkan langkah-demi-langkah (skenario pengguna) berdasarkan diagram *User Flow* (Gambar 4.15). Alur ini menggambarkan bagaimana seorang wisatawan (pengguna) berinteraksi dengan sistem mulai dari membuka aplikasi hingga mendapatkan navigasi perjalanan.

---

## 1. Tahap Awal (Entry Point)
**Langkah 1: Mulai - Buka Aplikasi/Web**
- Pengguna mengakses URL atau membuka aplikasi sistem rekomendasi pariwisata Trans Jogja di perangkat mereka.

**Langkah 2: Halaman Utama (Landing Page)**
- Pengguna disambut oleh halaman utama yang berisi penjelasan singkat mengenai aplikasi dan menu navigasi.
- Di tahap ini (Langkah Keputusan / *Decision*), pengguna dihadapkan pada 4 pilihan alur utama sesuai dengan kebutuhan mereka.

---

## 2. Pilihan Alur Utama

### Alur 1: Rekomendasi Destinasi (Eksplorasi)
*Ditujukan bagi wisatawan yang belum tahu ingin pergi ke mana dan butuh rekomendasi wisata berdasarkan kriteria tertentu.*
- **Aksi:** Pengguna memilih menu **"Peta Interaktif & Rekomendasi"**.
- **Aksi:** Pengguna mengatur filter dan bobot preferensi (misal: lebih mengutamakan waktu tempuh cepat, sedikit transit, atau tempat yang sedang populer).
- **Sistem:** Algoritma melakukan proses *Weighted Ranking* (pembobotan) yang dipadukan dengan perhitungan jarak (Dijkstra) dari lokasi pengguna.
- **Hasil:** Layar menampilkan daftar **Top-K Rekomendasi** (misal: 5 tempat wisata paling cocok).

### Alur 2: Cari Rute Spesifik (Tujuan Pasti)
*Ditujukan bagi wisatawan yang sudah tahu nama tempat wisata yang ingin dituju (misal: "Saya mau ke Candi Prambanan").*
- **Aksi:** Pengguna memilih menu **"Cari Rute Spesifik"**.
- **Aksi:** Pengguna memilih satu destinasi tujuan dari daftar pencarian.
- **Sistem:** Algoritma secara langsung mengeksekusi *Single-Source Shortest Path* (Dijkstra SSSP) untuk mencari kombinasi trayek bus tercepat.
- **Hasil:** Layar menampilkan **Detail Rute Terbaik** secara tunggal ke tujuan tersebut.

### Alur 3: Day Planner (Rencana Perjalanan Harian)
*Ditujukan bagi wisatawan yang memiliki waktu luang seharian dan ingin sistem menyusun rencana perjalanan ke beberapa tempat sekaligus.*
- **Aksi:** Pengguna memilih menu **"Rencana Perjalanan Harian"**.
- **Aksi:** Pengguna memasukkan batasan waktu operasional mereka (Jam Berangkat, Jam Pulang) dan minimum durasi kunjungan di satu tempat wisata (misal: minimal 2 jam/tempat).
- **Sistem:** AI/Algoritma akan mengkalkulasi kombinasi beberapa tempat wisata (POI) yang muat dijenguk dalam rentang waktu tersebut (menghitung ETA bus dan jam buka-tutup lokasi).
- **Hasil:** Layar menampilkan **Jadwal Rute Beruntun** (Itinerary seharian).

### Alur 4: Informasional (Edukasi & Data)
*Ditujukan bagi pengguna yang hanya ingin mencari informasi dasar Trans Jogja.*
- **Aksi:** Pengguna memilih menu informasi pendukung seperti **Jadwal Bus**, **Peta Semua Rute** (melihat poligon rute Trans Jogja), atau **Tentang**.
- **Hasil:** Layar menampilkan informasi statis atau peta rute interaktif tanpa fitur rekomendasi yang rumit. 
- *Alur Selesai.* (Pengguna selesai bereksplorasi di halaman informasi).

---

## 3. Tahap Eksekusi (Navigasi Perjalanan)
*Jika pengguna menggunakan Alur 1, 2, atau 3, mereka akan bermuara pada tahap eksekusi perjalanan ini.*

**Langkah 1: Pilih Rute/Jadwal**
- Dari hasil rekomendasi/pencarian, pengguna mengklik tombol "Pilih" atau "Lihat Detail Rute" pada opsi yang ditawarkan.

**Langkah 2: Tampilkan Arahan Navigasi Lengkap**
- Halaman akan memandu pengguna langkah demi langkah (secara *step-by-step navigation*).
- **First-mile:** Menampilkan rute jalan kaki dari titik awal pengguna ke Halte Keberangkatan terdekat.
- **Transit:** Memberitahu pengguna harus naik bus trayek apa (misal: 1A), dan di halte mana harus turun atau oper bus (transit).
- **Last-mile:** Menampilkan rute jalan kaki dari Halte Kedatangan menuju gerbang tempat wisata.

**Langkah 3: Selesai - Mulai Perjalanan**
- Wisatawan menutup aplikasi (atau menyimpannya di latar belakang) dan mulai melakukan perjalanan fisiknya di lapangan menggunakan armada Trans Jogja sesuai panduan yang diberikan.
