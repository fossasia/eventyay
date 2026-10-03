<template lang="pug">
.c-audio-translation(:class="{open: menuOpen}")
	.field-shell(ref="shell")
		span.floating-label {{ resolvedLabel }}
		button.language-toggle(
			ref="toggle",
			type="button",
			:aria-label="resolvedLabel",
			aria-haspopup="listbox",
			:aria-expanded="menuOpen ? 'true' : 'false'",
			:aria-controls="menuId",
			@click="toggleMenu",
			@keydown="onToggleKeydown"
		)
			span.value {{ internalSelectedLanguage }}
			i.mdi.mdi-menu-down(aria-hidden="true")
	teleport(to="body")
		template(v-if="menuOpen")
			.audio-translation-blocker(aria-hidden="true", @click="closeMenu")
			ul.language-menu(
				ref="menu",
				:id="menuId",
				role="listbox",
				:aria-label="resolvedLabel"
			)
				li(
					v-for="(option, index) of languageOptions",
					:key="option.key",
					role="option",
					:aria-selected="index === selectedIndex ? 'true' : 'false'",
					:class="{active: index === selectedIndex, highlight: index === highlightedIndex}",
					@click="selectLanguage(index)",
					@mouseenter="highlightedIndex = index"
				)
					span.language-name {{ option.language }}
					span.stream-type(v-if="option.streamType") {{ option.streamType }}
</template>
<script>
import { createPopper } from '@popperjs/core'
import { normalizeAudioTranslationSource } from 'lib/validators'
import { interpretationStreamType } from '../interpretation-streams'

let dropdownId = 0

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
			selectedIndex: -1,
			languageOptions: [],
			isSyncingSelection: false,
			menuOpen: false,
			highlightedIndex: 0,
			menuId: `audio-translation-menu-${++dropdownId}`,
			popper: null
		}
	},
	computed: {
		resolvedLabel() {
			return this.label || this.$t('Interpretation')
		},
		internalSelectedLanguage() {
			return this.languageOptions[this.selectedIndex]?.language ?? null
		},
	},
	watch: {
		languages: {
			immediate: true,
			handler(newLanguages) {
				this.languageOptions = newLanguages.map((entry, index) => ({
					key: `${index}:${entry.language}:${entry.tts_ws_url || entry.whep_url || entry.whip_url || entry.url || entry.youtube_id || ''}`,
					language: entry.language,
					streamType: this.resolveStreamTypeLabel(entry)
				}))
				this.syncSelectedLanguage()
			}
		},
		selectedLanguage: {
			immediate: true,
			handler() {
				this.syncSelectedLanguage()
			}
		},
		selectedIndex(index) {
			if (this.isSyncingSelection) return
			if (index >= 0) {
				this.sendLanguageChange()
			}
		}
	},
	beforeUnmount() {
		this.destroyPopper()
	},
	methods: {
		resolveStreamTypeLabel(entry) {
			const streamType = interpretationStreamType(entry)
			if (streamType === 'ai') return this.$t('AI')
			if (streamType === 'human') return this.$t('Human')
			return null
		},
		findLanguageIndex(language) {
			return this.languageOptions.findIndex(option => option.language === language)
		},
		syncSelectedLanguage() {
			// Nothing to do when the current pick already matches the parent.
			if (this.internalSelectedLanguage === this.selectedLanguage) return
			let nextIndex = this.findLanguageIndex(this.selectedLanguage)
			if (nextIndex === -1) nextIndex = this.findLanguageIndex('Original')
			if (this.selectedIndex === nextIndex) return
			this.isSyncingSelection = true
			this.selectedIndex = nextIndex
			this.$nextTick(() => {
				this.isSyncingSelection = false
			})
		},
		sendLanguageChange() {
			const selected = this.languages[this.selectedIndex]
			const audioSource = normalizeAudioTranslationSource(selected?.url || selected?.youtube_id)
			const useVideo = selected?.use_video || false

			this.$emit('languageChanged', {
				...(selected || {}),
				url: audioSource,
				useVideo,
				whepUrl: selected?.whep_url || selected?.whip_url || null,
				ttsWsUrl: selected?.tts_ws_url || null
			})
		},
		async toggleMenu() {
			if (this.menuOpen) {
				this.closeMenu()
				return
			}
			this.highlightedIndex = Math.max(this.selectedIndex, 0)
			this.menuOpen = true
			await this.$nextTick()
			if (!this.$refs.shell || !this.$refs.menu) {
				this.menuOpen = false
				return
			}
			try {
				this.popper = createPopper(this.$refs.shell, this.$refs.menu, {
					placement: 'top-start',
					strategy: 'fixed',
					modifiers: [
						{ name: 'offset', options: { offset: [0, 4] } },
						{ name: 'flip', options: { fallbackPlacements: ['bottom-start'] } },
						{ name: 'preventOverflow', options: { padding: 8 } },
						{
							name: 'sameWidth',
							enabled: true,
							phase: 'beforeWrite',
							requires: ['computeStyles'],
							fn: ({ state }) => {
								state.styles.popper.width = `${state.rects.reference.width}px`
							},
							effect: ({ state }) => {
								state.elements.popper.style.width = `${state.elements.reference.offsetWidth}px`
							}
						}
					]
				})
			} catch (error) {
				console.error('Failed to position interpretation language menu', error)
			}
		},
		closeMenu() {
			this.menuOpen = false
			this.destroyPopper()
		},
		destroyPopper() {
			this.popper?.destroy()
			this.popper = null
		},
		selectLanguage(index) {
			if (index < 0 || index >= this.languageOptions.length) return
			this.selectedIndex = index
			this.closeMenu()
		},
		onToggleKeydown(event) {
			if (event.key === 'Escape' && this.menuOpen) {
				event.preventDefault()
				this.closeMenu()
				return
			}
			if (event.key === 'Enter' || event.key === ' ') {
				event.preventDefault()
				if (!this.menuOpen) {
					this.toggleMenu()
					return
				}
				this.selectLanguage(this.highlightedIndex)
				return
			}
			if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
				event.preventDefault()
				if (!this.menuOpen) {
					this.toggleMenu()
					return
				}
				const delta = event.key === 'ArrowDown' ? 1 : -1
				const count = this.languageOptions.length
				if (!count) return
				this.highlightedIndex = (this.highlightedIndex + delta + count) % count
			}
		}
	}
}
</script>
<style lang="stylus">
.c-audio-translation
	position: relative
	display: inline-flex
	align-items: center
	flex: none
	z-index: 1
	&.open
		z-index: 1300
	.field-shell
		position: relative
		display: inline-flex
		align-items: center
		height: 26px
		padding: 0 6px
		min-width: 96px
		border: 1px solid var(--clr-grey-300, #cbd5e1)
		border-radius: 5px
		background: var(--clr-surface, #ffffff)
		color: var(--clr-text-primary, #1e293b)
		box-sizing: border-box
		transition: border-color 0.15s ease, box-shadow 0.15s ease
		&:hover
			border-color: var(--clr-primary, #2185d0)
			box-shadow: 0 0 0 2px var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.12))
	.floating-label
		display: none
	.language-toggle
		display: inline-flex
		align-items: center
		gap: 4px
		margin: 0
		padding: 0
		border: 0
		background: transparent
		color: var(--clr-text-primary, #1e293b)
		font: inherit
		font-size: 11px
		font-weight: 500
		line-height: 16px
		cursor: pointer
		width: 100%
		justify-content: space-between
		.value
			white-space: nowrap
			color: var(--clr-text-primary, #1e293b)
		.mdi-menu-down
			font-size: 16px
			line-height: 16px
			color: var(--clr-text-secondary, #64748b)

ul.language-menu
	position: fixed
	z-index: 1300
	display: flex
	flex-direction: column
	align-items: stretch
	box-sizing: border-box
	margin: 0
	padding: 3px
	list-style: none
	overflow-x: hidden
	overflow-y: auto
	max-height: 200px
	background: var(--clr-surface, #ffffff)
	border: 1px solid var(--clr-grey-300, #cbd5e1)
	border-radius: 5px
	box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12)
	font-family: inherit
	font-size: 11px
	font-weight: 500
	line-height: 16px
	color: var(--clr-text-primary, #1e293b)
	li
		display: flex
		align-items: center
		gap: 6px
		box-sizing: border-box
		margin: 0
		height: 26px
		padding: 0 6px
		list-style: none
		font-size: 11px
		font-weight: 500
		line-height: 26px
		color: var(--clr-text-primary, #1e293b)
		background: transparent
		white-space: nowrap
		overflow: hidden
		text-overflow: ellipsis
		cursor: pointer
		border-radius: 4px
		&:hover,
		&.highlight
			background-color: var(--clr-grey-100, #f1f5f9)
			color: var(--clr-primary, #2185d0)
		&.active
			font-weight: 600
			color: var(--clr-primary, #2185d0)
			background-color: var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.12))
		.language-name
			overflow: hidden
			text-overflow: ellipsis
		.stream-type
			flex: none
			margin-left: auto
			padding: 0 5px
			border-radius: 9px
			background: var(--clr-grey-100, #f1f5f9)
			color: var(--clr-text-secondary, #64748b)
			font-size: 10px
			font-weight: 400
			line-height: 16px

.audio-translation-blocker
	position: fixed
	inset: 0
	z-index: 1298
</style>
