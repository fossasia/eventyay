/**
 * <pretalx-fav-button> custom element — session favourite toggle.
 *
 * Discovers event slug, sub-system, and API base URL from the page URL.
 * Syncs fav state via Django REST API (POST/DELETE) with CSRF token.
 * Falls back to localStorage for anonymous users.
 *
 * @attr {string} submission-id — the submission code
 * @attr {string} logged-in — "true" or "false"
 */
class PretalxFavButton extends HTMLElement {
  connectedCallback () {
    const parts = window.location.pathname.split('/')
    this._subSystem = parts[1]
    this._eventSlug = parts[2]
    this._submissionId = this.getAttribute('submission-id') || parts[4]
    this._loggedIn = this.getAttribute('logged-in') === 'true'
    this._apiBase = new URL(
      `/${this._subSystem}/api/events/${this._eventSlug}/`,
      window.location
    ).href
    this._csrfToken = document.cookie
      .split('eventyay_csrftoken=')
      .pop()
      .split(';')
      .shift()
    this._isFaved = false

    this.innerHTML =
      '<button class="btn btn-xs btn-link">' +
      '<i class="fa fa-star-o"></i>' +
      '</button>'
    this._button = this.querySelector('button')
    this._icon = this.querySelector('i')
    this._button.addEventListener('click', () => this._toggle())

    this._loadState()
  }

  async _loadState () {
    try {
      if (this._loggedIn) {
        const favs = await this._apiFetch('submissions/favourites/', 'GET')
        this._isFaved = favs.includes(this._submissionId)
      } else {
        this._isFaved = this._localFavs().includes(this._submissionId)
      }
    } catch (error) {
      console.error('Failed to load favourite state: %s', error)
      this._isFaved = this._localFavs().includes(this._submissionId)
    }
    this._render()
    if (this._loggedIn) this._syncLocalFavs()
  }

  async _toggle () {
    this._isFaved = !this._isFaved
    this._syncLocalFavs()
    this._render()
    this._spin()
    if (this._loggedIn) {
      try {
        await this._apiFetch(
          `submissions/${this._submissionId}/favourite/`,
          this._isFaved ? 'POST' : 'DELETE'
        )
      } catch (error) {
        console.error('Failed to sync favourite state: %s', error)
      }
    }
  }

  _render () {
    this._icon.className = this._isFaved ? 'fa fa-star' : 'fa fa-star-o'
  }

  _spin () {
    this._icon.classList.add('fa-spin')
    setTimeout(() => this._icon.classList.remove('fa-spin'), 400)
  }

  /**
   * @throws {Error} when the network request fails
   */
  async _apiFetch (path, method) {
    const headers = { 'Content-Type': 'application/json' }
    if (method === 'POST' || method === 'DELETE') {
      headers['X-CSRFToken'] = this._csrfToken
    }
    const response = await fetch(this._apiBase + path, {
      method,
      headers,
      credentials: 'same-origin',
    })
    return response.json()
  }

  _localFavs () {
    const data = localStorage.getItem(`${this._eventSlug}_favs`)
    if (!data) return []
    try {
      return JSON.parse(data)
    } catch (error) {
      console.error('Failed to parse local favs: %s', error)
      localStorage.setItem(`${this._eventSlug}_favs`, '[]')
      return []
    }
  }

  _syncLocalFavs () {
    let favs = this._localFavs()
    if (this._isFaved && !favs.includes(this._submissionId)) {
      favs.push(this._submissionId)
    } else if (!this._isFaved) {
      favs = favs.filter(id => id !== this._submissionId)
    }
    localStorage.setItem(`${this._eventSlug}_favs`, JSON.stringify(favs))
  }
}

customElements.define('pretalx-fav-button', PretalxFavButton)
