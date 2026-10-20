import { ButtonLink } from "../components/ButtonLink";
import { SectionShell } from "../components/SectionShell";

export function NotFoundPage() {
  return (
    <SectionShell id="not-found" title="Page not found" intro="That page doesn't exist (yet).">
      <ButtonLink href={import.meta.env.BASE_URL}>Back to the home page</ButtonLink>
    </SectionShell>
  );
}
