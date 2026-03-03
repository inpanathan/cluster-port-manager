// TypeScript interfaces mirroring src/api/schemas.py

// ---------- Ingestion ----------

export interface IngestionResponse {
  source_id: string;
  status: string;
  chunk_count: number;
  error: string;
}

export interface FolderIngestionResponse {
  folder_source_id: string;
  total_files: number;
  succeeded: number;
  failed: number;
  skipped: number;
  results: IngestionResponse[];
}

export interface UrlIngestionRequest {
  url: string;
  title?: string;
  tags?: string[];
}

export interface TextIngestionRequest {
  content: string;
  title?: string;
  tags?: string[];
}

export interface FolderIngestionRequest {
  folder_path: string;
  tags?: string[];
}

// ---------- Source / Catalog ----------

export interface SourceUpdateRequest {
  title?: string;
  tags?: string[];
  description?: string;
}

export interface SourceDetail {
  id: string;
  title: string;
  source_type: string;
  origin: string;
  file_format: string;
  ingested_at: string;
  last_indexed_at: string | null;
  content_hash: string;
  chunk_count: number;
  total_tokens: number;
  status: string;
  tags: string[];
  description: string;
  error_message: string;
}

export interface SourceSummary {
  id: string;
  title: string;
  source_type: string;
  file_format: string;
  ingested_at: string;
  status: string;
  chunk_count: number;
  tags: string[];
}

export interface SourceListResponse {
  sources: SourceSummary[];
  total: number;
}

// ---------- Chat ----------

export interface ChatRequest {
  message: string;
  session_id?: string;
  source_ids?: string[];
}

export interface Citation {
  source_id: string;
  source_title: string;
  chunk_text: string;
  relevance_score: number;
}

export interface ChatMessage {
  role: string;
  content: string;
  timestamp: string;
  citations: Citation[];
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  citations: Citation[];
}

export interface ChatSession {
  id: string;
  messages: ChatMessage[];
  created_at: string;
  source_filter: string[] | null;
}

export interface ChatSessionSummary {
  id: string;
  created_at: string;
  message_count: number;
}

// ---------- Summarization ----------

export interface SummarizeRequest {
  source_ids?: string[];
  topic?: string;
  mode?: "short" | "detailed";
}

export interface SummarizeResponse {
  summary: string;
  mode: string;
  source_ids: string[];
  source_titles: string[];
}

// ---------- Q&A ----------

export interface QnAGenerateRequest {
  topic?: string;
  source_ids?: string[];
  count?: number;
  difficulty?: string;
}

export interface QAPair {
  question: string;
  answer: string;
  source_title: string;
  difficulty: string;
}

export interface QASet {
  id: string;
  topic: string;
  pairs: QAPair[];
  created_at: string;
  difficulty: string;
}

export interface QnAExportRequest {
  format: "json" | "markdown";
}

// ---------- Interview ----------

export interface InterviewStartRequest {
  topic: string;
  mode?: string;
  difficulty?: string;
  question_count?: number;
  source_ids?: string[];
}

export interface InterviewQuestion {
  index: number;
  question: string;
  user_answer: string;
  feedback: string;
  score: number;
  model_answer: string;
  answered: boolean;
}

export interface InterviewSession {
  id: string;
  topic: string;
  mode: string;
  difficulty: string;
  current_index: number;
  total_questions: number;
  completed: boolean;
  current_question: InterviewQuestion | null;
}

export interface InterviewAnswerRequest {
  answer: string;
}

export interface InterviewAnswerResponse {
  question: InterviewQuestion;
  next_question: InterviewQuestion | null;
  completed: boolean;
}

export interface InterviewSummary {
  id: string;
  topic: string;
  completed: boolean;
  overall_score: number;
  overall_feedback: string;
  questions: InterviewQuestion[];
}

// ---------- Books ----------

export interface BookSummary {
  id: string;
  title: string;
  author: string;
  file_format: string;
  publication_year: number | null;
  cover_image_path: string;
  tags: string[];
  embedding_status: string;
  chunk_count?: number;
}

export interface BookEmbedRequest {
  force?: boolean;
}

export interface BookEmbedResponse {
  book_id: string;
  chunk_count: number;
  total_tokens: number;
  duration_ms: number;
  validation_passed: boolean;
  skipped: boolean;
  error: string;
}

export interface BookProcessingStatus {
  embedding_status: string;
  graph_status: string;
  chunk_count: number | null;
  source_id: string | null;
}

export interface BookDetail {
  id: string;
  title: string;
  author: string;
  isbn: string;
  publisher: string;
  publication_year: number | null;
  language: string;
  page_count: number | null;
  file_format: string;
  file_size_bytes: number;
  cover_image_path: string;
  description: string;
  table_of_contents: string[];
  tags: string[];
  drive_folder_path: string;
  drive_file_id: string;
  created_at: string;
  processed_at: string | null;
  embedding_status: string;
  graph_status: string;
  source_id: string | null;
}

export interface BookListResponse {
  books: BookSummary[];
  total: number;
}

export interface BookUpdateRequest {
  title?: string;
  author?: string;
  tags?: string[];
  description?: string;
}

// ---------- Knowledge Graph ----------

export interface GraphNode {
  id: string;
  label: string;
  name: string;
  type: string;
  properties: Record<string, unknown>;
  connections_count: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
}

export interface GraphSearchResult {
  id: string;
  label: string;
  name: string;
  type: string;
  properties: Record<string, unknown>;
  connections_count: number;
  relevance_score: number;
}

export interface GraphSearchResponse {
  results: GraphSearchResult[];
  total: number;
}

export interface GraphNeighborhoodResponse {
  center_node: GraphNode;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphPathResponse {
  found: boolean;
  nodes: GraphNode[];
  edges: GraphEdge[];
  length: number;
}

export interface BookEntitiesResponse {
  book_id: string;
  entities: GraphNode[];
  total: number;
}

export interface RelatedBook {
  book_id: string;
  title: string;
  author: string;
  shared_entity_count: number;
  shared_topic_count: number;
}

export interface RelatedBooksResponse {
  book_id: string;
  related: RelatedBook[];
}

export interface TopicTreeNode {
  name: string;
  description: string;
  children: TopicTreeNode[];
}

export interface TopicTaxonomyResponse {
  topics: TopicTreeNode[];
}

export interface GraphStatsResponse {
  node_counts: Record<string, number>;
  relationship_counts: Record<string, number>;
  total_nodes: number;
  total_relationships: number;
}
