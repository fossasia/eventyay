<template lang="pug">
.language-audio-source-list
	h4(v-if="title") {{ title }}
	.language-url-entry(v-for="(entry, index) in entries" :key="index")
		bunt-select(name="language", v-model="entry.language", :options="languageOptions", label="Language")
		bunt-input(name="youtube_id", v-model="entry.youtube_id", label="Audio Source (YouTube ID or WHEP URL)", @blur="normalizeEntry(entry)")
		bunt-switch(name="use_video", v-model="entry.use_video", label="Use video from this interpretation channel", hint="If enabled, attendees will see both the audio and video from this interpretation channel. If disabled, attendees will hear the interpretation audio while continuing to see the original main video.")
		bunt-icon-button(@click="removeEntry(index)") delete-outline
	bunt-button(@click="addEntry") + Add Language and Audio Source
</template>
<script>
import ISO6391 from 'iso-639-1'
import { defaultLanguageStreamEntry, normalizeLanguageStreamEntry } from 'lib/interpretation-language-streams'

export default {
	name: 'LanguageAudioSourceList',
	props: {
		entries: {
			type: Array,
			required: true,
		},
		title: {
			type: String,
			default: '',
		},
	},
	data() {
		return {
			languageOptions: [],
		}
	},
	created() {
		this.languageOptions = ISO6391.getAllCodes().map(code => ({
			id: ISO6391.getName(code),
			label: ISO6391.getName(code),
		}))
	},
	methods: {
		addEntry() {
			this.entries.push(defaultLanguageStreamEntry())
		},
		removeEntry(index) {
			this.entries.splice(index, 1)
		},
		normalizeEntry(entry) {
			normalizeLanguageStreamEntry(entry)
		},
	},
}
</script>
