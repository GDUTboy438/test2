import type {
  TagBlacklistItem,
  TagCandidateItem,
  TagCandidateStatus,
  TagLibraryItem,
  TagSection,
  TagSource,
} from "../types/domain";

type TagManagerFixture = {
  tagLibrary: TagLibraryItem[];
  candidates: TagCandidateItem[];
  blacklist: TagBlacklistItem[];
  searchInput: string;
  source: TagSource;
  activeSection: TagSection;
};

const tagNames = [
  "动作片集",
  "悬疑烧脑",
  "纪录短片",
  "都市情感",
  "科幻合集",
  "旅行影像",
  "自然风光",
  "人物特写",
  "访谈节目",
  "怀旧电影",
  "演唱会",
  "家庭聚会",
  "运动赛事",
  "动漫专区",
  "剧情混剪",
  "幕后花絮",
  "经典台词",
  "节奏卡点",
  "搞笑日常",
  "实验短片",
  "高清素材",
  "航拍镜头",
  "夜景合集",
  "美食探店",
  "街头纪实",
  "电影预告",
  "纯音乐",
  "慢镜回放",
  "历史题材",
  "儿童向",
  "院线新片",
  "节日专题",
  "舞台表演",
  "短剧合集",
  "Vlog精选",
  "AI生成",
];

function toStatus(index: number): TagCandidateStatus {
  if (index % 7 === 0) {
    return "blacklisted";
  }
  if (index % 5 === 0) {
    return "approved";
  }
  if (index % 3 === 0) {
    return "mapped";
  }
  return "pending";
}

function buildTagLibrary(): TagLibraryItem[] {
  return tagNames.map((name, index) => ({
    id: index + 1,
    name: `${name}${index % 2 === 0 ? "…" : ""}`,
    usageCount: 128 - (index % 11) * 3,
    manualUsageCount: 48 - (index % 5) * 2,
    aiUsageCount: 80 - (index % 7) * 3,
  }));
}

function buildCandidates(): TagCandidateItem[] {
  return tagNames.slice(0, 24).map((name, index) => ({
    id: index + 101,
    name: `${name}候选${index % 2 === 0 ? "…" : ""}`,
    status: toStatus(index),
    mappedTagId: index % 3 === 0 ? index + 1 : 0,
    hitCount: 80 - (index % 9) * 4,
    firstSeenEpoch: 1730000000 - index * 8000,
    lastSeenEpoch: 1733000000 - index * 4000,
  }));
}

function buildBlacklist(): TagBlacklistItem[] {
  return [
    "低质词",
    "重复词",
    "营销诱导",
    "敏感词",
    "误判样本",
    "无意义标签",
    "垃圾候选",
    "拼写错误",
    "过短词",
    "临时停用",
  ].map((term, index) => ({
    id: index + 201,
    term,
    source: index % 2 === 0 ? "auto" : "manual",
    reason: index % 2 === 0 ? "候选拉黑" : "人工维护",
    hitCount: 22 - index,
    firstSeenEpoch: 1731000000 - index * 10000,
    lastSeenEpoch: 1733300000 - index * 3600,
  }));
}

const fixture: TagManagerFixture = {
  tagLibrary: buildTagLibrary(),
  candidates: buildCandidates(),
  blacklist: buildBlacklist(),
  searchInput: "",
  source: "all",
  activeSection: "tag_library",
};

export function getTagManagerFixture(): TagManagerFixture {
  return JSON.parse(JSON.stringify(fixture)) as TagManagerFixture;
}
