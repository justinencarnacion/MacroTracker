import { useState } from "react";
import { banner } from "../content/site";
import styles from "./Banner.module.css";

/** A wide picture banner, configured in content/site.ts. Hidden when the
 *  banner is turned off or the image can't be loaded. */
export function Banner() {
  const [failed, setFailed] = useState(false);
  if (!banner || failed) return null;

  return (
    <section className={styles.banner} aria-label="Banner">
      <figure className={styles.frame}>
        <img
          className={styles.image}
          src={`${import.meta.env.BASE_URL}${banner.src}`}
          alt={banner.alt}
          style={{ objectPosition: banner.focus ?? "center" }}
          onError={() => setFailed(true)}
        />
        {banner.caption && <figcaption className={styles.caption}>{banner.caption}</figcaption>}
      </figure>
    </section>
  );
}
