<template lang="pug">
div.c-audio-translation
		bunt-select(
		name="audio-translation",
		v-model="selectedLanguage",
		:options="languageOptions",
		label="Audio Translation"
)
</template>
<script>
import { normalizeYoutubeVideoId } from 'lib/validators'

export default {
	name: 'AudioTranslationDropdown',
	emits: ['languageChanged'],
	props: {
		languages: {
			type: Array,
			required: true
		}
	},
	data() {
		return {
			selectedLanguage: null, // Selected language for audio translation
			languageOptions: [] // Options for the dropdown
		}
	},
	watch: {
		languages: {
			immediate: true,
			handler(newLanguages) {
				this.languageOptions = newLanguages
					.filter(entry => this.isUsableLanguageEntry(entry))
					.map(entry => entry.language)
				if (!this.languageOptions.includes(this.selectedLanguage)) {
					this.selectedLanguage = this.languageOptions.includes('Original') ? 'Original' : null
				}
			}
		},
		selectedLanguage(newLanguage) {
			if (newLanguage) {
				this.sendLanguageChange()
			}
		}
	},
	methods: {
		isUsableLanguageEntry(entry) {
			if (!entry?.language) return false
			if (entry.language === 'Original') return true
			return !!this.normalizeAudioSource(entry.youtube_id)
		},
		normalizeAudioSource(audioSource) {
			if (!audioSource) return null
			const youtubeId = normalizeYoutubeVideoId(audioSource)
			if (youtubeId) return youtubeId
			try {
				new URL(audioSource)
				return audioSource
			} catch (e) {
				return null
			}
		},
		sendLanguageChange() {
			const selected = this.languages.find(item => item.language === this.selectedLanguage)
			const audioSource = this.normalizeAudioSource(selected?.youtube_id)
			const useVideo = selected?.use_video || false

			this.$emit('languageChanged', { url: audioSource, useVideo })
		}
	}
}
</script>

<style scoped>
.c-audio-translation {
	height: 65px;
	padding-top: 3px;
	margin-right: 5px;
}

@media (max-width: 992px) {
  .c-audio-translation {
    width: 50%;
    margin-right: 5px;
  }
}

.bunt-select {
		width: 100%;
}
</style>
