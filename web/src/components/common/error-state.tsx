import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

// F2.1: reusable error state. Use it inside a route or panel when a
// query fails or a feature can't load. The page-level fatal fallback
// lives in `src/app/error-boundary.tsx`.
export function ErrorState({
  title = "Something went wrong",
  message = "An unexpected error occurred.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center p-8 text-center"
    >
      <AlertCircle className="w-8 h-8 text-destructive mb-3" aria-hidden="true" />
      <h2 className="text-base font-semibold mb-1">{title}</h2>
      <p className="text-sm text-muted-foreground mb-4 max-w-sm">{message}</p>
      {onRetry ? (
        <Button onClick={onRetry} size="sm">
          Retry
        </Button>
      ) : null}
    </div>
  );
}
