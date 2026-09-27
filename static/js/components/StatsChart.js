import { useEffect, useRef, useState } from 'preact/hooks';
import { html } from '../h.js';
import { t } from '../i18n/index.js';
import { money } from '../fmt.js';
import { applyTheme, palette } from '../chartTheme.js';

// Chart.js owns the canvas and Preact owns none of it, the same split MapCanvas has
// with Leaflet. Chart.js is imported on first mount, so no other tab pays for it.
let loading;
function loadChart() {
  loading ??= import('chart.js').then((module) => {
    const { Chart } = module;
    Chart.register(
      module.BarController, module.BarElement, module.CategoryScale, module.LinearScale,
      module.Tooltip, module.Legend,
    );
    return Chart;
  });
  return loading;
}

function config(spec, code, locale) {
  const colors = palette();
  const tooltip = {
    callbacks: {
      label: (ctx) => [ctx.dataset.label, `${money(ctx.raw, locale)} ${code}`].filter(Boolean).join(' · '),
    },
  };
  const valueAxis = { stacked: spec.stacked, ticks: { callback: (value) => money(value, locale) } };
  const categoryAxis = { stacked: spec.stacked, grid: { display: false } };
  return {
    type: 'bar',
    data: {
      labels: spec.labels,
      datasets: spec.series.map((series, index) => ({
        label: series.label,
        data: series.data,
        backgroundColor: series.color ?? colors[index % colors.length],
      })),
    },
    options: {
      maintainAspectRatio: false,
      indexAxis: spec.horizontal ? 'y' : 'x',
      scales: spec.horizontal ? { x: valueAxis, y: categoryAxis } : { x: categoryAxis, y: valueAxis },
      plugins: { tooltip, legend: { display: spec.series.length > 1, position: 'bottom' } },
    },
  };
}

// Rebuilt from scratch whenever what it draws changes, or the theme does.
export function StatsChart({ spec, code, locale }) {
  const canvasRef = useRef(null);
  const [theme, setTheme] = useState(document.documentElement.dataset.bsTheme);
  const [failed, setFailed] = useState(false);
  const drawn = JSON.stringify(spec);

  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(document.documentElement.dataset.bsTheme));
    observer.observe(document.documentElement, { attributeFilter: ['data-bs-theme'] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let chart;
    let disposed = false;
    loadChart().then((Chart) => {
      if (disposed) return;
      applyTheme(Chart);
      chart = new Chart(canvasRef.current, config(spec, code, locale));
    }).catch(() => {
      if (!disposed) setFailed(true);
    });
    return () => {
      disposed = true;
      chart?.destroy();
    };
  }, [drawn, code, locale, theme]);

  if (failed) return html`<div class="alert alert-warning py-2 px-3 small mb-0">${t('stats.chart_failed')}</div>`;

  // A horizontal chart grows with its bars; side-by-side series each need a row too.
  const bars = spec.labels.length * (spec.stacked ? 1 : spec.series.length);
  const height = spec.horizontal ? Math.max(8, bars * 1.4 + 3) : 18;
  return html`
    <div class="position-relative" style="height:${height}rem">
      <canvas ref=${canvasRef} role="img" aria-label=${t('stats.chart')}></canvas>
    </div>
  `;
}
