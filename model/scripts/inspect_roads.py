
from pathlib import Path
import osmnx as ox
import networkx as nx

graph_path = Path("data/region3_roads.graphml")

if not graph_path.exists():
    raise FileNotFoundError(f"Cannot find {graph_path}")

G = ox.io.load_graphml(graph_path)

print("Graph loaded successfully")
print(f"Nodes: {G.number_of_nodes():,}")
print(f"Edges: {G.number_of_edges():,}")
print(f"Directed: {G.is_directed()}")
print(f"Connected components (weak): "
      f"{nx.number_weakly_connected_components(G):,}")

# Inspect an example edge
u, v, key, data = next(iter(G.edges(keys=True, data=True)))
print("\nExample edge:")
print(f"From node: {u}")
print(f"To node: {v}")
print(f"Length: {data.get('length', 'MISSING')}")
print(f"Highway type: {data.get('highway', 'MISSING')}")
print(f"One-way: {data.get('oneway', 'MISSING')}")
