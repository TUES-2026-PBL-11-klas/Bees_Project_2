import sys
import os

# Ensure src is in the python path
sys.path.insert(0, os.path.abspath("."))

from src.core.graph_builder import _CORRIDORS, PORT_REGISTRY
from global_land_mask import globe
import numpy as np

def points_on_line(lat1, lon1, lat2, lon2, num_points=50):
    lats = np.linspace(lat1, lat2, num_points)
    lons = np.linspace(lon1, lon2, num_points)
    return lats, lons

problematic_corridors = []

for corridor in _CORRIDORS:
    src_id, dst_id = corridor[0], corridor[1]
    if src_id not in PORT_REGISTRY or dst_id not in PORT_REGISTRY:
        continue
    
    src = PORT_REGISTRY[src_id]
    dst = PORT_REGISTRY[dst_id]
    
    lats, lons = points_on_line(src.latitude, src.longitude, dst.latitude, dst.longitude, 100)
    
    # We skip the very first and last point to allow ports to be slightly on land/coast
    is_on_land = globe.is_land(lats[5:-5], lons[5:-5])
    
    if np.any(is_on_land):
        problematic_corridors.append((src_id, dst_id))
        print(f"Land crossed: {src_id} -> {dst_id}")

print("Total problematic:", len(problematic_corridors))
