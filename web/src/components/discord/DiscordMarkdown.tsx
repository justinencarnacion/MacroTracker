import { Fragment, type ReactNode } from "react";
import styles from "./Discord.module.css";

/** Renders the small subset of Discord markdown the bot uses:
 *  ```code blocks```, `inline code`, and **bold**. Everything else is plain text. */
export function DiscordMarkdown({ text }: { text: string }) {
  const parts = text.split(/```\n?([\s\S]*?)\n?```/);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <pre key={index} className={styles.codeBlock}>{part}</pre>
        ) : (
          part.trim() && (
            <p key={index} className={styles.markdownText}>{renderInline(part.trim())}</p>
          )
        ),
      )}
    </>
  );
}

function renderInline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/).map((token, index) => {
    if (token.startsWith("`") && token.endsWith("`")) {
      return <code key={index} className={styles.inlineCode}>{token.slice(1, -1)}</code>;
    }
    if (token.startsWith("**") && token.endsWith("**")) {
      return <strong key={index}>{token.slice(2, -2)}</strong>;
    }
    return <Fragment key={index}>{token}</Fragment>;
  });
}
