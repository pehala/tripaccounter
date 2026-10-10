import { useState } from 'preact/hooks';
import { html } from '../h.js';
import { t, LANGS, getLocale, setLocale } from '../i18n/index.js';
import { date, dateTime } from '../fmt.js';

function currentTheme() {
  return document.documentElement.dataset.bsTheme === 'dark' ? 'dark' : 'light';
}

// Language + theme controls, identical on every page (trip list, new-trip form,
// every trip tab) — not tied to a trip being loaded. `version` is the running build
// ({ version, built_at }) or null; the menu ends with it when there is one.
export function ThemeLangMenu({ version }) {
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
      <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="dropdown" aria-expanded="false">
        <i class="bi bi-gear"></i> ${t('settings.menu')}
      </button>
      <ul class="dropdown-menu dropdown-menu-end">
        <li><h6 class="dropdown-header">${t('settings.menu')}</h6></li>
        ${Object.keys(LANGS).map((lang) => html`
          <li key=${lang}>
            <button class="dropdown-item ${lang === locale ? 'active' : ''}" type="button"
                    onClick=${() => setLocale(lang)}>${t(`lang.${lang}`)}</button>
          </li>
        `)}
        <li><hr class="dropdown-divider" /></li>
        <li>
          <button class="dropdown-item" type="button" onClick=${toggleTheme}>
            <i class="bi me-2 ${theme === 'dark' ? 'bi-sun' : 'bi-moon'}"></i>
            ${theme === 'dark' ? t('theme.light') : t('theme.dark')}
          </button>
        </li>
        ${version?.version && html`
          <li><hr class="dropdown-divider" /></li>
          <li>
            <span class="dropdown-item-text small text-body-secondary" data-testid="build-version"
                  title=${version.built_at ? dateTime(version.built_at, locale) : undefined}>
              ${version.version}${version.built_at && ` · ${date(version.built_at, locale)}`}
            </span>
          </li>
        `}
      </ul>
    </div>
  `;
}
