
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
from shapely import wkt

graph_path = Path("data/region3_roads.graphml")
boundary_path = Path("data/cleaned_data/region3_population.geojson")

# Load GraphML without OSMnx's strict attribute conversion
G = nx.read_graphml(graph_path, node_type=int)

print(f"Nodes: {G.number_of_nodes():,}")
print(f"Edges: {G.number_of_edges():,}")

# Build a GeoDataFrame from edge geometry
records = []

for u, v, data in G.edges(data=True):
    geom = data.get("geometry")

    if isinstance(geom, str):
        try:
            geom = wkt.loads(geom)
        except Exception:
            geom = None

    if geom is None:
        # Use endpoint coordinates if geometry was not saved
        if u in G.nodes and v in G.nodes:
            a, b = G.nodes[u], G.nodes[v]
            if "x" in a and "y" in a and "x" in b and "y" in b:
                from shapely.geometry import LineString
                geom = LineString([
                    (float(a["x"]), float(a["y"])),
                    (float(b["x"]), float(b["y"])),
                ])

    if geom is not None:
        records.append({"geometry": geom})

edges = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")

# Load and align the Region III boundary
barangays = gpd.read_file(boundary_path)

if barangays.crs is None:
    raise ValueError(
        "The boundary GeoJSON has no declared CRS. "
        "Check its source CRS before assigning one."
    )

barangays = barangays.to_crs(edges.crs)

# Plot
fig, ax = plt.subplots(figsize=(12, 12))

barangays.boundary.plot(ax=ax, color="black", linewidth=0.4)
edges.plot(ax=ax, color="steelblue", linewidth=0.25)

ax.set_title("Road Network — Central Luzon")
ax.set_axis_off()

plt.tight_layout()
plt.savefig("data/region3_road_network.png", dpi=250, bbox_inches="tight")
plt.show()

print("Saved to data/region3_road_network.png")
