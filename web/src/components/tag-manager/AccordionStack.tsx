import { ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { TagTile } from "./TagTile";
import type {
  TagBlacklistItem,
  TagCandidateItem,
  TagLibraryItem,
  TagSection,
} from "../../types/domain";

type AccordionStackProps = {
  activeSection: TagSection | null;
  canInteract: boolean;
  tagLibrary: TagLibraryItem[];
  candidates: TagCandidateItem[];
  blacklist: TagBlacklistItem[];
  selectedTagIds: number[];
  selectedCandidateIds: number[];
  selectedBlacklistIds: number[];
  highlightedTagIds: number[];
  highlightedCandidateIds: number[];
  onSetSection: (section: TagSection) => void;
  onToggleTag: (id: number) => void;
  onToggleCandidate: (id: number) => void;
  onToggleBlacklist: (id: number) => void;
  onAddTags: () => Promise<void>;
  onDeleteOneTag: (id: number) => Promise<void>;
  onDeleteSelectedTags: () => Promise<void>;
  onSelectAllTags: () => void;
  onApproveCandidates: () => Promise<void>;
  onRejectCandidates: () => Promise<void>;
  onBlacklistCandidates: () => Promise<void>;
  onRequeueCandidates: () => Promise<void>;
  onClearPendingCandidates: () => Promise<void>;
};

type ActionButtonProps = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "danger";
};

function ActionButton({ label, onClick, disabled = false, tone = "default" }: ActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`h-[34px] whitespace-nowrap rounded-[10px] border px-3 font-main text-[12px] font-bold ${
        tone === "danger"
          ? "border-[#FCA5A5] bg-[#FEF2F2] text-[#B91C1C]"
          : "border-[#CBD5E1] bg-[#F8FAFC] text-[#334155]"
      } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-[#94A3B8]"}`}
    >
      {label}
    </button>
  );
}

function chunkRows<T>(items: T[], perRow: number): T[][] {
  const safePerRow = Math.max(1, perRow);
  const rows: T[][] = [];
  for (let index = 0; index < items.length; index += safePerRow) {
    rows.push(items.slice(index, index + safePerRow));
  }
  return rows;
}

function useAutoRowCapacity(minTileWidth = 228, gap = 12) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [perRow, setPerRow] = useState(4);

  useEffect(() => {
    const node = ref.current;
    if (!node) {
      return;
    }

    const update = () => {
      const width = node.clientWidth;
      if (width <= 0) {
        return;
      }
      const estimated = Math.max(1, Math.floor((width + gap) / (minTileWidth + gap)));
      setPerRow(estimated);
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, [gap, minTileWidth]);

  return { ref, perRow };
}

function SectionShell({
  title,
  expanded,
  onToggle,
  actions,
  children,
}: {
  title: string;
  expanded: boolean;
  onToggle: () => void;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-[14px] border border-[#E5E7EB] bg-white px-4 py-3" data-testid={`accordion-${title}`}>
      <div className="flex h-10 w-full items-center justify-between">
        <button
          type="button"
          onClick={onToggle}
          className="flex h-10 items-center border-none bg-transparent p-0 text-left"
        >
          <span className="font-main text-[20px] font-bold leading-none text-[#111827]">{title}</span>
        </button>

        <div className="flex shrink-0 items-center gap-2">
          {actions ? <div className="flex items-center gap-2">{actions}</div> : null}

          <button
            type="button"
            onClick={onToggle}
            className="flex h-[38px] w-[38px] items-center justify-center rounded-[12px] border border-[#CBD5E1] bg-[#F8FAFC]"
            aria-label={`toggle ${title}`}
          >
            {expanded ? <ChevronUp size={18} color="#334155" /> : <ChevronDown size={18} color="#334155" />}
          </button>
        </div>
      </div>

      {expanded ? <div className="mt-[10px] border-t border-[#E5E7EB] pt-[10px]">{children}</div> : null}
    </section>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex h-full items-center justify-center font-main text-[13px] font-semibold text-[#94A3B8]">
      {text}
    </div>
  );
}

function candidateStatusLabel(status: TagCandidateItem["status"]): string {
  if (status === "approved") {
    return "已通过";
  }
  if (status === "blacklisted") {
    return "已拉黑";
  }
  if (status === "mapped") {
    return "已映射";
  }
  return "待审";
}

export function AccordionStack({
  activeSection,
  canInteract,
  tagLibrary,
  candidates,
  blacklist,
  selectedTagIds,
  selectedCandidateIds,
  selectedBlacklistIds,
  highlightedTagIds,
  highlightedCandidateIds,
  onSetSection,
  onToggleTag,
  onToggleCandidate,
  onToggleBlacklist,
  onAddTags,
  onDeleteOneTag,
  onDeleteSelectedTags,
  onSelectAllTags,
  onApproveCandidates,
  onBlacklistCandidates,
  onRequeueCandidates,
  onClearPendingCandidates,
}: AccordionStackProps) {
  const tagLayout = useAutoRowCapacity();
  const candidateLayout = useAutoRowCapacity();
  const blacklistLayout = useAutoRowCapacity();

  const highlightedTagSet = useMemo(() => new Set(highlightedTagIds), [highlightedTagIds]);
  const highlightedCandidateSet = useMemo(
    () => new Set(highlightedCandidateIds),
    [highlightedCandidateIds],
  );

  const tagRows = useMemo(
    () => chunkRows(tagLibrary, tagLayout.perRow),
    [tagLibrary, tagLayout.perRow],
  );
  const candidateRows = useMemo(
    () => chunkRows(candidates, candidateLayout.perRow),
    [candidateLayout.perRow, candidates],
  );
  const blacklistRows = useMemo(
    () => chunkRows(blacklist, blacklistLayout.perRow),
    [blacklist, blacklistLayout.perRow],
  );

  return (
    <div className="min-h-0 space-y-3 overflow-y-auto pr-1">
      <SectionShell
        title="标签库"
        expanded={activeSection === "tag_library"}
        onToggle={() => onSetSection("tag_library")}
        actions={(
          <>
            <ActionButton
              label="全选"
              onClick={onSelectAllTags}
              disabled={!canInteract || tagLibrary.length === 0}
            />
            <ActionButton
              label="批量删除"
              onClick={() => void onDeleteSelectedTags()}
              disabled={!canInteract || selectedTagIds.length === 0}
              tone="danger"
            />
            <ActionButton label="新增标签" onClick={() => void onAddTags()} disabled={!canInteract} />
          </>
        )}
      >
        <div
          ref={tagLayout.ref}
          className="h-[320px] overflow-y-auto rounded-[12px] border border-[#E5E7EB] bg-[#F8FAFC] p-3"
        >
          {tagLibrary.length === 0 ? (
            <EmptyState text="暂无标签" />
          ) : (
            <div className="space-y-3">
              {tagRows.map((row, rowIndex) => (
                <div key={`row-tag-${rowIndex}`} className={`flex flex-wrap gap-3 ${rowIndex % 2 === 1 ? "pl-10" : ""}`}>
                  {row.map((item) => (
                    <TagTile
                      key={item.id}
                      label={item.name}
                      count={item.usageCount}
                      checked={selectedTagIds.includes(item.id)}
                      onToggle={() => onToggleTag(item.id)}
                      onDelete={() => {
                        void onDeleteOneTag(item.id);
                      }}
                      highlighted={highlightedTagSet.has(item.id)}
                    />
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </SectionShell>

      <SectionShell
        title="候选标签库"
        expanded={activeSection === "candidate_library"}
        onToggle={() => onSetSection("candidate_library")}
        actions={(
          <>
            <ActionButton
              label="通过"
              onClick={() => void onApproveCandidates()}
              disabled={!canInteract || selectedCandidateIds.length === 0}
            />
            <ActionButton label="映射通过" onClick={() => undefined} disabled={true} />
            <ActionButton
              label="拉黑"
              onClick={() => void onBlacklistCandidates()}
              disabled={!canInteract || selectedCandidateIds.length === 0}
              tone="danger"
            />
            <ActionButton
              label="回退待审"
              onClick={() => void onRequeueCandidates()}
              disabled={!canInteract || selectedCandidateIds.length === 0}
            />
            <ActionButton
              label="清空待审"
              onClick={() => void onClearPendingCandidates()}
              disabled={!canInteract}
            />
          </>
        )}
      >
        <div
          ref={candidateLayout.ref}
          className="h-[320px] overflow-y-auto rounded-[12px] border border-[#E5E7EB] bg-[#F8FAFC] p-3"
        >
          {candidates.length === 0 ? (
            <EmptyState text="暂无候选标签" />
          ) : (
            <div className="space-y-3">
              {candidateRows.map((row, rowIndex) => (
                <div key={`row-candidate-${rowIndex}`} className={`flex flex-wrap gap-3 ${rowIndex % 2 === 1 ? "pl-10" : ""}`}>
                  {row.map((item) => (
                    <TagTile
                      key={item.id}
                      label={item.name}
                      count={item.hitCount}
                      checked={selectedCandidateIds.includes(item.id)}
                      onToggle={() => onToggleCandidate(item.id)}
                      tone={item.status === "blacklisted" ? "blacklist" : "candidate"}
                      statusLabel={candidateStatusLabel(item.status)}
                      highlighted={highlightedCandidateSet.has(item.id)}
                    />
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </SectionShell>

      <SectionShell
        title="黑名单"
        expanded={activeSection === "blacklist"}
        onToggle={() => onSetSection("blacklist")}
        actions={(
          <>
            <ActionButton label="新增黑名单词" onClick={() => undefined} disabled={true} />
            <ActionButton label="批量移除" onClick={() => undefined} disabled={true} tone="danger" />
          </>
        )}
      >
        <div
          ref={blacklistLayout.ref}
          className="h-[280px] overflow-y-auto rounded-[12px] border border-[#E5E7EB] bg-[#F8FAFC] p-3"
        >
          {blacklist.length === 0 ? (
            <EmptyState text="黑名单为空" />
          ) : (
            <div className="space-y-3">
              {blacklistRows.map((row, rowIndex) => (
                <div key={`row-blacklist-${rowIndex}`} className={`flex flex-wrap gap-3 ${rowIndex % 2 === 1 ? "pl-10" : ""}`}>
                  {row.map((item) => (
                    <TagTile
                      key={item.id}
                      label={item.term}
                      count={item.hitCount}
                      checked={selectedBlacklistIds.includes(item.id)}
                      onToggle={() => onToggleBlacklist(item.id)}
                      tone="blacklist"
                    />
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </SectionShell>
    </div>
  );
}
