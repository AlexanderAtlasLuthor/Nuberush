// F2.24 — option lists for the wizard dropdowns. Values stay wire-shaped:
// numeric fields carry plain integer strings (form.ts parses them to int),
// state carries the 2-letter USPS code, country the 2-letter ISO code.

import type { WizardSelectOption } from "./WizardSelect";

// 1–10 individually, then a few larger steps. Plain integer string values.
export const LOCATION_COUNT_OPTIONS: ReadonlyArray<WizardSelectOption> = [
  ...Array.from({ length: 10 }, (_, i) => {
    const n = String(i + 1);
    return { value: n, label: n };
  }),
  { value: "15", label: "15" },
  { value: "20", label: "20" },
  { value: "25", label: "25" },
  { value: "50", label: "50" },
];

// Representative weekly-order volumes. Integer string values; the label on
// the last entry reads as a floor ("5,000+") but the value is still 5000.
export const WEEKLY_ORDERS_OPTIONS: ReadonlyArray<WizardSelectOption> = [
  { value: "0", label: "0" },
  { value: "25", label: "Up to 25" },
  { value: "50", label: "25–50" },
  { value: "100", label: "50–100" },
  { value: "250", label: "100–250" },
  { value: "500", label: "250–500" },
  { value: "1000", label: "500–1,000" },
  { value: "2500", label: "1,000–2,500" },
  { value: "5000", label: "2,500+" },
];

export const COUNTRY_OPTIONS: ReadonlyArray<WizardSelectOption> = [
  { value: "US", label: "United States" },
  { value: "CA", label: "Canada" },
  { value: "MX", label: "Mexico" },
];

export const US_STATE_OPTIONS: ReadonlyArray<WizardSelectOption> = [
  { value: "AL", label: "Alabama" },
  { value: "AK", label: "Alaska" },
  { value: "AZ", label: "Arizona" },
  { value: "AR", label: "Arkansas" },
  { value: "CA", label: "California" },
  { value: "CO", label: "Colorado" },
  { value: "CT", label: "Connecticut" },
  { value: "DE", label: "Delaware" },
  { value: "DC", label: "District of Columbia" },
  { value: "FL", label: "Florida" },
  { value: "GA", label: "Georgia" },
  { value: "HI", label: "Hawaii" },
  { value: "ID", label: "Idaho" },
  { value: "IL", label: "Illinois" },
  { value: "IN", label: "Indiana" },
  { value: "IA", label: "Iowa" },
  { value: "KS", label: "Kansas" },
  { value: "KY", label: "Kentucky" },
  { value: "LA", label: "Louisiana" },
  { value: "ME", label: "Maine" },
  { value: "MD", label: "Maryland" },
  { value: "MA", label: "Massachusetts" },
  { value: "MI", label: "Michigan" },
  { value: "MN", label: "Minnesota" },
  { value: "MS", label: "Mississippi" },
  { value: "MO", label: "Missouri" },
  { value: "MT", label: "Montana" },
  { value: "NE", label: "Nebraska" },
  { value: "NV", label: "Nevada" },
  { value: "NH", label: "New Hampshire" },
  { value: "NJ", label: "New Jersey" },
  { value: "NM", label: "New Mexico" },
  { value: "NY", label: "New York" },
  { value: "NC", label: "North Carolina" },
  { value: "ND", label: "North Dakota" },
  { value: "OH", label: "Ohio" },
  { value: "OK", label: "Oklahoma" },
  { value: "OR", label: "Oregon" },
  { value: "PA", label: "Pennsylvania" },
  { value: "RI", label: "Rhode Island" },
  { value: "SC", label: "South Carolina" },
  { value: "SD", label: "South Dakota" },
  { value: "TN", label: "Tennessee" },
  { value: "TX", label: "Texas" },
  { value: "UT", label: "Utah" },
  { value: "VT", label: "Vermont" },
  { value: "VA", label: "Virginia" },
  { value: "WA", label: "Washington" },
  { value: "WV", label: "West Virginia" },
  { value: "WI", label: "Wisconsin" },
  { value: "WY", label: "Wyoming" },
];
