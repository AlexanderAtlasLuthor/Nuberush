export interface OrderLineItem {
  name: string;
  qty: number;
  price: number;
  image: string;
}

export interface OrderDetail {
  id: string;
  store: string;
  storeAddress: string;
  date: string;
  deliveredAt: string;
  status: 'Delivered' | 'Cancelled' | 'In Transit';
  items: OrderLineItem[];
  subtotal: number;
  deliveryFee: number;
  serviceFee: number;
  tax: number;
  tip: number;
  total: number;
  deliveryAddress: string;
  paymentMethod: string;
  driverName?: string;
}

export const pastOrders: OrderDetail[] = [
  {
    id: '#1038',
    store: 'Cloud Nine',
    storeAddress: '1450 Collins Ave, Miami Beach, FL',
    date: 'Mar 28, 2026',
    deliveredAt: 'Mar 28, 2026 · 7:42 PM',
    status: 'Delivered',
    items: [
      { name: 'JUUL Starter Kit', qty: 1, price: 29.99, image: 'https://images.unsplash.com/photo-1560913210-a2e267cee183?w=200&h=200&fit=crop' },
      { name: 'Mango Pods', qty: 1, price: 13.99, image: 'https://images.unsplash.com/photo-1571266028243-e4733b0f0bb0?w=200&h=200&fit=crop' },
    ],
    subtotal: 43.98,
    deliveryFee: 4.99,
    serviceFee: 1.99,
    tax: 3.08,
    tip: 3.0,
    total: 57.04,
    deliveryAddress: '520 Ocean Dr, Miami Beach, FL 33139',
    paymentMethod: 'Visa •••• 4242',
    driverName: 'Marcus T.',
  },
  {
    id: '#1035',
    store: 'Vapor District',
    storeAddress: '785 Washington Ave, Miami Beach, FL',
    date: 'Mar 25, 2026',
    deliveredAt: 'Mar 25, 2026 · 5:18 PM',
    status: 'Delivered',
    items: [
      { name: 'Blue Razz Ice 5000', qty: 1, price: 24.99, image: 'https://images.unsplash.com/photo-1567922045116-2a00fae2ed03?w=200&h=200&fit=crop' },
    ],
    subtotal: 24.99,
    deliveryFee: 4.99,
    serviceFee: 1.99,
    tax: 1.75,
    tip: 2.0,
    total: 35.72,
    deliveryAddress: '520 Ocean Dr, Miami Beach, FL 33139',
    paymentMethod: 'Mastercard •••• 8888',
    driverName: 'Jenna L.',
  },
  {
    id: '#1030',
    store: 'The Smoke Spot',
    storeAddress: '320 Lincoln Rd, Miami Beach, FL',
    date: 'Mar 20, 2026',
    deliveredAt: 'Mar 20, 2026 · 8:55 PM',
    status: 'Delivered',
    items: [
      { name: 'Arturo Fuente Short Story', qty: 1, price: 32.99, image: 'https://images.unsplash.com/photo-1589639781073-0e3ef070bae4?w=200&h=200&fit=crop' },
      { name: 'Cohiba Red Dot', qty: 1, price: 34.98, image: 'https://images.unsplash.com/photo-1589639781073-0e3ef070bae4?w=200&h=200&fit=crop&sig=2' },
    ],
    subtotal: 67.97,
    deliveryFee: 4.99,
    serviceFee: 1.99,
    tax: 4.76,
    tip: 5.0,
    total: 84.71,
    deliveryAddress: '520 Ocean Dr, Miami Beach, FL 33139',
    paymentMethod: 'Visa •••• 4242',
    driverName: 'Carlos R.',
  },
];

export const getOrder = (id: string) =>
  pastOrders.find((o) => o.id === id || o.id.replace('#', '') === id.replace('#', ''));
