-- ==============================================================================
-- SQL DDL (Data Definition Language) Schema - OPTIMAL & NORMALIZED (3NF)
-- Sistem Rekomendasi Trans Jogja & Pariwisata
-- ==============================================================================

-- 1. Tabel Kategori Wisata (Lookup Table untuk Normalisasi POI)
CREATE TABLE poi_category (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE
);

-- 2. Tabel Master Halte (Stop)
CREATE TABLE stop (
    stop_id VARCHAR(50) PRIMARY KEY,
    stop_name VARCHAR(100) NOT NULL,
    lat DECIMAL(10, 8) NOT NULL,
    lon DECIMAL(11, 8) NOT NULL
);

-- 3. Tabel Master Trayek/Rute Utama (Tanpa membedakan arah)
CREATE TABLE route (
    route_id VARCHAR(50) PRIMARY KEY, -- contoh: "1A"
    route_name VARCHAR(100) NOT NULL  -- contoh: "Jalur 1A Prambanan"
);

-- 4. Tabel Varian Trayek / Trip (Memisahkan arah pergi dan pulang)
CREATE TABLE trip (
    trip_id VARCHAR(50) PRIMARY KEY, -- contoh: "1A_0"
    route_id VARCHAR(50) NOT NULL,
    direction SMALLINT NOT NULL,     -- 0 untuk arah maju (outbound), 1 untuk arah mundur (inbound)
    CONSTRAINT fk_trip_route FOREIGN KEY (route_id) 
        REFERENCES route(route_id) ON DELETE CASCADE
);

-- 5. Tabel POI (Point of Interest) - NORMALISASI 3NF
-- Atribut jarak dan halte terdekat dihilangkan untuk dipisah ke tabel M:N
CREATE TABLE poi (
    poi_id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id INT NOT NULL,
    rating DECIMAL(3, 2),
    vote_count INT,
    lat DECIMAL(10, 8) NOT NULL,
    lon DECIMAL(11, 8) NOT NULL,
    description TEXT,
    CONSTRAINT fk_poi_category FOREIGN KEY (category_id) 
        REFERENCES poi_category(category_id) ON DELETE RESTRICT
);

-- 6. Tabel Akses Halte ke POI (Many-to-Many POI dan STOP)
-- Menyelesaikan masalah 1 POI yang bisa diakses dari banyak halte berbeda
CREATE TABLE poi_stop_access (
    poi_id INT NOT NULL,
    stop_id VARCHAR(50) NOT NULL,
    walk_dist_m DECIMAL(10, 2) NOT NULL,
    walk_time_min DECIMAL(10, 2) NOT NULL,
    is_nearest BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (poi_id, stop_id),
    CONSTRAINT fk_access_poi FOREIGN KEY (poi_id) 
        REFERENCES poi(poi_id) ON DELETE CASCADE,
    CONSTRAINT fk_access_stop FOREIGN KEY (stop_id) 
        REFERENCES stop(stop_id) ON DELETE CASCADE
);

-- 7. Tabel Jam Operasional POI (Normalisasi Composite Key)
CREATE TABLE poi_operating_hour (
    poi_id INT NOT NULL,
    day_of_week SMALLINT NOT NULL,    -- 1=Senin, 2=Selasa, ..., 7=Minggu
    open_time TIME NOT NULL,
    close_time TIME NOT NULL,
    PRIMARY KEY (poi_id, day_of_week),
    CONSTRAINT fk_operating_hour_poi FOREIGN KEY (poi_id) 
        REFERENCES poi(poi_id) ON DELETE CASCADE
);

-- 8. Tabel Urutan Halte dalam Trip (Normalisasi Composite Key)
CREATE TABLE trip_stop (
    trip_id VARCHAR(50) NOT NULL,
    stop_sequence INT NOT NULL,
    stop_id VARCHAR(50) NOT NULL,
    PRIMARY KEY (trip_id, stop_sequence),
    CONSTRAINT fk_ts_trip FOREIGN KEY (trip_id) 
        REFERENCES trip(trip_id) ON DELETE CASCADE,
    CONSTRAINT fk_ts_stop FOREIGN KEY (stop_id) 
        REFERENCES stop(stop_id) ON DELETE CASCADE
);

-- 9. Tabel Segmen Graf / Edge (Untuk Kalkulasi Dijkstra)
CREATE TABLE trip_segment (
    trip_id VARCHAR(50) NOT NULL,
    source_stop_id VARCHAR(50) NOT NULL,
    target_stop_id VARCHAR(50) NOT NULL,
    avg_travel_time_min DECIMAL(10, 2),
    distance_m DECIMAL(10, 2),
    geometry_path TEXT, 
    PRIMARY KEY (trip_id, source_stop_id, target_stop_id),
    CONSTRAINT fk_segment_source FOREIGN KEY (source_stop_id) 
        REFERENCES stop(stop_id) ON DELETE CASCADE,
    CONSTRAINT fk_segment_target FOREIGN KEY (target_stop_id) 
        REFERENCES stop(stop_id) ON DELETE CASCADE,
    CONSTRAINT fk_segment_trip FOREIGN KEY (trip_id) 
        REFERENCES trip(trip_id) ON DELETE CASCADE
);

-- 10. Tabel Jadwal Kedatangan Bus (Timetable)
CREATE TABLE schedule (
    schedule_id SERIAL PRIMARY KEY,
    trip_id VARCHAR(50) NOT NULL,
    stop_id VARCHAR(50) NOT NULL,
    departure_time TIME NOT NULL,
    CONSTRAINT fk_schedule_trip FOREIGN KEY (trip_id) 
        REFERENCES trip(trip_id) ON DELETE CASCADE,
    CONSTRAINT fk_schedule_stop FOREIGN KEY (stop_id) 
        REFERENCES stop(stop_id) ON DELETE CASCADE
);

-- 11. Tabel Statistik Waktu Tunggu Halte per Jam
-- Memisahkan wait_time dari tabel schedule yang statis
CREATE TABLE stop_wait_time (
    stop_id VARCHAR(50) NOT NULL,
    hour_of_day SMALLINT NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    avg_wait_time_min DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (stop_id, hour_of_day),
    CONSTRAINT fk_wait_time_stop FOREIGN KEY (stop_id) 
        REFERENCES stop(stop_id) ON DELETE CASCADE
);
