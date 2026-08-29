document.addEventListener('DOMContentLoaded', function () {
  var textarea = document.getElementById('id_internal_note');
  var counter = document.getElementById('internal-note-counter');
  if (!textarea || !counter) {
    return;
  }
  var updateCount = function () {
    counter.textContent = textarea.value.length;
  };
  updateCount();
  textarea.addEventListener('input', updateCount);
});