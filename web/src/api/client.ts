/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * Every call goes to /api on the same origin. In development Vite proxies that to
 * uvicorn on :8000, which is where the AWS credentials live -- the browser never
 * holds them.
 */

import type {
  Bootstrap,
  Comparison,
  ArchitectureOption,
  Readiness,
  RunResponse,
  SettingsPayload,
} from './types';

/** An API failure carrying the backend's own message, not a generic one. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { signal?: AbortSignal },
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });
  } catch (cause) {
    // A network-level failure usually means uvicorn is not running.
    throw new ApiError(
      `Cannot reach the demo backend at ${path}. Is the API running on port 8000?`,
      0,
    );
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') {
        detail = body.detail;
      } else if (Array.isArray(body?.detail)) {
        // FastAPI validation errors arrive as a list of issues.
        detail = body.detail
          .map((d: { loc?: unknown[]; msg?: string }) =>
            [d.loc?.slice(1).join('.'), d.msg].filter(Boolean).join(': '),
          )
          .join('; ');
      }
    } catch {
      // Keep the status-line fallback.
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body), signal });
}

export const api = {
  bootstrap: (signal?: AbortSignal) =>
    request<Bootstrap>('/api/bootstrap', { signal }),

  readiness: (settings: SettingsPayload, signal?: AbortSignal) =>
    post<Readiness>('/api/readiness', { settings }, signal),

  run: (modeKey: string, question: string, settings: SettingsPayload) =>
    post<RunResponse>(`/api/run/${modeKey}`, { question, settings }),

  architecture: (settings: SettingsPayload, signal?: AbortSignal) =>
    post<{ options: ArchitectureOption[] }>('/api/architecture', { settings }, signal),

  comparison: (signal?: AbortSignal) =>
    request<Comparison>('/api/comparison', { signal }),
};
