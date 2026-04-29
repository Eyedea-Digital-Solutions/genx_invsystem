'use strict';

const OfflineSync = (() => {

    const DB_NAME        = 'genx-pos-v6';
    const DB_VERSION     = 3;
    const SALES_STORE    = 'pending_sales';
    const ST_STORE       = 'pending_stock_takes';
    const CACHE_STORE    = 'inventory_cache';
    const SYNC_TAG       = 'genx-offline-sync';
    const SYNC_INTERVAL  = 30_000; // 30 s fallback poll

    let _db          = null;
    let _online      = navigator.onLine;
    let _syncTimer   = null;
    let _listeners   = [];

    /* ─────────────────────────────────────────────── PUBLIC API ── */

    async function init() {
        _db = await _openDB();
        _setupNetworkListeners();
        _updateUI();
        await _registerServiceWorker();
        _listenSWMessages();
        _startSyncPoller();

        const [sales, sts] = await Promise.all([countPending(), countPendingST()]);
        if (sales + sts > 0) _toast(`${sales + sts} offline item(s) queued — tap Sync Now to send.`, 'warning');
        return { online: _online, pending_sales: sales, pending_stock_takes: sts };
    }

    function isOnline() { return _online; }

    /**
     * Queue a sale payload for later submission.
     * @returns {number} IndexedDB id
     */
    async function queueSale(payload, csrf) {
        const id = await _put(SALES_STORE, { payload, csrf, ts: Date.now(), retries: 0 });
        _updateUI();
        _toast(`Sale saved offline — will sync when connected.`, 'warning');
        return id;
    }

    async function queueStockTake(payload) {
        const id = await _put(ST_STORE, {
            payload,
            csrf: _csrf(),
            ts:   Date.now(),
            retries: 0,
        });
        _updateUI();
        _toast(`Stock take saved offline — will sync when connected.`, 'warning');
        return id;
    }

    async function cacheProducts(key, products) {
        if (!_db || !key) return;
        await _putRecord(CACHE_STORE, { key, products, ts: Date.now() });
    }

    async function getCachedProducts(key) {
        if (!_db || !key) return null;
        return _getRecord(CACHE_STORE, key);
    }

    async function countPending()   { return _count(SALES_STORE); }
    async function countPendingST() { return _count(ST_STORE); }

    /** Attempt an immediate sync of all queued items */
    async function syncNow(opts = {}) {
        if (!_online) {
            _toast('Still offline — will sync automatically when connected.', 'warning');
            return;
        }
        return _sync(opts);
    }

    /* ────────────────────────────────────────────── INTERNALS ── */

    async function _sync(opts = {}) {
        const sales  = await _getAll(SALES_STORE);
        const stockT = await _getAll(ST_STORE);

        if (!sales.length && !stockT.length) return;

        let syncedSales = 0, failedSales = 0;
        let syncedST    = 0, failedST    = 0;

        /* ── Sales ── */
        for (const rec of sales) {
            if (rec.retries >= 5) {
                // Give up after 5 attempts — delete and toast
                await _del(SALES_STORE, rec.id);
                failedSales++;
                continue;
            }
            try {
                const csrf = rec.csrf || _csrf();
                const resp = await fetch('/sales/pos/complete/', {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body:    JSON.stringify(rec.payload),
                    credentials: 'same-origin',
                });
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();
                if (data.success) {
                    await _del(SALES_STORE, rec.id);
                    syncedSales++;
                    _notifyListeners('sale_synced', { receipt_number: data.receipt_number });
                } else {
                    await _incRetry(SALES_STORE, rec);
                    failedSales++;
                }
            } catch (e) {
                await _incRetry(SALES_STORE, rec);
                failedSales++;
            }
        }

        /* ── Stock Takes ── */
        for (const rec of stockT) {
            if (rec.retries >= 5) { await _del(ST_STORE, rec.id); failedST++; continue; }
            try {
                const csrf = rec.csrf || _csrf();
                const resp = await fetch('/inventory/api/stock-take/submit/', {
                    method:      'POST',
                    headers:     { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body:        JSON.stringify(rec.payload),
                    credentials: 'same-origin',
                });
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();
                if (data.ok) {
                    await _del(ST_STORE, rec.id);
                    syncedST++;
                    _notifyListeners('stock_take_synced', {});
                } else {
                    await _incRetry(ST_STORE, rec);
                    failedST++;
                }
            } catch (e) {
                await _incRetry(ST_STORE, rec);
                failedST++;
            }
        }

        _updateUI();

        if (syncedSales + syncedST > 0) {
            _toast(`Synced: ${syncedSales} sale(s), ${syncedST} stock take(s) ✓`, 'success');
        }
        if (failedSales + failedST > 0 && !opts.silent) {
            _toast(`${failedSales + failedST} item(s) failed to sync.`, 'danger');
        }
    }

    /* ── Network listeners ─────────────────────────────────────── */

    function _setupNetworkListeners() {
        window.addEventListener('online', async () => {
            _online = true;
            _updateUI();
            _toast('Back online — syncing…', 'info');
            await _sync();
        });
        window.addEventListener('offline', () => {
            _online = false;
            _updateUI();
            _toast('Offline — sales will be saved locally.', 'warning');
        });
    }

    /* ── Sync poller (fallback when SW background sync unavailable) */

    function _startSyncPoller() {
        if (_syncTimer) clearInterval(_syncTimer);
        _syncTimer = setInterval(async () => {
            if (!_online) return;
            const n = await countPending() + await countPendingST();
            if (n > 0) await _sync({ silent: true });
        }, SYNC_INTERVAL);
    }

    /* ── Service Worker ────────────────────────────────────────── */

    async function _registerServiceWorker() {
        if (!('serviceWorker' in navigator)) return;
        try {
            const reg = await navigator.serviceWorker.register('/static/js/sw.js', { scope: '/' });
            // Request background sync when going online
            window.addEventListener('online', async () => {
                if ('SyncManager' in window) {
                    try { await reg.sync.register(SYNC_TAG); } catch(_) {}
                }
            });
        } catch (e) {
            console.warn('[OfflineSync] SW registration failed:', e);
        }
    }

    function _listenSWMessages() {
        if (!('serviceWorker' in navigator)) return;
        navigator.serviceWorker.addEventListener('message', e => {
            const { type } = e.data || {};
            if (type === 'SALE_SYNCED') {
                _toast(`Offline sale synced: ${e.data.receipt_number}`, 'success');
                _updateUI();
            } else if (type === 'SYNC_COMPLETE') {
                const { synced_sales=0, synced_stock_takes=0, failed_sales=0 } = e.data;
                if (synced_sales + synced_stock_takes)
                    _toast(`Synced ${synced_sales} sale(s), ${synced_stock_takes} stock take(s)`, 'success');
                if (failed_sales)
                    _toast(`${failed_sales} sale(s) failed to sync`, 'warning');
                _updateUI();
            }
        });
    }

    /* ── UI Updates ────────────────────────────────────────────── */

    function _updateUI() {
        Promise.all([countPending(), countPendingST()]).then(([sales, sts]) => {
            const total = sales + sts;

            // PWA status badge
            const pwa = document.getElementById('pwa-status');
            if (pwa) {
                if (!_online) {
                    pwa.textContent  = '● OFFLINE';
                    pwa.style.background = 'rgba(239,68,68,.15)';
                    pwa.style.color  = '#ef4444';
                    pwa.style.borderColor= 'rgba(239,68,68,.3)';
                } else if (total > 0) {
                    pwa.textContent  = `↑ ${total} QUEUED`;
                    pwa.style.background = 'rgba(245,158,11,.15)';
                    pwa.style.color  = '#f59e0b';
                    pwa.style.borderColor= 'rgba(245,158,11,.3)';
                } else {
                    pwa.textContent  = '● ONLINE';
                    pwa.style.background = 'rgba(74,222,128,.12)';
                    pwa.style.color  = '#4ade80';
                    pwa.style.borderColor= 'rgba(74,222,128,.25)';
                }
            }

            // Offline banner
            const banner = document.getElementById('offline-banner');
            if (banner) {
                const show = !_online || total > 0;
                banner.classList.toggle('show', show);
                const msg = banner.querySelector('span');
                if (msg) {
                    if (!_online) msg.textContent = 'Offline — sales are saved locally and will sync automatically.';
                    else if (total > 0) msg.textContent = `${total} item(s) queued for sync.`;
                }
            }

            // Sync count badge
            const sc = document.getElementById('sync-count');
            if (sc) {
                sc.textContent = total > 0 ? total : '';
                sc.classList.toggle('show', total > 0);
            }
        });
    }

    /* ── Listeners (for POS to observe) ───────────────────────── */

    function addListener(fn) { _listeners.push(fn); }

    function _notifyListeners(event, data) {
        for (const fn of _listeners) { try { fn(event, data); } catch(_) {} }
    }

    /* ── Toast ─────────────────────────────────────────────────── */

    function _toast(msg, type = 'info') {
        if (window.showToast) { window.showToast(msg, type); return; }
        console.log(`[OfflineSync][${type}] ${msg}`);
    }

    /* ── CSRF helper ────────────────────────────────────────────── */

    function _csrf() {
        return window.CSRF_TOKEN
            || document.querySelector('[name=csrfmiddlewaretoken]')?.value
            || '';
    }

    /* ── IndexedDB helpers ─────────────────────────────────────── */

    function _openDB() {
        return new Promise((res, rej) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = e => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(SALES_STORE))
                    db.createObjectStore(SALES_STORE, { keyPath: 'id', autoIncrement: true });
                if (!db.objectStoreNames.contains(ST_STORE))
                    db.createObjectStore(ST_STORE, { keyPath: 'id', autoIncrement: true });
                if (!db.objectStoreNames.contains(CACHE_STORE))
                    db.createObjectStore(CACHE_STORE, { keyPath: 'key' });
            };
            req.onsuccess = e => res(e.target.result);
            req.onerror   = e => rej(e.target.error);
        });
    }

    function _count(store) {
        if (!_db) return Promise.resolve(0);
        return new Promise((res, rej) => {
            const req = _db.transaction(store, 'readonly').objectStore(store).count();
            req.onsuccess = e => res(e.target.result);
            req.onerror   = e => rej(e.target.error);
        });
    }

    function _put(store, rec) {
        return new Promise((res, rej) => {
            const req = _db.transaction(store, 'readwrite').objectStore(store).add(rec);
            req.onsuccess = e => res(e.target.result);
            req.onerror   = e => rej(e.target.error);
        });
    }

    function _putRecord(store, rec) {
        return new Promise((res, rej) => {
            const req = _db.transaction(store, 'readwrite').objectStore(store).put(rec);
            req.onsuccess = () => res();
            req.onerror   = e => rej(e.target.error);
        });
    }

    function _getRecord(store, key) {
        return new Promise((res, rej) => {
            const req = _db.transaction(store, 'readonly').objectStore(store).get(key);
            req.onsuccess = e => res(e.target.result || null);
            req.onerror   = e => rej(e.target.error);
        });
    }

    function _getAll(store) {
        return new Promise((res, rej) => {
            const req = _db.transaction(store, 'readonly').objectStore(store).getAll();
            req.onsuccess = e => res(e.target.result || []);
            req.onerror   = e => rej(e.target.error);
        });
    }

    function _del(store, key) {
        return new Promise((res, rej) => {
            const req = _db.transaction(store, 'readwrite').objectStore(store).delete(key);
            req.onsuccess = () => res();
            req.onerror   = e => rej(e.target.error);
        });
    }

    async function _incRetry(store, rec) {
        const existing = await _getRecord(store, rec.id);
        if (!existing) return;
        existing.retries = (existing.retries || 0) + 1;
        await _putRecord(store, existing);
    }

    /* ── Auto-init ─────────────────────────────────────────────── */

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        init,
        isOnline,
        queueSale,
        queueStockTake,
        cacheProducts,
        getCachedProducts,
        syncNow,
        countPending,
        countPendingST,
        addListener,
    };

})();

// Expose globally — replaces the old OfflineManager
window.OfflineManager = OfflineSync;
window.OfflineSync    = OfflineSync;