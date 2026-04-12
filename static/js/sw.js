const CACHE_VERSION = 'genx-pos-v5';
const STATIC_CACHE  = CACHE_VERSION + '-static';
const DYNAMIC_CACHE = CACHE_VERSION + '-dynamic';
const SYNC_TAG      = 'pos-offline-sales';

const PRECACHE_URLS = [
  '/sales/pos/',
  '/static/css/genx-design-system.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
  'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap',
];

// ── INSTALL ──────────────────────────────────────────────
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache =>
      Promise.allSettled(PRECACHE_URLS.map(url =>
        cache.add(url).catch(err => console.warn('[SW] Pre-cache miss:', url, err))
      ))
    )
  );
});

// ── ACTIVATE ─────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== STATIC_CACHE && k !== DYNAMIC_CACHE).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── FETCH ─────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;

  // POS API calls: network-first, offline fallback
  if (url.pathname.startsWith('/sales/pos/') || url.pathname.startsWith('/inventory/api/') || url.pathname.startsWith('/customers/api/')) {
    event.respondWith(
      fetch(request)
        .then(resp => {
          if (resp.ok) {
            const clone = resp.clone();
            caches.open(DYNAMIC_CACHE).then(c => c.put(request, clone));
          }
          return resp;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          if (cached) return cached;
          return new Response(JSON.stringify({ products: [], found: false, offline: true, error: 'Offline' }), {
            headers: { 'Content-Type': 'application/json', 'X-From-Cache': 'true' }
          });
        })
    );
    return;
  }

  // Receipt & sale API: network-first
  if (url.pathname.includes('/receipt/') || url.pathname.startsWith('/sales/pos/complete')) {
    event.respondWith(fetch(request).catch(() => caches.match(request)));
    return;
  }

  // Static assets: cache-first
  if (url.hostname.includes('jsdelivr') || url.hostname.includes('fonts.g') || url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(resp => {
          if (resp?.ok) {
            const clone = resp.clone();
            caches.open(STATIC_CACHE).then(c => c.put(request, clone));
          }
          return resp;
        });
      })
    );
    return;
  }

  // Everything else: network-first with dynamic cache
  event.respondWith(
    fetch(request)
      .then(resp => {
        if (resp.ok && resp.type !== 'opaque') {
          const clone = resp.clone();
          caches.open(DYNAMIC_CACHE).then(c => {
            c.put(request, clone);
            trimCache(DYNAMIC_CACHE, 60);
          });
        }
        return resp;
      })
      .catch(() => caches.match(request))
  );
});

// ── BACKGROUND SYNC ───────────────────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(replayOfflineSales());
  }
});

async function replayOfflineSales() {
  const db = await openDB();
  const pending = await getAllPending(db);
  const results = { synced: 0, failed: 0 };

  for (const sale of pending) {
    try {
      const resp = await fetch('/sales/pos/complete/', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': sale.csrf },
        body: JSON.stringify(sale.payload)
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.success) {
          await deletePending(db, sale.id);
          results.synced++;
          const clients = await self.clients.matchAll();
          clients.forEach(c => c.postMessage({ type: 'SALE_SYNCED', receipt_number: data.receipt_number, offline_id: sale.id }));
        } else { results.failed++; }
      } else { results.failed++; }
    } catch { results.failed++; }
  }

  if (results.synced > 0 || results.failed > 0) {
    const clients = await self.clients.matchAll();
    clients.forEach(c => c.postMessage({ type: 'SYNC_COMPLETE', ...results }));
  }
}

// ── PUSH NOTIFICATIONS ────────────────────────────────────
self.addEventListener('push', event => {
  if (!event.data) return;
  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || 'GenX POS', {
      body:  data.body || '',
      icon:  data.icon || '/static/icons/icon-192.png',
      badge: '/static/icons/badge-72.png',
      tag:   data.tag || 'genx-notification',
      data:  data,
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data?.url || '/sales/pos/';
  event.waitUntil(clients.openWindow(url));
});

// ── CACHE TRIMMING ────────────────────────────────────────
async function trimCache(cacheName, maxEntries) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length > maxEntries) {
    await Promise.all(keys.slice(0, keys.length - maxEntries).map(k => cache.delete(k)));
  }
}

// ── INDEXEDDB HELPERS ─────────────────────────────────────
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('genx-pos-v5', 2);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pending_sales')) {
        const store = db.createObjectStore('pending_sales', { keyPath: 'id', autoIncrement: true });
        store.createIndex('created_at', 'created_at');
        store.createIndex('status', 'status');
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

function getAllPending(db) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending_sales', 'readonly');
    const req = tx.objectStore('pending_sales').getAll();
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

function deletePending(db, id) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending_sales', 'readwrite');
    const req = tx.objectStore('pending_sales').delete(id);
    req.onsuccess = () => resolve();
    req.onerror   = e => reject(e.target.error);
  });
}
