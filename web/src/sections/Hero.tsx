import { ButtonLink } from "../components/ButtonLink";
import { site } from "../content/site";
import styles from "./Hero.module.css";

export function Hero() {
  return (
    <section className={styles.hero} aria-labelledby="hero-heading">
      <div className={styles.inner}>
        <div className={styles.copy}>
          <p className={styles.badge}>A Discord bot for macro tracking</p>
          <h1 id="hero-heading" className={styles.title}>{site.tagline}</h1>
          <p className={styles.summary}>{site.summary}</p>
          <div className={styles.actions}>
            <ButtonLink href={site.links.requestAccess}>Request access</ButtonLink>
            <ButtonLink href="#demo" variant="secondary">See it in action</ButtonLink>
          </div>
          <p className={styles.note}>
            Invite-only for now: the bot runs for one Discord server on a Raspberry Pi.
          </p>
        </div>
        <figure className={styles.preview}>
          <img
            src={`${import.meta.env.BASE_URL}demo/today.png`}
            alt="Today's macro progress: calories, protein, carbs, and fat against daily goals"
            width={1111}
            height={421}
          />
          <figcaption>The real chart the bot sends for /today</figcaption>
        </figure>
      </div>
    </section>
  );
}
