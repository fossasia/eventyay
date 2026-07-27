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

const drawPieChart = (data, scope, type) => {
    const id = scope + "-" + type
    const element = document.getElementById(id)
    if (!element || !data || !data.series || !data.series.length) return null

    const typeMapping = {
        track: "track",
        type: "submission_type",
        state: "state",
        language: "content_locale",
    }
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
                    if (!dataMapping[type]) return
                    const label = config.w.config.labels[config.dataPointIndex]
                    const searchValue = dataMapping[type][label]
                    if (searchValue) {
                        searchUrl += "&" + typeMapping[type] + "=" + searchValue
                        window.location.href = searchUrl
                    }
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

    // Pie charts
    chartTypes.forEach((item) => {
        const subData = getPieData("submission-" + item + "-data")
        if (subData) {
            drawPieChart(subData, "submission", item)
        }
        const talkData = getPieData("talk-" + item + "-data")
        if (talkData) {
            drawPieChart(talkData, "talk", item)
        }
    })
}

/* generate statistics charts. delay to draw the correct size immediately */
setTimeout(renderAllCharts, 10)
