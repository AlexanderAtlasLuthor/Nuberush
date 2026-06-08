// Store-scoped Regulatory surface (F2.27.6).
//
// Read-only compliance/regulatory visibility for products this store carries in
// inventory. There are NO lifecycle controls here (no acknowledge / dismiss /
// resolve) — those live only on the admin surface. This page imports no admin
// regulatory mutation hook or action component; it reuses only the read-only
// presentational badges.

import { useMemo, useState } from "react";
import { AlertCircle, ShieldAlert } from "lucide-react";

import { getApiErrorMessage } from "@/api";
import { useStoreContext } from "@/auth";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  RegulatoryRecommendedActionBadge,
  RegulatorySeverityBadge,
  RegulatoryStatusBadge,
} from "@/features/admin-regulatory/components/RegulatoryAlertBadges";

import { useStoreRegulatoryAlertsQuery } from "../hooks";
import type {
  StoreRegulatoryAlert,
  StoreRegulatoryAlertSeverity,
  StoreRegulatoryAlertStatus,
  StoreRegulatoryFilters,
  StoreRegulatoryRecommendedAction,
} from "../types";

const STATUS_OPTIONS: ReadonlyArray<StoreRegulatoryAlertStatus> = [
  "open",
  "acknowledged",
  "actioned",
  "dismissed",
];

const SEVERITY_OPTIONS: ReadonlyArray<StoreRegulatoryAlertSeverity> = [
  "low",
  "medium",
  "high",
  "critical",
];

const RECOMMENDED_ACTION_OPTIONS: ReadonlyArray<StoreRegulatoryRecommendedAction> =
  ["none", "hold", "ban"];

function PageHeader() {
  return (
    <header>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Store · Regulatory
      </p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight md:text-[28px]">
        Regulatory alerts
      </h1>
      <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground leading-relaxed">
        Read-only regulatory visibility for products in this store's inventory.
        Severity, status and recommended action are advisory signals surfaced by
        the platform — there are no actions to take here.
      </p>
    </header>
  );
}

function LoadingState() {
  return (
    <p
      className="text-sm text-muted-foreground"
      data-testid="store-regulatory-loading"
    >
      Loading regulatory alerts…
    </p>
  );
}

interface ErrorStateProps {
  error: unknown;
  onRetry: () => void;
}

function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <Alert variant="destructive" data-testid="store-regulatory-error">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Could not load regulatory alerts</AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        <span>{getApiErrorMessage(error)}</span>
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="self-start"
          data-testid="store-regulatory-retry"
        >
          Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function AlertCard({ alert }: { alert: StoreRegulatoryAlert }) {
  return (
    <article
      className="rounded-xl border border-border bg-card p-4 md:p-5 flex flex-col gap-3"
      data-testid="store-regulatory-alert-card"
    >
      <div className="flex flex-wrap items-center gap-2">
        <RegulatorySeverityBadge severity={alert.severity} />
        <RegulatoryStatusBadge status={alert.status} />
        <RegulatoryRecommendedActionBadge
          recommendedAction={alert.recommended_action}
        />
      </div>
      <div>
        <p className="text-sm font-semibold">
          {alert.product_name ?? "Unnamed product"}
        </p>
        {alert.notice_title ? (
          <p className="mt-0.5 text-sm text-muted-foreground">
            {alert.notice_title}
            {alert.notice_type ? ` · ${alert.notice_type}` : ""}
          </p>
        ) : null}
      </div>
      <dl className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <div className="flex gap-1">
          <dt className="font-medium">Notice published</dt>
          <dd>{formatDate(alert.notice_published_at)}</dd>
        </div>
        <div className="flex gap-1">
          <dt className="font-medium">Created</dt>
          <dd>{formatDate(alert.created_at)}</dd>
        </div>
        <div className="flex gap-1">
          <dt className="font-medium">Updated</dt>
          <dd>{formatDate(alert.updated_at)}</dd>
        </div>
      </dl>
    </article>
  );
}

interface FilterSelectProps<T extends string> {
  label: string;
  testId: string;
  value: T | "";
  options: ReadonlyArray<T>;
  onChange: (next: T | "") => void;
}

function FilterSelect<T extends string>({
  label,
  testId,
  value,
  options,
  onChange,
}: FilterSelectProps<T>) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
      {label}
      <select
        className="h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
        data-testid={testId}
        value={value}
        onChange={(e) => onChange(e.target.value as T | "")}
      >
        <option value="">All</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function StoreRegulatoryPage() {
  const { currentStoreId } = useStoreContext();

  const [status, setStatus] = useState<StoreRegulatoryAlertStatus | "">("");
  const [severity, setSeverity] = useState<StoreRegulatoryAlertSeverity | "">(
    "",
  );
  const [recommendedAction, setRecommendedAction] = useState<
    StoreRegulatoryRecommendedAction | ""
  >("");

  const filters = useMemo<StoreRegulatoryFilters>(() => {
    const next: StoreRegulatoryFilters = {};
    if (status) next.status = status;
    if (severity) next.severity = severity;
    if (recommendedAction) next.recommended_action = recommendedAction;
    return next;
  }, [status, severity, recommendedAction]);

  const query = useStoreRegulatoryAlertsQuery(currentStoreId, filters);

  return (
    <div
      className="px-4 py-5 md:px-8 md:py-7 max-w-[1320px] mx-auto w-full space-y-5 md:space-y-6"
      data-testid="store-regulatory-page"
    >
      <PageHeader />

      {!currentStoreId ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="store-regulatory-no-store"
        >
          Select a store to view regulatory alerts.
        </p>
      ) : null}

      {currentStoreId ? (
        <section
          className="flex flex-wrap gap-3"
          aria-label="Regulatory alert filters"
        >
          <FilterSelect<StoreRegulatoryAlertStatus>
            label="Status"
            testId="store-regulatory-filter-status"
            value={status}
            options={STATUS_OPTIONS}
            onChange={setStatus}
          />
          <FilterSelect<StoreRegulatoryAlertSeverity>
            label="Severity"
            testId="store-regulatory-filter-severity"
            value={severity}
            options={SEVERITY_OPTIONS}
            onChange={setSeverity}
          />
          <FilterSelect<StoreRegulatoryRecommendedAction>
            label="Recommended action"
            testId="store-regulatory-filter-recommended-action"
            value={recommendedAction}
            options={RECOMMENDED_ACTION_OPTIONS}
            onChange={setRecommendedAction}
          />
        </section>
      ) : null}

      {query.isPending && currentStoreId ? <LoadingState /> : null}

      {query.isError ? (
        <ErrorState
          error={query.error}
          onRetry={() => {
            void query.refetch();
          }}
        />
      ) : null}

      {query.isSuccess && query.data ? (
        query.data.items.length === 0 ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="store-regulatory-empty"
          >
            No regulatory alerts for products in this store.
          </p>
        ) : (
          <section
            className="grid gap-3 md:gap-4 grid-cols-1 lg:grid-cols-2"
            data-testid="store-regulatory-alerts"
            aria-label="Regulatory alerts"
          >
            {query.data.items.map((alert) => (
              <AlertCard key={alert.id} alert={alert} />
            ))}
          </section>
        )
      ) : null}
    </div>
  );
}
