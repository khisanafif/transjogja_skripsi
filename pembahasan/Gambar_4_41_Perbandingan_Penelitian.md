# Gambar 4.41 Diagram Perbandingan Penelitian Ini dengan Penelitian Sebelumnya

```mermaid
flowchart LR
    classDef lama fill:#95a5a6,stroke:#7f8c8d,color:#fff;
    classDef baru fill:#2ecc71,stroke:#27ae60,color:#fff;

    subgraph Penelitian Terdahulu (Baseline)
        A(Kalkulasi Waktu Berdasarkan Jarak & Kecepatan Statis):::lama
        B(Pencarian Rute Hanya untuk Satu Tujuan):::lama
        C(Tidak Mempertimbangkan Waktu Tunggu Bus):::lama
    end
    
    subgraph Sistem Yang Diusulkan
        D(Kalkulasi Waktu Dinamis via Segment-Based Historical Binning):::baru
        E(Rekomendasi Multi-Destinasi & Fitur Itinerary / Day Planner):::baru
        F(Inklusi Toleransi Waktu Tunggu & Realita Jalan Kaki):::baru
    end
    
    A -->|Disempurnakan Menjadi| D
    B -->|Diperluas Menjadi| E
    C -->|Dilengkapi Menjadi| F
```
