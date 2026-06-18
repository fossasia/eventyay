<template lang="pug">
prompt.c-recordings-prompt(@close="$emit('close')")
	.content
		bunt-icon-button#btn-close(@click="$emit('close')") close
		h1 {{ $t('RecordingsPrompt:headline:text') }}
		p {{ $t('RecordingsPrompt:info:text') }}
		bunt-progress-circular(v-if="loading")
		p(v-else-if="error != null") {{ $t('RecordingsPrompt:error:text') }}
		p(v-else-if="recordings.length === 0") {{ $t('RecordingsPrompt:empty:text') }}
		.recordings(v-else)
			.recording(v-for="r in recordings")
				.recording-dates {{ moment(r.start).format('l, LT') }} – {{ moment(r.end).format('LT') }}
				a.link.bunt-button(v-if="r.url && (r.state == 'published' || r.state == 'available')", :href="r.url", target="_blank") {{ $t('RecordingsPrompt:view:label') }}
				a.link.bunt-button(v-if="r.url_screenshare && (r.state == 'published' || r.state == 'available')", :href="r.url_screenshare", target="_blank") {{ $t('RecordingsPrompt:view-screenshare:label') }}
				a.link.bunt-button(v-if="r.url_video && (r.state == 'published' || r.state == 'available')", :href="r.url_video", target="_blank") {{ $t('RecordingsPrompt:view-video:label') }}
				a.link.bunt-button(v-if="r.url_notes && (r.state == 'published' || r.state == 'available')", :href="r.url_notes", target="_blank") {{ $t('RecordingsPrompt:view-notes:label') }}
				span(v-if="!r.url && !r.url_screenshare") {{ r.state }}
</template>
<script>
import api from 'lib/api'
import Prompt from 'components/Prompt'
import moment from 'moment'

export default {
	components: { Prompt },
	props: {
		room: Object
	},
	emits: ['close'],
	data() {
		return {
			recordings: [],
			error: null,
			loading: true,
		}
	},
	computed: {},
	async created() {
		try {
			const response = await api.call('bbb.recordings', {room: this.room.id})
			this.recordings = Array.isArray(response?.results) ? response.results : []
			this.error = null
		} catch (error) {
			this.error = error
			this.recordings = []
			console.error(error)
		} finally {
			this.loading = false
		}
	},
	methods: {
		moment: moment
	}
}
</script>
<style lang="stylus">
.c-recordings-prompt
	.prompt-wrapper
		width: 640px
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		h1
			margin: 0
			text-align: center
		.bunt-progress-circular
			margin: auto
		.recording
			border-bottom: 1px solid #ccc
			display: flex
			justify-content: space-between
			align-items: center
			padding: 8px 0
			.bunt-button
				themed-button-primary()

</style>
