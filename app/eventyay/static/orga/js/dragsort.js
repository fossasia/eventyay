/* Makes a table sortable by drag and drop, sending the new state to the server.
 * This implementation is hugely indebted to Julik Tarkhanov and his blog post at
 * https://blog.julik.nl/2022/10/drag-reordering */

const DIRECTION_HORIZONTAL = Symbol();
const DIRECTION_VERTICAL = Symbol();
const INTENT_BEFORE = Symbol();
const INTENT_AFTER = Symbol();
const getCsrfToken = () => {
    for (const name of ['eventyay_csrftoken', 'csrftoken', 'pretix_csrftoken']) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return decodeURIComponent(parts.pop().split(';').shift());
        }
    }
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
};
const EVENTYAY_CSRF_TOKEN = getCsrfToken();

const computeCentroid = (element) => {
    const rect = element.getBoundingClientRect();
    const viewportX = (rect.left + rect.right) / 2;
    const viewportY = (rect.top + rect.bottom) / 2;
    return { x: viewportX + window.scrollX, y: viewportY + window.scrollY };
};

const getSortableElements = (parentElement) => {
    return Array.from(parentElement.querySelectorAll("[dragsort-id], [data-formset-form]")).map(
        (el) => {
            return { element: el, centroid: computeCentroid(el) };
        },
    );
};

const predictDirection = (a, b) => {
    if (!a || !b) return DIRECTION_HORIZONTAL;
    const dx = Math.abs(b.centroid.x - a.centroid.x);
    const dy = Math.abs(b.centroid.y - a.centroid.y);
    return dx > dy ? DIRECTION_HORIZONTAL : DIRECTION_VERTICAL;
};

const intentFrom = (direction, evt, centroid) => {
    if (direction === DIRECTION_HORIZONTAL) {
        return evt.clientX + window.scrollX < centroid.x
            ? INTENT_BEFORE
            : INTENT_AFTER;
    } else {
        return evt.clientY + window.scrollY < centroid.y
            ? INTENT_BEFORE
            : INTENT_AFTER;
    }
};

const pageDistanceBetweenPointerAndCentroid = (evt, centroid) => {
    return Math.hypot(
        centroid.x - (evt.clientX + window.scrollX),
        centroid.y - (evt.clientY + window.scrollY),
    );
};

const unstyleDragIndicators = (parentElement) => {
    parentElement.parentElement
        .querySelectorAll(".drag-indicator")
        .forEach((el) =>
            el.classList.remove(
                "insert-before",
                "insert-after",
                "drag-indicator",
            ),
        );
};

const dragStart = (el) => {
    const parentElement = el.closest("[dragsort-url]");

    const sortableElements = getSortableElements(parentElement);
    const listDirection = predictDirection(...sortableElements);
    const isTable = parentElement.tagName === "TBODY";

    let closest = el;
    let intent = INTENT_BEFORE;

    const dragoverHandler = (evt) => {
        evt.preventDefault();

        const byProximity = sortableElements
            .map((pe) => {
                return {
                    d: pageDistanceBetweenPointerAndCentroid(evt, pe.centroid),
                    ...pe,
                };
            })
            .sort((a, b) => a.d - b.d);
        const { element, centroid } = byProximity[0];

        closest = byProximity[0].element;
        intent = intentFrom(listDirection, evt, byProximity[0].centroid);

        unstyleDragIndicators(parentElement);
        if (intent === INTENT_BEFORE) {
            element.classList.add("drag-indicator", "insert-before");
            if (!element.previousElementSibling && isTable) {
                // First table row, got to add the class to the th row instead
                element.parentElement.parentElement
                    .querySelector("thead")
                    .classList.add("drag-indicator", "insert-after");
            }
        } else {
            element.classList.add("drag-indicator", "insert-after");
        }
    };

    parentElement.addEventListener("dragover", dragoverHandler);
    const stopDragging = () => {
        unstyleDragIndicators(parentElement);
        parentElement.removeEventListener("dragover", dragoverHandler);
        return { closest, intent };
    };
    return stopDragging;
};

let pendingSave = Promise.resolve();

const pushOrder = (parentElement) => {
    const url = parentElement.getAttribute("dragsort-url");
    const ids = Array.from(parentElement.querySelectorAll("[dragsort-id], [data-formset-form]")).map(
        (el) => el.getAttribute("dragsort-id"),
    ).filter((id) => id);
    // Update position fields for form submission
    parentElement.querySelectorAll("[dragsort-id], [data-formset-form]").forEach((el, index) => {
        const positionInput = el.querySelector('input[name$="-position"]');
        if (positionInput) {
            positionInput.value = index + 1;
        }
    });

    const orderValue = ids.join(",");

    if (url) {
        const data = new URLSearchParams();
        data.append("order", orderValue);
        pendingSave = pendingSave
            .catch((err) => {
                console.error("Previous order save failed, continuing with latest order", err);
            })
            .then(async () => {
                const response = await fetch(url, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCsrfToken(),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: data,
                });
                if (!response.ok || response.redirected) {
                    throw new Error(
                        `Order save request failed: status ${response.status}${response.redirected ? " (redirected)" : ""}`
                    );
                }
                const contentType = response.headers.get("content-type") || "";
                if (contentType.includes("application/json")) {
                    const resData = await response.json();
                    if (resData && resData.ok === false) {
                        throw new Error(resData.error || "Order save response indicated failure");
                    }
                }
                return response;
            })
            .catch((err) => {
                console.error("Failed to save new item order", err);
                const message = typeof window.gettext === "function"
                    ? window.gettext("The new order could not be saved. Reload the page and try again.")
                    : "The new order could not be saved. Reload the page and try again.";
                window.alert(message);
                throw err;
            });
        return pendingSave;
    }
};

const initDragsort = () => {
    document.addEventListener("keydown", (evt) => {
        if (evt.key !== "ArrowUp" && evt.key !== "ArrowDown") return;
        const handle = evt.target.closest(".dragsort-button");
        if (!handle) return;

        const el = handle.closest("[dragsort-id]") || handle.closest("[data-formset-form]");
        if (!el || !el.parentElement) return;

        const parentElement = el.closest("[dragsort-url]") || el.parentElement;
        if (evt.key === "ArrowUp") {
            const prev = el.previousElementSibling;
            if (prev && (prev.hasAttribute("dragsort-id") || prev.hasAttribute("data-formset-form"))) {
                evt.preventDefault();
                prev.insertAdjacentElement("beforebegin", el);
                pushOrder(parentElement);
                handle.focus();
            }
        } else if (evt.key === "ArrowDown") {
            const next = el.nextElementSibling;
            if (next && (next.hasAttribute("dragsort-id") || next.hasAttribute("data-formset-form"))) {
                evt.preventDefault();
                next.insertAdjacentElement("afterend", el);
                pushOrder(parentElement);
                handle.focus();
            }
        }
    });

    document.addEventListener("dragstart", (evt) => {
        const handle = evt.target.closest(".dragsort-button");
        if (!handle) return;

        const el = handle.closest("[dragsort-id]") || handle.closest("[data-formset-form]");
        if (!el) return;

        evt.dataTransfer.effectAllowed = "move";
        // Changing the element’s class in the dragstart handler will immediately
        // fire the dragend handler in Chrome, for cursed reasons, so we do it
        // outside the event.
        setTimeout(() => el.classList.add("dragging"), 0);
        setTimeout(() => document.querySelector("body").classList.add("dragging"), 0);

        const stop = dragStart(el);
        if (!stop) return;  // Exit early if dragStart couldn't find a valid parent

        const dropHandler = (dropEvt) => dropEvt.preventDefault();
        el.parentElement.addEventListener("drop", dropHandler, { once: true });

        const dragEndHandler = (dragEvt) => {
            dragEvt.preventDefault();
            el.parentElement.removeEventListener("drop", dropHandler);
            el.classList.remove("dragging");
            document.querySelector("body").classList.remove("dragging");

            const { closest, intent } = stop();
            if (closest && closest !== el) {
                if (intent === INTENT_AFTER) {
                    closest.insertAdjacentElement("afterend", el);
                } else {
                    closest.insertAdjacentElement("beforebegin", el);
                }
                pushOrder(el.parentElement);
            }
        };

        document.addEventListener("dragend", dragEndHandler, { once: true });
    });
};

if (typeof onReady === 'function') {
    onReady(initDragsort);
} else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDragsort);
} else {
    initDragsort();
}
