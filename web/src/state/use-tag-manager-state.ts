import { useCallback, useEffect, useMemo, useState } from "react";
import { getTagManagerFixture } from "../design/tag-manager-fixtures";
import {
  approveTagCandidates,
  blacklistTagCandidates,
  clearPendingTagCandidates,
  createTagLibrary,
  deleteTagLibrary,
  getApiRuntimeInfo,
  getTagBlacklist,
  getTagCandidates,
  getTagLibrary,
  rejectTagCandidates,
  requeueTagCandidates,
} from "../services/tag-manager-api";
import type { ApiError } from "../types/api";
import type {
  TagBlacklistItem,
  TagCandidateItem,
  TagLibraryItem,
  TagSection,
  TagSource,
  ToastState,
  UiMode,
} from "../types/domain";

function readMode(): UiMode {
  const mode = new URLSearchParams(window.location.search).get("mode");
  return mode === "visual" ? "visual" : "live";
}

function normalize(text: string): string {
  return String(text || "").trim().toLowerCase();
}

function parseNames(raw: string): string[] {
  return raw
    .split(/[\n,，]/g)
    .map((item) => item.trim())
    .filter((item, index, arr) => item.length > 0 && arr.indexOf(item) === index);
}

function explainTagLoadError(
  error: ApiError | null,
  fallback: string,
): string {
  const code = String(error?.code ?? "");
  const message = String(error?.message ?? "");
  if (code === "API_CONTRACT_MISMATCH") {
    return message || "当前后端不是最新标签 API，请重启 main.py。";
  }
  if (code === "NO_LIBRARY") {
    return "未选择资源库，请先在主页选择 Library。";
  }
  if (code === "BAD_RESPONSE") {
    return "API 返回格式异常，请检查后端日志。";
  }
  if (code === "NETWORK_ERROR") {
    return "无法连接后端 API，请确认 main.py 正在运行。";
  }
  if (code === "HTTP_404" && message.includes("/api/tags/")) {
    return "后端缺少标签路由（旧版本实例），请重启 main.py。";
  }
  if (message) {
    return message;
  }
  return fallback;
}

export type TagManagerState = {
  mode: UiMode;
  scene: "J7vS3";
  loading: boolean;
  canInteract: boolean;
  errorMessage: string;
  toast: ToastState | null;
  searchInput: string;
  source: TagSource;
  activeSection: TagSection | null;
  showUnified: boolean;
  globalMatchCount: number;
  tagLibrary: TagLibraryItem[];
  candidates: TagCandidateItem[];
  blacklist: TagBlacklistItem[];
  visibleTagLibrary: TagLibraryItem[];
  visibleCandidates: TagCandidateItem[];
  visibleBlacklist: TagBlacklistItem[];
  selectedTagIds: number[];
  selectedCandidateIds: number[];
  selectedBlacklistIds: number[];
  setSearchInput: (value: string) => void;
  setSource: (value: TagSource) => void;
  setActiveSection: (value: TagSection) => void;
  toggleTagSelection: (id: number) => void;
  toggleCandidateSelection: (id: number) => void;
  toggleBlacklistSelection: (id: number) => void;
  selectAllTags: () => void;
  addTags: () => Promise<void>;
  deleteTagById: (id: number) => Promise<void>;
  deleteSelectedTags: () => Promise<void>;
  approveSelectedCandidates: () => Promise<void>;
  rejectSelectedCandidates: () => Promise<void>;
  blacklistSelectedCandidates: () => Promise<void>;
  requeueSelectedCandidates: () => Promise<void>;
  clearPendingCandidates: () => Promise<void>;
  clearToast: () => void;
};

export function useTagManagerState(): TagManagerState {
  const mode = readMode();
  const fixture = useMemo(() => getTagManagerFixture(), []);

  const [loading, setLoading] = useState(mode === "live");
  const [errorMessage, setErrorMessage] = useState("");
  const [toast, setToast] = useState<ToastState | null>(null);
  const [searchInput, setSearchInput] = useState(fixture.searchInput);
  const [source, setSource] = useState<TagSource>(fixture.source);
  const [activeSection, setActiveSectionState] = useState<TagSection | null>(fixture.activeSection);

  const [tagLibrary, setTagLibrary] = useState<TagLibraryItem[]>(
    mode === "visual" ? fixture.tagLibrary : [],
  );
  const [candidates, setCandidates] = useState<TagCandidateItem[]>(
    mode === "visual" ? fixture.candidates : [],
  );
  const [blacklist, setBlacklist] = useState<TagBlacklistItem[]>(
    mode === "visual" ? fixture.blacklist : [],
  );

  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<number[]>([]);
  const [selectedBlacklistIds, setSelectedBlacklistIds] = useState<number[]>([]);

  const setActiveSection = useCallback((value: TagSection) => {
    setActiveSectionState((prev) => (prev === value ? null : value));
  }, []);

  const setFailure = useCallback((message: string) => {
    setErrorMessage(message);
    setToast({ tone: "error", message });
  }, []);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const refreshAll = useCallback(async () => {
    if (mode !== "live") {
      return;
    }

    setLoading(true);

    const runtimeResp = await getApiRuntimeInfo();
    if (runtimeResp.ok && runtimeResp.data && !runtimeResp.data.hasTagRoutes) {
      const missing = runtimeResp.data.missingTagRoutes.join(", ");
      const contractError: ApiError = {
        code: "API_CONTRACT_MISMATCH",
        message: `当前后端不是最新标签 API，请重启 main.py（缺少路由：${missing || "unknown"}）。`,
      };
      setLoading(false);
      setTagLibrary([]);
      setCandidates([]);
      setBlacklist([]);
      setFailure(explainTagLoadError(contractError, "加载标签库失败。"));
      return;
    }

    const [libraryResp, candidatesResp, blacklistResp] = await Promise.all([
      getTagLibrary(),
      getTagCandidates(),
      getTagBlacklist(),
    ]);

    if (!libraryResp.ok || !libraryResp.data) {
      setLoading(false);
      setTagLibrary([]);
      setCandidates([]);
      setBlacklist([]);
      setFailure(explainTagLoadError(libraryResp.error, "加载标签库失败。"));
      return;
    }
    if (!candidatesResp.ok || !candidatesResp.data) {
      setLoading(false);
      setTagLibrary(libraryResp.data);
      setCandidates([]);
      setBlacklist([]);
      setFailure(explainTagLoadError(candidatesResp.error, "加载候选标签失败。"));
      return;
    }
    if (!blacklistResp.ok || !blacklistResp.data) {
      setLoading(false);
      setTagLibrary(libraryResp.data);
      setCandidates(candidatesResp.data);
      setBlacklist([]);
      setFailure(explainTagLoadError(blacklistResp.error, "加载黑名单失败。"));
      return;
    }

    setErrorMessage("");
    setTagLibrary(libraryResp.data);
    setCandidates(candidatesResp.data);
    setBlacklist(blacklistResp.data);
    setLoading(false);
  }, [mode, setFailure]);

  useEffect(() => {
    if (mode !== "live") {
      return;
    }
    void refreshAll();
  }, [mode, refreshAll]);

  const searchKey = normalize(searchInput);
  const showUnified = searchKey.length > 0;

  const matchedTagLibrary = useMemo(
    () => tagLibrary.filter((item) => normalize(item.name).includes(searchKey)),
    [searchKey, tagLibrary],
  );

  const matchedCandidates = useMemo(
    () => candidates.filter((item) => normalize(item.name).includes(searchKey)),
    [candidates, searchKey],
  );

  const matchedBlacklist = useMemo(
    () => blacklist.filter((item) => normalize(item.term).includes(searchKey)),
    [blacklist, searchKey],
  );

  const visibleTagLibrary = useMemo(() => {
    if (!showUnified) {
      return tagLibrary;
    }
    if (source !== "all" && source !== "tag_library") {
      return [];
    }
    return matchedTagLibrary;
  }, [matchedTagLibrary, showUnified, source, tagLibrary]);

  const visibleCandidates = useMemo(() => {
    if (!showUnified) {
      return candidates;
    }
    if (source !== "all" && source !== "candidate_library") {
      return [];
    }
    return matchedCandidates;
  }, [candidates, matchedCandidates, showUnified, source]);

  const visibleBlacklist = useMemo(() => {
    if (!showUnified) {
      return blacklist;
    }
    if (source !== "all" && source !== "blacklist") {
      return [];
    }
    return matchedBlacklist;
  }, [blacklist, matchedBlacklist, showUnified, source]);

  const globalMatchCount = visibleTagLibrary.length + visibleCandidates.length + visibleBlacklist.length;

  const toggleSelection = (current: number[], id: number): number[] => {
    if (current.includes(id)) {
      return current.filter((value) => value !== id);
    }
    return [...current, id];
  };

  const toggleTagSelection = useCallback((id: number) => {
    setSelectedTagIds((prev) => toggleSelection(prev, id));
  }, []);

  const toggleCandidateSelection = useCallback((id: number) => {
    setSelectedCandidateIds((prev) => toggleSelection(prev, id));
  }, []);

  const toggleBlacklistSelection = useCallback((id: number) => {
    setSelectedBlacklistIds((prev) => toggleSelection(prev, id));
  }, []);

  const selectAllTags = useCallback(() => {
    setSelectedTagIds(tagLibrary.map((item) => item.id));
  }, [tagLibrary]);

  const addTags = useCallback(async () => {
    const raw = window.prompt("请输入标签名称，多个标签可用逗号分隔：", "");
    if (!raw) {
      return;
    }

    const names = parseNames(raw);
    if (names.length === 0) {
      setFailure("没有可创建的标签名称。");
      return;
    }

    if (mode === "visual") {
      setTagLibrary((prev) => {
        let nextId = prev.reduce((max, item) => Math.max(max, item.id), 0) + 1;
        const existing = new Set(prev.map((item) => item.name.toLowerCase()));
        const created = names
          .filter((name) => !existing.has(name.toLowerCase()))
          .map((name) => ({
            id: nextId++,
            name,
            usageCount: 0,
            manualUsageCount: 0,
            aiUsageCount: 0,
          }));
        return [...prev, ...created];
      });
      setToast({ tone: "success", message: "已新增标签。" });
      return;
    }

    const response = await createTagLibrary({ names });
    if (!response.ok || !response.data) {
      setFailure(response.error?.message ?? "新增标签失败。");
      return;
    }

    await refreshAll();
    setToast({ tone: "success", message: `已新增 ${response.data.created} 个标签。` });
  }, [mode, refreshAll, setFailure]);

  const deleteSelectedTags = useCallback(async () => {
    if (selectedTagIds.length === 0) {
      return;
    }

    if (mode === "visual") {
      const selected = new Set(selectedTagIds);
      setTagLibrary((prev) => prev.filter((item) => !selected.has(item.id)));
      setSelectedTagIds([]);
      setToast({ tone: "success", message: "已删除所选标签。" });
      return;
    }

    const response = await deleteTagLibrary({ ids: selectedTagIds });
    if (!response.ok || !response.data) {
      setFailure(response.error?.message ?? "批量删除失败。");
      return;
    }

    setSelectedTagIds([]);
    await refreshAll();
    setToast({ tone: "success", message: `已删除 ${response.data.removed} 个标签。` });
  }, [mode, refreshAll, selectedTagIds, setFailure]);

  const deleteTagById = useCallback(async (id: number) => {
    if (id <= 0) {
      return;
    }

    if (mode === "visual") {
      setTagLibrary((prev) => prev.filter((item) => item.id !== id));
      setSelectedTagIds((prev) => prev.filter((value) => value !== id));
      setToast({ tone: "success", message: "标签已删除。" });
      return;
    }

    const response = await deleteTagLibrary({ ids: [id] });
    if (!response.ok || !response.data) {
      setFailure(response.error?.message ?? "删除标签失败。");
      return;
    }

    setSelectedTagIds((prev) => prev.filter((value) => value !== id));
    await refreshAll();
    setToast({ tone: "success", message: "标签已删除。" });
  }, [mode, refreshAll, setFailure]);

  const approveSelectedCandidates = useCallback(async () => {
    if (selectedCandidateIds.length === 0) {
      return;
    }

    if (mode === "visual") {
      const selected = new Set(selectedCandidateIds);
      setCandidates((prev) => prev.map((item) => (
        selected.has(item.id) ? { ...item, status: "approved" } : item
      )));
      setSelectedCandidateIds([]);
      setToast({ tone: "success", message: "候选标签已审批。" });
      return;
    }

    const response = await approveTagCandidates({ ids: selectedCandidateIds });
    if (!response.ok || !response.data) {
      setFailure(response.error?.message ?? "审批失败。");
      return;
    }

    setSelectedCandidateIds([]);
    await refreshAll();
    setToast({ tone: "success", message: `已审批 ${response.data.approved_candidates} 条候选。` });
  }, [mode, refreshAll, selectedCandidateIds, setFailure]);

  const rejectSelectedCandidates = useCallback(async () => {
    if (selectedCandidateIds.length === 0) {
      return;
    }

    if (mode === "visual") {
      const selected = new Set(selectedCandidateIds);
      setCandidates((prev) => prev.filter((item) => !selected.has(item.id)));
      setSelectedCandidateIds([]);
      setToast({ tone: "success", message: "候选标签已拒绝。" });
      return;
    }

    const response = await rejectTagCandidates({ ids: selectedCandidateIds });
    if (!response.ok || !response.data) {
      setFailure(response.error?.message ?? "拒绝失败。");
      return;
    }

    setSelectedCandidateIds([]);
    await refreshAll();
    setToast({ tone: "success", message: `已拒绝 ${response.data.rejected} 条候选。` });
  }, [mode, refreshAll, selectedCandidateIds, setFailure]);

  const blacklistSelectedCandidates = useCallback(async () => {
    if (selectedCandidateIds.length === 0) {
      return;
    }

    if (mode === "visual") {
      const selected = new Set(selectedCandidateIds);
      const termsToAdd: string[] = [];
      setCandidates((prev) => prev.map((item) => {
        if (!selected.has(item.id)) {
          return item;
        }
        termsToAdd.push(item.name.replace(/…/g, ""));
        return { ...item, status: "blacklisted" };
      }));
      setBlacklist((prev) => {
        let nextId = prev.reduce((max, item) => Math.max(max, item.id), 0) + 1;
        const existing = new Set(prev.map((item) => item.term));
        const added = termsToAdd
          .filter((term) => !existing.has(term))
          .map((term) => ({
            id: nextId++,
            term,
            source: "auto",
            reason: "候选拉黑",
            hitCount: 1,
            firstSeenEpoch: Math.floor(Date.now() / 1000),
            lastSeenEpoch: Math.floor(Date.now() / 1000),
          }));
        return [...added, ...prev];
      });
      setSelectedCandidateIds([]);
      setToast({ tone: "success", message: "候选标签已拉黑。" });
      return;
    }

    const response = await blacklistTagCandidates({ ids: selectedCandidateIds });
    if (!response.ok || !response.data) {
      setFailure(response.error?.message ?? "拉黑失败。");
      return;
    }

    setSelectedCandidateIds([]);
    await refreshAll();
    setToast({
      tone: "success",
      message: `已拉黑 ${response.data.blacklisted_candidates} 条候选。`,
    });
  }, [mode, refreshAll, selectedCandidateIds, setFailure]);

  const requeueSelectedCandidates = useCallback(async () => {
    if (selectedCandidateIds.length === 0) {
      return;
    }

    if (mode === "visual") {
      const selected = new Set(selectedCandidateIds);
      setCandidates((prev) => prev.map((item) => (
        selected.has(item.id) ? { ...item, status: "pending" } : item
      )));
      setSelectedCandidateIds([]);
      setToast({ tone: "success", message: "候选标签已回退到待审。" });
      return;
    }

    const response = await requeueTagCandidates({ ids: selectedCandidateIds });
    if (!response.ok || !response.data) {
      setFailure(response.error?.message ?? "回退失败。");
      return;
    }

    setSelectedCandidateIds([]);
    await refreshAll();
    setToast({ tone: "success", message: `已回退 ${response.data.requeued} 条候选。` });
  }, [mode, refreshAll, selectedCandidateIds, setFailure]);

  const clearPendingCandidates = useCallback(async () => {
    if (mode === "visual") {
      setCandidates((prev) => prev.filter((item) => item.status !== "pending"));
      setSelectedCandidateIds([]);
      setToast({ tone: "success", message: "已清空待审候选。" });
      return;
    }

    const response = await clearPendingTagCandidates();
    if (!response.ok || !response.data) {
      setFailure(response.error?.message ?? "清空待审失败。");
      return;
    }

    setSelectedCandidateIds([]);
    await refreshAll();
    setToast({ tone: "success", message: `已清空 ${response.data.removed} 条待审候选。` });
  }, [mode, refreshAll, setFailure]);

  return {
    mode,
    scene: "J7vS3",
    loading,
    canInteract: !loading,
    errorMessage,
    toast,
    searchInput,
    source,
    activeSection,
    showUnified,
    globalMatchCount,
    tagLibrary,
    candidates,
    blacklist,
    visibleTagLibrary,
    visibleCandidates,
    visibleBlacklist,
    selectedTagIds,
    selectedCandidateIds,
    selectedBlacklistIds,
    setSearchInput,
    setSource,
    setActiveSection,
    toggleTagSelection,
    toggleCandidateSelection,
    toggleBlacklistSelection,
    selectAllTags,
    addTags,
    deleteTagById,
    deleteSelectedTags,
    approveSelectedCandidates,
    rejectSelectedCandidates,
    blacklistSelectedCandidates,
    requeueSelectedCandidates,
    clearPendingCandidates,
    clearToast: () => setToast(null),
  };
}
