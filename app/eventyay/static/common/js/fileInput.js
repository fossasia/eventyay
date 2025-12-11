function handleFileSelect(input) {
    var name = input.name;
    var selectedInfo = document.getElementById(name + '-selected-info');
    var selectedName = document.getElementById(name + '-selected-name');
    var savedInfo = document.getElementById(name + '-saved-info');
    var existingInfo = document.getElementById(name + '-existing-info');
    var preview = document.getElementById(name + '-preview');
    var clearCheckbox = document.getElementById(name + '-clear-checkbox');
    if (input.files && input.files[0]) {
        selectedName.textContent = input.files[0].name;
        selectedInfo.style.display = 'block';
        if (savedInfo) savedInfo.style.display = 'none';
        if (existingInfo) existingInfo.style.display = 'none';
        if (preview) preview.style.display = 'none';
        if (clearCheckbox) clearCheckbox.checked = false;
    } else {
        selectedInfo.style.display = 'none';
        if (savedInfo) savedInfo.style.display = 'block';
    }
}

function clearFileInput(name) {
    var input = document.querySelector('input[name="' + name + '"]');
    input.value = '';
    document.getElementById(name + '-selected-info').style.display = 'none';
    var savedInfo = document.getElementById(name + '-saved-info');
    var existingInfo = document.getElementById(name + '-existing-info');
    var preview = document.getElementById(name + '-preview');
    if (savedInfo) savedInfo.style.display = 'block';
    if (existingInfo) existingInfo.style.display = 'block';
    if (preview) preview.style.display = 'block';
}

function clearExistingFile(name) {
    var existingInfo = document.getElementById(name + '-existing-info');
    var preview = document.getElementById(name + '-preview');
    var clearCheckbox = document.getElementById(name + '-clear-checkbox');
    if (existingInfo) existingInfo.style.display = 'none';
    if (preview) preview.style.display = 'none';
    if (clearCheckbox) clearCheckbox.checked = true;
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.form-file-selected').forEach(function(el) {
        var name = el.id.replace('-selected-info', '');
        var input = document.querySelector('input[name="' + name + '"]');
        if (input && !input.hasAttribute('onchange')) {
            input.addEventListener('change', function() { handleFileSelect(this); });
        }
    });
});
