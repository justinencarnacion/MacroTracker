import type { ReactNode } from "react";
import styles from "./Discord.module.css";

interface DiscordMessageProps {
  author: string;
  avatar: string;
  isBot?: boolean;
  time: string;
  children: ReactNode;
}

/** One message in a mock Discord conversation. */
export function DiscordMessage({ author, avatar, isBot = false, time, children }: DiscordMessageProps) {
  return (
    <article className={styles.message}>
      <div className={styles.avatar} aria-hidden="true">{avatar}</div>
      <div className={styles.body}>
        <header className={styles.meta}>
          <span className={styles.author}>{author}</span>
          {isBot && <span className={styles.botTag}>APP</span>}
          <time className={styles.time}>{time}</time>
        </header>
        <div className={styles.content}>{children}</div>
      </div>
    </article>
  );
}
