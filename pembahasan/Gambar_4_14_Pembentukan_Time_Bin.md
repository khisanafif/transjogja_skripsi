# Gambar 4.14 Diagram Pembentukan Time Bin

```mermaid
flowchart TD
    A[Data Waktu Historis (Stop Events)]
    B{Jam Operasional\n05:30 - 20:30}
    C[Pembentukan Rentang Jam\nInterval 3 Jam bin_size = 3]
    D[Agregasi Data Segmen per Time Bin]
    E[Menghitung Nilai Median Waktu Tempuh & Wait Time]
    F[(eta_lookup.json & wait_time.json)]
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
```
