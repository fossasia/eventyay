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
        setAttribute(name, value) {
            this.attributes[name] = value;
        },
        appendChild(child) {
            this.children.push(child);
            return child;
        },
        replaceChildren(...children) {
            this.children = children;
        },
    };
}

function createHarness({ resultsContainer, fetch, DOMParser } = {}) {
    const document = {
        readyState: 'loading',
        addEventListener() {},
        querySelector(selector) {
            return selector === '[data-ajax-results-region]' ? resultsContainer : null;
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
        document,
        window,
        fetch,
        DOMParser,
        console: { error() {} },
    };

    runInNewContext(
        source + '\n;globalThis.__ajaxFilterTestHooks = { showResultsLoadingState, fetchAndReplace };',
        context
    );

    return context.__ajaxFilterTestHooks;
}

test('shows an accessible loading state in the results region', () => {
    const resultsContainer = createElement('div');
    const { showResultsLoadingState } = createHarness({ resultsContainer });

    showResultsLoadingState(resultsContainer);

    assert.equal(resultsContainer.attributes['aria-busy'], 'true');
    assert.equal(resultsContainer.style.opacity, '1');
    assert.equal(resultsContainer.children.length, 1);

    const status = resultsContainer.children[0];
    assert.equal(status.attributes.role, 'status');
    assert.equal(status.attributes['aria-live'], 'polite');
    assert.equal(status.children[0].className, 'fa fa-spinner fa-spin');
    assert.equal(status.children[1].textContent, ' Loading…');
});

test('ignores an older response when a newer tab request has started', async () => {
    const resultsContainer = createElement('div');
    let resolveFirstResponse;
    let resolveFirstBody;
    let markFirstBodyStarted;
    let parserCalls = 0;
    let replacements = 0;

    const firstResponse = new Promise(resolve => {
        resolveFirstResponse = resolve;
    });
    const firstBody = new Promise(resolve => {
        resolveFirstBody = resolve;
    });
    const firstBodyStarted = new Promise(resolve => {
        markFirstBodyStarted = resolve;
    });

    resultsContainer.replaceWith = () => {
        replacements += 1;
    };

    let fetchCalls = 0;
    const fetch = () => {
        fetchCalls += 1;
        if (fetchCalls === 1) {
            return firstResponse;
        }
        return Promise.resolve({ ok: false, status: 503 });
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

    const olderRequest = fetchAndReplace('/events?tab=past', true, null, true);
    resolveFirstResponse({
        ok: true,
        text() {
            markFirstBodyStarted();
            return firstBody;
        },
    });
    await firstBodyStarted;

    const newerRequest = fetchAndReplace('/events?tab=draft', true, null, true);
    await newerRequest;

    resolveFirstBody('<html>stale results</html>');
    await olderRequest;

    assert.equal(parserCalls, 0);
    assert.equal(replacements, 0);
});
