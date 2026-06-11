# Dr.1.0 Driver Earnings, Performance, and Rewards Future Architecture

## 1. Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.J — Earnings, Performance, Rewards Future Architecture
- **Deliverable path:** `docs/dr.1.0-driver-earnings-performance-rewards.md`
- **Status:** Draft / Architecture
- **Scope:** Research/docs only
- **Implementation:** none — this document introduces no backend, frontend, or
  mobile implementation of any kind. It defines no endpoints, no database
  tables, no migrations, no schemas, no services, no payouts, no Stripe, no
  cashout, no payment movement, no earnings calculation in code, no rewards, no
  driver ranking, no performance enforcement, no tax documents, and no
  payroll/accounting integration.

This document is subordinate to `docs/dr.1.0-driver-app-contract-lock.md` and
consistent with `docs/dr.1.0-driver-feature-adaptation-matrix.md`,
`docs/dr.1.0-driver-domain-architecture.md`,
`docs/dr.1.0-driver-screen-inventory.md`,
`docs/dr.1.0-driver-user-flows.md`,
`docs/dr.1.0-driver-backend-gap-map.md`,
`docs/dr.1.0-driver-compliance-id-verification.md` (Dr.1.0.G),
`docs/dr.1.0-driver-proof-failure-return.md` (Dr.1.0.H),
`docs/dr.1.0-driver-live-map-navigation-surface.md` (Dr.1.0.H2),
`docs/dr.1.0-driver-ops-support-safety.md` (Dr.1.0.I),
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them. Metric
names, tier names, and event names are **architectural candidates**, finalized
in later Dr.1.x phases. Nothing here is implemented, and no payment movement is
introduced.

## 2. Purpose

This document defines how the NubeRush Driver App should present earnings
visibility, performance metrics, and future reward/status tiers. In Dr.1.0 this
is architecture-only and visibility-only: the app may display backend-authorized
information, but it never calculates payable amounts, moves money, or enforces
performance discipline.

Earnings/performance/rewards architecture matters for NubeRush because of:

- **Driver transparency** — drivers should understand their completed work and
  what they can expect to be shown.
- **Motivation** — clear, fair visibility supports driver engagement.
- **Operational quality** — performance visibility supports a reliable delivery
  operation.
- **Compliance-sensitive delivery behavior** — metrics must reinforce lawful,
  careful handling of regulated products.
- **Restricted-product accountability** — quality must reflect compliance, not
  speed alone.
- **Future driver trust system** — reward/status tiers are a future trust
  signal, gated behind legal/product review.
- **Future admin intelligence** — performance and compliance metrics feed future
  oversight analytics.
- **Uber Driver inspired visibility** — the earnings/performance visibility depth
  of a mature driver platform is studied (not copied) per the contract lock and
  adapted to NubeRush's regulated model.
- **Why this is visibility-only in Dr.1.0** — payouts, payment movement, and
  legal employment/payroll questions require a separate, later
  legal/product/accounting phase; Dr.1.0 deliberately scopes to architecture and
  display only.

## 3. Core Principles

- **The backend is the authority for earnings/performance data.** All values
  originate from backend-authorized state.
- **Mobile displays only backend-authorized values.** The app never computes
  payable amounts or metrics locally.
- **The MVP is earnings visibility only, not payouts.** No money moves.
- **No cashout.** There is no cashout in Dr.1.0.
- **No Stripe.** No Stripe or Stripe Connect is introduced.
- **No payment movement.** No settlement, transfer, or ledger movement.
- **No driver payroll assumptions.** Nothing here implies employment or payroll
  classification.
- **No tax document generation.** No tax forms or filings.
- **No automatic discipline from performance metrics.** Metrics never auto-punish
  a driver.
- **Performance metrics must be explainable.** Drivers should be able to
  understand what a metric means.
- **Compliance metrics must not reward unsafe shortcuts.** Metrics never incent
  bypassing compliance or safety.
- **Restricted delivery quality matters more than speed alone.** Quality is
  compliance-weighted, not speed-weighted.
- **Rewards/status tiers are future-only.** No tier is implemented or assigned in
  Dr.1.0.
- **Store/Admin visibility must be privacy-safe.** Oversight reads privacy-safe,
  role-limited data via backend events.
- **An audit trail is required for earnings/performance display events where
  relevant.** Display and support/dispute actions emit privacy-safe audit events.

## 4. Relationship to Prior Dr.1.0 Documents

This document builds on the prior Dr.1.0 subphases and does not restate or
replace them.

- **Dr.1.0.A — Contract lock** (`docs/dr.1.0-driver-app-contract-lock.md`):
  defines scope and the docs-only nature of Dr.1.0. This subphase stays inside
  that boundary and adds the explicit no-payment-movement boundary.
- **Dr.1.0.B — Uber feature adaptation**
  (`docs/dr.1.0-driver-feature-adaptation-matrix.md`): earnings/performance
  visibility adapts the studied structure to NubeRush.
- **Dr.1.0.C — Domain architecture**
  (`docs/dr.1.0-driver-domain-architecture.md`): earnings and performance are
  read-model views onto the backend-owned delivery domain.
- **Dr.1.0.D — Screen inventory**
  (`docs/dr.1.0-driver-screen-inventory.md`): earnings, history, and performance
  surfaces map to the screen inventory.
- **Dr.1.0.E — User flows** (`docs/dr.1.0-driver-user-flows.md`): visibility
  supports the existing flows without changing them.
- **Dr.1.0.F — Backend gap map**
  (`docs/dr.1.0-driver-backend-gap-map.md`): the future backend capability map in
  Section 23 extends the gap map for earnings/performance read models.
- **Dr.1.0.G — Compliance / ID verification**
  (`docs/dr.1.0-driver-compliance-id-verification.md`): completion counting and
  compliance metrics depend on the verification gate.
- **Dr.1.0.H — Proof / failed delivery / return-to-store**
  (`docs/dr.1.0-driver-proof-failure-return.md`): completion, failure, and return
  state determine what is counted and shown.
- **Dr.1.0.H2 — Live map / navigation surface**
  (`docs/dr.1.0-driver-live-map-navigation-surface.md`): route/distance summaries
  are future candidates derived from backend state, not local computation.
- **Dr.1.0.I — Safety/support/communication/notifications**
  (`docs/dr.1.0-driver-ops-support-safety.md`): safety incidents and support
  cases inform metrics but never auto-punish drivers.

How this subphase relates:

- **Earnings visibility depends on the completed delivery lifecycle.** Only
  backend-authorized completions feed earnings/history visibility.
- **Compliance failures and return-to-store flows affect delivery status, not
  local earnings logic.** Status comes from Dr.1.0.G/H; the app does not recompute
  earnings from it.
- **Safety incidents must not automatically punish drivers.** Dr.1.0.I safety
  events never trigger automatic discipline.
- **Performance metrics must consider restricted-product compliance.** Quality is
  compliance-weighted (Section 13).
- **Rewards cannot encourage illegal/unattended delivery.** No tier or metric
  rewards bypassing the no-unattended-restricted rule.
- **No payment movement is introduced.** This subphase moves no money.

## 5. MVP Earnings Visibility Surface

The MVP earnings visibility surface is display-only. Each item below states
Purpose, MVP/Future/No-Go classification, Backend dependency, Mobile
responsibility, Payment/legal notes, and Store/Admin visibility. Items are
architectural candidates.

### 5.1 Estimated earnings per delivery

- **Purpose:** show a backend-provided estimate for a delivery.
- **MVP/Future/No-Go:** MVP candidate (display only).
- **Backend dependency:** estimate provider (Section 6).
- **Mobile responsibility:** display the estimate; never compute it.
- **Payment/legal notes:** estimate, not a guaranteed payout.
- **Store/Admin visibility:** none (driver-facing).

### 5.2 Completed delivery count

- **Purpose:** show the count of backend-authorized completions.
- **MVP/Future/No-Go:** MVP candidate.
- **Backend dependency:** completion state (Dr.1.0.G/H).
- **Mobile responsibility:** display the count.
- **Payment/legal notes:** count is operational, not payment.
- **Store/Admin visibility:** Admin aggregate.

### 5.3 Delivery history

- **Purpose:** show a list of past deliveries with status and estimate line.
- **MVP/Future/No-Go:** MVP candidate.
- **Backend dependency:** delivery history projection (Section 8).
- **Mobile responsibility:** display redacted history.
- **Payment/legal notes:** no settlement detail.
- **Store/Admin visibility:** Admin history.

### 5.4 Earnings summary placeholder

- **Purpose:** present a placeholder summary surface.
- **MVP/Future/No-Go:** MVP placeholder.
- **Backend dependency:** earnings snapshot (Section 9).
- **Mobile responsibility:** display placeholder with disclaimer copy.
- **Payment/legal notes:** no payout state.
- **Store/Admin visibility:** none.

### 5.5 Current week placeholder

- **Purpose:** present a weekly summary placeholder.
- **MVP/Future/No-Go:** MVP placeholder.
- **Backend dependency:** earnings snapshot.
- **Mobile responsibility:** display placeholder.
- **Payment/legal notes:** no payout.
- **Store/Admin visibility:** none.

### 5.6 Today placeholder

- **Purpose:** present a daily summary placeholder.
- **MVP/Future/No-Go:** MVP placeholder.
- **Backend dependency:** earnings snapshot.
- **Mobile responsibility:** display placeholder.
- **Payment/legal notes:** no payout.
- **Store/Admin visibility:** none.

### 5.7 Delivery detail earnings line placeholder

- **Purpose:** show an estimate line on a delivery detail.
- **MVP/Future/No-Go:** MVP placeholder.
- **Backend dependency:** estimate/snapshot.
- **Mobile responsibility:** display the estimate line.
- **Payment/legal notes:** estimate only.
- **Store/Admin visibility:** none.

### 5.8 Excluded from the MVP surface (No-Go)

- **No cashout button.** No cashout exists.
- **No payout initiation.** The app cannot initiate a payout.
- **No bank account management.** No bank data is collected.
- **No tax forms.** No tax documents.
- **No Stripe account connection.** No Stripe/Stripe Connect.
- **No wallet balance.** No wallet.
- **No real-time payment settlement.** No settlement.

## 6. Estimated Earnings Per Delivery

- **Estimate shown before or during assignment as a future/MVP candidate.** A
  backend-provided estimate may be shown at assignment time.
- **The estimate must be backend-provided.** The app never computes it.
- **The estimate is not a guaranteed payout unless backend/payment policy later
  defines it.** It is an estimate, framed cautiously.
- **The estimate may depend on distance/time/base fee/incentive as future
  policy.** Inputs are a future backend policy concern, not local logic.
- **The estimate cannot be calculated locally by mobile.** No local computation.
- **No payment movement.** Showing an estimate moves no money.
- **No cashout.** No cashout is implied.
- **No Stripe.** No Stripe involvement.
- **No legal payroll assumption.** No employment/payroll implication.
- **Stale estimate handling.** A stale estimate is marked and refreshed from the
  backend (Section 20).
- **Dispute/support future path.** An earnings dispute/support path is a future
  candidate (Section 9, Dr.1.0.I).
- **Audit/visibility considerations.** Viewing an estimate emits a privacy-safe
  audit event (`delivery_earnings_estimate_viewed`).

## 7. Completed Delivery Count

- **Completed deliveries count.** Shows backend-authorized completions.
- **Backend-authorized completion only.** Only completions the backend accepts
  are counted.
- **Restricted delivery requires verification/proof before counting.** A
  restricted completion counts only after the Dr.1.0.G/H gates pass.
- **Failed delivery should not count as completed unless future policy says
  otherwise.** Failures are not completions by default.
- **Returned-to-store deliveries tracked separately.** Returns are a distinct
  category, not completions.
- **Safety cancellations tracked separately.** Safety cancellations are distinct
  and never auto-penalize (Dr.1.0.I).
- **Count resets/periods as future/backend-configurable.** Period boundaries are
  a future backend concern.
- **Mobile display only.** The app displays the count; it never derives it.
- **Admin visibility.** Admin sees aggregate counts, privacy-safe.
- **Audit implications.** Viewing the count is a candidate display audit event.

## 8. Delivery History Architecture

Delivery history is a redacted, backend-provided projection. The following are
**candidate history item types**, finalized in a later Dr.1.x phase.

### Completed deliveries

- **Meaning:** a backend-authorized completed delivery.
- **Data shown to driver:** status label, timestamp, store reference, estimate
  line, route/distance summary (future candidate).
- **Data hidden from driver:** raw ID data, raw location replay, settlement
  detail.
- **Backend dependency:** completion state (Dr.1.0.G/H).
- **Store/Admin visibility:** Admin history; Store limited.
- **Privacy/compliance notes:** redacted; no sensitive ID data.

### Failed deliveries

- **Meaning:** a backend-recorded failed delivery (Dr.1.0.H).
- **Data shown to driver:** status label, reason category, timestamp, store
  reference.
- **Data hidden from driver:** raw ID data, raw location replay, sensitive
  customer data.
- **Backend dependency:** failure state.
- **Store/Admin visibility:** Store and Admin.
- **Privacy/compliance notes:** reason category only, no sensitive detail.

### Returned-to-store deliveries

- **Meaning:** an order returned to the store (Dr.1.0.H).
- **Data shown to driver:** status label, return reason category, timestamp,
  store reference.
- **Data hidden from driver:** raw ID data, raw location replay.
- **Backend dependency:** return state.
- **Store/Admin visibility:** Store and Admin.
- **Privacy/compliance notes:** protects restricted inventory accountability.

### Canceled / support-reviewed deliveries

- **Meaning:** a canceled or support-reviewed delivery (Dr.1.0.I).
- **Data shown to driver:** status label, timestamp, support reference.
- **Data hidden from driver:** sensitive case content, sensitive ID data.
- **Backend dependency:** support/cancel state.
- **Store/Admin visibility:** Admin; Store if order-impacting.
- **Privacy/compliance notes:** no case content exposed.

### Safety escalations

- **Meaning:** a safety escalation linked to a delivery (Dr.1.0.I).
- **Data shown to driver:** status label, timestamp.
- **Data hidden from driver:** sensitive safety detail, call content.
- **Backend dependency:** safety state.
- **Store/Admin visibility:** Admin (priority); limited Store.
- **Privacy/compliance notes:** never auto-penalizes the driver.

### Compliance-failed deliveries

- **Meaning:** a delivery that failed a compliance gate (Dr.1.0.G).
- **Data shown to driver:** status label, compliance reason category, timestamp.
- **Data hidden from driver:** raw ID data, ID images, full ID numbers.
- **Backend dependency:** compliance state.
- **Store/Admin visibility:** Admin; no sensitive ID data.
- **Privacy/compliance notes:** redacted compliance status only.

Cross-cutting history fields:

- **Proof/verification references as redacted status only.** References are
  status-level, never raw evidence.
- **Estimated earnings line.** A cautious estimate line, not a settlement.
- **Status labels.** Clear, non-punitive status labels.
- **Timestamps.** Operational timestamps.
- **Store reference.** Store identity reference.
- **Route/distance summary as a future candidate.** Derived from backend state.
- **No raw ID data.** Never shown.
- **No raw location replay.** Never shown.
- **No payment settlement detail in the MVP.** Not shown.

## 9. Earnings Summary Placeholder

- **Daily summary placeholder.** A placeholder for daily totals.
- **Weekly summary placeholder.** A placeholder for weekly totals.
- **Completed deliveries count.** Shown from backend state.
- **Estimated earnings total.** A cautious estimated total, not a payout.
- **Pending review amount as a future candidate.** Reserved, future.
- **Adjustments as a future candidate.** Reserved, future.
- **Bonuses as a future candidate.** Reserved, future.
- **No payout state.** No payout is represented.
- **No cashout.** No cashout action.
- **No Stripe.** No Stripe involvement.
- **No tax/payroll language.** No tax or payroll wording.
- **Disclaimer/copy requirements.** The surface must clearly state that values
  are estimates and that no payout/cashout exists in this phase.
- **Support/dispute future path.** A future support/dispute path is reserved
  (Dr.1.0.I linkage).

## 10. No Payout / No Cashout / No Stripe Boundary

This subphase introduces no money movement of any kind.

- **Dr.1.0 does not move money.** No transfers, settlements, or ledger movement.
- **No driver cashout.** There is no cashout.
- **No wallet.** There is no wallet or balance.
- **No Stripe Connect.** No Stripe Connect onboarding or accounts.
- **No bank account collection.** No bank data is collected.
- **No instant pay.** No instant-pay capability.
- **No payment ledger implementation.** No ledger is built.
- **No payroll/tax implementation.** No payroll or tax handling.
- **No direct deposit.** No deposit capability.
- **No payment processor integration.** No processor is integrated.
- **No customer payment dependency.** Earnings visibility does not depend on
  customer payment behavior.
- **No payout promise.** Nothing here promises a payout.
- **No legal employment classification decision.** No employment/contractor
  determination is made.
- **Future payout work requires a separate legal/product/accounting phase.** Any
  payout capability is deferred to a dedicated future phase with legal review.

## 11. Performance Metrics Architecture

The following are **candidate performance metrics**, finalized in a later Dr.1.x
phase. Metrics are backend-computed, explainable, and never auto-punitive.

### completed deliveries

- **Definition:** count of backend-authorized completions.
- **MVP/Future:** MVP candidate.
- **Backend dependency:** completion state.
- **Mobile display responsibility:** display only.
- **Risk/abuse concern:** low; must not incent compliance bypass.
- **Admin visibility:** aggregate.
- **Notes:** compliance gates apply (Dr.1.0.G/H).

### acceptance rate

- **Definition:** share of offered deliveries accepted.
- **MVP/Future:** future candidate.
- **Backend dependency:** assignment state.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** must not pressure unsafe acceptance.
- **Admin visibility:** aggregate (future).
- **Notes:** explainable; no auto-discipline.

### cancellation rate

- **Definition:** share of accepted deliveries canceled.
- **MVP/Future:** future candidate.
- **Backend dependency:** cancel state.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** safety cancellations must not count against drivers.
- **Admin visibility:** aggregate (future).
- **Notes:** safety-aware exclusions required.

### on-time pickup

- **Definition:** share of pickups within a target window.
- **MVP/Future:** future candidate.
- **Backend dependency:** route/pickup timestamps.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** must not pressure unsafe driving.
- **Admin visibility:** aggregate (future).
- **Notes:** estimate-based; cautious.

### on-time delivery

- **Definition:** share of deliveries within a target window.
- **MVP/Future:** future candidate.
- **Backend dependency:** route/delivery timestamps.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** must not pressure unsafe driving or compliance bypass.
- **Admin visibility:** aggregate (future).
- **Notes:** speed never overrides compliance.

### return-to-store completion rate

- **Definition:** share of required returns completed (Dr.1.0.H).
- **MVP/Future:** MVP/early candidate.
- **Backend dependency:** return state.
- **Mobile display responsibility:** display only.
- **Risk/abuse concern:** must reward accountable returns, not discourage them.
- **Admin visibility:** aggregate.
- **Notes:** protects restricted inventory accountability.

### proof completion quality

- **Definition:** quality of proof completion (Dr.1.0.H).
- **MVP/Future:** MVP/early candidate.
- **Backend dependency:** proof state.
- **Mobile display responsibility:** display only.
- **Risk/abuse concern:** must not incent shortcut proof.
- **Admin visibility:** aggregate.
- **Notes:** redacted; no raw evidence.

### ID verification compliance rate

- **Definition:** correct handling of the Dr.1.0.G verification gate.
- **MVP/Future:** MVP/early candidate.
- **Backend dependency:** verification state.
- **Mobile display responsibility:** display only.
- **Risk/abuse concern:** must never incent bypass.
- **Admin visibility:** aggregate; no sensitive ID data.
- **Notes:** compliance-weighted quality.

### support escalation rate

- **Definition:** rate of support escalations (Dr.1.0.I).
- **MVP/Future:** future candidate.
- **Backend dependency:** support state.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** must not discourage legitimate escalation.
- **Admin visibility:** aggregate (future).
- **Notes:** legitimate escalation is positive, not punitive.

### safety incident rate

- **Definition:** rate of safety incidents (Dr.1.0.I).
- **MVP/Future:** future candidate.
- **Backend dependency:** safety state.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** must never auto-punish the driver.
- **Admin visibility:** aggregate (future); privacy-safe.
- **Notes:** review-based, not automatic.

### customer issue rate

- **Definition:** rate of customer-related issues.
- **MVP/Future:** future candidate.
- **Backend dependency:** support/issue state.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** must not penalize for customer fault.
- **Admin visibility:** aggregate (future).
- **Notes:** context required.

### store issue rate

- **Definition:** rate of store-related issues.
- **MVP/Future:** future candidate.
- **Backend dependency:** support/issue state.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** must not penalize for store fault.
- **Admin visibility:** aggregate (future).
- **Notes:** context required.

### app/network issue rate

- **Definition:** rate of app/connectivity issues affecting delivery.
- **MVP/Future:** future candidate.
- **Backend dependency:** technical/support state.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** must not penalize for platform fault.
- **Admin visibility:** aggregate (future).
- **Notes:** technical context required.

### delivery reliability score

- **Definition:** a composite reliability indicator.
- **MVP/Future:** future candidate.
- **Backend dependency:** multiple metrics.
- **Mobile display responsibility:** display only (future).
- **Risk/abuse concern:** must be explainable and compliance-weighted.
- **Admin visibility:** aggregate (future).
- **Notes:** no opaque scoring; no auto-discipline.

## 12. Compliance Metrics Architecture

The following are **candidate compliance metrics**, finalized in a later Dr.1.x
phase. They are redacted, never expose sensitive ID data, and never reward
shortcuts.

### ID verification completed

- **Definition:** verification completed correctly (Dr.1.0.G).
- **Why it matters:** evidences lawful restricted handoff.
- **Backend source:** verification state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate; no sensitive ID data.
- **Risk if misused:** could pressure speed; must not.
- **Notes:** quality, not speed.

### ID verification failed

- **Definition:** verification failed (Dr.1.0.G).
- **Why it matters:** failures are lawful blocks, not driver faults.
- **Backend source:** verification state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate; no sensitive ID data.
- **Risk if misused:** must not penalize lawful blocks.
- **Notes:** failure is correct behavior when warranted.

### verification abandoned

- **Definition:** verification started but not completed.
- **Why it matters:** signals process friction or issues.
- **Backend source:** verification state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate.
- **Risk if misused:** context required.
- **Notes:** may indicate tooling friction.

### wrong-recipient prevented

- **Definition:** delivery to the wrong recipient was prevented.
- **Why it matters:** evidences careful handoff.
- **Backend source:** verification/handoff state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate.
- **Risk if misused:** none if framed as positive.
- **Notes:** positive compliance signal.

### under-21 blocked

- **Definition:** an under-21 handoff was blocked (Dr.1.0.G).
- **Why it matters:** core legal requirement for restricted products.
- **Backend source:** verification state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate; no sensitive ID data.
- **Risk if misused:** must never be penalized.
- **Notes:** lawful block is correct behavior.

### expired/missing ID blocked

- **Definition:** an expired/missing ID handoff was blocked.
- **Why it matters:** lawful blocking requirement.
- **Backend source:** verification state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate.
- **Risk if misused:** must never be penalized.
- **Notes:** lawful block is correct behavior.

### restricted product not left unattended

- **Definition:** restricted product was not left unattended (Dr.1.0.H).
- **Why it matters:** core no-unattended rule.
- **Backend source:** proof/completion state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate.
- **Risk if misused:** none if framed as positive.
- **Notes:** positive compliance signal.

### return-to-store completed after failed verification

- **Definition:** a return was completed after a failed verification (Dr.1.0.H).
- **Why it matters:** evidences accountable handling.
- **Backend source:** return state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate.
- **Risk if misused:** must reward, not discourage, returns.
- **Notes:** positive accountability signal.

### suspected fake ID escalated

- **Definition:** a suspected fake ID was escalated (Dr.1.0.G/I).
- **Why it matters:** evidences proper escalation.
- **Backend source:** verification/support state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate; no sensitive ID data.
- **Risk if misused:** must not discourage escalation.
- **Notes:** escalation is correct behavior.

### compliance notification acknowledged

- **Definition:** a compliance notification was acknowledged (Dr.1.0.I).
- **Why it matters:** evidences awareness of compliance steps.
- **Backend source:** notification state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate.
- **Risk if misused:** low.
- **Notes:** acknowledgement is operational.

### proof blocked after failed verification

- **Definition:** proof was blocked due to failed verification (Dr.1.0.G/H).
- **Why it matters:** evidences correct gate ordering.
- **Backend source:** proof/verification state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate.
- **Risk if misused:** must not penalize correct blocking.
- **Notes:** correct behavior.

### compliance support escalations

- **Definition:** compliance-related support escalations (Dr.1.0.I).
- **Why it matters:** evidences proper use of support.
- **Backend source:** support state.
- **Mobile display candidate:** redacted count (future).
- **Admin visibility:** aggregate.
- **Risk if misused:** must not discourage legitimate escalation.
- **Notes:** legitimate escalation is positive.

## 13. Restricted Delivery Quality Model

Quality for NubeRush drivers is not speed-only. The quality model is
compliance-weighted and safety-aware.

- **Safe completion.** Deliveries completed safely for the driver and others.
- **Legal/restricted-product compliance.** Lawful handling of regulated products.
- **Successful store pickup.** Correct, confirmed pickup (Dr.1.0.H).
- **Correct customer handoff.** Handoff to the verified, correct recipient
  (Dr.1.0.G).
- **Valid verification/proof sequence.** Verification before proof, per
  Dr.1.0.G/H.
- **No unattended restricted products.** The no-unattended rule is upheld.
- **Proper failed delivery reporting.** Failures reported per Dr.1.0.H.
- **Proper return-to-store completion.** Returns completed and store-confirmed.
- **Safety escalation when needed.** Escalating safety is positive (Dr.1.0.I).
- **Communication professionalism.** Professional, privacy-safe communication.
- **No metric should reward bypassing compliance.** No quality measure incents
  shortcuts around compliance or safety.

## 14. Rewards / Status Tiers Future Architecture

Reward/status tiers are **future-only**. No tier is implemented, calculated, or
assigned in Dr.1.0. The following are candidate tiers.

### New Driver

- **Purpose:** entry status for a new driver.
- **Candidate eligibility signals:** recently onboarded.
- **Benefits (future candidate):** onboarding guidance.
- **Risks:** none significant.
- **Backend dependency:** driver state.
- **Mobile display:** future label.
- **Admin visibility:** aggregate (future).
- **No-Go boundaries:** no assignment privilege; no payment effect.

### Active Driver

- **Purpose:** status for an actively delivering driver.
- **Candidate eligibility signals:** recent active deliveries.
- **Benefits (future candidate):** standard visibility.
- **Risks:** none significant.
- **Backend dependency:** delivery state.
- **Mobile display:** future label.
- **Admin visibility:** aggregate (future).
- **No-Go boundaries:** no automatic privilege; no payment effect.

### Reliable Driver

- **Purpose:** status reflecting reliability.
- **Candidate eligibility signals:** reliability indicators (Section 11).
- **Benefits (future candidate):** recognition.
- **Risks:** must be explainable and fair.
- **Backend dependency:** performance metrics.
- **Mobile display:** future label.
- **Admin visibility:** aggregate (future).
- **No-Go boundaries:** no auto-discipline; no payment effect.

### Compliance Trusted

- **Purpose:** status reflecting compliance-safe behavior (Section 15).
- **Candidate eligibility signals:** compliance metrics (Section 12).
- **Benefits (future candidate):** recognition; no privilege in MVP.
- **Risks:** must not be a legal certification claim.
- **Backend dependency:** compliance metrics; admin review.
- **Mobile display:** future label with careful copy.
- **Admin visibility:** aggregate (future).
- **No-Go boundaries:** no compliance override; no legal claim without review.

### Restricted Delivery Certified

- **Purpose:** status reflecting restricted-delivery education (Section 16).
- **Candidate eligibility signals:** future training/legal approval.
- **Benefits (future candidate):** recognition; no privilege in MVP.
- **Risks:** must not be a real certification claim without legal review.
- **Backend dependency:** training/compliance; admin review.
- **Mobile display:** future label with careful copy.
- **Admin visibility:** aggregate (future).
- **No-Go boundaries:** no age/ID bypass; no compliance override.

### Store Preferred Driver (future candidate)

- **Purpose:** status reflecting store preference.
- **Candidate eligibility signals:** store-level reliability (future).
- **Benefits (future candidate):** recognition.
- **Risks:** must avoid unfair exclusion.
- **Backend dependency:** store/performance signals.
- **Mobile display:** future label.
- **Admin visibility:** aggregate (future).
- **No-Go boundaries:** no automatic assignment privilege in MVP.

### Safety Aware Driver (future candidate)

- **Purpose:** status reflecting safety awareness.
- **Candidate eligibility signals:** safety-positive behavior (Dr.1.0.I).
- **Benefits (future candidate):** recognition.
- **Risks:** must not discourage legitimate escalation.
- **Backend dependency:** safety/support signals.
- **Mobile display:** future label.
- **Admin visibility:** aggregate (future).
- **No-Go boundaries:** no auto-discipline; no payment effect.

### High Reliability Driver (future candidate)

- **Purpose:** status reflecting high reliability.
- **Candidate eligibility signals:** reliability indicators.
- **Benefits (future candidate):** recognition.
- **Risks:** must be explainable and fair.
- **Backend dependency:** performance metrics.
- **Mobile display:** future label.
- **Admin visibility:** aggregate (future).
- **No-Go boundaries:** no auto-discipline; no payment effect.

## 15. Compliance Trusted Tier

- **Future-only.** Not implemented or assigned in Dr.1.0.
- **Based on compliance-safe behavior.** Derived from compliance metrics
  (Section 12), not speed.
- **Proper ID verification handling.** Correct use of the Dr.1.0.G gate.
- **No unattended restricted delivery.** Upholds the no-unattended rule.
- **Correct return-to-store behavior.** Accountable returns (Dr.1.0.H).
- **Safety/support escalation when needed.** Positive escalation behavior
  (Dr.1.0.I).
- **Not based on speed alone.** Speed is not a qualifying signal.
- **No automatic assignment privilege in the MVP.** The tier grants no automatic
  privilege.
- **No legal certification claim unless legally reviewed.** The label is not a
  legal certification.
- **Backend/admin review requirement.** Assignment requires backend/admin review.
- **Driver-facing copy requirements.** Copy must be careful, non-legalistic, and
  explainable.

## 16. Restricted Delivery Certified Tier

- **Future-only.** Not implemented or assigned in Dr.1.0.
- **May require training/legal approval.** Likely gated behind training and legal
  review.
- **Restricted-product delivery education.** Education on regulated handling.
- **Age/ID verification education.** Education on the Dr.1.0.G gate.
- **Return-to-store procedure education.** Education on Dr.1.0.H returns.
- **Support/safety education.** Education on Dr.1.0.I support/safety.
- **Passing criteria as a future candidate.** Criteria are future and reviewed.
- **No real certification claim without legal review.** The label is not a legal
  certification absent review.
- **No automatic compliance override.** The tier never overrides compliance.
- **No bypass of age/ID verification.** Verification always applies.
- **Backend/admin authority.** Assignment is backend/admin authorized.
- **Mobile display requirements.** Careful, explainable display copy.

## 17. Driver Performance Detail Surface

The following describes a future driver-facing performance screen. No screen is
implemented in Dr.1.0.

- **Summary cards.** High-level summary cards.
- **Delivery count.** Completed delivery count.
- **Reliability indicators.** Explainable reliability indicators (future).
- **Compliance indicators.** Redacted compliance indicators (Section 12).
- **Return completion.** Return-to-store completion visibility (Dr.1.0.H).
- **Safety/support history summary.** Privacy-safe summary (Dr.1.0.I).
- **Communication professionalism (future candidate).** A future indicator.
- **Earnings visibility placeholder.** A placeholder, not a payout.
- **Explanations/tooltips.** Each metric is explainable.
- **No punitive language in the MVP.** Copy is non-punitive.
- **Dispute/support path.** A future dispute/support path (Dr.1.0.I linkage).
- **Privacy boundaries.** No sensitive ID data, no raw location replay.

## 18. Store/Admin Visibility

Visibility comes from backend-authorized events and is privacy-safe and
role-limited.

### Store visibility

- limited driver status for active delivery only
- pickup/return reliability as a future aggregate candidate
- no full earnings visibility
- no private safety details unless store-impacting
- no sensitive compliance/ID data
- no raw location replay

### Admin visibility

- driver delivery history
- compliance metrics
- return-to-store metrics
- support/safety linkage
- performance trend candidates
- earnings visibility / support context
- dispute review context
- no unrestricted payroll/payment data in Dr.1.0
- no sensitive ID data
- privacy-safe audit detail

## 19. Audit Events

Audit events are backend-owned and privacy-safe. Names are candidates,
finalized in a later Dr.1.x phase. "Forbidden metadata" never appears in an
event.

### earnings_summary_viewed

- **Trigger:** driver views the earnings summary.
- **Actor:** driver.
- **Required metadata:** period reference, snapshot reference.
- **Forbidden metadata:** bank/tax data, payment account data, raw ID data.
- **Store/Admin visibility:** none (driver-facing).
- **Privacy/compliance:** display record only.

### delivery_earnings_estimate_viewed

- **Trigger:** driver views a delivery earnings estimate.
- **Actor:** driver.
- **Required metadata:** delivery reference, estimate snapshot reference.
- **Forbidden metadata:** payment account data, settlement detail.
- **Store/Admin visibility:** none.
- **Privacy/compliance:** display record only.

### delivery_history_viewed

- **Trigger:** driver views delivery history.
- **Actor:** driver.
- **Required metadata:** period/page reference.
- **Forbidden metadata:** raw ID data, raw location replay, settlement detail.
- **Store/Admin visibility:** none.
- **Privacy/compliance:** display record only.

### performance_summary_viewed

- **Trigger:** driver views the performance summary.
- **Actor:** driver.
- **Required metadata:** metric set reference.
- **Forbidden metadata:** sensitive ID data, raw safety detail.
- **Store/Admin visibility:** none.
- **Privacy/compliance:** display record only.

### compliance_metric_viewed

- **Trigger:** driver views a compliance metric.
- **Actor:** driver.
- **Required metadata:** metric reference.
- **Forbidden metadata:** raw ID data, ID images, full ID numbers.
- **Store/Admin visibility:** none.
- **Privacy/compliance:** redacted display record.

### reward_tier_viewed

- **Trigger:** driver views a reward/status tier (future).
- **Actor:** driver.
- **Required metadata:** tier reference.
- **Forbidden metadata:** sensitive ID data, payment data.
- **Store/Admin visibility:** none.
- **Privacy/compliance:** display record only.

### reward_tier_candidate_calculated_future

- **Trigger:** a tier candidate is calculated (future, backend).
- **Actor:** backend (future).
- **Required metadata:** tier reference, signal references.
- **Forbidden metadata:** sensitive ID data, payment data.
- **Store/Admin visibility:** Admin (future).
- **Privacy/compliance:** future; review-gated.

### earnings_dispute_started_future

- **Trigger:** an earnings dispute is started (future).
- **Actor:** driver (future).
- **Required metadata:** delivery/period reference, category.
- **Forbidden metadata:** bank/tax data, payment account data.
- **Store/Admin visibility:** Admin (future).
- **Privacy/compliance:** future; dispute record.

### earnings_support_requested

- **Trigger:** driver requests earnings support.
- **Actor:** driver.
- **Required metadata:** delivery/period reference, category.
- **Forbidden metadata:** bank/tax data, payment account data.
- **Store/Admin visibility:** Admin support context.
- **Privacy/compliance:** support record.

### performance_support_requested

- **Trigger:** driver requests performance support.
- **Actor:** driver.
- **Required metadata:** metric reference, category.
- **Forbidden metadata:** sensitive ID data.
- **Store/Admin visibility:** Admin support context.
- **Privacy/compliance:** support record.

### admin_driver_performance_viewed

- **Trigger:** an admin views driver performance.
- **Actor:** admin.
- **Required metadata:** driver reference, view scope.
- **Forbidden metadata:** sensitive ID data, payment account data.
- **Store/Admin visibility:** Admin audit.
- **Privacy/compliance:** role-limited access record.

### admin_driver_compliance_metrics_viewed

- **Trigger:** an admin views driver compliance metrics.
- **Actor:** admin.
- **Required metadata:** driver reference, view scope.
- **Forbidden metadata:** raw ID data, ID images, full ID numbers.
- **Store/Admin visibility:** Admin audit.
- **Privacy/compliance:** role-limited, redacted access record.

### duplicate_earnings_action_rejected

- **Trigger:** a duplicate earnings action is rejected.
- **Actor:** backend.
- **Required metadata:** action type, idempotency key.
- **Forbidden metadata:** payment account data.
- **Store/Admin visibility:** Admin signal.
- **Privacy/compliance:** dedup record.

### stale_earnings_snapshot_detected

- **Trigger:** a stale earnings snapshot is detected.
- **Actor:** mobile/backend.
- **Required metadata:** snapshot reference, staleness reason.
- **Forbidden metadata:** payment account data.
- **Store/Admin visibility:** minimal.
- **Privacy/compliance:** freshness record.

### earnings_snapshot_refreshed

- **Trigger:** an earnings snapshot is refreshed from the backend.
- **Actor:** mobile/backend.
- **Required metadata:** snapshot reference.
- **Forbidden metadata:** payment account data.
- **Store/Admin visibility:** minimal.
- **Privacy/compliance:** refresh record.

## 20. Idempotency / Snapshot Freshness

- **Earnings snapshots are backend-provided.** The app renders a backend
  snapshot; it never computes one.
- **Stale snapshot handling.** Stale snapshots are detected and marked
  (`stale_earnings_snapshot_detected`).
- **Refresh behavior.** The app refreshes from the backend
  (`earnings_snapshot_refreshed`); it never recomputes.
- **Duplicate refresh prevention.** Duplicate refreshes are deduplicated.
- **Duplicate support/dispute requests.** Duplicates are rejected
  (`duplicate_earnings_action_rejected`).
- **Backend state reconciliation.** The backend reconciles state on reconnect.
- **No local earnings calculation.** The app never calculates payable amounts.
- **No local payout initiation.** The app cannot initiate a payout.
- **No local performance correction.** The app never edits metrics locally.
- **Audit events.** Snapshot and action events are auditable.
- **Offline behavior.** Offline display uses the last backend snapshot, marked
  potentially stale; no local calculation or payout occurs.

## 21. Privacy and Data-Minimization Boundaries

- **No bank data.** No bank account data is collected or shown.
- **No tax data.** No tax data is collected or shown.
- **No full payment account data.** No full payment account data.
- **No raw ID data.** No raw ID data is shown in earnings/performance surfaces.
- **No raw location replay.** No raw location trace is shown.
- **No unrestricted safety details.** Safety detail is minimized and privacy-safe.
- **No call/message content.** No communication content (Dr.1.0.I).
- **Driver-facing metrics should be explainable.** Metrics are understandable,
  not opaque.
- **Admin visibility should be role-limited.** Access is scoped by role.
- **Retention policy required for performance/earnings history.** A retention
  policy is required before storing history.
- **Legal/product/accounting review before payout expansion.** Any payout
  capability requires a dedicated review phase.

## 22. MVP vs Future Boundary

| Feature | MVP / Future / No-Go | Reason | Backend dependency | Mobile dependency | Store/Admin dependency |
|---|---|---|---|---|---|
| Estimated earnings per delivery | MVP (display) | Driver transparency | Estimate provider | Display estimate | None |
| Completed delivery count | MVP (display) | Operational visibility | Completion state | Display count | Admin aggregate |
| Delivery history | MVP (display) | Driver transparency | History projection | Display history | Admin history |
| Earnings summary placeholder | MVP (placeholder) | Visibility-only surface | Snapshot | Display placeholder | None |
| Weekly summary | MVP (placeholder) | Visibility-only surface | Snapshot | Display placeholder | None |
| Payout status | No-Go (Dr.1.0) | No money movement | — | — | — |
| Cashout | No-Go (Dr.1.0) | No money movement | — | — | — |
| Stripe Connect | No-Go (Dr.1.0) | No payment integration | — | — | — |
| Wallet balance | No-Go (Dr.1.0) | No wallet/ledger | — | — | — |
| Bank account management | No-Go (Dr.1.0) | No bank data collection | — | — | — |
| Tax documents | No-Go (Dr.1.0) | No tax handling | — | — | — |
| Performance summary | MVP (display) / Future (full) | Operational quality | Metrics projection | Display metrics | Admin aggregate |
| Compliance metrics | MVP (display) / Future (full) | Compliance accountability | Compliance projection | Display redacted | Admin aggregate |
| Rewards/status tiers | Future | Trust system; review-gated | Tier engine | Display label | Admin aggregate |
| Compliance Trusted | Future | Compliance-safe recognition | Compliance metrics; review | Display label | Admin aggregate |
| Restricted Delivery Certified | Future | Training/legal review needed | Training; review | Display label | Admin aggregate |
| Driver ranking | No-Go (Dr.1.0) | No ranking; avoid auto-discipline | — | — | — |
| Automatic assignment priority | No-Go (Dr.1.0) | No tier-based privilege | — | — | — |
| Payroll/accounting integration | No-Go (Dr.1.0) | Separate legal/accounting phase | — | — | — |

## 23. Future Backend Capability Map

Future backend capabilities needed to implement this architecture. Each is a
candidate, finalized in a later Dr.1.x phase, and extends the Dr.1.0.F gap map.

### Earnings estimate provider

- **Purpose:** provide per-delivery earnings estimates (Section 6).
- **Data sensitivity:** medium.
- **MVP/Future:** future (MVP display depends on it).
- **Depends on:** delivery domain, future earnings policy.
- **Store/Admin impact:** none directly.
- **Compliance/payment risk:** estimate, not payout; no money movement.

### Earnings snapshot model

- **Purpose:** provide read-only earnings snapshots (Section 9).
- **Data sensitivity:** medium.
- **MVP/Future:** future foundation.
- **Depends on:** estimate provider, completion state.
- **Store/Admin impact:** none directly.
- **Compliance/payment risk:** no settlement; display only.

### Delivery history projection

- **Purpose:** provide redacted delivery history (Section 8).
- **Data sensitivity:** medium.
- **MVP/Future:** future foundation.
- **Depends on:** completion/failure/return state (Dr.1.0.H).
- **Store/Admin impact:** Admin history.
- **Compliance/payment risk:** redacted; no sensitive ID/settlement.

### Performance metrics projection

- **Purpose:** compute explainable performance metrics (Section 11).
- **Data sensitivity:** medium.
- **MVP/Future:** future.
- **Depends on:** delivery/support/safety state.
- **Store/Admin impact:** Admin aggregate.
- **Compliance/payment risk:** no auto-discipline; explainable.

### Compliance metrics projection

- **Purpose:** compute redacted compliance metrics (Section 12).
- **Data sensitivity:** high.
- **MVP/Future:** future.
- **Depends on:** verification/proof/return state (Dr.1.0.G/H).
- **Store/Admin impact:** Admin aggregate; no sensitive ID data.
- **Compliance/payment risk:** must not reward shortcuts.

### Reward tier candidate engine

- **Purpose:** compute candidate reward/status tiers (Sections 14–16).
- **Data sensitivity:** medium.
- **MVP/Future:** future (legally reviewed).
- **Depends on:** performance/compliance metrics; admin review.
- **Store/Admin impact:** Admin aggregate.
- **Compliance/payment risk:** no legal claim; no auto-privilege.

### Earnings support/dispute case linkage

- **Purpose:** link earnings support/disputes to Dr.1.0.I cases.
- **Data sensitivity:** medium.
- **MVP/Future:** future.
- **Depends on:** support case model (Dr.1.0.I).
- **Store/Admin impact:** Admin support context.
- **Compliance/payment risk:** no payment movement.

### Admin driver performance view

- **Purpose:** provide a privacy-safe admin performance view (Section 18).
- **Data sensitivity:** medium-high.
- **MVP/Future:** future.
- **Depends on:** metrics projections; role controls.
- **Store/Admin impact:** core Admin visibility.
- **Compliance/payment risk:** role-limited; no sensitive ID/payment.

### Privacy/retention controls

- **Purpose:** govern minimization and retention (Section 21).
- **Data sensitivity:** high.
- **MVP/Future:** future foundation for any storage.
- **Depends on:** legal review.
- **Store/Admin impact:** bounds visibility.
- **Compliance/payment risk:** required before history storage.

### Audit event expansion

- **Purpose:** record earnings/performance audit events (Section 19).
- **Data sensitivity:** medium.
- **MVP/Future:** future foundation.
- **Depends on:** audit infrastructure.
- **Store/Admin impact:** audit detail.
- **Compliance/payment risk:** privacy-safe metadata only.

### Future payout/payroll boundary model

- **Purpose:** define the boundary for any future payout/payroll work.
- **Data sensitivity:** high.
- **MVP/Future:** future (separate legal/product/accounting phase).
- **Depends on:** legal/accounting review.
- **Store/Admin impact:** future.
- **Compliance/payment risk:** highest; explicitly out of Dr.1.0.

## 24. Phase Target Map

Future implementation maps to later Dr.1.x phases. These are planning targets,
not commitments, and define no implementation here.

| Phase | Target |
|---|---|
| Dr.1.1 | Backend earnings/performance read-model foundations (snapshot, history projection, metrics projections, audit) |
| Dr.1.2 | Mobile earnings/history/performance shell |
| Dr.1.3 | Driver MVP earnings visibility and delivery history |
| Dr.1.4 | Support/dispute pathways and admin visibility |
| Dr.1.5 | Rewards/status tiers after legal/product review |
| Dr.1.6 | Analytics, trust signals, and possible payout planning handoff |

## 25. No-Go Reminder

This subphase (Dr.1.0.J) is documentation only. It does not create and does not
authorize creating:

- backend endpoints
- database tables
- migrations
- schemas
- services
- frontend UI
- mobile screens
- a Flutter project
- a Capacitor project
- dependency changes
- tests
- CI/config changes
- payouts
- cashout
- Stripe
- Stripe Connect
- payment processor integration
- a wallet
- bank account collection
- tax documents
- payroll/accounting integration
- earnings calculation implementation
- performance enforcement implementation
- rewards implementation
- driver ranking implementation
- automatic assignment priority
- customer app behavior
- a production launch

All metric names, tier names, event names, and capabilities in this document
are architectural candidates for later Dr.1.x phases. Nothing here is
implemented, and no payment movement is introduced.
