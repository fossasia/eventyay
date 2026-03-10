/*global $, gettext*/
$(function () {
    // Question view
    if (!$(".form-order-change").length) {
        return;
    }
    $(".form-order-change").each(function () {
        var url = $(this).attr("data-pricecalc-endpoint");
        var $productvar = $(this).find("[name*=productvar]");
        var $subevent = $(this).find("[name*=subevent]");
        var $tax_rule = $(this).find("[name*=tax_rule]");
        var $price = $(this).find("[name*=price]");
        var update_price = function () {
            console.log(url);
            var productvar = $productvar.val();
            var product = null;
            var variation = null;
            if (productvar.indexOf("-")) {
                product = parseInt(productvar.split("-")[0]);
                variation = parseInt(productvar.split("-")[1]);
            } else {
                product = parseInt(productvar);
            }
            $price.closest(".field-container").append("<small class=\"loading-indicator\"><span class=\"fa fa-cog fa-spin\"></span> " +
                gettext("Calculating default price…") + "</small>");
            $.ajax(
                {
                    'type': 'POST',
                    'url': url,
                    'headers': {'X-CSRFToken': $("input[name=csrfmiddlewaretoken]").val()},
                    'data': JSON.stringify({
                        'product': product,
                        'variation': variation,
                        'subevent': $subevent.val(),
                        'tax_rule': $tax_rule.val(),
                        'locale': $("body").attr("data-pretixlocale"),
                    }),
                    'contentType': "application/json",
                    'success': function (data) {
                        $price.val(data.gross_formatted);
                        $tax_rule.val(data.tax_rule);
                        $price.closest(".field-container").find(".loading-indicator").remove();
                    },
                    // 'error': …
                    'context': this,
                    'dataType': 'json',
                    'timeout': 30000
                }
            );
        };
        $productvar.on("change", function () { $tax_rule.val(null); update_price() });
        $tax_rule.on("change", update_price);
        $subevent.on("change", update_price).on("change", function () {
            var seat = $(this).closest(".form-order-change").find("[id$=seat]");
            if (seat.length) {
                seat.prop("required", !!$subevent.val());
            }
        });
    });
    $('[data-model-select2=seat]').each(function () {
        var $s = $(this);
        $s.select2({
            theme: "bootstrap",
            delay: 100,
            allowClear: !$s.prop("required"),
            width: '100%',
            language: $("body").attr("data-select2-locale"),
            placeholder: $(this).attr("data-placeholder"),
            ajax: {
                url: function() {
                    var se = $(this).closest(".form-order-change, .form-horizontal").attr("data-subevent");
                    var url = $(this).attr('data-select2-url');
                    var changed = $(this).closest(".form-order-change, .form-horizontal").find("[id$=subevent]").val();
                    if (changed) {
                        return url + '?subevent=' + changed;
                    } else if (se) {
                        return url + '?subevent=' + se;
                    } else {
                        return url;
                    }
                },
                data: function (params) {
                    return {
                        query: params.term,
                        page: params.page || 1
                    }
                }
            },
            templateResult: function (res) {
                if (!res.id) {
                    return res.text;
                }
                var $ret = $("<span>").append(
                    $("<span>").addClass("primary").append($("<div>").text(res.text).html())
                );
                if (res.event) {
                    $ret.append(
                        $("<span>").addClass("secondary").append(
                            $("<span>").addClass("fa fa-calendar fa-fw")
                        ).append(" ").append($("<div>").text(res.event).html())
                    );
                }
                return $ret;
            },
        });
    });
});
