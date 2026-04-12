const OfflineManager = (() => {
  const DB_NAME    = 'genx-pos-v5';
  const DB_VERSION = 2;
  const STORE      = 'pending_sales';
  const SYNC_TAG   = 'pos-offline-sales';

  let _db = null;
  let _online = navigator.onLine;

  async function init() {
    _db = await _openDB();
    _setupListeners();
    _updateUI();
    await _registerSW();
    _listenSWMessages();

    const cnt = await countPending();
    if (cnt > 0) toast(`${cnt} offline sale(s) queued — will sync when online.`, 'warning');

    return { online: _online, pending: cnt };
  }

  function isOnline() { return _online; }

  async function queueSale(payload, csrf) {
    const record = { payload, csrf, created_at: new Date().toISOString(), status: 'pending', retries: 0 };
    const id = await _put(record);
    _updateUI();
    toast(`Sale saved offline (ID: ${id}). Will sync when connected.`, 'warning');
    return id;
  }

  async function syncNow() {
    if (!_online) { toast('Still offline — sync will happen automatically.', 'warning'); return; }
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
      try {
        const reg = await navigator.serviceWorker.ready;
        await reg.sync.register(SYNC_TAG);
        toast('Sync started in background…', 'info');
      } catch { await _manualReplay(); }
    } else { await _manualReplay(); }
  }

  async function countPending() {
    if (!_db) return 0;
    return new Promise((res, rej) => {
      const tx = _db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).count();
      req.onsuccess = e => res(e.target.result);
      req.onerror   = e => rej(e.target.error);
    });
  }

  async function _manualReplay() {
    const pending = await _getAll();
    if (!pending.length) return;
    let synced = 0, failed = 0;
    for (const sale of pending) {
      try {
        const resp = await fetch('/sales/pos/complete/', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': sale.csrf },
          body: JSON.stringify(sale.payload)
        });
        const d = await resp.json();
        if (d.success) { await _delete(sale.id); synced++; }
        else { failed++; await _incrementRetry(sale); }
      } catch { failed++; }
    }
    if (synced > 0) toast(`${synced} offline sale(s) synced!`, 'success');
    if (failed > 0) toast(`${failed} sale(s) failed to sync.`, 'danger');
    _updateUI();
  }

  function _openDB() {
    return new Promise((res, rej) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = e => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
          store.createIndex('created_at', 'created_at');
          store.createIndex('status', 'status');
        }
      };
      req.onsuccess = e => res(e.target.result);
      req.onerror   = e => rej(e.target.error);
    });
  }

  function _put(record) {
    return new Promise((res, rej) => {
      const tx  = _db.transaction(STORE, 'readwrite');
      const req = tx.objectStore(STORE).add(record);
      req.onsuccess = e => res(e.target.result);
      req.onerror   = e => rej(e.target.error);
    });
  }

  function _getAll() {
    return new Promise((res, rej) => {
      const tx  = _db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).getAll();
      req.onsuccess = e => res(e.target.result);
      req.onerror   = e => rej(e.target.error);
    });
  }

  function _delete(id) {
    return new Promise((res, rej) => {
      const tx  = _db.transaction(STORE, 'readwrite');
      const req = tx.objectStore(STORE).delete(id);
      req.onsuccess = () => res();
      req.onerror   = e => rej(e.target.error);
    });
  }

  async function _incrementRetry(sale) {
    try {
      const tx    = _db.transaction(STORE, 'readwrite');
      const store = tx.objectStore(STORE);
      const req   = store.get(sale.id);
      req.onsuccess = e => {
        const rec = e.target.result;
        if (rec) { rec.retries = (rec.retries || 0) + 1; store.put(rec); }
      };
    } catch {}
  }

  function _setupListeners() {
    window.addEventListener('online',  _onOnline);
    window.addEventListener('offline', _onOffline);
  }

  async function _onOnline() {
    _online = true; _updateUI();
    toast('Connection restored — syncing offline sales…', 'info');
    await syncNow();
  }

  function _onOffline() {
    _online = false; _updateUI();
    toast('⚠ No connection — sales saved locally, will sync automatically.', 'warning');
  }

  async function _registerSW() {
    if (!('serviceWorker' in navigator)) return;
    try {
      await navigator.serviceWorker.register('/static/js/sw.js', { scope: '/' });
    } catch (err) { console.warn('[OfflineManager] SW registration failed:', err); }
  }

  function _listenSWMessages() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.addEventListener('message', event => {
      const { type, receipt_number, synced, failed } = event.data || {};
      if (type === 'SALE_SYNCED') {
        toast(`✓ Offline sale synced: ${receipt_number}`, 'success');
        _updateUI();
      } else if (type === 'SYNC_COMPLETE') {
        if (synced > 0) toast(`${synced} sale(s) synced.`, 'success');
        if (failed > 0) toast(`${failed} sale(s) failed.`, 'warning');
        _updateUI();
      }
    });
  }

  function _updateUI() {
    countPending().then(cnt => {
      const el = document.getElementById('pwa-status');
      if (el) {
        if (!_online) {
          el.textContent = '⚡ OFFLINE';
          el.className   = 'offline';
        } else if (cnt > 0) {
          el.innerHTML = `<span class="sync-badge show"><i class="bi bi-arrow-repeat"></i>${cnt}</span> SYNCING`;
          el.className = 'online';
        } else {
          el.textContent = '● ONLINE';
          el.className   = 'online';
        }
      }

      const banner = document.getElementById('offline-banner');
      if (banner) banner.classList.toggle('show', !_online);

      const sync = document.getElementById('sync-count');
      if (sync) { sync.textContent = cnt > 0 ? cnt : ''; sync.classList.toggle('show', cnt > 0); }
    });
  }

  function toast(msg, type = 'info') {
    if (typeof window.showToast === 'function') { window.showToast(msg, type); return; }
    let stack = document.getElementById('genx-toast-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.id = 'genx-toast-stack';
      stack.style.cssText = 'position:fixed;top:60px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
      document.body.appendChild(stack);
    }
    const colors = { success: ['rgba(0,214,143,.12)', 'rgba(0,214,143,.3)', '#86efac'], warning: ['rgba(245,158,11,.1)', 'rgba(245,158,11,.3)', '#fcd34d'], danger: ['rgba(229,25,58,.1)', 'rgba(229,25,58,.3)', '#fca5a5'], info: ['rgba(59,130,246,.1)', 'rgba(59,130,246,.3)', '#93c5fd'] };
    const [bg, bdr, col] = colors[type] || colors.info;
    const t = document.createElement('div');
    t.style.cssText = `background:${bg};border:1px solid ${bdr};color:${col};padding:10px 14px;border-radius:10px;font-size:12px;font-weight:600;min-width:240px;max-width:360px;pointer-events:all;box-shadow:0 4px 20px rgba(0,0,0,.5);`;
    t.textContent = msg;
    stack.appendChild(t);
    setTimeout(() => { t.style.transition = 'opacity .3s'; t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 5000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  return { init, isOnline, queueSale, syncNow, countPending };
})();

window.OfflineManager = OfflineManager;
