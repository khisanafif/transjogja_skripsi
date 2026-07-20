# Gambar 4.9 Graph Jaringan Trans Jogja

```mermaid
flowchart TD
    classDef user fill:#9b59b6,stroke:#8e44ad,color:#fff,rx:20px,ry:20px;
    classDef stop fill:#f1c40f,stroke:#f39c12,color:#333,rx:20px,ry:20px;
    classDef poi fill:#e74c3c,stroke:#c0392b,color:#fff,rx:20px,ry:20px;
    
    U((Lokasi User)):::user
    S1((Halte Asal)):::stop
    S2((Halte Transit)):::stop
    S3((Halte Tujuan)):::stop
    D((Destinasi Wisata)):::poi
    
    U -- "WALK_START\n(Jarak Haversine)" --> S1
    S1 -- "BOARD\n(Waktu Tunggu rute_A)" --> S1
    
    S1 ===| "BUS (rute_A)\n(Akumulasi seg_eta)" |=== S2
    
    S2 -. "TRANSFER\n(Waktu Tunggu rute_B)" .-> S2
    
    S2 ===| "BUS (rute_B)\n(Akumulasi seg_eta)" |=== S3
    
    S3 -- "ALIGHT" --> S3
    S3 -- "WALK_END\n(Jarak Haversine)" --> D
```
