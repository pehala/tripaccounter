import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { t } from '../i18n/index.js';

// Module-level pub-sub so any view can push a flash without prop-drilling;
// <${Flash}/> is mounted once (Trip.js) and re-renders on push/dismiss.
let seq = 0;
let messages = [];
const listeners = new Set();

function notify() { listeners.forEach((fn) => fn(messages)); }

export function pushFlash(text, variant = 'danger') {
  const msg = { id: ++seq, text, variant };
  messages = [...messages, msg];
  notify();
  setTimeout(() => dismissFlash(msg.id), 6000);
}

export function dismissFlash(id) {
  messages = messages.filter((m) => m.id !== id);
  notify();
}

export function Flash() {
  const [list, setList] = useState(messages);
  useEffect(() => {
    listeners.add(setList);
    return () => listeners.delete(setList);
  }, []);

  if (!list.length) return null;

  return html`
    <div class="position-fixed top-0 start-50 translate-middle-x mt-2" style="z-index:1080; width:min(28rem,92vw)">
      ${list.map((m) => html`
        <div key=${m.id} class="alert alert-${m.variant} alert-dismissible shadow-sm py-2 px-3 mb-2">
          ${m.text}
          <button type="button" class="btn-close" aria-label=${t('action.close')} onClick=${() => dismissFlash(m.id)}></button>
        </div>
      `)}
    </div>
  `;
}
