
import { ChevronDown, Folder, FolderSearch, Pause, Play, RefreshCw, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { notifyRouteChanged, writeTagManagerLinkageToUrl, type TagManagerFocus } from "../../navigation/tag-manager-linkage";
import { setRouteInUrl } from "../../navigation/page-route";
import { getLatestLog, getLogEvents } from "../../services/logs-api";
import { getTagCandidates } from "../../services/tag-manager-api";
import { useFeatureExtractionState } from "../../state/use-feature-extraction-state";

type SelectOption = { value: string; label: string };
type DetailMetricKey = "processedVideos" | "selectedTerms" | "taggedVideos" | "createdRelations" | "pendingCandidates";
type DetailRow = { primary: string; secondary?: string; badge?: string; meta?: string };
type DetailState = { loading: boolean; error: string; rows: DetailRow[]; highlightTags: string[]; highlightCandidates: string[] };

function CapsuleChevron({ rotate = false }: { rotate?: boolean }) {
  return (
    <span className={`pointer-events-none inline-flex h-9 w-9 items-center justify-center rounded-[11px] border border-[#CBD5E1] bg-white transition-transform ${rotate ? "rotate-180" : ""}`}>
      <ChevronDown size={16} color="#334155" />
    </span>
  );
}

function DropdownControl({
  label,
  value,
  options,
  disabled,
  className,
  onChange,
}: {
  label: string;
  value: string;
  options: SelectOption[];
  disabled?: boolean;
  className?: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const current = options.find((item) => item.value === value)?.label ?? value;

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onEsc = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onEsc);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={`relative h-[64px] rounded-[14px] border border-[#CBD5E1] bg-[#F8FAFC] ${className ?? ""} ${disabled ? "opacity-60" : ""}`}>
      <button
        type="button"
        className="relative h-full w-full rounded-[inherit] border-none bg-transparent px-4 text-left"
        disabled={disabled}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="block truncate pr-12 font-main text-[16px] font-semibold text-[#0F172A]">
          <span className="text-[#64748B]">{label}:</span> {current}
        </span>
        <span className="absolute right-4 top-1/2 -translate-y-1/2"><CapsuleChevron rotate={open} /></span>
      </button>
      {open ? (
        <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-40 overflow-hidden rounded-[12px] border border-[#CBD5E1] bg-white shadow-[0_14px_28px_rgba(15,23,42,0.16)]">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`block w-full border-none px-3 py-2 text-left font-main text-[14px] ${option.value === value ? "bg-[#E8EDFF] font-bold text-[#1D4ED8]" : "bg-white text-[#334155] hover:bg-[#F8FAFC]"}`}
              onClick={() => {
                setOpen(false);
                if (option.value !== value) onChange(option.value);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function StepperField({ label, value, onStep, disabled }: { label: string; value: string; onStep: (delta: number) => void; disabled?: boolean }) {
  return (
    <div className={`flex h-[54px] min-w-0 items-center rounded-[12px] border border-[#CBD5E1] bg-[#F8FAFC] px-3 ${disabled ? "opacity-60" : ""}`}>
      <span className="mr-3 min-w-0 flex-1 truncate font-main text-[14px] font-semibold text-[#334155]">{label}</span>
      <div className="flex h-[38px] items-center rounded-[10px] border border-[#CBD5E1] bg-white px-2">
        <button type="button" className="h-7 w-7 rounded-[8px] border-none bg-transparent font-main text-[18px] font-bold text-[#334155]" onClick={() => onStep(-1)} disabled={disabled}>-</button>
        <span className="w-[56px] text-center font-main text-[15px] font-bold text-[#0F172A]">{value}</span>
        <button type="button" className="h-7 w-7 rounded-[8px] border-none bg-transparent font-main text-[18px] font-bold text-[#334155]" onClick={() => onStep(1)} disabled={disabled}>+</button>
      </div>
    </div>
  );
}

function metricTitle(metric: DetailMetricKey): string {
  if (metric === "processedVideos") return "处理视频详情";
  if (metric === "selectedTerms") return "选中词详情";
  if (metric === "taggedVideos") return "打标视频详情";
  if (metric === "createdRelations") return "新建关系详情";
  return "待审核候选词详情";
}

function emptyDetailState(): DetailState {
  return { loading: false, error: "", rows: [], highlightTags: [], highlightCandidates: [] };
}

function toTextList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item ?? "").trim()).filter((item, index, arr) => item.length > 0 && arr.indexOf(item) === index);
}

function stripTopTerm(term: string): string {
  const match = term.match(/^(.+?)\s*\(\d+\/\d+\)\s*$/);
  return (match?.[1] ?? term).trim();
}
async function loadVideoRows(): Promise<DetailRow[]> {
  const latest = await getLatestLog("tag_mining");
  if (!latest.ok || !latest.data?.item) return [];
  const eventsResp = await getLogEvents({ source: "tag_mining", log_id: latest.data.item.logId, page: 1, page_size: 200, event: "video_processed" });
  if (!eventsResp.ok || !eventsResp.data) throw new Error(eventsResp.error?.message ?? "读取任务日志失败。");
  return eventsResp.data.items.map((event) => {
    const selected = toTextList(event.payload.selected_terms);
    return {
      primary: event.relPath && event.relPath !== "-" ? event.relPath : String(event.payload.rel_path ?? "-"),
      secondary: selected.length > 0 ? selected.slice(0, 6).join("、") : "无标签",
      badge: `${selected.length} 个标签`,
      meta: event.timeLabel,
    };
  });
}

async function buildDetail(metric: DetailMetricKey, topTerms: string[]): Promise<DetailState> {
  if (metric === "pendingCandidates") {
    const pendingResp = await getTagCandidates(["pending"]);
    if (!pendingResp.ok || !pendingResp.data) throw new Error(pendingResp.error?.message ?? "读取待审核候选词失败。");
    return {
      loading: false,
      error: "",
      rows: pendingResp.data.map((item) => ({
        primary: item.name,
        secondary: `命中次数: ${item.hitCount}`,
        badge: "pending",
        meta: item.lastSeenEpoch > 0 ? new Date(item.lastSeenEpoch * 1000).toLocaleString("sv-SE").replace("T", " ") : "--",
      })),
      highlightTags: [],
      highlightCandidates: pendingResp.data.map((item) => item.name),
    };
  }

  if (metric === "selectedTerms") {
    const terms = topTerms.map(stripTopTerm).filter((item, index, arr) => item.length > 0 && arr.indexOf(item) === index);
    return {
      loading: false,
      error: "",
      rows: terms.map((term, index) => ({ primary: term, secondary: `排名 ${index + 1}` })),
      highlightTags: terms,
      highlightCandidates: terms,
    };
  }

  const rows = await loadVideoRows();
  if (metric === "processedVideos") {
    const terms = rows.flatMap((row) => (row.secondary && row.secondary !== "无标签" ? row.secondary.split("、") : [])).map((item) => item.trim()).filter((item, index, arr) => item.length > 0 && arr.indexOf(item) === index);
    return { loading: false, error: "", rows, highlightTags: terms, highlightCandidates: terms };
  }

  if (metric === "taggedVideos") {
    const taggedRows = rows.filter((row) => !row.badge?.startsWith("0 "));
    const terms = taggedRows.flatMap((row) => (row.secondary && row.secondary !== "无标签" ? row.secondary.split("、") : [])).map((item) => item.trim()).filter((item, index, arr) => item.length > 0 && arr.indexOf(item) === index);
    return { loading: false, error: "", rows: taggedRows, highlightTags: terms, highlightCandidates: terms };
  }

  const counter = new Map<string, number>();
  for (const row of rows) {
    if (!row.secondary || row.secondary === "无标签") continue;
    for (const term of row.secondary.split("、")) {
      const key = term.trim();
      if (!key) continue;
      counter.set(key, (counter.get(key) ?? 0) + 1);
    }
  }
  const relationRows = Array.from(counter.entries()).sort((a, b) => b[1] - a[1]).map(([term, count]) => ({ primary: term, secondary: "标签关联命中", badge: `${count}` }));
  const terms = relationRows.map((row) => row.primary);
  return { loading: false, error: "", rows: relationRows, highlightTags: terms, highlightCandidates: terms };
}

export function FeatureExtractionPageContent() {
  const state = useFeatureExtractionState();
  const taskRunning = state.task.status === "running" || state.task.status === "stopping";
  const lockModelSwitch = state.task.runningLockModelSwitch;
  const [activeMetric, setActiveMetric] = useState<DetailMetricKey | null>(null);
  const [detailState, setDetailState] = useState<DetailState>(emptyDetailState());
  const [detailRefreshSeq, setDetailRefreshSeq] = useState(0);

  const selectedEmbeddingLabel = useMemo(() => {
    const item = state.embeddingOptions.find((option) => option.selectValue === state.task.embeddingModel);
    return item?.name ?? "请选择 Embedding 模型";
  }, [state.embeddingOptions, state.task.embeddingModel]);

  const selectedRerankerLabel = useMemo(() => {
    const item = state.rerankerOptions.find((option) => option.selectValue === state.task.rerankerModel);
    return item?.name ?? "请选择 Reranker 模型";
  }, [state.rerankerOptions, state.task.rerankerModel]);

  useEffect(() => {
    if (!activeMetric) {
      setDetailState(emptyDetailState());
      return;
    }
    let disposed = false;
    setDetailState((prev) => ({ ...prev, loading: true, error: "" }));
    void (async () => {
      try {
        const next = await buildDetail(activeMetric, state.task.result.topTerms ?? []);
        if (!disposed) setDetailState(next);
      } catch (error) {
        if (!disposed) {
          setDetailState({ loading: false, error: error instanceof Error ? error.message : "读取结果详情失败。", rows: [], highlightTags: [], highlightCandidates: [] });
        }
      }
    })();
    return () => {
      disposed = true;
    };
  }, [activeMetric, detailRefreshSeq, state.task.result.topTerms]);

  const navigateToTagManager = () => {
    if (!activeMetric) return;
    const tagNames = detailState.highlightTags.slice(0, 20);
    const candidateNames = detailState.highlightCandidates.slice(0, 20);
    let focus: TagManagerFocus = activeMetric === "pendingCandidates" ? "candidate_library" : "tag_library";
    if (focus === "tag_library" && tagNames.length === 0 && candidateNames.length > 0) focus = "candidate_library";
    setRouteInUrl({ page: "settings", module: "tag-manager" });
    writeTagManagerLinkageToUrl({ focus, highlightTags: tagNames, highlightCandidates: candidateNames });
    notifyRouteChanged();
  };

  const metrics: Array<{ key: DetailMetricKey; text: string }> = [
    { key: "processedVideos", text: `处理视频数: ${state.task.result.processedVideos}` },
    { key: "selectedTerms", text: `选中词数: ${state.task.result.selectedTerms}` },
    { key: "taggedVideos", text: `打标视频数: ${state.task.result.taggedVideos}` },
    { key: "createdRelations", text: `新建关系数: ${state.task.result.createdRelations}` },
    { key: "pendingCandidates", text: `待审核候选词: ${state.task.result.pendingCandidateTerms}` },
  ];

  return (
    <>
      <section className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto px-4 pb-6 pt-4">
        <article className="rounded-[16px] border border-[#E2E8F0] bg-white p-5">
          <div className="flex items-start justify-between gap-4">
            <h2 className="m-0 font-main text-[24px] font-bold text-[#0F172A]">提取任务控制</h2>
            <div className="flex items-center gap-3">
              <button type="button" className="inline-flex h-12 items-center gap-2 rounded-[12px] border border-[#1E293B] bg-[#0F172A] px-5 font-main text-[14px] font-bold text-white disabled:cursor-not-allowed disabled:opacity-60" disabled={!state.canInteract || taskRunning} onClick={() => void state.startTask()}><Play size={16} />开始提取</button>
              <button type="button" className="inline-flex h-12 items-center gap-2 rounded-[12px] border border-[#CBD5E1] bg-[#E2E8F0] px-5 font-main text-[14px] font-bold text-[#334155] disabled:cursor-not-allowed disabled:opacity-60" disabled={!taskRunning} onClick={() => void state.stopTask()}><Pause size={16} />停止</button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-3">
            <DropdownControl label="strategy" value={state.task.strategy} options={[{ value: "auto", label: "auto" }, { value: "rule", label: "rule" }, { value: "model", label: "model" }]} onChange={(value) => state.setStrategy(value as "auto" | "rule" | "model")} disabled={!state.canInteract || taskRunning} />
            <DropdownControl label="scope" value={state.task.scope} options={[{ value: "new_only", label: "new_only" }, { value: "all", label: "all" }]} onChange={(value) => state.setScope(value as "all" | "new_only")} disabled={!state.canInteract || taskRunning} />
            <button type="button" className="flex h-[64px] items-center justify-between rounded-[14px] border border-[#C7D2FE] bg-[#EEF2FF] px-4 font-main text-[14px] font-bold text-[#4338CA] disabled:cursor-not-allowed disabled:opacity-60" onClick={state.toggleAdvanced} disabled={!state.canInteract || taskRunning}><span className="inline-flex items-center gap-2"><SlidersHorizontal size={16} />高级参数(4)</span><CapsuleChevron rotate={state.advancedExpanded} /></button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <DropdownControl label="核心模型 · Embedding" value={state.task.embeddingModel} options={state.embeddingOptions.length > 0 ? state.embeddingOptions.map((item) => ({ value: item.selectValue, label: item.name })) : [{ value: "", label: "暂无可用模型" }]} onChange={state.setEmbeddingModel} disabled={!state.canInteract || lockModelSwitch} />
            <DropdownControl label="核心模型 · Reranker" value={state.task.rerankerModel} options={state.rerankerOptions.length > 0 ? state.rerankerOptions.map((item) => ({ value: item.selectValue, label: item.name })) : [{ value: "", label: "暂无可用模型" }]} onChange={state.setRerankerModel} disabled={!state.canInteract || lockModelSwitch} />
          </div>

          <div className="mt-3 grid grid-cols-3 gap-3">
            <StepperField label="min_df" value={String(state.task.minDf)} onStep={state.stepMinDf} disabled={!state.canInteract || taskRunning} />
            <StepperField label="max_tags_per_video" value={String(state.task.maxTagsPerVideo)} onStep={state.stepMaxTagsPerVideo} disabled={!state.canInteract || taskRunning} />
            <StepperField label="max_terms" value={String(state.task.maxTerms)} onStep={state.stepMaxTerms} disabled={!state.canInteract || taskRunning} />
          </div>
          {state.advancedExpanded ? (
            <div className="mt-3 rounded-[14px] border border-[#D7DEEA] bg-gradient-to-b from-[#F8FAFC] to-[#F3F6FB] p-4 shadow-[inset_0_1px_0_#FFFFFF]">
              <div className="grid grid-cols-2 gap-3">
                <StepperField label="recall_top_k" value={String(state.task.recallTopK)} onStep={state.stepRecallTopK} disabled={!state.canInteract || taskRunning} />
                <StepperField label="recall_min_score" value={state.task.recallMinScore.toFixed(2)} onStep={state.stepRecallMinScore} disabled={!state.canInteract || taskRunning} />
                <DropdownControl label="auto_apply" value={state.task.autoApply >= 0.5 ? "true" : "false"} options={[{ value: "true", label: "true" }, { value: "false", label: "false" }]} onChange={(value) => state.setAutoApply(value as "true" | "false")} disabled={!state.canInteract || taskRunning} />
                <DropdownControl label="pending_review" value={state.task.pendingReview >= 0.5 ? "true" : "false"} options={[{ value: "true", label: "true" }, { value: "false", label: "false" }]} onChange={(value) => state.setPendingReview(value as "true" | "false")} disabled={!state.canInteract || taskRunning} />
              </div>
            </div>
          ) : null}
        </article>

        <article className="rounded-[16px] border border-[#E2E8F0] bg-white p-5">
          <h3 className="m-0 font-main text-[24px] font-bold text-[#0F172A]">任务进度与结果摘要</h3>
          <p className="mb-0 mt-2 font-main text-[14px] font-semibold text-[#475569]">phase: {state.task.phase} | 进度: {state.task.progressPercent}%</p>
          <div className="mt-2 h-2 w-full rounded bg-[#E2E8F0]"><div className="h-2 rounded bg-[#4F46E5]" style={{ width: `${state.task.progressPercent}%` }} /></div>
          <div className="mt-3 flex flex-wrap gap-2">
            {metrics.map((metric) => (
              <button key={metric.key} type="button" onClick={() => setActiveMetric((prev) => (prev === metric.key ? null : metric.key))} className={`inline-flex h-10 items-center rounded-full border px-5 font-main text-[14px] font-semibold ${activeMetric === metric.key ? "border-[#818CF8] bg-[#EEF2FF] text-[#3730A3]" : "border-[#CBD5E1] bg-[#F8FAFC] text-[#334155]"}`}>{metric.text}</button>
            ))}
            {state.task.result.fallbackReason ? (<span className="inline-flex h-10 items-center rounded-full border border-[#EAB308] bg-[#FEF9C3] px-5 font-main text-[14px] font-semibold text-[#92400E]">回退原因: {state.task.result.fallbackReason}</span>) : null}
          </div>

          {activeMetric ? (
            <div className="mt-4 rounded-[14px] border border-[#E2E8F0] bg-[#F8FAFC] p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="font-main text-[15px] font-bold text-[#0F172A]">{metricTitle(activeMetric)} · {detailState.rows.length} 条</div>
                <div className="flex items-center gap-2">
                  <button type="button" className="inline-flex h-8 items-center gap-1 rounded-[9px] border border-[#CBD5E1] bg-white px-3 font-main text-[12px] font-bold text-[#334155]" onClick={() => setDetailRefreshSeq((value) => value + 1)} disabled={detailState.loading}><RefreshCw size={13} />刷新</button>
                  <button type="button" className="inline-flex h-8 items-center rounded-[9px] border border-[#A5B4FC] bg-[#EEF2FF] px-3 font-main text-[12px] font-bold text-[#4338CA] disabled:cursor-not-allowed disabled:opacity-60" onClick={navigateToTagManager} disabled={detailState.highlightTags.length === 0 && detailState.highlightCandidates.length === 0}>前往标签管理</button>
                </div>
              </div>
              {detailState.loading ? (
                <div className="mt-3 rounded-[10px] border border-[#E2E8F0] bg-white px-3 py-6 text-center font-main text-[13px] font-semibold text-[#64748B]">正在加载结果详情...</div>
              ) : detailState.error ? (
                <div className="mt-3 rounded-[10px] border border-[#FECACA] bg-[#FEF2F2] px-3 py-3 font-main text-[13px] font-semibold text-[#B91C1C]">{detailState.error}</div>
              ) : detailState.rows.length === 0 ? (
                <div className="mt-3 rounded-[10px] border border-[#E2E8F0] bg-white px-3 py-6 text-center font-main text-[13px] font-semibold text-[#94A3B8]">当前维度暂无可展示内容</div>
              ) : (
                <div className="mt-3 max-h-[260px] overflow-y-auto rounded-[10px] border border-[#E2E8F0] bg-white">
                  {detailState.rows.map((row, index) => (
                    <div key={`${row.primary}-${index}`} className="flex items-start justify-between gap-3 border-b border-[#EEF2F7] px-3 py-2 last:border-b-0">
                      <div className="min-w-0">
                        <div className="truncate font-main text-[13px] font-semibold text-[#0F172A]">{row.primary}</div>
                        {row.secondary ? <div className="mt-1 truncate font-main text-[12px] font-medium text-[#64748B]">{row.secondary}</div> : null}
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {row.badge ? <span className="inline-flex h-6 items-center rounded-full border border-[#CBD5E1] bg-[#F8FAFC] px-2 font-main text-[11px] font-bold text-[#334155]">{row.badge}</span> : null}
                        {row.meta ? <span className="font-main text-[11px] font-semibold text-[#94A3B8]">{row.meta}</span> : null}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </article>

        <article className="rounded-[16px] border border-[#E2E8F0] bg-white p-5">
          <h3 className="m-0 font-main text-[24px] font-bold text-[#0F172A]">模型管理</h3>
          <div className="mt-4 grid grid-cols-[170px_1fr_1.2fr_auto_auto] gap-3">
            <DropdownControl label="模型类型" value={state.modelTypeFilter} options={[{ value: "all", label: "all" }, { value: "embedding", label: "embedding" }, { value: "reranker", label: "reranker" }]} onChange={(value) => state.setModelTypeFilter(value as "all" | "embedding" | "reranker")} className="h-10" />
            <label className="flex h-10 items-center gap-2 rounded-[10px] border border-[#CBD5E1] bg-[#F8FAFC] px-3"><Search size={14} color="#64748B" /><input className="w-full border-none bg-transparent font-main text-[13px] font-semibold text-[#334155] outline-none" value={state.searchKeyword} onChange={(event) => state.setSearchKeyword(event.target.value)} placeholder="搜索模型名 / 本地路径" /></label>
            <div className="flex h-10 items-center rounded-[10px] border border-[#CBD5E1] bg-[#F8FAFC] px-3 font-main text-[13px] font-semibold text-[#334155]">模型根路径: {state.modelRoot || "--"}</div>
            <button type="button" className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-[#A5B4FC] bg-[#EEF2FF] px-3 font-main text-[13px] font-bold text-[#4338CA]" onClick={() => void state.chooseModelRoot()}><FolderSearch size={14} />选择模型目录</button>
            <button type="button" className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-[#1E293B] bg-[#0F172A] px-3 font-main text-[13px] font-bold text-white" onClick={() => void state.importModelDirectory()}><Folder size={14} />导入目录</button>
          </div>
          <div className="mt-3 grid grid-cols-[1fr_1fr] gap-3">
            <div className="rounded-[10px] border border-[#CBD5E1] bg-[#F8FAFC] px-3 py-2 font-main text-[13px] font-semibold text-[#334155]">可用 Embedding: {selectedEmbeddingLabel}</div>
            <div className="rounded-[10px] border border-[#CBD5E1] bg-[#F8FAFC] px-3 py-2 font-main text-[13px] font-semibold text-[#334155]">可用 Reranker: {selectedRerankerLabel}</div>
          </div>
          <div className="mt-3 overflow-hidden rounded-[12px] border border-[#E2E8F0]">
            <table className="w-full border-collapse">
              <thead className="bg-[#F8FAFC]"><tr><th className="px-3 py-3 text-left font-main text-[12px] font-bold text-[#334155]">类型</th><th className="px-3 py-3 text-left font-main text-[12px] font-bold text-[#334155]">模型名</th><th className="px-3 py-3 text-left font-main text-[12px] font-bold text-[#334155]">来源</th><th className="px-3 py-3 text-left font-main text-[12px] font-bold text-[#334155]">下载状态</th><th className="px-3 py-3 text-left font-main text-[12px] font-bold text-[#334155]">本地路径 / 下载链接</th><th className="px-3 py-3 text-left font-main text-[12px] font-bold text-[#334155]">操作</th></tr></thead>
              <tbody>{state.filteredModels.map((model) => (<tr key={model.id} className="border-b border-[#E2E8F0]"><td className="px-3 py-3 font-main text-[13px] font-semibold text-[#334155]">{model.type}</td><td className="px-3 py-3 font-main text-[13px] font-semibold text-[#0F172A]">{model.name}</td><td className="px-3 py-3 font-main text-[13px] font-semibold"><span className={model.source === "custom" ? "text-[#4338CA]" : "text-[#334155]"}>{model.source}</span></td><td className="px-3 py-3 font-main text-[13px] font-semibold"><span className={model.downloaded ? "text-[#15803D]" : "text-[#B91C1C]"}>{model.downloaded ? "已下载" : "未下载"}</span></td><td className="px-3 py-3 font-main text-[13px] font-semibold text-[#334155]">{model.localPath ? model.localPath : model.downloadUrl}</td><td className="px-3 py-3">{model.downloaded ? (<button type="button" className="h-8 rounded-[10px] border border-[#93C5FD] bg-[#EFF6FF] px-3 font-main text-[12px] font-bold text-[#1D4ED8]" onClick={() => void state.openModelPath(model.localPath)}>打开本地路径</button>) : (<a className="inline-flex h-8 items-center rounded-[10px] border border-[#FECACA] bg-[#FEF2F2] px-3 font-main text-[12px] font-bold text-[#B91C1C] no-underline" href={model.downloadUrl} target="_blank" rel="noreferrer">去下载</a>)}</td></tr>))}</tbody>
            </table>
          </div>
          <div className="mt-3 flex justify-end"><button type="button" className="h-9 rounded-[10px] border border-[#CBD5E1] bg-white px-3 font-main text-[12px] font-bold text-[#334155]" onClick={() => void state.refreshModels()}>刷新模型列表</button></div>
        </article>
      </section>

      {state.errorMessage ? <div className="h-8 bg-[#FEE2E2] px-6 py-1 font-main text-[13px] font-semibold text-[#B91C1C]">{state.errorMessage}</div> : null}
      {state.toast ? <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 rounded-xl px-4 py-2 font-main text-[13px] font-semibold text-white ${state.toast.tone === "success" ? "bg-[#111827]" : "bg-[#B91C1C]"}`}>{state.toast.message}</div> : null}
    </>
  );
}
