import os
import sys
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import run_spatial_decision_pipeline

app = Flask(__name__)
CORS(app)  # Enable CORS for the dashboard fetch

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    if not data or "institution_name" not in data:
        return jsonify({"success": False, "error": "Missing 'institution_name'"}), 400
    
    inst_name = data["institution_name"]
    try:
        result = run_spatial_decision_pipeline(inst_name)
        if result is None:
            return jsonify({"success": False, "error": "Pipeline returned no result"}), 500
            
        # Try to parse the result if it's a string
        if isinstance(result, str):
            import json
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass

        return jsonify({
            "success": True,
            "data": result
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
