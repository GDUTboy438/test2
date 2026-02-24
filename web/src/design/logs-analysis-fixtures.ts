import type {
  LogAnalysisSummary,
  LogEventItem,
  LogFileItem,
  LogSource,
  LogSourceOption,
} from "../types/domain";

export type LogsAnalysisSceneId = "CIBf0" | "Hyzda";

type LogsAnalysisFixture = {
  sourceOptions: LogSourceOption[];
  defaultSource: LogSource;
  files: LogFileItem[];
  selectedLogId: string;
  events: LogEventItem[];
  analysis: LogAnalysisSummary;
  detailOpenDefault: boolean;
  selectedEventLineNoDefault: number | null;
};

const sourceOptions: LogSourceOption[] = [
  { source: "scan", label: "扫描日志" },
  { source: "tag_mining", label: "标签提取日志" },
  { source: "app_runtime", label: "项目运行日志" },
];

const files: LogFileItem[] = [
  {
    logId: "runtime_20260224.jsonl",
    fileName: "runtime_20260224.jsonl",
    source: "app_runtime",
    mtimeEpoch: 1766601012,
    sizeBytes: 2_516_582,
    mtimeLabel: "2026-02-24 10:30:12",
    sizeLabel: "2.4 MB",
  },
  {
    logId: "runtime_20260223.jsonl",
    fileName: "runtime_20260223.jsonl",
    source: "app_runtime",
    mtimeEpoch: 1766558100,
    sizeBytes: 1_887_437,
    mtimeLabel: "2026-02-24 09:15:00",
    sizeLabel: "1.8 MB",
  },
  {
    logId: "scan_20260224_103012.jsonl",
    fileName: "scan_20260224_103012.jsonl",
    source: "scan",
    mtimeEpoch: 1766516700,
    sizeBytes: 1_363_148,
    mtimeLabel: "2026-02-23 21:45:00",
    sizeLabel: "1.3 MB",
  },
  {
    logId: "tag_mining_20260224_104210.jsonl",
    fileName: "tag_mining_20260224_104210.jsonl",
    source: "tag_mining",
    mtimeEpoch: 1766601730,
    sizeBytes: 946_176,
    mtimeLabel: "2026-02-24 10:42:10",
    sizeLabel: "924 KB",
  },
];

const events: LogEventItem[] = [
  {
    lineNo: 1,
    tsEpoch: 1766601012,
    timeLabel: "10:30:12",
    level: "info",
    event: "scan_start",
    relPath: "-",
    summary: "Scan started, total_files=420",
    payload: { total_files: 420, stage: "scan_start" },
  },
  {
    lineNo: 2,
    tsEpoch: 1766601013,
    timeLabel: "10:30:13",
    level: "info",
    event: "file_discovered",
    relPath: "/Movies/A.mp4",
    summary: "file_discovered /Movies/A.mp4",
    payload: { rel_path: "/Movies/A.mp4" },
  },
  {
    lineNo: 3,
    tsEpoch: 1766601015,
    timeLabel: "10:30:15",
    level: "error",
    event: "parse_error",
    relPath: "-",
    summary: "Invalid JSON line.",
    payload: { error: "Invalid JSON line." },
  },
];

const analysis: LogAnalysisSummary = {
  source: "app_runtime",
  logId: "runtime_20260224.jsonl",
  total: 240,
  errorCount: 12,
  parseErrorCount: 2,
  lastErrorTs: 1766601015,
  lastErrorLabel: "10:30:15",
  topEvents: [
    { event: "file_discovered", count: 110 },
    { event: "scan_start", count: 1 },
    { event: "parse_error", count: 2 },
  ],
};

const baseFixture: Omit<LogsAnalysisFixture, "detailOpenDefault" | "selectedEventLineNoDefault"> = {
  sourceOptions,
  defaultSource: "app_runtime",
  files,
  selectedLogId: "runtime_20260224.jsonl",
  events,
  analysis,
};

const fixtureByScene: Record<LogsAnalysisSceneId, LogsAnalysisFixture> = {
  CIBf0: {
    ...baseFixture,
    detailOpenDefault: false,
    selectedEventLineNoDefault: null,
  },
  Hyzda: {
    ...baseFixture,
    detailOpenDefault: true,
    selectedEventLineNoDefault: 3,
  },
};

export function getLogsAnalysisFixture(scene: LogsAnalysisSceneId = "CIBf0"): LogsAnalysisFixture {
  const resolvedScene = scene in fixtureByScene ? scene : "CIBf0";
  return JSON.parse(JSON.stringify(fixtureByScene[resolvedScene])) as LogsAnalysisFixture;
}
