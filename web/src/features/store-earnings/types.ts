// Store earnings wire types. 1:1 mirror of
// `backend/app/schemas/earnings.py::StoreEarningsSummary`.

export interface StoreEarningsTopProduct {
  variant_id: string;
  product_name: string;
  variant_label: string | null;
  quantity_sold: number;
  revenue: string;
}

export interface StoreEarningsSummary {
  delivered_orders: number;
  total_items_sold: number;
  product_revenue: string;
  top_products: ReadonlyArray<StoreEarningsTopProduct>;
}
