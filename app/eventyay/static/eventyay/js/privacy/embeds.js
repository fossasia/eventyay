/*
 * Contextual consent for third-party embeds, shared by the built-in banner and
 * the external CMP bridge.
 *
 * The server never emits the embed URL as an iframe src. It sits on a wrapper
 * as data-consent-src, and the frame is only built here once the service has
 * consent. The wrapper stays in the DOM for the life of the page so that
 * withdrawing consent can find the frame and tear it down again.
 */
const buildEmbed = (wrapper) => {
    const iframe = document.createElement('iframe');
    iframe.src = wrapper.dataset.consentSrc;
    iframe.title = wrapper.dataset.consentTitle || '';
    iframe.loading = 'lazy';
    iframe.allowFullscreen = true;
    return iframe;
};

export const syncConsentedEmbeds = (hasConsent) => {
    document.querySelectorAll('[data-consent-embed]').forEach((wrapper) => {
        const placeholder = wrapper.querySelector('[data-consent-placeholder]');
        const iframe = wrapper.querySelector('iframe');
        const consented = hasConsent(wrapper.dataset.consentEmbed);

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
