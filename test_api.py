
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEOAPIFY_API_KEY")

if not api_key:
    raise ValueError("API key not found. Check your .env file.")

response = requests.get(
    "https://api.geoapify.com/v1/geocode/search",
    params={
        "text": "Jose B. Lingad Memorial General Hospital, San Fernando, Pampanga, Philippines",
        "apiKey": api_key,
    },
    timeout=20,
)

print("HTTP status:", response.status_code)

data = response.json()

if response.ok and data.get("features"):
    feature = data["features"][0]
    longitude, latitude = feature["geometry"]["coordinates"]

    print("API key works!")
    print("Matched location:", feature["properties"].get("formatted"))
    print("Latitude:", latitude)
    print("Longitude:", longitude)
else:
    print("Request failed:", data)

