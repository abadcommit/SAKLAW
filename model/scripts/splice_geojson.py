
import json
import sys
import re

# ---- Edit these two paths ----
INPUT_PATH = "data/barangays.geojson"
OUTPUT_PATH = "data/filtered.geojson"
# ------------------------------

ALLOWED_REGIONS = {
    "Region I (Ilocos Region)",
    "Cordillera Administrative Region (CAR)",
    "Region II (Cagayan Valley)",
    "Region III (Central Luzon)",
    "Region IV-A (Calabarzon)",
    "National Capital Region (NCR)",
}


def remove_nickname(name):
    """
    Remove a parenthetical suffix from a barangay name.

    Examples:
        'Anunas (Anu)' -> 'Anunas'
        'Barangay I (Pob.)' -> 'Barangay I'
        'San Jose (Proper)' -> 'San Jose'

    Names without parentheses remain unchanged.
    """
    if not isinstance(name, str):
        return name

    # Remove a parenthetical suffix, including its preceding whitespace.
    return re.sub(r"\s*\([^()]*\)\s*$", "", name).strip()


def filter_geojson(data, allowed=ALLOWED_REGIONS, key="ADM1_EN"):
    """Filter regions and remove barangay-name nicknames."""
    if data.get("type") != "FeatureCollection":
        raise ValueError("Input must be a GeoJSON FeatureCollection")

    features = []

    for feature in data.get("features", []):
        properties = feature.get("properties") or {}

        if properties.get(key) not in allowed:
            continue

        # Copy the feature and its properties to avoid modifying input data.
        feature = dict(feature)
        properties = dict(properties)

        if "ADM4_EN" in properties:
            properties["ADM4_EN"] = remove_nickname(
                properties["ADM4_EN"]
            )

        feature["properties"] = properties
        features.append(feature)

    result = {k: v for k, v in data.items() if k != "features"}
    result["features"] = features

    # Keep metadata consistent with the filtered output.
    metadata = dict(result.get("metadata") or {})
    if metadata:
        metadata["feature_count"] = len(features)
        metadata.pop("match_summary", None)
        metadata["filtered_by"] = {key: sorted(allowed)}
        metadata["nickname_suffixes_removed"] = True
        result["metadata"] = metadata

    return result


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    filtered = filter_geojson(data)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False)

    total = len(data.get("features", []))
    kept = len(filtered["features"])

    print(
        f"Kept {kept} of {total} features -> {OUTPUT_PATH}",
        file=sys.stderr
    )


if __name__ == "__main__":
    main()
