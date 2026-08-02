import json
from pathlib import Path

def get_api_keys():
    """Load API keys from api_keys.json"""
    keys_file = Path(__file__).parent.parent / "api_keys.json"
    with open(keys_file, "r", encoding="utf-8") as f:
        return json.load(f)

PEXELS_KEY = get_api_keys()["pexels_key"]
UNSPLASH_KEY = get_api_keys()["unsplash_key"]
