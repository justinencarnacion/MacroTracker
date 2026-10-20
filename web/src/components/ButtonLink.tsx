import type { ReactNode } from "react";
import styles from "./ButtonLink.module.css";

interface ButtonLinkProps {
  href: string;
  variant?: "primary" | "secondary";
  children: ReactNode;
}

/** A link styled as a button. External links open in a new tab. */
export function ButtonLink({ href, variant = "primary", children }: ButtonLinkProps) {
  const external = /^https?:\/\//.test(href);
  return (
    <a
      href={href}
      className={`${styles.button} ${styles[variant]}`}
      {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
    >
      {children}
    </a>
  );
}
