"""Render the actual nodes and relationships returned by Neo4j for one concept."""
import argparse
from collections import defaultdict
import os
from pathlib import Path
import textwrap

from neo4j import GraphDatabase

from ai_service.graph import cypher


LABELS = ("Source", "SourceVersion", "Chunk", "Claim", "Concept")
COLORS = ("#deedff", "#d6f3ef", "#f4efe1", "#ffe6d9", "#e8dcfa")


def node_text(node, label):
    if label == "Source":
        return node["id"].replace("-", " ")
    if label == "SourceVersion":
        return f'{node["language"].upper()} · {node["version"]}'
    if label == "Chunk":
        return f'PDF p. {node["page"]}' if node.get("page") else f'Text block {node["block_index"]}'
    if label == "Claim":
        return node["value"].replace("-", " ")
    return node["id"].replace("-", " ")


def render(graph, release, concept, output):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    buckets = defaultdict(list)
    for node in graph.nodes:
        label = next(iter(node.labels))
        buckets[label].append(node)
    if not buckets:
        raise ValueError("No nodes for this release and concept")
    fig, ax = plt.subplots(figsize=(14, 4.7), facecolor="#fafbfe")
    ax.set(xlim=(-0.7, 4.7), ylim=(-1.1, 1.35))
    ax.axis("off")
    positions = {}
    edges = list(graph.relationships)
    parents = {}
    for edge in edges:
        if edge.type in {"HAS_VERSION", "HAS_CHUNK"}:
            parents[edge.end_node.element_id] = edge.start_node
        elif edge.type == "SUPPORTED_BY":
            parents[edge.start_node.element_id] = edge.end_node

    def source_order(node):
        current = node
        while current.element_id in parents:
            current = parents[current.element_id]
        return current["id"]

    for column, label in enumerate(LABELS):
        nodes = sorted(buckets[label], key=lambda node: (source_order(node), node_text(node, label)))
        ax.text(column, 1.02, label, ha="center", color="#435169", fontsize=11, weight="bold")
        for index, node in enumerate(nodes):
            y = (0.5 - index / (len(nodes) - 1)) * 1.35 if len(nodes) > 1 else 0
            positions[node.element_id] = (column, y)
            ax.add_patch(FancyBboxPatch((column - .4, y - .21), .8, .42, boxstyle="round,pad=0.025",
                                       facecolor=COLORS[column], edgecolor="#53637b", zorder=3))
            ax.text(column, y, textwrap.fill(node_text(node, label), width=16), ha="center",
                    va="center", color="#19273c", fontsize=9, zorder=4)
    for edge in edges:
        x1, y1 = positions[edge.start_node.element_id]
        x2, y2 = positions[edge.end_node.element_id]
        direction = 1 if x2 > x1 else -1
        ax.add_patch(FancyArrowPatch((x1 + direction * .43, y1), (x2 - direction * .43, y2),
                                     arrowstyle="-|>", shrinkA=0, shrinkB=0, mutation_scale=11,
                                     color="#667993", linewidth=1.5, zorder=2))
    fig.suptitle(f'Knowledge graph · {concept.replace("-", " ")}', fontsize=20, color="#17253a",
                 x=.1, ha="left", y=.98, weight="bold")
    fig.text(.1, .055, f'Neo4j release {release[:12]}  |  {len(graph.nodes)} nodes · {len(graph.relationships)} relationships',
             fontsize=10, color="#435169")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concept", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    release = os.environ["AI_GRAPH_RELEASE_ID"]
    auth = (os.environ.get("AI_GRAPH_USERNAME", "neo4j"), os.environ["AI_GRAPH_PASSWORD"])
    with GraphDatabase.driver(os.environ["AI_GRAPH_URI"], auth=auth) as driver:
        graph = driver.execute_query(cypher("visualize.cypher"), release_id=release, concept_id=args.concept,
                                     database_=os.environ.get("AI_GRAPH_DATABASE", "neo4j"),
                                     routing_="r", result_transformer_=lambda result: result.graph())
    render(graph, release, args.concept, args.output)
    print(f"Rendered {len(graph.nodes)} nodes and {len(graph.relationships)} relationships to {args.output}")


if __name__ == "__main__":
    main()
