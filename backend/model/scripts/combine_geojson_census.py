
import json
import pandas as pd
from pathlib import Path

CENSUS_PATH = Path("data/census_2024_cleaned.csv")
GEOJSON_PATH = Path("data/filtered.geojson")
OUTPUT_PATH = Path("data/region3_population.geojson")


def normalize(value):
    """Normalize whitespace and capitalization for matching."""
    return " ".join(str(value).strip().lower().split())


def make_key(province, municipality, barangay):
    return (
        normalize(province),
        normalize(municipality),
        normalize(barangay),
    )


def main():
    # Load census data
    census = pd.read_csv(CENSUS_PATH, dtype=str).fillna("")

    required = {"province", "municipality", "barangay", "population"}
    missing = required - set(census.columns)

    if missing:
        raise ValueError(f"Missing census columns: {sorted(missing)}")

    census["population"] = pd.to_numeric(
        census["population"]
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )

    census["_key"] = census.apply(
        lambda row: make_key(
            row["province"],
            row["municipality"],
            row["barangay"],
        ),
        axis=1,
    )

    # Exclude duplicate keys to avoid ambiguous matches
    duplicate_mask = census["_key"].duplicated(keep=False)
    duplicate_keys = set(census.loc[duplicate_mask, "_key"])

    if duplicate_keys:
        print(f"WARNING: {len(duplicate_keys)} duplicate census keys excluded.")

    census = census[~census["_key"].isin(duplicate_keys)]

    population_lookup = dict(
        zip(census["_key"], census["population"])
    )

    # Load GeoJSON and retain Region III only
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    if geojson.get("type") != "FeatureCollection":
        raise ValueError("Input must be a GeoJSON FeatureCollection.")

    region3_features = [
        feature
        for feature in geojson.get("features", [])
        if (feature.get("properties") or {}).get("ADM1_PCODE") == "PH03"
    ]

    matched = 0
    unmatched = []

    # Add census population to Region III features
    for feature in region3_features:
        properties = feature.get("properties") or {}

        key = make_key(
            properties.get("ADM2_EN", ""),
            properties.get("ADM3_EN", ""),
            properties.get("ADM4_EN", ""),
        )

        population = population_lookup.get(key)

        if population is not None and pd.notna(population):
            properties["population"] = int(population)
            matched += 1
        else:
            properties.pop("population", None)
            unmatched.append((
                properties.get("ADM2_EN", ""),
                properties.get("ADM3_EN", ""),
                properties.get("ADM4_EN", ""),
            ))

        feature["properties"] = properties

    # Replace features with Region III features only
    geojson["features"] = region3_features

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    print("\n=== JOIN SUMMARY ===")
    print(f"Region III features retained: {len(region3_features)}")
    print(f"Features matched: {matched}")
    print(f"Features unmatched: {len(unmatched)}")
    print(f"Output: {OUTPUT_PATH.resolve()}")

    if unmatched:
        print("\nFirst 20 unmatched features:")
        for province, municipality, barangay in unmatched[:20]:
            print(f"{province} | {municipality} | {barangay}")

    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        check = json.load(f)

        features = check["features"]

        print("Total features:", len(features))
        print("Region codes:", sorted(set(
            (feature.get("properties") or {}).get("ADM1_PCODE")
            for feature in features
        )))
if __name__ == "__main__":
    main()
