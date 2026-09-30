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
					v-for="(language, index) of languageOptions",
					:key="language",
					role="option",
					:aria-selected="language === internalSelectedLanguage ? 'true' : 'false'",
					:class="{active: language === internalSelectedLanguage, highlight: index === highlightedIndex}",
					@click="selectLanguage(language)",
					@mouseenter="highlightedIndex = index"
				) {{ language }}
</template>
<script>
import { createPopper } from '@popperjs/core'
import { normalizeAudioTranslationSource } from 'lib/validators'

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
			internalSelectedLanguage: null,
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
	beforeUnmount() {
		this.destroyPopper()
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
			const audioSource = normalizeAudioTranslationSource(selected?.url || selected?.youtube_id)
			const useVideo = selected?.use_video || false

			this.$emit('languageChanged', { ...(selected || {}), url: audioSource, useVideo })
		},
		async toggleMenu() {
			if (this.menuOpen) {
				this.closeMenu()
				return
			}
			this.highlightedIndex = Math.max(this.languageOptions.indexOf(this.internalSelectedLanguage), 0)
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
		selectLanguage(language) {
			this.internalSelectedLanguage = language
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
				const language = this.languageOptions[this.highlightedIndex]
				if (language) this.selectLanguage(language)
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
		display: block
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

.audio-translation-blocker
	position: fixed
	inset: 0
	z-index: 1298
</style>
