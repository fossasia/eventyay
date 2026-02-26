<template lang="pug">
.c-app-bar
	.left
		button.hamburger(v-if="showActions", type="button", @click.stop="$emit('toggleSidebar')", aria-label="Toggle navigation")
			span.bar
			span.bar
			span.bar
		a.logo(:href="logoHref", :class="{anonymous: isAnonymous}")
			img(:src="theme.logo.url", :alt="world.title")
		span.admin-indicator(
			v-if="isAdminMode"
			@mouseenter="onAdminIndicatorEnter"
			@mouseleave="onAdminIndicatorLeave"
		) Admin mode ON
		div.admin-tooltip(
			v-if="isAdminMode && showAdminTooltip"
		) Admin mode is ON. Go to the tickets area to disable it and view this event as a staff member.
	router-link.settings(v-if="hasPermission('world:update')", :to="{name: 'admin:config'}", :aria-label="$t('RoomsSidebar:admin-config:label')")
		bunt-icon-button settings
	.user-section(v-if="showUser")
		.user-menu(ref="userMenuEl")
			div.user-profile(:class="{open: profileMenuOpen}", @click.stop="toggleProfileMenu")
				avatar(v-if="!isAnonymous", :user="user", :size="32")
				span.display-name(v-if="!isAnonymous") {{ user.profile.display_name }}
				span.display-name(v-else) {{ $t('AppBar:user-anonymous') }}
				span.user-caret(role="button", :aria-expanded="String(profileMenuOpen)", aria-haspopup="true", tabindex="0", @click.stop="toggleProfileMenu", @keydown.enter.prevent="toggleProfileMenu", @keydown.space.prevent="toggleProfileMenu", :class="{open: profileMenuOpen}")
			transition(name="dropdown-reveal")
				.profile-dropdown(v-if="profileMenuOpen", role="menu", @click.stop)
					template(v-for="item in menuItems", :key="item.key")
						div.menu-separator(v-if="item.separatorBefore")
						template(v-if="item.children")
							div.menu-item.menu-item-parent(:class="{open: dashboardSubmenuOpen}", role="menuitem", tabindex="0", @click.prevent.stop="toggleDashboardSubmenu", @keydown.enter.prevent.stop="toggleDashboardSubmenu", @keydown.space.prevent.stop="toggleDashboardSubmenu")
								span.menu-item-icon(v-if="item.icon" aria-hidden="true")
									i(:class="iconClasses[item.icon]")
								span.menu-item-label {{ item.label }}
								div.profile-submenu(v-if="dashboardSubmenuOpen", role="menu", @click.stop)
									a.menu-item(v-for="child in item.children", :key="child.key", :href="getItemHref(child)", role="menuitem", @click.prevent="onMenuItem(child)")
										span.menu-item-icon(v-if="child.icon" aria-hidden="true")
											i(:class="iconClasses[child.icon]")
										span.menu-item-label {{ child.label }}
						template(v-else)
							a.menu-item(:href="getItemHref(item)", role="menuitem", @click.prevent="onMenuItem(item)")
								span.menu-item-icon(v-if="item.icon" aria-hidden="true")
									i(:class="iconClasses[item.icon]")
								span.menu-item-label {{ item.label }}
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { jwtDecode } from 'jwt-decode'
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
	control: 'fa fa-cogs',
	profile: 'fa fa-user-circle'
}

const PROFILE_MENU_ITEMS = [
	{
		key: 'dashboard',
		label: 'Dashboard',
		icon: 'dashboard',
		children: [
			{ key: 'dashboard:main', label: 'Main dashboard', icon: 'dashboard', externalPath: 'common/' },
			{ key: 'dashboard:tickets', label: 'Tickets', icon: 'tickets', externalPath: 'control/' },
			{ key: 'dashboard:talks', label: 'Talks', icon: 'talks', externalPath: 'orga/event/' }
		]
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
const token = computed(() => store.state.token)
const hasPermission = computed(() => (permission) => {
	return store.getters.hasPermission(permission)
})

const isAdminMode = computed(() => {
	const rawToken = token.value || localStorage.getItem('token')
	if (!rawToken) return false
	try {
		const decoded = jwtDecode(rawToken)
		return Array.isArray(decoded?.traits) && decoded.traits.includes('admin')
	} catch (error) {
		if (process.env.NODE_ENV === 'development') {
			console.error('Failed to decode JWT token:', error)
		}
		return false
	}
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
const dashboardSubmenuOpen = ref(false)
const menuItems = ref(PROFILE_MENU_ITEMS)
const iconClasses = ICON_CLASSES
const userMenuEl = ref(null)
const showAdminTooltip = ref(false)

function onAdminIndicatorEnter() {
	if (!isAdminMode.value) return
	showAdminTooltip.value = true
}

function onAdminIndicatorLeave() {
	showAdminTooltip.value = false
}

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
	if (!profileMenuOpen.value) {
		dashboardSubmenuOpen.value = false
	}
}
function closeProfileMenu() {
	profileMenuOpen.value = false
	dashboardSubmenuOpen.value = false
}
function toggleDashboardSubmenu() {
	dashboardSubmenuOpen.value = !dashboardSubmenuOpen.value
}
function logout() {
	localStorage.removeItem('token')
	localStorage.removeItem('clientId')
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
	if (item.children) return '#dashboard'
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
	const el = userMenuEl.value
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
	font-size: 14px
	font-weight: 400
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
		position: relative
		.admin-indicator
			margin-left: 8px
			font-size: 11px
			font-weight: 600
			text-transform: uppercase
			letter-spacing: .05em
			color: #f44336
			cursor: default
		.admin-tooltip
			position: absolute
			top: 52px
			left: 8px
			right: auto
			max-width: 260px
			padding: 4px 8px
			border-radius: 3px
			background: rgba(0, 0, 0, 0.8)
			color: #fff
			font-size: 11px
			white-space: normal
			z-index: 130
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
	.user-menu
		position: relative
	.user-profile
		display: flex
		align-items: center
		gap: 8px
		padding: 6px 10px
		border-radius: 4px
		color: var(--clr-sidebar-text-primary)
		text-decoration: none
		position: relative
		cursor: pointer
		transition: background-color 0.15s ease-in-out, color 0.15s ease-in-out
		&:hover
			background-color: transparent
		&:focus-visible
			outline: 2px solid var(--clr-primary)
			outline-offset: 2px
		&.open
			.user-caret
				transform: rotate(180deg)
		.display-name
			font-size: inherit
			font-weight: 400
			max-width: 140px
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap
		.user-caret
			width: 0
			height: 0
			border-left: 5px solid transparent
			border-right: 5px solid transparent
			border-top: 6px solid currentColor
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
			top: calc(100% + 2px)
			right: 0
			min-width: 160px
			max-width: 400px
			width: auto
			max-height: 500px
			overflow: visible
			background: white
			color: #495057
			border: 1px solid #e9ecef
			border-radius: var(--size-border-radius, 0.25rem)
			box-shadow: var(--shadow-light, 0 0 6px 1px rgb(0 0 0 / 0.1))
			padding: 0
			z-index: 120
			font-size: 15px
			user-select: none
			&::before,
			&::after
				position: absolute
				display: inline-block
				content: " "
			&::before
				top: -16px
				right: 12px
				border: 8px solid transparent
				border-bottom-color: rgb(27 31 35 / 0.15)
			&::after
				top: -14px
				right: 13px
				border: 7px solid transparent
				border-bottom-color: white
			.menu-item
				appearance: none
				background: none
				border: none
				width: 100%
				box-sizing: border-box
				display: flex
				align-items: center
				gap: 8px
				text-align: left
				padding: 8px 18px
				min-height: 0
				line-height: 1.25
				cursor: pointer
				color: inherit
				font: inherit
				font-weight: 400
				text-decoration: none
				transition: color 0.15s ease-in-out, background-color 0.15s ease-in-out
				&:hover, &:focus-visible
					background: var(--clr-primary-alpha-18)
					color: var(--clr-primary-darken-15, var(--clr-primary))
					text-decoration: none
				&:focus-visible
					outline: none
				.menu-item-icon
					color: currentColor
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
			.menu-item-parent
				position: relative
			.submenu-caret
				margin-left: auto
				width: 0
				height: 0
				border-top: 5px solid transparent
				border-bottom: 5px solid transparent
				border-left: 6px solid currentColor
				opacity: 0.75
			.profile-submenu
				position: absolute
				top: 0
				right: 100%
				left: auto
				margin-right: 8px
				min-width: 160px
				max-width: 400px
				width: auto
				background: white
				color: #495057
				border: 1px solid #e9ecef
				border-radius: var(--size-border-radius, 0.25rem)
				box-shadow: var(--shadow-light, 0 0 6px 1px rgb(0 0 0 / 0.1))
				padding: 0
				z-index: 121
				&::before,
				&::after
					position: absolute
					display: inline-block
					content: " "
				&::before
					top: 10px
					right: -16px
					left: auto
					border: 8px solid transparent
					border-left-color: rgb(27 31 35 / 0.15)
				&::after
					top: 11px
					right: -14px
					left: auto
					border: 7px solid transparent
					border-left-color: white
			.menu-separator
				height: 1px
				background: rgba(0,0,0,0.08)
				margin: 6px 0

.dropdown-reveal-enter-active,
.dropdown-reveal-leave-active
	transition: opacity 120ms ease-out, transform 120ms ease-out
.dropdown-reveal-enter-from,
.dropdown-reveal-leave-to
	opacity: 0
	transform: translateY(-4px)


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
