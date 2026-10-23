
from pathlib import Path
from pyrosm import OSM
import osmnx as ox

# Input and output files
pbf_path = Path("data/raw_data/central_luzon-latest.osm.pbf")
output_path = Path("data/region3_roads.graphml")

if not pbf_path.exists():
    raise FileNotFoundError(f"Cannot find: {pbf_path}")

print("Reading the PBF extract...")
osm = OSM(str(pbf_path))

print("Extracting drivable road network...")
nodes, edges = osm.get_network(
    network_type="driving",
    nodes=True,
)

print(f"Road nodes: {len(nodes):,}")
print(f"Road edges: {len(edges):,}")

print("Building NetworkX graph...")
G = osm.to_graph(nodes, edges, graph_type="networkx")

print(f"Graph nodes: {G.number_of_nodes():,}")
print(f"Graph edges: {G.number_of_edges():,}")

print("Saving graph...")
ox.io.save_graphml(G, output_path)
print(f"Saved to {output_path}")