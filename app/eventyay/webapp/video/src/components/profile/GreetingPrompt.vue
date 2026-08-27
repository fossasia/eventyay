<template lang="pug">
prompt.c-profile-greeting-prompt(:allowCancel="false")
	.content
		connect-gravatar(v-if="showConnectGravatar", @change="setGravatar", @close="showConnectGravatar = false")
		.step-connect-social(v-else-if="activeStep === 'connectSocial'")
			h1 {{ $t('Hi there!') }}
			p {{ $t('Before you join others in this event, please set up your profile. We can get your profile information from one of your social media accounts, or you can fill in your profile by hand.') }}
			bunt-button.social-connection.social-twitter(v-if="world.social_logins.includes('twitter')", @click="connectSocial('twitter')")
				.mdi.mdi-twitter
				.label {{ $t('Twitter') }}
			bunt-button.social-connection.social-linkedin(v-if="world.social_logins.includes('linkedin')", @click="connectSocial('linkedin')")
				.mdi.mdi-linkedin
				.label {{ $t('LinkedIn') }}
			bunt-button.social-connection.social-gravatar(v-if="world.social_logins.includes('gravatar')",@click="showConnectGravatar = true")
				svg(viewBox="0 0 27 27")
					path(d="M10.8 2.699v9.45a2.699 2.699 0 005.398 0V5.862a8.101 8.101 0 11-8.423 1.913 2.702 2.702 0 00-3.821-3.821A13.5 13.5 0 1013.499 0 2.699 2.699 0 0010.8 2.699z")
				.label {{ $t('Gravatar') }}
			p.joiner {{ $t('or') }}
			bunt-button.manual(@click="activeStep = 'displayName'") {{ $t('Fill manually') }}
		.step-display-name(v-else-if="activeStep === 'displayName'")
			template(v-if="steps.includes('connectSocial')")
				h1 {{ $t('What are you called?') }}
				p {{ $t('We will show your name to other attendees if you interact with them, e.g. in a chat. You do not need to use your real name.') }}
			template(v-else)
				h1 {{ $t('Hi there!') }}
				p {{ $t('Before you join others in this event, please set up your profile. We will show your name to other attendees if you interact with them, e.g. in a chat. You do not need to use your real name. After this, you can optionally choose a picture.') }}
			bunt-input.display-name(name="displayName", :label="`${$t('Display name')} *`", v-model.trim="profile.display_name", :validation="v$.profile.display_name")
		.step-avatar(v-else-if="activeStep === 'avatar'")
			h1 {{ $t('Choose your look') }}
			p {{ $t('Pick an identicon or upload a picture.') }}
			change-avatar(ref="step", v-model="profile.avatar", :profile="profile", @blockSave="blockSave = $event")
		.step-display-language(v-else-if="activeStep === 'displayLanguage'")
			h2 {{ $t('Interface Language') }}
			p {{ $t('Please select your language. You can change it later in your profile.') }}
			bunt-select#select-interface-language(name="interface-language", v-model="interfaceLanguage", :options="languages", option-value="code", option-label="nativeLabel")
		.step-additional-fields(v-else-if="activeStep === 'additionalFields'")
			h1 {{ $t('Additional information') }}
			p {{ $t("And lastly, why not add some optional information to your profile? Don't worry, you can always edit anything in your profile later.") }}
			change-additional-fields(v-model="profile.fields")
		.actions(v-if="activeStep !== 'connectSocial' && !showConnectGravatar")
			bunt-button#btn-back(v-if="previousStep", @click="activeStep = previousStep") {{ $t('back') }}
			bunt-button#btn-continue(v-if="nextStep", :class="{invalid: v$.$invalid && v$.$dirty}", :disabled="blockSave || v$.$invalid && v$.$dirty", :loading="processingStep", :key="activeStep", @click="toNextStep") {{ $t('continue') }}
			bunt-button#btn-finish(v-else, :class="{invalid: v$.$invalid && v$.$dirty}", :loading="saving", :disabled="blockSave || v$.$invalid && v$.$dirty", @click="update") {{ $t('finish') }}
</template>
<script>
import { useVuelidate } from '@vuelidate/core'
import { mapState } from 'vuex'
import { required } from 'lib/validators'
import api from 'lib/api'
import config from 'config'
import { resolveLanguageOptions } from 'locales'
import Prompt from 'components/Prompt'
import ChangeAvatar from './ChangeAvatar'
import ChangeAdditionalFields from './ChangeAdditionalFields'
import ConnectGravatar from './ConnectGravatar'

export default {
	components: { Prompt, ChangeAvatar, ChangeAdditionalFields, ConnectGravatar },
	emits: ['close'],
	setup:() => ({v$:useVuelidate()}),
	data() {
		return {
			activeStep: null,
			showConnectGravatar: false,
			profile: null,
			processingStep: false,
			blockSave: false,
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
			const steps = [
				'displayName',
				'displayLanguage',
				'avatar'
			]
			if (this.world?.social_logins?.length) steps.unshift('connectSocial')
			if (this.world?.profile_fields?.length) steps.push('additionalFields')
			return steps
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
			avatar: this.user.profile?.avatar || {
				identicon: this.user.id
			},
			fields: this.user.profile?.fields || {},
			...this.user.profile,
			display_name: defaultDisplayName
		}

		// assume that when avatar url is set the social connection happened and skip first step
		if (this.activeStep === 'connectSocial' && this.profile.avatar.url) this.activeStep = this.nextStep
	},
	methods: {
		async toNextStep() {
			this.v$.$touch()
			if (this.v$.$invalid) return
			if (this.$refs.step?.update) {
				this.processingStep = true
				await this.$refs.step.update()
				this.processingStep = false
			}
			this.activeStep = this.nextStep
		},
		async connectSocial(network) {
			const { url } = await api.call('user.social.connect', {
				network,
				return_url: window.location.href
			})
			window.location = url
		},
		setGravatar(gravatar) {
			Object.assign(this.profile, gravatar)
			this.showConnectGravatar = false
			this.activeStep = this.nextStep
		},
		async update() {
			this.v$.$touch()
			if (this.v$.$invalid) {
				if (this.v$.profile?.display_name?.$invalid) this.activeStep = 'displayName'
				return
			}
			this.saving = true
			if (this.$refs.step?.update) {
				await this.$refs.step.update()
			}
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
		.step-connect-social, .step-display-name, .step-avatar, .step-display-language, .step-additional-fields
			display: flex
			flex-direction: column
			align-items: center
			flex: 1 1 auto
			min-height: 0
			overflow-y: auto
			width: 100%
		.step-connect-social
			margin-bottom: 16px
			.social-connection
				// margin-bottom: 8px
				.bunt-button-text
					display: flex
					align-items: center
					.mdi
						margin-right: 8px
						font-size: 24px
					.label
						width: 72px
			.social-twitter
				button-style(style: clear, color: #1DA1F2)
			.social-linkedin
				button-style(style: clear, color: #0A66C2)
			.social-gravatar
				button-style(style: clear, color: #4678eb)
				svg
					width: 20px
					margin: 0 12px 0 4px
					path
						fill: #4678eb
			.joiner
				text-align: center
			.manual
				themed-button-secondary()
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
