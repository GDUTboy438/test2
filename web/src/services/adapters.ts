import type { ApiDirectoryNode, ApiLibrary, ApiVideoItem } from "../types/api";
import type { DirectoryNode, LibraryInfo, SortDirection, SortField, VideoItem } from "../types/domain";

const SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"];

export function toLibraryInfo(raw: ApiLibrary): LibraryInfo {
  return {
    name: raw.name,
    root: raw.root,
  };
}

export function toDirectoryNode(raw: ApiDirectoryNode): DirectoryNode {
  return {
    id: raw.id,
    name: raw.name,
    path: raw.path,
    hasChildren: raw.hasChildren,
    children: (raw.children ?? []).map(toDirectoryNode),
  };
}

export function toVideoItem(raw: ApiVideoItem): VideoItem {
  return {
    id: raw.id,
    name: raw.name,
    path: raw.path,
    filePath: raw.filePath,
    duration: raw.duration,
    resolution: raw.resolution,
    size: raw.size,
    modified: raw.modified,
    status: raw.status,
    tags: raw.tags ?? [],
    detail: raw.detail,
    thumbUrl: raw.thumbUrl ?? null,
  };
}

export function normalizeRelativePath(value: string): string {
  const cleaned = value.trim().replaceAll("\\", "/");
  return cleaned.startsWith("/") ? cleaned.slice(1) : cleaned;
}

export function toOpenPath(video: VideoItem): string {
  const fromId = normalizeRelativePath(video.id);
  if (fromId.length > 0) {
    return fromId;
  }
  return normalizeRelativePath(video.filePath);
}

export function parseDurationSeconds(text: string): number {
  const parts = text.split(":").map((value) => Number.parseInt(value, 10));
  if (parts.some((value) => Number.isNaN(value))) {
    return 0;
  }
  if (parts.length === 2) {
    return (parts[0] * 60) + parts[1];
  }
  if (parts.length === 3) {
    return (parts[0] * 3600) + (parts[1] * 60) + parts[2];
  }
  return 0;
}

export function parseSizeBytes(text: string): number {
  const match = text.match(/^(\d+(?:\.\d+)?)\s*([A-Za-z]+)$/);
  if (!match) {
    return 0;
  }
  const value = Number.parseFloat(match[1]);
  const unit = match[2].toUpperCase();
  const unitIndex = SIZE_UNITS.indexOf(unit);
  if (Number.isNaN(value) || unitIndex < 0) {
    return 0;
  }
  return Math.round(value * (1024 ** unitIndex));
}

function parseDateMillis(text: string): number {
  const parsed = Date.parse(text);
  return Number.isNaN(parsed) ? 0 : parsed;
}

const nameCollator = new Intl.Collator("zh-Hans-CN", { numeric: true, sensitivity: "base" });

export function sortVideos(items: VideoItem[], field: SortField, direction: SortDirection): VideoItem[] {
  const sorted = [...items];
  sorted.sort((left, right) => {
    let result = 0;
    if (field === "name") {
      result = nameCollator.compare(left.name, right.name);
    }
    if (field === "modified") {
      result = parseDateMillis(left.modified) - parseDateMillis(right.modified);
    }
    if (field === "duration") {
      result = parseDurationSeconds(left.duration) - parseDurationSeconds(right.duration);
    }
    if (field === "size") {
      result = parseSizeBytes(left.size) - parseSizeBytes(right.size);
    }
    if (result === 0) {
      result = nameCollator.compare(left.name, right.name);
    }
    return direction === "asc" ? result : (result * -1);
  });
  return sorted;
}

export function formatDirectoryLabel(selectedDirectoryId: string, libraryName: string): string {
  if (!selectedDirectoryId) {
    return `${libraryName} > All Media`;
  }
  const last = selectedDirectoryId.split("/").filter(Boolean).at(-1) ?? selectedDirectoryId;
  return `${libraryName} > ${last}`;
}

export function buildRootNode(library: LibraryInfo, children: DirectoryNode[]): DirectoryNode {
  return {
    id: "",
    name: library.name,
    path: "/",
    hasChildren: children.length > 0,
    children,
  };
}

export function flattenStatusOptions(items: VideoItem[]): string[] {
  const options = new Set<string>();
  items.forEach((item) => options.add(item.status));
  return Array.from(options).sort(nameCollator.compare);
}

export function flattenResolutionOptions(items: VideoItem[]): string[] {
  const options = new Set<string>();
  items.forEach((item) => options.add(item.resolution));
  return Array.from(options).sort(nameCollator.compare);
}
