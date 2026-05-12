import { UserMenu } from "./UserMenu";

interface AppTopbarProps {
  surfaceLabel: string;
  scopeLabel: string;
}

export function AppTopbar({ surfaceLabel, scopeLabel }: AppTopbarProps) {
  return (
    <header
      aria-label="Topbar"
      className="h-14 border-b border-border bg-background flex items-center justify-between px-4 gap-4"
    >
      <div className="min-w-0">
        <p className="text-sm font-medium truncate">{surfaceLabel}</p>
        <p
          className="text-xs text-muted-foreground font-mono truncate"
          aria-label="Current surface scope"
          data-testid="store-context-indicator"
        >
          {scopeLabel}
        </p>
      </div>
      <UserMenu />
    </header>
  );
}
