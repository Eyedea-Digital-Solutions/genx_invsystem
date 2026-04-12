'use strict';

const GenXCharts = (() => {
  const PALETTE = {
    violet:  '#7c3aed',
    green:   '#00d68f',
    blue:    '#3b82f6',
    amber:   '#f59e0b',
    rose:    '#e5193a',
    cyan:    '#06b6d4',
    fuchsia: '#d946ef',
    indigo:  '#6366f1',
  };

  const DEFAULTS = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { family: 'Space Grotesk', size: 12 }, boxWidth: 12, padding: 16 } },
      tooltip: {
        backgroundColor: 'rgba(15,15,30,0.95)',
        titleColor: '#e2e8f0',
        bodyColor: '#94a3b8',
        borderColor: 'rgba(124,58,237,0.3)',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
        titleFont: { family: 'Space Grotesk', weight: '600' },
        bodyFont: { family: 'Space Grotesk' },
      },
    },
    scales: {
      x: { ticks: { color: '#64748b', font: { family: 'Space Grotesk', size: 11 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
      y: { ticks: { color: '#64748b', font: { family: 'Space Grotesk', size: 11 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
    },
  };

  function salesLine(ctx, labels, data, label = 'Sales') {
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label,
          data,
          borderColor: PALETTE.violet,
          backgroundColor: 'rgba(124,58,237,0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: PALETTE.violet,
          pointRadius: 4,
          pointHoverRadius: 6,
        }],
      },
      options: { ...DEFAULTS },
    });
  }

  function revenueBar(ctx, labels, datasets) {
    const colors = Object.values(PALETTE);
    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: datasets.map((d, i) => ({
          ...d,
          backgroundColor: colors[i % colors.length] + '99',
          borderColor: colors[i % colors.length],
          borderWidth: 1,
          borderRadius: 4,
        })),
      },
      options: { ...DEFAULTS, plugins: { ...DEFAULTS.plugins } },
    });
  }

  function categoryDonut(ctx, labels, data) {
    const colors = Object.values(PALETTE);
    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: colors.map(c => c + 'cc'),
          borderColor: colors,
          borderWidth: 1,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '65%',
        plugins: { ...DEFAULTS.plugins, legend: { position: 'bottom', labels: { ...DEFAULTS.plugins.legend.labels } } },
      },
    });
  }

  function sparkline(ctx, data, color = PALETTE.green) {
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map((_, i) => i),
        datasets: [{ data, borderColor: color, backgroundColor: color + '22', borderWidth: 1.5, fill: true, tension: 0.4, pointRadius: 0 }],
      },
      options: { responsive: true, maintainAspectRatio: false, animation: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } } },
    });
  }

  function fromDataAttr() {
    document.querySelectorAll('[data-chart]').forEach(el => {
      const type = el.dataset.chart;
      const raw = el.dataset.chartData;
      if (!raw) return;
      try {
        const d = JSON.parse(raw);
        const ctx = el.getContext('2d');
        if (type === 'sales-line') salesLine(ctx, d.labels, d.data, d.label);
        else if (type === 'revenue-bar') revenueBar(ctx, d.labels, d.datasets);
        else if (type === 'category-donut') categoryDonut(ctx, d.labels, d.data);
        else if (type === 'sparkline') sparkline(ctx, d.data, d.color);
      } catch (e) { console.warn('[GenXCharts] parse error', e); }
    });
  }

  document.addEventListener('DOMContentLoaded', fromDataAttr);
  return { salesLine, revenueBar, categoryDonut, sparkline, PALETTE };
})();

window.GenXCharts = GenXCharts;
