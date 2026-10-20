import type { ReactElement } from "react";
import { homeSections } from "../sections/registry";
import { NotFoundPage } from "./NotFoundPage";
import { SectionPage } from "./SectionPage";

export interface PageRoute {
  /** URL path relative to the site root, e.g. "/" or "/about". */
  path: string;
  /** Browser tab title for the page. */
  title: string;
  element: ReactElement;
}

/**
 * Every page on the site. To add a page: build its sections (or a component)
 * and add one entry here.
 */
export const pages: PageRoute[] = [
  { path: "/", title: "MacroTracker", element: <SectionPage sections={homeSections} /> },
  { path: "*", title: "Not found · MacroTracker", element: <NotFoundPage /> },
];
