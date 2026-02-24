import { X } from "lucide-react";
import type { LogEventItem } from "../../types/domain";

type EventDetailDrawerProps = {
  open: boolean;
  event: LogEventItem | null;
  onClose: () => void;
  widthCss?: string;
};

export function EventDetailDrawer({ open, event, onClose, widthCss = "400px" }: EventDetailDrawerProps) {
  if (!open) {
    return null;
  }

  const payloadJson = event ? JSON.stringify(event.payload, null, 2) : "{}";
  const selectedLabel = event ? `${event.timeLabel} ${event.event}` : "--";

  return (
    <aside
      className="flex h-full min-w-0 shrink-0 flex-col gap-[10px] rounded-[12px] border border-[#E5E7EB] bg-[#F8FAFC] p-3"
      style={{ width: widthCss }}
      data-testid="event-detail-panel"
    >
      <div className="flex h-[34px] items-center justify-between">
        <span className="font-main text-[13px] font-bold text-[#111827]">事件详情</span>
        <button
          type="button"
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-[10px] border border-[#CBD5E1] bg-[#EEF2F7]"
          aria-label="关闭事件详情"
        >
          <X size={14} color="#334155" />
        </button>
      </div>

      <div className="flex h-[22px] items-center justify-between">
        <span className="font-main text-[11px] font-bold text-[#334155]">已选中: {selectedLabel}</span>
        <span className="font-main text-[11px] font-semibold text-[#64748B]">row.payload</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto rounded-[10px] border border-[#1E293B] bg-[#0B122B] p-3">
        <pre className="m-0 whitespace-pre-wrap break-all font-mono text-[11px] font-semibold text-white">{payloadJson}</pre>
      </div>
    </aside>
  );
}
