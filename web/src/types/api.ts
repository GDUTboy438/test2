export type ApiError = {
  code: string;
  message: string;
};

export type ApiEnvelope<T> = {
  ok: boolean;
  data: T | null;
  error: ApiError | null;
};

export type ApiLibrary = {
  name: string;
  root: string;
};

export type ApiDirectoryNode = {
  id: string;
  name: string;
  path: string;
  hasChildren: boolean;
  children?: ApiDirectoryNode[] | null;
};

export type ApiVideoItem = {
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
  thumbUrl?: string | null;
};

export type ApiEntriesData = {
  items: ApiVideoItem[];
  total: number;
};

export type ApiSearchData = {
  items: ApiVideoItem[];
  total: number;
};

export type ApiScanProgress = {
  label: string;
  percent: string;
  current: number;
  total: number;
  state: string;
  rel_path: string;
};

export type ApiTagLibraryItem = {
  id: number;
  name: string;
  usage_count: number;
  manual_usage_count: number;
  ai_usage_count: number;
};

export type ApiTagCandidateItem = {
  id: number;
  name: string;
  status: "pending" | "approved" | "blacklisted" | "mapped";
  mapped_tag_id: number;
  first_seen_epoch: number;
  last_seen_epoch: number;
  hit_count: number;
};

export type ApiTagBlacklistItem = {
  id: number;
  term: string;
  source: string;
  reason: string;
  hit_count: number;
  first_seen_epoch: number;
  last_seen_epoch: number;
};

export type ApiTagLibraryData = {
  items: ApiTagLibraryItem[];
  total: number;
};

export type ApiTagCandidatesData = {
  items: ApiTagCandidateItem[];
  total: number;
};

export type ApiTagBlacklistData = {
  items: ApiTagBlacklistItem[];
  total: number;
};

export type ApiRuntimeInfoData = {
  app_title: string;
  app_version: string;
  python_executable: string;
  cwd: string;
  api_file: string;
  route_count: number;
  has_tag_routes: boolean;
  required_tag_routes: string[];
  missing_tag_routes: string[];
};

export type IdListPayload = {
  ids: number[];
};

export type CreateTagsPayload = {
  names: string[];
};

export type ApiLogSource = "scan" | "tag_mining" | "app_runtime";

export type ApiLogSourceOption = {
  source: ApiLogSource;
  label: string;
};

export type ApiLogSourcesData = {
  items: ApiLogSourceOption[];
  default_source: ApiLogSource;
};

export type ApiLogFileItem = {
  log_id: string;
  file_name: string;
  source: ApiLogSource;
  mtime_epoch: number;
  size_bytes: number;
};

export type ApiLogFilesData = {
  source: ApiLogSource;
  items: ApiLogFileItem[];
  total: number;
};

export type ApiLogLatestData = {
  source: ApiLogSource;
  item: ApiLogFileItem | null;
};

export type ApiLogEventItem = {
  line_no: number;
  ts_epoch: number;
  level: string;
  event: string;
  rel_path: string;
  summary: string;
  payload: Record<string, unknown>;
};

export type ApiLogEventsData = {
  source: ApiLogSource;
  log_id: string;
  total: number;
  page: number;
  page_size: number;
  items: ApiLogEventItem[];
};

export type ApiLogAnalysisData = {
  source: ApiLogSource;
  log_id: string;
  total: number;
  error_count: number;
  parse_error_count: number;
  last_error_ts: number | null;
  top_events: Array<{ event: string; count: number }>;
};

export type ApiFeatureModelType = "embedding" | "reranker";

export type ApiFeatureModelItem = {
  id: string;
  type: ApiFeatureModelType;
  name: string;
  source: "preset" | "custom";
  downloaded: boolean;
  download_status: "downloaded" | "missing";
  local_path: string;
  download_url: string;
  repo_id: string;
  select_value: string;
  selected: boolean;
};

export type ApiFeatureModelsData = {
  model_root: string;
  items: ApiFeatureModelItem[];
  embedding_options: ApiFeatureModelItem[];
  reranker_options: ApiFeatureModelItem[];
  imported_path?: string;
};

export type ApiFeatureThresholdsData = {
  source_path: string;
  warning: string;
  recall_top_k: number;
  recall_min_score: number;
  auto_apply: number;
  pending_review: number;
};

export type ApiFeatureTaskResultData = {
  status: string;
  processed_videos: number;
  selected_terms: number;
  tagged_videos: number;
  created_relations: number;
  pending_candidate_terms: number;
  pending_candidate_hits: number;
  semantic_auto_hits: number;
  semantic_pending_hits: number;
  semantic_rejected_hits: number;
  elapsed_ms: number;
  strategy_requested: string;
  strategy_used: string;
  model_name: string;
  reranker_name: string;
  fallback_reason: string;
  scope: string;
  threshold_config_path: string;
  top_terms: string[];
  error?: string;
};

export type ApiFeatureDependencyLogData = {
  status: string;
  reason: string;
  strategy_used: string;
  ts_epoch: number;
  log_id: string;
};

export type ApiFeatureTaskData = {
  status: string;
  phase: string;
  message: string;
  progress_percent: number;
  current: number;
  total: number;
  rel_path: string;
  started_epoch: number;
  updated_epoch: number;
  strategy: string;
  scope: string;
  embedding_model: string;
  reranker_model: string;
  min_df: number;
  max_tags_per_video: number;
  max_terms: number;
  recall_top_k: number | null;
  recall_min_score: number | null;
  auto_apply: number | null;
  pending_review: number | null;
  fallback_reason: string;
  dependency_status: string;
  dependency_message: string;
  result: ApiFeatureTaskResultData;
  running_lock_model_switch: boolean;
  background_run_supported: boolean;
  dependency_log?: ApiFeatureDependencyLogData;
};
