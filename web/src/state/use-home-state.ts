import { useCallback, useEffect, useMemo, useState } from "react";
import { getFrameSpec, parseSceneId, sceneFromState } from "../design/frame-spec";
import { getSceneFixture } from "../design/scene-fixtures";
import {
  buildRootNode,
  flattenResolutionOptions,
  flattenStatusOptions,
  formatDirectoryLabel,
  sortVideos,
} from "../services/adapters";
import {
  getCurrentLibrary,
  getDirectoryTree,
  getScanProgress,
  getVideosByDirectory,
  openVideo,
  pickLibrary,
  searchVideos,
} from "../services/library-api";
import type {
  DirectoryNode,
  FilterState,
  LibraryInfo,
  ScanProgressInfo,
  SceneId,
  SortDirection,
  SortField,
  ToastState,
  UiMode,
  VideoItem,
  ViewMode,
} from "../types/domain";

const PAGE_SIZE = 20;

function readMode(): UiMode {
  const mode = new URLSearchParams(window.location.search).get("mode");
  return mode === "visual" ? "visual" : "live";
}

function defaultScanState(): ScanProgressInfo {
  return {
    title: "Idle",
    percentText: "0%",
    percentValue: 0,
  };
}

function useDebouncedValue(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

function applyFilters(items: VideoItem[], filters: FilterState): VideoItem[] {
  return items.filter((item) => {
    const statusMatches =
      filters.statuses.length === 0 || filters.statuses.includes(item.status);
    const resolutionMatches =
      filters.resolutions.length === 0 || filters.resolutions.includes(item.resolution);
    return statusMatches && resolutionMatches;
  });
}

export type HomeState = {
  mode: UiMode;
  scene: SceneId;
  frameName: string;
  viewMode: ViewMode;
  detailOpen: boolean;
  loading: boolean;
  errorMessage: string;
  toast: ToastState | null;
  searchInput: string;
  library: LibraryInfo | null;
  treeRoot: DirectoryNode | null;
  selectedDirectoryId: string;
  items: VideoItem[];
  pageItems: VideoItem[];
  selectedVideo: VideoItem | null;
  statusOptions: string[];
  resolutionOptions: string[];
  filterState: FilterState;
  sortField: SortField;
  sortDirection: SortDirection;
  page: number;
  totalPages: number;
  breadcrumb: string;
  scanProgress: ScanProgressInfo;
  subNavHeight: 58 | 60;
  contentGap: number;
  listHeaderHeight: 50 | 54;
  listRowHeight: 86 | 94;
  gridCardHeight: 208 | 206;
  detailWidth: number;
  canInteract: boolean;
  setSearchInput: (value: string) => void;
  selectDirectory: (id: string) => void;
  setViewMode: (value: ViewMode) => void;
  setFilterState: (value: FilterState) => void;
  setSortField: (value: SortField) => void;
  toggleSortDirection: () => void;
  setPage: (value: number) => void;
  selectVideo: (id: string) => void;
  clearSelection: () => void;
  pickLibrary: () => Promise<void>;
  playSelected: () => Promise<void>;
};

export function useHomeState(): HomeState {
  const mode = readMode();
  const requestedScene = parseSceneId(new URLSearchParams(window.location.search).get("scene"));
  const fixture = useMemo(() => getSceneFixture(requestedScene), [requestedScene]);

  const [library, setLibrary] = useState<LibraryInfo | null>(
    mode === "visual" ? fixture.library : null,
  );
  const [treeRoot, setTreeRoot] = useState<DirectoryNode | null>(
    mode === "visual" ? buildRootNode(fixture.library, fixture.directories) : null,
  );
  const [selectedDirectoryId, setSelectedDirectoryId] = useState(
    mode === "visual" ? fixture.selectedDirectoryId : "",
  );
  const [items, setItems] = useState<VideoItem[]>(mode === "visual" ? fixture.items : []);
  const [searchInput, setSearchInput] = useState(mode === "visual" ? fixture.searchInput : "");
  const [viewMode, setViewMode] = useState<ViewMode>(
    mode === "visual" ? fixture.viewMode : "list",
  );
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(
    mode === "visual" ? fixture.selectedVideoId : null,
  );
  const [loading, setLoading] = useState(mode === "live");
  const [errorMessage, setErrorMessage] = useState("");
  const [toast, setToast] = useState<ToastState | null>(null);
  const [scanProgress, setScanProgress] = useState<ScanProgressInfo>(
    mode === "visual" ? fixture.scan : defaultScanState(),
  );
  const [filterState, setFilterState] = useState<FilterState>({ statuses: [], resolutions: [] });
  const [sortField, setSortField] = useState<SortField>("modified");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebouncedValue(searchInput, 300);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const setFailure = useCallback((message: string) => {
    setErrorMessage(message);
    setToast({ tone: "error", message });
  }, []);

  const bootstrapLiveMode = useCallback(async () => {
    const current = await getCurrentLibrary();
    if (!current.ok || !current.data) {
      if (current.error?.code === "NO_LIBRARY") {
        setLoading(false);
        setLibrary(null);
        setTreeRoot(null);
        setItems([]);
        setSelectedDirectoryId("");
        return;
      }
      setLoading(false);
      setFailure(current.error?.message ?? "Failed to load current library.");
      return;
    }

    setLibrary(current.data);

    const tree = await getDirectoryTree(current.data);
    if (!tree.ok || !tree.data) {
      setLoading(false);
      setFailure(tree.error?.message ?? "Failed to load directory tree.");
      return;
    }

    setTreeRoot(tree.data);
    setSelectedDirectoryId("");
    setLoading(false);
  }, [setFailure]);

  useEffect(() => {
    if (mode !== "live") {
      return;
    }
    void bootstrapLiveMode();
  }, [mode, bootstrapLiveMode]);

  const loadEntries = useCallback(async () => {
    if (mode !== "live" || !library) {
      return;
    }

    setLoading(true);

    const trimmed = debouncedSearch.trim();
    const response = trimmed.length > 0
      ? await searchVideos(trimmed)
      : await getVideosByDirectory(selectedDirectoryId);

    if (!response.ok || !response.data) {
      setLoading(false);
      setFailure(response.error?.message ?? "Failed to load videos.");
      return;
    }

    setItems(response.data);
    setLoading(false);
  }, [mode, library, debouncedSearch, selectedDirectoryId, setFailure]);

  useEffect(() => {
    if (mode !== "live" || !library) {
      return;
    }
    void loadEntries();
  }, [mode, library, loadEntries]);

  useEffect(() => {
    if (mode !== "live" || !library) {
      return;
    }

    let disposed = false;

    const tick = async () => {
      const progress = await getScanProgress();
      if (!progress.ok || !progress.data || disposed) {
        return;
      }
      setScanProgress(progress.data);
    };

    void tick();
    const timer = window.setInterval(() => {
      void tick();
    }, 2000);

    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [mode, library]);

  useEffect(() => {
    setPage(1);
  }, [selectedDirectoryId, debouncedSearch, filterState, sortField, sortDirection, viewMode]);

  const filteredItems = useMemo(
    () => applyFilters(items, filterState),
    [items, filterState],
  );

  const sortedItems = useMemo(
    () => sortVideos(filteredItems, sortField, sortDirection),
    [filteredItems, sortField, sortDirection],
  );

  const totalPages = useMemo(() => {
    const count = Math.ceil(sortedItems.length / PAGE_SIZE);
    return Math.max(1, count);
  }, [sortedItems]);

  useEffect(() => {
    if (page <= totalPages) {
      return;
    }
    setPage(totalPages);
  }, [page, totalPages]);

  const pageItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    const end = start + PAGE_SIZE;
    return sortedItems.slice(start, end);
  }, [page, sortedItems]);

  const selectedVideo = useMemo(
    () => sortedItems.find((item) => item.id === selectedVideoId) ?? null,
    [sortedItems, selectedVideoId],
  );

  useEffect(() => {
    if (!selectedVideoId) {
      return;
    }
    const exists = sortedItems.some((item) => item.id === selectedVideoId);
    if (!exists) {
      setSelectedVideoId(null);
    }
  }, [selectedVideoId, sortedItems]);

  const statusOptions = useMemo(() => flattenStatusOptions(items), [items]);
  const resolutionOptions = useMemo(() => flattenResolutionOptions(items), [items]);

  const detailOpen = selectedVideo !== null;
  const scene = mode === "visual" ? requestedScene : sceneFromState(viewMode, detailOpen);
  const frameSpec = getFrameSpec(scene);

  const breadcrumb = useMemo(() => {
    const libraryName = library?.name ?? "VisionVault";
    return formatDirectoryLabel(selectedDirectoryId, libraryName);
  }, [library, selectedDirectoryId]);

  const onPickLibrary = useCallback(async () => {
    if (mode !== "live") {
      return;
    }

    const selected = await pickLibrary();
    if (!selected.ok || !selected.data) {
      setFailure(selected.error?.message ?? "Failed to select library.");
      return;
    }

    setLibrary(selected.data);
    setSearchInput("");
    setSelectedVideoId(null);

    const tree = await getDirectoryTree(selected.data);
    if (!tree.ok || !tree.data) {
      setFailure(tree.error?.message ?? "Failed to load directory tree.");
      return;
    }

    setTreeRoot(tree.data);
    setSelectedDirectoryId("");
    setToast({ tone: "success", message: "Library selected." });
  }, [mode, setFailure]);

  const playSelected = useCallback(async () => {
    if (!selectedVideo) {
      return;
    }

    if (mode !== "live") {
      setToast({ tone: "success", message: "Play action is disabled in visual mode." });
      return;
    }

    const opened = await openVideo(selectedVideo);
    if (!opened.ok) {
      setFailure(opened.error?.message ?? "Failed to open video.");
      return;
    }

    setToast({ tone: "success", message: "Video opened." });
  }, [mode, selectedVideo, setFailure]);

  return {
    mode,
    scene,
    frameName: frameSpec.name,
    viewMode,
    detailOpen,
    loading,
    errorMessage,
    toast,
    searchInput,
    library,
    treeRoot,
    selectedDirectoryId,
    items,
    pageItems,
    selectedVideo,
    statusOptions,
    resolutionOptions,
    filterState,
    sortField,
    sortDirection,
    page,
    totalPages,
    breadcrumb,
    scanProgress,
    subNavHeight: frameSpec.subNavHeight,
    contentGap: frameSpec.contentGap,
    listHeaderHeight: frameSpec.listHeaderHeight,
    listRowHeight: frameSpec.listRowHeight,
    gridCardHeight: frameSpec.gridCardHeight,
    detailWidth: frameSpec.detailWidth,
    canInteract: true,
    setSearchInput,
    selectDirectory: (id: string) => {
      setSelectedDirectoryId(id);
      setSelectedVideoId(null);
    },
    setViewMode,
    setFilterState,
    setSortField,
    toggleSortDirection: () => {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    },
    setPage,
    selectVideo: (id: string) => setSelectedVideoId(id),
    clearSelection: () => setSelectedVideoId(null),
    pickLibrary: onPickLibrary,
    playSelected,
  };
}

