import { useState } from "react";
import { SectionShell } from "../components/SectionShell";
import { DiscordButtons, type DiscordButton } from "../components/discord/DiscordButtons";
import { DiscordEmbed } from "../components/discord/DiscordEmbed";
import { DiscordMessage } from "../components/discord/DiscordMessage";
import { demo, type DemoView } from "../content/demo";
import styles from "../components/discord/Discord.module.css";

const VIEW_BUTTONS: DiscordButton<DemoView>[] = [
  { value: "today", label: "Today", emoji: "📅" },
  { value: "week", label: "Week", emoji: "📊" },
];

/** A mock DM with the bot, using the real bot's output. The buttons work like the bot's. */
export function DiscordDemo() {
  const [view, setView] = useState<DemoView>("today");

  return (
    <SectionShell
      id="demo"
      eyebrow="See it in action"
      title="What a conversation looks like"
      intro="This is the bot's real output, generated from its own code. Try the Today and Week buttons."
    >
      <div className={styles.window}>
        <div className={styles.titleBar}>
          <span aria-hidden="true">@</span> MacroTrackerBot
        </div>

        <DiscordMessage author="you" avatar="🙂" time="Today at 12:40 PM">
          <p>{demo.logged.message}</p>
        </DiscordMessage>

        <DiscordMessage author="MacroTrackerBot" avatar="🍔" isBot time="Today at 12:40 PM">
          <p className={styles.botReply}>{demo.logged.reply}</p>
          <p className={styles.leftToday}>{demo.logged.leftToday}</p>
        </DiscordMessage>

        <DiscordMessage author="you" avatar="🙂" time="Today at 12:41 PM">
          <p><span className={styles.slash}>/today</span></p>
        </DiscordMessage>

        <DiscordMessage author="MacroTrackerBot" avatar="🍔" isBot time="Today at 12:41 PM">
          <div aria-live="polite">
            <DiscordEmbed {...demo.views[view]} />
          </div>
          <DiscordButtons
            buttons={VIEW_BUTTONS}
            selected={view}
            onSelect={setView}
            label="Switch between today's and this week's summary"
          />
        </DiscordMessage>
      </div>
    </SectionShell>
  );
}
