"""Knowledge graph query service.

Provides search, traversal, and analytics over the knowledge graph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.features.knowledge_graph.models import (
    GraphEdge,
    GraphNeighborhood,
    GraphNode,
    GraphPath,
    GraphSearchResult,
    RelatedBook,
    TopicTree,
)
from src.utils.graph_store import GraphStats
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.utils.graph_store import GraphStore

logger = get_logger(__name__)


class KnowledgeGraphService:
    """Query and analyze the knowledge graph."""

    def __init__(self, graph_store: GraphStore) -> None:
        self._store = graph_store

    def search_entities(
        self, query: str, *, entity_type: str | None = None, limit: int = 20
    ) -> list[GraphSearchResult]:
        """Search entities by name (fuzzy match)."""
        type_filter = ""
        params: dict = {"query": query.lower(), "limit": limit}
        if entity_type:
            type_filter = " AND n.type = $entity_type"
            params["entity_type"] = entity_type

        cypher = (
            f"MATCH (n:Entity) WHERE toLower(n.name) CONTAINS $query{type_filter} "
            "OPTIONAL MATCH (n)-[r]-() "
            "WITH n, count(r) AS connections "
            "RETURN n, connections ORDER BY connections DESC LIMIT $limit"
        )
        records = self._store.query(cypher, params)

        results = []
        for record in records:
            node_data = record.get("n", {})
            if hasattr(node_data, "items"):
                node_data = dict(node_data)
            connections = record.get("connections", 0)
            results.append(
                GraphSearchResult(
                    node=GraphNode(
                        id=node_data.get("id", ""),
                        label="Entity",
                        name=node_data.get("name", ""),
                        type=node_data.get("type", ""),
                        properties={
                            k: v for k, v in node_data.items() if k not in ("id", "name", "type")
                        },
                        connections_count=connections,
                    ),
                    relevance_score=1.0,
                )
            )
        return results

    def get_entity(self, entity_id: str, *, depth: int = 1) -> GraphNeighborhood:
        """Get an entity and its N-hop neighborhood."""
        # Get the center node
        center_cypher = "MATCH (n {id: $id}) RETURN n, labels(n)[0] AS label"
        center_records = self._store.query(center_cypher, {"id": entity_id})
        if not center_records:
            return GraphNeighborhood(
                center_node=GraphNode(id=entity_id, label="Unknown", name="Not Found")
            )

        center_data = center_records[0].get("n", {})
        if hasattr(center_data, "items"):
            center_data = dict(center_data)
        center_label = center_records[0].get("label", "Entity")

        center_node = GraphNode(
            id=center_data.get("id", entity_id),
            label=center_label,
            name=center_data.get("name", ""),
            type=center_data.get("type", ""),
            properties={k: v for k, v in center_data.items() if k not in ("id", "name", "type")},
        )

        # Get neighborhood
        neighbor_cypher = (
            f"MATCH (n {{id: $id}})-[r*1..{depth}]-(m) "
            "RETURN DISTINCT m, labels(m)[0] AS label, type(r[0]) AS rel_type"
        )
        neighbor_records = self._store.query(neighbor_cypher, {"id": entity_id})

        nodes = []
        edges = []
        seen_ids: set[str] = {entity_id}

        for record in neighbor_records:
            m_data = record.get("m", {})
            if hasattr(m_data, "items"):
                m_data = dict(m_data)
            m_id = m_data.get("id", "")
            if m_id in seen_ids:
                continue
            seen_ids.add(m_id)

            nodes.append(
                GraphNode(
                    id=m_id,
                    label=record.get("label", ""),
                    name=m_data.get("name", ""),
                    type=m_data.get("type", ""),
                    properties={k: v for k, v in m_data.items() if k not in ("id", "name", "type")},
                )
            )
            edges.append(
                GraphEdge(
                    source=entity_id,
                    target=m_id,
                    relationship=record.get("rel_type", "RELATED_TO"),
                )
            )

        return GraphNeighborhood(center_node=center_node, nodes=nodes, edges=edges)

    def find_path(self, from_id: str, to_id: str, *, max_depth: int = 5) -> GraphPath | None:
        """Find the shortest path between two entities."""
        cypher = (
            "MATCH (a {id: $from_id}), (b {id: $to_id}), "
            f"p = shortestPath((a)-[*..{max_depth}]-(b)) "
            "RETURN p"
        )
        records = self._store.query(cypher, {"from_id": from_id, "to_id": to_id})
        if not records:
            return None

        # Parse path into nodes and edges
        path_data = records[0].get("p")
        if not path_data:
            return None

        nodes = []
        edges = []
        if hasattr(path_data, "nodes"):
            for node in path_data.nodes:
                node_data = dict(node) if hasattr(node, "items") else {}
                nodes.append(
                    GraphNode(
                        id=node_data.get("id", ""),
                        label="Entity",
                        name=node_data.get("name", ""),
                        type=node_data.get("type", ""),
                    )
                )
            for rel in path_data.relationships:
                rel_data = dict(rel) if hasattr(rel, "items") else {}
                edges.append(
                    GraphEdge(
                        source=str(rel.start_node.element_id) if hasattr(rel, "start_node") else "",
                        target=str(rel.end_node.element_id) if hasattr(rel, "end_node") else "",
                        relationship=rel.type if hasattr(rel, "type") else "RELATED_TO",
                        properties=rel_data,
                    )
                )

        return GraphPath(nodes=nodes, edges=edges, length=len(edges))

    def get_book_entities(self, book_id: str) -> list[GraphNode]:
        """Get all entities from a specific book."""
        cypher = (
            "MATCH (n) WHERE n.book_id = $book_id AND (n:Entity OR n:Topic) "
            "OPTIONAL MATCH (n)-[r]-() "
            "WITH n, labels(n)[0] AS label, count(r) AS connections "
            "RETURN n, label, connections ORDER BY connections DESC"
        )
        records = self._store.query(cypher, {"book_id": book_id})

        nodes = []
        for record in records:
            n_data = record.get("n", {})
            if hasattr(n_data, "items"):
                n_data = dict(n_data)
            nodes.append(
                GraphNode(
                    id=n_data.get("id", ""),
                    label=record.get("label", "Entity"),
                    name=n_data.get("name", ""),
                    type=n_data.get("type", ""),
                    properties={k: v for k, v in n_data.items() if k not in ("id", "name", "type")},
                    connections_count=record.get("connections", 0),
                )
            )
        return nodes

    def get_related_books(self, book_id: str) -> list[RelatedBook]:
        """Get books related via cross-reference edges."""
        cypher = (
            "MATCH (a:Book {id: $book_id})-[r:CROSS_REFERENCED]-(b:Book) "
            "RETURN b, r.shared_entity_count AS shared "
            "ORDER BY shared DESC"
        )
        records = self._store.query(cypher, {"book_id": book_id})

        results = []
        for record in records:
            b_data = record.get("b", {})
            if hasattr(b_data, "items"):
                b_data = dict(b_data)
            results.append(
                RelatedBook(
                    book_id=b_data.get("id", ""),
                    title=b_data.get("title", ""),
                    author=b_data.get("author", ""),
                    shared_entity_count=record.get("shared", 0),
                )
            )
        return results

    def get_topic_taxonomy(self) -> list[TopicTree]:
        """Get the hierarchical topic structure."""
        cypher = (
            "MATCH (t:Topic) "
            "OPTIONAL MATCH (t)-[:SUBTOPIC_OF]->(parent:Topic) "
            "RETURN t, parent.name AS parent_name"
        )
        records = self._store.query(cypher)

        topics: dict[str, TopicTree] = {}
        parent_map: dict[str, str] = {}

        for record in records:
            t_data = record.get("t", {})
            if hasattr(t_data, "items"):
                t_data = dict(t_data)
            name = t_data.get("name", "")
            if not name:
                continue
            topics[name] = TopicTree(
                name=name,
                description=t_data.get("description", ""),
            )
            parent_name = record.get("parent_name")
            if parent_name:
                parent_map[name] = parent_name

        # Build tree
        for child_name, parent_name in parent_map.items():
            if parent_name in topics and child_name in topics:
                topics[parent_name].children.append(topics[child_name])

        # Return root topics (those without parents)
        roots = [t for name, t in topics.items() if name not in parent_map]
        return roots

    def get_stats(self) -> GraphStats:
        """Get graph statistics."""
        return self._store.get_stats()
