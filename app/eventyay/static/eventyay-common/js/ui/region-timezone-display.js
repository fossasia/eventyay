function getTimezoneOffset(region) {
    try {
        const parts = new Intl.DateTimeFormat(undefined, {
            timeZone: region,
            timeZoneName: 'longOffset',
        }).formatToParts(new Date());
        const offset = parts.find((part) => part.type === 'timeZoneName')?.value;
        return offset?.replace('GMT', 'UTC') || region.replace(/_/g, ' ');
    } catch (error) {
        console.error('Could not determine the timezone for the selected region.', error);
        return region.replace(/_/g, ' ');
    }
}

function initializeRegionTimezoneDisplay(output) {
    const select = document.getElementById(output.dataset.regionTimezoneSource);
    if (!select) {
        return;
    }

    const updateTimezone = () => {
        output.value = getTimezoneOffset(select.value);
        output.textContent = output.value;
    };

    select.addEventListener('change', updateTimezone);
    updateTimezone();
}

document.querySelectorAll('[data-region-timezone-display]').forEach(initializeRegionTimezoneDisplay);
