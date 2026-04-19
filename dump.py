
import json, sys
sys.path.insert(0, ".")
from src.core.graph_builder import _CORRIDORS
from src.core.ports import PORT_REGISTRY
ports = {k: {"lat": v.latitude, "lon": v.longitude} for k, v in PORT_REGISTRY.items()}
corridors = [(c[0], c[1]) for c in _CORRIDORS]
print(json.dumps({"ports": ports, "corridors": corridors}))
