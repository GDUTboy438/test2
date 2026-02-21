import { ArrowDown, ArrowUp } from "lucide-react";
import { useState } from "react";
import type { SortDirection, SortField } from "../../types/domain";

type SortMenuProps = {
  field: SortField;
  direction: SortDirection;
  onFieldChange: (field: SortField) => void;
  onDirectionToggle: () => void;
  disabled?: boolean;
};

const FIELD_OPTIONS: Array<{ value: SortField; label: string }> = [
  { value: "name", label: "Name" },
  { value: "modified", label: "Modified" },
  { value: "duration", label: "Duration" },
  { value: "size", label: "Size" },
];

export function SortMenu({
  field,
  direction,
  onFieldChange,
  onDirectionToggle,
  disabled = false,
}: SortMenuProps) {
  const [open, setOpen] = useState(false);

  const mergedToneClass = disabled
    ? "bg-[var(--color-sort-bg)] opacity-65"
    : open
      ? "bg-[var(--color-sort-bg)]"
      : "bg-[var(--color-sort-bg)] hover:brightness-110";

  const textToneClass = "text-[var(--color-sort-text)]";

  return (
    <div className="relative">
      <div
        className={`group flex h-9 w-[112px] items-center overflow-hidden rounded-[9px] border border-[var(--color-sort-border)] shadow-[0_1px_2px_rgba(15,23,42,0.12)] ${mergedToneClass} ${textToneClass}`}
      >
        <button
          type="button"
          disabled={disabled}
          onClick={() => setOpen((prev) => !prev)}
          className={`flex h-full flex-1 items-center justify-center border-none bg-transparent font-main text-[13px] font-semibold ${
            disabled ? "cursor-not-allowed" : "cursor-pointer"
          }`}
        >
          Sort
        </button>

        <div className="h-5 w-px bg-[var(--color-sort-border)]" />

        <button
          type="button"
          disabled={disabled}
          onClick={onDirectionToggle}
          className={`flex h-full w-10 items-center justify-center border-none bg-transparent ${
            disabled ? "cursor-not-allowed" : "cursor-pointer"
          }`}
          aria-label="toggle sort direction"
        >
          {direction === "asc" ? <ArrowUp size={14} /> : <ArrowDown size={14} />}
        </button>
      </div>

      {open ? (
        <div className="absolute right-0 top-11 z-20 w-[180px] rounded-xl border border-[var(--color-border)] bg-white p-2 shadow-[0_8px_24px_rgba(15,20,28,0.12)]">
          {FIELD_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                onFieldChange(option.value);
                setOpen(false);
              }}
              className={`flex w-full items-center justify-between rounded-md border-none px-2 py-2 text-left font-main text-[12px] ${
                field === option.value ? "bg-[#EEF2F7] font-bold text-[#111827]" : "bg-transparent text-[#4B5563]"
              }`}
            >
              <span>{option.label}</span>
              {field === option.value ? <span>v</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
