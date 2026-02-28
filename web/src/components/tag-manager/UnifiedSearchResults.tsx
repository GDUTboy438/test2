import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { TagTile } from "./TagTile";
import type {
  TagBlacklistItem,
  TagCandidateItem,
  TagLibraryItem,
} from "../../types/domain";

type UnifiedSearchResultsProps = {
  tagLibrary: TagLibraryItem[];
  candidates: TagCandidateItem[];
  blacklist: TagBlacklistItem[];
  selectedTagIds: number[];
  selectedCandidateIds: number[];
  selectedBlacklistIds: number[];
  highlightedTagIds: number[];
  highlightedCandidateIds: number[];
  onToggleTag: (id: number) => void;
  onToggleCandidate: (id: number) => void;
  onToggleBlacklist: (id: number) => void;
  onDeleteOneTag: (id: number) => Promise<void>;
};

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

function Group({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <section className="rounded-[12px] border border-[#E5E7EB] bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-main text-[20px] font-bold text-[#111827]">{title}</span>
        <span className="font-main text-[13px] font-semibold text-[#64748B]">{count}</span>
      </div>
      {children}
    </section>
  );
}

function EmptyResult() {
  return (
    <div className="flex h-[120px] items-center justify-center rounded-[12px] border border-dashed border-[#CBD5E1] font-main text-[14px] font-semibold text-[#94A3B8]">
      没有匹配结果
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

export function UnifiedSearchResults({
  tagLibrary,
  candidates,
  blacklist,
  selectedTagIds,
  selectedCandidateIds,
  selectedBlacklistIds,
  highlightedTagIds,
  highlightedCandidateIds,
  onToggleTag,
  onToggleCandidate,
  onToggleBlacklist,
  onDeleteOneTag,
}: UnifiedSearchResultsProps) {
  const hasAny = tagLibrary.length + candidates.length + blacklist.length > 0;

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
    <div className="min-h-0 space-y-3 overflow-y-auto pr-1" data-testid="tag-manager-unified-results">
      {!hasAny ? <EmptyResult /> : null}

      {tagLibrary.length > 0 ? (
        <Group title="标签库" count={tagLibrary.length}>
          <div ref={tagLayout.ref} className="space-y-3">
            {tagRows.map((row, rowIndex) => (
              <div key={`unified-tag-row-${rowIndex}`} className={`flex flex-wrap gap-3 ${rowIndex % 2 === 1 ? "pl-10" : ""}`}>
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
        </Group>
      ) : null}

      {candidates.length > 0 ? (
        <Group title="候选标签库" count={candidates.length}>
          <div ref={candidateLayout.ref} className="space-y-3">
            {candidateRows.map((row, rowIndex) => (
              <div key={`unified-candidate-row-${rowIndex}`} className={`flex flex-wrap gap-3 ${rowIndex % 2 === 1 ? "pl-10" : ""}`}>
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
        </Group>
      ) : null}

      {blacklist.length > 0 ? (
        <Group title="黑名单" count={blacklist.length}>
          <div ref={blacklistLayout.ref} className="space-y-3">
            {blacklistRows.map((row, rowIndex) => (
              <div key={`unified-blacklist-row-${rowIndex}`} className={`flex flex-wrap gap-3 ${rowIndex % 2 === 1 ? "pl-10" : ""}`}>
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
        </Group>
      ) : null}
    </div>
  );
}
