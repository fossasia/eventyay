/*global $*/

/**
 * Safely resolve a DOM attribute value as a jQuery CSS selector.
 *
 * Uses document.querySelectorAll() — a CSS-selector-only browser API that
 * cannot interpret strings as HTML — so tainted attribute values can never
 * trigger jQuery's HTML-creation path.  Invalid CSS selectors are caught and
 * result in an empty jQuery collection, keeping call-site chains safe.
 *
 * The guard prevents accidental redefinition when multiple scripts are loaded
 * on the same page.
 */
if (typeof safeSelector === 'undefined') {
    var safeSelector = function (s) {
        if (!s || typeof s !== 'string') return $();
        try {
            return $(document.querySelectorAll(s));
        } catch (e) {
            return $();
        }
    };
}
