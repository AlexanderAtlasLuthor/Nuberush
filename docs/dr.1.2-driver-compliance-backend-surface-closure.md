# NubeRush Dr.1.2 — Driver Compliance Backend Surface Closure

Status: closure artifact (as-built)
Closure base SHA: `e2f4e90d267c9ca4f5ebe671d3eabe5088cd3ac9`
Migration head: `d4e8b2c1f3a7`

## 1. Executive Summary

Dr.1.2 is the backend compliance surface for the NubeRush Driver App. It is a
backend-only phase: it adds API endpoints, services, storage, audit, and
idempotency support. It does not add any mobile, web, or UI code.

Dr.1.2 builds directly on top of Dr.1.1 (the driver backend foundations:
profile, eligibility, assignment lifecycle, and the operational delivery
flow up to `arrived_at_customer`). Dr.1.2 begins where the driver has
physically arrived at the customer and the compliance-sensitive part of the
delivery starts.

Dr.1.2 implemented the following backend capability set:

- delivery-time age / 21+ verification (verify-age)
- proof of delivery
- complete delivery gate
- failed delivery
- return-to-store custody progression
- store return confirmation
- redaction and operational-audit hardening
- a strong, optional `Idempotency-Key` ledger for compliance actions

All commercial outcomes (Order.status, inventory) continue to flow through the
existing orders/inventory authority. The driver layer never writes Order.status
or mutates inventory directly.

## 2. Phase Timeline / Commits

| Phase | Commit | Message |
| --- | --- | --- |
| A | `b83481de08c86bce009dd8281e20a7fc34250ea7` | docs(driver): lock Dr.1.2 compliance backend surface |
| B | `288b32d9f50503897caa91ee70b27b084521787b` | feat(driver): add Dr.1.2.B driver compliance storage foundation |
| C | `e60570cc012fdd04a6b4ab02b909e561563100c2` | feat(driver): add Dr.1.2.C verify-age action |
| D | `8a4af48acb47ed10d3a35c46547de0f50d29e018` | feat(driver): add Dr.1.2.D proof of delivery action |
| E | `6b3da771ac2f8c0a6bcee7db5cd59c3cc6f29a5f` | feat(driver): add Dr.1.2.E complete delivery gate |
| F | `345d7cbfc6f85d20ef89c9a3d27f1c868b1bb53f` | feat(driver): add Dr.1.2.F failed delivery action |
| G | `69f65724a566059f68f5859407fc495de5f4f79e` | feat(driver): add Dr.1.2.G return-to-store action |
| H | `8f6074f675865007aa1f514e3a008d3d9a1cf7ff` | feat(driver): add Dr.1.2.H store return confirmation |
| I.a | `f935548d6ee66ed03db1b5ce4ca8a3beda8af422` | feat(driver): harden compliance audit redaction |
| I.b | `2af994307ac2d05571de9d6751de42531c12af3e` | feat(driver): add compliance idempotency ledger pilot |
| I.c | `e2f4e90d267c9ca4f5ebe671d3eabe5088cd3ac9` | feat(driver): add compliance idempotency to driver actions |

Dr.1.2.I.d was a read-only final regression validation pass. It made no code
or test changes and produced no commit.

## 3. Final Route Surface

Driver router (`backend/app/api/routes/driver.py`):

GET (5):

- `GET /driver/me`
- `GET /driver/eligibility`
- `GET /driver/assignments`
- `GET /driver/assignments/{assignment_id}`
- `GET /driver/assignments/{assignment_id}/delivery-state`

POST (12):

- `POST /driver/assignments/{assignment_id}/accept`
- `POST /driver/assignments/{assignment_id}/decline`
- `POST /driver/assignments/{assignment_id}/start`
- `POST /driver/assignments/{assignment_id}/arrive-store`
- `POST /driver/assignments/{assignment_id}/pickup`
- `POST /driver/assignments/{assignment_id}/depart-to-customer`
- `POST /driver/assignments/{assignment_id}/arrive-customer`
- `POST /driver/assignments/{assignment_id}/verify-age`
- `POST /driver/assignments/{assignment_id}/proof`
- `POST /driver/assignments/{assignment_id}/complete`
- `POST /driver/assignments/{assignment_id}/fail`
- `POST /driver/assignments/{assignment_id}/return-to-store`

Final driver count: 5 GET, 12 POST, 0 PUT/PATCH/DELETE.

Store / orders endpoint (orders router, used to close the failed-return loop):

- `POST /orders/{order_id}/confirm-driver-return`

## 4. Compliance Actions Implemented

### verify-age

- Endpoint: `POST /driver/assignments/{assignment_id}/verify-age`
- Creates a `DriverDeliveryVerification` record.
- A `pass` outcome moves the operational state
  `arrived_at_customer -> id_verified`.
- A `fail` / `manual_review` outcome records the attempt and does not advance
  the state (it stays at `arrived_at_customer`).
- Authority boundary: no Order.status write, no inventory mutation.

### proof

- Endpoint: `POST /driver/assignments/{assignment_id}/proof`
- Creates a `DriverDeliveryProof` record.
- Requires all manual checklist confirmations to be true.
- Record-only: operational state stays `id_verified`.
- No photo, signature, or uploaded artifact storage.
- Authority boundary: no Order.status write, no inventory mutation.

### complete

- Endpoint: `POST /driver/assignments/{assignment_id}/complete`
- Requires a passed verification and a recorded proof.
- Moves the operational state `id_verified -> delivery_completed`.
- Closes the assignment `started -> completed`.
- Calls the orders authority bridge to set `Order.status = delivered`
  (which performs the inventory consume and writes the OrderAuditLog).
- Authority boundary: the driver layer never writes Order.status and never
  mutates inventory directly; the commercial promotion is the orders
  authority's responsibility.

### fail

- Endpoint: `POST /driver/assignments/{assignment_id}/fail`
- Creates a `DriverDeliveryFailure` record (structured reason code + safe note).
- Moves the operational state to `delivery_failed`.
- The assignment remains `started`.
- Authority boundary: Order.status unchanged, inventory unchanged,
  OrderAuditLog untouched.

### return-to-store

- Endpoint: `POST /driver/assignments/{assignment_id}/return-to-store`
- `action=start` moves `delivery_failed -> returning_to_store` and creates a
  `DriverDeliveryReturn` with `return_state = returning`.
- `action=arrive` moves `returning_to_store -> returned_to_store` and updates
  that row to `return_state = returned_pending_confirmation`.
- The driver never confirms the return (`confirmed_*` stay null).
- Authority boundary: Order.status unchanged, inventory unchanged.

### confirm-driver-return

- Endpoint: `POST /orders/{order_id}/confirm-driver-return`
- Lives in the orders router/service (orders/store authority).
- Manager / owner / admin only; store-scoped (admin cross-store).
- Confirms the physical return receipt.
- Sets `DriverDeliveryReturn.return_state = confirmed` (with `confirmed_at` /
  `confirmed_by_user_id`).
- Sets `Order.status = canceled` and `assignment.status = canceled`.
- Releases the held reservation; `quantity_on_hand` is unchanged (no restock).
- Preserves the existing OrderAuditLog behavior.

## 5. Final State Machines

### Successful delivery path

```text
offer
  -> accept
  -> start                 (en_route_to_store)
  -> arrive-store          (arrived_at_store)
  -> pickup                (picked_up)
  -> depart-to-customer    (en_route_to_customer)
  -> arrive-customer       (arrived_at_customer)
  -> verify-age (pass)     (id_verified)
  -> proof                 (id_verified, record-only)
  -> complete              (delivery_completed)
  -> Order.status delivered (via orders authority)
```

### Failed / return path

```text
picked_up | en_route_to_customer | arrived_at_customer
        | id_verification_pending | id_verified
  -> fail                     (delivery_failed)
  -> return-to-store start    (returning_to_store; return_state=returning)
  -> return-to-store arrive   (returned_to_store;
                               return_state=returned_pending_confirmation)
  -> confirm-driver-return    (return_state=confirmed)
  -> Order.status canceled
  -> assignment canceled
  -> reservation released (quantity_on_hand unchanged, no restock)
```

## 6. Storage / Models Added

Dr.1.2.B compliance storage tables:

- `driver_delivery_verifications`
- `driver_delivery_proofs`
- `driver_delivery_failures`
- `driver_delivery_returns`

Dr.1.2.I.b idempotency ledger table:

- `driver_compliance_idempotency_keys`

The idempotency ledger table records one claim per
`(store_id, action, idempotency_key)`:

- The `Idempotency-Key` is optional; a claim row exists only when a caller
  supplies the header.
- `UNIQUE(store_id, action, idempotency_key)` enforces per-store, per-action
  key uniqueness.
- `request_hash` is a 64-character SHA-256 digest of the action plus the
  validated request body.
- `response_ref_id` stores the id of the canonical record to reload on replay.
- `response_status_code` stores the recorded status (200).
- `state` is one of `pending` / `completed`.
- No raw request payload is stored.
- No response body is stored.

## 7. Redaction / Sensitive Data Policy

Dr.1.2 does not store any of the following:

- raw ID data
- date of birth or license numbers
- ID photos
- proof photos
- signatures
- OCR or barcode data
- customer PII
- raw request payloads
- raw response bodies
- tokens or headers
- exact sensitive location fields (for example latitude / longitude)

The `note` field on the verify-age and proof requests
(`DriverVerifyAgeRequest.note`, `DriverProofSubmitRequest.note`) is capped at
500 characters.

The operational-audit `before` / `after` allow-list is restricted to:

- `status`
- `state`
- `return_state`
- `reason_code`
- `outcome`

## 8. Audit Architecture

- The existing `operational_audit_logs` table is reused; no new audit table
  was introduced.
- A `delivery_assignment` target type was added to the operational-audit
  taxonomy.
- The seven `delivery_assignment` actions are:
  - `delivery_verified`
  - `delivery_proof_recorded`
  - `delivery_completed`
  - `delivery_failed`
  - `delivery_return_started`
  - `delivery_return_arrived`
  - `delivery_return_confirmed`
- Audit writes are non-committing and transaction-scoped: the audit helper
  only appends to the session, and the row commits (or rolls back) atomically
  with the business mutation it records.
- OrderAuditLog remains the orders authority's record for commercial outcomes
  (delivered / canceled). It is not replaced by the operational audit trail.

## 9. Idempotency Architecture

- `Idempotency-Key` is optional on all six covered actions.
- With no header, the action keeps its existing state-inferred behavior and
  writes no ledger row.
- With a header present, the ledger is used.
- Invalid / empty / whitespace-only / too-long / malformed key: 400.
- Same key + same payload + same scope: 200 replay.
- Same key + different payload: 409.
- Same key + different scope (actor / order / assignment): 409.
- Pending key (claim still in progress): 409.
- Replay reloads the canonical record from `response_ref_id` and re-serializes
  it through the existing read model.
- Replay does not re-run the business mutation and produces no duplicate side
  effects (no duplicate compliance record, no duplicate operational-audit row,
  no duplicate OrderAuditLog, no second inventory consume or release).

Covered actions:

- verify-age
- proof
- complete
- fail
- return-to-store
- confirm-driver-return

## 10. Authority Boundaries

- The driver service does not directly write Order.status.
- The driver service does not directly mutate inventory.
- complete uses the orders authority bridge to promote the order and consume
  inventory.
- confirm-driver-return lives in the orders router and service, not the driver
  service.
- Inventory consume and reservation release go through the existing
  orders/inventory authority.
- The driver never confirms returns; the store confirmation
  (confirm-driver-return) controls the physical return resolution and the
  commercial cancellation.

## 11. Final Validation Results

Final validation was performed in Dr.1.2.I.d against the local test database
at migration head `d4e8b2c1f3a7`.

Focused test files:

- `test_dr12i_redaction_and_taxonomy.py`: 15 passed
- `test_dr12i_compliance_audit_wiring.py`: 9 passed
- `test_compliance_idempotency.py`: 27 passed
- `test_orders_confirm_driver_return_idempotency.py`: 13 passed
- `test_driver_compliance_idempotency.py`: 28 passed

Targeted selections:

- `operational_audit`: 31 passed
- `confirm_driver_return or compliance_idempotency`: 99 passed
- `verify_age or proof`: 123 passed
- `order or inventory`: 814 passed
- `driver`: 985 passed

Full suite:

- `pytest -q`: 3676 passed, 3 skipped
  (the 3 skips are RLS environment-gated tests that run only under
  `RLS_ACTIVE_CI=1`)

Migrations:

- Alembic head / current: `d4e8b2c1f3a7`
- upgrade head -> downgrade -1 -> upgrade head: passed (the idempotency table
  is dropped on downgrade and recreated cleanly on upgrade)

GitHub Actions CI was green (frontend, backend-unit, rls-active) for:

- `f935548` (I.a)
- `2af9943` (I.b)
- `e2f4e90` (I.c)

## 12. What Dr.1.2 Did Not Implement

The following were intentionally out of scope for Dr.1.2:

- Flutter / mobile app
- driver UI
- customer UI
- store UI for return confirmation
- payment / refund automation
- delivery re-attempt flow
- TTL cleanup job for the idempotency `expires_at`
- unified audit feed integration for `operational_audit_logs`
- semantic PII detection / NLP in notes
- proof photo / signature uploads
- barcode / OCR ID parsing
- a real ID verification provider integration
- customer notifications
- route optimization / navigation
- earnings / payouts

## 13. Carry-forwards

The following items are carried forward. They are non-blocking for Dr.1.2
closure.

- `expires_at` exists on the idempotency ledger but there is no TTL cleanup
  runtime yet (non-blocking).
- The Supabase RLS migration for `driver_compliance_idempotency_keys`
  (`supabase/migrations/20260617120000_driver_compliance_idempotency_keys_rls.sql`)
  is present but is not wired into the CI rls-active job's hardcoded migration
  list. This follows the existing convention for prior RLS files and is
  non-blocking; the application role uses BYPASSRLS and the table is internal
  infrastructure (non-blocking).
- GitHub Actions emits Node.js 20 deprecation annotations for
  checkout / setup-node / setup-python actions. These are forced onto Node.js
  24 and do not fail the run (non-blocking).
- A fresh key on an already-finished action uses the preserved state-inferred
  replay path and does not persist a ledger row. This is intentional and
  idempotent (non-blocking).
- Per-store / per-action idempotency namespacing is intentional: the same key
  under a different store or a different action is a distinct claim, not a
  conflict (non-blocking).
- The future Flutter Driver App starts in Dr.1.3+ (non-blocking).

## 14. Dr.1.3+ Handoff

Dr.1.3+ can build the Flutter / mobile Driver App on top of the now-stable
backend surface:

- the existing driver profile, eligibility, and assignment endpoints
- the operational delivery flow (accept through arrive-customer)
- the compliance endpoints (verify-age, proof, complete, fail,
  return-to-store)
- the store-side confirm-driver-return endpoint
- optional `Idempotency-Key` support on all six compliance actions for safe
  client retries
- the documented authority boundaries (the mobile client never needs to write
  Order.status or inventory directly)

## 15. Closure Statement

Dr.1.2 is complete when:

- this closure document is committed
- final validation passes
- the closure commit is pushed
- CI is green on the closure SHA
- HEAD == origin/main
- the working tree is clean
