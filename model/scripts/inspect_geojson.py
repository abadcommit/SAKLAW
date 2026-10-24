
import pandas as pd
import geopandas as gpd

csv_path = "data/census_2024_cleaned.csv"
geojson_path = "data/filtered.geojson"

census = pd.read_csv(csv_path, dtype=str)
geo = gpd.read_file(geojson_path)

print("CENSUS CSV")
print("Shape:", census.shape)
print("Columns:", census.columns.tolist())
print(census.head(5).to_string(index=False))

print("\nGEOJSON")
print("Shape:", geo.shape)
print("Columns:", geo.columns.tolist())

# Region III only: ADM1_PCODE = PH03
region3_geo = geo[
    geo["ADM1_PCODE"].astype(str).str.strip() == "PH03"
].copy()

print("\nRegion III GeoJSON features:", len(region3_geo))
print("Unique provinces:", region3_geo["ADM2_EN"].nunique())
print("Unique municipalities/cities:", region3_geo["ADM3_PCODE"].nunique())
print("Unique barangay codes:", region3_geo["ADM4_PCODE"].nunique())

print("\nBarangays by province:")
print(region3_geo.groupby("ADM2_EN").size().sort_values(ascending=False))
