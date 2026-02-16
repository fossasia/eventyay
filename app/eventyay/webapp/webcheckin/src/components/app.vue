<template>
  <div>
    <div class="container">
      <h1>
        {{ $root.event_name }}
      </h1>

      <checkinlist-select
        v-if="!checkinlist"
        @selected="selectList($event)"
      ></checkinlist-select>

      <div class="autocomplete-wrapper" v-if="checkinlist">
        <input
          v-model="query"
          ref="input"
          :placeholder="$root.strings['input.placeholder']"
          @keyup="inputKeyup"
          @input="onInputChange"
          @keydown="onInputKeydown"
          @blur="onInputBlur"
          @focus="onInputFocus"
          class="form-control scan-input"
          autocomplete="off"
        />
        <ul v-if="showSuggestions && suggestions.length" class="autocomplete-dropdown">
          <li
            v-for="(s, idx) in suggestions"
            :key="s.id"
            :class="{ active: idx === selectedSuggestionIndex }"
            @mousedown.prevent="selectSuggestion(s)"
          >
            <div class="suggestion-main">
              <strong>{{ s.order }}-{{ s.positionid }}</strong>
              <span v-if="s.attendee_name"> {{ s.attendee_name }}</span>
            </div>
            <div class="suggestion-detail">
              {{ getSuggestionProduct(s) }}
              <span class="suggestion-secret">{{ s.secret.substring(0, 8) }}…</span>
            </div>
          </li>
          <li v-if="suggestionsLoading" class="loading">
            <span class="fa fa-cog fa-spin"></span>
          </li>
        </ul>
      </div>

      <div v-if="checkResult !== null" class="panel panel-primary check-result">
        <div class="panel-heading">
          <a class="pull-right" @click.prevent="clear" href="#" tabindex="-1">
            <span class="fa fa-close"></span>
          </a>
          <h3 class="panel-title">
            {{ $root.strings['check.headline'] }}
          </h3>
        </div>
        <div v-if="checkLoading" class="panel-body text-center">
          <span class="fa fa-4x fa-cog fa-spin loading-icon"></span>
        </div>
        <div v-else-if="checkError" class="panel-body text-center">
          {{ checkError }}
        </div>
        <div :class="'check-result-status check-result-' + checkResultColor">
          {{ checkResultText }}
        </div>
        <div v-if="checkResult && checkResult.reason_explanation" class="panel-body reason-explanation">
          {{ checkResult.reason_explanation }}
        </div>
        <div class="panel-body" v-if="checkResult.position">
          <div class="details">
            <h4>
              {{ checkResult.position.order }}-{{ checkResult.position.positionid }}
              {{ checkResult.position.attendee_name }}
            </h4>
            <span>{{ checkResultItemvar }}</span>
            <span v-if="checkResult.position.seat"><br />{{ checkResult.position.seat.name }}</span>
          </div>
        </div>
        <div class="attention" v-if="checkResult && checkResult.require_attention">
          <span class="fa fa-warning"></span>
          {{ $root.strings['check.attention'] }}
        </div>
      </div>

      <div v-else-if="searchResults !== null" class="panel panel-primary search-results">
        <div class="panel-heading">
          <a class="pull-right" @click.prevent="clear" href="#" tabindex="-1">
            <span class="fa fa-close"></span>
          </a>
          <h3 class="panel-title">
            {{ $root.strings['results.headline'] }}
          </h3>
        </div>
        <ul class="list-group">
          <searchresult-item
            ref="result"
            v-if="searchResults"
            v-for="p in searchResults"
            :position="p"
            :key="p.id"
            @selected="selectResult($event)"
          ></searchresult-item>
          <li v-if="!searchResults.length && !searchLoading" class="list-group-item text-center">
            {{ $root.strings['results.none'] }}
          </li>
          <li v-if="searchLoading" class="list-group-item text-center">
            <span class="fa fa-4x fa-cog fa-spin loading-icon"></span>
          </li>
          <li v-else-if="searchError" class="list-group-item text-center">
            {{ searchError }}
          </li>
          <a v-else-if="searchNextUrl" class="list-group-item text-center" href="#" @click.prevent="searchNext">
            {{ $root.strings['pagination.next'] }}
          </a>
        </ul>
      </div>

      <div v-else-if="checkinlist">
        <div class="panel panel-default">
          <div class="panel-body meta">
            <div class="row settings">
              <div class="col-sm-6">
                <div>
                  <span :class="'fa fa-sign-' + (type === 'exit' ? 'out' : 'in')"></span>
                  {{ $root.strings['scantype.' + type] }}<br />
                  <button @click="switchType" class="btn btn-default">
                    <span class="fa fa-refresh"></span>
                    {{ $root.strings['scantype.switch'] }}
                  </button>
                </div>
              </div>
              <div class="col-sm-6">
                <div v-if="checkinlist">
                  {{ checkinlist.name }}<br />
                  {{ subevent }}<br v-if="subevent" />
                  <button @click="switchList" type="button" class="btn btn-default">
                    {{ $root.strings['checkinlist.switch'] }}
                  </button>
                </div>
              </div>
            </div>
            <div v-if="status" class="row status">
              <div class="col-sm-4">
                <span class="statistic">{{ status.checkin_count }}</span>
                {{ $root.strings['status.checkin'] }}
              </div>
              <div class="col-sm-4">
                <span class="statistic">{{ status.position_count }}</span>
                {{ $root.strings['status.position'] }}
              </div>
              <div class="col-sm-4">
                <div class="pull-right">
                  <button @click="fetchStatus" class="btn btn-default">
                    <span :class="'fa fa-refresh' + (statusLoading ? ' fa-spin' : '')"></span>
                  </button>
                </div>
                <span class="statistic">{{ status.inside_count }}</span>
                {{ $root.strings['status.inside'] }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div :class="'modal modal-unpaid fade' + (showUnpaidModal ? ' in' : '')" tabindex="-1" role="dialog">
      <div class="modal-dialog" role="document">
        <div class="modal-content" v-if="checkResult && checkResult.position">
          <div class="modal-header">
            <button type="button" class="close" @click="showUnpaidModal = false">
              <span class="fa fa-close"></span>
            </button>
            <h4 class="modal-title">
              {{ $root.strings['modal.unpaid.head'] }}
            </h4>
          </div>
          <div class="modal-body">
            <p>
              {{ $root.strings['modal.unpaid.text'] }}
            </p>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-primary pull-right"
              @click="check(checkResult.position.secret, true, false, false)"
            >
              {{ $root.strings['modal.continue'] }}
            </button>
            <button type="button" class="btn btn-default" @click="showUnpaidModal = false">
              {{ $root.strings['modal.cancel'] }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <form
      :class="'modal modal-questions fade' + (showQuestionsModal ? ' in' : '')"
      tabindex="-1"
      role="dialog"
      ref="questionsModal"
    >
      <div class="modal-dialog" role="document">
        <div class="modal-content" v-if="checkResult && checkResult.questions">
          <div class="modal-header">
            <button type="button" class="close" @click="showQuestionsModal = false">
              <span class="fa fa-close"></span>
            </button>
            <h4 class="modal-title">
              {{ $root.strings['modal.questions'] }}
            </h4>
          </div>
          <div class="modal-body">
            <div
              :class="q.type === 'M' ? '' : q.type === 'B' ? 'checkbox' : 'form-group'"
              v-for="q in checkResult.questions"
              :key="q.id"
            >
              <label :for="'q_' + q.id" v-if="q.type !== 'B'">
                {{ q.question }}
                {{ q.required ? ' *' : '' }}
              </label>

              <textarea
                v-if="q.type === 'T'"
                v-model="answers[q.id.toString()]"
                :id="'q_' + q.id"
                class="form-control"
                :required="q.required"
              ></textarea>
              <input
                v-else-if="q.type === 'N'"
                type="number"
                v-model="answers[q.id.toString()]"
                :id="'q_' + q.id"
                class="form-control"
                :required="q.required"
              />
              <input
                v-else-if="q.type === 'D'"
                type="date"
                v-model="answers[q.id.toString()]"
                :id="'q_' + q.id"
                class="form-control"
                :required="q.required"
              />
              <input
                v-else-if="q.type === 'H'"
                type="time"
                step="1"
                v-model="answers[q.id.toString()]"
                :id="'q_' + q.id"
                class="form-control"
                :required="q.required"
              />
              <input
                v-else-if="q.type === 'W'"
                type="datetime-local"
                v-model="answers[q.id.toString()]"
                :id="'q_' + q.id"
                class="form-control"
                :required="q.required"
              />
              <select
                v-else-if="q.type === 'C'"
                v-model="answers[q.id.toString()]"
                :id="'q_' + q.id"
                class="form-control"
                :required="q.required"
              >
                <option v-if="!q.required"></option>
                <option v-for="op in q.options" :key="op.id" :value="op.id.toString()">{{ op.answer }}</option>
              </select>
              <div v-else-if="q.type === 'F'"><em>file input not supported</em></div>
              <div v-else-if="q.type === 'M'">
                <div class="checkbox" v-for="op in q.options" :key="op.id">
                  <label>
                    <input
                      type="checkbox"
                      :checked="answers[q.id.toString()] && answers[q.id.toString()].split(',').includes(op.id.toString())"
                      @input="answerSetM(q.id.toString(), op.id.toString(), $event.target.checked)"
                    />
                    {{ op.answer }}
                  </label>
                </div>
              </div>
              <label v-else-if="q.type === 'B'">
                <input
                  type="checkbox"
                  :checked="answers[q.id.toString()] === 'true'"
                  @input="answers[q.id.toString()] = $event.target.checked.toString()"
                  :required="q.required"
                />
                {{ q.question }}
                {{ q.required ? ' *' : '' }}
              </label>
              <select
                v-else-if="q.type === 'CC'"
                v-model="answers[q.id.toString()]"
                :id="'q_' + q.id"
                class="form-control"
                :required="q.required"
              >
                <option v-if="!q.required"></option>
                <option v-for="op in countries" :key="op.key" :value="op.key">{{ op.value }}</option>
              </select>
              <input
                v-else
                v-model="answers[q.id.toString()]"
                :id="'q_' + q.id"
                class="form-control"
                :required="q.required"
              />
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-primary pull-right" @click="check(checkResult.position.secret, true, true)">
              {{ $root.strings['modal.continue'] }}
            </button>
            <button type="button" class="btn btn-default" @click="showQuestionsModal = false">
              {{ $root.strings['modal.cancel'] }}
            </button>
          </div>
        </div>
      </div>
    </form>
  </div>
</template>

<script>
import CheckinlistSelect from './checkinlist-select.vue'
import SearchresultItem from './searchresult-item.vue'

export default {
  components: {
    CheckinlistSelect,
    SearchresultItem,
  },
  data() {
    return {
      type: 'entry',
      query: '',
      searchLoading: false,
      searchResults: null,
      searchNextUrl: null,
      searchError: null,
      status: null,
      statusLoading: 0,
      statusInterval: null,
      checkLoading: false,
      checkError: null,
      checkResult: null,
      checkinlist: null,
      clearTimeout: null,
      showUnpaidModal: false,
      showQuestionsModal: false,
      answers: {},
      // Autocomplete state
      suggestions: [],
      suggestionsLoading: false,
      showSuggestions: false,
      selectedSuggestionIndex: -1,
      debounceTimer: null,
    }
  },
  mounted() {
    window.addEventListener('focus', this.globalKeydown)
    document.addEventListener('visibilitychange', this.globalKeydown)
    document.addEventListener('keydown', this.globalKeydown)
    this.statusInterval = window.setInterval(this.fetchStatus, 120 * 1000)
  },
  unmounted() {
    window.removeEventListener('focus', this.globalKeydown)
    document.removeEventListener('visibilitychange', this.globalKeydown)
    document.removeEventListener('keydown', this.globalKeydown)
    window.clearInterval(this.statusInterval)
    window.clearInterval(this.clearTimeout)
    if (this.debounceTimer) clearTimeout(this.debounceTimer)
  },
  computed: {
    countries() {
      return JSON.parse(document.querySelector('#countries').innerHTML)
    },
    subevent() {
      if (!this.checkinlist) return ''
      if (!this.checkinlist.subevent) return ''
      const name = i18nstring_localize(this.checkinlist.subevent.name)
      const date = moment
        .utc(this.checkinlist.subevent.date_from)
        .tz(this.$root.timezone)
        .format(this.$root.datetime_format)
      return `${name} · ${date}`
    },
    checkResultItemvar() {
      if (!this.checkResult) return ''
      if (this.checkResult.position.variation) {
        return `${i18nstring_localize(this.checkResult.position.product.name)} – ${i18nstring_localize(this.checkResult.position.variation.value)}`
      }
      return i18nstring_localize(this.checkResult.position.product.name)
    },
    checkResultText() {
      if (!this.checkResult) return ''
      if (this.checkResult.status === 'ok') return this.$root.strings['result.ok']
      if (this.checkResult.status === 'incomplete') return this.$root.strings['result.questions']
      return this.$root.strings['result.' + this.checkResult.reason]
    },
    checkResultColor() {
      if (!this.checkResult) return ''
      if (this.checkResult.status === 'ok') return 'green'
      if (this.checkResult.status === 'incomplete') return 'purple'
      if (this.checkResult.reason === 'already_redeemed') return 'orange'
      return 'red'
    },
  },
  methods: {
    selectResult(position) {
      this.check(position.secret, false, false, false)
    },
    answerSetM(qid, oid, checked) {
      let v = this.answers[qid] ? this.answers[qid].split(',') : []
      if (checked && !v.includes(oid)) {
        v.push(oid)
      } else if (!checked) {
        v = v.filter((x) => x !== oid)
      }
      this.answers[qid] = v.join(',')
    },
    clear() {
      this.query = ''
      this.searchLoading = false
      this.searchResults = null
      this.searchNextUrl = null
      this.searchError = null
      this.checkLoading = false
      this.checkError = null
      this.checkResult = null
      this.showUnpaidModal = false
      this.showQuestionsModal = false
      this.answers = {}
    },
    check(code, ignore_unpaid, submit_questions, from_enter, allow_search = true) {
      if (!submit_questions) {
        this.answers = {}
      } else if (this.showQuestionsModal && !this.$refs.questionsModal.reportValidity()) {
        return
      }
      this.showUnpaidModal = false
      this.showQuestionsModal = false
      this.checkLoading = true
      this.checkError = null
      const existingQuestions = this.checkResult && this.checkResult.questions ? this.checkResult.questions : null
      this.checkResult = {}
      window.clearInterval(this.clearTimeout)

      const normalizedAnswers = { ...this.answers }
      if (existingQuestions) {
        const typeById = new Map(existingQuestions.map((q) => [q.id.toString(), q.type]))
        for (const [qid, val] of Object.entries(normalizedAnswers)) {
          if (!val) continue
          const qtype = typeById.get(qid)

          // Time: previously HH:mm:ss
          if (qtype === 'H' && /^\d{2}:\d{2}$/.test(val)) {
            normalizedAnswers[qid] = `${val}:00`
          }

          // Datetime: previously ISO string (moment().toISOString())
          // Native datetime-local usually yields YYYY-MM-DDTHH:mm, but can include seconds.
          if (qtype === 'W' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(val)) {
            if (typeof moment !== 'undefined') {
              try {
                const tz = this.$root?.timezone
                const fmt = val.length === 16 ? 'YYYY-MM-DDTHH:mm' : 'YYYY-MM-DDTHH:mm:ss'
                normalizedAnswers[qid] =
                  tz && moment.tz
                    ? moment.tz(val, fmt, tz).toISOString()
                    : moment(val, fmt).toISOString()
              } catch {
                // keep original value if parsing fails
              }
            }
          }
        }
      }

      fetch(
        this.$root.api.lists +
          this.checkinlist.id +
          '/positions/' +
          encodeURIComponent(code) +
          '/redeem/?expand=product&expand=variation',
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': document.querySelector('input[name=csrfmiddlewaretoken]').value,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            questions_supported: true,
            canceled_supported: true,
            ignore_unpaid: ignore_unpaid || false,
            type: this.type,
            answers: normalizedAnswers,
          }),
        }
      )
        .then((response) => {
          if (response.status === 404) return { status: 'error', reason: 'invalid' }
          if (!response.ok && response.status !== 400) throw new Error('HTTP status ' + response.status)
          return response.json()
        })
        .then((data) => {
          this.checkLoading = false
          this.checkResult = data
          if (this.checkinlist.include_pending && data.status === 'error' && data.reason === 'unpaid') {
            this.showUnpaidModal = true
            this.$nextTick(() => {
              document.querySelector('.modal-unpaid .btn-primary').focus()
            })
          } else if (data.status === 'incomplete') {
            this.showQuestionsModal = true
            for (const q of this.checkResult.questions) {
              if (!this.answers[q.id.toString()]) this.answers[q.id.toString()] = ''
              q.question = i18nstring_localize(q.question)
              for (const op of q.options) {
                op.answer = i18nstring_localize(op.answer)
              }
            }
            this.$nextTick(() => {
              document
                .querySelector('.modal-questions input, .modal-questions select, .modal-questions textarea')
                .focus()
            })
          } else if (data.status === 'error' && data.reason === 'invalid' && from_enter && allow_search) {
            this.startSearch(false)
          } else {
            this.clearTimeout = window.setTimeout(this.clear, 20 * 1000)
            this.fetchStatus()
          }
        })
        .catch((reason) => {
          this.checkLoading = false
          this.checkResult = {}
          this.checkError = reason.toString()
          this.clearTimeout = window.setTimeout(this.clear, 20 * 1000)
        })
    },
    globalKeydown(e) {
      if (
        document.activeElement.classList.contains('searchresult') &&
        (e.key === 'ArrowDown' || e.key === 'ArrowUp')
      ) {
        if (e.key === 'ArrowDown') {
          document.activeElement.nextElementSibling.focus()
          e.preventDefault()
          return true
        }
        if (e.key === 'ArrowUp') {
          document.activeElement.previousElementSibling.focus()
          e.preventDefault()
          return true
        }
      }

      const nodeName = document.activeElement.nodeName.toLowerCase()
      if (nodeName !== 'input' && nodeName !== 'textarea') {
        if (e.key && e.key.match(/^[a-z0-9A-Z+/=<>#]$/)) {
          this.query = ''
          this.refocus()
        }
      }
    },
    refocus() {
      this.$nextTick(() => {
        this.$refs.input.focus()
      })
    },
    inputKeyup(e) {
      if (e.key === 'Enter') {
        // If a suggestion is selected, use it
        if (this.showSuggestions && this.selectedSuggestionIndex >= 0 && this.suggestions[this.selectedSuggestionIndex]) {
          this.selectSuggestion(this.suggestions[this.selectedSuggestionIndex])
          return
        }
        this.hideSuggestions()
        this.startSearch(true)
      } else if (this.query === '') {
        this.clear()
      }
    },
    onInputChange() {
      // Debounced autocomplete search
      if (this.debounceTimer) clearTimeout(this.debounceTimer)
      
      if (this.query.length < 2) {
        this.hideSuggestions()
        return
      }
      
      this.debounceTimer = setTimeout(() => {
        this.fetchSuggestions()
      }, 250)
    },
    onInputKeydown(e) {
      if (!this.showSuggestions || !this.suggestions.length) return
      
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        this.selectedSuggestionIndex = Math.min(this.selectedSuggestionIndex + 1, this.suggestions.length - 1)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        this.selectedSuggestionIndex = Math.max(this.selectedSuggestionIndex - 1, -1)
      } else if (e.key === 'Escape') {
        this.hideSuggestions()
      }
    },
    onInputBlur() {
      // Delay hiding to allow click on suggestion
      setTimeout(() => {
        this.hideSuggestions()
      }, 150)
    },
    onInputFocus() {
      if (this.query.length >= 2 && this.suggestions.length) {
        this.showSuggestions = true
      }
    },
    hideSuggestions() {
      this.showSuggestions = false
      this.selectedSuggestionIndex = -1
    },
    fetchSuggestions() {
      if (!this.checkinlist || this.query.length < 2) return
      
      this.suggestionsLoading = true
      this.showSuggestions = true
      
      fetch(
        this.$root.api.lists +
          this.checkinlist.id +
          '/positions/?ignore_status=true&expand=product&expand=variation&search=' +
          encodeURIComponent(this.query) +
          '&page_size=8',
        {
          credentials: 'same-origin',
        }
      )
        .then((response) => response.json())
        .then((data) => {
          this.suggestionsLoading = false
          if (data.results) {
            this.suggestions = data.results
            this.selectedSuggestionIndex = -1
          }
        })
        .catch(() => {
          this.suggestionsLoading = false
          this.suggestions = []
        })
    },
    selectSuggestion(suggestion) {
      this.hideSuggestions()
      this.query = suggestion.secret
      this.check(suggestion.secret, false, false, false, false)
    },
    getSuggestionProduct(s) {
      if (s.variation) {
        return `${i18nstring_localize(s.product.name)} – ${i18nstring_localize(s.variation.value)}`
      }
      return i18nstring_localize(s.product.name)
    },
    startSearch(from_enter) {
      if (this.query.length >= 32 && from_enter) {
        this.check(this.query, false, false, true, true)
        return
      }
      this.checkResult = null
      this.searchLoading = true
      this.searchError = null
      this.searchResults = []
      this.answers = {}
      window.clearInterval(this.clearTimeout)

      fetch(
        this.$root.api.lists +
          this.checkinlist.id +
          '/positions/?ignore_status=true&expand=subevent&expand=product&expand=variation&check_rules=true&search=' +
          encodeURIComponent(this.query),
        {
          credentials: 'same-origin',
        }
      )
        .then((response) => response.json())
        .then((data) => {
          this.searchLoading = false
          if (data.results) {
            this.searchResults = data.results
            this.searchNextUrl = data.next
            if (data.results.length) {
              if (data.results[0].secret === this.query) {
                this.$nextTick(() => {
                  this.$refs.result[0].$refs.a.click()
                })
              } else {
                this.$nextTick(() => {
                  this.$refs.result[0].$refs.a.focus()
                })
              }
            } else {
              this.$nextTick(() => {
                this.$refs.input.blur()
              })
            }
          } else {
            this.searchError = data
          }
          this.clearTimeout = window.setTimeout(this.clear, 20 * 1000)
        })
        .catch((reason) => {
          this.searchLoading = false
          this.searchResults = []
          this.searchError = reason
          this.clearTimeout = window.setTimeout(this.clear, 20 * 1000)
        })
    },
    searchNext() {
      this.searchLoading = true
      this.searchError = null
      window.clearInterval(this.clearTimeout)
      fetch(this.searchNextUrl, {
        credentials: 'same-origin',
      })
        .then((response) => response.json())
        .then((data) => {
          this.searchLoading = false
          if (data.results) {
            this.searchResults.push(...data.results)
            this.searchNextUrl = data.next
          } else {
            this.searchError = data
          }
          this.clearTimeout = window.setTimeout(this.clear, 20 * 1000)
        })
        .catch((reason) => {
          this.searchLoading = false
          this.searchError = reason
          this.clearTimeout = window.setTimeout(this.clear, 20 * 1000)
        })
    },
    switchType() {
      this.type = this.type === 'exit' ? 'entry' : 'exit'
      this.refocus()
    },
    switchList() {
      location.hash = ''
      this.checkinlist = null
    },
    fetchStatus() {
      this.statusLoading++
      fetch(this.$root.api.lists + this.checkinlist.id + '/status/', {
        credentials: 'same-origin',
      })
        .then((response) => response.json())
        .then((data) => {
          this.statusLoading--
          this.status = data
        })
        .catch(() => {
          this.statusLoading--
        })
    },
    selectList(list) {
      this.checkinlist = list
      location.hash = '#' + list.id
      this.refocus()
      this.fetchStatus()
    },
  },
}
</script>
