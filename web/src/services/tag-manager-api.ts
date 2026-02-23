import type {
  ApiEnvelope,
  ApiRuntimeInfoData,
  ApiTagBlacklistData,
  ApiTagCandidatesData,
  ApiTagLibraryData,
  CreateTagsPayload,
  IdListPayload,
} from "../types/api";
import type {
  TagBlacklistItem,
  TagCandidateItem,
  TagCandidateStatus,
  TagLibraryItem,
} from "../types/domain";
import { requestApi } from "./http";
import {
  toTagBlacklistItem,
  toTagCandidateItem,
  toTagLibraryItem,
} from "./tag-manager-adapters";

export type ApiRuntimeInfo = {
  appTitle: string;
  appVersion: string;
  pythonExecutable: string;
  cwd: string;
  apiFile: string;
  routeCount: number;
  hasTagRoutes: boolean;
  requiredTagRoutes: string[];
  missingTagRoutes: string[];
};

function failedEnvelope<T>(envelope: ApiEnvelope<unknown>): ApiEnvelope<T> {
  return {
    ok: false,
    data: null,
    error: envelope.error,
  };
}

export async function getApiRuntimeInfo(): Promise<ApiEnvelope<ApiRuntimeInfo>> {
  const response = await requestApi<ApiRuntimeInfoData>("/runtime/info");
  if (!response.ok || !response.data) {
    return failedEnvelope<ApiRuntimeInfo>(response);
  }

  return {
    ok: true,
    data: {
      appTitle: String(response.data.app_title ?? ""),
      appVersion: String(response.data.app_version ?? ""),
      pythonExecutable: String(response.data.python_executable ?? ""),
      cwd: String(response.data.cwd ?? ""),
      apiFile: String(response.data.api_file ?? ""),
      routeCount: Number(response.data.route_count ?? 0),
      hasTagRoutes: Boolean(response.data.has_tag_routes),
      requiredTagRoutes: (response.data.required_tag_routes ?? []).map((item) => String(item)),
      missingTagRoutes: (response.data.missing_tag_routes ?? []).map((item) => String(item)),
    },
    error: null,
  };
}

export async function getTagLibrary(): Promise<ApiEnvelope<TagLibraryItem[]>> {
  const response = await requestApi<ApiTagLibraryData>("/tags/library");
  if (!response.ok || !response.data) {
    return failedEnvelope<TagLibraryItem[]>(response);
  }

  return {
    ok: true,
    data: response.data.items.map(toTagLibraryItem),
    error: null,
  };
}

export async function createTagLibrary(payload: CreateTagsPayload): Promise<ApiEnvelope<{ created: number }>> {
  return requestApi<{ created: number }>("/tags/library/create", {
    method: "POST",
    body: payload,
  });
}

export async function deleteTagLibrary(payload: IdListPayload): Promise<ApiEnvelope<{ removed: number }>> {
  return requestApi<{ removed: number }>("/tags/library/delete", {
    method: "POST",
    body: payload,
  });
}

export async function getTagCandidates(
  statuses: TagCandidateStatus[] = ["pending", "approved", "blacklisted", "mapped"],
): Promise<ApiEnvelope<TagCandidateItem[]>> {
  const response = await requestApi<ApiTagCandidatesData>("/tags/candidates", {
    query: { statuses: statuses.join(",") },
  });

  if (!response.ok || !response.data) {
    return failedEnvelope<TagCandidateItem[]>(response);
  }

  return {
    ok: true,
    data: response.data.items.map(toTagCandidateItem),
    error: null,
  };
}

export async function approveTagCandidates(
  payload: IdListPayload,
): Promise<ApiEnvelope<{ approved_candidates: number; created_tags: number; linked_relations: number }>> {
  return requestApi<{ approved_candidates: number; created_tags: number; linked_relations: number }>(
    "/tags/candidates/approve",
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function rejectTagCandidates(payload: IdListPayload): Promise<ApiEnvelope<{ rejected: number }>> {
  return requestApi<{ rejected: number }>("/tags/candidates/reject", {
    method: "POST",
    body: payload,
  });
}

export async function blacklistTagCandidates(
  payload: IdListPayload,
): Promise<ApiEnvelope<{ blacklisted_candidates: number; blacklist_terms_added: number }>> {
  return requestApi<{ blacklisted_candidates: number; blacklist_terms_added: number }>(
    "/tags/candidates/blacklist",
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function requeueTagCandidates(payload: IdListPayload): Promise<ApiEnvelope<{ requeued: number }>> {
  return requestApi<{ requeued: number }>("/tags/candidates/requeue", {
    method: "POST",
    body: payload,
  });
}

export async function clearPendingTagCandidates(): Promise<ApiEnvelope<{ removed: number }>> {
  return requestApi<{ removed: number }>("/tags/candidates/clear-pending", {
    method: "POST",
    body: {},
  });
}

export async function getTagBlacklist(): Promise<ApiEnvelope<TagBlacklistItem[]>> {
  const response = await requestApi<ApiTagBlacklistData>("/tags/blacklist");
  if (!response.ok || !response.data) {
    return failedEnvelope<TagBlacklistItem[]>(response);
  }

  return {
    ok: true,
    data: response.data.items.map(toTagBlacklistItem),
    error: null,
  };
}
