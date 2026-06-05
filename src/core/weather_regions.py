"""
Maritime weather regions — predefined coordinates for global sea areas.

Each region includes a representative center point and a bounding box
used for weather data queries and map display.
"""

from __future__ import annotations

MARITIME_REGIONS: list[dict] = [
    {
        "id": "black_sea",
        "name": "Black Sea",
        "lat": 43.0,
        "lon": 35.0,
        "bbox": {"min_lat": 41.0, "max_lat": 46.5, "min_lon": 27.5, "max_lon": 41.5},
    },
    {
        "id": "mediterranean_west",
        "name": "Mediterranean West",
        "lat": 38.0,
        "lon": 5.0,
        "bbox": {"min_lat": 35.0, "max_lat": 43.5, "min_lon": -5.5, "max_lon": 16.0},
    },
    {
        "id": "mediterranean_east",
        "name": "Mediterranean East",
        "lat": 34.0,
        "lon": 28.0,
        "bbox": {"min_lat": 30.0, "max_lat": 37.5, "min_lon": 16.0, "max_lon": 36.0},
    },
    {
        "id": "north_sea",
        "name": "North Sea",
        "lat": 55.0,
        "lon": 3.0,
        "bbox": {"min_lat": 51.0, "max_lat": 61.0, "min_lon": -3.0, "max_lon": 9.0},
    },
    {
        "id": "baltic_sea",
        "name": "Baltic Sea",
        "lat": 58.0,
        "lon": 19.0,
        "bbox": {"min_lat": 53.5, "max_lat": 65.5, "min_lon": 10.0, "max_lon": 30.0},
    },
    {
        "id": "arabian_sea",
        "name": "Arabian Sea",
        "lat": 18.0,
        "lon": 65.0,
        "bbox": {"min_lat": 8.0, "max_lat": 25.0, "min_lon": 50.0, "max_lon": 77.0},
    },
    {
        "id": "bay_of_bengal",
        "name": "Bay of Bengal",
        "lat": 14.0,
        "lon": 85.0,
        "bbox": {"min_lat": 5.0, "max_lat": 22.0, "min_lon": 77.0, "max_lon": 95.0},
    },
    {
        "id": "south_china_sea",
        "name": "South China Sea",
        "lat": 12.0,
        "lon": 115.0,
        "bbox": {"min_lat": 3.0, "max_lat": 23.0, "min_lon": 100.0, "max_lon": 121.0},
    },
    {
        "id": "caribbean_sea",
        "name": "Caribbean Sea",
        "lat": 18.0,
        "lon": -75.0,
        "bbox": {"min_lat": 9.0, "max_lat": 23.0, "min_lon": -89.0, "max_lon": -60.0},
    },
    {
        "id": "gulf_of_mexico",
        "name": "Gulf of Mexico",
        "lat": 25.0,
        "lon": -90.0,
        "bbox": {"min_lat": 18.0, "max_lat": 31.0, "min_lon": -98.0, "max_lon": -80.0},
    },
    {
        "id": "north_atlantic",
        "name": "North Atlantic",
        "lat": 45.0,
        "lon": -30.0,
        "bbox": {"min_lat": 30.0, "max_lat": 60.0, "min_lon": -60.0, "max_lon": -5.0},
    },
    {
        "id": "south_atlantic",
        "name": "South Atlantic",
        "lat": -20.0,
        "lon": -10.0,
        "bbox": {"min_lat": -40.0, "max_lat": 0.0, "min_lon": -40.0, "max_lon": 15.0},
    },
    {
        "id": "indian_ocean",
        "name": "Indian Ocean",
        "lat": -10.0,
        "lon": 70.0,
        "bbox": {"min_lat": -30.0, "max_lat": 5.0, "min_lon": 40.0, "max_lon": 100.0},
    },
    {
        "id": "north_pacific",
        "name": "North Pacific",
        "lat": 35.0,
        "lon": -160.0,
        "bbox": {"min_lat": 20.0, "max_lat": 50.0, "min_lon": -180.0, "max_lon": -130.0},
    },
    {
        "id": "red_sea",
        "name": "Red Sea",
        "lat": 20.0,
        "lon": 38.5,
        "bbox": {"min_lat": 12.5, "max_lat": 28.0, "min_lon": 32.0, "max_lon": 44.0},
    },
    {
        "id": "english_channel",
        "name": "English Channel",
        "lat": 50.0,
        "lon": -1.0,
        "bbox": {"min_lat": 48.5, "max_lat": 51.5, "min_lon": -5.5, "max_lon": 2.5},
    },
]
