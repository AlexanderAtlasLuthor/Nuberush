# Dr.1.0 Driver Feature Adaptation Matrix

## 1. Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.B — Uber Driver / Uber Eats Feature Adaptation Matrix
- **Status:** Draft for Dr.1.0 documentation
- **Scope:** documentation only
- **Implementation:** none

This document is subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and
consistent with `docs/mobile-apps-strategy-roadmap.md`,
`docs/f2.27-contract-lock.md`, and `docs/f2.27.x-stripe-readiness-roadmap.md`.
Where this document and those overlap, those are authoritative and this one
cross-references them.

## 2. Purpose

This document maps Uber Driver / Uber Eats Driver style capabilities into a
NubeRush Driver App product architecture. It takes the large, mature
functionality universe of a professional driver platform and classifies, item
by item, what NubeRush should keep, adapt, defer, reject, or upgrade.

Stated clearly:

- **The purpose is not to copy Uber.** No Uber branding, protected design, or UI
  is reproduced. NubeRush is not described as Uber and does not present itself
  as a rideshare product.
- **The purpose is to extract operational patterns and transform them for
  NubeRush.** The reference is the operational *structure* of a mature driver
  platform — onboarding, documents, availability, offers, pickup, dropoff,
  failure handling, support, safety, earnings — not its branding or screens.
- **NubeRush Driver must have professional driver-app depth.** It is a full
  driver operations platform, not a thin "assigned orders" viewer.
- **Restricted-product compliance is core, not an add-on.** Smoke-shop and vape
  delivery, 21+ verification, proof of delivery, failed-delivery handling, and
  return-to-store accountability are first-class requirements that shape every
  adaptation in this matrix.

NubeRush Driver is for smoke-shop delivery, vape / restricted-product orders,
21+ verification, store pickup, store handoff, proof of delivery, failed
delivery, return-to-store, support, safety, compliance audit, and
backend-authorized driver operations. NubeRush Driver is **not** rideshare,
passenger transport, airport queue operations, passenger no-show handling, ride
fare calculation, rider ratings, multi-passenger trips, or a UberX / Comfort /
XL / Black equivalent.

## 3. Classification System

Every feature in the matrix is assigned one decision:

- **Keep** — Feature applies directly to NubeRush with minimal change.
- **Adapt** — Feature applies, but must be transformed for smoke-shop delivery,
  restricted products, 21+ verification, store handoff, or return-to-store.
- **Defer** — Feature is valuable but not MVP / early-phase.
- **No** — Feature is rideshare-only or not relevant to NubeRush.
- **NubeRush Upgrade** — Feature becomes more compliance-heavy or operationally
  specific than the Uber equivalent because of NubeRush's regulated-product
  model.

## 4. Matrix Columns

The matrix below uses the following columns:

- **Uber-style module / feature** — the reference capability being classified.
- **Applies to NubeRush?** — Yes / Partial / No.
- **Decision** — Keep / Adapt / Defer / No / NubeRush Upgrade.
- **NubeRush adaptation** — how the capability is transformed for NubeRush, or
  why it is rejected.
- **Compliance impact** — the regulated-product / 21+ / audit implication.
- **Backend needed?** — Yes / No / Future (server-side work required).
- **Mobile needed?** — Yes / No / Future (driver-app surface required).
- **Phase target** — the Dr.1.x phase where the capability is expected (per the
  future phase map in the contract lock), or Future / N/A.
- **Notes** — additional constraints or rationale.

Phase targets reference the contract-lock phase map: **Dr.1.1** Driver Backend
Surface, **Dr.1.2** Driver Mobile Foundation, **Dr.1.3** Driver App MVP,
**Dr.1.4** Driver App Operations, **Dr.1.5** Driver Compliance Upgrade,
**Dr.1.6** Driver Growth Features. "Future" means beyond the currently mapped
phases; "N/A" means not applicable.

## 5. Full Feature Adaptation Matrix

### 5.1 Driver Account / Identity

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Driver login | Yes | Keep | Backend-authenticated driver session; order-scoped token | Auth audit | Yes | Yes | Dr.1.2 | No store-wide access |
| Driver profile | Yes | Keep | Read-mostly profile sourced from backend | Identity record | Yes | Yes | Dr.1.2 | Edits gated server-side |
| Driver photo | Yes | Adapt | Identity photo for handoff accountability, not public rating | Identity / proof support | Yes | Yes | Dr.1.3 | Not a marketing avatar |
| Legal name | Yes | Keep | Authoritative legal name from onboarding record | Identity / audit | Yes | Yes | Dr.1.2 | Immutable client-side |
| Phone verification | Yes | Keep | Verified contact for masked calls and dispatch | Contactability | Yes | Yes | Dr.1.2 | Used by safety/support |
| Email verification | Yes | Keep | Verified contact for account and policy notices | Account integrity | Yes | Yes | Dr.1.2 | — |
| Date of birth | Yes | NubeRush Upgrade | Drives driver 21+ eligibility for restricted delivery | Driver age-gate | Yes | No | Dr.1.1 | Backend computes eligibility |
| Driver status | Yes | Keep | Active / pending / suspended / blocked from backend | Authorization gate | Yes | Yes | Dr.1.1 | Server-decided |
| Account approval status | Yes | Keep | Backend approval state surfaced read-only | Authorization gate | Yes | Yes | Dr.1.2 | — |
| Driver deactivation / blocked status | Yes | NubeRush Upgrade | Block immediately revokes restricted-delivery authority | Compliance enforcement | Yes | Yes | Dr.1.1 | Mobile cannot override |
| Policy acknowledgments | Yes | NubeRush Upgrade | Restricted-product and 21+ policy acks recorded with audit | Policy audit | Yes | Yes | Dr.1.2 | Required before online |

### 5.2 Onboarding

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Driver signup | Partial | Adapt | Invite/provision model, not open self-signup | Controlled access | Yes | Yes | Dr.1.2 | Backend provisions drivers |
| Invitation onboarding | Yes | Keep | Driver onboards from a backend-issued invitation | Controlled access | Yes | Yes | Dr.1.2 | Preferred entry path |
| Activation checklist | Yes | Keep | Backend-driven checklist of activation steps | Readiness gate | Yes | Yes | Dr.1.2 | — |
| Profile setup | Yes | Keep | Guided profile completion | Identity completeness | Yes | Yes | Dr.1.2 | — |
| Document checklist | Yes | NubeRush Upgrade | Document set tied to restricted-delivery authorization | Document compliance | Yes | Yes | Dr.1.2 | Blocks online until met |
| Vehicle setup | Yes | Adapt | Delivery-vehicle profile, no ride-class semantics | Operational record | Yes | Yes | Dr.1.2 | No passenger capacity logic |
| Training checklist | Yes | NubeRush Upgrade | Includes 21+ / restricted-product / return-to-store modules | Policy compliance | Yes | Yes | Dr.1.2 | Required for restricted work |
| Approval pending screen | Yes | Keep | Read-only pending state from backend | Status transparency | No | Yes | Dr.1.2 | — |
| Rejected / action required flow | Yes | Keep | Reason + resubmission path | Remediation audit | Yes | Yes | Dr.1.2 | Reason from backend |

### 5.3 Documents

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Driver license upload | Yes | Adapt | Driver's own license as authorization doc (not customer ID) | Driver eligibility | Yes | Yes | Dr.1.2 | Privacy-safe handling |
| Government ID upload | Yes | Adapt | Driver identity verification document | Driver eligibility | Yes | Yes | Dr.1.2 | Distinct from customer 21+ check |
| Selfie verification | Partial | Defer | Driver identity-match check | Identity assurance | Future | Future | Dr.1.5 | Not MVP |
| Vehicle registration | Yes | Keep | Vehicle authorization document | Operational compliance | Yes | Yes | Dr.1.2 | — |
| Vehicle insurance | Yes | Keep | Insurance document with expiry tracking | Operational compliance | Yes | Yes | Dr.1.2 | — |
| Background check status | Yes | Keep | Read-only status from backend/vendor result | Trust / safety | Yes | Yes | Dr.1.2 | Status only, no raw report |
| Document expiration alerts | Yes | Keep | Backend-evaluated expiry notifications | Continued authorization | Yes | Yes | Dr.1.4 | — |
| Rejection reason and resubmission | Yes | Keep | Reason surfaced; resubmit path | Remediation audit | Yes | Yes | Dr.1.2 | — |
| Expiring soon warnings | Yes | Keep | Proactive warnings before lapse | Continued authorization | Yes | Yes | Dr.1.4 | — |

### 5.4 Vehicle

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Vehicle profile | Yes | Adapt | Delivery vehicle record, no ride tiers | Operational record | Yes | Yes | Dr.1.2 | — |
| Make / model / year / color / plate | Yes | Keep | Standard vehicle attributes for handoff/identification | Identification | Yes | Yes | Dr.1.2 | — |
| Vehicle photo | Partial | Defer | Optional identification aid | Low | Future | Future | Dr.1.6 | Not MVP |
| Active vehicle selection | Partial | Adapt | Single active delivery vehicle | Operational record | Yes | Yes | Dr.1.3 | Simplified vs multi-vehicle |
| Vehicle approval status | Yes | Keep | Backend approval state | Authorization | Yes | Yes | Dr.1.2 | — |
| Passenger capacity | No | No | Rideshare concept; no passengers | None | No | No | N/A | Not applicable — delivery only |
| Ride class eligibility | No | No | UberX/XL/Black tiering does not exist | None | No | No | N/A | Not applicable — no ride classes |
| Airport permit requirements | No | No | No airport passenger operations | None | No | No | N/A | Not applicable — no airport queueing |

### 5.5 Driver Compliance

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Driver active status | Yes | Keep | Backend-decided active flag | Authorization gate | Yes | Yes | Dr.1.1 | — |
| Driver 21+ eligibility | Yes | NubeRush Upgrade | Required to be eligible for restricted deliveries | Driver age-gate | Yes | No | Dr.1.1 | Server-computed |
| Required documents approved | Yes | NubeRush Upgrade | Gate to go online / receive restricted offers | Document compliance | Yes | Yes | Dr.1.1 | — |
| Required vehicle approved | Yes | Keep | Gate to go online | Operational compliance | Yes | Yes | Dr.1.1 | — |
| Training completed | Yes | NubeRush Upgrade | Restricted-product training gate | Policy compliance | Yes | Yes | Dr.1.2 | — |
| Restricted-product policy acknowledged | Yes | NubeRush Upgrade | Explicit ack stored with audit | Policy audit | Yes | Yes | Dr.1.2 | NubeRush-specific |
| Suspension / block status | Yes | NubeRush Upgrade | Immediately removes delivery authority | Compliance enforcement | Yes | Yes | Dr.1.1 | Mobile cannot bypass |
| Device permission health | Yes | Adapt | Location/notification/camera checks before online | Operational safety | No | Yes | Dr.1.2 | Client-side check, surfaced to backend |

### 5.6 Training

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Delivery basics | Yes | Keep | Core delivery workflow training | Operational readiness | Yes | Yes | Dr.1.2 | — |
| Restricted-product policy | Yes | NubeRush Upgrade | Smoke-shop / vape handling rules | Policy compliance | Yes | Yes | Dr.1.2 | NubeRush-specific |
| 21+ verification policy | Yes | NubeRush Upgrade | How to perform manual age verification | Age-gate policy | Yes | Yes | Dr.1.2 | NubeRush-specific |
| Valid ID checklist | Yes | NubeRush Upgrade | What constitutes acceptable ID | Verification quality | Yes | Yes | Dr.1.2 | Drives manual checklist |
| Failed ID handling | Yes | NubeRush Upgrade | What to do when ID fails | Failed-delivery policy | Yes | Yes | Dr.1.2 | Leads to return-to-store |
| Return-to-store policy | Yes | NubeRush Upgrade | Accountable return procedure | Inventory/audit | Yes | Yes | Dr.1.2 | NubeRush-specific |
| Safety training | Yes | Keep | Field-safety procedures | Driver safety | Yes | Yes | Dr.1.2 | — |
| Incident reporting | Yes | Keep | How to report incidents | Safety audit | Yes | Yes | Dr.1.2 | — |
| Quiz / certification future | Partial | Defer | Graded certification of policy mastery | Verification assurance | Future | Future | Dr.1.5 | Future module |

### 5.7 Online / Offline

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Go online | Yes | Adapt | Online only if compliance gates pass | Authorization gate | Yes | Yes | Dr.1.3 | Backend authorizes online state |
| Go offline | Yes | Keep | Standard offline transition | Availability audit | Yes | Yes | Dr.1.3 | — |
| Pause requests | Yes | Keep | Temporarily stop receiving offers | Availability state | Yes | Yes | Dr.1.4 | — |
| Resume requests | Yes | Keep | Resume offer flow | Availability state | Yes | Yes | Dr.1.4 | — |
| Stop new requests | Yes | Keep | Finish current, accept no new | Availability state | Yes | Yes | Dr.1.4 | — |
| View online time | Yes | Keep | Session time visibility | Transparency | Yes | Yes | Dr.1.4 | — |
| View active time | Yes | Keep | Active-delivery time visibility | Transparency | Yes | Yes | Dr.1.4 | — |
| Permission checks before online | Yes | NubeRush Upgrade | Block online without required permissions | Operational safety | No | Yes | Dr.1.3 | Location required |
| GPS / network health check | Yes | Keep | Pre-online connectivity/GPS verification | Reliability | No | Yes | Dr.1.3 | — |

### 5.8 Delivery Offers

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| New delivery offer | Yes | Keep | Backend-issued offer for an existing order | Assignment audit | Yes | Yes | Dr.1.3 | No parallel order model |
| Offer timer | Yes | Keep | Time-boxed accept window | Assignment integrity | Yes | Yes | Dr.1.3 | Backend authoritative on expiry |
| Accept offer | Yes | Keep | Driver accepts; backend confirms | Assignment audit | Yes | Yes | Dr.1.3 | — |
| Decline offer | Yes | Keep | Driver declines | Assignment audit | Yes | Yes | Dr.1.3 | — |
| Decline reason | Yes | Keep | Structured decline reasons | Operational analytics | Yes | Yes | Dr.1.4 | — |
| Store name | Yes | Keep | Pickup store identity | Operational | Yes | Yes | Dr.1.3 | — |
| Store address | Yes | Keep | Pickup location | Operational | Yes | Yes | Dr.1.3 | — |
| Pickup distance | Yes | Keep | Distance to store | Operational | Yes | Yes | Dr.1.3 | — |
| Approximate dropoff zone | Yes | NubeRush Upgrade | Zone-level only pre-accept; no exact customer address | Customer privacy | Yes | Yes | Dr.1.3 | Privacy boundary |
| Estimated duration | Yes | Keep | Estimated trip time | Operational | Yes | Yes | Dr.1.4 | — |
| Estimated earnings | Partial | Defer | Earnings estimate visibility | Transparency | Future | Future | Dr.1.6 | Earnings is growth-phase |
| Restricted product flag | Yes | NubeRush Upgrade | Marks order as restricted before accept | Age-gate signal | Yes | Yes | Dr.1.3 | NubeRush-specific |
| ID required flag | Yes | NubeRush Upgrade | Signals mandatory 21+ verification | Age-gate signal | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Bag count / item count | Yes | Adapt | Item/bag count for pickup verification | Pickup accuracy | Yes | Yes | Dr.1.3 | — |
| Pre-accept privacy boundary | Yes | NubeRush Upgrade | Sensitive details withheld until accept | Customer privacy | Yes | Yes | Dr.1.3 | NubeRush-specific |

### 5.9 Assignment

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Assigned deliveries | Yes | Keep | Driver's current assignments | Assignment audit | Yes | Yes | Dr.1.3 | — |
| Offered deliveries | Yes | Keep | Pending offers awaiting response | Assignment audit | Yes | Yes | Dr.1.3 | — |
| Assignment accept / decline | Yes | Keep | Accept/decline actions submitted to backend | Assignment audit | Yes | Yes | Dr.1.3 | — |
| Assignment expiration | Yes | Keep | Backend expires stale assignments | Assignment integrity | Yes | Yes | Dr.1.3 | — |
| Reassignment support | Yes | Adapt | Backend can reassign on failure/decline | Continuity / audit | Yes | Yes | Dr.1.4 | — |
| Manual dispatch support | Yes | NubeRush Upgrade | Store/admin-driven dispatch via backend | Dispatch control | Yes | Yes | Dr.1.4 | Store dispatch bridge |
| Auto-dispatch future | Partial | Defer | Automated assignment algorithm | Operational scale | Future | Future | Future | Not MVP |
| Driver-scoped order visibility | Yes | NubeRush Upgrade | Driver sees only assigned orders, never store-wide | Access scoping | Yes | Yes | Dr.1.1 | Core authority rule |

### 5.10 Active Delivery

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Active delivery overview | Yes | Keep | Current delivery state machine view | Lifecycle audit | Yes | Yes | Dr.1.3 | Plugs into existing order lifecycle |
| En route to store | Yes | Keep | Transit-to-pickup state | Lifecycle audit | Yes | Yes | Dr.1.3 | — |
| Arrived at store | Yes | Keep | Geofence-aware arrival | Lifecycle audit | Yes | Yes | Dr.1.3 | — |
| Waiting at store | Yes | Keep | Awaiting order ready | Operational | Yes | Yes | Dr.1.4 | — |
| Pickup confirmed | Yes | NubeRush Upgrade | Confirmed via store handoff accountability | Handoff audit | Yes | Yes | Dr.1.3 | Backend authorizes transition |
| En route to customer | Yes | Keep | Out-for-delivery transit | Lifecycle audit | Yes | Yes | Dr.1.3 | — |
| Arrived at customer | Yes | Keep | Geofence-aware arrival | Lifecycle audit | Yes | Yes | Dr.1.3 | — |
| Verification in progress | Yes | NubeRush Upgrade | 21+ manual verification step | Age-gate enforcement | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Delivery completed | Yes | NubeRush Upgrade | Allowed only after proof + verification pass | Completion gate | Yes | Yes | Dr.1.3 | Backend-authorized |
| Delivery failed | Yes | NubeRush Upgrade | Structured failure with reason | Failure audit | Yes | Yes | Dr.1.3 | — |
| Return required | Yes | NubeRush Upgrade | Restricted failures force return path | Inventory/audit | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Returned to store | Yes | NubeRush Upgrade | Accountable return completion | Inventory/audit | Yes | Yes | Dr.1.3 | Store confirms |

### 5.11 Store Pickup

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Navigate to store | Yes | Keep | Route to pickup store | Operational | No | Yes | Dr.1.3 | External nav handoff |
| Store pickup instructions | Yes | Keep | Store-specific pickup notes | Operational | Yes | Yes | Dr.1.3 | — |
| Order number match | Yes | Keep | Match order at pickup | Pickup accuracy | Yes | Yes | Dr.1.3 | — |
| Bag count confirmation | Yes | Adapt | Confirm item/bag count at pickup | Pickup accuracy | Yes | Yes | Dr.1.3 | — |
| Item count indicator | Yes | Adapt | Expected item count display | Pickup accuracy | Yes | Yes | Dr.1.3 | — |
| Order ready status | Yes | Adapt | "Restaurant ready" becomes store order ready | Operational | Yes | Yes | Dr.1.3 | — |
| Pickup checklist | Yes | NubeRush Upgrade | Includes restricted-product confirmation | Pickup compliance | Yes | Yes | Dr.1.3 | — |
| Pickup issue report | Yes | Keep | Report pickup problems | Operational audit | Yes | Yes | Dr.1.3 | — |
| Store closed issue | Yes | Keep | Handle closed-store case | Operational audit | Yes | Yes | Dr.1.4 | — |
| Store order not ready | Yes | Adapt | "Restaurant not ready" becomes store not ready | Operational audit | Yes | Yes | Dr.1.4 | — |

### 5.12 Store Handoff

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Store employee PIN | Yes | NubeRush Upgrade | PIN-based release accountability at pickup | Handoff audit | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Store employee confirmation | Yes | NubeRush Upgrade | Store-side confirms release to driver | Handoff audit | Yes | Yes | Dr.1.3 | Backend records |
| QR / barcode handoff future | Partial | Defer | Scan-based handoff | Handoff integrity | Future | Future | Dr.1.5 | Future upgrade |
| Manager override future | Partial | Defer | Supervisor override path | Handoff audit | Future | Future | Dr.1.5 | Future |
| Store-side release accountability | Yes | NubeRush Upgrade | Store is accountable for release | Compliance audit | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Handoff audit event | Yes | NubeRush Upgrade | Handoff recorded in audit timeline | Compliance audit | Yes | Yes | Dr.1.3 | — |

### 5.13 Navigation

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Map view | Yes | Keep | In-app map context | Operational | No | Yes | Dr.1.3 | — |
| Open Apple Maps | Yes | Keep | External nav handoff | Operational | No | Yes | Dr.1.3 | — |
| Open Google Maps | Yes | Keep | External nav handoff | Operational | No | Yes | Dr.1.3 | — |
| Open Waze | Yes | Keep | External nav handoff | Operational | No | Yes | Dr.1.3 | — |
| Store route | Yes | Keep | Route to pickup | Operational | No | Yes | Dr.1.3 | — |
| Customer route | Yes | Keep | Route to dropoff | Operational | No | Yes | Dr.1.3 | — |
| Return-to-store route | Yes | NubeRush Upgrade | Route for return flow | Return audit | No | Yes | Dr.1.3 | NubeRush-specific |
| ETA | Yes | Keep | Estimated arrival | Operational | Yes | Yes | Dr.1.4 | — |
| Distance | Yes | Keep | Distance display | Operational | No | Yes | Dr.1.3 | — |
| Route recalculation future | Partial | Defer | Dynamic recalculation | Operational | Future | Future | Dr.1.6 | Future |
| CarPlay / Android Auto future | Partial | Defer | In-car integration | Operational | Future | Future | Future | Not MVP |
| Internal turn-by-turn future | Partial | Defer | In-app navigation engine | Operational | Future | Future | Future | External nav first |

### 5.14 Customer Dropoff

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Navigate to customer | Yes | Keep | Route to dropoff | Operational | No | Yes | Dr.1.3 | — |
| Delivery instructions | Yes | Keep | Customer delivery notes | Operational | Yes | Yes | Dr.1.3 | — |
| Contact customer | Yes | Adapt | Masked contact only | Privacy | Yes | Yes | Dr.1.3 | — |
| Arrived at customer | Yes | Keep | Arrival marker | Lifecycle audit | Yes | Yes | Dr.1.3 | — |
| Meet customer | Yes | NubeRush Upgrade | Customer-present required for restricted | Age-gate enforcement | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Leave at door | Partial | NubeRush Upgrade | Forbidden for restricted products | Age-gate enforcement | Yes | Yes | Dr.1.3 | No unattended restricted delivery |
| Meet at door | Yes | Keep | In-person handoff option | Operational | Yes | Yes | Dr.1.3 | — |
| Meet outside | Yes | Keep | In-person handoff option | Operational | Yes | Yes | Dr.1.3 | — |
| Customer unavailable flow | Yes | NubeRush Upgrade | Leads to failed delivery + return for restricted | Failure/return audit | Yes | Yes | Dr.1.3 | NubeRush-specific |

### 5.15 Restricted Product Delivery

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Restricted product warning | Yes | NubeRush Upgrade | Explicit restricted-handling prompts | Age-gate signal | Yes | Yes | Dr.1.3 | NubeRush-specific |
| No unattended delivery | Yes | NubeRush Upgrade | Hard rule for restricted products | Age-gate enforcement | Yes | Yes | Dr.1.3 | Cannot leave at door |
| Customer present required | Yes | NubeRush Upgrade | Recipient must be present | Age-gate enforcement | Yes | Yes | Dr.1.3 | — |
| ID required | Yes | NubeRush Upgrade | ID check mandatory | Age-gate enforcement | Yes | Yes | Dr.1.3 | — |
| Valid ID required | Yes | NubeRush Upgrade | Acceptable, unexpired ID required | Age-gate enforcement | Yes | Yes | Dr.1.3 | — |
| 21+ required | Yes | NubeRush Upgrade | Recipient must be 21+ | Age-gate enforcement | Yes | Yes | Dr.1.3 | — |
| Wrong recipient handling | Yes | NubeRush Upgrade | Block delivery to non-orderer if required | Compliance enforcement | Yes | Yes | Dr.1.3 | — |
| Customer refusal handling | Yes | NubeRush Upgrade | Refusal → failed delivery → return | Failure/return audit | Yes | Yes | Dr.1.3 | — |
| Suspected fake ID handling | Yes | NubeRush Upgrade | Defined refusal + report procedure | Compliance/safety | Yes | Yes | Dr.1.3 | Return-to-store |
| Unsafe situation handling | Yes | NubeRush Upgrade | Abort path with safety + audit | Safety/compliance | Yes | Yes | Dr.1.3 | Links safety toolkit |

### 5.16 Age / ID Verification

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Manual ID checklist (MVP) | Yes | NubeRush Upgrade | Driver confirms checklist; backend records result | Age-gate enforcement | Yes | Yes | Dr.1.3 | MVP verification mechanism |
| ID scan future | Partial | Defer | Document scan | Verification assurance | Future | Future | Dr.1.5 | Legal/compliance gated |
| OCR future | Partial | Defer | Text extraction | Verification assurance | Future | Future | Dr.1.5 | Not in MVP |
| Barcode scan future | Partial | Defer | ID barcode parsing | Verification assurance | Future | Future | Dr.1.5 | Not in MVP |
| Liveness future | Partial | Defer | Liveness check | Verification assurance | Future | Future | Dr.1.5 | Not in MVP |
| Vendor verification future | Partial | Defer | Third-party verification | Verification assurance | Future | Future | Dr.1.5 | Not in MVP |
| Verification pass | Yes | NubeRush Upgrade | Pass recorded; unlocks completion | Completion gate | Yes | Yes | Dr.1.3 | Backend-authorized |
| Verification fail | Yes | NubeRush Upgrade | Fail blocks completion → return | Failure/return audit | Yes | Yes | Dr.1.3 | — |
| Manual review future | Partial | Defer | Human review queue | Verification assurance | Future | Future | Dr.1.5 | Future |
| Privacy / redaction boundary | Yes | NubeRush Upgrade | No raw ID images stored | Data privacy | Yes | Yes | Dr.1.3 | Hard boundary |

### 5.17 Proof of Delivery

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Driver attestation | Yes | NubeRush Upgrade | Driver attests delivery + verification facts | Proof audit | Yes | Yes | Dr.1.3 | MVP proof element |
| GPS timestamp | Yes | NubeRush Upgrade | Location+time attached to proof | Proof audit | Yes | Yes | Dr.1.3 | — |
| Customer PIN future | Partial | Defer | Customer-provided PIN | Proof assurance | Future | Future | Dr.1.5 | Future |
| Signature future | Partial | Defer | Captured signature | Proof assurance | Future | Future | Dr.1.5 | Future |
| Photo proof future | Partial | Defer | Delivery photo (non-ID) | Proof assurance | Future | Future | Dr.1.5 | No ID images |
| Barcode proof future | Partial | Defer | Scan-based proof | Proof assurance | Future | Future | Dr.1.5 | Future |
| Verification result attached to proof | Yes | NubeRush Upgrade | 21+ result bound to proof record | Compliance audit | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Backend authorization before completion | Yes | NubeRush Upgrade | Backend validates proof before completing | Completion gate | Yes | Yes | Dr.1.3 | Core authority rule |

### 5.18 Failed Delivery

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Customer not available | Yes | NubeRush Upgrade | Structured reason → return for restricted | Failure/return audit | Yes | Yes | Dr.1.3 | — |
| Customer not answering | Yes | Keep | Structured failure reason | Failure audit | Yes | Yes | Dr.1.3 | — |
| No valid ID | Yes | NubeRush Upgrade | Verification failure reason | Age-gate enforcement | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Expired ID | Yes | NubeRush Upgrade | Verification failure reason | Age-gate enforcement | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Underage | Yes | NubeRush Upgrade | Hard block; no delivery | Age-gate enforcement | Yes | Yes | Dr.1.3 | Return-to-store |
| ID mismatch | Yes | NubeRush Upgrade | Recipient mismatch failure | Compliance enforcement | Yes | Yes | Dr.1.3 | — |
| Wrong recipient | Yes | NubeRush Upgrade | Not the authorized recipient | Compliance enforcement | Yes | Yes | Dr.1.3 | — |
| Customer refused verification | Yes | NubeRush Upgrade | Refusal failure reason | Age-gate enforcement | Yes | Yes | Dr.1.3 | — |
| Unsafe location | Yes | Keep | Safety-driven failure | Safety audit | Yes | Yes | Dr.1.3 | Links safety toolkit |
| Wrong address | Yes | Keep | Address failure reason | Operational audit | Yes | Yes | Dr.1.3 | — |
| Driver emergency | Yes | Keep | Driver-side abort | Safety audit | Yes | Yes | Dr.1.3 | — |
| Vehicle issue | Yes | Keep | Vehicle-driven failure | Operational audit | Yes | Yes | Dr.1.4 | — |
| App issue | Yes | Keep | Technical failure path | Reliability audit | Yes | Yes | Dr.1.4 | — |
| Support required | Yes | Keep | Escalate to support | Support audit | Yes | Yes | Dr.1.4 | — |

### 5.19 Return to Store

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Return required screen | Yes | NubeRush Upgrade | Triggered on restricted failure | Inventory/audit | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Navigate back to store | Yes | NubeRush Upgrade | Route to originating store | Return audit | No | Yes | Dr.1.3 | — |
| Return reason | Yes | NubeRush Upgrade | Reason carried from failure | Audit linkage | Yes | Yes | Dr.1.3 | — |
| Store return PIN | Yes | NubeRush Upgrade | PIN-based return accountability | Handoff audit | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Store employee confirmation | Yes | NubeRush Upgrade | Store confirms receipt of return | Inventory/audit | Yes | Yes | Dr.1.3 | — |
| Return completed | Yes | NubeRush Upgrade | Backend closes return | Inventory/audit | Yes | Yes | Dr.1.3 | — |
| Inventory review through backend | Yes | NubeRush Upgrade | Inventory implications handled server-side | Inventory integrity | Yes | No | Dr.1.1 | Backend authority |
| Driver cannot self-close restricted return | Yes | NubeRush Upgrade | Driver cannot unilaterally close | Compliance enforcement | Yes | Yes | Dr.1.3 | Store/backend confirm |

### 5.20 Safety

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Safety toolkit | Yes | Adapt | Driver Delivery Safety Toolkit | Driver safety | Yes | Yes | Dr.1.4 | Delivery-context safety |
| Emergency button | Yes | Keep | Quick emergency access | Driver safety | Yes | Yes | Dr.1.4 | — |
| Call 911 | Yes | Keep | Direct emergency call | Driver safety | No | Yes | Dr.1.4 | — |
| Share current location | Yes | Keep | Share location with support/admin | Safety audit | Yes | Yes | Dr.1.4 | — |
| Share active route with support/admin | Yes | Adapt | Share route to oversight, not public | Safety audit | Yes | Yes | Dr.1.4 | — |
| Report unsafe location | Yes | Keep | Structured safety report | Safety audit | Yes | Yes | Dr.1.4 | — |
| Report threatening customer | Yes | Keep | Structured safety report | Safety audit | Yes | Yes | Dr.1.4 | — |
| Report accident | Yes | Keep | Accident reporting | Safety audit | Yes | Yes | Dr.1.4 | — |
| Report vehicle issue | Yes | Keep | Vehicle issue reporting | Operational audit | Yes | Yes | Dr.1.4 | — |
| Cancel for safety | Yes | Adapt | Safety-driven abort → failure/return | Safety/return audit | Yes | Yes | Dr.1.4 | — |
| Long stop detection future | Partial | Defer | Anomaly detection | Safety assurance | Future | Future | Future | Not MVP |
| Route deviation detection future | Partial | Defer | Anomaly detection | Safety assurance | Future | Future | Future | Not MVP |

### 5.21 Communication

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Call customer | Yes | Adapt | Masked voice call | Privacy | Yes | Yes | Dr.1.3 | — |
| Message customer | Yes | Adapt | Controlled messaging | Privacy | Yes | Yes | Dr.1.4 | — |
| Call store | Yes | Keep | Store contact | Operational | Yes | Yes | Dr.1.3 | — |
| Message store | Yes | Keep | Store messaging | Operational | Yes | Yes | Dr.1.4 | — |
| Contact support | Yes | Keep | Support channel | Support audit | Yes | Yes | Dr.1.4 | — |
| Masked phone numbers | Yes | NubeRush Upgrade | No raw customer numbers exposed | Privacy | Yes | Yes | Dr.1.3 | Privacy boundary |
| Quick messages | Yes | Keep | Canned message templates | Operational | Yes | Yes | Dr.1.4 | — |
| Controlled compliance messages | Yes | NubeRush Upgrade | Compliance-safe message set | Compliance | Yes | Yes | Dr.1.4 | NubeRush-specific |
| Message history future | Partial | Defer | Persistent thread history | Support audit | Future | Future | Dr.1.6 | Future |

### 5.22 Support

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Help center | Yes | Keep | In-app help | Support | Yes | Yes | Dr.1.4 | — |
| Pickup problem | Yes | Keep | Pickup issue topic | Operational audit | Yes | Yes | Dr.1.4 | — |
| Store problem | Yes | Keep | Store issue topic | Operational audit | Yes | Yes | Dr.1.4 | — |
| Customer problem | Yes | Keep | Customer issue topic | Operational audit | Yes | Yes | Dr.1.4 | — |
| ID verification problem | Yes | NubeRush Upgrade | Verification-specific support path | Compliance support | Yes | Yes | Dr.1.4 | NubeRush-specific |
| Unsafe delivery | Yes | Keep | Safety escalation topic | Safety audit | Yes | Yes | Dr.1.4 | — |
| Accident | Yes | Keep | Accident support topic | Safety audit | Yes | Yes | Dr.1.4 | — |
| Vehicle issue | Yes | Keep | Vehicle support topic | Operational audit | Yes | Yes | Dr.1.4 | — |
| App issue | Yes | Keep | Technical support topic | Reliability | Yes | Yes | Dr.1.4 | — |
| Earnings question | Partial | Defer | Earnings support topic | Transparency | Future | Future | Dr.1.6 | With earnings |
| Policy question | Yes | Keep | Policy support topic | Compliance support | Yes | Yes | Dr.1.4 | — |
| Support ticket | Yes | Keep | Structured ticket | Support audit | Yes | Yes | Dr.1.4 | — |
| Support chat future | Partial | Defer | Live chat | Support | Future | Future | Dr.1.6 | Future |

### 5.23 Earnings

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Estimated earnings per delivery | Partial | Defer | Visibility only, no payout | None (pre-payout) | Future | Future | Dr.1.6 | No payouts in scope |
| Completed delivery count | Yes | Keep | Operational count | Transparency | Yes | Yes | Dr.1.4 | — |
| Delivery history | Yes | Keep | Past deliveries (driver-scoped) | Transparency/audit | Yes | Yes | Dr.1.4 | — |
| Earnings summary placeholder | Partial | Defer | Visibility placeholder, no money movement | None (pre-payout) | Future | Future | Dr.1.6 | — |
| Daily earnings future | Partial | Defer | Daily rollups | Transparency | Future | Future | Dr.1.6 | — |
| Weekly earnings future | Partial | Defer | Weekly rollups | Transparency | Future | Future | Dr.1.6 | — |
| Tips future | Partial | Defer | Tip handling | Payment-linked | Future | Future | Future | Post-payments |
| Bonuses future | Partial | Defer | Bonus handling | Payment-linked | Future | Future | Future | Post-payments |
| Adjustments future | Partial | Defer | Earnings adjustments | Payment-linked | Future | Future | Future | Post-payments |
| Cashout | No (now) | Defer | Payout action | Payment-linked | Future | Future | Future | Out of Dr.1.0 scope |
| Payout method | No (now) | Defer | Payout configuration | Payment-linked | Future | Future | Future | Out of Dr.1.0 scope |
| Tax summary future | Partial | Defer | Tax documents | Payment-linked | Future | Future | Future | Post-payments |

### 5.24 Promotions / Opportunities

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Busy zones | Partial | Defer | Demand visualization | None | Future | Future | Dr.1.6 | Growth-phase |
| Bonus windows | Partial | Defer | Time-based incentives | Payment-linked | Future | Future | Future | Post-payments |
| Scheduled shifts | Partial | Defer | Shift scheduling | Operational | Future | Future | Dr.1.6 | Growth-phase |
| Store demand zones | Partial | Defer | Store-level demand hints | Operational | Future | Future | Dr.1.6 | — |
| High demand alerts | Partial | Defer | Demand notifications | Operational | Future | Future | Dr.1.6 | — |
| Legal delivery zones | Yes | NubeRush Upgrade | Legal-zone enforcement is core | Legal compliance | Yes | Yes | Dr.1.4 | NubeRush-specific |
| Restricted delivery radius | Yes | NubeRush Upgrade | Restricted-product delivery bounds | Legal compliance | Yes | Yes | Dr.1.4 | NubeRush-specific |
| Delivery opportunities future | Partial | Defer | Opportunity surfacing | Operational | Future | Future | Dr.1.6 | — |

### 5.25 Performance

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Completed deliveries | Yes | Keep | Core performance metric | Transparency | Yes | Yes | Dr.1.4 | — |
| Failed deliveries | Yes | Keep | Failure metric | Operational audit | Yes | Yes | Dr.1.4 | — |
| Return rate | Yes | NubeRush Upgrade | Restricted-return rate metric | Compliance signal | Yes | Yes | Dr.1.6 | NubeRush-specific |
| Pickup on-time rate | Yes | Keep | Pickup punctuality | Operational | Yes | Yes | Dr.1.6 | — |
| Delivery on-time rate | Yes | Keep | Delivery punctuality | Operational | Yes | Yes | Dr.1.6 | — |
| Acceptance rate | Yes | Keep | Offer acceptance metric | Operational | Yes | Yes | Dr.1.6 | — |
| Decline rate | Yes | Keep | Offer decline metric | Operational | Yes | Yes | Dr.1.6 | — |
| Cancellation rate | Yes | Keep | Cancellation metric | Operational | Yes | Yes | Dr.1.6 | — |
| Proof completion rate | Yes | NubeRush Upgrade | Proof-of-delivery completeness | Compliance signal | Yes | Yes | Dr.1.6 | NubeRush-specific |
| Compliance incident count | Yes | NubeRush Upgrade | Compliance events count | Compliance signal | Yes | Yes | Dr.1.6 | NubeRush-specific |
| Restricted delivery success rate | Yes | NubeRush Upgrade | Restricted-delivery success metric | Compliance signal | Yes | Yes | Dr.1.6 | NubeRush-specific |
| Audit cleanliness score | Yes | NubeRush Upgrade | Audit-completeness indicator | Compliance signal | Yes | Yes | Dr.1.6 | NubeRush-specific |
| Customer rating | Partial | Defer | Optional later, not rideshare-style | Reputation | Future | Future | Dr.1.6 | Not MVP |
| Store rating | Partial | Defer | Optional store feedback | Reputation | Future | Future | Dr.1.6 | Not MVP |

### 5.26 Rewards / Driver Status

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Uber Pro style tiers | Partial | Adapt | Becomes NubeRush driver status, not Uber Pro | Reputation | Future | Future | Dr.1.6 | Not a copy |
| NubeRush driver status | Yes | NubeRush Upgrade | Status tied to compliance + performance | Compliance signal | Yes | Yes | Dr.1.6 | NubeRush-specific |
| Compliance Trusted badge | Yes | NubeRush Upgrade | Earned via clean compliance record | Compliance signal | Yes | Yes | Dr.1.6 | NubeRush-specific |
| Restricted Delivery Certified badge | Yes | NubeRush Upgrade | Earned via restricted-delivery readiness | Compliance signal | Yes | Yes | Dr.1.6 | NubeRush-specific |
| Priority deliveries future | Partial | Defer | Status-based priority | Operational | Future | Future | Dr.1.6 | — |
| Bonus eligibility future | Partial | Defer | Status-based bonuses | Payment-linked | Future | Future | Future | Post-payments |
| Preferred shifts future | Partial | Defer | Status-based scheduling | Operational | Future | Future | Dr.1.6 | — |

### 5.27 Notifications

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| New delivery offer | Yes | Keep | Offer push | Operational | Yes | Yes | Dr.1.3 | — |
| Delivery assigned | Yes | Keep | Assignment push | Operational | Yes | Yes | Dr.1.3 | — |
| Offer expiring | Yes | Keep | Expiry push | Operational | Yes | Yes | Dr.1.3 | — |
| Order ready | Yes | Adapt | Store-order-ready push | Operational | Yes | Yes | Dr.1.3 | — |
| Pickup reminder | Yes | Keep | Pickup nudge | Operational | Yes | Yes | Dr.1.4 | — |
| Customer message | Yes | Keep | Message push | Operational | Yes | Yes | Dr.1.4 | — |
| Store message | Yes | Keep | Message push | Operational | Yes | Yes | Dr.1.4 | — |
| Support response | Yes | Keep | Support push | Support | Yes | Yes | Dr.1.4 | — |
| ID verification required | Yes | NubeRush Upgrade | Verification prompt push | Age-gate signal | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Return required | Yes | NubeRush Upgrade | Return-flow push | Return audit | Yes | Yes | Dr.1.3 | NubeRush-specific |
| Document expiring | Yes | Keep | Expiry push | Authorization | Yes | Yes | Dr.1.4 | — |
| Document rejected | Yes | Keep | Rejection push | Authorization | Yes | Yes | Dr.1.4 | — |
| Account approved | Yes | Keep | Approval push | Authorization | Yes | Yes | Dr.1.2 | — |
| Account blocked | Yes | NubeRush Upgrade | Block push; revokes authority | Compliance enforcement | Yes | Yes | Dr.1.1 | — |
| GPS issue | Yes | Keep | Diagnostics push | Reliability | No | Yes | Dr.1.4 | — |
| Network issue | Yes | Keep | Diagnostics push | Reliability | No | Yes | Dr.1.4 | — |
| Low battery | Yes | Keep | Reliability nudge | Reliability | No | Yes | Dr.1.4 | — |
| Policy update | Yes | NubeRush Upgrade | Policy-ack prompt | Policy audit | Yes | Yes | Dr.1.4 | — |
| App update required | Yes | Keep | Version-enforcement push | Reliability | Yes | Yes | Dr.1.4 | — |

### 5.28 Settings

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Profile | Yes | Keep | Profile settings | Identity | Yes | Yes | Dr.1.2 | — |
| Vehicle | Yes | Keep | Vehicle settings | Operational | Yes | Yes | Dr.1.2 | — |
| Documents | Yes | Keep | Document management | Authorization | Yes | Yes | Dr.1.2 | — |
| Notification preferences | Yes | Keep | Notification controls | Operational | Yes | Yes | Dr.1.4 | Compliance pushes non-optional |
| Sound settings | Yes | Keep | Sound controls | Operational | No | Yes | Dr.1.4 | — |
| Navigation preferences | Yes | Keep | Default nav app | Operational | No | Yes | Dr.1.3 | — |
| Privacy | Yes | NubeRush Upgrade | Privacy controls + data-handling info | Data privacy | Yes | Yes | Dr.1.4 | — |
| Security | Yes | Keep | Security controls | Account integrity | Yes | Yes | Dr.1.4 | — |
| Permissions | Yes | Keep | OS permission management | Reliability | No | Yes | Dr.1.3 | — |
| Language | Yes | Keep | Localization | Accessibility | No | Yes | Dr.1.4 | — |
| Help | Yes | Keep | Help entry | Support | Yes | Yes | Dr.1.4 | — |
| Legal | Yes | NubeRush Upgrade | Legal/compliance disclosures | Legal compliance | Yes | Yes | Dr.1.2 | — |
| App version | Yes | Keep | Version display | Reliability | No | Yes | Dr.1.2 | — |
| Diagnostics | Yes | Keep | Diagnostics view | Reliability | No | Yes | Dr.1.4 | — |
| Logout | Yes | Keep | Session end | Account integrity | Yes | Yes | Dr.1.2 | — |
| Delete account | Partial | Defer | Account deletion request | Data privacy | Future | Future | Dr.1.5 | Backend-gated process |

### 5.29 Geofencing / Legal Zones

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Store geofence | Yes | Adapt | Geofence for store arrival/pickup | Lifecycle integrity | Yes | Yes | Dr.1.3 | — |
| Dropoff geofence | Yes | Adapt | Geofence for customer arrival | Lifecycle integrity | Yes | Yes | Dr.1.3 | — |
| Legal delivery zone | Yes | NubeRush Upgrade | Restricted delivery only in legal zones | Legal compliance | Yes | Yes | Dr.1.4 | NubeRush-specific |
| Blocked zone | Yes | NubeRush Upgrade | No-delivery zones enforced | Legal compliance | Yes | Yes | Dr.1.4 | NubeRush-specific |
| Restricted zone | Yes | NubeRush Upgrade | Restricted-product-specific zones | Legal compliance | Yes | Yes | Dr.1.4 | NubeRush-specific |
| Delivery radius | Yes | Adapt | Store delivery radius bounds | Operational | Yes | Yes | Dr.1.4 | — |
| High-risk area | Yes | Adapt | Safety-flagged areas | Safety | Yes | Yes | Dr.1.4 | — |
| Pickup confirmation distance enforcement | Yes | NubeRush Upgrade | Pickup confirm requires proximity | Lifecycle integrity | Yes | Yes | Dr.1.3 | Backend validates |
| Delivery completion distance enforcement | Yes | NubeRush Upgrade | Completion requires proximity | Completion gate | Yes | Yes | Dr.1.3 | Backend validates |

### 5.30 Technical Reliability

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Offline handling | Yes | Keep | Graceful offline behavior | Reliability | Yes | Yes | Dr.1.2 | — |
| Retry queue | Yes | NubeRush Upgrade | Reliable action retry without double-effects | Audit integrity | Yes | Yes | Dr.1.2 | Pairs with idempotency |
| Idempotent actions | Yes | NubeRush Upgrade | Critical transitions idempotent | Audit integrity | Yes | Yes | Dr.1.1 | Backend-enforced |
| Secure token storage | Yes | Keep | OS secure storage for tokens | Security | No | Yes | Dr.1.2 | — |
| Refresh tokens | Yes | Keep | Token refresh flow | Security | Yes | Yes | Dr.1.2 | — |
| Device binding future | Partial | Defer | Bind session to device | Security | Future | Future | Dr.1.5 | Future |
| Push notifications | Yes | Keep | Push infrastructure | Operational | Yes | Yes | Dr.1.2 | Foundation |
| Background location future | Partial | Defer | Background tracking | Operational/privacy | Future | Future | Dr.1.4 | Privacy-reviewed |
| Crash reporting | Yes | Keep | Crash telemetry | Reliability | Yes | Yes | Dr.1.2 | — |
| Network diagnostics | Yes | Keep | Network checks | Reliability | No | Yes | Dr.1.2 | — |
| GPS diagnostics | Yes | Keep | GPS checks | Reliability | No | Yes | Dr.1.2 | — |
| State restoration | Yes | Keep | Resume after kill | Reliability | Yes | Yes | Dr.1.2 | — |
| Remote config | Yes | Keep | Server-driven config | Operational | Yes | Yes | Dr.1.2 | — |
| Feature flags | Yes | Keep | Gated rollout | Operational | Yes | Yes | Dr.1.2 | — |
| App version enforcement | Yes | Keep | Minimum-version gate | Reliability | Yes | Yes | Dr.1.2 | — |
| Event logging | Yes | NubeRush Upgrade | Compliance-grade event logging | Audit integrity | Yes | Yes | Dr.1.1 | Feeds audit timeline |
| Monitoring | Yes | Keep | Operational monitoring | Reliability | Yes | No | Dr.1.1 | Server-side |

### 5.31 Audit / Compliance Timeline

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Driver online event | Yes | NubeRush Upgrade | Recorded in compliance timeline | Audit | Yes | Yes | Dr.1.1 | — |
| Driver offline event | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Delivery offered | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Delivery accepted | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Delivery declined | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Driver assigned | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Arrived at store | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Store handoff started | Yes | NubeRush Upgrade | Recorded | Handoff audit | Yes | Yes | Dr.1.1 | — |
| Store handoff confirmed | Yes | NubeRush Upgrade | Recorded | Handoff audit | Yes | Yes | Dr.1.1 | — |
| Pickup confirmed | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Out for delivery | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Arrived at customer | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Customer contacted | Yes | NubeRush Upgrade | Recorded | Audit | Yes | Yes | Dr.1.1 | — |
| Verification started | Yes | NubeRush Upgrade | Recorded | Age-gate audit | Yes | Yes | Dr.1.1 | — |
| Age verification passed | Yes | NubeRush Upgrade | Recorded | Age-gate audit | Yes | Yes | Dr.1.1 | — |
| Age verification failed | Yes | NubeRush Upgrade | Recorded | Age-gate audit | Yes | Yes | Dr.1.1 | — |
| Proof recorded | Yes | NubeRush Upgrade | Recorded | Proof audit | Yes | Yes | Dr.1.1 | — |
| Delivery completed | Yes | NubeRush Upgrade | Recorded | Completion audit | Yes | Yes | Dr.1.1 | — |
| Delivery failed | Yes | NubeRush Upgrade | Recorded | Failure audit | Yes | Yes | Dr.1.1 | — |
| Return required | Yes | NubeRush Upgrade | Recorded | Return audit | Yes | Yes | Dr.1.1 | — |
| Return started | Yes | NubeRush Upgrade | Recorded | Return audit | Yes | Yes | Dr.1.1 | — |
| Returned to store | Yes | NubeRush Upgrade | Recorded | Return audit | Yes | Yes | Dr.1.1 | — |
| Store return confirmed | Yes | NubeRush Upgrade | Recorded | Inventory/audit | Yes | Yes | Dr.1.1 | — |
| Safety issue reported | Yes | NubeRush Upgrade | Recorded | Safety audit | Yes | Yes | Dr.1.1 | — |
| Support case opened | Yes | NubeRush Upgrade | Recorded | Support audit | Yes | Yes | Dr.1.1 | — |

### 5.32 Rideshare-only / Not Applicable

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| UberX | No | No | No ride tiers exist in NubeRush | None | No | No | N/A | Rideshare-only — delivery platform has no ride classes |
| Comfort | No | No | No ride tiers | None | No | No | N/A | Rideshare-only |
| XL | No | No | No ride tiers | None | No | No | N/A | Rideshare-only |
| Black | No | No | No ride tiers | None | No | No | N/A | Rideshare-only |
| Uber Pet | No | No | No passenger/pet rides | None | No | No | N/A | Rideshare-only |
| Passenger pickup | No | No | NubeRush picks up orders at stores, not people | None | No | No | N/A | No passenger transport |
| Passenger dropoff | No | No | NubeRush delivers products, not passengers | None | No | No | N/A | No passenger transport |
| Passenger destination changes | No | No | No passenger trips to modify | None | No | No | N/A | Not applicable |
| Multi-rider trips | No | No | No shared passenger rides | None | No | No | N/A | Not applicable |
| Passenger no-show | No | No | Customer-unavailable is handled via failed delivery instead | None | No | No | N/A | Replaced by failed delivery / return |
| Lost passenger items | No | No | No in-vehicle passenger belongings | None | No | No | N/A | Not applicable |
| Ride fare calculation | No | No | No fare meter; delivery economics differ | None | No | No | N/A | No ride fares |
| Airport queue | No | No | No airport passenger staging | None | No | No | N/A | Not applicable |
| Airport staging lot | No | No | No airport operations | None | No | No | N/A | Not applicable |
| Passenger ratings | No | No | No rider-of-driver rating model | None | No | No | N/A | Not a rideshare reputation system |
| Rider complaint flow | No | No | Replaced by support + compliance reporting | None | No | No | N/A | Not applicable |
| In-car passenger safety flow | No | No | No in-vehicle passenger; driver safety toolkit instead | None | No | No | N/A | Replaced by Driver Delivery Safety Toolkit |

### 5.33 Store / Admin Visibility Bridge

| Uber-style feature | Applies? | Decision | NubeRush adaptation | Compliance impact | Backend? | Mobile? | Phase | Notes |
|---|---|---|---|---|---|---|---|---|
| Store sees assigned driver | Yes | NubeRush Upgrade | Surfaced in existing Store Panel via backend | Oversight | Yes | No | Dr.1.4 | Web surface, not driver app |
| Store sees driver en route | Yes | NubeRush Upgrade | Store Panel visibility | Oversight | Yes | No | Dr.1.4 | — |
| Store confirms pickup handoff | Yes | NubeRush Upgrade | Store-side handoff confirmation | Handoff audit | Yes | No | Dr.1.4 | Backend records |
| Store sees out for delivery | Yes | NubeRush Upgrade | Store Panel visibility | Oversight | Yes | No | Dr.1.4 | — |
| Store sees failed delivery | Yes | NubeRush Upgrade | Store Panel visibility | Failure oversight | Yes | No | Dr.1.4 | — |
| Store sees return required | Yes | NubeRush Upgrade | Store Panel visibility | Return oversight | Yes | No | Dr.1.4 | — |
| Store confirms returned order | Yes | NubeRush Upgrade | Store-side return confirmation | Inventory/audit | Yes | No | Dr.1.4 | — |
| Admin sees driver compliance | Yes | NubeRush Upgrade | Admin Panel oversight | Compliance oversight | Yes | No | Dr.1.4 | — |
| Admin sees delivery audit timeline | Yes | NubeRush Upgrade | Admin Panel audit view | Compliance oversight | Yes | No | Dr.1.4 | — |
| Admin sees incident reports | Yes | NubeRush Upgrade | Admin Panel safety oversight | Safety oversight | Yes | No | Dr.1.4 | — |
| Admin sees verification failure patterns | Yes | NubeRush Upgrade | Admin Panel compliance analytics | Compliance oversight | Yes | No | Dr.1.6 | — |
| Admin sees support escalations | Yes | NubeRush Upgrade | Admin Panel support oversight | Support oversight | Yes | No | Dr.1.4 | — |

## 6. Key Keep Decisions

Features that should mostly carry over into NubeRush with minimal change,
because the operational pattern is the same regardless of cargo:

- **Login / profile** — backend-authenticated driver identity.
- **Onboarding checklist** — guided activation, with NubeRush document/training
  gates layered on.
- **Document management** — upload, expiry, rejection, resubmission.
- **Online / offline** — availability state machine.
- **Offers** — time-boxed offers tied to existing backend orders.
- **Navigation** — external nav handoff to Apple Maps / Google Maps / Waze.
- **Support** — help center and structured support topics.
- **Notifications** — operational push for offers, assignments, and status.
- **Performance basics** — completed/failed counts and core operational rates.

## 7. Key Adapt Decisions

Features that apply but must be transformed for NubeRush's model:

- **Passenger pickup becomes store pickup** — the driver collects an order at a
  store, with a store handoff instead of a rider entering a vehicle.
- **Passenger dropoff becomes restricted-product customer handoff** — an
  in-person, verified handoff rather than dropping a passenger at a location.
- **Alcohol-style ID verification becomes smoke-shop / vape 21+ verification** —
  the same age-gate pattern, applied to NubeRush's restricted products.
- **"Restaurant not ready" becomes "store order not ready"** — the pickup-wait
  pattern adapted to smoke-shop stores.
- **Airport geofence becomes store / dropoff / legal-zone geofencing** — geofence
  mechanics repurposed for store arrival, dropoff arrival, and legal delivery
  zones.
- **Uber Pro becomes NubeRush Driver Performance / Compliance Status** — a status
  model driven by compliance and delivery quality, not rideshare tiers.
- **Safety Toolkit becomes Driver Delivery Safety Toolkit** — safety features
  framed around solo field delivery rather than in-car passengers.

## 8. Key Defer Decisions

Features that are useful later but are intentionally not MVP:

- **Promotions** — busy zones, bonus windows, scheduled shifts.
- **Rewards** — driver status tiers and badges.
- **Customer / store ratings** — reputation surfaces.
- **Cashout** — payout actions.
- **Tax summary** — tax documentation.
- **ID scan / OCR / vendor verification** — automated verification (legal /
  compliance gated).
- **CarPlay / Android Auto** — in-car integrations.
- **Internal turn-by-turn** — in-app navigation engine.
- **Batch delivery** — multi-order batching.
- **Route optimization** — automated routing.

These are preserved in the architecture so later phases can implement them
without re-deriving the design; they are not built in the MVP.

## 9. Key No Decisions

Features that do not apply to NubeRush and are explicitly rejected, with the
reason documented:

- **Rideshare tiers** (UberX / Comfort / XL / Black / Pet) — NubeRush has no ride
  classes; it is a delivery platform.
- **Passenger rides** (pickup / dropoff / destination changes) — NubeRush
  transports products, not people.
- **Airport queues / staging** — no airport passenger operations.
- **Multi-rider trips** — no shared passenger rides.
- **Passenger no-show** — replaced by failed-delivery / return handling.
- **Lost passenger items** — no in-vehicle passenger belongings.
- **Ride fares** — no fare meter; delivery economics are separate.
- **Passenger ratings** — no rider-of-driver reputation model.

## 10. NubeRush-Specific Upgrade Decisions

Features where NubeRush must go beyond Uber-style generic delivery because of
the regulated-product model:

- **Restricted-product compliance** — restricted handling is first-class, not an
  add-on.
- **21+ manual verification (MVP)** — mandatory manual age verification on
  restricted deliveries.
- **No unattended delivery for restricted products** — leave-at-door is
  forbidden for restricted orders.
- **Failed verification blocks delivery** — a failed 21+ check stops completion.
- **Return-to-store required** — restricted failures route to an accountable
  return.
- **Store handoff PIN** — store-side release and return accountability.
- **Audit timeline** — a compliance-grade event timeline for every delivery.
- **Backend-authorized completion** — completion requires backend validation of
  proof and verification.
- **No raw ID image storage** — sensitive identity images are not captured or
  stored in the MVP.
- **Order-scoped driver access** — drivers see only their assigned orders, never
  store-wide data.

## 11. Backend Authority Notes

This matrix classifies features; it does **not** authorize mobile-owned business
logic.

- The matrix does not move any business rule into the mobile app.
- Mobile can **submit actions** (accept, picked up, out for delivery, verified,
  delivered, failed, returned) and **display state**.
- The backend must **decide** eligibility, assignment, order state, compliance,
  proof, completion, failed delivery, return flow, inventory implications, and
  audit.
- Any feature requiring sensitive business logic — verification outcome,
  completion authorization, return closure, inventory effects, compliance
  enforcement — must be backend-controlled. A "Mobile? Yes" cell means the app
  presents or initiates the action, not that it owns the decision.

This is consistent with the Backend Authority Rule in
`docs/dr.1.0-driver-app-contract-lock.md`.

## 12. MVP vs Future Notes

- Dr.1.0.B does **not** decide the final MVP scope by itself. It classifies the
  feature universe; it does not lock the build order.
- The phase-target column is an architectural expectation, not a commitment.
  Later Dr.1.0 documents (screen inventory, user flows, backend gap map) and the
  Dr.1.1+ implementation phases decide the actual implementation order.
- Features marked **Defer** or **Future** are intentionally preserved in the
  architecture without being implemented now, so later phases inherit a designed
  slot rather than a gap.

## 13. No-Go Reminder

This document is documentation only. It does **not** implement:

- backend endpoints
- migrations
- schemas
- frontend changes
- mobile app code
- a Flutter project
- a Capacitor project
- dependency changes
- Stripe
- checkout
- driver payouts
- real ID scan
- raw ID storage
- production launch

Any work that would cross one of these boundaries requires a separate,
explicitly approved future phase with its own contract, consistent with
`docs/dr.1.0-driver-app-contract-lock.md` and `docs/f2.27-contract-lock.md`.
