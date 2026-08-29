(function () {
    function updateStatus(row, active, statusText) {
        const status = row.querySelector("[data-video-server-status]");
        if (!status) {
            return;
        }
        status.textContent = statusText;
        status.classList.toggle("label-success", active);
        status.classList.toggle("label-default", !active);
    }

    async function toggleServer(input) {
        const row = input.closest("[data-video-server-row]");
        const table = input.closest("[data-video-server-table]");
        const previous = !input.checked;
        input.disabled = true;
        row.classList.add("video-server-row-saving");

        try {
            const response = await fetch(input.dataset.toggleUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": table.dataset.csrfToken,
                },
                body: JSON.stringify({ active: input.checked }),
            });
            let payload = {};
            try {
                payload = await response.json();
            } catch (error) {
                if (!response.ok) {
                    throw new Error("Could not update the video server.");
                }
                throw error;
            }
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "Could not update the video server.");
            }
            input.checked = payload.active;
            updateStatus(row, payload.active, payload.status);
        } catch (error) {
            input.checked = previous;
            window.alert(error.message);
        } finally {
            row.classList.remove("video-server-row-saving");
            input.disabled = false;
        }
    }

    document.addEventListener("change", (event) => {
        const input = event.target.closest("[data-video-server-toggle]");
        if (!input) {
            return;
        }
        toggleServer(input);
    });
}());
