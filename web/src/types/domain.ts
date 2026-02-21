export type SceneId = "5JcTk" | "88L9O" | "JrodX" | "2L8Xf";

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
