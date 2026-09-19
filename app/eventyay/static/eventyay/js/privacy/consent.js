/*
 * Bootstraps the Klaro consent manager from the admin-managed configuration.
 *
 * Klaro itself is vendored under static/klaro/ and loaded as a UMD bundle, so
 * it is available here as `window.klaro`. The configuration is read from a JSON
 * script tag rather than an inline script, which keeps the page free of inline
 * JavaScript and compatible with a strict CSP.
 */
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

    // Contextual consent: the wrapper stays in the DOM for the life of the page
    // so that accepting a category builds the embed and withdrawing it again
    // tears the embed back down.
    const manager = klaro.getManager(config);

    const buildEmbed = (wrapper) => {
        const iframe = document.createElement('iframe');
        iframe.src = wrapper.dataset.consentSrc;
        iframe.title = wrapper.dataset.consentTitle || '';
        iframe.loading = 'lazy';
        iframe.allowFullscreen = true;
        return iframe;
    };

    const syncConsentedEmbeds = () => {
        document.querySelectorAll('[data-consent-embed]').forEach((wrapper) => {
            const placeholder = wrapper.querySelector('[data-consent-placeholder]');
            const iframe = wrapper.querySelector('iframe');
            const consented = manager.getConsent(wrapper.dataset.consentEmbed);

            if (consented && !iframe) {
                wrapper.appendChild(buildEmbed(wrapper));
                if (placeholder) {
                    placeholder.hidden = true;
                }
            } else if (!consented && iframe) {
                // Withdrawal: drop the frame so the third party stops loading.
                iframe.remove();
                if (placeholder) {
                    placeholder.hidden = false;
                }
            }
        });
    };

    manager.watch({ update: syncConsentedEmbeds });
    syncConsentedEmbeds();
}
