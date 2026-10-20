import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { site } from "../content/site";
import styles from "./Layout.module.css";

/** Header and footer shared by every page. */
export function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <a className={styles.skip} href="#main">Skip to content</a>
      <header className={styles.header}>
        <div className={styles.inner}>
          <Link to="/" className={styles.brand}>
            <span aria-hidden="true">🥗</span> {site.name}
          </Link>
          <nav aria-label="Main">
            <a href={site.links.sourceCode} target="_blank" rel="noreferrer">GitHub</a>
          </nav>
        </div>
      </header>
      <main id="main">{children}</main>
      <footer className={styles.footer}>
        <div className={styles.inner}>
          <p>
            {site.name} is a student project. Macro estimates come from AI and are
            approximate, not medical or nutrition advice.
          </p>
        </div>
      </footer>
    </>
  );
}
