// Bootstrap's colours for Chart.js. Chart.js takes resolved colour strings, not
// `var(--bs-*)`, so they are read off the document each time a chart is built —
// which is also what makes a chart follow the light/dark switch.
const SERIES = ['primary', 'success', 'warning', 'danger', 'info', 'indigo', 'pink', 'teal', 'orange', 'cyan'];

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(`--bs-${name}`).trim();
}

export function palette() {
  return SERIES.map(cssVar);
}

export function applyTheme(Chart) {
  Chart.defaults.color = cssVar('secondary-color');
  Chart.defaults.borderColor = cssVar('border-color');
  Chart.defaults.font.family = cssVar('body-font-family');
}
