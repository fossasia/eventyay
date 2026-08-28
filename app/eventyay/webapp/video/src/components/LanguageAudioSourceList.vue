<template lang="pug">
.language-audio-source-list
	.list-header(v-if="title")
		.header-title-group
			i.mdi.mdi-translate.header-icon(aria-hidden="true")
			.header-text
				h4 {{ title }}
				p.header-subtitle {{ $t('Add multi-language audio or video interpretation channels for attendees.') }}
		bunt-button.btn-add-entry(@click="addEntry")
			i.mdi.mdi-plus(aria-hidden="true")
			span {{ $t('Add another language') }}

	.empty-state(v-if="entries.length === 0")
		i.mdi.mdi-translate-off(aria-hidden="true")
		p {{ $t('No interpretation channels added yet. Click "Add another language" above to add one.') }}

	.entries-container(v-else)
		.language-url-entry(v-for="(entry, index) in entries" :key="index")
			.entry-header
				.entry-badge
					i.mdi.mdi-web(aria-hidden="true")
					span {{ $t('Channel') }} # {{ index + 1 }}
				button.btn-delete-entry(
					type="button"
					:title="$t('Remove Channel')"
					@click="removeEntry(index)"
				)
					i.mdi.mdi-trash-can-outline(aria-hidden="true")

			.entry-fields-grid
				.field-group.lang-field
					label.field-label
						| {{ $t('Language') }}
						span.required-star *
					.custom-select-wrapper
						i.mdi.mdi-earth.select-icon(aria-hidden="true")
						select.custom-select(v-model="entry.language")
							option(value="" disabled) {{ $t('Select language') }}
							option(v-for="opt in languageOptions" :key="opt.id" :value="opt.id") {{ opt.label }}
						i.mdi.mdi-chevron-down.dropdown-arrow(aria-hidden="true")

				.field-group.source-field
					label.field-label
						| {{ $t('Audio / Video Source (YouTube or WHEP)') }}
						span.required-star *
					.input-wrapper
						input.text-input(
							type="text"
							v-model="entry.url"
							:placeholder="$t('YouTube URL/ID or WHEP endpoint (e.g. https://youtu.be/... or https://.../whep)')"
							@blur="normalizeEntry(entry)"
							@input="syncLegacyField(entry)"
						)

			.entry-switch-row
				bunt-switch(
					name="use_video",
					v-model="entry.use_video",
					:label="$t('Use video from this interpretation channel')",
					:hint="$t('If enabled, attendees see both video and audio from this channel. If disabled, attendees hear the audio while watching the main video.')"
				)
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
		// Ensure entry.url and entry.youtube_id are synced
		for (const entry of this.entries) {
			if (!entry.url && entry.youtube_id) {
				entry.url = entry.youtube_id
			} else if (entry.url && !entry.youtube_id) {
				entry.youtube_id = entry.url
			}
		}
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
		syncLegacyField(entry) {
			entry.youtube_id = entry.url
		}
	},
}
</script>

<style lang="stylus">
.language-audio-source-list
	display: flex
	flex-direction: column
	gap: 16px

	.list-header
		display: flex
		align-items: center
		justify-content: space-between
		flex-wrap: wrap
		gap: 12px
		.header-title-group
			display: flex
			align-items: center
			gap: 10px
			.header-icon
				font-size: 22px
				color: var(--clr-primary)
			.header-text
				h4
					margin: 0
					font-size: 15px
					font-weight: 600
					color: $clr-grey-900
				.header-subtitle
					margin: 2px 0 0 0
					font-size: 13px
					color: $clr-secondary-text-light
		.btn-add-entry
			themed-button-secondary()
			font-size: 13px
			font-weight: 500
			border-radius: 6px
			height: 38px
			display: inline-flex
			align-items: center
			gap: 6px

	.empty-state
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		padding: 24px
		background-color: $clr-grey-50
		border: 1px dashed $clr-grey-300
		border-radius: 8px
		color: $clr-grey-600
		text-align: center
		gap: 6px
		i
			font-size: 28px
			color: $clr-grey-400
		p
			margin: 0
			font-size: 13px

	.entries-container
		display: flex
		flex-direction: column
		gap: 12px

	.language-url-entry
		display: flex
		flex-direction: column
		gap: 14px
		background-color: $clr-white
		border: 1px solid $clr-grey-300
		border-radius: 8px
		padding: 16px
		position: relative
		transition: border-color 0.15s ease, box-shadow 0.15s ease
		&:hover
			border-color: $clr-grey-400

		.entry-header
			display: flex
			align-items: center
			justify-content: space-between
			padding-bottom: 8px
			border-bottom: 1px solid $clr-grey-100
			.entry-badge
				display: inline-flex
				align-items: center
				gap: 6px
				font-size: 13px
				font-weight: 600
				color: $clr-grey-800
				i
					font-size: 16px
					color: var(--clr-primary)
			.btn-delete-entry
				background: transparent
				border: none
				color: $clr-grey-500
				cursor: pointer
				padding: 4px 8px
				border-radius: 4px
				font-size: 18px
				display: inline-flex
				align-items: center
				justify-content: center
				transition: color 0.15s ease, background-color 0.15s ease
				&:hover
					color: $clr-danger
					background-color: rgba($clr-danger, 0.08)

		.entry-fields-grid
			display: grid
			grid-template-columns: 200px 1fr
			gap: 16px
			@media (max-width: 640px)
				grid-template-columns: 1fr

		.field-group
			display: flex
			flex-direction: column
			gap: 6px
			.field-label
				font-size: 13px
				font-weight: 500
				color: $clr-grey-700
				.required-star
					color: $clr-danger

		.custom-select-wrapper
			position: relative
			display: flex
			align-items: center
			background: #ffffff
			border: 1px solid $clr-grey-300
			border-radius: 6px
			height: 40px
			box-sizing: border-box
			&:focus-within
				border-color: var(--clr-primary)
				box-shadow: 0 0 0 2px rgba(187, 0, 17, 0.15)
			.select-icon
				display: flex
				align-items: center
				padding-left: 10px
				color: $clr-grey-500
				font-size: 18px
				pointer-events: none
			.custom-select
				width: 100%
				height: 100%
				padding: 0 32px 0 8px
				border: none
				background: transparent
				font-size: 14px
				font-family: inherit
				color: $clr-grey-800
				cursor: pointer
				outline: none
				appearance: none
			.dropdown-arrow
				position: absolute
				right: 10px
				color: $clr-grey-500
				font-size: 20px
				pointer-events: none

		.input-wrapper
			.text-input
				width: 100%
				height: 40px
				padding: 0 12px
				border: 1px solid $clr-grey-300
				border-radius: 6px
				font-size: 14px
				font-family: inherit
				color: $clr-grey-800
				background: #ffffff
				box-sizing: border-box
				outline: none
				transition: border-color 0.15s ease, box-shadow 0.15s ease
				&:focus
					border-color: var(--clr-primary)
					box-shadow: 0 0 0 2px rgba(187, 0, 17, 0.15)

		.entry-switch-row
			margin-top: 4px
			padding-top: 8px
			border-top: 1px solid $clr-grey-100
			.bunt-switch
				margin: 0
</style>
