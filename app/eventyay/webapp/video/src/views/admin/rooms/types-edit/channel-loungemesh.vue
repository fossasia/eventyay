<template lang="pug">
.c-channel-loungemesh-settings
	base-channel-form(
		providerId="loungemesh",
		:title="$t('LoungeMesh Spatial Lounge')",
		:subtitle="$t('Spatial proximity networking and workshop lounge powered by LoungeMesh.')",
		v-bind="$props"
	)
		template(#icon)
			svg.loungemesh-brand-icon(viewBox="0 0 48 48", fill="none", aria-hidden="true")
				defs
					linearGradient#lm-brand-grad(x1="8", y1="8", x2="40", y2="40", gradientUnits="userSpaceOnUse")
						stop(stop-color="#4f6ef7")
						stop(offset="1", stop-color="#7b93ff")
				rect(x="4", y="4", width="40", height="40", rx="12", fill="url(#lm-brand-grad)")
				circle(cx="18", cy="22", r="7", fill="#fff", opacity="0.95")
				circle(cx="30", cy="22", r="7", fill="#fff", opacity="0.75")
				path(d="M12 34c4 3 8 4 12 4s8-1 12-4", stroke="#fff", stroke-width="2.5", stroke-linecap="round", opacity="0.9")

		bunt-checkbox(name="enable_notes", v-model="module.config.enable_notes", :label="$t('Enable shared collaborative notes')")
		bunt-checkbox(name="enable_whiteboard", v-model="module.config.enable_whiteboard", :label="$t('Enable shared interactive whiteboard')")
		bunt-checkbox(name="enable_spatial_chat", v-model="module.config.enable_spatial_chat", :label="$t('Enable spatial chat')")

		.server-selection-group(ref="serverDropdownRef")
			.field-group
				label.field-label {{ $t('LoungeMesh Server') }}
				.custom-server-dropdown(:class="{ 'is-open': serverDropdownOpen }")
					button.dropdown-trigger(
						type="button",
						@click.stop="toggleServerDropdown",
						:aria-expanded="String(serverDropdownOpen)",
						aria-haspopup="listbox"
					)
						.trigger-content
							i.mdi.server-type-icon(:class="currentServerOption.isAuto ? 'mdi-auto-fix' : 'mdi-server-network'")
							span.server-name {{ currentServerOption.title }}
							span.scope-pill(:class="`scope-${currentServerOption.scope}`", v-if="!currentServerOption.isAuto") {{ currentServerOption.scopeLabel }}
						i.mdi.mdi-chevron-down.dropdown-chevron(:class="{ 'is-open': serverDropdownOpen }")

					transition(name="fade-dropdown")
						.dropdown-popover(v-if="serverDropdownOpen", role="listbox")
							.dropdown-option(
								v-for="opt in serverOptions",
								:key="opt.id",
								:class="{ 'is-active': opt.id === (module.config.prefer_server || '') }",
								role="option",
								:aria-selected="String(opt.id === (module.config.prefer_server || ''))",
								@click.stop="selectServer(opt)"
							)
								.option-content
									i.mdi.option-icon(:class="opt.isAuto ? 'mdi-auto-fix' : 'mdi-server-network'")
									span.option-title {{ opt.title }}
									span.scope-pill(:class="`scope-${opt.scope}`", v-if="!opt.isAuto") {{ opt.scopeLabel }}
								i.mdi.mdi-check.option-check(v-if="opt.id === (module.config.prefer_server || '')")
			bunt-button.btn-delete-server(
				v-if="selectedServer && selectedServer.is_custom",
				icon="delete",
				:tooltip="$t('Delete this custom server')",
				@click="deleteCustomServer(selectedServer)"
			)

		.custom-server-wrapper
			bunt-button.btn-toggle-custom(
				v-if="!showAddCustom",
				@click="showAddCustom = true"
			) {{ $t('+ Add custom server for this event') }}
			.custom-server-box(v-else)
				h4.box-title {{ $t('Add Custom LoungeMesh Server') }}
				p.box-hint {{ $t('Enter the LoungeMesh server URL and EVENTYAY_SERVICE_SECRET. The connection will be tested before saving.') }}
				bunt-input(
					name="custom_server_url",
					v-model="newServerUrl",
					:label="$t('Server URL (e.g. https://loungemesh.example.com)')"
				)
				bunt-input(
					name="custom_server_secret",
					v-model="newServerSecret",
					type="password",
					:label="$t('Service Secret (EVENTYAY_SERVICE_SECRET)')"
				)
				.box-actions
					bunt-button.btn-test-save(
						:loading="testingServer",
						@click="testAndAddServer"
					) {{ $t('Test & Save') }}
					bunt-button.btn-cancel(
						@click="cancelAddCustom"
					) {{ $t('Cancel') }}
				.box-status(:class="testSuccess ? 'status-ok' : 'status-err'", v-if="testMessage")
					| {{ testMessage }}
</template>
<script>
import api from 'lib/api'
import BaseChannelForm from './BaseChannelForm'
import mixin from './mixin'

export default {
	components: { BaseChannelForm },
	mixins: [mixin],
	data() {
		return {
			servers: [],
			loadingServers: false,
			serverDropdownOpen: false,
			showAddCustom: false,
			testingServer: false,
			newServerUrl: '',
			newServerSecret: '',
			testMessage: '',
			testSuccess: false,
			addOperationId: 0,
			cancelTimeout: null
		}
	},
	computed: {
		module() {
			if (!this.modules['call.loungemesh']) {
				this.addModule('call.loungemesh', {
					prefer_server: '',
					enable_notes: true,
					enable_whiteboard: true,
					enable_spatial_chat: true
				})
			}
			return this.modules['call.loungemesh']
		},
		serverOptions() {
			const options = [
				{
					id: '',
					title: this.$t('Auto (event default)'),
					scope: 'auto',
					scopeLabel: this.$t('Default'),
					isAuto: true
				}
			]
			for (const s of this.servers) {
				const scopeLabel = s.scope === 'event'
					? this.$t('Event')
					: s.scope === 'organizer'
						? this.$t('Organizer')
						: this.$t('Global')
				options.push({
					id: s.url,
					title: s.url,
					scope: s.scope || 'global',
					scopeLabel,
					raw: s
				})
			}
			if (this.module?.config?.prefer_server && !options.some(o => o.id === this.module.config.prefer_server || o.raw?.id === this.module.config.prefer_server)) {
				options.push({
					id: this.module.config.prefer_server,
					title: this.module.config.prefer_server,
					scope: 'configured',
					scopeLabel: this.$t('Configured')
				})
			}
			return options
		},
		currentServerOption() {
			const val = this.module?.config?.prefer_server || ''
			return this.serverOptions.find(o => o.id === val || o.raw?.id === val) || this.serverOptions[0]
		},
		selectedServer() {
			const val = this.module?.config?.prefer_server
			if (!val) return null
			return this.servers.find(s => s.url === val || s.id === val)
		}
	},
	async created() {
		if (this.module) {
			const cfg = this.module.config || {}
			const features = cfg.features || {}
			const notes = typeof cfg.enable_notes === 'boolean' ? cfg.enable_notes : (typeof features.notes === 'boolean' ? features.notes : true)
			const whiteboard = typeof cfg.enable_whiteboard === 'boolean' ? cfg.enable_whiteboard : (typeof features.whiteboard === 'boolean' ? features.whiteboard : true)
			const spatialChat = typeof cfg.enable_spatial_chat === 'boolean' ? cfg.enable_spatial_chat : (typeof features.spatial_chat === 'boolean' ? features.spatial_chat : true)

			this.module.config = {
				prefer_server: '',
				enable_notes: notes,
				enable_whiteboard: whiteboard,
				enable_spatial_chat: spatialChat,
				...cfg,
				features: {
					notes,
					whiteboard,
					spatial_chat: spatialChat,
					...features,
				}
			}
		}
		await this.fetchServers()
	},
	mounted() {
		document.addEventListener('click', this.handleDocumentClick)
	},
	methods: {
		toggleServerDropdown() {
			this.serverDropdownOpen = !this.serverDropdownOpen
		},
		selectServer(opt) {
			if (this.module?.config) {
				this.module.config.prefer_server = opt.id
			}
			this.serverDropdownOpen = false
		},
		handleDocumentClick(e) {
			if (this.serverDropdownOpen && this.$refs.serverDropdownRef && !this.$refs.serverDropdownRef.contains(e.target)) {
				this.serverDropdownOpen = false
			}
		},
		async fetchServers() {
			this.loadingServers = true
			try {
				const res = await api.call('loungemesh.servers')
				this.servers = res.servers || []
			} catch (e) {
				console.warn('Failed to fetch LoungeMesh servers:', e)
			} finally {
				this.loadingServers = false
			}
		},
		async testAndAddServer() {
			if (!this.newServerUrl.trim() || !this.newServerSecret.trim()) {
				this.testSuccess = false
				this.testMessage = this.$t('Server URL and service secret are required.')
				return
			}
			const opId = ++this.addOperationId
			this.testingServer = true
			this.testMessage = ''
			try {
				const created = await api.call('loungemesh.add_server', {
					url: this.newServerUrl.trim(),
					api_secret: this.newServerSecret.trim()
				})
				if (this.addOperationId !== opId || !this.showAddCustom) return
				this.testSuccess = true
				this.testMessage = this.$t('Server added successfully!')
				await this.fetchServers()
				if (this.addOperationId !== opId || !this.showAddCustom) return
				if (this.module?.config) {
					this.module.config.prefer_server = created.url
				}
				this.serverDropdownOpen = false
				if (this.cancelTimeout) clearTimeout(this.cancelTimeout)
				this.cancelTimeout = setTimeout(() => {
					if (this.addOperationId === opId) {
						this.cancelAddCustom()
					}
				}, 1000)
			} catch (e) {
				if (this.addOperationId !== opId) return
				this.testSuccess = false
				this.testMessage = e.message || this.$t('Connection test failed. Check URL and secret.')
			} finally {
				if (this.addOperationId === opId) {
					this.testingServer = false
				}
			}
		},
		async deleteCustomServer(server) {
			if (!confirm(this.$t('Are you sure you want to remove this custom server?'))) return
			try {
				await api.call('loungemesh.delete_server', { server_id: server.id })
				if (this.module.config.prefer_server === server.url || this.module.config.prefer_server === server.id) {
					this.module.config.prefer_server = ''
				}
				await this.fetchServers()
			} catch (e) {
				alert(e.message || this.$t('Failed to delete server.'))
			}
		},
		cancelAddCustom() {
			this.addOperationId++
			if (this.cancelTimeout) {
				clearTimeout(this.cancelTimeout)
				this.cancelTimeout = null
			}
			this.showAddCustom = false
			this.newServerUrl = ''
			this.newServerSecret = ''
			this.testMessage = ''
			this.testSuccess = false
			this.testingServer = false
		},
		beforeSave() {
			if (this.module?.config) {
				const cfg = this.module.config
				cfg.features = {
					...(cfg.features || {}),
					notes: Boolean(cfg.enable_notes),
					whiteboard: Boolean(cfg.enable_whiteboard),
					spatial_chat: Boolean(cfg.enable_spatial_chat),
				}
			}
		}
	},
	beforeUnmount() {
		document.removeEventListener('click', this.handleDocumentClick)
		this.addOperationId++
		if (this.cancelTimeout) {
			clearTimeout(this.cancelTimeout)
			this.cancelTimeout = null
		}
	}
}
</script>
<style lang="stylus">
.c-channel-loungemesh-settings
	.server-selection-group
		display: flex
		align-items: flex-end
		gap: 10px
		margin-top: 14px
		margin-bottom: 10px
		position: relative

		.field-group
			flex: 1
			display: flex
			flex-direction: column
			position: relative

			.field-label
				font-size: 13px
				font-weight: 600
				color: $clr-grey-800
				margin-bottom: 6px

			.custom-server-dropdown
				position: relative
				width: 100%

				.dropdown-trigger
					width: 100%
					height: 44px
					display: flex
					align-items: center
					justify-content: space-between
					padding: 0 14px
					background: #ffffff
					border: 1px solid $clr-grey-300
					border-radius: 6px
					box-sizing: border-box
					cursor: pointer
					outline: none
					transition: border-color 0.15s ease, box-shadow 0.15s ease
					text-align: left

					&:hover
						background-color: $clr-grey-50
						border-color: $clr-grey-400

					&:focus,
					&.is-open
						border-color: var(--clr-primary, #2185d0)
						box-shadow: 0 0 0 2px var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.15))

					.trigger-content
						display: flex
						align-items: center
						gap: 10px
						overflow: hidden

						.server-type-icon
							font-size: 20px
							color: var(--clr-primary, #2185d0)
							flex-shrink: 0

						.server-name
							font-size: 14px
							font-weight: 500
							color: $clr-grey-900
							white-space: nowrap
							overflow: hidden
							text-overflow: ellipsis

					.dropdown-chevron
						font-size: 20px
						color: $clr-grey-600
						transition: transform 0.2s ease
						flex-shrink: 0
						margin-left: 8px

						&.is-open
							transform: rotate(180deg)
							color: var(--clr-primary, #2185d0)

				.dropdown-popover
					position: absolute
					top: calc(100% + 6px)
					left: 0
					right: 0
					background: #ffffff
					border: 1px solid $clr-grey-200
					border-radius: 8px
					box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1)
					padding: 6px
					max-height: 250px
					overflow-y: auto
					z-index: 100

					.dropdown-option
						display: flex
						align-items: center
						justify-content: space-between
						padding: 9px 12px
						border-radius: 6px
						cursor: pointer
						transition: background-color 0.12s ease
						user-select: none

						&:hover
							background-color: $clr-grey-100

						&.is-active
							background-color: var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.12))
							.option-title
								color: var(--clr-primary, #2185d0)
								font-weight: 600
							.option-icon
								color: var(--clr-primary, #2185d0)

						.option-content
							display: flex
							align-items: center
							gap: 10px
							overflow: hidden

							.option-icon
								font-size: 18px
								color: $clr-grey-600
								flex-shrink: 0

							.option-title
								font-size: 13.5px
								color: $clr-grey-800
								white-space: nowrap
								overflow: hidden
								text-overflow: ellipsis

						.option-check
							font-size: 18px
							color: var(--clr-primary, #2185d0)
							flex-shrink: 0
							margin-left: 8px

		.scope-pill
			font-size: 11px
			font-weight: 600
			padding: 2px 8px
			border-radius: 12px
			text-transform: uppercase
			letter-spacing: 0.03em
			flex-shrink: 0

			&.scope-global
				background-color: var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.12))
				color: var(--clr-primary, #2185d0)
				border: 1px solid var(--clr-primary-alpha-30, rgba(33, 133, 208, 0.25))

			&.scope-event
				background-color: rgba(#4caf50, 0.12)
				color: #2e7d32
				border: 1px solid rgba(#4caf50, 0.3)

			&.scope-organizer
				background-color: $clr-grey-100
				color: $clr-grey-800
				border: 1px solid $clr-grey-300

			&.scope-configured
				background-color: rgba(#ff9800, 0.12)
				color: #e65100
				border: 1px solid rgba(#ff9800, 0.3)

		.btn-delete-server
			margin-bottom: 2px
			height: 44px
			width: 44px
			flex-shrink: 0

	.custom-server-wrapper
		margin-top: 8px
		margin-bottom: 16px
		.btn-toggle-custom
			themed-button-secondary()
			font-size: 13px
			font-weight: 600
			color: var(--clr-primary, #2185d0)
			&:hover
				color: var(--clr-primary-darken-15, #1a6fad)

	.custom-server-box
		margin-top: 8px
		padding: 16px
		border: 1px solid $clr-grey-200
		border-radius: 8px
		background-color: $clr-grey-50
		.box-title
			margin: 0 0 6px 0
			font-size: 15px
			font-weight: 600
			color: $clr-grey-900
		.box-hint
			margin: 0 0 12px 0
			font-size: 12px
			color: $clr-secondary-text-light
		.box-actions
			display: flex
			gap: 8px
			margin-top: 12px
			.btn-test-save
				themed-button-primary()
			.btn-cancel
				themed-button-secondary()
		.box-status
			margin-top: 10px
			font-size: 13px
			padding: 8px 12px
			border-radius: 6px
			&.status-ok
				background-color: rgba(#4caf50, 0.12)
				color: #2e7d32
				border: 1px solid rgba(#4caf50, 0.3)
			&.status-err
				background-color: rgba(#f44336, 0.12)
				color: #c62828
				border: 1px solid rgba(#f44336, 0.3)
</style>
