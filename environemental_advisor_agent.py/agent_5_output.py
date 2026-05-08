import json
import datetime
from typing import List, Dict, Any


class OutputGeneratorAgent:
    """
    Agent 5: Output Generator (v2.0)

    Produces a comprehensive JSON payload containing:
    - Executive summary with aggregated ecological KPIs
    - A full GeoJSON FeatureCollection layer for frontend map rendering
    - Per-zone ecological profiles with species, cost, and carbon projections
    - Metadata and pipeline provenance
    """

    def generate_report(
        self,
        institution: str,
        coordinates: Dict[str, float],
        ranked_zones: List[Dict[str, Any]]
    ) -> str:
        print("[Agent 5] Generating full spatial decision & ecological impact report...")

        # ── Aggregate KPIs ───────────────────────────────────────────────────
        total_area      = sum(z["available_area_sqm"] for z in ranked_zones)
        total_carbon_kg = sum(z["carbon_sequestration_kg_yr"] for z in ranked_zones)
        total_cost      = sum(z["cost_estimate"]["initial_planting_usd"] for z in ranked_zones)
        total_annual    = sum(z["cost_estimate"]["annual_maintenance_usd"] for z in ranked_zones)
        total_credit    = sum(z["cost_estimate"]["annual_carbon_credit_usd"] for z in ranked_zones)

        by_priority = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for z in ranked_zones:
            by_priority[z["priority"]] = by_priority.get(z["priority"], 0) + 1

        # Dominant species across all zones
        species_votes: Dict[str, int] = {}
        for z in ranked_zones:
            k = z["recommended_species"]["type"]
            species_votes[k] = species_votes.get(k, 0) + 1
        dominant_species_type = max(species_votes, key=species_votes.get) if species_votes else "N/A"

        # ── GeoJSON FeatureCollection ────────────────────────────────────────
        features = []
        for z in ranked_zones:
            if not z.get("polygon"):
                continue
            # GeoJSON uses [lng, lat] order
            ring = [[c[1], c[0]] for c in z["polygon"]]
            ring.append(ring[0])   # close polygon

            features.append({
                "type": "Feature",
                "properties": {
                    "zone_id":         z["zone_id"],
                    "impact_score":    z["impact_score"],
                    "priority":        z["priority"],
                    "priority_color":  z["color"],
                    "land_type":       z["land_type"],
                    "area_sqm":        z["available_area_sqm"],
                    "ndvi":            z["current_ndvi"],
                    "carbon_kg_yr":    z["carbon_sequestration_kg_yr"],
                    "species":         z["recommended_species"]["names"],
                    "flood_risk":      z["flood_risk"],
                    "solar":           z["solar_potential"],
                    "accessibility":   z["accessibility"],
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [ring]
                }
            })

        # ── Full report payload ──────────────────────────────────────────────
        report = {
            "metadata": {
                "system":            "UCAR Environmental & Land Suitability Advisor",
                "version":           "2.0.0",
                "institution_target": institution,
                "anchor_coordinates": coordinates,
                "timestamp":         datetime.datetime.now().isoformat(),
                "total_parcels_analysed": len(ranked_zones) + 2,  # +2 for excluded
                "pipeline_stages":   5,
            },
            "executive_summary": {
                "total_viable_zones":                   len(ranked_zones),
                "zones_by_priority":                    by_priority,
                "total_plantable_area_sqm":             total_area,
                "total_plantable_area_hectares":        round(total_area / 10000, 4),
                "estimated_co2_sequestration_kg_yr":    total_carbon_kg,
                "estimated_co2_sequestration_tons_yr":  round(total_carbon_kg / 1000, 2),
                "estimated_initial_investment_usd":     total_cost,
                "estimated_annual_maintenance_usd":     total_annual,
                "estimated_annual_carbon_credits_usd":  round(total_credit, 2),
                "dominant_recommended_species_type":    dominant_species_type,
                "top_priority_zone":                    ranked_zones[0]["zone_id"] if ranked_zones else "N/A",
            },
            "geojson_layer": {
                "type":     "FeatureCollection",
                "features": features,
            },
            "prioritized_intervention_zones": ranked_zones,
        }

        return json.dumps(report, indent=4)
