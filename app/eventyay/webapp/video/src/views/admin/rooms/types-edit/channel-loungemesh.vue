<template lang="pug">
.c-channel-loungemesh-settings
	base-channel-form(
		providerId="loungemesh",
		:title="$t('LoungeMesh Spatial Lounge')",
		:subtitle="$t('Spatial proximity networking and workshop lounge powered by LoungeMesh.')",
		providerIcon="mdi-account-group",
		v-bind="$props"
	)
		bunt-checkbox(name="enable_notes", v-model="module.config.enable_notes", :label="$t('Enable shared collaborative notes')")
		bunt-checkbox(name="enable_whiteboard", v-model="module.config.enable_whiteboard", :label="$t('Enable shared interactive whiteboard')")
		bunt-checkbox(name="enable_spatial_chat", v-model="module.config.enable_spatial_chat", :label="$t('Enable spatial chat')")
		.server-selection-group
			bunt-select(
				name="prefer_server",
				v-model="module.config.prefer_server",
				:label="$t('LoungeMesh Server')",
				:options="serverOptions",
				option-value="id",
				option-label="label"
			)
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
			showAddCustom: false,
			testingServer: false,
			newServerUrl: '',
			newServerSecret: '',
			testMessage: '',
			testSuccess: false
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
				{ id: '', label: this.$t('Auto (event default)') }
			]
			for (const s of this.servers) {
				const scopeLabel = s.scope === 'event' ? this.$t('Event') : s.scope === 'organizer' ? this.$t('Organizer') : this.$t('Global')
				options.push({
					id: s.url,
					label: `${s.url} (${scopeLabel})`,
					raw: s
				})
			}
			if (this.module?.config?.prefer_server && !options.some(o => o.id === this.module.config.prefer_server || o.raw?.id === this.module.config.prefer_server)) {
				options.push({
					id: this.module.config.prefer_server,
					label: `${this.module.config.prefer_server} (${this.$t('Configured')})`
				})
			}
			return options
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
	methods: {
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
			this.testingServer = true
			this.testMessage = ''
			try {
				const created = await api.call('loungemesh.add_server', {
					url: this.newServerUrl.trim(),
					api_secret: this.newServerSecret.trim()
				})
				this.testSuccess = true
				this.testMessage = this.$t('Server added successfully!')
				await this.fetchServers()
				this.module.config.prefer_server = created.url
				setTimeout(() => {
					this.cancelAddCustom()
				}, 1000)
			} catch (e) {
				this.testSuccess = false
				this.testMessage = e.message || this.$t('Connection test failed. Check URL and secret.')
			} finally {
				this.testingServer = false
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
			this.showAddCustom = false
			this.newServerUrl = ''
			this.newServerSecret = ''
			this.testMessage = ''
			this.testSuccess = false
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
	}
}
</script>
<style lang="stylus">
.c-channel-loungemesh-settings
	.server-selection-group
		display: flex
		align-items: center
		gap: 8px
		.bunt-select
			flex: 1
		.btn-delete-server
			margin-top: 16px
	.custom-server-wrapper
		margin-top: 8px
		margin-bottom: 16px
		.btn-toggle-custom
			font-size: 13px
			color: var(--clr-primary, #007bff)
	.custom-server-box
		margin-top: 8px
		padding: 16px
		border: 1px solid var(--clr-border, #e0e0e0)
		border-radius: 6px
		background-color: var(--clr-bg-secondary, #fafafa)
		.box-title
			margin: 0 0 6px 0
			font-size: 15px
			font-weight: 600
		.box-hint
			margin: 0 0 12px 0
			font-size: 12px
			color: var(--clr-text-secondary, #666)
		.box-actions
			display: flex
			gap: 8px
			margin-top: 12px
		.box-status
			margin-top: 10px
			font-size: 13px
			padding: 8px 12px
			border-radius: 4px
			&.status-ok
				background-color: #e8f5e9
				color: #2e7d32
			&.status-err
				background-color: #ffebee
				color: #c62828
</style>
