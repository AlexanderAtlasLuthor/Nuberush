import { useId } from "react";

/**
 * The NubeRush brand mark: the flame in its rounded orange box, identical
 * to `/favicon.svg`. Self-contained (its own gradient background), so it
 * replaces the old `premium-action` box + lucide `Flame` combo.
 *
 * Decorative by default (`aria-hidden`) — the surrounding link/heading
 * already provides the "NubeRush" accessible name. Size it via `className`
 * (e.g. `h-9 w-9`).
 */
export function BrandMark({ className }: { className?: string }) {
  // Unique gradient id per instance so multiple marks on one page don't
  // collide on a shared `id`.
  const gradientId = useId();

  return (
    <svg
      viewBox="0 0 64 64"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient
          id={gradientId}
          x1="8"
          y1="6"
          x2="58"
          y2="60"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#FF8B4A" />
          <stop offset="1" stopColor="#FF6B2C" />
        </linearGradient>
      </defs>
      <rect
        x="4"
        y="4"
        width="56"
        height="56"
        rx="16"
        fill={`url(#${gradientId})`}
      />
      <path
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="3.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M28.5 38.5A2.5 2.5 0 0 0 31 36c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"
      />
    </svg>
  );
}

export default BrandMark;
