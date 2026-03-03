import { request } from "./client";
import type {
  BookEntitiesResponse,
  GraphNeighborhoodResponse,
  GraphPathResponse,
  GraphSearchResponse,
  GraphStatsResponse,
  RelatedBooksResponse,
  TopicTaxonomyResponse,
} from "./types";

export function searchGraph(params: {
  q: string;
  type?: string;
  limit?: number;
}): Promise<GraphSearchResponse> {
  const query = new URLSearchParams();
  query.set("q", params.q);
  if (params.type) query.set("type", params.type);
  if (params.limit) query.set("limit", String(params.limit));
  return request<GraphSearchResponse>(`/graph/search?${query.toString()}`);
}

export function getEntity(
  entityId: string,
  depth?: number,
): Promise<GraphNeighborhoodResponse> {
  const query = depth ? `?depth=${depth}` : "";
  return request<GraphNeighborhoodResponse>(`/graph/entity/${entityId}${query}`);
}

export function findPath(
  fromId: string,
  toId: string,
  maxDepth?: number,
): Promise<GraphPathResponse> {
  const query = maxDepth ? `?max_depth=${maxDepth}` : "";
  return request<GraphPathResponse>(
    `/graph/entity/${fromId}/path/${toId}${query}`,
  );
}

export function getBookEntities(
  bookId: string,
): Promise<BookEntitiesResponse> {
  return request<BookEntitiesResponse>(`/graph/book/${bookId}/entities`);
}

export function getRelatedBooks(
  bookId: string,
): Promise<RelatedBooksResponse> {
  return request<RelatedBooksResponse>(`/graph/book/${bookId}/related`);
}

export function getTopicTaxonomy(): Promise<TopicTaxonomyResponse> {
  return request<TopicTaxonomyResponse>("/graph/topics");
}

export function getGraphStats(): Promise<GraphStatsResponse> {
  return request<GraphStatsResponse>("/graph/stats");
}
