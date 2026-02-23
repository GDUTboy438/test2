import { AccordionStack } from "../components/tag-manager/AccordionStack";
import { GlobalSearchCard } from "../components/tag-manager/GlobalSearchCard";
import { SettingsSidebar } from "../components/tag-manager/SettingsSidebar";
import { TagManagerHeader } from "../components/tag-manager/TagManagerHeader";
import { UnifiedSearchResults } from "../components/tag-manager/UnifiedSearchResults";
import { useTagManagerState } from "../state/use-tag-manager-state";

type TagManagerPageProps = {
  onBackToHome: () => void;
};

export function TagManagerPage({ onBackToHome }: TagManagerPageProps) {
  const state = useTagManagerState();

  return (
    <div className="app-page" data-mode={state.mode}>
      <div className="pvm-frame" data-mode={state.mode} data-testid="pvm-frame" data-scene={state.scene}>
        <SettingsSidebar brand="VisionVault Pro" />

        <main className="flex min-w-0 flex-1 flex-col bg-[#F3F4F6]">
          <TagManagerHeader onBackToLibrary={onBackToHome} disabled={state.loading} />
          <div className="h-px w-full bg-[#D1D5DB]" />

          <section className="flex min-h-0 flex-1 flex-col gap-[14px] px-4 pb-6 pt-4">
            <GlobalSearchCard
              query={state.searchInput}
              source={state.source}
              matchCount={state.globalMatchCount}
              showUnified={state.showUnified}
              disabled={!state.canInteract}
              onQueryChange={state.setSearchInput}
              onSourceChange={state.setSource}
            />

            {state.showUnified ? (
              <UnifiedSearchResults
                tagLibrary={state.visibleTagLibrary}
                candidates={state.visibleCandidates}
                blacklist={state.visibleBlacklist}
                selectedTagIds={state.selectedTagIds}
                selectedCandidateIds={state.selectedCandidateIds}
                selectedBlacklistIds={state.selectedBlacklistIds}
                onToggleTag={state.toggleTagSelection}
                onToggleCandidate={state.toggleCandidateSelection}
                onToggleBlacklist={state.toggleBlacklistSelection}
                onDeleteOneTag={state.deleteTagById}
              />
            ) : (
              <AccordionStack
                activeSection={state.activeSection}
                canInteract={state.canInteract}
                tagLibrary={state.tagLibrary}
                candidates={state.candidates}
                blacklist={state.blacklist}
                selectedTagIds={state.selectedTagIds}
                selectedCandidateIds={state.selectedCandidateIds}
                selectedBlacklistIds={state.selectedBlacklistIds}
                onSetSection={state.setActiveSection}
                onToggleTag={state.toggleTagSelection}
                onToggleCandidate={state.toggleCandidateSelection}
                onToggleBlacklist={state.toggleBlacklistSelection}
                onAddTags={state.addTags}
                onDeleteOneTag={state.deleteTagById}
                onDeleteSelectedTags={state.deleteSelectedTags}
                onSelectAllTags={state.selectAllTags}
                onApproveCandidates={state.approveSelectedCandidates}
                onRejectCandidates={state.rejectSelectedCandidates}
                onBlacklistCandidates={state.blacklistSelectedCandidates}
                onRequeueCandidates={state.requeueSelectedCandidates}
                onClearPendingCandidates={state.clearPendingCandidates}
              />
            )}
          </section>

          {state.errorMessage ? (
            <div className="h-8 bg-[#FEE2E2] px-6 py-1 font-main text-[13px] font-semibold text-[#B91C1C]">
              {state.errorMessage}
            </div>
          ) : null}
        </main>
      </div>

      {state.toast ? (
        <div
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 rounded-xl px-4 py-2 font-main text-[13px] font-semibold text-white ${
            state.toast.tone === "success" ? "bg-[#111827]" : "bg-[#B91C1C]"
          }`}
        >
          {state.toast.message}
        </div>
      ) : null}
    </div>
  );
}
