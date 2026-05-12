import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

// F2.1: top-level React error boundary.
//
// React error boundaries still require a class component (no hook
// equivalent). This wraps the whole app shell so any uncaught render
// error in a route falls back to a clean state instead of a blank screen.
//
// In F2.x, consider:
//   - integrating a real telemetry sink (Sentry, etc.) inside componentDidCatch
//   - per-route boundaries inside DashboardLayout so one feature crash
//     does not bring down the entire shell

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // F2.1: console only. Replace with telemetry sink when one lands.
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-background text-foreground">
        <AlertTriangle className="w-12 h-12 text-destructive mb-4" />
        <h1 className="text-xl font-semibold mb-2">Something went wrong</h1>
        <p className="text-sm text-muted-foreground mb-6 max-w-md text-center">
          {this.state.error?.message ?? "An unexpected error occurred."}
        </p>
        <Button onClick={this.reset}>Try again</Button>
      </div>
    );
  }
}
