<template lang="pug">
.c-app-bar
	.left
		button.hamburger(v-if="showActions", type="button", @click.stop="$emit('toggleSidebar')", aria-label="Toggle navigation")
			span.bar
			span.bar
			span.bar
		a.logo(:href="logoHref", :class="{anonymous: isAnonymous}")
			img(:src="theme.logo.url", :alt="world.title")
	// Admin quick link to Config
	router-link.settings(v-if="hasPermission('world:update')", :to="{name: 'admin:config'}", :aria-label="$t('RoomsSidebar:admin-config:label')")
		bunt-icon-button settings
	.user-section(v-if="showUser")
		div.user-profile(:class="{open: profileMenuOpen}", ref="userProfileEl", @click.self="toggleProfileMenu")
			avatar(v-if="!isAnonymous", :user="user", :size="32")
			span.display-name(v-if="!isAnonymous") {{ user.profile.display_name }}
			span.display-name(v-else) {{ $t('AppBar:user-anonymous') }}
			span.user-caret(role="button", :aria-expanded="String(profileMenuOpen)", aria-haspopup="true", tabindex="0", @click.stop="toggleProfileMenu", @keydown.enter.prevent="toggleProfileMenu", @keydown.space.prevent="toggleProfileMenu", :class="{open: profileMenuOpen}")
		.profile-dropdown(v-if="profileMenuOpen", role="menu")
			template(v-for="item in menuItems", :key="item.key")
				div.menu-separator(v-if="item.separatorBefore")
				a.menu-item(:href="getItemHref(item)", role="menuitem", @click.prevent="onMenuItem(item)")
					span.menu-item-icon(v-if="item.icon" aria-hidden="true")
						i(:class="iconClasses[item.icon]")
					span.menu-item-label {{ item.label }}
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import theme from 'theme'
import Avatar from 'components/Avatar'
import config from 'config'

const props = defineProps({
	showActions: {
		type: Boolean,
		default: true
	},
	showUser: {
		type: Boolean,
		default: false
	}
})

const ICON_CLASSES = {
	dashboard: 'fa fa-tachometer',
	orders: 'fa fa-shopping-cart',
	events: 'fa fa-calendar',
	organizers: 'fa fa-users',
	account: 'fa fa-user',
	admin: 'fa fa-cog',
	logout: 'fa fa-sign-out',
	tickets: 'fa fa-ticket',
	talks: 'fa fa-microphone',
	profile: 'fa fa-user-circle'
}

const PROFILE_MENU_ITEMS = [
	{
		key: 'dashboard',
		label: 'Dashboard',
		icon: 'dashboard',
		externalPath: 'common/'
	},
	{ key: 'orders', label: 'My Orders', externalPath: 'common/orders/', icon: 'orders' },
	{ key: 'sessions', label: 'My Sessions', externalPath: 'common/sessions/', icon: 'tickets' },
	{ key: 'events', label: 'My Events', externalPath: 'common/events/', icon: 'events' },
	{ key: 'organizers', label: 'Organizers', externalPath: 'common/organizers/', icon: 'organizers' },
	{ key: 'profile', label: 'Profile', route: { name: 'preferences' }, separatorBefore: true, icon: 'profile' },
	{ key: 'account', label: 'Account', externalPath: 'common/account/general', icon: 'account' },
	{ key: 'logout', label: 'Logout', action: 'logout', icon: 'logout', separatorBefore: true }
]

const emit = defineEmits(['toggleSidebar'])

const store = useStore()
const router = useRouter()

const user = computed(() => store.state.user)
const world = computed(() => store.state.world)
const hasPermission = computed(() => (permission) => {
	return store.getters.hasPermission(permission)
})

const isAnonymous = computed(() => Object.keys(user.value.profile || {}).length === 0)

const logoHref = computed(() => {
	try {
		return buildBaseSansVideo() + 'common/'
	} catch (e) {
		return '/common/'
	}
})

const profileMenuOpen = ref(false)
const menuItems = ref(PROFILE_MENU_ITEMS)
const iconClasses = ICON_CLASSES
const userProfileEl = ref(null)

function buildBaseSansVideo() {
	const { protocol, host } = window.location
	const basePath = config?.basePath ?? ''
	if (!basePath) {
		return `${protocol}//${host}/`
	}
	const segments = basePath.split('/').filter(Boolean)
	const videoIndex = segments.lastIndexOf('video')
	if (videoIndex === -1) {
		return `${protocol}//${host}/`
	}
	const prefixEnd = Math.max(0, videoIndex - 2)
	const prefixSegments = segments.slice(0, prefixEnd)
	const prefix =
		prefixSegments.length > 0
			? `/${prefixSegments.join('/')}/`
			: '/'
	return `${protocol}//${host}${prefix}`
}
function toggleProfileMenu() {
	profileMenuOpen.value = !profileMenuOpen.value
}
function closeProfileMenu() {
	profileMenuOpen.value = false
}
function logout() {
	// Clear webapp tokens
	localStorage.removeItem('token')
	localStorage.removeItem('clientId')
	// Navigate to Django logout which handles session and redirects to login
	const logoutUrl = buildBaseSansVideo() + 'common/logout/'
	window.location.href = logoutUrl
}
function onMenuItem(item) {
	if (item.action === 'logout') {
		logout()
		closeProfileMenu()
		return
	}
	if (item.route) {
		router.push(item.route).catch(() => {})
		closeProfileMenu()
		return
	}
	if (item.externalPath) {
		try {
			const base = buildBaseSansVideo()
			window.location.assign(base + item.externalPath)
		} catch (e) {
			window.location.assign('/' + item.externalPath)
		}
		closeProfileMenu()
		return
	}
	try {
		const base = buildBaseSansVideo()
		window.location.assign(base)
	} catch (e) {
		router.push('/').catch(() => {})
	}
	closeProfileMenu()
}

function getItemHref(item) {
	if (item.action === 'logout') return '#logout'
	if (item.route) return router.resolve(item.route).href
	if (item.externalPath) {
		try {
			const base = buildBaseSansVideo()
			return base + item.externalPath
		} catch (e) {
			return '/' + item.externalPath
		}
	}
	return '#'
}

function handleClickOutside(e) {
	if (!profileMenuOpen.value) return
	const el = userProfileEl.value
	if (el && !el.contains(e.target)) closeProfileMenu()
}
function handleGlobalKeydown(e) {
	if (e.key === 'Escape' && profileMenuOpen.value) closeProfileMenu()
}

onMounted(() => {
	if (!document.querySelector('link[href*="font-awesome"]')) {
		const link = document.createElement('link')
		link.rel = 'stylesheet'
		link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css'
		document.head.appendChild(link)
	}
	document.addEventListener('click', handleClickOutside)
	document.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
	document.removeEventListener('click', handleClickOutside)
	document.removeEventListener('keydown', handleGlobalKeydown)
})
</script>
<style lang="stylus">
.c-app-bar
	position: fixed
	top: 0
	left: 0
	right: 0
	height: 48px
	display: flex
	align-items: center
	justify-content: space-between
	padding: 0 8px
	background-color: var(--clr-sidebar)
	white-space: nowrap
	overflow: visible
	z-index: 120
	.bunt-icon-button
		icon-button-style(color: var(--clr-sidebar-text-primary), style: clear)
	.left
		display: flex
		align-items: center
		gap: 4px
		.hamburger
			appearance: none
			background: none
			border: none
			padding: 0.5rem
			margin: 0
			width: auto
			height: auto
			display: flex
			flex-direction: column
			justify-content: center
			align-items: flex-start
			cursor: pointer
			-webkit-tap-highlight-color: transparent
			outline: none
			&:focus-visible
				outline: 2px solid var(--clr-primary)
				outline-offset: 2px
			.bar
				display: block
				width: 22px
				height: 3px
				background: var(--clr-sidebar-text-primary)
				border-radius: 2px
				&:not(:last-child)
					margin-bottom: 5px
	.logo
		margin-left: 0
		font-size: 24px
		height: 40px
		&.anonymous
			pointer-events: none
		img
			height: 100%
			max-width: 100%
			object-fit: contain
			margin: 0
			padding: 0
	.settings
		margin-left: auto
		.bunt-icon-button
			icon-button-style(color: var(--clr-sidebar-text-primary), style: clear)
	.user-section
		display: flex
		align-items: center
		gap: 8px
		position: relative
	.user-profile
		display: flex
		align-items: center
		gap: 8px
		padding: 4px 8px
		color: var(--clr-sidebar-text-primary)
		text-decoration: none
		position: relative
		cursor: pointer
		&.open
			.user-caret
				transform: rotate(180deg)
		.display-name
			font-size: 14px
			font-weight: 500
			max-width: 140px
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap
		.user-caret
			width: 0
			height: 0
			border-left: 5px solid transparent
			border-right: 5px solid transparent
			border-top: 6px solid var(--clr-sidebar-text-primary)
			margin-left: 2px
			cursor: pointer
	.logout-btn
		appearance: none
		background: none
		border: none
		padding: 8px 12px
		cursor: pointer
		color: var(--clr-sidebar-text-primary)
		display: flex
		align-items: center
		justify-content: center
		border-radius: 4px
		transition: background-color 0.2s, color 0.2s
		&:hover
			background-color: rgba(0, 0, 0, 0.1)
			color: var(--clr-danger)
		&:focus-visible
			outline: 2px solid var(--clr-primary)
		i
			font-size: 18px
	.user-section
		.profile-dropdown
			position: absolute
			top: calc(100% + 6px)
			right: 0
			width: 220px
			max-height: 500px
			overflow: visible
			background: var(--clr-surface, #fff)
			color: var(--clr-text, #111)
			border: 1px solid rgba(0,0,0,0.2)
			border-radius: 2px
			box-shadow: 0 3px 8px rgba(0,0,0,0.175), 0 1px 3px rgba(0,0,0,0.105)
			padding: 6px 0
			z-index: 120
			font-size: 14px
			user-select: none
			.menu-item
				appearance: none
				background: none
				border: none
				width: 100%
				display: flex
				align-items: center
				gap: 8px
				text-align: left
				padding: 8px 10px
				cursor: pointer
				color: inherit
				font: inherit
				text-decoration: none
				&:hover, &:focus-visible
					background: rgba(0,0,0,0.06)
				.menu-item-icon
					color: var(--clr-primary)
					flex: 0 0 auto
					width: 18px
					height: 18px
					display: inline-flex
					align-items: center
					justify-content: center
					opacity: .9
					i
						font-size: 16px
						line-height: 1
						width: 16px
						height: 16px
						text-align: center
						color: currentColor
				.menu-item-label
					flex: 1 1 auto
					min-width: 0
					white-space: nowrap
					text-overflow: ellipsis
					overflow: hidden
			.menu-separator
				height: 1px
				background: rgba(0,0,0,0.08)
				margin: 6px 0


@media (max-width: 560px)
	.c-app-bar
		.user-profile .display-name
			display: none
		.logo img
			max-width: 120px

#app.override-sidebar-collapse .c-app-bar
	border-bottom: none
	.bunt-icon-button
		visibility: hidden
</style>
