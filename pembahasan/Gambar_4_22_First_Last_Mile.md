# Gambar 4.10 Diagram First-Mile–Bus–Last-Mile

```mermaid
flowchart LR
    classDef node fill:#34495e,stroke:#2c3e50,color:#fff,rx:5px,ry:5px;
    classDef transit fill:#27ae60,stroke:#2ecc71,color:#fff,rx:5px,ry:5px;
    classDef highlight fill:#e74c3c,stroke:#c0392b,color:#fff,rx:5px,ry:5px;

    A(Koordinat Pengguna):::node
    
    B(Halte Terdekat):::node
    C(Halte Tujuan):::node
    
    D(Titik POI Wisata):::node

    A -- "First-Mile (WALK_START)\nRadius max 1200m" --> B:::highlight
    B === "Main Transit\n(Algoritma SSSP Dijkstra)" === C:::transit
    C -- "Last-Mile (WALK_END)\nSesuai walk_dist_m" --> D:::highlight
```
