const CACHE_NAME   = 'genx-pos-v2';
const SYNC_TAG     = 'pos-offline-sales';

// Assets to pre-cache for offline use
const PRECACHE_URLS = [
    '/sales/pos/',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
];

// ── INSTALL: pre-cache shell ─────────────────────────────────────────────────
self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            // Attempt best-effort cache — don't fail install if CDN is unavailable
            return Promise.allSettled(
                PRECACHE_URLS.map(url =>
                    cache.add(url).catch(err => console.warn('Pre-cache miss:', url, err))
                )
            );
        })
    );
});

// ── ACTIVATE: clean old caches ──────────────────────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

// ── FETCH: network-first for API, cache-first for assets ────────────────────
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Pass through non-GET and cross-origin requests
    if (event.request.method !== 'GET') return;
    if (url.origin !== self.location.origin &&
        !url.hostname.includes('jsdelivr.net') &&
        !url.hostname.includes('googleapis.com')) return;

    // API calls: network-first, no caching
    if (url.pathname.startsWith('/sales/pos/') ||
        url.pathname.startsWith('/inventory/api/')) {
        event.respondWith(
            fetch(event.request).catch(() =>
                // Return empty JSON for search/scan when offline
                new Response(JSON.stringify({ products: [], found: false, offline: true }), {
                    headers: { 'Content-Type': 'application/json' }
                })
            )
        );
        return;
    }

    // Static assets / CDN: cache-first
    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) return cached;
            return fetch(event.request).then(response => {
                if (!response || response.status !== 200 || response.type === 'error') {
                    return response;
                }
                const toCache = response.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(event.request, toCache));
                return response;
            });
        })
    );
});

// ── BACKGROUND SYNC: replay queued offline sales ─────────────────────────────
self.addEventListener('sync', event => {
    if (event.tag === SYNC_TAG) {
        event.waitUntil(replayOfflineSales());
    }
});

async function replayOfflineSales() {
    const db      = await openDB();
    const pending = await getAllPending(db);

    for (const sale of pending) {
        try {
            const res = await fetch('/sales/pos/complete/', {
                method:  'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken':  sale.csrf,
                },
                body: JSON.stringify(sale.payload),
            });

            if (res.ok) {
                const data = await res.json();
                if (data.success) {
                    await deletePending(db, sale.id);
                    // Notify open POS windows about the synced sale
                    const clients = await self.clients.matchAll();
                    clients.forEach(client => client.postMessage({
                        type:           'SALE_SYNCED',
                        receipt_number: data.receipt_number,
                        offline_id:     sale.id,
                    }));
                }
            }
        } catch (err) {
            // Network still down — leave in queue, try next sync
            console.warn('Sync failed for offline sale', sale.id, err);
        }
    }
}

// ── INDEXEDDB HELPERS ────────────────────────────────────────────────────────
function openDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open('genx-pos-offline', 1);
        req.onupgradeneeded = e => {
            const db    = e.target.result;
            if (!db.objectStoreNames.contains('pending_sales')) {
                const store = db.createObjectStore('pending_sales', {
                    keyPath:       'id',
                    autoIncrement: true,
                });
                store.createIndex('created_at', 'created_at');
            }
        };
        req.onsuccess = e => resolve(e.target.result);
        req.onerror   = e => reject(e.target.error);
    });
}

function getAllPending(db) {
    return new Promise((resolve, reject) => {
        const tx    = db.transaction('pending_sales', 'readonly');
        const store = tx.objectStore('pending_sales');
        const req   = store.getAll();
        req.onsuccess = e => resolve(e.target.result);
        req.onerror   = e => reject(e.target.error);
    });
}

function deletePending(db, id) {
    return new Promise((resolve, reject) => {
        const tx    = db.transaction('pending_sales', 'readwrite');
        const store = tx.objectStore('pending_sales');
        const req   = store.delete(id);
        req.onsuccess = () => resolve();
        req.onerror   = e => reject(e.target.error);
    });
}