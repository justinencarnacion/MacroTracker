import type { ComponentType } from "react";

/**
 * One section of a page. Pages are built from ordered lists of these, so a new
 * section is a component plus one entry in a registry.
 */
export interface Section {
  /** Used as the HTML id, so the section can be linked to as #id. */
  id: string;
  /** Short name for navigation menus. */
  navLabel?: string;
  component: ComponentType;
}
