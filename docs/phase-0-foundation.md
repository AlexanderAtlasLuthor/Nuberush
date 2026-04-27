# NubeRush — Phase 0 (Foundation) — CLOSED

## Overview

Phase 0 establishes the **business model and core system rules** before any implementation.

Its purpose is to eliminate ambiguity and prevent structural errors in later phases (inventory, orders, compliance, RBAC).

---

## Business Model

**Selected Model:** SaaS + Marketplace Hybrid

### Interpretation

- Each store uses NubeRush as a SaaS platform
- The system can evolve into a marketplace connecting stores and customers

### Initial Monetization

- $0 monthly (adoption phase)
- % fee per delivery/order

### Planned Evolution

- Monthly SaaS subscription
- Reduced transaction fees

---

## Core System Rules

These rules are **non-negotiable and enforced at the backend level**.

### 1. Sales Rule

- Every sale **must** reduce inventory
- No "informational" sales exist
- If stock is insufficient → transaction fails

---

### 2. Compliance Rule

Allowed states:

- `allowed`
- `restricted`
- `banned`

Rules:

- `banned` → cannot be sold
- `restricted` → reserved for future logic
- `allowed` → normal sale

---

### 3. Roles

System roles:

- `admin` (global)
- `owner`
- `manager`
- `staff`
- `driver`

### Role Interpretation

- `admin` → full global control
- `owner` → full store control
- `manager` → operational control
- `staff` → limited operational access
- `driver` → delivery/logistics

---

## Architectural Decisions

### 1. Tenancy Model

- `store` is the unit of isolation
- No organizations (intentionally excluded for MVP)
- All operational data is scoped by `store_id`

---

### 2. Data Model Separation

- Products → global
- Inventory → per store
- Orders → per store
- Users → per store (except admin)

---

### 3. Security Principles

- The frontend **does not assign roles**
- The frontend **does not control store_id**
- All critical decisions are enforced in the backend

---

## MVP Assumptions

The MVP intentionally excludes:

- Full marketplace functionality
- Advanced compliance automation
- Delivery optimization systems
- Multi-organization structures
- Payment integration

---

## Out of Scope (Phase 0)

- Pricing finalization
- Stripe/payment systems
- Regulatory integrations
- Age verification flows
- Analytics
- Multi-tenant enterprise features

---

## Completion Criteria

Phase 0 is considered complete when:

- Business model is defined
- Core system rules are defined
- Roles are defined
- Tenancy model is defined
- Data separation is defined
- Security boundaries are defined

---

## Status

**Phase 0 — COMPLETED**

- Business logic defined
- System rules established
- Architectural decisions locked

---

## Impact on Next Phases

These decisions directly affect:

- Inventory system (sales rule)
- Product system (compliance)
- RBAC (roles)
- Security model (backend enforcement)
- Multi-tenancy (store isolation)

---

## Next Step

Proceed to:

**Phase 1 — Core Backend (Completed)**
**Next Active Work: Product System**
