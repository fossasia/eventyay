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

    const options = {
        series: [
            { name: labelOrdered, data: series.map(d => ({ x: new Date(d.x), y: d.ordered })) },
            { name: labelPaid, data: series.map(d => ({ x: new Date(d.x), y: d.paid })) }
        ],
        chart: {
            type: 'area',
            height: 220,
            redrawOnParentResize: true,
            toolbar: { show: false },
            animations: { enabled: true }
        },
        colors: [PALETTE[0], PALETTE[1]],
        xaxis: { type: 'datetime', tooltip: { enabled: false }, labels: { format: 'dd MMM' } },
        yaxis: { min: 0, labels: { formatter: (v) => Math.round(v) } },
        stroke: { curve: 'straight', width: 2 },
        fill: { type: 'solid', opacity: 0.15 },
        markers: { size: 4, hover: { size: 6 } },
        dataLabels: { enabled: false },
        legend: { position: 'top' },
        tooltip: { shared: true, x: { format: 'dd MMM yyyy' } }
    }
    new ApexCharts(chartEl, options).render()
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
            animations: { enabled: true },
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

    const currencies = parseData(dataEl, 'currencies') || []
    const label = dataEl.dataset.label || 'Revenue'

    const ykeys = currencies.length > 0 ? currencies : ['y']
    const labels = currencies.length > 0 ? currencies.map(c => `${label} (${c})`) : [label]
    const lineColors = currencies.length > 0
        ? currencies.map((_, i) => PALETTE[(1 + i) % PALETTE.length])
        : [PALETTE[1]]

    const options = {
        series: ykeys.map((key, i) => ({
            name: labels[i],
            data: series.map(d => ({ x: new Date(d.x), y: d[key] || 0 }))
        })),
        chart: {
            type: 'area',
            height: 220,
            redrawOnParentResize: true,
            toolbar: { show: false },
            animations: { enabled: true }
        },
        colors: lineColors,
        xaxis: { type: 'datetime', tooltip: { enabled: false }, labels: { format: 'dd MMM' } },
        yaxis: { min: 0 },
        stroke: { curve: 'straight', width: 2 },
        fill: { type: 'solid', opacity: 0.15 },
        markers: { size: 4, hover: { size: 6 } },
        dataLabels: { enabled: false },
        legend: { position: 'top' },
        tooltip: { shared: true, x: { format: 'dd MMM yyyy' } }
    }
    new ApexCharts(chartEl, options).render()
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
            animations: { enabled: true },
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
            animations: { enabled: true },
        },
        xaxis: { type: 'datetime', tooltip: { enabled: false }, labels: { format: 'dd MMM' } },
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

    const events = series.map((d) => d.event.length > 10 ? d.event.slice(0, 7) + '...' : d.event)
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
            animations: { enabled: true },
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
        tooltip: {
            shared: true,
            x: {
                formatter: (val, { dataPointIndex }) => {
                    const entry = series[dataPointIndex]
                    const name = entry ? entry.event : val
                    let rateStr = ''
                    if (entry && entry.total > 0) {
                        const percent = Math.round((entry.checked_in / entry.total) * 100)
                        rateStr = ` (Rate: ${percent}%)`
                    }
                    const div = document.createElement('div')
                    div.textContent = (name == null ? '' : String(name)) + rateStr
                    return div.innerHTML
                }
            },
            y: {
                formatter: (val) => val
            }
        },
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

    const options = {
        series: [
            { name: label, data: series.map(d => ({ x: new Date(d.x), y: d.y })) }
        ],
        chart: {
            type: 'area',
            height: 220,
            redrawOnParentResize: true,
            toolbar: { show: false },
            animations: { enabled: true }
        },
        colors: [PALETTE[3]],
        xaxis: { type: 'datetime', tooltip: { enabled: false }, labels: { format: 'dd MMM' } },
        yaxis: { min: 0, labels: { formatter: (v) => Math.round(v) } },
        stroke: { curve: 'straight', width: 2 },
        fill: { type: 'solid', opacity: 0.15 },
        markers: { size: 4, hover: { size: 6 } },
        dataLabels: { enabled: false },
        legend: { show: false },
        tooltip: { shared: true, x: { format: 'dd MMM yyyy' } }
    }
    new ApexCharts(chartEl, options).render()
}

function initCharts() {
    if (typeof ApexCharts === 'undefined') {
        setTimeout(initCharts, 30)
        return
    }
    // Yield execution to the browser layout engine to fully resolve grid column widths
    setTimeout(() => {
        drawOrdersOverTime()
        drawOrdersByStatus()
        drawRevenueOverTime()
        drawProposalsByState()
        drawProposalsOverTime()
        drawCheckinRate()
        drawCheckinsOverTime()
    }, 50)
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCharts)
} else {
    initCharts()
}
