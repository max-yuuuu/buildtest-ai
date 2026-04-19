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
  created_at: string;
}

export interface AvailableModel {
  model_id: string;
  suggested_type: ModelType | null;
  is_registered: boolean;
}

export interface ModelCreateInput {
  model_id: string;
  model_type: ModelType;
  context_window?: number | null;
  vector_dimension?: number | null;
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
