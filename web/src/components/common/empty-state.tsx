import { Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title?: string;
  message?: string;
  action?: ReactNode;
}

// F2.1: reusable empty-list / no-results state. Pages should call this
// when a query succeeds but returns zero rows (e.g. "no orders yet",
// "no products in this store").
export function EmptyState({
  icon: Icon = Inbox,
  title = "Nothing here yet",
  message,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <Icon className="w-8 h-8 text-muted-foreground mb-3" aria-hidden="true" />
      <h2 className="text-base font-semibold mb-1">{title}</h2>
      {message ? (
        <p className="text-sm text-muted-foreground max-w-sm">{message}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
