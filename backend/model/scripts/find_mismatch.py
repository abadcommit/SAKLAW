
import re
import unicodedata
from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium

# Change these paths
CSV_PATH = "data/census_2024_cleaned.csv"
GEOJSON_PATH = "data/filtered.geojson"
OUTPUT_DIR = Path("data/mismatch_check")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# 1. Load and filter the datasets
census = pd.read_csv(CSV_PATH, dtype=str).fillna("")
geo = gpd.read_file(GEOJSON_PATH)

region3 = geo[
    geo["ADM1_PCODE"].astype(str).str.strip().eq("PH03")
].copy()


# 2. Normalize names for comparison
# This handles case, extra spaces, punctuation, and common
# prefixes such as "Barangay" and "Brgy.".
def normalize(value, barangay=False):
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    value = value.lower().strip()

    if barangay:
        value = re.sub(r"^(barangay|brgy)\.?\s+", "", value)

    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def add_keys(df, province, municipality, barangay):
    result = df.copy()

    result["_province"] = result[province].map(normalize)
    result["_municipality"] = result[municipality].map(normalize)
    result["_barangay"] = result[barangay].map(
        lambda x: normalize(x, barangay=True)
    )

    # Do not consider incomplete administrative names a valid key.
    valid = result[
        ["_province", "_municipality", "_barangay"]
    ].ne("").all(axis=1)

    result["_key"] = ""
    result.loc[valid, "_key"] = (
        result.loc[valid, "_province"] + "|"
        + result.loc[valid, "_municipality"] + "|"
        + result.loc[valid, "_barangay"]
    )

    return result


census = add_keys(
    census, "province", "municipality", "barangay"
)
region3 = add_keys(
    region3, "ADM2_EN", "ADM3_EN", "ADM4_EN"
)


# 3. Detect duplicate composite keys
census_valid = census[census["_key"].ne("")].copy()
geo_valid = region3[region3["_key"].ne("")].copy()

census_key_counts = census_valid["_key"].value_counts()
geo_key_counts = geo_valid["_key"].value_counts()

census_duplicates = census_valid[
    census_valid["_key"].map(census_key_counts).gt(1)
]
geo_duplicates = geo_valid[
    geo_valid["_key"].map(geo_key_counts).gt(1)
]


# 4. Compare all three administrative levels together
census_keys = set(census_valid["_key"])
geo_keys = set(geo_valid["_key"])

region3["match_status"] = "Matched"
region3.loc[
    ~region3["_key"].isin(census_keys), "match_status"
] = "Missing in census"

# Duplicate keys need manual review, even if a match exists.
region3.loc[
    region3["_key"].isin(set(geo_duplicates["_key"])),
    "match_status"
] = "Duplicate GeoJSON key"

region3.loc[
    region3["_key"].isin(set(census_duplicates["_key"])),
    "match_status"
] = "Duplicate census key"


# Census rows without a corresponding GeoJSON key
census_unmatched = census[
    ~census["_key"].isin(geo_keys) | census["_key"].eq("")
].copy()

geo_unmatched = region3[
    region3["match_status"] != "Matched"
].copy()


# 5. Save review tables
geo_unmatched.drop(
    columns=["geometry"], errors="ignore"
).to_csv(
    OUTPUT_DIR / "geojson_unmatched.csv", index=False
)

census_unmatched.drop(
    columns=[
        "_province", "_municipality", "_barangay", "_key"
    ],
    errors="ignore"
).to_csv(
    OUTPUT_DIR / "census_unmatched.csv", index=False
)

census_duplicates.drop(
    columns=["_province", "_municipality", "_barangay", "_key"],
    errors="ignore"
).to_csv(
    OUTPUT_DIR / "census_duplicate_keys.csv", index=False
)

geo_duplicates.drop(
    columns=["geometry", "_province", "_municipality",
             "_barangay", "_key"],
    errors="ignore"
).to_csv(
    OUTPUT_DIR / "geojson_duplicate_keys.csv", index=False
)


# 6. Print the comparison summary
print("\n=== COMPARISON SUMMARY ===")
print("Census rows:", len(census))
print("Region III GeoJSON rows:", len(region3))
print("Matched GeoJSON barangays:",
      (region3["match_status"] == "Matched").sum())
print("Missing in census:",
      (region3["match_status"] == "Missing in census").sum())
print("Duplicate GeoJSON keys:", len(geo_duplicates))
print("Duplicate census rows:", len(census_duplicates))
print("Census rows with no GeoJSON match:", len(census_unmatched))

print("\n=== GEOJSON STATUS COUNTS ===")
print(region3["match_status"].value_counts())

print("\n=== FIRST UNMATCHED GEOJSON RECORDS ===")
print(
    geo_unmatched[
        ["ADM2_EN", "ADM3_EN", "ADM4_EN", "match_status"]
    ].head(30).to_string(index=False)
)

print("\nOutput folder:", OUTPUT_DIR.resolve())