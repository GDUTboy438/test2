import { useCallback, useEffect, useState } from "react";
import { BreadcrumbRow } from "./components/layout/BreadcrumbRow";
import { DetailPanel } from "./components/layout/DetailPanel";
import { FileGrid } from "./components/layout/FileGrid";
import { FileTable } from "./components/layout/FileTable";
import { PaginationBar } from "./components/layout/PaginationBar";
import { Sidebar } from "./components/layout/Sidebar";
import { SubNav } from "./components/layout/SubNav";
import { TopNav } from "./components/layout/TopNav";
import { readRouteFromUrl, setRouteInUrl, subscribePopState, type AppRoute } from "./navigation/page-route";
import { SettingsPage } from "./pages/SettingsPage";
import { useHomeState } from "./state/use-home-state";
import type { UiMode } from "./types/domain";

function EmptyState({ loading }: { loading: boolean }) {
  return (
    <div className="flex h-full items-center justify-center rounded-xl bg-white">
      <span className="font-main text-[14px] font-semibold text-[#6B7280]">
        {loading ? "Loading media..." : "No media data available."}
      </span>
    </div>
  );
}

function HomePage({ onOpenSettings }: { onOpenSettings: () => void }) {
  const state = useHomeState();
  const contentGap = state.detailOpen ? 10 : 0;

  const mainColumnWidth = state.detailOpen
    ? `calc(100% - ${state.detailWidth + contentGap}px)`
    : "100%";

  return (
    <div className="app-page" data-mode={state.mode}>
      <div className="pvm-frame" data-mode={state.mode} data-testid="pvm-frame" data-scene={state.scene}>
        <Sidebar
          brand="VisionVault Pro"
          libraryTitle="Libraries"
          treeRoot={state.treeRoot}
          selectedDirectoryId={state.selectedDirectoryId}
          scan={state.scanProgress}
          onSelectDirectory={state.selectDirectory}
          onPickLibrary={() => {
            void state.pickLibrary();
          }}
          onOpenSettings={onOpenSettings}
          canInteract={state.canInteract}
        />

        <main className="flex h-full min-w-0 flex-1 flex-col bg-[var(--color-main-bg)]" data-testid="main-area">
          <TopNav
            searchInput={state.searchInput}
            onSearchChange={state.setSearchInput}
            onPickLibrary={() => {
              void state.pickLibrary();
            }}
            onOpenSettings={onOpenSettings}
            canInteract={state.canInteract}
          />
          <div className="h-px w-full bg-[var(--color-border)]" />

          <SubNav
            height={state.subNavHeight}
            viewMode={state.viewMode}
            filterState={state.filterState}
            statusOptions={state.statusOptions}
            resolutionOptions={state.resolutionOptions}
            sortField={state.sortField}
            sortDirection={state.sortDirection}
            canInteract={state.canInteract}
            onViewModeChange={state.setViewMode}
            onFilterChange={state.setFilterState}
            onSortFieldChange={state.setSortField}
            onSortDirectionToggle={state.toggleSortDirection}
          />
          <div className="h-px w-full bg-[var(--color-border)]" />

          <BreadcrumbRow breadcrumb={state.breadcrumb} />
          <div className="h-px w-full bg-[var(--color-border)]" />

          <section
            className="flex min-h-0 w-full flex-1 overflow-hidden bg-[var(--color-main-bg)] px-3 pb-[10px] pt-2"
            style={{ gap: `${contentGap}px` }}
            data-testid="content-wrap"
          >
            <div
              className="flex h-full min-h-0 flex-col overflow-hidden rounded-[12px] border border-[var(--color-border)] bg-[var(--color-card)]"
              style={{ width: mainColumnWidth }}
            >
              {state.viewMode === "list" ? (
                <div className="flex h-full min-h-0 flex-col overflow-hidden px-4 pb-3 pt-2">
                  {state.pageItems.length > 0 ? (
                    <div className="min-h-0 flex-1">
                      <FileTable
                        items={state.pageItems}
                        selectedId={state.selectedVideo?.id ?? null}
                        rowHeight={state.listRowHeight}
                        headerHeight={state.listHeaderHeight}
                        onSelect={state.selectVideo}
                      />
                    </div>
                  ) : (
                    <div className="min-h-0 flex-1">
                      <EmptyState loading={state.loading} />
                    </div>
                  )}

                  <div className="shrink-0">
                    <PaginationBar page={state.page} totalPages={state.totalPages} onPageChange={state.setPage} />
                  </div>
                </div>
              ) : (
                <div className="flex h-full min-h-0 flex-col overflow-hidden px-4 pb-0 pt-2">
                  {state.pageItems.length > 0 ? (
                    <>
                      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
                        <FileGrid
                          items={state.pageItems}
                          selectedId={state.selectedVideo?.id ?? null}
                          cardHeight={state.gridCardHeight}
                          onSelect={state.selectVideo}
                        />
                      </div>
                      <div className="shrink-0">
                        <PaginationBar page={state.page} totalPages={state.totalPages} onPageChange={state.setPage} />
                      </div>
                    </>
                  ) : (
                    <EmptyState loading={state.loading} />
                  )}
                </div>
              )}
            </div>

            {state.detailOpen && state.selectedVideo ? (
              <DetailPanel
                video={state.selectedVideo}
                width={state.detailWidth}
                onPlay={() => {
                  void state.playSelected();
                }}
              />
            ) : null}
          </section>

          {state.errorMessage ? (
            <div className="h-7 bg-[#FEE2E2] px-4 py-1 font-main text-[12px] font-semibold text-[#B91C1C]">
              {state.errorMessage}
            </div>
          ) : null}
        </main>
      </div>

      {state.toast ? (
        <div
          className={`fixed bottom-5 left-1/2 -translate-x-1/2 rounded-lg px-4 py-2 font-main text-[13px] font-semibold text-white ${
            state.toast.tone === "success" ? "bg-[#111827]" : "bg-[#B91C1C]"
          }`}
        >
          {state.toast.message}
        </div>
      ) : null}
    </div>
  );
}

export function App() {
  const [route, setRoute] = useState<AppRoute>(() => readRouteFromUrl());

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pageFromQuery = params.get("page");
    const moduleFromQuery = params.get("module");
    const modeFromQuery = params.get("mode");
    const normalizedMode = modeFromQuery === "visual" && params.has("scene") ? "visual" : "live";
    const needRewrite =
      pageFromQuery !== route.page ||
      (route.page === "settings" && moduleFromQuery !== route.module) ||
      modeFromQuery !== normalizedMode;

    if (needRewrite) {
      setRouteInUrl(route, true);
    }
  }, [route]);

  useEffect(() => subscribePopState(() => setRoute(readRouteFromUrl())), []);

  const navigateRoute = useCallback((nextRoute: AppRoute) => {
    setRouteInUrl(nextRoute);
    setRoute(nextRoute);
  }, []);

  if (route.page === "settings") {
    const params = new URLSearchParams(window.location.search);
    const mode: UiMode = params.get("mode") === "visual" && params.has("scene") ? "visual" : "live";
    return (
      <SettingsPage
        module={route.module}
        mode={mode}
        onModuleChange={(module) => navigateRoute({ page: "settings", module })}
        onBackToHome={() => navigateRoute({ page: "home", module: "tag-manager" })}
      />
    );
  }

  return <HomePage onOpenSettings={() => navigateRoute({ page: "settings", module: "tag-manager" })} />;
}
