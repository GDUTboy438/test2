import type { AppPage } from "../types/domain";

const PAGE_KEY = "page";

export function readPageFromUrl(): AppPage {
  const page = new URLSearchParams(window.location.search).get(PAGE_KEY);
  return page === "tag-manager" ? "tag-manager" : "home";
}

export function setPageInUrl(page: AppPage, replace = false): void {
  const url = new URL(window.location.href);
  url.searchParams.set(PAGE_KEY, page);
  if (!url.searchParams.has("mode")) {
    url.searchParams.set("mode", "live");
  }

  const nextUrl = `${url.pathname}?${url.searchParams.toString()}${url.hash}`;
  if (replace) {
    window.history.replaceState(null, "", nextUrl);
    return;
  }
  window.history.pushState(null, "", nextUrl);
}

export function subscribePopState(onChange: () => void): () => void {
  const handler = () => onChange();
  window.addEventListener("popstate", handler);
  return () => window.removeEventListener("popstate", handler);
}
