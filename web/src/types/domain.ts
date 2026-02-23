export type SceneId = "5JcTk" | "88L9O" | "JrodX" | "2L8Xf" | "J7vS3";

export type AppPage = "home" | "tag-manager";

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
