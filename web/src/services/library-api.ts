import type {
  ApiDirectoryNode,
  ApiEntriesData,
  ApiEnvelope,
  ApiLibrary,
  ApiScanProgress,
  ApiSearchData,
} from "../types/api";
import type { DirectoryNode, LibraryInfo, ScanProgressInfo, VideoItem } from "../types/domain";
import { buildRootNode, toDirectoryNode, toLibraryInfo, toOpenPath, toVideoItem } from "./adapters";
import { requestApi } from "./http";

export async function getCurrentLibrary(): Promise<ApiEnvelope<LibraryInfo>> {
  const response = await requestApi<ApiLibrary>("/library/current");
  if (!response.ok || !response.data) {
    return {
      ok: false,
      data: null,
      error: response.error,
    };
  }
  return {
    ok: true,
    data: toLibraryInfo(response.data),
    error: null,
  };
}

export async function pickLibrary(): Promise<ApiEnvelope<LibraryInfo>> {
  const response = await requestApi<ApiLibrary>("/library/pick", { method: "POST" });
  if (!response.ok || !response.data) {
    return {
      ok: false,
      data: null,
      error: response.error,
    };
  }
  return {
    ok: true,
    data: toLibraryInfo(response.data),
    error: null,
  };
}

export async function getDirectoryTree(library: LibraryInfo): Promise<ApiEnvelope<DirectoryNode>> {
  const response = await requestApi<ApiDirectoryNode[]>("/directories", {
    query: { path: "", depth: 2 },
  });
  if (!response.ok || !response.data) {
    return {
      ok: false,
      data: null,
      error: response.error,
    };
  }

  const children = response.data.map(toDirectoryNode);
  return {
    ok: true,
    data: buildRootNode(library, children),
    error: null,
  };
}

export async function getVideosByDirectory(path: string): Promise<ApiEnvelope<VideoItem[]>> {
  const response = await requestApi<ApiEntriesData>("/entries", {
    query: {
      path,
      recursive: true,
    },
  });
  if (!response.ok || !response.data) {
    return {
      ok: false,
      data: null,
      error: response.error,
    };
  }

  return {
    ok: true,
    data: response.data.items.map(toVideoItem),
    error: null,
  };
}

export async function searchVideos(query: string): Promise<ApiEnvelope<VideoItem[]>> {
  const response = await requestApi<ApiSearchData>("/search", {
    query: { q: query },
  });
  if (!response.ok || !response.data) {
    return {
      ok: false,
      data: null,
      error: response.error,
    };
  }

  return {
    ok: true,
    data: response.data.items.map(toVideoItem),
    error: null,
  };
}

export async function openVideo(video: VideoItem): Promise<ApiEnvelope<{ status: string; path: string }>> {
  return requestApi<{ status: string; path: string }>("/entries/open", {
    method: "POST",
    body: {
      path: toOpenPath(video),
    },
  });
}

export async function getScanProgress(): Promise<ApiEnvelope<ScanProgressInfo>> {
  const response = await requestApi<ApiScanProgress>("/scan/progress");
  if (!response.ok || !response.data) {
    return {
      ok: false,
      data: null,
      error: response.error,
    };
  }

  const percentRaw = response.data.percent.replace("%", "");
  const parsedPercent = Number.parseInt(percentRaw, 10);

  return {
    ok: true,
    data: {
      title: response.data.label,
      percentText: response.data.percent,
      percentValue: Number.isNaN(parsedPercent) ? 0 : parsedPercent,
    },
    error: null,
  };
}
