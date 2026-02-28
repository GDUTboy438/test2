import { FeatureExtractionPageContent } from "../components/feature-extraction/FeatureExtractionPageContent";
import { LogsAnalysisPageContent } from "../components/logs-analysis/LogsAnalysisPageContent";
import { SettingsSidebar } from "../components/tag-manager/SettingsSidebar";
import { TagManagerHeader } from "../components/tag-manager/TagManagerHeader";
import { TagManagerPageContent } from "./TagManagerPage";
import type { SettingsModule, UiMode } from "../types/domain";

type SettingsPageProps = {
  module: SettingsModule;
  mode: UiMode;
  onModuleChange: (module: SettingsModule) => void;
  onBackToHome: () => void;
};

const HEADER_META: Record<SettingsModule, { title: string; subtitle: string; scene: "J7vS3" | "CIBf0" | "FEx01" }> = {
  "tag-manager": {
    title: "标签管理",
    subtitle: "标签的创建、检索与批量维护。",
    scene: "J7vS3",
  },
  "feature-extraction": {
    title: "特征提取",
    subtitle: "模型切换、任务执行与本地模型管理。",
    scene: "FEx01",
  },
  "logs-analysis": {
    title: "日志分析",
    subtitle: "聚合扫描、标签提取与项目运行日志。",
    scene: "CIBf0",
  },
};

export function SettingsPage({ module, mode, onModuleChange, onBackToHome }: SettingsPageProps) {
  const meta = HEADER_META[module];
  const sceneParam = new URLSearchParams(window.location.search).get("scene");
  const activeScene =
    module === "logs-analysis" && (sceneParam === "CIBf0" || sceneParam === "Hyzda")
      ? sceneParam
      : module === "feature-extraction" && (sceneParam === "FEx01" || sceneParam === "hFUDa")
        ? sceneParam
        : meta.scene;

  return (
    <div className="app-page" data-mode={mode}>
      <div className="pvm-frame" data-mode={mode} data-testid="pvm-frame" data-scene={activeScene}>
        <SettingsSidebar brand="VisionVault Pro" activeModule={module} onModuleChange={onModuleChange} />

        <main className="flex min-w-0 flex-1 flex-col bg-[#F8FAFC]">
          <TagManagerHeader title={meta.title} subtitle={meta.subtitle} onBackToLibrary={onBackToHome} />
          <div className="h-px w-full bg-[#E5E7EB]" />

          {module === "tag-manager" ? (
            <TagManagerPageContent />
          ) : module === "feature-extraction" ? (
            <FeatureExtractionPageContent />
          ) : (
            <LogsAnalysisPageContent />
          )}
        </main>
      </div>
    </div>
  );
}
