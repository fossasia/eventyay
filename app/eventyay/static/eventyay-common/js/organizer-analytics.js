function parseData(el, attr) {
    if (!el) return null
    const raw = el.dataset[attr]
    if (!raw) return null
    try {
        return JSON.parse(raw)
    } catch (e) {
        console.error('organizer-analytics: failed to parse', attr, e)
        return null
    }
}

const PALETTE = ['#2185d0', '#21ba45', '#f2711c', '#db2828', '#a333c8', '#fbbd08', '#00b5ad']

function drawOrdersOverTime() {
    const dataEl = document.getElementById('orders-over-time-data')
    const chartEl = document.getElementById('orders-over-time-chart')
    if (!dataEl || !chartEl) return

    const series = parseData(dataEl, 'series')
    if (!series || series.length === 0) return

    const labelOrdered = dataEl.dataset.labelOrdered || 'Placed'
    const labelPaid = dataEl.dataset.labelPaid || 'Paid'

    new Morris.Area({
        element: 'orders-over-time-chart',
        data: series,
        xkey: 'x',
        ykeys: ['ordered', 'paid'],
        labels: [labelOrdered, labelPaid],
        lineColors: [PALETTE[0], PALETTE[1]],
        smooth: false,
        resize: true,
        fillOpacity: 0.3,
        behaveLikeLine: true
    })
}

function drawOrdersByStatus() {
    const dataEl = document.getElementById('orders-by-status-data')
    const chartEl = document.getElementById('orders-by-status-chart')
    if (!dataEl || !chartEl) return

    const series = parseData(dataEl, 'series')
    if (!series || series.length === 0) return

    const options = {
        series: series.map((d) => d.value),
        labels: series.map((d) => d.label),
        chart: {
            type: 'donut',
            height: 220,
            redrawOnParentResize: true,
            animations: { enabled: false },
        },
        colors: PALETTE,
        dataLabels: { enabled: false },
        legend: {
            position: 'bottom',
            formatter: (val, opts) => {
                const short = val.length > 15 ? val.slice(0, 15) + '...' : val
                return `${short} - ${opts.w.globals.series[opts.seriesIndex]}`
            },
        },
        plotOptions: {
            pie: { donut: { labels: { show: true } } },
        },
        tooltip: { enabled: true },
    }
    new ApexCharts(chartEl, options).render()
}

function drawRevenueOverTime() {
    const dataEl = document.getElementById('revenue-over-time-data')
    const chartEl = document.getElementById('revenue-over-time-chart')
    if (!dataEl || !chartEl) return

    const series = parseData(dataEl, 'series')
    if (!series || series.length === 0) return

    const label = dataEl.dataset.label || 'Revenue'

    new Morris.Area({
        element: 'revenue-over-time-chart',
        data: series,
        xkey: 'x',
        ykeys: ['y'],
        labels: [label],
        lineColors: [PALETTE[1]],
        smooth: false,
        resize: true,
        fillOpacity: 0.3
    })
}

function drawProposalsByState() {
    const dataEl = document.getElementById('proposals-by-state-data')
    const chartEl = document.getElementById('proposals-by-state-chart')
    if (!dataEl || !chartEl) return

    const series = parseData(dataEl, 'series')
    if (!series || series.length === 0) return

    const options = {
        series: series.map((d) => d.value),
        labels: series.map((d) => d.label),
        chart: {
            type: 'donut',
            height: 220,
            redrawOnParentResize: true,
            animations: { enabled: false },
        },
        colors: PALETTE,
        dataLabels: { enabled: false },
        legend: {
            position: 'bottom',
            formatter: (val, opts) => {
                const short = val.length > 15 ? val.slice(0, 15) + '...' : val
                return `${short} - ${opts.w.globals.series[opts.seriesIndex]}`
            },
        },
        plotOptions: {
            pie: { donut: { labels: { show: true } } },
        },
        tooltip: { enabled: true },
    }
    new ApexCharts(chartEl, options).render()
}

function drawProposalsOverTime() {
    const dataEl = document.getElementById('proposals-over-time-data')
    const chartEl = document.getElementById('proposals-over-time-chart')
    if (!dataEl || !chartEl) return

    const series = parseData(dataEl, 'series')
    if (!series || series.length === 0) return

    const label = dataEl.dataset.label || 'New proposals'

    const options = {
        series: [
            {
                name: label,
                data: series.map((d) => ({ x: new Date(d.x), y: d.y })),
            },
        ],
        chart: {
            type: 'area',
            height: 220,
            redrawOnParentResize: true,
            toolbar: { show: false },
            animations: { enabled: false },
        },
        xaxis: { type: 'datetime', tooltip: { enabled: false } },
        yaxis: { min: 0, labels: { formatter: (v) => Math.round(v) } },
        colors: [PALETTE[2]],
        fill: { type: 'gradient' },
        dataLabels: { enabled: false },
        stroke: { curve: 'smooth', width: 2 },
        legend: { show: false },
        tooltip: { shared: true, x: { format: 'dd MMM yyyy' } },
    }
    new ApexCharts(chartEl, options).render()
}

function drawCheckinRate() {
    const dataEl = document.getElementById('checkin-rate-data')
    const chartEl = document.getElementById('checkin-rate-chart')
    if (!dataEl || !chartEl) return

    const series = parseData(dataEl, 'series')
    if (!series || series.length === 0) return

    const events = series.map((d) => d.event.length > 12 ? d.event.slice(0, 10) + '...' : d.event)
    const totals = series.map((d) => d.total)
    const checkedIn = series.map((d) => d.checked_in)

    const labelCheckedIn = dataEl.dataset.labelCheckedIn || 'Checked in'
    const labelTotal = dataEl.dataset.labelTotal || 'Total'

    const options = {
        series: [
            { name: labelCheckedIn, data: checkedIn },
            { name: labelTotal, data: totals },
        ],
        chart: {
            type: 'bar',
            height: 220,
            redrawOnParentResize: true,
            toolbar: { show: false },
            animations: { enabled: false },
        },
        plotOptions: {
            bar: {
                horizontal: false,
                dataLabels: { position: 'top' },
            },
        },
        xaxis: {
            categories: events,
            labels: {
                rotate: -45,
                rotateAlways: false,
                hideOverlappingLabels: true,
                maxHeight: 60
            }
        },
        yaxis: {
            min: 0,
            forceNiceScale: true,
            labels: {
                formatter: (v) => Number.isInteger(v) ? v : ''
            }
        },
        colors: [PALETTE[1], PALETTE[0]],
        dataLabels: { enabled: false },
        legend: { position: 'top' },
        tooltip: { shared: true },
    }
    new ApexCharts(chartEl, options).render()
}

function drawCheckinsOverTime() {
    const dataEl = document.getElementById('checkins-over-time-data')
    const chartEl = document.getElementById('checkins-over-time-chart')
    if (!dataEl || !chartEl) return

    const series = parseData(dataEl, 'series')
    if (!series || series.length === 0) return

    const label = dataEl.dataset.label || 'Check-ins'

    new Morris.Area({
        element: 'checkins-over-time-chart',
        data: series,
        xkey: 'x',
        ykeys: ['y'],
        labels: [label],
        lineColors: [PALETTE[3]],
        smooth: false,
        resize: true,
        fillOpacity: 0.3
    })
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        drawOrdersOverTime()
        drawOrdersByStatus()
        drawRevenueOverTime()
        drawProposalsByState()
        drawProposalsOverTime()
        drawCheckinRate()
        drawCheckinsOverTime()
    }, 50)
})
