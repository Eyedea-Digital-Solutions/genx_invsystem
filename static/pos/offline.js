const OfflineManager = (() => {

    const DB_NAME    = 'genx-pos-offline';
    const DB_VERSION = 1;
    const STORE_NAME = 'pending_sales';
    const SYNC_TAG   = 'pos-offline-sales';

    let _db = null;

    // ── PUBLIC API ────────────────────────────────────────────────────────────

    async function init() {
        _db = await _openDB();
        _setupConnectivityListeners();
        _updateUI();
        _registerServiceWorker();
        _listenForSyncMessages();

        // On load, show count of pending offline sales
        const pending = await countPending();
        if (pending > 0) {
            _showBanner(`${pending} offline sale(s) queued — will sync when online.`, 'warning');
        }
    }

    /** Returns true if the browser has network connectivity */
    function isOnline() {
        return navigator.onLine;
    }

    /**
     * Queue a sale for offline processing.
     * @param {Object} payload  - The same body sent to /sales/pos/complete/
     * @param {string} csrf     - CSRF token
     * @returns {number} The IndexedDB record ID
     */
    async function queueSale(payload, csrf) {
        const record = {
            payload,
            csrf,
            created_at: new Date().toISOString(),
            status:     'pending',
        };
        const id = await _put(record);
        _showBanner(`Sale saved offline (ID: ${id}). Will sync when connection is restored.`, 'warning');
        return id;
    }

    /** Attempt to sync all pending sales immediately */
    async function syncNow() {
        if (!isOnline()) {
            _showBanner('Still offline — sync will happen automatically when connected.', 'warning');
            return;
        }

        // Prefer Background Sync API
        if ('serviceWorker' in navigator && 'SyncManager' in window) {
            const reg = await navigator.serviceWorker.ready;
            await reg.sync.register(SYNC_TAG);
            _showBanner('Sync started in background…', 'info');
        } else {
            // Fallback: manual replay
            await _manualReplay();
        }
    }

    /** Count pending offline sales */
    async function countPending() {
        if (!_db) return 0;
        return new Promise((resolve, reject) => {
            const tx    = _db.transaction(STORE_NAME, 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const req   = store.count();
            req.onsuccess = e => resolve(e.target.result);
            req.onerror   = e => reject(e.target.error);
        });
    }

    // ── PRIVATE: IndexedDB ────────────────────────────────────────────────────

    function _openDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = e => {
                const db    = e.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    db.createObjectStore(STORE_NAME, {
                        keyPath:       'id',
                        autoIncrement: true,
                    });
                }
            };
            req.onsuccess = e => resolve(e.target.result);
            req.onerror   = e => reject(e.target.error);
        });
    }

    function _put(record) {
        return new Promise((resolve, reject) => {
            const tx    = _db.transaction(STORE_NAME, 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            const req   = store.add(record);
            req.onsuccess = e => resolve(e.target.result);
            req.onerror   = e => reject(e.target.error);
        });
    }

    function _getAll() {
        return new Promise((resolve, reject) => {
            const tx    = _db.transaction(STORE_NAME, 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const req   = store.getAll();
            req.onsuccess = e => resolve(e.target.result);
            req.onerror   = e => reject(e.target.error);
        });
    }

    function _delete(id) {
        return new Promise((resolve, reject) => {
            const tx    = _db.transaction(STORE_NAME, 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            const req   = store.delete(id);
            req.onsuccess = () => resolve();
            req.onerror   = e => reject(e.target.error);
        });
    }

    // ── PRIVATE: Manual replay (no Background Sync API) ──────────────────────

    async function _manualReplay() {
        const pending = await _getAll();
        if (!pending.length) return;

        let synced = 0, failed = 0;

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
                const data = await res.json();
                if (data.success) {
                    await _delete(sale.id);
                    synced++;
                } else {
                    failed++;
                }
            } catch {
                failed++;
            }
        }

        if (synced > 0) {
            _showBanner(`${synced} offline sale(s) synced successfully!`, 'success');
        }
        if (failed > 0) {
            _showBanner(`${failed} sale(s) failed to sync — check connection.`, 'danger');
        }
        _updateUI();
    }

    // ── PRIVATE: Connectivity ─────────────────────────────────────────────────

    function _setupConnectivityListeners() {
        window.addEventListener('online',  _onOnline);
        window.addEventListener('offline', _onOffline);
    }

    async function _onOnline() {
        _updateUI();
        _showBanner('Connection restored — syncing offline sales…', 'info');
        await syncNow();
    }

    function _onOffline() {
        _updateUI();
        _showBanner('⚠ No internet connection — sales will be saved locally and synced later.', 'warning');
    }

    // ── PRIVATE: Service Worker ───────────────────────────────────────────────

    async function _registerServiceWorker() {
        if (!('serviceWorker' in navigator)) return;
        try {
            await navigator.serviceWorker.register('/static/pos/sw.js', { scope: '/sales/pos/' });
        } catch (err) {
            console.warn('SW registration failed:', err);
        }
    }

    function _listenForSyncMessages() {
        if (!('serviceWorker' in navigator)) return;
        navigator.serviceWorker.addEventListener('message', event => {
            if (event.data?.type === 'SALE_SYNCED') {
                _showBanner(`Offline sale synced: ${event.data.receipt_number}`, 'success');
                _updateUI();
            }
        });
    }

    // ── PRIVATE: UI ───────────────────────────────────────────────────────────

    function _updateUI() {
        const indicator = document.getElementById('offline-indicator');
        if (!indicator) return;

        countPending().then(count => {
            if (!isOnline()) {
                indicator.textContent  = '⚠ OFFLINE';
                indicator.style.background = '#d97706';
                indicator.style.display    = 'flex';
            } else if (count > 0) {
                indicator.textContent  = `↑ SYNCING (${count})`;
                indicator.style.background = '#7c3aed';
                indicator.style.display    = 'flex';
            } else {
                indicator.style.display = 'none';
            }
        });
    }

    function _showBanner(message, type = 'info') {
        // Re-use existing banner container in POS or create one
        let container = document.getElementById('offline-banners');
        if (!container) {
            container = document.createElement('div');
            container.id = 'offline-banners';
            container.style.cssText = 'position:fixed;bottom:60px;left:50%;transform:translateX(-50%);z-index:9999;min-width:300px;max-width:90vw;';
            document.body.appendChild(container);
        }

        const colors = {
            success: { bg: '#16a34a', text: '#fff' },
            warning: { bg: '#d97706', text: '#fff' },
            danger:  { bg: '#dc2626', text: '#fff' },
            info:    { bg: '#2563eb', text: '#fff' },
        };
        const color = colors[type] || colors.info;

        const banner = document.createElement('div');
        banner.style.cssText = `
            background:${color.bg};color:${color.text};
            padding:9px 14px;border-radius:8px;font-size:12px;font-weight:600;
            margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;
            gap:10px;box-shadow:0 4px 16px rgba(0,0,0,.3);
        `;
        banner.innerHTML = `
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" style="background:none;border:none;color:inherit;cursor:pointer;font-size:16px;line-height:1;padding:0;">✕</button>
        `;
        container.appendChild(banner);

        // Auto-remove after 8 seconds
        setTimeout(() => banner.remove(), 8000);
    }

    return { init, isOnline, queueSale, syncNow, countPending };

})();

// Auto-init when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => OfflineManager.init());
} else {
    OfflineManager.init();
}