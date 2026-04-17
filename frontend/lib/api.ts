import type {
  Provider,
  ProviderCreateInput,
  ProviderUpdateInput,
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
      detail = body.detail ?? body.error ?? detail;
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
};
