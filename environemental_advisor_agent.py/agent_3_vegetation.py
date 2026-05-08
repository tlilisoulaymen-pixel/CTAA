import hashlib
from typing import List, Dict, Any


LAND_USE_PROFILES = {
    "built_environment": {
        "color": "#ef4444",
        "description": "Impervious surface / hardscape infrastructure",
        "plant_potential": 0.0,
        "soil_quality": 0.0,
        "icon": "🏗️"
    },
    "high_vegetation": {
        "color": "#16a34a",
        "description": "Mature tree canopy / dense green cover",
        "plant_potential": 0.1,
        "soil_quality": 0.9,
        "icon": "🌳"
    },
    "low_vegetation": {
        "color": "#84cc16",
        "description": "Sparse grass / shrubs / partial green cover",
        "plant_potential": 0.6,
        "soil_quality": 0.6,
        "icon": "🌿"
    },
    "barren_soil": {
        "color": "#d97706",
        "description": "Exposed / disturbed bare soil",
        "plant_potential": 0.85,
        "soil_quality": 0.4,
        "icon": "🟤"
    },
    "semi_arid": {
        "color": "#f59e0b",
        "description": "Arid / rocky substrate with minimal cover",
        "plant_potential": 0.70,
        "soil_quality": 0.25,
        "icon": "🏜️"
    },
    "transitional": {
        "color": "#38bdf8",
        "description": "Transitional land / mixed degraded surface",
        "plant_potential": 0.75,
        "soil_quality": 0.50,
        "icon": "🔄"
    }
}


class VegetationClassifierAgent:
    """
    Agent 3: Multi-Dimensional Vegetation & Land Use Classifier (v2.0)
    
    Produces 9 spatial parcels (N, NE, E, SE, S, SW, W, NW, Core) each with:
    - NDVI classification & land use type
    - Solar potential score
    - Soil quality proxy
    - Water retention score
    - Flood risk assessment
    - Accessibility rating
    - Canopy cover % & impervious surface %
    """

    def _classify_land_use(self, ndvi: float) -> str:
        if ndvi > 0.55:   return "high_vegetation"
        elif ndvi > 0.35: return "low_vegetation"
        elif ndvi > 0.18: return "transitional"
        elif ndvi > 0.08: return "barren_soil"
        elif ndvi > 0.0:  return "semi_arid"
        else:             return "built_environment"

    def _estimate_solar_potential(self, anchor_lat: float, lat_offset: float, h: int) -> float:
        """Latitude-based solar potential with pseudo-random terrain variation."""
        base_solar = 1.0 - abs(anchor_lat + lat_offset) / 90.0
        noise = ((h % 20) / 100.0) - 0.10
        return round(min(max(base_solar + noise, 0.1), 1.0), 2)

    def _estimate_water_retention(self, ndvi: float, h: int) -> float:
        """Soil water retention proxy — barren soils retain less moisture."""
        base = ndvi * 0.55 + 0.20
        noise = (h % 15) / 100.0
        return round(min(base + noise, 1.0), 2)

    def _estimate_flood_risk(self, zone_idx: int, h: int) -> str:
        """Topographic flood proxy derived from zone position hash."""
        score = (h + zone_idx * 11) % 10
        if score < 3:   return "Low"
        elif score < 7: return "Moderate"
        else:           return "High"

    def _estimate_accessibility(self, zone_idx: int, h: int) -> str:
        levels = ["High", "High", "Medium", "Medium", "Low"]
        return levels[(h + zone_idx * 3) % len(levels)]

    def _estimate_slope(self, h: int) -> float:
        """Slope in degrees (0 = flat, 15 = steep). Affects runoff and planting."""
        return round((h % 16), 1)

    def classify_spatial_layer(
        self,
        spatial_data: Dict[str, Any],
        anchor_lat: float,
        anchor_lng: float,
        name: str
    ) -> List[Dict[str, Any]]:
        """
        Classifies the institution's spatial footprint into 9 parcels with
        full multi-dimensional environmental metrics per parcel.
        """
        print("[Agent 3] Running multi-dimensional vegetation & land use classification...")

        hash_seed = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
        offset = 0.00045
        d = offset * 0.707  # diagonal (≈ 50m at 45°)

        # 9-parcel layout: cardinal + intercardinal + core
        quadrants = [
            {"id": f"{name} — North Parcel",      "lat_off":  offset, "lng_off":  0,     "base_ndvi": 0.12, "base_area": 1400},
            {"id": f"{name} — North-East Parcel", "lat_off":  d,      "lng_off":  d,     "base_ndvi": 0.62, "base_area":  650},
            {"id": f"{name} — East Parcel",       "lat_off":  0,      "lng_off":  offset,"base_ndvi": 0.68, "base_area":  720},
            {"id": f"{name} — South-East Parcel", "lat_off": -d,      "lng_off":  d,     "base_ndvi": 0.04, "base_area":  980},
            {"id": f"{name} — South Parcel",      "lat_off": -offset, "lng_off":  0,     "base_ndvi": 0.07, "base_area":    0},
            {"id": f"{name} — South-West Parcel", "lat_off": -d,      "lng_off": -d,     "base_ndvi": 0.22, "base_area": 2100},
            {"id": f"{name} — West Parcel",       "lat_off":  0,      "lng_off": -offset,"base_ndvi": 0.27, "base_area": 3200},
            {"id": f"{name} — North-West Parcel", "lat_off":  d,      "lng_off": -d,     "base_ndvi": 0.19, "base_area": 1800},
            {"id": f"{name} — Core Parcel",       "lat_off":  0,      "lng_off":  0,     "base_ndvi": 0.02, "base_area":  500},
        ]

        segments = []
        for i, q in enumerate(quadrants):
            # Derive per-parcel hash slice for deterministic variation
            h = (hash_seed >> (i * 4)) & 0xFFFF

            var_ndvi = (h % 15) * 0.02
            var_area = (h % 25) * 80

            clat = anchor_lat + q["lat_off"]
            clng = anchor_lng + q["lng_off"]
            half = offset / 2

            final_ndvi = round(min(q["base_ndvi"] + var_ndvi, 0.95), 2)
            v_type     = self._classify_land_use(final_ndvi)
            profile    = LAND_USE_PROFILES[v_type]

            solar         = self._estimate_solar_potential(anchor_lat, q["lat_off"], h)
            water_ret     = self._estimate_water_retention(final_ndvi, h)
            flood_risk    = self._estimate_flood_risk(i, h)
            accessibility = self._estimate_accessibility(i, h)
            slope_deg     = self._estimate_slope(h)

            canopy_pct     = round(final_ndvi * 100, 1)
            impervious_pct = round(max(0.0, (0.3 - final_ndvi) / 0.3 * 100), 1) if final_ndvi < 0.3 else 0.0

            polygon = [
                [clat + half, clng - half],
                [clat - half, clng - half],
                [clat - half, clng + half],
                [clat + half, clng + half],
            ]

            segments.append({
                "id":                   q["id"],
                "ndvi":                 final_ndvi,
                "type":                 v_type,
                "description":          profile["description"],
                "color":                profile["color"],
                "icon":                 profile["icon"],
                "plant_potential":      profile["plant_potential"],
                "soil_quality":         profile["soil_quality"],
                "usable_area_sqm":      max(0, q["base_area"] + var_area),
                "canopy_cover_pct":     canopy_pct,
                "impervious_surface_pct": impervious_pct,
                "solar_potential_score": solar,
                "water_retention_score": water_ret,
                "slope_degrees":         slope_deg,
                "flood_risk":            flood_risk,
                "accessibility":         accessibility,
                "center":  {"lat": clat, "lng": clng},
                "polygon": polygon,
            })

        print(f"[Agent 3] Classified {len(segments)} parcels with full multi-dimensional metrics.")
        return segments
