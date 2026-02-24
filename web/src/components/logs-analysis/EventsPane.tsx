import type { LogEventItem, LogsFilterState } from "../../types/domain";
import { EventDetailDrawer } from "./EventDetailDrawer";
import { LogsPaginationBar } from "./LogsPaginationBar";

type EventsPaneProps = {
  filters: LogsFilterState;
  levelOptions: string[];
  eventOptions: string[];
  events: LogEventItem[];
  total: number;
  page: number;
  pageSize: number;
  selectedLineNo: number | null;
  detailOpen: boolean;
  detailEvent: LogEventItem | null;
  disabled: boolean;
  onKeywordChange: (value: string) => void;
  onLevelChange: (value: string) => void;
  onEventChange: (value: string) => void;
  onClearFilters: () => void;
  onSelectEvent: (lineNo: number) => void;
  onOpenDetail: (lineNo: number) => void;
  onCloseDetail: () => void;
  onPageChange: (page: number) => void;
};

const TABLE_TEMPLATE = "110px 76px 176px 200px minmax(260px,1fr)";

function EventTableRows({
  events,
  selectedLineNo,
  onSelectEvent,
  onOpenDetail,
}: {
  events: LogEventItem[];
  selectedLineNo: number | null;
  onSelectEvent: (lineNo: number) => void;
  onOpenDetail: (lineNo: number) => void;
}) {
  if (events.length === 0) {
    return (
      <div className="flex h-full items-center justify-center font-main text-[13px] font-semibold text-[#94A3B8]">
        暂无事件
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {events.map((item) => {
        const selected = item.lineNo === selectedLineNo;
        const parseError = item.event.toLowerCase() === "parse_error";
        return (
          <button
            key={`${item.lineNo}-${item.timeLabel}`}
            type="button"
            onClick={() => onSelectEvent(item.lineNo)}
            onDoubleClick={() => onOpenDetail(item.lineNo)}
            className={`grid h-[34px] w-full items-center gap-3 rounded-[8px] border px-[10px] text-left ${
              parseError
                ? "border-[#FDBA74] bg-[#FFF7ED]"
                : selected
                  ? "border-[#CBD5E1] bg-white"
                  : "border-[#E5E7EB] bg-white"
            }`}
            style={{ gridTemplateColumns: TABLE_TEMPLATE }}
          >
            <span className={`font-main text-[11px] font-semibold ${parseError ? "text-[#7C2D12]" : "text-[#0F172A]"}`}>
              {item.timeLabel}
            </span>
            <span
              className={`font-main text-[11px] font-bold ${
                item.level === "error" ? "text-[#B91C1C]" : "text-[#0F766E]"
              }`}
            >
              {item.level}
            </span>
            <span className={`truncate font-main text-[11px] font-semibold ${parseError ? "text-[#7C2D12]" : "text-[#0F172A]"}`}>
              {item.event}
            </span>
            <span className={`truncate font-main text-[11px] font-semibold ${parseError ? "text-[#7C2D12]" : "text-[#334155]"}`}>
              {item.relPath || "-"}
            </span>
            <span className={`truncate font-main text-[11px] font-semibold ${parseError ? "text-[#7C2D12]" : "text-[#334155]"}`}>
              {item.summary}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function EventsPane({
  filters,
  levelOptions,
  eventOptions,
  events,
  total,
  page,
  pageSize,
  selectedLineNo,
  detailOpen,
  detailEvent,
  disabled,
  onKeywordChange,
  onLevelChange,
  onEventChange,
  onClearFilters,
  onSelectEvent,
  onOpenDetail,
  onCloseDetail,
  onPageChange,
}: EventsPaneProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const levelChoices = filters.level && !levelOptions.includes(filters.level) ? [filters.level, ...levelOptions] : levelOptions;
  const eventChoices = filters.event && !eventOptions.includes(filters.event) ? [filters.event, ...eventOptions] : eventOptions;
  const detailWidthCss = detailOpen ? "clamp(300px, 28vw, 400px)" : "0px";
  const mainColumnWidth = detailOpen ? `calc(100% - ${detailWidthCss} - 16px)` : "100%";

  return (
    <section
      className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 rounded-[14px] border border-[#E5E7EB] bg-white p-[14px]"
      data-testid="logs-events-pane"
    >
      <div className="flex min-h-[38px] flex-wrap items-center gap-2">
        <label className="flex h-9 min-w-[240px] flex-1 items-center rounded-[10px] border border-[#E2E8F0] bg-[#F8FAFC] px-3">
          <input
            value={filters.q}
            disabled={disabled}
            onChange={(event) => onKeywordChange(event.target.value)}
            placeholder="关键字搜索（事件/路径/摘要）"
            className="h-full w-full border-none bg-transparent font-main text-[12px] font-semibold text-[#334155] outline-none placeholder:text-[#94A3B8]"
          />
        </label>

        <select
          value={filters.level}
          disabled={disabled}
          onChange={(event) => onLevelChange(event.target.value)}
          className="h-9 rounded-[10px] border border-[#CBD5E1] bg-[#F8FAFC] px-[10px] font-main text-[11px] font-bold text-[#334155]"
        >
          <option value="">Level: all</option>
          {levelChoices.map((option) => (
            <option key={option} value={option}>
              Level: {option}
            </option>
          ))}
        </select>

        <select
          value={filters.event}
          disabled={disabled}
          onChange={(event) => onEventChange(event.target.value)}
          className="h-9 rounded-[10px] border border-[#CBD5E1] bg-[#F8FAFC] px-[10px] font-main text-[11px] font-bold text-[#334155]"
        >
          <option value="">Event: all</option>
          {eventChoices.map((option) => (
            <option key={option} value={option}>
              Event: {option}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={onClearFilters}
          disabled={disabled}
          className={`h-9 rounded-[10px] border border-[#CBD5E1] bg-[#F8FAFC] px-[10px] font-main text-[11px] font-bold text-[#334155] ${
            disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-[#94A3B8]"
          }`}
        >
          清空筛选
        </button>
      </div>

      <div className={`flex min-h-0 min-w-0 flex-1 overflow-hidden ${detailOpen ? "gap-4" : ""}`}>
        <div className="flex min-h-0 min-w-0 flex-col gap-3" style={{ width: mainColumnWidth }} data-testid="events-main-column">
          <div
            className="flex min-h-0 flex-1 flex-col rounded-[12px] border border-[#E5E7EB] bg-[#F8FAFC] p-[10px]"
            data-testid="events-table-card"
          >
            <div className="min-h-0 flex-1 overflow-x-auto">
              <div className="flex h-full min-w-[822px] flex-col">
                <div
                  className="grid h-8 shrink-0 items-center gap-3 rounded-[8px] bg-[#EEF2F7] px-[10px] font-main text-[11px] font-bold text-[#475569]"
                  style={{ gridTemplateColumns: TABLE_TEMPLATE }}
                >
                  <span>时间</span>
                  <span>级别</span>
                  <span>事件</span>
                  <span>路径</span>
                  <span>摘要</span>
                </div>

                <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain pt-2">
                  <EventTableRows
                    events={events}
                    selectedLineNo={selectedLineNo}
                    onSelectEvent={onSelectEvent}
                    onOpenDetail={onOpenDetail}
                  />
                </div>
              </div>
            </div>
          </div>

          <LogsPaginationBar
            page={page}
            totalPages={totalPages}
            disabled={disabled}
            onPageChange={onPageChange}
          />
        </div>

        <EventDetailDrawer open={detailOpen} event={detailEvent} onClose={onCloseDetail} widthCss={detailWidthCss} />
      </div>
    </section>
  );
}
