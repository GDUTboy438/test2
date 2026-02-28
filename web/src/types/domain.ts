export type SceneId =
  | "5JcTk"
  | "88L9O"
  | "JrodX"
  | "2L8Xf"
  | "J7vS3"
  | "CIBf0"
  | "Hyzda"
  | "FEx01"
  | "hFUDa";

export type AppPage = "home" | "settings";

export type SettingsModule = "tag-manager" | "feature-extraction" | "logs-analysis";

export type UiMode = "live" | "visual";

export type ViewMode = "list" | "grid";

export type SortField = "name" | "modified" | "duration" | "size";

export type SortDirection = "asc" | "desc";

export type FilterState = {
  statuses: string[];
  resolutions: string[];
};

export type PaginationState = {
  page: number;
  pageSize: number;
};

export type LibraryInfo = {
  name: string;
  root: string;
};

export type DirectoryNode = {
  id: string;
  name: string;
  path: string;
  hasChildren: boolean;
  children: DirectoryNode[];
};

export type VideoItem = {
  id: string;
  name: string;
  path: string;
  filePath: string;
  duration: string;
  resolution: string;
  size: string;
  modified: string;
  status: string;
  tags: string[];
  detail: string;
  thumbUrl: string | null;
};

export type ScanProgressInfo = {
  title: string;
  percentText: string;
  percentValue: number;
};

export type ToastState = {
  tone: "success" | "error";
  message: string;
};

export type TagSource = "all" | "tag_library" | "candidate_library" | "blacklist";

export type TagSection = "tag_library" | "candidate_library" | "blacklist";

export type TagLibraryItem = {
  id: number;
  name: string;
  usageCount: number;
  manualUsageCount: number;
  aiUsageCount: number;
};

export type TagCandidateStatus = "pending" | "approved" | "blacklisted" | "mapped";

export type TagCandidateItem = {
  id: number;
  name: string;
  status: TagCandidateStatus;
  mappedTagId: number;
  hitCount: number;
  firstSeenEpoch: number;
  lastSeenEpoch: number;
};

export type TagBlacklistItem = {
  id: number;
  term: string;
  source: string;
  reason: string;
  hitCount: number;
  firstSeenEpoch: number;
  lastSeenEpoch: number;
};

export type LogSource = "scan" | "tag_mining" | "app_runtime";

export type LogSourceOption = {
  source: LogSource;
  label: string;
};

export type LogFileItem = {
  logId: string;
  fileName: string;
  source: LogSource;
  mtimeEpoch: number;
  sizeBytes: number;
  mtimeLabel: string;
  sizeLabel: string;
};

export type LogEventItem = {
  lineNo: number;
  tsEpoch: number;
  timeLabel: string;
  level: string;
  event: string;
  relPath: string;
  summary: string;
  payload: Record<string, unknown>;
};

export type LogAnalysisSummary = {
  source: LogSource;
  logId: string;
  total: number;
  errorCount: number;
  parseErrorCount: number;
  lastErrorTs: number | null;
  lastErrorLabel: string;
  topEvents: Array<{ event: string; count: number }>;
};

export type LogsFilterState = {
  q: string;
  level: string;
  event: string;
  fromTs: number | null;
  toTs: number | null;
};

export type LogsPaginationState = {
  page: number;
  pageSize: number;
  total: number;
};
