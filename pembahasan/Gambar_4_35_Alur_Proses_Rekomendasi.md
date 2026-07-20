# Gambar 4.35 Diagram Alur Proses Rekomendasi Secara Kode (Deployment)

```mermaid
flowchart TD
    A[Frontend React Axios] -->|POST /recommend| B[Backend FastAPI (routers/all.py)]
    B --> C[Fungsi utama recommend() di recommender.py]
    C --> D[Eksekusi sssp_from_origin() di routing.py]
    D --> E[Lakukan Looping Filter POI Jarak 1.2km (Haversine)]
    E --> F[Kalkulasi Weighted Ranking (Normalisasi Cost/Benefit * Bobot)]
    F --> G[Sort Descending & Ambil Top K POI]
    G --> H[Return JSON Response ke Frontend]
    H --> I[Render Hasil di Komponen UI dan React-Leaflet Map]
```
