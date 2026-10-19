const interstitial = document.querySelector('script[data-external-link-url]').dataset.externalLinkUrl;
const confirmationPage = window.location.pathname === new URL(interstitial, window.location.origin).pathname;

function protectLink(link) {
    if (!link.hasAttribute('href') || (confirmationPage && link.hasAttribute('data-external-link-continue'))) return;
    let destination;
    try {
        destination = new URL(link.getAttribute('href'), document.baseURI);
    } catch (error) {
        if (error instanceof TypeError) {
            console.warn('Unable to validate link destination.', error);
            return;
        }
        throw error;
    }
    if (!['http:', 'https:'].includes(destination.protocol) || destination.origin === window.location.origin) return;
    const warning = new URL(interstitial, window.location.origin);
    warning.searchParams.set('next', destination.href);
    link.removeAttribute('download');
    link.href = warning.href;
}

function protectLinks(root) {
    if (root instanceof HTMLAnchorElement) protectLink(root);
    root.querySelectorAll('a[href]').forEach(protectLink);
}

protectLinks(document);
new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        if (mutation.type === 'attributes') protectLink(mutation.target);
        for (const node of mutation.addedNodes) {
            if (node instanceof Element) protectLinks(node);
        }
    }
}).observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['href']});
