import { Folder } from "lucide-react";

type BreadcrumbRowProps = {
  breadcrumb: string;
};

export function BreadcrumbRow({ breadcrumb }: BreadcrumbRowProps) {
  return (
    <div className="flex h-10 items-center bg-white px-6" data-testid="breadcrumb-row">
      <div className="flex h-5 items-center gap-[6px]">
        <Folder size={12} color="#9CA3AF" />
        <span className="font-main text-[13px] font-semibold text-[#6B7280]">{breadcrumb}</span>
      </div>
    </div>
  );
}
