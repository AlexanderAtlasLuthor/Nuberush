"""Service layer for the earnings surfaces.

Computes `AdminEarningsSummary` and `StoreEarningsSummary` from
`orders` + `order_items` filtered to delivered orders. Read-only: no
`db.add`, no `db.commit`, no model changes. The pricing rule is
encoded as module constants so a future migration that adds real
`delivery_fee` / `tip_amount` columns to `Order` can replace those
constants with summed columns without changing the public contract.

Pricing rule (locked):

  gross_base       = subtotal + delivery + tip + taxes
  commission       = COMMISSION_RATE * gross_base
  customer_paid    = gross_base + commission

Filter (locked):

  Only orders with `Order.status = delivered` count toward earnings.
  This matches the pattern already in use in
  `app.services.admin_settings` (delivered-orders aggregator).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Order
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.earnings import AdminEarningsStoreBreakdown
from app.schemas.earnings import AdminEarningsSummary
from app.schemas.earnings import StoreEarningsSummary
from app.schemas.earnings import StoreEarningsTopProduct


# Pricing constants. Module-local on purpose so the wire contract is
# unaffected when a future migration replaces them with summed columns.
COMMISSION_RATE: Decimal = Decimal("0.20")
DELIVERY_FEE_USD: Decimal = Decimal("10.00")
TIP_AMOUNT_USD: Decimal = Decimal("0.00")

# Bounded breakdown tail. Service-owned invariant, not caller-tunable.
_BY_STORE_LIMIT = 10
_TOP_PRODUCTS_LIMIT = 10


def _assert_admin_caller(actor: User) -> None:
    """RBAC gate. Mirrors `app.services.admin_dashboard._assert_admin_caller`."""
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


def _quantize_money(value: Decimal) -> Decimal:
    """Round a money value to two decimal places (banker's rounding off).

    Numeric(10, 2) columns already enforce two decimals on stored rows;
    arithmetic over them (multiplication by the commission rate) can
    produce more precision, so we quantise the derived values before
    they leave the service.
    """
    return value.quantize(Decimal("0.01"))


def get_admin_earnings_summary(
    db: Session,
    *,
    actor: User,
) -> AdminEarningsSummary:
    """Platform-wide earnings summary for the admin caller."""
    _assert_admin_caller(actor)

    delivered_filter = Order.status == OrderStatus.delivered

    totals_stmt = select(
        func.count(Order.id),
        func.coalesce(func.sum(Order.subtotal_amount), 0),
        func.coalesce(func.sum(Order.tax_amount), 0),
    ).where(delivered_filter)
    delivered_count_raw, subtotal_total_raw, tax_total_raw = db.execute(
        totals_stmt
    ).one()

    delivered_orders = int(delivered_count_raw or 0)
    subtotal_total = Decimal(subtotal_total_raw or 0)
    tax_total = Decimal(tax_total_raw or 0)
    delivery_total = DELIVERY_FEE_USD * delivered_orders
    tip_total = TIP_AMOUNT_USD * delivered_orders
    gross_base_total = (
        subtotal_total + delivery_total + tip_total + tax_total
    )
    commission_total = _quantize_money(
        gross_base_total * COMMISSION_RATE
    )
    customer_paid_total = gross_base_total + commission_total

    breakdown_stmt = (
        select(
            Order.store_id,
            Store.name,
            func.count(Order.id),
            func.coalesce(func.sum(Order.subtotal_amount), 0),
            func.coalesce(func.sum(Order.tax_amount), 0),
        )
        .join(Store, Store.id == Order.store_id)
        .where(delivered_filter)
        .group_by(Order.store_id, Store.name)
    )
    by_store_rows: list[AdminEarningsStoreBreakdown] = []
    for store_id, store_name, count_raw, subtotal_raw, tax_raw in db.execute(
        breakdown_stmt
    ).all():
        store_delivered = int(count_raw or 0)
        store_subtotal = Decimal(subtotal_raw or 0)
        store_tax = Decimal(tax_raw or 0)
        store_gross_base = (
            store_subtotal
            + DELIVERY_FEE_USD * store_delivered
            + TIP_AMOUNT_USD * store_delivered
            + store_tax
        )
        store_commission = _quantize_money(
            store_gross_base * COMMISSION_RATE
        )
        by_store_rows.append(
            AdminEarningsStoreBreakdown(
                store_id=store_id,
                store_name=store_name,
                delivered_orders=store_delivered,
                gross_base=_quantize_money(store_gross_base),
                commission=store_commission,
            )
        )
    by_store_rows.sort(key=lambda r: r.commission, reverse=True)
    by_store_rows = by_store_rows[:_BY_STORE_LIMIT]

    return AdminEarningsSummary(
        delivered_orders=delivered_orders,
        subtotal_total=_quantize_money(subtotal_total),
        delivery_total=_quantize_money(delivery_total),
        tip_total=_quantize_money(tip_total),
        tax_total=_quantize_money(tax_total),
        gross_base_total=_quantize_money(gross_base_total),
        commission_total=commission_total,
        customer_paid_total=_quantize_money(customer_paid_total),
        commission_rate=COMMISSION_RATE,
        delivery_fee=DELIVERY_FEE_USD,
        by_store=by_store_rows,
    )


def get_store_earnings_summary(
    db: Session,
    *,
    store_id: UUID,
) -> StoreEarningsSummary:
    """Earnings summary as seen by a single store.

    Stores only see products sold (units + product revenue). Delivery
    fee, tips, taxes and platform commission are intentionally absent.
    """
    delivered_filter = (
        (Order.status == OrderStatus.delivered) & (Order.store_id == store_id)
    )

    totals_stmt = (
        select(
            func.count(func.distinct(Order.id)),
            func.coalesce(func.sum(OrderItem.quantity), 0),
            func.coalesce(func.sum(OrderItem.line_total), 0),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .where(delivered_filter)
    )
    delivered_orders_raw, items_sold_raw, revenue_raw = db.execute(
        totals_stmt
    ).one()

    top_products_stmt = (
        select(
            OrderItem.variant_id,
            Product.name,
            ProductVariant.flavor,
            ProductVariant.size_label,
            func.coalesce(func.sum(OrderItem.quantity), 0),
            func.coalesce(func.sum(OrderItem.line_total), 0),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(ProductVariant, ProductVariant.id == OrderItem.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(delivered_filter)
        .group_by(
            OrderItem.variant_id,
            Product.name,
            ProductVariant.flavor,
            ProductVariant.size_label,
        )
        .order_by(func.sum(OrderItem.line_total).desc())
        .limit(_TOP_PRODUCTS_LIMIT)
    )
    top_products: list[StoreEarningsTopProduct] = []
    for (
        variant_id,
        product_name,
        flavor,
        size_label,
        qty_raw,
        revenue_row_raw,
    ) in db.execute(top_products_stmt).all():
        variant_label_parts = [p for p in (flavor, size_label) if p]
        variant_label = " · ".join(variant_label_parts) if variant_label_parts else None
        top_products.append(
            StoreEarningsTopProduct(
                variant_id=variant_id,
                product_name=product_name,
                variant_label=variant_label,
                quantity_sold=int(qty_raw or 0),
                revenue=_quantize_money(Decimal(revenue_row_raw or 0)),
            )
        )

    return StoreEarningsSummary(
        delivered_orders=int(delivered_orders_raw or 0),
        total_items_sold=int(items_sold_raw or 0),
        product_revenue=_quantize_money(Decimal(revenue_raw or 0)),
        top_products=top_products,
    )
