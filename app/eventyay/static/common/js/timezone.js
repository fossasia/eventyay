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
            const field = document.getElementById(fieldId);
            if (field) {
                field.value = this.detect();
            }
        },
        
        autoSet: function() {
            const tz = this.detect();
            const fields = document.querySelectorAll('.browser-timezone-field');
            fields.forEach(function(field) {
                field.value = tz;
            });
        },
        
        showIndicator: function(indicatorId) {
            const tz = this.detect();
            const indicator = document.getElementById(indicatorId || 'tz-indicator');
            if (indicator) {
                indicator.textContent = '(' + tz + ')';
            }
        },
        
        showInlineIndicators: function(selector) {
            const tz = this.detect();
            const indicators = document.querySelectorAll(selector || '.tz-indicator-inline');
            indicators.forEach(function(ind) {
                ind.textContent = '(' + tz + ')';
            });
        },
        
        convertDateTimes: function(selector) {
            const cells = document.querySelectorAll(selector || '.order-datetime');
            cells.forEach(function(cell) {
                const isoDate = cell.getAttribute('data-datetime');
                if (isoDate) {
                    try {
                        const date = new Date(isoDate);
                        const formatted = date.toLocaleString(undefined, {
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

