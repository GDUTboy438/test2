import { useMemo, useState } from "react";
import type { FilterState } from "../../types/domain";

type FilterMenuProps = {
  value: FilterState;
  statusOptions: string[];
  resolutionOptions: string[];
  onChange: (value: FilterState) => void;
  disabled?: boolean;
};

function toggleInList(list: string[], value: string): string[] {
  if (list.includes(value)) {
    return list.filter((item) => item !== value);
  }
  return [...list, value];
}

export function FilterMenu({
  value,
  statusOptions,
  resolutionOptions,
  onChange,
  disabled = false,
}: FilterMenuProps) {
  const [open, setOpen] = useState(false);
  const hasFilters = value.statuses.length > 0 || value.resolutions.length > 0;

  const safeStatusOptions = useMemo(() => statusOptions.slice(0, 8), [statusOptions]);
  const safeResolutionOptions = useMemo(() => resolutionOptions.slice(0, 8), [resolutionOptions]);

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((prev) => !prev)}
        className={`flex h-9 items-center justify-center rounded-[9px] border border-[var(--color-filter-border)] bg-[var(--color-filter-bg)] px-[14px] font-main text-[13px] font-semibold text-[var(--color-filter-text)] ${
          hasFilters ? "ring-1 ring-[#CBD5E1]" : ""
        } ${disabled ? "cursor-not-allowed opacity-70" : "cursor-pointer"}`}
      >
        Filter
      </button>

      {open ? (
        <div className="absolute right-0 top-11 z-20 w-[240px] rounded-xl border border-[var(--color-border)] bg-white p-3 shadow-[0_8px_24px_rgba(15,20,28,0.12)]">
          <div className="mb-2 font-main text-[12px] font-bold text-[#4B5563]">Status</div>
          <div className="mb-3 flex max-h-[120px] flex-col gap-1 overflow-y-auto">
            {safeStatusOptions.map((option) => (
              <label key={option} className="flex items-center gap-2 font-main text-[12px] text-[#374151]">
                <input
                  type="checkbox"
                  checked={value.statuses.includes(option)}
                  onChange={() => onChange({
                    ...value,
                    statuses: toggleInList(value.statuses, option),
                  })}
                />
                <span>{option}</span>
              </label>
            ))}
          </div>

          <div className="mb-2 font-main text-[12px] font-bold text-[#4B5563]">Resolution</div>
          <div className="flex max-h-[120px] flex-col gap-1 overflow-y-auto">
            {safeResolutionOptions.map((option) => (
              <label key={option} className="flex items-center gap-2 font-main text-[12px] text-[#374151]">
                <input
                  type="checkbox"
                  checked={value.resolutions.includes(option)}
                  onChange={() => onChange({
                    ...value,
                    resolutions: toggleInList(value.resolutions, option),
                  })}
                />
                <span>{option}</span>
              </label>
            ))}
          </div>

          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={() => onChange({ statuses: [], resolutions: [] })}
              className="rounded-md border-none bg-[#F3F4F6] px-2 py-1 font-main text-[12px] font-semibold text-[#374151]"
            >
              Clear
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
