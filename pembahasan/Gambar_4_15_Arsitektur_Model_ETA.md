# Gambar 4.15 Arsitektur Model ETA

```mermaid
flowchart TD
    A[Data Perjalanan Historis GTFS] --> B[Segmentasi Titik ke Titik (Halte-to-Halte)]
    B --> C[Pengelompokan Waktu (Time Binning)]
    C --> D[Kalkulasi Median Waktu Tempuh & Tunggu]
    D --> E[(Tabel Look-Up Model ETA)]
    E --> F[Injeksi Bobot Edge pada Algoritma Dijkstra]
```
