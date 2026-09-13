import { html } from '../h.js';
import { ThemeLangMenu } from './ThemeLangMenu.js';

// The one piece of chrome every route shares: language + theme, rendered once
// here so no view has to import or place ThemeLangMenu itself. Everything
// route-specific — trip list, new-trip form, a trip's own header and tabs — is
// `children`, drawn by app.js underneath this.
export function Shell({ children }) {
  return html`
    <div class="border-bottom bg-body shell-bar">
      <div class="container d-flex justify-content-end py-1" style="max-width:48rem">
        <${ThemeLangMenu} />
      </div>
    </div>
    ${children}
  `;
}
