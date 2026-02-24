import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";

type LogsPaginationBarProps = {
  page: number;
  totalPages: number;
  disabled: boolean;
  onPageChange: (page: number) => void;
};

type PageToken = number | "ellipsis";

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function buildPageTokens(page: number, totalPages: number): PageToken[] {
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const start = clamp(page - 1, 1, totalPages - 2);
  const windowPages = [start, start + 1, start + 2].filter((value) => value >= 1 && value <= totalPages);
  const tokens: PageToken[] = [];

  if (start > 1) {
    tokens.push(1);
  }
  if (start > 2) {
    tokens.push("ellipsis");
  }
  for (const value of windowPages) {
    if (!tokens.includes(value)) {
      tokens.push(value);
    }
  }
  const lastWindowValue = windowPages[windowPages.length - 1] ?? 1;
  if (lastWindowValue < totalPages - 1) {
    tokens.push("ellipsis");
  }
  if (lastWindowValue < totalPages) {
    tokens.push(totalPages);
  }

  return tokens;
}

function PageButton({
  active,
  children,
  disabled,
  onClick,
}: {
  active?: boolean;
  children: ReactNode;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`flex h-8 min-w-8 items-center justify-center rounded-lg px-2 font-main text-[13px] font-bold ${
        active ? "bg-[#111827] text-white" : "bg-[#F3F4F6] text-[#4B5563]"
      } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
    >
      {children}
    </button>
  );
}

export function LogsPaginationBar({ page, totalPages, disabled, onPageChange }: LogsPaginationBarProps) {
  const [jumpInput, setJumpInput] = useState("");
  const tokens = useMemo(() => buildPageTokens(page, totalPages), [page, totalPages]);

  return (
    <div
      className="flex h-14 shrink-0 items-center justify-center rounded-[10px] border border-[#E5E7EB] bg-white px-[10px]"
      data-testid="events-pagination-dock"
    >
      <div className="max-w-full overflow-x-auto">
        <div className="flex min-w-max items-center gap-2">
        <PageButton
          disabled={disabled || page <= 1}
          onClick={() => onPageChange(clamp(page - 1, 1, totalPages))}
        >
          <ChevronLeft size={14} />
        </PageButton>

        <PageButton
          disabled={disabled || page >= totalPages}
          onClick={() => onPageChange(clamp(page + 1, 1, totalPages))}
        >
          <ChevronRight size={14} />
        </PageButton>

        {tokens.map((token, index) =>
          token === "ellipsis" ? (
            <PageButton key={`ellipsis-${index}`} disabled>
              ...
            </PageButton>
          ) : (
            <PageButton
              key={token}
              active={token === page}
              disabled={disabled}
              onClick={() => onPageChange(token)}
            >
              {token}
            </PageButton>
          ),
        )}

        <input
          value={jumpInput}
          disabled={disabled}
          onChange={(event) => setJumpInput(event.target.value.replace(/[^0-9]/g, ""))}
          className="h-8 w-11 rounded-lg border border-[#E5E7EB] bg-white px-2 text-center font-main text-[13px] font-bold text-[#4B5563] outline-none"
          aria-label="jump page"
        />

        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            const value = Number.parseInt(jumpInput, 10);
            if (Number.isNaN(value)) {
              return;
            }
            onPageChange(clamp(value, 1, totalPages));
            setJumpInput("");
          }}
          className={`h-8 rounded-lg bg-[#111827] px-3 font-main text-[12px] font-bold text-white ${
            disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
          }`}
        >
          GO
        </button>
        </div>
      </div>
    </div>
  );
}
