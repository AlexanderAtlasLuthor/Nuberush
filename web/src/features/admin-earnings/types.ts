// Admin earnings wire types.
//
// 1:1 mirror of `backend/app/schemas/earnings.py`. Snake_case matches
// the JSON over the wire. Decimal values arrive as strings (Pydantic
// `Decimal` serialises to string by default) so amounts stay precise.

export interface AdminEarningsStoreBreakdown {
  store_id: string;
  store_name: string;
  delivered_orders: number;
  gross_base: string;
  commission: string;
}

export interface AdminEarningsSummary {
  delivered_orders: number;
  subtotal_total: string;
  delivery_total: string;
  tip_total: string;
  tax_total: string;
  gross_base_total: string;
  commission_total: string;
  customer_paid_total: string;
  commission_rate: string;
  delivery_fee: string;
  by_store: ReadonlyArray<AdminEarningsStoreBreakdown>;
}
