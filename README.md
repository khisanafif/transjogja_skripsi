# Trans Jogja Recommender — Full Package v2

## Struktur
```
transjogja_full_v2/
├── README.md               ← file ini
├── notebook/               ← pipeline data (CRISP-DM)
│   ├── transjogja_CRISP_DM_v4_updated.ipynb
│   ├── requirements.txt
│   ├── README.txt
│   ├── raw/                ← data input (KML, CSV, Excel)
│   ├── preprocessed/       ← hasil preprocessing notebook
│   ├── model/              ← lookup ETA, wait time, model metrics
│   ├── report/             ← audit: needs_review, coverage, smoke tests
│   └── web_artifacts/      ← output siap pakai untuk backend
└── app/                    ← production app (FastAPI + React)
    ├── README.md
    ├── backend/
    │   ├── data/           ← JSON artifacts (sudah sesuai TJ_ format)
    │   ├── engine/         ← ETA, recommender, routing, planner
    │   ├── routers/
    │   ├── startup.py
    │   └── main.py
    └── frontend/
        ├── src/
        └── dist/           ← built frontend (siap serve)
```

## Stop ID — Format Konsisten: TJ_XXXX
Seluruh file menggunakan format `TJ_0001` s.d. `TJ_0534`.
Lihat `app/backend/data/stop_id_mapping.json` untuk referensi old→new.

## Cara Menjalankan

### Notebook (pipeline data)
```bash
cd notebook
pip install -r requirements.txt
jupyter notebook transjogja_CRISP_DM_v4_updated.ipynb
```

### App (backend + frontend)
```bash
cd app/backend
pip install -r requirements.txt
bash start.sh
# Frontend: buka app/frontend/dist/index.html atau serve dengan static server
```

## Alur Kerja

1. Jalankan notebook → hasilkan artefak baru di `web_artifacts/`
2. Salin artefak ke `app/backend/data/`
3. Restart backend

## needs_review Gate

POI dengan `needs_review=1` dikecualikan dari rekomendasi.
- Notebook: cek `report/needs_review_list.csv`
- App: cek `app/backend/data/needs_review_list.json`

Isi jam operasional → simpan sebagai `raw/poi_hours_filled.csv` → re-run notebook
