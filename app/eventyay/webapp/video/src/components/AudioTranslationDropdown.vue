<template lang="pug">
div.c-audio-translation
		bunt-select(
		:name="selectName",
		v-model="internalSelectedLanguage",
		:options="languageOptions",
		:label="resolvedLabel"
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
		},
		label: {
			type: String,
			default: null
		}
	},
	data() {
		return {
			internalSelectedLanguage: null,
			languageOptions: [],
			isSyncingSelection: false
		}
	},
	computed: {
		selectName() {
			const slug = (this.resolvedLabel || 'audio-translation').toLowerCase().replace(/\s+/g, '-')
			return `audio-translation-${slug}`
		},
		resolvedLabel() {
			return this.label || this.$t('Audio Translation')
		},
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
	flex: 0 1 180px;
	min-width: 140px;
	max-width: 220px;
	padding-top: 3px;
}

@media (max-width: 992px) {
  .c-audio-translation {
    flex: 1 1 140px;
    min-width: 120px;
    max-width: none;
  }
}

.bunt-select {
		width: 100%;
}
</style>
