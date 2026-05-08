import math
import requests
from typing import List, Dict, Any

def create_polygon_from_point(lat: float, lng: float, radius_meters: float = 200) -> List[List[float]]:
    """Creates a GeoJSON polygon (square bounding box) around a central point."""
    earth_radius = 6378137.0  # Earth radius in meters
    
    # Coordinate offsets in radians
    dLat = radius_meters / earth_radius
    dLon = radius_meters / (earth_radius * math.cos(math.pi * lat / 180))

    # Convert to degrees
    lat_offset = dLat * 180 / math.pi
    lon_offset = dLon * 180 / math.pi

    # Create a square bounding box: [top_left, bottom_left, bottom_right, top_right, top_left]
    polygon = [
        [lng - lon_offset, lat + lat_offset],
        [lng - lon_offset, lat - lat_offset],
        [lng + lon_offset, lat - lat_offset],
        [lng + lon_offset, lat + lat_offset],
        [lng - lon_offset, lat + lat_offset] # Close the polygon
    ]
    return polygon

class SpatialFetchAgent:
    """
    Agent 2: Spatial Fetch
    Pulls environmental context (NDVI, polygons) via Agromonitoring.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.polygon_url = "http://api.agromonitoring.com/agro/1.0/polygons"
        self.ndvi_url = "http://api.agromonitoring.com/agro/1.0/ndvi/history"

    def create_and_fetch_spatial_data(self, lat: float, lng: float, name: str) -> Dict[str, Any]:
        """Creates a polygon and prepares spatial context for NDVI pulling."""
        print(f"[Agent 2] Generating spatial buffer for {name}")
        
        # 1. Create Polygon mapping
        geo_json = {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [create_polygon_from_point(lat, lng)]
            }
        }
        
        payload = {
            "name": f"Campus_Buffer_{name.replace(' ', '_')}",
            "geo_json": geo_json
        }
        
        headers = {"Content-Type": "application/json"}
        poly_resp = requests.post(
            f"{self.polygon_url}?appid={self.api_key}&duplicated=true", 
            json=payload, 
            headers=headers
        )
        
        poly_data = poly_resp.json()
        if "id" not in poly_data:
            if "error" in poly_data:
                print(f"[Agent 2] Polygon warning: {poly_data['error']}. Proceeding with simulated spatial layer.")
                return {"polygon_id": "simulated_poly", "geo_json": geo_json, "simulated": True}
            raise ValueError(f"Failed to create polygon: {poly_data}")
            
        poly_id = poly_data["id"]
        print(f"[Agent 2] Registered spatial footprint: {poly_id}")
        
        return {
            "polygon_id": poly_id,
            "geo_json": geo_json,
            "simulated": False
        }
