<template lang="pug">
prompt.c-channel-browser(@close="$emit('close')", :scrollable="false")
	.content
		h2 {{ $t('Browse channels') }}
		p {{ $t('Here, we show you a list of all channels that you can join for this event.') }}
			a(href="#", @click="$emit('createChannel')", v-if="hasPermission('world:rooms.create.chat') && $features.enabled('chat')")  {{ $t('Alternatively, you can create a new channel.') }}
		bunt-input(icon="search", name="search", :placeholder="$t('Search channels')", v-model="search")
		scrollbars.channels(y)
			router-link.channel(v-for="channel of searchedChannels", :to="{name: 'room', params: {roomId: channel.room.id}}", @click="$emit('close')")
				.channel-info
					.name(v-html="$emojify(channel.room.name)")
					.description(v-html="$emojify(channel.room.description)")
				.actions
					template(v-if="channel.channelJoined")
						bunt-button#btn-view {{ $t('view') }}
					template(v-else)
						bunt-button#btn-preview {{ $t('preview') }}
						bunt-button#btn-join(@click="$store.dispatch('chat/join', channel.room)") {{ $t('join') }}
			.no-results(v-if="search && searchedChannels.length === 0") {{ $t('Sorry, could not find any matching channels') }}
</template>
<script>
import {mapGetters, mapState} from 'vuex'
import Prompt from 'components/Prompt'
import fuzzysearch from 'lib/fuzzysearch'

export default {
	components: { Prompt },
	emits: ['close', 'createChannel'],
	data() {
		return {
			search: ''
		}
	},
	computed: {
		...mapState(['rooms']),
		...mapState('chat', ['joinedChannels']),
		...mapGetters(['hasPermission']),
		channels() {
			return this.rooms
				.filter(room => room.modules.length === 1 && room.modules[0].type === 'chat.native')
				.map(room => ({room, channelJoined: this.joinedChannels.some(channel => channel.id === room.modules[0].channel_id)}))
		},
		searchedChannels() {
			if (!this.search) return this.channels
			const query = this.search.toLowerCase()
			return this.channels.filter(channel => {
				const name = this.$localize(channel.room.name).toLowerCase()
				const description = this.$localize(channel.room.description).toLowerCase()
				return fuzzysearch(query, name) || fuzzysearch(query, description)
			})
		}
	}
}
</script>
<style lang="stylus">
.c-channel-browser
	.prompt-wrapper
		width: 580px
		height: 80vh
	.content
		min-height: 0
		display: flex
		flex-direction: column
	h2
		margin: 16px 16px 8px 16px
	p
		margin: 0 16px 8px 16px
		a
			font-weight: 600
	.bunt-input
		margin: 0 16px
	.channels
		.channel
			padding: 16px
			display: flex
			align-items: center
			&:not(:first-child)
				border-top: border-separator()
			.channel-info
				flex: auto
				color: $clr-primary-text-light
				.name
					font-size: 16px
					font-weight: 500
				.description
					white-space: pre-wrap
			.actions
				flex: none
				#btn-view, #btn-preview
					themed-button-secondary()
				#btn-join
					themed-button-primary()
		.no-results
			margin: 16px
			text-align: center
</style>
