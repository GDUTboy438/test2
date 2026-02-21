import { Play } from "lucide-react";
import type { VideoItem } from "../../types/domain";

type DetailPanelProps = {
  video: VideoItem;
  width: number;
  onPlay: () => void;
};

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex h-[22px] items-center justify-between">
      <span className="font-main text-[13px] font-medium text-[#6B7280]">{label}</span>
      <span className="font-main text-[13px] font-bold text-[#374151]">{value}</span>
    </div>
  );
}

export function DetailPanel({ video, width, onPlay }: DetailPanelProps) {
  const displayTags = video.tags.slice(0, 3);

  return (
    <aside className="h-full bg-[var(--color-main-bg)] p-2" style={{ width: `${width}px` }} data-testid="detail-column">
      <div className="flex h-full flex-col gap-3 rounded-xl bg-[var(--color-card)] p-4">
        <h2 className="m-0 font-main text-[16px] font-bold text-[#1F2937]">Video Details</h2>

        <div className="h-px w-full bg-[var(--color-border-soft)]" />

        {video.thumbUrl ? (
          <img src={video.thumbUrl} alt="video thumbnail" className="h-[200px] w-full rounded-xl object-cover" />
        ) : (
          <div className="h-[200px] w-full rounded-xl bg-[#C5CAD1]" />
        )}

        <div className="text-ellipsis font-main text-[14px] font-bold text-[#1F2937]">{video.name}</div>

        <div className="flex flex-col gap-2">
          <MetaRow label="Duration" value={video.duration} />
          <MetaRow label="Resolution" value={video.resolution} />
          <MetaRow label="Size" value={video.size} />
          <MetaRow label="Modified" value={video.modified} />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="font-main text-[12px] font-semibold text-[#6B7280]">Tag:</span>
          {displayTags.length > 0 ? displayTags.map((tag) => (
            <span
              key={tag}
              className="inline-flex h-7 items-center justify-center rounded-[14px] bg-[var(--color-pill)] px-[10px] font-main text-[12px] font-bold text-[#4B5563]"
            >
              {tag}
            </span>
          )) : (
            <span className="font-main text-[12px] font-semibold text-[#9CA3AF]">--</span>
          )}
        </div>

        <div className="font-main text-[11px] font-semibold text-[#9CA3AF]">Path: {video.path}</div>

        <div className="flex-1" />

        <button
          type="button"
          onClick={onPlay}
          className="flex h-[38px] w-full items-center justify-center gap-[6px] rounded-[10px] border-none bg-[var(--color-primary)] font-main text-[13px] font-bold text-white"
        >
          <Play size={14} fill="white" />
          Play
        </button>
      </div>
    </aside>
  );
}
