const voucherTableSelector = '.vouchers-table';
const groupRowSelector = '[data-voucher-group]';
const groupCheckboxSelector = '[data-voucher-group-select]';
const groupToggleSelector = '[data-voucher-group-toggle]';
const memberRowSelector = '[data-voucher-group-member]';
const loadMoreRowSelector = '[data-voucher-group-load-more]';
const loadMoreButtonSelector = '[data-voucher-group-load-more-button]';
const groupRequests = new WeakMap();

let pointerTable = null;

function groupRow(table, groupId) {
    return table.querySelector(`${groupRowSelector}[data-voucher-group="${groupId}"]`);
}

function groupMemberCheckboxes(table, groupId) {
    return table.querySelectorAll(`[data-voucher-group-member="${groupId}"] input[name="voucher"]`);
}

function groupHasMoreMembers(table, groupId) {
    return !!table.querySelector(`${loadMoreRowSelector}[data-voucher-group-load-more="${groupId}"]`);
}

function updateBatchActions(table) {
    const form = table.closest('form');
    if (!form) {
        return;
    }

    const hasSelection = !!form.querySelector('input[name="voucher"]:checked, input[name="voucher_group"]:checked');
    form.querySelectorAll('.batch-select-actions').forEach((actions) => {
        actions.classList.toggle('hidden', !hasSelection);
    });
    form.querySelectorAll('button[name="action"][value="delete"]').forEach((button) => {
        button.classList.toggle('hidden', !hasSelection);
    });

    const toggle = table.querySelector('[data-toggle-table]');
    if (!toggle) {
        return;
    }

    const checkboxes = table.querySelectorAll('tbody input[name="voucher"], tbody input[name="voucher_group"]');
    const checkedCount = Array.from(checkboxes).filter((checkbox) => checkbox.checked).length;
    toggle.checked = checkedCount > 0 && checkedCount === checkboxes.length;
    toggle.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
}

function syncGroupCheckbox(groupCheckbox) {
    const table = groupCheckbox.closest(voucherTableSelector);
    const groupId = groupCheckbox.dataset.voucherGroupSelect;
    const memberCheckboxes = groupMemberCheckboxes(table, groupId);
    const checkedCount = Array.from(memberCheckboxes).filter((checkbox) => checkbox.checked).length;

    if (memberCheckboxes.length === 0) {
        groupCheckbox.indeterminate = false;
    } else if (groupCheckbox.checked && checkedCount === memberCheckboxes.length) {
        groupCheckbox.indeterminate = false;
    } else if (checkedCount === 0) {
        groupCheckbox.checked = false;
        groupCheckbox.indeterminate = false;
    } else if (!groupHasMoreMembers(table, groupId) && checkedCount === memberCheckboxes.length) {
        groupCheckbox.checked = true;
        groupCheckbox.indeterminate = false;
    } else {
        groupCheckbox.checked = false;
        groupCheckbox.indeterminate = true;
    }
}

function syncGroupCheckboxes(table) {
    table.querySelectorAll(groupCheckboxSelector).forEach(syncGroupCheckbox);
}

function setGroupExpanded(table, groupId, expanded) {
    const toggle = table.querySelector(`${groupToggleSelector}[data-voucher-group-toggle="${groupId}"]`);
    if (!toggle) {
        return;
    }

    table
        .querySelectorAll(
            `[data-voucher-group-member="${groupId}"], [data-voucher-group-load-more="${groupId}"]`
        )
        .forEach((row) => {
            row.classList.toggle('hidden', !expanded);
        });
    toggle.setAttribute('aria-expanded', String(expanded));
    const icon = toggle.querySelector('.fa');
    icon.classList.toggle('fa-caret-right', !expanded);
    icon.classList.toggle('fa-caret-down', expanded);
}

function applyGroupSelection(table, groupId) {
    const groupCheckbox = table.querySelector(
        `${groupCheckboxSelector}[data-voucher-group-select="${groupId}"]`
    );
    if (groupCheckbox && groupCheckbox.checked) {
        groupMemberCheckboxes(table, groupId).forEach((checkbox) => {
            checkbox.checked = true;
        });
    }

    const toggle = table.querySelector(`${groupToggleSelector}[data-voucher-group-toggle="${groupId}"]`);
    if (toggle) {
        setGroupExpanded(table, groupId, toggle.getAttribute('aria-expanded') === 'true');
    }
    if (groupCheckbox) {
        syncGroupCheckbox(groupCheckbox);
    }
    updateBatchActions(table);
}

function insertGroupMembers(table, groupId, html) {
    const existingLoadMoreRow = table.querySelector(
        `${loadMoreRowSelector}[data-voucher-group-load-more="${groupId}"]`
    );
    const memberRows = table.querySelectorAll(`[data-voucher-group-member="${groupId}"]`);
    const anchor = existingLoadMoreRow || memberRows[memberRows.length - 1] || groupRow(table, groupId);
    if (!anchor) {
        return;
    }

    anchor.insertAdjacentHTML('afterend', html);
    if (existingLoadMoreRow) {
        existingLoadMoreRow.remove();
    }
}

async function requestGroupMembers(group, url) {
    if (groupRequests.has(group)) {
        return groupRequests.get(group);
    }

    const request = (async () => {
        try {
            const response = await fetch(url, {
                credentials: 'same-origin',
                headers: {'X-Requested-With': 'XMLHttpRequest'},
            });
            if (!response.ok) {
                throw new Error(`Request failed with status ${response.status}`);
            }

            const table = group.closest(voucherTableSelector);
            if (!table) {
                return false;
            }

            const html = await response.text();
            const groupId = group.dataset.voucherGroup;
            insertGroupMembers(table, groupId, html);
            applyGroupSelection(table, groupId);
            return true;
        } catch (error) {
            console.error('Unable to load voucher group members.', error);
            return false;
        } finally {
            groupRequests.delete(group);
        }
    })();
    groupRequests.set(group, request);
    return request;
}

function loadInitialGroupMembers(group) {
    if (group.dataset.voucherGroupMembersLoaded === 'true') {
        return Promise.resolve(true);
    }

    return requestGroupMembers(group, group.dataset.voucherGroupMembersUrl).then((loaded) => {
        if (loaded) {
            group.dataset.voucherGroupMembersLoaded = 'true';
        }
        return loaded;
    });
}

async function toggleGroup(toggle) {
    const table = toggle.closest(voucherTableSelector);
    const group = toggle.closest(groupRowSelector);
    if (!table || !group) {
        return;
    }

    const expanded = toggle.getAttribute('aria-expanded') === 'true';
    if (!expanded && !(await loadInitialGroupMembers(group))) {
        return;
    }

    setGroupExpanded(table, group.dataset.voucherGroup, !expanded);
}

async function loadMoreMembers(button) {
    const table = button.closest(voucherTableSelector);
    const loadMoreRow = button.closest(loadMoreRowSelector);
    if (!table || !loadMoreRow) {
        return;
    }

    const group = groupRow(table, loadMoreRow.dataset.voucherGroupLoadMore);
    if (!group) {
        return;
    }

    button.disabled = true;
    if (!(await requestGroupMembers(group, button.dataset.voucherGroupMembersUrl))) {
        button.disabled = false;
    }
}

function setGroupSelection(groupCheckbox) {
    const table = groupCheckbox.closest(voucherTableSelector);
    const groupId = groupCheckbox.dataset.voucherGroupSelect;

    groupCheckbox.indeterminate = false;
    groupMemberCheckboxes(table, groupId).forEach((memberCheckbox) => {
        memberCheckbox.checked = groupCheckbox.checked;
    });
    updateBatchActions(table);
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
    updateBatchActions(table);
}

document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) {
        return;
    }

    const toggle = event.target.closest(groupToggleSelector);
    if (toggle) {
        event.preventDefault();
        toggleGroup(toggle);
        return;
    }

    const loadMoreButton = event.target.closest(loadMoreButtonSelector);
    if (loadMoreButton) {
        loadMoreMembers(loadMoreButton);
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
        const checked = event.target.checked;
        if (table) {
            requestAnimationFrame(() => {
                table.querySelectorAll(groupCheckboxSelector).forEach((groupCheckbox) => {
                    groupCheckbox.checked = checked;
                    setGroupSelection(groupCheckbox);
                });
                syncGroupCheckboxes(table);
                updateBatchActions(table);
            });
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
        requestAnimationFrame(() => {
            syncGroupCheckboxes(pointerTable);
            updateBatchActions(pointerTable);
        });
        pointerTable = null;
    }
});

document.querySelectorAll(voucherTableSelector).forEach((table) => {
    syncGroupCheckboxes(table);
    updateBatchActions(table);
});
