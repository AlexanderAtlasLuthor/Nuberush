"""Seed realistic demo data so the dashboard surfaces have something
to render.

Idempotent: re-running detects the sentinel admin email and exits
without duplicating rows. To re-seed from scratch, drop and re-create
the DB (or `alembic downgrade base && alembic upgrade head`) first.

Usage:

    cd backend
    DATABASE_URL=postgresql+psycopg://nuberush:nuberush@127.0.0.1:5432/nuberush \\
        python -m scripts.seed_sample_data

What you get:

  - 1 global admin (admin@nuberush.dev / password123)
  - 2 stores ("Demo Downtown" / "Demo Uptown"), both active
  - Per store: owner, manager, 2 staff, 1 driver — all
    `<role>@<store-code>.nuberush.dev` with password123
  - 20 products across 4 categories with a mix of compliance statuses
    (allowed / restricted / banned) so the compliance widgets light up
  - 1–2 variants per product (40 variants total)
  - Per store: ~30 inventory items, ~7 of them low-stock so the
    low-stock widget + alerts surface real rows
  - Per store: ~25 orders distributed across every OrderStatus so the
    "by_status" histogram is dense; a couple of pending orders are
    backdated 2h so the aging_order alert lights up
  - Per store: ~12 inventory log rows so recent_activity is non-empty

Login (every account):

    password: password123
"""

from __future__ import annotations

import os
import random
import sys
import uuid
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


from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import Order
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.db.session import get_session_factory


PASSWORD = "password123"
ADMIN_EMAIL = "admin@nuberush.dev"

STORES = [
    {"code": "demo-a", "name": "Demo Downtown", "timezone": "America/New_York"},
    {"code": "demo-b", "name": "Demo Uptown", "timezone": "America/New_York"},
]

CATEGORIES = ["vape", "edible", "accessory", "concentrate"]

# Deterministic seed so re-runs produce identical histograms /
# distributions (helpful when comparing screenshots).
random.seed(20260514)


# --------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------- #


def _make_user(
    db: Session,
    *,
    role: UserRole,
    email: str,
    full_name: str,
    store: Store | None,
    password_hash: str,
) -> User:
    user = User(
        full_name=full_name,
        email=email,
        password_hash=password_hash,
        role=role,
        store_id=store.id if store is not None else None,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_store(db: Session, *, code: str, name: str, timezone: str) -> Store:
    store = Store(
        name=name,
        code=code,
        is_active=True,
        timezone=timezone,
    )
    db.add(store)
    db.flush()
    return store


def _seed_products(db: Session) -> list[Product]:
    """20 products, mix of compliance + active flags."""
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
        product = Product(
            name=name,
            brand="NubeRush Demo",
            category=category,
            description=f"Demo {category} — seeded for dashboard preview.",
            compliance_status=compliance,
            allowed_for_sale=allowed,
            is_active=True,
            jurisdiction="FL",
        )
        db.add(product)
        products.append(product)
    db.flush()
    return products


def _seed_variants(
    db: Session, products: list[Product]
) -> list[ProductVariant]:
    """1–2 variants per product, all priced."""
    variants: list[ProductVariant] = []
    for product in products:
        primary = ProductVariant(
            product_id=product.id,
            sku=f"SKU-{product.id.hex[:8].upper()}",
            barcode=f"BC{product.id.hex[:10].upper()}",
            flavor=random.choice(
                ["Original", "Mint", "Berry", "Citrus", "Mango"]
            ),
            price=Decimal(str(round(random.uniform(8, 60), 2))),
            cost=Decimal(str(round(random.uniform(3, 25), 2))),
            is_active=True,
        )
        db.add(primary)
        variants.append(primary)
        # Half the products also get a second variant so the catalog
        # has some breadth.
        if random.random() < 0.5:
            secondary = ProductVariant(
                product_id=product.id,
                sku=f"SKU-{product.id.hex[:8].upper()}-XL",
                barcode=f"BC{product.id.hex[:10].upper()}X",
                flavor="Variant XL",
                size_label="XL",
                price=Decimal(str(round(random.uniform(15, 90), 2))),
                cost=Decimal(str(round(random.uniform(8, 40), 2))),
                is_active=True,
            )
            db.add(secondary)
            variants.append(secondary)
    db.flush()
    return variants


def _seed_inventory(
    db: Session, store: Store, variants: list[ProductVariant]
) -> list[InventoryItem]:
    """~30 inventory items per store. Distribution:
      - 7 low-stock (on_hand <= threshold)
      - 3 fully depleted (on_hand == 0)
      - the rest healthy
    """
    items: list[InventoryItem] = []
    # Use a deterministic shuffle per store so the two stores don't
    # carry identical inventory.
    rng = random.Random(f"{store.code}-inventory")
    pool = list(variants)
    rng.shuffle(pool)
    selected = pool[:30]

    for index, variant in enumerate(selected):
        threshold = rng.choice([5, 10, 15, 20])
        if index < 3:
            # Depleted.
            on_hand = 0
        elif index < 10:
            # Low-stock.
            on_hand = rng.randint(0, threshold)
        else:
            # Healthy.
            on_hand = rng.randint(threshold + 5, threshold + 80)
        reserved = (
            rng.randint(0, on_hand // 3) if on_hand > 5 else 0
        )
        item = InventoryItem(
            store_id=store.id,
            variant_id=variant.id,
            quantity_on_hand=on_hand,
            quantity_reserved=reserved,
            reorder_threshold=threshold,
            status=InventoryStatus.available,
        )
        db.add(item)
        items.append(item)
    db.flush()
    return items


def _seed_inventory_logs(
    db: Session,
    store: Store,
    items: list[InventoryItem],
    actor: User,
) -> None:
    """~12 recent inventory log rows per store across mixed movement
    types. Timestamps span the past 5 days descending.
    """
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
        # Deltas: receipts +, sales/damage -, adjustments mixed.
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
        # quantity_after must be >= 0; clamp the simulated post-state.
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
        # Spread historically; newer rows first.
        db.flush()
        log.created_at = now - timedelta(
            hours=offset_minutes * 3, minutes=rng.randint(0, 30)
        )
    db.flush()


def _seed_orders(
    db: Session,
    store: Store,
    items: list[InventoryItem],
) -> None:
    """~25 orders per store with status mix that exercises the dense
    histogram + the aging_order alert.

    Status distribution per store:
      pending: 5 (2 of them backdated ~3h for aging_order alert)
      accepted: 3
      preparing: 3
      ready: 2
      out_for_delivery: 2
      delivered: 6
      canceled: 3
      returned: 1
    """
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
    # Filter to sellable items so order lines don't lie about totals.
    sellable_items = [
        i for i in items if i.quantity_on_hand > 0
    ]
    if not sellable_items:
        sellable_items = items  # fallback so seed never empties

    for idx, (order_status, is_aging) in enumerate(plan):
        # 1–3 line items per order.
        line_count = rng.randint(1, 3)
        chosen_items = rng.sample(
            sellable_items, k=min(line_count, len(sellable_items))
        )
        subtotal = Decimal("0.00")
        order = Order(
            store_id=store.id,
            idempotency_key=f"seed-{store.code}-{idx}-{uuid.uuid4().hex[:6]}",
            status=order_status,
            subtotal_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )
        db.add(order)
        db.flush()
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
            subtotal += line_total
        tax = (subtotal * Decimal("0.07")).quantize(Decimal("0.01"))
        order.subtotal_amount = subtotal
        order.tax_amount = tax
        order.total_amount = subtotal + tax
        # Lifecycle timestamps for completed orders so audit / list
        # endpoints have real dates to render.
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
        # Backdate aging orders so the aging_order alert lights up.
        if is_aging:
            order.created_at = now - timedelta(hours=3)
        else:
            order.created_at = now - timedelta(
                minutes=rng.randint(5, 60 * 24)
            )
        db.flush()


# --------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------- #


def seed(db: Session) -> None:
    if db.scalar(select(User).where(User.email == ADMIN_EMAIL)):
        print(
            f"⏩ Seed already applied (found {ADMIN_EMAIL}). "
            "Drop the DB and re-run to re-seed."
        )
        return

    print("🌱 Seeding demo data…")
    pw_hash = hash_password(PASSWORD)

    admin = _make_user(
        db,
        role=UserRole.admin,
        email=ADMIN_EMAIL,
        full_name="NubeRush Admin",
        store=None,
        password_hash=pw_hash,
    )

    products = _seed_products(db)
    variants = _seed_variants(db, products)

    for store_def in STORES:
        store = _make_store(
            db,
            code=store_def["code"],
            name=store_def["name"],
            timezone=store_def["timezone"],
        )
        owner = _make_user(
            db,
            role=UserRole.owner,
            email=f"owner@{store.code}.nuberush.dev",
            full_name=f"{store.name} Owner",
            store=store,
            password_hash=pw_hash,
        )
        _make_user(
            db,
            role=UserRole.manager,
            email=f"manager@{store.code}.nuberush.dev",
            full_name=f"{store.name} Manager",
            store=store,
            password_hash=pw_hash,
        )
        _make_user(
            db,
            role=UserRole.staff,
            email=f"staff1@{store.code}.nuberush.dev",
            full_name=f"{store.name} Staff One",
            store=store,
            password_hash=pw_hash,
        )
        _make_user(
            db,
            role=UserRole.staff,
            email=f"staff2@{store.code}.nuberush.dev",
            full_name=f"{store.name} Staff Two",
            store=store,
            password_hash=pw_hash,
        )
        _make_user(
            db,
            role=UserRole.driver,
            email=f"driver@{store.code}.nuberush.dev",
            full_name=f"{store.name} Driver",
            store=store,
            password_hash=pw_hash,
        )
        items = _seed_inventory(db, store, variants)
        _seed_inventory_logs(db, store, items, owner)
        _seed_orders(db, store, items)

    db.commit()
    print("✅ Seed complete.")
    print()
    print("Accounts (password = password123):")
    print(f"  • admin: {ADMIN_EMAIL}")
    for store_def in STORES:
        code = store_def["code"]
        print(
            f"  • owner@{code}.nuberush.dev / "
            f"manager@{code}.nuberush.dev / "
            f"staff1@{code}.nuberush.dev / driver@{code}.nuberush.dev"
        )


def main() -> int:
    if "DATABASE_URL" not in os.environ:
        print(
            "❌ DATABASE_URL is not set. "
            "Point it at your local Postgres before running.",
            file=sys.stderr,
        )
        return 1
    session_factory = get_session_factory()
    with session_factory() as db:
        try:
            seed(db)
        except Exception:
            db.rollback()
            raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
