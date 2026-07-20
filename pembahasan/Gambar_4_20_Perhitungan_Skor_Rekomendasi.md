# Gambar 4.20 Diagram Perhitungan Skor Rekomendasi

```mermaid
flowchart TD
    A[Total Skor Rekomendasi Destinasi] -->|35%| B[Komponen Waktu Tempuh ETA (Menit)]
    A -->|20%| C[Komponen Jarak Jalan Kaki First & Last Mile (Meter)]
    A -->|20%| D[Komponen Jumlah Transit (Frekuensi Pindah Bus)]
    A -->|10%| E[Komponen Toleransi Waktu Tunggu (Menit)]
    A -->|10%| F[Komponen Ulasan Rating Wisata (Bintang 1-5)]
    A -->|5%| G[Komponen Popularitas Wisata (Total Jumlah Vote)]
    
    B -.->|Normalisasi Cost| H(Semakin Kecil Angka, Semakin Tinggi Skor)
    C -.->|Normalisasi Cost| H
    D -.->|Normalisasi Cost| H
    E -.->|Normalisasi Cost| H
    
    F -.->|Normalisasi Benefit| I(Semakin Besar Angka, Semakin Tinggi Skor)
    G -.->|Normalisasi Benefit| I
```
