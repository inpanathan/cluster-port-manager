import { request } from "./client";
import type {
  BookDetail,
  BookEmbedRequest,
  BookEmbedResponse,
  BookListResponse,
  BookProcessingStatus,
  BookUpdateRequest,
} from "./types";

export function listBooks(params?: {
  author?: string;
  tag?: string;
  search?: string;
  embedding_status?: string;
  limit?: number;
  offset?: number;
}): Promise<BookListResponse> {
  const query = new URLSearchParams();
  if (params?.author) query.set("author", params.author);
  if (params?.tag) query.set("tag", params.tag);
  if (params?.search) query.set("search", params.search);
  if (params?.embedding_status) query.set("embedding_status", params.embedding_status);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return request<BookListResponse>(`/books${qs ? `?${qs}` : ""}`);
}

export function getBook(id: string): Promise<BookDetail> {
  return request<BookDetail>(`/books/${id}`);
}

export function updateBook(id: string, data: BookUpdateRequest): Promise<BookDetail> {
  return request<BookDetail>(`/books/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function deleteBook(id: string): Promise<void> {
  return request<void>(`/books/${id}`, { method: "DELETE" });
}

export function getBookDownloadUrl(id: string): string {
  return `/api/v1/books/${id}/download`;
}

export function getBookCoverUrl(id: string): string {
  return `/api/v1/books/${id}/cover`;
}

export function embedBook(bookId: string, force?: boolean): Promise<BookEmbedResponse> {
  const body: BookEmbedRequest = force !== undefined ? { force } : {};
  return request<BookEmbedResponse>(`/books/${bookId}/embed`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getBookStatus(bookId: string): Promise<BookProcessingStatus> {
  return request<BookProcessingStatus>(`/books/${bookId}/status`);
}
