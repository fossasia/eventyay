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
				this.languageOptions = newLanguages.map(entry => entry.language) // Directly assigning the list of languages
			}
		},
		selectedLanguage(newLanguage) {
			if (newLanguage) {
				this.sendLanguageChange()
			}
		}
	},
	methods: {
		sendLanguageChange() {
			const selected = this.languages.find(item => item.language === this.selectedLanguage)
			const youtubeId = selected?.youtube_id || null
			// Accept either raw ID or URL in the language list entries, but emit only a normalized ID or null.
			const normalizedYoutubeId = youtubeId ? normalizeYoutubeVideoId(youtubeId) : null
			this.$emit('languageChanged', normalizedYoutubeId)
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
