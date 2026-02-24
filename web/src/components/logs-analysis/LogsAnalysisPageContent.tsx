import { AnalysisCard } from "./AnalysisCard";
import { EventsPane } from "./EventsPane";
import { LogFilesPane } from "./LogFilesPane";
import { useLogsAnalysisState } from "../../state/use-logs-analysis-state";

export function LogsAnalysisPageContent() {
  const state = useLogsAnalysisState();
  const leftPaneWidthCss = state.leftPaneCollapsed
    ? "56px"
    : state.detailOpen
      ? "clamp(240px, 22vw, 320px)"
      : "clamp(260px, 24vw, 360px)";
  const eventsPaneWidthCss = `calc(100% - ${leftPaneWidthCss} - 12px)`;

  return (
    <>
      <section className="flex min-h-0 flex-1 flex-col gap-[14px] px-4 pb-6 pt-4">
        <AnalysisCard
          summary={state.analysis}
          sourceLabel={state.sourceOptions.find((item) => item.source === state.source)?.label ?? state.source}
        />

        <div className="flex min-h-0 min-w-0 flex-1 gap-3 overflow-hidden">
          <LogFilesPane
            paneWidthCss={leftPaneWidthCss}
            source={state.source}
            sourceOptions={state.sourceOptions}
            files={state.files}
            selectedLogId={state.selectedLogId}
            collapsed={state.leftPaneCollapsed}
            disabled={!state.canInteract}
            onSourceChange={state.setSource}
            onSelectFile={state.selectFile}
            onRefresh={() => {
              void state.refreshFiles();
            }}
            onLoadLatest={() => {
              void state.loadLatest();
            }}
            onToggleCollapse={state.toggleLeftPane}
          />

          <div className="min-h-0 min-w-0 shrink-0" style={{ width: eventsPaneWidthCss }}>
            <EventsPane
              filters={state.filters}
              levelOptions={state.levelOptions}
              eventOptions={state.eventOptions}
              events={state.events}
              total={state.total}
              page={state.page}
              pageSize={state.pageSize}
              selectedLineNo={state.selectedEventLineNo}
              detailOpen={state.detailOpen}
              detailEvent={state.detailEvent}
              disabled={!state.canInteract}
              onKeywordChange={state.setKeyword}
              onLevelChange={state.setLevel}
              onEventChange={state.setEvent}
              onClearFilters={state.clearFilters}
              onSelectEvent={state.selectEvent}
              onOpenDetail={state.openEventDetail}
              onCloseDetail={state.closeDetailDrawer}
              onPageChange={state.setPage}
            />
          </div>
        </div>
      </section>

      {state.errorMessage ? (
        <div className="h-8 bg-[#FEE2E2] px-6 py-1 font-main text-[13px] font-semibold text-[#B91C1C]">
          {state.errorMessage}
        </div>
      ) : null}

      {state.toast ? (
        <div
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 rounded-xl px-4 py-2 font-main text-[13px] font-semibold text-white ${
            state.toast.tone === "success" ? "bg-[#111827]" : "bg-[#B91C1C]"
          }`}
        >
          {state.toast.message}
        </div>
      ) : null}
    </>
  );
}
