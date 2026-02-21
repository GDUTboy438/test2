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
