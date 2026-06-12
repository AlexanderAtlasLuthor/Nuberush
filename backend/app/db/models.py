from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import FetchedValue
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


def timestamp_created_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


def timestamp_updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        server_onupdate=FetchedValue(),
        nullable=False,
    )


class UserRole(str, enum.Enum):
    owner = "owner"
    manager = "manager"
    staff = "staff"
    driver = "driver"
    admin = "admin"


class ComplianceStatus(str, enum.Enum):
    allowed = "allowed"
    restricted = "restricted"
    banned = "banned"


class ProductApprovalStatus(str, enum.Enum):
    """Catalog-curation gate for product rows.

    Pending → store-proposed; not visible to other stores, not sellable.
    Approved → curated by an admin (or admin-created); behaves as a normal
    catalog row (still subject to the separate compliance gate).
    Rejected → admin declined the proposal; rejection_reason is set.
    """

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class InventoryStatus(str, enum.Enum):
    available = "available"
    reserved = "reserved"
    sold = "sold"
    flagged = "flagged"
    quarantined = "quarantined"


class InventoryMovementType(str, enum.Enum):
    receipt = "receipt"
    adjustment = "adjustment"
    reservation = "reservation"
    sale = "sale"
    cancellation = "cancellation"
    return_ = "return"
    damage = "damage"
    compliance_hold = "compliance_hold"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    preparing = "preparing"
    ready = "ready"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    canceled = "canceled"
    returned = "returned"


class StoreApplicationStatus(str, enum.Enum):
    """Lifecycle for a merchant/store sign-up application (F2.24).

    draft           → started but not yet submitted (reserved for a future
                      "save and continue" flow; not produced by the MVP
                      intake path).
    submitted       → handed off by the applicant (reserved; the MVP intake
                      lands an application straight in `pending_review`).
    pending_review  → awaiting admin decision. The first operational state.
    approved        → admin accepted; the application links the store and the
                      owner user it provisioned (`provisioned_store_id`,
                      `provisioned_owner_user_id`).
    rejected        → admin declined; `rejection_reason` is set.

    All five values exist for extensibility, but only `pending_review`,
    `approved` and `rejected` are operational in F2.24. Provisioning and
    state transitions are NOT implemented in this data-layer subphase
    (F2.24.C1) — an application row is inert data here.
    """

    draft = "draft"
    submitted = "submitted"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (
        CheckConstraint("name <> ''", name="ck_stores_name_non_empty"),
        CheckConstraint("code <> ''", name="ck_stores_code_non_empty"),
        Index("ix_stores_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(50),
        server_default=text("'America/New_York'"),
        nullable=False,
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    users: Mapped[list[User]] = relationship(back_populates="store")
    inventory_items: Mapped[list[InventoryItem]] = relationship(back_populates="store")
    inventory_logs: Mapped[list[InventoryLog]] = relationship(back_populates="store")
    orders: Mapped[list[Order]] = relationship(back_populates="store")
    driver_profiles: Mapped[list[DriverProfile]] = relationship(
        back_populates="store"
    )
    driver_assignments: Mapped[list[OrderDriverAssignment]] = relationship(
        back_populates="store"
    )
    # Dr.1.1.G.1 — store-bound read anchor for delivery operational state.
    delivery_operational_states: Mapped[
        list[DriverDeliveryOperationalState]
    ] = relationship(back_populates="store")


class User(Base):
    # store_id is nullable by design: admin users are global and have no store.
    # Business rule (enforced in the service layer, not the DB): roles owner,
    # manager and staff must have a store_id; role admin must have store_id NULL.
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_store_id", "store_id"),
        Index("ix_users_role", "role"),
        Index("ix_users_is_active", "is_active"),
        # F2.22.2 identity bridge. Unique so a Supabase auth.users row maps
        # to at most one public.users row. A unique index (not a plain
        # constraint) keeps the lookup `WHERE auth_user_id = :sub` indexed
        # — that becomes the hot path once get_current_user is migrated.
        Index("ix_users_auth_user_id", "auth_user_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # F2.22.2 identity bridge: links this row to a Supabase `auth.users`
    # record (= the Supabase JWT `sub`). Since F2.22.2.F this is the ONLY
    # authentication link — there is no local password column anymore.
    # Nullable because pre-Supabase rows still need a backfill (see
    # scripts/backfill_supabase_auth_users.py). No cross-schema FK to
    # `auth.users` is declared here: that schema is owned by Supabase and
    # the relationship stays conceptual.
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    phone: Mapped[str | None] = mapped_column(String(30))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    store: Mapped[Store | None] = relationship(back_populates="users")
    inventory_logs: Mapped[list[InventoryLog]] = relationship(back_populates="performed_by_user")
    customer_orders: Mapped[list[Order]] = relationship(
        back_populates="customer_user",
        foreign_keys="Order.customer_user_id",
    )
    verified_orders: Mapped[list[Order]] = relationship(
        back_populates="age_verified_by_user",
        foreign_keys="Order.age_verified_by_user_id",
    )
    # Dr.1.1.C — a driver user has at most one operational driver profile.
    driver_profile: Mapped[DriverProfile | None] = relationship(
        back_populates="user",
        uselist=False,
    )


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("name <> ''", name="ck_products_name_non_empty"),
        CheckConstraint(
            "compliance_status != 'banned' OR allowed_for_sale = false",
            name="ck_products_banned_implies_not_allowed_for_sale",
        ),
        # rejected ⇔ rejection_reason set. Pending / approved must have
        # rejection_reason NULL so a row never carries a stale reason
        # after an admin re-approves a previously-rejected proposal.
        CheckConstraint(
            "(approval_status = 'rejected') = (rejection_reason IS NOT NULL)",
            name="ck_products_rejected_iff_reason",
        ),
        Index("ix_products_category", "category"),
        Index("ix_products_allowed_for_sale", "allowed_for_sale"),
        Index("ix_products_compliance_status", "compliance_status"),
        Index("ix_products_is_active", "is_active"),
        Index("ix_products_approval_status", "approval_status"),
        Index(
            "ix_products_proposed_by_store_id",
            "proposed_by_store_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    compliance_status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus, name="compliance_status"),
        server_default=text("'allowed'"),
        nullable=False,
    )
    allowed_for_sale: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    hold_reason: Mapped[str | None] = mapped_column(Text)
    jurisdiction: Mapped[str] = mapped_column(String(50), server_default=text("'FL'"), nullable=False)
    last_compliance_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Catalog approval workflow. Admin-created rows start `approved`;
    # store-proposed rows start `pending` and become `approved` /
    # `rejected` after admin review. Existing rows are backfilled to
    # `approved` by the migration so the catalog stays unchanged.
    approval_status: Mapped[ProductApprovalStatus] = mapped_column(
        Enum(ProductApprovalStatus, name="product_approval_status"),
        server_default=text("'approved'"),
        nullable=False,
    )
    proposed_by_store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
    )
    proposed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    variants: Mapped[list[ProductVariant]] = relationship(back_populates="product")
    compliance_audits: Mapped[list[ProductComplianceAuditLog]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    # F2.22.4.D: one primary image per product, enforced at the DB
    # layer by uq_product_images_product_id. uselist=False makes this
    # a scalar relationship; absence resolves to None.
    primary_image: Mapped[ProductImage | None] = relationship(
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_product_variants_sku"),
        CheckConstraint("sku <> ''", name="ck_product_variants_sku_non_empty"),
        CheckConstraint("price >= 0", name="ck_product_variants_price_non_negative"),
        CheckConstraint("cost IS NULL OR cost >= 0", name="ck_product_variants_cost_non_negative"),
        CheckConstraint("unit_count IS NULL OR unit_count > 0", name="ck_product_variants_unit_count_positive"),
        CheckConstraint("puff_count IS NULL OR puff_count > 0", name="ck_product_variants_puff_count_positive"),
        Index("ix_product_variants_product_id", "product_id"),
        Index("ix_product_variants_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True)
    flavor: Mapped[str | None] = mapped_column(String(100))
    size_label: Mapped[str | None] = mapped_column(String(50))
    unit_count: Mapped[int | None] = mapped_column(Integer)
    puff_count: Mapped[int | None] = mapped_column(Integer)
    thc_strength: Mapped[str | None] = mapped_column(String(50))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    product: Mapped[Product] = relationship(back_populates="variants")
    inventory_items: Mapped[list[InventoryItem]] = relationship(back_populates="variant")
    inventory_logs: Mapped[list[InventoryLog]] = relationship(back_populates="variant")
    order_items: Mapped[list[OrderItem]] = relationship(back_populates="variant")


class ProductImage(Base):
    """Metadata row for a product image stored in Supabase Storage.

    The binary lives in the `product-images` bucket; this row holds the
    business metadata FastAPI owns (which product, who uploaded, when).
    `unique(product_id)` enforces "one primary image per product" from
    the F2.22.4 scope lock (docs/f2.22-contract-lock.md §8.1).
    """

    __tablename__ = "product_images"
    __table_args__ = (
        UniqueConstraint(
            "product_id", name="uq_product_images_product_id"
        ),
        Index(
            "ix_product_images_uploaded_by_user_id",
            "uploaded_by_user_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "products.id",
            name="fk_product_images_product_id_products",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_product_images_uploaded_by_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    product: Mapped[Product] = relationship(back_populates="primary_image")
    uploaded_by_user: Mapped[User] = relationship()


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("store_id", "variant_id", name="uq_inventory_store_variant"),
        CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_items_quantity_on_hand_non_negative"),
        CheckConstraint("quantity_reserved >= 0", name="ck_inventory_items_quantity_reserved_non_negative"),
        CheckConstraint("reorder_threshold >= 0", name="ck_inventory_items_reorder_threshold_non_negative"),
        CheckConstraint("quantity_reserved <= quantity_on_hand", name="ck_inventory_items_reserved_lte_on_hand"),
        Index("ix_inventory_items_store_id", "store_id"),
        Index("ix_inventory_items_variant_id", "variant_id"),
        Index("ix_inventory_items_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    reorder_threshold: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    status: Mapped[InventoryStatus] = mapped_column(
        Enum(InventoryStatus, name="inventory_status"),
        server_default=text("'available'"),
        nullable=False,
    )
    last_counted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    store: Mapped[Store] = relationship(back_populates="inventory_items")
    variant: Mapped[ProductVariant] = relationship(back_populates="inventory_items")
    logs: Mapped[list[InventoryLog]] = relationship(back_populates="inventory_item")


class InventoryLog(Base):
    __tablename__ = "inventory_logs"
    __table_args__ = (
        CheckConstraint("quantity_delta <> 0", name="ck_inventory_logs_quantity_delta_non_zero"),
        CheckConstraint("quantity_after >= 0", name="ck_inventory_logs_quantity_after_non_negative"),
        CheckConstraint(
            "(reference_type IS NULL AND reference_id IS NULL) OR "
            "(reference_type IS NOT NULL AND reference_id IS NOT NULL)",
            name="ck_inventory_logs_reference_pair_consistent",
        ),
        Index("ix_inventory_logs_store_id", "store_id"),
        Index("ix_inventory_logs_variant_id", "variant_id"),
        Index("ix_inventory_logs_inventory_item_id", "inventory_item_id"),
        Index("ix_inventory_logs_created_at", "created_at"),
        Index("ix_inventory_logs_reference_type", "reference_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    performed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    movement_type: Mapped[InventoryMovementType] = mapped_column(
        Enum(
            InventoryMovementType,
            name="inventory_movement_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    reference_type: Mapped[str | None] = mapped_column(
        String(50),
        comment="Polymorphic source type for the related business record, such as order or adjustment.",
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        comment="Polymorphic UUID reference to the related business record identified by reference_type.",
    )
    created_at: Mapped[datetime] = timestamp_created_at()

    inventory_item: Mapped[InventoryItem] = relationship(back_populates="logs")
    store: Mapped[Store] = relationship(back_populates="inventory_logs")
    variant: Mapped[ProductVariant] = relationship(back_populates="inventory_logs")
    performed_by_user: Mapped[User | None] = relationship(back_populates="inventory_logs")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal_amount >= 0", name="ck_orders_subtotal_amount_non_negative"),
        CheckConstraint("tax_amount >= 0", name="ck_orders_tax_amount_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_orders_total_amount_non_negative"),
        CheckConstraint("total_amount >= subtotal_amount", name="ck_orders_total_amount_gte_subtotal"),
        CheckConstraint("idempotency_key <> ''", name="ck_orders_idempotency_key_non_empty"),
        UniqueConstraint("store_id", "idempotency_key", name="uq_orders_store_idempotency_key"),
        Index("ix_orders_store_id", "store_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        server_default=text("'pending'"),
        nullable=False,
    )
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), server_default=text("0"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), server_default=text("0"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), server_default=text("0"), nullable=False)
    age_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    age_verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    store: Mapped[Store] = relationship(back_populates="orders")
    customer_user: Mapped[User | None] = relationship(
        back_populates="customer_orders",
        foreign_keys=[customer_user_id],
    )
    age_verified_by_user: Mapped[User | None] = relationship(
        back_populates="verified_orders",
        foreign_keys=[age_verified_by_user_id],
    )
    items: Mapped[list[OrderItem]] = relationship(back_populates="order")
    audit_logs: Mapped[list[OrderAuditLog]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    driver_assignments: Mapped[list[OrderDriverAssignment]] = relationship(
        back_populates="order"
    )
    # Dr.1.1.G.1 — read anchor only; never mutated through this relationship.
    delivery_operational_states: Mapped[
        list[DriverDeliveryOperationalState]
    ] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "variant_id", name="uq_order_items_order_variant"),
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_order_items_unit_price_non_negative"),
        CheckConstraint("line_total >= 0", name="ck_order_items_line_total_non_negative"),
        CheckConstraint("line_total >= unit_price", name="ck_order_items_line_total_gte_unit_price"),
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_variant_id", "variant_id"),
        Index("ix_order_items_inventory_item_id", "inventory_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    order: Mapped[Order] = relationship(back_populates="items")
    variant: Mapped[ProductVariant] = relationship(back_populates="order_items")
    inventory_item: Mapped[InventoryItem] = relationship(
        foreign_keys=[inventory_item_id]
    )


class ProductComplianceAuditLog(Base):
    """Append-only audit trail for compliance changes on a product.

    Every transition of `Product.compliance_status` and every toggle of
    `Product.allowed_for_sale` must produce one row here. The contract is
    documented in `app.domain.products_rules` (section 4).
    """

    __tablename__ = "product_compliance_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "reason <> ''",
            name="ck_product_compliance_audit_logs_reason_non_empty",
        ),
        Index(
            "ix_product_compliance_audit_logs_product_id",
            "product_id",
        ),
        Index(
            "ix_product_compliance_audit_logs_changed_by_user_id",
            "changed_by_user_id",
        ),
        Index(
            "ix_product_compliance_audit_logs_created_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_compliance_status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus, name="compliance_status", create_type=False),
        nullable=False,
    )
    new_compliance_status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus, name="compliance_status", create_type=False),
        nullable=False,
    )
    previous_allowed_for_sale: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    new_allowed_for_sale: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = timestamp_created_at()

    product: Mapped[Product] = relationship(back_populates="compliance_audits")
    changed_by_user: Mapped[User | None] = relationship()


class OrderAuditLog(Base):
    """Append-only audit trail for order state transitions.

    Every transition of `Order.status` and other auditable order
    events (creation, cancellation, return) produce one row here.
    The contract is documented in `app.domain.orders_rules` (§8).
    """

    __tablename__ = "order_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "action <> ''",
            name="ck_order_audit_logs_action_non_empty",
        ),
        Index("ix_order_audit_logs_order_id", "order_id"),
        Index("ix_order_audit_logs_store_id", "store_id"),
        Index(
            "ix_order_audit_logs_performed_by_user_id",
            "performed_by_user_id",
        ),
        Index("ix_order_audit_logs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )
    performed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    previous_status: Mapped[OrderStatus | None] = mapped_column(
        Enum(OrderStatus, name="order_status", create_type=False),
    )
    new_status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", create_type=False),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = timestamp_created_at()

    order: Mapped[Order] = relationship(back_populates="audit_logs")
    performed_by_user: Mapped[User | None] = relationship()


class StoreApplication(Base):
    """A professional merchant/store sign-up application (F2.24).

    Public applicants submit business + owner details; an admin later
    reviews and approves or rejects them. At the F2.24.C1 data layer this
    row is INERT: nothing here creates a store, a user, or a Supabase Auth
    record, and no submit/approve/reject service exists yet.

    Provisioning links (`provisioned_store_id`, `provisioned_owner_user_id`)
    are populated only when an admin approves the application in a later
    subphase. The DB CHECK constraints below keep the row honest in the
    meantime — a non-approved row can never carry provisioning links, and an
    approved row must carry both.

    `owner_email` is stored verbatim at the model layer; normalization
    (lowercasing/trim) is the service layer's job in C2 — the column and its
    index simply support case-sensitive equality lookups today.
    """

    __tablename__ = "store_applications"
    __table_args__ = (
        CheckConstraint(
            "business_name <> ''",
            name="ck_store_applications_business_name_non_empty",
        ),
        CheckConstraint(
            "business_type <> ''",
            name="ck_store_applications_business_type_non_empty",
        ),
        CheckConstraint(
            "owner_full_name <> ''",
            name="ck_store_applications_owner_full_name_non_empty",
        ),
        CheckConstraint(
            "owner_email <> ''",
            name="ck_store_applications_owner_email_non_empty",
        ),
        CheckConstraint(
            "location_count > 0",
            name="ck_store_applications_location_count_positive",
        ),
        CheckConstraint(
            "estimated_weekly_orders IS NULL OR estimated_weekly_orders >= 0",
            name="ck_store_applications_estimated_weekly_orders_non_negative",
        ),
        # rejected ⇔ rejection_reason set. Mirrors the products workflow
        # (ck_products_rejected_iff_reason): a non-rejected row never keeps a
        # stale reason, and a rejected row must explain itself.
        CheckConstraint(
            "(status = 'rejected') = (rejection_reason IS NOT NULL)",
            name="ck_store_applications_rejected_iff_reason",
        ),
        # approved ⇔ provisioned store linked. Forces approved rows to carry
        # the store they created, and forbids any non-approved row
        # (draft / submitted / pending_review / rejected) from carrying one —
        # which satisfies "pending_review must not have a provisioned store"
        # as a special case.
        CheckConstraint(
            "(status = 'approved') = (provisioned_store_id IS NOT NULL)",
            name="ck_store_applications_approved_iff_store",
        ),
        # approved ⇔ provisioned owner linked. Same shape as the store link.
        CheckConstraint(
            "(status = 'approved') = (provisioned_owner_user_id IS NOT NULL)",
            name="ck_store_applications_approved_iff_owner",
        ),
        # Accepting the terms requires a timestamp recording when. A row that
        # did not accept may leave the timestamp NULL.
        CheckConstraint(
            "terms_accepted = false OR terms_accepted_at IS NOT NULL",
            name="ck_store_applications_terms_accepted_requires_timestamp",
        ),
        Index("ix_store_applications_status", "status"),
        Index("ix_store_applications_owner_email", "owner_email"),
        Index("ix_store_applications_submitted_at", "submitted_at"),
        # Unique index doubles as the lookup index the public status endpoint
        # (C2) will hit — same pattern as ix_users_auth_user_id.
        Index(
            "ix_store_applications_public_lookup_token",
            "public_lookup_token",
            unique=True,
        ),
        Index(
            "ix_store_applications_reviewed_by_user_id",
            "reviewed_by_user_id",
        ),
        Index(
            "ix_store_applications_provisioned_store_id",
            "provisioned_store_id",
        ),
        Index(
            "ix_store_applications_provisioned_owner_user_id",
            "provisioned_owner_user_id",
        ),
        # Backs the public-intake dedup rule at the DB layer (F2.24.C2): at
        # most one ACTIVE (non-rejected) application per owner_email. This
        # closes the query-then-insert TOCTOU race on the unauthenticated
        # endpoint — two concurrent same-email submissions can both pass the
        # service-level pre-check, and only this partial unique index stops
        # the second commit. owner_email is stored lowercased by the intake
        # service, so a plain-column partial unique index matches the
        # (lowercased) dedup query. `rejected` rows are excluded so a turned-
        # away applicant may re-apply.
        Index(
            "uq_store_applications_active_owner_email",
            "owner_email",
            unique=True,
            postgresql_where=text(
                "status IN ('draft', 'submitted', 'pending_review', "
                "'approved')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # --- Business / store details ---
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # --- Owner / contact details ---
    owner_full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    business_phone: Mapped[str | None] = mapped_column(String(30))

    # --- Address ---
    address_line_1: Mapped[str] = mapped_column(String(200), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    # ISO-3166 alpha-2; defaults to US for the MVP US-only footprint.
    country: Mapped[str] = mapped_column(
        String(2), server_default=text("'US'"), nullable=False
    )

    # --- Operational profile (Uber-Eats-style benchmark fields) ---
    location_count: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )
    estimated_weekly_orders: Mapped[int | None] = mapped_column(Integer)
    hours_of_operation: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(String(255))
    social_url: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    # --- Terms ---
    terms_accepted: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # --- Lifecycle / review ---
    status: Mapped[StoreApplicationStatus] = mapped_column(
        Enum(StoreApplicationStatus, name="store_application_status"),
        server_default=text("'draft'"),
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    # --- Provisioning links (populated only on approval, in a later phase) ---
    provisioned_store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
    )
    provisioned_owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Opaque token for the public status-lookup endpoint. Generated
    # Python-side (uuid4 hex = 32 chars) so every ORM insert is always
    # populated and unique without binding the model to a server-side SQL
    # expression — a complex server_default round-trips through Postgres's
    # normalizer and would otherwise show as spurious `alembic check` drift.
    public_lookup_token: Mapped[str] = mapped_column(
        String(64),
        default=lambda: uuid.uuid4().hex,
        nullable=False,
    )

    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    audit_logs: Mapped[list[StoreApplicationAuditLog]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        # Chronological, with id as a tiebreaker for same-tick rows, so the
        # admin detail view renders the history deterministically (mirrors
        # the explicit ordering of the order/compliance audit feeds).
        order_by=(
            "StoreApplicationAuditLog.created_at, "
            "StoreApplicationAuditLog.id"
        ),
    )
    reviewed_by_user: Mapped[User | None] = relationship(
        foreign_keys=[reviewed_by_user_id]
    )
    provisioned_store: Mapped[Store | None] = relationship(
        foreign_keys=[provisioned_store_id]
    )
    provisioned_owner_user: Mapped[User | None] = relationship(
        foreign_keys=[provisioned_owner_user_id]
    )


class StoreApplicationAuditLog(Base):
    """Append-only audit trail for a store application (F2.24).

    Mirrors the existing per-domain audit tables (`order_audit_logs`,
    `product_compliance_audit_logs`): a discriminator string (`event_type`,
    like `OrderAuditLog.action`), a nullable actor FK with ON DELETE SET
    NULL, and an append-only `created_at`. `payload` is a nullable JSONB bag
    for event-specific context (the attribute is named `payload`, not
    `metadata`, because SQLAlchemy reserves `Base.metadata`).

    F2.24.C1 only creates the table/model. No service emits rows yet; the
    `event_type` values listed in the project plan (application_created,
    application_approved, application_rejected, owner_provisioned,
    store_provisioned, email_triggered) are produced in later subphases.
    """

    __tablename__ = "store_application_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "event_type <> ''",
            name="ck_store_application_audit_logs_event_type_non_empty",
        ),
        Index(
            "ix_store_application_audit_logs_application_id",
            "application_id",
        ),
        Index(
            "ix_store_application_audit_logs_actor_user_id",
            "actor_user_id",
        ),
        Index(
            "ix_store_application_audit_logs_created_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("store_applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = timestamp_created_at()

    application: Mapped[StoreApplication] = relationship(
        back_populates="audit_logs"
    )
    actor_user: Mapped[User | None] = relationship()


class OperationalAuditLog(Base):
    """Append-only operational audit trail (F2.26.1.A — storage only).

    This is the persistent foundation for operational events — user
    management (create / update / role change / store assign-remove /
    activate-deactivate) and store lifecycle (create / update / activate /
    deactivate), with later phases extending it to settings and regulatory
    decisions. See docs/f2.26-web-app-mvp-closure-contract.md §6.

    F2.26.1.A creates the table and model ONLY. No service writes rows yet,
    the unified audit feed (`app.services.audit`) does not read it, and no
    `AuditSource` / `AuditEntityType` value references it. Those land in
    F2.26.1.B (write seams) and F2.26.2 (feed integration).

    Mirrors the existing per-domain append-only audit tables
    (`order_audit_logs`, `product_compliance_audit_logs`,
    `store_application_audit_logs`): a nullable actor FK with ON DELETE SET
    NULL, an append-only `created_at`, and no `updated_at`.

    `target_type` and `action` are `varchar`, NOT PostgreSQL enums — the
    same choice as `OrderAuditLog.action` and
    `StoreApplicationAuditLog.event_type`. New event kinds therefore never
    require an `ALTER TYPE ... ADD VALUE` migration; the closed verb set is
    enforced in the (future) service layer, not the DB.

    `store_id` is nullable by design: store-scoped events carry their store;
    global (admin-wide) events leave it NULL. The visibility rule that keeps
    NULL-store events admin-only is the unified-feed integration's job in a
    later subphase, not this one.

    The JSONB attribute is named `event_metadata` (not `metadata`) because
    SQLAlchemy reserves `Base.metadata`; the database column is still named
    `metadata` via the explicit column-name argument.
    """

    __tablename__ = "operational_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "target_type <> ''",
            name="ck_operational_audit_logs_target_type_non_empty",
        ),
        CheckConstraint(
            "action <> ''",
            name="ck_operational_audit_logs_action_non_empty",
        ),
        Index("ix_operational_audit_logs_created_at", "created_at"),
        Index("ix_operational_audit_logs_store_id", "store_id"),
        Index(
            "ix_operational_audit_logs_actor_user_id",
            "actor_user_id",
        ),
        Index(
            "ix_operational_audit_logs_target",
            "target_type",
            "target_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
    )
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Column name is "metadata"; the attribute is renamed to avoid the
    # reserved `Base.metadata`.
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB
    )
    created_at: Mapped[datetime] = timestamp_created_at()

    actor_user: Mapped[User | None] = relationship()
    store: Mapped[Store | None] = relationship()


# ===================================================================== #
# F2.26.5.A — Regulatory Intelligence Foundation (data model only).
#
# Backend-first foundation for vape/ENDS compliance signals. This subphase
# introduces storage ONLY: regulatory sources, imported notices/snapshots,
# best-effort product matches, human-reviewable compliance alerts, and an
# append-only audit trail for admin decisions on those alerts.
#
# Architectural guardrails baked in here (see the F2.26.5 scope lock):
#   - No automatic product blocking / hold / ban. A ComplianceAlert is an
#     advisory record reviewed by a human; nothing in this layer mutates a
#     Product. Real compliance mutation later must go through
#     `set_product_compliance()`, never a direct Product write.
#   - Regulatory decisions are audited in the DEDICATED
#     `regulatory_decision_audit_logs` table, NOT by extending
#     `operational_audit_logs` (whose taxonomy stays user/store-only).
#   - The constrained domain state columns (source kind, notice type, match
#     strategy, alert severity/status/recommended_action) are PostgreSQL
#     enums, matching `UserRole` / `OrderStatus` / `InventoryStatus`. The
#     decision-audit `action` is a `varchar` discriminator, matching every
#     other append-only audit table in this repo (`OrderAuditLog.action`,
#     `OperationalAuditLog.action`): new verbs never need an
#     `ALTER TYPE ... ADD VALUE`, and the closed set is enforced in the
#     (future) service/schema layer.
# ===================================================================== #


class RegulatorySourceKind(str, enum.Enum):
    """Origin/category of a regulatory source."""

    fda_pmta = "fda_pmta"
    fda_enforcement = "fda_enforcement"
    fda_advisory = "fda_advisory"
    retailer_guidance = "retailer_guidance"
    manual = "manual"


class RegulatoryNoticeType(str, enum.Enum):
    """Kind of imported regulatory notice/snapshot."""

    authorized_product_list = "authorized_product_list"
    enforcement_notice = "enforcement_notice"
    advisory = "advisory"
    retailer_guidance = "retailer_guidance"
    manual_snapshot = "manual_snapshot"


class RegulatoryMatchStrategy(str, enum.Enum):
    """How a notice was best-effort matched to an internal product/variant."""

    name = "name"
    brand = "brand"
    category = "category"
    sku = "sku"
    barcode = "barcode"
    flavor = "flavor"
    manual = "manual"


class ComplianceAlertSeverity(str, enum.Enum):
    """Operator-facing urgency of a compliance alert."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ComplianceAlertStatus(str, enum.Enum):
    """Human-review lifecycle of a compliance alert.

    open          → newly raised, awaiting review.
    acknowledged  → an admin has seen it but not yet acted.
    actioned      → an admin took the recommended (or another) action.
    dismissed     → an admin judged it not actionable.

    No status here implies an automatic Product mutation; transitions are
    recorded in `regulatory_decision_audit_logs` by a later subphase.
    """

    open = "open"
    acknowledged = "acknowledged"
    actioned = "actioned"
    dismissed = "dismissed"


class ComplianceRecommendedAction(str, enum.Enum):
    """Advisory action a compliance alert suggests — never auto-applied.

    `none` → informational only. `hold` / `ban` are the human-reviewable
    recommendations; applying either later goes through
    `set_product_compliance()`, not this table.
    """

    none = "none"
    hold = "hold"
    ban = "ban"


class RegulatorySource(Base):
    """An external or internal regulatory source feeding compliance signals.

    `last_synced_at` is a bookkeeping timestamp updated by a future ingestion
    service (F2.26.5.B); this subphase neither fetches nor schedules anything.

    F2.27.7.B adds NON-SECRET ingestion bookkeeping consumed by the future
    orchestrator (F2.27.7.C): `fetch_config` (e.g. endpoint / params / parser
    key — never a secret, token, or credential), `cursor` (an incremental
    high-water mark such as a last published date or external ref), and the
    `last_attempted_at` / `last_succeeded_at` pair. Secrets stay in settings,
    never in this row. These columns are inert here — no code reads or writes
    them in this subphase.
    """

    __tablename__ = "regulatory_sources"
    __table_args__ = (
        UniqueConstraint("name", name="uq_regulatory_sources_name"),
        CheckConstraint(
            "name <> ''", name="ck_regulatory_sources_name_non_empty"
        ),
        Index("ix_regulatory_sources_kind", "kind"),
        Index("ix_regulatory_sources_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[RegulatorySourceKind] = mapped_column(
        Enum(RegulatorySourceKind, name="regulatory_source_kind"),
        nullable=False,
    )
    reference_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    # F2.27.7.B ingestion bookkeeping (non-secret; orchestrator-owned in .C).
    fetch_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cursor: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_succeeded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    notices: Mapped[list[RegulatoryNotice]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    ingestion_runs: Mapped[list[RegulatoryIngestionRun]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class RegulatoryNotice(Base):
    """An imported regulatory notice/snapshot belonging to a source.

    Append-only by design (only `created_at`, no `updated_at`): a notice is
    an immutable import. `content_hash` supports dedupe — the
    `(source_id, content_hash)` uniqueness lets a later ingestion service
    skip re-importing an unchanged snapshot. `payload` is the raw structured
    body the import carried.
    """

    __tablename__ = "regulatory_notices"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "content_hash",
            name="uq_regulatory_notices_source_content_hash",
        ),
        CheckConstraint(
            "title <> ''", name="ck_regulatory_notices_title_non_empty"
        ),
        CheckConstraint(
            "content_hash <> ''",
            name="ck_regulatory_notices_content_hash_non_empty",
        ),
        Index("ix_regulatory_notices_source_id", "source_id"),
        Index("ix_regulatory_notices_notice_type", "notice_type"),
        Index("ix_regulatory_notices_published_at", "published_at"),
        Index("ix_regulatory_notices_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_sources.id",
            name="fk_regulatory_notices_source_id_regulatory_sources",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    external_ref: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    notice_type: Mapped[RegulatoryNoticeType] = mapped_column(
        Enum(RegulatoryNoticeType, name="regulatory_notice_type"),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = timestamp_created_at()

    source: Mapped[RegulatorySource] = relationship(
        back_populates="notices"
    )
    matches: Mapped[list[RegulatoryProductMatch]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[ComplianceAlert]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )


class RegulatoryProductMatch(Base):
    """A best-effort match between a notice and an internal product/variant.

    A match is a CANDIDATE, not a verdict — `confidence` (0.00–1.00) and
    `match_strategy` describe how it was derived. `matched_fields` records
    which fields lined up. A match never mutates the product; at most it
    seeds a `ComplianceAlert` for human review in a later subphase.
    """

    __tablename__ = "regulatory_product_matches"
    __table_args__ = (
        UniqueConstraint(
            "notice_id",
            "product_id",
            "variant_id",
            "match_strategy",
            name="uq_regulatory_product_matches_dedupe",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_regulatory_product_matches_confidence_range",
        ),
        Index("ix_regulatory_product_matches_notice_id", "notice_id"),
        Index("ix_regulatory_product_matches_product_id", "product_id"),
        Index("ix_regulatory_product_matches_variant_id", "variant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    notice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_notices.id",
            name="fk_regulatory_product_matches_notice_id_regulatory_notices",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "products.id",
            name="fk_regulatory_product_matches_product_id_products",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "product_variants.id",
            name="fk_regulatory_product_matches_variant_id_product_variants",
            ondelete="SET NULL",
        ),
    )
    match_strategy: Mapped[RegulatoryMatchStrategy] = mapped_column(
        Enum(RegulatoryMatchStrategy, name="regulatory_match_strategy"),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    matched_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )
    created_at: Mapped[datetime] = timestamp_created_at()

    notice: Mapped[RegulatoryNotice] = relationship(back_populates="matches")
    product: Mapped[Product] = relationship()
    variant: Mapped[ProductVariant | None] = relationship()
    alerts: Mapped[list[ComplianceAlert]] = relationship(
        back_populates="match"
    )


class ComplianceAlert(Base):
    """A human-reviewable regulatory compliance alert.

    Advisory only: raising an alert NEVER blocks, holds or bans a product.
    `recommended_action` is a suggestion an admin may follow; applying it
    later routes through `set_product_compliance()`, not this table. The
    review lifecycle is `status`; the `resolved_*` columns capture who/when
    closed it (kept consistent by a CHECK so a row is either fully resolved
    or not at all).
    """

    __tablename__ = "compliance_alerts"
    __table_args__ = (
        # A row is either unresolved (both NULL) or resolved (both set).
        CheckConstraint(
            "(resolved_at IS NULL) = (resolved_by_user_id IS NULL)",
            name="ck_compliance_alerts_resolution_pair_consistent",
        ),
        Index("ix_compliance_alerts_status", "status"),
        Index("ix_compliance_alerts_severity", "severity"),
        Index("ix_compliance_alerts_created_at", "created_at"),
        Index("ix_compliance_alerts_notice_id", "notice_id"),
        Index("ix_compliance_alerts_product_id", "product_id"),
        Index("ix_compliance_alerts_match_id", "match_id"),
        Index(
            "ix_compliance_alerts_resolved_by_user_id",
            "resolved_by_user_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    notice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_notices.id",
            name="fk_compliance_alerts_notice_id_regulatory_notices",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    # Nullable: most alerts are product-specific, but the architecture allows
    # a notice-level alert with no single product. SET NULL preserves the
    # alert's history if the product row is later removed.
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "products.id",
            name="fk_compliance_alerts_product_id_products",
            ondelete="SET NULL",
        ),
    )
    # Set only when the alert was generated from a specific match. SET NULL so
    # pruning a match never deletes the human-reviewable alert.
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_product_matches.id",
            name="fk_compliance_alerts_match_id_regulatory_product_matches",
            ondelete="SET NULL",
        ),
    )
    severity: Mapped[ComplianceAlertSeverity] = mapped_column(
        Enum(ComplianceAlertSeverity, name="compliance_alert_severity"),
        nullable=False,
    )
    status: Mapped[ComplianceAlertStatus] = mapped_column(
        Enum(ComplianceAlertStatus, name="compliance_alert_status"),
        server_default=text("'open'"),
        nullable=False,
    )
    recommended_action: Mapped[ComplianceRecommendedAction] = mapped_column(
        Enum(
            ComplianceRecommendedAction, name="compliance_recommended_action"
        ),
        server_default=text("'none'"),
        nullable=False,
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_compliance_alerts_resolved_by_user_id_users",
            ondelete="SET NULL",
        ),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    notice: Mapped[RegulatoryNotice] = relationship(back_populates="alerts")
    match: Mapped[RegulatoryProductMatch | None] = relationship(
        back_populates="alerts"
    )
    product: Mapped[Product | None] = relationship()
    resolved_by_user: Mapped[User | None] = relationship()
    decision_audits: Mapped[list[RegulatoryDecisionAuditLog]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )


class RegulatoryDecisionAuditLog(Base):
    """Append-only audit for admin decisions on regulatory alerts.

    Dedicated to regulatory decisions — deliberately NOT
    `operational_audit_logs`, whose taxonomy stays user/store-only. Mirrors
    the repo's other append-only audit tables: a `varchar` `action`
    discriminator (no PG enum, so new verbs never need an `ALTER TYPE`), a
    required `reason`, JSON `before`/`after`/`metadata` snapshots, and only
    `created_at` (no `updated_at`).

    `actor_user_id` is REQUIRED (NOT NULL) and uses ON DELETE RESTRICT:
    every regulatory decision is accountable to a real admin, and that admin
    cannot be deleted while their decisions stand. The JSONB attribute is
    `event_metadata` (column name `metadata`) because SQLAlchemy reserves
    `Base.metadata`.
    """

    __tablename__ = "regulatory_decision_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "action <> ''",
            name="ck_regulatory_decision_audit_logs_action_non_empty",
        ),
        CheckConstraint(
            "reason <> ''",
            name="ck_regulatory_decision_audit_logs_reason_non_empty",
        ),
        Index("ix_regulatory_decision_audit_logs_alert_id", "alert_id"),
        Index("ix_regulatory_decision_audit_logs_notice_id", "notice_id"),
        Index("ix_regulatory_decision_audit_logs_product_id", "product_id"),
        Index(
            "ix_regulatory_decision_audit_logs_actor_user_id",
            "actor_user_id",
        ),
        Index(
            "ix_regulatory_decision_audit_logs_created_at", "created_at"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "compliance_alerts.id",
            name="fk_regulatory_decision_audit_logs_alert_id_compliance_alerts",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    notice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_notices.id",
            name="fk_regulatory_decision_audit_logs_notice_id_regulatory_notices",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    # Nullable: the alert may be notice-level (no single product). SET NULL
    # preserves the append-only decision row if a product is later removed.
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "products.id",
            name="fk_regulatory_decision_audit_logs_product_id_products",
            ondelete="SET NULL",
        ),
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_regulatory_decision_audit_logs_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Column name is "metadata"; the attribute is renamed to avoid the
    # reserved `Base.metadata`.
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = timestamp_created_at()

    alert: Mapped[ComplianceAlert] = relationship(
        back_populates="decision_audits"
    )
    notice: Mapped[RegulatoryNotice] = relationship()
    product: Mapped[Product | None] = relationship()
    actor_user: Mapped[User] = relationship()


class RegulatoryIngestionRun(Base):
    """An ingestion attempt against one regulatory source — observability only
    (F2.27.7.B).

    The ledger row a future orchestrator (F2.27.7.C) opens when it ingests a
    source and closes when it finishes. It records WHO triggered the run, WHEN
    it ran, its terminal STATUS, and rolled-up COUNTERS (items seen / notices
    created / deduped / failed, plus matches and alerts created downstream). It
    NEVER mutates a product, an alert, or a compliance decision — this subphase
    ships the storage only; no orchestrator, route, scheduler, or writer exists
    yet.

    `trigger` and `status` are `varchar` discriminators guarded by CHECK
    constraints (no PG enum, so new values never need an `ALTER TYPE`),
    matching the repo's audit-table convention; the closed value sets are
    mirrored as Pydantic enums in `app.schemas.regulatory_ingestion`. Only
    `manual` is produced by F2.27.7; `scheduled` is future-ready.
    `actor_user_id` is NULLABLE (ON DELETE SET NULL): a `scheduled` run has no
    human actor, and a deleted admin must not erase the run's history.
    """

    __tablename__ = "regulatory_ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "trigger IN ('manual', 'scheduled')",
            name="ck_regulatory_ingestion_runs_trigger_valid",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'partial')",
            name="ck_regulatory_ingestion_runs_status_valid",
        ),
        CheckConstraint(
            "items_seen >= 0 AND items_created >= 0 AND items_deduped >= 0 "
            "AND items_failed >= 0 AND matches_created >= 0 "
            "AND alerts_created >= 0",
            name="ck_regulatory_ingestion_runs_counts_non_negative",
        ),
        Index("ix_regulatory_ingestion_runs_source_id", "source_id"),
        Index("ix_regulatory_ingestion_runs_status", "status"),
        Index("ix_regulatory_ingestion_runs_started_at", "started_at"),
        Index("ix_regulatory_ingestion_runs_created_at", "created_at"),
        Index(
            "ix_regulatory_ingestion_runs_actor_user_id", "actor_user_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_sources.id",
            name="fk_regulatory_ingestion_runs_source_id_regulatory_sources",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    items_seen: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    items_created: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    items_deduped: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    items_failed: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    matches_created: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    alerts_created: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_regulatory_ingestion_runs_actor_user_id_users",
            ondelete="SET NULL",
        ),
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    source: Mapped[RegulatorySource] = relationship(
        back_populates="ingestion_runs"
    )
    actor_user: Mapped[User | None] = relationship()
    items: Mapped[list[RegulatoryIngestionItem]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RegulatoryIngestionItem(Base):
    """A per-item outcome within a `RegulatoryIngestionRun` (F2.27.7.B).

    Append-only (only `created_at`, no `updated_at`): each row records what one
    source item became — `created` (a new notice persisted), `deduped` (matched
    an existing `(source_id, content_hash)` and reused it), or `failed` (a
    parse/persist error). `notice_id` is set only for `created` / `deduped`
    outcomes (ON DELETE SET NULL keeps the ledger row if a notice is removed).

    Security: this table NEVER stores a raw payload/body, a secret, an API key,
    or an auth header. It holds only the stable `external_ref`, the
    `content_hash`, and a short machine `error_code` + human `error_message` —
    there is deliberately NO `raw_payload` / `body` column.
    """

    __tablename__ = "regulatory_ingestion_items"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('created', 'deduped', 'failed')",
            name="ck_regulatory_ingestion_items_outcome_valid",
        ),
        Index("ix_regulatory_ingestion_items_run_id", "run_id"),
        Index("ix_regulatory_ingestion_items_notice_id", "notice_id"),
        Index("ix_regulatory_ingestion_items_outcome", "outcome"),
        Index(
            "ix_regulatory_ingestion_items_external_ref", "external_ref"
        ),
        Index(
            "ix_regulatory_ingestion_items_content_hash", "content_hash"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_ingestion_runs.id",
            name=(
                "fk_regulatory_ingestion_items_run_id_"
                "regulatory_ingestion_runs"
            ),
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    external_ref: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    notice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "regulatory_notices.id",
            name=(
                "fk_regulatory_ingestion_items_notice_id_"
                "regulatory_notices"
            ),
            ondelete="SET NULL",
        ),
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = timestamp_created_at()

    run: Mapped[RegulatoryIngestionRun] = relationship(
        back_populates="items"
    )
    notice: Mapped[RegulatoryNotice | None] = relationship()


class PlatformSettings(Base):
    """Singleton platform-wide configuration for Admin Settings (F2.27.10.A).

    Backend-first persistence foundation for the writable Admin Settings
    surface. This subphase ships the storage ONLY — there is no service,
    schema, route, or get-or-create logic yet. By design the table holds a
    SINGLE row (enforced by a later service layer, not the DB); this subphase
    neither inserts that row nor seeds defaults.

    Column server defaults mirror the read-only constants the current
    `admin_settings` snapshot surfaces (`platform_name` ≈ app name,
    `default_locale` `en-US`, `default_timezone` `America/New_York`) so the
    eventual get-or-create lands consistent values. `updated_at` is maintained
    by the shared `set_updated_at()` trigger, matching `regulatory_sources`
    and `compliance_alerts`.

    Deliberately NOT here: secrets or env-backed config (Supabase / email /
    database / CORS) never live in this table.
    """

    __tablename__ = "platform_settings"
    __table_args__ = (
        CheckConstraint(
            "platform_name <> ''",
            name="ck_platform_settings_platform_name_non_empty",
        ),
        CheckConstraint(
            "default_locale <> ''",
            name="ck_platform_settings_default_locale_non_empty",
        ),
        CheckConstraint(
            "default_timezone <> ''",
            name="ck_platform_settings_default_timezone_non_empty",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    platform_name: Mapped[str] = mapped_column(
        String(150),
        server_default=text("'NubeRush'"),
        nullable=False,
    )
    support_email: Mapped[str | None] = mapped_column(String(255))
    default_locale: Mapped[str] = mapped_column(
        String(10),
        server_default=text("'en-US'"),
        nullable=False,
    )
    default_timezone: Mapped[str] = mapped_column(
        String(50),
        server_default=text("'America/New_York'"),
        nullable=False,
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()


class PlatformSettingsAuditLog(Base):
    """Append-only audit trail for platform-settings mutations (F2.27.10.A).

    Dedicated table — deliberately NOT `operational_audit_logs` and NOT wired
    into the unified Admin Audit feed (`app.services.audit`). Mirrors the
    repo's other append-only audit tables: a `varchar` `action` discriminator
    (no PG enum, so new verbs never need an `ALTER TYPE`), JSON `before`/
    `after` snapshots, and only `created_at` (no `updated_at`).

    `actor_user_id` is REQUIRED and uses ON DELETE RESTRICT: every settings
    change is accountable to a real admin who cannot be deleted while their
    decisions stand. The future writer/service (a later subphase) will record
    `action = "platform_settings_updated"`; this subphase ships the storage
    only — no writer, no helper, no integration.
    """

    __tablename__ = "platform_settings_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "action <> ''",
            name="ck_platform_settings_audit_logs_action_non_empty",
        ),
        Index(
            "ix_platform_settings_audit_logs_platform_settings_id",
            "platform_settings_id",
        ),
        Index(
            "ix_platform_settings_audit_logs_actor_user_id",
            "actor_user_id",
        ),
        Index(
            "ix_platform_settings_audit_logs_created_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    platform_settings_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "platform_settings.id",
            name="fk_platform_settings_audit_logs_settings_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_platform_settings_audit_logs_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    before: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    after: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = timestamp_created_at()

    settings: Mapped[PlatformSettings] = relationship()
    actor_user: Mapped[User] = relationship()


# ===================================================================== #
# F2.27.9.A — QuickBooks / accounting integration foundation (storage only).
#
# Backend-first foundation for connecting a store to an external accounting
# provider (QuickBooks). This subphase introduces STORAGE ONLY: a per-store
# integration row holding ENCRYPTED OAuth tokens, a variant <-> external-item
# mapping, and an append-only sync ledger (run + per-item outcomes).
#
# Architectural guardrails baked in here (see the F2.27.9 diagnostic):
#   - NubeRush stays authoritative for inventory; QuickBooks mirrors it. Nothing
#     in this layer mutates inventory, products, or compliance — and no
#     OAuth flow, QuickBooks client, mapping service, or sync orchestrator
#     exists yet. These tables are inert data in F2.27.9.A.
#   - Tokens are stored ENCRYPTED AT REST only: the columns are
#     `access_token_encrypted` / `refresh_token_encrypted` (Fernet ciphertext
#     via app.core.encryption). There is deliberately NO plaintext token,
#     client secret, authorization header, or raw QuickBooks payload/body
#     column anywhere in this section — that material lives in settings (the
#     secret) or is never persisted (raw payloads).
#   - `provider` / `status` / `environment` / `sync_type` / `direction` /
#     `status` / `trigger` / `outcome` are `varchar` discriminators guarded by
#     CHECK constraints (no PG enum, so new values never need an
#     `ALTER TYPE`), matching the repo's audit/ledger convention
#     (`RegulatoryIngestionRun.trigger/status`). The closed sets are mirrored
#     as Pydantic enums in `app.schemas.accounting`.
#   - Token-bearing tables are additionally protected by a Supabase deny-all
#     FORCE-RLS migration (supabase/migrations); FastAPI reaches them only via
#     the BYPASSRLS `nuberush_app` role.
# ===================================================================== #


class StoreAccountingIntegration(Base):
    """A store's connection to an external accounting provider (QuickBooks).

    One row per (store, provider). Holds the connection lifecycle `status`, the
    `environment` (sandbox vs production), the Intuit `realm_id` (company id),
    and the OAuth tokens — stored ENCRYPTED ONLY (`access_token_encrypted` /
    `refresh_token_encrypted`). Token expiry timestamps and `scopes` are kept
    for refresh bookkeeping; none of the token *material* is ever stored in
    plaintext or returned by the API.

    F2.27.9.A ships the table/model only: no OAuth flow, client, or sync writes
    a token here yet.
    """

    __tablename__ = "store_accounting_integrations"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "provider",
            name="uq_store_accounting_integrations_store_provider",
        ),
        CheckConstraint(
            "provider IN ('quickbooks')",
            name="ck_store_accounting_integrations_provider_valid",
        ),
        CheckConstraint(
            "status IN ('connected', 'disconnected', 'expired', 'error')",
            name="ck_store_accounting_integrations_status_valid",
        ),
        CheckConstraint(
            "environment IN ('sandbox', 'production')",
            name="ck_store_accounting_integrations_environment_valid",
        ),
        Index(
            "ix_store_accounting_integrations_store_id", "store_id"
        ),
        Index("ix_store_accounting_integrations_status", "status"),
        Index(
            "ix_store_accounting_integrations_connected_by_user_id",
            "connected_by_user_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "stores.id",
            name="fk_store_accounting_integrations_store_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'quickbooks'"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'disconnected'"),
        nullable=False,
    )
    environment: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'sandbox'"),
        nullable=False,
    )
    realm_id: Mapped[str | None] = mapped_column(String(64))
    # OAuth tokens — ENCRYPTED AT REST ONLY (Fernet ciphertext). Never store
    # plaintext token material here.
    access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    scopes: Mapped[str | None] = mapped_column(Text)
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_store_accounting_integrations_connected_by_user_id",
            ondelete="SET NULL",
        ),
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    # Forward-only relationships to existing tables (no back_populates) so the
    # Store / User models stay untouched in this subphase.
    store: Mapped[Store] = relationship()
    connected_by_user: Mapped[User | None] = relationship()
    mappings: Mapped[list[ProductVariantAccountingMapping]] = relationship(
        back_populates="integration", cascade="all, delete-orphan"
    )
    sync_logs: Mapped[list[AccountingSyncLog]] = relationship(
        back_populates="integration", cascade="all, delete-orphan"
    )


class ProductVariantAccountingMapping(Base):
    """A 1:1 link between a NubeRush variant and an external accounting item.

    Within one integration, one NubeRush variant maps to exactly one external
    item and vice-versa (enforced by the two unique constraints). `store_id` is
    denormalized for fast tenancy filtering and RLS clarity. `sync_enabled`
    lets an operator opt a mapping out of a push without deleting it.

    F2.27.9.A ships the table/model only: no mapping service writes rows yet.
    """

    __tablename__ = "product_variant_accounting_mappings"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "variant_id",
            name="uq_product_variant_accounting_mappings_integration_variant",
        ),
        UniqueConstraint(
            "integration_id",
            "external_item_id",
            name="uq_product_variant_accounting_mappings_integration_external",
        ),
        CheckConstraint(
            "provider IN ('quickbooks')",
            name="ck_product_variant_accounting_mappings_provider_valid",
        ),
        Index(
            "ix_product_variant_accounting_mappings_integration_id",
            "integration_id",
        ),
        Index(
            "ix_product_variant_accounting_mappings_variant_id",
            "variant_id",
        ),
        Index(
            "ix_product_variant_accounting_mappings_store_id",
            "store_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "store_accounting_integrations.id",
            name="fk_product_variant_accounting_mappings_integration_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "stores.id",
            name="fk_product_variant_accounting_mappings_store_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "product_variants.id",
            name="fk_product_variant_accounting_mappings_variant_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'quickbooks'"),
        nullable=False,
    )
    external_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_item_name: Mapped[str | None] = mapped_column(String(255))
    sync_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    integration: Mapped[StoreAccountingIntegration] = relationship(
        back_populates="mappings"
    )
    store: Mapped[Store] = relationship()
    variant: Mapped[ProductVariant] = relationship()


class AccountingSyncLog(Base):
    """Append-only ledger header for one accounting sync run (F2.27.9.A).

    Records WHAT kind of sync ran (`sync_type`), in which `direction`, its
    terminal `status`, how it was triggered, when it ran, and rolled-up
    counters. Observability only — a sync run NEVER mutates inventory,
    products, or compliance. Mirrors `RegulatoryIngestionRun`: `varchar`
    discriminators guarded by CHECK constraints, counters defaulting to 0, and
    a redacted-only `error_summary` (never a raw payload/body).

    Only `manual` is produced by F2.27.9; `scheduled` is a future-ready
    discriminator value — NO automated scheduling exists or is implemented here.
    `actor_user_id` is nullable (ON DELETE SET NULL): a future system-triggered
    run has no human actor, and a deleted user must not erase the run's
    history. The row is append-only (only `created_at`, no `updated_at`).
    """

    __tablename__ = "accounting_sync_logs"
    __table_args__ = (
        CheckConstraint(
            "sync_type IN ('item_discovery', 'mapping_pull', 'inventory_push')",
            name="ck_accounting_sync_logs_sync_type_valid",
        ),
        CheckConstraint(
            "direction IN ('pull', 'push')",
            name="ck_accounting_sync_logs_direction_valid",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'partial')",
            name="ck_accounting_sync_logs_status_valid",
        ),
        CheckConstraint(
            "trigger IN ('manual', 'scheduled')",
            name="ck_accounting_sync_logs_trigger_valid",
        ),
        CheckConstraint(
            "items_seen >= 0 AND items_created >= 0 AND items_updated >= 0 "
            "AND items_skipped >= 0 AND items_failed >= 0",
            name="ck_accounting_sync_logs_counts_non_negative",
        ),
        Index("ix_accounting_sync_logs_store_id", "store_id"),
        Index("ix_accounting_sync_logs_integration_id", "integration_id"),
        Index("ix_accounting_sync_logs_status", "status"),
        Index("ix_accounting_sync_logs_started_at", "started_at"),
        Index("ix_accounting_sync_logs_created_at", "created_at"),
        Index("ix_accounting_sync_logs_actor_user_id", "actor_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "stores.id",
            name="fk_accounting_sync_logs_store_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "store_accounting_integrations.id",
            name="fk_accounting_sync_logs_integration_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    sync_type: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    items_seen: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    items_created: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    items_updated: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    items_skipped: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    items_failed: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_accounting_sync_logs_actor_user_id",
            ondelete="SET NULL",
        ),
    )
    created_at: Mapped[datetime] = timestamp_created_at()

    integration: Mapped[StoreAccountingIntegration] = relationship(
        back_populates="sync_logs"
    )
    store: Mapped[Store] = relationship()
    actor_user: Mapped[User | None] = relationship()
    items: Mapped[list[AccountingSyncLogItem]] = relationship(
        back_populates="sync_log", cascade="all, delete-orphan"
    )


class AccountingSyncLogItem(Base):
    """A per-item outcome within an `AccountingSyncLog` (F2.27.9.A).

    Append-only (only `created_at`): each row records what one item became
    during a run — `created` / `updated` / `skipped` / `failed`. `variant_id`
    is nullable with ON DELETE SET NULL so the ledger row survives variant
    removal; an inbound-discovery item may have no NubeRush variant yet.

    Security: this table NEVER stores a raw payload/body, a secret, a token, or
    an auth header — only the stable `external_item_id` / `external_item_name`,
    the `outcome`, and a short machine `error_code` + human `error_message`.
    There is deliberately NO `raw_payload` / `body` column.
    """

    __tablename__ = "accounting_sync_log_items"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('created', 'updated', 'skipped', 'failed')",
            name="ck_accounting_sync_log_items_outcome_valid",
        ),
        Index("ix_accounting_sync_log_items_sync_log_id", "sync_log_id"),
        Index("ix_accounting_sync_log_items_variant_id", "variant_id"),
        Index("ix_accounting_sync_log_items_outcome", "outcome"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    sync_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "accounting_sync_logs.id",
            name="fk_accounting_sync_log_items_sync_log_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "product_variants.id",
            name="fk_accounting_sync_log_items_variant_id",
            ondelete="SET NULL",
        ),
    )
    external_item_id: Mapped[str | None] = mapped_column(String(255))
    external_item_name: Mapped[str | None] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = timestamp_created_at()

    sync_log: Mapped[AccountingSyncLog] = relationship(
        back_populates="items"
    )
    variant: Mapped[ProductVariant | None] = relationship()


class DriverProfileStatus(str, enum.Enum):
    """Operational lifecycle of a driver profile (Dr.1.1.C).

    Stored as a VARCHAR + CHECK discriminator (not a PG enum), matching the
    recent F2.27 convention. `suspended` is deliberately NOT modelled in
    Dr.1.1.C; if introduced later it belongs HERE (operational lifecycle),
    never in `DriverApprovalStatus`.
    """

    active = "active"
    inactive = "inactive"


class DriverApprovalStatus(str, enum.Enum):
    """Onboarding approval gate of a driver profile (Dr.1.1.C).

    A monotonic decision (pending -> approved/rejected). Kept separate from
    `DriverProfileStatus` so "was this driver ever approved" never conflates
    with "is this driver currently operational".
    """

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class DriverProfile(Base):
    """Minimal operational identity for a driver user (Dr.1.1.C).

    One row per driver `User`, bound to a `Store` (store-bound driver
    tenancy, Dr.1.1.A §4). This is the foundation only: it carries lifecycle
    `status` and onboarding `approval_status` plus their timestamps, and
    nothing else. Documents, vehicles, training, background checks, payout,
    assignments, availability, eligibility, and audit are explicitly out of
    scope here and arrive in later Dr.1.1 subphases.

    The user/store match invariant (a profile's `store_id` must equal its
    user's `store_id`) is enforced in the service layer and tests, not at the
    DB level — it is a cross-table rule a CHECK constraint cannot express.
    """

    __tablename__ = "driver_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_driver_profiles_user_id"),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_driver_profiles_status_valid",
        ),
        CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name="ck_driver_profiles_approval_status_valid",
        ),
        Index("ix_driver_profiles_store_id", "store_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_driver_profiles_user_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "stores.id",
            name="fk_driver_profiles_store_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    user: Mapped[User] = relationship(back_populates="driver_profile")
    store: Mapped[Store] = relationship(back_populates="driver_profiles")
    assignments: Mapped[list[OrderDriverAssignment]] = relationship(
        back_populates="driver_profile"
    )
    # Dr.1.1.G.1 — self-scope read anchor for delivery operational state.
    delivery_operational_states: Mapped[
        list[DriverDeliveryOperationalState]
    ] = relationship(back_populates="driver_profile")


class OrderDriverAssignmentStatus(str, enum.Enum):
    """Lifecycle of a driver<->order assignment (Dr.1.1.A §10, frozen).

    Stored as a VARCHAR + CHECK discriminator (not a PG enum), matching the
    recent convention. This is the ASSIGNMENT lifecycle only — delivery
    operational micro-states (pickup_confirmed, en_route_to_customer, …)
    belong to a separate future contract (§11) and must never appear here.
    """

    offered = "offered"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    assigned = "assigned"
    started = "started"
    completed = "completed"
    canceled = "canceled"


class OrderDriverAssignment(Base):
    """Dedicated driver<->order assignment record (Dr.1.1.E).

    The assignment is its OWN entity, deliberately NOT an `assigned_driver_id`
    column on `orders` (Dr.1.1.A §10). It carries its own lifecycle `status`
    (the frozen §10 vocabulary) and lifecycle timestamps. It does NOT alter
    inventory, complete orders, or overload `OrderStatus`, and it never holds
    delivery operational micro-states (those are a separate future contract,
    §11).

    This is a MODEL FOUNDATION only: there is no dispatch, no accept/decline,
    no read endpoint, and no service in Dr.1.1.E. Status transitions, the
    user/store match invariant (assignment.store_id == order.store_id ==
    driver_profile.store_id), and any uniqueness rule (e.g. one active
    assignment per order) are deferred to Dr.1.1.F — no unique/partial-unique
    constraint is created here because offer fan-out semantics are not frozen.
    """

    __tablename__ = "order_driver_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('offered', 'accepted', 'declined', 'expired', "
            "'assigned', 'started', 'completed', 'canceled')",
            name="ck_order_driver_assignments_status_valid",
        ),
        Index("ix_order_driver_assignments_order_id", "order_id"),
        Index(
            "ix_order_driver_assignments_driver_profile_id",
            "driver_profile_id",
        ),
        Index("ix_order_driver_assignments_store_id", "store_id"),
        Index("ix_order_driver_assignments_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "orders.id",
            name="fk_order_driver_assignments_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    driver_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "driver_profiles.id",
            name="fk_order_driver_assignments_driver_profile_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "stores.id",
            name="fk_order_driver_assignments_store_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    declined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    order: Mapped[Order] = relationship(back_populates="driver_assignments")
    driver_profile: Mapped[DriverProfile] = relationship(
        back_populates="assignments"
    )
    store: Mapped[Store] = relationship(back_populates="driver_assignments")
    # Dr.1.1.G.1 — at most one operational-state row per assignment (the
    # assignment is the anchor; uselist=False makes this a scalar / 1:1).
    operational_state: Mapped[DriverDeliveryOperationalState | None] = (
        relationship(
            back_populates="assignment",
            uselist=False,
        )
    )


class DriverDeliveryOperationalStateValue(str, enum.Enum):
    """Physical operational state of the driver's delivery flow (Dr.1.1.G.1).

    A THIRD, separate axis from the two existing ones, frozen by the Dr.1.1.G
    domain contract:

      - `OrderStatus`                    = commercial/logistics state of the
                                           order.
      - `OrderDriverAssignmentStatus`    = lifecycle of the driver<->order
                                           assignment (offer/accept/...).
      - `DriverDeliveryOperationalState` = physical operational state of the
                                           driver's delivery flow (THIS enum).

    Stored as a VARCHAR + CHECK discriminator (not a PG enum), matching the
    `OrderDriverAssignmentStatus` convention — new states never require an
    `ALTER TYPE`. G.1 is STORAGE ONLY: this enumerates the vocabulary, but no
    transition logic, no action endpoint, and no service writes or advances a
    state in this subphase. Several values (id_verification_pending /
    id_verified, delivery_completed, delivery_failed, returning/returned) are
    forward-declared here for the schema but are only reachable through future
    action phases (pickup / proof / ID-verification / complete / fail /
    return), which are explicitly out of scope for G.1.
    """

    not_started = "not_started"
    en_route_to_store = "en_route_to_store"
    arrived_at_store = "arrived_at_store"
    pickup_started = "pickup_started"
    picked_up = "picked_up"
    en_route_to_customer = "en_route_to_customer"
    arrived_at_customer = "arrived_at_customer"
    id_verification_pending = "id_verification_pending"
    id_verified = "id_verified"
    delivery_completed = "delivery_completed"
    delivery_failed = "delivery_failed"
    returning_to_store = "returning_to_store"
    returned_to_store = "returned_to_store"
    canceled = "canceled"


class DriverDeliveryOperationalState(Base):
    """Dedicated delivery operational-state record (Dr.1.1.G.1).

    The operational state is its OWN entity, anchored 1:1 on an
    `OrderDriverAssignment` (UNIQUE `assignment_id`). It is deliberately NOT a
    column on `orders` or on `order_driver_assignments`: the physical driver
    flow is a third axis that must never overload `OrderStatus` or the
    assignment lifecycle (Dr.1.1.G domain contract).

    `order_id`, `driver_profile_id`, and `store_id` are denormalized off the
    assignment purely so future self-scoped, store-bound reads can filter
    without an extra join — they are read anchors, NOT a license to mutate the
    order. This is a MODEL FOUNDATION only (G.1): there is no service, schema,
    endpoint, or transition logic, and nothing here mutates orders, inventory,
    `OrderStatus`, or the assignment. Proof of delivery, ID verification, GPS,
    and the pickup/complete/fail/return actions are later subphases.

    FK semantics mirror `OrderDriverAssignment`: order_id / store_id CASCADE
    (the state is meaningless without them), driver_profile_id RESTRICT
    (preserve operational history; a profile with state rows is not
    hard-deletable), assignment_id CASCADE (the state is owned by its
    assignment). Mutable, so it carries the shared `set_updated_at` trigger.
    """

    __tablename__ = "driver_delivery_operational_states"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            name="uq_driver_delivery_operational_states_assignment_id",
        ),
        CheckConstraint(
            "state IN ('not_started', 'en_route_to_store', "
            "'arrived_at_store', 'pickup_started', 'picked_up', "
            "'en_route_to_customer', 'arrived_at_customer', "
            "'id_verification_pending', 'id_verified', "
            "'delivery_completed', 'delivery_failed', "
            "'returning_to_store', 'returned_to_store', 'canceled')",
            name="ck_driver_delivery_operational_states_state_valid",
        ),
        # No separate index on assignment_id: the UNIQUE constraint above
        # already creates a unique btree index sufficient for lookups.
        Index(
            "ix_driver_delivery_operational_states_order_id",
            "order_id",
        ),
        Index(
            "ix_driver_delivery_operational_states_driver_profile_id",
            "driver_profile_id",
        ),
        Index(
            "ix_driver_delivery_operational_states_store_id",
            "store_id",
        ),
        Index(
            "ix_driver_delivery_operational_states_state",
            "state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "order_driver_assignments.id",
            name="fk_driver_delivery_operational_states_assignment_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "orders.id",
            name="fk_driver_delivery_operational_states_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    driver_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "driver_profiles.id",
            name="fk_driver_delivery_operational_states_driver_profile_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "stores.id",
            name="fk_driver_delivery_operational_states_store_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String(40),
        server_default=text("'not_started'"),
        nullable=False,
    )
    state_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_transition_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = timestamp_created_at()
    updated_at: Mapped[datetime] = timestamp_updated_at()

    assignment: Mapped[OrderDriverAssignment] = relationship(
        back_populates="operational_state"
    )
    order: Mapped[Order] = relationship(
        back_populates="delivery_operational_states"
    )
    driver_profile: Mapped[DriverProfile] = relationship(
        back_populates="delivery_operational_states"
    )
    store: Mapped[Store] = relationship(
        back_populates="delivery_operational_states"
    )
