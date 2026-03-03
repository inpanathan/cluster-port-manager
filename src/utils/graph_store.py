"""Graph store abstraction over Neo4j.

Provides a protocol-based interface with Neo4j and mock implementations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GraphStats:
    """Aggregate statistics for the knowledge graph."""

    node_counts: dict[str, int] = field(default_factory=dict)
    relationship_counts: dict[str, int] = field(default_factory=dict)
    total_nodes: int = 0
    total_relationships: int = 0


@runtime_checkable
class GraphStore(Protocol):
    """Protocol for knowledge graph storage backends."""

    def create_node(self, label: str, properties: dict) -> str:
        """Create a node with a label and properties. Returns node ID."""
        ...

    def create_relationship(
        self, from_id: str, to_id: str, rel_type: str, properties: dict | None = None
    ) -> None:
        """Create a relationship between two nodes."""
        ...

    def find_node(self, label: str, properties: dict) -> dict | None:
        """Find a node by label and matching properties."""
        ...

    def merge_node(self, label: str, match_keys: dict, properties: dict) -> str:
        """Upsert a node — create if not exists, update if exists. Returns node ID."""
        ...

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Execute a raw Cypher query and return results."""
        ...

    def delete_book_graph(self, book_id: str) -> int:
        """Delete all nodes and relationships for a book. Returns count deleted."""
        ...

    def get_stats(self) -> GraphStats:
        """Get node/relationship counts by type."""
        ...

    def close(self) -> None:
        """Close the connection."""
        ...


class Neo4jGraphStore:
    """Neo4j-backed graph store using the official Python driver."""

    def __init__(self, url: str, user: str, password: str, database: str) -> None:
        try:
            import neo4j as neo4j_driver

            self._driver = neo4j_driver.GraphDatabase.driver(url, auth=(user, password))
            self._database = database
            self._driver.verify_connectivity()
            self._ensure_schema()
            logger.info("neo4j_graph_store_initialized", url=url, database=database)
        except ImportError as e:
            raise AppError(
                code=ErrorCode.NEO4J_CONNECTION_FAILED,
                message="neo4j driver not installed — run: uv sync --extra graph",
                cause=e,
            ) from e
        except Exception as e:
            raise AppError(
                code=ErrorCode.NEO4J_CONNECTION_FAILED,
                message=f"Failed to connect to Neo4j: {e}",
                cause=e,
            ) from e

    def _ensure_schema(self) -> None:
        """Create constraints and indexes if they don't exist."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Book) REQUIRE b.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Chapter) ON (c.book_id)",
        ]
        with self._driver.session(database=self._database) as session:
            for stmt in constraints + indexes:
                session.run(stmt)
        logger.info("neo4j_schema_ensured")

    def create_node(self, label: str, properties: dict) -> str:
        node_id = properties.get("id", str(uuid.uuid4()))
        properties["id"] = node_id
        cypher = f"CREATE (n:{label} $props) RETURN n.id AS id"  # noqa: S608
        with self._driver.session(database=self._database) as session:
            try:
                result = session.run(cypher, props=properties)
                record = result.single()
                return str(record["id"]) if record else node_id
            except Exception as e:
                raise AppError(
                    code=ErrorCode.GRAPH_QUERY_FAILED,
                    message=f"Failed to create {label} node: {e}",
                    cause=e,
                ) from e

    def create_relationship(
        self, from_id: str, to_id: str, rel_type: str, properties: dict | None = None
    ) -> None:
        props = properties or {}
        cypher = (
            "MATCH (a {id: $from_id}), (b {id: $to_id}) "
            f"CREATE (a)-[r:{rel_type} $props]->(b)"  # noqa: S608
        )
        with self._driver.session(database=self._database) as session:
            try:
                session.run(cypher, from_id=from_id, to_id=to_id, props=props)
            except Exception as e:
                raise AppError(
                    code=ErrorCode.GRAPH_QUERY_FAILED,
                    message=f"Failed to create relationship {rel_type}: {e}",
                    cause=e,
                ) from e

    def find_node(self, label: str, properties: dict) -> dict | None:
        conditions = " AND ".join(f"n.{k} = ${k}" for k in properties)
        cypher = f"MATCH (n:{label}) WHERE {conditions} RETURN n"  # noqa: S608
        with self._driver.session(database=self._database) as session:
            try:
                result = session.run(cypher, **properties)
                record = result.single()
                return dict(record["n"]) if record else None
            except Exception as e:
                raise AppError(
                    code=ErrorCode.GRAPH_QUERY_FAILED,
                    message=f"Failed to find {label} node: {e}",
                    cause=e,
                ) from e

    def merge_node(self, label: str, match_keys: dict, properties: dict) -> str:
        node_id = properties.get("id") or match_keys.get("id") or str(uuid.uuid4())
        all_props = {**match_keys, **properties, "id": node_id}
        on_match = ", ".join(f"n.{k} = ${k}" for k in properties if k != "id")
        cypher = (
            f"MERGE (n:{label} {{{', '.join(f'{k}: ${k}' for k in match_keys)}}})"  # noqa: S608
            f"{f' ON MATCH SET {on_match}' if on_match else ''}"
            f" ON CREATE SET n = $all_props"
            " RETURN n.id AS id"
        )
        with self._driver.session(database=self._database) as session:
            try:
                result = session.run(cypher, **all_props, all_props=all_props)
                record = result.single()
                return record["id"] if record else node_id
            except Exception as e:
                raise AppError(
                    code=ErrorCode.GRAPH_QUERY_FAILED,
                    message=f"Failed to merge {label} node: {e}",
                    cause=e,
                ) from e

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        with self._driver.session(database=self._database) as session:
            try:
                result = session.run(cypher, **(params or {}))
                return [dict(record) for record in result]
            except Exception as e:
                raise AppError(
                    code=ErrorCode.GRAPH_QUERY_FAILED,
                    message=f"Cypher query failed: {e}",
                    cause=e,
                ) from e

    def delete_book_graph(self, book_id: str) -> int:
        cypher = "MATCH (n) WHERE n.book_id = $book_id DETACH DELETE n RETURN count(n) AS cnt"
        with self._driver.session(database=self._database) as session:
            try:
                result = session.run(cypher, book_id=book_id)
                record = result.single()
                count = record["cnt"] if record else 0
                logger.info("book_graph_deleted", book_id=book_id, nodes_deleted=count)
                return count
            except Exception as e:
                raise AppError(
                    code=ErrorCode.GRAPH_QUERY_FAILED,
                    message=f"Failed to delete book graph: {e}",
                    cause=e,
                ) from e

    def get_stats(self) -> GraphStats:
        node_cypher = (
            "MATCH (n) WITH labels(n) AS lbls, count(*) AS cnt RETURN lbls[0] AS label, cnt"
        )
        rel_cypher = "MATCH ()-[r]->() WITH type(r) AS rtype, count(*) AS cnt RETURN rtype, cnt"
        with self._driver.session(database=self._database) as session:
            try:
                node_counts: dict[str, int] = {}
                for record in session.run(node_cypher):
                    node_counts[record["label"]] = record["cnt"]

                rel_counts: dict[str, int] = {}
                for record in session.run(rel_cypher):
                    rel_counts[record["rtype"]] = record["cnt"]

                return GraphStats(
                    node_counts=node_counts,
                    relationship_counts=rel_counts,
                    total_nodes=sum(node_counts.values()),
                    total_relationships=sum(rel_counts.values()),
                )
            except Exception as e:
                raise AppError(
                    code=ErrorCode.GRAPH_QUERY_FAILED,
                    message=f"Failed to get graph stats: {e}",
                    cause=e,
                ) from e

    def close(self) -> None:
        self._driver.close()
        logger.info("neo4j_connection_closed")


class MockGraphStore:
    """In-memory graph store for testing."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict] = {}
        self._node_labels: dict[str, str] = {}
        self._relationships: list[dict] = []
        logger.info("mock_graph_store_initialized")

    def create_node(self, label: str, properties: dict) -> str:
        node_id = str(properties.get("id", str(uuid.uuid4())))
        properties["id"] = node_id
        self._nodes[node_id] = properties
        self._node_labels[node_id] = label
        return node_id

    def create_relationship(
        self, from_id: str, to_id: str, rel_type: str, properties: dict | None = None
    ) -> None:
        self._relationships.append(
            {
                "from_id": from_id,
                "to_id": to_id,
                "type": rel_type,
                "properties": properties or {},
            }
        )

    def find_node(self, label: str, properties: dict) -> dict | None:
        for node_id, node_props in self._nodes.items():
            if self._node_labels.get(node_id) != label:
                continue
            if all(node_props.get(k) == v for k, v in properties.items()):
                return dict(node_props)
        return None

    def merge_node(self, label: str, match_keys: dict, properties: dict) -> str:
        existing = self.find_node(label, match_keys)
        if existing:
            node_id = str(existing["id"])
            self._nodes[node_id].update(properties)
            return node_id
        all_props = {**match_keys, **properties}
        return self.create_node(label, all_props)

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        return []

    def delete_book_graph(self, book_id: str) -> int:
        to_delete = [nid for nid, props in self._nodes.items() if props.get("book_id") == book_id]
        for nid in to_delete:
            del self._nodes[nid]
            self._node_labels.pop(nid, None)
        self._relationships = [
            r
            for r in self._relationships
            if r["from_id"] not in to_delete and r["to_id"] not in to_delete
        ]
        return len(to_delete)

    def get_stats(self) -> GraphStats:
        node_counts: dict[str, int] = {}
        for label in self._node_labels.values():
            node_counts[label] = node_counts.get(label, 0) + 1

        rel_counts: dict[str, int] = {}
        for rel in self._relationships:
            rtype = rel["type"]
            rel_counts[rtype] = rel_counts.get(rtype, 0) + 1

        return GraphStats(
            node_counts=node_counts,
            relationship_counts=rel_counts,
            total_nodes=len(self._nodes),
            total_relationships=len(self._relationships),
        )

    def close(self) -> None:
        self._nodes.clear()
        self._node_labels.clear()
        self._relationships.clear()


def create_graph_store(backend: str, **kwargs: str) -> GraphStore:
    """Factory to create the appropriate graph store.

    Args:
        backend: "mock", "local", or "cloud"
        **kwargs: url, user, password, database for Neo4j backends
    """
    if backend == "mock":
        return MockGraphStore()

    from src.utils.config import settings

    return Neo4jGraphStore(
        url=kwargs.get("url", settings.neo4j.url),
        user=kwargs.get("user", settings.neo4j.user),
        password=kwargs.get("password", settings.neo4j.password),
        database=kwargs.get("database", settings.neo4j.database),
    )
