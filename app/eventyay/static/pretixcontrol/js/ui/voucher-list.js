const voucherTableSelector = '.vouchers-table';
const groupCheckboxSelector = '[data-voucher-group-select]';
const groupToggleSelector = '[data-voucher-group-toggle]';
const memberRowSelector = '[data-voucher-group-member]';

let pointerTable = null;

function groupMemberCheckboxes(table, groupId) {
    return table.querySelectorAll(`[data-voucher-group-member="${groupId}"] input[name="voucher"]`);
}

function syncGroupCheckbox(groupCheckbox) {
    const table = groupCheckbox.closest(voucherTableSelector);
    const memberCheckboxes = groupMemberCheckboxes(table, groupCheckbox.dataset.voucherGroupSelect);
    const checkedCount = Array.from(memberCheckboxes).filter((checkbox) => checkbox.checked).length;

    groupCheckbox.checked = checkedCount === memberCheckboxes.length && checkedCount > 0;
    groupCheckbox.indeterminate = checkedCount > 0 && checkedCount < memberCheckboxes.length;
}

function syncGroupCheckboxes(table) {
    table.querySelectorAll(groupCheckboxSelector).forEach(syncGroupCheckbox);
}

function syncMemberGroupCheckbox(memberCheckbox) {
    const memberRow = memberCheckbox.closest(memberRowSelector);
    if (!memberRow) {
        return;
    }

    const table = memberCheckbox.closest(voucherTableSelector);
    const groupCheckbox = table.querySelector(
        `${groupCheckboxSelector}[data-voucher-group-select="${memberRow.dataset.voucherGroupMember}"]`
    );
    if (groupCheckbox) {
        syncGroupCheckbox(groupCheckbox);
    }
}

function setGroupSelection(groupCheckbox) {
    const table = groupCheckbox.closest(voucherTableSelector);
    const memberCheckboxes = groupMemberCheckboxes(table, groupCheckbox.dataset.voucherGroupSelect);
    const checked = groupCheckbox.checked;

    groupCheckbox.indeterminate = false;
    memberCheckboxes.forEach((memberCheckbox) => {
        if (memberCheckbox.checked !== checked) {
            memberCheckbox.checked = checked;
            memberCheckbox.dispatchEvent(new Event('change', {bubbles: true}));
        }
    });
}

function toggleGroup(toggle) {
    const table = toggle.closest(voucherTableSelector);
    const groupId = toggle.dataset.voucherGroupToggle;
    const expanded = toggle.getAttribute('aria-expanded') === 'true';
    const icon = toggle.querySelector('.fa');

    table.querySelectorAll(`[data-voucher-group-member="${groupId}"]`).forEach((memberRow) => {
        memberRow.classList.toggle('hidden', expanded);
    });
    toggle.setAttribute('aria-expanded', String(!expanded));
    icon.classList.toggle('fa-caret-right', expanded);
    icon.classList.toggle('fa-caret-down', !expanded);
}

document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) {
        return;
    }

    const toggle = event.target.closest(groupToggleSelector);
    if (toggle) {
        event.preventDefault();
        toggleGroup(toggle);
    }
});

document.addEventListener('change', (event) => {
    if (!(event.target instanceof HTMLInputElement)) {
        return;
    }

    if (event.target.matches(groupCheckboxSelector)) {
        setGroupSelection(event.target);
    } else if (event.target.matches('input[name="voucher"]')) {
        syncMemberGroupCheckbox(event.target);
    } else if (event.target.matches('[data-toggle-table]')) {
        const table = event.target.closest(voucherTableSelector);
        if (table) {
            requestAnimationFrame(() => syncGroupCheckboxes(table));
        }
    }
});

document.addEventListener('pointerdown', (event) => {
    if (event.target instanceof Element) {
        pointerTable = event.target.closest(voucherTableSelector);
    }
});

document.addEventListener('pointerup', () => {
    if (pointerTable) {
        requestAnimationFrame(() => syncGroupCheckboxes(pointerTable));
        pointerTable = null;
    }
});

document.querySelectorAll(voucherTableSelector).forEach(syncGroupCheckboxes);
