'use strict';

const GenX = (() => {
  function init() {
    _initSidebar();
    _initToasts();
    _initCommandPalette();
    _initTopbar();
    _initTableSearch();
    _initFormEnhancements();
    _initCounters();
    _initConfirm();
    _initAutoRefresh();
  }

  function _initSidebar() {
    const toggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (!sidebar) return;

    const syncSidebarMode = () => {
      if (window.innerWidth >= 992) {
        sidebar.classList.remove('collapsed');
        overlay?.classList.remove('show');
        localStorage.removeItem('sidebar-collapsed');
        return;
      }

      const stored = localStorage.getItem('sidebar-collapsed');
      if (stored === 'false') sidebar.classList.remove('collapsed');
      else sidebar.classList.add('collapsed');
    };

    syncSidebarMode();

    toggle?.addEventListener('click', () => {
      if (window.innerWidth >= 992) return;
      const collapsed = sidebar.classList.toggle('collapsed');
      localStorage.setItem('sidebar-collapsed', collapsed);
      if (overlay) overlay.classList.toggle('show', !collapsed && window.innerWidth < 992);
    });

    overlay?.addEventListener('click', () => {
      sidebar.classList.add('collapsed');
      overlay.classList.remove('show');
    });

    window.addEventListener('resize', syncSidebarMode);

    document.querySelectorAll('.sidebar-item[data-submenu]').forEach(item => {
      item.addEventListener('click', e => {
        const sub = document.querySelector(item.dataset.submenu);
        if (!sub) return;
        const open = sub.classList.toggle('show');
        item.setAttribute('aria-expanded', open);
        e.stopPropagation();
      });
    });

    const current = window.location.pathname;
    document.querySelectorAll('.sidebar-link').forEach(link => {
      const href = link.getAttribute('href');
      if (href && href !== '/' && current.startsWith(href)) {
        link.classList.add('active');
        const parent = link.closest('.sidebar-submenu');
        if (parent) {
          parent.classList.add('show');
          parent.previousElementSibling?.setAttribute('aria-expanded', 'true');
        }
      }
    });
  }

  function _initToasts() {
    window.showToast = function(msg, type = 'info', duration = 5000) {
      let stack = document.getElementById('toast-stack');
      if (!stack) {
        stack = document.createElement('div');
        stack.id = 'toast-stack';
        stack.style.cssText = 'position:fixed;top:72px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;max-width:380px;';
        document.body.appendChild(stack);
      }
      const icons = { success: 'bi-check-circle-fill', danger: 'bi-x-circle-fill', warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
      const toast = document.createElement('div');
      toast.className = `genx-toast genx-toast-${type}`;
      toast.innerHTML = `<i class="bi ${icons[type] || icons.info}"></i><span>${msg}</span><button onclick="this.closest('.genx-toast').remove()"><i class="bi bi-x"></i></button>`;
      toast.style.cssText = 'pointer-events:all;display:flex;align-items:center;gap:10px;padding:12px 14px;border-radius:12px;font-size:13px;font-weight:500;animation:slideUp .2s ease;box-shadow:0 8px 32px rgba(0,0,0,.5);';
      stack.appendChild(toast);
      setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity .3s'; setTimeout(() => toast.remove(), 300); }, duration);
    };

    document.querySelectorAll('[data-toast]').forEach(el => {
      const { toast: msg, toastType: type } = el.dataset;
      if (msg) setTimeout(() => window.showToast(msg, type || 'info'), 100);
    });
  }

  function _initCommandPalette() {
    const palette = document.getElementById('command-palette');
    const input = document.getElementById('command-input');
    const results = document.getElementById('command-results');
    if (!palette || !input) return;

    const commands = [
      { label: 'New Sale / POS Terminal', icon: 'bi-cart-plus', url: '/sales/pos/' },
      { label: 'Inventory Dashboard', icon: 'bi-boxes', url: '/inventory/' },
      { label: 'Add Product', icon: 'bi-plus-square', url: '/inventory/product/add/' },
      { label: 'Sales History', icon: 'bi-receipt', url: '/sales/' },
      { label: 'Analytics Dashboard', icon: 'bi-bar-chart', url: '/analytics/dashboard/' },
      { label: 'Cash Up', icon: 'bi-cash-stack', url: '/cashup/' },
      { label: 'Employees', icon: 'bi-people', url: '/employees/' },
      { label: 'Customers', icon: 'bi-person-lines-fill', url: '/customers/' },
      { label: 'Returns', icon: 'bi-arrow-return-left', url: '/returns/' },
      { label: 'Purchase Orders', icon: 'bi-truck', url: '/purchasing/' },
      { label: 'Promotions', icon: 'bi-tag', url: '/promotions/' },
      { label: 'EcoCash Transactions', icon: 'bi-phone', url: '/ecocash/' },
      { label: 'Expenses', icon: 'bi-wallet2', url: '/expenses/' },
      { label: 'Stock Take', icon: 'bi-clipboard-check', url: '/inventory/stock-take/' },
      { label: 'Low Stock Report', icon: 'bi-exclamation-triangle', url: '/inventory/low-stock/' },
    ];

    function open() { palette.classList.add('show'); input.value = ''; render(''); input.focus(); }
    function close() { palette.classList.remove('show'); }

    function render(q) {
      const filtered = q ? commands.filter(c => c.label.toLowerCase().includes(q.toLowerCase())) : commands;
      results.innerHTML = filtered.length
        ? filtered.map((c, i) => `<a href="${c.url}" class="cmd-item ${i === 0 ? 'active' : ''}"><i class="bi ${c.icon}"></i>${c.label}</a>`).join('')
        : '<div class="cmd-empty">No results</div>';
    }

    document.addEventListener('keydown', e => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); palette.classList.contains('show') ? close() : open(); }
      if (e.key === 'Escape') close();
      if (!palette.classList.contains('show')) return;
      const items = results.querySelectorAll('.cmd-item');
      const active = results.querySelector('.cmd-item.active');
      let idx = Array.from(items).indexOf(active);
      if (e.key === 'ArrowDown') { e.preventDefault(); items[Math.min(idx + 1, items.length - 1)]?.classList.add('active'); active?.classList.remove('active'); }
      if (e.key === 'ArrowUp')   { e.preventDefault(); items[Math.max(idx - 1, 0)]?.classList.add('active'); active?.classList.remove('active'); }
      if (e.key === 'Enter') { results.querySelector('.cmd-item.active')?.click(); }
    });

    input.addEventListener('input', e => render(e.target.value));
    palette.addEventListener('click', e => { if (e.target === palette) close(); });
    document.getElementById('command-palette-trigger')?.addEventListener('click', open);
  }

  function _initTopbar() {
    const search = document.getElementById('global-search');
    if (search) {
      let timer;
      search.addEventListener('input', e => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          const q = e.target.value.trim();
          if (q.length > 2) window.location.href = `/inventory/?q=${encodeURIComponent(q)}`;
        }, 500);
      });
    }
  }

  function _initTableSearch() {
    document.querySelectorAll('[data-table-search]').forEach(input => {
      const target = document.querySelector(input.dataset.tableSearch);
      if (!target) return;
      input.addEventListener('input', e => {
        const q = e.target.value.toLowerCase();
        target.querySelectorAll('tbody tr').forEach(row => {
          row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
        });
      });
    });
  }

  function _initFormEnhancements() {
    document.querySelectorAll('input[type="number"]').forEach(input => {
      input.addEventListener('wheel', e => e.preventDefault(), { passive: false });
    });

    document.querySelectorAll('[data-currency]').forEach(input => {
      input.addEventListener('blur', e => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val)) e.target.value = val.toFixed(2);
      });
    });

    document.querySelectorAll('form').forEach(form => {
      form.addEventListener('submit', e => {
        const btn = form.querySelector('[type="submit"]');
        if (btn && !btn.dataset.noLoading) {
          btn.disabled = true;
          btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing…';
        }
      });
    });
  }

  function _initCounters() {
    document.querySelectorAll('[data-count-url]').forEach(el => {
      fetch(el.dataset.countUrl)
        .then(r => r.json())
        .then(d => { el.textContent = d.count ?? d.value ?? ''; })
        .catch(() => {});
    });
  }

  function _initConfirm() {
    document.querySelectorAll('[data-confirm]').forEach(el => {
      el.addEventListener('click', e => {
        if (!confirm(el.dataset.confirm || 'Are you sure?')) e.preventDefault();
      });
    });
  }

  function _initAutoRefresh() {
    const meta = document.querySelector('meta[name="auto-refresh"]');
    if (meta) {
      const ms = parseInt(meta.content) * 1000;
      if (ms > 0) setTimeout(() => window.location.reload(), ms);
    }
  }

  document.addEventListener('DOMContentLoaded', init);
  return { showToast: (m, t) => window.showToast?.(m, t) };
})();

window.GenX = GenX;
