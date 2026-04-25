const OfflineManager = (() => {
  const DB_NAME = 'genx-pos-v6';
  const DB_VERSION = 3;
  const SALES_STORE = 'pending_sales';
  const STOCK_TAKE_STORE = 'pending_stock_takes';
  const INVENTORY_CACHE_STORE = 'inventory_cache';
  const SYNC_TAG = 'genx-offline-sync';

  let _db = null;
  let _online = navigator.onLine;

  async function init() {
    _db = await _openDB();
    _setupListeners();
    _updateUI();
    await _registerSW();
    _listenSWMessages();

    const sales = await countPending();
    const stockTakes = await countPendingStockTakes();

    if (sales > 0 || stockTakes > 0) {
      toast(_buildPendingSummary(sales, stockTakes), 'warning');
    }

    return { online: _online, pending_sales: sales, pending_stock_takes: stockTakes };
  }

  function isOnline() {
    return _online;
  }

  async function queueSale(payload, csrf) {
    const id = await _addRecord(SALES_STORE, {
      payload,
      csrf,
      created_at: new Date().toISOString(),
      status: 'pending',
      retries: 0,
    });
    _updateUI();
    toast(`Sale saved offline (ID: ${id}). Will sync when connected.`, 'warning');
    return id;
  }

  async function queueStockTake(payload) {
    const id = await _addRecord(STOCK_TAKE_STORE, {
      payload,
      csrf: _getCsrfToken(),
      created_at: new Date().toISOString(),
      status: 'pending',
      retries: 0,
    });
    _updateUI();
    toast(`Stock take saved offline (ID: ${id}). It will sync automatically when you're back online.`, 'warning');
    return id;
  }

  async function cacheProductsForCount(key, products) {
    if (!_db || !key) return;
    await _putRecord(INVENTORY_CACHE_STORE, {
      key,
      products,
      updated_at: new Date().toISOString(),
    });
  }

  async function getCachedProductsForCount(key) {
    if (!_db || !key) return null;
    return _getRecord(INVENTORY_CACHE_STORE, key);
  }

  async function countPending() {
    return _countStore(SALES_STORE);
  }

  async function countPendingStockTakes() {
    return _countStore(STOCK_TAKE_STORE);
  }

  async function syncNow() {
    if (!_online) {
      toast('Still offline. Pending work will sync automatically later.', 'warning');
      return;
    }

    if ('serviceWorker' in navigator && 'SyncManager' in window) {
      try {
        const reg = await navigator.serviceWorker.ready;
        await reg.sync.register(SYNC_TAG);
        toast('Offline sync started in the background.', 'info');
      } catch {
        await _manualReplay();
      }
    } else {
      await _manualReplay();
    }
  }

  async function _manualReplay() {
    const sales = await _getAll(SALES_STORE);
    const stockTakes = await _getAll(STOCK_TAKE_STORE);

    let syncedSales = 0;
    let failedSales = 0;
    let syncedStockTakes = 0;
    let failedStockTakes = 0;

    for (const sale of sales) {
      try {
        const resp = await fetch('/sales/pos/complete/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': sale.csrf },
          body: JSON.stringify(sale.payload),
        });
        const data = await resp.json();
        if (data.success) {
          await _deleteRecord(SALES_STORE, sale.id);
          syncedSales++;
        } else {
          failedSales++;
          await _incrementRetry(SALES_STORE, sale.id);
        }
      } catch {
        failedSales++;
      }
    }

    for (const stockTake of stockTakes) {
      try {
        const resp = await fetch('/inventory/api/stock-take/submit/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': stockTake.csrf || _getCsrfToken() },
          body: JSON.stringify(stockTake.payload),
        });
        const data = await resp.json();
        if (data.ok) {
          await _deleteRecord(STOCK_TAKE_STORE, stockTake.id);
          syncedStockTakes++;
        } else {
          failedStockTakes++;
          await _incrementRetry(STOCK_TAKE_STORE, stockTake.id);
        }
      } catch {
        failedStockTakes++;
      }
    }

    if (syncedSales || syncedStockTakes) {
      toast(_buildSyncedSummary(syncedSales, syncedStockTakes), 'success');
    }
    if (failedSales || failedStockTakes) {
      toast(_buildFailedSummary(failedSales, failedStockTakes), 'danger');
    }

    _updateUI();
  }

  function _setupListeners() {
    window.addEventListener('online', _onOnline);
    window.addEventListener('offline', _onOffline);
  }

  async function _onOnline() {
    _online = true;
    _updateUI();
    toast('Connection restored. Syncing offline work…', 'info');
    await syncNow();
  }

  function _onOffline() {
    _online = false;
    _updateUI();
    toast('Offline mode active. Sales and stock takes will be stored locally.', 'warning');
  }

  async function _registerSW() {
    if (!('serviceWorker' in navigator)) return;
    try {
      await navigator.serviceWorker.register('/static/js/sw.js', { scope: '/' });
    } catch (err) {
      console.warn('[OfflineManager] SW registration failed:', err);
    }
  }

  function _listenSWMessages() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.addEventListener('message', event => {
      const { type, receipt_number, synced_sales, failed_sales, synced_stock_takes, failed_stock_takes } = event.data || {};
      if (type === 'SALE_SYNCED') {
        toast(`Offline sale synced: ${receipt_number}`, 'success');
      } else if (type === 'STOCK_TAKE_SYNCED') {
        toast('Offline stock take synced successfully.', 'success');
      } else if (type === 'SYNC_COMPLETE') {
        if (synced_sales || synced_stock_takes) {
          toast(_buildSyncedSummary(synced_sales || 0, synced_stock_takes || 0), 'success');
        }
        if (failed_sales || failed_stock_takes) {
          toast(_buildFailedSummary(failed_sales || 0, failed_stock_takes || 0), 'warning');
        }
      }
      _updateUI();
    });
  }

  function _updateUI() {
    Promise.all([countPending(), countPendingStockTakes()]).then(([sales, stockTakes]) => {
      const totalPending = sales + stockTakes;
      const status = document.getElementById('pwa-status');
      if (status) {
        if (!_online) {
          status.textContent = `OFFLINE${totalPending ? ` • ${totalPending} QUEUED` : ''}`;
          status.className = 'offline';
        } else if (totalPending > 0) {
          status.textContent = `${totalPending} QUEUED`;
          status.className = 'online';
        } else {
          status.textContent = 'ONLINE';
          status.className = 'online';
        }
      }

      const banner = document.getElementById('offline-banner');
      if (banner) {
        banner.classList.toggle('show', !_online || totalPending > 0);
        const msg = banner.querySelector('span');
        if (msg) {
          if (!_online) {
            msg.textContent = 'You are offline. Sales and stock takes will be saved locally and synced automatically.';
          } else if (totalPending > 0) {
            msg.textContent = _buildPendingSummary(sales, stockTakes);
          } else {
            msg.textContent = 'You are back online.';
          }
        }
      }

      const sync = document.getElementById('sync-count');
      if (sync) {
        sync.textContent = totalPending > 0 ? totalPending : '';
        sync.classList.toggle('show', totalPending > 0);
      }
    });
  }

  function _buildPendingSummary(sales, stockTakes) {
    const bits = [];
    if (sales) bits.push(`${sales} sale${sales === 1 ? '' : 's'}`);
    if (stockTakes) bits.push(`${stockTakes} stock take${stockTakes === 1 ? '' : 's'}`);
    return `${bits.join(' and ')} queued for sync.`;
  }

  function _buildSyncedSummary(sales, stockTakes) {
    const bits = [];
    if (sales) bits.push(`${sales} sale${sales === 1 ? '' : 's'}`);
    if (stockTakes) bits.push(`${stockTakes} stock take${stockTakes === 1 ? '' : 's'}`);
    return `Synced ${bits.join(' and ')} successfully.`;
  }

  function _buildFailedSummary(sales, stockTakes) {
    const bits = [];
    if (sales) bits.push(`${sales} sale${sales === 1 ? '' : 's'}`);
    if (stockTakes) bits.push(`${stockTakes} stock take${stockTakes === 1 ? '' : 's'}`);
    return `Failed to sync ${bits.join(' and ')}.`;
  }

  function _getCsrfToken() {
    return window.CSRF_TOKEN || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  }

  function _openDB() {
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
        if (!db.objectStoreNames.contains(INVENTORY_CACHE_STORE)) {
          db.createObjectStore(INVENTORY_CACHE_STORE, { keyPath: 'key' });
        }
      };
      req.onsuccess = event => resolve(event.target.result);
      req.onerror = event => reject(event.target.error);
    });
  }

  function _countStore(storeName) {
    if (!_db) return Promise.resolve(0);
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(storeName, 'readonly');
      const req = tx.objectStore(storeName).count();
      req.onsuccess = event => resolve(event.target.result);
      req.onerror = event => reject(event.target.error);
    });
  }

  function _addRecord(storeName, record) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(storeName, 'readwrite');
      const req = tx.objectStore(storeName).add(record);
      req.onsuccess = event => resolve(event.target.result);
      req.onerror = event => reject(event.target.error);
    });
  }

  function _putRecord(storeName, record) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(storeName, 'readwrite');
      const req = tx.objectStore(storeName).put(record);
      req.onsuccess = () => resolve();
      req.onerror = event => reject(event.target.error);
    });
  }

  function _getRecord(storeName, key) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(storeName, 'readonly');
      const req = tx.objectStore(storeName).get(key);
      req.onsuccess = event => resolve(event.target.result || null);
      req.onerror = event => reject(event.target.error);
    });
  }

  function _getAll(storeName) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(storeName, 'readonly');
      const req = tx.objectStore(storeName).getAll();
      req.onsuccess = event => resolve(event.target.result || []);
      req.onerror = event => reject(event.target.error);
    });
  }

  function _deleteRecord(storeName, key) {
    return new Promise((resolve, reject) => {
      const tx = _db.transaction(storeName, 'readwrite');
      const req = tx.objectStore(storeName).delete(key);
      req.onsuccess = () => resolve();
      req.onerror = event => reject(event.target.error);
    });
  }

  async function _incrementRetry(storeName, key) {
    try {
      const existing = await _getRecord(storeName, key);
      if (!existing) return;
      existing.retries = (existing.retries || 0) + 1;
      await _putRecord(storeName, existing);
    } catch {}
  }

  function toast(msg, type = 'info') {
    if (typeof window.showToast === 'function') {
      window.showToast(msg, type);
      return;
    }
    console.log(`[${type}] ${msg}`);
  }

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
    cacheProductsForCount,
    getCachedProductsForCount,
    syncNow,
    countPending,
    countPendingStockTakes,
  };
})();

window.OfflineManager = OfflineManager;
