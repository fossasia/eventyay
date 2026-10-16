import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { runInNewContext } from "node:vm"
import test from "node:test"

const script = readFileSync(new URL("../../eventyay/static/common/js/base.js", import.meta.url), "utf8")

function createPage(storage = new Map()) {
    const listeners = {}
    const replacements = []

    class Form {}
    class Element {
        constructor(link) {
            this.link = link
        }

        closest(selector) {
            assert.equal(selector, "a[href]")
            return this.link
        }
    }

    runInNewContext(script, {
        document: {
            readyState: "loading",
            addEventListener: (name, callback) => { listeners[`document:${name}`] = callback },
        },
        window: {
            location: {
                href: "https://example.test/event/",
                origin: "https://example.test",
                replace: (url) => { replacements.push(url) },
            },
            addEventListener: (name, callback) => { listeners[`window:${name}`] = callback },
        },
        sessionStorage: {
            getItem: (key) => storage.get(key) ?? null,
            setItem: (key, value) => storage.set(key, value),
        },
        URL,
        HTMLFormElement: Form,
        Element,
        console,
    })

    return {
        click(href) {
            listeners["document:click"]({ target: new Element({ href }) })
        },
        submit(action) {
            const form = new Form()
            form.action = action
            listeners["document:submit"]({ target: form })
        },
        pageshow(persisted) {
            listeners["window:pageshow"]({ persisted })
        },
        get replacements() { return replacements },
        storage,
    }
}

test("navigates stale BFCache pages with GET after logout, including multiple Back restores", () => {
    const storage = new Map()
    const firstBackPage = createPage(storage)
    const secondBackPage = createPage(storage)
    firstBackPage.click("https://example.test/common/logout/")
    firstBackPage.pageshow(true)
    secondBackPage.pageshow(true)
    assert.deepEqual(firstBackPage.replacements, ["https://example.test/event/"])
    assert.deepEqual(secondBackPage.replacements, ["https://example.test/event/"])
})

test("marks logout forms and ignores non-logout navigation", () => {
    const page = createPage()
    page.submit("https://example.test/common/logout/")
    assert.equal(page.storage.get("eventyay.logout-version"), "1")

    const otherPage = createPage()
    otherPage.click("https://example.test/event/")
    otherPage.pageshow(true)
    assert.deepEqual(otherPage.replacements, [])
})

test("does not navigate a fresh page restored from BFCache without a later logout", () => {
    const storage = new Map()
    const logoutPage = createPage(storage)
    logoutPage.submit("https://example.test/logout/")
    const freshPage = createPage(storage)
    freshPage.pageshow(true)
    assert.deepEqual(freshPage.replacements, [])
})

test("matches actual common and event logout routes, including encoded segments", () => {
    const page = createPage()
    page.click("https://example.test/common/logout/")
    page.click("https://example.test/%63ommon/logout/")
    page.click("https://example.test/org%61nizer/event/log%6Fut")
    assert.equal(page.storage.get("eventyay.logout-version"), "3")
})

test("ignores ordinary paths that only end in logout", () => {
    const page = createPage()
    page.click("https://example.test/organizer/logout/")
    page.click("https://example.test/page/logout/")
    assert.equal(page.storage.has("eventyay.logout-version"), false)
})
