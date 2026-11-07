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

    // Klaro only knows how to link a privacy policy, so the cookie policy link
    // is added to the notice and to the preference modal here. Klaro re-renders
    // its own markup, so the link is restored whenever it is dropped.
    const cookiePolicy = config.eventyayCookiePolicy;
    if (cookiePolicy) {
        const buildCookiePolicyLink = () => {
            const paragraph = document.createElement('p');
            paragraph.className = 'eventyay-cookie-policy';
            const link = document.createElement('a');
            link.href = cookiePolicy.url;
            link.textContent = cookiePolicy.label;
            paragraph.appendChild(link);
            return paragraph;
        };

        const ensureCookiePolicyLinks = () => {
            const noticeText = document.getElementById('id-cookie-notice');
            if (noticeText && !noticeText.parentElement.querySelector('.eventyay-cookie-policy')) {
                noticeText.after(buildCookiePolicyLink());
            }
            document.querySelectorAll('.cm-header').forEach((header) => {
                if (!header.querySelector('.eventyay-cookie-policy')) {
                    header.appendChild(buildCookiePolicyLink());
                }
            });
        };

        const klaroRoot = document.getElementById(config.elementID) || document.body;
        new MutationObserver(ensureCookiePolicyLinks).observe(klaroRoot, { childList: true, subtree: true });
        ensureCookiePolicyLinks();
    }

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
