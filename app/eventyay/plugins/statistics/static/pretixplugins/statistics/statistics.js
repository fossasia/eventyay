/*globals $, Chart, gettext, django*/
function gettext(msgid) {
    if (typeof django !== 'undefined' && typeof django.gettext !== 'undefined') {
        return django.gettext(msgid);
    }
    return msgid;
}

$(function () {
    var obdRaw = JSON.parse($("#obd-data").html());
    var revRaw = JSON.parse($("#rev-data").html());
    var obpRaw = JSON.parse($("#obp-data").html());

    // --- Orders by day chart ---
    var obdCanvas = document.createElement('canvas');
    $("#obd_chart").css("height", "250px").empty().append(obdCanvas);
    new Chart(obdCanvas, {
        type: 'line',
        data: {
            labels: obdRaw.map(function (d) { return d.date; }),
            datasets: [
                {
                    label: gettext('Placed orders'),
                    data: obdRaw.map(function (d) { return d.ordered; }),
                    borderColor: '#2185d0',
                    backgroundColor: 'rgba(33,133,208,0.15)',
                    fill: true,
                    tension: 0,
                    pointRadius: 2
                },
                {
                    label: gettext('Paid orders'),
                    data: obdRaw.map(function (d) { return d.paid; }),
                    borderColor: '#50a167',
                    backgroundColor: 'rgba(80,161,103,0.15)',
                    fill: true,
                    tension: 0,
                    pointRadius: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: {
                x: { ticks: { maxTicksLimit: 12 } },
                y: { beginAtZero: true }
            }
        }
    });

    // --- Revenue over time chart ---
    var currency = $.trim($("#currency").html());
    var revCanvas = document.createElement('canvas');
    $("#rev_chart").css("height", "250px").empty().append(revCanvas);
    new Chart(revCanvas, {
        type: 'line',
        data: {
            labels: revRaw.map(function (d) { return d.date; }),
            datasets: [
                {
                    label: gettext('Total revenue'),
                    data: revRaw.map(function (d) { return d.revenue; }),
                    borderColor: '#2185d0',
                    backgroundColor: 'rgba(33,133,208,0.15)',
                    fill: true,
                    tension: 0,
                    pointRadius: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return currency + ' ' + context.parsed.y.toFixed(2);
                        }
                    }
                }
            },
            scales: {
                x: { ticks: { maxTicksLimit: 12 } },
                y: { beginAtZero: true }
            }
        }
    });

    // --- Orders by product chart ---
    var obpCanvas = document.createElement('canvas');
    $("#obp_chart").css("height", "250px").empty().append(obpCanvas);
    new Chart(obpCanvas, {
        type: 'bar',
        data: {
            labels: obpRaw.map(function (d) { return d.product_short || d.item_short; }),
            datasets: [
                {
                    label: gettext('Placed orders'),
                    data: obpRaw.map(function (d) { return d.ordered; }),
                    backgroundColor: '#2185d0'
                },
                {
                    label: gettext('Paid orders'),
                    data: obpRaw.map(function (d) { return d.paid; }),
                    backgroundColor: '#50a167'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        title: function (items) {
                            // Show full product name in tooltip
                            var idx = items[0].dataIndex;
                            return (obpRaw[idx].product || obpRaw[idx].item || '');
                        }
                    }
                }
            },
            scales: {
                x: { ticks: { maxRotation: 30 } },
                y: { beginAtZero: true }
            }
        }
    });
});
