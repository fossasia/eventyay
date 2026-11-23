import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('./ajax-filter.js', import.meta.url), 'utf8');

function createElement(tagName) {
    return {
        tagName,
        className: '',
        attributes: {},
        children: [],
        style: {},
        parentElement: null,
        nextSibling: null,
        textContent: '',
        setAttribute(name, value) {
            this.attributes[name] = value;
        },
        removeAttribute(name) {
            delete this.attributes[name];
        },
        appendChild(child) {
            this.children.push(child);
            child.parentElement = this;
            return child;
        },
        replaceChildren(...children) {
            this.children = children;
            children.forEach(child => {
                child.parentElement = this;
            });
        },
        insertBefore(child) {
            this.children.push(child);
            child.parentElement = this;
            return child;
        },
        querySelector(selector) {
            if (selector === '[data-ajax-loading-announcement]') {
                return this.children.find(child => child.attributes['data-ajax-loading-announcement'] !== undefined) || null;
            }
            return null;
        },
        dispatchEvent() {},
        replaceWith(replacement) {
            this.replacement = replacement;
            replacement.parentElement = this.parentElement;
            if (this.parentElement) {
                const index = this.parentElement.children.indexOf(this);
                if (index !== -1) {
                    this.parentElement.children[index] = replacement;
                }
            }
        },
    };
}

function createHarness({ resultsContainer, fetch, DOMParser } = {}) {
    const resultsParent = createElement('main');
    resultsParent.children = [resultsContainer];
    resultsContainer.parentElement = resultsParent;

    const document = {
        readyState: 'loading',
        addEventListener() {},
        querySelector(selector) {
            return selector === '[data-ajax-results-region]' ? resultsContainer : null;
        },
        querySelectorAll() {
            return [];
        },
        createElement,
        createTextNode(textContent) {
            return { nodeType: 3, textContent };
        },
    };

    const window = {
        gettext: text => text,
        location: { href: 'https://eventyay.test/events', origin: 'https://eventyay.test' },
        addEventListener() {},
    };

    const context = {
        AbortController,
        DOMException,
        URL,
        CustomEvent: class CustomEvent {},
        document,
        window,
        fetch,
        DOMParser,
        history: { pushState() {} },
        console: { error() {} },
    };

    runInNewContext(
        source + '\n;globalThis.__ajaxFilterTestHooks = { showResultsLoadingState, fetchAndReplace };',
        context
    );

    return {
        ...context.__ajaxFilterTestHooks,
        document,
        resultsParent,
    };
}

function createDeferred() {
    let resolve;
    const promise = new Promise(r => {
        resolve = r;
    });
    return { promise, resolve };
}

function createResponseDocument(resultsContainer) {
    return {
        querySelector(selector) {
            return selector === '[data-ajax-results-region]' ? resultsContainer : null;
        },
        querySelectorAll() {
            return [];
        },
    };
}

test('shows an accessible loading state outside the busy results region', () => {
    const resultsContainer = createElement('div');
    const { showResultsLoadingState, resultsParent } = createHarness({ resultsContainer });

    const announcement = showResultsLoadingState(resultsContainer);

    assert.equal(resultsContainer.attributes['aria-busy'], 'true');
    assert.equal(resultsContainer.style.opacity, '1');
    assert.equal(resultsContainer.children.length, 1);
    assert.equal(resultsContainer.children[0].attributes['aria-hidden'], 'true');
    assert.equal(resultsContainer.children[0].children[0].className, 'fa fa-spinner fa-spin');
    assert.equal(announcement.parentElement, resultsParent);
    assert.equal(announcement.attributes.role, 'status');
    assert.equal(announcement.attributes['aria-live'], 'polite');
    assert.equal(announcement.attributes['aria-atomic'], 'true');
    assert.equal(announcement.textContent, 'Loading…');
});

test('ignores an older response when a newer tab request has started and fails', async () => {
    const resultsContainer = createElement('div');
    const firstResponse = createDeferred();
    const firstBody = createDeferred();
    const firstBodyStarted = createDeferred();
    let parserCalls = 0;
    let replacements = 0;
    let fetchCalls = 0;

    const fetch = () => {
        fetchCalls += 1;
        return fetchCalls === 1
            ? firstResponse.promise
            : Promise.resolve({ ok: false, status: 503 });
    };

    class TestDOMParser {
        parseFromString() {
            parserCalls += 1;
            return {};
        }
    }

    const { fetchAndReplace } = createHarness({
        resultsContainer,
        fetch,
        DOMParser: TestDOMParser,
    });
    const originalReplaceWith = resultsContainer.replaceWith;
    resultsContainer.replaceWith = function(replacement) {
        replacements += 1;
        originalReplaceWith.call(this, replacement);
    };

    const olderRequest = fetchAndReplace('/events?tab=past', true, null, true);
    firstResponse.resolve({
        ok: true,
        text() {
            firstBodyStarted.resolve();
            return firstBody.promise;
        },
    });
    await firstBodyStarted.promise;

    const newerRequest = fetchAndReplace('/events?tab=draft', true, null, true);
    await newerRequest;

    firstBody.resolve('<html>stale results</html>');
    await olderRequest;

    assert.equal(parserCalls, 0);
    assert.equal(replacements, 0);
});

test('keeps successful newer results when an older response body resolves later', async () => {
    const resultsContainer = createElement('div');
    const newerResults = createElement('div');
    const firstResponse = createDeferred();
    const firstBody = createDeferred();
    const firstBodyStarted = createDeferred();
    let fetchCalls = 0;
    let parserCalls = 0;
    let replacements = 0;

    const fetch = () => {
        fetchCalls += 1;
        return fetchCalls === 1
            ? firstResponse.promise
            : Promise.resolve({
                ok: true,
                text: () => Promise.resolve('<html>new results</html>'),
            });
    };

    class TestDOMParser {
        parseFromString() {
            parserCalls += 1;
            return createResponseDocument(newerResults);
        }
    }

    const { fetchAndReplace, resultsParent } = createHarness({
        resultsContainer,
        fetch,
        DOMParser: TestDOMParser,
    });
    const originalReplaceWith = resultsContainer.replaceWith;
    resultsContainer.replaceWith = function(replacement) {
        replacements += 1;
        originalReplaceWith.call(this, replacement);
    };

    const olderRequest = fetchAndReplace('/events?tab=past', true, null, true);
    firstResponse.resolve({
        ok: true,
        text() {
            firstBodyStarted.resolve();
            return firstBody.promise;
        },
    });
    await firstBodyStarted.promise;

    const newerRequest = fetchAndReplace('/events?tab=draft', true, null, true);
    await newerRequest;

    assert.equal(resultsParent.children[0], newerResults);
    assert.equal(replacements, 1);
    assert.equal(parserCalls, 1);

    firstBody.resolve('<html>stale results</html>');
    await olderRequest;

    assert.equal(resultsParent.children[0], newerResults);
    assert.equal(replacements, 1);
    assert.equal(parserCalls, 1);
});
