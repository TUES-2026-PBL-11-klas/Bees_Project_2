from src.models.zone import Zone

class ZoneSpatialService:

    def get_zones_intersecting_point(self, longitude: float, latitude: float) -> list[Zone]:
        return list(Zone.objects(
            geometry__geo_intersects={
                "type": "Point",
                "coordinates": [longitude, latitude]
            },
            status="active"
        ))

    def get_zones_intersecting_route(self, coordinates: list[list[float]]) -> list[Zone]:
        return list(Zone.objects(
            geometry__geo_intersects={
                "type": "LineString",
                "coordinates": coordinates
            },
            status="active"
        ))

    def is_point_in_any_zone(self, longitude: float, latitude: float) -> bool:
        return self.get_zones_intersecting_point(longitude, latitude) != []

    def get_blocking_zones(self, coordinates: list[list[float]], vessel=None) -> list[Zone]:
        intersecting = self.get_zones_intersecting_route(coordinates)
        blocking = []
        for zone in intersecting:
            if getattr(zone, 'zone_type', None) != "canal":
                blocking.append(zone)
            else:
                if vessel is None:
                    continue
                c = getattr(zone, 'canal_constraints', None)
                if not c:
                    continue

                if c.allowed_vessel_types and vessel.vessel_type not in c.allowed_vessel_types:
                    blocking.append(zone)
                    continue
                if c.blocked_vessel_types and vessel.vessel_type in c.blocked_vessel_types:
                    blocking.append(zone)
                    continue

                if c.max_draft_m and vessel.max_draft_m and vessel.max_draft_m > c.max_draft_m:
                    blocking.append(zone)
                    continue
                if c.max_length_m and vessel.length_m and vessel.length_m > c.max_length_m:
                    blocking.append(zone)
                    continue
                if c.max_beam_m and vessel.beam_m and vessel.beam_m > c.max_beam_m:
                    blocking.append(zone)
                    continue
        return blocking

    def is_route_blocked(self, coordinates: list[list[float]], vessel=None) -> bool:
        return len(self.get_blocking_zones(coordinates, vessel)) > 0
