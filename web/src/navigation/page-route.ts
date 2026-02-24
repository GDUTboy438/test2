import type { AppPage, SettingsModule } from "../types/domain";

const PAGE_KEY = "page";
const MODULE_KEY = "module";

export type AppRoute = {
  page: AppPage;
  module: SettingsModule;
};

function parseModule(input: string | null): SettingsModule {
  return input === "logs-analysis" ? "logs-analysis" : "tag-manager";
}

export function readRouteFromUrl(): AppRoute {
  const params = new URLSearchParams(window.location.search);
  const page = params.get(PAGE_KEY);

  if (page === "tag-manager") {
    return { page: "settings", module: "tag-manager" };
  }
  if (page === "logs-analysis") {
    return { page: "settings", module: "logs-analysis" };
  }
  if (page === "settings") {
    return { page: "settings", module: parseModule(params.get(MODULE_KEY)) };
  }

  return { page: "home", module: "tag-manager" };
}

export function setRouteInUrl(route: AppRoute, replace = false): void {
  const url = new URL(window.location.href);
  url.searchParams.set(PAGE_KEY, route.page);

  if (route.page === "settings") {
    url.searchParams.set(MODULE_KEY, route.module);
  } else {
    url.searchParams.delete(MODULE_KEY);
  }

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
