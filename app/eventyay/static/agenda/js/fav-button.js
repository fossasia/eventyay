/**
 * <pretalx-fav-button> custom element — session favourite toggle.
 *
 * Discovers event slug and API base URL from the page URL.
 * Syncs fav state via Django REST API (POST/DELETE) with CSRF token.
 * Falls back to localStorage for anonymous users.
 * Uses replaceChildren() to safely render SVG nodes and prevent XSS injection.
 *
 * @attr {string} submission-id — the submission code
 * @attr {string} logged-in — "true" or "false"
 */
class PretalxFavButton extends HTMLElement {
  connectedCallback () {
    if (!this._button) {
      if (!document.getElementById('fav-button-styles')) {
        const style = document.createElement('style')
        style.id = 'fav-button-styles'
        style.textContent = '@keyframes fav-spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } } .fav-icon { display: inline-flex; vertical-align: middle; }'
        document.head.appendChild(style)
      }

      const starOutline = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.56 5.82 22 7 14.14l-5-4.87 6.91-1.01L12 2zm0 3.34L9.86 9.88l-4.58.67 3.32 3.24-.78 4.58L12 16.1l4.18 2.27-.78-4.58 3.32-3.24-4.58-.67L12 5.34z"/></svg>'
      const starFilled = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.56 5.82 22 7 14.14l-5-4.87 6.91-1.01L12 2z"/></svg>'

      const btn = document.createElement('button')
      btn.className = 'btn btn-xs btn-link'
      const span = document.createElement('span')
      span.className = 'fav-icon'
      const parser = new DOMParser()

      this._button = btn
      this._iconWrap = span
      this._button.appendChild(this._iconWrap)
      this.appendChild(this._button)
      this._button.addEventListener('click', () => this._toggle())
      this._starFilledNode = parser.parseFromString(starFilled, 'image/svg+xml').documentElement
      this._starOutlineNode = parser.parseFromString(starOutline, 'image/svg+xml').documentElement
    }

    this._syncContextFromPage()
    this._render()
    this._loadState()
  }

  _syncContextFromPage () {
    const parts = window.location.pathname.split('/')
    this._eventSlug = parts[2]
    this._submissionId = this.getAttribute('submission-id') || parts[4]
    this._loggedIn = this.getAttribute('logged-in') === 'true'
    this._apiBase = new URL(
      `/api/v1/events/${this._eventSlug}/`,
      window.location
    ).href
    this._csrfToken = document.cookie
      .split('eventyay_csrftoken=')
      .pop()
      .split(';')
      .shift()
    if (typeof this._isFaved !== 'boolean') this._isFaved = false
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
    const svgElement = this._isFaved ? this._starFilledNode : this._starOutlineNode
    this._iconWrap.replaceChildren(svgElement.cloneNode(true))
  }

  _spin () {
    this._iconWrap.style.animation = 'fav-spin 0.4s linear'
    setTimeout(() => { this._iconWrap.style.animation = '' }, 400)
  }

  /**
   * @throws {Error} when the network request fails or returns a non-OK status
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
    if (!response.ok) {
      throw new Error(`API ${method} ${path} failed: ${response.status}`)
    }
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
