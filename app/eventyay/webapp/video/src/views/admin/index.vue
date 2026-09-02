<template lang="pug">
.c-admin-overview(v-scrollbar.y="")
	.overview-header
		.title-section
			h1 {{ $t('Video Management') }}
			.event-subtitle(v-if="world && world.title")
				span.event-name(v-html="$emojify(world.title)")

	.stats-grid
		.stat-card
			.stat-icon.stages
				i.mdi.mdi-video-vintage
			.stat-content
				.stat-value {{ stageRooms.length }}
				.stat-label {{ $t('Stages & Streams') }}
		.stat-card
			.stat-icon.rooms
				i.mdi.mdi-door-open
			.stat-content
				.stat-value {{ allRooms.length }}
				.stat-label {{ $t('Total Rooms') }}
		.stat-card
			.stat-icon.viewers
				i.mdi.mdi-account-group
			.stat-content
				.stat-value {{ totalViewersCount }}
				.stat-label {{ $t('Active Viewers') }}
		.stat-card
			.stat-icon.announcements
				i.mdi.mdi-bullhorn
			.stat-content
				.stat-value {{ announcementsList.length }}
				.stat-label {{ $t('Announcements') }}

	.section-block
		.section-header
			h2 {{ $t('Quick Actions') }}
		.quick-actions-grid
			router-link.action-card(:to="{name: 'admin:rooms:index'}", v-if="hasPermission('room:update')")
				.card-icon
					i.mdi.mdi-door-open
				.card-details
					.card-title {{ $t('Rooms & Stages') }}
					.card-desc {{ $t('Create, configure and manage video rooms') }}
			router-link.action-card(:to="{name: 'admin:announcements'}", v-if="hasPermission('world:announce')")
				.card-icon
					i.mdi.mdi-bullhorn
				.card-details
					.card-title {{ $t('Announcements') }}
					.card-desc {{ $t('Broadcast announcements to all attendees') }}
			router-link.action-card(:to="{name: 'admin:users'}", v-if="hasPermission('world:users.list')")
				.card-icon
					i.mdi.mdi-account-multiple
				.card-details
					.card-title {{ $t('User Management') }}
					.card-desc {{ $t('View attendees, grant roles, and moderate') }}
			router-link.action-card(:to="{name: 'admin:chat:index'}", v-if="hasPermission('room:update')")
				.card-icon
					i.mdi.mdi-chat-processing
				.card-details
					.card-title {{ $t('Chat Rooms') }}
					.card-desc {{ $t('Configure public and private chat channels') }}

	.section-block
		.section-header
			h2 {{ $t('Live Rooms & Streams') }}
			router-link.section-link(:to="{name: 'admin:rooms:index'}", v-if="hasPermission('room:update')")
				span {{ $t('View all rooms') }}
				i.mdi.mdi-chevron-right(aria-hidden="true")
		.rooms-table-card
			.table-responsive
				table.overview-table(v-if="allRooms.length")
					thead
						tr
							th {{ $t('Room Name') }}
							th {{ $t('Type') }}
							th {{ $t('Viewers') }}
							th.actions-col {{ $t('Actions') }}
					tbody
						tr(v-for="room in allRooms.slice(0, 8)", :key="room.id")
							td.room-name-cell
								i.mdi(:class="getRoomIcon(room)")
								span(v-html="$emojify(room.name)")
							td
								span.type-badge {{ getRoomTypeLabel(room) }}
							td.viewers-cell
								i.mdi.mdi-account-outline
								span {{ getRoomViewerCount(room) }}
							td.actions-col
								router-link.btn-table-action(:to="{name: 'admin:rooms:item', params: {roomId: room.id}}", v-if="hasPermission('room:update')")
									i.mdi.mdi-pencil(aria-hidden="true")
									span {{ $t('Edit') }}
								router-link.btn-table-action.secondary(:to="{name: 'room', params: {roomId: room.id}}")
									i.mdi.mdi-eye(aria-hidden="true")
									span {{ $t('Preview') }}
			.empty-state(v-if="!allRooms.length")
				p {{ $t('No rooms created yet.') }}
				router-link.btn-primary(:to="{name: 'admin:rooms:index'}", v-if="hasPermission('room:update')") {{ $t('Create First Room') }}

	.section-block(v-if="announcementsList.length")
		.section-header
			h2 {{ $t('Recent Announcements') }}
			router-link.section-link(:to="{name: 'admin:announcements'}", v-if="hasPermission('world:announce')")
				span {{ $t('Manage announcements') }}
				i.mdi.mdi-chevron-right(aria-hidden="true")
		.announcements-card
			.announcement-item(v-for="item in announcementsList.slice(0, 4)", :key="item.id")
				.announcement-icon
					i.mdi.mdi-bullhorn-outline
				.announcement-body
					.announcement-text {{ item.text }}
					.announcement-meta(v-if="item.show_until")
						span {{ $t('Active until:') }} {{ formatTime(item.show_until) }}
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'
import { inferRoomType, inferType } from 'lib/room-types'

export default {
	name: 'VideoOrganiserOverview',
	computed: {
		...mapState(['world', 'connected', 'rooms', 'roomViewers']),
		...mapGetters(['hasPermission']),
		allRooms() {
			return this.rooms || []
		},
		stageRooms() {
			return this.allRooms.filter(room =>
				room.modules && room.modules.some(m => ['livestream.native', 'livestream.youtube', 'call.janus'].includes(m.type))
			)
		},
		totalViewersCount() {
			if (!this.allRooms.length) return 0
			let count = 0
			for (const room of this.allRooms) {
				if (typeof room.users === 'number') {
					count += room.users
				}
			}
			return count
		},
		announcementsList() {
			return this.$store.getters['announcement/announcements'] || []
		}
	},
	methods: {
		getRoomTypeLabel(room) {
			const inferred = Array.isArray(room.module_config)
				? inferType({ module_config: room.module_config })
				: inferRoomType(room)
			if (inferred?.name) return this.$localize(inferred.name)
			if (room.modules?.some(m => ['livestream.native', 'livestream.youtube'].includes(m.type))) return this.$t('Stage')
			if (room.modules?.some(m => m.type.startsWith('call.'))) return this.$t('Video Call')
			if (room.modules?.some(m => m.type === 'chat.native')) return this.$t('Text Channel')
			return this.$t('Room')
		},
		getRoomIcon(room) {
			if (room.modules?.some(m => ['livestream.native', 'livestream.youtube'].includes(m.type))) return 'mdi-video-vintage'
			if (room.modules?.some(m => m.type.startsWith('call.'))) return 'mdi-video'
			if (room.modules?.some(m => m.type === 'chat.native')) return 'mdi-chat-outline'
			return 'mdi-door-open'
		},
		getRoomViewerCount(room) {
			if (typeof room.users === 'number') return room.users
			if (typeof room.users === 'string') return room.users
			return 0
		},
		formatTime(timestamp) {
			if (!timestamp) return ''
			return moment(timestamp).format('LLL')
		}
	}
}
</script>
<style lang="stylus">
.c-admin-overview
	display: flex
	flex-direction: column
	flex: auto
	background-color: #f8f8f8
	min-height: 0
	height: 100%
	box-sizing: border-box
	padding: 24px 28px

	+below('m')
		padding: 16px

	.overview-header
		display: flex
		align-items: center
		justify-content: space-between
		margin-bottom: 24px
		flex-wrap: wrap
		gap: 16px

		.title-section
			h1
				font-size: 24px
				font-weight: 700
				color: #1e293b
				margin: 0 0 6px 0

			.event-subtitle
				display: flex
				align-items: center
				gap: 10px
				font-size: 13.5px
				color: #64748b
				flex-wrap: wrap

				.event-name
					font-weight: 500

	.stats-grid
		display: grid
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr))
		gap: 14px
		margin-bottom: 24px

		.stat-card
			display: flex
			align-items: center
			gap: 14px
			padding: 16px 18px
			background-color: #ffffff
			border-radius: 8px
			border: 1px solid #e7e7e7
			box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03)

			.stat-icon
				display: flex
				align-items: center
				justify-content: center
				width: 44px
				height: 44px
				border-radius: 8px
				font-size: 22px

				&.stages
					background-color: #eff6ff
					color: #0284c7

				&.rooms
					background-color: #f0fdf4
					color: #16a34a

				&.viewers
					background-color: #faf5ff
					color: #9333ea

				&.announcements
					background-color: #fff7ed
					color: #ea580c

			.stat-content
				.stat-value
					font-size: 22px
					font-weight: 700
					color: #0f172a
					line-height: 1.2

				.stat-label
					font-size: 12.5px
					font-weight: 500
					color: #64748b
					margin-top: 2px

	.section-block
		margin-bottom: 24px

		.section-header
			display: flex
			align-items: center
			justify-content: space-between
			margin-bottom: 12px

			h2
				font-size: 16px
				font-weight: 700
				color: #1e293b
				margin: 0

			.section-link
				display: inline-flex
				align-items: center
				gap: 4px
				font-size: 13px
				font-weight: 600
				color: #0284c7
				text-decoration: none

				&:hover
					color: #0369a1
					text-decoration: underline

		.quick-actions-grid
			display: grid
			grid-template-columns: repeat(4, 1fr)
			gap: 14px

			+below('l')
				grid-template-columns: repeat(2, 1fr)

			+below('s')
				grid-template-columns: 1fr

			.action-card
				display: flex
				align-items: flex-start
				gap: 12px
				padding: 14px 16px
				background-color: #ffffff
				border-radius: 8px
				border: 1px solid #e7e7e7
				text-decoration: none
				transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease

				.card-icon
					display: flex
					align-items: center
					justify-content: center
					width: 36px
					height: 36px
					border-radius: 6px
					background-color: #f1f5f9
					color: #334155
					font-size: 18px
					flex-shrink: 0

				.card-details
					.card-title
						font-size: 14px
						font-weight: 600
						color: #1e293b
						margin-bottom: 2px

					.card-desc
						font-size: 12px
						color: #64748b
						line-height: 1.35

				&:hover
					border-color: #cbd5e1
					box-shadow: 0 3px 6px -1px rgba(0, 0, 0, 0.06)
					transform: translateY(-1px)

					.card-icon
						background-color: #e0f2fe
						color: #0284c7

	.rooms-table-card, .announcements-card
		background-color: #ffffff
		border-radius: 8px
		border: 1px solid #e7e7e7
		overflow: hidden
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03)

	.table-responsive
		overflow-x: auto
		-webkit-overflow-scrolling: touch

	.overview-table
		width: 100%
		border-collapse: collapse
		text-align: left

		th
			padding: 11px 16px
			font-size: 11.5px
			font-weight: 700
			text-transform: uppercase
			letter-spacing: 0.5px
			color: #64748b
			background-color: #f8fafc
			border-bottom: 1px solid #e7e7e7

		td
			padding: 12px 16px
			font-size: 13.5px
			color: #334155
			border-bottom: 1px solid #f1f5f9

		tr:last-child td
			border-bottom: none

		.room-name-cell
			display: flex
			align-items: center
			gap: 8px
			font-weight: 500
			color: #1e293b

			.mdi
				font-size: 18px
				color: #64748b

		.type-badge
			display: inline-block
			padding: 2px 7px
			border-radius: 4px
			font-size: 11.5px
			font-weight: 500
			background-color: #f1f5f9
			color: #475569

		.viewers-cell
			display: inline-flex
			align-items: center
			gap: 5px
			font-size: 13px
			color: #64748b

			.mdi
				font-size: 15px

		.actions-col
			text-align: right

		.btn-table-action
			display: inline-flex
			align-items: center
			gap: 4px
			padding: 3px 8px
			margin-left: 6px
			border-radius: 4px
			font-size: 12px
			font-weight: 600
			text-decoration: none
			background-color: #f1f5f9
			color: #334155
			transition: background-color 0.15s ease

			.mdi
				font-size: 13px

			&:hover
				background-color: #e2e8f0
				color: #0f172a

			&.secondary
				background-color: transparent
				color: #64748b

				&:hover
					background-color: #f8fafc
					color: #0f172a

	.empty-state
		padding: 32px 16px
		text-align: center
		color: #64748b

		p
			margin-bottom: 12px
			font-size: 13.5px

		.btn-primary
			display: inline-flex
			align-items: center
			gap: 6px
			padding: 6px 14px
			border-radius: 6px
			background-color: #0284c7
			color: #ffffff
			font-size: 13px
			font-weight: 600
			text-decoration: none

			&:hover
				background-color: #0369a1

	.announcements-card
		padding: 4px 16px

		.announcement-item
			display: flex
			align-items: flex-start
			gap: 12px
			padding: 10px 0
			border-bottom: 1px solid #f1f5f9

			&:last-child
				border-bottom: none

			.announcement-icon
				display: flex
				align-items: center
				justify-content: center
				width: 30px
				height: 30px
				border-radius: 6px
				background-color: #fff7ed
				color: #ea580c
				font-size: 15px
				flex-shrink: 0

			.announcement-body
				flex: auto

				.announcement-text
					font-size: 13.5px
					font-weight: 500
					color: #1e293b
					line-height: 1.4

				.announcement-meta
					font-size: 11.5px
					color: #94a3b8
					margin-top: 3px
</style>
