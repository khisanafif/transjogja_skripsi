# Gambar 4.12 Diagram Normalisasi Data

```mermaid
flowchart TD
    A([Raw Data Mentah GTFS & POI])
    B[Penghapusan Missing Values & Duplikat]
    C[Standarisasi Format Waktu (HH:MM:SS)]
    D[Konversi Tipe Data Spasial (Float 6 Digit)]
    E[Penanganan Outlier & Imputasi Rating]
    F([Data Bersih / Clean Data])
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
```
