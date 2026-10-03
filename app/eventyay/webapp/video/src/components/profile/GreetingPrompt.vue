<template lang="pug">
prompt.c-profile-greeting-prompt(:allowCancel="false")
	.content
		.step-display-name(v-if="activeStep === 'displayName'")
			h1 {{ $t('Hi there!') }}
			p {{ $t('Before you join others in this event, please set up your profile. We will show your name to other attendees if you interact with them, e.g. in a chat. You do not need to use your real name.') }}
			bunt-input.display-name(name="displayName", :label="`${$t('Display name')} *`", v-model.trim="profile.display_name", :validation="v$.profile.display_name")
		.step-display-language(v-else-if="activeStep === 'displayLanguage'")
			h2 {{ $t('Interface Language') }}
			p {{ $t('Please select your language. You can change it later in your profile.') }}
			bunt-select#select-interface-language(name="interface-language", v-model="interfaceLanguage", :options="languages", option-value="code", option-label="nativeLabel")
		.actions
			bunt-button#btn-back(v-if="previousStep", @click="activeStep = previousStep") {{ $t('back') }}
			bunt-button#btn-continue(v-if="nextStep", :class="{invalid: v$.$invalid && v$.$dirty}", :disabled="v$.$invalid && v$.$dirty", :key="activeStep", @click="toNextStep") {{ $t('continue') }}
			bunt-button#btn-finish(v-else, :class="{invalid: v$.$invalid && v$.$dirty}", :loading="saving", :disabled="v$.$invalid && v$.$dirty", @click="update") {{ $t('finish') }}
</template>
<script>
import { useVuelidate } from '@vuelidate/core'
import { mapState } from 'vuex'
import { required } from 'lib/validators'
import config from 'config'
import { resolveLanguageOptions } from 'locales'
import Prompt from 'components/Prompt'

export default {
	components: { Prompt },
	emits: ['close'],
	setup:() => ({v$:useVuelidate()}),
	data() {
		return {
			activeStep: null,
			profile: null,
			saving: false,
			interfaceLanguage: this.$i18n.resolvedLanguage,
		}
	},
	validations() {
		if (!this.profile) return {}
		return {
			profile: {
				display_name: {
					required: required(this.$t('Display name cannot be empty'))
				}
			}
		}
	},
	computed: {
		...mapState(['user', 'world']),
		steps() {
			return [
				'displayName',
				'displayLanguage'
			]
		},
		previousStep() {
			return this.steps[this.steps.indexOf(this.activeStep) - 1]
		},
		nextStep() {
			return this.steps[this.steps.indexOf(this.activeStep) + 1]
		},
		languages() {
			const options = resolveLanguageOptions(config.locales)
			return options.length ? options : null
		}
	},
	async created() {
		this.activeStep = this.steps[0]
		// Determine default display name:
		// 1. Use existing saved display_name if available (even if empty string)
		// 2. Otherwise, use wikimedia_username if available
		// 3. Otherwise, leave empty
		let defaultDisplayName = ''
		if (this.user.profile?.display_name != null) {
			defaultDisplayName = this.user.profile.display_name
		} else if (this.user.wikimedia_username) {
			defaultDisplayName = this.user.wikimedia_username
		}

		// Build profile object, preserving computed display_name
		this.profile = {
			greeted: true,
			fields: this.user.profile?.fields || {},
			...this.user.profile,
			display_name: defaultDisplayName
		}
	},
	methods: {
		async toNextStep() {
			this.v$.$touch()
			if (this.v$.$invalid) return
			this.activeStep = this.nextStep
		},
		async update() {
			this.v$.$touch()
			if (this.v$.$invalid) {
				if (this.v$.profile?.display_name?.$invalid) this.activeStep = 'displayName'
				return
			}
			this.saving = true
			this.profile.greeted = true // override even if explicitly set to false by server
			await this.$store.dispatch('updateUser', {profile: this.profile})
			await this.$store.dispatch('updateUserLocale', this.interfaceLanguage)
			// TODO error handling
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-profile-greeting-prompt
	.content
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		position: relative
		padding: 16px
		min-height: 0
		h1
			margin: 8px 0
			text-align: center
		p
			margin: 0 0 8px 0
			width: 360px
			white-space: pre-wrap
		.step-display-name, .step-display-language
			display: flex
			flex-direction: column
			align-items: center
			flex: 1 1 auto
			min-height: 0
			overflow-y: auto
			width: 100%
		.display-name
			max-width: 280px
			margin-top: 16px
		.actions
			margin-top: 32px
			align-self: stretch
			display: flex
			justify-content: flex-end
			flex-shrink: 0
		#btn-back
			themed-button-secondary()
			margin-right: 8px
		#btn-continue, #btn-finish
			themed-button-primary()
			&.invalid
				button-style(color: $clr-danger)
		+below('m')
			p
				width: auto
</style>
