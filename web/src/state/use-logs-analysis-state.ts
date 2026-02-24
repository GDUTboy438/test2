import { useCallback, useEffect, useMemo, useState } from "react";
import { getLogsAnalysisFixture, type LogsAnalysisSceneId } from "../design/logs-analysis-fixtures";
import {
  getLatestLog,
  getLogAnalysis,
  getLogEvents,
  getLogFiles,
  getLogSources,
} from "../services/logs-api";
import type {
  LogAnalysisSummary,
  LogEventItem,
  LogFileItem,
  LogSource,
  LogSourceOption,
  LogsFilterState,
  ToastState,
  UiMode,
} from "../types/domain";

const DEFAULT_PAGE_SIZE = 100;

function readMode(): UiMode {
  const mode = new URLSearchParams(window.location.search).get("mode");
  return mode === "visual" ? "visual" : "live";
}

function readLogsScene(): LogsAnalysisSceneId {
  const scene = new URLSearchParams(window.location.search).get("scene");
  return scene === "Hyzda" ? "Hyzda" : "CIBf0";
}

function useDebouncedValue(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function emptyAnalysis(source: LogSource, logId = ""): LogAnalysisSummary {
  return {
    source,
    logId,
    total: 0,
    errorCount: 0,
    parseErrorCount: 0,
    lastErrorTs: null,
    lastErrorLabel: "--",
    topEvents: [],
  };
}

function formatError(errorCode: string | undefined, fallback: string): string {
  if (errorCode === "NO_LIBRARY") {
    return "No library selected. Go back to Home and select a library first.";
  }
  return fallback;
}

export type LogsAnalysisState = {
  mode: UiMode;
  scene: LogsAnalysisSceneId;
  loading: boolean;
  canInteract: boolean;
  hasLibrary: boolean;
  errorMessage: string;
  toast: ToastState | null;
  sourceOptions: LogSourceOption[];
  source: LogSource;
  files: LogFileItem[];
  selectedLogId: string;
  selectedFile: LogFileItem | null;
  leftPaneCollapsed: boolean;
  analysis: LogAnalysisSummary;
  filters: LogsFilterState;
  events: LogEventItem[];
  page: number;
  pageSize: number;
  total: number;
  selectedEventLineNo: number | null;
  detailOpen: boolean;
  detailEvent: LogEventItem | null;
  levelOptions: string[];
  eventOptions: string[];
  setSource: (value: LogSource) => void;
  refreshFiles: () => Promise<void>;
  loadLatest: () => Promise<void>;
  setKeyword: (value: string) => void;
  setLevel: (value: string) => void;
  setEvent: (value: string) => void;
  clearFilters: () => void;
  setPage: (page: number) => void;
  selectFile: (logId: string) => void;
  selectEvent: (lineNo: number) => void;
  openEventDetail: (lineNo: number) => void;
  closeDetailDrawer: () => void;
  toggleLeftPane: () => void;
};

export function useLogsAnalysisState(): LogsAnalysisState {
  const mode = readMode();
  const scene = readLogsScene();
  const fixture = useMemo(() => getLogsAnalysisFixture(scene), [scene]);

  const [loading, setLoading] = useState(mode === "live");
  const [hasLibrary, setHasLibrary] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [toast, setToast] = useState<ToastState | null>(null);

  const [sourceOptions, setSourceOptions] = useState<LogSourceOption[]>(
    mode === "visual" ? fixture.sourceOptions : [],
  );
  const [source, setSourceState] = useState<LogSource>(
    mode === "visual" ? fixture.defaultSource : "app_runtime",
  );
  const [files, setFiles] = useState<LogFileItem[]>(mode === "visual" ? fixture.files : []);
  const [selectedLogId, setSelectedLogId] = useState<string>(
    mode === "visual" ? fixture.selectedLogId : "",
  );
  const [analysis, setAnalysis] = useState<LogAnalysisSummary>(
    mode === "visual" ? fixture.analysis : emptyAnalysis("app_runtime"),
  );
  const [events, setEvents] = useState<LogEventItem[]>(mode === "visual" ? fixture.events : []);
  const [page, setPageState] = useState(1);
  const [total, setTotal] = useState(mode === "visual" ? fixture.analysis.total : 0);
  const [leftPaneCollapsed, setLeftPaneCollapsed] = useState(false);
  const [selectedEventLineNo, setSelectedEventLineNo] = useState<number | null>(
    mode === "visual" ? fixture.selectedEventLineNoDefault : null,
  );
  const [detailOpen, setDetailOpen] = useState(mode === "visual" ? fixture.detailOpenDefault : false);
  const [filters, setFilters] = useState<LogsFilterState>({
    q: "",
    level: "",
    event: "",
    fromTs: null,
    toTs: null,
  });

  const debouncedKeyword = useDebouncedValue(filters.q, 300);
  const pageSize = DEFAULT_PAGE_SIZE;

  const selectedFile = useMemo(
    () => files.find((item) => item.logId === selectedLogId) ?? null,
    [files, selectedLogId],
  );
  const detailEvent = useMemo(
    () => events.find((item) => item.lineNo === selectedEventLineNo) ?? null,
    [events, selectedEventLineNo],
  );
  const levelOptions = useMemo(() => {
    const options = Array.from(new Set(events.map((item) => item.level).filter(Boolean)));
    return options.sort();
  }, [events]);
  const eventOptions = useMemo(() => {
    const options = Array.from(new Set(events.map((item) => item.event).filter(Boolean)));
    return options.sort();
  }, [events]);

  useEffect(() => {
    if (selectedEventLineNo === null) {
      return;
    }
    const stillExists = events.some((item) => item.lineNo === selectedEventLineNo);
    if (!stillExists) {
      setSelectedEventLineNo(null);
      setDetailOpen(false);
    }
  }, [events, selectedEventLineNo]);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (mode !== "visual") {
      return;
    }
    setSourceOptions(fixture.sourceOptions);
    setSourceState(fixture.defaultSource);
    setFiles(fixture.files);
    setSelectedLogId(fixture.selectedLogId);
    setAnalysis(fixture.analysis);
    setEvents(fixture.events);
    setTotal(fixture.analysis.total);
    setPageState(1);
    setSelectedEventLineNo(fixture.selectedEventLineNoDefault);
    setDetailOpen(fixture.detailOpenDefault);
    setErrorMessage("");
    setHasLibrary(true);
  }, [fixture, mode]);

  const setFailure = useCallback((message: string) => {
    setErrorMessage(message);
    setToast({ tone: "error", message });
  }, []);

  const refreshFilesForSource = useCallback(
    async (targetSource: LogSource, preferLatest: boolean, currentLogId = "") => {
      if (mode !== "live") {
        return;
      }

      const [filesResp, latestResp] = await Promise.all([
        getLogFiles(targetSource, 200),
        getLatestLog(targetSource),
      ]);

      if (!filesResp.ok || !filesResp.data) {
        if (filesResp.error?.code === "NO_LIBRARY") {
          setHasLibrary(false);
          setErrorMessage("No library selected. Go back to Home and select a library first.");
          setFiles([]);
          setSelectedLogId("");
          setEvents([]);
          setTotal(0);
          setAnalysis(emptyAnalysis(targetSource));
          return;
        }
        setFailure(formatError(filesResp.error?.code, filesResp.error?.message ?? "Failed to load log files."));
        setFiles([]);
        setSelectedLogId("");
        setEvents([]);
        setTotal(0);
        setAnalysis(emptyAnalysis(targetSource));
        return;
      }

      setHasLibrary(true);
      setErrorMessage("");
      setFiles(filesResp.data.items);

      const latestLogId = latestResp.ok && latestResp.data?.item ? latestResp.data.item.logId : "";
      const hasCurrent = filesResp.data.items.some((item) => item.logId === currentLogId);
      const nextSelected =
        preferLatest || !hasCurrent
          ? latestLogId || filesResp.data.items[0]?.logId || ""
          : currentLogId;
      setSelectedLogId(nextSelected);
      setPageState(1);
      setSelectedEventLineNo(null);
      setDetailOpen(false);
    },
    [mode, setFailure],
  );

  useEffect(() => {
    if (mode !== "live") {
      return;
    }

    let disposed = false;

    const bootstrap = async () => {
      setLoading(true);
      const sourcesResp = await getLogSources();
      if (disposed) {
        return;
      }
      if (!sourcesResp.ok || !sourcesResp.data) {
        setLoading(false);
        if (sourcesResp.error?.code === "NO_LIBRARY") {
          setHasLibrary(false);
          setErrorMessage("No library selected. Go back to Home and select a library first.");
          return;
        }
        setFailure(formatError(sourcesResp.error?.code, sourcesResp.error?.message ?? "Failed to load log sources."));
        return;
      }

      setHasLibrary(true);
      setErrorMessage("");
      setSourceOptions(sourcesResp.data.items);
      setSourceState(sourcesResp.data.defaultSource);
      await refreshFilesForSource(sourcesResp.data.defaultSource, true, "");
      setLoading(false);
    };

    void bootstrap();
    return () => {
      disposed = true;
    };
  }, [mode, refreshFilesForSource, setFailure]);

  useEffect(() => {
    if (mode !== "live" || !hasLibrary) {
      return;
    }
    if (!selectedLogId) {
      setEvents([]);
      setTotal(0);
      setAnalysis(emptyAnalysis(source));
      return;
    }

    let disposed = false;

    const loadData = async () => {
      const query = {
        source,
        log_id: selectedLogId,
        page,
        page_size: pageSize,
        q: debouncedKeyword,
        level: filters.level,
        event: filters.event,
        fromTs: filters.fromTs,
        toTs: filters.toTs,
      };
      const [eventsResp, analysisResp] = await Promise.all([
        getLogEvents(query),
        getLogAnalysis(query),
      ]);
      if (disposed) {
        return;
      }

      if (!eventsResp.ok || !eventsResp.data) {
        if (eventsResp.error?.code === "LOG_NOT_FOUND") {
          await refreshFilesForSource(source, true, "");
          return;
        }
        setFailure(eventsResp.error?.message ?? "Failed to load log events.");
        setEvents([]);
        setTotal(0);
      } else {
        setEvents(eventsResp.data.items);
        setTotal(eventsResp.data.total);
      }

      if (!analysisResp.ok || !analysisResp.data) {
        setFailure(analysisResp.error?.message ?? "Failed to load log analysis.");
      } else {
        setAnalysis(analysisResp.data);
      }
    };

    void loadData();
    return () => {
      disposed = true;
    };
  }, [
    mode,
    hasLibrary,
    source,
    selectedLogId,
    page,
    pageSize,
    debouncedKeyword,
    filters.level,
    filters.event,
    filters.fromTs,
    filters.toTs,
    refreshFilesForSource,
    setFailure,
  ]);

  const setSource = useCallback(
    (value: LogSource) => {
      setSourceState(value);
      setFilters({ q: "", level: "", event: "", fromTs: null, toTs: null });
      setSelectedLogId("");
      setPageState(1);
      setSelectedEventLineNo(null);
      setDetailOpen(false);
      if (mode === "visual") {
        const visualFiles = fixture.files.filter((item) => item.source === value);
        const fallbackFiles = visualFiles.length > 0 ? visualFiles : fixture.files;
        setFiles(fallbackFiles);
        setSelectedLogId(fallbackFiles[0]?.logId ?? "");
        setAnalysis({ ...fixture.analysis, source: value });
      } else {
        void refreshFilesForSource(value, true, "");
      }
    },
    [fixture.analysis, fixture.files, mode, refreshFilesForSource],
  );

  const refreshFiles = useCallback(async () => {
    if (mode === "visual") {
      setToast({ tone: "success", message: "Log files refreshed." });
      return;
    }
    await refreshFilesForSource(source, false, selectedLogId);
    setToast({ tone: "success", message: "Log files refreshed." });
  }, [mode, refreshFilesForSource, selectedLogId, source]);

  const loadLatest = useCallback(async () => {
    if (mode === "visual") {
      const first = files[0];
      if (first) {
        setSelectedLogId(first.logId);
      }
      setToast({ tone: "success", message: "Latest log loaded." });
      return;
    }
    const latestResp = await getLatestLog(source);
    if (!latestResp.ok || !latestResp.data) {
      setFailure(latestResp.error?.message ?? "Failed to load latest log.");
      return;
    }
    setSelectedLogId(latestResp.data.item?.logId ?? "");
    setPageState(1);
    setToast({ tone: "success", message: "Latest log loaded." });
  }, [files, mode, setFailure, source]);

  const setKeyword = useCallback((value: string) => {
    setFilters((prev) => ({ ...prev, q: value }));
    setPageState(1);
  }, []);

  const setLevel = useCallback((value: string) => {
    setFilters((prev) => ({ ...prev, level: value }));
    setPageState(1);
  }, []);

  const setEvent = useCallback((value: string) => {
    setFilters((prev) => ({ ...prev, event: value }));
    setPageState(1);
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({ q: "", level: "", event: "", fromTs: null, toTs: null });
    setPageState(1);
  }, []);

  const setPage = useCallback((nextPage: number) => {
    setPageState(Math.max(1, nextPage));
  }, []);

  const selectFile = useCallback((logId: string) => {
    setSelectedLogId(logId);
    setPageState(1);
    setSelectedEventLineNo(null);
    setDetailOpen(false);
  }, []);

  const selectEvent = useCallback((lineNo: number) => {
    setSelectedEventLineNo(lineNo);
  }, []);

  const openEventDetail = useCallback((lineNo: number) => {
    setSelectedEventLineNo(lineNo);
    setDetailOpen(true);
  }, []);

  const closeDetailDrawer = useCallback(() => {
    setDetailOpen(false);
  }, []);

  return {
    mode,
    scene,
    loading,
    canInteract: !loading && hasLibrary,
    hasLibrary,
    errorMessage,
    toast,
    sourceOptions,
    source,
    files,
    selectedLogId,
    selectedFile,
    leftPaneCollapsed,
    analysis,
    filters,
    events,
    page,
    pageSize,
    total,
    selectedEventLineNo,
    detailOpen,
    detailEvent,
    levelOptions,
    eventOptions,
    setSource,
    refreshFiles,
    loadLatest,
    setKeyword,
    setLevel,
    setEvent,
    clearFilters,
    setPage,
    selectFile,
    selectEvent,
    openEventDetail,
    closeDetailDrawer,
    toggleLeftPane: () => setLeftPaneCollapsed((prev) => !prev),
  };
}
