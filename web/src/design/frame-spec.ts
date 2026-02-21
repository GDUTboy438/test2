import type { SceneId, ViewMode } from "../types/domain";

export type FrameSpec = {
  id: SceneId;
  name: string;
  subNavHeight: 58 | 60;
  contentGap: number;
  detailWidth: number;
  listHeaderHeight: 50 | 54;
  listRowHeight: 86 | 94;
  gridCardHeight: 208 | 206;
  viewMode: ViewMode;
  detailOpen: boolean;
};

const FRAME_SPEC_MAP: Record<SceneId, FrameSpec> = {
  "5JcTk": {
    id: "5JcTk",
    name: "PVM Home Rebuild - UX Max Variant",
    subNavHeight: 58,
    contentGap: 0,
    detailWidth: 360,
    listHeaderHeight: 50,
    listRowHeight: 86,
    gridCardHeight: 208,
    viewMode: "list",
    detailOpen: false,
  },
  "88L9O": {
    id: "88L9O",
    name: "PVM Home Rebuild - Detail Open Dark Sidebar",
    subNavHeight: 60,
    contentGap: 16,
    detailWidth: 360,
    listHeaderHeight: 54,
    listRowHeight: 94,
    gridCardHeight: 206,
    viewMode: "list",
    detailOpen: true,
  },
  JrodX: {
    id: "JrodX",
    name: "Grid - No Detail",
    subNavHeight: 58,
    contentGap: 0,
    detailWidth: 360,
    listHeaderHeight: 50,
    listRowHeight: 86,
    gridCardHeight: 208,
    viewMode: "grid",
    detailOpen: false,
  },
  "2L8Xf": {
    id: "2L8Xf",
    name: "Grid - Detail Open",
    subNavHeight: 60,
    contentGap: 16,
    detailWidth: 360,
    listHeaderHeight: 54,
    listRowHeight: 94,
    gridCardHeight: 206,
    viewMode: "grid",
    detailOpen: true,
  },
};

export const ALL_SCENES: SceneId[] = ["5JcTk", "88L9O", "JrodX", "2L8Xf"];

export function parseSceneId(input: string | null): SceneId {
  if (input === "5JcTk" || input === "88L9O" || input === "JrodX" || input === "2L8Xf") {
    return input;
  }
  return "88L9O";
}

export function getFrameSpec(sceneId: SceneId): FrameSpec {
  return FRAME_SPEC_MAP[sceneId];
}

export function sceneFromState(viewMode: ViewMode, detailOpen: boolean): SceneId {
  if (viewMode === "list" && !detailOpen) {
    return "5JcTk";
  }
  if (viewMode === "list" && detailOpen) {
    return "88L9O";
  }
  if (viewMode === "grid" && !detailOpen) {
    return "JrodX";
  }
  return "2L8Xf";
}
