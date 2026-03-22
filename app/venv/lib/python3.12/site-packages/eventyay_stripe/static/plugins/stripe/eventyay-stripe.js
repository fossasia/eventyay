/*global $, stripe_pubkey, stripe_loadingmessage, gettext */
'use strict';

var stripeObj = {
    stripe: null,
    elements: null,
    card: null,
    paymentRequest: null,
    paymentRequestButton: null,

    'cc_request': function () {
        waitingDialog.show(gettext("Contacting Stripe …"));
        $(".stripe-errors").hide();

        // ToDo: 'card' --> proper type of payment method
        stripeObj.stripe.createPaymentMethod('card', stripeObj.card).then(function (result) {
            waitingDialog.hide();
            if (result.error) {
                $(".stripe-errors").stop().hide().removeClass("sr-only");
                $(".stripe-errors").html("<div class='alert alert-danger'>" + result.error.message + "</div>");
                $(".stripe-errors").slideDown();
            } else {
                let $form = $("#stripe_payment_method_id").closest("form");
                // Insert the token into the form so it gets submitted to the server
                $("#stripe_payment_method_id").val(result.paymentMethod.id);
                $("#stripe_card_brand").val(result.paymentMethod.card.brand);
                $("#stripe_card_last4").val(result.paymentMethod.card.last4);
                // and submit
                $form.get(0).submit();
            }
        });
    },
    'pm_request': function (method, element, kwargs = {}) {
        waitingDialog.show(gettext("Contacting Stripe …"));
        $(".stripe-errors").hide();

        stripeObj.stripe.createPaymentMethod(method, element, kwargs).then(function (result) {
            waitingDialog.hide();
            if (result.error) {
                $(".stripe-errors").stop().hide().removeClass("sr-only");
                $(".stripe-errors").html("<div class='alert alert-danger'>" + result.error.message + "</div>");
                $(".stripe-errors").slideDown();
            } else {
                var $form = $("#stripe_" + method + "_payment_method_id").closest("form");
                // Insert the token into the form so it gets submitted to the server
                $("#stripe_" + method + "_payment_method_id").val(result.paymentMethod.id);
                if (method === 'card') {
                    $("#stripe_card_brand").val(result.paymentMethod.card.brand);
                    $("#stripe_card_last4").val(result.paymentMethod.card.last4);
                }
                if (method === 'sepa_debit') {
                    $("#stripe_sepa_debit_last4").val(result.paymentMethod.sepa_debit.last4);
                }
                // and submit
                $form.get(0).submit();
            }
        }).catch((e) => {
            waitingDialog.hide();
            $(".stripe-errors").stop().hide().removeClass("sr-only");
            $(".stripe-errors").html("<div class='alert alert-danger'>Technical error, please contact support: " + e + "</div>");
            $(".stripe-errors").slideDown();
        });
    },
    'load': function () {
      if (stripeObj.stripe !== null) {
          return;
      }
      $('.stripe-container').closest("form").find(".checkout-button-row .btn-primary").prop("disabled", true);
        $.ajax(
            {
                url: 'https://js.stripe.com/v3/',
                dataType: 'script',
                success: function () {
                    if ($.trim($("#stripe_connectedAccountId").html())) {
                        stripeObj.stripe = Stripe($.trim($("#stripe_pubkey").html()), {
                            stripeAccount: $.trim($("#stripe_connectedAccountId").html()),
                            locale: $.trim($("body").attr("data-locale"))
                        });
                    } else {
                        stripeObj.stripe = Stripe($.trim($("#stripe_pubkey").html()), {
                            locale: $.trim($("body").attr("data-locale"))
                        });
                    }
                    stripeObj.elements = stripeObj.stripe.elements();
                    if ($.trim($("#stripe_merchantcountry").html()) !== "") {
                        try {
                            stripeObj.paymentRequest = stripeObj.stripe.paymentRequest({
                                country: $("#stripe_merchantcountry").html(),
                                currency: $("#stripe_currency").val().toLowerCase(),
                                total: {
                                    label: gettext('Total'),
                                    amount: parseInt($("#stripe_total").val())
                                },
                                displayItems: [],
                                requestPayerName: false,
                                requestPayerEmail: false,
                                requestPayerPhone: false,
                                requestShipping: false,
                            });

                            stripeObj.paymentRequest.on('paymentmethod', function (ev) {
                                ev.complete('success');

                                let $form = $("#stripe_payment_method_id").closest("form");
                                // Insert the token into the form so it gets submitted to the server
                                $("#stripe_payment_method_id").val(ev.paymentMethod.id);
                                $("#stripe_card_brand").val(ev.paymentMethod.card.brand);
                                $("#stripe_card_last4").val(ev.paymentMethod.card.last4);
                                // and submit
                                $form.get(0).submit();
                            });
                        } catch (e) {
                            stripeObj.paymentRequest = null;
                        }
                    } else {
                        stripeObj.paymentRequest = null;
                    }
                    if ($("#stripe-card").length) {
                        stripeObj.card = stripeObj.elements.create('card', {
                            'style': {
                                'base': {
                                    'fontFamily': '"Open Sans","OpenSans","Helvetica Neue",Helvetica,Arial,sans-serif',
                                    'fontSize': '14px',
                                    'color': '#555555',
                                    'lineHeight': '1.42857',
                                    'border': '1px solid #ccc',
                                    '::placeholder': {
                                        color: 'rgba(0,0,0,0.4)',
                                    },
                                },
                                'invalid': {
                                    'color': 'red',
                                },
                            },
                            classes: {
                                focus: 'is-focused',
                                invalid: 'has-error',
                            }
                        });
                        stripeObj.card.mount("#stripe-card");
                    }
                    stripeObj.card.on('ready', function () {
                       $('.stripe-container').closest("form").find(".checkout-button-row .btn-primary").prop("disabled", false);
                    });
                    if ($("#stripe-payment-request-button").length && stripeObj.paymentRequest != null) {
                      stripeObj.paymentRequestButton = stripeObj.elements.create('paymentRequestButton', {
                        paymentRequest: stripeObj.paymentRequest,
                      });

                      stripeObj.paymentRequest.canMakePayment().then(function(result) {
                        if (result) {
                          stripeObj.paymentRequestButton.mount('#stripe-payment-request-button');
                          $('#stripe-elements .stripe-or').removeClass("hidden");
                          $('#stripe-payment-request-button').parent().removeClass("hidden");
                        } else {
                          $('#stripe-payment-request-button').hide();
                          document.getElementById('stripe-payment-request-button').style.display = 'none';
                        }
                      })
                    };
                    if ($("#stripe-sepa").length) {
                        stripeObj.sepa = stripeObj.elements.create('iban', {
                            'style': {
                                'base': {
                                    'fontFamily': '"Open Sans","OpenSans","Helvetica Neue",Helvetica,Arial,sans-serif',
                                    'fontSize': '14px',
                                    'color': '#555555',
                                    'lineHeight': '1.42857',
                                    'border': '1px solid #ccc',
                                    '::placeholder': {
                                        color: 'rgba(0,0,0,0.4)',
                                    },
                                },
                                'invalid': {
                                    'color': 'red',
                                },
                            },
                            supportedCountries: ['SEPA'],
                            classes: {
                                focus: 'is-focused',
                                invalid: 'has-error',
                            }
                        });
                        stripeObj.sepa.on('change', function (event) {
                            // List of IBAN-countries, that require the country as well as line1-property according to
                            // https://stripe.com/docs/payments/sepa-debit/accept-a-payment?platform=web&ui=element#web-submit-payment
                            if (['AD', 'PF', 'TF', 'GI', 'GB', 'GG', 'VA', 'IM', 'JE', 'MC', 'NC', 'BL', 'PM', 'SM', 'CH', 'WF'].indexOf(event.country) > 0) {
                                $("#stripe_sepa_debit_country").prop('checked', true);
                                $("#stripe_sepa_debit_country").change();
                            } else {
                                $("#stripe_sepa_debit_country").prop('checked', false);
                                $("#stripe_sepa_debit_country").change();
                            }
                            if (event.bankName) {
                                $("#stripe_sepa_debit_bank").val(event.bankName);
                            }
                        });
                        stripeObj.sepa.mount("#stripe-sepa");
                        stripeObj.sepa.on('ready', function () {
                            $('.stripe-container').closest("form").find(".checkout-button-row .btn-primary").prop("disabled", false);
                        });
                    }
                    if ($("#stripe-affirm").length) {
                        stripeObj.affirm = stripeObj.elements.create('affirmMessage', {
                            'amount': parseInt($("#stripe_affirm_total").val()),
                            'currency': $("#stripe_affirm_currency").val(),
                        });

                        stripeObj.affirm.mount('#stripe-affirm');
                    }
                    if ($("#stripe-klarna").length) {
                        try {
                            stripeObj.klarna = stripeObj.elements.create('paymentMethodMessaging', {
                                'amount': parseInt($("#stripe_klarna_total").val()),
                                'currency': $("#stripe_klarna_currency").val(),
                                'countryCode': $("#stripe_klarna_country").val(),
                                'paymentMethodTypes': ['klarna'],
                            });

                            stripeObj.klarna.mount('#stripe-klarna');
                        } catch (e) {
                            console.error(e);
                            $("#stripe-klarna").html("<div class='alert alert-danger'>Technical error, please contact support: " + e + "</div>");
                        }
                    }
                }
            }
        );
    },

    'confirmCard': function (payment_intent_client_secret) {
        $.ajax({
            url: 'https://js.stripe.com/v3/',
            dataType: 'script',
            success: function () {
                if ($.trim($("#stripe_connectedAccountId").html())) {
                    stripeObj.stripe = Stripe($.trim($("#stripe_pubkey").html()), {
                        stripeAccount: $.trim($("#stripe_connectedAccountId").html()),
                        locale: $.trim($("body").attr("data-locale"))
                    });
                } else {
                    stripeObj.stripe = Stripe($.trim($("#stripe_pubkey").html()), {
                        locale: $.trim($("body").attr("data-locale"))
                    });
                }
                stripeObj.stripe.confirmCard(
                    payment_intent_client_secret
                ).then(function (result) {
                    waitingDialog.show(gettext("Confirming your payment …"));
                    location.reload();
                });
            }
        });
    },
    'confirmCardiFrame': function (payment_intent_next_action_redirect_url) {
        waitingDialog.show(gettext("Contacting your bank …"));
        if (!isLiveMode()) {
            let iframe = document.createElement('iframe');
            iframe.src = payment_intent_next_action_redirect_url;
            iframe.className = 'embed-responsive-item';
            $('#scacontainer').append(iframe);
            $('#scacontainer iframe').load(function () {
                waitingDialog.hide();
            });
        } else {
            // Redirect in live mode
            window.location.href = payment_intent_next_action_redirect_url;
        }
    },
    'redirectToPayment': function (payment_intent_next_action_redirect_url) {
        waitingDialog.show(gettext("Contacting your bank …"));

        let payment_intent_redirect_action_handling = $.trim($("#stripe_payment_intent_redirect_action_handling").html());
        if (payment_intent_redirect_action_handling === 'iframe' && !isLiveMode()) {
            let iframe = document.createElement('iframe');
            iframe.src = payment_intent_next_action_redirect_url;
            iframe.className = 'embed-responsive-item';
            $('#scacontainer').append(iframe);
            $('#scacontainer iframe').on("load", function () {
                waitingDialog.hide();
            });
        } else if (payment_intent_redirect_action_handling === 'redirect') {
            window.location.href = payment_intent_next_action_redirect_url;
        }
    },
    'redirectWechatPay': function (payment_intent_client_secret) {
        stripeObj.loadObject(function () {
            stripeObj.stripe.confirmWechatPayPayment(
                payment_intent_client_secret,
                {
                    payment_method_options: {
                        wechat_pay: {
                            client: 'web',
                        },
                    },
                }
            ).then(function (result) {
                if (result.error) {
                    waitingDialog.hide();
                    $(".stripe-errors").stop().hide().removeClass("sr-only");
                    $(".stripe-errors").html("<div class='alert alert-danger'>Technical error, please contact support: " + result.error.message + "</div>");
                    $(".stripe-errors").slideDown();
                } else {
                    waitingDialog.show(gettext("Confirming your payment …"));
                    location.reload();
                }
            });
        });
    },
    'redirectAlipay': function (payment_intent_client_secret) {
        stripeObj.loadObject(function () {
            stripeObj.stripe.confirmAlipayPayment(
                payment_intent_client_secret,
                {
                    return_url: window.location.href
                }
            ).then(function (result) {
                if (result.error) {
                    waitingDialog.hide();
                    $(".stripe-errors").stop().hide().removeClass("sr-only");
                    $(".stripe-errors").html("<div class='alert alert-danger'>Technical error, please contact support: " + result.error.message + "</div>");
                    $(".stripe-errors").slideDown();
                } else {
                    waitingDialog.show(gettext("Confirming your payment …"));
                }
            });
        });
    }
};
$(function () {
    if ($("#stripe_payment_intent_SCA_status").length) {
        let payment_intent_redirect_action_handling = $.trim($("#stripe_payment_intent_redirect_action_handling").html());
        let stt = $.trim($("#order_status").html());
        let url = $.trim($("#order_url").html())
        // show message
        if (payment_intent_redirect_action_handling === 'iframe') {
            window.parent.postMessage('3DS-authentication-complete.' + stt, '*');
            return;
        } else if (payment_intent_redirect_action_handling === 'redirect') {
            waitingDialog.show(gettext("Confirming your payment …"));
            if (stt === 'p') {
                window.location.href = url + '?paid=yes';
            } else {
                window.location.href = url;
            }
        }
    // redirect to payment url: ideal, bancontact, eps, przelewy24
    } else if ($("#stripe_payment_intent_next_action_redirect_url").length) {
        let payment_intent_next_action_redirect_url = $.trim($("#stripe_payment_intent_next_action_redirect_url").html());
        stripeObj.redirectToPayment(payment_intent_next_action_redirect_url);
    // redirect to webchat pay
    } else if ($.trim($("#stripe_payment_intent_action_type").html()) === "wechat_pay_display_qr_code") {
        let payment_intent_client_secret = $.trim($("#stripe_payment_intent_client_secret").html());
        stripeObj.redirectWechatPay(payment_intent_client_secret);
    // redirect to alipay
    } else if ($.trim($("#stripe_payment_intent_action_type").html()) === "alipay_handle_redirect") {
        let payment_intent_client_secret = $.trim($("#stripe_payment_intent_client_secret").html());
        stripeObj.redirectAlipay(payment_intent_client_secret);
    // card payment
    } else if ($("#stripe_payment_intent_client_secret").length) {
        let payment_intent_client_secret = $.trim($("#stripe_payment_intent_client_secret").html());
        stripeObj.confirmCard(payment_intent_client_secret);
    }

    $(window).on("message onmessage", function(e) {
        if (typeof e.originalEvent.data === "string" && e.originalEvent.data.startsWith('3DS-authentication-complete.')) {
            waitingDialog.show(gettext("Confirming your payment …"));
            $('#scacontainer').hide();
            $('#continuebutton').removeClass('hidden');

            if (e.originalEvent.data.split('.')[1] == 'p') {
                window.location.href = $('#continuebutton').attr('href') + '?paid=yes';
            } else {
                window.location.href = $('#continuebutton').attr('href');
            }
        }
    });

    if (!$(".stripe-container").length)
        return;
    if (
        $("input[name=payment][value=stripe]").is(':checked')
        || $("input[name=payment][value=stripe_sepa_debit]").is(':checked')
        || $("input[name=payment][value=stripe_affirm]").is(':checked')
        || $("input[name=payment][value=stripe_klarna]").is(':checked')
        || $(".payment-redo-form").length) {
            stripeObj.load();
    } else {
        $("input[name=payment]").change(function () {
            if (['stripe', 'stripe_sepa_debit', 'stripe_affirm', 'stripe_klarna'].indexOf($(this).val()) > -1) {
                stripeObj.load();
            }
        })
    }

    $("#stripe_other_card").click(
        function (e) {
            $("#stripe_payment_method_id").val("");
            $("#stripe-current-card").slideUp();
            $("#stripe-elements").slideDown();

            e.preventDefault();
            return false;
        }
    );

    if ($("#stripe-current-card").length) {
        $("#stripe-elements").hide();
    }

    $("#stripe_other_account").click(
        function (e) {
            $("#stripe_sepa_debit_payment_method_id").val("");
            $("#stripe-current-account").slideUp();
            // We're using a css-selector here instead of the id-selector,
            // as we're hiding Stripe Elements *and* Django form fields
            $('.stripe-sepa_debit-form').slideDown();

            e.preventDefault();
            return false;
        }
    );

    if ($("#stripe-current-account").length) {
        // We're using a css-selector here instead of the id-selector,
        // as we're hiding Stripe Elements *and* Django form fields
        $('.stripe-sepa_debit-form').hide();
    }

    $('.stripe-container').closest("form").submit(
        function () {
            if ($("input[name=card_new]").length && !$("input[name=card_new]").prop('checked')) {
                return null;
            }
            if (($("input[name=payment][value=stripe]").prop('checked') || $("input[name=payment][type=radio]").length === 0)
                && $("#stripe_payment_method_id").val() == "") {
                stripeObj.cc_request();
                return false;
            }
            
            if (($("input[name=payment][value=stripe_sepa_debit]").prop('checked')) && $("#stripe_sepa_debit_payment_method_id").val() == "") {
                stripeObj.pm_request('sepa_debit', stripeObj.sepa, {
                    billing_details: {
                        name: $("#id_payment_stripe_sepa_debit-accountname").val(),
                        email: $("#stripe_sepa_debit_email").val(),
                        address: {
                            line1: $("#id_payment_stripe_sepa_debit-line1").val(),
                            postal_code: $("#id_payment_stripe_sepa_debit-postal_code").val(),
                            city: $("#id_payment_stripe_sepa_debit-city").val(),
                            country: $("#id_payment_stripe_sepa_debit-country").val(),
                        }
                    }
                });
                return false;
            }
        }
    );
});
function isLiveMode() {
    return window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
}
