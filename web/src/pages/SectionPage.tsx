import type { Section } from "../sections/types";

/** Renders a page as a stack of sections, in order. */
export function SectionPage({ sections }: { sections: Section[] }) {
  return (
    <>
      {sections.map(({ id, component: Component }) => (
        <Component key={id} />
      ))}
    </>
  );
}
