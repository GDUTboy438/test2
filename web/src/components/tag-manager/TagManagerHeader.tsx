type TagManagerHeaderProps = {
  title: string;
  subtitle: string;
  onBackToLibrary: () => void;
  disabled?: boolean;
};

export function TagManagerHeader({
  title,
  subtitle,
  onBackToLibrary,
  disabled = false,
}: TagManagerHeaderProps) {
  return (
    <header className="flex h-24 items-start justify-between bg-[#F9FAFB] px-9 pb-3 pt-4">
      <div className="flex flex-col gap-1.5">
        <h1 className="m-0 font-main text-[28px] font-bold leading-none text-[#111827]">{title}</h1>
        <p className="m-0 font-main text-[13px] font-semibold text-[#6B7280]">{subtitle}</p>
      </div>

      <button
        type="button"
        onClick={onBackToLibrary}
        disabled={disabled}
        className={`h-10 rounded-[11px] border border-[#4B5563] bg-[#1F2937] px-4 font-main text-[13px] font-bold text-white ${
          disabled ? "cursor-not-allowed opacity-70" : "cursor-pointer hover:brightness-110"
        }`}
      >
        返回资源库
      </button>
    </header>
  );
}
