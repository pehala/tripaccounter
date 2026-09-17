import { useEffect } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { getLocale } from '../i18n/index.js';
import { Loading } from '../components/Loading.js';
import { PeopleSection } from './setup/PeopleSection.js';
import { WalletsSection } from './setup/WalletsSection.js';
import { CurrenciesSection } from './setup/CurrenciesSection.js';
import { CountriesSection } from './setup/CountriesSection.js';
import { LabelsSection } from './setup/LabelsSection.js';
import { TripSection } from './setup/TripSection.js';

export function Setup() {
  const store = useStore();
  const locale = getLocale();

  useEffect(() => {
    if (!store.labels) reload('labels');
  }, [store.slug]);

  if (!store.labels) return html`<${Loading} />`;

  const trip = store.trip;

  return html`
    <${PeopleSection} trip=${trip} locale=${locale} />
    <${WalletsSection} trip=${trip} locale=${locale} />
    <${CurrenciesSection} trip=${trip} locale=${locale} />
    <${CountriesSection} trip=${trip} locale=${locale} />
    <${LabelsSection} trip=${trip} labels=${store.labels} locale=${locale} />
    <${TripSection} trip=${trip} locale=${locale} />
  `;
}
