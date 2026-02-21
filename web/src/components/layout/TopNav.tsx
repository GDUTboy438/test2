import { Search } from "lucide-react";

type TopNavProps = {
  searchInput: string;
  onSearchChange: (value: string) => void;
  onPickLibrary: () => void;
  canInteract: boolean;
};

function ActionButton({
  label,
  dark,
  disabled,
  onClick,
}: {
  label: string;
  dark?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`h-[38px] rounded-[10px] border-none px-[14px] font-main text-[13px] font-semibold ${
        dark ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-card)] text-[#374151]"
      } ${disabled ? "cursor-not-allowed opacity-75" : "cursor-pointer"}`}
    >
      {label}
    </button>
  );
}

export function TopNav({ searchInput, onSearchChange, onPickLibrary, canInteract }: TopNavProps) {
  return (
    <header className="flex h-[84px] items-center justify-between bg-[var(--color-card)] px-6" data-testid="top-nav">
      <label className="flex h-[42px] w-[620px] items-center gap-2 rounded-full bg-[#F3F4F6] px-[14px]">
        <Search size={14} strokeWidth={2.2} color="#9CA3AF" />
        <input
          value={searchInput}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search video title, path, or tags..."
          className="h-full w-full border-none bg-transparent font-main text-[14px] font-normal text-[#374151] outline-none placeholder:text-[#9CA3AF]"
          disabled={!canInteract}
        />
      </label>

      <div className="flex h-[84px] items-center gap-[10px]">
        <ActionButton label="Tag Manager" disabled />
        <ActionButton label="Select Library" dark disabled={!canInteract} onClick={onPickLibrary} />
      </div>
    </header>
  );
}
