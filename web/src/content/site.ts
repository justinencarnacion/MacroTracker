/**
 * All site copy and links in one place. Components read from here, so wording
 * can change without touching layout code.
 */

export const site = {
  name: "MacroTracker",
  tagline: "Track your macros by texting what you ate.",
  summary:
    "MacroTracker is a Discord bot. Message it your meal in plain English, " +
    "AI estimates the calories, protein, carbs, and fat, and charts show how " +
    "your day and week compare with your goals.",
  links: {
    // The bot is limited to one Discord server; this explains how to get in.
    requestAccess: "https://github.com/justinencarnacion",
    sourceCode: "https://github.com/justinencarnacion/MacroTracker",
  },
} as const;

export interface Step {
  title: string;
  body: string;
  example: string;
}

export const howItWorks: Step[] = [
  {
    title: "Text what you ate",
    body: "DM the bot a description or exact numbers. No app to install, no food database to search.",
    example: "2 eggs and toast",
  },
  {
    title: "AI estimates the macros",
    body: "Gemini estimates calories, protein, carbs, and fat, and the meal is saved to your private log.",
    example: "✅ Logged! 340 kcal · P 20g",
  },
  {
    title: "See your progress",
    body: "/today and /week reply with charts against your goals. Fix mistakes with /edit and /delete.",
    example: "/today",
  },
];
