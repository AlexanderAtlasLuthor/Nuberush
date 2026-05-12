export type MerchantOrderStatus = 'new' | 'preparing' | 'ready' | 'completed' | 'canceled';

export interface MerchantOrderItem {
  name: string;
  qty: number;
  price: number;
}

export interface MerchantOrder {
  id: string;
  customer: string;
  customerPhone: string;
  address: string;
  items: MerchantOrderItem[];
  subtotal: number;
  tax: number;
  deliveryFee: number;
  total: number;
  paymentMethod: string;
  time: string;
  placedAt: string;
  status: MerchantOrderStatus;
  driver?: string;
  notes?: string;
}

export const merchantOrders: MerchantOrder[] = [
  {
    id: '#1042',
    customer: 'John D.',
    customerPhone: '+1 (305) 555-0142',
    address: '1240 Ocean Dr, Apt 4B, Miami Beach, FL 33139',
    items: [
      { name: 'JUUL Starter Kit', qty: 1, price: 29.99 },
      { name: 'Mango Pods (4-pack)', qty: 1, price: 13.99 },
    ],
    subtotal: 43.98,
    tax: 3.08,
    deliveryFee: 4.99,
    total: 52.05,
    paymentMethod: 'Visa •••• 4242',
    time: '2 min ago',
    placedAt: 'Today, 2:14 PM',
    status: 'new',
    notes: 'Please ring twice — apartment buzzer is broken.',
  },
  {
    id: '#1043',
    customer: 'Sarah M.',
    customerPhone: '+1 (305) 555-0188',
    address: '825 Brickell Ave, Miami, FL 33131',
    items: [{ name: 'Blue Razz Ice 5000', qty: 1, price: 24.99 }],
    subtotal: 24.99,
    tax: 1.75,
    deliveryFee: 4.99,
    total: 31.73,
    paymentMethod: 'Apple Pay',
    time: '5 min ago',
    placedAt: 'Today, 2:11 PM',
    status: 'new',
  },
  {
    id: '#1041',
    customer: 'Mike R.',
    customerPhone: '+1 (305) 555-0210',
    address: '320 Lincoln Rd, Miami Beach, FL 33139',
    items: [
      { name: 'Arturo Fuente', qty: 2, price: 18.99 },
      { name: 'Cohiba Red Dot', qty: 1, price: 24.99 },
      { name: 'Cigar Cutter', qty: 1, price: 5.00 },
    ],
    subtotal: 67.97,
    tax: 4.76,
    deliveryFee: 4.99,
    total: 77.72,
    paymentMethod: 'Mastercard •••• 8821',
    time: '8 min ago',
    placedAt: 'Today, 2:08 PM',
    status: 'preparing',
    driver: 'Carlos M.',
  },
  {
    id: '#1040',
    customer: 'Lisa K.',
    customerPhone: '+1 (305) 555-0177',
    address: '500 Alton Rd, Miami Beach, FL 33139',
    items: [{ name: 'Grape Ice Pods', qty: 1, price: 18.99 }],
    subtotal: 18.99,
    tax: 1.33,
    deliveryFee: 4.99,
    total: 25.31,
    paymentMethod: 'Visa •••• 9988',
    time: '15 min ago',
    placedAt: 'Today, 2:01 PM',
    status: 'ready',
    driver: 'Diego R.',
  },
  {
    id: '#1038',
    customer: 'Tom W.',
    customerPhone: '+1 (305) 555-0163',
    address: '1450 Collins Ave, Miami Beach, FL 33139',
    items: [{ name: 'Hookah Charcoal', qty: 2, price: 6.49 }],
    subtotal: 12.99,
    tax: 0.91,
    deliveryFee: 4.99,
    total: 18.89,
    paymentMethod: 'Cash on Delivery',
    time: '1 hr ago',
    placedAt: 'Today, 1:14 PM',
    status: 'completed',
    driver: 'Luis T.',
  },
];

export const getMerchantOrder = (id: string) =>
  merchantOrders.find((o) => o.id === id || o.id === `#${id}` || o.id.replace('#', '') === id);
