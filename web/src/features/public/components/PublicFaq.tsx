import { ChevronDown } from "lucide-react";
import type { FaqItem } from "../content/publicCopy";

interface PublicFaqProps {
  items: ReadonlyArray<FaqItem>;
}

// Uses native <details>/<summary> for zero-JS accessibility. Screen
// readers and keyboard navigation work without extra wiring; toggling
// is browser-native.

export function PublicFaq({ items }: PublicFaqProps) {
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li
          key={item.question}
          className="rounded-xl border border-border bg-card"
        >
          <details className="group">
            <summary className="flex cursor-pointer items-center justify-between gap-4 p-5 list-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-xl">
              <span className="text-sm font-semibold text-foreground">
                {item.question}
              </span>
              <ChevronDown
                className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180"
                aria-hidden="true"
              />
            </summary>
            <div className="px-5 pb-5 pt-0">
              <p className="text-sm text-muted-foreground leading-relaxed">
                {item.answer}
              </p>
            </div>
          </details>
        </li>
      ))}
    </ul>
  );
}

export default PublicFaq;
