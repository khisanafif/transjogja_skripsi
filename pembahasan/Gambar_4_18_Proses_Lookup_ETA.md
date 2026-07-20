# Gambar 4.18 Diagram Proses Lookup ETA

```mermaid
flowchart TD
    A([Fungsi Pencarian ETA (Asal, Tujuan, Jam, Rute)]) --> B{Apakah ada record\ndi eta_lookup.json?}
    B -- Ada (Exact Match) --> C[Return ETA Median Aktual]
    B -- Tidak Ada --> D{Apakah ada rata-rata waktu\nuntuk rute ini?}
    D -- Ada (Route Average) --> E[Return Rata-rata Rute Keseluruhan]
    D -- Tidak Ada --> F[Return Fallback Default (3 Menit)]
    
    C --> G([Bobot Masuk ke Graph SSSP])
    E --> G
    F --> G
```
