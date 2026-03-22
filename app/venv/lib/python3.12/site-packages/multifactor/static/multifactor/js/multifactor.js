function display_message(level, msg) {
	document.getElementById('card').classList.add(`has-background-${level}-dark`, 'has-text-white', 'has-text-centered')
	document.getElementById('content').innerHTML = msg
}
window.display_error = function(msg) { display_message('danger', msg) }
window.display_succcess = function(msg) { display_message('success', msg) }


document.body.addEventListener('click', function (ev) {
	if (ev.target.classList.contains('delete-button')) {
		let carryOn = confirm('Are you sure you want to delete this factor?')
		if (!carryOn)
			ev.preventDefault()
	}
}, false)