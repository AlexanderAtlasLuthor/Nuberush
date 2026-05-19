from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from datetime import datetime

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
    # record (= the Supabase JWT `sub`). Nullable only during the F2.22.2
    # migration window — existing rows have no Supabase identity yet, and
    # the active login flow still uses `id`/`password_hash`. No cross-schema
    # FK to `auth.users` is declared here: that schema is owned by Supabase
    # and the relationship stays conceptual for this subphase.
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    phone: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
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
