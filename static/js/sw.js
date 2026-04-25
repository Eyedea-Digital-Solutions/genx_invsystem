const CACHE_VERSION = 'genx-pos-v6';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DYNAMIC_CACHE = `${CACHE_VERSION}-dynamic`;
const DB_NAME = 'genx-pos-v6';
const DB_VERSION = 3;
const SALES_STORE = 'pending_sales';
const STOCK_TAKE_STORE = 'pending_stock_takes';
const SYNC_TAG = 'genx-offline-sync';

const PRECACHE_URLS = [
  '/',
  '/dashboard/',
  '/sales/pos/',
  '/inventory/',
  '/inventory/stock-take/',
  '/inventory/stock-take/new/',
  '/static/css/genx-design-system.css',
  '/static/css/premium-features.css',
  '/static/js/app.js',
  '/static/js/offline.js',
  '/static/icons/icon-192.png',
  '/static/icons/badge-72.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache =>
      Promise.allSettled(
        PRECACHE_URLS.map(url => cache.add(url).catch(err => console.warn('[SW] Pre-cache miss:', url, err)))
      )
    )
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => ![STATIC_CACHE, DYNAMIC_CACHE].includes(key)).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;

  if (url.pathname.startsWith('/inventory/api/products-for-count/')) {
    event.respondWith(networkFirstJson(request, { products: [], offline: true, error: 'Offline' }));
    return;
  }

  if (
    url.pathname.startsWith('/sales/pos/') ||
    url.pathname.startsWith('/inventory/api/') ||
    url.pathname.startsWith('/customers/api/')
  ) {
    event.respondWith(networkFirstJson(request, { products: [], found: false, offline: true, error: 'Offline' }));
    return;
  }

  if (url.pathname.includes('/receipt/') || url.pathname.startsWith('/sales/pos/complete')) {
    event.respondWith(fetch(request).catch(() => caches.match(request)));
    return;
  }

  if (
    url.pathname.startsWith('/static/') ||
    url.hostname.includes('jsdelivr') ||
    url.hostname.includes('fonts.googleapis') ||
    url.hostname.includes('fonts.gstatic')
  ) {
    event.respondWith(cacheFirst(request));
    return;
  }

  event.respondWith(networkFirstPage(request));
});

self.addEventListener('sync', event => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(replayOfflineWork());
  }
});

async function networkFirstJson(request, fallbackPayload) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify(fallbackPayload), {
      headers: { 'Content-Type': 'application/json', 'X-From-Cache': 'true' },
    });
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) {
    const cache = await caches.open(STATIC_CACHE);
    cache.put(request, response.clone());
  }
  return response;
}

async function networkFirstPage(request) {
  try {
    const response = await fetch(request);
    if (response.ok && response.type !== 'opaque') {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
      trimCache(DYNAMIC_CACHE, 80);
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    const fallback = await caches.match('/inventory/stock-take/') || await caches.match('/dashboard/') || await caches.match('/');
    return fallback || Response.error();
  }
}

async function replayOfflineWork() {
  const db = await openDB();
  const sales = await getAll(db, SALES_STORE);
  const stockTakes = await getAll(db, STOCK_TAKE_STORE);
  const results = {
    synced_sales: 0,
    failed_sales: 0,
    synced_stock_takes: 0,
    failed_stock_takes: 0,
  };

  for (const sale of sales) {
    try {
      const response = await fetch('/sales/pos/complete/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': sale.csrf || '' },
        body: JSON.stringify(sale.payload),
      });
      const data = await response.json();
      if (data.success) {
        await deleteRecord(db, SALES_STORE, sale.id);
        results.synced_sales++;
        notifyClients({ type: 'SALE_SYNCED', receipt_number: data.receipt_number });
      } else {
        results.failed_sales++;
      }
    } catch {
      results.failed_sales++;
    }
  }

  for (const stockTake of stockTakes) {
    try {
      const response = await fetch('/inventory/api/stock-take/submit/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': stockTake.csrf || '' },
        body: JSON.stringify(stockTake.payload),
        credentials: 'include',
      });
      const data = await response.json();
      if (data.ok) {
        await deleteRecord(db, STOCK_TAKE_STORE, stockTake.id);
        results.synced_stock_takes++;
        notifyClients({ type: 'STOCK_TAKE_SYNCED', stock_take_id: data.stock_take_id });
      } else {
        results.failed_stock_takes++;
      }
    } catch {
      results.failed_stock_takes++;
    }
  }

  if (
    results.synced_sales ||
    results.failed_sales ||
    results.synced_stock_takes ||
    results.failed_stock_takes
  ) {
    notifyClients({ type: 'SYNC_COMPLETE', ...results });
  }
}

async function notifyClients(message) {
  const clients = await self.clients.matchAll();
  clients.forEach(client => client.postMessage(message));
}

async function trimCache(cacheName, maxEntries) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length > maxEntries) {
    await Promise.all(keys.slice(0, keys.length - maxEntries).map(key => cache.delete(key)));
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = event => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(SALES_STORE)) {
        db.createObjectStore(SALES_STORE, { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(STOCK_TAKE_STORE)) {
        db.createObjectStore(STOCK_TAKE_STORE, { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains('inventory_cache')) {
        db.createObjectStore('inventory_cache', { keyPath: 'key' });
      }
    };
    req.onsuccess = event => resolve(event.target.result);
    req.onerror = event => reject(event.target.error);
  });
}

function getAll(db, storeName) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).getAll();
    req.onsuccess = event => resolve(event.target.result || []);
    req.onerror = event => reject(event.target.error);
  });
}

function deleteRecord(db, storeName, key) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const req = tx.objectStore(storeName).delete(key);
    req.onsuccess = () => resolve();
    req.onerror = event => reject(event.target.error);
  });
}
