const resultsSelector = ".event-log-results";

let requestVersion = 0;
let activeRequest = null;

function getResults(html) {
    const parsed = new DOMParser().parseFromString(html, "text/html");
    return parsed.querySelector(resultsSelector);
}

function announceStatus(messageKey, fallback) {
    const status = document.querySelector("[data-event-log-status]");
    if (status) {
        status.textContent = status.dataset[messageKey] || fallback;
    }
}

function loadResults(url, updateHistory) {
    const target = new URL(url, window.location.href);

    if (target.origin !== window.location.origin) {
        window.location.href = target.href;
        return;
    }

    const version = ++requestVersion;

    activeRequest?.abort();
    activeRequest = new AbortController();

    document.querySelector(resultsSelector)?.setAttribute("aria-busy", "true");
    announceStatus("loadingMessage", "Loading event logs");

    fetch(target.href, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        signal: activeRequest.signal,
    })
        .then((response) => {
            if (!response.ok) {
                throw new Error(
                    "Event log request failed with HTTP status " + response.status
                );
            }
            return response.text();
        })
        .then((html) => {
            if (version !== requestVersion) return;

            const newResults = getResults(html);
            const currentResults = document.querySelector(resultsSelector);

            if (!newResults || !currentResults) {
                window.location.href = target.href;
                return;
            }

            const focusedControl = currentResults.contains(document.activeElement)
                ? document.activeElement
                : null;
            const focusedHref = focusedControl?.matches(".pagination a")
                ? focusedControl.getAttribute("href")
                : null;
            const focusedSearch = focusedControl?.matches(
                ".event-log-search-form input[name='q']"
            );

            newResults.setAttribute("aria-busy", "false");
            currentResults.replaceWith(newResults);
            announceStatus("loadedMessage", "Event logs updated");

            if (focusedSearch) {
                document.querySelector(
                    `${resultsSelector} .event-log-search-form input[name="q"]`
                )?.focus();
            } else if (focusedHref !== null) {
                const replacementLink = [
                    ...document.querySelectorAll(`${resultsSelector} .pagination a`),
                ].find((link) => link.getAttribute("href") === focusedHref);
                replacementLink?.focus();
            }

            if (updateHistory) {
                window.history.pushState({}, "", target.href);
            }
        })
        .catch((error) => {
            if (error.name === "AbortError" || version !== requestVersion) return;
            console.error(
                "Failed to load event logs via AJAX; falling back to navigation.",
                {
                    url: target.href,
                    error,
                }
            );
            window.location.href = target.href;
        });
}

document.addEventListener("submit", (event) => {
    const form = event.target.closest(".event-log-search-form");
    if (!form) return;

    event.preventDefault();

    const target = new URL(form.action || window.location.href, window.location.href);
    const params = new URLSearchParams(new FormData(form));
    params.delete("page");

    const currentPageSize = new URL(window.location.href).searchParams.get("page_size");
    if (currentPageSize && !params.has("page_size")) {
        params.set("page_size", currentPageSize);
    }

    target.search = params.toString();
    loadResults(target.href, true);
});

document.addEventListener("click", (event) => {
    if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
    ) return;

    const targetElement =
        event.target instanceof Element ? event.target : null;

    const anchor = targetElement?.closest(
        ".event-log-results .pagination a, " +
        ".event-log-results a[href*='page_size='], " +
        ".event-log-clear-search"
    );

    if (
        !anchor ||
        !anchor.getAttribute("href") ||
        (anchor.target && anchor.target !== "_self") ||
        anchor.hasAttribute("download")
    ) return;

    const target = new URL(anchor.href, window.location.href);
    if (target.origin !== window.location.origin) return;

    if (anchor.matches(".event-log-clear-search")) {
        const pageSize = new URL(window.location.href).searchParams.get("page_size");
        if (pageSize && !target.searchParams.has("page_size")) {
            target.searchParams.set("page_size", pageSize);
        }
    }

    event.preventDefault();
    loadResults(target.href, true);
});

window.addEventListener("popstate", () => {
    if (document.querySelector(resultsSelector)) {
        loadResults(window.location.href, false);
    }
});
