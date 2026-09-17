import { t } from '../i18n/index.js';
import { fmtParams } from '../fmt.js';

export function errText(err, locale) {
  return t('err.' + err.code, fmtParams(err.params, locale));
}
