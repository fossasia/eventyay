<template lang="pug">
.c-stream-schedule
	h2 {{ $t('Stream Schedules') }}
	.error(v-if="error") {{ error }}
	.loading(v-if="loading")
		bunt-progress-circular(size="large")
	template(v-else)
		.interpretation-plugin-language-streams(v-if="roomId && showPluginLanguageStreams")
			LanguageAudioSourceList(
				:title="$t('Interpretation source')"
				:entries="pluginLanguageStreamEntries"
			)
			p.plugin-language-streams-hint {{ $t('Room-level plugin streams used when “Use plugin language streams” is enabled on the Interpretation overview.') }}
		.stream-schedules-list(v-scrollbar.y="", v-if="streamSchedules && streamSchedules.length > 0")
			.stream-schedule-item(v-for="schedule in streamSchedules", :key="schedule.id")
				.info
					.title {{ schedule.title || $t('Untitled Stream') }}
					.url {{ schedule.url }}
					.time {{ formatDateTime(schedule.start_time) }} - {{ formatDateTime(schedule.end_time) }} ({{ eventTimezone }})
					.type {{ schedule.stream_type }}
				.actions
					bunt-icon-button(@click="editSchedule(schedule)") pencil
					bunt-icon-button(@click="deleteSchedule(schedule)") delete-outline
		.empty-state(v-else-if="streamSchedules !== null")
			p {{ $t('No stream schedules configured yet.') }}
			p {{ $t('Click "Add Stream Schedule" to create one.') }}
	bunt-button.add-btn(@click="openCreateForm") {{ $t('+ Add Stream Schedule') }}
	transition(name="prompt")
		prompt.c-stream-schedule-prompt(v-if="showCreateForm || editingSchedule", @close="closeForm", :scrollable="false")
			.content
				h1 {{ editingSchedule ? $t('Edit Stream Schedule') : $t('Create Stream Schedule') }}
				form.stream-schedule-form(@submit.prevent="saveSchedule")
					bunt-input(name="title", v-model="formData.title", :label="$t('Title (optional)')", :placeholder="$t('e.g., Day 1 Stream, Keynotes')")
					bunt-input(name="url", v-model="formData.url", :label="$t('Stream URL')", :validation="v$.formData.url", required, :placeholder="$t('https://youtube.com/watch?v=...')")
					.datetime-field
						label.datetime-label {{ $t('Start Time') }} ({{ eventTimezone }})
						input.datetime-input(type="datetime-local", v-model="plainStartTime", :class="{'has-error': v$.formData.start_time.$error}")
						.error-message(v-if="v$.formData.start_time.$error") {{ $t('Start time is required') }}
					.datetime-field
						label.datetime-label {{ $t('End Time') }} ({{ eventTimezone }})
						input.datetime-input(type="datetime-local", v-model="plainEndTime", :class="{'has-error': v$.formData.end_time.$error}")
						.error-message(v-if="v$.formData.end_time.$error") {{ $t('End time is required') }}
					.timezone-hint
						i {{ $t('All times in') }} {{ eventTimezone }}
					bunt-select(name="stream_type", v-model="formData.stream_type", :label="$t('Stream Type')", :options="streamTypeOptions", option-value="id", option-label="label", :validation="v$.formData.stream_type")
					.language-urls(v-if="formData.stream_type === 'youtube'")
						LanguageAudioSourceList(
							:title="$t('Languages and Audio Source')"
							:entries="formData.config.languageUrls"
						)
					.form-error(v-if="saveError")
						| {{ saveError }}
					.form-actions
						bunt-button.btn-save(type="submit", :loading="saving") {{ editingSchedule ? $t('Save') : $t('Create') }}
						bunt-button.btn-cancel(@click="closeForm") {{ $t('Cancel') }}
</template>
<script>
import { useVuelidate } from '@vuelidate/core';
import { helpers } from '@vuelidate/validators';
import { required, url, normalizeYoutubeVideoId } from 'lib/validators';
import api from 'lib/api';
import Prompt from 'components/Prompt';
import LanguageAudioSourceList from 'components/LanguageAudioSourceList';
import moment from 'lib/timetravelMoment';

export default {
	name: 'StreamSchedule',
	components: { Prompt, LanguageAudioSourceList },
	inject: {
		interpretationAdmin: { default: null },
	},
	props: {
		config: {
			type: Object,
			default: null,
		},
		roomId: {
			type: [String, Number],
			default: null,
		},
		openCreateOnMount: {
			type: Boolean,
			default: false,
		},
		roomName: {
			type: String,
			default: '',
		},
	},
	emits: ['create-requires-room', 'opened-create-on-mount'],
	setup: () => ({ v$: useVuelidate({ $stopPropagation: true }) }),
	data() {
		return {
			streamSchedules: null,
			loading: !!this.roomId,
			error: null,
			showCreateForm: false,
			editingSchedule: null,
			saving: false,
			saveError: null,
			formData: {
				title: '',
				url: '',
				start_time: null,
				end_time: null,
				stream_type: 'youtube',
				config: {},
			},
		};
	},
	computed: {
		showPluginLanguageStreams() {
			return Boolean(this.config?.interpretation_use_plugin_streams)
		},
		pluginLanguageStreamEntries() {
			return this.interpretationAdmin?.languageStreams ?? []
		},
		streamTypeOptions() {
			this.$store.state.userLocale
			return [
				{ id: 'youtube', label: this.$t('YouTube') },
				{ id: 'hls', label: this.$t('HLS') },
			]
		},
		eventTimezone() {
			return this.$store.state.world?.timezone || 'UTC';
		},
		plainStartTime: {
			get() {
				if (!this.formData.start_time) return undefined;
				const tz = this.eventTimezone || 'UTC';
				return moment.tz(this.formData.start_time, tz).format('YYYY-MM-DDTHH:mm');
			},
			set(value) {
				if (!value) {
					this.formData.start_time = null;
					return;
				}
				const tz = this.eventTimezone || 'UTC';
				this.formData.start_time = moment.tz(value, tz);
			},
		},
		plainEndTime: {
			get() {
				if (!this.formData.end_time) return undefined;
				const tz = this.eventTimezone || 'UTC';
				return moment.tz(this.formData.end_time, tz).format('YYYY-MM-DDTHH:mm');
			},
			set(value) {
				if (!value) {
					this.formData.end_time = null;
					return;
				}
				const tz = this.eventTimezone || 'UTC';
				this.formData.end_time = moment.tz(value, tz);
			},
		},
	},
	validations() {
		const urlRules = {
			required: required(this.$t('Stream URL is required'))
		};
		if (this.formData.stream_type === 'youtube') {
			urlRules.youtubeid = helpers.withMessage(this.$t('Must be a valid YouTube URL'), (value) => {
				if (!value) return true;
				return !!normalizeYoutubeVideoId(value);
			});
		} else {
			urlRules.url = url(this.$t('Must be a valid URL'));
		}

		const rules = {
			formData: {
				url: urlRules,
				start_time: {
					required: required(this.$t('Start time is required')),
				},
				end_time: {
					required: required(this.$t('End time is required')),
				},
				stream_type: {
					required: required(this.$t('Stream type is required')),
				},
			},
		};
		return rules;
	},
	async created() {
		if (!this.roomId) {
			this.streamSchedules = [];
			this.loading = false;
			return;
		}
		await this.fetchStreamSchedules();
		if (this.openCreateOnMount) {
			const savedDraft = this.loadSavedDraft();
			if (savedDraft) {
				this.formData = savedDraft;
				this.showCreateForm = true;
				await this.saveSchedule();
			} else {
				this.openCreateForm();
			}
			this.$emit('opened-create-on-mount');
		}
	},
	methods: {
		serializeFormData() {
			return {
				title: this.formData.title || '',
				url: this.formData.url,
				start_time: this.formData.start_time
					? this.formData.start_time.toISOString()
					: null,
				end_time: this.formData.end_time
					? this.formData.end_time.toISOString()
					: null,
				stream_type: this.formData.stream_type,
				config: {
					...this.formData.config,
					languageUrls: this.formData.config.languageUrls || [],
				},
			};
		},
		loadSavedDraft() {
			const key = `streamScheduleDraft:${this.roomId}`;
			const savedDraft = sessionStorage.getItem(key);
			if (!savedDraft) return null;
			sessionStorage.removeItem(key);
			try {
				const draft = JSON.parse(savedDraft);
				const tz = this.eventTimezone || 'UTC';
				return {
					title: draft.title || '',
					url: draft.url || '',
					start_time: draft.start_time ? this.parseApiDateTime(draft.start_time).tz(tz) : null,
					end_time: draft.end_time ? this.parseApiDateTime(draft.end_time).tz(tz) : null,
					stream_type: draft.stream_type || 'youtube',
					config: {
						...(draft.config || {}),
						languageUrls: draft.config?.languageUrls || [],
					},
				};
			} catch (error) {
				return null;
			}
		},
		getCsrfToken() {
			const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/);
			return match ? match[1] : null;
		},
		getApiBaseUrl() {
			const world = this.$store.state.world;

			// Try to get from world state first, then fall back to URL path
			let organizer = world?.organizer_slug;
			let event = world?.slug || world?.id;

			// If not available from world state, try to extract from current URL path
			if (!organizer || organizer === 'default') {
				const pathParts = window.location.pathname.split('/').filter(Boolean);
				// URL pattern: /{organizer}/{event}/video/event/rooms/{roomId}
				if (pathParts.length >= 2) {
					organizer = pathParts[0];
					event = pathParts[1];
				}
			}

			// Use absolute path to avoid config.api.base which includes /events/{id}/
			return `/api/v1/organizers/${organizer}/events/${event}/rooms/${this.roomId}/stream-schedules/`;
		},
		async fetchStreamSchedules() {
			if (!this.roomId) {
				this.streamSchedules = [];
				this.loading = false;
				return;
			}
			try {
				this.error = null;
				this.loading = true;
				const url = this.getApiBaseUrl();
				const authHeader = api._config.token
					? `Bearer ${api._config.token}`
					: api._config.clientId
					? `Client ${api._config.clientId}`
					: null;
				const headers = { Accept: 'application/json' };
				if (authHeader) headers.Authorization = authHeader;

				const response = await fetch(url, { headers, credentials: 'include' });
				if (response.status === 404) {
					this.streamSchedules = [];
					this.loading = false;
					return;
				}
				if (!response.ok) {
					throw new Error(`Failed to load schedules: ${response.statusText}`);
				}
				const data = await response.json();
				// Handle both array and paginated response
				this.streamSchedules = Array.isArray(data) ? data : data.results || [];
			} catch (error) {
				this.error = error.message || this.$t('Failed to load stream schedules');
				this.streamSchedules = [];
			} finally {
				this.loading = false;
			}
		},
		openCreateForm() {
			this.v$.$reset();
			this.showCreateForm = true;
		},
		editSchedule(schedule) {
			this.v$.$reset();
			this.editingSchedule = schedule;
			const tz = this.eventTimezone || 'UTC';
			let config = schedule.config ? JSON.parse(JSON.stringify(schedule.config)) : {};
			config.languageUrls = config.languageUrls || [];
			this.formData = {
				title: schedule.title || '',
				url: schedule.url,
				start_time: schedule.start_time ? this.parseApiDateTime(schedule.start_time).tz(tz) : null,
				end_time: schedule.end_time ? this.parseApiDateTime(schedule.end_time).tz(tz) : null,
				stream_type: schedule.stream_type,
				config: config,
			};
		},
		closeForm() {
			this.showCreateForm = false;
			this.editingSchedule = null;
			this.formData = {
				title: '',
				url: '',
				start_time: null,
				end_time: null,
				stream_type: 'youtube',
				config: { languageUrls: [] },
			};
			this.saveError = null;
			this.v$.$reset();
		},
		async saveSchedule() {
			this.saveError = null;
			this.v$.$touch();
			if (this.v$.$invalid) return;

			// Compare timestamps in UTC to avoid browser-timezone surprises.
			const now = moment.utc();
			if (this.formData.start_time) {
				const startTimeUtc = this.formData.start_time.clone().utc();
				if (!this.editingSchedule && startTimeUtc.isBefore(now)) {
					this.saveError = this.$t('Start time cannot be in the past.');
					return;
				}
				if (
					this.editingSchedule &&
					this.editingSchedule.start_time &&
					this.parseApiDateTime(this.editingSchedule.start_time).utc().isSameOrAfter(now) &&
					startTimeUtc.isBefore(now)
				) {
					this.saveError = this.$t('Start time cannot be in the past.');
					return;
				}
			}
			if (this.formData.start_time && this.formData.end_time) {
				if (this.formData.end_time.isSameOrBefore(this.formData.start_time)) {
					this.saveError = this.$t('End time must be after start time.');
					return;
				}
			}
			if (!this.roomId) {
				if (!this.roomName.trim()) {
					this.saveError = this.$t('Room name is required.');
					return;
				}
				this.$emit('create-requires-room', this.serializeFormData());
				return;
			}

			this.saving = true;
			try {
				const url = this.getApiBaseUrl();
				const authHeader = api._config.token
					? `Bearer ${api._config.token}`
					: api._config.clientId
					? `Client ${api._config.clientId}`
					: null;
				const headers = {
					Accept: 'application/json',
					'Content-Type': 'application/json',
				};
				if (authHeader) headers.Authorization = authHeader;
				const csrfToken = this.getCsrfToken();
				if (csrfToken) headers['X-CSRFToken'] = csrfToken;

				const payload = this.serializeFormData();

				let response;
				if (this.editingSchedule) {
					response = await fetch(`${url}${this.editingSchedule.id}/`, {
						method: 'PATCH',
						headers,
						body: JSON.stringify(payload),
						credentials: 'include',
					});
				} else {
					response = await fetch(url, {
						method: 'POST',
						headers,
						body: JSON.stringify(payload),
						credentials: 'include',
					});
				}

				if (!response.ok) {
					const responseClone = response.clone();
					let errorData = {};
					try {
						errorData = await response.json();
					} catch (e) {
						try {
							const text = await responseClone.text();
							if (text) {
								try {
									errorData = JSON.parse(text);
								} catch (parseError) {
									errorData = { detail: text };
								}
							}
						} catch (textError) {
						}
					}

					let errorMessage = null;

					if (errorData && typeof errorData === 'object') {
						const errorKeys = [
							'__all__',
							'non_field_errors',
							'detail',
							'message',
						];
						for (const key of errorKeys) {
							if (errorData[key]) {
								const val = errorData[key];
								if (Array.isArray(val) && val[0]) {
									errorMessage = val[0];
								} else if (typeof val === 'string') {
									errorMessage = val;
								}
								if (errorMessage) break;
							}
						}

						if (!errorMessage && Object.keys(errorData).length > 0) {
							const firstKey = Object.keys(errorData)[0];
							const firstValue = errorData[firstKey];
							if (Array.isArray(firstValue) && firstValue[0]) {
								errorMessage = firstValue[0];
							} else if (typeof firstValue === 'string') {
								errorMessage = firstValue;
							}
						}
					} else if (typeof errorData === 'string') {
						errorMessage = errorData;
					}

					if (!errorMessage) {
						errorMessage = this.$t('Bad Request');
					}

					throw new Error(errorMessage);
				}

				this.saving = false;
				this.closeForm();
				await this.fetchStreamSchedules();
			} catch (error) {
				this.saving = false;
				this.saveError = error.message || this.$t('Failed to save stream schedule');
			}
		},
		async deleteSchedule(schedule) {
			if (!confirm(`${this.$t('Delete stream schedule')} "${schedule.title || this.$t('Untitled')}"?`))
				return;

			try {
				const url = `${this.getApiBaseUrl()}${schedule.id}/`;
				const authHeader = api._config.token
					? `Bearer ${api._config.token}`
					: api._config.clientId
					? `Client ${api._config.clientId}`
					: null;
				const headers = { Accept: 'application/json' };
				if (authHeader) headers.Authorization = authHeader;
				const csrfToken = this.getCsrfToken();
				if (csrfToken) headers['X-CSRFToken'] = csrfToken;

				const response = await fetch(url, {
					method: 'DELETE',
					headers,
					credentials: 'include',
				});
				if (!response.ok)
					throw new Error(`Failed to delete: ${response.status}`);

				await this.fetchStreamSchedules();
			} catch (error) {
				this.error = error.message || this.$t('Failed to delete stream schedule');
			}
		},
		formatDateTime(datetime) {
			if (!datetime) return '';
			const tz = this.eventTimezone || 'UTC';
			return this.parseApiDateTime(datetime).tz(tz).format('YYYY-MM-DD HH:mm');
		},
		parseApiDateTime(datetime) {
			if (!datetime) return moment.invalid();
			if (moment.isMoment(datetime)) return datetime.clone();
			if (datetime instanceof Date) return moment(datetime);
			const value = String(datetime);
			// If the backend returns a timezone offset (e.g. 'Z' or '+01:00'), preserve it.
			// Otherwise treat the timestamp as UTC (not browser-local).
			const hasTimezone = /([zZ]|[+-]\d\d:?\d\d)$/.test(value);
			return hasTimezone ? moment.parseZone(value) : moment.utc(value);
		},
	},
};
</script>
<style lang="stylus">
.c-stream-schedule
	margin-top: 24px
	padding-top: 16px
	border-top: border-separator()
	h2
		margin-bottom: 16px
		font-size: 18px
		font-weight: 500
	.error
		color: $clr-danger
		margin-bottom: 16px
	.stream-schedules-list
		margin-top: 16px
		margin-bottom: 16px
		max-height: 300px
	.stream-schedule-item
		display: flex
		justify-content: space-between
		align-items: center
		padding: 12px
		border: border-separator()
		border-radius: 4px
		margin-bottom: 8px
		background: $clr-grey-50
		.info
			flex: auto
			.title
				font-weight: 500
				margin-bottom: 4px
			.url, .time, .type
				font-size: 12px
				color: $clr-grey-600
				margin-top: 2px
			.url
				word-break: break-all
		.actions
			display: flex
			gap: 8px
			flex-shrink: 0
			.bunt-icon-button
				icon-button-style(style: clear)
	.loading
		display: flex
		justify-content: center
		padding: 24px
	.interpretation-plugin-language-streams
		margin-bottom: 24px
		padding-bottom: 16px
		border-bottom: 1px solid $clr-grey-300
		.plugin-language-streams-hint
			margin: 8px 0 0
			font-size: 13px
			color: $clr-secondary-text-light
	.empty-state
		text-align: center
		padding: 24px
		color: $clr-grey-600
		p
			margin: 4px 0
	.add-btn
		margin-top: 16px
	.field-hint
		margin-top: 4px
		font-size: 12px
		line-height: 18px
		color: $clr-secondary-text-light

.c-stream-schedule-prompt
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		overflow-y: auto !important
		h1
			margin: 0 0 24px 0
			font-size: 20px
			font-weight: 500
	.stream-schedule-form
		display: flex
		flex-direction: column
		align-self: stretch
		.datetime-field
			margin-bottom: 16px
			.datetime-label
				display: block
				font-size: 12px
				color: $clr-grey-600
				margin-bottom: 6px
			.datetime-input
				width: 100%
				padding: 12px
				border: 1px solid $clr-grey-300
				border-radius: 4px
				font-size: 14px
				font-family: inherit
				background-color: white
				color: $clr-grey-800
				box-sizing: border-box
				&::-webkit-datetime-edit-fields-wrapper
					padding: 0
				&::-webkit-datetime-edit
					padding: 0
				&::-webkit-datetime-edit-text
					padding: 0 4px
				&::-webkit-datetime-edit-month-field,
				&::-webkit-datetime-edit-day-field,
				&::-webkit-datetime-edit-year-field,
				&::-webkit-datetime-edit-hour-field,
				&::-webkit-datetime-edit-minute-field,
				&::-webkit-datetime-edit-ampm-field
					padding: 0
				&::-webkit-calendar-picker-indicator
					cursor: pointer
					opacity: 0.6
					&:hover
						opacity: 1
				&:focus
					outline: none
					border-color: var(--clr-primary)
				&.has-error
					border-color: $clr-danger
			.error-message
				color: $clr-danger
				font-size: 12px
				margin-top: 4px
		.timezone-hint
			margin-bottom: 16px
			font-size: 14px
			color: $clr-grey-600
			i
				font-style: italic
		.form-error
			color: $clr-danger
			font-size: 14px
			padding: 12px 16px
			background: rgba($clr-danger, 0.1)
			border-radius: 4px
			margin-top: 24px
			margin-bottom: 16px
			border-left: 3px solid $clr-danger
		.form-actions
			display: flex
			gap: 12px
			margin-top: 16px
			.bunt-button
				&.btn-save
					themed-button-primary()
				&.btn-cancel
					themed-button-secondary()
</style>
