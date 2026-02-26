<template lang="pug">
.c-scheduleconfig
	.ui-page-header
	scrollbars(y)
		bunt-progress-circular(size="huge", v-if="!error && !config")
		.error(v-if="error") We could not fetch the current configuration.
		.ui-form-body(v-if="config")
			bunt-select(name="source", label="Schedule source", v-model="source", :options="sourceOptions")
			template(v-if="source === 'url'")
				p To automatically load the schedule from an external system, enter an URL here. Note that the URL must be a JSON file compliant with the eventyay-talk schedule widget API version 2.
				bunt-input(name="url", label="JSON URL", v-model="config.pretalx.url", placeholder="e.g. https://website.com/event.json", :validation="v$.config.pretalx.url")
			template(v-else-if="source === 'file'")
				p If you don't use eventyay-talk, you can upload your schedule as a Microsoft Excel file (XLSX) with a specific setup.
				p
					a(href="/schedule_ex_en.xlsx", target="_blank") Download English sample file
					| {{ " / " }}
					a(href="/schedule_ex_de.xlsx", target="_blank") Download German sample file
				upload-url-input(name="schedule-file", v-model="config.pretalx.url", label="Schedule file", :upload-url="uploadUrl", accept="application/vnd.ms-excel, .xlsx", :validation="v$.config.pretalx.url")
			template(v-else-if="source === 'conftool'")
				p conftool is controlled by the main conftool settings.
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") Save
		.errors {{ validationErrors.join(', ') }}
</template>
<script>
import { useVuelidate } from '@vuelidate/core'
import config from 'config'
import api from 'lib/api'
import { required, url } from 'lib/validators'
import UploadUrlInput from 'components/UploadUrlInput'
import ValidationErrorsMixin from 'components/mixins/validation-errors'

export default {
	components: { UploadUrlInput },
	mixins: [ValidationErrorsMixin],
	setup:() => ({v$:useVuelidate()}),
	data() {
		return {
			uploadUrl: config.api.scheduleImport,
			showUpload: false, // HACK we need an extra flag to show an empty file upload, since url and file use the same config field
			config: null,
			saving: false,
			error: null
		}
	},
	computed: {
		sourceOptions() {
			const sourceOptions = [
				{id: null, label: 'No Schedule'},
				{id: 'file', label: 'File Upload'},
				{id: 'url', label: 'External URL'},
			]
			if (this.$features.enabled('conftool')) {
				sourceOptions.push({id: 'conftool', label: 'Conftool'})
			}
			return sourceOptions
		},
		source: {
			get() {
				if (!this.config) return
				if (this.config.pretalx.conftool) return 'conftool'
				if (this.showUpload) return 'file'
				if (this.config.pretalx.url !== undefined) {
					if (this.config.pretalx.url.includes('/pub/')) { // this *looks* like our storage
						return 'file'
					}
					return 'url'
				}
				return null
			},
			set(value) {
				this.showUpload = false
				switch (value) {
					case 'file':
						this.showUpload = true
						this.config.pretalx = {
							url: ''
						}
						break
					case 'url':
						this.config.pretalx = {
							url: ''
						}
						break
					case 'conftool':
						this.config.pretalx = {
							conftool: true,
							url: this.config.pretalx.url
						}
						break
					case null:
						this.config.pretalx = {}
						break
				}
			}
		},
	},
	validations() {
		if (this.source === 'url' || this.source === 'file') {
			return {
				config: {
					pretalx: {
						url: {
							required: required('URL is required'),
							url: url('URL must be a valid URL')
						}
					}
				}
			}
		}
		return {}
	},
	async created() {
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('world.config.get')
		} catch (error) {
			this.error = error.message || error.toString()
			console.log(error)
		}
	},
	async mounted() {
		await this.$nextTick()
	},
	methods: {
		async save() {
			this.v$.$touch()
			if (this.v$.$invalid) return false
			if (!this.config) return false
			this.saving = true
			try {
				await api.call('world.config.patch', {pretalx: this.config.pretalx})
			} catch (error) {
				console.error(error.apiError || error)
				this.error = error.apiError?.code || error.message || error.toString()
			} finally {
				this.saving = false
			}
			return true
		}
	}
}
</script>
<style lang="stylus">
.c-scheduleconfig
	flex: auto
	display: flex
	flex-direction: column
	.scroll-content
		flex: auto // take up more space for select dropdown to position correctly
	.pretalx-status
		font-weight: bold
		color: $clr-success
		&.plugin-not-installed, &.not-connected
			color: $clr-danger
	#btn-pretalx-connect
		margin: 16px 0
		align-self: flex-start
		themed-button-secondary()
</style>
