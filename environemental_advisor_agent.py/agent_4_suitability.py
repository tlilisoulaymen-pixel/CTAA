from typing import List, Dict, Any

# ─────────────────────────────────────────────────────────────
# Mediterranean / North-African native species database
# ─────────────────────────────────────────────────────────────
SPECIES_DATABASE = {
    "arid_pioneer": {
        "names":       ["Acacia tortilis", "Retama raetam", "Atriplex halimus"],
        "common":      ["Umbrella Thorn", "White Weeping Broom", "Mediterranean Saltbush"],
        "description": "Drought-tolerant nitrogen-fixing pioneer species for barren/arid substrates.",
        "water_need":  "Very Low",
        "growth_rate": "Medium",
        "carbon_seq_kg_yr_per_plant": 8,
        "planting_density_per_100sqm": 4,
        "ecosystem_services": ["Soil stabilisation", "Nitrogen fixation", "Windbreak"],
    },
    "native_shrub": {
        "names":       ["Pistacia lentiscus", "Myrtus communis", "Rhamnus alaternus"],
        "common":      ["Mastic Tree", "Common Myrtle", "Mediterranean Buckthorn"],
        "description": "Mediterranean native shrubs providing high biodiversity, low maintenance.",
        "water_need":  "Low",
        "growth_rate": "Slow",
        "carbon_seq_kg_yr_per_plant": 12,
        "planting_density_per_100sqm": 6,
        "ecosystem_services": ["Pollinator habitat", "Bird corridor", "Erosion control"],
    },
    "shade_tree": {
        "names":       ["Pinus halepensis", "Ceratonia siliqua", "Quercus suber"],
        "common":      ["Aleppo Pine", "Carob Tree", "Cork Oak"],
        "description": "Long-lived canopy trees for urban cooling and maximum carbon capture.",
        "water_need":  "Low–Medium",
        "growth_rate": "Slow–Medium",
        "carbon_seq_kg_yr_per_plant": 35,
        "planting_density_per_100sqm": 1,
        "ecosystem_services": ["Urban cooling", "Carbon sequestration", "Shade canopy"],
    },
    "ground_cover": {
        "names":       ["Rosmarinus officinalis", "Lavandula stoechas", "Thymus capitatus"],
        "common":      ["Rosemary", "French Lavender", "Thyme"],
        "description": "Low-maintenance aromatic ground cover for erosion control and pollinators.",
        "water_need":  "Very Low",
        "growth_rate": "Fast",
        "carbon_seq_kg_yr_per_plant": 4,
        "planting_density_per_100sqm": 15,
        "ecosystem_services": ["Erosion control", "Pollinator support", "Soil health"],
    },
    "transitional_mix": {
        "names":       ["Spartium junceum", "Pistacia atlantica", "Cercis siliquastrum"],
        "common":      ["Spanish Broom", "Atlantic Pistachio", "Judas Tree"],
        "description": "Resilient mixed species for degraded / transitional land rehabilitation.",
        "water_need":  "Low",
        "growth_rate": "Medium",
        "carbon_seq_kg_yr_per_plant": 18,
        "planting_density_per_100sqm": 3,
        "ecosystem_services": ["Habitat creation", "Soil improvement", "Visual screening"],
    },
}

# Cost constants (USD)
PLANTING_COST_PER_SQM  = 9.0    # Labor + materials
MAINTENANCE_COST_ANNUAL = 3.5   # Per sqm/year
CARBON_CREDIT_VALUE_USD = 12.0  # Per tonne CO₂ (voluntary market estimate)


class SuitabilityAnalyzerAgent:
    """
    Agent 4: Multi-Criteria Suitability Analyzer (v2.0)

    Scoring weights (MCDA):
      ndvi_deficit   0.30  – How bare / green-deficient is the zone?
      area_score     0.25  – Size / unfragmented land available
      solar_potential 0.20 – Solar exposure for plant photosynthesis
      soil_quality   0.15  – Pedological suitability
      water_retention 0.10 – Moisture holding capacity
    """

    def __init__(self):
        self.min_usable_area      = 400   # sqm
        self.max_ndvi_threshold   = 0.35
        self.exclude_types        = {"built_environment", "high_vegetation"}
        self.weights = {
            "ndvi_deficit":    0.30,
            "area_score":      0.25,
            "solar_potential": 0.20,
            "soil_quality":    0.15,
            "water_retention": 0.10,
        }

    # ── Species selection ────────────────────────────────────────
    def _select_species(self, seg: Dict[str, Any]) -> Dict[str, Any]:
        ndvi  = seg["ndvi"]
        soil  = seg["soil_quality"]
        solar = seg["solar_potential_score"]
        water = seg["water_retention_score"]

        if ndvi < 0.08 and soil < 0.25:            key = "arid_pioneer"
        elif ndvi < 0.18 and solar > 0.68:         key = "shade_tree"
        elif ndvi < 0.22:                          key = "native_shrub"
        elif ndvi < 0.35 and water > 0.45:         key = "transitional_mix"
        else:                                      key = "ground_cover"

        return {"type": key, **SPECIES_DATABASE[key]}

    # ── Ecological & financial projections ──────────────────────
    def _project_carbon(self, area_sqm: float, species: Dict) -> float:
        density     = species["planting_density_per_100sqm"] / 100.0
        n_plants    = area_sqm * density
        return round(n_plants * species["carbon_seq_kg_yr_per_plant"], 1)

    def _project_cost(self, area_sqm: float, carbon_kg_yr: float) -> Dict[str, float]:
        initial   = round(area_sqm * PLANTING_COST_PER_SQM, 0)
        annual    = round(area_sqm * MAINTENANCE_COST_ANNUAL, 0)
        credit    = round((carbon_kg_yr / 1000.0) * CARBON_CREDIT_VALUE_USD, 2)
        payback   = round(initial / max(credit + annual * 0.1, 1), 1)
        return {
            "initial_planting_usd":       initial,
            "annual_maintenance_usd":     annual,
            "annual_carbon_credit_usd":   credit,
            "estimated_payback_years":    payback,
        }

    # ── MCDA composite score ─────────────────────────────────────
    def _composite_score(self, seg: Dict[str, Any]) -> float:
        ndvi_deficit = 1.0 - seg["ndvi"]
        area_score   = min(seg["usable_area_sqm"] / 5000.0, 1.0)
        solar        = seg["solar_potential_score"]
        soil         = seg["soil_quality"]
        water        = seg["water_retention_score"]

        # Slope penalty: slopes > 10° reduce score slightly
        slope_penalty = max(0.0, (seg.get("slope_degrees", 0) - 10) * 0.01)

        raw = (
            self.weights["ndvi_deficit"]    * ndvi_deficit  +
            self.weights["area_score"]      * area_score    +
            self.weights["solar_potential"] * solar         +
            self.weights["soil_quality"]    * soil          +
            self.weights["water_retention"] * water
        )
        return round(max(raw - slope_penalty, 0.0), 3)

    def _priority_tier(self, score: float) -> Dict[str, str]:
        if   score > 0.65: return {"priority": "Critical", "color": "#ef4444", "badge": "🔴"}
        elif score > 0.50: return {"priority": "High",     "color": "#f97316", "badge": "🟠"}
        elif score > 0.35: return {"priority": "Medium",   "color": "#38bdf8", "badge": "🔵"}
        else:              return {"priority": "Low",      "color": "#94a3b8", "badge": "⚪"}

    # ── Main analysis entry point ────────────────────────────────
    def analyze_and_rank(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print("[Agent 4] Applying MCDA spatial analysis & species recommendation engine...")
        candidates = []

        for seg in segments:
            if seg["type"] in self.exclude_types:
                continue
            if seg["usable_area_sqm"] < self.min_usable_area:
                continue
            if seg["ndvi"] > self.max_ndvi_threshold:
                continue

            score      = self._composite_score(seg)
            tier       = self._priority_tier(score)
            species    = self._select_species(seg)
            carbon_kg  = self._project_carbon(seg["usable_area_sqm"], species)
            cost       = self._project_cost(seg["usable_area_sqm"], carbon_kg)

            candidates.append({
                # Identity
                "zone_id":               seg["id"],
                "land_type":             seg["type"],
                "land_description":      seg["description"],
                "icon":                  seg.get("icon", "📍"),

                # Core metrics
                "current_ndvi":          seg["ndvi"],
                "available_area_sqm":    seg["usable_area_sqm"],
                "impact_score":          score,

                # Priority
                **tier,

                # Feasibility
                "feasibility":    "High" if seg["usable_area_sqm"] > 2000 else "Medium",
                "accessibility":  seg["accessibility"],

                # Environmental factors
                "flood_risk":           seg["flood_risk"],
                "solar_potential":       seg["solar_potential_score"],
                "water_retention":       seg["water_retention_score"],
                "soil_quality":          seg["soil_quality"],
                "slope_degrees":         seg.get("slope_degrees", 0),
                "canopy_cover_pct":      seg["canopy_cover_pct"],
                "impervious_surface_pct": seg["impervious_surface_pct"],

                # Species recommendation
                "recommended_species":   species,

                # Ecological & financial projections
                "carbon_sequestration_kg_yr":  carbon_kg,
                "carbon_sequestration_tons_yr": round(carbon_kg / 1000, 3),
                "cost_estimate":               cost,

                # Human-readable justification
                "justification": (
                    f"{seg['description']} detected (NDVI {seg['ndvi']:.2f}) over "
                    f"{seg['usable_area_sqm']:,} sqm. Solar: {seg['solar_potential_score']:.2f}, "
                    f"Flood risk: {seg['flood_risk']}, Slope: {seg.get('slope_degrees', 0):.0f}°."
                ),

                # Geometry
                "center":  seg["center"],
                "polygon": seg["polygon"],
                "color":   seg["color"],
            })

        ranked = sorted(candidates, key=lambda x: x["impact_score"], reverse=True)
        print(f"[Agent 4] Produced {len(ranked)} ranked intervention zones with full ecological profiles.")
        return ranked
