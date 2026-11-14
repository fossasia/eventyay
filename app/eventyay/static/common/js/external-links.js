const configuration = document.querySelector('script[data-external-link-url]').dataset;
const interstitial = new URL(configuration.externalLinkUrl, window.location.origin);
const signedRedirect = configuration.externalLinkRedirectUrl
    ? new URL(configuration.externalLinkRedirectUrl, window.location.origin).pathname : null;
const confirmationPage = window.location.pathname === interstitial.pathname;
const navigationLinks = 'a';
const xlinkNamespace = 'http://www.w3.org/1999/xlink';
const protectedLinks = new WeakSet();

function protectLink(link) {
    if (!link.matches(navigationLinks) || (confirmationPage && (
        link.hasAttribute('data-external-link-continue') || link.hasAttribute('data-external-link-cancel')
    ))) return;
    const useXlink = !link.hasAttribute('href') && link.hasAttributeNS(xlinkNamespace, 'href');
    const href = useXlink ? link.getAttributeNS(xlinkNamespace, 'href') : link.getAttribute('href');
    if (href === null) return;
    let destination;
    try {
        destination = new URL(href, document.baseURI);
    } catch (error) {
        if (error instanceof TypeError) {
            console.warn('Unable to validate link destination.', error);
            return;
        }
        throw error;
    }
    if (!['http:', 'https:'].includes(destination.protocol)) return;
    const local = destination.origin === window.location.origin;
    const signed = local && destination.pathname === signedRedirect && destination.searchParams.has('url');
    const protectedWarning = local && protectedLinks.has(link) && destination.pathname === interstitial.pathname;
    if (local && !signed && !protectedWarning) return;
    const warning = signed || protectedWarning ? destination : new URL(interstitial);
    if (!signed && !protectedWarning) warning.searchParams.set('next', destination.href);
    warning.searchParams.set('return_url', window.location.href);
    if (configuration.externalLinkOrigin) warning.searchParams.set('return_origin', configuration.externalLinkOrigin);
    link.removeAttribute('download');
    protectedLinks.add(link);
    if (href === warning.href) return;
    if (useXlink) link.setAttributeNS(xlinkNamespace, 'xlink:href', warning.href);
    else link.setAttribute('href', warning.href);
}

function protectLinks(root) {
    if (root instanceof Element) protectLink(root);
    root.querySelectorAll(navigationLinks).forEach(protectLink);
}

// Rewrite synchronously on activation, before MutationObserver delivers newly inserted or changed links.
for (const eventType of ['click', 'auxclick', 'contextmenu']) {
    window.addEventListener(eventType, (event) => {
        const link = event.composedPath().find((node) => node instanceof Element && node.matches(navigationLinks));
        if (link) protectLink(link);
    }, {capture: true});
}

protectLinks(document);
new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        if (mutation.type === 'attributes' && ['href', 'xlink:href'].includes(mutation.attributeName)) {
            protectLink(mutation.target);
        }
        for (const node of mutation.addedNodes) {
            if (node instanceof Element) protectLinks(node);
        }
    }
}).observe(document.body, {childList: true, subtree: true, attributes: true});
