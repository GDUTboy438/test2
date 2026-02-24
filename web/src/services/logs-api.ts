import type {
  ApiEnvelope,
  ApiLogAnalysisData,
  ApiLogEventsData,
  ApiLogFilesData,
  ApiLogLatestData,
  ApiLogSourcesData,
} from "../types/api";
import type {
  LogAnalysisSummary,
  LogEventItem,
  LogFileItem,
  LogSource,
  LogSourceOption,
  LogsFilterState,
} from "../types/domain";
import { requestApi } from "./http";
import {
  toLogAnalysisSummary,
  toLogEventItem,
  toLogFileItem,
  toLogSourceOption,
} from "./logs-adapters";

type LogQuery = Partial<LogsFilterState> & {
  source: LogSource;
  log_id?: string;
  page?: number;
  page_size?: number;
};

function failedEnvelope<T>(envelope: ApiEnvelope<unknown>): ApiEnvelope<T> {
  return {
    ok: false,
    data: null,
    error: envelope.error,
  };
}

function buildQuery(input: LogQuery) {
  return {
    source: input.source,
    log_id: input.log_id ?? "",
    page: input.page,
    page_size: input.page_size,
    level: input.level ?? "",
    event: input.event ?? "",
    q: input.q ?? "",
    from_ts: input.fromTs ?? undefined,
    to_ts: input.toTs ?? undefined,
  };
}

export async function getLogSources(): Promise<ApiEnvelope<{ items: LogSourceOption[]; defaultSource: LogSource }>> {
  const response = await requestApi<ApiLogSourcesData>("/logs/sources");
  if (!response.ok || !response.data) {
    return failedEnvelope(response);
  }
  return {
    ok: true,
    data: {
      items: (response.data.items ?? []).map(toLogSourceOption),
      defaultSource: response.data.default_source as LogSource,
    },
    error: null,
  };
}

export async function getLogFiles(
  source: LogSource,
  limit = 30,
): Promise<ApiEnvelope<{ source: LogSource; items: LogFileItem[]; total: number }>> {
  const response = await requestApi<ApiLogFilesData>("/logs/files", {
    query: { source, limit },
  });
  if (!response.ok || !response.data) {
    return failedEnvelope(response);
  }
  return {
    ok: true,
    data: {
      source: response.data.source as LogSource,
      items: (response.data.items ?? []).map(toLogFileItem),
      total: Number(response.data.total ?? 0),
    },
    error: null,
  };
}

export async function getLatestLog(source: LogSource): Promise<ApiEnvelope<{ source: LogSource; item: LogFileItem | null }>> {
  const response = await requestApi<ApiLogLatestData>("/logs/latest", {
    query: { source },
  });
  if (!response.ok || !response.data) {
    return failedEnvelope(response);
  }
  return {
    ok: true,
    data: {
      source: response.data.source as LogSource,
      item: response.data.item ? toLogFileItem(response.data.item) : null,
    },
    error: null,
  };
}

export async function getLogEvents(query: LogQuery): Promise<ApiEnvelope<{
  source: LogSource;
  logId: string;
  total: number;
  page: number;
  pageSize: number;
  items: LogEventItem[];
}>> {
  const response = await requestApi<ApiLogEventsData>("/logs/events", {
    query: buildQuery(query),
  });
  if (!response.ok || !response.data) {
    return failedEnvelope(response);
  }
  return {
    ok: true,
    data: {
      source: response.data.source as LogSource,
      logId: String(response.data.log_id ?? ""),
      total: Number(response.data.total ?? 0),
      page: Number(response.data.page ?? 1),
      pageSize: Number(response.data.page_size ?? 100),
      items: (response.data.items ?? []).map(toLogEventItem),
    },
    error: null,
  };
}

export async function getLogAnalysis(query: LogQuery): Promise<ApiEnvelope<LogAnalysisSummary>> {
  const response = await requestApi<ApiLogAnalysisData>("/logs/analysis", {
    query: buildQuery(query),
  });
  if (!response.ok || !response.data) {
    return failedEnvelope(response);
  }
  return {
    ok: true,
    data: toLogAnalysisSummary(response.data),
    error: null,
  };
}
