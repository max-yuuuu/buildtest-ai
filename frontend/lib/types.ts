export type ProviderType = "openai" | "anthropic" | "azure" | "zhipu" | "qwen";

export interface Provider {
  id: string;
  user_id: string;
  name: string;
  provider_type: ProviderType;
  base_url: string | null;
  is_active: boolean;
  api_key_mask: string;
  created_at: string;
  updated_at: string;
}

export interface ProviderCreateInput {
  name: string;
  provider_type: ProviderType;
  api_key: string;
  base_url?: string | null;
  is_active?: boolean;
}

export interface ProviderUpdateInput {
  name?: string;
  api_key?: string;
  base_url?: string | null;
  is_active?: boolean;
}

export interface ProviderTestResult {
  ok: boolean;
  latency_ms: number;
  message: string;
  models: string[];
}

export type ModelType = "llm" | "embedding";

export interface Model {
  id: string;
  provider_id: string;
  model_id: string;
  model_type: ModelType;
  context_window: number | null;
  vector_dimension: number | null;
  embedding_batch_size: number | null;
  created_at: string;
}

export interface AvailableModel {
  model_id: string;
  suggested_type: ModelType | null;
  is_registered: boolean;
}

export interface EmbeddingDimensionProbeResult {
  model_id: string;
  vector_dimension: number;
}

export interface ModelCreateInput {
  model_id: string;
  model_type: ModelType;
  context_window?: number | null;
  vector_dimension?: number | null;
  embedding_batch_size?: number | null;
}

export interface ModelUpdateInput {
  model_type?: ModelType;
  context_window?: number | null;
  vector_dimension?: number | null;
  embedding_batch_size?: number | null;
}

export type VectorDbType =
  | "postgres_pgvector"
  | "qdrant"
  | "milvus"
  | "weaviate"
  | "pinecone"
  | "chroma";

export interface VectorDbConfig {
  id: string;
  user_id: string;
  name: string;
  db_type: VectorDbType;
  connection_string_mask: string;
  api_key_mask: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface VectorDbCreateInput {
  name: string;
  db_type: VectorDbType;
  connection_string: string;
  api_key?: string | null;
  is_active?: boolean;
}

export interface VectorDbUpdateInput {
  name?: string;
  connection_string?: string;
  api_key?: string | null;
  is_active?: boolean;
}

export interface VectorDbTestResult {
  ok: boolean;
  latency_ms: number;
  message: string;
}

export interface KnowledgeBase {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  vector_db_config_id: string;
  collection_name: string;
  embedding_model_id: string;
  embedding_dimension: number;
  chunk_size: number;
  chunk_overlap: number;
  retrieval_top_k: number;
  retrieval_similarity_threshold: number;
  retrieval_config: Record<string, unknown>;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseCreateInput {
  name: string;
  description?: string | null;
  vector_db_config_id: string;
  embedding_model_id: string;
  chunk_size?: number;
  chunk_overlap?: number;
  retrieval_top_k?: number;
  retrieval_similarity_threshold?: number;
}

export interface KnowledgeBaseUpdateInput {
  name?: string;
  description?: string | null;
  embedding_model_id?: string;
  chunk_size?: number;
  chunk_overlap?: number;
  retrieval_top_k?: number;
  retrieval_similarity_threshold?: number;
}

export interface KbDocument {
  id: string;
  knowledge_base_id: string;
  file_name: string;
  file_type: string | null;
  file_size: number | null;
  status: string;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  ingestion_job_id?: string | null;
  ingestion_job_status?: string | null;
  ingestion_attempt_count?: number | null;
}

export interface RetrieveInput {
  query: string;
  top_k?: number;
  similarity_threshold?: number;
}

export interface RetrieveHit {
  document_id: string;
  chunk_index: number;
  text: string;
  score: number;
  knowledge_base_id?: string;
  source?: Record<string, unknown> | null;
}

export interface RetrieveResponse {
  hits: RetrieveHit[];
  strategy_id?: string;
  retrieval_params?: Record<string, unknown>;
}

export interface DocumentChunkItem {
  id: string;
  chunk_index: number;
  char_length: number;
  token_length: number | null;
  preview_text: string | null;
  source: Record<string, unknown>;
  created_at: string;
}

export interface DocumentChunksResponse {
  document: {
    id: string;
    knowledge_base_id: string;
    name: string;
    status: string;
    ingestion_job_id: string | null;
    completed_at: string | null;
  };
  chunk_summary: {
    total_chunks: number;
    avg_char_length: number | null;
    min_char_length: number | null;
    max_char_length: number | null;
  };
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  items: DocumentChunkItem[];
}
