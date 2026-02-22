/*globals $, Chart, gettext*/
$(function () {
    if (!$("#quota-stats").length) {
        return;
    }

    var data = JSON.parse($("#quota-chart-data").html());
    var labels = data.map(function (d) { return d.label; });
    var values = data.map(function (d) { return d.value; });
    var colors = [
        '#0044CC', // paid
        '#0088CC', // pending
        '#BD362F', // vouchers
        '#F89406', // carts
        '#51A351'  // available
    ];

    var canvas = document.createElement('canvas');
    $("#quota_chart").css("height", "250px").empty().append(canvas);

    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, data.length),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
});

$(function () {
    if (!$("input[name=productvars]").length) {
        return;
    }
    var autofill = ($("#id_name").val() === "");

    $("#id_name").on("change keyup keydown keypress", function () {
        autofill = false;
    });

    $("input[name=productvars]").change(function () {
        if (autofill) {
            var names = [];
            $("input[name=productvars]:checked").each(function () {
                names.push($.trim($(this).closest("label").text()));
            });
            $("#id_name").val(names.join(', '));
        }
    });
});
