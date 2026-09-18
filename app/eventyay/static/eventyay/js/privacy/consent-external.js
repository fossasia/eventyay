/*
 * Bridge between an external CMP and Eventyay's blocked embeds.
 *
 * Eventyay cannot know how every CMP reports consent, so embeds stay blocked
 * until the CMP's own consent callback tells us which services are allowed,
 * either by calling the API below or by dispatching an event:
 *
 *   window.eventyayConsent.grant('youtube');
 *   window.eventyayConsent.revoke('youtube');
 *   document.dispatchEvent(new CustomEvent('eventyay:consent',
 *       { detail: { service: 'youtube', granted: true } }));
 *
 * The service name is the identifier from the third-party service registry.
 */
import { syncConsentedEmbeds } from './embeds.js';

const granted = new Set();
const sync = () => syncConsentedEmbeds((service) => granted.has(service));

const setConsent = (service, allowed) => {
    if (!service) {
        return;
    }
    if (allowed) {
        granted.add(service);
    } else {
        granted.delete(service);
    }
    sync();
};

window.eventyayConsent = {
    grant: (service) => setConsent(service, true),
    revoke: (service) => setConsent(service, false),
};

document.addEventListener('eventyay:consent', (event) => {
    const detail = event.detail || {};
    setConsent(detail.service, Boolean(detail.granted));
});
