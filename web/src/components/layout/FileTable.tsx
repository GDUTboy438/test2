import type { VideoItem } from "../../types/domain";

const HEADER = ["File", "Duration", "Resolution", "Size", "Modified", "Status"];
const TABLE_COLUMNS = "84px minmax(300px,1fr) 100px 90px 90px 100px 110px";

type FileTableProps = {
  items: VideoItem[];
  selectedId: string | null;
  rowHeight: 86 | 94;
  headerHeight: 50 | 54;
  onSelect: (id: string) => void;
};

function StatusPill({ status }: { status: string }) {
  const isScanning = status.toLowerCase().includes("scan");
  return (
    <span
      className={`inline-flex h-6 items-center rounded-[14px] px-[10px] font-main text-[12px] font-bold ${
        isScanning ? "bg-[#DBEAFE] text-[#1D4ED8]" : "bg-[var(--color-pill)] text-[#374151]"
      }`}
    >
      {status}
    </span>
  );
}

function Thumbnail({ url }: { url: string | null }) {
  if (!url) {
    return <div className="h-[50px] w-[84px] rounded-lg bg-[#D1D5DB]" />;
  }
  return <img src={url} alt="thumb" className="h-[50px] w-[84px] rounded-lg object-cover" />;
}

export function FileTable({
  items,
  selectedId,
  rowHeight,
  headerHeight,
  onSelect,
}: FileTableProps) {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-transparent pt-2" data-testid="table-card">
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain" style={{ scrollbarGutter: "stable" }}>
        <div
          className="sticky top-0 z-10 grid shrink-0 items-center gap-[10px] bg-[var(--color-main-bg)] px-[18px]"
          style={{
            gridTemplateColumns: TABLE_COLUMNS,
            height: `${headerHeight}px`,
          }}
        >
          <span />
          {HEADER.map((item) => (
            <span key={item} className="font-main text-[13px] font-bold text-[#4B5563]">
              {item}
            </span>
          ))}
        </div>

        {items.map((row) => {
          const selected = selectedId === row.id;
          return (
            <button
              key={row.id}
              type="button"
              onClick={() => onSelect(row.id)}
              className={`grid w-full items-center gap-[10px] border-none px-[18px] text-left ${
                selected ? "bg-[#EEF2F7]" : "bg-white"
              }`}
              style={{
                gridTemplateColumns: TABLE_COLUMNS,
                height: `${rowHeight}px`,
              }}
            >
              <Thumbnail url={row.thumbUrl} />

              <div className="leading-[1.35]">
                <div className="text-ellipsis font-main text-[13px] font-semibold text-[#374151]">{row.name}</div>
                <div className="text-ellipsis font-main text-[12px] font-semibold text-[#6B7280]">{row.path}</div>
              </div>

              <span className="font-main text-[13px] font-normal text-[#4B5563]">{row.duration}</span>
              <span className="font-main text-[12px] font-bold text-[#374151]">{row.resolution}</span>
              <span className="font-main text-[13px] font-normal text-[#4B5563]">{row.size}</span>
              <span className="font-main text-[13px] font-normal text-[#4B5563]">{row.modified}</span>
              <StatusPill status={row.status} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
