/**
 * Browser timezone detection and datetime conversion utilities.
 */
const detectBrowserTimezone = () => {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch (e) {
        return 'UTC';
    }
};

const setBrowserTimezoneFields = () => {
    const timezone = detectBrowserTimezone();
    document.querySelectorAll('.browser-timezone-field').forEach((field) => {
        field.value = timezone;
    });
};

const updateIndicator = () => {
    const indicator = document.getElementById('tz-indicator');
    if (!indicator) {
        return;
    }
    indicator.textContent = `(${detectBrowserTimezone()})`;
};

const updateInlineIndicators = () => {
    const timezone = detectBrowserTimezone();
    document.querySelectorAll('.tz-indicator-inline').forEach((element) => {
        element.textContent = `(${timezone})`;
    });
};

const convertDateTimes = () => {
    document.querySelectorAll('.order-datetime').forEach((cell) => {
        const isoDate = cell.getAttribute('data-datetime');
        if (!isoDate) {
            return;
        }
        try {
            const date = new Date(isoDate);
            const formatted = date.toLocaleString(undefined, {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                hour12: false,
            });
            cell.textContent = formatted;
        } catch (e) {
            console.error("timezone.js failed to convert datetime:", e);
            // Swallow parsing exceptions so server-rendered content remains intact.
        }
    });
};

const initTimezoneUtilities = () => {
    setBrowserTimezoneFields();
    updateIndicator();
    updateInlineIndicators();
    convertDateTimes();
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTimezoneUtilities);
} else {
    initTimezoneUtilities();
}

export { detectBrowserTimezone, setBrowserTimezoneFields, updateIndicator, updateInlineIndicators, convertDateTimes };
