/*
 * Bootstraps the Klaro consent manager from the admin-managed configuration.
 *
 * Klaro itself is vendored under static/klaro/ and loaded as a UMD bundle, so
 * it is available here as `window.klaro`. The configuration is read from a JSON
 * script tag rather than an inline script, which keeps the page free of inline
 * JavaScript and compatible with a strict CSP.
 */
import { syncConsentedEmbeds } from './embeds.js';

const configElement = document.getElementById('klaro-config');
const klaro = window.klaro;

if (configElement && klaro) {
    const config = JSON.parse(configElement.textContent);

    // Klaro reads the config off window when it renders the banner.
    window.klaroConfig = config;
    klaro.setup(config);

    // Footer "Privacy settings" entry point, and the button inside every
    // blocked-embed placeholder.
    document.querySelectorAll('[data-privacy-settings]').forEach((trigger) => {
        trigger.addEventListener('click', (event) => {
            event.preventDefault();
            klaro.show(config);
        });
    });

    // Contextual consent for embeds; see embeds.js.
    const manager = klaro.getManager(config);
    const syncEmbeds = () => syncConsentedEmbeds((service) => manager.getConsent(service));

    manager.watch({ update: syncEmbeds });
    syncEmbeds();
}
