# Dr.1.0 Mobile Stack Decision — Flutter vs Capacitor

## 1. Document Status

- **Phase:** Dr.1.0 — Mobile Research + Driver App Product Architecture
- **Subphase:** Dr.1.0.K — Mobile Stack Research: Flutter vs Capacitor
- **Deliverable path:** `docs/dr.1.0-mobile-stack-decision.md`
- **Status:** Draft / Architecture Decision
- **Scope:** Research/docs only
- **Implementation:** none — this document introduces no backend, frontend, or
  mobile implementation of any kind. It creates no Flutter, Capacitor, React
  Native, native iOS, or native Android project; no dependencies; no tests; no
  CI/config changes; and no camera, GPS, background location, push, secure
  storage, offline queue, maps, navigation, ID scan/OCR/barcode/liveness, or
  payment behavior.

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
`docs/dr.1.0-driver-earnings-performance-rewards.md` (Dr.1.0.J),
`docs/mobile-apps-strategy-roadmap.md`, `docs/f2.27-contract-lock.md`, and
`docs/f2.27.x-stripe-readiness-roadmap.md`. Where this document and those
overlap, those are authoritative and this one cross-references them. The stack
recommendation is an **architectural decision candidate** with explicit revisit
triggers (Section 26). Nothing here is implemented.

## 2. Purpose

NubeRush needs a mobile stack decision now because the Driver App is the next
major application after the web app matures, and the stack choice shapes
velocity, quality, maintainability, app store readiness, and the team's ability
to deliver compliance-sensitive native features.

The decision matters because:

- **The Driver App is the next app after web app maturity.** It follows the F2.x
  web phases and the Dr.1.0 architecture work; choosing the stack unblocks
  Dr.1.x implementation planning.
- **The Driver App must be iOS and Android.** Drivers use both platforms; a
  cross-platform approach is strongly preferred over duplicated native builds.
- **The Driver App has high mobile-native requirements.** Location, the live map,
  notifications, secure storage, and offline behavior are core, not optional.
- **Restricted delivery raises camera/location/privacy/compliance complexity.**
  Regulated smoke-shop and vape delivery means future camera/ID, background
  location, and privacy features with real legal and store-review weight.
- **The choice affects maintainability, velocity, quality, app store readiness,
  and future compliance features.** A single, native-capable cross-platform
  stack reduces long-term cost and risk for a small team.

## 3. Decision Summary

The recommended direction is:

- **Recommended default: Flutter.** Flutter is the default Driver App direction.
  It provides strong native-feeling UI, mature plugins for the Driver App's
  native needs (camera, location, notifications, secure storage), consistent
  iOS/Android parity, and a single codebase a small team can maintain.
- **Fallback/prototype option: Capacitor.** Capacitor is acceptable for a
  short-lived prototype or internal demo that reuses web/React knowledge, but it
  is weaker for the driver-native, background-location, and compliance-heavy
  workflows the production app requires.
- **React Native: optional comparison / viable but not preferred.** React Native
  is a credible cross-platform option and worth comparing, but it is not the
  default unless team preferences or expertise change.
- **Native iOS/Android: not recommended as default.** Fully native dual
  implementation doubles the build and testing burden and demands platform
  specialists this team does not need to commit to for the MVP. It is reserved
  for future/specialized needs only.

Key reasoning:

- **Why Flutter wins.** It balances native capability and single-codebase
  velocity, has a mature plugin ecosystem for the Driver App's native needs,
  produces high-quality consistent UI on both platforms, and fits a
  backend-authorized thin-client model well.
- **Why Capacitor is weaker for driver-native workflows.** Its web-in-webview
  model is excellent for content-style apps but introduces risk and friction for
  background location, sustained GPS/map use, and future camera/compliance
  pipelines.
- **What would make Capacitor acceptable.** A short-lived prototype or internal
  demo with no background location, no production restricted delivery, and a
  clear migration path to Flutter (Section 22).
- **When React Native/native might be reconsidered.** If the team gains strong
  React Native expertise (Section 23), or if compliance/location demands require
  deep native integration that justifies native work (Section 24).

## 4. Dr.1.0 Driver App Requirements Driving the Decision

The decision is grounded in the requirements already defined across Dr.1.0.
These are product requirements, not implementation, and remain backend-authorized.

- **Assigned delivery workflow.** Drivers act on backend-assigned deliveries
  (Dr.1.0.C/E).
- **Store pickup.** Backend-routed pickup and handoff (Dr.1.0.H, Dr.1.0.H2).
- **Customer delivery.** Backend-routed customer leg after confirmed pickup.
- **21+ manual verification MVP.** Manual age/ID verification in the MVP
  (Dr.1.0.G).
- **Future camera/ID workflows.** Future document upload, barcode, OCR, and
  liveness candidates (Dr.1.0.G).
- **Proof/failure/return flows.** Proof, failed delivery, and return-to-store
  (Dr.1.0.H).
- **Live map/navigation surface.** Active delivery map and external navigation
  handoff (Dr.1.0.H2).
- **Safety/support/communication.** Emergency, support, masked communication,
  and incidents (Dr.1.0.I).
- **Notifications.** Assignment, compliance-critical, and safety notifications
  (Dr.1.0.I).
- **Earnings/performance visibility.** Visibility-only earnings and performance
  (Dr.1.0.J).
- **Offline/retry.** Safe offline queueing with no local compliance/payment
  finalization (Dr.1.0.H2, Dr.1.0.I, Dr.1.0.J).
- **Secure auth/session/token storage.** Secure handling of session/refresh
  tokens.
- **Backend-authorized state.** The backend owns lifecycle, compliance, and
  payment state.
- **Privacy-safe audit trail.** Privacy-safe, backend-owned audit events
  throughout.

## 5. Evaluation Criteria

Each criterion is assessed for every stack. For each, this section states why it
matters for NubeRush, what good looks like, and the risk if weak.

### Camera

- **Why it matters:** future ID/document/barcode/OCR/liveness workflows
  (Dr.1.0.G).
- **What good looks like:** mature, maintained camera plugins with secure
  capture and vendor SDK compatibility.
- **Risk if weak:** blocked or fragile future compliance capture.

### Location / GPS

- **Why it matters:** the live map, arrival candidates, and route context
  (Dr.1.0.H2).
- **What good looks like:** reliable foreground location with strong plugin
  support.
- **Risk if weak:** poor map reliability and arrival detection.

### Background location

- **Why it matters:** future background location for route telemetry
  (Dr.1.0.H2), policy-sensitive.
- **What good looks like:** robust, policy-compliant background location support.
- **Risk if weak:** unreliable telemetry and store-review rejection risk.

### Push notifications

- **Why it matters:** assignment, compliance-critical, and safety notifications
  (Dr.1.0.I).
- **What good looks like:** reliable push with secure token handling and
  permission flows.
- **Risk if weak:** missed compliance/safety notifications.

### Secure storage

- **Why it matters:** session/refresh token protection (Section 15).
- **What good looks like:** keychain/keystore-backed secure storage.
- **Risk if weak:** credential exposure on device.

### Offline / retry queue

- **Why it matters:** field connectivity is unreliable; safe queueing required
  (Dr.1.0.H2/I/J).
- **What good looks like:** durable local persistence with idempotent replay.
- **Risk if weak:** lost actions or unsafe local finalization.

### Navigation handoff

- **Why it matters:** external Apple Maps / Google Maps / Waze handoff
  (Dr.1.0.H2).
- **What good looks like:** reliable deep-link handoff to navigation apps.
- **Risk if weak:** broken navigation experience.

### Maps

- **Why it matters:** the live active-delivery map surface (Dr.1.0.H2).
- **What good looks like:** capable map rendering and future embedded-map
  options.
- **Risk if weak:** degraded situational awareness.

### Performance

- **Why it matters:** sustained map/location use and responsive UI.
- **What good looks like:** smooth, native-feeling performance under load.
- **Risk if weak:** battery drain, jank, and poor driver experience.

### Team complexity

- **Why it matters:** a small team must maintain the app long-term.
- **What good looks like:** a single codebase with a manageable learning curve.
- **Risk if weak:** slow delivery and high maintenance cost.

### Reuse from web

- **Why it matters:** the existing web stack and design language are assets.
- **What good looks like:** reuse of contracts and design language (not
  necessarily UI code).
- **Risk if weak:** duplicated product logic and drift.

### Long-term maintainability

- **Why it matters:** the Driver App is a long-lived platform.
- **What good looks like:** stable framework, healthy ecosystem, clear upgrades.
- **Risk if weak:** accumulating technical debt.

### App Store / Play Store readiness

- **Why it matters:** restricted delivery and location/camera draw review
  scrutiny (Section 20).
- **What good looks like:** well-trodden submission paths and policy alignment.
- **Risk if weak:** review delays or rejections.

### Testing strategy

- **Why it matters:** compliance-sensitive flows must be testable (Section 17).
- **What good looks like:** strong unit/widget/integration and device testing.
- **Risk if weak:** undetected regressions in critical flows.

### CI/CD impact

- **Why it matters:** signing, release channels, and build burden (Section 18).
- **What good looks like:** automatable pipelines with manageable build times.
- **Risk if weak:** operational drag on a small team.

### Compliance / privacy suitability

- **Why it matters:** regulated delivery and data minimization (Dr.1.0.G/I/J).
- **What good looks like:** secure capture/storage and privacy-safe behavior.
- **Risk if weak:** compliance and privacy exposure.

### Plugin ecosystem maturity

- **Why it matters:** native features depend on maintained plugins.
- **What good looks like:** mature, actively maintained plugins.
- **Risk if weak:** dependency risk and stalled features.

### UI quality and consistency

- **Why it matters:** a professional, consistent driver experience.
- **What good looks like:** consistent, native-feeling UI on both platforms.
- **Risk if weak:** inconsistent or low-quality UI.

### Future scalability

- **Why it matters:** the app must grow into compliance/analytics surfaces.
- **What good looks like:** headroom for future native and product features.
- **Risk if weak:** a ceiling that forces a rewrite.

## 6. Option A — Flutter

Flutter is a cross-platform UI framework using the Dart language, compiling to
native iOS and Android.

- **Dart/Flutter cross-platform model.** A single Dart codebase targets both
  platforms with native compilation.
- **Strong native-feeling UI.** Flutter renders its own consistent UI, giving a
  polished, native-feeling experience.
- **iOS/Android parity.** High parity across platforms reduces divergence.
- **Camera plugin ecosystem.** Mature camera plugins support future ID/document
  capture (subject to Dr.1.0.G review).
- **GPS/location support.** Strong location plugin support for the live map
  (Dr.1.0.H2).
- **Background location options.** Background location is achievable via
  maintained plugins, subject to store policy review (Section 20).
- **Push notification support.** Established push support with secure token
  handling.
- **Secure storage support.** Keychain/keystore-backed secure storage plugins.
- **Offline/local persistence options.** Mature local persistence for offline
  queues (Dr.1.0.H2/I/J).
- **Navigation handoff support.** Reliable deep-link handoff to external
  navigation apps.
- **Maps options.** Capable map rendering and future embedded-map options.
- **Performance expectations.** Strong performance for sustained map/location
  use.
- **Testing support.** Robust unit, widget, and integration testing.
- **CI/CD suitability.** Well-supported build/sign/release pipelines.
- **App Store / Play Store readiness.** Well-trodden submission paths.
- **Team learning curve.** Dart is a manageable learning curve for a team new to
  it; the single codebase offsets the ramp.
- **Backend integration via API client.** Integrates cleanly with backend APIs as
  the primary boundary.
- **Fit with backend-authorized architecture.** Suits a thin client that renders
  backend state and proposes actions.
- **Risks and mitigations.** Dart ramp (mitigate with training and a thin-client
  scope); plugin dependency risk (mitigate by selecting maintained plugins and
  isolating native concerns).

Assessment:

- **Strengths:** native capability, single codebase, UI quality, mature plugins,
  strong testing/CI fit.
- **Weaknesses:** Dart learning curve; reliance on community plugins for some
  native features.
- **NubeRush fit:** strong fit for the driver-native, compliance-sensitive app.
- **MVP suitability:** strong.
- **Future suitability:** strong (camera/compliance/location headroom).
- **Recommendation:** recommended default.

## 7. Option B — Capacitor

Capacitor wraps a web app (typically React) in a native shell with a bridge to
native plugins.

- **Web-to-mobile approach.** A web app runs in a native webview with native
  plugin bridges.
- **Reuse of web/React knowledge.** Strong reuse of the team's existing web/React
  skills.
- **Potential reuse of design/system concepts.** Design language and components
  may be reused.
- **Fast prototype potential.** Excellent for quickly standing up a prototype.
- **Camera plugin support.** Camera plugins exist but may be less suited to
  advanced compliance capture pipelines.
- **GPS/location support.** Foreground location is supported.
- **Background location limitations/risks.** Background location is a known weak
  spot, with reliability and store-policy risk for sustained tracking.
- **Push notification support.** Push is supported via plugins.
- **Secure storage considerations.** Secure storage exists but warrants careful
  review for token protection.
- **Offline/local persistence considerations.** Web-based persistence is possible
  but may be less robust for durable native queues.
- **Navigation handoff support.** External navigation handoff via links is
  feasible.
- **Maps/webview/native boundary tradeoffs.** Map and sustained-GPS workloads
  cross the webview/native boundary, adding performance and reliability risk.
- **Performance limitations for native-heavy flows.** Native-heavy, sustained
  flows (live map, background location) are weaker than compiled native.
- **App store readiness considerations.** Submittable, but compliance/location
  review risk is higher for native-heavy use.
- **Testing/CI/CD considerations.** Web testing reuse is a plus; device-level
  native testing still required.
- **Plugin dependency risk.** Reliance on the Capacitor plugin ecosystem for
  native features.
- **Fit with backend-authorized architecture.** Fits the thin-client model for
  display-centric flows.
- **Risks and mitigations.** Background location and sustained map reliability
  (mitigate by avoiding these in prototype scope); migration cost to Flutter
  (mitigate by keeping prototype thin and contract-driven).

Assessment:

- **Strengths:** fast prototyping, web/React reuse, low ramp.
- **Weaknesses:** background location, sustained map/native performance, future
  compliance capture.
- **NubeRush fit:** weak for production driver-native workflows; fine for
  prototypes.
- **MVP suitability:** limited; acceptable only for prototype/demo scope.
- **Future suitability:** weak for compliance/location-heavy future.
- **Recommendation:** fallback/prototype only.

## 8. Option C — React Native

React Native is a cross-platform framework using JavaScript/TypeScript with
native modules.

- **Cross-platform model.** A single JS/TS codebase targets both platforms.
- **JavaScript/TypeScript familiarity.** Aligns with the team's web language
  skills.
- **Native module ecosystem.** A broad native module ecosystem covers camera,
  location, and push.
- **Camera/location/push support.** Well-supported through community and vendor
  modules.
- **Bridge/native module complexity.** The native bridge and module management
  add complexity, especially for advanced native features.
- **Performance considerations.** Good performance, with care needed for
  native-heavy flows.
- **Testing/CI/CD considerations.** Mature testing and CI tooling; native build
  management still required.
- **Team complexity.** Requires native module discipline and occasional native
  debugging.
- **Fit with existing web knowledge.** Strong alignment with TypeScript/web
  contracts.
- **Why it may be viable.** Credible cross-platform option with strong ecosystem
  and TS contract sharing.
- **Why it is not the default recommendation unless team preferences change.**
  Flutter's UI consistency and plugin maturity edge it out for this team unless
  React Native expertise or TS-contract priorities dominate.

Assessment:

- **Strengths:** TS alignment, ecosystem, contract sharing.
- **Weaknesses:** bridge/native complexity, UI consistency vs Flutter.
- **NubeRush fit:** viable, not preferred for this team now.
- **Recommendation:** optional comparison; reconsider per Section 23.

## 9. Option D — Native iOS + Native Android

Fully native means separate Swift/iOS and Kotlin/Android applications.

- **Best native API access.** Direct, first-class access to every platform API.
- **Highest platform-specific control.** Maximum control over native behavior.
- **Duplicated implementation cost.** Two codebases double feature and fix work.
- **Need for iOS and Android expertise.** Requires sustained platform specialist
  skills.
- **Slower iteration for a small team.** Duplicate work slows velocity.
- **Higher testing/CI burden.** Two test suites and two pipelines.
- **Stronger fit only if future compliance/location demands require it.** Deep
  native integration may justify native work later (Section 24).
- **Not recommended as default.** The cost is not justified for the MVP.

Assessment:

- **Strengths:** maximal native control and API access.
- **Weaknesses:** duplicated cost, specialist needs, slow iteration.
- **NubeRush fit:** poor as default; future/specialized only.
- **Recommendation:** not recommended as default; reconsider per Section 24.

## 10. Comparison Matrix

Ratings: Strong, Medium, Weak, Risky, Overkill.

| Category | Flutter | Capacitor | React Native | Native iOS/Android | Notes |
|---|---|---|---|---|---|
| Camera | Strong | Medium | Strong | Strong | Native best; Flutter/RN mature; Capacitor adequate for basic capture |
| Location / GPS | Strong | Medium | Strong | Strong | Foreground solid across all; Capacitor weaker under sustained use |
| Background location | Strong | Weak | Medium | Strong | Capacitor is the key weak spot; native strongest |
| Push notifications | Strong | Medium | Strong | Strong | All support push; Capacitor via plugins |
| Secure storage | Strong | Medium | Strong | Strong | Keychain/keystore best on native/Flutter/RN |
| Offline / retry queue | Strong | Medium | Strong | Strong | Durable native persistence preferred over webview storage |
| Navigation handoff | Strong | Strong | Strong | Strong | External deep-link handoff feasible everywhere |
| Maps | Strong | Medium | Strong | Strong | Sustained map use weaker in webview |
| Performance | Strong | Weak | Strong | Strong | Native-heavy flows favor compiled stacks |
| Team complexity | Medium | Strong | Medium | Weak | Capacitor lowest ramp; native highest burden |
| Web reuse | Medium | Strong | Strong | Weak | Capacitor/RN reuse web skills; Flutter reuses contracts/design |
| Maintainability | Strong | Medium | Strong | Weak | Single codebase beats dual native |
| App store readiness | Strong | Medium | Strong | Strong | Capacitor higher review risk for native-heavy use |
| Testing | Strong | Medium | Strong | Strong | All testable; native doubles suites |
| CI/CD | Strong | Medium | Medium | Weak | Native doubles pipelines |
| Compliance / privacy suitability | Strong | Weak | Strong | Strong | Secure capture/storage favors native/Flutter/RN |
| Future scalability | Strong | Weak | Strong | Overkill | Native is overkill as default; Capacitor ceiling for compliance/location |

## 11. Camera / ID Verification Readiness

Camera/ID readiness is assessed against Dr.1.0.G. No camera or ID capture is
implemented in this subphase.

- **MVP manual checklist, no camera required.** The Dr.1.0.G MVP is manual
  verification, so no camera is required at launch; all stacks satisfy the MVP.
- **Future document upload.** Future document upload favors stacks with mature,
  secure camera/file plugins (Flutter, React Native, native).
- **Future barcode scanning.** Barcode scanning is well supported on Flutter,
  React Native, and native; Capacitor is workable but less ideal for sustained
  scanning.
- **Future OCR/vendor integration.** Vendor SDK integration is strongest where
  native module access is clean (native, Flutter, React Native).
- **Future liveness/face match vendor.** Liveness vendors typically ship native
  SDKs; Flutter/React Native/native integrate these more reliably than a
  webview model.
- **Privacy and legal review boundaries.** Any capture pipeline requires legal
  review and data-minimization (Dr.1.0.G/J); no raw ID storage by default.
- **No raw ID storage by default.** The architecture stores no raw ID data by
  default regardless of stack.
- **Secure capture pipeline future need.** A future secure capture pipeline favors
  native-capable stacks.

Conclusion: **Flutter is best positioned** for the MVP and the future
camera/compliance roadmap, with native and React Native also strong; Capacitor
is adequate only for basic, non-compliance prototype capture.

## 12. Location / GPS / Background Location Readiness

Assessed against Dr.1.0.H2. No location or tracking is implemented here.

- **Foreground location.** Required for the live map and own-position display;
  supported by all stacks.
- **Active delivery map.** Sustained foreground location/map use favors compiled
  native stacks over webview.
- **Arrival candidate.** Manual arrival is MVP; future geofence candidates favor
  native-capable stacks.
- **Background location future.** Background location is the decisive factor:
  strong on native and Flutter, risky/weak on Capacitor.
- **Permission recovery.** Permission recovery flows are implementable on all
  stacks (Dr.1.0.H2).
- **Privacy notices.** Privacy-first disclosures required regardless of stack.
- **No hidden tracking.** No silent tracking on any stack.
- **App Store / Play Store policy sensitivity.** Background/precise location draws
  review scrutiny; mature stacks reduce risk (Section 20).
- **Driver transparency.** Drivers are informed about location use.
- **Route telemetry future.** Future telemetry favors reliable background
  location support.

Conclusion: **Flutter is best positioned** (native is also strong); Capacitor's
background location weakness makes it unsuitable for the production location
roadmap.

## 13. Maps and Navigation Handoff Readiness

Assessed against Dr.1.0.H2. No maps or navigation are implemented here.

- **External Apple Maps handoff.** Deep-link handoff feasible on all stacks.
- **External Google Maps handoff.** Feasible on all stacks.
- **Waze handoff.** Feasible on all stacks.
- **Embedded map future.** Future embedded maps favor native-capable stacks;
  webview embedding is heavier.
- **Internal turn-by-turn future.** Future internal navigation (if ever) favors
  native-capable stacks.
- **Live map surface.** Sustained live map rendering favors Flutter/native over
  Capacitor.
- **ETA/distance display.** Estimate display is straightforward on all stacks.
- **Offline/stale route state behavior.** Durable offline state favors native
  persistence.
- **Privacy boundaries.** No raw continuous location replay regardless of stack
  (Dr.1.0.H2).

Conclusion: **Flutter is best positioned** for the live map and future embedded
map options; all stacks handle external handoff, but Capacitor is weaker for the
sustained live-map surface.

## 14. Push Notifications and Compliance-Critical Notifications Readiness

Assessed against Dr.1.0.I. No notification delivery is implemented here.

- **Assignment notifications.** Supported on all stacks.
- **Active delivery alerts.** Supported on all stacks.
- **Compliance-critical notifications.** Must be backend-driven (Dr.1.0.I);
  delivery reliability favors mature push support (Flutter, React Native,
  native).
- **Return-to-store reminders.** Supported on all stacks.
- **Support/safety alerts.** High-priority delivery favors reliable native push.
- **Stale notification handling.** Stale reconciliation is a client concern
  implementable on all stacks (Dr.1.0.I).
- **Push token security.** Secure token handling favors keychain/keystore-backed
  stacks.
- **Platform permission handling.** Permission flows supported across stacks.
- **Backend-driven notification principle.** All notifications originate from
  backend-authorized state (Dr.1.0.I).

Conclusion: **Flutter is best positioned** with reliable push and secure token
handling; React Native and native are also strong; Capacitor is workable but
carries more plugin/reliability risk.

## 15. Secure Storage, Auth, and Session Handling Readiness

No secure storage or auth is implemented here.

- **Supabase/session token storage future considerations.** Session/refresh
  tokens (e.g. Supabase-issued) must be stored securely; the local `.env`
  DATABASE_URL and backend secrets are never embedded in the app.
- **Secure storage requirements.** Keychain (iOS) / keystore (Android) backed
  storage is required.
- **Refresh token protection.** Refresh tokens must be protected at rest.
- **Device-level risk.** Lost/compromised devices require revocation support.
- **Logout/revocation behavior.** Backend-authorized logout/revocation.
- **Offline session behavior.** Offline sessions must not enable local
  compliance/payment finalization (Dr.1.0.H2/I/J).
- **No sensitive ID data storage.** No raw ID data stored on device (Dr.1.0.G/J).
- **Platform secure enclave/keychain/keystore considerations.** Native, Flutter,
  and React Native have strong secure-storage paths; Capacitor requires careful
  review.

Conclusion: **Flutter is best positioned** (native and React Native also strong)
for secure session/token handling; Capacitor needs extra scrutiny.

## 16. Offline / Retry Queue Readiness

Assessed against Dr.1.0.H2/I/J. No offline queue is implemented here.

- **Offline queue for safe actions.** Non-sensitive actions may queue offline.
- **Idempotency keys.** Queued actions carry idempotency keys (Dr.1.0.H2/I/J).
- **Stale state reconciliation.** Backend reconciles state on reconnect.
- **No local restricted completion.** Restricted completion never finalizes
  locally (Dr.1.0.G/H).
- **No local compliance override.** Compliance state is never overridden locally.
- **No local payout/payment mutation.** No payment movement locally (Dr.1.0.J).
- **Local persistence options.** Durable native persistence favors Flutter/native
  over webview storage.
- **Audit replay events.** Queue and replay are auditable (Dr.1.0.I/J).
- **Conflict handling.** Backend reconciliation resolves conflicts.

Conclusion: **Flutter is best positioned** for durable offline queues with
idempotent replay; Capacitor's webview persistence is weaker for this need.

## 17. Testing Strategy

Future testing strategy by stack. No tests are added in this subphase.

- **Unit tests.** Strong on Flutter (Dart), React Native (JS/TS), and native.
- **Widget/component tests.** Flutter widget tests and React Native component
  tests are mature; Capacitor reuses web component tests.
- **Integration tests.** Supported across stacks with varying tooling.
- **Mocked API client tests.** The backend API client is mockable on all stacks.
- **Offline queue tests.** Native-backed queues are more deterministically
  testable than webview storage.
- **Permission state tests.** Permission scenarios are testable across stacks.
- **Notification tests.** Push handling is testable with platform tooling.
- **Location simulation tests.** Location simulation is supported on native-
  capable stacks.
- **E2E/manual device testing.** Required on all stacks; physical-device testing
  is essential for location/notification flows.
- **App Store / Play Store release testing.** TestFlight and Play internal
  testing apply to all stacks.

Stack-specific implications: Flutter offers a cohesive, well-documented testing
story; React Native is strong with JS tooling; Capacitor reuses web tests but
still needs native device testing; native doubles the test suites.

## 18. CI/CD Impact

Assessed for future build/release. No CI/CD changes are made here.

- **Build pipelines.** Single-codebase stacks (Flutter, React Native, Capacitor)
  use one primary pipeline; native uses two.
- **iOS signing/profiles.** Required for all stacks targeting iOS.
- **Android signing.** Required for all stacks targeting Android.
- **Environment management.** Backend API endpoints and config managed per
  environment; no secrets embedded in the app.
- **Release channels.** Beta/internal/production channels apply across stacks.
- **TestFlight.** iOS beta distribution for all stacks.
- **Play internal testing.** Android internal distribution for all stacks.
- **Automated checks.** Lint/test/build checks automatable on all stacks.
- **Dependency risk.** Plugin/module dependencies carry maintenance risk
  (highest exposure for plugin-bridged stacks).
- **Build time.** Single-codebase builds are generally lighter than dual native.
- **Team operational burden.** Native dual pipelines impose the highest burden;
  Flutter/React Native/Capacitor are lighter.

Comparison: Flutter and React Native offer balanced CI/CD with one primary
pipeline; Capacitor is light but adds webview/native coordination; native is the
heaviest operationally.

## 19. Team Complexity and Web Reuse

- **Current web stack reuse.** The existing web app (React-based) and its design
  language are assets, but UI code reuse is not the deciding factor.
- **React/design-system reuse possibilities.** Capacitor and React Native enable
  the most direct web/React reuse; Flutter reuses design language and product
  contracts rather than UI code.
- **API contract reuse.** All stacks reuse the backend API contracts as the
  primary integration boundary.
- **Shared design language vs shared code.** The durable reuse is shared product
  contracts and design language, not necessarily shared UI code.
- **Learning curve.** Flutter/Dart adds a learning curve; Capacitor/React Native
  align more directly with existing skills.
- **Hiring/contractor availability.** Flutter and React Native both have healthy
  talent pools; this should be monitored (Section 23).
- **Long-term maintainability.** A single native-capable codebase (Flutter) is
  more maintainable than dual native and more reliable than webview for
  driver-native needs.
- **Why web reuse should not outweigh driver-native needs.** The Driver App's
  background location, sustained map, secure storage, and future compliance
  capture needs are native-heavy; short-term web reuse must not compromise these
  long-term requirements.

## 20. App Store / Play Store Policy Readiness

Assessed for future submission. No store deployment is performed here.

- **Background location policies.** Background/precise location requires clear
  justification and disclosures; mature stacks reduce review risk.
- **Location privacy disclosures.** Required privacy disclosures for location use.
- **Camera/ID verification review.** Future camera/ID capture draws review
  scrutiny and legal review (Dr.1.0.G).
- **Push notification permission.** Standard permission prompts and rationale.
- **Safety/emergency feature review.** Emergency/safety features (Dr.1.0.I) may
  draw additional review; native emergency calling is a future, store-sensitive
  item.
- **Data retention disclosures.** Retention policies must be disclosed
  (Dr.1.0.I/J).
- **No hidden tracking.** No silent tracking on any stack.
- **Compliance feature legal review.** Compliance features require legal review
  before release.
- **Review risk by stack.** Native-heavy use over a webview (Capacitor) carries
  higher review risk than compiled native stacks for location/compliance
  features.
- **Policy documentation requirements.** Submission requires documented privacy,
  location, and data-handling policies.

Conclusion: **Flutter (and native) are best positioned** for store review of a
location/compliance-heavy app; Capacitor carries higher review risk for these
features.

## 21. Recommended Architecture Direction

- **Build the Driver App with Flutter by default.** Flutter is the recommended
  default direction for the production Driver App.
- **Use backend API contracts as the primary integration boundary.** The backend
  remains the authority; the app integrates through versioned API contracts.
- **Reuse design language and product contracts from web, not necessarily UI
  code.** The durable reuse is shared contracts and design language.
- **Keep the mobile app a thin client.** Render backend state, initiate actions,
  queue safe retries, and never own compliance, payment, or final lifecycle
  decisions (Dr.1.0.G/H/H2/I/J).
- **Use Capacitor only for a prototype/internal demo if speed matters more than
  native reliability.** Capacitor is acceptable for scoped, short-lived
  prototypes (Section 22).
- **Do not start native iOS/Android dual implementation for the MVP.** Native
  dual builds are reserved for future/specialized needs (Section 24).

## 22. When Capacitor Would Be Acceptable

Capacitor is acceptable when all of the following hold:

- **Short-lived prototype.** The build is intentionally temporary.
- **Internal demo.** It targets internal stakeholders, not production drivers.
- **Investor/store operator walkthrough.** It demonstrates the workflow concept.
- **Limited driver workflow simulation.** It simulates, rather than operates, the
  driver workflow.
- **No background location requirement.** It does not rely on background location.
- **No future camera/compliance complexity in the prototype.** It avoids
  compliance capture pipelines.
- **No production restricted delivery use.** It is never used for real restricted
  deliveries.
- **Clear migration path to Flutter.** A documented path to migrate to Flutter
  exists, keeping the prototype thin and contract-driven.

## 23. When React Native Would Be Reconsidered

React Native would be reconsidered as the default when:

- **The team has strong React Native expertise.** Existing RN depth shifts the
  trade-off.
- **Plugin needs align well.** Required native modules are mature and proven.
- **Flutter hiring becomes an issue.** Talent availability favors RN.
- **Shared TypeScript contracts become a major priority.** TS contract sharing
  becomes a dominant requirement.
- **A proven native module strategy exists.** The team has a reliable native
  module approach.
- **The CI/CD team can support RN complexity.** Operational support is in place.

## 24. When Native Would Be Reconsidered

Fully native would be reconsidered when:

- **A regulatory/compliance vendor requires deeper native integration.** A vendor
  SDK demands native control beyond cross-platform reach.
- **Background location complexity becomes extreme.** Requirements exceed
  cross-platform plugin reliability.
- **App Store/Play Store review requires platform-specific behavior.** Review
  demands platform-specific implementations.
- **An advanced camera/liveness stack requires native control.** Compliance
  capture requires first-class native access.
- **A separate iOS/Android team exists.** Staffing supports dual native work.
- **Long-term budget supports duplicate platform work.** The organization can
  fund two codebases.

## 25. Phase Target Map

Future implementation maps to later Dr.1.x phases. These are planning targets,
not commitments, and define no implementation here.

| Phase | Target |
|---|---|
| Dr.1.1 | Backend contracts needed before mobile (driver backend surface, route/support/earnings read models, audit) |
| Dr.1.2 | Mobile project foundation decision/build setup (Flutter foundation, CI/CD scaffolding planning) |
| Dr.1.3 | Driver MVP Flutter app (active delivery, pickup, verification, proof/failure/return, live map) |
| Dr.1.4 | Safety/support/notifications (Dr.1.0.I surfaces) |
| Dr.1.5 | Compliance/camera/location upgrades (Dr.1.0.G capture, background location) |
| Dr.1.6 | Analytics/performance/rewards surfaces (Dr.1.0.J visibility) |

## 26. Decision Record

- **Decision:** Adopt Flutter as the default mobile stack for the NubeRush Driver
  App, with Capacitor reserved for prototype/demo use and React Native/native as
  reconsideration paths.
- **Date placeholder:** [DECISION_DATE — to be set when ratified]
- **Owner placeholder:** [DECISION_OWNER — to be assigned]
- **Status:** Draft / Architecture Decision (candidate; not yet ratified).
- **Rationale:** Flutter balances native capability and single-codebase velocity,
  best fits the driver-native, compliance-sensitive requirements (background
  location, sustained map, secure storage, future camera/compliance), and suits a
  small team and a backend-authorized thin-client model.
- **Alternatives considered:** Capacitor (prototype-only; weak for
  background-location/native-heavy production), React Native (viable;
  reconsider per Section 23), native iOS/Android (overkill as default; reconsider
  per Section 24).
- **Consequences:** the team invests in Dart/Flutter; UI reuse from web is
  limited to design language and contracts; durable reuse is the backend API
  contract boundary; a single codebase reduces long-term maintenance.
- **Revisit triggers:** the conditions in Sections 22 (Capacitor), 23 (React
  Native), and 24 (native), plus any major change in team expertise, hiring,
  compliance vendor requirements, or store policy.

## 27. No-Go Reminder

This subphase (Dr.1.0.K) is documentation only. It does not create and does not
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
- a React Native project
- a native iOS project
- a native Android project
- dependency changes
- tests
- CI/config changes
- camera implementation
- GPS implementation
- background location implementation
- push notification implementation
- secure storage implementation
- offline queue implementation
- map/navigation implementation
- an App Store / Play Store release
- ID scan/OCR/barcode/liveness implementation
- Stripe/payment/payout behavior
- a production launch

This document records an architecture decision only. The stack recommendation is
an architectural decision candidate with explicit revisit triggers (Section 26).
Nothing here is implemented.
