import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";

type PaginationBarProps = {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
};

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function buildPageButtons(page: number, totalPages: number): number[] {
  const maxButtons = Math.min(5, totalPages);
  const start = clamp(page - 2, 1, Math.max(1, totalPages - maxButtons + 1));
  return Array.from({ length: maxButtons }, (_, index) => start + index);
}

export function PaginationBar({ page, totalPages, onPageChange }: PaginationBarProps) {
  const [jumpInput, setJumpInput] = useState("");
  const pageButtons = useMemo(() => buildPageButtons(page, totalPages), [page, totalPages]);

  return (
    <div className="flex h-[52px] items-center justify-center border-t border-[var(--color-border)] bg-white px-4">
      <div className="flex items-center gap-[6px]">
        <button
          type="button"
          onClick={() => onPageChange(clamp(page - 1, 1, totalPages))}
          className="flex h-8 w-8 items-center justify-center rounded-lg border-none bg-[#F3F4F6]"
          aria-label="prev page"
        >
          <ChevronLeft size={14} color="#4B5563" />
        </button>

        {pageButtons.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => onPageChange(item)}
            className={`flex h-8 w-8 items-center justify-center rounded-lg border-none font-main text-[13px] font-bold ${
              item === page ? "bg-[#111827] text-white" : "bg-[#F3F4F6] text-[#4B5563]"
            }`}
          >
            {item}
          </button>
        ))}

        <button
          type="button"
          onClick={() => onPageChange(clamp(page + 1, 1, totalPages))}
          className="flex h-8 w-8 items-center justify-center rounded-lg border-none bg-[#F3F4F6]"
          aria-label="next page"
        >
          <ChevronRight size={14} color="#4B5563" />
        </button>

        <input
          value={jumpInput}
          onChange={(event) => setJumpInput(event.target.value.replace(/[^0-9]/g, ""))}
          className="h-8 w-11 rounded-lg border border-[var(--color-border)] bg-white px-2 text-center font-main text-[13px] text-[#4B5563] outline-none"
          aria-label="jump page"
        />

        <button
          type="button"
          onClick={() => {
            const value = Number.parseInt(jumpInput, 10);
            if (Number.isNaN(value)) {
              return;
            }
            onPageChange(clamp(value, 1, totalPages));
            setJumpInput("");
          }}
          className="h-8 rounded-lg border-none bg-[#111827] px-3 font-main text-[12px] font-bold text-white"
        >
          GO
        </button>
      </div>
    </div>
  );
}
