import { LayoutGrid, Settings } from "lucide-react";

type SettingsSidebarProps = {
  brand: string;
};

type ModuleStatus = {
  label: string;
  hint: string;
  active?: boolean;
};

const MODULES: ModuleStatus[] = [
  { label: "用户登录", hint: "规划中" },
  { label: "标签管理", hint: "服务就绪/API待接入", active: true },
  { label: "资源库来源", hint: "部分支持" },
  { label: "特征提取", hint: "部分支持" },
  { label: "模型管理", hint: "工具可用/API待接入" },
  { label: "电子书模式", hint: "规划中" },
  { label: "任务与日志", hint: "服务就绪/API待接入" },
  { label: "数据与备份", hint: "规划中" },
];

function StatusBadge({ text, active }: { text: string; active: boolean }) {
  return (
    <span
      className={`inline-flex h-[22px] items-center rounded-full px-2 font-sidebar text-[11px] font-bold leading-none ${
        active ? "bg-[#334155] text-[#D6E4FF]" : "bg-[#374151] text-[#E5E7EB]"
      }`}
    >
      {text}
    </span>
  );
}

export function SettingsSidebar({ brand }: SettingsSidebarProps) {
  return (
    <aside className="flex h-full w-[310px] flex-col bg-[#111827]" data-testid="tag-manager-settings-sidebar">
      <div className="flex h-[88px] items-center gap-3 px-[18px]">
        <div className="flex h-9 w-9 items-center justify-center rounded-[11px] bg-[#1F2937]">
          <LayoutGrid size={16} color="#E5E7EB" />
        </div>
        <span className="font-sidebar text-[16px] font-bold leading-none text-[#E5E7EB]">{brand}</span>
      </div>

      <div className="h-px w-full bg-[#FFFFFF1F]" />

      <div className="flex min-h-0 flex-1 flex-col gap-[10px] px-3 pb-3 pt-[14px]">
        <div className="flex h-8 items-center">
          <span className="font-sidebar text-[16px] font-bold leading-none text-[#D1D5DB]">设置模块</span>
        </div>

        <div className="h-px w-full bg-[#FFFFFF1F]" />

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <nav className="min-h-0 flex-1 space-y-[10px] overflow-y-auto pr-1 pt-3">
            {MODULES.map((module) => (
              <button
                key={module.label}
                type="button"
                className={`flex h-[46px] w-full items-center justify-between rounded-[10px] border-none px-3 text-left ${
                  module.active ? "bg-[#9CA3AF33]" : "bg-transparent"
                }`}
              >
                <span
                  className={`font-sidebar text-[14px] font-bold ${module.active ? "text-[#F3F4F6]" : "text-[#D1D5DB]"}`}
                >
                  {module.label}
                </span>
                <StatusBadge text={module.hint} active={Boolean(module.active)} />
              </button>
            ))}
          </nav>

          <div className="mt-[10px] shrink-0 flex flex-col gap-[10px]">
            <div className="h-px w-full bg-[#FFFFFF1F]" />

            <div className="flex h-[86px] items-center justify-between px-4">
              <div className="flex h-14 w-[200px] items-center gap-[10px] rounded-xl bg-[#1A2431] px-[10px]">
                <div className="h-9 w-9 rounded-full bg-[#303030]" />
                <div className="flex flex-col gap-[2px]">
                  <span className="font-sidebar text-[13px] font-bold text-[#E5E7EB]">Admin</span>
                  <span className="font-sidebar text-[11px] font-semibold text-[#94A3B8]">Local Library</span>
                </div>
              </div>

              <button
                type="button"
                className="flex h-10 w-10 items-center justify-center rounded-full border-none bg-[#2A3648] p-0"
                aria-label="settings"
              >
                <Settings size={18} strokeWidth={2.2} color="#D1D5DB" />
              </button>
            </div>

            <div className="flex h-14 flex-col gap-[6px] rounded-xl bg-[#1A2431] px-[14px] py-2">
              <div className="flex h-5 items-center justify-between">
                <span className="text-ellipsis font-sidebar text-[11px] font-semibold text-[#94A3B8]">
                  Scanning /videos/library…
                </span>
                <span className="font-sidebar text-[11px] font-bold text-[#E5E7EB]">47%</span>
              </div>
              <div className="h-1 w-full rounded bg-[#2F3B4E]">
                <div className="h-1 rounded bg-[#3B82F6]" style={{ width: "47%" }} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
