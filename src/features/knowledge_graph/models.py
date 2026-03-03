"""Pydantic models for the knowledge graph schema.

Defines node types, relationship types, and API response models
for the knowledge graph feature.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ── Entity types ────────────────────────────────────────────────────────


class EntityType(StrEnum):
    """Types of entities extracted from book content."""

    PERSON = "person"
    ORGANIZATION = "organization"
    PLACE = "place"
    CONCEPT = "concept"
    TECHNOLOGY = "technology"
    EVENT = "event"
    THEORY = "theory"


class RelationshipType(StrEnum):
    """Types of relationships between graph nodes."""

    AUTHORED_BY = "AUTHORED_BY"
    HAS_CHAPTER = "HAS_CHAPTER"
    MENTIONS = "MENTIONS"
    DISCUSSES = "DISCUSSES"
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"
    PRECEDES = "PRECEDES"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CROSS_REFERENCED = "CROSS_REFERENCED"
    SUBTOPIC_OF = "SUBTOPIC_OF"


# ── Extraction models (LLM output) ─────────────────────────────────────


class ExtractedEntity(BaseModel):
    """An entity extracted from a book chunk by the LLM."""

    name: str
    type: EntityType
    description: str = ""
    aliases: list[str] = Field(default_factory=list)


class ExtractedRelationship(BaseModel):
    """A relationship between two entities extracted by the LLM."""

    source_entity: str
    target_entity: str
    relationship_type: str
    context: str = ""
    confidence: float = 0.8


class ExtractedTopic(BaseModel):
    """A topic extracted from a book chunk by the LLM."""

    name: str
    description: str = ""
    parent_topic: str | None = None


class ExtractionResult(BaseModel):
    """Result of entity extraction from a single chunk."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    topics: list[ExtractedTopic] = Field(default_factory=list)


# ── Resolved entities ───────────────────────────────────────────────────


class ResolvedEntity(BaseModel):
    """An entity after deduplication and merging."""

    id: str
    name: str
    type: EntityType
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    mention_count: int = 1
    book_ids: list[str] = Field(default_factory=list)


# ── Graph response models (API output) ──────────────────────────────────


class GraphNode(BaseModel):
    """A node in the knowledge graph for API responses."""

    id: str
    label: str
    name: str
    type: str = ""
    properties: dict = Field(default_factory=dict)
    connections_count: int = 0


class GraphEdge(BaseModel):
    """An edge in the knowledge graph for API responses."""

    source: str
    target: str
    relationship: str
    properties: dict = Field(default_factory=dict)


class GraphNeighborhood(BaseModel):
    """A node and its N-hop neighborhood."""

    center_node: GraphNode
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class GraphPath(BaseModel):
    """A path between two nodes."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    length: int = 0


class GraphSearchResult(BaseModel):
    """Search result with relevance score."""

    node: GraphNode
    relevance_score: float = 0.0


class RelatedBook(BaseModel):
    """A book related via shared entities/topics."""

    book_id: str
    title: str
    author: str
    shared_entity_count: int = 0
    shared_topic_count: int = 0


class TopicTree(BaseModel):
    """A topic with its subtopics (hierarchical)."""

    name: str
    description: str = ""
    children: list[TopicTree] = Field(default_factory=list)
    book_count: int = 0


class GraphBuildResult(BaseModel):
    """Result of building a knowledge graph for a book."""

    book_id: str
    entity_count: int = 0
    relationship_count: int = 0
    topic_count: int = 0
    duration_ms: int = 0
    error: str = ""


class CrossRefResult(BaseModel):
    """Result of building cross-references between books."""

    cross_ref_edges: int = 0
    books_processed: int = 0
