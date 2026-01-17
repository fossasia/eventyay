import { createApp } from 'vue'
import Root from './components/Root.vue'

function gettext(msgid) {
  if (typeof django !== 'undefined' && typeof django.gettext !== 'undefined') {
    return django.gettext(msgid)
  }
  return msgid
}

function buildStrings() {
  return {
    'checkinlist.select': gettext('Select a check-in list'),
    'checkinlist.none': gettext('No active check-in lists found.'),
    'checkinlist.switch': gettext('Switch check-in list'),
    'results.headline': gettext('Search results'),
    'results.none': gettext('No tickets found'),
    'check.headline': gettext('Check-in result'),
    'check.attention': gettext('This ticket requires special attention'),
    'scantype.switch': gettext('Switch direction'),
    'scantype.entry': gettext('Entry'),
    'scantype.exit': gettext('Exit'),
    'input.placeholder': gettext('Scan a ticket or search and press return…'),
    'pagination.next': gettext('Load more'),
    'status.p': gettext('Valid'),
    'status.n': gettext('Unpaid'),
    'status.c': gettext('Canceled'),
    'status.e': gettext('Canceled'),
    'status.redeemed': gettext('Redeemed'),
    'modal.cancel': gettext('Cancel'),
    'modal.continue': gettext('Continue'),
    'modal.unpaid.head': gettext('Ticket not paid'),
    'modal.unpaid.text': gettext(
      'This ticket is not yet paid. Do you want to continue anyways?'
    ),
    'modal.questions': gettext('Additional information required'),
    'result.ok': gettext('Valid ticket'),
    'result.exit': gettext('Exit recorded'),
    'result.already_redeemed': gettext('Ticket already used'),
    'result.questions': gettext('Information required'),
    'result.invalid': gettext('Invalid ticket'),
    'result.product': gettext('Invalid product'),
    'result.unpaid': gettext('Ticket not paid'),
    'result.rules': gettext('Entry not allowed'),
    'result.revoked': gettext('Ticket code revoked/changed'),
    'result.canceled': gettext('Order canceled'),
    'status.checkin': gettext('Checked-in Tickets'),
    'status.position': gettext('Valid Tickets'),
    'status.inside': gettext('Currently inside'),
  }
}

class WebCheckinAppElement extends HTMLElement {
  connectedCallback() {
    if (this.__vue_app__) return

    if (typeof moment !== 'undefined') {
      const locale = document.body?.getAttribute('data-datetimelocale')
      if (locale) {
        moment.locale(locale)
      }
    }

    const apiLists = this.getAttribute('data-api-lists') || ''
    const eventName = this.getAttribute('data-event-name') || ''

    const timezone = document.body?.getAttribute('data-timezone') || ''
    const datetimeFormat = document.body?.getAttribute('data-datetimeformat') || ''

    const rootData = {
      api: { lists: apiLists },
      strings: buildStrings(),
      event_name: eventName,
      timezone,
      datetime_format: datetimeFormat,
    }

    const app = createApp(Root, { rootData })

    this.__vue_app__ = app
    const vm = app.mount(this)

    // Keep compatibility with the old integration.
    window.vapp = vm
  }

  disconnectedCallback() {
    if (!this.__vue_app__) return
    this.__vue_app__.unmount()
    this.__vue_app__ = null
  }
}

if (!customElements.get('webcheckin-app')) {
  customElements.define('webcheckin-app', WebCheckinAppElement)
}
