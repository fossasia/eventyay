/*global u2f */

function safeSelector(selector) {
    // Basic implementation of safeSelector if it's not available globally,
    // though the original script relied on a global safeSelector.
    // If it's used with `document.querySelector`, standard escaping applies.
    return selector;
}

document.addEventListener('DOMContentLoaded', () => {
    // 1. Collapse and dropdown events
    // Bootstrap 3 uses jQuery trigger(), so native addEventListener won't catch it.
    if (typeof jQuery !== 'undefined') {
        jQuery(document).on('shown.bs.collapse shown.bs.dropdown', function(e) {
            handleShown(e);
        });
    } else {
        document.addEventListener('shown.bs.collapse', (e) => {
            handleShown(e);
        });
        document.addEventListener('shown.bs.dropdown', (e) => {
            handleShown(e);
        });
    }

    function handleShown(e) {
        const target = e.target;
        if (target.matches('.sidebar .dropdown, ul.navbar-nav .dropdown, .navbar-events-collapse') || target.closest('.sidebar .dropdown, ul.navbar-nav .dropdown, .navbar-events-collapse')) {
            const el = target.matches('.sidebar .dropdown, ul.navbar-nav .dropdown, .navbar-events-collapse') ? target : target.closest('.sidebar .dropdown, ul.navbar-nav .dropdown, .navbar-events-collapse');
            const parent = el.parentElement;
            if (parent) {
                const input = parent.querySelector("input");
                if (input) {
                    input.value = "";
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.focus();
                }
            }
        }
    }

    // 2. Click event for '.dropdown-menu .form-box input'
    document.addEventListener('click', (e) => {
        if (e.target.matches('.dropdown-menu .form-box input')) {
            e.stopPropagation();
        }
    });

    // 3. Typeahead logic
    const containers = document.querySelectorAll("[data-event-typeahead]");
    containers.forEach(container => {
        let queryEl = container.querySelector('[data-typeahead-query]');
        if (!queryEl) {
            const fieldSelector = container.getAttribute("data-typeahead-field");
            if (fieldSelector) {
                queryEl = document.querySelector(safeSelector(fieldSelector));
            }
        }
        if (!queryEl) return;

        // Remove old items
        removeResultItems(container);
        let lastQuery = "";

        queryEl.addEventListener("change", () => {
            if (queryEl.value === "") {
                lastQuery = "";
                if (container.getAttribute("data-typeahead-field")) {
                    container.classList.remove('focused');
                    removeResultItems(container);
                    return;
                }
            }
            lastQuery = queryEl.value;
            const thisQuery = queryEl.value;
            
            const sourceUrl = container.getAttribute("data-source");
            const organizer = container.getAttribute("data-organizer");
            const url = new URL(sourceUrl, window.location.origin);
            url.searchParams.append("query", queryEl.value);
            if (organizer) {
                url.searchParams.append("organizer", organizer);
            }

            fetch(url, {
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (thisQuery !== lastQuery) {
                    return; // Lost race condition
                }
                removeResultItems(container);
                
                if (data.results && data.results.length > 0) {
                    data.results.forEach(res => {
                        const li = document.createElement("li");
                        const a = document.createElement("a");
                        a.href = res.url;
                        
                        a.addEventListener("mousedown", function(event) {
                            if (a.href) {
                                location.href = a.href;
                            }
                            li.classList.add("active");
                            event.preventDefault();
                            event.stopPropagation();
                        });

                        const outerDiv = document.createElement("div");

                        if (res.type === "organizer") {
                            const nameSpan = document.createElement("span");
                            nameSpan.className = "event-name-full";
                            
                            const iconSpan = document.createElement("span");
                            iconSpan.className = "fa fa-users fa-fw";
                            
                            const textDiv = document.createElement("div");
                            textDiv.textContent = res.name;
                            
                            nameSpan.appendChild(iconSpan);
                            nameSpan.appendChild(document.createTextNode(" "));
                            // In jQuery it did append($("<div>").text(res.name).html()) which means it appended text directly
                            nameSpan.appendChild(textDiv);
                            
                            outerDiv.appendChild(nameSpan);
                        } else if (res.type === "order" || res.type === "voucher") {
                            const titleSpan = document.createElement("span");
                            titleSpan.className = "event-name-full";
                            const titleDiv = document.createElement("div");
                            titleDiv.textContent = res.title;
                            titleSpan.appendChild(titleDiv);
                            
                            const orgSpan = document.createElement("span");
                            orgSpan.className = "event-organizer";
                            const iconSpan = document.createElement("span");
                            iconSpan.className = "fa fa-calendar fa-fw";
                            const evDiv = document.createElement("div");
                            evDiv.textContent = res.event;
                            orgSpan.appendChild(iconSpan);
                            orgSpan.appendChild(document.createTextNode(" "));
                            orgSpan.appendChild(evDiv);
                            
                            outerDiv.appendChild(titleSpan);
                            outerDiv.appendChild(orgSpan);
                        } else if (res.type === "user") {
                            const nameSpan = document.createElement("span");
                            nameSpan.className = "event-name-full";
                            const iconSpan = document.createElement("span");
                            iconSpan.className = "fa fa-user fa-fw";
                            const textDiv = document.createElement("div");
                            textDiv.textContent = res.name;
                            nameSpan.appendChild(iconSpan);
                            nameSpan.appendChild(document.createTextNode(" "));
                            nameSpan.appendChild(textDiv);
                            
                            outerDiv.appendChild(nameSpan);
                        } else {
                            outerDiv.className = "event-result-item";
                            
                            if (res.icon) {
                                const img = document.createElement("img");
                                img.src = res.icon;
                                img.className = "event-icon";
                                outerDiv.appendChild(img);
                            } else {
                                const iconContainer = document.createElement("div");
                                iconContainer.className = "event-icon event-icon--placeholder";
                                const faIcon = document.createElement("span");
                                faIcon.className = "fa fa-calendar fa-2x";
                                iconContainer.appendChild(faIcon);
                                outerDiv.appendChild(iconContainer);
                            }
                            
                            const textDiv = document.createElement("div");
                            textDiv.className = "event-text";
                            
                            const nameSpan = document.createElement("span");
                            nameSpan.className = "event-name-full";
                            const innerNameDiv = document.createElement("div");
                            innerNameDiv.textContent = res.name;
                            nameSpan.appendChild(innerNameDiv);
                            textDiv.appendChild(nameSpan);
                            
                            const orgSpan = document.createElement("span");
                            orgSpan.className = "event-organizer search-detail";
                            const usersIcon = document.createElement("span");
                            usersIcon.className = "fa fa-users fa-fw";
                            const innerOrgDiv = document.createElement("div");
                            innerOrgDiv.textContent = res.organizer;
                            orgSpan.appendChild(usersIcon);
                            orgSpan.appendChild(document.createTextNode(" "));
                            orgSpan.appendChild(innerOrgDiv);
                            textDiv.appendChild(orgSpan);
                            
                            const dateSpan = document.createElement("span");
                            dateSpan.className = "event-daterange search-detail";
                            const calIcon = document.createElement("span");
                            calIcon.className = "fa fa-calendar fa-fw";
                            dateSpan.appendChild(calIcon);
                            dateSpan.appendChild(document.createTextNode(" " + res.date_range));
                            textDiv.appendChild(dateSpan);
                            
                            outerDiv.appendChild(textDiv);
                        }
                        
                        a.appendChild(outerDiv);
                        li.appendChild(a);
                        container.appendChild(li);
                    });
                }
                
                if (document.activeElement === queryEl && container.children.length > 0) {
                    container.classList.add('focused');
                } else {
                    container.classList.remove('focused');
                }
            })
            .catch(err => console.error('Typeahead fetch error:', err));
        });

        queryEl.addEventListener("keydown", (event) => {
            if (event.which === 38 || event.which === 40) {
                event.preventDefault(); // Prevent cursor movement / page scrolling
            }
            const selected = container.querySelector(".active");
            if (event.which === 13) {  // enter
                if (selected) {
                    const link = selected.querySelector("a");
                    if (link) {
                        location.href = link.href;
                    }
                    event.preventDefault();
                    event.stopPropagation();
                }
            }
        });

        let isMousedownOnContainer = false;
        container.addEventListener("mousedown", () => {
            isMousedownOnContainer = true;
        });
        document.addEventListener("mouseup", () => {
            isMousedownOnContainer = false;
        });

        queryEl.addEventListener("blur", () => {
            // Need a slight delay to allow mousedown to fire on the link
            setTimeout(() => {
                if (!isMousedownOnContainer) {
                    container.classList.remove('focused');
                }
            }, 200);
        });

        // Also close when clicking outside
        document.addEventListener("mousedown", (e) => {
            if (!container.contains(e.target) && e.target !== queryEl) {
                container.classList.remove('focused');
            }
        });

        queryEl.addEventListener("keyup", (event) => {
            const items = Array.from(container.querySelectorAll("li:not(.query-holder)"));
            if (items.length === 0) {
                if (event.which !== 13 && event.which !== 38 && event.which !== 40) {
                    queryEl.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return;
            }
            
            const first = items[0];
            const last = items[items.length - 1];
            let selected = container.querySelector(".active");
            let selectedIndex = selected ? items.indexOf(selected) : -1;

            if (event.which === 13) {  // enter
                event.preventDefault();
                event.stopPropagation();
                return;
            } else if (event.which === 40) {  // down
                let next;
                if (!selected || selectedIndex === items.length - 1) {
                    next = first;
                } else {
                    next = items[selectedIndex + 1];
                }
                if (selected) selected.classList.remove("active");
                next.classList.add("active");
                next.scrollIntoView({ block: 'nearest' });
                event.preventDefault();
                event.stopPropagation();
                return;
            } else if (event.which === 38) {  // up
                let prev;
                if (!selected) {
                    prev = first; // Original logic selects first, then prev goes to last or previous
                    selectedIndex = 0;
                }
                
                if (selectedIndex === 0 || selectedIndex === -1) {
                    prev = last;
                } else {
                    prev = items[selectedIndex - 1];
                }
                
                // The original logic had a check for prev.find("input").length > 0 (query-holder)
                if (prev.querySelector("input")) {
                    prev = last;
                }

                if (selected) selected.classList.remove("active");
                prev.classList.add("active");
                prev.scrollIntoView({ block: 'nearest' });
                event.preventDefault();
                event.stopPropagation();
                return;
            } else {
                queryEl.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    });

    function removeResultItems(container) {
        const items = container.querySelectorAll("li:not(.query-holder)");
        items.forEach(item => item.remove());
    }
});
