// Hash routes, so deep links work on GitHub Pages without a server rewrite.

import { useEffect, useState } from "react";

export type Route = { page: "scan" } | { page: "shelves" } | { page: "shelf"; shelf: string };

export const href = {
  scan: "#/",
  shelves: "#/shelves",
  shelf: (shelf: string) => `#/shelves/${encodeURIComponent(shelf)}`,
};

export const isRoute = (hash: string) => hash === "" || hash.startsWith("#/");

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#\/?/, "").replace(/\/$/, "");
  if (path === "shelves") return { page: "shelves" };
  const match = /^shelves\/([^/]+)$/.exec(path);
  if (match) {
    try {
      return { page: "shelf", shelf: decodeURIComponent(match[1]) };
    } catch {
      // bad %-escape in a hand-typed URL: fall through to the scan page
    }
  }
  return { page: "scan" };
}

/** The current route, and whether we got here by navigating (not the first page load). */
export function useRoute(): { route: Route; navigated: boolean } {
  const [state, setState] = useState(() => ({ route: parseRoute(window.location.hash), navigated: false }));
  useEffect(() => {
    const onChange = () => {
      // in-page anchors like the skip link's #main aren't routes; stay put
      if (!isRoute(window.location.hash)) return;
      setState({ route: parseRoute(window.location.hash), navigated: true });
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return state;
}
