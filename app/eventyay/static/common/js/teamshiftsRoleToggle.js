document.querySelectorAll('.teamshifts-lead-options[data-role-name]').forEach(function (optionsDiv) {
  var roleName = optionsDiv.dataset.roleName;
  var form = optionsDiv.closest('form') || optionsDiv.closest('fieldset');
  if (!form || !roleName) {
    return;
  }

  function toggleLeadOptions() {
    var checked = form.querySelector('input[name="' + roleName + '"]:checked');
    optionsDiv.hidden = !(checked && checked.value === 'lead');
  }

  form.querySelectorAll('input[name="' + roleName + '"]').forEach(function (radio) {
    radio.addEventListener('change', toggleLeadOptions);
  });

  toggleLeadOptions();
});

// Toggle roles selector visibility based on "All roles" vs "Selected roles only"
document.querySelectorAll('.teamshifts-roles-selector[data-radio-name]').forEach(function (selector) {
  var radioName = selector.dataset.radioName;
  var container = selector.closest('.teamshifts-lead-options') || selector.closest('fieldset');
  if (!container || !radioName) {
    return;
  }

  function toggle() {
    var selectedRolesOnly = container.querySelector(
      'input[name="' + radioName + '"][value="False"]:checked',
    );
    selector.hidden = !selectedRolesOnly;
  }

  container.querySelectorAll('input[name="' + radioName + '"]').forEach(function (radio) {
    radio.addEventListener('change', toggle);
  });

  toggle();
});
