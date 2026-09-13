import { useState } from 'preact/hooks';
import { html } from '../h.js';
import { t, LANGS, getLocale, setLocale } from '../i18n/index.js';

function currentTheme() {
  return document.documentElement.dataset.bsTheme === 'dark' ? 'dark' : 'light';
}

// Language + theme controls, identical on every page (trip list, new-trip form,
// every trip tab) — not tied to a trip being loaded.
export function ThemeLangMenu() {
  const [theme, setTheme] = useState(currentTheme());
  const locale = getLocale();

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.bsTheme = next;
    localStorage.setItem('theme', next);
    setTheme(next);
  }

  return html`
    <div class="dropdown">
      <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="dropdown" aria-expanded="false">⋯</button>
      <ul class="dropdown-menu dropdown-menu-end">
        <li><h6 class="dropdown-header">${t('lang.menu')}</h6></li>
        ${Object.keys(LANGS).map((lang) => html`
          <li key=${lang}>
            <button class="dropdown-item ${lang === locale ? 'active' : ''}" type="button"
                    onClick=${() => setLocale(lang)}>${t(`lang.${lang}`)}</button>
          </li>
        `)}
        <li><hr class="dropdown-divider" /></li>
        <li>
          <button class="dropdown-item" type="button" onClick=${toggleTheme}>
            <i class="bi ${theme === 'dark' ? 'bi-sun' : 'bi-moon'}"></i>
            ${theme === 'dark' ? t('theme.light') : t('theme.dark')}
          </button>
        </li>
      </ul>
    </div>
  `;
}
