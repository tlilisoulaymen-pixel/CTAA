import sys
from pathlib import Path

# Add the directory to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_1_ingestion import DataIngestionAgent
from agent_2_spatial_fetch import SpatialFetchAgent
from agent_3_vegetation import VegetationClassifierAgent
from agent_4_suitability import SuitabilityAnalyzerAgent
from agent_5_output import OutputGeneratorAgent

# ==========================================
# API Configuration
# ==========================================
AGROMONITORING_API_KEY = "9432f1d4e8b7968eebc28d83e9b25226"

# ==========================================
# Main Pipeline Orchestrator
# ==========================================
def run_spatial_decision_pipeline(institution_name: str):
    """
    Orchestrates the multi-agent GIS pipeline for environmental intervention.
    """
    print("="*60)
    print("INITIATING LAND SUITABILITY & INTERVENTION PIPELINE")
    print("="*60)
    
    # Initialize Agents
    agent1 = DataIngestionAgent()
    agent2 = SpatialFetchAgent(AGROMONITORING_API_KEY)
    agent3 = VegetationClassifierAgent()
    agent4 = SuitabilityAnalyzerAgent()
    agent5 = OutputGeneratorAgent()
    
    try:
        # Step 1: Interpret institution as spatial asset
        coords = agent1.get_coordinates(institution_name)
        
        # Step 2: Identify spatial footprint (Buffer & Pull)
        spatial_data = agent2.create_and_fetch_spatial_data(coords["lat"], coords["lng"], institution_name)
        
        # Step 3: Classify vegetation/land use
        segments = agent3.classify_spatial_layer(spatial_data, coords["lat"], coords["lng"], institution_name)
        
        # Step 4: Constrained Suitability Analysis (Where SHOULD green be?)
        ranked_zones = agent4.analyze_and_rank(segments)
        
        # Step 5: Output final decision payload
        final_geojson_decision = agent5.generate_report(institution_name, coords, ranked_zones)
        
        print("\n" + "="*60)
        print("PIPELINE COMPLETE - FINAL SPATIAL DECISION PAYLOAD:")
        print("="*60)
        print(final_geojson_decision)
        print("="*60)
        
        return final_geojson_decision
        
    except Exception as e:
        print(f"\n[PIPELINE FATAL ERROR] {str(e)}")

if __name__ == "__main__":
    # Test execution for a UCAR-affiliated institution
    run_spatial_decision_pipeline("University of Carthage, Tunisia")
