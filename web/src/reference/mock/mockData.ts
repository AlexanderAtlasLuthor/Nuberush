export interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  category: string;
  image: string;
  storeId: string;
}

export interface Store {
  id: string;
  name: string;
  image: string;
  rating: number;
  reviewCount: number;
  deliveryTime: string;
  distance: string;
  address: string;
  featured: boolean;
  categories: string[];
}

export const categories = [
  { id: "vapes", name: "Vapes", icon: "💨" },
  { id: "cigars", name: "Cigars", icon: "🚬" },
  { id: "e-liquid", name: "E-Liquid", icon: "💧" },
  { id: "hookah", name: "Hookah", icon: "🫧" },
  { id: "wraps", name: "Wraps", icon: "🌿" },
  { id: "glass", name: "Glass", icon: "🔮" },
  { id: "accessories", name: "Accessories", icon: "⚙️" },
];

export const stores: Store[] = [
  {
    id: "cloud-nine",
    name: "Cloud Nine",
    image: "https://images.unsplash.com/photo-1527661591475-527312dd65f5?w=600&h=400&fit=crop",
    rating: 4.8,
    reviewCount: 324,
    deliveryTime: "20-30 min",
    distance: "1.2 mi",
    address: "1450 Collins Ave, Miami Beach, FL",
    featured: true,
    categories: ["vapes", "e-liquid", "accessories"],
  },
  {
    id: "vapor-district",
    name: "Vapor District",
    image: "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=600&h=400&fit=crop",
    rating: 4.6,
    reviewCount: 198,
    deliveryTime: "25-35 min",
    distance: "2.4 mi",
    address: "785 Washington Ave, Miami Beach, FL",
    featured: true,
    categories: ["vapes", "cigars", "hookah", "glass"],
  },
  {
    id: "the-smoke-spot",
    name: "The Smoke Spot",
    image: "https://images.unsplash.com/photo-1579546929518-9e396f3cc809?w=600&h=400&fit=crop",
    rating: 4.9,
    reviewCount: 412,
    deliveryTime: "15-25 min",
    distance: "0.8 mi",
    address: "320 Lincoln Rd, Miami Beach, FL",
    featured: true,
    categories: ["cigars", "wraps", "glass", "accessories"],
  },
];

export const products: Product[] = [
  // Cloud Nine
  { id: "cn-1", name: "Puff Bar Max", description: "5000 puff disposable vape with multiple flavor options. Smooth draw, long-lasting battery.", price: 24.99, category: "vapes", image: "https://images.unsplash.com/photo-1560913210-a2e267cee183?w=400&h=400&fit=crop", storeId: "cloud-nine" },
  { id: "cn-2", name: "Blue Razz E-Liquid", description: "Premium blue raspberry e-liquid. 60ml bottle, 3mg nicotine. Sweet and tangy flavor.", price: 18.99, category: "e-liquid", image: "https://images.unsplash.com/photo-1567922045116-2a00fae2ed03?w=400&h=400&fit=crop", storeId: "cloud-nine" },
  { id: "cn-3", name: "Mango Ice Pod Kit", description: "Refillable pod system with mango ice starter pack. Compact design, USB-C charging.", price: 34.99, category: "vapes", image: "https://images.unsplash.com/photo-1571266028243-e4733b0f0bb0?w=400&h=400&fit=crop", storeId: "cloud-nine" },
  { id: "cn-4", name: "Coil Pack (5pc)", description: "Replacement coils for most standard pod systems. 0.8 ohm mesh coils.", price: 12.99, category: "accessories", image: "https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=400&h=400&fit=crop", storeId: "cloud-nine" },
  { id: "cn-5", name: "Strawberry Cream Juice", description: "Rich strawberry cream e-liquid. 100ml bottle, available in 0, 3, 6mg.", price: 22.99, category: "e-liquid", image: "https://images.unsplash.com/photo-1625772452888-ca794a1cf39f?w=400&h=400&fit=crop", storeId: "cloud-nine" },

  // Vapor District
  { id: "vd-1", name: "Cuban Classic Cigar", description: "Premium hand-rolled cigar with rich, full-bodied flavor. Aged 5 years.", price: 15.99, category: "cigars", image: "https://images.unsplash.com/photo-1589639781073-0e3ef070bae4?w=400&h=400&fit=crop", storeId: "vapor-district" },
  { id: "vd-2", name: "Glass Bubbler Pipe", description: "Handcrafted glass bubbler with percolator. Smooth, filtered experience.", price: 49.99, category: "glass", image: "https://images.unsplash.com/photo-1595341888016-a392ef81b7de?w=400&h=400&fit=crop", storeId: "vapor-district" },
  { id: "vd-3", name: "Hookah Starter Set", description: "Complete hookah set with 2 hoses, tray, and charcoal starter. Modern design.", price: 89.99, category: "hookah", image: "https://images.unsplash.com/photo-1527661591475-527312dd65f5?w=400&h=400&fit=crop", storeId: "vapor-district" },
  { id: "vd-4", name: "Mint Blast Vape", description: "Refreshing mint disposable vape. 3000 puffs, 5% nicotine.", price: 19.99, category: "vapes", image: "https://images.unsplash.com/photo-1560913210-a2e267cee183?w=400&h=400&fit=crop", storeId: "vapor-district" },
  { id: "vd-5", name: "Shisha Flavor Pack", description: "Variety pack with 4 premium shisha flavors: Apple, Grape, Mint, Mixed Berry.", price: 29.99, category: "hookah", image: "https://images.unsplash.com/photo-1567922045116-2a00fae2ed03?w=400&h=400&fit=crop", storeId: "vapor-district" },
  { id: "vd-6", name: "Mini Cigar 5-Pack", description: "Premium mini cigars with natural wrapper. Smooth and mild.", price: 11.99, category: "cigars", image: "https://images.unsplash.com/photo-1589639781073-0e3ef070bae4?w=400&h=400&fit=crop", storeId: "vapor-district" },

  // The Smoke Spot
  { id: "ss-1", name: "Artisan Glass Pipe", description: "Hand-blown borosilicate glass pipe with unique color patterns. Heat resistant.", price: 39.99, category: "glass", image: "https://images.unsplash.com/photo-1595341888016-a392ef81b7de?w=400&h=400&fit=crop", storeId: "the-smoke-spot" },
  { id: "ss-2", name: "Natural Leaf Wraps", description: "Organic natural leaf wraps. Pack of 25. Slow burn, no chemicals.", price: 8.99, category: "wraps", image: "https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=400&h=400&fit=crop", storeId: "the-smoke-spot" },
  { id: "ss-3", name: "Premium Rolling Tray", description: "Large metal rolling tray with magnetic lid. Artistic design.", price: 24.99, category: "accessories", image: "https://images.unsplash.com/photo-1625772452888-ca794a1cf39f?w=400&h=400&fit=crop", storeId: "the-smoke-spot" },
  { id: "ss-4", name: "Maduro Cigar Box", description: "Box of 10 premium maduro cigars. Dark wrapper, complex flavor profile.", price: 54.99, category: "cigars", image: "https://images.unsplash.com/photo-1589639781073-0e3ef070bae4?w=400&h=400&fit=crop", storeId: "the-smoke-spot" },
  { id: "ss-5", name: "Hemp Wraps Variety", description: "Flavored hemp wraps variety pack. Includes Mango, Grape, Natural. 15 wraps.", price: 12.99, category: "wraps", image: "https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=400&h=400&fit=crop", storeId: "the-smoke-spot" },
  { id: "ss-6", name: "Torch Lighter Pro", description: "Triple flame torch lighter with adjustable flame. Refillable, windproof.", price: 16.99, category: "accessories", image: "https://images.unsplash.com/photo-1571266028243-e4733b0f0bb0?w=400&h=400&fit=crop", storeId: "the-smoke-spot" },
];

export const getStoreProducts = (storeId: string) => products.filter(p => p.storeId === storeId);
export const getStore = (storeId: string) => stores.find(s => s.id === storeId);
export const getProduct = (productId: string) => products.find(p => p.id === productId);
