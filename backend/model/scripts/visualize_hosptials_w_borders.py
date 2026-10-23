
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path

# Load data
hospital_path = Path("data/raw_data/hospitals_geocoded - Finalized.csv")
boundary_path = Path("data/cleaned_data/region3_population.geojson")

df = pd.read_csv(hospital_path)
df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
df = df.dropna(subset=["latitude", "longitude"])

hospitals = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
    crs="EPSG:4326",
)

barangays = gpd.read_file(boundary_path)

if barangays.crs is None:
    raise ValueError("Boundary CRS is missing. Check the source CRS first.")

# Keep Region III only, if this file contains multiple regions
if "ADM1_PCODE" in barangays.columns:
    region3 = barangays[
        barangays["ADM1_PCODE"].astype(str) == "PH03"
    ].copy()
else:
    region3 = barangays.copy()

if region3.empty:
    raise ValueError("No Region III features found. Check ADM1_PCODE.")

region3 = region3.to_crs("EPSG:4326")

# Identify hospitals inside vs. outside the region
region_geometry = region3.geometry.union_all()
hospitals["inside_region3"] = hospitals.geometry.intersects(
    region_geometry
)

inside = hospitals[hospitals["inside_region3"]]
outside = hospitals[~hospitals["inside_region3"]]

# Plot
fig, ax = plt.subplots(figsize=(12, 12))

region3.boundary.plot(
    ax=ax, color="black", linewidth=0.45
)

inside.plot(
    ax=ax, color="steelblue", markersize=20,
    label=f"Inside Region III ({len(inside)})"
)

outside.plot(
    ax=ax, color="crimson", markersize=35,
    marker="x", label=f"Outside Region III ({len(outside)})"
)

ax.set_title("Hospital Locations vs. Region III Boundaries")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.legend()
ax.set_aspect("equal", adjustable="datalim")
ax.grid(alpha=0.2)

plt.tight_layout()
plt.savefig(
    "data/hospitals_vs_region3.png",
    dpi=250,
    bbox_inches="tight"
)
plt.show()

print(f"Total hospitals: {len(hospitals)}")
print(f"Inside Region III: {len(inside)}")
print(f"Outside Region III: {len(outside)}")
print("Map saved to data/hospitals_vs_region3.png")
