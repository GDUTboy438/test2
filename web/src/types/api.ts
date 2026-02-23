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
