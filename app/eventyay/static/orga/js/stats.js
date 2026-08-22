const globalData = document.getElementById("global-data")
const dataMapping = globalData && globalData.dataset.mapping ? JSON.parse(globalData.dataset.mapping) : {}
let searchUrl = globalData && globalData.dataset.url ? globalData.dataset.url : ""

const drawTimeline = (targetId, elementIds) => {
    const targetElement = document.getElementById(targetId)
    if (!targetElement) return null

    const dataElements = elementIds
        .map((id) => document.getElementById(id))
        .filter((element) => element && element.dataset.timeline)

    if (!dataElements.length) return null

    const annotations = globalData && globalData.dataset.annotations ? globalData.dataset.annotations : '{"deadlines":[]}'
    const deadlines = JSON.parse(annotations).deadlines.map(
        (element) => {
            return {
                x: new Date(element[0]).getTime(),
                borderColor: "#ff4560",
                strokeDashArray: 0,
                label: {
                    style: {
                        borderColor: "#ff4560",
                        background: "#ff4560",
                        color: "#fff",
                        fontSize: "14px",
                        padding: { top: 5 },
                    },
                    text: element[1],
                },
            }
        },
    )
    let options = {
        series: dataElements.map((element) => {
            return {
                name: element.dataset.label,
                data: JSON.parse(element.dataset.timeline).map((element) => {
                    return { x: new Date(element.x), y: element.y }
                }),
            }
        }),
        xaxis: {
            type: "datetime",
            tooltip: { enabled: false },
            labels: {
                datetimeUTC: false,
                format: "dd MMM",
                datetimeFormatter: {
                    year: "yyyy",
                    month: "MMM yyyy",
                    day: "dd MMM",
                    hour: "HH:mm",
                },
                style: {
                    fontWeight: 400,
                },
            },
        },
        annotations: {
            xaxis: deadlines,
        },
        chart: {
            redrawOnParentResize: true,
            height: 250,
            type: "area",
            toolbar: {
                tools: {
                    download: false,
                    selection: false,
                    zoom: false,
                    zoomin: false,
                    zoomout: false,
                    pan: false,
                    reset: false,
                },
            },
        },
        colors: ["#008FFB", "#00E396"],
        fill: {
            type: ["gradient", "gradient"],
        },
        dataLabels: {
            enabled: false,
        },
        legend: {
            formatter: function (val, opts) {
                if (val.length > 15) val = val.slice(0, 15) + "…"
                return val
            },
            position: "top",
        },
        responsive: [
            {
                breakpoint: 480,
                options: {
                    chart: {
                        width: 300,
                    },
                    legend: {
                        position: "bottom",
                    },
                },
            },
        ],
        tooltip: {
            enabled: true,
            shared: true,
            x: {
                show: true,
                format: "dd MMM yyyy",
            },
            marker: { show: true },
            onDatasetHover: { highlightDataSeries: true },
        },
    }
    const chart = new ApexCharts(targetElement, options)
    chart.render()
    return chart
}

const getPieData = (id) => {
    const element = document.getElementById(id)
    if (!element || !element.dataset.states) return null
    const data = JSON.parse(element.dataset.states)
    if (!data || !data.length) return null
    return {
        series: data.map((e) => e.value),
        labels: data.map((e) => e.label),
    }
}

const typeMapping = {
    track: "track",
    type: "submission_type",
    state: "state",
    language: "content_locale",
}

const handleChartSelection = (type, label) => {
    if (!dataMapping[type]) return
    const searchValue = dataMapping[type][label]
    if (searchValue) {
        searchUrl += "&" + typeMapping[type] + "=" + searchValue
        window.location.href = searchUrl
    }
}

const drawBarChart = (data, scope, type) => {
    const id = scope + "-" + type
    const element = document.getElementById(id)
    if (!element || !data || !data.series || !data.series.length) return null

    // Sort entries descending by value
    const paired = data.labels.map((label, i) => ({ label, value: data.series[i] }))
    paired.sort((a, b) => b.value - a.value)

    const options = {
        series: [{
            name: "Count",
            data: paired.map((item) => item.value),
        }],
        chart: {
            height: Math.max(220, paired.length * 36),
            width: "100%",
            redrawOnParentResize: true,
            type: "bar",
            toolbar: { show: false },
            events: {
                dataPointSelection: (event, chartContext, config) => {
                    const label = paired[config.dataPointIndex]?.label
                    if (label) handleChartSelection(type, label)
                },
                dataPointMouseEnter: () => {
                    element.style.cursor = "pointer"
                },
                dataPointMouseLeave: () => {
                    element.style.cursor = "inherit"
                },
            },
        },
        plotOptions: {
            bar: {
                horizontal: true,
                distributed: true,
                borderRadius: 4,
                dataLabels: { position: "top" },
            },
        },
        dataLabels: {
            enabled: true,
            offsetX: 20,
            style: { fontSize: "12px", colors: ["#333"] },
        },
        xaxis: {
            categories: paired.map((item) => item.label),
            labels: { show: false },
            axisBorder: { show: false },
            axisTicks: { show: false },
        },
        yaxis: {
            labels: {
                maxWidth: 160,
                formatter: (val) => {
                    if (typeof val === "string" && val.length > 20) return val.slice(0, 19) + "…"
                    return val
                },
            },
        },
        legend: { show: false },
        tooltip: {
            y: {
                formatter: (val) => val + " proposals/sessions",
            },
        },
    }

    let chart = new ApexCharts(element, options)
    chart.render()
    return chart
}

const drawPieChart = (data, scope, type) => {
    const id = scope + "-" + type
    const element = document.getElementById(id)
    if (!element || !data || !data.series || !data.series.length) return null

    const options = {
        series: data.series,
        labels: data.labels,
        chart: {
            height: 320,
            width: "100%",
            redrawOnParentResize: true,
            type: "donut",
            events: {
                dataPointSelection: (event, chartContext, config) => {
                    const label = config.w.config.labels[config.dataPointIndex]
                    if (label) handleChartSelection(type, label)
                },
                dataPointMouseEnter: () => {
                    element.style.cursor = "pointer"
                },
                dataPointMouseLeave: () => {
                    element.style.cursor = "inherit"
                },
            },
        },
        dataLabels: {
            enabled: false,
        },
        legend: {
            formatter: function (val, opts) {
                if (val.length > 20) val = val.slice(0, 20) + "…"
                return val + " - " + opts.w.globals.series[opts.seriesIndex]
            },
        },
        responsive: [
            {
                breakpoint: 480,
                options: {
                    chart: {
                        width: 300,
                    },
                    legend: {
                        position: "bottom",
                    },
                },
            },
        ],
        plotOptions: {
            pie: {
                customScale: 0.85,
                donut: {
                    labels: {
                        show: true,
                        name: {
                            formatter: (val) => {
                                const details = val.indexOf("(") // Truncate duration display in centre of donut chart
                                if (details > -1)
                                    val = val.substring(0, details)
                                if (val.length < 16) return val
                                return val.slice(0, 15) + "…"
                            },
                        },
                    },
                },
            },
        },
        tooltip: {
            enabled: false,
        },
    }

    let chart = new ApexCharts(element, options)
    chart.render()
    return chart
}

const renderCategoricalChart = (data, scope, type) => {
    // If more than 6 categories exist, render a clean horizontal bar chart instead of a crowded donut
    if (data.labels && data.labels.length > 6) {
        return drawBarChart(data, scope, type)
    }
    return drawPieChart(data, scope, type)
}

let chartTypes = ["state"]
if (dataMapping.type) chartTypes.push("type")
if (dataMapping.track) chartTypes.push("track")
if (dataMapping.language) chartTypes.push("language")

const renderAllCharts = () => {
    // Timelines
    if (document.getElementById("proposal-timeline")) {
        drawTimeline("proposal-timeline", ["submission-timeline-data"])
    } else if (document.getElementById("timeline")) {
        drawTimeline("timeline", ["submission-timeline-data"])
    }

    if (document.getElementById("talk-timeline")) {
        drawTimeline("talk-timeline", ["talk-timeline-data"])
    }

    // Categorical charts (donut for <=6 categories, sorted bar chart for >6)
    chartTypes.forEach((item) => {
        const subData = getPieData("submission-" + item + "-data")
        if (subData) {
            renderCategoricalChart(subData, "submission", item)
        }
        const talkData = getPieData("talk-" + item + "-data")
        if (talkData) {
            renderCategoricalChart(talkData, "talk", item)
        }
    })
}

/* generate statistics charts. delay to draw the correct size immediately */
setTimeout(renderAllCharts, 10)
