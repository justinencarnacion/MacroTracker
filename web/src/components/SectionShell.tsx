import type { ReactNode } from "react";
import styles from "./SectionShell.module.css";

interface SectionShellProps {
  id: string;
  eyebrow?: string;
  title?: string;
  intro?: string;
  children: ReactNode;
}

/** Consistent spacing, width, and heading for every page section. */
export function SectionShell({ id, eyebrow, title, intro, children }: SectionShellProps) {
  const headingId = title ? `${id}-heading` : undefined;
  return (
    <section id={id} className={styles.section} aria-labelledby={headingId}>
      <div className={styles.inner}>
        {(eyebrow || title || intro) && (
          <header className={styles.header}>
            {eyebrow && <p className={styles.eyebrow}>{eyebrow}</p>}
            {title && <h2 id={headingId} className={styles.title}>{title}</h2>}
            {intro && <p className={styles.intro}>{intro}</p>}
          </header>
        )}
        {children}
      </div>
    </section>
  );
}
