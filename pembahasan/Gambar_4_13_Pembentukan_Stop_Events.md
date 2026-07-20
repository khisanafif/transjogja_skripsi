# Gambar 4.13 Diagram Pembentukan Stop Events

```mermaid
flowchart TD
    A[(Raw stop_times.txt)]
    B[Ekstrak trip_id, arrival_time, departure_time, stop_id]
    C[Pengurutan (Sort) berdasarkan trip_id & stop_sequence]
    D[Menghitung durasi perjalanan antar halte]
    E[Validasi: Filter durasi & jarak yang tidak logis]
    F[(Tabel Transaksional Stop Events)]
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
```
