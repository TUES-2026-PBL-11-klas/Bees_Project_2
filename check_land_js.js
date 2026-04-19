const fs = require('fs');
const turf = require('@turf/turf');

let landFeatures = [];
try {
  const landData = JSON.parse(fs.readFileSync('ne_50m_land.geojson', 'utf8'));
  landFeatures = landData.features;
} catch (e) {
  console.log("Downloading ne_50m_land.geojson...");
}

async function run() {
  if (landFeatures.length === 0) {
    const res = await fetch('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson');
    const data = await res.json();
    fs.writeFileSync('ne_50m_land.geojson', JSON.stringify(data));
    landFeatures = data.features;
  }

  const landGeometries = landFeatures.map(f => f.geometry).filter(Boolean);

  function wrapLonNear(lon, referenceLon) {
    let wrapped = lon;
    while (wrapped - referenceLon > 180) wrapped -= 360;
    while (wrapped - referenceLon < -180) wrapped += 360;
    return wrapped;
  }

  function wrapGeometryLongitudes(geometry, referenceLon) {
    if (!geometry || !geometry.coordinates) return geometry;
    const wrapCoords = (coords) => {
      if (!Array.isArray(coords)) return coords;
      if (coords.length >= 2 && typeof coords[0] === 'number' && typeof coords[1] === 'number') {
        return [wrapLonNear(coords[0], referenceLon), coords[1]];
      }
      return coords.map(wrapCoords);
    };
    return { ...geometry, coordinates: wrapCoords(geometry.coordinates) };
  }

  function segmentIntersectsLand(a, b) {
    const referenceLon = (a.lon + b.lon) / 2;
    const aLon = wrapLonNear(a.lon, referenceLon);
    const bLon = wrapLonNear(b.lon, referenceLon);


    const dLat = b.lat - a.lat;
    const dLon = bLon - aLon;
    const p1 = [aLon + dLon * 0.05, a.lat + dLat * 0.05];
    const p2 = [bLon - dLon * 0.05, b.lat - dLat * 0.05];

    const segment = [ p1, p2 ];
    const line = turf.lineString(segment);
    const [lineMinLon, lineMinLat, lineMaxLon, lineMaxLat] = turf.bbox(line);

    for (const landGeometry of landGeometries) {
      const wrappedLand = wrapGeometryLongitudes(landGeometry, referenceLon);
      const [landMinLon, landMinLat, landMaxLon, landMaxLat] = turf.bbox(wrappedLand);
      if (landMaxLon < lineMinLon || landMinLon > lineMaxLon || landMaxLat < lineMinLat || landMinLat > lineMaxLat) continue;
      if (turf.booleanIntersects(line, wrappedLand)) return true;
    }
    return false;
  }


  const execSync = require('child_process').execSync;
  const pythonScript = `
import json, sys
sys.path.insert(0, ".")
from src.core.graph_builder import _CORRIDORS
from src.core.ports import PORT_REGISTRY
ports = {k: {"lat": v.latitude, "lon": v.longitude} for k, v in PORT_REGISTRY.items()}
corridors = [(c[0], c[1]) for c in _CORRIDORS]
print(json.dumps({"ports": ports, "corridors": corridors}))
  `;
  fs.writeFileSync('dump.py', pythonScript);
  const out = execSync('python dump.py');
  const {ports, corridors} = JSON.parse(out);

  for (const [src, dst] of corridors) {
    if (!ports[src] || !ports[dst]) continue;
    const p1 = ports[src];
    const p2 = ports[dst];
    if (segmentIntersectsLand(p1, p2)) {
      console.log(`CROSSES: ${src} -> ${dst}`);
    }
  }
}
run();
