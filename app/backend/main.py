"""
main.py — FastAPI production-ready entry point.
"""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import startup
from routers.all import router

# ==============================================================================
# KONFIGURASI CORS & ORIGIN
# Mengatur domain mana saja yang diizinkan untuk mengakses API ini.
# ==============================================================================
# ── origins dari env (production: set ALLOWED_ORIGINS) ───────────────────────
ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app = FastAPI(
    title="Trans Jogja Tourism API",
    description="Sistem Rekomendasi Destinasi Wisata Terintegrasi Rute Trans Jogja",
    version="3.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ==============================================================================
# PENANGANAN ERROR GLOBAL
# Menangani error yang tidak terduga dan mengembalikan respons JSON.
# ==============================================================================
# ── global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exc(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Terjadi kesalahan server. Silakan coba lagi."},
    )

@app.on_event("startup")
async def on_startup():
    startup.load_all()

app.include_router(router, prefix="/api")

@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Trans Jogja Tourism API",
        "version": "3.1.0",
        "status": "ok",
        "docs": "/docs",
    }

@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "stops": len(startup.stops_list),
        "poi": len(startup.poi_list),
        "route_dirs": len(startup.route_to_stop_list),
        "eta_segments": len(startup.eta_exact),
    }
