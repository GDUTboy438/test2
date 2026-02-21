import type { ApiEnvelope } from "../types/api";

type QueryValue = string | number | boolean | undefined | null;

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  query?: Record<string, QueryValue>;
};

function buildQuery(query: Record<string, QueryValue> | undefined): string {
  if (!query) {
    return "";
  }
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, String(value));
  });
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

function buildInit(options: RequestOptions): RequestInit {
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
    },
  };
  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body);
  }
  return init;
}

export async function requestApi<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiEnvelope<T>> {
  const response = await fetch(`/api${path}${buildQuery(options.query)}`, buildInit(options));
  let payload: ApiEnvelope<T>;
  try {
    payload = (await response.json()) as ApiEnvelope<T>;
  } catch {
    payload = {
      ok: false,
      data: null,
      error: {
        code: "BAD_RESPONSE",
        message: "Server returned non-JSON response.",
      },
    };
  }

  if (!response.ok && payload.ok) {
    return {
      ok: false,
      data: null,
      error: {
        code: "HTTP_ERROR",
        message: `HTTP ${response.status}`,
      },
    };
  }

  return payload;
}
