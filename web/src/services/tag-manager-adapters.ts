import type {
  ApiTagBlacklistItem,
  ApiTagCandidateItem,
  ApiTagLibraryItem,
} from "../types/api";
import type {
  TagBlacklistItem,
  TagCandidateItem,
  TagLibraryItem,
} from "../types/domain";

export function toTagLibraryItem(item: ApiTagLibraryItem): TagLibraryItem {
  return {
    id: Number(item.id ?? 0),
    name: String(item.name ?? ""),
    usageCount: Number(item.usage_count ?? 0),
    manualUsageCount: Number(item.manual_usage_count ?? 0),
    aiUsageCount: Number(item.ai_usage_count ?? 0),
  };
}

export function toTagCandidateItem(item: ApiTagCandidateItem): TagCandidateItem {
  return {
    id: Number(item.id ?? 0),
    name: String(item.name ?? ""),
    status: item.status,
    mappedTagId: Number(item.mapped_tag_id ?? 0),
    hitCount: Number(item.hit_count ?? 0),
    firstSeenEpoch: Number(item.first_seen_epoch ?? 0),
    lastSeenEpoch: Number(item.last_seen_epoch ?? 0),
  };
}

export function toTagBlacklistItem(item: ApiTagBlacklistItem): TagBlacklistItem {
  return {
    id: Number(item.id ?? 0),
    term: String(item.term ?? ""),
    source: String(item.source ?? ""),
    reason: String(item.reason ?? ""),
    hitCount: Number(item.hit_count ?? 0),
    firstSeenEpoch: Number(item.first_seen_epoch ?? 0),
    lastSeenEpoch: Number(item.last_seen_epoch ?? 0),
  };
}
