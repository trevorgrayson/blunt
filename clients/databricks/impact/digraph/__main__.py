#!/usr/bin/env python3
"""
Build a dependency graph from a JSON node dict and export a CSV (and optional PNG).

JSON format (example):
{
  "node.name": {
    "metadata": {
      "owner": "...",
      "created_by": "...",
      "updated_by": "...",
      "email": "..."
    },
    "downstream": ["node.b", "node.c"]
  },
  ...
}
"""

import argparse
import json
import csv
import os
from typing import Dict, Any, List, Optional

import networkx as nx

# Only used if you pass --png; kept optional so the script works without it
try:
    import matplotlib.pyplot as plt  # noqa: F401
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False


def build_graph(nodes: Dict[str, Any]) -> nx.DiGraph:
    """Build a DiGraph from the node dict."""
    G = nx.DiGraph()
    for node, payload in nodes.items():
        if not isinstance(payload, dict):
            raise ValueError(f"Node '{node}' must map to an object.")
        meta = payload.get("metadata", {}) or {}
        if not isinstance(meta, dict):
            raise ValueError(f"metadata for '{node}' must be an object.")

        # Normalize metadata values (None if missing)
        owner = meta.get("owner")
        created_by = meta.get("created_by")
        updated_by = meta.get("updated_by")
        email = meta.get("email")

        # Ensure node exists with attributes
        G.add_node(
            node,
            owner=owner,
            created_by=created_by,
            updated_by=updated_by,
            email=email,
        )

        # Add downstream edges
        downstream_list = payload.get("downstream", []) or []
        if not isinstance(downstream_list, list):
            raise ValueError(f"'downstream' for '{node}' must be a list.")
        for downstream in downstream_list:
            # Ensure downstream node exists even if not defined
            if downstream not in G:
                G.add_node(downstream, owner=None, created_by=None, updated_by=None, email=None)
            G.add_edge(node, downstream)
    return G


def dependencies_to_rows(G: nx.DiGraph) -> List[Dict[str, Optional[str]]]:
    """Convert graph edges (and isolated nodes) into CSV rows."""
    rows: List[Dict[str, Optional[str]]] = []
    for u, v in G.edges():
        meta = G.nodes[u]
        rows.append(
            {
                "node": u,
                "downstream": v,
                "owner": meta.get("owner"),
                "created_by": meta.get("created_by"),
                "updated_by": meta.get("updated_by"),
                "email": meta.get("email"),
            }
        )

    # Include isolated nodes (no in/out edges)
    isolated = [n for n in G.nodes if G.out_degree(n) == 0 and G.in_degree(n) == 0]
    for n in isolated:
        meta = G.nodes[n]
        rows.append(
            {
                "node": n,
                "downstream": None,
                "owner": meta.get("owner"),
                "created_by": meta.get("created_by"),
                "updated_by": meta.get("updated_by"),
                "email": meta.get("email"),
            }
        )
    return rows


def write_csv(rows: List[Dict[str, Optional[str]]], csv_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)) or ".", exist_ok=True)
    fieldnames = ["node", "downstream", "owner", "created_by", "updated_by", "email"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def render_png(G: nx.DiGraph, png_path: str) -> None:
    """Render a simple spring-layout PNG of the graph (optional)."""
    if not _HAS_MPL:
        raise RuntimeError("matplotlib is not available. Install it or run without --png.")

    import matplotlib.pyplot as plt  # local import to keep import optional

    os.makedirs(os.path.dirname(os.path.abspath(png_path)) or ".", exist_ok=True)
    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, seed=42, k=None)  # seed for reproducibility
    nx.draw(
        G,
        pos,
        with_labels=False,
        node_size=300,
        arrows=True,
        width=0.8,
        alpha=0.9,
    )
    # Draw small node labels without crowding too much
    node_labels = {n: n for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=6)
    plt.tight_layout()
    plt.savefig(png_path, dpi=200)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export dependency CSV (and optional PNG) from a node JSON.")
    parser.add_argument("json_path", help="Path to the JSON file.")
    parser.add_argument("--csv", dest="csv_path", default="dependencies.csv", help="Output CSV path. Default: dependencies.csv")
    parser.add_argument("--png", dest="png_path", default=None, help="Optional PNG output path to render the graph.")
    args = parser.parse_args()

    # Load JSON
    with open(args.json_path, "r", encoding="utf-8") as f:
        nodes = json.load(f)
    if not isinstance(nodes, dict):
        raise ValueError("Top-level JSON must be an object/dict of nodes.")

    # Build graph and export
    G = build_graph(nodes)
    rows = dependencies_to_rows(G)
    write_csv(rows, args.csv_path)
    print(f"Wrote CSV: {os.path.abspath(args.csv_path)}  (rows: {len(rows)})")

    if args.png_path:
        render_png(G, args.png_path)
        print(f"Wrote PNG: {os.path.abspath(args.png_path)}")


if __name__ == "__main__":
    main()
