import type { VideoItem } from "../../types/domain";

type FileGridProps = {
  items: VideoItem[];
  selectedId: string | null;
  cardHeight: 208 | 206;
  onSelect: (id: string) => void;
};

function StatusText({ status }: { status: string }) {
  const isScanning = status.toLowerCase().includes("scan");
  return (
    <span className={`font-main text-[11px] font-semibold ${isScanning ? "text-[#1D4ED8]" : "text-[#5A4F42]"}`}>
      {status}
    </span>
  );
}

export function FileGrid({ items, selectedId, cardHeight, onSelect }: FileGridProps) {
  return (
    <div className="grid h-full grid-cols-5 gap-4 pb-1" data-testid="grid-body">
      {items.map((item) => {
        const selected = selectedId === item.id;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            className={`flex h-full w-full flex-col gap-2 rounded-lg border px-0 py-0 text-left ${
              selected ? "border-[#1D4ED8] bg-[#F8FAFC]" : "border-transparent bg-white"
            }`}
            style={{ height: `${cardHeight}px` }}
          >
            {item.thumbUrl ? (
              <img src={item.thumbUrl} alt="thumb" className="h-[120px] w-full rounded-lg object-cover" />
            ) : (
              <div className="h-[120px] w-full rounded-lg bg-[#D1D5DB]" />
            )}

            <div className="px-1">
              <div className="text-ellipsis font-main text-[11px] font-semibold text-[#374151]">{item.name}</div>
              <StatusText status={item.status} />
            </div>
          </button>
        );
      })}
    </div>
  );
}
