const DEFAULT_BACKEND_CANDIDATES = [
  "http://localhost:8000",
  "http://backend:8000",
  "http://host.docker.internal:8000",
];

let cachedBackendBaseUrl: string | null = null;

async function isBackendReachable(baseUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl}/healthz`, {
      method: "GET",
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  }
}

function uniqueCandidates(explicitBackendUrl: string | undefined): string[] {
  return [explicitBackendUrl, ...DEFAULT_BACKEND_CANDIDATES].filter(
    (value, index, all): value is string =>
      Boolean(value && value.trim() !== "") && all.indexOf(value) === index,
  );
}

export async function resolveBackendBaseUrl(): Promise<string> {
  if (cachedBackendBaseUrl) return cachedBackendBaseUrl;

  const explicitBackendUrl = process.env.BACKEND_URL?.trim() || undefined;
  const candidates = uniqueCandidates(explicitBackendUrl);

  // Prefer explicit BACKEND_URL when it is configured and reachable.
  if (explicitBackendUrl && (await isBackendReachable(explicitBackendUrl))) {
    cachedBackendBaseUrl = explicitBackendUrl;
    return cachedBackendBaseUrl;
  }

  for (const candidate of candidates) {
    if (candidate === explicitBackendUrl) continue;
    if (await isBackendReachable(candidate)) {
      cachedBackendBaseUrl = candidate;
      return candidate;
    }
  }

  // Keep failures stable and debuggable: if BACKEND_URL is configured but unreachable,
  // still surface that target first instead of silently inventing a different default.
  cachedBackendBaseUrl = explicitBackendUrl ?? DEFAULT_BACKEND_CANDIDATES[0];
  return cachedBackendBaseUrl;
}
