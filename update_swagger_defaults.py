import re

def add_examples_to_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Import Field and Path
    if 'from pydantic import BaseModel, field_validator' in content:
        content = content.replace(
            'from pydantic import BaseModel, field_validator',
            'from pydantic import BaseModel, field_validator, Field'
        )
    if 'from fastapi import APIRouter, HTTPException, Query' in content:
        content = content.replace(
            'from fastapi import APIRouter, HTTPException, Query',
            'from fastapi import APIRouter, HTTPException, Query, Path'
        )

    # get_nearest_stops
    content = content.replace(
        'lat: float = Query(..., description="Latitude pengguna"),',
        'lat: float = Query(..., description="Latitude pengguna", examples=[-7.7797]),'
    )
    content = content.replace(
        'lon: float = Query(..., description="Longitude pengguna"),',
        'lon: float = Query(..., description="Longitude pengguna", examples=[110.3752]),'
    )

    # get_stop
    content = content.replace(
        'def get_stop(stop_id: str):',
        'def get_stop(stop_id: str = Path(..., examples=["HT_194"])):',
    )

    # get_poi_detail
    content = content.replace(
        'def get_poi_detail(poi_id: int):',
        'def get_poi_detail(poi_id: int = Path(..., examples=[10])):'
    )

    # RecommendRequest
    content = re.sub(
        r'class RecommendRequest\(BaseModel\):\n\s+origin_stop_id: str',
        'class RecommendRequest(BaseModel):\n    origin_stop_id: str = Field(..., examples=["HT_194"])',
        content
    )

    # RouteRequest
    content = re.sub(
        r'class RouteRequest\(BaseModel\):\n\s+origin_stop_id: str\n\s+origin_walk_min: float = 0.0\n\s+dest_poi_id: int',
        'class RouteRequest(BaseModel):\n    origin_stop_id: str = Field(..., examples=["HT_194"])\n    origin_walk_min: float = 0.0\n    dest_poi_id: int = Field(..., examples=[10])',
        content
    )

    # ItineraryRequest
    content = re.sub(
        r'class ItineraryRequest\(BaseModel\):\n\s+origin_stop_id: str',
        'class ItineraryRequest(BaseModel):\n    origin_stop_id: str = Field(..., examples=["HT_194"])',
        content
    )

    # get_schedule
    content = content.replace(
        'stop_id: str = Query(...),',
        'stop_id: str = Query(..., examples=["HT_194"]),'
    )

    # get_routes_geojson
    content = content.replace(
        'def get_routes_geojson(route_id: Optional[str] = None):',
        'def get_routes_geojson(route_id: Optional[str] = Query(None, examples=["1A"])):'
    )

    # get_route_detail
    content = content.replace(
        'def get_route_detail(route_dir: str):',
        'def get_route_detail(route_dir: str = Path(..., examples=["1A_0"])):'
    )

    # get_routes_between
    content = content.replace(
        'from_stop: str = Query(...),',
        'from_stop: str = Query(..., examples=["HT_194"]),'
    )
    content = content.replace(
        'to_stop: str = Query(...),',
        'to_stop: str = Query(..., examples=["HT_001"]),'
    )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Updated {path}")

add_examples_to_file(r'c:\Users\User\Downloads\transjogja_skripsi\deploy_backend\routers\all.py')
try:
    add_examples_to_file(r'c:\Users\User\Downloads\transjogja_skripsi\app\backend\routers\all.py')
except Exception as e:
    print(e)
