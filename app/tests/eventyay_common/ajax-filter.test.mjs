import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const source = readFileSync(
    new URL('../../eventyay/static/eventyay-common/js/ajax-filter.js', import.meta.url),
    'utf8'
);

function createTimerQueue() {
    let nextId = 0;
    const timers = new Map();

    return {
        setTimeout(callback) {
            const id = ++nextId;
            timers.set(id, callback);
            return id;
        },
        clearTimeout(id) {
            timers.delete(id);
        },
        flush() {
            const callbacks = Array.from(timers.values());
            timers.clear();
            callbacks.forEach(fn => fn());
        },
        get size() {
            return timers.size;
        },
    };
}

function createMockElement(tagName, { classes = [], attrs = {} } = {}) {
    const el = {
        tagName: tagName.toUpperCase(),
        className: classes.join(' '),
        classList: {
            add(...names) {
                const set = new Set(el.className.split(/\s+/).filter(Boolean));
                names.forEach(n => set.add(n));
                el.className = Array.from(set).join(' ');
            },
            remove(...names) {
                const set = new Set(el.className.split(/\s+/).filter(Boolean));
                names.forEach(n => set.delete(n));
                el.className = Array.from(set).join(' ');
            },
            contains(name) {
                return el.className.split(/\s+/).filter(Boolean).includes(name);
            },
        },
        attributes: { ...attrs },
        children: [],
        style: {},
        parentElement: null,
        textContent: '',
        get nextSibling() {
            if (!this.parentElement) return null;
            const idx = this.parentElement.children.indexOf(this);
            return idx !== -1 && idx + 1 < this.parentElement.children.length
                ? this.parentElement.children[idx + 1]
                : null;
        },
        setAttribute(name, value) {
            this.attributes[name] = String(value);
        },
        getAttribute(name) {
            return Object.prototype.hasOwnProperty.call(this.attributes, name)
                ? this.attributes[name]
                : null;
        },
        removeAttribute(name) {
            delete this.attributes[name];
        },
        matches(selector) {
            if (selector === '[data-ajax-results-region]') {
                return this.getAttribute('data-ajax-results-region') !== null;
            }
            if (selector === '[data-ajax-loading-status]') {
                return this.getAttribute('data-ajax-loading-status') !== null;
            }
            if (selector.startsWith('.')) {
                return this.classList.contains(selector.slice(1));
            }
            return this.tagName.toLowerCase() === selector.toLowerCase();
        },
        closest(selector) {
            const parts = selector.split(/\s+/);
            let cur = this;
            if (parts.length === 2 && parts[0] === '.nav-tabs' && parts[1] === 'a') {
                if (cur.tagName === 'A') {
                    let p = cur.parentElement;
                    while (p) {
                        if (p.classList.contains('nav-tabs')) return cur;
                        p = p.parentElement;
                    }
                }
                return null;
            }
            while (cur) {
                if (cur.matches(selector)) return cur;
                cur = cur.parentElement;
            }
            return null;
        },
        appendChild(child) {
            child.parentElement = this;
            this.children.push(child);
            return child;
        },
        insertBefore(child, referenceNode) {
            child.parentElement = this;
            if (!referenceNode) {
                this.children.push(child);
            } else {
                const idx = this.children.indexOf(referenceNode);
                if (idx === -1) {
                    this.children.push(child);
                } else {
                    this.children.splice(idx, 0, child);
                }
            }
            return child;
        },
        replaceChildren(...nodes) {
            this.children.forEach(c => {
                c.parentElement = null;
            });
            this.children = [];
            nodes.forEach(n => this.appendChild(n));
        },
        replaceWith(replacement) {
            if (!this.parentElement) return;
            const idx = this.parentElement.children.indexOf(this);
            if (idx !== -1) {
                replacement.parentElement = this.parentElement;
                this.parentElement.children[idx] = replacement;
                this.parentElement = null;
            }
        },
        querySelector(selector) {
            for (const child of this.children) {
                if (child.matches(selector)) return child;
                const nested = child.querySelector(selector);
                if (nested) return nested;
            }
            return null;
        },
        querySelectorAll(selector) {
            const results = [];
            for (const child of this.children) {
                if (child.matches(selector)) results.push(child);
                results.push(...child.querySelectorAll(selector));
            }
            return results;
        },
        dispatchEvent() {},
    };
    return el;
}

function createDeferred() {
    let resolve;
    let reject;
    const promise = new Promise((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

function createTestEnv({ fetch, DOMParser, isEventsOverview = true } = {}) {
    const timers = createTimerQueue();
    const root = createMockElement('main');
    const tabList = createMockElement('ul', {
        classes: isEventsOverview ? ['nav', 'nav-tabs', 'events-overview-tabs'] : ['nav', 'nav-tabs', 'pfv-tabs'],
    });
    const tabItem = createMockElement('li');
    const tabLink = createMockElement('a', { attrs: { href: '?status=past&tab=past' } });
    tabItem.appendChild(tabLink);
    tabList.appendChild(tabItem);
    root.appendChild(tabList);

    const resultsContainer = createMockElement('div', {
        attrs: { 'data-ajax-results-region': '' },
    });
    const initialRow = createMockElement('table');
    resultsContainer.appendChild(initialRow);
    root.appendChild(resultsContainer);

    const navigationUrls = [];
    const pushedUrls = [];

    const document = {
        readyState: 'loading',
        addEventListener() {},
        createElement(tag) {
            return createMockElement(tag);
        },
        getElementById() {
            return null;
        },
        querySelector(selector) {
            return root.querySelector(selector);
        },
        querySelectorAll(selector) {
            return root.querySelectorAll(selector);
        },
    };

    const window = {
        gettext: text => text,
        location: {
            _href: 'https://eventyay.test/common/events/?tab=live',
            origin: 'https://eventyay.test',
            get href() {
                return this._href;
            },
            set href(val) {
                navigationUrls.push(val);
                this._href = val;
            },
        },
        addEventListener() {},
        setTimeout: timers.setTimeout,
        clearTimeout: timers.clearTimeout,
    };

    const context = {
        AbortController,
        DOMException,
        URL,
        URLSearchParams,
        CustomEvent: class CustomEvent {},
        Event: class Event {},
        document,
        window,
        fetch,
        DOMParser,
        history: {
            pushState(_state, _title, url) {
                pushedUrls.push(url);
                window.location._href = new URL(url, window.location.origin).href;
            },
        },
        console: { error() {} },
    };

    runInNewContext(
        `${source}\n;globalThis.__hooks = { fetchAndReplace, handleTabClick, handlePopState, getActiveController: () => activeRequestController };`,
        context
    );

    return {
        ...context.__hooks,
        root,
        tabLink,
        resultsContainer,
        timers,
        navigationUrls,
        pushedUrls,
        window,
    };
}

function createHtmlParser(resultsElement) {
    return class MockDOMParser {
        parseFromString() {
            return {
                querySelector(selector) {
                    return selector === '[data-ajax-results-region]' ? resultsElement : null;
                },
                querySelectorAll() {
                    return [];
                },
            };
        }
    };
}

test('real AbortController cancellation does not clear newer loading state', async () => {
    const firstSignalStates = [];
    const secondResponse = createDeferred();
    let callCount = 0;

    const fetch = (_url, options) => {
        callCount += 1;
        if (callCount === 1) {
            return new Promise((_resolve, reject) => {
                options.signal.addEventListener('abort', () => {
                    firstSignalStates.push(options.signal.aborted);
                    reject(new DOMException('The operation was aborted.', 'AbortError'));
                });
            });
        }
        return secondResponse.promise;
    };

    const newerResults = createMockElement('div', { attrs: { 'data-ajax-results-region': '' } });
    const env = createTestEnv({ fetch, DOMParser: createHtmlParser(newerResults) });

    const firstReq = env.fetchAndReplace('/events?tab=past', true, null, true);
    // Spinner replaced old table immediately
    assert.equal(env.resultsContainer.getAttribute('aria-busy'), 'true');
    assert.equal(env.resultsContainer.children[0].getAttribute('aria-hidden'), 'true');

    const secondReq = env.fetchAndReplace('/events?tab=draft', true, null, true);
    // Let abort microtask settle while second request is still pending
    await Promise.resolve();
    await firstReq;

    assert.deepEqual(firstSignalStates, [true]);
    // Newer request's busy state and pending announcement must still be intact
    assert.equal(env.resultsContainer.getAttribute('aria-busy'), 'true');
    assert.equal(env.timers.size, 1);
    env.timers.flush();
    const statusEl = env.root.querySelector('[data-ajax-loading-status]');
    assert.equal(statusEl.textContent, 'Loading…');
    assert.equal(env.resultsContainer.nextSibling, statusEl);

    secondResponse.resolve({
        ok: true,
        text: () => Promise.resolve('<html>draft</html>'),
    });
    await secondReq;

    assert.equal(env.root.children.includes(newerResults), true);
    assert.equal(statusEl.textContent, 'Events updated.');
    assert.equal(env.getActiveController(), null);
});

test('ignores stale response.text() after newer request succeeds or fails', async () => {
    const firstResponse = createDeferred();
    const firstBody = createDeferred();
    const firstBodyStarted = createDeferred();
    let callCount = 0;

    const fetch = () => {
        callCount += 1;
        if (callCount === 1) {
            return firstResponse.promise;
        }
        return Promise.resolve({ ok: false, status: 503 });
    };

    const staleResults = createMockElement('div', { attrs: { 'data-ajax-results-region': '' } });
    const env = createTestEnv({ fetch, DOMParser: createHtmlParser(staleResults) });

    const olderReq = env.fetchAndReplace('/events?tab=past', true, null, true);
    firstResponse.resolve({
        ok: true,
        text() {
            firstBodyStarted.resolve();
            return firstBody.promise;
        },
    });
    await firstBodyStarted.promise;

    const newerReq = env.fetchAndReplace('/events?tab=draft', true, null, true);
    await newerReq;

    // Newer failed -> navigated to fallback URL and cleared busy state
    assert.deepEqual(env.navigationUrls, ['/events?tab=draft']);
    assert.equal(env.resultsContainer.getAttribute('aria-busy'), null);

    // Late stale body must not replace DOM or re-navigate
    firstBody.resolve('<html>stale</html>');
    await olderReq;
    env.timers.flush();

    assert.equal(env.root.children.includes(staleResults), false);
    assert.deepEqual(env.navigationUrls, ['/events?tab=draft']);
    assert.equal(env.root.querySelector('[data-ajax-loading-status]').textContent, '');
});

test('ignores older non-abort failure after a newer tab request starts', async () => {
    const firstResponse = createDeferred();
    const secondResponse = createDeferred();
    let callCount = 0;

    const fetch = () => {
        callCount += 1;
        return callCount === 1 ? firstResponse.promise : secondResponse.promise;
    };

    const newerResults = createMockElement('div', { attrs: { 'data-ajax-results-region': '' } });
    const env = createTestEnv({ fetch, DOMParser: createHtmlParser(newerResults) });

    const olderReq = env.fetchAndReplace('/events?tab=past', true, null, true);
    const newerReq = env.fetchAndReplace('/events?tab=draft', true, null, true);

    // Older request rejects with a non-abort network error while newer is still loading
    firstResponse.reject(new Error('Network down'));
    await olderReq;

    assert.deepEqual(env.navigationUrls, []);
    assert.equal(env.resultsContainer.getAttribute('aria-busy'), 'true');

    secondResponse.resolve({
        ok: true,
        text: () => Promise.resolve('<html>draft</html>'),
    });
    await newerReq;

    assert.equal(env.root.children.includes(newerResults), true);
    assert.deepEqual(env.navigationUrls, []);
});

test('cleans up loading state when response lacks results container', async () => {
    const fetch = () => Promise.resolve({ ok: true, text: () => Promise.resolve('<html>no region</html>') });
    const env = createTestEnv({ fetch, DOMParser: createHtmlParser(null) });

    await env.fetchAndReplace('/events?tab=past', true, null, true);
    env.timers.flush();

    assert.equal(env.resultsContainer.getAttribute('aria-busy'), null);
    assert.equal(env.root.querySelector('[data-ajax-loading-status]').textContent, '');
    assert.deepEqual(env.navigationUrls, ['/events?tab=past']);
});

test('fast completion cancels deferred loading announcement', async () => {
    const newerResults = createMockElement('div', { attrs: { 'data-ajax-results-region': '' } });
    const fetch = () => Promise.resolve({ ok: true, text: () => Promise.resolve('<html>fast</html>') });
    const env = createTestEnv({ fetch, DOMParser: createHtmlParser(newerResults) });

    await env.fetchAndReplace('/events?tab=past', true, null, true);
    assert.equal(env.timers.size, 0);
    env.timers.flush();

    const statusEl = env.root.querySelector('[data-ajax-loading-status]');
    assert.equal(statusEl.textContent, '');
});

test('scopes spinner to events-overview-tabs and preserves opacity fallback for other tabs', async () => {
    const response = createDeferred();
    const fetch = () => response.promise;
    const newerResults = createMockElement('div', { attrs: { 'data-ajax-results-region': '' } });

    // 1. Events overview tab click -> spinner + aria-busy
    const eventsEnv = createTestEnv({ fetch, DOMParser: createHtmlParser(newerResults), isEventsOverview: true });
    let prevented = false;
    eventsEnv.handleTabClick({
        target: eventsEnv.tabLink,
        preventDefault() {
            prevented = true;
        },
    });
    assert.equal(prevented, true);
    assert.equal(eventsEnv.resultsContainer.getAttribute('aria-busy'), 'true');
    assert.equal(eventsEnv.resultsContainer.style.opacity, '1');

    // 2. Non-events tab click -> opacity 0.5, no spinner, no aria-busy
    const otherEnv = createTestEnv({ fetch, DOMParser: createHtmlParser(newerResults), isEventsOverview: false });
    otherEnv.handleTabClick({
        target: otherEnv.tabLink,
        preventDefault() {},
    });
    assert.equal(otherEnv.resultsContainer.getAttribute('aria-busy'), null);
    assert.equal(otherEnv.resultsContainer.style.opacity, '0.5');
    assert.equal(otherEnv.resultsContainer.children[0].tagName, 'TABLE');

    // 3. Events overview popstate -> spinner + aria-busy
    eventsEnv.handlePopState();
    assert.equal(eventsEnv.resultsContainer.getAttribute('aria-busy'), 'true');

    response.resolve({ ok: true, text: () => Promise.resolve('<html>ok</html>') });
});
