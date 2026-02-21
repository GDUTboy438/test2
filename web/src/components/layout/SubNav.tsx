import { Grid2x2, List } from "lucide-react";
import type { ReactNode } from "react";
import { FilterMenu } from "./FilterMenu";
import { SortMenu } from "./SortMenu";
import type { FilterState, SortDirection, SortField, ViewMode } from "../../types/domain";

type SubNavProps = {
  height: 58 | 60;
  viewMode: ViewMode;
  filterState: FilterState;
  statusOptions: string[];
  resolutionOptions: string[];
  sortField: SortField;
  sortDirection: SortDirection;
  canInteract: boolean;
  onViewModeChange: (value: ViewMode) => void;
  onFilterChange: (value: FilterState) => void;
  onSortFieldChange: (value: SortField) => void;
  onSortDirectionToggle: () => void;
};

function ToggleButton({
  active,
  icon,
  label,
  onClick,
  disabled,
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex h-9 items-center justify-center gap-[6px] rounded-[9px] border-none px-[14px] font-main text-[13px] ${
        active
          ? "bg-[var(--color-view-active-bg)] font-bold text-[var(--color-view-active-text)]"
          : "bg-[var(--color-view-inactive-bg)] font-semibold text-[var(--color-view-inactive-text)]"
      } ${disabled ? "cursor-not-allowed opacity-70" : "cursor-pointer"}`}
    >
      <span className={active ? "text-[var(--color-view-active-icon)]" : "text-[var(--color-view-inactive-text)]"}>
        {icon}
      </span>
      <span>{label}</span>
    </button>
  );
}

export function SubNav({
  height,
  viewMode,
  filterState,
  statusOptions,
  resolutionOptions,
  sortField,
  sortDirection,
  canInteract,
  onViewModeChange,
  onFilterChange,
  onSortFieldChange,
  onSortDirectionToggle,
}: SubNavProps) {
  return (
    <div
      className="flex items-center justify-between bg-white px-4"
      data-testid="sub-nav"
      style={{ height: `${height}px` }}
    >
      <div className="flex items-center gap-2">
        <ToggleButton
          active={viewMode === "list"}
          icon={<List size={14} />}
          label="List"
          onClick={() => onViewModeChange("list")}
          disabled={!canInteract}
        />
        <ToggleButton
          active={viewMode === "grid"}
          icon={<Grid2x2 size={14} />}
          label="Grid"
          onClick={() => onViewModeChange("grid")}
          disabled={!canInteract}
        />
      </div>

      <div className="flex items-center gap-[10px]">
        <FilterMenu
          value={filterState}
          statusOptions={statusOptions}
          resolutionOptions={resolutionOptions}
          onChange={onFilterChange}
          disabled={!canInteract}
        />

        <SortMenu
          field={sortField}
          direction={sortDirection}
          onFieldChange={onSortFieldChange}
          onDirectionToggle={onSortDirectionToggle}
          disabled={!canInteract}
        />
      </div>
    </div>
  );
}
