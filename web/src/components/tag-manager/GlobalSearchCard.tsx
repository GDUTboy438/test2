import { Search } from "lucide-react";
import type { TagSource } from "../../types/domain";

const SOURCE_OPTIONS: Array<{ value: TagSource; label: string }> = [
  { value: "all", label: "全部" },
  { value: "tag_library", label: "标签库" },
  { value: "candidate_library", label: "候选标签库" },
  { value: "blacklist", label: "黑名单" },
];

type GlobalSearchCardProps = {
  query: string;
  source: TagSource;
  matchCount: number;
  showUnified: boolean;
  disabled: boolean;
  onQueryChange: (value: string) => void;
  onSourceChange: (value: TagSource) => void;
};

function SourceChip({
  label,
  active,
  disabled,
  onClick,
}: {
  label: string;
  active: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`h-7 rounded-full border px-4 font-main text-[11px] font-bold leading-none ${
        active
          ? "border-[#374151] bg-[#111827] text-white"
          : "border-[#CBD5E1] bg-white text-[#334155]"
      } ${disabled ? "cursor-not-allowed opacity-70" : "cursor-pointer hover:border-[#94A3B8]"}`}
    >
      {label}
    </button>
  );
}

export function GlobalSearchCard({
  query,
  source,
  matchCount,
  showUnified,
  disabled,
  onQueryChange,
  onSourceChange,
}: GlobalSearchCardProps) {
  return (
    <section
      className="flex h-[104px] flex-col justify-between rounded-[14px] border border-[#E5E7EB] bg-white p-[14px]"
      data-testid="tag-manager-global-search-card"
    >
      <label className="flex h-10 items-center gap-2 rounded-[14px] border border-[#D1D5DB] bg-[#F8FAFC] px-4">
        <Search size={16} strokeWidth={2.2} color="#9CA3AF" />
        <input
          value={query}
          disabled={disabled}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜索标签（标签库 / 候选标签库 / 黑名单）"
          className="h-full w-full border-none bg-transparent font-main text-[13px] font-semibold text-[#374151] outline-none placeholder:text-[#94A3B8]"
        />
      </label>

      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {SOURCE_OPTIONS.map((option) => (
            <SourceChip
              key={option.value}
              label={option.label}
              active={source === option.value}
              disabled={disabled}
              onClick={() => onSourceChange(option.value)}
            />
          ))}
        </div>

        {showUnified ? (
          <div className="font-main text-[12px] font-semibold text-[#64748B]">
            共匹配 <span className="font-bold text-[#111827]">{matchCount}</span> 项
          </div>
        ) : null}
      </div>
    </section>
  );
}
