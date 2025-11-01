/**
 * Browser timezone detection and datetime conversion utility
 */
(function(window) {
    'use strict';
    
    window.EventyayTimezone = {
        detect: function() {
            try {
                return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
            } catch(e) {
                return 'UTC';
            }
        },
        
        setField: function(fieldId) {
            var field = document.getElementById(fieldId);
            if (field) {
                field.value = this.detect();
            }
        },
        
        autoSet: function() {
            var tz = this.detect();
            var fields = document.querySelectorAll('.browser-timezone-field');
            fields.forEach(function(field) {
                field.value = tz;
            });
        },
        
        showIndicator: function(indicatorId) {
            var tz = this.detect();
            var indicator = document.getElementById(indicatorId || 'tz-indicator');
            if (indicator) {
                indicator.textContent = '(' + tz + ')';
            }
        },
        
        showInlineIndicators: function(selector) {
            var tz = this.detect();
            var indicators = document.querySelectorAll(selector || '.tz-indicator-inline');
            indicators.forEach(function(ind) {
                ind.textContent = '(' + tz + ')';
            });
        },
        
        convertDateTimes: function(selector) {
            var cells = document.querySelectorAll(selector || '.order-datetime');
            cells.forEach(function(cell) {
                var isoDate = cell.getAttribute('data-datetime');
                if (isoDate) {
                    try {
                        var date = new Date(isoDate);
                        var formatted = date.toLocaleString(undefined, {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false
                        });
                        cell.textContent = formatted;
                    } catch(e) {}
                }
            });
        },
        
        initOrderDateTimes: function() {
            this.showIndicator();
            this.showInlineIndicators();
            this.convertDateTimes();
        }
    };
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            window.EventyayTimezone.autoSet();
            window.EventyayTimezone.initOrderDateTimes();
        });
    } else {
        window.EventyayTimezone.autoSet();
        window.EventyayTimezone.initOrderDateTimes();
    }
})(window);

