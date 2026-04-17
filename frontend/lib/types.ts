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
