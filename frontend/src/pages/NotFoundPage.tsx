import { ButtonLink } from "../components/ui/Button";
import { EmptyState } from "../components/ui/Feedback";

export function NotFoundPage() {
  return (
    <EmptyState title="Page not found" action={<ButtonLink to="/dashboard">Back to dashboard</ButtonLink>}>
      The page may have moved, or you may not have access to it.
    </EmptyState>
  );
}
