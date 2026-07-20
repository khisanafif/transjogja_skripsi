# Gambar 4.13 Arsitektur Implementasi Keseluruhan Sistem Website

```mermaid
flowchart TD
    classDef client fill:#34495e,stroke:#2c3e50,color:#fff,rx:5px,ry:5px;
    classDef frontend fill:#3498db,stroke:#2980b9,color:#fff,rx:10px,ry:10px;
    classDef backend fill:#2ecc71,stroke:#27ae60,color:#fff,rx:10px,ry:10px;
    classDef database fill:#f1c40f,stroke:#f39c12,color:#333,rx:10px,ry:10px;

    U((Wisatawan)):::client
    
    subgraph Frontend [Frontend Application (React + Vite)]
        F1(UI Components - Tailwind CSS):::frontend
        F2(State Management - Zustand):::frontend
        F3(Interactive Map - React-Leaflet):::frontend
        F4(REST API Client - Axios/Fetch):::frontend
        F5(Informational Modules - Jadwal, Peta Rute, Tentang):::frontend
    end
    
    subgraph Backend [Backend Service (FastAPI Python)]
        B_API(API Routers - Endpoints):::backend
        B1(Routing Engine - Dijkstra SSSP):::backend
        B2(Recommender Engine - Weighted Ranking):::backend
        B3(Day Planner Engine - Itinerary Logic):::backend
        B4(ETA & Wait Time Calculator):::backend
        B5(In-Memory Data Loader):::backend
    end
    
    subgraph DataStorage [Data Storage (JSON Artifacts)]
        D1[(Halte & POI)]:::database
        D2[(Rute & Segmen Jaringan)]:::database
        D3[(ETA & Waktu Tunggu Historis)]:::database
    end

    U -->|Input & Akses Browser| F1
    F1 <--> F2
    F1 <--> F3
    F1 <--> F4
    F1 <--> F5
    
    F4 <-->|HTTP GET/POST (JSON)| B_API
    
    B_API --> B1
    B_API --> B2
    B_API --> B3
    
    B1 <--> B4
    B2 <--> B4
    B3 <--> B4
    
    B1 <--> B5
    B2 <--> B5
    B3 <--> B5
    B4 <--> B5
    
    B5 <-->|Load JSON saat Startup| DataStorage
```
