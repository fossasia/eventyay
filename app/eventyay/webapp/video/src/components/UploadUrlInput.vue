<template lang="pug">
.c-upload-url-input
	.input-row
		bunt-input(:modelValue="modelValue", :label="label", :name="name", :validation="validation", @update:modelValue="update($event)")
		bunt-progress-circular(v-if="uploading", size="small")
		.file-selector(v-else)
			bunt-icon-button upload
			input(ref="fileInput", type="file", :accept="accept", @change="upload")
	.upload-hint(v-if="maxFileSize") Maximum file size: {{ formatFileSize(maxFileSize) }}.
	.upload-error(v-if="uploadError", role="alert") {{ uploadError }}

</template>
<script>
import config from 'config'
import api from 'lib/api'

function formatFileSize(bytes) {
	return `${Math.round(bytes / (1024 * 1024))} MB`
}

export default {
	props: {
		modelValue: String,
		label: String,
		name: String,
		validation: Object,
		uploadUrl: String,
		maxFileSize: {
			type: Number,
			default: () => config.api.uploadMaxSize
		},
		accept: {
			type: String,
			default: 'image/png, .png, image/jpg, .jpg, .jpeg, image/gif, .gif, application/pdf, .pdf, image/svg+xml, .svg, video/mp4, video/mpeg, .mp4, video/webm, audio/webm, .webm, audio/mp3, audio/mpeg, .mp3'
		}
	},
	emits: ['update:modelValue'],
	data() {
		return {
			uploading: false,
			uploadError: '',
		}
	},
	methods: {
		formatFileSize,
		update(val) {
			this.uploadError = ''
			this.$emit('update:modelValue', val)
		},
		async upload() {
			const file = this.$refs.fileInput.files[0]
			if (!file) return

			this.uploadError = ''
			if (this.maxFileSize && file.size > this.maxFileSize && !file.type.startsWith('image/')) {
				this.uploadError = `The file is too large. Maximum upload size is ${formatFileSize(this.maxFileSize)}.`
				if (this.$refs.fileInput) this.$refs.fileInput.value = ''
				return
			}

			this.uploading = true
			try {
				const data = await api.uploadFilePromise(file, file.name, this.uploadUrl)
				// Update field and optimistically save pretalx URL if the parent provided save()
				this.$emit('update:modelValue', data.url)
				if (this.$parent?.save) {
					await this.$parent.save()
				}
			} catch (error) {
				console.error(`Upload failed for ${file.name}`, error)
				const apiError = error.apiError || {}
				if (apiError.status === 413 || apiError.error === 'file.size') {
					this.uploadError = this.maxFileSize
						? `The file is too large. Maximum upload size is ${formatFileSize(this.maxFileSize)}.`
						: 'The file is too large. Please choose a smaller file.'
				} else {
					this.uploadError = 'The file could not be uploaded. Please try again.'
				}
			} finally {
				this.uploading = false
				if (this.$refs.fileInput) {
					this.$refs.fileInput.value = ''
				}
			}
		}
	},
}
</script>
<style lang="stylus">
	.c-upload-url-input
		.input-row
			display: flex
			align-items: center
		.bunt-progress-circular.small
			margin: 0 6px
		.bunt-input
			flex-grow: 1

		.file-selector
			flex-grow: 0
			position: relative

			input
				opacity: 0
				cursor: pointer
				position: absolute
				width: 100%
				height: 100%
				top: 0
				left: 0

		.upload-hint,
		.upload-error
			font-size: 12px
			margin-top: 4px

		.upload-hint
			color: $clr-secondary-text-light

		.upload-error
			color: $clr-danger
</style>
