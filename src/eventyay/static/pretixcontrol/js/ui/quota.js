/*globals $, Morris, gettext*/
$(function () {
    if (!$("#quota-stats").length) {
        return;
    }

    $(".chart").css("height", "250px");
    new Morris.Donut({
        element: 'quota_chart',
        data: JSON.parse($("#quota-chart-data").html()),
        resize: true,
        colors: [
            '#0044CC', // paid
            '#0088CC', // pending
            '#BD362F', // vouchers
            '#F89406', // carts
            '#51A351' // available
        ]
    });
});

$(function () {
    if (!$("input[name=productvars]").length) {
        return;
    }
    var autofill = ($("#id_name").val() === "");

    $("#id_name").on("change keyup keydown keypress", function () {
        autofill = false;
    })

    $("input[name=productvars]").change(function () {
        if (autofill) {
            var names = [];
            $("input[name=productvars]:checked").each(function () {
                names.push($.trim($(this).closest("label").text()))
            });
            $("#id_name").val(names.join(', '));
        }
    });
});
