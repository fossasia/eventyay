document.addEventListener('DOMContentLoaded', function () {
  var table = document.querySelector('[data-global-plugins-table]')
  if (!table) return

  var rows = table.querySelectorAll('[data-plugin-row]')

  function syncRow(row) {
    var active = row.querySelector('[data-col="active"]')
    var deps = row.querySelectorAll('[data-col="enable_by_default"], [data-col="show_in_organizer_list"]')
    deps.forEach(function (dep) {
      dep.disabled = !active.checked
      if (!active.checked) dep.checked = false
    })
  }

  rows.forEach(function (row) {
    syncRow(row)
    var active = row.querySelector('[data-col="active"]')
    active.addEventListener('change', function () { syncRow(row) })
  })
})
