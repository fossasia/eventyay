<template lang="pug">
.c-video-admin
	.ui-page-header
		h1 Video Admin
	scrollbars(y, v-if="!isAdminMode")
		.denied
			h2 Access denied
			p This area is only available in Video admin mode.
	.video-admin-layout(v-else)
		aside.video-admin-sidebar(aria-label="Video admin settings")
			a(v-for="item in navItems", :key="item.path", :href="item.href", :class="{active: activePath === item.path}", @click.prevent="open(item.path)") {{ item.label }}
		.video-admin-frame-wrap(:class="{loading: !frameReady}")
			.loading-indicator(v-if="!frameReady") Loading...
			iframe.video-admin-frame(ref="frame", :class="{ready: frameReady}", :src="frameSrc", title="Video Admin", @load="prepareFrame")
</template>
<script>
const ADMIN_BASE = '/admin/video/'
const ADMIN_SECTIONS = [
	{ label: 'Dashboard', path: '' },
	{ label: 'Events', path: 'events/' },
	{ label: 'BBB servers', path: 'bbbs/' },
	{ label: 'Move BBB room', path: 'bbbs/moveroom/' },
	{ label: 'Janus servers', path: 'janus/' },
	{ label: 'Jitsi servers', path: 'jitsi/' },
	{ label: 'TURN servers', path: 'turns/' },
	{ label: 'Streaming servers', path: 'streamingservers/' },
	{ label: 'Stream keys', path: 'streamkey/' },
	{ label: 'System logs', path: 'systemlog/' },
	{ label: 'Conftool posters', path: 'conftool/syncposters/' },
	{ label: 'Profile', path: 'auth/profile/' }
]
const ADMIN_PATHS = new Set(ADMIN_SECTIONS.map(item => item.path))

export default {
	name: 'VideoAdminConfig',
	data() {
		return {
			activePath: '',
			frameReady: false,
			frameWindow: null
		}
	},
	computed: {
		isAdminMode() {
			return this.$store.getters.isAdminMode
		},
		navItems() {
			return ADMIN_SECTIONS.map(item => ({
				...item,
				href: this.adminUrl(item.path)
			}))
		},
		frameSrc() {
			return this.adminUrl(this.activePath)
		}
	},
	created() {
		this.activePath = this.normalizedPath(this.$route.query.admin_path)
	},
	beforeUnmount() {
		this.removeFrameBeforeUnloadListener()
	},
	watch: {
		'$route.query.admin_path'(path) {
			this.activePath = this.normalizedPath(path)
			this.frameReady = false
		}
	},
	methods: {
		normalizedPath(path) {
			if (!path || typeof path !== 'string') return ''
			const normalized = path.replace(/^\/+/, '').replace(/^admin\/video\/?/, '')
			return ADMIN_PATHS.has(normalized) ? normalized : ''
		},
		adminUrl(path) {
			const url = new URL(`${ADMIN_BASE}${this.normalizedPath(path)}`, window.location.origin)
			url.searchParams.set('embedded', '1')
			return `${url.pathname}${url.search}`
		},
		open(path) {
			const nextPath = this.normalizedPath(path)
			if (nextPath === this.activePath) {
				this.frameReady = false
				this.$refs.frame.src = this.adminUrl(nextPath)
				return
			}
			this.activePath = nextPath
			this.frameReady = false
			this.$router.replace({
				name: 'admin:video-admin',
				query: this.activePath ? { admin_path: this.activePath } : {}
			})
		},
		prepareFrame() {
			const frame = this.$refs.frame
			const doc = frame?.contentDocument
			if (!doc || !doc.location.pathname.startsWith(ADMIN_BASE)) {
				this.frameReady = true
				return
			}

			this.addFrameBeforeUnloadListener(doc.defaultView)

			if (!doc.getElementById('video-admin-embedded-style')) {
				const style = doc.createElement('style')
				style.id = 'video-admin-embedded-style'
				style.textContent = `
					.navbar,
					.navbar-default.sidebar,
					footer {
						display: none !important;
					}
					body {
						background: #fff !important;
						overflow: auto !important;
					}
					#wrapper,
					#page-wrapper,
					.container-fluid {
						margin: 0 !important;
						padding: 0 !important;
						min-height: 0 !important;
					}
					.video-admin-wrapper {
						padding: 16px !important;
					}
					.video-admin-wrapper .page-header {
						margin-top: 0 !important;
					}
				`
				doc.head.appendChild(style)
			}

			for (const link of doc.querySelectorAll('a[href]')) {
				this.embedAdminUrl(link, 'href')
			}
			for (const form of doc.querySelectorAll('form[action]')) {
				this.embedAdminUrl(form, 'action')
			}
			requestAnimationFrame(() => {
				this.frameReady = true
			})
		},
		embedAdminUrl(element, attribute) {
			const value = attribute === 'href' ? element.href : element.action
			if (!value) return
			const url = new URL(value)
			if (url.origin !== window.location.origin || !url.pathname.startsWith(ADMIN_BASE)) return
			url.searchParams.set('embedded', '1')
			element.setAttribute(attribute, `${url.pathname}${url.search}${url.hash}`)
			if (element.tagName === 'A') element.setAttribute('target', '_self')
		},
		addFrameBeforeUnloadListener(frameWindow) {
			if (!frameWindow || frameWindow === this.frameWindow) return
			this.removeFrameBeforeUnloadListener()
			this.frameWindow = frameWindow
			this.frameWindow.addEventListener('beforeunload', this.handleFrameBeforeUnload)
		},
		removeFrameBeforeUnloadListener() {
			if (!this.frameWindow) return
			this.frameWindow.removeEventListener('beforeunload', this.handleFrameBeforeUnload)
			this.frameWindow = null
		},
		handleFrameBeforeUnload() {
			this.frameReady = false
		}
	}
}
</script>
<style lang="stylus">
.c-video-admin
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	height: 100%
	background-color: white
	.ui-page-header
		flex: none
		background-color: $clr-grey-50
	.denied
		padding: 24px
		h2
			font-size: 20px
			font-weight: 500
			margin: 0 0 8px
		p
			color: $clr-secondary-text-light
			margin: 0
	.video-admin-layout
		flex: auto
		display: flex
		min-height: 0
	.video-admin-sidebar
		flex: none
		width: 204px
		overflow-y: auto
		padding: 8px 0
		border-right: border-separator()
		background-color: $clr-grey-50
		a
			display: block
			min-height: 36px
			line-height: 20px
			color: $clr-primary-text-light
			padding: 8px 18px
			text-decoration: none
			border-left: 3px solid transparent
			&.active
				background-color: white
				border-left-color: $clr-primary
				color: $clr-primary
				font-weight: 500
			&:hover
				background-color: $clr-grey-300
			&:focus-visible
				outline: 2px solid $clr-primary
				outline-offset: -2px
	.video-admin-frame-wrap
		position: relative
		flex: auto
		min-height: 0
		background: white
	.loading-indicator
		position: absolute
		inset: 0
		display: flex
		align-items: center
		justify-content: center
		color: $clr-secondary-text-light
	.video-admin-frame
		display: block
		width: 100%
		height: 100%
		border: 0
		background: white
		opacity: 0
		&.ready
			opacity: 1
	@media (max-width: 720px)
		.ui-page-header
			h1
				font-size: 22px
		.video-admin-layout
			flex-direction: column
		.video-admin-sidebar
			width: 100%
			display: flex
			overflow-x: auto
			overflow-y: hidden
			padding: 0
			border-right: 0
			border-bottom: border-separator()
			a
				flex: none
				min-height: 40px
				padding: 10px 14px
				border-left: 0
				border-bottom: 3px solid transparent
				white-space: nowrap
				&.active
					border-bottom-color: $clr-primary
		.video-admin-frame-wrap
			min-height: 420px
</style>
