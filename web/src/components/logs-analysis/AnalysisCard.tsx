import type { LogAnalysisSummary } from "../../types/domain";

type AnalysisCardProps = {
  summary: LogAnalysisSummary;
  sourceLabel: string;
};

function StatCell({
  title,
  value,
  valueClass,
}: {
  title: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex h-full flex-1 flex-col gap-0.5 rounded-[10px] bg-[#F8FAFC] px-2 py-1.5">
      <span className="font-main text-[11px] font-semibold text-[#64748B]">{title}</span>
      <span className={`font-main text-[12px] font-bold text-[#0F172A] ${valueClass ?? ""}`}>{value}</span>
    </div>
  );
}

export function AnalysisCard({ summary, sourceLabel }: AnalysisCardProps) {
  return (
    <section className="flex h-[108px] flex-col gap-[10px] rounded-[14px] border border-[#E5E7EB] bg-white px-[14px] py-3">
      <div className="flex h-[26px] items-center justify-between">
        <span className="font-main text-[14px] font-bold text-[#111827]">日志分析</span>
        <span className="inline-flex h-6 items-center rounded-full border border-[#C7D2FE] bg-[#EEF2FF] px-2.5 font-main text-[11px] font-bold text-[#3730A3]">
          当前来源 {sourceLabel}
        </span>
      </div>

      <div className="flex h-[46px] gap-2">
        <StatCell title="总事件数" value={String(summary.total)} />
        <StatCell title="错误数" value={String(summary.errorCount)} valueClass="text-[#991B1B]" />
        <StatCell title="解析错误" value={String(summary.parseErrorCount)} valueClass="text-[#B45309]" />
        <StatCell title="最近错误" value={summary.lastErrorLabel || "--"} />
        <StatCell title="当前来源" value={summary.source} />
      </div>
    </section>
  );
}
