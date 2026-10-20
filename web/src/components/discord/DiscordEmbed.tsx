import styles from "./Discord.module.css";
import { DiscordMarkdown } from "./DiscordMarkdown";

export interface EmbedField {
  name: string;
  value: string;
}

export interface EmbedData {
  title: string;
  description?: string;
  fields: EmbedField[];
  image: { src: string; alt: string };
}

/** A Discord embed card: colored edge, title, inline fields, and an image. */
export function DiscordEmbed({ title, description, fields, image }: EmbedData) {
  return (
    <div className={styles.embed}>
      <p className={styles.embedTitle}>{title}</p>
      {description && (
        <div className={styles.embedDescription}>
          <DiscordMarkdown text={description} />
        </div>
      )}
      <dl className={styles.fields}>
        {fields.map((field) => (
          <div key={field.name} className={styles.field}>
            <dt>{field.name}</dt>
            <dd>{field.value}</dd>
          </div>
        ))}
      </dl>
      <img className={styles.embedImage} src={image.src} alt={image.alt} loading="lazy" />
    </div>
  );
}
