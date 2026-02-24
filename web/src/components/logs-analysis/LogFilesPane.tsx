import { Check, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { LogFileItem, LogSource, LogSourceOption } from "../../types/domain";

type LogFilesPaneProps = {
  paneWidthCss: string;
  source: LogSource;
  sourceOptions: LogSourceOption[];
  files: LogFileItem[];
  selectedLogId: string;
  collapsed: boolean;
  disabled: boolean;
  onSourceChange: (source: LogSource) => void;
  onSelectFile: (logId: string) => void;
  onRefresh: () => void;
  onLoadLatest: () => void;
  onToggleCollapse: () => void;
};

function ActionButton({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`h-7 rounded-[8px] border border-[#CBD5E1] bg-[#F8FAFC] px-[10px] font-main text-[11px] font-bold text-[#334155] ${
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-[#94A3B8]"
      }`}
    >
      {label}
    </button>
  );
}

export function LogFilesPane({
  paneWidthCss,
  source,
  sourceOptions,
  files,
  selectedLogId,
  collapsed,
  disabled,
  onSourceChange,
  onSelectFile,
  onRefresh,
  onLoadLatest,
  onToggleCollapse,
}: LogFilesPaneProps) {
  const [sourceMenuOpen, setSourceMenuOpen] = useState(false);
  const sourceMenuRef = useRef<HTMLDivElement | null>(null);

  const sourceLabel = useMemo(
    () => sourceOptions.find((item) => item.source === source)?.label ?? source,
    [source, sourceOptions],
  );

  useEffect(() => {
    if (!sourceMenuOpen) {
      return;
    }

    const onDocumentMouseDown = (event: MouseEvent) => {
      if (!sourceMenuRef.current) {
        return;
      }
      if (!sourceMenuRef.current.contains(event.target as Node)) {
        setSourceMenuOpen(false);
      }
    };

    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSourceMenuOpen(false);
      }
    };

    window.addEventListener("mousedown", onDocumentMouseDown);
    window.addEventListener("keydown", onEscape);
    return () => {
      window.removeEventListener("mousedown", onDocumentMouseDown);
      window.removeEventListener("keydown", onEscape);
    };
  }, [sourceMenuOpen]);

  useEffect(() => {
    if (collapsed || disabled) {
      setSourceMenuOpen(false);
    }
  }, [collapsed, disabled]);

  return (
    <section
      className="flex h-full min-w-0 shrink-0 flex-col rounded-[14px] border border-[#E5E7EB] bg-white p-[14px] transition-[width] duration-200"
      style={{ width: paneWidthCss }}
    >
      {collapsed ? (
        <div className="flex min-h-0 flex-1 flex-col items-center gap-3">
          <button
            type="button"
            disabled={disabled}
            onClick={onToggleCollapse}
            className="flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#CBD5E1] bg-[#F8FAFC]"
            aria-label="展开日志文件侧栏"
          >
            <ChevronRight size={16} color="#334155" />
          </button>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <div className="flex h-[34px] items-center justify-between">
            <span className="font-main text-[14px] font-bold text-[#111827]">日志文件</span>
            <div className="flex items-center gap-2">
              <ActionButton label="刷新" onClick={onRefresh} disabled={disabled} />
              <ActionButton label="加载最新" onClick={onLoadLatest} disabled={disabled} />
            </div>
          </div>

          <div ref={sourceMenuRef} className="relative">
            <div className="flex h-11 items-center justify-between rounded-[10px] border border-[#CBD5E1] bg-[#F8FAFC] px-2">
              <span className="font-main text-[12px] font-bold text-[#334155]">日志类型：{sourceLabel}</span>

              <button
                type="button"
                disabled={disabled}
                onClick={() => setSourceMenuOpen((prev) => !prev)}
                className={`flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#CBD5E1] bg-[#F8FAFC] transition ${
                  sourceMenuOpen ? "bg-white shadow-[0_2px_6px_rgba(15,23,42,0.08)]" : ""
                } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:bg-white"}`}
                aria-label="切换日志类型"
                aria-expanded={sourceMenuOpen}
              >
                <ChevronDown
                  size={16}
                  color="#334155"
                  className={`transition-transform duration-150 ${sourceMenuOpen ? "rotate-180" : ""}`}
                />
              </button>
            </div>

            {sourceMenuOpen && !disabled ? (
              <div className="absolute right-0 top-[calc(100%+6px)] z-30 w-[230px] rounded-[12px] border border-[#CBD5E1] bg-white p-1 shadow-[0_10px_24px_rgba(15,23,42,0.18)]">
                {sourceOptions.map((option) => {
                  const selected = option.source === source;
                  return (
                    <button
                      key={option.source}
                      type="button"
                      onClick={() => {
                        setSourceMenuOpen(false);
                        if (option.source !== source) {
                          onSourceChange(option.source);
                        }
                      }}
                      className={`flex h-9 w-full items-center justify-between rounded-[8px] px-3 text-left font-main text-[12px] font-bold ${
                        selected
                          ? "bg-[#1E3A8A] text-white"
                          : "text-[#334155] hover:bg-[#EEF2FF] hover:text-[#1E293B]"
                      }`}
                    >
                      <span>{option.label}</span>
                      {selected ? <Check size={14} /> : null}
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto rounded-[12px] border border-[#E5E7EB] bg-[#F8FAFC] p-[10px]">
            {files.length === 0 ? (
              <div className="flex h-full items-center justify-center font-main text-[13px] font-semibold text-[#94A3B8]">
                暂无日志文件
              </div>
            ) : (
              <div className="space-y-2">
                {files.map((item) => {
                  const selected = item.logId === selectedLogId;
                  return (
                    <button
                      key={item.logId}
                      type="button"
                      disabled={disabled}
                      onClick={() => onSelectFile(item.logId)}
                      className={`flex h-16 w-full flex-col gap-1 rounded-[10px] border px-[10px] py-2 text-left ${
                        selected ? "border-[#CBD5E1] bg-white" : "border-[#E5E7EB] bg-white"
                      }`}
                    >
                      <span className="text-ellipsis font-main text-[12px] font-bold text-[#0F172A]">{item.fileName}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-ellipsis font-main text-[11px] font-semibold text-[#64748B]">
                          mtime: {item.mtimeLabel}
                        </span>
                        <span className="font-main text-[11px] font-semibold text-[#64748B]">{item.sizeLabel}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mt-2 flex h-[30px] items-center justify-center">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="flex h-[22px] w-[26px] items-center justify-center rounded-[8px] border border-[#D7DFEA] bg-[#EEF2F7]"
          aria-label={collapsed ? "展开日志文件区" : "收起日志文件区"}
        >
          {collapsed ? <ChevronRight size={12} color="#475569" /> : <ChevronLeft size={12} color="#475569" />}
        </button>
      </div>
    </section>
  );
}
