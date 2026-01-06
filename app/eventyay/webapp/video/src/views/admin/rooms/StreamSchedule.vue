<template lang="pug">
.c-stream-schedule
	h2 Stream Schedules
	.error(v-if="error") {{ error }}
	.stream-schedules-list(v-scrollbar.y="", v-if="streamSchedules !== null")
		.stream-schedule-item(v-for="schedule in streamSchedules", :key="schedule.id")
			.info
				.title {{ schedule.title || 'Untitled Stream' }}
				.url {{ schedule.url }}
				.time {{ formatDateTime(schedule.start_time) }} - {{ formatDateTime(schedule.end_time) }}
				.type {{ schedule.stream_type }}
			.actions
				bunt-icon-button(@click="editSchedule(schedule)") edit
				bunt-icon-button(@click="deleteSchedule(schedule)") delete
		bunt-progress-circular(v-else, size="huge")
	bunt-button(@click="showCreateForm = true") Add Stream Schedule
	transition(name="prompt")
		prompt(v-if="showCreateForm || editingSchedule", @close="closeForm")
			.content
				.prompt-header
					h3 {{ editingSchedule ? 'Edit' : 'Create' }} Stream Schedule
				.stream-schedule-form
					bunt-input(name="title", v-model="formData.title", label="Title (optional)")
					bunt-input(name="url", v-model="formData.url", label="Stream URL", :validation="v$.formData.url", required)
					bunt-input(name="start_time", type="datetime-local", v-model="plainStartTime", label="Start Time", :validation="v$.formData.start_time", required)
					bunt-input(name="end_time", type="datetime-local", v-model="plainEndTime", label="End Time", :validation="v$.formData.end_time", required)
					bunt-select(name="stream_type", v-model="formData.stream_type", label="Stream Type", :options="streamTypes", :validation="v$.formData.stream_type")
				.ui-form-actions
					bunt-button.btn-save(@click="saveSchedule", :loading="saving", :error-message="saveError") {{ editingSchedule ? 'Save' : 'Create' }}
					bunt-button.btn-cancel(@click="closeForm") Cancel
</template>
<script>
import { useVuelidate } from "@vuelidate/core";
import { required, url } from "lib/validators";
import api from "lib/api";
import config from "config";
import Prompt from "components/Prompt";
import moment from "lib/timetravelMoment";

export default {
	name: "StreamSchedule",
	components: { Prompt },
	props: {
		roomId: {
			type: String,
			required: true,
		},
	},
	setup: () => ({ v$: useVuelidate() }),
	data() {
		return {
			streamSchedules: null,
			error: null,
			showCreateForm: false,
			editingSchedule: null,
			saving: false,
			saveError: null,
			streamTypes: [
				{ value: "youtube", label: "YouTube" },
				{ value: "vimeo", label: "Vimeo" },
				{ value: "hls", label: "HLS" },
				{ value: "iframe", label: "Iframe" },
				{ value: "native", label: "Native" },
			],
			formData: {
				title: "",
				url: "",
				start_time: null,
				end_time: null,
				stream_type: "youtube",
			},
		};
	},
	computed: {
		plainStartTime: {
			get() {
				return this.formData.start_time
					? this.formData.start_time.format("YYYY-MM-DDTHH:mm")
					: "";
			},
			set(value) {
				this.formData.start_time = value ? moment(value) : null;
			},
		},
		plainEndTime: {
			get() {
				return this.formData.end_time
					? this.formData.end_time.format("YYYY-MM-DDTHH:mm")
					: "";
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
					required: required("Stream URL is required"),
					url: url("Must be a valid URL"),
				},
				start_time: {
					required: required("Start time is required"),
				},
				end_time: {
					required: required("End time is required"),
				},
				stream_type: {
					required: required("Stream type is required"),
				},
			},
		};
	},
	async created() {
		await this.fetchStreamSchedules();
	},
	methods: {
		getApiBaseUrl() {
			const base = config.api.base || "/api/v1/";
			const organizer = this.$store.state.world?.organizer || "default";
			const event = this.$store.state.world?.slug || "default";
			return `${base}organizers/${organizer}/events/${event}/rooms/${this.roomId}/stream-schedules/`;
		},
		async fetchStreamSchedules() {
			try {
				this.error = null;
				const url = this.getApiBaseUrl();
				const authHeader = api._config.token
					? `Bearer ${api._config.token}`
					: api._config.clientId
					? `Client ${api._config.clientId}`
					: null;
				const headers = { Accept: "application/json" };
				if (authHeader) headers.Authorization = authHeader;

				const response = await fetch(url, { headers });
				if (!response.ok)
					throw new Error(`Failed to fetch: ${response.status}`);
				this.streamSchedules = await response.json();
			} catch (error) {
				console.error(error);
				this.error = error.message || "Failed to load stream schedules";
			}
		},
		editSchedule(schedule) {
			this.editingSchedule = schedule;
			this.formData = {
				title: schedule.title || "",
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
				title: "",
				url: "",
				start_time: null,
				end_time: null,
				stream_type: "youtube",
			};
			this.saveError = null;
		},
		async saveSchedule() {
			this.saveError = null;
			this.v$.$touch();
			if (this.v$.$invalid) return;

			this.saving = true;
			try {
				const url = this.getApiBaseUrl();
				const authHeader = api._config.token
					? `Bearer ${api._config.token}`
					: api._config.clientId
					? `Client ${api._config.clientId}`
					: null;
				const headers = {
					Accept: "application/json",
					"Content-Type": "application/json",
				};
				if (authHeader) headers.Authorization = authHeader;

				const payload = {
					title: this.formData.title || "",
					url: this.formData.url,
					start_time: this.formData.start_time.toISOString(),
					end_time: this.formData.end_time.toISOString(),
					stream_type: this.formData.stream_type,
				};

				let response;
				if (this.editingSchedule) {
					response = await fetch(`${url}${this.editingSchedule.id}/`, {
						method: "PATCH",
						headers,
						body: JSON.stringify(payload),
					});
				} else {
					response = await fetch(url, {
						method: "POST",
						headers,
						body: JSON.stringify(payload),
					});
				}

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(
						errorData.detail ||
							errorData.message ||
							`Failed to save: ${response.status}`
					);
				}

				this.saving = false;
				this.closeForm();
				await this.fetchStreamSchedules();
			} catch (error) {
				console.error(error);
				this.saving = false;
				this.saveError = error.message || "Failed to save stream schedule";
			}
		},
		async deleteSchedule(schedule) {
			if (!confirm(`Delete stream schedule "${schedule.title || "Untitled"}"?`))
				return;

			try {
				const url = `${this.getApiBaseUrl()}${schedule.id}/`;
				const authHeader = api._config.token
					? `Bearer ${api._config.token}`
					: api._config.clientId
					? `Client ${api._config.clientId}`
					: null;
				const headers = { Accept: "application/json" };
				if (authHeader) headers.Authorization = authHeader;

				const response = await fetch(url, { method: "DELETE", headers });
				if (!response.ok)
					throw new Error(`Failed to delete: ${response.status}`);

				await this.fetchStreamSchedules();
			} catch (error) {
				console.error(error);
				this.error = error.message || "Failed to delete stream schedule";
			}
		},
		formatDateTime(datetime) {
			return moment(datetime).format("YYYY-MM-DD HH:mm");
		},
	},
};
</script>
<style lang="stylus">
.c-stream-schedule
	.stream-schedules-list
		margin-top: 16px
		margin-bottom: 16px
	.stream-schedule-item
		display: flex
		justify-content: space-between
		align-items: center
		padding: 12px
		border: border-separator()
		border-radius: 4px
		margin-bottom: 8px
		.info
			flex: auto
			.title
				font-weight: 500
				margin-bottom: 4px
			.url, .time, .type
				font-size: 12px
				color: $clr-grey-600
				margin-top: 2px
		.actions
			display: flex
			gap: 8px
</style>
