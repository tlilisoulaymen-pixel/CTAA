import requests
from typing import Dict

class DataIngestionAgent:
    """
    Agent 1: Data Ingestion
    Interprets institutions as spatial assets by using a precise fallback dictionary or geocoding their names using Photon.
    """
    def __init__(self):
        self.base_url = "https://photon.komoot.io/api/"
        
        # High-fidelity precision dictionary for UCAR institutions
        self.precise_locations = {
            "National Institute of Applied Science and Technology, Tunis": {"lat": 36.843, "lng": 10.196}, # INSAT
            "Carthage High Commercial Studies Institute, Tunis": {"lat": 36.852, "lng": 10.334}, # IHEC
            "Higher School of Communications of Tunis, Tunis": {"lat": 36.892, "lng": 10.187}, # SUPCOM
            "Preparatory Institute for Engineering Studies of Nabeul, Tunisia": {"lat": 36.452, "lng": 10.730}, # IPEIN
            "Faculty of Sciences of Bizerte, Tunisia": {"lat": 37.261, "lng": 9.873}, # FSB
            "National School of Architecture and Urbanism, Tunis": {"lat": 36.871, "lng": 10.334}, # ENAU
            "National Engineering School of Carthage, Tunis": {"lat": 36.855, "lng": 10.231}, # ENICarthage
            "National Engineering School of Bizerte, Tunisia": {"lat": 37.264, "lng": 9.871}, # ENIB
            "Higher Institute of Fine Arts of Tunis, Tunis": {"lat": 36.804, "lng": 10.165}, # ISBAT
            "Higher Institute of Information and Communication Technologies, Tunis": {"lat": 36.702, "lng": 10.421}, # ISTIC
            "University of Carthage, Tunisia": {"lat": 36.857, "lng": 10.323} # Carthage University Admin
        }

    def get_coordinates(self, institution_name: str) -> Dict[str, float]:
        """Gets precise spatial coordinates."""
        print(f"[Agent 1] Geocoding institution: {institution_name}")
        
        # Check dictionary first for 100% accuracy on known campuses
        if institution_name in self.precise_locations:
            loc = self.precise_locations[institution_name]
            print(f"[Agent 1] High-fidelity match found at {loc['lat']}, {loc['lng']}")
            return loc
            
        # Fallback to API
        params = {
            "q": institution_name,
            "limit": 1
        }
        headers = {
            "User-Agent": "UCAR-Environmental-Advisor/1.0 (contact@ucar.edu)"
        }
        response = requests.get(self.base_url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            features = data.get("features", [])
            if features:
                coords = features[0]["geometry"]["coordinates"]
                location = {"lat": coords[1], "lng": coords[0]}
                print(f"[Agent 1] API spatial asset at {location['lat']}, {location['lng']}")
                return location
                
        raise ValueError(f"Geocoding failed for {institution_name}")
