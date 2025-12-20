<template lang="pug">
.c-change-avatar(v-if="modelValue")
	.inputs
		bunt-button.btn-randomize(@click="changeIdenticon") {{ $t('profile/ChangeAvatar:button-randomize:label') }}
		span {{ $t('profile/ChangeAvatar:or') }}
		upload-button.btn-upload(@change="fileSelected", accept="image/png, image/jpg, image/jpeg, .png, .jpg, .jpeg") {{ $t('profile/ChangeAvatar:button-upload:label') }}
	.upload-info Maximum file size: 10 MB. Supported formats: PNG, JPG, JPEG. Minimum dimensions: 128x128 pixels.
	.image-wrapper
		.file-error(v-if="fileError")
			.mdi.mdi-alert-octagon
			.message {{ fileError }}
		Cropper(v-else-if="avatarImage", ref="cropperRef", class="cropper", :stencilComponent="CircleStencil", :src="avatarImage", :stencilProps="{aspectRatio: '1/1'}", :sizeRestrictionsAlgorithm="pixelsRestrictions")
		identicon(v-else, :user="identiconUser", @click="changeIdenticon")
</template>
<script setup>
import { ref, computed, onMounted, getCurrentInstance, nextTick } from 'vue'
import { v4 as uuid } from 'uuid'
import { Cropper, CircleStencil } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'
import api from 'lib/api'
import Identicon from 'components/Identicon'
import UploadButton from 'components/UploadButton'

const MIN_AVATAR_SIZE = 128
const UPLOAD_AVATAR_SIZE = 256
const MAX_FILE_SIZE_MB = 10
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
const ALLOWED_FORMATS = ['image/png', 'image/jpg', 'image/jpeg']

// Props & Emits
const props = defineProps({
	modelValue: Object,
	profile: Object,
})
const emit = defineEmits(['update:modelValue', 'blockSave'])

// Globals
const { proxy } = getCurrentInstance()

// State
const identiconValue = ref(null)
const avatarImage = ref(null)
const fileError = ref(null)
const changedImage = ref(false)
const cropperRef = ref(null)
const selectedFileSize = ref(null)

// Derived
const identiconUser = computed(() => ({
	profile: {
		...props.profile,
		avatar: { identicon: identiconValue.value },
	},
}))

// Actions
function changeIdenticon() {
	fileError.value = null
	avatarImage.value = null
	selectedFileSize.value = null
	identiconValue.value = uuid()
	emit('blockSave', false)
}

function fileSelected(event) {
	fileError.value = null
	avatarImage.value = null
	selectedFileSize.value = null
	emit('blockSave', false)
	if (event.target.files.length !== 1) return
	const avatarFile = event.target.files[0]
	selectedFileSize.value = avatarFile.size
	
	// Validate file size (10MB max)
	if (avatarFile.size > MAX_FILE_SIZE_BYTES) {
		fileError.value = `File size exceeds ${MAX_FILE_SIZE_MB} MB. Please choose a smaller image.`
		emit('blockSave', true)
		event.target.value = ''
		return
	}
	
	// Validate file format
	if (!ALLOWED_FORMATS.includes(avatarFile.type)) {
		fileError.value = 'Invalid file format. Only PNG, JPG, and JPEG images are allowed.'
		emit('blockSave', true)
		event.target.value = ''
		return
	}
	
	const reader = new FileReader()
	reader.readAsDataURL(avatarFile)
	event.target.value = ''
	reader.onload = (readerEvent) => {
		if (readerEvent.target.readyState !== FileReader.DONE) return
		const img = new Image()
		img.onload = () => {
			if (img.width < MIN_AVATAR_SIZE || img.height < MIN_AVATAR_SIZE) {
				fileError.value = proxy.$t('profile/ChangeAvatar:error:image-too-small')
				emit('blockSave', true)
			} else {
				changedImage.value = true
				nextTick(() => {
					avatarImage.value = readerEvent.target.result
				})
			}
		}
		img.src = readerEvent.target.result
	}
}

function pixelsRestrictions({ minWidth, minHeight, maxWidth, maxHeight }) {
	return {
		minWidth: Math.max(MIN_AVATAR_SIZE, minWidth),
		minHeight: Math.max(MIN_AVATAR_SIZE, minHeight),
		maxWidth,
		maxHeight,
	}
}

async function update() {
	const { canvas } = cropperRef.value?.getResult() || {}
	if (!canvas) {
		emit('update:modelValue', { identicon: identiconValue.value })
		return
	}
	if (!changedImage.value) return

	const processed = await createAvatarBlob(canvas)
	if (!processed) {
		fileError.value = proxy.$t('profile/ChangeAvatar:error:process-failed')
		emit('blockSave', true)
		return
	}
	const { blob: resizedBlob, dimension } = processed
	if (ENV_DEVELOPMENT) {
		console.info('[avatar-upload] original size:', selectedFileSize.value || 0, 'bytes; upload size:', resizedBlob.size, 'bytes; dimension:', dimension + 'px')
	}

	await new Promise((resolve) => {
		const request = api.uploadFile(resizedBlob, 'avatar.png', null, dimension, dimension)
		const handleFailure = (status, responseText) => {
			let message = proxy.$t('profile/ChangeAvatar:error:upload-failed')
			if (status === 413) {
				message = proxy.$t('profile/ChangeAvatar:error:file-too-large')
			}
			console.error('[avatar-upload]', status, responseText)
			fileError.value = message
			emit('blockSave', true)
			resolve()
		}
		request.addEventListener('load', () => {
			const status = request.status
			const responseText = request.responseText || ''
			const contentType = request.getResponseHeader('content-type') || ''
			if (status < 200 || status >= 300 || !contentType.includes('application/json')) {
				return handleFailure(status, responseText)
			}
			try {
				const response = JSON.parse(responseText)
				emit('update:modelValue', { url: response.url })
				emit('blockSave', false)
				resolve()
			} catch (error) {
				return handleFailure(status, responseText)
			}
		})
		request.addEventListener('error', () => {
			handleFailure(request.status, request.responseText)
		})
	})
}

function createAvatarBlob(sourceCanvas) {
	return new Promise((resolve) => {
		const sourceSize = Math.min(sourceCanvas.width, sourceCanvas.height)
		const targetSize = Math.min(UPLOAD_AVATAR_SIZE, Math.max(MIN_AVATAR_SIZE, sourceSize))
		const canvas = document.createElement('canvas')
		canvas.width = targetSize
		canvas.height = targetSize
		const ctx = canvas.getContext('2d')
		if (!ctx) return resolve(null)
		ctx.imageSmoothingEnabled = true
		ctx.imageSmoothingQuality = 'high'
		ctx.drawImage(
			sourceCanvas,
			0,
			0,
			sourceCanvas.width,
			sourceCanvas.height,
			0,
			0,
			targetSize,
			targetSize
		)
		canvas.toBlob(blob => {
			if (!blob) return resolve(null)
			resolve({ blob, dimension: targetSize })
		}, 'image/png')
	})
}

onMounted(() => {
	if (!props.modelValue) {
		emit('update:modelValue', {})
		identiconValue.value = uuid()
	} else if (props.modelValue.url) {
		avatarImage.value = props.modelValue.url
	} else if (props.modelValue.identicon) {
		identiconValue.value = props.modelValue.identicon
	}
})

// Expose for parent refs
defineExpose({ update })
</script>
<style lang="stylus">
.c-change-avatar
	display: flex
	flex-direction: column
	.upload-info
		font-size: 12px
		color: rgba(0, 0, 0, 0.6)
		margin: 8px 0
		padding: 8px 12px
		background: rgba(33, 133, 208, 0.08)
		border-left: 3px solid var(--clr-primary, #2185d0)
		border-radius: 2px
		line-height: 1.5
	align-items: center
	.c-identicon
		cursor: pointer
		height: 128px
		width: 128px
	.inputs
		display: flex
		justify-content: center
		align-items: center
		margin-bottom: 16px
		> span
			margin: 0 28px 0 16px
	.btn-randomize
		themed-button-secondary()
	.btn-upload .bunt-button
		themed-button-primary()
	.image-wrapper
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		height: calc(80vh - 230px) // HACK approx. shrinking to avoid top down constraints
		max-height: 320px
		min-height: 160px
		+below('m')
			height: calc(95vh - 230px)
	.file-error
		width: 320px
		height: 320px
		display: flex
		flex-direction: column
		color: $clr-danger
		align-items: center
		justify-content: center
		.mdi
			font-size: 64px
	.cropper
		width: 320px
		height: 320px
		background-color: $clr-grey-900
</style>
