import { t } from '../i18n/index.js';
import { fmtParams } from '../fmt.js';
import { pushFlash } from './Flash.js';

export function errText(err, locale) {
  return t('err.' + err.code, fmtParams(err.params, locale));
}

// Flash what has no input to sit under — `fields.id`, or an error with no fields —
// and return the remaining field errors, keyed by field.
export function routeError(err, locale) {
  const { id, ...rest } = err.fields || {};
  if (id) pushFlash(errText(id, locale));
  else if (!Object.keys(rest).length) pushFlash(errText(err, locale));
  return rest;
}
