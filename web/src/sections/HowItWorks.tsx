import { SectionShell } from "../components/SectionShell";
import { howItWorks } from "../content/site";
import styles from "./HowItWorks.module.css";

export function HowItWorks() {
  return (
    <SectionShell
      id="how-it-works"
      eyebrow="How it works"
      title="Three steps, all inside Discord"
      intro="No app to download and no food database to scroll through. If you can send a message, you can track your macros."
    >
      <ol className={styles.steps}>
        {howItWorks.map((step, index) => (
          <li key={step.title} className={styles.step}>
            <span className={styles.number} aria-hidden="true">{index + 1}</span>
            <h3 className={styles.title}>{step.title}</h3>
            <p className={styles.body}>{step.body}</p>
            <code className={styles.example}>{step.example}</code>
          </li>
        ))}
      </ol>
    </SectionShell>
  );
}
