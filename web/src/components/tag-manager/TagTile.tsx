import { Check, X } from "lucide-react";

type TagTileProps = {
  label: string;
  count: number;
  checked: boolean;
  onToggle: () => void;
  onDelete?: () => void;
  widthClass?: string;
  tone?: "library" | "candidate" | "blacklist";
};

function toneClass(tone: TagTileProps["tone"]): string {
  if (tone === "blacklist") {
    return "bg-[#FFF7ED] border-[#FED7AA]";
  }
  if (tone === "candidate") {
    return "bg-[#F8FAFC] border-[#E2E8F0]";
  }
  return "bg-[#F8FAFC] border-[#E5E7EB]";
}

export function TagTile({
  label,
  count,
  checked,
  onToggle,
  onDelete,
  widthClass = "w-[216px]",
  tone = "library",
}: TagTileProps) {
  return (
    <div
      className={`flex h-11 ${widthClass} items-center justify-between rounded-[11px] border px-[12px] ${toneClass(tone)}`}
      data-testid="tag-tile"
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex min-w-0 items-center gap-[10px] border-none bg-transparent p-0 text-left"
      >
        <span
          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-[6px] border ${
            checked ? "border-[#111827] bg-[#111827] text-white" : "border-[#94A3B8] bg-white text-transparent"
          }`}
        >
          <Check size={12} strokeWidth={2.4} />
        </span>
        <span className="text-ellipsis max-w-[120px] font-sidebar text-[13px] font-bold text-[#0F172A]">{label}</span>
        <span className="font-sidebar text-[12px] font-bold text-[#64748B]">{count}</span>
      </button>

      {onDelete ? (
        <button
          type="button"
          onClick={onDelete}
          className="flex h-5 w-5 items-center justify-center border-none bg-transparent p-0 text-[#94A3B8] transition-colors hover:text-[#475569]"
          aria-label="delete tag"
        >
          <X size={14} strokeWidth={2.6} />
        </button>
      ) : (
        <span className="w-5" />
      )}
    </div>
  );
}
