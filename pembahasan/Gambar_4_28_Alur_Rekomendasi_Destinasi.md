# Gambar 4.28 Diagram Alur Rekomendasi Destinasi

```mermaid
flowchart TD
    A([Input Koordinat GPS & Preferensi Pengguna]) --> B[Cari Halte Keberangkatan Terdekat (First-Mile)]
    B --> C[Kalkulasi Dijkstra SSSP ke Seluruh Halte di Jaringan]
    C --> D[Pemetaan Halte Tujuan dengan POI Terdekat (Last-Mile)]
    D --> E[Kalkulasi Normalisasi Cost/Benefit]
    E --> F[Penerapan Algoritma Weighted Ranking]
    F --> G[Penyortiran (Sorting) Top-K (Maks 15 Destinasi)]
    G --> H([Tampilkan Rekomendasi ke Antarmuka Website])
```
