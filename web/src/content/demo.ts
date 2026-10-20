import type { EmbedData } from "../components/discord/DiscordEmbed";
import raw from "./demo.json";

/** Demo data generated from the real bot code by web/scripts/generate_demo.py. */
type RawEmbed = Omit<EmbedData, "image"> & { image: string };

function withImage(embed: RawEmbed, alt: string): EmbedData {
  return { ...embed, image: { src: `${import.meta.env.BASE_URL}demo/${embed.image}`, alt } };
}

export const demo = {
  logged: raw.logged,
  views: {
    today: withImage(raw.today, "Bar chart of today's calories, protein, carbs, and fat against daily goals"),
    week: withImage(raw.week, "Bar chart of calories for each day this week against the calorie goal"),
  },
};

export type DemoView = keyof typeof demo.views;
