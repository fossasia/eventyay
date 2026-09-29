document
    .querySelector("button#generate-widget")
    .addEventListener("click", (event) => {
        document.querySelector("#widget-generation").classList.add("d-none")
        document.querySelector("#generated-widget").classList.remove("d-none")
        const locale = document.querySelector("#id_locale").value
        const format = document.querySelector("#id_schedule_display").value
        const days = Array.from(document.querySelector("#id_days").querySelectorAll("option:checked"), e => e.value)
        const dayAttr = days.length ? ` date-filter="${days.join(",")}"` : ""
        document.querySelectorAll("pre#widget-body, pre#widget-body-markdown").forEach((pre) => {
            pre.textContent = pre.textContent
                .replace("LOCALE", locale)
                .replace("FORMAT", format)
                .replace("FILTER_DAYS", dayAttr)
        })
    })
