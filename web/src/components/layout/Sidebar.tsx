import { ChevronDown, ChevronRight, Folder, Plus, Settings } from "lucide-react";
import type { DirectoryNode, ScanProgressInfo } from "../../types/domain";

type SidebarProps = {
  brand: string;
  libraryTitle: string;
  treeRoot: DirectoryNode | null;
  selectedDirectoryId: string;
  scan: ScanProgressInfo;
  onSelectDirectory: (id: string) => void;
  onPickLibrary: () => void;
  onOpenSettings: () => void;
  canInteract: boolean;
};

type TreeRowProps = {
  id: string;
  label: string;
  level: number;
  active: boolean;
  hasChildren: boolean;
  expanded: boolean;
  onClick: (id: string) => void;
  canInteract: boolean;
};

function isDescendantSelected(nodeId: string, selectedDirectoryId: string): boolean {
  if (!nodeId || !selectedDirectoryId) {
    return false;
  }
  return selectedDirectoryId.startsWith(`${nodeId}/`);
}

function TreeRow({
  id,
  label,
  level,
  active,
  hasChildren,
  expanded,
  onClick,
  canInteract,
}: TreeRowProps) {
  const leftPadding = 10 + (level * 28);
  const textIsPrimary = level <= 1;

  return (
    <button
      type="button"
      onClick={() => onClick(id)}
      disabled={!canInteract}
      className={`flex w-full items-center gap-2 rounded-[8px] border-none text-left ${
        active ? "bg-[var(--color-sidebar-active)]" : "bg-transparent"
      } ${canInteract ? "cursor-pointer" : "cursor-default"}`}
      style={{
        padding: `0 10px 0 ${leftPadding}px`,
        height: level === 0 ? "30px" : "28px",
      }}
    >
      <span className="flex h-[14px] w-[14px] items-center justify-center">
        {hasChildren
          ? expanded
            ? <ChevronDown size={14} strokeWidth={2.2} color={active ? "#CBD5E1" : "#8EA2C2"} />
            : <ChevronRight size={14} strokeWidth={2.2} color={active ? "#CBD5E1" : "#8EA2C2"} />
          : null}
      </span>

      <span className="flex h-[14px] w-[14px] shrink-0 items-center justify-center">
        <Folder size={14} color={textIsPrimary ? "#8EA2C2" : "#7A8EAF"} />
      </span>

      <span
        className={`text-ellipsis font-sidebar ${textIsPrimary ? "text-[14px] font-bold" : "text-[13px] font-semibold"} ${
          textIsPrimary ? "text-[var(--color-tree-main)]" : "text-[var(--color-tree-sub)]"
        }`}
      >
        {label}
      </span>
    </button>
  );
}

function renderTreeNode(
  node: DirectoryNode,
  level: number,
  selectedDirectoryId: string,
  onSelectDirectory: (id: string) => void,
  canInteract: boolean,
){
  const children = node.children ?? [];
  const hasChildren = children.length > 0;
  const active = selectedDirectoryId === node.id;
  const expanded = hasChildren && (level === 0 || active || isDescendantSelected(node.id, selectedDirectoryId));

  return (
    <div key={node.id || "__root__"} className="flex flex-col gap-1">
      <TreeRow
        id={node.id}
        label={node.name}
        level={level}
        active={active}
        hasChildren={hasChildren}
        expanded={expanded}
        onClick={onSelectDirectory}
        canInteract={canInteract}
      />

      {expanded
        ? children.map((child) => renderTreeNode(child, level + 1, selectedDirectoryId, onSelectDirectory, canInteract))
        : null}
    </div>
  );
}

export function Sidebar({
  brand,
  libraryTitle,
  treeRoot,
  selectedDirectoryId,
  scan,
  onSelectDirectory,
  onPickLibrary,
  onOpenSettings,
  canInteract,
}: SidebarProps) {
  const rootNode: DirectoryNode = treeRoot ?? {
    id: "",
    name: "Libraries",
    path: "/",
    hasChildren: false,
    children: [],
  };

  return (
    <aside className="flex h-full w-[310px] flex-col bg-[var(--color-sidebar-bg)]" data-testid="sidebar">
      <div className="flex h-[88px] items-center gap-3 bg-[var(--color-sidebar-top)] px-[18px]">
        <div className="flex h-9 w-9 items-center justify-center rounded-[11px] bg-[#1F2937]">
          <span className="font-sidebar text-[15px] font-bold text-[var(--color-logo-glyph)]">▦</span>
        </div>
        <span className="font-sidebar text-[16px] font-bold text-[var(--color-sidebar-brand)]">{brand}</span>
      </div>

      <div className="h-px w-full bg-[var(--color-sidebar-divider)]" />

      <div className="flex min-h-0 flex-1 flex-col gap-[12px] bg-[var(--color-sidebar-body)] px-3 pb-3 pt-[14px]">
        <div className="flex h-8 items-center justify-between">
          <span className="font-sidebar text-[13px] font-bold text-[var(--color-sidebar-brand)]">{libraryTitle}</span>
          <button
            type="button"
            onClick={onPickLibrary}
            disabled={!canInteract}
            className={`flex h-6 w-6 items-center justify-center rounded border-none bg-transparent p-0 ${
              canInteract ? "cursor-pointer" : "cursor-default"
            }`}
            aria-label="pick library"
          >
            <Plus size={18} color="var(--color-sidebar-accent)" strokeWidth={2.4} />
          </button>
        </div>

        <div className="h-px w-full bg-[var(--color-sidebar-divider)]" />

        <div className="sidebar-tree-scroll flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto overscroll-contain pr-1">
          {renderTreeNode(rootNode, 0, selectedDirectoryId, onSelectDirectory, canInteract)}
        </div>

        <div className="mt-6 flex flex-col gap-[10px]">
          <div className="h-px w-full bg-[var(--color-border)]" />

          <div className="flex h-[86px] items-center justify-between px-4">
            <div className="flex h-14 w-[200px] items-center gap-[10px] rounded-xl bg-[var(--color-sidebar-card)] px-[10px]">
              <div className="h-9 w-9 rounded-full bg-[#303030]" />
              <div className="flex flex-col gap-[2px]">
                <span className="font-sidebar text-[13px] font-bold text-[var(--color-user-name)]">Admin</span>
                <span className="font-sidebar text-[11px] font-semibold text-[var(--color-user-role)]">Local Library</span>
              </div>
            </div>

            <button
              type="button"
              onClick={onOpenSettings}
              className="flex h-10 w-10 items-center justify-center rounded-full border-none bg-[var(--color-sidebar-active)] p-0"
              aria-label="settings"
            >
              <Settings size={18} strokeWidth={2.2} color="#D1D5DB" />
            </button>
          </div>

          <div className="flex h-14 flex-col gap-[6px] rounded-xl bg-[var(--color-sidebar-card)] px-[14px] py-2">
            <div className="flex h-5 items-center justify-between">
              <span className="text-ellipsis font-sidebar text-[11px] font-semibold text-[var(--color-user-role)]">
                {scan.title}
              </span>
              <span className="font-sidebar text-[11px] font-bold text-[var(--color-progress-text)]">{scan.percentText}</span>
            </div>
            <div className="h-1 w-full rounded bg-[#2F2F2F]">
              <div
                className="h-1 rounded bg-[#3B82F6]"
                style={{ width: `${Math.max(0, Math.min(100, scan.percentValue))}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
