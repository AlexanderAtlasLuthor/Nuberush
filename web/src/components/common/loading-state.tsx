import { Loader2 } from "lucide-react";

interface LoadingStateProps {
  message?: string;
}

// F2.1: reusable loading state. Centered spinner + caption. No business
// logic, no data fetching — pure presentational scaffolding.
export function LoadingState({ message = "Loading…" }: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center p-8 text-muted-foreground"
    >
      <Loader2 className="w-6 h-6 animate-spin mb-3" aria-hidden="true" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
