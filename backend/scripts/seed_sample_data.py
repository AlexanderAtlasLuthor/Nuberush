"""Seed realistic demo data so the dashboard surfaces have something
to render — safely, idempotently, and never against production.

F2.27.2 (staging seed) hardening
---------------------------------
This script is now CLI-guarded and entity-level idempotent:

  - ``--target local|staging`` is REQUIRED for any write. ``production`` /
    ``prod`` / ``live`` / ``main-prod`` are hard-rejected — F2.27.2 never
    seeds production.
  - ``--dry-run`` plans every find-or-create but rolls back at the end, so
    nothing is committed. A missing ``--target`` is allowed ONLY in
    ``--dry-run`` (a safe, write-free preview).
  - Idempotency no longer relies on the single ``admin@nuberush.dev``
    sentinel. Every seed-owned row is found-or-created on a stable identity
    (store code, user email, product name, variant SKU, store+variant
    inventory, store+idempotency-key order, …), so a second run — or a run
    that completes a partially-seeded DB — never duplicates data.
  - A single commit happens at the very end of a real run; any error rolls
    the whole thing back. No secrets are read or printed.

Usage::

    cd backend

    # write-free preview (no --target needed in dry-run)
    DATABASE_URL=... python -m scripts.seed_sample_data --dry-run

    # seed a local dev database
    DATABASE_URL=... python -m scripts.seed_sample_data --target local

    # seed a Supabase staging database (see docs/f2.27-staging-runbook.md)
    DATABASE_URL=... python -m scripts.seed_sample_data --target staging

What you get:

  - 1 global admin (admin@nuberush.dev)
  - 2 stores ("Demo Downtown" / "Demo Uptown"), both active
  - Per store: owner, manager, 2 staff, 1 driver — all
    `<role>@<store-code>.nuberush.dev`
  - 20 products across 4 categories with a mix of compliance statuses
    (allowed / restricted / banned) so the compliance widgets light up
  - 1–2 variants per product (deterministic SKUs)
  - Per store: ~30 inventory items (~7 low-stock, 3 depleted)
  - Per store: ~25 orders across every OrderStatus (a couple backdated so
    the aging_order alert lights up)
  - Per store: ~12 inventory log rows + one creation order-audit row per
    seeded order
  - A small set of metadata-only product images (no Supabase Storage call)
  - A minimal manual regulatory fixture (source → notice → match → alert →
    decision audit) so the Admin Regulatory surface has data to render

Authentication (F2.22.2.G3):

Seeded users are `public.users` app records only — they carry role,
store and is_active, but no credentials. NubeRush authenticates
exclusively through Supabase Auth, and these rows ship with
`auth_user_id = NULL`, so **they cannot sign in until a Supabase
identity is provisioned and the mapping is backfilled** with
`scripts/backfill_supabase_auth_users.py`. See
docs/f2.27-staging-runbook.md for the full staging sequence.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

# Allow `python -m scripts.seed_sample_data` from backend/ and
# `python scripts/seed_sample_data.py` from anywhere by ensuring the
# backend/ directory is on sys.path.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductImage
from app.db.models import ProductVariant
from app.db.models import RegulatoryDecisionAuditLog
from app.db.models import RegulatoryMatchStrategy
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryNoticeType
from app.db.models import RegulatoryProductMatch
from app.db.models import RegulatorySource
from app.db.models import RegulatorySourceKind
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.db.session import get_session_factory
from app.services.regulatory import compute_regulatory_notice_content_hash


ADMIN_EMAIL = "admin@nuberush.dev"

STORES = [
    {"code": "demo-a", "name": "Demo Downtown", "timezone": "America/New_York"},
    {"code": "demo-b", "name": "Demo Uptown", "timezone": "America/New_York"},
]

CATEGORIES = ["vape", "edible", "accessory", "concentrate"]

# Subset of product names that get a metadata-only product image fixture.
_IMAGE_PRODUCT_NAMES = [
    "Lumen Vape 350mAh",
    "Solace Gummies 10mg",
    "Drift Rolling Tray",
    "Apex Live Resin 1g",
]

# Manual regulatory fixture identity (stable across runs).
_REG_SOURCE_NAME = "NubeRush Demo Manual Source"
# The product the fixture's notice/match/alert is built around. Restricted
# (not banned) so the fixture never implies an auto-hold/ban.
_REG_PRODUCT_NAME = "Nightshade Cart 1g"


# --------------------------------------------------------------------- #
# CLI target validation
# --------------------------------------------------------------------- #


class SeedTargetError(Exception):
    """Raised when an unsupported / unsafe seed target is requested."""


_ALLOWED_TARGETS = {"local", "staging"}
# Any value that looks like production is hard-rejected in F2.27.2.
_BLOCKED_TARGETS = {
    "production",
    "prod",
    "live",
    "main-prod",
    "main_prod",
    "prod-main",
}


def validate_target(target: str | None, *, dry_run: bool) -> str | None:
    """Resolve and validate the requested seed target.

    Rules:
      - production-like targets are ALWAYS rejected (even in dry-run);
      - a real (write) run REQUIRES ``local`` or ``staging``;
      - ``--dry-run`` with no target is allowed (a write-free preview);
      - any other value is rejected.
    """
    normalized = target.strip().lower() if target is not None else None

    if normalized in _BLOCKED_TARGETS:
        raise SeedTargetError(
            f"Target '{target}' is not supported. F2.27.2 never seeds "
            "production — use --target local or --target staging."
        )

    if normalized is None:
        if dry_run:
            return None
        raise SeedTargetError(
            "A target is required for writes. Pass --target local or "
            "--target staging (or run with --dry-run for a write-free "
            "preview)."
        )

    if normalized not in _ALLOWED_TARGETS:
        raise SeedTargetError(
            f"Unknown target '{target}'. Valid targets: "
            f"{', '.join(sorted(_ALLOWED_TARGETS))}."
        )

    return normalized


# --------------------------------------------------------------------- #
# Summary tracking
# --------------------------------------------------------------------- #


@dataclass
class EntityCount:
    created: int = 0
    existing: int = 0


@dataclass
class SeedSummary:
    target: str | None
    dry_run: bool
    counts: dict[str, EntityCount] = field(default_factory=dict)

    # Entities reported even when zero, so the summary shape is stable.
    _TRACKED = (
        "stores",
        "users",
        "products",
        "variants",
        "inventory",
        "inventory_logs",
        "orders",
        "order_items",
        "order_audit_logs",
        "product_images",
        "regulatory_sources",
        "regulatory_notices",
        "regulatory_matches",
        "compliance_alerts",
        "regulatory_decision_audit_logs",
    )

    def __post_init__(self) -> None:
        for name in self._TRACKED:
            self.counts.setdefault(name, EntityCount())

    def record(self, entity: str, *, created: bool, n: int = 1) -> None:
        bucket = self.counts.setdefault(entity, EntityCount())
        if created:
            bucket.created += n
        else:
            bucket.existing += n

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "dry_run": self.dry_run,
            "entities": {
                name: {"created": c.created, "existing": c.existing}
                for name, c in self.counts.items()
            },
        }


# --------------------------------------------------------------------- #
# Generic find-or-create
# --------------------------------------------------------------------- #


def _find_or_create(
    db: Session,
    model: type,
    *,
    defaults: dict | None = None,
    **identity,
) -> tuple[object, bool]:
    """Return ``(instance, created)`` matching ``identity``.

    Existing rows are returned untouched (no field updates), so a rerun is a
    no-op. New rows are built from ``identity + defaults`` and flushed so
    their server-generated ids are available to dependent inserts.
    """
    instance = db.scalar(select(model).filter_by(**identity))
    if instance is not None:
        return instance, False
    params = {**identity, **(defaults or {})}
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True


# --------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------- #


def _seed_admin(db: Session, summary: SeedSummary) -> User:
    admin, created = _find_or_create(
        db,
        User,
        email=ADMIN_EMAIL,
        defaults={
            "full_name": "NubeRush Admin",
            "role": UserRole.admin,
            "store_id": None,
            "is_active": True,
        },
    )
    summary.record("users", created=created)
    return admin  # type: ignore[return-value]


def _seed_store_users(
    db: Session, store: Store, summary: SeedSummary
) -> User:
    """Find-or-create the per-store role users; return the owner."""
    plan = [
        (UserRole.owner, "owner", f"{store.name} Owner"),
        (UserRole.manager, "manager", f"{store.name} Manager"),
        (UserRole.staff, "staff1", f"{store.name} Staff One"),
        (UserRole.staff, "staff2", f"{store.name} Staff Two"),
        (UserRole.driver, "driver", f"{store.name} Driver"),
    ]
    owner: User | None = None
    for role, local_part, full_name in plan:
        user, created = _find_or_create(
            db,
            User,
            email=f"{local_part}@{store.code}.nuberush.dev",
            defaults={
                "full_name": full_name,
                "role": role,
                "store_id": store.id,
                "is_active": True,
            },
        )
        summary.record("users", created=created)
        if role == UserRole.owner:
            owner = user  # type: ignore[assignment]
    assert owner is not None
    return owner


def _seed_products(db: Session, summary: SeedSummary) -> list[Product]:
    """20 products, mix of compliance + active flags. Found-or-created
    on (name, category)."""
    products: list[Product] = []
    catalog = [
        ("Lumen Vape 350mAh", "vape", ComplianceStatus.allowed, True),
        ("Lumen Vape 500mAh", "vape", ComplianceStatus.allowed, True),
        ("Lumen Vape XL", "vape", ComplianceStatus.allowed, True),
        ("Nightshade Cart 1g", "vape", ComplianceStatus.restricted, True),
        ("Nightshade Cart 2g", "vape", ComplianceStatus.restricted, True),
        ("Cinder Disposable", "vape", ComplianceStatus.allowed, True),
        ("Cinder Pro Disposable", "vape", ComplianceStatus.allowed, True),
        ("Solace Gummies 10mg", "edible", ComplianceStatus.allowed, True),
        ("Solace Gummies 25mg", "edible", ComplianceStatus.allowed, True),
        ("Solace Chocolate Bar", "edible", ComplianceStatus.allowed, True),
        ("Hex Caramel 50mg", "edible", ComplianceStatus.restricted, True),
        ("Hex Brownie 100mg", "edible", ComplianceStatus.banned, False),
        ("PolarMint Lozenge", "edible", ComplianceStatus.allowed, True),
        ("Drift Rolling Tray", "accessory", ComplianceStatus.allowed, True),
        ("Drift Grinder", "accessory", ComplianceStatus.allowed, True),
        ("Drift Storage Jar", "accessory", ComplianceStatus.allowed, True),
        ("Drift Lighter Set", "accessory", ComplianceStatus.allowed, True),
        ("Apex Shatter 1g", "concentrate", ComplianceStatus.restricted, True),
        ("Apex Live Resin 1g", "concentrate", ComplianceStatus.allowed, True),
        ("Apex Distillate 5g", "concentrate", ComplianceStatus.banned, False),
    ]
    for name, category, compliance, allowed in catalog:
        product, created = _find_or_create(
            db,
            Product,
            name=name,
            category=category,
            defaults={
                "brand": "NubeRush Demo",
                "description": (
                    f"Demo {category} — seeded for dashboard preview."
                ),
                "compliance_status": compliance,
                "allowed_for_sale": allowed,
                "is_active": True,
                "jurisdiction": "FL",
            },
        )
        summary.record("products", created=created)
        products.append(product)  # type: ignore[arg-type]
    return products


def _seed_variants(
    db: Session, products: list[Product], summary: SeedSummary
) -> list[ProductVariant]:
    """1–2 variants per product, found-or-created on a deterministic SKU.

    A LOCAL rng (re-seeded each call) keeps the secondary-variant decision
    and the priced fields identical across repeated in-process runs, so the
    second run never invents a new SKU.
    """
    rng = random.Random("nuberush-seed-variants")
    variants: list[ProductVariant] = []
    for product in products:
        sku = f"SKU-{product.id.hex[:8].upper()}"
        primary, created = _find_or_create(
            db,
            ProductVariant,
            sku=sku,
            defaults={
                "product_id": product.id,
                "barcode": f"BC{product.id.hex[:10].upper()}",
                "flavor": rng.choice(
                    ["Original", "Mint", "Berry", "Citrus", "Mango"]
                ),
                "price": Decimal(str(round(rng.uniform(8, 60), 2))),
                "cost": Decimal(str(round(rng.uniform(3, 25), 2))),
                "is_active": True,
            },
        )
        summary.record("variants", created=created)
        variants.append(primary)  # type: ignore[arg-type]
        # Half the products also get a second variant. The decision is taken
        # from the deterministic local rng so it is stable across reruns.
        wants_secondary = rng.random() < 0.5
        secondary_price = Decimal(str(round(rng.uniform(15, 90), 2)))
        secondary_cost = Decimal(str(round(rng.uniform(8, 40), 2)))
        if wants_secondary:
            secondary, created = _find_or_create(
                db,
                ProductVariant,
                sku=f"{sku}-XL",
                defaults={
                    "product_id": product.id,
                    "barcode": f"BC{product.id.hex[:10].upper()}X",
                    "flavor": "Variant XL",
                    "size_label": "XL",
                    "price": secondary_price,
                    "cost": secondary_cost,
                    "is_active": True,
                },
            )
            summary.record("variants", created=created)
            variants.append(secondary)  # type: ignore[arg-type]
    return variants


def _seed_inventory(
    db: Session,
    store: Store,
    variants: list[ProductVariant],
    summary: SeedSummary,
) -> list[InventoryItem]:
    """~30 inventory items per store, found-or-created on (store, variant).

    Distribution on first create: 3 depleted, 7 low-stock, rest healthy.
    """
    items: list[InventoryItem] = []
    rng = random.Random(f"{store.code}-inventory")
    pool = list(variants)
    rng.shuffle(pool)
    selected = pool[:30]

    for index, variant in enumerate(selected):
        threshold = rng.choice([5, 10, 15, 20])
        if index < 3:
            on_hand = 0
        elif index < 10:
            on_hand = rng.randint(0, threshold)
        else:
            on_hand = rng.randint(threshold + 5, threshold + 80)
        reserved = rng.randint(0, on_hand // 3) if on_hand > 5 else 0
        item, created = _find_or_create(
            db,
            InventoryItem,
            store_id=store.id,
            variant_id=variant.id,
            defaults={
                "quantity_on_hand": on_hand,
                "quantity_reserved": reserved,
                "reorder_threshold": threshold,
                "status": InventoryStatus.available,
            },
        )
        summary.record("inventory", created=created)
        items.append(item)  # type: ignore[arg-type]
    return items


def _seed_inventory_logs(
    db: Session,
    store: Store,
    items: list[InventoryItem],
    actor: User,
    summary: SeedSummary,
) -> None:
    """~12 inventory log rows per store. Append-only with no natural key,
    so idempotency is store-scoped: if the store already has seed logs we
    skip rather than pile on duplicates."""
    existing = db.scalar(
        select(func.count())
        .select_from(InventoryLog)
        .where(InventoryLog.store_id == store.id)
    ) or 0
    if existing:
        summary.record("inventory_logs", created=False, n=existing)
        return

    rng = random.Random(f"{store.code}-logs")
    now = datetime.now(UTC)
    movement_pool = [
        InventoryMovementType.receipt,
        InventoryMovementType.adjustment,
        InventoryMovementType.sale,
        InventoryMovementType.return_,
        InventoryMovementType.damage,
    ]
    for offset_minutes in range(12):
        item = rng.choice(items)
        movement = rng.choice(movement_pool)
        if movement == InventoryMovementType.receipt:
            delta = rng.randint(5, 40)
        elif movement == InventoryMovementType.sale:
            delta = -rng.randint(1, 5)
        elif movement == InventoryMovementType.damage:
            delta = -rng.randint(1, 3)
        elif movement == InventoryMovementType.return_:
            delta = rng.randint(1, 4)
        else:  # adjustment
            delta = rng.choice([-5, -3, -1, 1, 3, 5])
        quantity_after = max(0, item.quantity_on_hand + delta)
        log = InventoryLog(
            inventory_item_id=item.id,
            store_id=store.id,
            variant_id=item.variant_id,
            performed_by_user_id=actor.id,
            movement_type=movement,
            quantity_delta=delta if delta != 0 else 1,
            quantity_after=quantity_after,
            reason=rng.choice(
                [
                    "Routine count",
                    "Cycle count adjustment",
                    "Receipt from supplier",
                    "Sold at counter",
                    "Damaged in transit",
                    "Customer return",
                ]
            ),
        )
        db.add(log)
        db.flush()
        log.created_at = now - timedelta(
            hours=offset_minutes * 3, minutes=rng.randint(0, 30)
        )
        summary.record("inventory_logs", created=True)
    db.flush()


def _seed_orders(
    db: Session,
    store: Store,
    items: list[InventoryItem],
    actor: User,
    summary: SeedSummary,
) -> None:
    """~25 orders per store, found-or-created on a DETERMINISTIC
    (store, idempotency_key). Each newly-created order also gets its line
    items and a single 'created' order-audit row."""
    rng = random.Random(f"{store.code}-orders")
    plan = (
        [(OrderStatus.pending, True)] * 2
        + [(OrderStatus.pending, False)] * 3
        + [(OrderStatus.accepted, False)] * 3
        + [(OrderStatus.preparing, False)] * 3
        + [(OrderStatus.ready, False)] * 2
        + [(OrderStatus.out_for_delivery, False)] * 2
        + [(OrderStatus.delivered, False)] * 6
        + [(OrderStatus.canceled, False)] * 3
        + [(OrderStatus.returned, False)] * 1
    )
    now = datetime.now(UTC)
    sellable_items = [i for i in items if i.quantity_on_hand > 0]
    if not sellable_items:
        sellable_items = items  # fallback so seed never empties

    for idx, (order_status, is_aging) in enumerate(plan):
        line_count = rng.randint(1, 3)
        chosen_items = rng.sample(
            sellable_items, k=min(line_count, len(sellable_items))
        )
        order, created = _find_or_create(
            db,
            Order,
            store_id=store.id,
            idempotency_key=f"seed-{store.code}-{idx}",
            defaults={
                "status": order_status,
                "subtotal_amount": Decimal("0.00"),
                "tax_amount": Decimal("0.00"),
                "total_amount": Decimal("0.00"),
            },
        )
        summary.record("orders", created=created)
        if not created:
            # Existing order — count its persisted line items and move on.
            existing_lines = db.scalar(
                select(func.count())
                .select_from(OrderItem)
                .where(OrderItem.order_id == order.id)
            ) or 0
            summary.record("order_items", created=False, n=existing_lines)
            _seed_order_audit(db, order, actor, summary)
            continue

        subtotal = Decimal("0.00")
        for item in chosen_items:
            qty = rng.randint(1, 3)
            unit_price = item.variant.price
            line_total = (unit_price * qty).quantize(Decimal("0.01"))
            db.add(
                OrderItem(
                    order_id=order.id,
                    variant_id=item.variant_id,
                    inventory_item_id=item.id,
                    quantity=qty,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )
            summary.record("order_items", created=True)
            subtotal += line_total
        tax = (subtotal * Decimal("0.07")).quantize(Decimal("0.01"))
        order.subtotal_amount = subtotal
        order.tax_amount = tax
        order.total_amount = subtotal + tax
        # Lifecycle timestamps for completed orders.
        if order_status == OrderStatus.accepted:
            order.accepted_at = now - timedelta(minutes=20)
        elif order_status in (
            OrderStatus.preparing,
            OrderStatus.ready,
            OrderStatus.out_for_delivery,
        ):
            order.accepted_at = now - timedelta(minutes=40)
        elif order_status == OrderStatus.delivered:
            order.accepted_at = now - timedelta(hours=4)
            order.delivered_at = now - timedelta(hours=1)
        elif order_status == OrderStatus.canceled:
            order.canceled_at = now - timedelta(hours=2)
            order.cancel_reason = "Demo cancellation"
        elif order_status == OrderStatus.returned:
            order.accepted_at = now - timedelta(hours=8)
            order.delivered_at = now - timedelta(hours=6)
            order.returned_at = now - timedelta(hours=3)
        if is_aging:
            order.created_at = now - timedelta(hours=3)
        else:
            order.created_at = now - timedelta(
                minutes=rng.randint(5, 60 * 24)
            )
        db.flush()
        _seed_order_audit(db, order, actor, summary)


def _seed_order_audit(
    db: Session, order: Order, actor: User, summary: SeedSummary
) -> None:
    """One 'created' audit row per order. Append-only, so idempotency is
    order-scoped: skip if the order already has any audit row."""
    existing = db.scalar(
        select(func.count())
        .select_from(OrderAuditLog)
        .where(OrderAuditLog.order_id == order.id)
    ) or 0
    if existing:
        summary.record("order_audit_logs", created=False, n=existing)
        return
    db.add(
        OrderAuditLog(
            order_id=order.id,
            store_id=order.store_id,
            performed_by_user_id=actor.id,
            previous_status=None,
            new_status=order.status,
            action="created",
            reason="Seeded demo order",
        )
    )
    summary.record("order_audit_logs", created=True)
    db.flush()


def _seed_product_images(
    db: Session,
    products: list[Product],
    uploader: User,
    summary: SeedSummary,
) -> None:
    """Metadata-only product images for a small subset of products.

    NO Supabase Storage call, no real object upload, no service-role key —
    just a deterministic ``object_key`` row so the image-metadata surface
    has something to render. Real object upload is a manual staging step
    (see docs/f2.27-staging-runbook.md). Idempotent on product_id (unique).
    """
    by_name = {p.name: p for p in products}
    for name in _IMAGE_PRODUCT_NAMES:
        product = by_name.get(name)
        if product is None:
            continue
        slug = name.lower().replace(" ", "-")
        _, created = _find_or_create(
            db,
            ProductImage,
            product_id=product.id,
            defaults={
                "object_key": f"products/demo/{slug}.jpg",
                "uploaded_by_user_id": uploader.id,
            },
        )
        summary.record("product_images", created=created)


def _seed_regulatory_fixture(
    db: Session,
    products: list[Product],
    admin: User,
    summary: SeedSummary,
) -> None:
    """Minimal MANUAL regulatory fixture for the Admin Regulatory smoke.

    Direct DB inserts only (the regulatory service functions commit
    internally, which would break this script's single-commit / dry-run
    contract). Constraints, enums and the notice content_hash are preserved
    — the hash is computed with the real
    ``compute_regulatory_notice_content_hash`` so it matches what ingestion
    would produce. Fully idempotent, advisory-only: no hold / ban / block
    is applied and no product is mutated.
    """
    product = next(
        (p for p in products if p.name == _REG_PRODUCT_NAME), None
    )
    if product is None:
        return

    # 1. Source — unique on name.
    source, created = _find_or_create(
        db,
        RegulatorySource,
        name=_REG_SOURCE_NAME,
        defaults={
            "kind": RegulatorySourceKind.manual,
            "reference_url": None,
            "is_active": True,
        },
    )
    summary.record("regulatory_sources", created=created)

    # 2. Notice — unique on (source_id, content_hash). Build the payload as
    #    a single-product list so detection-shaped consumers see it, then
    #    compute the canonical hash exactly as the service would.
    notice_type = RegulatoryNoticeType.manual_snapshot
    title = "Demo manual advisory — staging fixture"
    external_ref = "DEMO-REG-0001"
    payload = {
        "products": [
            {
                "product_name": product.name,
                "brand": product.brand,
                "category": product.category,
                "note": "Seeded manual fixture for staging smoke only.",
            }
        ]
    }
    content_hash = compute_regulatory_notice_content_hash(
        notice_type=notice_type,
        title=title,
        external_ref=external_ref,
        published_at=None,
        payload=payload,
    )
    notice, created = _find_or_create(
        db,
        RegulatoryNotice,
        source_id=source.id,
        content_hash=content_hash,
        defaults={
            "external_ref": external_ref,
            "title": title,
            "notice_type": notice_type,
            "published_at": None,
            "payload": payload,
        },
    )
    summary.record("regulatory_notices", created=created)

    # 3. Match — unique on (notice_id, product_id, variant_id, strategy).
    match, created = _find_or_create(
        db,
        RegulatoryProductMatch,
        notice_id=notice.id,
        product_id=product.id,
        variant_id=None,
        match_strategy=RegulatoryMatchStrategy.name,
        defaults={
            "confidence": Decimal("0.90"),
            "matched_fields": {"product_name": product.name},
        },
    )
    summary.record("regulatory_matches", created=created)

    # 4. Alert — no natural unique key; scope idempotency to
    #    (notice_id, product_id, match_id). Advisory recommendation only.
    alert = db.scalar(
        select(ComplianceAlert).where(
            ComplianceAlert.notice_id == notice.id,
            ComplianceAlert.product_id == product.id,
            ComplianceAlert.match_id == match.id,
        )
    )
    alert_created = alert is None
    if alert is None:
        alert = ComplianceAlert(
            notice_id=notice.id,
            product_id=product.id,
            match_id=match.id,
            severity=ComplianceAlertSeverity.medium,
            status=ComplianceAlertStatus.acknowledged,
            recommended_action=ComplianceRecommendedAction.hold,
            resolution_note=None,
        )
        db.add(alert)
        db.flush()
    summary.record("compliance_alerts", created=alert_created)

    # 5. Decision audit — append-only; scope idempotency to (alert_id,
    #    action). Documents the seeded acknowledgement so the decision-trail
    #    panel has a row. No product mutation accompanies it.
    _, created = _find_or_create(
        db,
        RegulatoryDecisionAuditLog,
        alert_id=alert.id,
        action="acknowledged",
        defaults={
            "notice_id": notice.id,
            "product_id": product.id,
            "actor_user_id": admin.id,
            "before": {"status": ComplianceAlertStatus.open.value},
            "after": {"status": ComplianceAlertStatus.acknowledged.value},
            "event_metadata": {"source": "seed_sample_data"},
            "reason": "Seeded acknowledgement for staging regulatory smoke.",
        },
    )
    summary.record("regulatory_decision_audit_logs", created=created)


# --------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------- #


def run_seed(
    db: Session, *, target: str | None, dry_run: bool
) -> SeedSummary:
    """Plan-and-apply the full seed inside a single transaction.

    Every entity is found-or-created (idempotent). In ``--dry-run`` the
    transaction is rolled back so nothing is committed; otherwise a single
    commit lands at the end. Any exception rolls everything back.
    """
    resolved = validate_target(target, dry_run=dry_run)
    summary = SeedSummary(target=resolved, dry_run=dry_run)

    try:
        admin = _seed_admin(db, summary)
        products = _seed_products(db, summary)
        variants = _seed_variants(db, products, summary)

        for store_def in STORES:
            store, created = _find_or_create(
                db,
                Store,
                code=store_def["code"],
                defaults={
                    "name": store_def["name"],
                    "timezone": store_def["timezone"],
                    "is_active": True,
                },
            )
            summary.record("stores", created=created)
            owner = _seed_store_users(db, store, summary)  # type: ignore[arg-type]
            items = _seed_inventory(db, store, variants, summary)  # type: ignore[arg-type]
            _seed_inventory_logs(db, store, items, owner, summary)  # type: ignore[arg-type]
            _seed_orders(db, store, items, owner, summary)  # type: ignore[arg-type]

        _seed_product_images(db, products, admin, summary)
        _seed_regulatory_fixture(db, products, admin, summary)

        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise

    return summary


def _print_summary(summary: SeedSummary) -> None:
    mode = "DRY-RUN (no writes committed)" if summary.dry_run else "APPLIED"
    print()
    print(f"Seed summary — target={summary.target or 'none'} — {mode}")
    print(f"  {'entity':<32} {'created':>8} {'existing':>9}")
    for name in SeedSummary._TRACKED:
        c = summary.counts[name]
        print(f"  {name:<32} {c.created:>8} {c.existing:>9}")
    print()
    if summary.dry_run:
        print(
            "DRY-RUN — nothing was committed. Re-run with --target "
            "local|staging to apply."
        )
    else:
        print("✅ Seed complete.")
        print(
            "\nAccounts are app records only (auth_user_id NULL). Provision "
            "Supabase identities and run\n"
            "    python -m scripts.backfill_supabase_auth_users --apply ...\n"
            "to make them login-capable. See docs/f2.27-staging-runbook.md."
        )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seed demo data idempotently. --target local|staging is "
            "required for writes; --dry-run previews without committing. "
            "Production targets are rejected."
        )
    )
    parser.add_argument(
        "--target",
        default=None,
        help=(
            "Destination environment: 'local' or 'staging'. Required for a "
            "real run. Production-like values are rejected."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Plan the seed and roll back without committing. Allowed with "
            "no --target."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if "DATABASE_URL" not in os.environ:
        print(
            "❌ DATABASE_URL is not set. "
            "Point it at your target Postgres before running.",
            file=sys.stderr,
        )
        return 1

    try:
        validate_target(args.target, dry_run=args.dry_run)
    except SeedTargetError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    session_factory = get_session_factory()
    with session_factory() as db:
        summary = run_seed(db, target=args.target, dry_run=args.dry_run)
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
