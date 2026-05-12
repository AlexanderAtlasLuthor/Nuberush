import { Settings } from "lucide-react";
import { FeaturePlaceholder } from "@/layouts/components/FeaturePlaceholder";

export default function SettingsPlaceholderPage() {
  return (
    <FeaturePlaceholder
      title="Store Settings"
      description="Store profile, preferences, notification defaults, and operational settings will be configured here once backend support exists."
      icon={Settings}
      status="Backend Required"
      futureCapabilities={[
        "Store profile",
        "Notification defaults",
        "Operational preferences",
        "Store user preferences",
      ]}
      requiredBackend={[
        "GET /stores/:storeId",
        "PATCH /stores/:storeId",
        "Store notification settings endpoint",
        "Store operational preferences endpoint",
      ]}
      nonGoals={[
        "No fake store settings",
        "No frontend-only policy changes",
        "No billing simulation",
      ]}
    />
  );
}
