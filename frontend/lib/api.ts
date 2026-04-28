import type {
  AvailableModel,
  BatchUploadResponse,
  KnowledgeBase,
  KnowledgeBaseCreateInput,
  KnowledgeBaseUpdateInput,
  KbDocument,
  Model,
  ModelCreateInput,
  EmbeddingDimensionProbeResult,
  ModelUpdateInput,
  Provider,
  ProviderCreateInput,
  ProviderTestResult,
  ProviderUpdateInput,
  RetrieveInput,
  RetrieveResponse,
  DocumentChunksResponse,
  VectorDbConfig,
  VectorDbCreateInput,
  VectorDbTestResult,
  VectorDbUpdateInput,
  NotificationListResponse,
} from "./types";

const BASE = "/api/backend";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (body.detail?.message) {
        detail = body.detail.message;
      } else {
        detail = body.error ?? detail;
      }
    } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const providerApi = {
  list: () => request<Provider[]>("/providers"),
  get: (id: string) => request<Provider>(`/providers/${id}`),
  create: (data: ProviderCreateInput) =>
    request<Provider>("/providers", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: string, data: ProviderUpdateInput) =>
    request<Provider>(`/providers/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/providers/${id}`, { method: "DELETE" }),
  test: (id: string) =>
    request<ProviderTestResult>(`/providers/${id}/test`, { method: "POST" }),
};

export const modelApi = {
  list: (providerId: string) =>
    request<Model[]>(`/providers/${providerId}/models`),
  listAvailable: (providerId: string) =>
    request<AvailableModel[]>(`/providers/${providerId}/models/available`),
  create: (providerId: string, data: ModelCreateInput) =>
    request<Model>(`/providers/${providerId}/models`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (providerId: string, modelPk: string, data: ModelUpdateInput) =>
    request<Model>(`/providers/${providerId}/models/${modelPk}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  delete: (providerId: string, modelPk: string) =>
    request<void>(`/providers/${providerId}/models/${modelPk}`, {
      method: "DELETE",
    }),
  probeEmbeddingDimension: (providerId: string, modelId: string) =>
    request<EmbeddingDimensionProbeResult>(`/providers/${providerId}/models/dimension-probe`, {
      method: "POST",
      body: JSON.stringify({ model_id: modelId }),
    }),
};

export const vectorDbApi = {
  list: () => request<VectorDbConfig[]>("/vector-dbs"),
  get: (id: string) => request<VectorDbConfig>(`/vector-dbs/${id}`),
  create: (data: VectorDbCreateInput) =>
    request<VectorDbConfig>("/vector-dbs", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: string, data: VectorDbUpdateInput) =>
    request<VectorDbConfig>(`/vector-dbs/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/vector-dbs/${id}`, { method: "DELETE" }),
  test: (id: string) =>
    request<VectorDbTestResult>(`/vector-dbs/${id}/test`, { method: "POST" }),
};

export const knowledgeBaseApi = {
  list: () => request<KnowledgeBase[]>("/knowledge-bases"),
  get: (id: string) => request<KnowledgeBase>(`/knowledge-bases/${id}`),
  create: (data: KnowledgeBaseCreateInput) =>
    request<KnowledgeBase>("/knowledge-bases", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: string, data: KnowledgeBaseUpdateInput) =>
    request<KnowledgeBase>(`/knowledge-bases/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/knowledge-bases/${id}`, { method: "DELETE" }),
  listDocuments: (kbId: string) =>
    request<KbDocument[]>(`/knowledge-bases/${kbId}/documents`),
  uploadDocument: async (kbId: string, file: File): Promise<KbDocument> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${BASE}/knowledge-bases/${kbId}/documents`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail ?? detail;
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return res.json() as Promise<KbDocument>;
  },
  uploadDocuments: async (
    kbId: string,
    files: File[],
  ): Promise<BatchUploadResponse> => {
    if (files.length === 1) {
      const doc = await knowledgeBaseApi.uploadDocument(kbId, files[0]);
      return {
        created_count: 1,
        documents: [doc],
      };
    }
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const res = await fetch(`${BASE}/knowledge-bases/${kbId}/documents/batch`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail ?? detail;
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return res.json() as Promise<BatchUploadResponse>;
  },
  retrieve: (kbId: string, data: RetrieveInput) =>
    request<RetrieveResponse>(`/knowledge-bases/${kbId}/retrieve`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  rebuild: (kbId: string, documentId?: string) =>
    request<void>(`/knowledge-bases/${kbId}/rebuild`, {
      method: "POST",
      body: JSON.stringify(documentId ? { document_id: documentId } : {}),
    }),
  deleteDocument: (kbId: string, docId: string) =>
    request<void>(`/knowledge-bases/${kbId}/documents/${docId}`, {
      method: "DELETE",
    }),
  retryDocumentIngestion: (kbId: string, docId: string) =>
    request<void>(`/knowledge-bases/${kbId}/documents/${docId}/ingestion-job/retry`, {
      method: "POST",
    }),
  getDocumentChunks: (kbId: string, docId: string, page = 1, pageSize = 10) =>
    request<DocumentChunksResponse>(
      `/knowledge-bases/${kbId}/documents/${docId}/chunks?page=${page}&page_size=${pageSize}`,
    ),
};

export const notificationApi = {
  list: (page = 1, pageSize = 20, unreadOnly = false) =>
    request<NotificationListResponse>(
      `/notifications?page=${page}&page_size=${pageSize}&unread_only=${unreadOnly}`,
    ),
  unreadCount: () => request<{ unread_count: number }>("/notifications/unread-count"),
  markRead: (notificationIds: string[]) =>
    request<{ updated: number }>("/notifications/mark-read", {
      method: "POST",
      body: JSON.stringify({ notification_ids: notificationIds }),
    }),
};
