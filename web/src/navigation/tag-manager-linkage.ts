export const TM_FOCUS_KEY = "tm_focus";
export const TM_HIGHLIGHT_TAGS_KEY = "tm_highlight_tags";
export const TM_HIGHLIGHT_CANDIDATES_KEY = "tm_highlight_candidates";
export const TM_HIGHLIGHT_EXPIRE_KEY = "tm_highlight_expire";
export const TM_HIGHLIGHT_TTL_MS = 10_000;

export type TagManagerFocus = "tag_library" | "candidate_library";

export type TagManagerLinkage = {
  focus: TagManagerFocus | null;
  highlightTags: string[];
  highlightCandidates: string[];
  expireAt: number;
};

export type TagManagerLinkagePayload = {
  focus?: TagManagerFocus | null;
  highlightTags?: string[];
  highlightCandidates?: string[];
  ttlMs?: number;
};

function parseCsv(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((part) => normalizeMatchKey(part))
    .filter((part, index, arr) => Boolean(part) && arr.indexOf(part) === index);
}

function stringifyCsv(values: string[]): string {
  const normalized = values
    .map((value) => normalizeMatchKey(value))
    .filter((value, index, arr) => Boolean(value) && arr.indexOf(value) === index);
  return normalized.join(",");
}

function isTagManagerFocus(value: string | null): value is TagManagerFocus {
  return value === "tag_library" || value === "candidate_library";
}

function writeSearchParams(params: URLSearchParams, replace: boolean): void {
  const url = new URL(window.location.href);
  url.search = params.toString();
  const next = `${url.pathname}?${url.searchParams.toString()}${url.hash}`;
  if (replace) {
    window.history.replaceState(null, "", next);
    return;
  }
  window.history.pushState(null, "", next);
}

export function normalizeMatchKey(value: string): string {
  return String(value || "")
    .replace(/[\.]{3}/g, " ")
    .replace(/\u2026/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

export function clearTagManagerLinkageFromUrl(replace = true): void {
  const params = new URLSearchParams(window.location.search);
  params.delete(TM_FOCUS_KEY);
  params.delete(TM_HIGHLIGHT_TAGS_KEY);
  params.delete(TM_HIGHLIGHT_CANDIDATES_KEY);
  params.delete(TM_HIGHLIGHT_EXPIRE_KEY);
  writeSearchParams(params, replace);
}

export function writeTagManagerLinkageToUrl(
  payload: TagManagerLinkagePayload,
  replace = true,
): void {
  const params = new URLSearchParams(window.location.search);
  const focus = payload.focus ?? null;
  const highlightTags = payload.highlightTags ?? [];
  const highlightCandidates = payload.highlightCandidates ?? [];
  const ttlMs = Math.max(1_000, Number(payload.ttlMs ?? TM_HIGHLIGHT_TTL_MS));

  if (focus) {
    params.set(TM_FOCUS_KEY, focus);
  } else {
    params.delete(TM_FOCUS_KEY);
  }

  const tagsCsv = stringifyCsv(highlightTags);
  if (tagsCsv) {
    params.set(TM_HIGHLIGHT_TAGS_KEY, tagsCsv);
  } else {
    params.delete(TM_HIGHLIGHT_TAGS_KEY);
  }

  const candidatesCsv = stringifyCsv(highlightCandidates);
  if (candidatesCsv) {
    params.set(TM_HIGHLIGHT_CANDIDATES_KEY, candidatesCsv);
  } else {
    params.delete(TM_HIGHLIGHT_CANDIDATES_KEY);
  }

  if (tagsCsv || candidatesCsv) {
    params.set(TM_HIGHLIGHT_EXPIRE_KEY, String(Date.now() + ttlMs));
  } else {
    params.delete(TM_HIGHLIGHT_EXPIRE_KEY);
  }

  writeSearchParams(params, replace);
}

export function readTagManagerLinkageFromUrl(): TagManagerLinkage | null {
  const params = new URLSearchParams(window.location.search);
  const expireAt = Number(params.get(TM_HIGHLIGHT_EXPIRE_KEY) ?? 0);
  if (!Number.isFinite(expireAt) || expireAt <= 0 || expireAt <= Date.now()) {
    clearTagManagerLinkageFromUrl(true);
    return null;
  }

  const highlightTags = parseCsv(params.get(TM_HIGHLIGHT_TAGS_KEY));
  const highlightCandidates = parseCsv(params.get(TM_HIGHLIGHT_CANDIDATES_KEY));
  if (highlightTags.length === 0 && highlightCandidates.length === 0) {
    clearTagManagerLinkageFromUrl(true);
    return null;
  }

  const rawFocus = params.get(TM_FOCUS_KEY);
  return {
    focus: isTagManagerFocus(rawFocus) ? rawFocus : null,
    highlightTags,
    highlightCandidates,
    expireAt,
  };
}

export function notifyRouteChanged(): void {
  window.dispatchEvent(new PopStateEvent("popstate"));
}
