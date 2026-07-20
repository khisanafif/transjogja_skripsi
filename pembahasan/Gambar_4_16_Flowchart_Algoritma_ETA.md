# Gambar 4.7 Flowchart Algoritma Estimasi ETA (Segment Edge)

```mermaid
flowchart TD
    classDef startEnd fill:#8e44ad,stroke:#732d91,color:#fff,rx:15px,ry:15px;
    classDef process fill:#3498db,stroke:#2980b9,color:#fff,rx:5px,ry:5px;
    classDef decision fill:#e67e22,stroke:#d35400,color:#fff,rx:50px,ry:50px;

    S([Mulai: Kalkulasi Bobot Edge Dijkstra]):::startEnd
    
    A(Ambil Pasangan Halte Asal dan Halte Tujuan\ndalam Satu Rute yang Sama):::process
    
    B{Apakah nilai ETA Segmen\n(eta_exact) ada di Lookup JSON?}:::decision
    
    C(Gunakan Median Historis Segmen\neta_exact):::process
    D(Gunakan Rata-Rata Rute\nroute_avg_eta):::process
    E(Fallback ke Default 3.0 Menit):::process
    
    F(Tambahkan Waktu Tunggu Bus\nBerdasarkan Jam Keberangkatan):::process
    
    G([Return Total Waktu Edge untuk Graph]):::startEnd

    S --> A
    A --> B
    B -- Ya --> C
    B -- Tidak --> D
    D -- Jika Tidak Ada --> E
    
    C --> F
    D --> F
    E --> F
    
    F --> G
```
