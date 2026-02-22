/*global $, Chart, gettext*/
$(function () {
    // Question view
    if (!$("#question-stats").length) {
        return;
    }

    var data_type = $("#question_chart").attr("data-type");
    var raw_data = JSON.parse($("#question-chart-data").html());
    var max_num = (data_type === 'N') ? 20 : 8;
    var others_sum = 0;

    // Truncate long labels
    for (var i = 0; i < raw_data.length; i++) {
        raw_data[i].value = raw_data[i].count;
        raw_data[i].label = raw_data[i].answer;
        if (raw_data[i].label.length > 20) {
            raw_data[i].label = raw_data[i].label.substring(0, 20) + '…';
        }
    }

    // Sort numeric type
    if (data_type === 'N') {
        raw_data.sort(function (a, b) {
            return parseFloat(a.label) - parseFloat(b.label);
        });
    }

    // Limit options
    if (raw_data.length > max_num) {
        for (var j = max_num; j < raw_data.length; j++) {
            others_sum += raw_data[j].count;
        }
        raw_data = raw_data.slice(0, max_num);
        raw_data.push({'value': others_sum, 'label': gettext('Others'), 'count': others_sum});
    }

    var canvas = document.createElement('canvas');
    $("#question_chart").css("height", "250px").empty().append(canvas);

    var labels = raw_data.map(function (d) { return d.label; });
    var values = raw_data.map(function (d) { return d.value || d.count; });

    if (data_type === 'B') {
        var bgColors;
        if (raw_data[0] && raw_data[0].answer_bool) {
            bgColors = ['#50A167', '#C44F4F'];
        } else {
            bgColors = ['#C44F4F', '#50A167'];
        }
        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{ data: values, backgroundColor: bgColors, borderWidth: 1 }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } }
            }
        });
    } else if (data_type === 'C') {
        var palette = [
            '#7F4A91', '#50A167', '#FFB419', '#5F9CD4', '#C44F4F',
            '#83FFFA', '#FF6C38', '#1f5b8e', '#2d683c'
        ];
        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{ data: values, backgroundColor: palette.slice(0, values.length), borderWidth: 1 }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } }
            }
        });
    } else {  // M, N, S, T
        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: gettext('Count'),
                    data: values,
                    backgroundColor: '#2185d0'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { maxRotation: 30 } },
                    y: { beginAtZero: true }
                },
                plugins: { legend: { display: false } }
            }
        });
    }
});

$(function () {
    // Question editor

    if (!$("#answer-options").length) {
        return;
    }

    // Question editor
    $("#id_type").change(question_page_toggle_view);
    $("#id_required").change(question_page_toggle_view);
    question_page_toggle_view();

    function question_page_toggle_view() {
        var show = $("#id_type").val() == "C" || $("#id_type").val() == "M";
        $("#answer-options").toggle(show);

        $("#valid-date").toggle($("#id_type").val() == "D");
        $("#valid-datetime").toggle($("#id_type").val() == "W");
        $("#valid-number").toggle($("#id_type").val() == "N");

        show = $("#id_type").val() == "B" && $("#id_required").prop("checked");
        $(".alert-required-boolean").toggle(show);
    }

    var $val = $("#id_dependency_values");
    var $dq = $("#id_dependency_question");
    var oldval = JSON.parse($("#dependency_value_val").text());
    function update_dependency_options() {
        $val.parent().find(".loading-indicator").remove();
        $("#id_dependency_values option").remove();
        $("#id_dependency_values").prop("required", false);

        var val = $dq.children("option:selected").val();
        if (!val) {
            $("#id_dependency_values").show();
            $val.show();
            return;
        }

        $("#id_dependency_values").prop("required", true);
        $val.hide();
        $val.parent().append("<div class=\"help-block loading-indicator\"><span class=\"fa fa-cog fa-spin\"></span></div>");

        var organizer = $("body").attr("data-organizer");
        var event = $("body").attr("data-event");

        if (!organizer || !event) {
            $val.parent().find(".loading-indicator").remove();
            $val.show();
            return;
        }

        var ajaxUrl = `/control/event/${organizer}/${event}/questions/${val}/options/`;
        $.ajax({
            url: ajaxUrl,
            type: 'GET',
            success: function (data) {
                if (data.type === "B") {
                    $val.append($("<option>").attr("value", "True").text(gettext("Yes")));
                    $val.append($("<option>").attr("value", "False").text(gettext("No")));
                } else {
                    for (var i = 0; i < data.options.length; i++) {
                        var opt = data.options[i];
                        var $opt = $("<option>").attr("value", opt.identifier).text(opt.answer);
                        $val.append($opt);
                    }
                }
                if (oldval) {
                    $val.val(oldval);
                }
                $val.parent().find(".loading-indicator").remove();
                $val.show();
            },
            error: function(xhr, status, error) {
                $val.parent().find(".loading-indicator").remove();
                $val.show();
            }
        });
    }

    update_dependency_options();
    $dq.change(update_dependency_options);
});
