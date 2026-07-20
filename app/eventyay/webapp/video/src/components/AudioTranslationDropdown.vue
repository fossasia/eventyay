<template lang="pug">
div.c-audio-translation
		bunt-select(
		name="audio-translation",
		v-model="internalSelectedLanguage",
		:options="languageOptions",
		label="Audio Translation"
)
</template>
<script>
import { normalizeAudioTranslationSource } from 'lib/validators'

export default {
	name: 'AudioTranslationDropdown',
	emits: ['languageChanged'],
	props: {
		languages: {
			type: Array,
			required: true
		},
		selectedLanguage: {
			type: String,
			default: 'Original'
		}
	},
	data() {
		return {
			internalSelectedLanguage: null,
			languageOptions: [],
			isSyncingSelection: false
		}
	},
	watch: {
		languages: {
			immediate: true,
			handler(newLanguages) {
				this.languageOptions = newLanguages.map(entry => entry.language)
				this.syncSelectedLanguage()
			}
		},
		selectedLanguage: {
			immediate: true,
			handler() {
				this.syncSelectedLanguage()
			}
		},
		internalSelectedLanguage(newLanguage) {
			if (this.isSyncingSelection) return
			if (newLanguage) {
				this.sendLanguageChange()
			}
		}
	},
	methods: {
		syncSelectedLanguage() {
			const fallback = this.languageOptions.includes('Original') ? 'Original' : null
			const nextLanguage = this.languageOptions.includes(this.selectedLanguage) ? this.selectedLanguage : fallback
			if (this.internalSelectedLanguage === nextLanguage) return
			this.isSyncingSelection = true
			this.internalSelectedLanguage = nextLanguage
			this.$nextTick(() => {
				this.isSyncingSelection = false
			})
		},
		sendLanguageChange() {
			const selected = this.languages.find(item => item.language === this.internalSelectedLanguage)
			const audioSource = normalizeAudioTranslationSource(selected?.youtube_id)
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
