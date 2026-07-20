# Gambar 4.24 Flowchart Pencarian Jalur

```mermaid
flowchart TD
    A([Mulai Pencarian Rute (Dijkstra SSSP)]) --> B[Inisialisasi: Semua Jarak Node = Tak Terhingga]
    B --> C[Set Jarak Node Halte Asal = 0]
    C --> D[Masukkan Halte Asal ke Priority Queue]
    D --> E{Apakah Priority Queue Kosong?}
    
    E -- Ya --> F([Selesai: Rute Tidak Ditemukan])
    E -- Tidak --> G[Ambil Node U dengan Jarak Terkecil]
    
    G --> H{Apakah U adalah Halte Tujuan?}
    H -- Ya --> I([Selesai: Rekonstruksi Jalur Terpendek dari Array Pendahulu])
    H -- Tidak --> J[Iterasi ke semua Node Tetangga V dari U]
    
    J --> K{Jarak(U) + Bobot Waktu(U,V) < Jarak(V)?}
    K -- Ya --> L[Update Jarak(V) dan Catat Pendahulu(V) = U]
    L --> M[Masukkan V ke dalam Priority Queue]
    M --> E
    K -- Tidak --> E
```
