import urllib.request
import json

def test_route(origin, dest):
    data = json.dumps({"origin_node_id": origin, "destination_node_id": dest, "vessel_id": None}).encode('utf-8')
    req = urllib.request.Request("http://localhost:8080/api/v1/routes/calculate", data=data, headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        print(f"{origin} -> {dest}: SUCCESS ({len(result.get('waypoints', []))} waypoints)")
    except urllib.error.HTTPError as e:
        print(f"{origin} -> {dest}: FAILED ({e.code} - {e.read().decode('utf-8')})")
    except Exception as e:
        print(f"{origin} -> {dest}: ERROR ({e})")

test_route("GENOA", "MARSEILLE")
test_route("VARNA", "CONSTANTA")
test_route("LISBON", "BILBAO")
test_route("WP_CAPE_ST_VINCENT", "ALGECIRAS")
test_route("CASABLANCA", "SINES")
