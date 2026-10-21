import { Banner } from "./Banner";
import { DiscordDemo } from "./DiscordDemo";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import type { Section } from "./types";

/**
 * The home page, top to bottom. To add a section: create a component in this
 * folder and add one entry here. Reorder entries to reorder the page.
 */
export const homeSections: Section[] = [
  { id: "banner", component: Banner },
  { id: "hero", component: Hero },
  { id: "how-it-works", navLabel: "How it works", component: HowItWorks },
  { id: "demo", navLabel: "Demo", component: DiscordDemo },
];
