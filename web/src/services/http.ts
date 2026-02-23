import type { ApiEnvelope } from "../types/api";

type QueryValue = string | number | boolean | undefined | null;

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  query?: Record<string, QueryValue>;
};

type LooseEnvelope = {
  ok?: unknown;
  data?: unknown;
  error?: {
    code?: unknown;
    message?: unknown;
  } | null;
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

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeEnvelope<T>(
  payload: unknown,
  response: Response,
  apiPath: string,
): ApiEnvelope<T> {
  if (isObject(payload)) {
    const maybe = payload as LooseEnvelope;
    if (typeof maybe.ok === "boolean") {
      if (maybe.ok) {
        if (!response.ok) {
          return {
            ok: false,
            data: null,
            error: {
              code: `HTTP_${response.status}`,
              message: `Request to ${apiPath} failed with HTTP ${response.status}.`,
            },
          };
        }
        return {
          ok: true,
          data: (maybe.data as T) ?? null,
          error: null,
        };
      }

      const errorCode = String(maybe.error?.code ?? `HTTP_${response.status}`);
      const errorMessage = String(
        maybe.error?.message ??
          `Request to ${apiPath} failed with HTTP ${response.status}.`,
      );
      return {
        ok: false,
        data: null,
        error: {
          code: errorCode,
          message: errorMessage,
        },
      };
    }
  }

  if (response.ok) {
    return {
      ok: false,
      data: null,
      error: {
        code: "BAD_RESPONSE",
        message: "Server returned non-envelope JSON response.",
      },
    };
  }

  return {
    ok: false,
    data: null,
    error: {
      code: `HTTP_${response.status}`,
      message: `Request to ${apiPath} failed with HTTP ${response.status}.`,
    },
  };
}

export async function requestApi<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiEnvelope<T>> {
  const query = buildQuery(options.query);
  const apiPath = `/api${path}${query}`;

  let response: Response;
  try {
    response = await fetch(apiPath, buildInit(options));
  } catch {
    return {
      ok: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Request to ${apiPath} failed. Check API service availability.`,
      },
    };
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return {
      ok: false,
      data: null,
      error: {
        code: response.ok ? "BAD_RESPONSE" : `HTTP_${response.status}`,
        message: response.ok
          ? "Server returned non-JSON response."
          : `Request to ${apiPath} failed with HTTP ${response.status}.`,
      },
    };
  }

  return normalizeEnvelope<T>(payload, response, apiPath);
}
