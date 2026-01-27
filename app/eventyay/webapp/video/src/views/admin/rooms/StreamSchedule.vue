<template lang="pug">
.c-stream-schedule
	h2 Stream Schedules
	.error(v-if="error") {{ error }}
	.loading(v-if="loading")
		bunt-progress-circular(size="large")
	template(v-else)
		.stream-schedules-list(v-scrollbar.y="", v-if="streamSchedules && streamSchedules.length > 0")
			.stream-schedule-item(v-for="schedule in streamSchedules", :key="schedule.id")
				.info
					.title {{ schedule.title || 'Untitled Stream' }}
					.url {{ schedule.url }}
					.time {{ formatDateTime(schedule.start_time) }} - {{ formatDateTime(schedule.end_time) }} ({{ eventTimezone }})
					.type {{ schedule.stream_type }}
				.actions
					bunt-icon-button(@click="editSchedule(schedule)") pencil
					bunt-icon-button(@click="deleteSchedule(schedule)") delete-outline
		.empty-state(v-else-if="streamSchedules !== null")
			p No stream schedules configured yet.
			p Click "Add Stream Schedule" to create one.
	bunt-button.add-btn(@click="openCreateForm") + Add Stream Schedule
	transition(name="prompt")
		prompt.c-stream-schedule-prompt(v-if="showCreateForm || editingSchedule", @close="closeForm")
			.content
				h1 {{ editingSchedule ? 'Edit' : 'Create' }} Stream Schedule
				form.stream-schedule-form(@submit.prevent="saveSchedule")
					bunt-input(name="title", v-model="formData.title", label="Title (optional)", placeholder="e.g., Day 1 Stream, Keynotes")
					bunt-input(name="url", v-model="formData.url", label="Stream URL", :validation="v$.formData.url", required, placeholder="https://youtube.com/watch?v=...")
					.datetime-field
						label.datetime-label Start Time ({{ eventTimezone }})
						input.datetime-input(type="datetime-local", v-model="plainStartTime", :class="{'has-error': v$.formData.start_time.$error}")
						.error-message(v-if="v$.formData.start_time.$error") Start time is required
					.datetime-field
						label.datetime-label End Time ({{ eventTimezone }})
						input.datetime-input(type="datetime-local", v-model="plainEndTime", :class="{'has-error': v$.formData.end_time.$error}")
						.error-message(v-if="v$.formData.end_time.$error") End time is required
					.timezone-hint
						i All times in {{ eventTimezone }}
					bunt-select(name="stream_type", v-model="formData.stream_type", label="Stream Type", :options="streamTypes", :validation="v$.formData.stream_type")
					.form-error(v-if="saveError")
						| {{ saveError }}
					.form-actions
						bunt-button.btn-save(type="submit", :loading="saving") {{ editingSchedule ? 'Save' : 'Create' }}
						bunt-button.btn-cancel(@click="closeForm") Cancel
</template>
<script>
import { useVuelidate } from '@vuelidate/core';
import { required, url } from 'lib/validators';
import api from 'lib/api';
import config from 'config';
import Prompt from 'components/Prompt';
import moment from 'lib/timetravelMoment';

export default {
	name: 'StreamSchedule',
	components: { Prompt },
	props: {
		roomId: {
			type: [String, Number],
			required: true,
		},
	},
	setup: () => ({ v$: useVuelidate({ $stopPropagation: true }) }),
	data() {
		return {
			streamSchedules: null,
			loading: true,
			error: null,
			showCreateForm: false,
			editingSchedule: null,
			saving: false,
			saveError: null,
			streamTypes: [
				{ id: 'youtube', label: 'YouTube' },
				{ id: 'vimeo', label: 'Vimeo' },
				{ id: 'hls', label: 'HLS' },
				{ id: 'iframe', label: 'Iframe' },
				{ id: 'native', label: 'Native' },
			],
			formData: {
				title: '',
				url: '',
				start_time: null,
				end_time: null,
				stream_type: 'youtube',
			},
		};
	},
	computed: {
		eventTimezone() {
			return this.$store.state.world?.timezone || 'UTC';
		},
		plainStartTime: {
			get() {
				return this.formData.start_time
					? this.formData.start_time.format('YYYY-MM-DDTHH:mm')
					: undefined;
			},
			set(value) {
				this.formData.start_time = value ? moment(value) : null;
			},
		},
		plainEndTime: {
			get() {
				return this.formData.end_time
					? this.formData.end_time.format('YYYY-MM-DDTHH:mm')
					: undefined;
			},
			set(value) {
				this.formData.end_time = value ? moment(value) : null;
			},
		},
	},
	validations() {
		return {
			formData: {
				url: {
					required: required('Stream URL is required'),
					url: url('Must be a valid URL'),
				},
				start_time: {
					required: required('Start time is required'),
				},
				end_time: {
					required: required('End time is required'),
				},
				stream_type: {
					required: required('Stream type is required'),
				},
			},
		};
	},
	async created() {
		await this.fetchStreamSchedules();
	},
	methods: {
		getCsrfToken() {
			const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/);
			return match ? match[1] : null;
		},
		getApiBaseUrl() {
			const world = this.$store.state.world;

			// Try to get from world state first, then fall back to URL path
			let organizer = world?.organizer || world?.organizer_slug;
			let event = world?.slug || world?.id;

			// If not available from world state, try to extract from current URL path
			if (!organizer || organizer === 'default') {
				const pathParts = window.location.pathname.split('/').filter(Boolean);
				// URL pattern: /{organizer}/{event}/video/admin/rooms/{roomId}
				if (pathParts.length >= 2) {
					organizer = pathParts[0];
					event = pathParts[1];
				}
			}

			// Use absolute path to avoid config.api.base which includes /events/{id}/
			return `/api/v1/organizers/${organizer}/events/${event}/rooms/${this.roomId}/stream-schedules/`;
		},
		async fetchStreamSchedules() {
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
				this.error = error.message || 'Failed to load stream schedules';
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
			this.formData = {
				title: schedule.title || '',
				url: schedule.url,
				start_time: moment(schedule.start_time),
				end_time: moment(schedule.end_time),
				stream_type: schedule.stream_type,
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
			};
			this.saveError = null;
			this.v$.$reset();
		},
		async saveSchedule() {
			this.saveError = null;
			this.v$.$touch();
			if (this.v$.$invalid) return;

			const now = moment();
			if (this.formData.start_time) {
				if (!this.editingSchedule && this.formData.start_time.isBefore(now)) {
					this.saveError = 'Start time cannot be in the past.';
					return;
				}
				if (
					this.editingSchedule &&
					this.editingSchedule.start_time &&
					moment(this.editingSchedule.start_time).isSameOrAfter(now) &&
					this.formData.start_time.isBefore(now)
				) {
					this.saveError = 'Start time cannot be in the past.';
					return;
				}
			}
			if (this.formData.start_time && this.formData.end_time) {
				if (this.formData.end_time.isSameOrBefore(this.formData.start_time)) {
					this.saveError = 'End time must be after start time.';
					return;
				}
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

				const payload = {
					title: this.formData.title || '',
					url: this.formData.url,
					start_time: this.formData.start_time
						? this.formData.start_time.toISOString()
						: null,
					end_time: this.formData.end_time
						? this.formData.end_time.toISOString()
						: null,
					stream_type: this.formData.stream_type,
				};

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
						errorMessage = 'Bad Request';
					}

					throw new Error(errorMessage);
				}

				this.saving = false;
				this.closeForm();
				await this.fetchStreamSchedules();
			} catch (error) {
				this.saving = false;
				this.saveError = error.message || 'Failed to save stream schedule';
			}
		},
		async deleteSchedule(schedule) {
			if (!confirm(`Delete stream schedule "${schedule.title || 'Untitled'}"?`))
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
				this.error = error.message || 'Failed to delete stream schedule';
			}
		},
		formatDateTime(datetime) {
			return moment(datetime).format('YYYY-MM-DD HH:mm');
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
	.empty-state
		text-align: center
		padding: 24px
		color: $clr-grey-600
		p
			margin: 4px 0
	.add-btn
		margin-top: 16px

.c-stream-schedule-prompt
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
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
