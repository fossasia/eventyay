/**
 * Talks dashboard widgets: readiness donuts + internal-note char counter.
 * External script only (CSP-safe). No jQuery.
 */

function parseJsonAttr(el, name, fallback) {
    const raw = el.getAttribute(name);
    if (!raw) {
        return fallback;
    }
    try {
        return JSON.parse(raw);
    } catch (error) {
        console.error('talks_dashboard_charts: failed to parse', name, error);
        return fallback;
    }
}

function renderDonut(el) {
    if (typeof window.ApexCharts === 'undefined') {
        console.error('talks_dashboard_charts: ApexCharts is not loaded');
        return;
    }
    if (el.dataset.chartBound === '1') {
        return;
    }
    const labels = parseJsonAttr(el, 'data-labels', []);
    const series = parseJsonAttr(el, 'data-series', []).map(Number);
    const colors = parseJsonAttr(el, 'data-colors', []);
    if (!series.length || series.every((value) => value === 0)) {
        // Keep a visible empty state ring
        series.length = 0;
        series.push(1);
        labels.length = 0;
        labels.push('—');
    }

    const chart = new window.ApexCharts(el, {
        chart: {
            type: 'donut',
            height: 160,
            fontFamily: 'inherit',
            animations: { enabled: true, speed: 350 },
        },
        series,
        labels,
        colors: colors.length ? colors : ['#2185d0', '#e5e7eb'],
        legend: { show: false },
        dataLabels: { enabled: false },
        stroke: { width: 2, colors: ['#ffffff'] },
        plotOptions: {
            pie: {
                donut: {
                    size: '72%',
                    labels: {
                        show: true,
                        name: { show: false },
                        value: {
                            fontSize: '18px',
                            fontWeight: 700,
                            color: '#111827',
                        },
                        total: {
                            show: true,
                            label: el.getAttribute('data-total-label') || '',
                            fontSize: '11px',
                            color: '#6b7280',
                            formatter(w) {
                                const totals = w.globals.seriesTotals;
                                // Ignore placeholder empty-state series
                                if (totals.length === 1 && labels[0] === '—') {
                                    return '0';
                                }
                                return totals.reduce((a, b) => a + b, 0);
                            },
                        },
                    },
                },
            },
        },
        tooltip: {
            y: {
                formatter(value) {
                    return String(value);
                },
            },
        },
    });
    chart.render();
    el.dataset.chartBound = '1';
}

function initTalksDashboardCharts(root = document) {
    const nodes = root.querySelectorAll('[data-td-donut]');
    for (const node of nodes) {
        renderDonut(node);
    }
}

function initNoteCounter(root = document) {
    const textarea = root.querySelector('[data-note-counter]');
    if (!textarea) {
        return;
    }
    const selector = textarea.getAttribute('data-note-counter');
    const counter = selector ? root.querySelector(selector) : null;
    if (!counter) {
        return;
    }
    const maxLength = Number(textarea.getAttribute('maxlength')) || 1000;
    const update = () => {
        counter.textContent = `${textarea.value.length}/${maxLength}`;
    };
    textarea.addEventListener('input', update);
    update();
}

function whenApexReady(callback) {
    if (typeof window.ApexCharts !== 'undefined') {
        callback();
        return;
    }
    let attempts = 0;
    const timer = window.setInterval(() => {
        attempts += 1;
        if (typeof window.ApexCharts === 'undefined') {
            if (attempts > 40) {
                window.clearInterval(timer);
                console.error('talks_dashboard_charts: timed out waiting for ApexCharts');
            }
            return;
        }
        window.clearInterval(timer);
        callback();
    }, 100);
}

function initDashboard() {
    initNoteCounter();
    const hasDonuts = document.querySelector('[data-td-donut]');
    if (hasDonuts) {
        whenApexReady(() => initTalksDashboardCharts());
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    initDashboard();
}
