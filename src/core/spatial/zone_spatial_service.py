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

    def is_route_blocked(self, coordinates: list[list[float]]) -> bool:
        return self.get_zones_intersecting_route(coordinates) != []

    def get_blocking_zones(self, coordinates: list[list[float]]) -> list[Zone]:
        return self.get_zones_intersecting_route(coordinates)
