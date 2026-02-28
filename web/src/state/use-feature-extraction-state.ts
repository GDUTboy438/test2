import { useCallback, useEffect, useMemo, useState } from "react";
import { getFeatureExtractionFixture } from "../design/feature-extraction-fixtures";
import {
  getFeatureModels,
  getFeatureTaskStatus,
  getFeatureThresholds,
  importFeatureModelDirectory,
  openFeatureModelPath,
  selectFeatureModelRoot,
  startFeatureExtraction,
  stopFeatureExtraction,
} from "../services/feature-extraction-api";
import type {
  ApiFeatureModelItem,
  ApiFeatureTaskData,
  ApiFeatureThresholdsData,
} from "../types/api";
import type { ToastState, UiMode } from "../types/domain";

type FeatureModel = {
  id: string;
  type: "embedding" | "reranker";
  name: string;
  source: "preset" | "custom";
  downloaded: boolean;
  downloadStatus: "downloaded" | "missing";
  localPath: string;
  downloadUrl: string;
  repoId: string;
  selectValue: string;
  selected: boolean;
};

type FeatureTaskResult = {
  status: string;
  processedVideos: number;
  selectedTerms: number;
  taggedVideos: number;
  createdRelations: number;
  pendingCandidateTerms: number;
  fallbackReason: string;
  topTerms: string[];
};

type FeatureTask = {
  status: "idle" | "running" | "stopping" | "completed" | "cancelled" | "failed";
  phase: string;
  message: string;
  progressPercent: number;
  strategy: "auto" | "rule" | "model";
  scope: "all" | "new_only";
  embeddingModel: string;
  rerankerModel: string;
  minDf: number;
  maxTagsPerVideo: number;
  maxTerms: number;
  recallTopK: number;
  recallMinScore: number;
  autoApply: number;
  pendingReview: number;
  dependencyStatus: string;
  dependencyMessage: string;
  runningLockModelSwitch: boolean;
  result: FeatureTaskResult;
};

type FeatureState = {
  mode: UiMode;
  loading: boolean;
  canInteract: boolean;
  hasLibrary: boolean;
  errorMessage: string;
  toast: ToastState | null;
  modelRoot: string;
  modelTypeFilter: "all" | "embedding" | "reranker";
  searchKeyword: string;
  advancedExpanded: boolean;
  task: FeatureTask;
  models: FeatureModel[];
  filteredModels: FeatureModel[];
  embeddingOptions: FeatureModel[];
  rerankerOptions: FeatureModel[];
  setModelTypeFilter: (value: "all" | "embedding" | "reranker") => void;
  setSearchKeyword: (value: string) => void;
  setStrategy: (value: "auto" | "rule" | "model") => void;
  setScope: (value: "all" | "new_only") => void;
  setEmbeddingModel: (value: string) => void;
  setRerankerModel: (value: string) => void;
  stepMinDf: (delta: number) => void;
  stepMaxTagsPerVideo: (delta: number) => void;
  stepMaxTerms: (delta: number) => void;
  stepRecallTopK: (delta: number) => void;
  stepRecallMinScore: (delta: number) => void;
  setAutoApply: (value: "true" | "false") => void;
  setPendingReview: (value: "true" | "false") => void;
  toggleAdvanced: () => void;
  startTask: () => Promise<void>;
  stopTask: () => Promise<void>;
  refreshModels: () => Promise<void>;
  chooseModelRoot: () => Promise<void>;
  importModelDirectory: () => Promise<void>;
  openModelPath: (path: string) => Promise<void>;
  clearToast: () => void;
};

function readMode(): UiMode {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("mode");
  return mode === "visual" && params.has("scene") ? "visual" : "live";
}

function clampInt(value: number, min: number, max = Number.MAX_SAFE_INTEGER): number {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, Math.round(value)));
}

function clampUnit(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return Number(value.toFixed(2));
}

function toModel(item: ApiFeatureModelItem): FeatureModel {
  return {
    id: String(item.id ?? ""),
    type: item.type === "reranker" ? "reranker" : "embedding",
    name: String(item.name ?? ""),
    source: item.source === "custom" ? "custom" : "preset",
    downloaded: Boolean(item.downloaded),
    downloadStatus: item.download_status === "missing" ? "missing" : "downloaded",
    localPath: String(item.local_path ?? ""),
    downloadUrl: String(item.download_url ?? ""),
    repoId: String(item.repo_id ?? ""),
    selectValue: String(item.select_value ?? ""),
    selected: Boolean(item.selected),
  };
}

function toTaskResult(data: ApiFeatureTaskData): FeatureTaskResult {
  return {
    status: String(data.result?.status ?? data.status ?? "idle"),
    processedVideos: Number(data.result?.processed_videos ?? 0),
    selectedTerms: Number(data.result?.selected_terms ?? 0),
    taggedVideos: Number(data.result?.tagged_videos ?? 0),
    createdRelations: Number(data.result?.created_relations ?? 0),
    pendingCandidateTerms: Number(data.result?.pending_candidate_terms ?? 0),
    fallbackReason: String(data.result?.fallback_reason ?? data.fallback_reason ?? ""),
    topTerms: Array.isArray(data.result?.top_terms) ? data.result.top_terms.map((item) => String(item)) : [],
  };
}

function toTask(data: ApiFeatureTaskData): FeatureTask {
  return {
    status:
      data.status === "running" ||
      data.status === "stopping" ||
      data.status === "completed" ||
      data.status === "cancelled" ||
      data.status === "failed"
        ? data.status
        : "idle",
    phase: String(data.phase ?? "idle"),
    message: String(data.message ?? ""),
    progressPercent: clampInt(Number(data.progress_percent ?? 0), 0, 100),
    strategy: data.strategy === "rule" || data.strategy === "model" ? data.strategy : "auto",
    scope: data.scope === "all" ? "all" : "new_only",
    embeddingModel: String(data.embedding_model ?? ""),
    rerankerModel: String(data.reranker_model ?? ""),
    minDf: clampInt(Number(data.min_df ?? 2), 1),
    maxTagsPerVideo: clampInt(Number(data.max_tags_per_video ?? 8), 1),
    maxTerms: clampInt(Number(data.max_terms ?? 400), 1),
    recallTopK: clampInt(Number(data.recall_top_k ?? 12), 1),
    recallMinScore: clampUnit(Number(data.recall_min_score ?? 0.45)),
    autoApply: clampUnit(Number(data.auto_apply ?? 0.8)),
    pendingReview: clampUnit(Number(data.pending_review ?? 0.6)),
    dependencyStatus: String(data.dependency_status ?? ""),
    dependencyMessage: String(data.dependency_message ?? ""),
    runningLockModelSwitch: Boolean(data.running_lock_model_switch),
    result: toTaskResult(data),
  };
}

function createIdleTask(thresholds: ApiFeatureThresholdsData | null): FeatureTask {
  return {
    status: "idle",
    phase: "idle",
    message: "等待执行",
    progressPercent: 0,
    strategy: "auto",
    scope: "new_only",
    embeddingModel: "",
    rerankerModel: "",
    minDf: 2,
    maxTagsPerVideo: 8,
    maxTerms: 400,
    recallTopK: clampInt(Number(thresholds?.recall_top_k ?? 12), 1),
    recallMinScore: clampUnit(Number(thresholds?.recall_min_score ?? 0.45)),
    autoApply: clampUnit(Number(thresholds?.auto_apply ?? 0.8)),
    pendingReview: clampUnit(Number(thresholds?.pending_review ?? 0.6)),
    dependencyStatus: "",
    dependencyMessage: "",
    runningLockModelSwitch: false,
    result: {
      status: "idle",
      processedVideos: 0,
      selectedTerms: 0,
      taggedVideos: 0,
      createdRelations: 0,
      pendingCandidateTerms: 0,
      fallbackReason: "",
      topTerms: [],
    },
  };
}

export function useFeatureExtractionState(): FeatureState {
  const mode = readMode();
  const fixture = useMemo(() => getFeatureExtractionFixture(), []);

  const [loading, setLoading] = useState(mode === "live");
  const [hasLibrary, setHasLibrary] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [toast, setToast] = useState<ToastState | null>(null);
  const [modelRoot, setModelRoot] = useState(mode === "visual" ? fixture.modelRoot : "");
  const [models, setModels] = useState<FeatureModel[]>(
    mode === "visual"
      ? fixture.models.map((item) => ({
          ...item,
          downloadStatus: item.downloadStatus,
        }))
      : [],
  );
  const [task, setTask] = useState<FeatureTask>(
    mode === "visual"
      ? {
          ...fixture.task,
          status: fixture.task.status,
        }
      : createIdleTask(null),
  );
  const [modelTypeFilter, setModelTypeFilter] = useState<"all" | "embedding" | "reranker">("all");
  const [searchKeyword, setSearchKeyword] = useState("");
  const [advancedExpanded, setAdvancedExpanded] = useState(false);

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

  const syncSelectionFromModels = useCallback((nextTask: FeatureTask, nextModels: FeatureModel[]) => {
    const defaultEmbedding =
      nextModels.find((item) => item.type === "embedding" && item.downloaded && item.selected) ??
      nextModels.find((item) => item.type === "embedding" && item.downloaded);
    const defaultReranker =
      nextModels.find((item) => item.type === "reranker" && item.downloaded && item.selected) ??
      nextModels.find((item) => item.type === "reranker" && item.downloaded);
    return {
      ...nextTask,
      embeddingModel: nextTask.embeddingModel || defaultEmbedding?.selectValue || "",
      rerankerModel: nextTask.rerankerModel || defaultReranker?.selectValue || "",
    };
  }, []);

  const bootstrapLive = useCallback(async () => {
    if (mode !== "live") {
      return;
    }
    setLoading(true);

    const [modelsResp, thresholdsResp, statusResp] = await Promise.all([
      getFeatureModels(),
      getFeatureThresholds(),
      getFeatureTaskStatus(),
    ]);

    if (!modelsResp.ok || !modelsResp.data) {
      setLoading(false);
      setFailure(modelsResp.error?.message ?? "加载模型列表失败。");
      return;
    }

    const nextModels = (modelsResp.data.items ?? []).map(toModel);
    setModelRoot(String(modelsResp.data.model_root ?? ""));
    setModels(nextModels);

    let nextTask = createIdleTask(thresholdsResp.ok && thresholdsResp.data ? thresholdsResp.data : null);
    if (statusResp.ok && statusResp.data) {
      nextTask = toTask(statusResp.data);
      setHasLibrary(true);
      setErrorMessage("");
    } else if (statusResp.error?.code === "NO_LIBRARY") {
      setHasLibrary(false);
      setErrorMessage("未选择资源库，请先返回首页选择资源库。");
    } else if (!statusResp.ok) {
      setFailure(statusResp.error?.message ?? "加载任务状态失败。");
    }

    setTask(syncSelectionFromModels(nextTask, nextModels));
    setLoading(false);
  }, [mode, setFailure, syncSelectionFromModels]);

  useEffect(() => {
    if (mode === "visual") {
      return;
    }
    void bootstrapLive();
  }, [bootstrapLive, mode]);

  useEffect(() => {
    if (mode !== "live") {
      return;
    }
    if (!(task.status === "running" || task.status === "stopping")) {
      return;
    }
    const timer = window.setInterval(async () => {
      const response = await getFeatureTaskStatus();
      const taskData = response.data;
      if (!response.ok || !taskData) {
        return;
      }
      setTask((prev) => ({
        ...prev,
        ...toTask(taskData),
      }));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [mode, task.status]);

  const filteredModels = useMemo(() => {
    const query = searchKeyword.trim().toLowerCase();
    return models.filter((item) => {
      if (modelTypeFilter !== "all" && item.type !== modelTypeFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        item.name.toLowerCase().includes(query) ||
        item.localPath.toLowerCase().includes(query) ||
        item.downloadUrl.toLowerCase().includes(query)
      );
    });
  }, [modelTypeFilter, models, searchKeyword]);

  const embeddingOptions = useMemo(
    () => models.filter((item) => item.type === "embedding" && item.downloaded),
    [models],
  );

  const rerankerOptions = useMemo(
    () => models.filter((item) => item.type === "reranker" && item.downloaded),
    [models],
  );

  const refreshModels = useCallback(async () => {
    if (mode === "visual") {
      setToast({ tone: "success", message: "模型列表已刷新。" });
      return;
    }
    const response = await getFeatureModels();
    if (!response.ok || !response.data) {
      setFailure(response.error?.message ?? "刷新模型列表失败。");
      return;
    }
    const nextModels = (response.data.items ?? []).map(toModel);
    setModelRoot(String(response.data.model_root ?? ""));
    setModels(nextModels);
    setTask((prev) => syncSelectionFromModels(prev, nextModels));
    setToast({ tone: "success", message: "模型列表已刷新。" });
  }, [mode, setFailure, syncSelectionFromModels]);

  const chooseModelRoot = useCallback(async () => {
    if (mode === "visual") {
      setToast({ tone: "success", message: "已打开模型目录选择器。" });
      return;
    }
    const response = await selectFeatureModelRoot("");
    if (!response.ok || !response.data) {
      if (response.error?.code === "CANCELLED") {
        return;
      }
      setFailure(response.error?.message ?? "选择模型目录失败。");
      return;
    }
    const nextModels = (response.data.items ?? []).map(toModel);
    setModelRoot(String(response.data.model_root ?? ""));
    setModels(nextModels);
    setTask((prev) => syncSelectionFromModels(prev, nextModels));
    setToast({ tone: "success", message: "模型目录已更新。" });
  }, [mode, setFailure, syncSelectionFromModels]);

  const importModelDirectory = useCallback(async () => {
    if (mode === "visual") {
      setToast({ tone: "success", message: "已导入模型目录。" });
      return;
    }
    const response = await importFeatureModelDirectory("");
    if (!response.ok || !response.data) {
      if (response.error?.code === "CANCELLED") {
        return;
      }
      setFailure(response.error?.message ?? "导入目录失败。");
      return;
    }
    const nextModels = (response.data.items ?? []).map(toModel);
    setModelRoot(String(response.data.model_root ?? ""));
    setModels(nextModels);
    setTask((prev) => syncSelectionFromModels(prev, nextModels));
    setToast({ tone: "success", message: "模型目录已导入。" });
  }, [mode, setFailure, syncSelectionFromModels]);

  const openModelPath = useCallback(
    async (path: string) => {
      if (!path) {
        return;
      }
      if (mode === "visual") {
        setToast({ tone: "success", message: "已打开本地路径。" });
        return;
      }
      const response = await openFeatureModelPath(path);
      if (!response.ok) {
        setFailure(response.error?.message ?? "打开路径失败。");
        return;
      }
      setToast({ tone: "success", message: "已打开本地路径。" });
    },
    [mode, setFailure],
  );

  const setStrategy = useCallback((value: "auto" | "rule" | "model") => {
    setTask((prev) => ({ ...prev, strategy: value }));
  }, []);

  const setScope = useCallback((value: "all" | "new_only") => {
    setTask((prev) => ({ ...prev, scope: value }));
  }, []);

  const setEmbeddingModel = useCallback((value: string) => {
    setTask((prev) => ({ ...prev, embeddingModel: value }));
  }, []);

  const setRerankerModel = useCallback((value: string) => {
    setTask((prev) => ({ ...prev, rerankerModel: value }));
  }, []);

  const stepMinDf = useCallback((delta: number) => {
    setTask((prev) => ({ ...prev, minDf: clampInt(prev.minDf + delta, 1) }));
  }, []);

  const stepMaxTagsPerVideo = useCallback((delta: number) => {
    setTask((prev) => ({ ...prev, maxTagsPerVideo: clampInt(prev.maxTagsPerVideo + delta, 1) }));
  }, []);

  const stepMaxTerms = useCallback((delta: number) => {
    setTask((prev) => ({ ...prev, maxTerms: clampInt(prev.maxTerms + delta, 1) }));
  }, []);

  const stepRecallTopK = useCallback((delta: number) => {
    setTask((prev) => ({ ...prev, recallTopK: clampInt(prev.recallTopK + delta, 1) }));
  }, []);

  const stepRecallMinScore = useCallback((delta: number) => {
    setTask((prev) => ({ ...prev, recallMinScore: clampUnit(prev.recallMinScore + delta * 0.01) }));
  }, []);

  const setAutoApply = useCallback((value: "true" | "false") => {
    setTask((prev) => ({ ...prev, autoApply: value === "true" ? 1 : 0 }));
  }, []);

  const setPendingReview = useCallback((value: "true" | "false") => {
    setTask((prev) => ({ ...prev, pendingReview: value === "true" ? 1 : 0 }));
  }, []);

  const startTask = useCallback(async () => {
    if (mode === "visual") {
      setTask((prev) => ({
        ...prev,
        status: "running",
        phase: "model_loading",
        message: "正在检查模型与依赖...",
        runningLockModelSwitch: true,
      }));
      return;
    }
    const response = await startFeatureExtraction({
      strategy: task.strategy,
      scope: task.scope,
      embedding_model: task.embeddingModel,
      reranker_model: task.rerankerModel,
      min_df: task.minDf,
      max_tags_per_video: task.maxTagsPerVideo,
      max_terms: task.maxTerms,
      recall_top_k: task.recallTopK,
      recall_min_score: task.recallMinScore,
      auto_apply: task.autoApply,
      pending_review: task.pendingReview,
    });
    const started = response.data;
    if (!response.ok || !started || !started.task) {
      setFailure(response.error?.message ?? "启动提取任务失败。");
      return;
    }
    setTask(toTask(started.task));
    setHasLibrary(true);
    setErrorMessage("");
    setToast({ tone: "success", message: "提取任务已启动。" });
  }, [mode, setFailure, task]);

  const stopTask = useCallback(async () => {
    if (mode === "visual") {
      setTask((prev) => ({
        ...prev,
        status: "stopping",
        message: "正在请求停止...",
      }));
      return;
    }
    const response = await stopFeatureExtraction();
    if (!response.ok) {
      setFailure(response.error?.message ?? "停止任务失败。");
      return;
    }
    setTask((prev) => ({
      ...prev,
      status: "stopping",
      message: "正在请求停止...",
      runningLockModelSwitch: true,
    }));
    setToast({ tone: "success", message: "已发送停止请求。" });
  }, [mode, setFailure]);

  return {
    mode,
    loading,
    canInteract: !loading && hasLibrary,
    hasLibrary,
    errorMessage,
    toast,
    modelRoot,
    modelTypeFilter,
    searchKeyword,
    advancedExpanded,
    task,
    models,
    filteredModels,
    embeddingOptions,
    rerankerOptions,
    setModelTypeFilter,
    setSearchKeyword,
    setStrategy,
    setScope,
    setEmbeddingModel,
    setRerankerModel,
    stepMinDf,
    stepMaxTagsPerVideo,
    stepMaxTerms,
    stepRecallTopK,
    stepRecallMinScore,
    setAutoApply,
    setPendingReview,
    toggleAdvanced: () => setAdvancedExpanded((prev) => !prev),
    startTask,
    stopTask,
    refreshModels,
    chooseModelRoot,
    importModelDirectory,
    openModelPath,
    clearToast: () => setToast(null),
  };
}


