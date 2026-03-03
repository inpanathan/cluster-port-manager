"""Entity resolution: deduplicate and merge entities across chunks and books.

Performs exact name matching, alias matching, and optional embedding-based
similarity to merge entities that refer to the same real-world concept.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from src.features.knowledge_graph.models import (
    EntityType,
    ExtractedEntity,
    ResolvedEntity,
)
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.models.embeddings import EmbeddingModel

logger = get_logger(__name__)


class EntityResolver:
    """Resolves and deduplicates entities using name matching and embeddings."""

    def __init__(
        self,
        embedding_model: EmbeddingModel | None = None,
        similarity_threshold: float = 0.92,
    ) -> None:
        self._embedding = embedding_model
        self._similarity_threshold = similarity_threshold

    def resolve(
        self, entities: list[ExtractedEntity], *, book_id: str = ""
    ) -> list[ResolvedEntity]:
        """Resolve entities within a single book.

        1. Group by normalized name (exact match)
        2. Merge aliases into existing groups
        3. Optionally use embedding similarity for remaining matches
        """
        if not entities:
            return []

        # Step 1: Group by normalized name
        groups: dict[str, list[ExtractedEntity]] = {}
        for entity in entities:
            key = _normalize_name(entity.name)
            if not key:
                continue
            groups.setdefault(key, []).append(entity)

        # Step 2: Merge alias matches into existing groups
        groups = self._merge_alias_groups(groups)

        # Step 3: Convert groups to resolved entities
        resolved = [_merge_group(group, book_id=book_id) for group in groups.values()]

        # Step 4: Optionally merge by embedding similarity
        if self._embedding and len(resolved) > 1:
            resolved = self._merge_by_similarity(resolved)

        logger.info(
            "entities_resolved",
            input_count=len(entities),
            output_count=len(resolved),
            book_id=book_id,
        )
        return resolved

    def resolve_across_books(
        self, book_entities: dict[str, list[ResolvedEntity]]
    ) -> list[ResolvedEntity]:
        """Resolve entities across multiple books.

        Args:
            book_entities: Mapping of book_id -> list of resolved entities
        """
        # Flatten all entities with book_id tracking
        all_entities: list[ResolvedEntity] = []
        for book_id, entities in book_entities.items():
            for entity in entities:
                if book_id not in entity.book_ids:
                    entity.book_ids.append(book_id)
                all_entities.append(entity)

        if not all_entities:
            return []

        # Group by normalized name
        groups: dict[str, list[ResolvedEntity]] = {}
        for entity in all_entities:
            key = _normalize_name(entity.name)
            if not key:
                continue
            groups.setdefault(key, []).append(entity)

        # Check aliases across groups
        groups = self._merge_alias_groups_resolved(groups)

        # Merge each group
        merged = [_merge_resolved_group(group) for group in groups.values()]

        logger.info(
            "cross_book_entities_resolved",
            input_count=len(all_entities),
            output_count=len(merged),
            book_count=len(book_entities),
        )
        return merged

    def _merge_alias_groups(
        self, groups: dict[str, list[ExtractedEntity]]
    ) -> dict[str, list[ExtractedEntity]]:
        """Check if any entity name is an alias of another group and merge."""
        alias_map: dict[str, str] = {}
        for key, entities in groups.items():
            for entity in entities:
                for alias in entity.aliases:
                    norm_alias = _normalize_name(alias)
                    if norm_alias and norm_alias != key:
                        alias_map[norm_alias] = key

        # Merge groups whose key appears as an alias of another group
        merged_groups: dict[str, list[ExtractedEntity]] = {}
        for key, entities in groups.items():
            target = alias_map.get(key, key)
            merged_groups.setdefault(target, []).extend(entities)

        return merged_groups

    def _merge_alias_groups_resolved(
        self, groups: dict[str, list[ResolvedEntity]]
    ) -> dict[str, list[ResolvedEntity]]:
        """Check aliases across resolved entity groups."""
        alias_map: dict[str, str] = {}
        for key, entities in groups.items():
            for entity in entities:
                for alias in entity.aliases:
                    norm_alias = _normalize_name(alias)
                    if norm_alias and norm_alias != key:
                        alias_map[norm_alias] = key

        merged_groups: dict[str, list[ResolvedEntity]] = {}
        for key, entities in groups.items():
            target = alias_map.get(key, key)
            merged_groups.setdefault(target, []).extend(entities)

        return merged_groups

    def _merge_by_similarity(self, entities: list[ResolvedEntity]) -> list[ResolvedEntity]:
        """Merge entities of the same type with high embedding similarity."""
        if not self._embedding:
            return entities

        # Group by type for pairwise comparison
        by_type: dict[str, list[ResolvedEntity]] = {}
        for entity in entities:
            by_type.setdefault(entity.type, []).append(entity)

        result: list[ResolvedEntity] = []
        for type_entities in by_type.values():
            if len(type_entities) < 2:
                result.extend(type_entities)
                continue

            # Compute embeddings for entity names
            names = [e.name for e in type_entities]
            try:
                embeddings = self._embedding.embed_texts(names)
            except Exception:
                result.extend(type_entities)
                continue

            # Find pairs to merge
            merged_indices: set[int] = set()
            merge_groups: dict[int, list[int]] = {}

            for i in range(len(type_entities)):
                if i in merged_indices:
                    continue
                merge_groups[i] = [i]
                for j in range(i + 1, len(type_entities)):
                    if j in merged_indices:
                        continue
                    sim = _cosine_similarity(embeddings[i], embeddings[j])
                    if sim >= self._similarity_threshold:
                        merge_groups[i].append(j)
                        merged_indices.add(j)

            for indices in merge_groups.values():
                group = [type_entities[idx] for idx in indices]
                result.append(_merge_resolved_group(group))

        return result


def _normalize_name(name: str) -> str:
    """Normalize an entity name for matching."""
    return name.lower().strip()


def _merge_group(entities: list[ExtractedEntity], *, book_id: str = "") -> ResolvedEntity:
    """Merge a group of extracted entities into a single resolved entity."""
    # Pick the most frequent name form as canonical
    name_counts: dict[str, int] = {}
    for e in entities:
        name_counts[e.name] = name_counts.get(e.name, 0) + 1
    canonical_name = max(name_counts, key=lambda n: name_counts[n])

    # Combine descriptions (take longest)
    descriptions = [e.description for e in entities if e.description]
    best_description = max(descriptions, key=len) if descriptions else ""

    # Union all aliases
    all_aliases: set[str] = set()
    for e in entities:
        all_aliases.update(e.aliases)
        if e.name != canonical_name:
            all_aliases.add(e.name)
    all_aliases.discard(canonical_name)

    # Use the most common type
    type_counts: dict[str, int] = {}
    for e in entities:
        type_counts[e.type] = type_counts.get(e.type, 0) + 1
    entity_type = max(type_counts, key=lambda t: type_counts[t])

    book_ids = [book_id] if book_id else []

    return ResolvedEntity(
        id=str(uuid.uuid4()),
        name=canonical_name,
        type=EntityType(entity_type)
        if entity_type in EntityType.__members__.values()
        else EntityType.CONCEPT,
        description=best_description,
        aliases=sorted(all_aliases),
        mention_count=len(entities),
        book_ids=book_ids,
    )


def _merge_resolved_group(entities: list[ResolvedEntity]) -> ResolvedEntity:
    """Merge a group of already-resolved entities."""
    if len(entities) == 1:
        return entities[0]

    # Pick canonical name by highest mention count
    canonical = max(entities, key=lambda e: e.mention_count)

    all_aliases: set[str] = set()
    all_book_ids: set[str] = set()
    total_mentions = 0
    descriptions = []

    for e in entities:
        all_aliases.update(e.aliases)
        all_book_ids.update(e.book_ids)
        total_mentions += e.mention_count
        if e.description:
            descriptions.append(e.description)
        if e.name != canonical.name:
            all_aliases.add(e.name)

    all_aliases.discard(canonical.name)

    return ResolvedEntity(
        id=canonical.id,
        name=canonical.name,
        type=canonical.type,
        description=max(descriptions, key=len) if descriptions else "",
        aliases=sorted(all_aliases),
        mention_count=total_mentions,
        book_ids=sorted(all_book_ids),
    )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))
