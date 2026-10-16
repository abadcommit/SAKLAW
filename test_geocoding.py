
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
INPUT_FILE = ROOT / "data" / "v_activefacilities.csv"
OUTPUT_FILE = ROOT / "data" / "geocode_test_first5.csv"

load_dotenv(ROOT / ".env")
API_KEY = os.getenv("GEOAPIFY_API_KEY")

if not API_KEY:
    raise ValueError("GEOAPIFY_API_KEY not found in .env")

df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")

# Filter hospitals
hospitals = df[
    df["Health Facility Type"].str.contains(
        "hospital", case=False, na=False
    )
]

test_df = hospitals.head(5).copy()

print(f"Total hospitals in dataset: {len(hospitals)}")
print(f"Testing first {len(test_df)} hospitals...\n")

results = []

for _, row in test_df.iterrows():
    facility_name = row.get("Facility Name", "")

    address_parts = [
        facility_name,
        row.get("Street Name and #", ""),
        row.get("Building name and #", ""),
        row.get("Barangay Name", ""),
        row.get("City/Municipality Name", ""),
        row.get("Province Name", ""),
        "Central Luzon",
        "Philippines",
    ]

    query = ", ".join(
        str(part).strip()
        for part in address_parts
        if pd.notna(part) and str(part).strip()
    )

    result = {
        "Facility Name": facility_name,
        "Health Facility Type": row.get("Health Facility Type", ""),
        "Province Name": row.get("Province Name", ""),
        "City/Municipality Name": row.get(
            "City/Municipality Name", ""
        ),
        "geocode_query": query,
        "latitude": None,
        "longitude": None,
        "matched_address": None,
        "confidence": None,
        "geocode_status": None,
    }

    try:
        response = requests.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={
                "text": query,
                "filter": "countrycode:ph",
                "apiKey": API_KEY,
            },
            timeout=30,
        )
        response.raise_for_status()

        features = response.json().get("features", [])

        if features:
            feature = features[0]
            coordinates = feature["geometry"]["coordinates"]
            properties = feature.get("properties", {})

            result["longitude"] = coordinates[0]
            result["latitude"] = coordinates[1]
            result["matched_address"] = properties.get("formatted")

            rank = properties.get("rank", {})
            result["confidence"] = rank.get("confidence")

            result["geocode_status"] = (
                "MATCHED"
                if result["confidence"] is not None
                and result["confidence"] > 0
                else "REVIEW"
            )
        else:
            result["geocode_status"] = "NO_RESULT"

    except (requests.RequestException, ValueError, KeyError) as error:
        result["geocode_status"] = "ERROR"
        result["error"] = str(error)

    results.append(result)

    print(f"Facility: {facility_name}")
    print(f"Status: {result['geocode_status']}")
    print(f"Matched address: {result['matched_address']}")
    print(f"Confidence: {result['confidence']}")
    print(
        f"Coordinates: {result['latitude']}, "
        f"{result['longitude']}"
    )
    print("-" * 50)

    time.sleep(0.2)

pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)

print(f"\nResults saved to: {OUTPUT_FILE}")

