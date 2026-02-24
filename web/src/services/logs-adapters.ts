import type {
  ApiLogAnalysisData,
  ApiLogEventItem,
  ApiLogFileItem,
  ApiLogSourceOption,
} from "../types/api";
import type {
  LogAnalysisSummary,
  LogEventItem,
  LogFileItem,
  LogSource,
  LogSourceOption,
} from "../types/domain";

function formatDateTime(epoch: number): string {
  if (!epoch || epoch <= 0) {
    return "--";
  }
  return new Date(epoch * 1000).toLocaleString("sv-SE").replace("T", " ");
}

function formatTime(epoch: number): string {
  if (!epoch || epoch <= 0) {
    return "--:--:--";
  }
  return new Date(epoch * 1000).toLocaleTimeString("en-GB", { hour12: false });
}

function formatSize(sizeBytes: number): string {
  if (!sizeBytes || sizeBytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = sizeBytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  if (unitIndex === 0) {
    return `${Math.round(size)} ${units[unitIndex]}`;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

export function toLogSourceOption(item: ApiLogSourceOption): LogSourceOption {
  return {
    source: item.source as LogSource,
    label: String(item.label ?? ""),
  };
}

export function toLogFileItem(item: ApiLogFileItem): LogFileItem {
  return {
    logId: String(item.log_id ?? ""),
    fileName: String(item.file_name ?? ""),
    source: item.source as LogSource,
    mtimeEpoch: Number(item.mtime_epoch ?? 0),
    sizeBytes: Number(item.size_bytes ?? 0),
    mtimeLabel: formatDateTime(Number(item.mtime_epoch ?? 0)),
    sizeLabel: formatSize(Number(item.size_bytes ?? 0)),
  };
}

export function toLogEventItem(item: ApiLogEventItem): LogEventItem {
  return {
    lineNo: Number(item.line_no ?? 0),
    tsEpoch: Number(item.ts_epoch ?? 0),
    timeLabel: formatTime(Number(item.ts_epoch ?? 0)),
    level: String(item.level ?? ""),
    event: String(item.event ?? ""),
    relPath: String(item.rel_path ?? "-"),
    summary: String(item.summary ?? ""),
    payload: (item.payload ?? {}) as Record<string, unknown>,
  };
}

export function toLogAnalysisSummary(item: ApiLogAnalysisData): LogAnalysisSummary {
  const lastErrorTs = item.last_error_ts == null ? null : Number(item.last_error_ts);
  return {
    source: item.source as LogSource,
    logId: String(item.log_id ?? ""),
    total: Number(item.total ?? 0),
    errorCount: Number(item.error_count ?? 0),
    parseErrorCount: Number(item.parse_error_count ?? 0),
    lastErrorTs,
    lastErrorLabel: lastErrorTs == null ? "--" : formatTime(lastErrorTs),
    topEvents: (item.top_events ?? []).map((entry) => ({
      event: String(entry.event ?? ""),
      count: Number(entry.count ?? 0),
    })),
  };
}
