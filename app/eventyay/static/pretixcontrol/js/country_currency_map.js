(function () {
    'use strict';

    var COUNTRY_CURRENCY = {
        "AC":"SHP","AD":"EUR","AE":"AED","AF":"AFN","AG":"XCD","AI":"XCD",
        "AL":"ALL","AM":"AMD","AO":"AOA","AR":"ARS","AS":"USD","AT":"EUR",
        "AU":"AUD","AW":"AWG","AX":"EUR","AZ":"AZN","BA":"BAM","BB":"BBD",
        "BD":"BDT","BE":"EUR","BF":"XOF","BG":"BGN","BH":"BHD","BI":"BIF",
        "BJ":"XOF","BL":"EUR","BM":"BMD","BN":"BND","BO":"BOB","BQ":"USD",
        "BR":"BRL","BS":"BSD","BT":"BTN","BW":"BWP","BY":"BYN","BZ":"BZD",
        "CA":"CAD","CC":"AUD","CD":"CDF","CF":"XAF","CG":"XAF","CH":"CHF",
        "CI":"XOF","CK":"NZD","CL":"CLP","CM":"XAF","CN":"CNY","CO":"COP",
        "CR":"CRC","CU":"CUP","CV":"CVE","CW":"ANG","CX":"AUD","CY":"EUR",
        "CZ":"CZK","DE":"EUR","DJ":"DJF","DK":"DKK","DM":"XCD","DO":"DOP",
        "DZ":"DZD","EC":"USD","EE":"EUR","EG":"EGP","ER":"ERN","ES":"EUR",
        "ET":"ETB","FI":"EUR","FJ":"FJD","FK":"FKP","FM":"USD","FO":"DKK",
        "FR":"EUR","GA":"XAF","GB":"GBP","GD":"XCD","GE":"GEL","GF":"EUR",
        "GG":"GBP","GH":"GHS","GI":"GIP","GL":"DKK","GM":"GMD","GN":"GNF",
        "GP":"EUR","GQ":"XAF","GR":"EUR","GT":"GTQ","GU":"USD","GW":"XOF",
        "GY":"GYD","HK":"HKD","HN":"HNL","HR":"EUR","HT":"HTG","HU":"HUF",
        "ID":"IDR","IE":"EUR","IL":"ILS","IM":"GBP","IN":"INR","IO":"USD",
        "IQ":"IQD","IR":"IRR","IS":"ISK","IT":"EUR","JE":"GBP","JM":"JMD",
        "JO":"JOD","JP":"JPY","KE":"KES","KG":"KGS","KH":"KHR","KI":"AUD",
        "KM":"KMF","KN":"XCD","KP":"KPW","KR":"KRW","KW":"KWD","KY":"KYD",
        "KZ":"KZT","LA":"LAK","LB":"LBP","LC":"XCD","LI":"CHF","LK":"LKR",
        "LR":"LRD","LS":"LSL","LT":"EUR","LU":"EUR","LV":"EUR","LY":"LYD",
        "MA":"MAD","MC":"EUR","MD":"MDL","ME":"EUR","MF":"EUR","MG":"MGA",
        "MH":"USD","MK":"MKD","ML":"XOF","MM":"MMK","MN":"MNT","MO":"MOP",
        "MP":"USD","MQ":"EUR","MR":"MRU","MS":"XCD","MT":"EUR","MU":"MUR",
        "MV":"MVR","MW":"MWK","MX":"MXN","MY":"MYR","MZ":"MZN","NA":"NAD",
        "NC":"XPF","NE":"XOF","NF":"AUD","NG":"NGN","NI":"NIO","NL":"EUR",
        "NO":"NOK","NP":"NPR","NR":"AUD","NU":"NZD","NZ":"NZD","OM":"OMR",
        "PA":"PAB","PE":"PEN","PF":"XPF","PG":"PGK","PH":"PHP","PK":"PKR",
        "PL":"PLN","PM":"EUR","PR":"USD","PS":"ILS","PT":"EUR","PW":"USD",
        "PY":"PYG","QA":"QAR","RE":"EUR","RO":"RON","RS":"RSD","RU":"RUB",
        "RW":"RWF","SA":"SAR","SB":"SBD","SC":"SCR","SD":"SDG","SE":"SEK",
        "SG":"SGD","SI":"EUR","SK":"EUR","SL":"SLE","SM":"EUR","SN":"XOF",
        "SO":"SOS","SR":"SRD","SS":"SSP","ST":"STN","SV":"USD","SX":"ANG",
        "SY":"SYP","SZ":"SZL","TC":"USD","TD":"XAF","TG":"XOF","TH":"THB",
        "TJ":"TJS","TL":"USD","TM":"TMT","TN":"TND","TO":"TOP","TR":"TRY",
        "TT":"TTD","TV":"AUD","TW":"TWD","TZ":"TZS","UA":"UAH","UG":"UGX",
        "US":"USD","UY":"UYU","UZ":"UZS","VA":"EUR","VC":"XCD","VE":"VES",
        "VG":"USD","VI":"USD","VN":"VND","VU":"VUV","WF":"XPF","WS":"WST",
        "XK":"EUR","YE":"YER","YT":"EUR","ZA":"ZAR","ZM":"ZMW","ZW":"ZWL"
    };

    function initCountryCurrencySelect() {
        var countryEl  = document.getElementById('id_country');
        var currencyEl = document.getElementById('id_currency');

        if (!countryEl || !currencyEl) {
            return;
        }

        countryEl.addEventListener('change', function () {
            var iso = COUNTRY_CURRENCY[this.value];
            if (!iso) {
                return;
            }
            for (var i = 0; i < currencyEl.options.length; i++) {
                if (currencyEl.options[i].value === iso) {
                    currencyEl.selectedIndex = i;
                    break;
                }
            }
        });
    }

    function initTooltips() {
        var els = document.querySelectorAll('[data-toggle="tooltip"]');
        for (var i = 0; i < els.length; i++) {
            (function (el) {
                el.addEventListener('mouseenter', function () {
                    var tip = document.createElement('div');
                    tip.className = 'tooltip-custom';
                    tip.style.cssText = [
                        'position:absolute',
                        'background:#333',
                        'color:#fff',
                        'padding:4px 8px',
                        'border-radius:4px',
                        'font-size:12px',
                        'max-width:220px',
                        'z-index:9999',
                        'pointer-events:none',
                    ].join(';');
                    tip.textContent = el.getAttribute('title') || el.getAttribute('data-original-title') || '';
                    if (!tip.textContent) {
                        return;
                    }
                    el.setAttribute('data-original-title', tip.textContent);
                    el.removeAttribute('title');
                    document.body.appendChild(tip);
                    var rect = el.getBoundingClientRect();
                    tip.style.top  = (window.scrollY + rect.top - tip.offsetHeight - 6) + 'px';
                    tip.style.left = (window.scrollX + rect.left + rect.width / 2 - tip.offsetWidth / 2) + 'px';
                    el._tooltip = tip;
                });
                el.addEventListener('mouseleave', function () {
                    if (el._tooltip) {
                        el._tooltip.remove();
                        el._tooltip = null;
                    }
                });
            }(els[i]));
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        initCountryCurrencySelect();
        initTooltips();
    });
}());
